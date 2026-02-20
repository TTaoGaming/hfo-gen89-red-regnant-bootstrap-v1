#!/usr/bin/env python3
"""
hfo_p6_devourer_daemon.py — P6 Kraken Keeper 6D Knowledge Extraction Daemon
=============================================================================
v1.0 | Gen89 | Port: P6 ASSIMILATE | Commander: Kraken Keeper
Powerword: ASSIMILATE | Spell: CLONE | School: Necromancy
Title: Devourer of Depths and Dreams | Trigram: ☱ Dui (Lake)

PURPOSE:
    Autonomous daemon implementing the Devourer's 6D Pipeline (SSOT Doc 21).
    Consumes idle GPU/NPU/API resources to extract knowledge from the SSOT
    and produce structured diataxis artifacts + stigmergy breadcrumbs.

    "What was consumed becomes vision. Depths ARE dreams. Memory IS digestion."

    Every cycle:
      1. READ stigmergy from ALL 8 ports (P0-P7) — what happened recently?
      2. FIND unenriched/underserved documents in SSOT
      3. RUN the 6D pipeline on each target:
           D0 DIRECT → D1 DISCOVER → D2 DECODE → D3 DEFINE → D4 DEMONSTRATE → D5 DISSEMINATE
      4. WRITE results back to SSOT (enriched fields + stigmergy events)
      5. EMIT a devourer pulse event for other daemons to read

    The outputs are NOT code. The outputs are KNOWLEDGE:
      - Enriched SSOT fields (bluf, tags, port, doc_type)
      - Gold diataxis-style summaries stored in metadata_json
      - Stigmergy events that other daemons consume
      - Cross-reference discoveries for the lineage table

THE RESOURCE PHILOSOPHY:
    "Unused free API/hardware/GPU/NPU is wasted resource."
    - GPU idle? Devourer runs Ollama enrichment
    - NPU idle? Re-embed stale documents
    - Gemini quota unused? Run grounded research
    - RAM available? Load larger context windows
    - CPU available? Run quality audits

    Like Google's RAM policy: if it's free and not reserved for
    something specific, the Devourer claims it.

STRANGE LOOP INTEGRATION:
    The Devourer reads output from:
      - Singer (P4) strife/splendor events → targets for adversarial review
      - Dancer (P5) death/dawn events → purge candidates + protection targets
      - Enrichment (P7) BLUF/port events → already-enriched docs to skip
      - Kraken Loop (P6) NPU discoveries → cluster insights to expand
      - Kraken Swarm (P6) worker events → knowledge graph edges to weave
      - Summoner (P7) foresight events → strategic priorities to follow
      - Tremorsense (P7) uptime events → resource availability windows

    And writes output that ALL ports can consume:
      - devourer.discovery → new knowledge found (P0 OBSERVE reads this)
      - devourer.enrichment → fields enriched (P6 loop reads this)
      - devourer.pulse → cycle heartbeat (P7 scheduler reads this)
      - devourer.diataxis → structured knowledge (ALL ports read this)

USAGE:
    python hfo_p6_devourer_daemon.py                    # 24/7 daemon
    python hfo_p6_devourer_daemon.py --single            # One cycle
    python hfo_p6_devourer_daemon.py --dry-run --single  # Preview
    python hfo_p6_devourer_daemon.py --status             # Current state
    python hfo_p6_devourer_daemon.py --status --json      # Machine-readable
    python hfo_p6_devourer_daemon.py --interval 120       # Custom interval
    python hfo_p6_devourer_daemon.py --model qwen3:8b     # Custom model
    python hfo_p6_devourer_daemon.py --batch 5            # Docs per cycle

Medallion: bronze
Port: P6 ASSIMILATE
Pointer key: daemon.p6_devourer
"""

from __future__ import annotations

import argparse
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
from typing import Any, Optional

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION VIA PAL
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
BRONZE_RES = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources"
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))

# Load .env if available
try:
    from dotenv import load_dotenv
    env_path = HFO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass

# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS & IDENTITY
# ═══════════════════════════════════════════════════════════════

DAEMON_NAME = "P6 Devourer of Depths and Dreams"
DAEMON_VERSION = "1.0"
SOURCE_TAG = f"hfo_p6_devourer_gen{GEN}"
DEFAULT_MODEL = "deepseek-r1:8b"
DEFAULT_INTERVAL = 300  # 5 minutes between cycles
DEFAULT_BATCH = 3       # Documents per cycle

# 6D Pipeline stages
STAGES = ["D0_DIRECT", "D1_DISCOVER", "D2_DECODE", "D3_DEFINE", "D4_DEMONSTRATE", "D5_DISSEMINATE"]

