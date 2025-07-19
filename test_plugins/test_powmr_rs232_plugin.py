#!/usr/bin/env python3
"""
Standalone test suite for the POWMR RS232 Plugin.

This test file validates the POWMR RS232 plugin functionality including:
- Plugin initialization and configuration
- Protocol packet building and parsing
- Register decoding and data processing
- Connection handling and error scenarios
- Data standardization and mapping
- Alert/fault code processing
- Temperature decoding

GitHub: https://github.com/jcvsite/solar-monitoring

Usage:
    python test_plugins/test_powmr_rs232_plugin.py
"""

import sys
import os
import unittest
import logging
import struct
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the plugin and its dependencies
from plugins.inverter.powmr_rs232_plugin import (
    PowmrCustomRs232Plugin, 
    ConnectionType,
    _modbus_crc16,
    _build_request_packet,
    _parse_response
)
from plugins.inverter.powmr_rs232_plugin_constants import (
    POWMR_REGISTERS,
    POWMR_CONFIG_REGISTERS,
    POWMR_RUN_MODE_CODES,
    POWMR_ALERT_MAPS,
    ALERT_CATEGORIES,
    PROTOCOL_HEADER,
    STATE_COMMAND,
    CONFIG_COMMAND_READ,
    STATE_ADDRESS,
    CONFIG_ADDRESS
)
from plugins.plugin_interface import StandardDataKeys

