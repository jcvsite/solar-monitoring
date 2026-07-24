# plugins/inverter/goodwe_modbus_constants.py
"""
GoodWe Modbus Constants and Register Definitions

This module contains holding-register maps and work-mode codes for GoodWe
EH/ET hybrid inverters used by the GoodWe Modbus plugin.

Features:
- Contiguous ET-family dynamic register block (~35100)
- PV string, grid, AC power, load, and battery fields
- Work-mode code interpretations
- Configurable EH map variants via plugin config

Supported Models:
- GoodWe EH / ET / ES hybrid families

Register Categories:
- GOODWE_ET_DYNAMIC: Real-time operational holding registers
- GOODWE_WORK_MODES: Work mode code interpretations

Protocol Reference: GoodWe Modbus (community / goodwe lib aligned)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from typing import Any, Dict

# Contiguous block starting at 35100 (ET family). EH may need goodwe_map=eh.
GOODWE_ET_START = 35100
GOODWE_ET_COUNT = 100

GOODWE_ET_DYNAMIC: Dict[str, Dict[str, Any]] = {
    "work_mode": {"addr": 35100, "type": "uint16"},
    "pv1_voltage": {"addr": 35103, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 35104, "type": "uint16", "scale": 0.1},
    "pv1_power": {"addr": 35105, "type": "uint16"},
    "pv2_voltage": {"addr": 35107, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 35108, "type": "uint16", "scale": 0.1},
    "pv2_power": {"addr": 35109, "type": "uint16"},
    "grid_l1_voltage": {"addr": 35121, "type": "uint16", "scale": 0.1},
    "grid_l1_current": {"addr": 35122, "type": "int16", "scale": 0.1},
    "grid_frequency": {"addr": 35123, "type": "uint16", "scale": 0.01},
    "ac_power": {"addr": 35136, "type": "int16"},
    "load_power": {"addr": 35138, "type": "int16"},
    "battery_voltage": {"addr": 35180, "type": "uint16", "scale": 0.1},
    "battery_current": {"addr": 35181, "type": "int16", "scale": 0.1},
    "battery_soc": {"addr": 35182, "type": "uint16"},
    "battery_soh": {"addr": 35183, "type": "uint16"},
    "battery_temp": {"addr": 35184, "type": "int16", "scale": 0.1},
    "inverter_temp": {"addr": 35174, "type": "int16", "scale": 0.1},
    "pv_total_energy": {"addr": 35191, "type": "uint32", "scale": 0.1},
    "pv_daily_energy": {"addr": 35193, "type": "uint16", "scale": 0.1},
}

GOODWE_WORK_MODES = {
    0: "Wait",
    1: "Online",
    2: "Normal",
    3: "Fault",
    4: "Permanent fault",
    5: "Offline",
}
