# plugins/inverter/sungrow_modbus_constants.py
"""
Sungrow Modbus Constants and Register Definitions

This module contains input-register maps for Sungrow SH hybrid inverters used
by the Sungrow Modbus plugin.

Features:
- Core PV/AC input-register block
- Hybrid battery input-register block
- Scales and type hints for voltage, power, and energy fields

Supported Models:
- Sungrow SH / SG hybrid families

Register Categories:
- SUNGROW_PV: PV and AC operational input registers
- SUNGROW_BAT: Hybrid battery input registers

Protocol Reference: Sungrow Modbus (community / Home Assistant aligned)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from typing import Any, Dict

# Core AC/PV block
SUNGROW_PV_START = 5000
SUNGROW_PV_COUNT = 40

SUNGROW_PV: Dict[str, Dict[str, Any]] = {
    "grid_l1_voltage": {"addr": 5019, "type": "uint16", "scale": 0.1},
    "grid_l1_current": {"addr": 5022, "type": "uint16", "scale": 0.1},
    "grid_frequency": {"addr": 5036, "type": "uint16", "scale": 0.1},
    "ac_power": {"addr": 5031, "type": "int16"},
    "pv_total_power": {"addr": 5017, "type": "uint16"},
    "daily_pv_energy": {"addr": 5003, "type": "uint16", "scale": 0.1},
    "total_pv_energy": {"addr": 5004, "type": "uint32", "scale": 0.1},
}

# Hybrid battery block
SUNGROW_BAT_START = 13000
SUNGROW_BAT_COUNT = 40

SUNGROW_BAT: Dict[str, Dict[str, Any]] = {
    "battery_power": {"addr": 13019, "type": "int16"},
    "battery_voltage": {"addr": 13021, "type": "uint16", "scale": 0.1},
    "battery_current": {"addr": 13020, "type": "int16", "scale": 0.1},
    "battery_soc": {"addr": 13022, "type": "uint16"},
    "battery_temp": {"addr": 13024, "type": "int16", "scale": 0.1},
    "load_power_hybrid": {"addr": 13028, "type": "uint16"},
}
