"""
Main entry point for the Solar Monitoring application.

This script orchestrates the entire application lifecycle:
- Initializes the eventlet monkey patch for async operations.
- Sets up logging.
- Loads configuration and validates it.
- Prevents multiple instances from running using a lock file.
- Initializes all core services (Database, MQTT, Web, etc.).
- Dynamically loads and starts all configured plugins in separate threads.
- Starts the data processor and watchdog threads.
- Handles graceful shutdown on SIGINT/SIGTERM signals.
"""

# Monkey patch standard libraries for eventlet compatibility.
# This must be done at the very top, before other standard libraries are imported.
import eventlet
eventlet.monkey_patch()

import logging
from logging.handlers import RotatingFileHandler
import pathlib
import sys
import threading
import signal
import time
import queue
from typing import Callable

from core.app_state import AppState
from core.config_loader import load_configuration, validate_core_config
from core.plugin_manager import (
    load_plugin_instance,
    poll_single_plugin_instance_thread,
    monitor_plugins_thread,
    thread_health_monitor
)
from core.data_processor import process_and_merge_data
from core.constants import *
from services.database_service import DatabaseService
from services.mqtt_service import MqttService
from services.web_service import WebService
from services.curses_service import CursesService
from services.tuya_service import TuyaService
from services.data_filter_service import DataFilterService
from utils.lock import acquire_lock, cleanup_lock_file

# Application version
__version__ = "1.3.1"


