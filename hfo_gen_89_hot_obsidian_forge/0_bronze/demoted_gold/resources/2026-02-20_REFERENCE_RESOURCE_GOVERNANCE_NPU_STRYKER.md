---
schema_id: hfo.gen89.reference.v1
medallion_layer: gold
doc_type: reference
port: P6
title: Resource Governance, NPU Utilization & Stryker CPU Headroom
bluf: "Definitive reference for HFO Gen89 resource governance: env var mappings, NPU architecture, Stryker coexistence, daemon pause mechanism, and hardware targets."
tags: resource_governance,npu,gpu,stryker,cpu_headroom,daemon_fleet,p6_assimilate
date: 2026-02-20
author: copilot_handoff_session
stigmergy_ref: "hfo.gen89.p7.handoff.session:2026-02-20:resource_governance_npu_stryker (row 15916)"
---

# Resource Governance, NPU Utilization & Stryker CPU Headroom

Gen89 Reference | Port: P6 ASSIMILATE | 2026-02-20

---

## 1. Hardware Baseline

| Resource | Spec | Budget |
|---|---|---|
| CPU | Intel Core Ultra (8 cores) | 60% ceiling for daemons |
| RAM | 31.5 GB | ≥8 GB free target |
| GPU (VRAM) | Intel Arc 140V — 16 GB | 10 GB soft budget (`HFO_VRAM_BUDGET_GB=10`) |
| NPU | Intel AI Boost (AI Boost) | 100% via all-MiniLM-L6-v2 embeddings |

**GPU note:** Do NOT set `HFO_VRAM_BUDGET_GB` above 12.0. Previous sessions caused system crashes at 13+ GB on Meteor Lake shared memory architecture.

---

## 2. Resource Governance Architecture

Two separate systems manage resource pressure — they do NOT communicate automatically:

```
┌──────────────────────────────────────────────────────┐
│  hfo_resource_governance.py (OBSERVER/REPORTER)       │
│  → Watches sustained CPU/RAM/VRAM regimes            │
│  → Fires ADVISORY stigmergy events only              │
│  → Does NOT pause daemons directly                   │
└──────────────────────────────────────────────────────┘
                           │ advisory events
                           ▼
          stigmergy_events table (SSOT)

┌──────────────────────────────────────────────────────┐
│  hfo_resource_monitor.py (ENFORCER)                  │
│  → Checks CPU/RAM every SENSE_INTERVAL_S seconds    │
│  → Auto-pauses workers when CPU > HFO_CPU_THROTTLE  │
│  → Checks for hfo.gen89.resource.request events     │
│    (external yield requests, every YIELD_CHECK_INTERVAL) │
│  → Sets self._paused = True → workers wait on event │
└──────────────────────────────────────────────────────┘
```

To actually **pause daemons**, you must either:
1. Let CPU spike above `HFO_CPU_THROTTLE` threshold, OR
2. Emit `hfo.gen89.resource.request` to stigmergy (see §5)

---

## 3. Env Var Reference — Name Mismatches (CRITICAL)

The governance daemon and monitor use **different env var names** than the `.env` file previously defined. As of 2026-02-20 both are now aligned:

### hfo_resource_governance.py reads:

| Variable (what script reads) | Default | Purpose | `.env` value |
|---|---|---|---|
| `HFO_GOV_SAMPLE_INTERVAL` | 10 | Sample interval seconds | 10 |
| `HFO_GOV_WINDOW_SIZE` | 60 | Ring buffer size | 60 |
| `HFO_GOV_COOLDOWN` | 300 | Min seconds between same event | 300 |
| `HFO_GOV_HEARTBEAT` | 300 | Heartbeat interval seconds | 300 |
| `HFO_GOV_CPU_OVER` | 80 | Advisory overutilized threshold | **60** |
| `HFO_GOV_RAM_OVER` | 90 | RAM overutilized threshold | 82 |
| `HFO_GOV_CPU_UNDER` | 15 | CPU underutilized threshold | 10 |
| `HFO_GOV_RAM_UNDER` | 50 | RAM underutilized threshold | 50 |
| `HFO_GOV_REGIME_PCT` | 70 | % of window that must match | 70 |
| `HFO_VRAM_BUDGET_GB` | 12 | VRAM budget GB | 10 |

