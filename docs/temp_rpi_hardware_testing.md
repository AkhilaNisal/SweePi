# Temporary Raspberry Pi Hardware Testing

## Purpose

This package is temporary. It allows SweePi to run on the old SLRC robot with Raspberry Pi GPIO stepper
motors and a directly connected MPU6050 while the STM32 encoder/IMU hardware is still being developed.

It does not replace the final STM32/encoder architecture, `sweepi_base_driver`, `sweepi_state_estimation`,
or the normal real bringup path.

## Architecture

```text
Nav2 / coverage / teleop
        |
/cmd_vel
        |
sweepi_temp_stepper_driver
        |
GPIO stepper motors + step count totals
        |
sweepi_temp_stepper_odom
        |
/wheel/odom
        |
sweepi_state_estimation EKF
        ^
/imu/data from sweepi_temp_mpu6050
        |
/odom + odom -> base_footprint
```

Only the EKF should publish `/odom` and `odom -> base_footprint`.

## Topics

| Topic | Purpose |
| --- | --- |
| `/cmd_vel` | Velocity command input |
| `/stepper/left_steps_total` | Signed left generated step pulse total |
| `/stepper/right_steps_total` | Signed right generated step pulse total |
| `/wheel/odom` | Open-loop wheel odometry for EKF input |
| `/imu/data` | MPU6050 IMU data for EKF input |
| `/odom` | Final fused EKF odometry |
| `/hardware/temp_stepper_status` | JSON stepper status |
| `/hardware/temp_odom_status` | JSON wheel odom status |
| `/hardware/temp_imu_status` | JSON IMU hardware status |
| `/imu/calibration_status` | IMU calibration status |

## Stepper Pins

Previous SLRC pin configuration:

```yaml
chip_name: gpiochip4

left_en_pin: 12
left_dir_pin: 5
left_step_pin: 6

right_en_pin: 22
right_dir_pin: 23
right_step_pin: 24

enable_active_low: true
left_dir_inverted: false
right_dir_inverted: true
```

## MPU6050 Connection

```text
VCC -> 3.3V or 5V depending on module regulator
GND -> GND
SDA -> Raspberry Pi SDA
SCL -> Raspberry Pi SCL
I2C bus -> 1
Default address -> 0x68
```

Enable and check I2C:

```bash
sudo raspi-config
sudo apt install i2c-tools python3-smbus python3-libgpiod
i2cdetect -y 1
```

Expected MPU6050 address:

```text
0x68
```

## IMU Calibration

Keep the robot still during startup. Startup calibration collects gyro samples unless a saved calibration file
already exists and loading is enabled.

Manual recalibration:

```bash
ros2 service call /imu/calibrate_gyro std_srvs/srv/Trigger "{}"
```

Calibration is saved to:

```text
~/.ros/sweepi_mpu6050_calibration.yaml
```

## Launch Commands

```bash
colcon build --symlink-install --packages-select sweepi_temp_rpi_hardware sweepi_real_bringup sweepi_state_estimation
source install/setup.bash
ros2 launch sweepi_temp_rpi_hardware temp_rpi_hardware.launch.py
ros2 launch sweepi_real_bringup temp_rpi_hardware_debug.launch.py launch_lidar:=false
```

Desktop dry-run:

```bash
ros2 launch sweepi_temp_rpi_hardware temp_rpi_hardware.launch.py dry_run_gpio:=true launch_imu:=false
```

## Testing Order

1. Test `/cmd_vel` to stepper movement.
2. Check step count topics.
3. Check `/wheel/odom`.
4. Check `/imu/data`.
5. Check `/odom` from EKF.
6. Check TF tree.
7. Check Nav2 movement only after the above are correct.

Commands:

```bash
ros2 topic echo /stepper/left_steps_total
ros2 topic echo /stepper/right_steps_total
ros2 topic echo /wheel/odom
ros2 topic echo /imu/data
ros2 topic echo /odom
ros2 topic hz /wheel/odom
ros2 topic hz /imu/data
ros2 run tf2_ros tf2_echo odom base_footprint
```

## Calibration Checks

- Move forward: `/wheel/odom` x should increase.
- Rotate robot counterclockwise: yaw should increase.
- Rotate robot counterclockwise: `imu.angular_velocity.z` should be positive.
- Robot flat and still: acceleration Z should be around `9.81 m/s^2` if IMU Z points upward.

If signs are wrong, tune:

```yaml
left_step_sign
right_step_sign
angular_velocity_signs
linear_acceleration_signs
```

## Limitations

- Stepper odom is not true encoder odom.
- It cannot detect missed steps.
- It cannot detect wheel slip.
- It cannot detect the robot being blocked.
- This package must be removed or disabled when the STM32 real base driver is ready.
