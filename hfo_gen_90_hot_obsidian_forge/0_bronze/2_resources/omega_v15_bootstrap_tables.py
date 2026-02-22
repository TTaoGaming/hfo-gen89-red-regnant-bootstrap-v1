"""
HFO Gen90 — Omega v15 Coordination Tables Bootstrap
Creates:
  - obsidian_blackboard: multi-agent tile porting coordination surface
  - spells: active/deployable spell registry linked to hfo_grimoire
Registers initial v15 tiles on the blackboard.
Session: b75409a13f6a39c8 | Nonce: 848CD7 | React: 9A4D7C
Meadows L8: Establishing governance rules for v15 tile porting
"""
import sqlite3, json
from datetime import datetime, timezone

DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
NOW = datetime.now(timezone.utc).isoformat()

conn = sqlite3.connect(DB)

# ── OBSIDIAN BLACKBOARD ─────────────────────────────────────────────────────
# Multi-agent shared coordination surface. Each tile gets a row.
# Agents claim tiles before porting, update stryker_score on completion.
conn.execute("""
CREATE TABLE IF NOT EXISTS obsidian_blackboard (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tile_key        TEXT NOT NULL UNIQUE,   -- e.g. 'event_bus', 'plugin_supervisor'
    source_file     TEXT,                   -- relative path in HFO_OMEGA_v15
    status          TEXT NOT NULL DEFAULT 'unvalidated',
                                            -- unvalidated | claimed | hardening | passed | blocked
    assignee        TEXT,                   -- agent_id claiming the tile
    stryker_score   REAL DEFAULT 0.0,       -- 0.0-100.0; target 80-99 (goldilocks)
    test_file       TEXT,                   -- path to test file for this tile
    priority        INTEGER DEFAULT 50,     -- lower = higher priority
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    metadata_json   TEXT DEFAULT '{}'
)
""")

# ── SPELLS TABLE ────────────────────────────────────────────────────────────
# Active/deployable spells — subset of hfo_grimoire linked to concrete tiles.
# Each spell tracks which code tile it animates and its current activation status.
conn.execute("""
CREATE TABLE IF NOT EXISTS spells (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    spell_key       TEXT NOT NULL UNIQUE,   -- e.g. 'origin_of_species_event_bus'
    grimoire_id     INTEGER REFERENCES hfo_grimoire(id),
    spell_name      TEXT NOT NULL,          -- human-readable name
    fca_archetype   TEXT,                   -- from hfo_grimoire
    target_tile     TEXT,                   -- FK to obsidian_blackboard.tile_key
    status          TEXT NOT NULL DEFAULT 'dormant',
                                            -- dormant | active | crystallized | deprecated
    activation_level TEXT DEFAULT 'bronze', -- bronze | silver | gold
    stryker_score   REAL DEFAULT 0.0,
    activated_at    TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    metadata_json   TEXT DEFAULT '{}'
)
""")

conn.commit()
print("✓ Created obsidian_blackboard table")
print("✓ Created spells table")

# ── REGISTER INITIAL TILES ─────────────────────────────────────────────────
INITIAL_TILES = [
    {
        'tile_key': 'event_bus',
        'source_file': 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/event_bus.ts',
        'status': 'claimed',
        'assignee': 'p7_spider_sovereign',
        'priority': 1,
        'notes': 'Foundation tile — all plugins depend on it. NO globalEventBus singleton (P99 fix). Stryker target 80-99%.'
    },
    {
        'tile_key': 'plugin_supervisor',
        'source_file': 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/plugin_supervisor.ts',
        'status': 'unvalidated',
        'assignee': None,
        'priority': 2,
        'notes': 'Microkernel core. Depends on event_bus. Port after event_bus passes.'
    },
    {
        'tile_key': 'audio_engine_plugin',
        'source_file': 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/audio_engine_plugin.ts',
        'status': 'claimed',
        'assignee': 'p7_spider_sovereign',
        'priority': 3,
        'notes': 'T-OMEGA-005 P8: zombie event listener fix (bounded method pattern). High ROI per fix effort.'
    },
    {
        'tile_key': 'gesture_fsm',
        'source_file': 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/gesture_fsm.ts',
        'status': 'unvalidated',
        'assignee': None,
        'priority': 4,
        'notes': 'State machine core. 6 ATDD invariants map to this tile.'
    },
    {
        'tile_key': 'kalman_filter',
        'source_file': 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/kalman_filter.ts',
        'status': 'unvalidated',
        'assignee': None,
        'priority': 5,
        'notes': 'Signal processing foundation. 1€ hybrid needed (SOTA upgrade). Pure math — highly testable.'
    },
    {
        'tile_key': 'w3c_pointer_fabric',
        'source_file': 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/w3c_pointer_fabric.ts',
        'status': 'unvalidated',
        'assignee': None,
        'priority': 6,
        'notes': 'omega.v13.arch.v4_rogue_agents P95: needs to be wrapped as a proper Plugin.'
    },
    {
        'tile_key': 'visualization_plugin',
        'source_file': 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/visualization_plugin.ts',
        'status': 'unvalidated',
        'assignee': None,
        'priority': 7,
        'notes': 'omega.v13.arch.v5_pal_leaks P93: route window.innerWidth/Height through PAL capabilities.'
    },
    {
        'tile_key': 'symbiote_injector_plugin',
        'source_file': 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/symbiote_injector_plugin.ts',
        'status': 'unvalidated',
        'assignee': None,
        'priority': 8,
        'notes': 'Potemkin Village bug: was never registered in demo_2026-02-20.ts. Must be wired into shell.ts.'
    },
]

