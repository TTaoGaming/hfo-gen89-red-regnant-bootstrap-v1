#!/usr/bin/env python3
"""Diagnose NPU, router, and CPU pressure. No theater."""
import os, sys, json, time
from pathlib import Path

_root = Path(__file__).parent
_res  = _root / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources"
sys.path.insert(0, str(_res))

try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env", override=False)
except ImportError:
    pass

SEP = "=" * 62
print(f"\n{SEP}")
print("  STRUCTURAL DIAGNOSIS — NPU / CPU / Enforcement")
print(SEP)

# ── 1. NPU model path ────────────────────────────────────────────────────────
npu_path = os.getenv("HFO_NPU_MODEL_PATH", "")
print(f"\n[1] NPU MODEL PATH")
print(f"  env HFO_NPU_MODEL_PATH : {repr(npu_path) if npu_path else 'NOT SET'}")
npu_ok = False
if npu_path:
    p = Path(npu_path)
    exists = p.exists()
    print(f"  path exists            : {exists}")
    if exists:
        files = sorted(p.iterdir())
        print(f"  contents ({len(files)} items)  : {[f.name for f in files[:10]]}")
        npu_ok = any(f.suffix in (".xml", ".bin") or "openvino" in f.name.lower() for f in files)
        print(f"  OpenVINO model files   : {npu_ok}")
    else:
        print("  !!! PATH DOES NOT EXIST — NPU CANNOT WORK")
else:
    print("  !!! NOT CONFIGURED — NPU DISABLED")

# ── 2. openvino_genai import ─────────────────────────────────────────────────
print(f"\n[2] OPENVINO_GENAI")
try:
    import openvino_genai as ov
    ver = getattr(ov, "__version__", "?")
    print(f"  import                 : OK  version={ver}")
    ov_ok = True
except ImportError as e:
    print(f"  import                 : MISSING  ({e})")
    ov_ok = False
except Exception as e:
    print(f"  import                 : ERROR  ({e})")
    ov_ok = False

# ── 3. Router config ─────────────────────────────────────────────────────────
print(f"\n[3] ROUTER CONFIG")
try:
    from hfo_llm_router import RouterConfig, LLMRouter
    r = RouterConfig.from_env()
    print(f"  strategy               : {r.strategy}")
    print(f"  npu_model_path         : {repr(r.npu_model_path)}")
    print(f"  vram_budget_gb         : {r.vram_budget_gb}")
    print(f"  cpu_target_pct         : {r.cpu_target_pct}")
    print(f"  gemini_key set         : {bool(r.gemini_api_key)}")
    print(f"  openrouter_key set     : {bool(r.openrouter_api_key)}")
except Exception as e:
    print(f"  ERROR loading router   : {e}")

# ── 4. Live resource snapshot ────────────────────────────────────────────────
print(f"\n[4] LIVE RESOURCES")
try:
    from hfo_resource_governor import get_resource_snapshot
    snap = get_resource_snapshot()
    ram_used = snap.ram_total_gb - snap.ram_available_gb
    print(f"  CPU                    : {snap.cpu_pct:.1f}%  (orchestrator target: 60%)")
    print(f"  RAM                    : {ram_used:.2f}/{snap.ram_total_gb:.1f} GB  ({snap.ram_used_pct:.1f}%)")
    print(f"  VRAM                   : {snap.vram_used_gb:.2f}/{snap.vram_budget_gb:.1f} GB  ({snap.vram_pct_of_budget:.1f}%)")
    print(f"  Ollama models loaded   : {len(snap.ollama_models_loaded)}")
    print(f"  safe_to_infer_gpu      : {snap.safe_to_infer_gpu}")
    print(f"  throttle_reason        : {snap.throttle_reason or 'none'}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 5. What processes are actually burning CPU? ───────────────────────────────
print(f"\n[5] TOP CPU PROCESSES (psutil)")
try:
    import psutil
    procs = []
    for p in psutil.process_iter(["pid","name","cpu_percent","memory_info"]):
        try:
            p.cpu_percent(interval=None)
        except Exception:
            pass
    time.sleep(0.5)
    for p in psutil.process_iter(["pid","name","cpu_percent","memory_info"]):
        try:
            cpu = p.info["cpu_percent"] or 0
            mem = (p.info["memory_info"].rss / 1024**3) if p.info["memory_info"] else 0
            procs.append((cpu, mem, p.info["pid"], p.info["name"]))
        except Exception:
            pass
    procs.sort(reverse=True)
    for cpu, mem, pid, name in procs[:12]:
        if cpu > 0.5 or "ollama" in name.lower() or "python" in name.lower():
            print(f"  {cpu:6.1f}%  {mem:.2f}GB  [{pid:6}] {name}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 6. Honest structural assessment ──────────────────────────────────────────
print(f"\n{SEP}")
print("  STRUCTURAL ENFORCEMENT AUDIT")
print(SEP)

npu_verdict = "WORKING" if (npu_ok and ov_ok) else "BROKEN"
print(f"\n  NPU                 : {npu_verdict}")
if not ov_ok:
    print("    openvino_genai not importable — every 'npu_first' falls through to Ollama (CPU)")
if not npu_ok:
    print("    model path missing — NPU physically cannot run")

print(f"\n  Orchestrator enforcement model:")
print("    REACTIVE (detects CPU > 60%, scales down concurrency)")
print("    NOT preemptive: CPU can spike for up to scale_interval_s=60s before action")
print("    NOT preventing Ollama from loading on CPU in the gap")
print("    Concurrency throttle only limits *new* port ticks, not in-flight ones")

print(f"\n  What WOULD give structural CPU protection:")
print("    A) Fix NPU first — eliminate CPU inference entirely")
print("       All inference → NPU/GPU → CPU usage from HFO drops to near 0")
print("    B) Reduce scale_interval_s to 10s (faster reaction)")
print("    C) Set OLLAMA_NUM_GPU_LAYERS=99 in .env to force Ollama onto GPU only")
print("       (prevents CPU threads from running model layers)")
print("    D) Add a pre-tick CPU gate in _run_port_tick: if CPU > target, skip tick")

print(f"\n  Verdict: Theater-adjacent until NPU is confirmed working OR Ollama")
print("  is pinned to GPU-only layers. The concurrency scaler is real but slow.")
print()
