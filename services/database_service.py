# services/database_service.py
import sqlite3
import logging
import threading
import queue
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from core.app_state import AppState
from plugins.plugin_interface import StandardDataKeys, DevicePlugin

logger = logging.getLogger(__name__)

class DatabaseService:
    """
    Manages SQLite database operations for the Solar Monitoring application.
    
    This service handles:
    - Database initialization and schema creation
    - Periodic storage of power history data
    - Daily energy summary calculations and storage
    - Historical data retrieval for web dashboard
    - Data pruning to maintain database size
    - Backfilling of yesterday's summary data from plugins
    
    The service runs in its own thread and automatically stores data at configured intervals.
    """
    
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.db_file = self.app_state.config.get('DATABASE', 'DB_FILE', fallback="solis_history.db")
        self.history_max_hours = self.app_state.config.getint('DATABASE', 'HISTORY_MAX_AGE_HOURS', fallback=168)
        self.conn_params = {"timeout": 30, "check_same_thread": False}
        self._thread = None
        self._init_db()

    def start(self):
        """
        Starts the database service thread.
        
        Creates and starts a daemon thread that will periodically store power data
        and update daily summaries based on the configured intervals.
        """
        self._thread = threading.Thread(target=self._run, name="DatabaseService", daemon=True)
        self._thread.start()

    def _init_db(self):
        """
        Initializes the SQLite database with required tables and settings.
        
        Creates the power_history and daily_summary tables if they don't exist,
        enables WAL mode for better concurrent access, and performs initial
        data pruning to remove old records.
        
        Raises:
            Exception: If database initialization fails critically.
        """
        logger.info(f"Initializing database at {self.db_file}")
        try:
            with self.app_state.db_lock, sqlite3.connect(self.db_file, **self.conn_params) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS power_history (
                                    timestamp INTEGER PRIMARY KEY, soc REAL, production REAL,
                                    battery REAL, load REAL, grid REAL )''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS daily_summary (
                                    date TEXT PRIMARY KEY, pv_yield_kwh REAL, 
                                    battery_charge_kwh REAL, battery_discharge_kwh REAL,
                                    grid_import_kwh REAL, grid_export_kwh REAL,
                                    load_energy_kwh REAL)''')
                conn.commit()
            self.prune_old_data()
        except Exception as e:
            logger.critical(f"Database initialization failed: {e}", exc_info=True)
            raise

    def prune_old_data(self):
        """
        Removes old power history records beyond the configured retention period.
        
        Deletes records from the power_history table that are older than
        HISTORY_MAX_AGE_HOURS. Daily summary records are kept indefinitely.
        """
        cutoff_ms = int((datetime.now(timezone.utc) - timedelta(hours=self.history_max_hours)).timestamp() * 1000)
        try:
            with self.app_state.db_lock, sqlite3.connect(self.db_file, **self.conn_params) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM power_history WHERE timestamp < ?", (cutoff_ms,))
                deleted_count = cursor.rowcount
                if deleted_count > 0: logger.info(f"Pruned {deleted_count} old power history records.")
        except Exception as e:
            logger.error(f"Error pruning database: {e}")

    def _run(self):
        """Main loop that periodically stores the latest processed data."""
        interval = self.app_state.config.getint('DATABASE', 'POWER_HISTORY_INTERVAL_SECONDS', fallback=60)
        logger.info(f"Database service started. Will store data every {interval} seconds.")

        while self.app_state.running:
            try:
                self.app_state.main_threads_stop_event.wait(interval)
                if not self.app_state.running:
                    break
                
                with self.app_state.data_lock:
                    data_packet = self.app_state.shared_data.copy()

                if not data_packet:
                    logger.debug("Database service: No data in shared state yet, skipping storage cycle.")
                    continue

                self._store_power_data(data_packet)
                self._update_daily_summary(data_packet)

            except Exception as e:
                logger.error(f"Database service loop error: {e}", exc_info=True)
                time.sleep(interval)

    def _store_power_data(self, data: dict):
        """
        Stores a single power data point to the power_history table.
        
        Extracts key power metrics from the processed data and stores them
        with a timestamp. Validates the timestamp before writing to prevent
        database corruption from invalid data.
        
        Args:
            data: Dictionary containing wrapped power data with 'value' keys
        """
        raw_power_data = {
            'soc': data.get(StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT, {}).get("value"),
            'production': data.get(StandardDataKeys.PV_TOTAL_DC_POWER_WATTS, {}).get("value"),
            'battery': data.get(StandardDataKeys.BATTERY_POWER_WATTS, {}).get("value"),
            'load': data.get(StandardDataKeys.LOAD_TOTAL_POWER_WATTS, {}).get("value"),
            'grid': data.get(StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS, {}).get("value"),
        }
        
        power_data = {
            key: value if isinstance(value, (int, float)) else None
            for key, value in raw_power_data.items()
        }
        
        timestamp_ms = data.get(StandardDataKeys.SERVER_TIMESTAMP_MS_UTC, {}).get("value")
        
        if not isinstance(timestamp_ms, int):
            logger.error(f"CRITICAL: Aborting database write. Invalid or missing timestamp received. Value: '{timestamp_ms}', Type: {type(timestamp_ms).__name__}")
            return
            
        try:
            with self.app_state.db_lock, sqlite3.connect(self.db_file, **self.conn_params) as conn:
                conn.execute("INSERT OR REPLACE INTO power_history (timestamp, soc, production, battery, load, grid) VALUES (?,?,?,?,?,?)",
                               (timestamp_ms, power_data['soc'], power_data['production'], power_data['battery'], power_data['load'], power_data['grid']))
            logger.debug("Stored power data point to database.")
        except Exception as e:
            logger.error(f"Failed to store power data: {e}")

    def backfill_yesterday_summary(self):
        """
        Attempts to backfill yesterday's energy summary from connected plugins.
        
        This method is called on application startup to fill in missing daily
        summary data for yesterday. It queries connected plugins that support
        the read_yesterday_energy_summary() method to get historical energy totals.
        
        This is particularly useful when the application was offline yesterday
        but the inverter/BMS devices stored the energy totals internally.
        """
        try:
            yesterday = datetime.now(self.app_state.local_tzinfo) - timedelta(days=1)
            yesterday_str = yesterday.strftime('%Y-%m-%d')
            with self.app_state.db_lock, sqlite3.connect(self.db_file, **self.conn_params) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM daily_summary WHERE date = ?", (yesterday_str,))
                if cursor.fetchone():
                    logger.info(f"Summary for yesterday ({yesterday_str}) already exists. No backfill needed.")
                    return
            logger.info(f"No summary found for {yesterday_str}. Checking connected plugins for backfill data.")
            for name, plugin in self.app_state.active_plugin_instances.items():
                if plugin.is_connected and hasattr(plugin, 'read_yesterday_energy_summary'):
                    logger.info(f"Querying connected plugin '{name}' for yesterday's summary...")
                    summary_data = plugin.read_yesterday_energy_summary()
                    if summary_data and isinstance(summary_data, dict):
                        logger.info(f"Plugin '{name}' provided yesterday's summary data. Storing it.")
                        self._store_daily_summary(yesterday_str, summary_data)
                        return 
                    else:
                        logger.info(f"Plugin '{name}' did not return valid summary data.")
                else:
                    logger.debug(f"Skipping plugin '{name}' for backfill (not connected or does not support feature).")
        except Exception as e:
            logger.error(f"Error during yesterday's summary backfill: {e}", exc_info=True)

    def _update_daily_summary(self, data: dict):
        """
        Updates today's daily energy summary with current data.
        
        Extracts daily energy totals from the current data packet and
        stores/updates the daily_summary table for today's date.
        
        Args:
            data: Dictionary containing wrapped energy data with 'value' keys
        """
        today_str = datetime.now(self.app_state.local_tzinfo).strftime('%Y-%m-%d')
        summary_for_today = {
            StandardDataKeys.ENERGY_PV_DAILY_KWH: data.get(StandardDataKeys.ENERGY_PV_DAILY_KWH, {}).get("value"),
            StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: data.get(StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH, {}).get("value"),
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: data.get(StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH, {}).get("value"),
            StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: data.get(StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH, {}).get("value"),
            StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH: data.get(StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH, {}).get("value"),
            StandardDataKeys.ENERGY_LOAD_DAILY_KWH: data.get(StandardDataKeys.ENERGY_LOAD_DAILY_KWH, {}).get("value"),
        }
        self._store_daily_summary(today_str, summary_for_today)
    
    def _store_daily_summary(self, date_str: str, summary: Dict[str, Any]):
        """
        Helper method to store a daily summary for a specific date.
        It now intelligently calculates load energy if it's not provided.
        """
        # Step 1: Extract and validate all component values
        pv_yield = summary.get(StandardDataKeys.ENERGY_PV_DAILY_KWH, 0.0)
        batt_charge = summary.get(StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH, 0.0)
        batt_discharge = summary.get(StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH, 0.0)
        grid_import = summary.get(StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH, 0.0)
        grid_export = summary.get(StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH, 0.0)
        load_energy = summary.get(StandardDataKeys.ENERGY_LOAD_DAILY_KWH, 0.0)

        # Convert any non-numeric types to 0.0 for safety
        pv_yield = pv_yield if isinstance(pv_yield, (int, float)) else 0.0
        batt_charge = batt_charge if isinstance(batt_charge, (int, float)) else 0.0
        batt_discharge = batt_discharge if isinstance(batt_discharge, (int, float)) else 0.0
        grid_import = grid_import if isinstance(grid_import, (int, float)) else 0.0
        grid_export = grid_export if isinstance(grid_export, (int, float)) else 0.0
        load_energy = load_energy if isinstance(load_energy, (int, float)) else 0.0

        # Step 2: If load_energy is zero or not provided, calculate it as a fallback.
        if load_energy <= 0.0:
            calculated_load = (pv_yield + batt_discharge + grid_import) - (batt_charge + grid_export)
            load_energy = max(0, calculated_load)

        # Step 3: Prepare final tuple for DB, now with a reliable load_energy value
        final_values = (
            pv_yield,
            batt_charge,
            batt_discharge,
            grid_import,
            grid_export,
            load_energy
        )

        # Step 4: Do not write if all energy flows are zero.
        if all(value < 0.01 for value in final_values):
            logger.debug(f"Skipping summary store for date {date_str} as all energy values are zero.")
            return

        try:
            with self.app_state.db_lock, sqlite3.connect(self.db_file, **self.conn_params) as conn:
                conn.execute("""
                    INSERT INTO daily_summary (date, pv_yield_kwh, battery_charge_kwh, battery_discharge_kwh, grid_import_kwh, grid_export_kwh, load_energy_kwh) 
                    VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(date) DO UPDATE SET 
                        pv_yield_kwh=excluded.pv_yield_kwh,
                        battery_charge_kwh=excluded.battery_charge_kwh, 
                        battery_discharge_kwh=excluded.battery_discharge_kwh,
                        grid_import_kwh=excluded.grid_import_kwh, 
                        grid_export_kwh=excluded.grid_export_kwh, 
                        load_energy_kwh=excluded.load_energy_kwh
                """, (date_str, *final_values))
            logger.info(f"Successfully stored/updated daily summary for date: {date_str}")
        except Exception as e:
            logger.error(f"Failed to store daily summary for date {date_str}: {e}")

    def fetch_history_data(self, days: int) -> Optional[Dict[str, Any]]:
        """
        Fetches power history data for the web dashboard using a rolling time window.
        
        Retrieves high-resolution power data points from the power_history table
        for the specified number of days, using a rolling window from the current time.
        
        Args:
            days: Number of days of history to retrieve (must be positive)
            
        Returns:
            Dictionary containing 'power' key with list of timestamped data points,
            or None if the query fails
        """
        if not isinstance(days, int) or days <= 0:
            logger.warning(f"DB History Fetch: Invalid days requested ({days}). Defaulting to 1.")
            days = 1
        
        now_utc = datetime.now(timezone.utc)
        start_datetime_utc = now_utc - timedelta(days=days)
        cutoff_ms = int(start_datetime_utc.timestamp() * 1000)
        
        logger.debug(f"DB History Fetch: Querying rolling {days}-day window since UTC timestamp {cutoff_ms}.")
        try:
            with self.app_state.db_lock, sqlite3.connect(self.db_file, **self.conn_params) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT timestamp, soc, production, battery, load, grid FROM power_history WHERE timestamp >= ? ORDER BY timestamp ASC", (cutoff_ms,))
                
                db_to_sdk_map = {
                    'soc': StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT,
                    'production': StandardDataKeys.PV_TOTAL_DC_POWER_WATTS,
                    'battery': StandardDataKeys.BATTERY_POWER_WATTS,
                    'load': StandardDataKeys.LOAD_TOTAL_POWER_WATTS,
                    'grid': StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS,
                }

                transformed_history = []
                for row in cursor.fetchall():
                    transformed_row = {'timestamp': row['timestamp']}
                    for db_key, sdk_key in db_to_sdk_map.items():
                        transformed_row[sdk_key] = row[db_key]
                    transformed_history.append(transformed_row)
            
            return {'power': transformed_history}
        except Exception as e:
            logger.error(f"DB History Fetch: Error fetching history: {e}", exc_info=True)
            return None

    def fetch_daily_summary(self, params: Optional[Dict]) -> Dict[str, Any]:
        """
        Fetches aggregated daily, monthly, or yearly energy summary data.
        
        Supports multiple query types:
        - 'daily': Returns daily summaries for a specified number of days
        - 'current_month_daily': Returns daily summaries for the current month
        - 'yearly_by_month': Returns monthly aggregates for a specific year
        - 'yearly_summary': Returns yearly aggregates across all years
        
        Args:
            params: Dictionary containing query parameters like 'type' and 'value'
            
        Returns:
            Dictionary containing the requested summary data and metadata
        """
        req_type = params.get("type", "daily") if isinstance(params, dict) else "daily"
        logger.info(f"DB Summary Fetch: type={req_type}, params={params}")
        resp: Dict[str, Any] = {"request_type": req_type, "params_received": params or {}}
        
        sum_fields = ["pv_yield_kwh", "battery_charge_kwh", "battery_discharge_kwh", "grid_import_kwh", "grid_export_kwh", "load_energy_kwh"]
        
        try:
            with self.app_state.db_lock, sqlite3.connect(self.db_file, **self.conn_params) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()

                if req_type == 'daily' or req_type == 'current_month_daily':
                    if req_type == 'daily':
                        days = params.get('value', 7)
                        end_date = datetime.now(self.app_state.local_tzinfo)
                        start_date = end_date - timedelta(days=days-1)
                    else:
                        today = datetime.now(self.app_state.local_tzinfo)
                        start_date = today.replace(day=1)
                        end_date = today
                    
                    c.execute(f"SELECT * FROM daily_summary WHERE date >= ? AND date <= ? ORDER BY date ASC", 
                              (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                    resp['summaries'] = [dict(row) for row in c.fetchall()]

                elif req_type == 'yearly_by_month':
                    year = params.get('value', datetime.now().year)
                    c.execute(f"SELECT strftime('%Y-%m', date) as month, {', '.join([f'SUM({f}) as {f}' for f in sum_fields])} FROM daily_summary WHERE strftime('%Y', date) = ? GROUP BY month ORDER BY month ASC", (str(year),))
                    resp['monthly_summaries'] = [dict(row) for row in c.fetchall()]
                    resp['query_year'] = year
                
                elif req_type == 'yearly_summary':
                    c.execute(f"SELECT strftime('%Y', date) as year, {', '.join([f'SUM({f}) as {f}' for f in sum_fields])} FROM daily_summary GROUP BY year ORDER BY year ASC")
                    resp['yearly_summaries'] = [dict(row) for row in c.fetchall()]

                else:
                    resp['error'] = f"Unsupported summary type: {req_type}"
            
            return resp

        except Exception as e:
            logger.error(f"DB daily summary fetch error: {e}", exc_info=True)
            return {"error": str(e), "request_type": req_type}

    def fetch_hourly_summary(self, date_str: str) -> Optional[List[Dict[str, Any]]]:
        """
        Calculates hourly energy flow breakdown for a specific date.
        
        Processes power_history data to calculate energy flows for each hour,
        breaking down consumption sources (solar direct, battery discharge, grid import)
        and energy returns (battery charge, grid export). Uses power thresholding
        to filter out noise and phantom readings.
        
        Args:
            date_str: Date in 'YYYY-MM-DD' format
            
        Returns:
            List of 24 hourly summary dictionaries (one per hour 0-23),
            or None if calculation fails
        """
        logger.info(f"Calculating hourly summary for date: {date_str}")
        try:
            POWER_THRESHOLD_W = self.app_state.hourly_summary_power_threshold_w

            start_of_day_local = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=self.app_state.local_tzinfo)
            end_of_day_local = start_of_day_local + timedelta(days=1)
            start_utc_ms = int(start_of_day_local.astimezone(timezone.utc).timestamp() * 1000)
            end_utc_ms = int(end_of_day_local.astimezone(timezone.utc).timestamp() * 1000)

            with self.app_state.db_lock, sqlite3.connect(self.db_file, **self.conn_params) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT timestamp, production, battery, grid FROM power_history WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC",
                    (start_utc_ms, end_utc_ms)
                )
                power_data = cursor.fetchall()
            
            if not power_data or len(power_data) < 2:
                logger.warning(f"Not enough data in power_history for {date_str} to calculate hourly summary.")
                return []

            hourly_summary = {i: {"hour": i, "battery_charge_kwh": 0.0, "battery_discharge_kwh": 0.0, "grid_import_kwh": 0.0, "grid_export_kwh": 0.0, "solar_to_load_kwh": 0.0} for i in range(24)}

            for i in range(1, len(power_data)):
                prev = power_data[i-1]
                curr = power_data[i]
                dt_seconds = (curr['timestamp'] - prev['timestamp']) / 1000.0
                if dt_seconds <= 0: continue
                dt_hours = dt_seconds / 3600.0
                interval_hour = datetime.fromtimestamp(prev['timestamp'] / 1000, self.app_state.local_tzinfo).hour

                # Calculate average power in kW for the interval
                avg_prod_kw = ((prev['production'] or 0) + (curr['production'] or 0)) / 2 / 1000.0
                avg_batt_kw = ((prev['battery'] or 0) + (curr['battery'] or 0)) / 2 / 1000.0
                avg_grid_kw = ((prev['grid'] or 0) + (curr['grid'] or 0)) / 2 / 1000.0

                # --- Corrected logic with thresholding ---
                threshold_kw = POWER_THRESHOLD_W / 1000.0

                # Battery: >0 is discharge, <0 is charge
                if avg_batt_kw > threshold_kw:
                    hourly_summary[interval_hour]['battery_discharge_kwh'] += avg_batt_kw * dt_hours
                elif avg_batt_kw < -threshold_kw:
                    hourly_summary[interval_hour]['battery_charge_kwh'] += abs(avg_batt_kw) * dt_hours
                
                # Grid: >0 is export, <0 is import (Corrected based on observed inverter behavior)
                if avg_grid_kw > threshold_kw: # Positive value is export
                    hourly_summary[interval_hour]['grid_export_kwh'] += avg_grid_kw * dt_hours
                elif avg_grid_kw < -threshold_kw: # Negative value is import
                    hourly_summary[interval_hour]['grid_import_kwh'] += abs(avg_grid_kw) * dt_hours
                
                # Solar used directly by load is what's left over from production
                # after charging the battery and exporting to the grid.
                solar_to_battery_kw = max(0, -avg_batt_kw)
                solar_to_grid_kw = max(0, avg_grid_kw)
                solar_to_load_kw = max(0, avg_prod_kw - solar_to_battery_kw - solar_to_grid_kw)
                hourly_summary[interval_hour]['solar_to_load_kwh'] += solar_to_load_kw * dt_hours
            
            return [v for k, v in sorted(hourly_summary.items())]

        except Exception as e:
            logger.error(f"Error calculating hourly summary for {date_str}: {e}", exc_info=True)
            return None