for tile in INITIAL_TILES:
    conn.execute("""
        INSERT OR IGNORE INTO obsidian_blackboard
            (tile_key, source_file, status, assignee, priority, notes, created_at, updated_at, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tile['tile_key'], tile['source_file'], tile['status'],
        tile['assignee'], tile['priority'], tile['notes'],
        NOW, NOW, json.dumps({'session': 'b75409a13f6a39c8', 'nonce': '848CD7'})
    ))

conn.commit()
print(f"✓ Registered {len(INITIAL_TILES)} tiles on obsidian_blackboard")

# ── REGISTER INITIAL SPELLS ────────────────────────────────────────────────
# Link grimoire FCAs to concrete code tiles they animate
INITIAL_SPELLS = [
    {
        'spell_key': 'origin_of_species_event_bus',
        'grimoire_id': 1,
        'spell_name': 'Origin of Species: EventBus Isolation',
        'fca_archetype': 'The Mutator / Variation Engine',
        'target_tile': 'event_bus',
        'status': 'active',
        'notes': 'Applies MAP-Elites variation: isolated EventBus instances, no globalEventBus singleton. Each plugin gets its own scoped bus.'
    },
    {
        'spell_key': 'genesis_stryker_gate',
        'grimoire_id': 2,
        'spell_name': 'Genesis: Stryker Fitness Gate',
        'fca_archetype': 'The Fitness Landscape / SPLENDOR Grid',
        'target_tile': None,  # applies to ALL tiles
        'status': 'active',
        'notes': 'Stryker 80-99% mutation kill rate required before any tile graduates from unvalidated to hardened. This IS the fitness gate.'
    },
    {
        'spell_key': 'animus_blast_audio_engine',
        'grimoire_id': 4,
        'spell_name': 'Animus Blast: AudioEngine Awakening',
        'fca_archetype': 'The Spark of Heredity',
        'target_tile': 'audio_engine_plugin',
        'status': 'active',
        'notes': 'Injects bounded method lifecycle (init/destroy with same reference) + PREY8-aware destroy(). Awakens the zombie plugin into a properly-managed participant.'
    },
]

for spell in INITIAL_SPELLS:
    conn.execute("""
        INSERT OR IGNORE INTO spells
            (spell_key, grimoire_id, spell_name, fca_archetype, target_tile, status,
             notes, created_at, updated_at, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        spell['spell_key'], spell['grimoire_id'], spell['spell_name'],
        spell['fca_archetype'], spell['target_tile'], spell['status'],
        spell['notes'], NOW, NOW,
        json.dumps({'session': 'b75409a13f6a39c8', 'nonce': '848CD7'})
    ))

conn.commit()
print(f"✓ Registered {len(INITIAL_SPELLS)} spells in spells table")

# ── VERIFY ──────────────────────────────────────────────────────────────────
print()
print("=== VERIFICATION ===")
bb_count = conn.execute("SELECT COUNT(*) FROM obsidian_blackboard").fetchone()[0]
sp_count = conn.execute("SELECT COUNT(*) FROM spells").fetchone()[0]
gr_count = conn.execute("SELECT COUNT(*) FROM hfo_grimoire").fetchone()[0]
print(f"obsidian_blackboard: {bb_count} tiles")
print(f"spells: {sp_count} spells")
print(f"hfo_grimoire: {gr_count} spells (source)")

print()
print("=== BLACKBOARD TILES ===")
for r in conn.execute("SELECT tile_key, status, assignee, priority, notes FROM obsidian_blackboard ORDER BY priority"):
    assignee = r[2] or '-'
    print(f"  [{r[3]:02d}] {r[0]} | {r[1]} | {assignee}")
    print(f"       {r[4][:80]}")

print()
print("=== SPELLS ===")
for r in conn.execute("SELECT spell_key, status, target_tile, activation_level FROM spells ORDER BY id"):
    target = r[2] or 'ALL TILES'
    print(f"  {r[0]} | {r[1]} | -> {target} | {r[3]}")

conn.close()
print()
print("DONE ✓")
