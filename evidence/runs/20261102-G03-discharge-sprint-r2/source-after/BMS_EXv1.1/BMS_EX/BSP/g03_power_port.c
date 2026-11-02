#include "g03_pwm_port.h"
#if defined(G03_PWM_LIVE_BUILD) && G03_PWM_LIVE_BUILD
#include "main.h"
#include "pwm_oneshot.h"
#include "g03_power_profile.h"
#include "g02_port.h"
#include "g03_port.h"
#include "g03_adc_port.h"
#include "g03_relay_port.h"
#include "g03_relay_profile.h"
#include "adbms_acquisition.h"
#include "firmware_identity.h"
#include <stdio.h>
#include <string.h>
#if G02_ALLOW_PIN_OUTPUT || G3R_LIVE_PROFILE_VERIFIED
#error "Other power entrypoints must remain disabled"
#endif
extern ADC_HandleTypeDef hadc2;
enum { IDLE, BASELINE, SETTLE, ACTIVE, COAST, RECOVERY, FINISHED };
enum { F_DATA=1U<<16, F_VOLTAGE=1U<<17, F_REGISTER=1U<<18,
       F_BUFFER=1U<<19, F_BASELINE=1U<<20, F_RECOVERY=1U<<21, F_LOAD=1U<<22 };
