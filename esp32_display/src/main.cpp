#include <Arduino.h>
#include <math.h>
#include <time.h>
#include <vector>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <SPI.h>

#include "config.h"
#include "secrets.h"
#include "settings_store.h"
#include "api_client.h"
#include "discovery.h"
#include "touch_input.h"
#include "ui.h"
#include "ui_lv.h"
#include "ui_lv/ui_actions.h"
#include "lvgl_port.h"
#include "theme.h"
#include "layout.h"
#include "git_ota.h"
#include "device_web.h"
#include "wifi_setup.h"

#ifndef FW_VERSION
#define FW_VERSION "0.0.0"
#endif

TFT_eSPI tft;

SettingsStore store;
ApiClient api;
Discovery discovery;
UiLv ui;

HostSettings settings;
GlanceData glance;
BmsData bms;
HistoryData history;

UiPage page = UiPage::Glance;
UiSettingsTab settingsTab = UiSettingsTab::Connection;
uint32_t lastPoll = 0;
uint32_t lastConfigPoll = 0;
uint32_t lastGood = 0;
uint32_t lastAnim = 0;
String statusMsg = "Boot";
String otaStatus = "Ready";
bool needRedraw = true;
std::vector<DiscoveredHost> found;
int foundIndex = 0;
uint8_t manualOctets[4] = {192, 168, 1, 240};
uint8_t manualSel = 0;

std::vector<WifiNetwork> wifiNets;
int wifiScroll = 0;
int wifiSelected = 0;
String wifiPickSsid;
String wifiPassword;
bool wifiShowPass = false;
bool wifiShift = false;
String wifiStatus;

bool settingsPinUnlocked = false;
String pinEntry;
String pinStatus;
String pinSetFirst;
uint8_t pinSetPhase = 0;
UiPage pinReturnPage = UiPage::Glance;

static const char* kLayoutNames[] = {"Classic", "Compact", "Ring", "Bars", "Flow"};
static const char* kThemeNames[] = {"Dark", "Light", "Solar", "Ocean", "Forest"};

static void pollIfDue(bool force);
static void pollDisplayConfig(bool force);
static bool glanceGridAlert(const GlanceData& g);

static const char* rotationLabel(uint8_t r);
static void refreshCurrentPage();
static void handleUiAction(UiActionId id, const UiActionCtx& ctx);
static void openSettingsPage();
static void applyScreenRotation();
static void startHostDiscovery();
static void openManualHost();
static void startWifiScan();
static bool ensureWifi(bool forcePortal);
static bool connectPickedWifi(const String& ssid, const String& pass);
static void showHostChoice();
static String manualOctetsToIp();
static void handlePinPadCommon(bool forSet);

static const char* rotationLabel(uint8_t r) {
  switch (r & 3) {
    case 1:
      return "Landscape";
    case 2:
      return "Portrait flip";
    case 3:
      return "Landscape flip";
    default:
      return "Portrait";
  }
}

static void refreshCurrentPage() {
  const bool stale = (lastGood == 0) || (millis() - lastGood > STALE_MS);
  switch (page) {
    case UiPage::Glance:
      ui.updateGlance(glance, stale, glanceGridAlert(glance), settings.glanceLayout);
      break;
    case UiPage::Bms:
      ui.updateBms(bms);
      break;
    case UiPage::History:
      ui.updateHistory(history);
      break;
    case UiPage::Settings:
    case UiPage::SettingsConn:
    case UiPage::SettingsUpdates:
      ui.updateSettings(settings, WiFi.status() == WL_CONNECTED, WiFi.SSID(),
                        settingsTab == UiSettingsTab::Updates ? otaStatus : statusMsg, otaStatus, settingsTab,
                        FW_VERSION);
      break;
    case UiPage::PickLayout:
      ui.showPickList("Layout", kLayoutNames, 5, settings.glanceLayout, false);
      break;
    case UiPage::PickTheme:
      ui.showPickList("Theme", kThemeNames, 5, settings.themeId, true);
      break;
    case UiPage::FindingHost:
      ui.showFindingHost(statusMsg);
      break;
    case UiPage::HostChoice:
      ui.showHostChoice(WiFi.SSID());
      break;
    case UiPage::ManualHost:
      ui.showManualHost(manualOctets, manualSel, settings.hostPort, statusMsg);
      break;
    case UiPage::WifiPick:
      ui.showWifiNetworks(wifiNets, wifiSelected, wifiStatus);
      break;
    case UiPage::WifiPassword:
      ui.showWifiPassword(wifiPickSsid, wifiPassword, wifiShowPass, wifiStatus);
      break;
    case UiPage::PinUnlock:
      ui.showPinPad("Settings locked", pinEntry, "Enter 4-digit PIN", pinStatus);
      break;
    case UiPage::PinSet:
      ui.showPinPad("Settings PIN", pinEntry, pinSetPhase ? "Confirm PIN" : "New PIN (4 digits)", pinStatus);
      break;
    default:
      break;
  }
}

