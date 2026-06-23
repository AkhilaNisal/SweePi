# SweePi Robot Manager

`sweepi_robot_manager` is the top-level entrypoint for running SweePi without launching each package manually. The master launch starts the robot bringup and the manager only. Exploration and coverage are selected later through manager service calls.

## Master Launch

Robot bringup plus manager:

```bash
ros2 launch sweepi_robot_manager master.launch.py
```

For a real robot, skip Gazebo:

```bash
ros2 launch sweepi_robot_manager master.launch.py \
  launch_sim:=false \
  use_sim_time:=false
```

## Manager Services

Start exploration. `map_name` is required. `mode` can be `auto`, `manual`, or `stopped`.

```bash
ros2 service call /sweepi_robot_manager/start_exploration \
  sweepi_robot_manager_interfaces/srv/StartTask \
  "{map_name: kitchen_first_floor, mode: auto, auto_start: false}"
```

Start coverage from a saved map. `map_name` is required and loads `~/SweePi/maps/<map_name>.yaml`. When coverage is started while exploration is still the active task, the manager shuts down the exploration launch stack first.

```bash
ros2 service call /sweepi_robot_manager/start_coverage \
  sweepi_robot_manager_interfaces/srv/StartTask \
  "{map_name: kitchen_first_floor, mode: '', auto_start: false}"
```

With `auto_start: false`, coverage is launched but the robot does not move yet. Use the same manual flow as before:

```bash
# 1. Set the AMCL initial pose in RViz.

# 2. Validate the frozen executable coverage path.
ros2 service call /sweepi_robot_manager/coverage/validate std_srvs/srv/Trigger {}

# 3. Start robot motion.
ros2 service call /sweepi_robot_manager/coverage/start std_srvs/srv/Trigger {}
```

With `auto_start: true`, the manager launches coverage and starts motion automatically after the path, AMCL initial pose, TF, and Nav2 costmaps are ready.

Coverage uses the installed FollowPath params file:

```text
install/sweepi_coverage/share/sweepi_coverage/config/coverage_follow_path_params.yaml
```

Verify the dynamic bypass parameters on the running node:

```bash
ros2 param get /coverage_follow_path_executor_node dynamic_rejoin_max_search_distance_m
ros2 param get /coverage_follow_path_executor_node dynamic_progress_search_forward_m
ros2 param get /coverage_follow_path_executor_node dynamic_max_rejoin_candidates
ros2 param get /coverage_follow_path_executor_node dynamic_collision_check_radius_m
```

Stop the active task launch stack:

```bash
ros2 service call /sweepi_robot_manager/stop_task std_srvs/srv/Trigger {}
```

Exploration controls:

```bash
ros2 service call /sweepi_robot_manager/exploration/start_auto std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/exploration/manual std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/exploration/stop std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/exploration/stop_and_save std_srvs/srv/Trigger {}
```

Coverage controls:

```bash
ros2 service call /sweepi_robot_manager/coverage/validate std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/coverage/start std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/coverage/pause std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/coverage/continue std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/coverage/stop std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/coverage/return_home std_srvs/srv/Trigger {}
ros2 service call /sweepi_robot_manager/coverage/reset std_srvs/srv/Trigger {}
```

Status:

```bash
ros2 topic echo /sweepi_robot_manager/status
```

When coverage reaches a final status after any cleanup pass, the manager records
the used map, final coverage status, elapsed time, latest `/coverage_stats`, and
latest `/coverage_map` cell summary. It then stops the coverage launch stack and
returns to `idle`, so another exploration or coverage task can be started.
Late Nav2 `CANCELED` results from internal dynamic-bypass or cleanup goal swaps
are ignored for automatic completion; the manager waits for `SUCCEEDED`,
`COMPLETED_WITH_SKIPS`, `FAILED`, or `BLOCKED_DYNAMIC_OBJECT`.

Read the retained coverage result:

```bash
ros2 topic echo /sweepi_robot_manager/coverage/last_summary --once
ros2 service call /sweepi_robot_manager/coverage/last_summary std_srvs/srv/Trigger {}
```

## Notes

- `/sweepi_robot_manager/start_exploration` starts Nav2 navigation, SLAM Toolbox through `sweepi_exploration`, and the wavefront explorer.
- `/sweepi_robot_manager/start_coverage` starts Nav2 with the coverage package config and the FollowPath coverage stack. It can transition directly from an active exploration launch.
- `/sweepi_robot_manager/stop_task` shuts down the active exploration or coverage launch stack. Completed coverage tasks are shut down automatically after the final status settles.
- The task control services forward stable API-facing commands to the lower-level package services.
