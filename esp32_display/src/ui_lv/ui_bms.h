#pragma once
#include <lvgl.h>
#include "api_client.h"
#include "ui_shell.h"

struct UiBmsWidgets {
  lv_obj_t* emptyLbl = nullptr;
  lv_obj_t* statsCard = nullptr;
  lv_obj_t* statGrid = nullptr;
  lv_obj_t* cellTitle = nullptr;
  lv_obj_t* cellStrip = nullptr;
  static const int kMaxCells = 16;
  lv_obj_t* cellCol[kMaxCells] = {};
  lv_obj_t* cellMark[kMaxCells] = {};
  lv_obj_t* cellBar[kMaxCells] = {};
  lv_obj_t* cellLbl[kMaxCells] = {};
  size_t cellCount = 0;
};

void uiBmsBuild(UiShellWidgets& shell, UiBmsWidgets& b);
void uiBmsUpdate(UiBmsWidgets& b, const BmsData& data);
