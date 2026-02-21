#!/usr/bin/env python3
"""Immediate VRAM eviction + governance wire-up diagnosis."""
import sys, json, urllib.request, urllib.error, time
sys.path.insert(0, 'hfo_gen_89_hot_obsidian_forge/0_bronze/resources')

OLLAMA = 'http://localhost:11434'

def ollama_ps():
    with urllib.request.urlopen(f'{OLLAMA}/api/ps', timeout=5) as r:
        return json.loads(r.read()).get('models', [])

def evict(name):
    """Force-evict a model by setting keep_alive=0."""
    body = json.dumps({'model': name, 'keep_alive': 0}).encode()
    req = urllib.request.Request(f'{OLLAMA}/api/generate', data=body,
                                  headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True
    except Exception as e:
        return str(e)

# --- BEFORE ---
before = ollama_ps()
total_before = sum(m.get('size_vram', 0) for m in before) / 1024**2
print(f"=== BEFORE eviction: {len(before)} models, {total_before:.0f} MB = {total_before/1024:.2f} GB ===")
for m in before:
    print(f"  {m['name']:<40s}  {m.get('size_vram',0)/1024**2:.0f} MB")

# --- EVICT ALL OVER-BUDGET ---
BUDGET_MB = 10 * 1024  # 10 GB
evicted = []
if total_before > BUDGET_MB:
    print(f"\n  !! OVER BUDGET by {total_before - BUDGET_MB:.0f} MB — evicting all models")
    for m in before:
        name = m['name']
        print(f"  Evicting {name}...", end=' ')
        result = evict(name)
        print('OK' if result is True else f'ERR: {result}')
        evicted.append(name)
    time.sleep(2)
else:
    print(f"\n  Within budget (budget {BUDGET_MB} MB). No eviction needed.")

# --- AFTER ---
after = ollama_ps()
total_after = sum(m.get('size_vram', 0) for m in after) / 1024**2
print(f"\n=== AFTER eviction: {len(after)} models, {total_after:.0f} MB = {total_after/1024:.2f} GB ===")
if not after:
    print("  GPU VRAM: 0 MB (fully cleared)")
for m in after:
    print(f"  {m['name']:<40s}  {m.get('size_vram',0)/1024**2:.0f} MB")

# --- ResourceGovernor enforce() ---
print("\n=== ResourceGovernor.enforce() ===")
try:
    from hfo_resource_governor import ResourceGovernor, GovernorConfig, get_resource_snapshot
    snap = get_resource_snapshot()
    cfg = GovernorConfig.from_env()
    gov = ResourceGovernor(cfg)
    gate = gov.gate(snap)
    print(f"  gate()   → {gate}")
    result = gov.enforce(snap)
    print(f"  enforce() → evicted={result.get('evicted_count',0)}  actions={result.get('actions_taken',[])}")
    print(f"  VRAM now: {snap.get('vram_pct','?')}%  ({snap.get('vram_used_gb','?')} GB)")
except Exception as e:
    import traceback
    print(f"  ERROR: {e}")
    traceback.print_exc()

print(f"\n=== Summary ===")
print(f"  Freed: {total_before - total_after:.0f} MB ({(total_before - total_after)/1024:.2f} GB)")
print(f"  Evicted models: {evicted}")
