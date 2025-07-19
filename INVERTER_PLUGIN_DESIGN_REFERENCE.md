# Inverter Plugin Design Reference

## Based on the Stable Solis Plugin Architecture

This document serves as the definitive reference for creating new inverter plugins in the Solar Monitoring Framework. It is based on the proven, stable design of the **Solis Modbus Plugin**, which has been thoroughly tested and refined.

## 🏗️ **Core Architecture Pattern**

### **File Structure**
Every inverter plugin should follow this two-file pattern:
```
plugins/inverter/
├── your_inverter_plugin.py          # Main plugin class
└── your_inverter_plugin_constants.py # Register maps and constants
```

### **Why This Pattern Works**
- **Separation of Concerns**: Logic separate from data definitions
- **Maintainability**: Easy to update register maps without touching core logic
- **Readability**: Clean, focused code files
- **Extensibility**: Simple to add new registers or modify mappings

---

## 📋 **Constants File Structure**

### **File: `your_inverter_plugin_constants.py`**

```python
"""
Constants and register definitions for [Your Inverter] plugin.
"""
from typing import Any, Dict, List

# --- Register Definitions ---
YOUR_INVERTER_REGISTERS: Dict[str, Dict[str, Any]] = {
    # Static registers (read once at startup)
    "model_number": {
        "key": "model_number", 
        "addr": 40001, 
        "type": "uint16", 
        "scale": 1, 
        "unit": "Code", 
        "static": True
    },
    "serial_number": {
        "key": "serial_number", 
        "addr": 40002, 
        "type": "string_read8", 
        "scale": 1, 
        "unit": None, 
        "static": True
    },
    
    # Dynamic registers (read periodically)
    "dc_voltage_1": {
        "key": "dc_voltage_1", 
        "addr": 40100, 
        "type": "uint16", 
        "scale": 0.1, 
        "unit": "V", 
        "poll_priority": "critical"
    },
    "active_power": {
        "key": "active_power", 
        "addr": 40101, 
        "type": "int32", 
        "scale": 1, 
        "unit": "W", 
        "poll_priority": "critical"
    },
    # ... more registers
}

# --- Status Code Mappings ---
YOUR_INVERTER_STATUS_CODES: Dict[int, str] = {
    0: "Standby",
    1: "Normal",
    2: "Fault",
    # ... more status codes
}

# --- Fault/Alert Bitfield Mappings ---
YOUR_INVERTER_FAULT_BITFIELD_MAPS: Dict[int, Dict[str, Any]] = {
    40200: {  # Fault register address
        "category": "grid",
        "bits": {
            0: "Grid Overvoltage",
            1: "Grid Undervoltage", 
            2: "Grid Overfrequency",
            # ... more fault bits
        }
    }
}

# --- Alert Categories ---
ALERT_CATEGORIES: List[str] = ["status", "grid", "battery", "inverter", "bms"]

# --- Model Code Mappings ---
YOUR_INVERTER_MODEL_CODES: Dict[int, str] = {
    0x01: "Model ABC-5K",
    0x02: "Model XYZ-10K",
    # ... more model codes
}
```

### **Key Register Definition Fields**

| Field | Required | Description | Example Values |
|-------|----------|-------------|----------------|
| `key` | ✅ | Unique identifier | `"dc_voltage_1"` |
| `addr` | ✅ | Modbus register address | `40001` |
| `type` | ✅ | Data type | `"uint16"`, `"int32"`, `"string_read8"` |
| `scale` | ✅ | Scaling factor | `0.1`, `1`, `0.01` |
| `unit` | ✅ | Unit of measurement | `"V"`, `"W"`, `"Code"`, `None` |
| `static` | ❌ | Read only at startup | `true` (default: `false`) |
| `poll_priority` | ❌ | Polling importance | `"critical"`, `"summary"` |
| `reg_func_type` | ❌ | Modbus function type | `"input"` (default), `"holding"` |

### **Supported Data Types**
- `uint16` - Unsigned 16-bit integer (1 register)
- `int16` - Signed 16-bit integer (1 register)  
- `uint32` - Unsigned 32-bit integer (2 registers)
- `int32` - Signed 32-bit integer (2 registers)
- `string_read8` - 8-register ASCII string (16 bytes)
- `Code` - Status/enum code (1 register, no scaling)
- `Bitfield` - Bit flags for alerts (1 register, no scaling)
- `Hex` - Hexadecimal value (1 register, no scaling)

---

