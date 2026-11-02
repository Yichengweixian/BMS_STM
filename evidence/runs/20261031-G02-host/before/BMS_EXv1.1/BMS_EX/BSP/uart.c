#include "uart.h"
#include <stdarg.h>
#include <string.h>

/* UART句柄 */
extern UART_HandleTypeDef huart1;

#if UART_EN_RX
/* 接收双缓冲：一块正在收，另一块交给 DMA 回发，两者互不干扰。
   32 字节对齐：DMA 发送前要按 cache line clean。 */
static uint8_t g_rx_buf[2][UART_RX_BUF_SIZE] __attribute__((aligned(32)));
static uint8_t g_rx_idx = 0U;               /* 当前用于接收的那一块 */
#endif

/* 正在被 DMA 读取的发送缓冲（发完 / 出错时清空）。
   接收侧据此判断“另一块能不能安全征用”，比只看忙标志更精确：
   应用完全可以先发送、再调 uart_rx_restart()，这里的判断照样成立。 */
static const uint8_t * volatile g_tx_buf = NULL;

/**
 * @brief   初始化串口
 * @param   baudrate: 通信波特率（单位：bps）
 * @retval  无
 */
void uart_init(uint32_t baudrate)
{
    UNUSED(baudrate);

    /* 这里不做 C 库重定向，也不调用 setvbuf：
       Keil 工程未启用 MicroLIB，printf 会走半主机（BKPT 0xAB），
       一旦执行即 HardFault / 卡死。需要打印请统一用 uart_printf()。 */

#if UART_EN_RX
    /* 启动接收：靠 IDLE（线空闲）断帧，比逐字节 RxCplt 少一个数量级的中断 */
    (void)HAL_UARTEx_ReceiveToIdle_IT(&huart1, g_rx_buf[g_rx_idx], UART_RX_BUF_SIZE);
#endif
}

#if UART_EN_RX
/**
 * @brief   取本次接收到的数据块
 * @retval  指向当前接收缓冲的指针（有效长度 = 回调参数 Size）
 * @note    只在 HAL_UARTEx_RxEventCallback 里有效；用完必须调 uart_rx_restart()。
 */
const uint8_t *uart_rx_data(void)
{
    return g_rx_buf[g_rx_idx];
}

/**
 * @brief   本帧处理完毕，重启接收（乒乓切块）
 * @retval  无
 * @note    ① 必须由应用层在 HAL_UARTEx_RxEventCallback 末尾调用，
 *             否则 HAL 已关闭接收（RxState 复位、IDLEIE 清零），只能收到一帧；
 *          ② 只有另一块没被 DMA 占用时才切换 —— 否则会把正在发送的缓冲当接收缓冲，
 *             新数据直接盖掉还没发出去的内容。
 */
void uart_rx_restart(void)
{
    uint8_t next = (uint8_t)(g_rx_idx ^ 1U);

    if (g_rx_buf[next] != g_tx_buf)          /* 另一块没被 DMA 读，可以征用 */
    {
        g_rx_idx = next;
    }

    (void)HAL_UARTEx_ReceiveToIdle_IT(&huart1, g_rx_buf[g_rx_idx], UART_RX_BUF_SIZE);
}
#endif

/* ==================== 发送（GPDMA1_Channel1 / USART1_TX） ==================== */

/* uart_printf 的格式化缓冲，必须是「常驻 + 32 字节对齐」：
   - 常驻：DMA 在后台读它，函数返回后内容还不能被覆盖，所以不能放栈上
   - 对齐：SCB_CleanDCache_by_Addr 按 cache line(32B) 操作，未对齐会波及相邻变量 */
static char uart_tx_buf[UART_PRINTF_BUF_SIZE] __attribute__((aligned(32)));

/* 发送忙标志：1 = DMA 传输中（含最后一个字节的移位时间） */
static volatile uint8_t uart_tx_busy_flag = 0U;

/**
 * @brief   等待上一帧发送结束
 * @param   timeout_ms: 超时时间（ms）
 * @retval  1 = 已空闲，0 = 超时（已强制中止本次传输）
 */
static uint8_t uart_tx_wait_idle(uint32_t timeout_ms)
{
    uint32_t start = HAL_GetTick();

    while (uart_tx_busy_flag != 0U)
    {
        if ((HAL_GetTick() - start) > timeout_ms)
        {
            /* 自愈：万一完成回调丢了，不能让串口永久静默 */
            (void)HAL_UART_AbortTransmit(&huart1);
            uart_tx_busy_flag = 0U;
            return 0U;
        }
    }

    return 1U;
}

/**
 * @brief   启动一次 DMA 发送（非阻塞，立即返回）
 * @param   data: 数据指针
 * @param   len : 字节数
 * @retval  HAL_OK / HAL_BUSY / HAL_ERROR
 * @note    data 必须一直有效到发送完成（uart_tx_is_busy() 返回 0），
 *          否则会发出被改写的数据。栈上缓冲请改用 uart_printf()。
 *          N6 默认开启 D-Cache，DMA 从内存取数前必须 clean，否则可能发旧内容。
 */
HAL_StatusTypeDef uart_send_dma(const uint8_t *data, uint16_t len)
{
    if ((data == NULL) || (len == 0U))
    {
        return HAL_ERROR;
    }

    if (uart_tx_busy_flag != 0U)
    {
        return HAL_BUSY;
    }

    SCB_CleanDCache_by_Addr((uint32_t *)(uintptr_t)data, (int32_t)len);

    g_tx_buf = data;                     /* 记录：这块在发送完成前不能被征用 */
    uart_tx_busy_flag = 1U;

    if (HAL_UART_Transmit_DMA(&huart1, (uint8_t *)(uintptr_t)data, len) != HAL_OK)
    {
        uart_tx_busy_flag = 0U;
        g_tx_buf = NULL;
        return HAL_ERROR;
    }

    return HAL_OK;
}