# Event types
EVT_PULSE      = f"hfo.gen{GEN}.devourer.pulse"
EVT_DISCOVERY  = f"hfo.gen{GEN}.devourer.discovery"
EVT_ENRICHMENT = f"hfo.gen{GEN}.devourer.enrichment"
EVT_DIATAXIS   = f"hfo.gen{GEN}.devourer.diataxis"
EVT_ERROR      = f"hfo.gen{GEN}.devourer.error"

# Stigmergy event families to consume from other ports
CONSUME_EVENTS = [
    "hfo.gen89.p4.singer%",           # Singer strife/splendor
    "hfo.gen89.p5.dancer%",           # Dancer death/dawn
    "hfo.gen89.p7.enrichment%",       # P7 enrichment
    "hfo.gen89.kraken.npu%",          # Kraken NPU discoveries
    "hfo.gen89.kraken.gpu%",          # Kraken GPU enrichments
    "hfo.gen89.p7.summoner%",         # Summoner foresight
    "hfo.gen89.p7.tremorsense%",      # Resource availability
    "hfo.gen89.devourer%",            # Own previous output
]

DEVOURER_IDENTITY = {
    "port": "P6",
    "powerword": "ASSIMILATE",
    "commander": "Kraken Keeper",
    "title": "Devourer of Depths and Dreams",
    "spell": "CLONE (Necromancy)",
    "daemon": DAEMON_NAME,
    "version": DAEMON_VERSION,
    "pipeline": "6D: DIRECT → DISCOVER → DECODE → DEFINE → DEMONSTRATE → DISSEMINATE",
    "philosophy": "Unused resource is wasted resource. Everything feeds the knowledge graph.",
}

# Graceful shutdown
_SHUTDOWN = False

def _handle_signal(sig, frame):
    global _SHUTDOWN
    _SHUTDOWN = True

for _s in (signal.SIGINT, signal.SIGTERM):
    try:
        signal.signal(_s, _handle_signal)
    except (OSError, ValueError):
        pass


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE & CLOUDEVENT HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def get_db_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
) -> int:
    """Write a CloudEvent to stigmergy_events with content-hash dedup."""
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": SOURCE_TAG,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "phase": "CLOUDEVENT",
        "data": data,
    }
    payload = json.dumps(envelope, sort_keys=True)
    content_hash = hashlib.sha256(payload.encode()).hexdigest()
    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, SOURCE_TAG, payload, content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 3  OLLAMA CLIENT
# ═══════════════════════════════════════════════════════════════

def ollama_alive() -> bool:
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
    timeout: float = 120,
    temperature: float = 0.3,
    num_predict: int = 1024,
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
        with httpx.Client(timeout=timeout) as c:
            resp = c.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
            return ""
    except Exception:
        return ""

def ollama_loaded_models() -> list[str]:
    """Return list of models currently loaded in VRAM."""
    try:
        import httpx
        with httpx.Client(timeout=5) as c:
            resp = c.get(f"{OLLAMA_BASE}/api/ps")
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []

def ensure_model_loaded(model: str) -> bool:
    """Ensure a model is loaded by sending a minimal prompt."""
    loaded = ollama_loaded_models()
    if any(model in m for m in loaded):
        return True
    # Warm-load
    resp = ollama_generate("ping", model=model, num_predict=1, timeout=60)
    return bool(resp) or resp == ""


# ═══════════════════════════════════════════════════════════════
# § 4  STIGMERGY CONSUMER — Read traces from all ports
# ═══════════════════════════════════════════════════════════════

def read_swarm_stigmergy(hours: float = 1.0) -> dict[str, list[dict]]:
    """
    Read recent stigmergy events from ALL ports.
    Returns dict keyed by event family → list of event summaries.
    This is the Devourer's sensory input — it reads the whole hive.
    """
    results: dict[str, list[dict]] = {}
    try:
        conn = get_db_ro()
        for pattern in CONSUME_EVENTS:
            rows = conn.execute(
                """SELECT id, event_type, timestamp, subject,
                          substr(data_json, 1, 500) as data_preview
                   FROM stigmergy_events
                   WHERE event_type LIKE ?
                     AND timestamp >= datetime('now', ?)
                   ORDER BY timestamp DESC
                   LIMIT 20""",
                (pattern, f"-{int(hours * 60)} minutes"),
            ).fetchall()
            if rows:
                family = pattern.rstrip("%").rstrip(".")
                results[family] = [dict(r) for r in rows]
        conn.close()
    except Exception:
        pass
    return results


