---
schema_id: hfo.gen89.p0.true_sight.v1
medallion_layer: bronze
port: P0
doc_type: forge_report
bluf: "P0 TRUE_SIGHT audit of omega_v13_microkernel — all hidden faults surfaced. 3 critical fixes applied."
tags: omega_v13,true_sight,p0,audit,ghost_events,orphan_files,pal_leak,plugin_registration
date: 2026-02-20
---

# P0 TRUE_SIGHT — Omega v13 Microkernel Audit

> **Operator:** TTAO  
> **Session:** f2b745f7d330aebe (PREY8 chain, react_token 9CB700)  
> **Scope:** Full AST scan — 54 .ts files, all event bus channels, all import chains  
> **Result:** 3 critical bugs fixed, 4 ghost event channels documented, 14+ orphan files catalogued

---

## Executive Summary

The P0 OBSERVE scan cast TRUE_SIGHT on the entire omega_v13_microkernel source tree. Three categories of hidden faults were found:

1. **Critical bugs** — code that actively broke live behavior (fixed in this session)
2. **Ghost event channels** — events published or subscribed with no matching counterpart (documented; 2 are extension points, 2 are benign)
3. **Orphan production files** — code that compiles and tests pass but never enters the live demo bootstrap chain

---

## 🚨 Critical Bugs Fixed

### Bug 1: PAL Leak in `visualization_plugin.ts:111`
**Before:**
```typescript
const scale = (window as any).omegaOverscanScale || 1.0;
```
**After:**
```typescript
// PAL-sourced overscan (ARCH-V5: never read raw window) — fix for PAL leak surfaced in P0 TRUE_SIGHT
const scale = this.context?.pal?.resolve<number>('OverscanScale') ?? 1.0;
```
**Impact:** The hand skeleton overlay was reading overscan from raw `window` instead of the PAL contract. Any future overscan changes via `OVERSCAN_SCALE_CHANGE` would update the PAL but the skeleton would remain at the old value. Now it always reads from PAL — the single source of truth.

---

### Bug 2: `StillnessMonitorPlugin` Not Registered in `demo_2026-02-20.ts`
**Before:** Zero registrations. `GestureFSMPlugin` subscribes to `STILLNESS_DETECTED` but the only publisher (`StillnessMonitorPlugin`) was never registered. Stillness detection was **completely broken** in the live demo.

**After (demo_2026-02-20.ts):**
```typescript
// TRUE_SIGHT fix: StillnessMonitorPlugin publishes STILLNESS_DETECTED which GestureFSMPlugin needs
supervisor.registerPlugin(new StillnessMonitorPlugin());
```
**Impact:** `STILLNESS_DETECTED` now fires after 1 minute of hand stillness (3600 ticks at 60fps). The FSM idle timer is now active.

---

### Bug 3: `SymbioteInjectorPlugin` Not Registered in `demo_2026-02-20.ts`
**Before:** `SymbioteInjectorPlugin` was only in the old `demo.ts` entry point. The live `demo_2026-02-20.ts` never registered it. Real `PointerEvent` dispatch to `document.elementFromPoint` (tldraw DOM injection) was **completely dead** in the current bootstrap.

**After (demo_2026-02-20.ts):**
```typescript
// TRUE_SIGHT fix: SymbioteInjectorPlugin dispatches real PointerEvents to document.elementFromPoint
supervisor.registerPlugin(new SymbioteInjectorPlugin());
```
**Impact:** The WYSIWYG invariant is now complete. `POINTER_UPDATE` → `SymbioteInjectorPlugin` → `document.elementFromPoint(sx, sy)` → real DOM `PointerEvent` → tldraw cursor moves.

---

## ⚠️ Ghost Event Channels (documented, not bugs)

| Event | Status | Direction | Analysis |
|---|---|---|---|
| `SETTINGS_TOGGLE` | Extension point | Subscribed in `shell.ts:444`, no publisher | Intentional external API hook. Gear button calls `toggleSettings()` directly. Any future gesture or external code can toggle settings via bus. Not broken — just unused. |
| `SETTINGS_PANEL_STATE` | Extension point | Published in `shell.ts:759`, no subscriber | Broadcast notification. Future components (e.g., a visual indicator or Playwright test) can listen. Not broken — just unused. |
| `OVERSCAN_SCALE_CHANGE` | Static default | Subscribed in `demo_2026-02-20.ts:134+`, no publisher | Handler is ready; OverscanScale is just fixed at 1.0 until a UI overscan slider is added. Not broken — extension point for future overscan UI. |
| `RAW_HAND_DATA` | Test-only | Published in `babylon_w3c_pipeline.spec.ts`, not in `MicrokernelEvents` | Spec internal bus injection pattern. Does not need to be in the schema. Low priority cleanup. |

---

## 📋 Orphaned Production Files

These files compile and have specs but are **not in the live demo import chain** (`demo_2026-02-20.ts`). They are deferred features, not dead code.

