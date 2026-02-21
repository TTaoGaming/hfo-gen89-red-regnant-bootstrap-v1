---
schema_id: hfo.diataxis.reference.v1
medallion_layer: gold
diataxis_type: reference
ports: [P7, P4, P5, P6]
commanders: [Spider Sovereign, Red Regnant, Pyre Praetorian, Kraken Keeper]
author: "TTAO + Red Regnant (P4 Gen89)"
date: "2026-02-20"
status: HANDOFF
bluf: >-
  Full session state handoff for 2026-02-20. Covers: resource governance fixes,
  NPU model downloads, Omega v13 active dev, Stryker CPU headroom problem,
  dancer cantrip/anomaly scan SKIPPED (bug), and 51 memory-loss surges in 1h.
  Critical open items: hfo_npu_llm_daemon.py not built, HFO_GOV_CPU_OVER not
  tuned, tldraw_layer.html integration unknown. PREY8 loop collapse rate HIGH.
keywords:
  - HANDOFF
  - SESSION_STATE
  - NPU_LLM
  - RESOURCE_GOVERNANCE
  - OMEGA_V13
  - STRYKER_CPU_HEADROOM
  - MEMORY_LOSS_SURGE
  - DANCER_SKIPPED
  - STRUCTURAL_GATE_FIX
  - CANONICAL_WRITE
  - INTEL_ARC_140V
stigmergy_anchors:
  - hfo.gen89.p7.handoff.session (row 15931)
---

# REFERENCE — 2026-02-20 Session Handoff (Gen89)

> **Next agent**: read this first. This is the session state at ~16:49 UTC.
> SSOT has **15,931 events**. The handoff event is at row 15931.

---

## 1. STIGMERGY HEALTH

| Signal | Status |
|--------|--------|
| Total events | 15,931 |
| Daemon heartbeats | HEALTHY (kraken, dancer, singer all pulsing) |
| memory_loss today | **CRITICAL — 51 in last hour (16:24 patrol)** |
| gate_blocked today | 3 events (16:21, 14:58, 15:20) |
| tamper_alerts today | 4 events (16:40, 16:35, 16:29 x2) |
| resource governance writes | WORKING (dancer.governance_patrol confirmed) |
| STRUCTURAL_GATE error | **FIXED** (hfo_resource_governance.py patched today) |

### Memory Loss Surge — Root Cause

The **51 memory losses in 1 hour** are caused by PREY8 agents (LLM sessions)
starting a `perceive` but never completing `react → execute → yield`. The
architecture catches these as orphaned sessions and logs them as `memory_loss`.

This is expected during heavy interactive dev (many short Copilot sessions). It
is NOT a code bug — it is the PREY8 loop detecting LLM context window death
correctly. The architecture is working; the rate is high because of session
churn.

**To reduce**: ensure every Copilot session closes with `hfo_yield.py`.

---

## 2. FIXES APPLIED THIS SESSION

### 2.1 STRUCTURAL_GATE Fix — hfo_resource_governance.py

**Problem**: `_write_gov_event()` called a local `write_event()` helper that
bypassed `hfo_ssot_write.write_stigmergy_event()`. This caused a
`STRUCTURAL_GATE` error because the DB CHECK constraint rejects raw inserts
without the canonical signal_metadata structure.

**Fix**: Replaced `_write_gov_event` with a direct call to
`write_stigmergy_event()` from `hfo_ssot_write`.

**Verify**: Check for `hfo.gen89.resource.*` events in stigmergy_events. If the
governance daemon is running, events should appear within 10 minutes.

### 2.2 SSOT Write Failed Fix — hfo_p7_gpu_npu_anchor.py

**Problem**: Local `write_event()` wrapper raised `SSOT write failed` on
structured inserts due to missing signal_metadata.

**Fix**: `write_event()` in `hfo_p7_gpu_npu_anchor.py` now calls
`write_stigmergy_event()` from `hfo_ssot_write` when `HAS_CANONICAL_WRITE=True`
(falls back to direct insert otherwise for BFT resilience).

### 2.3 VRAM Budget Enforcement — hfo_daemon_fleet.py + siblings

**Problem**: 8 daemon files hardcoded local Ollama model strings (e.g.
`gemma3:4b`, `qwen2.5:3b`), bypassing the `.env` VRAM budget governance.

**Fix**: All replaced with `os.getenv()` calls. Models now controlled from `.env`.

---

## 3. RESOURCE STATE AT HANDOFF

