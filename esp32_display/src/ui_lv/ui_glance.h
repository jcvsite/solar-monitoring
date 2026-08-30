#pragma once
#include <lvgl.h>
#include "api_client.h"
#include "ui_shell.h"

struct UiGlanceWidgets {
  lv_obj_t* gridPill = nullptr;
  lv_obj_t* socLbl = nullptr;
  lv_obj_t* socSubLbl = nullptr;
  lv_obj_t* socBar = nullptr;
  lv_obj_t* battIcon = nullptr;
  lv_obj_t* battFill = nullptr;
  lv_obj_t* battNub = nullptr;
  lv_obj_t* battArrow = nullptr;
  lv_obj_t* battLbl = nullptr;
  lv_obj_t* pvVal = nullptr;
  lv_obj_t* loadVal = nullptr;
  lv_obj_t* gridVal = nullptr;
  lv_obj_t* todayPv = nullptr;
  lv_obj_t* todayLoad = nullptr;
  lv_obj_t* statusLbl = nullptr;
  lv_obj_t* tempLbl = nullptr;
  lv_obj_t* staleOverlay = nullptr;
  lv_obj_t* arc = nullptr;
  lv_obj_t* bars[3] = {nullptr, nullptr, nullptr};
  lv_obj_t* flowCol = nullptr;
};

void uiGlanceBuild(UiShellWidgets& shell, UiGlanceWidgets& g, uint8_t layoutId);
void uiGlanceUpdate(UiGlanceWidgets& g, const GlanceData& data, bool stale, bool gridAlert, uint8_t layoutId);
void uiGlancePulseGrid(UiGlanceWidgets& g, bool gridAlert, uint32_t animMs);
void uiGlanceAnimateBattery(UiGlanceWidgets& g, const GlanceData& data, uint32_t animMs);
void uiGlanceDestroy(UiGlanceWidgets& g);
bool uiGlanceNeedsBuild(const UiGlanceWidgets& g, uint8_t layoutId);
