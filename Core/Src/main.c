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
#include <string.h>
#include <stdio.h>

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define PI 3.14159265f
#define WHEEL_RADIUS_M 0.0615f // assume 6.15cm radius wheels, adjust as necessary
#define WHEEL_BASE_M 0.29f // assume 29cm distance between wheels, adjust as necessary
#define MOTOR_TEST_ENABLE 0
#define MOTOR_TEST_LEFT_RPM 15.0f
#define MOTOR_TEST_RIGHT_RPM 15.0f
#define LEFT_ENCODER_SIGN -1
#define RIGHT_ENCODER_SIGN 1
#define ENCODER_TICKS_PER_REV 7392.0f 
#define PWM_MAX_COUNT 4799.0f
#define CONTROL_LOOP_MS 20U
#define CONTROL_LOOP_SEC ((float)CONTROL_LOOP_MS / 1000.0f)
#define COMMAND_TIMEOUT_MS 500U
#define GYRO_DPS_TO_RAD_PER_SEC (PI / 180.0f)
#define LEFT_SERVO_CHANNEL TIM_CHANNEL_1
#define RIGHT_SERVO_CHANNEL TIM_CHANNEL_3
#define SERVO_NEUTRAL_US 1500U
#define SERVO_LEFT_RELEASE_US 1650U
#define SERVO_LEFT_TIGHTEN_US 1350U
#define SERVO_RIGHT_RELEASE_US 1650U
#define SERVO_RIGHT_TIGHTEN_US 1350U
#define SERVO_STEP_US 10U     // Step size in microseconds for each control loop iteration
#define SERVO_HOLD_MS 300U   // Hold time in milliseconds at each extreme position
#define SERVO_CYCLES 3U      // Number of complete left-right cycles to perform when triggered
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
uint8_t mpu6050_address = 0;
uint8_t mpu6050_ready = 0;

// --- IMU RAW VARIABLES ---
int16_t raw_acc_x = 0, raw_acc_y = 0, raw_acc_z = 0;
int16_t raw_gyro_x = 0, raw_gyro_y = 0, raw_gyro_z = 0;

// --- IMU CALIBRATION VARIABLES (Gyros Only!) ---
int32_t gyro_x_offset = 0, gyro_y_offset = 0, gyro_z_offset = 0;

// --- ASCII COMMUNICATION PROTOCOL ---
char rx_line_buffer[128]; // Holds the incoming string
volatile uint8_t rx_byte;          // Holds a single character
volatile uint8_t rx_index = 0;
volatile uint8_t new_cmd_ready = 0;
char tx_buffer[256];      // Holds the outgoing FB string

// Command Variables from Pi
uint32_t cmd_seq = 0;
uint32_t fb_seq = 0;
uint32_t last_valid_cmd_ms = 0;
float cmd_left_vel = 0.0f;
float cmd_right_vel = 0.0f;
uint8_t motor_enable = 0;

// --- ENCODERS ---
uint16_t current_ticks_L = 0, previous_ticks_L = 0;
int16_t tick_diff_L = 0;
float current_rpm_L = 0.0f;

uint16_t current_ticks_R = 0, previous_ticks_R = 0;
int16_t tick_diff_R = 0;
float current_rpm_R = 0.0f;

// --- PID CONTROLLERS ---
typedef struct {
    float Kp; float Ki; float Kd;
    float setpoint; float integral; float prev_error;
} PID_Controller;

typedef enum {
    SERVO_IDLE = 0,
    SERVO_MOVE_LEFT,
    SERVO_HOLD_LEFT,
    SERVO_CENTER_AFTER_LEFT,
    SERVO_HOLD_CENTER_AFTER_LEFT,
    SERVO_MOVE_RIGHT,
    SERVO_HOLD_RIGHT,
    SERVO_CENTER_AFTER_RIGHT,
    SERVO_HOLD_CENTER_AFTER_RIGHT
} TubeServoState;

PID_Controller leftPID  = {25.0f, 0.5f, 0.0f, 0.0f, 0.0f, 0.0f};
PID_Controller rightPID = {25.0f, 0.5f, 0.0f, 0.0f, 0.0f, 0.0f};

float current_pwm_L = 0.0f;
float current_pwm_R = 0.0f;

