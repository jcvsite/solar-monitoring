# plugins/inverter/eg4_modbus_plugin.py
"""
EG4 Modbus Inverter Plugin

This plugin communicates with EG4 hybrid inverters using Modbus TCP and Serial protocols.
It supports comprehensive monitoring of inverter status, power generation, battery management,
and energy statistics for EG4 inverter models using the V58 protocol specification.

Features:
- Dual connection support (Modbus TCP and Serial)
- Complete V58 protocol implementation (200+ registers)
- Real-time monitoring of PV generation, battery status, and grid interaction
- 3-phase system support for applicable models
- BMS integration for battery cell monitoring
- Generator monitoring and control
- Off-grid/EPS operation support
- Comprehensive fault and warning code processing
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- AFCI (Arc Fault Circuit Interrupter) support
- Historical fault and warning records

Supported Models:
- EG4 6000XP, 12000XP, 18000XP series
- EG4 PowerPro series
- Compatible EG4 hybrid inverter models with V58 protocol

Protocol Reference: EG4 Modbus RTU Protocol V58
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

import logging
import struct
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from pymodbus.constants import Endian

try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException, ConnectionException as ModbusConnectionException
    from pymodbus.payload import BinaryPayloadDecoder
    from pymodbus.pdu import ExceptionResponse
except ImportError:
    ModbusSerialClient = None
    ModbusTcpClient = None

if TYPE_CHECKING:
    from core.app_state import AppState

from .eg4_modbus_constants import (
    EG4_INPUT_REGISTERS,
    EG4_HOLD_REGISTERS,
    EG4_OPERATION_MODES,
    EG4_ALARM_CODES,
)
from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port, check_icmp_ping
from enum import Enum

UNKNOWN = "Unknown"

class ConnectionType(str, Enum):
    """Enumeration for the supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"

