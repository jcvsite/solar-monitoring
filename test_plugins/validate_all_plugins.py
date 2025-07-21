#!/usr/bin/env python3
"""
Comprehensive Plugin Validation Test Suite

This script validates all available plugins in the Solar Monitoring Framework.
It performs systematic testing of plugin loading, configuration parsing, 
connection attempts, and data reading capabilities.

Features:
- Tests all inverter and BMS plugins
- Validates plugin interface compliance
- Tests configuration loading and parsing
- Attempts connections (with timeout protection)
- Validates data structure compliance
- Generates comprehensive test reports
- Supports both connected and offline testing modes

Usage:
    python test_plugins/validate_all_plugins.py [options]

Options:
    --offline-only    Skip actual device connections (test plugin loading only)
    --plugin-type     Test only specific plugin type (inverter, bms, all)
    --config-file     Use custom config file (default: config.ini)
    --verbose         Enable verbose logging
    --report-file     Save detailed report to file

Examples:
    # Test all plugins with connections
    python test_plugins/validate_all_plugins.py
    
    # Test only plugin loading (no connections)
    python test_plugins/validate_all_plugins.py --offline-only
    
    # Test only inverter plugins
    python test_plugins/validate_all_plugins.py --plugin-type inverter
    
    # Generate detailed report
    python test_plugins/validate_all_plugins.py --report-file validation_report.txt

GitHub: https://github.com/jcvsite/solar-monitoring
"""

import os
import sys
import time
import logging
import argparse
import traceback
import configparser
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Setup project path
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir)
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

# Import test configuration loader
from test_plugins.test_config_loader import load_plugin_config_from_file

# Import plugin interfaces
from plugins.plugin_interface import DevicePlugin, StandardDataKeys


class TestResult(Enum):
    """Test result enumeration."""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    WARN = "WARN"


@dataclass
class PluginTestResult:
    """Results for a single plugin test."""
    plugin_name: str
    plugin_type: str
    instance_name: str
    config_loaded: TestResult
    plugin_instantiated: TestResult
    connection_attempted: TestResult
    connection_successful: TestResult
    static_data_read: TestResult
    dynamic_data_read: TestResult
    data_structure_valid: TestResult
    overall_result: TestResult
    error_messages: List[str]
    warnings: List[str]
    test_duration: float
    data_samples: Dict[str, Any]


