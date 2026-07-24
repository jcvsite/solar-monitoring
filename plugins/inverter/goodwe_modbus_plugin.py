# plugins/inverter/goodwe_modbus_plugin.py
"""
GoodWe Modbus Inverter Plugin

This plugin communicates with GoodWe EH/ET/ES hybrid inverters using Modbus TCP
or Modbus RTU (local only). It reads work mode, PV, grid, load, and battery
metrics via a community-aligned holding-register map.

Features:
- Dual connection support (Modbus TCP and Serial RTU)
- Shared ModbusInverterPluginBase connection and block reads
- ET-family register block with optional EH map selection
- Real-time PV, AC, load, and battery SOC/SOH monitoring
- Work-mode interpretation helpers

Supported Models:
- GoodWe EH series (hybrid)
- GoodWe ET series (hybrid)
- GoodWe ES series (compatible map variants)

Protocol Reference: GoodWe Modbus (community / goodwe lib aligned)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from plugins.plugin_interface import StandardDataKeys
from plugins.inverter.modbus_inverter_base import ModbusInverterPluginBase, UNKNOWN
from plugins.inverter.goodwe_modbus_constants import (
    GOODWE_ET_START,
    GOODWE_ET_COUNT,
    GOODWE_ET_DYNAMIC,
    GOODWE_WORK_MODES,
)

if TYPE_CHECKING:
    from core.app_state import AppState


class GoodweModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "goodwe_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["EH", "ET", "ES"],
        "status": "testing",
        "api_version": 1,
    }
    manufacturer_name = "GoodWe"
    default_baud = 9600

    def __init__(self, instance_name, plugin_specific_config, main_logger, app_state=None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.goodwe_map = (plugin_specific_config.get("goodwe_map") or "auto").strip().lower()

    @property
    def name(self) -> str:
        return "goodwe_modbus"

    @property
    def pretty_name(self) -> str:
        return "GoodWe Modbus"

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        params = ModbusInverterPluginBase.get_configurable_params()
        params.append({
            "name": "goodwe_map",
            "type": "select",
            "options": ["auto", "et", "eh"],
            "default": "auto",
        })
        return params

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        data = self._static_shell(model=f"GoodWe-{self.goodwe_map.upper()}")
        self.last_known_static_data = data
        return data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            regs = self._read_holding_block(GOODWE_ET_START, GOODWE_ET_COUNT)
            if not regs:
                self.last_error_message = "Failed to read GoodWe holding block"
                self.disconnect()
                return None
            d = self._decode_block(regs, GOODWE_ET_DYNAMIC, GOODWE_ET_START)
            pv = (d.get("pv1_power") or 0) + (d.get("pv2_power") or 0)
            batt_i = d.get("battery_current")
            batt_v = d.get("battery_voltage")
            # GoodWe: negative current = charging → power convention +ve discharging
            batt_p = (-float(batt_v) * float(batt_i)) if batt_v is not None and batt_i is not None else None

            mode = int(d.get("work_mode") or 0)
            return {
                StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: GOODWE_WORK_MODES.get(mode, f"Mode {mode}"),
                StandardDataKeys.BATTERY_STATUS_TEXT: self._battery_status_from_power(batt_p),
                StandardDataKeys.AC_POWER_WATTS: d.get("ac_power"),
                StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv,
                StandardDataKeys.LOAD_TOTAL_POWER_WATTS: d.get("load_power"),
                StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
                StandardDataKeys.BATTERY_CURRENT_AMPS: batt_i,
                StandardDataKeys.BATTERY_VOLTAGE_VOLTS: batt_v,
                StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: d.get("battery_soc"),
                StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: d.get("battery_temp"),
                StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: d.get("inverter_temp"),
                StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_l1_voltage"),
                StandardDataKeys.GRID_L1_CURRENT_AMPS: d.get("grid_l1_current"),
                StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
                StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: d.get("pv1_voltage"),
                StandardDataKeys.PV_MPPT1_CURRENT_AMPS: d.get("pv1_current"),
                StandardDataKeys.PV_MPPT1_POWER_WATTS: d.get("pv1_power"),
                StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: d.get("pv2_voltage"),
                StandardDataKeys.PV_MPPT2_CURRENT_AMPS: d.get("pv2_current"),
                StandardDataKeys.PV_MPPT2_POWER_WATTS: d.get("pv2_power"),
                StandardDataKeys.ENERGY_PV_DAILY_KWH: d.get("pv_daily_energy"),
                StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: d.get("pv_total_energy"),
            }
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("GoodWe read failed: %s", e)
            self.disconnect()
            return None
