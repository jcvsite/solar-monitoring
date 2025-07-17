# plugins/battery/seplos_bms_v2.py
import time
import serial
from serial.serialutil import SerialException, SerialTimeoutException
import socket 
import logging
from typing import Any, Dict, Optional, List, Union, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from core.app_state import AppState
from datetime import datetime
import copy 

try:
    from ..plugin_utils import check_tcp_port, check_icmp_ping 
except ImportError:
    try:
        from plugin_utils import check_tcp_port, check_icmp_ping
    except ImportError:
        # Minimal fallback if plugin_utils is not available at all
        def check_tcp_port(host: str, port: int, timeout: float = 2.0, logger_instance: Optional[logging.Logger] = None) -> Tuple[bool, float, Optional[str]]:
            if logger_instance: logger_instance.error("plugin_utils.check_tcp_port not found (fallback used)!")
            else: logging.getLogger(__name__).error("plugin_utils.check_tcp_port not found (fallback used)!")
            return False, -1.0, "Util not found"
        def check_icmp_ping(host: str, count: int = 1, timeout_s: int = 1, logger_instance: Optional[logging.Logger] = None) -> Tuple[bool, float, Optional[str]]:
            if logger_instance: logger_instance.error("plugin_utils.check_icmp_ping not found (fallback used)!")
            else: logging.getLogger(__name__).error("plugin_utils.check_icmp_ping not found (fallback used)!")
            return False, -1.0, "Util not found"

try:
    from .bms_plugin_base import (
        BMSPluginBase, StandardDataKeys,
        BMS_KEY_SOC, BMS_KEY_SOH, BMS_KEY_VOLTAGE, BMS_KEY_CURRENT, BMS_KEY_POWER,
        BMS_KEY_REMAINING_CAPACITY_AH, BMS_KEY_FULL_CAPACITY_AH, BMS_KEY_NOMINAL_CAPACITY_AH,
        BMS_KEY_CYCLE_COUNT, BMS_KEY_TEMPERATURES_ALL, BMS_KEY_TEMP_SENSOR_PREFIX,
        BMS_KEY_TEMP_MAX, BMS_KEY_TEMP_MIN,
        BMS_KEY_CELL_COUNT, BMS_KEY_CELL_VOLTAGE_PREFIX, BMS_KEY_CELL_VOLTAGES_ALL,
        BMS_KEY_CELL_VOLTAGE_MIN, BMS_KEY_CELL_VOLTAGE_MAX, BMS_KEY_CELL_VOLTAGE_AVG, BMS_KEY_CELL_VOLTAGE_DIFF,
        BMS_KEY_CELL_BALANCE_ACTIVE_PREFIX, BMS_KEY_CELLS_BALANCING,
        BMS_KEY_STATUS_TEXT, BMS_KEY_CHARGE_FET_ON, BMS_KEY_DISCHARGE_FET_ON,
        BMS_KEY_FAULT_SUMMARY, BMS_KEY_ACTIVE_ALARMS_LIST, BMS_KEY_ACTIVE_WARNINGS_LIST,
        BMS_KEY_MANUFACTURER, BMS_KEY_MODEL, BMS_KEY_SERIAL_NUMBER, BMS_KEY_FIRMWARE_VERSION, BMS_KEY_HARDWARE_VERSION,
        BMS_PLUGIN_LAST_UPDATE, BMS_KEY_CELL_DISCONNECTION_PREFIX 
    )
except ImportError:
    try:
        from bms_plugin_base import ( # type: ignore
            BMSPluginBase, StandardDataKeys,
            BMS_KEY_SOC, BMS_KEY_SOH, BMS_KEY_VOLTAGE, BMS_KEY_CURRENT, BMS_KEY_POWER,
            BMS_KEY_REMAINING_CAPACITY_AH, BMS_KEY_FULL_CAPACITY_AH, BMS_KEY_NOMINAL_CAPACITY_AH,
            BMS_KEY_CYCLE_COUNT, BMS_KEY_TEMPERATURES_ALL, BMS_KEY_TEMP_SENSOR_PREFIX,
            BMS_KEY_TEMP_MAX, BMS_KEY_TEMP_MIN,
            BMS_KEY_CELL_COUNT, BMS_KEY_CELL_VOLTAGE_PREFIX, BMS_KEY_CELL_VOLTAGES_ALL,
            BMS_KEY_CELL_VOLTAGE_MIN, BMS_KEY_CELL_VOLTAGE_MAX, BMS_KEY_CELL_VOLTAGE_AVG, BMS_KEY_CELL_VOLTAGE_DIFF,
            BMS_KEY_CELL_BALANCE_ACTIVE_PREFIX, BMS_KEY_CELLS_BALANCING,
            BMS_KEY_STATUS_TEXT, BMS_KEY_CHARGE_FET_ON, BMS_KEY_DISCHARGE_FET_ON,
            BMS_KEY_FAULT_SUMMARY, BMS_KEY_ACTIVE_ALARMS_LIST, BMS_KEY_ACTIVE_WARNINGS_LIST,
            BMS_KEY_MANUFACTURER, BMS_KEY_MODEL, BMS_KEY_SERIAL_NUMBER, BMS_KEY_FIRMWARE_VERSION, BMS_KEY_HARDWARE_VERSION,
            BMS_PLUGIN_LAST_UPDATE, BMS_KEY_CELL_DISCONNECTION_PREFIX
        )
    except ImportError as e:
        raise ImportError(f"Could not import BMSPluginBase or StandardDataKeys. Ensure bms_plugin_base.py is accessible. Original error: {e}")


# --- Seplos Protocol Constants ---
CMD_READ_TELEMETRY = 0x42  # Command to read telemetry data (voltages, temps, etc.)
CMD_READ_TELESIGNALIZATION = 0x44  # Command to read status flags (alarms, warnings, etc.)
PROTOCOL_VERSION = 0x20  # Protocol version for the frame
PC_COMMAND_CID1 = 0x46  # CID1 (Command ID 1) used by PC when sending commands
BMS_RESPONSE_SUCCESS_CID1 = 0x00  # Expected CID1 from BMS on a successful data response

DEFAULT_BAUD_RATE_SEPLOS = 19200
DEFAULT_TCP_PORT_SEPLOS = 8888 
DEFAULT_TCP_TIMEOUT_SECONDS = 5.0 # Default overall timeout for TCP operations

# Data Validation Ranges
MIN_VALID_CELL_V = 1.0
MAX_VALID_CELL_V = 5.0
MIN_VALID_TEMP_C = -40.0
MAX_VALID_TEMP_C = 125.0
MIN_VALID_SOC = 0.0
MAX_VALID_SOC = 105.0 
MIN_VALID_SOH = 0.0
MAX_VALID_SOH = 100.0
MIN_VALID_CYCLE = 0
UNKNOWN = "Unknown"
ERROR_READ = "read_error"
DEFAULT_PLUGIN_NON_DATA_VALUES_LOWER = {
    None, "init", "unknown", "n/a", "error", ERROR_READ.lower(), 
    "proc_error", "decode_error", "n/a_config"
}


