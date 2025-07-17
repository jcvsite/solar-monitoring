# services/mqtt_service.py
import paho.mqtt.client as mqtt
import logging
import threading
import json
import time
import queue
import os
from datetime import timedelta
from typing import Dict, Any, Optional, List

from core.app_state import AppState
from plugins.plugin_interface import DevicePlugin, StandardDataKeys
from utils.helpers import STATUS_ONLINE, STATUS_OFFLINE, STATUS_NA

logger = logging.getLogger(__name__)

class MqttService:
    """
    Manages the connection to an MQTT broker for data publishing and Home Assistant integration.

    This service runs in a dedicated thread and is responsible for:
    - Establishing and maintaining a connection to the MQTT broker.
    - Handling automatic reconnection with exponential backoff.
    - Publishing processed data to various topics.
    - (If enabled) Publishing Home Assistant discovery payloads to automatically
      create and configure entities for the monitored devices.
    """
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.client: mqtt.Client = None
        self._thread: threading.Thread = None
        self.stop_event = threading.Event()
        self._discovered_instances = set()
        self.bridge_device_name = "Solar Monitor Bridge"
        self.bridge_unique_id = "solar_monitor_bridge"
        self._is_connected = threading.Event()
        self._reconnect_delay = 1

    def start(self):
        """
        Starts the MQTT service thread.

        If MQTT is disabled in the configuration, this method returns immediately.
        Otherwise, it spawns the main service thread (`_run`).
        """
        if not self.app_state.enable_mqtt:
            logger.warning("MQTT Service: Disabled by configuration. No data will be published.")
            return
        self._thread = threading.Thread(target=self._run, name="MqttService", daemon=True)
        self._thread.start()

    def stop(self):
        """
        Gracefully stops the MQTT service.

        This method signals the run loop to exit, publishes 'offline' status messages
        for all discovered devices to the MQTT broker, disconnects the client, and
        waits for the service thread to terminate.
        """
        if not self._thread or not self._thread.is_alive():
            return
        logger.info("MQTT Service: Stopping...")
        self.stop_event.set()
        if self.client and self._is_connected.is_set():
            try:
                # Publish offline statuses for all components
                availability_topic = f"{self.app_state.mqtt_topic}/bridge/status"
                self.client.publish(availability_topic, STATUS_OFFLINE, qos=1, retain=True)
                for instance_id in self.app_state.configured_plugin_instance_names:
                    instance_availability_topic = f"{self.app_state.mqtt_topic}/{instance_id}/status"
                    self.client.publish(instance_availability_topic, STATUS_OFFLINE, qos=1, retain=True)
                # Give a moment for messages to go out
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"MQTT Service: Error publishing offline status during stop: {e}")
        
        if self.client:
            self.client.disconnect()
        self._thread.join(timeout=5)
        logger.info("MQTT Service: Stopped.")

    def _setup_client(self):
        """
        Creates and configures the Paho MQTT client object.

        This method sets up the client with the configured client ID, protocol version,
        credentials, and a Last Will and Testament (LWT). The LWT ensures that if the
        service disconnects ungracefully, an 'offline' message is sent to the bridge's
        status topic. It also assigns the `_on_connect` and `_on_disconnect` callbacks.
        """
        config = self.app_state.config
        client_id = config.get('MQTT', 'MQTT_CLIENT_ID', fallback=f"solar_monitor_{os.getpid()}")
        
        # Use MQTTv311 for broader compatibility, especially with older brokers.
        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        username = config.get('MQTT', 'MQTT_USERNAME', fallback=None)
        password = config.get('MQTT', 'MQTT_PASSWORD', fallback=None)
        if username:
            self.client.username_pw_set(username, password)
        
        self.client.will_set(f"{self.app_state.mqtt_topic}/bridge/status", STATUS_OFFLINE, qos=1, retain=True)

    def _run(self):
        """Main run loop for the MQTT service thread.

        This loop manages the connection lifecycle. It attempts to connect to the broker,
        and if successful, enters a sub-loop to process data from the dispatch queue.
        If the connection is lost or fails, it implements an exponential backoff
        strategy for reconnection attempts.
        """
        self._setup_client()
        
        config = self.app_state.config
        broker_host = config.get('MQTT', 'MQTT_HOST', fallback='localhost')
        port = config.getint('MQTT', 'MQTT_PORT', fallback=1883)

        if self.app_state.enable_mqtt_tls:
            self.client.tls_set(
                ca_certs=self.app_state.tls_config.get("ca_certs"),
                certfile=self.app_state.tls_config.get("certfile"),
                keyfile=self.app_state.tls_config.get("keyfile")
            )
            if self.app_state.mqtt_tls_insecure:
                self.client.tls_insecure_set(True)

        while not self.stop_event.is_set():
            try:
                if not self._is_connected.is_set():
                    logger.info(f"MQTT Service: Attempting to connect to broker at {broker_host}:{port}...")
                    self.client.connect(broker_host, port, 60)
                    self.client.loop_start() # Start a background thread for network traffic
                    self._is_connected.wait(timeout=10) # Wait for on_connect callback

                if self._is_connected.is_set():
                    try:
                        dispatch_package = self.app_state.processed_data_dispatch_queue.get(timeout=1.0)
                        if dispatch_package:
                            self._publish_data_packet(dispatch_package)
                    except queue.Empty:
                        continue # Go back to the top of the loop to wait again
                else:
                    # Connection failed or was lost
                    if self.client.is_connected(): self.client.loop_stop() # Stop the background thread if it's running
                    logger.warning(f"MQTT connection failed or was lost after waiting. Retrying in {self._reconnect_delay}s...")
                    self.stop_event.wait(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, 60) # Exponential backoff
            
            except (ConnectionRefusedError, OSError, TimeoutError) as e:
                logger.error(f"MQTT connection error: {e}. Retrying in {self._reconnect_delay}s...")
                self._is_connected.clear()
                if self.client.is_connected(): self.client.loop_stop()
                self.app_state.mqtt_last_state = "Connection Error"
                self.stop_event.wait(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)
            except Exception as e:
                logger.error(f"MQTT Service: Unhandled exception in run loop: {e}", exc_info=True)
                self._is_connected.clear()
                if self.client.is_connected(): self.client.loop_stop()
                self.stop_event.wait(5)
        
        if self.client.is_connected():
            self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, rc):
        """
        Callback executed when the client connects to the MQTT broker.

        Args:
            client: The client instance for this callback.
            userdata: The private user data as set in Client() or user_data_set().
            flags: Response flags sent by the broker.
            rc (int): The connection result. 0 means success.
        """
        if rc == 0:
            self.app_state.mqtt_last_state = "connected"
            self._is_connected.set()
            self._reconnect_delay = 1
            self._discovered_instances.clear()
            logger.info("MQTT Service: Successfully connected to broker. Will attempt HA discovery on next data packet.")
            client.publish(f"{self.app_state.mqtt_topic}/bridge/status", STATUS_ONLINE, qos=1, retain=True)
        else:
            self.app_state.mqtt_last_state = f"Failed ({rc})"
            self._is_connected.clear()
            logger.error(f"MQTT Service: Failed to connect. Return code: {rc} - {mqtt.connack_string(rc)}")

    def _on_disconnect(self, client, userdata, rc):
        """
        Callback executed when the client disconnects from the MQTT broker.

        Args:
            client: The client instance for this callback.
            userdata: The private user data as set in Client() or user_data_set().
            rc (int): The disconnection result.
        """
        self.app_state.mqtt_last_state = "Disconnected"
        self._is_connected.clear()
        if rc != 0:
             logger.warning(f"MQTT Service: Unexpectedly disconnected from broker. RC: {rc}. Reconnection will be attempted.")

    def _calculate_time_remaining(self, data: dict) -> str:
        """
        Calculates a human-readable estimate of battery time remaining.

        This function estimates the time until the battery is full (when charging) or
        reaches a 20% state of charge (when discharging).

        Args:
            data (dict): A dictionary containing the necessary data keys, such as
                         battery power, SOC, and configured capacity.

        Returns:
            str: A formatted string like "~ 2h 30m (to 20%)", "Full", "Idle",
                 or "N/A" if the calculation cannot be performed.
        """
        soc_val = data.get(StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT, {}).get("value")
        power_val = data.get(StandardDataKeys.BATTERY_POWER_WATTS, {}).get("value")
        capacity_kwh = self.app_state.battery_usable_capacity_kwh
        if not all(isinstance(v, (int, float)) for v in [soc_val, power_val, capacity_kwh]) or capacity_kwh <= 0:
            return STATUS_NA
        if abs(power_val) < 25: return "Idle"
        if power_val > 0: # Discharging
            target_soc = 20
            if soc_val <= target_soc: return f"<{target_soc}%"
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

    def _publish_data_packet(self, dispatch_package: dict):
        """
        Publishes a complete data packet to the appropriate MQTT topics.

        This method is the core of the publishing logic. It takes a dispatch package
        from the queue and performs the following actions:
        1. Publishes a flattened, merged view of all data to a general state topic.
        2. For each plugin instance, publishes its specific data to a dedicated state topic.
        3. Publishes an 'online' or 'offline' status to each plugin's availability topic.
        4. If HA discovery is enabled and a plugin hasn't been discovered yet, it triggers
           the discovery process for that plugin.

        Args:
            dispatch_package (dict): The data package from the processed data queue.
        """
        if not self.client or not self._is_connected.is_set(): return
        logger.debug("Publishing data packet to MQTT...")
        
        # We use the full cache snapshot from the dispatch package, not just the live app_state one
        per_plugin_cache_snapshot = dispatch_package.get('per_plugin_data', {})
        merged_data_wrapped = dispatch_package.get('merged_data', {})
        
        # 1. Publish the main merged state topic if there is any data
        flat_merged_data = self._flatten_data_for_json(merged_data_wrapped)
        if flat_merged_data:
            flat_merged_data['display_tuya_status'] = self.app_state.tuya_last_known_state
            self.client.publish(f"{self.app_state.mqtt_topic}/state", json.dumps(flat_merged_data), qos=0, retain=False)

        # Iterate through all configured plugins to manage their availability and state publishing.
        timeout_seconds = self.app_state.mqtt_stale_data_timeout_seconds
        current_time = time.monotonic()

        for instance_id, plugin in self.app_state.active_plugin_instances.items():
            availability_topic = f"{self.app_state.mqtt_topic}/{instance_id}/status"
            
            # Determine availability based on the MQTT-specific timestamp (separate from watchdog)
            with self.app_state.plugin_state_lock:
                last_mqtt_data = self.app_state.mqtt_last_data_timestamp_per_plugin.get(instance_id, 0.0)
            
            is_stale = (current_time - last_mqtt_data) > timeout_seconds if last_mqtt_data > 0.0 else True
            status = STATUS_OFFLINE if is_stale else STATUS_ONLINE
            
            # 2. Publish the availability status for the plugin.
            self.client.publish(availability_topic, status, qos=1, retain=True)

            # 3. Publish the state topic using the cached data, regardless of online/offline status.
            # This ensures the last known values are always available.
            instance_data_wrapped = per_plugin_cache_snapshot.get(instance_id)
            if instance_data_wrapped:
                # Add the globally calculated time remaining to the BMS payload if relevant
                if StandardDataKeys.BATTERY_POWER_WATTS in instance_data_wrapped:
                    instance_data_wrapped[StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT] = merged_data_wrapped.get(StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT)

                flat_instance_data = self._flatten_data_for_json(instance_data_wrapped)
                if flat_instance_data:
                    state_topic = f"{self.app_state.mqtt_topic}/{instance_id}/state"
                    self.client.publish(state_topic, json.dumps(flat_instance_data), qos=0, retain=False)
                
                # 4. Trigger HA discovery if needed, using the cached data.
                if self.app_state.enable_ha_discovery and instance_id not in self._discovered_instances:
                    if self._publish_discovery_for_instance(instance_id, plugin, instance_data_wrapped, merged_data_wrapped):
                        self._discovered_instances.add(instance_id)

    def _flatten_data_for_json(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flattens the standard nested data structure into a simple key-value dictionary,
        explicitly skipping any keys where the value is None.

        This utility converts a dictionary like:
        `{'pv_power': {'value': 100, 'unit': 'W'}}`
        into:
        `{'pv_power': 100}`
        This is useful for creating simple JSON payloads for MQTT.

        Returns:
            Dict[str, Any]: The flattened dictionary.
        """
        flat_data = {}
        if not data_dict: return flat_data
        for key, item in data_dict.items():
            if key.endswith(StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS): continue
            
            value = None
            if isinstance(item, dict) and 'value' in item:
                value = item.get('value')
            elif not isinstance(item, dict):
                 value = item
            
            if value is not None:
                flat_data[key] = value
        return flat_data

    def _get_ha_sensor_definitions(self) -> List[Dict[str, Any]]:
        """
        Returns a master list of all possible sensor definitions for Home Assistant discovery.

        Each dictionary in the list defines a sensor, including its key, name, unit,
        device class, and other HA-specific attributes. This list is used to generate
        the discovery payloads.
        """
        return [
            # Inverter Power & Energy
            {"key": StandardDataKeys.PV_TOTAL_DC_POWER_WATTS, "p": 0, "name": "PV Power", "unit":"W", "device_class":"power", "state_class":"measurement", "icon": "mdi:solar-power", "category": "inverter"},
            {"key": StandardDataKeys.LOAD_TOTAL_POWER_WATTS, "p": 0, "name": "Load Power", "unit":"W", "device_class":"power", "state_class":"measurement", "icon": "mdi:home-lightning-bolt", "category": "inverter"},
            {"key": StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS, "p": 0, "name": "Grid Power", "unit":"W", "device_class":"power", "state_class":"measurement", "icon": "mdi:transmission-tower", "category": "inverter"},
            {"key": StandardDataKeys.ENERGY_PV_DAILY_KWH, "p": 2, "name": "PV Yield Today", "unit": "kWh", "device_class": "energy", "state_class": "total", "icon": "mdi:solar-power-variant", "category": "inverter"},
            {"key": StandardDataKeys.ENERGY_LOAD_DAILY_KWH, "p": 2, "name": "Load Energy Today", "unit": "kWh", "device_class": "energy", "state_class": "total", "icon": "mdi:home-lightning-bolt-outline", "category": "inverter"},
            {"key": StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH, "p": 2, "name": "Grid Import Today", "unit": "kWh", "device_class": "energy", "state_class": "total", "icon": "mdi:transmission-tower-import", "category": "inverter"},
            {"key": StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH, "p": 2, "name": "Grid Export Today", "unit": "kWh", "device_class": "energy", "state_class": "total", "icon": "mdi:transmission-tower-export", "category": "inverter"},
            {"key": StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH, "p": 2, "name": "Battery Charge Today", "unit": "kWh", "device_class": "energy", "state_class": "total", "icon": "mdi:battery-arrow-up", "category": "inverter"},
            {"key": StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH, "p": 2, "name": "Battery Discharge Today", "unit": "kWh", "device_class": "energy", "state_class": "total", "icon": "mdi:battery-arrow-down", "category": "inverter"},
            
            # Inverter Status & Details
             {"key": StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT, "name": "Inverter Status", "icon": "mdi:information-outline", "category": "inverter"},
            {"key": StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS, "p": 1, "name": "Inverter Temperature", "unit": "°C", "device_class": "temperature", "state_class": "measurement", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT1_POWER_WATTS, "p": 0, "name": "PV1 Power", "unit": "W", "device_class": "power", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS, "p": 1, "name": "PV1 Voltage", "unit": "V", "device_class": "voltage", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT1_CURRENT_AMPS, "p": 2, "name": "PV1 Current", "unit": "A", "device_class": "current", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT2_POWER_WATTS, "p": 0, "name": "PV2 Power", "unit": "W", "device_class": "power", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS, "p": 1, "name": "PV2 Voltage", "unit": "V", "device_class": "voltage", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT2_CURRENT_AMPS, "p": 2, "name": "PV2 Current", "unit": "A", "device_class": "current", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT3_POWER_WATTS, "p": 0, "name": "PV3 Power", "unit": "W", "device_class": "power", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT3_VOLTAGE_VOLTS, "p": 1, "name": "PV3 Voltage", "unit": "V", "device_class": "voltage", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT3_CURRENT_AMPS, "p": 2, "name": "PV3 Current", "unit": "A", "device_class": "current", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT4_POWER_WATTS, "p": 0, "name": "PV4 Power", "unit": "W", "device_class": "power", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT4_VOLTAGE_VOLTS, "p": 1, "name": "PV4 Voltage", "unit": "V", "device_class": "voltage", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.PV_MPPT4_CURRENT_AMPS, "p": 2, "name": "PV4 Current", "unit": "A", "device_class": "current", "state_class": "measurement", "icon": "mdi:solar-panel", "category": "inverter"},
            {"key": StandardDataKeys.GRID_L1_VOLTAGE_VOLTS, "p": 1, "name": "Grid L1 Voltage", "unit": "V", "device_class": "voltage", "state_class": "measurement", "icon": "mdi:transmission-tower", "category": "inverter"},
            {"key": StandardDataKeys.GRID_L1_CURRENT_AMPS, "p": 2, "name": "Grid L1 Current", "unit": "A", "device_class": "current", "state_class": "measurement", "icon": "mdi:transmission-tower", "category": "inverter"},
            {"key": StandardDataKeys.GRID_FREQUENCY_HZ, "p": 2, "name": "Grid Frequency", "unit": "Hz", "device_class": "frequency", "state_class": "measurement", "icon": "mdi:sine-wave", "category": "inverter"},

            # Inverter's view of the Battery (and derived values)
            {"key": StandardDataKeys.BATTERY_POWER_WATTS, "p": 0, "name": "Inverter Battery Power", "unit":"W", "device_class":"power", "state_class":"measurement", "icon": "mdi:home-battery", "category": "inverter"},
            {"key": StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT, "p": 1, "name": "Inverter Battery SOC", "unit":"%", "device_class":"battery", "state_class":"measurement", "category": "inverter"},
            {"key": StandardDataKeys.BATTERY_VOLTAGE_VOLTS, "p": 2, "name": "Inverter Battery Voltage", "unit": "V", "device_class": "voltage", "state_class": "measurement", "category": "inverter"},
            {"key": StandardDataKeys.BATTERY_CURRENT_AMPS, "p": 2, "name": "Inverter Battery Current", "unit": "A", "device_class": "current", "state_class": "measurement", "category": "inverter"},
            {"key": StandardDataKeys.BATTERY_STATUS_TEXT, "name": "Inverter Battery Status", "icon": "mdi:information-outline", "category": "inverter"},
            {"key": StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT, "name": "Battery Time Remaining", "icon": "mdi:clock-outline", "category": "inverter"},
            
            # BMS Sensors (and derived values)
            {"key": StandardDataKeys.BATTERY_POWER_WATTS, "p": 0, "name": "BMS Power", "unit":"W", "device_class":"power", "state_class":"measurement", "icon": "mdi:home-battery", "category": "bms"},
            {"key": StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT, "p": 1, "name": "BMS SOC", "unit":"%", "device_class":"battery", "state_class":"measurement", "category": "bms"},
            {"key": StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT, "p": 1, "name": "BMS SOH", "unit":"%", "device_class":"battery", "state_class":"measurement", "icon": "mdi:battery-heart-variant", "category": "bms"},
            {"key": StandardDataKeys.BATTERY_VOLTAGE_VOLTS, "p": 2, "name": "BMS Voltage", "unit": "V", "device_class": "voltage", "state_class": "measurement", "category": "bms"},
            {"key": StandardDataKeys.BATTERY_CURRENT_AMPS, "p": 2, "name": "BMS Current", "unit": "A", "device_class": "current", "state_class": "measurement", "category": "bms"},
            {"key": StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS, "p": 1, "name": "BMS Temperature", "unit": "°C", "device_class": "temperature", "state_class": "measurement", "category": "bms"},
            {"key": StandardDataKeys.BATTERY_CYCLES_COUNT, "name": "BMS Cycles", "icon": "mdi:recycle", "state_class": "total_increasing", "category": "bms"},
            {"key": StandardDataKeys.BATTERY_STATUS_TEXT, "name": "BMS Status", "icon": "mdi:information-outline", "category": "bms"},
            {"key": StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT, "name": "BMS Time Remaining", "icon": "mdi:clock-outline", "category": "bms"},
            {"key": StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS, "p": 3, "name": "BMS Cell Voltage Delta", "unit": "V", "device_class": "voltage", "state_class": "measurement", "icon": "mdi:delta", "category": "bms"},
            {"key": StandardDataKeys.BMS_CHARGE_FET_ON, "name": "BMS Charge FET", "device_class": "power", "category": "bms", "is_binary": True, "icon_template": "{{ 'mdi:power-plug' if value_json.get('bms_charge_fet_on') else 'mdi:power-plug-off' }}"},
            {"key": StandardDataKeys.BMS_DISCHARGE_FET_ON, "name": "BMS Discharge FET", "device_class": "power", "category": "bms", "is_binary": True, "icon_template": "{{ 'mdi:battery-charging' if value_json.get('bms_discharge_fet_on') else 'mdi:battery-off' }}"},
            {"key": StandardDataKeys.BMS_ACTIVE_ALARMS_LIST, "name": "BMS Alarms", "icon": "mdi:alert-box-outline", "category": "bms", "is_list": True},
            {"key": StandardDataKeys.BMS_ACTIVE_WARNINGS_LIST, "name": "BMS Warnings", "icon": "mdi:alert-outline", "category": "bms", "is_list": True},
            {"key": StandardDataKeys.BMS_TEMP_MAX_CELSIUS, "p": 1, "name": "BMS Max Temperature", "unit": "°C", "device_class": "temperature", "state_class": "measurement", "icon": "mdi:thermometer-chevron-up", "category": "bms"},
            {"key": StandardDataKeys.BMS_TEMP_MIN_CELSIUS, "p": 1, "name": "BMS Min Temperature", "unit": "°C", "device_class": "temperature", "state_class": "measurement", "icon": "mdi:thermometer-chevron-down", "category": "bms"},
            {"key": StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS, "p": 3, "name": "BMS Cell Voltage Min", "unit": "V", "device_class": "voltage", "state_class": "measurement", "icon": "mdi:arrow-down-bold-box-outline", "category": "bms"},
            {"key": StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS, "p": 3, "name": "BMS Cell Voltage Max", "unit": "V", "device_class": "voltage", "state_class": "measurement", "icon": "mdi:arrow-up-bold-box-outline", "category": "bms"},
            {"key": StandardDataKeys.BMS_CELL_WITH_MIN_VOLTAGE_NUMBER, "name": "BMS Cell with Min Voltage", "icon": "mdi:numeric-down", "category": "bms"},
            {"key": StandardDataKeys.BMS_CELL_WITH_MAX_VOLTAGE_NUMBER, "name": "BMS Cell with Max Voltage", "icon": "mdi:numeric-up", "category": "bms"},
            {"key": StandardDataKeys.BMS_FULL_CAPACITY_AH, "p": 2, "name": "BMS Full Capacity", "unit": "Ah", "icon": "mdi:battery", "category": "bms"},
            {"key": StandardDataKeys.BMS_REMAINING_CAPACITY_AH, "p": 2, "name": "BMS Remaining Capacity", "unit": "Ah", "icon": "mdi:battery-medium", "category": "bms"},
        ]

    def _publish_discovery_for_instance(self, instance_id: str, plugin: DevicePlugin, instance_data_wrapped: Optional[Dict], merged_data_wrapped: Optional[Dict]) -> bool:
        """
        Publishes Home Assistant discovery configuration for a specific plugin instance.

        This method constructs and publishes the MQTT messages required for Home Assistant
        to automatically discover and configure entities for a given device. It creates a
        device in HA and then attaches all relevant sensors to it.

        Args:
            instance_id (str): The unique identifier for the plugin instance.
            plugin (DevicePlugin): The plugin instance object.
            instance_data_wrapped (Optional[Dict]): The data packet for this specific instance,
                                                     used to determine which sensors to create.
            merged_data_wrapped (Optional[Dict]): The full merged data packet, used to get
                                                  static info like serial numbers.

        Returns:
            bool: True if discovery was successful, False otherwise.
        """
        if not instance_data_wrapped or not merged_data_wrapped:
            logger.debug(f"Discovery for '{instance_id}' deferred: missing instance or merged data.")
            return False

        logger.info(f"Attempting HA Discovery for instance '{instance_id}'...")
        # Use the merged data to get all possible static info
        merged_data_flat = self._flatten_data_for_json(merged_data_wrapped)
        
        device_category = plugin.plugin_config.get("_runtime_device_category", "unknown")
        
        if device_category == "unknown":
            logger.warning(f"Discovery for '{instance_id}' failed: Category is unknown.")
            return False

        bridge_device = {"identifiers": [self.bridge_unique_id], "name": self.bridge_device_name, "manufacturer": "JCV", "model": "Solar-Monitor Core", "sw_version": self.app_state.version}
        if "bridge" not in self._discovered_instances:
            tuya_payload = {"name": "Tuya Fan Status", "has_entity_name": True, "unique_id": f"{self.bridge_unique_id}_tuya_status", "device": bridge_device, "state_topic": f"{self.app_state.mqtt_topic}/state", "value_template": "{{ value_json.get('display_tuya_status', 'Disabled') }}", "icon": "mdi:fan"}
            self.client.publish(f"{self.app_state.ha_discovery_prefix}/sensor/{self.bridge_unique_id}_tuya_status/config", json.dumps(tuya_payload), qos=1, retain=True)
            self._discovered_instances.add("bridge")

        serial_key, mfg_key, fw_key = "", "", ""
        if device_category == "inverter":
            serial_key, mfg_key, fw_key = (StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER, StandardDataKeys.STATIC_INVERTER_MANUFACTURER, StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION)
        elif device_category == "bms":
            serial_key, mfg_key, fw_key = (StandardDataKeys.STATIC_BATTERY_SERIAL_NUMBER, StandardDataKeys.STATIC_BATTERY_MANUFACTURER, StandardDataKeys.STATIC_BATTERY_FIRMWARE_VERSION)
        
        identifier = merged_data_flat.get(serial_key) or instance_id
        
        device_info = { 
            "identifiers": [identifier], "name": instance_id, "model": plugin.pretty_name, 
            "manufacturer": merged_data_flat.get(mfg_key, plugin.name), "via_device": self.bridge_unique_id 
        }
        if fw_key and merged_data_flat.get(fw_key): device_info["sw_version"] = str(merged_data_flat.get(fw_key))
        
        state_topic = f"{self.app_state.mqtt_topic}/{instance_id}/state"
        availability_topic = f"{self.app_state.mqtt_topic}/{instance_id}/status"

        # Publish sensors from master definition list
        for params in self._get_ha_sensor_definitions():
            if params.get("category") != device_category: continue
            if params["key"] not in instance_data_wrapped: continue
            
            entity_type = "binary_sensor" if params.get("is_binary") else "sensor"
            payload = self._build_base_payload(params['name'], f"{identifier}_{params['key']}", device_info, state_topic, availability_topic)
            # This is the critical fix: The value_template must match the flat JSON structure.
            payload["value_template"] = f"{{{{ value_json.get('{params['key']}') }}}}"

            for field in ["unit_of_measurement", "device_class", "state_class", "icon", "icon_template", "entity_category"]:
                if field in params: payload[field] = params[field]
            if "p" in params: payload["suggested_display_precision"] = params["p"]
            if "unit" in params: payload["unit_of_measurement"] = params["unit"]
            # Use native booleans for binary sensors, which is cleaner
            if entity_type == "binary_sensor": payload.update({"payload_on": True, "payload_off": False})
            
            config_topic = f"{self.app_state.ha_discovery_prefix}/{entity_type}/{payload['unique_id']}/config"
            self.client.publish(config_topic, json.dumps(payload), qos=1, retain=True)
            
        if device_category == "bms":
            self._publish_bms_detail_sensors(identifier, device_info, state_topic, availability_topic, instance_data_wrapped, self._flatten_data_for_json(instance_data_wrapped))
            self._publish_bms_flags(identifier, device_info, state_topic, availability_topic, instance_data_wrapped)
            self._publish_master_problem_sensor(identifier, device_info, state_topic, availability_topic, instance_data_wrapped)

        logger.info(f"Finished HA discovery for instance '{instance_id}'.")
        return True

    def _build_base_payload(self, name, unique_id, device_info, state_topic, availability_topic):
        """
        Helper to build the common part of a Home Assistant discovery payload.

        Args:
            name (str): The friendly name of the entity.
            unique_id (str): The unique ID for the entity.
            device_info (dict): The dictionary describing the parent device.
            state_topic (str): The MQTT topic to read the entity's state from.
            availability_topic (str): The MQTT topic to read the entity's availability from.

        Returns:
            dict: A dictionary containing the base payload.
        """
        return {
            "name": name, "has_entity_name": True, "unique_id": unique_id, "device": device_info,
            "state_topic": state_topic, "availability_topic": availability_topic,
            "payload_available": STATUS_ONLINE, "payload_not_available": STATUS_OFFLINE
        }

    def _publish_bms_detail_sensors(self, identifier, device_info, state_topic, availability_topic, data_wrapped, data_flat):
        """
        Publishes discovery payloads for detailed BMS sensors.

        This includes creating individual sensors for each cell's voltage, balancing status,
        and each temperature probe reported by the BMS.
        """
        cell_count = data_flat.get(StandardDataKeys.BMS_CELL_COUNT, 0)
        if isinstance(cell_count, int) and cell_count > 0:
            for i in range(1, cell_count + 1):
                # Cell Voltage
                volt_key = f"bms_cell_voltage_{i}"
                if volt_key in data_wrapped:
                    payload = self._build_base_payload(f"Cell {i} Voltage", f"{identifier}_{volt_key}", device_info, state_topic, availability_topic)
                    payload.update({
                        "value_template": f"{{{{ value_json.get('{volt_key}') | round(3) }}}}",
                        "unit_of_measurement": "V", "device_class": "voltage", "state_class": "measurement",
                        "suggested_display_precision": 3, "entity_category": "diagnostic"
                    })
                    self.client.publish(f"{self.app_state.ha_discovery_prefix}/sensor/{payload['unique_id']}/config", json.dumps(payload), qos=1, retain=True)
                # Cell Balancing
                bal_key = f"bms_cell_balance_active_{i}"
                if bal_key in data_wrapped:
                    payload = self._build_base_payload(f"Cell {i} Balancing", f"{identifier}_{bal_key}", device_info, state_topic, availability_topic)
                    payload.update({
                        "value_template": f"{{{{ 'ON' if value_json.get('{bal_key}') else 'OFF' }}}}",
                        "payload_on": "ON", "payload_off": "OFF", "device_class": "power", "entity_category": "diagnostic"
                    })
                    self.client.publish(f"{self.app_state.ha_discovery_prefix}/binary_sensor/{payload['unique_id']}/config", json.dumps(payload), qos=1, retain=True)

        # Individual temperature sensors
        for key in data_wrapped:
            if key.startswith("bms_temp_sensor_"):
                sensor_name_part = key.replace("bms_temp_sensor_", "").replace("_", " ").title()
                payload = self._build_base_payload(f"Temp {sensor_name_part}", f"{identifier}_{key}", device_info, state_topic, availability_topic)
                payload.update({
                    "value_template": f"{{{{ value_json.get('{key}') | round(1) }}}}",
                    "unit_of_measurement": "°C", "device_class": "temperature", "state_class": "measurement",
                    "suggested_display_precision": 1, "entity_category": "diagnostic"
                })
                self.client.publish(f"{self.app_state.ha_discovery_prefix}/sensor/{payload['unique_id']}/config", json.dumps(payload), qos=1, retain=True)

    def _publish_bms_flags(self, identifier, device_info, state_topic, availability_topic, data_wrapped):
        """
        Auto-discovers all relevant BMS status flags as binary sensors for Home Assistant.

        This method iterates through the data keys, identifies keys that represent a
        status or protection flag, and creates a corresponding binary_sensor in HA.
        """
        for key, data in data_wrapped.items():
            # Find all keys that look like a status flag and have a string value
            if not (key.endswith(('_flag', '_failure', '_lock', '_protection', '_status', '_switch')) and isinstance(data.get('value'), str)):
                continue
            
            # --- FIX #1: More robust filter for internal keys ---
            if "_core_plugin_connection_status" in key:
                continue
            
            # Skip flags we have better, dedicated sensors for (e.g., bms_charge_fet_on)
            if key in [StandardDataKeys.BATTERY_STATUS_TEXT, 'discharge_status_flag', 'charge_status_flag', 'floating_charge_status_flag', 'standby_status_flag', 'power_off_status_flag']:
                continue

            # Give switches a different device_class so they don't look like "problems"
            device_class = "power" if key.endswith("_switch") else "problem"

            payload = self._build_base_payload(
                key.replace("_", " ").title(), f"{identifier}_{key}", 
                device_info, state_topic, availability_topic
            )
            
            acceptable_off_states = ['normal', 'off', 'on', 'idle', 'not_floating', 'not_charging', 'not_discharging', 'standby', 'power_on', 'calibrated', 'synced', 'active']
            
            payload.update({
                "device_class": device_class, 
                "entity_category": "diagnostic",
                "value_template": f"{{{{ 'OFF' if value_json.get('{key}') in {json.dumps(acceptable_off_states)} else 'ON' }}}}",
                "payload_on": "ON", "payload_off": "OFF"
            })
            self.client.publish(f"{self.app_state.ha_discovery_prefix}/binary_sensor/{payload['unique_id']}/config", json.dumps(payload), qos=1, retain=True)
            
    def _publish_master_problem_sensor(self, identifier, device_info, state_topic, availability_topic, data_wrapped):
        """
        Creates a single, aggregated binary_sensor in Home Assistant that is 'ON' if any
        BMS problem is detected.

        This simplifies automations by providing a single entity to monitor for any fault condition.
        """
        
        # --- FIX #2: START ---
        # The list of keys to check MUST be filtered to exclude generic statuses,
        # otherwise normal operation (like 'discharging') will be counted as a problem.
        problem_flag_keys = []
        for key, data in data_wrapped.items():
            # Only consider keys that are actual problem indicators
            if not (key.endswith(('_flag', '_failure', '_lock', '_protection')) and isinstance(data.get('value'), str)):
                continue
            
            # This is the crucial part: explicitly ignore the generic status flags
            if key in [StandardDataKeys.BATTERY_STATUS_TEXT, 'discharge_status_flag', 'charge_status_flag', 'floating_charge_status_flag', 'standby_status_flag', 'power_off_status_flag']:
                continue
            
            problem_flag_keys.append(key)
        
        if not problem_flag_keys: 
            return

        # Use the same comprehensive list of "good" states as the individual sensors
        acceptable_off_states = ['normal', 'off', 'on', 'idle', 'not_floating', 'not_charging', 'not_discharging', 'standby', 'power_on', 'calibrated', 'synced', 'active']
        
        # Build a single, large value_template that checks all problem flags against the "good" list
        conditions = " or ".join([f"value_json.get('{k}') not in {json.dumps(acceptable_off_states)}" for k in problem_flag_keys])
        value_template = f"{{{{ 'ON' if {conditions} else 'OFF' }}}}"
        # --- FIX #2: END ---
        
        payload = self._build_base_payload("BMS Problem", f"{identifier}_master_problem", device_info, state_topic, availability_topic)
        payload.update({
            "device_class": "problem",
            "value_template": value_template,
            "payload_on": "ON", "payload_off": "OFF",
            "icon": "mdi:alert-circle-check-outline"
        })
        self.client.publish(f"{self.app_state.ha_discovery_prefix}/binary_sensor/{payload['unique_id']}/config", json.dumps(payload), qos=1, retain=True)
