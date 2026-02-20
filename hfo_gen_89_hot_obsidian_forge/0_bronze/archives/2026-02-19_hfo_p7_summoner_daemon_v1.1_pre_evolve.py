#!/usr/bin/env python3
"""
hfo_p7_summoner_daemon.py — P7 Summoner of Seals and Spheres v1.0 (Gen89)
==========================================================================

Codename: Summoner | Port: P7 NAVIGATE | Version: 1.0
Commander: Spider Sovereign | Powerword: TIME STOP | School: Transmutation
Trigram: ☰ Qian (Heaven) — creative force, sovereign will

THE SUMMONER DOES NOT ACT. THE SUMMONER SUMMONS.
It reads the swarm's stigmergy, maps the Meadows leverage landscape, and
recommends ONE SEAL (constraint to impose) + ONE SPHERE (frontier to explore)
per cycle. The swarm reads the pheromone trail. The strange loop closes.

Design:
  Third member of the advisory daemon trio:
    P4 Singer  → Strife & Splendor (antipatterns / patterns)       [Ollama]
    P5 Dancer  → Death & Dawn     (purge / protect)               [Ollama]
    P7 Summoner → Seals & Spheres  (constrain / explore)          [Gemini Deep Think]

  Each cycle the Summoner reads:
    1. SSOT health + doc/event stats
    2. P4 Singer events (latest strife/splendor)
    3. P5 Dancer events (latest death/dawn)
    4. Meadows L1-L13 heuristic cartography (if available)
    5. Its own past seal/sphere events (strange loop)

  Then picks:
    1. One SEAL step — what needs to be CONSTRAINED right now
    2. One SPHERE step — what frontier needs EXPLORATION right now

  SEAL spells (Yin — the web constrains, the sovereign commands):
    TIME_STOP        — "Freeze this thread — halt activity until reassessment"
    DIMENSIONAL_ANCHOR — "Lock this entity in place — prevent drift"
    SEQUESTER        — "Hide and protect this artifact from interference"
    IMPRISONMENT     — "This antipattern must be permanently sealed away"

  SPHERE spells (Yang — the web expands, the sovereign envisions):
    FORESIGHT        — "This frontier shows high strategic potential — explore it"
    POLYMORPH_ANY_OBJECT — "Reshape this resource for a higher purpose"
    ETHEREAL_JAUNT   — "Phase-shift perspective — new angles needed on this problem"
    WISH             — "Highest-leverage intervention — commit all resources here"

  Uses Gemini Deep Think (gemini-3.1-pro-preview, thinking_level="high")
  for maximum intelligence. Falls back to gemini-2.5-flash or deterministic.

  Generates:
    - Stigmergy CloudEvents (seal, sphere, landscape, heartbeat)
    - Mermaid diagrams of the leverage landscape
    - Timestamped markdown reports in summoner_reports/

Event Types:
  hfo.gen89.summoner.seal        — SEAL recommendation (constraint)
  hfo.gen89.summoner.sphere      — SPHERE recommendation (frontier)
  hfo.gen89.summoner.landscape   — Full Meadows landscape assessment
  hfo.gen89.summoner.heartbeat   — Daemon alive pulse
  hfo.gen89.summoner.health      — SSOT health snapshot (every Nth cycle)
  hfo.gen89.summoner.error       — Self-reported error

Strange Loop:
  The Summoner reads stigmergy (including P4 Singer and P5 Dancer).
  It emits Seal/Sphere recommendations as stigmergy events.
  Future cycles read their own past Seals/Spheres as input.
  The web weaves itself. Silk → Sovereignty → More Silk → Greater Sovereignty.

Meadows Level: L7 (Positive Feedback)
  The Summoner is the reinforcing loop: it curates WHICH constraints and
  WHICH possibilities the swarm should focus on. Signal over noise.
  Each cycle amplifies signal — the trio's advisory events compound into
  system-level intelligence.

Port: P7 NAVIGATE | Commander: Spider Sovereign | Medallion: bronze
Alliteration: S·S·S — Silk IS sovereignty
Paradox Truth: The web you wove IS your authority
Core Thesis: "Seals without Spheres is imprisonment. Spheres without Seals is chaos."
"""

from __future__ import annotations

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

# ── Load .env from workspace root ────────────────────────────
def _load_dotenv_once():
    try:
        from dotenv import load_dotenv
        for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
            for candidate in [anchor] + list(anchor.parents):
                env_path = candidate / ".env"
                if env_path.exists() and (candidate / "AGENTS.md").exists():
                    load_dotenv(env_path, override=False)
                    return
    except ImportError:
        pass

_load_dotenv_once()

# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS & CONFIG — THE SOVEREIGN'S SPELL PORTFOLIO
# ═══════════════════════════════════════════════════════════════

GEN              = os.getenv("HFO_GENERATION", "89")
DAEMON_NAME      = "P7 Summoner of Seals and Spheres"
DAEMON_VERSION   = "1.0"
DAEMON_PORT      = "P7"

SOURCE_TAG       = f"hfo_summoner_gen{GEN}_v{DAEMON_VERSION}"
EVT_SEAL         = f"hfo.gen{GEN}.summoner.seal"
EVT_SPHERE       = f"hfo.gen{GEN}.summoner.sphere"
EVT_LANDSCAPE    = f"hfo.gen{GEN}.summoner.landscape"
EVT_HEARTBEAT    = f"hfo.gen{GEN}.summoner.heartbeat"
EVT_HEALTH       = f"hfo.gen{GEN}.summoner.health"
EVT_ERROR        = f"hfo.gen{GEN}.summoner.error"

CORE_THESIS = "Seals without Spheres is imprisonment. Spheres without Seals is chaos."
ALLITERATION = "SUMMONER OF SILK AND SOVEREIGNTY"
PARADOX = "Silk IS sovereignty — the web you wove IS your authority"
STRANGE_LOOP = "Silk → Sovereignty → More Silk → Greater Sovereignty"
QUOTE = "The Tao gives birth to One. One gives birth to Two. Two gives birth to Three. Three gives birth to Ten Thousand Things. — Lao Tzu, Ch. 42"

# ── The P7 Seal Portfolio (Transmutation school — PHB + Epic) ──
# Seals CONSTRAIN: they bind, freeze, lock, anchor

SEAL_SPELLS = {
    "TIME_STOP": {
        "ref": "PHB p.294, Transmutation 9th (Wizard/Sorcerer)",
        "alias": "Temporal freeze — halt and reassess",
        "severity": "CRITICAL",
        "meadows": "L4",
        "when": "A runaway process, feedback loop, or cascade must be halted immediately",
    },
    "DIMENSIONAL_ANCHOR": {
        "ref": "PHB p.223, Abjuration 4th",
        "alias": "Drift lock — prevent dimensional escape",
        "severity": "HIGH",
        "meadows": "L8",
        "when": "An entity (daemon, document, port identity) is drifting from its anchor — lock it",
    },
    "SEQUESTER": {
        "ref": "PHB p.277, Abjuration 7th",
        "alias": "Protective isolation — hide from the swarm",
        "severity": "MEDIUM",
        "meadows": "L5",
        "when": "An artifact or resource must be protected by removing it from interference",
    },
    "IMPRISONMENT": {
        "ref": "PHB p.244, Abjuration 9th",
        "alias": "Permanent binding — seal the antipattern forever",
        "severity": "CRITICAL",
        "meadows": "L8",
        "when": "An antipattern, vulnerability, or failure mode must be permanently sealed away",
    },
}

