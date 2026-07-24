# plugins/battery/daly_bms_decoder.py
"""
Daly Smart BMS Frame Decoder

This module builds host queries and parses Daly Smart BMS UART/RS485 responses
(protocol ~V1.2), including SOC/pack metrics, temperatures, MOSFET state, cell
voltage frames, and fault bitfields.

Features:
- Query frame construction with checksum
- Response frame finder for buffered streams
- Parsers for data IDs 0x90, 0x92, 0x93, 0x95, 0x98
- Shared helpers used by DalyBmsPlugin and unit tests

Supported Models:
- Daly Smart BMS (UART / RS485)
- Compatible Daly protocol clones (~V1.2 framing)

Protocol Reference: Daly Smart BMS UART/RS485 Protocol (~V1.2)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def build_query(data_id: int) -> bytes:
    """Host query: A5 40 <id> 08 + 8 zero bytes + checksum."""
    frame = bytearray([0xA5, 0x40, data_id & 0xFF, 0x08] + [0x00] * 8)
    frame.append(_checksum(frame))
    return bytes(frame)


def find_responses(buffer: bytes) -> List[bytes]:
    frames: List[bytes] = []
    i = 0
    while i + 13 <= len(buffer):
        if buffer[i] == 0xA5 and buffer[i + 1] in (0x01, 0x40):
            chunk = buffer[i : i + 13]
            if _checksum(chunk[:-1]) == chunk[-1]:
                frames.append(bytes(chunk))
                i += 13
                continue
        i += 1
    return frames


def parse_0x90(frame: bytes) -> Optional[Dict[str, Any]]:
    """Voltage (0.1V), current (0.1A offset 30000), SOC (0.1%)."""
    if len(frame) < 13 or frame[2] != 0x90:
        return None
    d = frame[4:12]
    voltage = ((d[0] << 8) | d[1]) / 10.0
    current = (((d[4] << 8) | d[5]) - 30000) / 10.0
    soc = ((d[6] << 8) | d[7]) / 10.0
    return {"voltage_v": voltage, "current_a": current, "soc": soc}


def parse_0x93(frame: bytes) -> Optional[Dict[str, Any]]:
    if len(frame) < 13 or frame[2] != 0x93:
        return None
    d = frame[4:12]
    return {
        "charge_fet": bool(d[0]),
        "discharge_fet": bool(d[1]),
        "status_code": d[2],
    }


def parse_0x92(frame: bytes) -> Optional[Dict[str, Any]]:
    if len(frame) < 13 or frame[2] != 0x92:
        return None
    d = frame[4:12]
    # max/min temp with 40 offset
    tmax = d[0] - 40
    tmin = d[2] - 40
    return {"temp_max_c": float(tmax), "temp_min_c": float(tmin), "temps_c": [float(tmax), float(tmin)]}


def parse_0x95_cell_frame(frame: bytes) -> Optional[Tuple[int, List[float]]]:
    """Returns (frame_number, up to 3 cell voltages in V)."""
    if len(frame) < 13 or frame[2] != 0x95:
        return None
    d = frame[4:12]
    frame_no = d[0]
    if frame_no == 0xFF:
        return None
    cells = []
    for i in range(3):
        off = 1 + i * 2
        mv = (d[off] << 8) | d[off + 1]
        if mv == 0:
            continue
        cells.append(mv / 1000.0)
    return frame_no, cells


def parse_0x98(frame: bytes) -> List[str]:
    if len(frame) < 13 or frame[2] != 0x98:
        return []
    d = frame[4:12]
    alarms = []
    # Bit flags — surface any non-zero byte as generic alarm for UI
    if any(d):
        alarms.append("Daly protection/alarm active")
    return alarms
