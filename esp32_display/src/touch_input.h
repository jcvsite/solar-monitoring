#pragma once
#include <stdint.h>

class TFT_eSPI;

struct TouchSample {
  bool active = false;
  int16_t x = 0;
  int16_t y = 0;
  int rawX = 0;
  int rawY = 0;
  int rawZ = 0;
};

bool touchInputBegin();
void touchInputSetRotation(uint8_t tftRotation);
bool touchInputRead(int16_t& x, int16_t& y);
bool touchInputSample(TouchSample& out);
void touchInputShowTap(TFT_eSPI& tft, int16_t x, int16_t y);
