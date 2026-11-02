/**
 * @file pi.h
 * @brief 数字PI控制器模块 (专用于双向DC-DC电源控制)
 * @details 基于增量式算法，包含抗饱和、输出限幅和模式管理
 */

#ifndef __PI_H
#define __PI_H

/* 包含头文件 --------------------------------------------------------*/
#include <stdint.h>
#include <stdbool.h>

/* 类型定义 ----------------------------------------------------------*/
/**
 * @brief PI控制器结构体
 * @note 针对100kHz开关频率优化，所有时间单位：秒(s)
 */
typedef struct {
    float Kp;
    float Ki_Ts;        /* Ki × Ts，提前乘好，省一次乘法 */
    float u_min;        /* 输出下限，本实验 0.40 */
    float u_max;        /* 输出上限，本实验 0.90 */
    float integ;        /* 积分项累加值 */
} PI_t;
 
static inline void PI_Init(PI_t *pi, float kp, float ki, float ts,
                           float u_min, float u_max, float u0)
{
    pi->Kp    = kp;
    pi->Ki_Ts = ki * ts;
    pi->u_min = u_min;
    pi->u_max = u_max;
    pi->integ = u0;              /* 从安全占空比起步 */
}
 
static inline float PI_Update(PI_t *pi, float err)
{
    float p = pi->Kp * err;
    float i = pi->integ + pi->Ki_Ts * err;
    float u;
 
    /* 积分项独立限幅 */
    if (i > pi->u_max) { i = pi->u_max; }
    if (i < pi->u_min) { i = pi->u_min; }
 
    u = p + i;
 
    /*  反算抗饱和 */
    if (u > pi->u_max) { u = pi->u_max; i = pi->u_max - p; }
    if (u < pi->u_min) { u = pi->u_min; i = pi->u_min - p; }
 
    pi->integ = i;
    return u;
}

#endif /* __PI_CONTROLLER_H */
