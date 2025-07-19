# BMS Plugin Design Reference

## Based on the Stable Seplos V2 Plugin Architecture

This document serves as the definitive reference for creating new BMS (Battery Management System) plugins in the Solar Monitoring Framework. It is based on the proven, stable design of the **Seplos V2 BMS Plugin**, which has been thoroughly tested and refined.

## 🏗️ **Core Architecture Pattern**

### **File Structure**
Every BMS plugin should follow this pattern:
```
plugins/battery/
├── your_bms_plugin.py          # Main plugin class
├── bms_plugin_base.py          # Shared base class (already exists)
└── (optional constants file)    # Protocol-specific constants if needed
```

### **Why This Pattern Works**
- **Inheritance from BMSPluginBase**: Provides standardized BMS interface
- **Consistent Data Keys**: Uses predefined StandardDataKeys for BMS data
- **Standardized Alert Processing**: Built-in categorization of alarms/warnings
- **Connection Flexibility**: Supports both Serial and TCP connections
- **Data Validation**: Built-in validation ranges and error handling

---

## 📋 **BMS Plugin Base Interface**

### **Key Standardized Data Keys**
The `BMSPluginBase` provides these standardized keys:

```python
# Core Battery Data
BMS_KEY_SOC = StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT
BMS_KEY_SOH = StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT
BMS_KEY_VOLTAGE = StandardDataKeys.BATTERY_VOLTAGE_VOLTS
BMS_KEY_CURRENT = StandardDataKeys.BATTERY_CURRENT_AMPS
BMS_KEY_POWER = StandardDataKeys.BATTERY_POWER_WATTS

# Capacity Information
BMS_KEY_REMAINING_CAPACITY_AH = StandardDataKeys.BMS_REMAINING_CAPACITY_AH
BMS_KEY_FULL_CAPACITY_AH = StandardDataKeys.BMS_FULL_CAPACITY_AH
BMS_KEY_NOMINAL_CAPACITY_AH = StandardDataKeys.BMS_NOMINAL_CAPACITY_AH
BMS_KEY_CYCLE_COUNT = StandardDataKeys.BATTERY_CYCLES_COUNT

# Cell Data
BMS_KEY_CELL_COUNT = StandardDataKeys.BMS_CELL_COUNT
BMS_KEY_CELL_VOLTAGES_ALL = StandardDataKeys.BMS_CELL_VOLTAGES_LIST
BMS_KEY_CELL_VOLTAGE_MIN = StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS
BMS_KEY_CELL_VOLTAGE_MAX = StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS
BMS_KEY_CELL_VOLTAGE_AVG = StandardDataKeys.BMS_CELL_VOLTAGE_AVERAGE_VOLTS
BMS_KEY_CELL_VOLTAGE_DIFF = StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS

# Temperature Data
BMS_KEY_TEMPERATURES_ALL = StandardDataKeys.BMS_CELL_TEMPERATURES_LIST
BMS_KEY_TEMP_MAX = StandardDataKeys.BMS_TEMP_MAX_CELSIUS
BMS_KEY_TEMP_MIN = StandardDataKeys.BMS_TEMP_MIN_CELSIUS

# Status and Control
BMS_KEY_STATUS_TEXT = StandardDataKeys.BATTERY_STATUS_TEXT
BMS_KEY_CHARGE_FET_ON = StandardDataKeys.BMS_CHARGE_FET_ON
BMS_KEY_DISCHARGE_FET_ON = StandardDataKeys.BMS_DISCHARGE_FET_ON
BMS_KEY_CELLS_BALANCING = StandardDataKeys.BMS_CELLS_BALANCING_TEXT

# Alarms and Warnings
BMS_KEY_ACTIVE_ALARMS_LIST = StandardDataKeys.BMS_ACTIVE_ALARMS_LIST
BMS_KEY_ACTIVE_WARNINGS_LIST = StandardDataKeys.BMS_ACTIVE_WARNINGS_LIST
BMS_KEY_FAULT_SUMMARY = StandardDataKeys.BMS_FAULT_SUMMARY_TEXT

# Static Information
BMS_KEY_MANUFACTURER = StandardDataKeys.STATIC_BATTERY_MANUFACTURER
BMS_KEY_MODEL = StandardDataKeys.STATIC_BATTERY_MODEL_NAME
BMS_KEY_SERIAL_NUMBER = StandardDataKeys.STATIC_BATTERY_SERIAL_NUMBER
BMS_KEY_FIRMWARE_VERSION = StandardDataKeys.STATIC_BATTERY_FIRMWARE_VERSION
BMS_KEY_HARDWARE_VERSION = StandardDataKeys.STATIC_BMS_HARDWARE_VERSION
```