## 🔧 **Main Plugin Class Structure**

### **File: `your_inverter_plugin.py`**

```python
import time
import struct
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.app_state import AppState

# Import your constants
from .your_inverter_plugin_constants import (
    YOUR_INVERTER_REGISTERS,
    YOUR_INVERTER_STATUS_CODES,
    YOUR_INVERTER_FAULT_BITFIELD_MAPS,
    ALERT_CATEGORIES,
    YOUR_INVERTER_MODEL_CODES
)

from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from plugins.plugin_utils import check_tcp_port, check_icmp_ping
from utils.helpers import FULLY_OPERATIONAL_STATUSES

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException, ModbusIOException, ConnectionException as ModbusConnectionException
from pymodbus.pdu import ExceptionResponse

# Constants
ERROR_READ = "read_error"
ERROR_DECODE = "decode_error"
UNKNOWN = "Unknown"

class ConnectionType(str, Enum):
    """Enumeration for supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"

class YourInverterPlugin(DevicePlugin):
    """Plugin for [Your Inverter Brand] inverters via Modbus TCP/Serial."""
    
    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], 
                 main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        # Initialize connection parameters
        self._init_connection_params()
        
        # Initialize register maps
        self._init_register_maps()
        
        # Initialize communication parameters
        self._init_communication_params()
        
        # Plugin state
        self.last_error_message: Optional[str] = None
        self.last_known_dynamic_data: Dict[str, Any] = {}
        self.plugin_init_time = time.monotonic()
        
        self.logger.info(f"[Your Inverter] Plugin '{self.instance_name}': Initialized")

    def _init_connection_params(self):
        """Initialize connection-related parameters."""
        try:
            self.connection_type = ConnectionType(
                self.plugin_config.get("connection_type", "tcp").strip().lower()
            )
        except ValueError:
            self.logger.warning(f"Invalid connection_type. Defaulting to TCP.")
            self.connection_type = ConnectionType.TCP
            
        # TCP parameters
        self.tcp_host = self.plugin_config.get("tcp_host", "127.0.0.1")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 502))
        
        # Serial parameters  
        self.serial_port = self.plugin_config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = int(self.plugin_config.get("baud_rate", 9600))
        
        # Common parameters
        self.slave_address = int(self.plugin_config.get("slave_address", 1))

    def _init_register_maps(self):
        """Initialize register maps for static and dynamic data."""
        self.static_registers_map = {
            k: v for k, v in YOUR_INVERTER_REGISTERS.items() 
            if v.get("static") and 'addr' in v
        }
        self.dynamic_registers_map = {
            k: v for k, v in YOUR_INVERTER_REGISTERS.items() 
            if not v.get("static") and 'addr' in v
        }

    def _init_communication_params(self):
        """Initialize Modbus communication parameters."""
        # Default values
        DEFAULT_MODBUS_TIMEOUT_S = 10
        DEFAULT_INTER_READ_DELAY_MS = 500
        DEFAULT_MAX_REGS_PER_READ = 60
        
        # Load from config with defaults
        self.modbus_timeout_seconds = int(
            self.plugin_config.get("modbus_timeout_seconds", DEFAULT_MODBUS_TIMEOUT_S)
        )
        self.inter_read_delay_ms = int(
            self.plugin_config.get("inter_read_delay_ms", DEFAULT_INTER_READ_DELAY_MS)
        )
        self.max_regs_per_read = int(
            self.plugin_config.get("max_regs_per_read", DEFAULT_MAX_REGS_PER_READ)
        )
        self.max_read_retries_per_group = int(
            self.plugin_config.get("max_read_retries_per_group", 2)
        )
        
        # Build read groups
        self.dynamic_read_groups = self._build_modbus_read_groups(
            list(self.dynamic_registers_map.items()), 
            self.max_regs_per_read
        )

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "your_inverter_modbus"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "[Your Inverter Brand] Modbus Inverter"

    # ... implement all required methods following Solis pattern
```

---

## 🔑 **Required Method Implementations**

### **1. Connection Management**

