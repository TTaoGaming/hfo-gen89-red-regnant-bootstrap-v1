#!/usr/bin/env python3
"""
hfo_progressive_summarizer.py — HFO Gen90 Progressive SSOT Summarizer
======================================================================

Headless daemon that reads SSOT documents in batches, generates enriched
summaries (BLUFs, tags, key entities) via Gemini thinking mode, and writes
the enrichment back to SSOT. Runs unattended. No operator required.

Architecture:
  SSOT docs (bronze, no bluf) → batch of N docs → Gemini 2.5 Flash/Pro
  (thinking mode) → structured enrichment JSON → write back to SSOT

Modes:
  --scan         Show how many docs need enrichment (dry run)
  --run          Process one batch (default: 20 docs)
  --daemon       Continuous loop until all docs enriched or budget exhausted
  --status       Show enrichment progress stats
  --verify       Verify last batch of enrichments

Billing:
  AI Studio free: 500 RPD × 2.5 Flash = ~500 docs/day (free)
  Vertex AI paid: $100/mo credits = ~80M Pro tokens = full SSOT in hours

Usage:
  python hfo_progressive_summarizer.py --scan
  python hfo_progressive_summarizer.py --run --batch-size 20
  python hfo_progressive_summarizer.py --daemon --model flash_25
  python hfo_progressive_summarizer.py --daemon --model pro  # needs Vertex or billing

Medallion: bronze
Port: P6 ASSIMILATE (learning / memory enrichment)
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Path resolution ────────────────────────────────────────────
def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

# ── Add resources dir for imports ──────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hfo_gemini_models import (
    create_gemini_client,
    get_effective_limits,
    get_model,
    VERTEX_AI_ENABLED,
)

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / os.getenv(
    "HFO_SSOT_DB",
    "hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"
)

# ── Constants ──────────────────────────────────────────────────
ENRICHMENT_TABLE = "document_enrichments"
MAX_DOC_CHARS = 40000       # Truncate very large docs to fit context
THINKING_BUDGET = 4096      # Thinking tokens per doc (balance speed/quality)
BATCH_SLEEP_S = 6.5         # Sleep between requests (free tier: 10 RPM)
VERTEX_BATCH_SLEEP_S = 0.2  # Vertex AI: 1000+ RPM

SYSTEM_PROMPT = """You are an expert knowledge librarian enriching a structured knowledge base.
For each document, produce a JSON object with these EXACT fields:

{
  "bluf": "1-3 sentence summary starting with the most important finding. Max 300 chars.",
  "tags": ["tag1", "tag2", "tag3"],
  "key_entities": ["entity1", "entity2"],
  "quality_score": 0.0 to 1.0,
  "doc_type_suggestion": "explanation|reference|how_to|tutorial|recipe_card|report|artifact|config",
  "meadows_level": 1 to 12,
  "port_suggestion": "P0|P1|P2|P3|P4|P5|P6|P7|null"
}

