# core/config_validator.py
"""
Plugin Configuration Validator

Extended validation for configured plugin instances in the Solar Monitoring
Framework. Checks importable plugin types, rejects known-bad types, and verifies
required connection keys before startup proceeds.

Features:
- Importable plugin_type verification
- Rejection of legacy/invalid plugin type names
- Connection-key presence checks per plugin category
- Fatal exit on unrecoverable configuration errors

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import importlib
import inspect
import logging
import sys
from typing import Any, Dict, List, Optional, Type

from core.app_state import AppState
from plugins.plugin_interface import DevicePlugin

logger = logging.getLogger(__name__)

KNOWN_BAD_PLUGIN_TYPES = {
    "inverter.powmr_modbus_plugin": "Use inverter.powmr_rs232_plugin (inv8851). There is no powmr_modbus_plugin module.",
}


def _strip_comment(value: Any) -> str:
    return str(value).split(";")[0].strip()


def _resolve_plugin_class(plugin_type_full: str) -> Optional[Type[DevicePlugin]]:
    if "." not in plugin_type_full:
        return None
    category, module_name = plugin_type_full.split(".", 1)
    mod_path = f"plugins.{category}.{module_name}"
    try:
        plug_mod = importlib.import_module(mod_path)
    except ImportError as e:
        logger.debug("Cannot import %s: %s", mod_path, e)
        return None
    for item_name in dir(plug_mod):
        item_obj = getattr(plug_mod, item_name)
        if (
            isinstance(item_obj, type)
            and issubclass(item_obj, DevicePlugin)
            and item_obj is not DevicePlugin
            and not inspect.isabstract(item_obj)
        ):
            return item_obj
    return None


def _validate_connection_keys(instance_name: str, section: Dict[str, str], plugin_type: str) -> List[str]:
    errors: List[str] = []
    # Seplos V2 uses seplos_connection_type
    if "seplos" in plugin_type and "v2" in plugin_type:
        conn = _strip_comment(section.get("seplos_connection_type", section.get("connection_type", "serial"))).lower()
        if conn == "tcp":
            if not _strip_comment(section.get("seplos_tcp_host", "")):
                errors.append(f"[PLUGIN_{instance_name}] seplos_tcp_host required for TCP.")
        elif conn == "serial":
            if not _strip_comment(section.get("seplos_serial_port", section.get("serial_port", ""))):
                # serial_port optional in some examples — warn only via debug; require at least one
                if "seplos_serial_port" not in section and "serial_port" not in section:
                    errors.append(f"[PLUGIN_{instance_name}] serial_port/seplos_serial_port recommended for serial.")
        return errors

    conn = _strip_comment(section.get("connection_type", "tcp")).lower()
    if conn == "tcp":
        if not _strip_comment(section.get("tcp_host", "")):
            # Many examples leave tcp_host as placeholder — only error if connection_type explicitly tcp and empty
            host = section.get("tcp_host")
            if host is not None and not _strip_comment(host):
                errors.append(f"[PLUGIN_{instance_name}] tcp_host is empty.")
    elif conn == "serial":
        if "serial_port" in section and not _strip_comment(section.get("serial_port", "")):
            errors.append(f"[PLUGIN_{instance_name}] serial_port is empty.")
    return errors


def validate_plugin_configurations(app_state: AppState) -> List[str]:
    """Return a list of validation error strings (empty if OK)."""
    errors: List[str] = []
    for instance_name in app_state.configured_plugin_instance_names:
        section_name = f"PLUGIN_{instance_name}"
        if not app_state.config.has_section(section_name):
            errors.append(f"Missing config section [{section_name}].")
            continue
        section = dict(app_state.config.items(section_name))
        plugin_type = _strip_comment(section.get("plugin_type", ""))
        if not plugin_type:
            errors.append(f"Missing 'plugin_type' in [{section_name}].")
            continue
        if plugin_type in KNOWN_BAD_PLUGIN_TYPES:
            errors.append(f"[{section_name}] Invalid plugin_type '{plugin_type}': {KNOWN_BAD_PLUGIN_TYPES[plugin_type]}")
            continue
        if "." not in plugin_type:
            errors.append(f"[{section_name}] plugin_type '{plugin_type}' must be 'category.module_name'.")
            continue
        plugin_cls = _resolve_plugin_class(plugin_type)
        if plugin_cls is None:
            errors.append(f"[{section_name}] Cannot import/resolve DevicePlugin for plugin_type '{plugin_type}'.")
            continue
        meta = plugin_cls.get_plugin_meta()
        logger.info(
            "Validated plugin '%s' -> %s (status=%s, protocols=%s)",
            instance_name,
            meta.get("plugin_id"),
            meta.get("status"),
            meta.get("protocols"),
        )
        errors.extend(_validate_connection_keys(instance_name, section, plugin_type))
    return errors


def validate_and_exit_on_error(app_state: AppState) -> None:
    """Run extended validation; exit process on failure."""
    errors = validate_plugin_configurations(app_state)
    if errors:
        for err in errors:
            logger.critical("Config validation: %s", err)
        logger.critical("Configuration validation failed (%d error(s)). Exiting.", len(errors))
        sys.exit(1)
    logger.info("Extended plugin configuration validated successfully.")
