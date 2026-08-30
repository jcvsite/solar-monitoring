#include "lvgl_port.h"
#include "touch_input.h"
#include "layout.h"

#include <Arduino.h>

static TFT_eSPI* s_tft = nullptr;
static uint8_t s_rotation = 0;

// Buffer line width must be >= max hor_res (320 in landscape).
static constexpr int kBufMaxWidth = 320;
static constexpr int kBufLines = 30;

static lv_disp_draw_buf_t s_drawBuf;
static lv_color_t s_buf1[kBufMaxWidth * kBufLines];
static lv_disp_drv_t s_dispDrv;
static lv_indev_drv_t s_indevDrv;

static void flushCb(lv_disp_drv_t* drv, const lv_area_t* area, lv_color_t* color_p) {
  if (!s_tft) {
    lv_disp_flush_ready(drv);
    return;
  }
  const int32_t w = area->x2 - area->x1 + 1;
  const int32_t h = area->y2 - area->y1 + 1;
  s_tft->startWrite();
  s_tft->setAddrWindow(area->x1, area->y1, w, h);
  // LV_COLOR_16_SWAP=1 already emits swapped bytes for the panel.
  s_tft->pushColors(reinterpret_cast<uint16_t*>(color_p), (uint32_t)(w * h), false);
  s_tft->endWrite();
  lv_disp_flush_ready(drv);
}

static void touchReadCb(lv_indev_drv_t* drv, lv_indev_data_t* data) {
  (void)drv;
  int16_t x = 0;
  int16_t y = 0;
  if (touchInputRead(x, y)) {
    data->state = LV_INDEV_STATE_PRESSED;
    data->point.x = x;
    data->point.y = y;
  } else {
    data->state = LV_INDEV_STATE_RELEASED;
  }
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
  lv_indev_drv_register(&s_indevDrv);
}

void lvglPortSetRotation(uint8_t rotation) {
  s_rotation = rotation & 3;
  touchInputSetRotation(s_rotation);
  updateDispMetrics();
  if (lv_scr_act()) lv_obj_invalidate(lv_scr_act());
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
