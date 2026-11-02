#ifndef ADBMS_ACQUISITION_H
#define ADBMS_ACQUISITION_H
#include "measurement_core.h"
/* Single ADBMS1818; bounded transfers; no balancing or S-control commands. */
void Afe_Acquire(MeasSample samples[MEAS_CHANNELS]);
uint32_t Afe_PulsePrepare(void);
/* samples: cells 1/7/13 then GPIO1. No reconfiguration or temperature reads. */
void Afe_PulseAcquire(MeasSample samples[4]);
#endif
