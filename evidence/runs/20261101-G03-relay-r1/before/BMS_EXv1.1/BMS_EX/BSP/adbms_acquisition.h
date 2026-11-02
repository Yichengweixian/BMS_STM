#ifndef ADBMS_ACQUISITION_H
#define ADBMS_ACQUISITION_H
#include "measurement_core.h"
/* Single ADBMS1818; bounded transfers; no balancing or S-control commands. */
void Afe_Acquire(MeasSample samples[MEAS_CHANNELS]);
#endif
