# core/data_processor.py
import logging
import queue
import time

from typing import Dict, Any

from core.app_state import AppState
from core.plugin_manager import get_primary_bms_instance_id
from plugins.plugin_interface import StandardDataKeys
from utils.helpers import (
    STATUS_CONNECTED, STATUS_DISCONNECTED, FULLY_OPERATIONAL_STATUSES,
    STATUS_ERROR, STATUS_NA
)

logger = logging.getLogger(__name__)

def _calculate_time_remaining(data: dict, app_state: AppState) -> str:
    """
    Calculates a human-readable estimate of battery time remaining.

    This function estimates the time until the battery is full (when charging) or
    reaches a 20% state of charge (when discharging). It uses the current battery
    power, state of charge (SOC), and the configured usable battery capacity to
    make the estimation.

    Args:
        data (dict): A dictionary containing the necessary data keys, such as
                     `battery_power_watts` and `battery_state_of_charge_percent`.
        app_state (AppState): The application state object, used to retrieve the
                              configured `battery_usable_capacity_kwh`.

    Returns:
        str: A formatted string representing the time estimate, which can be one of:
             - "~ Xh Ym (to 20%)" when discharging.
             - "~ Xh Ym (to 100%)" when charging.
             - "Idle" if the power draw/charge is negligible.
             - "Full" if the battery is at 100% SOC.
             - "<20%" if the battery is already below the discharge target.
             - "N/A" if the required data for calculation is missing or invalid.
    """
    soc_val = data.get(StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT, {}).get("value")
    power_val = data.get(StandardDataKeys.BATTERY_POWER_WATTS, {}).get("value")
    capacity_kwh = app_state.battery_usable_capacity_kwh

    if not all(isinstance(v, (int, float)) for v in [soc_val, power_val, capacity_kwh]) or capacity_kwh <= 0:
        return STATUS_NA
    
    if abs(power_val) < 25: 
        return "Idle"

    if power_val > 0: # Discharging
        target_soc = 20
        if soc_val <= target_soc: return f"<{target_soc}% ({soc_val}%)"
        energy_rem_wh = capacity_kwh * 1000 * ((soc_val - target_soc) / 100.0)
        hours = energy_rem_wh / power_val
        label = f"(to {target_soc}%)"
    else: # Charging
        if soc_val >= 100: return "Full"
        energy_to_full_wh = capacity_kwh * 1000 * ((100 - soc_val) / 100.0)
        hours = energy_to_full_wh / abs(power_val)
        label = "(to 100%)"
    
    if hours > 100: return f">100h {label}"
    h, m = divmod(int(hours * 60), 60)
    return f"~ {h}h {m}m {label}"

