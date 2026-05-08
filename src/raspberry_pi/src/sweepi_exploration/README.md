# 🤖 SweePi Autonomous Exploration System

[![ROS2](https://img.shields.io/badge/ROS2-Jazzy-blue?logo=ros)](https://docs.ros.org/en/jazzy/)
[![Python](https://img.shields.io/badge/Python-3.10+-green?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

A **complete autonomous frontier exploration system** for the SweePi robot using ROS2, featuring wavefront frontier detection, intelligent proximity-based blocking, and wall offset collision avoidance.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Launch Files](#launch-files)
- [Parameters](#parameters)
- [Usage Examples](#usage-examples)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

**SweePi Exploration** is an autonomous frontier-based exploration system that enables mobile robots to:
- 🗺️ Automatically explore unknown environments
- 🎯 Detect and navigate to frontier areas (boundaries between known and unknown space)
- 🧠 Intelligently block unreachable regions using connectivity checking
- 🛡️ Avoid obstacles and collisions with wall offset algorithms
- 💾 Generate and save occupancy grid maps

### Key Use Cases
- Indoor environment mapping
- Search and rescue operations
- Autonomous inspection missions
- Mobile robot research and development

---

## ✨ Features

### 🔍 **Wavefront Frontier Detection**
- Advanced wavefront algorithm for frontier cell detection
- Clustering and filtering of frontier regions
- Configurable minimum cluster size

### 🧠 **Smart Blocking System**
- **Connectivity-aware blocking**: Only blocks frontiers in the SAME disconnected region as failed areas
- Prevents false positives in complex environments
- Allows exploration of reachable areas separated by obstacles

### 🛡️ **Wall Offset Algorithm**
- Automatically offsets goals away from walls/obstacles
- Ensures robot has adequate clearance before navigation
- Configurable safety margins

### ⏱️ **Intelligent Timeout Management**
- Per-frontier attempt tracking
- Aggressive timeout limits to prevent infinite loops
- Region-based blocking after repeated failures

### 📊 **RViz Visualization**
- Real-time frontier visualization (green markers)
- Unreachable area markers (orange circles)
- Blocked region indicators (red markers)

### 💾 **Automatic Map Saving**
- Saves exploration results as PGM + YAML format
- Compatible with ROS navigation stack
- Timestamped for multiple exploration runs

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Wavefront Explorer Node                       │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐│
│  │  Map Input   │───▶│  Frontier    │───▶│  Goal      ││
│  │ (OccupancyG) │    │ Detection    │    │ Selection  ││
│  └──────────────┘    └──────────────┘    └────────────┘│
│         ▲                    │                    │      │
│         │                    ▼                    ▼      │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐│
│  │ SLAM Toolbox │    │  Filtering   │    │ Wall       ││
│  │   (Map)      │    │  & Blocking  │    │ Offset     ││
│  └──────────────┘    └──────────────┘    └────────────┘│
│         ▲                    │                    │      │
│         │                    ▼                    ▼      │
│  ┌──────────────────────────────────────────────────────┐│
│  │              Nav2 Navigation Stack                   ││
│  │         (NavigateToPose Action Server)               ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Installation

### Prerequisites
- **ROS2 Jazzy** or later
- **Nav2** stack installed
- **SLAM Toolbox** for mapping
- **Python 3.10+**
- **NumPy** for numerical operations

### Clone and Build

```bash
# Clone repository
cd ~/SweePi/src
git clone https://github.com/AkhilaNisal/SweePi.git

# Build the package
cd ~/SweePi
colcon build --packages-select sweepi_exploration

# Source setup
source install/setup.bash
```

### System Dependencies

```bash
# Install SLAM Toolbox
sudo apt-get install ros-jazzy-slam-toolbox

# Install Nav2
sudo apt-get install ros-jazzy-nav2-*

# Install other dependencies
sudo apt-get install ros-jazzy-vision-opencv ros-jazzy-tf2
```

---

## 🚀 Quick Start

### 1️⃣ **Start Gazebo Simulation** (Optional)

```bash
# Terminal 1: Launch Gazebo with SweePi robot
ros2 launch sweepi_gazebo gazebo.launch.py
```

### 2️⃣ **Start SLAM + Navigation + Exploration**

**Option A: All Together (Recommended)**

```bash
# Terminal 1: Everything in one command
ros2 launch sweepi_exploration master_launch.py
```

**Option B: Individual Components**

```bash
# Terminal 1: Start SLAM Toolbox
ros2 launch sweepi_slam slam_toolbox.launch.py use_sim_time:=true

# Terminal 2: Start Nav2 Navigation
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=true

# Terminal 3: Start Wavefront Explorer
ros2 launch sweepi_exploration exploration.launch.py
```

### 3️⃣ **Monitor Exploration**

```bash
# Terminal 4: Open RViz for visualization
rviz2
```

**Add in RViz:**
- `/map` → OccupancyGrid (see the map)
- `/exploration/frontiers` → MarkerArray (green spheres = unexplored areas)
- `/exploration/unreachable_areas` → MarkerArray (orange circles = failed attempts)

---

## 📂 Launch Files

### **Main Launch Files**

#### 1. **`master_launch.py`** - Complete System
Launches everything with proper timing (SLAM → Nav2 → Explorer)

```bash
# Default (balanced timing)
ros2 launch sweepi_exploration master_launch.py

# Custom timing
ros2 launch sweepi_exploration master_launch.py \
  slam_startup_delay:=2.0 \
  nav2_startup_delay:=10.0 \
  explorer_startup_delay:=5.0
```

**Timing Breakdown:**
- `t=0s` → SLAM starts
- `t=2s` → Nav2 starts (after SLAM initialized)
- `t=12s` → Explorer starts (after Nav2 ready)
- `t=17s` → Exploration begins

---

#### 2. **`exploration.launch.py`** - Explorer Only
Launches exploration system (requires SLAM + Nav2 already running)

```bash
# Default settings
ros2 launch sweepi_exploration exploration.launch.py

# With custom parameters
ros2 launch sweepi_exploration exploration.launch.py \
  frontier_min_size:=5 \
  max_exploration_time:=900 \
  unreachable_region_radius:=0.3

# For real robot
ros2 launch sweepi_exploration exploration.launch.py \
  use_sim_time:=false \
  nav_timeout:=40.0 \
  max_velocity:=0.03
```

---

#### 3. **`slam_toolbox.launch.py`** - SLAM Only
From `sweepi_slam` package - creates the map

```bash
# Synchronous SLAM
ros2 launch sweepi_slam slam_toolbox.launch.py mode:=sync

# Asynchronous SLAM (recommended for real robot)
ros2 launch sweepi_slam slam_toolbox.launch.py mode:=async
```

---

#### 4. **`navigation_launch.py`** - Nav2 Navigation
From `nav2_bringup` package - provides navigation capabilities

```bash
# Simulation mode
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=true

# Real robot
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=false
```

---

## ⚙️ Parameters

### Frontier Detection Parameters

#### **`frontier_min_size`** (default: 8)
- **Type**: Integer
- **Range**: 3-20
- **Effect**: Minimum cells to form a valid frontier cluster
- **Tuning**:
  - Lower (3-5): Detects small frontier areas, more exploration
  - Higher (15-20): Only large frontiers, faster but less thorough

```bash
# Explore small areas
ros2 launch sweepi_exploration exploration.launch.py frontier_min_size:=5

# Fast exploration (skip small areas)
ros2 launch sweepi_exploration exploration.launch.py frontier_min_size:=12
```

#### **`cluster_distance`** (default: 1.5m)
- **Type**: Float
- **Range**: 0.5-3.0 meters
- **Effect**: Maximum distance between cells to group as one frontier
- **Tuning**:
  - Lower (0.8-1.0): Separate nearby frontiers, more targets
  - Higher (2.0-3.0): Merge distant frontiers, fewer large targets

```bash
# Narrow corridors
ros2 launch sweepi_exploration exploration.launch.py cluster_distance:=0.8

# Open spaces
ros2 launch sweepi_exploration exploration.launch.py cluster_distance:=2.5
```

---

### Exploration Loop Parameters

#### **`exploration_frequency`** (default: 5.0 Hz)
- **Type**: Float
- **Range**: 1.0-10.0 Hz
- **Effect**: How often frontier detection runs
- **Tuning**:
  - Lower (2-3): Less CPU, gives Nav2 more processing time
  - Higher (8-10): More responsive, faster re-planning

```bash
# Slow, low-CPU mode
ros2 launch sweepi_exploration exploration.launch.py exploration_frequency:=2.0

# Fast, responsive mode
ros2 launch sweepi_exploration exploration.launch.py exploration_frequency:=8.0
```

#### **`nav_timeout`** (default: 25.0 seconds)
- **Type**: Float
- **Range**: 15-60 seconds
- **Effect**: Time allowed for robot to reach a goal
- **Tuning**:
  - Lower (15-20): Fail fast, try next frontier
  - Higher (40-60): Patient, gives robot more time

```bash
# Simulation (reliable navigation)
ros2 launch sweepi_exploration exploration.launch.py nav_timeout:=20.0

# Real robot (unpredictable environments)
ros2 launch sweepi_exploration exploration.launch.py nav_timeout:=50.0
```

---

### Speed Control Parameters

#### **`max_velocity`** (default: 0.05 m/s)
- **Type**: Float
- **Range**: 0.01-1.0 m/s
- **Effect**: Maximum forward speed

```bash
# Very slow (fragile payload)
ros2 launch sweepi_exploration exploration.launch.py max_velocity:=0.02

# Moderate (default)
ros2 launch sweepi_exploration exploration.launch.py max_velocity:=0.05

# Fast (robust robot)
ros2 launch sweepi_exploration exploration.launch.py max_velocity:=0.2
```

#### **`max_angular_velocity`** (default: 0.5 rad/s)
- **Type**: Float
- **Range**: 0.1-2.0 rad/s
- **Effect**: Maximum rotation speed

#### **`acceleration_limit`** (default: 0.3 m/s²)
- **Type**: Float
- **Range**: 0.1-1.0 m/s²
- **Effect**: Maximum acceleration (smoothness vs responsiveness)

---

### Attempt Limiting Parameters

#### **`max_attempts_per_frontier`** (default: 2)
- **Type**: Integer
- **Range**: 1-5
- **Effect**: Attempts to reach a frontier before blocking
- **Tuning**:
  - 1: Give up immediately (aggressive)
  - 2-3: Balanced (recommended)
  - 4-5: Patient (thorough)

```bash
# Aggressive mode (fast)
ros2 launch sweepi_exploration exploration.launch.py max_attempts_per_frontier:=1

# Balanced mode (default)
ros2 launch sweepi_exploration exploration.launch.py max_attempts_per_frontier:=2

# Patient mode (thorough)
ros2 launch sweepi_exploration exploration.launch.py max_attempts_per_frontier:=4
```

#### **`max_consecutive_timeouts`** (default: 2)
- **Type**: Integer
- **Range**: 1-10
- **Effect**: Timeouts in a row before stopping exploration
- **Tuning**:
  - Lower (1-2): Stop early if navigation fails
  - Higher (5-10): Keep trying despite failures

```bash
ros2 launch sweepi_exploration exploration.launch.py max_consecutive_timeouts:=3
```

#### **`max_exploration_time`** (default: 600 seconds = 10 minutes)
- **Type**: Integer
- **Range**: 60-3600 seconds
- **Effect**: Hard time limit for entire exploration
- **Tuning**:
  - 300s: Quick test (5 min)
  - 600s: Standard (10 min)
  - 1800s: Extended (30 min)

```bash
# Quick test
ros2 launch sweepi_exploration exploration.launch.py max_exploration_time:=300

# Extended exploration
ros2 launch sweepi_exploration exploration.launch.py max_exploration_time:=1800
```

---

### Wall Offset Parameters (Collision Avoidance)

#### **`goal_offset_distance`** (default: 0.5m)
- **Type**: Float
- **Range**: 0.3-1.5 meters
- **Effect**: How far to offset goals away from obstacles
- **Tuning**:
  - Lower (0.3-0.4): Explores closer to walls
  - Higher (0.8-1.5): Very conservative, safer

```bash
# Tight spaces
ros2 launch sweepi_exploration exploration.launch.py goal_offset_distance:=0.3

# Conservative mode
ros2 launch sweepi_exploration exploration.launch.py goal_offset_distance:=1.0
```

#### **`robot_radius`** (default: 0.25m)
- **Type**: Float
- **Range**: 0.1-0.5 meters
- **Effect**: Physical radius of robot (half-width)

```bash
# Small robot (10cm radius)
ros2 launch sweepi_exploration exploration.launch.py robot_radius:=0.1

# Large robot (30cm radius)
ros2 launch sweepi_exploration exploration.launch.py robot_radius:=0.3
```

#### **`safety_margin`** (default: 0.15m)
- **Type**: Float
- **Range**: 0.05-0.3 meters
- **Effect**: Extra buffer distance around robot

```bash
# Aggressive
ros2 launch sweepi_exploration exploration.launch.py safety_margin:=0.05

# Conservative
ros2 launch sweepi_exploration exploration.launch.py safety_margin:=0.25
```

---

### Smart Blocking Parameters

#### **`unreachable_region_radius`** (default: 0.5m)
- **Type**: Float
- **Range**: 0.2-1.0 meters
- **Effect**: Distance to block similar frontiers after failure
- **Tuning**:
  - Lower (0.2-0.3): More exploration, fewer blocked areas
  - Higher (0.8-1.0): Less time wasted, more areas blocked

```bash
# Maximize exploration
ros2 launch sweepi_exploration exploration.launch.py unreachable_region_radius:=0.2

# Minimize wasted time
ros2 launch sweepi_exploration exploration.launch.py unreachable_region_radius:=0.8
```

#### **`smart_blocking_enabled`** (default: true)
- **Type**: Boolean
- **Range**: true/false
- **Effect**: Uses connectivity checking before blocking
- **Impact**: Only blocks frontiers in SAME disconnected region

```bash
# Enable smart blocking (recommended)
ros2 launch sweepi_exploration exploration.launch.py smart_blocking_enabled:=true

# Disable (simpler but less intelligent)
ros2 launch sweepi_exploration exploration.launch.py smart_blocking_enabled:=false
```

---

## 💡 Usage Examples

### 📌 **Example 1: Quick Simulation Test**

```bash
# Terminal 1
ros2 launch sweepi_gazebo gazebo.launch.py

# Terminal 2: All-in-one launch
ros2 launch sweepi_exploration master_launch.py \
  slam_startup_delay:=1.0 \
  nav2_startup_delay:=5.0 \
  explorer_startup_delay:=2.0

# Terminal 3
rviz2
```

**Result:** Quick exploration in ~8 seconds ⏱️

---

### 📌 **Example 2: Real Robot - Safe & Thorough**

```bash
ros2 launch sweepi_exploration exploration.launch.py \
  use_sim_time:=false \
  frontier_min_size:=8 \
  exploration_frequency:=3.0 \
  nav_timeout:=40.0 \
  max_velocity:=0.03 \
  max_angular_velocity:=0.3 \
  acceleration_limit:=0.1 \
  goal_offset_distance:=0.7 \
  robot_radius:=0.3 \
  safety_margin:=0.2 \
  max_attempts_per_frontier:=3 \
  max_consecutive_timeouts:=3 \
  unreachable_region_radius:=0.3 \
  smart_blocking_enabled:=true
```

**Result:** Complete exploration, ~2-5 minutes ⏱️

---

### 📌 **Example 3: Maximum Coverage**

```bash
ros2 launch sweepi_exploration exploration.launch.py \
  frontier_min_size:=3 \
  cluster_distance:=1.0 \
  max_attempts_per_frontier:=5 \
  max_consecutive_timeouts:=10 \
  max_exploration_time:=1800 \
  unreachable_region_radius:=0.2 \
  smart_blocking_enabled:=true
```

**Result:** Explores entire environment, ~20-30 minutes ⏱️

---

### 📌 **Example 4: Fast & Efficient**

```bash
ros2 launch sweepi_exploration exploration.launch.py \
  frontier_min_size:=10 \
  cluster_distance:=2.0 \
  exploration_frequency:=8.0 \
  nav_timeout:=15.0 \
  max_velocity:=0.15 \
  max_attempts_per_frontier:=1 \
  max_exploration_time:=300 \
  unreachable_region_radius:=0.5
```

**Result:** Quick scan, ~3-5 minutes ⏱️

---

## 🔧 How It Works

### **Step 1: Map Reception**
```
SLAM Toolbox generates occupancy grid map
      ↓
WavefrontExplorer receives /map topic
      ↓
Map cells classified: occupied, free, unknown
```

### **Step 2: Frontier Detection**
```
Wavefront algorithm expands from free cells
      ↓
Finds boundaries between known ↔ unknown
      ↓
Clusters nearby frontier cells together
      ↓
Filters by minimum size threshold
```

### **Step 3: Smart Filtering**
```
Check if frontier is blocked by region
      ↓
Check if frontier is near previous failure
      ↓
If near failure → Check connectivity with BFS
      ↓
Only block if in SAME disconnected region
```

### **Step 4: Goal Selection**
```
Sort remaining frontiers by:
  - Cluster size (prefer large)
  - Distance (prefer close)
  - Previous attempts (penalize high)
      ↓
Select best frontier
```

### **Step 5: Goal Offsetting**
```
Find goal location AT frontier
      ↓
Apply wall offset algorithm:
  - Check 8 directions
  - Find position with most clearance
  - Ensure robot fits without collision
      ↓
Send offset goal to Nav2
```

### **Step 6: Navigation**
```
Nav2 plans path to goal
      ↓
Robot navigates using controller
      ↓
On success → Mark region as explored
      ↓
On failure → Record unreachable area
      ↓
Return to Step 2
```

---

## 📊 Output Files

### **Saved Maps**
Located in `~/SweePi/maps/`

```
swepi_exploration_map_20260415_150640.pgm   (image file)
swepi_exploration_map_20260415_150640.yaml  (metadata)
```

### **PGM Format**
- **White (255)**: Free space
- **Gray (128)**: Unknown
- **Black (0)**: Occupied

### **YAML Format**
```yaml
image: swepi_exploration_map_20260415_150640.pgm
resolution: 0.05
origin: [-5.0, -5.0, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196

swepi_metadata:
  timestamp: 2026-04-15T15:06:40
  exploration_time: 51.1
  goals_reached: 3
  goals_attempted: 3
  unreachable_areas: 0
```

---

## 🐛 Troubleshooting

### **Problem: Robot doesn't move**
```bash
# Check if Nav2 is running
ros2 topic list | grep navigate

# Check if SLAM is providing map
ros2 topic echo /map | head -20

# Increase nav_timeout
ros2 launch sweepi_exploration exploration.launch.py nav_timeout:=60.0
```

---

### **Problem: Robot explores same areas repeatedly**
```bash
# Increase unreachable_region_radius
ros2 launch sweepi_exploration exploration.launch.py unreachable_region_radius:=0.8

# Increase max_attempts_per_frontier
ros2 launch sweepi_exploration exploration.launch.py max_attempts_per_frontier:=1
```

---

### **Problem: Robot gets stuck on obstacles**
```bash
# Increase goal_offset_distance
ros2 launch sweepi_exploration exploration.launch.py goal_offset_distance:=1.0

# Increase safety_margin
ros2 launch sweepi_exploration exploration.launch.py safety_margin:=0.3

# Increase robot_radius if it's larger
ros2 launch sweepi_exploration exploration.launch.py robot_radius:=0.4
```

---

### **Problem: Exploration completes too quickly, missing areas**
```bash
# Decrease frontier_min_size
ros2 launch sweepi_exploration exploration.launch.py frontier_min_size:=3

# Increase max_exploration_time
ros2 launch sweepi_exploration exploration.launch.py max_exploration_time:=1800

# Increase max_attempts_per_frontier
ros2 launch sweepi_exploration exploration.launch.py max_attempts_per_frontier:=5

# Decrease unreachable_region_radius
ros2 launch sweepi_exploration exploration.launch.py unreachable_region_radius:=0.2
```

---

## 📚 File Structure

```
sweepi_exploration/
├── launch/
│   ├── master_launch.py              # Complete system launcher
│   ├── exploration.launch.py         # Explorer only launcher
│   └── slam_toolbox.launch.py        # SLAM launcher
├── sweepi_exploration/
│   ├── wavefront_explorer.py         # Main exploration node
│   └── __init__.py
├── config/
│   └── navigation.yaml               # Nav2 configuration
├── package.xml                       # Package metadata
├── setup.py                          # Python setup
├── README.md                         # This file
└── LICENSE                           # MIT License
```

---

## 📖 ROS Topics

### **Subscribed Topics**
- `/map` (OccupancyGrid) - Map from SLAM Toolbox
- `/tf` (TransformStamped) - Robot transforms

### **Published Topics**
- `/exploration/frontiers` (MarkerArray) - Detected frontiers
- `/exploration/unreachable_areas` (MarkerArray) - Failed attempts
- `/exploration/blocked_regions` (MarkerArray) - Blocked regions

### **Services**
- `/navigate_to_pose` (NavigateToPose) - Nav2 action service

---

## 📝 Parameters Summary Table

| Parameter | Default | Min | Max | Type | Effect |
|-----------|---------|-----|-----|------|--------|
| `frontier_min_size` | 8 | 3 | 20 | Int | Lower = more exploration |
| `cluster_distance` | 1.5m | 0.5 | 3.0 | Float | Lower = separate clusters |
| `exploration_frequency` | 5.0Hz | 1.0 | 10.0 | Float | Higher = more responsive |
| `nav_timeout` | 25s | 15 | 60 | Float | Higher = more patient |
| `max_velocity` | 0.05m/s | 0.01 | 1.0 | Float | Speed of robot |
| `max_attempts_per_frontier` | 2 | 1 | 5 | Int | Higher = more tries |
| `max_consecutive_timeouts` | 2 | 1 | 10 | Int | Higher = tolerant |
| `max_exploration_time` | 600s | 60 | 3600 | Int | Hard time limit |
| `goal_offset_distance` | 0.5m | 0.3 | 1.5 | Float | Higher = safer |
| `robot_radius` | 0.25m | 0.1 | 0.5 | Float | Robot size |
| `safety_margin` | 0.15m | 0.05 | 0.3 | Float | Extra buffer |
| `unreachable_region_radius` | 0.5m | 0.2 | 1.0 | Float | Lower = explore more |
| `smart_blocking_enabled` | true | - | - | Bool | Connectivity check |

---

## 🎓 References

- [ROS2 Navigation Framework](https://navigation.ros.org/)
- [SLAM Toolbox](https://github.com/SteveMacenski/slam_toolbox)
- [Frontier-based Exploration](https://en.wikipedia.org/wiki/Frontier-based_exploration)
- [Wavefront Algorithm](https://en.wikipedia.org/wiki/Breadth-first_search)

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details

---

## 👤 Author

**Akhila Nisal**  
GitHub: [@AkhilaNisal](https://github.com/AkhilaNisal)

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

---

## ❓ FAQ

**Q: What's the difference between master_launch.py and exploration.launch.py?**

A: `master_launch.py` launches SLAM, Nav2, and Explorer with proper timing. `exploration.launch.py` only launches the explorer (requires SLAM + Nav2 already running).

---

**Q: Can I use this on a real robot?**

A: Yes! Set `use_sim_time:=false` and adjust parameters for your robot's speeds and size.

---

**Q: How do I know exploration is complete?**

A: The system logs "✅ EXPLORATION COMPLETE" and saves the map to `~/SweePi/maps/`

---

**Q: What if my robot can't reach a frontier?**

A: The system will try up to `max_attempts_per_frontier` times, then block that region and move to the next frontier.

---

**Q: How do I visualize the exploration in real-time?**

A: Open RViz2 and add these topics:
- `/map` (OccupancyGrid)
- `/exploration/frontiers` (MarkerArray - green)
- `/exploration/unreachable_areas` (MarkerArray - orange)

---

## 🎉 Quick Reference - One-Liners

```bash
# Gazebo simulation
ros2 launch sweepi_gazebo gazebo.launch.py

# Complete system
ros2 launch sweepi_exploration master_launch.py

# SLAM only
ros2 launch sweepi_slam slam_toolbox.launch.py use_sim_time:=true

# Nav2 only
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=true

# Explorer only
ros2 launch sweepi_exploration exploration.launch.py

# RViz monitoring
rviz2

# View saved map
eog ~/SweePi/maps/swepi_exploration_map_*.pgm

# Check topics
ros2 topic list | grep exploration
```

---

**Last Updated:** April 15, 2026  
**Status:** ✅ Production Ready