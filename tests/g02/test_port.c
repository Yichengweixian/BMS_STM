#include "main.h"
#include "g02_port.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

TIM_TypeDef test_tim;
GPIO_TypeDef test_gpio_a, test_gpio_b, test_gpio_f, test_gpio_g;
ADC_TypeDef test_adc;
DWT_TypeDef test_dwt;
CoreDebug_Type test_core_debug;
ADC_HandleTypeDef hadc1;
TIM_HandleTypeDef htim1;
uint32_t test_clock_mask = 31U, test_primask;
static uint32_t tick, timer_hz = 400000000U, adc_hz = 64000000U;
static unsigned adc_started, stop_calls, start_calls, post_init_calls;
static int fail_start, fail_stop, fail_init, fail_cleanup, callback_error;
static int stop_during_prepare, fault_during_prepare;

void test_register_write(volatile uint32_t *reg, uint32_t value)
{
    if (reg == &TIM1->CR1 && (TIM1->CR1 & TIM_CR1_CMS))
        value = (value & ~TIM_CR1_DIR) | (TIM1->CR1 & TIM_CR1_DIR);
    *reg = value;
}
static void apply_bsrr(GPIO_TypeDef *gpio)
{
    gpio->ODR = (gpio->ODR | (gpio->BSRR & 0xffffU)) & ~(gpio->BSRR >> 16);
    gpio->BSRR = 0U;
}
void test_barrier(void)
{
    apply_bsrr(GPIOA); apply_bsrr(GPIOB); apply_bsrr(GPIOF); apply_bsrr(GPIOG);
    if (DWT->CTRL & DWT_CTRL_CYCCNTENA_Msk) DWT->CYCCNT += 4U;
}
uint32_t HAL_GetTick(void) { return tick; }
uint32_t HAL_RCC_GetCpuClockFreq(void) { return 800000000U; }
uint32_t HAL_RCCEx_GetTIMGFreq(void) { return timer_hz; }
uint32_t HAL_RCCEx_GetPeriphCLKFreq(uint32_t peripheral)
{ assert(peripheral == RCC_PERIPHCLK_ADC); return adc_hz; }
HAL_StatusTypeDef HAL_ADC_Stop(ADC_HandleTypeDef *adc)
{
    assert(adc == &hadc1 && test_primask == 0U);
    ++stop_calls;
    if (fail_stop) return HAL_ERROR;
    adc_started = 0;
    return HAL_OK;
}
HAL_StatusTypeDef HAL_ADC_Init(ADC_HandleTypeDef *adc)
{
    assert(adc == &hadc1 && test_primask == 0U);
    return fail_init ? HAL_ERROR : HAL_OK;
}
HAL_StatusTypeDef HAL_ADC_Start_IT(ADC_HandleTypeDef *adc)
{
    assert(adc == &hadc1 && test_primask == 0U);
    if(adc->Init.ExternalTrigConv==ADC_SOFTWARE_START){
        ++start_calls;adc_started=1;return fail_start?HAL_ERROR:HAL_OK;
    }
    assert(!(TIM1->CR1 & TIM_CR1_CEN) && !(TIM1->BDTR & TIM_BDTR_MOE));
    assert(TIM1->CCER == 0U && TIM1->EGR == TIM_EGR_UG && TIM1->SR == 0U);
    assert(!(TIM1->CR1 & TIM_CR1_DIR));
    assert((TIM1->CR1 & TIM_CR1_CMS) == TIM_COUNTERMODE_CENTERALIGNED1);
    assert(adc->Init.ExternalTrigConv == ADC_EXTERNALTRIG_T1_TRGO);
    assert(adc->Init.ExternalTrigConvEdge == ADC_EXTERNALTRIGCONVEDGE_RISING);
    ++start_calls;
    if (stop_during_prepare) G02_Stop(&g02_control);
    if (fault_during_prepare) G02_Fault(&g02_control, G02_FAULT_INJECTED);
    if (fail_start) return HAL_ERROR;
    adc_started = 1;
    return HAL_OK;
}
HAL_StatusTypeDef HAL_ADC_Stop_IT(ADC_HandleTypeDef *adc)
{
    assert(adc == &hadc1 && test_primask == 0U);
    if (fail_cleanup) return HAL_ERROR;
    adc_started = 0;
    return HAL_OK;
}
void HAL_ADC_IRQHandler(ADC_HandleTypeDef *adc)
{
    assert(adc == &hadc1);
    if ((ADC1->ISR & ADC_FLAG_OVR) || callback_error) HAL_ADC_ErrorCallback(adc);
    else HAL_ADC_ConvCpltCallback(adc);
    ADC1->ISR = 0U;
}
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *adc)
{ assert(adc == &hadc1); return ADC1->DR; }
void HAL_TIM_MspPostInit(TIM_HandleTypeDef *timer)
{
    assert(timer == &htim1 && test_primask == 1U);
    assert(!(TIM1->BDTR & TIM_BDTR_MOE));
    assert(!(TIM1->CR1 & TIM_CR1_CEN));
    ++post_init_calls;
    MODIFY_REG(GPIOA->MODER, 3U << 18, 2U << 18);
    MODIFY_REG(GPIOF->MODER, 3U << 14, 2U << 14);
}
void HAL_NVIC_SetPriority(uint32_t irq, uint32_t priority, uint32_t subpriority)
{ (void)irq; (void)priority; (void)subpriority; }
void HAL_NVIC_ClearPendingIRQ(uint32_t irq) { (void)irq; }
void HAL_NVIC_EnableIRQ(uint32_t irq) { (void)irq; }
void HAL_NVIC_DisableIRQ(uint32_t irq) { (void)irq; }

