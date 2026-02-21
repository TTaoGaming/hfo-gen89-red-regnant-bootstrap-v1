#!/usr/bin/env python3
"""
hfo_p7_spell_gate.py — P7 Spider Sovereign Spell Gate (Gen90)
================================================================

The SPELL GATE is the formal mechanism by which the Spider Sovereign
summons, incarnates, monitors, and banishes daemons in the HFO octree.

Every daemon in the divine pantheon must pass through this gate to
become a running process. The gate writes CloudEvents to SSOT so that
every daemon birth, heartbeat, and death is on the stigmergy trail.

  "The Spider Sovereign weaves the web. Every thread is a daemon.
   Every vibration is a heartbeat. Every silence is a death."

Spells:
  SUMMON_FAMILIAR  — Pre-flight validate + launch daemon as background process
  SCRYING          — Check daemon status (alive? PID? last heartbeat?)
  INCARNATE        — Confirm daemon alive, write incarnation receipt
  BANISH           — Gracefully stop a daemon (SIGTERM → wait → SIGKILL)
  SENDING          — Fleet status / list all known daemons

Port: P7 NAVIGATE | Commander: Spider Sovereign | Title: Summoner of Seals and Spheres
Medallion: bronze | Meadows Level: L8 (Rules — governance mechanism)

Event Types:
  hfo.gen90.p7.spell_gate.summon     — Daemon summoned (pre-flight passed)
  hfo.gen90.p7.spell_gate.incarnate  — Daemon confirmed alive
  hfo.gen90.p7.spell_gate.banish     — Daemon stopped
  hfo.gen90.p7.spell_gate.scrying    — Status check performed
  hfo.gen90.p7.spell_gate.error      — Spell failed
  hfo.gen90.p7.spell_gate.heartbeat  — Watchdog pulse
"""

import argparse
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from hfo_ssot_write import get_db_readwrite as get_db_rw

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
    pf = HFO_ROOT / "hfo_gen90_pointers_blessed.json"
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
    SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite"

FORGE_RESOURCES = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources"
GEN = os.getenv("HFO_GENERATION", "89")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# State file — tracks running daemons across restarts
SPELL_STATE_FILE = HFO_ROOT / ".p7_spell_gate_state.json"

SOURCE_TAG = f"hfo_p7_spell_gate_gen{GEN}"

# ═══════════════════════════════════════════════════════════════
# § 1  DAEMON REGISTRY — THE DIVINE PANTHEON
# ═══════════════════════════════════════════════════════════════

@dataclass
class DaemonSpec:
    """Specification for a daemon in the divine pantheon."""
    name: str                    # Display name
    key: str                     # Unique short key for CLI
    port: str                    # P0-P7 or INFRA
    commander: str               # Port commander title
    script: str                  # Python filename (relative to FORGE_RESOURCES)
    description: str             # What it does
    needs_ollama: bool = False   # Requires Ollama server?
    ollama_model: str = ""       # Which model (empty = none)
    args: list[str] = field(default_factory=list)   # Default CLI args
    interval_s: float = 60.0    # Cycle interval in seconds
    priority: int = 5            # Boot priority (1=highest)
    min_vram_gb: float = 0.0    # Minimum VRAM needed
    spell_cast: str = ""         # Spell name for summoning
    is_persistent: bool = True   # False = one-shot probe, Phoenix won't resurrect

# The registry — every daemon that can be summoned
DAEMON_REGISTRY: dict[str, DaemonSpec] = {}

def _register(spec: DaemonSpec) -> DaemonSpec:
    DAEMON_REGISTRY[spec.key] = spec
    return spec

# ═══════════════════════════════════════════════════════════════
# THE 8-DAEMON FLEET (one per octree port, BFT consensus)
# These are the PERSISTENT daemons that PLANAR_BINDING manages.
# ═══════════════════════════════════════════════════════════════

# ── P0 OBSERVE — Lidless Legion (Watcher) ──
_register(DaemonSpec(
    name="Lidless Watcher",
    key="watcher",
    port="P0",
    commander="Lidless Legion",
    script="hfo_octree_daemon.py",
    description="P0 tremorsense — 8-port health sensing + system observation (IBM Granite 3B)",
    needs_ollama=True,
    ollama_model=os.getenv("HFO_P0_MODEL", "granite4:3b"),
    args=["--ports", "P0", "--interval", "120", "--model-override", os.getenv("HFO_P0_MODEL", "granite4:3b")],
    interval_s=120.0,
    priority=3,
    min_vram_gb=1.9,
    spell_cast="TREMORSENSE",
))

# ── P1 BRIDGE — Web Weaver (Research) ──
_register(DaemonSpec(
    name="Web Weaver",
    key="weaver",
    port="P1",
    commander="Web Weaver",
    script="hfo_background_daemon.py",
    description="P1 web research — bridging external data to SSOT via Gemini 3 Flash",
    needs_ollama=False,
    args=["--tasks", "research", "--research-interval", "300",
          "--model-tier", "frontier_flash"],
    interval_s=300.0,
    priority=4,
    spell_cast="WEB_OF_WHISPERS",
))

