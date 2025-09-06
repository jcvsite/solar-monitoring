# plugins/plugin_interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional, Union, TYPE_CHECKING
import logging # Use standard logging

if TYPE_CHECKING:
    from core.app_state import AppState

def parse_config_int(config_dict: Dict[str, Any], key: str, default: int) -> int:
    """
    Parse an integer configuration value, handling comments and whitespace.
    
    Args:
        config_dict: The configuration dictionary
        key: The configuration key to parse
        default: Default value if key is not found
        
    Returns:
        The parsed integer value
        
    Example:
        # Handles values like "115200 ; comment" or "115200"
        baud_rate = parse_config_int(config, "baud_rate", 9600)
    """
    value_str = str(config_dict.get(key, default))
    # Strip comments (everything after ';') and whitespace
    clean_value = value_str.split(';')[0].strip()
    return int(clean_value)

def parse_config_float(config_dict: Dict[str, Any], key: str, default: float) -> float:
    """
    Parse a float configuration value, handling comments and whitespace.
    
    Args:
        config_dict: The configuration dictionary
        key: The configuration key to parse
        default: Default value if key is not found
        
    Returns:
        The parsed float value
    """
    value_str = str(config_dict.get(key, default))
    # Strip comments (everything after ';') and whitespace
    clean_value = value_str.split(';')[0].strip()
    return float(clean_value)

