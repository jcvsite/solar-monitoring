"""SOC jump filter must not latch a bad value forever.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from plugins.plugin_interface import StandardDataKeys
from services.data_filter_service import DataFilterService, FilterConfig

SOC = StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT


class _State:
    battery_max_charge_power_w = 3000.0
    battery_usable_capacity_kwh = 15.0
    poll_interval = 15


class SocJumpFilterTests(unittest.TestCase):
    def setUp(self):
        self.filt = DataFilterService(_State(), FilterConfig())

    def _apply(self, soc, last):
        current = {SOC: soc}
        previous = {} if last is None else {SOC: last}
        return self.filt.apply_all_filters(current, previous)[SOC]

    def test_stable_jump_is_accepted_after_confirmation(self):
        self.assertEqual(self._apply(95.9, 0.0), 0.0)
        self.assertEqual(self._apply(95.9, 0.0), 0.0)
        self.assertEqual(self._apply(95.9, 0.0), 95.9)

    def test_one_sample_glitch_does_not_replace_soc(self):
        self.assertEqual(self._apply(95.9, 40.0), 40.0)
        self.assertEqual(self._apply(40.2, 40.0), 40.2)

    def test_small_change_is_accepted_immediately(self):
        self.assertEqual(self._apply(50.4, 50.0), 50.4)
        self.assertIsNone(self.filt._soc_jump_pending)


if __name__ == "__main__":
    unittest.main()
