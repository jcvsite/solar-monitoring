#pragma once
#include <Arduino.h>

struct UpdateInfo {
  bool ok = false;
  String tag;
  String name;
  String assetName;
  String error;
};

class GitOta {
 public:
  void begin();
  void configure(const String& host, uint16_t port, const String& token, bool check, bool autoInstall);
  bool checkUpdateInfo(UpdateInfo& out);
  bool installLatest(String& statusOut);
  void loop();
  const String& status() const { return status_; }
  bool busy() const { return busy_; }

 private:
  String host_;
  uint16_t port_ = 8081;
  String token_;
  bool check_ = false;
  bool autoInstall_ = false;
  String status_ = "Ready";
  bool busy_ = false;
  uint32_t lastCheckMs_ = 0;
  String pendingTag_;
};

extern GitOta gitOta;
