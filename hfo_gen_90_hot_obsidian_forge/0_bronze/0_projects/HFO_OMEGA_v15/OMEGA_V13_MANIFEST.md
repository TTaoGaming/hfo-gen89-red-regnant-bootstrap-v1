---
schema_id: hfo.gen90.omega_v13.manifest.v1
medallion_layer: bronze
doc_type: reference
port: P7
bluf: "Omega v13 microkernel state capsule — tiles, test coverage, violations, and PARTIAL SHIP verdict as of 2026-02-20."
date: 2026-02-20
source: omega_v13_p7_binding_minimus_audit.md (silver, session a1e8d5e9dfc4b271)
---

# Omega v13 Microkernel — Manifest

> **Verdict: PARTIAL SHIP** — Architecture is sound; 6 contract violations unresolved; demo path is a hidden monolith.
> Source-of-record: `OMEGA_V13_CONCAT_2026-02-20.md` (80 files, 526.8 KB)

---

## Identity

| Field | Value |
|-------|-------|
| Version | v13 (pre-1.0) |
| Location | `hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel/` |
| Audit date | 2026-02-20 |
| Status | **PARTIAL SHIP** |
| Jest tests | 73 |
| Playwright tests | 16 |
| TypeScript errors | 0 |
| Stryker score | ⚠️ Not confirmed in audit |

---

## MVP Scope — 3-Pillar Pareto (5 Core Pieces)

The binding definition of "done" for v13. None wired end-to-end as of audit date.

| Pillar | Core Piece | File | Status |
|--------|-----------|------|--------|
| P1: Live on Smartphone | CP1: Foveated ROI Cropping (480p → 256×256) | `foveated_cropper.ts` | PARTIAL — not in demo path |
| P1: Live on Smartphone | CP2: Scale-Invariant Biological Raycasting | `biological_raycaster.ts` | PARTIAL — not wired to demo |
| P2: Cast to Big Screen | CP3: WebRTC UDP DataChannel (`ordered:false, maxRetransmits:0`) | `webrtc_udp_transport.ts` | IN_PROGRESS — transport stub |
| P2: Cast to Big Screen | CP4: W3C Level 3 Symbiote Injector (iframe pointer synthesis) | `symbiote_injector.ts` | PARTIAL — stateful upgrade pending |
| P3: Grow with User | CP5: Wood Grain Tuning (Privacy-safe `UserTuningProfile`) | `wood_grain_tuning.ts` | PARTIAL — GA integration deferred |

---

## Component Inventory (42 source files)

### Plugin Tiles — implements Plugin ✅

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `mediapipe_vision_plugin.ts` | ~391 | GOOD — unused by demo | Camera + ML core |
| `gesture_fsm_plugin.ts` | ~191 | GOOD | FSM orchestrator |
| `audio_engine_plugin.ts` | ~171 | GOOD — zombie listener bug (A5) | Cherry MX synthesizer |
| `visualization_plugin.ts` | ~249 | GOOD | Babylon dots overlay |
| `stillness_monitor_plugin.ts` | ~91 | GOOD | Anti-Midas dwell |
| `symbiote_injector.ts` | ~31 | GOOD — stateful upgrade pending | W3C pointer injection |

### Infrastructure / Fabric

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `plugin_supervisor.ts` | ~180 | GOOD | Orchestration backbone |
| `event_bus.ts` | ~175 | VIOLATION (V1) | Exports `globalEventBus` singleton |
| `layer_manager.ts` | ~159 | VIOLATION (V1) | Exports `globalLayerManager` singleton |
| `w3c_pointer_fabric.ts` | ~470 | VIOLATION (V4, V5) | No Plugin lifecycle; `window.innerWidth` hardcode |
| `kalman_filter.ts` | ~135 | GOOD | Cursor smoother |
| `temporal_rollup.ts` | ~147 | GOOD | Auto-tuning observability |
| `wood_grain_tuning.ts` | ~24 | GOOD | Privacy-safe profile |

### Demo / Bootstrap

| File | Lines | Status |
|------|-------|--------|
| `demo_video_golden.ts` | ~288 | ✅ GOLDEN MASTER — isolated from violations |
| `demo_2026-02-20.ts` | ~222 | VIOLATION (V2, V3) — god object monolith |

### Babylon / Physics

| File | Lines | Status |
|------|-------|--------|
| `babylon_physics.ts` | ~348 | ANTIPATTERN — wrong interface (B2) |
| `babylon_landmark_plugin.ts` | ~262 | ✅ — implements Plugin, not registered |

### Prediction / Personalization

| File | Lines | Status |
|------|-------|--------|
| `behavioral_predictive_layer.ts` | ~318 | ANTIPATTERN — main-thread GA (A1) |
| `behavioral_predictive_worker.ts` | ~125 | PARTIAL — exists, path broken |

