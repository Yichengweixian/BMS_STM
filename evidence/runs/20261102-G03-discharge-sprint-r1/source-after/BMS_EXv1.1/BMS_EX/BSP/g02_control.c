#include "g02_control.h"
#include <stddef.h>

static int valid_ops(const G02Ops *ops)
{
    return ops != NULL && ops->enter != NULL && ops->leave != NULL &&
           ops->allow_mode != NULL && ops->prepare != NULL &&
           ops->enable != NULL && ops->off != NULL &&
           ops->write_compare != NULL && ops->cleanup != NULL;
}

static int ready(const G02Control *c)
{
    return c != NULL && c->initialized != 0U;
}

static int valid_compare(const G02Control *c, uint32_t compare)
{
    return compare > 0U && compare < c->arr;
}

/* Caller holds the short critical section. No HAL waits belong here. */
static void fault_locked(G02Control *c, uint32_t faults)
{
    c->ops->off(c->ctx);
    if (c->state == G02_STATE_STARTING || c->state == G02_STATE_RUNNING ||
        c->preparing != 0U || c->cleaning != 0U) {
        c->cleanup_pending = 1U;
    }
    c->faults |= faults != 0U ? faults : G02_FAULT_CONFIG;
    c->state = G02_STATE_FAULT;
}

G02Result G02_Init(G02Control *c, const G02Ops *ops, void *ctx, uint32_t arr)
{
    uint32_t key;
    if (c == NULL) return G02_BAD_ARGUMENT;
    if (c->initialized != 0U) {
        /* Initialization is not a fault reset or a back door to reuse ADC. */
        G02_Stop(c);
        return c->faults != 0U ? G02_FAULTED : G02_NOT_READY;
    }
    if (!valid_ops(ops) || arr <= G02_INITIAL_COMPARE) return G02_BAD_ARGUMENT;
    c->ops = ops;
    c->ctx = ctx;
    key = ops->enter(ctx);
    ops->off(ctx);
    c->arr = arr;
    c->compare = G02_INITIAL_COMPARE;
    c->faults = 0U;
    c->state = G02_STATE_STOPPED;
    c->mode = G02_MODE_SAMPLING;
    c->preparing = 0U;
    c->cleaning = 0U;
    c->cleanup_pending = 0U;
    c->initialized = 1U;
    ops->leave(ctx, key);
    return G02_OK;
}

G02Result G02_Start(G02Control *c, G02Mode mode, uint32_t compare)
{
    uint32_t key, faults;
    G02Result result = G02_OK;
    if (!ready(c)) return G02_NOT_READY;
    key = c->ops->enter(c->ctx);
    if (c->faults != 0U || c->state == G02_STATE_FAULT) result = G02_FAULTED;
    else if (mode != G02_MODE_SAMPLING && mode != G02_MODE_PINS) result = G02_BAD_ARGUMENT;
    else if (!valid_compare(c, compare)) result = G02_BAD_ARGUMENT;
    else if (c->state != G02_STATE_STOPPED || c->preparing != 0U || c->cleaning != 0U)
        result = G02_BUSY;
    else if (c->cleanup_pending != 0U) result = G02_NOT_READY;
    else if (!c->ops->allow_mode(c->ctx, mode)) result = G02_DISALLOWED;
    if (result != G02_OK) {
        c->ops->leave(c->ctx, key);
        return result;
    }
    c->state = G02_STATE_STARTING;
    c->mode = mode;
    c->compare = compare;
    c->preparing = 1U;
    c->cleanup_pending = 1U;
    c->ops->leave(c->ctx, key);

    /* Preparation may block briefly in HAL and must remain interruptible.
     * STOP/fault can cancel it; the state check below is the only enable gate. */
    faults = c->ops->prepare(c->ctx, mode, compare);

    key = c->ops->enter(c->ctx);
    c->preparing = 0U;
    if (faults != 0U) {
        fault_locked(c, faults);
        result = G02_FAULTED;
    } else if (c->state != G02_STATE_STARTING || c->faults != 0U) {
        /* Preparation could have continued after an IRQ STOP. Remove any
         * peripheral state it established after that STOP, before returning. */
        c->ops->off(c->ctx);
        result = c->faults != 0U ? G02_FAULTED : G02_CANCELED;
    } else {
        faults = c->ops->enable(c->ctx, mode);
        if (faults != 0U) {
            fault_locked(c, faults);
            result = G02_FAULTED;
        } else if (c->state != G02_STATE_STARTING || c->faults != 0U) {
            c->ops->off(c->ctx);
            result = c->faults != 0U ? G02_FAULTED : G02_CANCELED;
        } else {
            c->state = G02_STATE_RUNNING;
        }
    }
    c->ops->leave(c->ctx, key);
    return result;
}

