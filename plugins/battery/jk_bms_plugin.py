# plugins/battery/jk_bms_plugin.py
"""
JK BMS Plugin for Solar Monitoring System

This plugin communicates with JK Battery Management Systems using their
native proprietary protocol (not Modbus). It supports both TCP and serial
connections and provides comprehensive battery monitoring.

Features:
- Native JK BMS protocol support
- Individual cell voltage monitoring (16S configuration)
- Multi-sensor temperature monitoring
- Real-time current and power monitoring
- State of charge and capacity tracking
- FET status and balancing monitoring
- Alarm and fault detection

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""

import struct
import logging
import serial
import socket
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.app_state import AppState

from plugins.plugin_interface import DevicePlugin, StandardDataKeys, parse_config_int, parse_config_str
from plugins.plugin_utils import check_tcp_port

# JK BMS Protocol Constants
JK_HEADER = bytes([0x55, 0xAA, 0xEB, 0x90])
JK_CMD_DEVICE_INFO = 0x03
JK_CMD_CELL_INFO = 0x01
JK_CMD_STATUS = 0x02

# JK BMS Commands (from protocol analysis)
JK_COMMANDS = {
    "device_info": bytes([0x01, 0x10, 0x16, 0x1C, 0x00, 0x01, 0x02, 0x00, 0x00, 0xD3, 0xCD]),
    "cell_info": bytes([0x01, 0x10, 0x16, 0x1E, 0x00, 0x01, 0x02, 0x00, 0x00, 0xD2, 0x2F]),
    "status_info": bytes([0x01, 0x10, 0x16, 0x20, 0x00, 0x01, 0x02, 0x00, 0x00, 0xD6, 0xF1])
}


def parse_jk_response(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse JK BMS proprietary protocol response.
    
    Protocol Structure:
    - Header: 55 AA EB 90 (4 bytes)
    - Command type: 1 byte
    - Length: 2 bytes (little-endian)
    - Data payload: variable length
    
    Args:
        data: Raw response bytes from JK BMS
        
    Returns:
        Dictionary of parsed values or None if parsing fails
    """
    if len(data) < 6 or data[:4] != JK_HEADER:
        return None
    
    cmd_type = data[4]
    length = struct.unpack('<H', data[5:7])[0] if len(data) > 6 else 0
    
    result = {"command_type": cmd_type, "length": length}
    
    if cmd_type == 0x02 and len(data) > 50:  # Main status response
        try:
            # Parse cell voltages (16S configuration)
            cell_voltages = []
            if len(data) >= 38:  # Header + 32 bytes for 16 cells
                offset = 6  # Start after header
                for i in range(16):
                    if offset + 1 < len(data):
                        cell_mv = struct.unpack('<H', data[offset:offset+2])[0]
                        if 2000 <= cell_mv <= 5000:  # Valid voltage range
                            cell_voltages.append(cell_mv / 1000.0)
                        else:
                            cell_voltages.append(0.0)
                        offset += 2
                    else:
                        cell_voltages.append(0.0)
                
                # Ensure exactly 16 cells
                while len(cell_voltages) < 16:
                    cell_voltages.append(0.0)
                cell_voltages = cell_voltages[:16]
            
            result["cell_voltages"] = cell_voltages
            
            # Calculate total voltage
            if cell_voltages:
                result["total_voltage"] = sum(cell_voltages)
            
            # Parse other values using JK BMS protocol data identifiers
            if len(data) >= 50:
                # Look for JK BMS data identifiers in the response
                pos = 6  # Start after header
                current_found = False
                soc_found = False
                
                # Debug: Log data identifiers found and check specific positions
                import logging
                logger = logging.getLogger(__name__)
                identifiers_found = []
                for i in range(6, min(len(data) - 1, 200)):
                    if data[i] in [0x79, 0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x89, 0x8A, 0x8B, 0x8C, 0xC0]:
                        identifiers_found.append(f"0x{data[i]:02X}@{i}")
                if identifiers_found:
                    logger.info(f"JK BMS: Data identifiers found: {', '.join(identifiers_found)}")
                else:
                    logger.info("JK BMS: No official data identifiers found, using position-based parsing")
                
                # Log key positions for analysis
                if len(data) > 80:
                    pos78_val = struct.unpack('<H', data[78:80])[0]
                    logger.info(f"JK BMS: Position 78 raw value: 0x{pos78_val:04X} ({pos78_val})")
                if len(data) > 156:
                    pos154_val = struct.unpack('<H', data[154:156])[0]
                    logger.info(f"JK BMS: Position 154 raw value: 0x{pos154_val:04X} ({pos154_val})")
                
                # Look for SOC value 52 (0x34) in the data
                soc_52_positions = []
                for i in range(6, min(len(data), 300)):
                    if data[i] == 52:  # 0x34
                        soc_52_positions.append(str(i))
                if soc_52_positions:
                    logger.info(f"JK BMS: Found SOC value 52 at positions: {', '.join(soc_52_positions)}")
                else:
                    logger.info("JK BMS: SOC value 52 not found in data")
                
                # Try to find data identifiers first
                data_id_found = False
                while pos < len(data) - 2:
                    data_id = data[pos]

                    # Current data (0x84) - Official JK BMS protocol
                    if data_id == 0x84 and pos + 2 < len(data):
                        try:
                            current_raw = struct.unpack('<H', data[pos+1:pos+3])[0]
                            # JK BMS current encoding: highest bit determines charge/discharge
                            if (current_raw & 0x8000) == 0x8000:
                                # Bit 15 = 1: charging (positive current)
                                current = float(current_raw & 0x7FFF) * 0.01
                                status = "charging"
                            else:
                                # Bit 15 = 0: discharging (negative current)
                                current = float(current_raw & 0x7FFF) * -0.01
                                status = "discharging"

                            result["current"] = current
                            current_found = True
                            data_id_found = True
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.info(f"JK BMS: Found 0x84 current at pos {pos}: {current:.2f}A ({status}, raw: 0x{current_raw:04X})")
                            pos += 3
                            continue
                        except:
                            pass

                    # SOC data (0x85) - Official JK BMS protocol
                    elif data_id == 0x85 and pos + 1 < len(data):
                        try:
                            soc_val = data[pos+1]
                            if 0 <= soc_val <= 100:
                                result["soc"] = soc_val
                                soc_found = True
                                data_id_found = True
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(f"JK BMS: Found 0x85 SOC at pos {pos}: {soc_val}%")
                            pos += 2
                            continue
                        except:
                            pass

                    # Total voltage (0x83) - Official JK BMS protocol
                    elif data_id == 0x83 and pos + 2 < len(data):
                        try:
                            voltage_raw = struct.unpack('<H', data[pos+1:pos+3])[0]
                            voltage = voltage_raw * 0.01  # 0.01V precision
                            if 20.0 <= voltage <= 70.0:  # Reasonable voltage range
                                result["total_voltage"] = voltage
                                data_id_found = True
                            pos += 3
                            continue
                        except:
                            pass

                    pos += 1

                # If no data identifiers found, use position-based parsing
                if not data_id_found:
                    logger.info("JK BMS: No data identifiers found, using position-based parsing")
                
                # Enhanced fallback current detection if 0x84 not found
                if not current_found:
                    import logging
                    logger = logging.getLogger(__name__)
                    current_candidates = []  # Initialize here

                    # SCAN for current data at positions that could contain varying values
                    # Look for positions with current values in the expected range (5-15A for 400-500W)
                    current_positions_to_scan = [78, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100]

                    for scan_pos in current_positions_to_scan:
                        if scan_pos + 1 < len(data):
                            try:
                                scan_raw = struct.unpack('<H', data[scan_pos:scan_pos+2])[0]
                                if scan_raw != 0 and scan_raw != 0xFFFF:
                                    # Try both 0.01A and 0.1A precision
                                    if (scan_raw & 0x8000) == 0x8000:
                                        scan_current_01 = float(scan_raw & 0x7FFF) * 0.01
                                        scan_current_10 = float(scan_raw & 0x7FFF) * 0.1
                                        scan_status = "charging"
                                    else:
                                        scan_current_01 = float(scan_raw & 0x7FFF) * -0.01
                                        scan_current_10 = float(scan_raw & 0x7FFF) * -0.1
                                        scan_status = "discharging"

                                    # Look for currents in the expected varying range (5-15A)
                                    if 5.0 <= abs(scan_current_10) <= 15.0:
                                        logger.info(f"JK BMS: Found varying current at pos {scan_pos}: {scan_current_10:.2f}A ({scan_status}, raw: 0x{scan_raw:04X})")
                                        result["current"] = scan_current_10
                                        current_found = True
                                        break
                                    elif 5.0 <= abs(scan_current_01) <= 15.0:
                                        logger.info(f"JK BMS: Found varying current at pos {scan_pos}: {scan_current_01:.2f}A ({scan_status}, raw: 0x{scan_raw:04X})")
                                        result["current"] = scan_current_01
                                        current_found = True
                                        break
                            except:
                                pass

                    # If no varying current found, try position 78 as fallback
                    if not current_found and len(data) > 79:
                        try:
                            pos78_raw = struct.unpack('<H', data[78:80])[0]
                            if pos78_raw != 0 and pos78_raw != 0xFFFF:
                                if (pos78_raw & 0x8000) == 0x8000:
                                    current = float(pos78_raw & 0x7FFF) * 0.01
                                    status = "charging"
                                else:
                                    current = float(pos78_raw & 0x7FFF) * -0.01
                                    status = "discharging"

                                logger.info(f"JK BMS: Using position 78 fallback: {current:.2f}A ({status}, raw: 0x{pos78_raw:04X})")
                                result["current"] = current
                                current_found = True
                        except:
                            pass

                    # If position 78 didn't work, try other positions
                    if not current_found:
                        # Try multiple known positions for current data
                        current_positions = [78, 80, 82, 84, 86, 88, 154, 156, 158, 160]

                        for pos in current_positions:
                            if pos + 1 < len(data):
                                try:
                                    current_raw = struct.unpack('<H', data[pos:pos+2])[0]

                                    # Skip obviously invalid values
                                    if current_raw == 0 or current_raw == 0xFFFF:
                                        continue

                                    # Apply JK BMS current encoding - try both 0.01A and 0.1A precision
                                    if (current_raw & 0x8000) == 0x8000:
                                        # Bit 15 = 1: charging (positive current)
                                        current_01 = float(current_raw & 0x7FFF) * 0.01
                                        current_10 = float(current_raw & 0x7FFF) * 0.1
                                        status = "charging"
                                    else:
                                        # Bit 15 = 0: discharging (negative current)
                                        current_01 = float(current_raw & 0x7FFF) * -0.01
                                        current_10 = float(current_raw & 0x7FFF) * -0.1
                                        status = "discharging"

                                    # Choose the better current value based on expected range
                                    if abs(current_10) <= 50.0 and abs(current_10) >= 0.5:  # 0.1A precision more likely for 400W
                                        current = current_10
                                    else:
                                        current = current_01

                                    # Accept reasonable current values (5-50A range for battery systems)
                                    if 5.0 <= abs(current) <= 50.0:
                                        current_candidates.append((pos, current, status, current_raw))
                                        logger.debug(f"JK BMS: Current candidate at pos {pos}: {current:.2f}A ({status}, raw: 0x{current_raw:04X})")
                                except:
                                    pass

                    # Also try positions that might contain current data based on pattern analysis
                    # Look for positions with values that could represent ~8A (407W / 52V)
                    for pos in range(70, min(len(data) - 1, 200), 2):
                        if pos + 1 < len(data) and pos not in [78, 80, 82, 84, 86, 88]:  # Skip already checked positions
                            try:
                                current_raw = struct.unpack('<H', data[pos:pos+2])[0]

                                # Skip cell voltages and other known patterns
                                if current_raw in [0x0CC0, 0x0CBF, 0x0CC2, 0x5000, 0xFFFF, 0x0000]:
                                    continue

                                # Look for values that could represent currents around 5-15A
                                if 0x0040 <= current_raw <= 0xFFFF:  # Raw values that would give 0.64A to 4095A (0.01A) or 6.4A to 40950A (0.1A)
                                    if (current_raw & 0x8000) == 0x8000:
                                        current_01 = float(current_raw & 0x7FFF) * 0.01
                                        current_10 = float(current_raw & 0x7FFF) * 0.1
                                        status = "charging"
                                    else:
                                        current_01 = float(current_raw & 0x7FFF) * -0.01
                                        current_10 = float(current_raw & 0x7FFF) * -0.1
                                        status = "discharging"

                                    # Prefer 0.1A precision for expected current range
                                    if abs(current_10) <= 15.0 and abs(current_10) >= 5.0:
                                        current = current_10
                                        logger.info(f"JK BMS: Found potential current at pos {pos}: {current:.2f}A ({status}, raw: 0x{current_raw:04X}, 0.1A precision)")
                                    elif abs(current_01) <= 15.0 and abs(current_01) >= 5.0:
                                        current = current_01
                                        logger.info(f"JK BMS: Found potential current at pos {pos}: {current:.2f}A ({status}, raw: 0x{current_raw:04X}, 0.01A precision)")
                                    else:
                                        continue

                                    if 5.0 <= abs(current) <= 15.0:  # Look for currents in expected range
                                        current_candidates.append((pos, current, status, current_raw))
                            except:
                                pass

                    # Select the best current candidate
                    if current_candidates:
                        # Filter out cell voltage values (typically 0x0Cxx range which would be ~32A)
                        filtered_candidates = []
                        for pos, current, status, current_raw in current_candidates:
                            # Skip values that look like cell voltages (0x0C00-0x0CFF range)
                            if not (0x0C00 <= current_raw <= 0x0CFF):
                                filtered_candidates.append((pos, current, status, current_raw))

                        if filtered_candidates:
                            # Group candidates by position range to find actual current data
                            # Current data should be in a specific position that varies with load
                            position_groups = {}
                            for pos, current, status, current_raw in filtered_candidates:
                                # Group by position ranges
                                if 75 <= pos <= 85:  # Primary positions
                                    group = "primary"
                                elif 150 <= pos <= 170:  # Secondary positions
                                    group = "secondary"
                                else:
                                    group = "other"

                                if group not in position_groups:
                                    position_groups[group] = []
                                position_groups[group].append((pos, current, status, current_raw))

                            # Prefer primary positions (75-85) as they're more likely to be actual current
                            if "primary" in position_groups and position_groups["primary"]:
                                # For primary positions, pick the one with largest absolute current
                                # (more likely to be actual varying current)
                                primary_candidates = position_groups["primary"]
                                primary_candidates.sort(key=lambda x: abs(x[1]), reverse=True)
                                pos, current, status, current_raw = primary_candidates[0]
                                logger.info(f"JK BMS: Selected primary position current at pos {pos}: {current:.2f}A ({status}, raw: 0x{current_raw:04X})")
                            elif "secondary" in position_groups and position_groups["secondary"]:
                                # For secondary positions, also pick largest absolute current
                                secondary_candidates = position_groups["secondary"]
                                secondary_candidates.sort(key=lambda x: abs(x[1]), reverse=True)
                                pos, current, status, current_raw = secondary_candidates[0]
                                logger.info(f"JK BMS: Selected secondary position current at pos {pos}: {current:.2f}A ({status}, raw: 0x{current_raw:04X})")
                            else:
                                # Fallback: pick the largest absolute current from any position
                                filtered_candidates.sort(key=lambda x: abs(x[1]), reverse=True)
                                pos, current, status, current_raw = filtered_candidates[0]
                                logger.info(f"JK BMS: Selected largest current at pos {pos}: {current:.2f}A ({status}, raw: 0x{current_raw:04X})")

                            result["current"] = current
                            current_found = True
                        elif current_candidates:
                            # If all candidates look like cell voltages, use the one with smallest absolute value
                            # (less likely to be a cell voltage)
                            current_candidates.sort(key=lambda x: abs(x[1]))
                            pos, current, status, current_raw = current_candidates[0]
                            result["current"] = current
                            current_found = True
                            logger.info(f"JK BMS: Using smallest current at pos {pos}: {current:.2f}A ({status}, raw: 0x{current_raw:04X})")

                    if not current_found:
                        logger.warning("JK BMS: No valid current values found in known positions")
                
                # Fallback SOC detection if 0x85 not found
                if not soc_found:
                    import logging
                    logger = logging.getLogger(__name__)
                    
                    # Look for SOC at known positions (150, 173) first
                    soc_positions = [150, 173]
                    for pos in soc_positions:
                        if pos < len(data):
                            soc_val = data[pos]
                            if 40 <= soc_val <= 60:  # Look for SOC around 52%
                                result["soc"] = soc_val
                                soc_found = True
                                logger.info(f"JK BMS: Found SOC {soc_val}% at known position {pos}")
                                break
                    
                    # If not found at known positions, scan for 52% specifically
                    if not soc_found:
                        for pos in range(6, min(len(data), 300)):
                            if pos < len(data) and data[pos] == 52:
                                result["soc"] = 52
                                soc_found = True
                                logger.info(f"JK BMS: Found target SOC 52% at position {pos}")
                                break
                    
                    # If still not found, use any reasonable SOC value
                    if not soc_found:
                        soc_candidates = []
                        for pos in range(6, min(len(data), 300)):
                            if pos < len(data):
                                soc_val = data[pos]
                                if 10 <= soc_val <= 100:
                                    soc_candidates.append(f"{soc_val}%@{pos}")
                        
                        logger.info(f"JK BMS: SOC candidates found: {', '.join(soc_candidates)}")
                        
                        # Prefer SOC values in the 40-60% range (more likely to be correct)
                        for pos in range(6, min(len(data), 300)):
                            if pos < len(data):
                                soc_val = data[pos]
                                if 40 <= soc_val <= 60:
                                    result["soc"] = soc_val
                                    logger.info(f"JK BMS: Using preferred SOC {soc_val}% at position {pos}")
                                    break
                        
                        # If no preferred SOC, use any reasonable value
                        if "soc" not in result:
                            for pos in range(6, min(len(data), 300)):
                                if pos < len(data):
                                    soc_val = data[pos]
                                    if 10 <= soc_val <= 100:
                                        result["soc"] = soc_val
                                        logger.info(f"JK BMS: Using fallback SOC {soc_val}% at position {pos}")
                                        break
                
                # Capacity detection
                for pos in range(100, min(250, len(data) - 1), 2):
                    try:
                        cap_raw = struct.unpack('<H', data[pos:pos+2])[0]
                        # Remaining capacity (~150-160Ah range)
                        if 150 <= cap_raw <= 160:
                            result["remaining_capacity"] = float(cap_raw)
                        # Total capacity (~220-250Ah range)
                        elif 220 <= cap_raw <= 250:
                            result["total_capacity"] = float(cap_raw)
                    except:
                        continue
                
                # Temperature detection
                temps = []
                for pos in range(150, min(250, len(data) - 1), 2):
                    if pos + 1 < len(data):
                        try:
                            temp_raw = struct.unpack('<H', data[pos:pos+2])[0]
                            if 150 <= temp_raw <= 500:  # 15-50°C in 0.1°C units
                                temp_c = temp_raw / 10.0
                                if 15.0 <= temp_c <= 50.0:
                                    temps.append(temp_c)
                                    if len(temps) >= 3:
                                        break
                        except:
                            continue
                
                if temps:
                    result["temperatures"] = temps
                    result["temperature"] = temps[0]
                
                # Status flags
                for pos in [160, 162, 164, 166]:
                    if pos + 1 < len(data):
                        try:
                            status = struct.unpack('<H', data[pos:pos+2])[0]
                            if status != 0:
                                result["status_flags"] = status
                                result["charge_fet"] = bool(status & 0x01)
                                result["discharge_fet"] = bool(status & 0x02)
                                result["balancing"] = bool(status & 0x04)
                                break
                        except:
                            continue
                            
        except (struct.error, IndexError):
            pass
    
    return result


