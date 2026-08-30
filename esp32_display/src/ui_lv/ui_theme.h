#pragma once
#include <lvgl.h>
#include <stdint.h>
#include "theme.h"

lv_color_t uiColor565(uint16_t c);
void uiThemeApply(uint8_t themeId);
void uiThemeRefreshStyles();
const lv_font_t* uiFontBody();
const lv_font_t* uiFontTitle();
const lv_font_t* uiFontDisplay();
const lv_font_t* uiFontSoc();

extern lv_style_t uiStyleScreen;
extern lv_style_t uiStyleCard;
extern lv_style_t uiStyleHeader;
extern lv_style_t uiStyleMuted;
extern lv_style_t uiStyleNavBtn;
extern lv_style_t uiStyleNavBtnActive;
extern lv_style_t uiStyleAccent;

lv_color_t uiSocColor(float soc);
void uiThemeInitOnce();
