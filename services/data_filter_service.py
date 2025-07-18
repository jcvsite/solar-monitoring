# services/data_filter_service.py
import logging
import time
from typing import Dict, Any, Optional, Tuple, Set
import math
from dataclasses import dataclass
from collections import defaultdict

from core.app_state import AppState
from plugins.plugin_interface import StandardDataKeys

logger = logging.getLogger(__name__)

@dataclass
class FilterConfig:
    """Configuration parameters for the data filter service."""
    spike_factor: float = 1.5
    spike_confirmation_threshold: int = 3
    soc_change_buffer: float = 1.5
    soc_max_overage: float = 105.0
    energy_safety_margin: float = 3.0
    energy_headroom_kwh: float = 0.1
    strict_spike_multiplier: float = 10.0
    absurd_spike_multiplier: float = 100.0
    max_elapsed_hours: float = 1.0
    min_elapsed_seconds: float = 1.0
    reset_time_start: int = 23
    reset_time_end: int = 2
    reset_threshold_ratio: float = 0.1
    reset_min_last_value: float = 5.0
    reset_max_new_value: float = 2.0
    max_spike_history_size: int = 100
    # Intelligent decrease correction parameters
    decrease_correction_enabled: bool = True
    decrease_correction_time_minutes: float = 10.0  # How long to wait before accepting persistent decrease
    decrease_correction_min_samples: int = 5  # Minimum number of samples needed
    decrease_correction_max_ratio: float = 0.8  # New value must be < 80% of current to trigger correction logic

