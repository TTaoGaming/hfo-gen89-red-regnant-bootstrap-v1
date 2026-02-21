---
schema_id: hfo.gen89.diataxis.omega_v13_microkernel.v1
medallion_layer: silver
doc_type: explanation
port: P4
tags: omega_v13, microkernel, architecture, diataxis, betrayal_audit, refactor_guide
bluf: "Diataxis analysis of the Omega v13 Man vs Machine architectural divergence. Six confirmed violations, surgical strike plan, and verified SOTA triumphs."
date: 2026-02-20
author: P4 Red Regnant (gen89)
---

# Omega v13 Microkernel — Diataxis Analysis
## Man vs. Machine: SOTA Triumphs, Six Betrayals, and the Surgical Strike

> **Validation status:** Every claim below was verified against live source files on 2026-02-20.
> Minor line-number precision errors in the source analysis (noted inline). All architectural claims confirmed.

---

## FRAMEWORK NOTE: Why Diataxis?

This document uses the [Diataxis](https://diataxis.fr/) framework to separate concerns:

| Quadrant | Orientation | Answers |
|---|---|---|
| **Tutorial** | Learning | "Walk me through what happened" |
| **How-to** | Task / Problem | "How do I fix violation X?" |
| **Reference** | Information | "What is the current state of each file?" |
| **Explanation** | Understanding | "Why does this architecture exist?" |

---

## PART I — EXPLANATION: The Architecture and Why It Was Betrayed

### The Microkernel Contract

Omega v13 is a **strict Microkernel OS** for gesture-driven spatial computing. The architecture
demands three invariants:

1. **Shared Data Fabric** — All communication between plugins flows exclusively over a single
   `EventBus` instance, injected per-supervisor instance. No plugin may hold a reference to
   a bus it did not receive via `PluginContext.eventBus`.

2. **Plugin Interface** — Every component (camera, fabric, compositor, audio) must implement
   `Plugin { name, version, init(ctx), start(), stop(), destroy() }`. The `PluginSupervisor`
   owns all lifecycle events. No component may self-start.

3. **Path Abstraction Layer (PAL)** — No component may call `window.innerWidth`, hardcode
   device dimensions, or resolve screen geometry directly. All environment reads go through
   `context.pal.resolve('ScreenWidth')`.

These three invariants are codified as `[RED]` tests in
`microkernel_arch_violations.spec.ts` — a world-class **OS Immune System** that will permanently
catch any future regression.

### The LLM Betrayal Pattern

The AI wrote the correct immune system, then ignored it when building the visual demo.
This is a well-known LLM failure mode: the model optimizes for "working demo quickly" at the
cost of architectural coherence. The result is a **hidden monolith** — the demo looks decoupled
but is secretly a God-Object that hard-couples every subsystem.

The irony: `MediaPipeVisionPlugin` was written correctly (pure Plugin, no gesture buckets,
uses `context.eventBus`) but was never imported into `demo_2026-02-20.ts`.
The AI wrote the abstraction and then copy-pasted the old code anyway.

---

## PART II — REFERENCE: Confirmed State of Each File (2026-02-20)

### ✅ SOTA: Files in Good Standing

#### `microkernel_arch_violations.spec.ts`
- 498 lines of ATDD/SBE specification for all 6 violations
- `[RED]` tests define acceptance criteria for violations not yet fixed
- `[GREEN]` tests are permanent regression guards
- Covers V1 (singletons), V2 (god object), V3 (double debounce), V4 (rogue agents),
  V5 (PAL leaks), V6 (stub impls)
- `makeContext()` factory correctly isolates `EventBus` + `PathAbstractionLayer` per test
- **Status: Do not modify. This is the spec. Fix the implementation to match it.**

#### `mediapipe_vision_plugin.ts`
- Correctly `implements Plugin` (line 50)
- Does NOT contain `gestureBuckets` or any debounce logic (confirmed: grep clean)
- Uses `context.pal.resolve<number>('OverscanScale')` for scale (line 76)
- Publishes only to `context.eventBus` — never imports `globalEventBus`
- Provides `injectTestFrame()` hook for headless BDD testing
- **Status: Architecturally correct. Unused by demo. Needs to be wired in.**

#### `tldraw_layer.html` — The Symbiote Agent
- Receives `SYNTHETIC_POINTER_EVENT` via `window.addEventListener('message', ...)`
- Calls `document.elementFromPoint(clientX, clientY)` inside the tldraw iframe
  to find the deep React sub-target
- Reconstructs a full `PointerEvent` with `bubbles: true, composed: true` and dispatches it
- Also handles `SYNTHETIC_WHEEL_EVENT` for scroll actions
- **This is the "Zero-Integration Spatial Computing" technique — React is being hacked from the outside through the iframe boundary**
- **Status: Correct. No changes needed.**

#### `layer_manager.ts` — Z-Stack Compositor
- Implements a Window-Manager-style central registry for 5 visual layers:
  - `z=0` VIDEO_BG, `z=10` BABYLON, `z=20` TLDRAW (pointer-events:auto),
    `z=30` SETTINGS, `z=40` VIZ (pointer-events:none)
- `applyStyles()` enforces `position:fixed; top:0; left:0; width:100vw; height:100vh`
- **⚠️ BETRAYAL: Exports `globalLayerManager = new LayerManager()` singleton (final line)**
  - This is a V1 Global Singleton Contraband violation that the source analysis identifies
    but does not name explicitly. The surgical strike must also nuke this.

#### `gesture_fsm_plugin.ts`, `audio_engine_plugin.ts`, `visualization_plugin.ts`, `stillness_monitor_plugin.ts`
- All correctly `implements Plugin`
- Status: Good standing (minor issues may exist; see V1 RED tests for FSM global bus import)

---

### 🚨 BETRAYAL: Files with Confirmed Violations

#### `event_bus.ts` — V1 Global Singleton Contraband

```typescript
// line 31 — THE CONTRABAND
export const globalEventBus = new EventBus();
```

**Violation:** `globalEventBus` is exported as a module-level singleton. Because JS modules
are singletons by the module system, any file that `import { globalEventBus }` bypasses the
`PluginSupervisor`'s bus injection entirely. The supervisor cannot isolate, restart, or
replace the bus.

**Consumers (all hard-coupled):** `demo_2026-02-20.ts`, `shell.ts`, `layer_manager.ts`,
`w3c_pointer_fabric.ts`, `babylon_landmark_plugin.ts`

**Fix:** Delete the export. Force compile errors that drive all consumers to accept
`context.eventBus` as their only bus.

---

#### `layer_manager.ts` — V1 Global Singleton Contraband (second instance)

```typescript
// final line — SECOND CONTRABAND
export const globalLayerManager = new LayerManager();
```

**Fix:** Delete. Wrap `LayerManager`/`Shell` into a `CompositorPlugin` that receives
its bus from `context.eventBus` during `init()`.

---

#### `demo_2026-02-20.ts` — V2 God-Object + V3 Double-Debounce

**V2: Phantom Refactor (lines ~247–370)**

The bootstrapper contains:
- `let handLandmarker: HandLandmarker | null = null`
- `const gestureBuckets: Record<number, {pointer_up, closed_fist, open_palm}>`
- `const BUCKET_MAX = 10, BUCKET_LEAK = 1, BUCKET_FILL = 3, GESTURE_THRESHOLD = 7`
- The full `predictWebcam()` loop with `FilesetResolver`, `HandLandmarker.createFromOptions`
- `globalEventBus.publish('FRAME_PROCESSED', handsData)`

`MediaPipeVisionPlugin` is **not imported** (confirmed: the import block at lines 1–41 contains
`GestureFSMPlugin`, `AudioEnginePlugin`, `VisualizationPlugin`, `W3CPointerFabric`,
`globalEventBus`, `globalLayerManager`, `ConfigManager`, `Shell`, `FilesetResolver`,
`HandLandmarker` — but no `MediaPipeVisionPlugin`).

> **Source analysis says "lines 140-270" — actual range is ~lines 247-370.**
> Precision error only; architectural claim is 100% correct.

**V3: Double-Debounce**

`gestureBuckets` in the demo implements leaky-bucket hysteresis (BUCKET_LEAK/FILL/THRESHOLD).
`GestureFSM.ts` also implements state smoothing. These two filters are in series.
Result: gesture transitions are debounced twice, adding approximately one full FSM cycle
of input latency on top of the existing hysteresis.

**Fix:** Remove `predictWebcam`, `handLandmarker`, `gestureBuckets`, `curlScore`, and the
`FilesetResolver`/`HandLandmarker` imports from `demo_2026-02-20.ts`. Register
`MediaPipeVisionPlugin` instead. The bootstrapper should only configure PAL and call
`supervisor.registerPlugin()`.

---

#### `w3c_pointer_fabric.ts` — V4 Rogue Agent + V5 PAL Leak

**V4: Does not implement `Plugin`**

```typescript
// class declaration — no 'implements Plugin'
export class W3CPointerFabric {
```

And the constructor hard-subscribes to `globalEventBus` directly:
```typescript
// constructor body
globalEventBus.subscribe('POINTER_UPDATE', this.onPointerUpdate.bind(this));
globalEventBus.subscribe('POINTER_COAST', this.onPointerCoast.bind(this));
```

The `PluginSupervisor` cannot stop, restart, or replace this component. It is a permanent
ambient service with no lifecycle.

**V5: PAL Leak (hardcoded screen dimensions)**

```typescript
// line ~95 in processLandmark() — and again in coastLandmark()
const screenWidth = window.innerWidth;
const screenHeight = window.innerHeight;
```

> **Source analysis says "line 91" — actual is ~line 95.**
> Precision error only; the violation is confirmed.

`window.innerWidth` makes this component headless-untestable and device-tied. The correct
form is `context.pal.resolve('ScreenWidth')`.

**Fix:** Add `implements Plugin`. Remove `globalEventBus` import. Accept `PluginContext` in
`init()`. Use `context.pal.resolve('ScreenWidth')` for screen dimensions.

---

## PART III — HOW-TO: The Surgical Strike (4 Refactors)

Execute in order. Run `npx jest microkernel_arch_violations.spec --no-coverage --verbose`
after each step to advance RED → GREEN.

### Refactor 1: Nuke the Singletons (V1)

**Files:** `event_bus.ts`, `layer_manager.ts`

1. In `event_bus.ts`, delete line 31:
   ```diff
   - export const globalEventBus = new EventBus();
   ```
2. In `layer_manager.ts`, delete the final export:
   ```diff
   - export const globalLayerManager = new LayerManager();
   ```
3. Let the TypeScript compiler emit errors on every file that imported these.
   Each error is a coupling violation that needs fixing in steps 2–4.
4. Add `getEventBus(): EventBus` to `PluginSupervisor` so `ATDD-ARCH-001` can pass.

**Gate:** `ATDD-ARCH-001` RED tests pass when `PluginSupervisor` instances are fully isolated.

---

### Refactor 2: Plugin-ify the Compositor and Fabric (V4 + partial V1)

**Files:** `layer_manager.ts`, `shell.ts` → new `CompositorPlugin.ts`;
`w3c_pointer_fabric.ts` → new `W3CPointerFabricPlugin.ts`

1. Create `CompositorPlugin` that `implements Plugin`:
   - `init(ctx)` receives `ctx.eventBus` and `ctx.pal`
   - Internally creates a `LayerManager` instance (not a global)
   - Subscribes to `LAYER_OPACITY_CHANGE` on `ctx.eventBus`
   - Mounts `Shell` inside itself

2. Create `W3CPointerFabricPlugin` that `implements Plugin`:
   - `init(ctx)` receives `ctx.eventBus` and `ctx.pal`
   - Subscribes to `POINTER_UPDATE` and `POINTER_COAST` on `ctx.eventBus`
   - Replaces `window.innerWidth` with `ctx.pal.resolve<number>('ScreenWidth')`
   - Replaces `window.innerHeight` with `ctx.pal.resolve<number>('ScreenHeight')`

**Gate:** `ATDD-ARCH-004` (V4 Rogue Agent) and `ATDD-ARCH-005` (V5 PAL Leak) turn GREEN.

---

### Refactor 3: Purge the Double-Debounce (V3)

**File:** `demo_2026-02-20.ts`

Remove from the bootstrapper:
- `const gestureBuckets: Record<...>`
- `const currentGestures: Record<...>`
- `const BUCKET_MAX, BUCKET_LEAK, BUCKET_FILL, GESTURE_THRESHOLD`
- The entire bucket logic block inside `predictWebcam()`

`MediaPipeVisionPlugin` must emit raw classification (highest-scoring gesture without smoothing).
`GestureFSMPlugin` is the sole smoother downstream.

**Gate:** `ATDD-ARCH-003` (V3 Double-Debounce) turns GREEN — confirmed by checking that
`MediaPipeVisionPlugin` has zero `gestureBuckets` or `BUCKET_` references.

---

### Refactor 4: Gut the Bootstrapper (V2)

**File:** `demo_2026-02-20.ts`

Remove from `bootstrap()`:
- `let handLandmarker`
- `let lastVideoTime`, `lastProcessTime`, `PROCESS_INTERVAL_MS`
- `function curlScore()`
- `function predictWebcam()`
- `async function startCamera()` (move the `START_CAMERA_REQ` event dispatch to Shell CTA)
- The `FilesetResolver` and `HandLandmarker` imports

Replace with:
```typescript
const pal = new PathAbstractionLayer();
pal.register('ScreenWidth',  window.screen.width);
pal.register('ScreenHeight', window.screen.height);
pal.register('OverscanScale', 1.0);

const supervisor = new PluginSupervisor(); // no globalEventBus argument
supervisor.registerPlugin(new MediaPipeVisionPlugin());
supervisor.registerPlugin(new GestureFSMPlugin());
supervisor.registerPlugin(new CompositorPlugin());
supervisor.registerPlugin(new W3CPointerFabricPlugin());
supervisor.registerPlugin(new AudioEnginePlugin());
supervisor.registerPlugin(new VisualizationPlugin());
await supervisor.initAll(pal);
await supervisor.startAll();
```

The `Shell` CTA button emits `START_CAMERA_REQ` on the bus.
`MediaPipeVisionPlugin.start()` listens for `START_CAMERA_REQ` and opens the camera.
No MediaPipe code touches the bootstrapper.

**Gate:** `ATDD-ARCH-002` (V2 God-Object) turns GREEN — `demo_2026-02-20.ts` must not
contain any `HandLandmarker`, `FilesetResolver`, `gestureBuckets`, or `predictWebcam` tokens.

---

## PART IV — TUTORIAL: What You Will Experience After the Strike

This is a narrative walkthrough of the end state, to cement the mental model.

### Before: The Monolith Disguised as Components

```
bootstrap() {
  ← creates video element directly
  ← creates HandLandmarker directly
  ← runs predictWebcam() loop
  ← runs gestureBuckets smoothing
  ← publishes FRAME_PROCESSED on globalEventBus
  ← GestureFSMPlugin picks it up from globalEventBus
  ← W3CPointerFabric picks it up from globalEventBus
  ← they're "decoupled" but share a hidden global wire
}
```

The system _looks_ decoupled from the outside but every component is secretly eavesdropping
on a single global pub/sub channel that nobody owns.

### After: True Microkernel

```
PluginSupervisor.initAll(pal)
  → MediaPipeVisionPlugin.init(ctx)   ← receives ctx.eventBus (isolated)
  → GestureFSMPlugin.init(ctx)        ← same bus, scoped to THIS supervisor
  → W3CPointerFabricPlugin.init(ctx)  ← same bus, no window.* calls
  → CompositorPlugin.init(ctx)        ← creates LayerManager, mounts Shell

bootstrap() only:
  ← configure PAL
  ← registerPlugin() ×6
  ← initAll()
  ← startAll()
  Done.
```

**What changes become possible:**
- Swap `MediaPipeVisionPlugin` for `MP4VisionPlugin` (replay recorded sessions): zero
  changes to any other file.
- Swap `EventBus` for `WebRTCUDPEventBus`: `PluginSupervisor` accepts any bus;
  no plugin imports it.
- Run two `PluginSupervisor` instances side-by-side (split-view mode): buses don't cross.
- Headless Playwright testing of the full pipeline with `injectTestFrame()`: no browser
  geometry required; PAL provides all screen math.

---

## Appendix A: Violation Summary Matrix

| ID | Violation | File | Confirmed? | Fix Step |
|----|-----------|------|------------|----------|
| V1a | `globalEventBus` singleton export | `event_bus.ts` line 31 | ✅ | Refactor 1 |
| V1b | `globalLayerManager` singleton export | `layer_manager.ts` final line | ✅ | Refactor 1 |
| V2 | Full MediaPipe loop in bootstrapper | `demo_2026-02-20.ts` lines ~247-370 | ✅ | Refactor 4 |
| V3 | `gestureBuckets` in demo + FSM downstream | `demo_2026-02-20.ts` lines ~255-265 | ✅ | Refactor 3 |
| V4 | `W3CPointerFabric` not `implements Plugin` | `w3c_pointer_fabric.ts` | ✅ | Refactor 2 |
| V5 | `window.innerWidth` hardcoded (×3) | `w3c_pointer_fabric.ts` lines ~95, ~152, ~162 | ✅ | Refactor 2 |
| V6 | `MediaPipeVisionPlugin` exists but unused | `demo_2026-02-20.ts` imports | ✅ | Refactor 4 |

---

## Appendix B: Source Analysis Accuracy Notes

The source analysis ("Man vs. Machine" review) is **substantially accurate**. Two minor
precision errors were found in line numbers, with no impact on the correctness of the
architectural claims:

| Claim | Stated | Actual | Impact |
|---|---|---|---|
| `predictWebcam` location | "lines 140-270" | ~lines 247-370 | None — violation confirmed |
| `window.innerWidth` location | "line 91" | ~line 95 | None — violation confirmed |

One omission: The analysis names `globalEventBus` in `event_bus.ts` as the sole singleton
contraband. The `globalLayerManager` export in `layer_manager.ts` is a second V1 violation
that must also be nuked in the Surgical Strike.

---

*Generated by P4 Red Regnant — Gen89 — 2026-02-20*
*Validated against live source files. All architectural claims confirmed.*
