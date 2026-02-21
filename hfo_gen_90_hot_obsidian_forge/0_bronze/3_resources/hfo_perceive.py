#!/usr/bin/env python3
"""
hfo_perceive.py — PREY8 Session-Start Bookend (Perceive / P)

MANDATORY: Called at the START of every agent interaction. Zero exceptions.

Usage:
    python hfo_perceive.py                           # Context snapshot
    python hfo_perceive.py --probe "user's intent"   # With FTS search
    python hfo_perceive.py --json                    # Machine-readable output

Writes a hfo.gen89.prey8.perceive CloudEvent to stigmergy_events.
Outputs session context for the agent to orient.

Part of the PREY8 loop: Perceive → React → Engage → Yield
"""

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ─── PAL Resolution ──────────────────────────────────────────────────────────

def find_root() -> Path:
    """Walk up from script or CWD to find AGENTS.md (workspace root)."""
    env_root = os.environ.get("HFO_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / "AGENTS.md").exists():
            return p
    for start in [Path.cwd(), Path(__file__).resolve().parent]:
        for ancestor in [start] + list(start.parents):
            if (ancestor / "AGENTS.md").exists():
                return ancestor
    print("ERROR: Cannot find HFO_ROOT", file=sys.stderr)
    sys.exit(1)


def resolve_db(root: Path) -> Path:
    """Resolve SSOT database path via blessed pointers."""
    for name in ["hfo_gen90_pointers_blessed.json", "hfo_gen89_pointers_blessed.json", "hfo_pointers_blessed.json"]:
        fp = root / name
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            pointers = data.get("pointers", data)
            if "ssot.db" in pointers:
                entry = pointers["ssot.db"]
                rel = entry["path"] if isinstance(entry, dict) else entry
                return root / rel
    # Fallback
    return root / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"


# ─── CloudEvent Builder ──────────────────────────────────────────────────────

def make_cloudevent(event_type: str, subject: str, data: dict, source: str) -> dict:
    """Build a CloudEvent 1.0 envelope."""
    now = datetime.now(timezone.utc).isoformat()
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    event_id = uuid.uuid4().hex

    envelope = {
        "specversion": "1.0",
        "id": event_id,
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "parent_span_id": None,
        "phase": "CLOUDEVENT",
        "data": data,
    }

    # Content-hash for dedupe
    payload = json.dumps(envelope, sort_keys=True, default=str)
    envelope["signature"] = hashlib.sha256(payload.encode()).hexdigest()
    return envelope


# ─── SSOT Queries ─────────────────────────────────────────────────────────────

def query_latest_stigmergy(conn: sqlite3.Connection, limit: int = 10) -> list:
    """Get the N most recent stigmergy events."""
    cur = conn.execute(
        "SELECT id, event_type, timestamp, subject, substr(data_json, 1, 500) "
        "FROM stigmergy_events ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    return [
        {"id": r[0], "event_type": r[1], "timestamp": r[2], "subject": r[3], "data_preview": r[4]}
        for r in cur.fetchall()
    ]


def query_doc_stats(conn: sqlite3.Connection) -> dict:
    """Get document counts by source + total."""
    cur = conn.execute(
        "SELECT source, COUNT(*), SUM(word_count) FROM documents GROUP BY source ORDER BY COUNT(*) DESC"
    )
    by_source = {r[0]: {"count": r[1], "words": r[2] or 0} for r in cur.fetchall()}

    cur2 = conn.execute("SELECT COUNT(*), SUM(word_count) FROM documents")
    total = cur2.fetchone()

    return {
        "total_docs": total[0],
        "total_words": total[1] or 0,
        "by_source": by_source,
    }


def query_stigmergy_stats(conn: sqlite3.Connection) -> dict:
    """Get stigmergy event counts."""
    cur = conn.execute("SELECT COUNT(*) FROM stigmergy_events")
    total = cur.fetchone()[0]

    cur2 = conn.execute(
        "SELECT event_type, COUNT(*) FROM stigmergy_events GROUP BY event_type ORDER BY COUNT(*) DESC LIMIT 10"
    )
    top_types = {r[0]: r[1] for r in cur2.fetchall()}

    return {"total_events": total, "top_event_types": top_types}


def query_last_session(conn: sqlite3.Connection) -> dict:
    """Get the most recent perceive and yield events."""
    last_perceive = None
    cur = conn.execute(
        "SELECT id, timestamp, data_json FROM stigmergy_events "
        "WHERE event_type LIKE '%prey8.perceive%' ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        last_perceive = {"id": row[0], "timestamp": row[1], "data": row[2][:500] if row[2] else None}

    last_yield = None
    cur2 = conn.execute(
        "SELECT id, timestamp, data_json FROM stigmergy_events "
        "WHERE event_type LIKE '%prey8.yield%' OR "
        "(event_type LIKE '%payoff%' AND subject = 'prey-yield') "
        "ORDER BY id DESC LIMIT 1"
    )
    row2 = cur2.fetchone()
    if row2:
        last_yield = {"id": row2[0], "timestamp": row2[1], "data": row2[2][:500] if row2[2] else None}

    return {"last_perceive": last_perceive, "last_yield": last_yield}


def query_fts(conn: sqlite3.Connection, probe: str, limit: int = 5) -> list:
    """Full-text search the documents table."""
    try:
        cur = conn.execute(
            "SELECT id, title, bluf, source, port FROM documents "
            "WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) "
            "LIMIT ?",
            (probe, limit)
        )
        return [
            {"id": r[0], "title": r[1], "bluf": r[2][:200] if r[2] else None, "source": r[3], "port": r[4]}
            for r in cur.fetchall()
        ]
    except Exception:
        return []


def query_meta(conn: sqlite3.Connection) -> dict:
    """Get key meta values."""
    cur = conn.execute("SELECT key, substr(value, 1, 200) FROM meta")
    return {r[0]: r[1] for r in cur.fetchall()}


# ─── Main ─────────────────────────────────────────────────────────────────────

def perceive(probe: str = None, json_output: bool = False) -> dict:
    """Execute the Perceive bookend. Returns context dict."""
    root = find_root()
    db_path = resolve_db(root)

    if not db_path.exists():
        print(f"ERROR: SSOT database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    # ── Gather context ──
    context = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hfo_root": str(root),
        "ssot_db": str(db_path),
        "generation": 89,
        "operator": os.environ.get("HFO_OPERATOR", "TTAO"),
    }

    context["doc_stats"] = query_doc_stats(conn)
    context["stigmergy_stats"] = query_stigmergy_stats(conn)
    context["last_session"] = query_last_session(conn)
    context["latest_stigmergy"] = query_latest_stigmergy(conn, 10)
    context["meta"] = query_meta(conn)

    if probe:
        context["fts_results"] = query_fts(conn, probe, 5)

    # ── Nonce for tracing ──
    nonce = uuid.uuid4().hex[:6].upper()
    context["nonce"] = nonce

    # ── Write perceive event to SSOT ──
    event_data = {
        "probe": probe or "(no probe — context snapshot)",
        "nonce": nonce,
        "ts": context["timestamp"],
        "encounter_count": 0,
        "doc_count": context["doc_stats"]["total_docs"],
        "event_count": context["stigmergy_stats"]["total_events"],
        "p6_gate": None,
    }

    event = make_cloudevent(
        event_type="hfo.gen89.prey8.perceive",
        subject="prey-perceive",
        data=event_data,
        source="hfo_perceive.py_gen89_v1",
    )

    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True, default=str).encode()
    ).hexdigest()

    try:
        conn.execute(
            "INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event["type"],
                event["time"],
                event["source"],
                event["subject"],
                json.dumps(event, default=str),
                content_hash,
            )
        )
        conn.commit()
        context["perceive_event_written"] = True
        context["perceive_event_hash"] = content_hash
    except sqlite3.IntegrityError:
        # Duplicate — nonce collision or identical event
        context["perceive_event_written"] = False
        context["perceive_event_note"] = "duplicate content_hash"

    conn.close()

    # ── Output ──
    if json_output:
        print(json.dumps(context, indent=2, default=str))
    else:
        print_human(context, probe)

    return context


