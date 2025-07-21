# Plugin Test Scripts

This directory contains standalone test scripts for testing individual plugins without running the full monitoring application. These scripts are useful for debugging connection issues, validating plugin configurations, and testing new hardware setups.

## Available Test Scripts

### Individual Plugin Tests

1. **`inverter_stand_alone_test_solis.py`** - Test Solis Modbus inverters
2. **`inverter_stand_alone_test_luxpower.py`** - Test LuxPower Modbus inverters (LXP-5K, LXP-12K, LXP-LB-5K)
3. **`inverter_stand_alone_test_deye.py`** - Test Deye/Sunsynk inverters
4. **`inverter_stand_alone_test_powmr.py`** - Test POWMR RS232 inverters (inv8851 protocol)
5. **`bms_stand_alone_test_seplos_v2.py`** - Test Seplos BMS V2
6. **`bms_stand_alone_test_seplos_v3.py`** - Test Seplos BMS V3
7. **`bms_stand_alone_test_jk.py`** - Test JK BMS (Modbus)

### Comprehensive Plugin Test Suites

1. **`test_powmr_rs232_plugin.py`** - Complete test suite for POWMR RS232 plugin

### Plugin Validation Tools

1. **`validate_all_plugins.py`** - Comprehensive validation of all plugins with detailed reporting
2. **`quick_plugin_check.py`** - Fast health check for plugin loading and instantiation
3. **`run_all_plugin_tests.py`** - Execute all individual plugin tests with comprehensive reporting

## Usage

### Testing Individual Plugins

Each standalone test script follows the same pattern:

```bash
# Test with default configuration
python test_plugins/inverter_stand_alone_test_solis.py

# Test with custom instance name
set INVERTER_INSTANCE_NAME=INV_Solis
python test_plugins/inverter_stand_alone_test_solis.py

# For LuxPower Modbus inverters
python test_plugins/inverter_stand_alone_test_luxpower.py
# Or with custom instance name
set INVERTER_INSTANCE_NAME=INV_LuxPower
python test_plugins/inverter_stand_alone_test_luxpower.py

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

### Using Plugin Validation Tools

The validation tools provide different levels of testing:

```bash
# Quick health check (fast, no connections)
python test_plugins/quick_plugin_check.py

# Comprehensive validation (tests loading, connections, data)
python test_plugins/validate_all_plugins.py

# Offline validation only (no device connections)
python test_plugins/validate_all_plugins.py --offline-only

# Test only inverter plugins
python test_plugins/validate_all_plugins.py --plugin-type inverter

# Generate detailed report
python test_plugins/validate_all_plugins.py --report-file validation_report.txt

# Run all individual plugin tests
python test_plugins/run_all_plugin_tests.py

# Run tests in parallel (faster)
python test_plugins/run_all_plugin_tests.py --parallel

# Set custom timeout for slow connections
python test_plugins/run_all_plugin_tests.py --timeout 300
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
- `[PLUGIN_INV_LuxPower]` - LuxPower inverter configuration (LXP-5K, LXP-12K, LXP-LB-5K)
- `[PLUGIN_INV_Deye]` - Deye/Sunsynk inverter configuration
- `[PLUGIN_INV_POWMR]` - POWMR RS232 inverter configuration (inv8851 protocol)

### For BMS Tests  
- `[PLUGIN_BMS_Seplos_v2]` - Seplos V2 BMS configuration
- `[PLUGIN_BMS_Seplos_v3]` - Seplos V3 BMS configuration
- `[PLUGIN_BMS_JK]` - JK BMS configuration

## Configuration Loading ⚠️ **NEEDS TESTING**

All test plugins now use a **centralized configuration loader** (`test_plugins/test_config_loader.py`) that provides:

> **⚠️ IMPORTANT**: This is a newly implemented system that requires testing across all plugin types. 
> If you encounter any configuration loading issues, please report them and temporarily revert to the previous individual plugin test files if needed.

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

## Validation Tools Explained

