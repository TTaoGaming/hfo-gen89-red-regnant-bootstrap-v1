#!/usr/bin/env python3
"""
hfo_p6_kraken_daemon.py — P6 Kraken Keeper 24/7 SSOT Enrichment Daemon
========================================================================
v1.0 | Gen89 | Port: P6 ASSIMILATE | Commander: Kraken Keeper
Powerword: ASSIMILATE | Spell: CLONE | School: Necromancy
Title: Devourer of Depths and Dreams | Trigram: ☶ Gen (Mountain)

PURPOSE:
    Continuous background daemon that incrementally improves the SSOT
    through safe, additive enrichment powered by local Ollama models.

    This is the P6 ASSIMILATE daemon — the knowledge metabolism of HFO.
    It devours the corpus, extracts insights, and stores them back.
    Every cycle, the SSOT gets a little richer. Stigmergic accumulation.

ENRICHMENT TASKS (5 concurrent asyncio loops):
    T1 — BLUF Generation    (every 120s)  Summarize docs lacking BLUFs
    T2 — Port Classification (every 180s)  Assign octree ports to unclassified docs
    T3 — Doc Type Classify   (every 300s)  Assign doc_type to untyped docs
    T4 — Lineage Mining      (every 600s)  Discover cross-references between docs
    T5 — Heartbeat + Stats   (every  60s)  Daemon alive signal + progress report

SAFETY GUARANTEES:
    - ADDITIVE ONLY: Never deletes, never overwrites existing non-null fields
    - BLUF: Only touches docs where bluf IS NULL OR bluf = '---'
    - Port: Only touches docs where port IS NULL
    - Doc_type: Only touches docs where doc_type IS NULL
    - Lineage: Only INSERTs new edges, never DELETEs
    - Every write is logged as a CloudEvent to stigmergy_events
    - Dry-run mode available for testing

PROVIDERS (dual-engine, Ollama primary):
    - Ollama gemma3:4b       — all enrichment (fastest local, no think-tags)
    - Gemini (optional)      — grounded web research when quota allows

USAGE:
    # Start continuous daemon (24/7 mode)
    python hfo_p6_kraken_daemon.py

    # Run one enrichment cycle then exit
    python hfo_p6_kraken_daemon.py --once

    # Dry run (detect targets but don't write)
    python hfo_p6_kraken_daemon.py --dry-run

    # Specific tasks only
    python hfo_p6_kraken_daemon.py --tasks bluf,port,doctype

    # Custom model (any Ollama model)
    python hfo_p6_kraken_daemon.py --model qwen3:8b

    # Custom intervals (seconds)
    python hfo_p6_kraken_daemon.py --bluf-interval 120 --port-interval 180

    # Show status / progress
    python hfo_p6_kraken_daemon.py --status

Medallion: bronze
Port: P6 ASSIMILATE
Pointer key: daemon.p6_kraken
"""

from __future__ import annotations

import argparse
import asyncio
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

import httpx

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
POINTERS_FILE = HFO_ROOT / "hfo_gen89_pointers_blessed.json"


