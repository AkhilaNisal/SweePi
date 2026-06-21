# SweePi Launch Guide

This branch supports two full-system launch modes:

1. **Simulation mode** — runs Gazebo, Nav2, coverage, coverage manager, and API bridge.
2. **Raspberry Pi robot mode** — runs real robot bringup, Nav2, coverage, coverage manager, and API bridge. Gazebo is not launched.

## Build

From the ROS 2 workspace:

```bash
cd /home/akhila-wedamestrige/SweePi/src/raspberry_pi
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select sweepi_bringup sweepi_coverage sweepi_api_bridge
source install/setup.bash
```

After building, verify that the API bridge executable is installed:

```bash
ros2 pkg executables sweepi_api_bridge
```

Expected output:

```text
sweepi_api_bridge api_bridge_node
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
HTTP:      http://localhost:8080
WebSocket: ws://localhost:8765
```

Useful API tests:

```bash
curl http://localhost:8080/api/v1/robot/status
curl -X POST http://localhost:8080/api/v1/cleaning/start
```

To check whether the API bridge is listening:

```bash
ss -ltnp | grep -E "8080|8765"
```

Expected result: both ports `8080` and `8765` should be listening.

Note: `ws://localhost:8765` is a WebSocket URL. Do not run it directly as a terminal command, and do not test it with normal `curl`. Use a WebSocket client if direct WebSocket testing is needed.

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
HTTP:      http://<raspberry-pi-ip>:8080
WebSocket: ws://<raspberry-pi-ip>:8765
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

The API bridge launch file is located in:

```text
src/raspberry_pi/src/sweepi_api_bridge/launch/api_bridge.launch.py
```

The API bridge node executable is:

```text
api_bridge_node
```

## Troubleshooting

If `curl http://localhost:8080/api/v1/robot/status` fails with connection refused, the API bridge is not running or did not bind to port `8080`.

Check whether the ports are open:

```bash
ss -ltnp | grep -E "8080|8765"
```

If nothing appears, check the launch terminal for errors related to:

```text
api_bridge_node
sweepi_api_bridge
```

You can also run the API bridge alone:

```bash
cd /home/akhila-wedamestrige/SweePi/src/raspberry_pi
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run sweepi_api_bridge api_bridge_node
```

Then test again from another terminal:

```bash
curl http://localhost:8080/api/v1/robot/status
```

If `/api/v1/cleaning/start` returns `accepted: false` because `/map` is unavailable, that means the bridge is reachable but the required map/coverage system is not ready yet.

## Notes

* Use `sweepi_sim_full.launch.py` for Gazebo testing.
* Use `sweepi_robot_full.launch.py` on the Raspberry Pi.
* The API bridge does not replace Nav2 or coverage; it only exposes robot control/status to the mobile app.
* For real robot mode, Gazebo is replaced by real hardware drivers.
* The API bridge should expose HTTP on port `8080` and WebSocket on port `8765`.
