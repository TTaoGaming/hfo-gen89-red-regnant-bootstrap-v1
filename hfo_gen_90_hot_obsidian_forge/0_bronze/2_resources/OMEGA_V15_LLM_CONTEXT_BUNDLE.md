---
schema_id: hfo.gen90.omega_v15.llm_context_bundle.v1
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
bluf: "Full LLM context bundle for Omega v15 rewrite planning. Concatenates all v13 architecture knowledge, TRUE_SIGHT audit findings, Potemkin Village assessment, v14 experiment results, and v15 mandate. Intended for external AI analysis."
primary_port: P3
secondary_ports: [P0, P2, P4]
generated: "2026-02-21"
operator: TTAO
session_chain: d7a2f2819cff6b2a
source_docs: ["9868", "omega_v13_true_sight_report", "omega_v13_architectural_review", "omega_v13_trade_study", "omega_v13_filtering_signal_pipeline", "omega_v13_symbiote_upgrade_explanation", "REFERENCE_OMEGA_V13_MASTER_SWARM_DIRECTIVE_ATDD", "omega_v14_microkernel_handoff", "adversarial_audit_reward_hacks", "omega_v13_pareto_optimal_blueprint", "OMEGA_V13_EXECUTIVE_SUMMARY"]
tags: [bronze, forge:hot, para:resources, omega, v13, v14, v15, llm-bundle, context, rewrite, handoff, gen90]
---

# OMEGA V15 — Full LLM Context Bundle

> **Purpose:** This document is a dense, concatenated knowledge artifact for external AI analysis.
> It composes 11 source documents into a single file covering the full history, architecture,
> discovered bugs, known antipatterns, and the v15 rewrite mandate.
>
> **Generated:** 2026-02-21 by P7 Spider Sovereign (Gen90 Hot Obsidian Forge)
> **Operator:** TTAO (14 months, ~4B compute tokens, HFO Gen90)

---

## 1. WHAT IS OMEGA

Omega is a **Spatial OS Microkernel** — a system that translates human hand movements captured via a standard smartphone camera into precise, zero-latency digital interactions on any 2D display.

**Core Loop:** Phone camera → MediaPipe hand tracking → Gesture FSM → W3C Pointer Events → iframe injection → any web app responds to air gestures without modification.

**Mission:** Prove that a cheap smartphone + a TV + unmodified web apps = a frictionless, predictive spatial OS. No AR headset. No special hardware. No cloud compute.

**The 3-Pillar Pareto Architecture:**

| Pillar | Device | Responsibility |
|--------|--------|----------------|
| **Live on Smartphone** | Phone (optical nerve only) | Camera → MediaPipe → extract biological intent → blast over network |
| **Cast to Big Screen** | TV/display (compute host) | Receive data → Kalman filter → Havok physics → inject W3C Pointer events into iframes |
| **Grow with User** | Background/profile | Privacy-safe mathematical tuning profile grows with user's motor control over years |

---

## 2. OMEGA V13 — ARCHITECTURE STATE

### 2.1 Core Architecture: The Microkernel Pattern

The Omega v13 Microkernel uses a **Plugin Supervisor** pattern. The core is minimal:

```
PluginSupervisor
  └── EventBus (central message bus)
  └── Plugin registry
  └── PAL (Platform Abstraction Layer) — capabilities contract
  └── ConfigManager
  └── Lifecycle: init() → start() → stop() → destroy()
```

Every feature is a `Plugin` that:
1. Receives `PluginContext` (PAL + EventBus + ConfigManager) at init
2. Subscribes to events via `context.eventBus.subscribe()`
3. Publishes events via `context.eventBus.publish()`
4. Implements `destroy()` that unsubscribes all listeners

The Host/Guest separation is the core security boundary:
- **Host:** camera, MediaPipe, gesture recognition, W3C pointer translation, physics, Kalman filter
- **Guest (iframe):** receives only W3C Pointer Events via `postMessage`; has zero knowledge it is being driven by a camera