static void handleUiAction(UiActionId id, const UiActionCtx& ctx) {
  switch (id) {
    case UiActionId::NavPage:
      settingsPinUnlocked = false;
      page = ctx.page;
      settingsTab = UiSettingsTab::Connection;
      pollIfDue(true);
      needRedraw = true;
      break;
    case UiActionId::OpenSettings:
      openSettingsPage();
      break;
    case UiActionId::PickLayout:
      settings.glanceLayout = (uint8_t)ctx.index;
      store.save(settings);
      page = UiPage::Settings;
      needRedraw = true;
      break;
    case UiActionId::PickTheme:
      settings.themeId = (uint8_t)ctx.index;
      ui.setTheme(settings.themeId);
      store.save(settings);
      page = UiPage::Settings;
      needRedraw = true;
      break;
    case UiActionId::RotateScreen:
      settings.screenRotation = (settings.screenRotation + 1) & 3;
      store.save(settings);
      applyScreenRotation();
      statusMsg = rotationLabel(settings.screenRotation);
      needRedraw = true;
      break;
    case UiActionId::OpenPinSet:
      page = UiPage::PinSet;
      pinSetPhase = 0;
      pinSetFirst = "";
      pinEntry = "";
      pinStatus = "New PIN (4 digits)";
      needRedraw = true;
      break;
    case UiActionId::StartHostDiscovery:
      startHostDiscovery();
      break;
    case UiActionId::OpenManualHost:
      openManualHost();
      break;
    case UiActionId::StartWifiScan:
      page = UiPage::WifiPick;
      startWifiScan();
      break;
    case UiActionId::WifiRescan:
      startWifiScan();
      break;
    case UiActionId::WifiPhonePortal:
      statusMsg = "Opening phone portal...";
      needRedraw = true;
      if (ensureWifi(true)) {
        statusMsg = "WiFi OK " + WiFi.localIP().toString();
        page = UiPage::Settings;
      } else {
        statusMsg = "Portal cancelled";
      }
      needRedraw = true;
      break;
    case UiActionId::WifiPickNetwork:
      if (ctx.index >= 0 && ctx.index < (int)wifiNets.size()) {
        wifiSelected = ctx.index;
        wifiPickSsid = wifiNets[ctx.index].ssid;
        if (!wifiNets[ctx.index].secure) {
          if (connectPickedWifi(wifiPickSsid, "")) {
            statusMsg = wifiStatus;
            page = settings.hostIp.length() ? UiPage::Glance : UiPage::HostChoice;
          } else {
            page = UiPage::WifiPick;
          }
        } else {
          wifiPassword = "";
          wifiShowPass = false;
          wifiStatus = "Enter password";
          page = UiPage::WifiPassword;
        }
        needRedraw = true;
      }
      break;
    case UiActionId::WifiConnect: {
      wifiPassword = ui.getWifiPasswordInput();
      if (connectPickedWifi(wifiPickSsid, wifiPassword)) {
        statusMsg = wifiStatus;
        page = settings.hostIp.length() ? UiPage::Glance : UiPage::HostChoice;
      } else {
        page = UiPage::WifiPassword;
      }
      needRedraw = true;
      break;
    }
    case UiActionId::WifiBack:
      if (page == UiPage::WifiPassword) {
        page = UiPage::WifiPick;
        wifiStatus = "Tap your network";
      } else {
        page = UiPage::Settings;
        statusMsg = wifiStatus;
      }
      needRedraw = true;
      break;
    case UiActionId::HostChoiceDiscover:
      startHostDiscovery();
      break;
    case UiActionId::HostChoiceManual:
      openManualHost();
      break;
    case UiActionId::FindingHostCancel:
      showHostChoice();
      break;
    case UiActionId::ManualOctetSelect:
      manualSel = (uint8_t)ctx.index;
      needRedraw = true;
      break;
    case UiActionId::ManualOctetDec:
      manualOctets[manualSel] = (manualOctets[manualSel] == 0) ? 255 : manualOctets[manualSel] - 1;
      needRedraw = true;
      break;
    case UiActionId::ManualOctetInc:
      manualOctets[manualSel] = (manualOctets[manualSel] == 255) ? 0 : manualOctets[manualSel] + 1;
      needRedraw = true;
      break;
    case UiActionId::ManualPortDec:
      if (settings.hostPort > 1) settings.hostPort--;
      needRedraw = true;
      break;
    case UiActionId::ManualPortInc:
      if (settings.hostPort < 65535) settings.hostPort++;
      needRedraw = true;
      break;
    case UiActionId::ManualTest: {
      const String ip = manualOctetsToIp();
      statusMsg = "Testing...";
      needRedraw = true;
      String title;
      if (api.probeHost(ip, settings.hostPort, settings.token, title)) {
        statusMsg = title.length() ? title : "Host OK";
      } else {
        statusMsg = "Not reachable";
      }
      needRedraw = true;
      break;
    }
    case UiActionId::ManualSave:
      settings.hostIp = manualOctetsToIp();
      store.save(settings);
      deviceWeb.applySettings(settings);
      statusMsg = "Saved";
      page = UiPage::Glance;
      pollIfDue(true);
      needRedraw = true;
      break;
    case UiActionId::ManualBack:
      page = settings.hostIp.length() ? UiPage::Settings : UiPage::HostChoice;
      statusMsg = "";
      needRedraw = true;
      break;
    case UiActionId::ToggleCheckUpdate:
      settings.checkForUpdate = !settings.checkForUpdate;
      if (!settings.checkForUpdate) settings.autoInstallUpdate = false;
      store.save(settings);
      gitOta.configure(settings.hostIp, settings.hostPort, settings.token, settings.checkForUpdate,
                       settings.autoInstallUpdate);
      needRedraw = true;
      break;
    case UiActionId::ToggleAutoUpdate:
      settings.autoInstallUpdate = !settings.autoInstallUpdate;
      if (settings.autoInstallUpdate) settings.checkForUpdate = true;
      store.save(settings);
      gitOta.configure(settings.hostIp, settings.hostPort, settings.token, settings.checkForUpdate,
                       settings.autoInstallUpdate);
      needRedraw = true;
      break;
    case UiActionId::ToggleGridAlert:
      settings.gridOfflineAlert = !settings.gridOfflineAlert;
      store.save(settings);
      needRedraw = true;
      break;
    case UiActionId::ToggleUseHostConfig:
      settings.useHostConfig = !settings.useHostConfig;
      store.save(settings);
      if (settings.useHostConfig) pollDisplayConfig(true);
      needRedraw = true;
      break;
    case UiActionId::OtaCheckNow: {
      String st;
      gitOta.installLatest(st);
      otaStatus = st;
      needRedraw = true;
      break;
    }
    case UiActionId::PinDigit:
      if (pinEntry.length() < 4) {
        pinEntry += String(ctx.digit);
        if (page == UiPage::PinUnlock || page == UiPage::PinSet) ui.updatePinPad(pinEntry, pinStatus);
        if (pinEntry.length() == 4 && page == UiPage::PinUnlock) handlePinPadCommon(false);
      }
      break;
    case UiActionId::PinDelete:
      if (pinEntry.length()) pinEntry.remove(pinEntry.length() - 1);
      ui.updatePinPad(pinEntry, pinStatus);
      break;
    case UiActionId::PinOk:
      handlePinPadCommon(page == UiPage::PinSet);
      needRedraw = true;
      break;
    case UiActionId::PinBack:
      pinEntry = "";
      page = (page == UiPage::PinSet) ? UiPage::Settings : UiPage::Glance;
      needRedraw = true;
      break;
    default:
      break;
  }
}

