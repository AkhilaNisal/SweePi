# 🚀 SweePi Bringup Package

## Overview

The **sweepi_bringup** package is the main entry point for launching the SweePi autonomous cleaning robot. It handles robot initialization, simulation environment setup, Gazebo integration, visualization, and system orchestration. This package bridges Gazebo simulation with ROS 2, manages controller configuration, and coordinates all robot subsystems.

## Package Purpose

- **Robot Launch Management**: Orchestrates the startup of all robot components
- **Gazebo Simulation**: Sets up Gazebo physics simulator with the robot world
- **Visualization**: Configures RViz for real-time visualization of robot state
- **Sensor Bridging**: Establishes communication between Gazebo and ROS 2 sensors
- **Controller Management**: Initializes differential drive controllers for wheel actuation
- **SLAM Integration**: Integrates with the SLAM system for autonomous mapping

## Dependencies

### Core ROS 2
- `rclcpp` - C++ ROS 2 client library
- `geometry_msgs` - Geometric messages (Twist, Pose, etc.)
- `sensor_msgs` - Sensor data messages (LaserScan, Image, Imu, etc.)
- `nav_msgs` - Navigation messages (Odometry, etc.)
- `tf2` / `tf2_ros` - Transform library for coordinate frames
- `std_msgs` - Standard message types

### Simulation (Gazebo)
- `gazebo` - Gazebo simulator
- `gazebo_ros` - Gazebo ROS 2 integration
- `gazebo_ros2_control` - Control plugin for Gazebo
- `gz_ros2_control` - Alternative control plugin
- `ros_gz` - ROS-Gazebo bridge utilities
- `ros_gz_sim` - Gazebo simulation launcher
- `ros_gz_bridge` - Topic/service bridging

### Robot Control
- `robot_state_publisher` - Publishes robot TF tree
- `joint_state_publisher` - Publishes joint states
- `urdf` - Unified Robot Description Format support
- `xacro` - XML macro language for URDF
- `controller_manager` - ROS 2 controller framework
- `diff_drive_controller` - Differential drive controller

### Visualization
- `rviz2` - RViz visualization tool
- `rviz_common` - RViz common libraries

### Internal
- `sweepi_description` - Robot URDF/mesh files
- `sweepi_slam` - SLAM subsystem

## Package Structure

```
sweepi_bringup/
├── CMakeLists.txt              # Build configuration
├── package.xml                 # Package metadata
├── launch/
│   ├── gazebo.launch.xml       # Main Gazebo simulation launcher
│   └── rviz.launch.xml         # RViz visualization launcher
├── config/
│   ├── gazebo.bridge.yaml      # ROS-Gazebo topic/service bridge config
│   └── sweepi_controller.yaml  # Controller parameters
├── worlds/
│   └── sweepi_world.world      # Gazebo world definition
└── rviz/
    └── (RViz configuration files)
```

## File Descriptions

| File | Purpose | Key Content |
|------|---------|------------|
| `gazebo.launch.xml` | Main launch file | Starts Gazebo, RViz, bridge, and robot TF support |
| `rviz.launch.xml` | Standalone RViz launcher | Displays robot model in RViz |
| `gazebo.bridge.yaml` | ROS-Gazebo bridge config | Bidirectional topic bridging |
| `sweepi_controller.yaml` | Differential drive config | Wheel parameters and velocity limits |
| `world2.sdf` | Gazebo world file | Environment setup, physics, models, and the built-in SweePi robot |

---

## 🎯 How to Use

### Launch Full Simulation
```bash
# Terminal 1: Start Gazebo simulation with the robot from world2.sdf
ros2 launch sweepi_bringup gazebo.launch.xml
```

### Launch with Custom Parameters
```bash
# Spawn robot at custom position only when using an empty world
ros2 launch sweepi_bringup gazebo.launch.xml spawn_robot:=true x_pose:=1.0 y_pose:=2.0

# Run headless (no GUI)
ros2 launch sweepi_bringup gazebo.launch.xml headless:=true
```

### Standalone RViz
```bash
ros2 launch sweepi_bringup rviz.launch.xml
```

### Control the Robot
```bash
# Publish twist commands (linear and angular velocity)
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "linear: {x: 0.5, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.5}"
```

### View Available Topics
```bash
ros2 topic list
```

### View Transform Tree
```bash
ros2 run tf2_tools view_frames.py
```

---

## ⚙️ Tunable Configurations

### gazebo.bridge.yaml - ROS-Gazebo Bridge Configuration