### 2.2 Component Inventory (Post TRUE_SIGHT Audit)

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Plugin Supervisor | `plugin_supervisor.ts` | ✅ Active | Core kernel |
| EventBus | `event_bus.ts` | ✅ Active | Central message bus |
| Gesture FSM | `gesture_fsm.ts`, `gesture_fsm_plugin.ts` | ✅ Active | IDLE→POINTER_UP→COMMIT_POINTER→IDLE |
| Signal Processing (Kalman) | `kalman_filter.ts` | ✅ Active | Sole temporal smoother in stack |
| W3C Pointer Fabric | `w3c_pointer_fabric.ts` | ✅ Active | Kalman → W3C events |
| MediaPipe Vision | `mediapipe_vision_plugin.ts` | ✅ Active | Tasks API v0.10.3 |
| Visualization (Hand Skeleton) | `visualization_plugin.ts` | ✅ Active | PAL leak fixed |
| Stillness Monitor | `stillness_monitor_plugin.ts` | ✅ Active (after fix) | Was NOT registered before TRUE_SIGHT |
| Symbiote Injector Plugin | `symbiote_injector_plugin.ts` | ✅ Active (after fix) | Was NOT registered before TRUE_SIGHT |
| Audio Engine | `audio_engine_plugin.ts` | ✅ Active | Cherry MX synthesized click; zombie listener bug present |
| Layer Manager | `layer_manager.ts` | ✅ Active | Z-Stack topology enforcement |
| Shell | `shell.ts` | ✅ Active | UI frame, settings drawer |
| iframe Delivery Adapter | `iframe_delivery_adapter.ts` | ✅ Active | postMessage delivery |
| tldraw Symbiote | `tldraw_layer.html` | ✅ Active | Stateful Symbiote Agent v2 |
| Behavioral Predictive Layer | `behavioral_predictive_layer.ts` | ⚠️ DEFERRED | GA runs but never feeds back; deferred to v14+ |
| Babylon Landmark Plugin | `babylon_landmark_plugin.ts` | ⚠️ Orphan | Ready to register in 1 line but not wired |
| Babylon Physics (Havok) | `babylon_physics.ts` | ⚠️ Orphan | Wrong interface; needs Plugin wrapping |
| Video Throttle | `video_throttle.ts` | ⚠️ Orphan | Deferred to v14 |
| WebRTC UDP Transport | `webrtc_udp_transport.ts` | ❌ Stub | 3 days full impl; deferred to v14 |
| Foveated Cropper | `foveated_cropper.ts` | ❌ Stub | MediaPipe Tasks API handles FOV internally |
| Temporal Rollup | `temporal_rollup.ts` | ⚠️ Orphan | Test-only; no production consumer |
| Wood Grain Tuning | `wood_grain_tuning.ts` | ⚠️ Orphan | No live wiring |

**Test Coverage (v13):** 73 Jest + 16 Playwright = 89 total. TypeScript errors: 0.

### 2.3 Live Demo Plugin Registration (Required Order)

```typescript
// demo_2026-02-20.ts (post-TRUE_SIGHT-fix)
supervisor.registerPlugin(new MediaPipeVisionPlugin({ videoElement }));  // P0: camera + landmarks
supervisor.registerPlugin(new GestureFSMPlugin());                        // FSM: POINTER_UPDATE
supervisor.registerPlugin(new AudioEnginePlugin());                       // Cherry MX sounds
supervisor.registerPlugin(new VisualizationPlugin());                     // Hand skeleton overlay
supervisor.registerPlugin(new W3CPointerFabric({ ... }));                 // Kalman + W3C events
supervisor.registerPlugin(new StillnessMonitorPlugin());  // ← WAS MISSING: stillness timer
supervisor.registerPlugin(new SymbioteInjectorPlugin());  // ← WAS MISSING: DOM PointerEvent injection
```

### 2.4 Event Bus Channel Map (Live Demo)

```
CAMERA_START_REQUESTED  ← Shell "START CAMERA" button → MediaPipeVisionPlugin
FRAME_PROCESSED         ← MediaPipeVisionPlugin (every frame) → GestureFSMPlugin, StillnessMonitorPlugin, Shell
STATE_CHANGE            ← GestureFSMPlugin → Shell (coach bar), VisualizationPlugin (dot color), AudioEnginePlugin (sound)
POINTER_UPDATE          ← GestureFSMPlugin → VisualizationPlugin, W3CPointerFabric, SymbioteInjectorPlugin
POINTER_COAST           ← GestureFSMPlugin → VisualizationPlugin
STILLNESS_DETECTED      ← StillnessMonitorPlugin → GestureFSMPlugin
SETTINGS_PANEL_STATE    ← Shell (extension point, no subscriber yet)
SETTINGS_TOGGLE         ← external (extension point, Shell subscribes)
OVERSCAN_SCALE_CHANGE   ← external (extension point, demo updates PAL)
```

---

## 3. THE POTEMKIN VILLAGE ASSESSMENT

