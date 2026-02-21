#!/usr/bin/env python3
"""
hfo_shodh.py — P6 ASSIMILATE :: Shodh Hebbian Association Graph
================================================================
v1.0 | Gen89 | P6 ASSIMILATE
Bronze medallion — unvalidated.

PURPOSE:
    Implements the Shodh (Hindi: 'search/discovery') Hebbian learning layer
    on top of the SSOT SQLite. Tracks co-retrieval events between documents and
    applies the Hebbian weight update rule:

        Δw = γ · a · b

    Where γ is the learning rate, a=1 (doc_a was retrieved), b=1 (doc_b was
    co-retrieved in the same session turn). Associations strengthen through
    repeated co-activation and decay over time (anti-Hebbian pruning).

ARCHITECTURE (from Doc 274 E40, Doc 125 R26):
    SSOT SQLite (single write-path)
      ├── embeddings table (9,868 rows — all docs embedded)
      ├── shodh_co_retrieval (append-only log of retrieval events)
      ├── shodh_associations (Hebbian edge weights between doc pairs)
      └── v_hebbian_top_associations (read-only VIEW)

USAGE:
    # Schema setup (run once or to migrate)
    python hfo_shodh.py --setup

    # Record a co-retrieval event (docs A and B retrieved in same turn)
    python hfo_shodh.py --co-retrieve 101,204,87  --session-id abc123

    # Show top associations for a document
    python hfo_shodh.py --top-for 101

    # Show global top associations
    python hfo_shodh.py --top-global --limit 20

    # Decay pass (call periodically to apply anti-Hebbian pruning)
    python hfo_shodh.py --decay

    # Seed from stigmergy (one-time import using P4 co-occurrence)
    python hfo_shodh.py --seed-from-stigmergy

    # Full status report
    python hfo_shodh.py --status

    # JSON output for any command
    python hfo_shodh.py --status --json

MEDALLION: bronze
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEN = os.environ.get("HFO_GENERATION", "89")
OPERATOR = os.environ.get("HFO_OPERATOR", "TTAO")
_SCRIPT_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _SCRIPT_DIR.parents[2]

DB_PATH = _WORKSPACE_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"

# Hebbian learning rate
GAMMA: float = float(os.environ.get("HFO_SHODH_GAMMA", "0.1"))
# Decay factor per decay pass (multiplier on weight, <1.0)
DECAY_FACTOR: float = float(os.environ.get("HFO_SHODH_DECAY", "0.99"))
# Minimum weight before a weak association is pruned
PRUNE_THRESHOLD: float = float(os.environ.get("HFO_SHODH_PRUNE", "0.01"))

# Hub docs: orientation/catalog documents that co-activate with nearly everything.
# Including them in Hebbian pairs saturates their edges at w=1.0 and drowns real
# domain-specific associations. They are excluded from pairing but still logged
# in shodh_co_retrieval so the retrieval event is auditable.
# Doc 1  = HFO Gold Diataxis Library — Full Catalog
# Doc 2  = HFO Gold Diataxis Library — Auto-Generated Catalog
# Doc 37 = REFERENCE_2026_AGENT_SWARM_GUIDANCE_V1 (AGENTS.md orientation doc)
HUB_DOC_IDS: frozenset[int] = frozenset(
    int(x) for x in os.environ.get("HFO_SHODH_HUB_IDS", "1,2,37").split(",") if x.strip()
)


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

SHODH_CO_RETRIEVAL_DDL = """
CREATE TABLE IF NOT EXISTS shodh_co_retrieval (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT,
    turn_id       TEXT,
    doc_id        INTEGER NOT NULL REFERENCES documents(id),
    retrieved_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    retrieval_mode TEXT   DEFAULT 'unknown',  -- semantic|associative|hybrid|fts
    query_text    TEXT,
    FOREIGN KEY(doc_id) REFERENCES documents(id)
);
"""

SHODH_ASSOCIATIONS_DDL = """
CREATE TABLE IF NOT EXISTS shodh_associations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_a         INTEGER NOT NULL,
    doc_b         INTEGER NOT NULL,
    weight        REAL    NOT NULL DEFAULT 0.1,
    co_activation_count INTEGER NOT NULL DEFAULT 1,
    last_activated TEXT,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY(doc_a) REFERENCES documents(id),
    FOREIGN KEY(doc_b) REFERENCES documents(id),
    UNIQUE(doc_a, doc_b) ON CONFLICT IGNORE
);
"""

SHODH_ASSOC_INDEXES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_shodh_assoc_a ON shodh_associations(doc_a);",
    "CREATE INDEX IF NOT EXISTS idx_shodh_assoc_b ON shodh_associations(doc_b);",
    "CREATE INDEX IF NOT EXISTS idx_shodh_assoc_weight ON shodh_associations(weight DESC);",
    "CREATE INDEX IF NOT EXISTS idx_shodh_coretrieve_session ON shodh_co_retrieval(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_shodh_coretrieve_doc ON shodh_co_retrieval(doc_id);",
]

HEBBIAN_VIEW_DDL = """
CREATE VIEW IF NOT EXISTS v_hebbian_top_associations AS
SELECT
    sa.doc_a,
    da.title        AS title_a,
    da.port         AS port_a,
    sa.doc_b,
    db.title        AS title_b,
    db.port         AS port_b,
    sa.weight,
    sa.co_activation_count,
    sa.last_activated,
    sa.updated_at
