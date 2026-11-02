#ifndef PWM_ONESHOT_H
#define PWM_ONESHOT_H

#include <stdint.h>

/* OFFLINE CANDIDATE, not teacher source and not a board power firmware.
 * Object storage MUST be zero-initialized before the one permitted Init.
 * Caller serializes ALL calls and callbacks in the same short critical section.
 * No callback may reenter the core. No API mutates a running CCR/profile. */
enum {
    PWM_FACT_FEEDBACK_PATH = 1U << 0,
    PWM_FACT_CURRENT_BOUND = 1U << 1, /* direction/scale/observable protection window */
    PWM_FACT_DRIVER_MAPPING = 1U << 2,
    PWM_FACT_EFFECTIVE_DEADTIME = 1U << 3,
    PWM_FACT_SUPPLY_LIMITS = 1U << 4,
    PWM_FACT_STOP_PATH = 1U << 5,
    PWM_FACT_CONDITIONS_FROZEN = 1U << 6,
    PWM_FACT_ALL = (1U << 7) - 1U
};
enum {
    PWM_F_STOP = 1U << 0, PWM_F_PROTOCOL = 1U << 1,
    PWM_F_ADC_INVALID = 1U << 2, PWM_F_ADC_STALE = 1U << 3,
    PWM_F_OVERRUN = 1U << 4, PWM_F_OVERCURRENT = 1U << 5,
    PWM_F_HEARTBEAT = 1U << 6, PWM_F_ISR_LATE = 1U << 7,
    PWM_F_ADAPTER = 1U << 8, PWM_F_REINIT = 1U << 9,
    PWM_F_EXTERNAL = 1U << 10
};
typedef enum { PWM_IDLE, PWM_PREPARING, PWM_RUNNING, PWM_DONE, PWM_FAULT } PWMState;
typedef enum {
    PWM_OK, PWM_BAD_ARGUMENT, PWM_NOT_READY, PWM_BUSY,
    PWM_ALREADY_USED, PWM_FAULTED, PWM_ADAPTER_ERROR
} PWMResult;

typedef struct {
    uint32_t enable_requested; /* exactly 1; no default power authorization */
    uint32_t verified_facts;   /* evidence-derived, not an override checklist */
    uint32_t profile_id;       /* nonzero identity, mapped to external evidence */
    uint32_t arr, ccr, ccr_min, ccr_max, deadtime_code;
    uint32_t run_ms, max_run_ms;
    uint32_t adc_max_age_ms, heartbeat_max_age_ms, isr_max_gap_ms;
    int32_t charge_max_ma, discharge_max_ma, start_current_max_ma;
} PWMProfile;

typedef struct {
    uint32_t at_ms; /* actual acquisition timestamp, never receipt timestamp */
    int32_t current_ma;
    uint32_t valid;
    uint32_t overrun;
} PWMSample;

typedef struct {
    /* One shared monotonic uint32 millisecond clock, wrapping naturally.
     * It must keep advancing while foreground/low-priority IRQs stall. */
    uint32_t (*now_ms)(void *ctx);
    /* Register-only, idempotent, bounded, mandatory. Disable BOTH PWM outputs
     * and prevent automatic reassertion. Valid from init/fault/ISR contexts.
     * A void return is deliberate: software cannot prove electrical shutdown. */
    void (*emergency_off)(void *ctx);
    /* Must leave outputs OFF. Program and read back frozen CCR/DTG, reserve
     * ADC, arm protections AND independent periodic deadline IRQ before return.
     * Both return 1 on success, 0 on any mismatch/failure. No waits/printf. */
    int (*prepare)(void *ctx, const PWMProfile *frozen);
    int (*enable_pair)(void *ctx);
    /* Optional foreground-only cleanup/report hook, after emergency_off.
     * No output enable or rearm allowed; returns 1 on success. */
    int (*after_off)(void *ctx, PWMState state, uint32_t faults);
} PWMOps;

typedef struct {
    uint32_t initialized, used, faults, pending_cleanup;
    PWMState state;
    PWMProfile frozen;
    PWMOps ops;
    void *ctx;
    uint32_t start_ms, stop_ms, last_isr_ms, last_adc_ms, last_heartbeat_ms;
    int32_t last_current_ma;
} PWMOneShot;

PWMResult PWM_OneShot_Init(PWMOneShot *c, const PWMOps *ops, void *ctx);
PWMResult PWM_OneShot_Start(PWMOneShot *c, const PWMProfile *p, const PWMSample *initial);
void PWM_OneShot_PeriodicISR(PWMOneShot *c);
void PWM_OneShot_ADCISR(PWMOneShot *c, const PWMSample *sample);
void PWM_OneShot_Heartbeat(PWMOneShot *c);
void PWM_OneShot_Stop(PWMOneShot *c);
void PWM_OneShot_ProtocolError(PWMOneShot *c);
void PWM_OneShot_Trip(PWMOneShot *c, uint32_t fault);
PWMResult PWM_OneShot_ClearFault(PWMOneShot *c);
PWMResult PWM_OneShot_Service(PWMOneShot *c);

#endif
