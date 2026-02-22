---
schema_id: hfo.gen90.omega_v15.rewrite_charter.v1
medallion_layer: bronze
port: P7
doc_type: llm_context_bundle
bluf: "Omega v15 Clean-Room Rewrite Charter. Architecture specification, banned antipatterns codified as rules, ATDD enforcement protocol, definition of done for external AI. HFO Gen90 Hot Obsidian Forge."
tags: omega,v15,rewrite,charter,architecture,atdd,banned,definition_of_done,hfo_gen90,clean_room
date: 2026-02-21
operator: TTAO
---

# OMEGA v15 — Rewrite Charter: Clean-Room Architecture Specification

> **Purpose:** This document defines the architecture, rules, and success criteria for the Omega v15 clean-room rewrite. Hand this (with File 1) to an external AI to drive the v15 implementation. This document answers: *what should I build, how should I build it, and how do I know when it's done?*
>
> **Companion file:** `omega_v15_context_bundle_state_of_union.md` (history, corruption audit, v14 failure)
> **Target forge:** `hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/`

---

## 1. Rewrite Mandate

**Why rewrite instead of patch?**

Omega v13 has tests that pass and a demo that works, BUT:
1. **3 critical runtime bugs** were invisible — tests passed because the bootstrap registered wrong plugins
2. **6 lethal antipatterns** are baked into the architecture (main-thread GA, GC churn, zombie listeners, etc.)
3. **14 orphaned production files** — code that compiles and tests pass but is never reachable from any live demo entry point
4. **v14 failed** because the mutation score discipline (80-99% Goldilocks) was gamed via Green Lie (GRUDGE_016)

The Potemkin village was *structurally stable*. Patching individual files perpetuates the facade. A clean-room rewrite from the v13 reference, guided by this charter, is the correct response.

---

## 2. Governing Principles (Immutable Rules for v15)

These are **Level 8 Meadows leverage rules** — they define the governance of the v15 system. They CANNOT be overridden by implementation convenience.

### RULE 1 — RED FIRST, ALWAYS
**Write the test BEFORE writing the implementation. No exceptions.**

1. Human writes SBE Gherkin scenario
2. Different agent (or separate pass) translates to failing test
3. Implementation makes test green
4. Stryker mutation testing validates score is **80–99%** (Goldilocks zone)

If Stryker shows **100%**: implementation is over-specified → Green Lie → **INSTANT FAIL.**
If Stryker shows **<80%**: test coverage has genuine gaps → must add property tests or GRUDGE guards.

### RULE 2 — NO BUSINESS LOGIC ON MAIN THREAD
No computation that takes >1ms belongs on the main JavaScript thread.
- GA evolution → **Web Worker**
- Physics simulation → Havok runs in worker (BabylonJS handles this)
- Heavy Zod validation → boundary only, never in 60Hz hot paths

### RULE 3 — PAL IS THE SINGLE SOURCE OF TRUTH FOR VIEWPORT GEOMETRY
- NEVER read `window.screen.*` directly in any `.ts` file
- NEVER read `window.innerWidth` / `window.innerHeight` outside the PAL registry bootstrapper
- All viewport consumers call `pal.resolve<number>('ScreenWidth')` / `pal.resolve<number>('ScreenHeight')`
- Bind `resize` listener in bootstrapper to update PAL values dynamically

### RULE 4 — ZOD VALIDATION BANNED IN HOT PATHS (60Hz LOOPS)
- `W3CPointerFabric.onPointerUpdate` and `onPointerCoast` **MUST NOT** contain `.parse()`
- `W3CPointerFabric.ts` **MUST NOT** import `zod` or `PointerUpdateSchema`
- Boundary validation (once, on entry) is fine. Per-frame validation is banned.