FROM shodh_associations sa
JOIN documents da ON da.id = sa.doc_a
JOIN documents db ON db.id = sa.doc_b
WHERE sa.weight >= 0.05
ORDER BY sa.weight DESC;
"""

HEBBIAN_PORT_AFFINITY_DDL = """
CREATE VIEW IF NOT EXISTS v_hebbian_port_affinity AS
SELECT
    COALESCE(da.port,'NULL') AS port_a,
    COALESCE(db.port,'NULL') AS port_b,
    COUNT(*)                 AS pair_count,
    ROUND(AVG(sa.weight),4)  AS avg_weight,
    ROUND(SUM(sa.weight),4)  AS total_weight
FROM shodh_associations sa
JOIN documents da ON da.id = sa.doc_a
JOIN documents db ON db.id = sa.doc_b
GROUP BY port_a, port_b
ORDER BY total_weight DESC;
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def cmd_setup(verbose: bool = True) -> dict:
    conn = get_conn()
    c = conn.cursor()

    created = []
    for ddl, name in [
        (SHODH_CO_RETRIEVAL_DDL, "shodh_co_retrieval"),
        (SHODH_ASSOCIATIONS_DDL, "shodh_associations"),
    ]:
        c.execute(ddl)
        created.append(name)

    for ddl in SHODH_ASSOC_INDEXES_DDL:
        c.execute(ddl)

    for ddl, name in [
        (HEBBIAN_VIEW_DDL, "v_hebbian_top_associations"),
        (HEBBIAN_PORT_AFFINITY_DDL, "v_hebbian_port_affinity"),
    ]:
        c.execute(ddl)
        created.append(f"VIEW:{name}")

    conn.commit()
    conn.close()

    result = {
        "status": "OK",
        "tables_and_views_created_or_verified": created,
        "db_path": str(DB_PATH),
    }
    if verbose:
        print("[Shodh Setup] Schema ready:")
        for item in created:
            print(f"  ✓ {item}")
    return result


# ---------------------------------------------------------------------------
# Record co-retrieval and apply Hebb rule
# ---------------------------------------------------------------------------

