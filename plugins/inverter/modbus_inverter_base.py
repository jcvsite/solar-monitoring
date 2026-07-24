# plugins/inverter/modbus_inverter_base.py
"""
Shared Modbus Inverter Plugin Base

This module provides a reusable TCP/RTU Modbus connection and register-block
read base class for inverter plugins such as GoodWe, Sofar, Sungrow, and
Felicity. It wraps modbus_helper for pymodbus API compatibility.

Features:
- Dual connection support (Modbus TCP and Serial RTU)
- Pre-connection TCP port / ICMP helpers
- Holding and input register block reads with map decoding
- Common DevicePlugin lifecycle (connect/disconnect/read)
- Shared UNKNOWN sentinel and connection-type enum

Supported Consumers:
- plugins/inverter/goodwe_modbus_plugin.py
- plugins/inverter/sofar_modbus_plugin.py
- plugins/inverter/sungrow_modbus_plugin.py
- plugins/inverter/felicity_modbus_plugin.py

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from plugins.plugin_interface import DevicePlugin, StandardDataKeys, parse_config_int, parse_config_str
from plugins.plugin_utils import check_tcp_port, check_icmp_ping
from plugins.modbus_helper import (
    create_modbus_client,
    safe_read_holding_registers,
    safe_read_input_registers,
    decode_registers_by_map,
)

if TYPE_CHECKING:
    from core.app_state import AppState

UNKNOWN = "Unknown"


class ConnectionType(str, Enum):
    TCP = "tcp"
    SERIAL = "serial"


class ModbusInverterPluginBase(DevicePlugin):
    """Base with connect/disconnect and block register reads via modbus_helper."""

    manufacturer_name: str = "Unknown"
    default_baud: int = 9600
    default_tcp_port: int = 502
    default_slave: int = 1

    def __init__(
        self,
        instance_name: str,
        plugin_specific_config: Dict[str, Any],
        main_logger: logging.Logger,
        app_state: Optional["AppState"] = None,
    ):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        try:
            # Probe pymodbus availability early
            from plugins.modbus_helper import ModbusTcpClient as _Probe  # noqa: F401
            if _Probe is None:
                raise ImportError("pymodbus is required")
        except ImportError as e:
            raise ImportError(f"{self.__class__.__name__} requires pymodbus") from e
        try:
            self.connection_type = ConnectionType(
                (parse_config_str(plugin_specific_config, "connection_type", "tcp") or "tcp").strip().lower()
            )
        except ValueError:
            self.connection_type = ConnectionType.TCP
        self.serial_port = parse_config_str(plugin_specific_config, "serial_port", "/dev/ttyUSB0")
        self.baud_rate = parse_config_int(plugin_specific_config, "baud_rate", self.default_baud)
        self.tcp_host = parse_config_str(plugin_specific_config, "tcp_host", "192.168.1.100")
        self.tcp_port = parse_config_int(plugin_specific_config, "tcp_port", self.default_tcp_port)
        self.slave_address = parse_config_int(plugin_specific_config, "slave_address", self.default_slave)
        self.modbus_timeout_seconds = float(
            parse_config_str(plugin_specific_config, "modbus_timeout_seconds", "5") or 5
        )
        self.last_error_message: Optional[str] = None
        self.last_known_static_data: Optional[Dict[str, Any]] = None
        self.client = None

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        return [
            {"name": "connection_type", "type": "select", "options": ["tcp", "serial"], "default": "tcp"},
            {"name": "tcp_host", "type": "str", "default": "192.168.1.100"},
            {"name": "tcp_port", "type": "int", "default": 502},
            {"name": "serial_port", "type": "str", "default": "/dev/ttyUSB0"},
            {"name": "baud_rate", "type": "int", "default": 9600},
            {"name": "slave_address", "type": "int", "default": 1},
            {"name": "modbus_timeout_seconds", "type": "float", "default": 5},
        ]

    def connect(self) -> bool:
        if self._is_connected_flag and self.client:
            return True
        if self.client:
            self.disconnect()
        self.last_error_message = None
        if self.connection_type == ConnectionType.TCP:
            port_open, _, err_msg = check_tcp_port(
                self.tcp_host, self.tcp_port, logger_instance=self.logger
            )
            if not port_open:
                self.last_error_message = f"TCP pre-check failed: {err_msg}"
                self.logger.error(self.last_error_message)
                check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                return False
        try:
            self.client = create_modbus_client(
                self.connection_type.value,
                host=self.tcp_host,
                port=self.tcp_port,
                serial_port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=self.modbus_timeout_seconds,
            )
            if self.client.connect():
                self._is_connected_flag = True
                self.logger.info("%s '%s': connected.", self.pretty_name, self.instance_name)
                return True
            self.last_error_message = "client.connect() returned False"
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("%s connect failed: %s", self.pretty_name, e)
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = None
        self._is_connected_flag = False
        return False

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                self.logger.debug("Error closing Modbus client: %s", e)
        self.client = None
        self._is_connected_flag = False

    def _read_holding_block(self, start: int, count: int) -> Optional[List[int]]:
        result = safe_read_holding_registers(
            self.client, start, count, slave=self.slave_address, logger_instance=self.logger
        )
        if result is None or (hasattr(result, "isError") and result.isError()):
            return None
        return list(result.registers)

    def _read_input_block(self, start: int, count: int) -> Optional[List[int]]:
        result = safe_read_input_registers(
            self.client, start, count, slave=self.slave_address, logger_instance=self.logger
        )
        if result is None or (hasattr(result, "isError") and result.isError()):
            return None
        return list(result.registers)

    def _decode_block(
        self, regs: List[int], register_map: Dict[str, Dict[str, Any]], start_addr: int
    ) -> Dict[str, Any]:
        return decode_registers_by_map(regs, register_map, start_addr)

    def _battery_status_from_power(self, power_w: Optional[float]) -> str:
        if power_w is None:
            return UNKNOWN
        if power_w > 50:
            return "Discharging"
        if power_w < -50:
            return "Charging"
        return "Idle"

    def _static_shell(self, model: str = UNKNOWN, serial: str = UNKNOWN, fw: str = UNKNOWN) -> Dict[str, Any]:
        return {
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
            StandardDataKeys.STATIC_INVERTER_MANUFACTURER: self.manufacturer_name,
            StandardDataKeys.STATIC_INVERTER_MODEL_NAME: model,
            StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: serial,
            StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION: fw,
            StandardDataKeys.STATIC_NUMBER_OF_MPPTS: 2,
            StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: 1,
        }
