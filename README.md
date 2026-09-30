# URBANTRACE
### AI-Powered Multi-Camera Urban Intelligence & Vehicle Trajectory Analytics

> **Smart India Hackathon 2026 — Software Problem Statement 26127**  
> **Organization:** BEL  
> **Category:** Software

URBANTRACE is a city-wide AI platform designed to transform distributed traffic-camera feeds into actionable urban intelligence.

The system combines **computer vision, ANPR, multi-object tracking, vehicle re-identification, geospatial modeling, trajectory analysis, and traffic intelligence** to follow vehicles across a network of cameras and build meaningful city-level movement information.

---

## 🚦 Problem

Modern urban surveillance systems generate enormous amounts of video data, but individual cameras usually operate independently.

This creates several challenges:

- A vehicle detected by one camera cannot easily be associated with its appearance at another camera.
- Number-plate recognition can be inconsistent across different camera views.
- Traffic events are difficult to correlate across a city-wide camera network.
- Raw video provides observations, but not a structured representation of vehicle journeys.
- Operators need to manually inspect multiple camera feeds to understand vehicle movement.

URBANTRACE addresses this by converting camera observations into a **structured city-wide vehicle intelligence layer**.

---

# 🎯 Objectives

URBANTRACE aims to provide:

- Multi-camera vehicle detection and tracking
- Automatic number plate recognition (ANPR)
- Vehicle attribute extraction
- Vehicle re-identification across camera views
- Camera-to-camera trajectory reasoning
- Geospatial vehicle journey reconstruction
- Traffic analytics
- Event and incident intelligence
- Explainable vehicle trajectories
- Interactive urban intelligence dashboards

---

# 🧠 System Architecture

```text
                    ┌──────────────────────────┐
                    │      Traffic Cameras     │
                    │  Live / Recorded Video   │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │    Vision Pipeline       │
                    │                          │
                    │  YOLOv8 Detection        │
                    │  ByteTrack Tracking      │
                    │  OpenCV Processing       │
                    └────────────┬─────────────┘
                                 │
                  ┌──────────────┼──────────────┐
                  ▼              ▼              ▼
          ┌────────────┐ ┌─────────────┐ ┌─────────────┐
          │   ANPR     │ │  Vehicle    │ │    Re-ID    │
          │ PaddleOCR  │ │ Attributes  │ │ Embeddings  │
          └──────┬─────┘ └──────┬──────┘ └──────┬──────┘
                 │              │               │
                 └──────────────┼───────────────┘
                                ▼
                    ┌──────────────────────────┐
                    │ Vehicle Observations     │
                    │ Camera + Time + Position │
                    │ Plate + Attributes       │
                    │ Tracking + Embeddings    │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │   PostgreSQL + PostGIS   │
                    │                          │
                    │ City / Camera / Road     │
                    │ Vehicle / Observation    │
                    │ Trajectory / Events      │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │ Graph / Trajectory Engine│
                    │                          │
                    │ Camera topology          │
                    │ Cross-camera matching    │
                    │ Journey reconstruction   │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │     Urban Intelligence   │
                    │                          │
                    │ Live Map                 │
                    │ Vehicle Journey          │
                    │ Traffic Analytics        │
                    │ Alert Center              │
                    │ Event Replay              │
                    │ What-If Simulation       │
                    └──────────────────────────┘