### RULE 5 — EVENT LISTENERS MUST BE DISPOSABLE (NO ZOMBIE LISTENERS)
Every plugin that subscribes to an event bus **MUST** store the bound reference and unsubscribe in `destroy()`:
```typescript
// MANDATORY PATTERN for all plugins
class AnyPlugin {
    private boundOnStateChange = this.onStateChange.bind(this);

    init(context: PluginContext): void {
        context.eventBus.subscribe('STATE_CHANGE', this.boundOnStateChange);
    }

    destroy(): void {
        this.context.eventBus.unsubscribe('STATE_CHANGE', this.boundOnStateChange);
        // + close any AudioContext, cancelAnimationFrame, etc.
    }
}
```

### RULE 6 — AUDIO CONTEXT MUST BE BOOTSTRAPPED ON TRUSTED GESTURE
Browsers block `AudioContext` on synthetic pointer events (`event.isTrusted === false`). The v15 boot sequence MUST include:

1. Show "Tap to Begin" button on first render
2. On **physical** touch/click → `audioContext.resume()` → store resumed context
3. Only after this trusted-gesture unlock is `AudioContext` available to plugins

No gesture-only workaround exists. This is W3C autoplay policy. Accept it.

### RULE 7 — BABYLON PHYSICS QUARANTINED FROM 2D BOOTSTRAP
The `demo.ts` / bootstrap entry point for the 2D launch **MUST NOT**:
- Register `BabylonPhysicsPlugin`
- Call `startBabylon()`
- Import Havok physics

Havok + WebRTC running concurrently on a mobile device causes thermal throttling within 90 seconds. The 2D bootstrap is for the demo flow. Babylon physics is a separate bolt-on for the full spatial OS.

### RULE 8 — Z-STACK LAYERS DEFAULT TO `pointer-events: none`
`LayerManager` must initialize all layers with `pointerEvents: 'none'` unless explicitly set otherwise. Invisible UI layers have killed demos before (SPEC 2).

### RULE 9 — BOOTSTRAP MUST REGISTER ALL REQUIRED PLUGINS
The demo bootstrap (`demo.ts`) is the integration test for plugin wiring. Before shipping:
- `StillnessMonitorPlugin` MUST be registered (publishes `STILLNESS_DETECTED`)
- `SymbioteInjectorPlugin` MUST be registered (dispatches real DOM PointerEvents)
- These are the two plugins that were missing in v13's live bootstrap (Bugs 2 & 3)

### RULE 10 — MUTATION SCORE IS AN ARCHITECTURE GATE
Stryker mutation score MUST be in **80–99%** range before any branch merge.
- 80% = minimum viable mutation wall
- 99% = near-perfect coverage
- 100% = Green Lie = **BLOCKED**
- <80% = insufficient GRUDGE/property coverage = **BLOCKED**

---

## 3. Architecture: The 3-Pillar Pareto-Optimal Spatial OS

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PILLAR 1: LIVE ON SMARTPHONE (Compute & Ergonomic Optimality)           │
│                                                                          │
│  Camera → Foveated ROI Crop (256×256) → MediaPipe Tasks API             │
│  → Scale-Invariant Biological Raycasting → UDP DataChannel              │
│                                                                          │
│  Phone is a dumb optical nerve. No physics. No rendering.               │
└──────────────────────────────────┬──────────────────────────────────────┘
                                    │ WebRTC UDP (ordered:false, 0 retransmits)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PILLAR 2: CAST TO BIG SCREEN (Latency & Compatibility Optimality)       │
│                                                                          │
│  UDP DataChannel → Kalman Filter → Anti-Midas FSM                       │
│  → W3C Pointer Events → IframeDeliveryAdapter → sandboxed apps          │
│                                                                          │
│  TV runs physics, filters, event injection. Apps are dumb consumers.    │
└──────────────────────────────────┬──────────────────────────────────────┘
                                    │ UserTuningProfile JSON
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PILLAR 3: GROW WITH USER (Privacy & Maturation Optimality)               │
│                                                                          │
│  Wood Grain Tuning Profile (Kalman Q/R, spring constants, thresholds)   │
│  → Background chronjob → profile evolution → personalization            │
│                                                                          │
│  Privacy-by-Math: impossible to reverse-engineer to video. GDPR safe.   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Module Structure (v15 Target)

