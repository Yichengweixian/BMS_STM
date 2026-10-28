#include "adbms1818.h"
#include "uart.h"
#include "string.h"
#include "stdint.h"

ADBMS1818_Reg bms1818_Reg={0};
bool g_auto_balance_enabled = false; // 自动均衡总开关
float g_balance_threshold = 0.2f;   // 默认压差阈值 200mV

void BMS1818_Delay_us(uint16_t nus){
	uint8_t i;
     while(nus --)
     {
       for(i =0;i<0x16;i++);
		 }
}

void spi_WR_byte(uint8_t *tx_Data, uint8_t *rx_data, uint8_t len)
{
    HAL_SPI_TransmitReceive(&hspi5, tx_Data, rx_data, len, HAL_MAX_DELAY);
}

uint8_t spi_WR_byte2(uint8_t data)
{
    uint8_t rx;
    HAL_SPI_TransmitReceive(&hspi5, &data, &rx, 1, HAL_MAX_DELAY);
    return rx;
}


uint16_t ADBMS_CalcPEC(uint8_t *data, uint8_t len)
{
    uint16_t remainder = 0x0010;   // 初始值，符合文档规范
    uint8_t i, bit;

    // 处理每个数据字节
    for (i = 0; i < len; i++) {
        // 当前数据字节与remainder高位异或（文档第57页算法）
        remainder ^= ((uint16_t)data[i] << 7);

        // 8位迭代计算（每个字节8次位操作）
        for (bit = 0; bit < 8; bit++) {
            // 检查第14位（0x4000），决定是否应用多项式
            if (remainder & 0x4000) {
                // 第14位为1：左移并异或多项式0x4599
                remainder = (remainder << 1) ^ 0x4599;
            } else {
                // 第14位为0：仅左移
                remainder <<= 1;
            }
        }
    }

    // 返回16位PEC：15位CRC左移1位（低位补0）
    return (remainder & 0x7FFF) << 1;
}


void ADBMS181x_write_cmd(uint16_t cmd,uint8_t wakeup){
	uint8_t Mcmd[8]={0};
	uint8_t databuf[4];
	uint16_t cmd_pec;
	Mcmd[0]=(uint8_t)(cmd>>8);
	Mcmd[1]=(uint8_t)cmd;
	cmd_pec = ADBMS_CalcPEC(Mcmd, 2);
  Mcmd[2] = (uint8_t)(cmd_pec >> 8);
	Mcmd[3] = (uint8_t)(cmd_pec);
//	log_debug("SEND RAW: ");
//	  for (int i = 0; i < 8; i++)
//	  {
//		  log_debug("%02X ", Mcmd[i]);
//	  }
//	  log_debug("\r\n");
	if(wakeup) wakeup_sleep_cmd(1);
	ADBMS_CS_LOW();
	BMS1818_Delay_us(1); // 满足t5
	spi_WR_byte(Mcmd, databuf, 4);
	BMS1818_Delay_us(1); // 满足t6后再拉高CSB
	ADBMS_CS_HIGH();
}

void ADBMS181x_read_reg(uint16_t cmd,uint8_t *databuf,uint8_t wakeup){
	uint8_t Mcmd[8]={0};
	uint16_t cmd_pec;
	Mcmd[0]=(uint8_t)(cmd>>8);
	Mcmd[1]=(uint8_t)cmd;
	cmd_pec = ADBMS_CalcPEC(Mcmd, 2);
  Mcmd[2] = (uint8_t)(cmd_pec >> 8);
	Mcmd[3] = (uint8_t)(cmd_pec);
//	log_debug("SEND RAW: ");
//	  for (int i = 0; i < 8; i++)
//	  {
//		  log_debug("%02X ", Mcmd[i]);
//	  }
//	  log_debug("\r\n");
	if(wakeup) wakeup_sleep_cmd(1);
	ADBMS_CS_LOW();
  spi_WR_byte(Mcmd,databuf,4);
	memset(Mcmd, 0xff, 8);
	spi_WR_byte(Mcmd,databuf,8);
	  ADBMS_CS_HIGH();
}

