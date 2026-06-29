# sweepi_temp_rpi_hardware

Temporary Raspberry Pi hardware compatibility layer for testing SweePi navigation on the old SLRC robot.

This package does not replace `sweepi_base_driver`, `sweepi_state_estimation`, or `sweepi_real_bringup`.
It publishes only the EKF inputs:

- `/wheel/odom` from generated GPIO step pulses
- `/imu/data` from a directly connected MPU6050

The final `/odom` and `odom -> base_footprint` TF must still come from `sweepi_state_estimation`.

## Runtime Packages

On the Raspberry Pi, install the hardware Python/system packages:

```bash
sudo apt install i2c-tools python3-smbus python3-libgpiod
```

Optional:

```bash
sudo apt install python3-smbus2
```

or:

```bash
pip install smbus2
```

## Launch

```bash
ros2 launch sweepi_temp_rpi_hardware temp_rpi_hardware.launch.py
```

Desktop dry-run without GPIO or IMU:

```bash
ros2 launch sweepi_temp_rpi_hardware temp_rpi_hardware.launch.py dry_run_gpio:=true launch_imu:=false
```

Full temporary real bringup:

```bash
ros2 launch sweepi_real_bringup temp_rpi_hardware_debug.launch.py launch_lidar:=false
```

## Limitations

Stepper wheel odometry is command-derived, open-loop odometry. It counts generated step pulses, but it cannot
detect missed steps, wheel slip, blocked wheels, or motor stall. Remove or disable this temporary package when
the STM32 encoder and IMU hardware path is ready.
