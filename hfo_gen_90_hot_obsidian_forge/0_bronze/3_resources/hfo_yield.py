#!/usr/bin/env python3
"""
hfo_yield.py — PREY8 Session-End Bookend (Yield / Y)

MANDATORY: Called at the END of every agent interaction. Zero exceptions.

Usage:
    python hfo_yield.py --summary "What was accomplished" --probe "Original intent"
    python hfo_yield.py --summary "..." --artifacts "file1.py,file2.md"
    python hfo_yield.py --summary "..." --next "step1,step2"
    python hfo_yield.py --json                     # Machine-readable output
    python hfo_yield.py --interactive              # Prompted input

Writes a hfo.gen89.prey8.yield CloudEvent to stigmergy_events.
Outputs a completion receipt.

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
    return root / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"


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

    payload = json.dumps(envelope, sort_keys=True, default=str)
    envelope["signature"] = hashlib.sha256(payload.encode()).hexdigest()
    return envelope


# ─── Main ─────────────────────────────────────────────────────────────────────

def yield_event(
    summary: str,
    probe: str = None,
    artifacts_created: list = None,
    artifacts_modified: list = None,
    next_steps: list = None,
    insights: list = None,
    nonce: str = None,
    json_output: bool = False,
) -> dict:
    """Execute the Yield bookend. Returns receipt dict."""
    root = find_root()
    db_path = resolve_db(root)

    if not db_path.exists():
        print(f"ERROR: SSOT database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    # ── Get current counts for context ──
    cur = conn.execute("SELECT COUNT(*) FROM stigmergy_events")
    total_events = cur.fetchone()[0]

    cur2 = conn.execute("SELECT COUNT(*) FROM documents")
    total_docs = cur2.fetchone()[0]

    # ── Find matching perceive event (for nonce chain) ──
    perceive_nonce = None
    cur3 = conn.execute(
        "SELECT id, data_json FROM stigmergy_events "
        "WHERE event_type LIKE '%prey8.perceive%' ORDER BY id DESC LIMIT 1"
    )
    row = cur3.fetchone()
    if row and row[1]:
        try:
            pdata = json.loads(row[1])
            perceive_nonce = pdata.get("data", {}).get("nonce")
        except (json.JSONDecodeError, KeyError):
            pass

    # ── Build yield nonce ──
    yield_nonce = nonce or uuid.uuid4().hex[:6].upper()
    ts = datetime.now(timezone.utc).isoformat()

    # ── Build event data ──
    event_data = {
        "probe": probe or "(not provided)",
        "summary": summary,
        "nonce": yield_nonce,
        "perceive_nonce": perceive_nonce,
        "ts": ts,
        "artifacts_created": artifacts_created or [],
        "artifacts_modified": artifacts_modified or [],
        "next_steps": next_steps or [],
        "insights": insights or [],
        "doc_count": total_docs,
        "event_count": total_events,
        "persists": f"PREY8 yield closed. Perceived nonce: {perceive_nonce}. "
                    f"Summary: {summary[:200]}",
    }

    event = make_cloudevent(
        event_type="hfo.gen89.prey8.yield",
        subject="prey-yield",
        data=event_data,
        source="hfo_yield.py_gen89_v1",
    )

    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True, default=str).encode()
    ).hexdigest()

    receipt = {
        "timestamp": ts,
        "nonce": yield_nonce,
        "perceive_nonce": perceive_nonce,
        "summary": summary,
        "artifacts_created": artifacts_created or [],
        "artifacts_modified": artifacts_modified or [],
        "next_steps": next_steps or [],
        "insights": insights or [],
        "hfo_root": str(root),
        "ssot_db": str(db_path),
    }

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
        receipt["yield_event_written"] = True
        receipt["yield_event_hash"] = content_hash
        receipt["new_event_id"] = conn.execute(
            "SELECT MAX(id) FROM stigmergy_events"
        ).fetchone()[0]
    except sqlite3.IntegrityError:
        receipt["yield_event_written"] = False
        receipt["yield_event_note"] = "duplicate content_hash"

    conn.close()

    # ── Output ──
    if json_output:
        print(json.dumps(receipt, indent=2, default=str))
    else:
        print_human(receipt)

    return receipt


def print_human(receipt: dict):
    """Human-readable receipt output."""
    print("=" * 72)
    print("  PREY8 YIELD — Session End Bookend")
    print("=" * 72)
    print(f"  Timestamp      : {receipt['timestamp']}")
    print(f"  Yield Nonce    : {receipt['nonce']}")
    print(f"  Perceive Nonce : {receipt['perceive_nonce'] or '(none found)'}")
    print()
    print(f"  Summary: {receipt['summary']}")
    print()

    if receipt["artifacts_created"]:
        print("  Artifacts Created:")
        for a in receipt["artifacts_created"]:
            print(f"    + {a}")
        print()

    if receipt["artifacts_modified"]:
        print("  Artifacts Modified:")
        for a in receipt["artifacts_modified"]:
            print(f"    ~ {a}")
        print()

    if receipt["next_steps"]:
        print("  Next Steps:")
        for s in receipt["next_steps"]:
            print(f"    -> {s}")
        print()

    if receipt["insights"]:
        print("  Insights:")
        for i in receipt["insights"]:
            print(f"    * {i}")
        print()

    written = receipt.get("yield_event_written", False)
    if written:
        print(f"  >> Yield event WRITTEN to SSOT (id={receipt.get('new_event_id')}, hash: {receipt['yield_event_hash'][:16]}...)")
    else:
        print(f"  >> Yield event NOT written ({receipt.get('yield_event_note', 'unknown')})")

    print()
    print("  Completion Contract (SW-4):")
    print(f"    Given : Session started with perceive nonce {receipt['perceive_nonce'] or 'N/A'}")
    print(f"    When  : Agent completed work and called yield")
    print(f"    Then  : Stigmergy event written={'YES' if written else 'NO'}, nonce={receipt['nonce']}")
    print("=" * 72)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="PREY8 Yield — Session End Bookend")
    parser.add_argument("--summary", "-s", type=str, required=False,
                        help="Summary of what was accomplished this session")
    parser.add_argument("--probe", "-p", type=str, default=None,
                        help="Original user intent / probe text")
    parser.add_argument("--artifacts-created", "-ac", type=str, default=None,
                        help="Comma-separated list of created artifact paths")
    parser.add_argument("--artifacts-modified", "-am", type=str, default=None,
                        help="Comma-separated list of modified artifact paths")
    parser.add_argument("--next", "-n", type=str, default=None,
                        help="Comma-separated list of next steps")
    parser.add_argument("--insights", "-i", type=str, default=None,
                        help="Comma-separated list of insights")
    parser.add_argument("--nonce", type=str, default=None,
                        help="Override yield nonce (default: auto-generated)")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output machine-readable JSON")
    parser.add_argument("--interactive", action="store_true",
                        help="Prompt for input interactively")
    args = parser.parse_args()

    if args.interactive:
        summary = input("Summary of work done: ")
        probe = input("Original probe/intent (or Enter to skip): ") or None
        ac = input("Artifacts created (comma-sep, or Enter): ") or None
        am = input("Artifacts modified (comma-sep, or Enter): ") or None
        ns = input("Next steps (comma-sep, or Enter): ") or None
        ins = input("Insights (comma-sep, or Enter): ") or None

        yield_event(
            summary=summary,
            probe=probe,
            artifacts_created=[x.strip() for x in ac.split(",")] if ac else None,
            artifacts_modified=[x.strip() for x in am.split(",")] if am else None,
            next_steps=[x.strip() for x in ns.split(",")] if ns else None,
            insights=[x.strip() for x in ins.split(",")] if ins else None,
            json_output=args.json,
        )
    else:
        if not args.summary:
            print("ERROR: --summary is required (or use --interactive)", file=sys.stderr)
            sys.exit(1)

        yield_event(
            summary=args.summary,
            probe=args.probe,
            artifacts_created=[x.strip() for x in args.artifacts_created.split(",")] if args.artifacts_created else None,
            artifacts_modified=[x.strip() for x in args.artifacts_modified.split(",")] if args.artifacts_modified else None,
            next_steps=[x.strip() for x in args.next.split(",")] if args.next else None,
            insights=[x.strip() for x in args.insights.split(",")] if args.insights else None,
            nonce=args.nonce,
            json_output=args.json,
        )


if __name__ == "__main__":
    main()
