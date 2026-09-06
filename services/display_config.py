# services/display_config.py
"""Global ESP32 display settings (display_config.json) and firmware release proxy."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "display_config.json"
GITHUB_REPO = "jcvsite/Solar-monitoring-viewer-esp32"
FIRMWARE_ASSET_PREFIX = "solar-viewer-cyd_esp32"

LAYOUT_CATALOG: List[Dict[str, Any]] = [
    {"id": 0, "name": "Classic", "description": "Large SOC, vertical battery, 2×2 metric tiles"},
    {"id": 1, "name": "Compact", "description": "Dense header metrics in a single row"},
    {"id": 2, "name": "Ring", "description": "SOC arc gauge with corner metrics"},
    {"id": 3, "name": "Bars", "description": "Horizontal power bar meters"},
    {"id": 4, "name": "Flow", "description": "PV → Home ← Grid energy flow"},
]

THEME_CATALOG: List[Dict[str, Any]] = [
    {"id": 0, "name": "Dark", "swatch": "#1C1C1E"},
    {"id": 1, "name": "Light", "swatch": "#F2F2F7"},
    {"id": 2, "name": "Solar", "swatch": "#FF9F0A"},
    {"id": 3, "name": "Ocean", "swatch": "#0A84FF"},
    {"id": 4, "name": "Forest", "swatch": "#30D158"},
]

DEFAULT_DISPLAY_CONFIG: Dict[str, Any] = {
    "config_rev": 1,
    "glance_layout": 0,
    "theme": 0,
    "rotation": 0,
    "brightness": 200,
    "poll_ms": 5000,
    "check_for_update": False,
    "auto_install_update": False,
    "grid_offline_alert": True,
    "force_update": False,
    "force_update_version": "",
    "settings_pin": "",
}


def normalize_settings_pin(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if len(s) == 4 and s.isdigit():
        return s
    return ""


def settings_pin_is_set(cfg: Dict[str, Any]) -> bool:
    return bool(normalize_settings_pin(cfg.get("settings_pin", "")))


def verify_settings_pin(cfg: Dict[str, Any], provided: Any) -> bool:
    stored = normalize_settings_pin(cfg.get("settings_pin", ""))
    if not stored:
        return True
    return normalize_settings_pin(provided) == stored


def check_settings_pin_for_write(current: Dict[str, Any], body: Dict[str, Any]) -> Optional[str]:
    """Return error message if PIN is required but missing/invalid."""
    if not settings_pin_is_set(current):
        return None
    if not verify_settings_pin(current, body.get("pin")):
        return "Invalid PIN"
    return None


def config_path(project_root: Optional[str] = None) -> str:
    root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, CONFIG_FILENAME)


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def validate_display_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return sanitized config dict."""
    src = data if isinstance(data, dict) else {}
    out = deepcopy(DEFAULT_DISPLAY_CONFIG)
    out["config_rev"] = max(1, _clamp_int(src.get("config_rev"), 1, 2_000_000_000, out["config_rev"]))
    out["glance_layout"] = _clamp_int(src.get("glance_layout"), 0, 4, 0)
    out["theme"] = _clamp_int(src.get("theme"), 0, 4, 0)
    out["rotation"] = _clamp_int(src.get("rotation"), 0, 3, 0)
    out["brightness"] = _clamp_int(src.get("brightness"), 0, 255, 200)
    out["poll_ms"] = _clamp_int(src.get("poll_ms"), 2000, 60000, 5000)
    out["check_for_update"] = bool(src.get("check_for_update", False))
    auto = bool(src.get("auto_install_update", False))
    out["auto_install_update"] = auto
    if auto:
        out["check_for_update"] = True
    out["grid_offline_alert"] = bool(src.get("grid_offline_alert", True))
    out["force_update"] = bool(src.get("force_update", False))
    ver = src.get("force_update_version")
    out["force_update_version"] = str(ver).strip() if ver else ""
    if "settings_pin" in src:
        out["settings_pin"] = normalize_settings_pin(src.get("settings_pin"))
    else:
        out["settings_pin"] = normalize_settings_pin(out.get("settings_pin", ""))
    return out


