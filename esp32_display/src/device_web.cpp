#include "device_web.h"
#include <WebServer.h>
#include <WiFi.h>

DeviceWeb deviceWeb;
static WebServer s_server(80);
static bool s_webUnlocked = false;
static uint32_t s_webUnlockAt = 0;

static const uint32_t kWebUnlockMs = 600000;

static bool pinRequired(const HostSettings& s) { return s.settingsPin.length() == 4; }

static bool webIsUnlocked(const HostSettings& s) {
  if (!pinRequired(s)) return true;
  if (!s_webUnlocked) return false;
  if (millis() - s_webUnlockAt > kWebUnlockMs) {
    s_webUnlocked = false;
    return false;
  }
  return true;
}

void DeviceWeb::applySettings(const HostSettings& s) {
  settings_ = s;
  if (!pinRequired(settings_)) {
    s_webUnlocked = false;
  }
}

String DeviceWeb::htmlPinGate() const {
  return R"raw(<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solar Display</title>
<style>body{font-family:sans-serif;margin:1rem;background:#111;color:#eee;max-width:420px}
input{padding:.8rem;font-size:1.2rem;width:100%;box-sizing:border-box;letter-spacing:.3em;text-align:center}
button{margin-top:1rem;padding:.7rem 1.2rem;background:#0a84ff;color:#fff;border:0;border-radius:6px;width:100%}
.card{background:#1c1c1e;padding:1rem;border-radius:8px}</style></head><body>
<h1>Solar Monitoring Viewer</h1>
<div class="card"><p>Settings are protected. Enter the 4-digit PIN.</p>
<form method="POST" action="/unlock">
<label>PIN<input name="pin" type="password" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" autocomplete="off"></label>
<button type="submit">Unlock</button>
</form></div></body></html>)raw";
}

String DeviceWeb::htmlPage() const {
  String ip = WiFi.localIP().toString();
  String host = settings_.hostIp.length() ? settings_.hostIp : "(not set)";
  String html = R"raw(<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Solar Display</title>
<style>body{font-family:sans-serif;margin:1rem;background:#111;color:#eee}
label{display:block;margin:.5rem 0}input,select{width:100%;padding:.4rem}
button{margin-top:1rem;padding:.6rem 1.2rem;background:#0a84ff;color:#fff;border:0;border-radius:6px}
.card{background:#1c1c1e;padding:1rem;border-radius:8px;margin-bottom:1rem}</style></head><body>
<h1>Solar Monitoring Viewer</h1>
<div class="card"><p>Device IP: )raw";
  html += ip;
  html += R"raw(</p><p>Host: )raw";
  html += host;
  html += ":" + String(settings_.hostPort);
  html += R"raw(</p></div>
<form method="POST" action="/save">
<div class="card">
<label>Host IP<input name="host" value=")raw";
  html += settings_.hostIp;
  html += R"raw("></label>
<label>Port<input name="port" type="number" value=")raw";
  html += String(settings_.hostPort);
  html += R"raw("></label>
<label>Layout<select name="layout">)raw";
  const char* layouts[] = {"Classic", "Compact", "Ring", "Bars", "Flow"};
  for (int i = 0; i < 5; i++) {
    html += "<option value='" + String(i) + "'";
    if ((int)settings_.glanceLayout == i) html += " selected";
    html += ">" + String(layouts[i]) + "</option>";
  }
  html += R"raw(</select></label>
<label>Theme<select name="theme">)raw";
  const char* themes[] = {"Dark", "Light", "Solar", "Ocean", "Forest"};
  for (int i = 0; i < 5; i++) {
    html += "<option value='" + String(i) + "'";
    if ((int)settings_.themeId == i) html += " selected";
    html += ">" + String(themes[i]) + "</option>";
  }
  html += R"raw(</select></label>
<label>Rotation<select name="rot">)raw";
  const char* rots[] = {"Portrait", "Landscape", "Portrait flip", "Landscape flip"};
  for (int i = 0; i < 4; i++) {
    html += "<option value='" + String(i) + "'";
    if ((int)settings_.screenRotation == i) html += " selected";
    html += ">" + String(rots[i]) + "</option>";
  }
  html += R"raw(</select></label>
<label>Settings PIN (4 digits, blank=off)<input name="setpin" inputmode="numeric" maxlength="4" pattern="[0-9]{4}" placeholder=")raw";
  html += pinRequired(settings_) ? "****" : "off";
  html += R"raw("></label>
<label><input type="checkbox" name="gridAlert" )raw";
  if (settings_.gridOfflineAlert) html += "checked";
  html += R"raw(> Grid offline alert</label>
<label><input type="checkbox" name="useHost" )raw";
  if (settings_.useHostConfig) html += "checked";
  html += R"raw(> Sync from host</label>
</div>
<button type="submit">Save</button>
</form></body></html>)raw";
  return html;
}

void DeviceWeb::handleRoot() {
  if (!webIsUnlocked(settings_)) {
    s_server.send(200, "text/html", htmlPinGate());
    return;
  }
  s_server.send(200, "text/html", htmlPage());
}

void DeviceWeb::handleUnlock() {
  String pin = s_server.hasArg("pin") ? s_server.arg("pin") : "";
  if (pinRequired(settings_) && pin == settings_.settingsPin) {
    s_webUnlocked = true;
    s_webUnlockAt = millis();
    s_server.sendHeader("Location", "/");
    s_server.send(303);
    return;
  }
  s_server.send(403, "text/html",
                 "<html><body style='background:#111;color:#eee;font-family:sans-serif;padding:1rem'>"
                 "<p>Wrong PIN.</p><a href='/'>Back</a></body></html>");
}

void DeviceWeb::handleSave() {
  if (!webIsUnlocked(settings_)) {
    s_server.send(403, "text/html", htmlPinGate());
    return;
  }
  if (s_server.hasArg("host")) settings_.hostIp = s_server.arg("host");
  if (s_server.hasArg("port")) settings_.hostPort = (uint16_t)constrain(s_server.arg("port").toInt(), 1, 65535);
  if (s_server.hasArg("layout")) settings_.glanceLayout = (uint8_t)constrain(s_server.arg("layout").toInt(), 0, 4);
  if (s_server.hasArg("theme")) settings_.themeId = (uint8_t)constrain(s_server.arg("theme").toInt(), 0, 4);
  if (s_server.hasArg("rot")) settings_.screenRotation = (uint8_t)constrain(s_server.arg("rot").toInt(), 0, 3);
  if (s_server.hasArg("setpin")) {
    String p = s_server.arg("setpin");
    p.trim();
    settings_.settingsPin = (p.length() == 4) ? p : "";
  }
  settings_.gridOfflineAlert = s_server.hasArg("gridAlert");
  settings_.useHostConfig = s_server.hasArg("useHost");
  s_server.send(200, "text/html", "<html><body><p>Saved.</p><a href='/'>Back</a></body></html>");
  extern bool gDeviceWebSaved;
  gDeviceWebSaved = true;
}

void DeviceWeb::begin() {
  if (started_) return;
  s_server.on("/", [this]() { handleRoot(); });
  s_server.on("/unlock", HTTP_POST, [this]() { handleUnlock(); });
  s_server.on("/save", HTTP_POST, [this]() { handleSave(); });
  s_server.begin();
  started_ = true;
}

void DeviceWeb::loop() {
  if (started_) s_server.handleClient();
}

bool gDeviceWebSaved = false;
