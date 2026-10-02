# test_plugins/test_display_api.py
"""Unit tests for compact display API helpers."""
import threading
import time
import unittest
from datetime import timezone
from unittest.mock import patch

from core.app_state import AppState
from plugins.plugin_interface import StandardDataKeys
import services.display_api as display_api
from services.display_api import build_display_payload, derive_grid_state


def _wrap(value):
    return {"value": value}


class TestDisplayApi(unittest.TestCase):
    def setUp(self):
        self.app = AppState("9.9.9-test")
        self.app.local_tzinfo = timezone.utc
        self.app.system_title = "Farm Solar"

    def test_grid_offline_from_status(self):
        packet = {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: _wrap("Grid Off"),
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: _wrap(0),
        }
        state, label = derive_grid_state(packet)
        self.assertEqual(state, "offline")
        self.assertEqual(label, "Offline")

    def test_grid_brownout(self):
        packet = {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: _wrap("Grid Undervoltage"),
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: _wrap(-100),
        }
        state, label = derive_grid_state(packet)
        self.assertEqual(state, "brownout")

    def test_grid_export_import(self):
        self.assertEqual(
            derive_grid_state(
                {
                    StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: _wrap("Generating"),
                    StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: _wrap(500),
                }
            )[0],
            "export",
        )
        self.assertEqual(
            derive_grid_state(
                {
                    StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: _wrap("Generating"),
                    StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: _wrap(-500),
                }
            )[0],
            "import",
        )

    def test_display_payload_title_and_fields(self):
        packet = {
            StandardDataKeys.SERVER_TIMESTAMP_MS_UTC: _wrap(int(time.time() * 1000)),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: _wrap(77.5),
            StandardDataKeys.BATTERY_POWER_WATTS: _wrap(-800),
            StandardDataKeys.BATTERY_STATUS_TEXT: _wrap("Charging"),
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: _wrap(2200),
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: _wrap(900),
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: _wrap(100),
            StandardDataKeys.ENERGY_PV_DAILY_KWH: _wrap(12.3),
            StandardDataKeys.ENERGY_LOAD_DAILY_KWH: _wrap(8.1),
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: _wrap("Generating"),
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: _wrap(48.5),
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: _wrap(31.2),
        }
        self.app.shared_data = packet
        payload = build_display_payload(self.app, packet)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["app"], "solar-monitoring")
        self.assertEqual(payload["title"], "Farm Solar")
        self.assertEqual(payload["soc"], 77.5)
        self.assertEqual(payload["battery_charge_state"], "charging")
        self.assertEqual(payload["grid_state"], "export")
        self.assertEqual(payload["inv_temp_c"], 48.5)
        self.assertEqual(payload["batt_temp_c"], 31.2)
        self.assertIsInstance(payload["pv_w"], float)
        self.assertIn("clock", payload)
        self.assertIn("timezone", payload)
        self.assertIn("tz_offset_sec", payload)
        self.assertIsNone(payload["weather"])

    def test_battery_charge_state_prefers_plugin_enum(self):
        packet = {
            StandardDataKeys.SERVER_TIMESTAMP_MS_UTC: _wrap(int(time.time() * 1000)),
            StandardDataKeys.BATTERY_POWER_WATTS: _wrap(200),
            StandardDataKeys.BATTERY_STATUS_TEXT: _wrap("Idle"),
            StandardDataKeys.BATTERY_CHARGE_STATE: _wrap("floating"),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: _wrap(90.0),
        }
        payload = build_display_payload(self.app, packet)
        self.assertEqual(payload["battery_charge_state"], "floating")

    def test_battery_charge_state_from_status_text(self):
        packet = {
            StandardDataKeys.SERVER_TIMESTAMP_MS_UTC: _wrap(int(time.time() * 1000)),
            StandardDataKeys.BATTERY_POWER_WATTS: _wrap(-40),
            StandardDataKeys.BATTERY_STATUS_TEXT: _wrap("Floating"),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: _wrap(95.0),
        }
        payload = build_display_payload(self.app, packet)
        self.assertEqual(payload["battery_charge_state"], "floating")

    def test_display_payload_weather_disabled(self):
        self.app.enable_weather_widget = False
        packet = {
            StandardDataKeys.SERVER_TIMESTAMP_MS_UTC: _wrap(int(time.time() * 1000)),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: _wrap(50.0),
        }
        payload = build_display_payload(self.app, packet)
        self.assertIsNone(payload["weather"])

    def test_weather_refresh_does_not_block_display_payload(self):
        with display_api._weather_lock:
            display_api._weather_cache.update(
                {
                    "fetched_at": 0.0,
                    "retry_after": 0.0,
                    "payload": None,
                    "inflight": False,
                    "worker": None,
                }
            )
        self.app.enable_weather_widget = True
        caller = threading.get_ident()
        callers = []

        def fail_open(*_args, **_kwargs):
            callers.append(threading.get_ident())
            raise OSError("offline")

        packet = {
            StandardDataKeys.SERVER_TIMESTAMP_MS_UTC: _wrap(int(time.time() * 1000)),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: _wrap(50.0),
        }
        with patch("services.display_api.urllib.request.urlopen", side_effect=fail_open):
            started = time.perf_counter()
            payload = build_display_payload(self.app, packet)
            elapsed = time.perf_counter() - started
            deadline = time.time() + 2
            while time.time() < deadline and not callers:
                time.sleep(0.01)
        self.assertLess(elapsed, 0.5)
        self.assertIsNone(payload["weather"])
        self.assertTrue(callers)
        self.assertNotEqual(callers[0], caller)


if __name__ == "__main__":
    unittest.main()
