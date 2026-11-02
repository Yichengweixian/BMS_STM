#include "g03_pwm_port.h"
#if defined(G03_PWM_DISABLED_BUILD) && G03_PWM_DISABLED_BUILD
#include "pwm_oneshot.h"
#include "g02_port.h"
#include "g03_port.h"
#include "g03_adc_port.h"
#include "g03_relay_port.h"
#include "g03_relay_profile.h"
#include "firmware_identity.h"
#include "main.h"
#include <stdio.h>
#include <string.h>
#if G02_ALLOW_PIN_OUTPUT || G3R_LIVE_PROFILE_VERIFIED
#error "PWM rehearsal requires every power-output gate closed"
#endif

/* This adapter cannot enable MOE, CCER, AF pins or either relay.
 * Fixture facts/limits exercise the candidate core only; physical_valid=0.
 * TIM1 is exclusively a 100 kHz ADC trigger with a frozen shadow CCR.
 * TIM2 runs freely at 1 MHz, including while foreground/UART stalls. */
extern ADC_HandleTypeDef hadc1;
#define CAPACITY 512U
#define PERIOD_US 100U
#define F_BUFFER (1UL<<16)
#define F_INTERLOCK (1UL<<17)
typedef struct {uint32_t event,us,raw,flags,ccr,cnt,phase,bits;} Row;
static PWMOneShot shot;
static PWMProfile profile;
static ADC_InitTypeDef saved_adc;
static uint32_t saved_regs[10];
static uint32_t saved_timer[9],saved_adc_priority,saved_tim_irq,saved_adc_irq;
static Row rows[CAPACITY];
static uint32_t owned,ready,scenario,start_id,tim_hz,adc_hz,restored;
static uint32_t written,overflow,samples,raw_latest,raw_min,raw_max,last_sample,gap_max,irq_gap,irq_count,last_irq;
static uint32_t triggered,off_logged,last_log,preflight_at,armed;
static uint32_t request_used,cleanup_attempted,stopped_clock;
static uint32_t injection_done,injection_at;
static uint32_t lock(void){uint32_t k=__get_PRIMASK();__disable_irq();return k;}
static void unlock(uint32_t k){__set_PRIMASK(k);}
static uint32_t now_us(void *ctx){(void)ctx;return owned?TIM2->CNT:stopped_clock;}
static uint32_t bits(void)
{
    return ((TIM1->BDTR&TIM_BDTR_MOE)?1U:0U)|(TIM1->CCER?2U:0U)|
        ((GPIOB->ODR&SWS_Relay_Pin)?8U:0U)|((GPIOG->ODR&SWL_Relay_Pin)?16U:0U)|
        (((GPIOA->ODR&GPIO_PIN_9)||(GPIOF->ODR&GPIO_PIN_7))?32U:0U);
}
static void trace(uint32_t event,uint32_t stamp,uint32_t raw,uint32_t flags)
{
    Row *r;
    if(written>=CAPACITY){++overflow;return;}
    r=&rows[written++];r->event=event;r->us=stamp;r->raw=raw;r->flags=flags;
    r->ccr=TIM1->CCR2;r->cnt=TIM1->CNT;r->phase=(TIM1->CR1&TIM_CR1_DIR)?1U:0U;r->bits=bits();
}
static void emergency_off(void *ctx)
{
    (void)ctx;G02_EmergencyOff();
    /* No polling or HAL call in this path. The time counter stays free-running. */
    if(owned){
        /* RM0486: IER writes require ADSTART=0. Mask NVIC immediately,
         * request conversion stop, defer IER/HAL cleanup until stopped. */
        HAL_NVIC_DisableIRQ(ADC1_2_IRQn);
        if(ADC1->CR&ADC_CR_ADSTART)SET_BIT(ADC1->CR,ADC_CR_ADSTP);
        TIM2->DIER=0U;
    }
    armed=0U;
    if(triggered&&!off_logged){off_logged=1U;trace(3U,TIM2->CNT,raw_latest,ADC1->ISR);}
}
static PWMSample sample(uint32_t raw,uint32_t stamp,uint32_t valid,uint32_t overrun)
{
    PWMSample s;
    s.at_us=stamp;
    /* Integer approximation of the existing uncalibrated HEX nominal model.
     * +/-2 A here is a disabled test fixture, never a physical power limit. */
    /* 1.8 V full scale * 1.326667 A/V. */
    s.current_ma=((int32_t)raw*2388+2047)/4095-1194;
    s.valid=valid;s.overrun=overrun;return s;
}
int G03_PWM_Busy(void){return owned&&(shot.state==PWM_RUNNING||shot.state==PWM_PREPARING);}
int G03_PWM_Owns(void){return owned!=0U;}
int G03_PWM_ReportReady(void){return !G03_PWM_Busy()&&(!owned||cleanup_attempted);}
int G03_PWM_Blocks(void){return owned||(shot.initialized&&shot.state==PWM_FAULT);}
static int prepare(void *ctx,const PWMProfile *p)
{
    (void)ctx;
    /* Foreground preflight has already performed all HAL waits. Start's first
     * off callback stopped ADC; rearm by registers only, never HAL here. */
    if(!ready||!owned||bits()||p->ccr!=1000U||p->arr!=2000U||p->deadtime_code!=0U)return 0;
    if(ADC1->CR&(ADC_CR_ADSTP|ADC_CR_ADDIS|ADC_CR_ADCAL))return 0;
    if(!(ADC1->CR&ADC_CR_ADEN))return 0;
    if(TIM1->PSC||TIM1->ARR!=2000U||TIM1->RCR!=1U||ADC1->SQR1!=64U||ADC1->PCSEL!=2U)return 0;
    if((TIM1->CR1&TIM_CR1_CMS)!=TIM_COUNTERMODE_CENTERALIGNED1)return 0;
    CLEAR_BIT(TIM1->BDTR,TIM_BDTR_MOE|TIM_BDTR_AOE|TIM_BDTR_DTG);
    TIM1->CCER=0U;TIM1->DIER=0U;
    CLEAR_BIT(TIM1->CR1,TIM_CR1_CEN|TIM_CR1_CMS|TIM_CR1_UDIS);
    CLEAR_BIT(TIM1->CR1,TIM_CR1_DIR);
    SET_BIT(TIM1->CR1,TIM_COUNTERMODE_CENTERALIGNED1|TIM_CR1_URS);
    MODIFY_REG(TIM1->CR2,TIM_CR2_MMS,TIM_TRGO_ENABLE);
    TIM1->CNT=0U;TIM1->CCR2=p->ccr;TIM1->EGR=TIM_EGR_UG;TIM1->SR=0U;
    MODIFY_REG(TIM1->CR2,TIM_CR2_MMS,TIM_TRGO_UPDATE);
    ADC1->ISR=ADC_FLAG_EOC|ADC_FLAG_EOS|ADC_FLAG_OVR|ADC_FLAG_AWD1;
    ADC1->IER=ADC_IT_EOC|ADC_IT_EOS|ADC_IT_OVR|ADC_IT_AWD1;
    SET_BIT(ADC1->CR,ADC_CR_ADSTART);
    TIM2->CCR1=TIM2->CNT+PERIOD_US;TIM2->SR=0U;TIM2->DIER=TIM_DIER_CC1IE;
    return bits()==0U&&TIM1->CCR2==p->ccr;
}
static int enable_trigger(void *ctx)
{
    (void)ctx;
    if(bits()||!(TIM2->DIER&TIM_DIER_CC1IE))return 0;
    triggered=armed=1U;last_irq=TIM2->CNT;
    HAL_NVIC_ClearPendingIRQ(ADC1_2_IRQn);HAL_NVIC_EnableIRQ(ADC1_2_IRQn);
    trace(1U,TIM2->CNT,raw_latest,0U);
    SET_BIT(TIM1->CR1,TIM_CR1_CEN); /* TRGO only. CCER and MOE stay zero. */
    return bits()==0U;
}
static int after_off(void *ctx,PWMState state,uint32_t faults)
{
    (void)ctx;(void)state;(void)faults;return 1;
}
static const PWMOps ops={now_us,emergency_off,prepare,enable_trigger,after_off};
void G03_PWM_Init(void)
{
    G02_EmergencyOff();(void)PWM_OneShot_Init(&shot,&ops,0);
}
static void save_regs(void)
{
    saved_regs[0]=ADC1->SQR1;saved_regs[1]=ADC1->SMPR1;saved_regs[2]=ADC1->SMPR2;saved_regs[3]=ADC1->PCSEL;
    saved_regs[4]=ADC1->CFGR1;saved_regs[5]=ADC1->CFGR2;saved_regs[6]=ADC1->AWD1LTR;saved_regs[7]=ADC1->AWD1HTR;
    saved_regs[8]=ADC1->IER;saved_regs[9]=ADC1->CALFACT;
}
static int preflight(void)
{
    ADC_ChannelConfTypeDef ch={0};ADC_AnalogWDGConfTypeDef wd={0};uint32_t i,k,f;
    G02_EmergencyOff();ready=0U;restored=0U;
    tim_hz=HAL_RCCEx_GetTIMGFreq();adc_hz=HAL_RCCEx_GetPeriphCLKFreq(RCC_PERIPHCLK_ADC);
    if(tim_hz!=400000000U||adc_hz!=64000000U||bits())return 0;
    G03_RelayTask(); /* Finish any terminal relay timer cleanup before taking TIM2. */
    saved_adc=hadc1.Init;save_regs();
    saved_timer[0]=TIM2->PSC;saved_timer[1]=TIM2->ARR;saved_timer[2]=TIM2->CNT;saved_timer[3]=TIM2->CR1;
    saved_timer[4]=TIM2->CR2;saved_timer[5]=TIM2->DIER;saved_timer[6]=TIM2->CCER;saved_timer[7]=TIM2->CCR1;saved_timer[8]=TIM2->CCMR1;
    saved_adc_priority=NVIC_GetPriority(ADC1_2_IRQn);saved_tim_irq=NVIC_GetEnableIRQ(TIM1_UP_IRQn);saved_adc_irq=NVIC_GetEnableIRQ(ADC1_2_IRQn);
    owned=1U;cleanup_attempted=0U;
    TIM2->CR1=0U;TIM2->DIER=0U;TIM2->CR2=0U;TIM2->CCER=0U;
    TIM2->PSC=tim_hz/1000000U-1U;TIM2->ARR=0xffffffffU;TIM2->CNT=0U;
    TIM2->EGR=TIM_EGR_UG;TIM2->SR=0U;TIM2->CR1=TIM_CR1_CEN;
    HAL_NVIC_SetPriority(TIM2_IRQn,0U,0U);HAL_NVIC_ClearPendingIRQ(TIM2_IRQn);HAL_NVIC_EnableIRQ(TIM2_IRQn);
    HAL_NVIC_SetPriority(ADC1_2_IRQn,1U,0U);HAL_NVIC_DisableIRQ(TIM1_UP_IRQn);
    if(HAL_ADC_Stop(&hadc1)!=HAL_OK)return 0;
    hadc1.Init.ExternalTrigConv=ADC_SOFTWARE_START;hadc1.Init.ExternalTrigConvEdge=ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc1.Init.NbrOfConversion=1U;hadc1.Init.ScanConvMode=ADC_SCAN_DISABLE;
    hadc1.Init.OversamplingMode=ENABLE;hadc1.Init.Oversampling.Ratio=2U;hadc1.Init.Oversampling.RightBitShift=ADC_RIGHTBITSHIFT_1;
    if(HAL_ADC_Init(&hadc1)!=HAL_OK)return 0;
    ch.Channel=ADC_CHANNEL_1;ch.Rank=ADC_REGULAR_RANK_1;
    ch.SamplingTime=scenario==8U?ADC_SAMPLETIME_6CYCLES_5:ADC_SAMPLETIME_11CYCLES_5;
    ch.SingleDiff=ADC_SINGLE_ENDED;ch.OffsetNumber=ADC_OFFSET_NONE;
    if(HAL_ADC_ConfigChannel(&hadc1,&ch)!=HAL_OK)return 0;
    for(i=0;i<64U;++i){
        k=lock();f=shot.faults;unlock(k);if(f)return 0;
        if(HAL_ADC_Start(&hadc1)!=HAL_OK||HAL_ADC_PollForConversion(&hadc1,10U)!=HAL_OK||HAL_ADC_GetError(&hadc1))return 0;
        raw_latest=HAL_ADC_GetValue(&hadc1);preflight_at=TIM2->CNT;
        trace(0U,preflight_at,raw_latest,0U);HAL_Delay(0U);
    }
    if(raw_latest<128U||raw_latest>3967U||HAL_ADC_Stop(&hadc1)!=HAL_OK)return 0;
    hadc1.Init.ExternalTrigConv=ADC_EXTERNALTRIG_T1_TRGO;hadc1.Init.ExternalTrigConvEdge=ADC_EXTERNALTRIGCONVEDGE_RISING;
    if(HAL_ADC_Init(&hadc1)!=HAL_OK)return 0;
    wd.WatchdogNumber=ADC_ANALOGWATCHDOG_1;wd.WatchdogMode=ADC_ANALOGWATCHDOG_SINGLE_REG;wd.Channel=ADC_CHANNEL_1;
    wd.ITMode=ENABLE;wd.LowThreshold=128U;wd.HighThreshold=3967U;wd.FilteringConfig=ADC_AWD_FILTERING_NONE;
    if(scenario==4U){wd.LowThreshold=3500U;wd.HighThreshold=3900U;}
    if(scenario==5U){wd.LowThreshold=100U;wd.HighThreshold=500U;}
    if(HAL_ADC_AnalogWDGConfig(&hadc1,&wd)!=HAL_OK)return 0;
    /* Enable ADC without starting an external conversion until core prepare.
     * HAL start/stop cannot be called while the core critical section is held. */
    if(HAL_ADC_Start_IT(&hadc1)!=HAL_OK)return 0;
    if(ADC1->CR&ADC_CR_ADSTART)SET_BIT(ADC1->CR,ADC_CR_ADSTP);
    {uint32_t begin=TIM2->CNT;while(ADC1->CR&ADC_CR_ADSTP)if(TIM2->CNT-begin>100U)return 0;}
    ADC1->IER=0U;ADC1->ISR=ADC_FLAG_EOC|ADC_FLAG_EOS|ADC_FLAG_OVR|ADC_FLAG_AWD1;
    ready=1U;return 1;
}
void G03_PWM_Task(void)
{
    uint32_t k;int good;
    if(!owned){k=lock();(void)PWM_OneShot_Service(&shot);unlock(k);return;}
    if(G03_PWM_Busy()||cleanup_attempted)return;
    cleanup_attempted=1U;
    /* Cleanup is allowed to wait in foreground, after register shutdown. */
    good=HAL_ADC_Stop_IT(&hadc1)==HAL_OK;
    if(good){
        hadc1.Init=saved_adc;good=HAL_ADC_Init(&hadc1)==HAL_OK;
        ADC1->SQR1=saved_regs[0];ADC1->SMPR1=saved_regs[1];ADC1->SMPR2=saved_regs[2];ADC1->PCSEL=saved_regs[3];
        ADC1->CFGR1=saved_regs[4];ADC1->CFGR2=saved_regs[5];ADC1->AWD1LTR=saved_regs[6];ADC1->AWD1HTR=saved_regs[7];
        ADC1->IER=saved_regs[8];
        good=good&&ADC1->SQR1==saved_regs[0]&&ADC1->SMPR1==saved_regs[1]&&ADC1->SMPR2==saved_regs[2]&&
            ADC1->PCSEL==saved_regs[3]&&ADC1->CFGR1==saved_regs[4]&&ADC1->CFGR2==saved_regs[5]&&ADC1->CALFACT==saved_regs[9];
    }
    k=lock();
    if(shot.state==PWM_FAULT)trace(4U,TIM2->CNT,raw_latest,shot.faults);
    if(good){
        restored=1U;trace(5U,TIM2->CNT,raw_latest,0U);stopped_clock=TIM2->CNT;
        TIM2->CR1=0U;TIM2->DIER=0U;TIM2->PSC=saved_timer[0];TIM2->ARR=saved_timer[1];TIM2->CR2=saved_timer[4];
        TIM2->CCER=saved_timer[6];TIM2->CCR1=saved_timer[7];TIM2->CCMR1=saved_timer[8];
        TIM2->EGR=TIM_EGR_UG;TIM2->CNT=saved_timer[2];TIM2->SR=0U;TIM2->DIER=saved_timer[5];TIM2->CR1=saved_timer[3];
        owned=ready=0U;(void)PWM_OneShot_Service(&shot);
    }
    else{PWM_OneShot_Trip(&shot,PWM_F_ADAPTER);ready=0U;}
    unlock(k);
    NVIC_SetPriority(ADC1_2_IRQn,saved_adc_priority);
    if(good&&saved_adc_irq){HAL_NVIC_ClearPendingIRQ(ADC1_2_IRQn);HAL_NVIC_EnableIRQ(ADC1_2_IRQn);}
    if(saved_tim_irq)HAL_NVIC_EnableIRQ(TIM1_UP_IRQn);
}
int G03_PWM_TimerIRQ(void)
{
    uint32_t stamp,delta,k;
    if(!owned)return 0;
    if(!(TIM2->SR&TIM_SR_CC1IF)||!(TIM2->DIER&TIM_DIER_CC1IE))return 1;
    TIM2->SR=~TIM_SR_CC1IF;stamp=TIM2->CNT;TIM2->CCR1=stamp+PERIOD_US;
    k=lock();delta=stamp-last_irq;last_irq=stamp;++irq_count;if(delta>irq_gap)irq_gap=delta;
    if(bits())PWM_OneShot_Trip(&shot,F_INTERLOCK);
    if(shot.state==PWM_RUNNING&&stamp-shot.start_us>=5000U&&!injection_done){
        injection_done=1U;injection_at=stamp;
        if(scenario==1U)MODIFY_REG(TIM1->CR2,TIM_CR2_MMS,TIM_TRGO_ENABLE);
        if(scenario==2U){PWMSample s=sample(raw_latest,stamp,0U,0U);PWM_OneShot_ADCISR(&shot,&s);}
        if(scenario==3U)HAL_NVIC_DisableIRQ(ADC1_2_IRQn);
    }
    if(shot.state==PWM_RUNNING&&scenario==3U&&injection_done==1U&&stamp-injection_at>=200U){
        injection_done=2U;HAL_NVIC_EnableIRQ(ADC1_2_IRQn);
    }
    PWM_OneShot_PeriodicISR(&shot);unlock(k);return 1;
}
int G03_PWM_ADCIRQ(void)
{
    uint32_t flags,raw,stamp,delta,k;PWMSample s;
    if(!owned)return 0;
    flags=ADC1->ISR;stamp=TIM2->CNT;
    /* Real AWD/OVR closes registers before consuming/formatting any data. */
    if(flags&(ADC_FLAG_AWD1|ADC_FLAG_OVR)){
        emergency_off(0);k=lock();
        PWM_OneShot_Trip(&shot,(flags&ADC_FLAG_AWD1?PWM_F_OVERCURRENT:0U)|(flags&ADC_FLAG_OVR?PWM_F_OVERRUN:0U));
        ADC1->ISR=flags&(ADC_FLAG_EOC|ADC_FLAG_EOS|ADC_FLAG_OVR|ADC_FLAG_AWD1);unlock(k);return 1;
    }
    if(!(flags&ADC_FLAG_EOC)){ADC1->ISR=flags&ADC_FLAG_EOS;return 1;}
    raw=ADC1->DR;
    /* With one rank, queued extra data means freshness is no longer known.
     * Do not timestamp an old FIFO sequence as a fresh observation. */
    if(ADC1->ISR&ADC_FLAG_EOC){emergency_off(0);k=lock();PWM_OneShot_Trip(&shot,PWM_F_ADC_STALE|PWM_F_OVERRUN);unlock(k);return 1;}
    ADC1->ISR=ADC_FLAG_EOS;
    k=lock();
    if(shot.state==PWM_RUNNING){
        if(samples){delta=stamp-last_sample;if(delta>gap_max)gap_max=delta;}
        last_sample=stamp;raw_latest=raw;++samples;
        if(raw<raw_min)raw_min=raw;if(raw>raw_max)raw_max=raw;
        s=sample(raw,stamp,raw>=128U&&raw<=3967U,0U);PWM_OneShot_ADCISR(&shot,&s);
        if(scenario==6U||samples<=64U||samples-last_log>=100U){
            if(written>=CAPACITY-3U){++overflow;PWM_OneShot_Trip(&shot,F_BUFFER);}
            else{trace(2U,stamp,raw,flags);last_log=samples;}
        }
    }
    unlock(k);return 1;
}
void G03_PWM_Stop(void){uint32_t k=lock();if(owned&&shot.state==PWM_IDLE)PWM_OneShot_Trip(&shot,PWM_F_STOP);else PWM_OneShot_Stop(&shot);unlock(k);}
void G03_PWM_ProtocolFault(void){uint32_t k=lock();if(owned&&shot.state==PWM_IDLE)PWM_OneShot_Trip(&shot,PWM_F_PROTOCOL);else PWM_OneShot_ProtocolError(&shot);unlock(k);}
void G03_PWM_CPUFault(void){G02_EmergencyOff();if(shot.initialized)PWM_OneShot_Trip(&shot,PWM_F_EXTERNAL);}
uint32_t G03_PWM_Command(uint32_t op,uint32_t arg,uint32_t request_id)
{
    uint32_t k,r;PWMSample initial;
    if(op==40U&&!arg)return PWM_OK;
    if(op==49U)return G02_DISALLOWED;
    if(op==42U)return G03_PWM_ReportReady()&&arg<written?PWM_OK:PWM_BAD_ARGUMENT;
    if(op==43U&&!arg){G03_PWM_Stop();return PWM_OK;}
    if(op==45U&&!arg){k=lock();PWM_OneShot_Heartbeat(&shot);unlock(k);return PWM_OK;}
    if(op==47U){
        uint32_t begin=TIM2->CNT;
        if(!G03_PWM_Busy()||!arg||arg>300000U)return PWM_BAD_ARGUMENT;
        /* Intentional foreground-only stall. IRQ and timer remain enabled. */
        while((uint32_t)(TIM2->CNT-begin)<arg)__NOP();
        return PWM_OK;
    }
    G03_PWM_Task();
    if(op==44U&&!arg){k=lock();r=(uint32_t)PWM_OneShot_ClearFault(&shot);unlock(k);return r;}
    if(owned||G03_RelayBusy()||G03_ADC_BlocksOthers()||G03_SyntheticBusy()||G02_OwnsADC(&g02_control)||g02_control.faults)return PWM_BUSY;
    if(op==46U&&arg<=8U){if(request_used||shot.state!=PWM_IDLE)return PWM_ALREADY_USED;scenario=arg;return PWM_OK;}
    if(op!=41U||arg<1000U||arg>200000U)return PWM_BAD_ARGUMENT;
    if(request_used)return PWM_ALREADY_USED;
    if(shot.state!=PWM_IDLE)return PWM_FAULTED;
    written=overflow=samples=raw_max=last_sample=gap_max=irq_gap=irq_count=triggered=off_logged=last_log=injection_done=injection_at=0U;raw_min=4095U;
    start_id=request_id;request_used=1U;
    if(!preflight()){
        k=lock();if(!shot.faults)PWM_OneShot_Trip(&shot,PWM_F_ADAPTER);
        r=shot.faults==PWM_F_ADAPTER?PWM_ADAPTER_ERROR:PWM_FAULTED;
        unlock(k);G03_PWM_Task();return r;
    }
    memset(&profile,0,sizeof profile);
    /* Deliberate synthetic fixture facts for the closed-output model only.
     * Gates compile closed. These bits are NOT physical board evidence. */
    profile.enable_requested=1U;profile.verified_facts=PWM_FACT_ALL;profile.profile_id=0x44525931U;
    profile.arr=2000U;profile.ccr=1000U;profile.ccr_min=400U;profile.ccr_max=1600U;
    profile.deadtime_source=PWM_DEADTIME_DRIVER;profile.deadtime_code=0U;
    profile.run_us=arg;profile.max_run_us=200000U;profile.adc_max_age_us=2000U;
    profile.heartbeat_max_age_us=scenario==7U?20000U:300000U;profile.isr_max_gap_us=500U;
    profile.charge_max_ma=profile.discharge_max_ma=2000;profile.start_current_max_ma=1500;
    initial=sample(raw_latest,preflight_at,1U,0U);
    k=lock();r=(uint32_t)PWM_OneShot_Start(&shot,&profile,&initial);unlock(k);
    if(r!=PWM_OK){emergency_off(0);G03_PWM_Task();}
    return r;
}
int G03_PWM_Report(char *out,unsigned size,uint32_t id,uint32_t result,uint32_t op,uint32_t arg)
{
    uint32_t v[33],k;unsigned i;int n,m;
    if(op==42U&&result==PWM_OK&&arg<written&&G03_PWM_ReportReady()){
        const Row *r=&rows[arg];
        return snprintf(out,size,"#G3E," BMS_DIAG_FIRMWARE ",%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu",
            (unsigned long)id,(unsigned long)result,(unsigned long)arg,(unsigned long)r->event,(unsigned long)r->us,
            (unsigned long)r->raw,(unsigned long)r->flags,(unsigned long)r->ccr,(unsigned long)r->cnt,(unsigned long)r->phase,(unsigned long)r->bits);
    }
    k=lock();v[0]=id;v[1]=result;v[2]=(uint32_t)shot.state;v[3]=shot.faults;v[4]=request_used;v[5]=owned;v[6]=scenario;v[7]=start_id;
    v[8]=shot.start_us;v[9]=shot.stop_us;v[10]=now_us(0);v[11]=profile.run_us;v[12]=samples;v[13]=raw_latest;v[14]=raw_min;v[15]=raw_max;
    v[16]=last_sample;v[17]=gap_max;v[18]=irq_gap;v[19]=irq_count;v[20]=written;v[21]=overflow;v[22]=tim_hz;v[23]=adc_hz;
    v[24]=owned||restored?1000000U:0U;v[25]=request_used?profile.arr:TIM1->ARR;v[26]=request_used?profile.ccr:TIM1->CCR2;
    v[27]=request_used?profile.deadtime_code:TIM1->BDTR&TIM_BDTR_DTG;v[28]=bits();
    v[29]=(TIM1->CR1&TIM_CR1_CEN)?1U:0U;v[30]=restored;v[31]=0U;v[32]=0U;unlock(k);
    n=snprintf(out,size,"#G3P," BMS_DIAG_FIRMWARE);
    for(i=0;i<33U;++i){if(n<0||n>=(int)size)return -1;m=snprintf(out+n,size-(unsigned)n,",%lu",(unsigned long)v[i]);if(m<0)return -1;n+=m;}
    return n;
}
#endif
