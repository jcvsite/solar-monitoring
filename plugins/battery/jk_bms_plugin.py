# plugins/battery/jk_bms_modbus_plugin.py
import struct
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.app_state import AppState

from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port
from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException
from pymodbus.pdu import ExceptionResponse

JK_MODBUS_REGISTERS: Dict[str, Dict[str, Any]] = {
    "total_voltage": {"addr": 0x0078, "type": "uint16", "scale": 0.01},
    "total_current": {"addr": 0x007A, "type": "int16", "scale": 0.01}, # Signed
    "soc": {"addr": 0x007C, "type": "uint16"},
    "cycle_count": {"addr": 0x007E, "type": "uint16"},
    "soh": {"addr": 0x007F, "type": "uint16"},
    "remaining_capacity_ah": {"addr": 0x0080, "type": "uint16", "scale": 0.01},
    "rated_capacity_ah": {"addr": 0x007D, "type": "uint16", "scale": 0.01},
    "cell_count": {"addr": 0x0082, "type": "uint16"},
    "max_cell_voltage": {"addr": 0x0088, "type": "uint16", "scale": 0.001},
    "max_cell_voltage_no": {"addr": 0x0089, "type": "uint16"},
    "min_cell_voltage": {"addr": 0x008A, "type": "uint16", "scale": 0.001},
    "min_cell_voltage_no": {"addr": 0x008B, "type": "uint16"},
    "max_cell_temp": {"addr": 0x008C, "type": "int16"},
    "max_cell_temp_no": {"addr": 0x008D, "type": "uint16"},
    "min_cell_temp": {"addr": 0x008E, "type": "int16"},
    "min_cell_temp_no": {"addr": 0x008F, "type": "uint16"},
    "temp_sensor_1": {"addr": 0x0090, "type": "int16"},
    "temp_sensor_2": {"addr": 0x0092, "type": "int16"},
    "mosfet_temp": {"addr": 0x0094, "type": "int16"},
    "status_bits": {"addr": 0x0096, "type": "uint16"},
    "alarm_bits": {"addr": 0x0098, "type": "uint32_le"},
    "bms_error_code": {"addr": 0x0097, "type": "uint16"},
    **{f"cell_{i+1}_voltage": {"addr": 0x009A + (i * 2), "type": "uint16", "scale": 0.001} for i in range(24)},
}

JK_ALARM_MAP = {
    0: "Cell Overvoltage", 1: "Cell Undervoltage", 2: "Pack Overvoltage", 3: "Pack Undervoltage",
    4: "Charge Over-temp", 5: "Charge Under-temp", 6: "Discharge Over-temp", 7: "Discharge Under-temp",
    8: "Charge Overcurrent", 9: "Discharge Overcurrent", 10: "SOC Too High", 11: "SOC Too Low",
    12: "Cell Difference Too High", 13: "MOSFET Over-temp"
}

def _decode(registers: List[int], info: Dict[str, Any]) -> Any:
    """
    Decodes raw Modbus register values based on data type specification.
    
    Handles various JK BMS data types including signed/unsigned integers
    and little-endian 32-bit values. Provides error handling for malformed data.
    
    Args:
        registers: List of raw 16-bit register values from Modbus
        info: Dictionary containing type and scaling information
        
    Returns:
        Decoded value or None if decoding fails
    """
    val_type = info.get("type", "uint16")
    if not registers: return None
    try:
        if val_type == "uint16": return registers[0]
        if val_type == "int16": return struct.unpack('>h', registers[0].to_bytes(2, 'big'))[0]
        if val_type == "uint32_le":
            val_bytes = registers[0].to_bytes(2, 'little') + registers[1].to_bytes(2, 'little')
            return struct.unpack('<I', val_bytes)[0]
    except (struct.error, IndexError): return None
    return None

