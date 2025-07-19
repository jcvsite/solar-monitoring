#!/usr/bin/env python3
"""
Centralized configuration loader for test plugins.

This module provides a unified way to load plugin configurations for standalone testing,
using the same robust parsing logic as the main application's config_loader.py.

GitHub: https://github.com/jcvsite/solar-monitoring
"""

import os
import sys
import configparser
import logging
from typing import Dict, Any, Type, Optional

# Add the project root to the Python path for imports
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir)
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)


def get_config_value(config: configparser.ConfigParser, var_name: str, section: str, 
                    return_type: Type = str, default: Any = None, preserve_semicolons: bool = False) -> Any:
    """
    Retrieves and converts a configuration value with intelligent comment handling.
    
    This function uses the same parsing logic as the main application's config_loader.py
    to ensure consistent behavior across all test plugins.
    
    Args:
        config: ConfigParser instance
        var_name: The configuration variable name
        section: Configuration file section name
        return_type: The expected type for conversion (str, int, float, bool)
        default: Default value if not found in config
        preserve_semicolons: If True, preserves semicolons in values (for keys that might contain them)
        
    Returns:
        The configuration value converted to the specified type
    """
    config_value = None
    
    # Get raw config value, handling semicolon comments intelligently
    if config.has_option(section, var_name):
        raw_value = config.get(section, var_name, fallback=None)
        if raw_value is not None:
            if preserve_semicolons:
                # For values that might legitimately contain semicolons (like crypto keys),
                # don't treat semicolon as a comment delimiter
                config_value = raw_value
            else:
                # For regular values, treat semicolon as comment delimiter but be smart about it
                # Only treat semicolon as comment if it's preceded by whitespace
                import re
                # Look for semicolon that's preceded by whitespace (likely a comment)
                comment_match = re.search(r'\s+;', raw_value)
                if comment_match:
                    config_value = raw_value[:comment_match.start()].rstrip()
                else:
                    config_value = raw_value
    
    if config_value is None:
        return default
    
    if isinstance(config_value, str):
        # Strip outer quotes and leading/trailing whitespace
        config_value = config_value.strip().strip("'\"")
    
    try:
        if return_type == bool:
            return config_value.lower() in ['true', '1', 'yes', 'on']
        return return_type(config_value)
    except (ValueError, TypeError):
        logging.warning(f"Could not cast '{config_value}' for '{var_name}' to {return_type.__name__}. Using default: {default}")
        return default