**Warning:** `.env` previously used `_PCT` and `_S` suffixes (`HFO_GOV_CPU_OVER_PCT`, `HFO_GOV_SAMPLE_INTERVAL_S`) that the script **does not read**. These were dead config. Fixed 2026-02-20.

### hfo_resource_monitor.py reads:

| Variable | Default | Purpose | `.env` value |
|---|---|---|---|
| `HFO_CPU_THROTTLE` | 85 | Pause workers above this CPU% | **60** |
| `HFO_CPU_RESUME` | 70 | Resume workers below this CPU% | **45** |
| `HFO_RAM_THROTTLE_GB` | 2 | Pause if free RAM < this GB | 4 |
| `HFO_RAM_RESUME_GB` | 4 | Resume if free RAM > this GB | 6 |
| `HFO_VRAM_BUDGET_GB` | 12 | Max VRAM for swarm | 10 |
| `HFO_VRAM_RESERVE_GB` | 2 | Keep free for other agents | 2 |
| `HFO_SENSE_INTERVAL` | 5 | Resource sense interval seconds | — |
| `HFO_YIELD_CHECK` | 15 | How often to check for yield requests | — |

**Note:** `.env` previously had `HFO_CPU_THROTTLE_PCT=75` — script reads `HFO_CPU_THROTTLE` (no `_PCT`). Fixed 2026-02-20.

---

## 4. NPU Utilization

### Current state (2026-02-20)

| Layer | Tool | Status | Docs/sec |
|---|---|---|---|
| Embeddings | `hfo_npu_embedder.py` (all-MiniLM-L6-v2 ONNX) | ✓ 100% (9866/9866) | ~83 |
| LLM inference | OpenVINO GenAI | ✓ Models downloaded, **not yet wired** | — |

### Downloaded NPU LLM models

Located at `C:\hfoDev\.hfo_models\npu_llm\`:
- `qwen3-1.7b-int4-ov-npu` — FluidInference/qwen3-1.7b-int4-ov-npu (HuggingFace)
- `qwen3-4b-int4-ov-npu` — FluidInference/qwen3-4b-int4-ov-npu (HuggingFace)

These are INT4 OpenVINO-optimized models **specifically compiled for Intel AI Boost NPU**. They run inference without touching GPU VRAM.

### Next step: hfo_npu_llm_daemon.py

The gap: Gen89 daemons (Devourer, Kraken) call Ollama for summarization/enrichment → GPU inference → CPU overhead. Routing short summarization tasks (BLUF generation, tag extraction) to the NPU would:
- Free GPU VRAM for larger models
- Reduce CPU load (NPU runs independently)
- Target: ~80% NPU utilization

**Recommended implementation:**
```python
from optimum.intel import OVModelForCausalLM
from transformers import AutoTokenizer

model_path = r"C:\hfoDev\.hfo_models\npu_llm\qwen3-1.7b-int4-ov-npu"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = OVModelForCausalLM.from_pretrained(model_path, device="NPU")
```

**Pointer key to add:** `npu.qwen3_1b` → `.hfo_models/npu_llm/qwen3-1.7b-int4-ov-npu`

### NPU detection note

`hfo_p7_gpu_npu_anchor.py` `diagnose` sometimes shows `⚠ No NPU device detected via WMI` even when OpenVINO lists NPU in `core.available_devices`. This is a WMI query timing issue — if OpenVINO confirms NPU, trust OpenVINO.

---

## 5. Stryker CPU Headroom

### Problem

HFO daemons (Devourer, Kraken, Background, Dancer) run continuously. Stryker mutation testing is CPU-intensive. No coordination existed — both competed for all 8 CPU cores.

### Solution: Two layers

**Layer 1 — Auto-throttle (passive):**  
`HFO_CPU_THROTTLE=60` in `.env` → daemon workers auto-pause when system CPU > 60%.  
Gives Stryker ~35-40% CPU headroom without manual intervention.

**Layer 2 — Explicit yield (active):**  
Run before Stryker to guarantee daemons yield immediately:
```bash
python _pause_for_stryker.py          # Pause → daemons yield within 15s
python _pause_for_stryker.py --status # Check active requests
python _pause_for_stryker.py --resume # Release when Stryker done
```

This emits `hfo.gen89.resource.request` to SSOT. Daemons using `ResourceMonitor.check_stigmergy_yields()` will set `_paused=True` within `HFO_YIELD_CHECK` seconds (default 15).

**Yield window:** 5 minutes. Re-run the script to extend. After 5 minutes, daemons auto-resume.

### Running Stryker

```bash
# 1. Pause daemons
python _pause_for_stryker.py

