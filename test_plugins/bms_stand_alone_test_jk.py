# bms_stand_alone_test_jk.py
"""
A standalone test script for the plugins\battery\jk_bms_modbus_plugin.
This script loads configuration from config.ini and tests the BMS connection
without running the full monitoring application.

Instructions:
1. Place this script in the 'test_plugins' directory.
2. Configure your BMS settings in config.ini under [PLUGIN_BMS_JK]
3. Run the script from your terminal: python bms_stand_alone_test_jk.py

Optional: You can override the config instance name by setting the environment variable:
   set BMS_INSTANCE_NAME=BMS_JK
   python bms_stand_alone_test_jk.py
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
from plugins.battery.jk_bms_plugin import JkBmsModbusPlugin
from test_plugins.test_config_loader import load_bms_config_from_file


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
    logger = logging.getLogger("JKBMSStandaloneTest")

    # --- Load Configuration from config.ini ---
    config_file_path = os.path.join(project_root_dir, "config.ini")
    
    # Allow override of instance name via environment variable
    bms_instance_name = os.environ.get("BMS_INSTANCE_NAME", "BMS_JK")
    
    try:
        jk_config = load_bms_config_from_file(config_file_path, bms_instance_name)
        logger.info(f"Loaded configuration for instance '{bms_instance_name}' from {config_file_path}")
        logger.info(f"Full config loaded: {jk_config}")
        logger.info(f"Connection type: {jk_config['connection_type']}")
        if jk_config['connection_type'] == 'tcp':
            logger.info(f"TCP Host: {jk_config['tcp_host']}:{jk_config['tcp_port']}")
        else:
            logger.info(f"Serial Port: {jk_config['serial_port']} @ {jk_config['baud_rate']} baud")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please ensure config.ini exists and contains a [PLUGIN_BMS_JK] section with proper BMS settings.")
        sys.exit(1)

    logger.info(f"Attempting to instantiate JkBmsModbusPlugin with config: {jk_config}")
    try:
        jk_plugin = JkBmsModbusPlugin(
            instance_name=jk_config.get("instance_name", "TestJK"),
            plugin_specific_config=jk_config,
            main_logger=logger
        )
    except Exception as e:
        logger.error(f"Error during JkBmsModbusPlugin instantiation: {e}", exc_info=True)
        sys.exit(1)

    logger.info("JkBmsModbusPlugin instantiated. Attempting to connect...")
    if jk_plugin.connect():
        logger.info("Successfully connected to JK BMS.")
        
        # 1. Read Static Data (once after connection)
        logger.info("\n>>> Reading Static Data...")
        static_info = jk_plugin.read_static_data()
        if static_info:
            pretty_print_data(static_info, "Static BMS Information")
        else:
            logger.error(f"Failed to read static data. Last error: {jk_plugin.last_error_message}")

        # 2. Read Dynamic Data (in a loop)
        try:
            for i in range(10): # Read data a few times
                logger.info(f"\n>>> Reading Dynamic Data (Cycle {i+1}) <<<")
                dynamic_data = jk_plugin.read_dynamic_data()
                if dynamic_data:
                    pretty_print_data(dynamic_data, f"Dynamic Data (Cycle {i+1})")
                else:
                    logger.error(f"Failed to read dynamic data. Last error: {jk_plugin.last_error_message}")
                
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Test interrupted by user.")
        finally:
            jk_plugin.disconnect()
            logger.info("Disconnected from JK BMS.")
    else:
        logger.error(f"Failed to connect to JK BMS. Check connection details. Last error: {jk_plugin.last_error_message}")