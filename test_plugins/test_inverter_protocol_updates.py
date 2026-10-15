"""Checks for the 2025-2026 inverter map and parser fixes."""
import logging
import unittest

from plugins.inverter.voltronic_pi_constants import parse_qpigs, parse_qpigs2
from plugins.modbus_helper import decode_int32_le, decode_registers_by_map
from plugins.inverter.sungrow_modbus_constants import SUNGROW_PV, SUNGROW_HYBRID, SUNGROW_BATT_POWER
from plugins.inverter.growatt_modbus_constants import GROWATT_WIT_INPUT_REGISTERS


class VoltronicQpigsTests(unittest.TestCase):
    def test_older_qpigs_uses_field_14_as_discharge_current(self):
        raw = b"(230.0 50.0 230.0 50.0 1000 800 050 400 48.00 10 80 45 5.0 200.0 20\r"
        parsed = parse_qpigs(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["pv_power"], 1000.0)
        self.assertAlmostEqual(parsed["battery_current"], 10.0)
        self.assertAlmostEqual(parsed["battery_power"], 480.0)

    def test_max_qpigs_does_not_treat_scc_voltage_as_amps(self):
        raw = b"(230.0 50.0 230.0 50.0 1000 800 050 400 48.00 10 80 45 2.0 180.0 52.00 5 00010000 00 00 400\r"
        parsed = parse_qpigs(raw)
        self.assertEqual(parsed["pv_power"], 400.0)
        self.assertAlmostEqual(parsed["battery_current"], -5.0)
        self.assertAlmostEqual(parsed["battery_power"], -240.0)

    def test_qpigs2_pv2_and_nak(self):
        parsed = parse_qpigs2(b"(12.5 360.0 4500\r")
        self.assertEqual(parsed["pv2_power"], 4500.0)
        self.assertIsNone(parse_qpigs2(b"(NAK\r"))
        self.assertIsNone(parse_qpigs2(b"(NOA\r"))


class DeyeDecodeTests(unittest.TestCase):
    def setUp(self):
        try:
            from plugins.inverter.deye_sunsynk_plugin import DeyeSunsynkPlugin
        except ImportError as exc:
            self.skipTest(f"pymodbus required to import Deye plugin: {exc}")
        self.plugin_cls = DeyeSunsynkPlugin

    def test_legacy_energy_is_low_word_first(self):
        value, _unit = self.plugin_cls._plugin_decode_register(
            [0x0010, 0x0001],
            {"type": "uint32_le", "scale": 0.1, "key": "total_energy"},
            logging.getLogger("test"),
        )
        self.assertAlmostEqual(value, 6555.2)

    def test_three_phase_signed_power(self):
        value, _unit = self.plugin_cls._plugin_decode_register(
            [0xFFFF, 0xFFFF],
            {"type": "int32_le", "key": "grid_power"},
            logging.getLogger("test"),
        )
        self.assertEqual(value, -1.0)

    def test_sg05_alias_selects_legacy_map(self):
        plugin = self.plugin_cls(
            "deye_test",
            {"deye_model_series": "sg05lp1", "connection_type": "tcp", "tcp_host": "127.0.0.1"},
            logging.getLogger("test"),
        )
        self.assertEqual(plugin.model_series, "legacy_hybrid")
        self.assertEqual(plugin.registers_map["total_energy"]["type"], "uint32_le")
        self.assertEqual(plugin._plugin_get_register_count("int32_le", logging.getLogger("test")), 2)


class SungrowAddressTests(unittest.TestCase):
    def test_hybrid_pdu_addresses_and_word_order(self):
        self.assertEqual(SUNGROW_PV["pv_total_power"]["addr"], 5016)
        self.assertEqual(SUNGROW_PV["grid_frequency_string"]["addr"], 5035)
        self.assertEqual(SUNGROW_HYBRID["battery_voltage"]["addr"], 13019)
        self.assertEqual(SUNGROW_HYBRID["battery_soc"]["scale"], 0.1)
        self.assertEqual(SUNGROW_BATT_POWER["battery_power"]["addr"], 5213)
        self.assertEqual(SUNGROW_BATT_POWER["grid_frequency"]["scale"], 0.01)
        # low word 100, high word 0 -> 100 W discharge; high word 0xFFFF -> negative
        self.assertEqual(decode_int32_le([100, 0], 0), 100)
        decoded = decode_registers_by_map(
            [0xFFFF, 0xFFFF],
            {"battery_power": {"addr": 5213, "type": "int32_le"}},
            5213,
        )
        self.assertEqual(decoded["battery_power"], -1)


class GrowattWitTests(unittest.TestCase):
    def test_wit_battery_power_is_signed_and_preferred(self):
        try:
            from plugins.inverter.growatt_modbus_plugin import GrowattModbusPlugin
            plugin = GrowattModbusPlugin(
            "growatt_test",
            {"connection_type": "tcp", "tcp_host": "127.0.0.1", "growatt_family": "wit"},
            logging.getLogger("test"),
        )
        except ImportError as exc:
            self.skipTest(f"pymodbus required to import Growatt plugin: {exc}")
        self.assertEqual(plugin._storage_kind, "wit")
        # -100 raw (0xFFFFFF9C) is high word 0xFFFF, low word 0xFF9C. Scale 0.1 -> -10 W.
        decoded = plugin._decode_registers_from_dict(
            {8091: 0xFFFF, 8092: 0xFF9C, 8093: 80, 8034: 480, 8035: 0xFF9C},
            GROWATT_WIT_INPUT_REGISTERS,
        )
        self.assertAlmostEqual(decoded["battery_power"], -10.0)
        standardized = plugin._standardize_operational_data(decoded)
        from plugins.plugin_interface import StandardDataKeys
        self.assertAlmostEqual(standardized[StandardDataKeys.BATTERY_POWER_WATTS], -10.0)
        self.assertEqual(standardized[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT], 80)


if __name__ == "__main__":
    unittest.main()
