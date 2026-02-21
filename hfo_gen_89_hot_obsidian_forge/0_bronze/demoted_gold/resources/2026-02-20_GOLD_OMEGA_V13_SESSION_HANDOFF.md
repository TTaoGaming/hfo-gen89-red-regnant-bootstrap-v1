---
schema_id: hfo.gen89.gold.reference.v1
medallion_layer: gold
doc_type: reference
port: P7
tags: handoff, omega_v13, npu, gpu, daemon_fleet, resource_governance, session_state
bluf: "2026-02-20 end-of-day handoff. Omega v13 Layered Compositor is building and serving. Devourer D1 format=json fix landed. NPU LLM models downloaded. Resource governance write-path fixed. Key open items: NPU LLM daemon, Stryker CPU budget, Playwright test run."
created: 2026-02-20T17:00:00Z
operator: TTAO
---

# Gen89 Session Handoff — 2026-02-20 (Gold Reference)

> **Next agent: read this first.** Sourced from live stigmergy trail (event ~15920+), terminal context, and build outputs.

---

## 1. Build State (Omega v13 Microkernel)

| File | Status |
|------|--------|
| `demo_2026-02-20.ts` | **BUILDS CLEAN** — `dist/demo2.js` 250.4 KB via esbuild ESM chrome120 |
| `demo.ts` (legacy) | Builds to `exemplars/bundle.js` — overscan + 15 FPS throttle + skeleton hand applied |
| `tldraw_layer.html` | Complete — symbiote agent receives `SYNTHETIC_POINTER_EVENT` postMessages |
| `visualization_plugin.ts` | Updated — white skeleton hand with bone connections; overscan-mapped coordinates |

### Active entry point
`index_demo2.html` → loads `dist/demo2.js` (ESM)

**Confirmed working stack:**
- z=0: `<video>` camera, mirrored, full-viewport
- z=10: Babylon.js canvas (physics dots, lazy-loaded)
- z=20: `<iframe src="tldraw_layer.html">` at 80% opacity, transparent background
- z=30: Config Mosaic panel (overscan slider, debug toggles)
- z=40: Visualization div — white 21-landmark skeleton hand

### W3C Pointer Fabric wiring
```
MediaPipe → FRAME_PROCESSED → GestureFSMPlugin
GestureFSMPlugin → POINTER_UPDATE → W3CPointerFabric → postMessage → tldraw_layer.html
GestureFSMPlugin → POINTER_UPDATE → VisualizationPlugin → skeleton hand
GestureFSMPlugin → STATE_CHANGE  → AudioEnginePlugin → click sound
FRAME_PROCESSED  → BabylonAdapter → 21-dot physics
```

---

## 2. Daemon Fleet Status

| Daemon | Port | Status | Notes |
|--------|------|--------|-------|
| P6 Devourer v2.0 | P6 | Running (background) | D1 `format=json` fix landed; progressive_summary coverage was 0.2% before fix |
| P5 GitOps | P5 | Created | Stash/pop around git pull exists; **fails when sqlite locked by Devourer** |
| P7 GPU/NPU Anchor | P7 | Fixed | `write_event` → `write_stigmergy_event` fix applied |
| Resource Governor | — | Fixed | `_write_gov_event` → `write_stigmergy_event` fix applied |
| Fleet Manager | — | Nuked + idle | `hfo_daemon_fleet.py --nuke` was run |

### Critical: GitOps + Devourer conflict
`git pull --rebase` fails when Devourer holds a write lock on `hfo_gen89_ssot.sqlite`.
**Workaround:** Stop Devourer before running GitOps pull:
```bash
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_daemon_fleet.py --nuke
git pull --rebase
# then restart Devourer
```

---

## 3. NPU / GPU Resource State

### NPU LLM Models (downloaded to `.hfo_models/npu_llm/`)
| Model | Size | Status |
|-------|------|--------|
| `FluidInference/qwen3-1.7b-int4-ov-npu` | ~1 GB | Downloaded ✓ |
| `FluidInference/qwen3-4b-int4-ov-npu` | ~2.5 GB | Downloaded ✓ |

**NPU usage:** Embeddings 100% (9866/9866 docs via all-MiniLM-L6-v2 ONNX).
**LLM inference NOT YET active on NPU.** Build `hfo_npu_llm_daemon.py` using `optimum-intel` + OpenVINO.

### GPU State (at handoff)
- VRAM: 8.6 / 15 GB (57%)
- Loaded: `gemma3:4b` (4.0 GB) + `qwen2.5-coder:7b` (4.6 GB)
- Target: 80% VRAM — load `phi4:14b` (8.4 GB) replacing `qwen2.5-coder:7b` when Stryker not running

### CPU Warning
At handoff CPU was near 100% due to Devourer + embed loop + Stryker competing.
**Fix:** Set `HFO_GOV_CPU_OVER=65` in `.env` to trigger daemon yield at 65% CPU:
```bash
# .env addition:
HFO_GOV_CPU_OVER=65
```

