# test_plugins/test_display_config.py
"""Tests for display_config.json management and validation."""
import json
import os
import tempfile
import unittest

from services.display_config import (
    DEFAULT_DISPLAY_CONFIG,
    LAYOUT_CATALOG,
    THEME_CATALOG,
    check_settings_pin_for_write,
    load_display_config,
    save_display_config,
    settings_pin_is_set,
    validate_display_config,
    verify_settings_pin,
)


class TestDisplayConfig(unittest.TestCase):
    def test_validate_defaults(self):
        cfg = validate_display_config({})
        self.assertEqual(cfg["glance_layout"], 0)
        self.assertEqual(cfg["theme"], 0)
        self.assertTrue(cfg["grid_offline_alert"])

    def test_validate_clamps(self):
        cfg = validate_display_config({
            "glance_layout": 99,
            "theme": -1,
            "rotation": 5,
            "brightness": 300,
        })
        self.assertEqual(cfg["glance_layout"], 4)
        self.assertEqual(cfg["theme"], 0)
        self.assertEqual(cfg["rotation"], 3)
        self.assertEqual(cfg["brightness"], 255)

    def test_auto_install_forces_check(self):
        cfg = validate_display_config({"auto_install_update": True, "check_for_update": False})
        self.assertTrue(cfg["check_for_update"])
        self.assertTrue(cfg["auto_install_update"])

    def test_settings_pin_validation(self):
        cfg = validate_display_config({"settings_pin": "1234"})
        self.assertEqual(cfg["settings_pin"], "1234")
        cfg = validate_display_config({"settings_pin": "12ab"})
        self.assertEqual(cfg["settings_pin"], "")
        self.assertFalse(settings_pin_is_set(cfg))
        cfg = validate_display_config({"settings_pin": "9999"})
        self.assertTrue(settings_pin_is_set(cfg))
        self.assertTrue(verify_settings_pin(cfg, "9999"))
        self.assertFalse(verify_settings_pin(cfg, "0000"))

    def test_pin_required_for_write(self):
        current = validate_display_config({"settings_pin": "4242"})
        self.assertEqual(check_settings_pin_for_write(current, {}), "Invalid PIN")
        self.assertIsNone(check_settings_pin_for_write(current, {"pin": "4242"}))

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "display_config.json")
            saved = save_display_config({"theme": 2, "glance_layout": 3}, project_root=tmp)
            self.assertEqual(saved["theme"], 2)
            self.assertEqual(saved["glance_layout"], 3)
            self.assertGreater(saved["config_rev"], DEFAULT_DISPLAY_CONFIG["config_rev"])
            loaded = load_display_config(tmp)
            self.assertEqual(loaded["theme"], 2)
            self.assertEqual(loaded["glance_layout"], 3)

    def test_catalog_sizes(self):
        self.assertEqual(len(LAYOUT_CATALOG), 5)
        self.assertEqual(len(THEME_CATALOG), 5)


if __name__ == "__main__":
    unittest.main()