```python
def connect(self) -> bool:
    """Establish connection to the inverter."""
    if self._is_connected_flag and self.client:
        return True
        
    if self.client:
        self.disconnect()
        
    self.last_error_message = None
    
    # Pre-connection checks for TCP
    if self.connection_type == ConnectionType.TCP:
        port_open, rtt_ms, err_msg = check_tcp_port(
            self.tcp_host, self.tcp_port, logger_instance=self.logger
        )
        if not port_open:
            self.last_error_message = f"TCP port check failed: {err_msg}"
            self.logger.error(self.last_error_message)
            return False
    
    # Create and connect client
    try:
        if self.connection_type == ConnectionType.SERIAL:
            self.client = ModbusSerialClient(
                port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=self.modbus_timeout_seconds
            )
        else:  # TCP
            self.client = ModbusTcpClient(
                host=self.tcp_host,
                port=self.tcp_port,
                timeout=self.modbus_timeout_seconds
            )
        
        if self.client.connect():
            self._is_connected_flag = True
            self.logger.info(f"Successfully connected to {self.connection_type.value}")
            return True
        else:
            self.last_error_message = "Client connect() returned False"
            
    except Exception as e:
        self.last_error_message = f"Connection exception: {e}"
        self.logger.error(self.last_error_message, exc_info=True)
    
    # Cleanup on failure
    if self.client:
        self.client.close()
    self.client = None
    self._is_connected_flag = False
    return False

def disconnect(self) -> None:
    """Close the Modbus connection."""
    if self.client:
        try:
            self.client.close()
        except Exception as e:
            self.logger.error(f"Error closing connection: {e}")
    self._is_connected_flag = False
    self.client = None
```

### **2. Data Reading and Decoding**

```python
@staticmethod
def _plugin_decode_register(registers: List[int], info: Dict[str, Any], 
                          logger_instance: logging.Logger) -> Tuple[Any, Optional[str]]:
    """Decode raw register values into scaled Python objects."""
    reg_type = info.get("type", "unknown")
    scale = float(info.get("scale", 1.0))
    unit = info.get("unit")
    key_name = info.get('key', 'Unknown')
    
    try:
        if not registers:
            raise ValueError("No registers provided")
            
        # Decode based on type
        if reg_type == "uint16":
            value = registers[0]
        elif reg_type == "int16":
            value = struct.unpack('>h', registers[0].to_bytes(2, 'big'))[0]
        elif reg_type == "uint32":
            value = struct.unpack('>I', b''.join(r.to_bytes(2, 'big') for r in registers[:2]))[0]
        elif reg_type == "int32":
            value = struct.unpack('>i', b''.join(r.to_bytes(2, 'big') for r in registers[:2]))[0]
        elif reg_type == "string_read8":
            byte_data = b''.join(reg.to_bytes(2, 'big') for reg in registers[:8])
            value = byte_data.rstrip(b'\x00 \t\r\n').decode('ascii', errors='ignore')
        elif reg_type in ["Code", "Bitfield", "Hex"]:
            value = registers[0]  # No scaling for codes/bitfields
        else:
            raise ValueError(f"Unsupported type: {reg_type}")
        
        # Apply scaling for numeric values (except codes/bitfields)
        if isinstance(value, (int, float)):
            should_scale = (abs(scale - 1.0) > 1e-9) and (unit not in ["Bitfield", "Code", "Hex"])
            final_value = float(value) * scale if should_scale else value
            return final_value, unit
        else:
            return value, unit
            
    except Exception as e:
        logger_instance.error(f"Decode error for '{key_name}' ({reg_type}): {e}")
        return ERROR_DECODE, unit

@staticmethod
def _plugin_get_register_count(reg_type: str, logger_instance: logging.Logger) -> int:
    """Get number of registers required for a data type."""
    if reg_type in ["uint32", "int32"]:
        return 2
    elif reg_type in ["uint16", "int16", "Code", "Bitfield", "Hex"]:
        return 1
    elif reg_type == "string_read8":
        return 8
    else:
        logger_instance.warning(f"Unknown register type '{reg_type}', assuming 1")
        return 1
```

### **3. Register Group Building**

```python
def _build_modbus_read_groups(self, register_list_tuples: List[Tuple[str, Dict[str, Any]]], 
                            max_regs_per_read: int) -> List[Dict[str, Any]]:
    """Group registers into efficient Modbus read operations."""
    groups = []
    if not register_list_tuples:
        return groups
    
    # Sort by register function type and address
    sorted_regs = sorted(
        register_list_tuples, 
        key=lambda item: (item[1].get('reg_func_type', 'input'), item[1]['addr'])
    )
    
    current_group = None
    max_gap = int(self.plugin_config.get("modbus_max_register_gap", 10))
    
    for key, info in sorted_regs:
        addr = info['addr']
        count = self._plugin_get_register_count(info["type"], self.logger)
        reg_func_type = info.get('reg_func_type', 'input')
        
        # Determine if we need a new group
        is_new_group = (
            current_group is None or
            reg_func_type != current_group['reg_func_type'] or
            addr >= current_group['start'] + current_group['count'] + max_gap or
            (addr + count - current_group['start'] > max_regs_per_read)
        )
        
        if is_new_group:
            if current_group:
                groups.append(current_group)
            current_group = {
                "start": addr,
                "count": count,
                "keys": [key],
                "reg_func_type": reg_func_type
            }
        else:
            current_group['count'] = (addr + count) - current_group['start']
            current_group['keys'].append(key)
    
    if current_group:
        groups.append(current_group)
    
    return groups
```