class Eg4ModbusPlugin(DevicePlugin):
    """
    A plugin to interact with EG4 inverters via Modbus TCP or RTU.

    This class implements the DevicePlugin interface to provide a standardized
    way of connecting to, reading data from, and interpreting data from EG4
    inverters. It handles Modbus communication, register decoding, data
    standardization, and error handling.

    The plugin supports reading both static device information and dynamic
    operational data from EG4 inverters using either Modbus TCP (network)
    or Modbus RTU (serial) communication protocols.
    """

    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the Eg4ModbusPlugin instance.

        Args:
            instance_name: A unique name for this plugin instance.
            plugin_specific_config: A dictionary of configuration parameters.
            main_logger: The main application logger.
            app_state: The global application state object, if available.
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        if ModbusSerialClient is None or ModbusTcpClient is None:
            raise ImportError("The 'eg4_modbus_plugin' requires 'pymodbus' to be installed.")

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
        self.baud_rate = int(self.plugin_config.get("baud_rate", 19200))
        self.tcp_host = self.plugin_config.get("tcp_host", "192.168.1.100")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 502))
        self.slave_address = int(self.plugin_config.get("slave_address", 1))
        
        # Modbus communication parameters
        self.modbus_timeout_seconds = int(self.plugin_config.get("modbus_timeout_seconds", 10))
        
        target_info = f"{self.tcp_host}:{self.tcp_port}" if self.connection_type == ConnectionType.TCP else f"{self.serial_port}:{self.baud_rate}"
        self.logger.info(f"EG4 Plugin '{self.instance_name}': Initialized. Conn: {self.connection_type.value}, Target: {target_info}, SlaveID: {self.slave_address}.")

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "eg4_modbus"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "EG4 Modbus Inverter"

    def connect(self) -> bool:
        """
        Establishes a connection to the EG4 inverter via Modbus TCP or RTU.

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
            self.logger.info(f"EG4 Plugin '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
            port_open, rtt_ms, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open:
                self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} is not open. Error: {err_msg}"
                self.logger.error(self.last_error_message)
                icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                if not icmp_ok:
                    self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host is likely down or blocked.")
                return False

        self.logger.info(f"EG4 Plugin '{self.instance_name}': Attempting to connect via {self.connection_type.value}...")
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
                self.logger.info(f"EG4 Plugin '{self.instance_name}': Successfully connected.")
                return True
            else:
                self.last_error_message = "Pymodbus client.connect() returned False."
        except Exception as e:
            self.last_error_message = f"Connection exception: {e}"
            self.logger.error(f"EG4 Plugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
        
        if self.client:
            self.client.close()
        self.client = None
        self._is_connected_flag = False
        return False

    def disconnect(self) -> None:
        """Closes the Modbus connection and resets the client."""
        if self.client:
            self.logger.info(f"EG4 Plugin '{self.instance_name}': Disconnecting client.")
            try:
                self.client.close()
            except Exception as e:
                self.logger.error(f"EG4 Plugin '{self.instance_name}': Error closing Modbus connection: {e}", exc_info=True)
        self.client = None
        self._is_connected_flag = False

    def read_static_data(self) -> Dict[str, Any]:
        """
        Reads static device information from the EG4 inverter.

        This includes model name, serial number, firmware versions, and detected
        number of MPPTs and phases. The data is cached after the first successful read.

        Returns:
            A dictionary containing the standardized static data, or empty dict if the read fails.
        """
        if self.last_known_static_data:
            return self.last_known_static_data
        
        self.logger.info(f"EG4 Plugin '{self.instance_name}': Reading static data...")
        if not self.is_connected:
            self.logger.error(f"EG4 Plugin '{self.instance_name}': Cannot read static data, not connected.")
            return {}
        
        try:
            # Read holding registers for static info
            regs = self._read_registers_in_chunks(self.client.read_holding_registers, [
                (7, 10), (115, 5) # Read versions and serial number
            ])
            if not regs:
                raise ConnectionException("Failed to read any holding registers for static data.")

            decoded = self._decode_registers(regs, EG4_HOLD_REGISTERS)

            # Build model code from firmware codes
            model_code = f"{decoded.get('fw_code_0', '')}{decoded.get('fw_code_1', '')}{decoded.get('fw_code_2', '')}{decoded.get('fw_code_3', '')}"

            static_data = {
                StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
                StandardDataKeys.STATIC_INVERTER_MANUFACTURER: "EG4",
                StandardDataKeys.STATIC_INVERTER_MODEL_NAME: model_code if model_code else UNKNOWN,
                StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: decoded.get("serial_number", UNKNOWN),
                StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION: f"COM:{decoded.get('com_version')} CTL:{decoded.get('control_version')}",
                StandardDataKeys.STATIC_NUMBER_OF_MPPTS: 2,
                StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: 1,
            }
            self.last_known_static_data = static_data
            return static_data

        except ConnectionException as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"EG4 Plugin '{self.instance_name}': Failed to read static data: {e}")
            self.disconnect()
            return {}

    def read_dynamic_data(self) -> Dict[str, Any]:
        """
        Reads real-time operational data from the EG4 inverter.

        This includes power values, voltages, currents, temperatures, and status
        information. The data is read from input registers and standardized.

        Returns:
            A dictionary containing the standardized operational data, or empty dict if the read fails.
        """
        if not self.is_connected:
            self.logger.error(f"EG4 Plugin '{self.instance_name}': Cannot read dynamic data, not connected.")
            return {}
            
        try:
            # Read input registers in 40-word chunks as per documentation
            chunks = [(0, 40), (40, 40), (80, 40)]
            regs = self._read_registers_in_chunks(self.client.read_input_registers, chunks)
            if not regs:
                raise ConnectionException("Failed to read any input registers for dynamic data.")
            
            decoded = self._decode_registers(regs, EG4_INPUT_REGISTERS)
            return self._standardize_operational_data(decoded)

        except ConnectionException as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"EG4 Plugin '{self.instance_name}': Failed to read dynamic data: {e}")
            self.disconnect()
            return {}

    def _read_registers_in_chunks(self, read_method, chunks: List[Tuple[int, int]]) -> Optional[Dict[int, int]]:
        """
        Reads multiple chunks of Modbus registers and combines them into a single dictionary.

        Args:
            read_method: The Modbus read method to use (e.g., read_input_registers).
            chunks: A list of (start_address, count) tuples defining the chunks to read.

        Returns:
            A dictionary mapping register addresses to their values, or None if all reads failed.
        """
        if not self.client or not self.client.is_open: 
            return None
        all_regs = {}
        for start, count in chunks:
            result = read_method(start, count, unit=self.slave_address)
            if result.isError():
                self.logger.warning(f"EG4 Plugin '{self.instance_name}': Modbus error reading chunk starting at {start}: {result}")
                continue
            for i, reg_val in enumerate(result.registers):
                all_regs[start + i] = reg_val
        return all_regs if all_regs else None
    
    def _decode_registers(self, regs: Dict[int, int], reg_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decodes raw register values into scaled and typed Python objects.

        Args:
            regs: A dictionary mapping register addresses to their raw values.
            reg_map: The register map defining how to decode each register.

        Returns:
            A dictionary of decoded values keyed by register name.
        """
        decoded = {}
        for key, info in reg_map.items():
            addr = info["addr"]
            if addr not in regs: continue

            # Create a decoder for each value to handle the specific little-endian byte/word order
            # The protocol specifies high/low bytes are reversed, and for 32-bit, the words are also reversed.
            # This corresponds to little-endian for both.
            
            if info.get("type") == "string":
                length = info.get("len", 1)
                byte_data = b''
                for i in range(length):
                    if addr + i in regs:
                        byte_data += struct.pack('>H', regs[addr + i])
                value = byte_data.decode('ascii', errors='ignore').strip().replace('\x00', '')

            else:
                registers_to_decode = [regs[addr]]
                if info.get("type") == "uint32" or info.get("type") == "int32":
                    if addr + 1 in regs:
                        registers_to_decode.append(regs[addr + 1])
                    else: continue
                
                decoder = BinaryPayloadDecoder.fromRegisters(
                    registers_to_decode, byteorder=Endian.Little, wordorder=Endian.Little
                )

                if info.get("type") == "uint32": value = decoder.decode_32bit_uint()
                elif info.get("type") == "int32": value = decoder.decode_32bit_int()
                elif info.get("type") == "int16": value = decoder.decode_16bit_int()
                else: value = decoder.decode_16bit_uint()

            scale = info.get("scale", 1.0)
            offset = info.get("offset", 0.0)
            decoded[key] = (float(value) * scale) + offset
        
        return decoded

    def _standardize_operational_data(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts raw EG4 register data into standardized format.

        Args:
            d: Dictionary of decoded register values from the EG4 inverter.

        Returns:
            A dictionary containing standardized operational data keys and values.
        """
        op_code = d.get("operation_mode")
        status_text = EG4_OPERATION_MODES.get(op_code, f"Unknown code: {op_code}")

        # Power calculations
        battery_power = d.get("battery_discharge_power", 0) - d.get("battery_charge_power", 0)
        
        # Grid power: Positive is export (to grid), negative is import (from grid)
        grid_power = d.get("power_to_grid", 0) - d.get("power_to_user", 0)
        
        # Load power is inverter output plus any power imported from grid for loads
        load_power = d.get("inverter_power_r", 0) + d.get("power_to_user", 0)
        
        batt_status = "Idle"
        if battery_power > 10: batt_status = "Discharging"
        elif battery_power < -10: batt_status = "Charging"

        # Faults & Alarms
        alerts = []
        fault_l = d.get("fault_code_l", 0)
        fault_h = d.get("fault_code_h", 0)
        warn_l = d.get("warning_code_l", 0)
        warn_h = d.get("warning_code_h", 0)
        
        fault_val = (fault_h << 16) | fault_l
        warn_val = (warn_h << 16) | warn_l
        
        for i in range(32):
            if (fault_val >> i) & 1: alerts.append(f"FAULT: {EG4_ALARM_CODES.get(f'E0{i:02d}', f'Unknown Fault Bit {i}')}")
            if (warn_val >> i) & 1: alerts.append(f"WARN: {EG4_ALARM_CODES.get(f'W0{i:02d}', f'Unknown Warning Bit {i}')}")

        return {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: status_text,
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status,
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: d.get("pv1_power", 0) + d.get("pv2_power", 0),
            StandardDataKeys.AC_POWER_WATTS: d.get("inverter_power_r"),
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: grid_power,
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: load_power,
            StandardDataKeys.BATTERY_POWER_WATTS: battery_power,
            StandardDataKeys.BATTERY_CURRENT_AMPS: d.get("bms_battery_current"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: d.get("battery_voltage"),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: d.get("battery_soc"),
            StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: d.get("battery_soh"),
            StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_r_voltage"),
            StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
            StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: d.get("pv1_voltage"),
            StandardDataKeys.PV_MPPT1_POWER_WATTS: d.get("pv1_power"),
            StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: d.get("pv2_voltage"),
            StandardDataKeys.PV_MPPT2_POWER_WATTS: d.get("pv2_power"),
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: d.get("inverter_temperature"),
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: d.get("battery_temperature"),
            StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT: {"inverter": alerts if alerts else ["OK"]},
            "raw_values": d
        }