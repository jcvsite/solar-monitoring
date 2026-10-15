# plugins/inverter/solax_modbus_plugin.py
"""
SolaX hybrid Modbus plugin (read-only).

Covers the Gen2–Gen4 input-register block used by X1/X3 hybrid inverters:
PV, battery, meter power, and energy counters. 32-bit values are little-endian
words, matching the SolaX Modbus layout.

Battery power is charge-positive on the wire and is flipped to the framework
convention (positive = discharge). Meter power is import-positive on the wire
and is flipped so positive grid power means export.

Register addresses follow the community map in wills106/homeassistant-solax-modbus
(Apache-2.0). This file is a monitoring subset, not a copy of that plugin.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from plugins.plugin_interface import StandardDataKeys, derive_battery_charge_state
from plugins.inverter.modbus_inverter_base import ModbusInverterPluginBase

SOLAX_INPUT_START = 0x0000
SOLAX_INPUT_COUNT = 84

SOLAX_INPUT: Dict[str, Dict[str, Any]] = {
    "inverter_power": {"addr": 0x0002, "type": "int16"},
    "pv1_voltage": {"addr": 0x0003, "type": "uint16", "scale": 0.1},
    "pv2_voltage": {"addr": 0x0004, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 0x0005, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 0x0006, "type": "uint16", "scale": 0.1},
    "grid_frequency": {"addr": 0x0007, "type": "uint16", "scale": 0.01},
    "inverter_temp": {"addr": 0x0008, "type": "int16"},
    "run_mode": {"addr": 0x0009, "type": "uint16"},
    "pv1_power": {"addr": 0x000A, "type": "uint16"},
    "pv2_power": {"addr": 0x000B, "type": "uint16"},
    "battery_voltage": {"addr": 0x0014, "type": "int16", "scale": 0.1},
    "battery_current": {"addr": 0x0015, "type": "int16", "scale": 0.1},
    "battery_power": {"addr": 0x0016, "type": "int16"},
    "battery_temp": {"addr": 0x0018, "type": "int16"},
    "battery_soc": {"addr": 0x001C, "type": "uint16"},
    "measured_power": {"addr": 0x0046, "type": "int32_le"},
    "grid_export_total": {"addr": 0x0048, "type": "uint32_le", "scale": 0.01},
    "grid_import_total": {"addr": 0x004A, "type": "uint32_le", "scale": 0.01},
    "eps_power": {"addr": 0x004E, "type": "uint16"},
    "pv_daily_energy": {"addr": 0x0050, "type": "uint16", "scale": 0.1},
}

SOLAX_RUN_MODES = {
    0: "Waiting",
    1: "Checking",
    2: "Normal",
    3: "Fault",
    4: "Permanent Fault",
    5: "Update",
    6: "Off-Grid Waiting",
    7: "Off-Grid",
    8: "Self Test",
    9: "Idle",
    10: "Standby",
}


def standardize_solax(decoded: Dict[str, Any], *, generation: str = "gen3") -> Dict[str, Any]:
    """Map a decoded SolaX input block onto StandardDataKeys."""
    batt_v = decoded.get("battery_voltage")
    batt_i = decoded.get("battery_current")
    if generation == "gen2":
        batt_v = float(batt_v) / 10.0 if batt_v is not None else None
        batt_i = float(batt_i) / 10.0 if batt_i is not None else None
    batt_p = decoded.get("battery_power")
    if batt_p is not None:
        batt_p = -float(batt_p)
    if batt_i is not None:
        batt_i = -float(batt_i)
    measured = decoded.get("measured_power")
    grid = -float(measured) if measured is not None else None
    inverter = decoded.get("inverter_power")
    house = None
    if inverter is not None and measured is not None:
        house = float(inverter) - float(measured)
    pv = (decoded.get("pv1_power") or 0) + (decoded.get("pv2_power") or 0)
    code = decoded.get("run_mode")
    mode = SOLAX_RUN_MODES.get(int(code), "Unknown") if code is not None else "Unknown"
    batt_status = "Idle"
    if batt_p is not None and batt_p > 10:
        batt_status = "Discharging"
    elif batt_p is not None and batt_p < -10:
        batt_status = "Charging"
    return {
        StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: mode,
        StandardDataKeys.BATTERY_STATUS_TEXT: batt_status,
        StandardDataKeys.BATTERY_CHARGE_STATE: derive_battery_charge_state(batt_p, batt_status),
        StandardDataKeys.AC_POWER_WATTS: inverter,
        StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv,
        StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: decoded.get("pv1_voltage"),
        StandardDataKeys.PV_MPPT1_CURRENT_AMPS: decoded.get("pv1_current"),
        StandardDataKeys.PV_MPPT1_POWER_WATTS: decoded.get("pv1_power"),
        StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: decoded.get("pv2_voltage"),
        StandardDataKeys.PV_MPPT2_CURRENT_AMPS: decoded.get("pv2_current"),
        StandardDataKeys.PV_MPPT2_POWER_WATTS: decoded.get("pv2_power"),
        StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
        StandardDataKeys.BATTERY_CURRENT_AMPS: batt_i,
        StandardDataKeys.BATTERY_VOLTAGE_VOLTS: batt_v,
        StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: decoded.get("battery_soc"),
        StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: decoded.get("battery_temp"),
        StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: decoded.get("inverter_temp"),
        StandardDataKeys.GRID_FREQUENCY_HZ: decoded.get("grid_frequency"),
        StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: grid,
        StandardDataKeys.LOAD_TOTAL_POWER_WATTS: house,
        StandardDataKeys.EPS_TOTAL_ACTIVE_POWER_WATTS: decoded.get("eps_power"),
        StandardDataKeys.ENERGY_PV_DAILY_KWH: decoded.get("pv_daily_energy"),
        StandardDataKeys.ENERGY_GRID_TOTAL_IMPORT_KWH: decoded.get("grid_import_total"),
        StandardDataKeys.ENERGY_GRID_TOTAL_EXPORT_KWH: decoded.get("grid_export_total"),
    }


class SolaxModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "solax_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["Gen2", "Gen3", "Gen4", "X1", "X3"],
        "status": "testing",
        "api_version": 1,
    }
    manufacturer_name = "SolaX"

    def __init__(self, instance_name, plugin_specific_config, main_logger, app_state=None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        generation = str(plugin_specific_config.get("solax_generation", "gen3")).split(";")[0].strip().lower()
        self.solax_generation = generation if generation in ("gen2", "gen3") else "gen3"

    @property
    def name(self) -> str:
        return "solax_modbus"

    @property
    def pretty_name(self) -> str:
        return "SolaX Modbus"

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        params = ModbusInverterPluginBase.get_configurable_params()
        params.append({
            "name": "solax_generation",
            "type": "select",
            "options": ["gen3", "gen2"],
            "default": "gen3",
        })
        return params

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        data = self._static_shell(model=f"SolaX-{self.solax_generation}")
        self.last_known_static_data = data
        return data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            regs = self._read_input_block(SOLAX_INPUT_START, SOLAX_INPUT_COUNT)
            if not regs:
                self.last_error_message = "Failed to read SolaX input block"
                self.disconnect()
                return None
            decoded = self._decode_block(regs, SOLAX_INPUT, SOLAX_INPUT_START)
            return standardize_solax(decoded, generation=self.solax_generation)
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("SolaX read failed: %s", e)
            self.disconnect()
            return None
