# 🤖 SweePi Exploration Package

Autonomous frontier-based exploration for the SweePi robot.  
Integrates **SLAM Toolbox** (via `sweepi_slam`) with **Nav2** for collision-free
path planning and obstacle avoidance.

---

## Table of Contents

1. [Overview](#overview)
2. [Package Structure](#package-structure)
3. [How It Works](#how-it-works)
4. [Dependencies](#dependencies)
5. [Launch Instructions](#launch-instructions)
6. [Configuration](#configuration)
7. [Nav2 Debugging Guide](#nav2-debugging-guide)
8. [Troubleshooting](#troubleshooting)
9. [Saving the Map](#saving-the-map)

---

## Overview

| Feature | Old package | **This package** |
|---------|-------------|-----------------|
| Path planning | ❌ None (straight-line) | ✅ Nav2 global planner |
| Obstacle avoidance | ❌ None | ✅ Nav2 local planner (DWB) |
| Reachability check | ❌ None | ✅ `ComputePathToPose` before each goal |
| SLAM | ❌ Duplicated setup | ✅ Reuses `sweepi_slam` |
| Failure recovery | ❌ None | ✅ Marks failed frontiers, tries next |

---

## Package Structure

```
sweepi_exploration/
├── CMakeLists.txt
├── package.xml
├── README.md
├── config/
│   ├── nav2_params.yaml          # Full Nav2 parameter set (debug-friendly)
│   ├── planner_server.yaml       # NavFn global planner config
│   └── controller_server.yaml   # DWB local planner config
├── launch/
│   └── exploration.launch.py    # Main launch file
├── maps/                         # Saved maps are written here
└── sweepi_exploration/
    ├── __init__.py
    └── exploration_manager.py   # Frontier detection + Nav2 goals
```

---

## How It Works

```
sweepi_slam ──► /map ──► ExplorationManager
                               │
                    detect frontier cells
                    cluster + filter
                               │
                    ComputePathToPose  ◄── Nav2 planner
                    (reachability check)
                               │
                    NavigateToPose ────► Nav2 controller
                                         (DWB local planner)
                                              │
                                         /cmd_vel ──► robot
```

1. **SLAM Toolbox** (from `sweepi_slam`) publishes the occupancy grid on `/map`.
2. **Exploration Manager** detects *frontier cells* — free cells adjacent to unknown cells.
3. Frontier cells are clustered and centroids computed.
4. Each candidate frontier is checked for reachability via Nav2's
   `ComputePathToPose` action (no path = skip frontier).
5. The closest reachable frontier is sent as a `NavigateToPose` goal.
6. Nav2's DWB local planner follows the path while avoiding obstacles.
7. On failure, the frontier is blacklisted and the next one is tried.
8. Exploration ends when no more reachable frontiers exist — the map is saved.

---

## Dependencies

```
Nav2:
  nav2_bringup          nav2_bt_navigator
  nav2_planner          nav2_controller
  nav2_behaviors        nav2_lifecycle_manager
  nav2_map_server

SLAM:
  sweepi_slam           slam_toolbox

ROS 2:
  rclpy  nav_msgs  geometry_msgs  visualization_msgs
  tf2    tf2_ros   tf2_geometry_msgs  action_msgs
```

Install Nav2 (if not already installed):

```bash
sudo apt install ros-humble-nav2-bringup ros-humble-nav2-* \
                 ros-humble-slam-toolbox
```

---

## Launch Instructions

### Step 1 – Start Gazebo simulation

```bash
ros2 launch sweepi_bringup gazebo.launch.xml
```

### Step 2 – Start autonomous exploration

```bash
ros2 launch sweepi_exploration exploration.launch.py
```

This single command starts:
- **SLAM Toolbox** (via `sweepi_slam`)
- **Nav2** stack (planner, controller, behavior server, BT navigator)
- **Exploration Manager** (frontier detection + goal publishing)

### Step 3 – Visualise in RViz

```bash
ros2 launch sweepi_slam slam_toolbox.launch.py   # optional separate RViz
```

Or open RViz manually and add:

| Display | Topic |
|---------|-------|
| Map | `/map` |
| Global Costmap | `/global_costmap/costmap` |
| Local Costmap | `/local_costmap/costmap` |
| Path | `/plan` |
| MarkerArray | `/exploration/frontiers` |
| Marker | `/exploration/goal` |

---

## Configuration

### Exploration parameters (`exploration.launch.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `frontier_min_size` | `5` cells | Minimum cluster size to be a valid frontier |
| `cluster_distance` | `0.5` m | Max distance between cells in a cluster |
| `goal_tolerance` | `0.3` m | Distance threshold to consider goal reached |
| `exploration_frequency` | `3.0` s | How often to search for new frontiers |
| `nav_timeout` | `30.0` s | Nav2 action timeout |

Override on launch:

```bash
ros2 launch sweepi_exploration exploration.launch.py frontier_min_size:=10 cluster_distance:=0.8
```

### Nav2 parameters (`config/nav2_params.yaml`)

Key parameters to tune for your robot:

```yaml
controller_server:
  ros__parameters:
    FollowPath:
      max_vel_x: 0.26       # Max forward speed (m/s) – reduce if robot oscillates
      max_vel_theta: 1.0    # Max rotation speed (rad/s)
      sim_time: 1.7         # DWB trajectory simulation horizon (s)

global_costmap:
  global_costmap:
    ros__parameters:
      robot_radius: 0.22    # IMPORTANT: set to your actual robot radius

local_costmap:
  local_costmap:
    ros__parameters:
      robot_radius: 0.22
      inflation_layer:
        inflation_radius: 0.55  # Set to robot_radius + safety margin
```

---

## Nav2 Debugging Guide

### Check Nav2 nodes are running

```bash
ros2 node list | grep nav2
```

Expected nodes:
```
/bt_navigator
/controller_server
/planner_server
/behavior_server
/lifecycle_manager_navigation
```

### Check Nav2 lifecycle state

```bash
ros2 lifecycle list /planner_server
ros2 lifecycle list /controller_server
```

Both should be in the **active** state.

### View Nav2 logs

```bash
# All Nav2 output
ros2 launch sweepi_exploration exploration.launch.py 2>&1 | grep -i "nav2\|planner\|controller\|error\|warn"

# Just the exploration manager
ros2 run sweepi_exploration exploration_manager.py --ros-args -p use_sim_time:=true
```

### Test Nav2 manually (without exploration)

```bash
# Send a single navigation goal to verify Nav2 is working
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{ pose: { header: { frame_id: 'map' }, pose: { position: { x: 1.0, y: 0.0, z: 0.0 }, orientation: { w: 1.0 } } } }"
```

### Check costmaps

```bash
# Verify sensor data is reaching the costmap
ros2 topic echo /local_costmap/costmap_updates --once
ros2 topic echo /global_costmap/costmap_updates --once
```

### Check TF tree

```bash
ros2 run tf2_tools view_frames
# Verify chain: map → odom → base_footprint
```

### Common Nav2 errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Planner server not active` | Lifecycle not started | Check `lifecycle_manager` is running |
| `Could not get robot pose` | TF chain broken | Check SLAM is publishing `map→odom` |
| `Failed to get plan` | Robot in unknown/obstacle space | Increase `tolerance` in planner config |
| `DWB failed to produce path` | Costmap blocking | Reduce `inflation_radius` |
| `Transform timeout` | Clock skew | Set `use_sim_time: true` everywhere |
| `Goal is outside costmap` | Costmap too small | Increase `width`/`height` in local costmap |

---

## Troubleshooting

### Robot not moving

1. Check `/cmd_vel` is being published:  
   `ros2 topic echo /cmd_vel`
2. Check Nav2 controller is active:  
   `ros2 lifecycle list /controller_server`
3. Check the robot accepts `/cmd_vel`:  
   Gazebo bridge must map `/cmd_vel` → `DiffDrive` plugin

### Exploration immediately finishes

- Increase `frontier_min_size` threshold (fewer noise frontiers)
- Check the map is being built: `ros2 topic echo /map --once`
- Check SLAM is running: `ros2 node list | grep slam`

### Navigation always fails

1. Test manually with a known-good pose (see above)
2. Check costmaps are populated with LiDAR data
3. Try setting `allow_unknown: true` in planner config
4. Reduce robot radius in costmap params if robot is large

### Nav2 crashes with "No BT XML file"

The package uses Nav2's built-in default behaviour trees.  
If Nav2 cannot find them, install the full nav2 package:

```bash
sudo apt install ros-humble-nav2-bt-navigator
```

---

## Saving the Map

The map is saved automatically when exploration finishes.  
To save manually at any time:

```bash
# Using the sweepi_slam helper script
bash $(ros2 pkg prefix sweepi_slam)/lib/sweepi_slam/save_map.sh

# Or directly with map_saver_cli
ros2 run nav2_map_server map_saver_cli -f ~/my_map
```

Maps are saved to:  
`<install>/share/sweepi_exploration/maps/sweepi_map.{yaml,pgm}`
