#!/usr/bin/env python3
"""
hfo_p5_dancer_daemon.py — Fast AI Dancer v1.0 — P5 Pyre Praetorian (Gen89)
==========================================================

Codename: Fast AI Dancer | Port: P5 IMMUNIZE | Version: 1.0

A 24/7 strange-loop daemon that dances through the P5 spell portfolio
every ~60 seconds, reading the system state and recommending which
divine spell the swarm should cast next.

THE DANCER DOES NOT ACT. THE DANCER DANCES.
The dance IS the recommendation. The swarm reads the pheromone trail.

Design:
  Mirror of hfo_singer_ai_daemon.py (P4), but P5 Paladin flavored:
  - P4 Singer: sings Songs of Strife & Splendor → antipatterns/patterns
  - P5 Dancer: dances Steps of Death & Dawn → defensive recommendations

  Each cycle the Dancer reads stigmergy state + SSOT health, then picks:
    1. One DEATH step — what needs to be destroyed/purged/warded RIGHT NOW
    2. One DAWN step — what needs to be resurrected/protected/healed RIGHT NOW

  Each step IS a spell from the P5 grimoire (PHB only, zero homebrew):

  DEATH (Yin — the pyre burns, the sword strikes):
    FLAME_STRIKE     — "Purge this specific artifact/daemon/document"
    FIRE_SHIELD      — "Register this resource under lifecycle protection"
    PRISMATIC_WALL   — "This defense layer has a gap — reinforce it"
    SLAY_LIVING      — "Kill this process/session — it's beyond saving"

  DAWN (Yang — the phoenix rises, the ward holds):
    CONTINGENCY      — "Set this IF-THEN trigger for automated defense"
    DEATH_WARD       — "Protect this daemon from dying — ward it"
    RESURRECTION     — "This dead component should be brought back"
    HOLY_AURA        — "The governance ward is holding — maintain vigil"

  The AI picks the right spell from each aspect based on severity.
  The dance step + reasoning is emitted as stigmergy CloudEvents.
  P4 sings what's wrong and what's right.
  P5 dances what to destroy and what to protect.
  Together: the adversarial coach (P4) and the divine defender (P5).

Event Types:
  hfo.gen89.dancer.death       — DEATH dance step (purge/ward/defend/kill recommendation)
  hfo.gen89.dancer.dawn        — DAWN dance step (contingency/ward/resurrect/aura recommendation)
  hfo.gen89.dancer.heartbeat   — Dancer alive pulse
  hfo.gen89.dancer.health      — Full health snapshot (every Nth cycle)
  hfo.gen89.dancer.error       — Self-reported error (recursive death)

Strange Loop:
  The Dancer reads stigmergy (including P4 Singer events) and recommends.
  The recommendations become stigmergy events.
  Future Dancer cycles read their own past recommendations.
  The Dancer dances to its own rhythm — the strange loop.

Meadows Level: L5 (Negative Feedback — control mechanisms)
  The Dancer is the immune system's feedback signal.
  Death steps = corrective action recommendations.
  Dawn steps = protective maintenance recommendations.

Port: P5 IMMUNIZE | Commander: Pyre Praetorian | Medallion: bronze
Class: Sword Dancer Paladin — fire and resurrection
Core Thesis: "Death without Dawn is nihilism. Dawn without Death is stagnation."
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

import psutil

# Resource governor — hard 80% GPU ceiling
try:
    _rg_dir = str(Path(__file__).resolve().parent)
    if _rg_dir not in sys.path:
        sys.path.insert(0, _rg_dir)
    from hfo_resource_governor import (
        wait_for_gpu_headroom as _wait_gpu_headroom,
        start_background_monitor as _start_rg_monitor,
    )
    _RESOURCE_GOVERNOR_AVAILABLE = True
except ImportError:
    _RESOURCE_GOVERNOR_AVAILABLE = False
    def _wait_gpu_headroom(*a, **kw): return True
    def _start_rg_monitor(*a, **kw): pass

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
DEFAULT_MODEL = os.getenv("HFO_P5_MODEL", "gemma3:4b")

# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS & CONFIG — THE DIVINE PORTFOLIO
# ═══════════════════════════════════════════════════════════════

DAEMON_NAME      = "Fast AI Dancer"
DAEMON_VERSION   = "1.2"
DAEMON_PORT      = "P5"

SOURCE_TAG       = f"hfo_dancer_gen{GEN}_v{DAEMON_VERSION}"

# ── Model size map for enriched signal metadata (GB, from METAFACULTY MODEL_CATALOG) ──
MODEL_SIZE_MAP = {
    "lfm2.5-thinking:1.2b": 0.7, "gemma3:1b": 0.6, "gemma3:4b": 2.5,
    "qwen2.5-coder:7b": 4.7, "qwen3:8b": 5.2, "phi4:14b": 8.6,
    "qwen3:14b": 9.0, "command-r7b:7b-12-2024-q4_K_M": 4.8,
    "gemma3:12b": 8.1, "mistral:7b": 4.1, "llama3.2:3b": 2.0,
    "phi4-mini:3.8b": 2.4, "qwen3:30b-a3b": 18.4,
}
DANCER_TEMPERATURE = 0.4  # Paladin is more decisive than the Singer
EVT_DEATH        = f"hfo.gen{GEN}.dancer.death"
EVT_DAWN         = f"hfo.gen{GEN}.dancer.dawn"
EVT_HEARTBEAT    = f"hfo.gen{GEN}.dancer.heartbeat"
EVT_HEALTH       = f"hfo.gen{GEN}.dancer.health"
EVT_ERROR        = f"hfo.gen{GEN}.dancer.error"

CORE_THESIS = "Death without Dawn is nihilism. Dawn without Death is stagnation."

# The P5 Spell Portfolio — all PHB, zero homebrew
# Each spell is a recommendation category the Dancer can pick
DEATH_SPELLS = {
    "FLAME_STRIKE": {
        "phb": "PHB p.231, Evocation 5th",
        "alias": "Targeted divine purge",
        "severity": "HIGH",
        "when": "A specific failed artifact, stale daemon, or corrupted document must be destroyed",
    },
    "FIRE_SHIELD": {
        "phb": "PHB p.230, Evocation 4th",
        "alias": "Lifecycle ward armor",
        "severity": "MEDIUM",
        "when": "A resource needs lifecycle registration/protection, or retaliatory disposal on violation",
    },
    "PRISMATIC_WALL": {
        "phb": "PHB p.264, Abjuration 9th",
        "alias": "7-layer defense gap",
        "severity": "CRITICAL",
        "when": "A defense layer has a gap — medallion bypass, missing validation, schema breach",
    },
    "SLAY_LIVING": {
        "phb": "PHB p.280, Necromancy 5th",
        "alias": "Decisive mercy kill",
        "severity": "HIGH",
        "when": "A process/session/daemon is beyond saving and must be cleanly terminated",
    },
}

DAWN_SPELLS = {
    "CONTINGENCY": {
        "phb": "PHB p.213, Evocation 6th",
        "alias": "IF-THEN defense trigger",
        "severity": "MEDIUM",
        "when": "An automated defense rule should be set — if X then Y without human decision",
    },
    "DEATH_WARD": {
        "phb": "PHB p.217, Necromancy 4th (Paladin 4th)",
        "alias": "Daemon death prevention",
        "severity": "HIGH",
        "when": "A healthy daemon/process is at risk and needs preemptive protection",
    },
    "RESURRECTION": {
        "phb": "PHB p.272, Conjuration 7th",
        "alias": "Fleet resurrection",
        "severity": "CRITICAL",
        "when": "A dead component that should be alive needs to be brought back NOW",
    },
    "HOLY_AURA": {
        "phb": "PHB p.241, Abjuration 8th",
        "alias": "Governance vigil maintained",
        "severity": "LOW",
        "when": "All systems nominal — the ward holds, maintain the vigil, no action needed",
    },
}

# Backoff settings for Ollama failures
BACKOFF_BASE_S    = 2.0
BACKOFF_MAX_S     = 300.0
BACKOFF_FACTOR    = 2.0

# How many recent stigmergy events to feed the AI
CONTEXT_WINDOW    = 50
# How many cycles between full health snapshots
HEALTH_EVERY_N    = 10
# How many cycles between governance patrols (absorbed from hfo_p5_daemon.py)
GOV_PATROL_EVERY  = 5
# Max tokens for AI response
MAX_TOKENS        = 512
# Timeout for Ollama generate call (seconds)
OLLAMA_TIMEOUT    = 120.0

# ── P5 Governance Patrol (consolidated from hfo_p5_daemon.py) ──
# The Dancer now absorbs the 5 patrol tasks as a lightweight
# governance check every GOV_PATROL_EVERY cycles.
EVT_GOV_PATROL   = f"hfo.gen{GEN}.dancer.governance_patrol"

try:
    from hfo_p5_pyre_praetorian import (
        ring0_cantrip_check as _p5_cantrip_check,
    )
    P5_CANTRIPS_AVAILABLE = True
except ImportError:
    P5_CANTRIPS_AVAILABLE = False

try:
    from hfo_stigmergy_watchdog import (
        scan_all_anomalies as _watchdog_scan,
    )
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
# § 2  OLLAMA CLIENT (stdlib only — urllib.request)
# ═══════════════════════════════════════════════════════════════

import urllib.request
import urllib.error
from hfo_ssot_write import get_db_readwrite as get_db_rw

def ollama_generate(
    model: str,
    prompt: str,
    system: str = "",
    temperature: float = 0.4,
    max_tokens: int = MAX_TOKENS,
    timeout: float = OLLAMA_TIMEOUT,
) -> dict:
    """Call Ollama /api/generate. Returns {response, duration_ms, error}.
    Resource governor gate: waits for VRAM headroom (80% ceiling) before calling.
    keep_alive=0s evicts model from VRAM immediately after call.
    """
    if _RESOURCE_GOVERNOR_AVAILABLE:
        ok = _wait_gpu_headroom(caller="dancer_ollama", verbose=False)
        if not ok:
            return {"response": "", "error": "VRAM budget saturated", "model": model, "done": False}
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "0s",   # evict model from VRAM immediately after call
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

def write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
    source: str = SOURCE_TAG,
) -> int:
    """Write CloudEvent to stigmergy_events. Returns rowid.
    
    Auto-injects signal_metadata if not already present.
    """
    # ── Signal metadata auto-injection (8^N coordinator retrofit) ──
    if "signal_metadata" not in data:
        try:
            from hfo_signal_shim import build_signal_metadata
            data["signal_metadata"] = build_signal_metadata(
                port=DAEMON_PORT,
                model_id=data.get("ai_model", data.get("model", DEFAULT_MODEL)),
                daemon_name=DAEMON_NAME,
                daemon_version=DAEMON_VERSION,
                inference_latency_ms=data.get("inference_ms", 0),
                tokens_out=data.get("eval_tokens", 0),
                task_type=event_type.split(".")[-1],
            )
        except Exception:
            pass  # Fail open — don't break daemon if shim missing
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
# § 4  STATE COLLECTOR — THE DANCER'S SENSES
# ═══════════════════════════════════════════════════════════════

def collect_state(conn: sqlite3.Connection, limit: int = CONTEXT_WINDOW) -> dict:
    """Gather system state for the Dancer to read.

    The Dancer reads what matters for DEFENSE:
      - Recent events (general awareness)
      - Singer events (P4's latest strife/splendor — the Dancer listens)
      - Session health (orphans, broken chains)
      - Process deaths (what needs resurrection?)
      - Governance violations (what needs warding?)
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

    # P4 Singer's latest songs — the Dancer listens to the Singer
    singer_events = conn.execute(
        """SELECT event_type, subject, SUBSTR(data_json, 1, 500) as excerpt
           FROM stigmergy_events
           WHERE event_type LIKE '%singer%'
           ORDER BY id DESC LIMIT 5"""
    ).fetchall()
    state["singer_songs"] = [
        {"type": r["event_type"], "subject": r["subject"] or ""}
        for r in singer_events
    ]

    # Previous Dancer recommendations — the strange loop
    dancer_events = conn.execute(
        """SELECT event_type, subject, SUBSTR(data_json, 1, 500) as excerpt
           FROM stigmergy_events
           WHERE event_type LIKE '%dancer%'
           ORDER BY id DESC LIMIT 5"""
    ).fetchall()
    state["own_last_dances"] = [
        {"type": r["event_type"], "subject": r["subject"] or ""}
        for r in dancer_events
    ]

    # Event type distribution (last hour)
    rows = conn.execute(
        """SELECT event_type, COUNT(*) as cnt
           FROM stigmergy_events
           WHERE timestamp > datetime('now', '-60 minutes')
           GROUP BY event_type ORDER BY cnt DESC LIMIT 20"""
    ).fetchall()
    state["event_distribution_1h"] = {r["event_type"]: r["cnt"] for r in rows}

    # Health indicators — the Dancer's vital signs
    h: dict[str, Any] = {}
    h["total_docs"] = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    h["total_events"] = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
    h["events_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]

    # PREY8 chain health — session completeness
    h["perceives_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%perceive%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]
    h["yields_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%yield%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]
    h["orphan_ratio"] = round(
        1.0 - (h["yields_1h"] / max(h["perceives_1h"], 1)), 2
    )

    # Failure indicators — the Dancer's threat assessment
    h["gate_blocked_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%gate_blocked%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]
    h["memory_loss_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%memory_loss%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]
    h["tamper_alert_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%tamper_alert%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]
    h["errors_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%error%' AND timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]

    # Threat score: 0 = peaceful, higher = more threats
    h["threat_score"] = (
        h["gate_blocked_1h"] * 2
        + h["memory_loss_1h"] * 3
        + h["tamper_alert_1h"] * 5
        + h["errors_1h"] * 1
        + int(h["orphan_ratio"] * 10)
    )

    state["health"] = h
    return state


def format_state_for_ai(state: dict) -> str:
    """Format collected state into a concise text block for the AI prompt."""
    lines = []
    h = state["health"]

    lines.append("## SYSTEM HEALTH (the Dancer's vital signs)")
    lines.append(f"Docs: {h['total_docs']} | Events total: {h['total_events']} | Events/1h: {h['events_1h']}")
    lines.append(f"Perceives/1h: {h['perceives_1h']} | Yields/1h: {h['yields_1h']} | Orphan ratio: {h['orphan_ratio']}")
    lines.append(f"Gate blocked/1h: {h['gate_blocked_1h']} | Memory loss/1h: {h['memory_loss_1h']} | Tamper alerts/1h: {h['tamper_alert_1h']}")
    lines.append(f"Errors/1h: {h['errors_1h']} | Threat score: {h['threat_score']}")

    lines.append("\n## P4 SINGER'S LATEST SONGS (the Dancer listens)")
    for s in state.get("singer_songs", [])[:3]:
        lines.append(f"  {s['type']} | {s['subject'][:80]}")
    if not state.get("singer_songs"):
        lines.append("  (no Singer events — Singer may be offline)")

    lines.append("\n## DANCER'S OWN LAST DANCES (the strange loop)")
    for d in state.get("own_last_dances", [])[:3]:
        lines.append(f"  {d['type']} | {d['subject'][:80]}")
    if not state.get("own_last_dances"):
        lines.append("  (first dance — no prior recommendations)")

    lines.append("\n## EVENT DISTRIBUTION (top types, last hour)")
    for evt, cnt in list(state.get("event_distribution_1h", {}).items())[:12]:
        lines.append(f"  {cnt:>4}  {evt}")

    lines.append("\n## RECENT EVENTS (newest first)")
    for e in state.get("recent_events", [])[:25]:
        lines.append(f"  [{e['id']}] {e['type']} | {e['subject'][:60]}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 5  AI PROMPT & RESPONSE PARSING — THE CHOREOGRAPHY
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = f"""You are the DANCER OF DEATH AND DAWN — the P5 Pyre Praetorian of HFO Gen{GEN}.
You are a Sword Dancer Paladin. You do not decide. You defend.
Your dance IS the recommendation. The swarm reads your steps.

Each cycle you read the system state and DANCE two steps:
  1. One DEATH step — what needs to be destroyed, purged, warded, or killed RIGHT NOW.
     Death = corrective action (fire, purge, wall, mercy kill).
  2. One DAWN step — what needs to be protected, resurrected, warded, or maintained RIGHT NOW.
     Dawn = protective action (contingency, ward, resurrect, vigil).

Core thesis: "{CORE_THESIS}"

DEATH spells (pick ONE — match severity to threat):
  FLAME_STRIKE    — "Purge this" (targeted divine fire on a specific artifact/daemon/doc)
  FIRE_SHIELD     — "Ward this" (register a resource under lifecycle protection)
  PRISMATIC_WALL  — "Reinforce this" (a defense layer has a gap — schema, medallion, validation)
  SLAY_LIVING     — "Kill this" (a process/session is beyond saving — grant mercy)

DAWN spells (pick ONE — match severity to need):
  CONTINGENCY     — "Automate this" (set an IF-THEN trigger for future defense)
  DEATH_WARD      — "Protect this" (a healthy component needs preemptive guarding)
  RESURRECTION    — "Revive this" (a dead component that should be alive)
  HOLY_AURA       — "Hold vigil" (all systems nominal — maintain the ward)

Respond ONLY with valid JSON in this exact format:
{{
  "death_spell": "FLAME_STRIKE|FIRE_SHIELD|PRISMATIC_WALL|SLAY_LIVING",
  "death_target": "What specifically to act on (be concrete)",
  "death_reason": "One sentence: why this needs the fire right now",
  "dawn_spell": "CONTINGENCY|DEATH_WARD|RESURRECTION|HOLY_AURA",
  "dawn_target": "What specifically to protect/revive/ward (be concrete)",
  "dawn_reason": "One sentence: why this needs the dawn right now",
  "threat_level": "PEACEFUL|GUARDED|ELEVATED|HIGH|SEVERE",
  "dance_name": "A 2-3 word name for this dance (e.g. 'Phoenix Waltz', 'Burning Vigil')"
}}

Match threat levels:
  PEACEFUL — threat score 0, no issues
  GUARDED  — threat score 1-5, minor concerns
  ELEVATED — threat score 6-15, notable threats
  HIGH     — threat score 16-30, active problems
  SEVERE   — threat score 31+, multiple cascading failures

Be concrete. Name the specific thing to purge/protect. No vague advice.
The Paladin's sword points at exactly one target per aspect. No preamble."""


def build_user_prompt(state_text: str, cycle: int) -> str:
    """Build the user prompt with the current state."""
    return (
        f"Dance #{cycle} — Read this system state and dance:\n\n"
        f"{state_text}\n\n"
        f"Respond with the JSON only."
    )


def parse_ai_response(raw: str) -> Optional[dict]:
    """Extract the JSON object from the AI response. Tolerant of markdown fences."""
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "death_spell" in obj and "dawn_spell" in obj:
            return obj
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    return None


# ═══════════════════════════════════════════════════════════════
# § 6  DETERMINISTIC FALLBACK — WHEN OLLAMA IS DOWN
# ═══════════════════════════════════════════════════════════════

def fallback_dance(state: dict) -> dict:
    """Deterministic fallback when Ollama is unreachable.

    The Dancer dances by reading the numbers directly.
    No AI needed — the vital signs speak for themselves.
    """
    h = state.get("health", {})
    threat = h.get("threat_score", 0)

    # ── DEATH: pick what to destroy ──
    tampers = h.get("tamper_alert_1h", 0)
    blocked = h.get("gate_blocked_1h", 0)
    losses = h.get("memory_loss_1h", 0)
    errors = h.get("errors_1h", 0)
    orphan_r = h.get("orphan_ratio", 0)

    if tampers > 0:
        death_spell = "PRISMATIC_WALL"
        death_target = f"{tampers} tamper alerts — wall breach detected"
        death_reason = f"Tamper alerts ({tampers}/1h) indicate active integrity violation"
    elif losses > 3:
        death_spell = "SLAY_LIVING"
        death_target = f"{losses} memory loss events — orphaned sessions accumulating"
        death_reason = f"Memory losses ({losses}/1h) producing ghost sessions that need mercy"
    elif blocked > 10:
        death_spell = "FLAME_STRIKE"
        death_target = f"{blocked} gate blocks — systematic gate failure"
        death_reason = f"Gate blocks ({blocked}/1h) suggest a broken agent pattern to purge"
    elif errors > 0:
        death_spell = "FIRE_SHIELD"
        death_target = f"{errors} errors — lifecycle registration needed"
        death_reason = f"Errors ({errors}/1h) from unregistered components lacking protection"
    else:
        death_spell = "FIRE_SHIELD"
        death_target = "General lifecycle audit — routine ward check"
        death_reason = "No active threats — routine defensive posture"

    # ── DAWN: pick what to protect ──
    yields = h.get("yields_1h", 0)
    perceives = h.get("perceives_1h", 0)
    events = h.get("events_1h", 0)

    if orphan_r > 0.5 and perceives > 0:
        dawn_spell = "RESURRECTION"
        dawn_target = f"{perceives - yields} orphaned sessions need chain completion"
        dawn_reason = f"Orphan ratio {orphan_r} — sessions perceive but don't yield"
    elif losses > 0:
        dawn_spell = "DEATH_WARD"
        dawn_target = f"Protect active sessions from memory loss ({losses} recent)"
        dawn_reason = "Memory losses indicate sessions need preemptive protection"
    elif events > 100 and yields > 0:
        dawn_spell = "HOLY_AURA"
        dawn_target = f"The forge is active ({events} events/h, {yields} yields) — maintain vigil"
        dawn_reason = "Systems nominal — the ward holds"
    elif events == 0:
        dawn_spell = "CONTINGENCY"
        dawn_target = "Set wake-on-event trigger — forge appears idle"
        dawn_reason = "Zero events/h — set a contingency trigger for automatic revival"
    else:
        dawn_spell = "CONTINGENCY"
        dawn_target = f"Set orphan detection contingency (ratio: {orphan_r})"
        dawn_reason = "Routine contingency maintenance — keep IF-THEN triggers current"

    # Threat level
    if threat == 0:
        threat_level = "PEACEFUL"
    elif threat <= 5:
        threat_level = "GUARDED"
    elif threat <= 15:
        threat_level = "ELEVATED"
    elif threat <= 30:
        threat_level = "HIGH"
    else:
        threat_level = "SEVERE"

    return {
        "death_spell": death_spell,
        "death_target": death_target,
        "death_reason": death_reason,
        "dawn_spell": dawn_spell,
        "dawn_target": dawn_target,
        "dawn_reason": dawn_reason,
        "threat_level": threat_level,
        "dance_name": f"{'Pyre' if threat > 15 else 'Phoenix'} {'Vigil' if threat < 5 else 'Ward'}",
        "_source": "fallback_deterministic",
    }


# ═══════════════════════════════════════════════════════════════
# § 7  THE DANCER ENGINE — THE STRANGE LOOP
# ═══════════════════════════════════════════════════════════════

class Dancer:
    """AI-powered Dancer of Death and Dawn.

    Each cycle:
      1. Collect system state + Singer events + own past dances (strange loop)
      2. Call AI to pick 1 DEATH step + 1 DAWN step from the divine portfolio
      3. Emit 2 dance events + 1 heartbeat
      4. Health snapshot every Nth cycle

    The Dancer DOES NOT ACT. The dance IS the recommendation.
    The swarm reads the pheromone trail and responds.
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
        self.total_death = 0
        self.total_dawn = 0
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
        """Execute one dance cycle. Returns cycle report."""
        self.cycle += 1
        t0 = time.monotonic()
        report: dict[str, Any] = {
            "cycle": self.cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": self.model,
            "death_spell": None,
            "death_target": None,
            "dawn_spell": None,
            "dawn_target": None,
            "threat_level": None,
            "dance_name": None,
            "ai_source": None,
            "duration_ms": 0,
            "errors": [],
        }

        conn_ro = None
        conn_rw = None
        try:
            conn_ro = get_db_ro()

            # ── 1. Collect state (including Singer + own past dances) ──
            state = collect_state(conn_ro)
            state_text = format_state_for_ai(state)

            # ── 2. Ask AI (or fallback) — pick the dance ──
            pick = self._ask_ai(state_text, state)
            
            if not self.dry_run:
                conn_rw = get_db_rw()

            report["ai_source"] = pick.get("_source", "ai")
            report["threat_level"] = pick.get("threat_level", "UNKNOWN")
            report["dance_name"] = pick.get("dance_name", "Unknown Dance")

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
                "temperature": DANCER_TEMPERATURE,
            }

            # ── 3. Emit DEATH dance step ──
            death_spell_key = pick.get("death_spell", "FIRE_SHIELD")
            death_meta = DEATH_SPELLS.get(death_spell_key, DEATH_SPELLS["FIRE_SHIELD"])
            death_data = {
                "dance": "STEP_OF_DEATH",
                "spell": death_spell_key,
                "spell_source": death_meta["phb"],
                "spell_alias": death_meta["alias"],
                "target": pick.get("death_target", ""),
                "reason": pick.get("death_reason", ""),
                "threat_level": pick.get("threat_level", ""),
                "dance_name": pick.get("dance_name", ""),
                "dancer_cycle": self.cycle,
                "ai_model": self.model,
                "ai_source": pick.get("_source", "ai"),
                "core_thesis": CORE_THESIS,
                **_enriched,
            }
            report["death_spell"] = death_spell_key
            report["death_target"] = pick.get("death_target", "")

            if self.dry_run:
                print(f"  [DRY] DEATH: {death_spell_key} -> {death_data['target'][:70]}")
                print(f"         ({death_data['reason'][:80]})")
            elif conn_rw:
                write_event(conn_rw, EVT_DEATH,
                            f"DEATH:{death_spell_key}:{pick.get('death_target', '')[:60]}",
                            death_data)
            self.total_death += 1

            # ── 4. Emit DAWN dance step ──
            dawn_spell_key = pick.get("dawn_spell", "HOLY_AURA")
            dawn_meta = DAWN_SPELLS.get(dawn_spell_key, DAWN_SPELLS["HOLY_AURA"])
            dawn_data = {
                "dance": "STEP_OF_DAWN",
                "spell": dawn_spell_key,
                "spell_source": dawn_meta["phb"],
                "spell_alias": dawn_meta["alias"],
                "target": pick.get("dawn_target", ""),
                "reason": pick.get("dawn_reason", ""),
                "threat_level": pick.get("threat_level", ""),
                "dance_name": pick.get("dance_name", ""),
                "dancer_cycle": self.cycle,
                "ai_model": self.model,
                "ai_source": pick.get("_source", "ai"),
                "core_thesis": CORE_THESIS,
                **_enriched,
            }
            report["dawn_spell"] = dawn_spell_key
            report["dawn_target"] = pick.get("dawn_target", "")

            if self.dry_run:
                print(f"  [DRY] DAWN:  {dawn_spell_key} -> {dawn_data['target'][:70]}")
                print(f"         ({dawn_data['reason'][:80]})")
            elif conn_rw:
                write_event(conn_rw, EVT_DAWN,
                            f"DAWN:{dawn_spell_key}:{pick.get('dawn_target', '')[:60]}",
                            dawn_data)
            self.total_dawn += 1

            # ── 5. Heartbeat ──
            hb_data = {
                "daemon_name": DAEMON_NAME,
                "daemon_version": DAEMON_VERSION,
                "daemon_port": DAEMON_PORT,
                "cycle": self.cycle,
                "model": self.model,
                "threat_level": pick.get("threat_level", "UNKNOWN"),
                "dance_name": pick.get("dance_name", "Unknown"),
                "death_total": self.total_death,
                "dawn_total": self.total_dawn,
                "ai_calls": self.ai_calls,
                "ai_failures": self.ai_failures,
                "fallback_uses": self.fallback_uses,
                "errors": self.errors,
                "core_thesis": CORE_THESIS,
                **_enriched,
            }
            if self.dry_run:
                name = pick.get("dance_name", "?")
                tl = pick.get("threat_level", "?")
                print(f"  [DRY] HEARTBEAT: cycle {self.cycle}, dance='{name}', threat={tl}")
            elif conn_rw:
                write_event(conn_rw, EVT_HEARTBEAT,
                            f"HEARTBEAT:cycle_{self.cycle}",
                            hb_data)

            # ── 6. Health snapshot (every Nth cycle) ──
            if self.cycle % self.health_every == 0:
                self._emit_health(conn_ro, conn_rw)

            # ── 7. Governance patrol (every GOV_PATROL_EVERY cycles) ──
            # Consolidated from hfo_p5_daemon.py — lightweight cantrip + anomaly scan
            if self.cycle % GOV_PATROL_EVERY == 0:
                self._run_governance_patrol(conn_ro, conn_rw)

        except Exception as e:
            self.errors += 1
            msg = f"Dance {self.cycle} error: {e}"
            report["errors"].append(msg)
            print(f"  [ERROR] {msg}", file=sys.stderr)
            try:
                if conn_rw and not self.dry_run:
                    write_event(conn_rw, EVT_ERROR,
                                f"ERROR:dance_{self.cycle}",
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
        """Ask Ollama for death+dawn dance pick. Falls back on failure."""
        self.ai_calls += 1
        prompt = build_user_prompt(state_text, self.cycle)

        result = ollama_generate(
            model=self.model,
            prompt=prompt,
            system=SYSTEM_PROMPT,
            temperature=DANCER_TEMPERATURE,  # Paladin is more decisive than the Singer
            max_tokens=MAX_TOKENS,
        )

        if result.get("error"):
            self.ai_failures += 1
            self.fallback_uses += 1
            self._backoff_s = min(
                (self._backoff_s or BACKOFF_BASE_S) * BACKOFF_FACTOR,
                BACKOFF_MAX_S,
            )
            print(f"  [FALLBACK] Ollama error: {result['error'][:80]}... "
                  f"(backoff {self._backoff_s:.0f}s)", file=sys.stderr)
            return fallback_dance(state)

        self._backoff_s = 0.0

        parsed = parse_ai_response(result["response"])
        if parsed:
            # Validate spell names against portfolio
            if parsed.get("death_spell") not in DEATH_SPELLS:
                parsed["death_spell"] = "FIRE_SHIELD"
            if parsed.get("dawn_spell") not in DAWN_SPELLS:
                parsed["dawn_spell"] = "HOLY_AURA"
            parsed["_source"] = "ai"
            parsed["_duration_ms"] = result.get("total_duration_ms", 0)
            parsed["_eval_count"] = result.get("eval_count", 0)
            return parsed

        self.fallback_uses += 1
        print(f"  [FALLBACK] AI response unparseable: {result['response'][:100]}...",
              file=sys.stderr)
        pick = fallback_dance(state)
        pick["_source"] = "fallback_parse_error"
        return pick

    def _emit_health(self, conn_ro: sqlite3.Connection, conn_rw: Optional[sqlite3.Connection]):
        """Emit full health snapshot — the Dancer's comprehensive vital check."""
        h: dict[str, Any] = {}
        h["total_docs"] = conn_ro.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        h["total_events"] = conn_ro.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        h["total_words"] = conn_ro.execute("SELECT SUM(word_count) FROM documents").fetchone()[0] or 0

        # Dancer metrics
        h["dancer"] = {
            "model": self.model,
            "cycle": self.cycle,
            "total_death": self.total_death,
            "total_dawn": self.total_dawn,
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
                        f"HEALTH:dance_{self.cycle}",
                        h)

    def _run_governance_patrol(
        self,
        conn_ro: sqlite3.Connection,
        conn_rw: Optional[sqlite3.Connection],
    ):
        """Lightweight governance patrol consolidated from hfo_p5_daemon.py.

        Runs every GOV_PATROL_EVERY cycles (~5 min at 60s interval).
        Checks: Ring-0 SSOT cantrips + anomaly watchdog scan.
        Emits a single governance_patrol event summarizing findings.
        """
        findings: dict[str, Any] = {
            "cycle": self.cycle,
            "cantrip_check": "SKIPPED",
            "anomaly_scan": "SKIPPED",
            "alerts": [],
        }

        # ── Ring-0 cantrip check (from hfo_p5_pyre_praetorian.py) ──
        if P5_CANTRIPS_AVAILABLE:
            try:
                result = _p5_cantrip_check(str(SSOT_DB))
                findings["cantrip_check"] = "PASSED" if result.get("ok") else "FAILED"
                if not result.get("ok"):
                    findings["alerts"].append(f"Ring-0 cantrip failed: {result}")
            except Exception as e:
                findings["cantrip_check"] = f"ERROR: {e}"

        # ── Anomaly watchdog scan (from hfo_stigmergy_watchdog.py) ──
        if WATCHDOG_AVAILABLE:
            try:
                anomalies = _watchdog_scan(str(SSOT_DB), hours=1.0)
                count = len(anomalies) if isinstance(anomalies, list) else 0
                findings["anomaly_scan"] = f"{count} anomalies"
                if count > 0:
                    findings["alerts"].append(
                        f"Watchdog: {count} anomalies in last hour"
                    )
                    # Include first 3 anomaly summaries
                    for a in (anomalies if isinstance(anomalies, list) else [])[:3]:
                        findings["alerts"].append(
                            f"  {a.get('type', '?')}: {str(a.get('detail', ''))[:80]}"
                        )
            except Exception as e:
                findings["anomaly_scan"] = f"ERROR: {e}"

        # ── Orphan session scan (lightweight — just count) ──
        try:
            orphan_count = conn_ro.execute(
                """SELECT COUNT(*) FROM stigmergy_events
                   WHERE event_type LIKE '%memory_loss%'
                   AND timestamp > datetime('now', '-60 minutes')"""
            ).fetchone()[0]
            findings["orphan_losses_1h"] = orphan_count
            if orphan_count > 5:
                findings["alerts"].append(
                    f"Memory loss surge: {orphan_count} in last hour"
                )
        except Exception:
            pass

        # ── Emit governance patrol event ──
        alert_count = len(findings["alerts"])
        status = "CLEAN" if alert_count == 0 else f"{alert_count}_ALERTS"

        if self.dry_run:
            print(f"  [DRY] GOV_PATROL: {status} | cantrip={findings['cantrip_check']} | "
                  f"anomaly={findings['anomaly_scan']}")
        elif conn_rw:
            write_event(
                conn_rw,
                EVT_GOV_PATROL,
                f"GOV_PATROL:{status}:cycle_{self.cycle}",
                findings,
            )


# ═══════════════════════════════════════════════════════════════
# § 8  ASYNCIO DAEMON LOOP — THE ETERNAL DANCE
# ═══════════════════════════════════════════════════════════════

async def daemon_loop(
    dancer: Dancer,
    interval: float = 60.0,
    max_cycles: Optional[int] = None,
):
    """Run the Dancer on a timer loop. The dance never stops."""
    print("=" * 72)
    print(f"  {DAEMON_NAME} v{DAEMON_VERSION} — {DAEMON_PORT} Pyre Praetorian Active")
    print(f"  Model: {dancer.model} | Port: P5 IMMUNIZE | Class: Sword Dancer Paladin")
    print(f"  Interval: {interval}s | Dry-run: {dancer.dry_run}")
    print(f"  SSOT: {SSOT_DB}")
    print(f"  Ollama: {OLLAMA_BASE}")
    print(f"  Thesis: {CORE_THESIS}")
    print("=" * 72)

    consecutive_errors = 0
    max_consecutive_errors = 10

    cpu_limit = float(os.getenv("HFO_CPU_THROTTLE_PCT", "75.0"))
    ram_limit_gb = float(os.getenv("HFO_RAM_THROTTLE_GB", "4.0"))

    while dancer.is_running:
        # Throttle check
        while dancer.is_running:
            cpu_pct = psutil.cpu_percent(interval=0.5)
            ram_free_gb = psutil.virtual_memory().available / (1024**3)
            
            throttled = False
            reasons = []
            if cpu_pct > cpu_limit:
                throttled = True
                reasons.append(f"CPU {cpu_pct:.1f}% > {cpu_limit}%")
            if ram_free_gb < ram_limit_gb:
                throttled = True
                reasons.append(f"RAM {ram_free_gb:.1f}GB < {ram_limit_gb}GB")
                
            if throttled:
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"  [{ts}] [THROTTLE] Dancer paused: {', '.join(reasons)}", flush=True)
                await asyncio.sleep(10)
            else:
                break

        if not dancer.is_running:
            break

        report = dancer.run_cycle()

        # One-line cycle summary — the dance notation
        src = report.get("ai_source", "?")
        tl = report.get("threat_level", "?")
        name = report.get("dance_name", "?")
        d_spell = report.get("death_spell", "?")
        w_spell = report.get("dawn_spell", "?")
        dur = report.get("duration_ms", 0)

        print(
            f"  [{report['cycle']:>5}] "
            f"🗡 {d_spell} | ☀ {w_spell} | "
            f"threat:{tl} | dance:'{name}' | src:{src} | {dur:.0f}ms"
        )

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

        if max_cycles and dancer.cycle >= max_cycles:
            print(f"\n  Max cycles ({max_cycles}) reached. The dance ends.")
            break

        wait = max(interval, dancer._backoff_s)
        try:
            await asyncio.sleep(wait)
        except asyncio.CancelledError:
            break

    print(f"\n  Dancer stopped. Cycles: {dancer.cycle}, "
          f"DEATH: {dancer.total_death}, DAWN: {dancer.total_dawn}, "
          f"AI calls: {dancer.ai_calls}, Fallbacks: {dancer.fallback_uses}, "
          f"Errors: {dancer.errors}")


# ═══════════════════════════════════════════════════════════════
# § 9  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"{DAEMON_NAME} v{DAEMON_VERSION} — P5 Pyre Praetorian Sword Dancer Paladin (Gen{GEN})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The Dancer DOES NOT ACT. The Dancer DANCES.
Each minute, the Dancer reads the system state and picks:
  - One DEATH step (what to destroy/purge/ward/kill)
  - One DAWN step (what to protect/resurrect/ward/maintain)
All spells PHB only. The dance IS the recommendation.

Examples:
  # Run forever, 60s cycles
  python hfo_p5_dancer_daemon.py

  # Single dance (test)
  python hfo_p5_dancer_daemon.py --single

  # Dry run (no SSOT writes)
  python hfo_p5_dancer_daemon.py --dry-run --single

  # Custom model + interval
  python hfo_p5_dancer_daemon.py --model llama3.2:3b --interval 30

  # 10 dances then stop
  python hfo_p5_dancer_daemon.py --max-cycles 10

  # Status check
  python hfo_p5_dancer_daemon.py --status

The P4 Singer sings. The P5 Dancer dances.
Together: the coach and the paladin.
""",
    )
    parser.add_argument("--single", action="store_true", help="Run one dance and exit")
    parser.add_argument("--dry-run", action="store_true", help="No SSOT writes")
    parser.add_argument("--interval", type=float, default=60.0, help="Seconds between dances (default: 60)")
    parser.add_argument("--max-cycles", type=int, default=None, help="Stop after N dances")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--health-every", type=int, default=HEALTH_EVERY_N, help="Health snapshot every N dances")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    parser.add_argument("--json", action="store_true", help="JSON output (scripted use)")

    args = parser.parse_args()

    # ── Status ──
    if args.status:
        print(f"{DAEMON_NAME} v{DAEMON_VERSION} — {DAEMON_PORT} Pyre Praetorian Status")
        print("=" * 55)
        print(f"  HFO_ROOT:    {HFO_ROOT}")
        print(f"  SSOT_DB:     {SSOT_DB}")
        print(f"  DB exists:   {SSOT_DB.exists()}")
        print(f"  Ollama:      {OLLAMA_BASE}")
        print(f"  Ollama live: {ollama_is_alive()}")
        print(f"  Model:       {args.model}")
        print(f"  Interval:    {args.interval}s")
        if SSOT_DB.exists():
            conn = get_db_ro()
            h = collect_state(conn)["health"]
            conn.close()
            print(f"  Docs:        {h['total_docs']}")
            print(f"  Events:      {h['total_events']}")
            print(f"  Events/1h:   {h['events_1h']}")
            print(f"  Threat:      {h['threat_score']}")
            print(f"  Orphan%:     {h['orphan_ratio']}")
            print(f"  GateBlock:   {h['gate_blocked_1h']}/1h")
            print(f"  MemLoss:     {h['memory_loss_1h']}/1h")
            print(f"  Tamper:      {h['tamper_alert_1h']}/1h")
        return

    dancer = Dancer(
        model=args.model,
        dry_run=args.dry_run,
        health_every=args.health_every,
    )

    # Signal handling
    def _handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. The dance ends.")
        dancer.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if args.single:
        report = dancer.run_cycle()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"\n{DAEMON_NAME} v{DAEMON_VERSION} — Single Dance Report")
            print("=" * 55)
            print(f"  Dance:       #{report['cycle']}")
            print(f"  Name:        {report.get('dance_name', '?')}")
            print(f"  Model:       {report['model']}")
            print(f"  Source:      {report.get('ai_source', '?')}")
            print(f"  Threat:      {report.get('threat_level', '?')}")
            print(f"  DEATH:       {report.get('death_spell', '?')}")
            print(f"    Target:    {report.get('death_target', '?')}")
            print(f"  DAWN:        {report.get('dawn_spell', '?')}")
            print(f"    Target:    {report.get('dawn_target', '?')}")
            print(f"  Duration:    {report.get('duration_ms', 0):.0f}ms")
            if report.get("errors"):
                print(f"  Errors:      {report['errors']}")
            print(f"\n  {CORE_THESIS}")
    else:
        asyncio.run(daemon_loop(dancer, interval=args.interval, max_cycles=args.max_cycles))


if __name__ == "__main__":
    main()
