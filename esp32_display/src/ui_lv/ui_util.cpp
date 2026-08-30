#include "ui_util.h"
#include "ui_theme.h"
#include <math.h>
#include <stdio.h>

String uiFmtPower(float w) {
  if (isnan(w)) return String("--");
  const float a = fabsf(w);
  char buf[16];
  if (a >= 1000.0f) {
    snprintf(buf, sizeof(buf), "%.1f kW", a / 1000.0f);
  } else {
    snprintf(buf, sizeof(buf), "%.0f W", a);
  }
  return String(buf);
}

String uiFmtKwh(float k) {
  if (isnan(k)) return String("--");
  char buf[16];
  snprintf(buf, sizeof(buf), "%.1f", k);
  return String(buf);
}

String uiFmtTemp(float c, char unit) {
  if (isnan(c)) return String("--");
  char buf[16];
  if (unit == 'F') {
    snprintf(buf, sizeof(buf), "%.0f F", c * 9.0f / 5.0f + 32.0f);
  } else {
    snprintf(buf, sizeof(buf), "%.0f C", c);
  }
  return String(buf);
}

String uiTruncate(const String& s, size_t maxLen) {
  if ((size_t)s.length() <= maxLen) return s;
  if (maxLen <= 1) return s.substring(0, maxLen);
  return s.substring(0, maxLen - 1) + ".";
}

lv_obj_t* uiMakeCard(lv_obj_t* parent, lv_coord_t w, lv_coord_t h) {
  lv_obj_t* card = lv_obj_create(parent);
  lv_obj_remove_style_all(card);
  lv_obj_add_style(card, &uiStyleCard, 0);
  lv_obj_set_size(card, w, h);
  lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
  return card;
}

lv_obj_t* uiMakeLabel(lv_obj_t* parent, const char* text, const lv_font_t* font, lv_color_t color) {
  lv_obj_t* lbl = lv_label_create(parent);
  lv_label_set_text(lbl, text ? text : "");
  lv_obj_set_style_text_font(lbl, font, 0);
  lv_obj_set_style_text_color(lbl, color, 0);
  return lbl;
}

void uiSetLabelText(lv_obj_t* label, const char* text) {
  if (label) lv_label_set_text(label, text ? text : "");
}

void uiSetLabelText(lv_obj_t* label, const String& text) {
  uiSetLabelText(label, text.c_str());
}
