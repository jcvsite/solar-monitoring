# plugins/battery/bms_plugin_base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from core.app_state import AppState
import logging
from datetime import datetime, timezone

try:
    from ..plugin_interface import DevicePlugin, StandardDataKeys
except ImportError:
    from plugin_interface import DevicePlugin, StandardDataKeys # type: ignore

# Standardized BMS Keys (using StandardDataKeys where possible)
BMS_KEY_SOC = StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT
BMS_KEY_SOH = StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT
BMS_KEY_VOLTAGE = StandardDataKeys.BATTERY_VOLTAGE_VOLTS
BMS_KEY_CURRENT = StandardDataKeys.BATTERY_CURRENT_AMPS
BMS_KEY_POWER = StandardDataKeys.BATTERY_POWER_WATTS
BMS_KEY_REMAINING_CAPACITY_AH = StandardDataKeys.BMS_REMAINING_CAPACITY_AH
BMS_KEY_FULL_CAPACITY_AH = StandardDataKeys.BMS_FULL_CAPACITY_AH
BMS_KEY_NOMINAL_CAPACITY_AH = StandardDataKeys.BMS_NOMINAL_CAPACITY_AH
BMS_KEY_CYCLE_COUNT = StandardDataKeys.BATTERY_CYCLES_COUNT
BMS_KEY_TEMPERATURES_ALL = StandardDataKeys.BMS_CELL_TEMPERATURES_LIST 
BMS_KEY_TEMP_SENSOR_PREFIX = "bms_temp_sensor_" 
BMS_KEY_TEMP_MAX = StandardDataKeys.BMS_TEMP_MAX_CELSIUS
BMS_KEY_TEMP_MIN = StandardDataKeys.BMS_TEMP_MIN_CELSIUS
BMS_KEY_CELL_COUNT = StandardDataKeys.BMS_CELL_COUNT
BMS_KEY_CELL_VOLTAGE_PREFIX = "bms_cell_voltage_" 
BMS_KEY_CELL_VOLTAGES_ALL = StandardDataKeys.BMS_CELL_VOLTAGES_LIST
BMS_KEY_CELL_VOLTAGE_MIN = StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS
BMS_KEY_CELL_VOLTAGE_MAX = StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS
BMS_KEY_CELL_VOLTAGE_AVG = StandardDataKeys.BMS_CELL_VOLTAGE_AVERAGE_VOLTS
BMS_KEY_CELL_VOLTAGE_DIFF = StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS
BMS_KEY_LOWEST_CELL_NUMBER = StandardDataKeys.BMS_CELL_WITH_MIN_VOLTAGE_NUMBER
BMS_KEY_HIGHEST_CELL_NUMBER = StandardDataKeys.BMS_CELL_WITH_MAX_VOLTAGE_NUMBER
BMS_KEY_CELL_BALANCE_ACTIVE_PREFIX = "bms_cell_balance_active_" 
BMS_KEY_CELLS_BALANCING = StandardDataKeys.BMS_CELLS_BALANCING_TEXT 
BMS_KEY_STATUS_TEXT = StandardDataKeys.BATTERY_STATUS_TEXT 
BMS_KEY_CHARGE_FET_ON = StandardDataKeys.BMS_CHARGE_FET_ON
BMS_KEY_DISCHARGE_FET_ON = StandardDataKeys.BMS_DISCHARGE_FET_ON
BMS_KEY_FAULT_SUMMARY = StandardDataKeys.BMS_FAULT_SUMMARY_TEXT 
BMS_KEY_ACTIVE_ALARMS_LIST = StandardDataKeys.BMS_ACTIVE_ALARMS_LIST 
BMS_KEY_ACTIVE_WARNINGS_LIST = StandardDataKeys.BMS_ACTIVE_WARNINGS_LIST 
BMS_PLUGIN_LAST_UPDATE = StandardDataKeys.BMS_PLUGIN_LAST_UPDATE_TIMESTAMP 
BMS_KEY_MANUFACTURER = StandardDataKeys.STATIC_BATTERY_MANUFACTURER
BMS_KEY_MODEL = StandardDataKeys.STATIC_BATTERY_MODEL_NAME
BMS_KEY_SERIAL_NUMBER = StandardDataKeys.STATIC_BATTERY_SERIAL_NUMBER
BMS_KEY_FIRMWARE_VERSION = StandardDataKeys.STATIC_BATTERY_FIRMWARE_VERSION
BMS_KEY_HARDWARE_VERSION = StandardDataKeys.STATIC_BMS_HARDWARE_VERSION
BMS_KEY_CELL_DISCONNECTION_PREFIX = "bms_cell_disconnection_status_"

