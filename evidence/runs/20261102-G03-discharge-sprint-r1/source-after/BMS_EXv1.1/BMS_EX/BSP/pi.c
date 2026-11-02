/**
 * @file pi.c
 * @brief 数字PI控制器模块实现
 */

#include "PI.h"

/* ==================== 公开函数实现 ==================== */

/**
 * @brief 初始化PI控制器
 */

void PI_Init(PI_Controller_t *pi, float kp, float ki, float ts, float d_min, float d_max){
    pi->Kp = kp;
    pi->Ki_Ts = ki * ts; // 预计算Ki*Ts，避免每次中断都做乘法
    pi->err_prev = 0.0f;
    pi->duty = 0.0f;
    pi->duty_min = d_min;
    pi->duty_max = d_max;
    pi->integral = 0.0f;
}

