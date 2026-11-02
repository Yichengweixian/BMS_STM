#ifndef G03_CONTROL_H
#define G03_CONTROL_H
#include <stdint.h>
/* Shadow outputs only. No enable/output callbacks exist in this module. */
enum { G03_STOPPED, G03_BREAK_WAIT, G03_RELAY_WAIT, G03_CHARGE,
       G03_DISCHARGE, G03_DECAY_WAIT, G03_FAULT };
enum { G03_OK, G03_BAD_ARGUMENT, G03_NOT_READY, G03_BUSY, G03_DISALLOWED, G03_FAULTED };
enum { G03_F_CONFIG=1U, G03_F_SENSOR=2U, G03_F_STALE=4U, G03_F_CURRENT=8U,
       G03_F_UV=16U, G03_F_OV=32U, G03_F_TEMP=64U, G03_F_LINK=128U,
       G03_F_INTERLOCK=256U, G03_F_DECAY=512U, G03_F_REVERSE=1024U, G03_F_EXTERNAL=2048U };
enum { G03_REASON_NONE, G03_REASON_DURATION, G03_REASON_STOP, G03_REASON_FAULT };
typedef struct {
    uint32_t known, break_ms, relay_ms, decay_ms, decay_timeout_ms;
    uint32_t link_ms, stale_ms, max_run_ms, ccr_min, ccr_max;
    int32_t cell_min_mv, cell_max_mv, charge_max_ma, discharge_max_ma;
    int32_t temp_min_mc, temp_max_mc, relay_release_ma;
} G03Config;
typedef struct {
    uint32_t valid, calibrated, at_ms;
    int32_t cell_mv[3], current_ma, temp_mc;
} G03Sample;
typedef struct {
    G03Config cfg;
    uint32_t initialized, configured, state, direction, faults, reason;
    uint32_t entered_ms, start_ms, stop_ms, heartbeat_ms, duration_ms, ccr;
    uint32_t shadow_relays, shadow_pwm, transitions, starts;
} G03Control;
void G03_Init(G03Control *c);
uint32_t G03_Configure(G03Control *c, const G03Config *cfg);
uint32_t G03_Start(G03Control *c, uint32_t direction, uint32_t duration_ms, uint32_t now, const G03Sample *s);
uint32_t G03_Compare(G03Control *c, uint32_t ccr);
void G03_Stop(G03Control *c, uint32_t now, uint32_t reason);
void G03_Fault(G03Control *c, uint32_t bits, uint32_t now);
uint32_t G03_Clear(G03Control *c);
uint32_t G03_Heartbeat(G03Control *c, uint32_t now);
void G03_Tick(G03Control *c, uint32_t now, const G03Sample *s, uint32_t interlock_bad);
int G03_Active(const G03Control *c);
#endif
