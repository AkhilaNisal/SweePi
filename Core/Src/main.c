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
#include "adc.h"
#include "i2c.h"
#include "tim.h"
#include "usart.h"
#include "usb_device.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define PI 3.14159265f
#define WHEEL_RADIUS_M 0.033f // assume 3.3cm radius wheels, adjust as necessary
#define WHEEL_BASE_M 0.200f // assume 20cm distance between wheels, adjust as necessary
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

// --- KINEMATICS ---
float target_linear_mps = 0.2f;   // Set this in Watch Window (Forward/Back)
float target_angular_rads = 0.1f; // Set this in Watch Window (Turning)

float target_velocity_mps_L = 0.0f; // Now calculated dynamically
float target_velocity_mps_R = 0.0f; // Now calculated dynamically

// --- ENCODERS ---
uint16_t current_ticks_L = 0, previous_ticks_L = 0;
int16_t tick_diff_L = 0;
float current_rpm_L = 0.0f;

uint16_t current_ticks_R = 0, previous_ticks_R = 0;
int16_t tick_diff_R = 0;
float current_rpm_R = 0.0f;

// --- PID CONTROLLERS ---
typedef struct {
    float Kp;
    float Ki;
    float Kd;
    float setpoint; // Target RPM
    float integral;
    float prev_error;
} PID_Controller;

// Initialized with your tuned Kp=25.0, Ki=0.5
PID_Controller leftPID  = {25.0f, 0.5f, 0.0f, 0.0f, 0.0f, 0.0f};
PID_Controller rightPID = {25.0f, 0.5f, 0.0f, 0.0f, 0.0f, 0.0f};

float current_pwm_L = 0.0f;
float current_pwm_R = 0.0f;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
float PID_Compute(PID_Controller *pid, float current_rpm);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

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
  MX_I2C1_Init();
  MX_I2C3_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  MX_TIM4_Init();
  MX_USART2_UART_Init();
  MX_USB_Device_Init();
  MX_ADC2_Init();



/* USER CODE BEGIN 2 */
  // --- Left Motor PWM (Channels 3 & 4) ---
  __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, 0);
  __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);

  // --- Right Motor PWM (Channels 1 & 2) ---
  __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0);
  __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0);
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);

  // Enable Master Output and the Motor Driver Chip
  __HAL_TIM_MOE_ENABLE(&htim1); 
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2, GPIO_PIN_SET);

  // --- Start Both Hardware Encoders ---
  HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL); // Left
  HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL); // Right
/* USER CODE END 2 */

  /* Infinite loop */

/* USER CODE BEGIN WHILE */
  while (1)
  {
// 1. Differential Drive Kinematics
    target_velocity_mps_L = target_linear_mps - (target_angular_rads * (WHEEL_BASE_M / 2.0f));
    target_velocity_mps_R = target_linear_mps + (target_angular_rads * (WHEEL_BASE_M / 2.0f));

    // 2. Convert to Target RPM
    leftPID.setpoint = (target_velocity_mps_L * 60.0f) / (2.0f * PI * WHEEL_RADIUS_M);
    
    // TEMPORARY GHOST WHEEL LOCK: Keep Right Motor asleep until hardware is plugged in!
    rightPID.setpoint = 0.0f; 
    // UNCOMMENT LATER: rightPID.setpoint = (target_velocity_mps_R * 60.0f) / (2.0f * PI * WHEEL_RADIUS_M);

    // 2. Read Hardware Timers (TIM2 = Left, TIM4 = Right)
    current_ticks_L = __HAL_TIM_GET_COUNTER(&htim2);
    current_ticks_R = __HAL_TIM_GET_COUNTER(&htim4);

    // 3. Calculate Deltas
    tick_diff_L = (int16_t)(current_ticks_L - previous_ticks_L);
    previous_ticks_L = current_ticks_L;
    
    tick_diff_R = (int16_t)(current_ticks_R - previous_ticks_R);
    previous_ticks_R = current_ticks_R;

    // 4. Calculate Real-World RPM
    current_rpm_L = ((float)tick_diff_L * 600.0f) / 7392.0f;
    current_rpm_R = ((float)tick_diff_R * 600.0f) / 7392.0f;

    // 5. SAFETY SWITCH & PID LOGIC
    if (HAL_GPIO_ReadPin(CHECK_BUTTON_GPIO_Port, CHECK_BUTTON_Pin) == GPIO_PIN_RESET) 
    {
        // --- LEFT MOTOR ---
        current_pwm_L += PID_Compute(&leftPID, current_rpm_L);
        if (current_pwm_L > 4799.0f) current_pwm_L = 4799.0f;
        if (current_pwm_L < 0.0f) current_pwm_L = 0.0f; 
        
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, (uint32_t)current_pwm_L);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);

        // --- RIGHT MOTOR ---
        current_pwm_R += PID_Compute(&rightPID, current_rpm_R);
        if (current_pwm_R > 4799.0f) current_pwm_R = 4799.0f;
        if (current_pwm_R < 0.0f) current_pwm_R = 0.0f; 
        
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, (uint32_t)current_pwm_R);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0);
    } 
    else 
    {
        // --- BRAKES ON ---
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, 0);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);
        
        // Reset PID Memory
        current_pwm_L = 0.0f; leftPID.integral = 0.0f; leftPID.prev_error = 0.0f;
        current_pwm_R = 0.0f; rightPID.integral = 0.0f; rightPID.prev_error = 0.0f;
    }

    // 6. Strictly timed 100ms calculation window
    HAL_Delay(100);
    
  /* USER CODE END WHILE */
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
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV2;
  RCC_OscInitStruct.PLL.PLLN = 8;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */
float PID_Compute(PID_Controller *pid, float current_rpm) {
    float error = pid->setpoint - current_rpm;
    
    pid->integral += error * 0.1f; // 100ms loop time
    // Anti-Windup
    if (pid->integral > 100.0f) pid->integral = 100.0f;
    if (pid->integral < -100.0f) pid->integral = -100.0f;
    
    float derivative = (error - pid->prev_error) / 0.1f;
    pid->prev_error = error;
    
    return (pid->Kp * error) + (pid->Ki * pid->integral) + (pid->Kd * derivative);
}
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
#ifdef USE_FULL_ASSERT
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
