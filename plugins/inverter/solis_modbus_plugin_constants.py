# plugins/inverter/solis_modbus_plugin_constants.py
"""
Solis Modbus Constants and Register Definitions

This module contains comprehensive constant definitions for Solis hybrid inverters using
the Modbus RTU/TCP protocol. It includes all register maps, status codes, fault bitfields,
and configuration parameters needed to communicate with Solis inverter models.

Features:
- Complete register mapping for operational and configuration data
- Input registers for real-time monitoring data
- Holding registers for configuration and static information
- Comprehensive fault and warning bitfield processing
- Battery management system integration
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- Inverter model and battery model code interpretations
- Modbus exception handling constants

Supported Models:
- Solis S5 series (hybrid inverters)
- Solis S6 series (hybrid inverters)
- Solis RHI series (residential hybrid inverters)
- Compatible Solis hybrid inverter models

Register Categories:
- SOLIS_REGISTERS: Complete register mapping for operational and configuration data
- SOLIS_INVERTER_STATUS_CODES: Inverter status interpretations
- SOLIS_FAULT_BITFIELD_MAPS: Fault and warning bitfield processing
- SOLIS_INVERTER_MODEL_CODES: Inverter model code interpretations
- BATTERY_MODEL_CODES: Battery model code interpretations
- MODBUS_EXCEPTION_CODES: Modbus exception handling constants

Protocol Features:
- Complete register mapping for operational and configuration data
- Battery management system integration
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- Comprehensive fault and warning bitfield processing
- Inverter model and battery model code interpretations

Protocol Features:
- Real-time monitoring of PV generation, battery status, and grid interaction
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- Comprehensive fault and warning code processing
- Battery management system integration
- Configuration parameter access
- Support for multiple polling priorities (critical, normal, low)

Protocol Reference: Solis Modbus RTU/TCP Protocol
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from typing import Any, Dict, List

# --- Solis Register Definitions ---
SOLIS_REGISTERS: Dict[str, Dict[str, Any]] = {
    "model_number": {"key": "model_number", "addr": 33000, "type": "uint16", "scale": 1, "unit": "Code", "static": True},
    "dsp_version": {"key": "dsp_version", "addr": 33001, "type": "uint16", "scale": 1, "unit": "Hex", "static": True},
    "hmi_version": {"key": "hmi_version", "addr": 33002, "type": "uint16", "scale": 1, "unit": "Hex", "static": True},
    "protocol_version": {"key": "protocol_version", "addr": 33003, "type": "uint16", "scale": 1, "unit": "Hex", "static": True},
    "serial_number": {"key": "serial_number", "addr": 33004, "type": "string_read8", "scale": 1, "unit": None, "static": True},
    "current_battery_model": {"key": "current_battery_model", "addr": 33160, "type": "uint16", "scale": 1, "unit": "Code", "static": True},

    # --- Dynamic Input Registers (Read Periodically) ---
    "year": {"key": "year", "addr": 33022, "type": "uint16", "scale": 1, "unit": None, "poll_priority": "critical"},
    "month": {"key": "month", "addr": 33023, "type": "uint16", "scale": 1, "unit": None, "poll_priority": "critical"},
    "day": {"key": "day", "addr": 33024, "type": "uint16", "scale": 1, "unit": None, "poll_priority": "critical"},
    "hour": {"key": "hour", "addr": 33025, "type": "uint16", "scale": 1, "unit": None, "poll_priority": "critical"},
    "minute": {"key": "minute", "addr": 33026, "type": "uint16", "scale": 1, "unit": None, "poll_priority": "critical"},
    "second": {"key": "second", "addr": 33027, "type": "uint16", "scale": 1, "unit": None, "poll_priority": "critical"},
    "energy_total": {"key": "energy_total", "addr": 33029, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "energy_this_month": {"key": "energy_this_month", "addr": 33031, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "energy_last_month": {"key": "energy_last_month", "addr": 33033, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "energy_today": {"key": "energy_today", "addr": 33035, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "energy_yesterday": {"key": "energy_yesterday", "addr": 33036, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "energy_this_year": {"key": "energy_this_year", "addr": 33037, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "energy_last_year": {"key": "energy_last_year", "addr": 33039, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "dc_voltage_1": {"key": "dc_voltage_1", "addr": 33049, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "dc_current_1": {"key": "dc_current_1", "addr": 33050, "type": "uint16", "scale": 0.1, "unit": "A", "poll_priority": "critical"},
    "dc_voltage_2": {"key": "dc_voltage_2", "addr": 33051, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "dc_current_2": {"key": "dc_current_2", "addr": 33052, "type": "uint16", "scale": 0.1, "unit": "A", "poll_priority": "critical"},
    "dc_voltage_3": {"key": "dc_voltage_3", "addr": 33053, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "dc_current_3": {"key": "dc_current_3", "addr": 33054, "type": "uint16", "scale": 0.1, "unit": "A", "poll_priority": "critical"},
    "dc_voltage_4": {"key": "dc_voltage_4", "addr": 33055, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "dc_current_4": {"key": "dc_current_4", "addr": 33056, "type": "uint16", "scale": 0.1, "unit": "A", "poll_priority": "critical"},
    "total_dc_power": {"key": "total_dc_power", "addr": 33057, "type": "uint32", "scale": 1, "unit": "W", "poll_priority": "critical"},
    "dc_bus_voltage": {"key": "dc_bus_voltage", "addr": 33071, "type": "uint16", "scale": 0.1, "unit": "V"},
    "dc_bus_half_voltage": {"key": "dc_bus_half_voltage", "addr": 33072, "type": "uint16", "scale": 0.1, "unit": "V"},
    "grid_voltage_l1": {"key": "grid_voltage_l1", "addr": 33073, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "grid_voltage_l2": {"key": "grid_voltage_l2", "addr": 33074, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "grid_voltage_l3": {"key": "grid_voltage_l3", "addr": 33075, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "grid_current_l1": {"key": "grid_current_l1", "addr": 33076, "type": "uint16", "scale": 0.1, "unit": "A", "poll_priority": "critical"},
    "grid_current_l2": {"key": "grid_current_l2", "addr": 33077, "type": "uint16", "scale": 0.1, "unit": "A", "poll_priority": "critical"},
    "grid_current_l3": {"key": "grid_current_l3", "addr": 33078, "type": "uint16", "scale": 0.1, "unit": "A", "poll_priority": "critical"},
    "active_power": {"key": "active_power", "addr": 33079, "type": "int32", "scale": 1, "unit": "W", "poll_priority": "critical"},
    "reactive_power": {"key": "reactive_power", "addr": 33081, "type": "int32", "scale": 1, "unit": "Var"},
    "apparent_power": {"key": "apparent_power", "addr": 33083, "type": "int32", "scale": 1, "unit": "VA"},
    "grid_frequency": {"key": "grid_frequency", "addr": 33094, "type": "uint16", "scale": 0.01, "unit": "Hz"},
    "working_mode": {"key": "working_mode", "addr": 33091, "type": "uint16", "scale": 1, "unit": "Code"},
    "grid_standard": {"key": "grid_standard", "addr": 33092, "type": "uint16", "scale": 1, "unit": "Code"},
    "inverter_temp": {"key": "inverter_temp", "addr": 33093, "type": "int16", "scale": 0.1, "unit": "°C", "poll_priority": "critical"},
    "current_status": {"key": "current_status", "addr": 33095, "type": "uint16", "scale": 1, "unit": "Code", "poll_priority": "critical"},
    "lead_acid_temp": {"key": "lead_acid_temp", "addr": 33096, "type": "int16", "scale": 0.1, "unit": "°C"},
    "llc_bus_voltage": {"key": "llc_bus_voltage", "addr": 33136, "type": "uint16", "scale": 0.1, "unit": "V"},
    "fault_status_01": {"key": "fault_status_01", "addr": 33116, "type": "uint16", "scale": 1, "unit": "Bitfield", "poll_priority": "critical"}, # Grid Faults
    "fault_status_02": {"key": "fault_status_02", "addr": 33117, "type": "uint16", "scale": 1, "unit": "Bitfield", "poll_priority": "critical"}, # EPS Faults
    "fault_status_03": {"key": "fault_status_03", "addr": 33118, "type": "uint16", "scale": 1, "unit": "Bitfield", "poll_priority": "critical"}, # Battery Faults
    "fault_status_04": {"key": "fault_status_04", "addr": 33119, "type": "uint16", "scale": 1, "unit": "Bitfield", "poll_priority": "critical"}, # Inverter DC Faults
    "fault_status_05": {"key": "fault_status_05", "addr": 33120, "type": "uint16", "scale": 1, "unit": "Bitfield", "poll_priority": "critical"}, # Inverter AC Faults
    "working_status": {"key": "working_status", "addr": 33121, "type": "uint16", "scale": 1, "unit": "Bitfield", "poll_priority": "critical"}, # Operational Flags
    "battery_failure_01": {"key": "battery_failure_01", "addr": 33145, "type": "uint16", "scale": 1, "unit": "Bitfield", "poll_priority": "critical"}, # BMS Faults 1
    "battery_failure_02": {"key": "battery_failure_02", "addr": 33146, "type": "uint16", "scale": 1, "unit": "Bitfield", "poll_priority": "critical"}, # BMS Faults 2
    "meter_voltage": {"key": "meter_voltage", "addr": 33128, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "meter_current": {"key": "meter_current", "addr": 33129, "type": "uint16", "scale": 0.01, "unit": "A", "poll_priority": "critical"},
    "meter_active_power": {"key": "meter_active_power", "addr": 33130, "type": "int32", "scale": 1, "unit": "W", "poll_priority": "critical"},
    "energy_storage_mode": {"key": "energy_storage_mode", "addr": 33132, "type": "uint16", "scale": 1, "unit": "Code"},
    "battery_voltage": {"key": "battery_voltage", "addr": 33133, "type": "uint16", "scale": 0.1, "unit": "V", "poll_priority": "critical"},
    "battery_current": {"key": "battery_current", "addr": 33134, "type": "int16", "scale": 0.1, "unit": "A", "poll_priority": "critical"},
    "battery_direction": {"key": "battery_direction", "addr": 33135, "type": "uint16", "scale": 1, "unit": "Code", "poll_priority": "critical"}, # 0=Charge, 1=Discharge
    "battery_soc": {"key": "battery_soc", "addr": 33139, "type": "uint16", "scale": 1, "unit": "%", "poll_priority": "critical"},
    "battery_soh": {"key": "battery_soh", "addr": 33140, "type": "uint16", "scale": 1, "unit": "%"},
    "battery_power": {"key": "battery_power", "addr": 33149, "type": "int32", "scale": 1, "unit": "W", "poll_priority": "critical"},
    "battery_detected": {"key": "battery_detected", "addr": 33159, "type": "uint16", "scale": 1, "unit": "Code"}, # 0=No, 1=Yes
    "battery_charge_current_limit_status": {"key": "battery_charge_current_limit_status", "addr": 33206, "type": "uint16", "scale": 0.1, "unit": "A"},
    "battery_discharge_current_limit_status": {"key": "battery_discharge_current_limit_status", "addr": 33207, "type": "uint16", "scale": 0.1, "unit": "A"},
    "bms_voltage": {"key": "bms_voltage", "addr": 33141, "type": "uint16", "scale": 0.01, "unit": "V"},
    "bms_current": {"key": "bms_current", "addr": 33142, "type": "int16", "scale": 0.01, "unit": "A"},
    "bms_charge_limit": {"key": "bms_charge_limit", "addr": 33143, "type": "uint16", "scale": 0.1, "unit": "A"},
    "bms_discharge_limit": {"key": "bms_discharge_limit", "addr": 33144, "type": "uint16", "scale": 0.1, "unit": "A"},
    "house_load_power": {"key": "house_load_power", "addr": 33147, "type": "uint16", "scale": 1, "unit": "W", "poll_priority": "critical"},
    "backup_load_power": {"key": "backup_load_power", "addr": 33148, "type": "uint16", "scale": 1, "unit": "W", "poll_priority": "critical"},
    "inverter_ac_grid_power": {"key": "inverter_ac_grid_power", "addr": 33151, "type": "int32", "scale": 1, "unit": "W"},
    "backup_voltage_l1": {"key": "backup_voltage_l1", "addr": 33137, "type": "uint16", "scale": 0.1, "unit": "V"},
    "backup_current_l1": {"key": "backup_current_l1", "addr": 33138, "type": "uint16", "scale": 0.1, "unit": "A"},
    "backup_voltage_l2": {"key": "backup_voltage_l2", "addr": 33153, "type": "uint16", "scale": 0.1, "unit": "V"},
    "backup_current_l2": {"key": "backup_current_l2", "addr": 33154, "type": "uint16", "scale": 0.1, "unit": "A"},
    "backup_voltage_l3": {"key": "backup_voltage_l3", "addr": 33155, "type": "uint16", "scale": 0.1, "unit": "V"},
    "backup_current_l3": {"key": "backup_current_l3", "addr": 33156, "type": "uint16", "scale": 0.1, "unit": "A"},
    "battery_charge_total": {"key": "battery_charge_total", "addr": 33161, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "battery_charge_today": {"key": "battery_charge_today", "addr": 33163, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "battery_charge_yesterday": {"key": "battery_charge_yesterday", "addr": 33164, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "battery_discharge_total": {"key": "battery_discharge_total", "addr": 33165, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "battery_discharge_today": {"key": "battery_discharge_today", "addr": 33167, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "battery_discharge_yesterday": {"key": "battery_discharge_yesterday", "addr": 33168, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "grid_import_total": {"key": "grid_import_total", "addr": 33169, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "grid_import_today": {"key": "grid_import_today", "addr": 33171, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "grid_import_yesterday": {"key": "grid_import_yesterday", "addr": 33172, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "grid_export_total": {"key": "grid_export_total", "addr": 33173, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "grid_export_today": {"key": "grid_export_today", "addr": 33175, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "grid_export_yesterday": {"key": "grid_export_yesterday", "addr": 33176, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "load_total_energy": {"key": "load_total_energy", "addr": 33177, "type": "uint32", "scale": 1, "unit": "kWh","poll_priority": "summary"},
    "load_today_energy": {"key": "load_today_energy", "addr": 33179, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "house_load_yesterday": {"key": "house_load_yesterday", "addr": 33180, "type": "uint16", "scale": 0.1, "unit": "kWh","poll_priority": "summary"},
    "meter_ac_voltage_l1": {"key": "meter_ac_voltage_l1", "addr": 33251, "type": "uint16", "scale": 0.1, "unit": "V"},
    "meter_ac_current_l1": {"key": "meter_ac_current_l1", "addr": 33252, "type": "uint16", "scale": 0.01, "unit": "A"},
    "meter_ac_voltage_l2": {"key": "meter_ac_voltage_l2", "addr": 33253, "type": "uint16", "scale": 0.1, "unit": "V"},
    "meter_ac_current_l2": {"key": "meter_ac_current_l2", "addr": 33254, "type": "uint16", "scale": 0.01, "unit": "A"},
    "meter_ac_voltage_l3": {"key": "meter_ac_voltage_l3", "addr": 33255, "type": "uint16", "scale": 0.1, "unit": "V"},
    "meter_ac_current_l3": {"key": "meter_ac_current_l3", "addr": 33256, "type": "uint16", "scale": 0.01, "unit": "A"},
    "meter_active_power_l1": {"key": "meter_active_power_l1", "addr": 33257, "type": "int32", "scale": 0.001, "unit": "kW"},
    "meter_active_power_l2": {"key": "meter_active_power_l2", "addr": 33259, "type": "int32", "scale": 0.001, "unit": "kW"},
    "meter_active_power_l3": {"key": "meter_active_power_l3", "addr": 33261, "type": "int32", "scale": 0.001, "unit": "kW"},
    "meter_active_power_total": {"key": "meter_active_power_total", "addr": 33263, "type": "int32", "scale": 0.001, "unit": "kW", "poll_priority": "critical"},
    "meter_reactive_power_l1": {"key": "meter_reactive_power_l1", "addr": 33265, "type": "int32", "scale": 1, "unit": "Var"},
    "meter_reactive_power_l2": {"key": "meter_reactive_power_l2", "addr": 33267, "type": "int32", "scale": 1, "unit": "Var"},
    "meter_reactive_power_l3": {"key": "meter_reactive_power_l3", "addr": 33269, "type": "int32", "scale": 1, "unit": "Var"},
    "meter_reactive_power_total": {"key": "meter_reactive_power_total", "addr": 33271, "type": "int32", "scale": 1, "unit": "Var"},
    "meter_apparent_power_l1": {"key": "meter_apparent_power_l1", "addr": 33273, "type": "int32", "scale": 1, "unit": "VA"},
    "meter_apparent_power_l2": {"key": "meter_apparent_power_l2", "addr": 33275, "type": "int32", "scale": 1, "unit": "VA"},
    "meter_apparent_power_l3": {"key": "meter_apparent_power_l3", "addr": 33277, "type": "int32", "scale": 1, "unit": "VA"},
    "meter_apparent_power_total": {"key": "meter_apparent_power_total", "addr": 33279, "type": "int32", "scale": 1, "unit": "VA"},
    "meter_power_factor": {"key": "meter_power_factor", "addr": 33281, "type": "int16", "scale": 0.001, "unit": None},
    "meter_grid_frequency": {"key": "meter_grid_frequency", "addr": 33282, "type": "uint16", "scale": 0.01, "unit": "Hz"},
    "meter_grid_import_total": {"key": "meter_grid_import_total", "addr": 33283, "type": "uint32", "scale": 0.01, "unit": "kWh","poll_priority": "summary"},
    "meter_grid_export_total": {"key": "meter_grid_export_total", "addr": 33285, "type": "uint32", "scale": 0.01, "unit": "kWh","poll_priority": "summary"},
}

# --- Solis Status and Code Mappings ---
SOLIS_INVERTER_STATUS_CODES: Dict[int, str] = {
    0: "Waiting", 1: "Open Loop Operation", 2: "Soft Start", 3: "Generating", 4: "Grid Bypass",
    5: "Grid Sync", 6: "Grid Bypass", 7: "Standby", 8: "Derating", 10: "Auto Test",
    12: "Parameter Setting", 13: "Firmware Updating", 14: "Timed Charge",
    15: "Generating", 16: "Timed Discharge",
    4096: "Stop", 4100: "Grid Off", 4111: "Islanding Fault", 4112: "Grid Overvoltage",
    4113: "Grid Undervoltage", 4114: "Grid Overfrequency", 4115: "Grid Underfrequency",
    4116: "Grid Reverse Current", 4117: "No Grid", 4118: "Grid Unbalanced",
    4119: "Grid Freq Fluctuation", 4120: "Grid Overcurrent", 4121: "Grid Current Sampling Error",
    4128: "DC Overvoltage", 4129: "DC Bus Overvoltage", 4130: "DC Bus Unbalanced",
    4131: "DC Bus Undervoltage", 4132: "DC Bus Unbalanced 2", 4133: "DC(A) Overcurrent",
    4134: "DC(B) Overcurrent", 4135: "DC Interference", 4136: "DC Reverse Polarity",
    4137: "PV Midpoint Grounding", 4144: "Grid Interference Protection",
    4145: "DSP Init Protection", 4146: "Over Temperature", 4147: "PV Insulation Fault",
    4148: "Leakage Current Fault", 4149: "Relay Check Protection", 4150: "DSP_B Protection",
    4151: "DC Injection Protection", 4152: "12V Undervoltage Faulty",
    4153: "Leakage Current Check Protection", 4154: "Under Temperature",
    4160: "AFCI Check Fault", 4161: "AFCI Fault", 4162: "DSP SRAM Fault",
    4163: "DSP FLASH Fault", 4164: "DSP PC Pointer Fault", 4165: "DSP Register Fault",
    4166: "Grid Interference Protection 02", 4167: "Grid Current Sampling Error",
    4168: "IGBT Overcurrent", 4176: "Grid Transient Overcurrent",
    4177: "Battery Hardware Overvoltage", 4178: "LLC Hardware Overcurrent",
    4179: "Battery Overvoltage", 4180: "Battery Undervoltage",
    4181: "Battery Not Connected", 4182: "Backup Overvoltage", 4183: "Backup Overload",
    4184: "DSP Selfcheck Error", 4192: "Battery Force Charging", 4193: "Battery Force Discharging",
    61456: "Grid Surge", 61457: "Fan Fault",
    8208: "Fail Safe", 8209: "Meter Comm Fail", 8210: "Battery Comm Fail (BMS)",
    8211: "BMS Firmware Updating", 8212: "DSP COM Fail", 8213: "BMS Alarm",
    8214: "BatName-FAIL", 8215: "BMS Alarm 2", 8216: "DRM Connect Fail", 8217: "Meter Select Fail",
    8224: "Lead-acid Battery High Temp", 8225: "Lead-acid Battery Low Temp"
}
SOLIS_FAULT_BITFIELD_MAPS: Dict[int, Dict[str, Any]] = {
    33116: {"category": "grid", "bits": {
        0: "No Grid", 1: "Grid Overvoltage", 2: "Grid Undervoltage", 3: "Grid Overfrequency",
        4: "Grid Underfrequency", 5: "Grid Imbalance", 6: "Grid Frequency Jitter",
        7: "Grid Impedance Too Large", 8: "Grid Current Tracking Fault",
        9: "METER Communication Failed", 10: "FailSafe", 11: "Grid Voltage Sample Exception" }},
    33117: {"category": "eps", "bits": {
        0: "EPS Overvoltage Fault", 1: "EPS Overload Fault" }},
    33118: {"category": "battery", "bits": {
        0: "Battery Not Connected", 1: "Battery Overvoltage Detection", 2: "Battery Undervoltage Detection" }},
    33119: {"category": "inverter", "bits": {
        0: "DC Overvoltage", 1: "DC Bus Overvoltage", 2: "DC Busbar Uneven Voltage",
        3: "DC Bus Undervoltage", 4: "DC Busbar Uneven Voltage 2", 5: "DC A Path Overcurrent",
        6: "DC B Path Overcurrent", 7: "DC Input Disturbance", 8: "Grid Overcurrent",
        9: "IGBT Overcurrent", 10: "Grid Disturbance 02", 11: "Arc Self-test Protection",
        12: "Arc Fault Reservation", 13: "Grid Current Sampling Abnormality", 14: "DC Bus High Voltage" }},
    33120: {"category": "inverter", "bits": {
        0: "Grid Disturbance", 1: "DC Component Too Large", 2: "Over Temperature Protection",
        3: "Relay Detection Protection", 4: "Under Temperature Protection", 5: "PV Insulation Fault",
        6: "12V Undervoltage Protection", 7: "Leakage Current Protection", 8: "Leakage Current Self-test Protection",
        9: "DSP Initialization Protection", 10: "DSP_B Protection",
        11: "Battery Overvoltage Hardware Failure", 12: "LLC Hardware Overcurrent",
        13: "Network Side Current Transient Overcurrent", 14: "CAN Communication Failed", 15: "DSP Communication Failed" }},
    33145: {"category": "bms", "bits": {
        0: "Over Temperature Discharge", 1: "BMS Overvoltage", 2: "BMS Undervoltage",
        3: "Under Temperature Discharge", 4: "BMS Over Temperature", 5: "BMS Under Temperature",
        6: "BMS Over Temperature Charging", 7: "BMS Under Temperature Charging", 8: "BMS Discharging Overcurrent" }},
    33146: {"category": "bms", "bits": {
        0: "BMS Charging Overcurrent", 2: "Over SoC", 3: "BMS Internal Protection", 4: "BMS Battery Module Unbalanced" }},
    33121: {"category": "status", "bits": {
        0: "Normal Operation", 1: "Initial Standby", 3: "Load Present", 4: "Export Power Limit Active",
        5: "Derating", 6: "Power Limiting", 7: "Import Power Limit Active", 8: "Load Failure",
        9: "Grid Present", 10: "Battery Failure", 11: "EPS Mode Active" }}
}
ALERT_CATEGORIES: List[str] = sorted(list(set(v['category'] for v in SOLIS_FAULT_BITFIELD_MAPS.values())))

SOLIS_INVERTER_MODEL_CODES: Dict[int, str] = {
    0: "Unknown",
    1: "Solis-2G Mini",
    2: "Solis-2G Single Phase",
    3: "Solis-2G Three Phase",
    16: "Solis 1P GT (0.7-10kW)",
    17: "Solis 1P LV GT",
    18: "Solis 1P HV GT (US)",
    25: "Solis S6 1P LV Hybrid (3-6kW)",
    32: "Solis 3P GT (3-20kW)",
    33: "Solis 3P GT (>20kW)",
    34: "Solis 3P LV GT",
    35: "Solis 3P HV GT (US?)",
    48: "Solis RHI/RAI 1P LV Hybrid/AC",
    49: "Solis RAI 1P LV AC Coupled",
    50: "Solis AIO 1P LV",
    64: "Solis RHI 1P HV Hybrid",
    65: "Solis RHI 1P HV Hybrid (US)",
    66: "Solis AIO 1P HV",
    80: "Solis RHI 3P LV Hybrid",
    96: "Solis RHI 3P HV Hybrid (5G)",
    112: "Solis S6 3P HV Hybrid (5-10kW)",
    113: "Solis S6 3P HV Hybrid (12-15kW+)",
    114: "Solis S6 3P LV Hybrid (10-15kW)",
    115: "Solis S6 3P HV Hybrid (20-50kW?)",
    128: "Solis S6 1P HV Hybrid",
    129: "Solis S6 1P HV Hybrid (US)",
    144: "Solis S6 1P LV Hybrid",
    145: "Solis S6 1P LV AC Coupled",
    160: "Solis Off-Grid (Generic)",
    161: "Solis S6 1P LV Off-Grid Hybrid",
}
BATTERY_MODEL_CODES: Dict[int, str] = {
    0: "Unknown / Not Set", 1: "Pylontech", 2: "BYD", 3: "LG RESU", 4: "Weco",
    5: "Soluna", 6: "Dyness", 7: "Pytes", 8: "Alpha ESS", 9: "Discover AES",
    10: "Huawei LUNA", 11: "Turbo Energy", 12: "Solax", 13: "FoxESS", 14: "RoyPow",
    15: "Uhome", 16: "Sunwoda", 99: "Battery BMS"
}
MODBUS_EXCEPTION_CODES: Dict[int, str] = {
    1: "Illegal Function", 2: "Illegal Data Address", 3: "Illegal Data Value",
    4: "Slave Device Failure", 5: "Acknowledge", 6: "Slave Device Busy",
    8: "Memory Parity Error", 10: "Gateway Path Unavailable",
    11: "Gateway Target Device Failed to Respond"
}