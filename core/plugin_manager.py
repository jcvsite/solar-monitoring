# core/plugin_manager.py
import logging
import threading
import time
import inspect
import queue
from typing import Dict, Any, Optional, List, Tuple

from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from core.app_state import AppState
from utils.helpers import (
    trigger_script_restart, STATUS_CONNECTED, STATUS_DISCONNECTED, STATUS_ERROR,
    STATUS_INITIALIZING, FULLY_OPERATIONAL_STATUSES
)
from core.constants import PLUGIN_POLL_THREAD_NAME_PREFIX, WATCHDOG_THREAD_NAME

logger = logging.getLogger(__name__)

def _check_for_data_stagnation(
    data: Dict[str, Any], 
    last_subset: Optional[Dict[str, Any]], 
    counter: int, 
    threshold: int, 
    logger_instance: logging.Logger
) -> Tuple[bool, int, Dict[str, Any]]:
    """
    Checks for data stagnation in an inverter's power flow.

    This helper function compares key power metrics from the current data packet
    with the previous one. If the values are identical for a configured number
    of consecutive polls, it flags the data as stagnant, which can indicate a
    frozen communication link.

    Returns:
        A tuple containing: (is_stagnant, new_counter, new_subset).
    """
    keys_to_check = [
        StandardDataKeys.AC_POWER_WATTS, 
        StandardDataKeys.PV_TOTAL_DC_POWER_WATTS, 
        StandardDataKeys.BATTERY_POWER_WATTS
    ]
    current_subset = {k: data.get(k) for k in keys_to_check}
    
    if last_subset and current_subset == last_subset:
        counter += 1
        logger_instance.debug(f"Power flows static. Stagnation count: {counter}/{threshold}")
    else:
        counter = 0
    
    is_stagnant = counter >= threshold
    if is_stagnant:
        logger_instance.warning(f"Data has been static for {counter} cycles. Declaring stagnation to trigger watchdog.")
        
    return is_stagnant, counter, current_subset

def get_primary_bms_instance_id(app_state: AppState) -> Optional[str]:
    """
    Finds the instance ID of the first configured BMS plugin.

    This function iterates through the active plugin instances in the application state
    and checks each plugin's configuration for a device category of "bms". It returns
    the instance ID of the first plugin found with this category, indicating the
    primary battery management system (BMS) in use.

    Parameters:
        app_state (AppState): The application state object containing information
                              about active plugin instances and their configurations.

    Returns:
        Optional[str]: The instance ID (string) of the primary BMS plugin if found,
                       otherwise None.
    """
    for instance_id, plugin in app_state.active_plugin_instances.items():
        if plugin.plugin_config.get("_runtime_device_category") == "bms":
            return instance_id
    return None

def load_plugin_instance(plugin_type_full: str, instance_name: str, app_state: AppState) -> Optional[DevicePlugin]:
    """
    Loads a single plugin instance based on its type string and config.

    This function dynamically imports and instantiates a plugin class based on the
    provided plugin type string. It expects the type string to follow a
    'category.module_name' format. The function then imports the specified module,
    searches for a concrete subclass of `DevicePlugin`, and instantiates it using
    plugin-specific configurations retrieved from the application's configuration.

    Parameters:
        plugin_type_full (str): A string identifying the plugin's category and module,
                               e.g., "inverter.solis_modbus".
        instance_name (str): A unique name for this specific instance of the plugin.
        app_state (AppState): The application state object providing access to the
                              application's configuration and other global data.

    Returns:
        Optional[DevicePlugin]: An instance of the loaded plugin if successful,
                               otherwise None.
    """
    try:
        if '.' not in plugin_type_full:
            logger.error(f"Invalid plugin_type format '{plugin_type_full}' for instance '{instance_name}'. Expected 'category.module_name'.")
            return None

        category, module_name = plugin_type_full.split('.', 1)
        mod_path = f"plugins.{category}.{module_name}"
        
        plug_mod = __import__(mod_path, fromlist=[module_name])
        
        found_class = None
        for item_name in dir(plug_mod):
            item_obj = getattr(plug_mod, item_name)
            if (isinstance(item_obj, type) and
                    issubclass(item_obj, DevicePlugin) and
                    item_obj is not DevicePlugin and
                    not inspect.isabstract(item_obj)):
                found_class = item_obj
                logger.debug(f"Found concrete plugin class '{found_class.__name__}' in module {mod_path}.")
                break
        
        if not found_class:
            logger.error(f"No valid, non-abstract DevicePlugin subclass found in module {mod_path}.")
            return None

        config_section = f"PLUGIN_{instance_name}"
        plugin_config = dict(app_state.config.items(config_section)) if app_state.config and app_state.config.has_section(config_section) else {}
        
        plugin_config["_instance_name"] = instance_name
        plugin_config["_plugin_category_from_type_string"] = category
        
        logger.info(f"Instantiating plugin '{instance_name}' (Class: {found_class.__name__})")
        return found_class(instance_name=instance_name, plugin_specific_config=plugin_config, main_logger=logger, app_state=app_state)

    except ImportError as e:
        logger.error(f"Cannot import plugin module for type '{plugin_type_full}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error loading plugin instance '{instance_name}': {e}", exc_info=True)
    return None



