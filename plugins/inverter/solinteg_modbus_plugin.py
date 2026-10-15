# plugins/inverter/solinteg_modbus_plugin.py
"""
Solinteg hybrid Modbus plugin (read-only).

Holding registers for PV, meter power, battery, and daily energy. Meter power
is export-positive (house load is inverter output minus meter power). Battery
power is discharge-positive.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from plugins.plugin_interface import StandardDataKeys, derive_battery_charge_state
from plugins.inverter.modbus_inverter_base import ModbusInverterPluginBase

SOLINTEG_STATUS_START = 10105
SOLINTEG_STATUS_COUNT = 1
SOLINTEG_STATUS: Dict[str, Dict[str, Any]] = {
    "run_mode": {"addr": 10105, "type": "uint16"},
}

SOLINTEG_METER_START = 11000
SOLINTEG_METER_COUNT = 76
SOLINTEG_METER: Dict[str, Dict[str, Any]] = {
    "grid_power": {"addr": 11000, "type": "int32"},
    "grid_export_total": {"addr": 11002, "type": "uint32", "scale": 0.01},
    "grid_import_total": {"addr": 11004, "type": "uint32", "scale": 0.01},
    "grid_frequency": {"addr": 11015, "type": "uint16", "scale": 0.01},
    "ac_power": {"addr": 11016, "type": "int32"},
    "pv_daily_energy": {"addr": 11018, "type": "uint32", "scale": 0.1},
    "pv_power_total": {"addr": 11028, "type": "uint32"},
    "inverter_temp": {"addr": 11032, "type": "int16", "scale": 0.1},
    "pv1_voltage": {"addr": 11038, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 11039, "type": "uint16", "scale": 0.1},
    "pv2_voltage": {"addr": 11040, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 11041, "type": "uint16", "scale": 0.1},
    "pv1_power": {"addr": 11062, "type": "uint32"},
    "pv2_power": {"addr": 11064, "type": "uint32"},
}

SOLINTEG_BATT_START = 30254
SOLINTEG_BATT_COUNT = 6
SOLINTEG_BATT: Dict[str, Dict[str, Any]] = {
    "battery_voltage": {"addr": 30254, "type": "uint16", "scale": 0.1},
    "battery_current": {"addr": 30255, "type": "int16", "scale": 0.1},
    "battery_power": {"addr": 30258, "type": "int32"},
}

SOLINTEG_SOC_START = 33000
SOLINTEG_SOC_COUNT = 4
SOLINTEG_SOC: Dict[str, Dict[str, Any]] = {
    "battery_soc": {"addr": 33000, "type": "uint16", "scale": 0.01},
    "battery_soh": {"addr": 33001, "type": "uint16", "scale": 0.01},
    "battery_temp": {"addr": 33003, "type": "int16", "scale": 0.1},
}

SOLINTEG_RUN_MODES = {
    0: "Waiting",
    1: "Self checking",
    2: "On Grid",
    3: "Fault",
    4: "Firmware upgrade",
    5: "Off Grid",
}


def standardize_solinteg(decoded: Dict[str, Any]) -> Dict[str, Any]:
    batt_p = decoded.get("battery_power")
    if batt_p is not None:
        batt_p = float(batt_p)
    ac = decoded.get("ac_power")
    grid = decoded.get("grid_power")
    house = None
    if ac is not None and grid is not None:
        house = float(ac) - float(grid)
    pv = decoded.get("pv_power_total")
    if not pv:
        pv = (decoded.get("pv1_power") or 0) + (decoded.get("pv2_power") or 0)
    code = decoded.get("run_mode")
    mode = SOLINTEG_RUN_MODES.get(int(code), "Unknown") if code is not None else "Unknown"
    batt_status = "Idle"
    if batt_p is not None and batt_p > 10:
        batt_status = "Discharging"
    elif batt_p is not None and batt_p < -10:
        batt_status = "Charging"
    return {
        StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: mode,
        StandardDataKeys.BATTERY_STATUS_TEXT: batt_status,
        StandardDataKeys.BATTERY_CHARGE_STATE: derive_battery_charge_state(batt_p, batt_status),
        StandardDataKeys.AC_POWER_WATTS: ac,
        StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv,
        StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: decoded.get("pv1_voltage"),
        StandardDataKeys.PV_MPPT1_CURRENT_AMPS: decoded.get("pv1_current"),
        StandardDataKeys.PV_MPPT1_POWER_WATTS: decoded.get("pv1_power"),
        StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: decoded.get("pv2_voltage"),
        StandardDataKeys.PV_MPPT2_CURRENT_AMPS: decoded.get("pv2_current"),
        StandardDataKeys.PV_MPPT2_POWER_WATTS: decoded.get("pv2_power"),
        StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
        StandardDataKeys.BATTERY_CURRENT_AMPS: decoded.get("battery_current"),
        StandardDataKeys.BATTERY_VOLTAGE_VOLTS: decoded.get("battery_voltage"),
        StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: decoded.get("battery_soc"),
        StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: decoded.get("battery_soh"),
        StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: decoded.get("battery_temp"),
        StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: decoded.get("inverter_temp"),
        StandardDataKeys.GRID_FREQUENCY_HZ: decoded.get("grid_frequency"),
        StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: grid,
        StandardDataKeys.LOAD_TOTAL_POWER_WATTS: house,
        StandardDataKeys.ENERGY_PV_DAILY_KWH: decoded.get("pv_daily_energy"),
        StandardDataKeys.ENERGY_GRID_TOTAL_IMPORT_KWH: decoded.get("grid_import_total"),
        StandardDataKeys.ENERGY_GRID_TOTAL_EXPORT_KWH: decoded.get("grid_export_total"),
    }


class SolintegModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "solinteg_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["MHS", "MHT"],
        "status": "testing",
        "api_version": 1,
    }
    manufacturer_name = "Solinteg"

    @property
    def name(self) -> str:
        return "solinteg_modbus"

    @property
    def pretty_name(self) -> str:
        return "Solinteg Modbus"

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        data = self._static_shell(model="Solinteg")
        data[StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC] = 1
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
            if not self._merge(SOLINTEG_METER_START, SOLINTEG_METER_COUNT, SOLINTEG_METER, decoded):
                self.last_error_message = "Failed to read Solinteg meter block"
                self.disconnect()
                return None
            self._merge(SOLINTEG_STATUS_START, SOLINTEG_STATUS_COUNT, SOLINTEG_STATUS, decoded)
            self._merge(SOLINTEG_BATT_START, SOLINTEG_BATT_COUNT, SOLINTEG_BATT, decoded)
            self._merge(SOLINTEG_SOC_START, SOLINTEG_SOC_COUNT, SOLINTEG_SOC, decoded)
            return standardize_solinteg(decoded)
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Solinteg read failed: %s", e)
            self.disconnect()
            return None