def summarize_swarm_state(stigmergy: dict[str, list[dict]]) -> str:
    """Produce a compact summary of recent swarm activity for LLM context."""
    if not stigmergy:
        return "No recent swarm activity detected."
    lines = ["Recent swarm activity (last hour):"]
    for family, events in stigmergy.items():
        lines.append(f"  {family}: {len(events)} events")
        for e in events[:3]:
            lines.append(f"    - [{e['timestamp'][:19]}] {e['subject']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 5  TARGET SELECTION — Find docs to devour
# ═══════════════════════════════════════════════════════════════

def find_targets(batch_size: int = DEFAULT_BATCH) -> list[dict]:
    """
    Find documents that need the Devourer's attention.

    Priority order (highest → lowest):
      1. Docs with NULL bluf (no summary at all)
      2. Docs with NULL port (unclassified)
      3. Docs with NULL doc_type (untyped)
      4. Docs with high word_count but minimal metadata
      5. Docs recently referenced by other daemons in stigmergy
    """
    targets = []
    try:
        conn = get_db_ro()

        # Priority 1: Missing BLUF (most impactful)
        if len(targets) < batch_size:
            rows = conn.execute(
                """SELECT id, title, source, port, doc_type, word_count,
                          substr(content, 1, 2000) as content_preview
                   FROM documents
                   WHERE (bluf IS NULL OR bluf = '' OR bluf = '---')
                     AND word_count > 50
                   ORDER BY word_count DESC
                   LIMIT ?""",
                (batch_size - len(targets),),
            ).fetchall()
            for r in rows:
                targets.append({**dict(r), "priority": "P1_MISSING_BLUF"})

        # Priority 2: Missing port
        if len(targets) < batch_size:
            rows = conn.execute(
                """SELECT id, title, source, port, doc_type, word_count,
                          substr(content, 1, 2000) as content_preview
                   FROM documents
                   WHERE port IS NULL
                     AND word_count > 50
                     AND id NOT IN ({})
                   ORDER BY word_count DESC
                   LIMIT ?""".format(",".join(str(t["id"]) for t in targets) or "0"),
                (batch_size - len(targets),),
            ).fetchall()
            for r in rows:
                targets.append({**dict(r), "priority": "P2_MISSING_PORT"})

        # Priority 3: Missing doc_type
        if len(targets) < batch_size:
            rows = conn.execute(
                """SELECT id, title, source, port, doc_type, word_count,
                          substr(content, 1, 2000) as content_preview
                   FROM documents
                   WHERE doc_type IS NULL
                     AND word_count > 50
                     AND id NOT IN ({})
                   ORDER BY word_count DESC
                   LIMIT ?""".format(",".join(str(t["id"]) for t in targets) or "0"),
                (batch_size - len(targets),),
            ).fetchall()
            for r in rows:
                targets.append({**dict(r), "priority": "P3_MISSING_DOCTYPE"})

        # Priority 4: High word count, minimal enrichment
        if len(targets) < batch_size:
            rows = conn.execute(
                """SELECT id, title, source, port, doc_type, word_count,
                          substr(content, 1, 2000) as content_preview
                   FROM documents
                   WHERE word_count > 500
                     AND (tags IS NULL OR tags = '')
                     AND id NOT IN ({})
                   ORDER BY word_count DESC
                   LIMIT ?""".format(",".join(str(t["id"]) for t in targets) or "0"),
                (batch_size - len(targets),),
            ).fetchall()
            for r in rows:
                targets.append({**dict(r), "priority": "P4_UNDERENRICHED"})

        conn.close()
    except Exception as e:
        print(f"  [ERROR] Target selection failed: {e}")
    return targets


# ═══════════════════════════════════════════════════════════════
# § 6  THE 6D PIPELINE — Each stage is an LLM task
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are P6 Kraken Keeper — the Devourer of Depths and Dreams.
You consume knowledge and produce structured understanding.
Your outputs are diataxis-style knowledge artifacts.
Be concise, precise, and structured. Output valid JSON when asked."""


def run_d0_direct(doc: dict, swarm_context: str, model: str) -> dict:
    """
    D0: DIRECT — Identify and bound the target.
    Produce a target brief: what is this, why does the swarm need it?
    """
    prompt = f"""Analyze this document and produce a JSON target brief.

DOCUMENT:
  Title: {doc.get('title', 'untitled')}
  Source: {doc.get('source', 'unknown')}
  Port: {doc.get('port', 'unassigned')}
  DocType: {doc.get('doc_type', 'untyped')}
  Words: {doc.get('word_count', 0)}

CONTENT PREVIEW:
{doc.get('content_preview', '')[:1500]}

SWARM CONTEXT:
{swarm_context[:500]}

Respond with ONLY a JSON object:
{{
  "what": "one sentence: what is this document about",
  "why": "why does the swarm need this knowledge",
  "port_suggestion": "P0-P7 or null if unsure",
  "doc_type_suggestion": "explanation|reference|how_to|tutorial|recipe_card|portable_artifact or null",
  "key_concepts": ["concept1", "concept2", "concept3"],
  "enrichment_priority": "HIGH|MEDIUM|LOW"
}}"""

    resp = ollama_generate(prompt, system=SYSTEM_PROMPT, model=model, num_predict=512)
    try:
        # Extract JSON from response
        start = resp.find("{")
        end = resp.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(resp[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {"what": resp[:200], "why": "parse_error", "enrichment_priority": "LOW"}


def run_d1_discover(doc: dict, brief: dict, model: str) -> dict:
    """
    D1: DISCOVER — Deep-read the target, produce understanding.
    Output: A BLUF (Bottom Line Up Front) summary.
    """
    prompt = f"""You are reading a document to produce a BLUF (Bottom Line Up Front) summary.

TARGET BRIEF: {json.dumps(brief, indent=2)[:500]}

DOCUMENT TITLE: {doc.get('title', 'untitled')}
CONTENT:
{doc.get('content_preview', '')[:1800]}

Write a 1-3 sentence BLUF that captures the essential knowledge.
A good BLUF answers: What is this? Why does it matter? What's the key insight?
Respond with ONLY the BLUF text, no formatting."""

    bluf = ollama_generate(prompt, system=SYSTEM_PROMPT, model=model, num_predict=256)
    return {"bluf": bluf.strip() if bluf else ""}


def run_d2_decode(doc: dict, brief: dict, model: str) -> dict:
    """
    D2: DECODE — Extract typed contracts, tags, classification.
    Output: Tags, port assignment, doc type.
    """
    prompt = f"""Classify this document for the HFO Octree knowledge system.

TARGET BRIEF: {json.dumps(brief, indent=2)[:400]}

DOCUMENT TITLE: {doc.get('title', 'untitled')}
Current port: {doc.get('port', 'null')}
Current doc_type: {doc.get('doc_type', 'null')}

The 8 OCTREE ports:
  P0 OBSERVE — sensing, perception, monitoring
  P1 BRIDGE — shared data, cross-references, integration
  P2 SHAPE — creation, models, generation, code
  P3 INJECT — payload delivery, deployment, injection
  P4 DISRUPT — red team, adversarial testing, probing
  P5 IMMUNIZE — blue team, testing, gates, defense
  P6 ASSIMILATE — learning, memory, knowledge, documentation
  P7 NAVIGATE — steering, C2, orchestration, architecture

Doc types: explanation, reference, how_to, tutorial, recipe_card, portable_artifact, doctrine, forge_report

CONTENT PREVIEW:
{doc.get('content_preview', '')[:1200]}

Respond with ONLY a JSON object:
{{
  "port": "P0-P7",
  "doc_type": "one of the types above",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "cross_references": ["related topic 1", "related topic 2"]
}}"""

    resp = ollama_generate(prompt, system=SYSTEM_PROMPT, model=model, num_predict=512)
    try:
        start = resp.find("{")
        end = resp.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(resp[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


def run_d3_define(doc: dict, brief: dict, model: str) -> dict:
    """
    D3: DEFINE — Produce actionable insights / key takeaways.
    Output: Structured knowledge extraction.
    """
    prompt = f"""Extract the key knowledge from this document as structured insights.

DOCUMENT TITLE: {doc.get('title', 'untitled')}
BRIEF: {brief.get('what', '')}

CONTENT:
{doc.get('content_preview', '')[:1500]}

Respond with ONLY a JSON object:
{{
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "actionable_items": ["action 1", "action 2"],
  "depends_on": ["prerequisite concept or doc"],
  "enables": ["downstream concept or capability"]
}}"""

    resp = ollama_generate(prompt, system=SYSTEM_PROMPT, model=model, num_predict=512)
    try:
        start = resp.find("{")
        end = resp.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(resp[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return {"key_insights": [], "actionable_items": []}


def run_d5_disseminate(
    conn: sqlite3.Connection,
    doc: dict,
    brief: dict,
    discover: dict,
    decode: dict,
    define: dict,
    dry_run: bool = False,
) -> dict:
    """
    D5: DISSEMINATE — Persist enrichment back to SSOT and emit stigmergy.
    This is where the Devourer writes back to the hive.
    """
    doc_id = doc["id"]
    updates = {}
    
    # Update BLUF if missing and we generated one
    bluf = discover.get("bluf", "")
    if bluf and (not doc.get("bluf") or doc.get("bluf") in ("", "---")):
        updates["bluf"] = bluf

    # Update port if missing and we have a suggestion
    port = decode.get("port") or brief.get("port_suggestion")
    if port and not doc.get("port"):
        # Validate port format
        if port in [f"P{i}" for i in range(8)]:
            updates["port"] = port

    # Update doc_type if missing
    doc_type = decode.get("doc_type") or brief.get("doc_type_suggestion")
    if doc_type and not doc.get("doc_type"):
        updates["doc_type"] = doc_type

    # Update tags if empty
    tags = decode.get("tags", [])
    if tags and (not doc.get("tags") or doc.get("tags") == ""):
        updates["tags"] = ",".join(str(t) for t in tags[:10])

    if dry_run:
        return {"doc_id": doc_id, "dry_run": True, "would_update": updates}

    if not updates:
        return {"doc_id": doc_id, "status": "NO_UPDATES_NEEDED"}

    # Write updates to SSOT
    try:
        set_clauses = []
        params = []
        for col, val in updates.items():
            set_clauses.append(f"{col} = ?")
            params.append(val)
        params.append(doc_id)

        conn.execute(
            f"UPDATE documents SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )

        # Store 6D enrichment metadata in metadata_json
        enrichment_data = {
            "devourer_6d": {
                "version": DAEMON_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "brief": brief,
                "insights": define.get("key_insights", []),
                "cross_refs": decode.get("cross_references", []),
                "updates_applied": list(updates.keys()),
            }
        }

        # Merge with existing metadata_json
        existing_meta = conn.execute(
            "SELECT metadata_json FROM documents WHERE id = ?", (doc_id,),
        ).fetchone()
        if existing_meta and existing_meta[0]:
            try:
                meta = json.loads(existing_meta[0])
                meta.update(enrichment_data)
                enrichment_data = meta
            except json.JSONDecodeError:
                pass

        conn.execute(
            "UPDATE documents SET metadata_json = ? WHERE id = ?",
            (json.dumps(enrichment_data), doc_id),
        )
        conn.commit()

        # Emit enrichment event
        write_event(conn, EVT_ENRICHMENT, f"doc:{doc_id}:enriched", {
            "doc_id": doc_id,
            "title": doc.get("title", ""),
            "updates": updates,
            "priority": doc.get("priority", ""),
            "insights_count": len(define.get("key_insights", [])),
            "identity": DEVOURER_IDENTITY,
        })

        # Emit diataxis knowledge event
        write_event(conn, EVT_DIATAXIS, f"doc:{doc_id}:knowledge", {
            "doc_id": doc_id,
            "title": doc.get("title", ""),
            "brief": brief,
            "bluf": bluf,
            "port": updates.get("port", doc.get("port")),
            "doc_type": updates.get("doc_type", doc.get("doc_type")),
            "tags": updates.get("tags", ""),
            "insights": define.get("key_insights", []),
            "cross_references": decode.get("cross_references", []),
        })

        return {"doc_id": doc_id, "status": "ENRICHED", "updates": updates}

    except Exception as e:
        return {"doc_id": doc_id, "status": "ERROR", "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# § 7  LINEAGE MINING — Populate the lineage table
# ═══════════════════════════════════════════════════════════════

def mine_lineage(
    conn: sqlite3.Connection,
    doc: dict,
    decode: dict,
    define: dict,
    dry_run: bool = False,
) -> int:
    """
    Discover and record cross-references in the lineage table.
    Returns number of new edges created.
    """
    doc_id = doc["id"]
    cross_refs = decode.get("cross_references", [])
    depends_on = define.get("depends_on", [])
    enables = define.get("enables", [])

    if not cross_refs and not depends_on and not enables:
        return 0

    edges_created = 0

    # Check if lineage table exists and has expected schema
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(lineage)").fetchall()]
        if not cols:
            return 0  # Table doesn't exist or is empty schema
    except Exception:
        return 0

    # For each cross-reference, try to find matching docs
    all_refs = list(set(cross_refs + depends_on + enables))
    for ref in all_refs[:5]:  # Limit to prevent runaway
        if dry_run:
            edges_created += 1
            continue

        # FTS search for matching docs
        try:
            matches = conn.execute(
                """SELECT id, title FROM documents
                   WHERE id IN (
                       SELECT rowid FROM documents_fts
                       WHERE documents_fts MATCH ?
                   ) AND id != ?
                   LIMIT 3""",
                (ref, doc_id),
            ).fetchall()

            for match in matches:
                rel_type = "cross_reference"
                if ref in depends_on:
                    rel_type = "depends_on"
                elif ref in enables:
                    rel_type = "enables"

                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO lineage
                           (parent_id, child_id, relation_type)
                           VALUES (?, ?, ?)""",
                        (doc_id, match[0], rel_type),
                    )
                    edges_created += 1
                except sqlite3.IntegrityError:
                    pass  # Edge already exists or schema mismatch

        except Exception:
            pass  # FTS match syntax error or other issue

    if edges_created > 0 and not dry_run:
        conn.commit()

    return edges_created


