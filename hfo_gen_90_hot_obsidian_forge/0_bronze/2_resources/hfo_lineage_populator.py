"""
HFO Lineage Populator — Automatic Dependency Graph from PREY8 Memory Refs.

Port: P6 ASSIMILATE (Kraken Keeper) — learning and memory.
Medallion: bronze (new implementation).

Scans stigmergy_events for perceive events that contain memory_refs,
then populates the lineage table with dependency relationships.

Lineage schema: id, doc_id, depends_on_hash, relation
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def populate_lineage_from_refs(
    db_path: str,
    memory_refs: list[int],
    relation: str = "prey8_memory_ref",
    session_id: str = "",
) -> dict:
    """Create lineage entries linking documents referenced in a perceive event.

    For each pair of docs in memory_refs, creates a bidirectional dependency.
    Uses content hashing to prevent duplicates.

    Args:
        db_path: Path to SSOT SQLite database
        memory_refs: List of document IDs referenced together
        relation: Relationship type label
        session_id: Optional PREY8 session ID for traceability

    Returns:
        dict with: created, skipped, duplicates_skipped, lineage_type
    """
    if not memory_refs or len(memory_refs) < 2:
        return {"created": 0, "skipped": 0, "duplicates_skipped": 0,
                "lineage_type": relation}

    conn = sqlite3.connect(db_path)
    created = 0
    duplicates_skipped = 0

    try:
        # Create pairwise relationships
        for i, doc_id in enumerate(memory_refs):
            for j, other_id in enumerate(memory_refs):
                if i >= j:
                    continue
                # Create a deterministic hash for dedup
                dep_hash = hashlib.sha256(
                    f"{doc_id}:{other_id}:{relation}".encode()
                ).hexdigest()

                # Check if already exists
                cur = conn.execute(
                    "SELECT COUNT(*) FROM lineage "
                    "WHERE doc_id = ? AND depends_on_hash = ?",
                    (doc_id, dep_hash)
                )
                if cur.fetchone()[0] > 0:
                    duplicates_skipped += 1
                    continue

                # Insert lineage entry
                conn.execute(
                    "INSERT INTO lineage (doc_id, depends_on_hash, relation) "
                    "VALUES (?, ?, ?)",
                    (doc_id, dep_hash, relation)
                )
                created += 1

                # Also insert reverse direction
                rev_hash = hashlib.sha256(
                    f"{other_id}:{doc_id}:{relation}".encode()
                ).hexdigest()
                cur = conn.execute(
                    "SELECT COUNT(*) FROM lineage "
                    "WHERE doc_id = ? AND depends_on_hash = ?",
                    (other_id, rev_hash)
                )
                if cur.fetchone()[0] == 0:
                    conn.execute(
                        "INSERT INTO lineage (doc_id, depends_on_hash, relation) "
                        "VALUES (?, ?, ?)",
                        (other_id, rev_hash, relation)
                    )
                    created += 1
                else:
                    duplicates_skipped += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "created": created,
        "duplicates_skipped": duplicates_skipped,
        "lineage_type": relation,
    }


def populate_lineage_from_stigmergy(db_path: str, limit: int = 100) -> dict:
    """Scan perceive events and auto-populate lineage from memory_refs.

    Reads PREY8 perceive events that contain memory_refs in their data,
    extracts the doc IDs, and creates lineage entries.

    Returns:
        dict with: events_processed, entries_created, errors
    """
    conn = sqlite3.connect(db_path)
    events_processed = 0
    total_created = 0
    errors = []

    try:
        cur = conn.execute(
            "SELECT id, data_json FROM stigmergy_events "
            "WHERE event_type LIKE '%perceive%' "
            "AND (data_json LIKE '%memory_refs%' OR data_json LIKE '%p6_memory_refs%') "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )

        for row in cur.fetchall():
            event_id = row[0]
            try:
                event = json.loads(row[1])
                data = event.get("data", {})
                # Try both field names
                refs_str = data.get("p6_memory_refs", "") or data.get("memory_refs", "")
                if not refs_str:
                    continue

                # Parse doc IDs — could be string or list
                refs = []
                if isinstance(refs_str, list):
                    for part in refs_str:
                        try:
                            refs.append(int(str(part).strip()))
                        except ValueError:
                            continue
                else:
                    for part in str(refs_str).split(","):
                        part = part.strip()
                        try:
                            refs.append(int(part))
                        except ValueError:
                            continue

                if len(refs) >= 2:
                    result = populate_lineage_from_refs(
                        db_path, refs,
                        session_id=data.get("session_id", "")
                    )
                    total_created += result["created"]
                    events_processed += 1
            except (json.JSONDecodeError, KeyError) as e:
                errors.append(f"Event {event_id}: {e}")

    finally:
        conn.close()

    return {
        "events_processed": events_processed,
        "entries_created": total_created,
        "errors": errors,
    }


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parent.parent.parent
        / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
    )
    print(f"Populating lineage from stigmergy perceive events...")
    result = populate_lineage_from_stigmergy(db_path)
    print(f"Events processed: {result['events_processed']}")
    print(f"Entries created:  {result['entries_created']}")
    if result['errors']:
        print(f"Errors: {len(result['errors'])}")
        for e in result['errors'][:5]:
            print(f"  - {e}")
