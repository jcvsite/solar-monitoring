# plugins/inverter/srne_modbus_plugin.py
"""
SRNE Modbus Inverter Plugin

This plugin communicates with SRNE hybrid inverters using Modbus TCP and Serial protocols.
It supports comprehensive monitoring of inverter status, power generation, battery management,
and energy statistics for SRNE inverter models.

Features:
- Dual connection support (Modbus TCP and Serial)
- Pre-connection validation for TCP connections
- Complete register mapping for operational and configuration data
- Real-time monitoring of PV generation, battery status, and grid interaction
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- Comprehensive error handling and connection management
- Battery management system integration
- Support for multiple SRNE inverter models
- Automatic retry mechanisms and connection recovery

Supported Models:
- SRNE ML series (hybrid inverters)
- SRNE HF series (high-frequency inverters)
- Compatible SRNE hybrid inverter models

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

import logging
import struct
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

# This plugin requires the pymodbus library for communication.
# You can install it with: pip install pymodbus
try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException, ConnectionException as ModbusConnectionException
    from pymodbus.pdu import ExceptionResponse
except ImportError:
    # Allows the application to start even if pymodbus is not installed,
    # but the plugin will fail gracefully at initialization.
    ModbusSerialClient = None
    ModbusTcpClient = None

if TYPE_CHECKING:
    from core.app_state import AppState

from .srne_modbus_constants import (
    SRNE_STATIC_REGISTERS,
    SRNE_DYNAMIC_REGISTERS,
    SRNE_BATTERY_STATUS_CODES,
    SRNE_FAULTS_LOW_MAP,
    SRNE_FAULTS_HIGH_MAP,
)
from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port, check_icmp_ping
from enum import Enum

UNKNOWN = "Unknown"

class ConnectionType(str, Enum):
    """Enumeration for the supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"