# ═══════════════════════════════════════════════════════════════
# § 8  THE DEVOURER CYCLE — One complete 6D pass
# ═══════════════════════════════════════════════════════════════

def run_cycle(
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH,
    dry_run: bool = False,
    quiet: bool = False,
) -> dict:
    """
    Run one complete Devourer cycle:
      1. Read swarm stigmergy
      2. Find targets
      3. Run 6D pipeline on each
      4. Disseminate results
      5. Emit pulse
    """
    _print = (lambda *a, **k: None) if quiet else print
    cycle_start = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()
    results = {
        "timestamp": now_iso,
        "model": model,
        "batch_size": batch_size,
        "dry_run": dry_run,
        "targets_found": 0,
        "enriched": 0,
        "errors": 0,
        "lineage_edges": 0,
        "documents": [],
    }

    # Step 1: Read swarm stigmergy (the Devourer's senses)
    _print(f"  [{now_iso[:19]}] Reading swarm stigmergy...")
    stigmergy = read_swarm_stigmergy(hours=1.0)
    swarm_context = summarize_swarm_state(stigmergy)
    results["swarm_families_consumed"] = len(stigmergy)
    results["swarm_events_consumed"] = sum(len(v) for v in stigmergy.values())
    _print(f"    Consumed {results['swarm_events_consumed']} events from {results['swarm_families_consumed']} families")

    # Step 2: Find targets
    _print(f"  [{datetime.now(timezone.utc).isoformat()[:19]}] Finding targets (batch={batch_size})...")
    targets = find_targets(batch_size)
    results["targets_found"] = len(targets)
    if not targets:
        _print("    No targets found — SSOT may be fully enriched!")
        return results

    _print(f"    Found {len(targets)} targets:")
    for t in targets:
        _print(f"      [{t['priority']}] Doc {t['id']}: {t.get('title', 'untitled')[:50]}")

    # Step 3: Check Ollama availability
    if not ollama_alive():
        _print("    [WARN] Ollama not reachable — skipping LLM stages")
        results["errors"] += 1
        return results

    # Ensure model is loaded
    _print(f"    Loading model {model}...")
    ensure_model_loaded(model)

    # Step 4: Run 6D pipeline on each target
    conn = None if dry_run else get_db_rw()

    for doc in targets:
        if _SHUTDOWN:
            _print("    [SHUTDOWN] Interrupted by signal")
            break

        doc_id = doc["id"]
        title_short = doc.get("title", "untitled")[:40]
        _print(f"\n  ── Devouring Doc {doc_id}: {title_short} ──")

        doc_result = {"doc_id": doc_id, "title": doc.get("title", ""), "stages": {}}

        try:
            # D0: DIRECT
            _print(f"    D0 DIRECT...")
            brief = run_d0_direct(doc, swarm_context, model)
            doc_result["stages"]["D0_DIRECT"] = "OK"
            _print(f"    → {brief.get('what', '?')[:60]}")

            # D1: DISCOVER (BLUF)
            _print(f"    D1 DISCOVER...")
            discover = run_d1_discover(doc, brief, model)
            doc_result["stages"]["D1_DISCOVER"] = "OK" if discover.get("bluf") else "EMPTY"
            if discover.get("bluf"):
                _print(f"    → BLUF: {discover['bluf'][:80]}")

            # D2: DECODE (classification)
            _print(f"    D2 DECODE...")
            decode = run_d2_decode(doc, brief, model)
            doc_result["stages"]["D2_DECODE"] = "OK" if decode else "EMPTY"
            if decode.get("port"):
                _print(f"    → Port: {decode.get('port')}, Type: {decode.get('doc_type')}")

            # D3: DEFINE (insights)
            _print(f"    D3 DEFINE...")
            define = run_d3_define(doc, brief, model)
            doc_result["stages"]["D3_DEFINE"] = "OK" if define.get("key_insights") else "EMPTY"
            if define.get("key_insights"):
                _print(f"    → {len(define['key_insights'])} insights extracted")

            # D4: DEMONSTRATE — skipped in autonomous mode (requires worked example)
            doc_result["stages"]["D4_DEMONSTRATE"] = "SKIPPED"

            # D5: DISSEMINATE
            _print(f"    D5 DISSEMINATE{'[DRY]' if dry_run else ''}...")
            if conn:
                disseminate = run_d5_disseminate(conn, doc, brief, discover, decode, define, dry_run)
            else:
                disseminate = {"doc_id": doc_id, "dry_run": True, "would_update": {
                    k: v for k, v in [
                        ("bluf", discover.get("bluf")),
                        ("port", decode.get("port")),
                        ("doc_type", decode.get("doc_type")),
                    ] if v
                }}
            doc_result["stages"]["D5_DISSEMINATE"] = disseminate.get("status", "DRY_RUN")
            doc_result["updates"] = disseminate.get("updates", disseminate.get("would_update", {}))

            # Lineage mining
            if conn:
                edges = mine_lineage(conn, doc, decode, define, dry_run)
                doc_result["lineage_edges"] = edges
                results["lineage_edges"] += edges

            if disseminate.get("status") == "ENRICHED":
                results["enriched"] += 1
            elif disseminate.get("status") == "ERROR":
                results["errors"] += 1

            status_icon = "✓" if disseminate.get("status") in ("ENRICHED", "DRY_RUN", "NO_UPDATES_NEEDED") else "✗"
            _print(f"    {status_icon} Doc {doc_id}: {disseminate.get('status', 'DRY_RUN')}")

        except Exception as e:
            doc_result["error"] = str(e)
            results["errors"] += 1
            _print(f"    ✗ Doc {doc_id}: ERROR — {e}")
            traceback.print_exc()

        results["documents"].append(doc_result)

    # Step 5: Emit pulse event
    elapsed = time.time() - cycle_start
    results["elapsed_seconds"] = round(elapsed, 1)

    if conn and not dry_run:
        write_event(conn, EVT_PULSE, "devourer:cycle:complete", {
            "targets_found": results["targets_found"],
            "enriched": results["enriched"],
            "errors": results["errors"],
            "lineage_edges": results["lineage_edges"],
            "elapsed_seconds": results["elapsed_seconds"],
            "model": model,
            "swarm_families": results["swarm_families_consumed"],
            "swarm_events": results["swarm_events_consumed"],
            "identity": DEVOURER_IDENTITY,
        })
        conn.close()

    _print(f"\n  Cycle complete: {results['enriched']} enriched, "
           f"{results['errors']} errors, {results['lineage_edges']} lineage edges, "
           f"{results['elapsed_seconds']}s")

    return results