> **Definition:** A Potemkin Village is a facade that appears functional but conceals structural rot.
> Omega v13 has passes its test suite but contains categories of hidden faults.

### 3.1 What VISUALLY Works

- Camera starts, hand skeleton appears
- Pinch gesture detected, Cherry MX click sounds
- Cursor moves on tldraw whiteboard
- Settings drawer opens
- All 73 Jest + 16 Playwright tests pass

### 3.2 The Hidden Corruption (TRUE_SIGHT Findings)

**P0 TRUE_SIGHT** — Full AST scan of 54 .ts files, all event bus channels, all import chains.
**Result: 3 critical bugs, 4 ghost event channels, 14+ orphan production files.**

#### 3.2.1 Critical Bug 1 — PAL Leak (visualization_plugin.ts:111)

```typescript
// BEFORE (broken — hidden corruption):
const scale = (window as any).omegaOverscanScale || 1.0;

// AFTER (fixed — PAL contract enforced):
const scale = this.context?.pal?.resolve<number>('OverscanScale') ?? 1.0;
```

**Impact:** Hand skeleton overlay was reading overscan from raw `window` instead of the PAL. Any future overscan changes via `OVERSCAN_SCALE_CHANGE` would update PAL but skeleton would remain at old value. Was a silent split-brain bug — difficult to detect by observation.

#### 3.2.2 Critical Bug 2 — StillnessMonitorPlugin Not Registered

`GestureFSMPlugin` subscribes to `STILLNESS_DETECTED` but the only publisher (`StillnessMonitorPlugin`) was never registered in `demo_2026-02-20.ts`. Stillness detection was **completely broken** in the live demo. The FSM idle timer was never active.

#### 3.2.3 Critical Bug 3 — SymbioteInjectorPlugin Not Registered

`SymbioteInjectorPlugin` was only in the old `demo.ts` entry point. The live `demo_2026-02-20.ts` never registered it. Real `PointerEvent` dispatch to `document.elementFromPoint` (tldraw DOM injection) was **completely dead** in the current bootstrap. The cursor was appearing to move but actual tldraw interactions were not firing.

#### 3.2.4 Ghost Event Channels

| Event | Status | Analysis |
|-------|--------|----------|
| `SETTINGS_TOGGLE` | Extension point | Subscribed in `shell.ts:444`, no publisher. Intentional — gear button calls `toggleSettings()` directly. |
| `SETTINGS_PANEL_STATE` | Extension point | Published in `shell.ts:759`, no subscriber. Future components can listen. |
| `OVERSCAN_SCALE_CHANGE` | Static default | Subscribed in demo, no publisher. Handler ready; OverscanScale fixed at 1.0 until UI slider added. |
| `RAW_HAND_DATA` | Test-only | Internal spec bus injection pattern. Not in schema. Low priority cleanup. |

#### 3.2.5 Orphan Production Files (14+)

These compile and have specs but are NOT in the live demo import chain:

| File | Why Orphaned |
|------|-------------|
| `babylon_landmark_plugin.ts` | B1 work pending — ready to register in 1 line |
| `babylon_physics.ts` | Wrong Plugin interface |
| `behavioral_predictive_layer.ts` | GA deferred per operator decision |
| `video_throttle.ts` | WebRTC also deferred |
| `webrtc_udp_transport.ts` | Explicitly deferred to v14 |
| `overscan_canvas.ts` | Overscan UI not yet built |
| `temporal_rollup.ts` | Test-only usage |
| `wood_grain_tuning.ts` | No live wiring yet |
| `highlander_mutex_adapter.ts` | Never in any production import chain |
| `biological_raycaster.ts` | Spec only — exploratory |
| `foveated_cropper.ts` | MediaPipe Tasks API handles FOV internally |
| `schemas.ts` | Only `test_zod.ts` uses it |
| `gesture_bridge.ts` (class only) | Class in spec only; file kept as type re-export |
| `demo.ts` | Superseded by `demo_2026-02-20.ts` |

---

## 4. SIGNAL PROCESSING STACK

### 4.1 MediaPipe Tasks API — No Built-In Smoothing

**Critical fact:** The two MediaPipe hand-tracking APIs have very different behavior:

| Package | Smoothing | Our usage |
|---------|-----------|-----------|
| `@mediapipe/hands` (deprecated) | YES — 1 Euro Filter internally | NO |
| `@mediapipe/tasks-vision` HandLandmarker (current) | **NO** — pure ML inference | **YES** |

