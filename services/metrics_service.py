# services/metrics_service.py
"""
Prometheus Metrics Service

Lightweight stdlib HTTP exporter that exposes selected Solar Monitoring gauges
for scraping by Prometheus (default port configurable via [METRICS]).

Features:
- Threading HTTP server for /metrics
- Gauges derived from shared_data StandardDataKeys
- Enable/disable and bind address from config.ini
- Minimal dependency footprint (no prometheus_client required)

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from core.app_state import AppState
from plugins.plugin_interface import StandardDataKeys

logger = logging.getLogger(__name__)


def _unwrap(packet: dict, key: str):
    entry = packet.get(key)
    if isinstance(entry, dict) and "value" in entry:
        return entry.get("value")
    return entry


def _num(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MetricsService:
    """Exposes /metrics in Prometheus text format when enabled."""

    def __init__(self, app_state: AppState):
        self.app_state = app_state
        self.enabled = app_state.config.getboolean("METRICS", "ENABLE_PROMETHEUS", fallback=False)
        self.port = app_state.config.getint("METRICS", "PROMETHEUS_PORT", fallback=9108)
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._start_monotonic = time.monotonic()

    def start(self) -> None:
        if not self.enabled:
            logger.info("Prometheus metrics disabled (METRICS.ENABLE_PROMETHEUS=false).")
            return
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A003
                logger.debug("metrics http: " + format, *args)

            def do_GET(self):  # noqa: N802
                path = urlparse(self.path).path
                if path not in ("/metrics", "/"):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not Found\n")
                    return
                body = service.render_metrics().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        try:
            self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
            self._thread = threading.Thread(target=self._server.serve_forever, name="MetricsService", daemon=True)
            self._thread.start()
            logger.info(f"Prometheus metrics listening on :{self.port}/metrics")
        except Exception as e:
            logger.error(f"Failed to start Prometheus metrics server: {e}", exc_info=True)
            self._server = None

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
            logger.info("Prometheus metrics server stopped.")

    def render_metrics(self) -> str:
        lines = [
            "# HELP solar_process_uptime_seconds Process uptime in seconds.",
            "# TYPE solar_process_uptime_seconds gauge",
            f"solar_process_uptime_seconds {time.monotonic() - self._start_monotonic:.1f}",
        ]
        with self.app_state.data_lock:
            data = dict(self.app_state.shared_data or {})

        gauges = [
            ("solar_pv_power_watts", StandardDataKeys.PV_TOTAL_DC_POWER_WATTS, "PV DC power watts"),
            ("solar_load_power_watts", StandardDataKeys.LOAD_TOTAL_POWER_WATTS, "Load power watts"),
            ("solar_grid_power_watts", StandardDataKeys.GRID_TOTAL_ACTIVE_POWER_WATTS, "Grid power watts"),
            ("solar_battery_power_watts", StandardDataKeys.BATTERY_POWER_WATTS, "Battery power watts"),
            ("solar_battery_soc_percent", StandardDataKeys.BATTERY_STATE_OF_CHARGE_PERCENT, "Battery SOC percent"),
        ]
        for metric, key, help_txt in gauges:
            val = _num(_unwrap(data, key))
            lines.append(f"# HELP {metric} {help_txt}.")
            lines.append(f"# TYPE {metric} gauge")
            if val is not None:
                lines.append(f"{metric} {val}")

        now = time.monotonic()
        lines.append("# HELP solar_plugin_connected Plugin connected flag (1/0).")
        lines.append("# TYPE solar_plugin_connected gauge")
        lines.append("# HELP solar_plugin_poll_age_seconds Seconds since last successful poll.")
        lines.append("# TYPE solar_plugin_poll_age_seconds gauge")
        lines.append("# HELP solar_plugin_consecutive_failures Consecutive failed polls.")
        lines.append("# TYPE solar_plugin_consecutive_failures gauge")
        for instance_id, plugin in self.app_state.active_plugin_instances.items():
            status = str(getattr(plugin, "connection_status", "") or "").lower()
            connected = 1 if status == "connected" else 0
            last_ok = self.app_state.last_successful_poll_timestamp_per_plugin.get(instance_id, 0.0)
            age = (now - last_ok) if last_ok else -1
            fails = self.app_state.plugin_consecutive_failures.get(instance_id, 0)
            label = f'instance="{instance_id}"'
            lines.append(f"solar_plugin_connected{{{label}}} {connected}")
            lines.append(f"solar_plugin_poll_age_seconds{{{label}}} {age:.1f}")
            lines.append(f"solar_plugin_consecutive_failures{{{label}}} {fails}")

        pack_count = _num(_unwrap(data, "bms_pack_count"))
        if pack_count is not None:
            lines.append("# HELP solar_bms_pack_count Number of BMS packs aggregated.")
            lines.append("# TYPE solar_bms_pack_count gauge")
            lines.append(f"solar_bms_pack_count {pack_count}")

        lines.append("")
        return "\n".join(lines)
