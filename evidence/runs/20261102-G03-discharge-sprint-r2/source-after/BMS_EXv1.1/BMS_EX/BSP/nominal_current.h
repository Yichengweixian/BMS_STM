#ifndef NOMINAL_CURRENT_H
#define NOMINAL_CURRENT_H
/* Recovered from independent BMS_Appli.hex dd44fae1...6be7f.
 * Software model ONLY: not board calibration, polarity or a power limit. */
#define CURRENT_MODEL_ID "hex-dd44fae1-nominal-v1"
#define CURRENT_HEX_GAIN (1.3266666730244954)
#define CURRENT_MCU_LSB (0.0004395604191813618f)
#define CURRENT_AFE_LSB (0.0001f)
static inline float Current_McuNominal(unsigned raw, float zero_v)
{ return (float)(((float)raw*CURRENT_MCU_LSB-zero_v)*CURRENT_HEX_GAIN); }
static inline float Current_AfeNominal(unsigned raw, float zero_v)
{ return (float)(((float)raw*CURRENT_AFE_LSB-zero_v)*CURRENT_HEX_GAIN); }
#endif