def poll_single_plugin_instance_thread(instance_id: str, app_state: AppState, data_queue: queue.Queue):
    """
    Dedicated polling thread with intelligent health checks and immediate UI feedback for connection status.

    This function represents the core logic for polling a single plugin instance. It runs in
    its own thread and is responsible for establishing a connection to the plugin's device,
    reading data, handling reconnections, and reporting status updates. The thread also
    implements health checks, including a data stagnation detection mechanism, to ensure
    the reliability of the data stream.

    Key features:
    - **Connection Management:** Attempts to connect to the plugin's device upon startup
      and during reconnections. Reports connection status updates to the shared data store.
    - **Data Acquisition:** Periodically reads both static (initialization) and dynamic
      (real-time) data from the plugin.
    - **Data Reporting:** Puts acquired data into a shared queue for processing by other
      parts of the application. Data packets include the plugin instance ID and the data
      itself (or an indication of failure).
    - **Health Checks:** Monitors data for stagnation by comparing successive power flow
      subsets. If data remains unchanged for a prolonged period, the cycle is marked as
      unsuccessful to trigger a watchdog action (potentially a plugin reload).
    - **Error Handling:** Catches exceptions during connection, data reading, and other
      operations, logging errors and updating the plugin's connection status accordingly.
    - **Thread Control:** Responds to a stop event (from the plugin manager or a watchdog)
      to gracefully terminate the polling loop and disconnect the plugin.

    This function uses a combination of shared memory (via the `app_state` object) and
    thread-safe queues to communicate with other parts of the application.
    """
    thread_logger = logging.getLogger(f"PluginPoll_{instance_id}")
    thread_logger.info("Thread started.")

    stop_event = app_state.plugin_stop_events.get(instance_id)
    if not stop_event:
        thread_logger.error("Could not find its stop_event in AppState. Thread exiting.")
        return

    last_power_flow_subset = None
    stagnation_counter = 0
    stagnation_threshold = (5 * 60) // app_state.poll_interval if app_state.poll_interval > 0 else 20

    local_static_data_cache: Dict[str, Any] = {}
    static_data_read_success = False
    status_key = f"{instance_id}_{StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS}"

    while app_state.running and not stop_event.is_set():
        cycle_start_time = time.monotonic()
        plugin_inst = app_state.active_plugin_instances.get(instance_id)
        if not plugin_inst:
            thread_logger.error("Plugin instance disappeared from active list. Thread exiting.")
            break

        try:
            if stop_event.is_set(): break
            
            # --- Connection Handling with retries and backoff ---
            if not plugin_inst.is_connected:
                reconnect_attempts = 0
                max_reconnect_attempts = 3
                while not plugin_inst.is_connected and reconnect_attempts < max_reconnect_attempts and not stop_event.is_set():
                    reconnect_attempts += 1
                    plugin_inst.connection_status = f"Connecting... ({reconnect_attempts})"
                    thread_logger.info(f"Attempting to connect... (Attempt {reconnect_attempts}/{max_reconnect_attempts})")
                    
                    # Provide immediate UI feedback
                    with app_state.data_lock:
                        app_state.shared_data.setdefault(status_key, {})["value"] = plugin_inst.connection_status

                    if plugin_inst.connect():
                        plugin_inst.connection_status = "connected"
                        thread_logger.info("Connection successful.")
                        break 
                    else:
                        plugin_inst.connection_status = "Connect Failed"
                        backoff_delay = min(2 ** reconnect_attempts, 15)
                        thread_logger.warning(f"Connection attempt {reconnect_attempts} failed. Waiting {backoff_delay}s.")
                        stop_event.wait(timeout=backoff_delay)
                
                if not plugin_inst.is_connected:
                    thread_logger.error(f"Failed to connect after {max_reconnect_attempts} attempts. Will retry after poll interval.")
                    with app_state.plugin_state_lock:
                        app_state.plugin_consecutive_failures[instance_id] = app_state.plugin_consecutive_failures.get(instance_id, 0) + 1
                    # Sleep for the main poll interval before trying the whole connection loop again
                    stop_event.wait(timeout=app_state.poll_interval)
                    continue
            
            # --- Data Polling ---
            is_this_cycle_truly_successful = False

            if plugin_inst.is_connected:
                final_data_for_global = {}

                if not static_data_read_success:
                    static_data = plugin_inst.read_static_data()
                    if static_data:
                        local_static_data_cache = static_data
                        static_data_read_success = True
                        plugin_inst.plugin_config["_runtime_device_category"] = static_data.get(StandardDataKeys.STATIC_DEVICE_CATEGORY, "unknown")
                        thread_logger.info(f"Successfully read static data. Device category: '{static_data.get(StandardDataKeys.STATIC_DEVICE_CATEGORY)}'")
                    else:
                        thread_logger.warning("Failed to read static data on first attempt after connect.")
                
                final_data_for_global.update(local_static_data_cache)
                
                dynamic_data = plugin_inst.read_dynamic_data()
                if dynamic_data is not None:
                    is_this_cycle_truly_successful = True # Assume success initially
                    final_data_for_global.update(dynamic_data)

                    # --- Stagnation Check (only for operational inverters) ---
                    device_category = plugin_inst.plugin_config.get("_runtime_device_category", "unknown")
                    if device_category == "inverter":
                        inverter_status = final_data_for_global.get(StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT)
                        if inverter_status in FULLY_OPERATIONAL_STATUSES:
                            is_stagnant, stagnation_counter, last_power_flow_subset = _check_for_data_stagnation(
                                final_data_for_global, last_power_flow_subset, stagnation_counter, stagnation_threshold, thread_logger
                            )
                            if is_stagnant:
                                is_this_cycle_truly_successful = False
                                plugin_inst.connection_status = "Stalled"
                        else:
                            # Not generating, so reset stagnation counter
                            stagnation_counter = 0
                            last_power_flow_subset = None
                            # For watchdog purposes, "Waiting" is still a successful connection
                            # Only mark as unsuccessful if there's an actual connection/communication problem
                            waiting_states = ['waiting', 'standby', 'idle', 'off', 'sleep']
                            if inverter_status and inverter_status.lower() in waiting_states:
                                is_this_cycle_truly_successful = True  # Waiting is normal, not a failure
                                thread_logger.debug(f"Inverter in normal waiting state ('{inverter_status}'). Marking as successful for watchdog.")
                            else:
                                is_this_cycle_truly_successful = False
                                thread_logger.info(f"Inverter reported a non-generating status ('{inverter_status}'). Cycle not marked as successful for watchdog.")
                
                else: # dynamic_data is None, indicating a read failure
                    is_this_cycle_truly_successful = False
                    plugin_inst.connection_status = STATUS_ERROR
                    thread_logger.warning("Dynamic data read failed (plugin returned None).")
                
            # --- Update global state based on cycle outcome ---
            # Separate MQTT availability from watchdog success criteria
            data_was_read_successfully = (dynamic_data is not None and plugin_inst.is_connected)
            
            if is_this_cycle_truly_successful:
                plugin_inst.connection_status = STATUS_CONNECTED
                data_queue.put({'instance_id': instance_id, 'data': final_data_for_global})
                with app_state.plugin_state_lock:
                    app_state.last_successful_poll_timestamp_per_plugin[instance_id] = time.monotonic()
                    app_state.mqtt_last_data_timestamp_per_plugin[instance_id] = time.monotonic()
                    app_state.plugin_consecutive_failures[instance_id] = 0
            else:
                # Even if cycle isn't "truly successful" for watchdog purposes,
                # update MQTT timestamp if we successfully read data
                if data_was_read_successfully:
                    with app_state.plugin_state_lock:
                        app_state.last_successful_poll_timestamp_per_plugin[instance_id] = time.monotonic()
                        app_state.mqtt_last_data_timestamp_per_plugin[instance_id] = time.monotonic()
                
                # Send an empty packet to the processor to signal failure for this cycle
                data_queue.put({'instance_id': instance_id, 'data': None})
                with app_state.plugin_state_lock:
                    if not data_was_read_successfully:  # Only increment failures if we truly failed to read data
                        app_state.plugin_consecutive_failures[instance_id] = app_state.plugin_consecutive_failures.get(instance_id, 0) + 1
                if not plugin_inst.is_connected:
                    plugin_inst.connection_status = STATUS_DISCONNECTED
            
            # Update the UI status for this plugin
            with app_state.data_lock:
                app_state.shared_data.setdefault(status_key, {})["value"] = plugin_inst.connection_status

        except Exception as e:
            thread_logger.error(f"Unhandled exception in poll loop: {e}", exc_info=True)
            with app_state.plugin_state_lock:
                app_state.plugin_consecutive_failures[instance_id] = app_state.plugin_consecutive_failures.get(instance_id, 0) + 1
            plugin_inst.connection_status = STATUS_ERROR
            with app_state.data_lock:
                app_state.shared_data.setdefault(status_key, {})["value"] = plugin_inst.connection_status

        cycle_duration = time.monotonic() - cycle_start_time
        sleep_time = max(0.1, app_state.poll_interval - cycle_duration)
        if app_state.running:
            stop_event.wait(timeout=sleep_time)

    plugin_inst = app_state.active_plugin_instances.get(instance_id)
    if plugin_inst:
        thread_logger.info("Stop event received, disconnecting plugin...")
        try:
            plugin_inst.disconnect()
        except Exception as e:
            thread_logger.error(f"Error during self-disconnect: {e}")
    thread_logger.info("Thread stopped gracefully.")

