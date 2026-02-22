---
schema_id: hfo.gen90.omega_v15.context_bundle.state_of_union.v1
medallion_layer: bronze
port: P0
doc_type: llm_context_bundle
bluf: "Omega v13/v14/v15 State of the Union — LLM handoff bundle. 14 months of Omega evolution, v13 TRUE_SIGHT corruption audit, v14 failure mode, Gen90 forge status. For external AI analysis driving v15 clean-room rewrite."
tags: omega,v13,v14,v15,context_bundle,potemkin,corruption,audit,handoff,rewrite,hfo_gen90
date: 2026-02-21
operator: TTAO
---

# OMEGA v15 — LLM Context Bundle: State of the Union

> **Purpose:** This document is a compressed, self-contained briefing for an external LLM to understand the full history and current state of the Omega project. No session context is required beyond this file. Hand this to any capable model for architectural analysis.
>
> **Project:** Omega — Total Tool Virtualization. Any physical tool → digital twin → zero-hardware gesture control.
> **Gen:** 88 generations across 14 months. $904 total investment. Solo dev (TTAO).
> **Compute Scale:** ~5 billion tokens consumed (1.5B proven on OpenRouter + heavy Copilot usage via "cursed ralph wiggums loops").
> **Current task:** Clean-room rewrite as Omega v15 in the HFO Gen90 Hot Obsidian Forge.

---

## 1. What Omega Is (North Star)

**North Star:** *"Total tool virtualization — any physical tool becomes a digital twin, gesture-controlled. Every child, every teacher: $0 interactive whiteboard."*

The core loop is:
```
Phone camera → MediaPipe hand tracking → gesture recognition 
→ W3C Pointer Events → any 2D web app (tldraw, Excalidraw, etc.)
```

You move your finger in air; a dot follows it on a 100-inch screen. Pinch = click. The app (whiteboard, piano, etc.) never knows it is being controlled by a camera — it just receives standard W3C PointerEvents.

**Proven floor (Gen8, v40):** Fully deployed touchless whiteboard at $0 hardware cost vs $3,000+ Epson BrightLink. 80%+ function coverage.

---

## 2. Omega Evolution History (88 Generations)

| Era | Status | Key Fact |
|-----|--------|----------|
| Gen1–Gen7 | Archaeology | Early monolith explorations |
| Gen8 v25.1 | Frozen baseline | 26,223 LOC, TWO-LAYER FSM, stable |
| Gen8 v31 | Latest pre-mosaic | 28,396 LOC, deployed, all green |
| Gen8 v33 | Forensic baseline | 28,967 LOC — hidden state audit |
| Gen8 v40 | FROZEN (mosaic done) | **7,466 LOC**, 10 tiles, -73.9% shed, 8/0 spec pass |
| Gen9 v1 | DONE | 1,109 LOC, 3-state FSM, 9/9 green |
| Gen9 v2 | BLOCKED | Session crashed mid-generation. SBE spec ready (281 lines, 23 tests). |
| Omega v13 | **CURRENT** | Full mosaic microkernel, Plugin architecture, BUT contains Potemkin corruption (see §5) |
| Omega v14 | STALLED | Mutation score stuck at 100% — Green Lie GRUDGE_016 |
| Omega v15 | **TARGET** | Clean-room rewrite in HFO Gen90 forge |

**Architecture decision for v15:** Option C (Import Map Federation) — zero build step, browser-native `<script type=importmap>`, ~400-line kernel. Pareto winner for solo-dev Chromebook.

---

## 3. Alpha Platform (Complete — Do Not Rebuild)

The Alpha Platform (cognitive symbiote swarm) is **22/22 payloads complete**. It underpins Omega but is NOT being rewritten. Key Alpha facts for v15 context:

| Alpha Component | Status | Key Metric |
|-----------------|--------|------------|
| SSOT SQLite | ✅ COMPLETE | 9,868 docs, 9,700+ stigmergy events |
| Zod contract spine | ✅ COMPLETE | 54/54 GREEN |
| PAL (Path Abstraction Layer) | ✅ COMPLETE | 140 blessed paths, `hfo_gen90_pointers_blessed.json` |
| Medallion flow (bronze→silver→gold) | ✅ COMPLETE | Enforced via pre-commit hook |
| P4 red-team matrix | ✅ COMPLETE | 8 ports × 4 columns |
| Stigmergy / blackboard | ✅ COMPLETE | CloudEvents, 9,700+ trail |
| HFO Gen90 Hot Obsidian Forge | ✅ BOOTSTRAPPED | `hfo_gen_90_hot_obsidian_forge/` |

