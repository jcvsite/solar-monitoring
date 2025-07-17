# core/config_loader.py
import configparser
import logging
import os
import sys
from zoneinfo import ZoneInfo
from typing import Any, Type, Optional

from core.app_state import AppState

logger = logging.getLogger(__name__)

def load_configuration(config_path: str, app_state: AppState):
    """
    Loads configuration from a .ini file and environment variables, populating the AppState object.

    This function reads settings from the specified configuration file and then allows
    environment variables to override them. The precedence is:
    1. Environment variable (e.g., `POLL_INTERVAL`)
    2. Value from config file (e.g., `POLL_INTERVAL` in `[GENERAL]`)
    3. Default value specified in the code.

    It populates various attributes of the `app_state` object, covering general settings,
    inverter system parameters, MQTT, Web Dashboard, TLS, Watchdog, Tuya, and Weather widget
    configurations. It also performs basic validation for some settings, such as ensuring
    TLS certificate files exist if TLS is enabled.

    Args:
        config_path (str): The path to the configuration file (e.g., 'config/config.ini').
        app_state (AppState): The central application state object to be populated with
                              the loaded configuration values.
    """
    config = configparser.ConfigParser(interpolation=None)
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        logger.info(f"Successfully read configuration from {config_path}")
    else:
        logger.warning(f"Config file not found at {config_path}. Using defaults and environment variables.")
    
    app_state.config = config

    def get_config_value(var_name: str, return_type: Type = str, default: Any = None, section: str = 'DEFAULT') -> Any:
        """
        Retrieves and converts a configuration value with environment variable override support.
        
        This helper function implements a configuration precedence system:
        1. Environment variable (highest priority)
        2. Configuration file value
        3. Default value (lowest priority)
        
        Args:
            var_name: The configuration variable name
            return_type: The expected type for conversion (str, int, float, bool)
            default: Default value if not found in env or config
            section: Configuration file section name
            
        Returns:
            The configuration value converted to the specified type
        """
        env_value = os.environ.get(var_name.upper())
        config_value = config.get(section, var_name, fallback=None) if config.has_option(section, var_name) else None
        
        value_to_cast = env_value if env_value is not None else config_value
        if value_to_cast is None:
            return default
        
        if isinstance(value_to_cast, str):
            value_to_cast = value_to_cast.strip().strip("'\"")
        
        try:
            if return_type == bool:
                return value_to_cast.lower() in ['true', '1', 'yes', 'on']
            return return_type(value_to_cast)
        except (ValueError, TypeError):
            logger.warning(f"Could not cast '{value_to_cast}' for '{var_name}' to {return_type.__name__}. Using default: {default}")
            return default

    # General
    app_state.poll_interval = get_config_value("POLL_INTERVAL", int, 15, section='GENERAL')
    local_timezone_str = get_config_value("LOCAL_TIMEZONE", str, "UTC", section='GENERAL')
    try:
        app_state.local_tzinfo = ZoneInfo(local_timezone_str)
    except Exception:
        logger.error(f"Invalid timezone '{local_timezone_str}'. Using UTC.")
        app_state.local_tzinfo = ZoneInfo("UTC")

    plugin_instances_str = get_config_value("PLUGIN_INSTANCES", str, "", section='GENERAL')
    if plugin_instances_str:
        app_state.configured_plugin_instance_names = [name.strip() for name in plugin_instances_str.split(',') if name.strip()]
    
    # INVERTER_SYSTEM
    app_state.default_mppt_count = get_config_value("DEFAULT_MPPT_COUNT", int, 2, section='INVERTER_SYSTEM')
    app_state.pv_installed_capacity_w = get_config_value("PV_INSTALLED_CAPACITY_W", float, 0.0, section='INVERTER_SYSTEM')
    app_state.inverter_max_ac_power_w = get_config_value("INVERTER_MAX_AC_POWER_W", float, 0.0, section='INVERTER_SYSTEM')
    app_state.battery_usable_capacity_kwh = get_config_value("BATTERY_USABLE_CAPACITY_KWH", float, 0.0, section='INVERTER_SYSTEM')
    app_state.battery_max_charge_power_w = get_config_value("BATTERY_MAX_CHARGE_POWER_W", float, 0.0, section='INVERTER_SYSTEM')
    app_state.battery_max_discharge_power_w = get_config_value("BATTERY_MAX_DISCHARGE_POWER_W", float, 0.0, section='INVERTER_SYSTEM')    
    
    # MQTT
    app_state.enable_mqtt = get_config_value("ENABLE_MQTT", bool, False, section='MQTT')
    if app_state.enable_mqtt:
        app_state.mqtt_topic = get_config_value("MQTT_TOPIC", str, "solar", section='MQTT')
        app_state.availability_topic = f"{app_state.mqtt_topic}/availability"
        app_state.enable_ha_discovery = get_config_value("ENABLE_HA_DISCOVERY", bool, False, section='MQTT')
        app_state.ha_discovery_prefix = get_config_value("HA_DISCOVERY_PREFIX", str, "homeassistant", section='MQTT')
        app_state.enable_mqtt_tls = get_config_value("ENABLE_MQTT_TLS", bool, False, section='MQTT')
        app_state.mqtt_tls_insecure = get_config_value("MQTT_TLS_INSECURE", bool, False, section='MQTT')
        app_state.mqtt_stale_data_timeout_seconds = get_config_value("MQTT_STALE_DATA_TIMEOUT_SECONDS", int, 300, section='MQTT')

    # Web Dashboard
    app_state.enable_web_dashboard = get_config_value("ENABLE_WEB_DASHBOARD", bool, False, section='WEB_DASHBOARD')
    app_state.web_dashboard_port = get_config_value("WEB_DASHBOARD_PORT", int, 8081, section='WEB_DASHBOARD')
    app_state.web_update_interval = get_config_value("WEB_UPDATE_INTERVAL", float, 2.0, section='WEB_DASHBOARD')
    app_state.enable_https = get_config_value("ENABLE_HTTPS", bool, False, section='WEB_DASHBOARD')

    # TLS (shared settings)
    app_state.tls_config["ca_certs"] = get_config_value("TLS_CA_CERTS_PATH", str, None, section='TLS')
    app_state.tls_config["certfile"] = get_config_value("TLS_CERT_PATH", str, None, section='TLS')
    app_state.tls_config["keyfile"] = get_config_value("TLS_KEY_PATH", str, None, section='TLS')
    
    # Validate TLS settings
    if app_state.enable_mqtt_tls:
        ca_certs = app_state.tls_config.get("ca_certs")
        if not ca_certs or not os.path.exists(ca_certs):
            logger.error(f"ENABLE_MQTT_TLS is true, but TLS_CA_CERTS_PATH '{ca_certs}' is missing or invalid. Disabling MQTT TLS.")
            app_state.enable_mqtt_tls = False
    
    if app_state.enable_https:
        certfile = app_state.tls_config.get("certfile")
        keyfile = app_state.tls_config.get("keyfile")
        if not all([certfile, keyfile]) or not os.path.exists(certfile) or not os.path.exists(keyfile):
            logger.error(f"ENABLE_HTTPS is true, but TLS_CERT_PATH or TLS_KEY_PATH are missing or invalid. Disabling HTTPS.")
            app_state.enable_https = False
    
    # Watchdog
    default_watchdog_timeout = (app_state.poll_interval * 4) + 30
    app_state.watchdog_timeout = get_config_value("WATCHDOG_TIMEOUT", int, default_watchdog_timeout, section='WATCHDOG')
    
    default_grace_period = (app_state.poll_interval * 2) + 15
    app_state.watchdog_grace_period = get_config_value("WATCHDOG_GRACE_PERIOD", int, default_grace_period, section='WATCHDOG')

    app_state.max_plugin_reload_attempts = get_config_value("MAX_RECONNECT_ATTEMPTS", int, 3, section='GENERAL')
    
    # Tuya
    app_state.enable_tuya = get_config_value("ENABLE_TUYA", bool, False, section='TUYA')
    if app_state.enable_tuya:
        app_state.tuya_device_id = get_config_value("TUYA_DEVICE_ID", str, None, section='TUYA')
        app_state.tuya_local_key = get_config_value("TUYA_LOCAL_KEY", str, None, section='TUYA')
        app_state.tuya_ip_address = get_config_value("TUYA_IP_ADDRESS", str, "Auto", section='TUYA')
        app_state.tuya_version = get_config_value("TUYA_VERSION", float, 3.4, section='TUYA')
        app_state.temp_threshold_on = get_config_value("TEMP_THRESHOLD_ON", float, 43.0, section='TUYA')
        app_state.temp_threshold_off = get_config_value("TEMP_THRESHOLD_OFF", float, 42.0, section='TUYA')
        
        if not all([app_state.tuya_device_id, app_state.tuya_local_key]):
            logger.warning("ENABLE_TUYA is True, but TUYA_DEVICE_ID or TUYA_LOCAL_KEY is missing. Disabling Tuya.")
            app_state.enable_tuya = False

    # Weather Widget
    app_state.enable_weather_widget = get_config_value("ENABLE_WEATHER_WIDGET", bool, False, section='WEATHER')
    if app_state.enable_weather_widget:
        app_state.weather_use_automatic_location = get_config_value("WEATHER_USE_AUTOMATIC_LOCATION", bool, True, section='WEATHER')
        app_state.weather_default_latitude = get_config_value("WEATHER_DEFAULT_LATITUDE", float, 51.5072, section='WEATHER')
        app_state.weather_default_longitude = get_config_value("WEATHER_DEFAULT_LONGITUDE", float, -0.1276, section='WEATHER')
        app_state.weather_temperature_unit = get_config_value("WEATHER_TEMPERATURE_UNIT", str, "celsius", section='WEATHER').lower()
        app_state.weather_update_interval_minutes = get_config_value("WEATHER_UPDATE_INTERVAL_MINUTES", int, 15, section='WEATHER')
        app_state.weather_map_zoom_level = get_config_value("WEATHER_MAP_ZOOM_LEVEL", int, 5, section='WEATHER')
        
        if app_state.weather_temperature_unit not in ['celsius', 'fahrenheit']:
            logger.warning(f"Invalid WEATHER_TEMPERATURE_UNIT '{app_state.weather_temperature_unit}'. Defaulting to 'celsius'.")
            app_state.weather_temperature_unit = 'celsius'
    
    # Filter
    app_state.filtering_mode = get_config_value("FILTERING_MODE", str, "adaptive", section='FILTER').lower()
    
    # Configurable Daily Energy Limits for filtering
    app_state.daily_limit_grid_import_kwh = get_config_value("DAILY_LIMIT_GRID_IMPORT_KWH", float, 100.0, section='FILTER')
    app_state.daily_limit_grid_export_kwh = get_config_value("DAILY_LIMIT_GRID_EXPORT_KWH", float, 50.0, section='FILTER')
    app_state.daily_limit_battery_charge_kwh = get_config_value("DAILY_LIMIT_BATTERY_CHARGE_KWH", float, 50.0, section='FILTER')
    app_state.daily_limit_battery_discharge_kwh = get_config_value("DAILY_LIMIT_BATTERY_DISCHARGE_KWH", float, 50.0, section='FILTER')
    app_state.daily_limit_pv_generation_kwh = get_config_value("DAILY_LIMIT_PV_GENERATION_KWH", float, 80.0, section='FILTER')
    app_state.daily_limit_load_consumption_kwh = get_config_value("DAILY_LIMIT_LOAD_CONSUMPTION_KWH", float, 120.0, section='FILTER')
    
    app_state.hourly_summary_power_threshold_w = get_config_value("HOURLY_SUMMARY_POWER_THRESHOLD_W", float, 2.0, section='DATABASE')
    logger.info("Configuration loading complete.")

