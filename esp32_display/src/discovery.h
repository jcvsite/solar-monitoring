#pragma once
#include <Arduino.h>
#include <vector>
#include "api_client.h"

struct DiscoveredHost {
  String ip;
  uint16_t port = 8081;
  String title;
};

class Discovery {
 public:
  // Prefer mDNS, then subnet scan of /api/display (blocking)
  int findHosts(ApiClient& api, const String& token, uint16_t port, std::vector<DiscoveredHost>& out, uint32_t timeoutMs = 8000);

  // Non-blocking search — call tickSearch() from loop(); cancel with cancelSearch()
  void beginSearch(uint16_t port);
  bool tickSearch(ApiClient& api, const String& token, std::vector<DiscoveredHost>& out);
  void cancelSearch();
  bool isSearching() const { return active_; }

 private:
  bool active_ = false;
  uint8_t phase_ = 0;
  uint16_t port_ = 8081;
  uint32_t startMs_ = 0;
  int scanLast_ = 1;
  int mdnsCount_ = 0;

  int mdnsBrowse(ApiClient& api, const String& token, std::vector<DiscoveredHost>& out, uint32_t timeoutMs);
  int subnetScan(ApiClient& api, const String& token, uint16_t port, std::vector<DiscoveredHost>& out);
  bool probeIp(ApiClient& api, const String& token, const String& host, std::vector<DiscoveredHost>& out);
};