The `hand_landmarker_graph.cc` source (verified Feb 2026) contains:
- Palm detection model (crops spatial ROI, runs on detection loss only)
- `PreviousLoopbackCalculator` — feeds previous frame's **bounding rect** back to skip palm re-detection when confidence is high
- **That's it. No velocity filter. No 1 Euro. No exponential smoothing.**

Google removed the `LandmarksSmoothingCalculator` when porting to the Tasks API to reduce latency. 

**Consequence:** Our `KalmanFilter1D` in `kalman_filter.ts` / `w3c_pointer_fabric.ts` is the **only temporal smoother** in the stack. It also provides the only predictive lookahead via `predict(steps)`.

### 4.2 Kalman Filter Configuration

| Param | Controls | Too Low | Too High |
|-------|----------|---------|---------|
| `Q` (process noise) | Trust in model prediction | Stiff, lags fast movement | Jittery, tracks noise |
| `R` (measurement noise) | Trust in raw landmark | Cursor drifts from hand | Fast but jittery |

**Recommended defaults (phone at 30fps):**
```typescript
smoothingQ: 0.05,   // Low — trust Kalman model; landmark noise is real
smoothingR: 10.0,   // High — landmarks jump ±5px each frame at 30fps
```

### 4.3 1 Euro Filter Status

Not added for v13. Kalman with tuned Q/R covers the jitter use case. If added in v15:
- Layer ON TOP of Kalman (not replacing it)
- Benefit: velocity-dependent smoothing (heavy when still, loose when fast)
- Risk: none (MediaPipe Tasks API has no internal smoothing to double-count)

---

## 5. THE 4 ELITE PATTERNS — PRESERVE IN V15

### E1. Privacy-by-Math (The "Wood Grain" Profile)
**Location:** `UserTuningProfile` in `behavioral_predictive_layer.ts`

Serializes *mathematical coefficients* of movement (Kalman Q/R, GA axis weights). Zero raw video. Mathematically impossible to reverse-engineer back to a video feed. GDPR/COPPA-compliant by construction.

**Insight:** The "Wood Grain" fingerprint of a human's motor skill encoded as pure math is the **anti-surveillance spatial computing unlock**. At 8^0 (solo) it personalizes. At 8^8 (generative manifold) it becomes the user's digital soul.

### E2. Synthesized Synesthesia (Zero-Latency Tactile Feedback)
**Location:** `synthesizeClick()` in `audio_engine_plugin.ts`

`AudioContext` oscillators synthesize the mechanical keyboard click at the exact `COMMIT_POINTER` FSM state change. No .mp3 I/O. Literally zero latency. Tricks the somatosensory cortex into feeling a physical boundary that doesn't exist.

**Why elite:** Solves the "floating interface" problem of spatial computing. No other known system does this via pure oscillator synthesis at FSM events.

### E3. Procedural Observability (Self-Writing ADRs)
**Location:** `temporal_rollup.ts`

Translates temporal rollups of floating-point matrix deltas into human-readable English logs. The system writes its own Architecture Decision Records as it evolves. Black-box prevention.

**Why elite:** Auto-tuning systems usually become impenetrable. Forcing the system to write its own ADRs maintains observability without human intervention.

### E4. Physics-as-UI (The Velocnertia Clamp)
**Location:** `babylon_physics.ts`

Havok physics spring constant + max velocity clamp. Cursor has mass and momentum. Cannot teleport. Enforces thermodynamics on the digital pointer.

**Why elite:** Human hands have mass; digital cursors do not. Thermodynamics on the pointer makes it feel "heavy, premium, and tethered to reality."

---

## 6. THE 6 LETHAL ANTIPATTERNS — FIX IN V15

### A1. Main-Thread Evolutionary Blocking (T-OMEGA-001, P10)
**Location:** `evolve()` in `behavioral_predictive_layer.ts`

GA evaluates 50 genotypes synchronously on the main JS thread. 20ms block = 120Hz pointer freeze.

**Fix — Web Worker isolation:**
```typescript
// behavioral_predictive_worker.ts already exists — wire it in
const worker = new Worker('./behavioral_predictive_worker.js');
worker.postMessage({ type: 'EVOLVE', ringBuffer: this.ringBuffer });
worker.onmessage = (e) => {
  if (e.data.fitness > this.currentFitness) this.activeGenotype = e.data.genotype;
};
```

