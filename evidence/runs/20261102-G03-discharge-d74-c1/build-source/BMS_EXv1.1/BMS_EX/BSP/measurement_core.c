#include "measurement_core.h"
#include "nominal_current.h"
#include <stdio.h>
#include <string.h>
const char * const meas_channel_names[MEAS_CHANNELS] = {
    "cell1", "cell7", "cell13", "current_afe_gpio1", "temperature_gpio2",
    "temperature_gpio3", "temperature_gpio4", "current_mcu_adc1", "afe_vref2"
};
uint16_t Meas_Pec15(const uint8_t *bytes, size_t length)
{
    uint16_t rem = 16U;
    size_t i; unsigned bit;
    for (i=0; i<length; ++i) {
        rem ^= (uint16_t)((uint16_t)bytes[i] << 7);
        for (bit=0; bit<8; ++bit)
            rem = (uint16_t)((rem << 1) ^ ((rem & 0x4000U) ? 0x4599U : 0U));
    }
    return (uint16_t)(rem << 1);
}
void Meas_Decode(MeasSample *s, const uint8_t frame[8], unsigned index)
{
    memcpy(s->frame, frame, 8); s->has_frame=1;
    if (index>2U) { s->status |= MEAS_CONFIG; return; }
    s->raw=(uint16_t)(frame[2U*index] | ((uint16_t)frame[2U*index+1U]<<8));
    s->has_raw=1;
    if (Meas_Pec15(frame,6) != (uint16_t)(((uint16_t)frame[6]<<8)|frame[7]))
        s->status |= MEAS_PEC;
}
MeasValue Meas_Evaluate(const MeasSample *s, MeasChannel ch, uint32_t now)
{
    MeasValue v={0};
    v.status=s->status|MEAS_UNCALIBRATED;
    v.age_ms=(uint32_t)(now-s->end_ms);
    if (!s->has_raw) v.status |= MEAS_NO_RAW;
    if (v.age_ms>MEAS_MAX_AGE_MS) v.status |= MEAS_STALE;
    if (s->has_raw && (s->raw==0xffffU ||
        (ch==MEAS_MCU_I && (s->raw==0U || s->raw>=4095U)))) v.status |= MEAS_RANGE;
    if (v.status & MEAS_INVALID_MASK) return v;
    /* MCU VREF is a DOCUMENT NOMINAL, not a measured reference. */
    v.sensor_v=(ch==MEAS_MCU_I) ? (float)s->raw*CURRENT_MCU_LSB : (float)s->raw*0.0001f;
    if (ch>=MEAS_TEMP1 && ch<=MEAS_TEMP3) {
        /* Model diagnostic only: PT1000 / 9.1k / 3V, actual probe unknown. */
        if (v.sensor_v<=0.0f || v.sensor_v>=2.999f) {
            v.status |= MEAS_RANGE; return v;
        }
        v.estimate=((9100.0f*v.sensor_v/(3.0f-v.sensor_v))/1000.0f-1.0f)/0.00385f;
    } else if (ch==MEAS_AFE_I) {
        v.estimate=Current_AfeNominal(s->raw,0.9f);
    } else if (ch==MEAS_MCU_I) {
        /* Nominal HEX model only; physical_valid remains zero. */
        v.estimate=Current_McuNominal(s->raw,0.9f);
    } else v.estimate=v.sensor_v;
    v.raw_valid=1; v.estimate_present=1;
    return v;
}
int Meas_Format(char *dest, size_t size, uint32_t seq, MeasChannel ch,
                const MeasSample *s, uint32_t now)
{
    char raw[8]="", sensor[24]="", estimate[24]="", frame[17]="";
    MeasValue v=Meas_Evaluate(s,ch,now);
    const char *unit=(ch==MEAS_AFE_I||ch==MEAS_MCU_I)?"A":
                     (ch>=MEAS_TEMP1&&ch<=MEAS_TEMP3)?"degC":"V";
    unsigned i; int n, tail;
    if ((unsigned)ch>=MEAS_CHANNELS) return -1;
    if (s->has_raw) (void)snprintf(raw,sizeof raw,"%u",(unsigned)s->raw);
    if (v.raw_valid) (void)snprintf(sensor,sizeof sensor,"%.6f",(double)v.sensor_v);
    if (v.estimate_present) (void)snprintf(estimate,sizeof estimate,"%.6f",(double)v.estimate);
    if (s->has_frame) for (i=0;i<8;++i) (void)snprintf(frame+2*i,3,"%02X",s->frame[i]);
    n=snprintf(dest,size,"M,%lu,%s,%lu,%lu,%lu,%s,%lu,%u,%s,%s,%s,,0,,%s,%s",
        (unsigned long)seq,meas_channel_names[ch],(unsigned long)s->start_ms,
        (unsigned long)s->end_ms,(unsigned long)v.age_ms,raw,
        (unsigned long)v.status,(unsigned)v.raw_valid,sensor,estimate,unit,MEAS_CAL_ID,frame);
    if (n<0 || (size_t)n>=size) return n;
    tail=snprintf(dest+n,size-(size_t)n,",%04X\r\n",Meas_Pec15((const uint8_t *)dest,(size_t)n));
    return tail<0 ? -1 : n+tail;
}
