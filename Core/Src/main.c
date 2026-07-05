/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
/*
  STM32G474RET6 PCB servo pins:

  PC6 = TIM3_CH1 = Left tendon servo
  PC7 = TIM3_CH2 = Right tendon servo
  PC8 = TIM3_CH3 = spare
  PC9 = TIM3_CH4 = spare
*/

#define LEFT_SERVO_CHANNEL       TIM_CHANNEL_1
#define RIGHT_SERVO_CHANNEL      TIM_CHANNEL_2
#define SERVO_3_CHANNEL          TIM_CHANNEL_3
#define SERVO_4_CHANNEL          TIM_CHANNEL_4

/*
  Safe first-test pulse range.
  1500 us = center.
  1400/1600 = small tendon movement.

  Do NOT start with 1000 and 2000 on the real arm.
*/

#define LEFT_CENTER_PULSE        1500U
#define RIGHT_CENTER_PULSE       1500U

#define ARM_LEFT_LEFT_PULSE      1600U
#define ARM_LEFT_RIGHT_PULSE     1400U

#define ARM_RIGHT_LEFT_PULSE     1400U
#define ARM_RIGHT_RIGHT_PULSE    1600U

#define SERVO_STEP_US            2U
#define SERVO_STEP_DELAY_MS      25U
#define ARM_HOLD_DELAY_MS        500U

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
TIM_HandleTypeDef htim3;

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_TIM3_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
static uint32_t left_servo_pulse = LEFT_CENTER_PULSE;
static uint32_t right_servo_pulse = RIGHT_CENTER_PULSE;

static void SetLeftServo(uint32_t pulse)
{
  __HAL_TIM_SET_COMPARE(&htim3, LEFT_SERVO_CHANNEL, pulse);
}

static void SetRightServo(uint32_t pulse)
{
  __HAL_TIM_SET_COMPARE(&htim3, RIGHT_SERVO_CHANNEL, pulse);
}

static void SetArmServos(uint32_t left_pulse, uint32_t right_pulse)
{
  SetLeftServo(left_pulse);
  SetRightServo(right_pulse);
}

static uint32_t StepToward(uint32_t current, uint32_t target)
{
  if (current < target)
  {
    current += SERVO_STEP_US;

    if (current > target)
    {
      current = target;
    }
  }
  else if (current > target)
  {
    if (current > SERVO_STEP_US)
    {
      current -= SERVO_STEP_US;
    }

    if (current < target)
    {
      current = target;
    }
  }

  return current;
}

static void MoveArmSmooth(uint32_t target_left_pulse, uint32_t target_right_pulse)
{
  while ((left_servo_pulse != target_left_pulse) ||
         (right_servo_pulse != target_right_pulse))
  {
    left_servo_pulse = StepToward(left_servo_pulse, target_left_pulse);
    right_servo_pulse = StepToward(right_servo_pulse, target_right_pulse);

    SetArmServos(left_servo_pulse, right_servo_pulse);

    HAL_Delay(SERVO_STEP_DELAY_MS);
  }
}

static void ArmCenter(void)
{
  MoveArmSmooth(LEFT_CENTER_PULSE, RIGHT_CENTER_PULSE);
}

static void ArmLeft(void)
{
  MoveArmSmooth(ARM_LEFT_LEFT_PULSE, ARM_LEFT_RIGHT_PULSE);
}

static void ArmRight(void)
{
  MoveArmSmooth(ARM_RIGHT_LEFT_PULSE, ARM_RIGHT_RIGHT_PULSE);
}

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_TIM3_Init();
  /* USER CODE BEGIN 2 */
  HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1);  // PC6 - left servo
  HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_2);  // PC7 - right servo
  HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_3);  // PC8 - spare
  HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_4);  // PC9 - spare

  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, LEFT_CENTER_PULSE);
  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_2, RIGHT_CENTER_PULSE);
  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_3, 1500U);
  __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_4, 1500U);

  HAL_Delay(1000);

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    ArmCenter();
    HAL_Delay(ARM_HOLD_DELAY_MS);

    ArmLeft();
    HAL_Delay(ARM_HOLD_DELAY_MS);

    ArmCenter();
    HAL_Delay(ARM_HOLD_DELAY_MS);

    ArmRight();
    HAL_Delay(ARM_HOLD_DELAY_MS);

    ArmCenter();
    HAL_Delay(ARM_HOLD_DELAY_MS);
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_0) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief TIM3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM3_Init(void)
{

  /* USER CODE BEGIN TIM3_Init 0 */

  /* USER CODE END TIM3_Init 0 */

  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM3_Init 1 */

  /* USER CODE END TIM3_Init 1 */
  htim3.Instance = TIM3;
  htim3.Init.Prescaler = 15;
  htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim3.Init.Period = 19999;
  htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_PWM_Init(&htim3) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 1500;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim3, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim3, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim3, &sConfigOC, TIM_CHANNEL_3) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim3, &sConfigOC, TIM_CHANNEL_4) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM3_Init 2 */

  /* USER CODE END TIM3_Init 2 */
  HAL_TIM_MspPostInit(&htim3);

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
/* USER CODE BEGIN MX_GPIO_Init_1 */
/* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();

/* USER CODE BEGIN MX_GPIO_Init_2 */
/* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