def validate_core_config(app_state: AppState):
    """
    Validates critical configuration settings after they have been loaded.

    This function performs essential checks to ensure the application can start
    correctly. It verifies that:
    - At least one plugin instance is defined in `PLUGIN_INSTANCES`.
    - Each defined plugin instance has a corresponding `plugin_type` in its
      configuration section (e.g., `[PLUGIN_main_inverter]`).
    - The `POLL_INTERVAL` is a positive number.

    If any of these checks fail, it logs a critical error message detailing the
    problems and terminates the application with `sys.exit(1)`.

    Args:
        app_state (AppState): The application state object containing the configuration
                              to be validated.
    """
    errors = []
    if not app_state.configured_plugin_instance_names:
        errors.append("PLUGIN_INSTANCES must be configured in [GENERAL] (e.g., PLUGIN_INSTANCES = main_inverter, main_bms).")
    else:
        for instance_name in app_state.configured_plugin_instance_names:
            plugin_type = app_state.config.get(f"PLUGIN_{instance_name}", "plugin_type", fallback=None)
            if not plugin_type:
                errors.append(f"Missing 'plugin_type' for instance '{instance_name}' in config section [PLUGIN_{instance_name}].")

    if app_state.poll_interval <= 0:
        errors.append("POLL_INTERVAL must be > 0.")
    
    if errors:
        logger.critical("Core Configuration Errors: " + "; ".join(errors) + ". Exiting.")
        sys.exit(1)
    
    logger.info("Core configuration validated successfully.")