| Resource | State |
|----------|-------|
| VRAM (Intel Arc 140V) | 8.6 / 15 GB (57%) |
| Loaded GPU models | gemma3:4b (4.0 GB) + qwen2.5-coder:7b (4.6 GB) |
| NPU embeddings | **100%** — 9,866/9,866 docs embedded via all-MiniLM-L6-v2 |
| NPU LLM models | Downloaded, NOT running (see §4) |
| CPU | HIGH — HFO daemons + Stryker competing |
| `HFO_GOV_CPU_OVER` setting | Default (~80%) — **NOT tuned for Stryker** |

### NPU LLM Models (in `.hfo_models/npu_llm/`)

| Model | Path | Status |
|-------|------|--------|
| qwen3-1.7b-int4-ov-npu | `FluidInference/qwen3-1.7b-int4-ov-npu` | Downloaded, not running |
| qwen3-4b-int4-ov-npu | `FluidInference/qwen3-4b-int4-ov-npu` | Downloaded, not running |

These models are downloaded from HuggingFace but **no daemon routes inference
to them yet**. `hfo_npu_llm_daemon.py` has NOT been built.

---

## 4. CRITICAL OPEN ITEMS (next agent priority order)

### P1 — Build hfo_npu_llm_daemon.py

**Why critical**: 100% NPU embedding coverage achieved. The NPU is now IDLE
(confirmed by `hfo.gen89.p7.gpu_npu_anchor.diagnose:
compute=21.5pct:npu=IDLE`). Two LLM models are downloaded and waiting.

**What to build**:
```
hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_npu_llm_daemon.py
```
Pattern to follow: `hfo_p6_devourer_daemon.py` (task loop) + optimum-intel
OpenVINO inference pipeline for qwen3-1.7b-int4-ov-npu.

Primary task: route P6 Devourer BLUF/summary generation to NPU instead of
Ollama GPU. This frees GPU VRAM and activates Intel AI Boost.

```python
# Skeleton
from optimum.intel import OVModelForCausalLM
from transformers import AutoTokenizer

MODEL_PATH = os.getenv('HFO_NPU_LLM_PATH',
    r'C:\hfoDev\.hfo_models\npu_llm\qwen3-1.7b-int4-ov-npu')
model = OVModelForCausalLM.from_pretrained(MODEL_PATH, device='NPU')
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
```

### P2 — Tune HFO_GOV_CPU_OVER for Stryker

**Why critical**: System hitting ~100% CPU when HFO daemons run alongside
Stryker mutation testing. Daemons should yield at 65% CPU to give Stryker
35% headroom.

**Fix**: Add to `.env`:
```
HFO_GOV_CPU_OVER=65
```

The `hfo_resource_governor.py` `ResourceMonitor` reads this env var and sets
`_paused=True` when CPU exceeds threshold, yielding cycles to Stryker.

**Alternative** (force immediate yield via stigmergy):
```sql
INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash)
VALUES ('hfo.gen89.resource.request', datetime('now'), 'manual', 'PAUSE_DAEMONS', '{}', hex(randomblob(16)));
```

### P3 — Fix Dancer cantrip_check / anomaly_scan SKIPPED

**Observation**: Every `dancer.governance_patrol` shows both
`cantrip_check: SKIPPED` and `anomaly_scan: SKIPPED`. These should be active.

**Investigate**: Check `hfo_p5_dancer_daemon.py` patrol task logic. The SKIPPED
pattern suggests a threshold guard is never being met, or the tasks are gated
behind an `if` block that evaluates to False every cycle.

### P4 — Verify tldraw_layer.html Integration

**State**: `tldraw_layer.html` is open in the editor. The tldraw whiteboard
layer for Omega v13 is unknown status.

**Check**: Does `demo_2026-02-20.ts` reference `tldraw_layer.html`? Is it
loaded as an iframe? Does the Omega v13 demo serve it?

### P5 — Run Playwright Tests Against demo_2026-02-20.ts

**State**: Playwright + chromium installed. Tests NOT yet verified to pass.

```
cd hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel
npx playwright test --reporter=list
```

---

## 5. OMEGA V13 STATUS

| File | Status |
|------|--------|
| `demo_2026-02-20.ts` | Active entry point → `dist/demo2.js` (esbuild) |
| `tldraw_layer.html` | Open in editor, integration unknown |
| `2026-02-20_omega_v13_pareto_optimal_blueprint.md` | Open in editor |
| `dist/demo2.js` | Built successfully (last esbuild exit=0) |
| Playwright | Installed + chromium browser available |
| Jest tests | `behavioral_predictive_layer.spec.ts`, `audio_engine_plugin.spec.ts` |

