#pragma once
// Runtime defaults (overridable via Settings / NVS).

#ifndef DEFAULT_HOST_PORT
#define DEFAULT_HOST_PORT 8081
#endif

#ifndef DEFAULT_HOST_IP
#define DEFAULT_HOST_IP "192.168.1.240"
#endif

#ifndef DEFAULT_POLL_MS
#define DEFAULT_POLL_MS 5000
#endif

#ifndef DEFAULT_API_TOKEN
#define DEFAULT_API_TOKEN ""
#endif

#ifndef STALE_MS
#define STALE_MS 30000
#endif

// CYD XPT2046 pins (https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display/blob/main/PINS.md)
#ifndef TOUCH_CS
#define TOUCH_CS 33
#endif

#ifndef TOUCH_IRQ_PIN
#define TOUCH_IRQ_PIN 36
#endif

#ifndef TOUCH_SPI_CLK
#define TOUCH_SPI_CLK 25
#endif

#ifndef TOUCH_SPI_MISO
#define TOUCH_SPI_MISO 39
#endif

#ifndef TOUCH_SPI_MOSI
#define TOUCH_SPI_MOSI 32
#endif

#ifndef TOUCH_Z_MIN
#define TOUCH_Z_MIN 150
#endif

// Portrait TFT rotation 0 — calibration from billism1 esp32-2432S028R examples
#ifndef TOUCH_MAP_X1
#define TOUCH_MAP_X1 280
#define TOUCH_MAP_X2 3750
#define TOUCH_MAP_Y1 280
#define TOUCH_MAP_Y2 3750
#endif

// Portrait mapping: screen X ← rawY, screen Y ← rawX (no swap flag needed)
#ifndef TOUCH_SWAP_XY
#define TOUCH_SWAP_XY 0
#endif

// User reported both axes reversed with MIRROR_X=1/MIRROR_Y=0 + swap.
// Fix: invert screen X (rawY axis), leave screen Y (rawX axis) direct.
#ifndef TOUCH_MIRROR_X
#define TOUCH_MIRROR_X 1
#endif

#ifndef TOUCH_MIRROR_Y
#define TOUCH_MIRROR_Y 0
#endif

#ifndef TOUCH_SHOW_DEBUG
#define TOUCH_SHOW_DEBUG 0
#endif

// Bottom navigation bar (height only; Y position via layout.h navY())
#define UI_NAV_H 27

// Local time offset from UTC (seconds). Overridden by solar-monitoring host when available.
#ifndef TIMEZONE_OFFSET_SEC
#define TIMEZONE_OFFSET_SEC 0
#endif
