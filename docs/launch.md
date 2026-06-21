# SweePi Launch Guide

This branch supports two full-system launch modes:

1. **Simulation mode** — runs Gazebo, Nav2, coverage, coverage manager, and API bridge.
2. **Raspberry Pi robot mode** — runs real robot bringup, Nav2, coverage, coverage manager, and API bridge. Gazebo is not launched.

## Build

From the ROS 2 workspace:

```bash
cd /home/akhila-wedamestrige/SweePi/src/raspberry_pi
colcon build --packages-select sweepi_bringup sweepi_coverage sweepi_api_bridge
source install/setup.bash
```

## Run Simulation

Use this command when testing with Gazebo:

```bash
ros2 launch sweepi_bringup sweepi_sim_full.launch.py
```

This launch file starts:

* Gazebo simulation
* Nav2
* coverage tracker
* coverage planner
* coverage follow-path executor
* coverage manager
* API bridge

Simulation uses:

```bash
use_sim_time:=true
auto_start:=false
```

The API bridge will be available at:

```text
http://localhost:8080
ws://localhost:8765
```

Example API test:

```bash
curl http://localhost:8080/api/v1/robot/status
curl -X POST http://localhost:8080/api/v1/cleaning/start
```

## Run on Raspberry Pi

Use this command on the real robot:

```bash
ros2 launch sweepi_bringup sweepi_robot_full.launch.py map:=/path/to/map.yaml
```

This launch file starts:

* real robot bringup
* Nav2
* coverage tracker
* coverage planner
* coverage follow-path executor
* coverage manager
* API bridge

It does **not** start Gazebo.

Real robot mode uses:

```bash
use_sim_time:=false
auto_start:=false
```

The real robot bringup should provide:

* `/scan` from the real LiDAR
* `/odom` from encoders or motor controller
* `/tf` transforms
* `/cmd_vel` connection to the motor controller

From the Flutter app or another device on the same LAN, connect to:

```text
http://<raspberry-pi-ip>:8080
ws://<raspberry-pi-ip>:8765
```

Example:

```bash
curl http://192.168.1.25:8080/api/v1/robot/status
```

## Launch Files

The full launch files are located in:

```text
src/raspberry_pi/src/sweepi_bringup/launch/
```

Important files:

```text
sweepi_sim_full.launch.py      # Full simulation launch
sweepi_robot_full.launch.py    # Full real robot launch
robot_bringup.launch.py        # Real robot hardware bringup placeholder
```

## Notes

* Use `sweepi_sim_full.launch.py` for Gazebo testing.
* Use `sweepi_robot_full.launch.py` on the Raspberry Pi.
* The API bridge does not replace Nav2 or coverage; it only exposes robot control/status to the mobile app.
* For real robot mode, Gazebo is replaced by real hardware drivers.
