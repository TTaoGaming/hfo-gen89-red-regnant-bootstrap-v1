"""
hfo_v15_update_scores.py
Update obsidian_blackboard with final Stryker scores and log hardening events.
Session: PREY8 nonce E8CA8B | Gen90
"""
import sqlite3, json, hashlib, datetime, pathlib

DB = pathlib.Path("C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")

def ts():
    return datetime.datetime.utcnow().isoformat() + "Z"

def content_hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
now = ts()

# ── 1. Update obsidian_blackboard ────────────────────────────────────────────
tiles = [
    {"key": "kalman_filter",  "score": 95.08, "killed": 56, "survived": 3,  "total": 61},
    {"key": "event_bus",      "score": 84.31, "killed": 43, "survived": 8,  "total": 51},
]

for t in tiles:
    status = "hardened"
    notes = (
        f"Stryker {t['score']:.2f}% | {t['killed']}/{t['total']} killed | "
        f"{t['survived']} survived | coverageAnalysis=all | "
        f"session=4c1fe92cae58f284 nonce=E8CA8B"
    )
    cur.execute(
        """UPDATE obsidian_blackboard
           SET stryker_score=?, status=?, notes=?, updated_at=?
           WHERE tile_key=?""",
        (t["score"], status, notes, now, t["key"]),
    )
    print(f"  [obsidian_blackboard] {t['key']:20s} -> {status} ({t['score']:.2f}%)")

# ── 2. Log stigmergy events ──────────────────────────────────────────────────
events = [
    {
        "event_type": "hfo.gen90.v15.tile_hardened",
        "subject": "kalman_filter.ts",
        "data": {
            "tile_key": "kalman_filter",
            "stryker_score": 95.08,
            "killed": 56, "survived": 3, "total": 61,
            "coverage_analysis": "all",
            "session": "4c1fe92cae58f284",
            "nonce": "E8CA8B",
            "test_file": "test_kalman_filter.test.ts",
            "threshold_met": True,
            "target_range": "80-99%",
            "agent": "p7_spider_sovereign",
        },
    },
    {
        "event_type": "hfo.gen90.v15.tile_hardened",
        "subject": "event_bus.ts",
        "data": {
            "tile_key": "event_bus",
            "stryker_score": 84.31,
            "killed": 43, "survived": 8, "total": 51,
            "coverage_analysis": "all",
            "session": "4c1fe92cae58f284",
            "nonce": "E8CA8B",
            "test_file": "test_event_bus.test.ts",
            "threshold_met": True,
            "target_range": "80-99%",
            "agent": "p7_spider_sovereign",
        },
    },
    {
        "event_type": "hfo.gen90.v15.stryker_config_fix",
        "subject": "stryker.config.json",
        "data": {
            "change": "coverageAnalysis perTest->all fixes NODE_ENV-gated branch coverage",
            "impact": "event_bus.ts jumped from 78.43% to 84.31%",
            "session": "4c1fe92cae58f284",
            "nonce": "E8CA8B",
            "agent": "p7_spider_sovereign",
        },
    },
]

for ev in events:
    data_json = json.dumps(ev["data"])
    chash = content_hash({"type": ev["event_type"], "subject": ev["subject"], "ts": now})
    try:
        cur.execute(
            """INSERT INTO stigmergy_events
               (event_type, timestamp, source, subject, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ev["event_type"], now, "p7_spider_sovereign", ev["subject"], data_json, chash),
        )
        print(f"  [stigmergy] {ev['event_type']} → {ev['subject']}")
    except sqlite3.IntegrityError as e:
        print(f"  [stigmergy] SKIP (dupe): {e}")

conn.commit()
conn.close()

print("\n✅ Done. Both tiles hardened in obsidian_blackboard, 3 events in stigmergy.")
