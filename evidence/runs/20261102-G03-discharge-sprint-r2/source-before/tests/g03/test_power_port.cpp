#include "main.h"
#include "g03_pwm_port.h"
#include "g03_power_profile.h"
#include "measurement_core.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
TIM_TypeDef model_tim1,model_tim2;
ADC_TypeDef model_adc1,model_adc2;
GPIO_TypeDef model_gpioa,model_gpiob,model_gpiof,model_gpiog;
ADC_HandleTypeDef hadc2;
G02Control g02_control;
static uint32_t primask,ticks,channel;
static int bad_data,large_current,block_foreground;
static unsigned enable_count;
Reg::operator uint32_t()const{return value;}
Reg &Reg::operator=(uint32_t v){
    if(this==&model_gpioa.BSRR)model_gpioa.ODR.value=(model_gpioa.ODR.value|(v&65535U))&~(v>>16U);
    if(this==&model_gpiof.BSRR)model_gpiof.ODR.value=(model_gpiof.ODR.value|(v&65535U))&~(v>>16U);
    if(this==&model_gpiob.BSRR)model_gpiob.ODR.value=(model_gpiob.ODR.value|(v&65535U))&~(v>>16U);
    if(this==&model_gpiog.BSRR)model_gpiog.ODR.value=(model_gpiog.ODR.value|(v&65535U))&~(v>>16U);
    if(this==&model_tim1.BDTR&&!(value&TIM_BDTR_MOE)&&(v&TIM_BDTR_MOE))++enable_count;
    value=v;return *this;
}
uint32_t __get_PRIMASK(){return primask;}void __disable_irq(){primask=1;}
void __set_PRIMASK(uint32_t v){primask=v;}void __DSB(){}void __NOP(){}
uint32_t HAL_GetTick(){return ticks/1000U;}
uint32_t HAL_RCCEx_GetTIMGFreq(){return 400000000U;}
uint32_t HAL_RCCEx_GetPeriphCLKFreq(uint32_t){return 64000000U;}
void HAL_NVIC_SetPriority(IRQn,uint32_t,uint32_t){}void HAL_NVIC_ClearPendingIRQ(IRQn){}
void HAL_NVIC_EnableIRQ(IRQn){}void HAL_NVIC_DisableIRQ(IRQn){}
uint32_t NVIC_GetPriority(IRQn){return 0;}uint32_t NVIC_GetEnableIRQ(IRQn){return 0;}
void NVIC_SetPriority(IRQn,uint32_t){}
int HAL_ADC_Stop(ADC_HandleTypeDef*){return HAL_OK;}int HAL_ADC_Init(ADC_HandleTypeDef*){return HAL_OK;}
int HAL_ADC_ConfigChannel(ADC_HandleTypeDef*,ADC_ChannelConfTypeDef *c){channel=c->Channel;return HAL_OK;}
int HAL_ADC_Start(ADC_HandleTypeDef*){return HAL_OK;}
int HAL_ADC_PollForConversion(ADC_HandleTypeDef*,uint32_t){return HAL_OK;}
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef*){return channel==14U?0U:1300U;}
uint32_t HAL_ADC_GetError(ADC_HandleTypeDef*){return 0;}
void G02_EmergencyOff(){model_tim1.BDTR&=~TIM_BDTR_MOE;model_tim1.CCER=0;model_tim1.CR1&=~TIM_CR1_CEN;model_gpiob.ODR=0;model_gpiog.ODR=0;}
int G02_OwnsADC(G02Control*){return 0;}int G03_RelayBusy(){return 0;}
void G03_RelayTask(){}int G03_ADC_BlocksOthers(){return 0;}int G03_SyntheticBusy(){return 0;}
static void advance(uint32_t us){
    for(uint32_t i=0;i<us;i+=100U){ticks+=100U;if(model_tim2.CR1&TIM_CR1_CEN)model_tim2.CNT=(uint32_t)model_tim2.CNT+100U;
        if(model_tim2.DIER&TIM_DIER_CC1IE){model_tim2.SR=TIM_SR_CC1IF;assert(!primask);G03_PWM_TimerIRQ();}}
}
uint32_t Afe_PulsePrepare(){advance(7000U);return 0;}
void Afe_PowerAcquire(MeasSample s[8]){
    uint32_t start=HAL_GetTick();advance(9000U);memset(s,0,sizeof(MeasSample)*8);
    for(unsigned i=0;i<8;++i){s[i].has_raw=1;s[i].raw=i<3?35000:9000;s[i].start_ms=start;s[i].end_ms=HAL_GetTick();}
    if(model_gpiog.ODR&SWS_Relay_Pin)s[3].raw=(model_tim1.BDTR&TIM_BDTR_MOE)?6000:6600;
    if(large_current)s[3].raw=1000;
    if(bad_data)s[3].status=MEAS_PEC;
}
MeasValue Meas_Evaluate(const MeasSample*s,MeasChannel,uint32_t){MeasValue v={};v.raw_valid=s->has_raw&&!s->status;return v;}
static unsigned long fields[25];
static void status(){char text[1024];assert(G03_PWM_Report(text,sizeof text,1,0,40,0)>0);
    char *p=strchr(text,',');p=strchr(p+1,',');for(unsigned i=0;i<25;++i){fields[i]=strtoul(p+1,&p,10);}}