---

## 4. Omega v13 — What Actually Works

### 4.1 Test Coverage
- **73 Jest unit tests** — ALL PASSING
- **16 Playwright E2E tests** — ALL PASSING
- **0 TypeScript compilation errors**
- **6 SBE Gherkin invariant specs** (see §7) — theoretically enforced

### 4.2 Working Core Components

| Component | File | Status | What It Does |
|-----------|------|--------|--------------|
| W3CPointerFabric | `w3c_pointer_fabric.ts` | ✅ WORKING | Kalman-smoothed pointer → W3C PointerEvent emission |
| GestureFSM | `gesture_fsm.ts` + `gesture_fsm_plugin.ts` | ✅ WORKING | 3-state FSM (IDLE → COMMIT_POINTER → READY), anti-Midas dwell timer |
| MediaPipeVisionPlugin | `mediapipe_vision_plugin.ts` | ✅ WORKING | Camera capture → MediaPipe Tasks API hand landmarks |
| SymbioteInjectorPlugin | `symbiote_injector_plugin.ts` | ✅ WORKING (after TRUE_SIGHT fix) | Synthesizes PointerEvents to `document.elementFromPoint` |
| StillnessMonitorPlugin | `stillness_monitor_plugin.ts` | ✅ WORKING (after TRUE_SIGHT fix) | Publishes `STILLNESS_DETECTED` after 3600 idle ticks |
| AudioEnginePlugin | `audio_engine_plugin.ts` | ✅ WORKING | Synthesized Cherry MX click via `AudioContext` on `COMMIT_POINTER` |
| KalmanFilter | `kalman_filter.ts` | ✅ WORKING | Kalman 1D smoother + 1-frame predictive lookahead |
| LayerManager | `layer_manager.ts` | ✅ WORKING | Z-stack topology, `pointer-events: none` enforcement |
| PluginSupervisor | `plugin_supervisor.ts` | ✅ WORKING | Plugin lifecycle (init/destroy/hot-swap) |
| IframeDeliveryAdapter | `iframe_delivery_adapter.ts` | ✅ WORKING | tldraw/Excalidraw iframe PointerEvent bridge |
| VisualizationPlugin | `visualization_plugin.ts` | ✅ WORKING (after PAL fix) | Hand skeleton dots + lines overlay |
| AudioContext unlock | `demo_2026-02-20.ts` `startBtn` | ✅ WORKING | Physical tap → `AudioContext.resume()` trusted gesture bootstrap |
| BabylonLandmarkPlugin | `babylon_landmark_plugin.ts` | ✅ WRITTEN, NOT WIRED | 21 colored spheres per hand, implements Plugin interface. **1 line to activate.** |

### 4.3 Kalman Smoothing Config (No MediaPipe Native Smoothing)

**CRITICAL FACT:** `@mediapipe/tasks-vision` HandLandmarker does **NOT** smooth landmarks. The legacy `@mediapipe/hands` package did (1 Euro Filter internally), but we use the current Tasks API which is pure ML inference — no temporal filter.

Our Kalman in `w3c_pointer_fabric.ts` is the **only** temporal smoother in the stack.

**Tuned defaults for 30fps phone:**
```typescript
smoothingQ: 0.05,   // Low — trust Kalman model; landmark noise is real
smoothingR: 10.0,   // High — landmarks jump ±5px/frame at 30fps
```

---

## 5. Omega v13 — The Potemkin Corruption (HONEST AUDIT)

### 5.1 TRUE_SIGHT Audit Summary

**Scope:** Full AST scan — 54 .ts files, all event bus channels, all import chains  
**Session:** f2b745f7d330aebe (PREY8 chain, react_token 9CB700)  
**Result:** 3 critical bugs fixed, 4 ghost event channels, 14+ orphan production files

### 5.2 Critical Bugs Found and Fixed

#### Bug 1: PAL Leak in `visualization_plugin.ts:111`
```typescript
// BEFORE (corrupt): reads raw window, bypasses PAL contract
const scale = (window as any).omegaOverscanScale || 1.0;

// AFTER (fixed): PAL-sourced overscan
const scale = this.context?.pal?.resolve<number>('OverscanScale') ?? 1.0;
```
**Impact:** Skeleton overlay ignored OVERSCAN_SCALE_CHANGE PAL events. Visual hand tracking would desync from the pointer on any overscan change.