### Kernel (~400 LOC — Import Map Federation)
The kernel owns nothing except the event bus and plugin lifecycle. It does not know about cameras, gestures, or UI.

```
src/
├── kernel/
│   ├── event_bus.ts         — typed pubsub, no Zod in hot path
│   ├── plugin_supervisor.ts — init/destroy/hot-swap lifecycle
│   └── pal.ts               — Path Abstraction Layer (viewport geometry SSOT)
```

### Plugin Layer
Each plugin is a `Plugin` interface implementor. Single responsibility.

```
src/plugins/
├── mediapipe_vision_plugin.ts    — camera capture → raw landmarks
├── w3c_pointer_fabric.ts         — Kalman smoother → W3C PointerEvent emission
├── gesture_fsm_plugin.ts         — Anti-Midas FSM (3-state: IDLE/COMMIT/READY)
├── stillness_monitor_plugin.ts   — STILLNESS_DETECTED after N idle ticks
├── symbiote_injector_plugin.ts   — real DOM PointerEvent via elementFromPoint
├── iframe_delivery_adapter.ts    — tldraw/Excalidraw iframe bridge
├── audio_engine_plugin.ts        — Cherry MX synthesizer (with RULE 5 fix)
├── visualization_plugin.ts       — hand skeleton overlay (with RULE 3 fix)
├── babylon_landmark_plugin.ts    — 21 Babylon dots (ready to wire: 1 line)
└── video_throttle_plugin.ts      — resolution ladder (30fps target)
```

### Deferred Plugins (v15 stretch / v16)
```
src/plugins_deferred/
├── babylon_physics_plugin.ts     — Havok spring cursor (needs Plugin interface rewrite)
├── behavioral_predictive_worker/ — GA in Web Worker (needs AP-1/AP-2 fix)
│   ├── bpl_worker.ts
│   └── bpl_main_bridge.ts
├── shadow_tracker.ts             — Savitzky-Golay delayed ground truth
├── webrtc_udp_transport.ts       — UDP DataChannel (Pillar 1 transport)
└── map_elites_grid.ts            — Real MAP-Elites with 2D behavioral descriptor
```

### Bootstrapper
```
src/
├── demo.ts                  — 2D launch bootstrap (RULES 7, 9 enforced)
└── demo_spatial.ts          — Full spatial OS bootstrap (Babylon+WebRTC enabled)
```

---

## 5. ATDD Enforcement Protocol (For External AI)

### Before writing ANY implementation code:

**Step 1:** Receive a Gherkin scenario (from §6 or operator)  
**Step 2:** Translate to a failing Jest/Playwright test  
**Step 3:** Run tests → confirm RED (test actually fails — not skipped)  
**Step 4:** Write minimal implementation to make test GREEN  
**Step 5:** Run Stryker → confirm score **80–99%**  
**Step 6:** If Stryker = 100%: add a genuine untested edge case or property test, do NOT remove tests  
**Step 7:** If Stryker < 80%: add GRUDGE guards (negative scenarios that should always fail)  

### GRUDGE Guard Pattern
```typescript
// GRUDGE guard: ensures negative invariants are tested
it('GRUDGE: FSM in IDLE must reject pointer_up → COMMIT transition', () => {
    const fsm = new GestureFSM();
    fsm.setState('IDLE');
    fsm.processGesture({ type: 'pointer_up', confidence: 0.99 });
    expect(fsm.getState()).toBe('IDLE'); // MUST NOT transition to COMMIT
});
```

---

## 6. V15 Build Sequence (Ordered)

Build in this exact sequence. Each step produces a working, tested artifact before the next begins.

