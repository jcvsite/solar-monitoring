#pragma once
#include <lvgl.h>
#include "api_client.h"
#include "ui_shell.h"

struct UiHistoryWidgets {
  lv_obj_t* emptyLbl = nullptr;
  lv_obj_t* legend = nullptr;
  lv_obj_t* chart = nullptr;
  lv_chart_series_t* serPv = nullptr;
  lv_chart_series_t* serLoad = nullptr;
  lv_chart_series_t* serSoc = nullptr;
  lv_obj_t* statsCard = nullptr;
  lv_obj_t* statVal[6] = {};
};

void uiHistoryBuild(UiShellWidgets& shell, UiHistoryWidgets& h);
void uiHistoryUpdate(UiHistoryWidgets& h, const HistoryData& data);