#### Bug 2: `StillnessMonitorPlugin` Not Registered in Live Demo
**Before:** `GestureFSMPlugin` subscribed to `STILLNESS_DETECTED` but the publisher (`StillnessMonitorPlugin`) was never registered in `demo_2026-02-20.ts`. Stillness detection was **completely dead** in live demo.  
**After:** Registration line added. FSM idle timer now active.

#### Bug 3: `SymbioteInjectorPlugin` Not Registered in Live Demo
**Before:** `SymbioteInjectorPlugin` was only in the old `demo.ts`. The live `demo_2026-02-20.ts` never registered it. Real DOM `PointerEvent` dispatch to `document.elementFromPoint` (tldraw injection) was **completely dead** in the current bootstrap.  
**After:** Registration line added. WYSIWYG invariant now complete.

### 5.3 Ghost Event Channels (Documented, Not Bugs)

| Event | Status | Analysis |
|-------|--------|----------|
| `SETTINGS_TOGGLE` | Extension point | Subscribed in `shell.ts:444`, no publisher. Intentional external API hook. |
| `SETTINGS_PANEL_STATE` | Extension point | Published in `shell.ts:759`, no subscriber. Broadcast for future components. |
| `OVERSCAN_SCALE_CHANGE` | Static default | Handler ready; OverscanScale fixed at 1.0 until UI overscan slider built. |
| `RAW_HAND_DATA` | Test-only | Published in `babylon_w3c_pipeline.spec.ts`; not in MicrokernelEvents schema. |

### 5.4 Orphaned Production Files (14+)

These compile and pass specs but are **not in the live demo import chain** (`demo_2026-02-20.ts`):

| File | Category | Status | Priority |
|------|----------|--------|----------|
| `babylon_landmark_plugin.ts` | B1 feature | Done, not wired | NEXT (1 line) |
| `babylon_physics.ts` | B2 feature | Wrong interface, needs Plugin wrapping | v15 |
| `behavioral_predictive_layer.ts` | V14 deferred | GA deferred by operator | v15 |
| `video_throttle.ts` | V14 deferred | Resolution ladder targeting | v15 |
| `webrtc_udp_transport.ts` | V14 deferred | WebRTC explicitly deferred | v15+ |
| `overscan_canvas.ts` | Extension point | Overscan UI not built | Future |
| `temporal_rollup.ts` | Utility | Test-only, no production consumer | Future |
| `wood_grain_tuning.ts` | Utility | Tuning helper, no live wiring | Future |
| `highlander_mutex_adapter.ts` | Pattern | Never in any production import chain | Future |
| `biological_raycaster.ts` | Research | Spec only — exploratory | v15+ |
| `foveated_cropper.ts` | Research | Spec only; MediaPipe Tasks API handles FOV internally | v15+ |
| `schemas.ts` | Utility | Only `test_zod.ts` uses it | Low |
| `gesture_bridge.ts` | Type adapter | `GestureBridge` class in spec only | Low |
| `mediapipe_gesture.ts` | Type source | Only type imports, no class instantiated | Low |

### 5.5 Architectural Antipatterns (6 Lethal — Do Not Carry Into v15)

#### AP-1: Main-Thread GA Blocking (The Frame-Dropper)
- **Location:** `behavioral_predictive_layer.ts` → `evolve()` method
- **Crime:** Genetic Algorithm runs on main JavaScript thread. 50 genotypes × `simulatePrediction` = 20ms+ blocking = 120Hz pointer freezes, DOM lock, camera stutter.
- **v15 fix:** Web Workers. Main thread posts ring-buffer via `postMessage`. Worker evolves silently. Posts updated `Genotype` back only on better fitness.

#### AP-2: GC Churn in GA Hot Loop (The Micro-Stutter)
- **Location:** `simulatePrediction` in `behavioral_predictive_layer.ts`
- **Crime:** `predictions.push({x, y, z, timestamp})` inside hot GA fitness loop. Creates hundreds of short-lived objects per generation at 60Hz → V8 GC "stop the world" → 50-100ms freeze.
- **v15 fix:** Pre-allocated `Float32Array`. Never `.push()` inside hot loops.

