# services/mdns_service.py
"""
mDNS / Zeroconf advertiser for Solar Monitoring LAN discovery.

Publishes ``_solar-monitoring._tcp.local.`` so ESP32 displays (and a future
Home Assistant custom component) can find the HTTP API without a fixed IP.
"""
from __future__ import annotations

import logging
import socket
from typing import Optional

from core.app_state import AppState

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_solar-monitoring._tcp.local."


class MdnsService:
    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self._zeroconf = None
        self._info = None
        self.enabled = bool(getattr(app_state, "enable_mdns", False))

    def start(self) -> None:
        if not self.enabled:
            logger.info("mDNS disabled (ENABLE_MDNS=false).")
            return
        if not self.app_state.enable_web_dashboard:
            logger.info("mDNS skipped: web dashboard is disabled.")
            return
        try:
            from zeroconf import ServiceInfo, Zeroconf
        except ImportError:
            logger.error("zeroconf package not installed; mDNS unavailable. pip install zeroconf")
            return

        hostname = (getattr(self.app_state, "mdns_hostname", None) or "solar-monitoring").strip()
        instance = (getattr(self.app_state, "mdns_instance_name", None) or self.app_state.system_title or "Solar Monitoring").strip()
        port = int(self.app_state.web_dashboard_port or 8081)
        https = 1 if getattr(self.app_state, "enable_https", False) else 0

        try:
            local_ip = _guess_lan_ip()
            host_ip = socket.inet_aton(local_ip)
        except OSError as e:
            logger.warning(f"mDNS: could not resolve LAN IP ({e}); advertising skipped.")
            return

        props = {
            b"app": b"solar-monitoring",
            b"api_version": b"1",
            b"path": b"/api/display",
            b"bms_path": b"/api/display/bms",
            b"history_path": b"/api/display/history",
            b"version": str(self.app_state.version).encode("utf-8"),
            b"https": str(https).encode("utf-8"),
            b"title": str(self.app_state.system_title).encode("utf-8")[:60],
        }

        server_name = f"{hostname}.local."
        service_name = f"{instance}.{SERVICE_TYPE}"

        try:
            self._zeroconf = Zeroconf()
            self._info = ServiceInfo(
                SERVICE_TYPE,
                service_name,
                addresses=[host_ip],
                port=port,
                properties=props,
                server=server_name,
            )
            self._zeroconf.register_service(self._info)
            logger.info(
                f"mDNS: advertising {service_name} on {local_ip}:{port} "
                f"(hostname {hostname}.local)"
            )
        except Exception as e:
            logger.warning(f"mDNS advertise failed (HTTP still works): {e}")
            self.stop()

    def stop(self) -> None:
        if self._zeroconf and self._info:
            try:
                self._zeroconf.unregister_service(self._info)
            except Exception as e:
                logger.debug(f"mDNS unregister note: {e}")
        if self._zeroconf:
            try:
                self._zeroconf.close()
            except Exception as e:
                logger.debug(f"mDNS close note: {e}")
        self._zeroconf = None
        self._info = None


def _guess_lan_ip() -> str:
    """Best-effort LAN IPv4 without sending traffic."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    finally:
        sock.close()