void G02_Stop(G02Control *c)
{
    uint32_t key;
    if (!ready(c)) return;
    key = c->ops->enter(c->ctx);
    c->ops->off(c->ctx);
    if (c->state == G02_STATE_STARTING || c->state == G02_STATE_RUNNING ||
        c->preparing != 0U || c->cleaning != 0U) {
        c->cleanup_pending = 1U;
    }
    c->state = c->faults != 0U ? G02_STATE_FAULT : G02_STATE_STOPPED;
    c->ops->leave(c->ctx, key);
}

void G02_Fault(G02Control *c, uint32_t faults)
{
    uint32_t key;
    if (!ready(c)) return;
    key = c->ops->enter(c->ctx);
    fault_locked(c, faults);
    c->ops->leave(c->ctx, key);
}

G02Result G02_ClearFault(G02Control *c)
{
    uint32_t key;
    G02Result result = G02_OK;
    if (!ready(c)) return G02_NOT_READY;
    key = c->ops->enter(c->ctx);
    if (c->state == G02_STATE_RUNNING || c->state == G02_STATE_STARTING ||
        c->preparing != 0U || c->cleaning != 0U) result = G02_BUSY;
    else if (c->cleanup_pending != 0U) result = G02_NOT_READY;
    else {
        c->ops->off(c->ctx);
        c->faults = 0U;
        c->state = G02_STATE_STOPPED;
    }
    c->ops->leave(c->ctx, key);
    return result;
}

G02Result G02_SetCompare(G02Control *c, uint32_t compare)
{
    uint32_t key, faults;
    G02Result result = G02_OK;
    if (!ready(c)) return G02_NOT_READY;
    key = c->ops->enter(c->ctx);
    if (c->faults != 0U || c->state == G02_STATE_FAULT) result = G02_FAULTED;
    else if (!valid_compare(c, compare)) result = G02_BAD_ARGUMENT;
    else if (c->state != G02_STATE_RUNNING) result = G02_NOT_READY;
    else {
        faults = c->ops->write_compare(c->ctx, compare);
        if (faults != 0U) {
            fault_locked(c, faults);
            result = G02_FAULTED;
        } else if (c->faults != 0U || c->state != G02_STATE_RUNNING) {
            c->ops->off(c->ctx);
            result = c->faults != 0U ? G02_FAULTED : G02_CANCELED;
        } else c->compare = compare;
    }
    c->ops->leave(c->ctx, key);
    return result;
}

G02Result G02_Service(G02Control *c)
{
    uint32_t key, faults;
    if (!ready(c)) return G02_NOT_READY;
    key = c->ops->enter(c->ctx);
    if (c->state == G02_STATE_RUNNING || c->state == G02_STATE_STARTING ||
        c->preparing != 0U || c->cleaning != 0U) {
        c->ops->leave(c->ctx, key);
        return G02_BUSY;
    }
    if (c->cleanup_pending == 0U) {
        c->ops->leave(c->ctx, key);
        return G02_OK;
    }
    c->cleaning = 1U;
    c->ops->leave(c->ctx, key);
    faults = c->ops->cleanup(c->ctx);
    key = c->ops->enter(c->ctx);
    c->cleaning = 0U;
    if (faults != 0U) {
        fault_locked(c, faults);
        c->cleanup_pending = 1U;
    } else c->cleanup_pending = 0U;
    c->ops->leave(c->ctx, key);
    return faults != 0U ? G02_FAULTED : G02_OK;
}

int G02_OwnsADC(const G02Control *c)
{
    if (!ready(c)) return 0;
    return c->state == G02_STATE_STARTING || c->state == G02_STATE_RUNNING ||
           c->preparing != 0U || c->cleanup_pending != 0U || c->cleaning != 0U;
}