static void startWifiScan() {
  wifiStatus = "Scanning...";
  needRedraw = true;
  ui.showWifiNetworks(wifiNets, wifiSelected, wifiStatus);
  if (wifiScanNetworks(wifiNets)) {
    wifiScroll = 0;
    wifiSelected = 0;
    wifiStatus = "Tap your network";
  } else {
    wifiNets.clear();
    wifiStatus = "No networks — tap Rescan";
  }
  needRedraw = true;
}

static bool connectPickedWifi(const String& ssid, const String& pass) {
  wifiStatus = "Connecting...";
  needRedraw = true;
  ui.setSplashMsg(wifiStatus.c_str());
  ui.tick();
  if (!wifiConnectAndSave(ssid.c_str(), pass.c_str())) {
    wifiStatus = "Failed — check password";
    return false;
  }
  wifiStatus = "Connected " + WiFi.localIP().toString();
  deviceWeb.applySettings(settings);
  deviceWeb.begin();
  ui.ensureClock();
  return true;
}

static bool nearEq(float a, float b) {
  if (isnan(a) && isnan(b)) return true;
  if (isnan(a) || isnan(b)) return false;
  return fabsf(a - b) < 1.0f;
}

static bool glanceVisualEqual(const GlanceData& a, const GlanceData& b) {
  return a.title == b.title && a.grid_state == b.grid_state && a.batt_status == b.batt_status &&
         a.batt_time == b.batt_time && a.status == b.status && nearEq(a.soc, b.soc) &&
         nearEq(a.batt_w, b.batt_w) && nearEq(a.pv_w, b.pv_w) && nearEq(a.load_w, b.load_w) &&
         nearEq(a.grid_w, b.grid_w) && nearEq(a.pv_today_kwh, b.pv_today_kwh) &&
         nearEq(a.load_today_kwh, b.load_today_kwh);
}

