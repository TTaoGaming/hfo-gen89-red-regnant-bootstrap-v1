"""
hfo_identity_sqlite.py — Port Commander Identity Persistence in SQLite

ALL identity data lives in the SSOT SQLite database. No markdown. No JSON files
at runtime — the bundle JSONs are the ONE-TIME ingest source; everything after
that reads from SQLite.

Two tables drive this system:

  port_commander_identity
    One row per port (0-7). Stores the full identity_capsule JSON after ingesting
    from port_bundles/p{n}_bundle.json. Change-detected via bundle_hash so re-
    ingestion is idempotent unless the bundle actually changed.

  port_commander_journal  (defined in hfo_port_journal.py, re-queried here)
    Merkle-chained per-commander memory trail. Time-ladder queries pull four
    non-overlapping windows.

rehydrate(port, conn) → structured dict
  HEALTHY   — identity + journal both present. Full embodiment possible.
  DEGRADED  — identity present, journal empty/missing. Can proceed but no memory.
              Operator is notified which components are absent.
  BROKEN    — identity missing or corrupt. Cannot embody. Fail closed.
              Operator receives exact diagnostic and remediation steps.

CLI:
  # Ingest all 8 port bundles into SQLite (idempotent)
  python hfo_identity_sqlite.py ingest

  # Ingest a single port
  python hfo_identity_sqlite.py ingest --port 4

  # Rehydrate port 4 (JSON output)
  python hfo_identity_sqlite.py rehydrate --port 4

  # Health check all 8 ports
  python hfo_identity_sqlite.py health

  # Force re-ingest even if bundle hash unchanged
  python hfo_identity_sqlite.py ingest --force
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PORTS = tuple(range(8))

COMMANDER_MAP: Dict[int, Tuple[str, str, str]] = {
    0: ("Lidless Legion",   "☰", "OBSERVE"),
    1: ("Web Weaver",       "☱", "BRIDGE"),
    2: ("Mirror Magus",     "☲", "SHAPE"),
    3: ("Harmonic Hydra",   "☳", "INJECT"),
    4: ("Red Regnant",      "☴", "DISRUPT"),
    5: ("Pyre Praetorian",  "☵", "IMMUNIZE"),
    6: ("Kraken Keeper",    "☶", "ASSIMILATE"),
    7: ("Spider Sovereign", "☷", "NAVIGATE"),
}

# Health states
HEALTH_HEALTHY  = "HEALTHY"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_BROKEN   = "BROKEN"

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _find_root() -> Path:
    env_root = os.environ.get("HFO_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / "AGENTS.md").exists():
            return p
    for start in [Path.cwd(), Path(__file__).resolve().parent]:
        for ancestor in [start] + list(start.parents):
            if (ancestor / "AGENTS.md").exists():
                return ancestor
    raise RuntimeError("Cannot find HFO_ROOT (no AGENTS.md found walking up from CWD or script)")


def _resolve_db(root: Optional[Path] = None, db_path: Optional[str] = None) -> Path:
    if db_path:
        return Path(db_path)
    env_path = os.environ.get("HFO_SSOT_DB")
    if env_path:
        return Path(env_path)
    if root is None:
        root = _find_root()
    # Try blessed pointers first
    for ptr_name in ["hfo_gen90_pointers_blessed.json", "hfo_pointers_blessed.json"]:
        fp = root / ptr_name
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            pointers = data.get("pointers", data)
            if "ssot.db" in pointers:
                entry = pointers["ssot.db"]
                rel = entry["path"] if isinstance(entry, dict) else entry
                return root / rel
    return root / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"


def _bundle_dir(root: Optional[Path] = None) -> Path:
    if root is None:
        root = _find_root()
    return root / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources" / "port_bundles"


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_IDENTITY_DDL = """
CREATE TABLE IF NOT EXISTS port_commander_identity (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    port        INTEGER NOT NULL UNIQUE,
    commander   TEXT    NOT NULL,
    trigram     TEXT    NOT NULL,
    word        TEXT    NOT NULL,
    bundle_hash TEXT    NOT NULL,
    identity_json TEXT  NOT NULL,
    ingested_at TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pci_port ON port_commander_identity (port);
"""

_JOURNAL_DDL = """
CREATE TABLE IF NOT EXISTS port_commander_journal (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    port           INTEGER NOT NULL,
    commander      TEXT    NOT NULL,
    session_id     TEXT,
    perceive_nonce TEXT,
    entry_type     TEXT    NOT NULL DEFAULT 'memory',
    content        TEXT    NOT NULL,
    content_hash   TEXT    NOT NULL UNIQUE,
    parent_hash    TEXT    NOT NULL,
    chain_hash     TEXT    NOT NULL,
    timestamp      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pcj_port_ts ON port_commander_journal (port, timestamp);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all required tables if they don't exist. Idempotent."""
    for ddl in [_IDENTITY_DDL, _JOURNAL_DDL]:
        for stmt in ddl.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
    conn.commit()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Bundle ingestion
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest_port(
    port: int,
    conn: sqlite3.Connection,
    root: Optional[Path] = None,
    force: bool = False,
) -> Dict:
    """
    Ingest the identity_capsule from p{port}_bundle.json into port_commander_identity.

    Idempotent — skips if bundle_hash unchanged (unless force=True).

    Returns dict with:
        action   : 'inserted' | 'updated' | 'skipped' | 'error'
        port     : int
        commander: str
        reason   : str (for skipped/error)
    """
    if port not in VALID_PORTS:
        return {"action": "error", "port": port, "reason": f"Invalid port {port!r}"}

    bundle_dir = _bundle_dir(root)
    bundle_path = bundle_dir / f"p{port}_bundle.json"

    if not bundle_path.exists():
        return {
            "action": "error",
            "port": port,
            "reason": f"Bundle file not found: {bundle_path}",
        }

    try:
        bundle_text = bundle_path.read_text(encoding="utf-8")
        bundle = json.loads(bundle_text)
    except Exception as exc:
        return {
            "action": "error",
            "port": port,
            "reason": f"Failed to parse bundle JSON: {exc}",
        }

    # Extract identity_capsule
    capsule = bundle.get("identity_capsule")
    if not capsule:
        return {
            "action": "error",
            "port": port,
            "reason": f"p{port}_bundle.json is missing 'identity_capsule' key. "
                      "Run identity capsule injection first.",
        }

    commander, trigram, word = COMMANDER_MAP[port]
    bundle_hash   = _sha256(bundle_text)
    identity_json = json.dumps(capsule, ensure_ascii=False)
    now           = datetime.now(timezone.utc).isoformat()

    ensure_schema(conn)

    # Check existing row
    existing = conn.execute(
        "SELECT id, bundle_hash FROM port_commander_identity WHERE port = ?", (port,)
    ).fetchone()

    if existing and existing[1] == bundle_hash and not force:
        return {
            "action": "skipped",
            "port": port,
            "commander": commander,
            "reason": "bundle_hash unchanged — no update needed",
        }

    if existing:
        conn.execute(
            """
            UPDATE port_commander_identity
            SET commander=?, trigram=?, word=?, bundle_hash=?,
                identity_json=?, updated_at=?
            WHERE port=?
            """,
            (commander, trigram, word, bundle_hash, identity_json, now, port),
        )
        conn.commit()
        return {
            "action": "updated",
            "port": port,
            "commander": commander,
            "bundle_hash": bundle_hash[:16],
            "reason": "force=True" if force else "bundle_hash changed",
        }
    else:
        conn.execute(
            """
            INSERT INTO port_commander_identity
                (port, commander, trigram, word, bundle_hash, identity_json, ingested_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (port, commander, trigram, word, bundle_hash, identity_json, now, now),
        )
        conn.commit()
        return {
            "action": "inserted",
            "port": port,
            "commander": commander,
            "bundle_hash": bundle_hash[:16],
        }


def ingest_all(
    conn: sqlite3.Connection,
    root: Optional[Path] = None,
    force: bool = False,
) -> List[Dict]:
    """Ingest all 8 port bundles. Returns list of per-port result dicts."""
    ensure_schema(conn)
    results = []
    for port in VALID_PORTS:
        results.append(ingest_port(port, conn, root=root, force=force))
    return results


# ---------------------------------------------------------------------------
# Time-ladder query (standalone, no hfo_port_journal import needed)
# ---------------------------------------------------------------------------

_LADDER_WINDOWS: List[Tuple[str, str, str, Optional[str]]] = [
    ("tier_1_1hr",    "Last 1 Hour",    "-1 hour",   None),
    ("tier_2_1day",   "Last 24 Hours",  "-24 hours", "-1 hour"),
    ("tier_3_1week",  "Last 7 Days",    "-7 days",   "-24 hours"),
    ("tier_4_1month", "Last 30 Days",   "-30 days",  "-7 days"),
]


def _query_time_ladder(port: int, conn: sqlite3.Connection) -> Dict:
    """
    Query port_commander_journal for all 4 time-ladder tiers.

    Returns dict with keys: tier_1_1hr, tier_2_1day, tier_3_1week, tier_4_1month,
    total_entries, chain_head (latest entry or None).
    """
    if not _table_exists(conn, "port_commander_journal"):
        return {
            "available": False,
            "reason": "port_commander_journal table does not exist",
            "tier_1_1hr": [], "tier_2_1day": [], "tier_3_1week": [], "tier_4_1month": [],
            "total_entries": 0, "chain_head": None,
        }

    ladder: Dict[str, Any] = {"available": True, "total_entries": 0, "chain_head": None}

    for key, _label, newer_than, older_than in _LADDER_WINDOWS:
        where = "WHERE port = ? AND timestamp >= datetime('now', ?)"
        params: List[Any] = [port, newer_than]
        if older_than:
            where += " AND timestamp < datetime('now', ?)"
            params.append(older_than)

        rows = conn.execute(
            f"SELECT id, entry_type, content, chain_hash, timestamp, "
            f"       session_id, perceive_nonce "
            f"FROM port_commander_journal {where} ORDER BY timestamp DESC",
            params,
        ).fetchall()

        ladder[key] = [
            {
                "id":             r[0],
                "entry_type":     r[1],
                "content":        r[2],
                "chain_hash":     r[3],
                "timestamp":      r[4],
                "session_id":     r[5],
                "perceive_nonce": r[6],
            }
            for r in rows
        ]

    # Total + chain head
    total_row = conn.execute(
        "SELECT COUNT(*) FROM port_commander_journal WHERE port = ?", (port,)
    ).fetchone()
    ladder["total_entries"] = total_row[0] if total_row else 0

    head = conn.execute(
        "SELECT id, entry_type, content, chain_hash, timestamp "
        "FROM port_commander_journal WHERE port = ? ORDER BY id DESC LIMIT 1",
        (port,),
    ).fetchone()
    if head:
        ladder["chain_head"] = {
            "id": head[0], "entry_type": head[1], "content": head[2],
            "chain_hash": head[3], "timestamp": head[4],
        }

    return ladder


# ---------------------------------------------------------------------------
# Fail-closed health check
# ---------------------------------------------------------------------------

def _build_operator_report(port: int, missing: List[str], degraded: List[str]) -> str:
    commander, trigram, word = COMMANDER_MAP[port]
    lines = [
        f"OPERATOR REPORT — P{port} {trigram} {word} / {commander}",
        "",
    ]
    if missing:
        lines.append("BROKEN — cannot embody commander. Missing required components:")
        for m in missing:
            lines.append(f"  ✗ {m}")
        lines.append("")
        lines.append("REMEDIATION:")
        if any("port_commander_identity" in m for m in missing):
            lines.append(
                f"  Run: python hfo_identity_sqlite.py ingest --port {port}"
            )
            lines.append(
                "  This ingests the identity_capsule from the port bundle JSON into SQLite."
            )
        if any("identity_capsule" in m for m in missing):
            lines.append(
                f"  The p{port}_bundle.json is missing its identity_capsule key."
            )
            lines.append(
                "  Run the identity capsule injection pass before ingesting."
            )
    if degraded:
        lines.append("DEGRADED — proceeding without:")
        for d in degraded:
            lines.append(f"  ⚠ {d}")
        lines.append("")
        lines.append("REMEDIATION:")
        if any("journal" in d for d in degraded):
            lines.append(
                f"  Write journal entries: python hfo_port_journal.py write --port {port} "
                "--content '...' --type memory"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core rehydrate
# ---------------------------------------------------------------------------

def rehydrate(
    port: int,
    conn: sqlite3.Connection,
    root: Optional[Path] = None,
) -> Dict:
    """
    Rehydrate the full commander context for ``port`` from SQLite.

    Returns a structured dict:
    {
        "port":                 int,
        "commander":            str,
        "trigram":              str,
        "word":                 str,
        "health":               "HEALTHY" | "DEGRADED" | "BROKEN",
        "missing":              [],      # BROKEN components
        "degraded":             [],      # DEGRADED (present but limited)
        "identity":             {} | None,
        "cognitive_persistence": {},
        "diagnostics":          {},
        "operator_report":      str | None,  # present if not HEALTHY
        "ingested_at":          str | None,
        "bundle_hash":          str | None,
    }

    Fail-closed contract:
        BROKEN   → identity is None, operator_report explains what to run
        DEGRADED → identity is populated, journal is empty/absent
        HEALTHY  → identity + journal both present
    """
    if port not in VALID_PORTS:
        return {
            "port": port, "health": HEALTH_BROKEN,
            "missing": [f"port {port!r} is invalid — must be 0-7"],
            "degraded": [], "identity": None, "cognitive_persistence": {},
            "diagnostics": {}, "operator_report": f"Port {port!r} is not a valid octree port.",
        }

    commander, trigram, word = COMMANDER_MAP[port]
    missing:   List[str] = []
    degraded:  List[str] = []
    diagnostics: Dict[str, Any] = {}

    ensure_schema(conn)

    # ── 1. Identity table ────────────────────────────────────────────────────
    identity_table_ok = _table_exists(conn, "port_commander_identity")
    diagnostics["identity_table_exists"] = identity_table_ok

    identity = None
    ingested_at = None
    bundle_hash = None

    if not identity_table_ok:
        missing.append(
            "port_commander_identity table is absent from the SSOT database"
        )
    else:
        row = conn.execute(
            "SELECT identity_json, ingested_at, updated_at, bundle_hash "
            "FROM port_commander_identity WHERE port = ?",
            (port,),
        ).fetchone()
        diagnostics["identity_row_exists"] = row is not None

        if row is None:
            missing.append(
                f"No identity row for P{port} {trigram} {commander} in "
                "port_commander_identity. Run: "
                f"python hfo_identity_sqlite.py ingest --port {port}"
            )
        else:
            try:
                identity = json.loads(row[0])
                ingested_at = row[1]
                bundle_hash = row[3]
                if not identity:
                    missing.append(
                        f"P{port} identity_json parsed to empty/null — "
                        "re-ingest: python hfo_identity_sqlite.py ingest --port {port} --force"
                    )
                    identity = None
            except Exception as exc:
                missing.append(
                    f"P{port} identity_json is corrupt (JSON parse error: {exc}) — "
                    f"re-ingest: python hfo_identity_sqlite.py ingest --port {port} --force"
                )
                identity = None

    # ── 2. Cognitive persistence / journal ───────────────────────────────────
    journal_table_ok = _table_exists(conn, "port_commander_journal")
    diagnostics["journal_table_exists"] = journal_table_ok

    cog: Dict[str, Any] = {}
    if not journal_table_ok:
        degraded.append(
            "port_commander_journal table absent — no memory trail available"
        )
        cog = {
            "available": False, "reason": "table absent",
            "tier_1_1hr": [], "tier_2_1day": [], "tier_3_1week": [], "tier_4_1month": [],
            "total_entries": 0, "chain_head": None,
        }
    else:
        cog = _query_time_ladder(port, conn)
        diagnostics["journal_entry_count"] = cog.get("total_entries", 0)
        if cog.get("total_entries", 0) == 0:
            degraded.append(
                f"P{port} journal is empty — no memory trail yet. "
                f"Write entries: python hfo_port_journal.py write --port {port} --content '...' --type memory"
            )

    # ── 3. Determine health ──────────────────────────────────────────────────
    if missing:
        health = HEALTH_BROKEN
    elif degraded:
        health = HEALTH_DEGRADED
    else:
        health = HEALTH_HEALTHY

    # ── 4. Build operator report if not HEALTHY ──────────────────────────────
    operator_report = None
    if health != HEALTH_HEALTHY:
        operator_report = _build_operator_report(port, missing, degraded)

    return {
        "port":                  port,
        "commander":             commander,
        "trigram":               trigram,
        "word":                  word,
        "health":                health,
        "missing":               missing,
        "degraded":              degraded,
        "identity":              identity,
        "cognitive_persistence": cog,
        "diagnostics":           diagnostics,
        "operator_report":       operator_report,
        "ingested_at":           ingested_at,
        "bundle_hash":           bundle_hash,
    }


# ---------------------------------------------------------------------------
# Health check — all 8 ports
# ---------------------------------------------------------------------------

def health_check_all(conn: sqlite3.Connection, root: Optional[Path] = None) -> List[Dict]:
    """Return lightweight health status for all 8 ports (no full rehydrate)."""
    ensure_schema(conn)
    identity_table_ok = _table_exists(conn, "port_commander_identity")
    journal_table_ok  = _table_exists(conn, "port_commander_journal")

    results = []
    for port in VALID_PORTS:
        commander, trigram, word = COMMANDER_MAP[port]
        identity_row = None
        if identity_table_ok:
            identity_row = conn.execute(
                "SELECT bundle_hash, ingested_at FROM port_commander_identity WHERE port = ?",
                (port,),
            ).fetchone()

        journal_count = 0
        if journal_table_ok:
            row = conn.execute(
                "SELECT COUNT(*) FROM port_commander_journal WHERE port = ?", (port,)
            ).fetchone()
            journal_count = row[0] if row else 0

        has_identity = identity_row is not None
        has_journal  = journal_count > 0

        if not has_identity:
            health = HEALTH_BROKEN
        elif not has_journal:
            health = HEALTH_DEGRADED
        else:
            health = HEALTH_HEALTHY

        results.append({
            "port":           port,
            "commander":      commander,
            "trigram":        trigram,
            "word":           word,
            "health":         health,
            "has_identity":   has_identity,
            "has_journal":    has_journal,
            "journal_entries": journal_count,
            "bundle_hash":    identity_row[0][:16] + "…" if identity_row else None,
            "ingested_at":    identity_row[1] if identity_row else None,
        })
    return results


# ---------------------------------------------------------------------------
# Convenience: open SSOT connection
# ---------------------------------------------------------------------------

def open_ssot(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open the SSOT SQLite database with WAL mode + busy timeout."""
    root = _find_root()
    path = _resolve_db(root=root, db_path=db_path)
    if not path.exists():
        raise FileNotFoundError(
            f"SSOT database not found at {path}\n"
            "Verify HFO_SSOT_DB env var or pointer registry."
        )
    conn = sqlite3.connect(str(path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = None  # plain tuples — caller can set row_factory if needed
    return conn


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_ingest_results(results: List[Dict]) -> None:
    for r in results:
        port = r.get("port", "?")
        action = r.get("action", "?")
        commander = r.get("commander", COMMANDER_MAP.get(port, ("?", "?", "?"))[0])
        if action == "error":
            print(f"  P{port} ✗ ERROR   — {r.get('reason')}")
        elif action == "skipped":
            print(f"  P{port} ○ SKIPPED — {commander} (bundle unchanged)")
        elif action == "inserted":
            print(f"  P{port} ✓ INSERTED — {commander}  hash:{r.get('bundle_hash', '?')}")
        elif action == "updated":
            print(f"  P{port} ↺ UPDATED — {commander}  hash:{r.get('bundle_hash', '?')}  ({r.get('reason')})")
        else:
            print(f"  P{port} ? {action} — {r}")


def main() -> None:
    import argparse

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="HFO Port Commander Identity SQLite — ingest, rehydrate, & health",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- ingest ---
    ing = sub.add_parser("ingest", help="Ingest port bundle(s) into SQLite")
    ing.add_argument("--port", type=int, choices=list(VALID_PORTS), default=None,
                     help="Specific port to ingest (default: all 8)")
    ing.add_argument("--force", action="store_true",
                     help="Re-ingest even if bundle hash is unchanged")
    ing.add_argument("--db", type=str, default=None)

    # --- rehydrate ---
    reh = sub.add_parser("rehydrate", help="Rehydrate full context for a port")
    reh.add_argument("--port", type=int, required=True, choices=list(VALID_PORTS))
    reh.add_argument("--db", type=str, default=None)

    # --- health ---
    hlt = sub.add_parser("health", help="Health check all 8 ports")
    hlt.add_argument("--db", type=str, default=None)

    args = parser.parse_args()

    try:
        conn = open_ssot(db_path=getattr(args, "db", None))
    except FileNotFoundError as exc:
        print(f"✗ BROKEN: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.cmd == "ingest":
        root = _find_root()
        if args.port is not None:
            results = [ingest_port(args.port, conn, root=root, force=args.force)]
        else:
            results = ingest_all(conn, root=root, force=args.force)
        _print_ingest_results(results)
        errors = [r for r in results if r.get("action") == "error"]
        if errors:
            print(f"\n{len(errors)} error(s) occurred.", file=sys.stderr)
            sys.exit(1)

    elif args.cmd == "rehydrate":
        root = _find_root()
        result = rehydrate(args.port, conn, root=root)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        if result["health"] == HEALTH_BROKEN:
            sys.exit(2)
        if result["health"] == HEALTH_DEGRADED:
            sys.exit(1)

    elif args.cmd == "health":
        results = health_check_all(conn)
        icon = {HEALTH_HEALTHY: "✓", HEALTH_DEGRADED: "⚠", HEALTH_BROKEN: "✗"}
        print(f"{'Port':<6} {'Health':<10} {'Commander':<20} {'Identity':<10} {'Journal':<8} {'Entries'}")
        print("─" * 80)
        any_broken = False
        for r in results:
            h = r["health"]
            if h == HEALTH_BROKEN:
                any_broken = True
            print(
                f"P{r['port']:<5} {icon[h]} {h:<8}  {r['commander']:<20} "
                f"{'YES' if r['has_identity'] else 'NO':<10} "
                f"{'YES' if r['has_journal'] else 'NO':<8} "
                f"{r['journal_entries']}"
            )
        if any_broken:
            sys.exit(2)


if __name__ == "__main__":
    main()