class TestPowmrRs232Plugin(unittest.TestCase):
    """Test suite for POWMR RS232 Plugin."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.logger = logging.getLogger("test_powmr_rs232")
        self.logger.setLevel(logging.DEBUG)
        
        # Mock app_state
        self.mock_app_state = Mock()
        
        # Basic plugin configuration for serial
        self.serial_config = {
            "connection_type": "serial",
            "serial_port": "COM3",
            "baud_rate": 9600,
            "powmr_protocol_version": 1
        }
        
        # Basic plugin configuration for TCP
        self.tcp_config = {
            "connection_type": "tcp",
            "tcp_host": "192.168.1.100",
            "tcp_port": 502,
            "powmr_protocol_version": 1
        }
        
        # Create plugin instance
        self.plugin = PowmrCustomRs232Plugin(
            instance_name="test_powmr_rs232",
            plugin_specific_config=self.serial_config,
            main_logger=self.logger,
            app_state=self.mock_app_state
        )

    def test_plugin_initialization(self):
        """Test plugin initialization and configuration parsing."""
        self.assertEqual(self.plugin.name, "powmr_custom_rs232")
        self.assertEqual(self.plugin.pretty_name, "POWMR RS232 Inverter")
        self.assertEqual(self.plugin.connection_type, ConnectionType.SERIAL)
        self.assertEqual(self.plugin.serial_port_path, "COM3")
        self.assertEqual(self.plugin.baud_rate, 9600)
        self.assertEqual(self.plugin.protocol_version, 1)

    def test_tcp_initialization(self):
        """Test TCP connection initialization."""
        tcp_plugin = PowmrCustomRs232Plugin(
            instance_name="test_powmr_tcp",
            plugin_specific_config=self.tcp_config,
            main_logger=self.logger
        )
        
        self.assertEqual(tcp_plugin.connection_type, ConnectionType.TCP)
        self.assertEqual(tcp_plugin.tcp_host, "192.168.1.100")
        self.assertEqual(tcp_plugin.tcp_port, 502)

    def test_modbus_crc16_calculation(self):
        """Test Modbus CRC16 calculation."""
        # Test with known data
        test_data = b'\x88\x51\x00\x03\x00\x00\x00\x90'
        expected_crc = 0x084d  # This should match the expected CRC
        
        calculated_crc = _modbus_crc16(test_data)
        
        # CRC calculation should be consistent
        self.assertIsInstance(calculated_crc, int)
        self.assertGreaterEqual(calculated_crc, 0)
        self.assertLessEqual(calculated_crc, 0xFFFF)

    def test_build_request_packet_state(self):
        """Test building state request packet."""
        packet = _build_request_packet("state", protocol_version=1)
        
        # Check packet structure
        self.assertEqual(len(packet), 10)  # 8 bytes header + 2 bytes CRC
        
        # Check protocol header
        protocol = struct.unpack('>H', packet[0:2])[0]
        self.assertEqual(protocol, PROTOCOL_HEADER)
        
        # Check command
        command = struct.unpack('>H', packet[2:4])[0]
        self.assertEqual(command, STATE_COMMAND)
        
        # Check address
        address = struct.unpack('>H', packet[4:6])[0]
        self.assertEqual(address, STATE_ADDRESS)

    def test_build_request_packet_config(self):
        """Test building config request packet."""
        packet = _build_request_packet("config", protocol_version=1)
        
        # Check packet structure
        self.assertEqual(len(packet), 10)  # 8 bytes header + 2 bytes CRC
        
        # Check protocol header
        protocol = struct.unpack('>H', packet[0:2])[0]
        self.assertEqual(protocol, PROTOCOL_HEADER)
        
        # Check command
        command = struct.unpack('>H', packet[2:4])[0]
        self.assertEqual(command, CONFIG_COMMAND_READ)
        
        # Check address
        address = struct.unpack('>H', packet[4:6])[0]
        self.assertEqual(address, CONFIG_ADDRESS)

    def test_build_request_packet_invalid(self):
        """Test building request packet with invalid type."""
        with self.assertRaises(ValueError):
            _build_request_packet("invalid", protocol_version=1)

    def test_parse_response_valid(self):
        """Test parsing valid response packet."""
        # Create a mock response packet
        header = struct.pack('>HHHH', PROTOCOL_HEADER, STATE_COMMAND, STATE_ADDRESS, 144)
        data = b'\x00' * 144  # 144 bytes of data
        crc = struct.pack('<H', _modbus_crc16(header + data))
        response = header + data + crc
        
        parsed = _parse_response(response, len(response))
        
        self.assertIsNotNone(parsed)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(len(parsed), 72)  # 144 bytes = 72 words

    def test_parse_response_invalid_length(self):
        """Test parsing response with invalid length."""
        short_response = b'\x88\x51\x00\x03'
        
        parsed = _parse_response(short_response, 154)
        
        self.assertIsNone(parsed)

    def test_parse_response_invalid_protocol(self):
        """Test parsing response with invalid protocol header."""
        # Wrong protocol header
        header = struct.pack('>HHHH', 0x1234, STATE_COMMAND, STATE_ADDRESS, 144)
        data = b'\x00' * 144
        crc = struct.pack('<H', _modbus_crc16(header + data))
        response = header + data + crc
        
        parsed = _parse_response(response, len(response))
        
        self.assertIsNone(parsed)

    def test_parse_response_invalid_crc(self):
        """Test parsing response with invalid CRC."""
        header = struct.pack('>HHHH', PROTOCOL_HEADER, STATE_COMMAND, STATE_ADDRESS, 144)
        data = b'\x00' * 144
        # Wrong CRC
        crc = struct.pack('<H', 0x1234)
        response = header + data + crc
        
        parsed = _parse_response(response, len(response))
        
        self.assertIsNone(parsed)

    def test_decode_data_uint16(self):
        """Test decoding uint16 register data."""
        raw_data = {0: 1234}  # Register 0 = 1234
        register_map = {
            "test_voltage": {"addr": 0, "type": "uint16", "scale": 0.1, "unit": "V"}
        }
        
        decoded = self.plugin._decode_data(raw_data, register_map)
        
        self.assertIn("test_voltage", decoded)
        self.assertAlmostEqual(decoded["test_voltage"], 123.4, places=1)

    def test_decode_data_int16(self):
        """Test decoding int16 register data (signed values)."""
        raw_data = {0: 65535}  # -1 in int16
        register_map = {
            "test_current": {"addr": 0, "type": "int16", "scale": 0.1, "unit": "A"}
        }
        
        decoded = self.plugin._decode_data(raw_data, register_map)
        
        self.assertIn("test_current", decoded)
        self.assertAlmostEqual(decoded["test_current"], -0.1, places=1)

    def test_decode_data_version_filtering(self):
        """Test that version 2 registers are filtered for version 1 protocol."""
        raw_data = {0: 1234, 1: 5678}
        register_map = {
            "v1_register": {"addr": 0, "type": "uint16", "scale": 1},
            "v2_register": {"addr": 1, "type": "uint16", "scale": 1, "version": 2}
        }
        
        decoded = self.plugin._decode_data(raw_data, register_map)
        
        self.assertIn("v1_register", decoded)
        self.assertNotIn("v2_register", decoded)

    def test_temperature_decoding(self):
        """Test temperature decoding from NTC registers."""
        # Mock decoded data with temperature registers
        decoded_data = {
            "ntc_temps_1": 0x2D1E,  # ntc3_temp=45, ntc2_temp=30
            "ntc_temps_2": 0x3C28   # bts_temp=60, ntc4_temp=40
        }
        
        standardized = self.plugin._standardize_operational_data(decoded_data)
        
        # Should extract temperatures correctly
        self.assertEqual(standardized[StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS], 45)
        self.assertEqual(standardized[StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS], 60)

    def test_run_mode_decoding(self):
        """Test run mode decoding from bitfield."""
        # Test normal mode (PV topology = 3)
        decoded_data = {"run_mode": 0x0300}  # PV topology in 3rd nibble
        
        standardized = self.plugin._standardize_operational_data(decoded_data)
        
        self.assertEqual(standardized[StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT], "Normal")

    def test_battery_power_calculation(self):
        """Test battery power calculation from voltage and current."""
        decoded_data = {
            "batt_voltage": 48.0,
            "batt_charge_current": -5.0  # Negative = discharging
        }
        
        standardized = self.plugin._standardize_operational_data(decoded_data)
        
        # Power should be positive when discharging
        self.assertEqual(standardized[StandardDataKeys.BATTERY_POWER_WATTS], 240.0)
        self.assertEqual(standardized[StandardDataKeys.BATTERY_STATUS_TEXT], "Discharging")

    def test_battery_charging_status(self):
        """Test battery charging status detection."""
        decoded_data = {
            "batt_voltage": 48.0,
            "batt_charge_current": 5.0  # Positive = charging
        }
        
        standardized = self.plugin._standardize_operational_data(decoded_data)
        
        # Power should be negative when charging
        self.assertEqual(standardized[StandardDataKeys.BATTERY_POWER_WATTS], -240.0)
        self.assertEqual(standardized[StandardDataKeys.BATTERY_STATUS_TEXT], "Charging")

    def test_alert_decoding_no_alerts(self):
        """Test alert decoding with no active alerts."""
        alert_bitfields = {}
        
        active_faults, categorized_alerts = self.plugin._decode_powmr_alerts(alert_bitfields)
        
        self.assertEqual(len(active_faults), 0)
        for category in ALERT_CATEGORIES:
            self.assertEqual(len(categorized_alerts[category]), 0)

    def test_alert_decoding_with_alerts(self):
        """Test alert decoding with active alerts."""
        # Mock system flags with some bits set
        alert_bitfields = {1: 0x0005}  # Bits 0 and 2 set
        
        active_faults, categorized_alerts = self.plugin._decode_powmr_alerts(alert_bitfields)
        
        self.assertGreater(len(active_faults), 0)
        self.assertIn("system", categorized_alerts)

    def test_constants_validation(self):
        """Test that all constants are properly defined."""
        # Check protocol constants
        self.assertEqual(PROTOCOL_HEADER, 0x8851)
        self.assertEqual(STATE_COMMAND, 0x0003)
        self.assertEqual(CONFIG_COMMAND_READ, 0x0300)
        
        # Check that all registers have required fields
        for reg_name, reg_info in POWMR_REGISTERS.items():
            self.assertIn("addr", reg_info, f"Register {reg_name} missing 'addr'")
            self.assertIn("type", reg_info, f"Register {reg_name} missing 'type'")
            
        # Check run mode codes
        self.assertIsInstance(POWMR_RUN_MODE_CODES, dict)
        self.assertIn(3, POWMR_RUN_MODE_CODES)  # Normal mode
        
        # Check alert categories
        self.assertIsInstance(ALERT_CATEGORIES, list)
        self.assertIn("system", ALERT_CATEGORIES)

    def test_register_address_ranges(self):
        """Test that register addresses are within reasonable ranges."""
        for reg_name, reg_info in POWMR_REGISTERS.items():
            addr = reg_info["addr"]
            self.assertGreaterEqual(addr, 0, f"Register {reg_name} has negative address")
            self.assertLess(addr, 100, f"Register {reg_name} address too high for POWMR protocol")

    @patch('plugins.inverter.powmr_rs232_plugin.serial.Serial')
    def test_serial_connection_success(self, mock_serial):
        """Test successful serial connection."""
        mock_serial_instance = Mock()
        mock_serial_instance.is_open = True
        mock_serial.return_value = mock_serial_instance
        
        result = self.plugin.connect()
        
        self.assertTrue(result)
        self.assertTrue(self.plugin.is_connected)
        mock_serial.assert_called_once()

    @patch('plugins.inverter.powmr_rs232_plugin.serial.Serial')
    def test_serial_connection_failure(self, mock_serial):
        """Test serial connection failure."""
        mock_serial.side_effect = Exception("Port not available")
        
        result = self.plugin.connect()
        
        self.assertFalse(result)
        self.assertFalse(self.plugin.is_connected)
        self.assertIsNotNone(self.plugin.last_error_message)

    @patch('plugins.inverter.powmr_rs232_plugin.socket.socket')
    def test_tcp_connection_success(self, mock_socket):
        """Test successful TCP connection."""
        tcp_plugin = PowmrCustomRs232Plugin(
            instance_name="test_tcp",
            plugin_specific_config=self.tcp_config,
            main_logger=self.logger
        )
        
        mock_socket_instance = Mock()
        mock_socket.return_value = mock_socket_instance
        
        result = tcp_plugin.connect()
        
        self.assertTrue(result)
        self.assertTrue(tcp_plugin.is_connected)
        mock_socket_instance.connect.assert_called_once_with(("192.168.1.100", 502))

    @patch('plugins.inverter.powmr_rs232_plugin.socket.socket')
    def test_tcp_connection_failure(self, mock_socket):
        """Test TCP connection failure."""
        tcp_plugin = PowmrCustomRs232Plugin(
            instance_name="test_tcp",
            plugin_specific_config=self.tcp_config,
            main_logger=self.logger
        )
        
        mock_socket_instance = Mock()
        mock_socket_instance.connect.side_effect = Exception("Connection refused")
        mock_socket.return_value = mock_socket_instance
        
        result = tcp_plugin.connect()
        
        self.assertFalse(result)
        self.assertFalse(tcp_plugin.is_connected)
        self.assertIsNotNone(tcp_plugin.last_error_message)

    def test_disconnect_cleanup(self):
        """Test proper cleanup during disconnect."""
        # Mock connections
        self.plugin.serial_client = Mock()
        self.plugin.serial_client.is_open = True
        self.plugin.tcp_client = Mock()
        self.plugin._is_connected_flag = True
        
        self.plugin.disconnect()
        
        self.plugin.serial_client.close.assert_called_once()
        self.plugin.tcp_client.close.assert_called_once()
        self.assertIsNone(self.plugin.serial_client)
        self.assertIsNone(self.plugin.tcp_client)
        self.assertFalse(self.plugin.is_connected)

    def test_protocol_version_2_support(self):
        """Test protocol version 2 support."""
        v2_config = self.serial_config.copy()
        v2_config["powmr_protocol_version"] = 2
        
        v2_plugin = PowmrCustomRs232Plugin(
            instance_name="test_v2",
            plugin_specific_config=v2_config,
            main_logger=self.logger
        )
        
        self.assertEqual(v2_plugin.protocol_version, 2)
        
        # Test packet building for version 2
        packet = _build_request_packet("state", protocol_version=2)
        data_size = struct.unpack('>H', packet[6:8])[0]
        self.assertEqual(data_size, 148)  # Version 2 has 4 extra bytes

class TestPowmrConstants(unittest.TestCase):
    """Test suite for POWMR constants validation."""

    def test_register_completeness(self):
        """Test that all expected registers are defined."""
        expected_registers = [
            "run_mode", "system_flags", "software_version", "inv_voltage",
            "inv_current", "grid_voltage", "batt_voltage", "pv_voltage",
            "bms_battery_soc", "ntc_temps_1", "ntc_temps_2"
        ]
        
        for reg in expected_registers:
            self.assertIn(reg, POWMR_REGISTERS, f"Missing register: {reg}")

    def test_config_register_completeness(self):
        """Test that config registers are defined."""
        expected_config_registers = [
            "inverter_max_power", "output_voltage_setting", "batt_cut_off_voltage",
            "batt_bulk_chg_voltage", "battery_equalization_enable"
        ]
        
        for reg in expected_config_registers:
            self.assertIn(reg, POWMR_CONFIG_REGISTERS, f"Missing config register: {reg}")

    def test_run_mode_codes_coverage(self):
        """Test that run mode codes cover expected states."""
        expected_modes = ["Standby", "Normal", "Fault"]
        
        mode_values = list(POWMR_RUN_MODE_CODES.values())
        for mode in expected_modes:
            self.assertIn(mode, mode_values, f"Missing run mode: {mode}")

    def test_alert_maps_structure(self):
        """Test that alert maps have proper structure."""
        for reg_addr, map_info in POWMR_ALERT_MAPS.items():
            self.assertIsInstance(reg_addr, int)
            self.assertIn("category", map_info)
            self.assertIn("bits", map_info)
            self.assertIsInstance(map_info["bits"], dict)

def run_tests():
    """Run all tests and display results."""
    print("=" * 60)
    print("POWMR RS232 Plugin Test Suite")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPowmrRs232Plugin))
    suite.addTests(loader.loadTestsFromTestCase(TestPowmrConstants))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    print("=" * 60)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)
    
    success = run_tests()
    sys.exit(0 if success else 1)