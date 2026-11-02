#ifndef TEST_G02_MAIN_H
#define TEST_G02_MAIN_H
#include <stdint.h>

/* Deliberately small register model: verifies software writes/callbacks, not
 * timer/ADC silicon timing. BSRR side effects are applied at barriers/HAL calls;
 * timer flags, CNT, conversion events and elapsed time are test inputs. */
typedef struct { volatile uint32_t CR1, CR2, DIER, SR, EGR, CCMR1, CCER,
    CNT, PSC, ARR, RCR, CCR2, BDTR; } TIM_TypeDef;
typedef struct { volatile uint32_t MODER, OTYPER, ODR, BSRR; } GPIO_TypeDef;
typedef struct { volatile uint32_t ISR, DR, IER, CR, CFGR1, CFGR2, CALFACT, DIFSEL, GCOMP, OFR1, SQR1, SMPR1, PCSEL; } ADC_TypeDef;
typedef struct { volatile uint32_t CTRL, CYCCNT; } DWT_TypeDef;
typedef struct { volatile uint32_t DEMCR; } CoreDebug_Type;
typedef struct { uint32_t ExternalTrigConv, ExternalTrigConvEdge;
    uint32_t preserved_configuration, OversamplingMode;
    struct { uint32_t Ratio,RightBitShift; } Oversampling; } ADC_InitTypeDef;
typedef struct { ADC_TypeDef *Instance; ADC_InitTypeDef Init; } ADC_HandleTypeDef;
typedef struct { TIM_TypeDef *Instance; } TIM_HandleTypeDef;
typedef enum { HAL_OK, HAL_ERROR, HAL_BUSY, HAL_TIMEOUT } HAL_StatusTypeDef;
extern TIM_TypeDef test_tim;
extern TIM_TypeDef test_tim2;
#define TIM2 (&test_tim2)
#define TIM2_IRQn 114U
extern GPIO_TypeDef test_gpio_a, test_gpio_b, test_gpio_f, test_gpio_g;
extern ADC_TypeDef test_adc;
extern DWT_TypeDef test_dwt;
extern CoreDebug_Type test_core_debug;
extern uint32_t test_clock_mask, test_primask;
#define TIM1 (&test_tim)
#define GPIOA (&test_gpio_a)
#define GPIOB (&test_gpio_b)
#define GPIOF (&test_gpio_f)
#define GPIOG (&test_gpio_g)
#define ADC1 (&test_adc)
#define DWT (&test_dwt)
#define CoreDebug (&test_core_debug)
#define __HAL_RCC_TIM1_IS_CLK_ENABLED() (test_clock_mask & 1U)
#define __HAL_RCC_GPIOA_IS_CLK_ENABLED() (test_clock_mask & 2U)
#define __HAL_RCC_GPIOB_IS_CLK_ENABLED() (test_clock_mask & 4U)
#define __HAL_RCC_GPIOF_IS_CLK_ENABLED() (test_clock_mask & 8U)
#define __HAL_RCC_GPIOG_IS_CLK_ENABLED() (test_clock_mask & 16U)
/* In center-aligned mode DIR is read-only. Route register helper writes through
 * this model so restart tests catch attempts to clear DIR before leaving CMS. */