def load_plugin_config_from_file(config_file_path: str, instance_name: str) -> Dict[str, Any]:
    """
    Load plugin configuration from config.ini file using centralized parsing logic.
    
    This function provides a unified way to load plugin configurations for testing,
    using the same robust parsing as the main application.
    
    Args:
        config_file_path: Path to the config.ini file
        instance_name: Name of the plugin instance (e.g., 'INV_Solis', 'BMS_Seplos_v2')
    
    Returns:
        Dictionary containing plugin configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If plugin section is not found
    """
    # Configure parser to handle comments properly (same as main config loader)
    config = configparser.ConfigParser(
        interpolation=None,
        inline_comment_prefixes=(';',),  # Enable inline comment support
        comment_prefixes=('#', ';')      # Support both # and ; for comments
    )
    
    if not os.path.exists(config_file_path):
        raise FileNotFoundError(f"Config file not found: {config_file_path}")
    
    config.read(config_file_path, encoding='utf-8')
    section_name = f"PLUGIN_{instance_name}"
    
    if not config.has_section(section_name):
        raise ValueError(f"Config section [{section_name}] not found in {config_file_path}")
    
    # Base configuration that all plugins need
    plugin_config = {
        "instance_name": f"Test{instance_name}",
        "connection_type": get_config_value(config, "connection_type", section_name, str, "tcp"),
    }
    
    # Connection-specific settings
    if plugin_config["connection_type"] == "tcp":
        plugin_config.update({
            "tcp_host": get_config_value(config, "tcp_host", section_name, str, "localhost"),
            "tcp_port": get_config_value(config, "tcp_port", section_name, int, 502),
        })
    else:  # serial connection
        plugin_config.update({
            "serial_port": get_config_value(config, "serial_port", section_name, str, "COM1"),
            "baud_rate": get_config_value(config, "baud_rate", section_name, int, 9600),
            "parity": get_config_value(config, "parity", section_name, str, "N"),
            "stopbits": get_config_value(config, "stopbits", section_name, int, 1),
            "bytesize": get_config_value(config, "bytesize", section_name, int, 8),
        })
    
    # Common plugin settings
    plugin_config.update({
        "slave_address": get_config_value(config, "slave_address", section_name, int, 1),
        "modbus_timeout_seconds": get_config_value(config, "modbus_timeout_seconds", section_name, int, 10),
        "inter_read_delay_ms": get_config_value(config, "inter_read_delay_ms", section_name, int, 500),
        "max_regs_per_read": get_config_value(config, "max_regs_per_read", section_name, int, 60),
        "max_read_retries_per_group": get_config_value(config, "max_read_retries_per_group", section_name, int, 2),
        "startup_grace_period_seconds": get_config_value(config, "startup_grace_period_seconds", section_name, int, 120),
    })
    
    # Plugin-specific settings (only add if they exist in config to avoid clutter)
    
    # POWMR RS232 specific
    if config.has_option(section_name, "powmr_protocol_version"):
        plugin_config["powmr_protocol_version"] = get_config_value(config, "powmr_protocol_version", section_name, int, 1)
    
    # Deye/Sunsynk specific
    if config.has_option(section_name, "deye_model_series"):
        plugin_config["deye_model_series"] = get_config_value(config, "deye_model_series", section_name, str, "modern_hybrid")
    
    # Seplos BMS specific
    if config.has_option(section_name, "seplos_connection_type"):
        plugin_config["seplos_connection_type"] = get_config_value(config, "seplos_connection_type", section_name, str, "tcp")
        plugin_config["seplos_pack_address"] = get_config_value(config, "seplos_pack_address", section_name, int, 0)
        plugin_config["seplos_tcp_host"] = get_config_value(config, "seplos_tcp_host", section_name, str, "localhost")
        plugin_config["seplos_tcp_port"] = get_config_value(config, "seplos_tcp_port", section_name, int, 5022)
        plugin_config["seplos_serial_port"] = get_config_value(config, "seplos_serial_port", section_name, str, "COM1")
        plugin_config["seplos_baud_rate"] = get_config_value(config, "seplos_baud_rate", section_name, int, 19200)
        plugin_config["seplos_tcp_timeout"] = get_config_value(config, "seplos_tcp_timeout", section_name, float, 10.0)
        plugin_config["seplos_inter_command_delay_ms"] = get_config_value(config, "seplos_inter_command_delay_ms", section_name, int, 500)
        plugin_config["seplos_serial_operation_timeout"] = get_config_value(config, "seplos_serial_operation_timeout", section_name, float, 5.0)
    
    # Static power ratings (common for inverters)
    if config.has_option(section_name, "static_max_ac_power_watts"):
        plugin_config["static_max_ac_power_watts"] = get_config_value(config, "static_max_ac_power_watts", section_name, float, 5000.0)
    if config.has_option(section_name, "static_max_dc_power_watts"):
        plugin_config["static_max_dc_power_watts"] = get_config_value(config, "static_max_dc_power_watts", section_name, float, 6000.0)
    
    # Tuya settings (for plugins that might use them)
    if config.has_option(section_name, "tuya_device_id"):
        plugin_config["tuya_device_id"] = get_config_value(config, "tuya_device_id", section_name, str, None)
        plugin_config["tuya_local_key"] = get_config_value(config, "tuya_local_key", section_name, str, None, preserve_semicolons=True)
        plugin_config["tuya_ip_address"] = get_config_value(config, "tuya_ip_address", section_name, str, "Auto")
        plugin_config["tuya_version"] = get_config_value(config, "tuya_version", section_name, float, 3.4)
    
    return plugin_config


def load_inverter_config_from_file(config_file_path: str, instance_name: str) -> Dict[str, Any]:
    """
    Load inverter plugin configuration from config.ini file.
    
    Convenience function specifically for inverter plugins.
    
    Args:
        config_file_path: Path to the config.ini file
        instance_name: Name of the inverter instance (e.g., 'INV_Solis', 'INV_POWMR')
    
    Returns:
        Dictionary containing inverter configuration
    """
    return load_plugin_config_from_file(config_file_path, instance_name)


def load_bms_config_from_file(config_file_path: str, instance_name: str) -> Dict[str, Any]:
    """
    Load BMS plugin configuration from config.ini file.
    
    Convenience function specifically for BMS plugins.
    
    Args:
        config_file_path: Path to the config.ini file
        instance_name: Name of the BMS instance (e.g., 'BMS_Seplos_v2', 'BMS_JK')
    
    Returns:
        Dictionary containing BMS configuration
    """
    return load_plugin_config_from_file(config_file_path, instance_name)