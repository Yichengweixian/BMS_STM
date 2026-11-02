#include "pwm_oneshot.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Every profile in this file is a SYNTHETIC software fixture, never a proposed
 * board setting. The fake adapter cannot access registers, USB or serial. */
typedef struct {
    PWMOneShot core;
    uint32_t now, prepare_delay, enable_delay, programmed_ccr;
    unsigned off_count, prepare_count, enable_count, cleanup_count;
    int output_on, prepare_ok, enable_ok, cleanup_ok;
    PWMState state_seen_at_off;
    char trace[128];
    unsigned trace_len;
} Fixture;

static void trace(Fixture *f, char e)
{ assert(f->trace_len < sizeof f->trace - 1U); f->trace[f->trace_len++] = e; f->trace[f->trace_len] = '\0'; }
static uint32_t clock_us(void *ctx) { return ((Fixture *)ctx)->now; }
static void emergency_off(void *ctx)
{
    Fixture *f = ctx;
    f->state_seen_at_off = f->core.state;
    f->output_on = 0; ++f->off_count; trace(f, 'O');
}
static int prepare(void *ctx, const PWMProfile *p)
{
    Fixture *f = ctx;
    assert(!f->output_on);
    ++f->prepare_count; trace(f, 'P'); f->programmed_ccr = p->ccr;
    f->now += f->prepare_delay;
    return f->prepare_ok;
}
static int enable(void *ctx)
{
    Fixture *f = ctx;
    ++f->enable_count; trace(f, 'E');
    f->output_on = 1; /* Simulate partial hardware enable even on failure. */
    f->now += f->enable_delay;
    return f->enable_ok;
}
static int after_off(void *ctx, PWMState state, uint32_t faults)
{
    Fixture *f = ctx;
    assert(!f->output_on);
    assert(state == PWM_DONE || state == PWM_FAULT);
    assert(state != PWM_FAULT || faults != 0U);
    ++f->cleanup_count; trace(f, 'C');
    return f->cleanup_ok;
}
static const PWMOps ops = { clock_us, emergency_off, prepare, enable, after_off };

static PWMProfile profile(void)
{
    PWMProfile p = {0};
    p.enable_requested = 1U; p.verified_facts = PWM_FACT_ALL; p.profile_id = 123U;
    p.arr = 1000U; p.ccr = 500U; p.ccr_min = 100U; p.ccr_max = 900U; p.deadtime_code = 7U;
    p.deadtime_source = PWM_DEADTIME_TIMER;
    p.run_us = 10U; p.max_run_us = 10U;
    p.adc_max_age_us = 4U; p.heartbeat_max_age_us = 20U; p.isr_max_gap_us = 2U;
    p.charge_max_ma = 100; p.discharge_max_ma = 100; p.start_current_max_ma = 10;
    return p;
}
static PWMSample sample(Fixture *f, int32_t ma)
{ PWMSample s = {f->now, ma, 1U, 0U}; return s; }
static void init(Fixture *f, uint32_t now)
{
    memset(f, 0, sizeof *f); f->now = now;
    f->prepare_ok = f->enable_ok = f->cleanup_ok = 1;
    assert(PWM_OneShot_Init(&f->core, &ops, f) == PWM_OK);
    assert(!f->output_on && !f->core.used && f->core.state == PWM_IDLE);
}
static PWMResult start(Fixture *f, const PWMProfile *p)
{ PWMSample s = sample(f, 0); return PWM_OneShot_Start(&f->core, p, &s); }
static void healthy_tick(Fixture *f)
{
    PWMSample s;
    ++f->now; s = sample(f, 0);
    PWM_OneShot_ADCISR(&f->core, &s);
    PWM_OneShot_PeriodicISR(&f->core);
}
static void assert_fault_off(Fixture *f, uint32_t reason)
{
    assert(!f->output_on && f->core.state == PWM_FAULT);
    assert((f->core.faults & reason) == reason);
}

