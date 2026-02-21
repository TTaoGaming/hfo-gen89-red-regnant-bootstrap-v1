# SBE/ATDD: N-Hand Gesture Bridge to W3C Pointer Fabric

## Overview
The `GestureBridge` acts as the connective tissue between raw N-hand tracking data (e.g., MediaPipe), the stateful Gesture FSM, and the W3C Pointer Fabric. It ensures that each tracked hand maintains its own independent state machine and pointer ID, enabling true multi-touch support for an arbitrary number of hands.

## Architecture Recommendation
To support N hands instantly without heavy dependencies:
1. **Lightweight FSM Instance**: A TypeScript class (`GestureFSM`) that implements the exact logic defined in `gesture_fsm.scxml` (Schmitt trigger, asymmetrical leaky bucket, COAST states).
2. **Bridge Manager**: A `GestureBridge` class that maintains a `Map<number, GestureFSM>` keyed by `handId`.
3. **Lifecycle Routing**: The bridge spawns an FSM when a new hand appears, routes frame data (gesture, confidence, x, y) to the specific FSM, and maps the FSM's state to the `isPinching` boolean required by the `W3CPointerFabric`.

---

## Scenario 1: Spawning Independent FSMs for Multi-Touch
**Given** the `GestureBridge` is initialized with a `W3CPointerFabric`
**When** a frame arrives with two distinct hands (`handId: 0` and `handId: 1`)
**Then** the bridge spawns two independent `GestureFSM` instances
**And** routes the spatial data for both hands to the fabric simultaneously.

## Scenario 2: Independent State Management
**Given** two hands are being tracked
**When** Hand 0 performs a `pointer_up` gesture with high confidence while Hand 1 performs an `open_palm`
**Then** Hand 0's FSM transitions to `COMMIT_POINTER` (isPinching = true)
**And** Hand 1's FSM transitions to `READY` (isPinching = false)
**And** the fabric dispatches a `pointerdown` for Hand 0 and a `pointermove` for Hand 1.

## Scenario 3: Graceful Degradation (COAST) per Hand
**Given** Hand 0 is in `COMMIT_POINTER`
**When** Hand 0's tracking confidence drops below the low threshold
**Then** Hand 0's FSM drops to `COMMIT_COAST`
**And** the bridge continues to report `isPinching = true` to the fabric for Hand 0, preventing an accidental `pointerup` during temporary tracking loss.

## Scenario 4: Hand Loss and Cleanup
**Given** Hand 1 is being tracked
**When** Hand 1 is no longer present in the incoming frame data for a sustained period (timeout)
**Then** the bridge sends a `timeout.coast` event to Hand 1's FSM
**And** the FSM transitions to `IDLE`
**And** the bridge cleans up the FSM instance to prevent memory leaks.

---

## Scenario 5: Highlander Mutex Adapter (Single-Touch Enforcement)

**Scenario 5.1: Basic First-Come, First-Served**
* **Given** a `HighlanderMutexAdapter` with default config
* **When** Hand 1 appears, followed by Hand 2
* **Then** the adapter locks onto Hand 1 and forwards its events
* **And** Hand 2's events are dropped
* **And** when Hand 1 disappears, the lock is released and Hand 2 can acquire it

**Scenario 5.2: Lock on Commit Only**
* **Given** a `HighlanderMutexAdapter` with `lockOnCommitOnly: true`
* **When** Hand 1 and Hand 2 are both hovering (`open_palm`)
* **Then** neither hand acquires the lock (both are dropped)
* **When** Hand 2 commits (`pointer_up`)
* **Then** Hand 2 acquires the lock and its events are forwarded
* **And** Hand 1's events are dropped even if it subsequently commits

**Scenario 5.3: Drop Hover Events**
* **Given** a `HighlanderMutexAdapter` with `dropHoverEvents: true`
* **When** Hand 1 appears and hovers (`open_palm`)
* **Then** Hand 1 acquires the lock, but its events are dropped (not forwarded)
* **When** Hand 1 commits (`pointer_up`)
* **Then** Hand 1's events are forwarded
