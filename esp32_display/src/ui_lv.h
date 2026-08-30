#pragma once
#include <TFT_eSPI.h>
#include <vector>
#include "ui.h"
#include "api_client.h"
#include "settings_store.h"
#include "wifi_setup.h"
#include "ui_lv/ui_glance.h"
#include "ui_lv/ui_bms.h"
#include "ui_lv/ui_history.h"
#include "ui_lv/ui_settings.h"
#include "ui_lv/ui_wifi.h"
#include "ui_lv/ui_pin.h"
#include "ui_lv/ui_shell.h"

class UiLv {
 public:
  void begin(TFT_eSPI& tft, uint8_t rotation);
  void setRotation(uint8_t rotation);
  void setTheme(uint8_t themeId);
  void tick();

  void showPage(UiPage page);
  void showSplash(const char* msg);
  void setSplashMsg(const char* msg);
  void showWifiPortal(const char* apName);

  void updateGlance(const GlanceData& g, bool stale, bool gridAlert, uint8_t layoutId);
  void pulseGlanceGrid(bool gridAlert, uint32_t animMs);
  void animateGlanceBattery(const GlanceData& g, uint32_t animMs);
  void refreshHeaderTime(const GlanceData& g);
  void updateBms(const BmsData& b);
  void updateHistory(const HistoryData& h);
  void updateSettings(const HostSettings& s, bool wifiOk, const String& wifiSsid, const String& statusMsg,
                      const String& otaStatus, UiSettingsTab tab, const char* fwVersion);
  void showPickList(const char* title, const char* const* names, int count, int selected, bool isTheme);
  void showHostChoice(const String& wifiSsid);
  void showFindingHost(const String& status);
  void showManualHost(const uint8_t octets[4], uint8_t selectedOctet, uint16_t port, const String& status);
  void showWifiNetworks(const std::vector<WifiNetwork>& nets, int selected, const String& status);
  void showWifiPassword(const String& ssid, const String& password, bool showPass, const String& status);
  void showPinPad(const char* title, const String& entry, const String& subtitle, const String& status);
  void updatePinPad(const String& entry, const String& status);

  void ensureClock();
  void syncClockTimezone(int offsetSec);

  String getWifiPasswordInput() const;

 private:
  void rebuildIfNeeded(UiPage page);
  UiShellWidgets shell_;
  UiGlanceWidgets glance_;
  UiBmsWidgets bms_;
  UiHistoryWidgets history_;
  UiSettingsWidgets settings_;
  UiWifiWidgets wifi_;
  UiPinWidgets pin_;
  UiPage currentPage_ = UiPage::Glance;
  uint8_t rotation_ = 0;
  uint8_t glanceLayout_ = 0;
  bool shellActive_ = false;
};
