# plugins/inverter/sungrow_modbus_constants.py
"""
Sungrow Modbus Constants and Register Definitions

PDU addresses are the Sungrow document register number minus 1, which is what
SH RS / SH RT inverters answer. Confirmed against the mkaiser SHx Home Assistant
map (including the 2025 battery-current and battery-power registers).

32-bit values are low word first (int32_le / uint32_le).

Supported Models:
- Sungrow SH RS and SH RT hybrids
- Sungrow string inverters that share the 5000 input block

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from typing import Any, Dict

# Input block covering daily/total energy, DC power, grid voltage, string frequency.
SUNGROW_PV_START = 5002
SUNGROW_PV_COUNT = 34  # 5002 through 5035

SUNGROW_PV: Dict[str, Dict[str, Any]] = {
    "daily_pv_energy": {"addr": 5002, "type": "uint16", "scale": 0.1},
    "total_pv_energy": {"addr": 5003, "type": "uint32_le", "scale": 0.1},
    "pv_total_power": {"addr": 5016, "type": "uint32_le"},
    "grid_l1_voltage": {"addr": 5018, "type": "uint16", "scale": 0.1},
    # String-inverter frequency. Hybrids use 5241 (0.01 Hz) when that read succeeds.
    "grid_frequency_string": {"addr": 5035, "type": "uint16", "scale": 0.1},
}

# Hybrid running / load / battery / AC block.
SUNGROW_HYBRID_START = 12999
SUNGROW_HYBRID_COUNT = 36  # 12999 through 13034

SUNGROW_HYBRID: Dict[str, Dict[str, Any]] = {
    "load_power": {"addr": 13007, "type": "int32_le"},
    # Positive export, negative import. Matches the dashboard grid sign.
    "grid_power": {"addr": 13009, "type": "int32_le"},
    "battery_voltage": {"addr": 13019, "type": "uint16", "scale": 0.1},
    "battery_current_legacy": {"addr": 13020, "type": "int16", "scale": 0.1},
    "battery_power_legacy": {"addr": 13021, "type": "int16"},
    "battery_soc": {"addr": 13022, "type": "uint16", "scale": 0.1},
    "battery_soh": {"addr": 13023, "type": "uint16", "scale": 0.1},
    "battery_temp": {"addr": 13024, "type": "int16", "scale": 0.1},
    "grid_l1_current": {"addr": 13030, "type": "int16", "scale": 0.1},
    "ac_power": {"addr": 13033, "type": "int32_le"},
}

# Datasheet 1.1.11: battery power at 5214 (PDU 5213), hybrid frequency at 5242 (PDU 5241).
SUNGROW_BATT_POWER_START = 5213
SUNGROW_BATT_POWER_COUNT = 29  # through 5241

SUNGROW_BATT_POWER: Dict[str, Dict[str, Any]] = {
    "battery_power": {"addr": 5213, "type": "int32_le"},
    "grid_frequency": {"addr": 5241, "type": "uint16", "scale": 0.01},
}

# Datasheet replacement for battery current (document register 5631).
SUNGROW_BATT_CURRENT_START = 5630
SUNGROW_BATT_CURRENT_COUNT = 1

SUNGROW_BATT_CURRENT: Dict[str, Dict[str, Any]] = {
    "battery_current": {"addr": 5630, "type": "int16", "scale": 0.1},
}

# Older names kept so existing imports still resolve.
SUNGROW_BAT = SUNGROW_HYBRID
SUNGROW_BAT_START = SUNGROW_HYBRID_START
SUNGROW_BAT_COUNT = SUNGROW_HYBRID_COUNT
