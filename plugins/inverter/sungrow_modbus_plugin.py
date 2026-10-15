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
- Sungrow SH RS and SH RT hybrids
- Sungrow SG string inverters that share the 5000 input block

Protocol Reference: Sungrow Modbus (community / Home Assistant aligned)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from plugins.plugin_interface import StandardDataKeys, derive_battery_charge_state
from plugins.inverter.modbus_inverter_base import ModbusInverterPluginBase
from plugins.inverter.sungrow_modbus_constants import (
    SUNGROW_PV,
    SUNGROW_PV_START,
    SUNGROW_PV_COUNT,
    SUNGROW_HYBRID,
    SUNGROW_HYBRID_START,
    SUNGROW_HYBRID_COUNT,
    SUNGROW_BATT_POWER,
    SUNGROW_BATT_POWER_START,
    SUNGROW_BATT_POWER_COUNT,
    SUNGROW_BATT_CURRENT,
    SUNGROW_BATT_CURRENT_START,
    SUNGROW_BATT_CURRENT_COUNT,
)

if TYPE_CHECKING:
    from core.app_state import AppState


class SungrowModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "sungrow_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["SH RS", "SH RT", "SG"],
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

    def _read_either(self, start: int, count: int) -> Optional[list]:
        regs = self._read_input_block(start, count)
        if not regs:
            regs = self._read_holding_block(start, count)
        return regs

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            regs = self._read_either(SUNGROW_PV_START, SUNGROW_PV_COUNT)
            if not regs:
                self.last_error_message = "Failed to read Sungrow PV block"
                self.disconnect()
                return None
            d = self._decode_block(regs, SUNGROW_PV, SUNGROW_PV_START)

            bat: Dict[str, Any] = {}
            bregs = self._read_either(SUNGROW_HYBRID_START, SUNGROW_HYBRID_COUNT)
            if bregs:
                bat = self._decode_block(bregs, SUNGROW_HYBRID, SUNGROW_HYBRID_START)

            pregs = self._read_either(SUNGROW_BATT_POWER_START, SUNGROW_BATT_POWER_COUNT)
            if pregs:
                bat.update(self._decode_block(pregs, SUNGROW_BATT_POWER, SUNGROW_BATT_POWER_START))
            cregs = self._read_either(SUNGROW_BATT_CURRENT_START, SUNGROW_BATT_CURRENT_COUNT)
            if cregs:
                bat.update(self._decode_block(cregs, SUNGROW_BATT_CURRENT, SUNGROW_BATT_CURRENT_START))

            batt_p = bat.get("battery_power", bat.get("battery_power_legacy"))
            batt_i = bat.get("battery_current", bat.get("battery_current_legacy"))
            load = bat.get("load_power", bat.get("ac_power"))
            frequency = bat.get("grid_frequency", d.get("grid_frequency_string"))
            status = self._battery_status_from_power(batt_p)

            return {
                StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: "Normal",
                StandardDataKeys.BATTERY_STATUS_TEXT: status,
                StandardDataKeys.BATTERY_CHARGE_STATE: derive_battery_charge_state(batt_p, status),
                StandardDataKeys.AC_POWER_WATTS: bat.get("ac_power"),
                StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: d.get("pv_total_power"),
                StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: bat.get("grid_power"),
                StandardDataKeys.LOAD_TOTAL_POWER_WATTS: load,
                StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
                StandardDataKeys.BATTERY_CURRENT_AMPS: batt_i,
                StandardDataKeys.BATTERY_VOLTAGE_VOLTS: bat.get("battery_voltage"),
                StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: bat.get("battery_soc"),
                StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: bat.get("battery_soh"),
                StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: bat.get("battery_temp"),
                StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_l1_voltage"),
                StandardDataKeys.GRID_L1_CURRENT_AMPS: bat.get("grid_l1_current"),
                StandardDataKeys.GRID_FREQUENCY_HZ: frequency,
                StandardDataKeys.ENERGY_PV_DAILY_KWH: d.get("daily_pv_energy"),
                StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: d.get("total_pv_energy"),
            }
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Sungrow read failed: %s", e)
            self.disconnect()
            return None
