#pragma once
#include <lvgl.h>
#include <Arduino.h>
#include "../ui.h"
#include "settings_store.h"
#include "ui_shell.h"

struct UiSettingsWidgets {
  lv_obj_t* tabs = nullptr;
  lv_obj_t* connPanel = nullptr;
  lv_obj_t* updPanel = nullptr;
};

void uiSettingsBuild(UiShellWidgets& shell, UiSettingsWidgets& s, UiSettingsTab tab, const HostSettings& cfg,
                     bool wifiOk, const String& wifiSsid, const String& statusMsg, const String& otaStatus,
                     const char* fwVersion);
void uiSettingsSetTab(UiSettingsWidgets& s, UiSettingsTab tab);
