#ifndef PWM_PORT_FIXTURE_MAIN_H
#define PWM_PORT_FIXTURE_MAIN_H
/* Offline register model. C++ conversions model DR pop/W1C side effects while
 * compiling the production adapter source unchanged; Keil checks actual C. */
#include <stdint.h>
#include <stddef.h>
#define G02_PORT_H
#define G03_PORT_H
#define G03_ADC_PORT_H
#define G03_RELAY_PORT_H
#define G02_ALLOW_PIN_OUTPUT 0
enum RegKind { NORMAL, ADC_CR_REG, ADC_ISR_REG, ADC_DR_REG, TIM1_CR1_REG,
               TIM1_CCER_REG, TIM1_BDTR_REG, GPIO_B_ODR, GPIO_G_ODR,
               GPIO_A_ODR, GPIO_F_ODR };
struct Reg {
    uint32_t value=0; RegKind kind=NORMAL;
    operator uint32_t() const;
    Reg &operator=(uint32_t next);
    Reg &operator|=(uint32_t bits){return *this=value|bits;}
    Reg &operator&=(uint32_t bits){return *this=value&bits;}
};
struct TIM_TypeDef {Reg CR1,CR2,DIER,SR,PSC,ARR,CNT,EGR,CCMR1,CCER,CCR1,CCR2,RCR,BDTR;};
struct ADC_TypeDef {Reg CR,ISR,IER,SQR1,SMPR1,SMPR2,PCSEL,CFGR1,CFGR2,AWD1LTR,AWD1HTR,CALFACT,DR;};
struct GPIO_TypeDef {Reg ODR,BSRR,MODER,OTYPER,AFR[2];};
extern TIM_TypeDef model_tim1,model_tim2;
extern ADC_TypeDef model_adc1,model_adc2;
#define ADC2 (&model_adc2)
extern GPIO_TypeDef model_gpioa,model_gpiob,model_gpiof,model_gpiog;
#define TIM1 (&model_tim1)
#define TIM2 (&model_tim2)
#define ADC1 (&model_adc1)
#define GPIOA (&model_gpioa)
#define GPIOB (&model_gpiob)
#define GPIOF (&model_gpiof)
#define GPIOG (&model_gpiog)
#define SWS_Relay_Pin (1U<<5)
#define SWL_Relay_Pin (1U<<5)
#define GPIO_PIN_9 (1U<<9)
#define GPIO_PIN_7 (1U<<7)
#define TIM_BDTR_MOE (1U<<15)
#define TIM_BDTR_AOE (1U<<14)
#define TIM_BDTR_DTG 255U
#define TIM_CR1_CEN 1U
#define TIM_CR1_CMS (3U<<5)
#define TIM_CR1_DIR (1U<<4)
#define TIM_CR1_UDIS (1U<<1)
#define TIM_CR1_URS (1U<<2)
#define TIM_COUNTERMODE_CENTERALIGNED1 (1U<<5)
#define TIM_CR2_MMS (7U<<4)
#define TIM_TRGO_ENABLE (1U<<4)
#define TIM_TRGO_UPDATE (2U<<4)
#define TIM_EGR_UG 1U
#define TIM_DIER_CC1IE 2U
#define TIM_SR_CC1IF 2U
#define ADC_CR_ADEN 1U
#define ADC_CR_ADDIS 2U
#define ADC_CR_ADSTART 4U
#define ADC_CR_ADSTP 16U
#define ADC_CR_ADCAL (1U<<31)
#define ADC_FLAG_EOC 4U
#define ADC_FLAG_EOS 8U
#define ADC_FLAG_OVR 16U
#define ADC_FLAG_AWD1 128U
#define ADC_IT_EOC ADC_FLAG_EOC
#define ADC_IT_EOS ADC_FLAG_EOS
#define ADC_IT_OVR ADC_FLAG_OVR
#define ADC_IT_AWD1 ADC_FLAG_AWD1
#define ADC_SOFTWARE_START 0U
#define ADC_EXTERNALTRIGCONVEDGE_NONE 0U
#define ADC_EXTERNALTRIGCONVEDGE_RISING (1U<<10)
#define ADC_EXTERNALTRIG_T1_TRGO 0x480U
#define ADC_SCAN_DISABLE 0U
#define ADC_RIGHTBITSHIFT_1 32U
#define ADC_CHANNEL_1 1U
#define ADC_REGULAR_RANK_1 1U
#define ADC_SAMPLETIME_6CYCLES_5 2U
#define ADC_SAMPLETIME_11CYCLES_5 3U
#define ADC_SINGLE_ENDED 0U
#define ADC_OFFSET_NONE 0U
#define ADC_ANALOGWATCHDOG_1 1U
#define ADC_ANALOGWATCHDOG_SINGLE_REG 1U
#define ADC_AWD_FILTERING_NONE 0U
#define RCC_PERIPHCLK_ADC 1U
#define ENABLE 1U
#define HAL_OK 0
#define HAL_ERROR 1
#define HAL_TIMEOUT 2
#define G02_DISALLOWED 6U
#define SET_BIT(reg,bits) ((reg)|=(bits))
#define CLEAR_BIT(reg,bits) ((reg)&=~(uint32_t)(bits))
#define MODIFY_REG(reg,clear,set) ((reg)=((uint32_t)(reg)&~(uint32_t)(clear))|(uint32_t)(set))
enum IRQn {TIM2_IRQn=0,ADC1_2_IRQn=1,TIM1_UP_IRQn=2};
struct ADC_OversamplingTypeDef {uint32_t Ratio,RightBitShift;};
struct ADC_InitTypeDef {uint32_t ExternalTrigConv,ExternalTrigConvEdge,NbrOfConversion,ScanConvMode,OversamplingMode,EOCSelection;ADC_OversamplingTypeDef Oversampling;};
struct ADC_HandleTypeDef {ADC_InitTypeDef Init;};
struct ADC_ChannelConfTypeDef {uint32_t Channel,Rank,SamplingTime,SingleDiff,OffsetNumber;};
struct ADC_AnalogWDGConfTypeDef {uint32_t WatchdogNumber,WatchdogMode,Channel,ITMode,LowThreshold,HighThreshold,FilteringConfig;};
struct G02Control {uint32_t faults;};
extern G02Control g02_control;
extern ADC_HandleTypeDef hadc1;
uint32_t __get_PRIMASK(void);
void __disable_irq(void);
void __set_PRIMASK(uint32_t);
void __NOP(void);
void __DSB(void);
void G02_EmergencyOff(void);
int G02_OwnsADC(G02Control *);
int G03_RelayBusy(void);
void G03_RelayTask(void);
int G03_ADC_BlocksOthers(void);
int G03_SyntheticBusy(void);
uint32_t HAL_RCCEx_GetTIMGFreq(void);
uint32_t HAL_RCCEx_GetPeriphCLKFreq(uint32_t);
void HAL_NVIC_SetPriority(IRQn,uint32_t,uint32_t);
void HAL_NVIC_ClearPendingIRQ(IRQn);
void HAL_NVIC_EnableIRQ(IRQn);
void HAL_NVIC_DisableIRQ(IRQn);
uint32_t NVIC_GetPriority(IRQn);
uint32_t NVIC_GetEnableIRQ(IRQn);
void NVIC_SetPriority(IRQn,uint32_t);
void NVIC_EnableIRQ(IRQn);
void NVIC_DisableIRQ(IRQn);
int HAL_ADC_Stop(ADC_HandleTypeDef *);
int HAL_ADC_Stop_IT(ADC_HandleTypeDef *);
int HAL_ADC_Init(ADC_HandleTypeDef *);
int HAL_ADC_ConfigChannel(ADC_HandleTypeDef *,ADC_ChannelConfTypeDef *);
int HAL_ADC_Start(ADC_HandleTypeDef *);
int HAL_ADC_Start_IT(ADC_HandleTypeDef *);
int HAL_ADC_PollForConversion(ADC_HandleTypeDef *,uint32_t);
uint32_t HAL_ADC_GetError(ADC_HandleTypeDef *);
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *);
int HAL_ADC_AnalogWDGConfig(ADC_HandleTypeDef *,ADC_AnalogWDGConfTypeDef *);
void HAL_Delay(uint32_t);

#define ADC_EOC_SINGLE_CONV 0U
#define ADC_CHANNEL_0 0U
#define ADC_CHANNEL_14 14U
#define ADC_CHANNEL_11 11U
#define DISABLE 0U
#define TIM_CCER_CC2E 16U
#define TIM_CCER_CC2NE 64U
#define TIM_CCMR1_OC2M (7U<<12)
#define TIM_CCMR1_OC2PE (1U<<11)
#define TIM_OCMODE_PWM1 (6U<<4)
#define TIM_BDTR_OSSI (1U<<10)
#define TIM_BDTR_OSSR (1U<<11)
#define TIM_CR2_OIS2 (1U<<10)
#define TIM_CR2_OIS2N (1U<<11)
uint32_t HAL_GetTick(void);
#endif

