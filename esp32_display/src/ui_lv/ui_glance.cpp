#include "ui_glance.h"
#include "../fonts/lv_font_soc_73.h"
#include "../fonts/lv_font_soc_40.h"
#include "../fonts/lv_font_soc_48.h"
#include "ui_theme.h"
#include "ui_util.h"
#include "layout.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

// Battery thinner (~28% vs original 56) so classic SOC can stay large (~73px visual).
static const lv_coord_t kBattW = 41;
static const lv_coord_t kBattH = 64;
static const lv_coord_t kBattInnerH = 48;
static const lv_coord_t kBattCapW = 16;
static const lv_coord_t kBattCapH = 5;
static const lv_coord_t kSocRowH = kBattH + kBattCapH + 2; // tight to battery+nub; SOC font ~56 line
static const lv_coord_t kClusterGap = 10;
static const lv_color_t kSocWhite = lv_color_white();
// Active battery body inner height (landscape Classic may shrink this).
static lv_coord_t s_battInnerH = kBattInnerH;

static lv_coord_t s_classicSocMaxW = 100;

static lv_coord_t classicSocTextWidth(const char* num, const char* pct, const lv_font_t* font) {
  const lv_coord_t numW = lv_txt_get_width(num, (uint32_t)strlen(num), font, -1, LV_TEXT_FLAG_NONE);
  const lv_coord_t pctW = lv_txt_get_width(pct, (uint32_t)strlen(pct), font, -1, LV_TEXT_FLAG_NONE);
  return numW + pctW + 2;
}