uint32_t left_servo_pulse = SERVO_NEUTRAL_US;
uint32_t right_servo_pulse = SERVO_NEUTRAL_US;
TubeServoState tube_servo_state = SERVO_IDLE;
uint8_t tube_servo_cycle_count = 0;
uint32_t tube_servo_hold_start_ms = 0;
uint8_t tube_trigger_latched = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
float PID_Compute(PID_Controller *pid, float current_rpm, float dt_sec);
void UInt64ToDec(uint64_t value, char *buffer, size_t buffer_size);
void TubeServo_Set(uint32_t left_pulse, uint32_t right_pulse);
uint32_t TubeServo_StepToward(uint32_t current, uint32_t target);
uint8_t TubeServo_MoveToward(uint32_t target_left, uint32_t target_right);
void TubeServo_StartCycle(void);
void TubeServo_Update(uint32_t now_ms);
uint8_t ModeEquals(const char *mode, const char *expected);
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

  // --- Tube servos on TIM3 (PC6 = left, PC8 = right) ---
  TubeServo_Set(SERVO_NEUTRAL_US, SERVO_NEUTRAL_US);
  HAL_TIM_PWM_Start(&htim3, LEFT_SERVO_CHANNEL);
  HAL_TIM_PWM_Start(&htim3, RIGHT_SERVO_CHANNEL);

  // Enable Master Output and the Motor Driver Chip
  __HAL_TIM_MOE_ENABLE(&htim1); 
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1|GPIO_PIN_2, GPIO_PIN_SET);

  // --- Start Both Hardware Encoders ---
  HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL); // Left
  HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL); // Right


  // Start listening on USART2 for the first character
  HAL_UART_Receive_IT(&huart2, (uint8_t *)&rx_byte, 1);

  // Standalone power-up marker for serial/debug checks.
  HAL_UART_Transmit(&huart2, (uint8_t *)"BOOT\r\n", 6, 100);

  // --- Give the MPU6050 time to wake up! ---
  HAL_Delay(800); 
  
  // --- Step 1: I2C Sanity Check Scanner ---
  HAL_StatusTypeDef result;
  
  for (uint8_t i = 1; i < 128; i++)
  {
      result = HAL_I2C_IsDeviceReady(&hi2c3, (uint16_t)(i << 1), 2, 10);
      
      if (result == HAL_OK)
      {
          if ((i == 0x68) || (i == 0x69))
          {
              mpu6050_address = i;
              break;
          }
      }
  }

  // --- Step 2: Wake up the MPU6050 ---
  // The MPU6050 boots in Sleep Mode. Write 0x00 to register 0x6B to wake it up!
  if (mpu6050_address != 0)
  {
      uint8_t wake_data = 0x00;
      if (HAL_I2C_Mem_Write(&hi2c3, (uint16_t)(mpu6050_address << 1), 0x6B, 1, &wake_data, 1, 10) == HAL_OK)
      {
          mpu6050_ready = 1;
      }
  }

  // --- Step 3: Calibrate MPU6050 Gyroscopes ---
  // DO NOT MOVE THE ROBOT DURING THIS 1 SECOND WINDOW!
  if (mpu6050_ready == 1)
  {
      int32_t sum_gx = 0, sum_gy = 0, sum_gz = 0;
      uint8_t calib_buf[6]; 
      const uint16_t num_samples = 500;

      for (uint16_t i = 0; i < num_samples; i++)
      {
          // Register 0x43 is where the Gyro data starts
          if (HAL_I2C_Mem_Read(&hi2c3, (uint16_t)(mpu6050_address << 1), 0x43, 1, calib_buf, 6, 10) == HAL_OK)
          {
              sum_gx += (int16_t)((calib_buf[0] << 8) | calib_buf[1]);
              sum_gy += (int16_t)((calib_buf[2] << 8) | calib_buf[3]);
              sum_gz += (int16_t)((calib_buf[4] << 8) | calib_buf[5]);
          }
          HAL_Delay(2); 
      }
      
      // Calculate the average offsets
      gyro_x_offset = sum_gx / num_samples;
      gyro_y_offset = sum_gy / num_samples;
      gyro_z_offset = sum_gz / num_samples;
  }

  // --- Manual motor test mode ---
  // Change MOTOR_TEST_LEFT_RPM / MOTOR_TEST_RIGHT_RPM above for bench testing.
  // The CHECK_BUTTON safety switch must still be pressed for PWM output.
  if (MOTOR_TEST_ENABLE != 0)
  {
      motor_enable = 1;
      leftPID.setpoint = MOTOR_TEST_LEFT_RPM;
      rightPID.setpoint = MOTOR_TEST_RIGHT_RPM;
  }

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    static uint32_t last_loop_start_ms = 0U;
    uint32_t loop_start_ms = HAL_GetTick();
    float dt_sec = CONTROL_LOOP_SEC;

    if (last_loop_start_ms != 0U)
    {
        uint32_t dt_ms = loop_start_ms - last_loop_start_ms;
        if ((dt_ms > 0U) && (dt_ms <= COMMAND_TIMEOUT_MS))
        {
            dt_sec = (float)dt_ms / 1000.0f;
        }
    }
    last_loop_start_ms = loop_start_ms;

    // --- 0. ASCII PROTOCOL PARSER (Pi -> STM32 over USART2) ---