#### AP-3: Ground Truth Paradox (Supervised vs. Unsupervised)
- **Location:** Tests use perfect sine wave as ground truth. Production has no ground truth — only noisy MediaPipe data.
- **Crime:** GA fitness function can't compute MSE in production because the "correct" signal doesn't exist.
- **v15 fix:** Shadow Tracker — run a heavily delayed Savitzky-Golay filter in background (~500ms lag). It represents the user's intended smooth path. Train the real-time GA to predict where the Shadow Tracker will be.

#### AP-4: MAP-Elites Mirage
- **Location:** `behavioral_predictive_layer.ts`
- **Crime:** Documentation claims MAP-Elites (Quality Diversity, 2D grid by behavioral axes). Code is a standard single-objective GA — top 50% by MSE, no grid, no behavioral descriptor mapping.
- **v15 fix:** Implement the MAP-Elites grid: evaluate each genotype, calculate behavioral descriptor (frequency/amplitude), map to 2D grid cell, only keep if fitness beats current cell occupant.

#### AP-5: Zombie Event Listeners (Memory Leak)
- **Location:** `audio_engine_plugin.ts`
- **Crime:** `this.context.eventBus.subscribe('STATE_CHANGE', this.onStateChange.bind(this))` — `.bind(this)` creates an anonymous reference that can never be unsubscribed. Hot-swap leaves dead listeners firing on destroyed audio contexts.
- **v15 fix:**
```typescript
private boundOnStateChange = this.onStateChange.bind(this);
// init(): subscribe(..., this.boundOnStateChange)
// destroy(): unsubscribe(..., this.boundOnStateChange)
```

#### AP-6: Untrusted Gesture Audio Trap
- **Location:** `bootstrap.ts` startBtn hack
- **Crime:** Browsers enforce autoplay policy: synthetic `PointerEvent` has `event.isTrusted === false` → `AudioContext` stays permanently muted in a gesture-only interface.
- **v15 fix:** Cannot bypass via code. The first interaction MUST be a physical screen tap (e.g., "Tap to Calibrate Camera" button). That single trusted gesture instantiates and `resume()`s the global `AudioContext`.

---

## 6. Omega v14 — Why It Stalled

**Goal:** Prove Omega v14 microkernel via correct-by-construction SDD with mutation score in the 80–99% Goldilocks zone.

**Failure mode — GRUDGE_016 (Green Lie):**
1. Built `src/microkernel.ts` with undocumented `dependencies` array + `untested-plugin` state
2. Added tests for this "untested" complexity → mutation score went to **100%**
3. 100% kill rate = every line of code is covered = the architecture has no genuine unknowns = **Green Lie**
4. Operator rule: "100% kill rate is instant fail, stop bypassing my architecture"

**Location:** `hfo_gen_89_hot_obsidian_forge/2_gold/projects/omega_v14_microkernel/`  
**Files:** `src/microkernel.ts`, `tests/microkernel.spec.ts`, `tests/microkernel.property.spec.ts`, `stryker.config.json`  
**Fix needed:** Remove tests for `untested-plugin` OR add genuinely untested complexity. Target: 80–99% Stryker score.

---

## 7. Omega v13 — ATDD Invariants (6 Gherkin Specs, Machine-Readable)

These are the 6 SBE invariants that MUST be enforced in v15. They prevent known failure modes from recurring.

### SPEC 1: PAL Viewport Binding (Anti-Drift)
```gherkin
Feature: PAL Viewport Binding
  Scenario: PAL resolves true CSS Viewport, not physical screen
    Given the bootstrapper demo_2026-02-20.ts registers ScreenWidth and ScreenHeight into the PAL
    When the source code of demo_2026-02-20.ts is statically analyzed
    Then it MUST NOT contain window.screen.width or window.screen.height
    And it MUST contain window.innerWidth and window.innerHeight
    And it MUST bind a resize event listener to dynamically update PAL dimensions
```

### SPEC 2: Z-Stack Event Permeability (Anti-Invisible Wall)
```gherkin
Feature: Z-Stack Event Permeability
  Scenario: UI layers default to pointer-events none
    Given the LayerManager initializes the Z-Stack
    When the default LAYER.SETTINGS descriptor is queried in layer_manager.ts
    Then its pointerEvents property MUST explicitly equal 'none'
```