// Native montserrat sizes only — zoom was clipping the SOC off-screen.
static const lv_font_t* pickClassicSocFont(const char* num, const char* pct, lv_coord_t maxW) {
  static const lv_font_t* kFonts[] = {
      &lv_font_soc_73, &lv_font_montserrat_48, &lv_font_montserrat_32, &lv_font_montserrat_28,
      &lv_font_montserrat_20,
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
  lv_obj_set_style_transform_zoom(lbl, 256, 0);  // 100% — no zoom
  lv_obj_set_style_shadow_width(lbl, 0, 0);
  lv_obj_clear_flag(lbl, LV_OBJ_FLAG_HIDDEN);
}

static void fitClassicSocLabels(UiGlanceWidgets& g, const char* num, const char* pct) {
  if (!g.socLbl || !g.socSubLbl) return;
  const lv_font_t* font = pickClassicSocFont(num, pct, s_classicSocMaxW);
  applyClassicSocStyle(g.socLbl, font);
  applyClassicSocStyle(g.socSubLbl, font);
}

static void buildBatteryIcon(UiGlanceWidgets& g, lv_obj_t* parent, const ThemePalette& t,
                             lv_coord_t battH = kBattH, lv_coord_t innerH = kBattInnerH) {
  s_battInnerH = innerH > 0 ? innerH : kBattInnerH;
  g.battIcon = lv_obj_create(parent);
  lv_obj_remove_style_all(g.battIcon);
  lv_obj_set_size(g.battIcon, kBattW, battH);
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
  lv_obj_set_width(g.battFill, kBattW - 8);
  lv_obj_set_height(g.battFill, 6);
  lv_obj_set_style_bg_color(g.battFill, uiColor565(t.charge), 0);
  lv_obj_set_style_bg_opa(g.battFill, LV_OPA_COVER, 0);
  lv_obj_set_style_radius(g.battFill, 2, 0);
  lv_obj_set_style_clip_corner(g.battFill, true, 0);
  lv_obj_clear_flag(g.battFill, LV_OBJ_FLAG_SCROLLABLE);
  // Keep overflow clipped so the flow arrow stays masked inside the fill.
  lv_obj_clear_flag(g.battFill, LV_OBJ_FLAG_OVERFLOW_VISIBLE);
  lv_obj_align(g.battFill, LV_ALIGN_BOTTOM_MID, 0, -6);

  // Arrow is a child of the fill so LVGL clips it to the SOC level.
  g.battArrow = uiMakeLabel(g.battFill, "", uiFontBody(), uiColor565(t.charge));
  lv_obj_set_style_text_align(g.battArrow, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_width(g.battArrow, kBattW - 8);
  lv_obj_align(g.battArrow, LV_ALIGN_TOP_MID, 0, 0);
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


static lv_obj_t* makeMiniMetric(lv_obj_t* parent, lv_coord_t cardW, lv_coord_t cardH, const char* title,
                                lv_obj_t** valOut, lv_color_t accent) {
  lv_obj_t* card = uiMakeCard(parent, cardW, cardH);
  lv_obj_set_style_pad_all(card, 3, 0);
  lv_obj_set_style_pad_row(card, 1, 0);
  lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(card, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  uiMakeLabel(card, title, uiFontBody(), uiColor565(themeActive().muted));
  *valOut = uiMakeLabel(card, "--", uiFontTitle(), accent);
  lv_obj_set_width(*valOut, cardW - 6);
  lv_obj_set_style_text_align(*valOut, LV_TEXT_ALIGN_CENTER, 0);
  return card;
}

static void applyAltSocFont(lv_obj_t* lbl, bool landscape = false) {
  if (!lbl) return;
  lv_obj_set_style_text_font(lbl, landscape ? &lv_font_soc_48 : &lv_font_soc_40, 0);
  lv_obj_set_style_text_letter_space(lbl, -1, 0);
  lv_obj_set_style_transform_zoom(lbl, 256, 0);
}


static lv_obj_t* makeGridPill(lv_obj_t* parent, lv_coord_t width, UiGlanceWidgets& g) {
  const ThemePalette& t = themeActive();
  g.gridPill = lv_obj_create(parent);
  lv_obj_remove_style_all(g.gridPill);
  lv_obj_set_size(g.gridPill, width, 16);
  lv_obj_set_style_radius(g.gridPill, 8, 0);
  lv_obj_set_style_bg_color(g.gridPill, uiColor565(t.ok), 0);
  lv_obj_set_style_bg_opa(g.gridPill, LV_OPA_COVER, 0);
  lv_obj_t* gridLbl = uiMakeLabel(g.gridPill, "GRID OK", uiFontBody(), uiColor565(t.onAccent));
  lv_obj_center(gridLbl);
  return g.gridPill;
}

static lv_obj_t* makeLandBody(lv_obj_t* content, lv_coord_t contentW, lv_coord_t bodyH) {
  lv_obj_t* row = lv_obj_create(content);
  lv_obj_remove_style_all(row);
  lv_obj_set_size(row, contentW, bodyH);
  lv_obj_clear_flag(row, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(row, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_column(row, 6, 0);
  return row;
}

static lv_obj_t* makeLandLeft(lv_obj_t* row, lv_coord_t leftW, lv_coord_t bodyH) {
  lv_obj_t* left = lv_obj_create(row);
  lv_obj_remove_style_all(left);
  lv_obj_set_size(left, leftW, bodyH);
  lv_obj_clear_flag(left, LV_OBJ_FLAG_SCROLLABLE);
  // Top-align inside the content band (header/nav stay clear). Allow the
  // battery nub to draw; do not hard-clip status labels.
  lv_obj_add_flag(left, LV_OBJ_FLAG_OVERFLOW_VISIBLE);
  lv_obj_set_flex_flow(left, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(left, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_top(left, 4, 0);
  lv_obj_set_style_pad_bottom(left, 2, 0);
  lv_obj_set_style_pad_row(left, 3, 0);
  return left;
}

static void buildClassicLandscape(lv_obj_t* content, UiGlanceWidgets& g, lv_coord_t contentW) {
  const ThemePalette& t = themeActive();
  lv_obj_clear_flag(content, LV_OBJ_FLAG_OVERFLOW_VISIBLE);
  // Prefer real content height; if LVGL has not laid out yet, derive from display
  // so we do not leave a black band above the nav.
  lv_coord_t bodyH = lv_obj_get_height(content);
  const lv_coord_t derivedH =
      (lv_coord_t)lv_disp_get_ver_res(nullptr) - 24 - (lv_coord_t)UI_NAV_H - 8;
  if (bodyH < derivedH - 4) bodyH = derivedH;
  if (bodyH > 8) bodyH -= 2;

  // Column: status+cards row on top, Inv/Batt temps under the cards.
  const lv_coord_t tempH = 18;
  lv_coord_t mainH = bodyH - tempH - 2;
  if (mainH < 90) mainH = bodyH > 20 ? bodyH - 20 : bodyH;

  lv_obj_t* col = lv_obj_create(content);
  lv_obj_remove_style_all(col);
  lv_obj_set_size(col, contentW, bodyH);
  lv_obj_clear_flag(col, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(col, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(col, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_row(col, 2, 0);

  lv_obj_t* row = makeLandBody(col, contentW, mainH);
  const lv_coord_t leftW = (contentW * 42) / 100;
  const lv_coord_t rightW = contentW - leftW - 8;
  lv_obj_t* left = makeLandLeft(row, leftW, mainH);
  // GRID -> SOC -> battery -> Charging/watts (temps live under the cards).
  lv_obj_set_flex_align(left, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

  makeGridPill(left, leftW - 6, g);
  if (g.gridPill) lv_obj_set_style_pad_bottom(g.gridPill, 2, 0);

  g.socLbl = uiMakeLabel(left, "0%", &lv_font_soc_48, kSocWhite);
  applyAltSocFont(g.socLbl, true);
  lv_obj_set_width(g.socLbl, leftW - 4);
  lv_obj_set_style_text_align(g.socLbl, LV_TEXT_ALIGN_CENTER, 0);

  // ~20% shorter so 2-line status+watts still fit above temps-under-cards.
  const lv_coord_t landBattH = (kBattH * 80) / 100;
  const lv_coord_t landInnerH = (kBattInnerH * 80) / 100;
  const lv_coord_t landRowH = landBattH + kBattCapH + 2;
  lv_obj_t* battWrap = lv_obj_create(left);
  lv_obj_remove_style_all(battWrap);
  lv_obj_set_size(battWrap, kBattW + 4, landRowH);
  lv_obj_clear_flag(battWrap, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_add_flag(battWrap, LV_OBJ_FLAG_OVERFLOW_VISIBLE);
  lv_obj_set_style_pad_top(battWrap, 2, 0);
  buildBatteryIcon(g, battWrap, t, landBattH, landInnerH);

  g.socBar = nullptr;

  g.battLbl = uiMakeLabel(left, "Idle", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.battLbl, leftW - 4);
  lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);
  lv_label_set_long_mode(g.battLbl, LV_LABEL_LONG_WRAP);
  lv_obj_set_style_text_line_space(g.battLbl, -2, 0);

  // Metrics column: 2x2 cards.
  lv_obj_t* right = lv_obj_create(row);
  lv_obj_remove_style_all(right);
  lv_obj_set_size(right, rightW, mainH);
  lv_obj_clear_flag(right, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(right, LV_OBJ_FLAG_OVERFLOW_VISIBLE);
  lv_obj_set_style_pad_top(right, 6, 0);
  lv_obj_set_flex_flow(right, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(right, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_START);
  lv_obj_set_style_pad_row(right, 4, 0);
  lv_obj_set_style_pad_column(right, 4, 0);
  const lv_coord_t cardW = (rightW - 6) / 2;
  const lv_coord_t cardH = (mainH - 16) / 2;
  g.pvCard = makeMetricCard(right, cardW, cardH, LV_SYMBOL_CHARGE, "PV", &g.pvVal, uiColor565(t.pv));
  makeMetricCard(right, cardW, cardH, LV_SYMBOL_HOME, "Load", &g.loadVal, uiColor565(t.text));
  g.gridCard = makeMetricCard(right, cardW, cardH, LV_SYMBOL_SHUFFLE, "Grid", &g.gridVal, uiColor565(t.grid));
  makeMetricCard(right, cardW, cardH, "", "Today", &g.todayPv, uiColor565(t.muted));

  // Inv/Batt under the cards (full width).
  g.tempLbl = uiMakeLabel(col, "Inv --  |  Batt --", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.tempLbl, contentW);
  lv_obj_set_style_text_align(g.tempLbl, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_style_pad_top(g.tempLbl, 2, 0);
}

static void buildCompactLandscape(lv_obj_t* content, UiGlanceWidgets& g, lv_coord_t contentW) {
  const ThemePalette& t = themeActive();
  lv_coord_t bodyH = lv_obj_get_height(content);
  if (bodyH < 120) bodyH = 150;

  lv_obj_t* row = makeLandBody(content, contentW, bodyH);
  const lv_coord_t leftW = (contentW * 40) / 100;
  const lv_coord_t rightW = contentW - leftW - 8;
  lv_obj_t* left = makeLandLeft(row, leftW, bodyH);

  g.socLbl = uiMakeLabel(left, "0%", &lv_font_soc_48, kSocWhite);
  applyAltSocFont(g.socLbl, true);
  lv_obj_set_width(g.socLbl, leftW - 4);
  lv_obj_set_style_text_align(g.socLbl, LV_TEXT_ALIGN_CENTER, 0);

  g.socBar = lv_bar_create(left);
  lv_obj_set_size(g.socBar, leftW - 12, 10);
  lv_bar_set_range(g.socBar, 0, 100);
  lv_obj_set_style_bg_color(g.socBar, uiColor565(t.card), LV_PART_MAIN);
  lv_obj_set_style_bg_color(g.socBar, uiColor565(t.charge), LV_PART_INDICATOR);
  lv_obj_set_style_radius(g.socBar, 4, 0);

  g.battLbl = uiMakeLabel(left, "Idle", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.battLbl, leftW - 4);
  lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

  lv_obj_t* right = lv_obj_create(row);
  lv_obj_remove_style_all(right);
  lv_obj_set_size(right, rightW, bodyH);
  lv_obj_clear_flag(right, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(right, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(right, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_START);
  lv_obj_set_style_pad_row(right, 4, 0);
  lv_obj_set_style_pad_column(right, 4, 0);
  const lv_coord_t cardW = (rightW - 6) / 2;
  const lv_coord_t cardH = (bodyH - 6) / 2;
  g.pvCard = makeMetricCard(right, cardW, cardH, LV_SYMBOL_CHARGE, "PV", &g.pvVal, uiColor565(t.pv));
  makeMetricCard(right, cardW, cardH, LV_SYMBOL_HOME, "Load", &g.loadVal, uiColor565(t.text));
  g.gridCard = makeMetricCard(right, cardW, cardH, LV_SYMBOL_SHUFFLE, "Grid", &g.gridVal, uiColor565(t.grid));
  makeMetricCard(right, cardW, cardH, "", "Today", &g.todayPv, uiColor565(t.muted));
}

static void buildRingLandscape(lv_obj_t* content, UiGlanceWidgets& g, lv_coord_t contentW) {
  const ThemePalette& t = themeActive();
  lv_coord_t bodyH = lv_obj_get_height(content);
  if (bodyH < 120) bodyH = 150;

  lv_obj_t* row = makeLandBody(content, contentW, bodyH);
  const lv_coord_t leftW = (contentW * 46) / 100;
  const lv_coord_t rightW = contentW - leftW - 8;
  lv_obj_t* left = makeLandLeft(row, leftW, bodyH);

  const lv_coord_t arcSz = bodyH > 150 ? 120 : (bodyH - 28);
  g.arc = lv_arc_create(left);
  lv_obj_set_size(g.arc, arcSz, arcSz);
  lv_arc_set_rotation(g.arc, 135);
  lv_arc_set_bg_angles(g.arc, 0, 270);
  lv_arc_set_range(g.arc, 0, 100);
  lv_obj_remove_style(g.arc, NULL, LV_PART_KNOB);
  lv_obj_clear_flag(g.arc, LV_OBJ_FLAG_CLICKABLE);
  lv_obj_set_style_arc_width(g.arc, 10, LV_PART_MAIN);
  lv_obj_set_style_arc_width(g.arc, 10, LV_PART_INDICATOR);
  lv_obj_set_style_arc_color(g.arc, uiColor565(t.card), LV_PART_MAIN);
  lv_obj_set_style_arc_color(g.arc, uiSocColor(50), LV_PART_INDICATOR);
  g.socLbl = uiMakeLabel(g.arc, "0%", &lv_font_soc_48, kSocWhite);
  applyAltSocFont(g.socLbl, true);
  lv_obj_center(g.socLbl);

  g.battLbl = uiMakeLabel(left, "Idle", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.battLbl, leftW - 4);
  lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

  lv_obj_t* right = lv_obj_create(row);
  lv_obj_remove_style_all(right);
  lv_obj_set_size(right, rightW, bodyH);
  lv_obj_clear_flag(right, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(right, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(right, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_row(right, 4, 0);
  const lv_coord_t mH = (bodyH - 12) / 3;
  g.pvCard = makeMiniMetric(right, rightW - 4, mH, "PV", &g.pvVal, uiColor565(t.pv));
  makeMiniMetric(right, rightW - 4, mH, "Load", &g.loadVal, uiColor565(t.text));
  g.gridCard = makeMiniMetric(right, rightW - 4, mH, "Grid", &g.gridVal, uiColor565(t.grid));
}

static void buildBarsLandscape(lv_obj_t* content, UiGlanceWidgets& g, lv_coord_t contentW) {
  const ThemePalette& t = themeActive();
  lv_coord_t bodyH = lv_obj_get_height(content);
  if (bodyH < 120) bodyH = 150;

  lv_obj_t* row = makeLandBody(content, contentW, bodyH);
  const lv_coord_t leftW = (contentW * 38) / 100;
  const lv_coord_t rightW = contentW - leftW - 8;
  lv_obj_t* left = makeLandLeft(row, leftW, bodyH);

  g.socLbl = uiMakeLabel(left, "0%", &lv_font_soc_48, kSocWhite);
  applyAltSocFont(g.socLbl, true);
  lv_obj_set_width(g.socLbl, leftW - 4);
  lv_obj_set_style_text_align(g.socLbl, LV_TEXT_ALIGN_CENTER, 0);

  g.socBar = lv_bar_create(left);
  lv_obj_set_size(g.socBar, leftW - 12, 10);
  lv_bar_set_range(g.socBar, 0, 100);
  lv_obj_set_style_bg_color(g.socBar, uiColor565(t.card), LV_PART_MAIN);
  lv_obj_set_style_bg_color(g.socBar, uiColor565(t.charge), LV_PART_INDICATOR);
  lv_obj_set_style_radius(g.socBar, 4, 0);

  g.battLbl = uiMakeLabel(left, "Idle", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.battLbl, leftW - 4);
  lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

  lv_obj_t* right = lv_obj_create(row);
  lv_obj_remove_style_all(right);
  lv_obj_set_size(right, rightW, bodyH);
  lv_obj_clear_flag(right, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(right, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(right, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_row(right, 4, 0);

  const char* labels[] = {"PV", "Load", "Grid"};
  lv_color_t accents[] = {uiColor565(t.pv), uiColor565(t.text), uiColor565(t.grid)};
  lv_obj_t** vals[] = {&g.pvVal, &g.loadVal, &g.gridVal};
  const lv_coord_t rowH = (bodyH - 12) / 3;
  for (int i = 0; i < 3; i++) {
    lv_obj_t* r = lv_obj_create(right);
    lv_obj_remove_style_all(r);
    lv_obj_set_size(r, rightW - 4, rowH);
    lv_obj_clear_flag(r, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_t* name = uiMakeLabel(r, labels[i], uiFontBody(), uiColor565(t.muted));
    lv_obj_align(name, LV_ALIGN_TOP_LEFT, 0, 2);
    *vals[i] = uiMakeLabel(r, "--", uiFontTitle(), accents[i]);
    lv_obj_align(*vals[i], LV_ALIGN_TOP_RIGHT, 0, 2);
    g.bars[i] = lv_bar_create(r);
    lv_obj_set_size(g.bars[i], rightW - 10, 10);
    lv_obj_align(g.bars[i], LV_ALIGN_BOTTOM_LEFT, 0, -4);
    lv_bar_set_range(g.bars[i], 0, 100);
    lv_obj_set_style_bg_color(g.bars[i], uiColor565(t.card), LV_PART_MAIN);
    lv_obj_set_style_bg_color(g.bars[i], accents[i], LV_PART_INDICATOR);
    lv_obj_set_style_radius(g.bars[i], 3, 0);
  }
}

static void buildFlowLandscape(lv_obj_t* content, UiGlanceWidgets& g, lv_coord_t contentW) {
  const ThemePalette& t = themeActive();
  lv_coord_t bodyH = lv_obj_get_height(content);
  if (bodyH < 120) bodyH = 150;

  lv_obj_t* row = makeLandBody(content, contentW, bodyH);
  const lv_coord_t leftW = (contentW * 40) / 100;
  const lv_coord_t rightW = contentW - leftW - 8;
  lv_obj_t* left = makeLandLeft(row, leftW, bodyH);

  g.socLbl = uiMakeLabel(left, "0%", &lv_font_soc_48, kSocWhite);
  applyAltSocFont(g.socLbl, true);
  lv_obj_set_width(g.socLbl, leftW - 4);
  lv_obj_set_style_text_align(g.socLbl, LV_TEXT_ALIGN_CENTER, 0);

  g.socBar = lv_bar_create(left);
  lv_obj_set_size(g.socBar, leftW - 12, 8);
  lv_bar_set_range(g.socBar, 0, 100);
  lv_obj_set_style_bg_color(g.socBar, uiColor565(t.card), LV_PART_MAIN);
  lv_obj_set_style_bg_color(g.socBar, uiColor565(t.charge), LV_PART_INDICATOR);

  g.battLbl = uiMakeLabel(left, "Idle", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.battLbl, leftW - 4);
  lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

  g.todayPv = uiMakeLabel(left, "Today -- / --", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.todayPv, leftW - 4);
  lv_obj_set_style_text_align(g.todayPv, LV_TEXT_ALIGN_CENTER, 0);

  g.flowCol = lv_obj_create(row);
  lv_obj_remove_style_all(g.flowCol);
  lv_obj_set_size(g.flowCol, rightW, bodyH);
  lv_obj_set_flex_flow(g.flowCol, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(g.flowCol, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_row(g.flowCol, 4, 0);
  const lv_coord_t mH = (bodyH - 12) / 3;
  g.pvCard = makeMiniMetric(g.flowCol, rightW - 4, mH, "PV", &g.pvVal, uiColor565(t.pv));
  makeMiniMetric(g.flowCol, rightW - 4, mH, "Home", &g.loadVal, uiColor565(t.text));
  g.gridCard = makeMiniMetric(g.flowCol, rightW - 4, mH, "Grid", &g.gridVal, uiColor565(t.grid));
}


static void buildClassicHome(lv_obj_t* content, UiGlanceWidgets& g, lv_coord_t contentW, lv_coord_t cardW,
                             lv_coord_t cardH) {
  const ThemePalette& t = themeActive();

  s_classicSocMaxW = contentW - kBattW - kClusterGap - 12;
  if (s_classicSocMaxW < 48) s_classicSocMaxW = 48;

  lv_obj_t* socRow = lv_obj_create(content);
  lv_obj_remove_style_all(socRow);
  // Room for lv_font_soc_73 so glyphs do not paint into the GRID pill below.
  const lv_coord_t classicSocH = kSocRowH < 78 ? 78 : kSocRowH;
  lv_obj_set_size(socRow, contentW, classicSocH);
  lv_obj_set_style_pad_top(socRow, 4, 0);
  lv_obj_clear_flag(socRow, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(socRow, LV_OBJ_FLAG_OVERFLOW_VISIBLE);

  lv_obj_t* cluster = lv_obj_create(socRow);
  lv_obj_remove_style_all(cluster);
  lv_obj_set_size(cluster, LV_SIZE_CONTENT, kSocRowH);
  lv_obj_clear_flag(cluster, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(cluster, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(cluster, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_column(cluster, kClusterGap, 0);
  lv_obj_align(cluster, LV_ALIGN_CENTER, 0, 0);

  lv_obj_t* socWrap = lv_obj_create(cluster);
  lv_obj_remove_style_all(socWrap);
  lv_obj_set_width(socWrap, s_classicSocMaxW);
  lv_obj_set_height(socWrap, kSocRowH);
  lv_obj_clear_flag(socWrap, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_flex_flow(socWrap, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(socWrap, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_set_style_pad_bottom(socWrap, 2, 0);

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
  lv_obj_set_style_pad_top(gridRow, 8, 0);
  lv_obj_set_size(gridRow, contentW, cardH * 2 + 14); // room for pad_top + pad_row
  lv_obj_set_flex_flow(gridRow, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(gridRow, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
  lv_obj_set_style_pad_row(gridRow, 6, 0);
  lv_obj_set_style_pad_column(gridRow, 6, 0);
  g.pvCard = makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_CHARGE, "PV", &g.pvVal, uiColor565(t.pv));
  makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_HOME, "Load", &g.loadVal, uiColor565(t.text));
  g.gridCard = makeMetricCard(gridRow, cardW, cardH, LV_SYMBOL_SHUFFLE, "Grid", &g.gridVal, uiColor565(t.grid));
  makeMetricCard(gridRow, cardW, cardH, "", "Today", &g.todayPv, uiColor565(t.muted));

  // Under cards — fits when portrait batt status+watts stay on one line.
  g.statusLbl = nullptr;
  g.tempLbl = uiMakeLabel(content, "Inv --  |  Batt --", uiFontBody(), uiColor565(t.muted));
  lv_obj_set_width(g.tempLbl, contentW);
  lv_obj_set_style_text_align(g.tempLbl, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_style_pad_top(g.tempLbl, 4, 0);
}

static uint8_t s_glanceBuiltLayout = 255;
static bool s_glanceBuiltLandscape = false;

bool uiGlanceNeedsBuild(const UiGlanceWidgets& g, uint8_t layoutId, bool landscape) {
  return !g.gridPill || s_glanceBuiltLayout != layoutId || s_glanceBuiltLandscape != landscape;
}

void uiGlanceDestroy(UiGlanceWidgets& g) {
  if (g.gridPill) {
    lv_obj_del(g.gridPill);
    g.gridPill = nullptr;
  }
  g = UiGlanceWidgets();
  s_glanceBuiltLayout = 255;
  s_glanceBuiltLandscape = false;
}

void uiGlanceBuild(UiShellWidgets& shell, UiGlanceWidgets& g, uint8_t layoutId, bool landscape) {
  // Drop a prior header-mounted GRID pill (content clear does not remove it).
  if (g.gridPill) {
    lv_obj_del(g.gridPill);
    g.gridPill = nullptr;
  }
  uiShellClearContent(shell);
  g = UiGlanceWidgets();
  const ThemePalette& t = themeActive();
  lv_obj_t* content = shell.content;
  lv_obj_clear_flag(content, LV_OBJ_FLAG_OVERFLOW_VISIBLE);
  lv_obj_set_style_pad_top(content, 0, 0);
  lv_obj_set_style_pad_row(content, 2, 0);
  const lv_coord_t contentW = lv_obj_get_width(shell.root) - 8;
  const lv_coord_t cardW = (contentW - 14) / 2;
  const lv_coord_t cardH = 52;

  // GRID pill: landscape Classic puts it on the metrics column; portrait puts it
  // under the SOC hero. Never in the header (covers title/clock).
  if (landscape) {
    if (layoutId == 1) buildCompactLandscape(content, g, contentW);
    else if (layoutId == 2) buildRingLandscape(content, g, contentW);
    else if (layoutId == 3) buildBarsLandscape(content, g, contentW);
    else if (layoutId == 4) buildFlowLandscape(content, g, contentW);
    else buildClassicLandscape(content, g, contentW);
  } else {
  if (layoutId == 1) {
    // Compact: mid SOC + bar + 2x2 cards (fits ~189px content, no scroll)
    const lv_coord_t cH = 40;
    g.socLbl = uiMakeLabel(content, "0%", &lv_font_soc_40, kSocWhite);
    applyAltSocFont(g.socLbl);
    lv_obj_set_width(g.socLbl, contentW - 8);
    lv_obj_set_style_text_align(g.socLbl, LV_TEXT_ALIGN_CENTER, 0);

    g.socBar = lv_bar_create(content);
    lv_obj_set_size(g.socBar, contentW - 20, 8);
    lv_bar_set_range(g.socBar, 0, 100);
    lv_obj_set_style_bg_color(g.socBar, uiColor565(t.card), LV_PART_MAIN);
    lv_obj_set_style_bg_color(g.socBar, uiColor565(t.charge), LV_PART_INDICATOR);
    lv_obj_set_style_radius(g.socBar, 4, 0);

    g.battLbl = uiMakeLabel(content, "Idle", uiFontBody(), uiColor565(t.muted));
    lv_obj_set_width(g.battLbl, contentW);
    lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

    lv_obj_t* gridRow = lv_obj_create(content);
    lv_obj_remove_style_all(gridRow);
    lv_obj_set_size(gridRow, contentW, cH * 2 + 6);
    lv_obj_set_flex_flow(gridRow, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(gridRow, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_row(gridRow, 4, 0);
    lv_obj_set_style_pad_column(gridRow, 4, 0);
    const lv_coord_t cW = (contentW - 10) / 2;
    g.pvCard = makeMetricCard(gridRow, cW, cH, LV_SYMBOL_CHARGE, "PV", &g.pvVal, uiColor565(t.pv));
    makeMetricCard(gridRow, cW, cH, LV_SYMBOL_HOME, "Load", &g.loadVal, uiColor565(t.text));
    g.gridCard = makeMetricCard(gridRow, cW, cH, LV_SYMBOL_SHUFFLE, "Grid", &g.gridVal, uiColor565(t.grid));
    makeMetricCard(gridRow, cW, cH, "", "Today", &g.todayPv, uiColor565(t.muted));
  } else if (layoutId == 2) {
    // Ring: SOC arc + 3 mini metrics (sized to avoid clipping)
    const lv_coord_t arcSz = 86;
    g.arc = lv_arc_create(content);
    lv_obj_set_size(g.arc, arcSz, arcSz);
    lv_arc_set_rotation(g.arc, 135);
    lv_arc_set_bg_angles(g.arc, 0, 270);
    lv_arc_set_range(g.arc, 0, 100);
    lv_obj_remove_style(g.arc, NULL, LV_PART_KNOB);
    lv_obj_clear_flag(g.arc, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(g.arc, 9, LV_PART_MAIN);
    lv_obj_set_style_arc_width(g.arc, 9, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(g.arc, uiColor565(t.card), LV_PART_MAIN);
    lv_obj_set_style_arc_color(g.arc, uiSocColor(50), LV_PART_INDICATOR);
    g.socLbl = uiMakeLabel(g.arc, "0%", &lv_font_soc_40, kSocWhite);
    applyAltSocFont(g.socLbl);
    lv_obj_center(g.socLbl);

    g.battLbl = uiMakeLabel(content, "Idle", uiFontBody(), uiColor565(t.muted));
    lv_obj_set_width(g.battLbl, contentW);
    lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

    lv_obj_t* metrics = lv_obj_create(content);
    lv_obj_remove_style_all(metrics);
    lv_obj_set_size(metrics, contentW, 48);
    lv_obj_set_flex_flow(metrics, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(metrics, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    const lv_coord_t mW = (contentW - 12) / 3;
    g.pvCard = makeMiniMetric(metrics, mW, 46, "PV", &g.pvVal, uiColor565(t.pv));
    makeMiniMetric(metrics, mW, 46, "Load", &g.loadVal, uiColor565(t.text));
    g.gridCard = makeMiniMetric(metrics, mW, 46, "Grid", &g.gridVal, uiColor565(t.grid));
  } else if (layoutId == 3) {
    // Bars: SOC hero + labeled power meters
    g.socLbl = uiMakeLabel(content, "0%", &lv_font_soc_40, kSocWhite);
    applyAltSocFont(g.socLbl);
    lv_obj_set_width(g.socLbl, contentW - 8);
    lv_obj_set_style_text_align(g.socLbl, LV_TEXT_ALIGN_CENTER, 0);

    g.socBar = lv_bar_create(content);
    lv_obj_set_size(g.socBar, contentW - 20, 8);
    lv_bar_set_range(g.socBar, 0, 100);
    lv_obj_set_style_bg_color(g.socBar, uiColor565(t.card), LV_PART_MAIN);
    lv_obj_set_style_bg_color(g.socBar, uiColor565(t.charge), LV_PART_INDICATOR);
    lv_obj_set_style_radius(g.socBar, 4, 0);

    g.battLbl = uiMakeLabel(content, "Idle", uiFontBody(), uiColor565(t.muted));
    lv_obj_set_width(g.battLbl, contentW);
    lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

    const char* labels[] = {"PV", "Load", "Grid"};
    lv_color_t accents[] = {uiColor565(t.pv), uiColor565(t.text), uiColor565(t.grid)};
    lv_obj_t** vals[] = {&g.pvVal, &g.loadVal, &g.gridVal};
    for (int i = 0; i < 3; i++) {
      lv_obj_t* row = lv_obj_create(content);
      lv_obj_remove_style_all(row);
      lv_obj_set_size(row, contentW - 4, 30);
      lv_obj_clear_flag(row, LV_OBJ_FLAG_SCROLLABLE);

      lv_obj_t* name = uiMakeLabel(row, labels[i], uiFontBody(), uiColor565(t.muted));
      lv_obj_align(name, LV_ALIGN_TOP_LEFT, 0, 0);

      *vals[i] = uiMakeLabel(row, "--", uiFontTitle(), accents[i]);
      lv_obj_align(*vals[i], LV_ALIGN_TOP_RIGHT, 0, 0);

      g.bars[i] = lv_bar_create(row);
      lv_obj_set_size(g.bars[i], contentW - 8, 8);
      lv_obj_align(g.bars[i], LV_ALIGN_BOTTOM_LEFT, 0, 0);
      lv_bar_set_range(g.bars[i], 0, 100);
      lv_obj_set_style_bg_color(g.bars[i], uiColor565(t.card), LV_PART_MAIN);
      lv_obj_set_style_bg_color(g.bars[i], accents[i], LV_PART_INDICATOR);
      lv_obj_set_style_radius(g.bars[i], 3, 0);
    }
  } else if (layoutId == 4) {
    // Flow: energy snapshot — SOC hero, then PV / Home / Grid strip
    g.socLbl = uiMakeLabel(content, "0%", &lv_font_soc_40, kSocWhite);
    applyAltSocFont(g.socLbl);
    lv_obj_set_width(g.socLbl, contentW - 8);
    lv_obj_set_style_text_align(g.socLbl, LV_TEXT_ALIGN_CENTER, 0);

    g.battLbl = uiMakeLabel(content, "Idle", uiFontBody(), uiColor565(t.muted));
    lv_obj_set_width(g.battLbl, contentW);
    lv_obj_set_style_text_align(g.battLbl, LV_TEXT_ALIGN_CENTER, 0);

    g.socBar = lv_bar_create(content);
    lv_obj_set_size(g.socBar, contentW - 20, 8);
    lv_bar_set_range(g.socBar, 0, 100);
    lv_obj_set_style_bg_color(g.socBar, uiColor565(t.card), LV_PART_MAIN);
    lv_obj_set_style_bg_color(g.socBar, uiColor565(t.charge), LV_PART_INDICATOR);
    lv_obj_set_style_radius(g.socBar, 4, 0);

    g.flowCol = lv_obj_create(content);
    lv_obj_remove_style_all(g.flowCol);
    lv_obj_set_size(g.flowCol, contentW, 56);
    lv_obj_set_flex_flow(g.flowCol, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(g.flowCol, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    const lv_coord_t fW = (contentW - 12) / 3;
    g.pvCard = makeMiniMetric(g.flowCol, fW, 54, "PV", &g.pvVal, uiColor565(t.pv));
    makeMiniMetric(g.flowCol, fW, 54, "Home", &g.loadVal, uiColor565(t.text));
    g.gridCard = makeMiniMetric(g.flowCol, fW, 54, "Grid", &g.gridVal, uiColor565(t.grid));

    g.todayPv = uiMakeLabel(content, "Today -- / --", uiFontBody(), uiColor565(t.muted));
    lv_obj_set_width(g.todayPv, contentW);
    lv_obj_set_style_text_align(g.todayPv, LV_TEXT_ALIGN_CENTER, 0);
  } else {
    buildClassicHome(content, g, contentW, cardW, cardH);
  }
  }

  if (!g.gridPill) {
    // Portrait: GRID on top, SOC under it (header stays title + clock only).
    makeGridPill(content, contentW, g);
    lv_obj_move_to_index(g.gridPill, 0);
    lv_obj_set_style_pad_bottom(g.gridPill, 2, 0);
  }

  s_glanceBuiltLayout = layoutId;
  s_glanceBuiltLandscape = landscape;

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

static void resolveBatteryFlow(const GlanceData& data, bool& charging, bool& discharging, bool& floating) {
  charging = false;
  discharging = false;
  floating = false;

  String state = data.battery_charge_state;
  state.toLowerCase();
  if (state == "charging") { charging = true; return; }
  if (state == "discharging") { discharging = true; return; }
  if (state == "floating") { floating = true; return; }
  if (state == "idle") return;

  String status = data.batt_status;
  status.toLowerCase();
  if (status.indexOf("discharg") >= 0) { discharging = true; return; }
  if (status.indexOf("charg") >= 0) { charging = true; return; }
  if (status.indexOf("float") >= 0) { floating = true; return; }

  // Framework convention: +ve DISCHARGING, -ve CHARGING.
  if (!isnan(data.batt_w)) {
    if (data.batt_w < -20.0f) charging = true;
    else if (data.batt_w > 20.0f) discharging = true;
  }
}

static void applyBatteryFill(UiGlanceWidgets& g, const GlanceData& data, uint32_t animMs, bool allowAnim) {
  if (!g.battIcon || !g.battFill) return;
  const float soc = isnan(data.soc) ? 0.0f : constrain(data.soc, 0.0f, 100.0f);
  bool charging = false, discharging = false, floating = false;
  resolveBatteryFlow(data, charging, discharging, floating);
  const bool active = charging || discharging || floating;
  const ThemePalette& th = themeActive();

  lv_color_t fc = uiSocColor(soc);
  if (charging || floating) fc = uiColor565(th.charge);
  else if (discharging) fc = uiColor565(th.grid);

  // Keep fill height locked to real SOC — motion lives in the masked arrow.
  const lv_coord_t fillH = (lv_coord_t)max(6.0f, s_battInnerH * soc / 100.0f);
  lv_obj_set_height(g.battFill, fillH);
  lv_obj_set_style_bg_color(g.battFill, fc, 0);
  lv_obj_set_style_bg_opa(g.battFill, LV_OPA_COVER, 0);
  lv_obj_align(g.battFill, LV_ALIGN_BOTTOM_MID, 0, -6);

  lv_obj_set_style_border_width(g.battIcon, 2, 0);
  lv_obj_set_style_border_color(g.battIcon, active ? fc : uiColor565(th.text), 0);
  if (g.battNub) lv_obj_set_style_bg_color(g.battNub, active ? fc : uiColor565(th.text), 0);

  if (!g.battArrow) return;

  if (!(allowAnim && active) || fillH < 16) {
    uiSetLabelText(g.battArrow, "");
    return;
  }

  const bool up = charging || floating;
  uiSetLabelText(g.battArrow, up ? LV_SYMBOL_UP : LV_SYMBOL_DOWN);

  // Contrasting arrow so it reads on top of the fill.
  lv_obj_set_style_text_color(g.battArrow, uiColor565(th.text), 0);

  // ~2.4s continuous flow inside the fill, clipped by the parent.
  const uint32_t period = 2400;
  const float t = (float)(animMs % period) / (float)period;  // 0..1
  const lv_coord_t arrowH = 14;
  const lv_coord_t travel = (lv_coord_t)max(0, (int)fillH - arrowH);
  lv_coord_t y;
  if (up) {
    // Rise: bottom -> top
    y = (lv_coord_t)((1.0f - t) * (float)travel);
  } else {
    // Fall: top -> bottom
    y = (lv_coord_t)(t * (float)travel);
  }

  // Fade near the loop wrap so it doesn't pop.
  float edge = t;
  if (edge > 0.5f) edge = 1.0f - edge;
  edge = constrain(edge / 0.15f, 0.0f, 1.0f);  // fade in first/last 15%
  const lv_opa_t arrowOpa = (lv_opa_t)(80 + (int)(edge * 175.0f));

  lv_obj_set_style_text_opa(g.battArrow, arrowOpa, 0);
  lv_obj_align(g.battArrow, LV_ALIGN_TOP_MID, 0, y);
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
      if (layoutId != 0 || (layoutId == 0 && !g.socSubLbl)) {
        applyAltSocFont(g.socLbl, s_glanceBuiltLandscape);
        lv_obj_set_style_text_color(g.socLbl, isnan(data.soc) ? uiColor565(themeActive().muted) : kSocWhite, 0);
      }
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
    if (!isnan(data.batt_w) && fabsf(data.batt_w) > 1.0f) {
      if (s_glanceBuiltLandscape) {
        // Narrow left column: status and watts on separate lines.
        s += "\n";
        s += uiFmtPower(data.batt_w);
      } else {
        // Portrait: one line so Inv/Batt temps stay on-screen.
        s += "  ";
        s += uiFmtPower(data.batt_w);
      }
    }
    lv_label_set_long_mode(g.battLbl, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_line_space(g.battLbl, -2, 0);
    uiSetLabelText(g.battLbl, s);
  }
  if (g.pvVal) uiSetLabelText(g.pvVal, uiFmtPower(data.pv_w));
  if (g.loadVal) uiSetLabelText(g.loadVal, uiFmtPower(data.load_w));
  if (g.gridVal) uiSetLabelText(g.gridVal, gridMetricText(data));
  if (g.todayPv) {
    // Flow uses a bare "Today -- / --" label; metric-card layouts already have a Today title.
    if (layoutId == 4) {
      uiSetLabelText(g.todayPv, String("Today ") + uiFmtKwh(data.pv_today_kwh) + " / " +
                                   uiFmtKwh(data.load_today_kwh));
    } else {
      uiSetLabelText(g.todayPv, uiFmtKwh(data.pv_today_kwh) + " / " + uiFmtKwh(data.load_today_kwh));
    }
  }
  if (g.statusLbl) {
    uiSetLabelText(g.statusLbl, String("Inverter: ") + (data.status.length() ? data.status : "--"));
  }
  if (g.tempLbl) {
    // One line in both orientations — two-line landscape was clipped under the battery stack.
    uiSetLabelText(g.tempLbl, String("Inv ") + uiFmtTemp(data.inv_temp_c, 'C') + "  |  Batt " +
                                   uiFmtTemp(data.batt_temp_c, 'C'));
  }
  if (g.bars[0]) {
    lv_bar_set_value(g.bars[0], (int32_t)constrain(data.pv_w / 50.0f, 0, 100), LV_ANIM_OFF);
    lv_bar_set_value(g.bars[1], (int32_t)constrain(data.load_w / 50.0f, 0, 100), LV_ANIM_OFF);
    lv_bar_set_value(g.bars[2], (int32_t)constrain(fabsf(data.grid_w) / 30.0f, 0, 100), LV_ANIM_OFF);
  }
  // Flow layout reuses pvVal/loadVal/gridVal + socLbl; no prefixed rewrite.
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

static void applyCardGlow(lv_obj_t* card, lv_obj_t* valLbl, bool active, lv_color_t accent,
                          uint32_t animMs, uint16_t phaseOffsetMs) {
  if (!card && !valLbl) return;
  const ThemePalette& th = themeActive();
  if (!active) {
    if (card) {
      lv_obj_set_style_border_width(card, 1, 0);
      lv_obj_set_style_border_color(card, uiColor565(th.line), 0);
      lv_obj_set_style_bg_opa(card, LV_OPA_COVER, 0);
    }
    if (valLbl) lv_obj_set_style_text_opa(valLbl, LV_OPA_COVER, 0);
    return;
  }

  // Very slow ~6.5s breath so it stays peripheral, not distracting.
  const uint32_t period = 6500;
  const float phase = (float)((animMs + phaseOffsetMs) % period) / (float)period;
  const float breath = sinf(phase * 6.2831853f) * 0.5f + 0.5f;  // 0..1
  const uint8_t borderW = breath > 0.65f ? 2 : 1;
  const lv_opa_t textOpa = (lv_opa_t)(210 + (int)(breath * 45.0f));  // mild

  if (card) {
    lv_obj_set_style_border_width(card, borderW, 0);
    lv_obj_set_style_border_color(card, accent, 0);
    lv_obj_set_style_bg_opa(card, (lv_opa_t)(245 + (int)(breath * 10.0f)), 0);
  }
  if (valLbl) {
    lv_obj_set_style_text_color(valLbl, accent, 0);
    lv_obj_set_style_text_opa(valLbl, textOpa, 0);
  }
}

static void applyPvGridGlow(UiGlanceWidgets& g, const GlanceData& data, uint32_t animMs) {
  const ThemePalette& th = themeActive();
  const bool pvOn = !isnan(data.pv_w) && data.pv_w > 20.0f;
  const bool gridOn = !isnan(data.grid_w) && fabsf(data.grid_w) > 20.0f;

  lv_color_t pvAccent = uiColor565(th.pv);
  applyCardGlow(g.pvCard, g.pvVal, pvOn, pvAccent, animMs, 0);

  lv_color_t gridAccent = uiColor565(th.grid);
  if (gridOn && !isnan(data.grid_w)) {
    if (data.grid_w > 0) gridAccent = uiColor565(th.gridImport);
    else gridAccent = uiColor565(th.gridExport);
  }
  applyCardGlow(g.gridCard, g.gridCard ? g.gridVal : nullptr, gridOn && g.gridCard, gridAccent, animMs, 1800);

  // Flow-layout labels (no cards): very slow text pulse.
  const uint32_t period = 6500;
  if (!g.pvCard && g.pvVal) {
    if (pvOn) {
      const float breath = sinf(((animMs % period) / (float)period) * 6.2831853f) * 0.5f + 0.5f;
      lv_obj_set_style_text_color(g.pvVal, pvAccent, 0);
      lv_obj_set_style_text_opa(g.pvVal, (lv_opa_t)(210 + (int)(breath * 45.0f)), 0);
    } else {
      lv_obj_set_style_text_opa(g.pvVal, LV_OPA_COVER, 0);
    }
  }
  if (!g.gridCard && g.gridVal) {
    if (gridOn) {
      const float breath = sinf((((animMs + 1800) % period) / (float)period) * 6.2831853f) * 0.5f + 0.5f;
      lv_obj_set_style_text_color(g.gridVal, gridAccent, 0);
      lv_obj_set_style_text_opa(g.gridVal, (lv_opa_t)(210 + (int)(breath * 45.0f)), 0);
    } else {
      lv_obj_set_style_text_opa(g.gridVal, LV_OPA_COVER, 0);
    }
  }
}

void uiGlanceAnimateBattery(UiGlanceWidgets& g, const GlanceData& data, uint32_t animMs) {
  applyBatteryFill(g, data, animMs, true);
  applyPvGridGlow(g, data, animMs);
}
