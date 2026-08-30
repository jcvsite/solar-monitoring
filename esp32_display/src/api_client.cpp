#include "api_client.h"
#include <HTTPClient.h>
#include <WiFi.h>

static float jnum(JsonVariantConst v) {
  if (v.isNull()) return NAN;
  return v.as<float>();
}

bool ApiClient::httpGetJson(const String& url, const String& token, JsonDocument& doc) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.setTimeout(4000);
  http.begin(url);
  http.addHeader("Accept", "application/json");
  if (token.length()) {
    http.addHeader("Authorization", "Bearer " + token);
  }
  int code = http.GET();
  if (code != 200) {
    http.end();
    return false;
  }
  String body = http.getString();
  http.end();
  DeserializationError err = deserializeJson(doc, body);
  return !err;
}

bool ApiClient::probeHost(const String& host, uint16_t port, const String& token, String& titleOut) {
  GlanceData g;
  if (!fetchGlance(host, port, token, g)) return false;
  if (g.title.length()) titleOut = g.title;
  return g.ok || g.title.length() > 0;
}

bool ApiClient::fetchGlance(const String& host, uint16_t port, const String& token, GlanceData& out) {
  String url = "http://" + host + ":" + String(port) + "/api/display";
  if (token.length()) url += "?token=" + token;
  JsonDocument doc;
  if (!httpGetJson(url, token, doc)) return false;
  if (doc["app"] && String(doc["app"].as<const char*>()) != "solar-monitoring") {
    // still accept if ok flag present (older)
  }
  out.ok = doc["ok"] | false;
  out.title = doc["title"] | "Solar Monitoring";
  out.age_s = jnum(doc["age_s"]);
  out.ts = doc["ts"] | "";
  out.soc = jnum(doc["soc"]);
  out.batt_w = jnum(doc["batt_w"]);
  out.batt_status = doc["batt_status"] | "";
  out.batt_time = doc["batt_time"] | "";
  out.pv_w = jnum(doc["pv_w"]);
  out.load_w = jnum(doc["load_w"]);
  out.grid_w = jnum(doc["grid_w"]);
  out.grid_state = doc["grid_state"] | "unknown";
  out.grid_label = doc["grid_label"] | "-";
  out.pv_today_kwh = jnum(doc["pv_today_kwh"]);
  out.load_today_kwh = jnum(doc["load_today_kwh"]);
  out.status = doc["status"] | "";
  out.alerts = doc["alerts"] | false;
  out.clock = doc["clock"] | "";
  out.timezone = doc["timezone"] | "";
  if (!doc["tz_offset_sec"].isNull()) {
    out.tz_offset_sec = doc["tz_offset_sec"].as<int>();
  }
  JsonObjectConst weather = doc["weather"];
  if (!weather.isNull() && (weather["enabled"] | false)) {
    out.weather_enabled = true;
    out.weather_code = weather["code"] | 0;
    out.weather_is_day = weather["is_day"] | 1;
    out.weather_temp = jnum(weather["temp"]);
    String unit = weather["unit"] | "C";
    out.weather_unit = unit.length() ? unit.charAt(0) : 'C';
  } else {
    out.weather_enabled = false;
    out.weather_code = 0;
    out.weather_is_day = 1;
    out.weather_temp = NAN;
    out.weather_unit = 'C';
  }
  out.inv_temp_c = jnum(doc["inv_temp_c"]);
  out.batt_temp_c = jnum(doc["batt_temp_c"]);
  return true;
}

