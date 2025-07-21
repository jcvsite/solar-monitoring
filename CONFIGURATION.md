# Configuration Guide

This guide covers all configuration options for the Solar Monitoring Framework, including plugin-specific settings and advanced configuration.

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration File Structure](#configuration-file-structure)
- [General Settings](#general-settings)
- [System Configuration](#system-configuration)
- [Plugin Configuration](#plugin-configuration)
- [Service Configuration](#service-configuration)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

## Quick Start

1. **Copy Example Configuration**:
   ```bash
   cp config.ini.example config.ini
   ```

2. **Edit Basic Settings**:
   - Set your timezone in `[GENERAL]` section
   - Configure your plugins in `[PLUGIN_*]` sections
   - Enable desired services (MQTT, Web Dashboard, etc.)

3. **Test Configuration**:
   ```bash
   python test_plugins/validate_all_plugins.py --offline-only
   ```

## Configuration File Structure

The `config.ini` file is organized into logical sections:

```ini
[GENERAL]                    # Core application settings
[INVERTER_SYSTEM]           # Physical system specifications
[PLUGIN_*]                  # Individual plugin configurations
[LOGGING]                   # Logging configuration
[MQTT]                      # MQTT/Home Assistant integration
[WEB_DASHBOARD]             # Web interface settings
[DATABASE]                  # Data storage settings
[FILTER]                    # Data filtering and validation
# ... additional service sections
```

## General Settings

### `[GENERAL]` Section

```ini
[GENERAL]
# List of plugin instances to load (comma-separated)
PLUGIN_INSTANCES = INV_Solis, BMS_Seplos_v2

# Polling interval in seconds
POLL_INTERVAL = 5

# Your local timezone (IANA format)
LOCAL_TIMEZONE = UTC

# Check for updates on startup
CHECK_FOR_UPDATES = true

# Maximum reconnection attempts
MAX_RECONNECT_ATTEMPTS = 5
```

#### Key Parameters

| Parameter | Description | Default | Examples |
|-----------|-------------|---------|----------|
| `PLUGIN_INSTANCES` | Active plugin instances | None | `INV_Solis, BMS_Seplos_v2` |
| `POLL_INTERVAL` | Data polling frequency (seconds) | 5 | `5`, `10`, `30` |
| `LOCAL_TIMEZONE` | IANA timezone identifier | UTC | `Europe/London`, `America/New_York` |
| `CHECK_FOR_UPDATES` | Enable update checking | true | `true`, `false` |

## System Configuration

### `[INVERTER_SYSTEM]` Section

Define your physical system specifications:

```ini
[INVERTER_SYSTEM]
# Number of MPPT inputs on your inverter
DEFAULT_MPPT_COUNT = 2

# Total solar array capacity in Watts
PV_INSTALLED_CAPACITY_W = 6600.0

# Inverter maximum AC output in Watts
INVERTER_MAX_AC_POWER_W = 6000.0

# Battery usable capacity in kWh
BATTERY_USABLE_CAPACITY_KWH = 15.36

# Battery maximum charge/discharge power in Watts
BATTERY_MAX_CHARGE_POWER_W = 5000.0
BATTERY_MAX_DISCHARGE_POWER_W = 6000.0
```

These values are used for:
- Data validation and filtering
- Efficiency calculations
- Dashboard displays
- Alert thresholds

## Plugin Configuration

### Plugin Configuration Pattern

Each plugin requires a dedicated configuration section:

```ini
[PLUGIN_InstanceName]
plugin_type = category.plugin_name
# ... plugin-specific parameters
```

### Inverter Plugins

#### Solis Modbus Plugin

```ini
[PLUGIN_INV_Solis]
plugin_type = inverter.solis_modbus_plugin

# Connection type: tcp or serial
connection_type = tcp

# TCP Settings (if connection_type = tcp)
tcp_host = 192.168.1.100
tcp_port = 502
slave_address = 1

# Serial Settings (if connection_type = serial)
# serial_port = COM4                    # Windows
# serial_port = /dev/ttyUSB0            # Linux
# baud_rate = 9600
# parity = N
# stopbits = 1
# bytesize = 8

# Optional: Advanced Modbus settings
# modbus_timeout_seconds = 15
# inter_read_delay_ms = 750
# max_regs_per_read = 60
# max_read_retries_per_group = 2
```

#### LuxPower Modbus Plugin

```ini
[PLUGIN_INV_LuxPower]
plugin_type = inverter.luxpower_modbus_plugin

# Connection type: tcp or serial
connection_type = tcp

# TCP Settings (if connection_type = tcp)
tcp_host = 192.168.1.100
tcp_port = 8000                         # Default for lxp-bridge
slave_address = 1

# Serial Settings (if connection_type = serial)
# serial_port = COM3                    # Windows
# serial_port = /dev/ttyUSB0            # Linux
# baud_rate = 9600

# Optional: Advanced settings
# modbus_timeout_seconds = 10
# inter_read_delay_ms = 500
# max_regs_per_read = 50
# max_read_retries_per_group = 2
```

#### POWMR RS232 Plugin

```ini
[PLUGIN_INV_POWMR]
plugin_type = inverter.powmr_rs232_plugin

# Connection type: tcp or serial
connection_type = serial

# POWMR Protocol Version (1 or 2)
powmr_protocol_version = 1

# TCP Settings (if connection_type = tcp)
# tcp_host = 192.168.1.120
# tcp_port = 502

# Serial Settings (if connection_type = serial)
serial_port = COM3                      # Windows
# serial_port = /dev/ttyUSB0            # Linux
baud_rate = 9600

# Optional: Power ratings
# static_max_ac_power_watts = 5000.0
# static_max_dc_power_watts = 6000.0
```

#### Deye/Sunsynk Plugin

```ini
[PLUGIN_INV_Deye]
plugin_type = inverter.deye_sunsynk_plugin

# Connection type: tcp or serial
connection_type = tcp

# TCP Settings
tcp_host = 192.168.1.100
tcp_port = 8899
slave_address = 1

# CRITICAL: Model series selection
# Options: modern_hybrid, legacy_hybrid, three_phase
deye_model_series = modern_hybrid

# Optional: Advanced settings
# modbus_timeout_seconds = 10
# inter_read_delay_ms = 750
# max_regs_per_read = 100
```

### BMS Plugins

#### Seplos BMS V2 Plugin

```ini
[PLUGIN_BMS_Seplos_v2]
plugin_type = battery.seplos_bms_v2_plugin

# Connection type: tcp or serial
seplos_connection_type = tcp

# TCP Settings (if seplos_connection_type = tcp)
seplos_tcp_host = 192.168.1.100
seplos_tcp_port = 5022
seplos_pack_address = 0

# Serial Settings (if seplos_connection_type = serial)
# seplos_serial_port = COM4             # Windows
# seplos_serial_port = /dev/ttyUSB0     # Linux
# seplos_baud_rate = 19200

# Optional: Advanced settings
# seplos_tcp_timeout = 4.0
# seplos_inter_command_delay_ms = 300
```

#### Seplos BMS V3 Plugin

```ini
[PLUGIN_BMS_Seplos_v3]
plugin_type = battery.seplos_bms_v3_plugin

# Connection type: tcp or serial
connection_type = tcp

# TCP Settings
tcp_host = 192.168.1.101
tcp_port = 8899
slave_address = 0

# Serial Settings (if connection_type = serial)
# serial_port = COM3
# baud_rate = 19200
# parity = N
# stopbits = 1
# bytesize = 8
```

#### JK BMS Plugin

```ini
[PLUGIN_BMS_JK]
plugin_type = battery.jk_bms_plugin

# Connection type: tcp or serial
connection_type = serial

# TCP Settings (if connection_type = tcp)
# tcp_host = 192.168.1.100
# tcp_port = 502
# slave_address = 1

# Serial Settings
serial_port = COM4                      # Windows
# serial_port = /dev/ttyUSB0            # Linux
baud_rate = 115200
slave_address = 1
```

## Service Configuration

### Logging

```ini
[LOGGING]
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = INFO

# Create log file
LOG_TO_FILE = True
```

### MQTT Integration

```ini
[MQTT]
# Enable MQTT features
ENABLE_MQTT = false

# MQTT Broker settings
MQTT_HOST = your.mqtt.broker.ip
MQTT_PORT = 1883
MQTT_USERNAME = your_username
MQTT_PASSWORD = your_password

# TLS settings
ENABLE_MQTT_TLS = false

# Topic and discovery settings
MQTT_TOPIC = solar
MQTT_UPDATE_INTERVAL = 5
ENABLE_HA_DISCOVERY = True
HA_DISCOVERY_PREFIX = homeassistant

# Timeout for marking devices offline
MQTT_STALE_DATA_TIMEOUT_SECONDS = 900
```

### Web Dashboard

```ini
[WEB_DASHBOARD]
# Enable web interface
ENABLE_WEB_DASHBOARD = True

# Port for web server
WEB_DASHBOARD_PORT = 8081

# HTTPS settings
ENABLE_HTTPS = false

# Update frequency
WEB_UPDATE_INTERVAL = 2.0

# Security (CHANGE THIS!)
FLASK_SECRET_KEY = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_STRING"
```

### Database

```ini
[DATABASE]
# SQLite database file
DB_FILE = solis_history.db

# Data retention (hours)
HISTORY_MAX_AGE_HOURS = 720

# Snapshot interval (seconds)
POWER_HISTORY_INTERVAL_SECONDS = 60

# Power threshold for calculations
HOURLY_SUMMARY_POWER_THRESHOLD_W = 2.0
```

### Console Dashboard

```ini
[CONSOLE_DASHBOARD]
# Enable terminal interface
ENABLE_DASHBOARD = True

# Update frequency
DASHBOARD_UPDATE_INTERVAL = 1
```

### Weather Widget

```ini
[WEATHER]
# Enable weather widget
ENABLE_WEATHER_WIDGET = True

# Location settings
WEATHER_USE_AUTOMATIC_LOCATION = False
WEATHER_DEFAULT_LATITUDE = 40.7128
WEATHER_DEFAULT_LONGITUDE = -74.0060

# Display settings
WEATHER_TEMPERATURE_UNIT = celsius
WEATHER_MAP_ZOOM_LEVEL = 5
WEATHER_UPDATE_INTERVAL_MINUTES = 15
```

### Tuya Smart Plug Control

```ini
[TUYA]
# Enable Tuya device control
ENABLE_TUYA = False

# Device settings
TUYA_DEVICE_ID = your_device_id_here
TUYA_LOCAL_KEY = your_local_key_here
TUYA_IP_ADDRESS = Auto
TUYA_VERSION = 3.4

# Temperature thresholds (°C)
TEMP_THRESHOLD_ON = 43.0
TEMP_THRESHOLD_OFF = 42.0
```

## Advanced Configuration

### Data Filtering

```ini
[FILTER]
# Filtering mode: adaptive or disabled
FILTERING_MODE = adaptive

# Daily energy limits (kWh) to prevent sensor errors
DAILY_LIMIT_GRID_IMPORT_KWH = 100.0
DAILY_LIMIT_GRID_EXPORT_KWH = 50.0
DAILY_LIMIT_BATTERY_CHARGE_KWH = 50.0
DAILY_LIMIT_BATTERY_DISCHARGE_KWH = 50.0
DAILY_LIMIT_PV_GENERATION_KWH = 80.0
DAILY_LIMIT_LOAD_CONSUMPTION_KWH = 120.0
```

### Watchdog System

```ini
[WATCHDOG]
# Timeout before restarting plugin (seconds)
WATCHDOG_TIMEOUT = 120

# Grace period after startup (seconds)
WATCHDOG_GRACE_PERIOD = 30

# Maximum restart attempts
MAX_PLUGIN_RELOAD_ATTEMPTS = 3
```

### TLS/SSL Configuration

```ini
[TLS]
# Certificate paths for HTTPS and secure MQTT
TLS_CA_CERTS_PATH = /etc/ssl/certs/ca-certificates.crt
TLS_CERT_PATH = /path/to/your/client.crt
TLS_KEY_PATH = /path/to/your/client.key
```

## Configuration Best Practices

### Security

1. **Change Default Secrets**:
   ```ini
   FLASK_SECRET_KEY = "your-unique-secret-key-here"
   ```

2. **Use Strong MQTT Credentials**:
   ```ini
   MQTT_USERNAME = strong_username
   MQTT_PASSWORD = strong_password
   ```

3. **Enable TLS When Possible**:
   ```ini
   ENABLE_MQTT_TLS = true
   ENABLE_HTTPS = true
   ```

### Performance

1. **Adjust Polling Based on System**:
   ```ini
   # Fast systems
   POLL_INTERVAL = 5
   
   # Slower systems or networks
   POLL_INTERVAL = 10
   ```

2. **Optimize Modbus Settings**:
   ```ini
   # For stable networks
   modbus_timeout_seconds = 10
   inter_read_delay_ms = 500
   
   # For unstable networks
   modbus_timeout_seconds = 15
   inter_read_delay_ms = 1000
   max_read_retries_per_group = 3
   ```

3. **Database Optimization**:
   ```ini
   # More frequent snapshots (more data, larger DB)
   POWER_HISTORY_INTERVAL_SECONDS = 30
   
   # Less frequent snapshots (less data, smaller DB)
   POWER_HISTORY_INTERVAL_SECONDS = 120
   ```

### Reliability

1. **Increase Timeouts for Unstable Connections**:
   ```ini
   WATCHDOG_TIMEOUT = 180
   modbus_timeout_seconds = 20
   ```

2. **Enable More Retries**:
   ```ini
   MAX_RECONNECT_ATTEMPTS = 10
   max_read_retries_per_group = 5
   ```

3. **Adjust Data Retention**:
   ```ini
   # Keep more history
   HISTORY_MAX_AGE_HOURS = 2160  # 90 days
   
   # Keep less history (smaller DB)
   HISTORY_MAX_AGE_HOURS = 168   # 7 days
   ```

## Configuration Validation

### Validate Configuration

```bash
# Test configuration loading
python test_plugins/validate_all_plugins.py --offline-only

# Test specific plugin configuration
python test_plugins/inverter_stand_alone_test_solis.py
```

### Common Configuration Errors

1. **Missing Plugin Sections**:
   ```
   Error: Config section [PLUGIN_INV_Solis] not found
   ```
   **Solution**: Add the required plugin section to config.ini

2. **Invalid Parameter Types**:
   ```
   Error: invalid literal for int() with base 10: 'abc'
   ```
   **Solution**: Ensure numeric parameters contain valid numbers

3. **Missing Required Parameters**:
   ```
   Error: Required parameter 'tcp_host' missing
   ```
   **Solution**: Add all required parameters for your plugin

## Troubleshooting

### Configuration Issues

1. **Check Syntax**:
   - Ensure proper INI file format
   - Check for missing `=` signs
   - Verify section headers have `[brackets]`

2. **Validate Parameters**:
   - Use validation tools to check configuration
   - Test individual plugins
   - Check log files for errors

3. **Network Settings**:
   - Verify IP addresses and ports
   - Test network connectivity
   - Check firewall settings

### Plugin-Specific Issues

1. **Connection Failures**:
   - Verify device IP addresses and ports
   - Check network connectivity
   - Ensure devices are powered on

2. **Data Reading Errors**:
   - Check Modbus settings (timeout, retries)
   - Verify slave addresses
   - Test with individual plugin tests

3. **Performance Issues**:
   - Adjust polling intervals
   - Optimize Modbus parameters
   - Check system resources

### Getting Help

1. **Use Validation Tools**: Run comprehensive validation
2. **Check Logs**: Review solar_monitoring.log for errors
3. **Test Individual Plugins**: Isolate configuration issues
4. **Consult Documentation**: Review plugin-specific guides
5. **Ask Community**: Open GitHub issues for help

For more troubleshooting information, see [TESTING.md](TESTING.md).