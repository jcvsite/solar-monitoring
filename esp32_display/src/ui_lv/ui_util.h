#pragma once
#include <Arduino.h>
#include <lvgl.h>

String uiFmtPower(float w);
String uiFmtKwh(float k);
String uiFmtTemp(float c, char unit);
String uiTruncate(const String& s, size_t maxLen);

lv_obj_t* uiMakeCard(lv_obj_t* parent, lv_coord_t w, lv_coord_t h);
lv_obj_t* uiMakeLabel(lv_obj_t* parent, const char* text, const lv_font_t* font, lv_color_t color);
void uiSetLabelText(lv_obj_t* label, const char* text);
void uiSetLabelText(lv_obj_t* label, const String& text);
