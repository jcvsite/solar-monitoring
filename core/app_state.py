# core/app_state.py
import threading
import queue
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional, List

from utils.helpers import TUYA_STATE_UNKNOWN

class AppState:
    """
    Centralized application state management class.
    
    This class serves as the single source of truth for all shared application state,
    including configuration, plugin instances, threading primitives, and runtime data.
    It provides thread-safe access to shared resources and maintains consistency
    across all application components.
    
    Key responsibilities:
    - Configuration storage and access
    - Plugin instance management
    - Thread synchronization primitives
    - Shared data caching
    - Service state tracking
    - MQTT and web service coordination
    """
    def __init__(self, version: str):
        # Version and Lifecycle
        self.version = version
        self.running = True
        self.restart_triggered = False
        self.main_threads_stop_event = threading.Event()
        self.plugin_stop_events: Dict[str, threading.Event] = {}

        # Configuration (will be populated by config_loader)
        self.config = None
        self.poll_interval = 15
        self.local_tzinfo = None
        self.configured_plugin_instance_names: List[str] = []
        self.alert_categories_display_order = ["status", "grid", "eps", "battery", "inverter", "bms"]
        
        # MQTT State
        self.enable_mqtt = False
        self.mqtt_client: Optional[mqtt.Client] = None
        self.mqtt_topic = "inverter"
        self.availability_topic = f"{self.mqtt_topic}/availability"
        self.mqtt_last_state: Optional[str] = None
        self.enable_ha_discovery = False
        self.ha_discovery_prefix = "homeassistant"
        self.enable_mqtt_tls = False
        self.mqtt_tls_insecure = False

        # Web Service State
        self.enable_web_dashboard = False
        self.web_dashboard_port = 8081
        self.web_update_interval = 2.0
        self.web_clients_connected = 0
        self.last_sent_data_web: Dict[str, Any] = {}
        self.enable_https = False

        # TLS Configuration (shared)
        self.tls_config: Dict[str, Optional[str]] = {
            "ca_certs": None,
            "certfile": None,
            "keyfile": None,
        }

        # Plugin & Polling State
        self.active_plugin_instances: Dict[str, 'DevicePlugin'] = {}
        self.plugin_polling_threads: Dict[str, threading.Thread] = {}
        self.plugin_data_queue = queue.Queue(maxsize=100) # For raw data from plugins to processor
        self.processed_data_dispatch_queue = queue.Queue(maxsize=5) # For final data to consumers (MQTT, Web)
        self.per_plugin_data_cache: Dict[str, Dict[str, Any]] = {} # <-- MODIFIED: Centralized per-plugin cache
        self.plugin_consecutive_failures: Dict[str, int] = {}
        self.last_successful_poll_timestamp_per_plugin: Dict[str, float] = {}
        self.mqtt_last_data_timestamp_per_plugin: Dict[str, float] = {}  # Separate timestamp for MQTT availability
        self.max_plugin_reload_attempts = 3
        
        # Thread restart coordination
        self.plugin_restart_lock = threading.Lock()  # Prevents conflicts between watchdog and thread monitor
        self.plugins_being_restarted: set = set()  # Track which plugins are currently being restarted
        
        # System-wide Configuration from config.ini
        self.pv_installed_capacity_w: float = 0.0
        self.inverter_max_ac_power_w: float = 0.0
        self.battery_usable_capacity_kwh: float = 0.0
        self.battery_max_charge_power_w: float = 0.0
        self.battery_max_discharge_power_w: float = 0.0
        self.default_mppt_count: int = 2
        
        # Shared Data for Curses UI
        self.shared_data: Dict[str, Dict[str, Any]] = {}
        
        # Locks
        self.data_lock = threading.RLock()
        self.db_lock = threading.RLock()
        self.plugin_reload_lock = threading.RLock()
        self.plugin_state_lock = threading.RLock()
        self.tuya_lock = threading.RLock()

        # Tuya State
        self.enable_tuya = False
        self.tuya_device_id: Optional[str] = None
        self.tuya_local_key: Optional[str] = None
        self.tuya_ip_address: Optional[str] = None
        self.tuya_version: float = 3.4
        self.temp_threshold_on: Optional[float] = None
        self.temp_threshold_off: Optional[float] = None
        self.tuya_device: Optional['tinytuya.OutletDevice'] = None 
        self.tuya_last_known_state: str = TUYA_STATE_UNKNOWN
        self.tuya_last_state_change_time: float = 0.0

        # Data Filtering State
        self.filtering_mode = "adaptive"
        self.last_valid_energy_values: Dict[str, Optional[float]] = {}
        self.last_valid_energy_timestamps: Dict[str, Optional[int]] = {}
        self.last_valid_power_values: Dict[str, Optional[float]] = {}
        self.last_valid_power_timestamps: Dict[str, Optional[int]] = {}
        self.last_valid_temperature_values: Dict[str, Optional[float]] = {}
        self.last_valid_temperature_timestamps: Dict[str, Optional[int]] = {}
        
        # Configurable Daily Energy Limits (kWh) for filtering
        self.daily_limit_grid_import_kwh: float = 100.0
        self.daily_limit_grid_export_kwh: float = 50.0
        self.daily_limit_battery_charge_kwh: float = 50.0
        self.daily_limit_battery_discharge_kwh: float = 50.0
        self.daily_limit_pv_generation_kwh: float = 80.0
        self.daily_limit_load_consumption_kwh: float = 120.0

        # Watchdog
        self.watchdog_timeout = 90
        self.watchdog_grace_period = 45

        # Weather Widget State
        self.enable_weather_widget = False
        self.weather_use_automatic_location = True
        self.weather_default_latitude: float = 51.5072
        self.weather_default_longitude: float = -0.1276
        self.weather_temperature_unit: str = "celsius"
        self.weather_update_interval_minutes: int = 15
        self.weather_map_zoom_level: int = 5
