# test_plugins/test_capture_replay.py
"""Golden capture / offline replay tests (no hardware).

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.bms_aggregator import aggregate_capacity_weighted
from core.data_sanitizer import sanitize_plugin_data
from plugins.plugin_interface import StandardDataKeys
from plugins.battery.jk_bms_decoder import jk_crc8, decode_jk02_cell_info, PROTOCOL_JK02_24S
from plugins.inverter.deye_sunsynk_plugin_constants import STATUS_CODES


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_json(name: str):
    with open(os.path.join(FIXTURES, name), encoding="utf-8-sig") as f:
        return json.load(f)


def _build_minimal_jk02_24s_frame(soc: int = 55, cell_mv: int = 3300, current_ma: int = -1500) -> bytes:
    data = bytearray(180)
    data[0:4] = bytes([0x55, 0xAA, 0xEB, 0x90])
    data[4] = 0x02
    data[5] = 0x01
    for i in range(16):
        data[6 + i * 2] = cell_mv & 0xFF
        data[6 + i * 2 + 1] = (cell_mv >> 8) & 0xFF
    offset = 0
    total_mv = cell_mv * 16
    for i, b in enumerate(total_mv.to_bytes(4, "little")):
        data[118 + offset + i] = b
    cur = current_ma & 0xFFFFFFFF
    for i in range(4):
        data[126 + offset + i] = (cur >> (8 * i)) & 0xFF
    data[130 + offset] = 0xFA
    data[131 + offset] = 0x00
    data[132 + offset] = 0xFA
    data[133 + offset] = 0x00
    data[141 + offset] = soc & 0xFF
    rem = int(100 * 1000)
    full = int(200 * 1000)
    for i in range(4):
        data[142 + offset + i] = (rem >> (8 * i)) & 0xFF
        data[146 + offset + i] = (full >> (8 * i)) & 0xFF
    data[166 + offset] = 1
    data[167 + offset] = 1
    data[-1] = jk_crc8(bytes(data[:-1]))
    return bytes(data)


class TestCaptureReplay(unittest.TestCase):
    def test_solis_status_decode_error_sanitized(self):
        dirty = _load_json("solis_status_decode_error.json")
        clean = sanitize_plugin_data(dirty, "INV_Solis")
        status = clean[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT]
        self.assertIsInstance(status, str)
        self.assertNotIsInstance(status, dict)
        self.assertIsNone(clean[StandardDataKeys.PV_TOTAL_DC_POWER_WATTS])

    def test_jk02_crc_frame_replay(self):
        frame = _build_minimal_jk02_24s_frame(soc=62, cell_mv=3310)
        decoded = decode_jk02_cell_info(frame, PROTOCOL_JK02_24S)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.get("soc"), 62)

    def test_deye_status_code_map(self):
        # Regression: STATUS_CODES must be int->str, never used as status text directly
        self.assertIsInstance(STATUS_CODES, dict)
        sample = STATUS_CODES.get(0) or STATUS_CODES.get(1) or next(iter(STATUS_CODES.values()))
        self.assertIsInstance(sample, str)
        fixture = _load_json("deye_status_regression.json")
        code = fixture["status_code"]
        text = STATUS_CODES.get(code, f"Unknown ({code})")
        self.assertEqual(text, fixture["expected_status_text"])

    def test_multi_bms_capacity_weighted(self):
        packs = _load_json("multi_bms_two_packs.json")["packs"]
        agg = aggregate_capacity_weighted(packs)
        # Pack A 100Ah @ 80%, Pack B 200Ah @ 50% => (80*100 + 50*200) / 300 = 60
        self.assertAlmostEqual(agg[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT], 60.0, places=2)
        self.assertAlmostEqual(agg[StandardDataKeys.BATTERY_POWER_WATTS], packs[0]["power"] + packs[1]["power"], places=2)
        self.assertAlmostEqual(agg[StandardDataKeys.BMS_FULL_CAPACITY_AH], 300.0, places=2)
        self.assertEqual(agg["bms_pack_count"], 2)


if __name__ == "__main__":
    unittest.main()