def deep_merge_dicts(base_dict: Dict[str, Any], merge_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merges two dictionaries, performing a deep merge specifically for dictionaries
    containing a 'value' key. It prioritizes values from the `merge_dict` while
    protecting specific keys (like connection status) from being overwritten.

    The merge handles special cases for device categories and categorized alerts,
    ensuring that alerts are combined intelligently and that inverter status isn't
    overwritten by non-inverter data.

    Parameters:
        base_dict (Dict[str, Any]): The dictionary to be merged into (destination).
        merge_dict (Dict[str, Any]): The dictionary from which values are taken (source).

    Returns:
        Dict[str, Any]: The `base_dict` after merging, containing a combination of
                       values from both dictionaries. The merge is performed in-place
                       on `base_dict`, but it is also returned for convenience.
    """

    for key, value_dict in merge_dict.items():
        if not isinstance(value_dict, dict) or 'value' not in value_dict:
            continue
        
        # This check is now the single point of protection against overwriting the live status
        if StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS in key:
            continue

        if key == StandardDataKeys.STATIC_DEVICE_CATEGORY:
            if base_dict.get(key, {}).get("value") != "inverter":
                base_dict[key] = value_dict
            continue

        if key == StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT and key in base_dict:
            base_val = base_dict.get(key, {}).get('value')
            merge_val = value_dict.get('value')
            if isinstance(base_val, dict) and isinstance(merge_val, dict):
                merged_alerts = base_val.copy()
                for alert_category, alert_list in merge_val.items():
                    existing_alerts = set(merged_alerts.get(alert_category, []))
                    existing_alerts.update(alert_list)
                    if len(existing_alerts) > 1:
                        existing_alerts.discard("OK")
                    merged_alerts[alert_category] = sorted(list(existing_alerts))
                base_dict[key]['value'] = merged_alerts
            else:
                base_dict[key] = value_dict
        else:
            base_dict[key] = value_dict
    return base_dict

def process_and_merge_data(app_state: AppState, db_service: 'DatabaseService', tuya_service: 'TuyaService', filter_service: 'DataFilterService', data_queue: queue.Queue):
    """
    Main data processing loop that runs in a dedicated thread.

    This function continuously consumes raw data packets from plugins via a queue.
    It trusts each plugin to handle its own internal state (e.g., non-operational
    statuses) and provide a best-effort data packet. The processor's role is to:

    1.  **Cache Update**: Store the latest data packet from each plugin instance.
    2.  **Data Merging**: Create a unified data snapshot by merging the cached data from all
        plugins. It uses a custom `deep_merge_dicts` function that intelligently handles
        data from different sources (e.g., giving BMS data precedence for shared keys).
    3.  **Data Filtering**: Apply a series of filters (e.g., for smoothing power values)
        to the merged data to ensure data quality and consistency.
    4.  **Data Enrichment**: Calculate derived values like battery time remaining and add
        application-level timestamps.
    5.  **Dispatch**: Put the final, processed data package onto a dispatch queue, making
        it available to consumer services like the Web UI, MQTT, and database logger.
    6.  **External Triggers**: Call other services based on the final data, such as
        triggering the Tuya fan control based on inverter temperature.
    """
    
    logger.info("Data Processing thread started. Waiting for data from plugins...")
    
    backfill_attempted = False
    last_good_merged_data: Dict[str, Any] = {}
    
    while app_state.running:
        try:
            report = data_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        instance_id = report['instance_id']
        plugin_data = report.get('data')

        with app_state.data_lock:
            if plugin_data:
                # Validate data quality before caching - don't cache null/empty/waiting states
                if _is_data_meaningful(plugin_data, instance_id, logger):
                    wrapped_data_packet = {key: {"value": value} for key, value in plugin_data.items()}
                    app_state.per_plugin_data_cache[instance_id] = wrapped_data_packet
                    logger.debug(f"DataProcessor: Cached meaningful data for '{instance_id}'")
                else:
                    logger.info(f"DataProcessor: Received non-meaningful data for '{instance_id}' (waiting/null state). Preserving last known good data.")
            else:
                # If a plugin fails to poll, we no longer clear its cache.
                # We keep the last known good data to allow for graceful timeouts in consumer services.
                logger.warning(f"DataProcessor: Received empty data packet for '{instance_id}', indicating a read error. Preserving last known data.")

        merged_data = {}
        with app_state.data_lock:
            per_plugin_cache_snapshot = app_state.per_plugin_data_cache.copy()

        for inst_id, data_packet in per_plugin_cache_snapshot.items():
            plugin = app_state.active_plugin_instances.get(inst_id)
            if plugin and plugin.plugin_config.get("_runtime_device_category") != "bms":
                merged_data = deep_merge_dicts(merged_data, data_packet)
        
        for inst_id, data_packet in per_plugin_cache_snapshot.items():
            plugin = app_state.active_plugin_instances.get(inst_id)
            if plugin and plugin.plugin_config.get("_runtime_device_category") == "bms":
                merged_data = deep_merge_dicts(merged_data, data_packet)

        if not merged_data:
            continue
            
        # The DataProcessor now trusts plugins to send their best-effort data.
        # Its primary role is to merge, filter, and dispatch.
        # The logic for handling non-operational states is now managed within each plugin.

        # Flatten the merged data for the filter service, apply filters, then re-wrap.
        current_flat = {k: v.get('value') for k, v in merged_data.items()}
        last_good_flat = {k: v.get('value') for k, v in last_good_merged_data.items()} if last_good_merged_data else {}
        filtered_flat = filter_service.apply_all_filters(current_flat, last_good_flat)
        
        # Fix load power calculation: if load = 0 or None but AC Power > 0, set load = AC Power
        load_power = filtered_flat.get(StandardDataKeys.LOAD_TOTAL_POWER_WATTS)
        ac_power = filtered_flat.get(StandardDataKeys.AC_POWER_WATTS)
        
        if (load_power is None or load_power == 0) and isinstance(ac_power, (int, float)) and ac_power > 0:
            logger.debug(f"Load power correction: Load was {load_power}W, AC power is {ac_power}W. Setting load = AC power.")
            filtered_flat[StandardDataKeys.LOAD_TOTAL_POWER_WATTS] = ac_power
        
        final_data_packet = {k: {"value": v} for k, v in filtered_flat.items()}
        
        # The filtered packet is now the new "last known good" data for the next cycle's filter.
        last_good_merged_data = final_data_packet.copy()
        
        if not final_data_packet: 
            logger.warning("Final data packet is empty, skipping cycle.")
            continue

        if not backfill_attempted:
            logger.info("First data packet processed. Triggering yesterday's summary backfill check.")
            db_service.backfill_yesterday_summary()
            backfill_attempted = True
        
        time_remaining_str = _calculate_time_remaining(final_data_packet, app_state)
        final_data_packet[StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT] = {"value": time_remaining_str}
        final_data_packet[StandardDataKeys.SERVER_TIMESTAMP_MS_UTC] = {"value": int(time.time() * 1000)}
        
        # Add individual plugin statuses, which are set by their respective poller threads
        for instance_name, plugin in app_state.active_plugin_instances.items():
            status_key = f"{instance_name}_{StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS}"
            final_data_packet[status_key] = {"value": plugin.connection_status}

        global_conn_status = _calculate_global_status(app_state)
        final_data_packet[StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS] = {"value": global_conn_status}
        
        with app_state.data_lock:
            app_state.shared_data = final_data_packet

        dispatch_package = {
            'merged_data': final_data_packet,
            'per_plugin_data': per_plugin_cache_snapshot
        }
        try:
            while not app_state.processed_data_dispatch_queue.empty():
                try: app_state.processed_data_dispatch_queue.get_nowait()
                except queue.Empty: break
            app_state.processed_data_dispatch_queue.put_nowait(dispatch_package)
            logger.debug("Dispatched comprehensive data package to services queue.")
        except queue.Full:
            logger.warning("Services dispatch queue is full. A data packet was dropped.")

        inverter_status_for_log = final_data_packet.get(StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT, {}).get("value", "Unknown")
        logger.info(f"DataProcessor: Cycle complete. Final Inverter status: '{inverter_status_for_log}'.")
        
        if app_state.enable_tuya:
            inverter_temp_dict = final_data_packet.get(StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS, {})
            inverter_temp_val = inverter_temp_dict.get("value")
            if isinstance(inverter_temp_val, (int, float)):
                tuya_service.trigger_control_from_temp(inverter_temp_val)
            else:
                logger.debug("Skipping Tuya control: Inverter temperature is not a valid number.")

    logger.info("Data Processing thread stopped.")

def _is_data_meaningful(plugin_data: dict, instance_id: str, logger) -> bool:
    """
    Determines if the plugin data contains meaningful values or is in a waiting/null state.
    
    Args:
        plugin_data (dict): The data returned by the plugin
        instance_id (str): The plugin instance identifier
        logger: Logger instance for debug messages
        
    Returns:
        bool: True if data is meaningful, False if it's a waiting/null state
    """
    if not plugin_data:
        return False
    
    # Check for common "waiting" or "null" state indicators
    inverter_status = plugin_data.get(StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT)
    if inverter_status and isinstance(inverter_status, str):
        waiting_states = ['waiting', 'standby', 'idle', 'off', 'sleep']
        if inverter_status.lower() in waiting_states:
            logger.debug(f"Plugin '{instance_id}' data marked as non-meaningful due to status: {inverter_status}")
            return False
    
    # Check if all power values are zero or None (indicating no meaningful activity)
    power_keys = [
        StandardDataKeys.PV_TOTAL_DC_POWER_WATTS,
        StandardDataKeys.AC_POWER_WATTS,
        StandardDataKeys.BATTERY_POWER_WATTS,
        StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS,
        StandardDataKeys.LOAD_TOTAL_POWER_WATTS
    ]
    
    meaningful_power_found = False
    for key in power_keys:
        value = plugin_data.get(key)
        if isinstance(value, (int, float)) and abs(value) > 1:  # More than 1W is considered meaningful
            meaningful_power_found = True
            break
    
    if not meaningful_power_found:
        logger.debug(f"Plugin '{instance_id}' data marked as non-meaningful due to all power values being zero/null")
        return False
    
    return True

def _calculate_global_status(app_state: AppState) -> str:
    """Calculates a single global connection status based on all active plugins.

    The global status is considered "connected" if at least one active plugin
    reports that it is connected. Otherwise, the status is "Disconnected".

    Args:
        app_state (AppState): The application state object, which holds the live
                              connection state for each plugin instance.
    """
    any_connected = any(plugin.is_connected for plugin in app_state.active_plugin_instances.values())
    return STATUS_CONNECTED if any_connected else STATUS_DISCONNECTED
