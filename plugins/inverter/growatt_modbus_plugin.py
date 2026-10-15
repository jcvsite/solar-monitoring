# plugins/inverter/growatt_modbus_plugin.py
"""
Growatt Modbus Inverter Plugin

This plugin communicates with Growatt hybrid inverters using Modbus TCP and Serial protocols.
It supports comprehensive monitoring of inverter status, power generation, battery management,
and energy statistics for Growatt inverter models using the V1.24 protocol specification.

Features:
- Dual connection support (Modbus TCP and Serial)
- Complete V1.24 protocol implementation (42+ input registers, 35+ holding registers)
- Real-time monitoring of PV generation, battery status, and grid interaction
- 3-phase system support for applicable models
- Storage/hybrid inverter support (MIX/SPH series)
- Energy statistics tracking (daily, total lifetime values)
- Temperature monitoring from multiple sensors
- Comprehensive fault and warning code processing
- Battery management system integration
- Configuration parameter access (writable registers)

Supported Models:
- Growatt MIC series (grid-tie inverters)
- Growatt MIX series (hybrid inverters)
- Growatt SPH series (storage inverters)
- Compatible Growatt inverter models with V1.24 protocol

Protocol Reference: Growatt Modbus RTU Protocol V1.24 (2020 edition)
GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

import logging
import struct
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

# This plugin requires the pymodbus library.
try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException, ConnectionException as ModbusConnectionException
    from pymodbus.pdu import ExceptionResponse
except ImportError:
    ModbusSerialClient = None
    ModbusTcpClient = None

if TYPE_CHECKING:
    from core.app_state import AppState

from .growatt_modbus_constants import (
    GROWATT_INPUT_REGISTERS,
    GROWATT_HOLD_REGISTERS,
    GROWATT_STATUS_CODES,
    GROWATT_STORAGE_WORK_MODES,
    GROWATT_WIT_INPUT_REGISTERS,
    GROWATT_WIT_INPUT_START,
    GROWATT_WIT_INPUT_COUNT,
    GROWATT_SPF_INPUT_REGISTERS,
    GROWATT_SPF_INPUT_COUNT,
    GROWATT_TLXH_INPUT_REGISTERS,
    GROWATT_TLXH_INPUT_START,
)
from plugins.plugin_interface import DevicePlugin, StandardDataKeys, derive_battery_charge_state
from plugins.plugin_utils import check_tcp_port, check_icmp_ping
from plugins.modbus_helper import safe_read_holding_registers, safe_read_input_registers
from enum import Enum

UNKNOWN = "Unknown"

class ConnectionType(str, Enum):
    """Enumeration for the supported connection types."""
    TCP = "tcp"
    SERIAL = "serial"

class GrowattModbusPlugin(DevicePlugin):
    PLUGIN_META = {
        "plugin_id": "growatt_modbus",
        "category": "inverter",
        "protocols": ["modbus_tcp", "modbus_rtu"],
        "models": ["MIX", "SPH", "MIC", "WIT", "SPF", "TL-XH"],
        "status": "testing",
        "api_version": 1,
    }
    """
    A plugin to interact with Growatt inverters via Modbus TCP or RTU.

    This class implements the DevicePlugin interface to provide a standardized
    way of connecting to, reading data from, and interpreting data from Growatt
    inverters. It handles Modbus communication, register decoding, data
    standardization, and error handling.

    The plugin supports reading both static device information and dynamic
    operational data from Growatt inverters using either Modbus TCP (network)
    or Modbus RTU (serial) communication protocols. It supports both standard
    inverter and storage/hybrid inverter models.
    """

    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        """
        Initializes the GrowattModbusPlugin instance.

        Args:
            instance_name: A unique name for this plugin instance.
            plugin_specific_config: A dictionary of configuration parameters.
            main_logger: The main application logger.
            app_state: The global application state object, if available.
        """
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        if ModbusSerialClient is None or ModbusTcpClient is None:
            raise ImportError("The 'growatt_modbus_plugin' requires 'pymodbus' to be installed.")

        self.last_error_message: Optional[str] = None
        self.last_known_static_data: Optional[Dict[str, Any]] = None
        
        # Parse connection configuration
        try:
            self.connection_type = ConnectionType(self.plugin_config.get("connection_type", "serial").strip().lower())
        except ValueError:
            self.logger.warning(f"Invalid connection_type '{self.plugin_config.get('connection_type')}' specified. Defaulting to Serial.")
            self.connection_type = ConnectionType.SERIAL

        # Connection parameters
        self.serial_port = self.plugin_config.get("serial_port", "/dev/ttyUSB0")
        self.baud_rate = int(self.plugin_config.get("baud_rate", 9600))
        self.tcp_host = self.plugin_config.get("tcp_host", "192.168.1.100")
        self.tcp_port = int(self.plugin_config.get("tcp_port", 502))
        self.slave_address = int(self.plugin_config.get("slave_address", 1))
        
        # Modbus communication parameters
        self.modbus_timeout_seconds = int(self.plugin_config.get("modbus_timeout_seconds", 10))
        # has_storage: true|false|auto — auto probes SPH block 1000, then WIT block 8034.
        # growatt_family: auto | sph | wit | spf | tlxh.
        raw_storage = str(self.plugin_config.get("has_storage", "auto")).split(";")[0].strip().lower()
        raw_family = str(self.plugin_config.get("growatt_family", "auto")).split(";")[0].strip().lower()
        if raw_storage in ("0", "false", "no", "off"):
            self._storage_kind = "off"
        elif raw_family in ("wit", "wit_tl3", "tl3"):
            self._storage_kind = "wit"
        elif raw_family in ("sph", "mix", "mix_sph"):
            self._storage_kind = "sph"
        elif raw_family in ("spf", "spf5000", "spf5000es", "offgrid"):
            self._storage_kind = "spf"
        elif raw_family in ("tlxh", "tl-xh", "tl_xh"):
            self._storage_kind = "tlxh"
        else:
            self._storage_kind = None  # probe once
        forced_storage = raw_storage in ("1", "true", "yes", "on")
        self._storage_probe = self._storage_kind is None and not forced_storage
        
        target_info = f"{self.tcp_host}:{self.tcp_port}" if self.connection_type == ConnectionType.TCP else f"{self.serial_port}:{self.baud_rate}"
        self.logger.info(
            f"Growatt Plugin '{self.instance_name}': Initialized. Conn: {self.connection_type.value}, "
            f"Target: {target_info}, SlaveID: {self.slave_address}, has_storage={raw_storage}, family={raw_family}."
        )

    @property
    def name(self) -> str:
        """Returns the technical name of the plugin."""
        return "growatt_modbus"

    @property
    def pretty_name(self) -> str:
        """Returns a user-friendly name for the plugin."""
        return "Growatt Modbus Inverter"

    @staticmethod
    def get_configurable_params() -> List[Dict[str, Any]]:
        return [
            {"name": "connection_type", "type": "select", "options": ["tcp", "serial"], "default": "tcp"},
            {"name": "tcp_host", "type": "str", "default": "192.168.1.100"},
            {"name": "tcp_port", "type": "int", "default": 502},
            {"name": "serial_port", "type": "str", "default": "/dev/ttyUSB0"},
            {"name": "baud_rate", "type": "int", "default": 9600},
            {"name": "slave_address", "type": "int", "default": 1},
            {"name": "modbus_timeout_seconds", "type": "float", "default": 5},
            {"name": "growatt_family", "type": "select", "options": ["auto", "sph", "wit", "spf", "tlxh"], "default": "auto"},
            {"name": "has_storage", "type": "select", "options": ["auto", "true", "false"], "default": "auto"},
        ]

    def connect(self) -> bool:
        """
        Establishes a connection to the Growatt inverter via Modbus TCP or RTU.

        For TCP connections, it performs a pre-connection check and then
        creates the appropriate Pymodbus client.

        Returns:
            True if the connection was successful, False otherwise.
        """
        if self._is_connected_flag and self.client:
            return True
        if self.client:
            self.disconnect()
        self.last_error_message = None

        if self.connection_type == ConnectionType.TCP:
            self.logger.info(f"Growatt Plugin '{self.instance_name}': Performing pre-connection network check for {self.tcp_host}:{self.tcp_port}...")
            port_open, rtt_ms, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
            if not port_open:
                self.last_error_message = f"Pre-check failed: TCP port {self.tcp_port} on {self.tcp_host} is not open. Error: {err_msg}"
                self.logger.error(self.last_error_message)
                icmp_ok, _, _ = check_icmp_ping(self.tcp_host, logger_instance=self.logger)
                if not icmp_ok:
                    self.logger.error(f"ICMP ping to {self.tcp_host} also failed. Host is likely down or blocked.")
                return False

        self.logger.info(f"Growatt Plugin '{self.instance_name}': Attempting to connect via {self.connection_type.value}...")
        try:
            if self.connection_type == ConnectionType.SERIAL:
                self.client = ModbusSerialClient(
                    method='rtu', port=self.serial_port, baudrate=self.baud_rate,
                    stopbits=1, bytesize=8, parity='N', timeout=self.modbus_timeout_seconds
                )
            else:  # TCP
                self.client = ModbusTcpClient(host=self.tcp_host, port=self.tcp_port, timeout=self.modbus_timeout_seconds)
            
            if self.client.connect():
                self._is_connected_flag = True
                self.logger.info(f"Growatt Plugin '{self.instance_name}': Successfully connected.")
                return True
            else:
                self.last_error_message = "Pymodbus client.connect() returned False."
        except Exception as e:
            self.last_error_message = f"Connection exception: {e}"
            self.logger.error(f"Growatt Plugin '{self.instance_name}': {self.last_error_message}", exc_info=True)
        
        if self.client:
            self.client.close()
        self.client = None
        self._is_connected_flag = False
        return False

    def disconnect(self) -> None:
        """Closes the Modbus connection and resets the client."""
        if self.client:
            self.logger.info(f"Growatt Plugin '{self.instance_name}': Disconnecting client.")
            try:
                self.client.close()
            except Exception as e:
                self.logger.error(f"Growatt Plugin '{self.instance_name}': Error closing Modbus connection: {e}", exc_info=True)
        self.client = None
        self._is_connected_flag = False

    def read_static_data(self) -> Dict[str, Any]:
        """
        Reads static device information from the Growatt inverter.

        This includes serial number, firmware versions, and detected
        number of MPPTs and phases. The data is cached after the first successful read.

        Returns:
            A dictionary containing the standardized static data, or empty dict if the read fails.
        """
        if self.last_known_static_data:
            return self.last_known_static_data
        
        self.logger.info(f"Growatt Plugin '{self.instance_name}': Reading static data...")
        if not self.is_connected:
            self.logger.error(f"Growatt Plugin '{self.instance_name}': Cannot read static data, not connected.")
            return {}

        try:
            # Read a block of holding registers for static info
            result = safe_read_holding_registers(
                self.client, 0, 45, slave=self.slave_address, logger_instance=self.logger
            )
            if result is None or result.isError():
                raise ConnectionException(f"Modbus error reading holding registers: {result}")
            
            decoded = self._decode_registers(result.registers, GROWATT_HOLD_REGISTERS, 0)

            firmware = decoded.get("firmware_version", "")
            control_fw = decoded.get("control_firmware_version", "")
            
            static_data = {
                StandardDataKeys.STATIC_DEVICE_CATEGORY: "inverter",
                StandardDataKeys.STATIC_INVERTER_MANUFACTURER: "Growatt",
                StandardDataKeys.STATIC_INVERTER_SERIAL_NUMBER: decoded.get("serial_number", UNKNOWN),
                StandardDataKeys.STATIC_INVERTER_FIRMWARE_VERSION: f"FW: {firmware}, Control: {control_fw}",
                StandardDataKeys.STATIC_NUMBER_OF_MPPTS: 2,
                StandardDataKeys.STATIC_NUMBER_OF_PHASES_AC: 1,
            }
            self.last_known_static_data = static_data
            return static_data

        except ConnectionException as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"Growatt Plugin '{self.instance_name}': Failed to read static data: {e}")
            self.disconnect()
            return {}

    def read_dynamic_data(self) -> Dict[str, Any]:
        """
        Reads real-time operational data from the Growatt inverter.

        This includes power values, voltages, currents, temperatures, and status
        information. The data is read from input registers in two blocks to support
        both standard and storage/hybrid inverter models.

        Returns:
            A dictionary containing the standardized operational data, or empty dict if the read fails.
        """
        if not self.is_connected:
            self.logger.error(f"Growatt Plugin '{self.instance_name}': Cannot read dynamic data, not connected.")
            return None

        try:
            if self._storage_kind == "spf":
                return self._read_spf()
            if self._storage_kind == "tlxh":
                return self._read_tlxh()
            all_registers = {}
            # Read first block of input registers (0-124), including PV3/PV4.
            res1 = safe_read_input_registers(
                self.client, 0, 125, slave=self.slave_address, logger_instance=self.logger
            )
            if res1 is None or res1.isError():
                raise ConnectionException(f"Modbus error reading input block 1: {res1}")
            for i, reg in enumerate(res1.registers):
                all_registers[i] = reg

            self._read_storage_block(all_registers)

            decoded = self._decode_registers_from_dict(all_registers, GROWATT_INPUT_REGISTERS)
            if self._storage_kind == "wit":
                decoded.update(self._decode_registers_from_dict(all_registers, GROWATT_WIT_INPUT_REGISTERS))
            return self._standardize_operational_data(decoded)

        except ConnectionException as e:
            self.last_error_message = f"Communication error: {e}"
            self.logger.error(f"Growatt Plugin '{self.instance_name}': Failed to read dynamic data: {e}")
            self.disconnect()
            return None

    def _modbus_illegal(self, result: Any) -> bool:
        err_txt = str(result)
        return "Illegal" in err_txt or "0x02" in err_txt or "illegal" in err_txt.lower()

    def _merge_input_block(self, all_registers: Dict[int, int], start: int, count: int) -> Any:
        result = safe_read_input_registers(
            self.client, start, count, slave=self.slave_address, logger_instance=self.logger
        )
        if result is not None and not result.isError():
            for i, reg in enumerate(result.registers):
                all_registers[start + i] = reg
        return result

    def _read_storage_block(self, all_registers: Dict[int, int]) -> None:
        """SPH/MIX live at input 1000. WIT TL3 lives at input 8034. Grid-tie units have neither."""
        kind = self._storage_kind
        if kind in ("off", "spf", "tlxh"):
            return
        if kind in (None, "sph"):
            res = self._merge_input_block(all_registers, 1000, 125)
            if res is not None and not res.isError():
                if kind is None:
                    self.logger.info(f"Growatt Plugin '{self.instance_name}': storage block 1000+ OK (SPH/MIX).")
                self._storage_kind = "sph"
                return
            if kind == "sph" or not self._modbus_illegal(res):
                self.logger.warning(
                    f"Growatt Plugin '{self.instance_name}': storage block 1000+ failed ({res})."
                )
                if kind == "sph":
                    return
            else:
                self.logger.info(
                    f"Growatt Plugin '{self.instance_name}': block 1000+ illegal; trying WIT input 8034."
                )
        resw = self._merge_input_block(all_registers, GROWATT_WIT_INPUT_START, GROWATT_WIT_INPUT_COUNT)
        if resw is not None and not resw.isError():
            if self._storage_kind != "wit":
                self.logger.info(f"Growatt Plugin '{self.instance_name}': WIT storage block 8034 OK.")
            self._storage_kind = "wit"
            return
        if self._storage_probe and self._storage_kind is None and self._modbus_illegal(resw):
            self._storage_kind = "off"
            self.logger.info(
                f"Growatt Plugin '{self.instance_name}': no SPH or WIT storage block; grid-tie registers only."
            )
        else:
            self.logger.warning(
                f"Growatt Plugin '{self.instance_name}': WIT block 8034 failed ({resw})."
            )

    def _read_spf(self) -> Optional[Dict[str, Any]]:
        all_registers: Dict[int, int] = {}
        res = self._merge_input_block(all_registers, 0, GROWATT_SPF_INPUT_COUNT)
        if res is None or res.isError():
            raise ConnectionException(f"Modbus error reading SPF input block: {res}")
        decoded = self._decode_registers_from_dict(all_registers, GROWATT_SPF_INPUT_REGISTERS)
        if "battery_power_charge" in decoded:
            decoded["battery_power"] = -(decoded.get("battery_power_charge") or 0)
        if "output_power" in decoded:
            decoded["load_power"] = decoded["output_power"]
        if "ac_input_power" in decoded:
            decoded["power_to_grid"] = -(decoded["ac_input_power"] or 0)
        decoded["today_pv_energy"] = (decoded.get("today_pv1_energy") or 0) + (decoded.get("today_pv2_energy") or 0)
        decoded["total_pv_energy"] = (decoded.get("total_pv1_energy") or 0) + (decoded.get("total_pv2_energy") or 0)
        return self._standardize_operational_data(decoded)

    def _read_tlxh(self) -> Optional[Dict[str, Any]]:
        all_registers: Dict[int, int] = {}
        # Modbus read length stays under 125 registers.
        res = self._merge_input_block(all_registers, GROWATT_TLXH_INPUT_START, 125)
        if res is None or res.isError():
            raise ConnectionException(f"Modbus error reading TL-XH input block: {res}")
        self._merge_input_block(all_registers, GROWATT_TLXH_INPUT_START + 125, 46)
        decoded = self._decode_registers_from_dict(all_registers, GROWATT_TLXH_INPUT_REGISTERS)
        voltage = decoded.get("battery_voltage") or 0
        current = decoded.get("battery_current") or 0
        decoded["battery_power"] = float(voltage) * float(current)
        string_w = (decoded.get("pv1_power") or 0) + (decoded.get("pv2_power") or 0)
        if not string_w and decoded.get("pv_total_power"):
            decoded["pv1_power"] = decoded["pv_total_power"]
        decoded["today_energy_to_user"] = decoded.get("today_grid_import")
        decoded["today_energy_to_grid"] = decoded.get("today_grid_export")
        decoded["total_energy_to_user"] = decoded.get("total_grid_import")
        decoded["total_energy_to_grid"] = decoded.get("total_grid_export")
        return self._standardize_operational_data(decoded)

    def _decode_registers(self, registers: List[int], register_map: Dict[str, Any], start_addr: int) -> Dict[str, Any]:
        """
        Decodes a list of registers based on a starting address.

        Args:
            registers: List of raw register values.
            register_map: The register map defining how to decode each register.
            start_addr: The starting address of the register block.

        Returns:
            A dictionary of decoded values keyed by register name.
        """
        reg_dict = {start_addr + i: val for i, val in enumerate(registers)}
        return self._decode_registers_from_dict(reg_dict, register_map)

    def _decode_registers_from_dict(self, reg_dict: Dict[int, int], register_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decodes registers from a dictionary of {address: value}.

        Args:
            reg_dict: Dictionary mapping register addresses to their raw values.
            register_map: The register map defining how to decode each register.

        Returns:
            A dictionary of decoded values keyed by register name.
        """
        decoded = {}
        for key, info in register_map.items():
            addr = info["addr"]
            if addr not in reg_dict: continue

            if info.get("type") in ("uint32", "int32"):
                if addr + 1 in reg_dict:
                    value = ((reg_dict[addr] & 0xFFFF) << 16) | (reg_dict[addr + 1] & 0xFFFF)
                    if info.get("type") == "int32" and value >= 0x80000000:
                        value -= 0x100000000
                else:
                    continue
            elif info.get("type") == "string":
                length = info.get("len", 1)
                byte_data = b''
                for i in range(length):
                    if addr + i in reg_dict:
                        byte_data += struct.pack('>H', reg_dict[addr + i])
                value = byte_data.decode('ascii', errors='ignore').strip().replace('\x00', '')
            else: # int16 or uint16
                value = reg_dict[addr]
                if info.get("type") == "int16":
                    value = struct.unpack('>h', struct.pack('>H', value))[0]

            scale = info.get("scale", 1.0)
            decoded[key] = float(value) * scale if scale != 1.0 else value
        return decoded

    def _standardize_operational_data(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts raw Growatt register data into standardized format.

        Args:
            d: Dictionary of decoded register values from the Growatt inverter.

        Returns:
            A dictionary containing standardized operational data keys and values.
        """
        # Determine status text
        status_code = d.get("inverter_status")
        status_text = GROWATT_STATUS_CODES.get(status_code, f"Unknown ({status_code})")
        if "system_work_state" in d:
             storage_status_code = d["system_work_state"]
             status_text = GROWATT_STORAGE_WORK_MODES.get(storage_status_code, status_text)

        # SPH reports charge and discharge as separate unsigned powers.
        # WIT reports one signed battery power (positive discharge).
        if "battery_charge_power" in d or "battery_discharge_power" in d:
            battery_power = d.get("battery_discharge_power", 0.0) - d.get("battery_charge_power", 0.0)
        else:
            battery_power = d.get("battery_power", 0.0)

        battery_voltage = d.get("battery_voltage", 0) or 0
        if "battery_current" in d and "battery_charge_power" not in d:
            battery_current = d["battery_current"]
        elif battery_voltage > 0:
            battery_current = battery_power / battery_voltage
        else:
            battery_current = 0

        batt_status_txt = "Idle"
        if battery_power > 10: batt_status_txt = "Discharging"
        elif battery_power < -10: batt_status_txt = "Charging"

        pv_power = sum(d.get(k, 0) or 0 for k in ("pv1_power", "pv2_power", "pv3_power", "pv4_power"))
        phase_powers = [d[k] for k in ("grid_l1_power", "grid_l2_power", "grid_l3_power") if k in d]
        grid_power = sum(phase_powers) if phase_powers else d.get("power_to_grid")
        load_power = d.get("load_power", d.get("power_to_user"))

        standardized = {
            StandardDataKeys.OPERATIONAL_INVERTER_STATUS_TEXT: status_text,
            StandardDataKeys.BATTERY_STATUS_TEXT: batt_status_txt,
            StandardDataKeys.BATTERY_CHARGE_STATE: derive_battery_charge_state(
                battery_power, batt_status_txt
            ),
            StandardDataKeys.AC_POWER_WATTS: d.get("output_power"),
            StandardDataKeys.PV_TOTAL_DC_POWER_WATTS: pv_power,
            StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS: grid_power,
            StandardDataKeys.LOAD_TOTAL_POWER_WATTS: load_power,
            StandardDataKeys.BATTERY_POWER_WATTS: battery_power,
            StandardDataKeys.BATTERY_CURRENT_AMPS: battery_current,
            StandardDataKeys.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS: d.get("inverter_temperature"),
            StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS: d.get("battery_temperature"),
            StandardDataKeys.GRID_L1_VOLTAGE_VOLTS: d.get("grid_l1_voltage"),
            StandardDataKeys.GRID_L1_CURRENT_AMPS: d.get("grid_l1_current"),
            StandardDataKeys.GRID_FREQUENCY_HZ: d.get("grid_frequency"),
            StandardDataKeys.BATTERY_VOLTAGE_VOLTS: d.get("battery_voltage"),
            StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT: d.get("battery_soc"),
            StandardDataKeys.PV_MPPT1_VOLTAGE_VOLTS: d.get("pv1_voltage"),
            StandardDataKeys.PV_MPPT1_CURRENT_AMPS: d.get("pv1_current"),
            StandardDataKeys.PV_MPPT1_POWER_WATTS: d.get("pv1_power"),
            StandardDataKeys.PV_MPPT2_VOLTAGE_VOLTS: d.get("pv2_voltage"),
            StandardDataKeys.PV_MPPT2_CURRENT_AMPS: d.get("pv2_current"),
            StandardDataKeys.PV_MPPT2_POWER_WATTS: d.get("pv2_power"),
            StandardDataKeys.ENERGY_PV_DAILY_KWH: d.get("today_pv_energy"),
            StandardDataKeys.ENERGY_PV_TOTAL_LIFETIME_KWH: d.get("total_pv_energy"),
            StandardDataKeys.ENERGY_BATTERY_DAILY_CHARGE_KWH: d.get("today_battery_charge_energy"),
            StandardDataKeys.ENERGY_BATTERY_DAILY_DISCHARGE_KWH: d.get("today_battery_discharge_energy"),
            StandardDataKeys.ENERGY_GRID_DAILY_IMPORT_KWH: d.get("today_energy_to_user", d.get("today_grid_import")),
            StandardDataKeys.ENERGY_GRID_DAILY_EXPORT_KWH: d.get("today_energy_to_grid", d.get("today_grid_export")),
            StandardDataKeys.ENERGY_GRID_TOTAL_IMPORT_KWH: d.get("total_energy_to_user", d.get("total_grid_import")),
            StandardDataKeys.ENERGY_GRID_TOTAL_EXPORT_KWH: d.get("total_energy_to_grid", d.get("total_grid_export")),
            "raw_values": d
        }
        if "battery_soh" in d:
            standardized[StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT] = d["battery_soh"]
        for index, prefix in ((3, "pv3"), (4, "pv4")):
            voltage = d.get(f"{prefix}_voltage") or 0
            power = d.get(f"{prefix}_power") or 0
            if voltage > 1 or power > 1:
                standardized[getattr(StandardDataKeys, f"PV_MPPT{index}_VOLTAGE_VOLTS")] = d.get(f"{prefix}_voltage")
                standardized[getattr(StandardDataKeys, f"PV_MPPT{index}_CURRENT_AMPS")] = d.get(f"{prefix}_current")
                standardized[getattr(StandardDataKeys, f"PV_MPPT{index}_POWER_WATTS")] = d.get(f"{prefix}_power")
        return standardized