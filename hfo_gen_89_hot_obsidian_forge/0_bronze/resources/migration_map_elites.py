"""
MAP-Elites Behavioral Grid Migration for HFO Gen89 SSOT
========================================================
Creates the mission_state table with behavioral descriptor columns
as indexed positional coordinates in the stigmergy manifold.

Option C Hybrid: mission_state (read model) + trigger-enforced
stigmergy_events audit trail (append-only write model).

Behavioral Descriptors (positional coordinates in the manifold):
  - port:           P0-P7 octree position
  - era:            ERA_0 through ERA_5+ temporal position
  - thread:         alpha/omega/specific thread name
  - meadows_level:  L1-L12 leverage depth
  - thread_type:    mission/era/waypoint/task/subtask

Fitness for MAP-Elites replacement:
  - fitness:              0.0-1.0 composite quality
  - mutation_confidence:  0-100 Stryker-style test confidence

When you query by positional data, you get a MATRIX of elites
per niche — not a single best.  This is social spider optimization:
agents read vibrations (query the grid), write to their niche cell,
and leave trace events automatically.

Usage:
    python migration_map_elites.py [--dry-run]

Schema ID: hfo.gen89.mission_state.map_elites.v1
"""
import sqlite3
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

# --- Path resolution via PAL pattern ---
def _find_root():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.isfile(os.path.join(d, "AGENTS.md")):
            return d
        d = os.path.dirname(d)
    raise FileNotFoundError("Cannot find HFO_ROOT (AGENTS.md)")

HFO_ROOT = _find_root()
DB_PATH = os.path.join(
    HFO_ROOT,
    "hfo_gen_89_hot_obsidian_forge", "2_gold", "resources",
    "hfo_gen89_ssot.sqlite"
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DDL: mission_state table
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DDL_MISSION_STATE = """
CREATE TABLE IF NOT EXISTS mission_state (
    -- IDENTITY
    thread_key    TEXT PRIMARY KEY,          -- unique key: 'alpha', 'ERA_4_W1', 'T-P4-001'
    parent_key    TEXT,                      -- hierarchical: era → waypoint → task
    thread_type   TEXT NOT NULL,             -- 'mission','era','waypoint','task','subtask'
    title         TEXT NOT NULL,
    bluf          TEXT,                      -- 1-line summary

    -- MAP-ELITES BEHAVIORAL DESCRIPTORS (positional coordinates in stigmergy manifold)
    port          TEXT,                      -- P0-P7 octree position
    era           TEXT,                      -- ERA_0 through ERA_5+
    thread        TEXT,                      -- 'alpha','omega', or specific thread name
    meadows_level INTEGER,                   -- L1-L12 leverage depth

    -- ELITE FITNESS (for MAP-Elites replacement logic)
    fitness              REAL    NOT NULL DEFAULT 0.0,   -- composite quality 0.0-1.0
    mutation_confidence  INTEGER NOT NULL DEFAULT 0,     -- Stryker-style 0-100

    -- STATE
    status        TEXT NOT NULL DEFAULT 'active',  -- active/blocked/done/archived
    priority      INTEGER DEFAULT 0,               -- higher = more important
    assignee      TEXT,                             -- commander key or agent_id

    -- METADATA
    metadata_json TEXT,              -- flexible overflow (JSON)
    created_at    TEXT NOT NULL,     -- ISO timestamp
    updated_at    TEXT NOT NULL,     -- ISO timestamp
    version       INTEGER NOT NULL DEFAULT 1,  -- optimistic concurrency
    medallion     TEXT NOT NULL DEFAULT 'bronze',

    -- REFERENTIAL INTEGRITY
    FOREIGN KEY (parent_key) REFERENCES mission_state(thread_key)
);
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INDEXES: one per behavioral descriptor
#  (not composite — queries slice any subset)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_ms_port          ON mission_state(port);",
    "CREATE INDEX IF NOT EXISTS idx_ms_era           ON mission_state(era);",
    "CREATE INDEX IF NOT EXISTS idx_ms_thread        ON mission_state(thread);",
    "CREATE INDEX IF NOT EXISTS idx_ms_meadows       ON mission_state(meadows_level);",
    "CREATE INDEX IF NOT EXISTS idx_ms_status        ON mission_state(status);",
    "CREATE INDEX IF NOT EXISTS idx_ms_parent        ON mission_state(parent_key);",
    "CREATE INDEX IF NOT EXISTS idx_ms_type          ON mission_state(thread_type);",
    "CREATE INDEX IF NOT EXISTS idx_ms_fitness       ON mission_state(fitness DESC);",
    # Composite index for the most common grid slice query
    "CREATE INDEX IF NOT EXISTS idx_ms_grid_slice    ON mission_state(port, era, thread, status);",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRIGGERS: dual-write to stigmergy_events
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIGGER_INSERT = """
CREATE TRIGGER IF NOT EXISTS tr_mission_state_created
AFTER INSERT ON mission_state
BEGIN
    INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash)
    VALUES (
        'hfo.gen89.mission.state_created',
        strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'),
        'mission_state_trigger',
        NEW.thread_key,
        json_object(
            'thread_key',   NEW.thread_key,
            'parent_key',   NEW.parent_key,
            'thread_type',  NEW.thread_type,
            'title',        NEW.title,
            'port',         NEW.port,
            'era',          NEW.era,
            'thread',       NEW.thread,
            'meadows_level',NEW.meadows_level,
            'fitness',      NEW.fitness,
            'status',       NEW.status,
            'version',      NEW.version
        ),
        hex(randomblob(16))
    );
