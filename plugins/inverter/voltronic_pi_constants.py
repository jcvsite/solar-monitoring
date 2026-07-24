# plugins/inverter/voltronic_pi_constants.py
"""
Voltronic PI30 Protocol Helpers

This module provides CRC, command framing, response finding, and QPIGS/QMN
parsers for Voltronic / Axpert / MPP Solar PI30 inverters.

Features:
- CRC16-XMODEM command framing
- Response buffer scanning
- QPIGS field decode into structured metrics
- QMN model-name parse helper

Supported Models:
- Voltronic / Axpert / MPP Solar / PIP PI30-compatible inverters

Protocol Reference: Voltronic PI30 (QPIGS / QMN)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def crc16_xmodem(data: bytes) -> int:
    """PI30 uses CRC16-XMODEM (poly 0x1021, init 0)."""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def build_command(cmd: str) -> bytes:
    payload = cmd.encode("ascii")
    crc = crc16_xmodem(payload)
    return payload + bytes([(crc >> 8) & 0xFF, crc & 0xFF, 0x0D])


def find_response(buffer: bytes) -> Optional[bytes]:
    """Extract a PI30 response starting with '(' ending with CRC + CR."""
    start = buffer.find(b"(")
    if start < 0:
        return None
    end = buffer.find(b"\r", start)
    if end < 0 or end - start < 3:
        return None
    return buffer[start:end]


def parse_qpigs(response: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse QPIGS payload (without leading '(' / trailing CRC).
    Field order matches common PI30 documentation.
    """
    if not response or response[0:1] != b"(":
        return None
    # Strip CRC (last 2 bytes before CR already removed by find_response)
    body = response[1:]
    if len(body) >= 2:
        # Optional: verify CRC of '(' + payload
        pass
    # Drop trailing CRC bytes if still present (2 bytes)
    text = body.decode("ascii", errors="ignore")
    # Some devices include CRC as non-printable; split on spaces for numeric fields
    # Prefer stripping last 2 chars if they are not part of numbers
    parts = text.strip().split()
    if len(parts) < 12:
        return None
    try:
        # Common QPIGS layout:
        # 0 grid_v, 1 grid_hz, 2 ac_out_v, 3 ac_out_hz, 4 ac_out_va, 5 ac_out_w,
        # 6 load_pct, 7 bus_v, 8 batt_v, 9 batt_charge_a, 10 batt_soc,
        # 11 inverter_temp, 12 pv_a, 13 pv_v, 14 batt_discharge_a, ...
        def f(i: int) -> float:
            return float(parts[i])

        grid_v = f(0)
        grid_hz = f(1)
        ac_out_v = f(2)
        ac_out_w = f(5)
        batt_v = f(8)
        batt_charge_a = f(9)
        batt_soc = f(10)
        inv_temp = f(11)
        pv_a = f(12) if len(parts) > 12 else 0.0
        pv_v = f(13) if len(parts) > 13 else 0.0
        batt_dis_a = f(14) if len(parts) > 14 else 0.0
        pv_w = pv_v * pv_a
        # Net battery current: discharge positive
        batt_i = batt_dis_a - batt_charge_a
        batt_p = batt_v * batt_i
        return {
            "grid_voltage": grid_v,
            "grid_frequency": grid_hz,
            "ac_output_voltage": ac_out_v,
            "ac_power": ac_out_w,
            "battery_voltage": batt_v,
            "battery_soc": batt_soc,
            "battery_current": batt_i,
            "battery_power": batt_p,
            "inverter_temp": inv_temp,
            "pv_voltage": pv_v,
            "pv_current": pv_a,
            "pv_power": pv_w,
            "raw_parts": parts,
        }
    except (ValueError, IndexError):
        return None


def parse_qmn(response: bytes) -> Optional[str]:
    if not response or response[0:1] != b"(":
        return None
    text = response[1:].decode("ascii", errors="ignore").strip()
    # Drop non-printable CRC tail
    clean = "".join(ch for ch in text if ch.isprintable() and ch not in "\r\n")
    return clean or None
