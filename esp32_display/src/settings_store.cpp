#include "settings_store.h"
#include "config.h"

static uint8_t clampU8(uint8_t v, uint8_t lo, uint8_t hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

void SettingsStore::begin() { prefs_.begin("solar_disp", false); }

HostSettings SettingsStore::load() {
  HostSettings s;
  s.hostIp = prefs_.getString("host", "");
  if (s.hostIp.length() == 0) s.hostIp = DEFAULT_HOST_IP;
  s.hostPort = prefs_.getUShort("port", DEFAULT_HOST_PORT);
  s.token = prefs_.getString("token", DEFAULT_API_TOKEN);
  s.pollMs = prefs_.getUInt("poll", DEFAULT_POLL_MS);
  s.brightness = clampU8(prefs_.getUChar("bri", 200), 0, 255);
  s.screenRotation = clampU8(prefs_.getUChar("rot", 0), 0, 3);
  s.glanceLayout = clampU8(prefs_.getUChar("glLayout", 0), 0, 4);
  s.themeId = clampU8(prefs_.getUChar("theme", 0), 0, 4);
  s.useHostConfig = prefs_.getBool("useHostCfg", true);
  s.gridOfflineAlert = prefs_.getBool("gridAlert", true);
  s.checkForUpdate = prefs_.getBool("chkUpd", false);
  s.autoInstallUpdate = prefs_.getBool("autoUpd", false);
  s.configRev = prefs_.getUInt("cfgRev", 0);
  s.settingsPin = prefs_.getString("setPin", "");
  if (s.settingsPin.length() != 4) s.settingsPin = "";
  if (s.hostPort == 0) s.hostPort = DEFAULT_HOST_PORT;
  if (s.pollMs < 2000) s.pollMs = 2000;
  if (s.autoInstallUpdate) s.checkForUpdate = true;
  return s;
}

void SettingsStore::save(const HostSettings& s) {
  prefs_.putString("host", s.hostIp);
  prefs_.putUShort("port", s.hostPort);
  prefs_.putString("token", s.token);
  prefs_.putUInt("poll", s.pollMs);
  prefs_.putUChar("bri", s.brightness);
  prefs_.putUChar("rot", s.screenRotation);
  prefs_.putUChar("glLayout", s.glanceLayout);
  prefs_.putUChar("theme", s.themeId);
  prefs_.putBool("useHostCfg", s.useHostConfig);
  prefs_.putBool("gridAlert", s.gridOfflineAlert);
  prefs_.putBool("chkUpd", s.checkForUpdate);
  prefs_.putBool("autoUpd", s.autoInstallUpdate);
  prefs_.putUInt("cfgRev", s.configRev);
  prefs_.putString("setPin", s.settingsPin.length() == 4 ? s.settingsPin : "");
}
