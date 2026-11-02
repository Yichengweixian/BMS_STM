#ifndef G02_CONTROL_H
#define G02_CONTROL_H

#include <stdint.h>

#define G02_INITIAL_COMPARE 1000U

typedef enum {
    G02_MODE_SAMPLING = 0,
    G02_MODE_PINS = 1
} G02Mode;

typedef enum {
    G02_STATE_STOPPED = 0,
    G02_STATE_STARTING,
    G02_STATE_RUNNING,
    G02_STATE_FAULT
} G02State;

typedef enum {
    G02_OK = 0,
    G02_BAD_ARGUMENT,
    G02_NOT_READY,
    G02_BUSY,
    G02_DISALLOWED,
    G02_FAULTED,
    G02_CANCELED
} G02Result;

enum {
    G02_FAULT_CONFIG    = 1U << 0,
    G02_FAULT_ADC       = 1U << 1,
    G02_FAULT_OVERRUN   = 1U << 2,
    G02_FAULT_INTERLOCK = 1U << 3,
    G02_FAULT_TIMING    = 1U << 4,
    G02_FAULT_INJECTED  = 1U << 5,
    G02_FAULT_CPU       = 1U << 6,
    G02_FAULT_CLOCK     = 1U << 7,
    G02_FAULT_PREPARE   = 1U << 8
};

/* enter/leave protect short state and register operations only. prepare and
 * cleanup run in the caller's main context, with interrupts enabled normally.
 * All fault-returning callbacks return zero on success, or a fault bitmask.
 * off MUST be nonblocking, idempotent, and remove output before other work.
 * enable MUST recheck relay/configuration interlocks before opening output.
 * allow_mode is a software capability gate, not proof of physical isolation. */
typedef struct {
    uint32_t (*enter)(void *ctx);
    void (*leave)(void *ctx, uint32_t key);
    int (*allow_mode)(void *ctx, G02Mode mode);
    uint32_t (*prepare)(void *ctx, G02Mode mode, uint32_t compare);
    uint32_t (*enable)(void *ctx, G02Mode mode);
    void (*off)(void *ctx);
    uint32_t (*write_compare)(void *ctx, uint32_t compare);
    uint32_t (*cleanup)(void *ctx);
} G02Ops;

/* Instances MUST be zero initialized before their first G02_Init call.
 * State fields are observable; all writes belong to the control API.
 * Repeated Init stops the existing instance and retains faults and ownership. */
typedef struct {
    const G02Ops *ops;
    void *ctx;
    uint32_t arr;
    volatile uint32_t compare;
    volatile uint32_t faults;
    volatile G02State state;
    volatile G02Mode mode;
    volatile uint8_t initialized;
    volatile uint8_t preparing;
    volatile uint8_t cleanup_pending;
    volatile uint8_t cleaning;
} G02Control;

G02Result G02_Init(G02Control *c, const G02Ops *ops, void *ctx, uint32_t arr);
/* Start, ClearFault, Service: main context only. Never call Start from an IRQ.
 * Compare is diagnostic CCR, strictly 1..ARR-1, not an allowed power range. */
G02Result G02_Start(G02Control *c, G02Mode mode, uint32_t compare);
void G02_Stop(G02Control *c);
void G02_Fault(G02Control *c, uint32_t faults);
G02Result G02_ClearFault(G02Control *c);
G02Result G02_SetCompare(G02Control *c, uint32_t compare);
G02Result G02_Service(G02Control *c);
int G02_OwnsADC(const G02Control *c);

#endif
