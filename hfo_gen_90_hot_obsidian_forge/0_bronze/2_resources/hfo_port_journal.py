"""
hfo_port_journal.py — Port Commander Cognitive Persistence Layer

Maintains a merkle-chained SQLite journal (``port_commander_journal`` table) in
the SSOT database. Every journal entry is SHA256-hashed over its content PLUS the
previous entry's hash, producing an immutable chain per commander. Tampering with
any historical entry breaks all subsequent hashes.

Journal Schema (``port_commander_journal`` table):
  id             INTEGER  PK autoincrement
  port           INTEGER  0-7
  commander      TEXT     e.g. "Red Regnant"
  session_id     TEXT     PREY8 session id (optional)
  perceive_nonce TEXT     PREY8 perceive nonce (optional)
  entry_type     TEXT     memory | insight | decision | artifact | attack | delivery
  content        TEXT     Free-form journal entry
  content_hash   TEXT     SHA256(content)         — deduplication key (UNIQUE)
  parent_hash    TEXT     Previous chain entry's chain_hash ("GENESIS" for first)
  chain_hash     TEXT     SHA256(content + parent_hash) — merkle link
  timestamp      TEXT     ISO-8601 UTC

Time-Ladder Query:
  Returns four non-overlapping windows (most recent first):
    Tier 1 — last 1 hour
    Tier 2 — 1 hour → 24 hours
    Tier 3 — 1 day  → 7 days
    Tier 4 — 7 days → 30 days

CLI Usage:
  # Write a memory entry for P4
  python hfo_port_journal.py write --port 4 --type memory \\
      --content "Boundary violation: port param unchecked before bundle load"

  # Write with PREY8 context
  python hfo_port_journal.py write --port 4 --type attack \\
      --content "ATTACK: port=-1 → IndexError. Mutant survived." \\
      --session "sess_abc123" --nonce "50D47A"

  # Read time ladder for P4
  python hfo_port_journal.py ladder --port 4

  # Read chain head (latest entry) for P7
  python hfo_port_journal.py head --port 7

  # Verify chain integrity for P0
  python hfo_port_journal.py verify --port 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PORTS = tuple(range(8))

COMMANDER_MAP: Dict[int, Tuple[str, str, str]] = {
    0: ("Lidless Legion",    "☰", "OBSERVE"),
    1: ("Web Weaver",        "☱", "BRIDGE"),
    2: ("Mirror Magus",      "☲", "SHAPE"),
    3: ("Harmonic Hydra",    "☳", "INJECT"),
    4: ("Red Regnant",       "☴", "DISRUPT"),
    5: ("Pyre Praetorian",   "☵", "IMMUNIZE"),
    6: ("Kraken Keeper",     "☶", "ASSIMILATE"),
    7: ("Spider Sovereign",  "☷", "NAVIGATE"),
}

VALID_ENTRY_TYPES = {
    "memory", "insight", "decision", "artifact", "attack", "delivery", "note"
}

_DEFAULT_DB_RELATIVE = (
    "hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"
)

# ---------------------------------------------------------------------------
# DB path resolution (mirrors hfo_port_context_bundle.py)
# ---------------------------------------------------------------------------

def _resolve_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return db_path
    env_path = os.environ.get("HFO_SSOT_DB")
    if env_path:
        return env_path
    candidate = Path(__file__)
    for _ in range(10):
        candidate = candidate.parent
        if (candidate / "AGENTS.md").exists():
            return str(candidate / _DEFAULT_DB_RELATIVE)
    return _DEFAULT_DB_RELATIVE


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

DDL = """
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
CREATE INDEX IF NOT EXISTS idx_pcj_port_ts  ON port_commander_journal (port, timestamp);
CREATE INDEX IF NOT EXISTS idx_pcj_chain    ON port_commander_journal (port, chain_hash);
CREATE INDEX IF NOT EXISTS idx_pcj_type     ON port_commander_journal (port, entry_type);
"""

def _ensure_schema(conn: sqlite3.Connection) -> None:
    for stmt in DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chain_hash(content: str, parent_hash: str) -> str:
    """SHA256(content + parent_hash) — the merkle link."""
    return _sha256(content + parent_hash)


# ---------------------------------------------------------------------------
# Core write operation
# ---------------------------------------------------------------------------

def write_entry(
    port: int,
    content: str,
    entry_type: str = "memory",
    session_id: Optional[str] = None,
    perceive_nonce: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict:
    """
    Write a journal entry for ``port``. Returns the written row as a dict.

    Raises:
        ValueError  — invalid port or entry_type
        sqlite3.IntegrityError — duplicate content (content_hash UNIQUE)
    """
    if port not in VALID_PORTS:
        raise ValueError(f"Invalid port {port!r}. Must be 0-7.")
    if entry_type not in VALID_ENTRY_TYPES:
        raise ValueError(f"Invalid entry_type {entry_type!r}. Must be one of {VALID_ENTRY_TYPES}.")

    commander, trigram, word = COMMANDER_MAP[port]
    db = _resolve_db_path(db_path)
    ts  = datetime.now(timezone.utc).isoformat()
    content_hash = _sha256(content)

    with sqlite3.connect(db) as conn:
        _ensure_schema(conn)

        # Get the current chain head for this port
        row = conn.execute(
            "SELECT chain_hash FROM port_commander_journal "
            "WHERE port = ? ORDER BY id DESC LIMIT 1",
            (port,),
        ).fetchone()
        parent = row[0] if row else "GENESIS"

        ch = _chain_hash(content, parent)

        conn.execute(
            """
            INSERT INTO port_commander_journal
                (port, commander, session_id, perceive_nonce, entry_type,
                 content, content_hash, parent_hash, chain_hash, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (port, commander, session_id, perceive_nonce, entry_type,
             content, content_hash, parent, ch, ts),
        )
        conn.commit()

        row_id = conn.execute(
            "SELECT id FROM port_commander_journal WHERE chain_hash = ?", (ch,)
        ).fetchone()[0]

    return {
        "id":             row_id,
        "port":           port,
        "commander":      commander,
        "trigram":        trigram,
        "entry_type":     entry_type,
        "content":        content,
        "content_hash":   content_hash,
        "parent_hash":    parent,
        "chain_hash":     ch,
        "timestamp":      ts,
        "session_id":     session_id,
        "perceive_nonce": perceive_nonce,
    }