static void test_default_and_missing_facts(void)
{
    Fixture f; PWMProfile p; unsigned i;
    init(&f, 10U); memset(&p, 0, sizeof p);
    assert(start(&f, &p) == PWM_NOT_READY);
    for (i = 0U; i < 7U; ++i) {
        p = profile(); p.verified_facts &= ~(1U << i);
        assert(start(&f, &p) == PWM_NOT_READY);
    }
    p = profile(); p.enable_requested = 0U;
    assert(start(&f, &p) == PWM_NOT_READY);
    p = profile(); p.profile_id = 0U;
    assert(start(&f, &p) == PWM_NOT_READY);
    assert(!f.core.used && !f.prepare_count && !f.enable_count && !f.output_on);
}

static void test_policy_boundaries(void)
{
    Fixture f; PWMProfile p; PWMSample s;
    init(&f, 10U); s = sample(&f, 0);
#define BAD(field, value) do { p = profile(); p.field = (value); \
    assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY); } while (0)
    BAD(arr, 0U); BAD(arr, 65536U); BAD(ccr, 0U); BAD(ccr, 1000U);
    BAD(ccr, 99U); BAD(ccr, 901U); BAD(ccr_min, 901U); BAD(ccr_max, 1000U);
    BAD(deadtime_code, 0U); BAD(deadtime_code, 256U);
    BAD(deadtime_source, PWM_DEADTIME_UNSPECIFIED);
    BAD(deadtime_source, (PWMDeadtimeSource)99);
    BAD(run_us, 0U); BAD(run_us, 11U); BAD(max_run_us, UINT32_C(0x80000000));
    BAD(adc_max_age_us, 0U); BAD(heartbeat_max_age_us, 0U);
    BAD(isr_max_gap_us, 0U); BAD(isr_max_gap_us, 11U);
    BAD(adc_max_age_us, 1U); BAD(heartbeat_max_age_us, 1U);
    BAD(charge_max_ma, 0); BAD(discharge_max_ma, 0); BAD(start_current_max_ma, -1);
    BAD(start_current_max_ma, 100);
#undef BAD
    assert(!f.core.used && !f.prepare_count);

    /* Source selection is explicit. Driver-supplied deadtime can be valid with
     * timer DTG=0; evidence of effective deadtime is still mandatory. */
    p = profile(); p.deadtime_source = PWM_DEADTIME_DRIVER; p.deadtime_code = 0U;
    p.verified_facts &= ~((uint32_t)PWM_FACT_EFFECTIVE_DEADTIME);
    assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY);
    assert(!f.core.used && !f.prepare_count);
    p.verified_facts |= PWM_FACT_EFFECTIVE_DEADTIME;
    assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_OK);
    assert(f.core.frozen.deadtime_source == PWM_DEADTIME_DRIVER && f.core.frozen.deadtime_code == 0U);
    PWM_OneShot_Stop(&f.core); assert_fault_off(&f, PWM_F_STOP);

    init(&f, 10U); s = sample(&f, 0);
    p = profile(); p.deadtime_source = PWM_DEADTIME_BOTH; p.deadtime_code = 0U;
    assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY);
    p.deadtime_code = 7U;
    assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_OK);
    PWM_OneShot_Stop(&f.core); assert_fault_off(&f, PWM_F_STOP);
}

static void test_initial_sample_rejected(void)
{
    Fixture f; PWMProfile p = profile(); PWMSample s;
    init(&f, 10U);
    s = sample(&f, 11); assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY);
    s = sample(&f, -11); assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY);
    s = sample(&f, 0); s.valid = 0U; assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY);
    s = sample(&f, 0); s.overrun = 1U; assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY);
    s = sample(&f, 0); s.at_us -= p.adc_max_age_us;
    assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY);
    s = sample(&f, 0); ++s.at_us;
    assert(PWM_OneShot_Start(&f.core, &p, &s) == PWM_NOT_READY);
    assert(PWM_OneShot_Start(&f.core, &p, NULL) == PWM_NOT_READY);
    assert(!f.core.used && !f.enable_count);
}

