#ifndef G03_PORT_H
#define G03_PORT_H
#include "g03_control.h"
void G03_PortInit(void);
void G03_TickIRQ(void);
int G03_BlocksG02(void);
uint32_t G03_Command(uint32_t op,uint32_t arg);
/* Formats a body without CRC. All fields describe a disabled exercise. */
int G03_Report(char *out,unsigned size,uint32_t id,uint32_t result);
#endif
