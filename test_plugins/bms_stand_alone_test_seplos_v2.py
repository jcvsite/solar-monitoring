# bms_stand_alone_test_seplos_v2.py
"""
A standalone test script for the plugins\battery\seplos_bms_v2_plugin.
This script loads configuration from config.ini and tests the BMS connection
without running the full monitoring application.

Instructions:
1. Place this script in the 'test_plugins' directory.
2. Configure your BMS settings in config.ini under [PLUGIN_BMS_Seplos_v2]
3. Run the script from your terminal: python bms_stand_alone_test_seplos_v2.py

Optional: You can override the config instance name by setting the environment variable:
   set BMS_INSTANCE_NAME=BMS_Seplos_v2
   python bms_stand_alone_test_seplos_v2.py
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
from plugins.battery.seplos_bms_v2_plugin import SeplosBMSV2


def load_bms_config_from_file(config_file_path: str, instance_name: str) -> dict:
    """
    Load BMS configuration from config.ini file.
    
    Args:
        config_file_path: Path to the config.ini file
        instance_name: Name of the BMS instance (e.g., 'BMS_Seplos_v2')
    
    Returns:
        Dictionary containing BMS configuration
    """
    config = configparser.ConfigParser(interpolation=None)
    
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")
    
    config.read(config_file_path, encoding='utf-8')
    section_name = f"PLUGIN_{instance_name}"
    
    if not config.has_section(section_name):
        raise ValueError(f"Config section [{section_name}] not found in {config_file_path}")
    
    # Extract BMS configuration from the config file
    bms_config = {
        "instance_name": f"Test{instance_name}",
        "seplos_connection_type": config.get(section_name, "seplos_connection_type", fallback="tcp"),
        "seplos_pack_address": config.getint(section_name, "seplos_pack_address", fallback=0),
    }
    
    # Add connection-specific settings
    if bms_config["seplos_connection_type"] == "tcp":
        bms_config.update({
            "seplos_tcp_host": config.get(section_name, "seplos_tcp_host", fallback="localhost"),
            "seplos_tcp_port": config.getint(section_name, "seplos_tcp_port", fallback=5022),
        })
    else:  # serial connection
        bms_config.update({
            "seplos_serial_port": config.get(section_name, "seplos_serial_port", fallback="COM1"),
            "seplos_baud_rate": config.getint(section_name, "seplos_baud_rate", fallback=19200),
        })
    
    # Add optional parameters if they exist
    optional_params = [
        ("seplos_tcp_timeout", "getfloat"),
        ("seplos_inter_command_delay_ms", "getint"),
        ("seplos_serial_operation_timeout", "getfloat")
    ]
    
    for param_name, getter_method in optional_params:
        if config.has_option(section_name, param_name):
            getter = getattr(config, getter_method)
            bms_config[param_name] = getter(section_name, param_name)
    
    return bms_config


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
    logger = logging.getLogger("SeplosV2StandaloneTest")

    # --- Load Configuration from config.ini ---
    config_file_path = os.path.join(project_root_dir, "config.ini")
    
    # Allow override of instance name via environment variable
    bms_instance_name = os.environ.get("BMS_INSTANCE_NAME", "BMS_Seplos_v2")
    
    try:
        seplos_config = load_bms_config_from_file(config_file_path, bms_instance_name)
        logger.info(f"Loaded configuration for instance '{bms_instance_name}' from {config_file_path}")
        logger.info(f"Full config loaded: {seplos_config}")
        logger.info(f"Connection type: {seplos_config['seplos_connection_type']}")
        if seplos_config['seplos_connection_type'] == 'tcp':
            logger.info(f"TCP Host: {seplos_config['seplos_tcp_host']}:{seplos_config['seplos_tcp_port']}")
        else:
            logger.info(f"Serial Port: {seplos_config['seplos_serial_port']} @ {seplos_config['seplos_baud_rate']} baud")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please ensure config.ini exists and contains a [PLUGIN_BMS_Seplos_v2] section with proper BMS settings.")
        sys.exit(1)

    logger.info(f"Attempting to instantiate SeplosBMSV2 with config: {seplos_config}")
    try:
        seplos_plugin = SeplosBMSV2(
            instance_name="TestBMS",
            plugin_specific_config=seplos_config,
            main_logger=logger
        )
    except Exception as e:
        logger.error(f"Error during SeplosBMSV2 instantiation: {e}", exc_info=True)
        sys.exit(1)

    logger.info("SeplosBMSV2 instantiated. Attempting to connect...")
    if seplos_plugin.connect():
        logger.info("Successfully connected to BMS.")
        
        try:
            for i in range(5): # Read data a few times
                logger.info(f"\n--- Read Cycle {i+1} ---")
                data = seplos_plugin.read_bms_data()
                if data:
                    logger.info("Successfully read data:")
                    for key, value in data.items():
                        # The data is already flattened by standardize_bms_keys
                        # No need to extract 'value' and 'unit' from nested dict
                        
                        # Truncate long lists for cleaner logging
                        if isinstance(value, list) and len(value) > 10:
                            log_val = f"{str(value[:5])[:-1]} ... {str(value[-5:])[1:]} (Total: {len(value)})"
                        else:
                            log_val = str(value)
                            
                        logger.info(f"  {key:<40}: {log_val}")
                else:
                    logger.error(f"Failed to read data. Last error: {seplos_plugin.last_error_message}")
                
                time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Test interrupted by user.")
        finally:
            seplos_plugin.disconnect()
            logger.info("Disconnected from BMS.")
    else:
        logger.error(f"Failed to connect to BMS. Last error: {seplos_plugin.last_error_message}")