---

## 🔧 **Main BMS Plugin Class Structure**

### **File: `your_bms_plugin.py`**

```python
import time
import serial
from serial.serialutil import SerialException, SerialTimeoutException
import socket
import logging
from typing import Any, Dict, Optional, List, Union, Tuple, TYPE_CHECKING
from datetime import datetime
import copy

if TYPE_CHECKING:
    from core.app_state import AppState

# Import plugin utilities
try:
    from ..plugin_utils import check_tcp_port, check_icmp_ping
except ImportError:
    from plugin_utils import check_tcp_port, check_icmp_ping

# Import BMS base class and standardized keys
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
        BMS_KEY_MANUFACTURER, BMS_KEY_MODEL, BMS_KEY_SERIAL_NUMBER, 
        BMS_KEY_FIRMWARE_VERSION, BMS_KEY_HARDWARE_VERSION,
        BMS_PLUGIN_LAST_UPDATE, BMS_KEY_CELL_DISCONNECTION_PREFIX
    )
except ImportError:
    from bms_plugin_base import (...)  # Fallback import

# Protocol-specific constants
DEFAULT_BAUD_RATE = 9600
DEFAULT_TCP_PORT = 8080
DEFAULT_TCP_TIMEOUT_SECONDS = 5.0

# Data validation ranges
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

class YourBMSPlugin(BMSPluginBase):
    """
    Plugin to communicate with [Your BMS Brand] devices.
    
    This class implements the BMSPluginBase for [Your BMS] protocol devices.
    It supports both serial and TCP connections and handles encoding commands,
    sending them, receiving responses, and decoding the data into standardized format.
    """
    
    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], 
                 main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """Initialize the BMS plugin."""
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        # Initialize connection parameters
        self._init_connection_params()
        
        # Initialize protocol-specific settings
        self._init_protocol_params()
        
        # Connection objects
        self.serial_connection: Optional[serial.Serial] = None
        self.tcp_socket: Optional[socket.socket] = None
        
        self.logger.info(f"[Your BMS] Plugin '{self.instance_name}': Initialized")

    def _init_connection_params(self):
        """Initialize connection-related parameters."""
        self.connection_type = self.plugin_config.get("connection_type", "serial").strip().lower()
        
        # Serial parameters
        self.serial_port_name = self.plugin_config.get("serial_port")
        self.baud_rate = int(self.plugin_config.get("baud_rate", DEFAULT_BAUD_RATE))
        self.serial_timeout = float(self.plugin_config.get("serial_timeout", 2.0))
        
        # TCP parameters
        self.tcp_host = self.plugin_config.get("tcp_host")
        self.tcp_port = int(self.plugin_config.get("tcp_port", DEFAULT_TCP_PORT))
        self.tcp_timeout = float(self.plugin_config.get("tcp_timeout", DEFAULT_TCP_TIMEOUT_SECONDS))
        
        # Common parameters
        self.pack_address = int(self.plugin_config.get("pack_address", 0))

    def _init_protocol_params(self):
        """Initialize protocol-specific parameters."""
        self.inter_command_delay_ms = int(self.plugin_config.get("inter_command_delay_ms", 100))
        self.max_retries = int(self.plugin_config.get("max_retries", 3))
        
        # Add any protocol-specific initialization here

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "your_bms"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "[Your BMS Brand] Battery Management System"

    # ... implement required methods
```

---

## 🔑 **Required Method Implementations**

### **1. Connection Management**

