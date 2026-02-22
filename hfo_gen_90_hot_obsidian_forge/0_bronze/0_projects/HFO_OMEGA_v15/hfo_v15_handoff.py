"""
hfo_v15_handoff.py
Update braided mission thread, note remaining issues in stigmergy, prepare handoff.
Session: PREY8 nonce E8CA8B | session 4c1fe92cae58f284 | Gen90
"""
import sqlite3, json, hashlib, datetime, pathlib

DB = pathlib.Path("C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")

def ts():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def chash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
now = ts()

# ── 1. Check current ERA_5 / v15 thread state ────────────────────────────────
cur.execute("SELECT thread_key, title, status, bluf, updated_at FROM mission_state ORDER BY created_at DESC LIMIT 20")
rows = cur.fetchall()
print("=== Recent mission_state rows ===")
for r in rows:
    print(f"  [{r['thread_key']:30s}] {r['status']:10s} | {r['title'][:60]}")

# ── 2. Upsert v15 tile-hardening waypoint ────────────────────────────────────
waypoints = [
    {
        "thread_key": "WP-V15-TILE-HARDEN-01",
        "parent_key": "ERA_5",         # will fall back to ERA_4 if ERA_5 missing
        "thread_type": "waypoint",
        "title": "v15 Tile Hardening — Phase 1 (kalman_filter + event_bus)",
        "bluf": "Two tiles hardened to Stryker 80-99%: kalman_filter 95.08%, event_bus 84.31%. Infra fixed (jest runner, coverageAnalysis=all, BOM removed).",
        "port": "P5",
        "era": "ERA_5",
        "thread": "omega",
        "meadows_level": 8,
        "fitness": 0.90,
        "mutation_confidence": 90,
        "status": "done",
        "priority": 7,
        "assignee": "p7_spider_sovereign",
        "metadata_json": json.dumps({
            "session": "4c1fe92cae58f284",
            "nonce": "E8CA8B",
            "agent": "p7_spider_sovereign",
            "tiles_hardened": [
                {"tile": "kalman_filter.ts",  "score": 95.08, "test_file": "test_kalman_filter.test.ts", "tests": 45},
                {"tile": "event_bus.ts",      "score": 84.31, "test_file": "test_event_bus.test.ts",     "tests": 32},
            ],
            "infra_fixes": [
                "stryker.config.json: command->jest runner, BOM removed",
                "jest.stryker.config.js: created (restricts Stryker testMatch)",
                "jest.config.js: .spec.ts files excluded (WASM import guard)",
                "event_bus.ts: process.env.NODE_ENV -> process.env['NODE_ENV'] (TS4111)",
                "stryker coverageAnalysis: perTest->all (fixes NODE_ENV-gated branch coverage)",
            ],
            "total_stryker_score": 90.18,
            "total_killed": 99,
            "total_survived": 11,
            "handoff_date": now,
        }),
    },
]

# Check if ERA_5 exists, else use ERA_4 as parent
cur.execute("SELECT thread_key FROM mission_state WHERE thread_key='ERA_5'")
era5 = cur.fetchone()
cur.execute("SELECT thread_key FROM mission_state WHERE thread_key='ERA_4'")
era4 = cur.fetchone()
parent = "ERA_5" if era5 else ("ERA_4" if era4 else "alpha")
print(f"\nUsing parent: {parent}")

