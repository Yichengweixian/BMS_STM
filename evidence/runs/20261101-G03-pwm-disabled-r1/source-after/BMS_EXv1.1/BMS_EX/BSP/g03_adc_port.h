#ifndef G03_ADC_PORT_H
#define G03_ADC_PORT_H
#include <stdint.h>
int G03_ADC_BlocksOthers(void);
int G03_ADC_Owns(void);
void G03_ADC_TickIRQ(void);
int G03_ADC_IRQHandler(void);
void G03_ADC_Task(void);
void G03_ADC_Stop(void);
uint32_t G03_ADC_Command(uint32_t op,uint32_t arg);
int G03_ADC_Report(char *out,unsigned size,uint32_t id,uint32_t result,uint32_t op,uint32_t arg);
uint32_t G03_ADC_Profile(void);
uint32_t G03_ADC_Calibrated(void);
#endif
