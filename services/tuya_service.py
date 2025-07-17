# services/tuya_service.py
import logging
import threading
import time
from typing import Optional, Union

from core.app_state import AppState
from plugins.plugin_interface import StandardDataKeys
from utils.helpers import TUYA_STATE_DISABLED, TUYA_STATE_UNKNOWN, TUYA_STATE_ON, TUYA_STATE_OFF

logger = logging.getLogger(__name__)

class TuyaService:
    def __init__(self, app_state: AppState):
        self.app_state = app_state

        if not self.app_state.enable_tuya:
            logger.info("Tuya Service: Disabled by configuration.")
            self.app_state.tuya_last_known_state = TUYA_STATE_DISABLED
        else:
            logger.info("Tuya Service: Enabled. Device will be initialized on first use.")
            # Get the initial state at startup in a non-blocking way
            threading.Thread(target=self.get_initial_state, name="TuyaInitialState", daemon=True).start()

    def _initialize_device(self):
        """Creates the Tuya device object from config and stores it in app_state."""
        # This function should only be called within a tuya_lock context.
        
        # Only import tinytuya when we are actually trying to use it.
        try:
            import tinytuya
        except ImportError:
            logger.error("Tuya library not found. Please install with 'pip install tinytuya'.")
            self.app_state.enable_tuya = False # Disable it for the rest of the run
            self.app_state.tuya_device = None
            return

        # Check again in case it was initialized by another thread
        if self.app_state.tuya_device:
            return
        
        logger.info("Initializing Tuya device object...")
        try:
            addr = None if self.app_state.tuya_ip_address.lower() == 'auto' else self.app_state.tuya_ip_address
            device = tinytuya.OutletDevice(
                self.app_state.tuya_device_id,
                addr,
                self.app_state.tuya_local_key
            )
            device.set_version(float(self.app_state.tuya_version))
            device.set_socketTimeout(7)
            # A quick ping to see if it's there
            status = device.status()
            if isinstance(status, dict) and 'dps' in status:
                self.app_state.tuya_device = device
                logger.info(f"Tuya device object initialized and communication confirmed. Status: {status}")
            else:
                logger.error(f"Failed to initialize Tuya device object. Status check returned invalid response: {status}")
                self.app_state.tuya_device = None
        except Exception as e:
            logger.error(f"Failed to initialize Tuya device object: {e}", exc_info=True)
            self.app_state.tuya_device = None

    def get_initial_state(self):
        """Fetches the initial state of the Tuya device at startup."""
        if not self.app_state.enable_tuya:
            return

        with self.app_state.tuya_lock:
            # Initialize the device on the first actual use
            if not self.app_state.tuya_device:
                self._initialize_device()

            if not self.app_state.tuya_device:
                logger.warning("Cannot get initial Tuya state, device not initialized.")
                self.app_state.tuya_last_known_state = TUYA_STATE_UNKNOWN
                return

            try:
                # The status was already checked in _initialize_device, but we can re-check
                status = self.app_state.tuya_device.status()
                if isinstance(status, dict) and 'dps' in status and '1' in status['dps']:
                    state = TUYA_STATE_ON if status['dps']['1'] else TUYA_STATE_OFF
                    self.app_state.tuya_last_known_state = state
                    self.app_state.tuya_last_state_change_time = time.monotonic()
                    logger.info(f"Initial Tuya device state is: {state}")
                else:
                    self.app_state.tuya_last_known_state = TUYA_STATE_UNKNOWN
                    logger.warning(f"Could not determine initial Tuya state. Response: {status}")
            except Exception as e:
                self.app_state.tuya_last_known_state = TUYA_STATE_UNKNOWN
                logger.error(f"Error getting initial Tuya state: {e}. Device will be re-initialized on next attempt.")
                # Setting device to None will force re-initialization on the next call
                self.app_state.tuya_device = None

    def trigger_control_from_temp(self, temperature: Optional[Union[float, int]]):
        """
        Checks the temperature against thresholds and triggers Tuya control if needed.
        This should be called from the main data processing loop.
        """
        if not self.app_state.enable_tuya or not isinstance(temperature, (int, float)):
            return

        # Start the actual control logic in a separate thread to not block the main loop
        threading.Thread(
            target=self._control_device,
            args=(temperature,),
            daemon=True,
            name="TuyaControl"
        ).start()

    def _control_device(self, temperature: float):
        """The core logic that runs in a thread to control the device."""
        current_state = self.app_state.tuya_last_known_state
        desired_state = current_state

        if temperature >= self.app_state.temp_threshold_on:
            desired_state = TUYA_STATE_ON
        elif temperature <= self.app_state.temp_threshold_off:
            desired_state = TUYA_STATE_OFF

        if desired_state == current_state and current_state != TUYA_STATE_UNKNOWN:
            return # No change needed

        cool_down_seconds = 60
        time_since_last_change = time.monotonic() - self.app_state.tuya_last_state_change_time
        if time_since_last_change < cool_down_seconds:
            logger.debug(f"Tuya cool-down active. Postponing action for {cool_down_seconds - time_since_last_change:.0f}s.")
            return

        logger.info(f"Tuya Control: Temp={temperature:.1f}°C. Current State: {current_state}. Desired State: {desired_state}.")
        
        with self.app_state.tuya_lock:
            # Re-initialize device if it was lost on a previous error
            if not self.app_state.tuya_device:
                self._initialize_device()
            
            if not self.app_state.tuya_device:
                logger.error("Tuya control aborted: Device object is not available.")
                return

            try:
                if desired_state == TUYA_STATE_ON:
                    res = self.app_state.tuya_device.turn_on()
                elif desired_state == TUYA_STATE_OFF:
                    res = self.app_state.tuya_device.turn_off()
                else: # Should not happen, but as a fallback
                    return

                logger.debug(f"Tuya command result: {res}")

                # After an operation, re-check status to confirm
                time.sleep(1) # Give the device a moment to update its state
                status = self.app_state.tuya_device.status()
                if isinstance(status, dict) and 'dps' in status and '1' in status['dps']:
                    new_state = TUYA_STATE_ON if status['dps']['1'] else TUYA_STATE_OFF
                    if new_state != self.app_state.tuya_last_known_state:
                        logger.info(f"Tuya state successfully changed: {self.app_state.tuya_last_known_state} -> {new_state}")
                        self.app_state.tuya_last_known_state = new_state
                        self.app_state.tuya_last_state_change_time = time.monotonic()
                    else:
                        logger.info(f"Tuya command sent, and state is confirmed as {new_state}.")
                else:
                    logger.warning(f"Tuya control command sent, but status confirmation failed. Response: {status}")
                    self.app_state.tuya_last_known_state = TUYA_STATE_UNKNOWN

            except Exception as e:
                logger.error(f"Tuya control error: {e}", exc_info=True)
                # Reset on error to force re-initialization next time
                self.app_state.tuya_device = None 
                self.app_state.tuya_last_known_state = TUYA_STATE_UNKNOWN