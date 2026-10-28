#include "oled_driver.h"

#include "oled_font.h"  	 


#include <stdio.h>  
#include <stdarg.h>
#include <stdbool.h>
extern I2C_HandleTypeDef hi2c4;

#define OLED_ADDRESS	0x78 

/* 单次 I2C 写的数据块大小。必须 ≤255（HAL 的 NBYTES 字段是 8 位）：
   >255 时 HAL 会走 RELOAD 分段，本板实测 1024 字节一次写会返回 HAL_ERROR。 */
#define OLED_CHUNK_SIZE   128u




// 单缓冲区：绘制和送屏用的是同一块 1KB 显存
__attribute__((aligned(32))) uint8_t OLED_Buffer[OLED_BUFFER_SIZE] = {0};

/* 显示偏移（0xD3 的 A[5:0]）：把 RAM 第 0 行整体挪到屏幕第几行。
   本模组玻璃映射比标准 128x64 低 6 行，实测两组数据：
     0xD3=0x00(0)  → 画面下偏 6 行
     0xD3=0xF7(55) → 画面跑到最底部
   两式解得偏移需取 64-6 = 58(0x3A)，此时 RAM 第 0 行正好落在屏幕第 0 行。
   换屏/换批次模组时只调这一个宏：画面整体偏低就加大，整体偏高就减小。 */
#define OLED_DISPLAY_OFFSET     0x30

// OLED命令数组（SSD1306 128x64）—— 0xAF 单独在 OLED_Init 里最后下发
static const uint8_t CMD_Data[] = {
    0xAE,              /* Display OFF */

    0x20, 0x00,        /* 水平寻址模式：整屏 1024 字节连续写入的前提 */
    0x21, 0x00, 0x7F,  /* 列范围 0~127 */
    0x22, 0x00, 0x07,  /* 页范围 0~7 */
    0x00, 0x10, 0x40, 0xB0, /* 列/行/页指针全归零（水平模式下无副作用） */

    0x81, 0xFF,        /* 对比度 255 */
    0xA1,              /* 段重映射（水平镜像） */
    0xA6,              /* 正常显示（非反白） */
    0xA4,              /* 输出跟随 GDDRAM 内容 */
    0xA8, 0x3F,        /* Multiplex = 63 -> 64 行 */
    0xC8,              /* COM 反向扫描（垂直镜像） */
    0xD3, OLED_DISPLAY_OFFSET, /* 显示偏移：本模组实测值，见上方宏 */
    0xD5, 0xF0,        /* 时钟分频=1 / 振荡频率=15 */
    0xD9, 0xF1,        /* 预充电周期 */
    0xDA, 0x12,        /* 交替 COM 引脚配置（128x64） */
    0xDB, 0x30,        /* VCOMH 去选电平 */
    0x8D, 0x14         /* ★电荷泵 ON：0x10=关、0x14=开，写错就是整屏黑 */
};

static const uint8_t CMD_DisplayOn[] = { 0xAF };

#define OLED_I2C_READY_TIMEOUT_MS   100u   /* 1KB@400kHz 约 25ms，留足余量 */

/**
 * @brief  等待 I2C 外设回到 READY 状态
 * @retval true=就绪  false=超时
 */
static bool OLED_I2C_WaitReady(uint32_t timeout_ms)
{
    uint32_t tick = HAL_GetTick();

    while (hi2c4.State != HAL_I2C_STATE_READY) {
        if ((HAL_GetTick() - tick) >= timeout_ms) {
            return false;
        }
    }

    return true;
}

/**
 * @brief  I2C 总线异常恢复：复位外设并沿用原 Init 结构体重新初始化
 */
static void OLED_I2C_Recover(void)
{
    (void)HAL_I2C_DeInit(&hi2c4);
    (void)HAL_I2C_Init(&hi2c4);
}

