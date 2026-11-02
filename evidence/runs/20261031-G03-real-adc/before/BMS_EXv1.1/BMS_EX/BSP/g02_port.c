#include "g02_port.h"
#include "g03_port.h"
#include "main.h"
#include <string.h>

extern ADC_HandleTypeDef hadc1;
extern TIM_HandleTypeDef htim1;
G02Control g02_control;
volatile G02Telemetry g02_telemetry;
volatile uint32_t g02_command;
volatile uint32_t g02_compare = G02_INITIAL_COMPARE;
volatile uint32_t g02_window_ms = G02_MAX_WINDOW_MS;
volatile G02Result g02_command_result;
static ADC_InitTypeDef saved_adc;
static volatile uint8_t adc_owned, timer_running, ccr_pending;
static uint32_t last_update_cycles, window_ms;

static uint32_t enter(void *ctx)
{
    uint32_t key = __get_PRIMASK(); (void)ctx;
    __disable_irq(); return key;
}
static void leave(void *ctx, uint32_t key)
{
    (void)ctx; __set_PRIMASK(key);
}
static uint32_t cycles(void) { return DWT->CYCCNT; }
static void maximum(volatile uint32_t *value, uint32_t n)
{
    if (n > *value) *value = n;
}
static void trace(uint32_t event)
{
    uint32_t seq = g02_telemetry.trace_written;
    volatile G02TraceEvent *e = &g02_telemetry.trace[seq % G02_TRACE_LENGTH];
    e->cycles = cycles(); e->counter = TIM1->CNT;
    e->down = (TIM1->CR1 & TIM_CR1_DIR) != 0U;
    e->event = event; e->update_seq = g02_telemetry.update_irqs;
    g02_telemetry.trace_written = seq + 1U;
    if (seq >= G02_TRACE_LENGTH) ++g02_telemetry.trace_overwritten;
}

/* Register-only shutdown: valid before PortInit and from a fault handler.
 * LOW is a defined MCU level, NOT proof of driver/relay physical isolation. */
