#include "ui_glance.h"
#include "ui_theme.h"
#include "ui_util.h"
#include "layout.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static const lv_coord_t kBattW = 56;
static const lv_coord_t kBattH = 64;
static const lv_coord_t kBattInnerH = 48;
static const lv_coord_t kBattCapW = 22;
static const lv_coord_t kBattCapH = 5;
static const lv_coord_t kSocRowH = kBattH + kBattCapH + 6;
static const lv_coord_t kClusterGap = 14;
static const lv_color_t kSocWhite = lv_color_white();

static lv_coord_t s_classicSocMaxW = 100;

static lv_coord_t classicSocTextWidth(const char* num, const char* pct, const lv_font_t* font) {
  const lv_coord_t numW = lv_txt_get_width(num, (uint32_t)strlen(num), font, -1, LV_TEXT_FLAG_NONE);
  const lv_coord_t pctW = lv_txt_get_width(pct, (uint32_t)strlen(pct), font, -1, LV_TEXT_FLAG_NONE);
  return numW + pctW + 2;
}

static const lv_font_t* pickClassicSocFont(const char* num, const char* pct, lv_coord_t maxW) {
  static const lv_font_t* kFonts[] = {
      &lv_font_montserrat_48, &lv_font_montserrat_32, &lv_font_montserrat_28, &lv_font_montserrat_20,
  };
  for (size_t i = 0; i < sizeof(kFonts) / sizeof(kFonts[0]); i++) {
    if (classicSocTextWidth(num, pct, kFonts[i]) <= maxW) return kFonts[i];
  }
  return &lv_font_montserrat_20;
}

static void applyClassicSocStyle(lv_obj_t* lbl, const lv_font_t* font) {
  lv_obj_set_style_text_font(lbl, font, 0);
  lv_obj_set_style_text_color(lbl, kSocWhite, 0);
  lv_obj_set_style_text_letter_space(lbl, -1, 0);
  lv_obj_set_style_transform_zoom(lbl, 256, 0);
  lv_obj_set_style_shadow_width(lbl, 0, 0);
}

static void fitClassicSocLabels(UiGlanceWidgets& g, const char* num, const char* pct) {
  if (!g.socLbl || !g.socSubLbl) return;
  const lv_font_t* font = pickClassicSocFont(num, pct, s_classicSocMaxW);
  applyClassicSocStyle(g.socLbl, font);
  applyClassicSocStyle(g.socSubLbl, font);
}