class BMSPluginBase(DevicePlugin, ABC):
    """
    Abstract Base Class for Battery Management System (BMS) plugins.

    This class provides a standardized framework for all BMS plugins. It inherits
    from `DevicePlugin` and defines a common set of methods and properties that
    concrete BMS plugins must implement. It handles the standardization of data keys
    and the generation of categorized alerts from raw alarm/warning data.

    Concrete implementations should focus on the specifics of communicating with
    the hardware and decoding its data, by implementing methods like `read_bms_data`
    and `get_bms_static_info`.
    """
    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the BMSPluginBase.

        Args:
            instance_name (str): The unique name for this plugin instance.
            plugin_specific_config (Dict[str, Any]): A dictionary containing configuration
                                                     parameters specific to this plugin.
            main_logger (logging.Logger): The main logger instance for the application.
            app_state (Optional[AppState]): The central application state object.
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.latest_data_cache: Dict[str, Any] = {}
        self._is_connected_flag: bool = False
        self.last_error_message: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """
        Returns the connection status of the plugin.

        Returns:
            bool: True if the plugin is connected to the device, False otherwise.
        """
        return self._is_connected_flag

    @staticmethod
    @abstractmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        """
        Returns a list of configuration parameters that this plugin supports.

        This method should be implemented by concrete subclasses to expose their
        specific configuration options to the system.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary
                                  describes a configurable parameter.
        """
        pass

    @abstractmethod
    def read_bms_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads dynamic data from the BMS.

        This is the core data reading method that concrete plugins must implement.
        It should handle the communication with the BMS device, decode the raw data,
        and return it as a flat dictionary using the standardized BMS keys
        (e.g., `BMS_KEY_SOC`, `BMS_KEY_VOLTAGE`).

        Returns:
            Optional[Dict[str, Any]]: A flat dictionary of BMS data, or None if
                                      the read operation fails.
        """
        pass

    @abstractmethod
    def get_bms_static_info(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves static information from the BMS.

        Concrete plugins must implement this method to read static data such as
        manufacturer, model, and serial number from the device.

        Returns:
            Optional[Dict[str, Any]]: A flat dictionary containing the static
                                      information, or None on failure.
        """
        pass

    def read_static_data(self) -> Dict[str, Any]:
        """
        Reads and standardizes static data from the BMS.

        This method wraps the abstract `get_bms_static_info` method. It calls the
        concrete implementation to get the raw static data, ensures the device
        category is set to 'bms', and maps the plugin-specific keys to the
        application-wide `StandardDataKeys`.

        Returns:
            Dict[str, Any]: A dictionary of standardized static data.
        """
        static_info = self.get_bms_static_info()
        processed_static_data: Dict[str, Any] = static_info if static_info else {}
        
        processed_static_data[StandardDataKeys.STATIC_DEVICE_CATEGORY] = "bms"
        
        standardized_data = {}
        key_map = {
            BMS_KEY_MANUFACTURER: StandardDataKeys.STATIC_BATTERY_MANUFACTURER,
            BMS_KEY_MODEL: StandardDataKeys.STATIC_BATTERY_MODEL_NAME,
            BMS_KEY_SERIAL_NUMBER: StandardDataKeys.STATIC_BATTERY_SERIAL_NUMBER,
            BMS_KEY_FIRMWARE_VERSION: StandardDataKeys.STATIC_BATTERY_FIRMWARE_VERSION,
            BMS_KEY_HARDWARE_VERSION: StandardDataKeys.STATIC_BMS_HARDWARE_VERSION,
        }
        for old_key, value in processed_static_data.items():
            new_key = key_map.get(old_key, old_key)
            standardized_data[new_key] = value

        if StandardDataKeys.STATIC_DEVICE_CATEGORY not in standardized_data:
            standardized_data[StandardDataKeys.STATIC_DEVICE_CATEGORY] = "bms"
            
        return standardized_data

    def read_dynamic_data(self) -> Dict[str, Any]:
        """
        Reads, processes, and standardizes dynamic data from the BMS.

        This is the main entry point for the polling loop. It calls the abstract
        `read_bms_data` method to get the raw data from the concrete plugin.
        It then processes this data to generate a categorized list of alerts
        from any reported alarms or warnings and adds a standardized UTC timestamp.

        If the read fails, it returns a minimal dictionary indicating the error state.

        Returns:
            Dict[str, Any]: A dictionary of standardized dynamic data, including
                            alerts and a timestamp.
        """
        processed_dynamic_data = self.read_bms_data()

        if not processed_dynamic_data: 
            self.logger.warning(f"BMS Plugin '{self.instance_name}': read_bms_data returned None. Propagating as a read failure.")
            return None
        
        # This will become the value for OPERATIONAL_CATEGORIZED_ALERTS_DICT
        bms_alerts_for_category: List[str] = []

        alarms_val = processed_dynamic_data.get(BMS_KEY_ACTIVE_ALARMS_LIST, [])
        warnings_val = processed_dynamic_data.get(BMS_KEY_ACTIVE_WARNINGS_LIST, [])
        
        alarms = alarms_val if isinstance(alarms_val, list) else ([alarms_val] if alarms_val else [])
        warnings = warnings_val if isinstance(warnings_val, list) else ([warnings_val] if warnings_val else [])
        
        if alarms: bms_alerts_for_category.extend([f"ALARM: {str(a)}" for a in alarms])
        if warnings: bms_alerts_for_category.extend([f"WARN: {str(w)}" for w in warnings])
        
        fault_summary = processed_dynamic_data.get(BMS_KEY_FAULT_SUMMARY)
        if fault_summary and isinstance(fault_summary, str) and fault_summary.lower() not in ["normal", "ok", ""]:
            bms_alerts_for_category.append(f"Summary: {fault_summary}")

        bms_status = processed_dynamic_data.get(BMS_KEY_STATUS_TEXT)
        if bms_status and isinstance(bms_status, str) and \
           bms_status.lower() not in ["normal", "ok", "idle", "standby", "unknown", "read error"] and \
           not any(bms_status in s for s in bms_alerts_for_category):
            bms_alerts_for_category.append(f"State: {bms_status}")
        
        processed_dynamic_data[StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT] = {
            "bms": bms_alerts_for_category if bms_alerts_for_category else ["OK"]
        }
        
        bms_plugin_update_iso = processed_dynamic_data.get(BMS_PLUGIN_LAST_UPDATE)
        if isinstance(bms_plugin_update_iso, str):
            try:
                dt_obj = datetime.fromisoformat(bms_plugin_update_iso.replace("Z", "+00:00"))
                if dt_obj.tzinfo is None:
                    dt_obj = dt_obj.replace(tzinfo=timezone.utc) 
                else:
                    dt_obj = dt_obj.astimezone(timezone.utc)
                processed_dynamic_data[StandardDataKeys.PLUGIN_DATA_TIMESTAMP_MS_UTC] = int(dt_obj.timestamp() * 1000)
            except ValueError as e_ts:
                self.logger.warning(f"BMS Plugin '{self.instance_name}': Could not parse timestamp '{bms_plugin_update_iso}': {e_ts}. Using current time.")
                processed_dynamic_data[StandardDataKeys.PLUGIN_DATA_TIMESTAMP_MS_UTC] = int(datetime.now(timezone.utc).timestamp() * 1000)
        elif StandardDataKeys.PLUGIN_DATA_TIMESTAMP_MS_UTC not in processed_dynamic_data:
            processed_dynamic_data[StandardDataKeys.PLUGIN_DATA_TIMESTAMP_MS_UTC] = int(datetime.now(timezone.utc).timestamp() * 1000)

        return processed_dynamic_data

    @abstractmethod
    def connect(self) -> bool:
        """
        Establishes a connection to the BMS device.

        Concrete plugins must implement this method to handle the specifics of
        connecting to their target device (e.g., opening a serial port or a
        TCP socket).

        Returns:
            bool: True on successful connection, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnects from the BMS device.

        Concrete plugins must implement this method to gracefully close the
        connection to their target device.
        """
        pass