def setup_logging(app_state: AppState):
    """
    Sets up logging to console and a rotating file based on the configuration.

    Args:
        app_state: The application state object containing the loaded config.
    """
    log_level_str = app_state.config.get('LOGGING', 'LOG_LEVEL', fallback='INFO').upper()
    
    log_levels = {
        "DEBUG": logging.DEBUG, "INFO": logging.INFO,
        "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL,
    }
    effective_log_level = log_levels.get(log_level_str, logging.INFO)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(effective_log_level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter('%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s')
    
    if not app_state.config.getboolean('CONSOLE_DASHBOARD', 'ENABLE_DASHBOARD', fallback=False):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if app_state.config.getboolean('LOGGING', 'LOG_TO_FILE', fallback=True):
        log_file_path = pathlib.Path(__file__).parent / LOG_FILE_NAME
        
        file_handler = RotatingFileHandler( # type: ignore
            log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        logging.info(f"Logging to file: {log_file_path}")

    logging.info(f"Logging level set to {log_level_str}.")


def graceful_exit(app_state: AppState) -> Callable[[int, object | None], None]:
    """
    Creates a signal handler function to ensure a clean shutdown.

    This function, when called by a signal (like SIGINT/Ctrl-C), will set
    the application's running flag to False, triggering a coordinated shutdown
    of all threads and services.

    Args:
        app_state: The global application state.

    Returns:
        A signal handler function.
    """
    def handler(signum, frame):
        if not app_state.running:
            return
        logger = logging.getLogger(CORE_LOGGER_NAME)
        logger.warning(f"Shutdown signal ({signal.Signals(signum).name}) received. Cleaning up...")
        app_state.running = False
        app_state.main_threads_stop_event.set()
    return handler


if __name__ == "__main__":
    # --- 1. Initial Setup ---
    script_dir = pathlib.Path(__file__).parent.resolve()
    app_state = AppState(version=__version__)
    
    config_file = script_dir / CONFIG_FILE_NAME
    load_configuration(config_file, app_state)
    
    setup_logging(app_state)
    logger = logging.getLogger(CORE_LOGGER_NAME)
    logger.info(f"--- Starting Solar Monitoring v{__version__} ---")

    if not acquire_lock(str(script_dir / LOCK_FILE_NAME)):
        logger.critical("Another instance is already running. Exiting.")
        sys.exit(1)

    # Validate critical configuration settings. This will exit if config is invalid.
    validate_core_config(app_state)
    
    # --- 2. Initialize Core Services ---
    logger.info("Initializing core services...")
    db_service = DatabaseService(app_state)
    mqtt_service = MqttService(app_state)
    web_service = WebService(app_state, db_service)
    curses_service = CursesService(app_state)
    # Store curses service in app_state so plugin manager can access it for cleanup
    app_state.curses_service = curses_service
    tuya_service = TuyaService(app_state)
    filter_service = DataFilterService(app_state)

    # --- 3. Load Plugins ---
    logger.info("Loading configured plugins...")
    for name in app_state.configured_plugin_instance_names:
        plugin_type = app_state.config.get(f"PLUGIN_{name}", "plugin_type")
        instance = load_plugin_instance(plugin_type, name, app_state)
        if instance:
            app_state.active_plugin_instances[name] = instance
    
    if not app_state.active_plugin_instances:
        logger.critical("No plugins were loaded successfully. Exiting.")
        cleanup_lock_file()
        sys.exit(1)

    # --- 4. Setup Graceful Shutdown ---
    signal.signal(signal.SIGINT, graceful_exit(app_state))  # Handle Ctrl-C
    signal.signal(signal.SIGTERM, graceful_exit(app_state)) # Handle systemctl stop, docker stop

    # --- 5. Create and Start Core Threads ---
    logger.info("Creating and starting core threads...")
    threads = []

    # Data Processor Thread: Consumes from plugins, processes, and dispatches data.
    proc_thread = threading.Thread(
        target=process_and_merge_data,
        args=(app_state, db_service, tuya_service, filter_service, app_state.plugin_data_queue),
        name=DATA_PROCESSOR_THREAD_NAME, daemon=True
    )
    threads.append(proc_thread)

    # Individual Plugin Polling Threads: One thread per hardware device.
    for name in app_state.active_plugin_instances:
        stop_event = threading.Event()
        app_state.plugin_stop_events[name] = stop_event
        thread = threading.Thread(
            target=poll_single_plugin_instance_thread,
            args=(name, app_state, app_state.plugin_data_queue),
            name=f"{PLUGIN_POLL_THREAD_NAME_PREFIX}_{name}", daemon=True
        )
        app_state.plugin_polling_threads[name] = thread
        threads.append(thread)

    # Watchdog Thread: Monitors the health of all plugin threads.
    watchdog_thread = threading.Thread(
        target=monitor_plugins_thread,
        args=(app_state,), name=WATCHDOG_THREAD_NAME, daemon=True
    )
    threads.append(watchdog_thread)
    
    # Thread Health Monitor: Periodically checks if all threads are running and restarts dead ones.
    health_monitor_thread = threading.Thread(
        target=thread_health_monitor,
        args=(app_state,), name="ThreadHealthMonitor", daemon=True
    )
    threads.append(health_monitor_thread)
    
    # --- 6. Start Services and Threads ---
    db_service.start()
    mqtt_service.start()
    web_service.start()
    curses_service.start()
    
    for t in threads:
        t.start()

    logger.info("All core threads started. Main loop is running.")

    try:
        logger.info("Main monitoring loop started. Press Ctrl+C to stop.")
        app_state.main_threads_stop_event.wait()
    except KeyboardInterrupt:
        logger.warning("=== SHUTDOWN INITIATED ===")
        logger.info("Ctrl+C detected, initiating graceful shutdown...")
        print("\n=== SHUTDOWN INITIATED ===")  # Also print to console
        print("Stopping Solar Monitoring System...")
        app_state.running = False
        app_state.main_threads_stop_event.set()
    finally:
        logger.warning("=== SHUTDOWN IN PROGRESS ===")
        logger.info("Main loop finished. Shutting down all components...")
        
        # Stop plugin threads first
        logger.info("Stopping plugin threads...")
        for plugin_name, event in app_state.plugin_stop_events.items():
            logger.info(f"Stopping plugin thread: {plugin_name}")
            event.set()
        
        # Stop services
        logger.info("Stopping all services...")
        logger.info("Stopping curses service...")
        curses_service.stop()
        
        logger.info("Stopping MQTT service...")
        mqtt_service.stop()
        
        logger.info("Stopping database service...")
        db_service.stop()
        
        logger.info("Stopping web service...")
        web_service.stop()
        
        # Wait for threads to finish
        logger.info("Waiting for threads to finish...")
        for i, t in enumerate(threads):
            if t.is_alive():
                logger.info(f"Waiting for thread {i+1}/{len(threads)}: {t.name}")
                t.join(timeout=2.0)
                if t.is_alive():
                    logger.warning(f"Thread {t.name} did not stop gracefully")
                else:
                    logger.info(f"Thread {t.name} stopped successfully")

        cleanup_lock_file()
        logger.warning("=== SHUTDOWN COMPLETE ===")
        logger.info(f"--- Solar Monitoring v{__version__} Finished ---")
        print("=== Solar Monitoring System Stopped ===")  # Final console message