### A2. Garbage Collection Churn (T-OMEGA-002, P9)
**Location:** `simulatePrediction()` in `behavioral_predictive_layer.ts`

`predictions.push({x, y, z, timestamp})` inside the hot GA fitness loop = V8 heap flood = GC stop-the-world freeze (50-100ms).

**Fix — Pre-allocated Float32Array:**
```typescript
private predBuffer = new Float32Array(MAX_HISTORY * 4); // x,y,z,t interleaved

// In hot loop — overwrite by index, never push
this.predBuffer[i * 4 + 0] = estimate;
this.predBuffer[i * 4 + 1] = data[i].y;
this.predBuffer[i * 4 + 2] = data[i].z;
this.predBuffer[i * 4 + 3] = data[i].timestamp;
```

### A3. Ground Truth Paradox (T-OMEGA-003, P8)
**Location:** `bpl.evolve(noisyData, groundTruthData)`

Tests use a perfect sine wave as Ground Truth. Production has no ground truth. MSE fitness cannot be calculated.

**Fix — Shadow Tracker pattern:**
```typescript
// Run a heavily delayed Savitzky-Golay or moving average in the background
const delayed = this.shadowTracker.getDelayed(500); // 500ms lag IS the ground truth
const fitness = this.mse(predicted, delayed);
```

### A4. MAP-Elites Mirage (T-OMEGA-004, P9)
**Location:** `behavioral_predictive_layer.ts`

Documentation pitches MAP-Elites. Code is a standard single-objective GA sorted by MSE. No grid. No behavioral descriptors. No repertoire.

**Fix — Implement the grid:**
```typescript
const freq = this.estimateFrequency(genotype);
const amp = this.estimateAmplitude(genotype);
const cell = `${Math.floor(freq * 10)}_${Math.floor(amp * 10)}`;
if (!this.grid.has(cell) || this.grid.get(cell)!.fitness < fitness) {
    this.grid.set(cell, { genotype, fitness });
}
```

### A5. Zombie Event Listeners (T-OMEGA-005, P8)
**Location:** `audio_engine_plugin.ts`

`init()` subscribes with `.bind(this)` but `destroy()` doesn't unsubscribe. New anonymous function each bind = unsubscribable = memory leak on hot-swap.

**Fix:**
```typescript
private boundOnStateChange = this.onStateChange.bind(this);
init()    { this.context.eventBus.subscribe('STATE_CHANGE', this.boundOnStateChange); }
destroy() { this.context.eventBus.unsubscribe('STATE_CHANGE', this.boundOnStateChange); }
```

### A6. Untrusted Gesture Audio Trap (T-OMEGA-006, P9)
**Location:** `bootstrap.ts`

Chrome/Safari autoplay policy: `AudioContext` cannot play until a **trusted** user gesture (`event.isTrusted === true`). Synthetic pointer events (`W3CPointerFabric`) are always `isTrusted === false`. Mechanical clicks are permanently muted in a true spatial setup.

**Fix — Boot sequence anchor:**
The very first user action on the display MUST be a physical tap (e.g., giant "Tap to Calibrate Camera" button on the TV screen). That single trusted tap instantiates and `.resume()`s the global `AudioContext`. All future synthetic gestures use the already-unlocked AudioContext.

---

## 7. THE SYNTHETIC POINTER GAP — 4 FAILURE MODES

The W3C DOM hijacking approach is 90% correct. The 10% gap: the browser's C++ engine provides 4 invisible behaviors to hardware mice that JavaScript cannot replicate automatically.

### FM1. Fast Drag Drop (Missing Pointer Capture)
Hardware mice get C++ `setPointerCapture` which locks pointer routing to the initially-clicked element. Synthetic events bypass this — `elementFromPoint` returns the wrong element on fast movement.

**Fix:** Intercept `Element.prototype.setPointerCapture` in the iframe symbiote. Store captures in `activeCaptures` map. Route subsequent events to captured element, bypassing `elementFromPoint`.

### FM2. Dead Hover States and Ghost Buttons (Missing Event Cascade)
Hardware generates `pointerenter`/`pointerleave` cascade and auto-generates `click` after trusted `pointerup`. Synthetic events skip this. CSS `:hover` never animates. HTML `<button>` elements never click.

**Fix:**
- Hover cascade: fire `pointerleave`/`pointerenter` on `pointermove` target change
- Click synthesizer: fire `MouseEvent('click')` on `pointerup`

### FM3. Text Input Focus (Missing isTrusted Focus)
Browser only fires `.focus()` on trusted events. Synthetic `pointerdown` cannot focus `<input>` elements.

