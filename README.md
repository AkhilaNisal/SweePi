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