### **4. Data Standardization**

```python
def read_static_data(self) -> Optional[Dict[str, Any]]:
    """Read static device information."""
    if not self.is_connected:
        self.logger.error("Cannot read static data - not connected")
        return None
    
    # Read static registers
    static_items = list(self.static_registers_map.items())
    static_groups = self._build_modbus_read_groups(static_items, self.max_regs_per_read)
    raw_static = self._read_registers_from_groups(static_groups)
    
    if raw_static is None:
        self.logger.error("Failed to read static data")
        return None
    
    # Standardize the data
    standardized_data = {
        StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
        StandardDataKeys.STATIC_INVERTER_MANUFACTURER: "[Your Brand]",
        StandardDataKeys.STATIC_INVERTER_MODEL_NAME: self._decode_model_name(
            raw_static.get("model_number")
        ),
        StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: str(
            raw_static.get("serial_number", UNKNOWN)
        ),
        StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION: self._decode_firmware_version(
            raw_static.get("firmware_version")
        ),
        StandardDataKeys.STATIC_NUMBER_OF_MPPTS: self._detect_mppt_count(raw_static),
        StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: self._detect_phase_count(raw_static),
    }
    
    return standardized_data

def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
    """Read live operational data."""
    if not self.is_connected:
        self.logger.error("Cannot read dynamic data - not connected")
        return None
    
    # Read dynamic registers
    raw_dynamic = self._read_registers_from_groups(self.dynamic_read_groups)
    if raw_dynamic is None:
        return None
    
    # Standardize the data
    standardized_data = {}
    
    # Power values
    standardized_data[StandardDataKeys.PV_TOTAL_DC_POWER_WATTS] = raw_dynamic.get("total_dc_power", 0)
    standardized_data[StandardDataKeys.INVERTER_AC_POWER_WATTS] = raw_dynamic.get("active_power", 0)
    standardized_data[StandardDataKeys.GRID_POWER_WATTS] = raw_dynamic.get("grid_power", 0)
    standardized_data[StandardDataKeys.BATTERY_POWER_WATTS] = raw_dynamic.get("battery_power", 0)
    standardized_data[StandardDataKeys.LOAD_TOTAL_POWER_WATTS] = raw_dynamic.get("load_power", 0)
    
    # Voltage/Current values
    standardized_data[StandardDataKeys.PV_VOLTAGE_1_VOLTS] = raw_dynamic.get("dc_voltage_1", 0)
    standardized_data[StandardDataKeys.PV_CURRENT_1_AMPS] = raw_dynamic.get("dc_current_1", 0)
    standardized_data[StandardDataKeys.GRID_VOLTAGE_L1_VOLTS] = raw_dynamic.get("grid_voltage_l1", 0)
    standardized_data[StandardDataKeys.BATTERY_VOLTAGE_VOLTS] = raw_dynamic.get("battery_voltage", 0)
    standardized_data[StandardDataKeys.BATTERY_CURRENT_AMPS] = raw_dynamic.get("battery_current", 0)
    
    # Energy values
    standardized_data[StandardDataKeys.PV_ENERGY_TODAY_KWH] = raw_dynamic.get("energy_today", 0)
    standardized_data[StandardDataKeys.PV_ENERGY_TOTAL_KWH] = raw_dynamic.get("energy_total", 0)
    
    # Status and operational data
    standardized_data[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT] = self._decode_status(
        raw_dynamic.get("current_status")
    )
    standardized_data[StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS] = raw_dynamic.get("inverter_temp", 0)
    standardized_data[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT] = raw_dynamic.get("battery_soc", 0)
    
    # Process alerts/faults
    fault_codes, categorized_alerts = self._decode_alerts(raw_dynamic)
    standardized_data[StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_CODES_LIST] = fault_codes
    standardized_data[StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT] = categorized_alerts
    
    return standardized_data
```

