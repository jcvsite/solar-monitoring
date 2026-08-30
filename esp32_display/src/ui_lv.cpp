#include "ui_lv.h"
#include "ui_lv/ui_splash.h"
#include "ui_lv/ui_setup.h"
#include "ui_lv/ui_theme.h"
#include "ui_lv/ui_logo.h"
#include "lvgl_port.h"
#include "layout.h"

void UiLv::begin(TFT_eSPI& tft, uint8_t rotation) {
  rotation_ = rotation & 3;
  lvglPortInit(tft, rotation_);
  uiThemeInitOnce();
}

void UiLv::setRotation(uint8_t rotation) {
  rotation_ = rotation & 3;
  lvglPortSetRotation(rotation_);
  if (shellActive_) showPage(currentPage_);
}

void UiLv::setTheme(uint8_t themeId) {
  uiThemeApply(themeId);
  if (shellActive_) showPage(currentPage_);
}

void UiLv::tick() { lvglPortTick(); }

void UiLv::ensureClock() { uiClockEnsure(); }
void UiLv::syncClockTimezone(int offsetSec) { uiClockSyncTimezone(offsetSec); }

void UiLv::showSplash(const char* msg) {
  shellActive_ = false;
  uiShellDestroy(shell_);
  uiWifiDestroy(wifi_);
  uiPinDestroy(pin_);
  uiSplashShow(msg);
}

void UiLv::setSplashMsg(const char* msg) { uiSplashSetMsg(msg); }

void UiLv::showWifiPortal(const char* apName) {
  shellActive_ = false;
  uiShellDestroy(shell_);
  uiWifiBuildPortal(wifi_, apName);
}

void UiLv::rebuildIfNeeded(UiPage page) {
  currentPage_ = page;
  const bool mainNav = page == UiPage::Glance || page == UiPage::Bms || page == UiPage::History || page == UiPage::Settings;
  if (!shellActive_ || !shell_.root) {
    uiWifiDestroy(wifi_);
    uiPinDestroy(pin_);
    uiShellCreate(shell_, page, mainNav, rotation_);
    uiSplashDismiss();
    uiLogoRelease();
    shellActive_ = true;
    if (page == UiPage::Glance) uiGlanceBuild(shell_, glance_, glanceLayout_);
    else if (page == UiPage::Bms) uiBmsBuild(shell_, bms_);
    else if (page == UiPage::History) uiHistoryBuild(shell_, history_);
    else if (page == UiPage::Settings) { /* built in updateSettings */ }
  } else {
    uiShellSetPage(shell_, page);
    if (page == UiPage::Glance) uiGlanceBuild(shell_, glance_, glanceLayout_);
    else if (page == UiPage::Bms) uiBmsBuild(shell_, bms_);
    else if (page == UiPage::History) uiHistoryBuild(shell_, history_);
  }
}

void UiLv::showPage(UiPage page) {
  if (page == UiPage::WifiPick || page == UiPage::WifiPassword || page == UiPage::PinUnlock || page == UiPage::PinSet ||
      page == UiPage::HostChoice || page == UiPage::FindingHost || page == UiPage::ManualHost || page == UiPage::PickLayout ||
      page == UiPage::PickTheme) {
    currentPage_ = page;
    return;
  }
  rebuildIfNeeded(page);
}

void UiLv::refreshHeaderTime(const GlanceData& g) {
  if (shell_.root) {
    uiShellSetPage(shell_, UiPage::Glance);
    uiShellSetGlanceHeader(shell_, g);
  }
}

void UiLv::updateGlance(const GlanceData& g, bool stale, bool gridAlert, uint8_t layoutId) {
  glanceLayout_ = layoutId;
  showPage(UiPage::Glance);
  if (!shell_.root) return;
  if (uiGlanceNeedsBuild(glance_, layoutId)) uiGlanceBuild(shell_, glance_, layoutId);
  uiShellSetPage(shell_, UiPage::Glance);
  uiShellSetGlanceHeader(shell_, g);
  uiGlanceUpdate(glance_, g, stale, gridAlert, layoutId);
}

void UiLv::pulseGlanceGrid(bool gridAlert, uint32_t animMs) {
  uiGlancePulseGrid(glance_, gridAlert, animMs);
}

void UiLv::animateGlanceBattery(const GlanceData& g, uint32_t animMs) {
  uiGlanceAnimateBattery(glance_, g, animMs);
}

void UiLv::updateBms(const BmsData& b) {
  showPage(UiPage::Bms);
  if (!shell_.root) return;
  uiShellSetPage(shell_, UiPage::Bms);
  uiShellSetHeader(shell_, LV_SYMBOL_BATTERY_FULL " Battery", b.ok ? "BMS" : "N/A");
  uiBmsUpdate(bms_, b);
}

void UiLv::updateHistory(const HistoryData& h) {
  showPage(UiPage::History);
  if (!shell_.root) return;
  uiShellSetPage(shell_, UiPage::History);
  uiShellSetHeader(shell_, LV_SYMBOL_LIST " History", String(h.hours) + "h");
  uiHistoryUpdate(history_, h);
}

void UiLv::updateSettings(const HostSettings& s, bool wifiOk, const String& wifiSsid, const String& statusMsg,
                          const String& otaStatus, UiSettingsTab tab, const char* fwVersion) {
  showPage(UiPage::Settings);
  if (!shell_.root) return;
  uiShellSetPage(shell_, UiPage::Settings);
  uiShellSetHeader(shell_, LV_SYMBOL_SETTINGS " Settings", wifiOk ? "Connected" : "Offline");
  uiSettingsBuild(shell_, settings_, tab, s, wifiOk, wifiSsid, statusMsg, otaStatus, fwVersion);
}

void UiLv::showPickList(const char* title, const char* const* names, int count, int selected, bool isTheme) {
  (void)isTheme;
  shellActive_ = false;
  uiShellDestroy(shell_);
  uiSetupPickList(title, names, count, selected, isTheme);
}

void UiLv::showHostChoice(const String& wifiSsid) {
  shellActive_ = false;
  uiShellDestroy(shell_);
  uiSetupHostChoice(wifiSsid);
}

void UiLv::showFindingHost(const String& status) {
  shellActive_ = false;
  uiShellDestroy(shell_);
  uiSetupFindingHost(status);
}

void UiLv::showManualHost(const uint8_t octets[4], uint8_t selectedOctet, uint16_t port, const String& status) {
  shellActive_ = false;
  uiShellDestroy(shell_);
  uiSetupManualHost(octets, selectedOctet, port, status);
}

void UiLv::showWifiNetworks(const std::vector<WifiNetwork>& nets, int selected, const String& status) {
  shellActive_ = false;
  uiShellDestroy(shell_);
  uiWifiBuildList(wifi_, nets, selected, status);
}

void UiLv::showWifiPassword(const String& ssid, const String& password, bool showPass, const String& status) {
  uiWifiBuildPassword(wifi_, ssid, password, showPass, status);
}

void UiLv::showPinPad(const char* title, const String& entry, const String& subtitle, const String& status) {
  shellActive_ = false;
  uiShellDestroy(shell_);
  uiPinBuild(pin_, title, entry, subtitle, status);
}

void UiLv::updatePinPad(const String& entry, const String& status) {
  uiPinUpdate(pin_, entry, status);
}

String UiLv::getWifiPasswordInput() const {
  if (wifi_.ta) return String(lv_textarea_get_text(wifi_.ta));
  return String("");
}
