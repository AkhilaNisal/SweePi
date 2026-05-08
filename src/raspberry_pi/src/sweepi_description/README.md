# 🤖 SweePi Description Package

## Overview

The **sweepi_description** package contains the complete kinematic and visual model of the SweePi autonomous cleaning robot. It defines the robot's structure through URDF (Unified Robot Description Format) files using Xacro macro language, includes 3D mesh files for visualization, and provides RViz configuration files for visualization.

## Package Purpose

- **Robot Definition**: Complete kinematic model in URDF format
- **Sensor Integration**: Definition of cameras, LiDAR, IMU, and cliff sensors
- **Physical Parameters**: Accurate geometric and inertial properties
- **Visualization**: 3D meshes and material definitions
- **Reusability**: Modular Xacro components for flexible configuration

## Dependencies

- `urdf` - Robot description format parser
- `xacro` - XML macro language for URDF templates
- No runtime dependencies (static definition package)

## Package Structure

```
sweepi_description/
├── CMakeLists.txt              # Build configuration
├── package.xml                 # Package metadata
├── urdf/
│   ├── sweepi.urdf.xacro       # Main robot URDF (includes all components)
│   ├── robot_base.xacro        # Robot base geometry and wheels
│   ├── robot_base_gazebo.xacro # Gazebo-specific physics parameters
│   ├── camera.xacro            # Camera sensor definition
│   ├── lidar.xacro             # LiDAR sensor definition
│   ├── imu.xacro               # IMU sensor definition
│   └── cliff_sensors.xacro     # Cliff detection sensors
├── launch/
│   └── display.launch.py        # RViz display launcher
├── rviz/
│   └── urdf_config.rviz         # RViz configuration file
└── meshes/
    └── (3D mesh files for visualization)
```

## 📝 File Descriptions

| File | Purpose | Lines | Description |
|------|---------|-------|-------------|
| `sweepi.urdf.xacro` | Master URDF | 16 | Includes all component definitions |
| `robot_base.xacro` | Base body | 184 | Defines base, wheels, casters, joints, materials, inertia |
| `robot_base_gazebo.xacro` | Gazebo plugins | 42 | Physics, diff-drive controller, joint state publisher |
| `camera.xacro` | Camera sensor | 80 | RGB camera with calibration and noise |
| `lidar.xacro` | LiDAR sensor | 91 | 2D/3D laser scanner configuration |
| `imu.xacro` | IMU sensor | 38 | Accelerometer and gyroscope |
| `cliff_sensors.xacro` | Cliff detection | 158 | Two infrared proximity sensors |
| `display.launch.py` | Launcher | 54 | Starts RViz and publishes robot state |


---

## 🎯 How to Use

### View Robot in RViz
```bash
# Terminal 1: Display robot model
ros2 launch sweepi_description display.launch.py

# Terminal 2: (Optional) Publish dummy joint states
ros2 run joint_state_publisher_gui joint_state_publisher_gui
```

### Generate URDF from Xacro
```bash
# Convert Xacro to URDF
xacro src/sweepi_description/urdf/sweepi.urdf.xacro > sweepi.urdf

# View URDF structure
cat sweepi.urdf
```

### Use in Your Code
```python
import os
from ament_index_python.packages import get_package_share_directory

# Get robot URDF path
urdf_path = os.path.join(
    get_package_share_directory('sweepi_description'),
    'urdf',
    'sweepi.urdf.xacro'
)
```

### Check Transform Tree
```bash
ros2 run tf2_tools view_frames.py  # Generate PDF of TF tree
```

---

## 🤝 Robot Structure & Coordinate Frames

### Transform Tree Hierarchy

```
map
└── odom
    └── base_footprint (origin at ground level)
        └── base_link (main body center)
            ├── left_wheel_link
            ├── right_wheel_link
            ├── front_caster_link
            ├── rear_caster_link
            ├── lidar_link
            │   └── lidar_link_optical
            ├── camera_link
            │   └── camera_link_optical
            ├── imu_link
            ├── cliff_left_link
            └── cliff_right_link
```

### Physical Dimensions

```
BODY:
  Radius: 0.200 m (20 cm)
  Height: 0.100 m (10 cm)
  Ground Clearance: 0.020 m (2 cm)
  Mass: 3.0 kg

DRIVE WHEELS:
  Radius: 0.025 m (2.5 cm)
  Width: 0.020 m (2 cm)
  Separation: 0.300 m (30 cm wheel-to-wheel)
  Mass: 0.15 kg each

CASTERS (Front/Rear):
  Radius: 0.010 m (1 cm)
  Mass: 0.05 kg each
  Offset from center: 0.160 m (16 cm)

SENSORS:
  Camera: Front mounted
  LiDAR: Front-top mounted (0.1m forward)
  IMU: Center mounted (0.05m height)
  Cliff Sensors: Two infrared (front corners)
```

---

## ⚙️ Tunable Parameters

### robot_base.xacro - Geometric Parameters

| Parameter | Current | Description | Tuning |
|-----------|---------|-------------|--------|
| `body_radius` | 0.200 m | Robot body diameter | Adjust for different chassis |
| `body_height` | 0.100 m | Robot height | Affects center of mass |
| `ground_clearance` | 0.020 m | Gap between body and ground | Increase for rough terrain |
| `drive_wheel_radius` | 0.025 m | Wheel size | Affects speed and torque |
| `drive_wheel_width` | 0.020 m | Wheel thickness | Affects traction |
| `wheel_span` | 0.300 m | Distance between wheels | Affects turning radius |
| `caster_offset_x` | 0.160 m | Distance from center | Position of casters |

**Larger robot example**:
```xml
<xacro:property name="body_radius"        value="0.250" />
<xacro:property name="body_height"        value="0.120" />
<xacro:property name="wheel_span"         value="0.350" />
<xacro:property name="drive_wheel_radius" value="0.030" />
```

### Inertial Properties (Mass)

| Component | Current | Adjustable |
|-----------|---------|-----------|
| Base link | 3.0 kg | Yes |
| Wheels | 0.15 kg each | Yes |
| Casters | 0.05 kg each | Yes |

**Lighter robot (faster simulation)**:
```xml
<xacro:body_inertia m="2.5" ... />  <!-- Reduced from 3.0 -->
```

### Sensor Configuration

**Camera (camera.xacro)**:
- Resolution: 640x480
- FOV: 90 degrees
- Update Rate: 20 Hz

**LiDAR (lidar.xacro)**:
- Range: 0.1 - 12.0 m
- Samples: 720 rays
- Update Rate: 10 Hz

**IMU (imu.xacro)**:
- Update Rate: 100 Hz
- Noise: Gaussian (angular: 0.0002, linear: 0.01)

**Cliff Sensors (cliff_sensors.xacro)**:
- Range: 0.01 - 0.25 m
- Update Rate: 30 Hz

---

## 📚 References

- [URDF Documentation](http://wiki.ros.org/urdf)
- [Xacro Documentation](http://wiki.ros.org/xacro)
- [RViz User Guide](https://github.com/ros-visualization/rviz/wiki)
- [Gazebo Simulation](https://gazebosim.org/)