### 🔍 `validate_all_plugins.py` - Comprehensive Plugin Validation

**Purpose**: Systematic validation of all plugins with detailed analysis and reporting.

**Features**:
- Tests plugin loading, instantiation, and interface compliance
- Attempts actual device connections (optional)
- Validates data structure compliance with StandardDataKeys
- Generates comprehensive reports with recommendations
- Supports offline-only mode for CI/CD pipelines

**Use Cases**:
- **Development**: Validate new plugins before integration
- **CI/CD**: Automated plugin health checks in build pipelines
- **Troubleshooting**: Systematic diagnosis of plugin issues
- **Documentation**: Generate plugin compatibility reports

**Sample Output**:
```
================================================================================
PLUGIN VALIDATION SUMMARY REPORT
================================================================================
Total Plugins Tested: 7
Passed: 5 ✅
Failed: 1 ❌
Warnings: 1 ⚠️
Success Rate: 71.4%

INVERTER PLUGINS:
  ✅ inverter.solis_modbus_plugin
  ✅ inverter.luxpower_modbus_plugin
  ⚠️ inverter.powmr_rs232_plugin (Plugin loads but connection failed)
  ❌ inverter.deye_sunsynk_plugin (Import error: Module not found)
```

### ⚡ `quick_plugin_check.py` - Fast Health Check

**Purpose**: Rapid validation of plugin loading and basic functionality.

**Features**:
- Fast execution (< 10 seconds)
- Tests import and instantiation only
- No actual device connections
- Perfect for development workflows
- Clean, concise output

**Use Cases**:
- **Development**: Quick check after code changes
- **Git Hooks**: Pre-commit validation
- **Build Systems**: Fast CI/CD health checks
- **Debugging**: Isolate import/instantiation issues

**Sample Output**:
```
🔍 Quick Plugin Health Check
==================================================
✅ PASS Solis Modbus        Plugin loads and instantiates correctly
✅ PASS LuxPower Modbus     Plugin loads and instantiates correctly
❌ FAIL POWMR RS232         Import error: No module named 'serial'
✅ PASS Deye/Sunsynk        Plugin loads and instantiates correctly
```

### 🧪 `run_all_plugin_tests.py` - Execute All Individual Tests

**Purpose**: Run all individual plugin test scripts with comprehensive reporting.

**Features**:
- Executes actual plugin test scripts
- Tests real hardware connections
- Parallel execution support
- Timeout protection
- Detailed output capture and reporting

**Use Cases**:
- **Hardware Testing**: Validate all configured devices
- **Integration Testing**: End-to-end plugin validation
- **Regression Testing**: Ensure changes don't break existing plugins
- **System Validation**: Complete system health check

**Sample Output**:
```
🧪 Running All Plugin Tests
============================================================
Found 4 test scripts:
  • Solis Modbus Inverter (inverter_stand_alone_test_solis.py)
  • LuxPower Modbus Inverter (inverter_stand_alone_test_luxpower.py)

[1/4] Running Solis Modbus Inverter...
  ✅ PASS Solis Modbus Inverter (45.2s)

[2/4] Running LuxPower Modbus Inverter...
  ❌ FAIL LuxPower Modbus Inverter (120.0s) - Connection timeout
```

## Choosing the Right Tool

| Tool | Speed | Scope | Hardware Required | Use Case |
|------|-------|-------|-------------------|----------|
| `quick_plugin_check.py` | ⚡ Fast | Loading only | ❌ No | Development, CI/CD |
| `validate_all_plugins.py` | 🐌 Medium | Comprehensive | ⚠️ Optional | Analysis, Troubleshooting |
| `run_all_plugin_tests.py` | 🐌 Slow | Full testing | ✅ Yes | Hardware validation |

## Integration with Main Application

These test scripts are independent of the main monitoring application but use the same:
- Plugin classes and interfaces
- Configuration file format
- Logging mechanisms
- Error handling patterns

This ensures that successful standalone tests indicate the plugin will work correctly in the full application.