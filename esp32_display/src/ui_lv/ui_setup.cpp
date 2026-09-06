#include "ui_setup.h"
#include "ui_actions.h"
#include "ui_theme.h"
#include "ui_util.h"
#include <stdio.h>

static lv_obj_t* s_screen = nullptr;
static bool s_pickTheme = false;

static void setupAction(lv_event_t* e) {
  uiActionsFire((UiActionId)(intptr_t)lv_event_get_user_data(e), UiActionCtx());
}

static void pickItem(lv_event_t* e) {
  UiActionCtx ctx;
  ctx.index = (int)(intptr_t)lv_event_get_user_data(e);
  uiActionsFire(s_pickTheme ? UiActionId::PickTheme : UiActionId::PickLayout, ctx);
}

static void octetSelect(lv_event_t* e) {
  UiActionCtx ctx;
  ctx.index = (int)(intptr_t)lv_event_get_user_data(e);
  uiActionsFire(UiActionId::ManualOctetSelect, ctx);
}

static void clearScreen() {
  if (s_screen) lv_obj_del(s_screen);
  s_screen = nullptr;
}

void uiSetupHostChoice(const String& wifiSsid) {
  clearScreen();
  const ThemePalette& t = themeActive();
  s_screen = lv_obj_create(NULL);
  lv_obj_add_style(s_screen, &uiStyleScreen, 0);
  lv_obj_set_size(s_screen, LV_HOR_RES, LV_VER_RES);
  uiMakeLabel(s_screen, "Find solar-monitoring host", uiFontTitle(), uiColor565(t.text));
  lv_obj_align(lv_obj_get_child(s_screen, 0), LV_ALIGN_TOP_MID, 0, 20);
  uiMakeLabel(s_screen, ("WiFi: " + wifiSsid).c_str(), uiFontBody(), uiColor565(t.muted));
  lv_obj_align(lv_obj_get_child(s_screen, 1), LV_ALIGN_TOP_MID, 0, 44);

  lv_obj_t* b1 = lv_btn_create(s_screen);
  lv_obj_set_size(b1, LV_PCT(90), 40);
  lv_obj_align(b1, LV_ALIGN_CENTER, 0, -20);
  lv_obj_add_event_cb(b1, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::HostChoiceDiscover);
  uiMakeLabel(b1, "Auto discover", uiFontBody(), uiColor565(t.text));

  lv_obj_t* b2 = lv_btn_create(s_screen);
  lv_obj_set_size(b2, LV_PCT(90), 40);
  lv_obj_align(b2, LV_ALIGN_CENTER, 0, 30);
  lv_obj_add_event_cb(b2, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::HostChoiceManual);
  uiMakeLabel(b2, "Enter IP manually", uiFontBody(), uiColor565(t.text));
  lv_scr_load(s_screen);
}

void uiSetupFindingHost(const String& status) {
  clearScreen();
  const ThemePalette& t = themeActive();
  s_screen = lv_obj_create(NULL);
  lv_obj_add_style(s_screen, &uiStyleScreen, 0);
  lv_obj_set_size(s_screen, LV_HOR_RES, LV_VER_RES);
  uiMakeLabel(s_screen, "Searching LAN...", uiFontTitle(), uiColor565(t.text));
  lv_obj_align(lv_obj_get_child(s_screen, 0), LV_ALIGN_CENTER, 0, -20);
  uiMakeLabel(s_screen, status.c_str(), uiFontBody(), uiColor565(t.muted));
  lv_obj_align(lv_obj_get_child(s_screen, 1), LV_ALIGN_CENTER, 0, 10);
  lv_obj_t* b = lv_btn_create(s_screen);
  lv_obj_add_event_cb(b, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::FindingHostCancel);
  uiMakeLabel(b, "Cancel", uiFontBody(), uiColor565(t.text));
  lv_obj_align(b, LV_ALIGN_BOTTOM_MID, 0, -20);
  lv_scr_load(s_screen);
}