class DataFilterService:
    """
    A service responsible for cleaning up raw data from plugins.

    This service applies various filtering techniques to the data stream to
    remove anomalies and unrealistic spikes before the data is used by other
    parts of the application (like the database or web UI). It primarily handles:
    - Spike detection for instantaneous power values.
    - Adaptive spike and anomaly detection for cumulative energy values, which
      can learn a new baseline if a "spike" is reported consistently.
    """
    def __init__(self, app_state: AppState, config: Optional[FilterConfig] = None):
        """
        Initializes the DataFilterService.

        Args:
            app_state (AppState): The central application state object, used to
                                  access system configuration for filter limits.
            config (FilterConfig): Optional configuration parameters for filtering behavior.
        """
        self.app_state = app_state
        self.config = config or FilterConfig()
        
        # State for adaptive energy spike filtering
        self.potential_spikes: Dict[str, Tuple[Any, int]] = {}
        # Time-based filtering state
        self.last_energy_timestamps: Dict[str, float] = {}
        # Intelligent decrease correction tracking
        # Format: {key: {'value': float, 'first_seen': timestamp, 'count': int, 'last_seen': timestamp}}
        self.potential_decreases: Dict[str, Dict[str, Any]] = {}
        
        # Cache for frequently accessed values
        self._daily_limits_cache: Optional[Dict[str, Optional[float]]] = None
        self._power_limits_cache: Optional[Dict[str, Optional[float]]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 300  # 5 minutes
        
        # Define key categories for better organization
        self.power_keys: Set[str] = {
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS,
            StandardDataKeys.AC_POWER_WATTS,
            StandardDataKeys.BATTERY_POWER_WATTS,
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS,
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS
        }
        
        self.energy_keys: Set[str] = {
            StandardDataKeys.ENERGY_PV_DAILY_KWH,
            StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH,
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH,
            StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH,
            StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH,
            StandardDataKeys.ENERGY_LOAD_DAILY_KWH
        }

    def _refresh_cache_if_needed(self) -> None:
        """Refresh cached limits if they're stale."""
        current_time = time.time()
        if current_time - self._cache_timestamp > self._cache_ttl:
            self._daily_limits_cache = None
            self._power_limits_cache = None
            self._cache_timestamp = current_time

    def _get_daily_limits(self) -> Dict[str, Optional[float]]:
        """Get cached daily limits, refreshing if necessary."""
        self._refresh_cache_if_needed()
        if self._daily_limits_cache is None:
            self._daily_limits_cache = {
                StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: self.app_state.daily_limit_grid_import_kwh,
                StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH: self.app_state.daily_limit_grid_export_kwh,
                StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: self.app_state.daily_limit_battery_charge_kwh,
                StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: self.app_state.daily_limit_battery_discharge_kwh,
                StandardDataKeys.ENERGY_PV_DAILY_KWH: self.app_state.daily_limit_pv_generation_kwh,
                StandardDataKeys.ENERGY_LOAD_DAILY_KWH: self.app_state.daily_limit_load_consumption_kwh
            }
        return self._daily_limits_cache

    def _get_daily_limit(self, key: str) -> Optional[float]:
        """
        Returns the configured absolute daily energy limit for a given energy data key.
        
        These limits are configurable in config.ini under the [FILTER] section and help
        prevent sensor errors, unit conversion issues, and accumulated values from 
        corrupting the system.
        
        Args:
            key: The energy data key (e.g., StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH)
            
        Returns:
            The daily limit in kWh, or None if no limit is configured for this key
        """
        return self._get_daily_limits().get(key)

    def _get_power_limits(self) -> Dict[str, Optional[float]]:
        """Get cached power limits, refreshing if necessary."""
        self._refresh_cache_if_needed()
        if self._power_limits_cache is None:
            self._power_limits_cache = {
                StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: self.app_state.pv_installed_capacity_w * self.config.spike_factor,
                StandardDataKeys.AC_POWER_WATTS: self.app_state.inverter_max_ac_power_w * self.config.spike_factor,
                StandardDataKeys.BATTERY_POWER_WATTS: max(
                    self.app_state.battery_max_charge_power_w, 
                    self.app_state.battery_max_discharge_power_w
                ) * self.config.spike_factor
            }
        return self._power_limits_cache

    def _get_limit(self, key: str) -> Optional[float]:
        """
        Calculates and returns a configured upper limit for a given power data key.
        The limit is based on the system's configured maximums (e.g., PV capacity,
        inverter AC power) multiplied by a spike factor to allow for some headroom.
        """
        limit = self._get_power_limits().get(key)
        return limit if limit and limit > 0 else None

    def _filter_power_value(self, key: str, value: Any, last_known_value: Optional[float]) -> Any:
        """
        Filters a single power value to reject unrealistic spikes.

        If the value exceeds a dynamically calculated limit, it's considered a
        spike, and the last known good value is returned instead. Non-numeric
        values are also rejected.
        """
        if not isinstance(value, (int, float)):
            return last_known_value

        limit = self._get_limit(key)
        if limit and abs(value) > limit:
            logger.warning(f"FILTER: Power spike detected for '{key}'. Value {value} > limit {limit}. Using last valid value: {last_known_value}")
            return last_known_value

        return value

    def _filter_soc_value(self, value: Any, last_known_value: Optional[float]) -> Any:
        """
        Filters the battery State of Charge (SOC) to prevent unrealistic jumps.

        This logic allows for normal charging/discharging changes but rejects any
        sudden, large jumps or drops that are physically impossible within a single
        poll interval.

        Returns:
            The filtered SOC value.
        """
        if not isinstance(value, (int, float)) or not (0 <= value <= self.config.soc_max_overage):
            return last_known_value

        if last_known_value is None:
            return value

        # Calculate max possible SOC change in one poll interval
        max_charge_w = self.app_state.battery_max_charge_power_w
        capacity_wh = self.app_state.battery_usable_capacity_kwh * 1000
        poll_interval_h = self.app_state.poll_interval / 3600

        if capacity_wh > 0 and max_charge_w > 0:
            # Max energy change in Wh in one interval
            max_energy_change_wh = max_charge_w * poll_interval_h
            # Max SOC change in percent
            max_soc_change_percent = (max_energy_change_wh / capacity_wh) * 100
            
            # Add a small buffer to the threshold
            soc_change_threshold = max_soc_change_percent * self.config.soc_change_buffer + 1.0

            if abs(value - last_known_value) > soc_change_threshold:
                logger.warning(f"FILTER: SOC jump detected. New: {value:.1f}%, Last: {last_known_value:.1f}%. Change exceeds threshold of {soc_change_threshold:.1f}%. Holding last value.")
                return last_known_value
        
        return value

    def _cleanup_spike_history(self) -> None:
        """Clean up old spike history to prevent memory leaks."""
        if len(self.potential_spikes) > self.config.max_spike_history_size:
            # Remove oldest entries (simple FIFO approach)
            keys_to_remove = list(self.potential_spikes.keys())[:-self.config.max_spike_history_size//2]
            for key in keys_to_remove:
                self.potential_spikes.pop(key, None)
            logger.debug(f"FILTER: Cleaned up {len(keys_to_remove)} old spike history entries")

    def _cleanup_decrease_history(self) -> None:
        """Clean up old decrease correction history to prevent memory leaks."""
        current_time = time.time()
        keys_to_remove = []
        
        for key, decrease_info in self.potential_decreases.items():
            # Remove entries older than 2x the correction time window
            max_age = self.config.decrease_correction_time_minutes * 120  # 2x in seconds
            if current_time - decrease_info['first_seen'] > max_age:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self.potential_decreases.pop(key, None)
        
        if keys_to_remove:
            logger.debug(f"FILTER: Cleaned up {len(keys_to_remove)} old decrease correction entries")

    def _handle_intelligent_decrease_correction(self, key: str, value: float, last_known_value: float) -> Optional[float]:
        """
        Handle intelligent decrease correction for persistent lower values.
        
        This addresses the rare case where a bad spike value gets through the filter,
        and then the sensor corrects itself to report the actual correct (lower) value.
        If the same lower value persists for a configurable time period, we accept it
        as a correction rather than a sensor glitch.
        
        Args:
            key: The energy data key
            value: The new (lower) value being reported
            last_known_value: The current held value (potentially incorrect spike)
            
        Returns:
            The corrected value if decrease is confirmed, None if still pending
        """
        if not self.config.decrease_correction_enabled:
            return None
            
        current_time = time.time()
        
        # Check if this decrease is significant enough to trigger correction logic
        if value >= (last_known_value * self.config.decrease_correction_max_ratio):
            # Decrease is not significant enough, clear any pending state
            self.potential_decreases.pop(key, None)
            return None
        
        # Track this potential decrease
        if key not in self.potential_decreases:
            # First time seeing this decrease
            self.potential_decreases[key] = {
                'value': value,
                'first_seen': current_time,
                'last_seen': current_time,
                'count': 1
            }
            logger.info(f"FILTER: '{key}' - DECREASE CORRECTION: Started tracking potential correction. "
                       f"New value: {value:.2f} kWh, Current held: {last_known_value:.2f} kWh. "
                       f"Will monitor for {self.config.decrease_correction_time_minutes:.1f} minutes.")
            return None
        else:
            decrease_info = self.potential_decreases[key]
            
            # Check if the value is consistent with what we're tracking
            if math.isclose(value, decrease_info['value'], rel_tol=0.05):  # 5% tolerance
                # Same value, update tracking
                decrease_info['last_seen'] = current_time
                decrease_info['count'] += 1
                
                elapsed_minutes = (current_time - decrease_info['first_seen']) / 60
                
                # Check if we've met the criteria for accepting the decrease
                time_criteria_met = elapsed_minutes >= self.config.decrease_correction_time_minutes
                sample_criteria_met = decrease_info['count'] >= self.config.decrease_correction_min_samples
                
                if time_criteria_met and sample_criteria_met:
                    # Accept the decrease as a correction
                    logger.warning(f"FILTER: '{key}' - DECREASE CORRECTION CONFIRMED: Accepting persistent lower value. "
                                 f"Corrected value: {value:.2f} kWh (was holding: {last_known_value:.2f} kWh). "
                                 f"Monitored for {elapsed_minutes:.1f} minutes with {decrease_info['count']} consistent samples. "
                                 f"This suggests the previous higher value was incorrect.")
                    
                    # Clear the tracking state
                    self.potential_decreases.pop(key, None)
                    return value
                else:
                    # Still pending, log progress
                    logger.info(f"FILTER: '{key}' - DECREASE CORRECTION: Monitoring progress. "
                               f"Value: {value:.2f} kWh, Elapsed: {elapsed_minutes:.1f}/{self.config.decrease_correction_time_minutes:.1f} min, "
                               f"Samples: {decrease_info['count']}/{self.config.decrease_correction_min_samples}")
                    return None
            else:
                # Different value, reset tracking
                logger.info(f"FILTER: '{key}' - DECREASE CORRECTION: Value changed from {decrease_info['value']:.2f} to {value:.2f} kWh. "
                           f"Resetting correction tracking.")
                self.potential_decreases[key] = {
                    'value': value,
                    'first_seen': current_time,
                    'last_seen': current_time,
                    'count': 1
                }
                return None

    def _is_daily_reset_time(self) -> bool:
        """Check if current time is within daily reset window."""
        current_hour = time.localtime().tm_hour
        return current_hour >= self.config.reset_time_start or current_hour <= self.config.reset_time_end

    def _is_valid_daily_reset(self, value: float, last_known_value: float) -> bool:
        """Check if a value decrease represents a valid daily reset."""
        return (
            self._is_daily_reset_time() and
            value < (last_known_value * self.config.reset_threshold_ratio) and 
            last_known_value > self.config.reset_min_last_value and 
            value < self.config.reset_max_new_value
        )

    def _calculate_elapsed_time(self, key: str) -> float:
        """Calculate elapsed time since last measurement, with bounds checking."""
        current_time = time.time()
        last_timestamp = self.last_energy_timestamps.get(key)
        
        if last_timestamp is None:
            elapsed_hours = self.app_state.poll_interval / 3600
            logger.debug(f"FILTER: '{key}' - First timestamp, using poll interval fallback: {elapsed_hours:.4f}h")
        else:
            elapsed_seconds = current_time - last_timestamp
            elapsed_hours = elapsed_seconds / 3600
            
            # Apply bounds checking
            if elapsed_seconds < self.config.min_elapsed_seconds:
                elapsed_hours = self.app_state.poll_interval / 3600
                logger.debug(f"FILTER: '{key}' - Elapsed time too small ({elapsed_seconds:.1f}s), using poll interval")
            elif elapsed_hours > self.config.max_elapsed_hours:
                elapsed_hours = self.config.max_elapsed_hours
                logger.debug(f"FILTER: '{key}' - Elapsed time capped at {self.config.max_elapsed_hours}h (was {elapsed_seconds/3600:.2f}h)")
            else:
                logger.debug(f"FILTER: '{key}' - Using actual elapsed time: {elapsed_seconds:.1f}s ({elapsed_hours:.4f}h)")
        
        # Update timestamp for next calculation
        self.last_energy_timestamps[key] = current_time
        return elapsed_hours

    def _get_max_power_for_energy_key(self, key: str) -> float:
        """Get the appropriate maximum power limit for a given energy key."""
        if key == StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH:
            return self.app_state.battery_max_charge_power_w
        elif key == StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH:
            return self.app_state.battery_max_discharge_power_w
        elif key == StandardDataKeys.ENERGY_PV_DAILY_KWH:
            return self.app_state.pv_installed_capacity_w
        elif key in [StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH, StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH]:
            return self.app_state.inverter_max_ac_power_w
        elif key == StandardDataKeys.ENERGY_LOAD_DAILY_KWH:
            return self.app_state.inverter_max_ac_power_w * 1.5
        else:
            return self.app_state.inverter_max_ac_power_w or 0

    def _handle_energy_spike_detection(self, key: str, value: float, last_known_value: float, max_increase_kwh: float) -> float:
        """Handle adaptive spike detection for energy values."""
        # Check for immediate rejection thresholds
        strict_spike_threshold = max_increase_kwh * self.config.strict_spike_multiplier
        if value > (last_known_value + strict_spike_threshold):
            logger.warning(f"FILTER: '{key}' - Large energy spike rejected outright. "
                         f"Value: {value:.2f} kWh, Last: {last_known_value:.2f} kWh, "
                         f"Increase: {(value - last_known_value):.2f} kWh > {strict_spike_threshold:.2f} kWh threshold.")
            return last_known_value

        absurd_spike_threshold = max_increase_kwh * self.config.absurd_spike_multiplier
        if value > (last_known_value + absurd_spike_threshold):
            logger.warning(f"FILTER: '{key}' - Absurd spike rejected outright. "
                         f"Value: {value:.2f}, Last: {last_known_value:.2f}, "
                         f"Threshold: >{absurd_spike_threshold:.2f} kWh above last")
            return last_known_value

        # Handle adaptive spike confirmation
        logger.warning(f"FILTER: '{key}' - Initial spike detected. Value: {value:.2f} kWh, "
                      f"Last: {last_known_value:.2f} kWh, Max Increase: {max_increase_kwh:.3f} kWh")
        
        potential_value, count = self.potential_spikes.get(key, (None, 0))

        if potential_value is not None and math.isclose(value, potential_value):
            count += 1
            logger.debug(f"FILTER: '{key}' - Potential spike repeated. "
                        f"Value: {value:.2f} kWh, Count: {count}/{self.config.spike_confirmation_threshold}")
        else:
            count = 1
            logger.debug(f"FILTER: '{key}' - New potential spike. Value: {value:.2f} kWh, Resetting counter.")
        
        self.potential_spikes[key] = (value, count)
        
        if count >= self.config.spike_confirmation_threshold:
            logger.info(f"FILTER: '{key}' - Spike CONFIRMED as new baseline. "
                       f"New value: {value:.2f} kWh (previously {last_known_value:.2f} kWh)")
            self.potential_spikes.pop(key, None)
            return value
        else:
            logger.warning(f"FILTER: '{key}' - Potential spike HOLDING. "
                          f"Value: {value:.2f} kWh (Last valid: {last_known_value:.2f} kWh), "
                          f"Count: {count}/{self.config.spike_confirmation_threshold}")
            return last_known_value

    def _filter_energy_value(self, key: str, value: Any, last_known_value: Optional[float]) -> Any:
        """
        Filters a cumulative energy value using an adaptive spike detection mechanism.

        This logic is designed for 'total_increasing' sensors. It handles:
        1. Rejection of invalid values (non-numeric, negative).
        2. Unit conversion error detection (e.g., Wh reported as kWh).
        3. Graceful handling of daily resets (large drops in value).
        4. Rejection of physically impossible decreases.
        5. Adaptive spike detection with absolute daily limits.
        6. Enhanced protection against 500+ kWh sensor errors.

        Returns:
            The filtered energy value.
        """
        # 1. Validate input value
        if not isinstance(value, (int, float)) or value < 0:
            return last_known_value
            
        # 2. Check absolute daily limits first
        daily_limit = self._get_daily_limit(key)
        if daily_limit and value > daily_limit:
            if last_known_value is None:
                logger.error(f"FILTER: '{key}' - CRITICAL: Initial value {value:.2f} kWh exceeds daily limit {daily_limit} kWh. Starting with 0.0 kWh.")
                return 0.0
            else:
                logger.warning(f"FILTER: '{key}' - Value {value:.2f} kWh exceeds daily limit {daily_limit} kWh. Preserving last value: {last_known_value:.2f} kWh")
                return last_known_value
        
        # 3. Accept initial value if no previous data
        if last_known_value is None:
            logger.info(f"FILTER: '{key}' - Accepting initial value: {value:.2f} kWh")
            return value

        # 4. Handle daily resets and intelligent decrease correction
        if value < last_known_value and not math.isclose(value, last_known_value):
            if self._is_valid_daily_reset(value, last_known_value):
                current_hour = time.localtime().tm_hour
                logger.info(f"FILTER: Detected daily reset for '{key}' at {current_hour:02d}:xx. "
                           f"New value {value:.2f} kWh << last value {last_known_value:.2f} kWh.")
                self.potential_spikes.pop(key, None)  # Clear spike state on reset
                self.potential_decreases.pop(key, None)  # Clear decrease correction state on reset
                return value
            else:
                # Check for intelligent decrease correction before rejecting
                corrected_value = self._handle_intelligent_decrease_correction(key, value, last_known_value)
                if corrected_value is not None:
                    # Decrease correction confirmed, accept the corrected value
                    self.potential_spikes.pop(key, None)  # Clear any spike state
                    return corrected_value
                else:
                    # Still pending or not applicable, reject the decrease for now
                    current_hour = time.localtime().tm_hour
                    reason = "during reset hours but criteria not met" if self._is_daily_reset_time() else f"outside reset hours ({current_hour:02d}:xx)"
                    logger.warning(f"FILTER: '{key}' - Invalid decrease detected {reason}. "
                                 f"New value: {value:.2f} kWh, Holding last value: {last_known_value:.2f} kWh")
                    return last_known_value

        # 5. Spike detection for increases
        if last_known_value > 0.01:  # Only check spikes after initial value
            elapsed_hours = self._calculate_elapsed_time(key)
            max_power_w = self._get_max_power_for_energy_key(key)
            
            if not max_power_w or max_power_w <= 0:
                max_power_w = self.app_state.inverter_max_ac_power_w
                logger.warning(f"FILTER: No specific power limit found for '{key}', using inverter max AC power: {max_power_w}W")

            # Calculate maximum allowed increase
            max_increase_kwh = (max_power_w / 1000) * elapsed_hours * self.config.energy_safety_margin + self.config.energy_headroom_kwh
            
            logger.debug(f"FILTER: '{key}' - Last: {last_known_value:.2f}, Current: {value:.2f}, "
                        f"Elapsed: {elapsed_hours*3600:.1f}s, Max Increase: {max_increase_kwh:.3f} kWh")

            if value > (last_known_value + max_increase_kwh):
                return self._handle_energy_spike_detection(key, value, last_known_value, max_increase_kwh)
            else:
                # No spike detected, clear any pending spike state
                if key in self.potential_spikes:
                    logger.info(f"FILTER: '{key}' - Potential spike cleared, accepting value of {value:.2f} kWh")
                    self.potential_spikes.pop(key, None)
        
        # Periodic cleanup of spike and decrease history
        if len(self.potential_spikes) > self.config.max_spike_history_size // 2:
            self._cleanup_spike_history()
        if len(self.potential_decreases) > self.config.max_spike_history_size // 4:
            self._cleanup_decrease_history()
        
        logger.debug(f"FILTER: '{key}' - Accepted value: {value:.2f} kWh (last: {last_known_value:.2f} kWh)")
        return value

    def apply_all_filters(self, current_data: Dict[str, Any], last_good_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies all relevant filters to a complete data packet.

        This is the main entry point for the filtering process. It iterates through
        the data, applying power or energy filters to the appropriate keys. For keys
        that are not filtered (e.g., status text), it passes the current value through.

        Returns:
            A new dictionary containing the fully filtered data.
        """
        if not current_data:
            return last_good_data or {}

        filtered_data = {}
        all_keys = set(current_data.keys()) | set(last_good_data.keys())

        # Process keys in batches for better performance
        for key in all_keys:
            current_value = current_data.get(key)
            last_value = last_good_data.get(key)
            
            try:
                if key in self.power_keys:
                    filtered_data[key] = self._filter_power_value(key, current_value, last_value)
                elif key in self.energy_keys:
                    # Special debug logging for grid import if needed
                    if key == StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH and logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"FILTER: Applying filter for GridImport. Current: {current_value}, Last: {last_value}")
                    filtered_data[key] = self._filter_energy_value(key, current_value, last_value)
                elif key == StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT:
                    filtered_data[key] = self._filter_soc_value(current_value, last_value)
                else:
                    # For non-filtered keys (like status text, alerts), prefer current value if it exists
                    filtered_data[key] = current_value if current_value is not None else last_value
            except Exception as e:
                logger.error(f"FILTER: Error processing key '{key}': {e}. Using last known value.")
                filtered_data[key] = last_value
        
        return filtered_data

    def get_filter_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current filter state.
        
        Returns:
            Dictionary containing filter statistics and state information.
        """
        return {
            'potential_spikes_count': len(self.potential_spikes),
            'potential_spikes': dict(self.potential_spikes),
            'potential_decreases_count': len(self.potential_decreases),
            'potential_decreases': dict(self.potential_decreases),
            'tracked_energy_keys': list(self.last_energy_timestamps.keys()),
            'cache_age_seconds': time.time() - self._cache_timestamp,
            'config': {
                'spike_factor': self.config.spike_factor,
                'spike_confirmation_threshold': self.config.spike_confirmation_threshold,
                'max_spike_history_size': self.config.max_spike_history_size,
                'decrease_correction_enabled': self.config.decrease_correction_enabled,
                'decrease_correction_time_minutes': self.config.decrease_correction_time_minutes,
                'decrease_correction_min_samples': self.config.decrease_correction_min_samples
            }
        }

    def reset_filter_state(self, keys: Optional[Set[str]] = None) -> None:
        """
        Reset filter state for specified keys or all keys.
        
        Args:
            keys: Set of keys to reset, or None to reset all
        """
        if keys is None:
            self.potential_spikes.clear()
            self.last_energy_timestamps.clear()
            self.potential_decreases.clear()
            logger.info("FILTER: Reset all filter state")
        else:
            for key in keys:
                self.potential_spikes.pop(key, None)
                self.last_energy_timestamps.pop(key, None)
                self.potential_decreases.pop(key, None)
            logger.info(f"FILTER: Reset filter state for keys: {keys}")

    def update_config(self, new_config: FilterConfig) -> None:
        """
        Update the filter configuration and clear caches.
        
        Args:
            new_config: New configuration to apply
        """
        self.config = new_config
        # Clear caches to force refresh with new config
        self._daily_limits_cache = None
        self._power_limits_cache = None
        self._cache_timestamp = 0
        logger.info("FILTER: Updated configuration and cleared caches")