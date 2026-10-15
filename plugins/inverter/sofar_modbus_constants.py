# plugins/inverter/sofar_modbus_constants.py
"""
Sofar Modbus register maps for monitoring.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from typing import Any, Dict

# 0.01 kW per count → watts. 0.1 kW per count → watts.
_W_FROM_001_KW = 10
_W_FROM_01_KW = 100

SOFAR_HYD_STATE_START = 0x0404
SOFAR_HYD_STATE_COUNT = 1
SOFAR_HYD_STATE: Dict[str, Dict[str, Any]] = {
    "system_state": {"addr": 0x0404, "type": "uint16"},
}

SOFAR_HYD_SYSTEM_STATES = {
    0: "Waiting",
    1: "Checking",
    2: "Grid-connected",
    3: "Emergency Power Supply",
    4: "Recoverable Fault",
    5: "Permanent Fault",
    6: "Upgrading",
    7: "Self-Charging",
}

# ASCII serial number, 7 registers.
SOFAR_HYD_SERIAL_START = 0x0445
SOFAR_HYD_SERIAL_COUNT = 7

# On-grid output, 0x0484 through 0x04AF.
SOFAR_HYD_GRID_START = 0x0484
SOFAR_HYD_GRID_COUNT = 0x04AF - 0x0484 + 1

SOFAR_HYD_GRID: Dict[str, Dict[str, Any]] = {
    "grid_frequency": {"addr": 0x0484, "type": "uint16", "scale": 0.01},
    "ac_power": {"addr": 0x0485, "type": "int16", "scale": _W_FROM_001_KW},
    "grid_power": {"addr": 0x0488, "type": "int16", "scale": _W_FROM_001_KW},
    "grid_l1_voltage": {"addr": 0x048D, "type": "uint16", "scale": 0.1},
    "grid_l1_power": {"addr": 0x0493, "type": "int16", "scale": _W_FROM_001_KW},
    "grid_l2_voltage": {"addr": 0x0498, "type": "uint16", "scale": 0.1},
    "grid_l2_power": {"addr": 0x049E, "type": "int16", "scale": _W_FROM_001_KW},
    "grid_l3_voltage": {"addr": 0x04A3, "type": "uint16", "scale": 0.1},
    "grid_l3_power": {"addr": 0x04A9, "type": "int16", "scale": _W_FROM_001_KW},
    "load_power": {"addr": 0x04AF, "type": "uint16", "scale": _W_FROM_001_KW},
}

SOFAR_HYD_TEMP_START = 0x0418
SOFAR_HYD_TEMP_COUNT = 1
SOFAR_HYD_TEMP: Dict[str, Dict[str, Any]] = {
    "inverter_temp": {"addr": 0x0418, "type": "int16"},
}

# Off-grid / EPS totals, 0x0504 through 0x050A.
SOFAR_HYD_EPS_START = 0x0504
SOFAR_HYD_EPS_COUNT = 0x050A - 0x0504 + 1
SOFAR_HYD_EPS: Dict[str, Dict[str, Any]] = {
    "eps_power": {"addr": 0x0504, "type": "int16", "scale": _W_FROM_001_KW},
    "eps_frequency": {"addr": 0x0507, "type": "uint16", "scale": 0.01},
    "eps_voltage": {"addr": 0x050A, "type": "uint16", "scale": 0.1},
}

# PV strings 1-4 plus the total at 0x05C4. One read covers the gap.
SOFAR_HYD_PV_START = 0x0584
SOFAR_HYD_PV_COUNT = 0x05C4 - 0x0584 + 1
SOFAR_HYD_PV: Dict[str, Dict[str, Any]] = {
    "pv1_voltage": {"addr": 0x0584, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 0x0585, "type": "uint16", "scale": 0.01},
    "pv1_power": {"addr": 0x0586, "type": "uint16", "scale": _W_FROM_001_KW},
    "pv2_voltage": {"addr": 0x0587, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 0x0588, "type": "uint16", "scale": 0.01},
    "pv2_power": {"addr": 0x0589, "type": "uint16", "scale": _W_FROM_001_KW},
    "pv3_voltage": {"addr": 0x058A, "type": "uint16", "scale": 0.1},
    "pv3_current": {"addr": 0x058B, "type": "uint16", "scale": 0.01},
    "pv3_power": {"addr": 0x058C, "type": "uint16", "scale": _W_FROM_001_KW},
    "pv4_voltage": {"addr": 0x058D, "type": "uint16", "scale": 0.1},
    "pv4_current": {"addr": 0x058E, "type": "uint16", "scale": 0.01},
    "pv4_power": {"addr": 0x058F, "type": "uint16", "scale": _W_FROM_001_KW},
    "pv_power_total": {"addr": 0x05C4, "type": "uint16", "scale": _W_FROM_01_KW},
}

SOFAR_HYD_BATT_START = 0x0604
SOFAR_HYD_BATT_COUNT = 7
SOFAR_HYD_BATT: Dict[str, Dict[str, Any]] = {
    "battery_voltage": {"addr": 0x0604, "type": "uint16", "scale": 0.1},
    "battery_current": {"addr": 0x0605, "type": "int16", "scale": 0.01},
    # Positive register value is charging.
    "battery_power": {"addr": 0x0606, "type": "int16", "scale": _W_FROM_001_KW},
    "battery_temp": {"addr": 0x0607, "type": "int16"},
    "battery_soc": {"addr": 0x0608, "type": "uint16"},
    "battery_soh": {"addr": 0x0609, "type": "uint16"},
}

SOFAR_HYD_BATT_TOTAL_START = 0x0667
SOFAR_HYD_BATT_TOTAL_COUNT = 3
SOFAR_HYD_BATT_TOTAL: Dict[str, Dict[str, Any]] = {
    "battery_power_total": {"addr": 0x0667, "type": "int16", "scale": _W_FROM_01_KW},
    "battery_soc_total": {"addr": 0x0668, "type": "uint16"},
    "battery_soh_total": {"addr": 0x0669, "type": "uint16"},
}

SOFAR_HYD_ENERGY_START = 0x0684
SOFAR_HYD_ENERGY_COUNT = 0x069B - 0x0684 + 1
SOFAR_HYD_ENERGY: Dict[str, Dict[str, Any]] = {
    "pv_daily_energy": {"addr": 0x0684, "type": "uint32", "scale": 0.01},
    "pv_total_energy": {"addr": 0x0686, "type": "uint32", "scale": 0.1},
    "load_daily_energy": {"addr": 0x0688, "type": "uint32", "scale": 0.01},
    "load_total_energy": {"addr": 0x068A, "type": "uint32", "scale": 0.1},
    "grid_import_daily": {"addr": 0x068C, "type": "uint32", "scale": 0.01},
    "grid_import_total": {"addr": 0x068E, "type": "uint32", "scale": 0.1},
    "grid_export_daily": {"addr": 0x0690, "type": "uint32", "scale": 0.01},
    "grid_export_total": {"addr": 0x0692, "type": "uint32", "scale": 0.1},
    "battery_charge_daily": {"addr": 0x0694, "type": "uint32", "scale": 0.01},
    "battery_charge_total": {"addr": 0x0696, "type": "uint32", "scale": 0.1},
    "battery_discharge_daily": {"addr": 0x0698, "type": "uint32", "scale": 0.01},
    "battery_discharge_total": {"addr": 0x069A, "type": "uint32", "scale": 0.1},
}

# Older HYD ES hybrid block. Positive battery power is charging.
# Positive measured grid power is export.
SOFAR_ES_START = 0x0200
SOFAR_ES_COUNT = 0x0222 - 0x0200 + 2
SOFAR_ES: Dict[str, Dict[str, Any]] = {
    "run_mode": {"addr": 0x0200, "type": "uint16"},
    "grid_l1_voltage": {"addr": 0x0206, "type": "uint16", "scale": 0.1},
    "grid_l2_voltage": {"addr": 0x0208, "type": "uint16", "scale": 0.1},
    "grid_l3_voltage": {"addr": 0x020A, "type": "uint16", "scale": 0.1},
    "grid_frequency": {"addr": 0x020C, "type": "uint16", "scale": 0.01},
    "battery_power": {"addr": 0x020D, "type": "int16", "scale": _W_FROM_001_KW},
    "battery_voltage": {"addr": 0x020E, "type": "uint16", "scale": 0.1},
    "battery_current": {"addr": 0x020F, "type": "int16", "scale": 0.01},
    "battery_soc": {"addr": 0x0210, "type": "uint16"},
    "battery_temp": {"addr": 0x0211, "type": "int16"},
    "grid_power": {"addr": 0x0212, "type": "int16", "scale": _W_FROM_001_KW},
    "load_power": {"addr": 0x0213, "type": "uint16", "scale": _W_FROM_001_KW},
    # Generation power is AC output, not PV DC. PV comes from the strings at 0x0250.
    "ac_power": {"addr": 0x0215, "type": "uint16", "scale": _W_FROM_001_KW},
    "eps_voltage": {"addr": 0x0216, "type": "uint16", "scale": 0.1},
    "eps_power": {"addr": 0x0217, "type": "uint16", "scale": _W_FROM_001_KW},
    "pv_daily_energy": {"addr": 0x0218, "type": "uint16", "scale": 0.01},
    "grid_export_daily": {"addr": 0x0219, "type": "uint16", "scale": 0.01},
    "grid_import_daily": {"addr": 0x021A, "type": "uint16", "scale": 0.01},
    "load_daily_energy": {"addr": 0x021B, "type": "uint16", "scale": 0.01},
    "pv_total_energy": {"addr": 0x021C, "type": "uint32"},
    "grid_export_total": {"addr": 0x021E, "type": "uint32"},
    "grid_import_total": {"addr": 0x0220, "type": "uint32"},
    "load_total_energy": {"addr": 0x0222, "type": "uint32"},
}

SOFAR_ES_PV_START = 0x0250
SOFAR_ES_PV_COUNT = 6
SOFAR_ES_PV: Dict[str, Dict[str, Any]] = {
    "pv1_voltage": {"addr": 0x0250, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 0x0251, "type": "uint16", "scale": 0.01},
    "pv1_power": {"addr": 0x0252, "type": "uint16", "scale": 10},
    "pv2_voltage": {"addr": 0x0253, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 0x0254, "type": "uint16", "scale": 0.01},
    "pv2_power": {"addr": 0x0255, "type": "uint16", "scale": 10},
}

SOFAR_ES_RUN_MODES = {
    0: "Waiting",
    1: "Checking",
    2: "Normal",
    3: "Checking Discharge",
    4: "Discharge",
    5: "EPS",
    6: "Fault",
    7: "Permanent Fault",
}
