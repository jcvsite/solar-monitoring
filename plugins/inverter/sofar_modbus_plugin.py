# plugins/inverter/sofar_modbus_plugin.py
"""
Sofar Modbus Inverter Plugin

Reads Sofar hybrid inverters over Modbus TCP or RTU.

Series:
- hyd / g3 / ep: HYD KTL and G3 holding-register map (PV at 0x0584, battery at 0x0604)
- es: older HYD ES hybrid block at 0x0200
- auto: use the HYD KTL map when 0x0584 answers, otherwise the ES block

Battery power registers are charge-positive and are flipped to the framework
convention (positive = discharge). Grid power is export-positive.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from plugins.plugin_interface import StandardDataKeys, derive_battery_charge_state, parse_config_str
from plugins.inverter.modbus_inverter_base import UNKNOWN, ModbusInverterPluginBase
from plugins.inverter.sofar_modbus_constants import (
    SOFAR_ES,
    SOFAR_ES_COUNT,
    SOFAR_ES_PV,
    SOFAR_ES_PV_COUNT,
    SOFAR_ES_PV_START,
    SOFAR_ES_RUN_MODES,
    SOFAR_ES_START,
    SOFAR_HYD_BATT,
    SOFAR_HYD_BATT_COUNT,
    SOFAR_HYD_BATT_START,
    SOFAR_HYD_BATT_TOTAL,
    SOFAR_HYD_BATT_TOTAL_COUNT,
    SOFAR_HYD_BATT_TOTAL_START,
    SOFAR_HYD_ENERGY,
    SOFAR_HYD_ENERGY_COUNT,
    SOFAR_HYD_ENERGY_START,
    SOFAR_HYD_EPS,
    SOFAR_HYD_EPS_COUNT,
    SOFAR_HYD_EPS_START,
    SOFAR_HYD_GRID,
    SOFAR_HYD_GRID_COUNT,
    SOFAR_HYD_GRID_START,
    SOFAR_HYD_PV,
    SOFAR_HYD_PV_COUNT,
    SOFAR_HYD_PV_START,
    SOFAR_HYD_SERIAL_COUNT,
    SOFAR_HYD_SERIAL_START,
    SOFAR_HYD_STATE,
    SOFAR_HYD_STATE_COUNT,
    SOFAR_HYD_STATE_START,
    SOFAR_HYD_SYSTEM_STATES,
    SOFAR_HYD_TEMP,
    SOFAR_HYD_TEMP_COUNT,
    SOFAR_HYD_TEMP_START,
)

_ES_SERIES = {"es", "old", "hyd_es"}


def _charge_positive_to_discharge(power_w: Optional[float]) -> Optional[float]:
    if power_w is None:
        return None
    return -float(power_w)


def standardize_sofar(decoded: Dict[str, Any], *, series: str) -> Dict[str, Any]:
    """Map a decoded Sofar block onto StandardDataKeys."""
    batt_src = decoded.get("battery_power_total")
    if batt_src is None:
        batt_src = decoded.get("battery_power")
    batt_p = _charge_positive_to_discharge(batt_src)
    batt_i = decoded.get("battery_current")
    if batt_i is not None:
        batt_i = -float(batt_i)
    pv_strings = [decoded.get(k) for k in ("pv1_power", "pv2_power", "pv3_power", "pv4_power")]
    pv_sum = sum(v for v in pv_strings if isinstance(v, (int, float)))
    pv_total = decoded.get("pv_power_total")
    if not pv_total and pv_sum:
        pv_total = pv_sum
    soc = decoded.get("battery_soc_total")
    if soc is None:
        soc = decoded.get("battery_soc")
    if series == "es":
        code, modes = decoded.get("run_mode"), SOFAR_ES_RUN_MODES
    else:
        code, modes = decoded.get("system_state"), SOFAR_HYD_SYSTEM_STATES
    status = modes.get(int(code), "Unknown") if code is not None else "Unknown"
    batt_status = "Idle"
    if batt_p is not None and batt_p > 50:
        batt_status = "Discharging"
    elif batt_p is not None and batt_p < -50:
        batt_status = "Charging"
    return {
        StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: status,
        StandardDataKeys.BATTERY_STATUS_TEXT: batt_status,
        StandardDataKeys.BATTERY_CHARGE_STATE: derive_battery_charge_state(batt_p, batt_status),
        StandardDataKeys.AC_POWER_WATTS: decoded.get("ac_power"),
        StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv_total,
        StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
        StandardDataKeys.BATTERY_CURRENT_AMPS: batt_i,
        StandardDataKeys.BATTERY_VOLTAGE_VOLTS: decoded.get("battery_voltage"),
        StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: soc,
        StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: decoded.get("battery_soh_total", decoded.get("battery_soh")),
        StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: decoded.get("battery_temp"),
        StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: decoded.get("inverter_temp"),
        StandardDataKeys.GRID_FREQUENCY_HZ: decoded.get("grid_frequency"),
        StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: decoded.get("grid_l1_voltage"),
        StandardDataKeys.GRID_L2_VOLTAGE_VOLTS: decoded.get("grid_l2_voltage"),
        StandardDataKeys.GRID_L3_VOLTAGE_VOLTS: decoded.get("grid_l3_voltage"),
        StandardDataKeys.GRID_L1_POWER_WATTS: decoded.get("grid_l1_power"),
        StandardDataKeys.GRID_L2_POWER_WATTS: decoded.get("grid_l2_power"),
        StandardDataKeys.GRID_L3_POWER_WATTS: decoded.get("grid_l3_power"),
        StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: decoded.get("grid_power"),
        StandardDataKeys.LOAD_TOTAL_POWER_WATTS: decoded.get("load_power"),
        StandardDataKeys.EPS_L1_VOLTAGE_VOLTS: decoded.get("eps_voltage"),
        StandardDataKeys.EPS_TOTAL_ACTIVE_POWER_WATTS: decoded.get("eps_power"),
        StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: decoded.get("pv1_voltage"),
        StandardDataKeys.PV_MPPT1_CURRENT_AMPS: decoded.get("pv1_current"),
        StandardDataKeys.PV_MPPT1_POWER_WATTS: decoded.get("pv1_power"),
        StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: decoded.get("pv2_voltage"),
        StandardDataKeys.PV_MPPT2_CURRENT_AMPS: decoded.get("pv2_current"),
        StandardDataKeys.PV_MPPT2_POWER_WATTS: decoded.get("pv2_power"),
        StandardDataKeys.PV_MPPT3_VOLTAGE_VOLTS: decoded.get("pv3_voltage"),
        StandardDataKeys.PV_MPPT3_CURRENT_AMPS: decoded.get("pv3_current"),
        StandardDataKeys.PV_MPPT3_POWER_WATTS: decoded.get("pv3_power"),
        StandardDataKeys.PV_MPPT4_VOLTAGE_VOLTS: decoded.get("pv4_voltage"),
        StandardDataKeys.PV_MPPT4_CURRENT_AMPS: decoded.get("pv4_current"),
        StandardDataKeys.PV_MPPT4_POWER_WATTS: decoded.get("pv4_power"),
        StandardDataKeys.ENERGY_PV_DAILY_KWH: decoded.get("pv_daily_energy"),
        StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: decoded.get("pv_total_energy"),
        StandardDataKeys.ENERGY_LOAD_DAILY_KWH: decoded.get("load_daily_energy"),
        StandardDataKeys.ENERGY_LOAD_TOTAL_KWH: decoded.get("load_total_energy"),
        StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: decoded.get("grid_import_daily"),
        StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH: decoded.get("grid_export_daily"),
        StandardDataKeys.ENERGY_GRID_TOTAL_IMPORT_KWH: decoded.get("grid_import_total"),
        StandardDataKeys.ENERGY_GRID_TOTAL_EXPORT_KWH: decoded.get("grid_export_total"),
        StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: decoded.get("battery_charge_daily"),
        StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: decoded.get("battery_discharge_daily"),
        StandardDataKeys.ENERGY_BATTERY_TOTAL_CHARGE_KWH: decoded.get("battery_charge_total"),
        StandardDataKeys.ENERGY_BATTERY_TOTAL_DISCHARGE_KWH: decoded.get("battery_discharge_total"),
    }


class SofarModbusPlugin(ModbusInverterPluginBase):
    PLUGIN_META = {
        "plugin_id": "sofar_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["HYD-KTL", "G3", "HYD-ES"],
        "status": "testing",
        "api_version": 1,
    }
    manufacturer_name = "Sofar"
    default_baud = 9600

    def __init__(self, instance_name, plugin_specific_config, main_logger, app_state=None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.sofar_series = (parse_config_str(plugin_specific_config, "sofar_series", "auto") or "auto").lower()
        self._resolved_series: Optional[str] = None

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
            "options": ["auto", "hyd", "g3", "ep", "es"],
            "default": "auto",
        })
        return params

    def _series(self) -> str:
        if self.sofar_series in _ES_SERIES:
            return "es"
        if self.sofar_series not in ("auto", ""):
            return "hyd"
        if self._resolved_series:
            return self._resolved_series
        if self._read_holding_block(SOFAR_HYD_PV_START, 3):
            self._resolved_series = "hyd"
        elif self._read_holding_block(SOFAR_ES_START, 1):
            self._resolved_series = "es"
        else:
            self._resolved_series = "hyd"
        self.logger.info("Sofar '%s': series resolved to %s", self.instance_name, self._resolved_series)
        return self._resolved_series

    def _merge(self, start: int, count: int, register_map: Dict[str, Dict[str, Any]], into: Dict[str, Any]) -> bool:
        regs = self._read_holding_block(start, count)
        if not regs:
            return False
        into.update(self._decode_block(regs, register_map, start))
        return True

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        series = self._series() if self.is_connected else self.sofar_series
        serial = UNKNOWN
        if series != "es" and self.is_connected:
            regs = self._read_holding_block(SOFAR_HYD_SERIAL_START, SOFAR_HYD_SERIAL_COUNT)
            if regs:
                raw = b"".join(r.to_bytes(2, "big") for r in regs)
                serial = raw.decode("ascii", errors="ignore").replace("\x00", "").strip() or UNKNOWN
        data = self._static_shell(model=f"Sofar-{series.upper()}", serial=serial)
        data[StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC] = 3
        data[StandardDataKeys.STATIC_NUMBER_OF_MPPTS] = 2
        self.last_known_static_data = data
        return data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            decoded: Dict[str, Any] = {}
            series = self._series()
            if series == "es":
                if not self._merge(SOFAR_ES_START, SOFAR_ES_COUNT, SOFAR_ES, decoded):
                    self.last_error_message = "Failed to read Sofar ES block"
                    self.disconnect()
                    return None
                self._merge(SOFAR_ES_PV_START, SOFAR_ES_PV_COUNT, SOFAR_ES_PV, decoded)
            else:
                if not self._merge(SOFAR_HYD_GRID_START, SOFAR_HYD_GRID_COUNT, SOFAR_HYD_GRID, decoded):
                    self.last_error_message = "Failed to read Sofar HYD grid block"
                    self.disconnect()
                    return None
                self._merge(SOFAR_HYD_STATE_START, SOFAR_HYD_STATE_COUNT, SOFAR_HYD_STATE, decoded)
                self._merge(SOFAR_HYD_TEMP_START, SOFAR_HYD_TEMP_COUNT, SOFAR_HYD_TEMP, decoded)
                self._merge(SOFAR_HYD_EPS_START, SOFAR_HYD_EPS_COUNT, SOFAR_HYD_EPS, decoded)
                self._merge(SOFAR_HYD_PV_START, SOFAR_HYD_PV_COUNT, SOFAR_HYD_PV, decoded)
                self._merge(SOFAR_HYD_BATT_START, SOFAR_HYD_BATT_COUNT, SOFAR_HYD_BATT, decoded)
                self._merge(SOFAR_HYD_BATT_TOTAL_START, SOFAR_HYD_BATT_TOTAL_COUNT, SOFAR_HYD_BATT_TOTAL, decoded)
                self._merge(SOFAR_HYD_ENERGY_START, SOFAR_HYD_ENERGY_COUNT, SOFAR_HYD_ENERGY, decoded)
            return standardize_sofar(decoded, series=series)
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Sofar read failed: %s", e)
            self.disconnect()
            return None
