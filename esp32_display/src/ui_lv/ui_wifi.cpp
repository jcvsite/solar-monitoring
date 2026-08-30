#include "ui_wifi.h"
#include "ui_actions.h"
#include "ui_logo.h"
#include "ui_theme.h"
#include "ui_util.h"
#include <stdio.h>

static void wifiAction(lv_event_t* e) {
  uiActionsFire((UiActionId)(intptr_t)lv_event_get_user_data(e), UiActionCtx());
}

static void wifiNetClicked(lv_event_t* e) {
  UiActionCtx ctx;
  ctx.index = (int)(intptr_t)lv_event_get_user_data(e);
  uiActionsFire(UiActionId::WifiPickNetwork, ctx);
}

void uiWifiDestroy(UiWifiWidgets& w) {
  if (w.screen) lv_obj_del(w.screen);
  if (w.passScreen) lv_obj_del(w.passScreen);
  w = UiWifiWidgets();
}

void uiWifiBuildPortal(UiWifiWidgets& w, const char* apName) {
  uiWifiDestroy(w);
  uiLogoEnsureLoaded();
  const ThemePalette& t = themeActive();
  w.screen = lv_obj_create(NULL);
  lv_obj_remove_style_all(w.screen);
  lv_obj_add_style(w.screen, &uiStyleScreen, 0);
  lv_obj_set_size(w.screen, LV_HOR_RES, LV_VER_RES);

  const lv_img_dsc_t* logo = uiLogoDescriptor();
  lv_obj_t* img = nullptr;
  if (logo) {
    img = lv_img_create(w.screen);
    lv_img_set_src(img, logo);
    lv_img_set_zoom(img, uiLogoSplashZoom());
    lv_obj_align(img, LV_ALIGN_TOP_MID, 0, 8);
  }

  lv_obj_t* title = uiMakeLabel(w.screen, "Phone WiFi Setup", uiFontTitle(), uiColor565(t.text));
  if (img) lv_obj_align_to(title, img, LV_ALIGN_OUT_BOTTOM_MID, 0, 8);
  else lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 24);
  lv_obj_t* apLbl = uiMakeLabel(w.screen, apName, uiFontBody(), uiColor565(t.pv));
  lv_obj_align_to(apLbl, title, LV_ALIGN_OUT_BOTTOM_MID, 0, 4);
  lv_obj_t* hint = uiMakeLabel(w.screen, "Join AP, open 192.168.4.1", uiFontBody(), uiColor565(t.muted));
  lv_obj_align_to(hint, apLbl, LV_ALIGN_OUT_BOTTOM_MID, 0, 4);
  lv_scr_load(w.screen);
}

void uiWifiBuildList(UiWifiWidgets& w, const std::vector<WifiNetwork>& nets, int selected, const String& status) {
  uiWifiDestroy(w);
  const ThemePalette& t = themeActive();
  w.screen = lv_obj_create(NULL);
  lv_obj_remove_style_all(w.screen);
  lv_obj_add_style(w.screen, &uiStyleScreen, 0);
  lv_obj_set_size(w.screen, LV_HOR_RES, LV_VER_RES);
  lv_obj_set_flex_flow(w.screen, LV_FLEX_FLOW_COLUMN);
  lv_obj_set_style_pad_all(w.screen, 6, 0);

  w.statusLbl = uiMakeLabel(w.screen, status.c_str(), uiFontBody(), uiColor565(t.muted));
  w.list = lv_list_create(w.screen);
  lv_obj_set_width(w.list, LV_PCT(100));
  lv_obj_set_flex_grow(w.list, 1);

  for (size_t i = 0; i < nets.size(); i++) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%s %s %ddB", nets[i].ssid.c_str(), nets[i].secure ? "[sec]" : "",
             nets[i].rssi);
    lv_obj_t* btn = lv_list_add_btn(w.list, LV_SYMBOL_WIFI, buf);
    if ((int)i == selected) lv_obj_add_state(btn, LV_STATE_CHECKED);
    lv_obj_add_event_cb(btn, wifiNetClicked, LV_EVENT_CLICKED, (void*)(intptr_t)i);
  }

  lv_obj_t* row = lv_obj_create(w.screen);
  lv_obj_remove_style_all(row);
  lv_obj_set_size(row, LV_PCT(100), 36);
  lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(row, LV_FLEX_ALIGN_SPACE_EVENLY, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  lv_obj_t* b1 = lv_btn_create(row);
  lv_obj_add_event_cb(b1, wifiAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::WifiRescan);
  uiMakeLabel(b1, "Rescan", uiFontBody(), uiColor565(t.text));
  lv_obj_t* b2 = lv_btn_create(row);
  lv_obj_add_event_cb(b2, wifiAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::WifiPhonePortal);
  uiMakeLabel(b2, "Phone", uiFontBody(), uiColor565(t.text));
  lv_obj_t* b3 = lv_btn_create(row);
  lv_obj_add_event_cb(b3, wifiAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::WifiBack);
  uiMakeLabel(b3, "Back", uiFontBody(), uiColor565(t.text));
  lv_scr_load(w.screen);
}

