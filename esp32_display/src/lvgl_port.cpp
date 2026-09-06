#include "lvgl_port.h"
#include "touch_input.h"
#include "layout.h"

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

static TFT_eSPI* s_tft = nullptr;
static uint8_t s_rotation = 0;
static int16_t s_touchStartX = 0;
static int16_t s_touchStartY = 0;
static int16_t s_touchLastX = 0;
static int16_t s_touchLastY = 0;
static bool s_touchDown = false;
static uint32_t s_touchDownMs = 0;
static int s_pendingSwipe = 0;

static constexpr int kSwipeMinPx = 48;
static constexpr uint32_t kSwipeMaxMs = 450;

static constexpr int kBufMaxWidth = 320;
static constexpr int kBufLines = 30;

static lv_disp_draw_buf_t s_drawBuf;
static lv_color_t s_buf1[kBufMaxWidth * kBufLines];
static lv_disp_drv_t s_dispDrv;
static lv_indev_drv_t s_indevDrv;
static lv_indev_t* s_indev = nullptr;

static uint16_t* s_fb = nullptr;
static int s_fbW = 0;
static int s_fbH = 0;
static int s_fbScale = 1;  // 1=full, 2=half-res capture
static bool s_mirror = false;

static void flushCb(lv_disp_drv_t* drv, const lv_area_t* area, lv_color_t* color_p) {
  if (!s_tft) {
    lv_disp_flush_ready(drv);
    return;
  }
  const int32_t w = area->x2 - area->x1 + 1;
  const int32_t h = area->y2 - area->y1 + 1;

  if (s_mirror && s_fb && s_fbW > 0 && s_fbH > 0) {
    lv_color_t* src = color_p;
    const int scale = s_fbScale < 1 ? 1 : s_fbScale;
    for (int32_t y = area->y1; y <= area->y2; y++) {
      for (int32_t x = area->x1; x <= area->x2; x++, src++) {
        if ((x % scale) != 0 || (y % scale) != 0) continue;
        const int dx = x / scale;
        const int dy = y / scale;
        if (dx < 0 || dy < 0 || dx >= s_fbW || dy >= s_fbH) continue;
        s_fb[(size_t)dy * (size_t)s_fbW + (size_t)dx] = src->full;
      }
    }
  }

  s_tft->startWrite();
  s_tft->setAddrWindow(area->x1, area->y1, w, h);
  s_tft->pushColors(reinterpret_cast<uint16_t*>(color_p), (uint32_t)(w * h), false);
  s_tft->endWrite();
  lv_disp_flush_ready(drv);
}

static void touchReadCb(lv_indev_drv_t* drv, lv_indev_data_t* data) {
  (void)drv;
  int16_t x = 0;
  int16_t y = 0;
  if (touchInputRead(x, y)) {
    if (!s_touchDown) {
      s_touchStartX = x;
      s_touchStartY = y;
      s_touchDown = true;
      s_touchDownMs = millis();
    }
    s_touchLastX = x;
    s_touchLastY = y;
    data->state = LV_INDEV_STATE_PRESSED;
    data->point.x = x;
    data->point.y = y;
  } else {
    if (s_touchDown) {
      s_touchDown = false;
      const int dx = (int)s_touchLastX - (int)s_touchStartX;
      const int dy = (int)s_touchLastY - (int)s_touchStartY;
      const uint32_t held = millis() - s_touchDownMs;
      const int navTop = navY(s_rotation) - 4;
      if (s_touchStartY < navTop && held <= kSwipeMaxMs && abs(dx) >= kSwipeMinPx &&
          abs(dx) > abs(dy) * 2) {
        s_pendingSwipe = dx < 0 ? -1 : 1;
      }
    }
    data->state = LV_INDEV_STATE_RELEASED;
    data->point.x = s_touchLastX;
    data->point.y = s_touchLastY;
  }
}

int lvglPortConsumeSwipe() {
  const int swipe = s_pendingSwipe;
  s_pendingSwipe = 0;
  return swipe;
}

