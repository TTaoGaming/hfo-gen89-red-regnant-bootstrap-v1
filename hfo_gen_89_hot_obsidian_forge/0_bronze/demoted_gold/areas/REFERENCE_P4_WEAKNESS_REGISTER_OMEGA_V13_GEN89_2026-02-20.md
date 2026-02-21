---
schema_id: hfo.gen89.diataxis.reference.v1
medallion_layer: gold
doc_type: reference
source: p4_payload
port: P4
commander: Red Regnant
tags: p4,disrupt,omega_v13,weakness,vulnerability,gesture_fsm,test_coverage,architecture,reference
generated: 2026-02-20
mutation_score: 0
bluf: "P4 Red Regnant adversarial weakness register for Omega v13 Microkernel and Gen89 HFO system. Synthesised from FSM-V1–V9 stigmergy events, Stryker coverage audit, arch-violation ATDD spec, patrol telemetry, and session handoffs. Ranked by blast radius. Do not promote to operate — use to prioritise remediation."
---

# P4 Red Regnant — Weakness Register
## Omega v13 Microkernel · Gen89 HFO · 2026-02-20

> **Document type:** REFERENCE — exhaustive catalogue of known weaknesses, prioritised by blast radius.
> **Commander:** Red Regnant · Port P4 · DISRUPT
> **Galois pair:** P5 IMMUNIZE (Pyre Praetorian) — every weakness here is a gate P5 must close.
> **Medallion:** Gold — this document is a hardened audit artefact, not a speculative analysis.
> **Source signal:** Stigmergy events 16559–16567 (FSM vulnerabilities), patrol report id 16594, handoff events 15793/15964, Stryker config inspection, microkernel_arch_violations.spec.ts, session yields 07:00–18:41 UTC.

---

## How to Read This Register

Each weakness entry is assigned:

| Field | Meaning |
|---|---|
| **ID** | Stable identifier. Never recycled. |
| **Blast radius** | CRITICAL / HIGH / MEDIUM / LOW — impact if not fixed |
| **Layer** | Which architectural layer is affected |
| **Status** | OPEN / IN-PROGRESS / FIXED / ACCEPTED |
| **Fix class** | CODE / DOC / TEST / PROCESS / ARCHITECTURE |
| **Effort** | S (hours) / M (days) / L (week+) |
| **Meadows leverage** | Which Meadows level the fix operates at |

Entries are sorted by blast radius (CRITICAL first), then by effort (smallest first within a tier).

---

## TIER 0 — CRITICAL (Existential Risk to Ship)

### W-CRIT-001 · Core Gesture Pipeline Has Zero Mutation Testing

| | |
|---|---|
| **ID** | W-CRIT-001 |
| **Blast radius** | CRITICAL |
| **Layer** | Test infrastructure |
| **Status** | OPEN |
| **Fix class** | TEST |
| **Effort** | M |
| **Meadows leverage** | L8 (Rules — gates enforce quality floor) |

**Finding:** Stryker mutation testing is configured only for three files:
- `plugin_supervisor.ts`
- `highlander_mutex_adapter.ts`
- `iframe_delivery_adapter.ts`

The following files — which are the **entire gesture sensing and classification pipeline** — have **zero mutation coverage**:

```
gesture_fsm.ts            ← leaky-bucket dwell state machine
mediapipe_vision_plugin.ts ← landmark scoring, palmWidth, thumbMiddleScore
gesture_bridge.ts         ← pointer event emission translation layer
gesture_fsm_plugin.ts     ← plugin lifecycle wrapper
behavioral_predictive_layer.ts ← GA-based movement prediction
```

**Why this is CRITICAL:** The dwell accumulator logic, landmark scoring weights, and state transition guards are the core value proposition of Omega v13. If a mutant survives in `gesture_fsm.ts` (e.g., `>` mutated to `>=` in the overflow check), the system silently misfires. Without mutation testing, the tests are not tests — they are documentation.

