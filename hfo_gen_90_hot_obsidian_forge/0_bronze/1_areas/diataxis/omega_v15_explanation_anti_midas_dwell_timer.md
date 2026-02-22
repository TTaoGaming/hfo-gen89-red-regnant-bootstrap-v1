---
title: "Omega v15 Diataxis: Anti-Midas Dwell Timer (FSM)"
type: "explanation"
status: "draft"
medallion: "bronze"
---

# Explanation: Anti-Midas Dwell Timer (FSM)

## The Core Capability
The Anti-Midas Dwell Timer is a defense mechanism against accidental interactions. It prevents the system from interpreting every fleeting movement as a deliberate command. It is a Finite State Machine (FSM) that requires a user to hold a specific pose or gesture for a defined duration before an action is triggered.

## The Logic
Without a dwell timer, a user might accidentally trigger an action simply by moving their hand through the camera's field of view. The Anti-Midas Dwell Timer introduces a necessary delay, ensuring that only intentional, sustained gestures are recognized.

1.  **Gesture Detection:** The system detects a potential gesture (e.g., a pinch).
2.  **State Transition (Pending):** The system enters a "pending" state and starts a timer.
3.  **Dwell Duration:** The user must maintain the gesture for the specified duration (e.g., 500ms).
4.  **State Transition (Active):** If the gesture is maintained, the system transitions to the "active" state and triggers the action.
5.  **Reset:** If the gesture is broken before the timer expires, the system resets to the "idle" state.

## Why it Matters for Omega v15
In Omega v15, this capability is critical for the Total Tool Virtualization architecture. The system must be robust against noise and accidental inputs. The Anti-Midas Dwell Timer provides a reliable, predictable way to filter out unintended interactions, ensuring a smooth and frustration-free user experience.

*Note: The Omega v13 implementation of this logic is deprecated. This document describes the core capability for the v15 clean-room rewrite.*