void uiSetupManualHost(const uint8_t octets[4], uint8_t selectedOctet, uint16_t port, const String& status) {
  clearScreen();
  const ThemePalette& t = themeActive();
  s_screen = lv_obj_create(NULL);
  lv_obj_add_style(s_screen, &uiStyleScreen, 0);
  lv_obj_set_size(s_screen, LV_HOR_RES, LV_VER_RES);
  lv_obj_set_flex_flow(s_screen, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_style_pad_all(s_screen, 8, 0);

  char ipBuf[20];
  snprintf(ipBuf, sizeof(ipBuf), "%u.%u.%u.%u", octets[0], octets[1], octets[2], octets[3]);
  uiMakeLabel(s_screen, "Manual host IP", uiFontTitle(), uiColor565(t.text));
  uiMakeLabel(s_screen, ipBuf, uiFontDisplay(), uiColor565(t.text));

  lv_obj_t* row = lv_obj_create(s_screen);
  lv_obj_remove_style_all(row);
  lv_obj_set_size(row, LV_PCT(100), 36);
  lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
  for (int i = 0; i < 4; i++) {
    char ob[8];
    snprintf(ob, sizeof(ob), "%u", octets[i]);
    lv_obj_t* btn = lv_btn_create(row);
    lv_obj_add_event_cb(btn, octetSelect, LV_EVENT_CLICKED, (void*)(intptr_t)i);
    if ((uint8_t)i == selectedOctet) lv_obj_add_state(btn, LV_STATE_CHECKED);
    uiMakeLabel(btn, ob, uiFontBody(), uiColor565(t.text));
  }

  char portBuf[24];
  snprintf(portBuf, sizeof(portBuf), "Port: %u", port);
  uiMakeLabel(s_screen, portBuf, uiFontBody(), uiColor565(t.text));

  lv_obj_t* ctl = lv_obj_create(s_screen);
  lv_obj_remove_style_all(ctl);
  lv_obj_set_size(ctl, LV_PCT(100), 36);
  lv_obj_set_flex_flow(ctl, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(ctl, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_t* dec = lv_btn_create(ctl);
  lv_obj_add_event_cb(dec, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::ManualOctetDec);
  uiMakeLabel(dec, "-", uiFontTitle(), uiColor565(t.text));
  lv_obj_t* inc = lv_btn_create(ctl);
  lv_obj_add_event_cb(inc, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::ManualOctetInc);
  uiMakeLabel(inc, "+", uiFontTitle(), uiColor565(t.text));
  lv_obj_t* pdec = lv_btn_create(ctl);
  lv_obj_add_event_cb(pdec, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::ManualPortDec);
  uiMakeLabel(pdec, "Port-", uiFontBody(), uiColor565(t.text));
  lv_obj_t* pinc = lv_btn_create(ctl);
  lv_obj_add_event_cb(pinc, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::ManualPortInc);
  uiMakeLabel(pinc, "Port+", uiFontBody(), uiColor565(t.text));

  uiMakeLabel(s_screen, status.c_str(), uiFontBody(), uiColor565(t.warn));

  lv_obj_t* acts = lv_obj_create(s_screen);
  lv_obj_remove_style_all(acts);
  lv_obj_set_size(acts, LV_PCT(100), 36);
  lv_obj_set_flex_flow(acts, LV_FLEX_FLOW_ROW);
  lv_obj_t* test = lv_btn_create(acts);
  lv_obj_add_event_cb(test, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::ManualTest);
  uiMakeLabel(test, "Test", uiFontBody(), uiColor565(t.text));
  lv_obj_t* save = lv_btn_create(acts);
  lv_obj_add_event_cb(save, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::ManualSave);
  uiMakeLabel(save, "Save", uiFontBody(), uiColor565(t.text));
  lv_obj_t* back = lv_btn_create(acts);
  lv_obj_add_event_cb(back, setupAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::ManualBack);
  uiMakeLabel(back, "Back", uiFontBody(), uiColor565(t.text));
  lv_scr_load(s_screen);
}

void uiSetupPickList(const char* title, const char* const* names, int count, int selected, bool isTheme) {
  s_pickTheme = isTheme;
  clearScreen();
  const ThemePalette& t = themeActive();
  s_screen = lv_obj_create(NULL);
  lv_obj_add_style(s_screen, &uiStyleScreen, 0);
  lv_obj_set_size(s_screen, LV_HOR_RES, LV_VER_RES);
  lv_obj_clear_flag(s_screen, LV_OBJ_FLAG_SCROLLABLE);

  uiMakeLabel(s_screen, title, uiFontTitle(), uiColor565(t.text));
  lv_obj_align(lv_obj_get_child(s_screen, 0), LV_ALIGN_TOP_MID, 0, 6);

  // Custom rows instead of lv_list + CHECKED (CHECKED drew a broken "x"/glyph with our fonts).
  lv_obj_t* list = lv_obj_create(s_screen);
  lv_obj_remove_style_all(list);
  lv_obj_set_size(list, LV_PCT(94), LV_PCT(78));
  lv_obj_align(list, LV_ALIGN_BOTTOM_MID, 0, -4);
  lv_obj_set_style_bg_color(list, uiColor565(t.bg), 0);
  lv_obj_set_style_bg_opa(list, LV_OPA_COVER, 0);
  lv_obj_set_flex_flow(list, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_style_pad_row(list, 4, 0);
  lv_obj_set_style_pad_all(list, 4, 0);
  lv_obj_add_flag(list, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(list, LV_SCROLLBAR_MODE_AUTO);
  lv_obj_set_scroll_dir(list, LV_DIR_VER);

  for (int i = 0; i < count; i++) {
    const bool on = (i == selected);
    lv_obj_t* btn = lv_btn_create(list);
    lv_obj_remove_style_all(btn);
    lv_obj_set_width(btn, LV_PCT(100));
    lv_obj_set_height(btn, 36);
    lv_obj_set_style_radius(btn, 8, 0);
    lv_obj_set_style_bg_opa(btn, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(btn, uiColor565(on ? t.panel : t.card), 0);
    lv_obj_set_style_border_width(btn, on ? 2 : 1, 0);
    lv_obj_set_style_border_color(btn, uiColor565(on ? t.charge : t.line), 0);
    lv_obj_set_style_pad_hor(btn, 10, 0);
    lv_obj_add_event_cb(btn, pickItem, LV_EVENT_CLICKED, (void*)(intptr_t)i);

    lv_obj_t* row = lv_obj_create(btn);
    lv_obj_remove_style_all(row);
    lv_obj_set_size(row, LV_PCT(100), LV_PCT(100));
    lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(row, 8, 0);
    lv_obj_clear_flag(row, LV_OBJ_FLAG_CLICKABLE);

    // Plain ASCII marker — no LVGL symbol font required.
    uiMakeLabel(row, on ? "[*]" : "[ ]", uiFontBody(), uiColor565(on ? t.charge : t.muted));
    uiMakeLabel(row, names[i], uiFontBody(), uiColor565(t.text));
  }
  lv_scr_load(s_screen);
}
