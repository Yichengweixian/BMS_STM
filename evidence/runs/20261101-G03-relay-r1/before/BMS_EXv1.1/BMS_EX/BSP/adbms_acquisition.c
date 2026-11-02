#include "adbms_acquisition.h"
#include "main.h"
#include <string.h>
extern SPI_HandleTypeDef hspi5;
#define SPI_TIMEOUT_MS 10U
#define CONVERSION_TIMEOUT_MS 20U
static void cs(uint8_t high)
{ HAL_GPIO_WritePin(ADBMS_CS_GPIO_Port,ADBMS_CS_Pin,high?GPIO_PIN_SET:GPIO_PIN_RESET); }
static uint32_t transfer(uint8_t *tx,uint8_t *rx,uint16_t len)
{
    HAL_StatusTypeDef st=HAL_SPI_TransmitReceive(&hspi5,tx,rx,len,SPI_TIMEOUT_MS);
    return st==HAL_OK?0U:(MEAS_IO | (st==HAL_TIMEOUT?MEAS_TIMEOUT:0U));
}
static void command_bytes(uint16_t cmd,uint8_t out[4])
{
    uint16_t pec;
    out[0]=(uint8_t)(cmd>>8); out[1]=(uint8_t)cmd;
    pec=Meas_Pec15(out,2); out[2]=(uint8_t)(pec>>8); out[3]=(uint8_t)pec;
}
static uint32_t command(uint16_t cmd)
{
    uint8_t tx[4],rx[4]; uint32_t st;
    command_bytes(cmd,tx); cs(0); st=transfer(tx,rx,4); cs(1); return st;
}
static uint32_t read_group(uint16_t cmd,uint8_t frame[8])
{
    uint8_t tx[12],rx[12]={0}; uint32_t st;
    memset(tx,0xff,sizeof tx); command_bytes(cmd,tx);
    cs(0); st=transfer(tx,rx,12); cs(1);
    if (st) return st; /* Partial RX must never look like a complete frame. */
    memcpy(frame,rx+4,8);
    if (Meas_Pec15(frame,6)!=(uint16_t)(((uint16_t)frame[6]<<8)|frame[7])) return MEAS_PEC;
    return 0;
}
static uint32_t write_config(uint16_t cmd,const uint8_t data[6])
{
    uint8_t tx[12],rx[12]; uint16_t pec; uint32_t st;
    command_bytes(cmd,tx); memcpy(tx+4,data,6); pec=Meas_Pec15(data,6);
    tx[10]=(uint8_t)(pec>>8); tx[11]=(uint8_t)pec;
    cs(0); st=transfer(tx,rx,12); cs(1); return st;
}
static uint32_t prepare(void)
{
    /* GPIO pull-downs off, REFON=1, ADCOPT=0, all discharge bits zero.
       GPIO readback is pin logic level, NOT the written pull-down control.
       Exclude GPIO/DTEN/MUTE status bits; still check REFON, ADCOPT,
       thresholds, DCC, DCTO and redundancy settings (datasheet Table 72). */
    const uint8_t a[6]={0xfc,0,0,0,0,0},b[6]={0x0f,0,0,0,0,0};
    uint8_t frame[8]; uint32_t st;
    cs(0); HAL_Delay(1); cs(1); HAL_Delay(1); /* wake and settle, one device */
    if ((st=write_config(0x0001,a))!=0) return st;
    if ((st=write_config(0x0024,b))!=0) return st;
    HAL_Delay(5); /* reference startup, independent of ADC conversion wait */
    if ((st=read_group(0x0002,frame))!=0) return st;
    if ((frame[0]&0x05U)!=(a[0]&0x05U) || memcmp(frame+1,a+1,5)!=0)
        return MEAS_CONFIG;
    if ((st=read_group(0x0026,frame))!=0) return st;
    if ((frame[0]&0xf0U)!=(b[0]&0xf0U) ||
        (frame[1]&0x7fU)!=(b[1]&0x7fU) || memcmp(frame+2,b+2,4)!=0)
        return MEAS_CONFIG;
    return 0;
}
static uint32_t convert(uint16_t clear_cmd,uint16_t start_cmd,uint32_t *begin,uint32_t *end)
{
    uint8_t tx[4],rx[4],dummy=0xff,busy=0; uint32_t st;
    *begin=HAL_GetTick();
    st=command(clear_cmd); /* Unconverted register stays 0xffff, not old data. */
    if (!st) st=command(start_cmd);
    if (!st) {
        command_bytes(0x0714,tx); /* PLADC; keep CS low through polling. */
        cs(0); st=transfer(tx,rx,4);
        while (!st) {
            st=transfer(&dummy,&busy,1);
            if (st || busy==0xffU) break;
            if ((uint32_t)(HAL_GetTick()-*begin)>=CONVERSION_TIMEOUT_MS) {st=MEAS_TIMEOUT; break;}
            HAL_Delay(1);
        }
        cs(1);
    }
    *end=HAL_GetTick();
    if ((uint32_t)(*end-*begin)>CONVERSION_TIMEOUT_MS) st|=MEAS_TIMEOUT;
    return st;
}
static void read_channel(MeasSample *s,uint16_t cmd,unsigned index)
{
    uint8_t frame[8]; uint32_t st;
    if (s->status) return;
    st=read_group(cmd,frame); s->status|=st;
    if (!(st&MEAS_IO)) Meas_Decode(s,frame,index);
}
void Afe_Acquire(MeasSample s[MEAS_CHANNELS])
{
    uint32_t st,begin=HAL_GetTick(),end; unsigned i;
    st=prepare(); end=HAL_GetTick();
    for (i=0;i<MEAS_CHANNELS;++i) if (i!=MEAS_MCU_I) {
        memset(&s[i],0,sizeof s[i]); s[i].start_ms=begin; s[i].end_ms=end; s[i].status=st;
    }
    if (st) return;
    st=convert(0x0711,0x0361,&begin,&end); /* MD=2, cells 1/7/13, DCP=0 */
    for(i=MEAS_CELL1;i<=MEAS_CELL13;++i) {s[i].start_ms=begin;s[i].end_ms=end;s[i].status=st;}
    read_channel(&s[MEAS_CELL1],0x0004,0);
    read_channel(&s[MEAS_CELL7],0x0008,0);
    read_channel(&s[MEAS_CELL13],0x0009,0);
    st=convert(0x0712,0x0560,&begin,&end); /* MD=2, all AUX */
    for (i=MEAS_AFE_I;i<MEAS_CHANNELS;++i) if (i!=MEAS_MCU_I) {
        s[i].start_ms=begin; s[i].end_ms=end; s[i].status=st;
    }
    /* Each record retains its whole eight-byte register frame, including PEC. */
    read_channel(&s[MEAS_AFE_I],0x000c,0);
    read_channel(&s[MEAS_TEMP1],0x000c,1);
    read_channel(&s[MEAS_TEMP2],0x000c,2);
    read_channel(&s[MEAS_TEMP3],0x000e,0);
    read_channel(&s[MEAS_REF2],0x000e,2);
}