```python
def connect(self) -> bool:
    """Establish connection to the BMS."""
    if self._is_connected_flag:
        return True
    
    self.disconnect()  # Clean up any existing connections
    self.last_error_message = None
    
    try:
        if self.connection_type == "serial":
            return self._connect_serial()
        elif self.connection_type == "tcp":
            return self._connect_tcp()
        else:
            self.last_error_message = f"Unsupported connection type: {self.connection_type}"
            self.logger.error(self.last_error_message)
            return False
            
    except Exception as e:
        self.last_error_message = f"Connection failed: {e}"
        self.logger.error(self.last_error_message, exc_info=True)
        return False

def _connect_serial(self) -> bool:
    """Establish serial connection."""
    if not self.serial_port_name:
        self.last_error_message = "Serial port not configured"
        self.logger.error(self.last_error_message)
        return False
    
    try:
        self.serial_connection = serial.Serial(
            port=self.serial_port_name,
            baudrate=self.baud_rate,
            timeout=self.serial_timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )
        
        if self.serial_connection.is_open:
            self._is_connected_flag = True
            self.logger.info(f"Serial connection established: {self.serial_port_name}@{self.baud_rate}")
            return True
        else:
            self.last_error_message = "Serial port failed to open"
            return False
            
    except SerialException as e:
        self.last_error_message = f"Serial connection error: {e}"
        self.logger.error(self.last_error_message)
        return False

def _connect_tcp(self) -> bool:
    """Establish TCP connection."""
    if not self.tcp_host:
        self.last_error_message = "TCP host not configured"
        self.logger.error(self.last_error_message)
        return False
    
    # Pre-connection checks
    port_open, rtt_ms, err_msg = check_tcp_port(
        self.tcp_host, self.tcp_port, logger_instance=self.logger
    )
    if not port_open:
        self.last_error_message = f"TCP port check failed: {err_msg}"
        self.logger.error(self.last_error_message)
        return False
    
    try:
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.settimeout(self.tcp_timeout)
        self.tcp_socket.connect((self.tcp_host, self.tcp_port))
        
        self._is_connected_flag = True
        self.logger.info(f"TCP connection established: {self.tcp_host}:{self.tcp_port}")
        return True
        
    except socket.error as e:
        self.last_error_message = f"TCP connection error: {e}"
        self.logger.error(self.last_error_message)
        if self.tcp_socket:
            self.tcp_socket.close()
            self.tcp_socket = None
        return False

def disconnect(self) -> None:
    """Close all connections."""
    self._is_connected_flag = False
    
    if self.serial_connection:
        try:
            self.serial_connection.close()
        except Exception as e:
            self.logger.error(f"Error closing serial connection: {e}")
        finally:
            self.serial_connection = None
    
    if self.tcp_socket:
        try:
            self.tcp_socket.close()
        except Exception as e:
            self.logger.error(f"Error closing TCP connection: {e}")
        finally:
            self.tcp_socket = None
    
    self.logger.info("Disconnected from BMS")
```

### **2. Data Reading (Core Abstract Methods)**

```python
def read_bms_data(self) -> Optional[Dict[str, Any]]:
    """
    Read live BMS data and return standardized dictionary.
    
    This is the main method that reads all dynamic BMS data.
    """
    if not self.is_connected:
        self.logger.error("Cannot read BMS data - not connected")
        return None
    
    try:
        # Read telemetry data (voltages, currents, temperatures, etc.)
        telemetry_data = self._read_telemetry_data()
        if not telemetry_data:
            return None
        
        # Read status/alarm data
        status_data = self._read_status_data()
        if not status_data:
            return None
        
        # Combine and standardize the data
        combined_data = {**telemetry_data, **status_data}
        standardized_data = self._standardize_bms_data(combined_data)
        
        # Update cache and timestamp
        self.latest_data_cache = standardized_data.copy()
        standardized_data[BMS_PLUGIN_LAST_UPDATE] = datetime.now(timezone.utc).isoformat()
        
        return standardized_data
        
    except Exception as e:
        self.logger.error(f"Error reading BMS data: {e}", exc_info=True)
        return None

def get_bms_static_info(self) -> Optional[Dict[str, Any]]:
    """
    Read static BMS information (model, serial, firmware, etc.).
    
    This method reads device identification and configuration data.
    """
    if not self.is_connected:
        self.logger.error("Cannot read static info - not connected")
        return None
    
    try:
        # Read device information
        device_info = self._read_device_info()
        if not device_info:
            return None
        
        # Standardize static data
        static_data = {
            BMS_KEY_MANUFACTURER: device_info.get("manufacturer", "[Your BMS Brand]"),
            BMS_KEY_MODEL: device_info.get("model", UNKNOWN),
            BMS_KEY_SERIAL_NUMBER: device_info.get("serial_number", UNKNOWN),
            BMS_KEY_FIRMWARE_VERSION: device_info.get("firmware_version", UNKNOWN),
            BMS_KEY_HARDWARE_VERSION: device_info.get("hardware_version", UNKNOWN),
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms"
        }
        
        return static_data
        
    except Exception as e:
        self.logger.error(f"Error reading static info: {e}", exc_info=True)
        return None
```

