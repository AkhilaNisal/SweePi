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

## Launch

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

## Start And Cancel

Start execution with the latest valid `/coverage_path`:

```bash
ros2 service call /start_coverage_follow_path std_srvs/srv/Trigger {}
```

Cancel the active FollowPath goal:

```bash
ros2 service call /cancel_coverage_follow_path std_srvs/srv/Trigger {}
```

## Inspect

Useful topics and actions:

```bash
ros2 topic echo /coverage_execution_status
ros2 topic echo /coverage_nav2_feedback
ros2 action list | grep follow
ros2 action info /follow_path
```

RViz/debug topics:

```text
/coverage_path
/coverage_active_path
/coverage_path_markers
/coverage_debug_markers
/coverage_execution_status
/coverage_nav2_feedback
/coverage_debug_info
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
drivable according to Nav2. Unexpected objects that appear in the costmap are
temporarily excluded instead of being marked covered, so they can be attempted
later if they become reachable again.

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

If Nav2 returns `FAILED_TO_MAKE_PROGRESS`, the FollowPath executor can optionally
queue the newest replanned path, but this is disabled by default because it changes
the active coverage plan:

```yaml
coverage_follow_path_executor_node:
  ros__parameters:
    auto_restart_on_failed_progress: false
    max_failed_progress_restarts: 3
```

Keep `robot_radius` at the real robot size. To move nearer to walls safely, tune
inflation radius and cost scaling rather than shrinking the robot footprint below
reality.

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
- Reduce excessive inflation only if the planner already guarantees clearance.
- For SweePi, use robot radius around `0.18-0.20 m` and safety margin around `0.04 m`.
- The coverage path should stay at least `robot_radius + safety_margin` away from obstacle cells.
- Inflation radius should not make valid near-object coverage strips too expensive.
