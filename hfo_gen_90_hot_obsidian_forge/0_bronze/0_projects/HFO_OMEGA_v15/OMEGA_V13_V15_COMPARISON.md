---
schema_id: hfo.gen90.omega_compare.v13_v15.v1
medallion_layer: bronze
doc_type: reference
port: P7
bluf: "Side-by-side comparison of Omega v13 vs v15: tile inventory, test coverage, violations, SOTA patterns, and next required tiles."
date: 2026-02-21
---

# Omega v13 vs v15 — Comparison Manifest

> v13 source: `OMEGA_V13_MANIFEST.md` (binding minimus, 2026-02-20, 80 files)
> v15 source: `OMEGA_V15_AUDIT_MANIFEST.md` (mutation testing complete, 2026-02-21, 42 files)

---

## 1. Status at a Glance

| Dimension | v13 (2026-02-20) | v15 (2026-02-21) |
|-----------|-----------------|-----------------|
| **Ship verdict** | ❌ PARTIAL SHIP | ⚠️ AUDIT-NEAR — 1 blocker (DEFECT-001) |
| **Contract violations** | 6 × RED (V1–V6) | V1 resolved (no global singletons), V4/V5 status unknown |
| **Stryker coverage** | ⚠️ Not confirmed | ✅ **5/5 primary tiles at Goldilocks (80–99%)** |
| **Jest tests** | 73 Jest + 16 Playwright | 242 (6 suites, all passing) |
| **TypeScript errors** | 0 | 0 |
| **SBE wrappers** | ❌ None | ✅ **3/3 passing** |
| **Golden master** | ✅ `demo_video_golden.ts` | ✅ `demo_video_golden.ts` (carried forward) |
| **Critical path** | Fix V1 → compiler drives V2–V5 | Fix DEFECT-001 → register Symbiote in shell.ts |
| **Highest unresolved risk** | A6 (Untrusted Audio Trap) | A6 (same — UX decision still required) |

---

## 2. Mutation Testing Scorecard

### v13 — No confirmed Stryker baseline

| Tile | Stryker | Notes |
|------|---------|-------|
| All tiles | ⚠️ Report on disk, not verified | Pre-mutation-testing phase |

### v15 — All primary tiles hardened

| Tile | Stryker % | Killed / Total | Status |
|------|-----------|---------------|--------|
| `kalman_filter.ts` | **95.08%** | — | ✅ Goldilocks |
| `event_bus.ts` | **84.31%** | — | ✅ Goldilocks |
| `plugin_supervisor.ts` | **85.85%** | — | ✅ Goldilocks |
| `audio_engine_plugin.ts` | **88.89%** | 138/162 | ✅ Goldilocks |
| `symbiote_injector_plugin.ts` | **87.76%** | 43/49 | ✅ Goldilocks |
| `gesture_fsm_plugin.ts` | ❌ BLOCKED | WASM dependency | Needs mock injection |
| All other tiles | ⏳ NOT TESTED | — | See §4 below |

---

## 3. Tile Inventory — v13 vs v15

### Core Microkernel (present in both)

| File | v13 Status | v15 Status | Δ |
|------|-----------|-----------|---|
| `event_bus.ts` | VIOLATION V1 (globalEventBus) | ✅ 84.31% Stryker — no global singleton | Fixed V1 |
| `plugin_supervisor.ts` | GOOD | ✅ 85.85% Stryker | Hardened |
| `audio_engine_plugin.ts` | GOOD — zombie listener bug (A5) | ✅ 88.89% Stryker — A5 fixed (T-OMEGA-005) | A5 resolved |
| `symbiote_injector_plugin.ts` | — | ✅ 87.76% Stryker — DEFECT-001 (not in shell.ts) | New tile, Potemkin |
| `symbiote_injector.ts` | GOOD (stateful upgrade pending) | Present (31 lines, compat shim?) | ⚠️ Relationship unclear |
| `kalman_filter.ts` | GOOD | ✅ 95.08% Stryker | Hardened |
| `gesture_fsm_plugin.ts` | GOOD | ⚠️ WASM blocked, no Stryker | Regressed on testability |
| `gesture_fsm.ts` | Present | Present (265 lines) | Not tested |
| `mediapipe_vision_plugin.ts` | GOOD — unused by demo | Present (391 lines) | Not tested |
| `visualization_plugin.ts` | GOOD | Present (249 lines) | Not tested |
| `stillness_monitor_plugin.ts` | GOOD | Present (91 lines) | Not tested |
| `behavioral_predictive_layer.ts` | ANTIPATTERN — main-thread GA (A1) | Present (318 lines) | A1 likely unresolved |
| `behavioral_predictive_worker.ts` | PARTIAL — path broken | Present (125 lines) | Status unknown |
| `w3c_pointer_fabric.ts` | VIOLATION V4+V5 | Present (470 lines) | Violations likely unresolved |
| `layer_manager.ts` | VIOLATION V1 (globalLayerManager) | Present (159 lines) | Status unknown |
| `wood_grain_tuning.ts` | PARTIAL — GA integration deferred | Present (24 lines) | Status unknown |
| `temporal_rollup.ts` | CONFIRMED SOTA (S3) | Present (147 lines) | Not tested |
| `webrtc_udp_transport.ts` | IN_PROGRESS — stub | Present (42 lines) | Status unknown |
| `biological_raycaster.ts` | PARTIAL — not wired | Present (13 lines) | Status unknown |
| `foveated_cropper.ts` | PARTIAL — not in demo path | Present (66 lines) | Status unknown |