### **3. Protocol-Specific Communication**

```python
def _read_telemetry_data(self) -> Optional[Dict[str, Any]]:
    """Read telemetry data from BMS."""
    try:
        # Send telemetry request command
        command = self._build_telemetry_command()
        response = self._send_command_and_get_response(command)
        
        if not response:
            return None
        
        # Parse the response
        parsed_data = self._parse_telemetry_response(response)
        return parsed_data
        
    except Exception as e:
        self.logger.error(f"Error reading telemetry: {e}")
        return None

def _read_status_data(self) -> Optional[Dict[str, Any]]:
    """Read status/alarm data from BMS."""
    try:
        # Send status request command
        command = self._build_status_command()
        response = self._send_command_and_get_response(command)
        
        if not response:
            return None
        
        # Parse the response
        parsed_data = self._parse_status_response(response)
        return parsed_data
        
    except Exception as e:
        self.logger.error(f"Error reading status: {e}")
        return None

def _send_command_and_get_response(self, command: bytes) -> Optional[bytes]:
    """Send command and receive response."""
    try:
        if self.connection_type == "serial":
            return self._send_serial_command(command)
        elif self.connection_type == "tcp":
            return self._send_tcp_command(command)
        else:
            self.logger.error(f"Unsupported connection type: {self.connection_type}")
            return None
            
    except Exception as e:
        self.logger.error(f"Communication error: {e}")
        return None

def _send_serial_command(self, command: bytes) -> Optional[bytes]:
    """Send command via serial connection."""
    if not self.serial_connection or not self.serial_connection.is_open:
        self.logger.error("Serial connection not available")
        return None
    
    try:
        # Clear input buffer
        self.serial_connection.reset_input_buffer()
        
        # Send command
        self.serial_connection.write(command)
        self.serial_connection.flush()
        
        # Add inter-command delay
        if self.inter_command_delay_ms > 0:
            time.sleep(self.inter_command_delay_ms / 1000.0)
        
        # Read response
        response = self.serial_connection.read_until(b'\r')  # Adjust terminator as needed
        
        if not response:
            self.logger.warning("No response received from BMS")
            return None
        
        return response
        
    except SerialException as e:
        self.logger.error(f"Serial communication error: {e}")
        return None

def _send_tcp_command(self, command: bytes) -> Optional[bytes]:
    """Send command via TCP connection."""
    if not self.tcp_socket:
        self.logger.error("TCP connection not available")
        return None
    
    try:
        # Send command
        self.tcp_socket.sendall(command)
        
        # Add inter-command delay
        if self.inter_command_delay_ms > 0:
            time.sleep(self.inter_command_delay_ms / 1000.0)
        
        # Read response
        response = self.tcp_socket.recv(4096)  # Adjust buffer size as needed
        
        if not response:
            self.logger.warning("No response received from BMS")
            return None
        
        return response
        
    except socket.error as e:
        self.logger.error(f"TCP communication error: {e}")
        return None
```

### **4. Data Parsing and Standardization**

