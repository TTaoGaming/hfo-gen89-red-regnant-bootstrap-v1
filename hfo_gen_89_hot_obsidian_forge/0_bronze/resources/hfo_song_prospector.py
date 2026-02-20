#!/usr/bin/env python3
"""
hfo_song_prospector.py — SONG PROSPECTOR Daemon (Gen89)
========================================================
v1.0 | Gen89 | Port: P4 DISRUPT | Commander: Red Regnant
Powerword: DISRUPT | School: Divination/Evocation (hybrid)
Title: Listener in the Deep Library | Trigram: ☲ Li (Fire)

PURPOSE:
    Background daemon that reads through SSOT memory documents using a
    high-intelligence LLM, identifies patterns (splendor) and antipatterns
    (strife), and proposes new songs for the SONGS OF STRIFE AND SPLENDOR
    songbook. Proposals accumulate as CloudEvent stigmergy events,
    reviewable through SQLite queries or the --status CLI.

    This is the creative prospecting arm of P4 DISRUPT — it doesn't break
    things, it *listens* to 9,861 documents and hears what songs are hiding
    in them. The Kraken (P6) devours knowledge. The Prospector hears music.

ARCHITECTURE:
    - Async daemon loop with configurable intervals
    - Samples SSOT documents in randomized batches
    - Sends document content to a high-intelligence Ollama model
    - Parses structured JSON proposals from model output
    - Deduplicates against existing songbook repertoire + prior proposals
    - Writes proposals as CloudEvents to stigmergy_events
    - Tracks progress: which doc IDs have been prospected

STIGMERGY EVENT TYPES (port-sharded to P4):
    hfo.gen89.p4.song_prospector.proposal    — A new song proposal
    hfo.gen89.p4.song_prospector.heartbeat   — Daemon alive signal
    hfo.gen89.p4.song_prospector.error       — Daemon self-reported error
    hfo.gen89.p4.song_prospector.start       — Daemon started
    hfo.gen89.p4.song_prospector.stop        — Daemon stopped

REVIEW PROPOSALS:
    # Quick status with proposal summary
    python hfo_song_prospector.py --status

    # Full JSON for programmatic review
    python hfo_song_prospector.py --status --json

    # SQL (direct query):
    SELECT data_json FROM stigmergy_events
    WHERE event_type = 'hfo.gen89.p4.song_prospector.proposal'
    ORDER BY timestamp DESC;

MODELS (default: qwen3:30b-a3b — MoE 30B with 3B active):
    The prospector needs creative intelligence to identify latent
    patterns in documents. Small models miss nuance. Use 12B+ for
    quality proposals. Available high-intelligence models:
      - qwen3:30b-a3b  (17.3 GB, MoE, 3B active — smart + efficient)
      - deepseek-r1:32b (18.5 GB, reasoning model — very thorough)
      - phi4:14b        (8.4 GB — good balance of speed and quality)
      - gemma3:12b      (7.6 GB — fast, solid pattern recognition)

USAGE:
    # Start continuous background prospecting
    python hfo_song_prospector.py

    # One cycle then exit (prospect one batch)
    python hfo_song_prospector.py --once

    # Dry run (show what would be proposed, no SSOT writes)
    python hfo_song_prospector.py --dry-run --once

    # Use a specific model
    python hfo_song_prospector.py --model deepseek-r1:32b

    # Custom batch size and interval
    python hfo_song_prospector.py --batch-size 5 --interval 600

    # Review accumulated proposals
    python hfo_song_prospector.py --status
    python hfo_song_prospector.py --status --json

Medallion: bronze
Port: P4 DISRUPT
Pointer key: daemon.song_prospector
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
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

# Fix Windows console encoding for Unicode
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
# PATH RESOLUTION VIA PAL (Path Abstraction Layer)
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    """Find HFO_ROOT by walking up from script location."""
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
POINTERS_FILE = HFO_ROOT / "hfo_gen89_pointers_blessed.json"


def _load_pointers() -> dict:
    """Load blessed pointer registry."""
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
# High-intelligence model: MoE 30B with 3B active — creative intelligence
# for pattern recognition without loading the full 32B into VRAM
DEFAULT_MODEL = os.environ.get("SONG_PROSPECTOR_MODEL", "qwen3:30b-a3b")
P4_SOURCE = f"hfo_song_prospector_gen{GEN}"
P4_EVENT_PREFIX = "hfo.gen89.p4.song_prospector"
STATE_FILE = HFO_ROOT / ".hfo_song_prospector_state.json"

# ═══════════════════════════════════════════════════════════════
# PROSPECTOR IDENTITY
# ═══════════════════════════════════════════════════════════════

PROSPECTOR_IDENTITY = {
    "port": "P4",
    "powerword": "DISRUPT",
    "commander": "Red Regnant",
    "title": "Listener in the Deep Library",
    "role": "Song Prospector",
    "spell": "LEGEND_LORE",
    "spell_school": "Divination",
    "trigram": "☲ Li (Fire)",
    "galois_pair": "P5 IMMUNIZE (Pyre Praetorian)",
    "core_thesis": "Every document holds a pattern or an antipattern. "
                   "The Prospector listens for the music hiding in the text.",
}

# ═══════════════════════════════════════════════════════════════
# EXISTING REPERTOIRE (songs already in the songbook — do NOT re-propose)
# ═══════════════════════════════════════════════════════════════

EXISTING_STRIFE = {
    "WAIL_OF_THE_BANSHEE": "Total session death / memory loss",
    "POWERWORD_KILL": "Silent failure / swallowed errors",
    "FELL_DRAIN": "Quality decay by shortcuts",
    "GREATER_SHOUT": "Uncontrolled blast radius",
    "SOUND_LANCE": "Retry storms",
    "SYMPATHETIC_VIBRATION": "Structural resonance collapse",
    "SHATTER": "Brittle design / no recovery",
    "REAPER": "Dead sessions / zombie processes",
    "WALL_OF_SOUND": "Information overload",
    "RESONATING_WORD": "Recurring cross-gen antipatterns",
}

EXISTING_SPLENDOR = {
    "INSPIRE_COURAGE": "Completed sessions",
    "INSPIRE_HEROICS": "Elite full-gate execution",
    "WORDS_OF_CREATION": "Reusable meta-architecture",
    "HARMONIC_CHORUS": "Swarm synergy",
    "INSPIRE_COMPETENCE": "Novice orientation success",
    "COUNTERSONG": "Anti-sycophancy / honest challenge",
    "SONG_OF_FREEDOM": "L13 Divine Conceptual Incarnation",
}

# D&D Bard spells/abilities NOT yet in the songbook — candidates for new songs
# From PHB, Spell Compendium, Complete Arcane, etc.
CANDIDATE_SPELLS = [
    # Strife candidates (damage/debuff bard spells)
    "DIRGE_OF_DISCORD", "CACOPHONOUS_CALL", "DISSONANT_WHISPERS",
    "HIDEOUS_LAUGHTER", "PHANTASMAL_KILLER", "HOLD_MONSTER",
    "IRRESISTIBLE_DANCE", "MASS_SUGGESTION", "WAIL_OF_DOOM",
    "DOLOROUS_BLOW", "INFERNAL_THRENODY", "CURSED_CHORD",
    # Splendor candidates (buff/heal bard spells)
    "OTTO_IRRESISTIBLE_DANCE", "HYMN_OF_PRAISE", "GLIBNESS",
    "ALLEGRO", "CRESCENDO", "CHORD_OF_SHARDS",
    "REVENANCE", "VIRTUOSO_PERFORMANCE", "ZENITH_STRIKE",
    "CLARION_CALL", "HEALING_HYMN", "LULLABY_OF_WARDING",
]

ALL_EXISTING = set(EXISTING_STRIFE.keys()) | set(EXISTING_SPLENDOR.keys())


# ═══════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_readonly() -> sqlite3.Connection:
    if not SSOT_DB.exists():
        raise FileNotFoundError(f"SSOT database not found: {SSOT_DB}")
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_readwrite() -> sqlite3.Connection:
    if not SSOT_DB.exists():
        raise FileNotFoundError(f"SSOT database not found: {SSOT_DB}")
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
    source: str = P4_SOURCE,
) -> str:
    """Write a CloudEvent to the stigmergy trail. Returns event_id."""
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
    model: str = DEFAULT_MODEL,
    timeout: float = 600,
    temperature: float = 0.7,
    num_predict: int = 2048,
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
        print(f"  [OLLAMA ERROR] {model}: {e}", file=sys.stderr)
        return ""


def ollama_available(model: str = DEFAULT_MODEL) -> bool:
    """Check if Ollama is reachable and the model is available."""
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code != 200:
                return False
            models = [m["name"] for m in r.json().get("models", [])]
            # Check exact match or match without tag
            return any(model in m or m.startswith(model.split(":")[0])
                       for m in models)
    except Exception:
        return False


def _strip_think_tags(text: str) -> str:
    """Strip <think>...</think> blocks from reasoning model output."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


