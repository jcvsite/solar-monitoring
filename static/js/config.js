/**
 * @file Centralized configuration and constants for the Solar Dashboard application.
 * This file includes UI behavior thresholds, network timing settings, and a comprehensive
 * mapping of backend data keys (SDK) to ensure consistency across the application.
 */

/**
 * Script version placeholder, replaced during the build process.
 * @type {string}
 */
export const __script_version__ = "{{ script_version }}";

// --- UI & Flow Behavior Constants ---

/** Minimum power in Watts to consider a flow active and animate it. */
export const FLOW_THRESHOLD_W = 1;
/** Minimum voltage for a PV string to be considered active/producing. */
export const MIN_VOLTAGE_FOR_ACTIVE_STRING = 1.0;
/** String constant for an unknown Tuya device state. */
export const JS_TUYA_STATE_UNKNOWN = "Unknown";
/** String constant for an 'ON' Tuya device state. */
export const JS_TUYA_STATE_ON = "ON";
/** String constant for an 'OFF' Tuya device state. */
export const JS_TUYA_STATE_OFF = "OFF";
/** String constant for a disabled Tuya device state. */
export const JS_TUYA_STATE_DISABLED = "Disabled";

// --- Network & Timing Constants ---

/** Time in milliseconds of inactivity before showing the disconnect popup. */
export const DISCONNECT_TIMEOUT_MS = 30000;
/** Interval in milliseconds for refreshing the power chart UI (currently not used for polling). */
export const POWER_CHART_UI_REFRESH_INTERVAL_MS = 15 * 1000;

/**
 * "Software Development Kit" for data keys.
 * This object provides a centralized mapping of all data point keys received from the backend.
 * Using this SDK ensures that any changes to backend key names only need to be updated in this one location.
 * @readonly
 * @enum {string}
 */
