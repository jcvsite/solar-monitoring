# services/display_api.py
"""
Compact JSON payloads for ESP32 / external glance clients.

Builds typed (non string-formatted) snapshots from shared_data for
``/api/display``, ``/api/display/bms``, and ``/api/display/history``.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.app_state import AppState
from plugins.plugin_interface import StandardDataKeys, derive_battery_charge_state
from utils.helpers import STATUS_NA

DISPLAY_APP_ID = "solar-monitoring"
DISPLAY_API_HEADER = "X-Solar-Monitoring"

_OFFLINE_PATTERNS = re.compile(
    r"\b(no\s*grid|grid\s*off|islanding|off[\s-]?grid|utility\s*loss|grid\s*lost)\b",
    re.IGNORECASE,
)
_BROWNOUT_PATTERNS = re.compile(
    r"\b(brownout|undervoltage|under[\s-]?voltage|grid\s*under|low\s*voltage)\b",
    re.IGNORECASE,
)


def _unwrap(packet: dict, key: str) -> Any:
    entry = packet.get(key)
    if isinstance(entry, dict) and "value" in entry:
        return entry.get("value")
    return entry


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _age_seconds(packet: dict) -> Optional[float]:
    ts_ms = _num(_unwrap(packet, StandardDataKeys.SERVER_TIMESTAMP_MS_UTC))
    if ts_ms is None:
        return None
    return max(0.0, (time.time() * 1000.0 - ts_ms) / 1000.0)


def _alerts_present(packet: dict) -> bool:
    alerts = _unwrap(packet, StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT)
    if not isinstance(alerts, dict):
        return False
    for value in alerts.values():
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _collect_alert_text(packet: dict) -> str:
    parts: List[str] = []
    status = _str(_unwrap(packet, StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT))
    if status:
        parts.append(status)
    alerts = _unwrap(packet, StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT)
    if isinstance(alerts, dict):
        for key in ("grid", "status", "eps", "inverter"):
            bucket = alerts.get(key)
            if isinstance(bucket, list):
                parts.extend(str(x) for x in bucket if x)
            elif isinstance(bucket, str) and bucket.strip():
                parts.append(bucket)
    faults = _unwrap(packet, StandardDataKeys.OPERATIONAL_ACTIVE_FAULT_MESSAGES_LIST)
    if isinstance(faults, list):
        parts.extend(str(x) for x in faults if x)
    return " | ".join(parts)


def derive_grid_state(packet: dict) -> Tuple[str, str]:
    """
    Returns (grid_state, grid_label) for display clients.

    States: ok | import | export | offline | brownout | unknown
    """
    blob = _collect_alert_text(packet)
    grid_w = _num(_unwrap(packet, StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS))
    grid_v = _num(_unwrap(packet, StandardDataKeys.GRID_L1_VOLTAGE_VOLTS))

    if blob and _OFFLINE_PATTERNS.search(blob):
        return "offline", "Offline"
    if blob and _BROWNOUT_PATTERNS.search(blob):
        return "brownout", "Brownout"
    if grid_v is not None and grid_v < 90:
        return "brownout", "Brownout"

    if grid_w is None and not blob:
        return "unknown", "—"

    if grid_w is None:
        return "ok", "OK"

    if abs(grid_w) < 25:
        return "ok", "OK"
    if grid_w > 0:
        return "export", "Export"
    return "import", "Import"


def check_display_token(app_state: AppState, request) -> Optional[str]:
    """Return an error message if token is required and missing/invalid."""
    token = ""
    if app_state.config and app_state.config.has_option("WEB_DASHBOARD", "DISPLAY_API_TOKEN"):
        token = (app_state.config.get("WEB_DASHBOARD", "DISPLAY_API_TOKEN", fallback="") or "").strip()
    if not token:
        return None
    auth = request.headers.get("Authorization", "")
    bearer = ""
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()
    q = request.args.get("token", "")
    if bearer == token or q == token:
        return None
    return "Unauthorized"


def _format_clock(now: datetime) -> str:
    hour = now.strftime("%I").lstrip("0") or "12"
    return f"{hour}:{now.strftime('%M %p')}"


def _tz_offset_seconds(tzinfo) -> Optional[int]:
    if tzinfo is None:
        return None
    try:
        offset = datetime.now(tzinfo).utcoffset()
        if offset is None:
            return None
        return int(offset.total_seconds())
    except (TypeError, ValueError, OSError):
        return None


_weather_cache: Dict[str, Any] = {"fetched_at": 0.0, "payload": None}


def _fetch_weather_cached(app_state: AppState) -> Optional[Dict[str, Any]]:
    if not getattr(app_state, "enable_weather_widget", False):
        return None
    interval = max(60, int(getattr(app_state, "weather_update_interval_minutes", 15) or 15) * 60)
    now = time.time()
    cached = _weather_cache.get("payload")
    if cached is not None and now - float(_weather_cache.get("fetched_at") or 0) < interval:
        return cached

    lat = getattr(app_state, "weather_default_latitude", None)
    lon = getattr(app_state, "weather_default_longitude", None)
    if lat is None or lon is None:
        return cached

    unit = getattr(app_state, "weather_temperature_unit", "celsius") or "celsius"
    if unit not in ("celsius", "fahrenheit"):
        unit = "celsius"
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code,is_day",
            "temperature_unit": unit,
            "timezone": "auto",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        cur = data.get("current") or {}
        code = cur.get("weather_code")
        if code is None:
            return cached
        snap = {
            "enabled": True,
            "code": int(code),
            "is_day": int(cur.get("is_day", 1)),
            "temp": _num(cur.get("temperature_2m")),
            "unit": "F" if unit == "fahrenheit" else "C",
        }
        _weather_cache["fetched_at"] = now
        _weather_cache["payload"] = snap
        return snap
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return cached


def build_display_payload(app_state: AppState, packet: Optional[dict] = None) -> Dict[str, Any]:
    if packet is None:
        with app_state.data_lock:
            packet = dict(app_state.shared_data)

    age_s = _age_seconds(packet)
    ready = age_s is not None or any(
        _unwrap(packet, k) is not None
        for k in (
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS,
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT,
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT,
        )
    )

    grid_state, grid_label = derive_grid_state(packet)
    now = datetime.now(app_state.local_tzinfo) if app_state.local_tzinfo else datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S") if app_state.local_tzinfo else ""
    tz_name = None
    if app_state.local_tzinfo is not None:
        tz_name = getattr(app_state.local_tzinfo, "key", str(app_state.local_tzinfo))

    batt_time = _str(_unwrap(packet, StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT))
    if batt_time == STATUS_NA:
        batt_time = None

    batt_power = _num(_unwrap(packet, StandardDataKeys.BATTERY_POWER_WATTS))
    batt_status = _str(_unwrap(packet, StandardDataKeys.BATTERY_STATUS_TEXT))
    batt_plugin_charge_state = _str(_unwrap(packet, StandardDataKeys.BATTERY_CHARGE_STATE))
    # Prefer plugin-emitted charge state (e.g. Seplos telesign flags) over power-sign guess.
    if batt_plugin_charge_state and batt_plugin_charge_state in ("charging", "discharging", "idle", "floating", "unknown"):
        batt_charge_state = batt_plugin_charge_state
    else:
        batt_charge_state = derive_battery_charge_state(batt_power, batt_status)

    return {
        "ok": bool(ready),
        "app": DISPLAY_APP_ID,
        "title": getattr(app_state, "system_title", "Solar Monitoring"),
        "age_s": round(age_s, 1) if age_s is not None else None,
        "ts": ts,
        "clock": _format_clock(now) if app_state.local_tzinfo else "",
        "timezone": tz_name,
        "tz_offset_sec": _tz_offset_seconds(app_state.local_tzinfo),
        "weather": _fetch_weather_cached(app_state),
        "soc": _num(_unwrap(packet, StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT)),
        "batt_w": batt_power,
        "batt_status": batt_status,
        "battery_charge_state": batt_charge_state,
        "batt_time": batt_time,
        "pv_w": _num(_unwrap(packet, StandardDataKeys.PV_TOTAL_DC_POWER_WATTS)),
        "load_w": _num(_unwrap(packet, StandardDataKeys.LOAD_TOTAL_POWER_WATTS)),
        "grid_w": _num(_unwrap(packet, StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS)),
        "grid_state": grid_state,
        "grid_label": grid_label,
        "pv_today_kwh": _num(_unwrap(packet, StandardDataKeys.ENERGY_PV_DAILY_KWH)),
        "load_today_kwh": _num(_unwrap(packet, StandardDataKeys.ENERGY_LOAD_DAILY_KWH)),
        "status": _str(_unwrap(packet, StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT)),
        "alerts": _alerts_present(packet),
        "inv_temp_c": _num(_unwrap(packet, StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS))
        or _num(_unwrap(packet, StandardDataKeys.BMS_CELL_TEMPERATURE_AVERAGE_CELSIUS)),
        "batt_temp_c": _num(_unwrap(packet, StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS))
        or _num(_unwrap(packet, StandardDataKeys.BMS_CELL_TEMPERATURE_AVERAGE_CELSIUS)),
    }


def build_bms_payload(app_state: AppState, packet: Optional[dict] = None) -> Dict[str, Any]:
    if packet is None:
        with app_state.data_lock:
            packet = dict(app_state.shared_data)

    soc = _num(_unwrap(packet, StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT))
    volts = _num(_unwrap(packet, StandardDataKeys.BATTERY_VOLTAGE_VOLTS))
    cell_count = _unwrap(packet, StandardDataKeys.BMS_CELL_COUNT)
    try:
        cell_count_i = int(cell_count) if cell_count is not None else None
    except (TypeError, ValueError):
        cell_count_i = None

    cells = _unwrap(packet, StandardDataKeys.BMS_CELL_VOLTAGES_LIST)
    cell_voltages: List[float] = []
    if isinstance(cells, list):
        for v in cells[:48]:
            n = _num(v)
            if n is not None:
                cell_voltages.append(round(n, 3))

    packs = _unwrap(packet, "bms_packs_list")
    pack_count = _unwrap(packet, "bms_pack_count")
    try:
        pack_count_i = int(pack_count) if pack_count is not None else None
    except (TypeError, ValueError):
        pack_count_i = None

    has_bms = any(v is not None for v in (soc, volts, cell_count_i)) or bool(cell_voltages)

    batt_power = _num(_unwrap(packet, StandardDataKeys.BATTERY_POWER_WATTS))
    batt_status = _str(_unwrap(packet, StandardDataKeys.BATTERY_STATUS_TEXT))
    batt_plugin_charge_state = _str(_unwrap(packet, StandardDataKeys.BATTERY_CHARGE_STATE))
    # Prefer plugin-emitted charge state (e.g. Seplos telesign flags) over power-sign guess.
    if batt_plugin_charge_state and batt_plugin_charge_state in ("charging", "discharging", "idle", "floating", "unknown"):
        batt_charge_state = batt_plugin_charge_state
    else:
        batt_charge_state = derive_battery_charge_state(batt_power, batt_status)

    return {
        "ok": has_bms,
        "app": DISPLAY_APP_ID,
        "title": getattr(app_state, "system_title", "Solar Monitoring"),
        "soc": soc,
        "soh": _num(_unwrap(packet, StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT)),
        "volts": volts,
        "amps": _num(_unwrap(packet, StandardDataKeys.BATTERY_CURRENT_AMPS)),
        "watts": batt_power,
        "status": batt_status,
        "battery_charge_state": batt_charge_state,
        "temp_min": _num(_unwrap(packet, StandardDataKeys.BMS_TEMP_MIN_CELSIUS))
        or _num(_unwrap(packet, StandardDataKeys.BMS_CELL_TEMPERATURE_MIN_CELSIUS)),
        "temp_max": _num(_unwrap(packet, StandardDataKeys.BMS_TEMP_MAX_CELSIUS))
        or _num(_unwrap(packet, StandardDataKeys.BMS_CELL_TEMPERATURE_MAX_CELSIUS)),
        "temp_avg": _num(_unwrap(packet, StandardDataKeys.BMS_CELL_TEMPERATURE_AVERAGE_CELSIUS))
        or _num(_unwrap(packet, StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS)),
        "cycles": _num(_unwrap(packet, StandardDataKeys.BATTERY_CYCLES_COUNT)),
        "cell_count": cell_count_i,
        "cell_min_v": _num(_unwrap(packet, StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS)),
        "cell_max_v": _num(_unwrap(packet, StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS)),
        "cell_delta_v": _num(_unwrap(packet, StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS)),
        "cells": cell_voltages,
        "pack_count": pack_count_i,
        "packs": packs if isinstance(packs, list) else None,
    }


def _downsample(points: List[dict], max_points: int) -> List[dict]:
    if len(points) <= max_points:
        return points
    if max_points <= 1:
        return points[-1:]
    step = (len(points) - 1) / float(max_points - 1)
    out: List[dict] = []
    for i in range(max_points):
        idx = int(round(i * step))
        out.append(points[min(idx, len(points) - 1)])
    return out


def build_history_payload(app_state: AppState, db_service, hours: int = 24, max_points: int = 120) -> Dict[str, Any]:
    hours = max(1, min(int(hours or 24), 168))
    max_points = max(10, min(int(max_points or 120), 240))
    days = max(1, (hours + 23) // 24)

    history = db_service.fetch_history_data(days) if db_service else None
    raw = (history or {}).get("power") or []
    cutoff_ms = int((time.time() - hours * 3600) * 1000)

    points: List[dict] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        ts = row.get("timestamp")
        try:
            ts_i = int(ts)
        except (TypeError, ValueError):
            continue
        if ts_i < cutoff_ms:
            continue
        points.append(
            {
                "t": ts_i,
                "pv_w": _num(row.get(StandardDataKeys.PV_TOTAL_DC_POWER_WATTS) or row.get("production")),
                "load_w": _num(row.get(StandardDataKeys.LOAD_TOTAL_POWER_WATTS) or row.get("load")),
                "soc": _num(row.get(StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT) or row.get("soc")),
            }
        )

    with app_state.data_lock:
        packet = dict(app_state.shared_data)

    return {
        "ok": True,
        "app": DISPLAY_APP_ID,
        "title": getattr(app_state, "system_title", "Solar Monitoring"),
        "hours": hours,
        "points": _downsample(points, max_points),
        "today": {
            "pv_kwh": _num(_unwrap(packet, StandardDataKeys.ENERGY_PV_DAILY_KWH)),
            "load_kwh": _num(_unwrap(packet, StandardDataKeys.ENERGY_LOAD_DAILY_KWH)),
            "grid_import_kwh": _num(_unwrap(packet, StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH)),
            "grid_export_kwh": _num(_unwrap(packet, StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH)),
            "batt_charge_kwh": _num(_unwrap(packet, StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH)),
            "batt_discharge_kwh": _num(_unwrap(packet, StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH)),
        },
    }
