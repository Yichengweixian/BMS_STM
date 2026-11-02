#ifndef KEY_H
#define KEY_H

#include <stdint.h>
#include <stdbool.h>
#include "stm32n6xx_hal.h"
#define KEY_MAX             4       // 最多支持的按键数
#define KEY_SCAN_CYCLE      10      // 扫描周期（ms）
#define KEY_LONG_TIME       800     // 长按判定时间（ms）
#define KEY_DOUBLE_TIME     300     // 双击最大间隔时间（ms）
#define KEY_REPEAT_START    600     // 连续短按首次触发时间（ms）
#define KEY_REPEAT_CYCLE    200     // 连续短按后续周期（ms）

typedef enum {
    KEY_EVENT_NONE = 0,
    KEY_EVENT_PRESS,    // 按下瞬间
    KEY_EVENT_CLICK,    // 短按
    KEY_EVENT_LONG,     // 长按
    KEY_EVENT_DOUBLE,   // 双击
    KEY_EVENT_REPEAT    // 连续短按（类似键盘长按）
} KeyEvent;

typedef struct {
    GPIO_TypeDef *port;
    uint16_t pin;
    uint8_t id;

    // 内部状态
    uint8_t state;
    uint16_t press_time;
    uint16_t release_time;
    uint16_t repeat_time;
    bool waiting_double;
    bool repeating;
    KeyEvent last_event;
} Key;

typedef void (*KeyCallback)(uint8_t key_id, KeyEvent event);

// 初始化按键
void Key_Init(Key *keys, uint8_t key_count);

// 注册回调
void Key_RegisterCallback(KeyCallback cb);

// 扫描按键（定时器中调用）
void Key_Scan(void);

#endif // KEY_H
