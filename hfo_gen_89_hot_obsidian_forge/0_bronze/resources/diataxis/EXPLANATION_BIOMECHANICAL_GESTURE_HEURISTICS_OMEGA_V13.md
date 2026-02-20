---
schema_id: hfo.mosaic_microkernel_header.v3
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
bluf: "Why explicit biomechanical structural heuristics (palm width normalisation, digit curl, structural locks) outperform generic shape-bounding-box ML confidence scores for stable, Anti-Midas spatial pointing in a webcam-only, RGB MediaPipe pipeline."
primary_port: P0
secondary_ports: [P2, P4]
diataxis_type: explanation
tags: [bronze, forge:hot, omega, v13, gesture, biomechanical, mediapipe, heuristic, anti-midas, pointing, fsm, hci, spatial-computing]
generated: "2026-02-20"
status: DRAFT — operator review required
related:
  - REFERENCE_GESTURE_FSM_ANTI_MIDAS_STATE_MACHINE.md
  - HOWTO_TUNE_GESTURE_FSM_THRESHOLDS.md
  - TUTORIAL_BUILD_GESTURE_CURSOR_FROM_SCRATCH.md
  - REFERENCE_OMEGA_GEN10_TOUCH2D_VERTICAL_SLICE_TILE_SPEC_V1 (doc 106)
---

# Explanation: Why Biomechanical Heuristics for Gesture Classification

> **The short answer:** A raw ML confidence score tells you "how much does this look like a pointer gesture?" A biomechanical score tells you "is the tendon structure of this hand currently physically capable of executing a stable pointing gesture?" These are different questions. The second question reliably predicts cursor stability; the first does not.

---

## 1. The Problem With Generic ML Confidence

MediaPipe's `GestureRecognizer` outputs a `score` between 0 and 1 for gesture categories like `Pointing_Up`. This score is a posterior probability from a classification model trained on a labelled dataset of hand images.

The failure mode is predictable: the model was not trained on *your* user's hand, your specific lighting, your camera distance, or your background. When the model sees a hand near a threshold (e.g., 0.52 vs 0.48), the confidence bounces frame-to-frame even though the user's *intent* has not changed. Feeding that unstable signal directly into a cursor control system produces the well-documented "virtual mouse thrash."

**Root cause:** The ML score conflates two separate questions into one number:
1. *Does this hand shape look like a pointer gesture?* (pattern matching)
2. *Is this hand in a biomechanically stable configuration for pointing?* (structural state)

---

## 2. What "Biomechanical Stability" Means in This Context

When a human points at something with intent — reaching for a button, selecting an item on a wall TV — the following anatomical events co-occur:

| Event | Why it happens |
|-------|---------------|
| Index finger extends | Required to produce the pointing vector |
| Middle, ring, pinky fingers curl | FDP/FDS tendons retract — provides a physical platform for the extended index |
| Thumb moves toward middle metacarpal | The anatomical "pinch brace" — the flexor pollicis longus stabilises the index extensor by providing a counter-resistance |
| Wrist stiffens slightly | Consequence of the overall tendon tension pattern |

This is a **structural lock**, not just a visual shape. Once in this configuration, small frame-to-frame ML noise does not change the underlying physical state.

A structural heuristic measures the *evidence of this lock directly* rather than asking a classifier to infer it.

---

## 3. The Scale-Invariant Structural Score

The key engineering insight is using **palm width** as the normalisation unit. Every person has a different hand size. Every user is at a different distance from the camera. Palm width (landmark[5]–landmark[17], index MCP to pinky MCP) scales with both, so dividing a distance measurement by palm width produces a scale-invariant structural ratio.

```
pointerLock = clamp01((1.5 - distNorm(thumb_tip, middle_PIP)) / 1.0)
```

This measures how close the thumb tip (landmark 4) is to the middle finger's PIP joint (landmark 10), normalised by palm width. A **high score** means the thumb is physically braced near the middle finger — the stabilising grip.

### ⚠ P4 Critique: The Contact Point is Approximate