void lvglPortResetInput() {
  s_touchDown = false;
  s_pendingSwipe = 0;
  s_touchDownMs = 0;
  touchInputReset();
  if (s_indev) lv_indev_reset(s_indev, nullptr);
}

static void updateDispMetrics() {
  s_dispDrv.hor_res = (lv_coord_t)scrW(s_rotation);
  s_dispDrv.ver_res = (lv_coord_t)scrH(s_rotation);
}

void lvglPortInit(TFT_eSPI& tft, uint8_t rotation) {
  s_tft = &tft;
  s_rotation = rotation & 3;
  touchInputSetRotation(s_rotation);

  lv_init();
  lv_disp_draw_buf_init(&s_drawBuf, s_buf1, nullptr, kBufMaxWidth * kBufLines);

  lv_disp_drv_init(&s_dispDrv);
  updateDispMetrics();
  s_dispDrv.flush_cb = flushCb;
  s_dispDrv.draw_buf = &s_drawBuf;
  lv_disp_drv_register(&s_dispDrv);

  lv_indev_drv_init(&s_indevDrv);
  s_indevDrv.type = LV_INDEV_TYPE_POINTER;
  s_indevDrv.read_cb = touchReadCb;
  s_indev = lv_indev_drv_register(&s_indevDrv);
}

void lvglPortSetRotation(uint8_t rotation) {
  s_rotation = rotation & 3;
  touchInputSetRotation(s_rotation);
  updateDispMetrics();

  if (s_tft) s_tft->fillScreen(TFT_BLACK);

  lv_disp_t* disp = lv_disp_get_default();
  if (disp) lv_disp_drv_update(disp, &s_dispDrv);

  lvglPortResetInput();
  if (lv_scr_act()) {
    lv_obj_set_size(lv_scr_act(), s_dispDrv.hor_res, s_dispDrv.ver_res);
    lv_obj_invalidate(lv_scr_act());
  }
}

void lvglPortTick() {
  static uint32_t last = 0;
  const uint32_t now = millis();
  const uint32_t elapsed = now - last;
  if (elapsed >= 5) {
    lv_tick_inc(elapsed);
    last = now;
  }
  lv_timer_handler();
}

bool lvglPortCaptureFrame() {
  lv_disp_t* disp = lv_disp_get_default();
  if (!disp) return false;
  const int fullW = (int)s_dispDrv.hor_res;
  const int fullH = (int)s_dispDrv.ver_res;
  if (fullW <= 0 || fullH <= 0 || fullW > 320 || fullH > 320) return false;

  lvglPortFreeCapture();

  // Half-res by default (~38KB) so capture works with fragmented heap.
  // ?scale=1 query is handled in device_web by calling twice if needed — here always half.
  s_fbScale = 2;
  s_fbW = (fullW + 1) / 2;
  s_fbH = (fullH + 1) / 2;
  s_fb = (uint16_t*)malloc((size_t)s_fbW * (size_t)s_fbH * sizeof(uint16_t));
  if (!s_fb) {
    // Last resort: quarter-res
    s_fbScale = 4;
    s_fbW = (fullW + 3) / 4;
    s_fbH = (fullH + 3) / 4;
    s_fb = (uint16_t*)malloc((size_t)s_fbW * (size_t)s_fbH * sizeof(uint16_t));
    if (!s_fb) return false;
  }
  memset(s_fb, 0, (size_t)s_fbW * (size_t)s_fbH * sizeof(uint16_t));
  s_mirror = true;

  if (lv_scr_act()) lv_obj_invalidate(lv_scr_act());
  lv_refr_now(disp);
  if (lv_scr_act()) lv_obj_invalidate(lv_scr_act());
  lv_timer_handler();

  s_mirror = false;
  return true;
}

int lvglPortFbWidth() { return s_fbW; }
int lvglPortFbHeight() { return s_fbH; }
const uint16_t* lvglPortFb() { return s_fb; }
uint8_t lvglPortRotation() { return s_rotation; }

void lvglPortFreeCapture() {
  s_mirror = false;
  if (s_fb) {
    free(s_fb);
    s_fb = nullptr;
  }
  s_fbW = 0;
  s_fbH = 0;
  s_fbScale = 1;
}
