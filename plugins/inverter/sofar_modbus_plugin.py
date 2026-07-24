# plugins/inverter/sofar_modbus_plugin.py
"""
Sofar Modbus Inverter Plugin

This plugin communicates with Sofar HYD/G3/ME hybrid inverters using Modbus TCP
or Modbus RTU (local only). It polls dynamic and energy register blocks aligned
with community sofar2mqtt mappings.

Features:
- Dual connection support (Modbus TCP and Serial RTU)
- Shared ModbusInverterPluginBase connection and block reads
- Dynamic PV/battery/grid block plus energy counters
- Configurable series hint (auto / HYD / G3)

Supported Models:
- Sofar HYD hybrid series
- Sofar G3 / ME compatible hybrids

Protocol Reference: Sofar Modbus (community sofar2mqtt aligned)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from plugins.plugin_interface import StandardDataKeys
from plugins.inverter.modbus_inverter_base import ModbusInverterPluginBase
from plugins.inverter.sofar_modbus_constants import (
    SOFAR_DYNAMIC,
    SOFAR_DYNAMIC_START,
    SOFAR_DYNAMIC_COUNT,
    SOFAR_ENERGY,
    SOFAR_ENERGY_START,
    SOFAR_ENERGY_COUNT,
)

if TYPE_CHECKING:
    from core.app_state import AppState


class SofarModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "sofar_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["HYD", "G3", "ME"],
        "status": "testing",
        "api_version": 1,
    }
    manufacturer_name = "Sofar"
    default_baud = 9600

    def __init__(self, instance_name, plugin_specific_config, main_logger, app_state=None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.sofar_series = (plugin_specific_config.get("sofar_series") or "auto").strip().lower()

    @property
    def name(self) -> str:
        return "sofar_modbus"

    @property
    def pretty_name(self) -> str:
        return "Sofar Modbus"

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        params = ModbusInverterPluginBase.get_configurable_params()
        params.append({
            "name": "sofar_series",
            "type": "select",
            "options": ["auto", "hyd", "g3"],
            "default": "auto",
        })
        return params

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        data = self._static_shell(model=f"Sofar-{self.sofar_series.upper()}")
        self.last_known_static_data = data
        return data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            regs = self._read_holding_block(SOFAR_DYNAMIC_START, SOFAR_DYNAMIC_COUNT)
            if not regs:
                self.last_error_message = "Failed to read Sofar dynamic block"
                self.disconnect()
                return None
            d = self._decode_block(regs, SOFAR_DYNAMIC, SOFAR_DYNAMIC_START)
            energy = {}
            eregs = self._read_holding_block(SOFAR_ENERGY_START, SOFAR_ENERGY_COUNT)
            if eregs:
                energy = self._decode_block(eregs, SOFAR_ENERGY, SOFAR_ENERGY_START)

            pv = (d.get("pv1_power") or 0) + (d.get("pv2_power") or 0)
            batt_v = d.get("battery_voltage")
            batt_i = d.get("battery_current")
            batt_p = (float(batt_v) * float(batt_i)) if batt_v is not None and batt_i is not None else None

            return {
                StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: "Normal",
                StandardDataKeys.BATTERY_STATUS_TEXT: self._battery_status_from_power(batt_p),
                StandardDataKeys.AC_POWER_WATTS: d.get("ac_power"),
                StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv,
                StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
                StandardDataKeys.BATTERY_CURRENT_AMPS: batt_i,
                StandardDataKeys.BATTERY_VOLTAGE_VOLTS: batt_v,
                StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: d.get("battery_soc"),
                StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: d.get("battery_temp"),
                StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: d.get("inverter_temp"),
                StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
                StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: d.get("pv1_voltage"),
                StandardDataKeys.PV_MPPT1_CURRENT_AMPS: d.get("pv1_current"),
                StandardDataKeys.PV_MPPT1_POWER_WATTS: d.get("pv1_power"),
                StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: d.get("pv2_voltage"),
                StandardDataKeys.PV_MPPT2_CURRENT_AMPS: d.get("pv2_current"),
                StandardDataKeys.PV_MPPT2_POWER_WATTS: d.get("pv2_power"),
                StandardDataKeys.ENERGY_PV_DAILY_KWH: energy.get("pv_daily_energy"),
                StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: energy.get("pv_total_energy"),
            }
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Sofar read failed: %s", e)
            self.disconnect()
            return None