| File | Category | Why Orphaned | Priority |
|---|---|---|---|
| `babylon_landmark_plugin.ts` | B1 feature | B1 work pending — dots not yet registered | NEXT (30 min) |
| `babylon_physics.ts` | B2 feature | Needs Plugin interface + velocity-drive fix | NEXT (3 hrs) |
| `behavioral_predictive_layer.ts` | V14 deferred | GA deferred per operator decision session yield 16683 | V14 |
| `video_throttle.ts` | V14 deferred | Resolution ladder targeting — WebRTC also deferred | V14 |
| `webrtc_udp_transport.ts` | V14 deferred | WebRTC explicitly deferred per operator decision | V14 |
| `overscan_canvas.ts` | Extension point | Overscan UI not yet built | Future |
| `temporal_rollup.ts` | Utility | Test-only usage; no production consumer yet | Future |
| `wood_grain_tuning.ts` | Utility | Tuning helper; no live wiring needed | Future |
| `highlander_mutex_adapter.ts` | Pattern | Never in any production import chain | Future |
| `biological_raycaster.ts` | Research | Spec only — exploratory | V14+ |
| `foveated_cropper.ts` | Research | Spec only; MediaPipe Tasks API handles FOV internally | V14+ |
| `schemas.ts` | Utility | Only `test_zod.ts` | Low |
| `gesture_bridge.ts` (class) | Type adapter | `GestureBridge` class in spec only; file kept as type re-export | Low |
| `mediapipe_gesture.ts` | Type source | Only type imports; no class ever instantiated | Low |
| `demo.ts` | Obsolete | Superseded by `demo_2026-02-20.ts` | Delete when stable |

---

## 🔍 Type Holes in Production Code

| Location | Issue | Risk |
|---|---|---|
| `w3c_pointer_fabric.ts:37-38` | `boundOnPointerUpdate: (data: any)` | Low — `PointerUpdatePayload` type available but not enforced |
| `w3c_pointer_fabric.ts:80` | `configManager.subscribe((cfg: any)` | Low — `ConfigMosaic` available; could add type safety |
| `gesture_fsm_plugin.ts` | Event handler `data: any` | Low — internal use only |
| `symbiote_injector_plugin.ts:39` | `data: any` on pointer handler | Low — typed as `unknown` in constructor, `any` in handler body |
| `demo_2026-02-20.ts` | `(window as any).omegaInjectFrame`, `__omegaExports` | Acceptable — documented test/debug harnesses |

---

## Live Demo Plugin Registration (after fixes)

```
supervisor.registerPlugin(new MediaPipeVisionPlugin({ videoElement }));  // P0: camera + landmarks
supervisor.registerPlugin(new GestureFSMPlugin());                        // FSM: POINTER_UPDATE
supervisor.registerPlugin(new AudioEnginePlugin());                       // Cherry MX sounds
supervisor.registerPlugin(new VisualizationPlugin());                     // Hand skeleton overlay
supervisor.registerPlugin(new W3CPointerFabric({ ... }));                 // Kalman + W3C events
supervisor.registerPlugin(new StillnessMonitorPlugin());  // ← FIXED: stillness timer
supervisor.registerPlugin(new SymbioteInjectorPlugin());  // ← FIXED: DOM PointerEvent injection
```

---

## Event Bus Channel Map (live demo, post-fix)

```
CAMERA_START_REQUESTED  ← bus.publish (Shell "START CAMERA" button)
                        → MediaPipeVisionPlugin.subscribe

FRAME_PROCESSED         ← MediaPipeVisionPlugin.publish (every frame)
                        → GestureFSMPlugin.subscribe
                        → StillnessMonitorPlugin.subscribe  ← RESTORED
                        → Shell.subscribe (camera state detection)

STATE_CHANGE            ← GestureFSMPlugin.publish
                        → Shell.subscribe (coach bar)
                        → VisualizationPlugin.subscribe (dot color)
                        → AudioEnginePlugin.subscribe (sound)

POINTER_UPDATE          ← GestureFSMPlugin.publish
                        → VisualizationPlugin.subscribe (skeleton)
                        → W3CPointerFabric.subscribe (Kalman → W3C events)
                        → SymbioteInjectorPlugin.subscribe  ← RESTORED

POINTER_COAST           ← GestureFSMPlugin.publish
                        → VisualizationPlugin.subscribe

STILLNESS_DETECTED      ← StillnessMonitorPlugin.publish  ← RESTORED
                        → GestureFSMPlugin.subscribe

SETTINGS_PANEL_STATE    ← Shell.publish (on toggle) — extension point, no subscriber yet
SETTINGS_TOGGLE         ← external publish — extension point, shell subscribes
OVERSCAN_SCALE_CHANGE   ← external publish — extension point, demo subscribes (updates PAL)
```

---

## Verification

- `npx tsc --noEmit` — 0 errors (post-fix)
- Jest — 73/73 (pre-existing `babylon_w3c_pipeline.spec.ts` suite failure is a Playwright test picked up by Jest config, not caused by these changes)
- Playwright — 16/16

---

## PREY8 Chain Reference

| Event | ID | Note |
|---|---|---|
| Session | f2b745f7d330aebe | p4_red_regnant |
| Last yield (prior session) | 16683 | nonce 5BC27B — all operator decisions logged |
| This execute (TRUE_SIGHT fix) | 16687 | step 3, execute_token E24CB5 |