def parse_config_str(config_dict: Dict[str, Any], key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Parse a string configuration value, handling comments and whitespace.
    
    Args:
        config_dict: The configuration dictionary
        key: The configuration key to parse
        default: Default value if key is not found
        
    Returns:
        The parsed string value, or None if not found and no default
    """
    value = config_dict.get(key, default)
    if value is None:
        return None
    value_str = str(value)
    # Strip comments (everything after ';') and whitespace
    clean_value = value_str.split(';')[0].strip()
    return clean_value if clean_value else None

# --- Standardized Data Keys ---
class StandardDataKeys:
    """
    A centralized namespace for standardized data keys used throughout the application.

    This class defines a comprehensive set of string constants that serve as keys
    for data dictionaries passed between plugins and the core application. Using these
    standard keys ensures consistency and interoperability between different hardware
    plugins (e.g., inverters, BMS) and core services (e.g., data processor,
    web service, MQTT service).

    The keys are grouped by their functional area:
    - Core Application Status
    - Device Identification (Static)
    - Inverter Operational Data
    - PV (Solar) Input
    - Battery System (Static and Dynamic)
    - Grid Interaction
    - Load / Consumption
    - EPS / Backup Power
    - Configuration Values
    """
    # === TIMESTAMPS & STATUS (Core Application Populated) ===
    SERVER_TIMESTAMP_MS_UTC = "server_timestamp_ms_utc"
    PLUGIN_DATA_TIMESTAMP_MS_UTC = "plugin_data_timestamp_ms_utc"
    CORE_PLUGIN_CONNECTION_STATUS = "core_plugin_connection_status" # For a specific plugin instance if multiple (used as prefix in SHARED_DATA)

    # === DEVICE IDENTIFICATION & STATIC INFO (from Plugin's read_static_data) ===
    STATIC_DEVICE_CATEGORY = "static_device_category" # str: "inverter", "bms", "meter", "generic_sensor_source"

    # === INVERTER IDENTIFICATION & STATIC INFO ===
    STATIC_INVERTER_MODEL_NAME = "static_inverter_model_name"
    STATIC_INVERTER_SERIAL_NUMBER = "static_inverter_serial_number"
    STATIC_INVERTER_FIRMWARE_VERSION = "static_inverter_firmware_version"
    STATIC_INVERTER_MANUFACTURER = "static_inverter_manufacturer"
    STATIC_COMMUNICATION_PROTOCOL_VERSION = "static_communication_protocol_version"
    STATIC_RATED_POWER_AC_WATTS = "static_rated_power_ac_watts"
    STATIC_NUMBER_OF_MPPTS = "static_number_of_mppts"
    STATIC_NUMBER_OF_PHASES_AC = "static_number_of_phases_ac"

    # === INVERTER OPERATIONAL STATUS & FAULTS (Dynamic) ===
    OPERATIONAL_INVERTER_STATUS_CODE = "operational_inverter_status_code"
    OPERATIONAL_INVERTER_STATUS_TEXT = "operational_inverter_status_text"
    OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS = "operational_inverter_temperature_celsius"
    OPERATIONAL_ACTIVE_FAULT_CODES_LIST = "operational_active_fault_codes_list"
    OPERATIONAL_ACTIVE_FAULT_MESSAGES_LIST = "operational_active_fault_messages_list"
    OPERATIONAL_CATEGORIZED_ALERTS_DICT = "operational_categorized_alerts_dict" # Categories: "status", "grid", "eps", "battery", "inverter", "bms", "unknown"
    OPERATIONAL_EFFICIENCY_PERCENT = "operational_efficiency_percent"
    OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT = "operational_battery_time_remaining_estimate_text"

    # === PV / SOLAR INPUT (Dynamic) ===
    PV_MPPT1_VOLTAGE_VOLTS = "pv_mppt1_voltage_volts"
    PV_MPPT1_CURRENT_AMPS = "pv_mppt1_current_amps"
    PV_MPPT1_POWER_WATTS = "pv_mppt1_power_watts"
    PV_MPPT2_VOLTAGE_VOLTS = "pv_mppt2_voltage_volts"
    PV_MPPT2_CURRENT_AMPS = "pv_mppt2_current_amps"
    PV_MPPT2_POWER_WATTS = "pv_mppt2_power_watts"
    PV_MPPT3_VOLTAGE_VOLTS = "pv_mppt3_voltage_volts"
    PV_MPPT3_CURRENT_AMPS = "pv_mppt3_current_amps"
    PV_MPPT3_POWER_WATTS = "pv_mppt3_power_watts"
    PV_MPPT4_VOLTAGE_VOLTS = "pv_mppt4_voltage_volts"
    PV_MPPT4_CURRENT_AMPS = "pv_mppt4_current_amps"
    PV_MPPT4_POWER_WATTS = "pv_mppt4_power_watts"
    PV_TOTAL_DC_POWER_WATTS = "pv_total_dc_power_watts"
    ENERGY_PV_DAILY_KWH = "energy_pv_daily_kwh"
    ENERGY_PV_MONTHLY_KWH = "energy_pv_monthly_kwh"
    ENERGY_PV_YEARLY_KWH = "energy_pv_yearly_kwh"
    ENERGY_PV_TOTAL_LIFETIME_KWH = "energy_pv_total_lifetime_kwh"

    # === BATTERY SYSTEM (Dynamic - can be from Inverter reporting on connected BMS, or directly from a BMS plugin) ===
    # --- Battery Identification (Static or semi-static) ---
    STATIC_BATTERY_MODEL_NAME = "static_battery_model_name"
    STATIC_BATTERY_SERIAL_NUMBER = "static_battery_serial_number"
    STATIC_BATTERY_FIRMWARE_VERSION = "static_battery_firmware_version" # Firmware of the battery pack/BMS
    STATIC_BATTERY_MANUFACTURER = "static_battery_manufacturer"
    STATIC_BATTERY_NOMINAL_CAPACITY_KWH = "static_battery_nominal_capacity_kwh"
    STATIC_BATTERY_NOMINAL_VOLTAGE_VOLTS = "static_battery_nominal_voltage_volts"
    STATIC_BMS_HARDWARE_VERSION = "static_bms_hardware_version"
    STATIC_BMS_SOFTWARE_VERSION = "static_bms_software_version"

    # --- Battery Operational (Dynamic) ---
    BATTERY_STATE_OF_CHARGE_PERCENT = "battery_state_of_charge_percent"
    BATTERY_STATE_OF_HEALTH_PERCENT = "battery_state_of_health_percent"
    BATTERY_VOLTAGE_VOLTS = "battery_voltage_volts"
    BATTERY_CURRENT_AMPS = "battery_current_amps" # Convention: +ve DISCHARGING, -ve CHARGING.
    BATTERY_POWER_WATTS = "battery_power_watts"   # Convention: +ve DISCHARGING, -ve CHARGING.
    BATTERY_TEMPERATURE_CELSIUS = "battery_temperature_celsius" # Main battery temp, or average if multiple sensors
    BATTERY_STATUS_CODE = "battery_status_code"
    BATTERY_STATUS_TEXT = "battery_status_text"
    BATTERY_CYCLES_COUNT = "battery_cycles_count"
    # --- BMS Limits (Optional but useful if available) ---
    BMS_CHARGE_CURRENT_LIMIT_AMPS = "bms_charge_current_limit_amps"
    BMS_DISCHARGE_CURRENT_LIMIT_AMPS = "bms_discharge_current_limit_amps"
    BMS_CHARGE_POWER_LIMIT_WATTS = "bms_charge_power_limit_watts"
    BMS_DISCHARGE_POWER_LIMIT_WATTS = "bms_discharge_power_limit_watts"

    # --- BMS Detailed Cell/Pack Info (NEW - primarily from a dedicated BMS plugin) ---
    BMS_CELL_COUNT = "bms_cell_count" # int
    BMS_CELL_VOLTAGE_MIN_VOLTS = "bms_cell_voltage_min_volts" # float
    BMS_CELL_VOLTAGE_MAX_VOLTS = "bms_cell_voltage_max_volts" # float
    BMS_CELL_VOLTAGE_AVERAGE_VOLTS = "bms_cell_voltage_average_volts" # float
    BMS_CELL_VOLTAGE_DELTA_VOLTS = "bms_cell_voltage_delta_volts" # float (Max - Min)
    BMS_TEMP_MAX_CELSIUS = "bms_temp_max_celsius" # Generic BMS max temp (could be cell or component)
    BMS_TEMP_MIN_CELSIUS = "bms_temp_min_celsius" # Generic BMS min temp
    BMS_CELL_TEMPERATURE_MIN_CELSIUS = "bms_cell_temperature_min_celsius" # float
    BMS_CELL_TEMPERATURE_MAX_CELSIUS = "bms_cell_temperature_max_celsius" # float
    BMS_CELL_TEMPERATURE_AVERAGE_CELSIUS = "bms_cell_temperature_average_celsius" # float
    BMS_CELL_VOLTAGES_LIST = "bms_cell_voltages_list" # List[float] (Optional, can be large)
    BMS_CELL_TEMPERATURES_LIST = "bms_cell_temperatures_list" # List[float] (Optional, can be large)
    BMS_BALANCING_STATUS_TEXT = "bms_balancing_status_text" # str: "Active", "Inactive", "Error"
    BMS_CELLS_BALANCING_TEXT = "bms_cells_balancing_text" # Text list of balancing cells, e.g., "1, 5, 8" or "None"
    BMS_CHARGE_FET_ON = "bms_charge_fet_on" # bool
    BMS_DISCHARGE_FET_ON = "bms_discharge_fet_on" # bool
    BMS_MOSFET_CHARGE_STATUS_TEXT = "bms_mosfet_charge_status_text" # str: "ON", "OFF"
    BMS_MOSFET_DISCHARGE_STATUS_TEXT = "bms_mosfet_discharge_status_text" # str: "ON", "OFF"
    BMS_REMAINING_CAPACITY_AH = "bms_remaining_capacity_ah"
    BMS_FULL_CAPACITY_AH = "bms_full_capacity_ah"
    BMS_NOMINAL_CAPACITY_AH = "bms_nominal_capacity_ah"
    BMS_FAULT_SUMMARY_TEXT = "bms_fault_summary_text"
    BMS_ACTIVE_ALARMS_LIST = "bms_active_alarms_list"
    BMS_ACTIVE_WARNINGS_LIST = "bms_active_warnings_list"
    BMS_PLUGIN_LAST_UPDATE_TIMESTAMP = "bms_plugin_last_update_timestamp"
    BMS_CELL_WITH_MIN_VOLTAGE_NUMBER = "bms_cell_with_min_voltage_number" # int: Number of the cell with the lowest voltage
    BMS_CELL_WITH_MAX_VOLTAGE_NUMBER = "bms_cell_with_max_voltage_number" # int: Number of the cell with the highest voltage

    # --- Battery Energy (Dynamic, Cumulative for the period) ---
    ENERGY_BATTERY_DAILY_CHARGE_KWH = "energy_battery_daily_charge_kwh"
    ENERGY_BATTERY_DAILY_DISCHARGE_KWH = "energy_battery_daily_discharge_kwh"
    ENERGY_BATTERY_TOTAL_CHARGE_KWH = "energy_battery_total_charge_kwh"
    ENERGY_BATTERY_TOTAL_DISCHARGE_KWH = "energy_battery_total_discharge_kwh"

    # === GRID INTERACTION (Dynamic) ===
    GRID_L1_VOLTAGE_VOLTS = "grid_l1_voltage_volts"
    GRID_L1_CURRENT_AMPS = "grid_l1_current_amps"
    GRID_L1_FREQUENCY_HZ = "grid_l1_frequency_hz"
    GRID_L1_POWER_WATTS = "grid_l1_power_watts"
    GRID_L2_VOLTAGE_VOLTS = "grid_l2_voltage_volts"
    GRID_L2_CURRENT_AMPS = "grid_l2_current_amps"
    GRID_L2_POWER_WATTS = "grid_l2_power_watts"
    GRID_L3_VOLTAGE_VOLTS = "grid_l3_voltage_volts"
    GRID_L3_CURRENT_AMPS = "grid_l3_current_amps"
    GRID_L3_POWER_WATTS = "grid_l3_power_watts"
    GRID_TOTAL_ACTIVE_POWER_WATTS = "grid_total_active_power_watts"
    GRID_TOTAL_REACTIVE_POWER_VAR = "grid_total_reactive_power_var"
    GRID_TOTAL_APPARENT_POWER_VA = "grid_total_apparent_power_va"
    GRID_POWER_FACTOR = "grid_power_factor"
    GRID_FREQUENCY_HZ = "grid_frequency_hz"
    ENERGY_GRID_DAILY_IMPORT_KWH = "energy_grid_daily_import_kwh"
    ENERGY_GRID_DAILY_EXPORT_KWH = "energy_grid_daily_export_kwh"
    ENERGY_GRID_TOTAL_IMPORT_KWH = "energy_grid_total_import_kwh"
    ENERGY_GRID_TOTAL_EXPORT_KWH = "energy_grid_total_export_kwh"
    ENERGY_GRID_YESTERDAY_IMPORT_KWH = "energy_grid_yesterday_import_kwh"
    ENERGY_GRID_YESTERDAY_EXPORT_KWH = "energy_grid_yesterday_export_kwh"

    # === LOAD / CONSUMPTION (Dynamic) ===
    LOAD_L1_POWER_WATTS = "load_l1_power_watts"
    LOAD_L2_POWER_WATTS = "load_l2_power_watts"
    LOAD_L3_POWER_WATTS = "load_l3_power_watts"
    LOAD_TOTAL_POWER_WATTS = "load_total_power_watts"
    AC_POWER_WATTS = "ac_power_watts" # Typically Inverter AC output power
    ENERGY_LOAD_DAILY_KWH = "energy_load_daily_kwh"
    ENERGY_LOAD_YESTERDAY_KWH = "energy_load_yesterday_kwh"
    ENERGY_LOAD_TOTAL_KWH = "energy_load_total_kwh"

    # === EPS / BACKUP POWER (Dynamic, if supported) ===
    EPS_L1_VOLTAGE_VOLTS = "eps_l1_voltage_volts"
    EPS_L1_CURRENT_AMPS = "eps_l1_current_amps"
    EPS_L1_FREQUENCY_HZ = "eps_l1_frequency_hz"
    EPS_L1_POWER_WATTS = "eps_l1_power_watts"
    EPS_L2_VOLTAGE_VOLTS = "eps_l2_voltage_volts"
    EPS_L2_CURRENT_AMPS = "eps_l2_current_amps"
    EPS_L2_FREQUENCY_HZ = "eps_l2_frequency_hz"
    EPS_L2_POWER_WATTS = "eps_l2_power_watts"
    EPS_L3_VOLTAGE_VOLTS = "eps_l3_voltage_volts"
    EPS_L3_CURRENT_AMPS = "eps_l3_current_amps"
    EPS_L3_FREQUENCY_HZ = "eps_l3_frequency_hz"
    EPS_L3_POWER_WATTS = "eps_l3_power_watts"
    EPS_TOTAL_ACTIVE_POWER_WATTS = "eps_total_active_power_watts"
    ENERGY_EPS_DAILY_KWH = "energy_eps_daily_kwh"
    ENERGY_EPS_YESTERDAY_KWH = "energy_eps_yesterday_kwh"
    ENERGY_EPS_TOTAL_KWH = "energy_eps_total_kwh"

    # === CONFIGURATION VALUES (from main config.ini, passed to plugin or used by core) ===
    CONFIG_PV_INSTALLED_CAPACITY_WATT_PEAK = "config_pv_installed_capacity_watt_peak"
    CONFIG_BATTERY_USABLE_CAPACITY_KWH = "config_battery_usable_capacity_kwh"
    CONFIG_BATTERY_MAX_CHARGE_POWER_W = "config_battery_max_charge_power_w"
    CONFIG_BATTERY_MAX_DISCHARGE_POWER_W = "config_battery_max_discharge_power_w"

    # === PLUGIN-SPECIFIC DATA (Optional pass-through) ===
    PLUGIN_SPECIFIC_DATA_DICT = "plugin_specific_data_dict" # dict


class DevicePlugin(ABC):
    """
    Abstract Base Class for all device plugins.

    This class defines the essential interface that every hardware-specific plugin
    must implement to be compatible with the monitoring application. It ensures
    that the core application can interact with any device (inverter, BMS, etc.)
    in a standardized way.

    Concrete plugins must implement methods for connecting, disconnecting, and
    reading both static (e.g., model, serial number) and dynamic (e.g., power,
    voltage) data.
    """
    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initialize the plugin with its specific configuration and the main application logger.
        'instance_name' is a unique identifier for this plugin instance (e.g., "main_inverter", "battery_bms").
        'plugin_specific_config' is a dictionary derived from the main config.ini
        (e.g., all keys from the [PLUGIN_YourPluginName_instance_name] section).
        """
        self.instance_name = instance_name
        self.plugin_config = plugin_specific_config
        self.logger = main_logger
        self.app_state = app_state
        self.client: Optional[Any] = None # Plugin-specific client (e.g., Modbus client, serial port)
        self._is_connected_flag: bool = False # Common flag, managed by plugin's connect/disconnect
        self.connection_status: str = "Initializing"

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique type name of this plugin (e.g., 'solis_modbus', 'seplos_bms_v2')."""
        pass

    @property
    @abstractmethod
    def pretty_name(self) -> str:
        """Return a human-friendly name for the plugin type (e.g., 'Solis Modbus Inverter', 'Seplos BMS v2')."""
        pass

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to the device. Returns True if connected."""
        # Concrete implementation that plugins can override if _is_connected_flag is not sufficient
        return self._is_connected_flag

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the device.
        MUST set self._is_connected_flag = True on success.
        Returns True on success, False on failure.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect from the device.
        MUST set self._is_connected_flag = False.
        """
        pass

    @abstractmethod
    def read_static_data(self) -> Dict[str, Any]:
        """
        Read static/identifying data from the device ONCE upon successful connection.
        MUST include StandardDataKeys.STATIC_DEVICE_CATEGORY key in the returned dictionary.
        Value for this key should be "inverter", "bms", "meter", etc.
        Returns a dictionary where keys are from StandardDataKeys (e.g., StandardDataKeys.STATIC_INVERTER_MODEL_NAME)
        and values are the corresponding data (direct values, not dicts like {'value': X}).
        """
        pass

    @abstractmethod
    def read_dynamic_data(self) -> Dict[str, Any]:
        """
        Read dynamic/operational data from the device.
        Returns a dictionary where keys are from StandardDataKeys and values are the current readings
        (direct values, not dicts like {'value': X}).
        Example:
        {
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: 88.2,
            StandardDataKeys.BATTERY_STATUS_TEXT: "Discharging",
            StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT: {"bms": ["Cell Overvoltage"]}, # If plugin generates this
            StandardDataKeys.PLUGIN_DATA_TIMESTAMP_MS_UTC: 1678886400000 # Optional: if plugin knows exact data time
        }
        The core application will add StandardDataKeys.SERVER_TIMESTAMP_MS_UTC and
        potentially StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS (though this is also per-instance).
        """
        pass
        
    def read_yesterday_energy_summary(self) -> Optional[Dict[str, Any]]:
        """
        Optional: Attempt to read cumulative energy totals for "yesterday" directly from the device.
        This is useful for backfilling the daily_summary table on script startup if the device
        stores these values.

        Returns:
            A dictionary where keys are StandardDataKeys (e.g., StandardDataKeys.ENERGY_PV_DAILY_KWH,
            but representing YESTERDAY'S total for that category) and values are the readings.
            Example: {
                StandardDataKeys.ENERGY_PV_DAILY_KWH: 10.5, # This would be PV yield for *yesterday*
                StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: 2.3,
                # etc. for other relevant StandardDataKeys normally used for daily totals.
            }
            Returns None if the plugin does not support this or fails to read.
            The plugin should map its internal "yesterday" registers to the "daily" StandardDataKeys
            for consistency with how the summary table is structured.
        """
        return None # Default implementation: not supported