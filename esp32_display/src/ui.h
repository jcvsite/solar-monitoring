#pragma once
#include <stdint.h>

#ifdef class
#undef class
#endif

enum class UiPage : uint8_t {
  Glance = 0,
  Bms = 1,
  History = 2,
  Settings = 3,
  SettingsConn = 4,
  SettingsUpdates = 5,
  PickLayout = 6,
  PickTheme = 7,
  FindingHost = 8,
  ManualHost = 9,
  HostChoice = 10,
  WifiPick = 11,
  WifiPassword = 12,
  PinUnlock = 13,
  PinSet = 14
};

enum class UiSettingsTab : uint8_t { Connection = 0, Updates = 1 };
