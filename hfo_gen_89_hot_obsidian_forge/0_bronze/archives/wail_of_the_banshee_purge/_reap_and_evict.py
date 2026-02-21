#!/usr/bin/env python3
"""Ghost process reaper + final eviction."""
import sys, os, json, time, urllib.request
sys.path.insert(0, 'hfo_gen_89_hot_obsidian_forge/0_bronze/resources')

import psutil

OLLAMA = 'http://localhost:11434'
BUDGET_MB = 8 * 1024  # evict when over 8 GB (80% of 10 GB budget)

# STEP 1 — show all HFO processes, don't kill anything yet
print("=== Current HFO + daemon processes ===")
all_procs = []
for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'status']):
    try:
        cmdline = ' '.join(p.info.get('cmdline') or [])
        if 'hfo_' in cmdline or 'daemon' in cmdline.lower():
            all_procs.append({
                'pid': p.pid,
                'age_min': round((time.time() - p.info.get('create_time', time.time())) / 60, 1),
                'status': p.info.get('status', '?'),
                'cmd': cmdline[-100:],
            })
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

all_procs.sort(key=lambda x: x['age_min'], reverse=True)
for p in all_procs:
    print(f"  PID {p['pid']:6d}  age={p['age_min']:6.1f}m  [{p['status']}]  {p['cmd']}")
print(f"\n  Total: {len(all_procs)} processes")

# STEP 2 — identify duplicate fleet managers (keep oldest)
fleet_managers = [(p, p['pid']) for p in all_procs if 'daemon_fleet' in p['cmd']]
print(f"\n=== Fleet manager instances: {len(fleet_managers)} ===")
for p, pid in fleet_managers:
    print(f"  PID {pid}  age={p['age_min']}m  {p['cmd']}")

print("\n>>> Kill duplicate fleet managers? (keeping oldest)")
# Sort by age descending; keep oldest (first), kill the rest
fleet_managers.sort(key=lambda x: x[0]['age_min'], reverse=True)
to_kill = fleet_managers[1:]  # kill all but oldest
print(f"  Would kill: {[pid for _, pid in to_kill]}")

# STEP 3 — ACTUALLY KILL duplicates
killed = []
for p, pid in to_kill:
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        killed.append(pid)
        print(f"  Terminated PID {pid} (age={p['age_min']}m): {p['cmd'][:60]}")
    except Exception as e:
        print(f"  Failed to kill PID {pid}: {e}")

time.sleep(2)

# Force kill if still alive
for p, pid in to_kill:
    try:
        proc = psutil.Process(pid)
        if proc.is_running():
            proc.kill()
            print(f"  Force-killed PID {pid}")
    except psutil.NoSuchProcess:
        pass  # already dead

print(f"\n  Killed {len(killed)} duplicate fleet managers: {killed}")

# STEP 4 — Evict over-budget models
def ollama_ps():
    try:
        with urllib.request.urlopen(f'{OLLAMA}/api/ps', timeout=5) as r:
            return json.loads(r.read()).get('models', [])
    except:
        return []

def evict(name):
    body = json.dumps({'model': name, 'keep_alive': '0s', 'prompt': ''}).encode()
    req = urllib.request.Request(f'{OLLAMA}/api/generate', data=body,
                                  headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            pass
        return True
    except Exception as e:
        return str(e)

time.sleep(1)
models = ollama_ps()
total_mb = sum(m.get('size_vram', 0) for m in models) / 1024**2
print(f"\n=== VRAM status: {len(models)} models, {total_mb:.0f} MB = {total_mb/1024:.2f} GB ===")
for m in models:
    print(f"  {m['name']:<40s}  {m.get('size_vram',0)/1024**2:.0f} MB")

if total_mb > BUDGET_MB:
    print(f"\n  !! OVER BUDGET — evicting largest models first")
    # Sort by vram descending, evict until under budget
    sorted_models = sorted(models, key=lambda m: m.get('size_vram', 0), reverse=True)
    freed = 0
    for m in sorted_models:
        if total_mb - freed <= BUDGET_MB:
            break
        vram_mb = m.get('size_vram', 0) / 1024**2
        print(f"  Evicting {m['name']} ({vram_mb:.0f} MB)...", end=' ')
        r = evict(m['name'])
        print('OK' if r is True else f'ERR: {r}')
        freed += vram_mb
    print(f"  Freed ~{freed:.0f} MB")
    time.sleep(3)
    # Check again
    models2 = ollama_ps()
    total2 = sum(m.get('size_vram', 0) for m in models2) / 1024**2
    print(f"  After eviction: {len(models2)} models, {total2:.0f} MB")
else:
    print("  Within budget, no eviction needed.")

# STEP 5 — Final process count
print("\n=== Final process count ===")
final_procs = []
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cmdline = ' '.join(p.info.get('cmdline') or [])
        if 'hfo_' in cmdline:
            final_procs.append(p.pid)
    except:
        pass
print(f"  hfo_* processes: {len(final_procs)} (was {len(all_procs)})")

# STEP 6 — Write governance enforce() now that it returns correctly
print("\n=== ResourceGovernor.enforce() (fixed) ===")
try:
    from hfo_resource_governor import ResourceGovernor, GovernorConfig, get_resource_snapshot
    snap = get_resource_snapshot()
    cfg = GovernorConfig.from_env()
    gov = ResourceGovernor(cfg)
    gate = gov.gate(snap)
    print(f"  gate()   → {gate}  (VRAM={snap.vram_pct_of_budget:.1f}%  RAM={snap.ram_used_pct:.1f}%)")
    result = gov.enforce(snap)
    print(f"  enforce() → evicted={result.get('evicted_count',0)}  "
          f"gate={result.get('gate')}  cycle={result.get('enforcement_cycle')}")
except Exception as e:
    import traceback
    print(f"  ERROR: {e}")
    traceback.print_exc()