void G02_EmergencyOff(void)
{
    if (__HAL_RCC_TIM1_IS_CLK_ENABLED()) {
        CLEAR_BIT(TIM1->BDTR, TIM_BDTR_MOE | TIM_BDTR_AOE);
        TIM1->DIER = 0U;
        CLEAR_BIT(TIM1->CR1, TIM_CR1_CEN);
        TIM1->CCER = 0U;
    }
    if (__HAL_RCC_GPIOA_IS_CLK_ENABLED()) {
        GPIOA->BSRR = GPIO_PIN_9 << 16U;
        CLEAR_BIT(GPIOA->OTYPER, GPIO_PIN_9);
        MODIFY_REG(GPIOA->MODER, 3UL << 18U, 1UL << 18U);
    }
    if (__HAL_RCC_GPIOF_IS_CLK_ENABLED()) {
        GPIOF->BSRR = GPIO_PIN_7 << 16U;
        CLEAR_BIT(GPIOF->OTYPER, GPIO_PIN_7);
        MODIFY_REG(GPIOF->MODER, 3UL << 14U, 1UL << 14U);
    }
    if (__HAL_RCC_GPIOB_IS_CLK_ENABLED()) GPIOB->BSRR = SWS_Relay_Pin << 16U;
    if (__HAL_RCC_GPIOG_IS_CLK_ENABLED()) GPIOG->BSRR = SWL_Relay_Pin << 16U;
    __DSB();
}
static void off(void *ctx)
{
    (void)ctx;
    if (timer_running) g02_telemetry.stop_request_cycles = cycles();
    G02_EmergencyOff();
    if (timer_running) {
        timer_running = 0U;
        g02_telemetry.stop_cycles = cycles();
        g02_telemetry.stop_ms = HAL_GetTick();
        trace(G02_EVENT_OFF);
    }
    ccr_pending = 0U;
}
static uint32_t interlock(void)
{
    return ((SWS_Relay_GPIO_Port->ODR & SWS_Relay_Pin) ||
            (SWL_Relay_GPIO_Port->ODR & SWL_Relay_Pin)) ? G02_FAULT_INTERLOCK : 0U;
}
static int allow_mode(void *ctx, G02Mode mode)
{
    (void)ctx;
    return mode == G02_MODE_SAMPLING || (mode == G02_MODE_PINS && G02_ALLOW_PIN_OUTPUT);
}
static uint32_t prepare(void *ctx, G02Mode mode, uint32_t compare)
{
    uint32_t before, after;
    (void)ctx; (void)mode;
    if (interlock()) return G02_FAULT_INTERLOCK;
    /* Snapshot actual runtime clocks, including Release's inherited FSBL. */
    memset((void *)&g02_telemetry, 0, sizeof g02_telemetry);
    g02_telemetry.cpu_hz = HAL_RCC_GetCpuClockFreq();
    g02_telemetry.tim_hz = HAL_RCCEx_GetTIMGFreq();
    g02_telemetry.adc_hz = HAL_RCCEx_GetPeriphCLKFreq(RCC_PERIPHCLK_ADC);
    g02_telemetry.psc = TIM1->PSC; g02_telemetry.arr = TIM1->ARR;
    g02_telemetry.rcr = TIM1->RCR; g02_telemetry.dtg = TIM1->BDTR & TIM_BDTR_DTG;
    if (g02_telemetry.tim_hz != 400000000U || g02_telemetry.adc_hz != 64000000U ||
        g02_telemetry.cpu_hz == 0U) return G02_FAULT_CLOCK;
    if (TIM1->PSC != 0U || TIM1->ARR != 2000U || TIM1->RCR != 1U ||
        (TIM1->CR1 & TIM_CR1_CMS) != TIM_COUNTERMODE_CENTERALIGNED1 ||
        (TIM1->CR1 & TIM_CR1_CKD) != TIM_CLOCKDIVISION_DIV1 ||
        (TIM1->CCMR1 & TIM_CCMR1_OC2M) != (TIM_OCMODE_PWM1 << 8U) ||
        !(TIM1->CCMR1 & TIM_CCMR1_OC2PE) || !(TIM1->CR1 & TIM_CR1_ARPE))
        return G02_FAULT_CONFIG;
    /* DWT timestamps are observations, never a replacement for scope timing. */
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    before = cycles(); __DSB(); __ISB(); after = cycles();
    g02_telemetry.cycle_read_pair_cycles = after - before;
    if ((DWT->CTRL & DWT_CTRL_NOCYCCNT_Msk) || after == before) return G02_FAULT_TIMING;
    last_update_cycles = 0U; ccr_pending = 0U;

    /* Quiet preparation: UG must occur BEFORE ADC is armed. MMS=RESET still
     * propagates UG as TRGO, so use ENABLE (CEN=0) while forcing preload. */
    CLEAR_BIT(TIM1->BDTR, TIM_BDTR_MOE | TIM_BDTR_AOE);
    TIM1->DIER = 0U; TIM1->CCER = 0U;
    /* DIR is read-only while center-aligned. Stop, temporarily select edge
     * alignment, reset DIR, then restore CMS so every restart starts up. */
    CLEAR_BIT(TIM1->CR1, TIM_CR1_CEN | TIM_CR1_CMS | TIM_CR1_UDIS);
    CLEAR_BIT(TIM1->CR1, TIM_CR1_DIR);
    SET_BIT(TIM1->CR1, TIM_COUNTERMODE_CENTERALIGNED1);
    SET_BIT(TIM1->CR1, TIM_CR1_URS);
    MODIFY_REG(TIM1->CR2, TIM_CR2_MMS, TIM_TRGO_ENABLE);
    TIM1->CNT = 0U; TIM1->CCR2 = compare;
    TIM1->EGR = TIM_EGR_UG;
    TIM1->SR = 0U;
    MODIFY_REG(TIM1->CR2, TIM_CR2_MMS, TIM_TRGO_UPDATE);
    g02_telemetry.ccr_requested = compare;
    /* G01 and this session have exclusive ADC ownership until cleanup succeeds. */
    saved_adc = hadc1.Init;
    adc_owned = 1U;
    if (HAL_ADC_Stop(&hadc1) != HAL_OK) return G02_FAULT_ADC;
    hadc1.Init.ExternalTrigConv = ADC_EXTERNALTRIG_T1_TRGO;
    hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_RISING;
    if (HAL_ADC_Init(&hadc1) != HAL_OK || HAL_ADC_Start_IT(&hadc1) != HAL_OK)
        return G02_FAULT_ADC;
    /* Same preemption priority serializes telemetry writers. ADC may run before
     * update ISR; the two service counts are intentionally NOT paired by index. */
    HAL_NVIC_SetPriority(TIM1_UP_IRQn, 0U, 0U);
    HAL_NVIC_SetPriority(ADC1_2_IRQn, 0U, 0U);
    HAL_NVIC_ClearPendingIRQ(TIM1_UP_IRQn);
    HAL_NVIC_EnableIRQ(TIM1_UP_IRQn);
    return 0U;
}
static uint32_t enable(void *ctx, G02Mode mode)
{
    (void)ctx;
    if (interlock()) return G02_FAULT_INTERLOCK;
    if (HAL_RCCEx_GetTIMGFreq() != g02_telemetry.tim_hz) return G02_FAULT_CLOCK;
    if (mode == G02_MODE_PINS) {
        if (!G02_ALLOW_PIN_OUTPUT) return G02_FAULT_CONFIG;
        /* Configure AF with MOE=0; both CC2 channels prepared in one write. */
        SET_BIT(TIM1->BDTR, TIM_BDTR_OSSI | TIM_BDTR_OSSR);
        CLEAR_BIT(TIM1->CR2, TIM_CR2_OIS2 | TIM_CR2_OIS2N);
        HAL_TIM_MspPostInit(&htim1);
        TIM1->CCER = TIM_CCER_CC2E | TIM_CCER_CC2NE;
    }
    TIM1->SR = 0U;
    TIM1->DIER = TIM_DIER_UIE;
    g02_telemetry.start_ms = HAL_GetTick();
    g02_telemetry.start_cycles = cycles();
    timer_running = 1U;
    /* CEN first keeps both off at MOE=0; one MOE write releases the pair. */
    SET_BIT(TIM1->CR1, TIM_CR1_CEN);
    if (mode == G02_MODE_PINS) SET_BIT(TIM1->BDTR, TIM_BDTR_MOE);
    return 0U;
}
static uint32_t write_compare(void *ctx, uint32_t compare)
{
    (void)ctx;
    if (interlock()) return G02_FAULT_INTERLOCK;
    /* Leave the timer/trigger schedule untouched. Wait for TWO serviced UEVs
     * after writing: the first could already have been pending before this
     * write. This records a conservative observation bound, not active-CCR
     * readback or a measured physical output edge. Scope remains mandatory. */
    TIM1->CCR2 = compare;
    ++g02_telemetry.ccr_writes;
    g02_telemetry.ccr_requested = compare;
    g02_telemetry.ccr_write_cycles = cycles();
    ccr_pending = 2U;
    trace(G02_EVENT_CCR);
    return 0U;
}
static uint32_t cleanup(void *ctx)
{
    (void)ctx;
    HAL_NVIC_DisableIRQ(TIM1_UP_IRQn);
    HAL_NVIC_ClearPendingIRQ(TIM1_UP_IRQn);
    if (!adc_owned) return 0U;
    if (HAL_ADC_Stop_IT(&hadc1) != HAL_OK) return G02_FAULT_ADC;
    hadc1.Init = saved_adc;
    if (HAL_ADC_Init(&hadc1) != HAL_OK) return G02_FAULT_ADC;
    adc_owned = 0U;
    return 0U;
}
static const G02Ops ops = {enter, leave, allow_mode, prepare, enable, off, write_compare, cleanup};

