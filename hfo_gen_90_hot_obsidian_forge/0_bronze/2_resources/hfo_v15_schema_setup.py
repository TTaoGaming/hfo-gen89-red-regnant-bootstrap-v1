"""
hfo_v15_schema_setup.py

Creates obsidian_blackboard and spells tables in the SSOT SQLite database.
Populates the spells table with the 4 entries from hfo_grimoire.
Logs creation events to stigmergy.

HFO v15 bootstrap | PREY8 nonce E8CA8B | Gen90
Run from: c:\\hfoDev
"""

import sqlite3
import hashlib
import json
import datetime
import sys

DB_PATH = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'

def make_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()

def ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def log_stigmergy(conn, event_type: str, subject: str, data: dict) -> None:
    data_str = json.dumps(data)
    h = make_hash(event_type + subject + data_str)
    try:
        conn.execute(
            "INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_type, ts(), 'p7_spider_sovereign', subject, data_str, h)
        )
        conn.commit()
        print(f"  [stigmergy] {event_type} → {subject}")
    except sqlite3.IntegrityError:
        print(f"  [stigmergy] dup skipped: {event_type}")

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ── 1. obsidian_blackboard ────────────────────────────────────────────────
    print("\n[1] Creating obsidian_blackboard table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS obsidian_blackboard (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id    TEXT    NOT NULL,
            namespace   TEXT    NOT NULL DEFAULT 'default',
            key         TEXT    NOT NULL,
            value       TEXT,
            value_type  TEXT    NOT NULL DEFAULT 'string',
            session_id  TEXT,
            nonce       TEXT,
            updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(agent_id, namespace, key)
        )
    """)
    conn.commit()
    print("  obsidian_blackboard: CREATE OK")

    # Seed the blackboard with bootstrap metadata
    conn.execute("""
        INSERT OR REPLACE INTO obsidian_blackboard
            (agent_id, namespace, key, value, value_type, session_id, nonce, updated_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
    """, ('p7_spider_sovereign', 'v15', 'stryker_target', 'kalman_filter.ts',
          'string', '4c1fe92cae58f284', 'E8CA8B', ts()))
    conn.execute("""
        INSERT OR REPLACE INTO obsidian_blackboard
            (agent_id, namespace, key, value, value_type, session_id, nonce, updated_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
    """, ('p7_spider_sovereign', 'v15', 'stryker_threshold_low', '80',
          'number', '4c1fe92cae58f284', 'E8CA8B', ts()))
    conn.execute("""
        INSERT OR REPLACE INTO obsidian_blackboard
            (agent_id, namespace, key, value, value_type, session_id, nonce, updated_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
    """, ('p7_spider_sovereign', 'v15', 'tiles_queued',
          json.dumps(['kalman_filter.ts', 'event_bus.ts', 'plugin_supervisor.ts']),
          'json', '4c1fe92cae58f284', 'E8CA8B', ts()))
    conn.execute("""
        INSERT OR REPLACE INTO obsidian_blackboard
            (agent_id, namespace, key, value, value_type, session_id, nonce, updated_at)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
    """, ('p7_spider_sovereign', 'v15', 'tiles_hardened', json.dumps([]),
          'json', '4c1fe92cae58f284', 'E8CA8B', ts()))
    conn.commit()
    print("  obsidian_blackboard: seeded 4 bootstrap rows")

    log_stigmergy(conn, 'hfo.gen90.v15.schema.table_created',
                  'obsidian_blackboard',
                  {'table': 'obsidian_blackboard', 'columns': 9,
                   'seeded_rows': 4, 'session': '4c1fe92cae58f284', 'nonce': 'E8CA8B'})

    # ── 2. spells ────────────────────────────────────────────────────────────
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

    # Populate from grimoire
    grimoire_rows = conn.execute(
        "SELECT id, spell_name, dnd_seed, fca_archetype, hfo_mapping FROM hfo_grimoire"
    ).fetchall()

    spell_defs = [
        {
            'grimoire_id': grimoire_rows[0]['id'],
            'spell_name': grimoire_rows[0]['spell_name'],
            'incantation': 'Run: python hfo_perceive.py && npm run stryker mutate tile',
            'effect': grimoire_rows[0]['hfo_mapping'],
            'port_affinity': 'P4',
            'status': 'active',
            'meadows_level': 9,
            'tags': 'mutation,MAP-Elites,variation',
        },
        {
            'grimoire_id': grimoire_rows[1]['id'],
            'spell_name': grimoire_rows[1]['spell_name'],
            'incantation': 'Run: npx stryker run (with jest runner + thresholds)',
            'effect': grimoire_rows[1]['hfo_mapping'],
            'port_affinity': 'P5',
            'status': 'active',
            'meadows_level': 8,
            'tags': 'stryker,fitness-landscape,gate',
        },
        {
            'grimoire_id': grimoire_rows[2]['id'],
            'spell_name': grimoire_rows[2]['spell_name'],
            'incantation': 'Set stryker.config.json mutate=[] to target tile',
            'effect': grimoire_rows[2]['hfo_mapping'],
            'port_affinity': 'P2',
            'status': 'active',
            'meadows_level': 9,
            'tags': 'pareto,quality-diversity,MAP-Elites',
        },
        {
            'grimoire_id': grimoire_rows[3]['id'],
            'spell_name': grimoire_rows[3]['spell_name'],
            'incantation': 'Call prey8_perceive + prey8_yield to awaken a static tile',
            'effect': grimoire_rows[3]['hfo_mapping'],
            'port_affinity': 'P6',
            'status': 'active',
            'meadows_level': 13,
            'tags': 'PREY8,stigmergy,heredity,consciousness',
        },
    ]

    inserted = 0
    for sd in spell_defs:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO spells
                    (grimoire_id, spell_name, incantation, effect, port_affinity, status, meadows_level, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (sd['grimoire_id'], sd['spell_name'], sd['incantation'], sd['effect'],
                  sd['port_affinity'], sd['status'], sd['meadows_level'], sd['tags']))
            inserted += 1
        except sqlite3.Error as e:
            print(f"  [spells] insert error for {sd['spell_name']}: {e}")

    conn.commit()
    print(f"  spells: {inserted} rows inserted")

    log_stigmergy(conn, 'hfo.gen90.v15.schema.table_created',
                  'spells',
                  {'table': 'spells', 'columns': 10,
                   'rows_from_grimoire': inserted,
                   'session': '4c1fe92cae58f284', 'nonce': 'E8CA8B'})

    # ── 3. Verify ────────────────────────────────────────────────────────────
    print("\n[3] Verification...")
    for tname in ['obsidian_blackboard', 'spells', 'hfo_grimoire']:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tname,)
        ).fetchone()
        count = conn.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
        print(f"  {tname}: {'✓ EXISTS' if row else 'MISSING'} ({count} rows)")

    conn.close()
    print("\n[DONE] Schema setup complete.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
