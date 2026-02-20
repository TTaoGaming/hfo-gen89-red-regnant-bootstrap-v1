---
schema_id: hfo.mosaic_microkernel_header.v3
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
bluf: "Operator procedure for calibrating GestureFSM confidence thresholds, dwell limits, and biomechanical scoring weights for a specific deployment environment (lighting, camera distance, user population). Assumes gesture_fsm.ts and mediapipe_vision_plugin.ts are already wired to the P1 bus."
primary_port: P2
secondary_ports: [P0, P7]
diataxis_type: how_to
tags: [bronze, forge:hot, omega, v13, gesture, fsm, tuning, calibration, thresholds, leaky-bucket, schmitt, biomechanical, how-to]
generated: "2026-02-20"
status: DRAFT — operator review required
related:
  - EXPLANATION_BIOMECHANICAL_GESTURE_HEURISTICS_OMEGA_V13.md
  - REFERENCE_GESTURE_FSM_ANTI_MIDAS_STATE_MACHINE_OMEGA_V13.md
  - TUTORIAL_BUILD_GESTURE_CURSOR_FROM_SCRATCH.md
---

# How-To: Tune GestureFSM Thresholds for Your Environment

> **When to use this:** You have a working gesture cursor but one of the following is happening: clicks fire too eagerly (Anti-Midas failing), cursor draws break too often on short-duration obstructions (coast too short), or the system refuses to recognise pointing (thresholds too high for your camera/lighting).

---

## Prerequisites

