# plugins/inverter/powmr_rs232_plugin_constants.py
"""
Constants and register definitions for POWMR hybrid inverters using the custom RS232 protocol.

This module contains all the constants, register mappings, and data structures needed
to communicate with POWMR hybrid inverters using their native inv8851 protocol.

The definitions are based on the official header file:
https://github.com/leodesigner/powmr4500_comm/blob/main/include/inv8851.h

Key Components:
- Protocol constants for packet structure
- Complete register mapping for state and configuration data
- Run mode codes and status interpretations
- Alert/fault code mappings with categorization
- Data type definitions and scaling factors

Protocol Overview:
The inv8851 protocol uses a simple packet structure:
[Protocol Header (0x8851)][Command][Address][Data Size][Data Payload][CRC16]

Supported Commands:
- 0x0003: Read state data (operational parameters)
- 0x0300: Read configuration data (settings)
- 0x1000: Write configuration data (future use)

Version Support:
- Version 1: Standard packet sizes (154 bytes state, 100 bytes config)
- Version 2: Extended packet sizes (158 bytes state, 104 bytes config)

GitHub: https://github.com/jcvsite/solar-monitoring
"""

from typing import Dict, Any

# Protocol constants based on inv8851.h specification
PROTOCOL_HEADER = 0x8851        # Fixed protocol identifier
STATE_COMMAND = 0x0003          # Command to read operational state data
CONFIG_COMMAND_READ = 0x0300    # Command to read configuration data
CONFIG_COMMAND_WRITE = 0x1000   # Command to write configuration data (future use)
STATE_ADDRESS = 0x0000          # Address for state data requests
CONFIG_ADDRESS = 0x0200         # Address for configuration data requests

# Run mode codes based on enum run_mode in inv8851.h
# These codes represent the PV topology operating mode (3rd nibble of run_mode register)
POWMR_RUN_MODE_CODES = {
    0: "Standby",                    # Inverter in standby mode
    1: "Fault",                      # System fault detected
    2: "Shutdown",                   # System shutdown
    3: "Normal",                     # Normal operation mode
    4: "No Battery",                 # Operating without battery
    5: "Discharge",                  # Battery discharging mode
    6: "Parallel Discharge",         # Parallel operation with discharge
    7: "Bypass",                     # Bypass mode (direct grid passthrough)
    8: "Charge",                     # Battery charging mode
    9: "Grid Discharge",             # Grid-tied discharge mode
    10: "Micro Grid Discharge",      # Micro-grid discharge mode
}

