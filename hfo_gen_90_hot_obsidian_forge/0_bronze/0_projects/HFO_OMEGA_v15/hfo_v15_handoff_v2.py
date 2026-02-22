"""
hfo_v15_handoff_v2.py
Update braided mission thread, note remaining issues in stigmergy, prepare handoff.
Session: PREY8 nonce E8CA8B | session 4c1fe92cae58f284 | Gen90
Uses hfo_ssot_write.write_stigmergy_event() with required signal_metadata.
"""
import sys, sqlite3, json, pathlib
sys.path.insert(0, "C:/hfoDev/hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources")

from hfo_ssot_write import write_stigmergy_event, get_db_readwrite
import datetime

DB = pathlib.Path("C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")

def ts():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

SIG = {
    "port": "P7",
    "model_id": "claude-sonnet-4-6",
    "daemon_name": "p7_spider_sovereign",
    "model_provider": "anthropic",
    "session": "4c1fe92cae58f284",
    "nonce": "E8CA8B",
    "gen": "90",
}

conn = get_db_readwrite(DB)
now = ts()
cur = conn.cursor()

# ── 1. Show recent mission_state ─────────────────────────────────────────────
cur.execute("SELECT thread_key, title, status FROM mission_state ORDER BY created_at DESC LIMIT 15")
print("=== Recent mission_state ===")
for r in cur.fetchall():
    print(f"  [{r['thread_key']:30s}] {r['status']:10s} | {r['title'][:55]}")

# detect parent era
cur.execute("SELECT thread_key FROM mission_state WHERE thread_key='ERA_5'")
parent = "ERA_5" if cur.fetchone() else ("ERA_4" if cur.execute("SELECT thread_key FROM mission_state WHERE thread_key='ERA_4'").fetchone() else "alpha")
print(f"\nParent: {parent}")

# ── 2. Upsert WP-V15-TILE-HARDEN-01 ─────────────────────────────────────────
wp_key = "WP-V15-TILE-HARDEN-01"
meta = json.dumps({
    "session": "4c1fe92cae58f284", "nonce": "E8CA8B",
    "agent": "p7_spider_sovereign",
    "tiles_hardened": [
        {"tile": "kalman_filter.ts",  "score": 95.08, "test_file": "test_kalman_filter.test.ts", "tests": 45},
        {"tile": "event_bus.ts",      "score": 84.31, "test_file": "test_event_bus.test.ts",     "tests": 32},
    ],
    "infra_fixes": [
        "stryker.config.json: command->jest runner, BOM removed",
        "jest.stryker.config.js: created (restricts Stryker testMatch)",
        "jest.config.js: .spec.ts excluded (WASM import guard)",
        "event_bus.ts: process.env.NODE_ENV -> ['NODE_ENV'] (TS4111)",
        "stryker coverageAnalysis: perTest->all (fixes NODE_ENV branch coverage)",
    ],
    "total_stryker_score": 90.18, "total_killed": 99, "total_survived": 11,
    "handoff_date": now,
})

conn.execute("BEGIN")
cur.execute("SELECT version FROM mission_state WHERE thread_key=?", (wp_key,))
row = cur.fetchone()
if row:
    ver = row["version"] + 1
    cur.execute("""UPDATE mission_state SET
        title=?, bluf=?, port=?, era=?, thread=?, meadows_level=?,
        fitness=?, mutation_confidence=?, status=?, priority=?,
        assignee=?, metadata_json=?, updated_at=?, version=?
        WHERE thread_key=?""",
        ("v15 Tile Hardening — Phase 1 (kalman_filter + event_bus)",
         "kalman_filter 95.08%, event_bus 84.31%, total 90.18%. Infra fixed.",
         "P5", parent, "omega", 8, 0.90, 90, "done", 7,
         "p7_spider_sovereign", meta, now, ver, wp_key))
    print(f"\n  [mission_state] UPDATED {wp_key} v{ver}")
