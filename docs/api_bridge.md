# SweePi API Bridge

The mobile app talks to `sweepi_api_bridge` over HTTP JSON. The bridge talks to
ROS services and topics, mainly through `sweepi_robot_manager`. The app should
not launch ROS packages directly.

All routes start with `/api`; there is no `/api/v1` prefix.

## Launch

Build and source:

```bash
cd ~/SweePi
colcon build --symlink-install
source install/setup.bash
```

Run only the bridge:

```bash
ros2 launch sweepi_api_bridge api_bridge.launch.py api_host:=0.0.0.0 api_port:=8080 use_sim_time:=true
```

Run the robot manager with the bridge in simulation:

```bash
ros2 launch sweepi_robot_manager master.launch.py use_sim_time:=true launch_api_bridge:=true
```

Run on the real robot without Gazebo:

```bash
ros2 launch sweepi_robot_manager master.launch.py use_sim_time:=false launch_sim:=false launch_api_bridge:=true
```

## Status

```bash
curl http://localhost:8080/api/system/health
curl http://localhost:8080/api/robot/status
```

## Exploration

Start automatic exploration:

```bash
curl -X POST http://localhost:8080/api/exploration/start \
  -H 'Content-Type: application/json' \
  -d '{"area_name":"living_room","mode":"automatic"}'
```

Start manual exploration:

```bash
curl -X POST http://localhost:8080/api/exploration/start \
  -H 'Content-Type: application/json' \
  -d '{"area_name":"living_room","mode":"manual"}'
```

Drive manually:

```bash
curl -X POST http://localhost:8080/api/exploration/manual/drive \
  -H 'Content-Type: application/json' \
  -d '{"linear_x":0.15,"angular_z":0.0,"duration_ms":300}'
```

Use command-style manual driving:

```bash
curl -X POST http://localhost:8080/api/exploration/manual/command \
  -H 'Content-Type: application/json' \
  -d '{"command":"rotate_left","speed":0.4,"duration_ms":500}'
```

Stop exploration motion without ending the task:

```bash
curl -X POST http://localhost:8080/api/exploration/stop
```

After this, the robot velocity is zero and autonomous/manual motion is paused,
but the exploration session remains active. Use `/api/exploration/mode` to
switch back to `automatic` or `manual`.

Stop and save exploration:

```bash
curl -X POST http://localhost:8080/api/exploration/stop-and-save
```

This is the task-ending exploration command. It stops motion, saves the active
map name, and lets the manager return to idle so coverage or a new exploration
task can start.

Check exploration status:

```bash
curl http://localhost:8080/api/exploration/status
```

## Maps

Get the current live map:

```bash
curl http://localhost:8080/api/maps/current
```

List saved maps from `~/SweePi/maps`:

```bash
curl http://localhost:8080/api/maps
```

Get a saved map:

```bash
curl http://localhost:8080/api/maps/kitchen_first_floor
curl http://localhost:8080/api/maps/kitchen_first_floor/metadata
```

Store sections and no-go zones:

```bash
curl -X PUT http://localhost:8080/api/maps/kitchen_first_floor/sections \
  -H 'Content-Type: application/json' \
  -d '{"sections":[{"section_id":"living_room_left","name":"Living Room Left","polygon":[[0,0],[2,0],[2,2],[0,2]]}],"no_go_zones":[]}'
```

## Cleaning

Prepare coverage/cleaning. This launches coverage through the manager, but does
not validate or start robot motion. The coverage path is generated after the
initial pose is set and TF/map/costmap data are ready.

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"kitchen_first_floor","cleaning_mode":"full_map","auto_start":false}'
```

Send initial pose through the API:

```bash
curl -X POST http://localhost:8080/api/localization/initial-pose \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"kitchen_first_floor","x":0.0,"y":0.0,"yaw":0.0}'
```

Or set the initial pose in RViz with `2D Pose Estimate`, then confirm:

```bash
curl http://localhost:8080/api/localization/status
curl http://localhost:8080/api/cleaning/status
```

Get the generated coverage path:

```bash
curl http://localhost:8080/api/cleaning/path
curl 'http://localhost:8080/api/cleaning/path?stride=5'
```

Validate and start motion:

```bash
curl -X POST http://localhost:8080/api/cleaning/validate
curl -X POST http://localhost:8080/api/cleaning/start-motion
```

Check progress and coverage map:

```bash
curl http://localhost:8080/api/cleaning/status
curl http://localhost:8080/api/cleaning/coverage-map
```

Pause, resume, stop, reset, and return home:

```bash
curl -X POST http://localhost:8080/api/cleaning/pause
curl -X POST http://localhost:8080/api/cleaning/resume
curl -X POST http://localhost:8080/api/cleaning/stop
curl -X POST http://localhost:8080/api/cleaning/reset
curl -X POST http://localhost:8080/api/cleaning/return-home
```

Get the last coverage summary:

```bash
curl http://localhost:8080/api/cleaning/last-summary
```

The app can use this shortcut only when it provides the initial pose:

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"kitchen_first_floor","cleaning_mode":"full_map","auto_start":true,"initial_pose":{"x":0.0,"y":0.0,"yaw":0.0}}'
```

The bridge still calls manager coverage with `auto_start=false`, waits for
initial pose, TF, and the generated path, then validates and starts motion.

Selected-section cleaning requests are validated and section metadata can be
stored, but section-only path generation is not implemented in
`sweepi_coverage` yet. The bridge returns `accepted:false` instead of pretending
to clean the full map.
