---
schema_id: hfo.gen90.omega_v15.audit_manifest.v1
medallion_layer: bronze
doc_type: reference
port: P5
bluf: "Omega v15 microkernel production audit manifest — tile-by-tile Stryker scores, test counts, known defects, and audit readiness gate."
updated: 2026-02-21
operator: TTAO
agent: p7_spider_sovereign
---

# Omega v15 Microkernel — Production Audit Manifest

> **Bronze medallion.** All claims are supported by evidence in this document.
> For external auditors: each tile's test file, Stryker score, and open issues are listed below.
> Status: **ALL 5 PRIMARY TILES AT GOLDILOCKS (80–99%)** — 2026-02-21. Audit gate open pending DEFECT-001 resolution.

---

## Quick Summary

| Tile | Jest Tests | Stryker % | Status | SBE Gate |
|------|-----------|-----------|--------|----------|
| `event_bus.ts` | ✅ (test_event_bus.test.ts) | **84.31%** ✅ | Goldilocks | — |
| `kalman_filter.ts` | ✅ (test_kalman_filter.test.ts) | **95.08%** ✅ | Goldilocks | — |
| `plugin_supervisor.ts` | **51** (test_plugin_supervisor.ts) | **85.85%** ✅ | Goldilocks | sbe_plugin_supervisor.py ✅ |
| `audio_engine_plugin.ts` | **104** (test_audio_engine_plugin.ts) | **88.89%** ✅ | Goldilocks | sbe_audio_engine.py ✅ |
| `symbiote_injector_plugin.ts` | **24** (test_symbiote_injector_plugin.ts) | **87.76%** ✅ | Goldilocks | sbe_symbiote_injector_plugin.py ✅ |

**Total active Jest tests across hardened tiles: 242 (6 suites, all passing 2026-02-21)**

---

## Stryker Configuration

**File:** `stryker.config.json`

```json
{
  "mutate": [
    "plugin_supervisor.ts",
    "audio_engine_plugin.ts",
    "symbiote_injector_plugin.ts"
  ],
  "thresholds": { "high": 90, "low": 80, "break": 75 }
}
```

**Goldilocks zone: 80–99%.** Score below 75% breaks the build.  
`event_bus.ts` and `kalman_filter.ts` were hardened in prior sessions (separate Stryker runs, scores extracted from reports).

---

## Tile Details

### Tile 1: `event_bus.ts` ✅
- **Stryker:** 84.31% (hardened session ~2026-02-19)
- **Test file:** `test_event_bus.test.ts`
- **Notes:** Publish/subscribe/unsubscribe invariants. Goldilocks confirmed.

### Tile 2: `kalman_filter.ts` ✅
- **Stryker:** 95.08% (hardened session ~2026-02-19)
- **Test file:** `test_kalman_filter.test.ts`
- **Notes:** Highest-scoring tile. Arithmetic mutation kills confirmed.

### Tile 3: `plugin_supervisor.ts` ✅
- **Stryker:** 85.85% (session stigmergy `C496AB`, 2026-02-21)
- **Test file:** `test_plugin_supervisor.ts` — 51 tests, @jest/globals
- **SBE wrapper:** `../../2_resources/sbe_plugin_supervisor.py` — 1 passed
- **Reports:** `stryker_plugin_supervisor_goldilocks.txt`, `stryker_plugin_supervisor_final.txt`
- **Notes:** Rewritten from node:test to @jest/globals. Full lifecycle FSM coverage.
  MockPlugin uses `receivedContext`/`shouldThrowOnInit`/`shouldThrowOnDestroy` flags.

### Tile 4: `audio_engine_plugin.ts` ✅
- **Stryker:** **88.89%** (R2 2026-02-21) — 138 killed, 6 timed out, 16 survived, 2 no-coverage / 162 total
- **Test file:** `test_audio_engine_plugin.ts` — **104 tests** (expanded from 21)
- **SBE wrapper:** `../../2_resources/sbe_audio_engine.py` — threshold ≥90 tests ✅
- **Coverage targets:** T-OMEGA-005 through T-OMEGA-016
  - T-005: Zombie fix (AudioContext not created at import time)
  - T-006: Deferred context init (first synthesizeClick creates ctx)
  - T-007: `onStateChange` callback — all branches
  - T-008: Null guard when ctx not created
  - T-009: Suspended AudioContext resumed before play
  - T-010: Buffer dimensions (1 channel, sampleRate, bufferDown vs bufferUp)
  - T-011: Identity properties (`name`, `version`)
  - T-012: `start()`/`stop()` console.log spy
  - T-013: `destroy()` before-init + `close()` verification
  - T-014: Cherry MX DSP arithmetic precision (data[1]/data[468]/data[684] at r=0.5 and r=0 noise)
  - T-015: PAL null guard — `AudioContextCtor` missing → `console.warn` called
  - T-016: `playSound` suspended-state/null-buffer/negative-state-transition guards
