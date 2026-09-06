#include "device_web.h"
#include "lvgl_port.h"
#include <WebServer.h>
#include <WiFi.h>
#include <string.h>

DeviceWeb deviceWeb;
static WebServer s_server(80);
static bool s_webUnlocked = false;
static uint32_t s_webUnlockAt = 0;
static bool s_doRestart = false;
static uint32_t s_restartAt = 0;

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
</form>
<form method="POST" action="/restart" style="margin-top:1rem">
<label>PIN to restart<input name="pin" type="password" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" autocomplete="off"></label>
<button type="submit" style="background:#ff453a">Restart device</button>
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
</form>
<form method="POST" action="/restart" onsubmit="return confirm('Restart the display now?');">
<button type="submit" style="background:#ff453a;margin-top:.75rem">Restart device</button>
</form>
<div class="card"><p><a href="/screen.bmp" style="color:#0a84ff">Capture screen (BMP)</a> · <a href="/diag.json" style="color:#0a84ff">diag.json</a></p>
<p style="opacity:.6;font-size:.85rem">Screenshot mirrors what LVGL is drawing right now.</p></div>
<p style="opacity:.6;font-size:.85rem">Use Restart if the touchscreen freezes — no on-screen action needed.</p>
</body></html>)raw";
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


void DeviceWeb::handleRestart() {
  // Allow restart when unlocked, or when correct PIN is posted (frozen-touch escape hatch).
  bool ok = webIsUnlocked(settings_);
  if (!ok && pinRequired(settings_)) {
    String pin = s_server.hasArg("pin") ? s_server.arg("pin") : "";
    ok = (pin == settings_.settingsPin);
  } else if (!pinRequired(settings_)) {
    ok = true;
  }
  if (!ok) {
    s_server.send(403, "text/html",
                   "<html><body style='background:#111;color:#eee;font-family:sans-serif;padding:1rem'>"
                   "<p>PIN required to restart.</p><a href='/'>Back</a></body></html>");
    return;
  }
  s_server.send(200, "text/html",
                 "<html><body style='background:#111;color:#eee;font-family:sans-serif;padding:1rem'>"
                 "<h1>Restarting…</h1><p>The display will reboot in about a second.</p>"
                 "</body></html>");
  s_doRestart = true;
  s_restartAt = millis() + 900;
}


void DeviceWeb::handleDiag() {
  String j = "{";
  j += "\"rotation\":" + String(lvglPortRotation());
  j += ",\"fb_w\":" + String(lvglPortFbWidth());
  j += ",\"fb_h\":" + String(lvglPortFbHeight());
  j += ",\"heap\":" + String(ESP.getFreeHeap());
  j += ",\"ip\":\"" + WiFi.localIP().toString() + "\"";
  j += ",\"rot_setting\":" + String(settings_.screenRotation);
  j += "}";
  s_server.send(200, "application/json", j);
}

