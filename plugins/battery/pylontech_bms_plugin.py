# plugins/battery/pylontech_bms_plugin.py
"""
Pylontech BMS Console Plugin

This plugin communicates with Pylontech battery modules using the console /
RS485 text protocol (local serial or TCP gateway). Prefer inverter-reported
SOC when the pack is already monitored via CAN through the inverter.

Features:
- Serial and TCP gateway connection support
- Console `pwr` / `info` style text parsing
- Pack SOC, voltage, current, power, and temperature extraction
- Alarm text capture when present
- Standardized BMS keys via BMSPluginBase

Supported Models:
- Pylontech US2000 / US3000 series
- Pylontech Force series (console-capable)
- Compatible packs exposing the Pylontech console protocol

Protocol Reference: Pylontech Console / RS485 Text Protocol
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
    BMS_KEY_TEMPERATURES_ALL, BMS_KEY_TEMP_MAX, BMS_KEY_TEMP_MIN,
    BMS_KEY_STATUS_TEXT, BMS_KEY_ACTIVE_ALARMS_LIST,
    BMS_KEY_MANUFACTURER, BMS_KEY_MODEL, BMS_KEY_SERIAL_NUMBER,
    BMS_KEY_FIRMWARE_VERSION, BMS_PLUGIN_LAST_UPDATE,
)
from plugins.battery.pylontech_bms_decoder import parse_pwr_line, parse_info_block


class PylontechBmsPlugin(BMSPluginBase):
    PLUGIN_META = {
        "plugin_id": "pylontech_bms",
        "category": "bms",
        "protocols": ["pylon_console"],
        "models": ["US2000", "US3000", "Force"],
        "status": "testing",
        "api_version": 1,
        "notes": "Console RS485. Many installs get SOC via inverter CAN; use this when direct console is wired.",
    }

    def __init__(self, instance_name, plugin_specific_config, main_logger, app_state=None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.connection_type = (parse_config_str(plugin_specific_config, "connection_type", "serial") or "serial").lower()
        self.serial_port = parse_config_str(plugin_specific_config, "serial_port", "/dev/ttyUSB0")
        self.baud_rate = parse_config_int(plugin_specific_config, "baud_rate", 115200)
        self.tcp_host = parse_config_str(plugin_specific_config, "tcp_host", "192.168.1.100")
        self.tcp_port = parse_config_int(plugin_specific_config, "tcp_port", 23)
        self.timeout = float(parse_config_str(plugin_specific_config, "timeout_seconds", "2") or 2)
        self._io = None
        self._static = {
            BMS_KEY_MANUFACTURER: "Pylontech",
            BMS_KEY_MODEL: "US-series",
            BMS_KEY_SERIAL_NUMBER: f"pylon_{self.connection_type}",
            BMS_KEY_FIRMWARE_VERSION: "Unknown",
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms",
        }

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        return [
            {"name": "connection_type", "type": "select", "options": ["serial", "tcp"], "default": "serial"},
            {"name": "serial_port", "type": "str", "default": "/dev/ttyUSB0"},
            {"name": "baud_rate", "type": "int", "default": 115200},
            {"name": "tcp_host", "type": "str", "default": "192.168.1.100"},
            {"name": "tcp_port", "type": "int", "default": 23},
        ]

    @property
    def name(self) -> str:
        return "pylontech_bms"

    @property
    def pretty_name(self) -> str:
        return "Pylontech BMS"

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
            # Best-effort identity
            try:
                info = self._cmd("info")
                parsed = parse_info_block(info)
                if parsed.get("model"):
                    self._static[BMS_KEY_MODEL] = parsed["model"]
                if parsed.get("serial"):
                    self._static[BMS_KEY_SERIAL_NUMBER] = parsed["serial"]
            except Exception:
                pass
            return True
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Pylontech connect failed: %s", e)
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

    def _cmd(self, command: str) -> str:
        line = (command.strip() + "\r").encode("ascii")
        if isinstance(self._io, socket.socket):
            self._io.sendall(line)
            time.sleep(0.3)
            chunks = []
            try:
                while True:
                    part = self._io.recv(1024)
                    if not part:
                        break
                    chunks.append(part)
                    if len(part) < 1024:
                        break
            except socket.timeout:
                pass
            return b"".join(chunks).decode("ascii", errors="ignore")
        self._io.reset_input_buffer()
        self._io.write(line)
        time.sleep(0.3)
        return self._io.read(2048).decode("ascii", errors="ignore")

    def get_bms_static_info(self) -> Optional[Dict[str, Any]]:
        return dict(self._static)

    def read_bms_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            text = self._cmd("pwr")
            parsed = parse_pwr_line(text)
            if not parsed:
                # Some firmwares use `power` alias
                text = self._cmd("power")
                parsed = parse_pwr_line(text)
            if not parsed:
                self.logger.warning("Pylontech: could not parse pwr response")
                return None
            v = parsed.get("voltage_v")
            i = parsed.get("current_a")
            power = (v * i) if v is not None and i is not None else None
            if i is not None and i > 0.5:
                status = "Discharging"
            elif i is not None and i < -0.5:
                status = "Charging"
            else:
                status = "Idle"
            out = {
                BMS_KEY_SOC: parsed.get("soc"),
                BMS_KEY_VOLTAGE: v,
                BMS_KEY_CURRENT: i,
                BMS_KEY_POWER: power,
                BMS_KEY_STATUS_TEXT: status,
                BMS_KEY_ACTIVE_ALARMS_LIST: [],
                BMS_PLUGIN_LAST_UPDATE: datetime.now(timezone.utc).isoformat(),
                StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms",
            }
            if parsed.get("temp_c") is not None:
                t = parsed["temp_c"]
                out[BMS_KEY_TEMPERATURES_ALL] = [t]
                out[BMS_KEY_TEMP_MAX] = t
                out[BMS_KEY_TEMP_MIN] = t
            return out
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Pylontech read failed: %s", e)
            self.disconnect()
            return None
