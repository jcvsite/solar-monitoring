# plugins/inverter/eg4_modbus_constants.py
"""
EG4 Modbus Constants and Register Definitions

This module contains comprehensive constant definitions for EG4 hybrid inverters using
the Modbus RTU Protocol V58. It includes all register maps, operation modes, fault codes,
and configuration parameters needed to communicate with EG4 inverter models.

Features:
- Complete V58 protocol implementation (200+ registers)
- Input registers for real-time operational data
- Holding registers for configuration and control
- 3-phase system support for applicable models
- BMS integration for battery cell monitoring
- Generator monitoring and control capabilities
- Off-grid/EPS operation support
- AFCI (Arc Fault Circuit Interrupter) support
- Historical fault and warning records
- Comprehensive energy monitoring and statistics

Supported Models:
- EG4 6000XP, 12000XP, 18000XP series
- EG4 PowerPro series
- Compatible EG4 hybrid inverter models with V58 protocol

Register Categories:
- EG4_INPUT_REGISTERS: Real-time operational data (FC04)
- EG4_HOLD_REGISTERS: Configuration and control parameters (FC03/FC06)
- EG4_OPERATION_MODES: Inverter operation state codes
- EG4_ALARM_CODES: Fault and warning code mappings

Protocol Features:
- Little-endian byte and word order for multi-register values
- Comprehensive BMS data including cell voltages and temperatures
- Generator integration with automatic transfer switching
- Time-based charging/discharging schedules
- Grid protection and power quality settings
- Parallel operation support for multiple inverters

Protocol Reference: EG4 Modbus RTU Protocol V58
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

from typing import Dict, Any

# -----------------------
# Input Registers (FC04)
# -----------------------
# Complete register map from EG4 V58 protocol CSV

EG4_INPUT_REGISTERS: Dict[str, Dict[str, Any]] = {
    # Basic System Status
    "operation_mode": {"addr": 0, "type": "uint16", "desc": "Inverter operation state"},
    "pv1_voltage": {"addr": 1, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "PV1 voltage"},
    "pv2_voltage": {"addr": 2, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "PV2 voltage"},
    "pv3_voltage": {"addr": 3, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "PV3 voltage"},
    "battery_voltage": {"addr": 4, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery voltage"},
    "battery_soc": {"addr": 5, "type": "uint8", "unit": "%", "desc": "Battery SOC (low byte)"},
    "battery_soh": {"addr": 5, "type": "uint8", "unit": "%", "desc": "Battery SOH (high byte)", "byte_offset": 1},
    "internal_fault_code": {"addr": 6, "type": "uint16", "desc": "Internal fault code"},
    
    # PV Power Data
    "pv1_power": {"addr": 7, "type": "uint16", "unit": "W", "desc": "PV1 power"},
    "pv2_power": {"addr": 8, "type": "uint16", "unit": "W", "desc": "PV2 power"},
    "pv3_power": {"addr": 9, "type": "uint16", "unit": "W", "desc": "PV3 power (total PV power)"},
    
    # Battery Power Data
    "battery_charge_power": {"addr": 10, "type": "uint16", "unit": "W", "desc": "Battery charging power"},
    "battery_discharge_power": {"addr": 11, "type": "uint16", "unit": "W", "desc": "Battery discharging power"},
    
    # Grid Voltage Data (3-Phase Support)
    "grid_r_voltage": {"addr": 12, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "R-phase grid voltage"},
    "grid_s_voltage": {"addr": 13, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "S-phase grid voltage"},
    "grid_t_voltage": {"addr": 14, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "T-phase grid voltage"},
    "grid_frequency": {"addr": 15, "type": "uint16", "scale": 0.01, "unit": "Hz", "desc": "Grid frequency"},
    
    # Inverter Power Data
    "inverter_power_r": {"addr": 16, "type": "uint16", "unit": "W", "desc": "On-grid inverter power (R-phase)"},
    "ac_charge_power_r": {"addr": 17, "type": "uint16", "unit": "W", "desc": "AC charging power (R-phase)"},
    "inverter_current_r": {"addr": 18, "type": "uint16", "scale": 0.01, "unit": "A", "desc": "Inverter RMS current (R-phase)"},
    "power_factor": {"addr": 19, "type": "uint16", "scale": 0.001, "desc": "Power factor"},
    
    # Off-Grid/EPS Data
    "eps_r_voltage": {"addr": 20, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "EPS R-phase voltage"},
    "eps_s_voltage": {"addr": 21, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "EPS S-phase voltage"},
    "eps_t_voltage": {"addr": 22, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "EPS T-phase voltage"},
    "eps_frequency": {"addr": 23, "type": "uint16", "scale": 0.01, "unit": "Hz", "desc": "EPS frequency"},
    "eps_power": {"addr": 24, "type": "uint16", "unit": "W", "desc": "EPS power (R-phase)"},
    "eps_apparent_power": {"addr": 25, "type": "uint16", "unit": "VA", "desc": "EPS apparent power (R-phase)"},
    
    # Grid Power Flow
    "power_to_grid": {"addr": 26, "type": "uint16", "unit": "W", "desc": "Power to grid (export)"},
    "power_to_user": {"addr": 27, "type": "uint16", "unit": "W", "desc": "Power to user (import)"},
    
    # Daily Energy Counters
    "daily_pv1_energy": {"addr": 28, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "PV1 daily energy"},
    "daily_pv2_energy": {"addr": 29, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "PV2 daily energy"},
    "daily_pv3_energy": {"addr": 30, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "PV3 daily energy"},
    "daily_inverter_energy": {"addr": 31, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "Daily inverter output energy"},
    "daily_ac_charge_energy": {"addr": 32, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "Daily AC charge energy"},
    "daily_battery_charge_energy": {"addr": 33, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "Daily battery charge energy"},
    "daily_battery_discharge_energy": {"addr": 34, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "Daily battery discharge energy"},
    "daily_eps_energy": {"addr": 35, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "Daily EPS energy"},
    "daily_energy_to_grid": {"addr": 36, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "Daily energy to grid"},
    "daily_energy_to_user": {"addr": 37, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "Daily energy to user"},
    
    # Bus Voltages
    "bus1_voltage": {"addr": 38, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Bus 1 voltage"},
    "bus2_voltage": {"addr": 39, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Bus 2 voltage"},
    
    # Total Energy Counters (32-bit values)
    "total_pv1_energy": {"addr": 40, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total PV1 energy"},
    "total_pv2_energy": {"addr": 42, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total PV2 energy"},
    "total_pv3_energy": {"addr": 44, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total PV3 energy"},
    "total_inverter_energy": {"addr": 46, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total inverter energy"},
    "total_ac_charge_energy": {"addr": 48, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total AC charge energy"},
    "total_battery_charge_energy": {"addr": 50, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total battery charge energy"},
    "total_battery_discharge_energy": {"addr": 52, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total battery discharge energy"},
    "total_eps_energy": {"addr": 54, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total EPS energy"},
    "total_energy_to_grid": {"addr": 56, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total energy to grid"},
    "total_energy_to_user": {"addr": 58, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total energy to user"},
    
    # Fault and Warning Codes
    "fault_code_l": {"addr": 60, "type": "uint16", "desc": "Fault code low word"},
    "fault_code_h": {"addr": 61, "type": "uint16", "desc": "Fault code high word"},
    "warning_code_l": {"addr": 62, "type": "uint16", "desc": "Warning code low word"},
    "warning_code_h": {"addr": 63, "type": "uint16", "desc": "Warning code high word"},
    
    # Temperature Data
    "inverter_temperature": {"addr": 64, "type": "int16", "scale": 0.1, "unit": "°C", "desc": "Internal temperature"},
    "radiator_temperature_1": {"addr": 65, "type": "int16", "scale": 0.1, "unit": "°C", "desc": "Radiator temperature 1"},
    "radiator_temperature_2": {"addr": 66, "type": "int16", "scale": 0.1, "unit": "°C", "desc": "Radiator temperature 2"},
    "battery_temperature": {"addr": 67, "type": "int16", "scale": 0.1, "unit": "°C", "desc": "Battery temperature"},
    
    # Runtime and System Info
    "runtime_total": {"addr": 69, "type": "uint32", "unit": "s", "desc": "Total runtime"},
    
    # BMS Data
    "bms_battery_type": {"addr": 80, "type": "uint16", "desc": "BMS battery type and brand"},
    "bms_max_charge_current": {"addr": 81, "type": "uint16", "scale": 0.01, "unit": "A", "desc": "BMS max charge current"},
    "bms_max_discharge_current": {"addr": 82, "type": "uint16", "scale": 0.01, "unit": "A", "desc": "BMS max discharge current"},
    "bms_charge_voltage_ref": {"addr": 83, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "BMS charge voltage reference"},
    "bms_discharge_cutoff_voltage": {"addr": 84, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "BMS discharge cutoff voltage"},
    "bms_parallel_num": {"addr": 96, "type": "uint16", "desc": "Number of batteries in parallel"},
    "bms_capacity": {"addr": 97, "type": "uint16", "unit": "Ah", "desc": "Battery capacity"},
    "bms_battery_current": {"addr": 98, "type": "int16", "scale": 0.01, "unit": "A", "desc": "BMS battery current"},
    "bms_fault_code": {"addr": 99, "type": "uint16", "desc": "BMS fault code"},
    "bms_warning_code": {"addr": 100, "type": "uint16", "desc": "BMS warning code"},
    "bms_max_cell_voltage": {"addr": 101, "type": "uint16", "scale": 0.001, "unit": "V", "desc": "BMS max cell voltage"},
    "bms_min_cell_voltage": {"addr": 102, "type": "uint16", "scale": 0.001, "unit": "V", "desc": "BMS min cell voltage"},
    "bms_max_cell_temp": {"addr": 103, "type": "int16", "scale": 0.1, "unit": "°C", "desc": "BMS max cell temperature"},
    "bms_min_cell_temp": {"addr": 104, "type": "int16", "scale": 0.1, "unit": "°C", "desc": "BMS min cell temperature"},
    "bms_cycle_count": {"addr": 106, "type": "uint16", "desc": "BMS cycle count"},
    
    # System Configuration
    "parallel_info": {"addr": 113, "type": "uint16", "desc": "Parallel system information"},
    "on_grid_load_power": {"addr": 114, "type": "uint16", "unit": "W", "desc": "On-grid load power"},
    "serial_number": {"addr": 115, "type": "string", "len": 5, "desc": "Serial number (10 ASCII chars)"},
    
    # Generator Data
    "generator_voltage": {"addr": 121, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Generator voltage"},
    "generator_frequency": {"addr": 122, "type": "uint16", "scale": 0.01, "unit": "Hz", "desc": "Generator frequency"},
    "generator_power": {"addr": 123, "type": "uint16", "unit": "W", "desc": "Generator power"},
    "daily_generator_energy": {"addr": 124, "type": "uint16", "scale": 0.1, "unit": "kWh", "desc": "Daily generator energy"},
    "total_generator_energy": {"addr": 125, "type": "uint32", "scale": 0.1, "unit": "kWh", "desc": "Total generator energy"},
    
    # Three-Phase Power Data
    "inverter_power_s": {"addr": 180, "type": "uint16", "unit": "W", "desc": "Inverter power S-phase"},
    "inverter_power_t": {"addr": 181, "type": "uint16", "unit": "W", "desc": "Inverter power T-phase"},
    "ac_charge_power_s": {"addr": 182, "type": "uint16", "unit": "W", "desc": "AC charge power S-phase"},
    "ac_charge_power_t": {"addr": 183, "type": "uint16", "unit": "W", "desc": "AC charge power T-phase"},
    "power_to_grid_s": {"addr": 184, "type": "uint16", "unit": "W", "desc": "Power to grid S-phase"},
    "power_to_grid_t": {"addr": 185, "type": "uint16", "unit": "W", "desc": "Power to grid T-phase"},
    "power_to_user_s": {"addr": 186, "type": "uint16", "unit": "W", "desc": "Power to user S-phase"},
    "power_to_user_t": {"addr": 187, "type": "uint16", "unit": "W", "desc": "Power to user T-phase"},
}

# -----------------------
# Holding Registers (FC03/FC06)
# -----------------------
# Complete configuration register map from EG4 V58 protocol CSV

EG4_HOLD_REGISTERS: Dict[str, Dict[str, Any]] = {
    # Firmware and Model Information
    "fw_code_0": {"addr": 7, "type": "uint8", "desc": "Firmware code 0 (model)", "byte_offset": 0},
    "fw_code_1": {"addr": 7, "type": "uint8", "desc": "Firmware code 1 (derived model)", "byte_offset": 1},
    "fw_code_2": {"addr": 8, "type": "uint8", "desc": "Firmware code 2 (ODM)", "byte_offset": 0},
    "fw_code_3": {"addr": 8, "type": "uint8", "desc": "Firmware code 3 (region)", "byte_offset": 1},
    "slave_version": {"addr": 9, "type": "uint8", "desc": "Slave CPU version", "byte_offset": 0},
    "com_version": {"addr": 9, "type": "uint8", "desc": "Communication CPU version", "byte_offset": 1},
    "control_version": {"addr": 10, "type": "uint8", "desc": "Control CPU version", "byte_offset": 0},
    "fw_version": {"addr": 10, "type": "uint8", "desc": "External firmware version", "byte_offset": 1},
    
    # System Reset and Time Settings
    "reset_settings": {"addr": 11, "type": "uint16", "desc": "Reset settings bitfield", "writable": True},
    "time_year": {"addr": 12, "type": "uint8", "desc": "Year (17-255)", "byte_offset": 0, "writable": True},
    "time_month": {"addr": 12, "type": "uint8", "desc": "Month (1-12)", "byte_offset": 1, "writable": True},
    "time_date": {"addr": 13, "type": "uint8", "desc": "Date (1-31)", "byte_offset": 0, "writable": True},
    "time_hour": {"addr": 13, "type": "uint8", "desc": "Hour (0-23)", "byte_offset": 1, "writable": True},
    "time_minute": {"addr": 14, "type": "uint8", "desc": "Minute (0-59)", "byte_offset": 0, "writable": True},
    "time_second": {"addr": 14, "type": "uint8", "desc": "Second (0-59)", "byte_offset": 1, "writable": True},
    
    # Communication and System Settings
    "modbus_address": {"addr": 15, "type": "uint16", "desc": "Modbus address (0-150)", "writable": True},
    "language": {"addr": 16, "type": "uint16", "desc": "Language (0: English, 1: German)", "writable": True},
    "pv_input_model": {"addr": 20, "type": "uint16", "desc": "PV input model configuration", "writable": True},
    
    # Function Enable Bits
    "function_enable": {"addr": 21, "type": "uint16", "desc": "Function enable bitfield", "writable": True},
    
    # PV and Grid Connection Settings
    "pv_start_voltage": {"addr": 22, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "PV startup voltage (90.0-500.0V)", "writable": True},
    "grid_connect_time": {"addr": 23, "type": "uint16", "unit": "s", "desc": "Grid connection time (30-600s)", "writable": True},
    "grid_reconnect_time": {"addr": 24, "type": "uint16", "unit": "s", "desc": "Grid reconnection time (0-900s)", "writable": True},
    
    # Grid Protection Limits
    "grid_volt_conn_low": {"addr": 25, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Grid voltage connection low limit", "writable": True},
    "grid_volt_conn_high": {"addr": 26, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Grid voltage connection high limit", "writable": True},
    "grid_freq_conn_low": {"addr": 27, "type": "uint16", "scale": 0.01, "unit": "Hz", "desc": "Grid frequency connection low limit", "writable": True},
    "grid_freq_conn_high": {"addr": 28, "type": "uint16", "scale": 0.01, "unit": "Hz", "desc": "Grid frequency connection high limit", "writable": True},
    
    # Power Control Settings
    "active_power_percent": {"addr": 60, "type": "uint16", "unit": "%", "desc": "Active power percentage (0-100%)", "writable": True},
    "reactive_power_percent": {"addr": 61, "type": "uint16", "unit": "%", "desc": "Reactive power percentage (0-60%)", "writable": True},
    "power_factor_cmd": {"addr": 62, "type": "uint16", "scale": 0.001, "desc": "Power factor command", "writable": True},
    "charge_power_percent": {"addr": 64, "type": "uint16", "unit": "%", "desc": "Charge power percentage (0-100%)", "writable": True},
    "discharge_power_percent": {"addr": 65, "type": "uint16", "unit": "%", "desc": "Discharge power percentage (0-100%)", "writable": True},
    "ac_charge_power_percent": {"addr": 66, "type": "uint16", "unit": "%", "desc": "AC charge power percentage (0-100%)", "writable": True},
    
    # AC Charge Time Settings
    "ac_charge_soc_limit": {"addr": 67, "type": "uint16", "unit": "%", "desc": "AC charge SOC limit (0-100%)", "writable": True},
    "ac_charge_start_hour": {"addr": 68, "type": "uint8", "desc": "AC charge start hour (0-23)", "byte_offset": 0, "writable": True},
    "ac_charge_start_minute": {"addr": 68, "type": "uint8", "desc": "AC charge start minute (0-59)", "byte_offset": 1, "writable": True},
    "ac_charge_end_hour": {"addr": 69, "type": "uint8", "desc": "AC charge end hour (0-23)", "byte_offset": 0, "writable": True},
    "ac_charge_end_minute": {"addr": 69, "type": "uint8", "desc": "AC charge end minute (0-59)", "byte_offset": 1, "writable": True},
    
    # Battery Settings
    "battery_charge_voltage": {"addr": 99, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery charge voltage (50.0-59.0V)", "writable": True},
    "battery_discharge_voltage": {"addr": 100, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery discharge cutoff voltage (40.0-52.0V)", "writable": True},
    "battery_charge_current": {"addr": 101, "type": "uint16", "unit": "A", "desc": "Battery charge current (0-140A)", "writable": True},
    "battery_discharge_current": {"addr": 102, "type": "uint16", "unit": "A", "desc": "Battery discharge current (0-140A)", "writable": True},
    "battery_soc_discharge_limit": {"addr": 105, "type": "uint16", "unit": "%", "desc": "Battery SOC discharge limit (10-90%)", "writable": True},
    
    # Advanced Function Settings
    "function_enable_1": {"addr": 110, "type": "uint16", "desc": "Function enable 1 bitfield", "writable": True},
    "system_type": {"addr": 112, "type": "uint16", "desc": "System type (parallel configuration)", "writable": True},
    "composed_phase": {"addr": 113, "type": "uint16", "desc": "Composed phase setting (1-3)", "writable": True},
    
    # EPS Settings
    "eps_voltage_set": {"addr": 90, "type": "uint16", "unit": "V", "desc": "EPS voltage setting (208-277V)", "writable": True},
    "eps_frequency_set": {"addr": 91, "type": "uint16", "unit": "Hz", "desc": "EPS frequency setting (50-60Hz)", "writable": True},
    
    # Battery Configuration
    "battery_capacity": {"addr": 147, "type": "uint16", "unit": "Ah", "desc": "Battery capacity (0-10000Ah)", "writable": True},
    "battery_nominal_voltage": {"addr": 148, "type": "uint16", "scale": 0.1, "unit": "V", "desc": "Battery nominal voltage (40.0-59.0V)", "writable": True},
    "battery_type": {"addr": 80, "type": "uint16", "desc": "Battery type and communication", "writable": True},
    
    # Grid Type and System Configuration
    "grid_type": {"addr": 205, "type": "uint16", "desc": "Grid type (0: Split240V, 1: Split208V, etc.)", "writable": True},
    "output_priority_config": {"addr": 145, "type": "uint16", "desc": "Output priority (0: Battery, 1: PV, 2: AC)", "writable": True},
    "line_mode": {"addr": 146, "type": "uint16", "desc": "Line mode (0: APL, 1: UPS, 2: GEN)", "writable": True},
}

EG4_OPERATION_MODES = {
    0x00: "Standby", 0x01: "Fault", 0x02: "Programming",
    0x04: "PV Feed to Grid", 0x08: "PV Charging Battery",
    0x0C: "PV Feed to Grid & Charging", 0x10: "Battery Discharging to Grid",
    0x14: "PV & Battery Discharging to Grid", 0x20: "AC Charging",
    0x28: "PV & AC Charging", 0x40: "Battery Off-Grid",
    0x60: "Off-Grid + Battery Charging", 0x80: "PV Off-Grid",
    0xC0: "PV & Battery Off-Grid", 0x88: "PV Charging + Off-Grid"
}

# Fault codes from appendix, page 36 onwards
# Combine fault and warning codes for a single lookup
EG4_ALARM_CODES = {
    # Faults (E Codes)
    "E000": "Internal communication failure 1", "E001": "Model fault",
    "E002": "rsvd", "E003": "rsvd", "E004": "rsvd", "E005": "rsvd", "E006": "rsvd",
    "E007": "rsvd", "E008": "Parallel CAN communication failure",
    "E009": "The host is missing", "E010": "Inconsistent rated power",
    "E011": "Inconsistent AC connection or grid safety settings",
    "E012": "UPS short circuit", "E013": "UPS backfilling", "E014": "BUS BUS short circuit",
    "E015": "Phase abnormality in parallel system", "E016": "Relay fault",
    "E017": "Internal communication failure 2", "E018": "Internal communication failure 3",
    "E019": "BUS overvoltage", "E020": "EPS connection fault", "E021": "PV overvoltage",
    "E022": "Overcurrent protection", "E023": "Neutral fault", "E024": "PV short circuit",
    "E025": "Heatsink temperature out of range", "E026": "Internal failure",
    "E027": "Consistency failure", "E028": "Generator connection inconsistent",
    "E029": "Parallel synchronization signal loss", "E030": "rsvd",
    "E031": "Internal communication failure 4",
    # Warnings (W Codes)
    "W000": "Communication failure with battery", "W001": "AFCI communication fault",
    "W002": "AFCI High", "W003": "Communication failure with meter",
    "W004": "Battery failure", "W005": "AutoTest failure", "W006": "rsvd",
    "W007": "LCD communication Fault", "W008": "Software mismatch",
    "W009": "Fan Stuck", "W010": "Same para address", "W011": "Secondary overflow",
    "W012": "BatOnMos or Phase loss for parallel system",
    "W013": "Overtemperature or No primary set in parallel",
    "W014": "Multi-Primary set in parallel system", "W015": "Battery Reverse",
    "W016": "No AC Connection", "W017": "AC Voltage out of range",
    "W018": "AC Frequency out of range", "W019": "AC inconsistent in parallel system",
    "W020": "PV Isolation low", "W021": "Leakage I high", "W022": "DC injection high",
    "W023": "PV short circuit", "W024": "rsvd", "W025": "Battery voltage high",
    "W026": "Battery voltage low", "W027": "Battery open", "W028": "EPS Overload",
    "W030": "Meter Reversed", "W031": "EPS DCV high"
}