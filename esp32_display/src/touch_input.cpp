#include "touch_input.h"
#include "config.h"
#include "layout.h"

#include <SPI.h>
#include <TFT_eSPI.h>
#include <XPT2046_Touchscreen.h>

#ifndef TOUCH_CS
#define TOUCH_CS 33
#endif

#ifndef TOUCH_IRQ_PIN
#define TOUCH_IRQ_PIN 36
#endif

static SPIClass s_touchSpi(VSPI);
static XPT2046_Touchscreen s_touch(TOUCH_CS, TOUCH_IRQ_PIN);
static bool s_ready = false;
static uint8_t s_rotation = 0;

void touchInputSetRotation(uint8_t tftRotation) {
  s_rotation = tftRotation & 3;
}

static void mapTouchPoint(int rawX, int rawY, int16_t& outX, int16_t& outY) {
  int32_t sx = map(rawY, TOUCH_MAP_Y1, TOUCH_MAP_Y2, 0, 239);
  int32_t sy = map(rawX, TOUCH_MAP_X1, TOUCH_MAP_X2, 0, 319);
#if TOUCH_MIRROR_X
  sx = 239 - sx;
#endif
#if TOUCH_MIRROR_Y
  sy = 319 - sy;
#endif
#if TOUCH_SWAP_XY
  outX = (int16_t)sy;
  outY = (int16_t)sx;
#else
  outX = (int16_t)sx;
  outY = (int16_t)sy;
#endif
  outX = constrain(outX, 0, 239);
  outY = constrain(outY, 0, 319);

  int16_t px = outX;
  int16_t py = outY;
  switch (s_rotation) {
    case 0:
      outX = px;
      outY = py;
      break;
    case 1:
      outX = py;
      outY = (int16_t)(239 - px);
      break;
    case 2:
      outX = (int16_t)(239 - px);
      outY = (int16_t)(319 - py);
      break;
    case 3:
      outX = (int16_t)(319 - py);
      outY = px;
      break;
    default:
      outX = px;
      outY = py;
      break;
  }
  outX = constrain(outX, 0, scrW(s_rotation) - 1);
  outY = constrain(outY, 0, scrH(s_rotation) - 1);
}

bool touchInputBegin() {
  if (s_ready) return true;
  s_touchSpi.begin(TOUCH_SPI_CLK, TOUCH_SPI_MISO, TOUCH_SPI_MOSI, TOUCH_CS);
  s_touch.begin(s_touchSpi);
  s_touch.setRotation(1);
  s_ready = true;
  return true;
}

static bool readPoint(TouchSample& out) {
  if (!s_ready) return false;

  bool irq = s_touch.tirqTouched();
  bool pressed = s_touch.touched();
  TS_Point p = s_touch.getPoint();

  if (!irq && !pressed && p.z < TOUCH_Z_MIN) return false;
  if (p.z < TOUCH_Z_MIN) return false;

  out.rawX = p.x;
  out.rawY = p.y;
  out.rawZ = p.z;
  mapTouchPoint(p.x, p.y, out.x, out.y);
  out.active = true;
  return true;
}

bool touchInputSample(TouchSample& out) {
  out = TouchSample();
  return readPoint(out);
}

bool touchInputRead(int16_t& x, int16_t& y) {
  TouchSample s;
  if (!readPoint(s)) return false;
  x = s.x;
  y = s.y;
  return true;
}

void touchInputShowTap(TFT_eSPI& tft, int16_t x, int16_t y) {
  tft.drawCircle(x, y, 10, TFT_YELLOW);
  tft.drawLine(x - 14, y, x + 14, y, TFT_YELLOW);
  tft.drawLine(x, y - 14, x, y + 14, TFT_YELLOW);
  tft.fillCircle(x, y, 3, TFT_WHITE);
}
