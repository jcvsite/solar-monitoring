# services/data_filter_service.py
import logging
import time
from typing import Dict, Any, Optional, Tuple
import math

from core.app_state import AppState
from plugins.plugin_interface import StandardDataKeys

logger = logging.getLogger(__name__)

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
    def __init__(self, app_state: AppState):
        """
        Initializes the DataFilterService.

        Args:
            app_state (AppState): The central application state object, used to
                                  access system configuration for filter limits.
        """
        self.app_state = app_state
        self.spike_factor = 1.5
        # State for adaptive energy spike filtering
        self.potential_spikes: Dict[str, Tuple[Any, int]] = {}
        self.spike_confirmation_threshold = 3
        # Time-based filtering state
        self.last_energy_timestamps: Dict[str, float] = {}

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
        daily_limits = {
            StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: self.app_state.daily_limit_grid_import_kwh,
            StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH: self.app_state.daily_limit_grid_export_kwh,
            StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: self.app_state.daily_limit_battery_charge_kwh,
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: self.app_state.daily_limit_battery_discharge_kwh,
            StandardDataKeys.ENERGY_PV_DAILY_KWH: self.app_state.daily_limit_pv_generation_kwh,
            StandardDataKeys.ENERGY_LOAD_DAILY_KWH: self.app_state.daily_limit_load_consumption_kwh
        }
        return daily_limits.get(key)

    def _get_limit(self, key: str) -> Optional[float]:
        """
        Calculates and returns a configured upper limit for a given power data key.
        The limit is based on the system's configured maximums (e.g., PV capacity,
        inverter AC power) multiplied by a spike factor to allow for some headroom.
        """
        limits = {
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: self.app_state.pv_installed_capacity_w * self.spike_factor,
            StandardDataKeys.AC_POWER_WATTS: self.app_state.inverter_max_ac_power_w * self.spike_factor,
            StandardDataKeys.BATTERY_POWER_WATTS: max(self.app_state.battery_max_charge_power_w, self.app_state.battery_max_discharge_power_w) * self.spike_factor
        }
        limit = limits.get(key)
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
        if not isinstance(value, (int, float)) or not (0 <= value <= 105): # Allow slight overage
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
            soc_change_threshold = max_soc_change_percent * 1.5 + 1.0

            if abs(value - last_known_value) > soc_change_threshold:
                logger.warning(f"FILTER: SOC jump detected. New: {value:.1f}%, Last: {last_known_value:.1f}%. Change exceeds threshold of {soc_change_threshold:.1f}%. Holding last value.")
                return last_known_value
        
        return value

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
        # 1. If current value is invalid, immediately return the last known good one.
        if not isinstance(value, (int, float)) or value < 0:
            return last_known_value
            
        # 2. Check absolute daily limits FIRST - applies to ALL values (initial or ongoing)
        daily_limit = self._get_daily_limit(key)
        if daily_limit and value > daily_limit:
            if last_known_value is None:
                # For initial bad values, we have no choice but to start with 0.0
                logger.error(f"FILTER: '{key}' - CRITICAL: Initial value {value:.2f} kWh exceeds configured daily limit of {daily_limit} kWh. "
                           f"Starting with 0.0 kWh as safe baseline.")
                return 0.0
            else:
                # For ongoing bad values, preserve the last good data
                logger.warning(f"FILTER: '{key}' - Value {value:.2f} kWh exceeds configured daily limit of {daily_limit} kWh. "
                             f"This is likely a sensor error. Preserving last good value: {last_known_value:.2f} kWh")
                return last_known_value
        
        # 3. If there's no previous value, accept the current value (already passed daily limit check)
        if last_known_value is None:
            logger.info(f"FILTER: '{key}' - Accepting initial value: {value:.2f} kWh")
            return value

        # Determine the relevant power limit for spike calculation
        max_power_w = self.app_state.inverter_max_ac_power_w
        
        if key == StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH:
            max_power_w = self.app_state.battery_max_charge_power_w
        elif key == StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH:
            max_power_w = self.app_state.battery_max_discharge_power_w
        elif key == StandardDataKeys.ENERGY_PV_DAILY_KWH:
            # PV can sometimes exceed inverter AC rating, use its own capacity
            max_power_w = self.app_state.pv_installed_capacity_w
        elif key in [StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH, StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH]:
            # Grid import/export should be limited by inverter AC power capacity
            # Use a more conservative limit for grid energy to prevent 500+ kWh spikes
            max_power_w = self.app_state.inverter_max_ac_power_w
            logger.debug(f"FILTER: Using inverter AC power limit {max_power_w}W for grid energy key '{key}'")
        elif key == StandardDataKeys.ENERGY_LOAD_DAILY_KWH:
            # Load energy should also be limited by inverter capacity plus some grid import
            max_power_w = self.app_state.inverter_max_ac_power_w * 1.5  # Allow for some grid direct consumption

        # If no specific limit is found, fall back to the inverter's max AC power
        if not max_power_w or max_power_w <= 0:
            max_power_w = self.app_state.inverter_max_ac_power_w
            logger.warning(f"FILTER: No specific power limit found for '{key}', using inverter max AC power: {max_power_w}W")

        # 3. Handle daily resets: Only accept significant drops as resets (not sensor glitches)
        if value < last_known_value and not math.isclose(value, last_known_value):
            # Check if this could be a legitimate daily reset (usually happens around midnight)
            current_time = time.time()
            current_hour = time.localtime(current_time).tm_hour
            
            # Only accept as daily reset if:
            # 1. It's during typical reset hours (23:00-02:00) AND
            # 2. New value is very small (< 10% of last value) AND
            # 3. Last value was substantial (> 5.0 kWh) AND  
            # 4. New value is reasonable for a reset (< 2.0 kWh)
            is_reset_time = current_hour >= 23 or current_hour <= 2
            is_likely_reset = (
                is_reset_time and
                value < (last_known_value * 0.1) and 
                last_known_value > 5.0 and 
                value < 2.0
            )
            
            if is_likely_reset:
                logger.info(f"FILTER: Detected daily reset for '{key}' at {current_hour:02d}:xx. "
                            f"New value {value:.2f} kWh << last value {last_known_value:.2f} kWh. "
                            f"Accepting as daily reset.")
                self.potential_spikes.pop(key, None) # Clear any pending spike state on reset
                return value  # Accept the new (reset) value
            else:
                # Not a valid reset - treat as invalid decrease (sensor glitch)
                if current_hour >= 23 or current_hour <= 2:
                    reason = f"during reset hours but criteria not met (last: {last_known_value:.2f}, new: {value:.2f})"
                else:
                    reason = f"outside reset hours ({current_hour:02d}:xx)"
                    
                logger.warning(f"FILTER: '{key}' - Invalid decrease detected {reason}. "
                             f"Energy values should only increase during the day. Holding last value: {last_known_value:.2f} kWh")
                return last_known_value

        # Note: Daily reset detection is already handled above in step 3

        # 5. Time-based adaptive spike handling with enhanced protection against extreme values
        if last_known_value > 0.01: # Start comparing after a small initial value
            # Calculate time-based maximum increase instead of poll interval-based
            current_time = time.time()
            last_timestamp = self.last_energy_timestamps.get(key)
            
            if last_timestamp is None:
                # First time seeing this key, use default poll interval as fallback
                elapsed_hours = self.app_state.poll_interval / 3600
                logger.debug(f"FILTER: '{key}' - First timestamp, using poll interval fallback: {elapsed_hours:.4f}h")
            else:
                # Calculate actual elapsed time
                elapsed_seconds = current_time - last_timestamp
                elapsed_hours = elapsed_seconds / 3600
                
                # Sanity check: if elapsed time is too small or too large, use reasonable bounds
                if elapsed_seconds < 1:  # Less than 1 second
                    elapsed_hours = self.app_state.poll_interval / 3600
                    logger.debug(f"FILTER: '{key}' - Elapsed time too small ({elapsed_seconds:.1f}s), using poll interval")
                elif elapsed_seconds > 3600:  # More than 1 hour
                    elapsed_hours = 1.0  # Cap at 1 hour to prevent huge spikes after long outages
                    logger.debug(f"FILTER: '{key}' - Elapsed time capped at 1 hour (was {elapsed_seconds/3600:.2f}h)")
                else:
                    logger.debug(f"FILTER: '{key}' - Using actual elapsed time: {elapsed_seconds:.1f}s ({elapsed_hours:.4f}h)")
            
            # Update timestamp for next calculation
            self.last_energy_timestamps[key] = current_time
            
            # Calculate maximum allowed increase based on actual elapsed time
            max_increase_kwh = (max_power_w / 1000) * elapsed_hours * 3.0 # 3x "normal" change for safety margin
            max_increase_kwh += 0.1 # Allow a little headroom for rounding or BMS imprecision
            
            # Note: Daily limit check is already performed at the beginning of this function
            
            logger.debug(f"FILTER: '{key}' - Last: {last_known_value:.2f}, Current: {value:.2f}, "
                        f"Elapsed: {elapsed_hours*3600:.1f}s, Max Increase: {max_increase_kwh:.3f} kWh")

            is_spike = value > (last_known_value + max_increase_kwh)
            
            if is_spike:
                # For energy values, be much more strict about large jumps
                # If the jump is more than 10x the normal max, reject it immediately
                # This prevents unit conversion errors (Wh vs kWh) and sensor glitches
                strict_spike_threshold_kwh = max_increase_kwh * 10
                if value > (last_known_value + strict_spike_threshold_kwh):
                    logger.warning(f"FILTER: '{key}' - Large energy spike rejected outright. "
                                 f"Value: {value:.2f} kWh, Last: {last_known_value:.2f} kWh, "
                                 f"Increase: {(value - last_known_value):.2f} kWh > {strict_spike_threshold_kwh:.2f} kWh threshold. "
                                 f"This is likely a sensor error or unit conversion issue."
                                 )
                    return last_known_value

                # Absurd-spike check: If the jump is 100x the normal max, reject it immediately.
                absurd_spike_threshold_kwh = max_increase_kwh * 100
                if value > (last_known_value + absurd_spike_threshold_kwh):
                    logger.warning(f"FILTER: '{key}' - Absurd spike rejected outright. "
                                 f"Value: {value:.2f}, Last: {last_known_value:.2f}, "
                                 f"Absurd Threshold: >{absurd_spike_threshold_kwh:.2f} kWh above last"
                                 )
                    return last_known_value

                logger.warning(f"FILTER: '{key}' - Initial spike detected. Value: {value:.2f} kWh, "
                            f"Last: {last_known_value:.2f} kWh, "
                            f"Max Increase: {max_increase_kwh:.3f} kWh"
                            )
                
                potential_value, count = self.potential_spikes.get(key, (None, 0))

                if potential_value is not None and math.isclose(value, potential_value):
                    count += 1 # Spike is same as previously observed one
                    logger.debug(f"FILTER: '{key}' - Potential spike repeated. "
                                 f"Value: {value:.2f} kWh, Count: {count}/{self.spike_confirmation_threshold}"
                                )
                else: # This is a new, different potential spike.
                    count = 1 # Reset counter.
                    logger.debug(f"FILTER: '{key}' - New potential spike. "
                                 f"Value: {value:.2f} kWh, Resetting counter."
                                )
                
                self.potential_spikes[key] = (value, count)
                
                if count >= self.spike_confirmation_threshold:
                    logger.info(f"FILTER: '{key}' - Spike CONFIRMED as new baseline. "
                                f"New value: {value:.2f} kWh (previously {last_known_value:.2f} kWh)"
                                )
                    self.potential_spikes.pop(key, None) # Clear state
                    return value # Accept the new value
                else:
                    logger.warning(f"FILTER: '{key}' - Potential spike HOLDING. "
                                   f"Value: {value:.2f} kWh (Last valid: {last_known_value:.2f} kWh), "
                                   f"Count: {count}/{self.spike_confirmation_threshold}"
                                  )
                    return last_known_value # Reject spike for now
            else:
                logger.debug(f"FILTER: '{key}' - No spike detected. Value: {value:.2f} kWh, "
                             f"Increase from last: {(value - last_known_value):.3f} kWh"
                             )
                if key in self.potential_spikes: # Wasn't a spike, clear state
                     logger.info(f"FILTER: '{key}' - Potential spike cleared, accepting value of {value:.2f} kWh")
                     self.potential_spikes.pop(key, None)
        
        # If all checks pass, the new value is good.
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
            return last_good_data

        filtered_data = {}
        all_keys = set(current_data.keys()) | set(last_good_data.keys())

        power_keys = [
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS, StandardDataKeys.AC_POWER_WATTS,
            StandardDataKeys.BATTERY_POWER_WATTS, StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS,
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS
        ]
        energy_keys = [
            StandardDataKeys.ENERGY_PV_DAILY_KWH, StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH,
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH, StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH,
            StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH, StandardDataKeys.ENERGY_LOAD_DAILY_KWH
        ]

        for key in all_keys:
            current_value = current_data.get(key)
            last_value = last_good_data.get(key)
            
            if key in power_keys:
                filtered_data[key] = self._filter_power_value(key, current_value, last_value)
            elif key == StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: # Specific logging
                logger.debug(f"FILTER: Applying filter for GridImport. Current: {current_value}, Last: {last_value}")
                filtered_data[key] = self._filter_energy_value(key, current_value, last_value)
            elif key in energy_keys:
                filtered_data[key] = self._filter_energy_value(key, current_value, last_value)
            else:
                # For non-filtered keys (like status text, alerts), prefer the current value if it exists, else fall back.
                filtered_data[key] = current_value if current_value is not None else last_value
        
        return filtered_data