#pragma once
#include "ui.h"
#include <stdint.h>

struct HostSettings;
struct GlanceData;
struct BmsData;
struct HistoryData;
struct WifiNetwork;
class ApiClient;
class SettingsStore;
class Discovery;

enum class UiActionId : uint8_t {
  NavPage,
  OpenSettings,
  SettingsTab,
  PickLayout,
  PickTheme,
  RotateScreen,
  OpenPinSet,
  StartHostDiscovery,
  OpenManualHost,
  StartWifiScan,
  WifiRescan,
  WifiPhonePortal,
  WifiPickNetwork,
  WifiConnect,
  WifiBack,
  HostChoiceDiscover,
  HostChoiceManual,
  FindingHostCancel,
  ManualOctetSelect,
  ManualOctetDec,
  ManualOctetInc,
  ManualPortDec,
  ManualPortInc,
  ManualTest,
  ManualSave,
  ManualBack,
  ToggleCheckUpdate,
  ToggleAutoUpdate,
  ToggleGridAlert,
  ToggleUseHostConfig,
  PinDigit,
  PinDelete,
  PinOk,
  PinBack,
  OtaCheckNow,
};

struct UiActionCtx {
  UiPage page = UiPage::Glance;
  UiSettingsTab settingsTab = UiSettingsTab::Connection;
  int index = -1;
  int digit = -1;
  bool flag = false;
};

typedef void (*UiActionHandler)(UiActionId id, const UiActionCtx& ctx);

void uiActionsSetHandler(UiActionHandler handler);
void uiActionsFire(UiActionId id, const UiActionCtx& ctx);