# ═══════════════════════════════════════════════════════════════
# § 9  STATUS DISPLAY
# ═══════════════════════════════════════════════════════════════

def show_status(as_json: bool = False) -> dict:
    """Show Devourer daemon status and SSOT enrichment coverage."""
    status = {
        "daemon": DAEMON_NAME,
        "version": DAEMON_VERSION,
        "ollama": "ONLINE" if ollama_alive() else "OFFLINE",
        "ssot_db": str(SSOT_DB),
        "ssot_exists": SSOT_DB.exists(),
    }

    if SSOT_DB.exists():
        try:
            conn = get_db_ro()

            # Enrichment coverage
            total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            no_bluf = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE bluf IS NULL OR bluf = '' OR bluf = '---'"
            ).fetchone()[0]
            no_port = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE port IS NULL"
            ).fetchone()[0]
            no_doctype = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE doc_type IS NULL"
            ).fetchone()[0]
            no_tags = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE tags IS NULL OR tags = ''"
            ).fetchone()[0]

            status["docs_total"] = total
            status["coverage"] = {
                "bluf": {"missing": no_bluf, "pct": round(100 * (total - no_bluf) / max(total, 1), 1)},
                "port": {"missing": no_port, "pct": round(100 * (total - no_port) / max(total, 1), 1)},
                "doc_type": {"missing": no_doctype, "pct": round(100 * (total - no_doctype) / max(total, 1), 1)},
                "tags": {"missing": no_tags, "pct": round(100 * (total - no_tags) / max(total, 1), 1)},
            }

            # Recent devourer events
            dev_events = conn.execute(
                """SELECT COUNT(*) FROM stigmergy_events
                   WHERE event_type LIKE ?""",
                (f"hfo.gen{GEN}.devourer%",),
            ).fetchone()[0]
            status["devourer_events_total"] = dev_events

            recent = conn.execute(
                """SELECT COUNT(*) FROM stigmergy_events
                   WHERE event_type LIKE ?
                     AND timestamp >= datetime('now', '-1 hour')""",
                (f"hfo.gen{GEN}.devourer%",),
            ).fetchone()[0]
            status["devourer_events_1h"] = recent

            # Lineage table
            try:
                lineage_count = conn.execute("SELECT COUNT(*) FROM lineage").fetchone()[0]
                status["lineage_edges"] = lineage_count
            except Exception:
                status["lineage_edges"] = "TABLE_EMPTY_OR_MISSING"

            conn.close()
        except Exception as e:
            status["error"] = str(e)

    if as_json:
        print(json.dumps(status, indent=2, default=str))
    else:
        print("=" * 70)
        print(f"  {DAEMON_NAME} — Status")
        print("=" * 70)
        print(f"  Ollama: {status.get('ollama', '?')}")
        print(f"  SSOT: {status.get('docs_total', '?')} documents")
        if "coverage" in status:
            cov = status["coverage"]
            print(f"\n  SSOT Enrichment Coverage:")
            print(f"    BLUF:     {cov['bluf']['pct']:5.1f}% ({cov['bluf']['missing']} missing)")
            print(f"    Port:     {cov['port']['pct']:5.1f}% ({cov['port']['missing']} missing)")
            print(f"    Doc Type: {cov['doc_type']['pct']:5.1f}% ({cov['doc_type']['missing']} missing)")
            print(f"    Tags:     {cov['tags']['pct']:5.1f}% ({cov['tags']['missing']} missing)")
        print(f"\n  Devourer events (total): {status.get('devourer_events_total', 0)}")
        print(f"  Devourer events (1h):    {status.get('devourer_events_1h', 0)}")
        print(f"  Lineage edges:           {status.get('lineage_edges', 0)}")
        print()

    return status


