# core/bms_aggregator.py
"""
Multi-BMS Capacity-Weighted Aggregator

Aggregates multiple BMS plugin packs into a combined system view for the Solar
Monitoring Framework (SOC weighted by pack Ah, summed power/current, pack list).

Features:
- Capacity-weighted combined SOC
- Summed Ah/power/current and mean pack voltage
- Publishes bms_packs_list, bms_pack_count, bms_aggregation_mode
- Optional primary BMS instance for detail views

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from plugins.plugin_interface import StandardDataKeys

logger = logging.getLogger(__name__)

# Extra keys published alongside standard battery keys
BMS_PACKS_LIST = "bms_packs_list"
BMS_PACK_COUNT = "bms_pack_count"
BMS_AGGREGATION_MODE = "bms_aggregation_mode"


def _unwrap(packet: Dict[str, Any], key: str) -> Any:
    entry = packet.get(key)
    if isinstance(entry, dict) and "value" in entry:
        return entry.get("value")
    return entry


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_bms_packs(app_state, per_plugin_cache: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build per-pack summaries from cached BMS plugin data."""
    packs: List[Dict[str, Any]] = []
    for instance_id, packet in per_plugin_cache.items():
        plugin = app_state.active_plugin_instances.get(instance_id)
        if not plugin:
            continue
        if plugin.plugin_config.get("_runtime_device_category") != "bms":
            continue
        soc = _as_float(_unwrap(packet, StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT))
        voltage = _as_float(_unwrap(packet, StandardDataKeys.BATTERY_VOLTAGE_VOLTS))
        current = _as_float(_unwrap(packet, StandardDataKeys.BATTERY_CURRENT_AMPS))
        power = _as_float(_unwrap(packet, StandardDataKeys.BATTERY_POWER_WATTS))
        remaining = _as_float(_unwrap(packet, StandardDataKeys.BMS_REMAINING_CAPACITY_AH))
        full = _as_float(_unwrap(packet, StandardDataKeys.BMS_FULL_CAPACITY_AH))
        soh = _as_float(_unwrap(packet, StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT))
        delta = _as_float(_unwrap(packet, StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS))
        status = _unwrap(packet, StandardDataKeys.BATTERY_STATUS_TEXT)
        alarms = _unwrap(packet, StandardDataKeys.BMS_ACTIVE_ALARMS_LIST) or []
        if not isinstance(alarms, list):
            alarms = [alarms] if alarms else []
        packs.append({
            "instance_id": instance_id,
            "model": _unwrap(packet, StandardDataKeys.STATIC_BATTERY_MODEL_NAME),
            "soc": soc,
            "voltage": voltage,
            "current": current,
            "power": power,
            "remaining_ah": remaining,
            "full_ah": full,
            "soh": soh,
            "status": status if isinstance(status, str) else None,
            "connection": getattr(plugin, "connection_status", None),
            "cell_delta": delta,
            "alarms": [str(a) for a in alarms],
            "firmware": _unwrap(packet, StandardDataKeys.STATIC_BATTERY_FIRMWARE_VERSION),
        })
    return packs


