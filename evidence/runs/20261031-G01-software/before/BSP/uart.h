#ifndef __UART_H
#define __UART_H

#include "main.h"
#include <stdio.h>

/* 硬件定义 */
#define UART_UX         USART1

/* 功能定义 */
#ifndef BSP_UART_RX_DISABLE
#define UART_EN_RX      1                   /* 使能串口接收功能 */
#else
#define UART_EN_RX      0                   /* 禁用串口接收功能 */
#endif

/* 接收参数（HAL_UARTEx_ReceiveToIdle_IT：IDLE 线空闲断帧） */
#define UART_RX_BUF_SIZE    200             /* 单帧接收缓冲大小，双缓冲各一块 */

/* 发送参数 */
#define UART_TX_TIMEOUT_MS      100         /* 单次发送超时（ms），不要用 0xFFFF */
#define UART_PRINTF_BUF_SIZE    128         /* uart_printf 单次格式化缓冲（字节） */

/* 函数声明 */
void uart_init(uint32_t baudrate);             /* 初始化串口并启动接收 */

/* 接收原语：HAL_UARTEx_RxEventCallback 由应用层（main.c）实现，
   驱动只负责把收到的数据块交出去、并负责重启接收。
   应用在回调里用 uart_rx_data() 取数据，处理完必须调 uart_rx_restart()。 */
const uint8_t *uart_rx_data(void);     /* 本帧数据块（长度 = 回调参数 Size） */
void           uart_rx_restart(void);  /* 本帧处理完：切块并重启接收 */

/* 发送接口：不依赖 C 库重定向，Keil(AC5/AC6) 与 GCC 行为一致。
   底层走 GPDMA1_Channel1（USART1_TX），需 huart1.hdmatx 已由 MSP 绑定。 */
HAL_StatusTypeDef uart_send_dma(const uint8_t *data, uint16_t len); /* 非阻塞，缓冲须常驻 */
uint8_t  uart_tx_is_busy(void);                    /* 1 = DMA 发送中 */
void     uart_send(const uint8_t *data, uint16_t len);  /* 阻塞轮询（应急/中断上下文） */
void     uart_send_string(const char *str);             /* 发送字符串（同步） */
void     uart_printf(const char *fmt, ...);             /* 格式化发送（同步，主循环用） */
#endif
