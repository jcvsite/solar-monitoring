# test_plugins/test_modbus_helper_compat.py
"""Unit tests for pymodbus API compatibility helper.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from plugins.modbus_helper import _call_with_slave_compat


class TestCallWithSlaveCompat(unittest.TestCase):
    def test_pymodbus_311_device_id_keyword_count(self):
        """pymodbus >=3.11: address positional; count/device_id keyword-only."""
        calls = []

        def read_input_registers(address, *, count=1, device_id=1):
            calls.append((address, count, device_id))
            return "ok311"

        result = _call_with_slave_compat(read_input_registers, 33000, 40, slave=1)
        self.assertEqual(result, "ok311")
        self.assertEqual(calls, [(33000, 40, 1)])

    def test_pymodbus_36_positional_unit(self):
        """Older pymodbus: address, count positional; unit= keyword."""
        calls = []

        def read_input_registers(address, count, unit=1):
            calls.append((address, count, unit))
            return "ok36"

        result = _call_with_slave_compat(read_input_registers, 33000, 40, slave=7)
        self.assertEqual(result, "ok36")
        self.assertEqual(calls, [(33000, 40, 7)])

    def test_mid_slave_keyword_count(self):
        def read_input_registers(address, *, count=1, slave=1):
            return (address, count, slave)

        self.assertEqual(_call_with_slave_compat(read_input_registers, 10, 5, slave=3), (10, 5, 3))


if __name__ == "__main__":
    unittest.main()