def cmd_co_retrieve(
    doc_ids: list[int],
    session_id: str | None = None,
    turn_id: str | None = None,
    retrieval_mode: str = "hybrid",
    query_text: str | None = None,
) -> dict:
    """
    Record that a set of docs were co-retrieved in the same turn and apply
    the Hebbian weight update to all pairs.
    """
    if len(doc_ids) < 2:
        return {"status": "SKIPPED", "reason": "need >= 2 docs for co-retrieval"}

    session_id = session_id or f"manual_{uuid.uuid4().hex[:8]}"
    turn_id = turn_id or uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()

    conn = get_conn()
    c = conn.cursor()

    # Log individual retrievals
    for doc_id in doc_ids:
        c.execute(
            "INSERT INTO shodh_co_retrieval (session_id, turn_id, doc_id, retrieved_at, retrieval_mode, query_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, turn_id, doc_id, now, retrieval_mode, query_text),
        )

    # Apply Hebbian rule to all pairs — excluding hub docs from pairing.
    # Hubs (AGENTS.md, catalog docs) co-activate with everything and would
    # saturate edges at w=1.0, drowning real domain-specific associations.
    pairing_ids = [d for d in set(doc_ids) if d not in HUB_DOC_IDS]
    hub_excluded = [d for d in set(doc_ids) if d in HUB_DOC_IDS]

    pairs_updated = 0
    delta_w = GAMMA  # a=1, b=1, gamma=GAMMA
    strengthened_pairs: list[tuple[int, int]] = []

    for a, b in itertools.combinations(sorted(pairing_ids), 2):
        # Canonical order: smaller id first
        doc_a, doc_b = (a, b) if a < b else (b, a)

        # Upsert association
        c.execute(
            """
            INSERT INTO shodh_associations (doc_a, doc_b, weight, co_activation_count, last_activated, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(doc_a, doc_b) DO UPDATE SET
                weight              = MIN(1.0, shodh_associations.weight + ?),
                co_activation_count = shodh_associations.co_activation_count + 1,
                last_activated      = excluded.last_activated,
                updated_at          = excluded.updated_at
            """,
            (doc_a, doc_b, delta_w, now, now, delta_w),
        )
        strengthened_pairs.append((doc_a, doc_b))
        pairs_updated += 1

    conn.commit()

    # ── Stigmergy emit: Hebbian co-retrieval strengthens the event trail ──────
    # Each time associations are updated, write a CloudEvent so PREY8 agents
    # can observe which document clusters are consolidating over time.
    if strengthened_pairs:
        try:
            from hfo_signal_shim import build_signal_metadata
            from hfo_ssot_write import write_stigmergy_event
            sig_meta = build_signal_metadata(
                port="P6",
                model_id="shodh_hebbian_v1",
                daemon_name="Shodh",
            )
            write_stigmergy_event(
                event_type="hfo.gen89.shodh.hebbian.co_retrieval",
                subject=session_id,
                data={
                    "session_id":     session_id,
                    "turn_id":        turn_id,
                    "docs_recorded":  len(doc_ids),
                    "hub_excluded":   hub_excluded,
                    "pairs_updated":  pairs_updated,
                    "delta_w":        delta_w,
                    "top_pairs":      strengthened_pairs[:5],
                    "query_text":     (query_text or "")[:120],
                    "retrieval_mode": retrieval_mode,
                },
                signal_metadata=sig_meta,
            )
        except Exception:
            pass  # never block retrieval on stigmergy write failure

    conn.close()

    return {
        "status": "OK",
        "session_id": session_id,
        "turn_id": turn_id,
        "docs_recorded": len(doc_ids),
        "hub_excluded": hub_excluded,
        "pairs_updated": pairs_updated,
        "delta_w": delta_w,
    }


# ---------------------------------------------------------------------------
# Decay pass
# ---------------------------------------------------------------------------

def cmd_decay() -> dict:
    """Apply anti-Hebbian decay to all associations; prune weak edges."""
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM shodh_associations")
    before = c.fetchone()[0]

    c.execute(
        "UPDATE shodh_associations SET weight = weight * ?, updated_at = ? "
        "WHERE weight > ?",
        (DECAY_FACTOR, datetime.now(timezone.utc).isoformat(), PRUNE_THRESHOLD),
    )

    c.execute("DELETE FROM shodh_associations WHERE weight < ?", (PRUNE_THRESHOLD,))
    pruned = conn.total_changes

    conn.commit()
    conn.close()

    c2 = get_conn().cursor()
    c2.execute("SELECT COUNT(*) FROM shodh_associations")
    after = c2.fetchone()[0]

    return {
        "status": "OK",
        "before": before,
        "after": after,
        "pruned": before - after,
        "decay_factor": DECAY_FACTOR,
    }


