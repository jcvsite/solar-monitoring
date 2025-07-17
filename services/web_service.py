# services/web_service.py
from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO
import eventlet
import logging
import time
import queue
import threading
import os
import json
from datetime import datetime

from core.app_state import AppState
from services.database_service import DatabaseService
from plugins.plugin_interface import StandardDataKeys
from utils.helpers import format_value_web, STATUS_NA, INIT_VAL

logger = logging.getLogger(__name__)

class WebService:
    def __init__(self, app_state: AppState, db_service: DatabaseService):
        self.app_state = app_state
        self.db_service = db_service
        self.app = Flask(__name__)
        self.app.config['TEMPLATES_AUTO_RELOAD'] = True
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.app.template_folder = os.path.join(project_root, 'templates')
        self.app.static_folder = os.path.join(project_root, 'static')
        
        self.socketio = SocketIO(self.app, async_mode='eventlet', cors_allowed_origins="*")
        
        if self.app_state.enable_web_dashboard:
            self._setup_routes()


    def _setup_routes(self):
        """
        Defines all Flask and SocketIO routes for the web dashboard.
        
        Sets up HTTP routes for serving the main dashboard and BMS viewer,
        as well as SocketIO event handlers for real-time communication
        including data updates, history requests, and client connection management.
        """
        @self.app.route('/')
        def index():
            weather_config = {
                "enabled": self.app_state.enable_weather_widget,
                "use_auto_location": self.app_state.weather_use_automatic_location,
                "default_lat": self.app_state.weather_default_latitude,
                "default_lon": self.app_state.weather_default_longitude,
                "temp_unit": self.app_state.weather_temperature_unit,
                "update_interval_mins": self.app_state.weather_update_interval_minutes,
                "map_zoom_level": self.app_state.weather_map_zoom_level
            }
            return render_template("web_dashboard.html", 
                                   script_version=self.app_state.version, 
                                   weather_config_json=json.dumps(weather_config))

        @self.app.route('/bms')
        def bms_view():
            """Serves the self-contained BMS viewer page."""
            return render_template('bms.html')

        @self.app.route('/static/<path:path>')
        def send_static(path):
            return send_from_directory(self.app.static_folder, path)

        @self.socketio.on('connect')
        def handle_connect():
            sid = request.sid
            self.app_state.web_clients_connected += 1
            logger.info(f"Web client connected: {sid}. Total clients: {self.app_state.web_clients_connected}")
            eventlet.spawn_n(self._wait_and_send_initial_data, sid)

        @self.socketio.on('disconnect')
        def handle_disconnect():
            self.app_state.web_clients_connected = max(0, self.app_state.web_clients_connected - 1)
            logger.info(f"Web client disconnected: {request.sid}. Total clients: {self.app_state.web_clients_connected}")
        
        @self.socketio.on('request_history')
        def handle_request_history(params=None):
            days = params.get('days', 1) if isinstance(params, dict) else 1
            self._send_power_history(days, sid=request.sid)

        @self.socketio.on('request_daily_summary')
        def handle_daily_summary(params=None):
            self._send_daily_summary(params, sid=request.sid)

        @self.socketio.on('request_hourly_summary')
        def handle_hourly_summary(params=None):
            """New handler for hourly data requests."""
            date_str = params.get('date') if isinstance(params, dict) else None
            if not date_str:
                date_str = datetime.now(self.app_state.local_tzinfo).strftime('%Y-%m-%d')
            self._send_hourly_summary(date_str, sid=request.sid)

        @self.socketio.on('request_full_update')
        def handle_request_full_update():
            sid = request.sid
            logger.info(f"Received 'request_full_update' from client {sid}.")
            with self.app_state.data_lock:
                latest_data = self.app_state.shared_data.copy()
            self._send_full_data(latest_data, sid=sid)

    def start(self):
        if not self.app_state.enable_web_dashboard:
            return
        
        eventlet.spawn_n(self._push_live_updates)
        eventlet.spawn_n(self._push_periodic_power_history)
        
        web_thread = threading.Thread(target=self._run_server, name="WebServer", daemon=True)
        web_thread.start()

    def _run_server(self):
        try:
            port = self.app_state.web_dashboard_port
            listen_socket = eventlet.listen(('0.0.0.0', port))
            
            if getattr(self.app_state, 'enable_https', False):
                logger.info(f"Web Service: Starting HTTPS server on 0.0.0.0:{port}")
                eventlet.wsgi.server(listen_socket, self.app,
                                     certfile=self.app_state.tls_config.get("certfile"),
                                     keyfile=self.app_state.tls_config.get("keyfile"))
            else:
                logger.info(f"Web Service: Starting HTTP server on 0.0.0.0:{port}")
                eventlet.wsgi.server(listen_socket, self.app)

        except Exception as e:
            logger.critical(f"Web server failed to start: {e}", exc_info=True)
            self.app_state.main_threads_stop_event.set()

    def _wait_and_send_initial_data(self, client_sid):
        """
        Waits for valid data then sends complete initial state to a new client.
        
        This method runs in a separate greenlet for each connecting client.
        It waits up to 15 seconds for the application to have valid data
        before sending the initial dashboard state to prevent empty dashboards.
        
        Args:
            client_sid: The SocketIO session ID of the connecting client
        """
        timeout = 15
        start_time = time.time()
        snapshot = {}
        while time.time() - start_time < timeout:
            with self.app_state.data_lock:
                snapshot = self.app_state.shared_data.copy()
            if self._is_data_ready(snapshot):
                break
            eventlet.sleep(0.5)
        
        logger.info(f"Sending initial data payload to client {client_sid}.")
        self._send_full_data(snapshot, sid=client_sid)

    def _push_live_updates(self):
        """
        Periodically checks for data changes and pushes incremental updates to all clients.
        
        This method runs in a continuous loop, comparing the current shared data
        with the last sent data to identify changes. Only changed values are sent
        to minimize network traffic and improve dashboard responsiveness.
        """
        logger.info("Web live update push task started.")
        while self.app_state.running:
            try:
                eventlet.sleep(self.app_state.web_update_interval)

                if self.app_state.web_clients_connected > 0:
                    with self.app_state.data_lock:
                        latest_data = self.app_state.shared_data.copy()
                    
                    if latest_data:
                        self._send_incremental_update(latest_data)

            except Exception as e:
                logger.error(f"Web push live updates loop error: {e}", exc_info=True)
                eventlet.sleep(5)

    def _push_periodic_power_history(self):
        """
        Periodically fetches and pushes 24-hour power history to all connected clients.
        
        Runs every 15 minutes to update the power history charts with the latest
        high-resolution data. This ensures charts stay current even for long-running
        dashboard sessions without requiring manual refresh.
        """
        interval = 15 * 60  # 15 minutes
        logger.info(f"Web periodic power history push task started. Interval: {interval}s.")
        while self.app_state.running:
            eventlet.sleep(interval)
            if self.app_state.web_clients_connected > 0:
                logger.info("Pushing periodic 24-hour power history to all clients.")
                self._send_power_history(days=1)

    def _send_full_data(self, data_snapshot, sid):
        """
        Sends a complete, formatted data snapshot to a specific client.
        
        Used for initial client connections and full refresh requests.
        Formats all available data for web display and caches it for
        future incremental update comparisons.
        
        Args:
            data_snapshot: Dictionary containing the current application state
            sid: SocketIO session ID of the target client
        """
        payload = self._prepare_web_payload(data_snapshot)
        if payload:
            self.socketio.emit('full_update', payload, to=sid)
            with self.app_state.data_lock:
                self.app_state.last_sent_data_web = payload.copy()

    def _send_incremental_update(self, data_snapshot):
        """
        Sends only changed data values to all connected clients.
        
        Compares the current data with the last sent data to identify changes,
        then broadcasts only the modified values. This reduces network traffic
        and improves dashboard performance, especially for slow connections.
        
        Args:
            data_snapshot: Dictionary containing the current application state
        """
        full_payload = self._prepare_web_payload(data_snapshot)
        incremental_payload = {}
        with self.app_state.data_lock:
            for key, value in full_payload.items():
                if self.app_state.last_sent_data_web.get(key) != value:
                    incremental_payload[key] = value
                    self.app_state.last_sent_data_web[key] = value
        if incremental_payload:
            self.socketio.emit('update', incremental_payload)

    def _send_power_history(self, days, sid=None):
        """Fetches and sends power_history data."""
        history_data = self.db_service.fetch_history_data(days)
        power_list = []
        if history_data and 'power' in history_data:
            power_list = history_data['power']
        
        payload = {"power": power_list, "requested_days_actual": days}
        
        self.socketio.emit('history_data', payload, to=sid)
        logger.info(f"Sent power_history ({len(power_list)} records, {days} days) to client(s): {'All' if sid is None else sid}")

    def _send_daily_summary(self, params, sid=None):
        """Fetches and sends daily_summary data."""
        summary_data = self.db_service.fetch_daily_summary(params)
        self.socketio.emit('daily_summary_data', summary_data, to=sid)
        logger.info(f"Sent daily_summary (params: {params}) to client(s): {'All' if sid is None else sid}")

    def _send_hourly_summary(self, date_str: str, sid=None):
        """Fetches and sends hourly summary data for a specific date."""
        hourly_data = self.db_service.fetch_hourly_summary(date_str)
        payload = {"date": date_str, "summary": hourly_data}
        self.socketio.emit('hourly_summary_data', payload, to=sid)
        logger.info(f"Sent hourly_summary for {date_str} to client(s): {'All' if sid is None else sid}")

    def _is_data_ready(self, data_snapshot: dict) -> bool:
        """
        Checks if the application has valid data ready for dashboard display.
        
        Validates that essential data like inverter status and PV power are
        available and not in their initial/placeholder states before sending
        to clients. This prevents showing empty or invalid dashboards.
        
        Args:
            data_snapshot: Dictionary containing the current application state
            
        Returns:
            True if data is ready for display, False otherwise
        """
        if not data_snapshot: return False
        inv_status = data_snapshot.get(StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT, {}).get("value", INIT_VAL)
        pv_power = data_snapshot.get(StandardDataKeys.PV_TOTAL_DC_POWER_WATTS, {}).get("value", None)
        return inv_status != INIT_VAL and pv_power is not None
        
    def _prepare_web_payload(self, data_snapshot: dict) -> dict:
        """
        Prepares a flat dictionary of formatted values suitable for the web UI.
        
        Converts the nested application data structure into a flat dictionary
        with properly formatted values for web display. Handles special formatting
        for BMS cell voltages, adds display timestamps, and includes system
        configuration values needed by the dashboard.
        
        Args:
            data_snapshot: Dictionary containing the current application state
            
        Returns:
            Flat dictionary ready for JSON serialization and web display
        """
        payload = {}
        for key, data_dict in data_snapshot.items():
            value = data_dict.get("value")
            
            if "bms_cell_voltage_" in key or key == StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS:
                payload[key] = format_value_web(value, precision=3)
            elif isinstance(value, (list, dict)):
                payload[key] = value
            else:
                payload[key] = format_value_web(value)
        
        payload['display_timestamp'] = datetime.now(self.app_state.local_tzinfo).strftime("%Y-%m-%d %H:%M:%S %Z")
        payload['display_mqtt_connection_status'] = self.app_state.mqtt_last_state or "Disabled"
        payload['display_tuya_status'] = self.app_state.tuya_last_known_state
        
        time_remaining = data_snapshot.get(StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT, {}).get("value", STATUS_NA)
        payload['display_battery_time_remaining'] = time_remaining
        
        payload[StandardDataKeys.CONFIG_PV_INSTALLED_CAPACITY_WATT_PEAK] = self.app_state.pv_installed_capacity_w
        payload[StandardDataKeys.CONFIG_BATTERY_USABLE_CAPACITY_KWH] = self.app_state.battery_usable_capacity_kwh
        payload[StandardDataKeys.CONFIG_BATTERY_MAX_CHARGE_POWER_W] = self.app_state.battery_max_charge_power_w
        payload[StandardDataKeys.CONFIG_BATTERY_MAX_DISCHARGE_POWER_W] = self.app_state.battery_max_discharge_power_w
        
        # Add update notification information
        payload['update_available'] = self.app_state.update_available
        payload['current_version'] = self.app_state.current_version
        payload['latest_version'] = self.app_state.latest_version
        payload['update_check_completed'] = self.app_state.update_check_completed
        
        return payload
