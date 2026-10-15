# plugins/inverter/alphaess_modbus_plugin.py
"""
AlphaESS hybrid Modbus plugin (read-only).

Holding-register subset: grid voltage and frequency, battery SOC, two PV
strings, and EPS power. Battery power is voltage times current, with the
register current sign kept as reported.

Register addresses follow wills106/homeassistant-solax-modbus plugin_alphaess.py
(Apache-2.0). This file is a monitoring subset.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from plugins.plugin_interface import StandardDataKeys, derive_battery_charge_state
from plugins.inverter.modbus_inverter_base import ModbusInverterPluginBase

ALPHAESS_GRID_START = 0x0014
ALPHAESS_GRID_COUNT = 16
ALPHAESS_GRID: Dict[str, Dict[str, Any]] = {
    "grid_voltage": {"addr": 0x0014, "type": "uint16"},
    "grid_current": {"addr": 0x0017, "type": "uint16", "scale": 0.1},
    "grid_frequency": {"addr": 0x001A, "type": "uint16", "scale": 0.01},
    "ac_power": {"addr": 0x0021, "type": "int32"},
}

ALPHAESS_BATT_START = 0x0100
ALPHAESS_BATT_COUNT = 0x0124 - 0x0100 + 2
ALPHAESS_BATT: Dict[str, Dict[str, Any]] = {
    "battery_voltage": {"addr": 0x0100, "type": "int16", "scale": 0.1},
    "battery_current": {"addr": 0x0101, "type": "int16", "scale": 0.1},
    "battery_soc": {"addr": 0x0102, "type": "uint16"},
    "battery_charge_total": {"addr": 0x0120, "type": "uint32", "scale": 0.1},
    "battery_discharge_total": {"addr": 0x0122, "type": "uint32", "scale": 0.1},
}

ALPHAESS_EPS_START = 0x041A
ALPHAESS_EPS_COUNT = 2
ALPHAESS_EPS: Dict[str, Dict[str, Any]] = {
    "eps_power": {"addr": 0x041A, "type": "int32"},
}

ALPHAESS_PV_START = 0x041D
ALPHAESS_PV_COUNT = 0x0435 - 0x041D + 1
ALPHAESS_PV: Dict[str, Dict[str, Any]] = {
    "pv1_voltage": {"addr": 0x041D, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 0x041E, "type": "uint16", "scale": 0.1},
    "pv1_power": {"addr": 0x041F, "type": "int32"},
    "pv2_voltage": {"addr": 0x0421, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 0x0422, "type": "uint16", "scale": 0.1},
    "pv2_power": {"addr": 0x0423, "type": "int32"},
    "inverter_temp": {"addr": 0x0435, "type": "int16", "scale": 0.1},
}


def standardize_alphaess(decoded: Dict[str, Any]) -> Dict[str, Any]:
    voltage = decoded.get("battery_voltage")
    current = decoded.get("battery_current")
    batt_p = None
    if voltage is not None and current is not None:
        batt_p = float(voltage) * float(current)
    pv = (decoded.get("pv1_power") or 0) + (decoded.get("pv2_power") or 0)
    batt_status = "Idle"
    if batt_p is not None and batt_p > 10:
        batt_status = "Discharging"
    elif batt_p is not None and batt_p < -10:
        batt_status = "Charging"
    return {
        StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: "Online",
        StandardDataKeys.BATTERY_STATUS_TEXT: batt_status,
        StandardDataKeys.BATTERY_CHARGE_STATE: derive_battery_charge_state(batt_p, batt_status),
        StandardDataKeys.AC_POWER_WATTS: decoded.get("ac_power"),
        StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv,
        StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: decoded.get("pv1_voltage"),
        StandardDataKeys.PV_MPPT1_CURRENT_AMPS: decoded.get("pv1_current"),
        StandardDataKeys.PV_MPPT1_POWER_WATTS: decoded.get("pv1_power"),
        StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: decoded.get("pv2_voltage"),
        StandardDataKeys.PV_MPPT2_CURRENT_AMPS: decoded.get("pv2_current"),
        StandardDataKeys.PV_MPPT2_POWER_WATTS: decoded.get("pv2_power"),
        StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
        StandardDataKeys.BATTERY_CURRENT_AMPS: current,
        StandardDataKeys.BATTERY_VOLTAGE_VOLTS: voltage,
        StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: decoded.get("battery_soc"),
        StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: decoded.get("inverter_temp"),
        StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: decoded.get("grid_voltage"),
        StandardDataKeys.GRID_L1_CURRENT_AMPS: decoded.get("grid_current"),
        StandardDataKeys.GRID_FREQUENCY_HZ: decoded.get("grid_frequency"),
        StandardDataKeys.EPS_TOTAL_ACTIVE_POWER_WATTS: decoded.get("eps_power"),
        StandardDataKeys.ENERGY_BATTERY_TOTAL_CHARGE_KWH: decoded.get("battery_charge_total"),
        StandardDataKeys.ENERGY_BATTERY_TOTAL_DISCHARGE_KWH: decoded.get("battery_discharge_total"),
    }


class AlphaEssModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "alphaess_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["Smile", "hybrid"],
        "status": "testing",
        "api_version": 1,
    }
    manufacturer_name = "AlphaESS"

    @property
    def name(self) -> str:
        return "alphaess_modbus"

    @property
    def pretty_name(self) -> str:
        return "AlphaESS Modbus"

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        data = self._static_shell(model="AlphaESS")
        self.last_known_static_data = data
        return data

    def _merge(self, start: int, count: int, register_map: Dict[str, Dict[str, Any]], into: Dict[str, Any]) -> bool:
        regs = self._read_holding_block(start, count)
        if not regs:
            return False
        into.update(self._decode_block(regs, register_map, start))
        return True

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            decoded: Dict[str, Any] = {}
            if not self._merge(ALPHAESS_GRID_START, ALPHAESS_GRID_COUNT, ALPHAESS_GRID, decoded):
                self.last_error_message = "Failed to read AlphaESS grid block"
                self.disconnect()
                return None
            self._merge(ALPHAESS_BATT_START, ALPHAESS_BATT_COUNT, ALPHAESS_BATT, decoded)
            self._merge(ALPHAESS_EPS_START, ALPHAESS_EPS_COUNT, ALPHAESS_EPS, decoded)
            self._merge(ALPHAESS_PV_START, ALPHAESS_PV_COUNT, ALPHAESS_PV, decoded)
            return standardize_alphaess(decoded)
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("AlphaESS read failed: %s", e)
            self.disconnect()
            return None