static void until(unsigned phase){for(unsigned i=0;i<50000;++i){advance(100);if(!block_foreground)G03_PWM_Task();status();if(fields[2]==phase)return;}assert(false);}
int main(int argc,char**argv){
    assert(argc==2);std::string name=argv[1];
    model_tim1.ARR=2000;model_tim1.RCR=1;model_tim1.CCR2=1800;
    model_tim1.CR1=TIM_COUNTERMODE_CENTERALIGNED1;model_tim1.CCMR1=(TIM_OCMODE_PWM1<<8U)|TIM_CCMR1_OC2PE;
    G03_PWM_Init();status();assert(fields[4]==0&&fields[13]==0&&enable_count==0);
    assert(G03_PWM_Command(49,0,2)!=0);assert(enable_count==0);
    bool dry=name=="dry";
    assert(G03_PWM_Command(dry?41:49,G3P_PROFILE_ID,3)==0);
    if(name=="stop_baseline")G03_PWM_Stop();
    else if(name=="stop_settle"){until(2);G03_PWM_Stop();}
    else if(name=="bad_baseline"){bad_data=1;}
    else{
        until(3);assert(enable_count==(dry?0U:1U));
        if(name=="stop")G03_PWM_Stop();
        if(name=="protocol")G03_PWM_ProtocolFault();
        if(name=="overcurrent")large_current=1;
        if(name=="pec")bad_data=1;
        if(name=="ccr")model_tim1.CCR2=1600;
        if(name=="stale"){block_foreground=1;advance(50000);block_foreground=0;}
        if(name=="late_irq"){model_tim2.CNT=(uint32_t)model_tim2.CNT+600U;advance(100);}
        if(name=="replay")assert(G03_PWM_Command(49,G3P_PROFILE_ID,4)!=0);
    }
    until(6);G03_PWM_Task();status();
    assert(fields[13]==0&&fields[5]==0&&fields[14]==1);
    assert(G03_PWM_Command(49,G3P_PROFILE_ID,5)!=0);
    if(name=="normal"||name=="dry"||name=="replay"){
        assert(fields[3]==0);assert(fields[16]-fields[15]>=100000&&fields[16]-fields[15]<=100100);
        if(!dry)assert(fields[18]-fields[16]>=20000&&fields[18]-fields[16]<=20100);
    }else assert(fields[3]!=0);
    if(name.find("baseline")!=std::string::npos||name=="stop_settle")assert(enable_count==0);
    else assert(enable_count==(dry?0U:1U));
    if(fields[3]){(void)G03_PWM_Command(44,0,6);assert(G03_PWM_Command(49,G3P_PROFILE_ID,7)!=0);}
    printf("PASS %s: outputs off; once token retained; independent timer and resource restore\n",argv[1]);
}