static void buildBatteryIcon(UiGlanceWidgets& g, lv_obj_t* parent, const ThemePalette& t) {
  g.battIcon = lv_obj_create(parent);
  lv_obj_remove_style_all(g.battIcon);
  lv_obj_set_size(g.battIcon, kBattW, kBattH);
  lv_obj_set_style_border_width(g.battIcon, 2, 0);
  lv_obj_set_style_border_color(g.battIcon, uiColor565(t.text), 0);
  lv_obj_set_style_radius(g.battIcon, 5, 0);
  lv_obj_set_style_bg_opa(g.battIcon, LV_OPA_TRANSP, 0);
  lv_obj_clear_flag(g.battIcon, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_align(g.battIcon, LV_ALIGN_BOTTOM_MID, 0, 0);

  g.battNub = lv_obj_create(parent);
  lv_obj_remove_style_all(g.battNub);
  lv_obj_set_size(g.battNub, kBattCapW, kBattCapH);
  lv_obj_set_style_bg_color(g.battNub, uiColor565(t.text), 0);
  lv_obj_set_style_bg_opa(g.battNub, LV_OPA_COVER, 0);
  lv_obj_set_style_radius(g.battNub, 2, 0);
  lv_obj_align_to(g.battNub, g.battIcon, LV_ALIGN_OUT_TOP_MID, 0, 0);

  g.battFill = lv_obj_create(g.battIcon);
  lv_obj_remove_style_all(g.battFill);
  lv_obj_set_width(g.battFill, kBattW - 10);
  lv_obj_set_height(g.battFill, 6);
  lv_obj_set_style_bg_color(g.battFill, uiColor565(t.charge), 0);
  lv_obj_set_style_bg_opa(g.battFill, LV_OPA_COVER, 0);
  lv_obj_set_style_radius(g.battFill, 2, 0);
  lv_obj_align(g.battFill, LV_ALIGN_BOTTOM_MID, 0, -6);

  g.battArrow = uiMakeLabel(g.battIcon, "", uiFontBody(), uiColor565(t.charge));
  lv_obj_align(g.battArrow, LV_ALIGN_CENTER, 0, -2);
}

static lv_obj_t* makeMetricCard(lv_obj_t* parent, lv_coord_t cardW, lv_coord_t cardH, const char* icon,
                                const char* title, lv_obj_t** valOut, lv_color_t accent) {
  lv_obj_t* card = uiMakeCard(parent, cardW, cardH);
  lv_obj_set_style_pad_all(card, 4, 0);
  lv_obj_set_style_pad_row(card, 2, 0);
  lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(card, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);

  lv_obj_t* capRow = lv_obj_create(card);
  lv_obj_remove_style_all(capRow);
  lv_obj_set_width(capRow, cardW - 8);
  lv_obj_set_height(capRow, LV_SIZE_CONTENT);
  lv_obj_clear_flag(capRow, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(capRow, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(capRow, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_column(capRow, 3, 0);
  if (icon && icon[0]) uiMakeLabel(capRow, icon, uiFontBody(), accent);
  uiMakeLabel(capRow, title, uiFontBody(), uiColor565(themeActive().muted));

  *valOut = uiMakeLabel(card, "--", uiFontTitle(), accent);
  lv_obj_set_width(*valOut, cardW - 10);
  lv_obj_set_style_text_align(*valOut, LV_TEXT_ALIGN_RIGHT, 0);
  return card;
}

static void buildClassicHome(lv_obj_t* content, UiGlanceWidgets& g, lv_coord_t contentW, lv_coord_t cardW,
                             lv_coord_t cardH) {
  const ThemePalette& t = themeActive();

  s_classicSocMaxW = contentW - kBattW - kClusterGap - 24;
  if (s_classicSocMaxW < 48) s_classicSocMaxW = 48;

  lv_obj_t* socRow = lv_obj_create(content);
  lv_obj_remove_style_all(socRow);
  lv_obj_set_size(socRow, contentW, kSocRowH);
  lv_obj_clear_flag(socRow, LV_OBJ_FLAG_SCROLLABLE);

  lv_obj_t* cluster = lv_obj_create(socRow);
  lv_obj_remove_style_all(cluster);
  lv_obj_set_size(cluster, LV_SIZE_CONTENT, kSocRowH);
  lv_obj_clear_flag(cluster, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(cluster, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(cluster, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_column(cluster, kClusterGap, 0);
  lv_obj_align(cluster, LV_ALIGN_CENTER, 0, 0);

  lv_obj_t* socWrap = lv_obj_create(cluster);
  lv_obj_remove_style_all(socWrap);
  lv_obj_set_width(socWrap, s_classicSocMaxW);
  lv_obj_set_height(socWrap, kBattH);
  lv_obj_clear_flag(socWrap, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(socWrap, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(socWrap, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END);

  g.socLbl = uiMakeLabel(socWrap, "0", uiFontSoc(), kSocWhite);
  g.socSubLbl = uiMakeLabel(socWrap, "%", uiFontSoc(), kSocWhite);
  lv_obj_set_style_pad_left(g.socSubLbl, 2, 0);
  fitClassicSocLabels(g, "100", "%");

  lv_obj_t* battWrap = lv_obj_create(cluster);
  lv_obj_remove_style_all(battWrap);
  lv_obj_set_size(battWrap, kBattW, kSocRowH);
  lv_obj_clear_flag(battWrap, LV_OBJ_FLAG_SCROLLABLE);
  buildBatteryIcon(g, battWrap, t);

  g.socBar = lv_bar_create(content);
  lv_obj_set_size(g.socBar, contentW - 8, 8);
  lv_bar_set_range(g.socBar, 0, 100);
  lv_obj_set_style_bg_color(g.socBar, uiColor565(t.card), LV_PART_MAIN);
  lv_obj_set_style_bg_color(g.socBar, uiColor565(t.charge), LV_PART_INDICATOR);

  g.battLbl = uiMakeLabel(content, "Idle", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.battLbl, contentW);
  lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

  lv_obj_t* gridRow = lv_obj_create(content);
  lv_obj_remove_style_all(gridRow);
  lv_obj_set_size(gridRow, contentW, cardH * 2 + 6);
  lv_obj_set_flex_flow(gridRow, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(gridRow, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
  lv_obj_set_style_pad_row(gridRow, 6, 0);
  lv_obj_set_style_pad_column(gridRow, 6, 0);
  makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_CHARGE, "PV", &g.pvVal, uiColor565(t.pv));
  makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_HOME, "Load", &g.loadVal, uiColor565(t.text));
  makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_SHUFFLE, "Grid", &g.gridVal, uiColor565(t.grid));
  makeMetricCard(gridRow, cardW, cardH, "", "Today", &g.todayPv, uiColor565(t.muted));

  g.statusLbl = nullptr;
  g.tempLbl = uiMakeLabel(content, "Inv --  |  Batt --", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.tempLbl, contentW);
  lv_obj_set_style_text_align(g.tempLbl, LV_TEXT_ALIGN_CENTER, 0);
}

static uint8_t s_glanceBuiltLayout = 255;

bool uiGlanceNeedsBuild(const UiGlanceWidgets& g, uint8_t layoutId) {
  return !g.gridPill || s_glanceBuiltLayout != layoutId;
}

void uiGlanceDestroy(UiGlanceWidgets& g) {
  g = UiGlanceWidgets();
  s_glanceBuiltLayout = 255;
}

void uiGlanceBuild(UiShellWidgets& shell, UiGlanceWidgets& g, uint8_t layoutId) {
  uiShellClearContent(shell);
  g = UiGlanceWidgets();
  const ThemePalette& t = themeActive();
  lv_obj_t* content = shell.content;
  const lv_coord_t contentW = lv_obj_get_width(shell.root) - 8;
  const lv_coord_t cardW = (contentW - 14) / 2;
  const lv_coord_t cardH = 52;

  g.gridPill = lv_obj_create(content);
  lv_obj_remove_style_all(g.gridPill);
  lv_obj_set_size(g.gridPill, contentW, 16);
  lv_obj_set_style_radius(g.gridPill, 8, 0);
  lv_obj_set_style_bg_color(g.gridPill, uiColor565(t.ok), 0);
  lv_obj_set_style_bg_opa(g.gridPill, LV_OPA_COVER, 0);
  lv_obj_t* gridLbl = uiMakeLabel(g.gridPill, "GRID OK", uiFontBody(), uiColor565(t.onAccent));
  lv_obj_center(gridLbl);

  if (layoutId == 2) {
    g.arc = lv_arc_create(content);
    lv_obj_set_size(g.arc, 120, 120);
    lv_arc_set_rotation(g.arc, 135);
    lv_arc_set_bg_angles(g.arc, 0, 270);
    lv_arc_set_range(g.arc, 0, 100);
    lv_obj_set_style_arc_width(g.arc, 10, LV_PART_MAIN);
    lv_obj_set_style_arc_width(g.arc, 10, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(g.arc, uiColor565(t.card), LV_PART_MAIN);
    lv_obj_set_style_arc_color(g.arc, uiSocColor(50), LV_PART_INDICATOR);
    g.socLbl = uiMakeLabel(g.arc, "0%", uiFontSoc(), uiColor565(t.text));
    lv_obj_center(g.socLbl);

    lv_obj_t* metrics = lv_obj_create(content);
    lv_obj_remove_style_all(metrics);
    lv_obj_set_size(metrics, contentW, cardH + 4);
    lv_obj_set_flex_flow(metrics, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(metrics, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    const lv_coord_t mW = (contentW - 8) / 2;
    makeMetricCard(metrics, mW, cardH, LV_SYMBOL_CHARGE, "PV", &g.pvVal, uiColor565(t.pv));
    makeMetricCard(metrics, mW, cardH, LV_SYMBOL_HOME, "Load", &g.loadVal, uiColor565(t.text));
  } else if (layoutId == 3) {
    const char* labels[] = {"PV", "Load", "Grid"};
    for (int i = 0; i < 3; i++) {
      lv_obj_t* row = lv_obj_create(content);
      lv_obj_remove_style_all(row);
      lv_obj_set_size(row, contentW - 8, 32);
      uiMakeLabel(row, labels[i], uiFontBody(), uiColor565(t.muted));
      g.bars[i] = lv_bar_create(row);
      lv_obj_set_size(g.bars[i], contentW - 56, 8);
      lv_obj_align(g.bars[i], LV_ALIGN_BOTTOM_LEFT, 0, 0);
      lv_bar_set_range(g.bars[i], 0, 100);
      lv_obj_set_style_bg_color(g.bars[i], uiColor565(t.card), LV_PART_MAIN);
    }
    g.socLbl = uiMakeLabel(content, "SOC 0%", uiFontTitle(), uiColor565(t.text));
  } else if (layoutId == 4) {
    g.flowCol = lv_obj_create(content);
    lv_obj_remove_style_all(g.flowCol);
    lv_obj_set_size(g.flowCol, contentW - 8, 120);
    lv_obj_set_flex_flow(g.flowCol, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(g.flowCol, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    g.pvVal = uiMakeLabel(g.flowCol, "PV --", uiFontBody(), uiColor565(t.pv));
    g.loadVal = uiMakeLabel(g.flowCol, "Home --", uiFontBody(), uiColor565(t.text));
    g.gridVal = uiMakeLabel(g.flowCol, "Grid --", uiFontBody(), uiColor565(t.grid));
    g.socLbl = uiMakeLabel(g.flowCol, "0% SOC", uiFontTitle(), uiColor565(t.text));
  } else if (layoutId == 1) {
    g.socLbl = uiMakeLabel(content, "0%", uiFontDisplay(), uiColor565(t.text));
    lv_obj_set_width(g.socLbl, contentW - 8);
    lv_obj_set_style_text_align(g.socLbl, LV_TEXT_ALIGN_CENTER, 0);
    g.socBar = lv_bar_create(content);
    lv_obj_set_size(g.socBar, contentW - 24, 10);
    lv_bar_set_range(g.socBar, 0, 100);
    lv_obj_set_style_bg_color(g.socBar, uiColor565(t.card), LV_PART_MAIN);
    lv_obj_set_style_bg_color(g.socBar, uiColor565(t.charge), LV_PART_INDICATOR);
    g.battLbl = uiMakeLabel(content, "Idle", uiFontBody(), uiColor565(t.muted));
    lv_obj_t* gridRow = lv_obj_create(content);
    lv_obj_remove_style_all(gridRow);
    lv_obj_set_size(gridRow, contentW, cardH * 2 + 6);
    lv_obj_set_flex_flow(gridRow, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(gridRow, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_row(gridRow, 6, 0);
    lv_obj_set_style_pad_column(gridRow, 6, 0);
    makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_CHARGE, "PV", &g.pvVal, uiColor565(t.pv));
    makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_HOME, "Load", &g.loadVal, uiColor565(t.text));
    makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_SHUFFLE, "Grid", &g.gridVal, uiColor565(t.grid));
    makeMetricCard(gridRow, cardW, cardH, "", "Today", &g.todayPv, uiColor565(t.muted));
  } else {
    buildClassicHome(content, g, contentW, cardW, cardH);
  }

  s_glanceBuiltLayout = layoutId;

  g.staleOverlay = lv_obj_create(content);
  lv_obj_remove_style_all(g.staleOverlay);
  lv_obj_set_size(g.staleOverlay, contentW - 8, 28);
  lv_obj_set_style_bg_color(g.staleOverlay, uiColor565(t.danger), 0);
  lv_obj_set_style_bg_opa(g.staleOverlay, LV_OPA_60, 0);
  lv_obj_set_style_radius(g.staleOverlay, 6, 0);
  uiMakeLabel(g.staleOverlay, "No connection", uiFontBody(), lv_color_white());
  lv_obj_center(lv_obj_get_child(g.staleOverlay, 0));
  lv_obj_add_flag(g.staleOverlay, LV_OBJ_FLAG_HIDDEN);
}

static void setGridPill(UiGlanceWidgets& g, const GlanceData& data, bool gridAlert) {
  if (!g.gridPill) return;
  const ThemePalette& t = themeActive();
  lv_obj_t* lbl = lv_obj_get_child(g.gridPill, 0);
  const bool offline = gridAlert || data.grid_state == "offline" || data.grid_state == "brownout";
  uint16_t bg = t.ok;
  if (offline) {
    bg = t.danger;
  } else if (data.grid_state == "import") {
    bg = t.gridImport;
  } else if (data.grid_state == "export") {
    bg = t.gridExport;
  }
  lv_obj_set_style_bg_color(g.gridPill, uiColor565(bg), 0);
  String text = offline ? "NO GRID" : ("GRID " + data.grid_label);
  text.toUpperCase();
  uiSetLabelText(lbl, text);
}

static String gridMetricText(const GlanceData& data) {
  if (data.grid_state == "ok") return String("Idle");
  return uiFmtPower(data.grid_w);
}

static void applyBatteryFill(UiGlanceWidgets& g, const GlanceData& data, uint32_t animMs, bool allowAnim) {
  if (!g.battIcon || !g.battFill) return;
  const float soc = isnan(data.soc) ? 0.0f : data.soc;
  const bool charging = !isnan(data.batt_w) && data.batt_w > 20.0f;
  const bool discharging = !isnan(data.batt_w) && data.batt_w < -20.0f;
  const ThemePalette& th = themeActive();

  lv_color_t fc = uiSocColor(soc);
  if (charging) fc = uiColor565(th.charge);
  else if (discharging) fc = uiColor565(th.grid);

  float displaySoc = soc;
  if (allowAnim && (charging || discharging)) {
    const float t = (float)(animMs % 1600) / 1600.0f;
    const float wave = sinf(t * 6.2831853f) * 0.5f + 0.5f;
    const float delta = wave * 12.0f;
    if (charging) displaySoc = constrain(soc + delta, 0.0f, 100.0f);
    else displaySoc = constrain(soc - delta, 0.0f, 100.0f);
  }

  const lv_coord_t fillH = (lv_coord_t)max(6.0f, kBattInnerH * displaySoc / 100.0f);
  lv_obj_set_height(g.battFill, fillH);
  lv_obj_set_style_bg_color(g.battFill, fc, 0);
  lv_obj_align(g.battFill, LV_ALIGN_BOTTOM_MID, 0, -6);

  if (g.battArrow) {
    if (charging) uiSetLabelText(g.battArrow, LV_SYMBOL_UP);
    else if (discharging) uiSetLabelText(g.battArrow, LV_SYMBOL_DOWN);
    else uiSetLabelText(g.battArrow, "");
    lv_obj_set_style_text_color(g.battArrow, fc, 0);
  }
}

static void updateBatteryIcon(UiGlanceWidgets& g, const GlanceData& data) {
  applyBatteryFill(g, data, 0, false);
}

void uiGlanceUpdate(UiGlanceWidgets& g, const GlanceData& data, bool stale, bool gridAlert, uint8_t layoutId) {
  setGridPill(g, data, gridAlert);
  char buf[32];
  if (g.socLbl) {
    if (g.socSubLbl) {
      const char* num = "--";
      if (!isnan(data.soc)) {
        snprintf(buf, sizeof(buf), "%.0f", data.soc);
        num = buf;
      }
      uiSetLabelText(g.socLbl, num);
      uiSetLabelText(g.socSubLbl, "%");
      fitClassicSocLabels(g, num, "%");
    } else {
      if (isnan(data.soc)) snprintf(buf, sizeof(buf), "--%%");
      else snprintf(buf, sizeof(buf), "%.0f%%", data.soc);
      uiSetLabelText(g.socLbl, buf);
    }
  }
  if (g.socBar && !isnan(data.soc)) {
    lv_bar_set_value(g.socBar, (int32_t)data.soc, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(g.socBar, uiSocColor(data.soc), LV_PART_INDICATOR);
  }
  if (g.arc && !isnan(data.soc)) {
    lv_arc_set_value(g.arc, (int32_t)data.soc);
    lv_obj_set_style_arc_color(g.arc, uiSocColor(data.soc), LV_PART_INDICATOR);
  }
  updateBatteryIcon(g, data);
  if (g.battLbl) {
    String s = data.batt_status.length() ? data.batt_status : "Idle";
    if (!isnan(data.batt_w) && fabsf(data.batt_w) > 1.0f) s += " " + uiFmtPower(data.batt_w);
    uiSetLabelText(g.battLbl, s);
  }
  if (g.pvVal) uiSetLabelText(g.pvVal, uiFmtPower(data.pv_w));
  if (g.loadVal) uiSetLabelText(g.loadVal, uiFmtPower(data.load_w));
  if (g.gridVal) uiSetLabelText(g.gridVal, gridMetricText(data));
  if (g.todayPv && layoutId == 0) {
    uiSetLabelText(g.todayPv, uiFmtKwh(data.pv_today_kwh) + " / " + uiFmtKwh(data.load_today_kwh));
  }
  if (g.todayPv && layoutId == 1) uiSetLabelText(g.todayPv, uiFmtKwh(data.pv_today_kwh) + " kWh");
  if (g.statusLbl) {
    uiSetLabelText(g.statusLbl, String("Inverter: ") + (data.status.length() ? data.status : "--"));
  }
  if (g.tempLbl) {
    uiSetLabelText(g.tempLbl, String("Inv ") + uiFmtTemp(data.inv_temp_c, 'C') + "  |  Batt " +
                                   uiFmtTemp(data.batt_temp_c, 'C'));
  }
  if (g.bars[0]) {
    lv_bar_set_value(g.bars[0], (int32_t)constrain(data.pv_w / 50.0f, 0, 100), LV_ANIM_OFF);
    lv_bar_set_value(g.bars[1], (int32_t)constrain(data.load_w / 50.0f, 0, 100), LV_ANIM_OFF);
    lv_bar_set_value(g.bars[2], (int32_t)constrain(fabsf(data.grid_w) / 30.0f, 0, 100), LV_ANIM_OFF);
  }
  if (g.flowCol) {
    uiSetLabelText(g.pvVal, String("PV ") + uiFmtPower(data.pv_w));
    uiSetLabelText(g.loadVal, String("Home ") + uiFmtPower(data.load_w));
    uiSetLabelText(g.gridVal, String("Grid ") + gridMetricText(data));
    snprintf(buf, sizeof(buf), "%.0f%% SOC", isnan(data.soc) ? 0.0f : data.soc);
    uiSetLabelText(g.socLbl, buf);
  }
  if (g.staleOverlay) {
    if (stale) lv_obj_clear_flag(g.staleOverlay, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_add_flag(g.staleOverlay, LV_OBJ_FLAG_HIDDEN);
  }
}

void uiGlancePulseGrid(UiGlanceWidgets& g, bool gridAlert, uint32_t animMs) {
  if (!g.gridPill || !gridAlert) return;
  const ThemePalette& t = themeActive();
  const bool hi = ((animMs / 5000) % 2) == 0;
  lv_obj_set_style_bg_opa(g.gridPill, hi ? LV_OPA_COVER : LV_OPA_40, 0);
  lv_obj_set_style_bg_color(g.gridPill, uiColor565(t.danger), 0);
}

void uiGlanceAnimateBattery(UiGlanceWidgets& g, const GlanceData& data, uint32_t animMs) {
  applyBatteryFill(g, data, animMs, true);
}
