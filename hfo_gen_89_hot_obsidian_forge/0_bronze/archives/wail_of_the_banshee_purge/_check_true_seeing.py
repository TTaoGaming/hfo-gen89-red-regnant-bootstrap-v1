"""Quick audit of TRUE_SEEING stigmergy records + current status file."""
import sqlite3, json, os
from pathlib import Path

ROOT = Path(__file__).parent
DB   = ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"
STATUS_FILE = ROOT / ".hfo_resource_status.json"

conn = sqlite3.connect(str(DB))
rows = conn.execute("""
    SELECT timestamp, data_json
    FROM stigmergy_events
    WHERE event_type='hfo.gen89.p0.true_seeing'
    ORDER BY id DESC LIMIT 60
""").fetchall()
conn.close()

print(f"TRUE_SEEING records in SSOT: {len(rows)}")
print()

cpu_v, ram_v, vram_v, swap_v, npu_v = [], [], [], [], []
snapshots = []

for ts, dj in rows:
    try:
        d = json.loads(dj)
        # handle different nesting levels
        inner = d.get("data", d)
        c = inner.get("current", inner)
        cpu  = c.get("cpu_pct")
        ram  = c.get("ram_pct")
        vram = c.get("vram_pct")
        swap = c.get("swap_pct")
        npu  = c.get("npu_active", False)
        vram_gb = c.get("vram_used_gb", 0)
        models  = [m.get("name","?") for m in (c.get("ollama_models") or [])]
        if cpu  is not None: cpu_v.append(cpu)
        if ram  is not None: ram_v.append(ram)
        if vram is not None: vram_v.append(vram)
        if swap is not None: swap_v.append(swap)
        npu_v.append(bool(npu))
        snapshots.append((ts, cpu, ram, vram_gb, vram, npu, models, swap))
    except Exception as e:
        snapshots.append((ts, None, None, None, None, None, [], None))

def stats(label, vals, target=80):
    v = [x for x in vals if x is not None]
    if not v:
        print(f"  {label}: no data")
        return
    avg = sum(v) / len(v)
    flag = "  !! OVER TARGET" if avg > target else ("  << UNDER" if avg < target * 0.5 else "  OK")
    print(f"  {label}: avg={avg:5.1f}%  min={min(v):5.1f}%  max={max(v):5.1f}%  n={len(v)}{flag}")

print("=== UTILISATION AVERAGES (target ~80%) ===")
stats("CPU ", cpu_v,  target=80)
stats("RAM ", ram_v,  target=80)
stats("VRAM", vram_v, target=80)
stats("Swap", swap_v, target=30)
npu_count = sum(npu_v)
npu_pct   = 100 * npu_count / max(len(npu_v), 1)
flag = "  << UNDERUTILISED" if npu_pct < 20 else "  OK"
print(f"  NPU : active {npu_count}/{len(npu_v)} samples ({npu_pct:.0f}%){flag}")

print()
print("=== LAST 10 SNAPSHOTS ===")
print(f"  {'Timestamp':<20}  {'CPU':>5}  {'RAM':>5}  {'VRAM GB':>8}  {'VRAM%':>6}  {'NPU':>4}  {'Swap':>5}  Models")
print("  " + "-"*90)
for ts, cpu, ram, vg, vp, npu, models, swap in snapshots[:10]:
    ts_s   = ts[:19] if ts else "?"
    cpu_s  = f"{cpu:.1f}%" if cpu is not None else "  ?"
    ram_s  = f"{ram:.1f}%" if ram is not None else "  ?"
    vg_s   = f"{vg:.2f}" if vg  is not None else "   ?"
    vp_s   = f"{vp:.1f}%" if vp  is not None else "  ?"
    sw_s   = f"{swap:.1f}%" if swap is not None else "  ?"
    npu_s  = " ON " if npu else " off"
    mods   = ", ".join(models) if models else "(none)"
    print(f"  {ts_s}  {cpu_s:>6}  {ram_s:>6}  {vg_s:>8}  {vp_s:>6}  {npu_s}  {sw_s:>6}  {mods}")

# Current live status file
print()
print("=== LIVE STATUS FILE (.hfo_resource_status.json) ===")
if STATUS_FILE.exists():
    s = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    c = s.get("current", {})
    r = s.get("rolling_10min", {})
    print(f"  Updated : {s.get('updated_at','?')[:19]}")
    print(f"  CPU     : {c.get('cpu_pct','?')}%  (10m avg {r.get('cpu_pct_avg','?')}%  peak {r.get('cpu_pct_peak','?')}%)")
    print(f"  RAM     : {c.get('ram_pct','?')}%  free {c.get('ram_free_gb','?')} GB  (10m avg {r.get('ram_pct_avg','?')}%)")
    print(f"  Swap    : {c.get('swap_pct','?')}%  {c.get('swap_used_gb','?')}/{c.get('swap_total_gb','?')} GB")
    print(f"  VRAM    : {c.get('vram_used_gb','?')} GB / {c.get('vram_budget_gb','?')} GB  ({c.get('vram_pct','?')}%)")
    print(f"  GPU gate: {c.get('gpu_gate','?')}")
    models = c.get('ollama_models') or []
    for m in models:
        print(f"    model  : {m.get('name','?')}  {m.get('vram_mb','?')} MB  ({m.get('size_mb','?')} MB total)")
    print(f"  NPU     : {'ACTIVE' if c.get('npu_active') else 'idle'}  (last inference: {c.get('npu_last_inference_s','never')} s ago)")
    print(f"  NPU cfg : {c.get('npu_model_configured','?')}")
    print(f"  Python  : {c.get('python_proc_count','?')} procs  ({c.get('hfo_daemon_count','?')} HFO daemons)")
    print(f"  Gov violations (10m): {r.get('governance_violations','?')}")
else:
    print("  File not found — is P0 Watcher running?")
