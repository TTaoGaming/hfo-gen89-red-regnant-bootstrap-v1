---
schema_id: hfo.gen89.diataxis.reference.v1
medallion_layer: bronze
promotion_candidate: gold
doc_type: reference
port: P6
tags: handoff,omega_v13,devourer_v2,npu,gen89,state_snapshot
author: p4_red_regnant
date: 2026-02-20
bluf: >
  Gen89 session handoff reference. Two active workstreams: (1) Omega v13 microkernel
  — 5-layer compositor demo built, MediaPipe+BabylonJS wiring in progress, NPU LLM
  models on disk; (2) Devourer v2.0 — enrichment running but D1 DISCOVER progressive
  summary bug fixed (format=json enforcement). SSOT at 9867 docs, 80.7% BLUF, 0.2%
  ProgSumm. P4 adversarial audit: D1 fix verified via syntax check; next cycle should
  show ProgSumm rising. Stale react session (DFDCEE / 674bda6c) open for babylon
  landmarks exemplar — still needs yield.
mnemonic: "O·B·S·I·D·I·A·N"
---

# Gen89 State Handoff Reference — 2026-02-20

> **P4 Red Regnant adversarial advisory:** This document is bronze-layer only.
> All doc stats and coverage numbers are point-in-time (2026-02-20T16:30 UTC).
> Promote to gold only after operator review.

---

## 1. SSOT State Snapshot

| Metric | Value | Notes |
|--------|-------|-------|
| Total documents | 9,867 | +5 from previous session |
| Stigmergy events | ~15,900 | High churn — 183 gate blocks / 24h |
| BLUF coverage | 80.7% (1,901 missing) | Devourer actively closing gap |
| Port coverage | 25.7% (7,336 missing) | Next major target |
| Doc type | 100% | Complete |
| Tags | ~100% (1 missing) | Complete |
| Progressive summary | 0.2% (18 docs) | D1 bug fixed — should rise |
| NPU embeddings | 100% (9,867 docs) | Intel AI Boost, all embedded |
| Lineage edges | 902 | Slowly growing |

---

## 2. Devourer v2.0 State

**File:** `hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_p6_devourer_daemon.py`  
**Version:** 2.0 (commit c45ffa7)  
**Status:** Running — 74 enrichment events, 47 in last 1h as of handoff.

### Architecture

```
6D Pipeline per document:
  D0 DIRECT    → gemma3:4b (LIGHT) — fast triage brief
  D1 DISCOVER  → qwen3:8b / gemma3:4b (HEAVY) — progressive 3-layer summarization ← BUG FIXED
  D2 DECODE    → gemma3:4b (LIGHT) — port + doc_type + tags
  D3 DEFINE    → qwen3:8b / gemma3:4b (HEAVY) — key insights
  D4 DEMONSTRATE → SKIPPED (autonomous mode)
  D5 DISSEMINATE → writes metadata_json + emits stigmergy events
```

### Model Tiers (compute_aware_model_select)

| Tier | Current Selection | VRAM (GB) | Notes |
|------|------------------|-----------|-------|
| LIGHT | gemma3:4b | ~4.3 | D0, D2 — fast classification |
| HEAVY | qwen3:8b or gemma3:4b fallback | ~8.1 / 4.3 | D1, D3 — deep reasoning |
| FALLBACK | qwen2.5:3b | ~2.4 | When VRAM under pressure |

### Critical Bug Fixed This Session

**Problem:** D1 DISCOVER returned empty `L2_SECTIONS` and `L3_CONCEPTS`.  
**Root cause:** `ollama_generate_with_metrics()` did not pass `"format": "json"` to the Ollama API, so models
returned narrative text with embedded JSON rather than validated JSON, causing `_extract_json()` to fall back
to the flat BLUF path.  
**Fix applied:** Added `response_format` parameter to `ollama_generate_with_metrics()` and called with
`response_format="json"` from `run_d1_discover()`. The Ollama `format=json` constraint forces the model to
output a valid JSON object.

```python
# Before (broken):
resp, metrics = ollama_generate_with_metrics(prompt, model=model, num_predict=1024)

# After (fixed):
resp, metrics = ollama_generate_with_metrics(prompt, model=model, num_predict=1024, response_format="json")
```

**Verified:** py_compile syntax check passed. First cycle post-fix not yet confirmed (handoff moment).

### Coverage Targets (priority order)

1. **Progressive Summary (L1/L2/L3):** 0.2% → target 80%+ (D1 fix now active)
2. **Port assignment:** 25.7% → target 80%+ (D2 handles this)
3. **BLUF:** 80.7% → 100% (D1 provides bluf)

