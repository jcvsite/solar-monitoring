# utils/helpers.py
"""
Shared Helper Utilities

Common status constants and small helpers used across core services and plugins
in the Solar Monitoring Framework.

Features:
- Connection/status string constants (online, error, initializing, etc.)
- Tuya state constants for UI/MQTT
- Value formatting helpers for dashboards
- Script restart trigger used by watchdog paths
- Error sentinel strings (decode/read/proc)

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

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

def _restart_rate_limit_path() -> str:
    """Return a path for tracking recent full-process restart attempts."""
    base = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv else __file__))
    return os.path.join(base, ".solar_monitoring_restart_state")


def should_allow_full_restart(max_restarts: int = 5, window_seconds: int = 3600) -> bool:
    """
    Rate-limit full process restarts to avoid restart storms.

    Returns True if a restart is allowed. Updates the on-disk counter when allowed.
    """
    path = _restart_rate_limit_path()
    now = __import__("time").time()
    timestamps = []
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        timestamps.append(float(line))
                    except ValueError:
                        continue
    except OSError as e:
        logger.warning(f"Could not read restart rate-limit file: {e}")

    timestamps = [ts for ts in timestamps if (now - ts) <= window_seconds]
    if len(timestamps) >= max_restarts:
        logger.critical(
            f"Restart rate limit reached ({len(timestamps)}/{max_restarts} in {window_seconds}s). "
            "Skipping os.execv; external supervisor should recover if needed."
        )
        return False

    timestamps.append(now)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(str(ts) for ts in timestamps[-max_restarts:]) + "\n")
    except OSError as e:
        logger.warning(f"Could not write restart rate-limit file: {e}")
    return True


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
    if not should_allow_full_restart():
        sys.exit(1)
    try:
        # Use the real interpreter path; hardcoding 'python' breaks on many Linux installs.
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except OSError as e:
        logger.error(f"Failed to restart script: {e}")
        sys.exit(1)
