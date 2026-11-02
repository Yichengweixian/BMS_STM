#include "pwm_oneshot.h"
#include <string.h>

#define HALF_RANGE UINT32_C(0x80000000)

static int interval(uint32_t n) { return n > 0U && n < HALF_RANGE; }
static int active(const PWMOneShot *c)
{ return c && c->initialized && (c->state == PWM_RUNNING || c->state == PWM_PREPARING); }

static int profile_valid(const PWMProfile *p)
{
    return p && p->enable_requested == 1U &&
        (p->verified_facts & PWM_FACT_ALL) == PWM_FACT_ALL && p->profile_id != 0U &&
        p->arr >= 2U && p->arr <= 65535U &&
        p->ccr_min > 0U && p->ccr_max < p->arr && p->ccr_min <= p->ccr_max &&
        p->ccr >= p->ccr_min && p->ccr <= p->ccr_max &&
        p->deadtime_code <= 255U &&
        ((p->deadtime_source == PWM_DEADTIME_DRIVER) ||
         ((p->deadtime_source == PWM_DEADTIME_TIMER || p->deadtime_source == PWM_DEADTIME_BOTH) &&
          p->deadtime_code > 0U)) &&
        interval(p->run_us) && interval(p->max_run_us) && p->run_us <= p->max_run_us &&
        interval(p->adc_max_age_us) && interval(p->heartbeat_max_age_us) &&
        interval(p->isr_max_gap_us) && p->isr_max_gap_us <= p->run_us &&
        p->isr_max_gap_us <= p->adc_max_age_us &&
        p->isr_max_gap_us <= p->heartbeat_max_age_us &&
        p->charge_max_ma > 0 && p->discharge_max_ma > 0 &&
        p->start_current_max_ma >= 0 && p->start_current_max_ma < p->charge_max_ma &&
        p->start_current_max_ma < p->discharge_max_ma;
}

static uint32_t sample_fault(const PWMProfile *p, const PWMSample *s, uint32_t now)
{
    uint32_t f = 0U;
    if (!s || s->valid != 1U) return PWM_F_ADC_INVALID;
    if (s->overrun) f |= PWM_F_OVERRUN;
    /* Future timestamps also fail, since the unsigned age is then huge. */
    if ((uint32_t)(now - s->at_us) >= p->adc_max_age_us) f |= PWM_F_ADC_STALE;
    if (s->current_ma > p->charge_max_ma || s->current_ma < -p->discharge_max_ma)
        f |= PWM_F_OVERCURRENT;
    return f;
}

static void finish(PWMOneShot *c, uint32_t now, uint32_t faults)
{
    /* This is deliberately before bookkeeping and ALL deferred callbacks. */
    c->ops.emergency_off(c->ctx);
    c->faults |= faults;
    c->stop_us = now;
    c->state = c->faults ? PWM_FAULT : PWM_DONE;
    c->pending_cleanup = 1U;
}

PWMResult PWM_OneShot_Init(PWMOneShot *c, const PWMOps *ops, void *ctx)
{
    if (!c) return PWM_BAD_ARGUMENT;
    if (c->initialized) {
        finish(c, c->ops.now_us(c->ctx), PWM_F_REINIT);
        return PWM_FAULTED; /* retains old callbacks and consumed token */
    }
    /* If supplied, close the adapter before rejecting an incomplete contract. */
    if (ops && ops->emergency_off) ops->emergency_off(ctx);
    if (!ops || !ops->now_us || !ops->emergency_off || !ops->prepare || !ops->enable_pair)
        return PWM_BAD_ARGUMENT;
    memset(c, 0, sizeof *c);
    c->ops = *ops; c->ctx = ctx; c->initialized = 1U; c->state = PWM_IDLE;
    return PWM_OK;
}

PWMResult PWM_OneShot_Start(PWMOneShot *c, const PWMProfile *p, const PWMSample *initial)
{
    uint32_t now, prepared_at, f;
    if (!c || !c->initialized) return PWM_NOT_READY;
    if (c->used) return PWM_ALREADY_USED;
    if (c->faults) return PWM_FAULTED;
    if (c->state != PWM_IDLE || c->pending_cleanup) return PWM_BUSY;
    if (!profile_valid(p)) return PWM_NOT_READY;
    now = c->ops.now_us(c->ctx);
    f = sample_fault(p, initial, now);
    if (f || initial->current_ma > p->start_current_max_ma ||
        initial->current_ma < -p->start_current_max_ma) return PWM_NOT_READY;

    /* Acceptance consumes the only token BEFORE a callback can touch hardware.
     * Callback failure, clear, cleanup and repeated Init cannot restore it. */
    c->used = 1U; c->frozen = *p; c->state = PWM_PREPARING;
    c->ops.emergency_off(c->ctx);
    if (c->ops.prepare(c->ctx, &c->frozen) != 1) {
        finish(c, c->ops.now_us(c->ctx), PWM_F_ADAPTER);
        return PWM_ADAPTER_ERROR;
    }
    prepared_at = c->ops.now_us(c->ctx);
    f = sample_fault(&c->frozen, initial, prepared_at);
    if ((uint32_t)(prepared_at - now) > c->frozen.isr_max_gap_us) f |= PWM_F_ISR_LATE;
    if (f) { finish(c, prepared_at, f); return PWM_FAULTED; }
    c->start_us = prepared_at;
    c->last_isr_us = prepared_at;
    c->last_heartbeat_us = prepared_at;
    c->last_adc_us = initial->at_us;
    c->last_current_ma = initial->current_ma;
    c->state = PWM_RUNNING;
    if (c->ops.enable_pair(c->ctx) != 1) {
        finish(c, c->ops.now_us(c->ctx), PWM_F_ADAPTER);
        return PWM_ADAPTER_ERROR;
    }
    /* A slow enable callback cannot grant extra time or refresh stale data. */
    PWM_OneShot_PeriodicISR(c);
    return c->state == PWM_RUNNING ? PWM_OK : PWM_FAULTED;
}