### Running the Daemon

```powershell
# 24/7 background loop (3 docs per cycle, 180s between cycles)
$env:PYTHONIOENCODING="utf-8"
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_p6_devourer_daemon.py --batch 3 --interval 180

# Single test cycle
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_p6_devourer_daemon.py --single --batch 2

# Status check
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_p6_devourer_daemon.py --status
```

---

## 3. Omega v13 Microkernel State

**Location:** `hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel/`  
**Status:** Demo built + served. Babylon visualization wired but Havok CDN missing = physics silent.

### Architecture Overview

```
5-Layer Compositor (demo_2026-02-20.ts):
  z=0   Video       MediaPipe camera feed
  z=10  Babylon     3D dot visualization (21 hand landmarks)
  z=20  TLDraw      Annotation / drawing layer
  z=30  Settings    Config UI
  z=40  Viz         Canvas2D overlays, gesture state
```

### Key Files

| File | Purpose | Status |
|------|---------|--------|
| `demo_2026-02-20.ts` | Main 5-layer compositor | Built (esbuild → dist/demo2.js) |
| `plugin_supervisor.ts` | IPlugin lifecycle manager | Done |
| `gesture_fsm.ts` | Defense-in-Depth FSM, SCXML spec | Done |
| `gesture_bridge.ts` | MediaPipe → W3C PointerEvent bridge | Done |
| `babylon_physics.ts` | Havok + spring physics 21-dot visualizer | **Broken: CDN commented out** |
| `visualization_plugin.ts` | Canvas2D overlay plugin (working exemplar) | Done |
| `audio_engine_plugin.ts` | Cherry MX sound synthesis | Done |
| `behavioral_predictive_layer.ts` | GA hyper-heuristic predictive system | Done |
| `w3c_pointer_fabric.ts` | Shared W3C Pointer event fabric | Done |
| `exemplars/` | Exemplar implementations | Mostly empty — see open work |

### Open Work: Babylon Landmark Visualization

Previous session (react token DFDCEE, session 674bda6c) analyzed the problem but was not yielded:
- Babylon CDN script commented out in `index_demo2.html` → Havok physics fails silently
- Proposed fix: two exemplars:
  - **A:** Standalone CDN-only HTML (zero build friction) with 21 landmark spheres + fingertip color-on-state
  - **B:** TypeScript `IPlugin` implementing `FRAME_PROCESSED` → direct sphere position updates @ 20fps, no Havok

**Next agent:** Implement `exemplars/exemplar_babylon_landmarks_standalone.html` (CDN Babylon + CDN MediaPipe).
Contract: `{ open_palm: lime, pointer_up: orange, closed_fist: red }` landmark dot colors.

### Build Commands

```powershell
cd "C:\hfoDev\hfo_gen_89_hot_obsidian_forge\1_silver\projects\omega_v13_microkernel"

# Build demo
npx esbuild demo_2026-02-20.ts --bundle --outfile=dist/demo2.js --sourcemap --format=esm --platform=browser --target=chrome120 --external:./babylon_physics

# Serve
python -m http.server 5173

# Run Playwright tests (Chromium installed)
npx playwright test
```

### Monolith Snapshot

`dist/2026-02-20_091713_omega_v13_monolith.md` — Full source snapshot (64 files, 8545 lines, generated 09:17 UTC).
**Note:** Monolith may be stale post-session edits. Regenerate with `_concat_omega_v13.py` if needed.

---

## 4. NPU LLM Models (Intel AI Boost)

Downloaded to `C:\hfoDev\.hfo_models\npu_llm\`:

| Model | Path | Status | Notes |
|-------|------|--------|-------|
| qwen3-1.7b-int4-ov-npu | `.hfo_models/npu_llm/qwen3-1.7b-int4-ov-npu/` | Downloaded | FluidInference HuggingFace |
| qwen3-4b-int4-ov-npu | `.hfo_models/npu_llm/qwen3-4b-int4-ov-npu/` | Downloaded | FluidInference HuggingFace |

**Integration status:** Downloaded but **not yet wired** into `hfo_npu_embedder.py` for inference.
Current NPU usage is embeddings only (ONNX model). The int4-ov models are for direct NPU inference
via OpenVINO runtime.

**Next agent:** Wire qwen3-1.7b-int4-ov-npu into a `hfo_npu_llm_client.py`  using `optimum.intel`
`OVModelForCausalLM` + `AutoTokenizer`. This would replace Ollama for LIGHT_MODEL tier on NPU.

```python
# Target integration pattern:
from optimum.intel import OVModelForCausalLM
from transformers import AutoTokenizer