# 2. Wait ~15 seconds for daemons to yield
Start-Sleep 15

# 3. Run Stryker
cd hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel
npx stryker run

# 4. Resume daemons
python _pause_for_stryker.py --resume
```

---

## 6. GPU Utilization Targets

**Current:** 8.6/15 GB = 57% VRAM  
**Target:** ~80% = ~12 GB VRAM  
**Budget:** 10 GB soft (`HFO_VRAM_BUDGET_GB=10`), 15 GB hard

### Loaded models (2026-02-20)
- `gemma3:4b` — 4.0 GB (general assistant)
- `qwen2.5-coder:7b` — 4.6 GB (coding)
- Total: 8.6 GB

### Path to 80% GPU utilization
Option A — Replace `qwen2.5-coder:7b` (4.6 GB) with `phi4:14b` (8.4 GB):
- Total: 4.0 + 8.4 = 12.4 GB = 83% ✓
- Risk: phi4 is 14B → slower inference

Option B — Add `qwen3:8b` (4.9 GB):
- Total: 4.0 + 4.6 + 4.9 = 13.5 GB = 90% ⚠ over soft budget
- Only do this when Stryker is not running

Option C — Load `gemma3:12b` (7.6 GB) alone:
- Total: 7.6 GB = 51% — worse than current

**Recommendation:** When not doing Stryker testing, swap `qwen2.5-coder:7b` for `phi4:14b` to hit ~80% GPU.

---

## 7. SSOT Write Fix (signal_metadata gate)

**Problem:** `hfo_resource_governance.py` and `hfo_p7_gpu_npu_anchor.py` used raw `INSERT INTO stigmergy_events` without `signal_metadata`. The structural gate (`hfo_ssot_write.py`) blocked all writes.

**Fix applied 2026-02-20:**
- Both files now import `write_stigmergy_event, build_signal_metadata` from `hfo_ssot_write`
- `_write_gov_event` in governance uses `build_signal_metadata(port="P6", daemon_name="resource_governance", ...)`
- `write_event` in anchor uses `build_signal_metadata(port="P7", daemon_name="gpu_npu_anchor", ...)`
- Both have raw-insert fallback if `hfo_ssot_write` import fails

**Verification:**
```
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_p7_gpu_npu_anchor.py diagnose
# Should show no [WARN] SSOT write failed lines
```

---

## 8. Quick Command Reference

```bash
# Resource status
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_resource_monitor.py

# Hardware audit
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_p7_gpu_npu_anchor.py diagnose

# NPU embedding stats
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_npu_embedder.py stats

# Pause daemons for Stryker
python _pause_for_stryker.py

# Start governance daemon (background)
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_resource_governance.py

# Ollama model status
ollama ps
```

---

## 9. Known Issues & Next Tasks

| Priority | Issue | Status |
|---|---|---|
| P0 | NPU LLM inference not wired — models downloaded but unused | Open |
| P1 | Governance daemon fires advisory events but no daemon reads them to self-throttle | Open |
| P2 | `hfo_p7_gpu_npu_anchor.py` WMI NPU detection flaky | Open |
| P3 | `HFO_GOV_WINDOW_SIZE` env var reads correctly but `SAMPLE_INTERVAL_S` → mismatch was present | Fixed |

---

*SSOT reference: stigmergy row 15916 (hfo.gen89.p7.handoff.session:2026-02-20:resource_governance_npu_stryker)*