def attempt_plugin_reinitialization(instance_id: str, reason: str, app_state: AppState):
    """
    Attempts to reload and restart a plugin instance.

    This function is called by the watchdog when a plugin is detected as stalled
    or failing. It stops the existing plugin thread, removes the plugin from the
    active instances, reloads it from scratch, and starts a new polling thread.

    Args:
        instance_id (str): The unique identifier of the plugin instance to reload.
        reason (str): A descriptive reason for the reload (e.g., "stalled", "failed").
        app_state (AppState): The application state object containing plugin information.
    """
    logger.warning(f"Attempting to reinitialize plugin '{instance_id}' due to: {reason}")
    
    # Clean up curses service to prevent color corruption when threads restart
    try:
        if hasattr(app_state, 'curses_service') and app_state.curses_service:
            app_state.curses_service.force_cleanup()
    except Exception as e:
        logger.debug(f"Error during curses cleanup on plugin restart: {e}")
    
    with app_state.plugin_reload_lock:
        # Stop the existing plugin thread
        stop_event = app_state.plugin_stop_events.get(instance_id)
        if stop_event:
            stop_event.set()
            
        # Wait for thread to stop
        existing_thread = app_state.plugin_polling_threads.get(instance_id)
        if existing_thread and existing_thread.is_alive():
            logger.info(f"Waiting for plugin thread '{instance_id}' to stop...")
            existing_thread.join(timeout=5.0)
            if existing_thread.is_alive():
                logger.error(f"Plugin thread '{instance_id}' did not stop gracefully")
        
        # Disconnect and remove the old plugin instance
        old_plugin = app_state.active_plugin_instances.get(instance_id)
        if old_plugin:
            try:
                old_plugin.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting old plugin '{instance_id}': {e}")
            del app_state.active_plugin_instances[instance_id]
        
        # Clean up thread references
        if instance_id in app_state.plugin_polling_threads:
            del app_state.plugin_polling_threads[instance_id]
        if instance_id in app_state.plugin_stop_events:
            del app_state.plugin_stop_events[instance_id]
        
        # Get plugin type from config
        plugin_type = app_state.config.get(f"PLUGIN_{instance_id}", "plugin_type", fallback=None)
        if not plugin_type:
            logger.error(f"Cannot reinitialize plugin '{instance_id}': plugin_type not found in config")
            return
        
        # Reload the plugin instance
        new_plugin = load_plugin_instance(plugin_type, instance_id, app_state)
        if not new_plugin:
            logger.error(f"Failed to reload plugin instance '{instance_id}'")
            return
        
        app_state.active_plugin_instances[instance_id] = new_plugin
        
        # Create new thread and start it
        new_stop_event = threading.Event()
        app_state.plugin_stop_events[instance_id] = new_stop_event
        
        new_thread = threading.Thread(
            target=poll_single_plugin_instance_thread,
            args=(instance_id, app_state, app_state.plugin_data_queue),
            name=f"PluginPoll_{instance_id}",
            daemon=True
        )
        app_state.plugin_polling_threads[instance_id] = new_thread
        new_thread.start()
        
        # Reset failure counters but preserve MQTT timestamp to avoid false unavailable states
        with app_state.plugin_state_lock:
            app_state.plugin_consecutive_failures[instance_id] = 0
            app_state.last_successful_poll_timestamp_per_plugin[instance_id] = 0.0
            # Don't reset mqtt_last_data_timestamp_per_plugin - let it maintain availability during reconnection
        
        logger.info(f"Successfully reinitialized plugin '{instance_id}'")


