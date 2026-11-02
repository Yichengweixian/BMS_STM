#include "key.h"


static Key *key_list = NULL;
static uint8_t key_num = 0;
static KeyCallback key_callback = NULL;

void Key_Init(Key *keys, uint8_t count) {
    key_list = keys;
    key_num = count;
    for (uint8_t i = 0; i < count; i++) {
        keys[i].state = 0;
        keys[i].press_time = 0;
        keys[i].release_time = 0;
        keys[i].repeat_time = 0;
        keys[i].waiting_double = false;
        keys[i].repeating = false;
        keys[i].last_event = KEY_EVENT_NONE;
    }
}

void Key_RegisterCallback(KeyCallback cb) {
    key_callback = cb;
}

void Key_Scan(void) {
    for (uint8_t i = 0; i < key_num; i++) {
        Key *k = &key_list[i];
        GPIO_PinState pin_state = HAL_GPIO_ReadPin(k->port, k->pin);

        switch (k->state) {
            case 0: // 未按下
                if (pin_state == GPIO_PIN_RESET) {
                    k->state = 1;
                    k->press_time = 0;
                    k->repeat_time = 0;
                    k->repeating = false;
                    if (key_callback) key_callback(k->id, KEY_EVENT_PRESS);
                }
                break;

            case 1: // 按下中
                k->press_time += KEY_SCAN_CYCLE;
                k->repeat_time += KEY_SCAN_CYCLE;

                if (pin_state == GPIO_PIN_SET) {
                    k->state = 2;
                    k->release_time = 0;

                    if (k->press_time >= KEY_LONG_TIME) {
                        if (key_callback) key_callback(k->id, KEY_EVENT_LONG);
                    } else {
                        if (k->waiting_double) {
                            if (key_callback) key_callback(k->id, KEY_EVENT_DOUBLE);
                            k->waiting_double = false;
                        } else {
                            k->waiting_double = true;
                        }
                    }

                } else {
                    if (!k->repeating && k->press_time >= KEY_REPEAT_START) {
                        k->repeating = true;
                        k->repeat_time = 0;
                        if (key_callback) key_callback(k->id, KEY_EVENT_REPEAT);
                    } else if (k->repeating && k->repeat_time >= KEY_REPEAT_CYCLE) {
                        k->repeat_time = 0;
                        if (key_callback) key_callback(k->id, KEY_EVENT_REPEAT);
                    }
                }
                break;

            case 2: // 抬起后等待双击
                k->release_time += KEY_SCAN_CYCLE;
                if (pin_state == GPIO_PIN_RESET) {
                    k->state = 1;
                    k->press_time = 0;
                    k->repeat_time = 0;
                    k->repeating = false;
                    if (key_callback) key_callback(k->id, KEY_EVENT_PRESS);
                } else if (k->release_time >= KEY_DOUBLE_TIME) {
                    if (k->waiting_double) {
                        if (key_callback) key_callback(k->id, KEY_EVENT_CLICK);
                        k->waiting_double = false;
                    }
                    k->state = 0;
                }
                break;
        }
    }
}