def load_display_config(project_root: Optional[str] = None) -> Dict[str, Any]:
    path = config_path(project_root)
    if not os.path.isfile(path):
        return deepcopy(DEFAULT_DISPLAY_CONFIG)
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return validate_display_config(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load %s: %s — using defaults", path, exc)
        return deepcopy(DEFAULT_DISPLAY_CONFIG)


def save_display_config(data: Dict[str, Any], project_root: Optional[str] = None) -> Dict[str, Any]:
    path = config_path(project_root)
    current = load_display_config(project_root)
    merged = validate_display_config({**current, **data})
    merged["config_rev"] = int(current.get("config_rev", 0)) + 1
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
        fh.write("\n")
    return merged


def build_config_response(project_root: Optional[str] = None, *, include_pin: bool = False) -> Dict[str, Any]:
    cfg = load_display_config(project_root)
    pin = normalize_settings_pin(cfg.get("settings_pin", ""))
    payload = {
        "ok": True,
        "app": "solar-monitoring",
        **cfg,
    }
    if include_pin:
        payload["settings_pin_set"] = bool(pin)
    else:
        payload.pop("settings_pin", None)
        payload["settings_pin_set"] = bool(pin)
    return payload


def _github_request(url: str, token: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "solar-monitoring-display-proxy",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest_release(token: str = "") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Returns (release_info, error_message)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        data = _github_request(url, token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, "No releases published yet"
        return None, f"GitHub HTTP {exc.code}"
    except Exception as exc:
        logger.warning("GitHub release fetch failed: %s", exc)
        return None, str(exc)

    tag = str(data.get("tag_name") or "")
    assets = data.get("assets") or []
    bin_url = None
    bin_name = None
    for asset in assets:
        name = str(asset.get("name") or "")
        if name.startswith(FIRMWARE_ASSET_PREFIX) and name.endswith(".bin"):
            bin_name = name
            bin_url = asset.get("browser_download_url")
            break
    if not bin_url:
        for asset in assets:
            name = str(asset.get("name") or "")
            if name == "firmware.bin" or name.endswith("firmware.bin"):
                bin_name = name
                bin_url = asset.get("browser_download_url")
                break
    return {
        "tag": tag,
        "name": str(data.get("name") or tag),
        "published_at": data.get("published_at"),
        "html_url": data.get("html_url"),
        "body": str(data.get("body") or "")[:2000],
        "asset_name": bin_name,
        "asset_url": bin_url,
    }, None


def download_firmware_bytes(token: str = "", version: str = "") -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Download firmware .bin from GitHub releases. Returns (bytes, filename, error)."""
    release, err = fetch_latest_release(token)
    if err or not release:
        return None, None, err or "Release unavailable"
    asset_url = release.get("asset_url")
    asset_name = release.get("asset_name") or "firmware.bin"
    if version and version.strip() and version.strip() != release.get("tag"):
        raw = version.strip()
        candidates = [raw]
        if raw.startswith(("v", "V")):
            candidates.append(raw[1:])
        else:
            candidates.append("v" + raw)
        last_exc: Optional[Exception] = None
        found = False
        for cand in candidates:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{cand}"
            try:
                rel = _github_request(url, token)
                for asset in rel.get("assets") or []:
                    name = str(asset.get("name") or "")
                    if name.endswith(".bin"):
                        asset_url = asset.get("browser_download_url")
                        asset_name = name
                        found = True
                        break
                if found:
                    break
            except Exception as exc:
                last_exc = exc
        if not found and last_exc is not None:
            return None, None, str(last_exc)
    if not asset_url:
        return None, None, "No firmware asset in release"
    headers = {"User-Agent": "solar-monitoring-display-proxy"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(asset_url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read(), asset_name, None
    except Exception as exc:
        logger.warning("Firmware download failed: %s", exc)
        return None, None, str(exc)
