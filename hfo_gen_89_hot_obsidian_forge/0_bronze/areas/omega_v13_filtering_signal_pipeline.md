---
schema_id: hfo.gen89.diataxis.explanation.v1
medallion_layer: bronze
doc_type: explanation
title: "Omega v13 — Signal Filtering & Performance Architecture"
bluf: "MediaPipe Tasks API has NO built-in smoothing. Kalman is our only smoother. Performance target: 30fps via auto resolution ladder. GA is deferred with tuned defaults shipped."
tags: mediapipe,kalman,one-euro,performance,resolution-ladder,gc,babylon,havok
---

# Omega v13 — Signal Filtering & Performance Architecture

*Explanation diataxis. Last updated 2026-02-20.*

---

## 1. Does MediaPipe already smooth landmarks?

**Short answer: No. Not in the Tasks API we use.**

There are two completely different MediaPipe hand-tracking APIs:

| Package | Smoothing? | Our usage? |
|---|---|---|
| `@mediapipe/hands` (legacy, deprecated) | YES — `LandmarksSmoothingCalculator` with 1 Euro Filter internally | NO |
| `@mediapipe/tasks-vision` HandLandmarker (current) | **NO** — pure ML inference, no temporal filter | **YES** |

### What the Tasks API actually does

The `hand_landmarker_graph.cc` source (verified Feb 2026) contains:
- Palm detection model (spatial crop, runs on detection loss only)
- `PreviousLoopbackCalculator` — feeds the previous frame's **bounding rect** back in to skip palm re-detection when confidence is high
- That's it. No velocity filter. No one euro. No exponential smoothing.

The old Hands package had a `LandmarksSmoothingCalculator` that applied a 1 Euro Filter per landmark across frames. Google removed it when porting to the Tasks API to reduce latency.

### What this means for us

Our Kalman filter in `kalman_filter.ts` / `w3c_pointer_fabric.ts` is **not double-smoothing anything**. It is the **only** temporal smoother in the stack. We need it.

The `predict(steps)` method on `KalmanFilter1D` is also the only source of predictive lookahead — no MediaPipe layer provides this.

**1 Euro Filter status:** Not adding it for v13. Kalman with tuned Q/R covers the jitter use case. 1 Euro would be additive only, not a replacement.

---

## 2. What Kalman Q and R mean (and what to ship as defaults)

The GA was supposed to evolve these. GA is deferred. We ship hand-tuned defaults.

| Param | What it controls | Too low | Too high |
|---|---|---|---|
| `Q` (process noise) | How much we trust the model's prediction | Stiff, lags behind fast movement | Jittery, tracks noise |
| `R` (measurement noise) | How much we trust the raw landmark | Cursor drifts from hand | Fast but jittery |

**Recommended defaults for a phone camera at 30fps:**
```typescript
// w3c_pointer_fabric.ts config
smoothingQ: 0.05,   // Low — we trust the Kalman model; landmark noise is real
smoothingR: 10.0,   // High — landmarks jump ±5px each frame at 30fps
```

These values are hand-tested for a 1080p → 30fps pipeline on mid-range devices. When the GA ships, it will evolve `kalmanQ` and `kalmanR` in the `Genotype` and write them back to `W3CPointerFabric.updateConfig()`.

---

## 3. Babylon: Dots now, Havok next

### What's actually in the code today

| File | What it is | Ready to use? |
|---|---|---|
| `babylon_landmark_plugin.ts` | 21 colored spheres per hand, transparent canvas, state color coding, implements `Plugin` interface | **Yes — 1 line to register** |
| `babylon_physics.ts` | Havok velocnertia spring physics, sphere per landmark | **No — uses old `GestureEventPayload` interface, needs `Plugin` wrapping** |

### The teleporting + disappearing problem

Both issues share the same root cause: **direct position assignment**.  
When a landmark jumps frame-to-frame (MediaPipe tracking loss → re-detect), setting `mesh.position.x = newX` immediately teleports the sphere. When confidence drops below threshold, the hand array goes empty and spheres are deallocated or hidden randomly.

