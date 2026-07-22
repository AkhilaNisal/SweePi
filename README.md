# 🤖 SweePi — Autonomous Floor Cleaning Robot

### Intelligent ROS 2 Powered Indoor Cleaning Robot with Smart Coverage Navigation

> **Status:** ✅ Completed Engineering Design Realization Project
>
> **Team:** Nexora
>
> **Department of Electronic & Telecommunication Engineering**

---

# 📖 Overview

**SweePi** is a fully autonomous indoor floor cleaning robot designed to perform efficient, systematic, and intelligent cleaning of residential and commercial environments.

Unlike conventional robotic vacuum cleaners that rely on random navigation, SweePi uses **LiDAR-based Simultaneous Localization and Mapping (SLAM)** together with **ROS 2 Navigation (Nav2)** and a **coverage path planning algorithm** to clean every reachable area while avoiding obstacles.

The robot integrates real-time localization, autonomous navigation, intelligent coverage planning, mobile application control, and a custom STM32-based hardware platform.

---

# ✨ Features

- 🗺️ LiDAR-based SLAM Mapping
- 📍 Autonomous Localization
- 🚗 ROS 2 Nav2 Navigation Stack
- 🧹 Intelligent Coverage Path Planning
- 📊 Real-time Cleaning Progress Tracking
- 📱 Mobile Application Control
- 📡 REST API Interface
- ⚙️ STM32 Real-Time Motor Controller
- 🔋 Dual Battery Power Architecture
- 📶 Wi-Fi Robot Communication
- 🛑 Automatic Obstacle Avoidance
- 🔄 Modular ROS 2 Package Architecture

---

# 🏗 System Architecture

```
                        +-------------------------+
                        |     Mobile Application  |
                        +-----------+-------------+
                                    |
                              REST API / Wi-Fi
                                    |
                        +-----------v-------------+
                        |   API Bridge (FastAPI)  |
                        +-----------+-------------+
                                    |
                              Robot Manager
                                    |
        +---------------------------+---------------------------+
        |                           |                           |
        |                           |                           |
+-------v------+           +---------v---------+       +---------v---------+
| SLAM Toolbox |           | Navigation (Nav2) |       | Coverage Planner  |
+--------------+           +-------------------+       +-------------------+
        |                           |                           |
        +-------------+-------------+---------------------------+
                      |
                 ROS 2 Topics
                      |
             +--------v---------+
             | State Estimation |
             +--------+---------+
                      |
             +--------v---------+
             |  STM32 Controller|
             +--------+---------+
                      |
       +--------------+--------------+
       |                             |
 Drive Motors                  Sensor Interfaces
       |                             |
 Wheel Encoders              IMU • LiDAR • Power
```

---

# 🧠 Software Stack

| Layer | Technology |
|--------|------------|
| Robot Framework | ROS 2 Jazzy |
| Operating System | Ubuntu Server 24.04 |
| SLAM | slam_toolbox |
| Navigation | Nav2 |
| Programming | Python, C++, C |
| Embedded Controller | STM32G474RET6 |
| SBC | Raspberry Pi 5 |
| API | FastAPI |
| Mobile App | Flutter |
| Version Control | Git & GitHub |

---

# ⚙️ Hardware

## Main Controller

- Raspberry Pi 5

## Embedded Controller

- STM32G474RET6

## Sensors

- RPLIDAR
- Wheel Encoders
- 9-DOF IMU (BNO055)

## Actuators

- Differential Drive Motors
- Vacuum Motor
- Side Brush Motors
- Servo Motors

---

# 🔋 Power Architecture

SweePi uses two independent battery systems for improved electrical isolation and reliability.

### 14.8V 4S LiPo

Powers:

- Raspberry Pi
- STM32 Controller
- Wheel Drive Motors

Converted using onboard regulators to

- 12V
- 5.1V
- 3.3V

---

### 11.1V 3S Battery

Powers:

- Vacuum Motor
- Front Cleaning Motors
- Servo Motors

A dedicated 6V buck converter supplies the servos.

---

# 📦 Repository Structure

