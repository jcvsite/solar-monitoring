# plugins/battery/seplos_bms_v3_plugin.py
import time
import struct
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.app_state import AppState

from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
from pymodbus.exceptions import ModbusException, ModbusIOException

# Based on Seplos V3 documentation
# Note: Deye/Sunsynk uses Holding Registers, Seplos V3 uses Input Registers
SEPLOS_V3_REGISTERS = {
    "voltage": {"addr": 0x1000, "type": "uint16", "scale": 0.01},
    "current": {"addr": 0x1001, "type": "int16", "scale": 0.01}, # Signed
    "remaining_capacity": {"addr": 0x1002, "type": "uint16", "scale": 0.01},
    "total_capacity": {"addr": 0x1003, "type": "uint16", "scale": 0.01},
    "soc": {"addr": 0x1005, "type": "uint16", "scale": 0.1},
    "soh": {"addr": 0x1006, "type": "uint16", "scale": 0.1},
    "cycle_count": {"addr": 0x1007, "type": "uint16"},
    "avg_cell_voltage": {"addr": 0x1008, "type": "uint16", "scale": 0.001},
    "avg_cell_temp": {"addr": 0x1009, "type": "uint16", "scale": 0.1, "offset": -273.1},
    "max_cell_voltage": {"addr": 0x100A, "type": "uint16", "scale": 0.001},
    "min_cell_voltage": {"addr": 0x100B, "type": "uint16", "scale": 0.001},
    "max_cell_temp": {"addr": 0x100C, "type": "uint16", "scale": 0.1, "offset": -273.1},
    "min_cell_temp": {"addr": 0x100D, "type": "uint16", "scale": 0.1, "offset": -273.1},
    # Cell voltages start at 0x1100
    **{f"cell_{i+1}_voltage": {"addr": 0x1100 + i, "type": "uint16", "scale": 0.001} for i in range(16)},
    # Temperatures start at 0x1110
    **{f"temp_{i+1}": {"addr": 0x1110 + i, "type": "uint16", "scale": 0.1, "offset": -273.1} for i in range(10)},
}

SEPLOS_V3_ALARMS = {
    # Add key alarms from the provided documentation
    65: "Discharge Event", 
    66: "Charge Event", 
    67: "Floating Charge",
    73: "Cell High Voltage Alarm", 
    74: "Cell Overvoltage Protection",
    75: "Cell Low Voltage Alarm", 
    76: "Cell Undervoltage Protection",
    81: "Charge High Temperature Alarm", 
    82: "Charge Over-temperature Protection",
    85: "Discharge High Temperature Alarm", 
    86: "Discharge Over-temperature Protection",
    97: "Charge Current Alarm", 
    98: "Charge Overcurrent Protection",
    100: "Discharge Current Alarm", 
    101: "Discharge Overcurrent Protection",
    102: "Output Short-circuit Protection", 
    115: "SOC Low Alarm",
    121: "Discharge FET On", 
    122: "Charge FET On",
}