```python
def _parse_telemetry_response(self, response: bytes) -> Optional[Dict[str, Any]]:
    """Parse telemetry response into raw data dictionary."""
    try:
        # Convert response to appropriate format (hex, ASCII, binary, etc.)
        # This is protocol-specific - implement based on your BMS protocol
        
        parsed_data = {}
        
        # Example parsing (adjust for your protocol):
        # parsed_data["pack_voltage"] = self._extract_voltage(response, offset=10)
        # parsed_data["pack_current"] = self._extract_current(response, offset=14)
        # parsed_data["soc"] = self._extract_soc(response, offset=18)
        # parsed_data["cell_voltages"] = self._extract_cell_voltages(response, start_offset=20)
        # parsed_data["temperatures"] = self._extract_temperatures(response, start_offset=50)
        
        return parsed_data
        
    except Exception as e:
        self.logger.error(f"Error parsing telemetry response: {e}")
        return None

def _parse_status_response(self, response: bytes) -> Optional[Dict[str, Any]]:
    """Parse status response into raw data dictionary."""
    try:
        # Parse status flags, alarms, warnings, etc.
        # This is protocol-specific
        
        parsed_data = {}
        
        # Example parsing:
        # parsed_data["charge_fet_on"] = self._extract_bit_flag(response, byte=5, bit=0)
        # parsed_data["discharge_fet_on"] = self._extract_bit_flag(response, byte=5, bit=1)
        # parsed_data["alarms"] = self._extract_alarm_flags(response, start_byte=10)
        # parsed_data["warnings"] = self._extract_warning_flags(response, start_byte=15)
        
        return parsed_data
        
    except Exception as e:
        self.logger.error(f"Error parsing status response: {e}")
        return None

def _standardize_bms_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert raw BMS data to standardized format."""
    standardized = {}
    
    # Core battery data
    standardized[BMS_KEY_VOLTAGE] = self._validate_voltage(raw_data.get("pack_voltage"))
    standardized[BMS_KEY_CURRENT] = self._validate_current(raw_data.get("pack_current"))
    standardized[BMS_KEY_POWER] = self._calculate_power(
        standardized[BMS_KEY_VOLTAGE], 
        standardized[BMS_KEY_CURRENT]
    )
    standardized[BMS_KEY_SOC] = self._validate_soc(raw_data.get("soc"))
    standardized[BMS_KEY_SOH] = self._validate_soh(raw_data.get("soh"))
    
    # Cell data
    cell_voltages = raw_data.get("cell_voltages", [])
    if cell_voltages:
        validated_cells = [self._validate_cell_voltage(v) for v in cell_voltages]
        valid_cells = [v for v in validated_cells if v is not None]
        
        if valid_cells:
            standardized[BMS_KEY_CELL_COUNT] = len(valid_cells)
            standardized[BMS_KEY_CELL_VOLTAGES_ALL] = valid_cells
            standardized[BMS_KEY_CELL_VOLTAGE_MIN] = min(valid_cells)
            standardized[BMS_KEY_CELL_VOLTAGE_MAX] = max(valid_cells)
            standardized[BMS_KEY_CELL_VOLTAGE_AVG] = sum(valid_cells) / len(valid_cells)
            standardized[BMS_KEY_CELL_VOLTAGE_DIFF] = max(valid_cells) - min(valid_cells)
            
            # Individual cell voltages
            for i, voltage in enumerate(valid_cells):
                standardized[f"{BMS_KEY_CELL_VOLTAGE_PREFIX}{i+1}"] = voltage
    
    # Temperature data
    temperatures = raw_data.get("temperatures", [])
    if temperatures:
        validated_temps = [self._validate_temperature(t) for t in temperatures]
        valid_temps = [t for t in validated_temps if t is not None]
        
        if valid_temps:
            standardized[BMS_KEY_TEMPERATURES_ALL] = valid_temps
            standardized[BMS_KEY_TEMP_MIN] = min(valid_temps)
            standardized[BMS_KEY_TEMP_MAX] = max(valid_temps)
            
            # Individual temperature sensors
            for i, temp in enumerate(valid_temps):
                standardized[f"{BMS_KEY_TEMP_SENSOR_PREFIX}{i+1}"] = temp
    
    # Status and control
    standardized[BMS_KEY_CHARGE_FET_ON] = raw_data.get("charge_fet_on", False)
    standardized[BMS_KEY_DISCHARGE_FET_ON] = raw_data.get("discharge_fet_on", False)
    
    # Process alarms and warnings
    alarms = raw_data.get("alarms", [])
    warnings = raw_data.get("warnings", [])
    
    standardized[BMS_KEY_ACTIVE_ALARMS_LIST] = alarms
    standardized[BMS_KEY_ACTIVE_WARNINGS_LIST] = warnings
    
    # Generate status text
    standardized[BMS_KEY_STATUS_TEXT] = self._generate_status_text(raw_data)
    
    # Generate fault summary
    if alarms or warnings:
        fault_summary = f"{len(alarms)} alarms, {len(warnings)} warnings"
    else:
        fault_summary = "Normal"
    standardized[BMS_KEY_FAULT_SUMMARY] = fault_summary
    
    return standardized
```