```
SweePi/
│
├── src/
│   ├── sweepi_api_bridge/
│   ├── sweepi_base_driver/
│   ├── sweepi_bringup/
│   ├── sweepi_coverage/
│   ├── sweepi_description/
│   ├── sweepi_exploration/
│   ├── sweepi_real_bringup/
│   ├── sweepi_robot_manager/
│   ├── sweepi_slam/
│   └── sweepi_state_estimation/
│
├── docs/
│
├── launch/
│
├── config/
│
├── maps/
│
└── README.md
```

---

# 🚀 Building the Workspace

```bash
mkdir -p ~/sweepi_ws/src

cd ~/sweepi_ws/src

git clone https://github.com/<your_username>/SweePi.git

cd ..

colcon build --symlink-install

source install/setup.bash
```

---

# 🚀 Running Simulation

```bash
ros2 launch sweepi_robot_manager master.launch.py \
launch_sim:=true
```

---

# 🤖 Running on Real Robot

Build required packages

```bash
colcon build --symlink-install \
--packages-select \
sweepi_base_driver \
sweepi_state_estimation \
sweepi_real_bringup \
sweepi_robot_manager \
sweepi_api_bridge
```

Source workspace

```bash
source install/setup.bash
```

Launch robot

```bash
ros2 launch sweepi_robot_manager master.launch.py \
launch_sim:=false \
launch_hardware:=true \
use_sim_time:=false \
launch_api_bridge:=true \
api_host:=0.0.0.0 \
api_port:=8080 \
launch_lidar:=true
```

---

# 🔧 Hardware Debug

Launch without LiDAR

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py \
base_serial_port:=/dev/ttyAMA0 \
base_baud_rate:=115200 \
launch_lidar:=false
```

USB Debug

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py \
base_serial_port:=/dev/ttyACM0 \
base_baud_rate:=115200 \
launch_lidar:=false
```

---

# 📡 REST API

The robot communicates with the mobile application through a REST API.

Typical cleaning workflow:

```
POST /api/localization/initial-pose

POST /api/cleaning/start

POST /api/cleaning/validate

POST /api/cleaning/start-motion

GET /api/cleaning/status
```

Command lifecycle includes

- accepted
- completed
- success
- task_finished
- state
- command
- next_steps
- error

---

# 📊 ROS Topics

### Sensor Topics

```
/scan
/imu/data
/wheel/odom
/odom
/map
/tf
```

### Coverage

```
/coverage_map
/coverage_map_updates
/coverage_path
/coverage_percentage
```

### Hardware

```
/hardware/status
/cmd_vel
```

---

# 🔍 Useful Commands

Check odometry

```bash
ros2 topic echo /odom
```

Check wheel odometry

```bash
ros2 topic echo /wheel/odom
```

Check IMU

```bash
ros2 topic echo /imu/data
```

Check hardware status

```bash
ros2 topic echo /hardware/status
```

Check publishing rate

```bash
ros2 topic hz /wheel/odom
```

Motor test

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.03}, angular: {z: 0.0}}"
```

Stop

```bash
ros2 topic pub -1 /cmd_vel geometry_msgs/msg/Twist \
"{linear: {x: 0.0}, angular: {z: 0.0}}"
```

---

# 📱 Mobile Application

The Flutter mobile application provides

- Robot discovery
- Wi-Fi provisioning
- Live map visualization
- Cleaning task selection
- Cleaning progress monitoring
- Robot status monitoring
- Manual control
- Map management

---

# 🎯 Project Objectives

- Autonomous indoor navigation
- Complete area coverage
- Intelligent obstacle avoidance
- Efficient cleaning path planning
- Mobile application integration
- Modular ROS 2 architecture
- Real-time embedded control

---

# 👥 Team Nexora

- D. P. H. Ranasinghe
- M. N. Kumarasinghe
- R. J. K. O. H. Ranathunga
- M. A. G. K. N. Rathnayake
- A. N. Wedamestrige

Department of Electronic & Telecommunication Engineering

Engineering Design Realization Project

---

# 📄 License

This project is developed for academic and research purposes as part of the Engineering Design Realization module.

---

## ⭐ Acknowledgements

Special thanks to

- ROS 2 Community
- Open Robotics
- Nav2 Developers
- slam_toolbox Contributors
- Raspberry Pi Foundation
- STMicroelectronics

---

**SweePi — Intelligent Autonomous Cleaning, Powered by ROS 2**
