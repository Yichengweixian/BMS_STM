/* Existing G02/synthetic G03 regression binaries exclude the real ADC adapter.
 * Real adapter is separately compiled/exercised by test_adc_port.c. */
#include "g03_adc_port.h"
int G03_ADC_BlocksOthers(void){return 0;}
int G03_ADC_Owns(void){return 0;}
int G03_ADC_IRQHandler(void){return 0;}
void G03_ADC_Stop(void){}
uint32_t G03_ADC_Command(uint32_t op,uint32_t arg){(void)op;(void)arg;return 2;}
int G03_ADC_Report(char *out,unsigned size,uint32_t id,uint32_t r,uint32_t op,uint32_t a)
{(void)out;(void)size;(void)id;(void)r;(void)op;(void)a;return -1;}
