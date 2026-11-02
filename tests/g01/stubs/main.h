#ifndef G01_TEST_MAIN_H
#define G01_TEST_MAIN_H
#include <stdint.h>
typedef struct {int unused;} SPI_HandleTypeDef;
typedef struct {int unused;} ADC_HandleTypeDef;
typedef enum {HAL_OK,HAL_ERROR,HAL_BUSY,HAL_TIMEOUT} HAL_StatusTypeDef;
#define GPIO_PIN_SET 1
#define GPIO_PIN_RESET 0
#define ADBMS_CS_GPIO_Port 1
#define ADBMS_CS_Pin 6
#define HAL_ADC_ERROR_NONE 0U
void HAL_GPIO_WritePin(int port,int pin,int value);
void HAL_Delay(uint32_t ms);
uint32_t HAL_GetTick(void);
HAL_StatusTypeDef HAL_SPI_TransmitReceive(SPI_HandleTypeDef *,uint8_t *,uint8_t *,uint16_t,uint32_t);
HAL_StatusTypeDef HAL_ADC_Start(ADC_HandleTypeDef *);
HAL_StatusTypeDef HAL_ADC_PollForConversion(ADC_HandleTypeDef *,uint32_t);
uint32_t HAL_ADC_GetValue(ADC_HandleTypeDef *);
uint32_t HAL_ADC_GetError(ADC_HandleTypeDef *);
HAL_StatusTypeDef HAL_ADC_Stop(ADC_HandleTypeDef *);
#endif