END;
"""

TRIGGER_UPDATE = """
CREATE TRIGGER IF NOT EXISTS tr_mission_state_changed
AFTER UPDATE ON mission_state
BEGIN
    INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash)
    VALUES (
        'hfo.gen89.mission.state_changed',
        strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'),
        'mission_state_trigger',
        NEW.thread_key,
        json_object(
            'thread_key',       NEW.thread_key,
            'old_status',       OLD.status,
            'new_status',       NEW.status,
            'old_fitness',      OLD.fitness,
            'new_fitness',      NEW.fitness,
            'old_version',      OLD.version,
            'new_version',      NEW.version,
            'port',             NEW.port,
            'era',              NEW.era,
            'thread',           NEW.thread,
            'meadows_level',    NEW.meadows_level,
            'delta',            json_object(
                'status_changed',  OLD.status != NEW.status,
                'fitness_changed', OLD.fitness != NEW.fitness,
                'title_changed',   OLD.title != NEW.title
            )
        ),
        hex(randomblob(16))
    );
END;
"""

TRIGGER_DELETE = """
CREATE TRIGGER IF NOT EXISTS tr_mission_state_archived
AFTER DELETE ON mission_state
BEGIN
    INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash)
    VALUES (
        'hfo.gen89.mission.state_deleted',
        strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now'),
        'mission_state_trigger',
        OLD.thread_key,
        json_object(
            'thread_key',  OLD.thread_key,
            'thread_type', OLD.thread_type,
            'title',       OLD.title,
            'port',        OLD.port,
            'era',         OLD.era,
            'final_status',OLD.status,
            'final_fitness',OLD.fitness,
            'final_version',OLD.version
        ),
        hex(randomblob(16))
    );
