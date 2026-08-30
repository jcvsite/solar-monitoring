#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <vector>

struct GlanceData {
  bool ok = false;
  String title = "Solar Monitoring";
  float age_s = -1;
  String ts;
  float soc = NAN;
  float batt_w = NAN;
  String batt_status;
  String batt_time;
  float pv_w = NAN;
  float load_w = NAN;
  float grid_w = NAN;
  String grid_state = "unknown";
  String grid_label = "-";
  float pv_today_kwh = NAN;
  float load_today_kwh = NAN;
  String status;
  bool alerts = false;
  String clock;
  String timezone;
  int tz_offset_sec = INT32_MIN;
  bool weather_enabled = false;
  int weather_code = 0;
  int weather_is_day = 1;
  float weather_temp = NAN;
  char weather_unit = 'C';
  float inv_temp_c = NAN;
  float batt_temp_c = NAN;
};

struct BmsData {
  bool ok = false;
  float soc = NAN, soh = NAN, volts = NAN, amps = NAN, watts = NAN;
  String status;
  float temp_min = NAN, temp_max = NAN, temp_avg = NAN;
  float cycles = NAN;
  int cell_count = 0;
  float cell_min_v = NAN, cell_max_v = NAN, cell_delta_v = NAN;
  std::vector<float> cells;
  int pack_count = 0;
};

struct HistoryPoint {
  uint32_t t = 0;
  float pv_w = NAN;
  float load_w = NAN;
  float soc = NAN;
};

struct HistoryData {
  bool ok = false;
  int hours = 24;
  std::vector<HistoryPoint> points;
  float today_pv = NAN, today_load = NAN;
  float today_gi = NAN, today_ge = NAN;
  float today_bc = NAN, today_bd = NAN;
};

/** Mirrors host display_config.json (/api/display/config). */
struct DisplayConfig {
  bool ok = false;
  uint32_t config_rev = 0;
  uint8_t glance_layout = 0;
  uint8_t theme = 0;
  uint8_t rotation = 0;
  uint8_t brightness = 200;
  uint32_t poll_ms = 5000;
  bool check_for_update = false;
  bool auto_install_update = false;
  bool grid_offline_alert = true;
  bool force_update = false;
  String force_update_version;
  String settings_pin;
  bool settings_pin_set = false;
};

class ApiClient {
 public:
  bool fetchGlance(const String& host, uint16_t port, const String& token, GlanceData& out);
  bool fetchBms(const String& host, uint16_t port, const String& token, BmsData& out);
  bool fetchHistory(const String& host, uint16_t port, const String& token, int hours, HistoryData& out);
  bool fetchDisplayConfig(const String& host, uint16_t port, const String& token, DisplayConfig& out);
  bool probeHost(const String& host, uint16_t port, const String& token, String& titleOut);

 private:
  bool httpGetJson(const String& url, const String& token, JsonDocument& doc);
};