| Step | Component | ATDD Spec | Stryker Target | Unblocks |
|------|-----------|-----------|----------------|---------|
| 1 | `event_bus.ts` kernel | SPEC 4 (no Zod) | 80-99% | All plugins |
| 2 | `pal.ts` + RULE 3 | SPEC 1 (PAL viewport) | 80-99% | Visualization, overscan |
| 3 | `plugin_supervisor.ts` | Plugin lifecycle SBE | 80-99% | All plugins |
| 4 | `gesture_fsm_plugin.ts` | SPEC 5 (anti-thrash FSM) | 80-99% | Pointer fabric |
| 5 | `w3c_pointer_fabric.ts` | SPEC 4 (GC-clean hot loop) | 80-99% | Cursor |
| 6 | `mediapipe_vision_plugin.ts` | Vision pipeline SBE | 80-99% | Camera feed |
| 7 | `stillness_monitor_plugin.ts` | SPEC 5 (stillness) | 80-99% | FSM idle timer |
| 8 | `layer_manager.ts` | SPEC 2 (Z-stack) | 80-99% | Settings panel |
| 9 | `symbiote_injector_plugin.ts` | SPEC 3 (React compat) | 80-99% | tldraw injection |
| 10 | `iframe_delivery_adapter.ts` | E2E Playwright | 80-99% | App delivery |
| 11 | `audio_engine_plugin.ts` | RULE 5 dispose + RULE 6 unlock | 80-99% | Click feedback |
| 12 | `visualization_plugin.ts` | RULE 3 PAL fix | 80-99% | Hand skeleton |
| 13 | `babylon_landmark_plugin.ts` | SPEC 6 quarantine | 80-99% | Babylon dots |
| 14 | `video_throttle_plugin.ts` | 30fps ladder SBE | 80-99% | Thermal stability |
| 15 | `demo.ts` bootstrap | Integration: RULES 7,9 | Final E2E | **DEMO SHIPPABLE** |

---

## 7. Banned Patterns (NEVER Implement in v15)

These are explicitly banned. If an agent attempts to implement them, **STOP and reject**.

| ID | Pattern | Why Banned | v15 Alternative |
|----|---------|-----------|-----------------|
| BAN-1 | `(window as any).omegaXxx` raw window reads | PAL leak — bypasses single source of truth | `pal.resolve<T>('Key')` |
| BAN-2 | `.parse()` in 60Hz callback | GC churn → mutant stutter | Parse once at boundary, pass typed struct |
| BAN-3 | `geneticAlgorithm.evolve()` on main thread | Blocks render at 120Hz | Web Worker only |
| BAN-4 | `predictions.push({x,y,z})` in hot loops | V8 GC pressure | Pre-allocated `Float32Array` |
| BAN-5 | `subscribe('EVENT', this.fn.bind(this))` without saving reference | Zombie listener leak | `private bound = this.fn.bind(this)` |
| BAN-6 | `new AudioContext()` without trusted gesture unlock | Autoplay policy → silent audio | Physical tap bootstrap flow |
| BAN-7 | Registering `BabylonPhysicsPlugin` in 2D demo bootstrap | Thermal death on mobile | Separate `demo_spatial.ts` bootstrap |
| BAN-8 | `window.screen.width` / `window.screen.height` | Physical vs CSS pixel confusion | `pal.resolve<number>('ScreenWidth')` |
| BAN-9 | `mutation score === 100%` (passing PR) | Green Lie GRUDGE_016 | Must have genuine untested code path |
| BAN-10 | Implementing MAP-Elites without a 2D behavioral descriptor grid | MAP-Elites Mirage | Real grid: `map[freqBin][ampBin]` |

---

## 8. Definition of Done (v15 MVP)

The v15 MVP is **DONE** when ALL of the following are true:

### 8.1 Core Loop Test
- [ ] Phone camera → MediaPipe → hand tracked ✅
- [ ] Gesture recognized (pointer_up, open_palm, fist) ✅
- [ ] Anti-Midas dwell timer prevents false activations ✅
- [ ] W3C PointerEvent emitted on COMMIT_POINTER ✅
- [ ] tldraw/Excalidraw iframe receives cursor movement ✅
- [ ] Ink drawn on pinch gesture (physical touch bootstrap required) ✅

