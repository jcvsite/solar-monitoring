#include "logo_solar_monitoring_lvgl.h"

const lv_img_dsc_t logo_solar_monitoring_img = {
    .header =
        {
            .cf = LV_IMG_CF_TRUE_COLOR,
            .always_zero = 0,
            .reserved = 0,
            .w = LOGO_SOLAR_MONITORING_W,
            .h = LOGO_SOLAR_MONITORING_H,
        },
    .data_size = (uint32_t)(LOGO_SOLAR_MONITORING_W * LOGO_SOLAR_MONITORING_H * 2),
    .data = (const uint8_t*)logo_solar_monitoring,
};
