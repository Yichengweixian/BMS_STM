#include "measurement.h"
#include "firmware_identity.h"
#include "g03_adc_port.h"
#include "nominal_current.h"
#include "measurement_core.h"
#include "adbms_acquisition.h"
#include "main.h"
#include "uart.h"
#include <string.h>
extern ADC_HandleTypeDef hadc1;
static uint32_t seq,last_start;
static uint8_t first;
static uint32_t metadata_profile,metadata_selfcal;
static void metadata(void)
{
    uart_printf("#META,schema=%s,fw=" BMS_DIAG_FIRMWARE ",build=%s %s,cal=%s,period_ms=500,kind=instantaneous_sample\r\n",
                MEAS_SCHEMA,__DATE__,__TIME__,MEAS_CAL_ID);
    uart_printf("#CONFIG,profile=cnn647b-" BMS_DIAG_FIRMWARE ",ADC_profile=%lu,ADC_selfcal=%lu,VREF_nominal=1.8,current_model=%s,zero_nominal_V=0.9,physical_valid=0,sign=unconfirmed\r\n",
        (unsigned long)G03_ADC_Profile(),(unsigned long)G03_ADC_Calibrated(),CURRENT_MODEL_ID);
    uart_printf("#FIELDS,type,seq,channel,start_ms,end_ms,age_ms,raw,status,raw_valid,sensor_V_nominal,estimate,unit,physical_value,physical_valid,reference,cal_id,frame_hex,wire_pec15\r\n");
    metadata_profile=G03_ADC_Profile();metadata_selfcal=G03_ADC_Calibrated();
}
void Measurement_Init(void)
{
    seq=0; first=1; last_start=HAL_GetTick();
    uart_printf("#BOOT," BMS_DIAG_FIRMWARE ",tick=%lu\r\n",(unsigned long)last_start);
    metadata();
}
static void adc_sample(MeasSample *s)
{
    HAL_StatusTypeDef st;
    memset(s,0,sizeof *s); s->start_ms=HAL_GetTick();
    st=HAL_ADC_Start(&hadc1);
    if (st==HAL_OK) st=HAL_ADC_PollForConversion(&hadc1,10);
    if (st==HAL_OK) {
        s->raw=(uint16_t)HAL_ADC_GetValue(&hadc1); s->has_raw=1;
        if (HAL_ADC_GetError(&hadc1)!=HAL_ADC_ERROR_NONE) s->status|=MEAS_ADC;
    } else s->status|=MEAS_ADC|(st==HAL_TIMEOUT?MEAS_TIMEOUT:MEAS_IO);
    s->end_ms=HAL_GetTick();
    if (HAL_ADC_Stop(&hadc1)!=HAL_OK) s->status|=MEAS_ADC;
}
void Measurement_Task(void)
{
    MeasSample samples[MEAS_CHANNELS];
    char row[320]; unsigned i; int n;
    uint32_t now=HAL_GetTick();
    if (!first && (uint32_t)(now-last_start)<MEAS_PERIOD_MS) return;
    first=0; last_start=now;
    if(metadata_profile!=G03_ADC_Profile() || metadata_selfcal!=G03_ADC_Calibrated())metadata();
    memset(samples,0,sizeof samples);
    adc_sample(&samples[MEAS_MCU_I]); /* Independent of TIM1/PWM and AFE failures. */
    Afe_Acquire(samples);
    if (seq && seq%20U==0U) metadata(); /* Late serial attachment gets schema. */
    for(i=0;i<MEAS_CHANNELS;++i) {
        n=Meas_Format(row,sizeof row,seq,(MeasChannel)i,&samples[i],HAL_GetTick());
        if (n>0 && n<(int)sizeof row) uart_printf("%s",row);
        else uart_printf("#ERROR,format,seq=%lu,ch=%u\r\n",(unsigned long)seq,i);
    }
    ++seq; /* Increment even if transport drops a row; recorder checks per channel. */
}
