# Copy PlatformIO build outputs into webflash/firmware for ESP Web Tools.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Build = Join-Path $Root ".pio\build\cyd_esp32"
$Out = Join-Path $Root "webflash\firmware"

if (-not (Test-Path (Join-Path $Build "firmware.bin"))) {
  Write-Host "No build found. Run from esp32_display:  pio run" -ForegroundColor Yellow
  exit 1
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null

$files = @(
  @{ Src = "bootloader.bin"; Dst = "bootloader.bin" },
  @{ Src = "partitions.bin"; Dst = "partitions.bin" },
  @{ Src = "firmware.bin"; Dst = "firmware.bin" }
)

foreach ($f in $files) {
  $src = Join-Path $Build $f.Src
  if (-not (Test-Path $src)) { throw "Missing $src" }
  Copy-Item -Force $src (Join-Path $Out $f.Dst)
  Write-Host "Copied $($f.Dst)"
}

# boot_app0 comes from the Arduino-ESP32 framework package
$bootApp = Get-ChildItem -Path (Join-Path $Root ".pio\packages") -Recurse -Filter "boot_app0.bin" -ErrorAction SilentlyContinue |
  Select-Object -First 1
if (-not $bootApp) {
  throw "boot_app0.bin not found under .pio/packages - run pio run once."
}
Copy-Item -Force $bootApp.FullName (Join-Path $Out "boot_app0.bin")
Write-Host "Copied boot_app0.bin from $($bootApp.FullName)"

Write-Host ""
Write-Host "Web flash ready. Serve and open in Chrome/Edge:" -ForegroundColor Green
Write-Host "  python -m http.server 8765 --directory webflash"
Write-Host "  http://localhost:8765"
