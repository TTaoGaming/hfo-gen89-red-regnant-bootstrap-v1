---
title: "Omega v15 Diataxis: W3C Pointer Fabric (Kalman + PointerEvents)"
type: "explanation"
status: "draft"
medallion: "bronze"
---

# Explanation: W3C Pointer Fabric (Kalman + PointerEvents)

## The Core Capability
The W3C Pointer Fabric is the universal language of interaction in Omega v15. It translates raw, noisy sensor data (like a camera feed) into a clean, standardized stream of W3C Pointer Events. This fabric decouples the input source from the application logic, allowing any component to consume and react to interactions seamlessly.

## The Logic
Raw sensor data is inherently noisy and jittery. The W3C Pointer Fabric uses a Kalman filter to smooth out this noise, predicting the true position of the user's interaction point. It then translates this smoothed data into standard W3C Pointer Events (e.g., `pointerdown`, `pointermove`, `pointerup`).

1.  **Raw Data Ingestion:** The system receives raw sensor data (e.g., MediaPipe landmarks).
2.  **Kalman Filtering:** A Kalman filter processes the data, reducing noise and predicting the true position.
3.  **Event Translation:** The smoothed position is translated into a standard W3C Pointer Event.
4.  **Event Dispatch:** The event is dispatched to the browser's event system, where any component can listen for it.

## Why it Matters for Omega v15
In Omega v15, this capability is the foundation of the Total Tool Virtualization architecture. By standardizing all interactions as W3C Pointer Events, the system achieves true decoupling. A component doesn't need to know if an interaction came from a mouse, a touch screen, or a mid-air gesture; it simply listens for standard pointer events. This enables a highly modular, extensible, and robust system.

*Note: The Omega v13 implementation of this logic is deprecated. This document describes the core capability for the v15 clean-room rewrite.*