Rules:
- BLUF = Bottom Line Up Front. Most important insight FIRST.
- Tags: 3-8 lowercase, hyphenated, specific (not generic like "documentation")
- Quality: 0.0 = junk/duplicate, 0.5 = useful, 0.8 = high value, 1.0 = gold
- Be honest about quality. Low-quality docs get low scores.
- Respond ONLY with the JSON object. No markdown fencing. No explanation."""


def get_db(readonly: bool = True) -> sqlite3.Connection:
    """Get SSOT database connection."""
    if readonly:
        conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(str(SSOT_DB))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_enrichment_table():
    """Create the enrichment table if it doesn't exist."""
    conn = sqlite3.connect(str(SSOT_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_enrichments (
            doc_id INTEGER PRIMARY KEY,
            bluf_enriched TEXT,
            tags_enriched TEXT,
            key_entities TEXT,
            quality_score REAL,
            doc_type_suggestion TEXT,
            meadows_level INTEGER,
            port_suggestion TEXT,
            model_used TEXT,
            enrichment_mode TEXT,
            enriched_at TEXT,
            content_hash TEXT,
            raw_response TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_unenriched_docs(limit: int = 20) -> list[dict]:
    """Get documents that haven't been enriched yet."""
    conn = get_db()
    cursor = conn.execute("""
        SELECT d.id, d.title, d.bluf, d.source, d.port, d.doc_type,
               d.word_count, substr(d.content, 1, ?) as content_preview
        FROM documents d
        LEFT JOIN document_enrichments e ON d.id = e.doc_id
        WHERE e.doc_id IS NULL
        ORDER BY d.word_count DESC
        LIMIT ?
    """, (MAX_DOC_CHARS, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_enrichment_stats() -> dict:
    """Get enrichment progress statistics."""
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    # Check if enrichment table exists
    table_exists = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (ENRICHMENT_TABLE,)
    ).fetchone()[0]

    if not table_exists:
        conn.close()
        return {
            "total_docs": total,
            "enriched": 0,
            "remaining": total,
            "percent": 0.0,
            "by_model": {},
            "avg_quality": 0.0,
        }

    enriched = conn.execute(
        f"SELECT COUNT(*) FROM {ENRICHMENT_TABLE}"
    ).fetchone()[0]

    by_model = {}
    for row in conn.execute(
        f"SELECT model_used, COUNT(*) as cnt FROM {ENRICHMENT_TABLE} GROUP BY model_used"
    ):
        by_model[row[0]] = row[1]

    avg_q = conn.execute(
        f"SELECT AVG(quality_score) FROM {ENRICHMENT_TABLE} WHERE quality_score IS NOT NULL"
    ).fetchone()[0] or 0.0

    conn.close()
    return {
        "total_docs": total,
        "enriched": enriched,
        "remaining": total - enriched,
        "percent": round(enriched / total * 100, 1) if total > 0 else 0.0,
        "by_model": by_model,
        "avg_quality": round(avg_q, 3),
    }


def enrich_document(client, model_id: str, doc: dict) -> Optional[dict]:
    """
    Call Gemini to enrich a single document.

    Returns parsed JSON enrichment or None on failure.
    """
    from google.genai import types

    # Build the prompt
    title = doc.get("title", "Untitled")
    content = doc.get("content_preview", "")[:MAX_DOC_CHARS]
    source = doc.get("source", "unknown")
    existing_bluf = doc.get("bluf", "")
    word_count = doc.get("word_count", 0)

    prompt = f"""Document ID: {doc['id']}
Title: {title}
Source: {source}
Existing BLUF: {existing_bluf or '(none)'}
Word count: {word_count}

--- CONTENT ---
{content}
--- END ---

Produce the enrichment JSON."""

    # Determine if model supports thinking
    spec = get_model(model_id)
    config_kwargs = {
        "temperature": 0.3,
        "system_instruction": SYSTEM_PROMPT,
    }

    if spec and spec.supports_thinking:
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_budget=THINKING_BUDGET
        )

    config = types.GenerateContentConfig(**config_kwargs)

    try:
        response = client.models.generate_content(
            model=spec.model_id if spec else model_id,
            contents=prompt,
            config=config,
        )

        text = response.text.strip()
        # Strip markdown fencing if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
        if text.startswith("json"):
            text = text[4:].strip()

        result = json.loads(text)
        result["_raw"] = response.text
        result["_prompt_tokens"] = getattr(
            response.usage_metadata, "prompt_token_count", 0
        )
        result["_completion_tokens"] = getattr(
            response.usage_metadata, "candidates_token_count", 0
        )
        result["_thinking_tokens"] = getattr(
            response.usage_metadata, "thoughts_token_count", 0
        )
        return result

    except json.JSONDecodeError as e:
        print(f"  [WARN] Doc {doc['id']}: JSON parse failed: {e}")
        return None
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            print(f"  [RATE] Doc {doc['id']}: Rate limited. Backing off.")
            return {"_rate_limited": True}
        print(f"  [ERR] Doc {doc['id']}: {e}")
        return None


def write_enrichment(doc_id: int, enrichment: dict, model_id: str, mode: str):
    """Write enrichment result to SSOT."""
    conn = sqlite3.connect(str(SSOT_DB))
    now = datetime.now(timezone.utc).isoformat()
    content_hash = hashlib.sha256(
        json.dumps(enrichment, sort_keys=True).encode()
    ).hexdigest()

    conn.execute(f"""
        INSERT OR REPLACE INTO {ENRICHMENT_TABLE}
        (doc_id, bluf_enriched, tags_enriched, key_entities, quality_score,
         doc_type_suggestion, meadows_level, port_suggestion,
         model_used, enrichment_mode, enriched_at, content_hash, raw_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id,
        enrichment.get("bluf", ""),
        json.dumps(enrichment.get("tags", [])),
        json.dumps(enrichment.get("key_entities", [])),
        enrichment.get("quality_score"),
        enrichment.get("doc_type_suggestion"),
        enrichment.get("meadows_level"),
        enrichment.get("port_suggestion"),
        model_id,
        mode,
        now,
        content_hash,
        enrichment.get("_raw", ""),
    ))
    conn.commit()
    conn.close()


def write_stigmergy_event(event_type: str, subject: str, data: dict):
    """Write a stigmergy event to SSOT."""
    conn = sqlite3.connect(str(SSOT_DB))
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps({
        "specversion": "1.0",
        "type": event_type,
        "source": "hfo_progressive_summarizer_gen90_v1",
        "subject": subject,
        "time": now,
        "data": data,
    }, default=str)
    content_hash = hashlib.sha256(payload.encode()).hexdigest()

    try:
        conn.execute(
            "INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_type, now, "hfo_progressive_summarizer_gen90_v1", subject, payload, content_hash)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Duplicate content_hash — skip
    conn.close()


def run_batch(model_tier: str = "flash_25", batch_size: int = 20,
              dry_run: bool = False) -> dict:
    """
    Process one batch of unenriched documents.

    Returns dict with batch stats.
    """
    ensure_enrichment_table()

    docs = get_unenriched_docs(batch_size)
    if not docs:
        print("All documents enriched! Nothing to do.")
        return {"processed": 0, "remaining": 0, "status": "complete"}

    mode = "vertex" if VERTEX_AI_ENABLED else "aistudio"
    sleep_s = VERTEX_BATCH_SLEEP_S if VERTEX_AI_ENABLED else BATCH_SLEEP_S
    spec = get_model(model_tier)
    model_id = spec.model_id if spec else model_tier

    print(f"Batch: {len(docs)} docs | Model: {model_id} | Mode: {mode}")
    print(f"Sleep: {sleep_s}s between requests")

    if dry_run:
        print("\n[DRY RUN] Would process:")
        for doc in docs:
            print(f"  Doc {doc['id']}: {doc['title'][:60]} ({doc['word_count']}w)")
        return {"processed": 0, "would_process": len(docs), "status": "dry_run"}

    client, actual_mode = create_gemini_client()
    print(f"Client mode: {actual_mode}")

    success = 0
    failed = 0
    rate_limited = 0
    total_tokens = 0

    for i, doc in enumerate(docs):
        print(f"  [{i+1}/{len(docs)}] Doc {doc['id']}: {doc['title'][:50]}...", end=" ")

        result = enrich_document(client, model_tier, doc)

        if result is None:
            print("FAILED")
            failed += 1
        elif result.get("_rate_limited"):
            print("RATE LIMITED — stopping batch")
            rate_limited += 1
            # Back off and stop this batch
            break
        else:
            write_enrichment(doc['id'], result, model_id, actual_mode)
            q = result.get("quality_score", "?")
            tokens = result.get("_completion_tokens", 0) + result.get("_thinking_tokens", 0)
            total_tokens += tokens
            print(f"OK (q={q}, {tokens}tok)")
            success += 1

        if i < len(docs) - 1:
            time.sleep(sleep_s)

    stats = get_enrichment_stats()

    batch_result = {
        "processed": success,
        "failed": failed,
        "rate_limited": rate_limited,
        "total_tokens": total_tokens,
        "model": model_id,
        "mode": actual_mode,
        "remaining": stats["remaining"],
        "percent_complete": stats["percent"],
        "status": "rate_limited" if rate_limited else "complete",
    }

    # Write stigmergy event
    write_stigmergy_event(
        "hfo.gen90.p6.enrichment.batch",
        f"BATCH:{success}/{len(docs)}:{model_id}",
        batch_result,
    )

    print(f"\nBatch complete: {success} OK, {failed} failed, {rate_limited} rate-limited")
    print(f"Progress: {stats['enriched']}/{stats['total_docs']} ({stats['percent']}%)")

    return batch_result


def run_daemon(model_tier: str = "flash_25", batch_size: int = 20,
               max_batches: int = 0, pause_between_batches_s: int = 60):
    """
    Continuous enrichment daemon. Runs batches until all docs processed
    or budget/rate limits exhausted.

    Args:
        model_tier: Which model tier to use
        batch_size: Docs per batch
        max_batches: 0 = unlimited
        pause_between_batches_s: Sleep between batches
    """
    print("=" * 60)
    print("  HFO Progressive Summarizer — Daemon Mode")
    print("=" * 60)
    print(f"  Model: {model_tier}")
    print(f"  Batch size: {batch_size}")
    print(f"  Max batches: {'unlimited' if max_batches == 0 else max_batches}")
    print(f"  Vertex AI: {'YES ($credits)' if VERTEX_AI_ENABLED else 'NO (free tier)'}")
    print()

    batch_num = 0
    total_processed = 0
    consecutive_rate_limits = 0

    while True:
        batch_num += 1
        if max_batches > 0 and batch_num > max_batches:
            print(f"\nMax batches ({max_batches}) reached. Stopping.")
            break

        print(f"\n--- Batch {batch_num} ---")
        result = run_batch(model_tier, batch_size)

        total_processed += result["processed"]

        if result["status"] == "complete" and result["processed"] == 0:
            print("\nAll documents enriched! Daemon complete.")
            break

        if result["status"] == "rate_limited":
            consecutive_rate_limits += 1
            if consecutive_rate_limits >= 3:
                print("\n3 consecutive rate limits. Stopping daemon.")
                print("Re-run tomorrow or enable Vertex AI for higher limits.")
                break
            backoff = pause_between_batches_s * (2 ** consecutive_rate_limits)
            print(f"Rate limited. Backing off {backoff}s...")
            time.sleep(backoff)
        else:
            consecutive_rate_limits = 0
            if result["remaining"] > 0:
                print(f"Pausing {pause_between_batches_s}s before next batch...")
                time.sleep(pause_between_batches_s)

    # Final summary
    stats = get_enrichment_stats()
    print(f"\n{'=' * 60}")
    print(f"  Daemon Summary")
    print(f"  Batches run: {batch_num}")
    print(f"  Total enriched this run: {total_processed}")
    print(f"  Overall progress: {stats['enriched']}/{stats['total_docs']} ({stats['percent']}%)")
    print(f"  Avg quality: {stats['avg_quality']}")
    print(f"{'=' * 60}")

    # Write summary event
    write_stigmergy_event(
        "hfo.gen90.p6.enrichment.daemon_complete",
        f"DAEMON:{total_processed}docs:{batch_num}batches",
        {
            "batches": batch_num,
            "total_enriched": total_processed,
            **stats,
        },
    )


def verify_last_batch(n: int = 5):
    """Show the last N enrichments for quality check."""
    ensure_enrichment_table()
    conn = get_db()
    cursor = conn.execute(f"""
        SELECT e.doc_id, d.title, e.bluf_enriched, e.tags_enriched,
               e.quality_score, e.model_used, e.enriched_at
        FROM {ENRICHMENT_TABLE} e
        JOIN documents d ON d.id = e.doc_id
        ORDER BY e.enriched_at DESC
        LIMIT ?
    """, (n,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No enrichments found yet.")
        return

    for r in rows:
        print(f"\nDoc {r[0]}: {r[1][:60]}")
        print(f"  BLUF: {r[2][:100]}")
        print(f"  Tags: {r[3]}")
        print(f"  Quality: {r[4]}")
        print(f"  Model: {r[5]} @ {r[6]}")


def main():
    parser = argparse.ArgumentParser(
        description="HFO Progressive SSOT Summarizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scan                          # See what needs enrichment
  %(prog)s --status                        # See progress stats
  %(prog)s --run --batch-size 10           # Process 10 docs (free tier)
  %(prog)s --run --model pro               # Use Pro (needs billing/Vertex)
  %(prog)s --daemon                        # Continuous until done
  %(prog)s --daemon --model pro --max 25   # 25 batches with Pro
  %(prog)s --verify                        # Check last enrichments
""")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true", help="Show unenriched doc count")
    group.add_argument("--status", action="store_true", help="Show enrichment stats")
    group.add_argument("--run", action="store_true", help="Process one batch")
    group.add_argument("--daemon", action="store_true", help="Continuous mode")
    group.add_argument("--verify", action="store_true", help="Verify last enrichments")

    parser.add_argument("--model", default="flash_25",
                       help="Model tier: nano, flash, flash_25, pro (default: flash_25)")
    parser.add_argument("--batch-size", type=int, default=20,
                       help="Docs per batch (default: 20)")
    parser.add_argument("--max", type=int, default=0,
                       help="Max batches in daemon mode (0=unlimited)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be processed")
    parser.add_argument("--pause", type=int, default=60,
                       help="Seconds between batches in daemon mode (default: 60)")
    parser.add_argument("--verify-count", type=int, default=5,
                       help="Number of enrichments to verify (default: 5)")
    parser.add_argument("--json", action="store_true",
                       help="JSON output")

    args = parser.parse_args()

    if args.scan:
        ensure_enrichment_table()
        docs = get_unenriched_docs(limit=99999)
        stats = get_enrichment_stats()
        if args.json:
            print(json.dumps(stats))
        else:
            print(f"Total documents: {stats['total_docs']}")
            print(f"Already enriched: {stats['enriched']}")
            print(f"Remaining: {stats['remaining']}")
            print(f"Progress: {stats['percent']}%")
            if stats['remaining'] > 0:
                # Estimate time
                rpm = 10 if not VERTEX_AI_ENABLED else 1000
                batches = stats['remaining'] // 20 + 1
                if VERTEX_AI_ENABLED:
                    est_min = stats['remaining'] / rpm
                    print(f"\nWith Vertex AI: ~{est_min:.0f} min ({stats['remaining']} docs @ ~{rpm} RPM)")
                else:
                    est_min = stats['remaining'] * 6.5 / 60
                    print(f"\nWith free tier (Flash 2.5): ~{est_min:.0f} min")
                    print(f"  = ~{est_min/60:.1f} hours")
                    print(f"  Budget: 500 RPD = ~500 docs/day")
                    est_days = stats['remaining'] / 500
                    print(f"  Estimated days: ~{est_days:.1f}")

    elif args.status:
        stats = get_enrichment_stats()
        if args.json:
            print(json.dumps(stats))
        else:
            print(f"Enrichment Progress:")
            print(f"  Total: {stats['total_docs']}")
            print(f"  Done:  {stats['enriched']}")
            print(f"  Left:  {stats['remaining']}")
            print(f"  {stats['percent']}% complete")
            print(f"  Avg quality: {stats['avg_quality']}")
            if stats['by_model']:
                print(f"  By model:")
                for m, c in stats['by_model'].items():
                    print(f"    {m}: {c}")

    elif args.run:
        run_batch(args.model, args.batch_size, dry_run=args.dry_run)

    elif args.daemon:
        run_daemon(args.model, args.batch_size, args.max, args.pause)

    elif args.verify:
        verify_last_batch(args.verify_count)


if __name__ == "__main__":
    main()
