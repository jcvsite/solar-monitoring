"""
Deye/SunSynk Modbus Constants and Register Definitions

This module contains comprehensive constant definitions for Deye and SunSynk hybrid inverters.
It includes all register maps, status codes, fault codes, and protocol constants needed
to communicate with various Deye and SunSynk inverter models via Modbus RTU/TCP.

Features:
- Complete register mapping for multiple inverter series
- BMS protocol support for battery communication
- Status code interpretations and fault diagnostics
- Modbus exception handling constants
- Support for both single-phase and three-phase systems
- Energy monitoring and configuration parameters

Supported Models:
- Modern single-phase hybrid inverters (SunSynk 5K, Deye SUN-5K-SG04LP1)
- Legacy single-phase hybrid inverters (older Deye models)
- Three-phase hybrid inverters (Deye SG01HP3 and similar)
- SunSynk ECCO series hybrid inverters

Protocol Support:
- Modbus RTU over Serial (RS485)
- Modbus TCP over Ethernet
- BMS communication protocols

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

from plugins.plugin_interface import StandardDataKeys as StdKeys

# BMS Protocol Codes - Maps numeric codes to BMS manufacturer names
BMS_PROTOCOL_CODES = {
    0: "Pylontech CAN", 1: "Sacred Sun RS485", 3: "Dyness CAN", 6: "GenixGreen RS485",
    12: "Pylon RS485", 13: "Vision CAN", 14: "Wattsonic RS485", 15: "Unipower RS485",
}

# Inverter Status Codes - Maps numeric status codes to human-readable text
STATUS_CODES = {
    0: 'Waiting', 1: 'Generating', 2: 'Fault', 3: 'Standby',
    59: {0: "Stand-by", 1: "Self-checking", 2: "Normal", 3: "FAULT"},
    3: {0: "Stand-by", 1: "Self-check", 2: "Normal", 3: "Warning", 4: "Fault"},
}

# Standard Modbus Exception Codes - Maps exception codes to descriptions
MODBUS_EXCEPTION_CODES = {
    1: "Illegal Function", 2: "Illegal Data Address", 3: "Illegal Data Value",
    4: "Slave Device Failure", 5: "Acknowledge", 6: "Slave Device Busy",
    10: "Gateway Path Unavailable", 11: "Gateway Target Device Failed to Respond",
}

# Deye-specific fault codes from official documentation
# These map bit positions in fault registers to human-readable error messages
DEYE_FAULT_CODES = {
    7: "DC/DC Softstart Fault", 10: "AuxPowerBoard Failure", 13: "Working mode change",
    18: "AC over current fault of hardware", 20: "DC over current fault of the hardware",
    22: "Emergency Stop Fault", 23: "AC leakage current transient over current",
    24: "DC insulation impedance failure", 26: "DC busbar is unbalanced",
    29: "Parallel CANBus Fault", 35: "No AC grid", 41: "Parallel system Stop",
    42: "AC line low voltage", 46: "Backup Battery Fault", 47: "AC over frequency",
    48: "AC lower frequency", 56: "DC busbar voltage is too low",
    58: "BMS communication fault", 63: "ARC fault", 64: "Heat sink high temperature failure",
}

# Deye-specific warning codes from official documentation
DEYE_WARNING_CODES = { 1: "Fan failure", 2: "Grid phase wrong" }

# === REGISTER MAPS ===
# These dictionaries define the Modbus register layouts for different Deye/Sunsynk models
# Each entry contains: address, data type, scaling factor, and metadata

# Common registers shared across all Deye/Sunsynk models
DEYE_COMMON_REGISTERS = {
    "device_serial": {"addr": 3, "type": "string", "len": 10, "static": True, "key": StdKeys.STATIC_INVERTER_SERIAL_NUMBER},
}

# Register map for modern single-phase hybrid inverters (most common)
# Includes Sunsynk 5K, Deye SUN-5K-SG04LP1, and similar models
DEYE_MODERN_HYBRID_REGISTERS = {
    "inverter_status_code": {"addr": 500, "type": "uint16"},
    "day_energy": {"addr": 514, "type": "uint16", "scale": 0.1},
    "total_energy": {"addr": 522, "type": "uint32_le", "scale": 0.1},
    "pv1_voltage": {"addr": 503, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 504, "type": "uint16", "scale": 0.1},
    "pv2_voltage": {"addr": 505, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 506, "type": "uint16", "scale": 0.1},
    "inverter_power": {"addr": 560, "type": "int16"},
    "inverter_voltage": {"addr": 534, "type": "uint16", "scale": 0.1},
    "inverter_current": {"addr": 535, "type": "uint16", "scale": 0.1},
    "grid_power": {"addr": 554, "type": "int16"},
    "grid_frequency": {"addr": 533, "type": "uint16", "scale": 0.01},
    "grid_daily_buy": {"addr": 526, "type": "uint16", "scale": 0.1},
    "grid_daily_sell": {"addr": 527, "type": "uint16", "scale": 0.1},
    "load_power": {"addr": 570, "type": "int16"},
    "battery_soc": {"addr": 586, "type": "uint16"},
    "battery_power": {"addr": 582, "type": "int16"},
    "battery_voltage": {"addr": 578, "type": "uint16", "scale": 0.1},
    "battery_current": {"addr": 579, "type": "int16", "scale": 0.1},
    "battery_temperature": {"addr": 182, "type": "int16", "scale": 0.1},
    "battery_daily_charge": {"addr": 528, "type": "uint16", "scale": 0.1},
    "battery_daily_discharge": {"addr": 529, "type": "uint16", "scale": 0.1},
    "radiator_temp": {"addr": 540, "type": "int16", "scale": 0.1, "offset": -100},
    "generator_power": {"addr": 166, "type": "int16"},
    "bms_protocol_code": {"addr": 325, "type": "uint16"},
}

# Register map for older single-phase Deye hybrid inverters
# These models use a different register layout than modern versions
DEYE_LEGACY_HYBRID_REGISTERS = {
    "pv1_power": {"addr": 186, "type": "uint16", "unit": "W"},
    "pv2_power": {"addr": 187, "type": "uint16", "unit": "W"},
    "pv1_voltage": {"addr": 109, "type": "uint16", "scale": 0.1, "unit": "V"},
    "pv2_voltage": {"addr": 111, "type": "uint16", "scale": 0.1, "unit": "V"},
    "pv1_current": {"addr": 110, "type": "uint16", "scale": 0.1, "unit": "A"},
    "pv2_current": {"addr": 112, "type": "uint16", "scale": 0.1, "unit": "A"},
    "day_energy": {"addr": 108, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "total_energy": {"addr": 96, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "total_battery_charge": {"addr": 72, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "total_battery_discharge": {"addr": 74, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "daily_battery_charge": {"addr": 70, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "daily_battery_discharge": {"addr": 71, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "battery_status": {"addr": 189, "type": "uint16"},
    "battery_power": {"addr": 190, "type": "int16", "unit": "W"},
    "battery_voltage": {"addr": 183, "type": "uint16", "scale": 0.01, "unit": "V"},
    "battery_soc": {"addr": 184, "type": "uint16", "unit": "%"},
    "battery_current": {"addr": 191, "type": "int16", "scale": 0.01, "unit": "A"},
    "battery_temperature": {"addr": 182, "type": "int16", "scale": 0.1, "offset": -100, "unit": "°C"},
    "grid_power": {"addr": 169, "type": "int16", "unit": "W"},
    "grid_voltage_l1": {"addr": 150, "type": "uint16", "scale": 0.1, "unit": "V"},
    "grid_current_l1": {"addr": 160, "type": "uint16", "scale": 0.01, "unit": "A"},
    "grid_daily_buy": {"addr": 76, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "total_grid_buy": {"addr": 78, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "grid_daily_sell": {"addr": 77, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "total_grid_sell": {"addr": 81, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "load_power": {"addr": 178, "type": "uint16", "unit": "W"},
    "daily_load_consumption": {"addr": 84, "type": "uint16", "scale": 0.1, "unit": "kWh"},
    "total_load_consumption": {"addr": 85, "type": "uint32", "scale": 0.1, "unit": "kWh"},
    "inverter_status_code": {"addr": 59, "type": "uint16"},
    "inverter_power": {"addr": 175, "type": "int16", "unit": "W"},
    "grid_frequency": {"addr": 79, "type": "uint16", "scale": 0.01, "unit": "Hz"},
    "dc_temperature": {"addr": 90, "type": "int16", "scale": 0.1, "offset": -100, "unit": "°C"},
    "ac_temperature": {"addr": 91, "type": "int16", "scale": 0.1, "offset": -100, "unit": "°C"},
}

# Register map for three-phase hybrid inverters
# Includes Deye SG01HP3 and similar three-phase models
DEYE_THREE_PHASE_REGISTERS = {
    "inverter_status_code": {"addr": 640, "type": "uint16"},
    "day_energy": {"addr": 70, "type": "uint16", "scale": 0.1},
    "total_energy": {"addr": 72, "type": "uint32_le", "scale": 0.1},
    "pv1_voltage": {"addr": 678, "type": "uint16", "scale": 0.1},
    "pv1_current": {"addr": 680, "type": "uint16", "scale": 0.1},
    "pv1_power": {"addr": 672, "type": "uint16"},
    "pv2_voltage": {"addr": 679, "type": "uint16", "scale": 0.1},
    "pv2_current": {"addr": 681, "type": "uint16", "scale": 0.1},
    "pv2_power": {"addr": 673, "type": "uint16"},
    "inverter_power": {"addr": 676, "type": "uint32_le"},
    "inverter_voltage": {"addr": 687, "type": "uint16", "scale": 0.1},
    "inverter_current": {"addr": 690, "type": "uint16", "scale": 0.1},
    "grid_power": {"addr": 796, "type": "int32_le"},
    "grid_daily_buy": {"addr": 85, "type": "uint16", "scale": 0.1},
    "grid_daily_sell": {"addr": 87, "type": "uint16", "scale": 0.1},
    "load_power": {"addr": 798, "type": "int32_le"},
    "battery_soc": {"addr": 778, "type": "uint16"},
    "battery_charge_power": {"addr": 809, "type": "uint16"},
    "battery_discharge_power": {"addr": 810, "type": "uint16"},
    "battery_voltage": {"addr": 776, "type": "uint16", "scale": 0.1},
    "battery_current": {"addr": 777, "type": "int16", "scale": 0.1},
    "battery_temperature": {"addr": 781, "type": "int16", "scale": 0.1, "offset": -100},
    "battery_daily_charge": {"addr": 81, "type": "uint16", "scale": 0.1},
    "battery_daily_discharge": {"addr": 83, "type": "uint16", "scale": 0.1},
    "radiator_temp": {"addr": 712, "type": "int16", "scale": 0.1, "offset": -100},
}

# Combined register map containing all possible registers across all models
# Used for validation and comprehensive register lookup
ALL_DEYE_REGISTERS = {
    **DEYE_COMMON_REGISTERS,
    **DEYE_MODERN_HYBRID_REGISTERS,
    **DEYE_LEGACY_HYBRID_REGISTERS,
    **DEYE_THREE_PHASE_REGISTERS
}
