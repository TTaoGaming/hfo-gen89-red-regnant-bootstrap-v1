"""
HFO Session Recovery — Orphan Reaper and Yield Enforcement.

Port: P5 IMMUNIZE (Pyre Praetorian) — detection, quarantine, hardening.
Medallion: bronze (new implementation).

Scans SSOT for orphaned PREY8 perceive events (perceives without matching yields)
and closes them with structured failure yield events.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def scan_orphans(db_path: str, max_age_hours: int = 24) -> list[dict]:
    """Scan for orphaned perceive events without matching yields.

    Args:
        db_path: Path to SSOT SQLite database
        max_age_hours: Only report orphans older than this (default: 24h)

    Returns:
        List of orphaned session records with: event_id, timestamp,
        session_id, nonce, probe, age_hours
    """
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)

    try:
        # Get all perceive events
        cur = conn.execute(
            "SELECT id, timestamp, data_json FROM stigmergy_events "
            "WHERE event_type LIKE '%prey8.perceive%' "
            "ORDER BY timestamp DESC"
        )

        # Get all yield session IDs for matching
        yield_cur = conn.execute(
            "SELECT data_json FROM stigmergy_events "
            "WHERE event_type LIKE '%prey8.yield%'"
        )
        yield_sessions = set()
        for row in yield_cur.fetchall():
            try:
                data = json.loads(row[0]).get("data", {})
                sid = data.get("session_id", "")
                if sid:
                    yield_sessions.add(sid)
            except (json.JSONDecodeError, KeyError):
                pass

        orphans = []
        for row in cur.fetchall():
            event_id, timestamp, data_json = row
            try:
                data = json.loads(data_json).get("data", {})
                session_id = data.get("session_id", "")
                nonce = data.get("nonce", "")
                probe = data.get("probe", "")[:200]

                # Check if this session ever yielded
                if session_id and session_id not in yield_sessions:
                    # Check age
                    try:
                        ts = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                        age_hours = (now - ts).total_seconds() / 3600
                    except ValueError:
                        age_hours = 0

                    if age_hours >= max_age_hours:
                        orphans.append({
                            "event_id": event_id,
                            "timestamp": timestamp,
                            "session_id": session_id,
                            "nonce": nonce,
                            "probe": probe,
                            "age_hours": round(age_hours, 1),
                        })
            except (json.JSONDecodeError, KeyError):
                pass

        return orphans
    finally:
        conn.close()


def reap_orphans(db_path: str, max_age_hours: int = 24) -> dict:
    """Close orphaned sessions with failure yield events.

    Scans for orphans and writes a structured failure yield for each,
    improving the yield ratio and leaving audit trails.

    Returns:
        dict with: reaped, total_orphans, yield_ratio_before, yield_ratio_after
    """
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc)

    try:
        # Get current yield ratio
        perceives = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events "
            "WHERE event_type LIKE '%prey8.perceive%'"
        ).fetchone()[0]
        yields_before = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events "
            "WHERE event_type LIKE '%prey8.yield%'"
        ).fetchone()[0]

        ratio_before = yields_before / max(perceives, 1) * 100

        # Find orphans
        orphans = scan_orphans(db_path, max_age_hours)

        reaped = 0
        for orphan in orphans:
            ts = now.isoformat()
            event = {
                "specversion": "1.0",
                "id": hashlib.sha256(
                    f"reaper:{orphan['session_id']}:{ts}".encode()
                ).hexdigest()[:32],
                "type": "hfo.gen90.prey8.yield",
                "source": "hfo_session_recovery_reaper",
                "subject": "prey-yield-reaper",
                "time": ts,
                "timestamp": ts,
                "datacontenttype": "application/json",
                "data": {
                    "summary": f"REAPER: Auto-closed orphaned session {orphan['session_id']} "
                               f"(age: {orphan['age_hours']:.1f}h, probe: {orphan['probe'][:100]})",
                    "session_id": orphan["session_id"],
                    "perceive_nonce": orphan["nonce"],
                    "reaper_action": "auto_close",
                    "age_hours": orphan["age_hours"],
                    "original_probe": orphan["probe"],
                    "p3_delivery_manifest": ["REAPER: orphan auto-closed"],
                    "p5_test_evidence": ["Session orphaned — no yield within threshold"],
                    "p5_mutation_confidence": 0,
                    "p5_immunization_status": "FAILED",
                    "sw4_completion_contract": {
                        "given": f"Session {orphan['session_id']} perceived but never yielded",
                        "when": f"Orphan reaper detected session aged {orphan['age_hours']:.1f}h",
                        "then": "Session auto-closed with failure yield to improve yield ratio",
                    },
                },
            }
            c_hash = hashlib.sha256(
                json.dumps(event, sort_keys=True).encode()
            ).hexdigest()

            conn.execute(
                "INSERT OR IGNORE INTO stigmergy_events "
                "(event_type, timestamp, subject, source, data_json, content_hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (event["type"], ts, event["subject"], event["source"],
                 json.dumps(event), c_hash),
            )
            reaped += 1

        conn.commit()

        # Get new yield ratio
        yields_after = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events "
            "WHERE event_type LIKE '%prey8.yield%'"
        ).fetchone()[0]
        ratio_after = yields_after / max(perceives, 1) * 100

        return {
            "reaped": reaped,
            "total_orphans": len(orphans),
            "yield_ratio_before": round(ratio_before, 1),
            "yield_ratio_after": round(ratio_after, 1),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HFO Session Recovery — Orphan Reaper")
    parser.add_argument("--db", default=str(
        Path(__file__).resolve().parent.parent.parent
        / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
    ), help="Path to SSOT database")
    parser.add_argument("--reap", action="store_true", help="Auto-close orphaned sessions")
    parser.add_argument("--max-age", type=int, default=24, help="Max orphan age in hours (default: 24)")
    args = parser.parse_args()

    db_path = args.db
    print("Scanning for orphaned sessions...")
    orphans = scan_orphans(db_path, args.max_age)
    print(f"Found {len(orphans)} orphans older than {args.max_age}h")
    for o in orphans[:10]:
        print(f"  [{o['session_id']}] {o['age_hours']:.1f}h — {o['probe'][:60]}")

    if orphans and args.reap:
        print(f"\nReaping...")
        result = reap_orphans(db_path, args.max_age)
        print(f"Reaped: {result['reaped']}")
        print(f"Yield ratio: {result['yield_ratio_before']:.1f}% → {result['yield_ratio_after']:.1f}%")
    elif not orphans:
        print("No orphans to reap.")
