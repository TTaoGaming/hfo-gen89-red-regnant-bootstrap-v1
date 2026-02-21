#!/usr/bin/env python3
"""
hfo_p6_kraken_workers.py — P6 Kraken Keeper Swarm Workers
===========================================================
v1.0 | Gen89 | Port: P6 ASSIMILATE | Layer: Workers

Extended knowledge enrichment workers beyond the core T1-T4:
    T5 — Progressive Summarization (multi-pass distillation)
    T6 — Knowledge Graph Extraction (entity/relation triples)
    T7 — Tag Expansion (enrich tags from content analysis)
    T8 — Quality Audit (validate existing enrichments)

Each worker is an async function that reads from SSOT, calls Ollama,
and writes additive enrichments back. All workers respect the
SwarmOrchestrator's pause/resume signals.

SAFETY:
    - ADDITIVE ONLY: Never deletes, never overwrites existing valid data
    - All writes logged as CloudEvents to stigmergy_events
    - Workers check orchestrator.wait_if_paused() before each batch
    - CPU-only workers (lineage, quality_audit) run without GPU

Medallion: bronze
Port: P6 ASSIMILATE
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from hfo_ssot_write import get_db_readwrite

if TYPE_CHECKING:
    from hfo_resource_monitor import SwarmOrchestrator

# ── Reuse the Kraken daemon's infrastructure ──
# These will be imported from the daemon or passed as deps
OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")


def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = _find_root()
SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
GEN = os.environ.get("HFO_GENERATION", "89")
P6_SOURCE = f"hfo_p6_kraken_swarm_gen{GEN}"



def get_db_readonly() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def write_stigmergy_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
    source: str = P6_SOURCE,
) -> str:
    event_id = hashlib.md5(
        f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()
    ).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    event = {
        "specversion": "1.0",
        "id": event_id,
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(event), content_hash),
    )
    conn.commit()
    return event_id


def _strip_think_tags(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


def _ollama_generate(
    prompt: str,
    system: str = "",
    model: str = "gemma3:4b",
    timeout: float = 180,
    temperature: float = 0.3,
    num_predict: int = 512,
) -> str:
    import httpx
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": temperature},
    }
    if system:
        payload["system"] = system
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json().get("response", "").strip()
    except Exception as e:
        print(f"  [OLLAMA ERROR] {e}", file=sys.stderr)
        return ""


SYSTEM_PROMPT = """You are the Kraken Keeper, commander of Port 6 (ASSIMILATE) in the HFO Octree.
You devour knowledge from documents and extract their essence.
Be concise and precise. No filler. No markdown formatting.
Answer ONLY what is asked. No preamble."""


# ═══════════════════════════════════════════════════════════════
# T5: PROGRESSIVE SUMMARIZATION
# ═══════════════════════════════════════════════════════════════

async def progressive_summarization(
    model: str = "qwen3:8b",
    batch_size: int = 1,
    dry_run: bool = False,
    orchestrator: Optional[SwarmOrchestrator] = None,
) -> dict:
    """
    Multi-pass progressive summarization (Tiago Forte method adapted for SSOT).

    Pass 1: Documents with no BLUF get a BLUF (already done by T1)
    Pass 2: Documents with BLUF but no metadata_json.summary get a 3-sentence summary
    Pass 3: Documents with summary get key_insights extracted
    Pass 4: Documents with insights get cross-domain connections mapped

    This worker handles Pass 2-4 (Pass 1 is the existing BLUF generator).
    Results are stored in metadata_json as additive enrichments.
    """
    results = {"enriched": 0, "pass_2": 0, "pass_3": 0, "pass_4": 0, "errors": 0}

    if orchestrator:
        await orchestrator.wait_if_paused()

    try:
        conn = get_db_readwrite()
    except Exception as e:
        results["errors"] = 1
        return results

    try:
        # Find docs with BLUF but needing deeper summarization
        # Check metadata_json for existing progressive summary fields
        cursor = conn.execute(
            """SELECT id, title, bluf, SUBSTR(content, 1, 4000) as content_preview,
                      metadata_json, source, port, word_count
               FROM documents
               WHERE bluf IS NOT NULL AND bluf != '' AND bluf != '---'
               AND word_count > 200
               ORDER BY word_count DESC
               LIMIT ?""",
            (batch_size * 3,),  # Fetch more, filter by pass
        )
        rows = cursor.fetchall()

        for row in rows:
            if not (orchestrator is None or orchestrator._running):
                break
            if orchestrator:
                await orchestrator.wait_if_paused()

            doc_id = row["id"]
            title = row["title"] or "(untitled)"
            bluf = row["bluf"] or ""
            content = row["content_preview"] or ""
            source = row["source"] or ""
            port = row["port"] or ""
            word_count = row["word_count"] or 0

            # Parse existing metadata
            try:
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}

            enrichment = meta.get("p6_enrichment", {})

            # Determine which pass this doc needs
            if "summary_3sent" not in enrichment:
                # PASS 2: Generate 3-sentence summary
                prompt = (
                    f"Write exactly 3 sentences summarizing this document's key value.\n"
                    f"Sentence 1: What is this about?\n"
                    f"Sentence 2: What is the key insight or contribution?\n"
                    f"Sentence 3: Who should read this and why?\n\n"
                    f"Title: {title}\nBLUF: {bluf}\nSource: {source}\nPort: {port}\n"
                    f"Content (truncated):\n{content[:3000]}\n\n"
                    f"Three sentences:"
                )
                raw = await asyncio.get_event_loop().run_in_executor(
                    None, lambda p=prompt: _ollama_generate(
                        p, system=SYSTEM_PROMPT, model=model, num_predict=256,
                    ),
                )
                summary = _strip_think_tags(raw)
                if summary and len(summary) > 30:
                    enrichment["summary_3sent"] = summary[:500]
                    enrichment["summary_model"] = model
                    enrichment["summary_ts"] = datetime.now(timezone.utc).isoformat()
                    results["pass_2"] += 1
                    results["enriched"] += 1
                    print(f"  [PROG-SUM P2] doc {doc_id}: {title[:50]}...")
                else:
                    results["errors"] += 1
                    continue

            elif "key_insights" not in enrichment and results["enriched"] < batch_size:
                # PASS 3: Extract key insights
                summary_3 = enrichment.get("summary_3sent", bluf)
                prompt = (
                    f"Extract 3-5 key insights from this document as a numbered list.\n"
                    f"Each insight should be one sentence capturing a non-obvious takeaway.\n\n"
                    f"Title: {title}\nSummary: {summary_3}\n"
                    f"Content (truncated):\n{content[:2500]}\n\n"
                    f"Key insights (numbered list):"
                )
                raw = await asyncio.get_event_loop().run_in_executor(
                    None, lambda p=prompt: _ollama_generate(
                        p, system=SYSTEM_PROMPT, model=model, num_predict=384,
                    ),
                )
                insights = _strip_think_tags(raw)
                if insights and len(insights) > 30:
                    # Parse numbered list
                    insight_list = [
                        line.strip().lstrip("0123456789.)-").strip()
                        for line in insights.split("\n")
                        if line.strip() and not line.strip().startswith("#")
                    ]
                    insight_list = [i for i in insight_list if len(i) > 10][:5]

                    if insight_list:
                        enrichment["key_insights"] = insight_list
                        enrichment["insights_model"] = model
                        enrichment["insights_ts"] = datetime.now(timezone.utc).isoformat()
                        results["pass_3"] += 1
                        results["enriched"] += 1
                        print(f"  [PROG-SUM P3] doc {doc_id}: {len(insight_list)} insights")
                    else:
                        results["errors"] += 1
                        continue
                else:
                    results["errors"] += 1
                    continue

            elif "cross_domain" not in enrichment and results["enriched"] < batch_size:
                # PASS 4: Map cross-domain connections
                insights = enrichment.get("key_insights", [])
                summary_3 = enrichment.get("summary_3sent", bluf)
                prompt = (
                    f"Given this document's insights, identify cross-domain connections.\n"
                    f"Which other fields, disciplines, or HFO ports does this connect to?\n\n"
                    f"Title: {title}\nPort: {port}\nSummary: {summary_3}\n"
                    f"Insights: {'; '.join(insights[:3])}\n\n"
                    f"Map 2-4 cross-domain connections. Format:\n"
                    f"CONNECT: <domain or port> — <how it connects>"
                )
                raw = await asyncio.get_event_loop().run_in_executor(
                    None, lambda p=prompt: _ollama_generate(
                        p, system=SYSTEM_PROMPT, model=model, num_predict=256,
                    ),
                )
                connections = _strip_think_tags(raw)
                if connections and len(connections) > 20:
                    conn_list = []
                    for line in connections.split("\n"):
                        line = line.strip()
                        if line.upper().startswith("CONNECT:"):
                            conn_list.append(line[8:].strip())
                        elif "—" in line or "-" in line:
                            conn_list.append(line.lstrip("0123456789.)-*").strip())
                    conn_list = [c for c in conn_list if len(c) > 10][:4]

                    if conn_list:
                        enrichment["cross_domain"] = conn_list
                        enrichment["cross_domain_model"] = model
                        enrichment["cross_domain_ts"] = datetime.now(timezone.utc).isoformat()
                        results["pass_4"] += 1
                        results["enriched"] += 1
                        print(f"  [PROG-SUM P4] doc {doc_id}: {len(conn_list)} connections")
                    else:
                        results["errors"] += 1
                        continue
                else:
                    results["errors"] += 1
                    continue
            else:
                continue  # Fully enriched

            if results["enriched"] > batch_size:
                break

            # Write back enriched metadata
            if not dry_run:
                meta["p6_enrichment"] = enrichment
                conn.execute(
                    "UPDATE documents SET metadata_json = ? WHERE id = ?",
                    (json.dumps(meta, ensure_ascii=False), doc_id),
                )
                write_stigmergy_event(
                    conn, "hfo.gen89.kraken.progressive_summary",
                    f"PROG_SUM:doc_{doc_id}",
                    {
                        "doc_id": doc_id,
                        "title": title[:100],
                        "passes_completed": [
                            k for k in ("summary_3sent", "key_insights", "cross_domain")
                            if k in enrichment
                        ],
                        "model": model,
                        "task": "T5_PROGRESSIVE_SUMMARIZATION",
                    },
                )

    except Exception as e:
        results["errors"] += 1
        print(f"  [T5 ERROR] {e}", file=sys.stderr)
    finally:
        conn.close()

    return results


# ═══════════════════════════════════════════════════════════════
# T6: KNOWLEDGE GRAPH EXTRACTION
# ═══════════════════════════════════════════════════════════════

async def knowledge_graph_extraction(
    model: str = "gemma3:4b",
    batch_size: int = 2,
    dry_run: bool = False,
    orchestrator: Optional[SwarmOrchestrator] = None,
) -> dict:
    """
    Extract entity-relation triples from documents.
    Stores triples in metadata_json.p6_enrichment.kg_triples.

    Triple format: (subject, predicate, object)
    Example: ("HFO", "uses", "8-port octree architecture")

    These triples form the basis for a future GraphRAG layer.
    """
    results = {"extracted": 0, "triples_total": 0, "errors": 0}

    if orchestrator:
        await orchestrator.wait_if_paused()

    try:
        conn = get_db_readwrite()
    except Exception as e:
        results["errors"] = 1
        return results

    try:
        # Find docs without KG triples yet
        cursor = conn.execute(
            """SELECT id, title, bluf, SUBSTR(content, 1, 3000) as content_preview,
                      metadata_json, source, port
               FROM documents
               WHERE bluf IS NOT NULL AND bluf != '' AND bluf != '---'
               AND word_count > 150
               ORDER BY RANDOM()
               LIMIT ?""",
            (batch_size * 2,),
        )
        rows = cursor.fetchall()

        for row in rows:
            if orchestrator and not orchestrator._running:
                break
            if orchestrator:
                await orchestrator.wait_if_paused()
            if results["extracted"] >= batch_size:
                break

            doc_id = row["id"]
            title = row["title"] or "(untitled)"
            bluf = row["bluf"] or ""
            content = row["content_preview"] or ""

            try:
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}

            enrichment = meta.get("p6_enrichment", {})

            # Skip if already has KG triples
            if "kg_triples" in enrichment:
                continue

            prompt = (
                f"Extract knowledge graph triples from this document.\n"
                f"A triple is: SUBJECT | PREDICATE | OBJECT\n\n"
                f"Rules:\n"
                f"- Extract 3-8 triples capturing the document's key relationships\n"
                f"- Use concise entity names (not full sentences)\n"
                f"- Predicates should be verbs: uses, implements, extends, requires, produces, etc.\n"
                f"- One triple per line in format: SUBJECT | PREDICATE | OBJECT\n\n"
                f"Title: {title}\nBLUF: {bluf}\n"
                f"Content:\n{content[:2000]}\n\n"
                f"Triples:"
            )

            raw = await asyncio.get_event_loop().run_in_executor(
                None, lambda p=prompt: _ollama_generate(
                    p, system=SYSTEM_PROMPT, model=model, num_predict=384,
                ),
            )
            response = _strip_think_tags(raw)

            if not response or len(response) < 10:
                results["errors"] += 1
                continue

            # Parse triples
            triples = []
            for line in response.split("\n"):
                line = line.strip()
                parts = [p.strip() for p in line.split("|")]
                if len(parts) == 3 and all(len(p) > 1 for p in parts):
                    triples.append({
                        "s": parts[0][:100],
                        "p": parts[1][:50],
                        "o": parts[2][:100],
                    })

            if not triples:
                results["errors"] += 1
                continue

            triples = triples[:8]  # Cap at 8

            if not dry_run:
                enrichment["kg_triples"] = triples
                enrichment["kg_model"] = model
                enrichment["kg_ts"] = datetime.now(timezone.utc).isoformat()
                meta["p6_enrichment"] = enrichment
                conn.execute(
                    "UPDATE documents SET metadata_json = ? WHERE id = ?",
                    (json.dumps(meta, ensure_ascii=False), doc_id),
                )
                write_stigmergy_event(
                    conn, "hfo.gen89.kraken.knowledge_graph",
                    f"KG:doc_{doc_id}",
                    {
                        "doc_id": doc_id,
                        "title": title[:100],
                        "triples_count": len(triples),
                        "sample_triple": triples[0] if triples else None,
                        "model": model,
                        "task": "T6_KNOWLEDGE_GRAPH",
                    },
                )

            results["extracted"] += 1
            results["triples_total"] += len(triples)
            print(f"  [KG] doc {doc_id}: {len(triples)} triples — {title[:50]}...")

    except Exception as e:
        results["errors"] += 1
        print(f"  [T6 ERROR] {e}", file=sys.stderr)
    finally:
        conn.close()

    return results


# ═══════════════════════════════════════════════════════════════
# T7: TAG EXPANSION
# ═══════════════════════════════════════════════════════════════

async def tag_expansion(
    model: str = "gemma3:4b",
    batch_size: int = 3,
    dry_run: bool = False,
    orchestrator: Optional[SwarmOrchestrator] = None,
) -> dict:
    """
    Enrich document tags from content analysis.
    Adds semantic tags that improve FTS discoverability.
    Only adds to existing tags — never deletes.
    """
    results = {"enriched": 0, "tags_added": 0, "errors": 0}

    if orchestrator:
        await orchestrator.wait_if_paused()

    try:
        conn = get_db_readwrite()
    except Exception as e:
        results["errors"] = 1
        return results

    try:
        # Find docs with sparse or no tags
        cursor = conn.execute(
            """SELECT id, title, bluf, SUBSTR(content, 1, 2000) as content_preview,
                      tags, source, port, doc_type
               FROM documents
               WHERE (tags IS NULL OR tags = '' OR LENGTH(tags) < 20)
               AND bluf IS NOT NULL AND bluf != '' AND bluf != '---'
               ORDER BY RANDOM()
               LIMIT ?""",
            (batch_size,),
        )
        rows = cursor.fetchall()

        for row in rows:
            if orchestrator and not orchestrator._running:
                break
            if orchestrator:
                await orchestrator.wait_if_paused()

            doc_id = row["id"]
            title = row["title"] or "(untitled)"
            bluf = row["bluf"] or ""
            content = row["content_preview"] or ""
            existing_tags = row["tags"] or ""
            source = row["source"] or ""
            port = row["port"] or ""
            doc_type = row["doc_type"] or ""

            prompt = (
                f"Generate 5-10 semantic tags for this document.\n"
                f"Tags should be lowercase, single words or hyphenated-phrases.\n"
                f"Include: topic tags, domain tags, technology tags, octree port tags.\n\n"
                f"Title: {title}\nBLUF: {bluf}\nSource: {source}\nPort: {port}\nType: {doc_type}\n"
                f"Existing tags: {existing_tags}\n"
                f"Content: {content[:1500]}\n\n"
                f"New tags (comma-separated, no duplicates with existing):"
            )

            raw = await asyncio.get_event_loop().run_in_executor(
                None, lambda p=prompt: _ollama_generate(
                    p, system=SYSTEM_PROMPT, model=model, num_predict=128,
                ),
            )
            response = _strip_think_tags(raw)

            if not response or len(response) < 3:
                results["errors"] += 1
                continue

            # Parse new tags
            new_tags = []
            existing_set = set(t.strip().lower() for t in existing_tags.split(",") if t.strip())
            for tag in re.split(r"[,\n]", response):
                tag = tag.strip().lower().strip(".-#*")
                tag = re.sub(r"[^a-z0-9_-]", "", tag.replace(" ", "-"))
                if tag and len(tag) > 2 and len(tag) < 50 and tag not in existing_set:
                    new_tags.append(tag)
                    existing_set.add(tag)

            new_tags = new_tags[:10]

            if not new_tags:
                continue

            if not dry_run:
                # Merge with existing tags
                all_tags = existing_tags.rstrip(",")
                if all_tags:
                    all_tags += "," + ",".join(new_tags)
                else:
                    all_tags = ",".join(new_tags)

                conn.execute(
                    "UPDATE documents SET tags = ? WHERE id = ?",
                    (all_tags, doc_id),
                )
                write_stigmergy_event(
                    conn, "hfo.gen89.kraken.tags_expanded",
                    f"TAGS:doc_{doc_id}",
                    {
                        "doc_id": doc_id,
                        "title": title[:100],
                        "new_tags": new_tags,
                        "total_tags": len(existing_set),
                        "model": model,
                        "task": "T7_TAG_EXPANSION",
                    },
                )

            results["enriched"] += 1
            results["tags_added"] += len(new_tags)
            print(f"  [TAGS] doc {doc_id}: +{len(new_tags)} tags — {title[:50]}...")

    except Exception as e:
        results["errors"] += 1
        print(f"  [T7 ERROR] {e}", file=sys.stderr)
    finally:
        conn.close()

    return results


# ═══════════════════════════════════════════════════════════════
# T8: QUALITY AUDIT (CPU-only, no GPU needed)
# ═══════════════════════════════════════════════════════════════

async def quality_audit(
    batch_size: int = 5,
    dry_run: bool = False,
    orchestrator: Optional[SwarmOrchestrator] = None,
    **kwargs,
) -> dict:
    """
    Audit quality of existing enrichments without using GPU.
    Checks:
    - BLUFs that are just the title repeated
    - Ports that might be misclassified (P6 over-assignment)
    - Tags that are meaningless (too short, generic)
    - Metadata corruption (invalid JSON)

    Results stored in stigmergy as quality signals for future re-enrichment.
    """
    results = {"audited": 0, "issues_found": 0, "issues": []}

    if orchestrator:
        await orchestrator.wait_if_paused()

    try:
        conn = get_db_readonly()
    except Exception as e:
        return {"audited": 0, "issues_found": 0, "errors": 1}

    try:
        # Check #1: BLUF == title (lazy/bad enrichment)
        cursor = conn.execute(
            """SELECT id, title, bluf FROM documents
               WHERE bluf IS NOT NULL AND bluf != '' AND bluf != '---'
               AND bluf = title
               LIMIT ?""",
            (batch_size,),
        )
        for row in cursor.fetchall():
            results["audited"] += 1
            results["issues_found"] += 1
            results["issues"].append({
                "doc_id": row["id"],
                "issue": "bluf_equals_title",
                "detail": f"BLUF is identical to title: {row['title'][:80]}",
            })

        # Check #2: Port distribution skew (P6 over-assignment)
        port_dist = conn.execute(
            """SELECT port, COUNT(*) as cnt FROM documents
               WHERE port IS NOT NULL
               GROUP BY port ORDER BY cnt DESC""",
        ).fetchall()
        total_ported = sum(r["cnt"] for r in port_dist)
        if total_ported > 0:
            for r in port_dist:
                pct = r["cnt"] / total_ported * 100
                if pct > 40:  # One port has > 40% of all docs — suspicious
                    results["issues_found"] += 1
                    results["issues"].append({
                        "doc_id": None,
                        "issue": "port_distribution_skew",
                        "detail": f"Port {r['port']} has {pct:.1f}% of all classified docs ({r['cnt']}/{total_ported})",
                    })

        # Check #3: metadata_json corruption
        cursor = conn.execute(
            """SELECT id, title, metadata_json FROM documents
               WHERE metadata_json IS NOT NULL AND metadata_json != ''
               ORDER BY RANDOM()
               LIMIT ?""",
            (batch_size * 5,),
        )
        for row in cursor.fetchall():
            results["audited"] += 1
            try:
                meta = json.loads(row["metadata_json"])
                if not isinstance(meta, dict):
                    results["issues_found"] += 1
                    results["issues"].append({
                        "doc_id": row["id"],
                        "issue": "metadata_not_dict",
                        "detail": f"metadata_json is {type(meta).__name__}, expected dict",
                    })
            except json.JSONDecodeError:
                results["issues_found"] += 1
                results["issues"].append({
                    "doc_id": row["id"],
                    "issue": "metadata_json_corrupt",
                    "detail": f"Invalid JSON in metadata_json for doc {row['id']}",
                })

        # Check #4: BLUF starts with port code (gemma3:4b quirk from earlier testing)
        cursor = conn.execute(
            """SELECT id, title, bluf FROM documents
               WHERE bluf LIKE 'P_\n%' ESCAPE '\\'
               LIMIT ?""",
            (batch_size,),
        )
        for row in cursor.fetchall():
            results["audited"] += 1
            bluf = row["bluf"] or ""
            if re.match(r"^P\d\n", bluf):
                results["issues_found"] += 1
                results["issues"].append({
                    "doc_id": row["id"],
                    "issue": "bluf_starts_with_port",
                    "detail": f"BLUF starts with port code: {bluf[:60]}",
                })

        conn.close()

        # Log audit results
        if not dry_run and results["issues_found"] > 0:
            try:
                wconn = get_db_readwrite()
                write_stigmergy_event(
                    wconn, "hfo.gen89.kraken.quality_audit",
                    f"AUDIT:batch:{results['audited']}",
                    {
                        "audited": results["audited"],
                        "issues_found": results["issues_found"],
                        "issues": results["issues"][:10],  # Cap for event size
                        "task": "T8_QUALITY_AUDIT",
                    },
                )
                wconn.close()
            except Exception:
                pass

        if results["issues_found"] > 0:
            print(f"  [AUDIT] {results['issues_found']} issues in {results['audited']} docs")
            for iss in results["issues"][:5]:
                print(f"    {iss['issue']}: {iss['detail'][:80]}")

    except Exception as e:
        print(f"  [T8 ERROR] {e}", file=sys.stderr)

    return results


# ═══════════════════════════════════════════════════════════════
# WORKER REGISTRY — Maps WorkerType to function
# ═══════════════════════════════════════════════════════════════

WORKER_REGISTRY = {
    "progressive_summary": progressive_summarization,
    "knowledge_graph": knowledge_graph_extraction,
    "tag_expansion": tag_expansion,
    "quality_audit": quality_audit,
}


async def run_worker(
    worker_type: str,
    model: str = "gemma3:4b",
    batch_size: int = 2,
    dry_run: bool = False,
    orchestrator: Optional[SwarmOrchestrator] = None,
) -> dict:
    """Run a worker by type name."""
    fn = WORKER_REGISTRY.get(worker_type)
    if not fn:
        return {"error": f"Unknown worker type: {worker_type}"}
    return await fn(
        model=model, batch_size=batch_size,
        dry_run=dry_run, orchestrator=orchestrator,
    )


# ═══════════════════════════════════════════════════════════════
# CLI — Test workers standalone
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="P6 Kraken Swarm Workers — Test Runner")
    parser.add_argument("worker", choices=list(WORKER_REGISTRY.keys()) + ["all"],
                        help="Worker type to test")
    parser.add_argument("--model", default="gemma3:4b", help="Ollama model")
    parser.add_argument("--batch-size", type=int, default=2, help="Batch size")
    parser.add_argument("--dry-run", action="store_true", help="No writes")
    args = parser.parse_args()

    async def _run():
        if args.worker == "all":
            for wtype in WORKER_REGISTRY:
                print(f"\n=== {wtype.upper()} ===")
                r = await run_worker(wtype, model=args.model,
                                     batch_size=args.batch_size, dry_run=args.dry_run)
                print(f"  Result: {r}")
        else:
            r = await run_worker(args.worker, model=args.model,
                                 batch_size=args.batch_size, dry_run=args.dry_run)
            print(f"Result: {r}")

    asyncio.run(_run())
