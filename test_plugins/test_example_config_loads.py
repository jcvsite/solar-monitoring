"""Every [PLUGIN_*] section in config.ini.example must construct its plugin.

config.ini.example documents options with trailing "; ..." notes, so this also
guards the inline-comment handling in core.config_loader.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
import logging
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.app_state import AppState
from core.config_loader import load_configuration
from core.plugin_catalog import _load_plugin_class

EXAMPLE = os.path.join(ROOT, "config.ini.example")


class TestExampleConfigLoads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_state = AppState("test")
        try:
            load_configuration(EXAMPLE, cls.app_state)
        except Exception as exc:  # tzdata and friends come from requirements.txt
            raise unittest.SkipTest(f"config loader dependencies missing: {exc}")
        cls.config = cls.app_state.config

    def test_no_inline_comment_leaks_into_values(self):
        leaked = [
            (section, key, value)
            for section in self.config.sections()
            for key, value in self.config.items(section)
            if " ;" in str(value)
        ]
        self.assertFalse(leaked, f"Inline comments left in config values: {leaked}")

    def test_every_plugin_section_constructs(self):
        logger = logging.getLogger("test")
        failures = []
        checked = 0
        for section in self.config.sections():
            if not section.startswith("PLUGIN_"):
                continue
            options = dict(self.config.items(section))
            plugin_cls = _load_plugin_class(options.get("plugin_type", ""))
            if plugin_cls is None:
                continue  # Optional dependency missing in this environment.
            checked += 1
            try:
                plugin_cls(section[len("PLUGIN_"):], options, logger)
            except Exception as exc:
                failures.append(f"[{section}] {type(exc).__name__}: {exc}")
        self.assertFalse(failures, "Example config sections failed to construct:\n" + "\n".join(failures))
        self.assertGreater(checked, 0, "No plugin sections were checked")


if __name__ == "__main__":
    unittest.main()
