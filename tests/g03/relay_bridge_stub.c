#include "g03_relay_port.h"
void G03_RelayInit(void){}
int G03_RelayBusy(void){return 0;}
void G03_RelayTask(void){}
void G03_RelayTickIRQ(void){}
void G03_RelayStop(void){}
void G03_RelayCPUFault(void){}
uint32_t G03_RelayCommand(uint32_t op,uint32_t arg){(void)op;(void)arg;return 4U;}
int G03_RelayReport(char *o,unsigned s,uint32_t i,uint32_t r,uint32_t p,uint32_t a)
{(void)o;(void)s;(void)i;(void)r;(void)p;(void)a;return -1;}
