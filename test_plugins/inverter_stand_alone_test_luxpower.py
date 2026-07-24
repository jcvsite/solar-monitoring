# inverter_stand_alone_test_luxpower.py
"""
A standalone test script for the plugins\inverter\luxpower_modbus_plugin.
This script loads configuration from config.ini and tests the inverter connection
without running the full monitoring application.

Instructions:
1. Place this script in the 'test_plugins' directory.
2. Configure your inverter settings in config.ini under [PLUGIN_INV_LuxPower]
3. Run the script from your terminal: python inverter_stand_alone_test_luxpower.py

Optional: You can override the config instance name by setting the environment variable:
   set INVERTER_INSTANCE_NAME=INV_LuxPower
   python inverter_stand_alone_test_luxpower.py

Supported LuxPower Models:
- LXP-5K: 5kW hybrid inverter
- LXP-12K: 12kW hybrid inverter  
- LXP-LB-5K: 5kW low-battery hybrid inverter

Connection Types:
- TCP: For network-based communication (default port 8000 for lxp-bridge)
- Serial: For direct RS485/RS232 communication

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
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
from plugins.inverter.luxpower_modbus_plugin import LuxpowerModbusPlugin
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


def print_luxpower_info():
    """Print information about LuxPower inverters and supported features."""
    print("\n" + "="*80)
    print("LuxPower Modbus Plugin Test")
    print("="*80)
    print("Supported Models:")
    print("  • LXP-5K: 5kW hybrid inverter")
    print("  • LXP-12K: 12kW hybrid inverter")
    print("  • LXP-LB-5K: 5kW low-battery hybrid inverter")
    print("\nConnection Types:")
    print("  • TCP: Network-based communication (default port 8000 for lxp-bridge)")
    print("  • Serial: Direct RS485/RS232 communication")
    print("\nFeatures Tested:")
    print("  • Static data: Model, serial number, firmware version")
    print("  • Dynamic data: PV generation, battery status, grid interaction")
    print("  • Energy statistics: Daily and total lifetime values")
    print("  • Temperature monitoring: Inverter and battery sensors")
    print("="*80)


def analyze_luxpower_data(static_data, dynamic_data):
    """Analyze and provide insights about the LuxPower data."""
    print("\n" + "="*60)
    print("LuxPower Data Analysis")
    print("="*60)
    
    if static_data:
        print("\n📋 Device Information:")
        manufacturer = static_data.get("static_inverter_manufacturer", "Unknown")
        model = static_data.get("static_inverter_model_name", "Unknown")
        serial = static_data.get("static_inverter_serial_number", "Unknown")
        firmware = static_data.get("static_inverter_firmware_version", "Unknown")
        mppts = static_data.get("static_number_of_mppts", "Unknown")
        phases = static_data.get("static_number_of_phases_ac", "Unknown")
        
        print(f"  • Manufacturer: {manufacturer}")
        print(f"  • Model: {model}")
        print(f"  • Serial Number: {serial}")
        print(f"  • Firmware: {firmware}")
        print(f"  • MPPTs: {mppts}")
        print(f"  • AC Phases: {phases}")
    
    if dynamic_data:
        print("\n⚡ Current Status:")
        status = dynamic_data.get("operational_inverter_status_text", "Unknown")
        battery_status = dynamic_data.get("battery_status_text", "Unknown")
        print(f"  • Inverter Status: {status}")
        print(f"  • Battery Status: {battery_status}")
        
        print("\n🔋 Power Flow:")
        pv_power = dynamic_data.get("pv_total_dc_power_watts", 0)
        ac_power = dynamic_data.get("ac_power_watts", 0)
        grid_power = dynamic_data.get("grid_total_active_power_watts", 0)
        battery_power = dynamic_data.get("battery_power_watts", 0)
        load_power = dynamic_data.get("load_total_power_watts", 0)
        
        print(f"  • PV Generation: {pv_power}W")
        print(f"  • AC Output: {ac_power}W")
        print(f"  • Grid Power: {grid_power}W")
        print(f"  • Battery Power: {battery_power}W")
        print(f"  • Load Power: {load_power}W")
        
        print("\n🌡️ Temperatures:")
        inv_temp = dynamic_data.get("operational_inverter_temperature_celsius")
        batt_temp = dynamic_data.get("battery_temperature_celsius")
        if inv_temp is not None:
            print(f"  • Inverter: {inv_temp}°C")
        if batt_temp is not None:
            print(f"  • Battery: {batt_temp}°C")
        
        print("\n🔌 MPPT Data:")
        for i in range(1, 3):  # LuxPower typically has 2 MPPTs
            voltage_key = f"pv_mppt{i}_voltage_volts"
            current_key = f"pv_mppt{i}_current_amps"
            power_key = f"pv_mppt{i}_power_watts"
            
            voltage = dynamic_data.get(voltage_key)
            current = dynamic_data.get(current_key)
            power = dynamic_data.get(power_key)
            
            if voltage is not None or current is not None or power is not None:
                print(f"  • MPPT{i}: {voltage or 0}V, {current or 0}A, {power or 0}W")
        
        print("\n🔋 Battery Details:")
        batt_voltage = dynamic_data.get("battery_voltage_volts")
        batt_current = dynamic_data.get("battery_current_amps")
        batt_soc = dynamic_data.get("battery_state_of_charge_percent")
        
        if batt_voltage is not None:
            print(f"  • Voltage: {batt_voltage}V")
        if batt_current is not None:
            print(f"  • Current: {batt_current}A")
        if batt_soc is not None:
            print(f"  • State of Charge: {batt_soc}%")
        
        print("\n📊 Energy Statistics:")
        pv_daily = dynamic_data.get("energy_pv_daily_kwh")
        pv_total = dynamic_data.get("energy_pv_total_lifetime_kwh")
        batt_charge_daily = dynamic_data.get("energy_battery_daily_charge_kwh")
        batt_discharge_daily = dynamic_data.get("energy_battery_daily_discharge_kwh")
        
        if pv_daily is not None:
            print(f"  • PV Today: {pv_daily}kWh")
        if pv_total is not None:
            print(f"  • PV Total: {pv_total}kWh")
        if batt_charge_daily is not None:
            print(f"  • Battery Charge Today: {batt_charge_daily}kWh")
        if batt_discharge_daily is not None:
            print(f"  • Battery Discharge Today: {batt_discharge_daily}kWh")


if __name__ == "__main__":
    # Configure basic logging to the console
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s [%(threadName)s] %(message)s')
    logger = logging.getLogger("LuxPowerStandaloneTest")

    # Print LuxPower information
    print_luxpower_info()

    # --- Load Configuration from config.ini ---
    config_file_path = os.path.join(project_root_dir, "config.ini")
    
    # Allow override of instance name via environment variable
    inverter_instance_name = os.environ.get("INVERTER_INSTANCE_NAME", "INV_LuxPower")
    
    try:
        luxpower_config = load_inverter_config_from_file(config_file_path, inverter_instance_name)
        logger.info(f"Loaded configuration for instance '{inverter_instance_name}' from {config_file_path}")
        logger.info(f"Full config loaded: {luxpower_config}")
        logger.info(f"Connection type: {luxpower_config['connection_type']}")
        if luxpower_config['connection_type'] == 'tcp':
            logger.info(f"TCP Host: {luxpower_config['tcp_host']}:{luxpower_config['tcp_port']}")
        else:
            logger.info(f"Serial Port: {luxpower_config['serial_port']} @ {luxpower_config['baud_rate']} baud")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please ensure config.ini exists and contains a [PLUGIN_INV_LuxPower] section with proper inverter settings.")
        logger.error("\nExample TCP Configuration:")
        logger.error("[PLUGIN_INV_LuxPower]")
        logger.error("plugin_type = inverter.luxpower_modbus_plugin")
        logger.error("connection_type = tcp")
        logger.error("tcp_host = 192.168.1.100")
        logger.error("tcp_port = 8000")
        logger.error("slave_address = 1")
        logger.error("\nExample Serial Configuration:")
        logger.error("[PLUGIN_INV_LuxPower]")
        logger.error("plugin_type = inverter.luxpower_modbus_plugin")
        logger.error("connection_type = serial")
        logger.error("serial_port = COM3")
        logger.error("baud_rate = 9600")
        logger.error("slave_address = 1")
        sys.exit(1)

    logger.info(f"Attempting to instantiate LuxpowerModbusPlugin with config: {luxpower_config}")
    try:
        luxpower_plugin = LuxpowerModbusPlugin(
            instance_name=luxpower_config.get("instance_name", "TestLuxPower"),
            plugin_specific_config=luxpower_config,
            main_logger=logger
        )
    except Exception as e:
        logger.error(f"Error during LuxpowerModbusPlugin instantiation: {e}", exc_info=True)
        sys.exit(1)

    logger.info("LuxpowerModbusPlugin instantiated. Attempting to connect...")
    if luxpower_plugin.connect():
        logger.info("Successfully connected to LuxPower Inverter.")
        
        # 1. Read Static Data (once after connection)
        logger.info("\n>>> Reading Static Data...")
        static_info = luxpower_plugin.read_static_data()
        if static_info:
            pretty_print_data(static_info, "Static Inverter Information")
        else:
            logger.error(f"Failed to read static data. Last error: {luxpower_plugin.last_error_message}")

        # 2. Read Dynamic Data (in a loop)
        dynamic_info = None
        try:
            for i in range(10): # Read data a few times
                logger.info(f"\n>>> Reading Dynamic Data (Cycle {i+1}) <<<")
                dynamic_data = luxpower_plugin.read_dynamic_data()
                if dynamic_data:
                    pretty_print_data(dynamic_data, f"Dynamic Data (Cycle {i+1})")
                    if i == 0:  # Store first successful read for analysis
                        dynamic_info = dynamic_data
                else:
                    logger.error(f"Failed to read dynamic data. Last error: {luxpower_plugin.last_error_message}")
                
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Test interrupted by user.")
        finally:
            # Analyze the data before disconnecting
            if static_info or dynamic_info:
                analyze_luxpower_data(static_info, dynamic_info)
            
            luxpower_plugin.disconnect()
            logger.info("Disconnected from LuxPower Inverter.")
    else:
        logger.error(f"Failed to connect to LuxPower Inverter. Check connection details. Last error: {luxpower_plugin.last_error_message}")
        logger.error("\nTroubleshooting Tips:")
        logger.error("1. Verify IP address and port (TCP) or serial port settings")
        logger.error("2. Check that Modbus is enabled on your LuxPower inverter")
        logger.error("3. For TCP: Ensure lxp-bridge or similar gateway is running")
        logger.error("4. For Serial: Check RS485 wiring and adapter configuration")
        logger.error("5. Verify slave_address matches your inverter configuration")
        logger.error("6. Check firewall settings if using TCP connection")