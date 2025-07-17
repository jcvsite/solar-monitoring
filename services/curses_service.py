import curses
import logging
import time
import copy
import threading
import re
from datetime import datetime
from typing import Tuple, Any, Dict

from core.app_state import AppState
from plugins.plugin_interface import StandardDataKeys
from utils.helpers import (
    format_value, UNKNOWN, STATUS_NA, STATUS_ERROR, STATUS_CONNECTED,
    TUYA_STATE_DISABLED, STATUS_INITIALIZING, STATUS_DISCONNECTED
)

logger = logging.getLogger(__name__)

# Color Pair Definitions
COLOR_PAIR_DEFAULT = 1
COLOR_PAIR_GREEN = 2
COLOR_PAIR_YELLOW = 3
COLOR_PAIR_RED = 4
COLOR_PAIR_BLUE = 5
COLOR_PAIR_ORANGE = 6
COLOR_PAIR_GREY = 7

# BMS Cell Background Color Pairs
COLOR_PAIR_BG_NORMAL = 20
COLOR_PAIR_BG_LOW_WARN = 21
COLOR_PAIR_BG_HIGH_WARN = 22
COLOR_PAIR_BG_CRITICAL_LOW = 23
COLOR_PAIR_BG_CRITICAL_HIGH = 24
COLOR_PAIR_BG_DEFAULT = 13