/**
 * @brief   查询发送是否进行中
 * @retval  1 = 正在发送，0 = 空闲
 */
uint8_t uart_tx_is_busy(void)
{
    return (uart_tx_busy_flag != 0U) ? 1U : 0U;
}

/**
 * @brief   发送并等待本帧发完（同步语义，内部走 DMA）
 * @param   data: 数据指针
 * @param   len : 字节数
 * @retval  HAL_OK / HAL_TIMEOUT / 其它 HAL 状态
 */
static HAL_StatusTypeDef uart_write_sync(const uint8_t *data, uint16_t len)
{
    HAL_StatusTypeDef st;

    if ((data == NULL) || (len == 0U))
    {
        return HAL_ERROR;
    }

    if (uart_tx_wait_idle(UART_TX_TIMEOUT_MS) == 0U)
    {
        return HAL_TIMEOUT;
    }

    st = uart_send_dma(data, len);
    if (st != HAL_OK)
    {
        return st;
    }

    return (uart_tx_wait_idle(UART_TX_TIMEOUT_MS) != 0U) ? HAL_OK : HAL_TIMEOUT;
}

/**
 * @brief   发送一段原始数据（阻塞轮询，保留作应急）
 * @param   data: 数据指针
 * @param   len : 字节数
 * @retval  无
 * @note    正常路径请用 uart_send_dma()。本函数只在 DMA 不可用（如启动早期、
 *          通道安全属性未配置）或中断上下文里退化为轮询发送。
 */
void uart_send(const uint8_t *data, uint16_t len)
{
    if ((data == NULL) || (len == 0U))
    {
        return;
    }

    /* 若 DMA 帧正在发，先等它结束，避免抢 gState 导致两边都失败 */
    if (uart_tx_wait_idle(UART_TX_TIMEOUT_MS) == 0U)
    {
        return;
    }

    (void)HAL_UART_Transmit(&huart1, (uint8_t *)(uintptr_t)data, len, UART_TX_TIMEOUT_MS);
}

/**
 * @brief   发送字符串（同步，不含结尾 '\0'）
 * @param   str: 以 '\0' 结尾的字符串
 * @retval  无
 */
void uart_send_string(const char *str)
{
    if (str == NULL)
    {
        return;
    }

    (void)uart_write_sync((const uint8_t *)str, (uint16_t)strlen(str));
}

/**
 * @brief   格式化发送（同步，内部走 DMA）
 * @param   fmt: printf 风格格式串
 * @retval  无
 * @note    用 vsnprintf 在常驻缓冲里格式化后交给 DMA：
 *          - 不经过 stdout，与本工程是否启用 MicroLIB 无关；
 *          - 整帧一次搬运，CPU 不参与逐字节轮询；
 *          - 超过 UART_PRINTF_BUF_SIZE 的部分被截断。
 *          不可重入（共用 uart_tx_buf），且会阻塞到本帧发完（128B@115200 约 11ms）。
 */
void uart_printf(const char *fmt, ...)
{
    va_list ap;
    int n;

    if (fmt == NULL)
    {
        return;
    }

    /* 缓冲是共享的：上一帧没发完就格式化会踩掉正在发送的数据 */
    if (uart_tx_wait_idle(UART_TX_TIMEOUT_MS) == 0U)
    {
        return;
    }

    va_start(ap, fmt);
    n = vsnprintf(uart_tx_buf, sizeof(uart_tx_buf), fmt, ap);
    va_end(ap);

    if (n <= 0)
    {
        return;
    }

    if (n >= (int)sizeof(uart_tx_buf))
    {
        n = (int)sizeof(uart_tx_buf) - 1;   /* 已截断 */
    }

    (void)uart_write_sync((const uint8_t *)uart_tx_buf, (uint16_t)n);
}

/**
 * @brief   发送完成回调（DMA 搬完 + 最后一个字节移位完成）
 * @param   huart: UART句柄指针
 * @retval  无
 */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == UART_UX)
    {
        g_tx_buf = NULL;                 /* 缓冲可被接收侧征用了 */
        uart_tx_busy_flag = 0U;
    }
}

/**
 * @brief   错误回调
 * @param   huart: UART句柄指针
 * @retval  无
 * @note    ① 发送出错要放开忙标志，否则串口永久 HAL_BUSY。
 *          ② 接收错误（ORE/FE/NE/PE）后 HAL 已关闭 RXNEIE、RxState 复位为 READY，
 *             不在这里重启就永久失联 —— 这是逐字节/IDLE 中断收包最常见的“串口突然没反应”。
 */
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == UART_UX)
    {
        g_tx_buf = NULL;
        uart_tx_busy_flag = 0U;

#if UART_EN_RX
        /* 只处理接收类错误；发送 DMA 错误不去打断正在进行的接收 */
        if ((huart->ErrorCode & (HAL_UART_ERROR_PE | HAL_UART_ERROR_NE |
                                 HAL_UART_ERROR_FE | HAL_UART_ERROR_ORE)) != 0U)
        {
            __HAL_UART_CLEAR_FLAG(huart, UART_CLEAR_OREF | UART_CLEAR_FEF |
                                         UART_CLEAR_NEF  | UART_CLEAR_PEF);
            huart->ErrorCode = HAL_UART_ERROR_NONE;

            if (huart->RxState != HAL_UART_STATE_READY)
            {
                (void)HAL_UART_AbortReceive(huart);   /* 强制复位，避免带着错误状态重启 */
            }

            (void)HAL_UARTEx_ReceiveToIdle_IT(huart, g_rx_buf[g_rx_idx], UART_RX_BUF_SIZE);
        }
#endif
    }
}