END;
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VIEW: MAP-Elites grid — matrix by position
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIEW_MAP_ELITES_GRID = """
CREATE VIEW IF NOT EXISTS map_elites_grid AS
SELECT
    port,
    era,
    thread,
    meadows_level,
    thread_type,
    COUNT(*)                              AS cell_count,
    MAX(fitness)                          AS best_fitness,
    AVG(fitness)                          AS avg_fitness,
    SUM(CASE WHEN status='active' THEN 1 ELSE 0 END)  AS active_count,
    SUM(CASE WHEN status='done'   THEN 1 ELSE 0 END)  AS done_count,
    SUM(CASE WHEN status='blocked' THEN 1 ELSE 0 END) AS blocked_count,
    GROUP_CONCAT(thread_key, ',')         AS elite_keys
FROM mission_state
WHERE status NOT IN ('archived')
GROUP BY port, era, thread, meadows_level, thread_type;
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VIEW: Port heatmap — fitness by port
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIEW_PORT_HEATMAP = """
CREATE VIEW IF NOT EXISTS port_heatmap AS
SELECT
    port,
    COUNT(*)       AS total_cells,
    AVG(fitness)   AS avg_fitness,
    MAX(fitness)   AS max_fitness,
    MIN(fitness)   AS min_fitness,
    SUM(CASE WHEN status='active'  THEN 1 ELSE 0 END) AS active,
    SUM(CASE WHEN status='done'    THEN 1 ELSE 0 END) AS done,
    SUM(CASE WHEN status='blocked' THEN 1 ELSE 0 END) AS blocked
