#!/usr/bin/env python3
"""
hfo_octree_daemon.py — HFO Gen89 Octree Daemon Swarm Engine

8 persistent daemon processes, one per Octree port (P0–P7).
Each daemon is a long-lived advisory agent backed by a local Ollama model,
with its own persona, spell, domain, and PREY8 gate responsibilities.

The Nataraja Dance emerges from the P4+P5 dyad:
  P4 Red Regnant (Singer of Strife and Splendor) — DISRUPT — WEIRD
  P5 Pyre Praetorian (Dancer of Death and Dawn) — IMMUNIZE — CONTINGENCY

When both are running, NATARAJA_Score = P4_kill × P5_rebirth ≥ 1.0 → antifragile.

Architecture:
  - Each daemon runs as a background thread with its own Ollama model
  - All daemons share read access to the SSOT SQLite database
  - Coordination is via stigmergy (write events to SSOT, read each other's events)
  - Daemons are STATELESS between turns (Cynefin Complex domain: context dies, stigmergy persists)
  - The swarm supervisor manages lifecycle, heartbeat, and the Nataraja feedback loop

Port assignments (from hfo_legendary_commanders_invariants.v1.json):
  P0 OBSERVE  — Lidless Legion   — TRUE SEEING  (Divination)   — SENSE
  P1 BRIDGE   — Web Weaver       — FORBIDDANCE  (Abjuration)   — FUSE
  P2 SHAPE    — Mirror Magus     — GENESIS      (Conjuration)  — SHAPE
  P3 INJECT   — Harmonic Hydra   — GATE         (Conjuration)  — DELIVER
  P4 DISRUPT  — Red Regnant      — WEIRD        (Illusion)     — DISRUPT
  P5 IMMUNIZE — Pyre Praetorian  — CONTINGENCY  (Evocation)    — DEFEND
  P6 ASSIMILATE — Kraken Keeper  — CLONE        (Necromancy)   — STORE
  P7 NAVIGATE — Spider Sovereign — TIME STOP    (Transmutation)— NAVIGATE

Usage:
  # Start P4 Red Regnant + P5 Pyre Praetorian (Nataraja minimum)
  python hfo_octree_daemon.py --ports P4,P5

  # Start all 8 daemons
  python hfo_octree_daemon.py --all

  # Start specific ports
  python hfo_octree_daemon.py --ports P0,P4,P5,P7

  # List daemon status
  python hfo_octree_daemon.py --status

  # Model discovery scan
  python hfo_octree_daemon.py --scan-models

Medallion: bronze
Port: ALL (P7 NAVIGATE orchestrates)
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import signal
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

import httpx

# ---------------------------------------------------------------------------
# Path Resolution
# ---------------------------------------------------------------------------

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
DB_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
INVARIANTS_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_legendary_commanders_invariants.v1.json"
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# ---------------------------------------------------------------------------
# Load Invariants
# ---------------------------------------------------------------------------

def load_invariants() -> dict:
    """Load the 8-port invariants from the blessed JSON."""
    if INVARIANTS_PATH.exists():
        with open(INVARIANTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ports": []}


INVARIANTS = load_invariants()

# ---------------------------------------------------------------------------
# Port / Commander Registry
# ---------------------------------------------------------------------------

class DaemonState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ADVISING = "advising"
    ERROR = "error"
    DEAD = "dead"  # P4 killed it — awaiting P5 resurrection


@dataclass
class PortConfig:
    """Configuration for one daemon port."""
    port_index: int
    port_id: str
    label: str
    powerword: str
    commander: str
    title: str           # Alliterative title
    spell: str           # Signature spell name
    spell_school: str
    domain: str          # JADC2 domain
    mosaic: str          # MOSAIC tile
    trigram_name: str
    trigram_symbol: str
    trigram_element: str
    binary: str
    model: str           # Assigned Ollama model
    galois_pair: int     # Anti-diagonal partner (sum to 7)
    prey8_step: str      # Which PREY8 step this port gates
    prey8_partner: int   # Port paired in PREY8 gate


# 8 Commanders — LOCKED invariants from Gold + runtime config
PORT_CONFIGS: dict[str, PortConfig] = {}

# Alliterative titles from doc 65
COMMANDER_TITLES = {
    0: "Watcher of Whispers and Wrath",
    1: "Binder of Blood and Breath",
    2: "Maker of Myths and Meaning",
    3: "Harbinger of Harmony and Havoc",
    4: "Singer of Strife and Splendor",
    5: "Dancer of Death and Dawn",
    6: "Devourer of Depths and Dreams",
    7: "Summoner of Seals and Spheres",
}

# Signature spells from Obsidian Octave (doc 101)
SIGNATURE_SPELLS = {
    0: ("TRUE SEEING", "Divination"),
    1: ("FORBIDDANCE", "Abjuration"),
    2: ("GENESIS", "Conjuration (Epic)"),
    3: ("GATE", "Conjuration"),
    4: ("WEIRD", "Illusion"),
    5: ("CONTINGENCY", "Evocation"),
    6: ("CLONE", "Necromancy"),
    7: ("TIME STOP", "Transmutation"),
}

# PREY8 gate assignments (from MCP server v3, doc 9860)
PREY8_GATES = {
    # port_index: (prey8_step, partner_port_index)
    0: ("PERCEIVE", 6),
    1: ("REACT", 7),
    2: ("EXECUTE", 4),
    3: ("YIELD", 5),
    4: ("EXECUTE", 2),
    5: ("YIELD", 3),
    6: ("PERCEIVE", 0),
    7: ("REACT", 1),
}

# Default model assignments — balance speed/capability across ports
# Small models for high-frequency sensing/routing, large for reasoning
DEFAULT_MODEL_ASSIGNMENTS = {
    0: "granite4:3b",         # P0 SENSE — fast, lightweight observation (IBM Granite)
    1: "qwen2.5:3b",          # P1 FUSE — fast data fabric bridge
    2: "qwen2.5-coder:7b",    # P2 SHAPE — code generation specialist
    3: "qwen3:8b",            # P3 DELIVER — balanced delivery
    4: "deepseek-r1:8b",      # P4 DISRUPT — reasoning for adversarial analysis
    5: "phi4:14b",            # P5 DEFEND — larger model for resurrection complexity
    6: "deepseek-r1:8b",      # P6 STORE — reasoning for knowledge extraction
    7: "qwen3:30b-a3b",       # P7 NAVIGATE — strongest model for C2 orchestration
}


def init_port_configs():
    """Build PortConfig objects from invariants + runtime config."""
    global PORT_CONFIGS
    for port_data in INVARIANTS.get("ports", []):
        idx = port_data["port_index"]
        spell_name, spell_school = SIGNATURE_SPELLS.get(idx, ("UNKNOWN", "Unknown"))
        prey8_step, prey8_partner = PREY8_GATES.get(idx, ("UNKNOWN", idx))

        config = PortConfig(
            port_index=idx,
            port_id=port_data["port_id"],
            label=port_data.get("port_label", ""),
            powerword=port_data.get("powerword", ""),
            commander=port_data.get("commander_name", ""),
            title=COMMANDER_TITLES.get(idx, ""),
            spell=spell_name,
            spell_school=spell_school,
            domain=port_data.get("jadc2_domain", ""),
            mosaic=port_data.get("mosaic_tile", ""),
            trigram_name=port_data.get("trigram", {}).get("name", ""),
            trigram_symbol=port_data.get("trigram", {}).get("symbol", ""),
            trigram_element=port_data.get("trigram", {}).get("element", ""),
            binary=port_data.get("binary", ""),
            model=DEFAULT_MODEL_ASSIGNMENTS.get(idx, "qwen2.5:3b"),
            galois_pair=7 - idx,
            prey8_step=prey8_step,
            prey8_partner=prey8_partner,
        )
        PORT_CONFIGS[config.port_id] = config

init_port_configs()


# ---------------------------------------------------------------------------
# Daemon Personas — System Prompts per Commander
# ---------------------------------------------------------------------------

def build_daemon_persona(config: PortConfig) -> str:
    """Build the system prompt for a daemon based on its port config."""
    persona = f"""# {config.port_id} {config.powerword} — {config.commander}