#if MOTOR_TEST_ENABLE == 0
    if (new_cmd_ready != 0)
    {
        unsigned long parsed_seq = 0;
        unsigned long parsed_time_ms = 0;
        float parsed_left_vel = 0.0f;
        float parsed_right_vel = 0.0f;
        unsigned int parsed_motor_enable = 0;
        unsigned int parsed_suction_enable = 0;
        unsigned int parsed_brush_enable = 0;
        char mode[16] = {0};

        if (sscanf(rx_line_buffer,
                   "CMD,%lu,%lu,%f,%f,%u,%u,%u,%15[^,\r\n]",
                   &parsed_seq,
                   &parsed_time_ms,
                   &parsed_left_vel,
                   &parsed_right_vel,
                   &parsed_motor_enable,
                   &parsed_suction_enable,
                   &parsed_brush_enable,
                   mode) >= 5)
        {
            cmd_seq = (uint32_t)parsed_seq;
            cmd_left_vel = parsed_left_vel;
            cmd_right_vel = parsed_right_vel;
            motor_enable = (parsed_motor_enable != 0U) ? 1U : 0U;
            last_valid_cmd_ms = HAL_GetTick();

            // Pi sends wheel linear velocity in m/s. PID setpoint is wheel RPM.
            leftPID.setpoint = (cmd_left_vel * 60.0f) / (2.0f * PI * WHEEL_RADIUS_M);
            rightPID.setpoint = (cmd_right_vel * 60.0f) / (2.0f * PI * WHEEL_RADIUS_M);

            if (ModeEquals(mode, "HIGH") || ModeEquals(mode, "TUBE"))
            {
                if (tube_trigger_latched == 0U)
                {
                    TubeServo_StartCycle();
                    tube_trigger_latched = 1U;
                }
            }
            else
            {
                tube_trigger_latched = 0U;
            }
        }

        new_cmd_ready = 0;
    }
#else
    if (new_cmd_ready != 0)
    {
        new_cmd_ready = 0;
    }
#endif

#if MOTOR_TEST_ENABLE == 0
    if ((motor_enable != 0U) && ((HAL_GetTick() - last_valid_cmd_ms) > COMMAND_TIMEOUT_MS))
    {
        motor_enable = 0U;
        leftPID.setpoint = 0.0f;
        rightPID.setpoint = 0.0f;
    }