# ═══════════════════════════════════════════════════════════════
# THE PROSPECTOR PROMPT
# ═══════════════════════════════════════════════════════════════

PROSPECTOR_SYSTEM = """You are the Song Prospector — a creative intelligence that reads documents
from a knowledge system called HFO (Hive Fleet Obsidian) and identifies patterns
that could become SONGS.

HFO has two kinds of songs:
  STRIFE songs warn of antipatterns — things that went wrong, failures, pain points,
  architectural mistakes, cognitive traps, wasted effort, broken sessions, lost memory.
  Named after D&D Bard damage/debuff spells.

  SPLENDOR songs celebrate patterns — things that worked, proven architectures,
  successful recoveries, wisdom gained, elegant solutions, compounding knowledge.
  Named after D&D Bard buff/healing spells.

When you read a document, look for:
  1. STRIFE: What went wrong? What pain is described? What antipattern recurs?
  2. SPLENDOR: What worked? What pattern proved itself? What wisdom was hard-won?

For each pattern you find, propose a song with:
  - "song_type": "strife" or "splendor"
  - "spell_name": A D&D Bard spell/ability name (UPPER_SNAKE_CASE)
  - "subtitle": A short evocative subtitle (like "Total Session Death" or "Swarm Synergy")
  - "pattern_description": 2-3 sentences describing the pattern/antipattern
  - "evidence_quote": A specific quote or detail from the document as evidence
  - "suggested_genre": Music genre for the lyrics (e.g., "Doom Metal", "Gospel", "Industrial")
  - "confidence": 1-10 how strong/clear this pattern is

RULES:
- Return ONLY valid JSON. No markdown, no preamble, no explanation.
- Return a JSON array of proposal objects. Empty array [] if no patterns found.
- Be specific. Cite actual details from the document.
- Don't propose patterns that are too vague or generic.
- Prefer strong, specific, recurring patterns over one-off observations.
- A confidence of 7+ means "this should definitely be a song".
- A confidence of 4-6 means "interesting but needs more evidence across documents".
- Below 4, don't bother proposing it.
"""

