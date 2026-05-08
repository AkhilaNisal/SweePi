# 🗺️ SweePi SLAM Package

## Overview

The **sweepi_slam** package handles Simultaneous Localization and Mapping (SLAM) for the SweePi autonomous cleaning robot. It uses **SLAM Toolbox** (based on Cartographer/Karto) to build real-time maps while simultaneously localizing the robot within the environment. This package is essential for autonomous navigation without predefined maps.

## Package Purpose

- **Online SLAM Mapping**: Real-time map creation during robot exploration
- **Robot Localization**: Determine robot position relative to built map
- **Loop Closure Detection**: Detect when robot revisits areas and correct drift
- **Map Persistence**: Save/load maps for reuse in navigation tasks
- **ROS 2 Integration**: Full ROS 2 lifecycle management

## Dependencies

### Core ROS 2
- `rclcpp` - C++ client library
- `sensor_msgs` - Sensor messages (LaserScan)
- `nav_msgs` - Navigation messages (OccupancyGrid, etc.)
- `geometry_msgs` - Geometric transforms
- `tf2_ros` - Transform management
- `std_msgs` - Standard message types

### SLAM
- `slam_toolbox` - SLAM algorithm and toolbox
- `nav2_map_server` - Map loading and saving utilities

### Visualization
- `rviz2` - ROS 2 visualization
- `visualization_msgs` - Visualization marker messages

## Package Structure

```
sweepi_slam/
├── CMakeLists.txt                           # Build configuration
├── package.xml                              # Package metadata
├── launch/
│   └── slam_toolbox.launch.py               # SLAM Toolbox launcher
├── config/
│   └── mapper_params_online_async.yaml      # SLAM tuning parameters
├── rviz/
│   └── slam_config.rviz                     # RViz SLAM visualization config
├── scripts/
│   ├── save_map.sh                          # Save current map to disk
│   └── load_map.sh                          # Load saved map from disk
└── maps/
    └── (Saved map files: .pgm, .yaml)
```

## 📝 File Descriptions

| File | Purpose | Size |
|------|---------|------|
| `slam_toolbox.launch.py` | Launches SLAM Toolbox node with SweePi config | 106 lines |
| `mapper_params_online_async.yaml` | **SLAM algorithm parameters** | 74 lines |
| `save_map.sh` | Bash script to save current map with timestamp | 33 lines |
| `load_map.sh` | Bash script to load saved map for localization | 33 lines |
| `slam_config.rviz` | RViz configuration for SLAM visualization | Config |

---

## 🎯 How to Use

### Basic SLAM Mapping

```bash
# Terminal 1: Launch Gazebo with robot and SLAM
ros2 launch sweepi_bringup gazebo.launch.xml

# Robot will automatically start mapping with SLAM Toolbox
# Drive robot around to explore environment

# Terminal 2: (Optional) Monitor SLAM in separate RViz
ros2 launch sweepi_slam slam_toolbox.launch.py
```

### Save Mapped Area

```bash
# Save map to file
./src/sweepi_slam/scripts/save_map.sh

# Or use map_saver directly
ros2 run nav2_map_server map_saver_cli -f my_map
```

**Output files**:
- `my_map.pgm` - Occupancy grid image (gray = free, black = obstacle)
- `my_map.yaml` - Map metadata (origin, resolution, etc.)

### Load Saved Map

```bash
# Load map for localization-only mode
./src/sweepi_slam/scripts/load_map.sh my_map

# Or launch with map:
ros2 launch sweepi_slam slam_toolbox.launch.py mode:=localization
```

### View SLAM Status

```bash
# List SLAM topics
ros2 topic list | grep slam

# View map
ros2 topic echo /map | head -20

# View pose estimates
ros2 topic echo /pose
```

### Interactive SLAM Commands

```bash
# Reset mapping (clear current map)
ros2 service call /slam_toolbox/reset_map slam_toolbox/srv/ResetMap

# Pause/resume mapping
ros2 service call /slam_toolbox/pause_new_measurements slam_toolbox/srv/PauseNewMeasurements

# Force loop closure
ros2 service call /slam_toolbox/force_loop_closure slam_toolbox/srv/ForceLoopClosure

# Toggle interactive mode
ros2 service call /slam_toolbox/toggle_interactive_mode slam_toolbox/srv/ToggleInteractiveMode
```

---

## 📚 SLAM Concepts

### Mapping Modes

1. **Online Mapping** (Default)
   - Robot actively builds map while exploring
   - Continuous localization against growing map
   - Loop closure detection corrects drift over time

2. **Localization Only**
   - Uses pre-saved map
   - Only localizes robot position
   - No new map updates

3. **Offline (Post-processing)**
   - Process recorded sensor data
   - Generate optimized map after exploration

---

## ⚙️ Tunable Parameters (mapper_params_online_async.yaml)

### Critical Parameters for SweePi

