#!/usr/bin/env python3
"""
hfo_p6_kraken_loop.py — P6 Kraken Strange Loop (NPU ↔ GPU)
============================================================
v1.0 | Gen90 | Port: P6 ASSIMILATE | Commander: Kraken Keeper
Powerword: ASSIMILATE | Spell: CLONE | School: Necromancy
Title: Devourer of Depths and Dreams | Trigram: ☶ Gen (Mountain)

PURPOSE:
    A strange loop daemon that puts NPU embeddings and GPU enrichment
    in a continuous recursive cycle, coordinated via SSOT stigmergy.

ARCHITECTURE:
    The strange loop has TWO tentacles that read each other's output:

    ┌──────────────────────────────────────────────────────────┐
    │  KRAKEN STRANGE LOOP                                     │
    │                                                          │
    │  ┌─────────────────┐    stigmergy    ┌────────────────┐ │
    │  │  NPU TENTACLE   │ ─────────────→  │  GPU TENTACLE  │ │
    │  │  (Embed+Discover)│                │  (Enrich+Shape)│ │
    │  │                  │  ←─────────────  │                │ │
    │  │  • Re-embed stale│    stigmergy    │  • Progressive │ │
    │  │  • Find clusters │                │    summarize   │ │
    │  │  • Detect orphans│                │  • KG extract  │ │
    │  │  • Quality gaps  │                │  • Tag expand  │ │
    │  └────────┬─────────┘                └───────┬────────┘ │
    │           │                                   │          │
    │           └───────────── SSOT ───────────────┘          │
    │                     (stigmergy_events)                   │
    └──────────────────────────────────────────────────────────┘

    Each cycle:
      1. NPU Tentacle reaches → embeds stale docs, finds clusters,
         writes kraken.npu.discovery events
      2. GPU Tentacle reaches → reads NPU discoveries, enriches docs
         via progressive summarization + KG, writes kraken.gpu.enrichment events
      3. Combined pulse emitted
      4. Sleep → next cycle: NPU reads GPU enrichment events and
         re-embeds those docs → cycle recurses

    The stigmergy IS the coordination. The loop IS the strange loop.
    "Everything that dies feeds the knowledge graph."

STRANGE LOOP INVARIANT:
    NPU writes → GPU reads NPU output → GPU writes → NPU reads GPU output
    This is the Hofstadter strange loop: each level reads the other's traces.
    The system's output becomes its input. Self-reference through stigmergy.

RESOURCE POLICY ("Take What Is Given"):
    IDLE/NOMINAL → Full batch sizes, both tentacles aggressive
    ELEVATED     → Reduced batch, NPU priority (cheaper)
    THROTTLED    → NPU only (zero VRAM), GPU paused
    CRITICAL     → Both paused, emit heartbeat only
    YIELDED      → Full stop

USAGE:
    # Run the strange loop (24/7 mode)
    python hfo_p6_kraken_loop.py

    # Single cycle (test)
    python hfo_p6_kraken_loop.py --single

    # Dry run (no SSOT writes)
    python hfo_p6_kraken_loop.py --dry-run --single

    # Custom interval and model
    python hfo_p6_kraken_loop.py --interval 45 --model qwen3:8b

    # Status — read the tentacle pheromone trail
    python hfo_p6_kraken_loop.py --status

    # JSON status (for other daemons)
    python hfo_p6_kraken_loop.py --status --json

Medallion: bronze
Port: P6 ASSIMILATE
Pointer key: daemon.p6_kraken_loop
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from hfo_ssot_write import get_db_readwrite as get_db_rw

# ═══════════════════════════════════════════════════════════════
# PATH RESOLUTION VIA PAL
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

DAEMON_NAME = "P6 Kraken Strange Loop"
DAEMON_VERSION = "1.0"
SOURCE_TAG = f"hfo_p6_kraken_loop_gen{GEN}"
DEFAULT_MODEL = os.getenv("HFO_P6_KRAKEN_MODEL", "gemma3:4b")
DEFAULT_INTERVAL = 60.0  # seconds between cycles
HEALTH_EVERY_N = 10  # health snapshot every N cycles

# Event type constants for stigmergy coordination
EVT_NPU_DISCOVERY = "hfo.gen90.kraken.npu.discovery"
EVT_GPU_ENRICHMENT = "hfo.gen90.kraken.gpu.enrichment"
EVT_LOOP_PULSE = "hfo.gen90.kraken.loop.pulse"
EVT_LOOP_HEALTH = "hfo.gen90.kraken.loop.health"

# Batch sizes per pressure level — "Take what is given"
BATCH_TABLE = {
    "IDLE":      {"npu": 50, "gpu": 5},
    "NOMINAL":   {"npu": 30, "gpu": 3},
    "ELEVATED":  {"npu": 20, "gpu": 2},
    "THROTTLED": {"npu": 10, "gpu": 0},  # NPU only
    "CRITICAL":  {"npu": 0,  "gpu": 0},  # Pause
    "YIELDED":   {"npu": 0,  "gpu": 0},  # Stop
}

# P6 ASSIMILATE identity
KRAKEN_LOOP_IDENTITY = {
    "port": "P6",
    "powerword": "ASSIMILATE",
    "commander": "Kraken Keeper",
    "title": "Devourer of Depths and Dreams",
    "spell": "CLONE (Necromancy)",
    "daemon": DAEMON_NAME,
    "version": DAEMON_VERSION,
    "architecture": "Strange Loop — NPU Tentacle ↔ GPU Tentacle via Stigmergy",
    "compute_axes": "NPU (OpenVINO embeddings) + GPU (Ollama enrichment)",
    "motto": "Everything that dies feeds the knowledge graph.",
}


# ═══════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn



def write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
    source: str = SOURCE_TAG,
) -> str:
    """Write a CloudEvent to stigmergy_events with content-hash dedup."""
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
        "timestamp": now,
        "datacontenttype": "application/json",
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "phase": "CLOUDEVENT",
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


# ═══════════════════════════════════════════════════════════════
# OLLAMA CLIENT
# ═══════════════════════════════════════════════════════════════

def ollama_is_alive() -> bool:
    try:
        import httpx
        with httpx.Client(timeout=5) as c:
            return c.get(f"{OLLAMA_BASE}/api/tags").status_code == 200
    except Exception:
        return False


def ollama_generate(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
    timeout: float = 180,
    temperature: float = 0.3,
    num_predict: int = 512,
) -> str:
    """Call Ollama generate API. Returns response text or empty on error."""
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


def _strip_think_tags(text: str) -> str:
    import re
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


# ═══════════════════════════════════════════════════════════════
# NPU EMBEDDER — Import with graceful fallback
# ═══════════════════════════════════════════════════════════════

HAS_NPU = False
_npu_error = ""

try:
    _res_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(_res_dir))
    from hfo_npu_embedder import (
        get_embedder,
        store_embedding,
        find_similar,
        get_embedding_stats,
        blob_to_embedding,
        embedding_to_blob,
        ensure_embeddings_table,
        cosine_similarity,
    )
    HAS_NPU = True
except ImportError as e:
    _npu_error = str(e)


# ═══════════════════════════════════════════════════════════════
# RESOURCE PRESSURE SENSING
# ═══════════════════════════════════════════════════════════════

def sense_pressure() -> str:
    """
    Quick resource pressure check. Returns one of:
    IDLE, NOMINAL, ELEVATED, THROTTLED, CRITICAL, YIELDED
    """
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory()
        ram_free_gb = ram.available / (1024 ** 3)

        if ram_free_gb < 2.0:
            return "CRITICAL"
        if cpu > 90:
            return "THROTTLED"
        if cpu > 70 or ram_free_gb < 4.0:
            return "ELEVATED"
        if cpu > 40:
            return "NOMINAL"
        return "IDLE"
    except ImportError:
        return "NOMINAL"  # No psutil → assume nominal


def get_batch_sizes(pressure: str) -> dict:
    """Get NPU/GPU batch sizes for current pressure level."""
    return BATCH_TABLE.get(pressure, BATCH_TABLE["NOMINAL"])


# ═══════════════════════════════════════════════════════════════
# §1  NPU TENTACLE — The Sensing Arm
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT_KRAKEN = (
    "You are the Kraken Keeper, commander of Port 6 (ASSIMILATE) in the HFO Octree. "
    "Title: Devourer of Depths and Dreams. Spell: CLONE (Necromancy). "
    "Be concise and precise. No filler. No markdown. Answer ONLY what is asked."
)


class NPUTentacle:
    """
    The NPU sensing arm of the Kraken Strange Loop.

    Responsibilities:
    1. Re-embed documents that have been enriched since last embedding
    2. Discover similarity clusters (groups of semantically related docs)
    3. Find orphan docs (low similarity to everything = isolated knowledge)
    4. Read GPU enrichment events and re-embed those specific docs

    Writes: EVT_NPU_DISCOVERY events to stigmergy
    Reads: EVT_GPU_ENRICHMENT events from stigmergy
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            "total_embedded": 0,
            "total_stale_found": 0,
            "total_clusters_found": 0,
            "total_orphans_found": 0,
            "total_cycles": 0,
            "errors": 0,
        }

    async def reach(self, batch_size: int = 30, cycle: int = 0) -> dict:
        """
        One tentacle reach — sense the corpus via NPU.

        Returns a report dict with discoveries for the GPU Tentacle.
        """
        report = {
            "stale_reembedded": 0,
            "gpu_triggered_reembeds": 0,
            "clusters_found": [],
            "orphans_found": [],
            "coverage": {},
            "errors": 0,
            "elapsed_ms": 0,
        }

        if not HAS_NPU:
            report["errors"] = 1
            report["error_msg"] = f"NPU unavailable: {_npu_error}"
            return report

        t0 = time.time()

        try:
            embedder = get_embedder()
            conn_ro = get_db_ro()
            conn_rw = get_db_rw()
            ensure_embeddings_table(conn_rw)

            # ── Step 1: Re-embed docs enriched by GPU since last embed ──
            # Find docs where metadata_json was updated after their embedding
            # We detect this by finding docs with p6_enrichment that have
            # older embeddings (or embeddings created before last GPU event)
            stale_rows = conn_ro.execute(
                """SELECT d.id, d.title, d.bluf, SUBSTR(d.content, 1, 2000) as content_head,
                          d.metadata_json
                   FROM documents d
                   JOIN embeddings e ON d.id = e.doc_id
                   WHERE d.metadata_json LIKE '%p6_enrichment%'
                   AND e.created_at < (
                       SELECT COALESCE(
                           (SELECT MAX(timestamp) FROM stigmergy_events
                            WHERE event_type LIKE 'hfo.gen90.kraken.%'
                            AND event_type NOT LIKE '%loop%'
                            AND event_type NOT LIKE '%npu%'),
                           e.created_at
                       )
                   )
                   ORDER BY RANDOM()
                   LIMIT ?""",
                (min(batch_size, 30),),
            ).fetchall()

            for row in stale_rows:
                doc_id = row["id"]
                title = row["title"] or ""
                bluf = row["bluf"] or ""
                content = row["content_head"] or ""

                # Build enriched text including p6 enrichment data
                text_parts = [title]
                if bluf and bluf != "---":
                    text_parts.append(bluf)

                # Include p6 enrichment summary if available
                try:
                    meta = json.loads(row["metadata_json"] or "{}")
                    p6 = meta.get("p6_enrichment", {})
                    if p6.get("summary_3sent"):
                        text_parts.append(p6["summary_3sent"])
                    if p6.get("key_insights"):
                        insights = p6["key_insights"]
                        if isinstance(insights, list):
                            text_parts.append(" ".join(insights[:3]))
                except (json.JSONDecodeError, AttributeError):
                    pass

                text_parts.append(content[:500])
                text = " ".join(t for t in text_parts if t).strip()

                if not text:
                    continue

                try:
                    vec = embedder.embed(text)
                    if not self.dry_run:
                        store_embedding(conn_rw, doc_id, vec, device=embedder.device)
                    report["stale_reembedded"] += 1
                except Exception as e:
                    report["errors"] += 1

                # Yield to event loop
                if report["stale_reembedded"] % 10 == 0:
                    await asyncio.sleep(0)

            # ── Step 2: Read last GPU enrichment events to re-embed those docs ──
            gpu_events = conn_ro.execute(
                """SELECT data_json FROM stigmergy_events
                   WHERE event_type = ?
                   ORDER BY id DESC LIMIT 5""",
                (EVT_GPU_ENRICHMENT,),
            ).fetchall()

            gpu_doc_ids = set()
            for evt_row in gpu_events:
                try:
                    evt_data = json.loads(evt_row["data_json"])
                    enriched_docs = evt_data.get("data", {}).get("enriched_doc_ids", [])
                    gpu_doc_ids.update(enriched_docs)
                except (json.JSONDecodeError, AttributeError):
                    pass

            # Re-embed GPU-enriched docs not yet re-embedded
            for doc_id in list(gpu_doc_ids)[:batch_size]:
                row = conn_ro.execute(
                    """SELECT title, bluf, SUBSTR(content, 1, 2000) as content_head,
                              metadata_json
                       FROM documents WHERE id = ?""",
                    (doc_id,),
                ).fetchone()
                if not row:
                    continue

                text_parts = [row["title"] or ""]
                if row["bluf"] and row["bluf"] != "---":
                    text_parts.append(row["bluf"])
                try:
                    meta = json.loads(row["metadata_json"] or "{}")
                    p6 = meta.get("p6_enrichment", {})
                    if p6.get("summary_3sent"):
                        text_parts.append(p6["summary_3sent"])
                except Exception:
                    pass
                text_parts.append((row["content_head"] or "")[:500])
                text = " ".join(t for t in text_parts if t).strip()

                if text:
                    try:
                        vec = embedder.embed(text)
                        if not self.dry_run:
                            store_embedding(conn_rw, doc_id, vec, device=embedder.device)
                        report["gpu_triggered_reembeds"] += 1
                    except Exception:
                        report["errors"] += 1

            # ── Step 3: Discover similarity clusters ──
            # Pick a random recently-enriched doc and find its nearest neighbors
            seed_row = conn_ro.execute(
                """SELECT d.id, d.title, e.embedding
                   FROM documents d
                   JOIN embeddings e ON d.id = e.doc_id
                   WHERE d.metadata_json LIKE '%p6_enrichment%'
                   ORDER BY RANDOM()
                   LIMIT 1""",
            ).fetchone()

            if seed_row and seed_row["embedding"]:
                seed_vec = blob_to_embedding(seed_row["embedding"])
                similar = find_similar(conn_ro, seed_vec, top_k=8, min_score=0.5)
                if len(similar) >= 3:
                    cluster = {
                        "seed_id": seed_row["id"],
                        "seed_title": (seed_row["title"] or "")[:80],
                        "members": [s["doc_id"] for s in similar],
                        "scores": [s["score"] for s in similar],
                        "size": len(similar),
                    }
                    report["clusters_found"].append(cluster)

            # ── Step 4: Find orphan docs (low similarity to everything) ──
            orphan_row = conn_ro.execute(
                """SELECT d.id, d.title, e.embedding
                   FROM documents d
                   JOIN embeddings e ON d.id = e.doc_id
                   WHERE d.bluf IS NOT NULL AND d.bluf != '---'
                   ORDER BY RANDOM()
                   LIMIT 5""",
            ).fetchall()

            for orow in orphan_row:
                if orow["embedding"]:
                    ovec = blob_to_embedding(orow["embedding"])
                    sim = find_similar(conn_ro, ovec, top_k=3, min_score=0.3)
                    # If max similarity to anything else is very low → orphan
                    non_self = [s for s in sim if s["doc_id"] != orow["id"]]
                    if non_self and max(s["score"] for s in non_self) < 0.4:
                        report["orphans_found"].append({
                            "doc_id": orow["id"],
                            "title": (orow["title"] or "")[:80],
                            "max_similarity": max(s["score"] for s in non_self),
                        })

            # ── Step 5: Coverage stats ──
            report["coverage"] = get_embedding_stats(conn_ro)

            conn_ro.close()
            conn_rw.close()

        except Exception as e:
            report["errors"] += 1
            report["error_msg"] = str(e)
            traceback.print_exc(file=sys.stderr)

        elapsed = round((time.time() - t0) * 1000, 1)
        report["elapsed_ms"] = elapsed

        # Update cumulative stats
        self.stats["total_embedded"] += report["stale_reembedded"] + report["gpu_triggered_reembeds"]
        self.stats["total_stale_found"] += report["stale_reembedded"]
        self.stats["total_clusters_found"] += len(report["clusters_found"])
        self.stats["total_orphans_found"] += len(report["orphans_found"])
        self.stats["total_cycles"] += 1
        self.stats["errors"] += report["errors"]

        return report