export const SDK = {
    // --- Core & Timestamps ---
    SERVER_TIMESTAMP_MS_UTC: "server_timestamp_ms_utc",
    CORE_PLUGIN_CONNECTION_STATUS: "core_plugin_connection_status",

    // --- Static Inverter & System Info ---
    STATIC_INVERTER_MODEL_NAME: "static_inverter_model_name",
    STATIC_INVERTER_MANUFACTURER: "static_inverter_manufacturer",
    STATIC_RATED_POWER_AC_WATTS: "static_rated_power_ac_watts",
    STATIC_NUMBER_OF_MPPTS: "static_number_of_mppts",
    CONFIG_PV_INSTALLED_CAPACITY_WATT_PEAK: "config_pv_installed_capacity_watt_peak",

    // --- Operational Status ---
    OPERATIONAL_INVERTER_STATUS_TEXT: "operational_inverter_status_text",
    OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: "operational_inverter_temperature_celsius",
    OPERATIONAL_CATEGORIZED_ALERTS_DICT: "operational_categorized_alerts_dict",

    // --- PV (Solar) Data ---
    PV_MPPT1_POWER_WATTS: "pv_mppt1_power_watts",
    PV_MPPT1_VOLTAGE_VOLTS: "pv_mppt1_voltage_volts",
    PV_MPPT1_CURRENT_AMPS: "pv_mppt1_current_amps",
    PV_MPPT2_POWER_WATTS: "pv_mppt2_power_watts",
    PV_MPPT2_VOLTAGE_VOLTS: "pv_mppt2_voltage_volts",
    PV_MPPT2_CURRENT_AMPS: "pv_mppt2_current_amps",
    PV_MPPT3_POWER_WATTS: "pv_mppt3_power_watts",
    PV_MPPT3_VOLTAGE_VOLTS: "pv_mppt3_voltage_volts",
    PV_MPPT3_CURRENT_AMPS: "pv_mppt3_current_amps",
    PV_MPPT4_POWER_WATTS: "pv_mppt4_power_watts",
    PV_MPPT4_VOLTAGE_VOLTS: "pv_mppt4_voltage_volts",
    PV_MPPT4_CURRENT_AMPS: "pv_mppt4_current_amps",
    PV_TOTAL_DC_POWER_WATTS: "pv_total_dc_power_watts",

    // --- Battery Data ---
    STATIC_BATTERY_MODEL_NAME: "static_battery_model_name",
    STATIC_BATTERY_MANUFACTURER: "static_battery_manufacturer",
    BATTERY_STATE_OF_CHARGE_PERCENT: "battery_state_of_charge_percent",
    BATTERY_POWER_WATTS: "battery_power_watts",
    BATTERY_STATUS_TEXT: "battery_status_text",
    BATTERY_TEMPERATURE_CELSIUS: "battery_temperature_celsius",
    BATTERY_VOLTAGE_VOLTS: "battery_voltage_volts",
    BATTERY_CURRENT_AMPS: "battery_current_amps",

    // --- BMS (Battery Management System) Data ---
    BMS_PLUGIN_CONNECTION_STATUS_KEY_PATTERN: "{instance_id}_core_plugin_connection_status",
    BMS_CELL_COUNT: "bms_cell_count",
    BMS_REMAINING_CAPACITY_AH: "bms_remaining_capacity_ah",
    BMS_FULL_CAPACITY_AH: "bms_full_capacity_ah",
    BMS_CELL_VOLTAGE_DELTA_VOLTS: "bms_cell_voltage_delta_volts",
    BMS_CELL_VOLTAGE_AVERAGE_VOLTS: "bms_cell_voltage_average_volts",
    BMS_CELL_WITH_MAX_VOLTAGE_NUMBER: "bms_cell_with_max_voltage_number",
    BMS_CELL_VOLTAGE_MAX_VOLTS: "bms_cell_voltage_max_volts",
    BMS_CELL_WITH_MIN_VOLTAGE_NUMBER: "bms_cell_with_min_voltage_number",
    BMS_CELL_VOLTAGE_MIN_VOLTS: "bms_cell_voltage_min_volts",
    BMS_TEMP_SENSOR_MOSFET: "bms_temp_sensor_mosfet",
    BMS_CHARGE_CURRENT_LIMIT_AMPS: "bms_charge_current_limit_amps",
    BMS_DISCHARGE_CURRENT_LIMIT_AMPS: "bms_discharge_current_limit_amps",
    BMS_CELL_TEMPERATURES_LIST: "bms_cell_temperatures_list",

    // --- Grid Data ---
    GRID_TOTAL_ACTIVE_POWER_WATTS: "grid_total_active_power_watts",
    GRID_L1_VOLTAGE_VOLTS: "grid_l1_voltage_volts",
    GRID_L1_CURRENT_AMPS: "grid_l1_current_amps",
    GRID_FREQUENCY_HZ: "grid_frequency_hz",

    // --- Load Data ---
    LOAD_TOTAL_POWER_WATTS: "load_total_power_watts",

    // --- Energy Summaries ---
    ENERGY_PV_DAILY_KWH: "energy_pv_daily_kwh",
    ENERGY_PV_MONTHLY_KWH: "energy_pv_monthly_kwh",
    ENERGY_PV_TOTAL_LIFETIME_KWH: "energy_pv_total_lifetime_kwh",
    ENERGY_BATTERY_DAILY_CHARGE_KWH: "energy_battery_daily_charge_kwh",
    ENERGY_BATTERY_DAILY_DISCHARGE_KWH: "energy_battery_daily_discharge_kwh",
    ENERGY_BATTERY_TOTAL_CHARGE_KWH: "energy_battery_total_charge_kwh",
    ENERGY_BATTERY_TOTAL_DISCHARGE_KWH: "energy_battery_total_discharge_kwh",
    ENERGY_GRID_DAILY_IMPORT_KWH: "energy_grid_daily_import_kwh",
    ENERGY_GRID_DAILY_EXPORT_KWH: "energy_grid_daily_export_kwh",
    ENERGY_GRID_TOTAL_IMPORT_KWH: "energy_grid_total_import_kwh",
    ENERGY_GRID_TOTAL_EXPORT_KWH: "energy_grid_total_export_kwh",
    ENERGY_LOAD_DAILY_KWH: "energy_load_daily_kwh",

    // --- Detailed/Less-Used Static Info ---
    STATIC_INVERTER_SERIAL_NUMBER: "static_inverter_serial_number",
    STATIC_INVERTER_FIRMWARE_VERSION: "static_inverter_firmware_version",
    STATIC_COMMUNICATION_PROTOCOL_VERSION: "static_communication_protocol_version",
    OPERATIONAL_ACTIVE_FAULT_CODES_LIST: "operational_active_fault_codes_list",
    OPERATIONAL_ACTIVE_FAULT_MESSAGES_LIST: "operational_active_fault_messages_list",
    OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT: "operational_battery_time_remaining_estimate_text",
    STATIC_BATTERY_SERIAL_NUMBER: "static_battery_serial_number",
    STATIC_BATTERY_FIRMWARE_VERSION: "static_battery_firmware_version",
    STATIC_BATTERY_NOMINAL_CAPACITY_KWH: "static_battery_nominal_capacity_kwh",
    STATIC_BATTERY_NOMINAL_VOLTAGE_VOLTS: "static_battery_nominal_voltage_volts",
    STATIC_NUMBER_OF_PHASES_AC: "static_number_of_phases_ac",
    BATTERY_STATE_OF_HEALTH_PERCENT: "battery_state_of_health_percent",
    BATTERY_CYCLES_COUNT: "battery_cycles_count",
    CONFIG_BATTERY_USABLE_CAPACITY_KWH: "config_battery_usable_capacity_kwh",
    CONFIG_BATTERY_MAX_CHARGE_POWER_W: "config_battery_max_charge_power_w",
    CONFIG_BATTERY_MAX_DISCHARGE_POWER_W: "config_battery_max_discharge_power_w"
};