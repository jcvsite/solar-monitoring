#pragma once
#include <stdint.h>
#include "theme.h"

/** Cell voltage colors matching console dashboard thresholds (curses_service). */
inline uint16_t cellVoltageColor(float v) {
  const ThemePalette& t = themeActive();
  if (v >= 3.65f) return t.cellCritHigh;
  if (v >= 3.55f) return t.cellHighWarn;
  if (v >= 3.15f) return t.cellNormal;
  if (v >= 2.80f) return t.cellLowWarn;
  return t.cellCritLow;
}
