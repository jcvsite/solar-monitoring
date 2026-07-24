# test_plugins/test_ha_discovery_coverage.py
"""Ensure flow-board energy/power/SOC keys have HA MQTT discovery definitions.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from unittest.mock import MagicMock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# mqtt_service imports paho at module load; stub for offline CI.
sys.modules.setdefault("paho", MagicMock())
sys.modules.setdefault("paho.mqtt", MagicMock())
sys.modules.setdefault("paho.mqtt.client", MagicMock())

from plugins.plugin_interface import StandardDataKeys
from services.mqtt_service import MqttService


# Keys used by static/js/app.js flow-board power/energy/SOC path.
FLOW_BOARD_REQUIRED_KEYS = {
    StandardDataKeys.PV_TOTAL_DC_POWER_WATTS,
    StandardDataKeys.LOAD_TOTAL_POWER_WATTS,
    StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS,
    StandardDataKeys.BATTERY_POWER_WATTS,
    StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT,
    StandardDataKeys.ENERGY_PV_DAILY_KWH,
    StandardDataKeys.ENERGY_LOAD_DAILY_KWH,
    StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH,
    StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH,
    StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH,
    StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH,
    StandardDataKeys.AC_POWER_WATTS,
}


class TestHaDiscoveryCoverage(unittest.TestCase):
    def test_flow_board_keys_have_discovery(self):
        app_state = MagicMock()
        app_state.enable_mqtt = False
        svc = MqttService(app_state)
        defs = svc._get_ha_sensor_definitions()
        discovered = {d["key"] for d in defs}
        missing = sorted(FLOW_BOARD_REQUIRED_KEYS - discovered)
        self.assertFalse(missing, f"Missing HA discovery for flow-board keys: {missing}")

    def test_power_energy_soc_have_unit_and_device_class(self):
        app_state = MagicMock()
        app_state.enable_mqtt = False
        svc = MqttService(app_state)
        by_key = {}
        for d in svc._get_ha_sensor_definitions():
            by_key.setdefault(d["key"], d)
        for key in FLOW_BOARD_REQUIRED_KEYS:
            d = by_key[key]
            self.assertIn("unit", d, f"{key} missing unit")
            self.assertIn("device_class", d, f"{key} missing device_class")

    def test_app_js_sdk_keys_exist_in_config(self):
        app_js = os.path.join(ROOT, "static", "js", "app.js")
        config_js = os.path.join(ROOT, "static", "js", "config.js")
        with open(app_js, encoding="utf-8") as f:
            app_src = f.read()
        with open(config_js, encoding="utf-8") as f:
            cfg_src = f.read()
        used = set(re.findall(r"SDK\.([A-Z0-9_]+)", app_src))
        defined = set(re.findall(r"^\s*([A-Z0-9_]+)\s*:", cfg_src, flags=re.M))
        critical_sdk_names = {
            "PV_TOTAL_DC_POWER_WATTS",
            "LOAD_TOTAL_POWER_WATTS",
            "GRID_TOTAL_ACTIVE_POWER_WATTS",
            "BATTERY_POWER_WATTS",
            "BATTERY_STATE_OF_CHARGE_PERCENT",
            "ENERGY_PV_DAILY_KWH",
            "ENERGY_LOAD_DAILY_KWH",
            "ENERGY_GRID_DAILY_IMPORT_KWH",
            "ENERGY_GRID_DAILY_EXPORT_KWH",
            "ENERGY_BATTERY_DAILY_CHARGE_KWH",
            "ENERGY_BATTERY_DAILY_DISCHARGE_KWH",
        }
        missing_cfg = sorted(critical_sdk_names - defined)
        self.assertFalse(missing_cfg, f"SDK keys missing from config.js: {missing_cfg}")
        unused = sorted(critical_sdk_names - used)
        self.assertFalse(unused, f"Critical SDK keys unused in app.js: {unused}")


if __name__ == "__main__":
    unittest.main()