void wakeup_sleep_cmd(uint8_t chain_N)
{
	  uint8_t cmd[2],status[2];
	  	cmd[0]=0xff;
	  	ADBMS_CS_LOW();
      BMS1818_Delay_us(10);
     	spi_WR_byte(cmd,status,1);
    	if(chain_N>200)BMS1818_Delay_us(300*chain_N/1000);
			else	{BMS1818_Delay_us(80*chain_N);}

    	ADBMS_CS_HIGH();
    	ADBMS_CS_LOW();
			spi_WR_byte(cmd,status,1);
      BMS1818_Delay_us(10*chain_N);
			spi_WR_byte(cmd,status,1);
      BMS1818_Delay_us(10*chain_N);
      ADBMS_CS_HIGH();
}


/*写1818寄存器*/
void ADBMS181x_write_reg(uint16_t cmd,uint8_t *databuf,uint8_t wakeup){
	uint8_t Mcmd[8+4];
	uint8_t buf[8];
	uint16_t cmd_pec;
	Mcmd[0]=(uint8_t)(cmd>>8);
	Mcmd[1]=(uint8_t)cmd;
	cmd_pec = ADBMS_CalcPEC(Mcmd, 2);
  Mcmd[2] = (uint8_t)(cmd_pec >> 8);
	Mcmd[3] = (uint8_t)(cmd_pec);

	for(int i=0;i<6;i++){
		Mcmd[4+i] = databuf[i];//写入数据
	}
	cmd_pec = ADBMS_CalcPEC(&Mcmd[4], 6);
  Mcmd[10] = (uint8_t)(cmd_pec >> 8);
	Mcmd[11] = (uint8_t)(cmd_pec);
//	  log_debug("SEND RAW: ");
//	  for (int i = 0; i < 12; i++)
//	  {
//	      log_debug("%02X ", Mcmd[i]);
//	  }
//	  log_debug("\r\n");
	if(wakeup) wakeup_sleep_cmd(1);
	ADBMS_CS_LOW();
  spi_WR_byte(Mcmd,buf,4+8);

  ADBMS_CS_HIGH();
}

void ADBMS1818_Read_Config(uint16_t config){
	  uint16_t pec_calc, pec_recv;//PEC校验
	  uint8_t rx_buf[8] = {0};
	  ADBMS181x_read_reg(config, rx_buf, 1);
	  BMS1818_Delay_us(3);
	  pec_calc = ADBMS_CalcPEC(rx_buf, 6);
	  pec_recv = ((uint16_t)rx_buf[6] << 8) | rx_buf[7];
}

uint8_t ADBMS181x_Config_GPIO(uint16_t gpio,uint8_t state){
	switch(gpio){
		case BMS1818_GPIO1:
			(state==1)? (bms1818_Reg.CFGARx[0]|=0x08):(bms1818_Reg.CFGARx[0]&=0xF7);
		break;
		case BMS1818_GPIO2:
			(state==1)? (bms1818_Reg.CFGARx[0]|=0x10):(bms1818_Reg.CFGARx[0]&=0xEF);
		break;
		case BMS1818_GPIO3:
			(state==1)? (bms1818_Reg.CFGARx[0]|=0x20):(bms1818_Reg.CFGARx[0]&=0xDF);
		break;
		case BMS1818_GPIO4:
			(state==1)? (bms1818_Reg.CFGARx[0]|=0x40):(bms1818_Reg.CFGARx[0]&=0xBF);
		break;
		case BMS1818_GPIO5:
			(state==1)? (bms1818_Reg.CFGARx[0]|=0x80):(bms1818_Reg.CFGARx[0]&=0x7F);
		break;
		case BMS1818_GPIO6:
			(state==1)? (bms1818_Reg.CFGBRx[0]|=0x01):(bms1818_Reg.CFGBRx[0]&=0xFE);
		break;
		case BMS1818_GPIO7:
			(state==1)? (bms1818_Reg.CFGBRx[0]|=0x02):(bms1818_Reg.CFGBRx[0]&=0xFD);
		break;
		case BMS1818_GPIO8:
			(state==1)? (bms1818_Reg.CFGBRx[0]|=0x04):(bms1818_Reg.CFGBRx[0]&=0xFB);
		break;
		case BMS1818_GPIO9:
			(state==1)? (bms1818_Reg.CFGBRx[0]|=0x08):(bms1818_Reg.CFGBRx[0]&=0xF7);
		break;
		default:

		return 0;
	}
	return 1;
}

