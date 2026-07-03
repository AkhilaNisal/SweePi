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

Temporary Raspberry Pi testing on the old SLRC robot is documented separately in
[Temporary Raspberry Pi Hardware Testing](temp_rpi_hardware_testing.md). That path uses
`sweepi_temp_rpi_hardware` to feed `/wheel/odom` and `/imu/data` into the same EKF without replacing the
final STM32 hardware packages.

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

Build and source the final hardware packages first:

```bash
colcon build --symlink-install --packages-select sweepi_base_driver sweepi_state_estimation sweepi_real_bringup
source install/setup.bash
```

Launch without lidar for the first STM32 UART test:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py launch_lidar:=false
```

Launch with the explicit Raspberry Pi UART device:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py base_serial_port:=/dev/ttyAMA0 base_baud_rate:=115200 launch_lidar:=false
```

Use a USB serial adapter or USB CDC device for debugging by overriding the port:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py base_serial_port:=/dev/ttyACM0 base_baud_rate:=115200 launch_lidar:=false
```

Launch the full hardware debug layer, including lidar:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py
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

## Raspberry Pi to STM32 UART Connection

The final robot path uses the Raspberry Pi UART pins for the STM32 base controller. The default ROS serial device is `/dev/ttyAMA0` at `115200` baud.

Wiring:

```text
Raspberry Pi GPIO14 / TXD / physical pin 8   -> STM32 RX
Raspberry Pi GPIO15 / RXD / physical pin 10  -> STM32 TX
Raspberry Pi GND                             -> STM32 GND
```

Safety notes:

- Raspberry Pi UART uses `3.3 V` logic.
- Do not connect a `5 V` UART TX signal into Raspberry Pi RX.
- Common ground between Raspberry Pi and STM32 is required.
- Do not power motors from the Raspberry Pi.
- Motor power and logic power must follow the PCB power design.
- Keep motor supply noise away from the Pi/STM32 logic supply as much as possible.

Enable the Raspberry Pi UART:

```bash
sudo raspi-config
```

Then choose:

```text
Interface Options -> Serial Port
Login shell over serial: No
Enable serial hardware: Yes
```

Reboot after changing the serial settings:

```bash
sudo reboot
```

Verify the UART device exists:

```bash
ls -l /dev/ttyAMA0
```

## Real Robot Hardware Constants

The final STM32-based hardware path uses these measured robot values:

```text
wheel_radius: 0.033 m
wheel_base / wheel_separation: 0.200 m
encoder_ticks_per_revolution: 7392
left_encoder_sign: -1
right_encoder_sign: 1
stm32_control_loop: 20 ms / 50 Hz
command_timeout: 500 ms
default_serial_port: /dev/ttyAMA0
baud_rate: 115200
gyro_units: rad/s
accel_units: m/s^2
```

The STM32 currently has these local motor-test firmware constants:

```c
#define MOTOR_TEST_ENABLE 1
#define MOTOR_TEST_LEFT_RPM 15.0f
#define MOTOR_TEST_RIGHT_RPM 15.0f
```

For real Raspberry Pi ROS control, STM32 must not permanently override serial `/cmd_vel` commands with fixed test RPM values. During real integration, set `MOTOR_TEST_ENABLE` to `0`, or make test RPM active only in a dedicated local test mode instead of normal serial mode. If `MOTOR_TEST_ENABLE` remains active in normal mode, the robot may ignore `/cmd_vel` even though the serial connection is working.

## STM32 Serial Protocol

The first implementation uses ASCII packets, one packet per line.

Command from Raspberry Pi to STM32:

```text
CMD,<seq>,<rpi_time_ms>,<left_vel_mps>,<right_vel_mps>,<motor_enable>,<suction_enable>,<brush_enable>,<mode>
```

The Raspberry Pi sends left and right wheel linear velocity in `m/s`. It does not send RPM or PWM; the STM32 converts wheel velocity into motor RPM/PID/PWM internally. Every serial message is newline-terminated. Checksum is disabled for now because `use_checksum: false`.

Example:

```text
CMD,552,184230,0.2000,0.2000,1,0,0,NORMAL
```

Feedback from STM32 to Raspberry Pi:

```text
FB,<seq>,<stm_time_us>,<delta_left_ticks>,<delta_right_ticks>,<gx>,<gy>,<gz>,<ax>,<ay>,<az>,<battery_voltage>,<fault>,<status>
```

The STM32 sends signed encoder delta ticks since the previous feedback packet. The Raspberry Pi applies `left_encoder_sign` and `right_encoder_sign`, and `stm_time_us` must be monotonic microseconds.


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

Important final robot values:

- `serial_port`: `/dev/ttyAMA0`
- `baud_rate`: `115200`
- `wheel_radius`: `0.033`
- `wheel_separation`: `0.200`
- `ticks_per_revolution`: `7392.0`
- `left_encoder_sign`: `-1.0`
- `right_encoder_sign`: `1.0`
- `command_rate_hz`: `50.0`
- `feedback_poll_rate_hz`: `100.0`
- `cmd_vel_timeout`: `0.5`
- `gyro_units`: `rad_s`
- `accel_units`: `m_s2`
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

## Hardware Test Commands

Inspect the hardware and odometry topics:

```bash
ros2 topic echo /hardware/status
ros2 topic echo /wheel/odom
ros2 topic echo /imu/data
ros2 topic echo /odom
```

Check publish rates:

```bash
ros2 topic hz /wheel/odom
ros2 topic hz /imu/data
```

With the robot lifted from the floor, send a small safe motor command:

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.03}, angular: {z: 0.0}}"
```

Stop the robot:

```bash
ros2 topic pub -1 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}, angular: {z: 0.0}}"
```

## Hardware Test Order

1. Confirm `/dev/ttyAMA0` exists and STM32 packets arrive.
2. Confirm `/hardware/status` updates.
3. Send small `/cmd_vel` commands with the robot lifted and verify motor direction.
4. Check encoder direction in `/wheel/odom`.
5. Check IMU direction in `/imu/data`; counterclockwise rotation should make gyro Z positive.
6. Start EKF and confirm `/odom` and `odom -> base_footprint`.
7. Start lidar and confirm `/scan` uses `lidar_link`.
8. Only after the hardware layer is stable, connect SLAM, AMCL, Nav2, coverage, and the robot manager.
