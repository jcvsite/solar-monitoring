#include "ui_shell.h"
#include "ui_actions.h"
#include "ui_theme.h"
#include "ui_util.h"
#include "config.h"
#include "layout.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "ui_splash.h"

static bool s_clockStarted = false;
static int s_activeTzOffset = TIMEZONE_OFFSET_SEC;
static UiPage s_navPage = UiPage::Glance;

void uiClockEnsure() {
  if (s_clockStarted) return;
  configTime(s_activeTzOffset, 0, "pool.ntp.org", "time.nist.gov");
  s_clockStarted = true;
}

void uiClockSyncTimezone(int offsetSec) {
  if (offsetSec < -43200 || offsetSec > 50400) return;
  if (offsetSec == s_activeTzOffset && s_clockStarted) return;
  s_activeTzOffset = offsetSec;
  configTime(s_activeTzOffset, 0, "pool.ntp.org", "time.nist.gov");
  s_clockStarted = true;
}

static uint16_t weatherDotColor(int code, int isDay) {
  const ThemePalette& t = themeActive();
  if (code == 0) return isDay ? t.warn : t.muted;
  if (code >= 51 && code <= 99) return t.grid;
  if (code >= 71 && code <= 77) return t.text;
  if (code >= 1 && code <= 48) return t.muted;
  return t.muted;
}

static uint16_t navAccentColor(int idx) {
  const ThemePalette& t = themeActive();
  switch (idx) {
    case 0:
      return t.pv;
    case 1:
      return t.charge;
    case 2:
      return t.grid;
    case 3:
      return t.pv;
    default:
      return t.text;
  }
}

static void styleNavBtn(UiShellWidgets& w, int idx, bool active) {
  if (!w.navBtns[idx]) return;
  const ThemePalette& t = themeActive();
  const uint16_t accent = navAccentColor(idx);

  const uint32_t childCnt = lv_obj_get_child_cnt(w.navBtns[idx]);
  for (uint32_t c = 0; c < childCnt; c++) {
    lv_obj_t* ch = lv_obj_get_child(w.navBtns[idx], c);
    if (lv_obj_check_type(ch, &lv_label_class)) {
      lv_obj_set_style_text_color(ch, uiColor565(active ? accent : t.dim), 0);
    }
  }
  if (w.navDots[idx]) {
    if (active) {
      lv_obj_clear_flag(w.navDots[idx], LV_OBJ_FLAG_HIDDEN);
      lv_obj_set_style_bg_color(w.navDots[idx], uiColor565(accent), 0);
    } else {
      lv_obj_add_flag(w.navDots[idx], LV_OBJ_FLAG_HIDDEN);
    }
  }
}

int uiShellNavIndex(UiPage page) {
  switch (page) {
    case UiPage::Glance:
      return 0;
    case UiPage::Bms:
      return 1;
    case UiPage::History:
      return 2;
    case UiPage::Settings:
    case UiPage::SettingsConn:
    case UiPage::SettingsUpdates:
      return 3;
    default:
      return -1;
  }
}

String uiClockHeaderRight(const GlanceData& g) {
  struct tm ti;
  String out;
  if (g.clock.length()) {
    out = g.clock;
  } else if (getLocalTime(&ti)) {
    char buf[16];
    strftime(buf, sizeof(buf), "%-I:%M %p", &ti);
    out = String(buf);
  } else {
    out = "--:--";
  }
  if (g.weather_enabled && !isnan(g.weather_temp)) {
    char wbuf[16];
    snprintf(wbuf, sizeof(wbuf), "  %.0f%c", g.weather_temp, g.weather_unit);
    out += wbuf;
  }
  return out;
}