static bool glanceGridAlert(const GlanceData& g) {
  if (!settings.gridOfflineAlert) return false;
  return g.grid_state == "offline" || g.grid_state == "brownout";
}

static void loadManualOctetsFromSettings() {
  if (settings.hostIp.length()) {
    int start = 0;
    for (int i = 0; i < 4; i++) {
      int dot = settings.hostIp.indexOf('.', start);
      String part = (dot >= 0) ? settings.hostIp.substring(start, dot) : settings.hostIp.substring(start);
      manualOctets[i] = (uint8_t)constrain(part.toInt(), 0, 255);
      if (dot < 0) break;
      start = dot + 1;
    }
  } else {
    IPAddress lip = WiFi.localIP();
    manualOctets[0] = 192;
    manualOctets[1] = 168;
    manualOctets[2] = 1;
    manualOctets[3] = 240;
    if (lip != IPAddress((uint32_t)0)) {
      manualOctets[0] = lip[0];
      manualOctets[1] = lip[1];
      manualOctets[2] = lip[2];
    }
  }
}

static String manualOctetsToIp() {
  char buf[16];
  snprintf(buf, sizeof(buf), "%u.%u.%u.%u", manualOctets[0], manualOctets[1], manualOctets[2], manualOctets[3]);
  return String(buf);
}

static void showHostChoice() {
  discovery.cancelSearch();
  page = UiPage::HostChoice;
  statusMsg = "";
  needRedraw = true;
}

static void openManualHost() {
  discovery.cancelSearch();
  loadManualOctetsFromSettings();
  manualSel = 0;
  page = UiPage::ManualHost;
  statusMsg = "Tap octet, use +/-";
  needRedraw = true;
}

static void startHostDiscovery() {
  found.clear();
  discovery.cancelSearch();
  discovery.beginSearch(settings.hostPort);
  page = UiPage::FindingHost;
  statusMsg = "Searching...";
  needRedraw = true;
}

static void finishHostDiscovery() {
  if (!found.empty()) {
    foundIndex = 0;
    settings.hostIp = found[0].ip;
    settings.hostPort = found[0].port;
    store.save(settings);
    statusMsg = "Found " + settings.hostIp;
    page = UiPage::Glance;
    pollIfDue(true);
  } else {
    statusMsg = "Not found";
    showHostChoice();
  }
  needRedraw = true;
}

static const char* kApNameBase = WIFI_SETUP_AP_NAME;

static String uniqueApName() {
  uint32_t id = (uint32_t)ESP.getEfuseMac();
  char buf[40];
  snprintf(buf, sizeof(buf), "%s-%04X", kApNameBase, (unsigned)(id & 0xFFFF));
  return String(buf);
}

