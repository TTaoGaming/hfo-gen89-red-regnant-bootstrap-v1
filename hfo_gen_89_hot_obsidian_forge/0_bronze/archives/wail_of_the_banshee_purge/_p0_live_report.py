#!/usr/bin/env python3
"""Live P0 TRUE SEEING report — run once and print."""
import sys
import time
import json
from pathlib import Path

# Resolve resource dir
_root = Path(__file__).parent
_res  = _root / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources"
sys.path.insert(0, str(_res))

try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env", override=False)
except ImportError:
    pass

from hfo_resource_governor import get_resource_snapshot, ResourceGovernor, GovernorConfig

SEP = "=" * 62

# ── Live snapshot ──────────────────────────────────────────────────────────
t0   = time.monotonic()
snap = get_resource_snapshot()
ms   = (time.monotonic() - t0) * 1000

ram_used_gb = snap.ram_total_gb - snap.ram_available_gb

print(f"\n{SEP}")
print(f"  P0 TRUE SEEING — live snapshot  ({ms:.0f} ms)")
print(SEP)
print(f"  CPU    : {snap.cpu_pct:5.1f}%   ({snap.cpu_cores} cores)")
print(f"  RAM    : {ram_used_gb:.2f} GB / {snap.ram_total_gb:.1f} GB  ({snap.ram_used_pct:.1f}%)  free={snap.ram_available_gb:.2f} GB")
print(f"  Swap   : {snap.swap_used_gb:.2f} GB / {snap.swap_total_gb:.1f} GB  ({snap.swap_used_pct:.1f}%)")
print(f"  VRAM   : {snap.vram_used_gb:.2f} GB / {snap.vram_budget_gb:.1f} GB  ({snap.vram_pct_of_budget:.1f}% of budget)  headroom={snap.vram_headroom_gb:.2f} GB")
print(f"  GPU pressure    : {snap.gpu_pressure}   safe_to_infer={snap.safe_to_infer_gpu}")
if snap.throttle_reason:
    print(f"  Throttle reason : {snap.throttle_reason}")
print(f"  Ollama models in VRAM : {len(snap.ollama_models_loaded)}")
for m in snap.ollama_models_loaded:
    name = m if isinstance(m, str) else m.get("name", str(m))
    mb   = m.get("vram_mb", 0) if isinstance(m, dict) else 0
    print(f"    + {name}  {mb:.0f} MB")

# ── Governance enforce ─────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  GOVERNANCE ENFORCE")
print(SEP)
gov    = ResourceGovernor(GovernorConfig.from_env())
result = gov.enforce()
gate   = result.get("gate", "?")
icon   = "GO" if gate == "GO" else "STOP"
print(f"  Gate     : {icon}")
print(f"  VRAM     : {result.get('vram_pct', 0):.1f}%")
print(f"  RAM      : {result.get('ram_pct',  0):.1f}%")
print(f"  CPU      : {result.get('cpu_pct',  0):.1f}%")
print(f"  Evicted  : {result.get('evicted_count', 0)} model(s)")
if result.get("evicted"):
    for e in result["evicted"]:
        print(f"    > evicted {e}")
else:
    print("  Actions  : none — all nominal")

# ── Historical trend from stigmergy ───────────────────────────────────────
print(f"\n{SEP}")
print("  P0 HISTORICAL TREND (last 5 readings)")
print(SEP)
db = _root / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
if db.exists():
    import sqlite3
    con  = sqlite3.connect(str(db), timeout=5)
    rows = con.execute("""
        SELECT timestamp, data_json FROM stigmergy_events
        WHERE event_type = 'hfo.gen89.p0.true_seeing'
        ORDER BY id DESC LIMIT 5
    """).fetchall()
    con.close()
    for ts, dj in rows:
        d   = json.loads(dj or "{}")
        dd  = d.get("data", d)
        cur = dd.get("current", {})
        if isinstance(cur, str):
            try: cur = json.loads(cur)
            except: cur = {}
        gov_h  = dd.get("governance", {})
        if isinstance(gov_h, str):
            try: gov_h = json.loads(gov_h)
            except: gov_h = {}
        acts    = gov_h.get("actions_taken", [])
        flag    = " !!!" if acts else ""
        daemons = cur.get("hfo_daemon_count", "?")
        npu     = "ON " if cur.get("npu_active") else "off"
        models  = cur.get("gpu_model_count", 0)
        print(
            f"  [{ts[:19]}]  "
            f"CPU {cur.get('cpu_pct', 0):5.1f}%  "
            f"RAM {cur.get('ram_pct', 0):5.1f}%  "
            f"VRAM {cur.get('vram_pct', 0):5.1f}%  "
            f"NPU={npu}  daemons={daemons}  models={models}{flag}"
        )
        for a in acts:
            print(f"    > {a}")
else:
    print("  DB not found — skipping history")

# ── Conductor scale recommendation ────────────────────────────────────────
print(f"\n{SEP}")
print("  CONDUCTOR SCALE RECOMMENDATION")
print(SEP)
vram_h = 80.0 - snap.vram_pct_of_budget
ram_h  = 80.0 - snap.ram_used_pct
cpu_h  = 80.0 - snap.cpu_pct
over   = snap.vram_pct_of_budget > 80 or snap.ram_used_pct > 80 or snap.cpu_pct > 80
print(f"  VRAM headroom : {vram_h:+.1f}pp  (target 80%)")
print(f"  RAM  headroom : {ram_h:+.1f}pp")
print(f"  CPU  headroom : {cpu_h:+.1f}pp")
if over:
    print("\n  Decision : SCALE DOWN  (pressure detected)")
elif vram_h >= 15 and ram_h >= 15 and cpu_h >= 15:
    print("\n  Decision : SCALE UP OK  (all headroom >= 15pp)")
else:
    print("\n  Decision : HOLD  (headroom below 15pp threshold)")
print()