**Remediation:**
1. Add `gesture_fsm.ts`, `mediapipe_vision_plugin.ts`, `gesture_bridge.ts` to `stryker.config.json` `mutate` array.
2. Write a Jest unit test suite for `GestureFSM` (dwell fill, leak, overflow, coast) — the current `test_gesture_bridge.ts` tests the bridge, not the FSM directly.
3. Target minimum 80% mutation score on these three files before promoting to silver.

**Acceptance criterion:** `npx stryker run` exits green on gesture pipeline files with ≥80% mutation score.

---

### W-CRIT-002 · Multi-Hand FSM Instantiation Pattern Unverified (FSM-V8)

| | |
|---|---|
| **ID** | W-CRIT-002 (maps to FSM-V8) |
| **Blast radius** | CRITICAL (silently broken with 2-hand use) |
| **Layer** | gesture_fsm.ts instantiation site |
| **Status** | OPEN |
| **Fix class** | CODE + TEST |
| **Effort** | S |
| **Meadows leverage** | L5 (Negative feedback — prevents thrash) |

**Finding:** `RawHandData` includes `handId: index`. `GestureFSM` owns per-hand state (dwell accumulators, coast timer). No evidence was found of `new GestureFSM()` being instantiated in a `Map<number, GestureFSM>` pattern in `gesture_bridge.ts` or `plugin_supervisor.ts`.