| Parameter | Current | Range | Description | Tuning Impact |
|-----------|---------|-------|-------------|---------------|
| `mode` | `mapping` | mapping/localization | SLAM operating mode | **Switch for different use cases** |
| `scan_topic` | `/scan` | - | LiDAR topic name | Must match your laser scanner |
| `resolution` | 0.05 m | 0.01-0.1 m | Map grid cell size | Lower = more detail (more CPU), Higher = faster |
| `throttle_scans` | 1 | 1-5 | Process every Nth scan | Increase to reduce CPU load |
| `transform_publish_period` | 0.02 s | 0.01-0.1 s | TF broadcast frequency | Lower = smoother updates |
| `map_update_interval` | 2.0 s | 0.5-10.0 s | How often to update map | Lower = real-time, Higher = efficient |

### Sensor Parameters

| Parameter | Current | Description | Tuning |
|-----------|---------|-------------|--------|
| `odom_frame` | odom | Odometry frame name | Keep consistent with robot |
| `map_frame` | map | Global map frame | Standard ROS convention |
| `base_frame` | base_footprint | Robot base frame | Keep consistent with URDF |
| `min_laser_range` | 0.1 m | Ignore closer readings | Increase for noisy surfaces |
| `max_laser_range` | 12.0 m | Ignore distant readings | **Match your LiDAR specs** |

### Motion Parameters (Loop Closure)

| Parameter | Current | Range | Description | Effect |
|-----------|---------|-------|-------------|--------|
| `minimum_travel_distance` | 0.1 m | 0.05-0.5 m | Min linear movement before new scan | Lower = more scans, Higher = sparse |
| `minimum_travel_heading` | 0.1 rad | 0.05-0.3 rad | Min rotation before new scan | Lower = more scans at turns |
| `minimum_time_interval` | 0.5 s | 0.1-2.0 s | Min time between scans | Prevents rapid re-scanning |

**Slow, detailed mapping**:
```yaml
minimum_travel_distance: 0.05    # Frequent scans
minimum_travel_heading: 0.05     # Capture all turns
throttle_scans: 1                # Process all scans
map_update_interval: 1.0         # Frequent updates
```

### Loop Closure Parameters

| Parameter | Current | Description | Tuning |
|-----------|---------|-------------|--------|
| `do_loop_closing` | true | Enable loop closure | Keep true for drift correction |
| `loop_search_maximum_distance` | 3.0 m | Search radius for loop closure | Increase for larger areas |
| `loop_match_minimum_chain_size` | 10 | Min scans to confirm loop | Increase for confidence |
| `loop_match_minimum_response_coarse` | 0.35 | Coarse search threshold | Lower = more aggressive |
| `loop_match_minimum_response_fine` | 0.45 | Fine search threshold | Lower = more aggressive |

**Aggressive loop closure (better drift correction)**:
```yaml
loop_search_maximum_distance: 5.0         # Increased search radius
loop_match_minimum_chain_size: 5          # Reduced chain requirement
loop_match_minimum_response_coarse: 0.3   # More aggressive coarse
loop_match_minimum_response_fine: 0.4     # More aggressive fine
```

### Solver Parameters

| Parameter | Current | Description |
|-----------|---------|-------------|
| `solver_plugin` | solver_plugins::CeresSolver | Optimization engine |
| `ceres_linear_solver` | SPARSE_NORMAL_CHOLESKY | Linear algebra solver |
| `ceres_trust_strategy` | LEVENBERG_MARQUARDT | Trust region strategy |

---

## 📊 Performance Tuning Guide

### Slow/Laggy Mapping

**Symptoms**: High CPU, RViz stutters, map slow to update

**Solutions**:
```yaml
throttle_scans: 3          # Process every 3rd scan
resolution: 0.1            # Reduce map detail
map_update_interval: 5.0   # Less frequent updates
minimum_travel_distance: 0.2  # Fewer scans
```

### Drift/Odometry Errors

**Symptoms**: Map becomes misaligned after exploration, lines don't match

**Solutions**:
```yaml
loop_match_minimum_response_coarse: 0.25  # More aggressive loop closure
loop_search_maximum_distance: 5.0         # Search larger area
minimum_travel_distance: 0.05             # More frequent scans
```

### False Loop Closures

**Symptoms**: Map jumps/warps, robot teleports on map

**Solutions**:
```yaml
loop_match_minimum_response_fine: 0.5     # Stricter matching
loop_match_minimum_chain_size: 15         # More confirmations
correlation_search_space_resolution: 0.005  # Finer search grid
```

### CPU Intensive

**Symptoms**: CPU at 100%, high memory, ROS messages delayed

**Solutions**:
```yaml
throttle_scans: 5          # Skip more scans
resolution: 0.15           # Coarser maps
update_rate: 50            # Reduce processing rate
transform_publish_period: 0.05  # Less frequent TF
```

---

## 📋 Map Files Format

### *.pgm (Occupancy Grid Image)
- Grayscale image where pixel brightness = occupancy
- White (255) = free space
- Black (0) = occupied
- Gray (127) = unknown

### *.yaml (Map Metadata)
```yaml
image: map.pgm              # Image filename
resolution: 0.05            # Meters per cell
origin: [-2.5, -2.5, 0]     # Map origin in meters
occupied_thresh: 0.65       # Occupancy threshold
free_thresh: 0.25           # Free space threshold
negate: 0                    # Don't invert colors
```

---

## 🚨 Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Map not building | SLAM node not starting | Check launch file, verify `