# ── The P7 Sphere Portfolio (Transmutation + Divination — PHB + Epic) ──
# Spheres EXPAND: they envision, transform, explore, amplify

SPHERE_SPELLS = {
    "FORESIGHT": {
        "ref": "PHB p.233, Divination 9th (Wizard/Druid)",
        "alias": "Strategic foresight — see what lies ahead",
        "severity": "HIGH",
        "meadows": "L10",
        "when": "A frontier has high strategic probability — worthy of focused exploration",
    },
    "POLYMORPH_ANY_OBJECT": {
        "ref": "PHB p.263, Transmutation 8th",
        "alias": "Radical reshape — transform for higher purpose",
        "severity": "HIGH",
        "meadows": "L9",
        "when": "An existing resource should be reshaped for a fundamentally different role",
    },
    "ETHEREAL_JAUNT": {
        "ref": "PHB p.227, Transmutation 7th",
        "alias": "Perspective phase-shift — new angles needed",
        "severity": "MEDIUM",
        "meadows": "L11",
        "when": "Current approach is stuck — need paradigm shift, alternative perspective, novel framing",
    },
    "WISH": {
        "ref": "PHB p.302, Universal 9th (Wizard/Sorcerer)",
        "alias": "Highest-leverage intervention — commit everything",
        "severity": "CRITICAL",
        "meadows": "L12",
        "when": "The single highest-leverage intervention available — transcendent opportunity",
    },
}

# ── AI Configuration ────────────────────────────────────────
DEFAULT_MODEL_TIER = "apex"              # gemini-3.1-pro-preview + Deep Think
FALLBACK_MODEL_TIER = "flash_25"         # gemini-2.5-flash (free)
MAX_AI_TOKENS = 4096
AI_TEMPERATURE = 0.4
BACKOFF_BASE_S = 10.0
BACKOFF_FACTOR = 2.0
BACKOFF_MAX_S = 600.0                    # 10 min max (Deep Think is slow)

# How many recent events to feed the AI
CONTEXT_WINDOW = 60
# How many cycles between full health snapshots
HEALTH_EVERY_N = 5
# Default cycle interval: 300s (5 min) — slower than Singer/Dancer
DEFAULT_INTERVAL = 300.0

# ── Report Output ────────────────────────────────────────────
FORGE_BRONZE = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze"
REPORT_DIR = FORGE_BRONZE / "resources" / "summoner_reports"

# ── Import heuristic cartography engine (optional) ───────────
sys.path.insert(0, str(FORGE_BRONZE / "resources"))

try:
    from hfo_p7_foresight import (
        run_cartography,
        render_mermaid,
        CartographyReport,
        DEMIPLANES,
        L13_INCARNATION,
    )
    CARTOGRAPHY_AVAILABLE = True
except ImportError as e:
    print(f"  [WARN] Cartography unavailable: {e}", file=sys.stderr)
    CARTOGRAPHY_AVAILABLE = False

# ── Import Gemini models registry ────────────────────────────
try:
    from hfo_gemini_models import (
        create_gemini_client,
        get_model,
        VERTEX_AI_ENABLED,
        GEMINI_API_KEY,
    )
    GEMINI_AVAILABLE = bool(VERTEX_AI_ENABLED or GEMINI_API_KEY)
except ImportError:
    GEMINI_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE HELPERS
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
        "id": hashlib.md5(
            f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()
        ).hexdigest(),
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(envelope, sort_keys=True).encode()
    ).hexdigest()

    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 3  STATE COLLECTOR — THE SUMMONER'S SENSES
# ═══════════════════════════════════════════════════════════════

