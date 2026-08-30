#pragma once
#include <lvgl.h>
#include <vector>
#include <Arduino.h>
#include "wifi_setup.h"

struct UiWifiWidgets {
  lv_obj_t* screen = nullptr;
  lv_obj_t* list = nullptr;
  lv_obj_t* statusLbl = nullptr;
  lv_obj_t* passScreen = nullptr;
  lv_obj_t* ta = nullptr;
  lv_obj_t* kb = nullptr;
};

void uiWifiBuildList(UiWifiWidgets& w, const std::vector<WifiNetwork>& nets, int selected, const String& status);
void uiWifiBuildPassword(UiWifiWidgets& w, const String& ssid, const String& password, bool showPass,
                         const String& status);
void uiWifiBuildPortal(UiWifiWidgets& w, const char* apName);
void uiWifiDestroy(UiWifiWidgets& w);
