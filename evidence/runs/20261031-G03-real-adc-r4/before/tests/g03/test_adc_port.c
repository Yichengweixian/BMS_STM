#define main baseline_main
#include "../g02/test_port.c"
#undef main
#include "g03_adc_port.h"
#include "g03_adc_core.h"
#include "g03_port.h"
ADC_Common_TypeDef test_adc_common;
static ADC_AnalogWDGConfTypeDef watchdog;
static uint32_t diagnostic_raw=1008U;
static int fail_cal,fail_wdg,fail_poll,unstable;
static unsigned capture_index;
HAL_StatusTypeDef HAL_ADC_Start(ADC_HandleTypeDef *h)
{assert(h==&hadc1&&!test_primask);ADC1->DR=diagnostic_raw+((unstable&&++capture_index%2)?100U:0U);return HAL_OK;}
HAL_StatusTypeDef HAL_ADC_PollForConversion(ADC_HandleTypeDef *h,uint32_t timeout)
{(void)h;(void)timeout;return fail_poll?HAL_TIMEOUT:HAL_OK;}
uint32_t HAL_ADC_GetError(ADC_HandleTypeDef *h){(void)h;return 0;}
HAL_StatusTypeDef HAL_ADCEx_Calibration_Start(ADC_HandleTypeDef *h,uint32_t diff)
{(void)h;(void)diff;diagnostic_raw=2048U;ADC1->CALFACT=17;return fail_cal?HAL_ERROR:HAL_OK;}
HAL_StatusTypeDef HAL_ADC_AnalogWDGConfig(ADC_HandleTypeDef *h,ADC_AnalogWDGConfTypeDef *w)
{(void)h;watchdog=*w;return fail_wdg?HAL_ERROR:HAL_OK;}
void HAL_Delay(uint32_t ms){tick+=ms;}
static unsigned status_fault(void)
{char r[1024];unsigned id,result,state,fault;long ua;
 G03_ADC_Report(r,sizeof r,1,0,20,0);
 assert(sscanf(r,"#G3A,g03-adc-r3,%u,%u,%ld,%u,%u",&id,&result,&ua,&state,&fault)==5);
 assert_off();return fault;}
static void conversion(uint32_t raw)
{
 uint32_t flags=ADC_FLAG_EOC|ADC_FLAG_EOS;
 if((ADC1->IER&ADC_IT_AWD1)&&(raw<watchdog.LowThreshold||raw>watchdog.HighThreshold))flags|=ADC_FLAG_AWD1;
 ADC1->CR=0;ADC1->ISR=flags;ADC1->DR=raw;
 assert(G03_ADC_IRQHandler());assert_off();
}
static void ready(void)
{assert(G03_ADC_Command(27,0)==0);assert(G03_ADC_Command(21,5)==0);assert(G03_ADC_Command(22,0)==0);}
#ifndef ADC_PORT_MAIN
#define ADC_PORT_MAIN main
#endif
int ADC_PORT_MAIN(void)
{
 unsigned i;char r[1024];assert(baseline_main()==0);G03_PortInit();
 assert(G03_ADC_Command(24,1000)==G03_NOT_READY);
 assert(G03_ADC_Command(21,0)==0);assert(G03_ADC_Command(22,0)==G03_NOT_READY);
 assert(G03_ADC_Command(21,1)==0);assert(G03_ADC_Command(21,2)==0);assert(G03_ADC_Command(21,5)==0);
 assert(G03_ADC_Command(21,3)==0);assert(G03_ADC_Command(22,0)==G03_NOT_READY);
 assert(G03_ADC_Command(21,4)==0);assert(G03_ADC_Command(22,0)==0);
 unstable=1;assert(G03_ADC_Command(21,5)==0);assert(G03_ADC_Command(22,0)==G03_NOT_READY);
 unstable=0;ready();unstable=1;assert(G03_ADC_Command(24,1000)==G03_FAULTED);
 assert(!G03_ADC_Owns());assert(status_fault()&G3A_ADC);unstable=0;ready();
 diagnostic_raw=2248U;assert(G03_ADC_Command(24,1000)==G03_FAULTED);
 assert(!G03_ADC_Owns());assert(status_fault()&G3A_ADC);ready();
 fail_poll=1;assert(G03_ADC_Command(24,1000)==G03_FAULTED);
 assert(!G03_ADC_Owns());fail_poll=0;ready();
 assert(G03_ADC_Command(22,0)==0);assert(G03_ADC_Command(23,2000)==G03_BAD_ARGUMENT);
 assert(G03_ADC_Command(24,1000)==0);assert(!G02_MeasurementAllowed());
 assert(G03_Command(11,100)==G03_BUSY);
 g02_command=G02_CMD_SAMPLE;G02_Task();assert(g02_command_result==G02_BUSY);
 assert(G03_ADC_Command(21,0)==G03_BUSY);
 for(i=0;i<1000;i++){
   conversion(2048);if(i%200==0)assert(G03_ADC_Command(25,0)==0);
   ++tick;G03_ADC_TickIRQ();assert_off();
 }
 G03_ADC_Task();assert(G02_MeasurementAllowed());assert(!status_fault());
 assert(G03_ADC_Command(28,0)==0);assert(G03_ADC_Command(28,10000)==G03_BAD_ARGUMENT);
 G03_ADC_Report(r,sizeof r,1,0,21,0);assert(strlen(r)<sizeof r);puts(r);
 for(i=1;i<=2;i++){
   ready();assert(G03_ADC_Command(29,i)==0);conversion(2048);
   assert(status_fault()&G3A_AWD);G03_ADC_Task();assert(G03_ADC_Command(24,100)==G03_FAULTED);
   G03_ADC_Report(r,sizeof r,i,0,20,0);puts(r);
 }
 ready();assert(G03_ADC_Command(24,1000)==0);
 tick+=6;G03_ADC_TickIRQ();assert(status_fault()&G3A_STALE);G03_ADC_Task();
 ready();assert(G03_ADC_Command(24,2000)==0);
 for(i=0;i<800;i++){conversion(2048);++tick;G03_ADC_TickIRQ();}
 assert(status_fault()&G3A_LINK);G03_ADC_Task();
 ready();assert(G03_ADC_Command(24,1000)==0);assert(G03_Command(13,0)==0);assert(!G03_ADC_Owns());
 fail_cal=1;assert(G03_ADC_Command(21,5)==G03_FAULTED);assert(status_fault()&G3A_ADC);fail_cal=0;
 ready();assert(G03_ADC_Command(24,1000)==0);ADC1->ISR=ADC_FLAG_OVR;assert(G03_ADC_IRQHandler());
 fail_cleanup=1;G03_ADC_Task();assert(G03_ADC_Owns());assert(G03_ADC_Command(27,0)==G03_BUSY);
 fail_cleanup=0;G03_ADC_Task();assert(G03_ADC_Command(27,0)==0);assert_off();
 puts("PASS: production ADC adapter, mutual exclusion, watchdog paths, SysTick deadline, cleanup failure, all outputs off");return 0;
}
