#pragma once
#include <stdint.h>
#include "config.h"

inline int scrW(uint8_t rotation) {
  return (rotation & 1) ? 320 : 240;
}

inline int scrH(uint8_t rotation) {
  return (rotation & 1) ? 240 : 320;
}

inline bool isLandscape(uint8_t rotation) { return (rotation & 1) != 0; }

inline int navY(uint8_t rotation) { return scrH(rotation) - UI_NAV_H; }

inline int contentH(uint8_t rotation) { return navY(rotation) - 22; }

inline int contentW(uint8_t rotation) { return scrW(rotation); }