- **Survivors (16):** Mostly `> vs >=` boundary comparisons in DSP synthesis and console.log StringLiterals in
  AudioContext unlock path. Score well within Goldilocks; no audit-blocking gaps.
- **Critical note:** `audio_engine_plugin.spec.ts` exists but is INVISIBLE to Jest
  (`testPathIgnorePatterns: ["\\.spec\\.ts$"]`). `test_audio_engine_plugin.ts` is the real harness.

### Tile 5: `symbiote_injector_plugin.ts` ✅
- **Stryker:** **87.76%** (R1 2026-02-21) — 43 killed, 0 timed out, 4 survived, 2 no-coverage / 49 total
- **Test file:** `test_symbiote_injector_plugin.ts` — 317 lines, **24 tests**
- **SBE wrapper:** `../../2_resources/sbe_symbiote_injector_plugin.py` — threshold ≥24 tests ✅
- **Coverage targets:** T-OMEGA-SYM-001 through T-OMEGA-SYM-007
  - SYM-001: `boundOnPointerUpdate` stable ref (zombie fix)
  - SYM-002: `init()`/`stop()`/`destroy()` subscription lifecycle
  - SYM-003: isPinching FSM (false→move, false→true→down, true→false→up, true→true→move)
  - SYM-004: `screenX = x * screenWidth` arithmetic kills
  - SYM-005: PAL ScreenWidth/Height resolution (number vs callable)
  - SYM-006: `DispatchEvent` absent → safe no-op
  - SYM-007: `isPinchingMap` cleared on `destroy()`

### Tile 6: `gesture_fsm_plugin.ts` ❌ BLOCKED
- **Stryker:** NOT POSSIBLE without special config (WASM dependency on `gesture_fsm_rs_adapter.ts`)
- **Test file:** `gesture_fsm_plugin.spec.ts` (invisible to standard Jest due to `.spec.ts` exclusion)
- **Blocker:** SCXML/WASM adapter requires mock injection not yet implemented for Stryker sandbox

---

## Additional Tiles Required (Audit Gaps)

> Full analysis in `OMEGA_V13_V15_COMPARISON.md`. Summary of tiles with zero test coverage:

### 🔴 Priority 1 — Ship Blockers

| Tile | Lines | Gap |
|------|-------|-----|
| `shell.ts` | 778 | Plugin registry completeness; DEFECT-001 lives here |
| `w3c_pointer_fabric.ts` | 470 | V4+V5 violations from v13 — no test coverage confirming resolution |
| `gesture_fsm.ts` | 265 | Core FSM (test file exists but not in Stryker run yet) |

### 🟠 Priority 2 — High Value

| Tile | Lines | Gap |
|------|-------|-----|
| `behavioral_predictive_layer.ts` | 318 | A1 (main-thread GA) from v13 likely still present |
| `visualization_plugin.ts` | 249 | No tests |
| `mediapipe_vision_plugin.ts` | 391 | No tests |
| `iframe_delivery_adapter.ts` | 127 | No tests |

### 🟡 Priority 3 — Achievable Wins (<3h each)

`stillness_monitor_plugin.ts` (91), `hud_plugin.ts` (79), `highlander_mutex_adapter.ts` (112), `temporal_rollup.ts` (147), `wood_grain_tuning.ts` (24)

### ❌ Blocked

`gesture_fsm_plugin.ts`, `babylon_physics.ts`, `babylon_landmark_plugin.ts` — all require WASM mock injection

---

## Known Defects for Audit

### DEFECT-001: SymbioteInjectorPlugin Potemkin Village ⚠️ HIGH
- **File:** `shell.ts`
- **Issue:** `SymbioteInjectorPlugin` is NOT registered in `shell.ts` loadedPlugins/instantiation path.
  Unit tests (`test_symbiote_injector_plugin.ts`) test the class in isolation, but the plugin is never
  actually loaded in the running microkernel.
- **Impact:** Integration coverage gap. The symbiote gesture-to-pointer translation is architecturally
  present but functionally absent in the live shell.
- **Fix:** Add `SymbioteInjectorPlugin` to `shell.ts` plugin registry.

### DEFECT-002: Dead Test File `.spec.ts` Exclusion Trap ⚠️ MEDIUM
- **Files affected:** `audio_engine_plugin.spec.ts`, `gesture_fsm_plugin.spec.ts`,
  `symbiote_injector.spec.ts`, and others
- **Issue:** `jest.config.js` has `testPathIgnorePatterns: ["\\.spec\\.ts$"]` — ALL `.spec.ts`
  files in the project are silently ignored by both Jest and Stryker.
- **Impact:** Spec files appear to exist but produce zero test coverage. Easy to mistake for coverage.
- **Fix:** Either remove the pattern and rename `.spec.ts` files to `.test.ts`, OR document the
  `test_*.ts` convention clearly and delete/archive the dead spec files.