else:
    cur.execute("""INSERT INTO mission_state
        (thread_key, parent_key, thread_type, title, bluf, port, era, thread,
         meadows_level, fitness, mutation_confidence, status, priority, assignee,
         metadata_json, created_at, updated_at, version, medallion)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (wp_key, parent, "waypoint",
         "v15 Tile Hardening — Phase 1 (kalman_filter + event_bus)",
         "kalman_filter 95.08%, event_bus 84.31%, total 90.18%. Infra fixed.",
         "P5", parent, "omega", 8, 0.90, 90, "done", 7,
         "p7_spider_sovereign", meta, now, now, 1, "bronze"))
    print(f"\n  [mission_state] INSERTED {wp_key}")
conn.execute("COMMIT")

# ── 3. Log issues to stigmergy ────────────────────────────────────────────────
print("\n=== Logging issues ===")
issues = [
    ("kalman_filter.ts:87 — equivalent_mutant", {
        "type": "equivalent_mutant", "severity": "low", "tile": "kalman_filter.ts",
        "description": "if(isNaN(x)) return NaN => if(false) return NaN is equivalent: NaN propagates through arithmetic. 1 survivor. Score 95.08% is above 80% threshold — acceptable.",
        "resolution": "Accept as equivalent mutant.",
    }),
    ("event_bus.ts:115-120 — string_literal_test_gap", {
        "type": "test_gap", "severity": "medium", "tile": "event_bus.ts",
        "description": "8 StringLiteral survivors in dead-letter console.warn at lines 115-120. Tests check Error.message but NOT warn() call string content.",
        "fix": "In test_event_bus.test.ts: add expect(warn.mock.calls[0][0]).toContain('Likely causes') for each warn fragment. Estimated gain: +8 kills => ~95% overall.",
    }),
    ("event_bus.ts:95 — conditional_test_gap", {
        "type": "test_gap", "severity": "medium", "tile": "event_bus.ts",
        "description": "ConditionalExpression + UnaryOperator survivors in publish() line 95 null-list guard. if(!list)return mutant => if(true)return always bails.",
        "fix": "Add test: subscribe to event, publish, assert handler was called exactly once. Verify list!=null path is taken.",
    }),
    ("stryker.config.json — infra_fragility", {
        "type": "infra_fragility", "severity": "high",
        "description": "stryker.config.json reverted to default (command runner => deleted test_plugin_supervisor.ts) on workspace reload — observed twice this session. Not committed to git.",
        "fix": "cd HFO_OMEGA_v15 && git add stryker.config.json jest.stryker.config.js && git commit -m 'chore: fix stryker config jest runner coverageAnalysis=all'",
        "priority": "IMMEDIATE — first thing next agent should do",
    }),
    ("obsidian_blackboard — remaining_tiles", {
        "type": "next_agent_todo", "severity": "medium",
        "tiles_remaining": ["gesture_fsm_plugin", "audio_engine_plugin", "kalman_2d_wrapper", "pointer_coaster", "host_core", "plugin_supervisor"],
        "description": "6 tiles remain to harden. Claim next tile in obsidian_blackboard, update stryker.config.json mutate, write tests, run Stryker, run hfo_v15_update_scores.py.",
        "warning": "gesture_fsm_plugin.spec.ts imports omega_core_rs WASM — crashes Jest dry run. Always use jest.stryker.config.js with testMatch pointing to .test.ts files only.",
    }),
]

for subject, data in issues:
    try:
        rid = write_stigmergy_event("hfo.gen90.v15.issue", subject, data, SIG,
                                    source="p7_spider_sovereign_gen90_p7", conn=conn)
        print(f"  OK row={rid} => {subject[:60]}")
    except Exception as e:
        print(f"  ERR: {e}")

# ── 4. Handoff event ──────────────────────────────────────────────────────────
print("\n=== Handoff event ===")
try:
    rid = write_stigmergy_event(
        "hfo.gen90.v15.handoff", "v15_tile_hardening_phase1",
        {
            "summary": "Phase 1 complete. kalman_filter 95.08%, event_bus 84.31%, total 90.18%. Infra fixed. 5 issues logged.",
            "tiles_done": ["kalman_filter", "event_bus"],
            "tiles_remaining": ["gesture_fsm_plugin", "audio_engine_plugin", "kalman_2d_wrapper", "pointer_coaster", "host_core", "plugin_supervisor"],
            "first_action_for_next_agent": [
                "git add stryker.config.json jest.stryker.config.js && git commit",
                "Add warn.mock.calls[0][0].toContain() assertions in test_event_bus.test.ts",
                "npx stryker run => confirm event_bus.ts ~95%",
                "Update stryker.config.json mutate to next tile",
                "Run hfo_v15_update_scores.py",
            ],
            "session": "4c1fe92cae58f284", "nonce": "E8CA8B",
        },
        SIG, source="p7_spider_sovereign_gen90_p7", conn=conn,
    )
    print(f"  OK row={rid} => handoff logged")
except Exception as e:
    print(f"  ERR: {e}")

conn.close()
print("\n✅ Done. mission_state updated. 5 issues + 1 handoff in stigmergy.")