/**
 * @brief  阻塞方式下发一段命令（初始化阶段用，时序确定）
 * @retval HAL 状态：HAL_ERROR 基本等价于"从机没应答(NACK)"
 */
static HAL_StatusTypeDef OLED_I2C_WriteCmdBlocking(const uint8_t *cmd, uint16_t len)
{
    if (!OLED_I2C_WaitReady(OLED_I2C_READY_TIMEOUT_MS)) {
        OLED_I2C_Recover();
        if (!OLED_I2C_WaitReady(OLED_I2C_READY_TIMEOUT_MS)) {
            return HAL_BUSY;                      /* 总线长期不可用，避免死等 */
        }
    }

    return HAL_I2C_Mem_Write(&hi2c4, OLED_ADDRESS, 0x00, I2C_MEMADD_SIZE_8BIT,
                             (uint8_t *)cmd, len, 50);
}

// 发送OLED初始化命令
/* 初始化序列只有 22 字节（<1ms），必须用阻塞方式：一旦 DMA 完成回调不来，
   电荷泵(0x8D,0x14)、水平寻址(0x20,0x00)这些关键命令就一条都没生效，
   表现就是"整屏全黑、推什么数据都不显示"。 */
void WriteCmd(void)
{
    (void)OLED_I2C_WriteCmdBlocking(CMD_Data, sizeof(CMD_Data));
}

/**
 * 非阻塞整屏刷新（DMA 分块链式发送）
 *
 * 为什么还要分块：HAL 的 NBYTES 只有 8 位，>255 字节会走 RELOAD 分段，
 * 本板实测这条路走不通（DMA 回调永远不来 / 返回 HAL_ERROR）。
 * 所以拆成 8 × 128 字节，一块发完在回调里接下一块。
 *
 * 调用即返回，整帧约 8 × 12ms（SCL≈100kHz）。调用频率低于帧耗时时，
 * 上一帧没发完的这次调用会被直接丢弃（单缓冲，避免撕裂）。
 * 2Hz 刷新（500ms/帧）余量充足，不会丢帧。
 */
static volatile uint8_t  oled_dma_active = 0;    /* 1 = 正在发一帧 */
static volatile uint16_t oled_dma_off    = 0;    /* 下一块在 OLED_Buffer 中的偏移 */
static volatile uint32_t oled_dma_tick   = 0;    /* 本帧启动时刻，用于超时自愈 */

#define OLED_FRAME_TIMEOUT_MS   500u             /* > 一帧耗时(≈100ms)，DMA 掉了也能自愈 */

void OLED_Refresh(void)
{
    /* 超时自愈：回调没来（DMA 异常）时不要把刷新永久卡死 */
    if (oled_dma_active && ((HAL_GetTick() - oled_dma_tick) > OLED_FRAME_TIMEOUT_MS)) {
        oled_dma_active = 0;
    }

    if (oled_dma_active) {
        return;                                  /* 上一帧还在发，丢弃本次（单缓冲防撕裂） */
    }

    if (hi2c4.State != HAL_I2C_STATE_READY) {
        return;                                  /* 总线被占用（比如刚发过命令），下帧再试 */
    }

    SCB_CleanDCache_by_Addr((uint32_t *)OLED_Buffer, OLED_BUFFER_SIZE);

    oled_dma_off  = 0;
    oled_dma_tick = HAL_GetTick();
    oled_dma_active = 1;

    if (HAL_I2C_Mem_Write_DMA(&hi2c4, OLED_ADDRESS, 0x40, I2C_MEMADD_SIZE_8BIT,
                              &OLED_Buffer[oled_dma_off], OLED_CHUNK_SIZE) != HAL_OK) {
        oled_dma_active = 0;                     /* 启动失败：放弃本帧，下一帧再试 */
    }
}

/**
 * @brief 阻塞等待当前帧发完（初始化阶段发 0xAF 之前必须等，否则会抢总线）
 */
