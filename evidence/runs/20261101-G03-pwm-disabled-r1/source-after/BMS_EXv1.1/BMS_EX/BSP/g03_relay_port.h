#ifndef G03_RELAY_PORT_H
#define G03_RELAY_PORT_H
#include <stdint.h>
void G03_RelayInit(void);
int G03_RelayBusy(void);
void G03_RelayTask(void);
void G03_RelayTickIRQ(void);
void G03_RelayStop(void);
void G03_RelayCPUFault(void);
uint32_t G03_RelayCommand(uint32_t op,uint32_t arg);
int G03_RelayReport(char *out,unsigned size,uint32_t id,uint32_t result,uint32_t op,uint32_t arg);
#endif
