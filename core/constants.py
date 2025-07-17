"""
Centralized constants for the Solar Monitoring application.

This module defines constants used throughout the application to avoid magic
strings and provide a single source of truth for configuration values.
"""

# Application Details
APP_NAME = "Solar Monitoring"
LOCK_FILE_NAME = "solar_monitoring.lock"
LOG_FILE_NAME = "solar_monitoring.log"
CONFIG_FILE_NAME = "config.ini"

# Logger Names
CORE_LOGGER_NAME = "InverterReaderCore"

# Thread Names
DATA_PROCESSOR_THREAD_NAME = "DataProcessor"
PLUGIN_POLL_THREAD_NAME_PREFIX = "PluginPoll"
WATCHDOG_THREAD_NAME = "Watchdog"

# Default Timeouts and Intervals (seconds)
DEFAULT_POLL_INTERVAL = 15
DEFAULT_WATCHDOG_TIMEOUT = 90
DEFAULT_WATCHDOG_GRACE_PERIOD = 45
DEFAULT_WEB_UPDATE_INTERVAL = 2.0
DEFAULT_MQTT_STALE_TIMEOUT = 300

# Database Constants
DEFAULT_HISTORY_MAX_AGE_HOURS = 168  # 1 week
DEFAULT_POWER_HISTORY_INTERVAL = 60  # 1 minute
DEFAULT_HOURLY_POWER_THRESHOLD = 2.0  # Watts

# Connection Retry Constants
DEFAULT_MAX_RECONNECT_ATTEMPTS = 3
DEFAULT_RECONNECT_BACKOFF_MAX = 15  # seconds