class CursesService:
    """Manages a real-time text-based console dashboard using curses.

    Displays key metrics for solar system components (inverter, battery, grid)
    and plugins, with color-coded BMS cell voltage visualization.
    """
    ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.enabled = app_state.config.getboolean('CONSOLE_DASHBOARD', 'ENABLE_DASHBOARD', fallback=True)
        self.update_interval = app_state.config.getint('CONSOLE_DASHBOARD', 'DASHBOARD_UPDATE_INTERVAL', fallback=1)
        self.stdscr = None
        self.curses_available = False
        try:
            import curses
            self.curses_available = True
        except ImportError:
            logger.warning("Curses library not found, console dashboard disabled.")
            self.enabled = False

    @staticmethod
    def _hex_to_curses_rgb(hex_color: str) -> Tuple[int, int, int]:
        """Converts hex color to curses RGB tuple (0-1000 scale)."""
        hex_color = hex_color.lstrip('#')
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (r * 1000 // 255, g * 1000 // 255, b * 1000 // 255)

    def start(self) -> None:
        """Starts the curses dashboard in a separate thread if enabled."""
        if not self.enabled:
            return
        threading.Thread(target=self._run_dashboard, name="CursesUI", daemon=True).start()

    def force_cleanup(self) -> None:
        """Force cleanup of curses state - called when watchdog restarts threads."""
        try:
            logger.info("Force cleanup triggered - performing targeted BMS color preservation")
            
            if self.stdscr:
                # Instead of aggressive reset, do a targeted BMS color refresh
                self._preserve_and_restore_bms_colors()
            else:
                # Even if stdscr is None, try to reset terminal colors aggressively
                self._emergency_terminal_reset()
                
            logger.info("Force cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during forced curses cleanup: {e}")
            # Emergency fallback
            self._emergency_terminal_reset()

    def _preserve_and_restore_bms_colors(self) -> None:
        """
        Preserve and restore ALL colors during plugin reconnections.
        
        This method handles both BMS background colors AND regular text colors
        to prevent any colors from being lost during plugin reconnection events.
        """
        try:
            logger.info("Preserving and restoring ALL colors during plugin reconnection")
            
            # Force reinitialize color system to ensure all colors work
            if curses.has_colors():
                try:
                    curses.start_color()
                    curses.use_default_colors()
                except curses.error:
                    pass
            
            # Restore ALL color pairs - both text and BMS background colors
            self._init_safe_colors()
            
            # Explicitly verify that text colors are working
            self._verify_text_colors()
            
            # Double-check BMS colors specifically (since they were the main issue)
            self._ensure_bms_colors()
            
            # Force a complete screen refresh to apply all color changes
            if self.stdscr:
                self.stdscr.clear()
                self.stdscr.refresh()
            
            logger.info("Complete color preservation completed successfully")
            
        except Exception as e:
            logger.warning(f"Color preservation failed, falling back to aggressive reset: {e}")
            # If targeted approach fails, fall back to aggressive reset
            self._aggressive_color_reset()

    def _emergency_terminal_reset(self) -> None:
        """Emergency terminal reset when curses is not available."""
        try:
            import os
            if os.name == 'nt':  # Windows
                os.system('cls')
                os.system('color 07')  # Reset to white on black
            else:  # Unix/Linux
                os.system('reset')
                os.system('tput sgr0')
            logger.info("Emergency terminal reset completed")
        except Exception as e:
            logger.error(f"Emergency terminal reset failed: {e}")

    def stop(self) -> None:
        """Stop the curses service and cleanup terminal state."""
        try:
            # Set running flag to false to stop the dashboard thread
            self.app_state.running = False
            
            # Force cleanup to restore terminal
            self.force_cleanup()
            
            logger.info("Curses service stopped.")
        except Exception as e:
            logger.error(f"Error stopping curses service: {e}")

    def _run_dashboard(self) -> None:
        """Main loop for the curses dashboard thread."""
        if not self.curses_available:
            return
        try:
            self.stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)
            curses.curs_set(0)
            self.stdscr.nodelay(True)
            self._init_curses_colors()
            layout = {'label_width': 12, 'col_padding': 3, 'data_start_y': 4}

            # Color refresh counter to periodically check for corruption
            color_refresh_counter = 0
            
            while self.app_state.running:
                loop_start = time.monotonic()
                
                input_result = self._handle_input()
                if input_result == 'quit':
                    self.app_state.main_threads_stop_event.set()
                    break
                
                # Disable automatic color refresh - only refresh during watchdog restarts
                # The automatic refresh was causing the alternating color issue
                # color_refresh_counter += 1
                # if color_refresh_counter >= 300:
                #     self._refresh_colors_if_needed()
                #     color_refresh_counter = 0
                
                with self.app_state.data_lock:
                    data_snapshot = copy.deepcopy(self.app_state.shared_data)
                
                self._draw_screen(data_snapshot, layout)
                
                if input_result == 'resize':
                    self.stdscr.clear()
                    self._draw_screen(data_snapshot, layout)
                
                loop_duration = time.monotonic() - loop_start
                time.sleep(max(0, self.update_interval - loop_duration))
        except Exception as e:
            logger.error(f"Curses dashboard crashed: {e}", exc_info=True)
        finally:
            self._cleanup_curses()

    def _init_curses_colors(self) -> None:
        """
        Initializes color pairs with robust error handling to prevent corruption.
        
        Uses a simplified, bulletproof approach that avoids complex color operations
        that can cause terminal state corruption during plugin reconnections.
        """
        if not self.curses_available:
            return
            
        try:
            # Only initialize colors if terminal supports them
            if not curses.has_colors():
                logger.info("Terminal does not support colors, using monochrome mode")
                return
                
            curses.start_color()
            
            # CRITICAL: Always use default colors to prevent background corruption
            curses.use_default_colors()
            
            # Initialize only essential color pairs with maximum safety
            self._init_safe_colors()
            
            logger.debug("Curses colors initialized successfully")
            
        except Exception as e:
            logger.warning(f"Color initialization failed, using monochrome: {e}")
            # Don't try to recover - just use no colors

    def _init_safe_colors(self) -> None:
        """
        Initialize only essential colors with maximum safety and error handling.
        
        This method uses the most conservative approach to prevent any color
        corruption issues during plugin reconnections or thread restarts.
        """
        try:
            # Only initialize the most basic, essential color pairs
            # Use -1 for background to maintain terminal default background
            
            # Essential text colors - keep it minimal
            curses.init_pair(COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, -1)
            curses.init_pair(COLOR_PAIR_GREEN, curses.COLOR_GREEN, -1)
            curses.init_pair(COLOR_PAIR_YELLOW, curses.COLOR_YELLOW, -1)
            curses.init_pair(COLOR_PAIR_RED, curses.COLOR_RED, -1)
            curses.init_pair(COLOR_PAIR_BLUE, curses.COLOR_CYAN, -1)
            curses.init_pair(COLOR_PAIR_ORANGE, curses.COLOR_MAGENTA, -1)
            
            # Grey color for disabled status - use a visible approach
            self._init_grey_color_safe()
            
            # BMS background colors - ROBUST initialization with error handling
            # Each color pair is initialized individually with fallback
            self._init_bms_color_pair(COLOR_PAIR_BG_NORMAL, curses.COLOR_BLACK, curses.COLOR_GREEN)
            self._init_bms_color_pair(COLOR_PAIR_BG_LOW_WARN, curses.COLOR_BLACK, curses.COLOR_YELLOW)
            self._init_bms_color_pair(COLOR_PAIR_BG_HIGH_WARN, curses.COLOR_BLACK, curses.COLOR_YELLOW)
            self._init_bms_color_pair(COLOR_PAIR_BG_CRITICAL_LOW, curses.COLOR_WHITE, curses.COLOR_RED)
            self._init_bms_color_pair(COLOR_PAIR_BG_CRITICAL_HIGH, curses.COLOR_WHITE, curses.COLOR_RED)
            
            logger.debug("Safe colors initialized successfully")
            
        except curses.error as e:
            logger.warning(f"Safe color initialization failed: {e}")
            # If even safe colors fail, the system will work in monochrome
        except Exception as e:
            logger.error(f"Unexpected error in safe color initialization: {e}")

    def _init_bms_color_pair(self, pair_id: int, fg_color: int, bg_color: int) -> None:
        """
        Initialize a single BMS background color pair with robust error handling.
        
        This method ensures that BMS background colors are properly initialized
        and maintained even during color recovery operations.
        """
        try:
            curses.init_pair(pair_id, fg_color, bg_color)
            logger.debug(f"BMS color pair {pair_id} initialized successfully")
        except curses.error as e:
            logger.warning(f"Failed to initialize BMS color pair {pair_id}: {e}")
            # Fallback: try with default background
            try:
                curses.init_pair(pair_id, fg_color, -1)
                logger.debug(f"BMS color pair {pair_id} initialized with default background")
            except curses.error:
                logger.warning(f"Complete failure to initialize BMS color pair {pair_id}")
        except Exception as e:
            logger.error(f"Unexpected error initializing BMS color pair {pair_id}: {e}")

    def _ensure_bms_colors(self) -> None:
        """
        Ensure BMS background colors are properly initialized after color reset.
        
        This method is called after aggressive color reset to make sure
        BMS cell background colors are working correctly.
        """
        try:
            logger.debug("Ensuring BMS background colors are properly initialized...")
            
            # Re-initialize all BMS background color pairs with extra verification
            bms_color_pairs = [
                (COLOR_PAIR_BG_NORMAL, curses.COLOR_BLACK, curses.COLOR_GREEN),
                (COLOR_PAIR_BG_LOW_WARN, curses.COLOR_BLACK, curses.COLOR_YELLOW),
                (COLOR_PAIR_BG_HIGH_WARN, curses.COLOR_BLACK, curses.COLOR_YELLOW),
                (COLOR_PAIR_BG_CRITICAL_LOW, curses.COLOR_WHITE, curses.COLOR_RED),
                (COLOR_PAIR_BG_CRITICAL_HIGH, curses.COLOR_WHITE, curses.COLOR_RED)
            ]
            
            for pair_id, fg, bg in bms_color_pairs:
                try:
                    # Initialize the color pair
                    curses.init_pair(pair_id, fg, bg)
                    
                    # Test that it works by getting the color pair
                    test_attr = curses.color_pair(pair_id)
                    if test_attr == 0:
                        logger.warning(f"BMS color pair {pair_id} returned 0 attribute")
                    else:
                        logger.debug(f"BMS color pair {pair_id} verified successfully")
                        
                except curses.error as e:
                    logger.warning(f"Failed to ensure BMS color pair {pair_id}: {e}")
                    # Try fallback with default background
                    try:
                        curses.init_pair(pair_id, fg, -1)
                        logger.debug(f"BMS color pair {pair_id} initialized with default background fallback")
                    except curses.error:
                        logger.error(f"Complete failure to initialize BMS color pair {pair_id}")
            
            logger.debug("BMS color verification completed")
            
        except Exception as e:
            logger.error(f"Error ensuring BMS colors: {e}")

    def _verify_text_colors(self) -> None:
        """
        Verify that text colors are properly initialized and working.
        
        This method ensures that regular text colors (green, red, yellow, etc.)
        are working correctly after color recovery operations.
        """
        try:
            logger.debug("Verifying text colors are properly initialized...")
            
            # Re-initialize and verify all text color pairs (except grey - handle separately)
            text_color_pairs = [
                (COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, -1),
                (COLOR_PAIR_GREEN, curses.COLOR_GREEN, -1),
                (COLOR_PAIR_YELLOW, curses.COLOR_YELLOW, -1),
                (COLOR_PAIR_RED, curses.COLOR_RED, -1),
                (COLOR_PAIR_BLUE, curses.COLOR_CYAN, -1),
                (COLOR_PAIR_ORANGE, curses.COLOR_MAGENTA, -1)
            ]
            
            for pair_id, fg, bg in text_color_pairs:
                try:
                    # Initialize the color pair
                    curses.init_pair(pair_id, fg, bg)
                    
                    # Test that it works by getting the color pair
                    test_attr = curses.color_pair(pair_id)
                    if test_attr == 0:
                        logger.warning(f"Text color pair {pair_id} returned 0 attribute")
                    else:
                        logger.debug(f"Text color pair {pair_id} verified successfully")
                        
                except curses.error as e:
                    logger.warning(f"Failed to verify text color pair {pair_id}: {e}")
            
            # Handle grey color separately using the safe initialization method
            try:
                self._init_grey_color_safe()
                # Test that grey color works
                test_attr = curses.color_pair(COLOR_PAIR_GREY)
                if test_attr == 0:
                    logger.warning("Grey color pair returned 0 attribute after safe initialization")
                else:
                    logger.debug("Grey color pair verified successfully after safe initialization")
            except Exception as e:
                logger.warning(f"Failed to verify grey color pair with safe method: {e}")
            
            logger.debug("Text color verification completed")
            
        except Exception as e:
            logger.error(f"Error verifying text colors: {e}")

    def _init_grey_color(self) -> None:
        """
        Initializes grey color with proper visibility for disabled status.
        
        This method ensures that "disabled" status text is visible by using
        a color that contrasts well with the terminal background.
        """
        try:
            # Try to use a visible grey color that works on both light and dark terminals
            if curses.COLORS >= 256:
                # Use 256-color palette for better grey visibility
                # Color 8 is bright black/dark grey, Color 7 is light grey
                curses.init_pair(COLOR_PAIR_GREY, 8, -1)  # Dark grey on default background
            else:
                # Fallback to basic colors - use white instead of black for visibility
                curses.init_pair(COLOR_PAIR_GREY, curses.COLOR_WHITE, -1)
                
            logger.debug("Grey color initialized successfully for disabled status")
        except curses.error as e:
            logger.warning(f"Failed to initialize grey color: {e}")
            # Ultimate fallback - use default color
            try:
                curses.init_pair(COLOR_PAIR_GREY, curses.COLOR_WHITE, -1)
            except curses.error:
                # If all else fails, use the default color pair
                pass

    def _init_grey_color_safe(self) -> None:
        """
        Initialize grey color with maximum visibility for disabled status.
        
        This method ensures that "disabled" status text is always visible
        by using the most appropriate color for the terminal.
        """
        try:
            # Strategy: Use a color that will be visible on both light and dark backgrounds
            if curses.COLORS >= 256:
                # Use 256-color palette - color 244 is a nice medium grey
                try:
                    curses.init_pair(COLOR_PAIR_GREY, 244, -1)  # Medium grey
                    logger.debug("Grey color initialized with 256-color palette (244)")
                    return
                except curses.error:
                    pass
            
            # Fallback 1: Try bright black (color 8) if available
            try:
                if curses.COLORS >= 16:
                    curses.init_pair(COLOR_PAIR_GREY, 8, -1)  # Bright black/dark grey
                    logger.debug("Grey color initialized with bright black (8)")
                    return
            except curses.error:
                pass
            
            # Fallback 2: Use white for visibility (better than invisible black)
            try:
                curses.init_pair(COLOR_PAIR_GREY, curses.COLOR_WHITE, -1)
                logger.debug("Grey color initialized with white fallback")
                return
            except curses.error:
                pass
            
            # Fallback 3: Use cyan as a visible alternative
            try:
                curses.init_pair(COLOR_PAIR_GREY, curses.COLOR_CYAN, -1)
                logger.debug("Grey color initialized with cyan fallback")
                return
            except curses.error:
                pass
            
            logger.warning("All grey color initialization attempts failed")
            
        except Exception as e:
            logger.error(f"Error in grey color safe initialization: {e}")
            # Last resort - try to use default color pair
            try:
                curses.init_pair(COLOR_PAIR_GREY, curses.COLOR_WHITE, -1)
            except:
                pass

    def _refresh_colors_if_needed(self) -> None:
        """
        Aggressively refresh colors to prevent corruption during plugin reconnections.
        
        This method detects color corruption and performs a complete color system
        reset to restore proper display colors.
        """
        try:
            # Test multiple color pairs to detect corruption
            test_pairs = [COLOR_PAIR_GREEN, COLOR_PAIR_RED, COLOR_PAIR_YELLOW]
            corruption_detected = False
            
            for pair_id in test_pairs:
                try:
                    test_attr = curses.color_pair(pair_id)
                    # Additional test: try to use the attribute
                    if test_attr == 0:  # This might indicate corruption
                        corruption_detected = True
                        break
                except curses.error:
                    corruption_detected = True
                    break
            
            if corruption_detected:
                logger.warning("Color corruption detected, performing aggressive color reset")
                self._aggressive_color_reset()
            else:
                # Even if no corruption detected, do a lightweight refresh periodically
                # This helps prevent gradual color degradation
                self._lightweight_color_refresh()
                
        except Exception as e:
            logger.warning(f"Color check failed, performing emergency reset: {e}")
            self._aggressive_color_reset()

    def _aggressive_color_reset(self) -> None:
        """
        Performs an aggressive color system reset to fix corruption.
        
        This method completely reinitializes the color system from scratch
        to recover from severe color corruption.
        """
        try:
            logger.info("Performing aggressive color reset...")
            
            # Step 1: Reset all color pairs to default
            if curses.has_colors():
                try:
                    for i in range(1, min(curses.COLOR_PAIRS, 64)):
                        try:
                            curses.init_pair(i, curses.COLOR_WHITE, -1)
                        except curses.error:
                            break
                except curses.error:
                    pass
            
            # Step 2: Reinitialize color system
            try:
                curses.start_color()
                curses.use_default_colors()
            except curses.error:
                pass
            
            # Step 3: Reinitialize our color pairs with extra emphasis on BMS colors
            self._init_safe_colors()
            
            # Step 4: Double-check BMS background colors are properly initialized
            self._ensure_bms_colors()
            
            # Step 5: Clear and refresh screen to apply changes
            self.stdscr.clear()
            self.stdscr.refresh()
            
            logger.info("Aggressive color reset completed successfully")
            
        except Exception as e:
            logger.error(f"Aggressive color reset failed: {e}")
            # Last resort: try terminal reset
            try:
                import os
                if os.name == 'nt':
                    os.system('color')  # Reset Windows console colors
                else:
                    os.system('tput sgr0')  # Reset Unix terminal attributes
            except:
                pass

    def _lightweight_color_refresh(self) -> None:
        """
        Performs a lightweight color refresh to maintain color stability.
        
        This method does minimal color maintenance to prevent gradual
        color degradation without disrupting the display.
        """
        try:
            # Just reinitialize the most critical color pairs
            essential_pairs = [
                (COLOR_PAIR_GREEN, curses.COLOR_GREEN, -1),
                (COLOR_PAIR_RED, curses.COLOR_RED, -1),
                (COLOR_PAIR_YELLOW, curses.COLOR_YELLOW, -1),
                (COLOR_PAIR_DEFAULT, curses.COLOR_WHITE, -1)
            ]
            
            for pair_id, fg, bg in essential_pairs:
                try:
                    curses.init_pair(pair_id, fg, bg)
                except curses.error:
                    pass  # Ignore errors in lightweight refresh
                    
        except Exception as e:
            logger.debug(f"Lightweight color refresh failed: {e}")

    def _get_bms_color_attr(self, key: str, value: Any, background: bool = False) -> int:
        """
        Returns curses color attribute for BMS data with proper error handling.
        
        This method prevents color corruption by safely handling color pair
        operations and providing fallbacks when color operations fail.
        """
        if not isinstance(value, (int, float)):
            return self._get_color_attr(value)

        text_pair, bg_pair = COLOR_PAIR_GREEN, COLOR_PAIR_BG_NORMAL

        try:
            if key == StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS:
                text_pair = COLOR_PAIR_RED if value >= 0.030 else COLOR_PAIR_ORANGE if value >= 0.010 else text_pair
            elif key == StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT:
                text_pair = COLOR_PAIR_RED if value <= 95 else COLOR_PAIR_ORANGE if value < 100 else text_pair
            elif key.startswith(StandardDataKeys.BMS_CELL_VOLTAGES_LIST):
                if value >= 3.65:
                    bg_pair = COLOR_PAIR_BG_CRITICAL_HIGH
                elif value >= 3.55:
                    bg_pair = COLOR_PAIR_BG_HIGH_WARN
                elif value >= 3.15:
                    bg_pair = COLOR_PAIR_BG_NORMAL
                elif value >= 2.80:
                    bg_pair = COLOR_PAIR_BG_LOW_WARN
                else:
                    bg_pair = COLOR_PAIR_BG_CRITICAL_LOW

            # Safely get color pair with error handling
            target_pair = bg_pair if background else text_pair
            return self._safe_color_pair(target_pair)
            
        except Exception as e:
            logger.debug(f"Error in BMS color attribute calculation: {e}")
            return self._safe_color_pair(COLOR_PAIR_DEFAULT)

    def _safe_color_pair(self, pair_id: int) -> int:
        """
        Safely returns a color pair attribute with error handling.
        
        This method prevents curses errors that can cause color corruption
        by providing fallbacks when color pair operations fail.
        """
        try:
            return curses.color_pair(pair_id)
        except curses.error:
            # If the requested color pair fails, fall back to default
            try:
                return curses.color_pair(COLOR_PAIR_DEFAULT)
            except curses.error:
                # If even default fails, return no attributes
                return 0

    def _handle_input(self) -> str | None:
        """Handles keyboard input, returning 'quit', 'resize', or None."""
        try:
            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q')):
                return 'quit'
            if key == curses.KEY_RESIZE:
                return 'resize'
        except curses.error:
            pass
        return None

    def _cleanup_curses(self) -> None:
        """Restores terminal to normal state and prevents color corruption."""
        if self.stdscr:
            try:
                # Clear screen and reset colors before cleanup
                self.stdscr.clear()
                self.stdscr.refresh()
                
                # Reset color pairs to prevent background corruption
                if curses.has_colors():
                    try:
                        # Reset all color pairs to default to prevent lingering background colors
                        curses.init_pair(1, curses.COLOR_WHITE, -1)
                        for i in range(2, min(curses.COLOR_PAIRS, 64)):
                            try:
                                curses.init_pair(i, curses.COLOR_WHITE, -1)
                            except curses.error:
                                break
                    except curses.error:
                        pass
                
                # Standard curses cleanup
                curses.nocbreak()
                self.stdscr.keypad(False)
                curses.echo()
                curses.curs_set(1)  # Restore cursor visibility
                curses.endwin()
                
                # Force terminal reset to clear any lingering color state
                import os
                if os.name == 'nt':  # Windows
                    os.system('cls')
                else:  # Unix/Linux
                    os.system('reset')
                
                logger.info("Curses service cleaned up with color reset.")
            except Exception as e:
                logger.error(f"Error during curses cleanup: {e}")
                # Emergency cleanup - force terminal reset
                try:
                    import os
                    if os.name == 'nt':
                        os.system('cls')
                    else:
                        os.system('reset')
                except:
                    pass

    def _get_color_attr(self, status: Any) -> int:
        """
        Returns curses color attribute based on status string with safe error handling.
        
        This method prevents color corruption by safely handling color pair
        operations and providing fallbacks when color operations fail.
        """
        s_lower = str(status).lower()
        pair, attr = COLOR_PAIR_DEFAULT, 0
        
        try:
            if any(x in s_lower for x in ["fault", "fail", "stop", "error", "alarm", "protection"]):
                pair, attr = COLOR_PAIR_RED, curses.A_BOLD
            elif any(x in s_lower for x in ["generating", "on", "connected", "discharging", "exporting", "ok", "good", "active"]):
                pair = COLOR_PAIR_GREEN
            elif any(x in s_lower for x in ["wait", "standby", "idle", "warning"]):
                pair = COLOR_PAIR_YELLOW
            elif s_lower == TUYA_STATE_DISABLED.lower():
                pair = COLOR_PAIR_GREY
            
            return self._safe_color_pair(pair) | attr
            
        except Exception as e:
            logger.debug(f"Error in color attribute calculation: {e}")
            return self._safe_color_pair(COLOR_PAIR_DEFAULT)

    def _add_str_safe(self, y: int, x: int, text: str, attr: int = 0) -> None:
        """Safely adds string to screen, handling boundaries."""
        try:
            sanitized_text = self.ANSI_ESCAPE_PATTERN.sub('', str(text))

            max_y, max_x = self.stdscr.getmaxyx()
            if 0 <= y < max_y and 0 <= x < max_x:
                # Use the sanitized text for display
                safe_text = sanitized_text[:max_x - x - 1]
                self.stdscr.addstr(y, x, safe_text, attr)
        except curses.error:
            pass

    def _add_std(self, y: int, x: int, layout: Dict, lbl: str, key: str, data: Dict,
                 prec: int = 1, unit_override: str | None = None, val_override: Any = None,
                 color_key_override: str | None = None, custom_color_attr: int | None = None) -> int:
        """Draws a standardized label-value line."""
        val_dict = data.get(key, {})
        raw_value = val_override if val_override is not None else val_dict.get("value", STATUS_NA)
        is_error = isinstance(raw_value, str) and "error" in raw_value.lower()
        unit = unit_override if unit_override is not None else val_dict.get("unit", "")
        formatted_val = raw_value if is_error else format_value(raw_value, prec)

        if unit and isinstance(unit, str) and unit not in ["Code", "TextList", "Dict"]:
            formatted_val += f" {unit}"

        attr = custom_color_attr or self._get_color_attr(
            val_override if val_override is not None else data.get(color_key_override or key, {}).get("value", raw_value)
        )

        self._add_str_safe(y, x, f"{lbl:<{layout['label_width']}}:", curses.A_BOLD)
        self._add_str_safe(y, x + layout['label_width'] + 2, str(formatted_val), attr)
        return y + 1

    def _draw_data_cols(self, data: Dict, layout: Dict, max_y: int, c1x: int, c2x: int, c3x: int) -> int:
        """Draws data columns for inverter, battery/BMS, and grid/system."""
        y1, y2, y3 = layout['data_start_y'], layout['data_start_y'], layout['data_start_y']

        # Inverter Column
        has_inverter_data = StandardDataKeys.STATIC_INVERTER_MODEL_NAME in data
        if has_inverter_data:
            inv_model = data.get(StandardDataKeys.STATIC_INVERTER_MODEL_NAME, {}).get("value", UNKNOWN)
            self._add_str_safe(y1 - 1, c1x, f"-- INV ({inv_model}) --", curses.A_BOLD)
            y1 = self._add_std(y1, c1x, layout, "Status", StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT, data)
            y1 = self._add_std(y1, c1x, layout, "Inv Temp", StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS, data, 1, "°C")
            y1 = self._add_std(y1, c1x, layout, "AC Power", StandardDataKeys.AC_POWER_WATTS, data, 0, "W")
            pv_power_val = data.get(StandardDataKeys.PV_TOTAL_DC_POWER_WATTS, {}).get("value")
            pv_capacity_val = self.app_state.pv_installed_capacity_w
            pv_power_str = f"{format_value(pv_power_val, 0)}W"
            if isinstance(pv_power_val, (int, float)) and isinstance(pv_capacity_val, (int, float)) and pv_capacity_val > 0:
                pv_percent = (pv_power_val / pv_capacity_val) * 100
                pv_power_str += f" ({format_value(pv_percent, 1)}%)"
            y1 = self._add_std(y1, c1x, layout, "PV Power", StandardDataKeys.PV_TOTAL_DC_POWER_WATTS, data, 0, unit_override="", val_override=pv_power_str)
            num_mppts = data.get(StandardDataKeys.STATIC_NUMBER_OF_MPPTS, {}).get("value", 0)
            if isinstance(num_mppts, int) and num_mppts > 0:
                for i in range(1, num_mppts + 1):
                    v_dict = data.get(f"pv_mppt{i}_voltage_volts", {})
                    p_dict = data.get(f"pv_mppt{i}_power_watts", {})
                    if v_dict and p_dict and isinstance(p_dict.get("value"), (int, float)) and p_dict["value"] > 10:
                        v, p = v_dict.get("value"), p_dict.get("value")
                        mppt_str = f"{format_value(v, 1)}V = {format_value(p, 0)}W"
                        y1 = self._add_std(y1, c1x + 2, layout, f"MPPT{i}", "", data, 0, val_override=mppt_str, color_key_override="generating")
            y1 += 1
            self._add_str_safe(y1, c1x, "-- ENERGY TODAY --", curses.A_BOLD)
            y1 += 1
            for key, label in [
                (StandardDataKeys.ENERGY_PV_DAILY_KWH, "PV Yield"),
                (StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH, "GridImport"),
                (StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH, "GridExport"),
                (StandardDataKeys.ENERGY_LOAD_DAILY_KWH, "LoadCons")
            ]:
                y1 = self._add_std(y1, c1x, layout, label, key, data, 2, "kWh")

        # Battery Column
        has_battery_data = StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT in data
        col2_start_x = c2x if has_inverter_data else c1x
        if has_battery_data:
            bms_model = data.get(StandardDataKeys.STATIC_BATTERY_MODEL_NAME, {}).get("value", UNKNOWN)
            title = f"-- BATTERY ({bms_model}) --" if bms_model != UNKNOWN else "-- BATTERY --"
            self._add_str_safe(y2 - 1, col2_start_x, title, curses.A_BOLD)
            soc = data.get(StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT, {}).get("value")
            soh = data.get(StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT, {}).get("value")
            soc_soh_str = f"{format_value(soc, 0)}%"
            soh_attr = self._get_bms_color_attr(StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT, soh)
            if isinstance(soh, (int, float)) and soh > 0:
                soc_soh_str += f" / {format_value(soh, 0)}%"
            y2 = self._add_std(y2, col2_start_x, layout, "SOC / SOH", "", data, 0, val_override=soc_soh_str, custom_color_attr=soh_attr)
            y2 = self._add_std(y2, col2_start_x, layout, "Time Est", StandardDataKeys.OPERATIONAL_BATTERY_TIME_REMAINING_ESTIMATE_TEXT, data)
            y2 = self._add_std(y2, col2_start_x, layout, "Batt Power", StandardDataKeys.BATTERY_POWER_WATTS, data, 0, "W", color_key_override=StandardDataKeys.BATTERY_STATUS_TEXT)
            y2 = self._add_std(y2, col2_start_x, layout, "BattStatus", StandardDataKeys.BATTERY_STATUS_TEXT, data, 0)
            y2 = self._add_std(y2, col2_start_x, layout, "BattChg", StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH, data, 2, "kWh")
            y2 = self._add_std(y2, col2_start_x, layout, "BattDisChg", StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH, data, 2, "kWh")

            # BMS Details
            has_bms_details = StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS in data
            if has_bms_details:
                y2 += 1
                self._add_str_safe(y2, col2_start_x, "-- BMS STATS --", curses.A_BOLD)
                y2 += 1
                v_delta = data.get(StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS, {}).get("value")
                v_delta_attr = self._get_bms_color_attr(StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS, v_delta)
                for key, label, prec, unit in [
                    (StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS, "Cell V Min", 3, "V"),
                    (StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS, "Cell V Max", 3, "V"),
                    (StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS, "Cell V Diff", 3, "V")
                ]:
                    y2 = self._add_std(y2, col2_start_x, layout, label, key, data, prec, unit,
                                     custom_color_attr=v_delta_attr if key == StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS else None)

                rem_cap = data.get(StandardDataKeys.BMS_REMAINING_CAPACITY_AH, {}).get("value")
                full_cap = data.get(StandardDataKeys.BMS_FULL_CAPACITY_AH, {}).get("value")
                if isinstance(rem_cap, (int, float)) and isinstance(full_cap, (int, float)):
                    capacity_str = f"{format_value(rem_cap, 1)}Ah / {format_value(full_cap, 1)}Ah"
                    y2 = self._add_std(y2, col2_start_x, layout, "Capacity", "", data, 0, val_override=capacity_str)

                min_temp = data.get(StandardDataKeys.BMS_TEMP_MIN_CELSIUS, {}).get("value")
                max_temp = data.get(StandardDataKeys.BMS_TEMP_MAX_CELSIUS, {}).get("value")
                if isinstance(min_temp, (int, float)) and isinstance(max_temp, (int, float)):
                    temps_str = f"{format_value(min_temp, 1)}°C / {format_value(max_temp, 1)}°C"
                    y2 = self._add_std(y2, col2_start_x, layout, "Temps(Min/Max)", "", data, 0, val_override=temps_str)

                y2 = self._add_std(y2, col2_start_x, layout, "Balancing", StandardDataKeys.BMS_CELLS_BALANCING_TEXT, data, 0)
                
                voltages = data.get(StandardDataKeys.BMS_CELL_VOLTAGES_LIST, {}).get("value")
                balancing_text = data.get(StandardDataKeys.BMS_CELLS_BALANCING_TEXT, {}).get("value", "")
                balancing_cells = set(re.findall(r'\d+', str(balancing_text)))

                # Get min/max voltage values for comparison
                min_v_val = data.get(StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS, {}).get("value")
                max_v_val = data.get(StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS, {}).get("value")

                if isinstance(voltages, list) and voltages:
                    y2 += 1
                    self._add_str_safe(y2, col2_start_x, f"{'Cell V':<{layout['label_width']}}: ", curses.A_BOLD)
                    y2 += 1
                    cells_per_row, col_width = 4, 10
                    for i, v in enumerate(voltages):
                        row, col = i // cells_per_row, i % cells_per_row
                        if col == 0 and i > 0:
                            y2 += 1
                        if y2 >= max_y - 1:
                            self._add_str_safe(y2, col2_start_x + col * col_width, "...")
                            break
                        
                        # Determine suffix for min/max cells
                        suffix = "  "
                        if isinstance(v, float):
                            # Use a small tolerance for float comparison
                            if isinstance(min_v_val, float) and abs(v - min_v_val) < 0.0001:
                                suffix = " ▼"
                            elif isinstance(max_v_val, float) and abs(v - max_v_val) < 0.0001:
                                suffix = " ▲"

                        cell_str = f" {format_value(v, 3)}V{suffix}"
                        attr = self._get_bms_color_attr(StandardDataKeys.BMS_CELL_VOLTAGES_LIST, v, background=True)
                        if str(i + 1) in balancing_cells:
                            attr |= curses.A_UNDERLINE
                        self._add_str_safe(y2, col2_start_x + col * col_width, cell_str, attr)
                        if col == (cells_per_row - 1) or i == (len(voltages) - 1):
                            self.stdscr.clrtoeol()

        # Grid & System Column
        col3_start_x = c3x
        if not has_inverter_data and not has_battery_data:
            col3_start_x = c1x
        elif not has_inverter_data or not has_battery_data:
            col3_start_x = c2x

        self._add_str_safe(y3 - 1, col3_start_x, "-- GRID & SYSTEM --", curses.A_BOLD)
        for key, label, prec, unit in [
            (StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS, "Grid Power", 0, "W"),
            (StandardDataKeys.GRID_L1_VOLTAGE_VOLTS, "Grid Volt", 1, "V"),
            (StandardDataKeys.LOAD_TOTAL_POWER_WATTS, "Load Power", 0, "W")
        ]:
            y3 = self._add_std(y3, col3_start_x, layout, label, key, data, prec, unit)

        y3 += 1
        self._add_str_safe(y3, col3_start_x, "-- PLUGINS --", curses.A_BOLD)
        y3 += 1
        for name in self.app_state.configured_plugin_instance_names:
            status_key = f"{name}_{StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS}"
            y3 = self._add_std(y3, col3_start_x, layout, name, status_key, data)

        y3 += 1
        self._add_str_safe(y3, col3_start_x, "-- SERVICES --", curses.A_BOLD)
        y3 += 1
        for label, val_override in [
            ("MQTT", self.app_state.mqtt_last_state or "disabled"),
            ("Web Clients", f"active ({self.app_state.web_clients_connected})" if self.app_state.web_clients_connected > 0 else "inactive"),
            ("Tuya Fan", self.app_state.tuya_last_known_state)
        ]:
            y3 = self._add_std(y3, col3_start_x, layout, label, "", data, val_override=val_override)

        return max(y1, y2, y3)

    def _draw_header(self, data: Dict, cols: int) -> None:
        """Draws the dashboard header."""
        status_dict = data.get(StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS, {})
        link_stat = status_dict.get("value", STATUS_DISCONNECTED)
        now = datetime.now(self.app_state.local_tzinfo).strftime('%Y-%m-%d %H:%M:%S %Z')
        
        # Check if update is available and add to header
        if self.app_state.update_available and self.app_state.latest_version:
            header_text = f"Solar Monitoring v{self.app_state.version} [UPDATE v{self.app_state.latest_version} AVAILABLE] - {now} - Link: "
        else:
            header_text = f"Solar Monitoring v{self.app_state.version} - {now} - Link: "
            
        self._add_str_safe(0, (cols - len(header_text) - len(str(link_stat))) // 2, header_text, curses.A_BOLD)
        self._add_str_safe(0, (cols - len(header_text) - len(str(link_stat))) // 2 + len(header_text), str(link_stat).upper(), self._get_color_attr(link_stat))
        self._add_str_safe(1, 0, "=" * cols, curses.A_BOLD)

    def _draw_faults(self, data: Dict, start_y: int, rows: int, cols: int) -> None:
        """Draws alerts and faults section."""
        if start_y >= rows - 2:
            return
        self._add_str_safe(start_y, 0, "-" * cols, curses.A_BOLD)
        y = start_y + 1
        self._add_str_safe(y, 1, "Alerts:", curses.A_BOLD | curses.A_UNDERLINE)
        
        alerts = data.get(StandardDataKeys.OPERATIONAL_CATEGORIZED_ALERTS_DICT, {}).get("value", {})
        has_alerts = alerts and any(alerts.values())

        if not has_alerts:
            status_dict = data.get(StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT, {})
            status = status_dict.get("value", "Normal")
            self._add_str_safe(y, 10, str(status), self._get_color_attr(status))
            return

        x = 10
        for category in self.app_state.alert_categories_display_order:
            messages = alerts.get(category)
            if not messages:
                continue
            cat_str = f"[{category.upper()}]: "
            self._add_str_safe(y, x, cat_str, curses.A_BOLD)
            x += len(cat_str)
            for i, msg in enumerate(messages):
                msg_str = f"{msg}, " if i < len(messages) - 1 else str(msg)
                if x + len(msg_str) > cols - 2:
                    y += 1
                    x = 10
                    if y >= rows - 1:
                        self._add_str_safe(y, x, "...", self._get_color_attr("fault"))
                        return
                self._add_str_safe(y, x, msg_str, self._get_color_attr("fault"))
                x += len(msg_str)
            x += 2

    def _draw_screen(self, data: Dict, layout: Dict) -> None:
        """Draws the entire dashboard screen."""
        if not self.stdscr:
            return
        self.stdscr.erase()
        rows, cols = self.stdscr.getmaxyx()
        
        if cols < 120:
            self._add_str_safe(rows // 2, 1, f"Terminal too narrow ({cols} < 120)")
        else:
            col1_x, col2_x, col3_x = 1, 40, 80
            self._draw_header(data, cols)
            self._add_str_safe(2, 0, "-" * cols)
            max_y = self._draw_data_cols(data, layout, rows, col1_x, col2_x, col3_x)
            self._draw_faults(data, max_y + 1, rows, cols)
        
        self.stdscr.refresh()