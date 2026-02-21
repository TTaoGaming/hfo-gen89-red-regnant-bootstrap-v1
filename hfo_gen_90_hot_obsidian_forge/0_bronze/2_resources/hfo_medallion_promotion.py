"""
HFO Medallion Promotion — Bronze to Silver Gate.

Port: P5 IMMUNIZE (Pyre Praetorian) — detect, quarantine, gate, harden, teach.
Medallion: bronze (new implementation).

Implements the medallion boundary crossing gate from SW-5.
Documents cannot self-promote. Promotion requires explicit validation criteria.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def check_promotion_criteria(db_path: str, doc_id: int, validation: dict = None) -> dict:
    """Check if a document meets silver promotion criteria.

    Required validation fields:
        - reviewed_by: Who reviewed (non-empty string)
        - review_date: When reviewed (ISO date string)
        - validation_type: How validated (human_review, automated, cross_reference)
        - claims_verified: Boolean — factual claims checked
        - cross_referenced: Boolean — checked against other docs

    Returns:
        dict with: eligible (bool), reason (str), doc_title (str)
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT id, title, medallion FROM documents WHERE id = ?",
            (doc_id,)
        )
        row = cur.fetchone()
        if not row:
            return {"eligible": False, "reason": f"Document {doc_id} not found"}

        doc_id, title, current_medallion = row

        # Must be bronze to promote to silver
        if current_medallion != "bronze":
            return {
                "eligible": False,
                "reason": f"Document is already '{current_medallion}', not bronze",
                "doc_title": title,
            }

        # Validation metadata is required
        if not validation:
            return {
                "eligible": False,
                "reason": "missing validation metadata",
                "doc_title": title,
            }

        required_fields = [
            "reviewed_by", "review_date", "validation_type",
            "claims_verified", "cross_referenced",
        ]
        missing = [f for f in required_fields if not validation.get(f)]
        if missing:
            return {
                "eligible": False,
                "reason": f"missing validation: {', '.join(missing)}",
                "doc_title": title,
            }

        return {
            "eligible": True,
            "reason": "all criteria met",
            "doc_title": title,
        }
    finally:
        conn.close()


def promote_to_silver(db_path: str, doc_id: int, validation: dict = None) -> dict:
    """Promote a bronze document to silver with validation gate.

    This is the fail-closed medallion boundary crossing from SW-5.
    Missing or invalid validation = REJECTED.

    Args:
        db_path: Path to SSOT SQLite database
        doc_id: Document ID to promote
        validation: Dict with validation criteria (see check_promotion_criteria)

    Returns:
        dict with: status (promoted/rejected/error), reason, doc_title
    """
    # Check criteria first
    check = check_promotion_criteria(db_path, doc_id, validation)
    if not check.get("eligible"):
        return {
            "status": "rejected",
            "reason": check.get("reason", "unknown"),
            "doc_title": check.get("doc_title", ""),
        }

    conn = sqlite3.connect(db_path)
    try:
        # Update medallion
        conn.execute(
            "UPDATE documents SET medallion = 'silver' WHERE id = ?",
            (doc_id,)
        )

        # Update metadata_json with validation record
        cur = conn.execute(
            "SELECT metadata_json FROM documents WHERE id = ?",
            (doc_id,)
        )
        row = cur.fetchone()
        metadata = {}
        if row and row[0]:
            try:
                metadata = json.loads(row[0])
            except json.JSONDecodeError:
                metadata = {}

        metadata["medallion_promotion"] = {
            "from": "bronze",
            "to": "silver",
            "validation": validation,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.execute(
            "UPDATE documents SET metadata_json = ? WHERE id = ?",
            (json.dumps(metadata), doc_id)
        )

        # Log stigmergy event
        ts = datetime.now(timezone.utc).isoformat()
        event = {
            "specversion": "1.0",
            "id": hashlib.sha256(
                f"promotion:{doc_id}:{ts}".encode()
            ).hexdigest()[:32],
            "type": "hfo.gen90.medallion.promotion",
            "source": "hfo_medallion_promotion",
            "subject": f"doc-{doc_id}-bronze-to-silver",
            "time": ts,
            "timestamp": ts,
            "datacontenttype": "application/json",
            "data": {
                "doc_id": doc_id,
                "doc_title": check.get("doc_title", ""),
                "from_medallion": "bronze",
                "to_medallion": "silver",
                "validation": validation,
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

        conn.commit()

        return {
            "status": "promoted",
            "reason": "all criteria met",
            "doc_title": check.get("doc_title", ""),
            "doc_id": doc_id,
        }
    except Exception as e:
        conn.rollback()
        return {
            "status": "error",
            "reason": str(e),
            "doc_title": check.get("doc_title", ""),
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parent.parent.parent
        / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
    )

    conn = sqlite3.connect(db_path)
    bronze = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE medallion = 'bronze'"
    ).fetchone()[0]
    silver = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE medallion = 'silver'"
    ).fetchone()[0]
    conn.close()

    print(f"Bronze: {bronze}, Silver: {silver}")
    print(f"Promotion rate: {silver}/{bronze+silver} = {silver/max(bronze+silver,1)*100:.1f}%")