static void test_deadline_without_foreground_and_frozen_ccr(void)
{
    Fixture f; PWMProfile p = profile(); unsigned i;
    init(&f, 10U); assert(start(&f, &p) == PWM_OK);
    assert(!strcmp(f.trace, "OOPE"));
    p.ccr = 800U; p.run_us = 1U; /* Caller mutation must not alter accepted snapshot. */
    assert(start(&f, &p) == PWM_ALREADY_USED);
    for (i = 0U; i < 9U; ++i) { healthy_tick(&f); assert(f.output_on); }
    assert(f.programmed_ccr == 500U && f.core.frozen.ccr == 500U);
    healthy_tick(&f);
    assert(!f.output_on && f.core.state == PWM_DONE && !f.core.faults);
    assert(f.core.stop_us - f.core.start_us == 10U);
    assert(f.cleanup_count == 0U && f.core.pending_cleanup);
    assert(f.state_seen_at_off == PWM_RUNNING); /* off precedes state bookkeeping */
    assert(PWM_OneShot_Service(&f.core) == PWM_OK);
    assert(!strcmp(f.trace, "OOPEOC"));
    assert(PWM_OneShot_Service(&f.core) == PWM_OK && f.cleanup_count == 1U);
    assert(start(&f, &p) == PWM_ALREADY_USED);
}

static void test_clock_wrap(void)
{
    Fixture f; PWMProfile p = profile(); unsigned i;
    init(&f, UINT32_MAX - 4U); assert(start(&f, &p) == PWM_OK);
    for (i = 0U; i < 10U; ++i) healthy_tick(&f);
    assert(f.now == 5U && f.core.state == PWM_DONE && !f.output_on && !f.core.faults);
    assert((uint32_t)(f.core.stop_us - f.core.start_us) == 10U);
}

static void test_stale_adc_and_duplicate_timestamp(void)
{
    Fixture f; PWMProfile p = profile(); PWMSample old; unsigned i;
    init(&f, 20U); old = sample(&f, 0); assert(start(&f, &p) == PWM_OK);
    for (i = 0U; i < 3U; ++i) {
        ++f.now; PWM_OneShot_ADCISR(&f.core, &old); PWM_OneShot_PeriodicISR(&f.core);
        assert(f.output_on);
    }
    ++f.now; PWM_OneShot_PeriodicISR(&f.core);
    assert_fault_off(&f, PWM_F_ADC_STALE);
    assert(f.core.last_adc_us == old.at_us);
}

static void test_heartbeat_expiry_and_no_revival(void)
{
    Fixture f; PWMProfile p = profile(); unsigned i;
    p.heartbeat_max_age_us = 3U;
    init(&f, UINT32_MAX - 1U); assert(start(&f, &p) == PWM_OK);
    for (i = 0U; i < 3U; ++i) healthy_tick(&f);
    assert_fault_off(&f, PWM_F_HEARTBEAT);
    PWM_OneShot_Heartbeat(&f.core); assert_fault_off(&f, PWM_F_HEARTBEAT);
    init(&f, 10U); assert(start(&f, &p) == PWM_OK);
    f.now += 3U; PWM_OneShot_Heartbeat(&f.core);
    assert_fault_off(&f, PWM_F_HEARTBEAT); /* late heartbeat before ISR still faults */
}

static void test_fresh_adc_cannot_revive_expired_chain(void)
{
    Fixture f; PWMProfile p = profile(); PWMSample fresh; unsigned i;
    init(&f, 20U); assert(start(&f, &p) == PWM_OK);
    for (i = 0U; i < 3U; ++i) { ++f.now; PWM_OneShot_PeriodicISR(&f.core); }
    assert(f.output_on && f.core.last_adc_us == 20U && f.core.last_isr_us == 23U);
    f.now = 25U; fresh = sample(&f, 0);
    PWM_OneShot_ADCISR(&f.core, &fresh); /* ADC wins IRQ ordering at this instant. */
    assert_fault_off(&f, PWM_F_ADC_STALE);
    assert(f.core.last_adc_us == 20U); /* expired history was not overwritten */
    PWM_OneShot_PeriodicISR(&f.core);
    assert_fault_off(&f, PWM_F_ADC_STALE);
    assert(!f.cleanup_count && f.enable_count == 1U);
}

static void test_fresh_heartbeat(void)
{
    Fixture f; PWMProfile p = profile(); unsigned i;
    p.heartbeat_max_age_us = 3U;
    init(&f, 10U); assert(start(&f, &p) == PWM_OK);
    for (i = 0U; i < 10U; ++i) {
        PWM_OneShot_Heartbeat(&f.core); healthy_tick(&f);
    }
    assert(f.core.state == PWM_DONE && !f.core.faults);
}

