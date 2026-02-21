#!/usr/bin/env python3
"""P0 TRUE SEEING full diagnostic."""
import sqlite3, json, os, sys
sys.path.insert(0, 'hfo_gen_89_hot_obsidian_forge/0_bronze/resources')

DB = 'hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite'
c = sqlite3.connect(DB)

# ── 1. Latest TRUE_SEEING raw structure ──────────────────────────────────────
print("=== TRUE_SEEING latest raw ===")
rows = c.execute("""SELECT timestamp, data_json FROM stigmergy_events
                    WHERE event_type LIKE '%true_seeing%' OR event_type LIKE '%TRUE_SEEING%'
                    ORDER BY id DESC LIMIT 3""").fetchall()
for ts, dj in rows:
    d = json.loads(dj)
    print(f"\n  [{ts[:19]}]  keys={list(d.keys())}")
    # Print nested snapshot if present
    snap = d.get('snapshot') or d.get('data') or d
    for k, v in list(snap.items())[:20]:
        print(f"    {k}: {v}")

# ── 2. Last 12 TRUE_SEEING flattened ─────────────────────────────────────────
print("\n=== TRUE_SEEING trend (last 12) ===")
rows = c.execute("""SELECT timestamp, data_json FROM stigmergy_events
                    WHERE event_type LIKE '%true_seeing%' OR event_type LIKE '%TRUE_SEEING%'
                    ORDER BY id DESC LIMIT 12""").fetchall()
def dig(d, *keys):
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return '?'
    return d
for ts, dj in reversed(rows):
    d = json.loads(dj)
    snap = d.get('snapshot') or d.get('data') or d
    cpu  = dig(snap, 'cpu_pct')
    ram  = dig(snap, 'ram_pct')
    vgb  = dig(snap, 'vram_used_gb')
    vpct = dig(snap, 'vram_pct')
    npu  = dig(snap, 'npu_active')
    gate = dig(snap, 'gpu_gate')
    models = snap.get('ollama_models_loaded', [])
    model_names = [m.get('name','?') if isinstance(m, dict) else m for m in models]
    print(f"  {ts[:19]}  CPU={cpu}%  RAM={ram}%  "
          f"VRAM={vgb}GB({vpct}%)  NPU={npu}  gate={gate}  models={model_names}")

# ── 3. Governor events ────────────────────────────────────────────────────────
print("\n=== Governor + Router events (last 20) ===")
rows = c.execute("""SELECT timestamp, event_type, data_json FROM stigmergy_events
                    WHERE event_type LIKE 'hfo.gen89.governor%'
                       OR event_type LIKE 'hfo.gen89.llm_router%'
                    ORDER BY id DESC LIMIT 20""").fetchall()
if not rows:
    print("  (none — governor class not yet invoked)")
for ts, et, dj in rows[:15]:
    d = json.loads(dj) if dj else {}
    evicted = d.get('evicted') or d.get('models') or []
    vram = d.get('vram_pct', '')
    ram  = d.get('ram_pct', '')
    extra = f"  vram={vram}%  ram={ram}%" if vram else ''
    extra += f"  evicted={evicted}" if evicted else ''
    print(f"  {ts[:19]}  {et}{extra}")

# ── 4. NPU state files ────────────────────────────────────────────────────────
print("\n=== NPU state ===")
for path in ['.hfo_npu_state.json', '.hfo_resource_status.json']:
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        print(f"  [{path}]")
        for k, v in list(data.items())[:10]:
            print(f"    {k}: {v}")
    else:
        print(f"  {path}: NOT FOUND")

# ── 5. Current live VRAM (Ollama ps) ─────────────────────────────────────────
print("\n=== Live Ollama /api/ps ===")
import urllib.request
try:
    with urllib.request.urlopen('http://localhost:11434/api/ps', timeout=5) as r:
        data = json.loads(r.read())
    models = data.get('models', [])
    total_vram = sum(m.get('size_vram', 0) for m in models) / 1024**2
    for m in models:
        vram_mb = m.get('size_vram', 0) / 1024**2
        print(f"  {m['name']:<40s}  vram={vram_mb:.0f}MB  expires={m.get('expires_at','?')}")
    print(f"  TOTAL: {total_vram:.0f} MB = {total_vram/1024:.2f} GB")
    if not models:
        print("  (no models loaded)")
except Exception as e:
    print(f"  Ollama unreachable: {e}")

# ── 6. NPU model path check ───────────────────────────────────────────────────
print("\n=== NPU availability ===")
npu_path = os.getenv('P6_NPU_LLM_MODEL', '')
print(f"  P6_NPU_LLM_MODEL = {npu_path!r}")
if npu_path:
    from pathlib import Path
    print(f"  Path exists: {Path(npu_path).exists()}")
try:
    import openvino_genai
    print("  openvino_genai: INSTALLED")
except ImportError:
    print("  openvino_genai: NOT INSTALLED  <-- router cannot use NPU")

# ── 7. Router config ──────────────────────────────────────────────────────────
print("\n=== Router config (from env) ===")
try:
    from hfo_llm_router import RouterConfig
    cfg = RouterConfig.from_env()
    print(f"  strategy        : {cfg.strategy}")
    print(f"  npu_model_path  : {cfg.npu_model_path!r}")
    print(f"  vram_budget_gb  : {cfg.vram_budget_gb}")
    print(f"  vram_target_pct : {cfg.vram_target_pct}%  (evict above {cfg.vram_target_gb:.1f} GB)")
    print(f"  ram_target_pct  : {cfg.ram_target_pct}%")
    print(f"  gemini_key      : {'SET' if cfg.gemini_api_key else 'NOT SET'}")
    print(f"  openrouter_key  : {'SET' if cfg.openrouter_api_key else 'NOT SET'}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 8. Process count ──────────────────────────────────────────────────────────
print("\n=== Python process count ===")
try:
    import psutil
    hfo_procs = [p for p in psutil.process_iter(['pid', 'name', 'cmdline'])
                 if any('hfo_' in (c or '') for c in (p.info.get('cmdline') or []))]
    print(f"  hfo_* python processes: {len(hfo_procs)}")
    for p in hfo_procs[:12]:
        cmd = ' '.join(p.info.get('cmdline') or [])
        print(f"    PID {p.info['pid']}: {cmd[-80:]}")
except Exception as e:
    print(f"  psutil error: {e}")
