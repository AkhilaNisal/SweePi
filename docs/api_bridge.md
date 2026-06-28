# SweePi API Bridge

The mobile app talks to `sweepi_api_bridge` over HTTP JSON. The bridge talks to
ROS services and topics, mainly through `sweepi_robot_manager`. The app should
not launch ROS packages directly.

All routes start with `/api`; there is no `/api/v1` prefix.

## Command Results

Robot command endpoints return top-level lifecycle fields. `accepted=true`
means the bridge accepted the command and attempted the ROS action;
`completed=true` means this endpoint's command step was confirmed. Long-running
tasks still finish through status polling with `task_finished=true`.

The mobile app should proceed to the next cleaning step only when the command
response has both `success=true` and `completed=true`. See
[`docs/command_lifecycle.md`](command_lifecycle.md) for the field definitions
and cleaning sequence.

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
  -d '{"map_name":"living_room","mode":"automatic"}'
```

Start manual exploration:

```bash
curl -X POST http://localhost:8080/api/exploration/start \
  -H 'Content-Type: application/json' \
  -d '{"map_name":"living_room","mode":"manual"}'
```

Switch the active exploration session to manual mode without saving:

```bash
curl -X POST http://localhost:8080/api/exploration/switch \
  -H 'Content-Type: application/json' \
  -d '{"new_mode":"manual"}'
```

Switch the same active exploration session back to automatic mode:

```bash
curl -X POST http://localhost:8080/api/exploration/switch \
  -H 'Content-Type: application/json' \
  -d '{"new_mode":"automatic"}'
```

When switching modes, the bridge asks the robot manager to stop current
exploration motion without saving, then continue in the selected mode under the
same map name that was given to `/api/exploration/start`.

Drive manually:

```bash
curl -X POST http://localhost:8080/api/exploration/manual-drive \
  -H 'Content-Type: application/json' \
  -d '{"command":"forward","speed":0.2}'
```

Stop exploration and save the map:

```bash
curl -X POST http://localhost:8080/api/exploration/stop \
  -H 'Content-Type: application/json' \
  -d '{"save_map":true}'
```

For a non-ending pause without saving, send `save_map:false`:

```bash
curl -X POST http://localhost:8080/api/exploration/stop \
  -H 'Content-Type: application/json' \
  -d '{"save_map":false}'
```

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
curl -X PUT http://localhost:8080/api/maps/kitchen_first_floor/metadata \
  -H 'Content-Type: application/json' \
  -d '{"name":"Kitchen First Floor","sections":[{"section_id":"living_room_left","name":"Living Room Left","bounds":{"x":0.0,"y":0.0,"width":2.0,"height":2.0}}]}'
```

## Cleaning

Prepare full-map cleaning. This launches coverage and waits for an initial pose;
the robot does not move yet.

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"kitchen_first_floor","cleaning_mode":"full-map"}'
```

Start selected-section cleaning. If `processed_map` is supplied, the bridge
writes it as the temporary coverage map. If not, the bridge derives a bounded
coverage map from the selected section rectangles. This also prepares coverage
only; initial pose and motion start remain separate steps.

```bash
curl -X POST http://localhost:8080/api/cleaning/start \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"kitchen_first_floor","cleaning_mode":"sections","sections":[{"section_id":"s1","name":"Section 1","bounds":{"x":1.2,"y":0.8,"width":2.0,"height":1.5}}]}'
```

Set the initial pose from the mobile app:

```bash
curl -X POST http://localhost:8080/api/localization/initial-pose \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"kitchen_first_floor","x":0.0,"y":0.0,"yaw":0.0,"frame":"map"}'
```

This endpoint returns `completed:true` only after localization/TF confirms the
robot pose near the requested pose. If `/initialpose` is published but
confirmation times out, the response has `accepted:true`, `completed:false`, and
`success:false`.

You can also set the initial pose in RViz with `2D Pose Estimate`, then check:

```bash
curl http://localhost:8080/api/localization/status
curl http://localhost:8080/api/cleaning/status
```

Get the generated coverage path:

```bash
curl http://localhost:8080/api/cleaning/path
curl 'http://localhost:8080/api/cleaning/path?stride=5'
```

Validate the generated path and start motion:

```bash
curl -X POST http://localhost:8080/api/cleaning/validate
curl -X POST http://localhost:8080/api/cleaning/start-motion
```

`start-motion` does not auto-validate. A failed or missing validation returns
`VALIDATION_REQUIRED`; call `validate` again after setting a new initial pose or
after the coverage path changes.

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

All app-facing responses include `success`, `message`, `error`, and
`timestamp`. The full endpoint contract is maintained in
`docs/final_api_doc.md`.
