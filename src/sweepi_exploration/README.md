# SweePi Exploration

`sweepi_exploration` provides a wavefront frontier explorer for building a map with SLAM Toolbox and Nav2. The explorer can run in automatic frontier mode or pause automatic goals so the robot can be driven manually with teleop.

Every exploration session must have a map name. Automatic exploration saves by itself when it completes. Manual teleop exploration saves when you call the manual stop-and-save service. Both write:

```text
~/SweePi/maps/<map_name>.yaml
~/SweePi/maps/<map_name>.pgm
```

The name is sanitized before saving: path components are removed, spaces and dots become underscores, and only letters, numbers, `_`, and `-` are kept.

## What Exists In This Package

```text
sweepi_exploration/
├── launch/
│   └── exploration.launch.py
├── sweepi_exploration/
│   ├── wavefront_explorer.py
│   └── __init__.py
├── CMakeLists.txt
├── package.xml
└── README.md
```

There is no `master_launch.py` in this package. `exploration.launch.py` starts SLAM Toolbox and the exploration node. Start Nav2 separately before using automatic exploration.

## Build

```bash
cd ~/SweePi
colcon build --packages-select sweepi_exploration
source install/setup.bash
```

## Start The System

In simulation, start the robot from `sweepi_bringup`:

```bash
ros2 launch sweepi_bringup gazebo.launch.xml
```

Start Nav2 in another terminal. Use your Nav2 setup/params for the robot; a basic command is:

```bash
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=true
```

Start SLAM plus the explorer. `map_name` is required:

```bash
ros2 launch sweepi_exploration exploration.launch.py map_name:=kitchen_first_floor
```

For a real robot, use real time:

```bash
ros2 launch sweepi_exploration exploration.launch.py \
  map_name:=kitchen_first_floor \
  use_sim_time:=false
```

## Automatic Exploration

Automatic mode is the default. The explorer sends frontier goals to Nav2 and saves the map with the required `map_name` when exploration finishes. This also works if you switch to manual mode and later resume automatic mode.

```bash
ros2 launch sweepi_exploration exploration.launch.py \
  map_name:=kitchen_first_floor \
  start_mode:=auto
```

The output is saved as:

```text
~/SweePi/maps/kitchen_first_floor.yaml
~/SweePi/maps/kitchen_first_floor.pgm
```

## Manual Teleop Exploration

Start paused in manual mode:

```bash
ros2 launch sweepi_exploration exploration.launch.py \
  map_name:=kitchen_first_floor \
  start_mode:=manual
```

Drive manually with a teleop node that publishes to `/cmd_vel`:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=/cmd_vel
```

After manual driving, stop further exploration and save the map with the given name:

```bash
ros2 service call /stop_exploration_and_save nav2_msgs/srv/SaveMap \
  "{map_topic: /map, map_url: kitchen_first_floor, image_format: pgm, map_mode: trinary, free_thresh: 0.196, occupied_thresh: 0.65}"
```

If `map_url` is empty, the service uses the required launch `map_name`. If neither is available, saving is rejected.

## Switch Between Manual And Automatic

Pause automatic goals and allow teleop:

```bash
ros2 service call /switch_to_manual_control std_srvs/srv/Trigger {}
```

Resume automatic frontier exploration:

```bash
ros2 service call /switch_to_auto_exploration std_srvs/srv/Trigger {}
```

Boolean control is also available:

```bash
ros2 service call /set_manual_control std_srvs/srv/SetBool "{data: true}"
ros2 service call /set_manual_control std_srvs/srv/SetBool "{data: false}"
```

Stop motion and pause further autonomous exploration without ending the task:

```bash
ros2 service call /stop_exploration std_srvs/srv/Trigger {}
```

After this, switch back to automatic or manual mode to continue. To end the
exploration task, use `/stop_exploration_and_save`.

Save without changing the current mode, mainly for manual teleop sessions:

```bash
ros2 service call /save_exploration_map nav2_msgs/srv/SaveMap \
  "{map_topic: /map, map_url: kitchen_first_floor, image_format: pgm, map_mode: trinary, free_thresh: 0.196, occupied_thresh: 0.65}"
```

## Launch Arguments

| Argument | Default | Notes |
| --- | --- | --- |
| `map_name` | required | Output map name for automatic completion and manual stop/save |
| `use_sim_time` | `true` | Use simulation clock |
| `start_mode` | `auto` | `auto`, `manual`, or `stopped` |
| `cmd_vel_topic` | `/cmd_vel` | Teleop/zero-velocity command topic |
| `frontier_min_size` | `5` | Minimum cells in a frontier cluster |
| `cluster_distance` | `1.2` | Frontier clustering distance |
| `exploration_frequency` | `3.0` | Main exploration loop frequency |
| `nav_timeout` | `15.0` | Time allowed for one Nav2 goal |
| `max_velocity` | `0.1` | Stored speed limit parameter |
| `max_angular_velocity` | `0.5` | Stored angular speed limit parameter |
| `acceleration_limit` | `0.1` | Stored acceleration parameter |
| `max_attempts_per_frontier` | `2` | Attempts before blocking a frontier region |
| `max_consecutive_timeouts` | `2` | Stop after repeated navigation timeouts |
| `max_exploration_time` | `600` | Maximum automatic exploration time in seconds |
| `goal_offset_distance` | `0.6` | Offset frontier goals away from walls |
| `robot_radius` | `0.3` | Robot radius used for clearance checks |
| `safety_margin` | `0.15` | Extra clearance around the robot |
| `unreachable_region_radius` | `0.3` | Radius for failed-frontier blocking |

Example with custom parameters:

```bash
ros2 launch sweepi_exploration exploration.launch.py \
  map_name:=lab_test_01 \
  frontier_min_size:=5 \
  max_exploration_time:=900 \
  unreachable_region_radius:=0.3
```

## Topics

Subscribed:

```text
/map
```

Published:

```text
/exploration/frontiers
/exploration/unreachable_areas
/exploration/blocked_regions
/exploration/mode
/cmd_vel
```

The node also uses the Nav2 `navigate_to_pose` action.

## Services

```text
/switch_to_manual_control     std_srvs/srv/Trigger
/switch_to_auto_exploration   std_srvs/srv/Trigger
/set_manual_control           std_srvs/srv/SetBool
/stop_exploration             std_srvs/srv/Trigger
/stop_exploration_and_save    nav2_msgs/srv/SaveMap
/save_exploration_map         nav2_msgs/srv/SaveMap
```

## RViz

Useful displays:

```text
/map                         OccupancyGrid
/exploration/frontiers       MarkerArray
/exploration/unreachable_areas MarkerArray
/exploration/blocked_regions MarkerArray
```

## Troubleshooting

Check that maps are being published:

```bash
ros2 topic echo /map --once
```

Check that Nav2 is available:

```bash
ros2 action list | grep navigate_to_pose
```

Check the current mode:

```bash
ros2 topic echo /exploration/mode --once
```

If a save fails, confirm that the session was launched with `map_name:=...` or that the `SaveMap` request contains a non-empty `map_url`.
