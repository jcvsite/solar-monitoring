#pragma once
#include <TFT_eSPI.h>
#include <lvgl.h>
#include <stdint.h>
#include <stddef.h>

void lvglPortInit(TFT_eSPI& tft, uint8_t rotation);
void lvglPortSetRotation(uint8_t rotation);
void lvglPortTick();
void lvglPortResetInput();
int lvglPortConsumeSwipe();

/** Capture current LVGL screen into an in-memory RGB565 buffer (full refresh). */
bool lvglPortCaptureFrame();
int lvglPortFbWidth();
int lvglPortFbHeight();
const uint16_t* lvglPortFb();
void lvglPortFreeCapture();
uint8_t lvglPortRotation();
