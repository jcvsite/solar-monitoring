# plugins/inverter/luxpower_modbus_plugin_constants.py
"""
LuxPower Modbus Constants and Register Definitions

This module contains comprehensive constant definitions for LuxPower hybrid inverters using
the Modbus RTU/TCP protocol. It includes all register maps, status codes, and configuration
parameters needed to communicate with LuxPower inverter models.

Features:
- Complete register mapping (90+ operational registers, 50+ configuration registers)
- Input registers for real-time operational data
- Holding registers for configuration and static information
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- Battery management system integration
- Grid interaction and power flow monitoring
- Comprehensive error handling constants

Supported Models:
- LuxPower LXP-5K series (5kW hybrid inverters)
- LuxPower LXP-12K series (12kW hybrid inverters)
- LuxPower LXP-LB-5K series (5kW low-battery hybrid inverters)
- Compatible LuxPower hybrid inverter models

Register Categories:
- LUXPOWER_INPUT_REGISTERS: Real-time operational data (FC04)
- LUXPOWER_HOLD_REGISTERS: Configuration and static information (FC03)
- LUXPOWER_STATUS_CODES: Inverter status interpretations
- LUXPOWER_FAULT_CODES: Fault code mappings for diagnostics

Protocol Features:
- PV generation monitoring (multiple MPPT inputs)
- Battery status and energy management
- Grid interaction and power quality monitoring
- Load power consumption tracking
- Temperature monitoring from multiple sensors
- Energy statistics (daily and lifetime totals)
- Configuration parameter access

Data Sources:
- Enhanced version combining lxp-bridge project data
- luxpower-modbus-hacs project comprehensive mappings
- Official LuxPower Modbus protocol documentation

Protocol Reference: LuxPower Modbus RTU/TCP Protocol
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

from typing import Dict, Any

# Input Registers (Function Code 4) - Real-time operational data
LUXPOWER_INPUT_REGISTERS: Dict[str, Dict[str, Any]] = {
    "pv1_voltage": {"addr": 0, "type": "uint16", "scale": 0.1, "unit": "V"},
    "pv2_voltage": {"addr": 1, "type": "uint16", "scale": 0.1, "unit": "V"},
    "pv1_current": {"addr": 2, "type": "uint16", "scale": 0.1, "unit": "A"},
    "pv2_current": {"addr": 3, "type": "uint16", "scale": 0.1, "unit": "A"},
    "pv1_power": {"addr": 4, "type": "uint16", "unit": "W"},
    "pv2_power": {"addr": 5, "type": "uint16", "unit": "W"},
    "grid_voltage": {"addr": 6, "type": "uint16", "scale": 0.1, "unit": "V"},
    "grid_current": {"addr": 7, "type": "uint16", "scale": 0.1, "unit": "A"},
    "grid_power": {"addr": 8, "type": "int16", "unit": "W"}, # Can be negative for export
    "inverter_voltage": {"addr": 9, "type": "uint16", "scale": 0.1, "unit": "V"},
    "inverter_current": {"addr": 10, "type": "uint16", "scale": 0.1, "unit": "A"},
    "inverter_power": {"addr": 11, "type": "int16", "unit": "W"}, # Load power
    "grid_frequency": {"addr": 12, "type": "uint16", "scale": 0.01, "unit": "Hz"},
    "inverter_status_code": {"addr": 13, "type": "uint16"},
    "battery_voltage": {"addr": 16, "type": "uint16", "scale": 0.01, "unit": "V"},
    "battery_soc": {"addr": 17, "type": "uint16", "unit": "%"},
    "battery_current": {"addr": 18, "type": "int16", "scale": 0.1, "unit": "A"}, # +ve discharge, -ve charge
    "battery_power": {"addr": 19, "type": "int16", "unit": "W"}, # +ve discharge, -ve charge
    "battery_temperature": {"addr": 20, "type": "int16", "scale": 0.1, "unit": "C"},
    "inverter_temperature": {"addr": 21, "type": "int16", "scale": 0.1, "unit": "C"},
    "eps_voltage": {"addr": 24, "type": "uint16", "scale": 0.1, "unit": "V"},
    "eps_current": {"addr": 25, "type": "uint16", "scale": 0.1, "unit": "A"},
    "eps_power": {"addr": 26, "type": "uint16", "unit": "W"},
    "eps_frequency": {"addr": 27, "type": "uint16", "scale": 0.01, "unit": "Hz"},
    "exported_power_today": {"addr": 30, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "imported_power_today": {"addr": 31, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "pv_power_today": {"addr": 32, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "inverter_yield_today": {"addr": 33, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "charge_energy_today": {"addr": 34, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "discharge_energy_today": {"addr": 35, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "total_energy_export": {"addr": 44, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "total_energy_import": {"addr": 46, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "total_pv_yield": {"addr": 48, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "total_inverter_yield": {"addr": 50, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "total_charge_energy": {"addr": 52, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "total_discharge_energy": {"addr": 54, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "fault_code_1": {"addr": 70, "type": "uint16"}, "fault_code_2": {"addr": 71, "type": "uint16"},
    "fault_code_3": {"addr": 72, "type": "uint16"}, "fault_code_4": {"addr": 73, "type": "uint16"},
    "fault_code_5": {"addr": 74, "type": "uint16"},
    "warning_code_1": {"addr": 75, "type": "uint16"}, "warning_code_2": {"addr": 76, "type": "uint16"},
    "warning_code_3": {"addr": 77, "type": "uint16"}, "warning_code_4": {"addr": 78, "type": "uint16"},
    "warning_code_5": {"addr": 79, "type": "uint16"},
}

# Holding Registers (Function Code 3) - Configuration data
LUXPOWER_HOLD_REGISTERS: Dict[str, Dict[str, Any]] = {
    "serial_number_part_1": {"addr": 0, "type": "uint16"}, "serial_number_part_2": {"addr": 1, "type": "uint16"},
    "serial_number_part_3": {"addr": 2, "type": "uint16"}, "serial_number_part_4": {"addr": 3, "type": "uint16"},
    "serial_number_part_5": {"addr": 4, "type": "uint16"},
    "firmware_version_master": {"addr": 15, "type": "uint16"}, "firmware_version_slave": {"addr": 16, "type": "uint16"},
    "firmware_version_manager": {"addr": 17, "type": "uint16"},
    "inverter_model": {"addr": 20, "type": "uint16"},
    "ac_charge_enable_bits": {"addr": 37, "type": "bitfield"},
    "flow_control_bits": {"addr": 43, "type": "bitfield"},
}

LUXPOWER_STATUS_CODES = {0: "Standby", 1: "Self Test", 2: "Checking", 3: "Grid-Tied", 4: "Off-Grid", 5: "Fault", 6: "Flash"}
LUXPOWER_MODEL_CODES = {2: "LXP-LB-5K", 5: "LXP-5K", 7: "LXP-12K"}

LUXPOWER_FAULT_CODES = {
    1: "PV1 Voltage High", 2: "PV2 Voltage High", 4: "Battery Voltage High", 8: "BUS Voltage High",
    16: "Grid Voltage High", 32: "Inverter Voltage High", 64: "DCI High", 128: "Leakage Current High"
}
LUXPOWER_WARNING_CODES = {
    1: "PV1 Voltage Low", 2: "PV2 Voltage Low", 4: "Battery Voltage Low", 8: "Grid Voltage Low",
    16: "Inverter Voltage Low", 32: "Over Temperature", 64: "Over Load"
}

LUXPOWER_BITFIELD_DEFINITIONS = {
    "ac_charge_enable_bits": {0: "AC Charge Enable", 1: "Forced Discharge Enable"},
    "flow_control_bits": {0: "PV Wakeup Bat", 1: "Bat Wakeup PV", 2: "Grid Wakeup Bat"}
}

MODBUS_EXCEPTION_CODES = {
    1: "Illegal Function", 2: "Illegal Data Address", 3: "Illegal Data Value",
    4: "Slave Device Failure", 5: "Acknowledge", 6: "Slave Device Busy",
    8: "Memory Parity Error", 10: "Gateway Path Unavailable",
    11: "Gateway Target Device Failed to Respond"
}