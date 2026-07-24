# plugins/inverter/sungrow_modbus_plugin.py
"""
Sungrow Modbus Inverter Plugin

This plugin communicates with Sungrow SH / SG hybrid inverters using Modbus TCP
or Modbus RTU (local only). It reads PV/AC and hybrid battery input-register
blocks aligned with community Home Assistant mappings.

Features:
- Dual connection support (Modbus TCP and Serial RTU)
- Shared ModbusInverterPluginBase connection and block reads
- PV/AC power and energy monitoring
- Hybrid battery voltage/power/SOC block

Supported Models:
- Sungrow SH hybrid series
- Sungrow SG hybrid-compatible models

Protocol Reference: Sungrow Modbus (community / Home Assistant aligned)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from plugins.plugin_interface import StandardDataKeys
from plugins.inverter.modbus_inverter_base import ModbusInverterPluginBase
from plugins.inverter.sungrow_modbus_constants import (
    SUNGROW_PV,
    SUNGROW_PV_START,
    SUNGROW_PV_COUNT,
    SUNGROW_BAT,
    SUNGROW_BAT_START,
    SUNGROW_BAT_COUNT,
)

if TYPE_CHECKING:
    from core.app_state import AppState


class SungrowModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "sungrow_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["SH", "SG Hybrid"],
        "status": "testing",
        "api_version": 1,
    }
    manufacturer_name = "Sungrow"
    default_baud = 9600

    @property
    def name(self) -> str:
        return "sungrow_modbus"

    @property
    def pretty_name(self) -> str:
        return "Sungrow Modbus"

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        data = self._static_shell(model="Sungrow-SH")
        self.last_known_static_data = data
        return data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            # Sungrow typically exposes runtime on input registers
            regs = self._read_input_block(SUNGROW_PV_START, SUNGROW_PV_COUNT)
            if not regs:
                regs = self._read_holding_block(SUNGROW_PV_START, SUNGROW_PV_COUNT)
            if not regs:
                self.last_error_message = "Failed to read Sungrow PV block"
                self.disconnect()
                return None
            d = self._decode_block(regs, SUNGROW_PV, SUNGROW_PV_START)

            bat = {}
            bregs = self._read_input_block(SUNGROW_BAT_START, SUNGROW_BAT_COUNT)
            if not bregs:
                bregs = self._read_holding_block(SUNGROW_BAT_START, SUNGROW_BAT_COUNT)
            if bregs:
                bat = self._decode_block(bregs, SUNGROW_BAT, SUNGROW_BAT_START)

            batt_p = bat.get("battery_power")
            load = bat.get("load_power_hybrid") or d.get("ac_power")

            return {
                StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: "Normal",
                StandardDataKeys.BATTERY_STATUS_TEXT: self._battery_status_from_power(batt_p),
                StandardDataKeys.AC_POWER_WATTS: d.get("ac_power"),
                StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: d.get("pv_total_power"),
                StandardDataKeys.LOAD_TOTAL_POWER_WATTS: load,
                StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
                StandardDataKeys.BATTERY_CURRENT_AMPS: bat.get("battery_current"),
                StandardDataKeys.BATTERY_VOLTAGE_VOLTS: bat.get("battery_voltage"),
                StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: bat.get("battery_soc"),
                StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: bat.get("battery_temp"),
                StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_l1_voltage"),
                StandardDataKeys.GRID_L1_CURRENT_AMPS: d.get("grid_l1_current"),
                StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
                StandardDataKeys.ENERGY_PV_DAILY_KWH: d.get("daily_pv_energy"),
                StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: d.get("total_pv_energy"),
            }
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Sungrow read failed: %s", e)
            self.disconnect()
            return None
