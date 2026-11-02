#include "g03_relay_port.h"
#include "g03_relay_core.h"
#include "g03_relay_profile.h"
#include "g02_port.h"
#include "g03_port.h"
#include "g03_adc_port.h"
#include "adbms_acquisition.h"
#include "main.h"
#include <stdio.h>
#include <string.h>
#if G02_ALLOW_PIN_OUTPUT
#error "Relay test requires PWM gate closed"
#endif
extern ADC_HandleTypeDef hadc1;
typedef struct {
    uint32_t phase,at_ms,done_ms,bits;
    MeasSample s[4],mcu;
} RelayRow;
static G3RCore core;
static RelayRow rows[G3R_CAPACITY];
static RelayRow working; /* never put the capture buffer on the 2 KiB stack */
static uint32_t written,prepared,next_ms,hz,last_irq,irq_max,on_cycles,off_cycles;
static uint32_t actual_high,live_used,session_cycle,last_data_cycle,timer_ok,window_started,window_stopped;
static uint32_t lock(void){uint32_t k=__get_PRIMASK();__disable_irq();return k;}
static void unlock(uint32_t k){__set_PRIMASK(k);}
static uint32_t bits(void)
{
    return ((TIM1->BDTR&TIM_BDTR_MOE)?1U:0U)|(TIM1->CCER?2U:0U)|
        ((TIM1->CR1&TIM_CR1_CEN)?4U:0U)|((GPIOB->ODR&SWS_Relay_Pin)?8U:0U)|
        ((GPIOG->ODR&SWL_Relay_Pin)?16U:0U)|
        (((GPIOA->ODR&GPIO_PIN_9)||(GPIOF->ODR&GPIO_PIN_7))?32U:0U);
}
static void off(void)
{
    if(__HAL_RCC_GPIOG_IS_CLK_ENABLED())GPIOG->BSRR=SWL_Relay_Pin<<16U;
    __DSB();
    if(window_started && !window_stopped){off_cycles=DWT->CYCCNT;window_stopped=1U;}
    actual_high=0;
}
static void apply(void)
{
    if(core.state!=G3R_PULSE || !core.command_on){off();return;}
    /* Only the foreground transition from a validated baseline may enable. */
}
int G03_RelayBusy(void){return G3R_Active(&core);}
void G03_RelayInit(void)
{
    uint32_t timg=HAL_RCCEx_GetTIMGFreq();
    G3R_Init(&core);G02_EmergencyOff();
    hz=HAL_RCC_GetCpuClockFreq();
    CoreDebug->DEMCR|=CoreDebug_DEMCR_TRCENA_Msk;DWT->CTRL|=DWT_CTRL_CYCCNTENA_Msk;
    TIM2->CR1=0;TIM2->DIER=0;TIM2->CR2=0;
    timer_ok=timg>=1000000U && timg%1000000U==0U && hz>=1000000U;
    if(!timer_ok)return;
    TIM2->PSC=timg/1000000U-1U;TIM2->ARR=999U;TIM2->CNT=0;
    TIM2->EGR=TIM_EGR_UG;TIM2->SR=0;
    HAL_NVIC_SetPriority(TIM2_IRQn,0U,0U);
    HAL_NVIC_ClearPendingIRQ(TIM2_IRQn);HAL_NVIC_EnableIRQ(TIM2_IRQn);
}
void G03_RelayTickIRQ(void)
{
    uint32_t stamp,delta,now;
    if(!(TIM2->SR&TIM_SR_UIF)||!(TIM2->DIER&TIM_DIER_UIE))return;
    TIM2->SR=~TIM_SR_UIF;stamp=DWT->CYCCNT;delta=stamp-last_irq;last_irq=stamp;
    if(delta>irq_max)irq_max=delta;
    if(!G03_RelayBusy())return;
    now=HAL_GetTick();
    if(delta>hz/1000U*2U)G3R_Trip(&core,G3R_TIMING,now);
    if(bits() & ~(actual_high?16U:0U))G3R_Trip(&core,G3R_INTERLOCK,now);
    if(core.state==G3R_PREPARE && stamp-session_cycle>hz/5U)G3R_Trip(&core,G3R_DATA,now);
    if((core.state==G3R_BASELINE||core.state==G3R_PULSE) && stamp-last_data_cycle>hz/1000U*G3R_STALE_MS)
        G3R_Trip(&core,G3R_STALE,now);
    /* DWT deadline still expires if the HAL tick is delayed by a lower priority IRQ. */
    if(core.state==G3R_PULSE && stamp-on_cycles>=hz/1000U*G3R_PULSE_MS)G3R_Tick(&core,core.on_ms+G3R_PULSE_MS);
    G3R_Tick(&core,now);apply();
}
void G03_RelayStop(void)
{uint32_t k=lock();G3R_Stop(&core,HAL_GetTick());off();unlock(k);}
void G03_RelayCPUFault(void)
{G3R_Trip(&core,G3R_CPU,HAL_GetTick());off();}
static void mcu_sample(MeasSample *s)
{
    HAL_StatusTypeDef st;memset(s,0,sizeof *s);s->start_ms=HAL_GetTick();
    st=HAL_ADC_Start(&hadc1);
    if(st==HAL_OK)st=HAL_ADC_PollForConversion(&hadc1,10U);
    if(st==HAL_OK){s->raw=(uint16_t)HAL_ADC_GetValue(&hadc1);s->has_raw=1U;
        if(HAL_ADC_GetError(&hadc1)!=HAL_ADC_ERROR_NONE)s->status|=MEAS_ADC;
    }else s->status|=MEAS_ADC|(st==HAL_TIMEOUT?MEAS_TIMEOUT:MEAS_IO);
    s->end_ms=HAL_GetTick();if(HAL_ADC_Stop(&hadc1)!=HAL_OK)s->status|=MEAS_ADC;
}
void G03_RelayTask(void)
{
    uint32_t k,now,valid=1U,i,old_state;uint16_t raw[4];
    if(!G03_RelayBusy()){
        if(TIM2->DIER&TIM_DIER_UIE){TIM2->DIER=0;TIM2->CR1=0;off();}
        return;
    }
    if(!prepared){
        uint32_t st=Afe_PulsePrepare();prepared=1U;k=lock();
        if(st)G3R_Trip(&core,G3R_DATA,HAL_GetTick());
        else G3R_Ready(&core,HAL_GetTick());
        last_data_cycle=DWT->CYCCNT;apply();unlock(k);next_ms=HAL_GetTick();return;
    }
    now=HAL_GetTick();if((int32_t)(now-next_ms)<0)return;
    next_ms=now+G3R_PERIOD_MS;
    memset(&working,0,sizeof working);working.at_ms=now;working.phase=core.state;working.bits=bits();
    Afe_PulseAcquire(working.s);mcu_sample(&working.mcu);working.done_ms=HAL_GetTick();
    for(i=0;i<4U;++i){
        MeasValue v=Meas_Evaluate(&working.s[i],(MeasChannel)i,working.done_ms);
        raw[i]=working.s[i].raw;if(!v.raw_valid)valid=0;
    }
    k=lock();old_state=core.state;
    if(written<G3R_CAPACITY)rows[written++]=working;
    else G3R_Trip(&core,G3R_BUFFER,working.done_ms);
    G3R_Sample(&core,working.done_ms,working.s[0].start_ms,valid,raw);
    if(valid)last_data_cycle=DWT->CYCCNT;
    if(old_state==G3R_BASELINE && core.state==G3R_PULSE){
        on_cycles=DWT->CYCCNT;window_started=1U; /* arm deadline before setting GPIO */
        if(core.live && (core.base_min<G3R_BASE_LOW_CODE || core.base_max>G3R_BASE_HIGH_CODE))
            G3R_Trip(&core,G3R_BASE,working.done_ms);
        else if(bits())G3R_Trip(&core,G3R_INTERLOCK,working.done_ms);
        else if(core.live){
            if(!G3R_LIVE_PROFILE_VERIFIED || live_used)G3R_Trip(&core,G3R_INTERLOCK,working.done_ms);
            else{live_used=1U;actual_high=1U;GPIOG->BSRR=SWL_Relay_Pin;__DSB();}
        }
    }
    apply();unlock(k);
}
uint32_t G03_RelayCommand(uint32_t op,uint32_t arg)
{
    uint32_t k;
    if(op==30U&&!arg)return G02_OK;
    if(op==34U&&!arg){G03_RelayStop();return G02_OK;}
    if(op==36U)return !G03_RelayBusy()&&arg<written?G02_OK:G02_BAD_ARGUMENT;
    if(op==35U&&!arg){k=lock();if(!G3R_Clear(&core)){unlock(k);return G02_BUSY;}unlock(k);return G02_OK;}
    if(op!=31U && op!=32U)return G02_BAD_ARGUMENT;
    if(arg)return G02_BAD_ARGUMENT;
    if(G03_RelayBusy()||G02_OwnsADC(&g02_control)||g02_control.faults||G03_SyntheticBusy()||G03_ADC_BlocksOthers())return G02_BUSY;
    if(op==32U && (!G3R_LIVE_PROFILE_VERIFIED||live_used))return G02_DISALLOWED;
    if(core.state!=G3R_IDLE || !timer_ok || bits())return G02_NOT_READY;
    k=lock();
    if(!G3R_Begin(&core,op==32U,HAL_GetTick(),G3R_CELL_LOW_CODE,G3R_CELL_HIGH_CODE)){unlock(k);return G02_NOT_READY;}
    written=prepared=irq_max=on_cycles=off_cycles=window_started=window_stopped=0;session_cycle=last_data_cycle=last_irq=DWT->CYCCNT;
    TIM2->CNT=0;TIM2->SR=0;TIM2->DIER=TIM_DIER_UIE;TIM2->CR1=TIM_CR1_CEN;
    unlock(k);return G02_OK;
}
int G03_RelayReport(char *out,unsigned size,uint32_t id,uint32_t result,uint32_t op,uint32_t arg)
{
    int n,m;uint32_t k,i;G3RCore c;
    if(op==36U && result==G02_OK && arg<written && !G03_RelayBusy()){
        const RelayRow *r=&rows[arg];
        n=snprintf(out,size,"#G3S," G3R_FIRMWARE ",%lu,%lu,%lu,%lu,%lu,%lu,%lu",(unsigned long)id,(unsigned long)result,
            (unsigned long)arg,(unsigned long)r->phase,(unsigned long)r->at_ms,(unsigned long)r->done_ms,(unsigned long)r->bits);
        for(i=0;i<5U;++i){const MeasSample *s=i<4U?&r->s[i]:&r->mcu;MeasValue v=Meas_Evaluate(s,i<4U?(MeasChannel)i:MEAS_MCU_I,r->done_ms);
            if(n<0||n>=(int)size)return -1;
            m=snprintf(out+n,size-(unsigned)n,",%lu,%lu,%u,%lu,%u,%02X%02X%02X%02X%02X%02X%02X%02X",
                (unsigned long)s->start_ms,(unsigned long)s->end_ms,(unsigned)s->raw,(unsigned long)v.status,(unsigned)v.raw_valid,
                s->frame[0],s->frame[1],s->frame[2],s->frame[3],s->frame[4],s->frame[5],s->frame[6],s->frame[7]);
            if(m<0)return -1;
            n+=m;
        }return n;
    }
    k=lock();c=core;unlock(k);
    return snprintf(out,size,"#G3R," G3R_FIRMWARE ",%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,0",
        (unsigned long)id,(unsigned long)result,(unsigned long)c.state,(unsigned long)c.faults,(unsigned long)c.reason,
        (unsigned long)c.live,(unsigned long)written,(unsigned long)c.base_count,(unsigned long)c.center,(unsigned long)c.tolerance,
        (unsigned long)c.on_ms,(unsigned long)c.off_ms,(unsigned long)c.recover_count,(unsigned long)bits(),
        (unsigned long)on_cycles,(unsigned long)off_cycles,(unsigned long)irq_max,(unsigned long)hz,
        (unsigned long)G3R_LIVE_PROFILE_VERIFIED,(unsigned long)live_used,(unsigned long)G3R_PERIOD_MS,(unsigned long)G3R_STALE_MS);
}
