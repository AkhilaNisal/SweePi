# sweepi_coverage

The package has two coverage execution modes:

- Old waypoint mode: `/coverage_path` -> `/coverage_waypoints` -> Nav2 `NavigateThroughPoses`.
- New FollowPath mode: `/coverage_path` -> Nav2 `FollowPath`.

The waypoint mode is still available in `coverage_executor_node.py` and
`coverage_system.launch.py` for comparison. The FollowPath mode is added beside it
and does not convert, reorder, batch, or pick a nearest waypoint from the coverage
path.

## Why FollowPath

Coverage paths are already planned as continuous strips. Sending those strips as
waypoint batches asks Nav2 to move between goal poses, which can trigger replanning
around nearby objects and leave uncovered patches. FollowPath sends the complete
`nav_msgs/Path` to the controller so Nav2 tracks the predefined path continuously.
The controller and local costmap can still stop or fail the action when the path is
actually unsafe.

## Reachable Cleanup Paths

The planner separates coverage cells from travel cells. Uncovered cells decide
what still needs to be cleaned, while safe travel cells are used only for
connectors between regions and from the robot's current pose into a cleanup
region. This keeps the first generated coverage path frozen during normal
execution, then lets the cleanup pass reach missed but accessible cells without
publishing a path whose first reachable pose is too far from the robot.

## Launch

Start Nav2 with the saved map you want to cover. The normal path is to pass the
same map name that was saved by exploration:

```bash
ros2 launch sweepi_coverage nav2_bringup.launch.py map_name:=kitchen_first_floor
```

This loads:

```text
~/SweePi/maps/kitchen_first_floor.yaml
```

You can still override the full map path when needed:

```bash
ros2 launch sweepi_coverage nav2_bringup.launch.py \
  map_name:=kitchen_first_floor \
  map:=/absolute/path/to/map.yaml
```

Start the FollowPath coverage stack:

```bash
ros2 launch sweepi_coverage coverage_follow_path.launch.py
```

Optional arguments:

```bash
ros2 launch sweepi_coverage coverage_follow_path.launch.py use_sim_time:=true auto_start:=false
ros2 launch sweepi_coverage coverage_follow_path.launch.py params_file:=/path/to/coverage_follow_path_params.yaml
```

The default params live in:

```text
src/sweepi_coverage/config/coverage_follow_path_params.yaml
```

When coverage is started through `sweepi_robot_manager`, the manager launch passes
the same installed config file into `coverage_follow_path.launch.py`:

```text
install/sweepi_coverage/share/sweepi_coverage/config/coverage_follow_path_params.yaml
```

After rebuilding and sourcing the workspace, verify the running executor is using
the intended dynamic-bypass values:

```bash
ros2 param get /coverage_follow_path_executor_node dynamic_rejoin_max_search_distance_m
ros2 param get /coverage_follow_path_executor_node dynamic_progress_search_forward_m
ros2 param get /coverage_follow_path_executor_node dynamic_max_rejoin_candidates
ros2 param get /coverage_follow_path_executor_node dynamic_collision_check_radius_m
```

Expected values:

```text
dynamic_rejoin_max_search_distance_m: 5.0
dynamic_progress_search_forward_m: 5.0
dynamic_max_rejoin_candidates: 100
dynamic_collision_check_radius_m: 0.25
```

The executor also logs these loaded dynamic obstacle parameters at startup.

## Start And Runtime Controls

Start execution with the latest valid `/coverage_path`:

```bash
ros2 service call /start_coverage_follow_path std_srvs/srv/Trigger {}
```

Pause at the current location. This cancels the active FollowPath goal and
publishes zero velocity:

```bash
ros2 service call /pause_coverage_follow_path std_srvs/srv/Trigger {}
```

Continue coverage after a pause. The executor keeps the original coverage path
and restarts from the nearest valid path pose using the same initial-position
selection logic as normal start:

```bash
ros2 service call /continue_coverage_follow_path std_srvs/srv/Trigger {}
```

Stop coverage and prevent further coverage execution until reset:

```bash
ros2 service call /stop_coverage_follow_path std_srvs/srv/Trigger {}
```

Clear the FollowPath executor cache while the coverage stack is still active:

