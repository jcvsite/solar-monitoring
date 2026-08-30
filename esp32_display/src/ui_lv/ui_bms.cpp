#include "ui_bms.h"
#include "cell_colors.h"
#include "ui_theme.h"
#include "ui_util.h"
#include "config.h"
#include <stdio.h>

static const lv_font_t* kCellFont = &lv_font_montserrat_14;

static lv_coord_t shellContentW(const UiShellWidgets& shell) {
  const lv_coord_t w = lv_obj_get_width(shell.root);
  return w > 0 ? w - 8 : 300;
}

static lv_coord_t shellContentH(const UiShellWidgets& shell) {
  const lv_coord_t h = lv_obj_get_height(shell.root);
  return h > 0 ? h - 24 - UI_NAV_H - 8 : 180;
}

static lv_obj_t* addStatRow(lv_obj_t* grid, const char* left, const char* right) {
  const ThemePalette& t = themeActive();
  lv_obj_t* row = lv_obj_create(grid);
  lv_obj_remove_style_all(row);
  lv_obj_set_size(row, LV_PCT(100), 16);
  lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(row, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  uiMakeLabel(row, left, uiFontBody(), uiColor565(t.muted));
  uiMakeLabel(row, right, uiFontBody(), uiColor565(t.text));
  return row;
}

void uiBmsBuild(UiShellWidgets& shell, UiBmsWidgets& b) {
  uiShellClearContent(shell);
  b = UiBmsWidgets();
  const ThemePalette& t = themeActive();
  const lv_coord_t sw = shellContentW(shell);

  lv_obj_set_flex_flow(shell.content, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(shell.content, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START);
  lv_obj_set_style_pad_row(shell.content, 4, 0);

  b.emptyLbl = uiMakeLabel(shell.content, "No BMS data", uiFontTitle(), uiColor565(t.muted));
  lv_obj_add_flag(b.emptyLbl, LV_OBJ_FLAG_HIDDEN);

  b.statsCard = uiMakeCard(shell.content, sw, 72);
  lv_obj_set_flex_flow(b.statsCard, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_style_pad_all(b.statsCard, 4, 0);
  b.statGrid = lv_obj_create(b.statsCard);
  lv_obj_remove_style_all(b.statGrid);
  lv_obj_set_size(b.statGrid, sw - 12, 64);
  lv_obj_set_flex_flow(b.statGrid, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_style_pad_row(b.statGrid, 1, 0);

  b.cellTitle = uiMakeLabel(shell.content, LV_SYMBOL_BARS " Cell voltages", uiFontBody(), uiColor565(t.charge));
  b.cellStrip = lv_obj_create(shell.content);
  lv_obj_remove_style_all(b.cellStrip);
  lv_obj_set_width(b.cellStrip, sw);
  lv_obj_set_flex_grow(b.cellStrip, 1);
  lv_obj_set_height(b.cellStrip, shellContentH(shell) - 100);
  lv_obj_set_style_min_height(b.cellStrip, 80, 0);
  lv_obj_set_flex_flow(b.cellStrip, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(b.cellStrip, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END);
  lv_obj_set_style_pad_row(b.cellStrip, 4, 0);
  lv_obj_set_style_pad_column(b.cellStrip, 3, 0);
  lv_obj_clear_flag(b.cellStrip, LV_OBJ_FLAG_SCROLLABLE);
}

static void layoutCell(UiBmsWidgets& b, size_t idx, lv_coord_t cw, lv_coord_t barH) {
  if (idx >= UiBmsWidgets::kMaxCells || !b.cellCol[idx]) return;
  lv_obj_set_size(b.cellCol[idx], cw, barH + 14);
  lv_obj_set_width(b.cellBar[idx], cw - 2);
  lv_obj_set_width(b.cellMark[idx], cw);
}

static void ensureCell(UiBmsWidgets& b, size_t idx, lv_coord_t cw, lv_coord_t barH) {
  if (idx >= UiBmsWidgets::kMaxCells) return;
  if (!b.cellCol[idx]) {
    lv_obj_t* col = lv_obj_create(b.cellStrip);
    lv_obj_remove_style_all(col);
    lv_obj_clear_flag(col, LV_OBJ_FLAG_SCROLLABLE);

    b.cellMark[idx] = uiMakeLabel(col, "", uiFontBody(), uiColor565(themeActive().warn));
    lv_obj_set_style_text_align(b.cellMark[idx], LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(b.cellMark[idx], LV_ALIGN_TOP_MID, 0, 0);

    b.cellBar[idx] = lv_obj_create(col);
    lv_obj_remove_style_all(b.cellBar[idx]);
    lv_obj_set_style_radius(b.cellBar[idx], 3, 0);
    lv_obj_clear_flag(b.cellBar[idx], LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_align(b.cellBar[idx], LV_ALIGN_BOTTOM_MID, 0, 0);

    b.cellLbl[idx] = uiMakeLabel(b.cellBar[idx], "--", kCellFont, lv_color_white());
    lv_obj_set_style_text_align(b.cellLbl[idx], LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_center(b.cellLbl[idx]);

    b.cellCol[idx] = col;
    if (idx + 1 > b.cellCount) b.cellCount = idx + 1;
  }
  layoutCell(b, idx, cw, barH);
}

void uiBmsUpdate(UiBmsWidgets& b, const BmsData& data) {
  if (!b.statsCard) return;

  if (!data.ok) {
    lv_obj_add_flag(b.statsCard, LV_OBJ_FLAG_HIDDEN);
    if (b.cellTitle) lv_obj_add_flag(b.cellTitle, LV_OBJ_FLAG_HIDDEN);
    if (b.cellStrip) lv_obj_add_flag(b.cellStrip, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(b.emptyLbl, LV_OBJ_FLAG_HIDDEN);
    return;
  }
  lv_obj_add_flag(b.emptyLbl, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(b.statsCard, LV_OBJ_FLAG_HIDDEN);
  if (b.cellTitle) lv_obj_clear_flag(b.cellTitle, LV_OBJ_FLAG_HIDDEN);
  if (b.cellStrip) lv_obj_clear_flag(b.cellStrip, LV_OBJ_FLAG_HIDDEN);

  lv_obj_clean(b.statGrid);
  char buf[48];
  char b2[48];
  snprintf(buf, sizeof(buf), "SOC %.0f%%", isnan(data.soc) ? 0.0f : data.soc);
  snprintf(b2, sizeof(b2), "SOH %.0f%%", isnan(data.soh) ? 0.0f : data.soh);
  addStatRow(b.statGrid, buf, b2);
  snprintf(buf, sizeof(buf), "V %.1f", isnan(data.volts) ? 0.0f : data.volts);
  snprintf(b2, sizeof(b2), "P %.0f W", isnan(data.watts) ? 0.0f : data.watts);
  addStatRow(b.statGrid, buf, b2);
  snprintf(buf, sizeof(buf), "T %.0f C", isnan(data.temp_avg) ? 0.0f : data.temp_avg);
  snprintf(b2, sizeof(b2), "d %.0f mV", isnan(data.cell_delta_v) ? 0.0f : data.cell_delta_v * 1000.0f);
  addStatRow(b.statGrid, buf, b2);
  snprintf(buf, sizeof(buf), "Cyc %.0f", isnan(data.cycles) ? 0.0f : data.cycles);
  snprintf(b2, sizeof(b2), "Cells %d", data.cell_count);
  addStatRow(b.statGrid, buf, b2);

  if (!b.cellStrip) return;

  lv_obj_update_layout(b.cellStrip);
  const lv_coord_t stripH = lv_obj_get_height(b.cellStrip);
  const lv_coord_t stripW = lv_obj_get_width(b.cellStrip);
  if (stripH < 20 || stripW < 20) return;

  size_t n = data.cells.size();
  if (n == 0 && data.cell_count > 0) {
    uiSetLabelText(b.cellTitle, LV_SYMBOL_BARS " Cell voltages (no data from host)");
    return;
  }
  if (n > UiBmsWidgets::kMaxCells) n = UiBmsWidgets::kMaxCells;
  if (n == 0) {
    for (size_t i = 0; i < b.cellCount; i++) {
      if (b.cellCol[i]) lv_obj_add_flag(b.cellCol[i], LV_OBJ_FLAG_HIDDEN);
    }
    return;
  }

  uiSetLabelText(b.cellTitle, LV_SYMBOL_BARS " Cell voltages");

  const int cols = n > 8 ? 8 : (int)n;
  const int rows = (int)((n + cols - 1) / cols);
  const lv_coord_t cw = (stripW - (cols - 1) * 3) / cols;
  const lv_coord_t barH = (stripH - rows * 28) / rows;
  const lv_coord_t useBarH = barH > 20 ? barH : 20;

  float vmin = data.cell_min_v;
  float vmax = data.cell_max_v;
  if (isnan(vmin) || isnan(vmax) || vmax <= vmin) {
    vmin = 3.0f;
    vmax = 3.5f;
    for (size_t i = 0; i < n; i++) {
      vmin = min(vmin, data.cells[i]);
      vmax = max(vmax, data.cells[i]);
    }
    if (vmax <= vmin) {
      vmin = 3.0f;
      vmax = 3.5f;
    }
  }
  const float span = vmax - vmin;

  size_t minIdx = 0;
  size_t maxIdx = 0;
  for (size_t i = 1; i < n; i++) {
    if (data.cells[i] < data.cells[minIdx]) minIdx = i;
    if (data.cells[i] > data.cells[maxIdx]) maxIdx = i;
  }

  for (size_t i = 0; i < n; i++) {
    ensureCell(b, i, cw, useBarH);
    lv_obj_clear_flag(b.cellCol[i], LV_OBJ_FLAG_HIDDEN);
    const float v = data.cells[i];
    const float norm = constrain((v - vmin) / span, 0.15f, 1.0f);
    const bool compact = cw < 20;
    const lv_coord_t h = (lv_coord_t)max((float)useBarH * norm, 20.0f);
    lv_obj_set_size(b.cellBar[i], cw - 2, h);
    lv_obj_set_style_bg_color(b.cellBar[i], uiColor565(cellVoltageColor(v)), 0);
    lv_obj_set_style_bg_opa(b.cellBar[i], LV_OPA_COVER, 0);
    lv_obj_align(b.cellBar[i], LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_text_font(b.cellLbl[i], kCellFont, 0);
    snprintf(buf, sizeof(buf), compact ? "%.1f" : "%.2f", v);
    uiSetLabelText(b.cellLbl[i], buf);
    lv_obj_center(b.cellLbl[i]);
    if (b.cellMark[i]) {
      if (i == minIdx && i == maxIdx) uiSetLabelText(b.cellMark[i], "-");
      else if (i == minIdx) uiSetLabelText(b.cellMark[i], "v");
      else if (i == maxIdx) uiSetLabelText(b.cellMark[i], "^");
      else uiSetLabelText(b.cellMark[i], "");
    }
  }
  for (size_t i = n; i < b.cellCount; i++) {
    if (b.cellCol[i]) lv_obj_add_flag(b.cellCol[i], LV_OBJ_FLAG_HIDDEN);
  }
}
