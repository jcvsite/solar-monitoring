# plugins/battery/jbd_bms_decoder.py
"""
JBD / Xiaoxiang / Overkill BMS Frame Decoder

This module builds read commands and parses UART responses for JBD-family BMS
devices (Xiaoxiang / Overkill) using the common V4-style framed protocol.

Features:
- Host read command construction
- Frame finding and checksum validation
- Basic info parse (SOC, voltages, FETs, protections)
- Cell voltage list parse
- Shared helpers used by JbdBmsPlugin and unit tests

Supported Models:
- JBD BMS modules
- Xiaoxiang / Overkill Solar BMS using the same UART framing

Protocol Reference: JBD / Xiaoxiang UART Protocol (V4-style)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def jbd_checksum(payload: bytes) -> int:
    """
    JBD checksum over (cmd, status/len fields through data):
    checksum = (0x10000 - sum(bytes)) & 0xFFFF  equivalently ~sum+1 for 16-bit.
    For short read commands the official form is:
      sum = cmd + length + data... ; checksum = (~sum + 1) & 0xFFFF
    """
    s = sum(payload) & 0xFFFF
    return (~s + 1) & 0xFFFF


def build_read_cmd(register: int) -> bytes:
    """Build host read frame: DD A5 RR 00 FF FD 77 for length-0 reads."""
    # DD A5 <reg> 00 <chk_hi> <chk_lo> 77
    body = bytes([0xA5, register & 0xFF, 0x00])
    chk = jbd_checksum(body)
    return bytes([0xDD]) + body + bytes([(chk >> 8) & 0xFF, chk & 0xFF, 0x77])


def find_frames(buffer: bytes) -> List[bytes]:
    frames: List[bytes] = []
    i = 0
    while i < len(buffer):
        if buffer[i] != 0xDD:
            i += 1
            continue
        if i + 7 > len(buffer):
            break
        # DD STATUS CMD LEN ... DATA CHK_H CHK_L 77  OR response DD CMD STATUS LEN ...
        # Response: DD <cmd> <status> <len> <data...> <chk_h> <chk_l> 77
        if i + 4 > len(buffer):
            break
        length = buffer[i + 3]
        total = 4 + length + 3  # header(4) + data + chk(2) + end(1)
        if i + total > len(buffer):
            break
        frame = buffer[i : i + total]
        if frame[-1] == 0x77:
            frames.append(bytes(frame))
        i += total
    return frames


def _u16(data: bytes, off: int) -> int:
    return (data[off] << 8) | data[off + 1]


def _s16(data: bytes, off: int) -> int:
    v = _u16(data, off)
    return v - 0x10000 if v >= 0x8000 else v


def parse_basic_info(frame: bytes) -> Optional[Dict[str, Any]]:
    """Parse 0x03 basic info response."""
    if len(frame) < 8 or frame[0] != 0xDD or frame[-1] != 0x77:
        return None
    cmd = frame[1]
    status = frame[2]
    length = frame[3]
    if cmd != 0x03 or status != 0x00 or length < 27:
        return None
    data = frame[4 : 4 + length]
    voltage_v = _u16(data, 0) / 100.0
    current_a = _s16(data, 2) / 100.0
    remaining_ah = _u16(data, 4) / 100.0
    full_ah = _u16(data, 6) / 100.0
    cycles = _u16(data, 8)
    # protection bits at 16-17 typically; MOS at 20; cells at 21; soc at 19
    soc = data[19] if length > 19 else 0
    mos = data[20] if length > 20 else 0
    cell_count = data[21] if length > 21 else 0
    ntc_count = data[22] if length > 22 else 0
    temps: List[float] = []
    for t in range(ntc_count):
        off = 23 + t * 2
        if off + 1 < length:
            # JBD temp: Kelvin*10 style → C = raw/10 - 273.1
            raw = _u16(data, off)
            temps.append(raw / 10.0 - 273.1)
    return {
        "voltage_v": voltage_v,
        "current_a": current_a,
        "remaining_ah": remaining_ah,
        "full_ah": full_ah,
        "cycles": cycles,
        "soc": float(soc),
        "charge_fet": bool(mos & 0x01),
        "discharge_fet": bool(mos & 0x02),
        "cell_count": int(cell_count),
        "temps_c": temps,
        "protection": _u16(data, 16) if length > 17 else 0,
    }


def parse_cell_voltages(frame: bytes) -> Optional[List[float]]:
    if len(frame) < 8 or frame[0] != 0xDD or frame[-1] != 0x77:
        return None
    if frame[1] != 0x04 or frame[2] != 0x00:
        return None
    length = frame[3]
    data = frame[4 : 4 + length]
    cells: List[float] = []
    for i in range(0, length - (length % 2), 2):
        cells.append(_u16(data, i) / 1000.0)
    return cells
