/* Static decoding cross-check only. No entry point, I/O or hardware actions.
 * Compile against the project's own STM32N647 HAL/CMSIS headers. */
#include "stm32n6xx_hal.h"

_Static_assert(ADC_EXTERNALTRIG_T1_TRGO == 0x480u, "TIM1 TRGO encoding");
_Static_assert(ADC_EXTERNALTRIGCONVEDGE_RISING == 0x400u, "rising edge");
_Static_assert(ADC_SAMPLETIME_6CYCLES_5 == 2u, "6.5 cycles");
_Static_assert(ADC_SAMPLETIME_11CYCLES_5 == 3u, "11.5 cycles");
_Static_assert(ADC_SINGLE_ENDED == 0x3ffu, "single ended");
_Static_assert(ADC_REGULAR_RANK_1 == 6u, "rank1 field position");
_Static_assert(ADC_REGULAR_RANK_2 == 12u, "rank2 field position");
_Static_assert(ADC_EOC_SEQ_CONV == 8u, "EOS selection");
_Static_assert(ADC_OVR_DATA_PRESERVED == 0u, "FIFO enabled preserved mode");
_Static_assert(ADC_ANALOGWATCHDOG_1 == 0x7dc00000u, "AWD1 encoding");
_Static_assert(ADC_ANALOGWATCHDOG_SINGLE_REG == 0xc00000u, "single regular channel");
_Static_assert(ADC_AWD_FILTERING_8SAMPLES == 0xe0000000u, "8 sample filter");
_Static_assert(TIM_COUNTERMODE_CENTERALIGNED1 == 0x20u, "center aligned mode1");
_Static_assert(TIM_OCMODE_PWM1 == 0x60u, "PWM1 mode");
_Static_assert(TIM_OCNIDLESTATE_SET == 0x200u, "complementary idle state");
_Static_assert(TIM_AUTOMATICOUTPUT_ENABLE == 0x4000u, "AOE bit");
_Static_assert(TIM_TRGO_UPDATE == 0x20u, "update TRGO");
_Static_assert(TIM_CHANNEL_2 == 4u, "channel2 HAL encoding");