typedef struct {
    uint32_t phase,begin,end,ccr,arr,bits,adc_status,adc_begin,adc_end;
    uint16_t adc[3];
    MeasSample afe[8];
} PowerRow;
static PWMOneShot shot;
static PWMProfile profile;
static PowerRow rows[G3P_CAPACITY],working;
static uint32_t phase,owned,used,live,written,start_id,session_at,phase_at;
static uint32_t pwm_on_at,pwm_off_at,relay_on_at,relay_off_at,next_sample,last_data;
static uint32_t last_irq,max_irq_gap,zero_sum,zero_count,zero_min,zero_max,zero;
static uint32_t restored,restore_attempted,stopped_clock,recovery_good;
static uint32_t saved_timer[9],saved_priority,saved_enable;
static ADC_InitTypeDef saved_adc;
static uint32_t saved_adc_regs[6];
static uint32_t key_lock(void){uint32_t k=__get_PRIMASK();__disable_irq();return k;}
static void key_unlock(uint32_t k){__set_PRIMASK(k);}
static uint32_t now_us(void *ctx){(void)ctx;return owned?TIM2->CNT:stopped_clock;}
static uint32_t output_bits(void)
{
    return ((TIM1->BDTR&TIM_BDTR_MOE)?1U:0U)|(TIM1->CCER?2U:0U)|
        ((GPIOB->ODR&SWS_Relay_Pin)?8U:0U)|((GPIOG->ODR&SWL_Relay_Pin)?16U:0U)|
        (((GPIOA->ODR&GPIO_PIN_9)||(GPIOF->ODR&GPIO_PIN_7))?32U:0U);
}
static void pwm_off(void)
{
    CLEAR_BIT(TIM1->BDTR,TIM_BDTR_MOE|TIM_BDTR_AOE);
    TIM1->CCER=0U;TIM1->DIER=0U;CLEAR_BIT(TIM1->CR1,TIM_CR1_CEN);
    GPIOA->BSRR=GPIO_PIN_9<<16U;GPIOF->BSRR=GPIO_PIN_7<<16U;
    CLEAR_BIT(GPIOA->OTYPER,GPIO_PIN_9);CLEAR_BIT(GPIOF->OTYPER,GPIO_PIN_7);
    MODIFY_REG(GPIOA->MODER,3UL<<18U,1UL<<18U);
    MODIFY_REG(GPIOF->MODER,3UL<<14U,1UL<<14U);__DSB();
}
static void relay_off(void)
{
    GPIOB->BSRR=SWS_Relay_Pin<<16U;GPIOG->BSRR=SWL_Relay_Pin<<16U;__DSB();
    if(relay_on_at&&!relay_off_at)relay_off_at=now_us(0);
}
static void emergency_off(void *ctx)
{
    (void)ctx;pwm_off();
    if(phase==ACTIVE){pwm_off_at=now_us(0);phase_at=pwm_off_at;phase=COAST;}
    /* The independent timer also owns relay release. Keeping the passive
     * diode/load path for 20 ms is NOT a claim of zero inductor current. */
}
static void trip(uint32_t fault)
{
    PWM_OneShot_Trip(&shot,fault);relay_off();
    if(owned&&phase!=RECOVERY&&phase!=FINISHED){phase=RECOVERY;phase_at=now_us(0);}
}
static int register_ok(void)
{
    if(TIM1->PSC||TIM1->ARR!=G3P_ARR||TIM1->CCR2!=G3P_CCR||TIM1->RCR!=1U)return 0;
    if((TIM1->CR1&TIM_CR1_CMS)!=TIM_COUNTERMODE_CENTERALIGNED1)return 0;
    if((TIM1->CCMR1&TIM_CCMR1_OC2M)!=(TIM_OCMODE_PWM1<<8U)||!(TIM1->CCMR1&TIM_CCMR1_OC2PE))return 0;
    if(TIM1->BDTR&(TIM_BDTR_AOE|TIM_BDTR_DTG))return 0;
    if(phase==ACTIVE&&live){
        if(output_bits()!=19U||!(TIM1->CR1&TIM_CR1_CEN))return 0;
        if(TIM1->CCER!=(TIM_CCER_CC2E|TIM_CCER_CC2NE))return 0;
        if((GPIOA->MODER&(3UL<<18U))!=(2UL<<18U)||(GPIOF->MODER&(3UL<<14U))!=(2UL<<14U))return 0;
        if(((GPIOA->AFR[1]>>4U)&15U)!=1U||((GPIOF->AFR[0]>>28U)&15U)!=1U)return 0;
    }else if(output_bits()!=((live&&(phase==SETTLE||phase==COAST))?16U:0U))return 0;
    return 1;
}
static int prepare(void *ctx,const PWMProfile *p)
{
    (void)ctx;
    if(phase!=SETTLE||!owned||p->ccr!=G3P_CCR||p->arr!=G3P_ARR||!register_ok())return 0;
    SET_BIT(TIM1->BDTR,TIM_BDTR_OSSI|TIM_BDTR_OSSR);
    CLEAR_BIT(TIM1->CR2,TIM_CR2_OIS2|TIM_CR2_OIS2N);
    CLEAR_BIT(TIM1->CR1,TIM_CR1_CEN|TIM_CR1_CMS|TIM_CR1_UDIS|TIM_CR1_DIR);
    SET_BIT(TIM1->CR1,TIM_COUNTERMODE_CENTERALIGNED1|TIM_CR1_URS);
    MODIFY_REG(TIM1->CR2,TIM_CR2_MMS,TIM_TRGO_ENABLE);
    TIM1->CNT=0U;TIM1->CCR2=p->ccr;TIM1->EGR=TIM_EGR_UG;TIM1->SR=0U;
    /* No TRGO ADC is used. The verified AFE branch supplies slow monitoring;
     * external source CC constrains sustained input, not switching peaks. */
    return TIM1->CCR2==p->ccr;
}
static int enable_pair(void *ctx)
{
    (void)ctx;
    if(!register_ok()||!(TIM2->DIER&TIM_DIER_CC1IE))return 0;
    if(live){
        MODIFY_REG(GPIOA->AFR[1],15UL<<4U,1UL<<4U);
        MODIFY_REG(GPIOF->AFR[0],15UL<<28U,1UL<<28U);
        MODIFY_REG(GPIOA->MODER,3UL<<18U,2UL<<18U);
        MODIFY_REG(GPIOF->MODER,3UL<<14U,2UL<<14U);
        TIM1->CCER=TIM_CCER_CC2E|TIM_CCER_CC2NE;
    }
    phase=ACTIVE;pwm_on_at=phase_at=now_us(0);
    SET_BIT(TIM1->CR1,TIM_CR1_CEN);
    if(live)SET_BIT(TIM1->BDTR,TIM_BDTR_MOE);
    __DSB();return register_ok();
}
static int after_off(void *ctx,PWMState state,uint32_t faults)
{(void)ctx;(void)state;(void)faults;return output_bits()==0U;}
static const PWMOps ops={now_us,emergency_off,prepare,enable_pair,after_off};
static int32_t current_ma(uint32_t raw)
{return ((int32_t)raw-(int32_t)zero)*199/1500;}
void G03_PWM_Init(void)
{G02_EmergencyOff();(void)PWM_OneShot_Init(&shot,&ops,0);}
int G03_PWM_Busy(void){return owned&&phase!=FINISHED;}
int G03_PWM_Owns(void){return owned!=0U;}
int G03_PWM_Blocks(void){return owned||shot.faults;}
int G03_PWM_ReportReady(void){return !owned;}
int G03_PWM_ADCIRQ(void){return 0;}
static int take_resources(void)
{
    ADC_ChannelConfTypeDef ch={0};
    if(HAL_RCCEx_GetTIMGFreq()!=400000000U||HAL_RCCEx_GetPeriphCLKFreq(RCC_PERIPHCLK_ADC)!=64000000U)return 0;
    G03_RelayTask();G02_EmergencyOff();
    saved_timer[0]=TIM2->PSC;saved_timer[1]=TIM2->ARR;saved_timer[2]=TIM2->CNT;saved_timer[3]=TIM2->CR1;
    saved_timer[4]=TIM2->CR2;saved_timer[5]=TIM2->DIER;saved_timer[6]=TIM2->CCER;saved_timer[7]=TIM2->CCR1;saved_timer[8]=TIM2->CCMR1;
    saved_priority=NVIC_GetPriority(TIM2_IRQn);saved_enable=NVIC_GetEnableIRQ(TIM2_IRQn);
    saved_adc=hadc2.Init;saved_adc_regs[0]=ADC2->SQR1;saved_adc_regs[1]=ADC2->SMPR1;saved_adc_regs[2]=ADC2->SMPR2;
    saved_adc_regs[3]=ADC2->PCSEL;saved_adc_regs[4]=ADC2->CFGR1;saved_adc_regs[5]=ADC2->CFGR2;
    owned=1U;TIM2->CR1=0U;TIM2->DIER=0U;TIM2->CR2=0U;TIM2->CCER=0U;
    TIM2->PSC=399U;TIM2->ARR=0xffffffffU;TIM2->CNT=0U;TIM2->EGR=TIM_EGR_UG;TIM2->SR=0U;
    TIM2->CCR1=100U;TIM2->DIER=TIM_DIER_CC1IE;TIM2->CR1=TIM_CR1_CEN;
    HAL_NVIC_SetPriority(TIM2_IRQn,0U,0U);HAL_NVIC_ClearPendingIRQ(TIM2_IRQn);HAL_NVIC_EnableIRQ(TIM2_IRQn);
    session_at=phase_at=last_data=last_irq=now_us(0);phase=BASELINE;
    TIM1->CCR2=G3P_CCR;
    if(HAL_ADC_Stop(&hadc2)!=HAL_OK)return 0;
    hadc2.Init.ExternalTrigConv=ADC_SOFTWARE_START;hadc2.Init.ExternalTrigConvEdge=ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc2.Init.NbrOfConversion=1U;hadc2.Init.ScanConvMode=ADC_SCAN_DISABLE;hadc2.Init.EOCSelection=ADC_EOC_SINGLE_CONV;
    hadc2.Init.OversamplingMode=DISABLE;
    if(HAL_ADC_Init(&hadc2)!=HAL_OK)return 0;
    ch.Channel=ADC_CHANNEL_0;ch.Rank=ADC_REGULAR_RANK_1;ch.SamplingTime=ADC_SAMPLETIME_11CYCLES_5;
    ch.SingleDiff=ADC_SINGLE_ENDED;ch.OffsetNumber=ADC_OFFSET_NONE;
    if(HAL_ADC_ConfigChannel(&hadc2,&ch)!=HAL_OK)return 0;
    return Afe_PulsePrepare()==0U;
}
static void acquire(void)
{
    uint32_t i;ADC_ChannelConfTypeDef ch={0};
    const uint32_t channels[3]={ADC_CHANNEL_0,ADC_CHANNEL_14,ADC_CHANNEL_11};
    memset(&working,0,sizeof working);working.phase=phase;working.begin=now_us(0);
    working.ccr=TIM1->CCR2;working.arr=TIM1->ARR;working.bits=output_bits();
    Afe_PowerAcquire(working.afe);
    working.adc_begin=now_us(0);
    ch.Rank=ADC_REGULAR_RANK_1;ch.SamplingTime=ADC_SAMPLETIME_11CYCLES_5;ch.SingleDiff=ADC_SINGLE_ENDED;ch.OffsetNumber=ADC_OFFSET_NONE;
    for(i=0;i<3U;++i){
        ch.Channel=channels[i];
        if(HAL_ADC_Stop(&hadc2)!=HAL_OK||HAL_ADC_ConfigChannel(&hadc2,&ch)!=HAL_OK||
           HAL_ADC_Start(&hadc2)!=HAL_OK||HAL_ADC_PollForConversion(&hadc2,2U)!=HAL_OK){working.adc_status|=MEAS_ADC;break;}
        working.adc[i]=(uint16_t)HAL_ADC_GetValue(&hadc2);
        if(HAL_ADC_GetError(&hadc2))working.adc_status|=MEAS_ADC;
    }
    if(HAL_ADC_Stop(&hadc2)!=HAL_OK)working.adc_status|=MEAS_ADC;
    working.adc_end=working.end=now_us(0);
}
static uint32_t assess(void)
{
    uint32_t i,f=0U;
    for(i=0;i<8U;++i)if(!Meas_Evaluate(&working.afe[i],i<7U?(MeasChannel)i:MEAS_REF2,HAL_GetTick()).raw_valid)f|=F_DATA;
    for(i=0;i<3U;++i)if(working.afe[i].raw<G3P_CELL_LOW||working.afe[i].raw>G3P_CELL_HIGH)f|=F_VOLTAGE;
    if(working.adc_status||working.adc[0]>=4090U||working.adc[1]>=4090U||working.adc[2]>=4090U)f|=F_DATA;
    return f;
}
static void restore(void)
{
    uint32_t k;int good;
    if(restore_attempted)return;restore_attempted=1U;
    G02_EmergencyOff();good=HAL_ADC_Stop(&hadc2)==HAL_OK;hadc2.Init=saved_adc;
    if(HAL_ADC_Init(&hadc2)!=HAL_OK)good=0;
    ADC2->SQR1=saved_adc_regs[0];ADC2->SMPR1=saved_adc_regs[1];ADC2->SMPR2=saved_adc_regs[2];
    ADC2->PCSEL=saved_adc_regs[3];ADC2->CFGR1=saved_adc_regs[4];ADC2->CFGR2=saved_adc_regs[5];
    good=good&&ADC2->SQR1==saved_adc_regs[0]&&ADC2->CFGR1==saved_adc_regs[4]&&ADC2->CFGR2==saved_adc_regs[5];
    k=key_lock();TIM2->DIER=0U;stopped_clock=TIM2->CNT;
    if(!good){trip(PWM_F_ADAPTER);key_unlock(k);return;}
    (void)PWM_OneShot_Service(&shot);
    TIM2->CR1=0U;TIM2->PSC=saved_timer[0];TIM2->ARR=saved_timer[1];TIM2->CR2=saved_timer[4];
    TIM2->CCER=saved_timer[6];TIM2->CCR1=saved_timer[7];TIM2->CCMR1=saved_timer[8];TIM2->EGR=TIM_EGR_UG;
    TIM2->CNT=saved_timer[2];TIM2->SR=0U;TIM2->DIER=saved_timer[5];TIM2->CR1=saved_timer[3];
    NVIC_SetPriority(TIM2_IRQn,saved_priority);if(!saved_enable)HAL_NVIC_DisableIRQ(TIM2_IRQn);
    owned=0U;restored=1U;key_unlock(k);
}
void G03_PWM_Task(void)
{
    uint32_t k,stamp,f,i;PWMSample s;PWMResult r;
    if(!owned)return;
    if(phase==FINISHED){restore();return;}
    stamp=now_us(0);if((int32_t)(stamp-next_sample)<0)return;next_sample=stamp+G3P_SAMPLE_US;
    acquire();f=assess();k=key_lock();stamp=now_us(0);
    if(written<G3P_CAPACITY)rows[written++]=working;else f|=F_BUFFER;
    /* Never refresh the deadline with an acquisition that started before the
     * previous monitor deadline expired. Conversion-start is conservative. */
    if(stamp-last_data>=G3P_STALE_US)f|=PWM_F_ADC_STALE;
    if(!f)last_data=working.begin;
    if(f){trip(f);key_unlock(k);return;}
    if(phase==BASELINE){
        uint32_t raw=working.afe[3].raw;
        for(i=0;i<3U;++i)if(working.afe[i].raw<G3P_CELL_START_LOW||working.afe[i].raw>G3P_CELL_START_HIGH)f|=F_BASELINE;
        if(raw<zero_min)zero_min=raw;if(raw>zero_max)zero_max=raw;zero_sum+=raw;++zero_count;
        if(raw<G3P_ZERO_LOW||raw>G3P_ZERO_HIGH||zero_max-zero_min>G3P_ZERO_SPAN)f|=F_BASELINE;
        if(f)trip(f);
        else if(stamp-session_at>=G3P_PRE_US&&zero_count>=16U){
            zero=zero_sum/zero_count;
            phase=SETTLE;phase_at=stamp;
            if(live){GPIOB->BSRR=SWS_Relay_Pin<<16U;GPIOG->BSRR=SWL_Relay_Pin;__DSB();relay_on_at=now_us(0);}
        }
    }else if(phase==SETTLE||phase==ACTIVE){
        s.at_us=working.begin;s.current_ma=current_ma(working.afe[3].raw);s.valid=1U;s.overrun=0U;
        if(s.current_ma>G3P_CHARGE_MA||s.current_ma< -G3P_DISCHARGE_MA)trip(PWM_F_OVERCURRENT);
        else if(phase==SETTLE&&stamp-phase_at>=G3P_SETTLE_US){
            if(live&&(s.current_ma> -G3P_PASSIVE_MIN_MA||s.current_ma< -G3P_PASSIVE_MAX_MA))trip(F_LOAD);
            else{r=PWM_OneShot_Start(&shot,&profile,&s);if(r!=PWM_OK)trip(PWM_F_ADAPTER);}
        }else if(phase==ACTIVE)PWM_OneShot_ADCISR(&shot,&s);
    }else if(phase==RECOVERY){
        int32_t ma=current_ma(working.afe[3].raw);
        if(ma>=-20&&ma<=20)++recovery_good;else recovery_good=0U;
    }
    key_unlock(k);
}
int G03_PWM_TimerIRQ(void)
{
    uint32_t k,stamp,gap;
    if(!owned)return 0;
    if(!(TIM2->SR&TIM_SR_CC1IF)||!(TIM2->DIER&TIM_DIER_CC1IE))return 1;
    TIM2->SR=~TIM_SR_CC1IF;stamp=TIM2->CNT;TIM2->CCR1=stamp+100U;k=key_lock();
    gap=stamp-last_irq;last_irq=stamp;if(gap>max_irq_gap)max_irq_gap=gap;
    if(phase!=FINISHED&&phase!=RECOVERY){
        if(gap>500U)trip(PWM_F_ISR_LATE);
        else if(stamp-last_data>=G3P_STALE_US)trip(PWM_F_ADC_STALE);
        else if(!register_ok())trip(F_REGISTER);
    }
    if(phase==ACTIVE)PWM_OneShot_PeriodicISR(&shot);
    /* Core callbacks timestamp transitions after the IRQ entry stamp. Reusing
     * the earlier stamp would underflow stamp-phase_at and skip the coast.
     * Refresh from the hardware counter AFTER every possible transition. */
    stamp=now_us(0);
    if(phase==SETTLE&&stamp-phase_at>=G3P_SETTLE_US+G3P_STALE_US)trip(PWM_F_ADC_STALE);
    stamp=now_us(0);
    if(phase==COAST&&stamp-phase_at>=G3P_COAST_US){relay_off();phase=RECOVERY;phase_at=stamp;}
    stamp=now_us(0);
    if(phase==RECOVERY&&stamp-phase_at>=G3P_RECOVERY_US){
        if(recovery_good<5U)trip(F_RECOVERY);
        pwm_off();relay_off();phase=FINISHED;
    }
    key_unlock(k);return 1;
}
void G03_PWM_Stop(void){uint32_t k=key_lock();if(phase!=FINISHED)trip(PWM_F_STOP);else G02_EmergencyOff();key_unlock(k);}
void G03_PWM_ProtocolFault(void){uint32_t k=key_lock();if(owned&&phase!=FINISHED)trip(PWM_F_PROTOCOL);key_unlock(k);}
void G03_PWM_CPUFault(void){G02_EmergencyOff();if(shot.initialized)trip(PWM_F_EXTERNAL);}
uint32_t G03_PWM_Command(uint32_t op,uint32_t arg,uint32_t id)
{
    uint32_t k;
    if(op==40U&&!arg)return PWM_OK;
    if(op==42U)return !owned&&arg<written?PWM_OK:PWM_BAD_ARGUMENT;
    if(op==43U&&!arg){G03_PWM_Stop();return PWM_OK;}
    if(op==45U&&!arg){k=key_lock();PWM_OneShot_Heartbeat(&shot);key_unlock(k);return PWM_OK;}
    if(op==44U&&!arg){k=key_lock();if(owned){key_unlock(k);return PWM_BUSY;}arg=PWM_OneShot_ClearFault(&shot);key_unlock(k);return arg;}
    /* Separate exact commands: rehearsal never touches a relay; live requires
     * the frozen contract ID. Neither command accepts duty or time overrides. */
    if((op!=41U&&op!=49U)||arg!=G3P_PROFILE_ID)return PWM_BAD_ARGUMENT;
    if(used)return PWM_ALREADY_USED;
    if(owned||G03_RelayBusy()||G03_ADC_BlocksOthers()||G03_SyntheticBusy()||G02_OwnsADC(&g02_control)||g02_control.faults)return PWM_BUSY;
    if(shot.state!=PWM_IDLE||shot.faults||output_bits())return PWM_NOT_READY;
    used=1U;live=op==49U;start_id=id;zero_min=65535U;
    memset(&profile,0,sizeof profile);
    profile.enable_requested=1U;profile.verified_facts=PWM_FACT_ALL;profile.profile_id=G3P_PROFILE_ID;
    profile.arr=G3P_ARR;profile.ccr=profile.ccr_min=profile.ccr_max=G3P_CCR;
    profile.deadtime_source=PWM_DEADTIME_DRIVER;profile.run_us=profile.max_run_us=G3P_RUN_US;
    profile.adc_max_age_us=G3P_STALE_US;profile.heartbeat_max_age_us=200000U;profile.isr_max_gap_us=500U;
    profile.charge_max_ma=G3P_CHARGE_MA;profile.discharge_max_ma=G3P_DISCHARGE_MA;
    /* Passive-load current is already present after relay closure. The core
     * uses symmetric pre-start magnitude; use the discharge bound for both
     * here, then enforce the tighter reverse-current guard in the adapter. */
    profile.charge_max_ma=G3P_DISCHARGE_MA;profile.start_current_max_ma=G3P_DISCHARGE_MA-1;
    if(!take_resources()){k=key_lock();trip(PWM_F_ADAPTER);key_unlock(k);return PWM_ADAPTER_ERROR;}
    return PWM_OK;
}
int G03_PWM_Report(char *out,unsigned size,uint32_t id,uint32_t result,uint32_t op,uint32_t arg)
{
    uint32_t v[25],k,i;int n,m;
    if(op==42U&&result==PWM_OK&&arg<written&&!owned){
        const PowerRow *r=&rows[arg];
        n=snprintf(out,size,"#G3L," BMS_DIAG_FIRMWARE ",%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%u,%u,%u",
            (unsigned long)id,(unsigned long)result,(unsigned long)arg,(unsigned long)r->phase,(unsigned long)r->begin,(unsigned long)r->end,
            (unsigned long)r->ccr,(unsigned long)r->arr,(unsigned long)r->bits,(unsigned long)r->adc_status,(unsigned long)r->adc_begin,(unsigned long)r->adc_end,r->adc[0],r->adc[1],r->adc[2]);
        for(i=0;i<8U;++i){const MeasSample *s=&r->afe[i];
            if(n<0||n>=(int)size)return -1;
            m=snprintf(out+n,size-(unsigned)n,",%u,%lu,%lu,%lu,%u,%02X%02X%02X%02X%02X%02X%02X%02X",s->raw,(unsigned long)s->start_ms,(unsigned long)s->end_ms,(unsigned long)s->status,s->has_raw,
                s->frame[0],s->frame[1],s->frame[2],s->frame[3],s->frame[4],s->frame[5],s->frame[6],s->frame[7]);if(m<0)return -1;n+=m;
        }return n;
    }
    k=key_lock();v[0]=id;v[1]=result;v[2]=phase;v[3]=shot.faults;v[4]=used;v[5]=owned;v[6]=live;v[7]=start_id;
    v[8]=G3P_PROFILE_ID;v[9]=G3P_CCR;v[10]=G3P_ARR;v[11]=G3P_RUN_US;v[12]=written;v[13]=output_bits();
    v[14]=restored;v[15]=pwm_on_at;v[16]=pwm_off_at;v[17]=relay_on_at;v[18]=relay_off_at;v[19]=max_irq_gap;
    v[20]=zero;v[21]=recovery_good;v[22]=1U;v[23]=0U;v[24]=(uint32_t)shot.state;key_unlock(k);
    n=snprintf(out,size,"#G3Q," BMS_DIAG_FIRMWARE);
    for(i=0;i<25U;++i){if(n<0||n>=(int)size)return -1;m=snprintf(out+n,size-(unsigned)n,",%lu",(unsigned long)v[i]);if(m<0)return -1;n+=m;}return n;
}
#endif