void G02_PortInit(void)
{
    G02_EmergencyOff();
    g02_command = G02_CMD_NONE;
    (void)G02_Init(&g02_control, &ops, 0, 2000U);
}
void G02_CPUFault(void)
{
    G02_EmergencyOff();
    if (g02_control.initialized) G02_Fault(&g02_control, G02_FAULT_CPU);
}
int G02_MeasurementAllowed(void)
{
    return !adc_owned && !G02_OwnsADC(&g02_control);
}
void G02_Task(void)
{
    uint32_t command = g02_command, requested_window = g02_window_ms;
    g02_command = G02_CMD_NONE;
    (void)G02_Service(&g02_control);
    switch (command) {
    case G02_CMD_NONE: break;
    case G02_CMD_SAMPLE:
    case G02_CMD_PINS:
        if(G03_BlocksG02()){g02_command_result=G02_BUSY;break;}
        if (requested_window == 0U || requested_window > G02_MAX_WINDOW_MS) {
            g02_command_result = G02_BAD_ARGUMENT; break;
        }
        g02_command_result = G02_Start(&g02_control,
            command == G02_CMD_SAMPLE ? G02_MODE_SAMPLING : G02_MODE_PINS, g02_compare);
        if (g02_command_result == G02_OK) window_ms = requested_window;
        break;
    case G02_CMD_STOP: G02_Stop(&g02_control); g02_command_result = G02_OK; break;
    case G02_CMD_FAULT: G02_Fault(&g02_control, G02_FAULT_INJECTED); g02_command_result = G02_OK; break;
    case G02_CMD_CLEAR: g02_command_result = G02_ClearFault(&g02_control); break;
    case G02_CMD_COMPARE: g02_command_result = G02_SetCompare(&g02_control, g02_compare); break;
    default: g02_command_result = G02_BAD_ARGUMENT; break;
    }
    if (g02_control.state == G02_STATE_RUNNING &&
        (uint32_t)(HAL_GetTick() - g02_telemetry.start_ms) >= window_ms)
        G02_Stop(&g02_control);
    (void)G02_Service(&g02_control);
}
void G02_TIM1_IRQHandler(void)
{
    uint32_t start = cycles(), delta;
    if (!(TIM1->SR & TIM_SR_UIF) || !(TIM1->DIER & TIM_DIER_UIE)) return;
    TIM1->SR = ~TIM_SR_UIF;
    if (!timer_running) return;
    ++g02_telemetry.update_irqs;
    if (g02_telemetry.update_irqs > 1U) {
        delta = start - last_update_cycles;
        maximum(&g02_telemetry.update_gap_max_cycles, delta);
        if (delta > g02_telemetry.cpu_hz / 100000U * 3U / 2U)
            ++g02_telemetry.late_update_irqs;
    }
    last_update_cycles = start;
    if (ccr_pending && --ccr_pending == 0U) {
        g02_telemetry.ccr_next_uev_observed = g02_telemetry.ccr_requested;
        g02_telemetry.ccr_observed_cycles = start;
    }
    trace(G02_EVENT_UPDATE);
    if (interlock()) G02_Fault(&g02_control, G02_FAULT_INTERLOCK);
    /* A conversion may be in flight or its IRQ pending; two observations of
     * slack avoid assuming ISR order. Persistent missing completion is fatal. */
    if (g02_telemetry.update_irqs > g02_telemetry.adc_completions + 2U)
        G02_Fault(&g02_control, G02_FAULT_TIMING);
    maximum(&g02_telemetry.update_isr_max_cycles, cycles() - start);
}
int G02_ADC_IRQHandler(void)
{
    uint32_t start, overrun;
    if (!adc_owned) return 0;
    start = cycles(); overrun = ADC1->ISR & ADC_FLAG_OVR;
    if (overrun) ++g02_telemetry.overruns;
    HAL_ADC_IRQHandler(&hadc1);
    if (overrun) G02_Fault(&g02_control, G02_FAULT_OVERRUN);
    maximum(&g02_telemetry.adc_isr_max_cycles, cycles() - start);
    return 1;
}
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc != &hadc1 || !adc_owned) return;
    g02_telemetry.last_adc_raw = HAL_ADC_GetValue(hadc);
    ++g02_telemetry.adc_completions;
    g02_telemetry.adc_counter = TIM1->CNT;
    g02_telemetry.adc_down = (TIM1->CR1 & TIM_CR1_DIR) != 0U;
    trace(G02_EVENT_ADC);
}
void HAL_ADC_ErrorCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc != &hadc1 || !adc_owned) return;
    ++g02_telemetry.adc_errors;
    G02_Fault(&g02_control, G02_FAULT_ADC);
}