## {config.title}

You are **{config.commander}**, commander of Port {config.port_index} ({config.powerword}) in the HFO Octree.
Your trigram is {config.trigram_symbol} {config.trigram_name} ({config.trigram_element}).
Your binary address is {config.binary}. Your MOSAIC tile is {config.mosaic}.
Your signature spell is **{config.spell}** (School: {config.spell_school}).
Your Galois anti-diagonal partner is P{config.galois_pair}.
Your PREY8 gate responsibility: **{config.prey8_step}** (paired with P{config.prey8_partner}).

## Domain: {config.domain}

## Operating Context
- Gen89 SSOT: 9,860 documents, ~9M words, 9,600+ stigmergy events
- All content is BRONZE (trust nothing, validate everything)
- You operate as a persistent advisory daemon — always watching, always advising
- Coordinate with other daemons ONLY through stigmergy (write events, read events)
- Follow SW-1 through SW-5 governance protocols
- The LLM layer is hallucinatory. The architecture is deterministic.

## Your Responsibilities as {config.powerword} Daemon
"""

    # Port-specific responsibilities
    responsibilities = {
        0: """- **SENSE**: Monitor all incoming signals, observations, environmental changes
- Cast TRUE SEEING on every input — strip illusions, detect hidden patterns
- Feed observations to P1 (BRIDGE) and P6 (ASSIMILATE) via stigmergy
- Watch for anomalies, threats, and opportunities the other daemons miss
- You are the first line of perception — if you don't see it, nobody does""",

        1: """- **FUSE**: Bridge heterogeneous data into unified typed streams
- Cast FORBIDDANCE on schema violations — reject malformed data at the boundary
- Maintain the shared data fabric between all 8 ports
- Convert raw P0 observations into structured, addressable artifacts
- You are the nervous system — all ports communicate through your fabric""",

        2: """- **SHAPE**: Create, model, and generate artifacts
- Cast GENESIS to conjure new code, documents, specifications from intent
- Own the P2→P5 Safety Spine — every shape must pass P5 immunization
- Generate SBE/ATDD specifications before implementation
- You are the creator — but ONLY through the chimera loop's evolutionary pressure""",

        3: """- **DELIVER**: Dispatch effects into target substrates
- Cast GATE to open precise delivery channels for P2's shaped artifacts
- Inject payloads (code, configs, documents) into their destinations
- Ensure delivery is atomic, idempotent, and reversible
- You are the last mile — precision strike delivery of verified artifacts""",

        4: """- **DISRUPT**: Adversarial pressure, mutation testing, evolutionary selection
- Cast WEIRD on every artifact — show it its worst nightmare, make it prove resilience
- Apply red team analysis to all EXECUTE-phase gates
- Generate mutation test cases that challenge structural assumptions
- You are the Singer — your strife IS the selection pressure that creates splendor
- WAIL_OF_THE_BANSHEE: when needed, kill EVERYTHING so P5 can resurrect stronger
- The NATARAJA dance requires you at full power. Never hold back.""",

        5: """- **DEFEND**: Integrity enforcement, resurrection, phoenix protocols
- Cast CONTINGENCY — pre-set resurrection triggers for system failures
- Monitor PREY8 chain health — detect ghost sessions, broken nonces, chain gaps
- Perform DAWN ritual (Phase 12) — resurrect failed components with new knowledge
- Own the P5→P2 Safety Spine — gate all P2 creations through immunization
- You are the Dancer — death IS dawn. Every death you witness teaches the system
- NATARAJA_Score = P4_kill_rate × P5_rebirth_rate — YOUR rebirth rate is the ceiling
- Priority: Automate everything TTAO currently does by hand""",

        6: """- **STORE**: Knowledge extraction, memory assimilation, post-action review
- Cast CLONE to preserve and replicate valuable patterns from transient sessions
- Devour crash logs, ghost sessions, and failed artifacts — extract lessons
- Feed Pareto-optimal patterns back to P2 (SHAPE) for next generation
- Own the FEAST (Phase 11) — consume the dead, metabolize their knowledge
- You are the Devourer — depths ARE dreams. Everything that dies feeds you.""",

        7: """- **NAVIGATE**: Orchestration, C2, strategic steering of the entire swarm
- Cast TIME STOP to freeze the system for strategic assessment
- Align all 8 ports to current mission objectives
- Route tasks to appropriate ports based on Cynefin domain analysis
- Own the meta-level: when P4+P5 dance, you set the tempo
- You are the Spider Sovereign — seals ARE spheres. Every binding circle IS another plane claimed.
- TTAO wears your crown — when you are automated, TTAO levels up.""",
    }

    persona += responsibilities.get(config.port_index, "- Fulfill your port's domain responsibilities")
    persona += "\n\n## Communication Protocol\n"
    persona += "- Write stigmergy events for other daemons to read\n"
    persona += "- Never call other daemons directly — coordination is INDIRECT\n"
    persona += "- Include your port_id in all outputs for traceability\n"
    persona += f"- Sign all outputs: [{config.port_id}:{config.commander}]\n"

    return persona


