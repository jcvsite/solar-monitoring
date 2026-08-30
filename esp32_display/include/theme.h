#pragma once
#include <stdint.h>

struct ThemePalette {
  uint16_t bg;
  uint16_t card;
  uint16_t panel;
  uint16_t header;
  uint16_t line;
  uint16_t text;
  uint16_t muted;
  uint16_t dim;
  uint16_t pv;
  uint16_t charge;
  uint16_t disch;
  uint16_t grid;
  uint16_t danger;
  uint16_t warn;
  uint16_t ok;
  uint16_t onAccent;
  uint16_t gridImport;
  uint16_t gridExport;
  uint16_t cellNormal;
  uint16_t cellLowWarn;
  uint16_t cellHighWarn;
  uint16_t cellCritLow;
  uint16_t cellCritHigh;
};

void themeSetActive(uint8_t id);
const ThemePalette& themeActive();
const char* themeName(uint8_t id);