def thread_health_monitor(app_state: AppState):
    """
    Thread health monitor that periodically checks if all required threads are running
    and automatically restarts any dead threads.
    
    This runs independently of the watchdog and focuses purely on thread lifecycle management.
    """
    logger.info("Thread Health Monitor: Starting with 60s check interval...")
    
    while app_state.running:
        time.sleep(60)  # Check every minute
        if not app_state.running:
            break
            
        try:
            # Get list of all currently running threads
            current_threads = {t.name: t for t in threading.enumerate() if t.is_alive()}
            
            # Check each plugin thread
            for instance_id in list(app_state.active_plugin_instances.keys()):
                expected_thread_name = f"{PLUGIN_POLL_THREAD_NAME_PREFIX}_{instance_id}"
                
                if expected_thread_name not in current_threads:
                    # Check if another process is already restarting this plugin
                    with app_state.plugin_restart_lock:
                        if instance_id in app_state.plugins_being_restarted:
                            logger.debug(f"Thread Health Monitor: Plugin '{instance_id}' is already being restarted by watchdog. Skipping.")
                            continue
                        
                        # Mark plugin as being restarted to prevent watchdog conflicts
                        app_state.plugins_being_restarted.add(instance_id)
                    
                    try:
                        logger.warning(f"Thread Health Monitor: Plugin thread '{expected_thread_name}' is not running. Restarting...")
                        
                        # Remove the dead thread from tracking
                        if instance_id in app_state.plugin_polling_threads:
                            del app_state.plugin_polling_threads[instance_id]
                        
                        # Create new stop event if needed
                        if instance_id not in app_state.plugin_stop_events:
                            app_state.plugin_stop_events[instance_id] = threading.Event()
                        
                        # Start a new thread for this plugin
                        new_thread = threading.Thread(
                            target=poll_single_plugin_instance_thread,
                            args=(instance_id, app_state, app_state.plugin_data_queue),
                            name=expected_thread_name,
                            daemon=True
                        )
                        app_state.plugin_polling_threads[instance_id] = new_thread
                        new_thread.start()
                        
                        # Reset failure counters for the restarted plugin
                        with app_state.plugin_state_lock:
                            app_state.plugin_consecutive_failures[instance_id] = 0
                            # Don't reset timestamps to avoid MQTT availability issues
                        
                        logger.info(f"Thread Health Monitor: Successfully restarted plugin thread '{expected_thread_name}'")
                    
                    finally:
                        # Always remove from restart set when done
                        with app_state.plugin_restart_lock:
                            app_state.plugins_being_restarted.discard(instance_id)
                else:
                    # Thread exists, check if it's actually responsive
                    thread = current_threads[expected_thread_name]
                    if not thread.is_alive():
                        logger.warning(f"Thread Health Monitor: Plugin thread '{expected_thread_name}' exists but is not alive. Will restart on next check.")
            
            # Check if watchdog thread is running
            if WATCHDOG_THREAD_NAME not in current_threads:
                logger.warning("Thread Health Monitor: Watchdog thread is not running. Restarting...")
                watchdog_thread = threading.Thread(
                    target=monitor_plugins_thread,
                    args=(app_state,),
                    name=WATCHDOG_THREAD_NAME,
                    daemon=True
                )
                watchdog_thread.start()
                logger.info("Thread Health Monitor: Successfully restarted watchdog thread")
                
        except Exception as e:
            logger.error(f"Thread Health Monitor: Error during health check: {e}", exc_info=True)
    
    logger.info("Thread Health Monitor: Stopped")

