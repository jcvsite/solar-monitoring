# plugins/inverter/deye_sunsynk_plugin.py
import time
import struct
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.app_state import AppState

from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port, check_icmp_ping
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException, ModbusIOException, ConnectionException as ModbusConnectionException
from pymodbus.pdu import ExceptionResponse

from .deye_sunsynk_plugin_constants import (
    BMS_PROTOCOL_CODES,
    STATUS_CODES,
    MODBUS_EXCEPTION_CODES,
    DEYE_FAULT_CODES,
    DEYE_WARNING_CODES,
    DEYE_COMMON_REGISTERS,
    DEYE_MODERN_HYBRID_REGISTERS,
    DEYE_LEGACY_HYBRID_REGISTERS,
    DEYE_THREE_PHASE_REGISTERS,
    ALL_DEYE_REGISTERS
)

ERROR_READ = "read_error"
ERROR_DECODE = "decode_error"
UNKNOWN = "Unknown"

class ConnectionType(str, Enum):
    """Enumeration for the supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"
class DeyeSunsynkPlugin(DevicePlugin):
    """
    Plugin for Deye and Sunsynk hybrid inverters using Modbus communication.
    
    This plugin supports multiple Deye/Sunsynk inverter models including:
    - Modern single-phase hybrid inverters (most common)
    - Legacy single-phase hybrid inverters
    - Three-phase hybrid inverters
    
    Key Features:
    - Modbus TCP and RTU (serial) support
    - Multiple inverter model series support
    - Comprehensive power flow monitoring
    - Energy statistics and daily totals
    - Fault and warning detection
    - Battery management system integration
    - Automatic MPPT detection
    """
    
    @staticmethod
    def _plugin_decode_register(registers: List[int], info: Dict[str, Any], logger_instance: logging.Logger) -> Tuple[Any, Optional[str]]:
        """
        Decodes raw Modbus register values based on data type specification.
        
        Handles various Deye/Sunsynk data types including signed/unsigned integers,
        little-endian 32-bit values, and ASCII strings. Applies scaling and offset
        transformations as specified in the register definition.
        
        Args:
            registers: List of raw 16-bit register values from Modbus
            info: Dictionary containing type, scale, offset, and other metadata
            logger_instance: Logger for error reporting
            
        Returns:
            Tuple of (decoded_value, unit) or (ERROR_DECODE, unit) on failure
        """
        """Decodes register values with error handling and logging."""
        reg_type = info.get("type", "uint16")
        scale = float(info.get("scale", 1.0))
        offset = float(info.get("offset", 0.0))
        unit = info.get("unit")
        value = None
        key_name_for_log = info.get('key', 'N/A_KeyMissingInInfo')
        try:
            if not registers:
                raise ValueError("No registers provided")

            if reg_type == "uint16": value = registers[0]
            elif reg_type == "int16": value = struct.unpack('>h', registers[0].to_bytes(2, 'big'))[0]
            elif reg_type == "uint32_le":
                value = struct.unpack('<I', registers[0].to_bytes(2, 'little') + registers[1].to_bytes(2, 'little'))[0]
            elif reg_type == "string":
                value = b''.join(r.to_bytes(2, 'big') for r in registers[:info.get("len")]).decode('ascii', errors='ignore').strip('\x00')
            else:
                raise ValueError(f"Unsupported type: {reg_type}")

            if isinstance(value, (int, float)):
                value = float(value) * scale + offset
            return value, unit

        except (struct.error, ValueError, IndexError) as e:
            logger_instance.error(f"DeyeSunsynkPlugin: Decode error for '{key_name_for_log}' ({reg_type}) with {registers}: {e}", exc_info=False)
            return ERROR_DECODE, unit

    @staticmethod
    def _plugin_get_register_count(reg_type: str, logger_instance: logging.Logger, reg_len: Optional[int] = None) -> int:
        """
        Determines the number of 16-bit registers required for a given data type.
        
        Args:
            reg_type: Data type string (uint16, int16, uint32_le, string)
            logger_instance: Logger for warnings
            reg_len: Length for string types
            
        Returns:
            Number of registers required for the data type
        """
        """Determines the number of registers a data type occupies."""
        if reg_type == "uint32_le": return 2
        elif reg_type in ["uint16", "int16"]: return 1
        elif reg_type == "string": return reg_len if reg_len else 1
        else:
            logger_instance.warning(f"DeyeSunsynkPlugin: Unknown type '{reg_type}' in get_register_count. Assuming 1.")
            return 1

    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the Deye/Sunsynk inverter plugin.
        
        Sets up connection parameters, selects the appropriate register map based
        on the configured model series, and prepares Modbus read groups for
        efficient data acquisition.
        
        Args:
            instance_name: Unique identifier for this plugin instance
            plugin_specific_config: Configuration dictionary from config.ini
            main_logger: Application logger instance
            app_state: Global application state object
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.last_error_message: Optional[str] = None
        self.last_known_dynamic_data: Dict[str, Any] = {}
        
        try:
            self.connection_type = ConnectionType(self.plugin_config.get("connection_type", "tcp").strip().lower())
        except ValueError:
            self.logger.warning(f"Invalid connection_type '{self.plugin_config.get('connection_type')}', defaulting to TCP.")
            self.connection_type = ConnectionType.TCP

        self.serial_port = self.plugin_config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = int(self.plugin_config.get("baud_rate", 9600))
        self.tcp_host = self.plugin_config.get("tcp_host")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 502))
        self.slave_address = int(self.plugin_config.get("slave_address", 1))
        
        self.modbus_timeout_seconds = int(self.plugin_config.get("modbus_timeout_seconds", 15))
        self.inter_read_delay_ms = int(self.plugin_config.get("inter_read_delay_ms", 100))
        self.max_regs_per_read = int(self.plugin_config.get("modbus_max_registers_per_read", 100))
        self.max_read_retries_per_group = int(self.plugin_config.get("max_read_retries_per_group", 2))
        self._max_waiting_polls = int(self.plugin_config.get("max_consecutive_waiting_polls", 5))
        
        self.model_series = self.plugin_config.get("deye_model_series", "modern_hybrid").lower()
        self.registers_map = DEYE_COMMON_REGISTERS.copy()
        if self.model_series == "modern_hybrid":
            self.registers_map.update(DEYE_MODERN_HYBRID_REGISTERS)
        elif self.model_series == "legacy_hybrid":
            self.registers_map.update(DEYE_LEGACY_HYBRID_REGISTERS)
        elif self.model_series == "three_phase":
            self.registers_map.update(DEYE_THREE_PHASE_REGISTERS)
        else:
            self.logger.warning(f"Unknown 'deye_model_series', defaulting to 'modern_hybrid'.")
            self.registers_map.update(DEYE_MODERN_HYBRID_REGISTERS)
            
        self.static_registers_map = {k: v for k, v in self.registers_map.items() if v.get("static")}
        self.dynamic_registers_map = {k: v for k, v in self.registers_map.items() if not v.get("static")}
        self.dynamic_read_groups = self._build_modbus_read_groups(list(self.dynamic_registers_map.items()))
        self._waiting_status_counter = 0
        self.client = None # Initialized in connect()

        target_info = f"{self.tcp_host}:{self.tcp_port}" if self.connection_type == ConnectionType.TCP else f"{self.serial_port}:{self.baud_rate}"
        self.logger.info(f"Deye/Sunsynk Plugin '{self.instance_name}' initialized. Model: {self.model_series}, Conn: {self.connection_type.value}, Target: {target_info}, SlaveID: {self.slave_address}")

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        """Returns a list of configuration parameters that this plugin supports."""
        return [
            {"name": "connection_type", "type": str, "default": "tcp", "description": "Connection type to use.", "options": ["tcp", "serial"]},
            {"name": "tcp_host", "type": str, "default": "192.168.1.100", "description": "IP Address or Hostname of the inverter's Modbus adapter."},
            {"name": "tcp_port", "type": int, "default": 502, "description": "TCP Port for the Modbus adapter."},
            {"name": "serial_port", "type": str, "default": "/dev/ttyUSB0", "description": "Serial port for Modbus RTU."},
            {"name": "baud_rate", "type": int, "default": 9600, "description": "Baud rate for serial connection."},
            {"name": "slave_address", "type": int, "default": 1, "description": "Modbus slave address (unit ID)."},
            {"name": "deye_model_series", "type": str, "default": "modern_hybrid", "description": "The Deye/Sunsynk model series for the correct register map.", "options": ["modern_hybrid", "legacy_hybrid", "three_phase", "deye_hybrid_yaml", "deye_2mppt", "deye_4mppt"]},
            {"name": "modbus_timeout_seconds", "type": int, "default": 15, "description": "Modbus connection and read timeout in seconds."},
            {"name": "inter_read_delay_ms", "type": int, "default": 100, "description": "Delay in milliseconds between Modbus reads."},
            {"name": "modbus_max_registers_per_read", "type": int, "default": 100, "description": "Max number of registers to read in a single request."},
            {"name": "modbus_max_register_gap", "type": int, "default": 10, "description": "Max gap between register addresses before creating a new read group."},
            {"name": "max_read_retries_per_group", "type": int, "default": 2, "description": "Number of retries for a failed Modbus read group."},
            {"name": "max_consecutive_waiting_polls", "type": int, "default": 5, "description": "Max consecutive polls to tolerate 'Waiting' status before reconnecting."},
        ]

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "deye_sunsynk"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        model_map = {
            "modern_hybrid": "Deye/Sunsynk Hybrid",
            "legacy_hybrid": "Deye Legacy Hybrid",
            "three_phase": "Deye 3-Phase Hybrid"
        }
        model_name = model_map.get(self.model_series, "Deye/Sunsynk Inverter")
        return f"{model_name} ({self.connection_type.value.upper()})"

    def connect(self) -> bool:
        """
        Establishes connection to the Deye/Sunsynk inverter.
        
        For TCP connections, performs pre-connection network checks including
        port availability and ICMP ping tests. Handles both TCP and serial
        connection types with comprehensive error handling.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._is_connected_flag and self.client: return True
        if self.client: self.disconnect()
        self.last_error_message = None

        if self.connection_type == ConnectionType.TCP:
            self.logger.info(f"DeyePlugin '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
            port_open, _, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open:
                self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} is not open. Error: {err_msg}"
                self.logger.error(self.last_error_message)
                icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                if not icmp_ok: self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host is likely down or blocked.")
                return False

        self.logger.info(f"DeyePlugin '{self.instance_name}': Attempting to connect via {self.connection_type.value}...")
        try:
            if self.connection_type == ConnectionType.SERIAL:
                self.client = ModbusSerialClient(port=self.serial_port, baudrate=self.baud_rate, timeout=self.modbus_timeout_seconds)
            else: # TCP
                self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=self.modbus_timeout_seconds)
            
            if self.client.connect():
                self._is_connected_flag = True
                self.logger.info(f"DeyePlugin '{self.instance_name}': Successfully connected.")
                return True
            else:
                self.last_error_message = "Pymodbus client.connect() returned False."
        except Exception as e:
            self.last_error_message = f"Connection exception: {e}"
            self.logger.error(f"DeyePlugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
        
        if self.client: self.client.close()
        self.client = None
        self._is_connected_flag = False
        return False

    def disconnect(self) -> None:
        """
        Closes the Modbus connection and resets the client.
        
        Safely terminates the connection to the inverter and cleans up
        the client object to prepare for reconnection attempts.
        """
        if self.client:
            self.logger.info(f"DeyePlugin '{self.instance_name}': Disconnecting client.")
            try:
                self.client.close()
            except Exception as e:
                self.logger.error(f"Error closing Modbus connection: {e}", exc_info=True)
        self._is_connected_flag = False
        self.client = None

    def _is_client_connected(self) -> bool:
        """
        Checks if the Modbus client is currently connected.
        
        Uses connection-type specific methods to verify the client state,
        handling differences between TCP socket and serial port connections.
        
        Returns:
            True if client is connected and ready for communication
        """
        if not self.client: return False
        if self.connection_type == ConnectionType.TCP:
            return self.client.is_socket_open()
        else: # Serial
            return self.client.is_open

    def _build_modbus_read_groups(self, register_list: List[Tuple[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Groups registers into efficient Modbus read operations.
        
        Analyzes register addresses and creates contiguous read groups to minimize
        the number of Modbus transactions. Respects maximum register count and
        gap limits to optimize communication efficiency.
        
        Args:
            register_list: List of (key, register_info) tuples to group
            
        Returns:
            List of read group dictionaries with start address, count, and keys
        """
        """Groups registers into contiguous blocks with configurable max gap and read size."""
        groups: List[Dict[str, Any]] = []
        if not register_list: return groups
        
        sorted_regs = sorted(register_list, key=lambda item: item[1]['addr'])
        current_group: Optional[Dict[str, Any]] = None
        max_gap = int(self.plugin_config.get("modbus_max_register_gap", 10))
        
        for key, info in sorted_regs:
            addr = info['addr']
            count = self._plugin_get_register_count(info.get("type", "uint16"), self.logger, info.get("len"))
            
            is_new_group = (
                current_group is None or
                addr >= current_group['start'] + current_group['count'] + max_gap or
                (addr + count - current_group['start'] > self.max_regs_per_read)
            )
            
            if is_new_group:
                if current_group: groups.append(current_group)
                current_group = {"start": addr, "count": count, "keys": [key]}
            else:
                current_group['count'] = (addr + count) - current_group['start']
                current_group['keys'].append(key)
                
        if current_group: groups.append(current_group)
        return groups

    def _read_registers_from_groups(self, groups: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Executes Modbus read operations for all register groups.
        
        Performs the actual Modbus communication with comprehensive error handling,
        retry logic, and data validation. Decodes raw register values according
        to their type specifications and handles communication failures gracefully.
        
        Args:
            groups: List of register groups to read
            
        Returns:
            Dictionary of decoded register values or None on failure
        """
        """Reads Modbus registers, handles retries and decoding with refined error handling."""
        decoded_data = {}
        if not self.is_connected:
            self.logger.error(f"DeyePlugin '{self.instance_name}': Not connected. Aborting read.")
            return None

        for group_index, group in enumerate(groups):
            retries = 0
            success_this_group = False
            while retries <= self.max_read_retries_per_group and not success_this_group:
                try:
                    if not self.client or not self._is_client_connected():
                        raise ModbusIOException("Client invalid or disconnected before retry")

                    read_result = self.client.read_holding_registers(address=group["start"], count=group["count"], slave=self.slave_address)

                    if isinstance(read_result, ExceptionResponse):
                        exc_msg = MODBUS_EXCEPTION_CODES.get(read_result.exception_code, f'Unknown Modbus Exc ({read_result.exception_code})')
                        raise ModbusException(f"Slave Exc Code {read_result.exception_code}: {exc_msg}")
                    if read_result.isError():
                        raise ModbusIOException("Pymodbus reported general error")
                    if not hasattr(read_result, "registers") or read_result.registers is None or len(read_result.registers) < group['count']:
                        raise ModbusIOException(f"Short response (Got {len(read_result.registers) if hasattr(read_result, 'registers') and read_result.registers is not None else 'None'}, Exp {group['count']})")

                    regs = read_result.registers
                    for key in group["keys"]:
                        info = self.registers_map.get(key)
                        if not info: continue
                        start_idx = info["addr"] - group["start"]
                        num_regs = self._plugin_get_register_count(info.get("type", "uint16"), self.logger, info.get("len"))
                        if not (0 <= start_idx and start_idx + num_regs <= len(regs)):
                            self.logger.warning(f"DeyePlugin: Not enough registers for key '{key}' in group @{group['start']}. Skipping.")
                            continue
                        value, _ = self._plugin_decode_register(regs[start_idx : start_idx + num_regs], info, self.logger)
                        decoded_data[key] = value
                    success_this_group = True

                except (ModbusException, ModbusIOException, ModbusConnectionException, OSError, struct.error) as e_comm:
                    retries += 1
                    self.logger.warning(f"DeyePlugin '{self.instance_name}': Comm error group @{group['start']} (Try {retries}/{self.max_read_retries_per_group}): {type(e_comm).__name__} - {e_comm}")
                    if retries > self.max_read_retries_per_group:
                        self.logger.error(f"DeyePlugin '{self.instance_name}': Max retries for group @{group['start']}. Forcing disconnect and aborting poll cycle.")
                        self.disconnect()
                        return None
                    time.sleep(0.5)
                except Exception as e_unexpected:
                    self.logger.error(f"DeyePlugin '{self.instance_name}': Unexpected error in group @{group['start']}: {e_unexpected}", exc_info=True)
                    self.disconnect()
                    return None

            if self.is_connected and self.inter_read_delay_ms > 0 and group_index < len(groups) - 1:
                time.sleep(self.inter_read_delay_ms / 1000.0)
        return decoded_data

    def _detect_mppts_heuristically(self, mppt_voltage_data: Dict[str, Any]) -> int:
        """
        Automatically detects the number of active MPPT inputs.
        
        Analyzes PV voltage readings to determine how many MPPT inputs
        are actually connected and active. Uses voltage thresholds to
        distinguish between connected and unused inputs.
        
        Args:
            mppt_voltage_data: Dictionary containing PV voltage readings
            
        Returns:
            Number of detected active MPPT inputs
        """
        """Determines the number of active MPPTs based on reported voltages."""
        MIN_VOLTAGE_THRESHOLD = float(self.plugin_config.get("mppt_detection_min_voltage", 30.0))
        mppt_keys = ["pv1_voltage", "pv2_voltage", "pv3_voltage", "pv4_voltage"] # Deye might have up to 4
        
        active_mppts = [i + 1 for i, key in enumerate(mppt_keys) if isinstance(v := mppt_voltage_data.get(key), (int, float)) and v > MIN_VOLTAGE_THRESHOLD]
        
        if not active_mppts:
            # Fallback for three-phase models which often have at least 2
            return 2 if self.model_series == "three_phase" else 1
        
        return max(active_mppts)

    def read_static_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads static device identification and configuration data.
        
        Retrieves manufacturer information, model details, serial number,
        and automatically detects the number of MPPT inputs and AC phases
        based on the configured model series and live voltage readings.
        
        Returns:
            Dictionary of standardized static device information
        """
        """Reads static device information from the inverter."""
        self.logger.info(f"DeyePlugin '{self.instance_name}': Reading static data...")
        if not self.is_connected:
            self.logger.error(f"DeyePlugin '{self.instance_name}': Cannot read static data, not connected.")
            return None
        
        static_read_groups = self._build_modbus_read_groups(list(self.static_registers_map.items()))
        raw_static_data = self._read_registers_from_groups(static_read_groups)
        if not raw_static_data:
            self.logger.error(f"DeyePlugin '{self.instance_name}': Failed to read static data from device.")
            return None

        model_name = f"Deye/Sunsynk ({self.model_series.replace('_', ' ').title()})"
        num_phases = 3 if self.model_series == "three_phase" else 1
        
        # Heuristically detect MPPTs by reading PV voltages
        mppt_volt_keys = [k for k, v in self.dynamic_registers_map.items() if "voltage" in k and "pv" in k]
        mppt_items = [(k, v) for k, v in self.dynamic_registers_map.items() if k in mppt_volt_keys]
        num_mppts = 2 # Default
        if mppt_items:
            mppt_groups = self._build_modbus_read_groups(mppt_items)
            if mppt_groups and (mppt_data := self._read_registers_from_groups(mppt_groups)):
                num_mppts = self._detect_mppts_heuristically(mppt_data)

        serial_number = raw_static_data.get('device_serial', UNKNOWN)
        if serial_number in [ERROR_DECODE, ERROR_READ]:
            serial_number = f"Error_{self.instance_name}"

        return {
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
            StandardDataKeys.STATIC_INVERTER_MANUFACTURER: "Deye/Sunsynk",
            StandardDataKeys.STATIC_INVERTER_MODEL_NAME: model_name,
            StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: serial_number,
            StandardDataKeys.STATIC_NUMBER_OF_MPPTS: num_mppts,
            StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: num_phases,
        }

    def _is_data_sane(self, raw_data: Dict[str, Any]) -> bool:
        """
        Performs sanity checks on decoded inverter data.
        
        Validates that critical values like battery SOC are within reasonable
        ranges to detect communication errors or device malfunctions that
        could corrupt the monitoring system.
        
        Args:
            raw_data: Dictionary of decoded register values
            
        Returns:
            True if data passes sanity checks, False otherwise
        """
        """Performs a sanity check on critical decoded values."""
        soc = raw_data.get("battery_soc")
        if not isinstance(soc, (int, float)) or not (0 <= soc <= 105):
            self.logger.warning(f"DeyePlugin: Sanity check FAILED. Unreasonable SOC: {soc}%.")
            return False
        # Add other checks for voltage, power, etc. as needed
        return True

    def _decode_deye_alerts(self, raw_data: Dict[str, Any]) -> Tuple[List[int], Dict[str, List[str]]]:
        """
        Decodes fault and warning registers into human-readable alerts.
        
        Processes the inverter's fault and warning bitfield registers to extract
        active alerts and categorize them by severity. Maps numeric codes to
        descriptive messages for user-friendly error reporting.
        
        Args:
            raw_data: Dictionary containing fault and warning register values
            
        Returns:
            Tuple of (active_fault_codes, categorized_alerts_dict)
        """
        """Decodes raw fault and warning register values into categorized alert messages."""
        active_alert_codes = []
        categorized_alerts = {"fault": [], "warning": []}

        # Process fault codes (assuming 4 registers for faults)
        for i in range(1, 5):
            fault_val = raw_data.get(f"fault_code_{i}")
            if isinstance(fault_val, int) and fault_val != 0:
                for bit in range(16):
                    if (fault_val >> bit) & 1:
                        code = (i - 1) * 16 + bit
                        if code in DEYE_FAULT_CODES:
                            active_alert_codes.append(code)
                            categorized_alerts["fault"].append(DEYE_FAULT_CODES[code])

        # Process warning codes (assuming 2 registers for warnings)
        for i in range(1, 3):
            warn_val = raw_data.get(f"warning_code_{i}")
            if isinstance(warn_val, int) and warn_val != 0:
                for bit in range(16):
                    if (warn_val >> bit) & 1:
                        code = (i - 1) * 16 + bit
                        if code in DEYE_WARNING_CODES:
                            # Warnings can also be added to the main list if needed
                            categorized_alerts["warning"].append(DEYE_WARNING_CODES[code])
                            
        return active_alert_codes, categorized_alerts

    def _standardize_operational_data(self, status_txt: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts raw inverter data into standardized application format.
        
        Transforms model-specific register values into the common StandardDataKeys
        format used throughout the application. Handles power calculations,
        energy totals, status determination, and unit conversions.
        
        Args:
            status_txt: Decoded inverter status text
            raw_data: Dictionary of raw decoded register values
            
        Returns:
            Dictionary using StandardDataKeys with calculated and formatted values
        """
        """Converts raw dynamic data from the inverter into the application's standard format."""
        
        def to_float_or_zero(value: Any) -> float:
            if value is None or value in [ERROR_DECODE, ERROR_READ]: return 0.0
            try: return float(value)
            except (ValueError, TypeError): return 0.0

        # Decode alerts first
        active_faults, categorized_alerts = self._decode_deye_alerts(raw_data)

        # --- Power Calculations ---
        if 'battery_charge_power' in raw_data: # For three-phase models
            battery_power = to_float_or_zero(raw_data.get("battery_discharge_power")) - to_float_or_zero(raw_data.get("battery_charge_power"))
        else: # For single-phase models, Deye is + for charge, - for discharge. We want the opposite.
            battery_power = to_float_or_zero(raw_data.get("battery_power")) * -1

        grid_power = to_float_or_zero(raw_data.get("grid_power"))
        inverter_power = to_float_or_zero(raw_data.get("inverter_power"))
        load_power = to_float_or_zero(raw_data.get("load_power"))
        if load_power == 0: load_power = inverter_power + grid_power # Fallback calculation

        pv1_power = to_float_or_zero(raw_data.get("pv1_power"))
        if pv1_power == 0: pv1_power = to_float_or_zero(raw_data.get("pv1_voltage")) * to_float_or_zero(raw_data.get("pv1_current"))
        pv2_power = to_float_or_zero(raw_data.get("pv2_power"))
        if pv2_power == 0: pv2_power = to_float_or_zero(raw_data.get("pv2_voltage")) * to_float_or_zero(raw_data.get("pv2_current"))
        pv_power = pv1_power + pv2_power

        batt_status = "Idle"
        if battery_power > 10: batt_status = "Discharging"
        elif battery_power < -10: batt_status = "Charging"

        # --- Energy Calculations ---
        pv_yield = to_float_or_zero(raw_data.get("day_energy"))
        batt_chg = to_float_or_zero(raw_data.get("battery_daily_charge"))
        batt_disch = to_float_or_zero(raw_data.get("battery_daily_discharge"))
        grid_buy = to_float_or_zero(raw_data.get("grid_daily_buy"))
        grid_sell = to_float_or_zero(raw_data.get("grid_daily_sell"))
        
        load_energy = to_float_or_zero(raw_data.get("load_daily_buy"))
        if load_energy == 0: # Fallback calculation
            load_energy = max(0, (pv_yield + batt_disch + grid_buy) - (batt_chg + grid_sell))

        bms_code = raw_data.get("bms_protocol_code")
        bms_model = BMS_PROTOCOL_CODES.get(bms_code, f"Code {bms_code}") if isinstance(bms_code, int) else UNKNOWN

        standardized_data = {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: status_txt,
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status,
            StandardDataKeys.STATIC_BATTERY_MODEL_NAME: bms_model,
            StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: to_float_or_zero(raw_data.get("battery_soh")),
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: round(pv_power, 2),
            StandardDataKeys.AC_POWER_WATTS: inverter_power,
            StandardDataKeys.BATTERY_POWER_WATTS: battery_power,
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: grid_power,
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: load_power,
            StandardDataKeys.ENERGY_PV_DAILY_KWH: pv_yield,
            StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: batt_chg,
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: batt_disch,
            StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: grid_buy,
            StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH: grid_sell,
            StandardDataKeys.ENERGY_LOAD_DAILY_KWH: round(load_energy, 2),
            StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: to_float_or_zero(raw_data.get("total_energy")),
            StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: raw_data.get("pv1_voltage"),
            StandardDataKeys.PV_MPPT1_CURRENT_AMPS: raw_data.get("pv1_current"),
            StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: raw_data.get("pv2_voltage"),
            StandardDataKeys.PV_MPPT2_CURRENT_AMPS: raw_data.get("pv2_current"),
            StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: raw_data.get("inverter_voltage"),
            StandardDataKeys.GRID_L1_CURRENT_AMPS: raw_data.get("inverter_current"),
            StandardDataKeys.GRID_FREQUENCY_HZ: raw_data.get("grid_frequency"),
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: raw_data.get("radiator_temp"),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: raw_data.get("battery_soc"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: raw_data.get("battery_voltage"),
            StandardDataKeys.BATTERY_CURRENT_AMPS: raw_data.get("battery_current"),
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: raw_data.get("battery_temperature"),
            "generator_power_watts": to_float_or_zero(raw_data.get("generator_power")),
            StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_CODES_LIST: active_faults,
            StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT: categorized_alerts,
        }
        return standardized_data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads and processes all dynamic inverter data.
        
        Orchestrates the complete data acquisition process including:
        - Reading all dynamic register groups
        - Decoding inverter status
        - Handling special states like 'Waiting'
        - Performing data sanity checks
        - Standardizing data format
        
        Returns:
            Dictionary of standardized dynamic data or None on failure
        """
        """Reads and processes dynamic (periodically changing) data from the inverter."""
        self.logger.debug(f"DeyePlugin '{self.instance_name}': Reading dynamic data...")
        if not self.is_connected:
            self.logger.error(f"DeyePlugin '{self.instance_name}': Cannot read, not connected.")
            return None

        raw_data = self._read_registers_from_groups(self.dynamic_read_groups)
        if raw_data is None:
            self.logger.warning(f"DeyePlugin '{self.instance_name}': Failed to read dynamic data block.")
            return None

        status_code = raw_data.get("inverter_status_code")
        if not isinstance(status_code, int):
            self.logger.error(f"DeyePlugin '{self.instance_name}': Failed to decode status (got: '{status_code}'). Forcing disconnect.")
            self.disconnect()
            return None
            
        status_txt = STATUS_CODES.get(status_code, f"Unknown ({status_code})")

        if status_txt == "Waiting":
            return self._handle_waiting_status(status_txt)

        if not self._is_data_sane(raw_data):
            self.last_error_message = "Data failed sanity check."
            self.disconnect() # Force disconnect on bad data
            return None

        self._waiting_status_counter = 0
        standardized_data = self._standardize_operational_data(status_txt, raw_data)
        self.last_known_dynamic_data = standardized_data.copy()
        return standardized_data

    def _handle_waiting_status(self, status_txt: str) -> Optional[Dict[str, Any]]:
        """
        Handles the inverter 'Waiting' status with intelligent recovery.
        
        When the inverter reports 'Waiting' status (typically at night or during
        startup), this method tracks consecutive occurrences and forces a
        reconnection if the inverter appears stuck in this state.
        
        Args:
            status_txt: The 'Waiting' status text
            
        Returns:
            Updated data with current status or None to trigger reconnection
        """
        """Handles the 'Waiting' status, preserving last known data or forcing a reconnect."""
        self._waiting_status_counter += 1
        self.logger.info(f"DeyePlugin '{self.instance_name}': Inverter status is 'Waiting'. Count: {self._waiting_status_counter}/{self._max_waiting_polls}.")
        
        if self._waiting_status_counter >= self._max_waiting_polls:
            self.logger.warning(f"DeyePlugin '{self.instance_name}': Inverter stuck in 'Waiting' state for {self._max_waiting_polls} polls. Forcing reconnect.")
            self.disconnect()
            self._waiting_status_counter = 0
            return None

        # Preserve last known data, but update the status
        updated_data = self.last_known_dynamic_data.copy()
        updated_data[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT] = status_txt
        return updated_data
