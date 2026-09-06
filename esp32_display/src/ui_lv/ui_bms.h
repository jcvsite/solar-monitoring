#pragma once
#include <lvgl.h>
#include "api_client.h"
#include "ui_shell.h"

struct UiBmsWidgets {
  lv_obj_t* emptyLbl = nullptr;

  lv_obj_t* heroCard = nullptr;
  lv_obj_t* socLbl = nullptr;
  lv_obj_t* sohLbl = nullptr;
  lv_obj_t* statusLbl = nullptr;
  lv_obj_t* socBar = nullptr;

  lv_obj_t* metricsRow = nullptr;
  lv_obj_t* mVolts = nullptr;
  lv_obj_t* mAmps = nullptr;
  lv_obj_t* mWatts = nullptr;
  lv_obj_t* mTemp = nullptr;

  lv_obj_t* metaLbl = nullptr;

  lv_obj_t* cellTitle = nullptr;
  lv_obj_t* cellCard = nullptr;
  lv_obj_t* cellStrip = nullptr;

  static const int kMaxCells = 16;
  lv_obj_t* cellCol[kMaxCells] = {};
  lv_obj_t* cellMark[kMaxCells] = {};
  lv_obj_t* cellBar[kMaxCells] = {};
  lv_obj_t* cellLbl[kMaxCells] = {};
  lv_obj_t* cellIdx[kMaxCells] = {};
  size_t cellCount = 0;
};

void uiBmsBuild(UiShellWidgets& shell, UiBmsWidgets& b);
void uiBmsUpdate(UiBmsWidgets& b, const BmsData& data);
