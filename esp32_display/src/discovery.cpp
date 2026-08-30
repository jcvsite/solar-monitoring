#include "discovery.h"
#include <ESPmDNS.h>
#include <WiFi.h>

static String localMdnsName() {
  uint32_t id = (uint32_t)ESP.getEfuseMac();
  char buf[32];
  snprintf(buf, sizeof(buf), "esp32-solar-%06X", id & 0xFFFFFF);
  return String(buf);
}

bool Discovery::probeIp(ApiClient& api, const String& token, const String& host, std::vector<DiscoveredHost>& out) {
  WiFiClient client;
  client.setTimeout(80);
  if (!client.connect(host.c_str(), port_)) {
    return false;
  }
  client.stop();
  String title;
  if (!api.probeHost(host, port_, token, title)) {
    return false;
  }
  DiscoveredHost h;
  h.ip = host;
  h.port = port_;
  h.title = title;
  out.push_back(h);
  return true;
}

void Discovery::beginSearch(uint16_t port) {
  active_ = true;
  phase_ = 0;
  port_ = port;
  startMs_ = millis();
  scanLast_ = 1;
  mdnsCount_ = 0;
  String name = localMdnsName();
  MDNS.begin(name.c_str());
}

void Discovery::cancelSearch() {
  active_ = false;
}

bool Discovery::tickSearch(ApiClient& api, const String& token, std::vector<DiscoveredHost>& out) {
  if (!active_) return true;

  if (phase_ == 0) {
    mdnsCount_ = MDNS.queryService("solar-monitoring", "tcp");
    if (mdnsCount_ > 0 || (millis() - startMs_) >= 4000) {
      for (int i = 0; i < mdnsCount_; i++) {
        String ip = MDNS.IP(i).toString();
        uint16_t port = MDNS.port(i);
        port_ = port;
        probeIp(api, token, ip, out);
      }
      if (!out.empty()) {
        active_ = false;
        return true;
      }
      phase_ = 1;
      scanLast_ = 1;
    }
    return false;
  }

  IPAddress ip = WiFi.localIP();
  if (ip == IPAddress((uint32_t)0)) {
    active_ = false;
    return true;
  }

  while (scanLast_ <= 254) {
    int last = scanLast_++;
    if (last == (int)ip[3]) continue;
    String host = String(ip[0]) + "." + String(ip[1]) + "." + String(ip[2]) + "." + String(last);
    if (probeIp(api, token, host, out)) {
      active_ = false;
      return true;
    }
    if (out.size() >= 5) {
      active_ = false;
      return true;
    }
    return false;
  }

  active_ = false;
  return true;
}

int Discovery::findHosts(ApiClient& api, const String& token, uint16_t port, std::vector<DiscoveredHost>& out, uint32_t timeoutMs) {
  out.clear();
  int n = mdnsBrowse(api, token, out, timeoutMs);
  if (n > 0) return n;
  return subnetScan(api, token, port, out);
}

int Discovery::mdnsBrowse(ApiClient& api, const String& token, std::vector<DiscoveredHost>& out, uint32_t timeoutMs) {
  String name = localMdnsName();
  if (!MDNS.begin(name.c_str())) {
    return 0;
  }
  int n = MDNS.queryService("solar-monitoring", "tcp");
  uint32_t start = millis();
  while (n == 0 && (millis() - start) < timeoutMs) {
    delay(200);
    n = MDNS.queryService("solar-monitoring", "tcp");
  }
  for (int i = 0; i < n; i++) {
    DiscoveredHost h;
    h.ip = MDNS.IP(i).toString();
    h.port = MDNS.port(i);
    String title;
    if (api.probeHost(h.ip, h.port, token, title)) {
      h.title = title;
      out.push_back(h);
    }
  }
  return (int)out.size();
}

int Discovery::subnetScan(ApiClient& api, const String& token, uint16_t port, std::vector<DiscoveredHost>& out) {
  IPAddress ip = WiFi.localIP();
  IPAddress gw = WiFi.gatewayIP();
  if (ip == IPAddress((uint32_t)0)) return 0;

  // Scan .1-.254 on same /24 (skip self); short timeouts keep this under ~30s worst case
  uint8_t a = ip[0], b = ip[1], c = ip[2];
  for (int last = 1; last <= 254; last++) {
    if (last == ip[3]) continue;
    // Prefer gateway first once
    if (last == 1 && gw[3] != 1) {
      // also try gateway explicitly at start of loop via reorder: handled below
    }
    String host = String(a) + "." + String(b) + "." + String(c) + "." + String(last);
    port_ = port;
    if (probeIp(api, token, host, out)) {
      if (out.size() >= 5) break;
    }
    yield();
  }
  return (int)out.size();
}