static void OLED_WaitFrameDone(uint32_t timeout_ms)
{
    uint32_t tick = HAL_GetTick();

    while (oled_dma_active) {
        if ((HAL_GetTick() - tick) > timeout_ms) {
            oled_dma_active = 0;                 /* 超时：放弃等待，避免卡死 */
            break;
        }
    }
}

/* 一块发完 → 接着发下一块；全部发完则清标志 */
void HAL_I2C_MemTxCpltCallback(I2C_HandleTypeDef *hi2c)
{
    if ((hi2c->Instance != hi2c4.Instance) || (oled_dma_active == 0U)) {
        return;
    }

    oled_dma_off += OLED_CHUNK_SIZE;

    if (oled_dma_off >= OLED_BUFFER_SIZE) {
        oled_dma_active = 0;                     /* 整帧发送完毕 */
        return;
    }

    if (HAL_I2C_Mem_Write_DMA(&hi2c4, OLED_ADDRESS, 0x40, I2C_MEMADD_SIZE_8BIT,
                              &OLED_Buffer[oled_dma_off], OLED_CHUNK_SIZE) != HAL_OK) {
        oled_dma_active = 0;                     /* 续块失败：放弃剩余部分 */
    }
}

/* 总线错误：清标志，否则刷新会永久停滞 */
void HAL_I2C_ErrorCallback(I2C_HandleTypeDef *hi2c)
{
    if (hi2c->Instance == hi2c4.Instance) {
        oled_dma_active = 0;
    }
}

void OLED_Init(void)
{
    WriteCmd();                                   /* 配置命令，阻塞下发 */
    (void)OLED_I2C_WaitReady(OLED_I2C_READY_TIMEOUT_MS);

    /* GDDRAM 上电是随机值。先把整屏清黑推一遍，再点亮 0xAF，就不会闪 */
    for (uint16_t i = 0; i < OLED_BUFFER_SIZE; i++) {
        OLED_Buffer[i] = 0;
    }

    OLED_Refresh();
    OLED_WaitFrameDone(OLED_FRAME_TIMEOUT_MS);    /* 必须等首帧发完再发 0xAF */

    /* 屏上已经是全黑，此刻点亮。0xAF 一定要发成功，否则屏一直是 0xAE 关闭状态 */
    if (OLED_I2C_WriteCmdBlocking(CMD_DisplayOn, sizeof(CMD_DisplayOn)) != HAL_OK) {
        OLED_I2C_Recover();                       /* 总线复位后再试一次点亮 */
        (void)OLED_I2C_WriteCmdBlocking(CMD_DisplayOn, sizeof(CMD_DisplayOn));
    }

    HAL_Delay(100);                               /* 等电荷泵电压稳定 */
}
void OLED_Clear(void)
{
    for (uint16_t i = 0; i < OLED_BUFFER_SIZE; i++)
    {
        OLED_Buffer[i] = 0;
    }
}

void OLED_fill(void)
{
    for (uint16_t i = 0; i < OLED_BUFFER_SIZE; i++)
    {
        OLED_Buffer[i] = 0xFF;
    }
}

void OLED_Draw_Point(uint8_t x, uint8_t y)
{
    if (x >= OLED_WIDTH || y >= OLED_HEIGHT) {
        return; // 坐标超出屏幕范围，直接返回不操作
    }

    uint8_t n = y / 8;
    uint8_t m = y % 8;
    OLED_Buffer[n * OLED_WIDTH + x] |= (1 << m);
}


void OLED_Clear_Point(uint8_t x, uint8_t y)
{
    uint8_t n = y / 8;
    uint8_t m = y % 8;
    OLED_Buffer[n * 128 + x] &= ~(1 << m);
}