# ---------------------------------------------------------------------------
# Time-ladder query
# ---------------------------------------------------------------------------

_LADDER_WINDOWS = [
    ("1 hour",  "TIER-1 · Last 1 Hour",          "-1 hour",   None),
    ("1 day",   "TIER-2 · Last 24 Hours",         "-24 hours", "-1 hour"),
    ("1 week",  "TIER-3 · Last 7 Days",           "-7 days",   "-24 hours"),
    ("1 month", "TIER-4 · Last 30 Days",          "-30 days",  "-7 days"),
]

def get_time_ladder(
    port: int,
    db_path: Optional[str] = None,
    as_markdown: bool = True,
) -> str | List[Dict]:
    """
    Return a time-ladder context bundle for ``port``.

    Each tier is NON-OVERLAPPING — tier-2 shows only entries older than 1 hr
    but newer than 24 hr, etc.

    Args:
        port        : 0-7
        db_path     : path to SSOT SQLite (resolved automatically if None)
        as_markdown : if True returns formatted markdown string;
                      if False returns list of dicts per tier

    Returns:
        Markdown string or list of tier dicts depending on ``as_markdown``.
    """
    if port not in VALID_PORTS:
        raise ValueError(f"Invalid port {port!r}.")

    commander, trigram, word = COMMANDER_MAP[port]
    db = _resolve_db_path(db_path)
    tiers = []

    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_schema(conn)

            for _label_short, label, newer_than, older_than in _LADDER_WINDOWS:
                where = "WHERE port = ? AND timestamp >= datetime('now', ?)"
                params: list = [port, newer_than]
                if older_than:
                    where += " AND timestamp < datetime('now', ?)"
                    params.append(older_than)

                rows = conn.execute(
                    f"SELECT id, entry_type, content, chain_hash, "
                    f"       timestamp, session_id, perceive_nonce "
                    f"FROM port_commander_journal "
                    f"{where} "
                    f"ORDER BY timestamp DESC",
                    params,
                ).fetchall()

                tiers.append({
                    "label":   label,
                    "window":  _label_short,
                    "count":   len(rows),
                    "entries": [dict(r) for r in rows],
                })
    except sqlite3.OperationalError:
        # DB doesn't exist yet or table missing — return empty tiers
        for _, label, *_ in _LADDER_WINDOWS:
            tiers.append({"label": label, "window": "", "count": 0, "entries": []})

    if not as_markdown:
        return tiers

    # --- Render as markdown ---
    lines: List[str] = []
    total = sum(t["count"] for t in tiers)

    lines.append(f"## ⏱ COGNITIVE PERSISTENCE — {trigram} P{port} {word} Time Ladder")
    lines.append(f"> **Commander:** {commander} | **Total entries in window:** {total}")
    lines.append("")

    for tier in tiers:
        label  = tier["label"]
        count  = tier["count"]
        entries = tier["entries"]

        lines.append(f"### {label}  ({count} entries)")
        if not entries:
            lines.append("_No journal entries in this window._")
        else:
            for e in entries:
                ts_short = e["timestamp"][:19].replace("T", " ")
                nonce = f" `{e['perceive_nonce']}`" if e.get("perceive_nonce") else ""
                chain_short = e["chain_hash"][:8]
                lines.append(
                    f"- **[{e['entry_type'].upper()}]** `{ts_short}`{nonce} "
                    f"· `chain:{chain_short}`"
                )
                # Content — indent continuation lines
                content_lines = e["content"].strip().splitlines()
                lines.append(f"  > {content_lines[0]}")
                for cl in content_lines[1:]:
                    lines.append(f"  > {cl}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chain head
# ---------------------------------------------------------------------------

def get_chain_head(port: int, db_path: Optional[str] = None) -> Optional[Dict]:
    """Return the most recent journal entry for ``port``, or None if empty."""
    if port not in VALID_PORTS:
        raise ValueError(f"Invalid port {port!r}.")

    db = _resolve_db_path(db_path)
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM port_commander_journal "
                "WHERE port = ? ORDER BY id DESC LIMIT 1",
                (port,),
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.OperationalError:
        return None


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------

def verify_chain(port: int, db_path: Optional[str] = None) -> Dict:
    """
    Walk the full journal chain for ``port`` and verify every merkle link.

    Returns a dict with:
        port, commander, total_entries, broken_at (list of IDs), valid (bool)
    """
    if port not in VALID_PORTS:
        raise ValueError(f"Invalid port {port!r}.")

    commander, trigram, word = COMMANDER_MAP[port]
    db = _resolve_db_path(db_path)
    broken: List[int] = []
    total = 0

    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_schema(conn)
            rows = conn.execute(
                "SELECT id, content, parent_hash, chain_hash "
                "FROM port_commander_journal "
                "WHERE port = ? ORDER BY id ASC",
                (port,),
            ).fetchall()

            for row in rows:
                total += 1
                expected = _chain_hash(row["content"], row["parent_hash"])
                if expected != row["chain_hash"]:
                    broken.append(row["id"])
    except sqlite3.OperationalError:
        pass

    return {
        "port":          port,
        "commander":     commander,
        "trigram":       trigram,
        "total_entries": total,
        "broken_at":     broken,
        "valid":         len(broken) == 0,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_write(args: argparse.Namespace) -> None:
    try:
        result = write_entry(
            port=args.port,
            content=args.content,
            entry_type=args.type,
            session_id=getattr(args, "session", None),
            perceive_nonce=getattr(args, "nonce", None),
            db_path=getattr(args, "db", None),
        )
        commander, trigram, word = COMMANDER_MAP[args.port]
        print(f"✓ Journal entry written")
        print(f"  Port     : P{args.port} {trigram} {word} / {commander}")
        print(f"  ID       : {result['id']}")
        print(f"  Type     : {result['entry_type']}")
        print(f"  Chain    : {result['chain_hash'][:16]}…")
        print(f"  Parent   : {result['parent_hash'][:16]}…")
        print(f"  Timestamp: {result['timestamp']}")
    except sqlite3.IntegrityError:
        print("⚠  Duplicate entry — this content has already been recorded (content_hash collision).")
        sys.exit(1)
    except Exception as exc:
        print(f"✗ Error: {exc}")
        sys.exit(1)


def _cli_ladder(args: argparse.Namespace) -> None:
    md = get_time_ladder(args.port, db_path=getattr(args, "db", None))
    print(md)


def _cli_head(args: argparse.Namespace) -> None:
    head = get_chain_head(args.port, db_path=getattr(args, "db", None))
    if head is None:
        commander, trigram, word = COMMANDER_MAP[args.port]
        print(f"  P{args.port} {trigram} {word} / {commander} — no journal entries yet.")
    else:
        print(json.dumps(head, indent=2))


def _cli_verify(args: argparse.Namespace) -> None:
    result = verify_chain(args.port, db_path=getattr(args, "db", None))
    status = "✓ VALID" if result["valid"] else f"✗ BROKEN at entry IDs: {result['broken_at']}"
    print(f"Chain verification — P{result['port']} {result['trigram']} {result['commander']}")
    print(f"  Total entries : {result['total_entries']}")
    print(f"  Status        : {status}")
    if not result["valid"]:
        sys.exit(1)


def main() -> None:
    # Force UTF-8 stdout on Windows (trigram symbols ☰ ☱ ☲ … are outside cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="HFO Port Commander Cognitive Persistence Journal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- write ---
    w = sub.add_parser("write", help="Write a journal entry for a port commander")
    w.add_argument("--port",    type=int, required=True, choices=VALID_PORTS)
    w.add_argument("--content", type=str, required=True, help="Journal entry text")
    w.add_argument("--type",    type=str, default="memory",
                   choices=sorted(VALID_ENTRY_TYPES), help="Entry classification")
    w.add_argument("--session", type=str, default=None, help="PREY8 session_id")
    w.add_argument("--nonce",   type=str, default=None, help="PREY8 perceive nonce")
    w.add_argument("--db",      type=str, default=None, help="Override SSOT DB path")

    # --- ladder ---
    la = sub.add_parser("ladder", help="Print time-ladder context bundle for a port")
    la.add_argument("--port", type=int, required=True, choices=VALID_PORTS)
    la.add_argument("--db",   type=str, default=None)

    # --- head ---
    h = sub.add_parser("head", help="Show the latest journal entry for a port")
    h.add_argument("--port", type=int, required=True, choices=VALID_PORTS)
    h.add_argument("--db",   type=str, default=None)

    # --- verify ---
    v = sub.add_parser("verify", help="Verify merkle chain integrity for a port")
    v.add_argument("--port", type=int, required=True, choices=VALID_PORTS)
    v.add_argument("--db",   type=str, default=None)

    args = parser.parse_args()
    dispatch = {
        "write":  _cli_write,
        "ladder": _cli_ladder,
        "head":   _cli_head,
        "verify": _cli_verify,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
