# plugins/plugin_utils.py
import time
import socket
import platform
import subprocess
import re
import logging
from typing import Tuple, Optional

def check_tcp_port(host: str, port: int, timeout: float = 2.0, logger_instance: Optional[logging.Logger] = None) -> Tuple[bool, float, Optional[str]]:
    """
    Checks if a TCP port is open on a given host by attempting a connection.

    This utility function is used to verify network connectivity to a device
    before attempting a full protocol connection. It provides a quick way to
    diagnose network issues like firewalls or incorrect IP/port configurations.

    Args:
        host (str): The hostname or IP address to connect to.
        port (int): The TCP port number to check.
        timeout (float): The connection timeout in seconds.
        logger_instance (Optional[logging.Logger]): An optional logger instance
            to use for debug messages. If None, a default logger is used.

    Returns:
        A tuple containing:
        - bool: True if the port is open and a connection was successful, False otherwise.
        - float: The connection latency in milliseconds if successful, otherwise -1.0.
        - Optional[str]: An error message if the connection failed, otherwise None.
    """
    effective_logger = logger_instance if logger_instance else logging.getLogger(__name__)
    effective_logger.debug(f"TCP Check (util): Attempting to connect to {host}:{port} with timeout {timeout}s")
    start_time = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            end_time = time.monotonic()
            latency_ms = (end_time - start_time) * 1000
            effective_logger.debug(f"TCP Check (util): {host}:{port} success. Latency: {latency_ms:.2f} ms")
            return True, latency_ms, None
    except socket.timeout:
        effective_logger.debug(f"TCP Check (util): {host}:{port} timeout.")
        return False, -1.0, "Timeout"
    except socket.error as e:
        effective_logger.debug(f"TCP Check (util): {host}:{port} socket error: {e}")
        return False, -1.0, str(e)
    except Exception as e_unexp:
        effective_logger.debug(f"TCP Check (util): {host}:{port} unexpected error: {e_unexp}")
        return False, -1.0, f"Unexpected: {str(e_unexp)}"

def check_icmp_ping(host: str, count: int = 1, timeout_s: int = 1, logger_instance: Optional[logging.Logger] = None) -> Tuple[bool, float, Optional[str]]:
    """
    Performs an ICMP ping to a host to check for reachability and latency.

    This function uses the system's native `ping` command, making it a reliable
    way to check basic network reachability. It adapts its command-line arguments
    for both Windows and Unix-like systems (Linux, macOS).

    Args:
        host (str): The hostname or IP address to ping.
        count (int): The number of ICMP packets to send.
        timeout_s (int): The timeout in seconds to wait for a reply.
        logger_instance (Optional[logging.Logger]): An optional logger instance
            to use for debug messages. If None, a default logger is used.

    Returns:
        A tuple containing:
        - bool: True if the host was reachable (ping exit code 0), False otherwise.
        - float: The average latency in milliseconds if successful and parsable,
                 otherwise -1.0.
        - Optional[str]: The raw output from the ping command or an error message.
    """
    effective_logger = logger_instance if logger_instance else logging.getLogger(__name__)
    effective_logger.debug(f"ICMP Check (util): Pinging {host} (count={count}, timeout={timeout_s}s)")
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    timeout_param_flag = '-w' if platform.system().lower() == 'windows' else '-W' 
    ping_timeout_value = timeout_s * 1000 if platform.system().lower() == 'windows' else timeout_s
    command = ['ping', param, str(count), timeout_param_flag, str(ping_timeout_value), host]
    raw_output = ""
    try:
        # Prevent console window from appearing on Windows
        startupinfo = None
        if platform.system().lower() == 'windows':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
        stdout, stderr = process.communicate(timeout=timeout_s + 2) 
        raw_output = stdout + stderr

        if process.returncode == 0 and stdout:
            avg_latency = -1.0; latencies = []
            if platform.system().lower() == 'windows':
                match = re.search(r"Average = (\d+)ms", stdout)
                if match: latencies.append(float(match.group(1)))
            else: 
                # More robust regex for Linux/macOS
                summary_match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)", stdout)
                if summary_match:
                    latencies.append(float(summary_match.group(1)))
                else: # Fallback for line-by-line parsing
                    for line_match in re.finditer(r"time=([\d.]+) ms", stdout):
                        latencies.append(float(line_match.group(1)))
            
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                effective_logger.debug(f"ICMP Check (util): {host} success. Avg Latency: {avg_latency:.2f} ms.")
                return True, avg_latency, raw_output.strip()
            else: 
                return True, -1.0, f"Success (exit 0), latency parsing failed."
        else:
            return False, -1.0, f"Exit code {process.returncode}. Output: {raw_output.strip()}"
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        return False, -1.0, f"Ping exception: {e}"