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
#ifndef TOUCH_SAMPLES
#define TOUCH_SAMPLES 5
#endif
#ifndef TOUCH_RELEASE_FRAMES
#define TOUCH_RELEASE_FRAMES 2
#endif

static SPIClass s_touchSpi(VSPI);
static XPT2046_Touchscreen s_touch(TOUCH_CS, TOUCH_IRQ_PIN);
static bool s_ready = false;
static uint8_t s_rotation = 0;

static bool s_latched = false;
static int16_t s_latchX = 0;
static int16_t s_latchY = 0;
static uint8_t s_missFrames = 0;

void touchInputSetRotation(uint8_t tftRotation) { s_rotation = tftRotation & 3; }

void touchInputReset() {
  s_latched = false;
  s_missFrames = 0;
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
    case 0: outX = px; outY = py; break;
    case 1: outX = py; outY = (int16_t)(239 - px); break;
    case 2: outX = (int16_t)(239 - px); outY = (int16_t)(319 - py); break;
    case 3: outX = (int16_t)(319 - py); outY = px; break;
    default: outX = px; outY = py; break;
  }
  outX = constrain(outX, 0, scrW(s_rotation) - 1);
  outY = constrain(outY, 0, scrH(s_rotation) - 1);
}

bool touchInputBegin() {
  if (s_ready) return true;
  s_touchSpi.begin(TOUCH_SPI_CLK, TOUCH_SPI_MISO, TOUCH_SPI_MOSI, TOUCH_CS);
  s_touchSpi.setFrequency(2500000);
  s_touch.begin(s_touchSpi);
  s_touch.setRotation(1);
  s_ready = true;
  touchInputReset();
  return true;
}

static bool rawSample(int& rx, int& ry, int& rz) {
  bool irq = s_touch.tirqTouched();
  bool pressed = s_touch.touched();
  if (!irq && !pressed) return false;
  TS_Point p = s_touch.getPoint();
  if (p.z < TOUCH_Z_MIN) return false;
  rx = p.x;
  ry = p.y;
  rz = p.z;
  return true;
}

static bool readPoint(TouchSample& out) {
  if (!s_ready) return false;

  long sumX = 0, sumY = 0, sumZ = 0;
  int n = 0;
  for (int i = 0; i < TOUCH_SAMPLES; i++) {
    int rx, ry, rz;
    if (!rawSample(rx, ry, rz)) continue;
    sumX += rx;
    sumY += ry;
    sumZ += rz;
    n++;
  }

  if (n >= 2) {
    const int rx = (int)(sumX / n);
    const int ry = (int)(sumY / n);
    const int rz = (int)(sumZ / n);
    out.rawX = rx;
    out.rawY = ry;
    out.rawZ = rz;
    mapTouchPoint(rx, ry, out.x, out.y);
    out.active = true;
    s_latched = true;
    s_latchX = out.x;
    s_latchY = out.y;
    s_missFrames = 0;
    return true;
  }

  if (s_latched && s_missFrames < TOUCH_RELEASE_FRAMES) {
    s_missFrames++;
    out.x = s_latchX;
    out.y = s_latchY;
    out.active = true;
    return true;
  }

  s_latched = false;
  s_missFrames = 0;
  return false;
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
