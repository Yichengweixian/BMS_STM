#ifndef FIRMWARE_IDENTITY_H
#define FIRMWARE_IDENTITY_H
#if defined(G03_PWM_LIVE_BUILD) && G03_PWM_LIVE_BUILD
#define BMS_DIAG_FIRMWARE "g03-power-points-r4"
#elif defined(G03_PWM_DISABLED_BUILD) && G03_PWM_DISABLED_BUILD
#define BMS_DIAG_FIRMWARE "g03-pwm-disabled-r1"
#else
#define BMS_DIAG_FIRMWARE "g03-relay-r2"
#endif
#endif
