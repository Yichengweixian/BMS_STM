/* Compiled as C++ only to attach side effects to modeled register reads.
 * This links the unchanged production g03_pwm_port.c and pwm_oneshot.c. */
#include "pwm_port_fixture/main.h"
#include "g03_pwm_port.h"
#include "pwm_oneshot.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

TIM_TypeDef model_tim1,model_tim2;
ADC_TypeDef model_adc1;
GPIO_TypeDef model_gpioa,model_gpiob,model_gpiof,model_gpiog;
ADC_HandleTypeDef hadc1;
G02Control g02_control;
static uint32_t primask, priorities[3],enabled[3],next_adc;
static uint32_t fifo[8],fifo_count,dr_reads,off_count,forbidden_enable_writes;
static uint32_t poll_fail,clock_fail,cleanup_fail,near_wrap,software_conversions;
static uint32_t timg_hz=400000000U,fixture_raw=1250U;
static uint32_t g02_owns,relay_busy,adc_other,synthetic_busy;
static uint32_t off_with_pending_adc,hal_wait_in_critical;
static uint32_t protocol_in_delay;

static void require_off(void)
{
    assert(!(TIM1->BDTR.value&(TIM_BDTR_MOE|TIM_BDTR_AOE)));
    assert(!TIM1->CCER.value);
    assert(!(GPIOB->ODR.value&SWS_Relay_Pin));
    assert(!(GPIOG->ODR.value&SWL_Relay_Pin));
    assert(!(GPIOA->ODR.value&GPIO_PIN_9));
    assert(!(GPIOF->ODR.value&GPIO_PIN_7));
    assert(!forbidden_enable_writes);
}
Reg::operator uint32_t() const
{
    if(kind!=ADC_DR_REG)return value;
    ++dr_reads;
    if(!fifo_count)return value;
    uint32_t raw=fifo[0];
    --fifo_count;
    memmove(fifo,fifo+1,fifo_count*sizeof *fifo);
    if(!fifo_count)ADC1->ISR.value&=~ADC_FLAG_EOC;
    return raw;
}
Reg &Reg::operator=(uint32_t next)
{
    if((kind==TIM1_BDTR_REG&&(next&(TIM_BDTR_MOE|TIM_BDTR_AOE)))||
       (kind==TIM1_CCER_REG&&next)||
       (kind==GPIO_B_ODR&&(next&SWS_Relay_Pin))||
       (kind==GPIO_G_ODR&&(next&SWL_Relay_Pin))||
       (kind==GPIO_A_ODR&&(next&GPIO_PIN_9))||
       (kind==GPIO_F_ODR&&(next&GPIO_PIN_7)))++forbidden_enable_writes;
    if(kind==ADC_ISR_REG){value&=~next;return *this;}
    if(kind==ADC_CR_REG&&(next&ADC_CR_ADSTP))next&=~(ADC_CR_ADSTP|ADC_CR_ADSTART);
    if(kind==TIM1_CR1_REG&&!(value&TIM_CR1_CEN)&&(next&TIM_CR1_CEN))next_adc=TIM2->CNT.value+10U;
    value=next;return *this;
}
static void push_adc(uint32_t raw)
{
    if(fifo_count==8U){ADC1->ISR.value|=ADC_FLAG_OVR;return;}
    fifo[fifo_count++]=raw;ADC1->DR.value=raw;
    ADC1->ISR.value|=ADC_FLAG_EOC|ADC_FLAG_EOS;
    if(raw<ADC1->AWD1LTR.value||raw>ADC1->AWD1HTR.value)ADC1->ISR.value|=ADC_FLAG_AWD1;
}
static void advance(uint32_t us)
{
    while(us--){
        if(TIM2->CR1.value&TIM_CR1_CEN)++TIM2->CNT.value;
        if((TIM1->CR1.value&TIM_CR1_CEN)&&(ADC1->CR.value&ADC_CR_ADSTART)&&TIM2->CNT.value==next_adc){
            next_adc+=10U;
            if((TIM1->CR2.value&TIM_CR2_MMS)==TIM_TRGO_UPDATE)push_adc(fixture_raw);
        }
        if((TIM2->DIER.value&TIM_DIER_CC1IE)&&TIM2->CNT.value==TIM2->CCR1.value)TIM2->SR.value|=TIM_SR_CC1IF;
        if(!primask&&enabled[TIM2_IRQn]&&(TIM2->SR.value&TIM_SR_CC1IF)&&(TIM2->DIER.value&TIM_DIER_CC1IE))G03_PWM_TimerIRQ();
        if(!primask&&enabled[ADC1_2_IRQn]&&(ADC1->ISR.value&ADC1->IER.value))G03_PWM_ADCIRQ();
        require_off();
    }
}
uint32_t __get_PRIMASK(void){return primask;}
void __disable_irq(void){primask=1U;}
void __set_PRIMASK(uint32_t value){primask=value;}
void __NOP(void){advance(1U);}
void __DSB(void){}
void G02_EmergencyOff(void)
{
    ++off_count;if(ADC1->ISR.value&(ADC_FLAG_AWD1|ADC_FLAG_OVR))++off_with_pending_adc;
    TIM1->BDTR&=~(TIM_BDTR_MOE|TIM_BDTR_AOE);TIM1->CCER=0;TIM1->DIER=0;TIM1->CR1&=~TIM_CR1_CEN;
    GPIOA->ODR=0;GPIOF->ODR=0;GPIOB->ODR=0;GPIOG->ODR=0;
}
int G02_OwnsADC(G02Control *){return (int)g02_owns;}
int G03_RelayBusy(void){return (int)relay_busy;}
void G03_RelayTask(void){}
int G03_ADC_BlocksOthers(void){return (int)adc_other;}
int G03_SyntheticBusy(void){return (int)synthetic_busy;}
uint32_t HAL_RCCEx_GetTIMGFreq(void){return clock_fail?200000000U:timg_hz;}
uint32_t HAL_RCCEx_GetPeriphCLKFreq(uint32_t){return 64000000U;}
void HAL_NVIC_SetPriority(IRQn irq,uint32_t priority,uint32_t){priorities[irq]=priority;}
void HAL_NVIC_ClearPendingIRQ(IRQn){}
void HAL_NVIC_EnableIRQ(IRQn irq){enabled[irq]=1U;}
void HAL_NVIC_DisableIRQ(IRQn irq){enabled[irq]=0U;}
void NVIC_EnableIRQ(IRQn irq){enabled[irq]=1U;}
void NVIC_DisableIRQ(IRQn irq){enabled[irq]=0U;}
uint32_t NVIC_GetPriority(IRQn irq){return priorities[irq];}
uint32_t NVIC_GetEnableIRQ(IRQn irq){return enabled[irq];}
void NVIC_SetPriority(IRQn irq,uint32_t priority){priorities[irq]=priority;}
static void hal_foreground(void){if(primask)++hal_wait_in_critical;assert(!primask);}
int HAL_ADC_Stop(ADC_HandleTypeDef *){hal_foreground();ADC1->CR=0U;fifo_count=0;ADC1->ISR.value=0;return HAL_OK;}
int HAL_ADC_Stop_IT(ADC_HandleTypeDef *h){hal_foreground();if(cleanup_fail)return HAL_ERROR;ADC1->IER=0;return HAL_ADC_Stop(h);}
int HAL_ADC_Init(ADC_HandleTypeDef *h)
{hal_foreground();ADC1->CFGR1=h->Init.ExternalTrigConv|h->Init.ExternalTrigConvEdge;ADC1->CFGR2=h->Init.Oversampling.RightBitShift|1U;return HAL_OK;}
int HAL_ADC_ConfigChannel(ADC_HandleTypeDef *,ADC_ChannelConfTypeDef *p)
{hal_foreground();ADC1->SQR1=p->Channel<<6;ADC1->PCSEL=1U<<p->Channel;ADC1->SMPR1=p->SamplingTime<<3;return HAL_OK;}
int HAL_ADC_Start(ADC_HandleTypeDef *)
{hal_foreground();if(near_wrap&&!software_conversions)TIM2->CNT.value=UINT32_MAX-64500U;++software_conversions;ADC1->CR=ADC_CR_ADEN;push_adc(fixture_raw);return HAL_OK;}
int HAL_ADC_Start_IT(ADC_HandleTypeDef *)
{hal_foreground();ADC1->CR=ADC_CR_ADEN|ADC_CR_ADSTART;ADC1->IER=ADC_IT_EOC|ADC_IT_EOS|ADC_IT_OVR|ADC_IT_AWD1;return HAL_OK;}
int HAL_ADC_PollForConversion(ADC_HandleTypeDef *,uint32_t){hal_foreground();return poll_fail?HAL_TIMEOUT:HAL_OK;}
uint32_t HAL_ADC_GetError(ADC_HandleTypeDef *){return 0U;}
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *){return ADC1->DR;}
int HAL_ADC_AnalogWDGConfig(ADC_HandleTypeDef *,ADC_AnalogWDGConfTypeDef *p)
{hal_foreground();ADC1->AWD1LTR=p->LowThreshold;ADC1->AWD1HTR=p->HighThreshold;ADC1->CFGR1|=1U<<22;return HAL_OK;}
void HAL_Delay(uint32_t ms)
{
    hal_foreground();advance((ms+1U)*1000U);
    if(protocol_in_delay&&software_conversions==4U){
        protocol_in_delay=0U;G03_PWM_ProtocolFault();
    }
}