class SeplosBmsV3Plugin(DevicePlugin):
    """
    Plugin to communicate with Seplos V3 protocol BMS devices over Modbus.

    This class implements the `DevicePlugin` interface for Seplos V3 BMS devices
    that use Modbus for communication. It supports both Modbus TCP and Modbus RTU
    (serial) connections. It reads telemetry from input registers and alarm
    statuses from coils, then standardizes the data for the application.
    """
    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.last_known_dynamic_data = {}
        self.connection_type = self.plugin_config.get("connection_type", "tcp").lower()
        self.tcp_host = self.plugin_config.get("tcp_host")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 8899)) # Common port for adapters
        self.serial_port = self.plugin_config.get("serial_port")
        self.baud_rate = int(self.plugin_config.get("baud_rate", 19200))
        self.slave_address = int(self.plugin_config.get("slave_address", 0)) # Packet says Client 1 = ID 0
        timeout = int(self.plugin_config.get("modbus_timeout_seconds", 10))
        
        if self.connection_type == "tcp":
            self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=timeout)
        else: # serial
            self.client = ModbusSerialClient(port=self.serial_port, baudrate=self.baud_rate, timeout=timeout)

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        """
        Returns a list of configuration parameters that this plugin supports.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary
                                  describes a configurable parameter.
        """
        return [
            {"name": "connection_type", "type": str, "default": "tcp", "description": "Connection type: 'tcp' or 'serial'.", "options": ["tcp", "serial"]},
            {"name": "tcp_host", "type": str, "default": None, "description": "IP Address or Hostname of BMS adapter (if type is 'tcp')."},
            {"name": "tcp_port", "type": int, "default": 8899, "description": "TCP Port for BMS adapter (if type is 'tcp')."},
            {"name": "serial_port", "type": str, "default": None, "description": "Serial port (if type is 'serial'). E.g., /dev/ttyUSB0 or COM3."},
            {"name": "baud_rate", "type": int, "default": 19200, "description": "Baud rate for serial connection."},
            {"name": "slave_address", "type": int, "default": 0, "description": "Modbus slave address (unit ID)."},
            {"name": "modbus_timeout_seconds", "type": int, "default": 10, "description": "Modbus connection and read timeout."},
        ]

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "seplos_bms_v3"
    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "Seplos BMS v3"

    def connect(self) -> bool:
        """
        Establishes a connection to the BMS via Modbus TCP or Serial.

        Returns:
            bool: True on successful connection, False otherwise.
        """
        if self._is_connected_flag: return True
        if self.connection_type == "tcp":
            if not check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)[0]:
                self.last_error_message = f"TCP port check failed for {self.tcp_host}:{self.tcp_port}"
                return False
        try:
            if self.client.connect():
                self._is_connected_flag = True; return True
        except Exception as e:
            self.last_error_message = f"Connection exception: {e}"
        return False

    def disconnect(self) -> None:
        """Closes the Modbus connection."""
        if self.client: self.client.close()
        self._is_connected_flag = False

    def read_static_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads static device information from the BMS.

        Seplos V3 provides manufacturer, model, and serial number in a block of
        input registers starting at 0x1700. This method reads that block and
        parses the ASCII string.

        Returns:
            A dictionary containing the standardized static data keys, or None
            if the read fails. A fallback with default values is used if parsing
            the string fails.
        """

        if not self.is_connected: return None
        try:
            # Read manufacturer info from 0x1700, length 51
            result = self.client.read_input_registers(0x1700, 51, unit=self.slave_address)
            if result.isError(): return None
            # The result is a long string, let's parse the useful parts
            full_string = b''.join(r.to_bytes(2, 'big') for r in result.registers).decode('ascii', errors='ignore').strip('\x00')
            manufacturer = full_string[:20].strip() # Example parsing
            model = full_string[20:40].strip()
            serial = full_string[40:].strip()
        except Exception:
            manufacturer, model, serial = "Seplos", "Seplos V3", "Unknown"
        
        return {
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms",
            StandardDataKeys.STATIC_BATTERY_MANUFACTURER: manufacturer,
            StandardDataKeys.STATIC_BATTERY_MODEL_NAME: model,
            StandardDataKeys.STATIC_BATTERY_SERIAL_NUMBER: serial,
        }

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        """
        Reads a full set of dynamic data from the BMS.

        This method orchestrates reading the main telemetry data blocks from
        input registers and the alarm statuses from coils. It then processes
        this raw data, standardizes it, and returns the result.

        Returns:
            A dictionary of standardized dynamic data, or None if essential
            read operations fail.
        """
        if not self.is_connected: return None
        
        # Read the two main blocks of Input Registers
        telemetry_block_1 = self._read_input_registers_block(0x1000, 0x12)
        telemetry_block_2 = self._read_input_registers_block(0x1100, 0x1A)
        # Read the alarm block as Coils
        alarm_coils = self._read_coils_block(0x1200, 0x90)
        
        if telemetry_block_1 is None or telemetry_block_2 is None:
            return None # Failed to read essential data

        # Combine raw data
        raw_data = {**telemetry_block_1, **telemetry_block_2}
        
        # Process alarms
        warnings, alarms, active_balancing_cells = [], [], []
        if alarm_coils:
            for bit, description in SEPLOS_V3_ALARMS.items():
                if bit - 0x1200 < len(alarm_coils) and alarm_coils[bit - 0x1200]:
                    if "Protection" in description or "Fault" in description: alarms.append(description)
                    elif "Alarm" in description: warnings.append(description)
            
            # Check balancing status (bits 48-63)
            for i in range(16):
                if 48 + i < len(alarm_coils) and alarm_coils[48+i]:
                    active_balancing_cells.append(str(i+1))

        raw_data["warnings"] = warnings
        raw_data["alarms"] = alarms
        raw_data["balancing_cells"] = ", ".join(active_balancing_cells) or "None"

        # Standardize and calculate final values
        std_data = self._standardize(raw_data)

        if not self._is_data_sane(std_data):
            self.last_error_message = "Data failed sanity check (e.g., unreasonable values)."
            self.disconnect()
            return None

        self.last_known_dynamic_data.update(std_data)
        return self.last_known_dynamic_data

    def _is_data_sane(self, std_data):
        """
        Performs basic sanity checks on the standardized data.

        This method validates that critical values like SOC are within
        reasonable ranges to detect communication errors or device malfunctions.

        Args:
            std_data (dict): The standardized data dictionary to validate.

        Returns:
            bool: True if the data passes sanity checks, False otherwise.
        """
        # Basic sanity checks
        soc = std_data.get(StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT)
        if soc is not None and not (0 <= soc <= 105):
            self.logger.warning(f"Seplos V3: SOC value {soc}% is out of reasonable range")
            return False
            
        voltage = std_data.get(StandardDataKeys.BATTERY_VOLTAGE_VOLTS)
        if voltage is not None and not (10 <= voltage <= 100):
            self.logger.warning(f"Seplos V3: Battery voltage {voltage}V is out of reasonable range")
            return False
            
        return True

    def _read_input_registers_block(self, start_addr, count):
        """
        Helper method to read a block of Modbus Input Registers.

        It reads the specified registers, decodes the values based on the
        `SEPLOS_V3_REGISTERS` definition, and returns a dictionary of the
        decoded data.

        Args:
            start_addr (int): The starting register address.
            count (int): The number of registers to read.

        Returns:
            A dictionary of the decoded values, or None on a Modbus error.
        """
        try:
            result = self.client.read_input_registers(start_addr, count, unit=self.slave_address)
            if result.isError(): return None
            
            decoded = {}
            for key, info in SEPLOS_V3_REGISTERS.items():
                if info['addr'] >= start_addr and info['addr'] < start_addr + count:
                    idx = info['addr'] - start_addr
                    raw_val = result.registers[idx]
                    val = float(raw_val)
                    if "scale" in info: val *= info["scale"]
                    if "offset" in info: val += info["offset"]
                    decoded[key] = val
            return decoded
        except ModbusIOException as e:
            self.logger.warning(f"Modbus IO error reading registers @{hex(start_addr)}: {e}")
            self.disconnect()
            return None

    def _read_coils_block(self, start_addr, count):
        """
        Helper method to read a block of Modbus Coils.

        Args:
            start_addr (int): The starting coil address.
            count (int): The number of coils to read.

        Returns:
            A list of booleans representing the coil states, or None on a
            Modbus error.
        """
        try:
            result = self.client.read_coils(start_addr, count, unit=self.slave_address)
            if result.isError(): return None
            return result.bits
        except ModbusIOException as e:
            self.logger.warning(f"Modbus IO error reading coils @{hex(start_addr)}: {e}")
            self.disconnect()
            return None

    def _standardize(self, raw_data):
        """
        Converts the raw, decoded Modbus data into the application's standard format.

        This method maps the plugin-specific keys to `StandardDataKeys`, calculates
        derived values (like power and status), and ensures data conventions
        (like power sign) are met.

        Args:
            raw_data (dict): A dictionary of raw data from the decoding methods.

        Returns:
            A dictionary with standardized keys and values.
        """
        cell_voltages = [raw_data.get(f"cell_{i+1}_voltage") for i in range(16)]
        cell_voltages = [v for v in cell_voltages if isinstance(v, float)]
        
        battery_power = raw_data.get('voltage', 0) * raw_data.get('current', 0)
        
        # Determine status text
        batt_status = "Idle"
        alarms = raw_data.get("alarms", [])
        warnings = raw_data.get("warnings", [])
        if alarms:
            batt_status = f"Protection: {alarms[0]}"
        elif warnings:
            batt_status = f"Warning: {warnings[0]}"
        elif battery_power > 10: batt_status = "Charging"
        elif battery_power < -10: batt_status = "Discharging"

        # Invert power and current to match our standard (+ discharge, - charge)
        battery_power *= -1
        current = raw_data.get('current', 0) * -1
        
        return {
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: raw_data.get("soc"),
            StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: raw_data.get("soh"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: raw_data.get("voltage"),
            StandardDataKeys.BATTERY_CURRENT_AMPS: current,
            StandardDataKeys.BATTERY_POWER_WATTS: battery_power,
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: raw_data.get("avg_cell_temp"),
            StandardDataKeys.BATTERY_CYCLES_COUNT: raw_data.get("cycle_count"),
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status,
            StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS: raw_data.get("min_cell_voltage"),
            StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS: raw_data.get("max_cell_voltage"),
            StandardDataKeys.BMS_CELL_VOLTAGE_AVERAGE_VOLTS: raw_data.get("avg_cell_voltage"),
            StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS: raw_data.get("max_cell_voltage", 0) - raw_data.get("min_cell_voltage", 0),
            StandardDataKeys.BMS_TEMP_MIN_CELSIUS: raw_data.get("min_cell_temp"),
            StandardDataKeys.BMS_TEMP_MAX_CELSIUS: raw_data.get("max_cell_temp"),
            StandardDataKeys.BMS_REMAINING_CAPACITY_AH: raw_data.get("remaining_capacity"),
            StandardDataKeys.BMS_FULL_CAPACITY_AH: raw_data.get("total_capacity"),
            StandardDataKeys.BMS_CELL_VOLTAGES_LIST: cell_voltages,
            StandardDataKeys.BMS_ACTIVE_WARNINGS_LIST: raw_data.get("warnings"),
            StandardDataKeys.BMS_ACTIVE_ALARMS_LIST: raw_data.get("alarms"),
            StandardDataKeys.BMS_CELLS_BALANCING_TEXT: raw_data.get("balancing_cells"),
        }