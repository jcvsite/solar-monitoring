#include "ui_bms.h"
#include "cell_colors.h"
#include "ui_theme.h"
#include "ui_util.h"
#include "config.h"
#include <stdio.h>
#include <math.h>
#include <string.h>

static const lv_font_t* kCellFont = &lv_font_montserrat_14;

static lv_coord_t shellContentW(const UiShellWidgets& shell) {
  const lv_coord_t w = lv_obj_get_width(shell.content);
  if (w > 8) return w - 4;
  const lv_coord_t rw = lv_obj_get_width(shell.root);
  return rw > 0 ? rw - 8 : 300;
}

static lv_color_t statusColor(const String& status) {
  const ThemePalette& t = themeActive();
  String s = status;
  s.toLowerCase();
  if (s.indexOf("alarm") >= 0 || s.indexOf("fault") >= 0 || s.indexOf("error") >= 0) return uiColor565(t.danger);
  if (s.indexOf("discharg") >= 0) return uiColor565(t.warn);
  if (s.indexOf("charg") >= 0 || s.indexOf("float") >= 0) return uiColor565(t.charge);
  return uiColor565(t.muted);
}

static lv_obj_t* makeMetricChip(lv_obj_t* parent, lv_coord_t w, lv_coord_t h, const char* caption,
                                lv_obj_t** valOut, lv_color_t accent) {
  const ThemePalette& t = themeActive();
  lv_obj_t* card = uiMakeCard(parent, w, h);
  lv_obj_set_style_pad_all(card, 3, 0);
  lv_obj_set_style_pad_row(card, 0, 0);
  lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(card, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_border_width(card, 1, 0);
  lv_obj_set_style_border_color(card, accent, 0);
  lv_obj_set_style_border_opa(card, LV_OPA_40, 0);
  uiMakeLabel(card, caption, uiFontBody(), uiColor565(t.muted));
  *valOut = uiMakeLabel(card, "--", uiFontTitle(), accent);
  lv_obj_set_style_text_align(*valOut, LV_TEXT_ALIGN_CENTER, 0);
  return card;
}

void uiBmsBuild(UiShellWidgets& shell, UiBmsWidgets& b) {
  uiShellClearContent(shell);
  b = UiBmsWidgets();
  const ThemePalette& t = themeActive();

  // No scrolling — same rule as Glance: fit the content area.
  lv_obj_clear_flag(shell.content, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(shell.content, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(shell.content, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START);
  lv_obj_set_style_pad_row(shell.content, 3, 0);
  lv_obj_set_style_pad_top(shell.content, 0, 0);
  lv_obj_set_style_pad_bottom(shell.content, 0, 0);

  lv_obj_update_layout(shell.content);
  const lv_coord_t sw = shellContentW(shell);
  const lv_coord_t chipW = (sw - 9) / 2;
  const lv_coord_t chipH = 34;

  b.emptyLbl = uiMakeLabel(shell.content, "No BMS data", uiFontTitle(), uiColor565(t.muted));
  lv_obj_add_flag(b.emptyLbl, LV_OBJ_FLAG_HIDDEN);

  // Compact hero
  b.heroCard = uiMakeCard(shell.content, sw, 48);
  lv_obj_set_style_pad_all(b.heroCard, 4, 0);
  lv_obj_set_style_pad_row(b.heroCard, 2, 0);
  lv_obj_set_flex_flow(b.heroCard, LV_FLEX_FLOW_COLUMN);
  lv_obj_clear_flag(b.heroCard, LV_OBJ_FLAG_SCROLLABLE);

  lv_obj_t* top = lv_obj_create(b.heroCard);
  lv_obj_remove_style_all(top);
  lv_obj_set_size(top, sw - 10, 22);
  lv_obj_set_flex_flow(top, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(top, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

  lv_obj_t* left = lv_obj_create(top);
  lv_obj_remove_style_all(left);
  lv_obj_set_size(left, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
  lv_obj_set_flex_flow(left, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(left, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_column(left, 6, 0);
  b.socLbl = uiMakeLabel(left, "--%", uiFontDisplay(), uiColor565(t.charge));
  b.statusLbl = uiMakeLabel(left, "Idle", uiFontBody(), uiColor565(t.muted));
  b.sohLbl = uiMakeLabel(top, "SOH --", uiFontBody(), uiColor565(t.muted));

  b.socBar = lv_bar_create(b.heroCard);
  lv_obj_set_size(b.socBar, sw - 12, 6);
  lv_bar_set_range(b.socBar, 0, 100);
  lv_obj_set_style_bg_color(b.socBar, uiColor565(t.card), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(b.socBar, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_bg_color(b.socBar, uiColor565(t.charge), LV_PART_INDICATOR);
  lv_obj_set_style_radius(b.socBar, 3, LV_PART_MAIN);
  lv_obj_set_style_radius(b.socBar, 3, LV_PART_INDICATOR);

  // 2x2 compact metrics
  b.metricsRow = lv_obj_create(shell.content);
  lv_obj_remove_style_all(b.metricsRow);
  lv_obj_set_size(b.metricsRow, sw, chipH * 2 + 4);
  lv_obj_set_flex_flow(b.metricsRow, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(b.metricsRow, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
  lv_obj_set_style_pad_row(b.metricsRow, 4, 0);
  lv_obj_set_style_pad_column(b.metricsRow, 5, 0);
  makeMetricChip(b.metricsRow, chipW, chipH, "Voltage", &b.mVolts, uiColor565(t.text));
  makeMetricChip(b.metricsRow, chipW, chipH, "Current", &b.mAmps, uiColor565(t.grid));
  makeMetricChip(b.metricsRow, chipW, chipH, "Power", &b.mWatts, uiColor565(t.pv));
  makeMetricChip(b.metricsRow, chipW, chipH, "Temp", &b.mTemp, uiColor565(t.warn));

  // Meta + title on one line to save vertical space
  b.metaLbl = uiMakeLabel(shell.content, "Cycles -- | dV -- | Cells --", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(b.metaLbl, sw);
  lv_obj_set_style_text_align(b.metaLbl, LV_TEXT_ALIGN_CENTER, 0);
  b.cellTitle = nullptr;

  // Remaining height goes to cells (flex grow) — no scroll, no overflow.
  b.cellCard = uiMakeCard(shell.content, sw, 40);
  lv_obj_set_style_pad_all(b.cellCard, 3, 0);
  lv_obj_set_height(b.cellCard, 0);
  lv_obj_set_flex_grow(b.cellCard, 1);
  lv_obj_set_style_min_height(b.cellCard, 48, 0);
  lv_obj_clear_flag(b.cellCard, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(b.cellCard, LV_FLEX_FLOW_COLUMN);

  b.cellStrip = lv_obj_create(b.cellCard);
  lv_obj_remove_style_all(b.cellStrip);
  lv_obj_set_width(b.cellStrip, sw - 10);
  lv_obj_set_height(b.cellStrip, 0);
  lv_obj_set_flex_grow(b.cellStrip, 1);
  lv_obj_set_flex_flow(b.cellStrip, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(b.cellStrip, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END);
  lv_obj_set_style_pad_row(b.cellStrip, 2, 0);
  lv_obj_set_style_pad_column(b.cellStrip, 2, 0);
  lv_obj_clear_flag(b.cellStrip, LV_OBJ_FLAG_SCROLLABLE);
}

static void layoutCell(UiBmsWidgets& b, size_t idx, lv_coord_t cw, lv_coord_t barH) {
  if (idx >= UiBmsWidgets::kMaxCells || !b.cellCol[idx]) return;
  lv_obj_set_size(b.cellCol[idx], cw, barH + 22);
  lv_obj_set_width(b.cellBar[idx], cw - 2);
  if (b.cellMark[idx]) lv_obj_set_width(b.cellMark[idx], cw);
  if (b.cellIdx[idx]) lv_obj_set_width(b.cellIdx[idx], cw);
}

static void ensureCell(UiBmsWidgets& b, size_t idx, lv_coord_t cw, lv_coord_t barH) {
  if (idx >= UiBmsWidgets::kMaxCells) return;
  if (!b.cellCol[idx]) {
    const ThemePalette& t = themeActive();
    lv_obj_t* col = lv_obj_create(b.cellStrip);
    lv_obj_remove_style_all(col);
    lv_obj_clear_flag(col, LV_OBJ_FLAG_SCROLLABLE);

    b.cellMark[idx] = uiMakeLabel(col, "", uiFontBody(), uiColor565(t.warn));
    lv_obj_set_style_text_align(b.cellMark[idx], LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(b.cellMark[idx], LV_ALIGN_TOP_MID, 0, 0);

    b.cellBar[idx] = lv_obj_create(col);
    lv_obj_remove_style_all(b.cellBar[idx]);
    lv_obj_set_style_radius(b.cellBar[idx], 3, 0);
    lv_obj_clear_flag(b.cellBar[idx], LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_align(b.cellBar[idx], LV_ALIGN_BOTTOM_MID, 0, -14);

    b.cellLbl[idx] = uiMakeLabel(b.cellBar[idx], "--", kCellFont, lv_color_white());
    lv_obj_set_style_text_align(b.cellLbl[idx], LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_center(b.cellLbl[idx]);

    char ibuf[8];
    snprintf(ibuf, sizeof(ibuf), "%u", (unsigned)(idx + 1));
    b.cellIdx[idx] = uiMakeLabel(col, ibuf, uiFontBody(), uiColor565(t.dim));
    lv_obj_set_style_text_align(b.cellIdx[idx], LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_transform_zoom(b.cellIdx[idx], 128, 0); // ~50% size
    lv_obj_set_style_transform_pivot_x(b.cellIdx[idx], lv_pct(50), 0);
    lv_obj_set_style_transform_pivot_y(b.cellIdx[idx], lv_pct(50), 0);
    lv_obj_align(b.cellIdx[idx], LV_ALIGN_BOTTOM_MID, 0, 2);

    b.cellCol[idx] = col;
    if (idx + 1 > b.cellCount) b.cellCount = idx + 1;
  }
  layoutCell(b, idx, cw, barH);
}

static void setHiddenGroup(UiBmsWidgets& b, bool hideData) {
  auto set = [](lv_obj_t* o, bool hide) {
    if (!o) return;
    if (hide) lv_obj_add_flag(o, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_clear_flag(o, LV_OBJ_FLAG_HIDDEN);
  };
  set(b.heroCard, hideData);
  set(b.metricsRow, hideData);
  set(b.metaLbl, hideData);
  set(b.cellCard, hideData);
  set(b.emptyLbl, !hideData);
}

void uiBmsUpdate(UiBmsWidgets& b, const BmsData& data) {
  if (!b.heroCard) return;

  if (!data.ok) {
    setHiddenGroup(b, true);
    return;
  }
  setHiddenGroup(b, false);

  char buf[64];
  const float soc = isnan(data.soc) ? 0.0f : data.soc;
  snprintf(buf, sizeof(buf), "%.0f%%", soc);
  uiSetLabelText(b.socLbl, buf);
  lv_obj_set_style_text_color(b.socLbl, uiSocColor(soc), 0);
  if (b.socBar) {
    lv_bar_set_value(b.socBar, (int32_t)constrain(soc, 0.0f, 100.0f), LV_ANIM_OFF);
    lv_obj_set_style_bg_color(b.socBar, uiSocColor(soc), LV_PART_INDICATOR);
  }

  String st = data.status.length() ? data.status : String("Idle");
  uiSetLabelText(b.statusLbl, st.c_str());
  lv_obj_set_style_text_color(b.statusLbl, statusColor(st), 0);

  if (isnan(data.soh)) uiSetLabelText(b.sohLbl, "SOH --");
  else {
    snprintf(buf, sizeof(buf), "SOH %.0f%%", data.soh);
    uiSetLabelText(b.sohLbl, buf);
  }

  if (b.mVolts) {
    if (isnan(data.volts)) uiSetLabelText(b.mVolts, "--");
    else {
      snprintf(buf, sizeof(buf), "%.1fV", data.volts);
      uiSetLabelText(b.mVolts, buf);
    }
  }
  if (b.mAmps) {
    if (isnan(data.amps)) uiSetLabelText(b.mAmps, "--");
    else {
      snprintf(buf, sizeof(buf), "%+.1fA", data.amps);
      uiSetLabelText(b.mAmps, buf);
    }
  }
  if (b.mWatts) uiSetLabelText(b.mWatts, uiFmtPower(data.watts));
  if (b.mTemp) {
    if (isnan(data.temp_avg)) uiSetLabelText(b.mTemp, "--");
    else {
      snprintf(buf, sizeof(buf), "%.0fC", data.temp_avg);
      uiSetLabelText(b.mTemp, buf);
    }
  }

  char cyc[20], dv[20], cells[20];
  if (isnan(data.cycles)) snprintf(cyc, sizeof(cyc), "Cyc --");
  else snprintf(cyc, sizeof(cyc), "Cyc %.0f", data.cycles);
  if (isnan(data.cell_delta_v)) snprintf(dv, sizeof(dv), "dV --");
  else snprintf(dv, sizeof(dv), "dV %.0fmV", data.cell_delta_v * 1000.0f);
  snprintf(cells, sizeof(cells), "n=%d", data.cell_count > 0 ? data.cell_count : (int)data.cells.size());
  snprintf(buf, sizeof(buf), "%s | %s | %s", cyc, dv, cells);
  uiSetLabelText(b.metaLbl, buf);

  if (!b.cellStrip) return;
  lv_obj_update_layout(b.cellStrip);
  const lv_coord_t stripH = lv_obj_get_height(b.cellStrip);
  const lv_coord_t stripW = lv_obj_get_width(b.cellStrip);
  if (stripH < 16 || stripW < 16) return;

  size_t n = data.cells.size();
  if (n == 0 && data.cell_count > 0) return;
  if (n > UiBmsWidgets::kMaxCells) n = UiBmsWidgets::kMaxCells;
  if (n == 0) {
    for (size_t i = 0; i < b.cellCount; i++) {
      if (b.cellCol[i]) lv_obj_add_flag(b.cellCol[i], LV_OBJ_FLAG_HIDDEN);
    }
    return;
  }

  const int cols = n > 8 ? 8 : (int)n;
  const int rows = (int)((n + cols - 1) / cols);
  const lv_coord_t cw = (stripW - (cols - 1) * 2) / cols;
  // Leave room for mark + index labels inside each column.
  const lv_coord_t barH = (stripH - rows * 24 - (rows - 1) * 2) / rows;
  const lv_coord_t useBarH = barH > 14 ? barH : 14;

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
    const float norm = constrain((v - vmin) / span, 0.20f, 1.0f);
    const bool compact = cw < 22;
    const lv_coord_t h = (lv_coord_t)max((float)useBarH * norm, 12.0f);
    lv_obj_set_size(b.cellBar[i], cw - 2, h);
    lv_obj_set_style_bg_color(b.cellBar[i], uiColor565(cellVoltageColor(v)), 0);
    lv_obj_set_style_bg_opa(b.cellBar[i], LV_OPA_COVER, 0);
    lv_obj_align(b.cellBar[i], LV_ALIGN_BOTTOM_MID, 0, -14);
    lv_obj_set_style_text_font(b.cellLbl[i], kCellFont, 0);
    snprintf(buf, sizeof(buf), compact ? "%.1f" : "%.2f", v);
    uiSetLabelText(b.cellLbl[i], buf);
    lv_obj_center(b.cellLbl[i]);
    if (b.cellMark[i]) {
      if (i == minIdx && i == maxIdx) uiSetLabelText(b.cellMark[i], "");
      else if (i == minIdx) uiSetLabelText(b.cellMark[i], LV_SYMBOL_DOWN);
      else if (i == maxIdx) uiSetLabelText(b.cellMark[i], LV_SYMBOL_UP);
      else uiSetLabelText(b.cellMark[i], "");
    }
  }
  for (size_t i = n; i < b.cellCount; i++) {
    if (b.cellCol[i]) lv_obj_add_flag(b.cellCol[i], LV_OBJ_FLAG_HIDDEN);
  }
}