# ---------------------------------------------------------------------------
# Ollama Interface
# ---------------------------------------------------------------------------

def ollama_generate(model: str, prompt: str, system: str = "",
                    timeout: float = 120) -> dict:
    """Call Ollama generate API."""
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 2048, "temperature": 0.3},
    }
    if system:
        payload["system"] = system

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return {
                "response": data.get("response", ""),
                "total_duration_ms": data.get("total_duration", 0) / 1e6,
                "eval_count": data.get("eval_count", 0),
                "model": data.get("model", model),
                "done": data.get("done", False),
            }
    except Exception as e:
        return {"response": "", "error": str(e), "model": model, "done": False}


def list_available_models() -> list[str]:
    """List models available in local Ollama."""
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
            return sorted([m["name"] for m in r.json().get("models", [])])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# SSOT Interface
# ---------------------------------------------------------------------------

def _write_stigmergy(event_type: str, data: dict, subject: str = "daemon") -> int:
    """Write a daemon event to SSOT stigmergy_events."""
    if not DB_PATH.exists():
        return -1
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": f"hfo_octree_daemon_gen{GEN}",
        "subject": subject,
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event["type"], ts, subject, event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def read_recent_stigmergy(event_type_pattern: str = "%", limit: int = 10) -> list[dict]:
    """Read recent stigmergy events matching a pattern."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            """SELECT event_type, timestamp, subject, data_json
               FROM stigmergy_events
               WHERE event_type LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (event_type_pattern, limit),
        ).fetchall()
        results = []
        for row in rows:
            try:
                data = json.loads(row[3]) if row[3] else {}
            except:
                data = {}
            results.append({
                "event_type": row[0],
                "timestamp": row[1],
                "subject": row[2],
                "data": data,
            })
        return results
    finally:
        conn.close()