void OLED_Apply_Mask(enum OLED_GrayLevel gray)
{
    bool mask[4];
    switch (gray) {
        case OLED_GRAY_0:
            mask[0] = false; mask[1] = false; mask[2] = false; mask[3] = false; break;
        case OLED_GRAY_1:
            mask[0] = true;  mask[1] = false; mask[2] = false; mask[3] = false; break;
        case OLED_GRAY_2:
            mask[0] = true;  mask[1] = false; mask[2] = false; mask[3] = true;  break;
        case OLED_GRAY_3:
            mask[0] = true;  mask[1] = true;  mask[2] = true;  mask[3] = false; break;
        case OLED_GRAY_4:
            mask[0] = true;  mask[1] = true;  mask[2] = true;  mask[3] = true;  break;
        default:
            mask[0] = false; mask[1] = false; mask[2] = false; mask[3] = false; break;
    }

    for (uint8_t y = 0; y < 64; y += 2) {
        for (uint8_t x = 0; x < 128; x += 2) {
            uint16_t idx0 = (y / 8) * 128 + x;
            uint8_t bit0 = 1 << (y % 8);
            uint16_t idx1 = idx0 + 1;
            uint16_t idx2 = ((y + 1) / 8) * 128 + x;
            uint8_t bit2 = 1 << ((y + 1) % 8);
            uint16_t idx3 = idx2 + 1;

            bool p0 = (OLED_Buffer[idx0] & bit0) != 0;
            bool p1 = (OLED_Buffer[idx1] & bit0) != 0;
            bool p2 = (OLED_Buffer[idx2] & bit2) != 0;
            bool p3 = (OLED_Buffer[idx3] & bit2) != 0;

            if (p0 && mask[0])
                OLED_Buffer[idx0] |= bit0;
            else
                OLED_Buffer[idx0] &= ~bit0;

            if (p1 && mask[1])
                OLED_Buffer[idx1] |= bit0;
            else
                OLED_Buffer[idx1] &= ~bit0;

            if (p2 && mask[2])
                OLED_Buffer[idx2] |= bit2;
            else
                OLED_Buffer[idx2] &= ~bit2;

            if (p3 && mask[3])
                OLED_Buffer[idx3] |= bit2;
            else
                OLED_Buffer[idx3] &= ~bit2;
        }
    }
}

void OLED_ShowChar(uint8_t x, uint8_t y, char chr, uint8_t size) {
    if (chr < 32 || chr > 126) chr = '?';
    uint8_t i, j, c = chr - 32;

    if (size == 1) {  // 6x8 字符
        for (i = 0; i < 6; i++) {
            uint8_t line = F6x8[c][i];
            for (j = 0; j < 8; j++) {
                if (line & (1 << j))
                    OLED_Draw_Point(x + i, y + j);
            }
        }
    } else if (size == 2) {  // 8x16 字符
        for (i = 0; i < 8; i++) {
            uint8_t line1 = F8X16[c][i];
            uint8_t line2 = F8X16[c][i + 8];
            for (j = 0; j < 8; j++) {
                if (line1 & (1 << j))
                    OLED_Draw_Point(x + i, y + j);         // 上半部分
                if (line2 & (1 << j))
                    OLED_Draw_Point(x + i, y + j + 8);     // 下半部分
            }
        }
    }
}

void OLED_ShowString(uint8_t x, uint8_t y, const char *str, uint8_t size) {
    uint8_t char_width = (size == 1) ? 6 : 8;

    while (*str) {
        OLED_ShowChar(x, y, *str, size);
        x += char_width;
        if (x > (128 - char_width)) {
            x = 0;
            y += (size == 1) ? 8 : 16;
        }
        str++;
    }
}

void OLED_ShowNum(uint8_t x, uint8_t y, uint32_t num, uint8_t len, uint8_t size) {
    char buf[12];
    snprintf(buf, sizeof(buf), "%0*u", len, num);
    OLED_ShowString(x, y, buf, size);
}