static uint32_t field(unsigned index)
{
    char out[1024],*p=out;assert(G03_PWM_Report(out,sizeof out,123U,0U,40U,0U)>0);
    for(unsigned i=0;i<index+2U;++i){p=strchr(p,',');assert(p);++p;}
    return (uint32_t)strtoul(p,NULL,10);
}
static uint32_t event_count(unsigned event)
{
    unsigned count=0;char out[1024];
    for(uint32_t i=0;i<field(20);++i){
        assert(G03_PWM_Command(42U,i,1000U+i)==PWM_OK);
        assert(G03_PWM_Report(out,sizeof out,1000U+i,0U,42U,i)>0);
        char *p=out;for(unsigned j=0;j<5U;++j){p=strchr(p,',');assert(p);++p;}
        if(strtoul(p,NULL,10)==event)++count;
    }
    return count;
}
static uint32_t expected_adc[10],expected_tim[9];
static void setup(void)
{
    TIM1->CR1.kind=TIM1_CR1_REG;TIM1->CCER.kind=TIM1_CCER_REG;TIM1->BDTR.kind=TIM1_BDTR_REG;
    ADC1->CR.kind=ADC_CR_REG;ADC1->ISR.kind=ADC_ISR_REG;ADC1->DR.kind=ADC_DR_REG;
    GPIOA->ODR.kind=GPIO_A_ODR;GPIOB->ODR.kind=GPIO_B_ODR;GPIOF->ODR.kind=GPIO_F_ODR;GPIOG->ODR.kind=GPIO_G_ODR;
    TIM1->ARR=2000U;TIM1->RCR=1U;TIM1->CR1=TIM_COUNTERMODE_CENTERALIGNED1|TIM_CR1_DIR;
    TIM1->BDTR.value=TIM_BDTR_MOE|TIM_BDTR_AOE;TIM1->CCER.value=0x55U;GPIOG->ODR.value=SWL_Relay_Pin;
    TIM2->PSC=399U;TIM2->ARR=999U;TIM2->CNT=123U;TIM2->CCR1=321U;TIM2->CCMR1=0x42U;
    ADC1->SQR1=64U;ADC1->SMPR1=24U;ADC1->SMPR2=17U;ADC1->PCSEL=2U;
    ADC1->CFGR1=0x80000000U;ADC1->CFGR2=0x10021U;ADC1->CALFACT=11U;
    ADC1->AWD1LTR=0U;ADC1->AWD1HTR=4095U;
    hadc1.Init.ExternalTrigConv=0U;hadc1.Init.NbrOfConversion=1U;hadc1.Init.OversamplingMode=1U;hadc1.Init.Oversampling.Ratio=2U;hadc1.Init.Oversampling.RightBitShift=32U;
    priorities[ADC1_2_IRQn]=0U;enabled[ADC1_2_IRQn]=enabled[TIM2_IRQn]=enabled[TIM1_UP_IRQn]=1U;
    G03_PWM_Init();require_off();assert(field(2)==PWM_IDLE&&!field(4));
    uint32_t a[]={ADC1->SQR1,ADC1->SMPR1,ADC1->SMPR2,ADC1->PCSEL,ADC1->CFGR1,ADC1->CFGR2,ADC1->AWD1LTR,ADC1->AWD1HTR,ADC1->IER,ADC1->CALFACT};memcpy(expected_adc,a,sizeof a);
    uint32_t t[]={TIM2->PSC,TIM2->ARR,TIM2->CNT,TIM2->CR1,TIM2->CR2,TIM2->DIER,TIM2->CCER,TIM2->CCR1,TIM2->CCMR1};memcpy(expected_tim,t,sizeof t);
}
static void restored(void)
{
    G03_PWM_Task();require_off();assert(!G03_PWM_Owns()&&field(30)==1U);
    uint32_t a[]={ADC1->SQR1,ADC1->SMPR1,ADC1->SMPR2,ADC1->PCSEL,ADC1->CFGR1,ADC1->CFGR2,ADC1->AWD1LTR,ADC1->AWD1HTR,ADC1->IER,ADC1->CALFACT};assert(!memcmp(a,expected_adc,sizeof a));
    uint32_t t[]={TIM2->PSC,TIM2->ARR,TIM2->CNT,TIM2->CR1,TIM2->CR2,TIM2->DIER,TIM2->CCER,TIM2->CCR1,TIM2->CCMR1};assert(!memcmp(t,expected_tim,sizeof t));
    assert(enabled[ADC1_2_IRQn]&&enabled[TIM1_UP_IRQn]&&priorities[ADC1_2_IRQn]==0U);
    assert(!hal_wait_in_critical);
}
static void start(unsigned scenario,uint32_t duration)
{assert(G03_PWM_Command(46U,scenario,1U)==PWM_OK);assert(G03_PWM_Command(41U,duration,2U)==PWM_OK);assert(G03_PWM_Busy());assert(!(TIM1->CR1.value&TIM_CR1_DIR));require_off();}

