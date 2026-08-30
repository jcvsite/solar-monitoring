#include "wifi_setup.h"

bool wifiScanNetworks(std::vector<WifiNetwork>& out, int maxNetworks) {
  out.clear();
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(false, false);
  delay(100);
  int n = WiFi.scanNetworks(false, true);
  if (n <= 0) return false;

  for (int i = 0; i < n && (int)out.size() < maxNetworks; i++) {
    String ssid = WiFi.SSID(i);
    if (ssid.length() == 0) continue;
    bool dup = false;
    for (const auto& existing : out) {
      if (existing.ssid == ssid) {
        dup = true;
        break;
      }
    }
    if (dup) continue;
    WifiNetwork net;
    net.ssid = ssid;
    net.rssi = WiFi.RSSI(i);
    net.secure = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
    out.push_back(net);
  }
  WiFi.scanDelete();
  return !out.empty();
}

bool wifiConnectAndSave(const char* ssid, const char* password, uint32_t timeoutMs) {
  if (!ssid || !ssid[0]) return false;
  WiFi.mode(WIFI_STA);
  WiFi.persistent(true);
  WiFi.setAutoReconnect(true);
  WiFi.disconnect(false, false);
  delay(100);
  WiFi.begin(ssid, password);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < timeoutMs) {
    delay(200);
  }
  return WiFi.status() == WL_CONNECTED;
}
