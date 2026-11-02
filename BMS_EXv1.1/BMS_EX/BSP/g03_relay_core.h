#ifndef G03_RELAY_CORE_H
#define G03_RELAY_CORE_H
#include <stdint.h>
/* Engineering observation rules, not calibrated physical current limits. */
#define G3R_PERIOD_MS 20U
#define G3R_STALE_MS 40U
#define G3R_BASE_SAMPLES 50U
#define G3R_PULSE_MS 99U /* reserve 1 ms for interrupt entry; acceptance <=100 ms */
#define G3R_POST_MS 1000U
#define G3R_CAPACITY 256U
enum { G3R_IDLE, G3R_PREPARE, G3R_BASELINE, G3R_PULSE, G3R_POST, G3R_DONE, G3R_FAULT };
enum { G3R_DATA=1U, G3R_STALE=2U, G3R_CELL=4U, G3R_BASE=8U,
       G3R_BUFFER=16U, G3R_INTERLOCK=32U, G3R_TIMING=64U, G3R_CPU=128U };
enum { G3R_END_NONE, G3R_END_DEADLINE, G3R_END_STOP, G3R_END_FAULT };
typedef struct {
    uint32_t state, faults, reason, live, command_on, samples, base_count;
    uint32_t base_min, base_max, base_sum, center, tolerance;
    uint32_t last_sample, session_start, on_ms, off_ms, post_start, recover_count;
    uint32_t cell_low, cell_high;
} G3RCore;
void G3R_Init(G3RCore *c);
int G3R_Begin(G3RCore *c,uint32_t live,uint32_t now,uint32_t low,uint32_t high);
void G3R_Ready(G3RCore *c,uint32_t now);
void G3R_Trip(G3RCore *c,uint32_t fault,uint32_t now);
void G3R_Stop(G3RCore *c,uint32_t now);
void G3R_Tick(G3RCore *c,uint32_t now);
/* Complete required-channel snapshot; timestamp is oldest conversion START. */
void G3R_Sample(G3RCore *c,uint32_t now,uint32_t oldest,uint32_t valid,
                const uint16_t raw[4]);
int G3R_Clear(G3RCore *c);
int G3R_Active(const G3RCore *c);
#endif