def _load_pointers() -> dict:
    if not POINTERS_FILE.exists():
        return {}
    with open(POINTERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("pointers", data)


def resolve_pointer(key: str) -> Path:
    pointers = _load_pointers()
    if key not in pointers:
        raise KeyError(f"Pointer '{key}' not found")
    entry = pointers[key]
    rel_path = entry["path"] if isinstance(entry, dict) else entry
    return HFO_ROOT / rel_path


# ── Resolve critical paths ──
try:
    SSOT_DB = resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"

GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
P6_MODEL = os.environ.get("P6_OLLAMA_MODEL", "gemma3:4b")
P6_SOURCE = f"hfo_p6_kraken_daemon_gen{GEN}"
STATE_FILE = HFO_ROOT / ".hfo_p6_kraken_state.json"

# ═══════════════════════════════════════════════════════════════
# KRAKEN KEEPER IDENTITY
# ═══════════════════════════════════════════════════════════════

KRAKEN_IDENTITY = {
    "port": "P6",
    "powerword": "ASSIMILATE",
    "commander": "Kraken Keeper",
    "title": "Devourer of Depths and Dreams",
    "spell": "CLONE",
    "spell_school": "Necromancy",
    "trigram": "☶ Gen (Mountain)",
    "galois_pair": "P1 BRIDGE (Web Weaver)",
    "prey8_gate": "PERCEIVE (paired with P0 OBSERVE)",
    "core_thesis": "Depths ARE dreams. Everything that dies feeds the knowledge graph.",
}

# Octree port definitions for classification
OCTREE_PORTS = {
    "P0": {"label": "OBSERVE", "domain": "Sensing, monitoring, observation, perception, awareness, reconnaissance, telemetry, metrics"},
    "P1": {"label": "BRIDGE", "domain": "Data fabric, integration, APIs, schemas, contracts, binding, shared protocols, interoperability"},
    "P2": {"label": "SHAPE", "domain": "Creation, code generation, modeling, design, architecture, construction, building, specification"},
    "P3": {"label": "INJECT", "domain": "Delivery, deployment, injection, distribution, publishing, dispatch, payload, transport"},
    "P4": {"label": "DISRUPT", "domain": "Red team, adversarial, testing, mutation, breaking, challenging, probing, attacking, auditing"},
    "P5": {"label": "IMMUNIZE", "domain": "Defense, security, governance, validation, gates, integrity, resilience, hardening, compliance"},
    "P6": {"label": "ASSIMILATE", "domain": "Knowledge, learning, memory, extraction, archiving, cataloging, indexing, post-action review"},
    "P7": {"label": "NAVIGATE", "domain": "Orchestration, steering, C2, strategy, routing, planning, prioritization, meta-coordination"},
}

# Document type taxonomy
DOC_TYPES = [
    "explanation", "reference", "how_to", "tutorial",
    "recipe_card", "template", "portable_artifact",
    "doctrine", "forge_report", "concordance", "catalog",
    "incident_report", "config", "project_spec",
]


# ═══════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_readonly() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_readwrite() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
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

def ollama_generate(
    prompt: str,
    system: str = "",
    model: str = P6_MODEL,
    timeout: float = 180,
    temperature: float = 0.3,
    num_predict: int = 1024,
) -> str:
    """Call Ollama generate API. Returns response text or empty on error."""
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "temperature": temperature,
        },
    }
    if system:
        payload["system"] = system

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("response", "").strip()
    except Exception as e:
        print(f"  [OLLAMA ERROR] {e}", file=sys.stderr)
        return ""


def ollama_available() -> bool:
    """Check if Ollama is reachable."""
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# P6 KRAKEN KEEPER — Core Enrichment Engine
# ═══════════════════════════════════════════════════════════════

KRAKEN_SYSTEM_PROMPT = f"""You are the Kraken Keeper, commander of Port 6 (ASSIMILATE) in the HFO Octree.
Your title: Devourer of Depths and Dreams. Your spell: CLONE (Necromancy).
You devour knowledge from documents and extract their essence.

RULES:
- Be concise and precise. No filler. No markdown formatting.
- Answer ONLY what is asked. No preamble, no explanation of your process.
- When generating a BLUF (Bottom Line Up Front), write 1-3 sentences capturing the document's core value proposition.
- When classifying a port, respond ONLY with the port ID (P0, P1, P2, P3, P4, P5, P6, P7).
- When classifying a doc type, respond ONLY with the type name.
- Strip any <think> tags or reasoning traces from your output.
"""


def _strip_think_tags(text: str) -> str:
    """Strip <think>...</think> blocks from deepseek-r1 output."""
    import re
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


