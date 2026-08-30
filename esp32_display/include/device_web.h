#pragma once
#include <Arduino.h>
#include "settings_store.h"

extern bool gDeviceWebSaved;

class DeviceWeb {
 public:
  void begin();
  void loop();
  void applySettings(const HostSettings& s);
  const HostSettings& settings() const { return settings_; }

 private:
  void handleRoot();
  void handleSave();
  void handleUnlock();
  String htmlPage() const;
  String htmlPinGate() const;
  HostSettings settings_;
  bool started_ = false;
};

extern DeviceWeb deviceWeb;
