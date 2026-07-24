# plugins/battery/jbd_bms_plugin.py
"""
JBD / Xiaoxiang / Overkill BMS Plugin

This plugin communicates with JBD-family battery management systems over UART
(serial or TCP serial gateway) using the common Xiaoxiang/Overkill read protocol.
It publishes pack SOC, cell voltages, temperatures, FET status, and alarms.

Features:
- Serial and TCP gateway connection support
- Basic info and cell voltage frame reads
- Pack voltage, current, power, SOC, and capacity tracking
- Cell voltage min/max/avg/diff and temperature sensors
- Charge/discharge FET status and active alarm lists
- Standardized BMS keys via BMSPluginBase

Supported Models:
- JBD BMS modules
- Xiaoxiang / Daly-compatible JBD UART clones
- Overkill Solar BMS (JBD protocol)

Protocol Reference: JBD / Xiaoxiang UART Protocol (V4-style)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import logging
import socket
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None  # type: ignore

if TYPE_CHECKING:
    from core.app_state import AppState

from plugins.plugin_interface import StandardDataKeys, parse_config_int, parse_config_str
from plugins.battery.bms_plugin_base import (
    BMSPluginBase,
    BMS_KEY_SOC, BMS_KEY_VOLTAGE, BMS_KEY_CURRENT, BMS_KEY_POWER,
    BMS_KEY_REMAINING_CAPACITY_AH, BMS_KEY_FULL_CAPACITY_AH, BMS_KEY_CYCLE_COUNT,
    BMS_KEY_TEMPERATURES_ALL, BMS_KEY_TEMP_MAX, BMS_KEY_TEMP_MIN,
    BMS_KEY_CELL_COUNT, BMS_KEY_CELL_VOLTAGES_ALL,
    BMS_KEY_CELL_VOLTAGE_MIN, BMS_KEY_CELL_VOLTAGE_MAX, BMS_KEY_CELL_VOLTAGE_AVG,
    BMS_KEY_CELL_VOLTAGE_DIFF, BMS_KEY_LOWEST_CELL_NUMBER, BMS_KEY_HIGHEST_CELL_NUMBER,
    BMS_KEY_STATUS_TEXT, BMS_KEY_CHARGE_FET_ON, BMS_KEY_DISCHARGE_FET_ON,
    BMS_KEY_ACTIVE_ALARMS_LIST, BMS_KEY_MANUFACTURER, BMS_KEY_MODEL,
    BMS_KEY_SERIAL_NUMBER, BMS_KEY_FIRMWARE_VERSION, BMS_PLUGIN_LAST_UPDATE,
)
from plugins.battery.jbd_bms_decoder import build_read_cmd, find_frames, parse_basic_info, parse_cell_voltages


class JbdBmsPlugin(BMSPluginBase):
    PLUGIN_META = {
        "plugin_id": "jbd_bms",
        "category": "bms",
        "protocols": ["jbd_uart"],
        "models": ["JBD", "Xiaoxiang", "Overkill"],
        "status": "testing",
        "api_version": 1,
    }

    def __init__(self, instance_name, plugin_specific_config, main_logger, app_state=None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.connection_type = (parse_config_str(plugin_specific_config, "connection_type", "serial") or "serial").lower()
        self.serial_port = parse_config_str(plugin_specific_config, "serial_port", "COM4")
        self.baud_rate = parse_config_int(plugin_specific_config, "baud_rate", 9600)
        self.tcp_host = parse_config_str(plugin_specific_config, "tcp_host", "192.168.1.100")
        self.tcp_port = parse_config_int(plugin_specific_config, "tcp_port", 8899)
        self.timeout = float(parse_config_str(plugin_specific_config, "timeout_seconds", "2") or 2)
        self._io = None
        self._static = {
            BMS_KEY_MANUFACTURER: "JBD",
            BMS_KEY_MODEL: "Xiaoxiang/Overkill",
            BMS_KEY_SERIAL_NUMBER: f"jbd_{self.connection_type}",
            BMS_KEY_FIRMWARE_VERSION: "Unknown",
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms",
        }

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        return [
            {"name": "connection_type", "type": str, "default": "serial", "options": ["serial", "tcp"]},
            {"name": "serial_port", "type": str, "default": "/dev/ttyUSB0"},
            {"name": "baud_rate", "type": int, "default": 9600},
            {"name": "tcp_host", "type": str, "default": "192.168.1.100"},
            {"name": "tcp_port", "type": int, "default": 8899},
        ]

    @property
    def name(self) -> str:
        return "jbd_bms"

    @property
    def pretty_name(self) -> str:
        return f"JBD BMS ({self.connection_type.upper()})"

    def connect(self) -> bool:
        self.disconnect()
        try:
            if self.connection_type == "tcp":
                s = socket.create_connection((self.tcp_host, self.tcp_port), timeout=self.timeout)
                s.settimeout(self.timeout)
                self._io = s
            else:
                if serial is None:
                    raise ImportError("pyserial required")
                self._io = serial.Serial(self.serial_port, self.baud_rate, timeout=self.timeout)
            self._is_connected_flag = True
            return True
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("JBD connect failed: %s", e)
            self._is_connected_flag = False
            return False

    def disconnect(self) -> None:
        if self._io:
            try:
                self._io.close()
            except Exception:
                pass
        self._io = None
        self._is_connected_flag = False

    def _xfer(self, cmd: bytes) -> bytes:
        if not self._io:
            return b""
        if self.connection_type == "tcp":
            self._io.sendall(cmd)
            time.sleep(0.15)
            chunks = []
            try:
                while True:
                    part = self._io.recv(256)
                    if not part:
                        break
                    chunks.append(part)
                    if len(b"".join(chunks)) > 8:
                        break
            except socket.timeout:
                pass
            return b"".join(chunks)
        self._io.reset_input_buffer()
        self._io.write(cmd)
        time.sleep(0.2)
        return self._io.read(256)

    def get_bms_static_info(self) -> Optional[Dict[str, Any]]:
        return dict(self._static)

    def read_bms_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            buf = self._xfer(build_read_cmd(0x03))
            basic = None
            for fr in find_frames(buf):
                basic = parse_basic_info(fr)
                if basic:
                    break
            if not basic:
                # wake + retry
                self._xfer(build_read_cmd(0x03))
                time.sleep(0.3)
                buf = self._xfer(build_read_cmd(0x03))
                for fr in find_frames(buf):
                    basic = parse_basic_info(fr)
                    if basic:
                        break
            if not basic:
                self.logger.warning("JBD: no basic info frame")
                return None

            cells: List[float] = []
            cbuf = self._xfer(build_read_cmd(0x04))
            for fr in find_frames(cbuf):
                parsed = parse_cell_voltages(fr)
                if parsed:
                    cells = parsed
                    break

            v, i = basic["voltage_v"], basic["current_a"]
            power = v * i
            if i > 0.5:
                status = "Discharging"
            elif i < -0.5:
                status = "Charging"
            else:
                status = "Idle"
            alarms = []
            if basic.get("protection"):
                alarms.append(f"Protection flags=0x{basic['protection']:04X}")

            out = {
                BMS_KEY_SOC: basic["soc"],
                BMS_KEY_VOLTAGE: v,
                BMS_KEY_CURRENT: i,
                BMS_KEY_POWER: power,
                BMS_KEY_REMAINING_CAPACITY_AH: basic["remaining_ah"],
                BMS_KEY_FULL_CAPACITY_AH: basic["full_ah"],
                BMS_KEY_CYCLE_COUNT: basic["cycles"],
                BMS_KEY_TEMPERATURES_ALL: basic["temps_c"],
                BMS_KEY_CHARGE_FET_ON: basic["charge_fet"],
                BMS_KEY_DISCHARGE_FET_ON: basic["discharge_fet"],
                BMS_KEY_STATUS_TEXT: status,
                BMS_KEY_ACTIVE_ALARMS_LIST: alarms,
                BMS_KEY_CELL_COUNT: basic["cell_count"] or len(cells),
                BMS_PLUGIN_LAST_UPDATE: datetime.now(timezone.utc).isoformat(),
                StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms",
            }
            if basic["temps_c"]:
                out[BMS_KEY_TEMP_MAX] = max(basic["temps_c"])
                out[BMS_KEY_TEMP_MIN] = min(basic["temps_c"])
            if cells:
                out[BMS_KEY_CELL_VOLTAGES_ALL] = cells
                out[BMS_KEY_CELL_VOLTAGE_MIN] = min(cells)
                out[BMS_KEY_CELL_VOLTAGE_MAX] = max(cells)
                out[BMS_KEY_CELL_VOLTAGE_AVG] = sum(cells) / len(cells)
                out[BMS_KEY_CELL_VOLTAGE_DIFF] = max(cells) - min(cells)
                out[BMS_KEY_LOWEST_CELL_NUMBER] = cells.index(min(cells)) + 1
                out[BMS_KEY_HIGHEST_CELL_NUMBER] = cells.index(max(cells)) + 1
            return out
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("JBD read failed: %s", e)
            self.disconnect()
            return None