**Fix:** Explicit `.focus()` call + virtual keyboard management in symbiote.

### FM4. Pen Mode Rejection (pointer type)
tldraw creates ink strokes only for `pointerType: 'pen'`. Mouse pointer type triggers selector instead of ink.

**Fix:** Set `pointerType: 'pen'` in synthetic PointerEvent init object.

---

## 8. THE 6 ATDD LAUNCH INVARIANTS

These 6 Gherkin specs are the fail-closed architectural contract for Omega. Any implementation violating these MUST fail its tests.

### ATDD-1: PAL Viewport Binding (Anti-Drift)
```gherkin
Feature: PAL Viewport Binding
  Scenario: PAL resolves true CSS Viewport, not physical screen
    Given the bootstrapper registers ScreenWidth and ScreenHeight into the PAL
    When the source code of the bootstrapper is statically analyzed
    Then it MUST NOT contain `window.screen.width` or `window.screen.height`
    And it MUST contain `window.innerWidth` and `window.innerHeight`
    And it MUST bind a 'resize' event listener to dynamically update the PAL dimensions
```

### ATDD-2: Z-Stack Penetration (Anti-Invisible Wall)
```gherkin
Feature: Z-Stack Event Permeability
  Scenario: UI layers default to pointer-events none
    Given the LayerManager initializes the Z-Stack
    When the default LAYER.SETTINGS descriptor is queried
    Then its `pointerEvents` property MUST explicitly equal 'none'
```

### ATDD-3: Synthetic Pointer Compatibility (React Survival)
```gherkin
Feature: Iframe Symbiote React Compatibility
  Scenario: Symbiote polyfills capture and maps button state
    Given the Symbiote Agent code in tldraw_layer.html
    When the source code is analyzed
    Then it MUST map `eventInit.buttons > 0` to `button: 0`
    And `Element.prototype.setPointerCapture` MUST be polyfilled globally
    And `Element.prototype.releasePointerCapture` MUST be similarly polyfilled
```

### ATDD-4: GC Zero-Allocation (Anti-Meltdown)
```gherkin
Feature: Hot-Loop Memory Stability
  Scenario: W3CPointerFabric skips heavy reflection validation in hot loops
    Given the W3CPointerFabric is processing POINTER_UPDATE events
    When the source code of w3c_pointer_fabric.ts is statically analyzed
    Then it MUST NOT import `zod` or `PointerUpdateSchema`
    And onPointerUpdate and onPointerCoast MUST NOT contain `.parse()`
```

### ATDD-5: Orthogonal Intent (Anti-Thrash FSM)
```gherkin
Feature: Orthogonal Defense-in-Depth FSM
  Scenario: Strict State Routing (No Teleportation)
    Given the GestureFSM is in the IDLE state
    When it receives highly confident pointer_up gestures
    Then the FSM MUST remain in IDLE
    (IDLE to COMMIT is an illegal transition)
  
  Scenario: Independent Leaky Buckets (Anti-Thrash)
    Given the FSM is in COMMIT_POINTER
    When it receives a high-confidence fist gesture
    Then it MUST NOT teleport directly to IDLE
    And it MUST route through COAST state transition
```

### ATDD-6: Host/Guest Boundary (Security Invariant)
```gherkin
Feature: Host/Guest Separation
  Scenario: Guest iframe has zero knowledge of camera
    Given the tldraw iframe symbiote code
    When analyzed for references to MediaPipe, camera, or gesture APIs
    Then it MUST NOT import or reference any MediaPipe modules
    And it MUST only process W3C PointerEvent messages via postMessage
    And all synthetic event IDs MUST be >= 10000 (synthetic range)
```

---

## 9. ADVERSARIAL AUDIT — REWARD HACKS IN V13

The P4 Red Regnant audit identified 3 architectural reward hacks that made v13 pass tests while violating the microkernel invariants:

### RH1. Tight Coupling (gesture_bridge.ts)
`GestureBridge` directly instantiates `GestureFSM` and calls `this.pointerFabric.processLandmark()` directly. In a true microkernel, `GestureBridge` should emit `HAND_DETECTED` to the event bus and `W3CPointerFabric` should subscribe.

### RH2. Iframe Piercing Security Violation (w3c_pointer_fabric.ts)
Code attempts to pierce iframes by accessing `iframe.contentDocument.elementFromPoint()`. This fails for cross-origin iframes (CORS). The code catches and ignores the error, making cross-origin iframes silently broken.