```bash
ros2 service call /reset_coverage_follow_path std_srvs/srv/Trigger {}
```

When running through `sweepi_robot_manager`, prefer the manager reset service.
It clears `/coverage_map`, `/coverage_path`, planner markers, and executor cache,
then returns the manager to `idle`:

```bash
ros2 service call /sweepi_robot_manager/coverage/reset std_srvs/srv/Trigger {}
```

Return home. The home pose is recorded from the robot pose when coverage first
starts. Return home stops coverage, cancels the active FollowPath goal, and sends
Nav2 `NavigateToPose` back to that initial pose:

```bash
ros2 service call /return_home_coverage_follow_path std_srvs/srv/Trigger {}
```

The older cancel service is still available for direct cancellation of the active
SmoothPath or FollowPath action:

```bash
ros2 service call /cancel_coverage_follow_path std_srvs/srv/Trigger {}
```

## Inspect

Useful topics and actions:

```bash
ros2 topic echo /local_costmap/costmap --once
ros2 topic echo /coverage_execution_status
ros2 topic echo /coverage_dynamic_skip_status
ros2 topic echo /coverage_debug_info
ros2 topic echo /coverage_nav2_feedback
ros2 action list | grep follow
ros2 action info /follow_path
ros2 service call /validate_coverage_follow_path std_srvs/srv/Trigger {}
ros2 service call /start_coverage_follow_path std_srvs/srv/Trigger {}
ros2 service call /pause_coverage_follow_path std_srvs/srv/Trigger {}
ros2 service call /continue_coverage_follow_path std_srvs/srv/Trigger {}
ros2 service call /stop_coverage_follow_path std_srvs/srv/Trigger {}
ros2 service call /return_home_coverage_follow_path std_srvs/srv/Trigger {}
```

RViz/debug topics:

```text
/coverage_path
/coverage_active_path
/coverage_smoothed_path
/coverage_skipped_segments
/coverage_path_markers
/coverage_debug_markers
/coverage_execution_status
/coverage_nav2_feedback
/coverage_debug_info
/local_costmap/costmap
```

## FollowPath Requires Continuous `/coverage_path`

FollowPath executes `nav_msgs/Path` as one continuous path. It cannot execute
disconnected strips with large jumps between consecutive poses. A large jump can
cause local validation failure or a Nav2 `INVALID_PATH` result.

Validate the cached path before starting:

```bash
ros2 service call /validate_coverage_follow_path std_srvs/srv/Trigger {}
ros2 topic echo /coverage_debug_info --once
```

Add `/coverage_debug_markers` in RViz to see the exact jump start, jump end, red
jump line, robot pose, first pose, last pose, and nearest path pose.

## Costmap-Aware Coverage Planning

The FollowPath launch config can filter coverage cells with Nav2's global costmap
before publishing `/coverage_path`:

```yaml
coverage_planner_node:
  ros__parameters:
    use_nav_costmap_for_planning: true
    nav_costmap_topic: "/global_costmap/costmap"
    max_allowed_nav_cost: 90
    treat_unknown_cost_as_blocked: true
```

This makes the planner cover cells that still need sweeping and are currently
drivable according to Nav2's global/static view. The planner keeps the real robot
size and coverage margin, so known mapped obstacles remain conservatively avoided.

For FollowPath execution, the default config freezes `/coverage_path` after the
first valid costmap-aware plan:

```yaml
coverage_planner_node:
  ros__parameters:
    freeze_path_after_first_valid_plan: true
    wait_for_nav_costmap_before_planning: true
    wait_for_robot_pose_before_planning: true
```

This keeps the path stable while the robot moves and prevents freezing an early
fallback path before `/global_costmap/costmap` or `map -> base_link` TF is ready.
Restart the coverage launch, or disable these parameters, when you intentionally
want a newly generated coverage path.

## Dynamic Local Obstacle Handling

The FollowPath executor keeps the coverage path frozen and lets normal walls be
handled by the original `FollowPath` goal plus the Nav2 local controller. Dynamic
skip is for local-only obstacles, such as a box, chair, person, or wall that is
missing from the saved map, that appear in `/local_costmap/costmap` but are not
occupied in the saved `/map`.