class SeplosBMSV2(BMSPluginBase):
    """
    Plugin to communicate with Seplos V2 protocol BMS devices.

    This class implements the `BMSPluginBase` for Seplos V2 protocol BMS devices.
    It supports both serial and TCP connections. It handles encoding commands,
    sending them, receiving responses, and decoding the telemetry and
    telesignalization data into a standardized format.
    """
    # --- Telemetry Payload Offsets (in bytes, after ASCII hex to string conversion) ---
    _TEL_NUM_CELLS_OFFSET = 4       
    _TEL_CELL_V_START_OFFSET = 6    
    _TEL_TEMP_START_OFFSET = 72     
    _TEL_CURRENT_OFFSET = 96        
    _TEL_VOLTAGE_OFFSET = 100       
    _TEL_RES_CAP_OFFSET = 104       
    _TEL_BMS_CAP_OFFSET = 110       
    _TEL_SOC_OFFSET = 114           
    _TEL_RATED_CAP_OFFSET = 118     
    _TEL_CYCLES_OFFSET = 122        
    _TEL_SOH_OFFSET = 126           
    _TEL_PORT_V_OFFSET = 130           
    
    TELESIGNALIZATION_SIGNALS = [
        {"name": "voltage_sensing_failure", "byte": 29, "bit": 0, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "temp_sensing_failure", "byte": 29, "bit": 1, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "current_sensing_failure", "byte": 29, "bit": 2, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "power_switch_failure", "byte": 29, "bit": 3, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "cell_voltage_difference_sensing_failure", "byte": 29, "bit": 4, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "charging_switch_failure", "byte": 29, "bit": 5, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "discharging_switch_failure", "byte": 29, "bit": 6, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "current_limit_switch_failure", "byte": 29, "bit": 7, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "cell_overvoltage_warning_flag", "byte": 30, "bit": 0, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "cell_overvoltage_protection_flag", "byte": 30, "bit": 1, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "cell_voltage_low_warning_flag", "byte": 30, "bit": 2, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "cell_voltage_low_protection_flag", "byte": 30, "bit": 3, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "pack_overvoltage_warning_flag", "byte": 30, "bit": 4, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "pack_overvoltage_protection_flag", "byte": 30, "bit": 5, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "pack_voltage_low_warning_flag", "byte": 30, "bit": 6, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "pack_voltage_low_protection_flag", "byte": 30, "bit": 7, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "charging_temp_high_warning_flag", "byte": 31, "bit": 0, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "charging_temp_high_protection_flag", "byte": 31, "bit": 1, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "charging_temp_low_warning_flag", "byte": 31, "bit": 2, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "charging_temp_low_protection_flag", "byte": 31, "bit": 3, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "discharging_temp_high_warning_flag", "byte": 31, "bit": 4, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "discharging_temp_high_protection_flag", "byte": 31, "bit": 5, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "discharging_temp_low_warning_flag", "byte": 31, "bit": 6, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "discharging_temp_low_protection_flag", "byte": 31, "bit": 7, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "ambient_temp_high_warning_flag", "byte": 32, "bit": 0, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "ambient_temp_high_protection_flag", "byte": 32, "bit": 1, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "ambient_temp_low_warning_flag", "byte": 32, "bit": 2, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "ambient_temp_low_protection_flag", "byte": 32, "bit": 3, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "component_temp_high_protection_flag", "byte": 32, "bit": 4, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "component_temp_high_warning_flag", "byte": 32, "bit": 5, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "cell_low_temp_heating", "byte": 32, "bit": 6, "type": "status", "on": "heating", "off": "idle"},
        {"name": "over_temp_air_cooled", "byte": 32, "bit": 7, "type": "status", "on": "cooling", "off": "idle"},
        {"name": "charging_overcurrent_warning_flag", "byte": 33, "bit": 0, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "charging_overcurrent_protection_flag", "byte": 33, "bit": 1, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "discharging_overcurrent_warning_flag", "byte": 33, "bit": 2, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "discharging_overcurrent_protection_flag", "byte": 33, "bit": 3, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "transient_overcurrent_protection_flag", "byte": 33, "bit": 4, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "output_short_circuit_protection_flag", "byte": 33, "bit": 5, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "transient_overcurrent_lock", "byte": 33, "bit": 6, "type": "protect", "on": "locked", "off": "normal"},
        {"name": "output_short_circuit_lock", "byte": 33, "bit": 7, "type": "protect", "on": "locked", "off": "normal"},
        {"name": "charging_high_voltage_protection_flag", "byte": 34, "bit": 0, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "intermittent_power_supplement", "byte": 34, "bit": 1, "type": "status", "on": "active", "off": "idle"},
        {"name": "soc_low_warning_flag", "byte": 34, "bit": 2, "type": "warn", "on": "warning", "off": "normal"},
        {"name": "soc_low_protection_flag", "byte": 34, "bit": 3, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "cell_low_voltage_forbidden_charging", "byte": 34, "bit": 4, "type": "protect", "on": "charging_forbidden", "off": "normal"},
        {"name": "output_reverse_protection", "byte": 34, "bit": 5, "type": "protect", "on": "protection", "off": "normal"},
        {"name": "output_connection_failure", "byte": 34, "bit": 6, "type": "protect", "on": "failure", "off": "normal"},
        {"name": "discharge_switch", "byte": 35, "bit": 0, "type": "status", "on": "on", "off": "off"},
        {"name": "charge_switch", "byte": 35, "bit": 1, "type": "status", "on": "on", "off": "off"},
        {"name": "current_limit_switch", "byte": 35, "bit": 2, "type": "status", "on": "on", "off": "off"},
        {"name": "heating_limit_switch", "byte": 35, "bit": 3, "type": "status", "on": "on", "off": "off"}, # Max 16 cells for this part of bitfield
        *[{"name": f"cell_equalization_{i+1}", "byte": 36 + (i // 8), "bit": i % 8, "type": "status", "on": "balancing", "off": "idle"} for i in range(16)], # Max 16 cells for this part of bitfield
        {"name": "discharge_status_flag", "byte": 38, "bit": 0, "type": "status", "on": "discharging", "off": "not_discharging"},
        {"name": "charge_status_flag", "byte": 38, "bit": 1, "type": "status", "on": "charging", "off": "not_charging"},
        {"name": "floating_charge_status_flag", "byte": 38, "bit": 2, "type": "status", "on": "floating", "off": "not_floating"},
        {"name": "standby_status_flag", "byte": 38, "bit": 4, "type": "status", "on": "standby", "off": "not_standby"},
        {"name": "power_off_status_flag", "byte": 38, "bit": 5, "type": "status", "on": "power_off", "off": "power_on"},
        {"name": "auto_charging_wait", "byte": 41, "bit": 4, "type": "status", "on": "waiting_auto_charge", "off": "normal"},
        {"name": "manual_charging_wait", "byte": 41, "bit": 5, "type": "status", "on": "waiting_manual_charge", "off": "normal"},
        {"name": "eep_storage_failure", "byte": 42, "bit": 0, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "rtc_clock_failure", "byte": 42, "bit": 1, "type": "warn", "on": "failure", "off": "normal"},
        {"name": "no_calibration_of_voltage", "byte": 42, "bit": 2, "type": "warn", "on": "uncalibrated", "off": "calibrated"},
        {"name": "no_calibration_of_current", "byte": 42, "bit": 3, "type": "warn", "on": "uncalibrated", "off": "calibrated"},
        {"name": "no_calibration_of_null_point", "byte": 42, "bit": 4, "type": "warn", "on": "uncalibrated", "off": "calibrated"},
        {"name": "perpetual_calendar_not_synced", "byte": 42, "bit": 5, "type": "warn", "on": "not_synced", "off": "synced"},
    ]

    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the SeplosBMSV2 plugin.

        It reads connection-specific configuration (serial or TCP), sets up
        timeouts, and validates the provided settings. If the configuration is
        invalid, the plugin is disabled.

        Args:
            See `BMSPluginBase` for argument details.
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)

        self.connection_type = self.plugin_config.get("seplos_connection_type", "serial").strip().lower()
        self.serial_port_name = self.plugin_config.get("seplos_serial_port")
        self.baud_rate = int(self.plugin_config.get("seplos_baud_rate", DEFAULT_BAUD_RATE_SEPLOS))
        self.tcp_host = self.plugin_config.get("seplos_tcp_host")
        self.tcp_port = int(self.plugin_config.get("seplos_tcp_port", DEFAULT_TCP_PORT_SEPLOS))
        
        self.serial_operation_timeout = float(self.plugin_config.get("seplos_serial_operation_timeout", 2.5))
        
        self.pack_address = int(self.plugin_config.get("seplos_pack_address", 0)) 

        self._orig_tcp_timeout = float(self.plugin_config.get("seplos_tcp_timeout", DEFAULT_TCP_TIMEOUT_SECONDS))
        self.tcp_timeout = self._orig_tcp_timeout 

        self.inter_command_delay_ms = int(self.plugin_config.get("seplos_inter_command_delay_ms", 200))

        self._user_set_params = {
            "seplos_tcp_timeout": "seplos_tcp_timeout" in self.plugin_config,
        }
        self.measured_rtt_ms: Optional[float] = None
        
        self.client: Union[serial.Serial, socket.socket, None] = None
        self.receive_buffer = bytearray()
        self.last_error_message: Optional[str] = None

        log_conn_params = f"Instance: '{self.instance_name}', Type: {self.connection_type}, PackAddr: {self.pack_address:02X}"
        valid_config = True
        if self.connection_type == "serial":
            log_conn_params += f", Port: {self.serial_port_name}, Baud: {self.baud_rate}, OpTimeout: {self.serial_operation_timeout}s"
            if not self.serial_port_name:
                 self.logger.error(f"SeplosBMSV2 {log_conn_params} - ERROR: 'seplos_serial_port' not configured.")
                 valid_config = False
        elif self.connection_type == "tcp":
            log_conn_params += f", Host: {self.tcp_host}, Port: {self.tcp_port}, TCPTimeout: {self.tcp_timeout}s"
            if not self.tcp_host:
                 self.logger.error(f"SeplosBMSV2 {log_conn_params} - ERROR: 'seplos_tcp_host' not configured.")
                 valid_config = False
        else:
            self.logger.error(f"SeplosBMSV2 '{self.instance_name}': Invalid 'seplos_connection_type' ('{self.connection_type}'). Must be 'serial' or 'tcp'. Plugin disabled.")
            self.connection_type = "disabled" 
            valid_config = False
            
        if not valid_config:
            self.connection_type = "disabled" 
            self.last_error_message = "Plugin configuration error (see logs)"

        self.logger.info(f"SeplosBMSV2 Plugin Initialized (Synchronous Mode): {log_conn_params}")

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "seplos_bms_v2"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin, including the connection type."""
        if self.connection_type == "disabled":
            return f"Seplos BMS (Config Error)"
        return f"Seplos BMS ({self.connection_type.capitalize()})"

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        """
        Returns a list of configuration parameters that this plugin supports.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary
                                  describes a configurable parameter.
        """
        return [
            {"name": "SEPLOS_CONNECTION_TYPE", "type": str, "default": "serial", "description": "Connection type: 'serial' or 'tcp'.", "options": ["serial", "tcp"]},
            {"name": "SEPLOS_SERIAL_PORT", "type": str, "default": None, "description": "Serial port (if type is 'serial'). E.g., /dev/ttyUSB0 or COM3."},
            {"name": "SEPLOS_BAUD_RATE", "type": int, "default": DEFAULT_BAUD_RATE_SEPLOS, "description": "Baud rate for serial connection."},
            {"name": "SEPLOS_TCP_HOST", "type": str, "default": None, "description": "IP Address or Hostname of BMS (if type is 'tcp')."},
            {"name": "SEPLOS_TCP_PORT", "type": int, "default": DEFAULT_TCP_PORT_SEPLOS, "description": "TCP Port for BMS (if type is 'tcp')."},
            {"name": "SEPLOS_TCP_TIMEOUT", "type": float, "default": DEFAULT_TCP_TIMEOUT_SECONDS, "description": "TCP connection and read timeout."},
            {"name": "SEPLOS_SERIAL_OPERATION_TIMEOUT", "type": float, "default": 2.5, "description": "Overall timeout for serial send/receive operations."},
            {"name": "SEPLOS_PACK_ADDRESS", "type": int, "default": 0, "description": "Pack address (0-15 decimal)."},
            {"name": "SEPLOS_INTER_COMMAND_DELAY_MS", "type": int, "default": 200, "description": "Delay (ms) between sending commands to the BMS."},
            {"name": "SEPLOS_MANUFACTURER", "type": str, "default": "Seplos", "description": "Static: Manufacturer name."},
            {"name": "SEPLOS_MODEL", "type": str, "default": "Seplos V2 Protocol", "description": "Static: Model name."},
            {"name": "SEPLOS_SERIAL_NUMBER", "type": str, "default": "N/A_Config", "description": "Static: Serial number."},
        ]

    def auto_adjust_params(self, measured_rtt_ms: float):
        """
        Dynamically adjusts the TCP timeout based on a measured network RTT.

        This is only applicable for TCP connections and is not used if the user
        has explicitly set a timeout in the configuration.

        Args:
            measured_rtt_ms (float): The measured round-trip time in milliseconds.
        """
        if self.connection_type != "tcp": return
        self.measured_rtt_ms = measured_rtt_ms
        self.logger.info(f"SeplosBMSV2 '{self.instance_name}': Auto-adjusting params based on RTT: {measured_rtt_ms:.2f} ms")
        original_params_log = f"(Original TCP Timeout: {self._orig_tcp_timeout}s)"

        if not self._user_set_params["seplos_tcp_timeout"]:
            op_timeout_s = (measured_rtt_ms / 1000.0) * 4.0 + 2.0
            
            self.tcp_timeout = max(3.0, min(10.0, round(op_timeout_s, 1)))
            self.logger.info(f"SeplosBMSV2 '{self.instance_name}': Auto-adjusted TCP timeout to: {self.tcp_timeout}s. {original_params_log}")
        else:
            self.logger.info(f"SeplosBMSV2 '{self.instance_name}': seplos_tcp_timeout is user-set to {self._orig_tcp_timeout}s, not auto-adjusting.")

    def connect(self) -> bool:
        """
        Establishes a connection to the BMS.

        For TCP, it performs a pre-connection network check. It handles both
        serial and TCP connection logic.

        Returns:
            bool: True on successful connection, False otherwise.
        """
        if self._is_connected_flag and self.client:
            return True
        if self.client: self.disconnect()
        self.last_error_message = "Plugin disabled (config error)" if self.connection_type == "disabled" else None

        if self.connection_type == "tcp":
            if not self.tcp_host: self.last_error_message = "TCP Host not configured"; return False
            self.logger.info(f"SeplosBMSV2 '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
            port_open, rtt_ms, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open:
                self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} unreachable. Error: {err_msg}"
                self.logger.error(self.last_error_message)
                icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                if not icmp_ok: self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host may be down.")
                return False
            self.auto_adjust_params(rtt_ms)

        try:
            if self.connection_type == "serial":
                self.logger.info(f"SeplosBMSV2 '{self.instance_name}': Connecting to {self.serial_port_name}...")
                self.client = serial.Serial(port=self.serial_port_name, baudrate=self.baud_rate, timeout=1.5, write_timeout=1.0)
            elif self.connection_type == "tcp":
                self.logger.info(f"SeplosBMSV2 '{self.instance_name}': Connecting to {self.tcp_host}:{self.tcp_port}...")
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(self.tcp_timeout)
                self.client.connect((self.tcp_host, self.tcp_port))
            else: return False

            self._is_connected_flag = True
            self.logger.info(f"SeplosBMSV2 '{self.instance_name}': Successfully connected.")
            return True
        except Exception as e:
            self.last_error_message = f"Connection failed: {e}"
            self.logger.error(f"SeplosBMSV2 '{self.instance_name}': {self.last_error_message}", exc_info=True)
            if self.client:
                try: self.client.close()
                except: pass
            self.client = None
            self._is_connected_flag = False
            return False

    def disconnect(self) -> None:
        """Gracefully disconnects from the BMS, closing the serial port or TCP socket."""
        conn_type_msg = f"({self.connection_type.capitalize()})" if self.connection_type and self.connection_type != "disabled" else ""
        if self.client:
            self.logger.info(f"SeplosBMSV2 '{self.instance_name}' {conn_type_msg}: Disconnecting...")
            try:
                if self.connection_type == "serial" and isinstance(self.client, serial.Serial) and self.client.is_open:
                    self.client.close()
                elif self.connection_type == "tcp" and isinstance(self.client, socket.socket):
                    try: self.client.shutdown(socket.SHUT_RDWR)
                    except socket.error: pass 
                    self.client.close()
            except Exception as e: self.logger.error(f"SeplosBMSV2 '{self.instance_name}' {conn_type_msg}: Error during disconnect: {e}")
        self._is_connected_flag = False
        self.client = None

    @staticmethod
    def _calculate_frame_checksum(frame_content_bytes: bytes) -> int:
        """
        Calculates the checksum for a Seplos protocol frame.

        The checksum is a 16-bit value calculated as the two's complement of the
        sum of all bytes in the frame content.

        Args:
            frame_content_bytes (bytes): The bytes of the frame content to be checksummed.

        Returns:
            int: The calculated 16-bit checksum.
        """
        s = sum(frame_content_bytes)
        lcs = s & 0xFFFF
        lcs = (lcs ^ 0xFFFF) + 1
        return lcs & 0xFFFF

    @staticmethod
    def _get_info_length(info_ascii_hex_bytes: bytes) -> int:
        """
        Calculates the `LENID` field for a Seplos command frame.

        This field encodes both the length of the INFO field and a simple
        checksum of the length digits.

        Returns:
            int: The calculated LENID value.
        """
        lenid = len(info_ascii_hex_bytes)
        if lenid > 0xFFF: lenid = 0xFFF 
        lchksum_calc = sum((lenid >> (i * 4)) & 0xF for i in range(3))
        lchksum_calc %= 16
        lchksum_calc = (lchksum_calc ^ 0xF) + 1
        lchksum_calc %= 16
        return (lchksum_calc << 12) | lenid

    def _encode_cmd(self, cid2: int) -> bytes:
        """
        Encodes a command for the Seplos BMS.

        It constructs the full frame, including start/end delimiters, headers,
        INFO payload, and checksum.

        Args:
            cid2 (int): The Command ID 2 for the specific command.

        Returns:
            bytes: The fully encoded command frame, ready to be sent.
        """
        info_ascii_hex_bytes = b"01" # Standard INFO for commands
        lenid_field_val = self._get_info_length(info_ascii_hex_bytes)
        frame_part_for_checksum_str = (
            f"{PROTOCOL_VERSION:02X}"
            f"{self.pack_address:02X}" 
            f"{PC_COMMAND_CID1:02X}"   
            f"{cid2:02X}"              
            f"{lenid_field_val:04X}"
        )
        frame_part_for_checksum_bytes = frame_part_for_checksum_str.encode('ascii') + info_ascii_hex_bytes
        checksum = self._calculate_frame_checksum(frame_part_for_checksum_bytes)
        full_frame_str = (
            "~" + frame_part_for_checksum_str + info_ascii_hex_bytes.decode('ascii') + 
            f"{checksum:04X}" + "\r"
        )
        return full_frame_str.encode('ascii')

    def _is_valid_frame(self, data: bytes, sent_cid2: Optional[int] = None) -> bool:
        """
        Validates a received data frame from the BMS.

        It checks for correct start/end delimiters, CIDs, checksum, and INFO
        field length.

        Args:
            data (bytes): The raw bytes of the frame candidate.
            sent_cid2 (Optional[int]): The CID2 of the command that was sent,
                                       used to validate the response.
        """
        min_len_no_info = 16 
        if not data or len(data) < min_len_no_info : 
            self.last_error_message = f"Frame too short (len {len(data) if data else 0} < {min_len_no_info})"; return False
        if data[0:1] != b"~":
            self.last_error_message = "Invalid frame start (missing ~)"; return False
        if data[-1:] != b"\r":
            self.last_error_message = "Invalid frame end (missing CR)"; return False
        
        sent_cid2_log_str = f"{sent_cid2:02X}" if sent_cid2 is not None else "N/A (None)"

        try:
            cid1_resp_hex_str = data[5:7].decode('ascii')
            cid2_resp_hex_str = data[7:9].decode('ascii', errors='ignore') 
            cid1_resp_val = int(cid1_resp_hex_str, 16)
            
            try: cid2_resp_val = int(cid2_resp_hex_str, 16)
            except ValueError: self.last_error_message = f"Invalid CID2 hex ('{cid2_resp_hex_str}')"; return False 

            is_data_query = (sent_cid2 is not None and (sent_cid2 == CMD_READ_TELEMETRY or sent_cid2 == CMD_READ_TELESIGNALIZATION))
            
            if is_data_query:
                if not (cid1_resp_val == BMS_RESPONSE_SUCCESS_CID1 and cid2_resp_val == sent_cid2) and \
                   not (cid1_resp_val == PC_COMMAND_CID1 and cid2_resp_val == BMS_RESPONSE_SUCCESS_CID1): # Quirk check
                    self.last_error_message = f"Invalid CIDs for data response (SentCID2:{sent_cid2_log_str}, GotCIDs:{cid1_resp_hex_str}/{cid2_resp_hex_str})"
                    return False
            elif cid1_resp_val != BMS_RESPONSE_SUCCESS_CID1: # Non-data command error
                self.last_error_message = f"BMS Error CID1:{cid1_resp_hex_str} (SentCID2:{sent_cid2_log_str})"
                return False

            frame_part_to_checksum = data[1:-5] 
            calculated_chksum = self._calculate_frame_checksum(frame_part_to_checksum)
            received_checksum_hex_str = data[-5:-1].decode('ascii')
            received_chksum_val = int(received_checksum_hex_str, 16)
            if calculated_chksum != received_chksum_val:
                self.last_error_message = f"Checksum mismatch (Calc:{calculated_chksum:04X},Recv:{received_checksum_hex_str})"; return False

            lenid_field_hex_str = data[9:13].decode('ascii')
            lenid_field_val = int(lenid_field_hex_str, 16)
            declared_info_len = lenid_field_val & 0xFFF 
            actual_info_len = len(data[13:-5]) 
            if actual_info_len != declared_info_len:
                self.last_error_message = f"INFO length mismatch (Declared:{declared_info_len},Actual:{actual_info_len})"; return False
            
            self.last_error_message = None 
            return True 
        except (UnicodeError, ValueError, IndexError) as e:
            self.logger.debug(f"S'{self.instance_name}': Frame validation parsing error: {e}, data: {data!r}")
            self.last_error_message = f"Frame validation parsing error: {str(e)}"; return False
        except Exception as e_unexp: 
            self.logger.error(f"S'{self.instance_name}': Unexpected frame validation error: {e_unexp}, data: {data!r}", exc_info=True)
            self.last_error_message = f"Unexpected frame validation error: {str(e_unexp)}"; return False

    def _extract_and_validate_frame_from_buffer(self, sent_cid2: Optional[int]) -> Optional[bytes]:
        """
        Scans the receive buffer for a complete and valid Seplos frame.

        It handles and discards any leading garbage data. If a valid frame is
        found, it's removed from the buffer and its INFO payload is returned.
        Sets `self.last_error_message` if an invalid frame is found.
        """
        MIN_FRAME_LEN = 16
        MAX_FRAME_LEN = 200  # Safety limit for searching for the end delimiter

        while True: # Loop to find the first valid frame, discarding garbage before it
            start_index = self.receive_buffer.find(b"~")

            if start_index == -1: # No start delimiter found at all
                if len(self.receive_buffer) > MAX_FRAME_LEN * 2: # Buffer is full of junk
                    self.logger.warning(f"S '{self.instance_name}': Receive buffer ({len(self.receive_buffer)} bytes) contains no '~', discarding.")
                    self.receive_buffer.clear()
                self.last_error_message = "No frame start delimiter '~' found in buffer"
                return None

            if start_index > 0: # Garbage before the first '~'
                garbage = self.receive_buffer[:start_index]
                self.logger.debug(f"S '{self.instance_name}': Discarding {len(garbage)} bytes of leading garbage from buffer: {garbage!r}")
                self.receive_buffer = self.receive_buffer[start_index:]
            
            # Buffer now starts with '~' or is empty if only garbage was there
            if not self.receive_buffer: return None

            # Search for end delimiter '\r' within a reasonable distance
            search_len_for_end = min(len(self.receive_buffer), MAX_FRAME_LEN)
            end_index = self.receive_buffer.find(b"\r", 0, search_len_for_end)

            if end_index != -1:
                frame_candidate = bytes(self.receive_buffer[:end_index+1])
                self.logger.debug(f"S '{self.instance_name}': Extracted frame candidate from buffer ({len(frame_candidate)} bytes): {frame_candidate!r}")

                if self._is_valid_frame(frame_candidate, sent_cid2):
                    self.logger.info(f"S '{self.instance_name}': Valid frame found and decoded from buffer for sent_cid2={sent_cid2 if sent_cid2 is not None else 'N/A'}.")
                    self.receive_buffer = self.receive_buffer[end_index+1:] # Consume frame
                    return frame_candidate[13:-5] # Return INFO payload
                else:
                    # Invalid frame, self.last_error_message is set by _is_valid_frame
                    self.logger.warning(f"S '{self.instance_name}': Invalid frame candidate from buffer. Error: {self.last_error_message}. Discarding: {frame_candidate!r}")
                    self.receive_buffer = self.receive_buffer[end_index+1:] # Consume invalid frame
                    # Continue loop to see if there's another frame in the buffer
            else:
                # No end delimiter found within MAX_FRAME_LEN of a '~'
                # If buffer is huge, it might be stuck. Otherwise, frame is incomplete.
                if len(self.receive_buffer) > MAX_FRAME_LEN:
                    self.logger.warning(f"S '{self.instance_name}': Found '~' but no '\\r' in next {MAX_FRAME_LEN} bytes. Buffer len {len(self.receive_buffer)}. Discarding first byte and retrying search.")
                    self.receive_buffer = self.receive_buffer[1:] # Discard the '~' and try again
                else:
                    # Frame is incomplete, wait for more data in next poll cycle
                    self.last_error_message = "Incomplete frame in buffer (no CR after ~ within max len)"
                    return None
        return None # Should not be reached if loop logic is correct


    def _send_receive_seplos_frame(self, command_frame: bytes) -> Optional[bytes]:
        """
        Sends an encoded command to the BMS and handles the response.

        It manages the entire communication cycle, including sending the command,
        reading the response into a buffer, and extracting a valid frame from
        that buffer. It includes timeout logic for the operation.

        Args:
            command_frame (bytes): The encoded command to send.

        Returns:
            Optional[bytes]: The INFO payload of the valid response frame, or None on failure.
        """
        self.last_error_message = None 
        if not self._is_connected_flag or not self.client:
            self.last_error_message = "Client not connected for send/receive"
            if self.connect(): self.logger.info(f"S '{self.instance_name}': Reconnected successfully for S/R.")
            else: return None
        
        cmd_str_for_log = command_frame[7:9].decode(errors='ignore') if len(command_frame) > 8 else "N/A"
        sent_cid2_val_int = -1
        try: sent_cid2_val_int = int(cmd_str_for_log, 16)
        except ValueError: self.logger.warning(f"S '{self.instance_name}': Could not parse sent CMD {cmd_str_for_log} for CID2 value.")


        try:
            if self.connection_type == "serial" and isinstance(self.client, serial.Serial):
                if not self.client.is_open: 
                    self.last_error_message = "Serial port not open for write"; self.disconnect(); return None
                self.client.write(command_frame)
            elif self.connection_type == "tcp" and isinstance(self.client, socket.socket):
                self.client.settimeout(self.tcp_timeout) 
                self.client.sendall(command_frame)
            else: 
                self.last_error_message = "Invalid client type for send"; self.disconnect(); return None
            self.logger.debug(f"S '{self.instance_name}': CMD 0x{cmd_str_for_log} sent. Now attempting to read response...")

            # --- Receive response data and append to buffer ---
            operation_timeout_s = self.tcp_timeout if self.connection_type == "tcp" else self.serial_operation_timeout
            read_end_time = time.monotonic() + operation_timeout_s
            
            # Perform reads to populate self.receive_buffer
            while time.monotonic() < read_end_time:
                remaining_read_time = read_end_time - time.monotonic()
                if remaining_read_time <= 0.01: break 
                
                chunk = None; bytes_in_chunk = 0
                try:
                    if self.connection_type == "serial" and isinstance(self.client, serial.Serial):
                        original_serial_timeout = self.client.timeout 
                        self.client.timeout = min(0.5, remaining_read_time)
                        try: 
                            data_waiting = self.client.in_waiting
                            if data_waiting > 0:
                                chunk = self.client.read(min(data_waiting, 256))
                        finally: self.client.timeout = original_serial_timeout
                    elif self.connection_type == "tcp" and isinstance(self.client, socket.socket):
                        self.client.settimeout(min(0.25, remaining_read_time)) # Short non-blocking attempt
                        received_chunk = self.client.recv(256) 
                        if not received_chunk: 
                            self.last_error_message = "TCP connection closed by BMS during read"; self.disconnect(); return None
                        chunk = received_chunk
                except serial.SerialTimeoutException: self.logger.debug(f"S '{self.instance_name}' (Serial): Individual serial read() timed out.")
                except socket.timeout: self.logger.debug(f"S '{self.instance_name}' (TCP): Individual recv() timed out.")
                except (SerialException, socket.error, IOError) as e_comm_read: 
                    self.last_error_message = f"Comm error during read: {str(e_comm_read)}"; self.disconnect(); return None
                
                if chunk:
                    self.receive_buffer.extend(chunk)
                    bytes_in_chunk = len(chunk)
                    self.logger.debug(f"S '{self.instance_name}': Read {bytes_in_chunk} bytes into buffer. Total buffer: {len(self.receive_buffer)}")
                
                if not chunk and remaining_read_time > 0.1:
                    time.sleep(0.05) 
                elif not chunk and remaining_read_time <= 0.1:
                    break

            if self.connection_type == "tcp" and isinstance(self.client, socket.socket):
                try: self.client.settimeout(self.tcp_timeout) # Restore main timeout
                except: pass 

            # After read attempts, try to extract and validate from the buffer
            return self._extract_and_validate_frame_from_buffer(sent_cid2_val_int if sent_cid2_val_int !=-1 else None)

        except Exception as e_sr_outer: 
            self.logger.error(f"S '{self.instance_name}': Outer error in _send_receive for CMD 0x{cmd_str_for_log}: {e_sr_outer}", exc_info=True)
            self.last_error_message = f"Outer S/R error for CMD 0x{cmd_str_for_log}: {str(e_sr_outer)}"
            self.disconnect(); return None
        
        # This path should ideally not be reached if all errors set last_error_message
        if not self.last_error_message: self.last_error_message = "Unknown failure in _send_receive_frame (end)"
        return None # Fallback

    @staticmethod
    def _int_from_1byte_hex_ascii(data_hex_ascii: bytes, offset: int) -> Optional[int]:
        """
        Decodes a 1-byte integer from a 2-character hex ASCII string.

        Args:
            data_hex_ascii (bytes): The byte string containing the hex characters.
            offset (int): The starting position of the 2-char hex string.

        Returns:
            Optional[int]: The decoded integer, or None on failure.
        """
        try:
            if offset + 2 > len(data_hex_ascii): return None
            return int(data_hex_ascii[offset:offset+2].decode("ascii"), 16)
        except (ValueError, UnicodeError, IndexError): return None

    @staticmethod
    def _int_from_2byte_hex_ascii(data_hex_ascii: bytes, offset: int, signed=False) -> Optional[int]:
        """
        Decodes a 2-byte integer from a 4-character hex ASCII string.

        Args:
            data_hex_ascii (bytes): The byte string containing the hex characters.
            offset (int): The starting position of the 4-char hex string.
            signed (bool): Whether to interpret the integer as signed.

        Returns:
            Optional[int]: The decoded integer, or None on failure.
        """
        try:
            if offset + 4 > len(data_hex_ascii): return None
            hex_chars = data_hex_ascii[offset:offset+4].decode("ascii")
            byte_data = bytes.fromhex(hex_chars) 
            return int.from_bytes(byte_data, byteorder="big", signed=signed)
        except (ValueError, UnicodeError, IndexError): return None
    
    def _decode_telemetry_payload(self, info_data_hex_ascii: bytes) -> Dict[str, Dict[str, Any]]:
        """
        Decodes the telemetry INFO payload from the BMS.

        This function parses the ASCII hex string containing telemetry data like
        cell voltages, temperatures, current, SOC, etc., and converts it into a
        standardized dictionary format. It includes validation for the decoded values.

        Args:
            info_data_hex_ascii (bytes): The INFO payload as a byte string of hex characters.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where keys are standardized data
                                       keys and values are nested dictionaries
                                       containing the 'value' and 'unit'.
        """
        bms_data: Dict[str, Dict[str, Any]] = {}
        
        if len(info_data_hex_ascii) != 150: 
             self.logger.warning(f"S '{self.instance_name}': Telemetry payload len {len(info_data_hex_ascii)}, exp 150. Decoding subset.")

        try:
            num_cells = self._int_from_1byte_hex_ascii(info_data_hex_ascii, self._TEL_NUM_CELLS_OFFSET)
            if num_cells is None or not (1 <= num_cells <= 16): num_cells = 0 
            bms_data[BMS_KEY_CELL_COUNT] = {"value": num_cells if num_cells > 0 else None, "unit": None}

            all_decoded_cell_voltages: List[Optional[float]] = []; voltages_v_valid_only: List[float] = [] 
            for i in range(num_cells): 
                offset = self._TEL_CELL_V_START_OFFSET + (i * 4)
                v_mv = self._int_from_2byte_hex_ascii(info_data_hex_ascii, offset)
                cell_v = round(v_mv * 0.001, 3) if v_mv is not None else None
                if cell_v is not None and not (MIN_VALID_CELL_V <= cell_v <= MAX_VALID_CELL_V): cell_v = None 
                
                bms_data[BMS_KEY_CELL_VOLTAGE_PREFIX + str(i+1)] = {"value": cell_v, "unit": "V"}
                all_decoded_cell_voltages.append(cell_v)
                if cell_v is not None: voltages_v_valid_only.append(cell_v)
            
            if voltages_v_valid_only:
                min_v, max_v = min(voltages_v_valid_only), max(voltages_v_valid_only)
                avg_v = sum(voltages_v_valid_only) / len(voltages_v_valid_only)
                
                min_indices = [i + 1 for i, v in enumerate(all_decoded_cell_voltages) if v is not None and v == min_v]
                max_indices = [i + 1 for i, v in enumerate(all_decoded_cell_voltages) if v is not None and v == max_v]
                
                min_indices_str = ", ".join(map(str, min_indices)) if min_indices else "N/A"
                max_indices_str = ", ".join(map(str, max_indices)) if max_indices else "N/A"

                delta_v = max_v - min_v
                bms_data.update({
                    BMS_KEY_CELL_VOLTAGES_ALL: {"value": voltages_v_valid_only, "unit": "V"},
                    BMS_KEY_CELL_VOLTAGE_MIN: {"value": min_v, "unit": "V"},
                    BMS_KEY_CELL_VOLTAGE_MAX: {"value": max_v, "unit": "V"},
                    BMS_KEY_CELL_VOLTAGE_AVG: {"value": round(avg_v, 3), "unit": "V"},
                    BMS_KEY_CELL_VOLTAGE_DIFF: {"value": round(delta_v, 3), "unit": "V"},
                    StandardDataKeys.BMS_CELL_WITH_MIN_VOLTAGE_NUMBER: {"value": min_indices_str, "unit": None},
                    StandardDataKeys.BMS_CELL_WITH_MAX_VOLTAGE_NUMBER: {"value": max_indices_str, "unit": None}
                })

            temps_c: List[float] = []
            temp_names = ["cell_1", "cell_2", "cell_3", "cell_4", "ambient", "mosfet"] 
            for i, name in enumerate(temp_names):
                offset = self._TEL_TEMP_START_OFFSET + (i * 4)
                t_01k = self._int_from_2byte_hex_ascii(info_data_hex_ascii, offset)
                temp_c = round((t_01k - 2731) * 0.1, 1) if t_01k is not None else None 
                if temp_c is not None and not (MIN_VALID_TEMP_C <= temp_c <= MAX_VALID_TEMP_C): temp_c = None
                bms_data[BMS_KEY_TEMP_SENSOR_PREFIX + name] = {"value": temp_c, "unit": "°C"}
                if temp_c is not None: temps_c.append(temp_c)
            
            if temps_c:
                bms_data[BMS_KEY_TEMPERATURES_ALL] = {"value": temps_c, "unit": "°C"}
                bms_data[BMS_KEY_TEMP_MAX] = {"value": max(temps_c), "unit": "°C"}
                bms_data[BMS_KEY_TEMP_MIN] = {"value": min(temps_c), "unit": "°C"}
                main_batt_temp_set = False
                for name in ["cell_1", "cell_2", "cell_3", "cell_4", "ambient", "mosfet"]:
                    val = bms_data.get(BMS_KEY_TEMP_SENSOR_PREFIX + name, {}).get("value")
                    if isinstance(val, float):
                        bms_data[StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS] = {"value": val, "unit": "°C"}
                        main_batt_temp_set = True; break
                if not main_batt_temp_set: bms_data[StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS] = {"value": None, "unit": "°C"}

            current_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_CURRENT_OFFSET, signed=True) 
            total_voltage_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_VOLTAGE_OFFSET)    
            residual_cap_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_RES_CAP_OFFSET)   
            bms_reported_capacity_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_BMS_CAP_OFFSET)    
            soc_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_SOC_OFFSET)             
            rated_cap_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_RATED_CAP_OFFSET)     
            cycles_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_CYCLES_OFFSET)          
            soh_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_SOH_OFFSET)             
            port_voltage_raw = self._int_from_2byte_hex_ascii(info_data_hex_ascii, self._TEL_PORT_V_OFFSET)

            bms_curr_val = round(current_raw * 0.01, 2) if current_raw is not None else None
            bms_volt_val_external = round(port_voltage_raw * 0.01, 2) if port_voltage_raw is not None else None
            internal_pack_volt_val = round(total_voltage_raw * 0.01, 2) if total_voltage_raw is not None else None

            bms_data[BMS_KEY_CURRENT] = {"value": bms_curr_val, "unit": "A"}
            bms_data[BMS_KEY_VOLTAGE] = {"value": bms_volt_val_external, "unit": "V"}
            bms_data[BMS_KEY_POWER] = {"value": round(bms_curr_val * internal_pack_volt_val, 2) if bms_curr_val is not None and internal_pack_volt_val is not None else None, "unit": "W"}
            bms_data[BMS_KEY_REMAINING_CAPACITY_AH] = {"value": round(residual_cap_raw * 0.01, 2) if residual_cap_raw is not None else None, "unit": "Ah"}
            bms_data[BMS_KEY_FULL_CAPACITY_AH] = {"value": round(bms_reported_capacity_raw * 0.01, 2) if bms_reported_capacity_raw is not None else None, "unit": "Ah"}
            bms_data[BMS_KEY_NOMINAL_CAPACITY_AH] = {"value": round(rated_cap_raw * 0.01, 2) if rated_cap_raw is not None else None, "unit": "Ah"}
            
            soc_val = round(soc_raw * 0.1, 1) if soc_raw is not None else None
            if soc_val is not None and not (MIN_VALID_SOC <= soc_val <= MAX_VALID_SOC): soc_val = None 
            bms_data[BMS_KEY_SOC] = {"value": soc_val, "unit": "%"}
            
            cycles_val = cycles_raw
            if cycles_val is not None and cycles_val < MIN_VALID_CYCLE: cycles_val = None 
            bms_data[BMS_KEY_CYCLE_COUNT] = {"value": cycles_val, "unit": None}

            soh_val = round(soh_raw * 0.1, 1) if soh_raw is not None else None
            if soh_val is not None and not (MIN_VALID_SOH <= soh_val <= MAX_VALID_SOH): soh_val = None 
            bms_data[BMS_KEY_SOH] = {"value": soh_val, "unit": "%"}
            
        except Exception as e:
            self.logger.error(f"S '{self.instance_name}': Error decoding telemetry: {e}. INFO: {info_data_hex_ascii!r}", exc_info=True)
            return {} 
        return bms_data

    def _get_telesign_flag_state(self, info_payload_bytes: bytes, signal_name_key: str) -> Optional[str]:
        """
        Gets the state ('on' or 'off' text) of a specific telesignalization flag.

        Args:
            info_payload_bytes (bytes): The decoded (binary) INFO payload.
            signal_name_key (str): The name of the signal to look up (e.g., "charge_switch").

        Returns:
            Optional[str]: The descriptive state text (e.g., "on", "off", "failure"), or None if not found.
        """
        for signal_def in self.TELESIGNALIZATION_SIGNALS:
            if signal_def["name"] == signal_name_key:
                byte_idx, bit_idx = signal_def["byte"], signal_def["bit"]
                if byte_idx >= len(info_payload_bytes): return None
                is_on = (info_payload_bytes[byte_idx] >> bit_idx) & 1
                return signal_def["on"] if is_on else signal_def["off"]
        return None

    def _decode_telesignalization_payload(self, info_data_hex_ascii: bytes) -> Dict[str, Dict[str, Any]]:
        """
        Decodes the telesignalization INFO payload from the BMS.

        This function parses the bit-packed status flags, alarms, and warnings
        from the telesignalization response. It generates lists of active alarms
        and warnings, and derives a summary status text.

        Args:
            info_data_hex_ascii (bytes): The INFO payload as a byte string of hex characters.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary of standardized data keys and
                                       their corresponding values and units.
        """
        bms_data: Dict[str, Dict[str, Any]] = {}

        if len(info_data_hex_ascii) != 98: 
            self.logger.warning(f"S '{self.instance_name}': Telesign payload len {len(info_data_hex_ascii)}, exp 98. Decoding subset.")

        try:
            info_payload_bytes = bytes.fromhex(info_data_hex_ascii.decode("ascii"))
        except (ValueError, UnicodeError) as e_decode: 
            self.logger.error(f"S '{self.instance_name}': Failed to decode telesign ASCII hex to bytes: {e_decode}. Data: {info_data_hex_ascii!r}")
            return {}

        active_alarms: List[str] = []; active_warnings: List[str] = []; status_flags_on: List[str] = [] 
        num_cells_rep_ts = self._get_num_cells_from_telesign_payload(info_payload_bytes)
        bms_data[f"{BMS_KEY_CELL_COUNT}_reported_ts"] = {"value": num_cells_rep_ts, "unit": None}

        for signal_def in self.TELESIGNALIZATION_SIGNALS:
            name = signal_def["name"]; nice_name = name.replace("_flag", "").replace("_", " ").title()
            if name.startswith("cell_equalization_"): continue # Handled separately

            byte_idx, bit_idx = signal_def["byte"], signal_def["bit"]
            if byte_idx >= len(info_payload_bytes): 
                bms_data[name] = {"value": None, "unit": None}; continue
            
            is_on = (info_payload_bytes[byte_idx] >> bit_idx) & 1
            state_text = signal_def["on"] if is_on else signal_def["off"]
            bms_data[name] = {"value": state_text, "unit": None, "source": "telesign"} 

            if is_on:
                if signal_def["type"] == "protect": active_alarms.append(nice_name)
                elif signal_def["type"] == "warn": active_warnings.append(nice_name)
                elif signal_def["type"] == "status":
                    if name == "charge_status_flag": status_flags_on.append("Charging")
                    elif name == "discharge_status_flag": status_flags_on.append("Discharging")
                    elif name == "floating_charge_status_flag": status_flags_on.append("Floating")
                    elif name == "standby_status_flag": status_flags_on.append("Standby")
                    elif name == "cell_low_temp_heating": status_flags_on.append("Heating")
                    elif name == "over_temp_air_cooled": status_flags_on.append("Cooling")
        
        bms_data[BMS_KEY_ACTIVE_ALARMS_LIST] = {"value": sorted(list(set(active_alarms))), "unit": None}
        bms_data[BMS_KEY_ACTIVE_WARNINGS_LIST] = {"value": sorted(list(set(active_warnings))), "unit": None}

        status_text_final = "Idle"
        if active_alarms: status_text_final = "Protection: " + active_alarms[0]
        elif active_warnings: status_text_final = "Warning: " + active_warnings[0]
        elif status_flags_on: status_text_final = ", ".join(sorted(list(set(status_flags_on))))
        
        bms_data[BMS_KEY_STATUS_TEXT] = {"value": status_text_final, "unit": None, "source": "telesign"}
        bms_data[BMS_KEY_FAULT_SUMMARY] = {"value": "Normal" if not active_alarms and not active_warnings else (active_alarms[0] if active_alarms else active_warnings[0]), "unit": None}
        bms_data[BMS_KEY_CHARGE_FET_ON] = {"value": bms_data.get("charge_switch", {}).get("value") == "on", "unit": None}
        bms_data[BMS_KEY_DISCHARGE_FET_ON] = {"value": bms_data.get("discharge_switch", {}).get("value") == "on", "unit": None}

        balancing_cells: List[str] = []
        max_bal = min(num_cells_rep_ts if num_cells_rep_ts > 0 else 16, 16) 
        for i in range(1, max_bal + 1):
            bal_key = f"cell_equalization_{i}"
            bal_status = self._get_telesign_flag_state(info_payload_bytes, bal_key)
            is_bal = bal_status == "balancing" 
            bms_data[BMS_KEY_CELL_BALANCE_ACTIVE_PREFIX + str(i)] = {"value": is_bal, "unit": None}
            if is_bal: balancing_cells.append(str(i))
        bms_data[BMS_KEY_CELLS_BALANCING] = {"value": ", ".join(balancing_cells) if balancing_cells else "None", "unit": None}
        
        return bms_data

    def _get_num_cells_from_telesign_payload(self, info_payload_bytes: bytes) -> int:
        """
        Extracts the cell count from the telesignalization payload.

        Seplos docs indicate the number of cells is at Byte 1 (0-indexed) of the
        decoded INFO payload.

        Args:
            info_payload_bytes (bytes): The decoded (binary) INFO payload.

        Returns:
            int: The number of cells reported, or 0 on failure.
        """
        if len(info_payload_bytes) > 1: 
            try: return int(info_payload_bytes[1])
            except (IndexError, ValueError): self.logger.warning(f"S '{self.instance_name}': Failed to get num_cells from telesign byte 1.")
        return 0

    def standardize_bms_keys(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates internal data keys to the application's standard keys.

        This method takes the nested dictionary structure produced by the decoder
        methods, maps the keys to the application-wide `StandardDataKeys`, and
        returns a flat dictionary of the results.

        Args:
            raw_data (Dict[str, Any]): The nested dictionary with plugin-specific keys.

        Returns:
            Dict[str, Any]: A flat dictionary with standardized keys and unwrapped values.
        """
        key_map = {
            BMS_KEY_SOC: StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT,
            BMS_KEY_SOH: StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT,
            BMS_KEY_VOLTAGE: StandardDataKeys.BATTERY_VOLTAGE_VOLTS,
            BMS_KEY_CURRENT: StandardDataKeys.BATTERY_CURRENT_AMPS,
            BMS_KEY_POWER: StandardDataKeys.BATTERY_POWER_WATTS,
            BMS_KEY_TEMP_MAX: StandardDataKeys.BMS_TEMP_MAX_CELSIUS,
            BMS_KEY_TEMP_MIN: StandardDataKeys.BMS_TEMP_MIN_CELSIUS,
            BMS_KEY_CELL_COUNT: StandardDataKeys.BMS_CELL_COUNT,
            BMS_KEY_CELL_VOLTAGES_ALL: StandardDataKeys.BMS_CELL_VOLTAGES_LIST,
            BMS_KEY_CELL_VOLTAGE_MIN: StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS,
            BMS_KEY_CELL_VOLTAGE_MAX: StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS,
            BMS_KEY_CELL_VOLTAGE_AVG: StandardDataKeys.BMS_CELL_VOLTAGE_AVERAGE_VOLTS,
            BMS_KEY_CELL_VOLTAGE_DIFF: StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS,
            BMS_KEY_STATUS_TEXT: StandardDataKeys.BATTERY_STATUS_TEXT,
            BMS_KEY_FAULT_SUMMARY: StandardDataKeys.BMS_FAULT_SUMMARY_TEXT,
            BMS_KEY_REMAINING_CAPACITY_AH: StandardDataKeys.BMS_REMAINING_CAPACITY_AH,
            BMS_KEY_FULL_CAPACITY_AH: StandardDataKeys.BMS_FULL_CAPACITY_AH,
            BMS_KEY_NOMINAL_CAPACITY_AH: StandardDataKeys.BMS_NOMINAL_CAPACITY_AH,
            BMS_KEY_CYCLE_COUNT: StandardDataKeys.BATTERY_CYCLES_COUNT,
            BMS_KEY_CHARGE_FET_ON: StandardDataKeys.BMS_CHARGE_FET_ON,
            BMS_KEY_DISCHARGE_FET_ON: StandardDataKeys.BMS_DISCHARGE_FET_ON,
            BMS_KEY_CELLS_BALANCING: StandardDataKeys.BMS_CELLS_BALANCING_TEXT,
            BMS_KEY_ACTIVE_ALARMS_LIST: StandardDataKeys.BMS_ACTIVE_ALARMS_LIST,
            BMS_KEY_ACTIVE_WARNINGS_LIST: StandardDataKeys.BMS_ACTIVE_WARNINGS_LIST,
        }
        
        std_data = {}
        for raw_key, value_dict in raw_data.items():
            raw_value = value_dict.get("value") if isinstance(value_dict, dict) else value_dict
            
            std_key = key_map.get(raw_key, raw_key)
            std_data[std_key] = raw_value
        
        if StandardDataKeys.BMS_TEMP_MAX_CELSIUS in std_data and StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS not in std_data:
            main_temp = std_data.get(BMS_KEY_TEMP_SENSOR_PREFIX + "cell_1")
            if main_temp is None:
                main_temp = std_data.get(StandardDataKeys.BMS_TEMP_MAX_CELSIUS)
            std_data[StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS] = main_temp

        return std_data

    def _is_data_sane(self, data: Dict[str, Dict[str, Any]]) -> bool:
        """
        Performs a sanity check on critical decoded values.

        It verifies that key metrics like cell voltages and state of charge fall
        within reasonable, predefined ranges. This helps to reject corrupted
        data packets.

        Args:
            data (Dict[str, Dict[str, Any]]): The nested dictionary of decoded data.

        Returns:
            True if data seems reasonable, False otherwise.
        """
        cell_voltages = data.get(BMS_KEY_CELL_VOLTAGES_ALL, {}).get("value", [])
        if not cell_voltages:
            self.logger.warning(f"S'{self.instance_name}': Sanity check failed - no cell voltages decoded.")
            return False

        for v in cell_voltages:
            if not (MIN_VALID_CELL_V <= v <= MAX_VALID_CELL_V):
                self.logger.error(f"S'{self.instance_name}': Sanity check FAILED. Unreasonable cell voltage detected: {v}V. Rejecting data packet.")
                return False
        
        soc = data.get(BMS_KEY_SOC, {}).get("value")
        if not isinstance(soc, (int, float)) or not (MIN_VALID_SOC <= soc <= MAX_VALID_SOC):
            self.logger.error(f"S'{self.instance_name}': Sanity check FAILED. Unreasonable SOC detected: {soc}%. Rejecting data packet.")
            return False

        self.logger.debug(f"S'{self.instance_name}': Data sanity check passed.")
        return True


    def read_bms_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads and decodes a full data set from the Seplos BMS.

        This method implements the core data acquisition logic. It orchestrates:
        1. Sending the command to read telemetry data.
        2. Sending the command to read telesignalization (status) data.
        3. Decoding both responses.
        4. Merging the results.
        5. Performing a sanity check on the data.
        6. Standardizing keys and data conventions (e.g., power sign).

        Returns:
            A flat dictionary of standardized BMS data, or None if the read
            operation fails at any stage.
        """
        self.last_error_message = None
        if not self._is_connected_flag:
            if not self.connect():
                self.logger.error(f"S '{self.instance_name}': Connection failed. Cannot read data.")
                return None

        # These methods return dicts of wrapped data: {'key': {'value': val, 'unit': u}}
        all_bms_data_nested: Dict[str, Dict[str, Any]] = {}
        telemetry_ok, telesign_ok = False, False

        payload_tel = self._send_receive_seplos_frame(self._encode_cmd(CMD_READ_TELEMETRY))
        if payload_tel:
            decoded_tel = self._decode_telemetry_payload(payload_tel)
            if decoded_tel:
                all_bms_data_nested.update(decoded_tel)
                telemetry_ok = True

        if self.inter_command_delay_ms > 0:
            time.sleep(self.inter_command_delay_ms / 1000.0)

        if self._is_connected_flag:
            payload_ts = self._send_receive_seplos_frame(self._encode_cmd(CMD_READ_TELESIGNALIZATION))
            if payload_ts:
                decoded_ts = self._decode_telesignalization_payload(payload_ts)
                if decoded_ts:
                    all_bms_data_nested.update(decoded_ts)
                    telesign_ok = True
        
        if not telemetry_ok and not telesign_ok:
            return None

        if not self._is_data_sane(all_bms_data_nested):
            self.last_error_message = "Data failed sanity check (e.g., unreasonable cell voltage)."
            self.disconnect() 
            return None

        status_dict = all_bms_data_nested.get(BMS_KEY_STATUS_TEXT, {})
        final_status_text = status_dict.get("value", "Unknown") if isinstance(status_dict, dict) else "Unknown"

        if "idle" in final_status_text.lower():
            current_dict = all_bms_data_nested.get(BMS_KEY_CURRENT, {})
            bms_current = current_dict.get("value", 0) if isinstance(current_dict, dict) else 0
            if isinstance(bms_current, (int, float)):
                if bms_current > 0.5: final_status_text = "Charging"
                elif bms_current < -0.5: final_status_text = "Discharging"
                else: final_status_text = "Idle"
        
        all_bms_data_nested[BMS_KEY_STATUS_TEXT] = {"value": final_status_text, "unit": None}
        
        standardized_data = self.standardize_bms_keys(all_bms_data_nested)
        
        power_key, current_key = StandardDataKeys.BATTERY_POWER_WATTS, StandardDataKeys.BATTERY_CURRENT_AMPS
        
        if power_key in standardized_data and isinstance(standardized_data.get(power_key), (int, float)):
            standardized_data[power_key] *= -1
        
        if current_key in standardized_data and isinstance(standardized_data.get(current_key), (int, float)):
            standardized_data[current_key] *= -1

        power_val_final = standardized_data.get(power_key)
        # Only overwrite the status if it's generic, preserving detailed statuses like "Protection"
        current_status = standardized_data.get(StandardDataKeys.BATTERY_STATUS_TEXT, "Unknown")
        if current_status in ["Idle", "Charging", "Discharging", "Unknown", "Standby"]:
            if isinstance(power_val_final, (int, float)):
                if power_val_final > 10:
                    standardized_data[StandardDataKeys.BATTERY_STATUS_TEXT] = "Discharging"
                elif power_val_final < -10:
                    standardized_data[StandardDataKeys.BATTERY_STATUS_TEXT] = "Charging"
                else:
                    standardized_data[StandardDataKeys.BATTERY_STATUS_TEXT] = "Idle"

        self.latest_data_cache = standardized_data.copy()
        return self.latest_data_cache

    def get_bms_static_info(self) -> Optional[Dict[str, Any]]:
        """
        Provides static information about the BMS.

        This data is primarily sourced from the plugin's configuration file, as
        the Seplos V2 protocol does not have a standard command to read this
        information directly from the device.

        Returns:
            A dictionary containing static BMS info like manufacturer and model.
        """
        model_suffix = f" ({self.connection_type.capitalize()})" if self.connection_type and self.connection_type != "disabled" else ""
        return {
            BMS_KEY_MANUFACTURER: self.plugin_config.get("seplos_manufacturer", "Seplos"),
            BMS_KEY_MODEL: self.plugin_config.get("seplos_model", "Seplos V2") + model_suffix,
            BMS_KEY_SERIAL_NUMBER: self.plugin_config.get("seplos_serial_number", f"N/A_Config_{self.instance_name}"),
            BMS_KEY_FIRMWARE_VERSION: self.plugin_config.get("seplos_firmware_version", "Unknown (Seplos V2)"), 
            BMS_KEY_HARDWARE_VERSION: self.plugin_config.get("seplos_hardware_version", "Unknown (Seplos V2)"), 
        }