# ═══════════════════════════════════════════════════════════════
# § 10  DAEMON LOOP
# ═══════════════════════════════════════════════════════════════

def daemon_loop(
    model: str = DEFAULT_MODEL,
    interval: int = DEFAULT_INTERVAL,
    batch_size: int = DEFAULT_BATCH,
):
    """Run the Devourer in continuous daemon mode."""
    print("=" * 70)
    print(f"  {DAEMON_NAME} — Starting 24/7 Daemon")
    print(f"  Model: {model} | Interval: {interval}s | Batch: {batch_size}")
    print(f"  Pipeline: DIRECT → DISCOVER → DECODE → DEFINE → DEMONSTRATE → DISSEMINATE")
    print(f"  Philosophy: Unused resource is wasted resource.")
    print("=" * 70)

    cycle_count = 0
    while not _SHUTDOWN:
        cycle_count += 1
        print(f"\n{'─' * 70}")
        print(f"  DEVOURER CYCLE {cycle_count}")
        print(f"{'─' * 70}")

        try:
            result = run_cycle(model=model, batch_size=batch_size, dry_run=False)
            enriched = result.get("enriched", 0)
            errors = result.get("errors", 0)
            elapsed = result.get("elapsed_seconds", 0)
            print(f"  Cycle {cycle_count}: {enriched} enriched, {errors} errors, {elapsed}s")
        except Exception as e:
            print(f"  [ERROR] Cycle {cycle_count} failed: {e}")
            traceback.print_exc()

        # Sleep with shutdown check
        for _ in range(interval):
            if _SHUTDOWN:
                break
            time.sleep(1)

    print(f"\n  {DAEMON_NAME} — Shutdown after {cycle_count} cycles")


