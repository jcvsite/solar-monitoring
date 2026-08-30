#include "ui_logo.h"
#include "logo_solar_monitoring.h"
#include <Arduino.h>
#include <string.h>

static uint16_t* s_logoRam = nullptr;
static lv_img_dsc_t s_logoDsc;

bool uiLogoEnsureLoaded() {
  if (s_logoRam) return true;
  const size_t bytes = (size_t)LOGO_SOLAR_MONITORING_W * LOGO_SOLAR_MONITORING_H * sizeof(uint16_t);
  s_logoRam = (uint16_t*)malloc(bytes);
  if (!s_logoRam) return false;
  const size_t count = (size_t)LOGO_SOLAR_MONITORING_W * LOGO_SOLAR_MONITORING_H;
  for (size_t i = 0; i < count; i++) {
    uint16_t pix = pgm_read_word(&logo_solar_monitoring[i]);
    s_logoRam[i] = (uint16_t)((pix << 8) | (pix >> 8));
  }
  s_logoDsc.header.cf = LV_IMG_CF_TRUE_COLOR;
  s_logoDsc.header.always_zero = 0;
  s_logoDsc.header.reserved = 0;
  s_logoDsc.header.w = LOGO_SOLAR_MONITORING_W;
  s_logoDsc.header.h = LOGO_SOLAR_MONITORING_H;
  s_logoDsc.data_size = (uint32_t)bytes;
  s_logoDsc.data = (const uint8_t*)s_logoRam;
  return true;
}

const lv_img_dsc_t* uiLogoDescriptor() {
  return s_logoRam ? &s_logoDsc : nullptr;
}

uint16_t uiLogoSplashZoom() {
  const lv_coord_t textReserve = 76;
  const lv_coord_t maxLogoH = LV_VER_RES - 8 - textReserve;
  if (maxLogoH >= LOGO_SOLAR_MONITORING_H) return 256;
  if (maxLogoH < 48) return (uint16_t)((48 * 256) / LOGO_SOLAR_MONITORING_H);
  return (uint16_t)((maxLogoH * 256) / LOGO_SOLAR_MONITORING_H);
}

void uiLogoRelease() {
  if (s_logoRam) {
    free(s_logoRam);
    s_logoRam = nullptr;
  }
}
