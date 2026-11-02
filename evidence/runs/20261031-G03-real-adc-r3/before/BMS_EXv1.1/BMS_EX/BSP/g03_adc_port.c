#include "g03_adc_port.h"
#include "g03_adc_core.h"
#include "g03_port.h"
#include "g02_port.h"
#include "main.h"
#include <stdio.h>
#include <string.h>
#if G02_ALLOW_PIN_OUTPUT
#error "Real ADC diagnostic firmware must keep pin output disabled"
#endif
extern ADC_HandleTypeDef hadc1;
/* Disabled real-ADC exercise. No PWM/relay enable or TIM CCR write exists. */
static G3ACore core;
static volatile uint32_t owned,cleanup_pending,armed;
static uint32_t profile,calibrated,diag_valid,diag_min,diag_max,diag_sum,diag_raw[64];
static uint32_t diag_regs[12],hw_low,hw_high,off_cycles;
static uint32_t lock(void){uint32_t k=__get_PRIMASK();__disable_irq();return k;}
static void unlock(uint32_t k){__set_PRIMASK(k);}
static uint32_t cycles(void){return DWT->CYCCNT;}
static uint32_t bits(void)
{
    return ((TIM1->BDTR&TIM_BDTR_MOE)?1U:0U)|((TIM1->CCER)?2U:0U)|
        ((TIM1->CR1&TIM_CR1_CEN)?4U:0U)|((GPIOB->ODR&SWS_Relay_Pin)?8U:0U)|
        ((GPIOG->ODR&SWL_Relay_Pin)?16U:0U)|
        (((GPIOA->ODR&GPIO_PIN_9)||(GPIOF->ODR&GPIO_PIN_7))?32U:0U);
}
static void shutdown(void)
{
    G02_EmergencyOff();if(!off_cycles)off_cycles=cycles();armed=0U;
    ADC1->IER=0U;
    if(ADC1->CR&ADC_CR_ADSTART)SET_BIT(ADC1->CR,ADC_CR_ADSTP);
    cleanup_pending=1U;
}
int G03_ADC_Owns(void){return owned!=0U;}
int G03_ADC_BlocksOthers(void){return owned || core.state!=G3A_IDLE;}
uint32_t G03_ADC_Profile(void){return profile;}
uint32_t G03_ADC_Calibrated(void){return calibrated;}
void G03_ADC_Task(void)
{
    ADC_AnalogWDGConfTypeDef w={0};
    if(!cleanup_pending)return;
    if(HAL_ADC_Stop_IT(&hadc1)!=HAL_OK){core.state=G3A_FAULT;core.faults|=G3A_ADC;return;}
    w.WatchdogNumber=ADC_ANALOGWATCHDOG_1;w.WatchdogMode=ADC_ANALOGWATCHDOG_NONE;
    w.Channel=ADC_CHANNEL_1;w.HighThreshold=4095U;
    if(HAL_ADC_AnalogWDGConfig(&hadc1,&w)!=HAL_OK){core.state=G3A_FAULT;core.faults|=G3A_ADC;return;}
    ADC1->ISR=ADC_FLAG_EOC|ADC_FLAG_EOS|ADC_FLAG_OVR|ADC_FLAG_AWD1;
    cleanup_pending=0U;owned=0U;
}
void G03_ADC_Stop(void)
{
    uint32_t k=lock();
    if(owned){G3A_Stop(&core,HAL_GetTick(),cycles(),2U);shutdown();}
    unlock(k);G03_ADC_Task();
}
void G03_ADC_TickIRQ(void)
{
    uint32_t k;
    if(!owned||!armed||core.state!=G3A_RUNNING)return;
    k=lock();
    if(bits())G3A_Trip(&core,G3A_INTERLOCK,HAL_GetTick(),cycles());
    G3A_Tick(&core,HAL_GetTick(),cycles());
    if(core.state!=G3A_RUNNING)shutdown();
    else if(!(ADC1->CR&ADC_CR_ADSTART)) {
        /* Already-enabled ADC, no HAL waits, UART or floating point in SysTick. */
        SET_BIT(ADC1->CR,ADC_CR_ADSTART);
    }
    unlock(k);
}
int G03_ADC_IRQHandler(void)
{
    uint32_t flags,raw,errors=0,stamp;
    if(!owned)return 0;
    flags=ADC1->ISR;stamp=cycles();
    if(flags&ADC_FLAG_AWD1)errors|=G3A_AWD;
    if(flags&ADC_FLAG_OVR)errors|=G3A_OVR;
    if(errors){G02_EmergencyOff();if(!off_cycles)off_cycles=cycles();armed=0U;}
    if(flags&ADC_FLAG_EOC){
        raw=ADC1->DR;
        G3A_Sample(&core,raw,errors,HAL_GetTick(),stamp);
    }else if(errors)G3A_Trip(&core,errors,HAL_GetTick(),stamp);
    ADC1->ISR=flags&(ADC_FLAG_EOC|ADC_FLAG_EOS|ADC_FLAG_OVR|ADC_FLAG_AWD1);
    if(core.state!=G3A_RUNNING)shutdown();
    return 1;
}
static uint32_t diagnostic(uint32_t p)
{
    uint32_t i,raw,r=G03_OK;
    if(p>3U)return G03_BAD_ARGUMENT;
    diag_valid=0;core.configured=0;owned=1;G02_EmergencyOff();
    if(HAL_ADC_Stop(&hadc1)!=HAL_OK){r=G03_FAULTED;goto done;}
    hadc1.Init.ExternalTrigConv=ADC_SOFTWARE_START;
    hadc1.Init.ExternalTrigConvEdge=ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc1.Init.OversamplingMode=(p==0U||p==3U)?ENABLE:DISABLE;
    hadc1.Init.Oversampling.Ratio=2U;
    hadc1.Init.Oversampling.RightBitShift=ADC_RIGHTBITSHIFT_1;
    if(HAL_ADC_Init(&hadc1)!=HAL_OK){r=G03_FAULTED;goto done;}
    profile=p;
    if(p>=2U){
        calibrated=2U;
        if(HAL_ADCEx_Calibration_Start(&hadc1,ADC_SINGLE_ENDED)!=HAL_OK){r=G03_FAULTED;goto done;}
        calibrated=1U;
        if(HAL_ADC_Stop(&hadc1)!=HAL_OK){r=G03_FAULTED;goto done;}
    }
    diag_min=4095U;diag_max=0;diag_sum=0;
    for(i=0;i<64U;++i){
        if(HAL_ADC_Start(&hadc1)!=HAL_OK || HAL_ADC_PollForConversion(&hadc1,10U)!=HAL_OK ||
           HAL_ADC_GetError(&hadc1)!=HAL_ADC_ERROR_NONE){r=G03_FAULTED;goto done;}
        raw=HAL_ADC_GetValue(&hadc1);diag_raw[i]=raw;
        if(raw<diag_min)diag_min=raw;
        if(raw>diag_max)diag_max=raw;
        diag_sum+=raw;
        if(HAL_ADC_Stop(&hadc1)!=HAL_OK){r=G03_FAULTED;goto done;}
        HAL_Delay(1U);
    }
    diag_valid=1;
done:
    diag_regs[0]=ADC1->CFGR1;diag_regs[1]=ADC1->CFGR2;diag_regs[2]=ADC1->CALFACT;
    diag_regs[3]=ADC1->DIFSEL;diag_regs[4]=ADC1->GCOMP;diag_regs[5]=ADC1->OFR1;
    diag_regs[6]=ADC1->SQR1;diag_regs[7]=ADC1->SMPR1;diag_regs[8]=ADC1->PCSEL;
    diag_regs[9]=ADC1->CR;diag_regs[10]=ADC12_COMMON->CCR;diag_regs[11]=GPIOA->MODER;
    if(r!=G03_OK){core.state=G3A_FAULT;core.faults|=G3A_ADC;diag_valid=0;}
    shutdown();G03_ADC_Task();
    return owned?G03_FAULTED:r;
}
static uint32_t start(uint32_t duration,uint32_t probe)
{
    ADC_AnalogWDGConfTypeDef w={0};uint32_t k,now;
    if(!core.configured||calibrated!=1U)return G03_NOT_READY;
    if(duration<100U||duration>2000U)return G03_BAD_ARGUMENT;
    G02_EmergencyOff();
    w.WatchdogNumber=ADC_ANALOGWATCHDOG_1;w.WatchdogMode=ADC_ANALOGWATCHDOG_SINGLE_REG;
    w.Channel=ADC_CHANNEL_1;w.ITMode=ENABLE;w.LowThreshold=core.low;w.HighThreshold=core.high;
    w.FilteringConfig=ADC_AWD_FILTERING_NONE;
    if(probe==1U){w.LowThreshold=diag_max+32U;w.HighThreshold=diag_max+64U;}
    if(probe==2U){w.LowThreshold=diag_min-64U;w.HighThreshold=diag_min-32U;}
    if(w.LowThreshold<1U||w.HighThreshold>4094U||w.LowThreshold>=w.HighThreshold)return G03_BAD_ARGUMENT;
    if(HAL_ADC_Stop(&hadc1)!=HAL_OK || HAL_ADC_AnalogWDGConfig(&hadc1,&w)!=HAL_OK){
        owned=1;core.state=G3A_FAULT;core.faults|=G3A_ADC;
        shutdown();G03_ADC_Task();return G03_FAULTED;
    }
    hw_low=w.LowThreshold;hw_high=w.HighThreshold;
    CoreDebug->DEMCR|=CoreDebug_DEMCR_TRCENA_Msk;DWT->CTRL|=DWT_CTRL_CYCCNTENA_Msk;
    k=lock();now=HAL_GetTick();
    if(!G3A_Start(&core,duration,now,cycles(),probe)){unlock(k);return G03_NOT_READY;}
    owned=1;off_cycles=0;unlock(k);
    if(HAL_ADC_Start_IT(&hadc1)!=HAL_OK){
        k=lock();G3A_Trip(&core,G3A_ADC,HAL_GetTick(),cycles());shutdown();unlock(k);G03_ADC_Task();return G03_FAULTED;
    }
    k=lock();armed=core.state==G3A_RUNNING;unlock(k);
    /* Custom ISR consumes EOS and rearms by ADSTART only, once per SysTick. */
    return G03_OK;
}
uint32_t G03_ADC_Command(uint32_t op,uint32_t arg)
{
    uint32_t k,r;G3AEvent e;
    if(op==20U&&!arg)return G03_OK;
    if(op==28U){if(owned||core.state==G3A_RUNNING)return G03_BUSY;
        return G3A_Read(&core,arg,&e)?G03_OK:G03_BAD_ARGUMENT;}
    if(op==26U&&!arg){G03_ADC_Stop();return G03_OK;}
    if(op==25U&&!arg){k=lock();r=G3A_Heartbeat(&core,HAL_GetTick(),cycles())?G03_OK:G03_FAULTED;
        if(owned&&core.state!=G3A_RUNNING)shutdown();
        unlock(k);return r;}
    if(G02_OwnsADC(&g02_control)||g02_control.faults||G03_SyntheticBusy())return G03_BUSY;
    G03_ADC_Task();
    if(op==27U&&!arg){if(owned)return G03_BUSY;k=lock();r=G3A_Clear(&core)?G03_OK:G03_BUSY;unlock(k);return r;}
    if(core.state==G3A_FAULT)return G03_FAULTED;
    if(owned||core.state!=G3A_IDLE)return G03_BUSY;
    if(op==21U)return diagnostic(arg);
    if(op==22U&&!arg){
        if(!diag_valid||calibrated!=1U||diag_min<128U||diag_max>3967U||diag_max-diag_min>32U)return G03_NOT_READY;
        /* Assumed static baseline, NOT verified zero current or gain calibration. */
        return G3A_Configure(&core,(diag_sum*1000U+32U)/64U,50U)?G03_OK:G03_NOT_READY;
    }
    if(op==23U){if(!core.configured)return G03_NOT_READY;
        return G3A_Configure(&core,core.zero_mcode,arg)?G03_OK:G03_BAD_ARGUMENT;}
    if(op==24U)return start(arg,0U);
    if(op==29U&&(arg==1U||arg==2U))return start(200U,arg);
    return G03_BAD_ARGUMENT;
}
int G03_ADC_Report(char *out,unsigned size,uint32_t id,uint32_t result,uint32_t op,uint32_t arg)
{
    uint32_t k,i;int n,m;G3AEvent e;
    if(op==21U){
        n=snprintf(out,size,"#G3D,g03-adc-r2,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu",
            (unsigned long)id,(unsigned long)result,(unsigned long)profile,(unsigned long)calibrated,
            (unsigned long)(diag_valid?64U:0U),(unsigned long)diag_min,(unsigned long)diag_max,(unsigned long)diag_sum);
        for(i=0;i<12U+(diag_valid?64U:0U);++i){
            if(n<0||n>=(int)size)return -1;
            m=snprintf(out+n,size-(unsigned)n,",%lu",(unsigned long)(i<12U?diag_regs[i]:diag_raw[i-12U]));
            if(m<0)return -1;
            n+=m;
        }return n;
    }
    if(op==28U){
        k=lock();memset(&e,0,sizeof e);(void)G3A_Read(&core,arg,&e);unlock(k);
        return snprintf(out,size,"#G3T,g03-adc-r2,%lu,%lu,%lu,%lu,%lu,%lu,%ld,%lu,%lu,%lu",
            (unsigned long)id,(unsigned long)result,(unsigned long)e.seq,(unsigned long)e.ms,(unsigned long)e.cycles,
            (unsigned long)e.raw,(long)e.ua,(unsigned long)e.ccr,(unsigned long)e.event,(unsigned long)e.faults);
    }
    /* A small scalar snapshot; never copy the trace or format with IRQs masked. */
    { uint32_t v[33];int32_t ua;
      k=lock();v[0]=core.state;v[1]=core.faults;v[2]=core.configured;v[3]=profile;v[4]=calibrated;
      v[5]=core.count;v[6]=core.raw;ua=core.ua;v[7]=core.zero_mcode;v[8]=core.limit_ma;
      v[9]=core.low;v[10]=core.high;v[11]=core.ccr;v[12]=core.step;v[13]=core.written;
      v[14]=core.overwritten;v[15]=core.probe;v[16]=owned;v[17]=bits();v[18]=0;v[19]=0;
      v[20]=hw_low;v[21]=hw_high;v[22]=core.trip_ms;v[23]=core.trip_cycles;v[24]=off_cycles;
      v[25]=ADC1->CFGR1;v[26]=ADC1->CFGR2;v[27]=ADC1->CALFACT;
      v[28]=core.reason;v[29]=core.start_ms;v[30]=core.last_ms;v[31]=core.heartbeat_ms;v[32]=core.duration_ms;unlock(k);
      n=snprintf(out,size,"#G3A,g03-adc-r2,%lu,%lu,%ld",(unsigned long)id,(unsigned long)result,(long)ua);
      for(i=0;i<33U;++i){if(n<0||n>=(int)size)return -1;
          m=snprintf(out+n,size-(unsigned)n,",%lu",(unsigned long)v[i]);if(m<0)return -1;
            n+=m;}
      return n;
    }
}
