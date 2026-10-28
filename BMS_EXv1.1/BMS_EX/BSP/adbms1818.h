#ifndef _ADBMS1818_H
#define _ADBMS1818_H


#include "main.h"
#include "stdio.h"
#include <stdbool.h>

extern SPI_HandleTypeDef hspi5;
#define ADBMS_CS_LOW() HAL_GPIO_WritePin(GPIOH,GPIO_PIN_6,GPIO_PIN_RESET)
#define ADBMS_CS_HIGH() HAL_GPIO_WritePin(GPIOH,GPIO_PIN_6,GPIO_PIN_SET)


#define WRCFGA  0x01   //写配置寄存器A
#define WRCFGB  0x24   //写配置寄存器B
#define RDCFGA  0x02   //读配置寄存器A
#define RDCFGB  0x26   //读配置寄存器B

/*读取电压寄存器使用ADBMS181x_rdcv_reg*/
//也可使用下边的快速读取
#define RDCVA   0x04   //读取电压寄存器组A
#define RDCVB   0x06   //读取电压寄存器组B
#define RDCVC   0x08   //读取电压寄存器组C
#define RDCVD   0x0A   //读取电压寄存器组D
#define RDCVE   0x09   //读取电压寄存器组E
#define RDCVF   0x0B   //读取电压寄存器组F

#define RDAUXA  0x0C   //读取辅助寄存器A
#define RDAUXB  0x0E   //读取辅助寄存器B
#define RDAUXC  0x0D   //读取辅助寄存器C
#define RDAUXD  0x0F   //读取辅助寄存器D

#define RDSTATA 0x10   //读取状态寄存器A
#define RDSTATB 0x12   //读取状态寄存器B


#define WRSCTRL 0x14   //写s控制寄存器组
#define RDSCTRL 0x16   //读s控制寄存器组

//comm命令
#define WRCOMM  0x0721  // 写comm寄存器组
#define STCOMM  0x0723  // 启动IIC/SPI通讯
#define RDCOMM  0x0722  // 读取comm寄存器组
//IIC_CMD 寄存器内数据用
#define IW_Start  0x06  //开始
#define IW_Stop   0x01  //停止
#define IW_Null   0x00  //空
#define IW_Nsend  0x07  //不发送 释放总线并忽略之后的数据
#define IR_Start  0x06  //从主机开始
#define IR_Stop   0x01  //从主机停止
#define IR_LOW    0x00  //字节之间SDA为低电平
#define IR_High   0x07  //字节之间SDA为高电平

#define FW_Ack    0x00  //主机写入ACK
#define FW_Nack   0x08  //主机写入NACK
#define FW_NaS    0x09  //主机写入NACK+停止
#define FR_MAck   0x00  //主机读取ACK
#define FR_SAck   0x07  //从机读取ACK
#define FR_SNAck  0x08  //从机读取NAck
#define FR_SAckS  0x01  //从机ACK+主机停止
#define FR_SNAckS 0x09  //从机NACK+主机停止

#define BMS1818_GPIO1     0x0002   // 0x08
#define BMS1818_GPIO2     0x0004   // 0x08<<1
#define BMS1818_GPIO3     0x0008   // 0x08<<2
#define BMS1818_GPIO4   	0x0010	 // 0x08<<3
#define BMS1818_GPIO5  		0x0020   // 0x08<<4
#define BMS1818_GPIO6   	0x0040	 // 0x01
#define BMS1818_GPIO7   	0x0080	 // 0x01<<1
#define BMS1818_GPIO8   	0x0100	 // 0x01<<2
#define BMS1818_GPIO9  		0x0200   // 0x01<<3


#define MD_422HZ_1KHZ   0
#define MD_27KHZ_14KHZ  1
#define MD_7KHZ_3KHZ    2
#define MD_26HZ_2KHZ    3

/*CHG低三位有效*/
#define CHG_ALL            0x00      //GPIO1至GPIO5，第二基准电压，GPIO6至GPIO9
#define CHG_G1G6           0x01      //GPIO1、GPIO6
#define CHG_G2G7           0x02      //....
#define CHG_G3G8           0x03
#define CHG_G4G9           0x04
#define CHG_G5             0x05
#define CHG_VREF2          0x06


/*CH低三位有效*/
#define CH_ALL             0x00      //所有电池
#define CH_V1_7_13         0x01      //电池 1 7 13
#define CH_V2_8_14         0x02      //....
#define CH_V3_9_15         0x03
#define CH_V4_10_16        0x04
#define CH_V5_11_17        0x05
#define CH_V6_12_18        0x06


#define ADCVAX            0x046F   // 0100 0110 1111  //所有电池和GPIO1 GPIO2   (这俩是掩码不能直接使用)
#define ADAX              0x0460   // 0100 0110 0000  //GPIO ADC转换
#define ADCV              0x0260   // 0010 0110 0000  //启动对18节电池的转换

/* --------- NTC 参数（按你电路） --------- */
#define VREF2_VOLT   3.000f      // 实测 VREF2（建议用万用表量）
#define R_UP         9100.0f     // 上拉电阻 9.1k
#define PT_R0        1000.0f     // PT1000
#define PT_ALPHA     0.00385f


typedef struct{
	uint8_t CFGARx[8];
	uint8_t CFGBRx[8];
	uint16_t VREF2;//第二基准电压值
	uint8_t COMM[8];
	/*................*/
}ADBMS1818_Reg;
extern bool g_auto_balance_enabled; // 自动均衡总开关
extern float g_balance_threshold;   // 默认压差阈值 200mV

void spi_WR_byte(uint8_t *tx_Data, uint8_t *rx_data, uint8_t len);
void BMS1818_Delay_us(uint16_t nus);
uint16_t ADBMS_CalcPEC(uint8_t *data, uint8_t len);
uint8_t ADBMS1818_RC_Check(uint8_t* original,uint16_t* target);
void ADBMS181x_write_cmd(uint16_t cmd,uint8_t wakeup);
void ADBMS181x_read_reg(uint16_t cmd,uint8_t *databuf,uint8_t wakeup);
void ADBMS1818_Read_Config(uint16_t config);
void wakeup_sleep_cmd(uint8_t chain_N);
void ADBMS1818_EnableVREF2(void);
void ADBMS1818_EnableGPIO_PULL_UPOFF(void);
uint8_t ADBMS181x_Config_GPIO(uint16_t gpio,uint8_t state);
void ADBMS181x_read_16T(uint16_t *Tdata);
uint16_t ADBMS1818_ReadCellVoltage(uint8_t cell_num, uint8_t print_pec);
void ADBMS1818_SetCellDischarge(uint8_t cell_num, uint8_t state);
void AutoBalance_Run(float v1, float v2, float v3);
#endif
