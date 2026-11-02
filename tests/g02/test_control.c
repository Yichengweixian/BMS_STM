/* Host fault injection against the production control state machine.
 * This mock proves API ordering/rollback, not MCU timing or electrical state. */
#include "g02_control.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    G02Control control;
    uint32_t irq_mask;
    uint32_t prepare_fault, enable_fault, compare_fault, cleanup_fault;
    unsigned prepare_action, enable_action, compare_action, cleanup_action;
    unsigned prepare_calls, enable_calls, off_calls, compare_calls, cleanup_calls;
    unsigned output, timer, adc, relay;
    unsigned pins_allowed;
    uint32_t written_compare;
} Fixture;

static uint32_t enter(void *ctx)
{
    Fixture *f = ctx;
    uint32_t previous = f->irq_mask;
    f->irq_mask = 1U;
    return previous;
}
static void leave(void *ctx, uint32_t previous)
{
    Fixture *f = ctx;
    assert(f->irq_mask == 1U && previous <= 1U);
    f->irq_mask = previous;
}
static int allow_mode(void *ctx, G02Mode mode)
{
    Fixture *f = ctx;
    assert(f->irq_mask == 1U);
    return mode == G02_MODE_SAMPLING || f->pins_allowed != 0U;
}
static void off(void *ctx)
{
    Fixture *f = ctx;
    assert(f->irq_mask == 1U);
    ++f->off_calls;
    f->output = 0U;
    f->timer = 0U;
    f->relay = 0U;
    /* ADC HAL cleanup is deliberately not performed in the fast off path. */
}
static uint32_t prepare(void *ctx, G02Mode mode, uint32_t compare)
{
    Fixture *f = ctx;
    (void)mode;
    assert(f->irq_mask == 0U);
    assert(f->control.state == G02_STATE_STARTING);
    assert(f->control.preparing != 0U && G02_OwnsADC(&f->control));
    assert(!f->output && !f->timer);
    ++f->prepare_calls;
    if (f->relay != 0U) return G02_FAULT_INTERLOCK;
    f->adc = 1U;
    f->written_compare = compare;
    switch (f->prepare_action) {
    case 1: G02_Stop(&f->control); break;
    case 2: G02_Fault(&f->control, G02_FAULT_INJECTED); break;
    case 3: f->relay = 1U; break;
    case 4:
        assert(G02_Start(&f->control, G02_MODE_SAMPLING, 1000U) == G02_BUSY);
        assert(G02_SetCompare(&f->control, 900U) == G02_NOT_READY);
        assert(G02_Service(&f->control) == G02_BUSY);
        assert(G02_ClearFault(&f->control) == G02_BUSY);
        break;
    case 5:
        G02_Fault(&f->control, G02_FAULT_INJECTED);
        assert(G02_Init(&f->control, NULL, NULL, 0U) == G02_FAULTED);
        assert(G02_ClearFault(&f->control) == G02_BUSY);
        assert(G02_Service(&f->control) == G02_BUSY);
        break;
    case 6:
        G02_Stop(&f->control);
        assert(G02_Start(&f->control, G02_MODE_SAMPLING, 1000U) == G02_BUSY);
        assert(G02_Service(&f->control) == G02_BUSY);
        break;
    default: break;
    }
    /* Emulate HAL continuing after the IRQ cancellation. The core must not
     * let this turn into a late enable and must retain cleanup ownership. */
    f->adc = 1U;
    return f->prepare_fault;
}
static uint32_t enable(void *ctx, G02Mode mode)
{
    Fixture *f = ctx;
    assert(f->irq_mask == 1U && f->control.state == G02_STATE_STARTING);
    assert(f->control.preparing == 0U);
    ++f->enable_calls;
    if (f->relay != 0U) return G02_FAULT_INTERLOCK;
    if (f->enable_fault != 0U) return f->enable_fault;
    f->timer = 1U;
    f->output = mode == G02_MODE_PINS;
    if (f->enable_action == 1U) G02_Fault(&f->control, G02_FAULT_CPU);
    if (f->enable_action == 2U) G02_Stop(&f->control);
    return 0U;
}
static uint32_t write_compare(void *ctx, uint32_t compare)
{
    Fixture *f = ctx;
    assert(f->irq_mask == 1U && f->control.state == G02_STATE_RUNNING);
    ++f->compare_calls;
    if (f->compare_fault != 0U) return f->compare_fault;
    f->written_compare = compare;
    if (f->compare_action == 1U) G02_Fault(&f->control, G02_FAULT_OVERRUN);
    if (f->compare_action == 2U) G02_Stop(&f->control);
    return 0U;
}
static uint32_t cleanup(void *ctx)
{
    Fixture *f = ctx;
    assert(f->irq_mask == 0U);
    assert(!f->output && !f->timer);
    assert(f->control.preparing == 0U && G02_OwnsADC(&f->control));
    ++f->cleanup_calls;
    if (f->cleanup_action == 1U) {
        assert(G02_Start(&f->control, G02_MODE_SAMPLING, 1000U) == G02_BUSY);
        assert(G02_Service(&f->control) == G02_BUSY);
        assert(G02_ClearFault(&f->control) == G02_BUSY);
        G02_Stop(&f->control);
    }
    if (f->cleanup_action == 2U) G02_Fault(&f->control, G02_FAULT_INJECTED);
    if (f->cleanup_fault != 0U) return f->cleanup_fault;
    f->adc = 0U;
    return 0U;
}
static const G02Ops ops = {
    enter, leave, allow_mode, prepare, enable, off, write_compare, cleanup
};

