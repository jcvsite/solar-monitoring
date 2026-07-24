# plugins/battery/jk_bms_decoder.py
"""
JK BMS JK02 Frame Decoder

This module provides frame finding and decode helpers for JK (Jikong) BMS
devices using the JK02 UART protocol. It supports cell/status and device-info
frames used by the JK BMS plugin.

Features:
- JK02 header detection (55 AA EB 90) and CRC8 validation
- Cell/status info decode for 24s and 32s layouts
- Device info frame decode (model, hardware, firmware)
- Frame selection helpers when multiple frames are buffered
- UART trigger command constants for cell and device info reads

Frame Layout (response):
- 0..3  header 55 AA EB 90
- 4     frame type (0x02 = cell/status info, 0x01 = settings, 0x03 = device info)
- 5     frame counter
- 6..   payload
- last  CRC8 = sum(bytes[0..n-2]) & 0xFF

Supported Models:
- JK BMS GPS/UART port devices (JK02 protocol)
- Compatible JK packs using the same framing

Protocol Reference: JK BMS JK02 UART
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

JK_HEADER = bytes([0x55, 0xAA, 0xEB, 0x90])
FRAME_TYPE_CELL_INFO = 0x02
FRAME_TYPE_DEVICE_INFO = 0x03

# UART trigger commands (Modbus-like write to register 0x16xx) used by JK BMS GPS/UART port.
# These match the widely used esphome-jk-bms / community command set.
JK_UART_CMD_CELL_INFO = bytes([0x01, 0x10, 0x16, 0x1E, 0x00, 0x01, 0x02, 0x00, 0x00, 0xD2, 0x2F])
JK_UART_CMD_DEVICE_INFO = bytes([0x01, 0x10, 0x16, 0x1C, 0x00, 0x01, 0x02, 0x00, 0x00, 0xD3, 0xCD])

PROTOCOL_JK02_24S = "jk02_24s"
PROTOCOL_JK02_32S = "jk02_32s"

MIN_CELL_V = 0.5
MAX_CELL_V = 5.0


def jk_crc8(data: bytes) -> int:
    """JK frame CRC: low 8 bits of the sum of all bytes except the CRC itself."""
    return sum(data) & 0xFF


def find_jk_frames(buffer: bytes) -> List[bytes]:
    """Extract candidate JK frames from a receive buffer."""
    frames: List[bytes] = []
    i = 0
    while True:
        idx = buffer.find(JK_HEADER, i)
        if idx < 0:
            break
        # Typical cell-info frames are ~300 bytes; accept 50..512
        for length in (300, 320, 292, 280, 256, 200, 150, 100):
            end = idx + length
            if end <= len(buffer):
                candidate = buffer[idx:end]
                if len(candidate) >= 6 and (jk_crc8(candidate[:-1]) == candidate[-1]):
                    frames.append(candidate)
                    i = end
                    break
        else:
            # Fallback: try any length from 50 to remaining where CRC matches
            matched = False
            for length in range(50, min(513, len(buffer) - idx + 1)):
                candidate = buffer[idx : idx + length]
                if jk_crc8(candidate[:-1]) == candidate[-1]:
                    frames.append(candidate)
                    i = idx + length
                    matched = True
                    break
            if not matched:
                i = idx + 4
    return frames


def _u16(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def _i16(data: bytes, offset: int) -> int:
    val = _u16(data, offset)
    return val - 0x10000 if val & 0x8000 else val


def _u32(data: bytes, offset: int) -> int:
    return (
        data[offset]
        | (data[offset + 1] << 8)
        | (data[offset + 2] << 16)
        | (data[offset + 3] << 24)
    )


def _i32(data: bytes, offset: int) -> int:
    val = _u32(data, offset)
    return val - 0x100000000 if val & 0x80000000 else val


def detect_protocol_version(frame: bytes) -> str:
    """Prefer 32S when the frame is long enough and looks valid at 32S offsets."""
    if len(frame) >= 300:
        # 32S uses initial offset=16 before the second offset doubling.
        return PROTOCOL_JK02_32S
    return PROTOCOL_JK02_24S


def decode_jk02_cell_info(frame: bytes, protocol: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Decode a JK02 type-0x02 cell/status frame.

    """
    if len(frame) < 150 or frame[:4] != JK_HEADER:
        return None
    if frame[4] != FRAME_TYPE_CELL_INFO:
        return None
    if jk_crc8(frame[:-1]) != frame[-1]:
        return None

    protocol = protocol or detect_protocol_version(frame)
    # First offset: 0 for 24S, 16 for 32S (extra cell voltage slots)
    offset = 16 if protocol == PROTOCOL_JK02_32S else 0
    cells = 24 + (offset // 2)  # 24 or 32

    cell_voltages: List[float] = []
    for i in range(cells):
        pos = i * 2 + 6
        if pos + 1 >= len(frame):
            break
        mv = _u16(frame, pos)
        volts = mv * 0.001
        if MIN_CELL_V <= volts <= MAX_CELL_V:
            cell_voltages.append(round(volts, 3))
        elif mv == 0:
            continue
        else:
            # Out-of-range: skip rather than poison averages
            continue

    # After cell/resistance block, esphome doubles the offset for the remaining fields.
    offset = offset * 2

    required = 168 + offset
    if len(frame) < required:
        # Try 24S layout if 32S failed length check
        if protocol == PROTOCOL_JK02_32S:
            return decode_jk02_cell_info(frame, PROTOCOL_JK02_24S)
        return None

    total_voltage = _u32(frame, 118 + offset) * 0.001
    # JK reports charge current as positive; app convention is +discharge / -charge.
    jk_current = _i32(frame, 126 + offset) * 0.001
    app_current = -jk_current
    power = total_voltage * app_current

    temp1 = _i16(frame, 130 + offset) * 0.1
    temp2 = _i16(frame, 132 + offset) * 0.1
    # 24S: errors at 134; 32S: mosfet temp at 134, errors at 136 — handle both carefully
    if protocol == PROTOCOL_JK02_32S:
        mosfet_temp = _i16(frame, 134 + offset) * 0.1
        errors = _u16(frame, 136 + offset)
    else:
        mosfet_temp = None
        errors = _u32(frame, 134 + offset)

    balancing = frame[140 + offset] != 0
    soc = float(frame[141 + offset])
    remaining_ah = _u32(frame, 142 + offset) * 0.001
    full_ah = _u32(frame, 146 + offset) * 0.001
    cycles = _u32(frame, 150 + offset)
    soh = float(frame[158 + offset]) if (158 + offset) < len(frame) else None
    charge_fet = bool(frame[166 + offset]) if (166 + offset) < len(frame) else None
    discharge_fet = bool(frame[167 + offset]) if (167 + offset) < len(frame) else None

    temps = [t for t in (temp1, temp2, mosfet_temp) if t is not None and -40 <= t <= 100]

    alarms: List[str] = []
    if isinstance(errors, int) and errors:
        alarms.append(f"JK fault bitmask 0x{errors:X}")

    if app_current > 0.5:
        status = "Discharging"
    elif app_current < -0.5:
        status = "Charging"
    else:
        status = "Idle"

    valid_cells = cell_voltages
    result: Dict[str, Any] = {
        "protocol": protocol,
        "cell_voltages": valid_cells,
        "cell_count": len(valid_cells),
        "total_voltage": round(total_voltage, 3) if total_voltage else (
            round(sum(valid_cells), 3) if valid_cells else None
        ),
        "current": round(app_current, 3),
        "power": round(power, 1),
        "soc": max(0.0, min(100.0, soc)),
        "soh": max(0.0, min(100.0, soh)) if soh is not None else None,
        "remaining_ah": round(remaining_ah, 3),
        "full_ah": round(full_ah, 3),
        "cycles": cycles,
        "temperatures": temps,
        "charge_fet": charge_fet,
        "discharge_fet": discharge_fet,
        "balancing": balancing,
        "status": status,
        "alarms": alarms,
    }
    if valid_cells:
        result["cell_voltage_min"] = min(valid_cells)
        result["cell_voltage_max"] = max(valid_cells)
        result["cell_voltage_avg"] = round(sum(valid_cells) / len(valid_cells), 3)
        result["cell_voltage_delta"] = round(result["cell_voltage_max"] - result["cell_voltage_min"], 3)
        result["cell_min_number"] = valid_cells.index(result["cell_voltage_min"]) + 1
        result["cell_max_number"] = valid_cells.index(result["cell_voltage_max"]) + 1
    return result


def decode_jk02_device_info(frame: bytes) -> Optional[Dict[str, Any]]:
    """Best-effort device info decode from type 0x03 frames."""
    if len(frame) < 100 or frame[:4] != JK_HEADER or frame[4] != FRAME_TYPE_DEVICE_INFO:
        return None
    if jk_crc8(frame[:-1]) != frame[-1]:
        return None
    # Vendor string / hardware / software often appear as ASCII after offset 6.
    ascii_bytes = bytes(b if 32 <= b < 127 else 0 for b in frame[6:100])
    text = ascii_bytes.replace(b"\x00", b" ").decode("ascii", errors="ignore")
    parts = [p.strip() for p in text.split() if p.strip()]
    return {
        "raw_info_text": " ".join(parts)[:120] if parts else None,
        "manufacturer": "JK BMS",
    }


def pick_best_cell_frame(frames: List[bytes]) -> Optional[Tuple[bytes, Dict[str, Any]]]:
    """Return the first successfully decoded cell-info frame."""
    for frame in frames:
        if frame[4] != FRAME_TYPE_CELL_INFO:
            continue
        decoded = decode_jk02_cell_info(frame)
        if decoded and decoded.get("cell_count", 0) > 0:
            return frame, decoded
        # Also accept frames with SOC even if cells filtered out
        if decoded and decoded.get("soc") is not None:
            return frame, decoded
    return None
