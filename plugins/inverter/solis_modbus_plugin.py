# plugins/inverter/solis_modbus_plugin.py
import time
import struct
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from core.app_state import AppState

# Import constants from the new file
from .solis_modbus_plugin_constants import (
    SOLIS_REGISTERS,
    SOLIS_INVERTER_STATUS_CODES,
    SOLIS_FAULT_BITFIELD_MAPS,
    ALERT_CATEGORIES,
    SOLIS_INVERTER_MODEL_CODES,
    BATTERY_MODEL_CODES,
    MODBUS_EXCEPTION_CODES
)

from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port, check_icmp_ping
from utils.helpers import FULLY_OPERATIONAL_STATUSES

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException, ConnectionException as ModbusConnectionException
from pymodbus.pdu import ExceptionResponse

ERROR_READ = "read_error"
ERROR_DECODE = "decode_error"
UNKNOWN = "Unknown"

class ConnectionType(str, Enum):
    """Enumeration for the supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"


class SolisModbusPlugin(DevicePlugin):
    """
    A plugin to interact with Solis inverters via Modbus TCP or Serial.

    This class implements the DevicePlugin interface to provide a standardized
    way of connecting to, reading data from, and interpreting data from Solis
    inverters. It handles Modbus communication, register decoding, data
    standardization, and error handling.

    It features dynamic parameter adjustment for TCP connections to optimize
    communication reliability based on network latency.
    """
    @staticmethod
    def _plugin_decode_register(registers: List[int], info: Dict[str, Any], logger_instance: logging.Logger) -> Tuple[Any, Optional[str]]:
        """
        Decodes raw register values into a scaled and typed Python object.

        Args:
            registers: A list of integers representing the raw Modbus register values.
            info: The dictionary of register information from SOLIS_REGISTERS.
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
            if not registers: raise ValueError("No registers provided")
            if reg_type == "uint16": value = registers[0]
            elif reg_type == "int16": value = struct.unpack('>h', registers[0].to_bytes(2, 'big'))[0]
            elif reg_type == "uint32": value = struct.unpack('>I', b''.join(r.to_bytes(2, 'big') for r in registers[:2]))[0]
            elif reg_type == "int32": value = struct.unpack('>i', b''.join(r.to_bytes(2, 'big') for r in registers[:2]))[0]
            elif reg_type == "string_read8":
                byte_data = b''.join(reg.to_bytes(2, 'big') for reg in registers[:8])
                value = byte_data.rstrip(b'\x00 \t\r\n').decode('ascii', errors='ignore')
            elif reg_type in ["Code", "Bitfield", "Hex"]: value = registers[0]
            else: raise ValueError(f"Unsupported type: {reg_type}")

            if isinstance(value, (int, float)):
                should_scale = (abs(scale - 1.0) > 1e-9) and (unit not in ["Bitfield", "Code", "Hex"])
                final_value = float(value) * scale if should_scale else value
                return final_value, unit
            else: return value, unit
        except (struct.error, ValueError, IndexError, TypeError) as e:
            logger_instance.error(f"SolisPlugin: Decode Error for '{key_name_for_log}' ({reg_type}) with {registers}: {e}", exc_info=False)
            return ERROR_DECODE, unit

    @staticmethod
    def _plugin_get_register_count(reg_type: str, logger_instance: logging.Logger) -> int:
        """
        Determines the number of 16-bit registers a given data type occupies.

        Args:
            reg_type: The data type string (e.g., "uint32", "string_read8").
            logger_instance: The logger to use for reporting warnings.

        Returns:
            The number of registers required for the data type.
        """
        if reg_type in ["uint32", "int32"]: return 2
        if reg_type in ["uint16", "int16", "Code", "Bitfield", "Hex"]: return 1
        if reg_type == "string_read8": return 8
        logger_instance.warning(f"SolisPlugin: Unknown type '{reg_type}' in get_register_count. Assuming 1.")
        return 1

    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the SolisModbusPlugin instance.

        Args:
            instance_name: A unique name for this plugin instance.
            plugin_specific_config: A dictionary of configuration parameters.
            main_logger: The main application logger.
            app_state: The global application state object, if available.
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        self.last_error_message: Optional[str] = None
        self.last_known_dynamic_data: Dict[str, Any] = {}
        
        try:
            self.connection_type = ConnectionType(self.plugin_config.get("connection_type", "tcp").strip().lower())
        except ValueError:
            self.logger.warning(f"Invalid connection_type '{self.plugin_config.get('connection_type')}' specified. Defaulting to TCP.")
            self.connection_type = ConnectionType.TCP

        self.serial_port = self.plugin_config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = int(self.plugin_config.get("baud_rate", 9600))
        self.tcp_host = self.plugin_config.get("tcp_host", "127.0.0.1")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 502))
        self.slave_address = int(self.plugin_config.get("slave_address", 1))
        
        DEFAULT_MODBUS_TIMEOUT_S = 15
        DEFAULT_INTER_READ_DELAY_MS = 750
        DEFAULT_MAX_REGS_PER_READ = 60
        self._orig_modbus_timeout_seconds = int(self.plugin_config.get("modbus_timeout_seconds", DEFAULT_MODBUS_TIMEOUT_S))
        self.modbus_timeout_seconds = self._orig_modbus_timeout_seconds
        self._orig_inter_read_delay_ms = int(self.plugin_config.get("inter_read_delay_ms", DEFAULT_INTER_READ_DELAY_MS))
        self.inter_read_delay_ms = self._orig_inter_read_delay_ms
        self._orig_max_regs_per_read = int(self.plugin_config.get("max_regs_per_read", DEFAULT_MAX_REGS_PER_READ))
        self.max_regs_per_read = self._orig_max_regs_per_read
        self.max_read_retries_per_group = int(self.plugin_config.get("max_read_retries_per_group", 2))
        self.startup_grace_period_seconds = int(self.plugin_config.get("startup_grace_period_seconds", 120))
        self._user_set_params = {
            "modbus_timeout_seconds": "modbus_timeout_seconds" in self.plugin_config,
            "inter_read_delay_ms": "inter_read_delay_ms" in self.plugin_config,
            "max_regs_per_read": "max_regs_per_read" in self.plugin_config,
        }
        self.measured_rtt_ms: Optional[float] = None
        self.static_registers_map = {k: v for k, v in SOLIS_REGISTERS.items() if v.get("static") and 'addr' in v}
        self.dynamic_registers_map = {k: v for k, v in SOLIS_REGISTERS.items() if not v.get("static") and 'addr' in v}
        self.dynamic_read_groups = self._build_modbus_read_groups(list(self.dynamic_registers_map.items()), self.max_regs_per_read)
        self._waiting_status_counter = 0
        self.plugin_init_time = time.monotonic()
        target_info = f"{self.tcp_host}:{self.tcp_port}" if self.connection_type == ConnectionType.TCP else f"{self.serial_port}:{self.baud_rate}"
        self.logger.info(f"Solis Plugin '{self.instance_name}': Initialized. Conn: {self.connection_type.value}, Target: {target_info}, SlaveID: {self.slave_address}.")

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "solis_modbus"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "Solis Modbus Inverter"

    def auto_adjust_params(self, measured_rtt_ms: float):
        """
        Dynamically adjusts Modbus communication parameters based on network latency.

        This method is called for TCP connections after a successful port check.
        It modifies the inter-read delay, max registers per read, and timeout
        to improve reliability on high-latency or unstable networks. These
        adjustments are only made if the user has not explicitly set the
        corresponding parameters in the configuration.

        Args:
            measured_rtt_ms: The measured round-trip time to the device in
                             milliseconds.
        """
        if self.connection_type != ConnectionType.TCP: return
        self.measured_rtt_ms = measured_rtt_ms
        self.logger.info(f"SolisPlugin '{self.instance_name}': Auto-adjusting params based on RTT: {measured_rtt_ms:.2f} ms")
        original_params_log = f"(Originals: Timeout={self._orig_modbus_timeout_seconds}s, Delay={self._orig_inter_read_delay_ms}ms, MaxRegs={self._orig_max_regs_per_read})"
        
        if not self._user_set_params["inter_read_delay_ms"]:
            self.inter_read_delay_ms = min(1000, max(100, int(measured_rtt_ms * 1.2) + 50))
        
        prev_max_regs = self.max_regs_per_read
        if not self._user_set_params["max_regs_per_read"]:
            if measured_rtt_ms > 200: self.max_regs_per_read = 30
            elif measured_rtt_ms > 80: self.max_regs_per_read = 45
            else: self.max_regs_per_read = self._orig_max_regs_per_read
            if prev_max_regs != self.max_regs_per_read:
                self.dynamic_read_groups = self._build_modbus_read_groups(list(self.dynamic_registers_map.items()), self.max_regs_per_read)
                self.logger.info(f"SolisPlugin '{self.instance_name}': Rebuilt dynamic_read_groups with new max_regs_per_read={self.max_regs_per_read}")
        
        if not self._user_set_params["modbus_timeout_seconds"]:
            self.modbus_timeout_seconds = max(5, int(self.inter_read_delay_ms * 2 / 1000) + 2)

        self.logger.info(f"SolisPlugin '{self.instance_name}': Final auto-adjusted params: Timeout={self.modbus_timeout_seconds}s, Delay={self.inter_read_delay_ms}ms, MaxRegs={self.max_regs_per_read}. {original_params_log}")

    def connect(self) -> bool:
        """
        Establishes a connection to the Solis inverter.

        For TCP connections, it performs a pre-connection check and may
        auto-adjust communication parameters. It then creates and connects
        the appropriate Pymodbus client.

        Returns:
            True if the connection was successful, False otherwise.
        """
        if self._is_connected_flag and self.client: return True
        if self.client: self.disconnect()
        self.last_error_message = None

        if self.connection_type == ConnectionType.TCP:
            self.logger.info(f"SolisPlugin '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
            port_open, rtt_ms, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open:
                self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} is not open. Error: {err_msg}"
                self.logger.error(self.last_error_message)
                icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                if not icmp_ok: self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host is likely down or blocked.")
                return False
            self.auto_adjust_params(rtt_ms)

        self.logger.info(f"SolisPlugin '{self.instance_name}': Attempting to connect via {self.connection_type.value}...")
        try:
            if self.connection_type == ConnectionType.SERIAL:
                self.client = ModbusSerialClient(port=self.serial_port, baudrate=self.baud_rate, timeout=self.modbus_timeout_seconds)
            else: # TCP
                self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=self.modbus_timeout_seconds)
            
            if self.client.connect():
                self._is_connected_flag = True
                self.logger.info(f"SolisPlugin '{self.instance_name}': Successfully connected.")
                return True
            else:
                self.last_error_message = "Pymodbus client.connect() returned False."
        except Exception as e:
            self.last_error_message = f"Connection exception: {e}"
            self.logger.error(f"SolisPlugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
        
        if self.client: self.client.close()
        self.client = None
        self._is_connected_flag = False
        return False

    def disconnect(self) -> None:
        """Closes the Modbus connection and resets the client."""
        if self.client:
            self.logger.info(f"SolisPlugin '{self.instance_name}': Disconnecting client.")
            try:
                self.client.close()
            except Exception as e:
                self.logger.error(f"Error closing Modbus connection: {e}", exc_info=True)
        self._is_connected_flag = False
        self.client = None

    def _decode_solis_alerts(self, raw_bitfield_values: Dict[int, int]) -> Tuple[List[int], Dict[str, List[str]]]:
        """
        Decodes raw bitfield register values into categorized alert messages.

        Args:
            raw_bitfield_values: A dictionary where keys are register addresses
                                 and values are the integer values read from them.

        Returns:
            A tuple containing:
            - A list of unique numeric codes for active alerts.
            - A dictionary of categorized alert messages (e.g., {"grid": ["Grid Overvoltage"]}).
        """
        active_alert_codes_numeric: List[int] = []
        categorized_alert_details: Dict[str, List[str]] = {cat: [] for cat in ALERT_CATEGORIES}
        
        for reg_addr, reg_val in raw_bitfield_values.items():
            map_info = SOLIS_FAULT_BITFIELD_MAPS.get(reg_addr)
            if not map_info or not isinstance(reg_val, int): continue
            
            bit_map: Dict[int, str] = map_info.get("bits", {})
            category: str = map_info.get("category", "unknown_alert_category")
            if category not in categorized_alert_details:
                categorized_alert_details[category] = []

            for bit_pos in range(16):
                if (reg_val >> bit_pos) & 1:
                    numeric_code = (reg_addr << 16) | bit_pos 
                    active_alert_codes_numeric.append(numeric_code)
                    alert_detail = bit_map.get(bit_pos, f"Unknown {category.capitalize()} Bit {bit_pos} (Reg {reg_addr})")
                    categorized_alert_details[category].append(alert_detail)
        
        return active_alert_codes_numeric, categorized_alert_details

    def _read_registers_from_groups(self, groups: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Reads multiple groups of Modbus registers, handles retries, and decodes them.

        This is the core communication method. It iterates through register groups,
        dynamically selects the correct Pymodbus read function (e.g.,
        `read_input_registers`), performs the read with retries, and decodes
        the raw values.

        Args:
            groups: A list of register groups to read, created by `_build_modbus_read_groups`.

        Returns:
            A dictionary of the decoded data, or None if a non-recoverable error occurs.
        """
        decoded_data: Dict[str, Any] = {}
        raw_bitfield_registers_this_read: Dict[int, int] = {}
        if not groups:
            decoded_data["_active_fault_codes_list_internal"] = []
            decoded_data["_categorized_alerts_internal"] = {cat: [] for cat in ALERT_CATEGORIES}
            return decoded_data

        for group_index, group in enumerate(groups):
            if not self.is_connected:
                self.logger.error(f"SolisPlugin '{self.instance_name}': Not connected. Aborting read for group @{group['start']}.")
                return None # Fail the entire read operation immediately.

            retries = 0
            success_this_group = False
            while retries <= self.max_read_retries_per_group and not success_this_group:
                try:
                    if not self.client or not self.is_connected: raise ModbusIOException("Client invalid or disconnected before retry")
                    
                    # Dynamically select the read function based on the group type
                    reg_func_type = group.get('reg_func_type', 'input')
                    read_func_attr = 'read_holding_registers' if reg_func_type == 'holding' else 'read_input_registers'
                    read_func = getattr(self.client, read_func_attr)

                    result = read_func(address=group["start"], count=group["count"], slave=self.slave_address)
                    
                    if isinstance(result, ExceptionResponse):
                        exc_msg = MODBUS_EXCEPTION_CODES.get(result.exception_code, f'Unknown Modbus Exc ({result.exception_code})')
                        raise ModbusException(f"Slave Exc Code {result.exception_code}: {exc_msg}")
                    if result.isError(): raise ModbusIOException("Pymodbus reported general error")
                    if not hasattr(result, "registers") or result.registers is None or len(result.registers) < group['count']:
                        raise ModbusIOException(f"Short response (Got {len(result.registers) if result.registers else 'None'}, Exp {group['count']})")
                    
                    regs = result.registers
                    for key in group["keys"]:
                        info = SOLIS_REGISTERS.get(key)
                        if not info: continue
                        start_idx = info["addr"] - group["start"]
                        num_regs = self._plugin_get_register_count(info["type"], self.logger)
                        if not (0 <= start_idx and start_idx + num_regs <= len(regs)): continue
                        value, _ = self._plugin_decode_register(regs[start_idx : start_idx + num_regs], info, self.logger)
                        decoded_data[key] = value
                        if info.get("unit") == "Bitfield" and isinstance(value, int) and value != ERROR_DECODE:
                            raw_bitfield_registers_this_read[info["addr"]] = value
                    success_this_group = True

                except (ModbusException, ModbusIOException, ModbusConnectionException, OSError, AttributeError, struct.error) as e_comm:
                    retries += 1
                    self.logger.warning(f"SolisPlugin '{self.instance_name}': Comm error group @{group['start']} (Try {retries}/{self.max_read_retries_per_group}): {type(e_comm).__name__} - {e_comm}")
                    if retries > self.max_read_retries_per_group:
                        self.logger.error(f"SolisPlugin '{self.instance_name}': Max retries for group @{group['start']}. Forcing disconnect and aborting poll cycle.")
                        self.disconnect()
                        return None
                    time.sleep(0.5)
                except Exception as e_unexpected:
                    self.logger.error(f"SolisPlugin '{self.instance_name}': Unexpected error in group @{group['start']}: {e_unexpected}", exc_info=True)
                    self.disconnect()
                    return None

            if self.inter_read_delay_ms > 0 and group_index < len(groups) - 1:
                time.sleep(self.inter_read_delay_ms / 1000.0)

        numeric_codes, categorized_details = self._decode_solis_alerts(raw_bitfield_registers_this_read)
        decoded_data["_active_fault_codes_list_internal"] = numeric_codes
        decoded_data["_categorized_alerts_internal"] = categorized_details
        return decoded_data

    def _build_modbus_read_groups(self, register_list_tuples: List[Tuple[str, Dict[str, Any]]], max_regs_per_read: int) -> List[Dict[str, Any]]:
        """
        Groups registers into contiguous blocks for efficient Modbus reading.

        This method takes a list of registers and groups them to minimize the
        number of Modbus requests. It sorts registers by address and creates
        a new group when a gap between registers is too large or the group
        size exceeds the configured maximum.

        Args:
            register_list_tuples: A list of (key, info_dict) tuples from the register map.
            max_regs_per_read: The maximum number of registers to read in a single request.

        Returns:
            A list of group dictionaries, each specifying a start address, count, and keys.
        """
        groups: List[Dict[str, Any]] = []
        if not register_list_tuples: return groups
        sorted_regs = sorted(register_list_tuples, key=lambda item: (item[1].get('reg_func_type', 'input'), item[1]['addr']))
        current_group: Optional[Dict[str, Any]] = None
        max_gap = int(self.plugin_config.get("modbus_max_register_gap", 10))
        for key, info in sorted_regs:
            addr = info['addr']
            count = self._plugin_get_register_count(info["type"], self.logger)
            reg_func_type = info.get('reg_func_type', 'input')
            is_new_group = (
                current_group is None or
                reg_func_type != current_group['reg_func_type'] or
                addr >= current_group['start'] + current_group['count'] + max_gap or
                (addr + count - current_group['start'] > max_regs_per_read)
            )
            if is_new_group:
                if current_group: groups.append(current_group)
                current_group = {"start": addr, "count": count, "keys": [key], "reg_func_type": reg_func_type}
            else:
                current_group['count'] = (addr + count) - current_group['start']
                current_group['keys'].append(key)
        if current_group: groups.append(current_group)
        return groups

    def decode_inverter_model(self, model_code_value: Optional[int]) -> Tuple[Optional[int], str]:
        """
        Decodes the inverter model code into a protocol version and model description.

        Args:
            model_code_value: The integer value read from the model number register.

        Returns:
            A tuple containing:
            - The protocol version as an integer, or None on error.
            - A human-readable model description string.
        """
        if not isinstance(model_code_value, int): return None, "Invalid Input Type"
        try:
            protocol_version = (model_code_value >> 8) & 0xFF
            inverter_model_code_actual = model_code_value & 0xFF
            model_description = SOLIS_INVERTER_MODEL_CODES.get(inverter_model_code_actual, f"Unknown Solis Model (0x{inverter_model_code_actual:02X})")
            return protocol_version, model_description
        except Exception as e:
            model_code_hex = f"0x{model_code_value:04X}" if isinstance(model_code_value, int) else str(model_code_value)
            self.logger.error(f"SolisPlugin '{self.instance_name}': Error decoding model code {model_code_hex}: {e}")
            return None, "Decoding Error"

    def decode_battery_model(self, code_value: Optional[int]) -> str:
        """
        Decodes the battery model code into a human-readable name.

        Args:
            code_value: The integer value read from the battery model register.

        Returns:
            A string with the battery manufacturer's name or an "Unknown" message.
        """
        if not isinstance(code_value, int): return "Invalid Code Type"
        return BATTERY_MODEL_CODES.get(code_value, f"Unknown Battery Code ({code_value})")

    def _detect_mppts_heuristically(self, mppt_voltage_data: Dict[str, Any]) -> int:
        """
        Determines the number of active MPPTs based on reported voltages.

        It checks the voltage on up to 4 potential MPPT inputs. If any voltage
        is above a minimum threshold, it assumes that MPPT and all lower-numbered
        ones exist.

        Args:
            mppt_voltage_data: A dictionary containing DC voltage readings (e.g., {"dc_voltage_1": 120.5}).

        Returns:
            The detected number of MPPTs (e.g., 2 or 4).
        """
        default_mppt_count = self.app_state.default_mppt_count if self.app_state else int(self.plugin_config.get("default_mppt_count", 2))
        MIN_VOLTAGE_THRESHOLD = float(self.plugin_config.get("mppt_detection_min_voltage", 30.0))
        mppt_voltage_keys = ["dc_voltage_1", "dc_voltage_2", "dc_voltage_3", "dc_voltage_4"]
        active_mppt_indices = [i + 1 for i, solis_key in enumerate(mppt_voltage_keys) if isinstance(voltage := mppt_voltage_data.get(solis_key), (int, float)) and voltage > MIN_VOLTAGE_THRESHOLD]
        if not active_mppt_indices: return default_mppt_count
        highest_active_mppt_index = max(active_mppt_indices)
        final_mppt_count = 2 if highest_active_mppt_index <= 2 else 4
        return max(final_mppt_count, default_mppt_count)

    def read_static_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads static device information from the inverter.

        This includes serial number, model name, firmware version, and detected
        number of MPPTs and phases.

        Returns:
            A dictionary containing the standardized static data, or None if the read fails.
        """
        self.logger.info(f"SolisPlugin '{self.instance_name}': Reading static data...")
        if not self.is_connected:
            self.logger.error(f"SolisPlugin '{self.instance_name}': Cannot read static data, not connected.")
            return None
        
        static_items = list(self.static_registers_map.items())
        static_read_groups = self._build_modbus_read_groups(static_items, self.max_regs_per_read)
        solis_raw_static = self._read_registers_from_groups(static_read_groups)
        if solis_raw_static is None:
            self.logger.error(f"SolisPlugin '{self.instance_name}': Failed to read static data from device.")
            return None

        standardized_static_data: Dict[str, Any] = {StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter"}
        standardized_static_data[StandardDataKeys.STATIC_INVERTER_MANUFACTURER] = "Solis"
        model_num = solis_raw_static.get("model_number")
        model_desc_heuristic = UNKNOWN
        if isinstance(model_num, int):
            _, model_desc = self.decode_inverter_model(model_num)
            standardized_static_data[StandardDataKeys.STATIC_INVERTER_MODEL_NAME] = model_desc
            model_desc_heuristic = model_desc
        else:
            standardized_static_data[StandardDataKeys.STATIC_INVERTER_MODEL_NAME] = str(model_num) if model_num else UNKNOWN
        
        raw_batt_model = solis_raw_static.get("current_battery_model")
        standardized_static_data[StandardDataKeys.STATIC_BATTERY_MODEL_NAME] = self.decode_battery_model(raw_batt_model) if isinstance(raw_batt_model, int) else UNKNOWN
        
        serial = solis_raw_static.get("serial_number", UNKNOWN)
        if serial and serial not in [ERROR_READ, ERROR_DECODE, UNKNOWN]:
            standardized_static_data[StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER] = str(serial)
        else:
            standardized_static_data[StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER] = UNKNOWN
        dsp_ver = solis_raw_static.get("dsp_version", UNKNOWN)
        standardized_static_data[StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION] = f"DSP:0x{dsp_ver:X}" if isinstance(dsp_ver, int) else str(dsp_ver)
        
        mppt_volt_data_heuristic = {}
        if self.is_connected:
            mppt_v_keys = ["dc_voltage_1", "dc_voltage_2", "dc_voltage_3", "dc_voltage_4"]
            mppt_v_items = [(k,v) for k,v in self.dynamic_registers_map.items() if k in mppt_v_keys]
            if mppt_v_items:
                mppt_groups = self._build_modbus_read_groups(mppt_v_items, self.max_regs_per_read)
                if mppt_groups and (mppt_data := self._read_registers_from_groups(mppt_groups)):
                    mppt_volt_data_heuristic.update(mppt_data)
        
        num_mppts = self._detect_mppts_heuristically(mppt_volt_data_heuristic)
        standardized_static_data[StandardDataKeys.STATIC_NUMBER_OF_MPPTS] = num_mppts
        num_phases = 3 if "3P" in str(model_desc_heuristic).upper() or "THREE PHASE" in str(model_desc_heuristic).upper() else 1
        standardized_static_data[StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC] = num_phases
        
        configured_max_ac_power = self.plugin_config.get(StandardDataKeys.STATIC_RATED_POWER_AC_WATTS)
        if configured_max_ac_power is None and self.app_state and self.app_state.inverter_max_ac_power_w > 0:
            configured_max_ac_power = self.app_state.inverter_max_ac_power_w
        if configured_max_ac_power is not None:
            try:
                standardized_static_data[StandardDataKeys.STATIC_RATED_POWER_AC_WATTS] = float(configured_max_ac_power)
            except (ValueError, TypeError):
                self.logger.warning(f"SolisPlugin '{self.instance_name}': Could not parse configured rated AC power ('{configured_max_ac_power}') as float.")
                standardized_static_data[StandardDataKeys.STATIC_RATED_POWER_AC_WATTS] = None
        else:
             standardized_static_data[StandardDataKeys.STATIC_RATED_POWER_AC_WATTS] = None
        
        self.logger.info(f"SolisPlugin '{self.instance_name}' Static Data: Model='{standardized_static_data.get(StandardDataKeys.STATIC_INVERTER_MODEL_NAME)}', MPPTs={num_mppts}, Phases={num_phases}")
        return standardized_static_data

    def _standardize_operational_data(self, status_txt: str, solis_raw_dynamic: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts raw dynamic data from the inverter into the application's standard format.

        This involves calculating derived values (e.g., MPPT power), interpreting
        status codes, and mapping Solis-specific keys to standardized keys.

        Args:
            status_txt: The human-readable status of the inverter.
            solis_raw_dynamic: A dictionary of raw data read from the device.

        Returns:
            A dictionary containing standardized dynamic data.
        """
        self.logger.debug(f"Inverter status is '{status_txt}'. Processing full data packet.")
        def to_float_or_zero(value: Any) -> float:
            if value is None: return 0.0
            try: return float(value)
            except (ValueError, TypeError): return 0.0

        standardized_data = {}
        for i in range(1, 5):
            v = solis_raw_dynamic.get(f"dc_voltage_{i}")
            c = solis_raw_dynamic.get(f"dc_current_{i}")
            standardized_data[f"pv_mppt{i}_voltage_volts"] = v
            standardized_data[f"pv_mppt{i}_current_amps"] = c
            standardized_data[f"pv_mppt{i}_power_watts"] = round(to_float_or_zero(v) * to_float_or_zero(c), 2)

        inverter_power = to_float_or_zero(solis_raw_dynamic.get("active_power"))
        grid_power = to_float_or_zero(solis_raw_dynamic.get("meter_active_power"))
        load_power_direct = solis_raw_dynamic.get("house_load_power")
        backup_load = to_float_or_zero(solis_raw_dynamic.get("backup_load_power"))
        if isinstance(load_power_direct, (int, float)):
            load_power = to_float_or_zero(load_power_direct) + backup_load
        else: # Fallback calculation
            load_power = inverter_power + grid_power

        raw_battery_power = to_float_or_zero(solis_raw_dynamic.get("battery_power"))
        if solis_raw_dynamic.get("battery_direction") == 1:
            battery_power, batt_status_txt = raw_battery_power, "Discharging"
        elif solis_raw_dynamic.get("battery_direction") == 0:
            battery_power, batt_status_txt = -raw_battery_power, "Charging"
        else:
            battery_power, batt_status_txt = 0.0, "Idle" if raw_battery_power < 10 else f"Unknown Dir ({solis_raw_dynamic.get('battery_direction')})"

        pv_yield = to_float_or_zero(solis_raw_dynamic.get("energy_today"))
        grid_import = to_float_or_zero(solis_raw_dynamic.get("grid_import_today"))
        grid_export = to_float_or_zero(solis_raw_dynamic.get("grid_export_today"))
        batt_charge = to_float_or_zero(solis_raw_dynamic.get("battery_charge_today"))
        batt_discharge = to_float_or_zero(solis_raw_dynamic.get("battery_discharge_today"))
        load_energy_direct = solis_raw_dynamic.get("load_today_energy")
        load_energy = load_energy_direct if isinstance(load_energy_direct, (int, float)) and load_energy_direct >= 0 else max(0, (pv_yield + grid_import + batt_discharge) - (grid_export + batt_charge))

        standardized_data.update({
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: status_txt,
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status_txt,
            StandardDataKeys.AC_POWER_WATTS: inverter_power,
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: to_float_or_zero(solis_raw_dynamic.get("total_dc_power")),
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: grid_power,
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: load_power,
            StandardDataKeys.BATTERY_POWER_WATTS: battery_power,
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: solis_raw_dynamic.get("inverter_temp"),
            StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: solis_raw_dynamic.get("grid_voltage_l1"),
            StandardDataKeys.GRID_L1_CURRENT_AMPS: solis_raw_dynamic.get("grid_current_l1"),
            StandardDataKeys.GRID_FREQUENCY_HZ: solis_raw_dynamic.get("grid_frequency"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: solis_raw_dynamic.get("battery_voltage"),
            StandardDataKeys.BATTERY_CURRENT_AMPS: abs(to_float_or_zero(solis_raw_dynamic.get("battery_current"))),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: solis_raw_dynamic.get("battery_soc"),
            StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: solis_raw_dynamic.get("battery_soh"),
            StandardDataKeys.ENERGY_PV_DAILY_KWH: pv_yield,
            StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: batt_charge,
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: batt_discharge,
            StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: grid_import,
            StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH: grid_export,
            StandardDataKeys.ENERGY_LOAD_DAILY_KWH: load_energy,
            StandardDataKeys.EPS_TOTAL_ACTIVE_POWER_WATTS: backup_load,
            StandardDataKeys.EPS_L1_VOLTAGE_VOLTS: solis_raw_dynamic.get("backup_voltage_l1"),
            StandardDataKeys.EPS_L1_CURRENT_AMPS: solis_raw_dynamic.get("backup_current_l1"),
            StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_CODES_LIST: solis_raw_dynamic.get("_active_fault_codes_list_internal", []),
            StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT: solis_raw_dynamic.get("_categorized_alerts_internal", {})
        })
        return standardized_data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads and processes dynamic (periodically changing) data from the inverter.

        This is the main polling method. It reads all dynamic registers,
        handles specific states like "Waiting", standardizes the data, and
        updates the last known data cache.

        Returns:
            A dictionary of standardized dynamic data, or None on read failure.
        """
        self.logger.debug(f"SolisPlugin '{self.instance_name}': Reading dynamic data...")
        if not self.is_connected:
            self.logger.error(f"SolisPlugin '{self.instance_name}': Cannot read, not connected.")
            return None

        solis_raw_dynamic = self._read_registers_from_groups(self.dynamic_read_groups)
        if solis_raw_dynamic is None:
            self.logger.warning(f"SolisPlugin '{self.instance_name}': Failed to read dynamic data block. Signaling read failure.")
            return None

        status_code = solis_raw_dynamic.get("current_status")
        if not isinstance(status_code, int):
            self.logger.error(f"SolisPlugin '{self.instance_name}': Failed to decode status (got: '{status_code}'). Forcing disconnect.")
            self.disconnect()
            return None

        status_txt = SOLIS_INVERTER_STATUS_CODES.get(status_code, f"Unknown ({status_code})")

        if status_txt == "Waiting":
            self._waiting_status_counter += 1
            max_waiting_polls = int(self.plugin_config.get("max_consecutive_waiting_polls", 5))
            self.logger.info(f"SolisPlugin '{self.instance_name}': Inverter status is 'Waiting'. Count: {self._waiting_status_counter}/{max_waiting_polls}. Preserving last known values.")
            if self._waiting_status_counter >= max_waiting_polls:
                self.logger.warning(f"SolisPlugin '{self.instance_name}': Inverter stuck in 'Waiting' state for {max_waiting_polls} polls. Forcing reconnect.")
                self.disconnect()
                self._waiting_status_counter = 0
                return None
            
            updated_cache = self.last_known_dynamic_data.copy()
            updated_cache[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT] = status_txt
            updated_cache[StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_CODES_LIST] = solis_raw_dynamic.get("_active_fault_codes_list_internal", [])
            updated_cache[StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT] = solis_raw_dynamic.get("_categorized_alerts_internal", {})
            return updated_cache

        self._waiting_status_counter = 0
        standardized_dynamic_data = self._standardize_operational_data(status_txt, solis_raw_dynamic)
        self.last_known_dynamic_data = standardized_dynamic_data.copy()
        return standardized_dynamic_data

    def read_yesterday_energy_summary(self) -> Optional[Dict[str, Any]]:
        """
        Reads the energy summary data for the previous day.

        This is typically called once per day to fetch historical totals.

        Returns:
            A dictionary of standardized daily energy totals, or None on failure.
        """
        self.logger.info(f"SolisPlugin '{self.instance_name}': Reading yesterday's energy summary...")
        if not self.is_connected:
            self.last_error_message = "Cannot read yesterday summary, not connected."
            self.logger.error(f"SolisPlugin '{self.instance_name}': {self.last_error_message}")
            return None
            
        yesterday_registers_map = {k: v for k, v in self.dynamic_registers_map.items() if "yesterday" in k}
        if not yesterday_registers_map:
            self.logger.info("No 'yesterday' energy registers defined for this plugin.")
            return None
            
        read_groups = self._build_modbus_read_groups(list(yesterday_registers_map.items()), self.max_regs_per_read)
        raw_data = self._read_registers_from_groups(read_groups)
        if raw_data is None:
            self.last_error_message = "Failed to read yesterday's energy data from device."
            return None
            
        summary_data = {}
        key_map = {
            "energy_yesterday": StandardDataKeys.ENERGY_PV_DAILY_KWH,
            "battery_charge_yesterday": StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH,
            "battery_discharge_yesterday": StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH,
            "grid_import_yesterday": StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH,
            "grid_export_yesterday": StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH,
            "house_load_yesterday": StandardDataKeys.ENERGY_LOAD_DAILY_KWH,
        }
        for solis_key, std_key in key_map.items():
            if solis_key in raw_data and isinstance(raw_data[solis_key], (int, float)):
                summary_data[std_key] = raw_data[solis_key]
        return summary_data if summary_data else None