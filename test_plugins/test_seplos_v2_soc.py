"""Offline decode tests for Seplos V2 SOC vs remaining capacity.

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

from plugins.battery.seplos_bms_v2_plugin import SeplosBMSV2
from plugins.plugin_interface import StandardDataKeys


def _u8(n: int) -> str:
    return f"{n & 0xFF:02X}"


def _u16(n: int) -> str:
    return f"{n & 0xFFFF:04X}"


def _telemetry_frame(soc_raw: int, residual_raw: int, cell_mv: int = 3200, full_raw: int = 29990) -> bytes:
    """Build a 16-cell / 6-temp Seplos 0x42 INFO payload (150 ASCII hex chars)."""
    parts = ["0000", _u8(16)]
    parts.extend(_u16(cell_mv) for _ in range(16))
    parts.append(_u8(6))
    # 25.0 C -> (raw - 2731) * 0.1
    parts.extend(_u16(2981) for _ in range(6))
    parts.append(_u16(0))       # current
    parts.append(_u16(5120))    # pack voltage 51.20 V
    parts.append(_u16(residual_raw))
    parts.append(_u8(10))       # customize info
    parts.append(_u16(full_raw))
    parts.append(_u16(soc_raw))
    parts.append(_u16(30000))   # rated capacity
    parts.append(_u16(100))     # cycles
    parts.append(_u16(1000))    # SOH 100.0%
    parts.append(_u16(5120))    # port voltage
    payload = "".join(parts)
    payload += "00" * ((150 - len(payload)) // 2)
    assert len(payload) == 150, len(payload)
    return payload.encode("ascii")


class SeplosV2SocFallbackTests(unittest.TestCase):
    def setUp(self):
        self.plugin = SeplosBMSV2(
            "test",
            {"seplos_connection_type": "serial", "seplos_serial_port": "COM_TEST"},
            logging.getLogger("seplos_v2_soc_test"),
        )

    def test_zero_soc_uses_capacity_when_cells_are_not_empty(self):
        decoded = self.plugin._decode_telemetry_payload(
            _telemetry_frame(soc_raw=0, residual_raw=10140)
        )
        self.assertEqual(decoded[StandardDataKeys.BMS_REMAINING_CAPACITY_AH]["value"], 101.4)
        self.assertEqual(decoded[StandardDataKeys.BMS_FULL_CAPACITY_AH]["value"], 299.9)
        self.assertEqual(decoded[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT]["value"], 33.8)
        self.assertEqual(decoded[StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT]["value"], 100.0)

    def test_matching_soc_is_left_alone(self):
        decoded = self.plugin._decode_telemetry_payload(
            _telemetry_frame(soc_raw=338, residual_raw=10140)
        )
        self.assertEqual(decoded[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT]["value"], 33.8)

    def test_higher_reported_soc_is_not_replaced(self):
        decoded = self.plugin._decode_telemetry_payload(
            _telemetry_frame(soc_raw=800, residual_raw=10140)
        )
        self.assertEqual(decoded[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT]["value"], 80.0)

    def test_empty_pack_keeps_reported_zero(self):
        decoded = self.plugin._decode_telemetry_payload(
            _telemetry_frame(soc_raw=0, residual_raw=0, cell_mv=2900)
        )
        self.assertEqual(decoded[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT]["value"], 0.0)

    def test_low_cell_voltage_keeps_reported_zero_even_if_capacity_disagrees(self):
        decoded = self.plugin._decode_telemetry_payload(
            _telemetry_frame(soc_raw=0, residual_raw=10140, cell_mv=2900)
        )
        self.assertEqual(decoded[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT]["value"], 0.0)


if __name__ == "__main__":
    unittest.main()
