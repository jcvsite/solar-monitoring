# plugins/battery/daly_bms_plugin.py
"""
Daly Smart BMS Plugin

This plugin communicates with Daly Smart BMS devices over UART or RS485
(serial or TCP gateway). It queries pack status, cell voltages, temperatures,
MOSFET state, and fault bitfields for the Solar Monitoring Framework.

Features:
- Serial and TCP gateway connection support
- Multi-command poll cycle (SOC/voltage/current, temps, MOS, cells, faults)
- Cell voltage min/max tracking and pack metrics
- Charge/discharge MOSFET status and alarm decoding
- Standardized BMS keys via BMSPluginBase

Supported Models:
- Daly Smart BMS (UART / RS485)
- Compatible Daly protocol clones (~V1.2 framing)

Protocol Reference: Daly Smart BMS UART/RS485 Protocol (~V1.2)
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
    BMS_KEY_CELL_COUNT, BMS_KEY_CELL_VOLTAGES_ALL,
    BMS_KEY_CELL_VOLTAGE_MIN, BMS_KEY_CELL_VOLTAGE_MAX, BMS_KEY_CELL_VOLTAGE_AVG,
    BMS_KEY_CELL_VOLTAGE_DIFF, BMS_KEY_LOWEST_CELL_NUMBER, BMS_KEY_HIGHEST_CELL_NUMBER,
    BMS_KEY_STATUS_TEXT, BMS_KEY_CHARGE_FET_ON, BMS_KEY_DISCHARGE_FET_ON,
    BMS_KEY_ACTIVE_ALARMS_LIST, BMS_KEY_MANUFACTURER, BMS_KEY_MODEL,
    BMS_KEY_SERIAL_NUMBER, BMS_KEY_FIRMWARE_VERSION, BMS_PLUGIN_LAST_UPDATE,
)
from plugins.battery.daly_bms_decoder import (
    build_query, find_responses, parse_0x90, parse_0x92, parse_0x93, parse_0x95_cell_frame, parse_0x98,
)


class DalyBmsPlugin(BMSPluginBase):
    PLUGIN_META = {
        "plugin_id": "daly_bms",
        "category": "bms",
        "protocols": ["daly_uart"],
        "models": ["Daly Smart BMS"],
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
            BMS_KEY_MANUFACTURER: "Daly",
            BMS_KEY_MODEL: "Smart BMS",
            BMS_KEY_SERIAL_NUMBER: f"daly_{self.connection_type}",
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
        return "daly_bms"

    @property
    def pretty_name(self) -> str:
        return f"Daly BMS ({self.connection_type.upper()})"

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
            self.logger.error("Daly connect failed: %s", e)
            return False

    def disconnect(self) -> None:
        if self._io:
            try:
                self._io.close()
            except Exception:
                pass
        self._io = None
        self._is_connected_flag = False

    def _query(self, data_id: int) -> List[bytes]:
        cmd = build_query(data_id)
        if not self._io:
            return []
        if self.connection_type == "tcp":
            self._io.sendall(cmd)
            time.sleep(0.08)
            buf = b""
            try:
                buf = self._io.recv(256)
            except socket.timeout:
                pass
        else:
            self._io.reset_input_buffer()
            self._io.write(cmd)
            time.sleep(0.1)
            buf = self._io.read(128)
        return find_responses(buf)

    def get_bms_static_info(self) -> Optional[Dict[str, Any]]:
        return dict(self._static)

    def read_bms_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            pack = None
            for fr in self._query(0x90):
                pack = parse_0x90(fr)
                if pack:
                    break
            if not pack:
                self.logger.warning("Daly: no 0x90 response")
                return None

            mos = {}
            for fr in self._query(0x93):
                mos = parse_0x93(fr) or {}
                if mos:
                    break
            temps = {}
            for fr in self._query(0x92):
                temps = parse_0x92(fr) or {}
                if temps:
                    break

            cells_map: Dict[int, List[float]] = {}
            for _ in range(16):
                for fr in self._query(0x95):
                    parsed = parse_0x95_cell_frame(fr)
                    if not parsed:
                        continue
                    fno, cvs = parsed
                    cells_map[fno] = cvs
            cells: List[float] = []
            for k in sorted(cells_map.keys()):
                cells.extend(cells_map[k])

            alarms: List[str] = []
            for fr in self._query(0x98):
                alarms.extend(parse_0x98(fr))

            v, i = pack["voltage_v"], pack["current_a"]
            if i > 0.5:
                status = "Discharging"
            elif i < -0.5:
                status = "Charging"
            else:
                status = "Idle"

            out = {
                BMS_KEY_SOC: pack["soc"],
                BMS_KEY_VOLTAGE: v,
                BMS_KEY_CURRENT: i,
                BMS_KEY_POWER: v * i,
                BMS_KEY_STATUS_TEXT: status,
                BMS_KEY_CHARGE_FET_ON: mos.get("charge_fet"),
                BMS_KEY_DISCHARGE_FET_ON: mos.get("discharge_fet"),
                BMS_KEY_ACTIVE_ALARMS_LIST: alarms,
                BMS_PLUGIN_LAST_UPDATE: datetime.now(timezone.utc).isoformat(),
                StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms",
            }
            if temps.get("temps_c"):
                out[BMS_KEY_TEMPERATURES_ALL] = temps["temps_c"]
                out[BMS_KEY_TEMP_MAX] = temps.get("temp_max_c")
                out[BMS_KEY_TEMP_MIN] = temps.get("temp_min_c")
            if cells:
                out[BMS_KEY_CELL_VOLTAGES_ALL] = cells
                out[BMS_KEY_CELL_COUNT] = len(cells)
                out[BMS_KEY_CELL_VOLTAGE_MIN] = min(cells)
                out[BMS_KEY_CELL_VOLTAGE_MAX] = max(cells)
                out[BMS_KEY_CELL_VOLTAGE_AVG] = sum(cells) / len(cells)
                out[BMS_KEY_CELL_VOLTAGE_DIFF] = max(cells) - min(cells)
                out[BMS_KEY_LOWEST_CELL_NUMBER] = cells.index(min(cells)) + 1
                out[BMS_KEY_HIGHEST_CELL_NUMBER] = cells.index(max(cells)) + 1
            return out
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Daly read failed: %s", e)
            self.disconnect()
            return None