def monitor_plugins_thread(app_state: AppState):
    """
    The watchdog thread. Monitors the health of plugin polling threads.

    This function runs in its own thread and acts as a watchdog for monitoring the
    health and responsiveness of individual plugin polling threads. It periodically
    checks each active plugin instance for signs of stalling or failure, and attempts
    to re-initialize any problematic plugins.

    Key monitoring aspects:
    - **Stall Detection:** Tracks the last successful data poll time for each plugin. If
      a plugin exceeds a predefined timeout (`app_state.watchdog_timeout`) without a
      successful poll, it's considered stalled. An initial grace period
      (`app_state.watchdog_grace_period`) is applied at startup to allow plugins to
      initialize.
    - **Failure Tracking:** Monitors consecutive failure counts for each plugin, as
      updated by the polling threads. This information is used in conjunction with
      stall detection to determine if a re-initialization attempt is warranted.
    - **Re-initialization:** If a plugin is detected as stalled and the number of
      consecutive failures is below a threshold (`app_state.max_plugin_reload_attempts`),
      the function calls `attempt_plugin_reinitialization` to reload and restart the
      plugin.
    - **Critical Failure Handling:** If a plugin fails to recover after the maximum
      allowed re-initialization attempts, the function triggers a full script restart
      via `trigger_script_restart`, assuming a critical and unrecoverable system state.
    """
    logger.info("Watchdog: Starting grace period of %ss...", app_state.watchdog_grace_period)
    time.sleep(app_state.watchdog_grace_period)
    logger.info(f"Watchdog: Monitoring active (Timeout: {app_state.watchdog_timeout}s).")

    thread_start_times = {name: time.monotonic() for name in app_state.active_plugin_instances.keys()}

    while app_state.running:
        current_time = time.monotonic()
        time.sleep(15) 
        if not app_state.running: break

        for instance_id in list(app_state.active_plugin_instances.keys()):
            with app_state.plugin_state_lock:
                last_success = app_state.last_successful_poll_timestamp_per_plugin.get(instance_id, 0.0)
                failures = app_state.plugin_consecutive_failures.get(instance_id, 0)
            
            is_stalled = False
            
            if last_success == 0.0:
                initial_timeout = app_state.watchdog_grace_period + app_state.watchdog_timeout
                start_time = thread_start_times.get(instance_id, current_time)
                if (current_time - start_time) > initial_timeout:
                    logger.warning(
                        f"Watchdog: Plugin '{instance_id}' has not completed its first successful poll "
                        f"within the initial timeout of {initial_timeout:.0f}s. Declaring stalled."
                    )
                    is_stalled = True
            
            elif (current_time - last_success) > app_state.watchdog_timeout:
                logger.warning(f"Watchdog: Plugin '{instance_id}' has stalled. Last successful poll was {current_time - last_success:.1f}s ago.")
                is_stalled = True

            if is_stalled:
                # Check if another process is already restarting this plugin
                with app_state.plugin_restart_lock:
                    if instance_id in app_state.plugins_being_restarted:
                        logger.debug(f"Watchdog: Plugin '{instance_id}' is already being restarted by another process. Skipping.")
                        continue
                    
                    if failures < app_state.max_plugin_reload_attempts:
                        # Mark plugin as being restarted
                        app_state.plugins_being_restarted.add(instance_id)
                        thread_start_times[instance_id] = time.monotonic()
                        
                        try:
                            attempt_plugin_reinitialization(instance_id, "stalled", app_state)
                        finally:
                            # Always remove from restart set when done
                            app_state.plugins_being_restarted.discard(instance_id)
                    else:
                        msg = f"Plugin '{instance_id}' failed to recover after {failures + 1} attempts. Triggering full script restart."
                        logger.critical(msg)
                        trigger_script_restart(msg)
                        return