PROSPECT_PROMPT_TEMPLATE = """Analyze this document from the HFO knowledge system for song-worthy patterns.

DOCUMENT ID: {doc_id}
TITLE: {title}
SOURCE: {source}
PORT: {port}
WORD COUNT: {word_count}

CONTENT (first 4000 chars):
{content}

---

SONGS ALREADY IN THE SONGBOOK (do NOT re-propose these):
Strife: {existing_strife}
Splendor: {existing_splendor}

Respond with a JSON array of song proposals. Empty array [] if nothing stands out.
"""


# ═══════════════════════════════════════════════════════════════
# SONG PROSPECTOR — Core Engine
# ═══════════════════════════════════════════════════════════════

class SongProspector:
    """The P4 Song Prospector daemon — creative pattern mining via Ollama."""

    def __init__(
        self,
        dry_run: bool = False,
        model: str = DEFAULT_MODEL,
        batch_size: int = 3,
        interval: float = 300,
        min_confidence: int = 5,
    ):
        self.dry_run = dry_run
        self.model = model
        self.batch_size = batch_size
        self.interval = interval
        self.min_confidence = min_confidence
        self._running = True

        # Stats
        self.stats = {
            "cycles": 0,
            "docs_prospected": 0,
            "proposals_generated": 0,
            "proposals_strife": 0,
            "proposals_splendor": 0,
            "proposals_deduplicated": 0,
            "ollama_calls": 0,
            "errors": 0,
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

        # Load prospected doc IDs from state file
        self._prospected_ids: set[int] = set()
        self._load_state()

        # Track proposals already emitted this session
        self._session_proposals: set[str] = set()

    def stop(self):
        self._running = False

    def _load_state(self):
        """Load persistent state from disk."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._prospected_ids = set(data.get("prospected_ids", []))
            except Exception:
                pass

    def _save_state(self):
        """Persist state to disk."""
        state = {
            "stats": dict(self.stats),
            "prospected_ids": sorted(self._prospected_ids),
            "model": self.model,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    # ── Fetch candidate documents ──

    def _get_candidate_docs(self, conn: sqlite3.Connection) -> list[dict]:
        """Get a random batch of documents not yet prospected."""
        # First get total count for status
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

        # Get docs we haven't prospected yet, preferring longer docs (more content)
        # Exclude very short docs (< 200 words) — not enough substance
        prospected_csv = ",".join(str(i) for i in self._prospected_ids) if self._prospected_ids else "-1"
        query = f"""
            SELECT id, title, SUBSTR(content, 1, 4000) as content_preview,
                   source, port, word_count, doc_type, bluf
            FROM documents
            WHERE id NOT IN ({prospected_csv})
              AND word_count > 200
            ORDER BY RANDOM()
            LIMIT ?
        """
        rows = conn.execute(query, (self.batch_size,)).fetchall()
        return [dict(r) for r in rows]

    # ── Prospect a single document ──

    def _prospect_document(self, doc: dict) -> list[dict]:
        """Send a document to the LLM and parse song proposals."""
        prompt = PROSPECT_PROMPT_TEMPLATE.format(
            doc_id=doc["id"],
            title=doc.get("title") or "(untitled)",
            source=doc.get("source") or "unknown",
            port=doc.get("port") or "unclassified",
            word_count=doc.get("word_count") or 0,
            content=doc.get("content_preview") or "",
            existing_strife=", ".join(EXISTING_STRIFE.keys()),
            existing_splendor=", ".join(EXISTING_SPLENDOR.keys()),
        )

        raw = ollama_generate(
            prompt,
            system=PROSPECTOR_SYSTEM,
            model=self.model,
            temperature=0.7,
            num_predict=2048,
        )
        self.stats["ollama_calls"] += 1

        if not raw:
            return []

        # Strip think tags and extract JSON
        cleaned = _strip_think_tags(raw)

        # Try to find JSON array in the response
        proposals = self._parse_proposals(cleaned)
        return proposals

    def _parse_proposals(self, text: str) -> list[dict]:
        """Parse JSON proposals from LLM output. Robust to formatting noise."""
        # Try direct parse first
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [p for p in result if isinstance(p, dict)]
            if isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass

        # Try to extract JSON array from surrounding text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return [p for p in result if isinstance(p, dict)]
            except json.JSONDecodeError:
                pass

        # Try to find individual JSON objects
        objects = []
        for m in re.finditer(r"\{[^{}]+(?:\{[^{}]*\}[^{}]*)*\}", text):
            try:
                obj = json.loads(m.group())
                if isinstance(obj, dict) and "song_type" in obj:
                    objects.append(obj)
            except json.JSONDecodeError:
                continue
        return objects

    # ── Dedup and validate proposals ──

    def _validate_proposal(self, proposal: dict) -> Optional[dict]:
        """Validate and normalize a proposal. Returns None if invalid/duplicate."""
        song_type = proposal.get("song_type", "").lower()
        if song_type not in ("strife", "splendor"):
            return None

        spell_name = proposal.get("spell_name", "").upper().replace(" ", "_")
        if not spell_name:
            return None

        # Check against existing songbook
        if spell_name in ALL_EXISTING:
            return None

        # Check against session proposals (dedup within session)
        dedup_key = f"{song_type}:{spell_name}"
        if dedup_key in self._session_proposals:
            self.stats["proposals_deduplicated"] += 1
            return None

        confidence = proposal.get("confidence", 0)
        if not isinstance(confidence, (int, float)):
            try:
                confidence = int(confidence)
            except (ValueError, TypeError):
                confidence = 5

        if confidence < self.min_confidence:
            return None

        subtitle = proposal.get("subtitle", "Unnamed Pattern")[:100]
        pattern_desc = proposal.get("pattern_description", "")[:500]
        evidence = proposal.get("evidence_quote", "")[:500]
        genre = proposal.get("suggested_genre", "Unknown")[:50]

        self._session_proposals.add(dedup_key)

        return {
            "song_type": song_type,
            "spell_name": spell_name,
            "subtitle": subtitle,
            "pattern_description": pattern_desc,
            "evidence_quote": evidence,
            "suggested_genre": genre,
            "confidence": min(max(int(confidence), 1), 10),
        }

    # ── Write proposal to stigmergy ──

    def _write_proposal(self, conn: sqlite3.Connection, proposal: dict,
                        doc_id: int, doc_title: str) -> str:
        """Write a validated song proposal as a CloudEvent."""
        song_type = proposal["song_type"]
        spell_name = proposal["spell_name"]

        return write_stigmergy_event(
            conn,
            event_type=f"{P4_EVENT_PREFIX}.proposal",
            subject=f"PROPOSAL:{song_type.upper()}:{spell_name}",
            data={
                "song_type": song_type,
                "spell_name": spell_name,
                "subtitle": proposal["subtitle"],
                "pattern_description": proposal["pattern_description"],
                "evidence_quote": proposal["evidence_quote"],
                "suggested_genre": proposal["suggested_genre"],
                "confidence": proposal["confidence"],
                "source_doc_id": doc_id,
                "source_doc_title": doc_title[:100],
                "model": self.model,
                "prospector_identity": PROSPECTOR_IDENTITY["title"],
            },
        )

    # ── Main prospect cycle ──

    async def prospect_cycle(self) -> dict:
        """Run one prospecting cycle across a batch of documents."""
        self.stats["cycles"] += 1
        cycle_start = time.monotonic()
        report = {
            "cycle": self.stats["cycles"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "docs_prospected": 0,
            "proposals": [],
            "errors": [],
        }

        conn_ro = None
        conn_rw = None

        try:
            conn_ro = get_db_readonly()
            conn_rw = get_db_readwrite() if not self.dry_run else None

            # Get candidate documents
            candidates = self._get_candidate_docs(conn_ro)
            if not candidates:
                print("  [PROSPECTOR] No unprospected documents remaining. Full pass complete.")
                report["message"] = "full_pass_complete"
                return report

            for doc in candidates:
                if not self._running:
                    break

                doc_id = doc["id"]
                title = doc.get("title") or "(untitled)"

                print(f"  [PROSPECT] Doc {doc_id}: {title[:60]}...")

                # Prospect via LLM
                try:
                    raw_proposals = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda d=doc: self._prospect_document(d),
                    )
                except Exception as e:
                    report["errors"].append(f"Doc {doc_id}: {e}")
                    self.stats["errors"] += 1
                    continue

                self._prospected_ids.add(doc_id)
                self.stats["docs_prospected"] += 1
                report["docs_prospected"] += 1

                # Validate and write proposals
                valid_count = 0
                for raw_prop in raw_proposals:
                    validated = self._validate_proposal(raw_prop)
                    if validated is None:
                        continue

                    valid_count += 1
                    song_type = validated["song_type"]
                    spell = validated["spell_name"]
                    conf = validated["confidence"]

                    if conn_rw and not self.dry_run:
                        self._write_proposal(conn_rw, validated, doc_id, title)

                    report["proposals"].append({
                        "type": song_type,
                        "spell": spell,
                        "subtitle": validated["subtitle"],
                        "confidence": conf,
                        "doc_id": doc_id,
                    })

                    self.stats["proposals_generated"] += 1
                    if song_type == "strife":
                        self.stats["proposals_strife"] += 1
                    else:
                        self.stats["proposals_splendor"] += 1

                    icon = "[STRIFE]" if song_type == "strife" else "[SPLENDOR]"
                    print(f"    {icon} PROPOSAL: {spell} - \"{validated['subtitle']}\" "
                          f"[{song_type}, conf={conf}]")

                if valid_count == 0:
                    print(f"    (no songs heard in this document)")

        except Exception as e:
            report["errors"].append(str(e))
            self.stats["errors"] += 1
            print(f"  [PROSPECTOR ERROR] {e}", file=sys.stderr)
            traceback.print_exc()
        finally:
            if conn_ro:
                conn_ro.close()
            if conn_rw:
                conn_rw.close()

        elapsed = time.monotonic() - cycle_start
        report["elapsed_seconds"] = round(elapsed, 1)

        # Save state after each cycle
        self._save_state()

        print(f"  [CYCLE {self.stats['cycles']}] "
              f"{report['docs_prospected']} docs, "
              f"{len(report['proposals'])} proposals, "
              f"{report['elapsed_seconds']}s")

        return report

    # ── Heartbeat ──

    def _write_heartbeat(self, conn: sqlite3.Connection):
        """Write a daemon heartbeat event."""
        write_stigmergy_event(
            conn,
            event_type=f"{P4_EVENT_PREFIX}.heartbeat",
            subject=f"SONG_PROSPECTOR_HEARTBEAT:{datetime.now(timezone.utc).strftime('%H%M%S')}",
            data={
                "action": "heartbeat",
                "stats": dict(self.stats),
                "model": self.model,
                "prospected_count": len(self._prospected_ids),
                "identity": PROSPECTOR_IDENTITY["title"],
            },
        )

    # ── Status / Review ──

    @staticmethod
    def get_proposal_summary() -> dict:
        """Query stigmergy for all accumulated song proposals."""
        summary = {
            "total_proposals": 0,
            "strife_proposals": [],
            "splendor_proposals": [],
            "by_confidence": {},
            "by_model": {},
            "by_spell": {},
            "docs_prospected_total": 0,
            "error": None,
        }

        try:
            conn = get_db_readonly()
        except Exception as e:
            summary["error"] = str(e)
            return summary

        try:
            # Get all proposals
            rows = conn.execute(
                """SELECT data_json, timestamp FROM stigmergy_events
                   WHERE event_type = ?
                   ORDER BY timestamp DESC""",
                (f"{P4_EVENT_PREFIX}.proposal",),
            ).fetchall()

            for row in rows:
                try:
                    event = json.loads(row["data_json"])
                    data = event.get("data", {})
                except (json.JSONDecodeError, KeyError):
                    continue

                summary["total_proposals"] += 1
                song_type = data.get("song_type", "unknown")
                spell = data.get("spell_name", "UNKNOWN")
                conf = data.get("confidence", 0)
                model = data.get("model", "unknown")

                entry = {
                    "spell_name": spell,
                    "subtitle": data.get("subtitle", ""),
                    "pattern_description": data.get("pattern_description", ""),
                    "confidence": conf,
                    "source_doc_id": data.get("source_doc_id"),
                    "source_doc_title": data.get("source_doc_title", ""),
                    "suggested_genre": data.get("suggested_genre", ""),
                    "model": model,
                    "timestamp": row["timestamp"],
                }

                if song_type == "strife":
                    summary["strife_proposals"].append(entry)
                else:
                    summary["splendor_proposals"].append(entry)

                # Aggregate by confidence
                conf_bucket = f"{conf}/10"
                summary["by_confidence"][conf_bucket] = \
                    summary["by_confidence"].get(conf_bucket, 0) + 1

                # Aggregate by model
                summary["by_model"][model] = \
                    summary["by_model"].get(model, 0) + 1

                # Aggregate by spell (potential dupes across docs)
                if spell not in summary["by_spell"]:
                    summary["by_spell"][spell] = {
                        "song_type": song_type,
                        "count": 0,
                        "max_confidence": 0,
                        "subtitle": data.get("subtitle", ""),
                    }
                summary["by_spell"][spell]["count"] += 1
                summary["by_spell"][spell]["max_confidence"] = max(
                    summary["by_spell"][spell]["max_confidence"], conf
                )

            # Get prospected docs count from heartbeats
            hb_row = conn.execute(
                """SELECT data_json FROM stigmergy_events
                   WHERE event_type = ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (f"{P4_EVENT_PREFIX}.heartbeat",),
            ).fetchone()
            if hb_row:
                try:
                    hb_event = json.loads(hb_row["data_json"])
                    summary["docs_prospected_total"] = \
                        hb_event.get("data", {}).get("prospected_count", 0)
                except Exception:
                    pass

            # Also check state file
            if STATE_FILE.exists():
                try:
                    with open(STATE_FILE, "r") as f:
                        state = json.load(f)
                    summary["docs_prospected_total"] = max(
                        summary["docs_prospected_total"],
                        len(state.get("prospected_ids", [])),
                    )
                except Exception:
                    pass

        except Exception as e:
            summary["error"] = str(e)
        finally:
            conn.close()

        return summary


