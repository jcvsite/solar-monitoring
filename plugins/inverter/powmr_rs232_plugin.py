# plugins/inverter/powmr_rs232_plugin.py
"""
POWMR RS232 Inverter Plugin

This plugin communicates with POWMR hybrid inverters using their native RS232 protocol
(inv8851) instead of Modbus. It supports both direct serial connections and TCP connections
via RS232-to-TCP converters.

The plugin implements the complete inv8851 protocol specification as documented in:
https://github.com/leodesigner/powmr4500_comm/blob/main/include/inv8851.h

Features:
- Native inv8851 protocol support (versions 1 and 2)
- Serial and TCP connection types
- Complete register mapping (74+ registers)
- Temperature monitoring from multiple NTC sensors
- Comprehensive alert/fault code processing
- BMS integration for battery cell monitoring
- Configuration parameter reading
- Real-time monitoring of PV generation, battery status, and grid interaction
- Energy statistics tracking (daily, total lifetime values)
- Comprehensive error handling and connection management

Supported Models:
- POWMR 4500W series
- POWMR 6000W series
- Compatible POWMR hybrid inverter models with inv8851 protocol

Protocol Reference: inv8851 RS232 Protocol
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

import time
import struct
import logging
import serial
import socket
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.app_state import AppState

from .powmr_rs232_plugin_constants import (
    POWMR_REGISTERS,
    POWMR_CONFIG_REGISTERS,
    POWMR_RUN_MODE_CODES,
    POWMR_ALERT_MAPS,
    ALERT_CATEGORIES,
    PROTOCOL_HEADER,
    STATE_COMMAND,
    CONFIG_COMMAND_READ,
    STATE_ADDRESS,
    CONFIG_ADDRESS
)

from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port, check_icmp_ping

# Constants for error handling
ERROR_READ = "read_error"
ERROR_DECODE = "decode_error"
UNKNOWN = "Unknown"

def _modbus_crc16(data: bytes) -> int:
    """
    Calculate Modbus CRC16 checksum for packet validation.
    
    This function implements the standard Modbus CRC16 algorithm used by
    the POWMR inv8851 protocol for packet integrity verification.
    
    Args:
        data: The byte data to calculate CRC for (excluding the CRC bytes themselves)
        
    Returns:
        The calculated 16-bit CRC value as an integer
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

def _build_request_packet(request_type: str, protocol_version: int = 1) -> bytes:
    """
    Build a properly formatted request packet based on inv8851.h structure.
    
    Creates request packets for either state data or configuration data according
    to the POWMR inv8851 protocol specification. The packet structure is:
    [Protocol Header][Command][Address][Data Size][CRC]
    
    Args:
        request_type: Either "state" for operational data or "config" for settings
        protocol_version: Protocol version (1 or 2), affects data payload size
        
    Returns:
        Complete request packet as bytes, ready to send to inverter
        
    Raises:
        ValueError: If request_type is not "state" or "config"
    """
    if request_type == "state":
        # Protocol (0x8851) + Command (0x0003) + Address (0x0000) + Data Size
        data_size = 144 if protocol_version == 1 else 148  # Based on inv8851.h
        packet_data = struct.pack('>HHHH', PROTOCOL_HEADER, STATE_COMMAND, STATE_ADDRESS, data_size)
    elif request_type == "config":
        # Protocol (0x8851) + Command (0x0300) + Address (0x0200) + Data Size  
        data_size = 90 if protocol_version == 1 else 94  # Based on inv8851.h
        packet_data = struct.pack('>HHHH', PROTOCOL_HEADER, CONFIG_COMMAND_READ, CONFIG_ADDRESS, data_size)
    else:
        raise ValueError(f"Invalid request type: {request_type}")
    
    # Calculate and append CRC
    crc = _modbus_crc16(packet_data)
    return packet_data + struct.pack('<H', crc)

