# test_plugins/test_jbd_daly_decoders.py
"""Unit tests for JBD and Daly BMS frame decoders.

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from plugins.battery.jbd_bms_decoder import (
    build_read_cmd,
    find_frames,
    jbd_checksum,
    parse_basic_info,
    parse_cell_voltages,
)
from plugins.battery.daly_bms_decoder import (
    build_query,
    find_responses,
    parse_0x90,
    parse_0x93,
)
from plugins.battery.pylontech_bms_decoder import parse_pwr_line
from plugins.inverter.voltronic_pi_constants import build_command, crc16_xmodem, parse_qpigs


class TestJbdDecoder(unittest.TestCase):
    def test_build_read_cmd_ends_with_77(self):
        cmd = build_read_cmd(0x03)
        self.assertEqual(cmd[0], 0xDD)
        self.assertEqual(cmd[-1], 0x77)
        self.assertEqual(cmd[1], 0xA5)
        self.assertEqual(cmd[2], 0x03)

    def test_parse_basic_info(self):
        # Build synthetic 0x03 response with 27+ bytes data
        data = bytearray(27)
        # voltage 4800 -> 48.00V
        data[0], data[1] = 0x12, 0xC0
        # current -150 -> -1.50A (0xFF6A as s16)
        data[2], data[3] = 0xFF, 0x6A
        # remaining 10000 -> 100Ah
        data[4], data[5] = 0x27, 0x10
        # full 20000 -> 200Ah
        data[6], data[7] = 0x4E, 0x20
        # cycles 5
        data[8], data[9] = 0x00, 0x05
        data[16], data[17] = 0x00, 0x00  # protection
        data[19] = 88  # soc
        data[20] = 0x03  # both FETs
        data[21] = 4  # cells
        data[22] = 1  # ntc
        # temp 2981 -> 25.0C (298.1K)
        data[23], data[24] = 0x0B, 0xA5
        body = bytes([0x03, 0x00, len(data)]) + bytes(data)
        chk = jbd_checksum(body)
        frame = bytes([0xDD]) + body + bytes([(chk >> 8) & 0xFF, chk & 0xFF, 0x77])
        parsed = parse_basic_info(frame)
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed["voltage_v"], 48.0, places=1)
        self.assertEqual(parsed["soc"], 88.0)
        self.assertTrue(parsed["charge_fet"])
        self.assertTrue(parsed["discharge_fet"])

    def test_find_frames_and_cells(self):
        data = bytearray(8)
        data[0], data[1] = 0x0C, 0xE4  # 3300 mV
        data[2], data[3] = 0x0C, 0xE4
        body = bytes([0x04, 0x00, 4]) + bytes(data[:4])
        chk = jbd_checksum(body)
        frame = bytes([0xDD]) + body + bytes([(chk >> 8) & 0xFF, chk & 0xFF, 0x77])
        frames = find_frames(b"\x00" + frame + b"\xff")
        self.assertEqual(len(frames), 1)
        cells = parse_cell_voltages(frames[0])
        self.assertEqual(len(cells), 2)
        self.assertAlmostEqual(cells[0], 3.3, places=2)


class TestDalyDecoder(unittest.TestCase):
    def test_build_query_checksum(self):
        q = build_query(0x90)
        self.assertEqual(len(q), 13)
        self.assertEqual(q[0], 0xA5)
        self.assertEqual(q[2], 0x90)

    def test_parse_0x90(self):
        # voltage 480 -> 48.0V; current 30150 -> 15.0A; soc 885 -> 88.5%
        d = bytearray(8)
        d[0], d[1] = 0x01, 0xE0
        d[4], d[5] = 0x75, 0xC6  # 30150 → 15.0A
        d[6], d[7] = 0x03, 0x75  # 885
        frame = bytearray([0xA5, 0x01, 0x90, 0x08]) + d
        frame.append(sum(frame) & 0xFF)
        parsed = parse_0x90(bytes(frame))
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed["voltage_v"], 48.0, places=1)
        self.assertAlmostEqual(parsed["current_a"], 15.0, places=1)
        self.assertAlmostEqual(parsed["soc"], 88.5, places=1)
        found = find_responses(bytes(frame))
        self.assertEqual(len(found), 1)

    def test_parse_0x93(self):
        d = bytearray([1, 1, 0, 0, 0, 0, 0, 0])
        frame = bytearray([0xA5, 0x01, 0x93, 0x08]) + d
        frame.append(sum(frame) & 0xFF)
        parsed = parse_0x93(bytes(frame))
        self.assertTrue(parsed["charge_fet"])
        self.assertTrue(parsed["discharge_fet"])


class TestPylonAndVoltronic(unittest.TestCase):
    def test_pylon_pwr(self):
        text = "Power\nSOC: 72%\nVoltage: 49.6\nCurrent: -12.5\nTemperature: 28.0\n"
        p = parse_pwr_line(text)
        self.assertEqual(p["soc"], 72.0)
        self.assertAlmostEqual(p["voltage_v"], 49.6)
        self.assertAlmostEqual(p["current_a"], -12.5)

    def test_voltronic_qpigs(self):
        # Minimal QPIGS-like body
        fields = "230.0 50.0 230.0 50.0 0500 0400 013 400 48.0 00 080 0025 00.0 000.0 00.00"
        resp = ("(" + fields).encode("ascii")
        parsed = parse_qpigs(resp)
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed["grid_voltage"], 230.0)
        self.assertEqual(parsed["battery_soc"], 80.0)

    def test_voltronic_crc_stable(self):
        self.assertEqual(crc16_xmodem(b"QPI"), crc16_xmodem(b"QPI"))
        pkt = build_command("QPI")
        self.assertEqual(pkt[-1], 0x0D)
        self.assertTrue(pkt.startswith(b"QPI"))


if __name__ == "__main__":
    unittest.main()