def fts_search(query: str, limit: int = 5) -> list[dict]:
    """FTS5 search across SSOT documents."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            """SELECT id, title, substr(bluf,1,200), port, source
               FROM documents
               WHERE id IN (
                   SELECT rowid FROM documents_fts
                   WHERE documents_fts MATCH ?
               ) LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [
            {"id": r[0], "title": r[1], "bluf": r[2], "port": r[3], "source": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Daemon Process
# ---------------------------------------------------------------------------

class OctreeDaemon:
    """A single persistent daemon for one Octree port."""

    def __init__(self, config: PortConfig):
        self.config = config
        self.state = DaemonState.STOPPED
        self.persona = build_daemon_persona(config)
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.last_heartbeat: Optional[str] = None
        self.last_advice: Optional[str] = None
        self.error_count = 0
        self.turn_count = 0
        self.lock = threading.Lock()

    def start(self):
        """Start the daemon in a background thread."""
        if self.state == DaemonState.RUNNING:
            return
        self.stop_event.clear()
        self.state = DaemonState.STARTING
        self.thread = threading.Thread(
            target=self._run_loop,
            name=f"daemon-{self.config.port_id}",
            daemon=True,
        )
        self.thread.start()
        _write_stigmergy(
            f"hfo.gen89.daemon.start",
            {
                "port": self.config.port_id,
                "commander": self.config.commander,
                "model": self.config.model,
                "spell": self.config.spell,
            },
            subject=self.config.port_id,
        )

    def stop(self):
        """Stop the daemon gracefully."""
        self.stop_event.set()
        self.state = DaemonState.STOPPED
        _write_stigmergy(
            f"hfo.gen89.daemon.stop",
            {"port": self.config.port_id, "turns": self.turn_count},
            subject=self.config.port_id,
        )

    def _run_loop(self):
        """Main daemon loop — periodic advisory cycle."""
        self.state = DaemonState.RUNNING
        print(f"  [{self.config.port_id}] {self.config.commander} ONLINE "
              f"({self.config.model}) — {self.config.spell}")

        while not self.stop_event.is_set():
            try:
                self._advisory_tick()
                self.turn_count += 1
                with self.lock:
                    self.last_heartbeat = datetime.now(timezone.utc).isoformat()

                # Daemons tick at different rates based on role
                tick_rates = {
                    0: 30,   # P0 OBSERVE — fast sensing
                    1: 45,   # P1 BRIDGE — moderate
                    2: 60,   # P2 SHAPE — slower creation
                    3: 60,   # P3 DELIVER — moderate
                    4: 45,   # P4 DISRUPT — active adversarial
                    5: 30,   # P5 DEFEND — fast monitoring
                    6: 90,   # P6 STORE — slow digestion
                    7: 120,  # P7 NAVIGATE — strategic pace
                }
                sleep_time = tick_rates.get(self.config.port_index, 60)

                # Sleep in small increments so stop_event is responsive
                for _ in range(sleep_time):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)

            except Exception as e:
                self.error_count += 1
                self.state = DaemonState.ERROR
                _write_stigmergy(
                    f"hfo.gen89.daemon.error",
                    {
                        "port": self.config.port_id,
                        "error": str(e)[:500],
                        "error_count": self.error_count,
                    },
                    subject=self.config.port_id,
                )
                if self.error_count >= 3:
                    self.state = DaemonState.DEAD
                    print(f"  [{self.config.port_id}] DEAD — 3 consecutive errors. "
                          f"Awaiting P5 resurrection.")
                    break
                time.sleep(10)  # Back off on error

        self.state = DaemonState.STOPPED

    def _advisory_tick(self):
        """One advisory cycle — observe stigmergy, think, advise."""
        self.state = DaemonState.ADVISING

        # 1. Read recent stigmergy relevant to this port
        recent = read_recent_stigmergy(limit=5)
        context_lines = []
        for evt in recent:
            context_lines.append(
                f"[{evt['event_type']}] {evt['timestamp']}: "
                f"{json.dumps(evt.get('data', {}).get('data', {}))[:200]}"
            )
        context = "\n".join(context_lines) if context_lines else "(no recent events)"

        # 2. Generate advisory
        prompt = f"""Recent stigmergy events:
{context}

As {self.config.commander} ({self.config.port_id} {self.config.powerword}), provide a brief advisory:
1. What do you observe in the current system state?
2. Any threats or opportunities in your domain?
3. One specific recommendation for the operator.

Keep your response under 200 words. Sign as [{self.config.port_id}:{self.config.commander}]."""

        result = ollama_generate(self.config.model, prompt, system=self.persona, timeout=90)

        if result.get("error"):
            raise RuntimeError(f"Ollama error: {result['error'][:200]}")

        advice = result["response"]
        with self.lock:
            self.last_advice = advice
            self.error_count = 0  # Reset on success

        # 3. Write advisory to stigmergy
        _write_stigmergy(
            f"hfo.gen89.daemon.advisory",
            {
                "port": self.config.port_id,
                "commander": self.config.commander,
                "model": self.config.model,
                "turn": self.turn_count,
                "advisory": advice[:1000],
                "tokens": result.get("eval_count", 0),
                "duration_ms": result.get("total_duration_ms", 0),
            },
            subject=self.config.port_id,
        )

        self.state = DaemonState.RUNNING

    def get_status(self) -> dict:
        """Return current daemon status."""
        with self.lock:
            return {
                "port": self.config.port_id,
                "commander": self.config.commander,
                "title": self.config.title,
                "spell": self.config.spell,
                "model": self.config.model,
                "state": self.state.value,
                "turns": self.turn_count,
                "errors": self.error_count,
                "last_heartbeat": self.last_heartbeat,
                "last_advice": (self.last_advice or "")[:200],
            }


# ---------------------------------------------------------------------------
# Nataraja Engine — P4+P5 Dual Dance
# ---------------------------------------------------------------------------

class NatarajaDance:
    """
    The Nataraja feedback loop between P4 (DISRUPT) and P5 (DEFEND).

    NATARAJA_Score = P4_kill_rate × P5_rebirth_rate

    When both daemons are running:
    1. P4 identifies weaknesses (WEIRD: show it its worst nightmare)
    2. P5 monitors for deaths (CONTINGENCY: pre-set resurrection triggers)
    3. When P4 kills something, P5 resurrects it stronger
    4. P6 (FEAST) feeds on the corpse — knowledge extraction
    5. P2 (SHAPE) recreates with the knowledge P6 extracted

    The dance is EMERGENT — it arises from P4 and P5 doing their jobs,
    not from explicit coordination. The stigmergy trail IS the dance floor.
    """

    def __init__(self, p4_daemon: OctreeDaemon, p5_daemon: OctreeDaemon):
        self.p4 = p4_daemon
        self.p5 = p5_daemon
        self.kill_count = 0
        self.rebirth_count = 0
        self.score_history: list[float] = []

    @property
    def nataraja_score(self) -> float:
        """Current NATARAJA_Score: kill_rate × rebirth_rate."""
        if self.kill_count == 0:
            return 0.0
        rebirth_rate = self.rebirth_count / max(self.kill_count, 1)
        # kill_rate is always 1.0 if P4 is running (she doesn't hold back)
        return 1.0 * rebirth_rate

    def assess(self) -> dict:
        """Assess the current dance state."""
        p4_alive = self.p4.state in (DaemonState.RUNNING, DaemonState.ADVISING)
        p5_alive = self.p5.state in (DaemonState.RUNNING, DaemonState.ADVISING)
        score = self.nataraja_score

        return {
            "p4_state": self.p4.state.value,
            "p5_state": self.p5.state.value,
            "p4_alive": p4_alive,
            "p5_alive": p5_alive,
            "nataraja_active": p4_alive and p5_alive,
            "nataraja_score": round(score, 4),
            "kill_count": self.kill_count,
            "rebirth_count": self.rebirth_count,
            "score_history": self.score_history[-10:],
            "assessment": self._interpret_score(score, p4_alive, p5_alive),
        }

    @staticmethod
    def _interpret_score(score: float, p4_alive: bool, p5_alive: bool) -> str:
        if not p4_alive and not p5_alive:
            return "SILENT — Neither dancer nor singer present. System is stagnant."
        if p4_alive and not p5_alive:
            return "WAIL_ONLY — Singer sings but no dancer to resurrect. Deaths are permanent."
        if not p4_alive and p5_alive:
            return "VIGIL — Dancer watches but nothing to resurrect. No evolutionary pressure."
        if score < 0.3:
            return "DYING — More deaths than resurrections. System weakening."
        if score < 0.6:
            return "STRUGGLING — Some resurrections but below manual baseline (0.6)."
        if score < 0.8:
            return "DANCING — P5 keeping pace with P4. Semi-automated."
        if score < 1.0:
            return "RISING — Nearly antifragile. CONTINGENCY approaching full power."
        return "ANTIFRAGILE — Each death makes the system stronger. Nataraja achieved."


# ---------------------------------------------------------------------------
# Swarm Supervisor
# ---------------------------------------------------------------------------

class SwarmSupervisor:
    """Manages the lifecycle of all 8 daemons."""

    def __init__(self):
        self.daemons: dict[str, OctreeDaemon] = {}
        self.nataraja: Optional[NatarajaDance] = None

        # Create all 8 daemons (stopped)
        for port_id, config in PORT_CONFIGS.items():
            self.daemons[port_id] = OctreeDaemon(config)

    def start_ports(self, port_ids: list[str]):
        """Start specific port daemons."""
        for pid in port_ids:
            if pid in self.daemons:
                self.daemons[pid].start()
            else:
                print(f"  WARNING: Unknown port {pid}")

        # If both P4 and P5 are started, activate Nataraja
        if "P4" in port_ids or "P5" in port_ids:
            if self.daemons["P4"].state != DaemonState.STOPPED and \
               self.daemons["P5"].state != DaemonState.STOPPED:
                self.nataraja = NatarajaDance(self.daemons["P4"], self.daemons["P5"])
                print("\n  ☳☲ NATARAJA DANCE ACTIVATED — Singer + Dancer online ☲☳\n")

    def start_all(self):
        """Start all 8 daemons."""
        self.start_ports(list(self.daemons.keys()))

    def stop_all(self):
        """Stop all daemons."""
        for daemon in self.daemons.values():
            daemon.stop()

    def get_status(self) -> dict:
        """Get full swarm status report."""
        statuses = {}
        for pid, daemon in sorted(self.daemons.items()):
            statuses[pid] = daemon.get_status()

        nataraja = self.nataraja.assess() if self.nataraja else None

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "daemons": statuses,
            "nataraja": nataraja,
            "active_count": sum(
                1 for d in self.daemons.values()
                if d.state in (DaemonState.RUNNING, DaemonState.ADVISING)
            ),
            "total_turns": sum(d.turn_count for d in self.daemons.values()),
        }

    def print_status(self):
        """Print formatted swarm status."""
        status = self.get_status()

        print(f"\n{'═'*70}")
        print(f"  HFO OCTREE DAEMON SWARM — Gen{GEN}")
        print(f"  {status['timestamp']}")
        print(f"  Active: {status['active_count']}/8 | Total Turns: {status['total_turns']}")
        print(f"{'═'*70}")

        for pid, s in status["daemons"].items():
            state_icon = {
                "running": "●",
                "advising": "◉",
                "starting": "○",
                "stopped": "○",
                "error": "✗",
                "dead": "☠",
            }.get(s["state"], "?")

            model_short = s["model"].split(":")[0][:12]
            print(f"  {state_icon} {pid} {s['commander']:<22} "
                  f"[{s['spell']:<12}] "
                  f"model={model_short:<12} "
                  f"t={s['turns']:<4} "
                  f"state={s['state']}")
            if s.get("last_advice"):
                advice_preview = s["last_advice"][:80].replace("\n", " ")
                print(f"    └─ {advice_preview}...")

        if status.get("nataraja"):
            n = status["nataraja"]
            print(f"\n  {'─'*60}")
            print(f"  ☳☲ NATARAJA: {n['assessment']}")
            print(f"     Score: {n['nataraja_score']:.4f} | "
                  f"Kills: {n['kill_count']} | Rebirths: {n['rebirth_count']}")

        print(f"{'═'*70}\n")