---

## 4. Resource Governance Fixes Applied (This Session)

All three files now use the canonical `write_stigmergy_event` + `build_signal_metadata` API:

1. **`hfo_resource_governance.py`** — replaced `_write_gov_event` internal method with `write_stigmergy_event` from `hfo_ssot_write`. Fixes `STRUCTURAL_GATE` error.
2. **`hfo_p7_gpu_npu_anchor.py`** — replaced `write_event(conn, ...)` with `write_stigmergy_event(...)`. Fixes `SSOT write failed` error.
3. **`hfo_p6_devourer_daemon.py`** — added `response_format=json` (→ `format=json`) to Ollama API call in `run_d1_discover`. Fixes empty `progressive_summary` L2/L3 fields.

---

## 5. Omega v13 Visual Stack Fixes (This Session)

Applied to `demo.ts` (legacy bundle) in response to user bug report:

| Fix | Location |
|-----|----------|
| Remove foveated cropping | `demo.ts` — `HandLandmarker` options simplified |
| 15 FPS throttle | `demo.ts` — `PROCESS_INTERVAL_MS = 1000/15` guard in `predictWebcam` |
| Overscan coordinate mapping | `demo.ts` + `visualization_plugin.ts` — `offset = (1 - 1/scale) / 2` formula |
| White skeleton hand | `visualization_plugin.ts` — bone connection lines + white dots |
| Config panel + overscan slider | `exemplars/host.html` — `<input type="range">` updates `window.omegaOverscanScale` |
| Bundle path fix | `exemplars/host.html` — `src="bundle.js"` (was `../dist/demo.js`) |

---

## 6. Open Work Queue (Prioritized)

1. **[P1 CRITICAL] NPU LLM daemon** — `hfo_npu_llm_daemon.py` using `OVModelForCausalLM` from `optimum-intel`. Route Devourer summarization tasks to NPU `qwen3-1.7b-int4-ov-npu`. Target: ~80% NPU utilization.
2. **[P2 HIGH] Set `HFO_GOV_CPU_OVER=65`** in `.env` to protect Stryker headroom.
3. **[P3 HIGH] Stryker mutation testing** — run `stryker.config.json` (installed in omega_v13_microkernel). Needs CPU headroom.
4. **[P4 MEDIUM] Playwright test suite** — `npx playwright test` exits 1. Fix test server setup in `playwright.config.ts`.
5. **[P5 MEDIUM] GitOps + Devourer conflict** — implement advisory lock or daemon pause signal before GitOps pull.
6. **[P6 MEDIUM] Promote Devourer fix to silver/gold** — `hfo_p6_devourer_daemon.py` changes are in bronze; verify progressive_summary coverage rising before promoting.
7. **[P7 LOW] tldraw bundle** — `dist/tldraw_bundle.js` may need rebuild from `tldraw_entrypoint.tsx` via `npx esbuild tldraw_entrypoint.tsx --bundle --outfile=dist/tldraw_bundle.js --format=iife --platform=browser --target=chrome120`.

---

## 7. Stigmergy Breadcrumbs

| Event ID | Type | Summary |
|----------|------|---------|
| 15907 | `hfo.gen89.prey8.yield` | Nonce F95388: D1 format=json fix + handoff state doc V1 |
| 15924 | `hfo.gen89.prey8.react` | Nonce CE0C8F: Current session — gitops stash fix + this doc |
| ~15890 | `hfo.gen89.p7.handoff.session` | Full resource governance handoff, NPU downloads, Stryker headroom, next priorities |
| ~15329 | `hfo.gen89.prey8.yield` | Nonce 4D20DA: Leaky bucket + palm width gesture detection |

---

## 8. Key File Paths (PAL — use pointers, not hardcoded paths)

```bash
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_pointers.py list
```

| Pointer Key | Target |
|-------------|--------|
| `ssot.db` | `2_gold/resources/hfo_gen89_ssot.sqlite` |
| `prey8.perceive` | `0_bronze/resources/hfo_perceive.py` |
| `prey8.yield` | `0_bronze/resources/hfo_yield.py` |

---

## 9. Quick Start for Next Agent

```bash
# 1. Activate venv
.venv\Scripts\Activate.ps1

# 2. Verify pointers
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_pointers.py check

# 3. Check CPU — if >80%, pause Devourer first
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_resource_governor.py status

# 4. PREY8 perceive
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_perceive.py \
  --probe "your task here"

# 5. Build Omega v13 demo
cd hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel
npx esbuild demo_2026-02-20.ts --bundle --outfile=dist/demo2.js \
  --format=esm --platform=browser --target=chrome120 --external:./babylon_physics

# 6. Serve and test
npx http-server . -p 5173
# Open http://localhost:5173/index_demo2.html
```

---

*Authored by P4 Red Regnant (MCP v4.0) — 2026-02-20 end-of-day session handoff.*
*SSOT doc count: 9868 | Stigmergy events: ~15930+ | Medallion: gold*