# State data register mapping - addresses are word offsets from start of data payload
# Complete register map based on inv8851.h structure with all 74 registers
# Each register represents a 16-bit word containing operational data
POWMR_REGISTERS: Dict[str, Dict[str, Any]] = {
    # Word 0: Run mode with 4 topology nibbles
    "run_mode": {"addr": 0, "type": "uint16", "unit": "Bitfield"},
    
    # Word 1: System status flags (matches inv8851.h system_flags)
    "system_flags": {"addr": 1, "type": "uint16", "unit": "Bitfield"},
    
    # Words 2-3: Warning/fault flags
    "warning_flags_1": {"addr": 2, "type": "int16", "unit": "Bitfield"},
    "warning_flags_2": {"addr": 3, "type": "int16", "unit": "Bitfield"},
    
    # Word 4: Grid and utility flags
    "grid_flags": {"addr": 4, "type": "uint16", "unit": "Bitfield"},
    
    # Words 5-12: Additional warning/status flags (from inv8851.h)
    "warning_flags_3": {"addr": 5, "type": "int16", "unit": "Bitfield"},
    "warning_flags_4": {"addr": 6, "type": "int16", "unit": "Bitfield"},
    "warning_flags_5": {"addr": 7, "type": "int16", "unit": "Bitfield"},
    "warning_flags_6": {"addr": 8, "type": "int16", "unit": "Bitfield"},
    "warning_flags_7": {"addr": 9, "type": "int16", "unit": "Bitfield"},
    "warning_flags_8": {"addr": 10, "type": "int16", "unit": "Bitfield"},
    "warning_flags_9": {"addr": 11, "type": "int16", "unit": "Bitfield"},
    "warning_flags_10": {"addr": 12, "type": "int16", "unit": "Bitfield"},
    
    # Word 13: PV and parallel status flags
    "pv_parallel_flags": {"addr": 13, "type": "uint16", "unit": "Bitfield"},
    
    # Word 14-15: Version and log info
    "software_version": {"addr": 14, "type": "int16", "static": True},
    "log_number": {"addr": 15, "type": "int16"},
    
    # Words 16-20: Reserved/unknown
    "reserved_16": {"addr": 16, "type": "int16"},
    "reserved_17": {"addr": 17, "type": "int16"},
    "reserved_18": {"addr": 18, "type": "int16"},
    "reserved_19": {"addr": 19, "type": "int16"},
    "reserved_20": {"addr": 20, "type": "int16"},
    
    # Words 21-25: Inverter output measurements
    "inv_voltage": {"addr": 21, "type": "int16", "scale": 0.1, "unit": "V"},
    "inv_current": {"addr": 22, "type": "int16", "scale": 0.01, "unit": "A"},
    "inv_freq": {"addr": 23, "type": "int16", "scale": 0.01, "unit": "Hz"},
    "inv_va": {"addr": 24, "type": "int16", "unit": "VA"},
    "load_va": {"addr": 25, "type": "int16", "unit": "VA"},
    
    # Word 26: Grid consumption (from inv8851.h comments)
    "grid_consumption_va": {"addr": 26, "type": "int16", "unit": "VA"},
    
    # Words 27-32: Load measurements
    "load_watt": {"addr": 27, "type": "int16", "unit": "W"},
    "inverter_va_percent": {"addr": 28, "type": "int16", "unit": "%"},
    "inverter_watt_percent": {"addr": 29, "type": "int16", "unit": "%"},
    "load_current": {"addr": 30, "type": "int16", "scale": 0.01, "unit": "A"},
    "low_load_current": {"addr": 31, "type": "int16", "scale": 0.01, "unit": "A"},
    "grid_power_consumption": {"addr": 32, "type": "int16", "unit": "W"},
    
    # Words 33-38: Grid measurements and parallel
    "grid_voltage": {"addr": 33, "type": "int16", "scale": 0.1, "unit": "V"},
    "grid_current": {"addr": 34, "type": "int16", "scale": 0.01, "unit": "A"},
    "grid_freq": {"addr": 35, "type": "int16", "scale": 0.01, "unit": "Hz"},
    "parallel_voltage": {"addr": 36, "type": "int16", "scale": 0.1, "unit": "V"},
    "parallel_current": {"addr": 37, "type": "int16", "scale": 0.01, "unit": "A"},
    "parallel_frequency": {"addr": 38, "type": "int16", "scale": 0.01, "unit": "Hz"},
    
    # Words 39-42: Battery measurements
    "batt_voltage": {"addr": 39, "type": "int16", "scale": 0.01, "unit": "V"},
    "batt_charge_current": {"addr": 40, "type": "int16", "scale": 0.1, "unit": "A"},
    "reserved_41": {"addr": 41, "type": "int16"},
    "reserved_42": {"addr": 42, "type": "int16"},
    
    # Words 43-49: PV and bus measurements
    "pv_voltage": {"addr": 43, "type": "int16", "scale": 0.1, "unit": "V"},
    "pv_current": {"addr": 44, "type": "int16", "scale": 0.01, "unit": "A"},
    "pv_power": {"addr": 45, "type": "int16", "unit": "W"},
    "bus_voltage": {"addr": 46, "type": "int16", "scale": 0.1, "unit": "V"},
    "reserved_47": {"addr": 47, "type": "int16"},
    "reserved_48": {"addr": 48, "type": "int16"},
    "inverter_voltage_dc_component": {"addr": 49, "type": "int16", "scale": 0.1, "unit": "V"},
    
    # Word 50: Fan speeds (2 bytes: fan1_speed_percent | fan2_speed_percent)
    "fan_speeds": {"addr": 50, "type": "uint16"},
    
    # Word 51: NTC temperatures (2 bytes: ntc2_temperature | ntc3_temperature)
    "ntc_temps_1": {"addr": 51, "type": "uint16"},
    
    # Word 52: More temperatures (2 bytes: ntc4_temperature | bts_temperature)
    "ntc_temps_2": {"addr": 52, "type": "uint16"},
    
    # Words 53-71: BMS data
    "bms_battery_soc": {"addr": 53, "type": "int16", "unit": "%"},
    "bms_battery_voltage": {"addr": 54, "type": "int16", "scale": 0.01, "unit": "V"},
    "bms_battery_current": {"addr": 55, "type": "int16", "scale": 0.01, "unit": "A"},
    "bms_cell_01_voltage": {"addr": 56, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_02_voltage": {"addr": 57, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_03_voltage": {"addr": 58, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_04_voltage": {"addr": 59, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_05_voltage": {"addr": 60, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_06_voltage": {"addr": 61, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_07_voltage": {"addr": 62, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_08_voltage": {"addr": 63, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_09_voltage": {"addr": 64, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_10_voltage": {"addr": 65, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_11_voltage": {"addr": 66, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_12_voltage": {"addr": 67, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_13_voltage": {"addr": 68, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_14_voltage": {"addr": 69, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_15_voltage": {"addr": 70, "type": "int16", "scale": 0.001, "unit": "V"},
    "bms_cell_16_voltage": {"addr": 71, "type": "int16", "scale": 0.001, "unit": "V"},
    
    # Version 2 protocol extra words
    "extra_word1_v2_state": {"addr": 72, "type": "uint16", "version": 2},
    "extra_word2_v2_state": {"addr": 73, "type": "uint16", "version": 2},
}

# Configuration data register mapping - addresses are word offsets from start of config data payload
# These registers contain user-configurable settings and system parameters
# Configuration data is typically read once and cached since it changes infrequently
POWMR_CONFIG_REGISTERS: Dict[str, Dict[str, Any]] = {
    "config_flags_1": {"addr": 0, "type": "uint16", "unit": "Bitfield"},
    "config_flags_2": {"addr": 1, "type": "uint16", "unit": "Bitfield"},
    "inverter_max_power": {"addr": 2, "type": "int16", "unit": "W"},
    "output_voltage_setting": {"addr": 3, "type": "int16", "scale": 0.1, "unit": "V"},
    "output_freq_setting": {"addr": 4, "type": "int16", "scale": 0.01, "unit": "Hz"},
    "batt_cut_off_voltage": {"addr": 15, "type": "int16", "scale": 0.01, "unit": "V"},
    "batt_bulk_chg_voltage": {"addr": 20, "type": "int16", "scale": 0.01, "unit": "V"},
    "batt_float_chg_voltage": {"addr": 22, "type": "int16", "scale": 0.01, "unit": "V"},
    "batt_pont_back_to_util_volt": {"addr": 23, "type": "int16", "scale": 0.01, "unit": "V"},
    "util_chg_current_setting": {"addr": 24, "type": "int16", "scale": 0.1, "unit": "A"},
    "total_chg_current_setting": {"addr": 25, "type": "int16", "scale": 0.1, "unit": "A"},
    "batt_chg_cut_off_current": {"addr": 26, "type": "int16", "scale": 0.1, "unit": "A"},
    "battery_equalization_enable": {"addr": 37, "type": "uint16", "unit": "bool"},
    "batt_eq_voltage": {"addr": 41, "type": "int16", "scale": 0.01, "unit": "V"},
    "batt_eq_time": {"addr": 42, "type": "int16", "unit": "min"},
    "batt_eq_timeout": {"addr": 43, "type": "int16", "unit": "min"},
    "batt_eq_interval": {"addr": 44, "type": "int16", "unit": "days"},
}

# Alert/status bit mappings based on inv8851.h structure
# Maps register addresses to their bit definitions and categories
# Each bitfield register can have up to 16 individual status/alert bits
POWMR_ALERT_MAPS = {
    # Word 1: System status flags (from inv8851.h system_flags structure)
    1: { "category": "system", "bits": {
        0: "System Power", 1: "Charge Finish", 2: "Bus OK", 3: "Bus/Grid Voltage Match",
        4: "No Battery", 5: "PV Excess", 6: "Floating Charge", 7: "System Initial Finished",
        8: "Inverter Topology Initial Finished", 9: "LLC Topology Initial Finished",
        10: "PV Topology Initial Finished", 11: "Buck Topology Initial Finished",
        12: "EQ Charge Start", 13: "EQ Charge Ready"
    }},
    
    # Words 2-3: Warning/fault flags (generic mapping)
    2: { "category": "warning", "bits": {
        i: f"Warning Flag 2 Bit {i}" for i in range(16)
    }},
    3: { "category": "warning", "bits": {
        i: f"Warning Flag 3 Bit {i}" for i in range(16)
    }},
    
    # Word 4: Grid and utility flags (from inv8851.h grid flags structure)
    4: { "category": "grid", "bits": {
        0: "Grid PLL OK", 9: "Disable Utility"
    }},
    
    # Words 5-12: Additional warning flags (generic mapping for now)
    5: { "category": "warning", "bits": {
        i: f"Warning Flag 5 Bit {i}" for i in range(16)
    }},
    6: { "category": "warning", "bits": {
        i: f"Warning Flag 6 Bit {i}" for i in range(16)
    }},
    7: { "category": "warning", "bits": {
        i: f"Warning Flag 7 Bit {i}" for i in range(16)
    }},
    8: { "category": "warning", "bits": {
        i: f"Warning Flag 8 Bit {i}" for i in range(16)
    }},
    9: { "category": "warning", "bits": {
        i: f"Warning Flag 9 Bit {i}" for i in range(16)
    }},
    10: { "category": "warning", "bits": {
        i: f"Warning Flag 10 Bit {i}" for i in range(16)
    }},
    11: { "category": "warning", "bits": {
        i: f"Warning Flag 11 Bit {i}" for i in range(16)
    }},
    12: { "category": "warning", "bits": {
        i: f"Warning Flag 12 Bit {i}" for i in range(16)
    }},
    
    # Word 13: PV and parallel status flags (from inv8851.h)
    13: { "category": "system", "bits": {
        4: "PV Input OK", 8: "Parallel Lock Phase OK"
    }}
}

# Alert categories for organizing different types of system notifications
# Used to group related alerts together for better user interface organization
ALERT_CATEGORIES = [
    "system",    # System status and operational state alerts
    "grid",      # Grid-related alerts (voltage, frequency, connection)
    "fault",     # Hardware faults and critical errors
    "warning"    # Non-critical warnings and informational alerts
]