# ═══════════════════════════════════════════════════════════════
# DAEMON LOOP
# ═══════════════════════════════════════════════════════════════

async def daemon_loop(prospector: SongProspector, single: bool = False):
    """Main daemon loop — prospect, heartbeat, repeat."""
    print(f"\n  +==================================================+")
    print(f"  |  SONG PROSPECTOR -- Listener in the Deep Library  |")
    print(f"  |  Port: P4 DISRUPT | Model: {prospector.model:<20s} |")
    print(f"  |  Interval: {prospector.interval}s | Batch: {prospector.batch_size} docs             |")
    if prospector.dry_run:
        print(f"  |  *** DRY RUN -- no SSOT writes ***               |")
    print(f"  +==================================================+\n")

    # Check Ollama
    if not ollama_available(prospector.model):
        print(f"  [ERROR] Ollama model '{prospector.model}' not available!", file=sys.stderr)
        print(f"  Available models: run 'ollama list'", file=sys.stderr)
        return

    # Log start event
    if not prospector.dry_run:
        try:
            conn = get_db_readwrite()
            write_stigmergy_event(
                conn,
                event_type=f"{P4_EVENT_PREFIX}.start",
                subject="SONG_PROSPECTOR_START",
                data={
                    "action": "daemon_start",
                    "model": prospector.model,
                    "batch_size": prospector.batch_size,
                    "interval": prospector.interval,
                    "min_confidence": prospector.min_confidence,
                    "dry_run": prospector.dry_run,
                    "identity": PROSPECTOR_IDENTITY,
                },
            )
            conn.close()
        except Exception:
            pass

    try:
        if single:
            # Single cycle
            report = await prospector.prospect_cycle()
            # Write heartbeat
            if not prospector.dry_run:
                try:
                    conn = get_db_readwrite()
                    prospector._write_heartbeat(conn)
                    conn.close()
                except Exception:
                    pass
        else:
            # Continuous loop
            heartbeat_interval = 120
            last_heartbeat = 0

            while prospector._running:
                report = await prospector.prospect_cycle()

                # Heartbeat
                now = time.monotonic()
                if now - last_heartbeat > heartbeat_interval and not prospector.dry_run:
                    try:
                        conn = get_db_readwrite()
                        prospector._write_heartbeat(conn)
                        conn.close()
                        last_heartbeat = now
                    except Exception:
                        pass

                # Check if full pass completed
                if report.get("message") == "full_pass_complete":
                    print("\n  All documents prospected. Resetting for second pass "
                          "(with potentially different model temperature)...")
                    prospector._prospected_ids.clear()
                    prospector._save_state()

                # Wait for next cycle
                if prospector._running:
                    print(f"  Sleeping {prospector.interval}s until next cycle...\n")
                    await asyncio.sleep(prospector.interval)

    except asyncio.CancelledError:
        pass
    finally:
        # Log stop event
        if not prospector.dry_run:
            try:
                conn = get_db_readwrite()
                write_stigmergy_event(
                    conn,
                    event_type=f"{P4_EVENT_PREFIX}.stop",
                    subject="SONG_PROSPECTOR_STOP",
                    data={
                        "action": "daemon_stop",
                        "final_stats": dict(prospector.stats),
                        "docs_prospected": len(prospector._prospected_ids),
                    },
                )
                conn.close()
            except Exception:
                pass

        prospector._save_state()
        print("\n  Song Prospector stopped. The Library remembers what it heard.\n")


