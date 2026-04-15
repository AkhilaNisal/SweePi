# 🚀 SweePi Exploration Package

**Autonomous Frontier-Based Exploration for Mobile Robots**

An advanced ROS 2 package for autonomous exploration using wavefront frontier detection, wall offset algorithms, and smart proximity-based blocking. Designed for the SweePi robot to autonomously map unknown environments efficiently.

---

## 📋 Table of Contents

- [Features](#features)
- [What is it?](#what-is-it)
- [How it Works](#how-it-works)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Parameters](#parameters)
- [Launch Files](#launch-files)
- [Usage Examples](#usage-examples)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Authors](#authors)

---

## ✨ Features

### Core Capabilities
- ✅ **Wavefront Frontier Detection** - Detects unexplored regions (frontiers) using BFS algorithm
- ✅ **Autonomous Goal Selection** - Intelligently selects best frontier based on size, distance, and exploration history
- ✅ **Wall Offset Algorithm** - Offsets goals away from obstacles to prevent collisions
- ✅ **Smart Proximity Blocking** - Uses connectivity checking to avoid blocking reachable areas
- ✅ **Region-Based Tracking** - Tracks attempts per region to avoid retrying unreachable areas
- ✅ **Automatic Timeout Management** - Detects and handles navigation failures gracefully
- ✅ **Map Saving** - Saves explored map as PGM image with metadata

### Advanced Features
- 🧠 **Connectivity-Aware Blocking** - BFS checks if frontiers are in same connected region before blocking
- 📊 **Real-time Visualization** - Publishes markers for frontiers, blocked regions, unreachable areas
- 🎯 **Aggressive Attempt Limiting** - Configurable attempt limits prevent infinite loops
- ⏱️ **Hard Time Limits** - Exploration stops after configurable time for safety
- ����️ **Safety Margins** - Configurable robot radius and safety buffers
- 📈 **Speed Control** - Adjustable velocity and acceleration parameters
- 💾 **Persistent Logging** - Saves exploration results with timestamps

---

## 🤖 What is it?

The **SweePi Exploration Package** is a complete autonomous exploration system for mobile robots. It enables a robot to:

1. **Create Maps** - SLAM generates occupancy grid
2. **Detect Frontiers** - Identifies boundaries between explored and unexplored space
3. **Select Goals** - Chooses best frontier to explore next
4. **Navigate Safely** - Offsets goals to avoid obstacles and collisions
5. **Handle Failures** - Intelligently blocks unreachable areas to avoid retries
6. **Complete Autonomously** - Explores until no more frontiers, saves final map

### Key Components

| Component | Purpose |
|-----------|---------|
| **Wavefront Explorer** | Main node that detects frontiers and sends navigation goals |
| **SLAM Toolbox** | Creates 2D occupancy grid map from lidar scans |
| **Nav2 Stack** | Provides path planning and navigation services |
| **Launch Files** | Coordinates startup of all components |

---

## 🧠 How it Works

### Algorithm Overview