bool ApiClient::fetchBms(const String& host, uint16_t port, const String& token, BmsData& out) {
  String url = "http://" + host + ":" + String(port) + "/api/display/bms";
  if (token.length()) url += "?token=" + token;
  JsonDocument doc;
  if (!httpGetJson(url, token, doc)) return false;
  out.ok = doc["ok"] | false;
  out.soc = jnum(doc["soc"]);
  out.soh = jnum(doc["soh"]);
  out.volts = jnum(doc["volts"]);
  out.amps = jnum(doc["amps"]);
  out.watts = jnum(doc["watts"]);
  out.status = doc["status"] | "";
  out.temp_min = jnum(doc["temp_min"]);
  out.temp_max = jnum(doc["temp_max"]);
  out.temp_avg = jnum(doc["temp_avg"]);
  out.cycles = jnum(doc["cycles"]);
  out.cell_count = doc["cell_count"] | 0;
  out.cell_min_v = jnum(doc["cell_min_v"]);
  out.cell_max_v = jnum(doc["cell_max_v"]);
  out.cell_delta_v = jnum(doc["cell_delta_v"]);
  out.pack_count = doc["pack_count"] | 0;
  out.cells.clear();
  JsonArray arr = doc["cells"].as<JsonArray>();
  if (!arr.isNull()) {
    for (JsonVariant v : arr) {
      out.cells.push_back(v.as<float>());
      if (out.cells.size() >= 32) break;
    }
  }
  return true;
}

bool ApiClient::fetchHistory(const String& host, uint16_t port, const String& token, int hours, HistoryData& out) {
  String url = "http://" + host + ":" + String(port) + "/api/display/history?hours=" + String(hours);
  if (token.length()) url += "&token=" + token;
  JsonDocument doc;
  if (!httpGetJson(url, token, doc)) return false;
  out.ok = doc["ok"] | false;
  out.hours = doc["hours"] | hours;
  out.today_pv = jnum(doc["today"]["pv_kwh"]);
  out.today_load = jnum(doc["today"]["load_kwh"]);
  out.today_gi = jnum(doc["today"]["grid_import_kwh"]);
  out.today_ge = jnum(doc["today"]["grid_export_kwh"]);
  out.today_bc = jnum(doc["today"]["batt_charge_kwh"]);
  out.today_bd = jnum(doc["today"]["batt_discharge_kwh"]);
  out.points.clear();
  JsonArray arr = doc["points"].as<JsonArray>();
  if (!arr.isNull()) {
    for (JsonObject o : arr) {
      HistoryPoint p;
      p.t = o["t"] | 0;
      p.pv_w = jnum(o["pv_w"]);
      p.load_w = jnum(o["load_w"]);
      p.soc = jnum(o["soc"]);
      out.points.push_back(p);
    }
  }
  return true;
}

bool ApiClient::fetchDisplayConfig(const String& host, uint16_t port, const String& token, DisplayConfig& out) {
  String url = "http://" + host + ":" + String(port) + "/api/display/config";
  if (token.length()) url += "?token=" + token;
  JsonDocument doc;
  if (!httpGetJson(url, token, doc)) return false;
  out.ok = doc["ok"] | false;
  out.config_rev = doc["config_rev"] | 0;
  out.glance_layout = (uint8_t)constrain((int)(doc["glance_layout"] | 0), 0, 4);
  out.theme = (uint8_t)constrain((int)(doc["theme"] | 0), 0, 4);
  out.rotation = (uint8_t)constrain((int)(doc["rotation"] | 0), 0, 3);
  out.brightness = (uint8_t)constrain((int)(doc["brightness"] | 200), 0, 255);
  out.poll_ms = doc["poll_ms"] | 5000;
  if (out.poll_ms < 2000) out.poll_ms = 2000;
  out.check_for_update = doc["check_for_update"] | false;
  out.auto_install_update = doc["auto_install_update"] | false;
  out.grid_offline_alert = doc["grid_offline_alert"] | true;
  out.force_update = doc["force_update"] | false;
  out.force_update_version = doc["force_update_version"] | "";
  out.settings_pin_set = doc["settings_pin_set"] | false;
  if (doc["settings_pin"].is<const char*>()) {
    out.settings_pin = doc["settings_pin"].as<const char*>();
  }
  if (out.settings_pin.length() != 4) out.settings_pin = "";
  if (out.settings_pin.length() == 4) out.settings_pin_set = true;
  if (out.auto_install_update) out.check_for_update = true;
  return out.ok;
}
