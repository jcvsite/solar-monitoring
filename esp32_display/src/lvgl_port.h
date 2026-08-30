#pragma once
#include <TFT_eSPI.h>
#include <lvgl.h>
#include <stdint.h>

void lvglPortInit(TFT_eSPI& tft, uint8_t rotation);
void lvglPortSetRotation(uint8_t rotation);
void lvglPortTick();
