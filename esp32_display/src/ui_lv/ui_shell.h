#pragma once
#include <lvgl.h>
#include <stdint.h>
#include "../ui.h"
#include "api_client.h"

struct UiShellWidgets {
  lv_obj_t* root = nullptr;
  lv_obj_t* header = nullptr;
  lv_obj_t* titleLbl = nullptr;
  lv_obj_t* rightLbl = nullptr;
  lv_obj_t* weatherDot = nullptr;
  lv_obj_t* alertDot = nullptr;
  lv_obj_t* content = nullptr;
  lv_obj_t* nav = nullptr;
  lv_obj_t* navBtns[4] = {nullptr, nullptr, nullptr, nullptr};
  lv_obj_t* navDots[4] = {nullptr, nullptr, nullptr, nullptr};
};

int uiShellNavIndex(UiPage page);
void uiShellCreate(UiShellWidgets& w, UiPage page, bool showNav, uint8_t rotation);
void uiShellDestroy(UiShellWidgets& w);
void uiShellSetPage(UiShellWidgets& w, UiPage page);
void uiShellSetHeader(UiShellWidgets& w, const String& left, const String& right);
void uiShellSetGlanceHeader(UiShellWidgets& w, const GlanceData& g);
void uiShellClearContent(UiShellWidgets& w);

void uiClockEnsure();
void uiClockSyncTimezone(int offsetSec);
String uiClockHeaderRight(const GlanceData& g);