void ADBMS1818_EnableVREF2(void)
{
	uint8_t tx[12];
	    uint8_t rx_dummy[12];
	    uint16_t pec;

	    /* --------- WRCFGA Command (0x0001) --------- */
	    tx[0] = 0x00;
	    tx[1] = 0x01;

	    pec = ADBMS_CalcPEC(tx, 2);
	    tx[2] = (uint8_t)(pec >> 8);
	    tx[3] = (uint8_t)(pec & 0xFF);

	    /* --------- CFGA Data --------- */
	    tx[4] = 0xFE;   // REFON=1, VREF2ON=1
	    tx[5] = 0x00;
	    tx[6] = 0x00;
	    tx[7] = 0x00;
	    tx[8] = 0x00;
	    tx[9] = 0x00;

	    pec = ADBMS_CalcPEC(&tx[4], 6);
	    tx[10] = (uint8_t)(pec >> 8);
	    tx[11] = (uint8_t)(pec & 0xFF);
//		  printf("SEND RAW: ");
//		  for (int i = 0; i < 12; i++)
//		  {
//		      printf("%02X ", tx[i]);
//		  }
//		  printf("\r\n");
	    /* --------- SPI Transaction --------- */
	    ADBMS_CS_LOW();
	    spi_WR_byte(tx, rx_dummy, 12);
	    ADBMS_CS_HIGH();

	    /* 手册要求参考电压稳定时间 */
	    BMS1818_Delay_us(5);
}





/*转换所有电池电压
在7Khz下需要 3ms 建议等待6ms以上
MD ADC模式
CHG

*/
void ADBMS1818_ADCV(uint8_t MD,uint8_t CH,uint8_t DCP){
	uint16_t cmd=0;
	cmd|=(DCP<<4);
	cmd|=(MD<<7);
	cmd|=(CH);
  cmd|=ADCV;
  ADBMS181x_write_cmd(cmd,1);
}

/**
 * @brief 读取指定电池的电压
 * @param cell_num 电池序号 (1-18)
 * @param print_pec 是否打印PEC校验信息 (1=打印, 0=不打印)
 * @return uint16_t 电池电压值 *10000(单位: V)，读取失败返回-1.0f
 */
uint16_t ADBMS1818_ReadCellVoltage(uint8_t cell_num, uint8_t print_pec) {
    uint8_t Mcmd[8] = {0};
    uint16_t pec_calc, pec_recv;
    uint16_t raw_voltage = 0;

    // 1. 参数有效性检查
    if(cell_num < 1 || cell_num > 18) {
        if(print_pec) {
            uart_printf("错误: 电池编号超出范围 (1-18)!\r\n");
        }
        return 0;
    }

    // 2. 启动所有电池的ADC转换
    ADBMS1818_ADCV(MD_422HZ_1KHZ, CH_ALL, 0);

    // 3. 等待转换完成
    BMS1818_Delay_us(10000);

    // 4. 计算电池所在的寄存器组和组内位置
    uint8_t reg_group = (cell_num - 1) / 3;          // 寄存器组索引 (0-5)
    uint8_t cell_in_group = (cell_num - 1) % 3;     // 组内位置 (0-2)

    // 5. 定义各寄存器组的读取命令
    uint16_t read_cmds[6] = {RDCVA, RDCVB, RDCVC, RDCVD, RDCVE, RDCVF};
    uint16_t read_cmd = read_cmds[reg_group];

    // 7. 读取对应的寄存器组
    ADBMS181x_read_reg(read_cmd, Mcmd, 0);
    // 8. 计算并验证PEC
    pec_calc = ADBMS_CalcPEC(Mcmd, 6);
    pec_recv = ((uint16_t)Mcmd[6] << 8) | Mcmd[7];

    // 9. 根据PEC校验结果处理
    if(pec_calc == pec_recv) {
        // PEC校验通过
        raw_voltage = Mcmd[cell_in_group * 2] | ((uint16_t)Mcmd[cell_in_group * 2 + 1] << 8);


     //  printf("%.4fV\r\n", voltage_v);
        return raw_voltage;
    } else {
        // PEC校验失败
        return 0;  // 返回错误值
    }
}