# ═══════════════════════════════════════════════════════════════
# CLI — STATUS DISPLAY
# ═══════════════════════════════════════════════════════════════

def show_status(as_json: bool = False):
    """Display accumulated proposal summary."""
    summary = SongProspector.get_proposal_summary()

    if as_json:
        print(json.dumps(summary, indent=2, default=str))
        return

    print("\n  +==================================================+")
    print(f"  |  SONG PROSPECTOR -- Proposal Review               |")
    print(f"  +==================================================+\n")

    if summary.get("error"):
        print(f"  ERROR: {summary['error']}")
        return

    total = summary["total_proposals"]
    strife_n = len(summary["strife_proposals"])
    splendor_n = len(summary["splendor_proposals"])
    prospected = summary["docs_prospected_total"]

    print(f"  Documents Prospected:  {prospected:,}")
    print(f"  Total Proposals:       {total}")
    print(f"    [STRIFE]  Count:      {strife_n}")
    print(f"    [SPLENDOR] Count:     {splendor_n}")

    if summary["by_confidence"]:
        print(f"\n  Confidence Distribution:")
        for conf in sorted(summary["by_confidence"].keys(), reverse=True):
            count = summary["by_confidence"][conf]
            bar = "#" * count
            print(f"    {conf:>4s}: {count:>3d} {bar}")

    # Show unique spell proposals ranked by max confidence
    if summary["by_spell"]:
        print(f"\n  -- Unique Song Proposals (ranked by confidence) --")
        ranked = sorted(
            summary["by_spell"].items(),
            key=lambda x: (-x[1]["max_confidence"], -x[1]["count"]),
        )
        for spell, info in ranked:
            icon = "[S]" if info["song_type"] == "strife" else "[+]"
            print(f"    {icon} {spell:<30s} conf={info['max_confidence']:>2d}/10  "
                  f"seen={info['count']}x  \"{info['subtitle']}\"")

    # Show top strife proposals with details
    if summary["strife_proposals"]:
        print(f"\n  -- TOP STRIFE PROPOSALS --")
        top_strife = sorted(summary["strife_proposals"],
                            key=lambda x: -x["confidence"])[:10]
        for p in top_strife:
            print(f"    [STRIFE]  {p['spell_name']:<25s} conf={p['confidence']}/10")
            print(f"       \"{p['subtitle']}\"")
            if p["pattern_description"]:
                print(f"       {p['pattern_description'][:120]}")
            print(f"       Genre: {p['suggested_genre']}  |  "
                  f"Source: doc {p['source_doc_id']} ({p['source_doc_title'][:40]})")
            print()

    # Show top splendor proposals with details
    if summary["splendor_proposals"]:
        print(f"\n  -- TOP SPLENDOR PROPOSALS --")
        top_splendor = sorted(summary["splendor_proposals"],
                              key=lambda x: -x["confidence"])[:10]
        for p in top_splendor:
            print(f"    [SPLENDOR] {p['spell_name']:<25s} conf={p['confidence']}/10")
            print(f"       \"{p['subtitle']}\"")
            if p["pattern_description"]:
                print(f"       {p['pattern_description'][:120]}")
            print(f"       Genre: {p['suggested_genre']}  |  "
                  f"Source: doc {p['source_doc_id']} ({p['source_doc_title'][:40]})")
            print()

    if total == 0:
        print("\n  No proposals yet. Run the daemon to start prospecting!")
        print("    python hfo_song_prospector.py --once")

    # SQL hint
    print(f"\n  -- SQL Review Query --")
    print(f"  SELECT json_extract(data_json, '$.data.spell_name') as spell,")
    print(f"         json_extract(data_json, '$.data.song_type') as type,")
    print(f"         json_extract(data_json, '$.data.confidence') as conf,")
    print(f"         json_extract(data_json, '$.data.subtitle') as subtitle")
    print(f"  FROM stigmergy_events")
    print(f"  WHERE event_type = '{P4_EVENT_PREFIX}.proposal'")
    print(f"  ORDER BY conf DESC;")
    print()


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="SONG PROSPECTOR — Listener in the Deep Library (Gen89 P4)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hfo_song_prospector.py                          # 24/7 continuous
  python hfo_song_prospector.py --once                   # Single cycle
  python hfo_song_prospector.py --dry-run --once         # Preview (no writes)
  python hfo_song_prospector.py --model deepseek-r1:32b  # Use reasoning model
  python hfo_song_prospector.py --batch-size 5           # More docs per cycle
  python hfo_song_prospector.py --status                 # Review proposals
  python hfo_song_prospector.py --status --json          # JSON review
""",
    )
    parser.add_argument("--once", action="store_true",
                        help="Run one prospecting cycle and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="No SSOT writes, show proposals in stdout only")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--batch-size", type=int, default=3,
                        help="Documents per cycle (default: 3)")
    parser.add_argument("--interval", type=float, default=300,
                        help="Seconds between cycles (default: 300)")
    parser.add_argument("--min-confidence", type=int, default=5,
                        help="Minimum confidence to accept (1-10, default: 5)")
    parser.add_argument("--status", action="store_true",
                        help="Show accumulated proposals and exit")
    parser.add_argument("--json", action="store_true",
                        help="Output status in JSON")

    args = parser.parse_args()

    # Status mode
    if args.status:
        show_status(as_json=args.json)
        return

    # Build prospector
    prospector = SongProspector(
        dry_run=args.dry_run,
        model=args.model,
        batch_size=args.batch_size,
        interval=args.interval,
        min_confidence=args.min_confidence,
    )

    # Signal handling
    def handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. Stopping Song Prospector...")
        prospector.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Run
    asyncio.run(daemon_loop(prospector, single=args.once))


if __name__ == "__main__":
    main()