#endif

    TubeServo_Update(loop_start_ms);

    // --- 1. Read All 6 MPU6050 Axes ---
    uint8_t i2c_buf[14]; 
    
    // Read 14 bytes starting from register 0x3B (ACCEL_XOUT_H)
    if ((mpu6050_ready != 0) && (HAL_I2C_Mem_Read(&hi2c3, (uint16_t)(mpu6050_address << 1), 0x3B, 1, i2c_buf, 14, 10) == HAL_OK))
    {
        // Accel Data
        raw_acc_x = (int16_t)((i2c_buf[0] << 8) | i2c_buf[1]);
        raw_acc_y = (int16_t)((i2c_buf[2] << 8) | i2c_buf[3]);
        raw_acc_z = (int16_t)((i2c_buf[4] << 8) | i2c_buf[5]);
        
        // i2c_buf[6] and [7] are the Temperature sensor (Ignored)
        
        // Gyro Data
        raw_gyro_x = (int16_t)((i2c_buf[8] << 8)  | i2c_buf[9]);
        raw_gyro_y = (int16_t)((i2c_buf[10] << 8) | i2c_buf[11]);
        raw_gyro_z = (int16_t)((i2c_buf[12] << 8) | i2c_buf[13]);
    }

    // --- 2. Read Hardware Timers & Deltas ---
    current_ticks_L = __HAL_TIM_GET_COUNTER(&htim2);
    current_ticks_R = __HAL_TIM_GET_COUNTER(&htim4);

    tick_diff_L = (int16_t)(LEFT_ENCODER_SIGN * (int16_t)(current_ticks_L - previous_ticks_L));
    previous_ticks_L = current_ticks_L;
    
    tick_diff_R = (int16_t)(RIGHT_ENCODER_SIGN * (int16_t)(current_ticks_R - previous_ticks_R));
    previous_ticks_R = current_ticks_R;

    current_rpm_L = ((float)tick_diff_L * 60.0f) / (ENCODER_TICKS_PER_REV * dt_sec);
    current_rpm_R = ((float)tick_diff_R * 60.0f) / (ENCODER_TICKS_PER_REV * dt_sec);

    // --- 3. SAFETY SWITCH & PID LOGIC ---
    // Change this line to look for SET instead of RESET!
    if (motor_enable == 1) 
    {
	        current_pwm_L += PID_Compute(&leftPID, current_rpm_L, dt_sec);
	        if (current_pwm_L > PWM_MAX_COUNT) current_pwm_L = PWM_MAX_COUNT;
	        if (current_pwm_L < -PWM_MAX_COUNT) current_pwm_L = -PWM_MAX_COUNT;
	        
	        if (current_pwm_L >= 0.0f)
	        {
	            __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, (uint32_t)current_pwm_L);
	            __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);
	        }
	        else
	        {
	            __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, 0);
	            __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, (uint32_t)(-current_pwm_L));
	        }
	        
	        current_pwm_R += PID_Compute(&rightPID, current_rpm_R, dt_sec);
	        if (current_pwm_R > PWM_MAX_COUNT) current_pwm_R = PWM_MAX_COUNT;
	        if (current_pwm_R < -PWM_MAX_COUNT) current_pwm_R = -PWM_MAX_COUNT;
	        
	        if (current_pwm_R >= 0.0f)
	        {
	            __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, (uint32_t)current_pwm_R);
	            __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0);
	        }
	        else
	        {
	            __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0);
	            __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, (uint32_t)(-current_pwm_R));
	        }
    } 
    else 
    {
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, 0);
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);
        current_pwm_L = 0.0f; leftPID.integral = 0.0f; leftPID.prev_error = 0.0f;
        current_pwm_R = 0.0f; rightPID.integral = 0.0f; rightPID.prev_error = 0.0f;
    }

    // --- 4. ASCII PROTOCOL FEEDBACK (Pi Telemetry) ---
    
    // Apply gyro offsets and convert to rad/s.
    float gx = ((float)(raw_gyro_x - gyro_x_offset) / 131.0f) * GYRO_DPS_TO_RAD_PER_SEC;
    float gy = ((float)(raw_gyro_y - gyro_y_offset) / 131.0f) * GYRO_DPS_TO_RAD_PER_SEC;
    float gz = ((float)(raw_gyro_z - gyro_z_offset) / 131.0f) * GYRO_DPS_TO_RAD_PER_SEC;

    // Convert Accel to m/s^2 (Standard config is +/- 2g -> /16384.0, then * 9.81 gravity)
    float ax = ((float)raw_acc_x / 16384.0f) * 9.81f;
    float ay = ((float)raw_acc_y / 16384.0f) * 9.81f;
    float az = ((float)raw_acc_z / 16384.0f) * 9.81f;

    uint32_t fb_seq_out = fb_seq;
    uint64_t stm_time_us = ((uint64_t)HAL_GetTick()) * 1000ULL;
    char stm_time_us_text[21];

    fb_seq = (fb_seq + 1U) % 1000000U;
    UInt64ToDec(stm_time_us, stm_time_us_text, sizeof(stm_time_us_text));

    snprintf(tx_buffer, sizeof(tx_buffer),
             "FB,%lu,%s,%d,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,12.0,0,OK\r\n",
             (unsigned long)fb_seq_out,
             stm_time_us_text,
             tick_diff_L,
             tick_diff_R,
             gx,
             gy,
             gz,
             ax,
             ay,
             az);
    if (huart2.gState == HAL_UART_STATE_READY)
    {
        HAL_UART_Transmit_IT(&huart2, (uint8_t*)tx_buffer, strlen(tx_buffer));
    }

    // --- 5. Keep the full loop close to 50 Hz, compensating for work time ---
    uint32_t elapsed_ms = HAL_GetTick() - loop_start_ms;
    if (elapsed_ms < CONTROL_LOOP_MS)
    {
        HAL_Delay(CONTROL_LOOP_MS - elapsed_ms);
    }
    
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
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
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV2;
  RCC_OscInitStruct.PLL.PLLN = 12;
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
void TubeServo_Set(uint32_t left_pulse, uint32_t right_pulse)
{
    left_servo_pulse = left_pulse;
    right_servo_pulse = right_pulse;
    __HAL_TIM_SET_COMPARE(&htim3, LEFT_SERVO_CHANNEL, left_servo_pulse);
    __HAL_TIM_SET_COMPARE(&htim3, RIGHT_SERVO_CHANNEL, right_servo_pulse);
}

