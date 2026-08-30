#pragma once
#include <lvgl.h>

// Copy logo from PROGMEM into RAM for LVGL (frees on uiLogoRelease).
bool uiLogoEnsureLoaded();
const lv_img_dsc_t* uiLogoDescriptor();
uint16_t uiLogoSplashZoom();
void uiLogoRelease();