FROM mission_state
WHERE port IS NOT NULL AND status != 'archived'
GROUP BY port
ORDER BY port;
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VIEW: Thread health — fitness by thread
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIEW_THREAD_HEALTH = """
CREATE VIEW IF NOT EXISTS thread_health AS
SELECT
    thread,
    era,
    COUNT(*)       AS total_cells,
    AVG(fitness)   AS avg_fitness,
    SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active,
    SUM(CASE WHEN status='done'   THEN 1 ELSE 0 END) AS done
FROM mission_state
WHERE status != 'archived'
GROUP BY thread, era
ORDER BY thread, era;
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SEED DATA: Braided Mission Thread
#  Source: Doc 7855 braided_mission_thread YAML
#          Doc 100 Obsidian Hourglass Trellis
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

SEED_DATA = [
    # === MISSION LEVEL (North Stars) ===
    {
        "thread_key": "alpha",
        "parent_key": None,
        "thread_type": "mission",
        "title": "Cognitive Symbiote Social Spider Swarm",
        "bluf": "Personal AI cognitive symbiote swarm — exemplar ensemble of AI commanders running strict safety dyads",
        "port": None, "era": None, "thread": "alpha", "meadows_level": 12,
        "fitness": 0.0, "mutation_confidence": 0,
        "status": "active", "priority": 10, "assignee": "TTAO",
        "metadata_json": json.dumps({"north_star": True, "source_doc": 7855}),
    },
    {
        "thread_key": "omega",
        "parent_key": None,
        "thread_type": "mission",
        "title": "Total Tool Virtualization",
        "bluf": "All tools of humanity + props + software + hardware = $0 cost to MASTERY and POWER_LEVELING humanity",
        "port": None, "era": None, "thread": "omega", "meadows_level": 12,
        "fitness": 0.0, "mutation_confidence": 0,
        "status": "active", "priority": 10, "assignee": "TTAO",
        "metadata_json": json.dumps({"north_star": True, "source_doc": 7855}),
    },

    # === ERA LEVEL (5 eras from Doc 100 Trellis) ===
    {
        "thread_key": "ERA_0",
        "parent_key": "alpha",
        "thread_type": "era",
        "title": "Pre-HFO — Solo Genesis",
        "bluf": "Solo dev, no memory system, raw prototypes, no architecture",
        "port": None, "era": "ERA_0", "thread": "alpha", "meadows_level": 11,
        "fitness": 1.0, "mutation_confidence": 90,
        "status": "done", "priority": 0, "assignee": "TTAO",
        "metadata_json": json.dumps({"source_doc": 100, "alpha_state": "Solo dev, no memory system", "omega_state": "Raw prototypes, no architecture"}),
    },
    {
        "thread_key": "ERA_1",
        "parent_key": "alpha",
        "thread_type": "era",
        "title": "Memory Awakening — Shodh + Doobidoo",
        "bluf": "1st memories stored, SSOT SQLite born, Gen7 interactive whiteboard v1",
        "port": None, "era": "ERA_1", "thread": "alpha", "meadows_level": 11,
        "fitness": 1.0, "mutation_confidence": 85,
        "status": "done", "priority": 0, "assignee": "TTAO",
        "metadata_json": json.dumps({"source_doc": 100, "alpha_state": "1st memories stored, SSOT born", "omega_state": "Gen7 interactive whiteboard v1"}),
    },
    {
        "thread_key": "ERA_2",
        "parent_key": "alpha",
        "thread_type": "era",
        "title": "Forge Industrialization — Hot + Cold Obsidian",
        "bluf": "Grimoire lineage v1→v8.8→v11.1, Gen8 born v25.1 (28654 lines)",
        "port": None, "era": "ERA_2", "thread": "alpha", "meadows_level": 11,
        "fitness": 1.0, "mutation_confidence": 85,
        "status": "done", "priority": 0, "assignee": "TTAO",
        "metadata_json": json.dumps({"source_doc": 100, "alpha_state": "Grimoire lineage v1→v8.8→v11.1", "omega_state": "Gen8 born v25.1 (28654 lines)"}),
    },
    {
        "thread_key": "ERA_3",
        "parent_key": "alpha",
        "thread_type": "era",
        "title": "Federation Crystallization — 4 Quines",
        "bluf": "Federation quines (α Doctrine, Σ Memory, Ω Knowledge, Δ Code). Gen8 v30 trade study, 4 Pareto options.",
        "port": None, "era": "ERA_3", "thread": "alpha", "meadows_level": 11,
        "fitness": 1.0, "mutation_confidence": 80,
        "status": "done", "priority": 0, "assignee": "TTAO",
        "metadata_json": json.dumps({"source_doc": 100, "alpha_state": "4 federation quines", "omega_state": "Gen8 v30 trade study"}),
    },
    {
        "thread_key": "ERA_4",
        "parent_key": "alpha",
        "thread_type": "era",
        "title": "Mosaic Recomposition — Current (Feb 2026)",
        "bluf": "8557→9860 memories, 88→89 generations, Gold Diataxis library. Gen8 v40 kernel 7466 lines, 10 tiles, 73.9% shed.",
        "port": None, "era": "ERA_4", "thread": "alpha", "meadows_level": 9,
        "fitness": 0.3, "mutation_confidence": 55,
        "status": "active", "priority": 10, "assignee": "TTAO",
        "metadata_json": json.dumps({"source_doc": 100, "alpha_state": "9860 docs, 89 gens, Gold Diataxis", "omega_state": "Gen8 v40 kernel 7466 lines, 10 tiles", "you_are_here": True}),
    },
    {
        "thread_key": "ERA_5",
        "parent_key": "alpha",
        "thread_type": "era",
        "title": "Import Map Federation — Gen9 (Near Future)",
        "bluf": "Distributed doctrine, cross-tile governance. Gen9 federation, per-tile ESM imports, tile autonomy.",
        "port": None, "era": "ERA_5", "thread": "alpha", "meadows_level": 9,
        "fitness": 0.0, "mutation_confidence": 0,
        "status": "active", "priority": 5, "assignee": None,
        "metadata_json": json.dumps({"source_doc": 100, "alpha_state": "Distributed doctrine", "omega_state": "Gen9 federation, per-tile ESM imports"}),
    },

    # === WAYPOINT LEVEL (Doc 100 Goal Chain) ===
    {
        "thread_key": "ERA_4_W1",
        "parent_key": "ERA_4",
        "thread_type": "waypoint",
        "title": "Touch2D Microkernel",
        "bluf": "MediaPipe → anti-Midas FSM, anti-thrash, W3C PointerEvent out",
        "port": "P2", "era": "ERA_4", "thread": "omega", "meadows_level": 3,
        "fitness": 0.1, "mutation_confidence": 20,
        "status": "active", "priority": 9, "assignee": "P2_MIRROR_MAGUS",
        "metadata_json": json.dumps({"source_doc": 100, "sub_goals": ["Drumpad works with noisy touch", "Piano works with clean touch"]}),
    },
    {
        "thread_key": "ERA_4_W2",
        "parent_key": "ERA_4",
        "thread_type": "waypoint",
        "title": "Spike Factory",
        "bluf": "Shared data fabric, gesture control plane, touchscreen emulator",
        "port": "P1", "era": "ERA_4", "thread": "omega", "meadows_level": 7,
        "fitness": 0.0, "mutation_confidence": 0,
        "status": "active", "priority": 7, "assignee": "P1_WEB_WEAVER",
        "metadata_json": json.dumps({"source_doc": 100, "sub_goals": ["All instruments via gesture", "Mouse/pen emulation"]}),
    },
    {
        "thread_key": "ERA_4_W3",
        "parent_key": "ERA_4",
        "thread_type": "waypoint",
        "title": "Genie Simulations",
        "bluf": "MediaPipe-driven world models, video→game bridge",
        "port": "P2", "era": "ERA_4", "thread": "omega", "meadows_level": 9,
        "fitness": 0.0, "mutation_confidence": 0,
        "status": "active", "priority": 5, "assignee": "P2_MIRROR_MAGUS",
        "metadata_json": json.dumps({"source_doc": 100, "sub_goals": ["Interactive world control", "Predictive next-state"]}),
    },
    {
        "thread_key": "ERA_4_W_NORTH_STAR",
        "parent_key": "ERA_4",
        "thread_type": "waypoint",
        "title": "Total Tool Virtualization",
        "bluf": "All instruments, all tools, all humanity",
        "port": None, "era": "ERA_4", "thread": "omega", "meadows_level": 12,
        "fitness": 0.0, "mutation_confidence": 0,
        "status": "active", "priority": 1, "assignee": None,
        "metadata_json": json.dumps({"source_doc": 100, "north_star": True}),
    },

    # === TASK LEVEL: Current ERA_4 active tasks per port ===
    {
        "thread_key": "T-P0-001",
        "parent_key": "ERA_4",
        "thread_type": "task",
        "title": "PREY8 Eval Harness — Model Benchmarking",
        "bluf": "Observe model capabilities via eval harness on HumanEval problems",
        "port": "P0", "era": "ERA_4", "thread": "alpha", "meadows_level": 5,
        "fitness": 0.65, "mutation_confidence": 55,
        "status": "active", "priority": 8, "assignee": "P0_LIDLESS_LEGION",
        "metadata_json": json.dumps({"models_tested": ["qwen2.5-coder:7b", "llama3.2:3b", "gemma3:4b", "granite4:3b", "lfm2.5-thinking:1.2b"]}),
    },
    {
        "thread_key": "T-P2-001",
        "parent_key": "ERA_4_W1",
        "thread_type": "task",
        "title": "P2 Chimera Loop — Evolutionary Code Generation",
        "bluf": "Universal Darwinism engine: generate → test → select → evolve code via local LLMs",
        "port": "P2", "era": "ERA_4", "thread": "alpha", "meadows_level": 7,
        "fitness": 0.4, "mutation_confidence": 45,
        "status": "active", "priority": 8, "assignee": "P2_MIRROR_MAGUS",
        "metadata_json": json.dumps({"script": "hfo_p2_chimera_loop.py"}),
    },
    {
        "thread_key": "T-P4-001",
        "parent_key": "ERA_4",
        "thread_type": "task",
        "title": "P4 Red Regnant PREY8 Gates — Fail-Closed Enforcement",
        "bluf": "Port-pair gates on all PREY8 steps, tamper-evident hash chains, memory loss tracking",
        "port": "P4", "era": "ERA_4", "thread": "alpha", "meadows_level": 8,
        "fitness": 0.75, "mutation_confidence": 70,
        "status": "active", "priority": 9, "assignee": "P4_RED_REGNANT",
        "metadata_json": json.dumps({"script": "hfo_prey8_mcp_server.py", "gates_passed": "22/22"}),
    },
    {
        "thread_key": "T-P5-001",
        "parent_key": "ERA_4",
        "thread_type": "task",
        "title": "P5 Contingency Framework — Antifragile Error Handling",
        "bluf": "Fail-closed contingency protocols for the octree daemon swarm",
        "port": "P5", "era": "ERA_4", "thread": "alpha", "meadows_level": 5,
        "fitness": 0.3, "mutation_confidence": 30,
        "status": "active", "priority": 7, "assignee": "P5_PYRE_PRAETORIAN",
        "metadata_json": json.dumps({"script": "hfo_p5_contingency.py"}),
    },
    {
        "thread_key": "T-P6-001",
        "parent_key": "ERA_4",
        "thread_type": "task",
        "title": "MAP-Elites Mission Grid — Stigmergy State Layer",
        "bluf": "Behavioral grid in SQLite for social spider optimization — matrix not scalar",
        "port": "P6", "era": "ERA_4", "thread": "alpha", "meadows_level": 6,
        "fitness": 0.0, "mutation_confidence": 0,
        "status": "active", "priority": 9, "assignee": "P6_KRAKEN_KEEPER",
        "metadata_json": json.dumps({"this_task": True, "option": "C_hybrid"}),
    },
    {
        "thread_key": "T-P7-001",
        "parent_key": "ERA_4",
        "thread_type": "task",
        "title": "8 Persistent Daemons — Octree Swarm Supervisor",
        "bluf": "One daemon per port, supervised by SwarmSupervisor, coordinated via stigmergy",
        "port": "P7", "era": "ERA_4", "thread": "alpha", "meadows_level": 9,
        "fitness": 0.35, "mutation_confidence": 35,
        "status": "active", "priority": 8, "assignee": "P7_SPIDER_SOVEREIGN",
        "metadata_json": json.dumps({"script": "hfo_octree_daemon.py"}),
    },
]


def run_migration(db_path: str, dry_run: bool = False):
    """Run the MAP-Elites migration against the SSOT database."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()

    # Check if already migrated
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mission_state'")
    if c.fetchone():
        print("[!] mission_state table already exists. Checking if it needs updates...")
        c.execute("SELECT COUNT(*) FROM mission_state")
        count = c.fetchone()[0]
        print(f"    Current rows: {count}")
        if count > 0:
            print("    Skipping seed — data already present.")
            conn.close()
            return

    if dry_run:
        print("=== DRY RUN — showing SQL only ===\n")
        print(DDL_MISSION_STATE)
        for idx in DDL_INDEXES:
            print(idx)
        print(TRIGGER_INSERT)
        print(TRIGGER_UPDATE)
        print(TRIGGER_DELETE)
        print(VIEW_MAP_ELITES_GRID)
        print(VIEW_PORT_HEATMAP)
        print(VIEW_THREAD_HEALTH)
        print(f"\nSeed data: {len(SEED_DATA)} rows")
        for row in SEED_DATA:
            print(f"  {row['thread_key']:20s} | {row['thread_type']:10s} | {row['title'][:50]}")
        conn.close()
        return

    print("=== MAP-Elites Behavioral Grid Migration ===\n")

    # 1. Create table
    print("[1/7] Creating mission_state table...")
    c.execute(DDL_MISSION_STATE)

    # 2. Create indexes
    print("[2/7] Creating behavioral descriptor indexes...")
    for idx in DDL_INDEXES:
        c.execute(idx)
    print(f"       {len(DDL_INDEXES)} indexes created")

    # 3. Create triggers
    print("[3/7] Creating stigmergy audit triggers...")
    c.execute(TRIGGER_INSERT)
    c.execute(TRIGGER_UPDATE)
    c.execute(TRIGGER_DELETE)
    print("       3 triggers active (INSERT, UPDATE, DELETE)")

    # 4. Create views
    print("[4/7] Creating MAP-Elites grid views...")
    c.execute(VIEW_MAP_ELITES_GRID)
    c.execute(VIEW_PORT_HEATMAP)
    c.execute(VIEW_THREAD_HEALTH)
    print("       3 views created (map_elites_grid, port_heatmap, thread_health)")

    # 5. Seed data
    print(f"[5/7] Seeding braided mission thread ({len(SEED_DATA)} rows)...")
    for row in SEED_DATA:
        c.execute("""
            INSERT INTO mission_state
            (thread_key, parent_key, thread_type, title, bluf,
             port, era, thread, meadows_level,
             fitness, mutation_confidence,
             status, priority, assignee,
             metadata_json, created_at, updated_at, version, medallion)
            VALUES (?,?,?,?,?, ?,?,?,?, ?,?, ?,?,?, ?,?,?,?,?)
        """, (
            row["thread_key"], row["parent_key"], row["thread_type"],
            row["title"], row["bluf"],
            row["port"], row["era"], row["thread"], row["meadows_level"],
            row["fitness"], row["mutation_confidence"],
            row["status"], row["priority"], row["assignee"],
            row["metadata_json"], NOW, NOW, 1, "bronze"
        ))
    print(f"       {len(SEED_DATA)} elite cells seeded")

    # 6. Update meta
    print("[6/7] Updating SSOT meta...")
    c.execute("""
        INSERT OR REPLACE INTO meta (key, value)
        VALUES ('map_elites_schema', ?)
    """, (json.dumps({
        "schema_id": "hfo.gen89.mission_state.map_elites.v1",
        "created": NOW,
        "behavioral_descriptors": ["port", "era", "thread", "meadows_level"],
        "fitness_range": "0.0-1.0",
        "mutation_confidence_range": "0-100",
        "seed_source": "braided_mission_thread_alpha_omega_hfo_gen88v8.yaml + REFERENCE_OBSIDIAN_HOURGLASS_TRELLIS",
        "views": ["map_elites_grid", "port_heatmap", "thread_health"],
        "triggers": ["tr_mission_state_created", "tr_mission_state_changed", "tr_mission_state_archived"],
    }),))

    # 7. Commit
    conn.commit()
    print("[7/7] Committed.\n")

    # Verify
    print("=== Verification ===")
    c.execute("SELECT COUNT(*) FROM mission_state")
    print(f"  mission_state rows: {c.fetchone()[0]}")

    c.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE 'hfo.gen89.mission.%'")
    print(f"  stigmergy audit events: {c.fetchone()[0]}")

    print("\n=== MAP-Elites Grid (matrix view) ===")
    c.execute("SELECT port, era, thread, meadows_level, cell_count, best_fitness, elite_keys FROM map_elites_grid ORDER BY port, era")
    for row in c.fetchall():
        p = row[0] or '---'
        e = row[1] or '---'
        t = row[2] or '---'
        ml = str(row[3]) if row[3] is not None else '-'
        print(f"  [{p:4s}] [{e:5s}] [{t:6s}] [L{ml:>2s}] cells={row[4]} best={row[5]:.2f} keys={row[6][:60]}")

    print("\n=== Port Heatmap ===")
    c.execute("SELECT * FROM port_heatmap")
    for row in c.fetchall():
        print(f"  {row[0]}: total={row[1]} avg_fitness={row[2]:.2f} max={row[3]:.2f} active={row[5]} done={row[6]} blocked={row[7]}")

    print("\n=== Thread Health ===")
    c.execute("SELECT * FROM thread_health")
    for row in c.fetchall():
        print(f"  {row[0] or '---':8s} [{row[1] or '---':5s}] total={row[2]} avg_fitness={row[3]:.2f} active={row[4]} done={row[5]}")

    conn.close()
    print("\n✓ Migration complete. MAP-Elites behavioral grid is live.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_migration(DB_PATH, dry_run=dry_run)
