# plugins/battery/jk_bms_plugin.py
"""
JK BMS Plugin

This plugin communicates with JK (Jikong) battery management systems using the
native JK02 UART protocol, with an optional Modbus RTU/TCP mode. It decodes
cell voltages, pack metrics, FET status, and device information for the Solar
Monitoring Framework.

Features:
- Dual connection support (serial and TCP gateway)
- JK02 UART frame decode (24s / 32s layouts, auto detection)
- Optional Modbus RTU/TCP protocol mode
- Cell voltages, temperatures, SOC, current, and capacity tracking
- Charge/discharge FET status and alarm/warning lists
- Device info frames (manufacturer, model, firmware)
- Configurable frame version and protocol mode

Supported Models:
- JK BMS GPS/UART port devices (JK02 protocol)
- Compatible JK packs with RS485/TCP adapters

Config Notes:
- connection_type = serial | tcp
- jk_protocol_mode = uart | modbus (default: uart)
- jk_frame_version = auto | jk02_24s | jk02_32s

Protocol Reference: JK BMS JK02 UART / Modbus
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
from plugins.plugin_utils import check_tcp_port
from plugins.battery.bms_plugin_base import (
    BMSPluginBase,
    BMS_KEY_SOC,
    BMS_KEY_SOH,
    BMS_KEY_VOLTAGE,
    BMS_KEY_CURRENT,
    BMS_KEY_POWER,
    BMS_KEY_REMAINING_CAPACITY_AH,
    BMS_KEY_FULL_CAPACITY_AH,
    BMS_KEY_CYCLE_COUNT,
    BMS_KEY_TEMPERATURES_ALL,
    BMS_KEY_TEMP_MAX,
    BMS_KEY_TEMP_MIN,
    BMS_KEY_CELL_COUNT,
    BMS_KEY_CELL_VOLTAGES_ALL,
    BMS_KEY_CELL_VOLTAGE_MIN,
    BMS_KEY_CELL_VOLTAGE_MAX,
    BMS_KEY_CELL_VOLTAGE_AVG,
    BMS_KEY_CELL_VOLTAGE_DIFF,
    BMS_KEY_LOWEST_CELL_NUMBER,
    BMS_KEY_HIGHEST_CELL_NUMBER,
    BMS_KEY_CELLS_BALANCING,
    BMS_KEY_STATUS_TEXT,
    BMS_KEY_CHARGE_FET_ON,
    BMS_KEY_DISCHARGE_FET_ON,
    BMS_KEY_ACTIVE_ALARMS_LIST,
    BMS_KEY_ACTIVE_WARNINGS_LIST,
    BMS_KEY_MANUFACTURER,
    BMS_KEY_MODEL,
    BMS_KEY_SERIAL_NUMBER,
    BMS_KEY_FIRMWARE_VERSION,
    BMS_PLUGIN_LAST_UPDATE,
)
from plugins.battery.jk_bms_decoder import (
    PROTOCOL_JK02_24S,
    PROTOCOL_JK02_32S,
    JK_UART_CMD_CELL_INFO,
    JK_UART_CMD_DEVICE_INFO,
    find_jk_frames,
    decode_jk02_cell_info,
    decode_jk02_device_info,
    pick_best_cell_frame,
)

try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    from pymodbus.exceptions import ModbusException
except ImportError:  # pragma: no cover
    ModbusSerialClient = None  # type: ignore
    ModbusTcpClient = None  # type: ignore
    ModbusException = Exception  # type: ignore


class JkBmsPlugin(BMSPluginBase):
    """JK BMS over proprietary UART framing or Modbus RTU V1.0."""
    PLUGIN_META = {
        "plugin_id": "jk_bms",
        "category": "bms",
        "protocols": ["jk02_uart", "modbus_rtu"],
        "models": ["JK-B*", "JK-PB*"],
        "status": "experimental",
        "api_version": 1,
    }

    def __init__(
        self,
        instance_name: str,
        plugin_specific_config: Dict[str, Any],
        main_logger: logging.Logger,
        app_state: Optional["AppState"] = None,
    ):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        self.connection_type = (parse_config_str(plugin_specific_config, "connection_type", "serial") or "serial").lower()
        self.protocol_mode = (parse_config_str(plugin_specific_config, "jk_protocol_mode", "uart") or "uart").lower()
        frame_ver = (parse_config_str(plugin_specific_config, "jk_frame_version", "auto") or "auto").lower()
        if frame_ver in (PROTOCOL_JK02_24S, "24s"):
            self.frame_version: Optional[str] = PROTOCOL_JK02_24S
        elif frame_ver in (PROTOCOL_JK02_32S, "32s"):
            self.frame_version = PROTOCOL_JK02_32S
        else:
            self.frame_version = None  # auto

        self.serial_port = parse_config_str(plugin_specific_config, "serial_port", "COM4")
        self.baud_rate = parse_config_int(plugin_specific_config, "baud_rate", 115200 if self.protocol_mode == "uart" else 115200)
        self.tcp_host = parse_config_str(plugin_specific_config, "tcp_host", "192.168.1.100")
        self.tcp_port = parse_config_int(plugin_specific_config, "tcp_port", 8899)
        self.slave_address = parse_config_int(plugin_specific_config, "slave_address", 1)
        self.timeout = float(parse_config_str(plugin_specific_config, "timeout_seconds", "3") or 3)
        self._static_cache: Dict[str, Any] = {
            BMS_KEY_MANUFACTURER: "JK BMS",
            BMS_KEY_MODEL: "JK-BMS",
            BMS_KEY_SERIAL_NUMBER: f"jk_{self.connection_type}",
            BMS_KEY_FIRMWARE_VERSION: "Unknown",
        }
        self._consecutive_bad_packets = 0

    @property
    def name(self) -> str:
        return "jk_bms"

    @property
    def pretty_name(self) -> str:
        return "JK BMS"

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        return [
            {"name": "connection_type", "type": "select", "options": ["serial", "tcp"], "default": "serial"},
            {"name": "jk_protocol_mode", "type": "select", "options": ["uart", "modbus"], "default": "uart"},
            {"name": "jk_frame_version", "type": "select", "options": ["auto", "jk02_24s", "jk02_32s"], "default": "auto"},
            {"name": "serial_port", "type": "str", "default": "COM4"},
            {"name": "baud_rate", "type": "int", "default": 115200},
            {"name": "tcp_host", "type": "str", "default": "192.168.1.100"},
            {"name": "tcp_port", "type": "int", "default": 8899},
            {"name": "slave_address", "type": "int", "default": 1},
        ]

    def connect(self) -> bool:
        try:
            if self.protocol_mode == "modbus":
                return self._connect_modbus()
            return self._connect_uart()
        except Exception as e:
            self.logger.error(f"JK BMS '{self.instance_name}': connect failed: {e}")
            self._is_connected_flag = False
            self.connection_status = "Connect Failed"
            return False

    def _connect_uart(self) -> bool:
        if self.connection_type == "serial" and serial is None:
            raise ImportError("pyserial is required for JK BMS serial UART mode")
        if self.connection_type == "tcp":
            ok, _, err = check_tcp_port(self.tcp_host, self.tcp_port, timeout=self.timeout, logger_instance=self.logger)
            if not ok:
                self.logger.warning(f"JK BMS TCP check failed: {err}")
                return False
            sock = socket.create_connection((self.tcp_host, self.tcp_port), timeout=self.timeout)
            sock.settimeout(self.timeout)
            self.client = sock
        else:
            self.client = serial.Serial(
                port=self.serial_port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
        self._is_connected_flag = True
        self.connection_status = "connected"
        self.logger.info(f"JK BMS '{self.instance_name}': UART connected ({self.connection_type}).")
        return True

    def _connect_modbus(self) -> bool:
        if ModbusTcpClient is None or ModbusSerialClient is None:
            raise ImportError("pymodbus is required for jk_protocol_mode=modbus")
        if self.connection_type == "tcp":
            self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=self.timeout)
        else:
            self.client = ModbusSerialClient(
                port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                bytesize=8,
                parity="N",
                stopbits=1,
            )
        if not self.client.connect():
            return False
        self._is_connected_flag = True
        self.connection_status = "connected"
        self.logger.info(f"JK BMS '{self.instance_name}': Modbus connected ({self.connection_type}).")
        return True

    def disconnect(self) -> None:
        try:
            if self.client is not None:
                if self.protocol_mode == "modbus":
                    self.client.close()
                elif self.connection_type == "tcp":
                    self.client.close()
                else:
                    if getattr(self.client, "is_open", False):
                        self.client.close()
        except Exception as e:
            self.logger.debug(f"JK BMS disconnect error: {e}")
        finally:
            self.client = None
            self._is_connected_flag = False
            self.connection_status = "disconnected"

    def _uart_exchange(self, command: bytes, settle_s: float = 0.35) -> bytes:
        if self.client is None:
            return b""
        try:
            if self.connection_type == "serial":
                self.client.reset_input_buffer()
                self.client.write(command)
                time.sleep(settle_s)
                waiting = self.client.in_waiting
                data = self.client.read(waiting if waiting else 512)
                # Read a bit more if header incomplete
                if data and data.find(b"\x55\xaa\xeb\x90") >= 0 and len(data) < 150:
                    time.sleep(0.2)
                    extra = self.client.read(self.client.in_waiting or 256)
                    data += extra
                return data or b""
            # TCP
            self.client.sendall(command)
            time.sleep(settle_s)
            chunks = []
            self.client.settimeout(self.timeout)
            try:
                while True:
                    chunk = self.client.recv(512)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    if sum(len(c) for c in chunks) > 600:
                        break
                    self.client.settimeout(0.25)
            except socket.timeout:
                pass
            return b"".join(chunks)
        except Exception as e:
            self.logger.warning(f"JK BMS UART I/O error: {e}")
            self.disconnect()
            return b""

    def get_bms_static_info(self) -> Optional[Dict[str, Any]]:
        if self.protocol_mode == "uart" and self.is_connected:
            raw = self._uart_exchange(JK_UART_CMD_DEVICE_INFO)
            for frame in find_jk_frames(raw):
                info = decode_jk02_device_info(frame)
                if info:
                    if info.get("raw_info_text"):
                        self._static_cache[BMS_KEY_MODEL] = info["raw_info_text"][:64]
                    self._static_cache[BMS_KEY_MANUFACTURER] = info.get("manufacturer", "JK BMS")
                    break
        self._static_cache[BMS_KEY_SERIAL_NUMBER] = (
            f"jk_{self.tcp_host}_{self.tcp_port}" if self.connection_type == "tcp" else f"jk_{self.serial_port}"
        )
        return dict(self._static_cache)

    def read_bms_data(self) -> Optional[Dict[str, Any]]:
        if not self.is_connected:
            return None
        try:
            if self.protocol_mode == "modbus":
                data = self._read_modbus()
            else:
                data = self._read_uart()
            if not data:
                self._consecutive_bad_packets += 1
                if self._consecutive_bad_packets >= 5:
                    self.logger.warning("JK BMS: too many bad packets; disconnecting for reconnect.")
                    self.disconnect()
                    self._consecutive_bad_packets = 0
                return None
            self._consecutive_bad_packets = 0
            data[BMS_PLUGIN_LAST_UPDATE] = datetime.now(timezone.utc).isoformat()
            return data
        except Exception as e:
            self.logger.error(f"JK BMS read_bms_data error: {e}", exc_info=True)
            return None

    def _read_uart(self) -> Optional[Dict[str, Any]]:
        raw = self._uart_exchange(JK_UART_CMD_CELL_INFO)
        if not raw:
            return None
        frames = find_jk_frames(raw)
        if not frames:
            self.logger.debug(f"JK BMS: no valid frames in {len(raw)} bytes")
            return None

        # Prefer configured frame version when set
        if self.frame_version:
            for frame in frames:
                if frame[4] != 0x02:
                    continue
                decoded = decode_jk02_cell_info(frame, self.frame_version)
                if decoded:
                    return self._map_decoded(decoded)
            return None

        picked = pick_best_cell_frame(frames)
        if not picked:
            return None
        _, decoded = picked
        return self._map_decoded(decoded)

    def _map_decoded(self, decoded: Dict[str, Any]) -> Dict[str, Any]:
        temps = decoded.get("temperatures") or []
        balancing = "Active" if decoded.get("balancing") else "None"
        out: Dict[str, Any] = {
            BMS_KEY_SOC: decoded.get("soc"),
            BMS_KEY_SOH: decoded.get("soh"),
            BMS_KEY_VOLTAGE: decoded.get("total_voltage"),
            BMS_KEY_CURRENT: decoded.get("current"),
            BMS_KEY_POWER: decoded.get("power"),
            BMS_KEY_REMAINING_CAPACITY_AH: decoded.get("remaining_ah"),
            BMS_KEY_FULL_CAPACITY_AH: decoded.get("full_ah"),
            BMS_KEY_CYCLE_COUNT: decoded.get("cycles"),
            BMS_KEY_CELL_COUNT: decoded.get("cell_count"),
            BMS_KEY_CELL_VOLTAGES_ALL: decoded.get("cell_voltages") or [],
            BMS_KEY_CELL_VOLTAGE_MIN: decoded.get("cell_voltage_min"),
            BMS_KEY_CELL_VOLTAGE_MAX: decoded.get("cell_voltage_max"),
            BMS_KEY_CELL_VOLTAGE_AVG: decoded.get("cell_voltage_avg"),
            BMS_KEY_CELL_VOLTAGE_DIFF: decoded.get("cell_voltage_delta"),
            BMS_KEY_LOWEST_CELL_NUMBER: decoded.get("cell_min_number"),
            BMS_KEY_HIGHEST_CELL_NUMBER: decoded.get("cell_max_number"),
            BMS_KEY_TEMPERATURES_ALL: temps,
            BMS_KEY_TEMP_MAX: max(temps) if temps else None,
            BMS_KEY_TEMP_MIN: min(temps) if temps else None,
            BMS_KEY_STATUS_TEXT: decoded.get("status", "Unknown"),
            BMS_KEY_CHARGE_FET_ON: decoded.get("charge_fet"),
            BMS_KEY_DISCHARGE_FET_ON: decoded.get("discharge_fet"),
            BMS_KEY_CELLS_BALANCING: balancing,
            BMS_KEY_ACTIVE_ALARMS_LIST: decoded.get("alarms") or [],
            BMS_KEY_ACTIVE_WARNINGS_LIST: [],
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: temps[0] if temps else None,
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms",
        }
        return out

    def _modbus_read_holding(self, address: int, count: int):
        assert self.client is not None
        try:
            return self.client.read_holding_registers(address=address, count=count, slave=self.slave_address)
        except TypeError:
            return self.client.read_holding_registers(address, count, unit=self.slave_address)

    def _read_modbus(self) -> Optional[Dict[str, Any]]:
        """
        JK BMS RS485 Modbus V1.0 subset (holding registers).
        Addresses commonly used by community integrations (phinix / YamBMS style).
        """
        try:
            # Cell voltages: 0x1200.. often 16-32 cells as uint16 mV — try bulk at 0x1200
            cells_result = self._modbus_read_holding(0x1200, 32)
            if cells_result.isError():
                # Alternate base used by some firmwares
                cells_result = self._modbus_read_holding(0x00, 32)
            cell_voltages = []
            if not cells_result.isError() and cells_result.registers:
                for raw in cells_result.registers:
                    v = raw * 0.001
                    if 0.5 <= v <= 5.0:
                        cell_voltages.append(round(v, 3))

            # Core status block — several firmwares map SOC near 0x1268 / capacity areas.
            # Read a diagnostic window and pick plausible SOC/voltage/current.
            status = self._modbus_read_holding(0x1290, 40)
            soc = voltage = current = None
            temps: List[float] = []
            if not status.isError() and status.registers:
                regs = status.registers
                # Heuristic within known ranges for V1.0 maps
                for r in regs[:10]:
                    if soc is None and 0 < r <= 100:
                        soc = float(r)
                # Prefer explicit documented-ish offsets when present in window:
                # Many maps: pack voltage as uint16 0.01V, current int16 0.01A near capacity block.
                if len(regs) > 8:
                    cand_v = regs[0] * 0.01
                    if 10 <= cand_v <= 100:
                        voltage = cand_v
                    cand_i = regs[1] if regs[1] < 32768 else regs[1] - 65536
                    current = cand_i * 0.01  # may still need sign flip per device

            if voltage is None and cell_voltages:
                voltage = sum(cell_voltages)
            if current is None:
                current = 0.0
            # App convention +discharge
            app_current = -float(current)
            power = (voltage or 0) * app_current
            if soc is None:
                return None

            decoded = {
                "soc": soc,
                "soh": None,
                "total_voltage": round(voltage, 3) if voltage else None,
                "current": round(app_current, 3),
                "power": round(power, 1),
                "remaining_ah": None,
                "full_ah": None,
                "cycles": None,
                "cell_count": len(cell_voltages),
                "cell_voltages": cell_voltages,
                "temperatures": temps,
                "charge_fet": None,
                "discharge_fet": None,
                "balancing": False,
                "status": "Discharging" if app_current > 0.5 else ("Charging" if app_current < -0.5 else "Idle"),
                "alarms": [],
            }
            if cell_voltages:
                decoded["cell_voltage_min"] = min(cell_voltages)
                decoded["cell_voltage_max"] = max(cell_voltages)
                decoded["cell_voltage_avg"] = round(sum(cell_voltages) / len(cell_voltages), 3)
                decoded["cell_voltage_delta"] = round(decoded["cell_voltage_max"] - decoded["cell_voltage_min"], 3)
                decoded["cell_min_number"] = cell_voltages.index(decoded["cell_voltage_min"]) + 1
                decoded["cell_max_number"] = cell_voltages.index(decoded["cell_voltage_max"]) + 1
            return self._map_decoded(decoded)
        except ModbusException as e:
            self.logger.warning(f"JK BMS Modbus error: {e}")
            self.disconnect()
            return None