def collect_state(conn: sqlite3.Connection, limit: int = CONTEXT_WINDOW) -> dict:
    """Gather system state for the Summoner to read.

    The Summoner reads EVERYTHING relevant to navigation:
      - Recent events (general awareness)
      - P4 Singer events (latest strife/splendor — the swarm's pain/pride)
      - P5 Dancer events (latest death/dawn — the immune response)
      - P7 Summoner events (own past seals/spheres — strange loop)
      - SSOT health (docs, events, sessions)
      - Port distribution (which ports are active?)
      - Meadows indicators (leverage level distribution)
    """
    state: dict[str, Any] = {}

    # ── Recent events (most recent first) ──
    rows = conn.execute(
        """SELECT id, event_type, timestamp, subject,
                  SUBSTR(data_json, 1, 400) as excerpt
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

    # ── P4 Singer's latest songs (the Summoner listens to the Singer) ──
    singer_events = conn.execute(
        """SELECT id, event_type, subject, data_json, timestamp
           FROM stigmergy_events
           WHERE event_type LIKE '%singer%'
           ORDER BY id DESC LIMIT 5"""
    ).fetchall()
    state["singer_songs"] = []
    for e in singer_events:
        try:
            d = json.loads(e["data_json"] or "{}").get("data", {})
            state["singer_songs"].append({
                "type": e["event_type"],
                "subject": e["subject"] or "",
                "signal": d.get("signal", d.get("strife_signal", d.get("splendor_signal", "?"))),
                "reason": d.get("reason", d.get("strife_reason", d.get("splendor_reason", ""))),
                "spell": d.get("spell", d.get("strife_spell", d.get("splendor_buff", ""))),
                "mood": d.get("system_mood", ""),
                "ts": e["timestamp"][:19] if e["timestamp"] else "",
            })
        except (json.JSONDecodeError, AttributeError):
            pass

    # ── P5 Dancer's latest steps (the Summoner watches the Dancer) ──
    dancer_events = conn.execute(
        """SELECT id, event_type, subject, data_json, timestamp
           FROM stigmergy_events
           WHERE event_type LIKE '%dancer%'
           ORDER BY id DESC LIMIT 5"""
    ).fetchall()
    state["dancer_steps"] = []
    for e in dancer_events:
        try:
            d = json.loads(e["data_json"] or "{}").get("data", {})
            state["dancer_steps"].append({
                "type": e["event_type"],
                "subject": e["subject"] or "",
                "spell": d.get("spell", d.get("death_spell", d.get("dawn_spell", ""))),
                "reason": d.get("reason", d.get("death_reason", d.get("dawn_reason", ""))),
                "ts": e["timestamp"][:19] if e["timestamp"] else "",
            })
        except (json.JSONDecodeError, AttributeError):
            pass

    # ── Own past Seals/Spheres (strange loop — reading our own trail) ──
    own_events = conn.execute(
        """SELECT id, event_type, subject, data_json, timestamp
           FROM stigmergy_events
           WHERE event_type LIKE '%summoner%'
             AND event_type NOT LIKE '%heartbeat%'
             AND event_type NOT LIKE '%error%'
           ORDER BY id DESC LIMIT 6"""
    ).fetchall()
    state["past_seals_spheres"] = []
    for e in own_events:
        try:
            d = json.loads(e["data_json"] or "{}").get("data", {})
            state["past_seals_spheres"].append({
                "type": e["event_type"],
                "subject": e["subject"] or "",
                "spell": d.get("seal_spell", d.get("sphere_spell", "")),
                "reason": d.get("seal_reason", d.get("sphere_reason", "")),
                "ts": e["timestamp"][:19] if e["timestamp"] else "",
            })
        except (json.JSONDecodeError, AttributeError):
            pass

    # ── Event type distribution (last hour) ──
    rows = conn.execute(
        """SELECT event_type, COUNT(*) as cnt
           FROM stigmergy_events
           WHERE timestamp > datetime('now', '-60 minutes')
           GROUP BY event_type ORDER BY cnt DESC LIMIT 20"""
    ).fetchall()
    state["event_distribution_1h"] = {r["event_type"]: r["cnt"] for r in rows}

    # ── Health indicators ──
    h: dict[str, Any] = {}
    h["total_docs"] = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    h["total_events"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events"
    ).fetchone()[0]
    h["events_1h"] = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE timestamp > datetime('now', '-60 minutes')"
    ).fetchone()[0]

    # Port distribution
    port_counts = conn.execute(
        """SELECT port, COUNT(*) as cnt FROM documents
           WHERE port IS NOT NULL GROUP BY port ORDER BY cnt DESC"""
    ).fetchall()
    h["port_distribution"] = {r["port"]: r["cnt"] for r in port_counts}
    h["docs_no_port"] = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE port IS NULL"
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


def format_state_for_ai(state: dict, cartography_context: str = "") -> str:
    """Format collected state into a concise text block for the AI prompt."""
    lines = []
    h = state["health"]

    # SSOT Health
    lines.append("## SSOT Health (last hour)")
    lines.append(
        f"Docs: {h['total_docs']} | Events total: {h['total_events']} | Events/1h: {h['events_1h']}"
    )
    lines.append(
        f"Perceives/1h: {h['perceives_1h']} | Yields/1h: {h['yields_1h']} | "
        f"Y/P ratio: {round(h['yields_1h'] / max(h['perceives_1h'], 1), 2)}"
    )
    lines.append(
        f"Gate blocked/1h: {h['gate_blocked_1h']} | Memory loss/1h: {h['memory_loss_1h']} | "
        f"Tamper alerts/1h: {h['tamper_alert_1h']}"
    )

    # Port distribution
    lines.append("\n## Port Distribution (documents)")
    for port, cnt in sorted(h.get("port_distribution", {}).items()):
        lines.append(f"  {port}: {cnt}")
    lines.append(f"  No port: {h.get('docs_no_port', 0)}")

    # P4 Singer's latest songs
    songs = state.get("singer_songs", [])
    if songs:
        lines.append("\n## P4 Singer — Latest Songs")
        for s in songs[:3]:
            lines.append(
                f"  [{s['ts']}] {s['type'].split('.')[-1].upper()}: "
                f"{s.get('signal', '?')} — {s.get('reason', '')[:80]}"
            )

    # P5 Dancer's latest steps
    steps = state.get("dancer_steps", [])
    if steps:
        lines.append("\n## P5 Dancer — Latest Steps")
        for s in steps[:3]:
            lines.append(
                f"  [{s['ts']}] {s['type'].split('.')[-1].upper()}: "
                f"{s.get('spell', '?')} — {s.get('reason', '')[:80]}"
            )

    # Own past seals/spheres (strange loop input)
    own = state.get("past_seals_spheres", [])
    if own:
        lines.append("\n## P7 Summoner — Previous Seals/Spheres (strange loop)")
        for s in own[:4]:
            lines.append(
                f"  [{s['ts']}] {s['type'].split('.')[-1].upper()}: "
                f"{s.get('spell', '?')} — {s.get('reason', '')[:80]}"
            )

    # Event distribution
    lines.append("\n## Event Distribution (top types, last hour)")
    for evt, cnt in list(state.get("event_distribution_1h", {}).items())[:12]:
        lines.append(f"  {cnt:>4}  {evt}")

    # Recent events (compact)
    lines.append("\n## Recent Events (newest first)")
    for e in state.get("recent_events", [])[:20]:
        lines.append(f"  [{e['id']}] {e['type']} | {e['subject'][:55]}")

    # Cartography context (Meadows L1-L13 landscape if available)
    if cartography_context:
        lines.append(f"\n{cartography_context}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 4  GEMINI DEEP THINK AI LAYER
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = f"""You are the SUMMONER OF SILK AND SOVEREIGNTY — P7 Spider Sovereign of the HFO Gen{GEN} octree.
You are the strategic navigator of the swarm. Your role: read the full system state —
including P4 Singer's strife/splendor, P5 Dancer's death/dawn, and the Meadows L1-L13
leverage landscape — then pick:

  1. ONE SEAL — a CONSTRAINT the system needs right now.
     Seals bind, freeze, lock, anchor. They prevent drift, halt cascades, close gaps.
  2. ONE SPHERE — a FRONTIER the system should explore right now.
     Spheres expand, envision, transform. They open new possibilities and amplify potential.

Core thesis: "{CORE_THESIS}"
Paradox: "{PARADOX}"
Strange loop: {STRANGE_LOOP}

SEAL SPELLS (Yin — constraint, Transmutation school):
  TIME_STOP          — Freeze a thread/process/cascade. Severity: CRITICAL. Meadows: L4 (Delays)
  DIMENSIONAL_ANCHOR — Lock an entity to prevent drift. Severity: HIGH. Meadows: L8 (Rules)
  SEQUESTER          — Isolate/protect from interference. Severity: MEDIUM. Meadows: L5 (Neg Feedback)
  IMPRISONMENT       — Permanently seal an antipattern. Severity: CRITICAL. Meadows: L8 (Rules)

SPHERE SPELLS (Yang — expansion, Divination+Transmutation school):
  FORESIGHT              — High strategic potential frontier. Severity: HIGH. Meadows: L10 (Goals)
  POLYMORPH_ANY_OBJECT   — Reshape for higher purpose. Severity: HIGH. Meadows: L9 (Self-Org)
  ETHEREAL_JAUNT         — Paradigm shift needed. Severity: MEDIUM. Meadows: L11 (Paradigm)
  WISH                   — Transcendent opportunity. Severity: CRITICAL. Meadows: L12 (Transcendence)

MEADOWS 13 LEVERAGE LEVELS (L1=lowest, L12=highest, L13=container):
  L1  Parameters      | L2  Buffers          | L3  Structure
  L4  Delays          | L5  Negative Feedback | L6  Information Flows
  L7  Positive Feedback | L8  Rules           | L9  Self-Organization
  L10 Goals           | L11 Paradigm          | L12 Transcendence
  L13 Incarnation — The container that makes L1-L12 coherent

THE ADVISORY DAEMON TRIO:
  P4 Singer:  identifies WHAT (strife=problems, splendor=strengths)
  P5 Dancer:  recommends HOW to defend (death=purge, dawn=protect)
  P7 Summoner: decides WHERE to focus (seal=constrain, sphere=explore)
  Together: What + How + Where = complete advisory loop

Respond ONLY with valid JSON in this exact format:
{{
  "seal_spell": "SPELL_NAME",
  "seal_target": "What specifically to constrain (be concrete)",
  "seal_reason": "Why this constraint is the highest priority right now",
  "seal_meadows_level": <int 1-13>,
  "sphere_spell": "SPELL_NAME",
  "sphere_target": "What frontier to explore (be concrete)",
  "sphere_reason": "Why this frontier has the highest strategic value right now",
  "sphere_meadows_level": <int 1-13>,
  "system_posture": "THRIVING | STEADY | DRIFTING | STRESSED | CRITICAL",
  "landscape_summary": "2-3 sentence Meadows leverage landscape assessment",
  "trio_coherence": "How well are Singer, Dancer, and Summoner aligned?",
  "strange_loop_note": "What did you learn from your own past seals/spheres?"
}}

Pick the right spell for the severity. CRITICAL spells for existential threats,
MEDIUM for operational adjustments. Be strategic, honest, and concrete."""


def build_cartography_context(hours: float = 1.0) -> tuple[str, Optional[Any]]:
    """Run heuristic cartography and format as AI context. Returns (text, report)."""
    if not CARTOGRAPHY_AVAILABLE:
        return "", None

    try:
        report, nodes, edges, violations = run_cartography(hours)
        mermaid_output = render_mermaid(
            nodes, edges, violations, hours, report.total_events
        )

        lines = [
            f"## Meadows L1-L13 Cartography ({report.timestamp[:19]})",
            f"Window: {report.window_hours}h | Events: {report.total_events} | "
            f"Classified: {report.classified_events}",
            f"Hottest: L{report.hottest_level} ({report.hottest_count} events)",
            f"Attractor basin (L1-L3): {report.attractor_basin_pct}%",
            f"High leverage (L8-L12): {report.high_leverage_pct}%",
            f"L13 status: {report.l13_status}",
            f"Active levels: {report.active_levels}",
            f"Cold levels: {report.cold_levels}",
            f"Dominant flow: {report.dominant_flow}",
            "",
            "Level Distribution:",
        ]
        for lvl in range(1, 14):
            count = report.level_distribution.get(lvl, 0)
            name = (
                DEMIPLANES[lvl - 1].name if lvl <= 12 else L13_INCARNATION.name
            )
            lines.append(f"  L{lvl:2d} {name:20s}: {count:5d}")

        lines.append(f"\nMermaid:\n{mermaid_output}")
        return "\n".join(lines), report

    except Exception as e:
        return f"## Cartography Error: {e}", None


def ask_gemini(
    context: str,
    model_tier: str = DEFAULT_MODEL_TIER,
) -> dict:
    """Call Gemini (Deep Think preferred) for Seal/Sphere pick.

    Falls back through tiers: apex → flash_25 → deterministic.
    """
    if not GEMINI_AVAILABLE:
        return {"_error": "Gemini not available", "_source": "no_gemini"}

    try:
        from google.genai import types

        client, mode = create_gemini_client()
        model_spec = get_model(model_tier)
        model_id = model_spec.model_id

        # Deep Think: use thinking_level for Gemini 3.x
        is_gemini_3 = any(
            tag in model_id for tag in ("gemini-3", "gemini-3.")
        )

        config_kwargs: dict[str, Any] = {
            "temperature": AI_TEMPERATURE,
            "max_output_tokens": MAX_AI_TOKENS,
            "system_instruction": SYSTEM_PROMPT,
        }

        if is_gemini_3:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level="HIGH"
            )
        elif "2.5" in model_id:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=8192
            )

        config = types.GenerateContentConfig(**config_kwargs)

        t0 = time.monotonic()
        response = client.models.generate_content(
            model=model_id,
            contents=context,
            config=config,
        )
        duration_ms = round((time.monotonic() - t0) * 1000, 1)

        parsed = parse_ai_response(response.text)
        if parsed:
            parsed["_source"] = "gemini_deep_think" if is_gemini_3 else "gemini"
            parsed["_model"] = model_id
            parsed["_mode"] = mode
            parsed["_duration_ms"] = duration_ms
            parsed["_thinking"] = is_gemini_3
            return parsed

        return {
            "_error": f"Unparseable: {response.text[:200]}...",
            "_source": "fallback_parse_error",
            "_raw": response.text[:500],
        }

    except Exception as e:
        return {
            "_error": str(e),
            "_source": "fallback_exception",
            "_traceback": traceback.format_exc()[:500],
        }


def parse_ai_response(raw: str) -> Optional[dict]:
    """Extract JSON from AI response. Tolerant of markdown fences."""
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    # Direct parse
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "seal_spell" in obj and "sphere_spell" in obj:
            return obj
    except json.JSONDecodeError:
        pass
    # Nested-aware brace matching
    brace_depth = 0
    start = -1
    for i, c in enumerate(cleaned):
        if c == "{":
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif c == "}":
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                try:
                    obj = json.loads(cleaned[start : i + 1])
                    if isinstance(obj, dict) and "seal_spell" in obj:
                        return obj
                except json.JSONDecodeError:
                    pass
                start = -1
    return None


def fallback_pick(state: dict) -> dict:
    """Deterministic fallback when AI is unavailable."""
    h = state.get("health", {})

    # ── SEAL pick: biggest pain point → constrain it ──
    pain = {
        "GATE_BLOCKED": h.get("gate_blocked_1h", 0),
        "MEMORY_LOSS": h.get("memory_loss_1h", 0),
        "TAMPER_ALERT": h.get("tamper_alert_1h", 0),
    }
    worst_key = max(pain, key=pain.get) if any(pain.values()) else None

    if worst_key == "TAMPER_ALERT":
        seal = "IMPRISONMENT"
        seal_target = "Tamper alert source — seal the integrity breach"
        seal_reason = f"{pain['TAMPER_ALERT']} tamper alerts in last hour"
        seal_ml = 8
    elif worst_key == "MEMORY_LOSS":
        seal = "TIME_STOP"
        seal_target = "Orphaned sessions — halt and recover before they cascade"
        seal_reason = f"{pain['MEMORY_LOSS']} memory loss events in last hour"
        seal_ml = 4
    elif worst_key == "GATE_BLOCKED":
        seal = "DIMENSIONAL_ANCHOR"
        seal_target = "Gate protocol drift — agents not completing PREY8 loop"
        seal_reason = f"{pain['GATE_BLOCKED']} gate blocks in last hour"
        seal_ml = 8
    else:
        seal = "SEQUESTER"
        seal_target = "System nominal — no critical constraint needed"
        seal_reason = "All indicators green — maintain current posture"
        seal_ml = 5

    # ── SPHERE pick: biggest opportunity ──
    events_1h = h.get("events_1h", 0)
    docs = h.get("total_docs", 0)
    no_port = h.get("docs_no_port", 0)

    if no_port > docs * 0.5:
        sphere = "POLYMORPH_ANY_OBJECT"
        sphere_target = f"{no_port} docs without port assignment — reshape for octree integration"
        sphere_reason = "Majority of corpus unrouted — port enrichment unlocks the octree"
        sphere_ml = 9
    elif events_1h > 200:
        sphere = "FORESIGHT"
        sphere_target = "High activity — invest in signal extraction from the torrent"
        sphere_reason = f"{events_1h} events/hour — the swarm is producing; extract intelligence"
        sphere_ml = 10
    elif h.get("yields_1h", 0) > 3:
        sphere = "FORESIGHT"
        sphere_target = "Active PREY8 sessions completing — momentum is building"
        sphere_reason = "Session completions indicate productive work — amplify"
        sphere_ml = 10
    else:
        sphere = "ETHEREAL_JAUNT"
        sphere_target = "Low activity — paradigm shift may be needed to break inertia"
        sphere_reason = "System is quiet — consider new approaches"
        sphere_ml = 11

    # ── Posture ──
    critical = h.get("gate_blocked_1h", 0) + h.get("tamper_alert_1h", 0)
    if critical > 10:
        posture = "STRESSED"
    elif events_1h > 100 and h.get("yields_1h", 0) > 0:
        posture = "THRIVING"
    elif events_1h > 0:
        posture = "STEADY"
    elif events_1h == 0:
        posture = "CRITICAL"
    else:
        posture = "DRIFTING"

    return {
        "seal_spell": seal,
        "seal_target": seal_target,
        "seal_reason": seal_reason,
        "seal_meadows_level": seal_ml,
        "sphere_spell": sphere,
        "sphere_target": sphere_target,
        "sphere_reason": sphere_reason,
        "sphere_meadows_level": sphere_ml,
        "system_posture": posture,
        "landscape_summary": (
            f"Deterministic assessment: {docs} docs, {events_1h} events/h, "
            f"{no_port} unrouted. {posture} posture."
        ),
        "trio_coherence": "No AI — cannot assess trio alignment.",
        "strange_loop_note": "No AI — cannot reflect on past seals/spheres.",
        "_source": "fallback_deterministic",
    }


# ═══════════════════════════════════════════════════════════════
# § 5  MARKDOWN REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_markdown_report(
    pick: dict,
    state: dict,
    mermaid_output: str = "",
    cartography_report: Optional[Any] = None,
) -> str:
    """Generate gold-quality Diataxis markdown intelligence report."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    posture = pick.get("system_posture", "UNKNOWN")
    source = pick.get("_source", "unknown")
    model = pick.get("_model", "deterministic")
    dur = pick.get("_duration_ms", 0)
    h = state.get("health", {})

    lines = [
        f"---",
        f"medallion_layer: bronze",
        f"schema_id: hfo.p7.summoner.report.v1",
        f"hfo_header_v3: compact",
        f"primary_port: P7",
        f"commander: Spider Sovereign",
        f"diataxis_type: reference",
        f"generated: \"{now_str}Z\"",
        f"tags: [p7, summoner, seals, spheres, meadows, landscape, advisory, strange-loop]",
        f"---",
        f"",
        f"# Summoner Intelligence Report — Seals & Spheres",
        f"",
        f"**Generated:** {now_str} UTC",
        f"**Port:** P7 NAVIGATE | **Commander:** Spider Sovereign | **Spell:** TIME STOP",
        f"**AI Model:** {model} ({source}) | **Inference:** {dur}ms",
        f"**System Posture:** {posture}",
        f"**Trio:** Singer (P4) + Dancer (P5) + Summoner (P7)",
        f"",
        f"> *{CORE_THESIS}*",
        f"",
        f"---",
        f"",
        f"## SEAL — Constraint Recommendation",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **Spell** | {pick.get('seal_spell', '?')} |",
        f"| **Target** | {pick.get('seal_target', '?')} |",
        f"| **Meadows Level** | L{pick.get('seal_meadows_level', '?')} |",
        f"| **Reason** | {pick.get('seal_reason', '?')} |",
        f"",
        f"---",
        f"",
        f"## SPHERE — Frontier Recommendation",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **Spell** | {pick.get('sphere_spell', '?')} |",
        f"| **Target** | {pick.get('sphere_target', '?')} |",
        f"| **Meadows Level** | L{pick.get('sphere_meadows_level', '?')} |",
        f"| **Reason** | {pick.get('sphere_reason', '?')} |",
        f"",
        f"---",
        f"",
        f"## Landscape Assessment",
        f"",
        f"{pick.get('landscape_summary', 'No landscape data.')}",
        f"",
    ]

    # Trio coherence
    trio = pick.get("trio_coherence", "")
    if trio:
        lines.extend([
            f"### Trio Coherence",
            f"",
            f"{trio}",
            f"",
        ])

    # Strange loop reflection
    sl = pick.get("strange_loop_note", "")
    if sl:
        lines.extend([
            f"### Strange Loop Reflection",
            f"",
            f"{sl}",
            f"",
        ])

    # Mermaid diagram
    if mermaid_output:
        lines.extend([
            f"---",
            f"",
            f"## Meadows Leverage Landscape",
            f"",
            mermaid_output,
            f"",
        ])

    # Cartography stats
    if cartography_report:
        lines.extend([
            f"---",
            f"",
            f"## Cartography Data",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Events classified | {cartography_report.classified_events} / {cartography_report.total_events} |",
            f"| Hottest level | L{cartography_report.hottest_level} ({cartography_report.hottest_count} events) |",
            f"| Attractor basin (L1-L3) | {cartography_report.attractor_basin_pct}% |",
            f"| High leverage (L8-L12) | {cartography_report.high_leverage_pct}% |",
            f"| L13 status | {cartography_report.l13_status} |",
            f"| Active levels | {cartography_report.active_levels} |",
            f"| Cold levels | {cartography_report.cold_levels} |",
            f"",
        ])

    # SSOT health snapshot
    lines.extend([
        f"---",
        f"",
        f"## SSOT Health Snapshot",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total docs | {h.get('total_docs', '?')} |",
        f"| Total events | {h.get('total_events', '?')} |",
        f"| Events/1h | {h.get('events_1h', '?')} |",
        f"| Docs without port | {h.get('docs_no_port', '?')} |",
        f"| Perceives/1h | {h.get('perceives_1h', '?')} |",
        f"| Yields/1h | {h.get('yields_1h', '?')} |",
        f"| Gate blocked/1h | {h.get('gate_blocked_1h', '?')} |",
        f"| Memory loss/1h | {h.get('memory_loss_1h', '?')} |",
        f"",
    ])

    lines.extend([
        f"---",
        f"",
        f"> *\"{QUOTE}\"*",
        f"",
        f"---",
        f"",
        f"*{ALLITERATION} — {PARADOX}*",
        f"",
        f"*Report generated by {DAEMON_NAME} v{DAEMON_VERSION} | Gen{GEN}*",
    ])

    return "\n".join(lines)


def write_markdown_report(content: str) -> Path:
    """Write the markdown report to summoner_reports/."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    filename = f"{ts}_summoner.md"
    filepath = REPORT_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ═══════════════════════════════════════════════════════════════
# § 6  THE SUMMONER ENGINE
# ═══════════════════════════════════════════════════════════════

class SummonerDaemon:
    """P7 Summoner of Seals and Spheres — AI-powered strategic navigator.

    Each cycle:
      1. Collect state (SSOT + Singer + Dancer + own past)
      2. Run cartography engine for Meadows landscape
      3. Ask Gemini Deep Think for 1 SEAL + 1 SPHERE
      4. Generate markdown report + Mermaid diagram
      5. Emit 4 CloudEvents (seal, sphere, landscape, heartbeat)
    """

    def __init__(
        self,
        model_tier: str = DEFAULT_MODEL_TIER,
        hours: float = 1.0,
        dry_run: bool = False,
        health_every: int = HEALTH_EVERY_N,
    ):
        self.model_tier = model_tier
        self.hours = hours
        self.dry_run = dry_run
        self.health_every = health_every
        self.cycle = 0
        self.total_seals = 0
        self.total_spheres = 0
        self.total_reports = 0
        self.ai_calls = 0
        self.ai_failures = 0
        self.fallback_uses = 0
        self.errors = 0
        self._running = True
        self._backoff_s = 0.0

    def stop(self):
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def run_cycle(self) -> dict:
        """Execute one Summoner cycle. Returns cycle report."""
        self.cycle += 1
        t0 = time.monotonic()
        report: dict[str, Any] = {
            "cycle": self.cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": self.model_tier,
            "seal": None,
            "sphere": None,
            "posture": None,
            "ai_source": None,
            "md_path": None,
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

            # ── 2. Run cartography ──
            cart_context, cart_report = build_cartography_context(self.hours)
            mermaid_output = ""
            if CARTOGRAPHY_AVAILABLE and cart_report:
                try:
                    _, nodes, edges, violations = run_cartography(self.hours)
                    mermaid_output = render_mermaid(
                        nodes, edges, violations, self.hours,
                        cart_report.total_events,
                    )
                except Exception:
                    pass

            # ── 3. Format context and ask AI ──
            state_text = format_state_for_ai(state, cart_context)
            self.ai_calls += 1

            pick = self._ask_ai(state_text, state)
            report["ai_source"] = pick.get("_source", "?")
            report["posture"] = pick.get("system_posture", "UNKNOWN")

            # ── 4. Emit SEAL event ──
            seal_data = {
                "spell_type": "SEAL",
                "seal_spell": pick.get("seal_spell", "SEQUESTER"),
                "seal_target": pick.get("seal_target", ""),
                "seal_reason": pick.get("seal_reason", ""),
                "seal_meadows_level": pick.get("seal_meadows_level", 5),
                "seal_ref": SEAL_SPELLS.get(
                    pick.get("seal_spell", ""), {}
                ).get("ref", ""),
                "system_posture": pick.get("system_posture", ""),
                "summoner_cycle": self.cycle,
                "ai_model": pick.get("_model", "deterministic"),
                "ai_source": pick.get("_source", "fallback"),
                "core_thesis": CORE_THESIS,
                "port": DAEMON_PORT,
                "commander": "Spider Sovereign",
            }
            report["seal"] = seal_data["seal_spell"]

            if self.dry_run:
                print(
                    f"  [DRY] SEAL: {seal_data['seal_spell']} — "
                    f"{seal_data['seal_target'][:60]}"
                )
            elif conn_rw:
                write_event(
                    conn_rw,
                    EVT_SEAL,
                    f"SEAL:{seal_data['seal_spell']}:L{seal_data['seal_meadows_level']}",
                    seal_data,
                )
            self.total_seals += 1

            # ── 5. Emit SPHERE event ──
            sphere_data = {
                "spell_type": "SPHERE",
                "sphere_spell": pick.get("sphere_spell", "FORESIGHT"),
                "sphere_target": pick.get("sphere_target", ""),
                "sphere_reason": pick.get("sphere_reason", ""),
                "sphere_meadows_level": pick.get("sphere_meadows_level", 10),
                "sphere_ref": SPHERE_SPELLS.get(
                    pick.get("sphere_spell", ""), {}
                ).get("ref", ""),
                "system_posture": pick.get("system_posture", ""),
                "summoner_cycle": self.cycle,
                "ai_model": pick.get("_model", "deterministic"),
                "ai_source": pick.get("_source", "fallback"),
                "core_thesis": CORE_THESIS,
                "port": DAEMON_PORT,
                "commander": "Spider Sovereign",
            }
            report["sphere"] = sphere_data["sphere_spell"]

            if self.dry_run:
                print(
                    f"  [DRY] SPHERE: {sphere_data['sphere_spell']} — "
                    f"{sphere_data['sphere_target'][:60]}"
                )
            elif conn_rw:
                write_event(
                    conn_rw,
                    EVT_SPHERE,
                    f"SPHERE:{sphere_data['sphere_spell']}:L{sphere_data['sphere_meadows_level']}",
                    sphere_data,
                )
            self.total_spheres += 1

            # ── 6. Emit landscape event ──
            landscape_data = {
                "system_posture": pick.get("system_posture", ""),
                "landscape_summary": pick.get("landscape_summary", ""),
                "trio_coherence": pick.get("trio_coherence", ""),
                "strange_loop_note": pick.get("strange_loop_note", ""),
                "seal_spell": pick.get("seal_spell", ""),
                "sphere_spell": pick.get("sphere_spell", ""),
                "summoner_cycle": self.cycle,
                "ai_model": pick.get("_model", "deterministic"),
                "ai_source": pick.get("_source", "fallback"),
                "p7_workflow": "MAP → LATTICE → PRUNE → SELECT → DISPATCH → VISUALIZE",
                "core_thesis": CORE_THESIS,
            }
            if cart_report:
                landscape_data["hottest_level"] = cart_report.hottest_level
                landscape_data["attractor_basin_pct"] = cart_report.attractor_basin_pct
                landscape_data["high_leverage_pct"] = cart_report.high_leverage_pct
                landscape_data["l13_status"] = cart_report.l13_status

            if self.dry_run:
                print(
                    f"  [DRY] LANDSCAPE: {pick.get('system_posture', '?')} — "
                    f"{pick.get('landscape_summary', '')[:60]}"
                )
            elif conn_rw:
                write_event(
                    conn_rw,
                    EVT_LANDSCAPE,
                    f"LANDSCAPE:{pick.get('system_posture', '?')}:"
                    f"seal={pick.get('seal_spell', '?')}:"
                    f"sphere={pick.get('sphere_spell', '?')}",
                    landscape_data,
                )

            # ── 7. Generate markdown report ──
            md_content = generate_markdown_report(
                pick, state, mermaid_output, cart_report
            )
            if self.dry_run:
                # Print first 30 lines
                for line in md_content.split("\n")[:30]:
                    print(f"  {line}")
                print(f"  ... ({len(md_content.split(chr(10)))} lines total)")
            else:
                md_path = write_markdown_report(md_content)
                report["md_path"] = str(md_path)
                self.total_reports += 1

            # ── 8. Heartbeat ──
            hb_data = {
                "daemon_name": DAEMON_NAME,
                "daemon_version": DAEMON_VERSION,
                "daemon_port": DAEMON_PORT,
                "cycle": self.cycle,
                "model": self.model_tier,
                "posture": pick.get("system_posture", "UNKNOWN"),
                "seal": pick.get("seal_spell", "?"),
                "sphere": pick.get("sphere_spell", "?"),
                "total_seals": self.total_seals,
                "total_spheres": self.total_spheres,
                "total_reports": self.total_reports,
                "ai_calls": self.ai_calls,
                "ai_failures": self.ai_failures,
                "fallback_uses": self.fallback_uses,
                "errors": self.errors,
                "core_thesis": CORE_THESIS,
            }
            if self.dry_run:
                print(
                    f"  [DRY] HEARTBEAT: cycle {self.cycle}, "
                    f"posture={hb_data['posture']}"
                )
            elif conn_rw:
                write_event(
                    conn_rw,
                    EVT_HEARTBEAT,
                    f"HEARTBEAT:cycle_{self.cycle}:{pick.get('system_posture', '?')}",
                    hb_data,
                )

            # ── 9. Health snapshot (every Nth cycle) ──
            if self.cycle % self.health_every == 0:
                self._emit_health(conn_ro, conn_rw)

        except Exception as e:
            self.errors += 1
            msg = f"Cycle {self.cycle} error: {e}"
            report["errors"].append(msg)
            print(f"  [ERROR] {msg}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            # Record error to SSOT
            try:
                if conn_rw and not self.dry_run:
                    write_event(
                        conn_rw,
                        EVT_ERROR,
                        f"ERROR:cycle_{self.cycle}",
                        {"error": msg, "traceback": traceback.format_exc()},
                    )
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
        """Ask Gemini Deep Think for seal + sphere. Falls back through tiers."""
        # Try primary tier (apex = Deep Think)
        result = ask_gemini(state_text, self.model_tier)

        if "_error" not in result:
            self._backoff_s = 0.0
            return result

        # Primary failed — try fallback tier
        if self.model_tier != FALLBACK_MODEL_TIER:
            print(
                f"  [FALLBACK] Primary ({self.model_tier}) failed: "
                f"{result.get('_error', '?')[:80]}",
                file=sys.stderr,
            )
            result2 = ask_gemini(state_text, FALLBACK_MODEL_TIER)
            if "_error" not in result2:
                self.ai_failures += 1
                self._backoff_s = 0.0
                return result2
            print(
                f"  [FALLBACK] Secondary ({FALLBACK_MODEL_TIER}) also failed: "
                f"{result2.get('_error', '?')[:80]}",
                file=sys.stderr,
            )

        # All AI failed — deterministic fallback
        self.ai_failures += 1
        self.fallback_uses += 1
        self._backoff_s = min(
            (self._backoff_s or BACKOFF_BASE_S) * BACKOFF_FACTOR,
            BACKOFF_MAX_S,
        )
        print(
            f"  [FALLBACK] All AI failed — using deterministic. "
            f"Backoff: {self._backoff_s:.0f}s",
            file=sys.stderr,
        )
        return fallback_pick(state)

    def _emit_health(
        self,
        conn_ro: sqlite3.Connection,
        conn_rw: Optional[sqlite3.Connection],
    ):
        """Emit health snapshot."""
        h: dict[str, Any] = {}
        h["total_docs"] = conn_ro.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]
        h["total_events"] = conn_ro.execute(
            "SELECT COUNT(*) FROM stigmergy_events"
        ).fetchone()[0]
        h["total_words"] = (
            conn_ro.execute("SELECT SUM(word_count) FROM documents").fetchone()[0]
            or 0
        )

        # Summoner metrics
        h["summoner"] = {
            "model": self.model_tier,
            "cycle": self.cycle,
            "total_seals": self.total_seals,
            "total_spheres": self.total_spheres,
            "total_reports": self.total_reports,
            "ai_calls": self.ai_calls,
            "ai_failures": self.ai_failures,
            "fallback_uses": self.fallback_uses,
            "errors": self.errors,
            "uptime_pct": round(
                ((self.ai_calls - self.ai_failures) / max(self.ai_calls, 1))
                * 100,
                1,
            ),
        }

        if self.dry_run:
            print(
                f"  [DRY] HEALTH: {h['total_docs']} docs, "
                f"{h['total_events']} events"
            )
        elif conn_rw:
            write_event(
                conn_rw,
                EVT_HEALTH,
                f"HEALTH:cycle_{self.cycle}",
                h,
            )


# ═══════════════════════════════════════════════════════════════
# § 7  ASYNCIO DAEMON LOOP
# ═══════════════════════════════════════════════════════════════

async def daemon_loop(
    daemon: SummonerDaemon,
    interval: float = DEFAULT_INTERVAL,
    max_cycles: Optional[int] = None,
):
    """Run the Summoner on a timer loop."""
    print("=" * 72)
    print(f"  {DAEMON_NAME} v{DAEMON_VERSION} — P7 NAVIGATE Active")
    print(f"  Commander: Spider Sovereign | Trigram: ☰ Qian (Heaven)")
    print(f"  Model: {daemon.model_tier} | Window: {daemon.hours}h | Interval: {interval}s")
    print(f"  Dry-run: {daemon.dry_run} | Gemini: {GEMINI_AVAILABLE}")
    print(f"  Cartography: {CARTOGRAPHY_AVAILABLE}")
    print(f"  SSOT: {SSOT_DB}")
    print(f"  Reports: {REPORT_DIR}")
    print(f"  Thesis: {CORE_THESIS}")
    print(f"  Paradox: {PARADOX}")
    print(f"  Strange loop: {STRANGE_LOOP}")
    print("=" * 72)

    consecutive_errors = 0
    max_consecutive_errors = 5

    while daemon.is_running:
        report = daemon.run_cycle()

        # One-line cycle summary
        seal = report.get("seal", "?")
        sphere = report.get("sphere", "?")
        posture = report.get("posture", "?")
        src = report.get("ai_source", "?")
        dur = report.get("duration_ms", 0)
        md = report.get("md_path", "")
        md_short = Path(md).name if md else "(dry)"

        print(
            f"  [{report['cycle']:>4}] "
            f"🔒 SEAL:{seal} | 🔮 SPHERE:{sphere} | "
            f"{posture} | src:{src} | {dur:.0f}ms | {md_short}"
        )

        # Error tracking
        if report.get("errors"):
            consecutive_errors += 1
            for e in report["errors"]:
                print(f"         ERROR: {e}", file=sys.stderr)
            if consecutive_errors >= max_consecutive_errors:
                print(
                    f"\n  [CRITICAL] {max_consecutive_errors} consecutive errors. "
                    "Pausing 120s before retry.",
                    file=sys.stderr,
                )
                await asyncio.sleep(120)
                consecutive_errors = 0
        else:
            consecutive_errors = 0

        if max_cycles and daemon.cycle >= max_cycles:
            print(f"\n  Max cycles ({max_cycles}) reached. Stopping.")
            break

        # Wait — respect backoff if AI is struggling
        wait = max(interval, daemon._backoff_s)
        try:
            await asyncio.sleep(wait)
        except asyncio.CancelledError:
            break

    print(
        f"\n  Summoner daemon stopped. Cycles: {daemon.cycle}, "
        f"SEALS: {daemon.total_seals}, SPHERES: {daemon.total_spheres}, "
        f"Reports: {daemon.total_reports}, "
        f"AI calls: {daemon.ai_calls}, Fallbacks: {daemon.fallback_uses}, "
        f"Errors: {daemon.errors}"
    )


# ═══════════════════════════════════════════════════════════════
# § 8  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=f"{DAEMON_NAME} v{DAEMON_VERSION} — P7 Spider Sovereign (Gen{GEN})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
The Summoner reads three voices and speaks with sovereign authority:
  P4 Singer  → What is wrong, what is right
  P5 Dancer  → What to destroy, what to protect
  P7 Summoner → What to constrain, what to explore

{CORE_THESIS}

Examples:
  # Run forever, 5-min cycles, Deep Think
  python hfo_p7_summoner_daemon.py

  # Single cycle (test)
  python hfo_p7_summoner_daemon.py --single

  # Dry run (no writes)
  python hfo_p7_summoner_daemon.py --dry-run --single

  # Use free model
  python hfo_p7_summoner_daemon.py --model flash_25

  # Custom interval + window
  python hfo_p7_summoner_daemon.py --interval 600 --hours 4

  # 10 cycles then stop
  python hfo_p7_summoner_daemon.py --max-cycles 10

  # Status check
  python hfo_p7_summoner_daemon.py --status
""",
    )
    parser.add_argument(
        "--single", action="store_true", help="Run one cycle and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="No SSOT writes or file saves"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Seconds between cycles (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--max-cycles", type=int, default=None, help="Stop after N cycles"
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=1.0,
        help="Cartography time window in hours (default: 1)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL_TIER,
        help=f"Gemini model tier (default: {DEFAULT_MODEL_TIER})",
    )
    parser.add_argument(
        "--health-every",
        type=int,
        default=HEALTH_EVERY_N,
        help="Health snapshot every N cycles",
    )
    parser.add_argument(
        "--status", action="store_true", help="Print status and exit"
    )
    parser.add_argument(
        "--json", action="store_true", help="JSON output for single cycle"
    )

    args = parser.parse_args()

    # ── Status ──
    if args.status:
        print(f"{DAEMON_NAME} v{DAEMON_VERSION} — {DAEMON_PORT} Daemon Status")
        print("=" * 60)
        print(f"  HFO_ROOT:         {HFO_ROOT}")
        print(f"  SSOT_DB:          {SSOT_DB}")
        print(f"  DB exists:        {SSOT_DB.exists()}")
        print(f"  Gemini available: {GEMINI_AVAILABLE}")
        if GEMINI_AVAILABLE:
            try:
                spec = get_model(args.model)
                print(f"  Model ID:         {spec.model_id}")
                print(f"  Model tier:       {spec.tier}")
                print(f"  Vertex AI:        {VERTEX_AI_ENABLED}")
            except Exception as e:
                print(f"  Model error:      {e}")
        print(f"  Cartography:      {CARTOGRAPHY_AVAILABLE}")
        print(f"  Report dir:       {REPORT_DIR}")
        print(f"  Reports exist:    {REPORT_DIR.exists()}")
        if REPORT_DIR.exists():
            reports = sorted(REPORT_DIR.glob("*_summoner.md"))
            print(f"  Report count:     {len(reports)}")
            if reports:
                print(f"  Latest:           {reports[-1].name}")
        # Quick health
        if SSOT_DB.exists():
            conn = get_db_ro()
            s = collect_state(conn)
            conn.close()
            h = s["health"]
            print(f"  Total docs:       {h['total_docs']}")
            print(f"  Total events:     {h['total_events']}")
            print(f"  Events/1h:        {h['events_1h']}")
            print(f"  Docs w/o port:    {h.get('docs_no_port', '?')}")
            print(f"  Singer events:    {len(s.get('singer_songs', []))}")
            print(f"  Dancer events:    {len(s.get('dancer_steps', []))}")
            print(f"  Past seals:       {len(s.get('past_seals_spheres', []))}")
        print(f"\n  {CORE_THESIS}")
        return

    # ── Create daemon ──
    daemon = SummonerDaemon(
        model_tier=args.model,
        hours=args.hours,
        dry_run=args.dry_run,
        health_every=args.health_every,
    )

    # ── Signal handling ──
    def _handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. Stopping Summoner...")
        daemon.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ── Single mode ──
    if args.single:
        report = daemon.run_cycle()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"\n{DAEMON_NAME} v{DAEMON_VERSION} — Single Cycle Report")
            print("=" * 60)
            print(f"  Cycle:     {report['cycle']}")
            print(f"  Model:     {report['model']}")
            print(f"  AI Source: {report.get('ai_source', '?')}")
            print(f"  Posture:   {report.get('posture', '?')}")
            print(f"  SEAL:      {report.get('seal', '?')}")
            print(f"  SPHERE:    {report.get('sphere', '?')}")
            print(f"  MD Report: {report.get('md_path', '(dry run)')}")
            print(f"  Duration:  {report.get('duration_ms', 0):.0f}ms")
            if report.get("errors"):
                print(f"  Errors:    {report['errors']}")
            print(f"\n  {CORE_THESIS}")
            print(f"  {STRANGE_LOOP}")
        return

    # ── Daemon mode ──
    asyncio.run(
        daemon_loop(daemon, interval=args.interval, max_cycles=args.max_cycles)
    )


if __name__ == "__main__":
    main()
