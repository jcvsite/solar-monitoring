# Firmware binaries for browser flashing

This folder is filled by:

```bash
# from esp32_display/
pio run
# Windows
powershell -File scripts/prepare_webflash.ps1
# Linux / macOS
./scripts/prepare_webflash.sh
```

Expected files:

- `bootloader.bin`
- `partitions.bin`
- `boot_app0.bin`
- `firmware.bin`

They are gitignored (large / build-specific). Publish them in GitHub Releases for end users.