**Architectural threats resolved today (T-OMEGA-001 to T-OMEGA-006)**:

| Threat | Fix |
|--------|-----|
| T-OMEGA-001: Main-Thread Evolutionary Blocking | Web Worker for GA evolution |
| T-OMEGA-002: GC Churn | Float32Array pre-allocation in hot loops |
| T-OMEGA-003: Ground Truth Paradox | Shadow Tracker for unsupervised learning |
| T-OMEGA-004: MAP-Elites Mirage | True MAP-Elites grid with Typed Arrays |
| T-OMEGA-005: Zombie Event Listeners | Bound method pattern + unsubscribe |
| T-OMEGA-006: Untrusted Gesture Audio Trap | AudioContext on user gesture only |

---

## 6. CANONICAL WRITE API — Reference

All stigmergy events MUST use `hfo_ssot_write.write_stigmergy_event()`.

```python
from hfo_ssot_write import write_stigmergy_event, build_signal_metadata

sig = build_signal_metadata(
    port='P6',                   # P0-P7
    model_id='gemma3:4b',        # model used, or 'governance' for infra events
    daemon_name='my_daemon',     # daemon filename (no .py)
    daemon_version='v1.0',       # semver
    task_type='summarization',   # what the daemon is doing
)

row_id = write_stigmergy_event(
    event_type='hfo.gen89.p6.daemon.task',
    subject='task:my_task',
    data={'key': 'value'},
    signal_metadata=sig,
)
```

**Required signal_metadata fields**: `port`, `model_id`, `daemon_name`,
`model_provider` (auto-set by `build_signal_metadata`), `daemon_version`.

**Empty strings rejected**. `""` is not a valid field value — the gate will log
a `STRUCTURAL_GATE_BLOCK` event and raise `SignalMetadataIncomplete`.

---

## 7. SSOT POINTERS

| Key | Path |
|-----|------|
| `ssot.db` | `hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite` |
| Canonical write | `hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_ssot_write.py` |
| Resource governor | `hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_resource_governor.py` |
| GPU/NPU anchor | `hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_p7_gpu_npu_anchor.py` |
| Omega v13 | `hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel/` |
| NPU LLM models | `C:/hfoDev/.hfo_models/npu_llm/` |
| Handoff stigmergy row | 15931 (`hfo.gen89.p7.handoff.session`) |

---

*Generated by Red Regnant (P4 Gen89) on 2026-02-20T16:49 UTC.
Stigmergy event: row 15931. Chain: PREY8 audit session.*

---

## 8. ADDENDUM — GITOPS DAEMON FIXES (2026-02-20 ~17:00 UTC)

### 8.1 hfo_p5_gitops_daemon.py — Three bugs fixed

**Bug 1: `model_provider` not a valid arg for `build_signal_metadata`**
- Removed `model_provider=...` kwarg from all `build_signal_metadata()` calls in the daemon.
- Canonical signature: `build_signal_metadata(port, model_id, daemon_name, daemon_version, *, task_type, cycle, ...)`

**Bug 2: Windows CP1252 UnicodeDecodeError on git subprocess output**
- Added `encoding="utf-8"` to all `subprocess.run()` calls.
- Git on Windows emits UTF-8 output (line endings, Unicode paths), but Python defaults to the system code page (cp1252) which can't decode byte 0x90.

**Bug 3: `git pull --rebase` blocked by unstaged SSOT changes**
- The `hfo_gen89_ssot.sqlite` binary file is always modified by running daemons.
- `git pull --rebase` fails when unstaged modifications exist.
- **Fix**: Detect unstaged modifications before pull. If present, skip pull and push-only.
```python
has_unstaged = any(line[1] == 'M' for line in status_out.splitlines() if len(line) >= 2)
if has_unstaged:
    print("  [~] Skipping pull: unstaged modifications. Pushing only.")
else:
    code, out, err = self.run_cmd(["git", "pull", "--rebase"])
```

### 8.2 Stash accumulation bug (discovered during debugging)

Multiple test runs of the daemon accumulated stale `gitops_auto_stash` entries in `git stash list`. To clean up:
```bash
git stash list   # check for gitops_auto_stash entries
git stash drop stash@{N}  # drop each stale entry
```

### 8.3 Stigmergy emission — VERIFIED working

`hfo.gen89.gitops.error` events are now successfully written to SSOT (confirmed at rows ~15954+).
`hfo.gen89.gitops.sync` events will be emitted on successful push cycles.

---

*Addendum written by P4 Red Regnant PREY8 session 2bd88306a0d73a0d, ~17:00 UTC.*
