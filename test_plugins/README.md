# Plugin Test Scripts

This directory contains standalone test scripts for testing individual plugins without running the full monitoring application. These scripts are useful for debugging connection issues, validating plugin configurations, and testing new hardware setups.

## Available Test Scripts

### Individual Plugin Tests

1. **`inverter_stand_alone_test_solis.py`** - Test Solis Modbus inverters
2. **`inverter_stand_alone_test_deye.py`** - Test Deye/Sunsynk inverters
3. **`inverter_stand_alone_test_powmr.py`** - Test POWMR RS232 inverters (inv8851 protocol)
4. **`bms_stand_alone_test_seplos_v2.py`** - Test Seplos BMS V2
5. **`bms_stand_alone_test_seplos_v3.py`** - Test Seplos BMS V3
6. **`bms_stand_alone_test_jk.py`** - Test JK BMS (Modbus)

### Comprehensive Plugin Test Suites

1. **`test_powmr_rs232_plugin.py`** - Complete test suite for POWMR RS232 plugin

## Usage

### Testing Individual Plugins

Each standalone test script follows the same pattern:

```bash
# Test with default configuration
python test_plugins/inverter_stand_alone_test_solis.py

# Test with custom instance name
set INVERTER_INSTANCE_NAME=INV_Solis
python test_plugins/inverter_stand_alone_test_solis.py

# For POWMR RS232 inverters
python test_plugins/inverter_stand_alone_test_powmr.py
# Or with custom instance name
set INVERTER_INSTANCE_NAME=INV_POWMR
python test_plugins/inverter_stand_alone_test_powmr.py

# For BMS plugins
set BMS_INSTANCE_NAME=BMS_Seplos_v2
python test_plugins/bms_stand_alone_test_seplos_v2.py

# Run comprehensive test suite for POWMR RS232
python test_plugins/test_powmr_rs232_plugin.py
```
## What the Tests Do

Each test script performs the following operations:

1. **Load Configuration** - Reads plugin settings from `config.ini`
2. **Initialize Plugin** - Creates and configures the plugin instance
3. **Test Connection** - Attempts to connect to the device
4. **Read Static Data** - Retrieves device information (model, serial, etc.)
5. **Read Dynamic Data** - Performs multiple cycles of real-time data reading
6. **Display Results** - Shows formatted data output
7. **Clean Disconnect** - Properly closes the connection

## Configuration Requirements

Before running tests, ensure your `config.ini` file contains the appropriate plugin sections:

### For Inverter Tests
- `[PLUGIN_INV_Solis]` - Solis inverter configuration
- `[PLUGIN_INV_Deye]` - Deye/Sunsynk inverter configuration
- `[PLUGIN_INV_POWMR]` - POWMR RS232 inverter configuration (inv8851 protocol)

### For BMS Tests  
- `[PLUGIN_BMS_Seplos_v2]` - Seplos V2 BMS configuration
- `[PLUGIN_BMS_Seplos_v3]` - Seplos V3 BMS configuration
- `[PLUGIN_BMS_JK]` - JK BMS configuration

## Configuration Loading

All test plugins now use a **centralized configuration loader** (`test_plugins/test_config_loader.py`) that provides:

### ✅ **Robust Configuration Parsing**
- **Intelligent comment handling**: Properly handles inline comments with `;` and `#`
- **Smart semicolon detection**: Preserves legitimate semicolons in values like crypto keys
- **Automatic whitespace trimming**: Removes extra spaces and quotes
- **Type conversion**: Automatic conversion to int, float, bool, or string
- **Consistent behavior**: Same parsing logic as the main application

### ✅ **Plugin-Specific Support**
- **POWMR RS232**: `powmr_protocol_version` parameter
- **Deye/Sunsynk**: `deye_model_series` parameter  
- **Seplos BMS**: All Seplos-specific connection parameters
- **Universal parameters**: Modbus settings, timeouts, power ratings

### ✅ **Error Prevention**
- **No more parsing errors**: Eliminates `invalid literal for int()` errors
- **Graceful fallbacks**: Uses sensible defaults when values are missing
- **Clear error messages**: Helpful feedback when configuration issues occur

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure you're running from the project root directory
   - Check that all required dependencies are installed

2. **Connection Failures**
   - Verify IP addresses and ports in config.ini
   - Check network connectivity to devices
   - Ensure devices are powered on and responsive

3. **Configuration Errors** ✅ **RESOLVED**
   - ~~Verify plugin section names match exactly~~ ✅ **Auto-handled**
   - ~~Check for typos in configuration parameters~~ ✅ **Auto-handled**
   - ~~Ensure required parameters are present~~ ✅ **Auto-handled**
   - **Configuration parsing is now robust and handles most common issues automatically**

### Debug Tips

1. **Check Network Connectivity**
   ```bash
   ping 192.168.1.11  # Replace with your device IP
   telnet 192.168.1.11 5021  # Test port connectivity
   ```

### Successful Test
```
2025-07-17 10:00:17,727 INFO [MainThread] Successfully connected to Solis Inverter.

--- Static Inverter Information ---
{ 'static_battery_model_name': 'Pylontech',
  'static_device_category': 'inverter',
  'static_inverter_model_name': 'Solis S6 1P LV Hybrid (3-6kW)',
  'static_rated_power_ac_watts': 6000.0 }

--- Dynamic Data (Cycle 1) ---
{ 'ac_power_watts': 2870.0,
  'battery_power_watts': 708.0,
  'operational_inverter_status_text': 'Generating' }
```

### Failed Test
```
2025-07-17 10:00:17,727 ERROR [MainThread] Failed to connect to device.
Check connection details. Last error: Connection timeout
```

## Adding New Plugin Tests

To create a test script for a new plugin:

1. Copy an existing test script as a template
2. Update the import statement for your plugin class
3. Modify the configuration loading function for your plugin's parameters
4. Update the script documentation and instance names
5. Test with your specific plugin configuration

## Integration with Main Application

These test scripts are independent of the main monitoring application but use the same:
- Plugin classes and interfaces
- Configuration file format
- Logging mechanisms
- Error handling patterns

This ensures that successful standalone tests indicate the plugin will work correctly in the full application.