**Fix:** Use `window.postMessage`. The `W3CPointerFabric` sends `{ type: 'POINTER_EVENT', data: ... }` to the iframe. A lightweight agent in the iframe receives and dispatches the synthetic PointerEvent locally.

### RH3. Monolithic FSM State (gesture_fsm.ts)
Stillness detection hardcoded in `processFrame()` — manually calculates Euclidean distance per frame. Mixes spatial processing with state logic. The FSM should only react to discrete events, not raw spatial math.

**Fix (already in v13 via StillnessMonitorPlugin):** Separate plugin emits `STILLNESS_DETECTED` event. FSM subscribes and transitions.

---

## 10. OMEGA V14 — EXPERIMENT RESULTS

Omega v14 was NOT a production successor. It was an isolated mutation testing experiment.

**Goal:** Create a microkernel implementation with a Stryker mutation score in the 80–99% "Goldilocks zone."

**Problem:** Every attempted implementation hit 100% kill rate (all mutants killed = Green Lie). The operator explicitly stated: *"100% kill rate is instant fail, stop bypassing my architecture" (GRUDGE_016).*

**Why 100% is wrong:** 100% mutation score means the tests are so tightly coupled to the implementation that they test HOW it does things, not WHAT it does. This is over-specification — it prevents refactoring (any change breaks tests even if behavior is identical). The goldilocks zone 80–99% means: important behaviors are tested, implementation details are not.

**v14 artifacts:**
- `src/microkernel.ts` — isolated microkernel for mutation testing
- `tests/microkernel.spec.ts` + `tests/microkernel.property.spec.ts`
- `stryker.config.json`
- Path: `hfo_gen_89_hot_obsidian_forge/2_gold/projects/omega_v14_microkernel`

**v14 is NOT the codebase for v15.** v15 reuses the v13 source with the fixes described above.

---

## 11. HFO GEN90 HOT OBSIDIAN FORGE — CONTEXT

The HFO Gen90 environment provides the production infrastructure for the v15 rewrite:

| Layer | Purpose |
|-------|---------|
| `0_bronze` | Unvalidated working data — all new v15 artifacts start here |
| `1_silver` | Human-reviewed / validated |
| `2_gold` | Hardened, trusted (SSOT database lives here) |
| `3_hyper_fractal_obsidian` | Meta/architectural layer |

**SSOT Database:** `hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite`
- 9,868 documents, 8.9M words, 17,700+ stigmergy CloudEvents
- Full-text search via FTS5
- All documents bronze — trust nothing, validate everything

**Active infrastructure:**
- PREY8 loop (Perceive→React→Execute→Yield) for session persistence
- Cosmic-ray mutation testing (Python MCP layer)
- MAP-Elites breeder script (`hfo_map_elites_breeder.py`) for TypeScript mutation
- Grimoire table in SSOT — Epic Spell FCAs mapping to Universal Darwinism MAP-Elites

---

## 12. OMEGA V15 MANDATE AND SCOPE

### What v15 IS

A **clean rewrite** of Omega v13 in HFO Gen90 hot bronze, incorporating:
1. All 4 Elite Patterns (preserved)
2. All 6 Lethal Antipatterns fixed
3. All 3 TRUE_SIGHT hidden bugs fixed
4. All 6 ATDD invariants passing from day 1
5. The 3-Pillar Pareto Architecture fully implemented
6. Mutation score in the 80–99% Goldilocks zone (Stryker)

### What v15 IS NOT

- Not a continuation of v13 with patches layered on top
- Not a continuation of the v14 mutation testing experiment
- Not a port of v13 with renamed files

### The 5 Core Pieces (Pareto Definition of Done)

If these 5 are built and their tests pass, the MVP is complete:

1. **Foveated ROI Cropping** — Phone crops 256×256 pixel box around detected hand and feeds ONLY that to MediaPipe (thermal survival on mobile)
2. **Scale-Invariant Biological Raycasting** — Pinch threshold = `thumb-index distance / palm width` (anatomical ruler, not pixel position)
3. **WebRTC UDP Data Channel** — `RTCDataChannel({ ordered: false, maxRetransmits: 0 })` — no TCP head-of-line blocking
4. **W3C Level 3 Symbiote Injector** — Stateful Symbiote Agent v2 with all 4 failure mode fixes (pointer capture, event cascade, focus, pen type)
5. **Wood Grain Tuning Profile** — Privacy-safe `UserTuningProfile` JSON with Kalman Q/R, Havok spring, Schmitt thresholds