void PWM_OneShot_PeriodicISR(PWMOneShot *c)
{
    uint32_t now, f = 0U;
    if (!c || !c->initialized || c->state != PWM_RUNNING) return;
    now = c->ops.now_us(c->ctx);
    if ((uint32_t)(now - c->last_isr_us) > c->frozen.isr_max_gap_us) f |= PWM_F_ISR_LATE;
    if ((uint32_t)(now - c->last_adc_us) >= c->frozen.adc_max_age_us) f |= PWM_F_ADC_STALE;
    if ((uint32_t)(now - c->last_heartbeat_us) >= c->frozen.heartbeat_max_age_us) f |= PWM_F_HEARTBEAT;
    c->last_isr_us = now;
    if (f || (uint32_t)(now - c->start_us) >= c->frozen.run_us)
        finish(c, now, f);
}

void PWM_OneShot_ADCISR(PWMOneShot *c, const PWMSample *sample)
{
    uint32_t now, f;
    if (!c || !c->initialized || c->state != PWM_RUNNING) return;
    now = c->ops.now_us(c->ctx);
    f = sample_fault(&c->frozen, sample, now);
    /* Like heartbeat, late fresh data cannot revive an expired acquisition
     * chain merely by arriving before the pending periodic IRQ. */
    if ((uint32_t)(now - c->last_adc_us) >= c->frozen.adc_max_age_us)
        f |= PWM_F_ADC_STALE;
    if (f) { finish(c, now, f); return; }
    c->last_adc_us = sample->at_us; /* duplicate old data cannot extend freshness */
    c->last_current_ma = sample->current_ma;
}

void PWM_OneShot_Heartbeat(PWMOneShot *c)
{
    uint32_t now;
    if (!c || !c->initialized || c->state != PWM_RUNNING) return;
    now = c->ops.now_us(c->ctx);
    /* A late packet cannot revive an already expired heartbeat. */
    if ((uint32_t)(now - c->last_heartbeat_us) >= c->frozen.heartbeat_max_age_us)
        finish(c, now, PWM_F_HEARTBEAT);
    else c->last_heartbeat_us = now;
}

void PWM_OneShot_Trip(PWMOneShot *c, uint32_t fault)
{
    if (!c || !c->initialized || !fault) return;
    finish(c, c->ops.now_us(c->ctx), fault);
}
void PWM_OneShot_Stop(PWMOneShot *c)
{ if (active(c)) PWM_OneShot_Trip(c, PWM_F_STOP); }
void PWM_OneShot_ProtocolError(PWMOneShot *c)
{ if (active(c)) PWM_OneShot_Trip(c, PWM_F_PROTOCOL); }

PWMResult PWM_OneShot_ClearFault(PWMOneShot *c)
{
    if (!c || !c->initialized) return PWM_NOT_READY;
    if (active(c) || c->pending_cleanup) return PWM_BUSY;
    if (c->state != PWM_FAULT) return PWM_BAD_ARGUMENT;
    c->ops.emergency_off(c->ctx);
    c->faults = 0U; c->state = PWM_IDLE;
    return PWM_OK; /* used deliberately retained */
}

PWMResult PWM_OneShot_Service(PWMOneShot *c)
{
    if (!c || !c->initialized) return PWM_NOT_READY;
    if (!c->pending_cleanup) return PWM_OK;
    if (active(c)) return PWM_BUSY;
    c->pending_cleanup = 0U;
    if (c->ops.after_off && c->ops.after_off(c->ctx, c->state, c->faults) != 1) {
        /* Keep the token and fault latch, do not auto-retry cleanup forever. */
        c->ops.emergency_off(c->ctx);
        c->faults |= PWM_F_ADAPTER; c->state = PWM_FAULT;
        return PWM_ADAPTER_ERROR;
    }
    return PWM_OK;
}
