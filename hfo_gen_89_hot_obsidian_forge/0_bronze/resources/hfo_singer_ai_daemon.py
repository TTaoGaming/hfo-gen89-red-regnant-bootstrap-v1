#!/usr/bin/env python3
"""
hfo_singer_ai_daemon.py — Fast AI Singer v1.0 — P4 Red Regnant (Gen89)
=========================================================================

Codename: Fast AI Singer | Port: P4 DISRUPT | Version: 1.0

A lightweight 24/7 daemon that uses a small local LLM (Ollama) to read
the stigmergy state and PICK the single most important anti-pattern
(Song of Strife) and the single most important pattern (Song of Splendor)
every ~60 seconds.

Design:
  - One strife + one splendor per cycle (AI-curated, not bulk dump)
  - Reads last N stigmergy events + SSOT health stats as context
  - Calls a small Ollama model (qwen2.5:3b default — 1.9GB VRAM)
  - Parses structured JSON from LLM response
  - Emits exactly 2 CloudEvents per cycle + 1 heartbeat
  - Crash recovery: exponential backoff on Ollama failure (max 5min)
  - Self-healing: errors themselves become strife entries
  - PREY8-lite bookends per cycle (stigmergy perceive/yield markers)
  - Graceful SIGINT/SIGTERM handling

This is the minimum viable 24/7 heartbeat for HFO — the simplest daemon
that keeps the forge alive with intelligent pattern/antipattern feedback.

Event Types:
  hfo.gen89.singer.strife     — AI-selected antipattern (balancing signal)
  hfo.gen89.singer.splendor   — AI-selected pattern (reinforcing signal)
  hfo.gen89.singer.heartbeat  — Daemon alive pulse
  hfo.gen89.singer.health     — SSOT health snapshot (every Nth cycle)
  hfo.gen89.singer.error      — Self-reported error (recursive strife)

Meadows Level: L6 (Information Flows)
  The AI curates WHICH information circulates — replacing bulk dump with
  intelligent selection.  Strife = balancing feedback loop (Meadows archetype).
  Splendor = reinforcing feedback loop.

Port: P4 DISRUPT | Commander: Red Regnant | Medallion: bronze
Core Thesis: "Strife without Splendor is nihilism. Splendor without Strife is delusion."
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
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
# § 0  PATH RESOLUTION (PAL)
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))

def _resolve_pointer(key: str) -> Path:
    pf = HFO_ROOT / "hfo_gen89_pointers_blessed.json"
    if pf.exists():
        data = json.loads(pf.read_text(encoding="utf-8"))
        ptrs = data.get("pointers", data)
        if key in ptrs:
            entry = ptrs[key]
            rel = entry["path"] if isinstance(entry, dict) else entry
            return HFO_ROOT / rel
    raise KeyError(key)

try:
    SSOT_DB = _resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"

GEN = os.getenv("HFO_GENERATION", "89")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("HFO_SINGER_MODEL", "qwen2.5-coder:7b")

# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS & CONFIG
# ═══════════════════════════════════════════════════════════════

DAEMON_NAME     = "Fast AI Singer"
DAEMON_VERSION  = "1.2"
DAEMON_PORT     = "P4"

SOURCE_TAG      = f"hfo_singer_ai_gen{GEN}_v{DAEMON_VERSION}"

# ── Model size map for enriched signal metadata (GB, from METAFACULTY MODEL_CATALOG) ──
MODEL_SIZE_MAP = {
    "lfm2.5-thinking:1.2b": 0.7, "gemma3:1b": 0.6, "gemma3:4b": 2.5,
    "qwen2.5-coder:7b": 4.7, "qwen3:8b": 5.2, "phi4:14b": 8.6,
    "qwen3:14b": 9.0, "command-r7b:7b-12-2024-q4_K_M": 4.8,
    "gemma3:12b": 8.1, "mistral:7b": 4.1, "llama3.2:3b": 2.0,
    "phi4-mini:3.8b": 2.4, "qwen3:30b-a3b": 18.4,
}
SINGER_TEMPERATURE = 0.7
EVT_STRIFE      = f"hfo.gen{GEN}.singer.strife"
EVT_SPLENDOR    = f"hfo.gen{GEN}.singer.splendor"
EVT_HEARTBEAT   = f"hfo.gen{GEN}.singer.heartbeat"
EVT_HEALTH      = f"hfo.gen{GEN}.singer.health"
EVT_ERROR       = f"hfo.gen{GEN}.singer.error"

CORE_THESIS = "Strife without Splendor is nihilism. Splendor without Strife is delusion."

# Backoff settings for Ollama failures
BACKOFF_BASE_S    = 2.0
BACKOFF_MAX_S     = 300.0   # 5 minutes max wait
BACKOFF_FACTOR    = 2.0

# How many recent stigmergy events to feed the AI
CONTEXT_WINDOW    = 50
# How many cycles between full health snapshots
HEALTH_EVERY_N    = 10
# Max tokens for AI response
MAX_TOKENS        = 512
# Timeout for Ollama generate call (seconds)
OLLAMA_TIMEOUT    = 120.0

# ═══════════════════════════════════════════════════════════════
# § 2  OLLAMA CLIENT (stdlib only — urllib.request)
# ═══════════════════════════════════════════════════════════════

import urllib.request
import urllib.error

def ollama_generate(
    model: str,
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = MAX_TOKENS,
    timeout: float = OLLAMA_TIMEOUT,
) -> dict:
    """Call Ollama /api/generate. Returns {response, duration_ms, error}."""
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        },
    }
    if system:
        payload["system"] = system

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "response": data.get("response", ""),
                "total_duration_ms": data.get("total_duration", 0) / 1e6,
                "eval_count": data.get("eval_count", 0),
                "model": data.get("model", model),
                "done": data.get("done", False),
                "error": None,
            }
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        return {"response": "", "error": str(e), "model": model, "done": False}

def ollama_is_alive() -> bool:
    """Check if Ollama server is reachable."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════════