int main(int argc,char **argv)
{
    assert(argc==2);setup();const char *which=argv[1];
    if(!strcmp(which,"deadline")||!strcmp(which,"wrap")){
        near_wrap=!strcmp(which,"wrap");
        g02_owns=1U;assert(G03_PWM_Command(41U,10000U,1U)==PWM_BUSY);g02_owns=0U;assert(!field(4));
        assert(G03_PWM_Command(49U,0U,1U)==G02_DISALLOWED);
        start(0U,10000U);uint32_t began=field(8);
        assert(G03_PWM_Command(47U,20000U,3U)==PWM_OK); /* foreground stalled */
        assert(field(2)==PWM_DONE&&!field(3));require_off();
        assert((uint32_t)(field(9)-began)==10000U&&field(12)==999U);
        assert(!field(30)&&G03_PWM_Owns());restored();
        assert(event_count(1U)==1U&&event_count(3U)==1U&&event_count(5U)==1U);
        assert(G03_PWM_Command(41U,10000U,4U)==PWM_ALREADY_USED);
    }else if(!strcmp(which,"stop")||!strcmp(which,"protocol")){
        start(0U,100000U);advance(1230U);
        if(!strcmp(which,"stop"))assert(G03_PWM_Command(43U,0U,3U)==PWM_OK);else G03_PWM_ProtocolFault();
        uint32_t reason=!strcmp(which,"stop")?PWM_F_STOP:PWM_F_PROTOCOL;
        assert(field(2)==PWM_FAULT&&(field(3)&reason));require_off();assert(!(TIM1->CR1.value&TIM_CR1_CEN));
        restored();assert(G03_PWM_Command(44U,0U,4U)==PWM_OK);assert(G03_PWM_Command(41U,1000U,5U)==PWM_ALREADY_USED);
    }else if(!strcmp(which,"preflight")||!strcmp(which,"clock")){
        poll_fail=!strcmp(which,"preflight");clock_fail=!strcmp(which,"clock");
        assert(G03_PWM_Command(41U,10000U,1U)==PWM_ADAPTER_ERROR);require_off();assert(field(4)==1U);
        if(poll_fail)restored();else G03_PWM_Task();
        assert(!G03_PWM_Owns());assert(G03_PWM_Command(44U,0U,2U)==PWM_OK);
        assert(G03_PWM_Command(41U,10000U,3U)==PWM_ALREADY_USED);
    }else if(!strcmp(which,"preflight_protocol")){
        protocol_in_delay=1U;
        assert(G03_PWM_Command(41U,10000U,1U)==PWM_FAULTED);
        assert(!protocol_in_delay&&software_conversions==4U);
        assert(field(2)==PWM_FAULT&&field(3)==PWM_F_PROTOCOL&&field(4)==1U);
        assert(!(TIM1->CR1.value&TIM_CR1_CEN)&&!field(12));require_off();restored();
        assert(event_count(1U)==0U&&event_count(3U)==0U&&event_count(4U)==1U);
        assert(G03_PWM_Command(44U,0U,2U)==PWM_OK);
        assert(G03_PWM_Command(41U,10000U,3U)==PWM_ALREADY_USED);
    }else if(!strcmp(which,"fault_flags")||!strcmp(which,"fifo")){
        start(0U,10000U);uint32_t before=dr_reads;
        push_adc(fixture_raw);push_adc(fixture_raw);
        if(!strcmp(which,"fault_flags"))ADC1->ISR.value|=ADC_FLAG_AWD1|ADC_FLAG_OVR;
        assert(G03_PWM_ADCIRQ());require_off();
        assert(field(2)==PWM_FAULT&&(field(3)&PWM_F_OVERRUN));
        if(!strcmp(which,"fault_flags")){assert(dr_reads==before&&off_with_pending_adc);assert(field(3)&PWM_F_OVERCURRENT);}
        else{assert(dr_reads==before+1U);assert(field(3)&PWM_F_ADC_STALE);}
        restored();assert(event_count(3U)==1U);
    }else if(!strcmp(which,"buffer")){
        start(6U,100000U);advance(6000U);
        assert(field(2)==PWM_FAULT&&(field(3)&(1U<<16)));require_off();restored();
        assert(field(20)==512U&&field(21)==1U);
        assert(event_count(3U)==1U&&event_count(4U)==1U&&event_count(5U)==1U);
    }else if(!strcmp(which,"overrun_scenario")){
        start(3U,100000U);advance(6000U);
        assert(field(2)==PWM_FAULT&&(field(3)&PWM_F_OVERRUN));require_off();restored();
    }else if(!strcmp(which,"awd_low")||!strcmp(which,"awd_high")){
        start(!strcmp(which,"awd_low")?4U:5U,100000U);uint32_t before=dr_reads;advance(10U);
        assert(field(2)==PWM_FAULT&&(field(3)&PWM_F_OVERCURRENT));assert(dr_reads==before);require_off();restored();
    }else if(!strcmp(which,"cleanup_failure")||!strcmp(which,"cleanup_failure_readback")){
        start(0U,10000U);advance(100U);G03_PWM_Stop();cleanup_fail=1U;G03_PWM_Task();require_off();
        assert(G03_PWM_Owns()&&G03_PWM_ReportReady());assert(field(3)&PWM_F_ADAPTER);
        assert(G03_PWM_Command(41U,10000U,4U)==PWM_BUSY);
        if(!strcmp(which,"cleanup_failure_readback")){
            char out[1024];uint32_t count=field(20),fault=field(3);assert(count>64U);
            for(uint32_t i=0;i<count;++i){
                assert(G03_PWM_Command(42U,i,1000U+i)==PWM_OK);
                assert(G03_PWM_Report(out,sizeof out,1000U+i,PWM_OK,42U,i)>0);
                assert(!strncmp(out,"#G3E,",strlen("#G3E,")));
                assert(G03_PWM_Owns()&&field(20)==count&&field(3)==fault);require_off();
            }
            assert(G03_PWM_Command(42U,count,2000U)==PWM_BAD_ARGUMENT);
            assert(event_count(3U)==1U&&event_count(4U)==1U);
            assert(G03_PWM_Command(41U,10000U,2001U)==PWM_BUSY);
        }
    }else assert(!"unknown test case");
    printf("PASS %s; production port with offline side-effect register model\n",which);
    return 0;
}