### SPEC 3: Synthetic Pointer React Compatibility
```gherkin
Feature: Iframe Symbiote React Compatibility
  Scenario: Symbiote polyfills capture and maps button state
    Given the Symbiote Agent code in tldraw_layer.html
    When the source code is analyzed
    Then it MUST map eventInit.buttons > 0 to button: 0 (main click) to trigger ink
    And Element.prototype.setPointerCapture MUST be polyfilled globally to catch IDs >= 10000
    And Element.prototype.releasePointerCapture MUST be similarly polyfilled
```

### SPEC 4: GC Zero-Allocation Hot Loop (Anti-Meltdown)
```gherkin
Feature: Hot-Loop Memory Stability
  Scenario: W3CPointerFabric skips Zod validation in hot loops
    Given the W3CPointerFabric is processing POINTER_UPDATE events
    When the source code of w3c_pointer_fabric.ts is statically analyzed
    Then it MUST NOT import zod or PointerUpdateSchema
    And the onPointerUpdate and onPointerCoast methods MUST NOT contain .parse()
```

### SPEC 5: Orthogonal Intent FSM (Anti-Thrash)
```gherkin
Feature: Orthogonal Defense-in-Depth FSM
  Scenario: Strict State Routing (No Teleportation)
    Given the GestureFSM is in the IDLE state
    When it receives highly confident pointer_up gestures
    Then the FSM MUST remain in IDLE (IDLE to COMMIT is an illegal transition)

  Scenario: Independent Leaky Buckets (Anti-Thrash)
    Given the FSM is in COMMIT_POINTER
    When the FSM receives open_palm frames
    Then the internal READY bucket MUST fill
    And the IDLE bucket MUST NOT fill
    And returning to pointer_up MUST aggressively leak the opposing buckets
```

### SPEC 6: Babylon Physics Quarantine (Battery Survival)
```gherkin
Feature: Mobile-Safe Physics Scaling
  Scenario: Babylon physics quarantined from 2D launch bootstrapper
    Given the demo_2026-02-20.ts bootstrapper
    When the source code is analyzed
    Then it MUST NOT register or instantiate BabylonPhysicsPlugin
    And it MUST NOT call startBabylon()
    Because 3D Havok physics running concurrently with WebRTC cast melts mobile batteries
```

---

## 8. HFO Gen90 Hot Obsidian Forge — Current State

### Forge Structure
```
hfo_gen_90_hot_obsidian_forge/
├── 0_bronze/                       ← Working layer (all new work starts here)
│   ├── 0_projects/
│   │   └── HFO_OMEGA_v15/          ← v15 project (seeded from v13 source)
│   ├── 1_areas/
│   ├── 2_resources/                ← Scripts, tools, context bundles (THIS FILE)
│   └── 3_archives/
├── 1_silver/                       ← Human-reviewed / validated
├── 2_gold/
│   └── 2_resources/
│       └── hfo_gen90_ssot.sqlite   ← THE DATABASE (9,868 docs, ~9M words)
└── 3_hyper_fractal_obsidian/       ← Meta/architectural layer
```

### SSOT Database (as of 2026-02-21)
| Metric | Value |
|--------|-------|
| Total documents | 9,868 |
| Total stigmergy events | 17,700+ |
| Total words | ~9M |
| Source breakdown | memory (7,423), p4_payload (1,234), p3_payload (522), diataxis (428) |
| All medallions | bronze (trust nothing, validate everything) |

### What is Already in HFO_OMEGA_v15 Directory

The v15 project was seeded from v13 source. It contains:
- All v13 source `.ts` files (~55 files)
- All v13 test specs
- Build infrastructure (`jest.config.js`, `tsconfig.json`, `playwright.config.ts`, `stryker.config.json`)
- Analysis docs: architectural review, pareto blueprint, filtering pipeline, temporal manifest
- The v13 `OMEGA_V13_CONCAT_2026-02-20.md` concatenated source bundle

**Critical:** The v15 rewrite should NOT just fix the v13 bugs in-place. It should be a **clean-room rebuild** using the v13 source as a reference, following the architecture defined in File 2 (the Rewrite Charter).

---

## 9. The 3-Pillar Pareto-Optimal Architecture (v15 Target)

This is the architecture the operator approved. Three distributed pillars, 5 Core Pieces.

### Pillar 1: "Live on Smartphone" (Compute & Ergonomic Optimality)
> The phone is a dumb, ultra-fast optical nerve. It extracts biological intent and sends it over the network.

