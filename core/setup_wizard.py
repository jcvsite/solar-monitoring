# core/setup_wizard.py
"""
First-Run Setup Wizard

Interactive console wizard that writes `config.ini` when configuration is
missing/incomplete, or when started with `python main.py --setup`.

Features:
- Detects when setup is required
- Inverter/BMS plugin selection from the plugin catalog
- Writes connection and core service defaults
- Marks setup_completed and enables console dashboard by default

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.plugin_catalog import list_plugins


def needs_setup(config_path: Path, force: bool = False) -> bool:
    if force:
        return True
    if not config_path.exists():
        return True
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError:
        return True
    if "setup_completed" in text.lower():
        # Explicit false triggers wizard
        for line in text.splitlines():
            if line.strip().lower().startswith("setup_completed"):
                val = line.split("=", 1)[-1].split(";")[0].strip().lower()
                return val in ("false", "0", "no", "off")
    # Missing PLUGIN_INSTANCES or empty → treat as new
    if "PLUGIN_INSTANCES" not in text:
        return True
    for line in text.splitlines():
        if line.strip().startswith("PLUGIN_INSTANCES"):
            val = line.split("=", 1)[-1].split(";")[0].strip()
            return not bool(val)
    return True


def _prompt(msg: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    try:
        raw = input(f"{msg}{suffix}: ").strip()
    except EOFError:
        raw = ""
    if not raw and default is not None:
        return default
    return raw


def _prompt_choice(title: str, options: List[Tuple[str, str]], allow_skip: bool = True) -> Optional[str]:
    """
    options: list of (id, label). Returns chosen id or None if skip.
    """
    print()
    print(title)
    print("-" * max(40, len(title)))
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}) {label}")
    if allow_skip:
        print("  0) Skip / None")
    while True:
        raw = _prompt("Enter number", "0" if allow_skip else "1")
        try:
            n = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if allow_skip and n == 0:
            return None
        if 1 <= n <= len(options):
            return options[n - 1][0]
        print("Invalid selection.")


def _prompt_yes_no(msg: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    raw = _prompt(f"{msg} ({d})", "y" if default else "n").lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


def _connection_block(defaults: Dict[str, Any], *, slave_prompt: Optional[str] = None) -> Dict[str, str]:
    conn = _prompt_choice(
        "Connection type",
        [("tcp", "TCP / network"), ("serial", "Serial / USB")],
        allow_skip=False,
    ) or "tcp"
    out: Dict[str, str] = {"connection_type": conn}
    id_prompt = slave_prompt or "Modbus slave / unit ID"
    if conn == "tcp":
        out["tcp_host"] = _prompt("TCP host / IP", defaults.get("tcp_host", "192.168.1.100"))
        out["tcp_port"] = _prompt("TCP port", str(defaults.get("tcp_port", 502)))
        out["slave_address"] = _prompt(id_prompt, str(defaults.get("slave_address", 1)))
    else:
        default_port = "COM3" if sys.platform.startswith("win") else "/dev/ttyUSB0"
        out["serial_port"] = _prompt("Serial port", defaults.get("serial_port", default_port))
        out["baud_rate"] = _prompt("Baud rate", str(defaults.get("baud_rate", 9600)))
        out["slave_address"] = _prompt(id_prompt, str(defaults.get("slave_address", 1)))
    return out


def _defaults_for_plugin(plugin_type: str) -> Dict[str, Any]:
    if "goodwe" in plugin_type:
        return {"tcp_port": 502, "slave_address": 247, "baud_rate": 9600}
    if "sofar" in plugin_type:
        return {"tcp_port": 8899, "slave_address": 1, "baud_rate": 9600}
    if "sungrow" in plugin_type:
        return {"tcp_port": 502, "slave_address": 1, "baud_rate": 9600}
    if "jk_bms" in plugin_type:
        return {"baud_rate": 115200, "tcp_port": 8899}
    if "jbd" in plugin_type or "daly" in plugin_type:
        return {"baud_rate": 9600, "tcp_port": 8899}
    if "voltronic" in plugin_type or "powmr" in plugin_type:
        return {"baud_rate": 2400 if "voltronic" in plugin_type else 9600, "tcp_port": 23}
    if "pylontech" in plugin_type:
        return {"baud_rate": 115200, "tcp_port": 8899}
    if "seplos_bms_v2" in plugin_type:
        # Pack address is Seplos ADR (usually 0), not Modbus slave ID
        return {"tcp_port": 5022, "slave_address": 0, "baud_rate": 19200}
    if "deye" in plugin_type:
        return {"tcp_port": 8899, "slave_address": 1}
    return {"tcp_port": 502, "slave_address": 1, "baud_rate": 9600}


def _extra_plugin_keys(plugin_type: str) -> Dict[str, str]:
    extras: Dict[str, str] = {}
    if "deye" in plugin_type:
        extras["deye_model_series"] = "auto"
    if "growatt" in plugin_type:
        extras["has_storage"] = "auto"
    if "goodwe" in plugin_type:
        extras["goodwe_map"] = "auto"
    if "sofar" in plugin_type:
        extras["sofar_series"] = "auto"
    if "jk_bms" in plugin_type:
        extras["jk_protocol_mode"] = "uart"
    if "voltronic" in plugin_type:
        extras["pi_protocol"] = "auto"
    if "seplos_bms_v2" in plugin_type:
        # Seplos V2 uses seplos_* keys — map connection into those
        pass
    return extras


def _normalize_seplos_v2(conn: Dict[str, str]) -> Dict[str, str]:
    out = dict(conn)
    ctype = out.pop("connection_type", "serial")
    out["seplos_connection_type"] = ctype
    # Always keep pack address (ADR). Default 0 — do not confuse with Modbus slave 1.
    out["seplos_pack_address"] = out.pop("slave_address", "0")
    if ctype == "tcp":
        out["seplos_tcp_host"] = out.pop("tcp_host", "192.168.1.100")
        out["seplos_tcp_port"] = out.pop("tcp_port", "5022")
    else:
        out["seplos_serial_port"] = out.pop("serial_port", "/dev/ttyUSB0")
        out["seplos_baud_rate"] = out.pop("baud_rate", "19200")
        out.pop("tcp_host", None)
        out.pop("tcp_port", None)
    return out


def _instance_name(plugin_type: str, category: str) -> str:
    base = plugin_type.split(".")[-1].replace("_plugin", "")
    # Keep readable
    mapping = {
        "solis_modbus": "INV_Solis",
        "deye_sunsynk": "INV_Deye",
        "growatt_modbus": "INV_Growatt",
        "goodwe_modbus": "INV_GoodWe",
        "sofar_modbus": "INV_Sofar",
        "sungrow_modbus": "INV_Sungrow",
        "felicity_modbus": "INV_Felicity",
        "voltronic_pi": "INV_Voltronic",
        "luxpower_modbus": "INV_LuxPower",
        "eg4_modbus": "INV_EG4",
        "srne_modbus": "INV_SRNE",
        "powmr_rs232": "INV_POWMR",
        "seplos_bms_v2": "BMS_Seplos_v2",
        "seplos_bms_v3": "BMS_Seplos_v3",
        "jk_bms": "BMS_JK",
        "jbd_bms": "BMS_JBD",
        "daly_bms": "BMS_Daly",
        "pylontech_bms": "BMS_Pylontech",
    }
    return mapping.get(base, f"{'INV' if category == 'inverter' else 'BMS'}_{base}")


def _render_ini(
    instances: List[Tuple[str, str, Dict[str, str]]],
    *,
    timezone: str,
    pv_kw: float,
    batt_kwh: float,
    enable_web: bool,
    enable_mqtt: bool,
    enable_weather: bool,
    mqtt: Dict[str, str],
) -> str:
    names = [n for n, _, _ in instances]
    lines = [
        "# Generated by Solar Monitoring first-run setup wizard",
        "# Re-run: python main.py --setup",
        "",
        "[GENERAL]",
        "setup_completed = true",
        f"PLUGIN_INSTANCES = {', '.join(names) if names else ''}",
        "POLL_INTERVAL = 5",
        f"LOCAL_TIMEZONE = {timezone}",
        "CHECK_FOR_UPDATES = false",
        "MAX_RECONNECT_ATTEMPTS = 5",
        "",
        "[BMS_AGGREGATION]",
        "bms_aggregation_mode = capacity_weighted",
        "",
        "[INVERTER_SYSTEM]",
        "DEFAULT_MPPT_COUNT = 2",
        f"PV_INSTALLED_CAPACITY_W = {pv_kw * 1000.0:.1f}",
        f"INVERTER_MAX_AC_POWER_W = {max(pv_kw * 1000.0 * 0.9, 3000.0):.1f}",
        f"BATTERY_USABLE_CAPACITY_KWH = {batt_kwh:.2f}",
        "BATTERY_MAX_CHARGE_POWER_W = 5000.0",
        "BATTERY_MAX_DISCHARGE_POWER_W = 6000.0",
        "",
        "[LOGGING]",
        "LOG_LEVEL = INFO",
        "LOG_TO_FILE = true",
        "",
        "[CONSOLE_DASHBOARD]",
        "ENABLE_DASHBOARD = true",
        "DASHBOARD_UPDATE_INTERVAL = 1",
        "FONT_SCALE = normal",
        "",
        "[WEB_DASHBOARD]",
        f"ENABLE_WEB_DASHBOARD = {'true' if enable_web else 'false'}",
        "WEB_DASHBOARD_PORT = 8081",
        "ENABLE_HTTPS = false",
        "WEB_UPDATE_INTERVAL = 2.0",
        'FLASK_SECRET_KEY = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_STRING"',
        "",
        "[MQTT]",
        f"ENABLE_MQTT = {'true' if enable_mqtt else 'false'}",
        f"MQTT_HOST = {mqtt.get('host', '127.0.0.1')}",
        f"MQTT_PORT = {mqtt.get('port', '1883')}",
        f"MQTT_USERNAME = {mqtt.get('user', '')}",
        f"MQTT_PASSWORD = {mqtt.get('password', '')}",
        "ENABLE_HA_DISCOVERY = true",
        "HA_DISCOVERY_PREFIX = homeassistant",
        "MQTT_TOPIC = solar",
        "MQTT_UPDATE_INTERVAL = 5",
        "",
        "[DATABASE]",
        "DB_FILE = solis_history.db",
        "HISTORY_MAX_AGE_HOURS = 720",
        "POWER_HISTORY_INTERVAL_SECONDS = 60",
        "ENABLE_AUTO_VACUUM = true",
        "VACUUM_INTERVAL_HOURS = 168",
        "DAILY_SUMMARY_MAX_AGE_DAYS = 0",
        "",
        "[METRICS]",
        "ENABLE_PROMETHEUS = false",
        "PROMETHEUS_PORT = 9108",
        "",
        "[WATCHDOG]",
        "WATCHDOG_TIMEOUT = 120",
        "WATCHDOG_GRACE_PERIOD = 30",
        "MAX_PLUGIN_RELOAD_ATTEMPTS = 3",
        "",
        "[FILTER]",
        "FILTERING_MODE = adaptive",
        "",
        "[WEATHER]",
        "; Enable or disable the weather widget on the dashboard",
        f"ENABLE_WEATHER_WIDGET = {'True' if enable_weather else 'False'}",
        "; Use browser's geolocation to find location automatically. Falls back to default if denied.",
        "WEATHER_USE_AUTOMATIC_LOCATION = False",
        "; Default location to use if automatic detection is off or fails.",
        "WEATHER_DEFAULT_LATITUDE = 16.6167",
        "WEATHER_DEFAULT_LONGITUDE = 120.3166",
        "; The initial zoom level for the weather map (e.g., 5 is country-level, 10 is city-level)",
        "WEATHER_MAP_ZOOM_LEVEL = 5",
        "; Temperature unit: \"celsius\" or \"fahrenheit\"",
        "WEATHER_TEMPERATURE_UNIT = celsius",
        "; How often to refresh weather data, in minutes.",
        "WEATHER_UPDATE_INTERVAL_MINUTES = 15",
        "",
        "[TUYA]",
        "ENABLE_TUYA = false",
        "",
    ]
    for name, ptype, cfg in instances:
        lines.append(f"[PLUGIN_{name}]")
        lines.append(f"plugin_type = {ptype}")
        for k, v in cfg.items():
            lines.append(f"{k} = {v}")
        lines.append("")
    return "\n".join(lines) + "\n"


def run_setup_wizard(config_path: Path) -> bool:
    """
    Interactive wizard. Returns True if config was written successfully.
    """
    print()
    print("=" * 60)
    print("  Solar Monitoring — First-run setup")
    print("=" * 60)
    print("Answer a few questions. Settings are saved to config.ini.")
    print("Press Ctrl+C to cancel.")
    print()

    inv_options = []
    for p in list_plugins(category="inverter", include_unloadable=True):
        status = (p.get("meta") or {}).get("status", "?")
        label = f"{p['label']} [{status}]"
        if not p.get("loadable"):
            label += " (not installed yet)"
        inv_options.append((p["plugin_type"], label))

    bms_options = []
    for p in list_plugins(category="bms", include_unloadable=True):
        status = (p.get("meta") or {}).get("status", "?")
        label = f"{p['label']} [{status}]"
        if not p.get("loadable"):
            label += " (not installed yet)"
        bms_options.append((p["plugin_type"], label))

    instances: List[Tuple[str, str, Dict[str, str]]] = []

    inv_type = _prompt_choice("Select inverter (or skip for BMS-only)", inv_options, allow_skip=True)
    if inv_type:
        if not any(p["plugin_type"] == inv_type and p.get("loadable") for p in list_plugins(category="inverter")):
            print(f"WARNING: Plugin '{inv_type}' is not loadable yet. Config will still be written.")
        name = _instance_name(inv_type, "inverter")
        cfg = _connection_block(_defaults_for_plugin(inv_type))
        cfg.update(_extra_plugin_keys(inv_type))
        instances.append((name, inv_type, cfg))

    while True:
        bms_type = _prompt_choice(
            "Select BMS (or skip). You can add another after.",
            bms_options,
            allow_skip=True,
        )
        if not bms_type:
            break
        if not any(p["plugin_type"] == bms_type and p.get("loadable") for p in list_plugins(category="bms")):
            print(f"WARNING: Plugin '{bms_type}' is not loadable yet. Config will still be written.")
        name = _instance_name(bms_type, "bms")
        # Avoid duplicate instance names
        existing = {n for n, _, _ in instances}
        base = name
        i = 2
        while name in existing:
            name = f"{base}_{i}"
            i += 1
        slave_prompt = None
        if "seplos_bms_v2" in bms_type:
            slave_prompt = "Seplos pack address ADR (usually 0)"
        cfg = _connection_block(_defaults_for_plugin(bms_type), slave_prompt=slave_prompt)
        cfg.update(_extra_plugin_keys(bms_type))
        if "seplos_bms_v2" in bms_type:
            cfg = _normalize_seplos_v2(cfg)
        instances.append((name, bms_type, cfg))
        if not _prompt_yes_no("Add another BMS?", False):
            break

    if not instances:
        print("No devices selected. Aborting setup.")
        return False

    timezone = _prompt("Timezone (IANA)", "Asia/Manila")
    try:
        pv_kw = float(_prompt("PV array size (kW)", "6.6"))
    except ValueError:
        pv_kw = 6.6
    try:
        batt_kwh = float(_prompt("Battery usable capacity (kWh)", "10"))
    except ValueError:
        batt_kwh = 10.0

    enable_web = _prompt_yes_no("Enable web dashboard?", True)
    enable_weather = _prompt_yes_no("Enable weather widget on the web dashboard?", True)
    enable_mqtt = _prompt_yes_no("Enable MQTT / Home Assistant?", False)
    mqtt: Dict[str, str] = {"host": "127.0.0.1", "port": "1883", "user": "", "password": ""}
    if enable_mqtt:
        mqtt["host"] = _prompt("MQTT host", "127.0.0.1")
        mqtt["port"] = _prompt("MQTT port", "1883")
        mqtt["user"] = _prompt("MQTT username", "")
        try:
            mqtt["password"] = getpass.getpass("MQTT password (hidden): ")
        except Exception:
            mqtt["password"] = _prompt("MQTT password", "")

    content = _render_ini(
        instances,
        timezone=timezone,
        pv_kw=pv_kw,
        batt_kwh=batt_kwh,
        enable_web=enable_web,
        enable_mqtt=enable_mqtt,
        enable_weather=enable_weather,
        mqtt=mqtt,
    )

    if config_path.exists():
        backup = config_path.with_suffix(".ini.bak")
        try:
            backup.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Backed up existing config to {backup.name}")
        except OSError as e:
            print(f"Could not backup existing config: {e}")

    config_path.write_text(content, encoding="utf-8")
    print()
    print(f"Wrote {config_path}")
    print("Console dashboard will start next (ENABLE_DASHBOARD=true).")
    print("Re-run setup anytime: python main.py --setup")
    print()
    return True
