# plugins/inverter/felicity_modbus_plugin.py
"""
Felicity Solar Modbus Inverter Plugin

This plugin communicates with Felicity Solar T-REX / hybrid inverters using
Modbus TCP or Modbus RTU (local only). Register layout is Growatt-like and
marked for testing pending field validation.

Features:
- Dual connection support (Modbus TCP and Serial RTU)
- Shared ModbusInverterPluginBase connection and block reads
- Dynamic PV/grid/load block plus optional storage block
- Temperature and status register decode

Supported Models:
- Felicity Solar T-REX series
- Felicity LI / hybrid variants with Growatt-like maps

Protocol Reference: Felicity Solar Modbus (Growatt-like holding registers; testing)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from plugins.plugin_interface import StandardDataKeys
from plugins.inverter.modbus_inverter_base import ModbusInverterPluginBase
from plugins.inverter.felicity_modbus_constants import (
    FELICITY_DYNAMIC,
    FELICITY_START,
    FELICITY_COUNT,
    FELICITY_STORAGE,
    FELICITY_STORAGE_START,
    FELICITY_STORAGE_COUNT,
)

if TYPE_CHECKING:
    from core.app_state import AppState


class FelicityModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "felicity_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["T-REX", "LI", "Hybrid"],
        "status": "testing",
        "api_version": 1,
    }
    manufacturer_name = "Felicity"
    default_baud = 9600

    @property
    def name(self) -> str:
        return "felicity_modbus"

    @property
    def pretty_name(self) -> str:
        return "Felicity Modbus"

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        data = self._static_shell(model="Felicity-Hybrid")
        self.last_known_static_data = data
        return data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            regs = self._read_holding_block(FELICITY_START, FELICITY_COUNT)
            if not regs:
                self.last_error_message = "Failed to read Felicity block"
                self.disconnect()
                return None
            d = self._decode_block(regs, FELICITY_DYNAMIC, FELICITY_START)
            storage = {}
            sregs = self._read_holding_block(FELICITY_STORAGE_START, FELICITY_STORAGE_COUNT)
            if sregs:
                storage = self._decode_block(sregs, FELICITY_STORAGE, FELICITY_STORAGE_START)

            pv = (d.get("pv1_power") or 0) + (d.get("pv2_power") or 0)
            batt_p = storage.get("battery_power")
            batt_v = storage.get("battery_voltage") or d.get("battery_voltage")
            batt_soc = storage.get("battery_soc") or d.get("battery_soc")

            return {
                StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: "Normal",
                StandardDataKeys.BATTERY_STATUS_TEXT: self._battery_status_from_power(batt_p),
                StandardDataKeys.AC_POWER_WATTS: d.get("ac_power"),
                StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv,
                StandardDataKeys.LOAD_TOTAL_POWER_WATTS: d.get("load_power"),
                StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
                StandardDataKeys.BATTERY_VOLTAGE_VOLTS: batt_v,
                StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: batt_soc,
                StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: storage.get("battery_temp"),
                StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: d.get("inverter_temp"),
                StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_l1_voltage"),
                StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
                StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: d.get("pv1_voltage"),
                StandardDataKeys.PV_MPPT1_CURRENT_AMPS: d.get("pv1_current"),
                StandardDataKeys.PV_MPPT1_POWER_WATTS: d.get("pv1_power"),
                StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: d.get("pv2_voltage"),
                StandardDataKeys.PV_MPPT2_CURRENT_AMPS: d.get("pv2_current"),
                StandardDataKeys.PV_MPPT2_POWER_WATTS: d.get("pv2_power"),
            }
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Felicity read failed: %s", e)
            self.disconnect()
            return None
