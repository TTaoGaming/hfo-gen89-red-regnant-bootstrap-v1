---
title: "Omega v15 Diataxis: Privacy-by-Math (UserTuningProfile)"
type: "explanation"
status: "draft"
medallion: "bronze"
---

# Explanation: Privacy-by-Math (UserTuningProfile)

## The Core Capability
The `UserTuningProfile` is not just a configuration object; it is a mathematical guarantee of privacy. It represents the user's physical dimensions and interaction preferences (e.g., arm length, resting position, tremor threshold) as pure mathematical constants.

## The Logic
Instead of sending raw camera feeds or point clouds to a server for processing, the system uses the `UserTuningProfile` to normalize and filter the data locally. The server only ever receives abstract, normalized interaction events (e.g., "a pinch occurred at normalized coordinates [0.5, 0.5]").

1.  **Local Calibration:** The user performs a calibration gesture.
2.  **Profile Generation:** The system calculates the user's unique physical constants (the `UserTuningProfile`).
3.  **Data Normalization:** All subsequent raw data (e.g., MediaPipe landmarks) is transformed using this profile.
4.  **Abstract Event Emission:** Only the normalized, abstract events are emitted to the broader system.

## Why it Matters for Omega v15
In Omega v15, this capability is crucial for the Total Tool Virtualization architecture. The browser-native `<script type=importmap>` environment must handle all raw data processing locally. The `UserTuningProfile` ensures that the system remains performant and privacy-preserving by only passing abstract events through the W3C Pointer Fabric.

*Note: The Omega v13 implementation of this logic is deprecated. This document describes the core capability for the v15 clean-room rewrite.*
