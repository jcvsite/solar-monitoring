#include "ui_theme.h"
#include <math.h>

lv_style_t uiStyleScreen;
lv_style_t uiStyleCard;
lv_style_t uiStyleHeader;
lv_style_t uiStyleMuted;
lv_style_t uiStyleNavBtn;
lv_style_t uiStyleNavBtnActive;
lv_style_t uiStyleAccent;

static const lv_font_t* s_fontBody = &lv_font_montserrat_16;
static const lv_font_t* s_fontTitle = &lv_font_montserrat_16;
static const lv_font_t* s_fontDisplay = &lv_font_montserrat_20;
static const lv_font_t* s_fontSoc = &lv_font_montserrat_48;

lv_color_t uiColor565(uint16_t c) {
  const uint8_t r = (uint8_t)(((c >> 11) & 0x1F) << 3);
  const uint8_t g = (uint8_t)(((c >> 5) & 0x3F) << 2);
  const uint8_t b = (uint8_t)((c & 0x1F) << 3);
  return lv_color_make(r, g, b);
}

const lv_font_t* uiFontBody() { return s_fontBody; }
const lv_font_t* uiFontTitle() { return s_fontTitle; }
const lv_font_t* uiFontDisplay() { return s_fontDisplay; }
const lv_font_t* uiFontSoc() { return s_fontSoc; }

static void initStyle(lv_style_t* st) {
  lv_style_init(st);
}

void uiThemeRefreshStyles() {
  const ThemePalette& t = themeActive();

  lv_style_set_bg_color(&uiStyleScreen, uiColor565(t.bg));
  lv_style_set_bg_opa(&uiStyleScreen, LV_OPA_COVER);
  lv_style_set_text_color(&uiStyleScreen, uiColor565(t.text));
  lv_style_set_border_width(&uiStyleScreen, 0);
  lv_style_set_pad_all(&uiStyleScreen, 0);

  lv_style_set_bg_color(&uiStyleCard, uiColor565(t.card));
  lv_style_set_bg_opa(&uiStyleCard, LV_OPA_COVER);
  lv_style_set_border_color(&uiStyleCard, uiColor565(t.line));
  lv_style_set_border_width(&uiStyleCard, 1);
  lv_style_set_radius(&uiStyleCard, 8);
  lv_style_set_pad_all(&uiStyleCard, 6);
  lv_style_set_text_color(&uiStyleCard, uiColor565(t.text));

  lv_style_set_bg_color(&uiStyleHeader, uiColor565(t.header));
  lv_style_set_bg_opa(&uiStyleHeader, LV_OPA_COVER);
  lv_style_set_text_color(&uiStyleHeader, uiColor565(t.text));
  lv_style_set_border_color(&uiStyleHeader, uiColor565(t.line));
  lv_style_set_border_width(&uiStyleHeader, 0);
  lv_style_set_border_side(&uiStyleHeader, LV_BORDER_SIDE_BOTTOM);
  lv_style_set_radius(&uiStyleHeader, 0);
  lv_style_set_pad_hor(&uiStyleHeader, 6);
  lv_style_set_pad_ver(&uiStyleHeader, 4);

  lv_style_set_text_color(&uiStyleMuted, uiColor565(t.muted));
  lv_style_set_text_font(&uiStyleMuted, s_fontBody);

  lv_style_set_bg_color(&uiStyleNavBtn, uiColor565(t.card));
  lv_style_set_text_color(&uiStyleNavBtn, uiColor565(t.dim));
  lv_style_set_border_width(&uiStyleNavBtn, 0);
  lv_style_set_radius(&uiStyleNavBtn, 6);
  lv_style_set_pad_all(&uiStyleNavBtn, 4);

  lv_style_set_bg_color(&uiStyleNavBtnActive, uiColor565(t.panel));
  lv_style_set_text_color(&uiStyleNavBtnActive, uiColor565(t.text));
  lv_style_set_border_width(&uiStyleNavBtnActive, 0);
  lv_style_set_radius(&uiStyleNavBtnActive, 6);
  lv_style_set_pad_all(&uiStyleNavBtnActive, 4);

  lv_style_set_bg_color(&uiStyleAccent, uiColor565(t.pv));
  lv_style_set_text_color(&uiStyleAccent, uiColor565(t.onAccent));
  lv_style_set_radius(&uiStyleAccent, 8);
  lv_style_set_pad_hor(&uiStyleAccent, 10);
  lv_style_set_pad_ver(&uiStyleAccent, 6);
}

void uiThemeApply(uint8_t themeId) {
  themeSetActive(themeId);
  uiThemeRefreshStyles();
}

lv_color_t uiSocColor(float soc) {
  const ThemePalette& t = themeActive();
  if (isnan(soc)) return uiColor565(t.muted);
  if (soc < 20) return uiColor565(t.danger);
  if (soc < 40) return uiColor565(t.warn);
  return uiColor565(t.charge);
}

void uiThemeInitOnce() {
  static bool done = false;
  if (done) return;
  done = true;
  initStyle(&uiStyleScreen);
  initStyle(&uiStyleCard);
  initStyle(&uiStyleHeader);
  initStyle(&uiStyleMuted);
  initStyle(&uiStyleNavBtn);
  initStyle(&uiStyleNavBtnActive);
  initStyle(&uiStyleAccent);
}