/**
 * @brief  设置单节电池的放电状态 (不覆盖原有配置)
 * @param  cell_num: 电池序号 1 ~ 18
 * @param  state:    1-开启放电, 0-关闭放电
 */
void ADBMS1818_SetCellDischarge(uint8_t cell_num, uint8_t state)
{
    uint8_t tx[12] = {0};
    uint8_t rx[12] = {0};
    uint8_t cfg_data[6] = {0}; // 用于暂存读回来的6字节配置
    uint16_t pec;

    if (cell_num < 1 || cell_num > 18) return;

    /* =======================================================
     * 针对电池 1 ~ 12 (操作配置寄存器组 A)
     * ======================================================= */
    if (cell_num >= 1 && cell_num <= 12)
    {
        // ----------------- 第1步：读 (Read RDCFGA) -----------------
        tx[0] = 0x00;
        tx[1] = 0x02; // RDCFGA 命令
        pec = ADBMS_CalcPEC(tx, 2);
        tx[2] = (uint8_t)(pec >> 8);
        tx[3] = (uint8_t)(pec & 0xFF);
        // tx[4] ~ tx[11] 保持为0，作为提供SPI时钟的dummy byte

        ADBMS_CS_LOW();
        spi_WR_byte(tx, rx, 12);
        ADBMS_CS_HIGH();
        HAL_Delay(1); // 视SPI速度可适当缩短

        // rx[4] ~ rx[9] 就是当前的 CFGAR0 ~ CFGAR5
        for (int i = 0; i < 6; i++) {
            cfg_data[i] = rx[4 + i];
            uart_printf("[DEBUG] cfg_data[%d] = 0x%02X\r\n", i, cfg_data[i]);
        }

        // ----------------- 第2步：改 (Modify) -----------------
        if (cell_num <= 8) // 修改 CFGAR4 (cfg_data[4])
        {
            if (state == 1)
                cfg_data[4] |=  (1 << (cell_num - 1)); // 按位或，仅将该位置1
            else
                cfg_data[4] &= ~(1 << (cell_num - 1)); // 按位与反，仅将该位清0
        }
        else // 修改 CFGAR5 (cfg_data[5])
        {
            if (state == 1)
                cfg_data[5] |=  (1 << (cell_num - 9));
            else
                cfg_data[5] &= ~(1 << (cell_num - 9));
        }

        // ----------------- 第3步：写 (Write WRCFGA) -----------------
        tx[0] = 0x00;
        tx[1] = 0x01; // WRCFGA 命令
        pec = ADBMS_CalcPEC(tx, 2);
        tx[2] = (uint8_t)(pec >> 8);
        tx[3] = (uint8_t)(pec & 0xFF);

        // 装载修改后的配置数据
        for (int i = 0; i < 6; i++) {
            tx[4 + i] = cfg_data[i];
        }
		tx[4]=0xFE;
		tx[5]=0x00;
        pec = ADBMS_CalcPEC(&tx[4], 6);
        tx[10] = (uint8_t)(pec >> 8);
        tx[11] = (uint8_t)(pec & 0xFF);

        ADBMS_CS_LOW();
        spi_WR_byte(tx, rx, 12);
        ADBMS_CS_HIGH();
    }
    /* =======================================================
     * 针对电池 13 ~ 18 (操作配置寄存器组 B)
     * ======================================================= */
    else
    {
        // ----------------- 第1步：读 (Read RDCFGB) -----------------
        tx[0] = 0x00;
        tx[1] = 0x26; // RDCFGB 命令
        pec = ADBMS_CalcPEC(tx, 2);
        tx[2] = (uint8_t)(pec >> 8);
        tx[3] = (uint8_t)(pec & 0xFF);

        ADBMS_CS_LOW();
        spi_WR_byte(tx, rx, 12);
        ADBMS_CS_HIGH();
        HAL_Delay(1);

        // rx[4] ~ rx[9] 就是当前的 CFGBR0 ~ CFGBR5
        for (int i = 0; i < 6; i++) {
            cfg_data[i] = rx[4 + i];
        }

        // ----------------- 第2步：改 (Modify) -----------------
        if (cell_num <= 16) // 修改 CFGBR0 (cfg_data[0])
        {
            if (state == 1)
                cfg_data[0] |=  (1 << ((cell_num - 13) + 4)); // 注意：DCC13位于Bit4，所以要 +4
            else
                cfg_data[0] &= ~(1 << ((cell_num - 13) + 4));
        }
        else // 修改 CFGBR1 (cfg_data[1])
        {
            if (state == 1)
                cfg_data[1] |=  (1 << (cell_num - 17));
            else
                cfg_data[1] &= ~(1 << (cell_num - 17));
        }

        // ----------------- 第3步：写 (Write WRCFGB) -----------------
        tx[0] = 0x00;
        tx[1] = 0x24; // WRCFGB 命令
        pec = ADBMS_CalcPEC(tx, 2);
        tx[2] = (uint8_t)(pec >> 8);
        tx[3] = (uint8_t)(pec & 0xFF);

        // 装载修改后的配置数据
        for (int i = 0; i < 6; i++) {
            tx[4 + i] = cfg_data[i];
        }

        pec = ADBMS_CalcPEC(&tx[4], 6);
        tx[10] = (uint8_t)(pec >> 8);
        tx[11] = (uint8_t)(pec & 0xFF);

        ADBMS_CS_LOW();
        spi_WR_byte(tx, rx, 12);
        ADBMS_CS_HIGH();
    }
}