void test_register_write(volatile uint32_t *reg, uint32_t value);
#define CLEAR_BIT(REG, BIT) test_register_write(&(REG), (REG) & ~(BIT))
#define SET_BIT(REG, BIT) test_register_write(&(REG), (REG) | (BIT))
#define MODIFY_REG(REG, MASK, VALUE) test_register_write(&(REG), ((REG) & ~(MASK)) | (VALUE))
#define __get_PRIMASK() (test_primask)
#define __disable_irq() (test_primask = 1U)
#define __set_PRIMASK(value) (test_primask = (value))
void test_barrier(void);
#define __DSB() test_barrier()
#define __ISB() test_barrier()
#define TIM_CR1_CEN (1U << 0)
#define TIM_CR1_UDIS (1U << 1)
#define TIM_CR1_URS (1U << 2)
#define TIM_CR1_DIR (1U << 4)
#define TIM_CR1_CMS (3U << 5)
#define TIM_CR1_ARPE (1U << 7)
#define TIM_CR1_CKD (3U << 8)
#define TIM_COUNTERMODE_CENTERALIGNED1 (1U << 5)
#define TIM_CLOCKDIVISION_DIV1 0U
#define TIM_CR2_MMS (7U << 4)
#define TIM_CR2_OIS2 (1U << 10)
#define TIM_CR2_OIS2N (1U << 11)
#define TIM_TRGO_ENABLE (1U << 4)
#define TIM_TRGO_UPDATE (2U << 4)
#define TIM_DIER_UIE 1U
#define TIM_SR_UIF 1U
#define TIM_EGR_UG 1U
#define TIM_CCMR1_OC2PE (1U << 11)
#define TIM_CCMR1_OC2M (7U << 12)
#define TIM_OCMODE_PWM1 (6U << 4)
#define TIM_CCER_CC2E (1U << 4)
#define TIM_CCER_CC2NE (1U << 6)
#define TIM_BDTR_DTG 255U
#define TIM_BDTR_OSSI (1U << 10)
#define TIM_BDTR_OSSR (1U << 11)
#define TIM_BDTR_AOE (1U << 14)
#define TIM_BDTR_MOE (1U << 15)
#define GPIO_PIN_5 (1U << 5)
#define GPIO_PIN_7 (1U << 7)
#define GPIO_PIN_9 (1U << 9)
#define SWS_Relay_Pin GPIO_PIN_5
#define SWL_Relay_Pin GPIO_PIN_5
#define SWS_Relay_GPIO_Port GPIOB
#define SWL_Relay_GPIO_Port GPIOG
#define CoreDebug_DEMCR_TRCENA_Msk (1U << 24)
#define DWT_CTRL_CYCCNTENA_Msk 1U
#define DWT_CTRL_NOCYCCNT_Msk (1U << 25)
#define ADC_SOFTWARE_START 0U
#define ADC_EXTERNALTRIGCONVEDGE_NONE 0U
#define ADC_EXTERNALTRIG_T1_TRGO 9U
#define ADC_EXTERNALTRIGCONVEDGE_RISING 1U
#define ADC_FLAG_OVR (1U << 4)
#define RCC_PERIPHCLK_ADC 1U
#define TIM1_UP_IRQn 113U
#define ADC1_2_IRQn 46U
uint32_t HAL_GetTick(void);
uint32_t HAL_RCC_GetCpuClockFreq(void);
uint32_t HAL_RCCEx_GetTIMGFreq(void);
uint32_t HAL_RCCEx_GetPeriphCLKFreq(uint32_t peripheral);
HAL_StatusTypeDef HAL_ADC_Stop(ADC_HandleTypeDef *adc);
HAL_StatusTypeDef HAL_ADC_Init(ADC_HandleTypeDef *adc);
HAL_StatusTypeDef HAL_ADC_Start_IT(ADC_HandleTypeDef *adc);
HAL_StatusTypeDef HAL_ADC_Stop_IT(ADC_HandleTypeDef *adc);
void HAL_ADC_IRQHandler(ADC_HandleTypeDef *adc);
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *adc);
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *adc);
void HAL_ADC_ErrorCallback(ADC_HandleTypeDef *adc);
void HAL_TIM_MspPostInit(TIM_HandleTypeDef *timer);
void HAL_NVIC_SetPriority(uint32_t irq, uint32_t priority, uint32_t subpriority);
void HAL_NVIC_ClearPendingIRQ(uint32_t irq);
void HAL_NVIC_EnableIRQ(uint32_t irq);
void HAL_NVIC_DisableIRQ(uint32_t irq);

typedef struct { uint32_t CCR; } ADC_Common_TypeDef;
extern ADC_Common_TypeDef test_adc_common;
#define ADC12_COMMON (&test_adc_common)
typedef struct { uint32_t WatchdogNumber,WatchdogMode,Channel,ITMode,LowThreshold,HighThreshold,FilteringConfig; } ADC_AnalogWDGConfTypeDef;
#define ENABLE 1U
#define DISABLE 0U
#define ADC_CR_ADSTART 4U
#define ADC_CR_ADSTP 16U
#define ADC_FLAG_EOC 4U
#define ADC_FLAG_EOS 8U
#define ADC_FLAG_AWD1 128U
#define ADC_ANALOGWATCHDOG_1 1U
#define ADC_ANALOGWATCHDOG_NONE 0U
#define ADC_ANALOGWATCHDOG_SINGLE_REG 1U
#define ADC_AWD_FILTERING_NONE 0U
#define ADC_CHANNEL_1 1U
#define ADC_RIGHTBITSHIFT_1 1U
#define ADC_SINGLE_ENDED 0U
#define HAL_ADC_ERROR_NONE 0U
HAL_StatusTypeDef HAL_ADC_Start(ADC_HandleTypeDef *h);
HAL_StatusTypeDef HAL_ADC_PollForConversion(ADC_HandleTypeDef *h,uint32_t timeout);
uint32_t HAL_ADC_GetError(ADC_HandleTypeDef *h);
HAL_StatusTypeDef HAL_ADCEx_Calibration_Start(ADC_HandleTypeDef *h,uint32_t diff);
HAL_StatusTypeDef HAL_ADC_AnalogWDGConfig(ADC_HandleTypeDef *h,ADC_AnalogWDGConfTypeDef *w);
void HAL_Delay(uint32_t ms);

#endif

#define ADC_IT_AWD1 128U