**If a single `GestureFSM` instance is fed alternating data from two hands:**
- Left hand classifies READY → fills dwell
- Right hand classifies IDLE → leaks dwell (reads as the other hand's state)
- Accumulator thrashes between hands — no gesture ever completes
- System appears broken to the user; no error is thrown

**Additional hazard:** MediaPipe handedness classification (`Left`/`Right`) is unreliable under hand rotation. Wrist position continuity is the correct identity signal, not handedness string.

**Remediation:**
1. In `gesture_bridge.ts`: change to `Map<number, GestureFSM>` keyed by `handId`.
2. On hand detection: `map.get(id) ?? new GestureFSM(config)` → set in map.
3. On hand loss: keep FSM alive for `coast_timeout_ms + 500ms` grace before pruning.
4. Add unit test: feed two alternating-hand streams to same bridge, assert each hand independently fires a click.

---

### W-CRIT-003 · 6 Architectural Violations Outstanding (RED Tests Not Green)

| | |
|---|---|
| **ID** | W-CRIT-003 |
| **Blast radius** | CRITICAL (structural integrity) |
| **Layer** | Microkernel architecture |
| **Status** | OPEN (ATDD specs written, implementations pending) |
| **Fix class** | ARCHITECTURE + CODE |
| **Effort** | L |
| **Meadows leverage** | L9 (Self-organisation — restructuring the system) |

**Finding:** `microkernel_arch_violations.spec.ts` defines 6 ATDD acceptance criteria, mapped to braided mission threads. As of 2026-02-20, all 6 have specs but several are RED (failing). In order of priority:

| Violation | Mission thread | Meadows | Status |
|---|---|---|---|
| **V1: Global Singleton Contraband** (EventBus exported as module-level singleton) | omega.v13.arch.v1_global_singleton | L8 | RED |
| **V2: God Object** (PluginSupervisor doing too much — routing + lifecycle + config) | omega.v13.arch.v2_god_object | L9 | RED |
| **V3: Double Debounce** (both gesture_fsm and gesture_bridge debounce pointer events) | omega.v13.arch.v3_double_debounce | L5 | RED |
| **V4: Rogue Agents** (plugins adding EventBus listeners without cleanup contract) | omega.v13.arch.v4_rogue_agents | L8 | PARTIAL |
| **V5: PAL Leaks** (config values read directly rather than via PAL resolver) | omega.v13.arch.v5_pal_leaks | L6 | RED |
| **V6: Stub Implementations** (several spec files have no backing implementation) | omega.v13.arch.v6_stub_impls | L3 | OPEN |

**V1 is the highest-risk:** the global EventBus singleton breaks test isolation. Every Jest test that imports `event_bus.ts` shares state with every other test. This means test order dependency — a hidden source of flaky tests and false GREEN results.

**Remediation:** Follow the RED → GREEN → REFACTOR discipline already encoded in `microkernel_arch_violations.spec.ts`. Fix one violation per session.

---

## TIER 1 — HIGH (Incorrect Behaviour Under Foreseeable Real-World Conditions)

### W-HIGH-001 · Ghost-Draw Teleport on COMMIT_COAST Recovery (FSM-V5)

| | |
|---|---|
| **ID** | W-HIGH-001 (maps to FSM-V5) |
| **Blast radius** | HIGH |
| **Layer** | gesture_fsm.ts:231 + gesture_bridge.ts caller |
| **Status** | OPEN |
| **Fix class** | CODE + TEST |
| **Effort** | S |
| **Meadows leverage** | L5 (Negative feedback gate on re-entry) |

**Finding:** `isPinching()` returns `true` for both `COMMIT_POINTER` and `COMMIT_COAST`. `coast_timeout_ms = 500ms`.

**Failure scenario:**
1. User is drawing a stroke (COMMIT_POINTER, isPinching=true).
2. Hand exits camera frame — FSM transitions to COMMIT_COAST.
3. User re-enters camera frame at a **different screen position** within 500ms.
4. `isPinching()` is still `true`. Gesture bridge emits `pointermove` immediately at the new position.
5. Result: a **teleport stroke** is drawn from old position to new position — a ghost line the user did not intend.

This is directly reproducible in the tldraw integration whenever the user's hand briefly leaves the camera boundary during a drawing gesture. This **will** be reported as a serious bug by first-time users.

**Remediation:**
1. Add `isCoasting(): boolean` to `GestureFSM` public API.
2. In gesture bridge: detect transition from `isPinching() && isCoasting()` → `isPinching() && !isCoasting()`.
3. Apply velocity teleport gate: `if (delta_position > 0.1 normalised units) { emit pointerup → wait 1 frame → emit pointerdown at new position }`.
4. Add regression test: simulate coast + re-entry at >0.1 delta, assert pointerup is emitted.

---

### W-HIGH-002 · Behavioral Predictive Worker Integration Unverified

| | |
|---|---|
| **ID** | W-HIGH-002 |
| **Blast radius** | HIGH (silent failure — worker silently not working) |
| **Layer** | behavioral_predictive_layer.ts + behavioral_predictive_worker.ts |
| **Status** | OPEN |
| **Fix class** | TEST |
| **Effort** | S |
| **Meadows leverage** | L5 (Verification gate) |

**Finding:** The `BehavioralPredictiveLayer` was refactored to offload its GA evolutionary loop to `behavioral_predictive_worker.ts` via `Worker` (session yield 07:33). The spec `behavioral_predictive_layer.spec.ts` was created. However, no stigmergy event confirms:
- The worker postMessage protocol has been tested end-to-end.
- The worker is instantiated by `BehavioralPredictiveLayer` at runtime (not only at test time).
- Chrome/Chromium's Worker serialisation constraints on the GA population model are exercised.
- The fallback behaviour when the Worker is unavailable (e.g., in Jest JSDOM environment) is defined.

**Remediation:**
1. Confirm `behavioral_predictive_layer.spec.ts` has a test that actually boots the Worker and receives a prediction.
2. Add JSDOM worker mock + fallback path test.
3. Add a `console.warn` + graceful fallback to main-thread synchronous fallback if Worker spawn fails.

---

## TIER 2 — MEDIUM (Incorrect Behaviour Under Specific but Predictable Conditions)

### W-MED-001 · palmWidth Collapses Under Lateral Pointing (FSM-V3)

| | |
|---|---|
| **ID** | W-MED-001 (maps to FSM-V3) |
| **Blast radius** | MEDIUM |
| **Layer** | mediapipe_vision_plugin.ts:252 |
| **Status** | OPEN |
| **Fix class** | CODE |
| **Effort** | S |
| **Meadows leverage** | L1 (Parameter change: replace landmark pair) |

**Finding:** `palmWidth = dist3(lm[5], lm[17])` — the 2D projected distance between index MCP and pinky MCP.

At hand yaw rotation >~45 degrees (common when pointing sideways at a large TV display), this projection foreshortens. All derived structural ratios (`thumbScore`, `thumbMiddleScore`) divide by a collapsing denominator and produce unreliable output — false positives and false negatives in gesture classification multiply.

**This is a core use case:** the system is explicitly designed for TV-distance interaction where lateral arm extension is a primary movement pattern.

**Remediation (pick one):**
- **Option A (recommended):** Replace `dist3(lm[5], lm[17])` with `dist3(lm[0], lm[9])` (wrist to middle MCP) — rotation-stable under typical pointing postures.
- **Option B:** Suppress all gesture output when estimated yaw >45 degrees, emit `IDLE` explicitly.
- **Option C (minimum):** Document constraint in REFERENCE and HOWTO with angular limit.

---

### W-MED-002 · thumbMiddleScore Uses Anatomically Wrong Landmark (FSM-V2)

| | |
|---|---|
| **ID** | W-MED-002 (maps to FSM-V2) |
| **Blast radius** | MEDIUM |
| **Layer** | mediapipe_vision_plugin.ts:256 |
| **Status** | OPEN |
| **Fix class** | CODE |
| **Effort** | S |
| **Meadows leverage** | L1 (Parameter: change landmark index) |

**Finding:**
```typescript
thumbMiddleScore = clamp01((1.5 - dist3(lm[4], lm[12]) / palmWidth))
```

`lm[12]` is the **middle fingertip** (DIP joint) — it moves significantly as the finger curls. The anatomical brace that stabilises the pinch brace grip contacts the proximal phalanx base near `lm[9]` (middle MCP), which is nearly fixed regardless of curl state.

Using `lm[12]` (a moving point) means `thumbMiddleScore` is coupled to curl state, not brace proximity. The score fires when it shouldn't and fails when it should (finger curled = brace contact reduced = score misleadingly drops).

**The original proposed implementation used `lm[10]` (PIP joint). The committed code uses `lm[12]` — even further from the correct measurement point.**

**Remediation:**
```typescript
// Before:
thumbMiddleScore = clamp01((1.5 - dist3(lm[4], lm[12]) / palmWidth))
// After:
thumbMiddleScore = clamp01((1.5 - dist3(lm[4], lm[9]) / palmWidth))
```
The `1.5` activation constant may need empirical recalibration after the change. Capture confidence distributions before and after with real hand data.

---

### W-MED-003 · Overscan Transform in Sensor Layer (SRP Violation) (FSM-V6)

| | |
|---|---|
| **ID** | W-MED-003 (maps to FSM-V6) |
| **Blast radius** | MEDIUM |
| **Layer** | mediapipe_vision_plugin.ts:271–275 |
| **Status** | OPEN |
| **Fix class** | ARCHITECTURE (move concern to correct owner) |
| **Effort** | S |
| **Meadows leverage** | L3 (Physical structure — move transform to correct tile) |

**Finding:** Overscan scale/offset mapping is applied inside `classifyHand()` inside `MediaPipeVisionPlugin`.

Per the Gen10 tile spec (doc 106), overscan is a **display-time transform** owned by `p7_orchestrator`. Embedding it in the sensor means:
- A change to display configuration (TV overscan settings, window resize, projector calibration) requires modifying the biomechanical sensor file.
- The sensor outputs **display-space** coordinates, not normalised sensor coordinates. Downstream tiles cannot reuse the sensor output without baking in the display config.
- Unit tests for the sensor must mock display config — a layering violation.

**Remediation:**
1. Remove overscan scale/offset from `classifyHand()`. Emit raw mirrored normalised `(x, y)` ∈ [0,1] on P1 bus.
2. Move overscan transform to `p7_orchestrator` or a dedicated `cursor_2d` tile.
3. Remove `config.overscanScale` from `MediaPipeVisionConfig`.
4. Bind the PAL key `OverscanScale` in the orchestrator, not the sensor.

---

### W-MED-004 · Single Dwell Accumulator Merges Competing Release Gestures (FSM-V9)

| | |
|---|---|
| **ID** | W-MED-004 (maps to FSM-V9) |
| **Blast radius** | MEDIUM (accessibility hazard) |
| **Layer** | gesture_fsm.ts:handleCommitPointer (~line 175) |
| **Status** | OPEN |
| **Fix class** | CODE |
| **Effort** | M |
| **Meadows leverage** | L4 (Delay structure — independent bucket timings) |

**Finding:** In `handleCommitPointer()`, **both** `open_palm` and `closed_fist` gestures fill the **same** `dwell_accumulator_ms`. If the user alternates between `open_palm` and `closed_fist` rapidly (tremor, neuromotor variability, uncertain release), both contribute to the same bucket and may reach overflow. The transition target is determined by the **current-frame gesture at overflow** — which under alternation is non-deterministic from the user's perspective.

**Accessibility impact:** Users with hand tremor or neuromotor conditions (Parkinson's, essential tremor) are the population most likely to exhibit rapid gesture alternation. This creates a non-deterministic release gesture for exactly the users for whom precise control is most important.

**Remediation (defer until W-CRIT-002 and W-HIGH-001 resolved):**
- Split into `dwell_open_palm_ms` and `dwell_closed_fist_ms` — independent fill/leak buckets in `COMMIT_POINTER` state.
- Accept Option A (document and defer) until higher-priority vulns are resolved.

---

### W-MED-005 · PREY8 Memory Loss Epidemic (60/hour at Peak)

| | |
|---|---|
| **ID** | W-MED-005 |
| **Blast radius** | MEDIUM (process integrity) |
| **Layer** | PREY8 bookend discipline |
| **Status** | OPEN (structural) |
| **Fix class** | PROCESS |
| **Effort** | S |
| **Meadows leverage** | L6 (Information flows — close the nonce chain) |

**Finding:** Singer daemon reports **60 memory loss events in the last hour** (18:40 UTC report). Patrol log shows **10 orphaned perceives**, **184 gate blocks**, **77 tamper alerts** in 24h.

Root cause: the high session churn of the Omega v13 sprint (05:00–08:00 UTC) generated many perceive events that were never closed with a yield. The MCP PREY8 tools were used rapidly under context-window pressure, leading to perceive events fired and then the agent losing context before reaching yield.

**Impact:** Every orphaned perceive is a dead-end session. The stigmergy trail has gaps. Future agents reading the trail will encounter `memory_loss` events where work happened but was not recorded.

**Remediation:**
1. Run `prey8_detect_memory_loss` at the start of every session to surface orphans before opening a new perceive.
2. Enforce the PREY8 bookend as the literal first and last tool call — not an afterthought.
3. Consider a yield template in the agent prompt that forces `summary`, `artifacts_created`, `next_steps` to be populated from the session before closing.

---

### W-MED-006 · P5/P7 Strange Loop Incomplete

| | |
|---|---|
| **ID** | W-MED-006 |
| **Blast radius** | MEDIUM (strategic gap) |
| **Layer** | PREY8 strange loop architecture |
| **Status** | OPEN |
| **Fix class** | PROCESS |
| **Effort** | M |
| **Meadows leverage** | L9 (Self-organisation) |

**Finding:** Stigmergy event 15793 (16:24 UTC) records that the 8-port strange loop session was interrupted. Two critical commander PREY8 loops were never executed:
- **P5 Pyre Praetorian** — full Perceive→React→Execute→Yield focused on immunization/gate defence. This means the P5 blue-team perspective on today's work has never been formally recorded.
- **P7 Spider Sovereign** — full loop focused on C2 steering. The system currently has no formal P7-layer steering record for the current sprint trajectory.

Without P5 and P7 loop closures, the system is operating on P4 adversarial signal alone — strife without the immunizing and navigational counterweights.

---

## TIER 3 — LOW (Quality, Documentation, and Provenance Issues)

### W-LOW-001 · Gesture Scoring Weights Lack Empirical Provenance (FSM-V4)

| | |
|---|---|
| **ID** | W-LOW-001 (maps to FSM-V4) |
| **Fix class** | DOC |
| **Effort** | S |
| **Meadows leverage** | L1 |

```typescript
pointerUpScore = (1 - indexCurl) * 0.4
              + middleCurl       * 0.1
              + ringCurl         * 0.1
              + pinkyCurl        * 0.1
              + thumbMiddleScore * 0.3
```

These weights are undocumented heuristics with no empirical basis. Without provenance, future agents cannot distinguish deliberate design from arbitrary starting points. Per Gen10 tile spec §9 (Tuning Parameters Registry), all tunable values must be tagged.

**Fix:** Add above weight constants a comment: `// INITIAL_HEURISTIC 2026-02-20 — not empirically validated`. Add the weight table to REFERENCE diataxis with provenance tag.

---

### W-LOW-002 · "Zero-Latency" Claim Contradicts Anti-Midas Design (FSM-V7)

| | |
|---|---|
| **ID** | W-LOW-002 (maps to FSM-V7) |
| **Fix class** | DOC |
| **Effort** | S |
| **Meadows leverage** | L1 |

Documentation describes the system as "zero-latency". The actual minimum click latency is `dwell_limit_ready_ms (100ms) + dwell_limit_commit_ms (100ms) = 200ms`. This is correct and intentional (Anti-Midas) but calling it zero-latency is internally contradictory and will confuse users who experience the first click taking ~200ms.

**Fix:** Replace all "zero-latency" references with "intent-dwell latency". Document: "minimum ~200ms from arm-raise to first click — tunable, intentional Anti-Midas design."

---

### W-LOW-003 · Apple/Ultraleap Sensor Modality Conflation (FSM-V1)

| | |
|---|---|
| **ID** | W-LOW-003 (maps to FSM-V1) |
| **Fix class** | DOC |
| **Effort** | S |
| **Meadows leverage** | L1 |

The EXPLANATION doc claims the biomechanical brace insight mirrors Apple Vision Pro / Ultraleap research. Apple uses LiDAR + structured light (true 3D mesh). Ultraleap uses IR stereo depth (true 3D point cloud). Omega v13 uses RGB MediaPipe with a learned 2D z-estimate — not a measured depth signal.

The structural insight is correct. The comparison overstates measurement precision available in an RGB-only pipeline.

**Fix:** Acknowledge the directional alignment with IR/3D research, clarify MediaPipe z is inferred not measured. Note the RGB constraint limits scale-invariance relative to depth-sensor systems.

---

### W-LOW-004 · 5 Pareto Spec Files Have No Implementations

| | |
|---|---|
| **ID** | W-LOW-004 |
| **Fix class** | CODE |
| **Effort** | L |
| **Meadows leverage** | L3 |

Spec files created during 08:09 UTC session:
- `foveated_cropping.spec.ts` → `foveated_cropper.ts` (file exists but spec may be ahead of impl)
- `biological_raycasting.spec.ts` → `biological_raycaster.ts` (file exists)
- `webrtc_udp_coasting.spec.ts` → `webrtc_udp_transport.ts` (file exists)
- `symbiote_injector.spec.ts` → `symbiote_injector.ts` (file exists)
- `wood_grain_tuning.spec.ts` → `wood_grain_tuning.ts` (file exists)

These are Pareto-Optimal Spatial OS blueprint specs. Their RED/GREEN status is not confirmed in the stigmergy trail. They represent unverified implementation claims.

**Fix:** Run `npx jest --testPathPattern="pareto|foveated|raycasting|coasting|symbiote|wood_grain"` and record pass/fail to SSOT.

---

### W-LOW-005 · NPU LLM Daemon Not Built (Models Downloaded, Daemon Absent)

| | |
|---|---|
| **ID** | W-LOW-005 |
| **Fix class** | CODE |
| **Effort** | M |
| **Meadows leverage** | L3 |

Session handoff (16:55 UTC, event 15964) identifies as TODO-1 CRITICAL: "Build hfo_npu_llm_daemon.py — NPU is IDLE, models downloaded." The NPU (`qwen3-4b-int4-ov-npu`) has been downloaded to `.hfo_models/npu_llm/` and is ready. No daemon wraps it. The NPU is the lowest-power, lowest-latency inference path available and is completely unused.

**Impact:** All inference routes through Ollama (GPU) or Gemini API. The NPU inference path — designed for always-on low-latency classification — produces zero throughput.

---

## Weakness Priority Matrix

```
BLAST RADIUS  │ EFFORT S     │ EFFORT M          │ EFFORT L
──────────────┼──────────────┼───────────────────┼─────────────────────
CRITICAL      │ W-CRIT-002   │ W-CRIT-001        │ W-CRIT-003
              │ (multi-hand  │ (Stryker gesture  │ (6 arch violations)
              │  FSM map)    │  pipeline)        │
──────────────┼──────────────┼───────────────────┼─────────────────────
HIGH          │ W-HIGH-001   │                   │
              │ (ghost-draw) │ W-HIGH-002        │
              │              │ (worker verify)   │
──────────────┼──────────────┼───────────────────┼─────────────────────
MEDIUM        │ W-MED-001    │ W-MED-004         │
              │ W-MED-002    │ W-MED-005         │
              │ W-MED-003    │ W-MED-006         │
──────────────┼──────────────┼───────────────────┼─────────────────────
LOW           │ W-LOW-001    │ W-LOW-005         │ W-LOW-004
              │ W-LOW-002    │                   │
              │ W-LOW-003    │                   │
```

**Recommended fix order (Pareto front):**
1. **W-CRIT-002** (S effort, CRITICAL blast) — `Map<handId, GestureFSM>` in gesture_bridge.ts
2. **W-HIGH-001** (S effort, HIGH blast) — ghost-draw teleport gate on coast recovery
3. **W-MED-002** (S effort, MEDIUM blast) — `lm[12]` → `lm[9]` in thumbMiddleScore
4. **W-MED-001** (S effort, MEDIUM) — palmWidth landmark rotation fix
5. **W-CRIT-001** (M effort, CRITICAL) — add gesture pipeline to Stryker
6. **W-MED-003** (S effort, MEDIUM) — move overscan to orchestrator
7. **W-LOW-001/002/003** (S effort each) — documentation provenance fixes

---

## What Is Not In This Register

The following areas have been excluded because they are either already mitigated or out of scope for Omega v13 Phase 1:

- **Playwright E2E tests**: `tests/omega_pointer.spec.ts` exists. Its pass/fail state is not confirmed but it is not blocking the gesture core.
- **Temporal rollup**: `temporal_rollup.ts` and `temporal_rollup.test.ts` exist; not P4-flagged.
- **TLDraw integration**: `tldraw_entrypoint.tsx` / `tldraw_layer.html` exist; integration-level only.
- **Babylon.js physics**: `babylon_landmark_plugin.ts` / `babylon_physics.ts` are research spikes, not on critical path.
- **Gen89 SSOT bronze medallion escalation**: All 9,868 documents are bronze. This is a known architectural constraint — not a bug.

---

## Signal Sources

| Signal | Event IDs | Confidence |
|---|---|---|
| FSM-V1 through FSM-V9 | 16559–16567 | HIGH (structural analysis) |
| Stryker config audit | File inspection `stryker.config.json` | HIGH |
| Arch violations spec | File inspection `microkernel_arch_violations.spec.ts` | HIGH |
| PREY8 memory loss | Singer event 16588, patrol 16594 | HIGH |
| Strange loop incomplete | Handoff event 15793 | HIGH |
| NPU idle | Handoff event 15964 | HIGH |
| Behavioral predictive worker | Session yield 07:33 UTC | MEDIUM (no verification event in SSOT) |
| Pareto spec files | Session yield 08:09 UTC | MEDIUM (pass/fail not confirmed) |

---

*Generated: 2026-02-20 · P4 Red Regnant · Gen89 · Operator: TTAO*
*Galois complement: P5 Pyre Praetorian owns the remediation gates.*
*Meadows note: most fixes operate at L1–L5. W-CRIT-003 reaches L9 (self-organisation). The test infrastructure weakness (W-CRIT-001) operates at L8 (rules) — it will not be fixed by adding more code, only by changing what counts as "done".*
