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


def load_inverter_config_from_file(config_file_path: str, instance_name: str) -> dict:
    """
    Load inverter configuration from config.ini file.
    
    Args:
        config_file_path: Path to the config.ini file
        instance_name: Name of the inverter instance (e.g., 'INV_Deye')
    
    Returns:
        Dictionary containing inverter configuration
    """
    config = configparser.ConfigParser(interpolation=None)
    
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")
    
    config.read(config_file_path, encoding='utf-8')
    section_name = f"PLUGIN_{instance_name}"
    
    if not config.has_section(section_name):
        raise ValueError(f"Config section [{section_name}] not found in {config_file_path}")
    
    # Extract inverter configuration from the config file
    inverter_config = {
        "instance_name": f"Test{instance_name}",
        "connection_type": config.get(section_name, "connection_type", fallback="tcp"),
        "slave_address": config.getint(section_name, "slave_address", fallback=1),
        "deye_model_series": config.get(section_name, "deye_model_series", fallback="modern_hybrid"),
    }
    
    # Add connection-specific settings
    if inverter_config["connection_type"] == "tcp":
        inverter_config.update({
            "tcp_host": config.get(section_name, "tcp_host", fallback="localhost"),
            "tcp_port": config.getint(section_name, "tcp_port", fallback=8899),
        })
    else:  # serial connection
        inverter_config.update({
            "serial_port": config.get(section_name, "serial_port", fallback="COM1"),
            "baud_rate": config.getint(section_name, "baud_rate", fallback=9600),
            "parity": config.get(section_name, "parity", fallback="N"),
            "stopbits": config.getint(section_name, "stopbits", fallback=1),
            "bytesize": config.getint(section_name, "bytesize", fallback=8),
        })
    
    # Add optional parameters if they exist
    optional_params = [
        ("modbus_timeout_seconds", "getfloat"),
        ("inter_read_delay_ms", "getint"),
        ("max_regs_per_read", "getint"),
        ("max_read_retries_per_group", "getint"),
        ("static_rated_power_ac_watts", "getfloat")
    ]
    
    for param_name, getter_method in optional_params:
        if config.has_option(section_name, param_name):
            getter = getattr(config, getter_method)
            inverter_config[param_name] = getter(section_name, param_name)
    
    return inverter_config


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