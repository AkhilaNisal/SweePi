# 🤖 SweePi — Adaptive Floor Cleaning Robot
### *An intelligent cleaning robot with an extendable flexible arm*

> **Status:** 🚧 Work In Progress — Semester 4 Engineering Design Realization Project  
> **Team:** Nexora | Department of Electronic & Telecommunication Engineering

---

## 📌 Overview

**FlexiClean** is an autonomous floor cleaning robot designed to overcome the physical limitations of conventional robotic vacuums. While standard robots struggle with sharp corners, furniture gaps, and low-clearance areas, FlexiClean deploys an **extendable flexible cleaning arm** to reach where others can't.

The system combines **LiDAR-based SLAM navigation** with a **dual-mode cleaning architecture** — standard bottom cleaning for open areas, and arm-extended cleaning for restricted zones.

---

## 🧩 System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FLEXICLEAN SYSTEM                  │
├───────────────────┬─────────────────────────────────┤
│   Sensing Layer   │  LiDAR · Wheel Encoders          │
│                   │  Proximity Sensors               │
├───────────────────┼─────────────────────────────────┤
│   Control Layer   │  Embedded Processor / MCU        │
│                   │  SLAM Navigation Algorithm       │
├───────────────────┼─────────────────────────────────┤
│  Actuation Layer  │  Drive Motors (Differential)     │
│                   │  Suction Motor · Arm Motor       │
├───────────────────┼─────────────────────────────────┤
│   Power System    │  Rechargeable Battery Pack       │
│                   │  Power Regulation Module         │
└───────────────────┴─────────────────────────────────┘
```

---

## 🔩 Key Subsystems

### 1. Main Mobile Cleaning Unit
- Compact **cylindrical body** with differential drive (2 wheels + caster)
- Bottom-mounted **suction and brushing mechanism**
- **LiDAR sensor** for real-time environment mapping
- Onboard microcontroller / embedded processor *(selection in progress)*

### 2. Extendable Flexible Cleaning Arm
- **Flexible segmented structure** stored within the main body
- Small wheels for independent arm mobility
- Dedicated **mini cleaning head** at the tip
- Motorized **extension and retraction** mechanism
- Deploys automatically when restricted zones are detected

---

## ✨ Key Innovations

| Feature | Description |
|---|---|
| 🦾 Deployable Arm | Extends into corners, under furniture & narrow gaps |
| 🗺️ Map-Based Zone Detection | Classifies areas as *reachable* or *restricted* using SLAM |
| 🔄 Dual-Mode Cleaning | Seamlessly switches between standard and extended modes |
| 📦 Compact Form Factor | Full arm mechanism housed within the main robot body |
| 🔧 Modular Architecture | Designed for future hardware/software upgrades |

---

## 🗺️ Roadmap

- [ ] Literature review & requirement analysis
- [ ] Mechanical design — chassis & arm
- [ ] Sensor and processor selection
- [ ] SLAM mapping & navigation algorithm development
- [ ] System integration & prototype build
- [ ] Testing & performance evaluation

---

## 📡 Mobile API Contract

The robot/mobile contract lives under `/api` and is documented in
[`docs/final_api_doc.md`](docs/final_api_doc.md). Robot command responses expose
top-level lifecycle fields including `accepted`, `completed`, `task_finished`,
`state`, `command`, `next_steps`, and structured `error`.

For cleaning, the app must follow:

```text
POST /api/cleaning/start
POST /api/localization/initial-pose
POST /api/cleaning/validate
POST /api/cleaning/start-motion
GET  /api/cleaning/status
```

The app should advance to the next step only when the previous command returns
`success=true` and `completed=true`; `accepted=true` only means the command was
accepted and sent toward ROS/mock logic. See
[`docs/command_lifecycle.md`](docs/command_lifecycle.md).

---

## Real Hardware Bringup

Final STM32-based hardware packages:

```bash
colcon build --symlink-install --packages-select sweepi_base_driver sweepi_state_estimation sweepi_real_bringup sweepi_robot_manager sweepi_api_bridge
source install/setup.bash
```

Launch the full real robot stack with robot manager and API bridge:

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

Launch only the hardware bringup without LiDAR for the first STM32 UART test:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py base_serial_port:=/dev/ttyAMA0 base_baud_rate:=115200 launch_lidar:=false
```

Launch with explicit Raspberry Pi UART settings:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py base_serial_port:=/dev/ttyAMA0 base_baud_rate:=115200 launch_lidar:=false
```

USB debug override:

```bash
ros2 launch sweepi_real_bringup hardware_debug.launch.py base_serial_port:=/dev/ttyACM0 base_baud_rate:=115200 launch_lidar:=false
```

Useful checks:

```bash
ros2 topic echo /hardware/status
ros2 topic echo /wheel/odom
ros2 topic echo /imu/data
ros2 topic echo /odom
ros2 topic hz /wheel/odom
ros2 topic hz /imu/data
```

For a lifted-wheel motor test, publish a small command and then stop:

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.03}, angular: {z: 0.0}}"
ros2 topic pub -1 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}, angular: {z: 0.0}}"
```

See [`docs/hardware.md`](docs/hardware.md) for Raspberry Pi UART wiring, STM32 constants, and integration warnings.

---

## 👥 Team Nexora

- Ranasinghe D.P.H.
- Kumarasinghe M.N. 
- Ranathunga R.J.K.O.H. 
- Rathnayake M.A.G.K.N. 
- Wedamestrige A.N. 

> Department of Electronic and Telecommunication Engineering  
> Semester 4 — Engineering Design Realization Project

---

## 📄 License

This project is developed for academic purposes as part of the university engineering curriculum.

---

*Last updated: February 2026*