### New in v15 (not in v13)

| File | Lines | Category | Priority |
|------|-------|----------|----------|
| `shell.ts` | 778 | Orchestration — replaces ad-hoc bootstrapper | 🔴 Critical |
| `babylon_physics.ts` | 348 | Physics-as-UI (SOTA S4) | 🟠 High |
| `babylon_landmark_plugin.ts` | 262 | Visualization | 🟡 Medium |
| `hud_plugin.ts` | 79 | Debug overlay (F4 from v13 trade study) | 🟡 Medium |
| `input_harnesses.ts` | 225 | Test infrastructure | 🟡 Medium |
| `event_channel_manifest.ts` | 295 | Event type registry | 🟡 Medium |
| `iframe_delivery_adapter.ts` | 127 | Delivery abstraction | 🟡 Medium |
| `highlander_mutex_adapter.ts` | 112 | "One true pinch" guard | 🟡 Medium |
| `overscan_canvas.ts` | 188 | Display — foveation output | 🟡 Medium |
| `video_throttle.ts` | 140 | Thermal stability (C3 from trade study) | 🟡 Medium |
| `gesture_fsm_rs_adapter.ts` | 65 | WASM bridge — blocks gesture_fsm Stryker | 🔴 Blocker |
| `gesture_bridge.ts` | 62 | Gesture routing | 🟡 Medium |
| `mediapipe_gesture.ts` | 182 | MediaPipe classification | 🟡 Medium |

### Present in v13, absent / moved in v15

| File | v13 Notes | v15 Status |
|------|----------|-----------|
| `demo_2026-02-20.ts` | VIOLATION V2/V3 (god object) | Present (222 lines) — likely still god object |
| `microkernel_arch_violations.spec.ts` | ATDD immune system (498 lines) | ⚠️ Not found in v15 project — **gap** |

---

## 4. Next Required Tiles (v15 Audit Gaps)

These are tiles present in v15 that have ZERO test coverage or known violations — ordered by audit priority.

### Priority 1 — Ship Blockers 🔴

| Tile | Lines | Why Critical | Recommended Test |
|------|-------|-------------|-----------------|
| `shell.ts` | 778 | Orchestration backbone — registers all plugins; DEFECT-001 lives here | Integration test: all plugins registered, loaded, destroyed cleanly |
| `w3c_pointer_fabric.ts` | 470 | V4+V5 violations from v13 likely still present; PAL leak `window.innerWidth`; no Plugin lifecycle | `test_w3c_pointer_fabric.ts` — PAL resolution, Plugin lifecycle, pointer coordinate transforms |
| `gesture_fsm.ts` | 265 | Core FSM state machine — all transitions, dwell timer, anti-Midas | `test_gesture_fsm.ts` — already exists (`test_gesture_fsm.ts` in jest.stryker.config.js) |

### Priority 2 — High Value 🟠

| Tile | Lines | Why | Recommended Test |
|------|-------|-----|-----------------|
| `behavioral_predictive_layer.ts` | 318 | A1 (main-thread GA) and A3 (ground truth paradox) likely still present | `test_behavioral_predictive_layer.ts` — evolve(), GA fitness, shadow tracker |
| `visualization_plugin.ts` | 249 | Plugin lifecycle; Babylon mocking needed | `test_visualization_plugin.ts` — mock Babylon Scene, verify dots rendered |
| `mediapipe_vision_plugin.ts` | 391 | Camera + ML core — most integration-heavy | `test_mediapipe_vision_plugin.ts` — mock vision API, verify event publish |
| `iframe_delivery_adapter.ts` | 127 | Delivery layer for Symbiote; no tests | `test_iframe_delivery_adapter.ts` |

### Priority 3 — Achievable Wins 🟡

| Tile | Lines | Why | Estimated Effort |
|------|-------|-----|-----------------|
| `stillness_monitor_plugin.ts` | 91 | Small, self-contained, pure logic | ~2 hours |
| `hud_plugin.ts` | 79 | Small, DOM-light | ~2 hours |
| `highlander_mutex_adapter.ts` | 112 | "One true pinch" mutex — pure logic | ~1 hour |
| `temporal_rollup.ts` | 147 | SOTA S3 — Kalman delta → English log | ~3 hours |
| `wood_grain_tuning.ts` | 24 | Privacy-by-Math (SOTA S1) | ~1 hour |

### Blocked / Deferred

