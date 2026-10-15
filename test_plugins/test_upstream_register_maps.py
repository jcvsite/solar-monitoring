"""Decode checks for register maps adapted from community Modbus plugins."""
from __future__ import annotations

from core.plugin_catalog import list_plugins
from plugins.modbus_helper import decode_registers_by_map
from plugins.plugin_interface import StandardDataKeys
from plugins.inverter.sofar_modbus_constants import (
    SOFAR_HYD_BATT,
    SOFAR_HYD_BATT_START,
    SOFAR_HYD_GRID,
    SOFAR_HYD_GRID_START,
)
from plugins.inverter.sofar_modbus_plugin import standardize_sofar
from plugins.inverter.solax_modbus_plugin import (
    SOLAX_INPUT,
    SOLAX_INPUT_COUNT,
    SOLAX_INPUT_START,
    standardize_solax,
)
from plugins.inverter.solinteg_modbus_plugin import standardize_solinteg
from plugins.inverter.srne_modbus_plugin import standardize_srne_hybrid


def _block(start: int, count: int, values: dict[int, int]) -> list[int]:
    return [values.get(start + i, 0) for i in range(count)]


def test_sofar_hyd_flips_charge_positive_battery_and_reads_grid_frequency():
    grid = _block(SOFAR_HYD_GRID_START, 0x04AF - SOFAR_HYD_GRID_START + 1, {
        0x0484: 5000,  # 50.00 Hz
        0x0488: 150,   # 1.50 kW export at the PCC
    })
    batt = _block(SOFAR_HYD_BATT_START, 7, {
        0x0604: 512,   # 51.2 V
        0x0606: 100,   # 1.00 kW charging
        0x0608: 80,
    })
    decoded = {}
    decoded.update(decode_registers_by_map(grid, SOFAR_HYD_GRID, SOFAR_HYD_GRID_START))
    decoded.update(decode_registers_by_map(batt, SOFAR_HYD_BATT, SOFAR_HYD_BATT_START))
    out = standardize_sofar(decoded, series="hyd")
    assert out[StandardDataKeys.GRID_FREQUENCY_HZ] == 50.0
    assert out[StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS] == 1500
    assert out[StandardDataKeys.BATTERY_POWER_WATTS] == -1000
    assert out[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT] == 80
    assert out[StandardDataKeys.BATTERY_CHARGE_STATE] == "charging"


def test_solax_meter_import_becomes_negative_grid_power():
    regs = _block(SOLAX_INPUT_START, SOLAX_INPUT_COUNT, {
        0x0002: 2000,
        0x000A: 1500,
        0x0014: 480,   # 48.0 V
        0x0016: 400,   # 400 W charging
        0x001C: 55,
        0x0046: 500,   # import 500 W, low word of little-endian int32
    })
    decoded = decode_registers_by_map(regs, SOLAX_INPUT, SOLAX_INPUT_START)
    out = standardize_solax(decoded, generation="gen3")
    assert out[StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS] == -500
    assert out[StandardDataKeys.BATTERY_POWER_WATTS] == -400
    assert out[StandardDataKeys.LOAD_TOTAL_POWER_WATTS] == 1500  # 2000 - 500
    assert out[StandardDataKeys.PV_TOTAL_DC_POWER_WATTS] == 1500
    assert out[StandardDataKeys.BATTERY_VOLTAGE_VOLTS] == 48.0


def test_solinteg_house_load_is_inverter_minus_export():
    out = standardize_solinteg({
        "ac_power": 3000,
        "grid_power": 1000,
        "battery_power": 500,
        "pv_power_total": 4000,
        "battery_soc": 70,
        "run_mode": 2,
    })
    assert out[StandardDataKeys.LOAD_TOTAL_POWER_WATTS] == 2000
    assert out[StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS] == 1000
    assert out[StandardDataKeys.BATTERY_CHARGE_STATE] == "discharging"
    assert out[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT] == "On Grid"


def test_srne_hybrid_maps_dual_pv_and_run_mode():
    out = standardize_srne_hybrid({
        "pv1_power": 800,
        "pv2_power": 200,
        "battery_power": -100,
        "battery_soc": 60,
        "battery_voltage": 51.2,
        "run_mode": 5,
        "inverter_voltage": 230,
        "inverter_current": 4,
        "load_current": 3,
        "grid_frequency": 50.0,
    })
    assert out[StandardDataKeys.PV_TOTAL_DC_POWER_WATTS] == 1000
    assert out[StandardDataKeys.BATTERY_CHARGE_STATE] == "charging"
    assert out[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT] == "Inverter"
    assert out[StandardDataKeys.AC_POWER_WATTS] == 920
    assert out[StandardDataKeys.LOAD_TOTAL_POWER_WATTS] == 690


def test_catalog_includes_new_inverter_plugins():
    types = {p["plugin_type"] for p in list_plugins()}
    assert "inverter.solax_modbus_plugin" in types
    assert "inverter.alphaess_modbus_plugin" in types
    assert "inverter.solinteg_modbus_plugin" in types
