"""Plain-text console fallback when the curses module cannot load."""
import os
import sys
import unittest
from datetime import timezone
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from plugins.plugin_interface import StandardDataKeys
from services.curses_service import CursesService


class TestPlainConsole(unittest.TestCase):
    def test_status_text_includes_live_readings(self):
        svc = CursesService.__new__(CursesService)
        svc.app_state = SimpleNamespace(
            version="1.5.0",
            local_tzinfo=timezone.utc,
            system_title="Shed",
            update_available=False,
            latest_version=None,
            web_dashboard_port=8081,
            configured_plugin_instance_names=["INV"],
            mqtt_last_state="connected",
            web_clients_connected=0,
            tuya_last_known_state="off",
        )
        data = {
            StandardDataKeys.AC_POWER_WATTS: {"value": 1500},
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: {"value": 82.4},
            StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS: {"value": "connected"},
            "INV_" + StandardDataKeys.CORE_PLUGIN_CONNECTION_STATUS: {"value": "connected"},
            "INV_health_last_success_age_s": {"value": 3},
            "INV_health_consecutive_failures": {"value": 0},
        }
        text = svc._format_plain_status(data)
        self.assertIn("Shed v1.5.0", text)
        self.assertIn("1500 W", text)
        self.assertIn("82.4 %", text)
        self.assertIn("INV", text)
        self.assertIn("Plain console", text)


if __name__ == "__main__":
    unittest.main()