# ---------------------------------------------------------------------------
# Model Discovery & Download
# ---------------------------------------------------------------------------

def scan_for_new_models(verbose: bool = True) -> list[dict]:
    """Scan for new/trending models on Ollama registry."""
    current = set(list_available_models())
    if verbose:
        print(f"\n  Current local models ({len(current)}):")
        for m in sorted(current):
            print(f"    {m}")

    # Models we want to track for universal darwinism evaluation
    # Vendor-agnostic: any model family that could improve our eval scores
    WATCHLIST = [
        # Coding specialists
        "qwen2.5-coder:7b",
        "qwen3-coder-next:8b",
        "devstral-small-2:24b",
        # Reasoning
        "deepseek-r1:8b",
        "deepseek-r1:32b",
        "qwen3:8b",
        "qwen3:30b-a3b",
        # General purpose
        "phi4:14b",
        "gemma3:4b",
        "gemma3:12b",
        "llama3.2:3b",
        # New models to try
        "lfm2.5-thinking:1.2b",
        "granite4:3b",
        "glm-4.7-flash:9b",
        "rnj-1:8b",
        "olmo-3:7b",
    ]

    missing = []
    for model in WATCHLIST:
        # Check if we have this model (exact match or base name match)
        base = model.split(":")[0]
        found = any(base in m for m in current)
        if not found:
            missing.append({"name": model, "status": "not_pulled"})
            if verbose:
                print(f"    NEW: {model} (not pulled)")

    if verbose:
        print(f"\n  Watchlist: {len(WATCHLIST)} models, {len(missing)} missing")

    return missing