The anatomically precise brace location is the lateral surface of the **index finger metacarpal** or the middle finger **metacarpal base** (landmark 9 vicinity), not the middle PIP joint (landmark 10). For typical pointing, landmark 10 will produce a functional but slightly underestimated pointerLock score.

*This is acceptable as a first-order heuristic but should be noted in the tuning registry. Users with naturally wide thumb-to-index grip may need a higher threshold offset.*

### ⚠ P4 Critique: Scale Invariance Degrades Under Rotation

Palm width (landmark 5 to 17) is the 2D projected distance, not the 3D true distance. At hand rotation angles >45° (common when pointing sideways at a large display), the projection foreshortens, collapsing the normalisation unit toward zero. All structural ratios become unreliable.

*Mitigation: consider using the wrist-to-middle-MCP distance (landmark 0 to 9) as a more rotation-stable base unit, or accept the limitation and note it in the reference spec.*

---

## 4. Why RGB MediaPipe is Fundamentally Different from Leap/Vision Pro

The analysis often references "what Apple and Ultraleap researched." This is technically misleading and matters for calibration of expectations:

| System | Sensor | Depth Model | Environment |
|--------|--------|-------------|-------------|
| Leap Motion / Ultraleap | Infrared stereo | True 3D point cloud | Controlled desk environment |
| Apple Vision Pro | LiDAR + structured light | True 3D mesh | Worn on face, millimetre precision |
| MediaPipe (this system) | RGB webcam | 2D landmark projection | Living room, TV distance, variable lighting |

MediaPipe does infer a `z` value but it is a learned *estimate* from a single 2D image, not a measured depth signal. Scale-invariant ratios are a compensatory technique precisely because true 3D is unavailable.

The fundamental insight — brace stability → cursor stability — is genuinely sound and aligns with all three research traditions. The *implementation target* (RGB, 2D, TV-distance) is significantly more constrained than the IR/3D sensor systems.

---

## 5. The Two-Layer Implication: Why the FSM Exists

Even a perfect biomechanical structural score does not eliminate frame-to-frame variance in an RGB pipeline. Lighting transients, motion blur, and partial occlusion all degrade the structural score ephemerally without the hand's physical state changing.

The correct architecture therefore has two layers:

```
Layer 1: Biomechanical Sensor
  - Measures structural state per frame (no memory)
  - Outputs: raw gesture label + structural confidence

Layer 2: Intent FSM
  - Accumulates dwell evidence across frames
  - Transitions only when enough evidence accumulates (leaky bucket)
  - Strictly restricts which transitions are legal (strict state graph)
```

This is the Anti-Midas architecture. The FSM's role is not to *detect* gestures — the sensor handles that. The FSM's role is to decide when a gesture has been *sustained with intent* long enough to act on it.

---

## 6. What This Buys in Practice

| Without biomechanical structure | With biomechanical structure |
|--------------------------------|------------------------------|
| Threshold bounces on "is this a pointer?" | Threshold stable on "is the hand braced?" |
| FSM fed fluctuating confidence → leaky bucket fills/drains rapidly | FSM fed stable structural score → bucket fills steadily, drains on genuine state change |
| Child makes pointing gesture → cursor fires immediately → draws on everything | Child must extend index AND form the thumb brace AND sustain it for N frames → Anti-Midas preserved |
| Camera noise → spurious clicks | Camera noise → leaks buckets, does not reach overflow threshold |

---

## 7. Summary

Biomechanical structural heuristics are not a replacement for ML — they are a *pre-filter* that converts raw landmark geometry into a signal that respects the underlying physics of the hand. That signal is stable across frame noise, scale-invariant within limits, and structurally meaningful. When composited with a strict FSM behind it, the result is a cursor control system that tracks user *intent* rather than user *frame*.

The documented approach is architecturally sound. The two documented limitations — landmark contact point approximation and rotation-induced scale collapse — are known, bounded, and tunable. They do not invalidate the concept; they define its calibration envelope.

---

*Generated 2026-02-20 by P4 Red Regnant. Bronze layer — validate before promotion.*
