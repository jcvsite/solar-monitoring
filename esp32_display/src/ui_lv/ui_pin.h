#pragma once
#include <lvgl.h>
#include <Arduino.h>

struct UiPinWidgets {
  lv_obj_t* screen = nullptr;
  lv_obj_t* entryLbl = nullptr;
  lv_obj_t* statusLbl = nullptr;
};

void uiPinBuild(UiPinWidgets& p, const char* title, const String& entry, const String& subtitle,
                const String& status);
void uiPinUpdate(UiPinWidgets& p, const String& entry, const String& status);
void uiPinDestroy(UiPinWidgets& p);