---

## 📊 **Configuration Parameters**

### **Required Configuration Parameters**

```python
def get_configurable_params() -> List[Dict[str, Any]]:
    """Define configuration parameters for this plugin."""
    return [
        {
            "name": "connection_type",
            "type": "select",
            "options": ["tcp", "serial"],
            "default": "tcp",
            "description": "Connection type (TCP or Serial)"
        },
        {
            "name": "tcp_host",
            "type": "string",
            "default": "192.168.1.100",
            "description": "IP address for TCP connection"
        },
        {
            "name": "tcp_port", 
            "type": "integer",
            "default": 502,
            "description": "Port for TCP connection"
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
            "default": 9600,
            "description": "Serial baud rate"
        },
        {
            "name": "slave_address",
            "type": "integer",
            "default": 1,
            "description": "Modbus slave address"
        },
        {
            "name": "modbus_timeout_seconds",
            "type": "integer", 
            "default": 10,
            "description": "Modbus communication timeout"
        },
        {
            "name": "inter_read_delay_ms",
            "type": "integer",
            "default": 500,
            "description": "Delay between register reads (ms)"
        },
        {
            "name": "max_regs_per_read",
            "type": "integer",
            "default": 60,
            "description": "Maximum registers per read operation"
        }
    ]
```

---

## ✅ **Implementation Checklist**

### **Phase 1: Basic Structure**
- [ ] Create constants file with register definitions
- [ ] Create main plugin class inheriting from `DevicePlugin`
- [ ] Implement `__init__` method with parameter initialization
- [ ] Implement `name` and `pretty_name` properties
- [ ] Implement `get_configurable_params()` method

### **Phase 2: Connection Management**
- [ ] Implement `connect()` method with TCP/Serial support
- [ ] Implement `disconnect()` method
- [ ] Add pre-connection checks for TCP
- [ ] Add proper error handling and logging

### **Phase 3: Data Processing**
- [ ] Implement `_plugin_decode_register()` static method
- [ ] Implement `_plugin_get_register_count()` static method  
- [ ] Implement `_build_modbus_read_groups()` method
- [ ] Implement `_read_registers_from_groups()` method

### **Phase 4: Data Standardization**
- [ ] Implement `read_static_data()` method
- [ ] Implement `read_dynamic_data()` method
- [ ] Map all raw values to `StandardDataKeys`
- [ ] Implement status/model/alert decoding methods

### **Phase 5: Testing & Refinement**
- [ ] Test with actual hardware
- [ ] Optimize register grouping and timing
- [ ] Add device-specific features
- [ ] Document any quirks or special handling

---

## 🎯 **Key Design Principles**

### **1. Robust Error Handling**
- Always check connection status before operations
- Implement retry logic for transient failures
- Gracefully handle decode errors
- Log errors with sufficient context

### **2. Efficient Communication**
- Group registers to minimize Modbus requests
- Use appropriate delays between reads
- Implement configurable timeouts
- Support both TCP and Serial connections

### **3. Data Standardization**
- Always map to `StandardDataKeys` enum values
- Handle missing/invalid data gracefully
- Provide meaningful status text
- Categorize alerts appropriately

### **4. Configuration Flexibility**
- Support both TCP and Serial connections
- Make communication parameters configurable
- Provide sensible defaults
- Allow fine-tuning for different network conditions

### **5. Maintainability**
- Separate constants from logic
- Use clear, descriptive method names
- Document complex register mappings
- Follow consistent coding patterns

---

## 📚 **Additional Resources**

- **Base Plugin Interface**: `plugins/plugin_interface.py`
- **Standard Data Keys**: `plugins/plugin_interface.py` (StandardDataKeys enum)
- **Plugin Utils**: `plugins/plugin_utils.py` (network checking utilities)
- **Reference Implementation**: `plugins/inverter/solis_modbus_plugin.py`

---

## 🚀 **Getting Started**

1. **Study the Solis plugin** - Understand the proven patterns
2. **Gather your inverter's documentation** - Register maps, Modbus specifications
3. **Create the constants file** - Define all registers and mappings
4. **Implement the plugin class** - Follow the established patterns
5. **Test incrementally** - Start with connection, then static data, then dynamic data
6. **Refine and optimize** - Adjust timing and grouping based on real-world testing

This reference ensures consistency, reliability, and maintainability across all inverter plugins in the Solar Monitoring Framework.