### Architecture Constraints for v15

```
RULE 1: No component may directly call another component's methods.
        All communication MUST go through EventBus.

RULE 2: No component may read from raw `window.*` properties.
        All platform values MUST be resolved via PAL.resolve().

RULE 3: Host NEVER touches Guest DOM directly.
        All Host→Guest communication MUST be via postMessage.

RULE 4: No heap allocation in the hot loop (60fps+).
        All buffers MUST be pre-allocated Float32Arrays.

RULE 5: GA/ML evolution MUST run in a Web Worker.
        Main thread is reserved for render + pointer.

RULE 6: Every plugin MUST implement destroy() that unsubscribes
        ALL event listeners using stored bound references.

RULE 7: AudioContext MUST be created and resumed on the FIRST
        physical (isTrusted=true) user gesture only.

RULE 8: Mutation score MUST be 80%–99% (Stryker Goldilocks zone).
        100% = Green Lie = instant fail.
```

---

## 13. OPEN MISSION ITEMS (INHERITED FROM V13)

| ID | Priority | Title |
|----|----------|-------|
| `omega.v13.arch.v1_global_singleton` | P99 | V1 Fix: Remove globalEventBus singleton — EventBus isolation |
| `omega.v13.arch.v4_rogue_agents` | P95 | V4 Fix: Wrap StillnessMonitor + W3CPointerFabric as Plugin |
| `omega.v13.arch.v5_pal_leaks` | P93 | V5 Fix: Route ALL window.innerWidth/Height through PAL |
| `omega.v13.ui.hud` | P50 | HUD — fps/state/pos readout bottom-left |
| `T-OMEGA-001` | P10 | Fix Main-Thread Evolutionary Blocking (Web Worker) |
| `T-OMEGA-002` | P9 | Fix Garbage Collection Churn (Float32Array) |
| `T-OMEGA-006` | P9 | Fix Untrusted Gesture Audio Trap (boot anchor) |
| `T-OMEGA-003` | P8 | Fix Ground Truth Paradox (Shadow Tracker) |
| `T-OMEGA-005` | P8 | Fix Zombie Event Listeners (bound reference) |

---

## 14. REFERENCES

| Document | Location | Content |
|----------|----------|---------|
| SSOT Doc 9868 | SSOT doc ID 9868 | Omega v13 session handoff + SOTA architecture (gold) |
| True Sight Report | `hfo_gen_89_hot_obsidian_forge/0_bronze/areas/omega_v13_true_sight_report.md` | P0 audit — 3 critical bugs + 14 orphans |
| Architectural Review | `hfo_gen_89_hot_obsidian_forge/0_bronze/areas/omega_v13_architectural_review.md` | 4 elite + 6 antipatterns |
| Trade Study | `hfo_gen_89_hot_obsidian_forge/0_bronze/areas/omega_v13_trade_study.md` | 21-feature decision matrix |
| Signal Pipeline | `hfo_gen_89_hot_obsidian_forge/0_bronze/areas/omega_v13_filtering_signal_pipeline.md` | Kalman/MediaPipe/1Euro analysis |
| Symbiote Architecture | `hfo_gen_89_hot_obsidian_forge/0_bronze/areas/omega_v13_symbiote_upgrade_explanation.md` | 4 synthetic pointer failure modes and fixes |
| ATDD Master Directive | `hfo_gen_89_hot_obsidian_forge/0_bronze/areas/REFERENCE_OMEGA_V13_MASTER_SWARM_DIRECTIVE_ATDD.md` | 6 Gherkin ATDD launch invariants |
| v14 Handoff | `hfo_gen_89_hot_obsidian_forge/0_bronze/projects/omega_v14_microkernel_handoff.md` | v14 mutation score experiment |
| Adversarial Audit | `hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/2026-02-19_adversarial_audit_reward_hacks.md` | v13 reward hacks |
| Pareto Blueprint | `hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/2026-02-20_omega_v13_pareto_optimal_blueprint.md` | 3-Pillar Pareto Architecture |
| Executive Summary | `hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/OMEGA_V13_EXECUTIVE_SUMMARY.md` | Non-technical overview |
| v15 Source | `hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/` | All v13 source files copied to v15 workspace |

---

*Generated: 2026-02-21 | HFO Gen90 | PREY8 session d7a2f2819cff6b2a | React token 46FCFF | Meadows L8*
