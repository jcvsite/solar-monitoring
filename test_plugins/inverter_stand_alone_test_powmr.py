# inverter_stand_alone_test_powmr.py
"""
A standalone test script for the plugins/inverter/powmr_rs232_plugin.
This script loads configuration from config.ini and tests the inverter connection
without running the full monitoring application.

Instructions:
1. Place this script in the 'test_plugins' directory.
2. Configure your inverter settings in config.ini under [PLUGIN_INV_POWMR]
3. Run the script from your terminal: python inverter_stand_alone_test_powmr.py

Optional: You can override the config instance name by setting the environment variable:
   set INVERTER_INSTANCE_NAME=INV_POWMR
   python inverter_stand_alone_test_powmr.py
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
from plugins.inverter.powmr_rs232_plugin import PowmrCustomRs232Plugin
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
    logger = logging.getLogger("PowmrStandaloneTest")

    # --- Load Configuration from config.ini ---
    config_file_path = os.path.join(project_root_dir, "config.ini")
    
    # Allow override of instance name via environment variable
    inverter_instance_name = os.environ.get("INVERTER_INSTANCE_NAME", "INV_POWMR")
    
    try:
        powmr_config = load_inverter_config_from_file(config_file_path, inverter_instance_name)
        logger.info(f"Loaded configuration for instance '{inverter_instance_name}' from {config_file_path}")
    except (FileNotFoundError, ValueError) as e:
        # Try fallback to old section name
        if inverter_instance_name == "INV_POWMR_RS232":
            logger.warning(f"Could not find [PLUGIN_INV_POWMR_RS232] section, trying [PLUGIN_INV_POWMR] for backward compatibility")
            try:
                inverter_instance_name = "INV_POWMR"
                powmr_config = load_inverter_config_from_file(config_file_path, inverter_instance_name)
                logger.info(f"Loaded configuration from legacy section [PLUGIN_{inverter_instance_name}]")
            except (FileNotFoundError, ValueError) as e2:
                logger.error(f"Configuration error: {e2}")
                logger.error("Please ensure config.ini exists and contains either [PLUGIN_INV_POWMR_RS232] or [PLUGIN_INV_POWMR] section with proper inverter settings.")
                sys.exit(1)
        else:
            logger.error(f"Configuration error: {e}")
            logger.error(f"Please ensure config.ini exists and contains a [PLUGIN_{inverter_instance_name}] section with proper inverter settings.")
            sys.exit(1)
    
    logger.info(f"Full config loaded: {powmr_config}")
    logger.info(f"Connection type: {powmr_config['connection_type']}")
    logger.info(f"Protocol version: {powmr_config.get('powmr_protocol_version', 1)}")
    if powmr_config['connection_type'] == 'tcp':
        logger.info(f"TCP Host: {powmr_config['tcp_host']}:{powmr_config['tcp_port']}")
    else:
        logger.info(f"Serial Port: {powmr_config['serial_port']} @ {powmr_config['baud_rate']} baud")

    logger.info(f"Attempting to instantiate PowmrCustomRs232Plugin with config: {powmr_config}")
    try:
        powmr_plugin = PowmrCustomRs232Plugin(
            instance_name=powmr_config.get("instance_name", "TestPowmr"),
            plugin_specific_config=powmr_config,
            main_logger=logger
        )
    except Exception as e:
        logger.error(f"Error during PowmrCustomRs232Plugin instantiation: {e}", exc_info=True)
        sys.exit(1)

    logger.info("PowmrCustomRs232Plugin instantiated. Attempting to connect...")
    if powmr_plugin.connect():
        logger.info("Successfully connected to POWMR Inverter.")
        
        # 1. Read Static Data (once after connection)
        logger.info("\n>>> Reading Static Data...")
        static_info = powmr_plugin.read_static_data()
        if static_info:
            pretty_print_data(static_info, "Static Inverter Information")
        else:
            logger.error(f"Failed to read static data. Last error: {powmr_plugin.last_error_message}")

        # 2. Read Dynamic Data (in a loop)
        try:
            for i in range(10): # Read data a few times
                logger.info(f"\n>>> Reading Dynamic Data (Cycle {i+1}) <<<")
                dynamic_data = powmr_plugin.read_dynamic_data()
                if dynamic_data:
                    pretty_print_data(dynamic_data, f"Dynamic Data (Cycle {i+1})")
                else:
                    logger.error(f"Failed to read dynamic data. Last error: {powmr_plugin.last_error_message}")
                
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Test interrupted by user.")
        finally:
            powmr_plugin.disconnect()
            logger.info("Disconnected from POWMR Inverter.")
    else:
        logger.error(f"Failed to connect to POWMR Inverter. Check connection details. Last error: {powmr_plugin.last_error_message}")