class PluginValidator:
    """Main plugin validation class."""
    
    # Plugin registry - maps plugin types to their classes and default instances
    PLUGIN_REGISTRY = {
        # Inverter plugins
        'inverter.solis_modbus_plugin': {
            'class_name': 'SolisModbusPlugin',
            'module_path': 'plugins.inverter.solis_modbus_plugin',
            'default_instance': 'INV_Solis',
            'category': 'inverter',
            'status': 'stable'
        },
        'inverter.luxpower_modbus_plugin': {
            'class_name': 'LuxpowerModbusPlugin', 
            'module_path': 'plugins.inverter.luxpower_modbus_plugin',
            'default_instance': 'INV_LuxPower',
            'category': 'inverter',
            'status': 'ready_for_testing'
        },
        'inverter.eg4_modbus_plugin': {
            'class_name': 'Eg4ModbusPlugin',
            'module_path': 'plugins.inverter.eg4_modbus_plugin',
            'default_instance': 'INV_EG4',
            'category': 'inverter',
            'status': 'ready_for_testing'
        },
        'inverter.growatt_modbus_plugin': {
            'class_name': 'GrowattModbusPlugin',
            'module_path': 'plugins.inverter.growatt_modbus_plugin',
            'default_instance': 'INV_Growatt',
            'category': 'inverter',
            'status': 'ready_for_testing'
        },
        'inverter.srne_modbus_plugin': {
            'class_name': 'SrneModbusPlugin',
            'module_path': 'plugins.inverter.srne_modbus_plugin',
            'default_instance': 'INV_SRNE',
            'category': 'inverter',
            'status': 'ready_for_testing'
        },
        'inverter.powmr_rs232_plugin': {
            'class_name': 'PowmrCustomRs232Plugin',
            'module_path': 'plugins.inverter.powmr_rs232_plugin', 
            'default_instance': 'INV_POWMR',
            'category': 'inverter',
            'status': 'ready_for_testing'
        },
        'inverter.deye_sunsynk_plugin': {
            'class_name': 'DeyeSunsynkPlugin',
            'module_path': 'plugins.inverter.deye_sunsynk_plugin',
            'default_instance': 'INV_Deye',
            'category': 'inverter', 
            'status': 'ready_for_testing'
        },
        # BMS plugins
        'battery.seplos_bms_v2_plugin': {
            'class_name': 'SeplosBMSV2',
            'module_path': 'plugins.battery.seplos_bms_v2_plugin',
            'default_instance': 'BMS_Seplos_v2',
            'category': 'bms',
            'status': 'stable'
        },
        'battery.seplos_bms_v3_plugin': {
            'class_name': 'SeplosBmsV3Plugin', 
            'module_path': 'plugins.battery.seplos_bms_v3_plugin',
            'default_instance': 'BMS_Seplos_v3',
            'category': 'bms',
            'status': 'needs_testers'
        },
        'battery.jk_bms_plugin': {
            'class_name': 'JkBmsModbusPlugin',
            'module_path': 'plugins.battery.jk_bms_plugin', 
            'default_instance': 'BMS_JK',
            'category': 'bms',
            'status': 'needs_testers'
        }
    }
    
    def __init__(self, config_file: str = "config.ini", offline_only: bool = False, 
                 plugin_type_filter: str = "all", verbose: bool = False):
        """Initialize the plugin validator."""
        self.config_file = os.path.join(project_root_dir, config_file)
        self.offline_only = offline_only
        self.plugin_type_filter = plugin_type_filter.lower()
        self.verbose = verbose
        self.results: List[PluginTestResult] = []
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s %(levelname)-8s [%(name)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        return logging.getLogger("PluginValidator")
    
    def validate_all_plugins(self) -> List[PluginTestResult]:
        """Validate all registered plugins."""
        self.logger.info("="*80)
        self.logger.info("Solar Monitoring Framework - Plugin Validation Suite")
        self.logger.info("="*80)
        self.logger.info(f"Config file: {self.config_file}")
        self.logger.info(f"Test mode: {'Offline only' if self.offline_only else 'Full validation'}")
        self.logger.info(f"Plugin filter: {self.plugin_type_filter}")
        self.logger.info(f"Plugins to test: {len(self._get_filtered_plugins())}")
        self.logger.info("="*80)
        
        filtered_plugins = self._get_filtered_plugins()
        
        for plugin_type, plugin_info in filtered_plugins.items():
            self.logger.info(f"\n🔍 Testing {plugin_type} ({plugin_info['status'].upper()})")
            result = self._test_single_plugin(plugin_type, plugin_info)
            self.results.append(result)
            self._log_test_result(result)
            
        return self.results
    
    def _get_filtered_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Get plugins filtered by type."""
        if self.plugin_type_filter == "all":
            return self.PLUGIN_REGISTRY
        elif self.plugin_type_filter in ["inverter", "bms"]:
            return {k: v for k, v in self.PLUGIN_REGISTRY.items() 
                   if v['category'] == self.plugin_type_filter}
        else:
            self.logger.warning(f"Unknown plugin type filter: {self.plugin_type_filter}")
            return self.PLUGIN_REGISTRY
    
    def _test_single_plugin(self, plugin_type: str, plugin_info: Dict[str, Any]) -> PluginTestResult:
        """Test a single plugin comprehensively."""
        start_time = time.time()
        
        result = PluginTestResult(
            plugin_name=plugin_type,
            plugin_type=plugin_info['category'],
            instance_name=plugin_info['default_instance'],
            config_loaded=TestResult.FAIL,
            plugin_instantiated=TestResult.FAIL,
            connection_attempted=TestResult.SKIP,
            connection_successful=TestResult.FAIL,
            static_data_read=TestResult.FAIL,
            dynamic_data_read=TestResult.FAIL,
            data_structure_valid=TestResult.FAIL,
            overall_result=TestResult.FAIL,
            error_messages=[],
            warnings=[],
            test_duration=0.0,
            data_samples={}
        )
        
        try:
            # Test 1: Configuration Loading
            self.logger.debug(f"  📋 Testing configuration loading...")
            config, config_result = self._test_config_loading(plugin_info['default_instance'])
            result.config_loaded = config_result
            if config_result == TestResult.FAIL:
                result.error_messages.append("Configuration loading failed")
                result.overall_result = TestResult.FAIL
                return result
            elif config_result == TestResult.SKIP:
                result.error_messages.append(f"Configuration section [PLUGIN_{plugin_info['default_instance']}] not found in config.ini")
                result.plugin_instantiated = TestResult.SKIP
                result.connection_attempted = TestResult.SKIP
                result.connection_successful = TestResult.SKIP
                result.static_data_read = TestResult.SKIP
                result.dynamic_data_read = TestResult.SKIP
                result.data_structure_valid = TestResult.SKIP
                result.overall_result = TestResult.SKIP
                return result
                
            # Test 2: Plugin Instantiation
            self.logger.debug(f"  🔧 Testing plugin instantiation...")
            plugin_instance, instantiation_result = self._test_plugin_instantiation(
                plugin_info, config)
            result.plugin_instantiated = instantiation_result
            if instantiation_result == TestResult.FAIL:
                result.error_messages.append("Plugin instantiation failed")
                result.overall_result = TestResult.FAIL
                return result
                
            # Test 3: Interface Compliance
            self.logger.debug(f"  ✅ Testing interface compliance...")
            interface_result = self._test_interface_compliance(plugin_instance)
            if interface_result == TestResult.FAIL:
                result.error_messages.append("Interface compliance failed")
                result.warnings.append("Plugin may not implement all required methods")
                
            # Skip connection tests if offline mode
            if self.offline_only:
                result.connection_attempted = TestResult.SKIP
                result.connection_successful = TestResult.SKIP
                result.static_data_read = TestResult.SKIP
                result.dynamic_data_read = TestResult.SKIP
                result.data_structure_valid = TestResult.SKIP
                result.overall_result = TestResult.PASS if result.plugin_instantiated == TestResult.PASS else TestResult.FAIL
            else:
                # Test 4: Connection Attempt
                self.logger.debug(f"  🔌 Testing connection...")
                connection_result = self._test_connection(plugin_instance)
                result.connection_attempted = TestResult.PASS
                result.connection_successful = connection_result
                
                if connection_result == TestResult.PASS:
                    # Test 5: Static Data Reading
                    self.logger.debug(f"  📊 Testing static data reading...")
                    static_data, static_result = self._test_static_data_reading(plugin_instance)
                    result.static_data_read = static_result
                    if static_data:
                        result.data_samples['static_data'] = static_data
                        
                    # Test 6: Dynamic Data Reading  
                    self.logger.debug(f"  ⚡ Testing dynamic data reading...")
                    dynamic_data, dynamic_result = self._test_dynamic_data_reading(plugin_instance)
                    result.dynamic_data_read = dynamic_result
                    if dynamic_data:
                        result.data_samples['dynamic_data'] = dynamic_data
                        
                    # Test 7: Data Structure Validation
                    self.logger.debug(f"  🔍 Testing data structure validation...")
                    structure_result = self._test_data_structure_validation(static_data, dynamic_data)
                    result.data_structure_valid = structure_result
                    
                    # Disconnect cleanly
                    try:
                        plugin_instance.disconnect()
                    except Exception as e:
                        result.warnings.append(f"Disconnect error: {e}")
                else:
                    result.static_data_read = TestResult.SKIP
                    result.dynamic_data_read = TestResult.SKIP
                    result.data_structure_valid = TestResult.SKIP
                    result.warnings.append("Connection failed - skipping data tests")
                    
                # Determine overall result
                if connection_result == TestResult.PASS:
                    if (result.static_data_read == TestResult.PASS and 
                        result.dynamic_data_read == TestResult.PASS and
                        result.data_structure_valid == TestResult.PASS):
                        result.overall_result = TestResult.PASS
                    else:
                        result.overall_result = TestResult.WARN
                else:
                    result.overall_result = TestResult.WARN  # Plugin loads but can't connect
                    
        except Exception as e:
            result.error_messages.append(f"Unexpected error: {str(e)}")
            result.overall_result = TestResult.FAIL
            self.logger.error(f"  ❌ Unexpected error testing {plugin_type}: {e}")
            if self.verbose:
                self.logger.debug(traceback.format_exc())
                
        finally:
            result.test_duration = time.time() - start_time
            
        return result
    
    def _test_config_loading(self, instance_name: str) -> Tuple[Optional[Dict[str, Any]], TestResult]:
        """Test configuration loading for a plugin."""
        try:
            config = load_plugin_config_from_file(self.config_file, instance_name)
            if config and isinstance(config, dict):
                return config, TestResult.PASS
            else:
                return None, TestResult.FAIL
        except FileNotFoundError:
            return None, TestResult.SKIP  # Config file doesn't exist
        except ValueError as e:
            return None, TestResult.SKIP  # Plugin section doesn't exist
        except Exception as e:
            return None, TestResult.FAIL
    
    def _test_plugin_instantiation(self, plugin_info: Dict[str, Any], 
                                 config: Dict[str, Any]) -> Tuple[Optional[DevicePlugin], TestResult]:
        """Test plugin instantiation."""
        try:
            # Dynamic import of plugin module
            module_path = plugin_info['module_path']
            class_name = plugin_info['class_name']
            
            module = __import__(module_path, fromlist=[class_name])
            plugin_class = getattr(module, class_name)
            
            # Instantiate plugin
            plugin_instance = plugin_class(
                instance_name=f"Test{plugin_info['default_instance']}",
                plugin_specific_config=config,
                main_logger=self.logger
            )
            
            return plugin_instance, TestResult.PASS
            
        except ImportError as e:
            return None, TestResult.FAIL
        except AttributeError as e:
            return None, TestResult.FAIL
        except Exception as e:
            return None, TestResult.FAIL
    
    def _test_interface_compliance(self, plugin_instance: DevicePlugin) -> TestResult:
        """Test that plugin implements required interface methods."""
        required_methods = ['connect', 'disconnect', 'read_static_data', 'read_dynamic_data']
        required_properties = ['name', 'pretty_name', 'is_connected']
        
        try:
            # Check methods
            for method_name in required_methods:
                if not hasattr(plugin_instance, method_name):
                    return TestResult.FAIL
                method = getattr(plugin_instance, method_name)
                if not callable(method):
                    return TestResult.FAIL
                    
            # Check properties
            for prop_name in required_properties:
                if not hasattr(plugin_instance, prop_name):
                    return TestResult.FAIL
                    
            return TestResult.PASS
            
        except Exception as e:
            return TestResult.FAIL
    
    def _test_connection(self, plugin_instance: DevicePlugin) -> TestResult:
        """Test plugin connection with timeout protection."""
        try:
            # Set a reasonable timeout for connection attempts
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Connection attempt timed out")
            
            # Set timeout (only on Unix-like systems)
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)  # 30 second timeout
            
            try:
                connected = plugin_instance.connect()
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)  # Cancel timeout
                    
                return TestResult.PASS if connected else TestResult.FAIL
                
            except TimeoutError:
                return TestResult.FAIL
            except Exception as e:
                return TestResult.FAIL
                
        except Exception as e:
            return TestResult.FAIL
    
    def _test_static_data_reading(self, plugin_instance: DevicePlugin) -> Tuple[Optional[Dict[str, Any]], TestResult]:
        """Test static data reading."""
        try:
            static_data = plugin_instance.read_static_data()
            if static_data and isinstance(static_data, dict):
                return static_data, TestResult.PASS
            else:
                return None, TestResult.FAIL
        except Exception as e:
            return None, TestResult.FAIL
    
    def _test_dynamic_data_reading(self, plugin_instance: DevicePlugin) -> Tuple[Optional[Dict[str, Any]], TestResult]:
        """Test dynamic data reading."""
        try:
            dynamic_data = plugin_instance.read_dynamic_data()
            if dynamic_data and isinstance(dynamic_data, dict):
                return dynamic_data, TestResult.PASS
            else:
                return None, TestResult.FAIL
        except Exception as e:
            return None, TestResult.FAIL
    
    def _test_data_structure_validation(self, static_data: Optional[Dict[str, Any]], 
                                      dynamic_data: Optional[Dict[str, Any]]) -> TestResult:
        """Validate that data structures contain expected StandardDataKeys."""
        try:
            issues = []
            
            # Check static data structure
            if static_data:
                required_static_keys = [
                    StandardDataKeys.STATIC_DEVICE_CATEGORY,
                ]
                for key in required_static_keys:
                    if key not in static_data:
                        issues.append(f"Missing required static key: {key}")
                        
            # Check dynamic data structure  
            if dynamic_data:
                # At least some operational data should be present
                operational_keys = [k for k in dynamic_data.keys() 
                                  if k.startswith('operational_') or k.startswith('battery_') 
                                  or k.startswith('pv_') or k.startswith('grid_')]
                if not operational_keys:
                    issues.append("No operational data keys found in dynamic data")
                    
            return TestResult.PASS if not issues else TestResult.WARN
            
        except Exception as e:
            return TestResult.FAIL
    
    def _log_test_result(self, result: PluginTestResult):
        """Log the test result for a single plugin."""
        status_emoji = {
            TestResult.PASS: "✅",
            TestResult.FAIL: "❌", 
            TestResult.WARN: "⚠️",
            TestResult.SKIP: "⏭️"
        }
        
        emoji = status_emoji.get(result.overall_result, "❓")
        self.logger.info(f"  {emoji} {result.plugin_name} - {result.overall_result.value} ({result.test_duration:.2f}s)")
        
        if result.error_messages:
            for error in result.error_messages:
                self.logger.error(f"    ❌ {error}")
                
        if result.warnings:
            for warning in result.warnings:
                self.logger.warning(f"    ⚠️ {warning}")
    
    def generate_summary_report(self) -> str:
        """Generate a comprehensive summary report."""
        if not self.results:
            return "No test results available."
            
        # Count results by status
        status_counts = {status: 0 for status in TestResult}
        for result in self.results:
            status_counts[result.overall_result] += 1
            
        # Calculate success rate
        total_tests = len(self.results)
        passed_tests = status_counts[TestResult.PASS]
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        report = []
        report.append("="*80)
        report.append("PLUGIN VALIDATION SUMMARY REPORT")
        report.append("="*80)
        report.append(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Config File: {self.config_file}")
        report.append(f"Test Mode: {'Offline Only' if self.offline_only else 'Full Validation'}")
        report.append(f"Plugin Filter: {self.plugin_type_filter}")
        report.append("")
        
        # Overall statistics
        report.append("OVERALL STATISTICS:")
        report.append(f"  Total Plugins Tested: {total_tests}")
        report.append(f"  Passed: {status_counts[TestResult.PASS]} ✅")
        report.append(f"  Failed: {status_counts[TestResult.FAIL]} ❌")
        report.append(f"  Warnings: {status_counts[TestResult.WARN]} ⚠️")
        report.append(f"  Skipped: {status_counts[TestResult.SKIP]} ⏭️")
        report.append(f"  Success Rate: {success_rate:.1f}%")
        report.append("")
        
        # Detailed results by category
        inverter_results = [r for r in self.results if r.plugin_type == 'inverter']
        bms_results = [r for r in self.results if r.plugin_type == 'bms']
        
        if inverter_results:
            report.append("INVERTER PLUGINS:")
            for result in inverter_results:
                status_emoji = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭️"}
                emoji = status_emoji.get(result.overall_result.value, "❓")
                report.append(f"  {emoji} {result.plugin_name}")
                report.append(f"    Config: {result.config_loaded.value}")
                report.append(f"    Instantiation: {result.plugin_instantiated.value}")
                if not self.offline_only:
                    report.append(f"    Connection: {result.connection_successful.value}")
                    report.append(f"    Data Reading: {result.static_data_read.value}/{result.dynamic_data_read.value}")
                report.append(f"    Duration: {result.test_duration:.2f}s")
                if result.error_messages:
                    report.append(f"    Errors: {'; '.join(result.error_messages)}")
                report.append("")
                
        if bms_results:
            report.append("BMS PLUGINS:")
            for result in bms_results:
                status_emoji = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "SKIP": "⏭️"}
                emoji = status_emoji.get(result.overall_result.value, "❓")
                report.append(f"  {emoji} {result.plugin_name}")
                report.append(f"    Config: {result.config_loaded.value}")
                report.append(f"    Instantiation: {result.plugin_instantiated.value}")
                if not self.offline_only:
                    report.append(f"    Connection: {result.connection_successful.value}")
                    report.append(f"    Data Reading: {result.static_data_read.value}/{result.dynamic_data_read.value}")
                report.append(f"    Duration: {result.test_duration:.2f}s")
                if result.error_messages:
                    report.append(f"    Errors: {'; '.join(result.error_messages)}")
                report.append("")
        
        # Recommendations
        report.append("RECOMMENDATIONS:")
        failed_results = [r for r in self.results if r.overall_result == TestResult.FAIL]
        if failed_results:
            report.append("  Failed Plugins:")
            for result in failed_results:
                report.append(f"    • {result.plugin_name}: Check plugin implementation and dependencies")
                
        warn_results = [r for r in self.results if r.overall_result == TestResult.WARN]
        if warn_results:
            report.append("  Warning Plugins:")
            for result in warn_results:
                report.append(f"    • {result.plugin_name}: Plugin loads but has connection/data issues")
                
        if not self.offline_only:
            no_config_results = [r for r in self.results if r.config_loaded == TestResult.SKIP]
            if no_config_results:
                report.append("  Missing Configurations:")
                for result in no_config_results:
                    report.append(f"    • Add [PLUGIN_{result.instance_name}] section to config.ini")
                    
        report.append("")
        report.append("="*80)
        
        return "\n".join(report)
    
    def save_detailed_report(self, filename: str):
        """Save a detailed report including data samples."""
        report = []
        report.append("DETAILED PLUGIN VALIDATION REPORT")
        report.append("="*80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Config File: {self.config_file}")
        report.append(f"Test Mode: {'Offline Only' if self.offline_only else 'Full Validation'}")
        report.append("")
        
        for result in self.results:
            report.append(f"PLUGIN: {result.plugin_name}")
            report.append("-" * 60)
            report.append(f"Type: {result.plugin_type}")
            report.append(f"Instance: {result.instance_name}")
            report.append(f"Overall Result: {result.overall_result.value}")
            report.append(f"Test Duration: {result.test_duration:.2f}s")
            report.append("")
            
            report.append("Test Results:")
            report.append(f"  Configuration Loading: {result.config_loaded.value}")
            report.append(f"  Plugin Instantiation: {result.plugin_instantiated.value}")
            report.append(f"  Connection Attempted: {result.connection_attempted.value}")
            report.append(f"  Connection Successful: {result.connection_successful.value}")
            report.append(f"  Static Data Read: {result.static_data_read.value}")
            report.append(f"  Dynamic Data Read: {result.dynamic_data_read.value}")
            report.append(f"  Data Structure Valid: {result.data_structure_valid.value}")
            report.append("")
            
            if result.error_messages:
                report.append("Errors:")
                for error in result.error_messages:
                    report.append(f"  • {error}")
                report.append("")
                
            if result.warnings:
                report.append("Warnings:")
                for warning in result.warnings:
                    report.append(f"  • {warning}")
                report.append("")
                
            if result.data_samples:
                report.append("Data Samples:")
                for data_type, data in result.data_samples.items():
                    report.append(f"  {data_type.title()}:")
                    if isinstance(data, dict):
                        for key, value in list(data.items())[:10]:  # Limit to first 10 items
                            report.append(f"    {key}: {value}")
                        if len(data) > 10:
                            report.append(f"    ... and {len(data) - 10} more items")
                    report.append("")
                    
            report.append("="*80)
            report.append("")
            
        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("\n".join(report))


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Comprehensive Plugin Validation Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Test all plugins with connections
  %(prog)s --offline-only               # Test only plugin loading
  %(prog)s --plugin-type inverter       # Test only inverter plugins  
  %(prog)s --report-file report.txt     # Generate detailed report
  %(prog)s --verbose                    # Enable verbose logging
        """
    )
    
    parser.add_argument('--offline-only', action='store_true',
                       help='Skip actual device connections (test plugin loading only)')
    parser.add_argument('--plugin-type', choices=['all', 'inverter', 'bms'], default='all',
                       help='Test only specific plugin type')
    parser.add_argument('--config-file', default='config.ini',
                       help='Use custom config file')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--report-file', 
                       help='Save detailed report to file')
    
    args = parser.parse_args()
    
    # Create validator
    validator = PluginValidator(
        config_file=args.config_file,
        offline_only=args.offline_only,
        plugin_type_filter=args.plugin_type,
        verbose=args.verbose
    )
    
    try:
        # Run validation
        results = validator.validate_all_plugins()
        
        # Generate and display summary
        summary = validator.generate_summary_report()
        print(summary)
        
        # Save detailed report if requested
        if args.report_file:
            validator.save_detailed_report(args.report_file)
            print(f"\nDetailed report saved to: {args.report_file}")
            
        # Exit with appropriate code
        failed_count = sum(1 for r in results if r.overall_result == TestResult.FAIL)
        sys.exit(1 if failed_count > 0 else 0)
        
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during validation: {e}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()