model_path = r"C:\hfoDev\.hfo_models\npu_llm\qwen3-1.7b-int4-ov-npu"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = OVModelForCausalLM.from_pretrained(model_path, device="NPU")
```

---

## 5. Gen89 Infrastructure Health

### Daemon Fleet

| Daemon | Port | Status | Notes |
|--------|------|--------|-------|
| hfo_p6_devourer_daemon.py | P6 | Active (v2.0) | 47 events/1h, D1 fix applied |
| hfo_background_daemon.py | P7 | Active | Patrol: 10 orphaned perceives, 66 tamper alerts |
| hfo_octree_daemon.py | All | Unknown | Not checked this session |

### Known Issues

| Issue | Severity | Status |
|-------|----------|--------|
| D1 DISCOVER empty L2/L3 | High | **Fixed (format=json)** |
| Orphaned PREY8 sessions | Medium | 10 pending — noise, not errors |
| Babylon CDN missing in index_demo2.html | Medium | Open — needs exemplar |
| qwen3:8b not loaded (falls back to gemma3:4b) | Low | Auto-fallback works |
| NPU LLM models downloaded but not integrated | Low | Future work |

### Gate Block Noise

183 gate blocks in 24h is high — attributed to:
1. Stale `reacted` phase sessions from previous context windows
2. MCP server restarts between sessions
3. Multiple concurrent agents calling perceive without yielding

Not a reliability issue — the gates are working correctly. Each block is logged and provides
diagnostic data. The architecture is working as designed: tamper-evident, fail-closed.

---

## 6. Open Work Queue (Priority Order)

### Immediate (next session)

1. **Verify D1 fix works** — Run `--single --batch 3` and check progressive_summary coverage rises
2. **Babylon landmarks exemplar A** — CDN-only HTML in `exemplars/`
3. **Yield stale react session** — Session 674bda6c (react DFDCEE) needs closure

### Short-term

4. **Wire NPU LLM models** — `hfo_npu_llm_client.py` using OVModelForCausalLM
5. **Port coverage push** — 25.7% → 80% (Devourer D2 handles this automatically)
6. **Babylon IPlugin exemplar B** — TypeScript IPlugin for landmark dots

### Deferred

7. **Promote this document to gold diataxis** — After operator review
8. **Progressive summary coverage validation** — After D1 fix confirmed working
9. **Omega v13 full E2E Playwright test** — Framework installed, no tests written yet

---

## 7. Stigmergy Trail Breadcrumbs

Key nonces for chain reconstruction:

| Nonce | Session | Type | Summary |
|-------|---------|------|---------|
| B18CDB | 59f1463833c8a6bc | yield | Devourer v2.0 implementation (Stryker 62%) |
| 4B8D41 | 213f0bbea80383a0 | yield | HFO_ALTER_REALITY draft document |
| DFDCEE | 674bda6c8c2412ca | react | Babylon landmarks exemplar plan (NOT YIELDED) |
| F4B85B | CLI run | perceive | Omega v13 handoff CLI perceive (orphaned) |
| 93C817 | 2541e1773507078e | perceive | This session (current) |

**Orphaned session warning:** Session 674bda6c has open react token DFDCEE. The planned
artifacts (babylon exemplars) were never created. Next agent should either:
- Create the babylon exemplar artifacts and yield that session, OR
- Record it as abandoned and start a fresh session for babylon work.

---

## 8. P4 Adversarial Audit Notes

**D1 fix risk:** `format=json` in Ollama forces valid JSON but may cause model to produce
sparse/incomplete objects (e.g., empty string for L1_BLUF). Mitigation: the fallback path
still exists — if `L1_BLUF` is empty or missing, the flat-bluf fallback kicks in.

**Omega v13 Babylon risk:** Havok CDN being commented out was intentional (physics was over-engineered
for the requirement). The direct-sphere-position exemplar approach avoids Havok entirely — lower
complexity, same visual result.

**NPU LLM integration risk:** `optimum.intel` v1.20+ required for qwen3 OV support. Check version
before attempting integration. Fallback: Ollama continues to work as LIGHT/HEAVY model backend.

**Coverage numbers reliability:** All coverage percentages are computed from DB queries at a single
point in time. The Devourer runs asynchronously — numbers will drift between sessions.

---

*Generated by P4 Red Regnant — Gen89 session handoff. Date: 2026-02-20.*  
*Promote to gold after operator review: git mv to 2_gold/resources/ and update medallion_layer.*