# ═══════════════════════════════════════════════════════════════
# §2  GPU TENTACLE — The Shaping Arm
# ═══════════════════════════════════════════════════════════════

class GPUTentacle:
    """
    The GPU enrichment arm of the Kraken Strange Loop.

    Responsibilities:
    1. Read NPU discovery events (clusters, orphans, quality gaps)
    2. Run progressive summarization on docs flagged by NPU
    3. Run knowledge graph extraction on cluster members
    4. Fix quality issues (BLUF == title, stale summaries)

    Writes: EVT_GPU_ENRICHMENT events to stigmergy
    Reads: EVT_NPU_DISCOVERY events from stigmergy
    """

    def __init__(self, model: str = DEFAULT_MODEL, dry_run: bool = False):
        self.model = model
        self.dry_run = dry_run
        self.stats = {
            "total_summaries": 0,
            "total_kg_triples": 0,
            "total_quality_fixes": 0,
            "total_cycles": 0,
            "ai_calls": 0,
            "errors": 0,
        }

    async def reach(
        self,
        npu_report: dict,
        batch_size: int = 3,
        cycle: int = 0,
    ) -> dict:
        """
        One tentacle reach — enrich the corpus via GPU.

        Reads the NPU tentacle's discoveries and acts on them.
        Returns a report dict.
        """
        report = {
            "summaries_generated": 0,
            "kg_triples_extracted": 0,
            "quality_fixes": 0,
            "enriched_doc_ids": [],
            "errors": 0,
            "elapsed_ms": 0,
        }

        if not ollama_is_alive():
            report["errors"] = 1
            report["error_msg"] = "Ollama not reachable"
            return report

        t0 = time.time()

        try:
            conn = get_db_rw()

            # ── Priority 1: Enrich docs from NPU clusters ──
            # Pick docs from discovered clusters that lack enrichment
            target_doc_ids = []

            for cluster in npu_report.get("clusters_found", []):
                for doc_id in cluster.get("members", [])[:batch_size]:
                    if doc_id not in target_doc_ids:
                        target_doc_ids.append(doc_id)

            # Also add orphan docs (need enrichment most)
            for orphan in npu_report.get("orphans_found", []):
                did = orphan.get("doc_id")
                if did and did not in target_doc_ids:
                    target_doc_ids.append(did)

            # Fallback: if NPU found nothing interesting, pick random unenriched docs
            if not target_doc_ids:
                fallback_rows = conn.execute(
                    """SELECT id FROM documents
                       WHERE metadata_json NOT LIKE '%summary_3sent%'
                       AND bluf IS NOT NULL AND bluf != '---'
                       ORDER BY RANDOM()
                       LIMIT ?""",
                    (batch_size,),
                ).fetchall()
                target_doc_ids = [r["id"] for r in fallback_rows]

            # Cap to batch size
            target_doc_ids = target_doc_ids[:batch_size]

            # ── Enrich each target doc ──
            for doc_id in target_doc_ids:
                row = conn.execute(
                    """SELECT id, title, bluf, SUBSTR(content, 1, 3000) as content_preview,
                              metadata_json, tags, source, port
                       FROM documents WHERE id = ?""",
                    (doc_id,),
                ).fetchone()

                if not row:
                    continue

                title = row["title"] or "(untitled)"
                bluf = row["bluf"] or ""
                content = row["content_preview"] or ""
                meta_raw = row["metadata_json"] or "{}"

                try:
                    meta = json.loads(meta_raw)
                except json.JSONDecodeError:
                    meta = {}

                p6 = meta.get("p6_enrichment", {})
                enriched_this_doc = False

                # ─── Progressive Summary (Pass 2: 3-sentence summary) ───
                if not p6.get("summary_3sent") and content and len(content) > 100:
                    prompt = (
                        f"Summarize this document in exactly 3 sentences.\n"
                        f"Title: {title}\n"
                        f"BLUF: {bluf}\n\n"
                        f"Content:\n{content[:2500]}\n\n"
                        f"3-sentence summary:"
                    )
                    raw = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda p=prompt: ollama_generate(
                            p, system=SYSTEM_PROMPT_KRAKEN, model=self.model,
                            num_predict=256,
                        ),
                    )
                    self.stats["ai_calls"] += 1
                    summary = _strip_think_tags(raw)

                    if summary and len(summary) > 20:
                        p6["summary_3sent"] = summary
                        p6["summary_model"] = self.model
                        p6["summary_ts"] = datetime.now(timezone.utc).isoformat()
                        report["summaries_generated"] += 1
                        enriched_this_doc = True

                # ─── Knowledge Graph (entity triples) ───
                if not p6.get("kg_triples") and content and len(content) > 200:
                    prompt = (
                        f"Extract up to 8 entity-relation triples from this document.\n"
                        f"Format: SUBJECT|PREDICATE|OBJECT (one per line)\n"
                        f"Use lowercase. Predicates should be verbs.\n\n"
                        f"Title: {title}\n"
                        f"BLUF: {bluf}\n\n"
                        f"Content:\n{content[:2000]}\n\n"
                        f"Triples:"
                    )
                    raw = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda p=prompt: ollama_generate(
                            p, system=SYSTEM_PROMPT_KRAKEN, model=self.model,
                            num_predict=256,
                        ),
                    )
                    self.stats["ai_calls"] += 1
                    response = _strip_think_tags(raw)

                    triples = []
                    import re
                    for line in response.split("\n"):
                        line = line.strip().lstrip("0123456789.-) ")
                        parts = re.split(r"\s*\|\s*", line)
                        if len(parts) == 3:
                            s, p_val, o = [x.strip().lower()[:100] for x in parts]
                            if s and p_val and o and len(s) > 1 and len(o) > 1:
                                triples.append({"s": s, "p": p_val, "o": o})
                    triples = triples[:8]

                    if triples:
                        p6["kg_triples"] = triples
                        p6["kg_model"] = self.model
                        p6["kg_ts"] = datetime.now(timezone.utc).isoformat()
                        report["kg_triples_extracted"] += len(triples)
                        enriched_this_doc = True

                # ─── Quality Fix: BLUF == title ───
                if bluf and bluf == title and content and len(content) > 100:
                    prompt = (
                        f"Write a BLUF (Bottom Line Up Front) for this document.\n"
                        f"1-3 sentences. No quotes, no markdown.\n\n"
                        f"Title: {title}\n"
                        f"Content:\n{content[:2000]}\n\n"
                        f"BLUF:"
                    )
                    raw = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda p=prompt: ollama_generate(
                            p, system=SYSTEM_PROMPT_KRAKEN, model=self.model,
                            num_predict=200,
                        ),
                    )
                    self.stats["ai_calls"] += 1
                    new_bluf = _strip_think_tags(raw)

                    if new_bluf and len(new_bluf) > 10 and new_bluf != title:
                        if not self.dry_run:
                            conn.execute(
                                "UPDATE documents SET bluf = ? WHERE id = ?",
                                (new_bluf[:500], doc_id),
                            )
                        report["quality_fixes"] += 1
                        enriched_this_doc = True

                # ─── Write enrichment to metadata_json ───
                if enriched_this_doc and not self.dry_run:
                    meta["p6_enrichment"] = p6
                    conn.execute(
                        "UPDATE documents SET metadata_json = ? WHERE id = ?",
                        (json.dumps(meta), doc_id),
                    )
                    report["enriched_doc_ids"].append(doc_id)
                    conn.commit()

                    print(f"    [GPU] doc {doc_id}: "
                          f"{'sum ' if report['summaries_generated'] else ''}"
                          f"{'kg ' if report['kg_triples_extracted'] else ''}"
                          f"{'fix ' if report['quality_fixes'] else ''}"
                          f"— {title[:50]}...")

            conn.close()

        except Exception as e:
            report["errors"] += 1
            report["error_msg"] = str(e)
            traceback.print_exc(file=sys.stderr)

        elapsed = round((time.time() - t0) * 1000, 1)
        report["elapsed_ms"] = elapsed

        # Update cumulative stats
        self.stats["total_summaries"] += report["summaries_generated"]
        self.stats["total_kg_triples"] += report["kg_triples_extracted"]
        self.stats["total_quality_fixes"] += report["quality_fixes"]
        self.stats["total_cycles"] += 1
        self.stats["errors"] += report["errors"]

        return report


