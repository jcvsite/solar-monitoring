"""Decode checks for the EG4 V58 register map.

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

from plugins.inverter.eg4_modbus_constants import EG4_INPUT_REGISTERS


class TestEg4Decode(unittest.TestCase):
    def setUp(self):
        try:
            from plugins.inverter.eg4_modbus_plugin import Eg4ModbusPlugin
            self.plugin = Eg4ModbusPlugin(
                "eg4_test",
                {"connection_type": "tcp", "tcp_host": "127.0.0.1"},
                logging.getLogger("test"),
            )
        except ImportError as exc:
            self.skipTest(f"pymodbus required for EG4 plugin: {exc}")

    def _decode(self, regs):
        return self.plugin._decode_registers(regs, EG4_INPUT_REGISTERS)

    def test_soc_and_soh_share_register_5_as_separate_bytes(self):
        # Low byte 80 is SOC, high byte 100 is SOH.
        decoded = self._decode({5: (100 << 8) | 80})
        self.assertEqual(decoded["battery_soc"], 80)
        self.assertEqual(decoded["battery_soh"], 100)

    def test_uint16_is_not_byte_swapped(self):
        decoded = self._decode({4: 512})
        self.assertAlmostEqual(decoded["battery_voltage"], 51.2)

    def test_int16_temperature_is_signed(self):
        decoded = self._decode({64: 0xFFFF})
        self.assertAlmostEqual(decoded["inverter_temperature"], -0.1)

    def test_uint32_is_low_word_first(self):
        # total_pv1_energy at 40, scale 0.1: raw 0x00010000 -> 65536 -> 6553.6 kWh
        decoded = self._decode({40: 0x0000, 41: 0x0001})
        self.assertAlmostEqual(decoded["total_pv1_energy"], 6553.6)

    def test_string_serial_is_not_scaled(self):
        # serial_number at 115, len 5 ASCII registers.
        raw = b"EG4TEST123"
        regs = {115 + i: (raw[2 * i] << 8) | raw[2 * i + 1] for i in range(5)}
        decoded = self._decode(regs)
        self.assertEqual(decoded["serial_number"], "EG4TEST123")


if __name__ == "__main__":
    unittest.main()