def print_human(ctx: dict, probe: str = None):
    """Human-readable context output."""
    print("=" * 72)
    print("  PREY8 PERCEIVE — Session Start Bookend")
    print("=" * 72)
    print(f"  Timestamp : {ctx['timestamp']}")
    print(f"  Nonce     : {ctx['nonce']}")
    print(f"  Generation: {ctx['generation']}")
    print(f"  Operator  : {ctx['operator']}")
    print(f"  SSOT DB   : {ctx['ssot_db']}")
    print()

    ds = ctx["doc_stats"]
    print(f"  Documents : {ds['total_docs']:,} ({ds['total_words']:,} words)")
    for src, info in sorted(ds["by_source"].items(), key=lambda x: -x[1]["count"]):
        print(f"    {src:20s} : {info['count']:>6,} docs, {info['words']:>10,} words")
    print()

    ss = ctx["stigmergy_stats"]
    print(f"  Stigmergy : {ss['total_events']:,} events")
    for et, count in list(ss["top_event_types"].items())[:5]:
        print(f"    {et:50s} : {count:>5}")
    print()

    ls = ctx["last_session"]
    if ls["last_perceive"]:
        print(f"  Last Perceive: id={ls['last_perceive']['id']}, ts={ls['last_perceive']['timestamp']}")
    if ls["last_yield"]:
        print(f"  Last Yield   : id={ls['last_yield']['id']}, ts={ls['last_yield']['timestamp']}")
    print()

    print("  Latest Stigmergy (last 10):")
    for ev in ctx["latest_stigmergy"]:
        print(f"    [{ev['id']:>5}] {ev['event_type'][:50]:50s} | {ev['timestamp']}")
    print()

    if probe and "fts_results" in ctx:
        print(f"  FTS Results for: '{probe}'")
        for r in ctx["fts_results"]:
            print(f"    [{r['id']}] {r['title'][:60]} ({r['source']}, {r['port']})")
        print()

    written = ctx.get("perceive_event_written", False)
    if written:
        print(f"  >> Perceive event WRITTEN to SSOT (hash: {ctx['perceive_event_hash'][:16]}...)")
    else:
        print(f"  >> Perceive event NOT written ({ctx.get('perceive_event_note', 'unknown')})")

    print("=" * 72)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="PREY8 Perceive — Session Start Bookend")
    parser.add_argument("--probe", "-p", type=str, default=None,
                        help="User's intent / query for FTS search")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output machine-readable JSON")
    args = parser.parse_args()
    perceive(probe=args.probe, json_output=args.json)


if __name__ == "__main__":
    main()