static String uniqueHostname() {
  uint32_t id = (uint32_t)ESP.getEfuseMac();
  char buf[32];
  snprintf(buf, sizeof(buf), "esp32-solar-%06X", (unsigned)(id & 0xFFFFFF));
  return String(buf);
}

static void setBrightness(uint8_t v) {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(TFT_BL, 5000, 8);
  ledcWrite(TFT_BL, v);
#else
  ledcSetup(0, 5000, 8);
  ledcAttachPin(TFT_BL, 0);
  ledcWrite(0, v);
#endif
}

static void applyScreenRotation() {
  settings.screenRotation = (uint8_t)constrain(settings.screenRotation, (int)0, (int)3);
  tft.setRotation(settings.screenRotation);
  touchInputSetRotation(settings.screenRotation);
  ui.setRotation(settings.screenRotation);
}

static String gPortalApName;

static void configModeCallback(WiFiManager* wm) {
  (void)wm;
  ui.showWifiPortal(gPortalApName.c_str());
}

static bool ensureWifi(bool forcePortal) {
  WiFi.mode(WIFI_STA);
  gPortalApName = uniqueApName();
  String hostname = uniqueHostname();

  String seedSsid = WIFI_SSID;
  String seedPass = WIFI_PASSWORD;
  bool seedOk = seedSsid.length() > 0 && seedSsid != "YourWiFiSSID";

  WiFiManager wm;
  wm.setDebugOutput(false);
  wm.setConfigPortalTimeout(300);
  wm.setConnectTimeout(30);
  wm.setAPCallback(configModeCallback);
  wm.setTitle("Solar Display WiFi");
  wm.setHostname(hostname.c_str());
  wm.setCustomHeadElement(
      "<meta name='viewport' content='width=device-width,initial-scale=1'>"
      "<style>"
      "body{font-family:system-ui,sans-serif;background:#111;color:#eee;padding:12px;max-width:420px;margin:auto}"
      "input,select{font-size:18px;padding:12px;width:100%;box-sizing:border-box;margin:8px 0;"
      "border-radius:8px;border:1px solid #444;background:#1c1c1e;color:#fff}"
      "button,.btn{font-size:18px;padding:12px 16px;border-radius:8px;border:0;background:#0a84ff;color:#fff;"
      "width:100%;margin-top:12px;cursor:pointer}"
      "h1{font-size:1.35rem} label{font-weight:600;display:block;margin-top:10px}"
      ".msg{padding:10px;border-radius:8px;background:#1c1c1e;margin:10px 0}"
      "</style>");

  if (forcePortal) {
    ui.showWifiPortal(gPortalApName.c_str());
    bool ok = wm.startConfigPortal(gPortalApName.c_str());
    return ok && WiFi.status() == WL_CONNECTED;
  }

  ui.setSplashMsg("WiFi...");
  ui.tick();
  bool ok = false;
  if (seedOk) {
    ok = wm.autoConnect(gPortalApName.c_str(), NULL);
    if (!ok) {
      WiFi.begin(seedSsid.c_str(), seedPass.c_str());
      uint32_t t0 = millis();
      while (WiFi.status() != WL_CONNECTED && millis() - t0 < 12000) {
        lvglPortTick();
        delay(20);
      }
      ok = WiFi.status() == WL_CONNECTED;
      if (!ok) {
        ui.showWifiPortal(gPortalApName.c_str());
        ok = wm.startConfigPortal(gPortalApName.c_str());
      }
    }
  } else {
    ok = wm.autoConnect(gPortalApName.c_str());
  }
  return ok && WiFi.status() == WL_CONNECTED;
}

static bool pinIsSet() { return settings.settingsPin.length() == 4; }

static void openSettingsPage() {
  if (pinIsSet() && !settingsPinUnlocked) {
    page = UiPage::PinUnlock;
    pinEntry = "";
    pinStatus = "Enter PIN";
    pinReturnPage = UiPage::Settings;
    needRedraw = true;
    return;
  }
  page = UiPage::Settings;
  settingsTab = UiSettingsTab::Connection;
  settingsPinUnlocked = true;
  pollIfDue(true);
  needRedraw = true;
}

