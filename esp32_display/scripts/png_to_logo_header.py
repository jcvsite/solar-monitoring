#!/usr/bin/env python3
"""Convert static/icons/icon-192x192.png to ESP32 RGB565 PROGMEM header (unmodified pixels)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Install Pillow: pip install pillow", file=sys.stderr)
    sys.exit(1)


def rgb888_to_rgb565(r: int, g: int, b: int) -> int:
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def convert(png_path: Path, out_path: Path, size: int | None = None) -> None:
    img = Image.open(png_path).convert("RGB")
    if size is not None and (img.width != size or img.height != size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    w, h = img.size

    pixels: list[int] = []
    for y in range(h):
        for x in range(w):
            r, g, b = img.getpixel((x, y))
            pixels.append(rgb888_to_rgb565(r, g, b))

    var = "logo_solar_monitoring"
    lines = [
        "#pragma once",
        "#include <pgmspace.h>",
        "#include <stdint.h>",
        "",
        f"#define LOGO_SOLAR_MONITORING_W {w}",
        f"#define LOGO_SOLAR_MONITORING_H {h}",
        "",
        f"static const uint16_t {var}[] PROGMEM = {{",
    ]
    for i in range(0, len(pixels), 12):
        chunk = pixels[i : i + 12]
        lines.append("  " + ", ".join(f"0x{v:04X}" for v in chunk) + ",")
    lines.append("};")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path} ({w}x{h}, {len(pixels) * 2} bytes)")


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    default_png = root / "static" / "icons" / "icon-192x192.png"
    default_out = Path(__file__).resolve().parents[1] / "include" / "logo_solar_monitoring.h"

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--png", type=Path, default=default_png)
    p.add_argument("--out", type=Path, default=default_out)
    p.add_argument("--size", type=int, default=None, help="Optional square resize (e.g. 24 for small icons)")
    args = p.parse_args()

    if not args.png.is_file():
        print(f"Missing PNG: {args.png}", file=sys.stderr)
        sys.exit(1)
    convert(args.png, args.out, size=args.size)


if __name__ == "__main__":
    main()
