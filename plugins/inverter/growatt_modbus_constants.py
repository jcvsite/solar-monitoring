# plugins/inverter/growatt_modbus_constants.py
"""
Growatt Modbus Constants and Register Definitions

This module contains comprehensive constant definitions for Growatt hybrid inverters using
the Modbus RTU Protocol V1.24 (2020 edition). It includes all register maps, status codes,
fault codes, and configuration parameters needed to communicate with Growatt inverter models.

Features:
- Complete V1.24 protocol implementation (42+ input registers, 35+ holding registers)
- Input registers for real-time operational, energy, and BMS data
- Holding registers for configuration, enable bits, power rates, and battery settings
- 3-phase system support for applicable models
- Storage/hybrid inverter support (MIX/SPH series)
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- Comprehensive fault and warning code processing
- Battery management system integration
- Configuration parameter access (writable registers)

Supported Models:
- Growatt MIC series (grid-tie inverters)
- Growatt MIX series (hybrid inverters)
- Growatt SPH series (storage inverters)
- Compatible Growatt inverter models with V1.24 protocol

Register Categories:
- GROWATT_INPUT_REGISTERS: Real-time operational data (FC04)
- GROWATT_HOLD_REGISTERS: Configuration and control parameters (FC03/FC06)
- GROWATT_STATUS_CODES: Inverter status interpretations
- GROWATT_STORAGE_WORK_MODES: Storage system work mode codes
- GROWATT_FAULT_CODES: Fault code mappings for diagnostics
- GROWATT_WARNING_CODES: Warning code mappings for maintenance alerts

Protocol Features:
- Complete PV monitoring (both strings with voltage, current, power)
- Full 3-phase grid support (L1, L2, L3 phases)
- Extensive energy counters (today/total for all categories)
- Battery management (SOC, voltage, power, temperature)
- House load monitoring and power flow analysis
- Configuration access (battery settings, work modes, time schedules)

Protocol Reference: Growatt Modbus RTU Protocol V1.24 (2020 edition)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

from typing import Dict, Any

# -----------------------
# Input Registers (FC04)
# -----------------------
# All registers from input_registry_map.csv: Status, PV, grid, output, energy, temperatures, and storage/BMS specifics.

GROWATT_INPUT_REGISTERS: Dict[str, Dict[str, Any]] = {
    "inverter_status": {"addr": 0, "type": "uint16", "desc": "Inverter run state (0: Waiting, 1: Normal, 3: Fault)"},
    "pv1_voltage": {"addr": 3, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "PV1 voltage"},
    "pv1_current": {"addr": 4, "type": "uint16", "scale": 0.1, "unit": "A", "desc": "PV1 current"},
    "pv1_power": {"addr": 5, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "PV1 input power"},
    "pv2_voltage": {"addr": 7, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "PV2 voltage"},
    "pv2_current": {"addr": 8, "type": "uint16", "scale": 0.1, "unit": "A", "desc": "PV2 current"},
    "pv2_power": {"addr": 9, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "PV2 input power"},
    "output_power": {"addr": 35, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "Total output power (active)"},
    "grid_frequency": {"addr": 37, "type": "uint16", "scale": 0.01, "unit": "Hz", "desc": "Grid frequency"},
    "grid_l1_voltage": {"addr": 38, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Phase 1 voltage to grid"},
    "grid_l1_current": {"addr": 39, "type": "uint16", "scale": 0.1, "unit": "A", "desc": "Phase 1 current to grid"},
    "grid_l1_power": {"addr": 40, "type": "int32", "scale": 0.1, "unit": "W", "desc": "Phase 1 active power to grid"},
    "grid_l2_voltage": {"addr": 42, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Phase 2 voltage to grid (3-phase)"},
    "grid_l2_current": {"addr": 43, "type": "uint16", "scale": 0.1, "unit": "A", "desc": "Phase 2 current to grid (3-phase)"},
    "grid_l2_power": {"addr": 44, "type": "int32", "scale": 0.1, "unit": "W", "desc": "Phase 2 active power to grid (3-phase)"},
    "grid_l3_voltage": {"addr": 46, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Phase 3 voltage to grid (3-phase)"},
    "grid_l3_current": {"addr": 47, "type": "uint16", "scale": 0.1, "unit": "A", "desc": "Phase 3 current to grid (3-phase)"},
    "grid_l3_power": {"addr": 48, "type": "int32", "scale": 0.1, "unit": "W", "desc": "Phase 3 active power to grid (3-phase)"},
    "today_pv_energy": {"addr": 53, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "PV energy today"},
    "total_pv_energy": {"addr": 91, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "PV energy total"},
    "inverter_temperature": {"addr": 93, "type": "int16", "scale": 0.1, "unit": "°C", "desc": "Inverter temperature"},
    "system_work_state": {"addr": 1000, "type": "uint16", "desc": "System work mode storage"},
    "battery_discharge_power": {"addr": 1009, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "Battery discharge power"},
    "battery_charge_power": {"addr": 1011, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "Battery charge power"},
    "battery_voltage": {"addr": 1013, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery voltage"},
    "battery_soc": {"addr": 1014, "type": "uint16", "unit": "%", "desc": "Battery SOC"},
    "house_load_power": {"addr": 1016, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "House load power"},
    "power_to_user": {"addr": 1021, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "AC power to user total"},
    "power_to_grid": {"addr": 1029, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "AC power to grid total"},
    "local_load_power": {"addr": 1037, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "Local load power"},
    "battery_temperature": {"addr": 1040, "type": "int16", "scale": 0.1, "unit": "°C", "desc": "Battery temperature"},
    "today_energy_to_user": {"addr": 1044, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Energy to user today"},
    "today_energy_to_grid": {"addr": 1048, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Energy to grid today"},
    "today_battery_discharge_energy": {"addr": 1052, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Battery discharge energy today"},
    "today_battery_charge_energy": {"addr": 1056, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Battery charge energy today"},
    "today_local_load_energy": {"addr": 1062, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Local load energy today"},
    "total_energy_to_user": {"addr": 1064, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Energy to user total"},
    "total_energy_to_grid": {"addr": 1068, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Energy to grid total"},
    "total_battery_discharge_energy": {"addr": 1072, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Battery discharge energy total"},
    "total_battery_charge_energy": {"addr": 1076, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Battery charge energy total"},
    "total_local_load_energy": {"addr": 1080, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Local load energy total"},
    "battery_power": {"addr": 1084, "type": "int32", "scale": 0.1, "unit": "W", "desc": "Battery power (positive: discharge, negative: charge)"},
    "upper_power": {"addr": 1086, "type": "uint32", "scale": 0.1, "unit": "W", "desc": "Upper (UPS) power"},
    "today_direct_consumption_from_pv": {"addr": 1088, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Direct consumption from PV today"},
    "total_direct_consumption_from_pv": {"addr": 1092, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Direct consumption from PV total"},
    "today_energy_from_grid": {"addr": 1096, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Energy from grid today"},
    "total_energy_from_grid": {"addr": 1100, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Energy from grid total"},
}

# -----------------------
# Holding Registers (FC03/FC06)
# -----------------------
# All registers from holding_registry_map.csv: Configuration, enable bits, power rates, times, voltages, battery settings, and more.

GROWATT_HOLD_REGISTERS: Dict[str, Dict[str, Any]] = {
    "inverter_on_off": {"addr": 0, "type": "uint16", "desc": "Inverter On/Off (0: Off, 1: On)", "writable": True},
    "safety_function_enable": {"addr": 1, "type": "uint16", "desc": "Safety function enable bits", "writable": True},
    "active_power_rate": {"addr": 3, "type": "uint16", "scale": 0.1, "unit": "%", "desc": "Active power rate (10-100%)", "writable": True},
    "reactive_power_rate": {"addr": 4, "type": "int16", "scale": 0.1, "unit": "%", "desc": "Reactive power rate (-100 to 100%)", "writable": True},
    "power_factor": {"addr": 5, "type": "int16", "scale": 0.001, "desc": "Power factor (-999 to 1000)", "writable": True},
    "shadow_mppt_enable": {"addr": 6, "type": "uint16", "desc": "Shadow MPPT for PV (0: Disable, 1: Enable)", "writable": True},
    "grid_first_start_time": {"addr": 7, "type": "uint16", "desc": "Grid first start time (HHMM)", "writable": True},
    "grid_first_stop_time": {"addr": 8, "type": "uint16", "desc": "Grid first stop time (HHMM)", "writable": True},
    "firmware_version": {"addr": 9, "type": "string", "len": 3, "desc": "Firmware version"},
    "control_firmware_version": {"addr": 12, "type": "string", "len": 3, "desc": "Control firmware version"},
    "serial_number": {"addr": 23, "type": "string", "len": 5, "desc": "Inverter serial number"},
    "modbus_version": {"addr": 45, "type": "uint16", "scale": 0.01, "desc": "Modbus version number"},
    "meter_type": {"addr": 47, "type": "uint16", "desc": "Meter type (0: Single-phase, 1: Three-phase)"},
    "ct_type": {"addr": 48, "type": "uint16", "desc": "CT type (0: 100A/0.033V, 1: 200A/0.066V)"},
    "battery_type": {"addr": 1000, "type": "uint16", "desc": "Battery type (0: Lead-acid, 1: Lithium, 2: Other)", "writable": True},
    "ac_charge_enable": {"addr": 1001, "type": "uint16", "desc": "AC charge enable (0: Disable, 1: Enable)", "writable": True},
    "forced_charge_enable": {"addr": 1002, "type": "uint16", "desc": "Forced charge enable (0: Disable, 1: Enable)", "writable": True},
    "forced_discharge_enable": {"addr": 1003, "type": "uint16", "desc": "Forced discharge enable (0: Disable, 1: Enable)", "writable": True},
    "battery_first_serial_number": {"addr": 1125, "type": "string", "len": 8, "desc": "Battery first serial number"},
    "battery_charge_voltage": {"addr": 1204, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery charge voltage", "writable": True},
    "battery_discharge_voltage": {"addr": 1205, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery discharge cut-off voltage", "writable": True},
    "battery_charge_max_current": {"addr": 1206, "type": "uint16", "scale": 0.1, "unit": "A", "desc": "Battery charge max current", "writable": True},
    "battery_discharge_max_current": {"addr": 1207, "type": "uint16", "scale": 0.1, "unit": "A", "desc": "Battery discharge max current", "writable": True},
    "ac_charge_start_time": {"addr": 1208, "type": "uint16", "desc": "AC charge start time (HHMM)", "writable": True},
    "ac_charge_end_time": {"addr": 1209, "type": "uint16", "desc": "AC charge end time (HHMM)", "writable": True},
    "forced_charge_start_time": {"addr": 1210, "type": "uint16", "desc": "Forced charge start time (HHMM)", "writable": True},
    "forced_charge_end_time": {"addr": 1211, "type": "uint16", "desc": "Forced charge end time (HHMM)", "writable": True},
    "forced_discharge_start_time": {"addr": 1212, "type": "uint16", "desc": "Forced discharge start time (HHMM)", "writable": True},
    "forced_discharge_end_time": {"addr": 1213, "type": "uint16", "desc": "Forced discharge end time (HHMM)", "writable": True},
    "battery_soc_limit_for_grid": {"addr": 1214, "type": "uint16", "unit": "%", "desc": "Battery SOC limit for grid", "writable": True},
    "battery_soc_limit_for_load": {"addr": 1215, "type": "uint16", "unit": "%", "desc": "Battery SOC limit for load", "writable": True},
    "work_mode": {"addr": 1216, "type": "uint16", "desc": "Work mode (0: Priority load, 1: Priority battery, 2: Priority grid)", "writable": True},
    "grid_first_soc": {"addr": 1217, "type": "uint16", "unit": "%", "desc": "Grid first SOC", "writable": True},
    "battery_first_soc": {"addr": 1218, "type": "uint16", "unit": "%", "desc": "Battery first SOC", "writable": True},
    "load_first_soc": {"addr": 1219, "type": "uint16", "unit": "%", "desc": "Load first SOC", "writable": True},
    "ac_charge_power_limit": {"addr": 1220, "type": "uint16", "scale": 0.1, "unit": "kW", "desc": "AC charge power limit", "writable": True},
    "forced_discharge_power_limit": {"addr": 1221, "type": "uint16", "scale": 0.1, "unit": "kW", "desc": "Forced discharge power limit", "writable": True},
    "export_power_limit": {"addr": 1222, "type": "uint16", "scale": 0.1, "unit": "kW", "desc": "Export power limit", "writable": True},
    "external_generation_power": {"addr": 1223, "type": "uint16", "scale": 0.1, "unit": "kW", "desc": "External generation power", "writable": True},
    "max_feed_in_power": {"addr": 1224, "type": "uint16", "scale": 0.1, "unit": "kW", "desc": "Max feed-in power", "writable": True},
    "battery_low_voltage": {"addr": 1225, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery low voltage", "writable": True},
    "battery_high_voltage": {"addr": 1226, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery high voltage", "writable": True},
    # Note: Protocol V1.24 may include additional holding registers for specific models; expand as needed.
}

# --------------------
# Status Codes & Modes
# --------------------

GROWATT_STATUS_CODES = {
    0: "Waiting",
    1: "Normal",
    3: "Fault",
}

GROWATT_STORAGE_WORK_MODES = {
    0: "Waiting",
    1: "Self-test",
    2: "Reserved",
    3: "System Fault",
    4: "Flash",
    5: "PV & Battery Online",
    6: "Battery Online",
    7: "PV Offline",
    8: "Battery Offline",
}

# --------------------
# Fault and Warning Codes
# --------------------
# Derived from protocol documentation; use with inverter_status or dedicated fault registers.

GROWATT_FAULT_CODES = {
    1: "No AC Connection",
    2: "AC V Outrange",
    3: "AC F Outrange",
    4: "Module Over Temperature",
    5: "PV Isolation Low",
    6: "Output High DCI",
    7: "Residual I High",
    8: "PV Voltage High",
    9: "Auto Test Failed",
    117: "Relay Fault",
    118: "Init Model Fault",
    119: "GFCI Device Damage",
    120: "HCT Fault",
    121: "Slave Communication Failure",
    122: "Bus Voltage Fault",
    123: "Leakage Current Too High",
    124: "DC Short Circuit",
    203: "Insulation Problem",
    300: "AC Voltage Outrange",
    303: "N/PE Voltage Too High",
    405: "Firmware Version Mismatch",
    409: "Bus Over Voltage",
    411: "DSP/M3 Communication Abnormal",
}

GROWATT_WARNING_CODES = {
    400: "Fan Function Abnormal",
    403: "EEPROM Version Inconsistency",
    405: "Firmware Version Mismatch",
    408: "Grid Frequency High/Low",
    501: "Insulation Impedance Low",
}