static void test_adc_faults_immediate(void)
{
    const uint32_t reasons[] = {PWM_F_OVERCURRENT, PWM_F_OVERCURRENT, PWM_F_OVERRUN, PWM_F_ADC_INVALID, PWM_F_ADC_STALE};
    Fixture f; PWMProfile p = profile(); PWMSample s; unsigned i;
    for (i = 0U; i < 5U; ++i) {
        init(&f, 10U); assert(start(&f, &p) == PWM_OK); s = sample(&f, 0);
        if (i == 0U) s.current_ma = 101;
        if (i == 1U) s.current_ma = -101;
        if (i == 2U) s.overrun = 1U;
        if (i == 3U) s.valid = 0U;
        if (i == 4U) ++s.at_us;
        PWM_OneShot_ADCISR(&f.core, &s); assert_fault_off(&f, reasons[i]);
        assert(!f.cleanup_count); /* no foreground service needed to cut output */
    }
}

static void test_stop_protocol_and_latched_token(void)
{
    Fixture f; PWMProfile p = profile();
    init(&f, 10U); assert(start(&f, &p) == PWM_OK);
    PWM_OneShot_Stop(&f.core); assert_fault_off(&f, PWM_F_STOP);
    assert(PWM_OneShot_ClearFault(&f.core) == PWM_BUSY);
    assert(PWM_OneShot_Service(&f.core) == PWM_OK);
    assert(PWM_OneShot_ClearFault(&f.core) == PWM_OK);
    assert(!f.core.faults && f.core.used && start(&f, &p) == PWM_ALREADY_USED);
    init(&f, 10U); assert(start(&f, &p) == PWM_OK);
    PWM_OneShot_ProtocolError(&f.core); assert_fault_off(&f, PWM_F_PROTOCOL);
    assert(PWM_OneShot_Service(&f.core) == PWM_OK);
    assert(PWM_OneShot_ClearFault(&f.core) == PWM_OK);
    assert(start(&f, &p) == PWM_ALREADY_USED);
}

static void test_callback_failures_cut_off(void)
{
    Fixture f; PWMProfile p = profile();
    init(&f, 10U); f.prepare_ok = 0;
    assert(start(&f, &p) == PWM_ADAPTER_ERROR);
    assert_fault_off(&f, PWM_F_ADAPTER);
    assert(!strcmp(f.trace, "OOPO") && !f.enable_count && f.core.used);
    init(&f, 10U); f.enable_ok = 0;
    assert(start(&f, &p) == PWM_ADAPTER_ERROR);
    assert_fault_off(&f, PWM_F_ADAPTER);
    assert(!strcmp(f.trace, "OOPEO") && f.enable_count == 1U && f.core.used);
    assert(PWM_OneShot_Service(&f.core) == PWM_OK);
    assert(PWM_OneShot_ClearFault(&f.core) == PWM_OK);
    assert(start(&f, &p) == PWM_ALREADY_USED);
}

static void test_slow_adapter_is_rejected(void)
{
    Fixture f; PWMProfile p = profile();
    init(&f, 10U); f.prepare_delay = 3U;
    assert(start(&f, &p) == PWM_FAULTED); assert_fault_off(&f, PWM_F_ISR_LATE);
    assert(!f.enable_count && f.core.used);
    init(&f, 10U); f.enable_delay = 3U;
    assert(start(&f, &p) == PWM_FAULTED); assert_fault_off(&f, PWM_F_ISR_LATE);
    assert(f.enable_count == 1U && f.core.used);
}

static void test_late_isr_and_reinit(void)
{
    Fixture f; PWMProfile p = profile();
    init(&f, 10U); assert(start(&f, &p) == PWM_OK);
    f.now += 3U; PWM_OneShot_PeriodicISR(&f.core); assert_fault_off(&f, PWM_F_ISR_LATE);
    assert(PWM_OneShot_Init(&f.core, &ops, &f) == PWM_FAULTED);
    assert_fault_off(&f, PWM_F_REINIT);
    assert(f.core.used && f.prepare_count == 1U && start(&f, &p) == PWM_ALREADY_USED);
}

