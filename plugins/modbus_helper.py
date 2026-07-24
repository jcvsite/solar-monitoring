# plugins/modbus_helper.py
"""
Shared Modbus Client Helpers

This module centralizes pymodbus client creation and register read helpers with
compatibility for both unit= and slave= keyword APIs across pymodbus versions.
It is used by Solis and other Modbus-based plugins.

Features:
- create_modbus_client for TCP and serial RTU
- safe_read_holding_registers / safe_read_input_registers wrappers
- decode_registers_by_map for typed register maps
- ExceptionResponse and connection error handling
- Logging-friendly failure returns for plugin callers

Supported Consumers:
- Inverter plugins using Modbus TCP/RTU
- plugins/inverter/modbus_inverter_base.py
- plugins/inverter/solis_modbus_plugin.py (and related migrations)

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    from pymodbus.pdu import ExceptionResponse
except ImportError:  # pragma: no cover
    ModbusSerialClient = None  # type: ignore
    ModbusTcpClient = None  # type: ignore
    ExceptionResponse = tuple  # type: ignore


def create_modbus_client(
    connection_type: str,
    *,
    host: Optional[str] = None,
    port: int = 502,
    serial_port: Optional[str] = None,
    baudrate: int = 9600,
    parity: str = "N",
    stopbits: int = 1,
    bytesize: int = 8,
    timeout: float = 3.0,
) -> Any:
    """Create a Modbus TCP or RTU client. Raises ImportError if pymodbus missing."""
    if ModbusTcpClient is None or ModbusSerialClient is None:
        raise ImportError("pymodbus is required for Modbus plugins")
    conn = (connection_type or "tcp").lower()
    if conn == "tcp":
        return ModbusTcpClient(host=host, port=port, timeout=timeout)
    return ModbusSerialClient(
        port=serial_port,
        baudrate=baudrate,
        parity=parity,
        stopbits=stopbits,
        bytesize=bytesize,
        timeout=timeout,
    )


def _call_with_slave_compat(method: Callable, address: int, count: int, slave: int = 1, **kwargs):
    """
    Call a pymodbus read method across 3.x API variants.

    Compatibility matrix:
    - pymodbus <=3.6: method(address, count, unit=/slave=)
    - pymodbus ~3.7–3.10: method(address, count=count, slave=)  (count often keyword-only)
    - pymodbus >=3.11: method(address, count=count, device_id=)
    """
    attempts = (
        # Newest first (keyword-only count + device_id)
        lambda: method(address, count=count, device_id=slave, **kwargs),
        lambda: method(address, count=count, slave=slave, **kwargs),
        lambda: method(address, count=count, unit=slave, **kwargs),
        # Older positional count + unit/slave
        lambda: method(address, count, slave=slave, **kwargs),
        lambda: method(address, count, unit=slave, **kwargs),
        # Last resort: no slave/unit/device_id
        lambda: method(address, count=count, **kwargs),
        lambda: method(address, count, **kwargs),
    )
    last_err: Optional[BaseException] = None
    for attempt in attempts:
        try:
            return attempt()
        except TypeError as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise TypeError(f"Unable to call {getattr(method, '__name__', method)} with any known pymodbus signature")


def safe_read_holding_registers(client: Any, address: int, count: int, slave: int = 1, logger_instance: Optional[logging.Logger] = None):
    """Read holding registers with slave/unit compatibility."""
    log = logger_instance or logger
    if client is None:
        raise ConnectionError("Modbus client is None")
    result = _call_with_slave_compat(client.read_holding_registers, address, count, slave=slave)
    if isinstance(result, ExceptionResponse) or (hasattr(result, "isError") and result.isError()):
        log.debug("Holding register read error @%s count=%s: %s", address, count, result)
    return result


def safe_read_input_registers(client: Any, address: int, count: int, slave: int = 1, logger_instance: Optional[logging.Logger] = None):
    """Read input registers with slave/unit compatibility."""
    log = logger_instance or logger
    if client is None:
        raise ConnectionError("Modbus client is None")
    result = _call_with_slave_compat(client.read_input_registers, address, count, slave=slave)
    if isinstance(result, ExceptionResponse) or (hasattr(result, "isError") and result.isError()):
        log.debug("Input register read error @%s count=%s: %s", address, count, result)
    return result


def decode_uint16(registers: List[int], index: int) -> Optional[int]:
    if index < 0 or index >= len(registers):
        return None
    return int(registers[index]) & 0xFFFF


def decode_int16(registers: List[int], index: int) -> Optional[int]:
    val = decode_uint16(registers, index)
    if val is None:
        return None
    return val - 0x10000 if val >= 0x8000 else val


def decode_uint32_be(registers: List[int], index: int) -> Optional[int]:
    if index < 0 or index + 1 >= len(registers):
        return None
    return ((registers[index] & 0xFFFF) << 16) | (registers[index + 1] & 0xFFFF)


def decode_uint32_le(registers: List[int], index: int) -> Optional[int]:
    if index < 0 or index + 1 >= len(registers):
        return None
    return ((registers[index + 1] & 0xFFFF) << 16) | (registers[index] & 0xFFFF)


def decode_registers_by_map(
    registers: List[int],
    register_map: Dict[str, Dict[str, Any]],
    start_addr: int,
) -> Dict[str, Any]:
    """
    Decode a contiguous register block using a simple map:
    {name: {addr, type, scale?, offset?}}
    Types: uint16, int16, uint32, uint32_le
    """
    decoded: Dict[str, Any] = {}
    for key, info in register_map.items():
        addr = info.get("addr")
        if addr is None:
            continue
        idx = addr - start_addr
        reg_type = info.get("type", "uint16")
        if reg_type == "uint16":
            val = decode_uint16(registers, idx)
        elif reg_type == "int16":
            val = decode_int16(registers, idx)
        elif reg_type in ("uint32", "uint32_be"):
            val = decode_uint32_be(registers, idx)
        elif reg_type == "uint32_le":
            val = decode_uint32_le(registers, idx)
        else:
            val = decode_uint16(registers, idx)
        if val is None:
            continue
        scale = info.get("scale", 1)
        offset = info.get("offset", 0)
        if scale != 1 or offset:
            val = float(val) * float(scale) + float(offset)
        decoded[key] = val
    return decoded
