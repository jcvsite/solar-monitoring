# plugins/inverter/srne_modbus_constants.py
"""
SRNE Modbus Constants and Register Definitions

This module contains comprehensive constant definitions for SRNE solar charge controllers
and DC power management devices using the Modbus RTU protocol. It includes all register maps,
status codes, fault codes, and configuration parameters needed to communicate with SRNE devices.

Features:
- Complete register mapping for operational and configuration data
- Static information registers for device identification
- Real-time operational data monitoring
- Battery status and management parameters
- Load control and monitoring capabilities
- Temperature monitoring from multiple sensors
- Comprehensive error handling and fault detection
- Energy statistics tracking (daily, total lifetime values)
- Configuration parameter access

Supported Models:
- SRNE ML series (hybrid inverters)
- SRNE HF series (high-frequency inverters)
- SRNE solar charge controllers
- Compatible SRNE DC power management devices

Register Categories:
- SRNE_REGISTERS: Complete register mapping for operational and configuration data
- SRNE_STATUS_CODES: Device status interpretations
- SRNE_FAULT_CODES: Fault code mappings for diagnostics
- SRNE_LOAD_MODES: Load control mode interpretations

Protocol Features:
- Hexadecimal addressing as per official documentation
- Function Code 0x03 (Read Holding Registers) primary usage
- Real-time monitoring of solar generation and battery management
- Load control and power distribution monitoring
- Temperature monitoring from multiple sensors
- Energy statistics tracking (daily, total lifetime values)
- Comprehensive fault and warning code processing
- Configuration parameter access and control

Note: SRNE devices are primarily DC charge controllers and power management systems,
not AC inverters. They manage solar panel charging, battery storage, and DC load distribution.

Protocol Reference: SRNE Modbus RTU Protocol Specification
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

from typing import Dict, Any

# Static Information Registers (Controller Info, read once)
SRNE_STATIC_REGISTERS: Dict[str, Dict[str, Any]] = {
    "system_info": {"addr": 0x000A, "len": 2}, # System Voltage/Current, Product Type
    "product_model": {"addr": 0x000C, "len": 8}, # ASCII Model String (16 bytes)
    "software_version": {"addr": 0x0014, "len": 2},
    "hardware_version": {"addr": 0x0016, "len": 2},
    "product_serial_number": {"addr": 0x0018, "len": 2},
}

# Dynamic Information Registers (Real-time operational data, polled frequently)
SRNE_DYNAMIC_REGISTERS: Dict[str, Dict[str, Any]] = {
    "battery_soc": {"addr": 0x0100, "scale": 1, "unit": "%"},
    "battery_voltage": {"addr": 0x0101, "scale": 0.1, "unit": "V"},
    "charge_current": {"addr": 0x0102, "scale": 0.01, "unit": "A"},
    "temperatures": {"addr": 0x0103}, # High byte: Controller, Low byte: Battery
    "load_voltage": {"addr": 0x0104, "scale": 0.1, "unit": "V"},
    "load_current": {"addr": 0x0105, "scale": 0.01, "unit": "A"},
    "load_power": {"addr": 0x0106, "unit": "W"},
    "pv_voltage": {"addr": 0x0107, "scale": 0.1, "unit": "V"},
    "pv_current": {"addr": 0x0108, "scale": 0.01, "unit": "A"},
    "pv_power": {"addr": 0x0109, "unit": "W"},
    "daily_min_battery_voltage": {"addr": 0x010B, "scale": 0.1, "unit": "V"},
    "daily_max_battery_voltage": {"addr": 0x010C, "scale": 0.1, "unit": "V"},
    "daily_max_charge_current": {"addr": 0x010D, "scale": 0.01, "unit": "A"},
    "daily_max_discharge_current": {"addr": 0x010E, "scale": 0.01, "unit": "A"},
    "daily_max_charge_power": {"addr": 0x010F, "unit": "W"},
    "daily_max_discharge_power": {"addr": 0x0110, "unit": "W"},
    "daily_charge_amp_hours": {"addr": 0x0111, "unit": "Ah"},
    "daily_discharge_amp_hours": {"addr": 0x0112, "unit": "Ah"},
    "daily_pv_power_generation": {"addr": 0x0113, "unit": "Wh"},
    "daily_load_power_consumption": {"addr": 0x0114, "unit": "Wh"},
    "total_operating_days": {"addr": 0x0115},
    "total_over_discharges": {"addr": 0x0116},
    "total_full_charges": {"addr": 0x0117},
    "total_charge_amp_hours": {"addr": 0x0118, "type": "uint32", "scale": 0.001, "unit": "kAh"},
    "total_discharge_amp_hours": {"addr": 0x011A, "type": "uint32", "scale": 0.001, "unit": "kAh"},
    "total_pv_power_generation": {"addr": 0x011C, "type": "uint32", "scale": 0.001, "unit": "kWh"},
    "total_load_power_consumption": {"addr": 0x011E, "type": "uint32", "scale": 0.001, "unit": "kWh"},
    "status_register": {"addr": 0x0120}, # Load status, brightness, battery status
    "fault_info_high": {"addr": 0x0121}, # Faults B16-B31
    "fault_info_low": {"addr": 0x0122},  # Faults B0-B15
}

# Mapping from register 0x0120 (low byte)
SRNE_BATTERY_STATUS_CODES = {
    0: "Charging Deactivated", 1: "Charging Activated", 2: "MPPT Charging",
    3: "Equalizing Charging", 4: "Boost Charging", 5: "Floating Charging",
    6: "Current Limiting (Overpower)"
}

# Bitfield mapping for Fault Register 0x0122 (Low 16 bits)
SRNE_FAULTS_LOW_MAP = {
    0: "Battery Over-discharge", 1: "Battery Over-voltage", 2: "Battery Under-voltage",
    3: "Load Short Circuit", 4: "Load Overpower or Over-current",
    5: "Controller Temperature Too High", 6: "Battery High Temperature (Prohibit Charging)",
    7: "Photovoltaic Input Overpower", 8: "(reserved)", 9: "Photovoltaic Input Side Over-voltage",
    10: "(reserved)", 11: "Solar Panel Working Point Over-voltage",
    12: "Solar Panel Reversely Connected", 13: "(reserved)", 14: "(reserved)", 15: "(reserved)",
}

# Bitfield mapping for Fault Register 0x0121 (High 16 bits)
SRNE_FAULTS_HIGH_MAP = {
    # Bits are B16-B31, so we map from 0-15
    6: "Power Supply Status (0=Batt, 1=Mains)", # B22
    7: "Battery Detected (SLD)", # B23
    8: "Battery High Temp (Prohibit Discharging)", # B24
    9: "Battery Low Temp (Prohibit Discharging)", # B25
    10: "Overcharge Protection", # B26
    11: "Battery Low Temp (Stop Charging)", # B27
    12: "Battery Reversely Connected", # B28
    13: "Capacitor Over-voltage", # B29
    14: "Induction Probe Damaged", # B30
    15: "Load Open-circuit", # B31
}