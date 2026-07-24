# test_plugins/test_data_sanitizer_and_jk_decoder.py
"""Offline tests for data sanitizer and JK BMS JK02 decoder.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.data_sanitizer import (
    is_successful_dynamic_read,
    sanitize_plugin_data,
)
from plugins.plugin_interface import StandardDataKeys
from plugins.battery.jk_bms_decoder import jk_crc8, decode_jk02_cell_info, PROTOCOL_JK02_24S


def _build_minimal_jk02_24s_frame(soc: int = 55, cell_mv: int = 3300, current_ma: int = -1500) -> bytes:
    """Build a synthetic JK02 24S frame with valid CRC for decoder unit tests."""
    # Frame long enough for 24S offsets (need ~170+ bytes before CRC)
    data = bytearray(180)
    data[0:4] = bytes([0x55, 0xAA, 0xEB, 0x90])
    data[4] = 0x02
    data[5] = 0x01
    # 16 cells at offset 6
    for i in range(16):
        mv = cell_mv
        data[6 + i * 2] = mv & 0xFF
        data[6 + i * 2 + 1] = (mv >> 8) & 0xFF
    offset = 0  # 24S
    # total voltage 32-bit mV at 118
    total_mv = cell_mv * 16
    for i, b in enumerate(total_mv.to_bytes(4, "little")):
        data[118 + offset + i] = b
    # current int32 mA at 126 (JK charge-positive)
    cur = current_ma & 0xFFFFFFFF
    for i in range(4):
        data[126 + offset + i] = (cur >> (8 * i)) & 0xFF
    # temps
    data[130 + offset] = 0xFA  # 250 -> 25.0C little endian? 250 = 0x00FA
    data[131 + offset] = 0x00
    data[132 + offset] = 0xFA
    data[133 + offset] = 0x00
    data[141 + offset] = soc & 0xFF
    # remaining/full capacity
    rem = int(100 * 1000)
    full = int(200 * 1000)
    for i in range(4):
        data[142 + offset + i] = (rem >> (8 * i)) & 0xFF
        data[146 + offset + i] = (full >> (8 * i)) & 0xFF
    data[166 + offset] = 1
    data[167 + offset] = 1
    crc = jk_crc8(bytes(data[:-1]))
    data[-1] = crc
    return bytes(data)


class TestDataSanitizer(unittest.TestCase):
    def test_empty_dict_is_failure(self):
        self.assertFalse(is_successful_dynamic_read({}))
        self.assertFalse(is_successful_dynamic_read(None))
        self.assertTrue(is_successful_dynamic_read({"a": 1}))

    def test_status_dict_never_passes_through(self):
        dirty = {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: {0: "Stand-by", 1: "Normal"},
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: 88.5,
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: "decode_error",
        }
        clean = sanitize_plugin_data(dirty, "test")
        self.assertIsInstance(clean[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT], str)
        self.assertTrue(clean[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT].startswith("Unknown"))
        self.assertIsNone(clean[StandardDataKeys.PV_TOTAL_DC_POWER_WATTS])
        self.assertEqual(clean[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT], 88.5)

    def test_soc_clamped(self):
        clean = sanitize_plugin_data({StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: 150}, "t")
        self.assertEqual(clean[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT], 100.0)


class TestJkDecoder(unittest.TestCase):
    def test_decode_synthetic_frame(self):
        frame = _build_minimal_jk02_24s_frame(soc=64, cell_mv=3300, current_ma=2000)
        decoded = decode_jk02_cell_info(frame, PROTOCOL_JK02_24S)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["soc"], 64)
        self.assertGreaterEqual(decoded["cell_count"], 1)
        # JK +2A charge => app convention -2A (charging)
        self.assertAlmostEqual(decoded["current"], -2.0, places=2)


if __name__ == "__main__":
    unittest.main()