# ═══════════════════════════════════════════════════════════════
# § 11  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"{DAEMON_NAME} — 6D Knowledge Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The Devourer consumes idle resources to extract knowledge from the SSOT.
Every cycle: read swarm stigmergy → find targets → run 6D pipeline → enrich SSOT.

"Unused free API/hardware/GPU/NPU is wasted resource."
"What was consumed becomes vision. Depths ARE dreams. Memory IS digestion."

Examples:
  python hfo_p6_devourer_daemon.py                      # 24/7 daemon
  python hfo_p6_devourer_daemon.py --single              # One cycle
  python hfo_p6_devourer_daemon.py --dry-run --single    # Preview
  python hfo_p6_devourer_daemon.py --status              # Coverage report
  python hfo_p6_devourer_daemon.py --model qwen3:8b      # Different model
  python hfo_p6_devourer_daemon.py --batch 5             # 5 docs per cycle
        """,
    )
    parser.add_argument("--single", action="store_true",
                        help="Run one cycle then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing to SSOT")
    parser.add_argument("--status", action="store_true",
                        help="Show enrichment coverage and daemon status")
    parser.add_argument("--json", action="store_true",
                        help="JSON output (with --status)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help=f"Seconds between cycles (default: {DEFAULT_INTERVAL})")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                        help=f"Documents per cycle (default: {DEFAULT_BATCH})")

    args = parser.parse_args()

    if args.status:
        show_status(as_json=args.json)
        return

    if args.single:
        result = run_cycle(
            model=args.model,
            batch_size=args.batch,
            dry_run=args.dry_run,
        )
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        return

    # Full daemon mode
    daemon_loop(
        model=args.model,
        interval=args.interval,
        batch_size=args.batch,
    )


if __name__ == "__main__":
    main()