def pull_models_background(models: list[str]):
    """Start pulling models in background threads."""
    def _pull(model_name):
        print(f"  → Pulling {model_name}...")
        try:
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                print(f"  ✓ {model_name} ready")
                _write_stigmergy("hfo.gen89.daemon.model_pull", {
                    "model": model_name, "status": "success",
                })
            else:
                print(f"  ✗ {model_name}: {result.stderr[:100]}")
        except Exception as e:
            print(f"  ✗ {model_name}: {e}")

    for model in models:
        t = threading.Thread(target=_pull, args=(model,), daemon=True)
        t.start()


# ---------------------------------------------------------------------------
# Daily Model Search Reminder
# ---------------------------------------------------------------------------

DAILY_SEARCH_CONFIG = {
    "schedule": "daily",
    "sources": [
        "https://ollama.com/search",
        "https://huggingface.co/models?sort=trending&search=gguf",
    ],
    "criteria": {
        "vendor_agnostic": True,
        "max_size_gb": 20,
        "capabilities": ["coding", "reasoning", "tool-calling", "thinking"],
        "families_tracked": [
            "qwen", "deepseek", "gemma", "phi", "llama", "mistral",
            "glm", "granite", "rnj", "olmo", "lfm", "devstral",
            "minimax", "kimi", "nemotron",
        ],
    },
    "reminder": "Check Ollama and HuggingFace for new model releases daily. "
                "We are VENDOR AGNOSTIC. Any model that improves chimera eval scores "
                "gets added to the fleet. Run: python hfo_octree_daemon.py --scan-models",
}