static void passAction(lv_event_t* e) {
  uiActionsFire((UiActionId)(intptr_t)lv_event_get_user_data(e), UiActionCtx());
}

void uiWifiBuildPassword(UiWifiWidgets& w, const String& ssid, const String& password, bool showPass,
                         const String& status) {
  if (w.screen) {
    lv_obj_del(w.screen);
    w.screen = nullptr;
  }
  if (w.passScreen) lv_obj_del(w.passScreen);
  const ThemePalette& t = themeActive();
  w.passScreen = lv_obj_create(NULL);
  lv_obj_remove_style_all(w.passScreen);
  lv_obj_add_style(w.passScreen, &uiStyleScreen, 0);
  lv_obj_set_size(w.passScreen, LV_HOR_RES, LV_VER_RES);

  uiMakeLabel(w.passScreen, ssid.c_str(), uiFontTitle(), uiColor565(t.text));
  lv_obj_align(lv_obj_get_child(w.passScreen, 0), LV_ALIGN_TOP_MID, 0, 4);
  w.ta = lv_textarea_create(w.passScreen);
  lv_obj_set_width(w.ta, LV_PCT(95));
  lv_obj_align(w.ta, LV_ALIGN_TOP_MID, 0, 28);
  lv_textarea_set_one_line(w.ta, true);
  lv_textarea_set_password_mode(w.ta, !showPass);
  lv_textarea_set_text(w.ta, password.c_str());

  w.kb = lv_keyboard_create(w.passScreen);
  lv_keyboard_set_textarea(w.kb, w.ta);
  lv_obj_align(w.kb, LV_ALIGN_BOTTOM_MID, 0, -36);

  uiMakeLabel(w.passScreen, status.c_str(), uiFontBody(), uiColor565(t.muted));
  lv_obj_align(lv_obj_get_child(w.passScreen, 3), LV_ALIGN_BOTTOM_MID, 0, -4);

  lv_obj_t* row = lv_obj_create(w.passScreen);
  lv_obj_remove_style_all(row);
  lv_obj_set_size(row, LV_PCT(100), 32);
  lv_obj_align(row, LV_ALIGN_BOTTOM_MID, 0, -8);
  lv_obj_t* conn = lv_btn_create(row);
  lv_obj_add_event_cb(conn, passAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::WifiConnect);
  uiMakeLabel(conn, "Connect", uiFontBody(), uiColor565(t.text));
  lv_obj_align(conn, LV_ALIGN_LEFT_MID, 8, 0);
  lv_obj_t* back = lv_btn_create(row);
  lv_obj_add_event_cb(back, passAction, LV_EVENT_CLICKED, (void*)(intptr_t)UiActionId::WifiBack);
  uiMakeLabel(back, "Back", uiFontBody(), uiColor565(t.text));
  lv_obj_align(back, LV_ALIGN_RIGHT_MID, -8, 0);
  lv_scr_load(w.passScreen);
}