void OLED_ShowBitmap(uint8_t x, uint8_t y, const uint8_t *bmp, uint8_t width, uint8_t height) {
    for (uint8_t i = 0; i < width; i++) {
        for (uint8_t j = 0; j < height; j++) {
            if (bmp[i + (j / 8) * width] & (1 << (j % 8))) {
                OLED_Draw_Point(x + i, y + j);
            }
        }
    }
}
void OLED_Draw_Line(int x0, int y0, int x1, int y1) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy, e2;

    while (1) {
        OLED_Draw_Point(x0, y0);
        if (x0 == x1 && y0 == y1) break;
        e2 = 2 * err;
        if (e2 >= dy) {
            err += dy;
            x0 += sx;
        }
        if (e2 <= dx) {
            err += dx;
            y0 += sy;
        }
    }
}

// 画空心矩形
void OLED_Draw_Rectangle(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1) {
    // 顶边
    OLED_Draw_Line(x0, y0, x1, y0);
    // 底边
    OLED_Draw_Line(x0, y1, x1, y1);
    // 左边
    OLED_Draw_Line(x0, y0, x0, y1);
    // 右边
    OLED_Draw_Line(x1, y0, x1, y1);
}

static void drawCirclePoints(int xc, int yc, int x, int y) {
    OLED_Draw_Point(xc + x, yc + y);
    OLED_Draw_Point(xc - x, yc + y);
    OLED_Draw_Point(xc + x, yc - y);
    OLED_Draw_Point(xc - x, yc - y);
    OLED_Draw_Point(xc + y, yc + x);
    OLED_Draw_Point(xc - y, yc + x);
    OLED_Draw_Point(xc + y, yc - x);
    OLED_Draw_Point(xc - y, yc - x);
}

void OLED_Draw_Circle(int x0, int y0, int r) {
    int x = 0;
    int y = r;
    int d = 1 - r;

    drawCirclePoints(x0, y0, x, y);

    while (x < y) {
        x++;
        if (d < 0) {
            d += 2 * x + 1;
        } else {
            y--;
            d += 2 * (x - y) + 1;
        }
        drawCirclePoints(x0, y0, x, y);
    }
}
void OLED_Fill_Rectangle(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1) {
    for (uint8_t y = y0; y <= y1; y++) {
        for (uint8_t x = x0; x <= x1; x++) {
            OLED_Draw_Point(x, y);
        }
    }
}

static void drawLine(int x_start, int x_end, int y_line) {
    for (int x = x_start; x <= x_end; x++) {
        OLED_Draw_Point(x, y_line);
    }
}

void OLED_Fill_Circle(int x0, int y0, int r) {
    int x = 0;
    int y = r;
    int d = 1 - r;

    drawLine(x0 - r, x0 + r, y0);

    while (x < y) {
        x++;
        if (d < 0) {
            d += 2 * x + 1;
        } else {
            y--;
            d += 2 * (x - y) + 1;
        }

        drawLine(x0 - x, x0 + x, y0 + y);
        drawLine(x0 - x, x0 + x, y0 - y);

        drawLine(x0 - y, x0 + y, y0 + x);
        drawLine(x0 - y, x0 + y, y0 - x);
    }
}

// 画椭圆轮廓，(xc, yc)是中心，rx, ry是半轴长度
void OLED_Draw_Ellipse(int xc, int yc, int rx, int ry) {
    int x = 0, y = ry;
    long rx2 = (long)rx * rx;
    long ry2 = (long)ry * ry;
    long tworx2 = 2 * rx2;
    long twory2 = 2 * ry2;
    long px = 0;
    long py = tworx2 * y;

    // 椭圆第一部分
    long p = (long)(ry2 - (rx2 * ry) + (0.25 * rx2));
    while (px < py) {
        OLED_Draw_Point(xc + x, yc + y);
        OLED_Draw_Point(xc - x, yc + y);
        OLED_Draw_Point(xc + x, yc - y);
        OLED_Draw_Point(xc - x, yc - y);

        x++;
        px += twory2;
        if (p < 0) {
            p += ry2 + px;
        } else {
            y--;
            py -= tworx2;
            p += ry2 + px - py;
        }
    }

    // 椭圆第二部分
    p = (long)(ry2 * (x + 0.5) * (x + 0.5) + rx2 * (y -1) * (y - 1) - rx2 * ry2);
    while (y >= 0) {
        OLED_Draw_Point(xc + x, yc + y);
        OLED_Draw_Point(xc - x, yc + y);
        OLED_Draw_Point(xc + x, yc - y);
        OLED_Draw_Point(xc - x, yc - y);

        y--;
        py -= tworx2;
        if (p > 0) {
            p += rx2 - py;
        } else {
            x++;
            px += twory2;
            p += rx2 - py + px;
        }
    }
}

