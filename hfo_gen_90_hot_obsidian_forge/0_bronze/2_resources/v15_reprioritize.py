"""
v15_reprioritize.py — Feature-flag off phone-specific tiles, set launch queue.

LAUNCH STACK (TV/desktop path, no phone hardware needed):
  plugin_supervisor          — microkernel core, everything hangs off it
  gesture_fsm                — IDLE→READY→COMMIT_POINTER state machine
  w3c_pointer_fabric         — pointer fabric (uses KalmanFilter2D from hardened kalman_filter)
  symbiote_injector_plugin   — injects W3C pointer events into iframes
  visualization_plugin       — dot/ring state visualization + synesthesia visual
  wood_grain_tuning          — UserTuningProfile serialization (privacy-by-math)
  temporal_rollup            — self-writing ADR observability log

FEATURE_FLAGGED (phone-path, not needed to launch):
  foveated_cropper           — Pareto Pillar 1: 256x256 thermal crop (phone CPU only)
  biological_raycaster       — Pareto Pillar 1: anatomical ruler (phone-side scale-invariance)
  webrtc_udp_transport       — Pareto Pillar 2: needed only when phone→TV UDP path is live
  iframe_delivery_adapter    — Pareto Pillar 2: needed only with webrtc_udp_transport
"""

import sqlite3

DB = "C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"

LAUNCH_QUEUE = [
    # (tile_key, new_priority)  — highest priority = hardens next
    ("plugin_supervisor",       20),
    ("gesture_fsm",             19),
    ("w3c_pointer_fabric",      18),
    ("symbiote_injector_plugin",17),
    ("visualization_plugin",    16),
    ("wood_grain_tuning",       15),
    ("temporal_rollup",         14),
    # gesture_fsm_plugin last (still v15_target but WASM dependency)
    ("gesture_fsm_plugin",      13),
]

FEATURE_FLAGGED = [
    "foveated_cropper",
    "biological_raycaster",
    "webrtc_udp_transport",
    "iframe_delivery_adapter",
]

conn = sqlite3.connect(DB)
cur = conn.cursor()

print("== Setting launch queue priorities ==")
for tile_key, pri in LAUNCH_QUEUE:
    cur.execute(
        "UPDATE obsidian_blackboard SET priority=?, updated_at=datetime('now') WHERE tile_key=?",
        (pri, tile_key)
    )
    print(f"  pri={pri:2}  {tile_key}")

print("\n== Feature-flagging phone-path tiles ==")
for tile_key in FEATURE_FLAGGED:
    cur.execute(
        "UPDATE obsidian_blackboard SET status='feature_flagged', priority=0, updated_at=datetime('now') WHERE tile_key=?",
        (tile_key,)
    )
    print(f"  [feature_flagged]  {tile_key}")

conn.commit()

# Print the revised manifest
print("\n\n=== REVISED TILE MANIFEST ===\n")
STATUS_ORDER = (
    "CASE status "
    "WHEN 'hardened'        THEN 0 "
    "WHEN 'v15_target'      THEN 1 "
    "WHEN 'v13_antipattern' THEN 2 "
    "WHEN 'v13_potemkin'    THEN 3 "
    "WHEN 'feature_flagged' THEN 4 "
    "ELSE 5 END, priority DESC"
)
rows = cur.execute(
    f"SELECT tile_key, status, stryker_score, priority FROM obsidian_blackboard ORDER BY {STATUS_ORDER}"
).fetchall()

counts: dict[str, int] = {}
for r in rows:
    counts[r[0].split()[0] if False else r[1]] = counts.get(r[1], 0) + 1

cur_status = None
for tile_key, status, score, priority in rows:
    if status != cur_status:
        cur_status = status
        print(f"\n  ── {cur_status} ({counts[cur_status]}) ──")
    s = f"{score:.1f}%" if score else "--"
    print(f"  pri={priority:2}  {tile_key:35}  {s}")

conn.close()
