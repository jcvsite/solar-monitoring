# utils/helpers.py
import os
import sys
import logging
from typing import Any

logger = logging.getLogger(__name__)

# --- Status Constants ---
INIT_VAL = "Init"
UNKNOWN = "Unknown"
STATUS_NA = "N/A"
STATUS_ERROR = "error"
STATUS_ONLINE = "online"
STATUS_OFFLINE = "offline"
STATUS_CONNECTED = "connected"
STATUS_DISCONNECTED = "disconnected"
STATUS_INITIALIZING = "initializing"

# --- Error String Constants ---
ERROR_READ = "read_error"
ERROR_PROC = "proc_error"
ERROR_DECODE = "decode_error"

# --- Tuya State Constants ---
TUYA_STATE_UNKNOWN = "Unknown"
TUYA_STATE_ON = "ON"
TUYA_STATE_OFF = "OFF"
TUYA_STATE_DISABLED = "disabled"

# --- Operational Status Sets ---
FULLY_OPERATIONAL_STATUSES = {"Generating", "Grid Sync", "Discharging", "Charging", "Normal", "No Grid"}
PARTIALLY_RELIABLE_STATUSES = {"Waiting", "Standby", "Idle"}

# --- Formatting Functions ---
def format_value(value: Any, precision: int = 2) -> str:
    """
    Formats a numeric value to a string with specified precision.
    
    Args:
        value: The value to format (int, float, or other type)
        precision: Number of decimal places for floating point values
        
    Returns:
        Formatted string representation of the value, or "N/A" if None
    """
    if isinstance(value, (int, float)):
        try:
            return f"{float(value):.{precision}f}"
        except (ValueError, TypeError):
            return str(value)
    if value is None:
        return STATUS_NA
    return str(value)

def format_value_web(value: Any, precision: int = 2) -> str:
    """
    Formats a value for web display with appropriate precision and type handling.
    
    Args:
        value: The value to format (int, float, bool, or other type)
        precision: Number of decimal places for floating point values
        
    Returns:
        Formatted string suitable for web display, with booleans as "ON"/"OFF"
    """
    if isinstance(value, float):
        return f"{value:.{precision}f}"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return STATUS_NA
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)

def format_time_ago(elapsed_seconds: Any) -> str:
    """
    Formats elapsed time into a human-readable "time ago" string.
    
    Args:
        elapsed_seconds: Number of seconds elapsed (int or float)
        
    Returns:
        Human-readable time string like "5s ago", "2 min ago", "1 day ago"
    """
    if not isinstance(elapsed_seconds, (int, float)) or elapsed_seconds < 0:
        return ""
    if elapsed_seconds < 5: return "just now"
    if elapsed_seconds < 60: return f"{int(elapsed_seconds)}s ago"
    if elapsed_seconds < 3600: return f"{int(elapsed_seconds / 60)} min ago"
    if elapsed_seconds < 86400: return f"{int(elapsed_seconds / 3600)} hr ago"
    d = int(elapsed_seconds / 86400)
    return f"{d} day{'s' if d > 1 else ''} ago"

def trigger_script_restart(reason: str):
    """
    Triggers a complete restart of the application script.
    
    This function is called in critical failure scenarios where a clean restart
    is the only viable recovery option. It logs the reason and attempts to
    restart the Python process with the same arguments.
    
    Args:
        reason: Descriptive reason for the restart (logged as critical)
    """
    logger.critical(f"Triggering script restart due to: {reason}")
    try:
        os.execv(sys.executable, ['python'] + sys.argv)
    except OSError as e:
        logger.error(f"Failed to restart script: {e}")
        sys.exit(1)