static void test_cleanup_failure_does_not_rearm(void)
{
    Fixture f; PWMProfile p = profile();
    init(&f, 10U); assert(start(&f, &p) == PWM_OK);
    PWM_OneShot_Stop(&f.core); f.cleanup_ok = 0;
    assert(PWM_OneShot_Service(&f.core) == PWM_ADAPTER_ERROR);
    assert_fault_off(&f, PWM_F_STOP | PWM_F_ADAPTER);
    assert(!strcmp(f.trace, "OOPEOCO"));
    assert(!f.core.pending_cleanup && f.cleanup_count == 1U);
    assert(PWM_OneShot_ClearFault(&f.core) == PWM_OK);
    assert(start(&f, &p) == PWM_ALREADY_USED);
}

static void test_missing_callback_and_null_interfaces(void)
{
    Fixture f; PWMOps incomplete = ops;
    memset(&f, 0, sizeof f); incomplete.enable_pair = NULL;
    assert(PWM_OneShot_Init(&f.core, &incomplete, &f) == PWM_BAD_ARGUMENT);
    assert(!f.core.initialized && f.off_count == 1U && !f.output_on);
    assert(PWM_OneShot_Init(NULL, &ops, &f) == PWM_BAD_ARGUMENT);
    assert(PWM_OneShot_Start(NULL, NULL, NULL) == PWM_NOT_READY);
    PWM_OneShot_Stop(NULL); PWM_OneShot_ProtocolError(NULL);
    PWM_OneShot_PeriodicISR(NULL); PWM_OneShot_ADCISR(NULL, NULL);
    PWM_OneShot_Heartbeat(NULL); PWM_OneShot_Trip(NULL, PWM_F_EXTERNAL);
    assert(PWM_OneShot_ClearFault(NULL) == PWM_NOT_READY);
    assert(PWM_OneShot_Service(NULL) == PWM_NOT_READY);
}

/* All quantities below are microseconds. These remain disconnected simulation
 * fixtures, selected to exercise a 100 us supervisor and 10 us ADC schedule. */
static PWMProfile micro_profile(void)
{
    PWMProfile p = profile();
    p.run_us = 1000U; p.max_run_us = 1000U;
    p.adc_max_age_us = 250U;
    p.heartbeat_max_age_us = 5000U;
    p.isr_max_gap_us = 200U;
    return p;
}

static void test_microsecond_cadence_and_wrap(void)
{
    Fixture f; PWMProfile p = micro_profile(); uint32_t elapsed, initial;
    unsigned scenario;
    for (scenario = 0U; scenario < 2U; ++scenario) {
        initial = scenario ? UINT32_MAX - 149U : 123456U;
        init(&f, initial); assert(start(&f, &p) == PWM_OK);
        for (elapsed = 10U; elapsed <= p.run_us; elapsed += 10U) {
            PWMSample s;
            f.now = initial + elapsed; s = sample(&f, 0);
            PWM_OneShot_ADCISR(&f.core, &s);
            if (elapsed % 100U == 0U) PWM_OneShot_PeriodicISR(&f.core);
            if (elapsed < p.run_us) assert(f.output_on && f.core.state == PWM_RUNNING);
        }
        assert(f.core.state == PWM_DONE && !f.core.faults && !f.output_on);
        assert((uint32_t)(f.core.stop_us - f.core.start_us) == 1000U);
        assert(f.core.pending_cleanup && !f.cleanup_count);
        assert(f.enable_count == 1U && start(&f, &p) == PWM_ALREADY_USED);
    }
}

static void test_microsecond_exact_deadline_boundary(void)
{
    Fixture f; PWMProfile p = micro_profile(); PWMSample s;
    p.run_us = 200U; p.max_run_us = 200U;
    init(&f, UINT32_MAX - 49U); assert(start(&f, &p) == PWM_OK);
    f.now += 100U; s = sample(&f, 0); PWM_OneShot_ADCISR(&f.core, &s);
    PWM_OneShot_PeriodicISR(&f.core); assert(f.output_on);
    f.now += 99U; s = sample(&f, 0); PWM_OneShot_ADCISR(&f.core, &s);
    PWM_OneShot_PeriodicISR(&f.core); assert(f.output_on && !f.core.faults);
    ++f.now; PWM_OneShot_PeriodicISR(&f.core);
    assert(f.core.state == PWM_DONE && !f.output_on && !f.core.faults);
    assert((uint32_t)(f.core.stop_us - f.core.start_us) == 200U);
}