### **5. Data Validation Methods**

```python
def _validate_voltage(self, value: Any) -> Optional[float]:
    """Validate and return voltage value."""
    if not isinstance(value, (int, float)):
        return None
    
    voltage = float(value)
    if 0 <= voltage <= 1000:  # Reasonable range for pack voltage
        return voltage
    return None

def _validate_current(self, value: Any) -> Optional[float]:
    """Validate and return current value."""
    if not isinstance(value, (int, float)):
        return None
    
    current = float(value)
    if -1000 <= current <= 1000:  # Reasonable range for pack current
        return current
    return None

def _validate_cell_voltage(self, value: Any) -> Optional[float]:
    """Validate and return cell voltage value."""
    if not isinstance(value, (int, float)):
        return None
    
    voltage = float(value)
    if MIN_VALID_CELL_V <= voltage <= MAX_VALID_CELL_V:
        return voltage
    return None

def _validate_temperature(self, value: Any) -> Optional[float]:
    """Validate and return temperature value."""
    if not isinstance(value, (int, float)):
        return None
    
    temp = float(value)
    if MIN_VALID_TEMP_C <= temp <= MAX_VALID_TEMP_C:
        return temp
    return None

def _validate_soc(self, value: Any) -> Optional[float]:
    """Validate and return SOC value."""
    if not isinstance(value, (int, float)):
        return None
    
    soc = float(value)
    if MIN_VALID_SOC <= soc <= MAX_VALID_SOC:
        return soc
    return None

def _validate_soh(self, value: Any) -> Optional[float]:
    """Validate and return SOH value."""
    if not isinstance(value, (int, float)):
        return None
    
    soh = float(value)
    if MIN_VALID_SOH <= soh <= MAX_VALID_SOH:
        return soh
    return None

def _calculate_power(self, voltage: Optional[float], current: Optional[float]) -> Optional[float]:
    """Calculate power from voltage and current."""
    if voltage is not None and current is not None:
        return voltage * current
    return None

def _generate_status_text(self, raw_data: Dict[str, Any]) -> str:
    """Generate human-readable status text."""
    alarms = raw_data.get("alarms", [])
    warnings = raw_data.get("warnings", [])
    
    if alarms:
        return f"Alarm: {alarms[0]}"  # Show first alarm
    elif warnings:
        return f"Warning: {warnings[0]}"  # Show first warning
    else:
        return "Normal"
```

---

## 📊 **Configuration Parameters**

