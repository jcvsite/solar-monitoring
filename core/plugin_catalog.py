# core/plugin_catalog.py
"""
Plugin Catalog

Discoverable catalog of inverter and BMS plugins for the setup wizard and
documentation surfaces in the Solar Monitoring Framework.

Features:
- Explicit registry of plugin_type paths and display labels
- Live PLUGIN_META introspection when imports succeed
- Helpers used by the first-run setup wizard

GitHub Project: https://github.com/jcvsite/solar-monitoring
License: MIT
"""
from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, Dict, List, Optional, Type

from plugins.plugin_interface import DevicePlugin

logger = logging.getLogger(__name__)

# Explicit registry: (plugin_type module path, display label)
# Keep in sync when adding plugins. Wizard prefers live PLUGIN_META when import works.
KNOWN_PLUGINS: List[Dict[str, str]] = [
    {"plugin_type": "inverter.solis_modbus_plugin", "label": "Solis (Modbus)"},
    {"plugin_type": "inverter.deye_sunsynk_plugin", "label": "Deye / Sunsynk (Modbus)"},
    {"plugin_type": "inverter.growatt_modbus_plugin", "label": "Growatt (Modbus)"},
    {"plugin_type": "inverter.goodwe_modbus_plugin", "label": "GoodWe EH/ET (Modbus)"},
    {"plugin_type": "inverter.sofar_modbus_plugin", "label": "Sofar Hybrid (Modbus)"},
    {"plugin_type": "inverter.sungrow_modbus_plugin", "label": "Sungrow SH Hybrid (Modbus)"},
    {"plugin_type": "inverter.felicity_modbus_plugin", "label": "Felicity T-REX (Modbus)"},
    {"plugin_type": "inverter.voltronic_pi_plugin", "label": "Voltronic / Axpert / MPP (PI30)"},
    {"plugin_type": "inverter.luxpower_modbus_plugin", "label": "LuxPower (Modbus)"},
    {"plugin_type": "inverter.eg4_modbus_plugin", "label": "EG4 (Modbus)"},
    {"plugin_type": "inverter.srne_modbus_plugin", "label": "SRNE (Modbus)"},
    {"plugin_type": "inverter.powmr_rs232_plugin", "label": "POWMR (inv8851 RS232)"},
    {"plugin_type": "battery.seplos_bms_v2_plugin", "label": "Seplos BMS V2"},
    {"plugin_type": "battery.seplos_bms_v3_plugin", "label": "Seplos BMS V3"},
    {"plugin_type": "battery.jk_bms_plugin", "label": "JK BMS"},
    {"plugin_type": "battery.jbd_bms_plugin", "label": "JBD / Xiaoxiang / Overkill BMS"},
    {"plugin_type": "battery.daly_bms_plugin", "label": "Daly Smart BMS"},
    {"plugin_type": "battery.pylontech_bms_plugin", "label": "Pylontech (console/RS485)"},
]


def _load_plugin_class(plugin_type: str) -> Optional[Type[DevicePlugin]]:
    try:
        category, module_name = plugin_type.split(".", 1)
        mod = importlib.import_module(f"plugins.{category}.{module_name}")
        for name in dir(mod):
            obj = getattr(mod, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, DevicePlugin)
                and obj is not DevicePlugin
                and not inspect.isabstract(obj)
            ):
                return obj
    except Exception as e:
        logger.debug("Catalog skip %s: %s", plugin_type, e)
    return None


def list_plugins(category: Optional[str] = None, include_unloadable: bool = False) -> List[Dict[str, Any]]:
    """
    Return plugin catalog entries with live PLUGIN_META when available.

    category: 'inverter' | 'bms' | None (all)
    """
    out: List[Dict[str, Any]] = []
    for entry in KNOWN_PLUGINS:
        ptype = entry["plugin_type"]
        cat = ptype.split(".", 1)[0]
        meta_cat = "bms" if cat == "battery" else cat
        if category and meta_cat != category and not (category == "bms" and cat == "battery"):
            if category == "inverter" and cat != "inverter":
                continue
            if category == "bms" and cat != "battery":
                continue
        cls = _load_plugin_class(ptype)
        if cls is None:
            if include_unloadable:
                out.append({
                    "plugin_type": ptype,
                    "label": entry["label"],
                    "meta": {"status": "unavailable", "category": meta_cat},
                    "loadable": False,
                })
            continue
        meta = cls.get_plugin_meta()
        out.append({
            "plugin_type": ptype,
            "label": entry["label"],
            "meta": meta,
            "class": cls,
            "loadable": True,
        })
    return out


def default_instance_name(plugin_type: str, category: str) -> str:
    short = plugin_type.split(".")[-1].replace("_plugin", "").replace("_modbus", "")
    short = short.replace("_", "")
    prefix = "INV" if category == "inverter" else "BMS"
    return f"{prefix}_{short}"[:32]