for wp in waypoints:
    wp["parent_key"] = parent
    cur.execute("SELECT version FROM mission_state WHERE thread_key=?", (wp["thread_key"],))
    existing = cur.fetchone()
    if existing:
        ver = existing["version"] + 1
        cur.execute("""
            UPDATE mission_state SET
                title=?, bluf=?, port=?, era=?, thread=?, meadows_level=?,
                fitness=?, mutation_confidence=?, status=?, priority=?,
                assignee=?, metadata_json=?, updated_at=?, version=?
            WHERE thread_key=?
        """, (
            wp["title"], wp["bluf"], wp["port"], wp["era"], wp["thread"],
            wp["meadows_level"], wp["fitness"], wp["mutation_confidence"],
            wp["status"], wp["priority"], wp["assignee"], wp["metadata_json"],
            now, ver, wp["thread_key"]
        ))
        print(f"  [mission_state] UPDATED {wp['thread_key']} v{ver}")
    else:
        cur.execute("""
            INSERT INTO mission_state
            (thread_key, parent_key, thread_type, title, bluf, port, era,
             thread, meadows_level, fitness, mutation_confidence, status,
             priority, assignee, metadata_json, created_at, updated_at, version, medallion)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            wp["thread_key"], wp["parent_key"], wp["thread_type"],
            wp["title"], wp["bluf"], wp["port"], wp["era"], wp["thread"],
            wp["meadows_level"], wp["fitness"], wp["mutation_confidence"],
            wp["status"], wp["priority"], wp["assignee"], wp["metadata_json"],
            now, now, 1, "bronze"
        ))
        print(f"  [mission_state] INSERTED {wp['thread_key']}")

# ── 3. Log remaining issues as stigmergy events ───────────────────────────────
remaining_issues = [
    {
        "subject": "kalman_filter.ts:87",
        "issue": "1 equivalent mutant: `if (isNaN(this.x)) return NaN` → `if (false) return NaN`. "
                 "NaN propagates through arithmetic regardless, making this mutation undetectable. "
                 "Consider refactoring to different guard or accept as equivalent.",
        "severity": "low",
        "type": "equivalent_mutant",
    },
    {
        "subject": "kalman_filter.ts:57,62,75",
        "issue": "3 arithmetic operator survivors on init/prediction/covariance paths. "
                 "Exact-value tests with C=2 kill 95% but 3 remain likely-equivalent due to "
                 "default param symmetry (A=1, B=0). Score 95.08% — above threshold, acceptable.",
        "severity": "low",
        "type": "equivalent_mutant",
    },
    {
        "subject": "event_bus.ts:115-120",
        "issue": "8 StringLiteral survivors in dead-letter console.warn message lines 115-120. "
                 "Stryker mutates each string fragment to empty string ''. Tests check .toContain() "
                 "on the full Error message but NOT on the warn() multi-line template literal. "
                 "Fix: add .toContain() assertions for each fragment line in test_event_bus.test.ts.",
        "severity": "medium",
        "type": "test_gap",
        "fix": "Add toContain checks: 'Likely causes', 'Subscriber plugin', 'Wrong bus', 'Plugin destroyed', 'Fix: verify'",
        "estimated_score_gain": "+8 killed → event_bus ~100% → overall ~95%",
    },
    {
        "subject": "event_bus.ts:95",
        "issue": "ConditionalExpression + UnaryOperator survivors in publish() guard. "
                 "Line 95: `if (!list) return`. Mutant: `if (true) return` always returns early. "
                 "Test gap: no assertion that publish() DOES NOT return early when subscribers exist. "
                 "Fix: subscribe handler and assert it WAS called after publish, in a test that "
                 "covers the exact list!=null branch path.",
        "severity": "medium",
        "type": "test_gap",
        "fix": "Add explicit test: subscribe to event, publish, assert handler called exactly once (verifies list was not null)",
    },
    {
        "subject": "stryker_infra",
        "issue": "stryker.config.json not committed to git — reverts on workspace reload (observed twice). "
                 "Root cause: file is recreated from package.json default on npm commands. "
                 "Fix: ensure stryker.config.json is in .gitignore EXCLUDED list, or commit it explicitly.",
        "severity": "high",
        "type": "infra_fragility",
        "fix": "git add stryker.config.json jest.stryker.config.js && git commit",
    },
    {
        "subject": "obsidian_blackboard",
        "issue": "6 tiles remain in 'not_started' or 'queued' status: gesture_fsm_plugin, "
                 "audio_engine_plugin, kalman_2d_wrapper, pointer_coaster, host_core, plugin_supervisor. "
                 "Next agent should claim and harden these in priority order.",
        "severity": "medium",
        "type": "next_agent_todo",
        "fix": "Run: SELECT tile_key, status, priority FROM obsidian_blackboard WHERE status != 'hardened' ORDER BY priority DESC",
    },
]

for issue in remaining_issues:
    data = {
        "session": "4c1fe92cae58f284",
        "nonce": "E8CA8B",
        "agent": "p7_spider_sovereign",
        "severity": issue["severity"],
        "type": issue["type"],
        "description": issue["issue"],
    }
    if "fix" in issue:
        data["fix"] = issue["fix"]
    if "estimated_score_gain" in issue:
        data["estimated_score_gain"] = issue["estimated_score_gain"]

    h = chash({"type": "hfo.gen90.v15.issue", "subject": issue["subject"], "ts": now})
    try:
        cur.execute("""
            INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash)
            VALUES (?,?,?,?,?,?)
        """, ("hfo.gen90.v15.issue", now, "p7_spider_sovereign", issue["subject"],
               json.dumps(data), h))
        print(f"  [stigmergy] issue logged → {issue['subject']} [{issue['severity']}]")
    except sqlite3.IntegrityError as e:
        print(f"  [stigmergy] SKIP dupe: {e}")

# ── 4. Log handoff event ──────────────────────────────────────────────────────
handoff_data = {
    "session": "4c1fe92cae58f284",
    "nonce": "E8CA8B",
    "agent": "p7_spider_sovereign",
    "handoff_to": "next_agent",
    "summary": "Phase 1 tile hardening complete. 2 tiles hardened (kalman_filter 95.08%, event_bus 84.31%). "
               "Total score 90.18%. Infrastructure fixed. 5 remaining issues logged. "
               "Next priority: harden event_bus.ts string-literal gaps (+~8 kills), then tackle gesture_fsm_plugin.",
    "tiles_done": ["kalman_filter", "event_bus"],
    "tiles_remaining": ["gesture_fsm_plugin", "audio_engine_plugin", "kalman_2d_wrapper", "pointer_coaster", "host_core", "plugin_supervisor"],
    "first_action_for_next_agent": (
        "1. git add stryker.config.json jest.stryker.config.js && git commit  "
        "2. Add console.warn string fragment toContain() tests in test_event_bus.test.ts  "
        "3. Run Stryker to verify event_bus.ts hits ~95%  "
        "4. Update stryker.config.json mutate to next tile  "
        "5. Run hfo_v15_update_scores.py to record scores"
    ),
}
hh = chash({"type": "hfo.gen90.v15.handoff", "session": "4c1fe92cae58f284"})
try:
    cur.execute("""
        INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash)
        VALUES (?,?,?,?,?,?)
    """, ("hfo.gen90.v15.handoff", now, "p7_spider_sovereign", "v15_tile_hardening_phase1",
           json.dumps(handoff_data), hh))
    print(f"\n  [stigmergy] HANDOFF event logged")
except sqlite3.IntegrityError as e:
    print(f"  [stigmergy] SKIP dupe: {e}")

conn.commit()
conn.close()
print("\n✅ Handoff complete. Braided thread updated. Issues + handoff logged to stigmergy.")