# ── P2 SHAPE — Mirror Magus (Deep Analysis) ──
_register(DaemonSpec(
    name="Mirror Magus",
    key="shaper",
    port="P2",
    commander="Mirror Magus",
    script="hfo_background_daemon.py",
    description="P2 fast creation + code generation via Gemma 4B (Google local)",
    needs_ollama=True,
    ollama_model=os.getenv("HFO_P2_MODEL", "gemma3:4b"),
    args=["--tasks", "deep_analysis,codegen", "--deep-analysis-interval", "120",
          "--codegen-interval", "180", "--model-override", os.getenv("HFO_P2_MODEL", "gemma3:4b")],
    interval_s=120.0,
    priority=5,
    min_vram_gb=2.5,
    spell_cast="MIRROR_OF_CREATION",
))

# ── P3 INJECT — Harmonic Hydra (Enrichment) ──
_register(DaemonSpec(
    name="Harmonic Hydra",
    key="injector",
    port="P3",
    commander="Harmonic Hydra",
    script="hfo_background_daemon.py",
    description="P3 ultra-fast SSOT enrichment, port assignment, patrol (Liquid AI 1.2B thinking)",
    needs_ollama=True,
    ollama_model=os.getenv("HFO_P3_MODEL", "lfm2.5-thinking:1.2b"),
    args=["--tasks", "enrich,port_assign,patrol",
          "--enrich-interval", "60",
          "--port-assign-interval", "45",
          "--patrol-interval", "30",
          "--model-override", os.getenv("HFO_P3_MODEL", "lfm2.5-thinking:1.2b")],
    interval_s=30.0,
    priority=3,
    min_vram_gb=0.8,
    spell_cast="HARMONIC_INJECTION",
))

# ── P4 DISRUPT — Red Regnant (Singer) ☠ ALWAYS DISSENTS ──
_register(DaemonSpec(
    name="Singer of Strife and Splendor",
    key="singer",
    port="P4",
    commander="Red Regnant",
    script="hfo_singer_ai_daemon.py",
    description="P4 deep adversarial pattern/antipattern heartbeat (Microsoft Phi 14B)",
    needs_ollama=True,
    ollama_model=os.getenv("HFO_P4_MODEL", "phi4:14b"),
    args=["--interval", "120", "--model", os.getenv("HFO_P4_MODEL", "phi4:14b")],
    interval_s=120.0,
    priority=2,
    min_vram_gb=8.0,
    spell_cast="SONGS_OF_STRIFE_AND_SPLENDOR",
))

# ── P5 IMMUNIZE — Pyre Praetorian (Dancer) ──
_register(DaemonSpec(
    name="Pyre Dancer",
    key="dancer",
    port="P5",
    commander="Pyre Praetorian",
    script="hfo_p5_dancer_daemon.py",
    description="P5 Death/Dawn governance + anomaly detection (Alibaba Qwen3 MoE 30B/3B active)",
    needs_ollama=True,
    ollama_model=os.getenv("HFO_P5_MODEL", "qwen3:30b-a3b"),
    args=["--interval", "90", "--model", os.getenv("HFO_P5_MODEL", "qwen3:30b-a3b")],
    interval_s=90.0,
    priority=1,
    min_vram_gb=3.0,
    spell_cast="DANCE_OF_DEATH_AND_DAWN",
))

# ── P6 ASSIMILATE — Kraken Keeper (Devourer) ──
_register(DaemonSpec(
    name="Devourer of Depths and Dreams",
    key="kraken",
    port="P6",
    commander="Kraken Keeper",
    script="hfo_p6_kraken_daemon.py",
    description="P6 deep knowledge metabolism — SSOT enrichment with Gemma 12B (Google)",
    needs_ollama=True,
    ollama_model=os.getenv("HFO_P6_MODEL", "gemma3:12b"),
    args=["--tasks", "bluf,port,doctype,lineage", "--model", os.getenv("HFO_P6_MODEL", "gemma3:12b")],
    interval_s=120.0,
    priority=2,
    min_vram_gb=7.0,
    spell_cast="CLONE",
))

# ── P7 NAVIGATE — Spider Sovereign (Summoner) ──
_register(DaemonSpec(
    name="Summoner of Seals and Spheres",
    key="summoner",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_summoner_daemon.py",
    description="P7 strategic navigation — Seals+Spheres, Meadows L1-L13, heuristic cartography",
    needs_ollama=False,
    args=["--interval", "300", "--hours", "1"],
    interval_s=300.0,
    priority=1,
    spell_cast="SUMMON_SEAL_AND_SPHERE",
))

