---
schema_id: hfo.gen89.p2.project_definition.v1
medallion_layer: bronze
target_layer: gold
port: P2/P7
hfo_header_v3: compact
bluf: "Gold Project Definition for Omega v13 Microkernel. Defines the W3C Pointer shared data fabric and provides SBE/ATDD Gherkin specs for the Video Resource Throttle (Resolution Step-Ladder)."
---

# Project: Omega v13 Microkernel

> **P7 Spider Sovereign & P2 Mirror Magus Synthesis**
> *This is the Gold Project definition for the Omega v13 Microkernel. The core invariant is that the shared data fabric is W3C Pointer events, and consumers are "dumb". The first component to be built is the Video Resource Throttle.*

## 1. Architecture: The W3C Pointer Fabric

The Omega v13 Microkernel operates on a strict separation of concerns:
*   **The Host (The Eye):** Handles the camera, overscan, resolution throttling, and MediaPipe gesture recognition.
*   **The Fabric:** The Host translates complex 3D hand gestures into standard 2D **W3C Pointer Events** (`pointerdown`, `pointermove`, `pointerup`).
*   **The Consumers (The Apps):** The 2D apps running in the IFrame sandbox are "dumb". They do not know they are being controlled by a camera. They simply listen for standard W3C Pointer events. This is what unlocks *all* touch 2D apps without modification.

## 2. Component: Video Resource Throttle (Resolution Step-Ladder)

The Video Resource Throttle is a critical invariant that survived 88 generations. It manages the `MediaStreamTrack` constraints dynamically to prevent thermal throttling and maintain a target FPS.

**Key Requirement:** The logic for *when* to step up or down is external (handled by a separate FPS monitor). This component's sole responsibility is to execute the step stably, without crashing the stream or causing a black screen flash.

### SBE / ATDD (Gherkin Specs)

These specs define the correct-by-construction behavior of the throttle.

```gherkin
Feature: Video Resource Throttle (Resolution Step-Ladder)
  As the Omega v13 Microkernel
  I want to dynamically step the video resolution up or down
  So that I can maintain target FPS without interrupting the user's video stream

  Background:
    Given the VideoResourceThrottle is initialized with a running MediaStream
    And the resolution ladder is defined as:
      | Level | Width | Height |
      | 0     | 320   | 240    |
      | 1     | 640   | 480    |
      | 2     | 1280  | 720    |
    And the current resolution level is 2 (1280x720)

  Scenario: Step down resolution successfully
    When the external governor commands a "step down"
    Then the throttle should apply constraints for Level 1 (640x480) to the active video track
    And the video stream should not be stopped or recreated
    And the current resolution level should be updated to 1

  Scenario: Step up resolution successfully
    Given the current resolution level is 1 (640x480)
    When the external governor commands a "step up"
    Then the throttle should apply constraints for Level 2 (1280x720) to the active video track
    And the video stream should not be stopped or recreated
    And the current resolution level should be updated to 2

  Scenario: Attempt to step down at the lowest level
    Given the current resolution level is 0 (320x240)
    When the external governor commands a "step down"
    Then the throttle should ignore the command
    And the current resolution level should remain 0
    And no constraints should be applied to the video track

  Scenario: Attempt to step up at the highest level
    Given the current resolution level is 2 (1280x720)
    When the external governor commands a "step up"
    Then the throttle should ignore the command
    And the current resolution level should remain 2
    And no constraints should be applied to the video track

  Scenario: Browser rejects the requested constraints (OverconstrainedError)
    Given the current resolution level is 1 (640x480)
    And the browser hardware does not support Level 2 (1280x720)
    When the external governor commands a "step up"
    And the track.applyConstraints() throws an OverconstrainedError
    Then the throttle should catch the error
    And the video stream should remain active at Level 1 (640x480)
    And the current resolution level should remain 1
```