void DeviceWeb::handleScreen() {
  // Capture is relatively expensive; allow without PIN so LAN debug works when UI is broken.
  if (!lvglPortCaptureFrame()) {
    s_server.send(500, "text/plain", "capture failed (OOM or LVGL not ready)");
    return;
  }
  const int w = lvglPortFbWidth();
  const int h = lvglPortFbHeight();
  const uint16_t* fb = lvglPortFb();
  if (!fb || w <= 0 || h <= 0) {
    lvglPortFreeCapture();
    s_server.send(500, "text/plain", "empty frame");
    return;
  }

  const uint32_t rowPad = (uint32_t)((w * 3 + 3) & ~3);
  const uint32_t imgSize = rowPad * (uint32_t)h;
  const uint32_t fileSize = 54 + imgSize;

  uint8_t hdr[54];
  memset(hdr, 0, sizeof(hdr));
  hdr[0] = 'B'; hdr[1] = 'M';
  hdr[2] = (uint8_t)(fileSize);
  hdr[3] = (uint8_t)(fileSize >> 8);
  hdr[4] = (uint8_t)(fileSize >> 16);
  hdr[5] = (uint8_t)(fileSize >> 24);
  hdr[10] = 54;
  hdr[14] = 40;
  hdr[18] = (uint8_t)(w);
  hdr[19] = (uint8_t)(w >> 8);
  hdr[20] = (uint8_t)(w >> 16);
  hdr[21] = (uint8_t)(w >> 24);
  hdr[22] = (uint8_t)(h);
  hdr[23] = (uint8_t)(h >> 8);
  hdr[24] = (uint8_t)(h >> 16);
  hdr[25] = (uint8_t)(h >> 24);
  hdr[26] = 1;
  hdr[28] = 24;
  hdr[34] = (uint8_t)(imgSize);
  hdr[35] = (uint8_t)(imgSize >> 8);
  hdr[36] = (uint8_t)(imgSize >> 16);
  hdr[37] = (uint8_t)(imgSize >> 24);

  s_server.setContentLength(fileSize);
  s_server.send(200, "image/bmp", "");
  WiFiClient client = s_server.client();
  client.write(hdr, sizeof(hdr));

  // BMP is bottom-up. Convert RGB565 -> BGR888 per row.
  uint8_t* row = (uint8_t*)malloc(rowPad);
  if (!row) {
    lvglPortFreeCapture();
    return;
  }
  memset(row, 0, rowPad);
  for (int y = h - 1; y >= 0; --y) {
    const uint16_t* src = fb + (size_t)y * (size_t)w;
    for (int x = 0; x < w; ++x) {
      // LV_COLOR_16_SWAP=1: byte-swap before interpreting as RGB565.
      uint16_t c = src[x];
      c = (uint16_t)((c >> 8) | (c << 8));
      const uint8_t r5 = (c >> 11) & 0x1F;
      const uint8_t g6 = (c >> 5) & 0x3F;
      const uint8_t b5 = c & 0x1F;
      row[x * 3 + 0] = (uint8_t)((b5 * 255) / 31);
      row[x * 3 + 1] = (uint8_t)((g6 * 255) / 63);
      row[x * 3 + 2] = (uint8_t)((r5 * 255) / 31);
    }
    client.write(row, rowPad);
  }
  free(row);
  lvglPortFreeCapture();
}


void DeviceWeb::handleRotate() {
  // GET /rotate?to=0..3  — applies on next main-loop save tick via gDeviceWebSaved
  if (!s_server.hasArg("to")) {
    s_server.send(400, "text/plain", "usage: /rotate?to=0..3");
    return;
  }
  int to = s_server.arg("to").toInt();
  if (to < 0 || to > 3) {
    s_server.send(400, "text/plain", "to must be 0..3");
    return;
  }
  settings_.screenRotation = (uint8_t)to;
  extern bool gDeviceWebSaved;
  gDeviceWebSaved = true;
  s_server.send(200, "application/json",
                String("{\"ok\":true,\"rotation\":") + String(to) + "}");
}

void DeviceWeb::begin() {
  if (started_) return;
  s_server.on("/", [this]() { handleRoot(); });
  s_server.on("/unlock", HTTP_POST, [this]() { handleUnlock(); });
  s_server.on("/save", HTTP_POST, [this]() { handleSave(); });
  s_server.on("/restart", HTTP_POST, [this]() { handleRestart(); });
  s_server.on("/screen.bmp", HTTP_GET, [this]() { handleScreen(); });
  s_server.on("/diag.json", HTTP_GET, [this]() { handleDiag(); });
  s_server.on("/rotate", HTTP_GET, [this]() { handleRotate(); });
  s_server.begin();
  started_ = true;
}

void DeviceWeb::loop() {
  if (started_) s_server.handleClient();
  if (s_doRestart && (int32_t)(millis() - s_restartAt) >= 0) {
    s_doRestart = false;
    ESP.restart();
  }
}

bool gDeviceWebSaved = false;