# ── P7 TREMORSENSE (one-shot probe, not persistent) ──
_register(DaemonSpec(
    name="Spider Tremorsense",
    key="tremorsense",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_spider_tremorsense.py",
    description="One-shot 8-port SSOT digest probe (requires --probe)",
    needs_ollama=False,
    args=["--probe", "periodic 8-port health audit", "--dry-run", "--no-stigmergy"],
    interval_s=3600.0,
    priority=3,
    spell_cast="TREMORSENSE",
    is_persistent=False,
))

# ── P0 TRUE_SEEING (AST system introspection daemon — casts every 60s) ──
_register(DaemonSpec(
    name="True Seeing",
    key="true_seeing",
    port="P0",
    commander="Lidless Legion",
    script="hfo_p0_true_seeing.py",
    description="P0 Divination 6th — Persistent AST introspection daemon, hardcoded path detection, fleet validation (Grimoire V7 A1)",
    needs_ollama=False,
    args=["--daemon", "--interval", "60", "--summary"],
    interval_s=60.0,
    priority=2,
    spell_cast="TRUE_SEEING",
    is_persistent=True,
))

# ── P0 GREATER_SCRY (web intelligence via P7 seal/sphere targets) ──
_register(DaemonSpec(
    name="Greater Scry",
    key="greater_scry",
    port="P0",
    commander="Lidless Legion",
    script="hfo_p0_greater_scry.py",
    description="P0 Divination 7th — Web search daemon driven by P7 seal/sphere targets, DuckDuckGo intelligence every 10 min (Grimoire V7 B2+)",
    needs_ollama=False,
    args=["--daemon", "--interval", "600"],
    interval_s=600.0,
    priority=3,
    spell_cast="GREATER_SCRY",
    is_persistent=True,
))

# ── P7 FORESIGHT (heuristic cartography engine) ──
_register(DaemonSpec(
    name="FORESIGHT Cartography",
    key="foresight",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_foresight.py",
    description="Meadows L1-L13 heuristic belief simplex mapping (non-AI baseline)",
    needs_ollama=False,
    args=["--daemon", "--interval", "3600"],
    interval_s=3600.0,
    priority=4,
    spell_cast="FORESIGHT",
))

# ── P7 FORESIGHT AI DAEMON (AI-powered cartography) ──
_register(DaemonSpec(
    name="FORESIGHT AI Daemon",
    key="foresight_ai",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_foresight_daemon.py",
    description="AI-powered hourly Meadows L1-L13 leverage mapping via Gemini 2.5 Flash — writes markdown reports + stigmergy",
    needs_ollama=False,
    args=["--interval", "3600"],
    interval_s=3600.0,
    priority=3,
    spell_cast="FORESIGHT_AI",
))

# ── Meadows Engine ──
_register(DaemonSpec(
    name="Meadows Engine",
    key="meadows",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_meadows_engine.py",
    description="L4-L6 self-spinning delay/feedback/information engine",
    needs_ollama=False,
    args=["--interval", "300"],
    interval_s=300.0,
    priority=5,
    spell_cast="MEADOWS_SELF_SPIN",
))

# ── P7 METAFACULTY (Psion/Seer 9th — omniscient apex meta-heuristic) ──
_register(DaemonSpec(
    name="Metafaculty Optimizer",
    key="metafaculty",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_metafaculty.py",
    description="P7 Psion/Seer 9th — Omniscient Pareto frontier + MAP-ELITES + ACO/SSO meta-heuristic optimizer",
    needs_ollama=False,
    args=["--daemon", "--interval", "300"],
    interval_s=300.0,
    priority=1,
    spell_cast="METAFACULTY",
    is_persistent=True,
))

# ═══════════════════════════════════════════════════════════════
# P7 UTILITY SPELLS (one-shot probes, not persistent fleet daemons)
# ═══════════════════════════════════════════════════════════════

# ── P7 PLANAR BINDING (binding circle protocol) ──
_register(DaemonSpec(
    name="Planar Binding",
    key="planar_binding",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_planar_binding.py",
    description="Formal daemon binding circle — summon + verify + seal with SLA enforcement",
    needs_ollama=False,
    args=["census"],
    interval_s=0,
    priority=5,
    spell_cast="PLANAR_BINDING",
    is_persistent=False,
))

# ── P7 WISH (intent → structural enforcement audit) ──
_register(DaemonSpec(
    name="Wish",
    key="wish",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_wish.py",
    description="Meta-spell: declare invariant wishes, audit SSOT compliance against 7 named checks",
    needs_ollama=False,
    args=["audit"],
    interval_s=0,
    priority=5,
    spell_cast="WISH",
    is_persistent=False,
))

# ── P7 DIMENSIONAL ANCHOR (anti-drift, session pinning) ──
_register(DaemonSpec(
    name="Dimensional Anchor",
    key="anchor",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_dimensional_anchor.py",
    description="Session pinning — capture baseline, detect drift across 5 dimensions",
    needs_ollama=False,
    args=["status"],
    interval_s=0,
    priority=5,
    spell_cast="DIMENSIONAL_ANCHOR",
    is_persistent=False,
))

