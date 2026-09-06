#pragma once
#include <Arduino.h>
#include "api_client.h"
#include "settings_store.h"
#include "ui.h"

// FreeRTOS worker that fetches host APIs off the UI thread.
void hostPollBegin(ApiClient* api, HostSettings* settings);
void hostPollRequest(UiPage page, bool force);
bool hostPollTakeGlance(GlanceData& out);
bool hostPollTakeBms(BmsData& out);
bool hostPollTakeHistory(HistoryData& out);
bool hostPollBusy();