/**
 * @brief 自动均衡核心状态机 (建议在 main.c 的 100ms 定时器里调用)
 */
void AutoBalance_Run(float v1, float v2, float v3) {
    // 1. 如果没开自动均衡，直接退出，把控制权交给手动指令
    if (!g_auto_balance_enabled) {
        return;
    }

    // 2. ⭐️ 工业级底层防呆：极度欠压保护
    // 如果任意一节电池电压已经低得离谱（比如低于 3.0V），绝对禁止均衡放电！
    // 否则本来就没电的电池会被彻底榨干。
    if (v1 < 3.0f || v2 < 3.0f || v3 < 3.0f) {
        ADBMS1818_SetCellDischarge(1, false);
        ADBMS1818_SetCellDischarge(2, false);
        ADBMS1818_SetCellDischarge(3, false);
        return;
    }

    // 3. 木桶效应：找出最低电压
    float min_v = v1;
    if (v2 < min_v) min_v = v2;
    if (v3 < min_v) min_v = v3;

    // 4. 阈值判断与硬件执行 (直接调用你写好的驱动)
    ADBMS1818_SetCellDischarge(1, (v1 - min_v) >= g_balance_threshold);
    ADBMS1818_SetCellDischarge(7, (v2 - min_v) >= g_balance_threshold);
    ADBMS1818_SetCellDischarge(13, (v3 - min_v) >= g_balance_threshold);
}
