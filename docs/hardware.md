# SweePi Real Hardware Layer

This document describes the first real-robot hardware packages. These packages are intentionally separate
from `sweepi_robot_manager`, coverage, exploration, Nav2, and the API bridge so the hardware layer can be
debugged by itself.

## Packages

`sweepi_base_driver`

- Talks to the STM32 over a line-based serial protocol.
- Subscribes to `/cmd_vel`.
- Sends left and right wheel velocity commands to the STM32.
- Reads encoder deltas, IMU values, battery voltage, fault flags, and status.
- Publishes wheel-only odometry on `/wheel/odom`.
- Publishes IMU data on `/imu/data`.
- Publishes JSON hardware status on `/hardware/status`.

`sweepi_state_estimation`

- Starts `robot_localization` EKF.
- Fuses `/wheel/odom` and `/imu/data`.
- Publishes final fused local odometry on `/odom`.
- Publishes the `odom -> base_footprint` transform.

`sweepi_real_bringup`

- Provides a standalone debug launch file for the real hardware stack.
- Can launch the base driver, EKF, robot description, and the existing `sllidar_ros2` lidar driver.
- Does not launch the robot manager, API bridge, coverage, exploration, Nav2, Gazebo, or SLAM.

## Expected Topics

| Topic | Publisher | Message | Purpose |
| --- | --- | --- | --- |
| `/cmd_vel` | Nav2, teleop, or test node | `geometry_msgs/msg/Twist` | Desired robot velocity |
| `/wheel/odom` | `sweepi_base_driver` | `nav_msgs/msg/Odometry` | Encoder-only odometry for EKF |
| `/imu/data` | `sweepi_base_driver` | `sensor_msgs/msg/Imu` | Gyro and acceleration data for EKF |
| `/odom` | `robot_localization` EKF | `nav_msgs/msg/Odometry` | Final fused local odometry |
| `/scan` | `sllidar_ros2` | `sensor_msgs/msg/LaserScan` | Real lidar scan |
| `/hardware/status` | `sweepi_base_driver` | `std_msgs/msg/String` | JSON hardware status |

Only the EKF should publish `odom -> base_footprint`. The base driver publishes `/wheel/odom` but does not
publish TF.

## Debug Launch

Build and source the workspace first:

```bash
colcon build --symlink-install
source install/setup.bash
```

Launch the full hardware debug layer:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py
```

Common launch arguments:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py \
  base_serial_port:=/dev/serial/by-id/YOUR_STM32_DEVICE \
  lidar_serial_port:=/dev/serial/by-id/YOUR_RPLIDAR_DEVICE
```

Launch only the STM32 base driver:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py \
  launch_ekf:=false \
  launch_lidar:=false \
  publish_robot_description:=false
```

Launch only EKF for checking `/wheel/odom` and `/imu/data` inputs:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py \
  launch_base:=false \
  launch_lidar:=false
```

Launch only lidar:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py \
  launch_base:=false \
  launch_ekf:=false \
  publish_robot_description:=false
```

## STM32 Serial Protocol

The first implementation uses ASCII packets, one packet per line.

Command from Raspberry Pi to STM32:

```text
CMD,<seq>,<time_ms>,<left_vel>,<right_vel>,<motor_enable>,<suction_enable>,<brush_enable>,<mode>[,<checksum>]
```

Example:

```text
CMD,552,184230,0.2000,0.2000,1,0,0,NORMAL
```

Feedback from STM32 to Raspberry Pi:

```text
FB,<seq>,<stm_time_us>,<delta_left>,<delta_right>,<gx>,<gy>,<gz>,<ax>,<ay>,<az>,<battery>,<fault>,<status>[,<checksum>]
```

Example:

```text
FB,1042,523456789,18,19,0.002,-0.001,0.134,0.03,-0.02,9.79,15.1,0,OK
```

Recommended STM32 behavior:

- Send feedback at 50 Hz to 100 Hz.
- Use signed encoder delta ticks since the previous feedback packet.
- Use a monotonic STM32 timestamp in microseconds.
- Send gyro in `rad/s` and acceleration in `m/s^2` when possible.
- Stop motors if no valid command arrives within 200 ms to 500 ms.
- Keep the robot still during startup gyro bias calibration.

## Base Driver Parameters

Default parameters live in:

```text
src/sweepi_base_driver/config/base_driver_params.yaml
```

Important tuning values:

- `wheel_radius`
- `wheel_separation`
- `ticks_per_revolution`
- `left_encoder_sign`
- `right_encoder_sign`
- `gyro_units`
- `accel_units`
- `imu_angular_velocity_signs`
- `imu_linear_acceleration_signs`
- covariance diagonals for `/wheel/odom` and `/imu/data`

If the STM32 sends gyro in degrees per second, set:

```yaml
gyro_units: deg_s
```

If the STM32 sends acceleration in g, set:

```yaml
accel_units: g
```

## EKF Inputs

The first EKF config fuses:

- From `/wheel/odom`: `x`, `y`, `yaw`, `linear.x`, and `angular.z`.
- From `/imu/data`: `angular_velocity.z`.

It does not initially fuse IMU orientation or linear acceleration because low-cost IMU acceleration can make
2D odometry worse until it is calibrated and tuned.

## Hardware Test Order

1. Confirm STM32 packets arrive and `/hardware/status` updates.
2. Send small `/cmd_vel` commands and verify motor direction.
3. Check encoder direction in `/wheel/odom`.
4. Check IMU direction in `/imu/data`; counterclockwise rotation should make gyro Z positive.
5. Start EKF and confirm `/odom` and `odom -> base_footprint`.
6. Start lidar and confirm `/scan` uses `lidar_link`.
7. Only after the hardware layer is stable, connect SLAM, AMCL, Nav2, coverage, and the robot manager.
