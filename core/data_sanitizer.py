# core/data_sanitizer.py
"""
Plugin Data Sanitizer

Sanitizes plugin payloads before merge/UI so unknown or malformed values cannot
crash consumers in the Solar Monitoring Framework.

Features:
- Strips/normalizes decode/read/proc error sentinels
- Type-safe numeric/list coercion for StandardDataKeys
- Helpers to classify successful vs failed dynamic reads
- Protects web, MQTT, DB, and aggregator paths from bad payloads

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from plugins.plugin_interface import StandardDataKeys
from utils.helpers import ERROR_DECODE, ERROR_PROC, ERROR_READ

logger = logging.getLogger(__name__)

_ERROR_STRINGS = {ERROR_DECODE, ERROR_PROC, ERROR_READ, "decode_error", "read_error", "proc_error"}

_STATUS_TEXT_KEYS = {
    StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT,
    StandardDataKeys.BATTERY_STATUS_TEXT,
    StandardDataKeys.BMS_FAULT_SUMMARY_TEXT,
    StandardDataKeys.BMS_BALANCING_STATUS_TEXT,
    StandardDataKeys.BMS_CELLS_BALANCING_TEXT,
    StandardDataKeys.BMS_MOSFET_CHARGE_STATUS_TEXT,
    StandardDataKeys.BMS_MOSFET_DISCHARGE_STATUS_TEXT,
    StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT,
}

_LIST_STR_KEYS = {
    StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_CODES_LIST,
    StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_MESSAGES_LIST,
    StandardDataKeys.BMS_ACTIVE_ALARMS_LIST,
    StandardDataKeys.BMS_ACTIVE_WARNINGS_LIST,
}

_LIST_FLOAT_KEYS = {
    StandardDataKeys.BMS_CELL_VOLTAGES_LIST,
    StandardDataKeys.BMS_CELL_TEMPERATURES_LIST,
}

_MEANINGFUL_NUMERIC_KEYS = (
    StandardDataKeys.PV_TOTAL_DC_POWER_WATTS,
    StandardDataKeys.AC_POWER_WATTS,
    StandardDataKeys.BATTERY_POWER_WATTS,
    StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS,
    StandardDataKeys.LOAD_TOTAL_POWER_WATTS,
    StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT,
    StandardDataKeys.BATTERY_VOLTAGE_VOLTS,
    StandardDataKeys.BMS_CELL_COUNT,
)


def is_error_sentinel(value: Any) -> bool:
    if isinstance(value, str) and value.strip().lower() in _ERROR_STRINGS:
        return True
    return False


def to_finite_float(value: Any) -> Optional[float]:
    if value is None or is_error_sentinel(value):
        return None
    if isinstance(value, bool):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    return num


def to_optional_int(value: Any) -> Optional[int]:
    num = to_finite_float(value)
    if num is None:
        return None
    return int(round(num))


def _sanitize_status_text(value: Any) -> Optional[str]:
    if value is None or is_error_sentinel(value):
        return None
    if isinstance(value, dict):
        # Broken nested status maps (e.g. Deye STATUS_CODES) must never reach the UI.
        return f"Unknown ({next(iter(value.keys()), '?')})"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else None
    text = str(value).strip()
    return text if text else None


def _sanitize_str_list(value: Any) -> List[str]:
    if value is None or is_error_sentinel(value):
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, (list, tuple)):
        return [str(value)]
    out: List[str] = []
    for item in value:
        if item is None or is_error_sentinel(item):
            continue
        out.append(str(item))
    return out


def _sanitize_float_list(value: Any) -> List[float]:
    if value is None or is_error_sentinel(value) or not isinstance(value, (list, tuple)):
        return []
    out: List[float] = []
    for item in value:
        num = to_finite_float(item)
        if num is not None:
            out.append(num)
    return out


def _sanitize_alerts_dict(value: Any) -> Dict[str, List[str]]:
    if not isinstance(value, dict):
        return {"unknown": ["OK"]}
    cleaned: Dict[str, List[str]] = {}
    for category, messages in value.items():
        cat_key = str(category)
        cleaned[cat_key] = _sanitize_str_list(messages) or ["OK"]
    return cleaned or {"unknown": ["OK"]}


def sanitize_plugin_data(data: Optional[Dict[str, Any]], instance_id: str = "") -> Optional[Dict[str, Any]]:
    """
    Return a cleaned copy of a flat plugin data dict, or None if unusable.

    Empty dicts are treated as read failures (same as None).
    """
    if data is None:
        return None
    if not isinstance(data, dict):
        logger.warning("Sanitizer: non-dict payload from '%s' discarded.", instance_id)
        return None
    if not data:
        return None

    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None or is_error_sentinel(value):
            cleaned[key] = None
            continue

        if key in _STATUS_TEXT_KEYS:
            cleaned[key] = _sanitize_status_text(value)
        elif key == StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT:
            cleaned[key] = _sanitize_alerts_dict(value)
        elif key in _LIST_STR_KEYS:
            cleaned[key] = _sanitize_str_list(value)
        elif key in _LIST_FLOAT_KEYS:
            cleaned[key] = _sanitize_float_list(value)
        elif key == StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT:
            num = to_finite_float(value)
            if num is None:
                cleaned[key] = None
            else:
                # Allow brief overshoot from devices, but clamp for consumers.
                cleaned[key] = max(0.0, min(100.0, num if num <= 105.0 else 100.0))
        elif key in (
            StandardDataKeys.STATIC_NUMBER_OF_MPPTS,
            StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC,
            StandardDataKeys.BMS_CELL_COUNT,
            StandardDataKeys.BATTERY_CYCLES_COUNT,
            StandardDataKeys.BMS_CELL_WITH_MIN_VOLTAGE_NUMBER,
            StandardDataKeys.BMS_CELL_WITH_MAX_VOLTAGE_NUMBER,
        ):
            cleaned[key] = to_optional_int(value)
        elif isinstance(value, bool):
            cleaned[key] = value
        elif isinstance(value, (int, float)):
            cleaned[key] = to_finite_float(value)
        elif isinstance(value, dict):
            # Keep plugin-specific nested dicts but drop error sentinels inside.
            nested = {
                nk: (None if is_error_sentinel(nv) else nv)
                for nk, nv in value.items()
            }
            cleaned[key] = nested
        else:
            cleaned[key] = value

    return cleaned


def plugin_data_has_operational_signal(data: Optional[Dict[str, Any]]) -> bool:
    """True if the payload contains at least one usable operational numeric field."""
    if not data:
        return False
    for key in _MEANINGFUL_NUMERIC_KEYS:
        num = to_finite_float(data.get(key))
        if num is not None:
            return True
    # Static-only packets after connect are still useful once.
    if data.get(StandardDataKeys.STATIC_DEVICE_CATEGORY):
        return True
    status = data.get(StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT)
    if isinstance(status, str) and status.strip():
        return True
    batt_status = data.get(StandardDataKeys.BATTERY_STATUS_TEXT)
    if isinstance(batt_status, str) and batt_status.strip():
        return True
    return False


def is_successful_dynamic_read(data: Any) -> bool:
    """Normalize plugin failure returns: None and empty {} are failures."""
    if data is None:
        return False
    if isinstance(data, dict) and not data:
        return False
    if not isinstance(data, dict):
        return False
    return True