void uiShellSetGlanceHeader(UiShellWidgets& w, const GlanceData& g) {
  uiShellSetHeader(w, g.title, uiClockHeaderRight(g));
  if (w.weatherDot) {
    if (g.weather_enabled && !isnan(g.weather_temp)) {
      lv_obj_clear_flag(w.weatherDot, LV_OBJ_FLAG_HIDDEN);
      lv_obj_set_style_bg_color(w.weatherDot, uiColor565(weatherDotColor(g.weather_code, g.weather_is_day)), 0);
      lv_obj_align_to(w.weatherDot, w.rightLbl, LV_ALIGN_OUT_LEFT_MID, -3, 0);
    } else {
      lv_obj_add_flag(w.weatherDot, LV_OBJ_FLAG_HIDDEN);
    }
  }
  if (w.alertDot) {
    if (g.alerts) lv_obj_clear_flag(w.alertDot, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_add_flag(w.alertDot, LV_OBJ_FLAG_HIDDEN);
  }
}

static void fireNavIndex(int idx) {
  if (idx < 0 || idx > 3) return;
  UiActionCtx ctx;
  ctx.index = idx;
  if (idx == 3) {
    uiActionsFire(UiActionId::OpenSettings, ctx);
  } else {
    ctx.page = (UiPage)idx;
    uiActionsFire(UiActionId::NavPage, ctx);
  }
}

static void navClicked(lv_event_t* e) {
  fireNavIndex((int)(intptr_t)lv_event_get_user_data(e));
}

void uiShellSwipePage(int direction) {
  if (direction == 0) return;
  int idx = uiShellNavIndex(s_navPage);
  if (idx < 0) return;
  idx += (direction < 0) ? 1 : -1;
  fireNavIndex(idx);
}

void uiShellCreate(UiShellWidgets& w, UiPage page, bool showNav, uint8_t rotation) {
  uiShellDestroy(w);
  s_navPage = page;
  const ThemePalette& t = themeActive();
  const lv_coord_t sw = (lv_coord_t)scrW(rotation);
  const lv_coord_t sh = (lv_coord_t)scrH(rotation);

  w.root = lv_obj_create(NULL);
  lv_obj_remove_style_all(w.root);
  lv_obj_add_style(w.root, &uiStyleScreen, 0);
  lv_obj_set_size(w.root, sw, sh);
  lv_obj_clear_flag(w.root, LV_OBJ_FLAG_SCROLLABLE);

  w.header = lv_obj_create(w.root);
  lv_obj_remove_style_all(w.header);
  lv_obj_add_style(w.header, &uiStyleHeader, 0);
  lv_obj_set_size(w.header, sw, 24);
  lv_obj_align(w.header, LV_ALIGN_TOP_MID, 0, 0);
  lv_obj_clear_flag(w.header, LV_OBJ_FLAG_SCROLLABLE);

  w.alertDot = lv_obj_create(w.header);
  lv_obj_remove_style_all(w.alertDot);
  lv_obj_set_size(w.alertDot, 6, 6);
  lv_obj_set_style_radius(w.alertDot, LV_RADIUS_CIRCLE, 0);
  lv_obj_set_style_bg_color(w.alertDot, uiColor565(t.danger), 0);
  lv_obj_set_style_bg_opa(w.alertDot, LV_OPA_COVER, 0);
  lv_obj_align(w.alertDot, LV_ALIGN_LEFT_MID, 2, 0);
  lv_obj_add_flag(w.alertDot, LV_OBJ_FLAG_HIDDEN);

  w.titleLbl = uiMakeLabel(w.header, "", uiFontBody(), uiColor565(t.text));
  lv_obj_align(w.titleLbl, LV_ALIGN_LEFT_MID, 10, 0);

  w.weatherDot = lv_obj_create(w.header);
  lv_obj_remove_style_all(w.weatherDot);
  lv_obj_set_size(w.weatherDot, 7, 7);
  lv_obj_set_style_radius(w.weatherDot, LV_RADIUS_CIRCLE, 0);
  lv_obj_set_style_bg_opa(w.weatherDot, LV_OPA_COVER, 0);
  lv_obj_add_flag(w.weatherDot, LV_OBJ_FLAG_HIDDEN);

  w.rightLbl = uiMakeLabel(w.header, "", uiFontBody(), uiColor565(t.muted));
  lv_obj_align(w.rightLbl, LV_ALIGN_RIGHT_MID, 0, 0);

  const lv_coord_t contentH = showNav ? (lv_coord_t)(navY(rotation) - 24) : (lv_coord_t)(sh - 24);
  w.content = lv_obj_create(w.root);
  lv_obj_remove_style_all(w.content);
  lv_obj_set_size(w.content, sw, contentH);
  lv_obj_align(w.content, LV_ALIGN_TOP_MID, 0, 24);
  lv_obj_set_style_bg_color(w.content, uiColor565(t.bg), 0);
  lv_obj_set_style_bg_opa(w.content, LV_OPA_COVER, 0);
  lv_obj_set_style_pad_all(w.content, 4, 0);
  lv_obj_set_style_pad_row(w.content, 2, 0);
  lv_obj_set_flex_flow(w.content, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_flex_align(w.content, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START);
  lv_obj_clear_flag(w.content, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_clear_flag(w.content, LV_OBJ_FLAG_OVERFLOW_VISIBLE);

  if (showNav) {
    w.nav = lv_obj_create(w.root);
    lv_obj_remove_style_all(w.nav);
    lv_obj_set_size(w.nav, sw, UI_NAV_H);
    lv_obj_align(w.nav, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_color(w.nav, uiColor565(t.card), 0);
    lv_obj_set_style_bg_opa(w.nav, LV_OPA_COVER, 0);
    lv_obj_set_style_border_side(w.nav, LV_BORDER_SIDE_TOP, 0);
    lv_obj_set_style_border_color(w.nav, uiColor565(t.line), 0);
    lv_obj_set_style_border_width(w.nav, 1, 0);
    lv_obj_set_flex_flow(w.nav, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(w.nav, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_all(w.nav, 2, 0);
    lv_obj_clear_flag(w.nav, LV_OBJ_FLAG_SCROLLABLE);

    static const char* labels[] = {"Home", "BMS", "Hist", "Set"};
    const int activeIdx = uiShellNavIndex(page);
    const lv_coord_t btnW = (sw - 8) / 4;
    for (int i = 0; i < 4; i++) {
      lv_obj_t* btn = lv_btn_create(w.nav);
      lv_obj_remove_style_all(btn);
      lv_obj_add_style(btn, &uiStyleNavBtn, 0);
      lv_obj_set_style_bg_opa(btn, LV_OPA_TRANSP, 0);
      lv_obj_set_size(btn, btnW, UI_NAV_H - 4);
      lv_obj_clear_flag(btn, LV_OBJ_FLAG_SCROLLABLE);
      lv_obj_add_event_cb(btn, navClicked, LV_EVENT_CLICKED, (void*)(intptr_t)i);
      lv_obj_t* lbl = uiMakeLabel(btn, labels[i], uiFontBody(), uiColor565(t.dim));
      lv_obj_center(lbl);
      uiMakeNonClickable(lbl);
      w.navBtns[i] = btn;

      w.navDots[i] = lv_obj_create(btn);
      lv_obj_remove_style_all(w.navDots[i]);
      lv_obj_set_size(w.navDots[i], 4, 4);
      lv_obj_set_style_radius(w.navDots[i], LV_RADIUS_CIRCLE, 0);
      lv_obj_set_style_bg_opa(w.navDots[i], LV_OPA_COVER, 0);
      lv_obj_align(w.navDots[i], LV_ALIGN_TOP_MID, 0, 1);
      lv_obj_add_flag(w.navDots[i], LV_OBJ_FLAG_HIDDEN);
      uiMakeNonClickable(w.navDots[i]);

      styleNavBtn(w, i, i == activeIdx);
    }
    lv_obj_move_foreground(w.nav);
  }

  lv_obj_t* prev = lv_scr_act();
  lv_scr_load(w.root);
  // Delete previous screen only after new one is active.
  // Splash has its own lifetime — abandon tracking, don't double-del via uiSplashDismiss.
  if (prev && prev != w.root) {
    if (uiSplashOwns(prev)) {
      uiSplashAbandon();
      lv_obj_del(prev);
    } else {
      lv_obj_del(prev);
    }
  }
}

void uiShellDestroy(UiShellWidgets& w) {
  if (!w.root) return;
  lv_obj_t* root = w.root;
  w = UiShellWidgets();
  if (lv_scr_act() == root) {
    lv_obj_t* blank = lv_obj_create(NULL);
    lv_obj_remove_style_all(blank);
    lv_obj_set_style_bg_color(blank, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(blank, LV_OPA_COVER, 0);
    lv_coord_t hor = lv_disp_get_hor_res(nullptr);
    lv_coord_t ver = lv_disp_get_ver_res(nullptr);
    lv_obj_set_size(blank, hor, ver);
    lv_scr_load(blank);
  }
  lv_obj_del(root);
}

void uiShellSetPage(UiShellWidgets& w, UiPage page) {
  s_navPage = page;
  if (!w.nav) return;
  const int activeIdx = uiShellNavIndex(page);
  for (int i = 0; i < 4; i++) {
    styleNavBtn(w, i, i == activeIdx);
  }
}

void uiShellSetHeader(UiShellWidgets& w, const String& left, const String& right) {
  uiSetLabelText(w.titleLbl, uiTruncate(left, 16));
  uiSetLabelText(w.rightLbl, right);
  if (w.weatherDot) lv_obj_add_flag(w.weatherDot, LV_OBJ_FLAG_HIDDEN);
  if (w.alertDot) lv_obj_add_flag(w.alertDot, LV_OBJ_FLAG_HIDDEN);
}

void uiShellClearContent(UiShellWidgets& w) {
  if (!w.content) return;
  lv_obj_clean(w.content);
}