static void fixture(Fixture *f)
{
    memset(f, 0, sizeof *f);
    assert(G02_Init(&f->control, &ops, f, 2000U) == G02_OK);
    assert(f->irq_mask == 0U && f->off_calls == 1U);
    assert(f->control.state == G02_STATE_STOPPED);
    assert(f->control.compare == 1000U && f->control.faults == 0U);
    assert(!G02_OwnsADC(&f->control));
}
static void assert_off(const Fixture *f)
{
    assert(f->output == 0U && f->timer == 0U && f->relay == 0U);
    assert(f->irq_mask == 0U);
}

static void test_default_and_invalid_api(void)
{
    Fixture f;
    G02Control empty = {0};
    G02Ops incomplete = ops;
    assert(G02_Init(NULL, &ops, NULL, 2000U) == G02_BAD_ARGUMENT);
    assert(G02_Init(&empty, NULL, NULL, 2000U) == G02_BAD_ARGUMENT);
    incomplete.off = NULL;
    assert(G02_Init(&empty, &incomplete, NULL, 2000U) == G02_BAD_ARGUMENT);
    assert(G02_Init(&empty, &ops, NULL, 1000U) == G02_BAD_ARGUMENT);
    assert(G02_Start(&empty, G02_MODE_SAMPLING, 1000U) == G02_NOT_READY);
    assert(G02_SetCompare(&empty, 1000U) == G02_NOT_READY);
    assert(G02_ClearFault(&empty) == G02_NOT_READY);
    assert(G02_Service(&empty) == G02_NOT_READY);
    G02_Stop(&empty);
    G02_Fault(&empty, G02_FAULT_CPU);
    assert(!G02_OwnsADC(&empty) && !G02_OwnsADC(NULL));
    fixture(&f);
    assert(G02_Start(&f.control, (G02Mode)2, 1000U) == G02_BAD_ARGUMENT);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 0U) == G02_BAD_ARGUMENT);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 2000U) == G02_BAD_ARGUMENT);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, UINT32_MAX) == G02_BAD_ARGUMENT);
    assert(f.prepare_calls == 0U);
    assert(G02_Service(&f.control) == G02_OK && f.cleanup_calls == 0U);
    assert(G02_SetCompare(&f.control, 900U) == G02_NOT_READY);
    assert_off(&f);
}

static void test_gate_and_modes(void)
{
    Fixture f;
    fixture(&f);
    assert(G02_Start(&f.control, G02_MODE_PINS, 1000U) == G02_DISALLOWED);
    assert(f.prepare_calls == 0U && f.control.faults == 0U);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_OK);
    assert(f.control.state == G02_STATE_RUNNING && f.timer && f.adc && !f.output);
    assert(G02_OwnsADC(&f.control));
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_BUSY);
    assert(G02_ClearFault(&f.control) == G02_BUSY);
    assert(G02_Service(&f.control) == G02_BUSY);
    G02_Stop(&f.control);
    assert_off(&f);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_NOT_READY);
    assert(G02_Service(&f.control) == G02_OK && f.adc == 0U);
    f.pins_allowed = 1U;
    assert(G02_Start(&f.control, G02_MODE_PINS, 1000U) == G02_OK);
    assert(f.output == 1U && f.control.mode == G02_MODE_PINS);
    G02_Stop(&f.control);
    assert_off(&f);
    assert(G02_Service(&f.control) == G02_OK);
}

