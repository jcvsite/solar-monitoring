# plugins/inverter/luxpower_modbus_plugin.py
"""
LuxPower Modbus Inverter Plugin

This plugin communicates with LuxPower hybrid inverters using both Modbus TCP and Serial protocols.
It supports comprehensive monitoring of inverter status, power generation, battery management,
and energy statistics for LuxPower inverter models including LXP-5K, LXP-12K, and LXP-LB-5K.

Features:
- Dual connection support (Modbus TCP and Serial)
- Pre-connection validation for TCP connections
- Complete register mapping (90+ operational registers, 50+ configuration registers)
- Real-time monitoring of PV generation, battery status, and grid interaction
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- Comprehensive error handling and connection management
- Support for multiple LuxPower inverter models
- Automatic retry mechanisms and connection recovery

Supported Models:
- LuxPower LXP-5K series
- LuxPower LXP-12K series
- LuxPower LXP-LB-5K series
- Compatible LuxPower hybrid inverter models

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""


import time
import struct
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException, ConnectionException as ModbusConnectionException
from pymodbus.pdu import ExceptionResponse

if TYPE_CHECKING:
    from core.app_state import AppState

from .luxpower_modbus_plugin_constants import (
    LUXPOWER_INPUT_REGISTERS, LUXPOWER_HOLD_REGISTERS,
    LUXPOWER_STATUS_CODES, LUXPOWER_MODEL_CODES,
    LUXPOWER_FAULT_CODES, LUXPOWER_WARNING_CODES,
    LUXPOWER_BITFIELD_DEFINITIONS, MODBUS_EXCEPTION_CODES
)
from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port, check_icmp_ping

ERROR_READ = "read_error"
ERROR_DECODE = "decode_error"
UNKNOWN = "Unknown"

class ConnectionType(str, Enum):
    """Enumeration for the supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"

