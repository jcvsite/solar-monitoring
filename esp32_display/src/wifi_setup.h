#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <vector>

struct WifiNetwork {
  String ssid;
  int32_t rssi;
  bool secure;
};

bool wifiScanNetworks(std::vector<WifiNetwork>& out, int maxNetworks = 16);
bool wifiConnectAndSave(const char* ssid, const char* password, uint32_t timeoutMs = 20000);
