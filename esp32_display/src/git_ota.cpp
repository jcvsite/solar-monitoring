#include "git_ota.h"
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <WiFi.h>
#include <ArduinoJson.h>

#ifndef FW_VERSION
#define FW_VERSION "0.0.0"
#endif

GitOta gitOta;

void GitOta::begin() { status_ = "Ready"; }

void GitOta::configure(const String& host, uint16_t port, const String& token, bool check, bool autoInstall) {
  host_ = host;
  port_ = port;
  token_ = token;
  check_ = check;
  autoInstall_ = autoInstall;
}

bool GitOta::checkUpdateInfo(UpdateInfo& out) {
  out = UpdateInfo();
  if (WiFi.status() != WL_CONNECTED || host_.length() == 0) return false;
  String url = "http://" + host_ + ":" + String(port_) + "/api/display/update-info";
  if (token_.length()) url += "?token=" + token_;
  HTTPClient http;
  http.setTimeout(8000);
  http.begin(url);
  http.addHeader("Accept", "application/json");
  if (token_.length()) http.addHeader("Authorization", "Bearer " + token_);
  int code = http.GET();
  if (code != 200) {
    out.error = "HTTP " + String(code);
    http.end();
    return false;
  }
  String body = http.getString();
  http.end();
  JsonDocument doc;
  if (deserializeJson(doc, body)) {
    out.error = "JSON parse";
    return false;
  }
  out.ok = doc["ok"] | false;
  JsonObjectConst rel = doc["release"];
  if (!rel.isNull()) {
    out.tag = rel["tag"] | "";
    out.name = rel["name"] | out.tag;
    out.assetName = rel["asset_name"] | "";
  }
  if (!out.ok) out.error = doc["error"] | "No release";
  return out.ok;
}

bool GitOta::installLatest(String& statusOut) {
  if (WiFi.status() != WL_CONNECTED || host_.length() == 0) {
    statusOut = "No host";
    return false;
  }
  busy_ = true;
  status_ = "Downloading...";
  String url = "http://" + host_ + ":" + String(port_) + "/api/display/firmware/latest.bin";
  if (token_.length()) url += "?token=" + token_;
  if (pendingTag_.length()) {
    url += (url.indexOf('?') >= 0 ? "&" : "?") + String("ver=") + pendingTag_;
  }
  httpUpdate.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  httpUpdate.rebootOnUpdate(true);
  WiFiClient client;
  status_ = "Installing...";
  t_httpUpdate_return ret = httpUpdate.update(client, url, String(FW_VERSION));
  busy_ = false;
  switch (ret) {
    case HTTP_UPDATE_OK:
      statusOut = "Updated to " FW_VERSION;
      status_ = statusOut;
      return true;
    case HTTP_UPDATE_NO_UPDATES:
      statusOut = "Already current";
      status_ = statusOut;
      return false;
    case HTTP_UPDATE_FAILED:
    default:
      statusOut = String("Update failed: ") + httpUpdate.getLastErrorString();
      status_ = statusOut;
      return false;
  }
}

void GitOta::loop() {
  if (!check_ || busy_ || WiFi.status() != WL_CONNECTED || host_.length() == 0) return;
  uint32_t interval = autoInstall_ ? 3600000UL : 86400000UL;
  if (millis() - lastCheckMs_ < interval && lastCheckMs_ != 0) return;
  lastCheckMs_ = millis();
  UpdateInfo info;
  if (!checkUpdateInfo(info) || !info.tag.length()) {
    status_ = info.error.length() ? info.error : "Check failed";
    return;
  }
  String cur = String(FW_VERSION);
  String remote = info.tag;
  remote.replace("v", "");
  cur.replace("v", "");
  if (remote == cur) {
    status_ = "Up to date (" FW_VERSION ")";
    return;
  }
  status_ = "Update: " + info.tag;
  pendingTag_ = info.tag;
  if (autoInstall_) {
    String st;
    installLatest(st);
  }
}
