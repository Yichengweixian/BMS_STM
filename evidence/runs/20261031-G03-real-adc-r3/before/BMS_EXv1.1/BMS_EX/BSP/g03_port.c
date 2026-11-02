#include "g03_port.h"
#include "g03_adc_port.h"
#include "g02_port.h"
#include "main.h"
#include <stdio.h>
/* Synthetic fixture v1, NOT measured limits or calibration.
 * No function in this adapter can enable a timer, PWM pin or relay. */
static const G03Config fixture={1U,20U,30U,20U,200U,800U,100U,10000U,400U,1600U,
    3000,4200,500,500,0,45000,20};
static G03Control control;
static uint32_t scenario,tick_count,last_tick_ms,max_tick_gap,fixture_selected;
static uint32_t lock(void){uint32_t k=__get_PRIMASK();__disable_irq();return k;}
static void unlock(uint32_t k){__set_PRIMASK(k);}
static uint32_t output_bits(void)
{
    uint32_t b=0U;
    if(TIM1->BDTR&TIM_BDTR_MOE)b|=1U;
    if(TIM1->CCER)b|=2U;
    if(TIM1->CR1&TIM_CR1_CEN)b|=4U;
    if(SWS_Relay_GPIO_Port->ODR&SWS_Relay_Pin)b|=8U;
    if(SWL_Relay_GPIO_Port->ODR&SWL_Relay_Pin)b|=16U;
    if((GPIOA->ODR&GPIO_PIN_9)||(GPIOF->ODR&GPIO_PIN_7))b|=32U;
    return b;
}
static G03Sample sample(uint32_t now)
{
    G03Sample s={1U,1U,0U,{3600,3600,3600},0,25000};
    s.at_ms=now;
    if(control.state==G03_CHARGE)s.current_ma=100;
    if(control.state==G03_DISCHARGE)s.current_ma=-100;
    switch(scenario){
    case 1:s.valid=0U;break;
    case 2:s.at_ms=now-fixture.stale_ms-1U;break;
    case 3:s.current_ma=control.direction==2U?-600:600;break;
    case 4:s.cell_mv[1]=2900;break;
    case 5:s.cell_mv[2]=4300;break;
    case 6:s.temp_mc=46000;break;
    case 8:s.current_ma=control.direction==2U?100:-100;break;
    case 9:s.current_ma=control.direction==2U?-100:100;break;
    case 10:s.calibrated=0U;break;
    default:break;
    }
    return s;
}
void G03_PortInit(void)
{
    uint32_t k=lock();
    G03_Init(&control);
    /* Explicit fixture selection is required on each cold boot. */
    G02_EmergencyOff();unlock(k);
}
int G03_SyntheticBusy(void)
{ return control.initialized && control.state!=G03_STOPPED; }
int G03_BlocksG02(void)
{ return G03_SyntheticBusy() || G03_ADC_BlocksOthers(); }
void G03_TickIRQ(void)
{
    uint32_t now,delta,bits;G03Sample s;
    if(!G03_Active(&control))return;
    now=HAL_GetTick();delta=now-last_tick_ms;
    if(tick_count && delta>max_tick_gap)max_tick_gap=delta;
    last_tick_ms=now;++tick_count;
    bits=output_bits();s=sample(now);
    G03_Tick(&control,now,&s,scenario==7U || bits!=0U);
    if(g02_control.faults)G03_Fault(&control,G03_F_EXTERNAL,now);
    /* Register-only off path runs even when the foreground task stalls. */
    G02_EmergencyOff();
}
uint32_t G03_Command(uint32_t op,uint32_t arg)
{
    uint32_t k,r=G03_BAD_ARGUMENT,now;G03Sample s;
    /* Foreground cleanup must occur before the short critical section. */
    if(op==13U && !arg){G03_ADC_Stop();g02_command=G02_CMD_STOP;G02_Task();}
    k=lock();now=HAL_GetTick();
    if(op==10U && !arg)r=G03_OK;
    else if(op==18U)r=G03_DISALLOWED; /* Power requests always rejected. */
    else if(op==13U && !arg){G03_Stop(&control,now,G03_REASON_STOP);G02_EmergencyOff();r=G03_OK;}
    else if(G03_ADC_BlocksOthers()||G02_OwnsADC(&g02_control)||g02_control.faults)r=G03_BUSY;
    else if(op==17U && arg<=1U){
        if(control.state!=G03_STOPPED)r=control.faults?G03_FAULTED:G03_BUSY;
        else if(arg==0U){control.configured=0U;fixture_selected=0U;r=G03_OK;}
        else{r=G03_Configure(&control,&fixture);if(r==G03_OK)fixture_selected=1U;}
    }else if(op==11U||op==12U){
        s=sample(now);r=G03_Start(&control,op==11U?1U:2U,arg,now,&s);
        if(r==G03_OK){tick_count=0U;max_tick_gap=0U;last_tick_ms=now;G02_EmergencyOff();}
    }else if(op==14U && !arg)r=G03_Clear(&control);
    else if(op==15U && !arg)r=G03_Heartbeat(&control,now);
    else if(op==16U && arg<=10U){scenario=arg;r=G03_OK;}
    else if(op==19U)r=G03_Compare(&control,arg);
    unlock(k);return r;
}
int G03_Report(char *out,unsigned size,uint32_t id,uint32_t result)
{
    G03Control c;uint32_t k=lock(),bits=output_bits(),ticks=tick_count,gap=max_tick_gap,sc=scenario,fs=fixture_selected;
    c=control;unlock(k);
    return snprintf(out,size,"#G03,g03-adc-r2,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,1,0",
        (unsigned long)id,(unsigned long)result,(unsigned long)c.state,(unsigned long)c.direction,
        (unsigned long)c.faults,(unsigned long)c.reason,(unsigned long)c.configured,(unsigned long)fs,
        (unsigned long)c.ccr,(unsigned long)c.shadow_relays,(unsigned long)c.shadow_pwm,(unsigned long)bits,
        (unsigned long)c.start_ms,(unsigned long)c.stop_ms,(unsigned long)c.heartbeat_ms,
        (unsigned long)c.transitions,(unsigned long)c.starts,(unsigned long)ticks,(unsigned long)gap,(unsigned long)sc);
}