class KrakenKeeper:
    """The P6 ASSIMILATE daemon — incremental SSOT enrichment via Ollama."""

    def __init__(self, dry_run: bool = False, model: str = P6_MODEL,
                 batch_size: int = 3):
        self.dry_run = dry_run
        self.model = model
        self.batch_size = batch_size
        self._running = True

        # Enrichment counters
        self.stats = {
            "cycles": 0,
            "blufs_generated": 0,
            "ports_classified": 0,
            "doctypes_classified": 0,
            "lineage_edges_added": 0,
            "errors": 0,
            "ollama_calls": 0,
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

    def stop(self):
        self._running = False

    # ── T1: BLUF GENERATION ──────────────────────────────────

    async def enrich_blufs(self) -> dict:
        """Find docs without BLUFs, generate them via Ollama."""
        results = {"enriched": 0, "skipped": 0, "errors": 0, "docs": []}

        try:
            conn = get_db_readwrite()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            # Find docs missing BLUFs
            cursor = conn.execute(
                """SELECT id, title, SUBSTR(content, 1, 2000) as content_preview,
                          source, word_count
                   FROM documents
                   WHERE (bluf IS NULL OR bluf = '---')
                   ORDER BY word_count DESC
                   LIMIT ?""",
                (self.batch_size,),
            )
            rows = cursor.fetchall()

            for row in rows:
                if not self._running:
                    break

                doc_id = row["id"]
                title = row["title"] or "(untitled)"
                content = row["content_preview"] or ""
                source = row["source"] or "unknown"

                if not content or len(content) < 50:
                    results["skipped"] += 1
                    continue

                # Generate BLUF via Ollama
                prompt = (
                    f"Write a BLUF (Bottom Line Up Front) summary for this document.\n"
                    f"Title: {title}\nSource: {source}\n\n"
                    f"Content (first 2000 chars):\n{content}\n\n"
                    f"BLUF (1-3 sentences, no quotes, no markdown):"
                )

                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(p, system=KRAKEN_SYSTEM_PROMPT, model=self.model),
                )
                self.stats["ollama_calls"] += 1

                bluf = _strip_think_tags(raw_response)
                if not bluf or len(bluf) < 10:
                    results["errors"] += 1
                    continue

                # Truncate excessively long BLUFs
                if len(bluf) > 500:
                    bluf = bluf[:497] + "..."

                if not self.dry_run:
                    conn.execute(
                        "UPDATE documents SET bluf = ? WHERE id = ? AND (bluf IS NULL OR bluf = '---')",
                        (bluf, doc_id),
                    )
                    write_stigmergy_event(
                        conn, "hfo.gen89.kraken.bluf_enriched",
                        f"BLUF:doc_{doc_id}",
                        {
                            "doc_id": doc_id,
                            "title": title[:100],
                            "source": source,
                            "bluf_length": len(bluf),
                            "bluf_preview": bluf[:200],
                            "model": self.model,
                            "task": "T1_BLUF_GENERATION",
                        },
                    )

                results["enriched"] += 1
                results["docs"].append({"id": doc_id, "title": title[:60]})
                self.stats["blufs_generated"] += 1
                print(f"  [BLUF] doc {doc_id}: {title[:50]}... ({len(bluf)} chars)")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T1 ERROR] {e}", file=sys.stderr)
        finally:
            conn.close()

        return results

    # ── T2: PORT CLASSIFICATION ──────────────────────────────

    async def classify_ports(self) -> dict:
        """Find docs without port assignment, classify via Ollama."""
        results = {"classified": 0, "skipped": 0, "errors": 0, "docs": []}

        try:
            conn = get_db_readwrite()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            cursor = conn.execute(
                """SELECT id, title, bluf, SUBSTR(content, 1, 1500) as content_preview,
                          source, tags
                   FROM documents
                   WHERE port IS NULL
                   ORDER BY RANDOM()
                   LIMIT ?""",
                (self.batch_size,),
            )
            rows = cursor.fetchall()

            port_descriptions = "\n".join(
                f"  {pid}: {info['label']} — {info['domain']}"
                for pid, info in OCTREE_PORTS.items()
            )

            for row in rows:
                if not self._running:
                    break

                doc_id = row["id"]
                title = row["title"] or "(untitled)"
                bluf = row["bluf"] or ""
                content = row["content_preview"] or ""
                source = row["source"] or "unknown"
                tags = row["tags"] or ""

                context = f"Title: {title}\nBLUF: {bluf}\nSource: {source}\nTags: {tags}"
                if bluf and len(bluf) > 20:
                    # Use BLUF if available, cheaper than full content
                    text_for_classification = context
                else:
                    text_for_classification = f"{context}\nContent preview: {content[:800]}"

                prompt = (
                    f"Classify this document into exactly ONE octree port.\n\n"
                    f"Port definitions:\n{port_descriptions}\n\n"
                    f"Document:\n{text_for_classification}\n\n"
                    f"Reply with ONLY the port ID (e.g., P4). Nothing else:"
                )

                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(
                        p, system=KRAKEN_SYSTEM_PROMPT, model=self.model,
                        num_predict=64,
                    ),
                )
                self.stats["ollama_calls"] += 1

                response = _strip_think_tags(raw_response).upper().strip()

                # Extract port ID — look for P0-P7 pattern
                import re
                port_match = re.search(r"P[0-7]", response)
                if not port_match:
                    results["errors"] += 1
                    continue

                port = port_match.group(0)

                if not self.dry_run:
                    conn.execute(
                        "UPDATE documents SET port = ? WHERE id = ? AND port IS NULL",
                        (port, doc_id),
                    )
                    write_stigmergy_event(
                        conn, "hfo.gen89.kraken.port_classified",
                        f"PORT:{port}:doc_{doc_id}",
                        {
                            "doc_id": doc_id,
                            "title": title[:100],
                            "assigned_port": port,
                            "port_label": OCTREE_PORTS[port]["label"],
                            "source": source,
                            "model": self.model,
                            "task": "T2_PORT_CLASSIFICATION",
                        },
                    )

                results["classified"] += 1
                results["docs"].append({"id": doc_id, "port": port, "title": title[:60]})
                self.stats["ports_classified"] += 1
                print(f"  [PORT] doc {doc_id} → {port} {OCTREE_PORTS[port]['label']}: {title[:50]}...")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T2 ERROR] {e}", file=sys.stderr)
        finally:
            conn.close()

        return results

    # ── T3: DOC TYPE CLASSIFICATION ──────────────────────────

    async def classify_doctypes(self) -> dict:
        """Find docs without doc_type, classify via Ollama."""
        results = {"classified": 0, "skipped": 0, "errors": 0, "docs": []}

        try:
            conn = get_db_readwrite()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            cursor = conn.execute(
                """SELECT id, title, bluf, SUBSTR(content, 1, 1000) as content_preview,
                          source, tags
                   FROM documents
                   WHERE doc_type IS NULL
                   ORDER BY id
                   LIMIT ?""",
                (self.batch_size,),
            )
            rows = cursor.fetchall()

            types_list = ", ".join(DOC_TYPES)

            for row in rows:
                if not self._running:
                    break

                doc_id = row["id"]
                title = row["title"] or "(untitled)"
                bluf = row["bluf"] or ""
                content = row["content_preview"] or ""
                source = row["source"] or "unknown"

                prompt = (
                    f"Classify this document into exactly ONE type.\n\n"
                    f"Valid types: {types_list}\n\n"
                    f"Document:\n  Title: {title}\n  BLUF: {bluf}\n"
                    f"  Source: {source}\n  Content: {content[:500]}\n\n"
                    f"Reply with ONLY the type name (e.g., explanation). Nothing else:"
                )

                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(
                        p, system=KRAKEN_SYSTEM_PROMPT, model=self.model,
                        num_predict=64,
                    ),
                )
                self.stats["ollama_calls"] += 1

                response = _strip_think_tags(raw_response).lower().strip()

                # Match to known types
                matched_type = None
                for dt in DOC_TYPES:
                    if dt in response:
                        matched_type = dt
                        break

                if not matched_type:
                    results["errors"] += 1
                    continue

                if not self.dry_run:
                    conn.execute(
                        "UPDATE documents SET doc_type = ? WHERE id = ? AND doc_type IS NULL",
                        (matched_type, doc_id),
                    )
                    write_stigmergy_event(
                        conn, "hfo.gen89.kraken.doctype_classified",
                        f"DOCTYPE:{matched_type}:doc_{doc_id}",
                        {
                            "doc_id": doc_id,
                            "title": title[:100],
                            "assigned_type": matched_type,
                            "source": source,
                            "model": self.model,
                            "task": "T3_DOCTYPE_CLASSIFICATION",
                        },
                    )

                results["classified"] += 1
                results["docs"].append({"id": doc_id, "type": matched_type})
                self.stats["doctypes_classified"] += 1
                print(f"  [TYPE] doc {doc_id} → {matched_type}: {title[:50]}...")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T3 ERROR] {e}", file=sys.stderr)
        finally:
            conn.close()

        return results

    # ── T4: LINEAGE CROSS-REFERENCE MINING ───────────────────

    async def mine_lineage(self) -> dict:
        """Discover cross-references between documents, populate lineage table."""
        results = {"edges_added": 0, "docs_scanned": 0, "errors": 0}

        try:
            conn = get_db_readwrite()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            # Pick a random doc with content
            cursor = conn.execute(
                """SELECT id, title, SUBSTR(content, 1, 3000) as content_preview,
                          content_hash, source, port
                   FROM documents
                   WHERE word_count > 100
                   ORDER BY RANDOM()
                   LIMIT ?""",
                (self.batch_size,),
            )
            rows = cursor.fetchall()

            for row in rows:
                if not self._running:
                    break

                doc_id = row["id"]
                title = row["title"] or "(untitled)"
                content = row["content_preview"] or ""
                doc_hash = row["content_hash"] or ""
                source = row["source"] or "unknown"

                # Ask Ollama to extract document references
                prompt = (
                    f"This document is from the HFO knowledge system (Gen89, ~9860 docs).\n"
                    f"Extract any EXPLICIT references to other documents, concepts, or topics.\n\n"
                    f"Title: {title}\nSource: {source}\n"
                    f"Content:\n{content}\n\n"
                    f"List up to 5 referenced topics/concepts, one per line.\n"
                    f"Format: TOPIC: <topic name>\n"
                    f"If no references found, reply: NONE"
                )

                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(
                        p, system=KRAKEN_SYSTEM_PROMPT, model=self.model,
                        num_predict=512,
                    ),
                )
                self.stats["ollama_calls"] += 1

                response = _strip_think_tags(raw_response)
                results["docs_scanned"] += 1

                if "NONE" in response.upper() and len(response) < 20:
                    continue

                # Parse topics and attempt FTS match
                topics = []
                for line in response.split("\n"):
                    line = line.strip()
                    if line.upper().startswith("TOPIC:"):
                        topic = line[6:].strip().strip("-").strip()
                        if topic and len(topic) > 3:
                            topics.append(topic)

                for topic in topics[:5]:
                    # FTS search for matching documents
                    try:
                        # Sanitize topic for FTS5
                        safe_topic = " ".join(
                            w for w in topic.split()
                            if w.isalnum() or w.replace("-", "").isalnum()
                        )
                        if not safe_topic:
                            continue

                        target_cursor = conn.execute(
                            """SELECT id, content_hash FROM documents
                               WHERE id IN (
                                   SELECT rowid FROM documents_fts
                                   WHERE documents_fts MATCH ?
                               ) AND id != ?
                               LIMIT 1""",
                            (safe_topic, doc_id),
                        )
                        target = target_cursor.fetchone()

                        if target:
                            target_hash = target["content_hash"] or ""
                            # Check if edge already exists
                            existing = conn.execute(
                                """SELECT 1 FROM lineage
                                   WHERE doc_id = ? AND depends_on_hash = ?""",
                                (doc_id, target_hash),
                            ).fetchone()

                            if not existing and target_hash and not self.dry_run:
                                conn.execute(
                                    """INSERT INTO lineage (doc_id, depends_on_hash, relation)
                                       VALUES (?, ?, ?)""",
                                    (doc_id, target_hash, f"references:{topic[:100]}"),
                                )
                                results["edges_added"] += 1
                                self.stats["lineage_edges_added"] += 1

                    except sqlite3.OperationalError:
                        # FTS query syntax issue — skip
                        pass

                if results["edges_added"] > 0 and not self.dry_run:
                    conn.commit()
                    write_stigmergy_event(
                        conn, "hfo.gen89.kraken.lineage_mined",
                        f"LINEAGE:doc_{doc_id}",
                        {
                            "doc_id": doc_id,
                            "title": title[:100],
                            "topics_found": len(topics),
                            "edges_added": results["edges_added"],
                            "model": self.model,
                            "task": "T4_LINEAGE_MINING",
                        },
                    )
                    print(f"  [LINEAGE] doc {doc_id}: {results['edges_added']} new edges")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T4 ERROR] {e}", file=sys.stderr)
        finally:
            conn.close()

        return results

    # ── T5: HEARTBEAT + STATS ────────────────────────────────

    def get_enrichment_progress(self) -> dict:
        """Query current SSOT enrichment state."""
        try:
            conn = get_db_readonly()
            total = conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0]
            no_bluf_null = conn.execute("SELECT COUNT(1) FROM documents WHERE bluf IS NULL").fetchone()[0]
            no_bluf_dash = conn.execute("SELECT COUNT(1) FROM documents WHERE bluf = '---'").fetchone()[0]
            no_port = conn.execute("SELECT COUNT(1) FROM documents WHERE port IS NULL").fetchone()[0]
            no_doctype = conn.execute("SELECT COUNT(1) FROM documents WHERE doc_type IS NULL").fetchone()[0]
            lineage_count = conn.execute("SELECT COUNT(1) FROM lineage").fetchone()[0]
            events = conn.execute("SELECT COUNT(1) FROM stigmergy_events").fetchone()[0]
            kraken_events = conn.execute(
                "SELECT COUNT(1) FROM stigmergy_events WHERE event_type LIKE '%kraken%'"
            ).fetchone()[0]
            conn.close()
            return {
                "total_docs": total,
                "missing_bluf": no_bluf_null + no_bluf_dash,
                "missing_port": no_port,
                "missing_doctype": no_doctype,
                "lineage_edges": lineage_count,
                "total_events": events,
                "kraken_events": kraken_events,
                "enrichment_pct": {
                    "bluf": round(100 * (1 - (no_bluf_null + no_bluf_dash) / max(total, 1)), 1),
                    "port": round(100 * (1 - no_port / max(total, 1)), 1),
                    "doctype": round(100 * (1 - no_doctype / max(total, 1)), 1),
                },
            }
        except Exception as e:
            return {"error": str(e)}

    async def emit_heartbeat(self) -> dict:
        """Emit daemon heartbeat + enrichment progress."""
        progress = self.get_enrichment_progress()

        heartbeat = {
            "cycle": self.stats["cycles"],
            "identity": KRAKEN_IDENTITY,
            "model": self.model,
            "progress": progress,
            "daemon_stats": dict(self.stats),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if not self.dry_run:
            try:
                conn = get_db_readwrite()
                write_stigmergy_event(
                    conn, "hfo.gen89.kraken.heartbeat",
                    f"HEARTBEAT:cycle_{self.stats['cycles']}",
                    heartbeat,
                )
                conn.close()
            except Exception as e:
                print(f"  [HEARTBEAT ERROR] {e}", file=sys.stderr)

        return heartbeat


# ═══════════════════════════════════════════════════════════════
# ASYNC DAEMON LOOP
# ═══════════════════════════════════════════════════════════════

async def task_loop(
    name: str,
    coroutine_fn,
    interval: float,
    kraken: KrakenKeeper,
):
    """Run an enrichment task on a repeating interval."""
    while kraken._running:
        try:
            result = await coroutine_fn()
            if isinstance(result, dict) and result.get("errors", 0) > 0:
                print(f"  [{name}] completed with {result['errors']} errors", file=sys.stderr)
        except Exception as e:
            print(f"  [{name} CRASH] {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            kraken.stats["errors"] += 1

        # Sleep in small increments for responsive shutdown
        for _ in range(int(interval)):
            if not kraken._running:
                break
            await asyncio.sleep(1)


async def daemon_loop(
    kraken: KrakenKeeper,
    intervals: dict,
    enabled_tasks: set,
    single: bool = False,
):
    """Main daemon loop — runs all enabled tasks concurrently."""
    banner = f"""
  ╔═══════════════════════════════════════════════════════════╗
  ║  P6 KRAKEN KEEPER — Devourer of Depths and Dreams        ║
  ║  Port: P6 ASSIMILATE | Spell: CLONE (Necromancy)         ║
  ║  Model: {kraken.model:48s} ║
  ║  Mode: {'DRY RUN' if kraken.dry_run else '24/7 ENRICHMENT':48s} ║
  ╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)

    # Verify Ollama
    if not ollama_available():
        print("  [FATAL] Ollama not reachable at {OLLAMA_BASE}. Exiting.", file=sys.stderr)
        return

    print(f"  Ollama: ONLINE at {OLLAMA_BASE}")
    print(f"  Model:  {kraken.model}")
    print(f"  DB:     {SSOT_DB} ({SSOT_DB.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  Tasks:  {', '.join(sorted(enabled_tasks))}")
    print(f"  Batch:  {kraken.batch_size} docs per task cycle")
    print()

    # Initial progress report
    progress = kraken.get_enrichment_progress()
    if "error" not in progress:
        print(f"  Enrichment baseline:")
        print(f"    BLUFs:    {progress['enrichment_pct']['bluf']:.1f}% complete ({progress['missing_bluf']} remaining)")
        print(f"    Ports:    {progress['enrichment_pct']['port']:.1f}% complete ({progress['missing_port']} remaining)")
        print(f"    DocTypes: {progress['enrichment_pct']['doctype']:.1f}% complete ({progress['missing_doctype']} remaining)")
        print(f"    Lineage:  {progress['lineage_edges']} edges")
        print()

    # Log daemon start
    if not kraken.dry_run:
        try:
            conn = get_db_readwrite()
            write_stigmergy_event(
                conn, "hfo.gen89.kraken.start",
                "KRAKEN_START",
                {
                    "action": "daemon_start",
                    "model": kraken.model,
                    "batch_size": kraken.batch_size,
                    "enabled_tasks": sorted(enabled_tasks),
                    "intervals": intervals,
                    "dry_run": kraken.dry_run,
                    "initial_progress": progress,
                    "identity": KRAKEN_IDENTITY,
                },
            )
            conn.close()
        except Exception as e:
            print(f"  [WARN] Could not log start: {e}", file=sys.stderr)

    if single:
        # Run one cycle of each task
        kraken.stats["cycles"] = 1
        print("  === SINGLE CYCLE MODE ===\n")

        if "bluf" in enabled_tasks:
            print("  --- T1: BLUF Generation ---")
            r = await kraken.enrich_blufs()
            print(f"    Enriched: {r['enriched']}, Errors: {r['errors']}\n")

        if "port" in enabled_tasks:
            print("  --- T2: Port Classification ---")
            r = await kraken.classify_ports()
            print(f"    Classified: {r['classified']}, Errors: {r['errors']}\n")

        if "doctype" in enabled_tasks:
            print("  --- T3: Doc Type Classification ---")
            r = await kraken.classify_doctypes()
            print(f"    Classified: {r['classified']}, Errors: {r['errors']}\n")

        if "lineage" in enabled_tasks:
            print("  --- T4: Lineage Mining ---")
            r = await kraken.mine_lineage()
            print(f"    Edges added: {r['edges_added']}, Scanned: {r['docs_scanned']}\n")

        hb = await kraken.emit_heartbeat()
        progress = hb.get("progress", {})
        print("  --- Final Progress ---")
        if "enrichment_pct" in progress:
            print(f"    BLUFs:    {progress['enrichment_pct']['bluf']:.1f}%")
            print(f"    Ports:    {progress['enrichment_pct']['port']:.1f}%")
            print(f"    DocTypes: {progress['enrichment_pct']['doctype']:.1f}%")
            print(f"    Lineage:  {progress.get('lineage_edges', 0)} edges")
        print(f"    Ollama calls: {kraken.stats['ollama_calls']}")
        print(f"\n  Depths ARE dreams. The Kraken feeds.\n")
        return

    # Build concurrent task list
    tasks = []
    if "bluf" in enabled_tasks:
        tasks.append(task_loop("T1:BLUF", kraken.enrich_blufs, intervals.get("bluf", 120), kraken))
    if "port" in enabled_tasks:
        tasks.append(task_loop("T2:PORT", kraken.classify_ports, intervals.get("port", 180), kraken))
    if "doctype" in enabled_tasks:
        tasks.append(task_loop("T3:TYPE", kraken.classify_doctypes, intervals.get("doctype", 300), kraken))
    if "lineage" in enabled_tasks:
        tasks.append(task_loop("T4:LINEAGE", kraken.mine_lineage, intervals.get("lineage", 600), kraken))
    # Heartbeat always runs
    tasks.append(task_loop("T5:HEARTBEAT", kraken.emit_heartbeat, intervals.get("heartbeat", 60), kraken))

    print(f"  Starting {len(tasks)} concurrent tasks... (Ctrl+C to stop)\n")

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        # Log daemon stop
        if not kraken.dry_run:
            try:
                conn = get_db_readwrite()
                write_stigmergy_event(
                    conn, "hfo.gen89.kraken.stop",
                    "KRAKEN_STOP",
                    {
                        "action": "daemon_stop",
                        "final_stats": dict(kraken.stats),
                        "final_progress": kraken.get_enrichment_progress(),
                    },
                )
                conn.close()
            except Exception:
                pass

        # Save state
        _save_state(kraken)
        print("\n  Kraken Keeper stopped. The depths remember.\n")


def _save_state(kraken: KrakenKeeper):
    """Persist daemon state to disk."""
    state = {
        "stats": dict(kraken.stats),
        "model": kraken.model,
        "progress": kraken.get_enrichment_progress(),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P6 KRAKEN KEEPER — Devourer of Depths and Dreams (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hfo_p6_kraken_daemon.py                     # 24/7 mode
  python hfo_p6_kraken_daemon.py --once              # Single cycle
  python hfo_p6_kraken_daemon.py --dry-run --once    # Dry run
  python hfo_p6_kraken_daemon.py --tasks bluf,port   # Specific tasks
  python hfo_p6_kraken_daemon.py --model qwen3:8b    # Different model
  python hfo_p6_kraken_daemon.py --status             # Show progress
""",
    )
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="No writes, just show targets")
    parser.add_argument("--tasks", type=str, default="bluf,port,doctype,lineage",
                        help="Comma-separated tasks: bluf,port,doctype,lineage")
    parser.add_argument("--model", type=str, default=P6_MODEL, help=f"Ollama model (default: {P6_MODEL})")
    parser.add_argument("--batch-size", type=int, default=3, help="Docs per task cycle (default: 3)")
    parser.add_argument("--bluf-interval", type=float, default=120, help="BLUF cycle interval (seconds)")
    parser.add_argument("--port-interval", type=float, default=180, help="Port cycle interval (seconds)")
    parser.add_argument("--doctype-interval", type=float, default=300, help="DocType cycle interval (seconds)")
    parser.add_argument("--lineage-interval", type=float, default=600, help="Lineage cycle interval (seconds)")
    parser.add_argument("--status", action="store_true", help="Show enrichment progress and exit")
    parser.add_argument("--json", action="store_true", help="Output in JSON")

    args = parser.parse_args()

    if args.status:
        print("P6 KRAKEN KEEPER — Enrichment Status")
        print("=" * 50)
        print(f"  SSOT:  {SSOT_DB}")
        print(f"  Model: {args.model}")
        print(f"  State: {STATE_FILE}")
        print()

        kraken = KrakenKeeper(model=args.model)
        progress = kraken.get_enrichment_progress()

        if args.json:
            # Load saved state too
            saved = {}
            if STATE_FILE.exists():
                with open(STATE_FILE, "r") as f:
                    saved = json.load(f)
            print(json.dumps({"progress": progress, "saved_state": saved}, indent=2))
            return

        if "error" in progress:
            print(f"  ERROR: {progress['error']}")
            return

        print(f"  Documents:  {progress['total_docs']:,}")
        print(f"  Events:     {progress['total_events']:,} ({progress['kraken_events']} from Kraken)")
        print(f"  Lineage:    {progress['lineage_edges']} edges")
        print()
        print(f"  Enrichment Coverage:")
        print(f"    BLUFs:    {progress['enrichment_pct']['bluf']:5.1f}%  ({progress['missing_bluf']:,} remaining)")
        print(f"    Ports:    {progress['enrichment_pct']['port']:5.1f}%  ({progress['missing_port']:,} remaining)")
        print(f"    DocTypes: {progress['enrichment_pct']['doctype']:5.1f}%  ({progress['missing_doctype']:,} remaining)")
        print()

        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)
            print(f"  Last Run:")
            stats = saved.get("stats", {})
            print(f"    BLUFs generated:  {stats.get('blufs_generated', 0)}")
            print(f"    Ports classified: {stats.get('ports_classified', 0)}")
            print(f"    Types classified: {stats.get('doctypes_classified', 0)}")
            print(f"    Lineage edges:    {stats.get('lineage_edges_added', 0)}")
            print(f"    Ollama calls:     {stats.get('ollama_calls', 0)}")
            print(f"    Saved at:         {saved.get('saved_at', '?')}")
        else:
            print("  No previous state found. Daemon has not been run yet.")

        print(f"\n  Depths ARE dreams. The Kraken feeds.")
        return

    # Build daemon
    kraken = KrakenKeeper(
        dry_run=args.dry_run,
        model=args.model,
        batch_size=args.batch_size,
    )

    enabled_tasks = set(args.tasks.split(","))
    intervals = {
        "bluf": args.bluf_interval,
        "port": args.port_interval,
        "doctype": args.doctype_interval,
        "lineage": args.lineage_interval,
        "heartbeat": 60,
    }

    # Signal handling
    def handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. Stopping Kraken Keeper...")
        kraken.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    asyncio.run(daemon_loop(kraken, intervals, enabled_tasks, single=args.once))


if __name__ == "__main__":
    main()
