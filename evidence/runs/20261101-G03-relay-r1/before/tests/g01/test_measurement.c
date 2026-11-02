/* Host-only fault injection of the SAME acquisition/core sources used by Keil. */
#include "main.h"
#include "measurement_core.h"
#include "measurement.h"
#include "adbms_acquisition.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
SPI_HandleTypeDef hspi5;
ADC_HandleTypeDef hadc1;
static uint32_t tick;
static uint32_t ready_tick;
static int fault,adc_fault,cs_high=1,reads,adc_calls;
static uint8_t cfg_a[6],cfg_b[6];
static uint16_t last_cmd;
static char output[65536];
static size_t output_len;
void HAL_GPIO_WritePin(int port,int pin,int value)
{ assert(port==1 && pin==6); cs_high=value; }
void HAL_Delay(uint32_t ms) {tick+=ms;}
uint32_t HAL_GetTick(void) {return tick;}
void uart_printf(const char *fmt,...)
{
    va_list ap; int n;
    va_start(ap,fmt); n=vsnprintf(output+output_len,sizeof output-output_len,fmt,ap); va_end(ap);
    assert(n>0 && (size_t)n<sizeof output-output_len); output_len+=(size_t)n;
}
static void finish_pec(uint8_t frame[8])
{ uint16_t p=Meas_Pec15(frame,6);frame[6]=(uint8_t)(p>>8);frame[7]=(uint8_t)p; }
static void code(uint8_t *p,uint16_t val) {p[0]=(uint8_t)val;p[1]=(uint8_t)(val>>8);}
HAL_StatusTypeDef HAL_SPI_TransmitReceive(SPI_HandleTypeDef *h,uint8_t *tx,uint8_t *rx,uint16_t n,uint32_t timeout)
{
    uint16_t cmd; uint8_t frame[8]={0};
    assert(h==&hspi5 && !cs_high && timeout>0 && timeout<=20);
    if(fault==1) {tick+=timeout;return HAL_TIMEOUT;}
    memset(rx,0,n);
    if(n==1) {assert(last_cmd==0x0714); rx[0]=(fault==2 || (int32_t)(tick-ready_tick)<0)?0:0xff;return HAL_OK;}
    assert(n==4 || n==12);
    assert(Meas_Pec15(tx,2)==(uint16_t)(((uint16_t)tx[2]<<8)|tx[3]));
    cmd=(uint16_t)(((uint16_t)tx[0]<<8)|tx[1]);last_cmd=cmd;
    if(n==4) {
        assert(cmd==0x0711||cmd==0x0712||cmd==0x0361||cmd==0x0560||cmd==0x0714);
        if(cmd==0x0361) ready_tick=tick+2;
        if(cmd==0x0560) ready_tick=tick+5;
        return HAL_OK;
    }
    if(cmd==1||cmd==0x24) {
        assert(Meas_Pec15(tx+4,6)==(uint16_t)(((uint16_t)tx[10]<<8)|tx[11]));
        memcpy(cmd==1?cfg_a:cfg_b,tx+4,6);
        if(cmd==1) assert(tx[8]==0 && tx[9]==0);
        else assert((tx[4]&0xf0)==0 && tx[5]==0); /* no DCC output enabled */
        return HAL_OK;
    }
    if(cmd==2) {
        memcpy(frame,cfg_a,6);
        frame[0]=(uint8_t)((frame[0]&0x05U)|2U); /* GPIO inputs LOW; DTEN HIGH */
        if(fault==3) frame[4]=1;  /* DCC mismatch must still fail */
        if(fault==7) frame[0]&=(uint8_t)~4U; /* REFON mismatch */
        if(fault==8) frame[0]|=1U; /* ADCOPT mismatch */
    } else if(cmd==0x26) {
        memcpy(frame,cfg_b,6);frame[0]&=0xf0U;frame[1]|=0x80U; /* GPIO LOW, MUTE status HIGH */
        if(fault==9) frame[0]|=0x10U; /* DCC13 mismatch */
        if(fault==10) frame[1]|=0x40U; /* FDRF mismatch */
    }
    else {
        ++reads;
        if(fault==5) return HAL_ERROR;
        if(cmd==4||cmd==8||cmd==9) code(frame,38920);
        else if(cmd==0xc) {code(frame,9000);code(frame+2,3231);code(frame+4,3231);}
        else if(cmd==0xe) {code(frame,3231);code(frame+4,30000);}
        else assert(0);
        if(fault==6) memset(frame,0xff,6); /* conversion not accepted; cleared regs */
    }
    finish_pec(frame);
    if(fault==4 && cmd==0xc) frame[7]^=1;
    memcpy(rx+4,frame,8);return HAL_OK;
}
HAL_StatusTypeDef HAL_ADC_Start(ADC_HandleTypeDef *h)
{assert(h==&hadc1);++adc_calls;return adc_fault==1?HAL_ERROR:HAL_OK;}
HAL_StatusTypeDef HAL_ADC_PollForConversion(ADC_HandleTypeDef *h,uint32_t timeout)
{(void)h;assert(timeout==10);++tick;return adc_fault==2?HAL_TIMEOUT:HAL_OK;}
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *h) {(void)h;return adc_fault==5?4095:2048;}
uint32_t HAL_ADC_GetError(ADC_HandleTypeDef *h) {(void)h;return adc_fault==3?1:0;}
HAL_StatusTypeDef HAL_ADC_Stop(ADC_HandleTypeDef *h) {(void)h;return adc_fault==4?HAL_ERROR:HAL_OK;}
static void core_tests(void)
{
    const uint8_t cmd[2]={0,1};
    MeasSample s={0};MeasValue v;char row[320],small[4];uint8_t frame[8]={0};
    assert(Meas_Pec15(cmd,2)==0x3d6e); /* independent datasheet command PEC vector */
    code(frame,38920);finish_pec(frame);Meas_Decode(&s,frame,0);
    v=Meas_Evaluate(&s,MEAS_CELL1,0);assert(v.raw_valid && fabsf(v.estimate-3.892f)<0.00001f);
    frame[7]^=1;Meas_Decode(&s,frame,0);
    v=Meas_Evaluate(&s,MEAS_AFE_I,0);assert(!v.raw_valid && !v.estimate_present && (v.status&MEAS_PEC));
    assert(Meas_Format(row,sizeof row,1,MEAS_AFE_I,&s,0)>0);
    assert(strstr(row,",130,0,,,A,,0,,uncalibrated-v1,")!=NULL);
    { int n=Meas_Format(small,sizeof small,0,MEAS_CELL1,&s,0);assert(n<0 || n>=(int)sizeof small); }
    { int full=Meas_Format(row,sizeof row,0,MEAS_CELL1,&s,0),size;
      for(size=1;size<=full;++size) {int n=Meas_Format(row,(size_t)size,0,MEAS_CELL1,&s,0);assert(n<0||n>=size);} }
    s.status=0;s.raw=9000;v=Meas_Evaluate(&s,MEAS_AFE_I,0);assert(v.raw_valid && fabsf(v.estimate)<0.0001f);
    s.raw=8000;v=Meas_Evaluate(&s,MEAS_AFE_I,0);assert(v.estimate<0);
    s.raw=10000;v=Meas_Evaluate(&s,MEAS_AFE_I,0);assert(v.estimate>0);
    s.raw=2048;v=Meas_Evaluate(&s,MEAS_MCU_I,0);assert(v.raw_valid && v.estimate_present && fabsf(v.sensor_v-0.90021978f)<0.000001f);
    s.raw=4095;v=Meas_Evaluate(&s,MEAS_MCU_I,0);assert(!v.raw_valid && (v.status&MEAS_RANGE));
    s.raw=0;v=Meas_Evaluate(&s,MEAS_MCU_I,0);assert(!v.raw_valid);
    s.raw=3231;v=Meas_Evaluate(&s,MEAS_TEMP1,0);assert(v.raw_valid && v.estimate>25 && v.estimate<26);
    s.raw=0;v=Meas_Evaluate(&s,MEAS_TEMP1,0);assert(!v.raw_valid && !v.estimate_present);
    s.raw=30000;v=Meas_Evaluate(&s,MEAS_TEMP1,0);assert(!v.raw_valid);
    s.raw=65535;v=Meas_Evaluate(&s,MEAS_CELL1,0);assert(!v.raw_valid);
    s.raw=38920;s.end_ms=0xfffffff0U;v=Meas_Evaluate(&s,MEAS_CELL1,0x10);assert(v.raw_valid && v.age_ms==32);
    v=Meas_Evaluate(&s,MEAS_CELL1,0x500);assert(!v.raw_valid && (v.status&MEAS_STALE));
    s.has_raw=0;v=Meas_Evaluate(&s,MEAS_CELL1,s.end_ms);assert(!v.raw_valid && (v.status&MEAS_NO_RAW));
}
static void acquisition_tests(void)
{
    MeasSample s[MEAS_CHANNELS];unsigned i;
    for(fault=0;fault<=10;++fault) {
        memset(s,0,sizeof s);reads=0;Afe_Acquire(s);assert(cs_high);
        for(i=0;i<MEAS_CHANNELS;++i) if(i!=MEAS_MCU_I) {
            MeasValue v=Meas_Evaluate(&s[i],(MeasChannel)i,tick);
            if(fault==0) {assert(v.raw_valid);if(i==MEAS_AFE_I)assert(s[i].end_ms-s[i].start_ms>=5);}
            if(fault==1) assert((s[i].status&MEAS_TIMEOUT) && !s[i].has_raw && !v.raw_valid);
            if(fault==2) assert((s[i].status&MEAS_TIMEOUT) && reads==0 && !s[i].has_raw);
            if(fault>=7) assert((s[i].status&MEAS_CONFIG) && reads==0 && !s[i].has_raw);
            if(fault==3) assert((s[i].status&MEAS_CONFIG) && reads==0 && !s[i].has_raw);
            if(fault==4 && i>=MEAS_AFE_I && i<=MEAS_TEMP2) assert((s[i].status&MEAS_PEC) && s[i].has_raw && !v.raw_valid);
            if(fault==4 && i==MEAS_CELL1) assert(v.raw_valid); /* group-local fault */
            if(fault==5) assert((s[i].status&MEAS_IO) && !s[i].has_raw);
            if(fault==6) assert((v.status&MEAS_RANGE) && s[i].has_raw && !v.raw_valid);
        }
    }
    fault=0;
}
int main(void)
{
    int before;unsigned i;
#ifdef _WIN32
    _setmode(_fileno(stdout),_O_BINARY);
#endif
    core_tests(); acquisition_tests();
    for(adc_fault=0;adc_fault<=5;++adc_fault) {
        tick=0;output_len=0;Measurement_Init();Measurement_Task();
        if(adc_fault==0) assert(strstr(output,",2048,128,1,0.900220,0.000292,A,,0,,uncalibrated-v1,,")!=NULL);
        if(adc_fault==1) assert(strstr(output,",,449,0,,,A,,0,,uncalibrated-v1,,")!=NULL);
        if(adc_fault==2) assert(strstr(output,",,452,0,,,A,,0,,uncalibrated-v1,,")!=NULL);
        if(adc_fault==3||adc_fault==4) assert(strstr(output,",2048,192,0,,,A,,0,,uncalibrated-v1,,")!=NULL);
        if(adc_fault==5) assert(strstr(output,",4095,136,0,,,A,,0,,uncalibrated-v1,,")!=NULL);
    }
    adc_fault=0;fault=1;output_len=0;Measurement_Init();Measurement_Task();
    assert(strstr(output,",2048,128,1,0.900220,0.000292,A,,0,,uncalibrated-v1,,")!=NULL);
    fault=0;tick=0;output_len=0;Measurement_Init();Measurement_Task();
    before=adc_calls;Measurement_Task();assert(adc_calls==before);
    for(i=0;i<3;++i) {HAL_Delay(500);Measurement_Task();}
    fwrite(output,1,output_len,stdout);
    fprintf(stderr,"PASS: core vectors; AFE faults 0..10 including GPIO/DTEN/MUTE read semantics; ADC faults 0..5; independent ADC; scheduler; CSV emitted by production C. SIMULATION ONLY.\n");
    return 0;
}

uint32_t G03_ADC_Profile(void){return 0;}
uint32_t G03_ADC_Calibrated(void){return 0;}