# ═══════════════════════════════════════════════════════════════
# §3  KRAKEN LOOP — The Strange Loop Engine
# ═══════════════════════════════════════════════════════════════

class KrakenLoop:
    """
    The P6 Kraken Strange Loop — two tentacles in mutual stigmergy dialogue.

    Each cycle:
      1. Sense pressure → determine batch sizes
      2. NPU Tentacle reaches (embed + discover)
      3. GPU Tentacle reaches (enrich based on NPU discoveries)
      4. Emit combined pulse to stigmergy
      5. Sleep → next cycle
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dry_run: bool = False,
        health_every: int = HEALTH_EVERY_N,
    ):
        self.model = model
        self.dry_run = dry_run
        self.health_every = health_every
        self._running = True
        self._cycle = 0
        self._start_time = time.time()
        self.errors = 0

        self.npu = NPUTentacle(dry_run=dry_run)
        self.gpu = GPUTentacle(model=model, dry_run=dry_run)

    def stop(self):
        self._running = False

    def run_cycle(self) -> dict:
        """Run one complete strange loop cycle synchronously."""
        return asyncio.get_event_loop().run_until_complete(self._async_cycle())

    async def _async_cycle(self) -> dict:
        """One full cycle: sense → NPU reach → GPU reach → pulse."""
        self._cycle += 1
        cycle = self._cycle
        t0 = time.time()

        # ── Sense pressure ──
        pressure = sense_pressure()
        batches = get_batch_sizes(pressure)

        result = {
            "loop_cycle": cycle,
            "pressure": pressure,
            "npu_batch": batches["npu"],
            "gpu_batch": batches["gpu"],
            "model": self.model,
            "npu": {},
            "gpu": {},
            "errors": 0,
        }

        # ── NPU Tentacle reaches ──
        npu_report = {}
        if batches["npu"] > 0:
            try:
                npu_report = await self.npu.reach(
                    batch_size=batches["npu"], cycle=cycle,
                )
                result["npu"] = npu_report
            except Exception as e:
                result["npu"] = {"error": str(e)}
                result["errors"] += 1
                self.errors += 1
        else:
            result["npu"] = {"skipped": True, "reason": f"pressure={pressure}"}

        # ── GPU Tentacle reaches (reads NPU output) ──
        if batches["gpu"] > 0:
            try:
                gpu_report = await self.gpu.reach(
                    npu_report=npu_report,
                    batch_size=batches["gpu"],
                    cycle=cycle,
                )
                result["gpu"] = gpu_report
            except Exception as e:
                result["gpu"] = {"error": str(e)}
                result["errors"] += 1
                self.errors += 1
        else:
            result["gpu"] = {"skipped": True, "reason": f"pressure={pressure}"}

        # ── Emit combined pulse ──
        elapsed_ms = round((time.time() - t0) * 1000, 1)
        result["combined_duration_ms"] = elapsed_ms

        if not self.dry_run:
            try:
                conn = get_db_rw()

                # Write NPU discovery event
                npu_stale = npu_report.get("stale_reembedded", 0)
                npu_gpu_triggered = npu_report.get("gpu_triggered_reembeds", 0)
                npu_clusters = len(npu_report.get("clusters_found", []))
                npu_orphans = len(npu_report.get("orphans_found", []))

                if npu_stale or npu_gpu_triggered or npu_clusters or npu_orphans:
                    write_event(conn, EVT_NPU_DISCOVERY,
                        f"NPU:cycle_{cycle}:re={npu_stale}:cl={npu_clusters}:or={npu_orphans}",
                        {
                            "cycle": cycle,
                            "stale_reembedded": npu_stale,
                            "gpu_triggered_reembeds": npu_gpu_triggered,
                            "clusters_found": npu_report.get("clusters_found", []),
                            "orphans_found": npu_report.get("orphans_found", []),
                            "coverage": npu_report.get("coverage", {}),
                            "elapsed_ms": npu_report.get("elapsed_ms", 0),
                        },
                    )

                # Write GPU enrichment event
                gpu_summaries = result["gpu"].get("summaries_generated", 0)
                gpu_kg = result["gpu"].get("kg_triples_extracted", 0)
                gpu_fixes = result["gpu"].get("quality_fixes", 0)
                gpu_doc_ids = result["gpu"].get("enriched_doc_ids", [])

                if gpu_summaries or gpu_kg or gpu_fixes:
                    write_event(conn, EVT_GPU_ENRICHMENT,
                        f"GPU:cycle_{cycle}:sum={gpu_summaries}:kg={gpu_kg}:fix={gpu_fixes}",
                        {
                            "cycle": cycle,
                            "summaries_generated": gpu_summaries,
                            "kg_triples_extracted": gpu_kg,
                            "quality_fixes": gpu_fixes,
                            "enriched_doc_ids": gpu_doc_ids,
                            "model": self.model,
                            "elapsed_ms": result["gpu"].get("elapsed_ms", 0),
                        },
                    )

                # Write combined pulse
                write_event(conn, EVT_LOOP_PULSE,
                    f"PULSE:cycle_{cycle}:{pressure}",
                    {
                        "cycle": cycle,
                        "pressure": pressure,
                        "npu_batch": batches["npu"],
                        "gpu_batch": batches["gpu"],
                        "npu_reembedded": npu_stale + npu_gpu_triggered,
                        "npu_clusters": npu_clusters,
                        "npu_orphans": npu_orphans,
                        "gpu_summaries": gpu_summaries,
                        "gpu_kg_triples": gpu_kg,
                        "gpu_quality_fixes": gpu_fixes,
                        "combined_duration_ms": elapsed_ms,
                        "model": self.model,
                        "identity": KRAKEN_LOOP_IDENTITY,
                    },
                )
                conn.close()
            except Exception as e:
                print(f"  [PULSE ERROR] {e}", file=sys.stderr)

        return result

    async def _emit_loop_health(self):
        """Emit a health snapshot to stigmergy."""
        uptime = time.time() - self._start_time
        try:
            conn_ro = get_db_ro()
            coverage = {}
            if HAS_NPU:
                coverage = get_embedding_stats(conn_ro)

            total_docs = conn_ro.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            total_events = conn_ro.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]

            # Count loop-specific events
            loop_events = conn_ro.execute(
                "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE 'hfo.gen90.kraken.%'"
            ).fetchone()[0]

            # Count enriched docs
            enriched_docs = conn_ro.execute(
                "SELECT COUNT(*) FROM documents WHERE metadata_json LIKE '%p6_enrichment%'"
            ).fetchone()[0]

            conn_ro.close()

            health = {
                "cycle": self._cycle,
                "uptime_s": round(uptime, 1),
                "pressure": sense_pressure(),
                "total_docs": total_docs,
                "total_events": total_events,
                "loop_events": loop_events,
                "enriched_docs": enriched_docs,
                "embedding_coverage": coverage,
                "npu_stats": dict(self.npu.stats),
                "gpu_stats": dict(self.gpu.stats),
                "loop_errors": self.errors,
                "model": self.model,
                "identity": KRAKEN_LOOP_IDENTITY,
            }

            if not self.dry_run:
                conn = get_db_rw()
                write_event(conn, EVT_LOOP_HEALTH,
                    f"HEALTH:cycle_{self._cycle}",
                    health,
                )
                conn.close()

        except Exception as e:
            print(f"  [HEALTH ERROR] {e}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════
# §4  DAEMON LOOP — The Eternal Strange Loop
# ═══════════════════════════════════════════════════════════════

async def daemon_loop(
    loop_engine: KrakenLoop,
    interval: float = DEFAULT_INTERVAL,
    max_cycles: Optional[int] = None,
):
    """Run the Kraken Strange Loop forever (or for max_cycles)."""
    banner = f"""
  ╔═══════════════════════════════════════════════════════════╗
  ║  {DAEMON_NAME} v{DAEMON_VERSION}                         ║
  ║  Port: P6 ASSIMILATE | Spell: CLONE (Necromancy)         ║
  ║  Architecture: NPU Tentacle ↔ GPU Tentacle               ║
  ║  Model: {loop_engine.model:48s} ║
  ║  NPU: {'ONLINE' if HAS_NPU else 'OFFLINE — ' + _npu_error[:37]:48s} ║
  ║  Interval: {interval:4.0f}s | Health every: {loop_engine.health_every} cycles              ║
  ║  Mode: {'DRY RUN' if loop_engine.dry_run else '24/7 STRANGE LOOP':48s} ║
  ╚═══════════════════════════════════════════════════════════╝

  The tentacles reach. The stigmergy coordinates.
  Everything that dies feeds the knowledge graph.