def _parse_response(response: bytes, expected_len: int) -> Optional[Dict[int, Any]]:
    """
    Parse response packet according to inv8851.h structure.
    
    Validates and extracts data from inverter response packets. Performs
    protocol header validation, CRC verification, and data extraction.
    
    Args:
        response: Raw response bytes from inverter
        expected_len: Expected total packet length including headers and CRC
        
    Returns:
        Dictionary mapping word indices to values, or None if validation fails
        
    Note:
        The returned dictionary uses 0-based word indices as keys, where each
        word represents a 16-bit register value from the inverter.
    """
    if len(response) != expected_len:
        return None
    
    # Check protocol header (0x8851)
    protocol_header = struct.unpack('>H', response[0:2])[0]
    if protocol_header != PROTOCOL_HEADER:
        return None

    # Verify CRC
    crc_from_packet = struct.unpack('<H', response[-2:])[0]
    calculated_crc = _modbus_crc16(response[:-2])
    if crc_from_packet != calculated_crc:
        return None

    # Extract data payload (skip 8-byte header, exclude 2-byte CRC)
    num_words = (expected_len - 10) // 2
    data_words = struct.unpack(f'>{num_words}H', response[8:-2])
    return {i: val for i, val in enumerate(data_words)}


class ConnectionType(str, Enum):
    """Enumeration for supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"


class PowmrCustomRs232Plugin(DevicePlugin):
    """
    POWMR RS232 Inverter Plugin using native inv8851 protocol.
    
    This plugin communicates with POWMR hybrid inverters using their proprietary
    RS232 protocol instead of Modbus. It provides comprehensive monitoring of
    inverter status, power generation, battery management, and system alerts.
    
    The plugin supports both direct serial connections and TCP connections via
    RS232-to-TCP converters, making it suitable for both local and remote monitoring.
    
    Key Features:
    - Native inv8851 protocol implementation
    - Dual connection support (Serial/TCP)
    - Complete register mapping (74+ data points)
    - Multi-sensor temperature monitoring
    - BMS integration for battery cell monitoring
    - Comprehensive fault/alert processing
    - Protocol version support (v1 and v2)
    
    Configuration Parameters:
    - connection_type: "serial" or "tcp"
    - powmr_protocol_version: 1 or 2
    - serial_port: COM port or device path
    - baud_rate: Serial communication speed
    - tcp_host: IP address for TCP connections
    - tcp_port: TCP port number
    
    Example Configuration:
        [PLUGIN_INV_POWMR_RS232]
        plugin_type = inverter.powmr_rs232_plugin
        connection_type = serial
        serial_port = COM3
        baud_rate = 9600
        powmr_protocol_version = 1
    """
    
    @staticmethod
    def _plugin_decode_register(registers: List[int], info: Dict[str, Any], logger_instance: logging.Logger) -> Tuple[Any, Optional[str]]:
        """
        Decodes raw register values into a scaled and typed Python object.

        Args:
            registers: A list of integers representing the raw register values.
            info: The dictionary of register information from POWMR_REGISTERS.
            logger_instance: The logger to use for reporting errors.

        Returns:
            A tuple containing:
            - The decoded and scaled value. On error, returns the string "decode_error".
            - The unit of the value as a string (e.g., "V", "A", "W"), or None.
        """
        reg_type: str = info.get("type", "unknown")
        scale: float = float(info.get("scale", 1.0))
        unit: Optional[str] = info.get("unit")
        value: Any = None
        key_name_for_log: str = info.get('key', 'N/A_KeyMissingInInfo')

        try:
            if not registers:
                raise ValueError("No registers provided")
            
            if reg_type == "uint16":
                value = registers[0]
            elif reg_type == "int16":
                value = struct.unpack('>h', registers[0].to_bytes(2, 'big'))[0]
            elif reg_type == "uint32":
                if len(registers) < 2:
                    raise ValueError("Insufficient registers for uint32")
                value = struct.unpack('>I', b''.join(r.to_bytes(2, 'big') for r in registers[:2]))[0]
            elif reg_type == "int32":
                if len(registers) < 2:
                    raise ValueError("Insufficient registers for int32")
                value = struct.unpack('>i', b''.join(r.to_bytes(2, 'big') for r in registers[:2]))[0]
            else:
                raise ValueError(f"Unsupported type: {reg_type}")

            if isinstance(value, (int, float)):
                should_scale = (abs(scale - 1.0) > 1e-9) and (unit not in ["Bitfield", "Code", "Hex"])
                final_value = float(value) * scale if should_scale else value
                return final_value, unit
            else:
                return value, unit
                
        except (struct.error, ValueError, IndexError, TypeError) as e:
            logger_instance.error(f"POWMRPlugin: Decode Error for '{key_name_for_log}' ({reg_type}) with {registers}: {e}", exc_info=False)
            return ERROR_DECODE, unit

    @staticmethod
    def _plugin_get_register_count(reg_type: str, logger_instance: logging.Logger) -> int:
        """
        Determines the number of 16-bit registers a given data type occupies.

        Args:
            reg_type: The data type string (e.g., "uint32", "int16").
            logger_instance: The logger to use for reporting warnings.

        Returns:
            The number of registers required for the data type.
        """
        if reg_type in ["uint32", "int32"]:
            return 2
        if reg_type in ["uint16", "int16"]:
            return 1
        logger_instance.warning(f"POWMRPlugin: Unknown type '{reg_type}' in get_register_count. Assuming 1.")
        return 1
    
    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initialize the POWMR RS232 plugin.
        
        Args:
            instance_name: Unique identifier for this plugin instance
            plugin_specific_config: Configuration dictionary from config.ini
            main_logger: Logger instance for this plugin
            app_state: Optional application state object
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        # Parse connection configuration
        self.connection_type = ConnectionType(self.plugin_config.get("connection_type", "serial"))
        self.protocol_version = int(self.plugin_config.get("powmr_protocol_version", 1))
        
        # Serial connection parameters
        self.serial_port_path = self.plugin_config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = int(self.plugin_config.get("baud_rate", 9600))
        
        # TCP connection parameters
        self.tcp_host = self.plugin_config.get("tcp_host")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 502))
        
        # Connection objects
        self.serial_client: Optional[serial.Serial] = None
        self.tcp_client: Optional[socket.socket] = None
        self.last_error_message: Optional[str] = None
        
        # Data caching for efficiency
        self.last_known_dynamic_data: Dict[str, Any] = {}
        self.last_known_config_data: Optional[Dict[str, Any]] = None

        self.logger.info(f"POWMR Plugin '{self.instance_name}': Initialized for protocol version {self.protocol_version}, connection type: {self.connection_type.value}")

    @property
    def name(self) -> str:
        """Return the technical name of the plugin."""
        return "powmr_rs232"

    @property
    def pretty_name(self) -> str:
        """Return a user-friendly name for the plugin."""
        return "POWMR Inverter"

    def connect(self) -> bool:
        """
        Establish connection to the POWMR inverter.
        
        Attempts to connect using the configured connection type (Serial or TCP).
        If already connected and connection is valid, returns immediately.
        Otherwise, cleans up any existing connections and establishes a new one.
        
        Returns:
            True if connection successful, False otherwise
            
        Note:
            Connection details and error messages are logged appropriately.
            The last_error_message attribute is updated on failure.
        """
        if self._is_connected_flag and self._validate_connection():
            return True
            
        # Clean up any existing connections
        self.disconnect()
        self.last_error_message = None

        if self.connection_type == ConnectionType.SERIAL:
            return self._connect_serial()
        else:
            return self._connect_tcp()

    def _connect_serial(self) -> bool:
        """
        Establish serial connection to the inverter.
        
        Configures and opens a serial connection using the configured port
        and baud rate. Uses standard 8N1 configuration (8 data bits, no
        parity, 1 stop bit) which is typical for POWMR inverters.
        
        Returns:
            True if serial connection successful, False otherwise
        """
        try:
            self.serial_client = serial.Serial(
                port=self.serial_port_path, 
                baudrate=self.baud_rate, 
                timeout=5,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            self._is_connected_flag = True
            self.logger.info(f"POWMR Plugin '{self.instance_name}': Successfully connected via Serial on {self.serial_port_path}")
            return True
        except serial.SerialException as e:
            self.last_error_message = f"Failed to open serial port {self.serial_port_path}: {e}"
            self.logger.error(f"POWMR Plugin '{self.instance_name}': {self.last_error_message}")
            return False

    def _connect_tcp(self) -> bool:
        """
        Establish TCP connection to the inverter.
        
        Performs a pre-connection check and creates a TCP socket connection
        to the configured host and port. This is typically used with 
        RS232-to-TCP converters for remote monitoring of POWMR inverters.
        
        Returns:
            True if TCP connection successful, False otherwise
        """
        # Perform pre-connection network check
        self.logger.info(f"POWMRPlugin '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
        port_open, rtt_ms, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
        if not port_open:
            self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} is not open. Error: {err_msg}"
            self.logger.error(self.last_error_message)
            icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
            if not icmp_ok:
                self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host is likely down or blocked.")
            return False

        try:
            self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_client.settimeout(10)
            self.tcp_client.connect((self.tcp_host, self.tcp_port))
            self._is_connected_flag = True
            self.logger.info(f"POWMR Plugin '{self.instance_name}': Successfully connected via TCP to {self.tcp_host}:{self.tcp_port}")
            return True
        except (socket.error, OSError) as e:
            self.last_error_message = f"Failed to connect to {self.tcp_host}:{self.tcp_port}: {e}"
            self.logger.error(f"POWMR Plugin '{self.instance_name}': {self.last_error_message}")
            if self.tcp_client:
                self.tcp_client.close()
                self.tcp_client = None
            return False

    def _validate_connection(self) -> bool:
        """
        Validate that the current connection is still active.
        
        Performs basic validation to ensure the connection object exists
        and is in a usable state. Does not perform actual communication.
        
        Returns:
            True if connection appears valid, False otherwise
        """
        if self.connection_type == ConnectionType.SERIAL:
            return self.serial_client and self.serial_client.is_open
        else:
            return self.tcp_client is not None
    
    def disconnect(self) -> None:
        """
        Close the connection and clean up resources.
        
        Safely closes both serial and TCP connections if they exist,
        handles any exceptions during cleanup, and resets connection state.
        This method is safe to call multiple times.
        """
        try:
            if self.serial_client and self.serial_client.is_open:
                self.serial_client.close()
                self.logger.debug(f"POWMR Plugin '{self.instance_name}': Serial connection closed")
        except Exception as e:
            self.logger.warning(f"POWMR Plugin '{self.instance_name}': Error closing serial connection: {e}")
        
        try:
            if self.tcp_client:
                self.tcp_client.close()
                self.logger.debug(f"POWMR Plugin '{self.instance_name}': TCP connection closed")
        except Exception as e:
            self.logger.warning(f"POWMR Plugin '{self.instance_name}': Error closing TCP connection: {e}")
        
        self.serial_client = None
        self.tcp_client = None
        self._is_connected_flag = False
        self.logger.info(f"POWMR Plugin '{self.instance_name}': Disconnected from POWMR inverter")

    def read_static_data(self) -> Optional[Dict[str, Any]]:
        """
        Read static device information from the inverter.
        
        Retrieves device identification, capabilities, and configuration data
        that doesn't change during normal operation. This includes firmware
        version, model information, and system capabilities.
        
        The method first attempts to read configuration data, then falls back
        to dynamic data if needed for firmware version information.
        
        Returns:
            Dictionary containing standardized static data keys, or None on failure
            
        Note:
            Static data is cached after first successful read to improve performance.
            Configuration data is included in the response for diagnostic purposes.
        """
        # Static data is best read from the configuration packet - read once and cache
        if self.last_known_config_data is None:
            self.logger.info("Configuration data not cached. Reading from inverter.")
            self.last_known_config_data = self.read_configuration_data()

        # Fallback to dynamic data for firmware version if config read fails
        if not self.last_known_dynamic_data:
            self.read_dynamic_data()

        if not self.last_known_config_data and not self.last_known_dynamic_data:
            self.logger.error("Could not read any data from inverter.")
            return None

        sw_version = self.last_known_dynamic_data.get("software_version")
        
        return {
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
            StandardDataKeys.STATIC_INVERTER_MANUFACTURER: "POWMR",
            StandardDataKeys.STATIC_INVERTER_MODEL_NAME: "POWMR Hybrid",
            StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: UNKNOWN,
            StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION: str(sw_version) if sw_version else UNKNOWN,
            StandardDataKeys.STATIC_NUMBER_OF_MPPTS: 1,
            StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: 1,
            # Include the entire decoded config for diagnostics
            "inverter_configuration": self.last_known_config_data
        }

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        """
        Read real-time operational data from the inverter.
        
        Retrieves current operational status, power measurements, temperatures,
        battery information, and system alerts. This data changes frequently
        during normal operation.
        
        The method builds a state request packet, sends it to the inverter,
        receives the response, validates it, decodes the raw register values,
        and standardizes the data according to the plugin interface.
        
        Returns:
            Dictionary containing standardized operational data, or None on failure
            
        Note:
            - Automatically disconnects on communication errors
            - Caches the last successful read for reference
            - Includes raw register values for debugging
        """
        if not self.is_connected:
            self.logger.error("Not connected, cannot read data.")
            return None

        try:
            request_packet = _build_request_packet("state", self.protocol_version)
            expected_len = 154 if self.protocol_version == 1 else 158
            
            if self.connection_type == ConnectionType.SERIAL and self.serial_client:
                self.serial_client.write(request_packet)
                response_bytes = self.serial_client.read(expected_len)
            elif self.connection_type == ConnectionType.TCP and self.tcp_client:
                self.tcp_client.sendall(request_packet)
                response_bytes = self.tcp_client.recv(expected_len)
            else:
                self.last_error_message = "Client not initialized for reading."
                return None

            if len(response_bytes) < expected_len:
                self.last_error_message = f"Incomplete response. Got {len(response_bytes)}, expected {expected_len}."
                return None

            parsed_data = _parse_response(response_bytes, expected_len)
            if not parsed_data:
                self.last_error_message = "Failed to parse state response or CRC check failed."
                return None
            
            decoded_data = self._decode_data(parsed_data, POWMR_REGISTERS)
            standardized_data = self._standardize_operational_data(decoded_data)
            self.last_known_dynamic_data = standardized_data.copy()
            return standardized_data

        except (serial.SerialException, socket.error, OSError) as e:
            self.last_error_message = f"Communication error: {e}"
            self.disconnect()
            return None
        except Exception as e:
            self.last_error_message = f"An unexpected error occurred: {e}"
            self.logger.error(self.last_error_message, exc_info=True)
            return None

    def read_configuration_data(self) -> Optional[Dict[str, Any]]:
        """
        Read the inverter's static configuration settings.
        
        Retrieves configuration parameters such as output voltage settings,
        battery charging parameters, equalization settings, and other
        user-configurable options that define how the inverter operates.
        
        Returns:
            Dictionary containing decoded configuration parameters, or None on failure
            
        Note:
            Configuration data is typically read once and cached since these
            settings don't change frequently during normal operation.
        """
        if not self.is_connected:
            return None
        try:
            request_packet = _build_request_packet("config", self.protocol_version)
            expected_len = 100 if self.protocol_version == 1 else 104
            
            if self.connection_type == ConnectionType.SERIAL and self.serial_client:
                self.serial_client.write(request_packet)
                response_bytes = self.serial_client.read(expected_len)
            elif self.connection_type == ConnectionType.TCP and self.tcp_client:
                self.tcp_client.sendall(request_packet)
                response_bytes = self.tcp_client.recv(expected_len)
            else:
                return None

            if len(response_bytes) < expected_len:
                self.last_error_message = f"Incomplete config response. Got {len(response_bytes)}, expected {expected_len}."
                return None

            parsed_data = _parse_response(response_bytes, expected_len)
            if not parsed_data:
                self.last_error_message = "Failed to parse config response or CRC check failed."
                return None
            
            return self._decode_data(parsed_data, POWMR_CONFIG_REGISTERS)

        except (serial.SerialException, socket.error, OSError) as e:
            self.last_error_message = f"Communication error during config read: {e}"
            self.disconnect()
            return None
        except Exception as e:
            self.last_error_message = f"An unexpected error occurred during config read: {e}"
            self.logger.error(self.last_error_message, exc_info=True)
            return None

    def _decode_data(self, raw_data: Dict[int, int], register_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decode raw register values into meaningful data using the register map.
        
        Converts raw 16-bit register values from the inverter into properly
        scaled and typed values according to the register definitions. Handles
        different data types (int16, uint16) and applies scaling factors.
        
        Args:
            raw_data: Dictionary mapping register addresses to raw values
            register_map: Register definition map (POWMR_REGISTERS or POWMR_CONFIG_REGISTERS)
            
        Returns:
            Dictionary mapping register names to decoded values
            
        Note:
            - Filters out version 2 registers when using protocol version 1
            - Handles signed/unsigned integer conversion
            - Applies scaling factors for proper unit conversion
        """
        decoded = {}
        for key, info in register_map.items():
            # Skip version 2 registers if using protocol version 1
            if info.get("version") == 2 and self.protocol_version != 2:
                continue

            addr = info["addr"]
            if addr in raw_data:
                value = raw_data[addr]
                scale = info.get("scale", 1.0)
                
                # Handle signed 16-bit integers
                if info.get("type") == "int16":
                    # Convert unsigned to signed using struct pack/unpack
                    value = struct.unpack('>h', struct.pack('>H', value))[0]

                # Apply scaling if needed
                decoded[key] = float(value) * scale if scale != 1.0 else value
        return decoded

    def _standardize_operational_data(self, decoded_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert decoded register data into standardized plugin interface format.
        
        Transforms the raw decoded register values into the standard data keys
        expected by the monitoring system. Performs calculations, status
        interpretations, and data aggregations as needed.
        
        Args:
            decoded_data: Dictionary of decoded register values
            
        Returns:
            Dictionary using StandardDataKeys with calculated and interpreted values
            
        Key Processing:
        - Extracts run mode from PV topology nibble
        - Calculates battery power from voltage and current
        - Decodes temperature sensors from packed words
        - Processes alert bitfields into categorized alerts
        - Determines battery charging/discharging status
        """
        # Extract run mode from PV topology (3rd nibble of run_mode register)
        run_mode_val = decoded_data.get("run_mode", 0)
        pv_topology_code = (run_mode_val >> 8) & 0x0F
        status_txt = POWMR_RUN_MODE_CODES.get(pv_topology_code, f"Unknown ({pv_topology_code})")

        # Calculate battery power and status
        battery_current = decoded_data.get("batt_charge_current", 0.0)
        battery_voltage = decoded_data.get("batt_voltage", 0.0)
        battery_power = -(battery_current * battery_voltage)

        batt_status_txt = "Idle"
        if battery_power > 10: 
            batt_status_txt = "Discharging"
        elif battery_power < -10: 
            batt_status_txt = "Charging"

        # Temperature decoding based on inv8851.h structure
        ntc_temps_1 = decoded_data.get("ntc_temps_1", 0)
        ntc_temps_2 = decoded_data.get("ntc_temps_2", 0)
        
        # Word 51: ntc2_temperature (low byte) | ntc3_temperature (high byte)
        ntc2_temp = ntc_temps_1 & 0xFF if ntc_temps_1 else None
        ntc3_temp = (ntc_temps_1 >> 8) & 0xFF if ntc_temps_1 else None
        
        # Word 52: ntc4_temperature (low byte) | bts_temperature (high byte)
        ntc4_temp = ntc_temps_2 & 0xFF if ntc_temps_2 else None
        bts_temp = (ntc_temps_2 >> 8) & 0xFF if ntc_temps_2 else None
        
        # Select the most appropriate temperature readings
        # ntc3 is likely the main inverter temperature, bts is battery temperature sensor
        inverter_temp = ntc3_temp if ntc3_temp and ntc3_temp > 0 else ntc2_temp
        battery_temp = bts_temp if bts_temp and bts_temp > 0 else None

        # Process alert bitfields
        alert_bitfields = {
            reg['addr']: int(decoded_data.get(key, 0)) 
            for key, reg in POWMR_REGISTERS.items() 
            if reg.get('unit') == 'Bitfield'
        }
        active_faults, categorized_alerts = self._decode_powmr_alerts(alert_bitfields)

        return {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: status_txt,
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status_txt,
            StandardDataKeys.AC_POWER_WATTS: decoded_data.get("load_watt"),
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: decoded_data.get("pv_power"),
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: 0,  # Not directly available
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: decoded_data.get("load_watt"),
            StandardDataKeys.BATTERY_POWER_WATTS: battery_power,
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: inverter_temp,
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: battery_temp,
            StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: decoded_data.get("grid_voltage"),
            StandardDataKeys.GRID_L1_CURRENT_AMPS: decoded_data.get("grid_current"),
            StandardDataKeys.GRID_FREQUENCY_HZ: decoded_data.get("grid_freq"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: battery_voltage,
            StandardDataKeys.BATTERY_CURRENT_AMPS: abs(battery_current),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: decoded_data.get("bms_battery_soc"),
            StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: decoded_data.get("pv_voltage"),
            StandardDataKeys.PV_MPPT1_CURRENT_AMPS: decoded_data.get("pv_current"),
            StandardDataKeys.PV_MPPT1_POWER_WATTS: decoded_data.get("pv_power"),
            StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_CODES_LIST: active_faults,
            StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT: categorized_alerts,
            "raw_values": decoded_data  # Include raw values for debugging
        }

    def _decode_powmr_alerts(self, raw_bitfield_values: Dict[int, int]) -> Tuple[List[int], Dict[str, List[str]]]:
        """
        Decode alert bitfields into categorized alert messages.
        
        Processes the bitfield registers to extract active alerts and faults,
        categorizes them according to type (system, grid, warning, etc.), and
        generates both numeric codes and human-readable descriptions.
        
        Args:
            raw_bitfield_values: Dictionary mapping register addresses to bitfield values
            
        Returns:
            Tuple containing:
            - List of numeric alert codes for unique identification
            - Dictionary of categorized alert descriptions by type
            
        Note:
            - Numeric codes are generated as (register_addr << 16) | bit_position
            - Unknown bits are reported with generic descriptions
            - Empty categories are included in the result for consistency
        """
        active_alert_codes_numeric: List[int] = []
        categorized_alert_details: Dict[str, List[str]] = {cat: [] for cat in ALERT_CATEGORIES}
        
        for reg_addr, reg_val in raw_bitfield_values.items():
            map_info = POWMR_ALERT_MAPS.get(reg_addr)
            if not map_info or not isinstance(reg_val, int): 
                continue
            
            bit_map: Dict[int, str] = map_info.get("bits", {})
            category: str = map_info.get("category", "unknown")

            # Check each bit in the 16-bit register
            for bit_pos in range(16):
                if (reg_val >> bit_pos) & 1:
                    # Generate unique numeric code
                    numeric_code = (reg_addr << 16) | bit_pos 
                    active_alert_codes_numeric.append(numeric_code)
                    
                    # Get human-readable description
                    alert_detail = bit_map.get(bit_pos, f"Unknown Bit {bit_pos} (Reg {reg_addr})")
                    
                    # Ensure category exists in result dictionary
                    if category not in categorized_alert_details:
                        categorized_alert_details[category] = []
                    categorized_alert_details[category].append(alert_detail)
        
        return active_alert_codes_numeric, categorized_alert_details