**Fix for `babylon_physics.ts`** (Havok path):
- Replace `mesh.position.set(...)` with velocity-drive: `impostor.setLinearVelocity(towardTarget * springK)`
- Gate hand removal behind a 3-frame confidence latch (don't destroy on first empty frame)
- Pool meshes — allocate 21 spheres at startup per max hand slot, never deallocate mid-session

This is the Velocnertia pattern already in `babylon_physics.ts` — it just needs to be wired to the Plugin lifecycle and receive `RawHandData[]` from the event bus instead of `GestureEventPayload`.

### Phase plan

| Phase | Work | File |
|---|---|---|
| v13 now | Register `BabylonLandmarkPlugin` (direct position, no physics, no teleport because we gate on confidence) | `demo_2026-02-20.ts` |
| v13 next | Wrap `BabylonPhysicsPlugin` with Plugin interface, fix teleport via velocity drive | `babylon_physics.ts` |
| v14 | FABRIK inverse kinematics for wrist/finger chain | new file |
| v14+ | MANO parametric hand model | new file |

---

## 4. Performance target: 30fps via resolution ladder

### Why 30fps is the right v13 target

Current gen phone GPUs (Snapdragon 778G, A15) run MediaPipe HandLandmarker at:
- **1080p input → ~15fps** (GPU inference 12ms + frame transfer overhead)
- **720p input → ~25fps**
- **480p input → ~35fps** (comfortably above 30fps budget)

Halving linear resolution quarters the pixel count. Frame rate roughly doubles. The resolution ladder is the most efficient thermal and performance lever we have.

### How the resolution ladder works

`VideoResourceThrottle` in `video_throttle.ts` uses `track.applyConstraints()` — this changes resolution **without stopping the stream**, so no black screen flash.

```typescript
// Suggested ladder for v13
const RESOLUTION_LADDER = [
    { width: 480,  height: 360  },   // Level 0 — thermal/battery save
    { width: 640,  height: 480  },   // Level 1 — default start
    { width: 1280, height: 720  },   // Level 2 — good conditions
    { width: 1920, height: 1080 },   // Level 3 — high-end only
];
```

### Auto-target controller (what we need to build)

A simple PID-style fps observer:
```
every 2 seconds:
  if measured_fps < 25:  step down 1 level
  if measured_fps > 32:  step up 1 level (after 5s stable)
```

This is the **primary thermal throttle** for v13. We don't need anything more sophisticated until 120fps is a target, which requires hardware we don't have yet.

---

## 5. Basic GC hygiene (what matters at 30fps)

At 30fps we have a 33ms frame budget. The hot path is:
```
MediaPipe → classifyHand() → FRAME_PROCESSED → W3CPointerFabric → POINTER_UPDATE → tldraw
```

### What allocates today (and approximately how much it matters at 30fps)

| Allocation | Frames/sec | GC pressure | Fix |
|---|---|---|---|
| `{ x, y }` landmark objects in `classifyHand()` | 30 × 21 × 2 = 1,260/s | Low on desktop, medium on phone | Pre-allocate `Float32Array` pool |
| `mirroredLandmarks.map(...)` creates 21 new objects | 30/s | Low | Mutate in-place or reuse array |
| `RawHandData[]` array creation | 30/s | Negligible | — |

**At 30fps this is unlikely to cause visible jank on any post-2022 phone.** We fix it if profiling shows GC pauses > 5ms. The resolution ladder will give us more headroom than TypedArray pre-allocation for v13.

**At 120fps** (future) the allocation rate x4 and this becomes mandatory.

---

## 6. GA deferred — ship tuned defaults

The genetic algorithm in `behavioral_predictive_layer.ts` evolves `kalmanQ` and `kalmanR`. It is correct code but:
- Has no fitness signal (Shadow Tracker not built)
- Runs on main thread (Worker path broken)
- Even with those fixed, it needs ~50 generations × session data to converge

**v13 decision:** Disable auto-evolution. Ship the hand-tuned defaults from §2. The `BehavioralPredictiveLayer` class stays in the codebase because the genotype schema and population structure are correct — we just don't call `evolve()` on every frame until v14.

When GA ships (v14):
1. Build Shadow Tracker (record target vs actual positions)
2. Fix Worker bundle path
3. Call `evolve()` once per 5-minute session in background
4. Write winning genotype back via `W3CPointerFabric.updateConfig({ smoothingQ, smoothingR })`

---

## 7. Wired connection at v13

WebRTC DataChannel (`webrtc_udp_transport.ts`) is a stub. For v13 demos:
- **Phone → laptop via USB** (Android Debug Bridge screencast or iOS Cable)
- **Chromecast or HDMI dongle** from the phone natively
- **Same-device demo** (phone browser, phone screen cast to TV over native OS mirroring)

The upgrade path when WebRTC ships (v14):
1. Phone opens a signaling server tab
2. TV opens the receiver tab
3. ICE negotiation over a hosted STUN server
4. DataChannel carries `POINTER_UPDATE` JSON at ~30fps (~2KB/s — negligible bandwidth)

---

## Summary: v13 Definitive Scope

| Area | Decision | Status |
|---|---|---|
| Landmark smoothing | Kalman only, Q=0.05 R=10.0 defaults | Already wired |
| 1 Euro Filter | Skip for v13 — not double-smoothing anything, Kalman sufficient | Deferred |
| Babylon dots | Register `BabylonLandmarkPlugin` (confidence-gated, no teleport) | 30 min to wire |
| Babylon Havok physics | Fix Plugin interface, velocity-drive stops teleport | ~3 hrs |
| Resolution ladder | Build auto fps-observer on top of existing `VideoResourceThrottle` | ~4 hrs |
| Performance target | 30fps, drop to 480p if needed | Ladder implements this |
| GA evolution | Disabled; ship tuned defaults | Ship defaults now |
| Shadow Tracker | Deferred to v14 | — |
| WebRTC | Deferred to v14; use wired/Chromecast | — |
| 120fps | Requires future hardware; v15+ | — |