"""
    print(banner)

    consecutive_errors = 0
    MAX_BACKOFF = 300  # 5 min max

    while loop_engine._running:
        try:
            report = await loop_engine._async_cycle()

            # One-line cycle summary
            npu = report.get("npu", {})
            gpu = report.get("gpu", {})
            pressure = report.get("pressure", "?")
            npu_re = npu.get("stale_reembedded", 0) + npu.get("gpu_triggered_reembeds", 0)
            npu_cl = len(npu.get("clusters_found", []))
            gpu_sum = gpu.get("summaries_generated", 0)
            gpu_kg = gpu.get("kg_triples_extracted", 0)
            gpu_fix = gpu.get("quality_fixes", 0)
            dur = report.get("combined_duration_ms", 0)
            errs = report.get("errors", 0)

            print(
                f"  [{loop_engine._cycle:>4}] "
                f"{pressure:9s} | "
                f"NPU: re={npu_re} cl={npu_cl} | "
                f"GPU: sum={gpu_sum} kg={gpu_kg} fix={gpu_fix} | "
                f"{dur:.0f}ms"
                + (f" [{errs} err]" if errs else ""),
            )

            consecutive_errors = 0

            # Health snapshot
            if loop_engine._cycle % loop_engine.health_every == 0:
                await loop_engine._emit_loop_health()
                print(f"  [HEALTH] Snapshot emitted at cycle {loop_engine._cycle}")

        except Exception as e:
            consecutive_errors += 1
            loop_engine.errors += 1
            backoff = min(interval * (2 ** consecutive_errors), MAX_BACKOFF)
            print(f"  [ERROR] Cycle failed: {e} (backoff {backoff:.0f}s)", file=sys.stderr)
            if consecutive_errors >= 5:
                print("  [FATAL] 5 consecutive errors. Stopping.", file=sys.stderr)
                break
            await asyncio.sleep(backoff)
            continue

        # Max cycles check
        if max_cycles and loop_engine._cycle >= max_cycles:
            print(f"\n  Reached max cycles ({max_cycles}). Stopping.")
            break

        # Sleep with responsive shutdown
        for _ in range(int(interval)):
            if not loop_engine._running:
                break
            await asyncio.sleep(1)

        # Periodic GC
        if loop_engine._cycle % 20 == 0:
            gc.collect()

    # Final health snapshot
    if not loop_engine.dry_run:
        await loop_engine._emit_loop_health()

    uptime = time.time() - loop_engine._start_time
    print(f"\n  Kraken Strange Loop stopped after {loop_engine._cycle} cycles ({uptime/60:.1f}m)")
    print(f"  NPU: {loop_engine.npu.stats}")
    print(f"  GPU: {loop_engine.gpu.stats}")
    print(f"  The depths remember. The knowledge graph grows.\n")


# ═══════════════════════════════════════════════════════════════
# §5  STATUS — Read the Tentacle Pheromone Trail
# ═══════════════════════════════════════════════════════════════

def print_status(as_json: bool = False):
    """Print the strange loop status from stigmergy."""
    status = {
        "daemon": DAEMON_NAME,
        "version": DAEMON_VERSION,
        "ssot_db": str(SSOT_DB),
        "db_exists": SSOT_DB.exists(),
        "ollama_alive": ollama_is_alive(),
        "npu_available": HAS_NPU,
        "pressure": sense_pressure(),
    }

    if not SSOT_DB.exists():
        if as_json:
            print(json.dumps(status, indent=2))
        else:
            print(f"  {DAEMON_NAME} — No SSOT found at {SSOT_DB}")
        return

    conn = get_db_ro()
    try:
        # Last loop pulse
        pulse_row = conn.execute(
            "SELECT subject, timestamp, SUBSTR(data_json, 1, 1500) as data "
            "FROM stigmergy_events WHERE event_type = ? "
            "ORDER BY id DESC LIMIT 1",
            (EVT_LOOP_PULSE,),
        ).fetchone()

        if pulse_row:
            try:
                pulse = json.loads(pulse_row["data"]).get("data", {})
                status["last_pulse"] = {
                    "timestamp": pulse_row["timestamp"][:19],
                    "cycle": pulse.get("cycle"),
                    "pressure": pulse.get("pressure"),
                    "npu_reembedded": pulse.get("npu_reembedded"),
                    "npu_clusters": pulse.get("npu_clusters"),
                    "gpu_summaries": pulse.get("gpu_summaries"),
                    "gpu_kg_triples": pulse.get("gpu_kg_triples"),
                    "duration_ms": pulse.get("combined_duration_ms"),
                }
            except (json.JSONDecodeError, AttributeError):
                status["last_pulse"] = None
        else:
            status["last_pulse"] = None

        # Last health snapshot
        health_row = conn.execute(
            "SELECT SUBSTR(data_json, 1, 2000) as data, timestamp "
            "FROM stigmergy_events WHERE event_type = ? "
            "ORDER BY id DESC LIMIT 1",
            (EVT_LOOP_HEALTH,),
        ).fetchone()

        if health_row:
            try:
                health = json.loads(health_row["data"]).get("data", {})
                status["last_health"] = {
                    "timestamp": health_row["timestamp"][:19],
                    "cycle": health.get("cycle"),
                    "enriched_docs": health.get("enriched_docs"),
                    "loop_events": health.get("loop_events"),
                    "npu_total_embedded": health.get("npu_stats", {}).get("total_embedded"),
                    "gpu_total_summaries": health.get("gpu_stats", {}).get("total_summaries"),
                    "gpu_total_kg": health.get("gpu_stats", {}).get("total_kg_triples"),
                }
            except (json.JSONDecodeError, AttributeError):
                status["last_health"] = None
        else:
            status["last_health"] = None

        # Event counts
        for evt_type, label in [
            (EVT_NPU_DISCOVERY, "npu_discoveries"),
            (EVT_GPU_ENRICHMENT, "gpu_enrichments"),
            (EVT_LOOP_PULSE, "loop_pulses"),
            (EVT_LOOP_HEALTH, "health_snapshots"),
        ]:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM stigmergy_events WHERE event_type = ?",
                (evt_type,),
            ).fetchone()[0]
            status[label] = cnt

        # Embedding coverage
        if HAS_NPU:
            status["embedding_coverage"] = get_embedding_stats(conn)

        # Enrichment coverage
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        enriched = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE metadata_json LIKE '%p6_enrichment%'"
        ).fetchone()[0]
        status["enrichment_coverage"] = {
            "total_docs": total,
            "enriched_docs": enriched,
            "pct": round(100 * enriched / max(total, 1), 1),
        }

    finally:
        conn.close()

    if as_json:
        print(json.dumps(status, indent=2, default=str))
        return

    # Pretty print
    print(f"\n  {DAEMON_NAME} v{DAEMON_VERSION} — Status Report")
    print("  " + "=" * 58)
    print(f"  SSOT:      {SSOT_DB}")
    print(f"  Ollama:    {'ONLINE' if status['ollama_alive'] else 'OFFLINE'}")
    print(f"  NPU:       {'ONLINE' if status['npu_available'] else 'OFFLINE'}")
    print(f"  Pressure:  {status['pressure']}")

    lp = status.get("last_pulse")
    if lp:
        print(f"\n  Last Pulse:")
        print(f"    Timestamp:  {lp.get('timestamp')}")
        print(f"    Cycle:      {lp.get('cycle')}")
        print(f"    Pressure:   {lp.get('pressure')}")
        print(f"    NPU:        re={lp.get('npu_reembedded', 0)} cl={lp.get('npu_clusters', 0)}")
        print(f"    GPU:        sum={lp.get('gpu_summaries', 0)} kg={lp.get('gpu_kg_triples', 0)}")
        print(f"    Duration:   {lp.get('duration_ms', 0):.0f}ms")
    else:
        print(f"\n  (No loop pulses yet — loop has not run)")

    lh = status.get("last_health")
    if lh:
        print(f"\n  Last Health:")
        print(f"    Timestamp:       {lh.get('timestamp')}")
        print(f"    Enriched docs:   {lh.get('enriched_docs', 0)}")
        print(f"    Loop events:     {lh.get('loop_events', 0)}")
        print(f"    NPU embeddings:  {lh.get('npu_total_embedded', 0)}")
        print(f"    GPU summaries:   {lh.get('gpu_total_summaries', 0)}")
        print(f"    GPU KG triples:  {lh.get('gpu_total_kg', 0)}")

    print(f"\n  Event Counts:")
    print(f"    NPU discoveries: {status.get('npu_discoveries', 0)}")
    print(f"    GPU enrichments: {status.get('gpu_enrichments', 0)}")
    print(f"    Loop pulses:     {status.get('loop_pulses', 0)}")
    print(f"    Health shots:    {status.get('health_snapshots', 0)}")

    ec = status.get("enrichment_coverage", {})
    print(f"\n  Enrichment Coverage:")
    print(f"    Total docs:    {ec.get('total_docs', 0)}")
    print(f"    Enriched:      {ec.get('enriched_docs', 0)} ({ec.get('pct', 0):.1f}%)")

    emb = status.get("embedding_coverage", {})
    if emb:
        print(f"\n  Embedding Coverage:")
        print(f"    Embedded:      {emb.get('total_embedded', 0)} / {emb.get('total_docs', 0)} "
              f"({emb.get('coverage_pct', 0):.1f}%)")

    print(f"\n  The tentacles reach. The stigmergy coordinates.")
    print(f"  Everything that dies feeds the knowledge graph.\n")


# ═══════════════════════════════════════════════════════════════
# §6  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"{DAEMON_NAME} v{DAEMON_VERSION} — NPU ↔ GPU Strange Loop (Gen{GEN})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
The Kraken Strange Loop puts NPU and GPU in mutual stigmergy dialogue:

  Each cycle:
    NPU Tentacle → embeds stale docs, discovers clusters, finds orphans
    GPU Tentacle → reads NPU discoveries, enriches via summaries + KG
    Combined pulse → written to SSOT stigmergy
    Next cycle: NPU reads GPU enrichment events → re-embeds → better results

  THIS IS THE STRANGE LOOP — each tentacle reads the other's output.
  The system's output becomes its input. Self-reference through stigmergy.

Resource policy ("Take What Is Given"):
  IDLE/NOMINAL → Full batch (NPU={BATCH_TABLE["NOMINAL"]["npu"]}, GPU={BATCH_TABLE["NOMINAL"]["gpu"]})
  ELEVATED     → Reduced (NPU={BATCH_TABLE["ELEVATED"]["npu"]}, GPU={BATCH_TABLE["ELEVATED"]["gpu"]})
  THROTTLED    → NPU only (GPU paused)
  CRITICAL     → Both paused

Examples:
  python hfo_p6_kraken_loop.py                    # 24/7 strange loop
  python hfo_p6_kraken_loop.py --single           # One cycle
  python hfo_p6_kraken_loop.py --dry-run --single # Dry run
  python hfo_p6_kraken_loop.py --interval 30      # Faster cycles
  python hfo_p6_kraken_loop.py --max-cycles 10    # Run 10 then stop
  python hfo_p6_kraken_loop.py --status           # Read the trail
  python hfo_p6_kraken_loop.py --status --json    # JSON status

The tentacles reach. The stigmergy coordinates.
Everything that dies feeds the knowledge graph.
""",
    )
    parser.add_argument("--single", action="store_true",
                        help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="No SSOT writes")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help=f"Seconds between cycles (default: {DEFAULT_INTERVAL})")
    parser.add_argument("--max-cycles", type=int, default=None,
                        help="Stop after N cycles")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"Ollama model for GPU enrichment (default: {DEFAULT_MODEL})")
    parser.add_argument("--health-every", type=int, default=HEALTH_EVERY_N,
                        help=f"Health snapshot every N cycles (default: {HEALTH_EVERY_N})")
    parser.add_argument("--status", action="store_true",
                        help="Print strange loop status and exit")
    parser.add_argument("--json", action="store_true",
                        help="JSON output (with --status)")

    args = parser.parse_args()

    # ── Status ──
    if args.status:
        print_status(args.json)
        return

    # ── Create the loop engine ──
    loop_engine = KrakenLoop(
        model=args.model,
        dry_run=args.dry_run,
        health_every=args.health_every,
    )

    # ── Signal handling ──
    def _handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. The tentacles retract.")
        loop_engine.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ── Single cycle ──
    if args.single:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(loop_engine._async_cycle())
        finally:
            loop.close()

        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            npu = report.get("npu", {})
            gpu = report.get("gpu", {})
            print()
            print(f"  {DAEMON_NAME} v{DAEMON_VERSION} — Single Cycle Report")
            print("  " + "=" * 58)
            print(f"  Cycle:      #{report['loop_cycle']}")
            print(f"  Pressure:   {report['pressure']}")
            print(f"  Model:      {report['model']}")
            print(f"  Duration:   {report.get('combined_duration_ms', 0):.0f}ms")
            print()
            print(f"  NPU TENTACLE (Embed + Discover):")
            print(f"    Re-embedded:   {npu.get('stale_reembedded', 0)} stale docs")
            print(f"    GPU-triggered: {npu.get('gpu_triggered_reembeds', 0)} re-embeds")
            print(f"    Clusters:      {len(npu.get('clusters_found', []))} found")
            print(f"    Orphans:       {len(npu.get('orphans_found', []))} found")
            print(f"    Duration:      {npu.get('elapsed_ms', 0):.0f}ms")
            cov = npu.get("coverage", {})
            if cov:
                print(f"    Coverage:      {cov.get('total_embedded', 0)}/{cov.get('total_docs', 0)} "
                      f"({cov.get('coverage_pct', 0):.1f}%)")
            print()
            print(f"  GPU TENTACLE (Enrich + Shape):")
            print(f"    Summaries:     {gpu.get('summaries_generated', 0)}")
            print(f"    KG triples:    {gpu.get('kg_triples_extracted', 0)}")
            print(f"    Quality fixes: {gpu.get('quality_fixes', 0)}")
            print(f"    Docs enriched: {len(gpu.get('enriched_doc_ids', []))}")
            print(f"    Duration:      {gpu.get('elapsed_ms', 0):.0f}ms")
            if report.get("errors"):
                print(f"\n  Errors:      {report['errors']}")
            print()
            print("  The tentacles reached. The stigmergy coordinates.")
            print("  Everything that dies feeds the knowledge graph.")
        return

    # ── Infinite loop ──
    asyncio.run(daemon_loop(loop_engine, interval=args.interval, max_cycles=args.max_cycles))


if __name__ == "__main__":
    main()
