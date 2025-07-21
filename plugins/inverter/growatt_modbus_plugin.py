# plugins/inverter/growatt_modbus_plugin.py
"""
Growatt Modbus Inverter Plugin

This plugin communicates with Growatt hybrid inverters using Modbus TCP and Serial protocols.
It supports comprehensive monitoring of inverter status, power generation, battery management,
and energy statistics for Growatt inverter models using the V1.24 protocol specification.

Features:
- Dual connection support (Modbus TCP and Serial)
- Complete V1.24 protocol implementation (42+ input registers, 35+ holding registers)
- Real-time monitoring of PV generation, battery status, and grid interaction
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

Protocol Reference: Growatt Modbus RTU Protocol V1.24 (2020 edition)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

import logging
import struct
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

# This plugin requires the pymodbus library.
try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException, ConnectionException as ModbusConnectionException
    from pymodbus.pdu import ExceptionResponse
except ImportError:
    ModbusSerialClient = None
    ModbusTcpClient = None

if TYPE_CHECKING:
    from core.app_state import AppState

from .growatt_modbus_constants import (
    GROWATT_INPUT_REGISTERS,
    GROWATT_HOLD_REGISTERS,
    GROWATT_STATUS_CODES,
    GROWATT_STORAGE_WORK_MODES
)
from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port, check_icmp_ping
from enum import Enum

UNKNOWN = "Unknown"

class ConnectionType(str, Enum):
    """Enumeration for the supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"