static void test_stop_idempotence_and_cleanup(void)
{
    Fixture f;
    fixture(&f);
    G02_Stop(&f.control);
    G02_Stop(&f.control);
    assert(!G02_OwnsADC(&f.control));
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_OK);
    G02_Stop(&f.control);
    G02_Stop(&f.control);
    assert(f.control.state == G02_STATE_STOPPED && G02_OwnsADC(&f.control));
    assert(f.cleanup_calls == 0U && f.adc == 1U);
    f.cleanup_action = 1U;
    assert(G02_Service(&f.control) == G02_OK);
    assert(f.cleanup_calls == 1U && !G02_OwnsADC(&f.control));
    assert(G02_Service(&f.control) == G02_OK && f.cleanup_calls == 1U);
    assert_off(&f);
}

static void test_fault_latching_and_explicit_clear(void)
{
    Fixture f;
    fixture(&f);
    f.pins_allowed = 1U;
    assert(G02_Start(&f.control, G02_MODE_PINS, 1000U) == G02_OK);
    G02_Fault(&f.control, G02_FAULT_OVERRUN);
    G02_Fault(&f.control, G02_FAULT_TIMING);
    G02_Stop(&f.control);
    assert_off(&f);
    assert(f.control.state == G02_STATE_FAULT);
    assert(f.control.faults == (G02_FAULT_OVERRUN | G02_FAULT_TIMING));
    assert(G02_Start(&f.control, G02_MODE_PINS, 1000U) == G02_FAULTED);
    assert(G02_SetCompare(&f.control, 700U) == G02_FAULTED);
    assert(G02_ClearFault(&f.control) == G02_NOT_READY);
    assert(G02_Service(&f.control) == G02_OK);
    assert(f.control.state == G02_STATE_FAULT);
    assert(G02_ClearFault(&f.control) == G02_OK);
    assert(f.control.state == G02_STATE_STOPPED && f.control.faults == 0U);
    assert_off(&f);
    assert(f.enable_calls == 1U);
    assert(G02_Start(&f.control, G02_MODE_PINS, 1000U) == G02_OK);
    G02_Stop(&f.control);
    assert(G02_Service(&f.control) == G02_OK);
    G02_Fault(&f.control, 0U);
    assert(f.control.faults == G02_FAULT_CONFIG);
    assert(!G02_OwnsADC(&f.control));
}

static void test_prepare_faults_and_interlocks(void)
{
    Fixture f;
    uint32_t failures[] = {G02_FAULT_CLOCK, G02_FAULT_ADC, G02_FAULT_CONFIG, G02_FAULT_PREPARE};
    unsigned i;
    for (i = 0U; i < sizeof failures / sizeof failures[0]; ++i) {
        fixture(&f);
        f.prepare_fault = failures[i];
        assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
        assert(f.control.faults == failures[i] && f.enable_calls == 0U);
        assert(f.cleanup_calls == 0U && G02_OwnsADC(&f.control));
        assert_off(&f);
        assert(G02_Service(&f.control) == G02_OK);
    }
    fixture(&f);
    f.relay = 1U;
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert(f.control.faults == G02_FAULT_INTERLOCK && f.enable_calls == 0U);
    assert_off(&f);
    fixture(&f);
    f.prepare_action = 3U;
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert(f.control.faults == G02_FAULT_INTERLOCK && f.enable_calls == 1U);
    assert_off(&f);
    fixture(&f);
    f.enable_fault = G02_FAULT_CLOCK;
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert(f.control.faults == G02_FAULT_CLOCK);
    assert_off(&f);
}

static void test_prepare_cancellation_and_reentrancy(void)
{
    Fixture f;
    unsigned action;
    for (action = 1U; action <= 6U; ++action) {
        if (action == 3U) continue;
        fixture(&f);
        f.prepare_action = action;
        if (action == 4U) {
            assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_OK);
            G02_Stop(&f.control);
        } else {
            G02Result expected = action == 2U || action == 5U ? G02_FAULTED : G02_CANCELED;
            assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == expected);
            assert(f.enable_calls == 0U && f.off_calls >= 3U);
        }
        assert(f.control.preparing == 0U && G02_OwnsADC(&f.control));
        assert_off(&f);
        assert(G02_Service(&f.control) == G02_OK);
        assert(!G02_OwnsADC(&f.control));
    }
    fixture(&f);
    f.prepare_action = 2U;
    f.prepare_fault = G02_FAULT_ADC;
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert(f.control.faults == (G02_FAULT_INJECTED | G02_FAULT_ADC));
}

