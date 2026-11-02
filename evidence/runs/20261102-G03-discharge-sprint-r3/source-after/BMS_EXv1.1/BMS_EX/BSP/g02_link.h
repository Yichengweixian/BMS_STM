#ifndef G02_LINK_H
#define G02_LINK_H
#include <stdint.h>
void G02_LinkRx(const uint8_t *data, uint16_t size);
void G02_LinkRxError(void);
void G02_LinkTask(void);
#endif