| Tile | Lines | Blocker |
|------|-------|---------|
| `gesture_fsm_plugin.ts` | 191 | WASM `gesture_fsm_rs_adapter.ts` — needs `jest.mock()` stub |
| `babylon_physics.ts` | 348 | Babylon/Havok WASM — needs heavy mocking |
| `babylon_landmark_plugin.ts` | 262 | Babylon WASM |
| `mediapipe_gesture.ts` | 182 | MediaPipe WASM + browser APIs |
| `demo_2026-02-20.ts` | 222 | God object — not unit-testable until V2 fixed |

---

## 5. Violation Status — v13 → v15

| v13 Violation | Description | v15 Status |
|--------------|-------------|-----------|
| V1: Global Singleton Contraband | `globalEventBus`, `globalLayerManager` | ✅ **RESOLVED** — v15 event_bus has no global export (confirmed by 84.31% Stryker) |
| V2: God-Object Phantom Refactor | `demo_2026-02-20.ts` bootstrapper | ⚠️ File still present (222 lines) — likely unresolved |
| V3: Double-Debounce | Demo gesture buckets + FSM hysteresis in series | ⚠️ Unknown — `demo_2026-02-20.ts` not audited in v15 |
| V4: Rogue Agent (no Plugin lifecycle) | `w3c_pointer_fabric.ts` — no `implements Plugin` | ⚠️ Unknown — no v15 tests for this file |
| V5: PAL Leak (`window.innerWidth`) | `w3c_pointer_fabric.ts:~95` | ⚠️ Unknown — no v15 tests for this file |
| V6: Stub Implementations | `throw new Error('not implemented')` | ⚠️ Unknown — not audited |
| A5: Zombie Event Listener | `audio_engine_plugin.ts` no `boundOnStateChange` | ✅ **RESOLVED** — T-OMEGA-005 kills this class of mutant |
| A6: Untrusted Audio Trap | `AudioContext.resume()` from `isTrusted=false` | ⚠️ **STILL OPEN** — UX decision required |

---

## 6. SOTA Patterns — Carried Forward?

| Pattern | v13 | v15 |
|---------|-----|-----|
| S1: Privacy-by-Math (Wood Grain) | ✅ `wood_grain_tuning.ts` | ✅ Present (24 lines) — not tested |
| S2: Synthesized Synesthesia (Cherry MX) | ✅ `audio_engine_plugin.ts` | ✅ **88.89% Stryker** — CONFIRMED |
| S3: Procedural Observability | ✅ `temporal_rollup.ts` | ✅ Present (147 lines) — not tested |
| S4: Physics-as-UI (Velocinertia) | ✅ `babylon_physics.ts` wrong interface | ✅ Present (348 lines) — interface status unknown |
| NEW: Defense-in-Depth FSM | — | ✅ `gesture_fsm.ts` SCXML-inspired |
| NEW: Fail-Closed Mutation Gates | — | ✅ Stryker break=75% enforced on 5 tiles |

---

## 7. Open Questions for Auditor

1. **Did V4/V5 get fixed in v15?** `w3c_pointer_fabric.ts` (470 lines) has zero test coverage — does it `implements Plugin` now, and does it use PAL for `ScreenWidth`?

2. **Is `symbiote_injector.ts` (31 lines) a dead compat shim or still active?** v15 has both `symbiote_injector.ts` and `symbiote_injector_plugin.ts`. Relationship unclear.

3. **Is `behavioral_predictive_layer.ts` still on the main thread?** A1 was a ship-blocker in v13. Nothing in v15 confirms it's been moved to `BehavioralPredictiveWorker`.

4. **What is `shell.ts` (778 lines)?** This is the largest file in v15 and the DEFECT-001 blocker. It replaces the v13 demo bootstrapper pattern — but its plugin registry completeness is unverified.

5. **Is `microkernel_arch_violations.spec.ts` (498-line ATDD immune system) present in v15?** Not found in file search. If absent, the immune system was dropped.

---

## 8. Recommended Next Actions (Priority-Ordered)

1. **Fix DEFECT-001** — Register `SymbioteInjectorPlugin` in `shell.ts` (~30 min)
2. **Audit `w3c_pointer_fabric.ts`** — Check V4/V5 resolution; create `test_w3c_pointer_fabric.ts`
3. **Verify shell.ts plugin registry** — All plugins registered; destroy ⇔ init balance
4. **Create immune system spec for v15** — Port or replace `microkernel_arch_violations.spec.ts`
5. **Resolve `gesture_fsm_plugin.ts` block** — Add `jest.mock('./gesture_fsm_rs_adapter')` stub
6. **Tackle Priority 2 tiles** — `behavioral_predictive_layer`, `visualization_plugin`, `stillness_monitor_plugin`
7. **Wire CP1–CP4 end-to-end** — The 3-Pillar Pareto MVP still not wired in v15 either

---

*Bronze medallion. Generated by p7_spider_sovereign 2026-02-21.*
*PREY8 session f48e04a578db544a (nonce 504A98→27C579, chain intact).*