uint32_t TubeServo_StepToward(uint32_t current, uint32_t target)
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
        if ((current - target) < SERVO_STEP_US)
        {
            current = target;
        }
        else
        {
            current -= SERVO_STEP_US;
        }
    }

    return current;
}

uint8_t TubeServo_MoveToward(uint32_t target_left, uint32_t target_right)
{
    uint32_t next_left = TubeServo_StepToward(left_servo_pulse, target_left);
    uint32_t next_right = TubeServo_StepToward(right_servo_pulse, target_right);

    TubeServo_Set(next_left, next_right);

    return ((left_servo_pulse == target_left) && (right_servo_pulse == target_right)) ? 1U : 0U;
}

void TubeServo_StartCycle(void)
{
    if (tube_servo_state == SERVO_IDLE)
    {
        tube_servo_cycle_count = 0U;
        tube_servo_state = SERVO_MOVE_LEFT;
    }
}

void TubeServo_Update(uint32_t now_ms)
{
    switch (tube_servo_state)
    {
        case SERVO_IDLE:
            break;

        case SERVO_MOVE_LEFT:
            if (TubeServo_MoveToward(SERVO_LEFT_RELEASE_US, SERVO_RIGHT_TIGHTEN_US) != 0U)
            {
                tube_servo_hold_start_ms = now_ms;
                tube_servo_state = SERVO_HOLD_LEFT;
            }
            break;

        case SERVO_HOLD_LEFT:
            if ((now_ms - tube_servo_hold_start_ms) >= SERVO_HOLD_MS)
            {
                tube_servo_state = SERVO_CENTER_AFTER_LEFT;
            }
            break;

        case SERVO_CENTER_AFTER_LEFT:
            if (TubeServo_MoveToward(SERVO_NEUTRAL_US, SERVO_NEUTRAL_US) != 0U)
            {
                tube_servo_hold_start_ms = now_ms;
                tube_servo_state = SERVO_HOLD_CENTER_AFTER_LEFT;
            }
            break;

        case SERVO_HOLD_CENTER_AFTER_LEFT:
            if ((now_ms - tube_servo_hold_start_ms) >= SERVO_HOLD_MS)
            {
                tube_servo_state = SERVO_MOVE_RIGHT;
            }
            break;

        case SERVO_MOVE_RIGHT:
            if (TubeServo_MoveToward(SERVO_LEFT_TIGHTEN_US, SERVO_RIGHT_RELEASE_US) != 0U)
            {
                tube_servo_hold_start_ms = now_ms;
                tube_servo_state = SERVO_HOLD_RIGHT;
            }
            break;

        case SERVO_HOLD_RIGHT:
            if ((now_ms - tube_servo_hold_start_ms) >= SERVO_HOLD_MS)
            {
                tube_servo_state = SERVO_CENTER_AFTER_RIGHT;
            }
            break;

        case SERVO_CENTER_AFTER_RIGHT:
            if (TubeServo_MoveToward(SERVO_NEUTRAL_US, SERVO_NEUTRAL_US) != 0U)
            {
                tube_servo_hold_start_ms = now_ms;
                tube_servo_state = SERVO_HOLD_CENTER_AFTER_RIGHT;
            }
            break;

        case SERVO_HOLD_CENTER_AFTER_RIGHT:
            if ((now_ms - tube_servo_hold_start_ms) >= SERVO_HOLD_MS)
            {
                tube_servo_cycle_count++;
                if (tube_servo_cycle_count >= SERVO_CYCLES)
                {
                    tube_servo_state = SERVO_IDLE;
                }
                else
                {
                    tube_servo_state = SERVO_MOVE_LEFT;
                }
            }
            break;

        default:
            tube_servo_state = SERVO_IDLE;
            TubeServo_Set(SERVO_NEUTRAL_US, SERVO_NEUTRAL_US);
            break;
    }
}