Inflated high-cost cells are not enough to trigger a skip. With the default
configuration, the detector requires local cost `100`; cost `99` inflation near a
known wall is ignored. If Nav2 reports collision/progress failure, or if the
same static-map-free `99` inscribed band persists across repeated checks, the
executor treats it as a local-only map mismatch and tries the same validated
bypass/rejoin flow. A temporary bypass is generated only after confirmation. The
replacement path is validated before the old `FollowPath` goal is canceled using
the local costmap for the temporary bypass and the saved map to reject known
static walls. Live global costmap obstacle-layer cells that are static-map-free
are treated as part of the confirmed dynamic object instead of automatically
vetoing the candidate.

The replacement path starts at the current robot pose, follows a temporary local
bypass, then rejoins the original frozen coverage path from the selected rejoin
index onward. Dynamic bypass is intentionally conservative: a connector is
rejected when it would be a large shortcut compared with the frozen coverage path
section being replaced, because that would skip accessible coverage strips.
Skipped object-covered sections are not retried and are not counted as cleaned.
If no safe rejoin or valid compact bypass can be found after the confirmed
obstacle and exhaustive local rejoin search, the active goal is canceled and
`/coverage_execution_status` becomes
`BLOCKED_DYNAMIC_OBJECT` instead of continuing into the object. If any section
was skipped, the final status is `COMPLETED_WITH_SKIPS`; otherwise the task
finishes as `SUCCEEDED`.

Useful checks:

```bash
ros2 topic echo /coverage_execution_status
ros2 topic echo /coverage_dynamic_skip_status
ros2 topic echo /coverage_debug_info
ros2 topic echo /local_costmap/costmap --once
ros2 topic echo /map --once
ros2 service call /validate_coverage_follow_path std_srvs/srv/Trigger {}
ros2 service call /start_coverage_follow_path std_srvs/srv/Trigger {}
```

Add these in RViz:

```text
/coverage_path
/coverage_active_path
/coverage_smoothed_path
/coverage_skipped_segments
/coverage_debug_markers
/local_costmap/costmap
/map
```

Test cases:

1. Run without new objects:
   - The robot should handle wall junctions normally.
   - Dynamic skip should not trigger near known walls.

2. Add a box on the coverage path:
   - Dynamic skip should trigger after confirmation.
   - A temporary bypass should be generated.
   - The robot should rejoin the original coverage path.
   - Status should return to `EXECUTING`.

3. Wall/corner after a box:
   - Dynamic skip should not trigger from inflated cost `99`.
   - Known walls should be ignored by the dynamic detector.
   - The robot should continue using normal `FollowPath`.

4. Invalid candidate path:
   - The candidate should be rejected before canceling the current `FollowPath`.
   - The current goal should continue.
   - The robot should not enter `FAILED` because of a bad candidate.

Keep `robot_radius_m: 0.20`, `coverage_safety_margin_m: 0.10`, and
`inflation_radius_m: 0.30`. The dynamic skip feature is only for unexpected local
obstacles; it is not a reason to shrink the planner margin or make the robot
drive closer to known walls. Nav2 local collision detection, obstacle layers, and
inflation remain enabled.

## Nav2 Controller Guidance

Use a FollowPath controller plugin that is tuned for slow, close path tracking. A
good starting point for Regulated Pure Pursuit is:

```yaml
controller_server:
  ros__parameters:
    controller_plugins: ["FollowPath"]

    FollowPath:
      plugin: "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
      desired_linear_vel: 0.12
      lookahead_dist: 0.25
      min_lookahead_dist: 0.12
      max_lookahead_dist: 0.35
      use_velocity_scaled_lookahead_dist: false
      use_collision_detection: true
      max_allowed_time_to_collision_up_to_carrot: 0.5
      use_regulated_linear_velocity_scaling: true
      use_cost_regulated_linear_velocity_scaling: false
      use_rotate_to_heading: true
      allow_reversing: false
```

Local costmap notes:

- Keep collision checking enabled.
- Do not reduce `robot_radius` below the real robot radius.
- For SweePi, keep robot radius at `0.20 m` and coverage safety margin at `0.10 m`.
- The coverage path should stay at least `robot_radius + safety_margin` away from obstacle cells.
- Keep inflation radius at `0.30 m` unless there is a separate, safety-reviewed tuning change.