class GrowattModbusPlugin(DevicePlugin):
    """
    A plugin to interact with Growatt inverters via Modbus TCP or RTU.

    This class implements the DevicePlugin interface to provide a standardized
    way of connecting to, reading data from, and interpreting data from Growatt
    inverters. It handles Modbus communication, register decoding, data
    standardization, and error handling.

    The plugin supports reading both static device information and dynamic
    operational data from Growatt inverters using either Modbus TCP (network)
    or Modbus RTU (serial) communication protocols. It supports both standard
    inverter and storage/hybrid inverter models.
    """

    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the GrowattModbusPlugin instance.

        Args:
            instance_name: A unique name for this plugin instance.
            plugin_specific_config: A dictionary of configuration parameters.
            main_logger: The main application logger.
            app_state: The global application state object, if available.
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        if ModbusSerialClient is None or ModbusTcpClient is None:
            raise ImportError("The 'growatt_modbus_plugin' requires 'pymodbus' to be installed.")

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
        self.logger.info(f"Growatt Plugin '{self.instance_name}': Initialized. Conn: {self.connection_type.value}, Target: {target_info}, SlaveID: {self.slave_address}.")

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "growatt_modbus"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "Growatt Modbus Inverter"

    def connect(self) -> bool:
        """
        Establishes a connection to the Growatt inverter via Modbus TCP or RTU.

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
            self.logger.info(f"Growatt Plugin '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
            port_open, rtt_ms, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open:
                self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} is not open. Error: {err_msg}"
                self.logger.error(self.last_error_message)
                icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                if not icmp_ok:
                    self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host is likely down or blocked.")
                return False

        self.logger.info(f"Growatt Plugin '{self.instance_name}': Attempting to connect via {self.connection_type.value}...")
        try:
            if self.connection_type == ConnectionType.SERIAL:
                self.client = ModbusSerialClient(
                    method='rtu', port=self.serial_port, baudrate=self.baud_rate,
                    stopbits=1, bytesize=8, parity='N', timeout=self.modbus_timeout_seconds
                )
            else:  # TCP
                self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=self.modbus_timeout_seconds)
            
            if self.client.connect():
                self._is_connected_flag = True
                self.logger.info(f"Growatt Plugin '{self.instance_name}': Successfully connected.")
                return True
            else:
                self.last_error_message = "Pymodbus client.connect() returned False."
        except Exception as e:
            self.last_error_message = f"Connection exception: {e}"
            self.logger.error(f"Growatt Plugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
        
        if self.client:
            self.client.close()
        self.client = None
        self._is_connected_flag = False
        return False

    def disconnect(self) -> None:
        """Closes the Modbus connection and resets the client."""
        if self.client:
            self.logger.info(f"Growatt Plugin '{self.instance_name}': Disconnecting client.")
            try:
                self.client.close()
            except Exception as e:
                self.logger.error(f"Growatt Plugin '{self.instance_name}': Error closing Modbus connection: {e}", exc_info=True)
        self.client = None
        self._is_connected_flag = False

    def read_static_data(self) -> Dict[str, Any]:
        """
        Reads static device information from the Growatt inverter.

        This includes serial number, firmware versions, and detected
        number of MPPTs and phases. The data is cached after the first successful read.

        Returns:
            A dictionary containing the standardized static data, or empty dict if the read fails.
        """
        if self.last_known_static_data:
            return self.last_known_static_data
        
        self.logger.info(f"Growatt Plugin '{self.instance_name}': Reading static data...")
        if not self.is_connected:
            self.logger.error(f"Growatt Plugin '{self.instance_name}': Cannot read static data, not connected.")
            return {}

        try:
            # Read a block of holding registers for static info
            result = self.client.read_holding_registers(0, 45, slave=self.slave_address)
            if result.isError(): raise ConnectionException(f"Modbus error reading holding registers: {result}")
            
            decoded = self._decode_registers(result.registers, GROWATT_HOLD_REGISTERS, 0)

            firmware = decoded.get("firmware_version", "")
            control_fw = decoded.get("control_firmware_version", "")
            
            static_data = {
                StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
                StandardDataKeys.STATIC_INVERTER_MANUFACTURER: "Growatt",
                StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: decoded.get("serial_number", UNKNOWN),
                StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION: f"FW: {firmware}, Control: {control_fw}",
                StandardDataKeys.STATIC_NUMBER_OF_MPPTS: 2,
                StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: 1,
            }
            self.last_known_static_data = static_data
            return static_data

        except ConnectionException as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"Growatt Plugin '{self.instance_name}': Failed to read static data: {e}")
            self.disconnect()
            return {}

    def read_dynamic_data(self) -> Dict[str, Any]:
        """
        Reads real-time operational data from the Growatt inverter.

        This includes power values, voltages, currents, temperatures, and status
        information. The data is read from input registers in two blocks to support
        both standard and storage/hybrid inverter models.

        Returns:
            A dictionary containing the standardized operational data, or empty dict if the read fails.
        """
        if not self.is_connected:
            self.logger.error(f"Growatt Plugin '{self.instance_name}': Cannot read dynamic data, not connected.")
            return {}

        try:
            all_registers = {}
            # Read first block of input registers (0-124)
            res1 = self.client.read_input_registers(0, 125, slave=self.slave_address)
            if res1.isError(): raise ConnectionException(f"Modbus error reading input block 1: {res1}")
            for i, reg in enumerate(res1.registers): all_registers[i] = reg
            
            # Read second block for storage systems (1000-1124)
            res2 = self.client.read_input_registers(1000, 125, slave=self.slave_address)
            if res2.isError(): raise ConnectionException(f"Modbus error reading input block 2: {res2}")
            for i, reg in enumerate(res2.registers): all_registers[1000 + i] = reg

            decoded = self._decode_registers_from_dict(all_registers, GROWATT_INPUT_REGISTERS)
            return self._standardize_operational_data(decoded)

        except ConnectionException as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"Growatt Plugin '{self.instance_name}': Failed to read dynamic data: {e}")
            self.disconnect()
            return {}

    def _decode_registers(self, registers: List[int], register_map: Dict[str, Any], start_addr: int) -> Dict[str, Any]:
        """
        Decodes a list of registers based on a starting address.

        Args:
            registers: List of raw register values.
            register_map: The register map defining how to decode each register.
            start_addr: The starting address of the register block.

        Returns:
            A dictionary of decoded values keyed by register name.
        """
        reg_dict = {start_addr + i: val for i, val in enumerate(registers)}
        return self._decode_registers_from_dict(reg_dict, register_map)

    def _decode_registers_from_dict(self, reg_dict: Dict[int, int], register_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decodes registers from a dictionary of {address: value}.

        Args:
            reg_dict: Dictionary mapping register addresses to their raw values.
            register_map: The register map defining how to decode each register.

        Returns:
            A dictionary of decoded values keyed by register name.
        """
        decoded = {}
        for key, info in register_map.items():
            addr = info["addr"]
            if addr not in reg_dict: continue

            if info.get("type") == "uint32":
                if addr + 1 in reg_dict:
                    value = (reg_dict[addr] << 16) + reg_dict[addr + 1]
                else: continue
            elif info.get("type") == "string":
                length = info.get("len", 1)
                byte_data = b''
                for i in range(length):
                    if addr + i in reg_dict:
                        byte_data += struct.pack('>H', reg_dict[addr + i])
                value = byte_data.decode('ascii', errors='ignore').strip().replace('\x00', '')
            else: # int16 or uint16
                value = reg_dict[addr]
                if info.get("type") == "int16":
                    value = struct.unpack('>h', struct.pack('>H', value))[0]

            scale = info.get("scale", 1.0)
            decoded[key] = float(value) * scale if scale != 1.0 else value
        return decoded

    def _standardize_operational_data(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts raw Growatt register data into standardized format.

        Args:
            d: Dictionary of decoded register values from the Growatt inverter.

        Returns:
            A dictionary containing standardized operational data keys and values.
        """
        # Determine status text
        status_code = d.get("inverter_status")
        status_text = GROWATT_STATUS_CODES.get(status_code, f"Unknown ({status_code})")
        if "system_work_state" in d:
             storage_status_code = d["system_work_state"]
             status_text = GROWATT_STORAGE_WORK_MODES.get(storage_status_code, status_text)

        # Calculate battery power and current (convention: negative is charging)
        charge_power = d.get("battery_charge_power", 0.0)
        discharge_power = d.get("battery_discharge_power", 0.0)
        battery_power = discharge_power - charge_power

        battery_current = 0
        if d.get("battery_voltage", 0) > 0:
            battery_current = battery_power / d["battery_voltage"]

        batt_status_txt = "Idle"
        if battery_power > 10: batt_status_txt = "Discharging"
        elif battery_power < -10: batt_status_txt = "Charging"

        pv_power = d.get("pv1_power", 0) + d.get("pv2_power", 0)

        return {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: status_text,
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status_txt,
            StandardDataKeys.AC_POWER_WATTS: d.get("output_power"),
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv_power,
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: d.get("grid_l1_power"),
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: d.get("power_to_user"),
            StandardDataKeys.BATTERY_POWER_WATTS: battery_power,
            StandardDataKeys.BATTERY_CURRENT_AMPS: battery_current,
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: d.get("inverter_temperature"),
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: d.get("battery_temperature"),
            StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_l1_voltage"),
            StandardDataKeys.GRID_L1_CURRENT_AMPS: d.get("grid_l1_current"),
            StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: d.get("battery_voltage"),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: d.get("battery_soc"),
            StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: d.get("pv1_voltage"),
            StandardDataKeys.PV_MPPT1_CURRENT_AMPS: d.get("pv1_current"),
            StandardDataKeys.PV_MPPT1_POWER_WATTS: d.get("pv1_power"),
            StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: d.get("pv2_voltage"),
            StandardDataKeys.PV_MPPT2_CURRENT_AMPS: d.get("pv2_current"),
            StandardDataKeys.PV_MPPT2_POWER_WATTS: d.get("pv2_power"),
            StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: d.get("total_pv_energy"),
            StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: d.get("today_battery_charge_energy"),
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: d.get("today_battery_discharge_energy"),
            "raw_values": d
        }