static void test_enable_cancellation(void)
{
    Fixture f;
    unsigned action;
    for (action = 1U; action <= 2U; ++action) {
        fixture(&f);
        f.pins_allowed = 1U;
        f.enable_action = action;
        assert(G02_Start(&f.control, G02_MODE_PINS, 1000U) ==
               (action == 1U ? G02_FAULTED : G02_CANCELED));
        assert(f.control.state != G02_STATE_RUNNING);
        assert_off(&f);
        assert(G02_Service(&f.control) == G02_OK);
    }
}

static void test_compare_range_and_faults(void)
{
    Fixture f;
    unsigned action;
    fixture(&f);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_OK);
    assert(G02_SetCompare(&f.control, 0U) == G02_BAD_ARGUMENT);
    assert(G02_SetCompare(&f.control, 2000U) == G02_BAD_ARGUMENT);
    assert(G02_SetCompare(&f.control, UINT32_MAX) == G02_BAD_ARGUMENT);
    assert(f.compare_calls == 0U && f.control.compare == 1000U);
    assert(G02_SetCompare(&f.control, 1U) == G02_OK);
    assert(f.control.compare == 1U && f.written_compare == 1U);
    assert(G02_SetCompare(&f.control, 1999U) == G02_OK);
    assert(f.control.compare == 1999U && f.written_compare == 1999U);
    f.compare_fault = G02_FAULT_CONFIG;
    assert(G02_SetCompare(&f.control, 1000U) == G02_FAULTED);
    assert(f.control.compare == 1999U && f.control.faults == G02_FAULT_CONFIG);
    assert_off(&f);
    for (action = 1U; action <= 2U; ++action) {
        fixture(&f);
        assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_OK);
        f.compare_action = action;
        assert(G02_SetCompare(&f.control, 900U) ==
               (action == 1U ? G02_FAULTED : G02_CANCELED));
        assert(f.control.compare == 1000U);
        assert_off(&f);
    }
}

static void test_reinit_preserves_fault_and_ownership(void)
{
    Fixture f;
    fixture(&f);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_OK);
    assert(G02_Init(&f.control, NULL, NULL, 0U) == G02_NOT_READY);
    assert(f.control.ops == &ops && f.control.ctx == &f && f.control.arr == 2000U);
    assert(f.control.state == G02_STATE_STOPPED && G02_OwnsADC(&f.control));
    assert_off(&f);
    G02_Fault(&f.control, G02_FAULT_CPU);
    assert(G02_Init(&f.control, NULL, NULL, 0U) == G02_FAULTED);
    assert(f.control.faults == G02_FAULT_CPU && f.control.state == G02_STATE_FAULT);
    assert(G02_OwnsADC(&f.control));
    assert(G02_Service(&f.control) == G02_OK);
    assert(f.control.faults == G02_FAULT_CPU);
}

static void test_cleanup_failure_and_fault_during_cleanup(void)
{
    Fixture f;
    fixture(&f);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_OK);
    G02_Stop(&f.control);
    f.cleanup_fault = G02_FAULT_ADC;
    assert(G02_Service(&f.control) == G02_FAULTED);
    assert(f.control.faults == G02_FAULT_ADC && G02_OwnsADC(&f.control));
    assert(G02_ClearFault(&f.control) == G02_NOT_READY);
    assert(G02_Start(&f.control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    f.cleanup_fault = 0U;
    f.cleanup_action = 2U;
    assert(G02_Service(&f.control) == G02_OK);
    assert(f.control.faults == (G02_FAULT_ADC | G02_FAULT_INJECTED));
    assert(f.control.state == G02_STATE_FAULT && !G02_OwnsADC(&f.control));
    assert_off(&f);
}

int main(void)
{
    unsigned count = 0U;
#define RUN(test) do { test(); ++count; puts("PASS: " #test); } while (0)
    RUN(test_default_and_invalid_api);
    RUN(test_gate_and_modes);
    RUN(test_stop_idempotence_and_cleanup);
    RUN(test_fault_latching_and_explicit_clear);
    RUN(test_prepare_faults_and_interlocks);
    RUN(test_prepare_cancellation_and_reentrancy);
    RUN(test_enable_cancellation);
    RUN(test_compare_range_and_faults);
    RUN(test_reinit_preserves_fault_and_ownership);
    RUN(test_cleanup_failure_and_fault_during_cleanup);
#undef RUN
    printf("PASS: %u production-control host test groups; SIMULATION ONLY.\n", count);
    return 0;
}
