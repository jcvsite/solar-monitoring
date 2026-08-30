#!/usr/bin/env bash
# Copy PlatformIO build outputs into webflash/firmware for ESP Web Tools.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/.pio/build/cyd_esp32"
OUT="$ROOT/webflash/firmware"

if [[ ! -f "$BUILD/firmware.bin" ]]; then
  echo "No build found. Run: pio run"
  exit 1
fi

mkdir -p "$OUT"
cp -f "$BUILD/bootloader.bin" "$OUT/bootloader.bin"
cp -f "$BUILD/partitions.bin" "$OUT/partitions.bin"
cp -f "$BUILD/firmware.bin" "$OUT/firmware.bin"

BOOT_APP="$(find "$ROOT/.pio/packages" -name boot_app0.bin 2>/dev/null | head -n 1 || true)"
if [[ -z "$BOOT_APP" ]]; then
  echo "boot_app0.bin not found under .pio/packages — run pio run once."
  exit 1
fi
cp -f "$BOOT_APP" "$OUT/boot_app0.bin"

echo "Web flash ready. Serve and open in Chrome/Edge:"
echo "  python -m http.server 8765 --directory webflash"
echo "  http://localhost:8765"