- `mediapipe_vision_plugin.ts` is running and publishing `{gesture, confidence}` to the P1 bus each frame
- `gesture_fsm.ts` is consuming that stream
- You have a frame-level **debug overlay** that displays: current FSM state, bucket values, and structural confidence score per frame
  *(If you don't have this: add a `getDebugInfo()` method to GestureFSM that returns `{state, buckets, coast_ticks, current_confidence}`.)*
- You can vary your environment: background, lighting, hand distance, and user

---

## Step 1: Measure Your Structural Confidence Distribution

**Goal:** Understand what confidence values your sensor actually produces for each gesture in your environment. Do not guess — measure.

1. Enable the debug overlay.
2. Hold each gesture for 10 seconds each: `open_palm`, `pointer_up`, `closed_fist`.
3. For each gesture, record the min, typical, and max `maxScore` (the confidence passed to the FSM).
4. Note transitions: what confidence do you get during the **transition between** `open_palm` and `pointer_up`?

**Expected findings in a typical living-room/TV setup:**

| Gesture | Structurally strong hand | Partially occluded | Low light |
|---------|--------------------------|-------------------|-----------|
| `open_palm` | 0.65–0.85 | 0.45–0.60 | 0.30–0.50 |
| `pointer_up` | 0.60–0.80 | 0.40–0.55 | 0.25–0.45 |
| `closed_fist` | 0.70–0.90 | 0.50–0.65 | 0.35–0.55 |
| Transition phase | 0.30–0.55 typical | — | — |

---

## Step 2: Set `conf_high` and `conf_low`

**Rule:** `conf_high` should be set to *just above the top of your transition-phase distribution*. `conf_low` should be set to *just below the bottom of your weakest clean gestures*.

The goal: clean gestures consistently exceed `conf_high`. Transition noise stays in or below the hysteresis band. Complete signal loss drops below `conf_low`.

**Starting values:**

| Environment | `conf_high` | `conf_low` |
|------------|-------------|------------|
| Good lighting, close camera (~60cm) | 0.65 | 0.50 |
| Mixed/side lighting, medium (~90cm) | 0.58 | 0.42 |
| Poor lighting or far camera (~150cm+) | 0.48 | 0.32 |

**Verify:** After setting, run the debug overlay. The `current_confidence` in the overlay should stay comfortably above `conf_high` during clean held gestures and drop into or below the band during transitions. If clean gestures hover in the band, lower `conf_high` by 0.05.

---

## Step 3: Tune Dwell Limits (Bucket Overflow Thresholds)

Dwell limits control how many **milliseconds** of sustained gesture evidence are required before a transition fires. All limits are framerate-independent — the FSM accumulates elapsed ms per frame.

| Parameter | Too High → | Too Low → | Default | Recommended Range |
|-----------|-----------|-----------|---------|-------------------|
| `dwell_limit_ready_ms` | System feels unresponsive to arming | Accidental arming from open-palm transit | 100ms | 80–200ms |
| `dwell_limit_commit_ms` | Click registration lags noticeably | Accidental clicks from brief flicks | 100ms | 60–150ms |
| `coast_timeout_ms` | Hand loss keeps cursor pinching (ghost-draw) | Jittery hand breaks draw on momentary occlusion | 500ms | 300–800ms |

**User population adjustments:**

- **Young children (4–8):** Increase `dwell_limit_commit_ms` to 180–220ms. They jab and flick their index finger; they rarely sustain the pointing gesture without intent.
- **Adults:** Defaults (100ms/100ms) work well.
- **Users with tremor:** Increase `dwell_limit_ready_ms` and `dwell_limit_commit_ms` to 180–250ms. Their gestures drift but intent is sustained.

---

## Step 4: Tune Coast Timeout

`coast_timeout_ms` = milliseconds of consecutive zero/low-confidence input before the FSM resets to IDLE. Default: 500ms.

**If mid-draw breaks are occurring (the line stops when the user briefly occludes their hand):**
- Increase `coast_timeout_ms` to 600–1000ms.

**If ghost-cursor lingers too long after user moves out of frame:**
- Decrease `coast_timeout_ms` to 250–350ms.

**⚠ Warning: coast risk under COMMIT_COAST.** See FSM-V1 in the Reference doc. If you increase coast timeout significantly, ensure your pointer-event emitter guards against teleport events on recovery (velocity gate).

---

## Step 5: Tune `pointerLock` Threshold and Scoring Weights

This is the most environment-specific tuning. It affects the raw `pointerUpScore` in `classifyHand()`.

The `pointerLock` formula is:

```
thumbToMiddleDist = dist3(landmarks[4], landmarks[12]) / palmWidth
pointerLock = clamp01((1.5 - thumbToMiddleDist) / 1.0)
```

The constant `1.5` is the "activation distance" — when thumb tip (lm[4]) is within 1.5 palm-widths of the middle finger **fingertip** (lm[12]), the lock score starts building.

**To diagnose:** Ask your user to make a clear pointing gesture and read the debug overlay's `maxScore` for `pointer_up`. If it is consistently below `conf_high`:

1. **Check that the user's thumb is actually bracing.** Some users point with the thumb fully extended away. Their `pointerLock` score will be near 0. Coach them to pinch the thumb toward the middle finger.
2. **If the user genuinely cannot form the brace** (mobility limitation, child hand proportions): increase the activation constant from `1.5` to `2.0`, or reduce `pointerLock`'s weight coefficient from `0.30` to `0.15` and redistribute to `(1-indexCurl)`.

**Weight adjustment table:**

| User type | `indexCurl` weight | `pointerLock` weight | Notes |
|-----------|-------------------|---------------------|-------|
| Standard adult | 0.35 | 0.30 | Default |
| Young child | 0.45 | 0.20 | Children have looser thumb anatomy |
| Mobility-limited | 0.50 | 0.10 | Rely primarily on index extension |

---

## Step 6: Regression Test After Each Change

After any parameter change, run all five SBE invariants from the Reference doc before declaring the tuning done. Pay special attention to:

- **Anti-Midas invariant** — does it still block IDLE→COMMIT shortcut?
- **Anti-thrash invariant** — does a 2-frame `open_palm` during drawing leave the state in `COMMIT_POINTER`?
- **Coast timeout** — does the FSM still return to IDLE after the configured timeout?

---

## Tuning Log Template

Record every change to prevent regression:

```
Date:
Environment: [lighting / camera distance / user population]
Changed: [parameter name] from [old value] to [new value]
Reason: [observed symptom]
Outcome: [pass / fail / partial]
SBE regression: [all pass / fails: list]
```

---

*Generated 2026-02-20 by P4 Red Regnant. Bronze layer — validate before promotion.*
