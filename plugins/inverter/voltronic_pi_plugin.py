# plugins/inverter/voltronic_pi_plugin.py
"""
Voltronic / Axpert / MPP Solar PI30 Plugin

This plugin communicates with Voltronic-based hybrid inverters (Axpert, MPP Solar,
PIP, and clones) using the native PI30 ASCII protocol over serial or TCP.
It polls QPIGS/QMN-style responses and standardizes power-flow metrics.

Features:
- Dual connection support (direct serial and TCP serial gateway)
- PI30 CRC16-XMODEM framed command/response exchange
- Real-time PV, battery, grid, and load metrics from QPIGS
- Model name probing via QMN where available
- Local-only operation (no cloud dependency)

Supported Models:
- Voltronic / Axpert hybrid inverters
- MPP Solar / PIP and compatible PI30 clones

Protocol Reference: Voltronic PI30 (QPIGS / QMN)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import logging
import socket
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None  # type: ignore

from plugins.plugin_interface import DevicePlugin, StandardDataKeys, parse_config_int, parse_config_str
from plugins.plugin_utils import check_tcp_port
from plugins.inverter.voltronic_pi_constants import build_command, find_response, parse_qpigs, parse_qmn

if TYPE_CHECKING:
    from core.app_state import AppState

UNKNOWN = "Unknown"


class VoltronicPiPlugin(DevicePlugin):
    PLUGIN_META = {
        "plugin_id": "voltronic_pi",
        "category": "inverter",
        "protocols": ["pi30_serial", "pi30_tcp"],
        "models": ["Axpert", "MPP", "Voltronic", "PIP"],
        "status": "testing",
        "api_version": 1,
    }

    def __init__(self, instance_name, plugin_specific_config, main_logger, app_state=None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.connection_type = (parse_config_str(plugin_specific_config, "connection_type", "serial") or "serial").lower()
        self.serial_port = parse_config_str(plugin_specific_config, "serial_port", "/dev/ttyUSB0")
        self.baud_rate = parse_config_int(plugin_specific_config, "baud_rate", 2400)
        self.tcp_host = parse_config_str(plugin_specific_config, "tcp_host", "192.168.1.100")
        self.tcp_port = parse_config_int(plugin_specific_config, "tcp_port", 23)
        self.timeout = float(parse_config_str(plugin_specific_config, "timeout_seconds", "2") or 2)
        self._io = None
        self.last_error_message: Optional[str] = None
        self.last_known_static_data: Optional[Dict[str, Any]] = None
        self._model = UNKNOWN

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        return [
            {"name": "connection_type", "type": "select", "options": ["serial", "tcp"], "default": "serial"},
            {"name": "serial_port", "type": "str", "default": "/dev/ttyUSB0"},
            {"name": "baud_rate", "type": "int", "default": 2400},
            {"name": "tcp_host", "type": "str", "default": "192.168.1.100"},
            {"name": "tcp_port", "type": "int", "default": 23},
        ]

    @property
    def name(self) -> str:
        return "voltronic_pi"

    @property
    def pretty_name(self) -> str:
        return "Voltronic PI30"

    def connect(self) -> bool:
        self.disconnect()
        try:
            if self.connection_type == "tcp":
                ok, _, err = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
                if not ok:
                    self.last_error_message = err
                    return False
                s = socket.create_connection((self.tcp_host, self.tcp_port), timeout=self.timeout)
                s.settimeout(self.timeout)
                self._io = s
            else:
                if serial is None:
                    raise ImportError("pyserial required for Voltronic serial")
                self._io = serial.Serial(self.serial_port, self.baud_rate, timeout=self.timeout)
            self._is_connected_flag = True
            return True
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Voltronic connect failed: %s", e)
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

    def _xfer(self, cmd: str) -> bytes:
        packet = build_command(cmd)
        if isinstance(self._io, socket.socket):
            self._io.sendall(packet)
            time.sleep(0.35)
            chunks = []
            try:
                while True:
                    part = self._io.recv(512)
                    if not part:
                        break
                    chunks.append(part)
                    if b"\r" in part:
                        break
            except socket.timeout:
                pass
            return b"".join(chunks)
        self._io.reset_input_buffer()
        self._io.write(packet)
        time.sleep(0.35)
        return self._io.read(512)

    def read_static_data(self) -> Dict[str, Any]:
        if self.last_known_static_data:
            return self.last_known_static_data
        model = UNKNOWN
        try:
            raw = self._xfer("QMN")
            resp = find_response(raw)
            if resp:
                model = parse_qmn(resp) or UNKNOWN
                self._model = model
        except Exception as e:
            self.logger.debug("QMN failed: %s", e)
        data = {
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
            StandardDataKeys.STATIC_INVERTER_MANUFACTURER: "Voltronic",
            StandardDataKeys.STATIC_INVERTER_MODEL_NAME: model,
            StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: f"voltronic_{self.connection_type}",
            StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION: UNKNOWN,
            StandardDataKeys.STATIC_NUMBER_OF_MPPTS: 1,
            StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: 1,
        }
        self.last_known_static_data = data
        return data

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            raw = self._xfer("QPIGS")
            resp = find_response(raw)
            if not resp:
                self.last_error_message = "No QPIGS response"
                return None
            d = parse_qpigs(resp)
            if not d:
                self.last_error_message = "QPIGS parse failed"
                return None
            batt_p = d.get("battery_power")
            status = "Discharging" if (batt_p or 0) > 50 else "Charging" if (batt_p or 0) < -50 else "Idle"
            return {
                StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: "Normal",
                StandardDataKeys.BATTERY_STATUS_TEXT: status,
                StandardDataKeys.AC_POWER_WATTS: d.get("ac_power"),
                StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: d.get("pv_power"),
                StandardDataKeys.LOAD_TOTAL_POWER_WATTS: d.get("ac_power"),
                StandardDataKeys.BATTERY_POWER_WATTS: batt_p,
                StandardDataKeys.BATTERY_CURRENT_AMPS: d.get("battery_current"),
                StandardDataKeys.BATTERY_VOLTAGE_VOLTS: d.get("battery_voltage"),
                StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: d.get("battery_soc"),
                StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: d.get("inverter_temp"),
                StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_voltage"),
                StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
                StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: d.get("pv_voltage"),
                StandardDataKeys.PV_MPPT1_CURRENT_AMPS: d.get("pv_current"),
                StandardDataKeys.PV_MPPT1_POWER_WATTS: d.get("pv_power"),
            }
        except Exception as e:
            self.last_error_message = str(e)
            self.logger.error("Voltronic read failed: %s", e)
            self.disconnect()
            return None
