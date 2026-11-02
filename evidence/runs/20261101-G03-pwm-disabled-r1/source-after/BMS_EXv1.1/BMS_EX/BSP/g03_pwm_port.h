#ifndef G03_PWM_PORT_H
#define G03_PWM_PORT_H
#include <stdint.h>
#if defined(G03_PWM_DISABLED_BUILD) && G03_PWM_DISABLED_BUILD
void G03_PWM_Init(void);
void G03_PWM_Task(void);
int G03_PWM_Busy(void);
int G03_PWM_Blocks(void);
int G03_PWM_Owns(void);
int G03_PWM_ReportReady(void);
int G03_PWM_TimerIRQ(void);
int G03_PWM_ADCIRQ(void);
void G03_PWM_Stop(void);
void G03_PWM_ProtocolFault(void);
void G03_PWM_CPUFault(void);
uint32_t G03_PWM_Command(uint32_t op,uint32_t arg,uint32_t request_id);
int G03_PWM_Report(char *out,unsigned size,uint32_t id,uint32_t result,uint32_t op,uint32_t arg);
#else
static inline void G03_PWM_Init(void){}
static inline void G03_PWM_Task(void){}
static inline int G03_PWM_Busy(void){return 0;}
static inline int G03_PWM_Blocks(void){return 0;}
static inline int G03_PWM_Owns(void){return 0;}
static inline int G03_PWM_ReportReady(void){return 1;}
static inline int G03_PWM_TimerIRQ(void){return 0;}
static inline int G03_PWM_ADCIRQ(void){return 0;}
static inline void G03_PWM_Stop(void){}
static inline void G03_PWM_ProtocolFault(void){}
static inline void G03_PWM_CPUFault(void){}
static inline uint32_t G03_PWM_Command(uint32_t o,uint32_t a,uint32_t i){(void)o;(void)a;(void)i;return 1U;}
static inline int G03_PWM_Report(char *b,unsigned s,uint32_t i,uint32_t r,uint32_t o,uint32_t a)
{(void)b;(void)s;(void)i;(void)r;(void)o;(void)a;return -1;}
#endif
#endif