static void assert_off(void)
{
    assert(!(TIM1->BDTR & (TIM_BDTR_MOE | TIM_BDTR_AOE)));
    assert(!(TIM1->CR1 & TIM_CR1_CEN));
    assert(TIM1->DIER == 0U && TIM1->CCER == 0U);
    assert((GPIOA->MODER & (3U << 18)) == (1U << 18));
    assert((GPIOF->MODER & (3U << 14)) == (1U << 14));
    assert(!(GPIOA->ODR & GPIO_PIN_9) && !(GPIOF->ODR & GPIO_PIN_7));
    assert(!(GPIOB->ODR & GPIO_PIN_5) && !(GPIOG->ODR & GPIO_PIN_5));
}
static void restore_and_clear(void)
{
    fail_start = fail_stop = fail_init = fail_cleanup = callback_error = 0;
    stop_during_prepare = fault_during_prepare = 0;
    timer_hz = 400000000U; adc_hz = 64000000U;
    assert(G02_Service(&g02_control) == G02_OK);
    assert(G02_ClearFault(&g02_control) == G02_OK);
    assert_off();
    assert(G02_MeasurementAllowed());
    assert(!adc_started);
    assert(g02_control.state == G02_STATE_STOPPED);
    assert(hadc1.Init.ExternalTrigConv == ADC_SOFTWARE_START);
    assert(hadc1.Init.ExternalTrigConvEdge == ADC_EXTERNALTRIGCONVEDGE_NONE);
    assert(hadc1.Init.preserved_configuration == 0x12345678U);
}
static void start_sample(void)
{
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_OK);
    assert(g02_control.state == G02_STATE_RUNNING);
    assert(TIM1->CR1 & TIM_CR1_CEN);
    assert(!(TIM1->BDTR & TIM_BDTR_MOE) && TIM1->CCER == 0U);
    assert(adc_started && !G02_MeasurementAllowed());
}
static void update_event(void)
{
    DWT->CYCCNT += 8000U;
    TIM1->SR = TIM_SR_UIF;
    G02_TIM1_IRQHandler();
}
int main(void)
{
    /* Earliest fault path tolerates clocks off and does not enter HAL. */
    test_clock_mask = 0U;
    G02_CPUFault();
    assert(!g02_control.initialized && !stop_calls);
    test_clock_mask = 31U;
    TIM1->BDTR = TIM_BDTR_MOE | TIM_BDTR_AOE;
    TIM1->CR1 = TIM_CR1_CEN;
    TIM1->CCER = TIM_CCER_CC2E | TIM_CCER_CC2NE;
    GPIOA->ODR = GPIO_PIN_9; GPIOF->ODR = GPIO_PIN_7;
    GPIOB->ODR = GPIO_PIN_5; GPIOG->ODR = GPIO_PIN_5;
    G02_CPUFault();
    assert_off();
    TIM1->ARR = 2000U; TIM1->RCR = 1U;
    TIM1->CR1 = TIM_COUNTERMODE_CENTERALIGNED1 | TIM_CR1_ARPE;
    TIM1->CCMR1 = (TIM_OCMODE_PWM1 << 8) | TIM_CCMR1_OC2PE;
    hadc1.Instance = ADC1;
    hadc1.Init.preserved_configuration = 0x12345678U;
    htim1.Instance = TIM1;
    G02_PortInit();
    assert_off(); assert(G02_MeasurementAllowed());
    G02_Task(); assert_off(); assert(start_calls == 0U);

#if G02_ALLOW_PIN_OUTPUT
    assert(G02_Start(&g02_control, G02_MODE_PINS, 1000U) == G02_OK);
    assert(post_init_calls == 1U);
    assert(TIM1->CCER == (TIM_CCER_CC2E | TIM_CCER_CC2NE));
    assert(TIM1->BDTR & TIM_BDTR_MOE);
    G02_Stop(&g02_control); assert_off(); restore_and_clear();
#else
    assert(G02_Start(&g02_control, G02_MODE_PINS, 1000U) == G02_DISALLOWED);
    assert_off(); assert(post_init_calls == 0U && start_calls == 0U);
#endif

    /* Restart from the down-counting half: CMS must be exited before DIR can
     * be cleared. The model rejects DIR writes while CMS is still selected. */
    TIM1->CR1 |= TIM_CR1_DIR;
    CLEAR_BIT(TIM1->CR1, TIM_CR1_DIR);
    assert(TIM1->CR1 & TIM_CR1_DIR); /* Verify the read-only model itself. */
    start_sample();
    assert(!(TIM1->CR1 & TIM_CR1_DIR));
    assert(TIM1->CCR2 == 1000U);
    update_event();
    ADC1->DR = 2345U;
    assert(G02_ADC_IRQHandler() == 1);
    assert(g02_telemetry.adc_completions == 1U && g02_telemetry.last_adc_raw == 2345U);
    assert(G02_SetCompare(&g02_control, 1200U) == G02_OK);
    assert(TIM1->CCR2 == 1200U && g02_telemetry.ccr_writes == 1U);
    update_event();
    assert(g02_telemetry.ccr_next_uev_observed == 0U);
    (void)G02_ADC_IRQHandler();
    update_event();
    assert(g02_telemetry.ccr_next_uev_observed == 1200U);
    G02_Stop(&g02_control); assert_off();
    assert(!G02_MeasurementAllowed()); /* ADC cleanup is deferred from STOP. */
    G02_Stop(&g02_control); assert_off(); restore_and_clear();
    assert(G02_ADC_IRQHandler() == 0);

    /* Bad clock/config and raised relay output cannot open either channel. */
    timer_hz = 200000000U;
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert(g02_control.faults & G02_FAULT_CLOCK); assert_off(); restore_and_clear();
    TIM1->PSC = 1U;
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert(g02_control.faults & G02_FAULT_CONFIG); assert_off(); TIM1->PSC = 0U; restore_and_clear();
    GPIOB->ODR = GPIO_PIN_5;
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert(g02_control.faults & G02_FAULT_INTERLOCK); assert_off(); restore_and_clear();

    /* Three consecutive UEV services without any completion exceed the
     * two-event software guard. This is loss detection, not real ADC timing. */
    start_sample();
    update_event(); update_event();
    assert(g02_control.state == G02_STATE_RUNNING);
    update_event();
    assert(g02_control.faults & G02_FAULT_TIMING);
    assert(g02_control.state == G02_STATE_FAULT); assert_off();
    G02_Stop(&g02_control); assert_off();
    assert(g02_control.faults & G02_FAULT_TIMING);
    assert(G02_Service(&g02_control) == G02_OK);
    assert(g02_control.state == G02_STATE_FAULT);
    G02_Task(); assert_off();
    assert(g02_control.state == G02_STATE_FAULT);
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    restore_and_clear();
    G02_Task(); assert_off();
    assert(g02_control.state == G02_STATE_STOPPED);

    /* Start failures and an IRQ stop/fault during preparation never reach CEN. */
    fail_start = 1;
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert_off(); restore_and_clear();
    fail_stop = 1;
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert_off(); restore_and_clear();
    fail_init = 1;
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert_off(); restore_and_clear();
    stop_during_prepare = 1;
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_CANCELED);
    assert_off(); restore_and_clear();
    fault_during_prepare = 1;
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    assert(g02_control.faults & G02_FAULT_INJECTED); assert_off(); restore_and_clear();

    /* OVR, ADC error and runtime relay changes all latch an immediate stop. */
    start_sample(); ADC1->ISR = ADC_FLAG_OVR;
    assert(G02_ADC_IRQHandler() == 1);
    assert(g02_telemetry.overruns == 1U && g02_telemetry.adc_errors == 1U);
    assert(g02_control.faults & G02_FAULT_OVERRUN); assert_off();
    assert(G02_Start(&g02_control, G02_MODE_SAMPLING, 1000U) == G02_FAULTED);
    restore_and_clear();
    start_sample(); callback_error = 1; (void)G02_ADC_IRQHandler();
    assert(g02_control.faults & G02_FAULT_ADC); assert_off(); restore_and_clear();
    start_sample(); GPIOG->ODR = GPIO_PIN_5; update_event();
    assert(g02_control.faults & G02_FAULT_INTERLOCK); assert_off(); restore_and_clear();

    /* A failed cleanup retains ADC ownership and prevents rearming/clearing. */
    start_sample(); G02_Stop(&g02_control); fail_cleanup = 1;
    assert(G02_Service(&g02_control) == G02_FAULTED);
    assert(!G02_MeasurementAllowed());
    assert(G02_ClearFault(&g02_control) == G02_NOT_READY);
    assert_off(); restore_and_clear();

    /* CPU fault latches; repeated init cannot clear it. */
    start_sample(); G02_CPUFault(); assert_off();
    assert(g02_control.faults & G02_FAULT_CPU);
    G02_PortInit(); assert(g02_control.faults & G02_FAULT_CPU);
    restore_and_clear();

    /* Mailbox validation and bounded observation window (main-loop observed). */
    g02_window_ms = 0U; g02_command = G02_CMD_SAMPLE; G02_Task();
    assert(g02_command_result == G02_BAD_ARGUMENT); assert_off();
    g02_window_ms = 5U; g02_command = G02_CMD_SAMPLE; G02_Task();
    assert(g02_command_result == G02_OK && g02_control.state == G02_STATE_RUNNING);
    tick += 5U; G02_Task(); assert_off(); assert(G02_MeasurementAllowed());
    /* A rejected busy Start must not modify the active one-second deadline. */
    g02_window_ms = 1000U; g02_command = G02_CMD_SAMPLE; G02_Task();
    assert(g02_command_result == G02_OK);
    tick += 100U;
    g02_window_ms = 10000U; g02_command = G02_CMD_SAMPLE; G02_Task();
    assert(g02_command_result == G02_BUSY);
    tick += 900U; G02_Task();
    assert_off(); assert(G02_MeasurementAllowed());
    assert(g02_control.state == G02_STATE_STOPPED);
    assert(test_primask == 0U);
    puts("PASS: production G02 port/register model; default gate, pair release (if enabled), ADC ownership, callbacks, failures, cancellation, cleanup and stop. Simulation only.");
    return 0;
}