static void test_microsecond_periodic_quantization_is_explicit(void)
{
    Fixture f; PWMProfile p = micro_profile(); PWMSample s;
    /* A deadline between periodic checks is observed at the next check.
     * The board adapter must budget this delay, never claim run_us as a hard
     * electrical maximum or round a physical limit upward to this schedule. */
    p.run_us = 150U; p.max_run_us = 150U; p.isr_max_gap_us = 100U;
    init(&f, 1000U); assert(start(&f, &p) == PWM_OK);
    f.now += 100U; s = sample(&f, 0); PWM_OneShot_ADCISR(&f.core, &s);
    PWM_OneShot_PeriodicISR(&f.core); assert(f.output_on);
    f.now += 100U; s = sample(&f, 0); PWM_OneShot_ADCISR(&f.core, &s);
    PWM_OneShot_PeriodicISR(&f.core);
    assert(f.core.state == PWM_DONE && !f.output_on && !f.core.faults);
    assert((uint32_t)(f.core.stop_us - f.core.start_us) == 200U);
}

static void test_microsecond_fresh_adc_cannot_revive(void)
{
    Fixture f; PWMProfile p = micro_profile(); PWMSample fresh;
    init(&f, UINT32_MAX - 199U); assert(start(&f, &p) == PWM_OK);
    f.now += 100U; PWM_OneShot_PeriodicISR(&f.core); assert(f.output_on);
    f.now += 100U; PWM_OneShot_PeriodicISR(&f.core); assert(f.output_on);
    f.now += 50U; fresh = sample(&f, 0);
    PWM_OneShot_ADCISR(&f.core, &fresh);
    assert_fault_off(&f, PWM_F_ADC_STALE);
    assert((uint32_t)(f.core.stop_us - f.core.start_us) == 250U);
    assert(f.core.last_adc_us == f.core.start_us);
}

static void test_microsecond_isr_gap_boundary(void)
{
    Fixture f; PWMProfile p = micro_profile(); PWMSample s;
    init(&f, 0U); assert(start(&f, &p) == PWM_OK);
    f.now = 200U; s = sample(&f, 0); PWM_OneShot_ADCISR(&f.core, &s);
    PWM_OneShot_PeriodicISR(&f.core); assert(f.output_on && !f.core.faults);
    f.now = 401U; s = sample(&f, 0); PWM_OneShot_ADCISR(&f.core, &s);
    assert(f.output_on); /* ADC freshness cannot mask delayed supervisor IRQ. */
    PWM_OneShot_PeriodicISR(&f.core); assert_fault_off(&f, PWM_F_ISR_LATE);
}

int main(void)
{
    unsigned tests = 0U;
#define RUN(fn) do { fn(); ++tests; puts("PASS " #fn); } while (0)
    RUN(test_default_and_missing_facts);
    RUN(test_policy_boundaries);
    RUN(test_initial_sample_rejected);
    RUN(test_deadline_without_foreground_and_frozen_ccr);
    RUN(test_clock_wrap);
    RUN(test_stale_adc_and_duplicate_timestamp);
    RUN(test_fresh_adc_cannot_revive_expired_chain);
    RUN(test_heartbeat_expiry_and_no_revival);
    RUN(test_fresh_heartbeat);
    RUN(test_adc_faults_immediate);
    RUN(test_stop_protocol_and_latched_token);
    RUN(test_callback_failures_cut_off);
    RUN(test_slow_adapter_is_rejected);
    RUN(test_late_isr_and_reinit);
    RUN(test_cleanup_failure_does_not_rearm);
    RUN(test_missing_callback_and_null_interfaces);
    RUN(test_microsecond_cadence_and_wrap);
    RUN(test_microsecond_exact_deadline_boundary);
    RUN(test_microsecond_periodic_quantization_is_explicit);
    RUN(test_microsecond_fresh_adc_cannot_revive);
    RUN(test_microsecond_isr_gap_boundary);
    printf("PASS %u tests; host simulation only; no board adapter\n", tests);
    return 0;
}
