#ifndef G02_PORT_H
#define G02_PORT_H
#include "g02_control.h"

/* Deliberately OFF in both delivered targets. A separately reviewed no-power
 * build is required for pin output. This flag is not hardware authorization. */
#ifndef G02_ALLOW_PIN_OUTPUT
#define G02_ALLOW_PIN_OUTPUT 0
#endif
#define G02_TRACE_LENGTH 128U
#define G02_MAX_WINDOW_MS 10000U

enum { G02_CMD_NONE, G02_CMD_SAMPLE, G02_CMD_PINS, G02_CMD_STOP,
       G02_CMD_FAULT, G02_CMD_CLEAR, G02_CMD_COMPARE };
enum { G02_EVENT_UPDATE=1, G02_EVENT_ADC, G02_EVENT_CCR, G02_EVENT_OFF };
typedef struct {
    uint32_t cycles, counter, down, event, update_seq;
} G02TraceEvent;
typedef struct {
    uint32_t cpu_hz, tim_hz, adc_hz, psc, arr, rcr, dtg;
    uint32_t start_ms, stop_ms, start_cycles, stop_request_cycles, stop_cycles;
    uint32_t update_irqs, adc_completions, overruns, adc_errors;
    uint32_t update_gap_max_cycles, update_isr_max_cycles, adc_isr_max_cycles;
    uint32_t cycle_read_pair_cycles, late_update_irqs;
    uint32_t adc_counter, adc_down, last_adc_raw;
    uint32_t ccr_writes, ccr_requested, ccr_next_uev_observed;
    uint32_t ccr_write_cycles, ccr_observed_cycles;
    uint32_t trace_written, trace_overwritten;
    G02TraceEvent trace[G02_TRACE_LENGTH];
} G02Telemetry;

/* Debugger mailbox: set compare/window first; write command LAST while halted,
 * then run freely. No breakpoints during the timing window. No UART command.
 * Mailbox is consumed in main context and never arms itself after reset. */
extern volatile uint32_t g02_command, g02_compare, g02_window_ms;
extern volatile G02Result g02_command_result;
extern G02Control g02_control;
extern volatile G02Telemetry g02_telemetry;
void G02_PortInit(void);
void G02_Task(void);
int G02_MeasurementAllowed(void);
void G02_EmergencyOff(void);
void G02_CPUFault(void);
void G02_TIM1_IRQHandler(void);
int G02_ADC_IRQHandler(void);
#endif