---

## SOTA Confirmations (Do Not Refactor)

| # | Pattern | Where | Verdict |
|---|---------|-------|---------|
| S1 | Privacy-by-Math (Wood Grain) | `wood_grain_tuning.ts` → `UserTuningProfile` | ✅ CONFIRMED — Kalman covariances only, GDPR-compliant |
| S2 | Synthesized Synesthesia (Zero-Latency Click) | `audio_engine_plugin.ts` → `synthesizeClick()` | ✅ CONFIRMED — fires on exact FSM `COMMIT_POINTER` |
| S3 | Procedural Observability (Self-Writing ADRs) | `temporal_rollup.ts` | ✅ CONFIRMED — auto-tuning glass box |
| S4 | Physics-as-UI (Velocinertia Clamp) | `babylon_physics.ts` → Havok spring | ✅ CONFIRMED — cursor has mass, cannot teleport |

---

## Blocking Issues (6 Lethal Antipatterns)

| # | Name | File | Severity | Fix |
|---|------|------|----------|-----|
| A1 | Main-Thread GA Blocking | `behavioral_predictive_layer.ts` → `evolve()` | 🔴 Ship-blocker | Move GA to `BehavioralPredictiveWorker` |
| A2 | GC Churn Micro-Stutter | `simulatePrediction()` → `.push({})` in hot loop | 🟠 Perf-critical | Pre-allocate `Float32Array`, overwrite by index |
| A3 | Ground Truth Paradox | `bpl.evolve(noisyData, groundTruthData)` | 🟠 Perf-critical | Implement Shadow Tracker (Savitzky-Golay) |
| A4 | MAP-Elites Mirage | Docs claim MAP-Elites; code is standard GA | 🟡 Arch-debt | Rename to GA or implement 2D behavioral grid |
| A5 | Zombie Event Listener | `audio_engine_plugin.ts` → `init()` | 🔴 Ship-blocker | Store `boundOnStateChange`; unsubscribe in `destroy()` |
| A6 | Untrusted Gesture Audio Trap | `AudioContext.resume()` from `isTrusted=false` event | 🔴 Ship-blocker | UX "Tap to Calibrate" boot screen — cannot be fixed in code |

---

## Contract Violations (6 Microkernel Invariants — ALL RED)

Spec: `microkernel_arch_violations.spec.ts` (498 lines, ATDD immune system)

| ID | Name | Where | Fix |
|----|------|-------|-----|
| V1 | Global Singleton Contraband | `event_bus.ts:31`, `layer_manager.ts` | Delete `globalEventBus`/`globalLayerManager`; callers use `context.eventBus` |
| V2 | God-Object Phantom Refactor | `demo_2026-02-20.ts:~247-370` | Gut bootstrapper; register `MediaPipeVisionPlugin` |
| V3 | Double-Debounce | `demo_2026-02-20.ts` + `GestureFSMPlugin` | Remove bucket logic from demo |
| V4 | Rogue Agent (no Plugin lifecycle) | `w3c_pointer_fabric.ts` | Create `W3CPointerFabricPlugin` |
| V5 | PAL Leak (hardcoded `window.innerWidth`) | `w3c_pointer_fabric.ts:~95` | `ctx.pal.resolve<number>('ScreenWidth')` |
| V6 | Stub Implementations | ⚠️ UNVERIFIED | `grep -r "throw new Error.*not implemented" *.ts` |

**Repair order:** V1 → V4+V1 → V3 → V2 → V5/V6

---

## Test Coverage

| Suite | Status |
|-------|--------|
| Golden Master (`golden_master_test.mjs`) | ✅ PASS |
| build:golden | ✅ PASS |
| Arch Violations (`microkernel_arch_violations.spec.ts`) | 6× 🔴 RED |
| All other specs | ⚠️ UNVERIFIED |
| Stryker mutation | ⚠️ Report on disk, result not read in audit |

---

## Audit Disposition

| Dimension | Verdict |
|-----------|---------|
| Can this ship? | **NO** — 6 contract violations unresolved |
| Is the architecture sound? | **YES** — microkernel contract is correct |
| Is the golden master valid? | **YES** — `demo_video_golden.ts` isolated from violations |
| Is the MVP scope clear? | **YES** — 3 Pillars, 5 Core Pieces, 5 Gherkin scenarios |
| Critical path | Fix V1 → compiler errors drive V2–V5 → wire CP1–CP4 end-to-end |
| Highest risk | A6 — cannot be fixed in code; requires UX decision |

---

*Bronze medallion. Source: Gen89 session a1e8d5e9dfc4b271, binding minimus issued 2026-02-20.*