static void handlePinPadCommon(bool forSet) {
  if (forSet) {
    if (pinEntry.length() == 0) {
      settings.settingsPin = "";
      store.save(settings);
      deviceWeb.applySettings(settings);
      pinSetPhase = 0;
      pinSetFirst = "";
      pinStatus = "PIN disabled";
      page = UiPage::Settings;
      needRedraw = true;
      return;
    }
    if (pinEntry.length() != 4) return;
    if (pinSetPhase == 0) {
      pinSetFirst = pinEntry;
      pinEntry = "";
      pinSetPhase = 1;
      pinStatus = "Confirm PIN";
      needRedraw = true;
      return;
    }
    if (pinEntry != pinSetFirst) {
      pinEntry = "";
      pinSetPhase = 0;
      pinSetFirst = "";
      pinStatus = "No match — retry";
      needRedraw = true;
      return;
    }
    settings.settingsPin = pinEntry;
    store.save(settings);
    deviceWeb.applySettings(settings);
    pinEntry = "";
    pinSetPhase = 0;
    pinSetFirst = "";
    pinStatus = "PIN saved";
    page = UiPage::Settings;
    needRedraw = true;
    return;
  }
  if (pinEntry.length() != 4) return;
  if (pinEntry == settings.settingsPin) {
    settingsPinUnlocked = true;
    pinEntry = "";
    page = pinReturnPage;
    pinStatus = "";
    needRedraw = true;
  } else {
    pinEntry = "";
    pinStatus = "Wrong PIN";
    needRedraw = true;
  }
}

static void applyHostSettingsFromConfig(const DisplayConfig& cfg) {
  bool changed = false;
  if (cfg.config_rev > settings.configRev) {
    settings.configRev = cfg.config_rev;
    changed = true;
  }
  if (settings.glanceLayout != cfg.glance_layout) {
    settings.glanceLayout = cfg.glance_layout;
    changed = true;
  }
  if (settings.themeId != cfg.theme) {
    settings.themeId = cfg.theme;
    ui.setTheme(settings.themeId);
    changed = true;
  }
  if (settings.screenRotation != cfg.rotation) {
    settings.screenRotation = cfg.rotation;
    applyScreenRotation();
    changed = true;
  }
  if (settings.brightness != cfg.brightness) {
    settings.brightness = cfg.brightness;
    setBrightness(settings.brightness);
    changed = true;
  }
  if (settings.pollMs != cfg.poll_ms) {
    settings.pollMs = cfg.poll_ms;
    changed = true;
  }
  if (settings.checkForUpdate != cfg.check_for_update) {
    settings.checkForUpdate = cfg.check_for_update;
    changed = true;
  }
  if (settings.autoInstallUpdate != cfg.auto_install_update) {
    settings.autoInstallUpdate = cfg.auto_install_update;
    changed = true;
  }
  if (settings.gridOfflineAlert != cfg.grid_offline_alert) {
    settings.gridOfflineAlert = cfg.grid_offline_alert;
    changed = true;
  }
  if (settings.useHostConfig && cfg.settings_pin != settings.settingsPin) {
    settings.settingsPin = cfg.settings_pin;
    changed = true;
  }
  gitOta.configure(settings.hostIp, settings.hostPort, settings.token, settings.checkForUpdate,
                   settings.autoInstallUpdate);
  if (changed) {
    store.save(settings);
    deviceWeb.applySettings(settings);
    needRedraw = true;
  }
  if (cfg.force_update) {
    String st;
    gitOta.installLatest(st);
    otaStatus = st;
  }
}

static void pollDisplayConfig(bool force) {
  if (!settings.useHostConfig) return;
  if (!force && millis() - lastConfigPoll < 30000) return;
  lastConfigPoll = millis();
  if (settings.hostIp.length() == 0 || WiFi.status() != WL_CONNECTED) return;
  DisplayConfig cfg;
  if (api.fetchDisplayConfig(settings.hostIp, settings.hostPort, settings.token, cfg)) {
    applyHostSettingsFromConfig(cfg);
  }
}

