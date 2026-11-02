#define ADC_LINK_MAIN previous_adc_link_main
#include "test_adc_link.c"
#undef main
#include "g03_relay_port.h"
#include "g03_relay_core.h"
#include "adbms_acquisition.h"
TIM_TypeDef test_tim2;
static unsigned afe_fault,spi_stall,afe_raw=9000;
static void elapsed(unsigned ms)
{
    while(ms--){++tick;DWT->CYCCNT+=800000U;
        if(TIM2->DIER&TIM_DIER_UIE){TIM2->SR=TIM_SR_UIF;G03_RelayTickIRQ();}
        assert(!(TIM1->CR1&TIM_CR1_CEN)&&!TIM1->CCER&&!(TIM1->BDTR&TIM_BDTR_MOE));
        assert(!(GPIOB->ODR&SWS_Relay_Pin));
    }
}
uint32_t Afe_PulsePrepare(void){elapsed(8);return 0;}
void Afe_PulseAcquire(MeasSample s[4])
{
    unsigned i;memset(s,0,4*sizeof *s);
    for(i=0;i<4;++i){s[i].start_ms=tick;s[i].raw=(uint16_t)(i<3?38900:afe_raw);s[i].has_raw=1;
        s[i].status=afe_fault?MEAS_PEC:0;}
    elapsed(spi_stall?60:7);
    for(i=0;i<4;++i)s[i].end_ms=tick;
}
static unsigned relay_field(unsigned index)
{
    char buf[1024],*s;unsigned i;
    assert(G03_RelayReport(buf,sizeof buf,1,0,30,0)>0);s=buf;
    for(i=0;i<index+2;++i){s=strchr(s,',');assert(s);++s;}
    return (unsigned)strtoul(s,0,10);
}
static void run_until(unsigned state,unsigned max_ms)
{while(relay_field(2)!=state && max_ms--){elapsed(1);G03_RelayTask();}assert(relay_field(2)==state);}
int main(void)
{
    unsigned off_tick,on,old_count,i,j;
    char saved_reply[sizeof reply];uint8_t flood[300];
    TIM1->ARR=2000;TIM1->RCR=1;TIM1->CR1=TIM_COUNTERMODE_CENTERALIGNED1|TIM_CR1_ARPE;
    TIM1->CCMR1=(TIM_OCMODE_PWM1<<8)|TIM_CCMR1_OC2PE;hadc1.Instance=ADC1;
    htim1.Instance=TIM1;G02_PortInit();G03_PortInit();G03_RelayInit();assert_off();
    send(1,31,0);assert(G03_RelayBusy() && !G02_MeasurementAllowed());
    elapsed(20);G03_RelayTask();send(1,31,0); /* replay cannot reset preparation */
    assert(G03_Command(11,100)==G03_BUSY);assert(G03_ADC_Command(21,5)==G03_BUSY);
    g02_command=G02_CMD_SAMPLE;G02_Task();assert(g02_command_result==G02_BUSY);
    run_until(G3R_PULSE,1500);old_count=relay_field(7);assert(old_count==50);assert_off();
    on=relay_field(10);memcpy(saved_reply,reply,sizeof reply);memset(flood,'X',sizeof flood);
    for(i=0;relay_field(2)==G3R_PULSE && i<120U;++i){
        for(j=0;j<20U;++j)send(1,31,0); /* replay traffic cannot extend the window */
        G02_LinkRx(flood,sizeof flood);G02_LinkTask(); /* RX overflow, then resynchronize */
        G02_LinkRx((const uint8_t *)"\n",1);G02_LinkTask();
        elapsed(1);G03_RelayTask();
        assert(relay_field(10)==on && relay_field(7)==old_count);
        assert(memcmp(saved_reply,reply,sizeof reply)==0); /* capture never formats TX */
    }
    assert(relay_field(2)==G3R_POST && relay_field(3)==0);
    assert((unsigned)(relay_field(11)-on)<=100U);
    puts("PASS relay repeated-request/RX-overflow pressure: no capture TX, no extended deadline");
    run_until(G3R_DONE,1500);assert_off();assert(relay_field(4)==G3R_END_DEADLINE);
    G02_LinkTask();expect(1,0,"#G3R");send(2,31,0);expect(2,G02_NOT_READY,"#G3R");
    send(3,35,0);expect(3,0,"#G3R");
#if G3R_LIVE_PROFILE_VERIFIED
    afe_raw=9200;G03_RelayCommand(32,0);run_until(G3R_FAULT,1800);
    assert(relay_field(3)&G3R_BASE);assert_off();assert(relay_field(19)==0);
    afe_raw=9000;G03_RelayCommand(35,0);
    send(4,32,0);run_until(G3R_PULSE,1500);on=tick;assert(GPIOG->ODR&SWL_Relay_Pin);
    send(4,32,0); /* same request must not retrigger */
    spi_stall=1;elapsed(20);G03_RelayTask();spi_stall=0;
    off_tick=relay_field(11);assert(!(GPIOG->ODR&SWL_Relay_Pin));assert(off_tick-on<=100);
    assert(relay_field(3)&G3R_STALE);run_until(G3R_FAULT,1500);
    send(5,35,0);send(6,32,0);expect(6,G02_DISALLOWED,"#G3R"); /* once per boot */
#else
    (void)off_tick;(void)on;
    send(4,32,0);expect(4,G02_DISALLOWED,"#G3R");
#endif
    G03_RelayCommand(35,0);G03_RelayCommand(31,0);run_until(G3R_PULSE,1500);
    G03_RelayStop();assert_off();assert(relay_field(4)==G3R_END_STOP);run_until(G3R_DONE,1500);
    G03_RelayCommand(35,0);G03_RelayCommand(31,0);afe_fault=1;run_until(G3R_FAULT,2000);
    assert(relay_field(3)&G3R_DATA);afe_fault=0;
    G03_RelayCommand(35,0);G03_RelayCommand(31,0);G03_RelayTask();
    elapsed(41);assert(relay_field(3)&G3R_STALE);assert_off();
    puts("PASS relay production adapter/link, interlocks, no replay, SPI stall/local cutoff, STOP and PEC");return 0;
}
