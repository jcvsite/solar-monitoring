# plugins/battery/pylontech_bms_decoder.py
"""
Pylontech Console Response Decoder

This module parses Pylontech console / RS485 text responses such as `pwr`
status lines and `info` blocks into structured dictionaries for the plugin.

Features:
- Flexible SOC / voltage / current token extraction
- Info-block field parsing for identity metadata
- Tolerant regex matching across firmware text variants
- Shared helpers used by PylontechBmsPlugin and unit tests

Supported Models:
- Pylontech US2000 / US3000 / Force console interfaces

Protocol Reference: Pylontech Console / RS485 Text Protocol
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional


def parse_pwr_line(text: str) -> Optional[Dict[str, Any]]:
    """
    Parse a `pwr` console response line.
    Formats vary; look for SOC / Voltage / Current tokens.
    """
    if not text:
        return None
    out: Dict[str, Any] = {}
    # Common patterns: SOC: 55%  or  SOC  55
    m = re.search(r"SOC\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?", text, re.I)
    if m:
        out["soc"] = float(m.group(1))
    m = re.search(r"Volt(?:age)?\s*[:=]?\s*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        out["voltage_v"] = float(m.group(1))
    m = re.search(r"Curr(?:ent)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)", text, re.I)
    if m:
        out["current_a"] = float(m.group(1))
    m = re.search(r"Temp(?:erature)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)", text, re.I)
    if m:
        out["temp_c"] = float(m.group(1))
    return out or None


def parse_info_block(text: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    m = re.search(r"Manufacturer\s*[:=]\s*(.+)", text, re.I)
    if m:
        info["manufacturer"] = m.group(1).strip()
    m = re.search(r"Device\s*Name\s*[:=]\s*(.+)", text, re.I)
    if m:
        info["model"] = m.group(1).strip()
    m = re.search(r"Barcode\s*[:=]\s*(\S+)", text, re.I)
    if m:
        info["serial"] = m.group(1).strip()
    return info