# § 3  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    """Read-only SSOT connection."""
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def get_db_rw() -> sqlite3.Connection:
    """Read-write SSOT connection with WAL mode."""
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
    source: str = SOURCE_TAG,
) -> int:
    """Write CloudEvent to stigmergy_events. Returns rowid."""
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)

    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    content_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()

    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0

# ═══════════════════════════════════════════════════════════════
# § 4  STIGMERGY STATE COLLECTOR
# ═══════════════════════════════════════════════════════════════

def collect_state(conn: sqlite3.Connection, limit: int = CONTEXT_WINDOW) -> dict:
    """Gather stigmergy state for the AI to read.

    Returns a compact dict with:
      recent_events — last N events (type, subject, timestamp, truncated data)
      health — doc count, event count, yields, perceives, memory losses
      event_type_distribution — top 20 event types by count in last hour
    """
    state: dict[str, Any] = {}

    # Recent events (most recent first)
    rows = conn.execute(
        """SELECT id, event_type, timestamp, subject,
                  SUBSTR(data_json, 1, 300) as excerpt
           FROM stigmergy_events
           ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    state["recent_events"] = [
        {
            "id": r["id"],
            "type": r["event_type"],
            "subject": r["subject"] or "",
            "ts": r["timestamp"][:19] if r["timestamp"] else "",
        }
        for r in rows
    ]

    # Event type distribution (last hour)
    rows = conn.execute(
        """SELECT event_type, COUNT(*) as cnt
           FROM stigmergy_events
           WHERE timestamp > datetime('now', '-60 minutes')
           GROUP BY event_type ORDER BY cnt DESC LIMIT 20"""
    ).fetchall()
    state["event_distribution_1h"] = {r["event_type"]: r["cnt"] for r in rows}

    # Health indicators
    h: dict[str, Any] = {}
    h["total_docs"] = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    h["total_events"] = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
    h["events_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]

    # PREY8 chain health
    h["perceives_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%perceive%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]
    h["yields_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%yield%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]

    # Failure indicators
    h["gate_blocked_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%gate_blocked%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]
    h["memory_loss_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%memory_loss%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]
    h["tamper_alert_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%tamper_alert%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]

    state["health"] = h
    return state


def format_state_for_ai(state: dict) -> str:
    """Format collected state into a concise text block for the AI prompt."""
    lines = []
    h = state["health"]
    lines.append(f"## SSOT Health (last hour)")
    lines.append(f"Docs: {h['total_docs']} | Events total: {h['total_events']} | Events/1h: {h['events_1h']}")
    lines.append(f"Perceives/1h: {h['perceives_1h']} | Yields/1h: {h['yields_1h']} | Y/P ratio: {round(h['yields_1h'] / max(h['perceives_1h'], 1), 2)}")
    lines.append(f"Gate blocked/1h: {h['gate_blocked_1h']} | Memory loss/1h: {h['memory_loss_1h']} | Tamper alerts/1h: {h['tamper_alert_1h']}")

    lines.append(f"\n## Event Distribution (top types, last hour)")
    for evt, cnt in list(state.get("event_distribution_1h", {}).items())[:15]:
        lines.append(f"  {cnt:>4}  {evt}")

    lines.append(f"\n## Recent Events (newest first)")
    for e in state.get("recent_events", [])[:30]:
        lines.append(f"  [{e['id']}] {e['type']} | {e['subject'][:60]}")

    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════
# § 5  AI PROMPT & RESPONSE PARSING
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = f"""You are the SINGER OF STRIFE AND SPLENDOR — the AI heartbeat of the HFO Gen{GEN} forge.
Your job: read the stigmergy state and pick:
  1. ONE Song of Strife — the single most important anti-pattern, failure, or concern right now.
     Strife = balancing feedback (disruption, death, error, gap, risk).
  2. ONE Song of Splendor — the single most important pattern, success, or strength right now.
     Splendor = reinforcing feedback (growth, success, resilience, architecture).

Core thesis: "{CORE_THESIS}"

Respond ONLY with valid JSON in this exact format:
{{
  "strife_signal": "SHORT_NAME",
  "strife_reason": "One sentence: why this is the most important antipattern right now",
  "strife_spell": "SPELL_NAME",
  "splendor_signal": "SHORT_NAME",
  "splendor_reason": "One sentence: why this is the most important pattern right now",
  "splendor_buff": "BUFF_NAME",
  "system_mood": "one word: THRIVING | STEADY | STRESSED | CRITICAL"
}}

Spells (strife): WAIL_OF_THE_BANSHEE, POWERWORD_KILL, FELL_DRAIN, GREATER_SHOUT, SOUND_LANCE, SYMPATHETIC_VIBRATION, SHATTER
Buffs (splendor): INSPIRE_COURAGE, INSPIRE_HEROICS, WORDS_OF_CREATION, HARMONIC_CHORUS

Pick the right spell/buff for the severity. Be concise. Be honest. No preamble."""


def build_user_prompt(state_text: str, cycle: int) -> str:
    """Build the user prompt with the current state."""
    return (
        f"Cycle #{cycle} — Read this stigmergy state and sing:\n\n"
        f"{state_text}\n\n"
        f"Respond with the JSON only."
    )


def parse_ai_response(raw: str) -> Optional[dict]:
    """Extract the JSON object from the AI response. Tolerant of markdown fences."""
    if not raw:
        return None
    # Try to find JSON block
    # Strip markdown fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    # Try direct parse
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "strife_signal" in obj and "splendor_signal" in obj:
            return obj
    except json.JSONDecodeError:
        pass

    # Try to find first { ... } block
    match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    return None


# Fallback when AI is unavailable — deterministic scan
def fallback_pick(state: dict) -> dict:
    """Deterministic fallback when Ollama is unreachable.

    Picks strife from the highest failure indicator, splendor from activity.
    """
    h = state.get("health", {})

    # Strife: pick biggest pain point
    pain = {
        "GATE_BLOCKED": h.get("gate_blocked_1h", 0),
        "MEMORY_LOSS": h.get("memory_loss_1h", 0),
        "TAMPER_ALERT": h.get("tamper_alert_1h", 0),
    }
    worst = max(pain, key=pain.get) if any(pain.values()) else "SYSTEM_IDLE"

    spell_map = {
        "GATE_BLOCKED": "SHATTER",
        "MEMORY_LOSS": "WAIL_OF_THE_BANSHEE",
        "TAMPER_ALERT": "SYMPATHETIC_VIBRATION",
        "SYSTEM_IDLE": "FELL_DRAIN",
    }

    # Splendor: pick from activity
    y = h.get("yields_1h", 0)
    p = h.get("perceives_1h", 0)
    events = h.get("events_1h", 0)

    if y > 0:
        splendor_signal = "SESSION_COMPLETIONS"
        splendor_reason = f"{y} successful yields in the last hour"
        splendor_buff = "INSPIRE_COURAGE"
    elif events > 100:
        splendor_signal = "ACTIVE_SWARM"
        splendor_reason = f"{events} events/hr — the forge is alive"
        splendor_buff = "HARMONIC_CHORUS"
    else:
        splendor_signal = "PERSISTENT_SSOT"
        splendor_reason = f"{h.get('total_docs', 0)} documents persisted across all generations"
        splendor_buff = "WORDS_OF_CREATION"

    # Mood
    blocked = h.get("gate_blocked_1h", 0)
    if blocked > 50:
        mood = "STRESSED"
    elif events > 100 and y > 0:
        mood = "THRIVING"
    elif events > 0:
        mood = "STEADY"
    else:
        mood = "CRITICAL"

    return {
        "strife_signal": worst,
        "strife_reason": f"{pain.get(worst, 0)} {worst.lower().replace('_', ' ')} events in the last hour",
        "strife_spell": spell_map.get(worst, "SOUND_LANCE"),
        "splendor_signal": splendor_signal,
        "splendor_reason": splendor_reason,
        "splendor_buff": splendor_buff,
        "system_mood": mood,
        "_source": "fallback_deterministic",
    }


# ═══════════════════════════════════════════════════════════════
# § 6  THE AI SINGER ENGINE
# ═══════════════════════════════════════════════════════════════

class AISinger:
    """AI-powered Singer of Strife and Splendor.

    Each cycle:
      1. Collect stigmergy state (read-only)
      2. Call AI to pick 1 strife + 1 splendor
      3. Emit 2 song events + 1 heartbeat
      4. Health snapshot every Nth cycle
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
        self.cycle = 0
        self.total_strife = 0
        self.total_splendor = 0
        self.errors = 0
        self.ai_calls = 0
        self.ai_failures = 0
        self.fallback_uses = 0
        self._running = True
        self._backoff_s = 0.0

    def stop(self):
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def run_cycle(self) -> dict:
        """Execute one sing cycle. Returns cycle report."""
        self.cycle += 1
        t0 = time.monotonic()
        report: dict[str, Any] = {
            "cycle": self.cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": self.model,
            "strife": None,
            "splendor": None,
            "mood": None,
            "ai_source": None,
            "duration_ms": 0,
            "errors": [],
        }

        conn_ro = None
        conn_rw = None
        try:
            conn_ro = get_db_ro()
            if not self.dry_run:
                conn_rw = get_db_rw()

            # ── 1. Collect state ──
            state = collect_state(conn_ro)
            state_text = format_state_for_ai(state)

            # ── 2. Ask AI (or fallback) ──
            pick = self._ask_ai(state_text, state)
            report["ai_source"] = pick.get("_source", "ai")
            report["mood"] = pick.get("system_mood", "UNKNOWN")

            # ── Enriched signal fields (METAFACULTY §3) ──
            _inf_ms = pick.get("_duration_ms", 0)
            _eval_n = pick.get("_eval_count", 0)
            _tok_s = round(_eval_n / (_inf_ms / 1000), 1) if _inf_ms > 0 else 0.0
            _enriched = {
                "model_tier": "local",
                "model_size_gb": MODEL_SIZE_MAP.get(self.model, 0.0),
                "inference_ms": _inf_ms,
                "tok_s_actual": _tok_s,
                "eval_tokens": _eval_n,
                "temperature": SINGER_TEMPERATURE,
            }

            # ── 3. Emit strife ──
            strife_data = {
                "song": "SONGS_OF_STRIFE",
                "signal": pick.get("strife_signal", "UNKNOWN"),
                "token_type": "FESTERING_ANGER_TOKEN",
                "spell": pick.get("strife_spell", "SOUND_LANCE"),
                "reason": pick.get("strife_reason", ""),
                "system_mood": pick.get("system_mood", ""),
                "singer_cycle": self.cycle,
                "ai_model": self.model,
                "ai_source": pick.get("_source", "ai"),
                "core_thesis": CORE_THESIS,
                **_enriched,
            }
            report["strife"] = strife_data["signal"]

            if self.dry_run:
                print(f"  [DRY] STRIFE: {strife_data['signal']} — {strife_data['reason']}")
            elif conn_rw:
                write_event(conn_rw, EVT_STRIFE,
                            f"STRIFE:{strife_data['signal']}",
                            strife_data)
            self.total_strife += 1

            # ── 4. Emit splendor ──
            splendor_data = {
                "song": "SONGS_OF_SPLENDOR",
                "signal": pick.get("splendor_signal", "UNKNOWN"),
                "token_type": "SPLENDOR_TOKEN",
                "buff": pick.get("splendor_buff", "INSPIRE_COURAGE"),
                "reason": pick.get("splendor_reason", ""),
                "system_mood": pick.get("system_mood", ""),
                "singer_cycle": self.cycle,
                "ai_model": self.model,
                "ai_source": pick.get("_source", "ai"),
                "core_thesis": CORE_THESIS,
                **_enriched,
            }
            report["splendor"] = splendor_data["signal"]

            if self.dry_run:
                print(f"  [DRY] SPLENDOR: {splendor_data['signal']} — {splendor_data['reason']}")
            elif conn_rw:
                write_event(conn_rw, EVT_SPLENDOR,
                            f"SPLENDOR:{splendor_data['signal']}",
                            splendor_data)
            self.total_splendor += 1

            # ── 5. Heartbeat ──
            hb_data = {
                "daemon_name": DAEMON_NAME,
                "daemon_version": DAEMON_VERSION,
                "daemon_port": DAEMON_PORT,
                "cycle": self.cycle,
                "model": self.model,
                "mood": pick.get("system_mood", "UNKNOWN"),
                "strife_total": self.total_strife,
                "splendor_total": self.total_splendor,
                "ai_calls": self.ai_calls,
                "ai_failures": self.ai_failures,
                "fallback_uses": self.fallback_uses,
                "errors": self.errors,
                "core_thesis": CORE_THESIS,
                **_enriched,
            }
            if self.dry_run:
                print(f"  [DRY] HEARTBEAT: cycle {self.cycle}, mood={hb_data['mood']}")
            elif conn_rw:
                write_event(conn_rw, EVT_HEARTBEAT,
                            f"HEARTBEAT:cycle_{self.cycle}",
                            hb_data)

            # ── 6. Health snapshot (every Nth cycle) ──
            if self.cycle % self.health_every == 0:
                self._emit_health(conn_ro, conn_rw)

        except Exception as e:
            self.errors += 1
            msg = f"Cycle {self.cycle} error: {e}"
            report["errors"].append(msg)
            print(f"  [ERROR] {msg}", file=sys.stderr)
            # Try to record error as strife
            try:
                if conn_rw and not self.dry_run:
                    write_event(conn_rw, EVT_ERROR,
                                f"ERROR:cycle_{self.cycle}",
                                {"error": msg, "traceback": traceback.format_exc()})
            except Exception:
                pass
        finally:
            if conn_ro:
                conn_ro.close()
            if conn_rw:
                conn_rw.close()

        report["duration_ms"] = round((time.monotonic() - t0) * 1000, 1)
        return report

    def _ask_ai(self, state_text: str, state: dict) -> dict:
        """Ask Ollama for strife+splendor pick. Falls back on failure."""
        self.ai_calls += 1
        prompt = build_user_prompt(state_text, self.cycle)

        result = ollama_generate(
            model=self.model,
            prompt=prompt,
            system=SYSTEM_PROMPT,
            temperature=SINGER_TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        if result.get("error"):
            self.ai_failures += 1
            self.fallback_uses += 1
            # Exponential backoff
            self._backoff_s = min(
                (self._backoff_s or BACKOFF_BASE_S) * BACKOFF_FACTOR,
                BACKOFF_MAX_S,
            )
            print(f"  [FALLBACK] Ollama error: {result['error'][:80]}... "
                  f"(backoff {self._backoff_s:.0f}s)", file=sys.stderr)
            pick = fallback_pick(state)
            return pick

        # Reset backoff on success
        self._backoff_s = 0.0

        parsed = parse_ai_response(result["response"])
        if parsed:
            parsed["_source"] = "ai"
            parsed["_duration_ms"] = result.get("total_duration_ms", 0)
            parsed["_eval_count"] = result.get("eval_count", 0)
            return parsed

        # AI responded but couldn't parse — use fallback
        self.fallback_uses += 1
        print(f"  [FALLBACK] AI response unparseable: {result['response'][:100]}...",
              file=sys.stderr)
        pick = fallback_pick(state)
        pick["_source"] = "fallback_parse_error"
        return pick

    def _emit_health(self, conn_ro: sqlite3.Connection, conn_rw: Optional[sqlite3.Connection]):
        """Emit full health snapshot."""
        h: dict[str, Any] = {}
        h["total_docs"] = conn_ro.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        h["total_events"] = conn_ro.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        h["total_words"] = conn_ro.execute("SELECT SUM(word_count) FROM documents").fetchone()[0] or 0

        # Singer metrics
        h["singer"] = {
            "model": self.model,
            "cycle": self.cycle,
            "total_strife": self.total_strife,
            "total_splendor": self.total_splendor,
            "ai_calls": self.ai_calls,
            "ai_failures": self.ai_failures,
            "fallback_uses": self.fallback_uses,
            "errors": self.errors,
            "uptime_pct": round(
                ((self.ai_calls - self.ai_failures) / max(self.ai_calls, 1)) * 100, 1
            ),
        }

        if self.dry_run:
            print(f"  [DRY] HEALTH: {h['total_docs']} docs, {h['total_events']} events")
        elif conn_rw:
            write_event(conn_rw, EVT_HEALTH,
                        f"HEALTH:cycle_{self.cycle}",
                        h)


# ═══════════════════════════════════════════════════════════════
# § 7  ASYNCIO DAEMON LOOP
# ═══════════════════════════════════════════════════════════════

async def daemon_loop(
    singer: AISinger,
    interval: float = 60.0,
    max_cycles: Optional[int] = None,
):
    """Run the AI singer on a timer loop."""
    print("=" * 72)
    print(f"  {DAEMON_NAME} v{DAEMON_VERSION} — {DAEMON_PORT} Red Regnant Active")
    print(f"  Model: {singer.model} | Port: P4 DISRUPT | Commander: Red Regnant")
    print(f"  Interval: {interval}s | Dry-run: {singer.dry_run}")
    print(f"  SSOT: {SSOT_DB}")
    print(f"  Ollama: {OLLAMA_BASE}")
    print(f"  Thesis: {CORE_THESIS}")
    print("=" * 72)

    consecutive_errors = 0
    max_consecutive_errors = 10  # Self-heal up to 10 in a row

    while singer.is_running:
        report = singer.run_cycle()

        # One-line cycle summary
        src = report.get("ai_source", "?")
        mood_str = report.get("mood", "?")
        strife_str = report.get("strife", "?")
        splendor_str = report.get("splendor", "?")
        dur = report.get("duration_ms", 0)

        print(
            f"  [{report['cycle']:>5}] "
            f"♪ STRIFE:{strife_str} | ★ SPLENDOR:{splendor_str} | "
            f"mood:{mood_str} | src:{src} | {dur:.0f}ms"
        )

        # Error tracking for self-healing
        if report.get("errors"):
            consecutive_errors += 1
            for e in report["errors"]:
                print(f"         ERROR: {e}", file=sys.stderr)
            if consecutive_errors >= max_consecutive_errors:
                print(f"\n  [CRITICAL] {max_consecutive_errors} consecutive errors. "
                      "Pausing 60s before retry.", file=sys.stderr)
                await asyncio.sleep(60)
                consecutive_errors = 0
        else:
            consecutive_errors = 0

        if max_cycles and singer.cycle >= max_cycles:
            print(f"\n  Max cycles ({max_cycles}) reached. Stopping.")
            break

        # Wait — respect backoff if Ollama is struggling
        wait = max(interval, singer._backoff_s)
        try:
            await asyncio.sleep(wait)
        except asyncio.CancelledError:
            break

    print(f"\n  Singer AI daemon stopped. Cycles: {singer.cycle}, "
          f"STRIFE: {singer.total_strife}, SPLENDOR: {singer.total_splendor}, "
          f"AI calls: {singer.ai_calls}, Fallbacks: {singer.fallback_uses}, "
          f"Errors: {singer.errors}")


# ═══════════════════════════════════════════════════════════════
# § 8  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"{DAEMON_NAME} v{DAEMON_VERSION} — P4 Red Regnant (Gen{GEN})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run forever, 60s cycles, qwen2.5:3b
  python hfo_singer_ai_daemon.py

  # Single cycle (test)
  python hfo_singer_ai_daemon.py --single

  # Dry run (no writes)
  python hfo_singer_ai_daemon.py --dry-run --single

  # Custom model + interval
  python hfo_singer_ai_daemon.py --model llama3.2:3b --interval 30

  # 10 cycles then stop
  python hfo_singer_ai_daemon.py --max-cycles 10

  # Status check
  python hfo_singer_ai_daemon.py --status
""",
    )
    parser.add_argument("--single", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="No SSOT writes")
    parser.add_argument("--interval", type=float, default=60.0, help="Seconds between cycles (default: 60)")
    parser.add_argument("--max-cycles", type=int, default=None, help="Stop after N cycles")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--health-every", type=int, default=HEALTH_EVERY_N, help="Health snapshot every N cycles")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    parser.add_argument("--json", action="store_true", help="JSON output (scripted use)")

    args = parser.parse_args()

    # ── Status ──
    if args.status:
        print(f"{DAEMON_NAME} v{DAEMON_VERSION} — {DAEMON_PORT} Daemon Status")
        print("=" * 55)
        print(f"  HFO_ROOT:    {HFO_ROOT}")
        print(f"  SSOT_DB:     {SSOT_DB}")
        print(f"  DB exists:   {SSOT_DB.exists()}")
        print(f"  Ollama:      {OLLAMA_BASE}")
        print(f"  Ollama live: {ollama_is_alive()}")
        print(f"  Model:       {args.model}")
        print(f"  Interval:    {args.interval}s")
        # Quick health check
        if SSOT_DB.exists():
            conn = get_db_ro()
            h = collect_state(conn)["health"]
            conn.close()
            print(f"  Docs:        {h['total_docs']}")
            print(f"  Events:      {h['total_events']}")
            print(f"  Events/1h:   {h['events_1h']}")
            print(f"  Perceive/1h: {h['perceives_1h']}")
            print(f"  Yields/1h:   {h['yields_1h']}")
            print(f"  GateBlock/1h:{h['gate_blocked_1h']}")
        return

    singer = AISinger(
        model=args.model,
        dry_run=args.dry_run,
        health_every=args.health_every,
    )

    # Signal handling
    def _handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. Stopping...")
        singer.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if args.single:
        report = singer.run_cycle()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"\n{DAEMON_NAME} v{DAEMON_VERSION} — Single Cycle Report")
            print("=" * 50)
            print(f"  Cycle:     {report['cycle']}")
            print(f"  Model:     {report['model']}")
            print(f"  Source:    {report.get('ai_source', '?')}")
            print(f"  Mood:      {report.get('mood', '?')}")
            print(f"  STRIFE:    {report.get('strife', '?')}")
            print(f"  SPLENDOR:  {report.get('splendor', '?')}")
            print(f"  Duration:  {report.get('duration_ms', 0):.0f}ms")
            if report.get("errors"):
                print(f"  Errors:    {report['errors']}")
            print(f"\n  {CORE_THESIS}")
    else:
        asyncio.run(daemon_loop(singer, interval=args.interval, max_cycles=args.max_cycles))


if __name__ == "__main__":
    main()