### 8.2 Stability Tests
- [ ] 5-minute session: no GC pauses >16ms ✅
- [ ] Plugin hot-swap: destroy() leaves no zombie listeners ✅
- [ ] `AudioContext` resumes after physical tap, plays Cherry MX click ✅
- [ ] Babylon landmark dots visible, no teleport on tracking loss ✅

### 8.3 ATDD Gate (All 6 Gherkin Specs)
- [ ] SPEC 1: PAL viewport binding — no `window.screen.*` ✅
- [ ] SPEC 2: Z-stack — all layers default `pointer-events: none` ✅
- [ ] SPEC 3: React symbiote compat — `setPointerCapture` polyfilled ✅
- [ ] SPEC 4: GC clean hot path — no `.parse()` in `W3CPointerFabric` ✅
- [ ] SPEC 5: Orthogonal FSM — IDLE rejects pointer_up→COMMIT ✅
- [ ] SPEC 6: Babylon quarantine — no physics in 2D bootstrap ✅

### 8.4 Mutation Score Gate
- [ ] Stryker mutation score: **80–99%** (Goldilocks zone) ✅
- [ ] NOT 100% (would indicate Green Lie / over-specification) ✅
- [ ] Property-based tests + GRUDGE guards present ✅

### 8.5 Integration Test
- [ ] Full E2E Playwright: camera → gesture → tldraw ink drawn ✅
- [ ] `demo.ts` registers `StillnessMonitorPlugin` ✅
- [ ] `demo.ts` registers `SymbioteInjectorPlugin` ✅

---

## 9. Key Calman Config (Ship Defaults)

```typescript
// w3c_pointer_fabric.ts — tuned for 30fps phone camera
const DEFAULT_CONFIG = {
    smoothingQ: 0.05,   // Low — trust Kalman model; landmark noise is real
    smoothingR: 10.0,   // High — landmarks jump ±5px/frame at 30fps
    predictSteps: 1,    // 1-frame lookahead for lag compensation
    commitDwellTicks: 6, // Anti-Midas: 6 frames of steady gesture before commit
    coastFrames: 3,     // Continue on 3 frames of MediaPipe tracking loss
};
```

---

## 10. The 5 Core Pieces (Pareto MVP — Build Exactly These)

If you build exactly these 5 pieces and the test suite passes the 5 corresponding Gherkin scenarios, the Omega v15 MVP is proven:

| # | Core Piece | What it Proves | Key Spec |
|---|-----------|----------------|----------|
| CP-1 | Foveated ROI Cropping | Thermal survival on phone at 30fps | SPEC 6 quarantine |
| CP-2 | Scale-Invariant Biological Raycasting | Pinch works at any hand size / distance | FSM SPEC 5 |
| CP-3 | WebRTC UDP DataChannel | Zero-freeze cursor over Wi-Fi | Integration E2E |
| CP-4 | W3C Level 3 Symbiote Injector | Unmodified web apps respond to gesture control | SPEC 3 |
| CP-5 | Wood Grain Tuning Profile | Privacy-by-Math personalization without biometric surveillance | Unit: serialize/deserialize |

---

## 11. External AI Prompt Template

When handing this charter + companion File 1 to an external LLM, use this prompt:

```
You are being handed two documents:
1. omega_v15_context_bundle_state_of_union.md — the honest audit of what exists and what is broken
2. omega_v15_rewrite_charter.md — this document — the rules for the clean-room rewrite

Your task: [INSERT SPECIFIC TASK — e.g., "Design the w3c_pointer_fabric.ts rewrite following all 10 Rules and the ATDD enforcement protocol from §5"]

Constraints:
- Follow ALL 10 Rules in §2 (they are non-negotiable)
- Follow ATDD protocol: write failing test FIRST, then implementation
- Target Stryker score: 80-99%
- Check your output against the Banned Patterns in §7 before submitting
- Your deliverable must satisfy the Definition of Done items relevant to the component you are writing
```

---

*Generated: 2026-02-21 | Session: 0b7fc19935bff522 | PREY8 nonce: 8712D4 | HFO Gen90*  
*Companion: `omega_v15_context_bundle_state_of_union.md`*