def aggregate_capacity_weighted(
    packs: List[Dict[str, Any]],
    *,
    fallback_capacity_ah: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Aggregate packs:
    - SOC: capacity-weighted (equal-weight fallback)
    - current/power/remaining_ah: sum
    - voltage: mean of packs with voltage
    - soh: capacity-weighted when available
    """
    if not packs:
        return {
            BMS_PACKS_LIST: [],
            BMS_PACK_COUNT: 0,
            BMS_AGGREGATION_MODE: "capacity_weighted",
        }

    weights: List[Tuple[Dict[str, Any], float]] = []
    for pack in packs:
        w = pack.get("full_ah")
        if w is None or w <= 0:
            w = pack.get("remaining_ah")
        if (w is None or w <= 0) and fallback_capacity_ah and fallback_capacity_ah > 0:
            w = fallback_capacity_ah / max(len(packs), 1)
        if w is None or w <= 0:
            w = 1.0  # equal weight
        weights.append((pack, float(w)))

    weight_sum = sum(w for _, w in weights) or 1.0
    soc_packs = [(p, w) for p, w in weights if p.get("soc") is not None]
    if soc_packs:
        soc = sum(p["soc"] * w for p, w in soc_packs) / (sum(w for _, w in soc_packs) or 1.0)
    else:
        soc = None

    soh_packs = [(p, w) for p, w in weights if p.get("soh") is not None]
    soh = (
        sum(p["soh"] * w for p, w in soh_packs) / (sum(w for _, w in soh_packs) or 1.0)
        if soh_packs else None
    )

    voltages = [p["voltage"] for p in packs if p.get("voltage") is not None]
    currents = [p["current"] for p in packs if p.get("current") is not None]
    powers = [p["power"] for p in packs if p.get("power") is not None]
    remaining = [p["remaining_ah"] for p in packs if p.get("remaining_ah") is not None]
    fulls = [p["full_ah"] for p in packs if p.get("full_ah") is not None]

    statuses = [p.get("status") for p in packs if p.get("status")]
    if any(s and "alarm" in str(s).lower() for s in statuses):
        combined_status = "Alarm"
    elif any(s and "charg" in str(s).lower() for s in statuses):
        combined_status = "Charging"
    elif any(s and "discharg" in str(s).lower() for s in statuses):
        combined_status = "Discharging"
    elif statuses:
        combined_status = statuses[0]
    else:
        combined_status = "Idle"

    result: Dict[str, Any] = {
        BMS_PACKS_LIST: packs,
        BMS_PACK_COUNT: len(packs),
        BMS_AGGREGATION_MODE: "capacity_weighted",
        StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: round(soc, 2) if soc is not None else None,
        StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT: round(soh, 2) if soh is not None else None,
        StandardDataKeys.BATTERY_VOLTAGE_VOLTS: round(sum(voltages) / len(voltages), 3) if voltages else None,
        StandardDataKeys.BATTERY_CURRENT_AMPS: round(sum(currents), 3) if currents else None,
        StandardDataKeys.BATTERY_POWER_WATTS: round(sum(powers), 1) if powers else None,
        StandardDataKeys.BMS_REMAINING_CAPACITY_AH: round(sum(remaining), 3) if remaining else None,
        StandardDataKeys.BMS_FULL_CAPACITY_AH: round(sum(fulls), 3) if fulls else None,
        StandardDataKeys.BATTERY_STATUS_TEXT: combined_status,
    }
    return result


def apply_bms_aggregation(app_state, per_plugin_cache: Dict[str, Dict[str, Any]], merged_flat: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mutate/return merged_flat with aggregated BMS values when 1+ BMS packs exist.
    Single pack still publishes packs_list for UI consistency.
    """
    mode = "capacity_weighted"
    if app_state.config and app_state.config.has_section("BMS_AGGREGATION"):
        mode = app_state.config.get("BMS_AGGREGATION", "bms_aggregation_mode", fallback="capacity_weighted")
    mode = str(mode).split(";")[0].strip().lower() or "capacity_weighted"

    packs = collect_bms_packs(app_state, per_plugin_cache)
    if not packs:
        return merged_flat

    fallback_ah = None
    if getattr(app_state, "battery_usable_capacity_kwh", None):
        # Rough Ah estimate at ~51.2V nominal for weighting fallback only
        try:
            fallback_ah = float(app_state.battery_usable_capacity_kwh) * 1000.0 / 51.2
        except (TypeError, ValueError):
            fallback_ah = None

    if mode != "capacity_weighted":
        logger.warning("Unsupported bms_aggregation_mode '%s'; using capacity_weighted.", mode)

    agg = aggregate_capacity_weighted(packs, fallback_capacity_ah=fallback_ah)
    for key, value in agg.items():
        if value is not None:
            merged_flat[key] = value
    return merged_flat
