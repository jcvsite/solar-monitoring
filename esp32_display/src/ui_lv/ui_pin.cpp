#include "ui_pin.h"
#include "ui_actions.h"
#include "ui_theme.h"
#include "ui_util.h"

static const char* kPinMap[] = {"1", "2", "3", "\n", "4", "5", "6", "\n", "7", "8", "9", "\n", "Del", "0", "OK", ""};

static void pinBtnEvent(lv_event_t* e) {
  UiActionCtx ctx;
  const uint32_t id = lv_btnmatrix_get_selected_btn(lv_event_get_target(e));
  const char* txt = lv_btnmatrix_get_btn_text(lv_event_get_target(e), id);
  if (!txt) return;
  if (strcmp(txt, "Del") == 0) {
    uiActionsFire(UiActionId::PinDelete, ctx);
  } else if (strcmp(txt, "OK") == 0) {
    uiActionsFire(UiActionId::PinOk, ctx);
  } else if (strlen(txt) == 1 && txt[0] >= '0' && txt[0] <= '9') {
    ctx.digit = txt[0] - '0';
    uiActionsFire(UiActionId::PinDigit, ctx);
  }
}

static void pinBackEvent(lv_event_t* e) {
  (void)e;
  uiActionsFire(UiActionId::PinBack, UiActionCtx());
}

void uiPinDestroy(UiPinWidgets& p) {
  if (p.screen) lv_obj_del(p.screen);
  p = UiPinWidgets();
}

void uiPinBuild(UiPinWidgets& p, const char* title, const String& entry, const String& subtitle,
                const String& status) {
  uiPinDestroy(p);
  const ThemePalette& t = themeActive();
  p.screen = lv_obj_create(NULL);
  lv_obj_remove_style_all(p.screen);
  lv_obj_add_style(p.screen, &uiStyleScreen, 0);
  lv_obj_set_size(p.screen, LV_HOR_RES, LV_VER_RES);

  uiMakeLabel(p.screen, title, uiFontTitle(), uiColor565(t.text));
  lv_obj_align(lv_obj_get_child(p.screen, 0), LV_ALIGN_TOP_MID, 0, 8);
  uiMakeLabel(p.screen, subtitle.c_str(), uiFontBody(), uiColor565(t.muted));
  lv_obj_align(lv_obj_get_child(p.screen, 1), LV_ALIGN_TOP_MID, 0, 28);

  p.entryLbl = uiMakeLabel(p.screen, entry.c_str(), uiFontDisplay(), uiColor565(t.text));
  lv_obj_align(p.entryLbl, LV_ALIGN_TOP_MID, 0, 52);

  lv_obj_t* pad = lv_btnmatrix_create(p.screen);
  lv_btnmatrix_set_map(pad, kPinMap);
  lv_obj_set_size(pad, LV_PCT(90), 140);
  lv_obj_align(pad, LV_ALIGN_CENTER, 0, 20);
  lv_obj_add_event_cb(pad, pinBtnEvent, LV_EVENT_VALUE_CHANGED, NULL);

  p.statusLbl = uiMakeLabel(p.screen, status.c_str(), uiFontBody(), uiColor565(t.warn));
  lv_obj_align(p.statusLbl, LV_ALIGN_BOTTOM_MID, 0, -36);

  lv_obj_t* back = lv_btn_create(p.screen);
  lv_obj_add_event_cb(back, pinBackEvent, LV_EVENT_CLICKED, NULL);
  uiMakeLabel(back, "Back", uiFontBody(), uiColor565(t.text));
  lv_obj_align(back, LV_ALIGN_BOTTOM_MID, 0, -6);
  lv_scr_load(p.screen);
}

void uiPinUpdate(UiPinWidgets& p, const String& entry, const String& status) {
  uiSetLabelText(p.entryLbl, entry);
  uiSetLabelText(p.statusLbl, status);
}