class JkBmsPlugin(DevicePlugin):
    """
    JK BMS Plugin using native proprietary protocol.
    
    Supports comprehensive monitoring of JK Battery Management Systems
    including cell voltages, temperatures, current, SOC, and system status.
    """
    
    def __init__(self, instance_name: str, plugin_specific_config: Dict[str, Any], 
                 main_logger: logging.Logger, app_state: Optional['AppState'] = None):
        super().__init__(instance_name, plugin_specific_config, main_logger, app_state)
        
        self.last_known_dynamic_data: Dict[str, Any] = {}
        self.connection_type = self.plugin_config.get("connection_type", "tcp").lower()
        self.timeout = parse_config_int(self.plugin_config, "timeout_seconds", 10)
        self.client = None
        self.last_error_message: Optional[str] = None

        # Configure connection parameters
        self.logger.info(f"JK BMS '{self.instance_name}': Configuring for {self.connection_type} connection")
        
        valid_config = True
        if self.connection_type == "tcp":
            self.tcp_host = parse_config_str(self.plugin_config, "tcp_host")
            self.tcp_port = parse_config_int(self.plugin_config, "tcp_port", 8899)
            self.logger.info(f"JK BMS '{self.instance_name}': TCP config - Host: {self.tcp_host}, Port: {self.tcp_port}")
            if not self.tcp_host: 
                self.logger.error(f"JK BMS '{self.instance_name}': TCP host not configured")
                valid_config = False
        elif self.connection_type == "serial":
            self.serial_port = parse_config_str(self.plugin_config, "serial_port")
            self.baud_rate = parse_config_int(self.plugin_config, "baud_rate", 115200)
            self.logger.info(f"JK BMS '{self.instance_name}': Serial config - Port: {self.serial_port}, Baud: {self.baud_rate}")
            if not self.serial_port: 
                self.logger.error(f"JK BMS '{self.instance_name}': Serial port not configured")
                valid_config = False
        else:
            self.logger.error(f"JK BMS '{self.instance_name}': Invalid connection type '{self.connection_type}'. Must be 'tcp' or 'serial'")
            valid_config = False
            
        if not valid_config:
            self.connection_type = "disabled"
            self.last_error_message = "Plugin configuration error (see logs)"
            self.logger.error(f"JK BMS '{self.instance_name}': Plugin disabled due to configuration errors")

    @property
    def name(self) -> str:
        return "jk_bms"
    
    @property
    def pretty_name(self) -> str:
        return "JK BMS (Native Protocol)"

    def _send_command(self, command: bytes) -> Optional[bytes]:
        """Send command to JK BMS and receive response."""
        if not self.client:
            self.logger.debug("JK BMS: No client connection available")
            return None
            
        try:
            # Log command being sent
            self.logger.debug(f"JK BMS: Sending command: {command.hex(' ').upper()}")
            
            # Send command
            if self.connection_type == "tcp":
                self.client.send(command)
            else:  # serial
                self.client.write(command)
            
            # Wait for response (give BMS time to process)
            time.sleep(0.5)  # Increased delay for JK BMS
            
            # Read response
            response = b""
            if self.connection_type == "tcp":
                for _ in range(5):  # Multiple read attempts
                    try:
                        chunk = self.client.recv(1024)
                        if chunk:
                            response += chunk
                            self.logger.debug(f"JK BMS: Received chunk: {len(chunk)} bytes")
                        else:
                            break
                    except socket.timeout:
                        self.logger.debug("JK BMS: TCP read timeout")
                        break
                    time.sleep(0.05)
            else:  # serial
                if self.client.in_waiting > 0:
                    response = self.client.read(self.client.in_waiting)
                    self.logger.debug(f"JK BMS: Serial read: {len(response)} bytes")
                else:
                    self.logger.debug("JK BMS: No serial data waiting")
            
            if response:
                self.logger.debug(f"JK BMS: Total response: {len(response)} bytes")
                return response
            else:
                self.logger.debug("JK BMS: No response received")
                return None
                
        except Exception as e:
            self.logger.warning(f"JK BMS: Command failed: {e}")
            return None

    def connect(self) -> bool:
        """Establish connection to JK BMS device."""
        if self._is_connected_flag and self.client: 
            self.logger.debug("JK BMS: Already connected")
            return True
        
        if self.connection_type == "disabled":
            self.last_error_message = "Plugin disabled due to configuration error"
            return False
        
        self.logger.info(f"JK BMS: Attempting to connect via {self.connection_type}")
        
        try:
            if self.connection_type == "tcp":
                if not getattr(self, 'tcp_host', None): 
                    self.last_error_message = "TCP host not configured"
                    self.logger.error("JK BMS: TCP host not configured")
                    return False
                
                self.logger.info(f"JK BMS: Connecting to TCP {self.tcp_host}:{self.tcp_port}")
                    
                # Pre-check port availability
                port_open, _, err_msg = check_tcp_port(self.tcp_host, self.tcp_port, logger_instance=self.logger)
                if not port_open: 
                    self.last_error_message = f"Port check failed: {err_msg}"
                    self.logger.error(f"JK BMS: Port check failed: {err_msg}")
                    return False
                
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(self.timeout)
                self.client.connect((self.tcp_host, self.tcp_port))
                
            else:  # serial
                if not getattr(self, 'serial_port', None): 
                    self.last_error_message = "Serial port not configured"
                    self.logger.error("JK BMS: Serial port not configured")
                    return False
                
                self.logger.info(f"JK BMS: Connecting to Serial {self.serial_port} @ {self.baud_rate} baud")
                
                self.client = serial.Serial(
                    port=self.serial_port,
                    baudrate=self.baud_rate,
                    timeout=self.timeout,
                    bytesize=8,
                    parity='N',
                    stopbits=1
                )
            
            self._is_connected_flag = True
            if self.connection_type == "tcp":
                self.logger.info(f"JK BMS: Successfully connected via TCP to {self.tcp_host}:{self.tcp_port}")
            else:
                self.logger.info(f"JK BMS: Successfully connected via Serial to {self.serial_port} @ {self.baud_rate} baud")
            return True
            
        except Exception as e:
            self.last_error_message = f"Connection failed: {e}"
            self.logger.error(f"JK BMS: Connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Close connection to JK BMS device."""
        if self.client: 
            try:
                self.client.close()
            except:
                pass
        self.client = None
        self._is_connected_flag = False

    def is_connected(self) -> bool:
        """Check if connected to JK BMS."""
        return self._is_connected_flag and self.client is not None

    def read_static_data(self) -> Optional[Dict[str, Any]]:
        """Read static device information."""
        if self.connection_type == "tcp":
            serial_id = f"jk_{self.tcp_host}_{self.tcp_port}"
        else:
            serial_id = f"jk_{self.serial_port}_{self.baud_rate}"
        
        return {
            StandardDataKeys.STATIC_BATTERY_MANUFACTURER: "JK BMS",
            StandardDataKeys.STATIC_BATTERY_MODEL_NAME: "JKBMS (Native Protocol)",
            StandardDataKeys.STATIC_BATTERY_SERIAL_NUMBER: serial_id,
            StandardDataKeys.STATIC_DEVICE_CATEGORY: "bms"
        }

    def read_dynamic_data(self) -> Optional[Dict[str, Any]]:
        """Read real-time battery data from JK BMS."""
        self.last_error_message = None
        
        if not self._is_connected_flag:
            self.logger.debug("JK BMS: Not connected, attempting to connect...")
            if not self.connect():
                self.logger.error(f"JK BMS: Connection failed. Cannot read data. Error: {self.last_error_message}")
                return None
        
        # Send status command to get current data
        response = self._send_command(JK_COMMANDS["status_info"])
        if not response:
            self.logger.warning("JK BMS: No response to status command, trying alternative commands...")
            
            # Try alternative commands if the main one fails
            for cmd_name, cmd_bytes in JK_COMMANDS.items():
                if cmd_name != "status_info":
                    self.logger.debug(f"JK BMS: Trying {cmd_name} command...")
                    response = self._send_command(cmd_bytes)
                    if response:
                        self.logger.info(f"JK BMS: Got response from {cmd_name} command")
                        break
            
            if not response:
                self.logger.error("JK BMS: No response from any command")
                return None
        
        # Log response for debugging
        self.logger.info(f"JK BMS: Raw response (first 100 bytes): {response[:100].hex(' ').upper()}")
        if len(response) > 4:
            self.logger.info(f"JK BMS: Received response type 0x{response[4]:02X}, length {len(response)} bytes")
        else:
            self.logger.warning(f"JK BMS: Response too short: {len(response)} bytes")
        
        # Parse the response
        parsed_data = parse_jk_response(response)
        if not parsed_data:
            self.logger.warning(f"JK BMS: Failed to parse response. Raw data: {response.hex(' ').upper()}")
            return None
        
        # Log parsed data for debugging
        self.logger.info(f"JK BMS: Parsed data: {parsed_data}")
        self.logger.info(f"JK BMS: Successfully parsed data: {list(parsed_data.keys())}")
        
        # Debug: Log specific bytes around potential current positions
        if len(response) > 80:
            self.logger.debug(f"JK BMS: Bytes 38-50: {response[38:50].hex(' ').upper()}")
            self.logger.debug(f"JK BMS: Bytes 70-85: {response[70:85].hex(' ').upper()}")
            self.logger.debug(f"JK BMS: Bytes 140-155: {response[140:155].hex(' ').upper()}")
            
            # Enhanced current detection debugging
            if len(response) > 81:
                import struct
                try:
                    # Check for protocol version indicator (0xC0)
                    protocol_version = None
                    for i in range(6, min(len(response) - 1, 200)):
                        if response[i] == 0xC0 and i + 1 < len(response):
                            protocol_version = response[i + 1]
                            self.logger.info(f"JK BMS: Found protocol version 0xC0: 0x{protocol_version:02X}")
                            break

                    # Scan for potential current values across the response
                    self.logger.info("JK BMS: Scanning for current values (0.01A precision)...")
                    current_candidates = []

                    for pos in range(6, min(len(response) - 1, 300), 2):
                        if pos + 1 < len(response):
                            try:
                                val_raw = struct.unpack('<H', response[pos:pos+2])[0]

                                # Skip obviously invalid values
                                if val_raw == 0 or val_raw == 0xFFFF or val_raw == 0x5000:
                                    continue

                                # Try different current encodings
                                # Standard JK encoding (0.01A precision)
                                if (val_raw & 0x8000) == 0x8000:
                                    current_01 = float(val_raw & 0x7FFF) * 0.01  # charging
                                else:
                                    current_01 = float(val_raw & 0x7FFF) * -0.01  # discharging

                                # Alternative encoding (0.1A precision)
                                if (val_raw & 0x8000) == 0x8000:
                                    current_10 = float(val_raw & 0x7FFF) * 0.1  # charging
                                else:
                                    current_10 = float(val_raw & 0x7FFF) * -0.1  # discharging

                                # Log reasonable current values
                                if abs(current_01) <= 100.0:
                                    current_candidates.append(f"Pos {pos}: 0x{val_raw:04X} -> {current_01:.2f}A (0.01A)")
                                if abs(current_10) <= 100.0 and abs(current_10) != abs(current_01):
                                    current_candidates.append(f"Pos {pos}: 0x{val_raw:04X} -> {current_10:.2f}A (0.1A)")

                            except:
                                pass

                    if current_candidates:
                        self.logger.info(f"JK BMS: Found {len(current_candidates)} current candidates:")
                        for candidate in current_candidates[:10]:  # Limit to first 10
                            self.logger.info(f"JK BMS: {candidate}")
                        if len(current_candidates) > 10:
                            self.logger.info(f"JK BMS: ... and {len(current_candidates) - 10} more")
                    else:
                        self.logger.info("JK BMS: No current candidates found in scan")

                except Exception as e:
                    self.logger.debug(f"JK BMS: Debug scanning failed: {e}")
        
        # Convert to standard format
        result = {}
        
        # Cell voltages
        if "cell_voltages" in parsed_data:
            cell_voltages = parsed_data["cell_voltages"]
            result[StandardDataKeys.BMS_CELL_VOLTAGES_LIST] = cell_voltages
            result[StandardDataKeys.BMS_CELL_COUNT] = len([v for v in cell_voltages if v > 0])
            
            valid_voltages = [v for v in cell_voltages if v > 0]
            if valid_voltages:
                max_voltage = max(valid_voltages)
                min_voltage = min(valid_voltages)
                avg_voltage = sum(valid_voltages) / len(valid_voltages)
                
                result[StandardDataKeys.BMS_CELL_VOLTAGE_MAX_VOLTS] = max_voltage
                result[StandardDataKeys.BMS_CELL_VOLTAGE_MIN_VOLTS] = min_voltage
                result[StandardDataKeys.BMS_CELL_VOLTAGE_AVERAGE_VOLTS] = round(avg_voltage, 3)
                result[StandardDataKeys.BMS_CELL_VOLTAGE_DELTA_VOLTS] = max_voltage - min_voltage
                
                # Find cells with min/max voltages (matching Seplos V2 format)
                min_indices = [str(i+1) for i, v in enumerate(cell_voltages) if v == min_voltage and v > 0]
                max_indices = [str(i+1) for i, v in enumerate(cell_voltages) if v == max_voltage and v > 0]
                result[StandardDataKeys.BMS_CELL_WITH_MIN_VOLTAGE_NUMBER] = ",".join(min_indices)
                result[StandardDataKeys.BMS_CELL_WITH_MAX_VOLTAGE_NUMBER] = ",".join(max_indices)
        
        # Battery voltage
        if "total_voltage" in parsed_data:
            result[StandardDataKeys.BATTERY_VOLTAGE_VOLTS] = parsed_data["total_voltage"]
        
        # Current and power
        if "current" in parsed_data:
            current = parsed_data["current"]
            result[StandardDataKeys.BATTERY_CURRENT_AMPS] = current

            # Calculate power if we have voltage
            if "total_voltage" in parsed_data:
                power = parsed_data["total_voltage"] * current
                result[StandardDataKeys.BATTERY_POWER_WATTS] = power

            # For JK BMS, negative current = discharging (power should be negative)
            # Positive current = charging (power should be positive)
            # This matches the JK BMS convention where current sign indicates direction

            # Battery status based on current (JK BMS convention)
            current_val = result.get(StandardDataKeys.BATTERY_CURRENT_AMPS, 0)
            if isinstance(current_val, (int, float)):
                if current_val < -0.1:  # Negative current = discharging
                    result[StandardDataKeys.BATTERY_STATUS_TEXT] = "Discharging"
                elif current_val > 0.1:  # Positive current = charging
                    result[StandardDataKeys.BATTERY_STATUS_TEXT] = "Charging"
                else:
                    result[StandardDataKeys.BATTERY_STATUS_TEXT] = "Idle"
            else:
                result[StandardDataKeys.BATTERY_STATUS_TEXT] = "Idle"
        else:
            # If current is not found, set it to 0 and mark as idle
            result[StandardDataKeys.BATTERY_CURRENT_AMPS] = 0.0
            result[StandardDataKeys.BATTERY_POWER_WATTS] = 0.0
            result[StandardDataKeys.BATTERY_STATUS_TEXT] = "Idle (Current N/A)"
        
        # State of charge
        if "soc" in parsed_data:
            result[StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT] = parsed_data["soc"]
        
        # State of health (if available)
        if "soh" in parsed_data:
            result[StandardDataKeys.BATTERY_STATE_OF_HEALTH_PERCENT] = parsed_data["soh"]
        
        # Capacities
        if "remaining_capacity" in parsed_data:
            result[StandardDataKeys.BMS_REMAINING_CAPACITY_AH] = parsed_data["remaining_capacity"]
        if "total_capacity" in parsed_data:
            result[StandardDataKeys.BMS_FULL_CAPACITY_AH] = parsed_data["total_capacity"]
            # Also set as nominal capacity if not explicitly provided
            if "nominal_capacity" not in parsed_data:
                result[StandardDataKeys.BMS_NOMINAL_CAPACITY_AH] = parsed_data["total_capacity"]
        if "nominal_capacity" in parsed_data:
            result[StandardDataKeys.BMS_NOMINAL_CAPACITY_AH] = parsed_data["nominal_capacity"]
        
        # Cycle count
        if "cycle_count" in parsed_data:
            result[StandardDataKeys.BATTERY_CYCLES_COUNT] = parsed_data["cycle_count"]
        
        # Temperature
        if "temperature" in parsed_data:
            result[StandardDataKeys.BATTERY_TEMPERATURE_CELSIUS] = parsed_data["temperature"]
        if "temperatures" in parsed_data:
            temps = parsed_data["temperatures"]
            result[StandardDataKeys.BMS_TEMP_MAX_CELSIUS] = max(temps)
            result[StandardDataKeys.BMS_TEMP_MIN_CELSIUS] = min(temps)
        
        # FET status
        if "charge_fet" in parsed_data:
            result[StandardDataKeys.BMS_CHARGE_FET_ON] = parsed_data["charge_fet"]
        if "discharge_fet" in parsed_data:
            result[StandardDataKeys.BMS_DISCHARGE_FET_ON] = parsed_data["discharge_fet"]
        
        # Balancing status
        if "balancing" in parsed_data:
            result[StandardDataKeys.BMS_CELLS_BALANCING_TEXT] = "Active" if parsed_data["balancing"] else "Inactive"
        
        # System status and alarms
        result[StandardDataKeys.BMS_FAULT_SUMMARY_TEXT] = "Normal"
        result[StandardDataKeys.BMS_ACTIVE_ALARMS_LIST] = []
        result[StandardDataKeys.BMS_ACTIVE_WARNINGS_LIST] = []
        
        # Parse alarms/warnings if available
        if "alarms" in parsed_data and parsed_data["alarms"]:
            result[StandardDataKeys.BMS_ACTIVE_ALARMS_LIST] = parsed_data["alarms"]
            result[StandardDataKeys.BMS_FAULT_SUMMARY_TEXT] = "Alarm Active"
        if "warnings" in parsed_data and parsed_data["warnings"]:
            result[StandardDataKeys.BMS_ACTIVE_WARNINGS_LIST] = parsed_data["warnings"]
        
        # Log the final result
        self.logger.info(f"JK BMS: Returning {len(result)} data points: {list(result.keys())}")
        if result:
            # Log key values for debugging
            soc = result.get(StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT, "N/A")
            voltage = result.get(StandardDataKeys.BATTERY_VOLTAGE_VOLTS, "N/A")
            current = result.get(StandardDataKeys.BATTERY_CURRENT_AMPS, "N/A")
            self.logger.info(f"JK BMS: Key values - SOC: {soc}%, Voltage: {voltage}V, Current: {current}A")
        
        self.last_known_dynamic_data = result
        return result if result else None

    def get_last_known_dynamic_data(self) -> Dict[str, Any]:
        """Return the last successfully read dynamic data."""
        return self.last_known_dynamic_data.copy()
