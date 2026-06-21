# SweePi Launch Guide

This branch supports two full-system launch modes:

1. **Simulation mode** — runs Gazebo, Nav2, SLAM Toolbox, idle exploration, coverage, coverage manager, and API bridge.
2. **Raspberry Pi robot mode** — runs real robot bringup, Nav2, coverage, coverage manager, and API bridge. Gazebo is not launched.

## Build

From the ROS 2 workspace:

```bash
cd /home/akhila-wedamestrige/SweePi/src/raspberry_pi
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select sweepi_bringup sweepi_coverage sweepi_api_bridge sweepi_slam sweepi_exploration
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
* SLAM Toolbox
* idle wavefront explorer
* coverage tracker
* coverage planner
* coverage follow-path executor
* coverage manager
* API bridge

The explorer is available for API control, but it does **not** start moving on
launch. Start it with `POST /api/v1/exploration/start`.

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
curl http://localhost:8080/api/v1/exploration/status
```

For the full HTTP and WebSocket reference, including Postman setup and the
simulation control sequence, see [`docs/api.md`](api.md).

To check whether the API bridge is listening:

```bash
ss -ltnp | grep -E "8080|8765"
```

Expected result: both ports `8080` and `8765` should be listening.

Note: `ws://localhost:8765` is a WebSocket URL. Do not run it directly as a terminal command, and do not test it with normal `curl`. Use a WebSocket client if direct WebSocket testing is needed.

## API Mapping Workflow Before Cleaning

Cleaning requires a live `/map`. Build and save the map through the API before
starting cleaning.

Start simulation:

```bash
cd /home/akhila-wedamestrige/SweePi/src/raspberry_pi
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch sweepi_bringup sweepi_sim_full.launch.py
```

Start exploration and provide the area/map name:

```bash
curl -X POST http://localhost:8080/api/v1/exploration/start \
  -H "Content-Type: application/json" \
  -d '{"area_name":"first_floor"}'
```

Check exploration status:

```bash
curl http://localhost:8080/api/v1/exploration/status
```

Wait until `/map` is available through the bridge:

```bash
curl http://localhost:8080/api/v1/maps/current
```

Continue once the response includes:

```json
{
  "available": true
}
```

Stop exploration. This saves the current live `/map` using the `area_name`
from the start request:

```bash
curl -X POST http://localhost:8080/api/v1/exploration/stop
```

Expected saved-map response:

```json
{
  "accepted": true,
  "state": "idle",
  "area_name": "first_floor",
  "map_saved": true,
  "map_id": "first_floor",
  "message": "Exploration stopped and map saved"
}
```

Then start cleaning:

```bash
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

Check whether the map topic exists and has a transient-local message:

```bash
ros2 topic echo /map --once --qos-durability transient_local
```

If `POST /api/v1/exploration/start` is rejected with
`"/exploration/start is unavailable"`, the `wavefront_explorer` node or its
services are missing. Check:

```bash
ros2 service list | grep /exploration
ros2 node list | grep wavefront
```

If SLAM Toolbox is not running:

```bash
ros2 node list | grep slam
```

If exploration status says Nav2 is not ready, check the action server:

```bash
ros2 action list | grep navigate_to_pose
```

## Notes

* Use `sweepi_sim_full.launch.py` for Gazebo testing.
* Use `sweepi_robot_full.launch.py` on the Raspberry Pi.
* The API bridge does not replace Nav2 or coverage; it only exposes robot control/status to the mobile app.
* For real robot mode, Gazebo is replaced by real hardware drivers.
* The API bridge should expose HTTP on port `8080` and WebSocket on port `8765`.