class SrneModbusPlugin(DevicePlugin):
    """
    A plugin to interact with SRNE Solar Charge Controllers via Modbus TCP or RTU.

    This class implements the DevicePlugin interface to provide a standardized
    way of connecting to, reading data from, and interpreting data from SRNE
    solar charge controllers. It handles Modbus communication, register
    decoding, data standardization, and error handling.

    The plugin supports reading both static device information and dynamic
    operational data from SRNE controllers using either Modbus TCP (network)
    or Modbus RTU (serial) communication protocols. SRNE controllers are
    primarily DC devices that manage solar panel charging of battery systems.
    """

    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the SrneModbusPlugin instance.

        Args:
            instance_name: A unique name for this plugin instance.
            plugin_specific_config: A dictionary of configuration parameters.
            main_logger: The main application logger.
            app_state: The global application state object, if available.
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        if ModbusSerialClient is None or ModbusTcpClient is None:
            raise ImportError("The 'srne_modbus_plugin' requires 'pymodbus' to be installed.")

        self.last_error_message: Optional[str] = None
        self.last_known_static_data: Optional[Dict[str, Any]] = None
        
        # Parse connection configuration
        try:
            self.connection_type = ConnectionType(self.plugin_config.get("connection_type", "serial").strip().lower())
        except ValueError:
            self.logger.warning(f"Invalid connection_type '{self.plugin_config.get('connection_type')}' specified. Defaulting to Serial.")
            self.connection_type = ConnectionType.SERIAL

        # Connection parameters
        self.serial_port = self.plugin_config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = int(self.plugin_config.get("baud_rate", 9600))
        self.tcp_host = self.plugin_config.get("tcp_host", "192.168.1.100")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 502))
        self.slave_address = int(self.plugin_config.get("slave_address", 1))
        
        # Modbus communication parameters
        self.modbus_timeout_seconds = int(self.plugin_config.get("modbus_timeout_seconds", 10))
        
        target_info = f"{self.tcp_host}:{self.tcp_port}" if self.connection_type == ConnectionType.TCP else f"{self.serial_port}:{self.baud_rate}"
        self.logger.info(f"SRNE Plugin '{self.instance_name}': Initialized. Conn: {self.connection_type.value}, Target: {target_info}, SlaveID: {self.slave_address}.")

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "srne_modbus"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "SRNE Modbus Controller"

    def connect(self) -> bool:
        """
        Establishes a connection to the SRNE controller via Modbus TCP or RTU.

        For TCP connections, it performs a pre-connection check and then
        creates the appropriate Pymodbus client.

        Returns:
            True if the connection was successful, False otherwise.
        """
        if self._is_connected_flag and self.client:
            return True
        if self.client:
            self.disconnect()
        self.last_error_message = None

        if self.connection_type == ConnectionType.TCP:
            self.logger.info(f"SRNE Plugin '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
            port_open, rtt_ms, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open:
                self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} is not open. Error: {err_msg}"
                self.logger.error(self.last_error_message)
                icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                if not icmp_ok:
                    self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host is likely down or blocked.")
                return False

        self.logger.info(f"SRNE Plugin '{self.instance_name}': Attempting to connect via {self.connection_type.value}...")
        try:
            if self.connection_type == ConnectionType.SERIAL:
                self.client = ModbusSerialClient(
                    method='rtu',
                    port=self.serial_port,
                    baudrate=self.baud_rate,
                    stopbits=1,
                    bytesize=8,
                    parity='N',
                    timeout=self.modbus_timeout_seconds
                )
            else:  # TCP
                self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=self.modbus_timeout_seconds)
            
            # Set slave address on client if supported
            if hasattr(self.client, 'slave'):
                self.client.slave = self.slave_address
                
            if self.client.connect():
                self._is_connected_flag = True
                self.logger.info(f"SRNE Plugin '{self.instance_name}': Successfully connected.")
                return True
            else:
                self.last_error_message = "Pymodbus client.connect() returned False."
        except Exception as e:
            self.last_error_message = f"Connection exception: {e}"
            self.logger.error(f"SRNE Plugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
        
        if self.client:
            self.client.close()
        self.client = None
        self._is_connected_flag = False
        return False

    def disconnect(self) -> None:
        """Closes the Modbus connection and resets the client."""
        if self.client:
            self.logger.info(f"SRNE Plugin '{self.instance_name}': Disconnecting client.")
            try:
                self.client.close()
            except Exception as e:
                self.logger.error(f"SRNE Plugin '{self.instance_name}': Error closing Modbus connection: {e}", exc_info=True)
        self.client = None
        self._is_connected_flag = False

    def read_static_data(self) -> Dict[str, Any]:
        """
        Reads static device information from the SRNE controller.

        This includes model name, firmware version, and device characteristics.
        The data is cached after the first successful read.

        Returns:
            A dictionary containing the standardized static data, or empty dict if the read fails.
        """
        if self.last_known_static_data:
            return self.last_known_static_data
        
        self.logger.info(f"SRNE Plugin '{self.instance_name}': Reading static data...")
        if not self.is_connected:
            self.logger.error(f"SRNE Plugin '{self.instance_name}': Cannot read static data, not connected.")
            return {}

        try:
            static_data = {StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter"} # Treat as inverter type
            
            # Read Product Model (ASCII)
            model_info = SRNE_STATIC_REGISTERS["product_model"]
            # Try different parameter formats for pymodbus version compatibility
            try:
                result = self.client.read_holding_registers(model_info["addr"], model_info["len"], unit=self.slave_address)
            except TypeError:
                try:
                    result = self.client.read_holding_registers(model_info["addr"], model_info["len"], slave=self.slave_address)
                except TypeError:
                    result = self.client.read_holding_registers(model_info["addr"], model_info["len"])
            if not result.isError():
                static_data[StandardDataKeys.STATIC_INVERTER_MODEL_NAME] = self._decode_string_from_registers(result.registers)
            else:
                self.logger.warning(f"SRNE Plugin '{self.instance_name}': Failed to read model info: {result}")

            # Read Versions
            sw_info = SRNE_STATIC_REGISTERS["software_version"]
            # Try different parameter formats for pymodbus version compatibility
            try:
                result = self.client.read_holding_registers(sw_info["addr"], sw_info["len"], unit=self.slave_address)
            except TypeError:
                try:
                    result = self.client.read_holding_registers(sw_info["addr"], sw_info["len"], slave=self.slave_address)
                except TypeError:
                    result = self.client.read_holding_registers(sw_info["addr"], sw_info["len"])
            if not result.isError():
                # V03.02.01 is stored as 0003 0201
                v_major = result.registers[0] >> 8
                v_minor = result.registers[0] & 0xFF
                v_patch = result.registers[1]
                static_data[StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION] = f"SW: {v_major:02d}.{v_minor:02d}.{v_patch:02d}"

            # Add manufacturer
            static_data[StandardDataKeys.STATIC_INVERTER_MANUFACTURER] = "SRNE"
            static_data[StandardDataKeys.STATIC_NUMBER_OF_MPPTS] = 1
            static_data[StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC] = 0 # It's a DC device

            self.last_known_static_data = static_data
            return static_data

        except ConnectionException as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"SRNE Plugin '{self.instance_name}': Failed to read static data: {e}")
            self.disconnect()
            return {}

    def read_dynamic_data(self) -> Dict[str, Any]:
        """
        Reads real-time operational data from the SRNE controller.

        This includes battery status, PV power, load power, temperatures, and fault
        information. The data is read from holding registers in a single block.

        Returns:
            A dictionary containing the standardized operational data, or empty dict if the read fails.
        """
        if not self.is_connected:
            self.logger.error(f"SRNE Plugin '{self.instance_name}': Cannot read dynamic data, not connected.")
            return {}

        try:
            # Read all dynamic registers in one block (from 0x0100 to 0x0122)
            start_addr = 0x0100
            count = (0x0122 - 0x0100) + 1
            # Try different parameter formats for pymodbus version compatibility
            try:
                result = self.client.read_holding_registers(start_addr, count, unit=self.slave_address)
            except TypeError:
                try:
                    result = self.client.read_holding_registers(start_addr, count, slave=self.slave_address)
                except TypeError:
                    result = self.client.read_holding_registers(start_addr, count)

            if result.isError() or isinstance(result, ExceptionResponse):
                raise ConnectionException(f"Modbus error reading dynamic registers: {result}")
            
            raw_values = self._decode_registers(result.registers, SRNE_DYNAMIC_REGISTERS, start_addr)
            return self._standardize_operational_data(raw_values)

        except ConnectionException as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"SRNE Plugin '{self.instance_name}': Failed to read dynamic data: {e}")
            self.disconnect()
            return {}

    def _decode_registers(self, registers: List[int], register_map: Dict[str, Any], start_addr: int) -> Dict[str, Any]:
        """
        Decodes raw register values into scaled and typed Python objects.

        Args:
            registers: List of raw register values from the Modbus read.
            register_map: The register map defining how to decode each register.
            start_addr: The starting address of the register block.

        Returns:
            A dictionary of decoded values keyed by register name.
        """
        decoded = {}
        for key, info in register_map.items():
            addr = info["addr"]
            offset = addr - start_addr
            
            if offset < 0 or offset >= len(registers):
                continue
            
            if info.get("type") == "uint32":
                if offset + 1 < len(registers):
                    value = (registers[offset] << 16) | registers[offset + 1]
                else:
                    continue
            else: # uint16
                value = registers[offset]

            scale = info.get("scale", 1.0)
            decoded[key] = float(value) * scale if scale != 1.0 else value
        return decoded

    def _decode_string_from_registers(self, registers: List[int]) -> str:
        """
        Decodes a list of registers into an ASCII string.

        Args:
            registers: List of register values containing ASCII data.

        Returns:
            The decoded ASCII string with null bytes and whitespace stripped.
        """
        byte_data = b''
        for reg in registers:
            byte_data += struct.pack('>H', reg)
        return byte_data.decode('ascii', errors='ignore').strip().replace('\x00', '')

    def _standardize_operational_data(self, decoded_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts raw SRNE register data into standardized format.

        Args:
            decoded_data: Dictionary of decoded register values from the SRNE controller.

        Returns:
            A dictionary containing standardized operational data keys and values.
        """
        # Decode status and faults
        status_reg = decoded_data.get("status_register", 0)
        batt_status_code = status_reg & 0xFF
        load_status_bit = (status_reg >> 15) & 1 # b7 of high byte
        
        battery_status_text = SRNE_BATTERY_STATUS_CODES.get(batt_status_code, f"Unknown ({batt_status_code})")
        is_charging = "charging" in battery_status_text.lower() and "deactivated" not in battery_status_text.lower()
        
        charge_current = decoded_data.get("charge_current", 0.0)
        battery_voltage = decoded_data.get("battery_voltage", 0.0)
        
        # Interface standard: current/power are negative for charging
        battery_power = (charge_current * battery_voltage) if is_charging else 0.0
        battery_current_signed = charge_current if is_charging else 0.0

        # Temperatures
        temp_reg = decoded_data.get("temperatures", 0)
        controller_temp = temp_reg >> 8
        battery_temp = temp_reg & 0xFF

        # Faults
        faults_low = decoded_data.get("fault_info_low", 0)
        faults_high = decoded_data.get("fault_info_high", 0)
        alerts = []
        for i in range(16):
            if (faults_low >> i) & 1: alerts.append(SRNE_FAULTS_LOW_MAP.get(i, f"Unknown Low Fault Bit {i}"))
            if (faults_high >> i) & 1: alerts.append(SRNE_FAULTS_HIGH_MAP.get(i, f"Unknown High Fault Bit {i}"))

        return {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: battery_status_text,
            StandardDataKeys.BATTERY_STATUS_TEXT: battery_status_text,
            StandardDataKeys.AC_POWER_WATTS: 0, # DC-only device
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: decoded_data.get("pv_power"),
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: decoded_data.get("load_power"),
            StandardDataKeys.BATTERY_POWER_WATTS: -battery_power,
            StandardDataKeys.BATTERY_CURRENT_AMPS: -battery_current_signed,
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: controller_temp,
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: battery_temp,
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: battery_voltage,
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: decoded_data.get("battery_soc"),
            StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: decoded_data.get("pv_voltage"),
            StandardDataKeys.PV_MPPT1_CURRENT_AMPS: decoded_data.get("pv_current"),
            StandardDataKeys.PV_MPPT1_POWER_WATTS: decoded_data.get("pv_power"),
            StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT: {"inverter": alerts if alerts else ["OK"]},
            # Pass through daily totals
            StandardDataKeys.ENERGY_PV_DAILY_KWH: decoded_data.get("daily_pv_power_generation", 0) / 1000.0,
            StandardDataKeys.ENERGY_LOAD_DAILY_KWH: decoded_data.get("daily_load_power_consumption", 0) / 1000.0,
            # Pass through lifetime totals
            StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: decoded_data.get("total_pv_power_generation"),
            StandardDataKeys.ENERGY_LOAD_TOTAL_KWH: decoded_data.get("total_load_power_consumption"),
            "raw_values": decoded_data
        }