// 传入三角形三个顶点坐标
void OLED_Draw_Triangle(int x0, int y0, int x1, int y1, int x2, int y2) {
    OLED_Draw_Line(x0, y0, x1, y1);
    OLED_Draw_Line(x1, y1, x2, y2);
    OLED_Draw_Line(x2, y2, x0, y0);
}
void drawQuarterCircle(int xc, int yc, int r, int quadrant) {
    int x = 0;
    int y = r;
    int d = 1 - r;

    while (x <= y) {
        switch (quadrant) {
            case 1: // 左上
                OLED_Draw_Point(xc - y, yc - x);
                OLED_Draw_Point(xc - x, yc - y);
                break;
            case 2: // 右上
                OLED_Draw_Point(xc + x, yc - y);
                OLED_Draw_Point(xc + y, yc - x);
                break;
            case 3: // 右下
                OLED_Draw_Point(xc + y, yc + x);
                OLED_Draw_Point(xc + x, yc + y);
                break;
            case 4: // 左下
                OLED_Draw_Point(xc - x, yc + y);
                OLED_Draw_Point(xc - y, yc + x);
                break;
        }

        if (d < 0) {
            d += 2 * x + 3;
        } else {
            d += 2 * (x - y) + 5;
            y--;
        }
        x++;
    }
}

void OLED_Draw_Rounded_Rectangle(int x0, int y0, int x1, int y1, int radius) {
    if (radius > (x1 - x0) / 2) radius = (x1 - x0) / 2;
    if (radius > (y1 - y0) / 2) radius = (y1 - y0) / 2;

    // 画四条边（减去圆角部分）
    OLED_Draw_Line(x0 + radius, y0, x1 - radius, y0); // 上边
    OLED_Draw_Line(x0 + radius, y1, x1 - radius, y1); // 下边
    OLED_Draw_Line(x0, y0 + radius, x0, y1 - radius); // 左边
    OLED_Draw_Line(x1, y0 + radius, x1, y1 - radius); // 右边

    // 画四个圆角
    drawQuarterCircle(x0 + radius, y0 + radius, radius, 1); // 左上角
    drawQuarterCircle(x1 - radius, y0 + radius, radius, 2); // 右上角
    drawQuarterCircle(x1 - radius, y1 - radius, radius, 3); // 右下角
    drawQuarterCircle(x0 + radius, y1 - radius, radius, 4); // 左下角
}

void OLED_Printf(uint8_t x, uint8_t y, uint8_t size, const char* format, ...)
{
    // 定义一个足够大的缓冲区来存放格式化后的字符串
    // 对于128x64的屏幕，一行最多21个6x8字符或16个8x16字符，128字节足够了
    char buffer[128];

    // 定义一个va_list变量来处理可变参数
    va_list args;

    // 从format参数之后开始初始化va_list
    va_start(args, format);

    // 使用vsnprintf进行格式化，这是sprintf的安全版本
    // 它会将格式化后的字符串输出到buffer中
    vsnprintf(buffer, sizeof(buffer), format, args);

    // 清理va_list
    va_end(args);

    // 调用您已有的函数，将格式化好的字符串显示到OLED上
    OLED_ShowString(x, y, buffer, size);
}


