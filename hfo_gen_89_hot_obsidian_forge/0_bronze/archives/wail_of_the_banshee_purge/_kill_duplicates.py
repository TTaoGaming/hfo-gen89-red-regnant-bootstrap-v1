#!/usr/bin/env python3
"""Kill duplicate daemon instances — keep newest of each type."""
import psutil, time, re, sys
from collections import defaultdict

SAFE_KEEP_PATTERNS = {
    # pattern → keep strategy ('newest' or 'oldest')
    'hfo_octree_daemon': 'newest',
    'hfo_singer_ai_daemon': 'newest',
    'hfo_p5_dancer_daemon': 'newest',
    'hfo_p6_devourer_daemon': 'newest',
    'hfo_background_daemon': 'newest',
    'hfo_p7_metafaculty': 'newest',
    'hfo_p7_spell_gate': 'newest',
    'hfo_p7_summoner': 'newest',
    'hfo_prey8_mcp_server': 'newest',  # one instance
    'mcp-server-sqlite': 'newest',     # one instance
}

groups = defaultdict(list)
for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        cmdline = ' '.join(p.info.get('cmdline') or [])
        for pattern in SAFE_KEEP_PATTERNS:
            if pattern in cmdline:
                groups[pattern].append({
                    'pid': p.pid,
                    'age_s': time.time() - p.info.get('create_time', time.time()),
                    'cmd': cmdline[-80:],
                })
                break
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

print("=== Duplicate daemon audit ===")
killed_total = 0
for pattern, procs in sorted(groups.items()):
    strategy = SAFE_KEEP_PATTERNS[pattern]
    procs.sort(key=lambda x: x['age_s'], reverse=(strategy == 'oldest'))
    # keep first, kill rest
    to_kill = procs[1:]
    tag = '✓ SINGLE' if len(procs) == 1 else f'!! {len(procs)}x → kill {len(to_kill)}'
    print(f"\n  [{pattern}]  {tag}")
    for pr in procs:
        keep_flag = '  KEEP' if pr == procs[0] else '  KILL'
        print(f"    PID {pr['pid']:6d}  age={pr['age_s']/60:.1f}m{keep_flag}  {pr['cmd']}")
    for pr in to_kill:
        try:
            proc = psutil.Process(pr['pid'])
            proc.terminate()
            killed_total += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

time.sleep(3)
# Force-kill stragglers
for pattern, procs in groups.items():
    procs.sort(key=lambda x: x['age_s'], reverse=(SAFE_KEEP_PATTERNS[pattern] == 'oldest'))
    for pr in procs[1:]:
        try:
            p = psutil.Process(pr['pid'])
            if p.is_running():
                p.kill()
        except:
            pass

print(f"\n=== Killed {killed_total} duplicate daemon processes ===")

# Final count
hfo_procs = []
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        cmd = ' '.join(p.info.get('cmdline') or [])
        if 'hfo_' in cmd:
            hfo_procs.append({'pid': p.pid, 'cmd': cmd[-70:]})
    except:
        pass
print(f"\n=== Remaining hfo_* processes: {len(hfo_procs)} ===")
for p in hfo_procs:
    print(f"  PID {p['pid']:6d}  {p['cmd']}")
