#ifndef __OLED_DRIVER_H
#define __OLED_DRIVER_H			  	 

#include "stdlib.h"	    	

#include "main.h"
#define OLED_WIDTH 128
#define OLED_HEIGHT 64
#define OLED_BUFFER_SIZE 1024
/* 单缓冲区显存：绘图直接改这块，OLED_Refresh() 直接把它推上屏 */
extern uint8_t OLED_Buffer[OLED_BUFFER_SIZE];
enum OLED_GrayLevel{
	OLED_GRAY_0=0,
	OLED_GRAY_1,
	OLED_GRAY_2,
	OLED_GRAY_3,
    OLED_GRAY_4,
};
typedef enum {
    OLED_FONT_6x8 = 1,
    OLED_FONT_8x16 = 2,
} OLED_FontSize;
void WriteCmd(void);
void OLED_Init(void);
void OLED_Clear(void);
void OLED_fill(void);
void OLED_Refresh(void);           /* 非阻塞：启动 DMA 发送整帧后立即返回（约 100ms 发完） */
void OLED_Draw_Point(uint8_t x,uint8_t y);
void OLED_Clear_Point(uint8_t x,uint8_t y);
void OLED_Apply_Mask(enum OLED_GrayLevel gray);
void OLED_ShowChar(uint8_t x, uint8_t y, char chr, uint8_t size);
void OLED_ShowString(uint8_t x, uint8_t y, const char *str, uint8_t size);
void OLED_ShowNum(uint8_t x, uint8_t y, uint32_t num, uint8_t len, uint8_t size);
void OLED_ShowBitmap(uint8_t x, uint8_t y, const uint8_t *bmp, uint8_t width, uint8_t height);
void OLED_Draw_Circle(int x0, int y0, int r);
void OLED_Draw_Rectangle(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1);
void OLED_Draw_Line(int x0, int y0, int x1, int y1) ;
void OLED_Fill_Circle(int x0, int y0, int r) ;
void OLED_Fill_Rectangle(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1);
void drawQuarterCircle(int xc, int yc, int r, int quadrant) ;
void OLED_Draw_Triangle(int x0, int y0, int x1, int y1, int x2, int y2) ;
void OLED_Draw_Ellipse(int xc, int yc, int rx, int ry) ;
void OLED_Draw_Rounded_Rectangle(int x0, int y0, int x1, int y1, int radius) ;
void OLED_Printf(uint8_t x, uint8_t y, uint8_t size, const char* format, ...);
#endif  
	 



