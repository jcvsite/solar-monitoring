#pragma once
#include <Arduino.h>
#include <Preferences.h>

struct HostSettings {
  String hostIp;
  uint16_t hostPort = 8081;
  String token;
  uint32_t pollMs = 5000;
  uint8_t brightness = 200;
  uint8_t screenRotation = 0;  // 0-3 TFT_eSPI rotation
  uint8_t glanceLayout = 0;    // 0-4
  uint8_t themeId = 0;         // 0-4
  bool useHostConfig = true;
  bool gridOfflineAlert = true;
  bool checkForUpdate = false;
  bool autoInstallUpdate = false;
  uint32_t configRev = 0;
  String settingsPin;  // "" = off, else 4 digits
};

class SettingsStore {
 public:
  void begin();
  HostSettings load();
  void save(const HostSettings& s);

 private:
  Preferences prefs_;
};
