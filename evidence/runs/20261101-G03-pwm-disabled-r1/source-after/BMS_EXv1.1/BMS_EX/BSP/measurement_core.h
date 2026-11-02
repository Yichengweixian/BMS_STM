#ifndef MEASUREMENT_CORE_H
#define MEASUREMENT_CORE_H
#include <stdint.h>
#include <stddef.h>
#define MEAS_PERIOD_MS 500U
#define MEAS_MAX_AGE_MS 1000U
#define MEAS_CHANNELS 9U
#define MEAS_SCHEMA "g01-v1"
#define MEAS_CAL_ID "uncalibrated-v1"
/* These are quality flags, never physical safety limits. */
enum {
    MEAS_IO=1U, MEAS_PEC=2U, MEAS_TIMEOUT=4U, MEAS_RANGE=8U,
    MEAS_STALE=16U, MEAS_CONFIG=32U, MEAS_ADC=64U,
    MEAS_UNCALIBRATED=128U, MEAS_NO_RAW=256U
};
#define MEAS_INVALID_MASK (MEAS_IO|MEAS_PEC|MEAS_TIMEOUT|MEAS_RANGE|MEAS_STALE|MEAS_CONFIG|MEAS_ADC|MEAS_NO_RAW)
typedef enum {
    MEAS_CELL1, MEAS_CELL7, MEAS_CELL13, MEAS_AFE_I,
    MEAS_TEMP1, MEAS_TEMP2, MEAS_TEMP3, MEAS_MCU_I, MEAS_REF2
} MeasChannel;
typedef struct {
    uint32_t start_ms, end_ms, status;
    uint16_t raw;
    uint8_t has_raw, has_frame, frame[8];
} MeasSample;
typedef struct {
    uint32_t status, age_ms;
    uint8_t raw_valid, estimate_present;
    float sensor_v, estimate;
} MeasValue;
extern const char * const meas_channel_names[MEAS_CHANNELS];
uint16_t Meas_Pec15(const uint8_t *bytes, size_t length);
void Meas_Decode(MeasSample *sample, const uint8_t frame[8], unsigned index);
MeasValue Meas_Evaluate(const MeasSample *sample, MeasChannel channel, uint32_t now);
/* Physical value/reference stay empty until independently calibrated. */
int Meas_Format(char *dest, size_t size, uint32_t seq, MeasChannel channel,
                const MeasSample *sample, uint32_t now);
#endif