uint8_t ModeEquals(const char *mode, const char *expected)
{
    while ((*mode != '\0') && (*expected != '\0'))
    {
        char mode_char = *mode;
        char expected_char = *expected;

        if ((mode_char >= 'a') && (mode_char <= 'z'))
        {
            mode_char = (char)(mode_char - ('a' - 'A'));
        }

        if ((expected_char >= 'a') && (expected_char <= 'z'))
        {
            expected_char = (char)(expected_char - ('a' - 'A'));
        }

        if (mode_char != expected_char)
        {
            return 0U;
        }

        mode++;
        expected++;
    }

    return ((*mode == '\0') && (*expected == '\0')) ? 1U : 0U;
}

void UInt64ToDec(uint64_t value, char *buffer, size_t buffer_size)
{
    char reversed[20];
    size_t reversed_len = 0U;
    size_t out_len = 0U;

    if (buffer_size == 0U)
    {
        return;
    }

    if (value == 0ULL)
    {
        buffer[0] = '0';
        if (buffer_size > 1U)
        {
            buffer[1] = '\0';
        }
        return;
    }

    while ((value > 0ULL) && (reversed_len < sizeof(reversed)))
    {
        reversed[reversed_len++] = (char)('0' + (value % 10ULL));
        value /= 10ULL;
    }

    while ((reversed_len > 0U) && (out_len < (buffer_size - 1U)))
    {
        buffer[out_len++] = reversed[--reversed_len];
    }

    buffer[out_len] = '\0';
}

float PID_Compute(PID_Controller *pid, float current_rpm, float dt_sec) {
    float error = pid->setpoint - current_rpm;
    
    pid->integral += error * dt_sec;
    // Anti-Windup
    if (pid->integral > 100.0f) pid->integral = 100.0f;
    if (pid->integral < -100.0f) pid->integral = -100.0f;
    
    float derivative = (error - pid->prev_error) / dt_sec;
    pid->prev_error = error;
    
    return (pid->Kp * error) + (pid->Ki * pid->integral) + (pid->Kd * derivative);
}

// This triggers every time a single ASCII character arrives
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2)
    {
        // Leave the completed line untouched until the main loop parses it.
        if (new_cmd_ready != 0)
        {
            HAL_UART_Receive_IT(&huart2, (uint8_t *)&rx_byte, 1);
            return;
        }

        // If it's a newline, the string is finished!
        if (rx_byte == '\n' || rx_byte == '\r')
        {
            if (rx_index > 0) 
            {
                rx_line_buffer[rx_index] = '\0'; // Add null terminator
                new_cmd_ready = 1;               // Flag the main loop to parse it
                rx_index = 0;                    // Reset for the next string
            }
        } 
        else 
        {
            // Otherwise, keep adding letters to the buffer
            if (rx_index < 127) 
            {
                rx_line_buffer[rx_index++] = rx_byte;
            }
        }
        // Listen for the next single character
        HAL_UART_Receive_IT(&huart2, (uint8_t *)&rx_byte, 1);
    }
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