```python
@staticmethod
def get_configurable_params() -> List[Dict[str, Any]]:
    """Define configuration parameters for this BMS plugin."""
    return [
        {
            "name": "connection_type",
            "type": "select",
            "options": ["serial", "tcp"],
            "default": "serial",
            "description": "Connection type (Serial or TCP)"
        },
        {
            "name": "serial_port",
            "type": "string",
            "default": "/dev/ttyUSB0",
            "description": "Serial port path"
        },
        {
            "name": "baud_rate",
            "type": "integer",
            "default": DEFAULT_BAUD_RATE,
            "description": "Serial baud rate"
        },
        {
            "name": "serial_timeout",
            "type": "float",
            "default": 2.0,
            "description": "Serial communication timeout (seconds)"
        },
        {
            "name": "tcp_host",
            "type": "string",
            "default": "192.168.1.100",
            "description": "TCP host IP address"
        },
        {
            "name": "tcp_port",
            "type": "integer",
            "default": DEFAULT_TCP_PORT,
            "description": "TCP port number"
        },
        {
            "name": "tcp_timeout",
            "type": "float",
            "default": DEFAULT_TCP_TIMEOUT_SECONDS,
            "description": "TCP communication timeout (seconds)"
        },
        {
            "name": "pack_address",
            "type": "integer",
            "default": 0,
            "description": "BMS pack address (for multi-pack systems)"
        },
        {
            "name": "inter_command_delay_ms",
            "type": "integer",
            "default": 100,
            "description": "Delay between commands (milliseconds)"
        },
        {
            "name": "max_retries",
            "type": "integer",
            "default": 3,
            "description": "Maximum communication retry attempts"
        }
    ]
```

---

## ✅ **Implementation Checklist**

### **Phase 1: Basic Structure**
- [ ] Create main plugin class inheriting from `BMSPluginBase`
- [ ] Implement `__init__` method with connection parameter initialization
- [ ] Implement `name` and `pretty_name` properties
- [ ] Implement `get_configurable_params()` method

### **Phase 2: Connection Management**
- [ ] Implement `connect()` method with Serial/TCP support
- [ ] Implement `disconnect()` method
- [ ] Add connection validation and error handling
- [ ] Test connection establishment with actual hardware

### **Phase 3: Protocol Implementation**
- [ ] Implement command building methods
- [ ] Implement communication methods (`_send_command_and_get_response`)
- [ ] Implement response parsing methods
- [ ] Test basic communication with BMS

### **Phase 4: Data Processing**
- [ ] Implement `read_bms_data()` method
- [ ] Implement `get_bms_static_info()` method
- [ ] Implement data validation methods
- [ ] Implement data standardization methods
- [ ] Test data accuracy and validation

### **Phase 5: Testing & Refinement**
- [ ] Test with actual BMS hardware
- [ ] Validate all data fields and ranges
- [ ] Test error handling and recovery
- [ ] Optimize communication timing
- [ ] Document protocol quirks and special handling

---

## 🎯 **Key Design Principles**

### **1. Inherit from BMSPluginBase**
- Always extend `BMSPluginBase` for consistency
- Use standardized data keys from the base class
- Leverage built-in alert categorization

### **2. Robust Communication**
- Support both Serial and TCP connections
- Implement proper timeouts and retries
- Handle connection failures gracefully
- Add appropriate delays between commands

### **3. Data Validation**
- Validate all incoming data against reasonable ranges
- Handle invalid/missing data gracefully
- Provide meaningful error messages
- Use consistent validation patterns

### **4. Standardized Output**
- Always map to StandardDataKeys enum values
- Provide individual cell voltages and temperatures
- Calculate derived values (min/max/average/delta)
- Generate human-readable status text

### **5. Error Handling**
- Never crash on communication errors
- Log errors with sufficient context
- Provide fallback values when appropriate
- Maintain connection state properly

---

## 📚 **Additional Resources**

- **BMS Plugin Base**: `plugins/battery/bms_plugin_base.py`
- **Standard Data Keys**: `plugins/plugin_interface.py` (StandardDataKeys enum)
- **Plugin Utils**: `plugins/plugin_utils.py` (network checking utilities)
- **Reference Implementation**: `plugins/battery/seplos_bms_v2_plugin.py`

---

## 🚀 **Getting Started**

1. **Study the Seplos V2 plugin** - Understand the proven patterns
2. **Gather your BMS documentation** - Protocol specifications, command formats
3. **Implement the plugin class** - Follow the established patterns
4. **Test incrementally** - Start with connection, then static data, then dynamic data
5. **Validate thoroughly** - Test all data fields and error conditions
6. **Refine and optimize** - Adjust timing and validation based on real-world testing

This reference ensures consistency, reliability, and maintainability across all BMS plugins in the Solar Monitoring Framework.