static void pollIfDue(bool force) {
  if (!force && millis() - lastPoll < settings.pollMs) return;
  lastPoll = millis();
  if (settings.hostIp.length() == 0 || WiFi.status() != WL_CONNECTED) return;

  if (page == UiPage::Glance || force) {
    GlanceData g;
    if (api.fetchGlance(settings.hostIp, settings.hostPort, settings.token, g)) {
      if (g.tz_offset_sec >= -43200 && g.tz_offset_sec <= 50400) {
        ui.syncClockTimezone(g.tz_offset_sec);
      }
      bool headerChanged = (g.clock != glance.clock) || (g.weather_enabled != glance.weather_enabled) ||
                           (g.weather_code != glance.weather_code) || (g.weather_temp != glance.weather_temp);
      if (force || !glanceVisualEqual(glance, g)) {
        glance = g;
        needRedraw = true;
      } else {
        glance = g;
        if (page == UiPage::Glance && headerChanged) {
          ui.refreshHeaderTime(glance);
        }
      }
      lastGood = millis();
    }
  }
  if (page == UiPage::Bms) {
    BmsData b;
    if (api.fetchBms(settings.hostIp, settings.hostPort, settings.token, b)) {
      bms = b;
      lastGood = millis();
      needRedraw = true;
    }
  }
  if (page == UiPage::History) {
    HistoryData h;
    if (api.fetchHistory(settings.hostIp, settings.hostPort, settings.token, 24, h)) {
      history = h;
      lastGood = millis();
      needRedraw = true;
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  store.begin();
  settings = store.load();

  themeSetActive(settings.themeId);
  touchInputBegin();

  tft.init();
  applyScreenRotation();
  setBrightness(settings.brightness);
  ui.begin(tft, settings.screenRotation);
  ui.setTheme(settings.themeId);
  uiActionsSetHandler(handleUiAction);
  ui.showSplash("Starting...");
  ui.tick();

  gitOta.begin();
  gitOta.configure(settings.hostIp, settings.hostPort, settings.token, settings.checkForUpdate,
                   settings.autoInstallUpdate);

  if (ensureWifi(false)) {
    ui.setSplashMsg(WiFi.localIP().toString().c_str());
    ui.tick();
    deviceWeb.applySettings(settings);
    deviceWeb.begin();
    ui.ensureClock();
    {
      struct tm ti;
      uint32_t t0 = millis();
      while (millis() - t0 < 3000) {
        lvglPortTick();
        if (getLocalTime(&ti)) break;
        delay(20);
      }
    }
    delay(400);
  } else {
    page = UiPage::WifiPick;
    startWifiScan();
    delay(400);
  }

  if (page != UiPage::WifiPick && page != UiPage::WifiPassword) {
    page = UiPage::Glance;
    statusMsg = settings.hostIp;
  }

  pollDisplayConfig(true);
  pollIfDue(true);
  refreshCurrentPage();
  needRedraw = false;
}

void loop() {
  ui.tick();

  if (gDeviceWebSaved) {
    gDeviceWebSaved = false;
    settings = deviceWeb.settings();
    store.save(settings);
    applyScreenRotation();
    ui.setTheme(settings.themeId);
    setBrightness(settings.brightness);
    needRedraw = true;
  }

  deviceWeb.loop();
  gitOta.loop();
  otaStatus = gitOta.status();

  if (page == UiPage::FindingHost && discovery.isSearching()) {
    if (discovery.tickSearch(api, settings.token, found)) {
      finishHostDiscovery();
    }
  }

  static bool wasStale = false;
  const bool stale = (lastGood == 0) || (millis() - lastGood > STALE_MS);
  if (stale != wasStale) {
    wasStale = stale;
    needRedraw = true;
  }

  pollIfDue(false);
  pollDisplayConfig(false);

  static uint32_t lastClock = 0;
  if (page == UiPage::Glance && WiFi.status() == WL_CONNECTED && millis() - lastClock >= 30000) {
    lastClock = millis();
    ui.ensureClock();
    ui.refreshHeaderTime(glance);
  }

  if (page == UiPage::Glance && glanceGridAlert(glance) && millis() - lastAnim >= 5000) {
    lastAnim = millis();
    ui.pulseGlanceGrid(true, millis());
  }

  static uint32_t lastBattAnim = 0;
  if (page == UiPage::Glance && millis() - lastBattAnim >= 120) {
    lastBattAnim = millis();
    ui.animateGlanceBattery(glance, millis());
  }

  if (needRedraw) {
    needRedraw = false;
    refreshCurrentPage();
  }

  delay(5);
}