### DEFECT-003: `gesture_fsm_plugin.ts` Stryker Blocked ⚠️ MEDIUM
- **Issue:** The WASM-based `gesture_fsm_rs_adapter.ts` cannot be mocked in the Stryker sandbox
  without custom config.
- **Impact:** gesture FSM tile has no mutation score.
- **Fix:** Add `jest.mock('./gesture_fsm_rs_adapter')` stub in Stryker jest config, or use
  `--ignoreStatic` on the adapter file.

### DEFECT-004: stryker.config.json Timeout Risk ⚠️ LOW
- **Issue:** `timeoutMS: 10000` may be tight for AudioContext synthesis tests.
  Prior Stryker runs saw occasional timeouts on plugin_supervisor.
- **Impact:** Spurious "timed out" survivors inflate the mutant-killed denominator.
- **Fix:** Increase to `timeoutMS: 15000` for the audio tile.

---

## Audit Readiness Checklist

| Item | Status |
|------|--------|
| All Jest tests passing (242/242) | ✅ 2026-02-21 |
| `event_bus.ts` Stryker ≥ 80% | ✅ 84.31% |
| `kalman_filter.ts` Stryker ≥ 80% | ✅ 95.08% |
| `plugin_supervisor.ts` Stryker ≥ 80% | ✅ 85.85% |
| `audio_engine_plugin.ts` Stryker ≥ 80% | ✅ 88.89% (R2 2026-02-21) |
| `symbiote_injector_plugin.ts` Stryker ≥ 80% | ✅ 87.76% (R1 2026-02-21) |
| SBE wrapper: plugin_supervisor | ✅ 1 passed |
| SBE wrapper: audio_engine | ✅ 1 passed |
| SBE wrapper: symbiote_injector | ✅ 1 passed |
| DEFECT-001 (Potemkin Village) resolved | ❌ Open |
| DEFECT-002 (.spec.ts trap) documented | ✅ Documented |
| DEFECT-003 (gesture_fsm WASM) has mitigation | ❌ Open |
| PREY8 stigmergy chain intact | ✅ Session fb009e7661b5f640 yield A77E28 |

**Audit gate opens when:** All 5 primary tiles ≥ 80% Stryker AND DEFECT-001 resolved.

> **2026-02-21:** All 5 tiles now at Goldilocks. DEFECT-001 remains the sole blocking item.

---

## File Inventory

```
HFO_OMEGA_v15/
├── OMEGA_V15_AUDIT_MANIFEST.md          ← THIS FILE
├── stryker.config.json                  ← mutate: [plugin_supervisor, audio_engine, symbiote_injector]
├── jest.config.js                       ← testPathIgnorePatterns: [.spec.ts$]  ← TRAP documented above
├── jest.stryker.config.js               ← stryker-specific jest config
│
├── SOURCE TILES (primary audit targets)
│   ├── event_bus.ts                     ✅ 84.31% Stryker
│   ├── kalman_filter.ts                 ✅ 95.08% Stryker
│   ├── plugin_supervisor.ts             ✅ 85.85% Stryker
│   ├── audio_engine_plugin.ts           ✅ 88.89% Stryker (R2)
│   ├── symbiote_injector_plugin.ts      ✅ 87.76% Stryker (R1)
│   └── gesture_fsm_plugin.ts            ❌ WASM blocked
│
├── TEST HARNESSES (test_*.ts convention)
│   ├── test_event_bus.test.ts
│   ├── test_kalman_filter.test.ts
│   ├── test_plugin_supervisor.ts        ← 51 tests
│   ├── test_audio_engine_plugin.ts      ← 104 tests (T-OMEGA-001 to T-OMEGA-016) 2026-02-21
│   └── test_symbiote_injector_plugin.ts ← 24 tests (T-OMEGA-SYM-001 to SYM-007)
│
├── SBE WRAPPERS (in ../../../2_resources/)
│   ├── sbe_plugin_supervisor.py         ✅ 1 passed
│   ├── sbe_audio_engine.py              ✅ 1 passed (threshold ≥90)
│   └── sbe_symbiote_injector_plugin.py  ✅ 1 passed (threshold ≥24)
│
└── STRYKER REPORTS
    ├── stryker_plugin_supervisor_goldilocks.txt
    ├── stryker_run.txt / stryker_run2.txt
    └── stryker_all_tiles_2026-02-21.txt  ← in progress
```

---

## Session Trail (PREY8 stigmergy anchors)

| Session | Nonce | Achievement |
|---------|-------|-------------|
| fb009e7661b5f640 | A77E28 | test_audio_engine_plugin.ts (21 tests), sbe fixes |
| (current session) | — | audio_engine 88.89%, symbiote 87.76%, all 5 tiles Goldilocks, manifest updated |

| C496AB (prior) | — | plugin_supervisor.ts 85.85% Stryker |
| (prior) | — | event_bus.ts 84.31%, kalman_filter.ts 95.08% |

---

*Generated by p7_spider_sovereign — February 21, 2026 — Bronze medallion*
*Update this file after each Stryker run and defect resolution.*