# ---------------------------------------------------------------------------
# Top associations
# ---------------------------------------------------------------------------

def cmd_top_for(doc_id: int, limit: int = 20) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM v_hebbian_top_associations
        WHERE doc_a = ? OR doc_b = ?
        ORDER BY weight DESC
        LIMIT ?
        """,
        (doc_id, doc_id, limit),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"status": "OK", "doc_id": doc_id, "associations": rows}


def cmd_top_global(limit: int = 20) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT * FROM v_hebbian_top_associations LIMIT {limit}")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"status": "OK", "top_associations": rows, "count": len(rows)}


# ---------------------------------------------------------------------------
# Seed from stigmergy (P4 co-occurrence proxy)
# ---------------------------------------------------------------------------

def cmd_seed_from_stigmergy() -> dict:
    """
    Cold-start the Hebbian graph by co-occurring documents that appear in the
    same PREY8 execute event's data_json. Also seeds from the FTS-based 'related
    documents share port' heuristic.

    Strategy:
    1. For every PREY8 session, find all docs referenced in that session's events
       via data_json doc_id patterns. Co-retrieve them all.
    2. For every port P0-P7, co-retrieve pairs of docs tagged to the same port
       (max 50 pairs per port to avoid explosion).
    3. Seed cross-port pairs from the chimera_lineage if populated.
    """
    conn = get_conn()
    c = conn.cursor()

    total_pairs = 0

    # Strategy 1: Port-affinity seed — pairs of docs on the same port, by source priority
    print("[Shodh Seed] Strategy 1: Port-affinity co-retrieval...")
    ports = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]
    for port in ports:
        c.execute(
            "SELECT id FROM documents WHERE port = ? ORDER BY word_count DESC LIMIT 30",
            (port,),
        )
        doc_ids = [r[0] for r in c.fetchall()]
        if len(doc_ids) >= 2:
            result = cmd_co_retrieve(
                doc_ids, session_id=f"seed_port_{port}", retrieval_mode="seed_port_affinity"
            )
            pairs = result.get("pairs_updated", 0)
            total_pairs += pairs
            print(f"  Port {port}: {len(doc_ids)} docs → {pairs} association pairs")

    # Strategy 2: Source-affinity seed — key sources
    print("[Shodh Seed] Strategy 2: Source-affinity co-retrieval (diataxis + gold_report)...")
    for source in ["diataxis", "silver", "gold_report"]:
        c.execute(
            "SELECT id FROM documents WHERE source = ? ORDER BY word_count DESC LIMIT 40",
            (source,),
        )
        doc_ids = [r[0] for r in c.fetchall()]
        if len(doc_ids) >= 2:
            result = cmd_co_retrieve(
                doc_ids, session_id=f"seed_src_{source}", retrieval_mode="seed_source_affinity"
            )
            pairs = result.get("pairs_updated", 0)
            total_pairs += pairs
            print(f"  Source '{source}': {len(doc_ids)} docs → {pairs} pairs")

    # Strategy 3: PREY8 session co-reference from stigmergy data_json
    print("[Shodh Seed] Strategy 3: PREY8 session doc co-references...")
    import re
    pattern = re.compile(r'"doc_id"\s*:\s*(\d+)')
    c.execute(
        "SELECT subject, GROUP_CONCAT(data_json, '') as all_data "
        "FROM stigmergy_events WHERE event_type LIKE '%prey8%' AND data_json IS NOT NULL "
        "GROUP BY subject "
        "HAVING COUNT(*) >= 2 "
        "LIMIT 100"
    )
    session_co_refs = 0
    for row in c.fetchall():
        combined = row[1] or ""
        found = [int(m) for m in pattern.findall(combined)]
        found = list(set(found))
        if len(found) >= 2:
            result = cmd_co_retrieve(
                found[:20],  # cap at 20 per session
                session_id=f"seed_prey8_{(row[0] or 'unk')[:20]}",
                retrieval_mode="seed_stigmergy_coref",
            )
            total_pairs += result.get("pairs_updated", 0)
            session_co_refs += 1

    print(f"  {session_co_refs} PREY8 session groups processed")

    conn.close()
    conn2 = get_conn()
    c2 = conn2.cursor()
    c2.execute("SELECT COUNT(*) FROM shodh_associations")
    total_assoc = c2.fetchone()[0]
    conn2.close()

    return {
        "status": "OK",
        "total_pairs_seeded": total_pairs,
        "total_associations_in_db": total_assoc,
    }


# ---------------------------------------------------------------------------
# Status report
# ---------------------------------------------------------------------------

def cmd_status() -> dict:
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM shodh_associations")
    total_assoc = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM shodh_co_retrieval")
    total_events = c.fetchone()[0]

    c.execute("SELECT MAX(weight), AVG(weight), MIN(weight) FROM shodh_associations WHERE weight > 0")
    row = c.fetchone()
    max_w, avg_w, min_w = (row[0] or 0, row[1] or 0, row[2] or 0)

    c.execute("SELECT COUNT(*) FROM shodh_associations WHERE weight >= 0.5")
    strong = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM shodh_associations WHERE weight >= 0.1 AND weight < 0.5")
    medium = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM shodh_associations WHERE weight < 0.1")
    weak = c.fetchone()[0]

    # Top 5 strongest associations
    c.execute(
        "SELECT doc_a, doc_b, weight, co_activation_count FROM shodh_associations "
        "ORDER BY weight DESC LIMIT 5"
    )
    top5 = [dict(r) for r in c.fetchall()]

    # Port affinity view
    try:
        c.execute("SELECT * FROM v_hebbian_port_affinity LIMIT 10")
        port_affinity = [dict(r) for r in c.fetchall()]
    except sqlite3.OperationalError:
        port_affinity = []

    conn.close()

    return {
        "status": "OK",
        "shodh_version": "1.0",
        "total_associations": total_assoc,
        "total_co_retrieval_events": total_events,
        "weight_stats": {
            "max": round(max_w, 4),
            "avg": round(avg_w, 4),
            "min": round(min_w, 4),
        },
        "strength_buckets": {
            "strong (>=0.5)": strong,
            "medium (0.1-0.5)": medium,
            "weak (<0.1)": weak,
        },
        "top_5_associations": top5,
        "port_affinity_top10": port_affinity,
        "gamma": GAMMA,
        "decay_factor": DECAY_FACTOR,
        "prune_threshold": PRUNE_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Shodh Hebbian Association Graph for HFO Gen89")
    parser.add_argument("--setup", action="store_true", help="Create schema (idempotent)")
    parser.add_argument("--co-retrieve", metavar="IDS", help="Comma-sep doc IDs to co-retrieve")
    parser.add_argument("--session-id", metavar="SID", help="Session ID for co-retrieval")
    parser.add_argument("--top-for", metavar="DOC_ID", type=int, help="Show top associations for doc")
    parser.add_argument("--top-global", action="store_true", help="Show global top associations")
    parser.add_argument("--limit", type=int, default=20, help="Result limit")
    parser.add_argument("--decay", action="store_true", help="Apply anti-Hebbian decay pass")
    parser.add_argument("--seed-from-stigmergy", action="store_true", help="Seed initial associations")
    parser.add_argument("--status", action="store_true", help="Full status report")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    def out(data: dict) -> None:
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            for k, v in data.items():
                if isinstance(v, (list, dict)):
                    print(f"  {k}:")
                    print(f"    {json.dumps(v, indent=4)}")
                else:
                    print(f"  {k}: {v}")

    if args.setup:
        out(cmd_setup(verbose=not args.json))

    elif args.co_retrieve:
        ids = [int(x.strip()) for x in args.co_retrieve.split(",")]
        out(cmd_co_retrieve(ids, session_id=args.session_id))

    elif args.top_for is not None:
        out(cmd_top_for(args.top_for, limit=args.limit))

    elif args.top_global:
        out(cmd_top_global(limit=args.limit))

    elif args.decay:
        out(cmd_decay())

    elif args.seed_from_stigmergy:
        r = cmd_seed_from_stigmergy()
        out(r)

    elif args.status:
        out(cmd_status())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