class LuxpowerModbusPlugin(DevicePlugin):
    """
    A plugin to interact with LuxPower inverters via Modbus TCP or Serial.

    This class implements the DevicePlugin interface to provide a standardized
    way of connecting to, reading data from, and interpreting data from LuxPower
    inverters. It handles Modbus communication, register decoding, data
    standardization, and error handling.

    The plugin supports reading both static device information and dynamic
    operational data from LuxPower inverters using either Modbus TCP (network)
    or Modbus RTU (serial) communication protocols.
    """

    @staticmethod
    def _plugin_decode_register(registers: List[int], info: Dict[str, Any], logger_instance: logging.Logger) -> Tuple[Any, Optional[str]]:
        """
        Decodes raw register values into a scaled and typed Python object.

        Args:
            registers: A list of integers representing the raw Modbus register values.
            info: The dictionary of register information from LUXPOWER_INPUT_REGISTERS or LUXPOWER_HOLD_REGISTERS.
            logger_instance: The logger to use for reporting errors.

        Returns:
            A tuple containing:
            - The decoded and scaled value. On error, returns the string "decode_error".
            - The unit of the value as a string (e.g., "V", "A", "kWh"), or None.
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
            elif reg_type == "bitfield":
                value = registers[0]
            else:
                raise ValueError(f"Unsupported type: {reg_type}")

            if isinstance(value, (int, float)):
                should_scale = (abs(scale - 1.0) > 1e-9) and (reg_type not in ["bitfield"])
                final_value = float(value) * scale if should_scale else value
                return final_value, unit
            else:
                return value, unit
                
        except (struct.error, ValueError, IndexError, TypeError) as e:
            logger_instance.error(f"LuxPowerPlugin: Decode Error for '{key_name_for_log}' ({reg_type}) with {registers}: {e}", exc_info=False)
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
        if reg_type in ["uint16", "int16", "bitfield"]:
            return 1
        logger_instance.warning(f"LuxPowerPlugin: Unknown type '{reg_type}' in get_register_count. Assuming 1.")
        return 1

    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the LuxpowerModbusPlugin instance.

        Args:
            instance_name: A unique name for this plugin instance.
            plugin_specific_config: A dictionary of configuration parameters.
            main_logger: The main application logger.
            app_state: The global application state object, if available.
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        self.last_error_message: Optional[str] = None
        self.last_known_static_data: Optional[Dict[str, Any]] = None
        
        # Parse connection configuration
        try:
            self.connection_type = ConnectionType(self.plugin_config.get("connection_type", "tcp").strip().lower())
        except ValueError:
            self.logger.warning(f"Invalid connection_type '{self.plugin_config.get('connection_type')}' specified. Defaulting to TCP.")
            self.connection_type = ConnectionType.TCP

        # Connection parameters
        self.serial_port = self.plugin_config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = int(self.plugin_config.get("baud_rate", 9600))
        self.tcp_host = self.plugin_config.get("tcp_host", "192.168.1.100")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 8000))  # Default port from lxp-bridge
        self.slave_address = int(self.plugin_config.get("slave_address", 1))
        
        # Modbus communication parameters
        DEFAULT_MODBUS_TIMEOUT_S = 10
        DEFAULT_INTER_READ_DELAY_MS = 500
        DEFAULT_MAX_REGS_PER_READ = 50
        
        self.modbus_timeout_seconds = int(self.plugin_config.get("modbus_timeout_seconds", DEFAULT_MODBUS_TIMEOUT_S))
        self.inter_read_delay_ms = int(self.plugin_config.get("inter_read_delay_ms", DEFAULT_INTER_READ_DELAY_MS))
        self.max_regs_per_read = int(self.plugin_config.get("max_regs_per_read", DEFAULT_MAX_REGS_PER_READ))
        self.max_read_retries_per_group = int(self.plugin_config.get("max_read_retries_per_group", 2))
        
        self.client = None
        
        target_info = f"{self.tcp_host}:{self.tcp_port}" if self.connection_type == ConnectionType.TCP else f"{self.serial_port}:{self.baud_rate}"
        self.logger.info(f"LuxPower Plugin '{self.instance_name}': Initialized. Conn: {self.connection_type.value}, Target: {target_info}, SlaveID: {self.slave_address}.")

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "luxpower_modbus"
    
    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "LuxPower Modbus Inverter"

    def connect(self) -> bool:
        """
        Establishes a connection to the LuxPower inverter.

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
            self.logger.info(f"LuxPowerPlugin '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
            port_open, rtt_ms, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open:
                self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} is not open. Error: {err_msg}"
                self.logger.error(self.last_error_message)
                icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                if not icmp_ok:
                    self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host is likely down or blocked.")
                return False

        self.logger.info(f"LuxPowerPlugin '{self.instance_name}': Attempting to connect via {self.connection_type.value}...")
        try:
            if self.connection_type == ConnectionType.SERIAL:
                self.client = ModbusSerialClient(port=self.serial_port, baudrate=self.baud_rate, timeout=self.modbus_timeout_seconds)
            else:  # TCP
                self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=self.modbus_timeout_seconds)
            
            if self.client.connect():
                self._is_connected_flag = True
                self.logger.info(f"LuxPowerPlugin '{self.instance_name}': Successfully connected.")
                return True
            else:
                self.last_error_message = "Pymodbus client.connect() returned False."
        except Exception as e:
            self.last_error_message = f"Connection exception: {e}"
            self.logger.error(f"LuxPowerPlugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
        
        if self.client:
            self.client.close()
        self.client = None
        self._is_connected_flag = False
        return False
        
    def disconnect(self) -> None:
        """Closes the Modbus connection and resets the client."""
        if self.client:
            self.logger.info(f"LuxPowerPlugin '{self.instance_name}': Disconnecting client.")
            try:
                self.client.close()
            except Exception as e:
                self.logger.error(f"LuxPowerPlugin '{self.instance_name}': Error closing Modbus connection: {e}", exc_info=True)
        self._is_connected_flag = False
        self.client = None

    def read_static_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads static device information from the inverter.

        This includes serial number, model name, firmware version, and detected
        number of MPPTs and phases.

        Returns:
            A dictionary containing the standardized static data, or None if the read fails.
        """
        if self.last_known_static_data:
            return self.last_known_static_data
            
        self.logger.info(f"LuxPowerPlugin '{self.instance_name}': Reading static data...")
        if not self.is_connected:
            self.logger.error(f"LuxPowerPlugin '{self.instance_name}': Cannot read static data, not connected.")
            return None

        try:
            # Read 50 holding registers starting from address 0
            result = self.client.read_holding_registers(0, 50, slave=self.slave_address)
            
            if isinstance(result, ExceptionResponse):
                exc_msg = MODBUS_EXCEPTION_CODES.get(result.exception_code, f'Unknown Modbus Exc ({result.exception_code})')
                raise ModbusException(f"Slave Exc Code {result.exception_code}: {exc_msg}")
            if result.isError():
                raise ModbusIOException("Pymodbus reported general error")
            if not hasattr(result, "registers") or result.registers is None or len(result.registers) < 50:
                raise ModbusIOException(f"Short response (Got {len(result.registers) if result.registers else 'None'}, Exp 50)")

            decoded = self._decode_registers_from_response(result.registers, LUXPOWER_HOLD_REGISTERS)

            # Reconstruct ASCII serial numbers from registers
            inverter_sn = self._decode_string_from_registers(decoded, "serial_number_part_", 5)

            # Format firmware versions
            fw_master = decoded.get("firmware_version_master", 0)
            fw_slave = decoded.get("firmware_version_slave", 0)
            fw_manager = decoded.get("firmware_version_manager", 0)
            firmware_version = f"M:{fw_master}, S:{fw_slave}, D:{fw_manager}"

            model_code = decoded.get("inverter_model")
            model_name = LUXPOWER_MODEL_CODES.get(model_code, f"Unknown ({model_code})")

            static_data = {
                StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
                StandardDataKeys.STATIC_INVERTER_MANUFACTURER: "LuxPower",
                StandardDataKeys.STATIC_INVERTER_MODEL_NAME: model_name,
                StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: inverter_sn if inverter_sn and inverter_sn not in [ERROR_READ, ERROR_DECODE, UNKNOWN] else UNKNOWN,
                StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION: firmware_version,
                StandardDataKeys.STATIC_NUMBER_OF_MPPTS: 2,
                StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: 1,
                "raw_config_values": decoded,
            }
            self.last_known_static_data = static_data
            return static_data

        except (ModbusException, ModbusIOException, ModbusConnectionException, OSError, AttributeError, struct.error) as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"LuxPowerPlugin '{self.instance_name}': {self.last_error_message}")
            self.disconnect()
            return None
        except Exception as e:
            self.last_error_message = f"Unexpected error reading static data: {e}"
            self.logger.error(f"LuxPowerPlugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
            self.disconnect()
            return None

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads dynamic/operational data from the inverter.

        Returns:
            A dictionary containing the standardized dynamic data, or None if the read fails.
        """
        if not self.is_connected:
            self.logger.error(f"LuxPowerPlugin '{self.instance_name}': Cannot read dynamic data, not connected.")
            return None

        try:
            # Read 100 input registers starting from address 0
            result = self.client.read_input_registers(0, 100, slave=self.slave_address)
            
            if isinstance(result, ExceptionResponse):
                exc_msg = MODBUS_EXCEPTION_CODES.get(result.exception_code, f'Unknown Modbus Exc ({result.exception_code})')
                raise ModbusException(f"Slave Exc Code {result.exception_code}: {exc_msg}")
            if result.isError():
                raise ModbusIOException("Pymodbus reported general error")
            if not hasattr(result, "registers") or result.registers is None or len(result.registers) < 100:
                raise ModbusIOException(f"Short response (Got {len(result.registers) if result.registers else 'None'}, Exp 100)")
            
            decoded = self._decode_registers_from_response(result.registers, LUXPOWER_INPUT_REGISTERS)
            return self._standardize_operational_data(decoded)

        except (ModbusException, ModbusIOException, ModbusConnectionException, OSError, AttributeError, struct.error) as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"LuxPowerPlugin '{self.instance_name}': {self.last_error_message}")
            self.disconnect()
            return None
        except Exception as e:
            self.last_error_message = f"Unexpected error reading dynamic data: {e}"
            self.logger.error(f"LuxPowerPlugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
            self.disconnect()
            return None

    def _decode_registers_from_response(self, registers: List[int], register_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decodes raw register values from a Modbus response into a dictionary of scaled values.

        Args:
            registers: A list of integers representing the raw Modbus register values.
            register_map: The dictionary of register information (LUXPOWER_INPUT_REGISTERS or LUXPOWER_HOLD_REGISTERS).

        Returns:
            A dictionary of decoded and scaled values.
        """
        decoded = {}
        for key, info in register_map.items():
            addr = info["addr"]
            reg_count = self._plugin_get_register_count(info["type"], self.logger)
            
            if addr + reg_count - 1 >= len(registers):
                continue  # Skip if not enough registers
                
            reg_slice = registers[addr:addr + reg_count]
            value, _ = self._plugin_decode_register(reg_slice, info, self.logger)
            
            if value != ERROR_DECODE:
                decoded[key] = value
                
        return decoded



    def _decode_string_from_registers(self, decoded_data: Dict[str, Any], prefix: str, count: int) -> str:
        """
        Decodes ASCII string data from multiple registers.

        Args:
            decoded_data: Dictionary of decoded register values.
            prefix: The prefix of the register keys (e.g., "serial_number_part_").
            count: The number of registers to decode.

        Returns:
            The decoded ASCII string with null bytes and whitespace stripped.
        """
        chars = []
        for i in range(1, count + 1):
            reg_val = decoded_data.get(f"{prefix}{i}", 0)
            if reg_val == 0: 
                break
            chars.extend([chr(reg_val >> 8), chr(reg_val & 0xFF)])
        return "".join(chars).strip()

    def _decode_faults_and_warnings(self, d: Dict[str, Any]) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Decodes fault and warning codes from register data.

        Args:
            d: Dictionary of decoded register values.

        Returns:
            A tuple containing:
            - A list of active fault messages.
            - A dictionary of categorized alerts (fault, warning, status).
        """
        active_faults, active_warnings = [], []
        for i in range(1, 6):
            fault_code = d.get(f"fault_code_{i}")
            if fault_code: 
                active_faults.extend(v for k, v in LUXPOWER_FAULT_CODES.items() if fault_code & k)
            warn_code = d.get(f"warning_code_{i}")
            if warn_code: 
                active_warnings.extend(v for k, v in LUXPOWER_WARNING_CODES.items() if warn_code & k)
        
        categorized = {"fault": active_faults, "warning": active_warnings}
        if not active_faults and not active_warnings: 
            categorized["status"] = ["OK"]
        return active_faults, categorized

    def _decode_bitfields(self, d: Dict[str, Any]) -> List[str]:
        """
        Decodes bitfield registers into a list of active status descriptions.

        Args:
            d: Dictionary of decoded register values.

        Returns:
            A list of active status descriptions from bitfield registers.
        """
        active_statuses = []
        for key, bit_map in LUXPOWER_BITFIELD_DEFINITIONS.items():
            reg_val = d.get(key)
            if isinstance(reg_val, int):
                for bit, description in bit_map.items():
                    if (reg_val >> bit) & 1:
                        active_statuses.append(description)
        return active_statuses

    def _standardize_operational_data(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts raw LuxPower register data into standardized format.

        Args:
            d: Dictionary of decoded register values from the LuxPower inverter.

        Returns:
            A dictionary containing standardized operational data keys and values.
        """
        status_code = d.get("inverter_status_code")
        status_txt = LUXPOWER_STATUS_CODES.get(status_code, f"Unknown ({status_code})")
        
        battery_power = d.get("battery_power", 0.0)
        batt_status_txt = "Idle"
        if battery_power > 10: batt_status_txt = "Discharging"
        elif battery_power < -10: batt_status_txt = "Charging"
        
        active_faults, categorized_alerts = self._decode_faults_and_warnings(d)
        if active_faults: status_txt = "Fault"
        
        # Add bitfield statuses to alerts
        bit_statuses = self._decode_bitfields(d)
        if bit_statuses:
            if "status" not in categorized_alerts: categorized_alerts["status"] = []
            categorized_alerts["status"].extend(bit_statuses)

        return {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: status_txt,
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status_txt,
            StandardDataKeys.AC_POWER_WATTS: d.get("inverter_power"),
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: d.get("pv1_power", 0) + d.get("pv2_power", 0),
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: d.get("grid_power"),
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: d.get("inverter_power"),
            StandardDataKeys.BATTERY_POWER_WATTS: -battery_power,
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: d.get("inverter_temperature"),
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: d.get("battery_temperature"),
            StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_voltage"),
            StandardDataKeys.GRID_L1_CURRENT_AMPS: d.get("grid_current"),
            StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: d.get("battery_voltage"),
            StandardDataKeys.BATTERY_CURRENT_AMPS: d.get("battery_current"),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: d.get("battery_soc"),
            StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: d.get("pv1_voltage"),
            StandardDataKeys.PV_MPPT1_CURRENT_AMPS: d.get("pv1_current"),
            StandardDataKeys.PV_MPPT1_POWER_WATTS: d.get("pv1_power"),
            StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: d.get("pv2_voltage"),
            StandardDataKeys.PV_MPPT2_CURRENT_AMPS: d.get("pv2_current"),
            StandardDataKeys.PV_MPPT2_POWER_WATTS: d.get("pv2_power"),
            StandardDataKeys.EPS_TOTAL_ACTIVE_POWER_WATTS: d.get("eps_power"),
            StandardDataKeys.EPS_L1_VOLTAGE_VOLTS: d.get("eps_voltage"),
            StandardDataKeys.EPS_L1_CURRENT_AMPS: d.get("eps_current"),
            StandardDataKeys.EPS_L1_FREQUENCY_HZ: d.get("eps_frequency"),
            StandardDataKeys.ENERGY_PV_DAILY_KWH: d.get("pv_power_today"),
            StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: d.get("total_pv_yield"),
            StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: d.get("charge_energy_today"),
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: d.get("discharge_energy_today"),
            StandardDataKeys.ENERGY_BATTERY_TOTAL_CHARGE_KWH: d.get("total_charge_energy"),
            StandardDataKeys.ENERGY_BATTERY_TOTAL_DISCHARGE_KWH: d.get("total_discharge_energy"),
            StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: d.get("imported_power_today"),
            StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH: d.get("exported_power_today"),
            StandardDataKeys.ENERGY_GRID_TOTAL_IMPORT_KWH: d.get("total_energy_import"),
            StandardDataKeys.ENERGY_GRID_TOTAL_EXPORT_KWH: d.get("total_energy_export"),
            StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_MESSAGES_LIST: active_faults,
            StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT: categorized_alerts,
            "raw_values": d
        }