| Parameter | Current | Description | Tuning |
|-----------|---------|-------------|--------|
| Clock bridge | `/clock` | Synchronizes simulation time | Keep for synchronized simulation |
| Joint States | `/joint_states` | Robot joint positions | Essential for control feedback |
| TF Bridge | `/tf` | Transform tree updates | Keep for proper frame hierarchy |
| Cmd Vel | `/cmd_vel` | Robot velocity commands | Core control input |
| Camera | `/camera/image_raw` | Camera stream | Reduce update rate if CPU limited |
| LIDAR | `/scan` | LiDAR point cloud | Critical for SLAM |
| Odometry | `/odom` | Robot odometry | Essential for localization |

**Reduce camera publish rate** (modify bridge config):
```yaml
- ros_topic_name: "/camera/image_raw"
  gz_topic_name: "/camera/image_raw"
  lazy: true  # Only publish when subscribed
```

### sweepi_controller.yaml - Differential Drive Controller

| Parameter | Current | Range | Description | Tuning |
|-----------|---------|-------|-------------|--------|
| `update_rate` | 100 Hz | 50-200 Hz | Controller update frequency | Increase for faster response |
| `wheel_separation` | 0.300 m | 0.25-0.35 m | Distance between wheels | **Calibrate from actual robot** |
| `wheel_radius` | 0.025 m | 0.020-0.030 m | Wheel radius | **Critical for odometry** |
| `pose_covariance` | 0.001 | - | Position uncertainty | Lower = trust odometry more |
| `linear.x.max_velocity` | 0.5 m/s | 0.1-2.0 m/s | Maximum forward speed | Reduce for stability |
| `angular.z.max_velocity` | 1.0 rad/s | 0.5-3.0 rad/s | Maximum rotation | Adjust for turning |
| `publish_rate` | 50.0 Hz | 10-100 Hz | Odometry publication rate | Lower reduces network load |

**Tune for slower, controlled movement**:
```yaml
diff_drive_controller:
  ros__parameters:
    linear.x.max_velocity: 0.3    # Reduced from 0.5
    angular.z.max_velocity: 0.7   # Reduced from 1.0
    update_rate: 150              # Increased precision
```

**Tune for higher speed exploration**:
```yaml
diff_drive_controller:
  ros__parameters:
    linear.x.max_velocity: 1.0    # Increased from 0.5
    angular.z.max_velocity: 1.5   # Increased from 1.0
```

---

## 🚨 Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Robot doesn't move | Gazebo bridge not active | Verify `gazebo.bridge.yaml` is loaded and check ROS logs |
| Odometry drift | Wrong wheel calibration | Recalibrate `wheel_separation` and `wheel_radius` with actual measurements |
| High CPU usage | Too many bridge topics | Set `lazy: true` for unused topics in bridge config |
| TF tree errors | Missing frame transforms | Check `lidar_scan_frame_fix` node is running in launch file |
| RViz sees no data | Incorrect topic names | Verify bridge config topic names match RViz subscriptions |
| Gazebo crashes | Physics instability | Reduce `update_rate`, check collision geometries |

---

## 📊 Launch Arguments Reference

### gazebo.launch.xml

```bash
ros2 launch sweepi_bringup gazebo.launch.xml \
  use_sim_time:=true \      # Use Gazebo clock (recommended)
  x_pose:=0.0 \             # Initial X position (meters)
  y_pose:=0.0 \             # Initial Y position (meters)
  headless:=false \         # Run without GUI
  spawn_robot:=false        # world2.sdf already contains the robot
```

| Argument | Default | Description |
|----------|---------|-------------|
| `use_sim_time` | true | Use Gazebo/simulation clock instead of system clock |
| `x_pose` | 0.0 | Robot initial X position in world |
| `y_pose` | 0.0 | Robot initial Y position in world |
| `headless` | false | Disable GUI (true = faster, no visual feedback) |
| `spawn_robot` | false | Spawn robot from `robot_description`; keep false for `world2.sdf` to avoid duplicate `/scan` and `/odom` publishers |

---

## 🔧 Performance Optimization

- **Reduce sensor update rates**: Set `lazy: true` for non-critical topics
- **Increase controller update rate**: For more responsive control (CPU cost)
- **Adjust LIDAR range**: Modify bridge if using different sensor
- **Disable visualization**: Run headless for faster simulation
- **Reduce map resolution**: In SLAM config

---

## 📚 References

- [ROS 2 Launch Documentation](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Launch.html)
- [Differential Drive Controller](https://github.com/ros-controls/ros2_controllers)
- [ROS-Gazebo Bridge](https://github.com/gazebosim/ros_gz)
- [Gazebo Documentation](https://gazebosim.org/)
