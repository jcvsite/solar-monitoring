#pragma once
#include <lvgl.h>
#include <Arduino.h>

void uiSetupHostChoice(const String& wifiSsid);
void uiSetupFindingHost(const String& status);
void uiSetupManualHost(const uint8_t octets[4], uint8_t selectedOctet, uint16_t port, const String& status);
void uiSetupPickList(const char* title, const char* const* names, int count, int selected, bool isTheme);