class JkBmsModbusPlugin(DevicePlugin):
    """
    Plugin for JK BMS devices using Modbus communication protocol.
    
    This plugin communicates with JK Battery Management Systems that support
    the RS485 Modbus protocol. It supports both TCP and serial connections
    and provides comprehensive battery monitoring including cell voltages,
    temperatures, alarms, and balancing status.
    
    Key Features:
    - Modbus TCP and RTU (serial) support
    - Individual cell voltage monitoring (up to 24 cells)
    - Temperature monitoring with multiple sensors
    - Alarm and warning detection
    - Cell balancing status monitoring
    - Comprehensive battery state reporting
    """
    
    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.last_known_dynamic_data: Dict[str, Any] = {}
        self.connection_type = self.plugin_config.get("connection_type", "tcp").lower()
        self.slave_address = int(self.plugin_config.get("slave_address", 1))
        timeout = int(self.plugin_config.get("modbus_timeout_seconds", 10))

        if self.connection_type == "tcp":
            self.tcp_host = self.plugin_config.get("tcp_host")
            self.tcp_port = int(self.plugin_config.get("tcp_port", 8899))
            if not self.tcp_host: self.logger.error(f"JK BMS Plugin '{self.instance_name}': 'tcp_host' not configured for TCP connection.")
            self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=timeout)
        elif self.connection_type == "serial":
            self.serial_port = self.plugin_config.get("serial_port")
            self.baud_rate = int(self.plugin_config.get("baud_rate", 115200))
            if not self.serial_port: self.logger.error(f"JK BMS Plugin '{self.instance_name}': 'serial_port' not configured for serial connection.")
            self.client = ModbusSerialClient(port=self.serial_port, baudrate=self.baud_rate, timeout=timeout)
        else:
            self.logger.error(f"JK BMS Plugin '{self.instance_name}': Invalid connection_type '{self.connection_type}'. Must be 'tcp' or 'serial'.")
            self.client = None

    @property
    def name(self) -> str: return "jk_bms_modbus"
    @property
    def pretty_name(self) -> str: return "JK BMS (Modbus)"

    def connect(self) -> bool:
        """
        Establishes connection to the JK BMS device.
        
        For TCP connections, performs a pre-connection port check to validate
        network connectivity. Handles both TCP and serial connection types
        with appropriate error handling and logging.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._is_connected_flag and self.client and self.client.is_socket_open(): return True
        
        if self.connection_type == "tcp":
            if not getattr(self, 'tcp_host', None): self.last_error_message = "TCP host not configured."; return False
            port_open, _, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open: self.last_error_message = f"Pre-check failed: {err_msg}"; return False
        elif self.connection_type == "serial":
             if not getattr(self, 'serial_port', None): self.last_error_message = "Serial port not configured."; return False

        try:
            if self.client and self.client.connect():
                self._is_connected_flag = True; return True
        except Exception as e:
            self.last_error_message = f"Connection failed: {e}"
        return False

    def disconnect(self) -> None:
        """
        Closes the connection to the JK BMS device.
        
        Safely closes the Modbus client connection and resets the
        connection state flag.
        """
        if self.client: self.client.close()
        self._is_connected_flag = False

    def read_static_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads static device identification information.
        
        Returns basic device information including manufacturer, model,
        and a generated serial number based on the slave address.
        
        Returns:
            Dictionary containing static device information using StandardDataKeys
        """
        return {
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms",
            StandardDataKeys.STATIC_BATTERY_MANUFACTURER: "JK BMS",
            StandardDataKeys.STATIC_BATTERY_MODEL_NAME: "JKBMS (RS485)",
            StandardDataKeys.STATIC_BATTERY_SERIAL_NUMBER: f"jk_{self.slave_address}",
        }

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads comprehensive dynamic battery data from the JK BMS.
        
        Performs a single large Modbus read to get all battery telemetry including:
        - Battery voltage, current, power, and SOC
        - Individual cell voltages (up to 24 cells)
        - Temperature readings from multiple sensors
        - Alarm and warning status
        - FET status and balancing information
        - Capacity and cycle count data
        
        The method handles communication errors gracefully and maintains
        the last known good data for system stability.
        
        Returns:
            Dictionary of standardized battery data or None if read fails
        """
        if not self.is_connected: return None
        # Read a single large block covering all registers
        start_addr = 0x0078
        end_addr = 0x00E5 # Last cell voltage register
        num_regs_to_read = (end_addr - start_addr) + 1
        
        try:
            result = self.client.read_holding_registers(start_addr, num_regs_to_read, slave=self.slave_address)
            if result.isError() or isinstance(result, ExceptionResponse):
                raise ModbusIOException(f"Modbus error reading main block: {result}")
        except (ModbusException, ModbusIOException) as e:
            self.last_error_message = f"Modbus communication error: {e}"
            self.disconnect()
            return self.last_known_dynamic_data

        raw_data = {}
        for key, info in JK_MODBUS_REGISTERS.items():
            idx = info['addr'] - start_addr
            num_regs = 2 if '32' in info.get('type', '') else 1
            if idx >= 0 and (idx + num_regs) <= len(result.registers):
                raw_val = _decode(result.registers[idx : idx + num_regs], info)
                if raw_val is not None:
                    val = float(raw_val)
                    if "scale" in info: val *= info["scale"]
                    raw_data[key] = val
        
        self.last_known_dynamic_data.update(raw_data)
        
        # --- Calculations and Standardization ---
        current = -self.last_known_dynamic_data.get('total_current', 0)
        power = self.last_known_dynamic_data.get('total_voltage', 0) * current
        
        batt_status = "Idle"
        if power > 10: batt_status = "Discharging"
        elif power < -10: batt_status = "Charging"

        status_bits = int(self.last_known_dynamic_data.get('status_bits', 0))
        balancing = bool((status_bits >> 8) & 1)
        charge_fet = bool((status_bits >> 0) & 1)
        discharge_fet = bool((status_bits >> 1) & 1)

        alarm_bits = int(self.last_known_dynamic_data.get('alarm_bits', 0))
        alarms = [desc for bit, desc in JK_ALARM_MAP.items() if (alarm_bits >> bit) & 1]

        cell_count = int(self.last_known_dynamic_data.get('cell_count', 0))
        cell_voltages = [self.last_known_dynamic_data.get(f"cell_{i+1}_voltage") for i in range(cell_count)]
        valid_cell_voltages = [v for v in cell_voltages if isinstance(v, float) and v > 2.0]
        
        temps = [self.last_known_dynamic_data.get("temp_sensor_1"), self.last_known_dynamic_data.get("temp_sensor_2")]
        valid_temps = [t for t in temps if t is not None]

        return {
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: self.last_known_dynamic_data.get("soc"),
            StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: self.last_known_dynamic_data.get("soh"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: self.last_known_dynamic_data.get("total_voltage"),
            StandardDataKeys.BATTERY_CURRENT_AMPS: current,
            StandardDataKeys.BATTERY_POWER_WATTS: power,
            StandardDataKeys.BATTERY_CYCLES_COUNT: self.last_known_dynamic_data.get("cycle_count"),
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status,
            StandardDataKeys.BMS_CHARGE_FET_ON: charge_fet,
            StandardDataKeys.BMS_DISCHARGE_FET_ON: discharge_fet,
            StandardDataKeys.BMS_CELLS_BALANCING_TEXT: "Active" if balancing else "None",
            StandardDataKeys.BMS_ACTIVE_ALARMS_LIST: alarms,
            StandardDataKeys.BMS_FAULT_SUMMARY_TEXT: alarms[0] if alarms else "Normal",
            StandardDataKeys.BMS_CELL_COUNT: cell_count,
            StandardDataKeys.BMS_CELL_VOLTAGES_LIST: valid_cell_voltages,
            StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS: self.last_known_dynamic_data.get("min_cell_voltage"),
            StandardDataKeys.BMS_CELL_WITH_MIN_VOLTAGE_NUMBER: self.last_known_dynamic_data.get("min_cell_voltage_no"),
            StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS: self.last_known_dynamic_data.get("max_cell_voltage"),
            StandardDataKeys.BMS_CELL_WITH_MAX_VOLTAGE_NUMBER: self.last_known_dynamic_data.get("max_cell_voltage_no"),
            StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS: (self.last_known_dynamic_data.get("max_cell_voltage", 0) - self.last_known_dynamic_data.get("min_cell_voltage", 0)) if valid_cell_voltages else 0,
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: self.last_known_dynamic_data.get("temp_sensor_1"),
            StandardDataKeys.BMS_TEMP_MIN_CELSIUS: self.last_known_dynamic_data.get("min_cell_temp"),
            StandardDataKeys.BMS_TEMP_MAX_CELSIUS: self.last_known_dynamic_data.get("max_cell_temp"),
            StandardDataKeys.BMS_REMAINING_CAPACITY_AH: self.last_known_dynamic_data.get("remaining_capacity_ah"),
            StandardDataKeys.BMS_FULL_CAPACITY_AH: self.last_known_dynamic_data.get("rated_capacity_ah"),
        }