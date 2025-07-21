#!/usr/bin/env python3
"""
Quick Plugin Health Check

A lightweight script to quickly verify that all plugins can be loaded and instantiated.
This is useful for CI/CD pipelines and quick development checks.

Usage:
    python test_plugins/quick_plugin_check.py

Features:
- Fast execution (no actual connections)
- Tests plugin loading and basic instantiation
- Validates interface compliance
- Generates concise pass/fail report
- Exit code indicates overall success/failure

GitHub: https://github.com/jcvsite/solar-monitoring
"""

import os
import sys
import logging
from typing import Dict, List, Tuple

# Setup project path
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir)
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

# Import plugin interface
from plugins.plugin_interface import DevicePlugin


class QuickPluginChecker:
    """Quick plugin health checker."""
    
    # Plugin registry for quick checks
    PLUGINS = {
        'Solis Modbus': {
            'module': 'plugins.inverter.solis_modbus_plugin',
            'class': 'SolisModbusPlugin',
            'type': 'inverter'
        },
        'LuxPower Modbus': {
            'module': 'plugins.inverter.luxpower_modbus_plugin', 
            'class': 'LuxpowerModbusPlugin',
            'type': 'inverter'
        },
        'POWMR RS232': {
            'module': 'plugins.inverter.powmr_rs232_plugin',
            'class': 'PowmrCustomRs232Plugin', 
            'type': 'inverter'
        },
        'Deye/Sunsynk': {
            'module': 'plugins.inverter.deye_sunsynk_plugin',
            'class': 'DeyeSunsynkPlugin',
            'type': 'inverter'
        },
        'Seplos BMS V2': {
            'module': 'plugins.battery.seplos_bms_v2_plugin',
            'class': 'SeplosBMSV2',
            'type': 'bms'
        },
        'Seplos BMS V3': {
            'module': 'plugins.battery.seplos_bms_v3_plugin', 
            'class': 'SeplosBmsV3Plugin',
            'type': 'bms'
        },
        'JK BMS': {
            'module': 'plugins.battery.jk_bms_plugin',
            'class': 'JkBmsModbusPlugin',
            'type': 'bms'
        }
    }
    
    def __init__(self):
        """Initialize the checker."""
        # Suppress logging for clean output
        logging.getLogger().setLevel(logging.CRITICAL)
        self.results = []
        
    def check_all_plugins(self) -> List[Tuple[str, bool, str]]:
        """Check all plugins quickly."""
        print("🔍 Quick Plugin Health Check")
        print("=" * 50)
        
        for plugin_name, plugin_info in self.PLUGINS.items():
            success, message = self._check_single_plugin(plugin_name, plugin_info)
            self.results.append((plugin_name, success, message))
            
            # Print result
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {plugin_name:<20} {message}")
            
        return self.results
    
    def _check_single_plugin(self, plugin_name: str, plugin_info: Dict[str, str]) -> Tuple[bool, str]:
        """Check a single plugin."""
        try:
            # Test import
            module = __import__(plugin_info['module'], fromlist=[plugin_info['class']])
            plugin_class = getattr(module, plugin_info['class'])
            
            # Test instantiation with minimal config
            minimal_config = {
                'connection_type': 'tcp',
                'tcp_host': 'localhost',
                'tcp_port': 502,
                'slave_address': 1
            }
            
            # Create dummy logger
            import logging
            logger = logging.getLogger(f"Test{plugin_name}")
            
            # Instantiate plugin
            plugin_instance = plugin_class(
                instance_name=f"Test{plugin_name}",
                plugin_specific_config=minimal_config,
                main_logger=logger
            )
            
            # Check interface compliance
            required_methods = ['connect', 'disconnect', 'read_static_data', 'read_dynamic_data']
            required_properties = ['name', 'pretty_name', 'is_connected']
            
            for method_name in required_methods:
                if not hasattr(plugin_instance, method_name) or not callable(getattr(plugin_instance, method_name)):
                    return False, f"Missing method: {method_name}"
                    
            for prop_name in required_properties:
                if not hasattr(plugin_instance, prop_name):
                    return False, f"Missing property: {prop_name}"
            
            # Test basic properties
            try:
                name = plugin_instance.name
                pretty_name = plugin_instance.pretty_name
                is_connected = plugin_instance.is_connected
            except Exception as e:
                return False, f"Property access error: {e}"
            
            return True, "Plugin loads and instantiates correctly"
            
        except ImportError as e:
            return False, f"Import error: {str(e)}"
        except AttributeError as e:
            return False, f"Class not found: {str(e)}"
        except Exception as e:
            return False, f"Instantiation error: {str(e)}"
    
    def print_summary(self):
        """Print summary of results."""
        total = len(self.results)
        passed = sum(1 for _, success, _ in self.results if success)
        failed = total - passed
        
        print("\n" + "=" * 50)
        print("SUMMARY:")
        print(f"  Total Plugins: {total}")
        print(f"  Passed: {passed} ✅")
        print(f"  Failed: {failed} ❌")
        print(f"  Success Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print("\nFailed Plugins:")
            for plugin_name, success, message in self.results:
                if not success:
                    print(f"  ❌ {plugin_name}: {message}")
        
        print("=" * 50)
        
        return failed == 0


def main():
    """Main execution."""
    checker = QuickPluginChecker()
    
    try:
        # Run checks
        results = checker.check_all_plugins()
        
        # Print summary and exit with appropriate code
        success = checker.print_summary()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nCheck interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()