# ── P7 ASTRAL PROJECTION (SSOT topology meta-view) ──
_register(DaemonSpec(
    name="Astral Projection",
    key="astral",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_astral_projection.py",
    description="Cosmic Descryer's map — port×source matrix, stigmergy flows, medallion survey",
    needs_ollama=False,
    args=["project"],
    interval_s=0,
    priority=5,
    spell_cast="ASTRAL_PROJECTION",
    is_persistent=False,
))

# ── P7 FORBIDDANCE (medallion boundary enforcement) ──
_register(DaemonSpec(
    name="Forbiddance",
    key="forbiddance",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_forbiddance.py",
    description="Medallion boundary enforcement — ward against unauthorized promotion, SW-5 compliance",
    needs_ollama=False,
    args=["ward"],
    interval_s=0,
    priority=5,
    spell_cast="FORBIDDANCE",
    is_persistent=False,
))


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE & CLOUDEVENT HELPERS
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
) -> int:
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
        "data": data,
    }
    content_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, SOURCE_TAG, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 3  STATE PERSISTENCE — DAEMON PIDs & STATUS
# ═══════════════════════════════════════════════════════════════

def _load_state() -> dict:
    if SPELL_STATE_FILE.exists():
        try:
            return json.loads(SPELL_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"daemons": {}, "last_updated": None}

