# plugins/inverter/sofar_modbus_constants.py
"""
Sofar Modbus Constants and Register Definitions

This module contains holding-register maps for Sofar HYD/G3 hybrid inverters
used by the Sofar Modbus plugin.

Features:
- Dynamic operational register block (PV, battery, AC, temperatures)
- Energy counter register block
- Scales and signed/unsigned type hints per field

Supported Models:
- Sofar HYD / G3 / ME hybrid families

Register Categories:
- SOFAR_DYNAMIC: Real-time operational holding registers
- SOFAR_ENERGY: Daily/lifetime energy counters

Protocol Reference: Sofar Modbus (community sofar2mqtt aligned)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from typing import Any, Dict

SOFAR_DYNAMIC_START = 0x0480
SOFAR_DYNAMIC_COUNT = 32

SOFAR_DYNAMIC: Dict[str, Dict[str, Any]] = {
    "ac_power": {"addr": 0x0480, "type": "int16"},
    "pv1_voltage": {"addr": 0x0484, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 0x0485, "type": "uint16", "scale": 0.01},
    "pv1_power": {"addr": 0x0486, "type": "uint16"},
    "pv2_voltage": {"addr": 0x0487, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 0x0488, "type": "uint16", "scale": 0.01},
    "pv2_power": {"addr": 0x0489, "type": "uint16"},
    "battery_voltage": {"addr": 0x048D, "type": "uint16", "scale": 0.1},
    "battery_current": {"addr": 0x048E, "type": "int16", "scale": 0.01},
    "battery_soc": {"addr": 0x048F, "type": "uint16"},
    "battery_temp": {"addr": 0x0490, "type": "int16", "scale": 0.1},
    "grid_frequency": {"addr": 0x048C, "type": "uint16", "scale": 0.01},
    "inverter_temp": {"addr": 0x0491, "type": "int16", "scale": 0.1},
}

SOFAR_ENERGY_START = 0x0684
SOFAR_ENERGY_COUNT = 8
SOFAR_ENERGY: Dict[str, Dict[str, Any]] = {
    "pv_daily_energy": {"addr": 0x0684, "type": "uint16", "scale": 0.01},
    "pv_total_energy": {"addr": 0x0685, "type": "uint32", "scale": 0.1},
}
