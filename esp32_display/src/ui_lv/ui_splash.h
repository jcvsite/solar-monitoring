#pragma once
#include <lvgl.h>
#include <Arduino.h>

void uiSplashShow(const char* msg);
void uiSplashSetMsg(const char* msg);
void uiSplashDismiss();
void uiSplashAbandon();
bool uiSplashOwns(const lv_obj_t* obj);
bool uiSplashIsActive();