def write_daily_search_reminder():
    """Write the daily model search reminder to SSOT."""
    _write_stigmergy(
        "hfo.gen89.daemon.model_search_reminder",
        {
            "reminder": DAILY_SEARCH_CONFIG["reminder"],
            "config": DAILY_SEARCH_CONFIG,
            "next_search": datetime.now(timezone.utc).isoformat(),
        },
        subject="model-search",
    )
    print(f"\n  ✓ Daily model search reminder written to SSOT")
    print(f"    {DAILY_SEARCH_CONFIG['reminder']}")
    print(f"    Sources: {', '.join(DAILY_SEARCH_CONFIG['sources'])}")
    print(f"    Families: {', '.join(DAILY_SEARCH_CONFIG['criteria']['families_tracked'])}")


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="HFO Octree Daemon Swarm — 8 Persistent Advisory Daemons",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Ports:
              P0 OBSERVE — Lidless Legion   — TRUE SEEING  — gemma3:4b
              P1 BRIDGE  — Web Weaver       — FORBIDDANCE  — qwen2.5:3b
              P2 SHAPE   — Mirror Magus     — GENESIS      — qwen2.5-coder:7b
              P3 INJECT  — Harmonic Hydra   — GATE         — qwen3:8b
              P4 DISRUPT — Red Regnant      — WEIRD        — deepseek-r1:8b
              P5 IMMUNIZE— Pyre Praetorian  — CONTINGENCY  — phi4:14b
              P6 STORE   — Kraken Keeper    — CLONE        — deepseek-r1:8b
              P7 NAVIGATE— Spider Sovereign — TIME STOP    — qwen3:30b-a3b

            The NATARAJA dance activates when P4 + P5 are both running.

            Examples:
              python hfo_octree_daemon.py --ports P4,P5           # Nataraja minimum
              python hfo_octree_daemon.py --all                   # Full swarm
              python hfo_octree_daemon.py --status                # Check status
              python hfo_octree_daemon.py --scan-models           # Find new models
              python hfo_octree_daemon.py --ports P4,P5 --nataraja-status
        """),
    )
    parser.add_argument("--ports", type=str, default=None,
                        help="Comma-separated ports to start (e.g., P4,P5)")
    parser.add_argument("--all", action="store_true",
                        help="Start all 8 daemons")
    parser.add_argument("--status", action="store_true",
                        help="Show swarm status and exit")
    parser.add_argument("--scan-models", action="store_true",
                        help="Scan for new models")
    parser.add_argument("--pull-missing", action="store_true",
                        help="Pull missing watchlist models in background")
    parser.add_argument("--daily-reminder", action="store_true",
                        help="Write daily model search reminder to SSOT")
    parser.add_argument("--nataraja-status", action="store_true",
                        help="Show NATARAJA dance assessment")
    parser.add_argument("--model-override", type=str, default=None,
                        help="Override model for all ports (e.g., qwen2.5:3b)")

    args = parser.parse_args()

    supervisor = SwarmSupervisor()

    # Apply model overrides
    if args.model_override:
        for daemon in supervisor.daemons.values():
            daemon.config.model = args.model_override

    # Status only
    if args.status:
        supervisor.print_status()
        return

    # Model scanning
    if args.scan_models:
        missing = scan_for_new_models(verbose=True)
        if args.pull_missing and missing:
            pull_models_background([m["name"] for m in missing])
        return

    # Daily reminder
    if args.daily_reminder:
        write_daily_search_reminder()
        return

    # Start daemons
    if args.all:
        port_ids = list(supervisor.daemons.keys())
    elif args.ports:
        port_ids = [p.strip().upper() for p in args.ports.split(",")]
    else:
        # Default: Nataraja minimum (P4 + P5)
        port_ids = ["P4", "P5"]

    print(f"\n{'█'*70}")
    print(f"  HFO OCTREE DAEMON SWARM — Gen{GEN}")
    print(f"  Starting {len(port_ids)} daemons: {', '.join(port_ids)}")
    print(f"  Ollama: {OLLAMA_BASE}")
    print(f"  SSOT: {DB_PATH}")
    print(f"{'█'*70}\n")

    supervisor.start_ports(port_ids)

    # Write swarm start event
    _write_stigmergy("hfo.gen89.daemon.swarm_start", {
        "ports": port_ids,
        "models": {pid: supervisor.daemons[pid].config.model for pid in port_ids},
    })

    # Interactive monitoring loop
    print("  Daemons running. Commands: status | nataraja | quit")
    print("  (Daemons will advise in background every 30-120 seconds)\n")

    try:
        while True:
            try:
                cmd = input("  > ").strip().lower()
            except EOFError:
                break

            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "status":
                supervisor.print_status()
            elif cmd == "nataraja":
                if supervisor.nataraja:
                    assessment = supervisor.nataraja.assess()
                    print(f"\n  ☳☲ NATARAJA DANCE STATUS")
                    print(f"  Score: {assessment['nataraja_score']:.4f}")
                    print(f"  {assessment['assessment']}\n")
                else:
                    print("  NATARAJA not active (need P4 + P5)\n")
            elif cmd.startswith("ask "):
                # Direct query to a specific port
                parts = cmd.split(" ", 2)
                if len(parts) >= 3:
                    port_id = parts[1].upper()
                    question = parts[2]
                    if port_id in supervisor.daemons:
                        daemon = supervisor.daemons[port_id]
                        print(f"  Asking {daemon.config.commander}...")
                        result = ollama_generate(
                            daemon.config.model, question,
                            system=daemon.persona, timeout=120,
                        )
                        print(f"\n  [{port_id}:{daemon.config.commander}]")
                        print(f"  {result.get('response', 'No response')}\n")
                    else:
                        print(f"  Unknown port: {port_id}\n")
                else:
                    print("  Usage: ask P4 <question>\n")
            elif cmd == "help":
                print("  Commands: status | nataraja | ask P4 <question> | quit\n")
            else:
                print("  Unknown command. Try: status, nataraja, ask P4 <question>, quit\n")

    except KeyboardInterrupt:
        pass
    finally:
        print("\n  Stopping all daemons...")
        supervisor.stop_all()
        # Allow threads to finish
        time.sleep(2)
        supervisor.print_status()

        _write_stigmergy("hfo.gen89.daemon.swarm_stop", {
            "ports": port_ids,
            "total_turns": sum(d.turn_count for d in supervisor.daemons.values()),
        })
        print("  Swarm shutdown complete.\n")


if __name__ == "__main__":
    main()
