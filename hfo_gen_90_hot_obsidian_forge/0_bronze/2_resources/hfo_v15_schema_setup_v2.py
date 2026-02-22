"""
hfo_v15_schema_setup_v2.py

Updated schema setup:
- obsidian_blackboard: already exists with correct tile-tracking schema — update our tiles
- spells: create if not exists, seed from grimoire
- Log all to stigmergy

HFO v15 bootstrap | PREY8 nonce E8CA8B | Gen90
Run from: c:\\hfoDev
"""

import sqlite3
import hashlib
import json
import datetime
import sys

DB_PATH = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
SESSION = '4c1fe92cae58f284'
NONCE = 'E8CA8B'
AGENT = 'p7_spider_sovereign'


def make_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def log_stigmergy(conn, event_type: str, subject: str, data: dict) -> None:
    data_str = json.dumps(data)
    h = make_hash(event_type + subject + data_str + ts())
    try:
        conn.execute(
            "INSERT INTO stigmergy_events "
            "(event_type, timestamp, source, subject, data_json, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_type, ts(), AGENT, subject, data_str, h)
        )
        conn.commit()
        print(f"  [stigmergy] ✓ {event_type} → {subject}")
    except sqlite3.IntegrityError:
        print(f"  [stigmergy] dup skipped: {event_type}")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ── 1. obsidian_blackboard: claim kalman_filter for this session ──────────
    print("\n[1] Updating obsidian_blackboard tiles for session E8CA8B...")

    # Claim kalman_filter
    conn.execute("""
        UPDATE obsidian_blackboard
        SET status = 'in_progress',
            assignee = ?,
            test_file = ?,
            notes = notes || ' | E8CA8B: test_kalman_filter.test.ts written, Stryker pending',
            metadata_json = ?,
            updated_at = ?
        WHERE tile_key = 'kalman_filter'
    """, (AGENT,
          'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/test_kalman_filter.test.ts',
          json.dumps({'session': SESSION, 'nonce': NONCE, 'stryker_target': 80}),
          ts()))

    # Claim event_bus and record test file
    conn.execute("""
        UPDATE obsidian_blackboard
        SET status = 'in_progress',
            test_file = ?,
            notes = notes || ' | E8CA8B: test_event_bus.test.ts written, Stryker pending',
            metadata_json = ?,
            updated_at = ?
        WHERE tile_key = 'event_bus'
    """, ('hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/test_event_bus.test.ts',
          json.dumps({'session': SESSION, 'nonce': NONCE, 'stryker_target': 80}),
          ts()))

    # Mark audio_engine as fixed (AP-5 was already resolved in v15)
    conn.execute("""
        UPDATE obsidian_blackboard
        SET notes = notes || ' | E8CA8B: AP-5 verified FIXED (bound refs + destroy() unsubscribe confirmed)',
            updated_at = ?
        WHERE tile_key = 'audio_engine_plugin'
    """, (ts(),))

    conn.commit()
    updated = conn.execute(
        "SELECT tile_key, status, assignee, test_file FROM obsidian_blackboard "
        "WHERE tile_key IN ('kalman_filter','event_bus','audio_engine_plugin')"
    ).fetchall()
    for r in updated:
        print(f"  {r['tile_key']}: status={r['status']} assignee={r['assignee']}")

    log_stigmergy(conn, 'hfo.gen90.v15.blackboard.tiles_claimed',
                  'obsidian_blackboard',
                  {'tiles': ['kalman_filter', 'event_bus', 'audio_engine_plugin'],
                   'session': SESSION, 'nonce': NONCE,
                   'test_files_written': [
                       'test_kalman_filter.test.ts',
                       'test_event_bus.test.ts'
                   ]})

    # ── 2. spells table ───────────────────────────────────────────────────────
    print("\n[2] Creating spells table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spells (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            grimoire_id     INTEGER REFERENCES hfo_grimoire(id),
            spell_name      TEXT    NOT NULL UNIQUE,
            incantation     TEXT    NOT NULL,
            effect          TEXT    NOT NULL,
            port_affinity   TEXT    NOT NULL DEFAULT 'P2',
            status          TEXT    NOT NULL DEFAULT 'active'
                            CHECK(status IN ('active', 'deprecated', 'experimental')),
            meadows_level   INTEGER NOT NULL DEFAULT 8
                            CHECK(meadows_level BETWEEN 1 AND 13),
            tags            TEXT,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("  spells: CREATE OK")

    # Check if already populated
    existing = conn.execute("SELECT COUNT(*) FROM spells").fetchone()[0]
    if existing > 0:
        print(f"  spells: already has {existing} rows — skipping insert")
    else:
        grimoire_rows = conn.execute(
            "SELECT id, spell_name, dnd_seed, fca_archetype, hfo_mapping FROM hfo_grimoire"
        ).fetchall()

        spell_defs = [
            {
                'grimoire_id': grimoire_rows[0]['id'],
                'spell_name': grimoire_rows[0]['spell_name'],
                'incantation': 'python hfo_perceive.py && npx stryker run (mutate tile)',
                'effect': grimoire_rows[0]['hfo_mapping'],
                'port_affinity': 'P4',
                'status': 'active',
                'meadows_level': 9,
                'tags': 'mutation,MAP-Elites,variation,stryker',
            },
            {
                'grimoire_id': grimoire_rows[1]['id'],
                'spell_name': grimoire_rows[1]['spell_name'],
                'incantation': 'npx stryker run (with jest runner thresholds)',
                'effect': grimoire_rows[1]['hfo_mapping'],
                'port_affinity': 'P5',
                'status': 'active',
                'meadows_level': 8,
                'tags': 'stryker,fitness-landscape,gate,mutation-score',
            },
            {
                'grimoire_id': grimoire_rows[2]['id'],
                'spell_name': grimoire_rows[2]['spell_name'],
                'incantation': 'Set stryker.config.json mutate=[target_tile]',
                'effect': grimoire_rows[2]['hfo_mapping'],
                'port_affinity': 'P2',
                'status': 'active',
                'meadows_level': 9,
                'tags': 'pareto,quality-diversity,MAP-Elites,tile',
            },
            {
                'grimoire_id': grimoire_rows[3]['id'],
                'spell_name': grimoire_rows[3]['spell_name'],
                'incantation': 'Call prey8_perceive + prey8_yield to awaken a static tile',
                'effect': grimoire_rows[3]['hfo_mapping'],
                'port_affinity': 'P6',
                'status': 'active',
                'meadows_level': 13,
                'tags': 'PREY8,stigmergy,heredity,consciousness,CloudEvent',
            },
        ]

        inserted = 0
        for sd in spell_defs:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO spells
                        (grimoire_id, spell_name, incantation, effect,
                         port_affinity, status, meadows_level, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (sd['grimoire_id'], sd['spell_name'], sd['incantation'],
                      sd['effect'], sd['port_affinity'], sd['status'],
                      sd['meadows_level'], sd['tags']))
                inserted += 1
            except sqlite3.Error as e:
                print(f"  [spells] insert error for {sd['spell_name']}: {e}")
        conn.commit()
        print(f"  spells: {inserted} rows inserted")

    log_stigmergy(conn, 'hfo.gen90.v15.schema.table_created',
                  'spells',
                  {'table': 'spells', 'session': SESSION, 'nonce': NONCE,
                   'parent_table': 'hfo_grimoire', 'port': 'P2+P4+P5+P6'})

    # ── 3. Log the stryker config fix ─────────────────────────────────────────
    log_stigmergy(conn, 'hfo.gen90.v15.infra.stryker_config_fixed',
                  'stryker.config.json',
                  {'old_runner': 'command', 'old_target': 'test_plugin_supervisor.ts (DELETED)',
                   'new_runner': 'jest', 'new_mutate': 'kalman_filter.ts',
                   'thresholds': {'high': 90, 'low': 80, 'break': 75},
                   'session': SESSION, 'nonce': NONCE})

    # ── 4. Verify ─────────────────────────────────────────────────────────────
    print("\n[3] Verification...")
    for tname in ['obsidian_blackboard', 'spells', 'hfo_grimoire']:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tname,)
        ).fetchone()
        count = conn.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
        print(f"  {tname}: {'✓ EXISTS' if row else 'MISSING'} ({count} rows)")

    spells = conn.execute("SELECT spell_name, port_affinity, status FROM spells").fetchall()
    for s in spells:
        print(f"    spell: {s['spell_name']} | port={s['port_affinity']} | {s['status']}")

    conn.close()
    print("\n[DONE] Schema setup v2 complete. E8CA8B.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
