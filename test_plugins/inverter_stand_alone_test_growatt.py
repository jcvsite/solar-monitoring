# inverter_stand_alone_test_growatt.py
"""
A standalone test script for the plugins\inverter\growatt_modbus_plugin.
This script loads configuration from config.ini and tests the inverter connection
without running the full monitoring application.

Instructions:
1. Place this script in the 'test_plugins' directory.
2. Configure your inverter settings in config.ini under [PLUGIN_INV_Growatt]
3. Run the script from your terminal: python inverter_stand_alone_test_growatt.py

Optional: You can override the config instance name by setting the environment variable:
   set INVERTER_INSTANCE_NAME=INV_Growatt
   python inverter_stand_alone_test_growatt.py
"""
import logging
import time
import sys
import os
import configparser
from pprint import pformat

# --- Setup Project Path ---
# This allows the script to find project modules (like the plugin itself).
# It adds the parent 'solar_monitoring' directory to the Python path.
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir)
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

# Now, project-level imports will work
from plugins.inverter.growatt_modbus_plugin import GrowattModbusPlugin
from test_plugins.test_config_loader import load_inverter_config_from_file


def pretty_print_data(data_dict, title="Data"):
    """Helper function to print dictionaries in a readable format."""
    print(f"\n--- {title} ---")
    if not data_dict:
        print("  (No data returned)")
        return
    
    # Using pformat for a cleaner print of complex structures
    formatted_string = pformat(data_dict, indent=2, width=120)
    print(formatted_string)


if __name__ == "__main__":
    # Configure basic logging to the console
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s [%(threadName)s] %(message)s')
    
    # Get the instance name from environment variable or use default
    instance_name = os.environ.get('INVERTER_INSTANCE_NAME', 'INV_Growatt')
    
    print("="*80)
    print("Growatt Modbus Inverter Plugin - Standalone Test")
    print("="*80)
    print(f"Testing instance: {instance_name}")
    print(f"Config file: config.ini")
    print("="*80)
    
    try:
        # Load configuration
        print("\n🔧 Loading configuration...")
        config = load_inverter_config_from_file("config.ini", instance_name)
        print(f"✅ Configuration loaded successfully")
        print(f"   Connection type: {config.get('connection_type', 'Not specified')}")
        if config.get('connection_type') == 'tcp':
            print(f"   TCP Host: {config.get('tcp_host', 'Not specified')}")
            print(f"   TCP Port: {config.get('tcp_port', 'Not specified')}")
        else:
            print(f"   Serial Port: {config.get('serial_port', 'Not specified')}")
            print(f"   Baud Rate: {config.get('baud_rate', 'Not specified')}")
        print(f"   Slave Address: {config.get('slave_address', 'Not specified')}")
        
        # Create plugin instance
        print("\n🔌 Creating Growatt plugin instance...")
        plugin = GrowattModbusPlugin(
            instance_name=f"Test_{instance_name}",
            plugin_specific_config=config,
            main_logger=logging.getLogger("GrowattTest")
        )
        print(f"✅ Plugin instance created successfully")
        print(f"   Plugin name: {plugin.name}")
        print(f"   Pretty name: {plugin.pretty_name}")
        
        # Test connection
        print("\n🌐 Testing connection...")
        start_time = time.time()
        connected = plugin.connect()
        connection_time = time.time() - start_time
        
        if connected:
            print(f"✅ Connection successful! ({connection_time:.2f}s)")
            print(f"   Connection status: {plugin.is_connected}")
            
            # Test static data reading
            print("\n📊 Reading static data...")
            static_data = plugin.read_static_data()
            if static_data:
                print("✅ Static data read successfully")
                pretty_print_data(static_data, "Static Data")
            else:
                print("❌ Failed to read static data")
            
            # Test dynamic data reading
            print("\n⚡ Reading dynamic data...")
            dynamic_data = plugin.read_dynamic_data()
            if dynamic_data:
                print("✅ Dynamic data read successfully")
                pretty_print_data(dynamic_data, "Dynamic Data")
                
                # Show key operational values
                print("\n--- Key Operational Values ---")
                print(f"  Inverter Status: {dynamic_data.get('operational_inverter_status_text', 'N/A')}")
                print(f"  Battery Status: {dynamic_data.get('battery_status_text', 'N/A')}")
                print(f"  AC Power: {dynamic_data.get('ac_power_watts', 'N/A')} W")
                print(f"  PV Power: {dynamic_data.get('pv_total_dc_power_watts', 'N/A')} W")
                print(f"  Battery Power: {dynamic_data.get('battery_power_watts', 'N/A')} W")
                print(f"  Battery SOC: {dynamic_data.get('battery_state_of_charge_percent', 'N/A')} %")
                print(f"  Grid Power: {dynamic_data.get('grid_total_active_power_watts', 'N/A')} W")
                print(f"  Load Power: {dynamic_data.get('load_total_power_watts', 'N/A')} W")
                
                # Show energy statistics
                print("\n--- Energy Statistics ---")
                print(f"  PV Daily: {dynamic_data.get('energy_pv_daily_kwh', 'N/A')} kWh")
                print(f"  PV Total: {dynamic_data.get('energy_pv_total_lifetime_kwh', 'N/A')} kWh")
                print(f"  Battery Charge Daily: {dynamic_data.get('energy_battery_daily_charge_kwh', 'N/A')} kWh")
                print(f"  Battery Discharge Daily: {dynamic_data.get('energy_battery_daily_discharge_kwh', 'N/A')} kWh")
                
                # Show alerts if any
                alerts = dynamic_data.get('operational_categorized_alerts_dict', {})
                if alerts:
                    print("\n--- Alerts ---")
                    for category, alert_list in alerts.items():
                        if alert_list and alert_list != ["OK"]:
                            print(f"  {category.upper()}: {', '.join(alert_list)}")
                        elif alert_list == ["OK"]:
                            print(f"  {category.upper()}: OK")
            else:
                print("❌ Failed to read dynamic data")
            
            # Test multiple reads to check consistency
            print("\n🔄 Testing multiple reads for consistency...")
            for i in range(3):
                print(f"   Read {i+1}/3...", end=" ")
                test_data = plugin.read_dynamic_data()
                if test_data:
                    status = test_data.get('operational_inverter_status_text', 'N/A')
                    power = test_data.get('ac_power_watts', 'N/A')
                    print(f"Status: {status}, Power: {power} W")
                else:
                    print("Failed")
                time.sleep(1)
            
            # Disconnect
            print("\n🔌 Disconnecting...")
            plugin.disconnect()
            print(f"✅ Disconnected. Connection status: {plugin.is_connected}")
            
        else:
            print(f"❌ Connection failed! ({connection_time:.2f}s)")
            if hasattr(plugin, 'last_error_message') and plugin.last_error_message:
                print(f"   Error: {plugin.last_error_message}")
            print("   Please check your configuration and device connectivity.")
            
    except FileNotFoundError:
        print("❌ Configuration file 'config.ini' not found!")
        print("   Please copy 'config.ini.example' to 'config.ini' and configure your settings.")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print(f"   Please check the [{instance_name}] section in config.ini")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("Test completed!")
    print("="*80)