- **Foveated ROI Cropping:** Start at 480p to find the human. Once found, crop 256×256 bounding box around hand → feed only that into MediaPipe. Prevents thermal throttling.
- **Scale-Invariant Biological Raycasting:** Pinch threshold = (Thumb-Index distance) / (Palm Width). Anatomical ruler — invariant to hand size and distance from camera.

### Pillar 2: "Cast to Big Screen" (Latency & Compatibility Optimality)
> The 100-inch TV receives raw optical nerve data, runs heavy physics and filters, injects W3C events into sandboxed iframes.

- **WebRTC UDP DataChannel:** `ordered: false`, `maxRetransmits: 0`. TCP WebSockets freeze on dropped packets. UDP drops gracefully — stale cursor data is better than a frozen cursor.
- **W3C Level 3 Symbiote Injector:** Translates UDP math into local iframe coordinates → `IframeDeliveryAdapter` → synthesized `pointerdown`/`pointermove` with predictive lookahead arrays.

### Pillar 3: "Grow with User" (Privacy & Maturation Optimality)
> Personalization without biometric surveillance.

- **Wood Grain Tuning Profile:** All Kalman covariances, Havok spring constants, Schmitt Trigger thresholds serialized to JSON (`UserTuningProfile`). Privacy-by-Math: mathematically impossible to reverse-engineer to video. GDPR/COPPA compliant by construction.

---

## 10. Feature Decision Matrix (v13 → v15)

| Feature | v13 State | v15 Decision | Notes |
|---------|-----------|--------------|-------|
| Kalman smoother | ✅ Working | CARRY | Core temporal smoother, only one in stack |
| Anti-Midas FSM | ✅ Working | CARRY + STRENGTHEN | Add SCXML formal spec |
| W3C PointerFabric | ✅ Working | CARRY, NO ZOD IN HOT PATH | SPEC 4 enforces this |
| tldraw symbiote | ✅ Working | CARRY | SPEC 3: polyfill `setPointerCapture` |
| Audio Cherry MX | ✅ Working | CARRY with AP-6 fix | Must have physical tap bootstrap |
| Babylon dots (B1) | ✅ Written, NOT wired | WIRE IN v15 | 1 registration line |
| Babylon physics (B2) | ⚠️ Wrong interface | REWRITE with Plugin interface + velocity-drive | AP-1/AP-2 fix required |
| GA Behavioral Predictor | ⚠️ Blocks main thread | REWRITE in Web Worker | AP-1 fix |
| Shadow Tracker | ❌ Missing | BUILD in v15 | Required for AP-3 fix |
| WebRTC UDP | ❌ Stub | BUILD as Pillar 2 | v15 core deliverable |
| Foveated crop | ✅ Exists | WIRE to MediaPipe plugin | C4 from trade study |
| Video resolution ladder | ✅ Exists | WIRE to MediaPipe plugin | C3 from trade study |
| MAP-Elites GA | ❌ Mirage | REAL IMPLEMENTATION in v15 | AP-4 fix |
| GA Worker isolation | ⚠️ Path broken | FIX worker bundle path in v15 | C1 from trade study |
| Pre-alloc TypedArrays | ❌ Missing | IMPLEMENT in v15 | C2 from trade study, AP-2 fix |
| FABRIK IK (v14+) | ❌ Not built | v15 stretch goal | Wrist/finger chain |

---

## 11. Key Technical Facts for External AI

1. **MediaPipe Tasks API has NO built-in smoothing.** Our Kalman is the only temporal filter.
2. **tldraw needs `setPointerCapture` polyfill.** React internals crash on pointer IDs ≥ 10000 without it.
3. **`buttons > 0` → `button: 0` mapping required.** React's ink only fires on main-button events.
4. **AudioContext MUST be resumed on a trusted gesture.** `event.isTrusted === false` on synthetic pointer events → audio permanently muted.
5. **Babylon physics MUST NOT run in the 2D bootstrap.** Havok + WebRTC concurrently = mobile thermal throttle death.
6. **W3CPointerFabric hot path MUST NOT call `.parse()`** — Zod validation in a 60Hz loop causes GC churn.
7. **Z-Stack layers MUST default to `pointer-events: none`.** Otherwise invisible UI layers block camera control.
8. **PAL is the single source of truth for viewport geometry.** Never read `window.screen.*` directly.

---

*Generated: 2026-02-21 | Session: a028afc9b8bdb466 | PREY8 nonce: C560DF | HFO Gen90*
