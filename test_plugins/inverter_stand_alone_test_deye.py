# inverter_stand_alone_test_deye.py
"""
A standalone test script for the plugins\inverter\deye_sunsynk_plugin.
This script loads configuration from config.ini and tests the inverter connection
without running the full monitoring application.

Instructions:
1. Place this script in the 'test_plugins' directory.
2. Configure your inverter settings in config.ini under [PLUGIN_INV_Deye]
3. Run the script from your terminal: python inverter_stand_alone_test_deye.py

Optional: You can override the config instance name by setting the environment variable:
   set INVERTER_INSTANCE_NAME=INV_Deye
   python inverter_stand_alone_test_deye.py
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
from plugins.inverter.deye_sunsynk_plugin import DeyeSunsynkPlugin
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
    logger = logging.getLogger("DeyeStandaloneTest")

    # --- Load Configuration from config.ini ---
    config_file_path = os.path.join(project_root_dir, "config.ini")
    
    # Allow override of instance name via environment variable
    inverter_instance_name = os.environ.get("INVERTER_INSTANCE_NAME", "INV_Deye")
    
    try:
        deye_config = load_inverter_config_from_file(config_file_path, inverter_instance_name)
        logger.info(f"Loaded configuration for instance '{inverter_instance_name}' from {config_file_path}")
        logger.info(f"Full config loaded: {deye_config}")
        logger.info(f"Connection type: {deye_config['connection_type']}")
        logger.info(f"Model series: {deye_config['deye_model_series']}")
        if deye_config['connection_type'] == 'tcp':
            logger.info(f"TCP Host: {deye_config['tcp_host']}:{deye_config['tcp_port']}")
        else:
            logger.info(f"Serial Port: {deye_config['serial_port']} @ {deye_config['baud_rate']} baud")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please ensure config.ini exists and contains a [PLUGIN_INV_Deye] section with proper inverter settings.")
        sys.exit(1)

    logger.info(f"Attempting to instantiate DeyeSunsynkPlugin with config: {deye_config}")
    try:
        deye_plugin = DeyeSunsynkPlugin(
            instance_name=deye_config.get("instance_name", "TestDeye"),
            plugin_specific_config=deye_config,
            main_logger=logger
        )
    except Exception as e:
        logger.error(f"Error during DeyeSunsynkPlugin instantiation: {e}", exc_info=True)
        sys.exit(1)

    logger.info("DeyeSunsynkPlugin instantiated. Attempting to connect...")
    if deye_plugin.connect():
        logger.info("Successfully connected to Deye/Sunsynk Inverter.")
        
        # 1. Read Static Data (once after connection)
        logger.info("\n>>> Reading Static Data...")
        static_info = deye_plugin.read_static_data()
        if static_info:
            pretty_print_data(static_info, "Static Inverter Information")
        else:
            logger.error(f"Failed to read static data. Last error: {deye_plugin.last_error_message}")

        # 2. Read Dynamic Data (in a loop)
        try:
            for i in range(10): # Read data a few times
                logger.info(f"\n>>> Reading Dynamic Data (Cycle {i+1}) <<<")
                dynamic_data = deye_plugin.read_dynamic_data()
                if dynamic_data:
                    pretty_print_data(dynamic_data, f"Dynamic Data (Cycle {i+1})")
                else:
                    logger.error(f"Failed to read dynamic data. Last error: {deye_plugin.last_error_message}")
                
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Test interrupted by user.")
        finally:
            deye_plugin.disconnect()
            logger.info("Disconnected from Deye/Sunsynk Inverter.")
    else:
        logger.error(f"Failed to connect to Deye/Sunsynk Inverter. Check connection details. Last error: {deye_plugin.last_error_message}")