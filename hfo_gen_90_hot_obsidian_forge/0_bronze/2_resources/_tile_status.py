import sqlite3

DB = "C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"

STATUS_ORDER = (
    "CASE status "
    "WHEN 'hardened'        THEN 0 "
    "WHEN 'v15_target'      THEN 1 "
    "WHEN 'v13_antipattern' THEN 2 "
    "WHEN 'v13_potemkin'    THEN 3 "
    "ELSE 4 END, priority DESC"
)

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

rows = db.execute(
    f"SELECT tile_key, status, stryker_score, priority "
    f"FROM obsidian_blackboard ORDER BY {STATUS_ORDER}"
).fetchall()

counts: dict[str, int] = {}
for r in rows:
    counts[r["status"]] = counts.get(r["status"], 0) + 1

print(f"Total: {len(rows)} tiles")

cur_status = None
for r in rows:
    if r["status"] != cur_status:
        cur_status = r["status"]
        print(f"\n  ── {cur_status} ({counts[cur_status]}) ──")
    score = f"{r['stryker_score']:.1f}%" if r["stryker_score"] else "--"
    print(f"  pri={r['priority']:2}  {r['tile_key']:35}  {score}")

db.close()
