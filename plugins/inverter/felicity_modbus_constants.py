# plugins/inverter/felicity_modbus_constants.py
"""
Felicity Solar Modbus Constants and Register Definitions

This module contains Growatt-like holding-register maps for Felicity Solar
T-REX / hybrid inverters used by the Felicity Modbus plugin (testing).

Features:
- Primary dynamic register block (status, PV, grid, load, temperature)
- Optional storage/hybrid register block
- Scales and type hints aligned with Growatt-style maps

Supported Models:
- Felicity Solar T-REX / LI / hybrid families

Register Categories:
- FELICITY_DYNAMIC: Real-time operational holding registers
- FELICITY_STORAGE: Optional storage/hybrid holding registers

Protocol Reference: Felicity Solar Modbus (Growatt-like; testing)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from typing import Any, Dict

FELICITY_START = 0
FELICITY_COUNT = 125

FELICITY_DYNAMIC: Dict[str, Dict[str, Any]] = {
    "inverter_status": {"addr": 0, "type": "uint16"},
    "pv1_voltage": {"addr": 3, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 4, "type": "uint16", "scale": 0.1},
    "pv1_power": {"addr": 5, "type": "uint32"},
    "pv2_voltage": {"addr": 7, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 8, "type": "uint16", "scale": 0.1},
    "pv2_power": {"addr": 9, "type": "uint32"},
    "grid_l1_voltage": {"addr": 38, "type": "uint16", "scale": 0.1},
    "grid_frequency": {"addr": 37, "type": "uint16", "scale": 0.01},
    "ac_power": {"addr": 35, "type": "uint32"},
    "load_power": {"addr": 47, "type": "uint32"},
    "inverter_temp": {"addr": 32, "type": "int16", "scale": 0.1},
}

# Storage block may be unavailable on grid-tied-only units
FELICITY_STORAGE_START = 1000
FELICITY_STORAGE_COUNT = 50
FELICITY_STORAGE: Dict[str, Dict[str, Any]] = {
    "battery_voltage": {"addr": 1013, "type": "uint16", "scale": 0.1},
    "battery_soc": {"addr": 1014, "type": "uint16"},
    "battery_power": {"addr": 1015, "type": "int16"},
    "battery_temp": {"addr": 1040, "type": "int16", "scale": 0.1},
}
