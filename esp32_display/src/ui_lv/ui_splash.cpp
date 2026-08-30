#include "ui_splash.h"
#include "ui_logo.h"
#include "ui_theme.h"
#include "ui_util.h"

static lv_obj_t* s_splash = nullptr;
static lv_obj_t* s_msgLbl = nullptr;

void uiSplashShow(const char* msg) {
  uiLogoEnsureLoaded();
  if (s_splash) {
    uiSplashSetMsg(msg);
    return;
  }

  s_splash = lv_obj_create(NULL);
  lv_obj_remove_style_all(s_splash);
  lv_obj_set_style_bg_color(s_splash, lv_color_white(), 0);
  lv_obj_set_style_bg_opa(s_splash, LV_OPA_COVER, 0);
  lv_obj_set_size(s_splash, LV_HOR_RES, LV_VER_RES);
  lv_obj_clear_flag(s_splash, LV_OBJ_FLAG_SCROLLABLE);

  lv_obj_t* img = nullptr;
  const lv_img_dsc_t* logo = uiLogoDescriptor();
  if (logo) {
    img = lv_img_create(s_splash);
    lv_img_set_src(img, logo);
    lv_img_set_zoom(img, uiLogoSplashZoom());
    lv_obj_align(img, LV_ALIGN_TOP_MID, 0, 8);
  }

  lv_obj_t* title = uiMakeLabel(s_splash, "Solar Monitoring", uiFontTitle(), uiColor565(themeActive().text));
  if (img) lv_obj_align_to(title, img, LV_ALIGN_OUT_BOTTOM_MID, 0, 6);
  else lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 48);

  lv_obj_t* viewer = uiMakeLabel(s_splash, "Viewer", uiFontTitle(), uiColor565(themeActive().pv));
  lv_obj_align_to(viewer, title, LV_ALIGN_OUT_BOTTOM_MID, 0, 2);

  s_msgLbl = uiMakeLabel(s_splash, msg ? msg : "", uiFontBody(), uiColor565(themeActive().muted));
  lv_obj_align_to(s_msgLbl, viewer, LV_ALIGN_OUT_BOTTOM_MID, 0, 6);

  lv_scr_load(s_splash);
  lv_obj_invalidate(s_splash);
}

void uiSplashSetMsg(const char* msg) {
  if (s_msgLbl) uiSetLabelText(s_msgLbl, msg ? msg : "");
}

void uiSplashDismiss() {
  if (!s_splash) return;
  // Never delete the screen LVGL is still displaying.
  if (lv_scr_act() == s_splash) return;
  lv_obj_del(s_splash);
  s_splash = nullptr;
  s_msgLbl = nullptr;
}

bool uiSplashIsActive() {
  return s_splash && lv_scr_act() == s_splash;
}
