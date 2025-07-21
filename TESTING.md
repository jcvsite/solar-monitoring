# Plugin Testing & Validation Guide

This guide covers the comprehensive testing and validation system for the Solar Monitoring Framework plugins.

## Table of Contents

- [Overview](#overview)
- [Validation Tools](#validation-tools)
- [Quick Start](#quick-start)
- [Detailed Tool Documentation](#detailed-tool-documentation)
- [Individual Plugin Tests](#individual-plugin-tests)
- [Troubleshooting](#troubleshooting)
- [CI/CD Integration](#cicd-integration)

## Overview

The Solar Monitoring Framework includes a three-tier plugin testing and validation system designed to ensure reliability, ease troubleshooting, and support development workflows.

### Validation Philosophy

- **Fast Feedback**: Quick checks for development workflows
- **Comprehensive Analysis**: Detailed validation with reporting
- **Hardware Testing**: End-to-end validation with real devices
- **Quality Assurance**: Automated testing for CI/CD pipelines

## Validation Tools

| Tool | Purpose | Speed | Hardware Required | Use Case |
|------|---------|-------|-------------------|----------|
| `quick_plugin_check.py` | Fast health check | ⚡ < 10s | ❌ No | Development, CI/CD |
| `validate_all_plugins.py` | Comprehensive validation | 🐌 30-120s | ⚠️ Optional | Analysis, Troubleshooting |
| `run_all_plugin_tests.py` | Execute all individual tests | 🐌 5-20min | ✅ Yes | Hardware validation |

## Quick Start

### Basic Validation Commands

```bash
# Fast development check (no hardware needed)
python test_plugins/quick_plugin_check.py

# Comprehensive validation with detailed reporting
python test_plugins/validate_all_plugins.py

# Offline validation for CI/CD pipelines
python test_plugins/validate_all_plugins.py --offline-only

# Test only inverter plugins
python test_plugins/validate_all_plugins.py --plugin-type inverter

# Generate detailed report
python test_plugins/validate_all_plugins.py --report-file validation_report.txt

# Run all individual plugin tests with real hardware
python test_plugins/run_all_plugin_tests.py --parallel
```

### Sample Output

```
🔍 Quick Plugin Health Check
==================================================
✅ PASS Solis Modbus         Plugin loads and instantiates correctly
✅ PASS LuxPower Modbus      Plugin loads and instantiates correctly
✅ PASS POWMR RS232          Plugin loads and instantiates correctly
✅ PASS Deye/Sunsynk         Plugin loads and instantiates correctly
✅ PASS Seplos BMS V2        Plugin loads and instantiates correctly
✅ PASS Seplos BMS V3        Plugin loads and instantiates correctly
✅ PASS JK BMS               Plugin loads and instantiates correctly

SUMMARY: 7/7 plugins passed (100.0% success rate)
```

## Detailed Tool Documentation

### ⚡ Quick Plugin Check (`quick_plugin_check.py`)

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

**Command Options**:
```bash
python test_plugins/quick_plugin_check.py
```

### 🔍 Comprehensive Validation (`validate_all_plugins.py`)

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

**Command Options**:
```bash
# Basic comprehensive validation
python test_plugins/validate_all_plugins.py

# Offline mode (no device connections)
python test_plugins/validate_all_plugins.py --offline-only

# Test specific plugin types
python test_plugins/validate_all_plugins.py --plugin-type inverter
python test_plugins/validate_all_plugins.py --plugin-type bms

# Generate detailed report
python test_plugins/validate_all_plugins.py --report-file validation_report.txt

# Verbose logging
python test_plugins/validate_all_plugins.py --verbose

# Custom config file
python test_plugins/validate_all_plugins.py --config-file custom_config.ini
```

### 🧪 Full Test Execution (`run_all_plugin_tests.py`)

**Purpose**: Execute all individual plugin test scripts with comprehensive reporting.

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

**Command Options**:
```bash
# Basic test execution
python test_plugins/run_all_plugin_tests.py

# Parallel execution (faster)
python test_plugins/run_all_plugin_tests.py --parallel

# Custom timeout
python test_plugins/run_all_plugin_tests.py --timeout 300

# Generate detailed report
python test_plugins/run_all_plugin_tests.py --report-file test_report.txt

# Verbose output
python test_plugins/run_all_plugin_tests.py --verbose
```

## Individual Plugin Tests

Each plugin has its own standalone test script for focused testing:

### Available Test Scripts

1. **`inverter_stand_alone_test_solis.py`** - Test Solis Modbus inverters
2. **`inverter_stand_alone_test_luxpower.py`** - Test LuxPower Modbus inverters
3. **`inverter_stand_alone_test_deye.py`** - Test Deye/Sunsynk inverters
4. **`inverter_stand_alone_test_powmr.py`** - Test POWMR RS232 inverters
5. **`bms_stand_alone_test_seplos_v2.py`** - Test Seplos BMS V2
6. **`bms_stand_alone_test_seplos_v3.py`** - Test Seplos BMS V3
7. **`bms_stand_alone_test_jk.py`** - Test JK BMS

### Usage Examples

```bash
# Test with default configuration
python test_plugins/inverter_stand_alone_test_solis.py

# Test with custom instance name
set INVERTER_INSTANCE_NAME=INV_Solis
python test_plugins/inverter_stand_alone_test_solis.py

# Test LuxPower inverter
python test_plugins/inverter_stand_alone_test_luxpower.py

# Test BMS with custom instance
set BMS_INSTANCE_NAME=BMS_Seplos_v2
python test_plugins/bms_stand_alone_test_seplos_v2.py
```

### What Individual Tests Do

Each test script performs:

1. **Load Configuration** - Reads plugin settings from `config.ini`
2. **Initialize Plugin** - Creates and configures the plugin instance
3. **Test Connection** - Attempts to connect to the device
4. **Read Static Data** - Retrieves device information (model, serial, etc.)
5. **Read Dynamic Data** - Performs multiple cycles of real-time data reading
6. **Display Results** - Shows formatted data output with analysis
7. **Clean Disconnect** - Properly closes the connection

## Troubleshooting

### Common Issues

#### Import Errors
```
❌ FAIL Plugin Name: Import error: No module named 'module_name'
```
**Solution**: Install missing dependencies or check plugin implementation.

#### Configuration Errors
```
❌ FAIL Plugin Name: Config section [PLUGIN_NAME] not found
```
**Solution**: Add the required plugin configuration section to `config.ini`.

#### Connection Failures
```
❌ FAIL Plugin Name: Connection timeout
```
**Solutions**:
- Verify IP addresses and ports in config.ini
- Check network connectivity to devices
- Ensure devices are powered on and responsive
- Check firewall settings

#### Class Not Found Errors
```
❌ FAIL Plugin Name: Class not found: module has no attribute 'ClassName'
```
**Solution**: Check plugin registry in validation scripts for correct class names.

### Debug Tips

1. **Check Network Connectivity**
   ```bash
   ping 192.168.1.11  # Replace with your device IP
   telnet 192.168.1.11 5021  # Test port connectivity
   ```

2. **Use Verbose Logging**
   ```bash
   python test_plugins/validate_all_plugins.py --verbose
   ```

3. **Test Individual Plugins**
   ```bash
   python test_plugins/inverter_stand_alone_test_solis.py
   ```

4. **Check Configuration**
   - Verify plugin section names match exactly
   - Check for typos in configuration parameters
   - Ensure required parameters are present

### Successful vs Failed Test Examples

**Successful Test:**
```
2025-07-20 10:00:17,727 INFO [MainThread] Successfully connected to Solis Inverter.

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

**Failed Test:**
```
2025-07-20 10:00:17,727 ERROR [MainThread] Failed to connect to device.
Check connection details. Last error: Connection timeout
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Plugin Validation
on: [push, pull_request]

jobs:
  validate-plugins:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: pip install -r requirements.txt
    - name: Quick plugin check
      run: python test_plugins/quick_plugin_check.py
    - name: Comprehensive validation (offline)
      run: python test_plugins/validate_all_plugins.py --offline-only
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any
    stages {
        stage('Plugin Validation') {
            steps {
                sh 'python test_plugins/quick_plugin_check.py'
                sh 'python test_plugins/validate_all_plugins.py --offline-only --report-file validation_report.txt'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'validation_report.txt', fingerprint: true
                }
            }
        }
    }
}
```

### Exit Codes

All validation tools use standard exit codes:
- **0**: All tests passed
- **1**: One or more tests failed

This makes them suitable for automated CI/CD pipelines that depend on exit codes for success/failure determination.

## Best Practices

### For Development
1. Run `quick_plugin_check.py` after code changes
2. Use comprehensive validation before committing
3. Test with actual hardware when possible
4. Include validation in pre-commit hooks

### For Production Deployment
1. Run full hardware validation before deployment
2. Generate and review detailed reports
3. Test all configured plugins
4. Validate after configuration changes

### For Troubleshooting
1. Start with quick plugin check to isolate issues
2. Use comprehensive validation for detailed analysis
3. Run individual plugin tests for focused debugging
4. Check logs and error messages carefully

## Contributing

When adding new plugins or modifying existing ones:

1. **Update Plugin Registry**: Add new plugins to validation tool registries
2. **Create Test Scripts**: Add individual test scripts for new plugins
3. **Test Thoroughly**: Ensure all validation tools work with new plugins
4. **Update Documentation**: Update this guide with new plugin information

For more information on plugin development, see [DEVELOPER.md](DEVELOPER.md).