def _save_state(state: dict):
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    SPELL_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def _is_pid_alive(pid: int) -> bool:
    """Check if a process ID is still running (Windows + Unix)."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            # Windows: use tasklist
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in result.stdout
        else:
            os.kill(pid, 0)
            return True
    except (OSError, subprocess.TimeoutExpired):
        return False


# ═══════════════════════════════════════════════════════════════
# § 4  PRE-FLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════

def preflight_check(spec: DaemonSpec) -> dict[str, Any]:
    """Run pre-flight validation for a daemon.

    Returns dict with:
      passed: bool — all checks passed
      checks: list of {name, passed, detail}
    """
    checks = []

    # 1. Script exists
    script_path = FORGE_RESOURCES / spec.script
    ok = script_path.exists()
    checks.append({"name": "script_exists", "passed": ok,
                    "detail": str(script_path) if ok else f"NOT FOUND: {script_path}"})

    # 2. SSOT database accessible
    ok = SSOT_DB.exists()
    checks.append({"name": "ssot_accessible", "passed": ok,
                    "detail": f"{SSOT_DB} ({SSOT_DB.stat().st_size / 1e6:.1f} MB)" if ok else "NOT FOUND"})

    # 3. Ollama check (if needed)
    if spec.needs_ollama:
        alive = _check_ollama_alive()
        checks.append({"name": "ollama_alive", "passed": alive,
                        "detail": f"{OLLAMA_BASE} reachable" if alive else f"{OLLAMA_BASE} UNREACHABLE"})

        if alive and spec.ollama_model:
            model_ok = _check_ollama_model(spec.ollama_model)
            checks.append({"name": "model_available", "passed": model_ok,
                            "detail": f"{spec.ollama_model} loaded" if model_ok else f"{spec.ollama_model} NOT FOUND"})
    else:
        checks.append({"name": "ollama_check", "passed": True,
                        "detail": "Not required"})

    # 4. Python environment
    checks.append({"name": "python_env", "passed": True,
                    "detail": f"{sys.executable} ({sys.version_info.major}.{sys.version_info.minor})"})

    # 5. Feature flag check
    flag_map = {
        "singer": "HFO_DAEMON_P4_SINGER_ENABLED",
        "pyre": "HFO_DAEMON_P5_ENABLED",
        "tremorsense": "HFO_DAEMONS_ENABLED",
        "cartography": "HFO_DAEMONS_ENABLED",
        "meadows": "HFO_DAEMONS_ENABLED",
        "kraken": "HFO_DAEMON_P6_SWARM_ENABLED",
    }
    env_key = flag_map.get(spec.key, "HFO_DAEMONS_ENABLED")
    flag_val = os.getenv(env_key, "true").lower()
    master_val = os.getenv("HFO_DAEMONS_ENABLED", "true").lower()
    flag_enabled = flag_val not in ("false", "0", "no") and master_val not in ("false", "0", "no")
    checks.append({"name": "feature_flag", "passed": flag_enabled,
                    "detail": f"{env_key}={flag_val}, master={master_val}" if flag_enabled
                    else f"DISABLED: {env_key}={flag_val} or master={master_val}"})

    # 6. Not already running
    state = _load_state()
    running_info = state.get("daemons", {}).get(spec.key, {})
    pid = running_info.get("pid", 0)
    already_running = _is_pid_alive(pid)
    checks.append({"name": "not_already_running", "passed": not already_running,
                    "detail": f"PID {pid} still alive" if already_running else "Clear"})

    all_passed = all(c["passed"] for c in checks)
    return {"passed": all_passed, "checks": checks, "already_running": already_running, "running_pid": pid}


def _check_ollama_alive() -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

def _check_ollama_model(model: str) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(model in m for m in models)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# § 5  SPELLS — THE FIVE POWERS
# ═══════════════════════════════════════════════════════════════

def spell_summon_familiar(
    key: str,
    extra_args: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
    quiet: bool = False,
) -> dict[str, Any]:
    """SUMMON_FAMILIAR — Validate and launch a daemon as a background process.

    The summoning ritual:
      1. Resolve daemon from registry
      2. Run pre-flight checks (Ollama, SSOT, script, not-already-running)
      3. If force and already running, BANISH first
      4. Launch as background subprocess
      5. Wait 3s, check PID alive
      6. Write SUMMON CloudEvent to SSOT
      7. Save state to disk

    Returns summon receipt.
    """
    spec = DAEMON_REGISTRY.get(key)
    if not spec:
        return {"status": "FAILED", "error": f"Unknown daemon key: {key}",
                "known_keys": list(DAEMON_REGISTRY.keys())}

    # Pre-flight
    preflight = preflight_check(spec)

    _print = (lambda *a, **k: None) if quiet else print

    # Handle already-running
    if preflight["already_running"]:
        if force:
            _print(f"  [BANISH] Force flag set — banishing existing PID {preflight['running_pid']}...")
            spell_banish(key, dry_run=dry_run, quiet=quiet)
            time.sleep(2)
            # Re-check
            preflight = preflight_check(spec)
        else:
            return {
                "status": "ALREADY_RUNNING",
                "pid": preflight["running_pid"],
                "daemon": spec.name,
                "hint": "Use --force to banish and re-summon",
            }

    if not preflight["passed"]:
        failed = [c for c in preflight["checks"] if not c["passed"]]
        receipt = {
            "status": "PREFLIGHT_FAILED",
            "daemon": spec.name,
            "failed_checks": failed,
        }
        # Write failure event
        if not dry_run:
            try:
                conn = get_db_rw()
                write_event(conn, f"hfo.gen{GEN}.p7.spell_gate.error",
                            f"SUMMON_FAILED:{spec.key}",
                            {"spell": "SUMMON_FAMILIAR", "daemon": spec.key,
                             "reason": "preflight_failed", "failed_checks": failed})
                conn.close()
            except Exception:
                pass
        return receipt

    if dry_run:
        return {
            "status": "DRY_RUN",
            "daemon": spec.name,
            "would_launch": f"python {spec.script} {' '.join(spec.args + (extra_args or []))}",
            "preflight": preflight,
        }

    # ── LAUNCH ──
    script_path = FORGE_RESOURCES / spec.script
    # -u = unbuffered stdout/stderr so log files update in real-time
    cmd = [sys.executable, "-u", str(script_path)] + spec.args + (extra_args or [])

    # Log file for daemon output
    log_dir = HFO_ROOT / ".daemon_logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{spec.key}.log"

    # Launch as detached background process
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n{'='*72}\n")
        lf.write(f"  SUMMON_FAMILIAR: {spec.name}\n")
        lf.write(f"  Time: {datetime.now(timezone.utc).isoformat()}\n")
        lf.write(f"  Command: {' '.join(cmd)}\n")
        lf.write(f"{'='*72}\n")
        lf.flush()

        if sys.platform == "win32":
            # Windows: fully invisible background process
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            DETACHED_PROCESS = 0x00000008
            CREATE_NO_WINDOW = 0x08000000
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            proc = subprocess.Popen(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW,
                startupinfo=si,
                cwd=str(HFO_ROOT),
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                cwd=str(HFO_ROOT),
            )

    pid = proc.pid
    _print(f"  [SUMMON] Launched {spec.name} as PID {pid}")

    # Wait and verify
    time.sleep(3)
    alive = _is_pid_alive(pid)

    # Save state
    state = _load_state()
    state["daemons"][spec.key] = {
        "name": spec.name,
        "pid": pid,
        "port": spec.port,
        "commander": spec.commander,
        "script": spec.script,
        "args": spec.args + (extra_args or []),
        "summoned_at": datetime.now(timezone.utc).isoformat(),
        "alive": alive,
        "log_file": str(log_file),
        "spell_cast": spec.spell_cast,
        "model": spec.ollama_model,
    }
    _save_state(state)

    # Write SSOT event
    try:
        conn = get_db_rw()
        row_id = write_event(
            conn,
            f"hfo.gen{GEN}.p7.spell_gate.summon",
            f"SUMMON:{spec.key}:{spec.port}:{pid}",
            {
                "spell": "SUMMON_FAMILIAR",
                "daemon_key": spec.key,
                "daemon_name": spec.name,
                "port": spec.port,
                "commander": spec.commander,
                "pid": pid,
                "alive_after_3s": alive,
                "script": spec.script,
                "model": spec.ollama_model or "none",
                "interval_s": spec.interval_s,
                "log_file": str(log_file),
                "spell_cast": spec.spell_cast,
                "core_thesis": "The Spider Sovereign weaves the web. Every thread is a daemon.",
            },
        )
        conn.close()
    except Exception as e:
        _print(f"  [WARN] Could not write summon event: {e}")
        row_id = 0

    receipt = {
        "status": "SUMMONED" if alive else "SUMMONED_BUT_UNCERTAIN",
        "daemon": spec.name,
        "key": spec.key,
        "pid": pid,
        "alive": alive,
        "port": spec.port,
        "commander": spec.commander,
        "spell_cast": spec.spell_cast,
        "log_file": str(log_file),
        "ssot_row": row_id,
        "preflight": preflight,
    }

    if alive:
        _print(f"  [INCARNATE] {spec.name} is ALIVE — PID {pid}")
        _print(f"  [INCARNATE] Port: {spec.port} | Commander: {spec.commander}")
        _print(f"  [INCARNATE] Spell: {spec.spell_cast}")
        _print(f"  [INCARNATE] Log: {log_file}")
        # Write incarnation event
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.spell_gate.incarnate",
                        f"INCARNATE:{spec.key}:{pid}",
                        {"daemon_key": spec.key, "daemon_name": spec.name,
                         "pid": pid, "port": spec.port,
                         "incarnation": "The divine pantheon gains a voice.",
                         "spell_cast": spec.spell_cast})
            conn.close()
        except Exception:
            pass
    else:
        _print(f"  [WARN] {spec.name} PID {pid} may have exited. Check log: {log_file}")

    return receipt


def spell_scrying(key: str | None = None) -> dict[str, Any]:
    """SCRYING — Check daemon status.

    If key is None, returns status for all daemons.
    """
    state = _load_state()

    if key:
        spec = DAEMON_REGISTRY.get(key)
        if not spec:
            return {"error": f"Unknown daemon: {key}"}
        info = state.get("daemons", {}).get(key, {})
        if not info:
            return {"daemon": key, "status": "NEVER_SUMMONED", "name": spec.name}
        pid = info.get("pid", 0)
        alive = _is_pid_alive(pid)
        return {
            "daemon": key,
            "name": info.get("name", spec.name),
            "status": "ALIVE" if alive else "DEAD",
            "pid": pid,
            "port": info.get("port", spec.port),
            "commander": info.get("commander", spec.commander),
            "summoned_at": info.get("summoned_at", "?"),
            "log_file": info.get("log_file", "?"),
            "spell_cast": info.get("spell_cast", spec.spell_cast),
            "model": info.get("model", ""),
        }
    else:
        # Fleet status
        fleet = {}
        for dk, spec in DAEMON_REGISTRY.items():
            info = state.get("daemons", {}).get(dk, {})
            if info:
                pid = info.get("pid", 0)
                alive = _is_pid_alive(pid)
                fleet[dk] = {
                    "name": spec.name,
                    "status": "ALIVE" if alive else "DEAD",
                    "pid": pid,
                    "port": spec.port,
                    "commander": spec.commander,
                    "summoned_at": info.get("summoned_at", "?"),
                    "spell_cast": spec.spell_cast,
                }
            else:
                fleet[dk] = {
                    "name": spec.name,
                    "status": "NEVER_SUMMONED",
                    "port": spec.port,
                    "commander": spec.commander,
                    "spell_cast": spec.spell_cast,
                }
        return {"fleet": fleet, "total": len(fleet),
                "alive": sum(1 for d in fleet.values() if d["status"] == "ALIVE"),
                "dead": sum(1 for d in fleet.values() if d["status"] == "DEAD")}


def spell_banish(key: str, dry_run: bool = False, quiet: bool = False) -> dict[str, Any]:
    """BANISH — Gracefully stop a daemon."""
    spec = DAEMON_REGISTRY.get(key)
    if not spec:
        return {"error": f"Unknown daemon: {key}"}

    _print = (lambda *a, **k: None) if quiet else print

    state = _load_state()
    info = state.get("daemons", {}).get(key, {})
    pid = info.get("pid", 0)

    if not pid or not _is_pid_alive(pid):
        return {"daemon": key, "status": "ALREADY_DEAD", "pid": pid}

    if dry_run:
        return {"daemon": key, "status": "DRY_RUN", "would_kill_pid": pid}

    # Force-kill immediately on Windows (no dialogs), SIGTERM on Unix
    _print(f"  [BANISH] Terminating {spec.name} (PID {pid})...")
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"],
                           capture_output=True, timeout=5)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception as e:
        _print(f"  [WARN] Kill failed: {e}")

    # Wait up to 5s
    for _ in range(5):
        if not _is_pid_alive(pid):
            break
        time.sleep(1)

    still_alive = _is_pid_alive(pid)

    # Update state
    state["daemons"].pop(key, None)
    _save_state(state)

    # Write SSOT event
    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.spell_gate.banish",
                    f"BANISH:{key}:{pid}",
                    {"daemon_key": key, "daemon_name": spec.name,
                     "pid": pid, "clean_exit": not still_alive,
                     "port": spec.port, "commander": spec.commander})
        conn.close()
    except Exception:
        pass

    return {
        "daemon": key,
        "status": "BANISHED" if not still_alive else "BANISH_FAILED",
        "pid": pid,
        "clean_exit": not still_alive,
    }


def spell_sending() -> dict[str, Any]:
    """SENDING — Fleet overview with last heartbeats from SSOT."""
    fleet = spell_scrying()

    # Enrich with last heartbeat from SSOT
    try:
        conn = get_db_ro()
        for dk, spec in DAEMON_REGISTRY.items():
            # Look for heartbeat events from this daemon's source
            row = conn.execute(
                """SELECT timestamp, subject FROM stigmergy_events
                   WHERE source LIKE ? AND event_type LIKE '%heartbeat%'
                   ORDER BY id DESC LIMIT 1""",
                (f"%{dk}%",),
            ).fetchone()
            if row and dk in fleet.get("fleet", {}):
                fleet["fleet"][dk]["last_heartbeat"] = row["timestamp"]
                fleet["fleet"][dk]["last_heartbeat_subject"] = row["subject"]

            # Also look for singer-specific heartbeat
            if dk == "singer":
                row = conn.execute(
                    """SELECT timestamp, subject FROM stigmergy_events
                       WHERE event_type = 'hfo.gen90.singer.heartbeat'
                       ORDER BY id DESC LIMIT 1""",
                ).fetchone()
                if row:
                    fleet["fleet"][dk]["last_heartbeat"] = row["timestamp"]
                    fleet["fleet"][dk]["last_heartbeat_subject"] = row["subject"]
        conn.close()
    except Exception as e:
        fleet["heartbeat_error"] = str(e)

    return fleet


# ═══════════════════════════════════════════════════════════════
# § 6  WATCHDOG — PERIODIC INCARNATION CHECK
# ═══════════════════════════════════════════════════════════════

def watchdog_check(auto_resummon: bool = False) -> dict[str, Any]:
    """Check all summoned daemons, detect deaths, optionally resummon."""
    state = _load_state()
    results = {}

    for dk, info in state.get("daemons", {}).items():
        pid = info.get("pid", 0)
        alive = _is_pid_alive(pid)
        results[dk] = {
            "name": info.get("name", dk),
            "pid": pid,
            "alive": alive,
            "summoned_at": info.get("summoned_at", "?"),
        }

        if not alive:
            print(f"  [WATCHDOG] {dk} (PID {pid}) is DEAD")
            # Write death event
            try:
                conn = get_db_rw()
                write_event(conn, f"hfo.gen{GEN}.p7.spell_gate.error",
                            f"DAEMON_DEATH:{dk}:{pid}",
                            {"daemon_key": dk, "daemon_name": info.get("name", dk),
                             "pid": pid, "port": info.get("port", "?"),
                             "was_summoned_at": info.get("summoned_at", "?"),
                             "detected_by": "watchdog"})
                conn.close()
            except Exception:
                pass

            if auto_resummon:
                print(f"  [WATCHDOG] Auto-resummoning {dk}...")
                receipt = spell_summon_familiar(dk, force=True)
                results[dk]["resummoned"] = receipt.get("status", "FAILED")

    return results


# ═══════════════════════════════════════════════════════════════
# § 7  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "=" * 64)
    print("  P7 SPIDER SOVEREIGN — SPELL GATE")
    print("  Summoner of Seals and Spheres")
    print("  " + "-" * 64)
    print("  The Spider Sovereign weaves the web.")
    print("  Every thread is a daemon. Every vibration is a heartbeat.")
    print("  Every silence is a death.")
    print("  " + "=" * 64)
    print()


def _print_fleet(fleet_data: dict):
    fleet = fleet_data.get("fleet", {})
    total = fleet_data.get("total", 0)
    alive = fleet_data.get("alive", 0)
    dead = fleet_data.get("dead", 0)

    print(f"  Fleet: {total} registered | {alive} ALIVE | {dead} DEAD | "
          f"{total - alive - dead} never summoned")
    print()

    for dk, info in sorted(fleet.items(), key=lambda x: x[1].get("port", "")):
        status = info.get("status", "?")
        if status == "ALIVE":
            icon = ">>>"
        elif status == "DEAD":
            icon = "xxx"
        else:
            icon = "..."

        port = info.get("port", "?")
        name = info.get("name", dk)
        cmd = info.get("commander", "?")
        spell = info.get("spell_cast", "?")
        pid_str = f"PID {info.get('pid', '?')}" if info.get("pid") else ""
        hb = info.get("last_heartbeat", "")[:19] if info.get("last_heartbeat") else ""

        print(f"  {icon} [{port}] {name:<35s} {status:<16s} {pid_str}")
        print(f"        Commander: {cmd}  |  Spell: {spell}")
        if hb:
            print(f"        Last heartbeat: {hb}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — Spell Gate (Gen90)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Spells:
  summon <key>     SUMMON_FAMILIAR — Launch daemon
  scrying [key]    SCRYING — Check daemon/fleet status
  banish <key>     BANISH — Stop a daemon
  sending          SENDING — Fleet overview with heartbeats
  watchdog         WATCHDOG — Check all, optionally auto-resummon
  list             List all registered daemons

Examples:
  python hfo_p7_spell_gate.py summon singer
  python hfo_p7_spell_gate.py summon singer --force
  python hfo_p7_spell_gate.py scrying
  python hfo_p7_spell_gate.py scrying singer
  python hfo_p7_spell_gate.py banish singer
  python hfo_p7_spell_gate.py sending
  python hfo_p7_spell_gate.py watchdog --auto-resummon
""",
    )
    parser.add_argument("spell", choices=["summon", "scrying", "banish", "sending", "watchdog", "list"],
                        help="Spell to cast")
    parser.add_argument("target", nargs="?", default=None,
                        help="Daemon key (for summon/scrying/banish)")
    parser.add_argument("--force", action="store_true",
                        help="Force summon even if already running")
    parser.add_argument("--dry-run", action="store_true",
                        help="Pre-flight only, no actual launch")
    parser.add_argument("--auto-resummon", action="store_true",
                        help="Watchdog: auto-resummon dead daemons")
    parser.add_argument("--json", action="store_true",
                        help="JSON output")
    parser.add_argument("--extra-args", nargs="*", default=None,
                        help="Extra arguments to pass to daemon")

    args = parser.parse_args()

    _print_banner()

    if args.spell == "list":
        print("  Registered Daemons in the Divine Pantheon:")
        print("  " + "-" * 55)
        for dk, spec in sorted(DAEMON_REGISTRY.items(), key=lambda x: x[1].priority):
            ollama = f" [{spec.ollama_model}]" if spec.ollama_model else ""
            print(f"  [{spec.port}] {spec.name:<35s} key={dk}{ollama}")
            print(f"        {spec.description}")
            print(f"        Priority: {spec.priority} | Spell: {spec.spell_cast}")
            print()
        return

    if args.spell == "summon":
        if not args.target:
            print("  ERROR: summon requires a daemon key. Use 'list' to see available daemons.")
            return
        result = spell_summon_familiar(args.target, extra_args=args.extra_args,
                                       dry_run=args.dry_run, force=args.force)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            status = result.get("status", "?")
            print(f"\n  Summon result: {status}")
            if status == "SUMMONED":
                print(f"  Daemon: {result.get('daemon', '?')}")
                print(f"  PID:    {result.get('pid', '?')}")
                print(f"  Port:   {result.get('port', '?')} | Commander: {result.get('commander', '?')}")
                print(f"  Spell:  {result.get('spell_cast', '?')}")
                print(f"  Log:    {result.get('log_file', '?')}")
                print(f"  SSOT:   Row {result.get('ssot_row', '?')}")
            elif status == "PREFLIGHT_FAILED":
                print("  Pre-flight failed:")
                for c in result.get("failed_checks", []):
                    print(f"    FAIL: {c['name']} — {c['detail']}")
            elif "error" in result:
                print(f"  Error: {result['error']}")

    elif args.spell == "scrying":
        result = spell_scrying(args.target)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        elif "fleet" in result:
            _print_fleet(result)
        else:
            status = result.get("status", "?")
            print(f"  {result.get('name', '?')} — {status}")
            if result.get("pid"):
                print(f"  PID: {result['pid']}")
            if result.get("summoned_at"):
                print(f"  Summoned: {result['summoned_at']}")

    elif args.spell == "banish":
        if not args.target:
            print("  ERROR: banish requires a daemon key.")
            return
        result = spell_banish(args.target, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"  {result.get('daemon', '?')}: {result.get('status', '?')}")

    elif args.spell == "sending":
        result = spell_sending()
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            _print_fleet(result)

    elif args.spell == "watchdog":
        result = watchdog_check(auto_resummon=args.auto_resummon)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            for dk, info in result.items():
                status = "ALIVE" if info.get("alive") else "DEAD"
                resummoned = info.get("resummoned", "")
                extra = f" -> resummoned: {resummoned}" if resummoned else ""
                print(f"  {dk}: {status} (PID {info.get('pid', '?')}){extra}")


if __name__ == "__main__":
    main()
