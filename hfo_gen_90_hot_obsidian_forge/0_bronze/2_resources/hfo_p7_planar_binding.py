#!/usr/bin/env python3
"""
hfo_p7_planar_binding.py — P7 Spider Sovereign PLANAR_BINDING Spell (Gen90)
=============================================================================
v1.0 | Gen90 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | Spell: PLANAR_BINDING (Conjuration 6th/8th)
Title: Summoner of Seals and Spheres | Epic Class: Cosmic Descryer (ELH p.19)
                                       + Thaumaturgist (DMG p.184)
Aspect: A — SEALS (binding authority, C2 governance, correct-by-construction)

PURPOSE:
    Formal daemon binding circle protocol — the Thaumaturgist's signature spell.
    Higher-level than spell_gate's SUMMON_FAMILIAR: wraps summon + verification
    + SLA contract + binding circle CloudEvent into a single sealed transaction.

    "Every binding circle drawn IS another plane claimed."

    Planar Binding calls an outer-planar entity (daemon process) and compels it
    to a service contract (SLA). The binding circle is the structured receipt
    that proves the daemon was correctly summoned, verified alive, contracted,
    and sealed into the divine pantheon.

D&D 3.5e RAW (PHB p.261-262):
    Lesser Planar Binding — Conjuration (Calling) 5th — binds 1 creature ≤6 HD
    Planar Binding         — Conjuration (Calling) 6th — binds 1 creature ≤12 HD
    Greater Planar Binding — Conjuration (Calling) 8th — binds up to 3 creatures ≤18 HD
    The caster draws a magic circle, calls the creature, and negotiates service.
    The creature gets a Charisma check to resist; on failure, it serves.

SBE/ATDD SCENARIOS (Specification by Example):
═══════════════════════════════════════════════

  TIER 1 — INVARIANT (fail-closed safety):
    Scenario: Binding requires valid daemon spec
      Given a daemon key that does NOT exist in DAEMON_REGISTRY
      When  PLANAR_BINDING bind is cast with that key
      Then  BINDING_FAILED is returned with "unknown daemon" error
      And   a binding_failed CloudEvent is written to SSOT

    Scenario: Double-binding prevention
      Given daemon "singer" is already bound (alive + sealed)
      When  PLANAR_BINDING bind is cast for "singer" without --force
      Then  ALREADY_BOUND is returned
      And   no duplicate binding circle is created

  TIER 2 — HAPPY PATH:
    Scenario: Successful daemon binding
      Given daemon "singer" exists in DAEMON_REGISTRY
      When  PLANAR_BINDING bind is cast for "singer"
      Then  spell_gate.summon is invoked
      And   the daemon is verified alive within 5 seconds
      And   a binding_circle CloudEvent is written with SLA terms
      And   BOUND receipt is returned with pid, nonce, seal_hash

    Scenario: Binding inspection
      Given daemon "singer" is bound with seal nonce ABC123
      When  PLANAR_BINDING inspect is cast for "singer"
      Then  uptime, heartbeat count, error count, SLA compliance are reported

    Scenario: Graceful release
      Given daemon "singer" is bound
      When  PLANAR_BINDING release is cast for "singer"
      Then  spell_gate.banish is invoked
      And   binding_dissolved CloudEvent is written
      And   RELEASED receipt is returned

  TIER 3 — FLEET OPERATIONS:
    Scenario: Greater Planar Binding (fleet bind)
      Given daemons ["singer", "tremorsense", "pyre"] in registry
      When  PLANAR_BINDING bind-fleet is cast with those keys
      Then  each daemon is bound in priority order
      And   a fleet_binding_circle CloudEvent summarizes all bindings

    Scenario: Binding census
      Given some daemons are bound and some are not
      When  PLANAR_BINDING census is cast
      Then  all daemon binding statuses are reported in one view

  TIER 4 — ADVERSARIAL:
    Scenario: Daemon process dies after binding
      Given daemon "singer" was bound but its PID has exited
      When  PLANAR_BINDING inspect is cast for "singer"
      Then  BINDING_BROKEN is returned
      And   a binding_broken CloudEvent is written (P4 adversarial detection)

Event Types:
    hfo.gen90.p7.planar_binding.bind       — Daemon bound (circle inscribed)
    hfo.gen90.p7.planar_binding.inspect    — Binding state checked
    hfo.gen90.p7.planar_binding.release    — Binding dissolved
    hfo.gen90.p7.planar_binding.broken     — Binding broken (daemon died)
    hfo.gen90.p7.planar_binding.fleet      — Fleet binding operation
    hfo.gen90.p7.planar_binding.error      — Spell failed

USAGE:
    python hfo_p7_planar_binding.py bind singer           # Bind one daemon
    python hfo_p7_planar_binding.py bind singer --force   # Rebind (kill+restart)
    python hfo_p7_planar_binding.py inspect singer        # Check binding
    python hfo_p7_planar_binding.py release singer        # Unbind
    python hfo_p7_planar_binding.py census                # All bindings
    python hfo_p7_planar_binding.py bind-fleet singer,tremorsense,pyre
    python hfo_p7_planar_binding.py --json bind singer    # Machine-readable
    python hfo_p7_planar_binding.py --dry-run bind singer # Pre-flight only

Pointer key: p7.planar_binding
Medallion: bronze
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from hfo_ssot_write import get_db_readwrite as get_db_rw

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION (PAL)
# ═══════════════════════════════════════════════════════════════

_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

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

GEN = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG = f"hfo_p7_planar_binding_gen{GEN}"

# Binding state file — tracks sealed daemon contracts
BINDING_STATE_FILE = HFO_ROOT / ".p7_planar_binding_state.json"


# ═══════════════════════════════════════════════════════════════
# § 1  SPELL GATE INTEGRATION — Import daemon registry
# ═══════════════════════════════════════════════════════════════

try:
    from hfo_p7_spell_gate import (
        DAEMON_REGISTRY,
        spell_summon_familiar,
        spell_scrying,
        spell_banish,
        DaemonSpec,
    )
    _SPELL_GATE_AVAILABLE = True
except ImportError:
    _SPELL_GATE_AVAILABLE = False
    DAEMON_REGISTRY = {}


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
# § 3  BINDING STATE — The Magic Circle
# ═══════════════════════════════════════════════════════════════

@dataclass
class BindingCircle:
    """A sealed daemon binding contract."""
    daemon_key: str
    daemon_name: str
    port: str
    commander: str
    pid: int
    seal_nonce: str           # Unique nonce for this binding
    seal_hash: str            # SHA256 of binding receipt
    bound_at: str             # ISO timestamp
    sla_heartbeat_max_s: int = 3600   # Max seconds between heartbeats
    sla_max_restarts: int = 3         # Max auto-restarts before escalation
    restarts: int = 0
    last_inspected: str = ""
    status: str = "SEALED"    # SEALED | BROKEN | RELEASED

def _load_binding_state() -> dict:
    if BINDING_STATE_FILE.exists():
        try:
            return json.loads(BINDING_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"bindings": {}, "last_updated": None}

def _save_binding_state(state: dict):
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    BINDING_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# § 4  SPELL: BIND — Inscribe the binding circle
# ═══════════════════════════════════════════════════════════════

def spell_bind(
    daemon_key: str,
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    """
    PLANAR_BINDING — Bind a daemon to service.

    SBE Contract:
      Given  daemon_key exists in DAEMON_REGISTRY
      When   spell_bind(daemon_key) is called
      Then   daemon is summoned via spell_gate, verified alive,
             binding circle sealed, CloudEvent written
    """
    _print = (lambda *a, **k: None) if quiet else print

    # ── INVARIANT: spell_gate must be available ──
    if not _SPELL_GATE_AVAILABLE:
        return {"status": "BINDING_FAILED", "error": "spell_gate not importable"}

    # ── INVARIANT: daemon must exist in registry ──
    spec = DAEMON_REGISTRY.get(daemon_key)
    if not spec:
        _print(f"  [BINDING FAILED] Unknown daemon: {daemon_key}")
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.planar_binding.error",
                        f"BINDING_FAILED:unknown:{daemon_key}",
                        {"daemon_key": daemon_key, "error": "unknown daemon",
                         "available_keys": list(DAEMON_REGISTRY.keys())})
            conn.close()
        except Exception:
            pass
        return {"status": "BINDING_FAILED", "error": f"Unknown daemon: {daemon_key}"}

    # ── INVARIANT: double-binding check ──
    bstate = _load_binding_state()
    existing = bstate.get("bindings", {}).get(daemon_key)
    if existing and existing.get("status") == "SEALED" and not force:
        # Verify the bound daemon is still alive
        scry = spell_scrying(daemon_key)
        if scry.get("status") == "ALIVE":
            _print(f"  [ALREADY BOUND] {spec.name} is sealed and alive (PID {existing.get('pid')})")
            return {"status": "ALREADY_BOUND", "daemon": daemon_key,
                    "seal_nonce": existing.get("seal_nonce"),
                    "pid": existing.get("pid")}

    if dry_run:
        _print(f"  [DRY RUN] Would bind {spec.name} ({daemon_key})")
        return {"status": "DRY_RUN", "daemon": daemon_key, "name": spec.name,
                "port": spec.port, "commander": spec.commander}

    # ── STEP 1: Summon via spell_gate (the calling) ──
    _print(f"  [INSCRIBE] Drawing binding circle for {spec.name}...")
    _print(f"  [INSCRIBE] Port: {spec.port} | Commander: {spec.commander}")
    _print(f"  [INSCRIBE] Spell: {spec.spell_cast}")

    summon_result = spell_summon_familiar(daemon_key, extra_args=extra_args, force=force)
    summon_status = summon_result.get("status", "FAILED")

    if summon_status not in ("SUMMONED", "SUMMONED_BUT_UNCERTAIN"):
        _print(f"  [BINDING FAILED] Summon returned: {summon_status}")
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.planar_binding.error",
                        f"BINDING_FAILED:summon:{daemon_key}",
                        {"daemon_key": daemon_key, "summon_result": summon_result})
            conn.close()
        except Exception:
            pass
        return {"status": "BINDING_FAILED", "error": f"Summon failed: {summon_status}",
                "summon_result": summon_result}

    pid = summon_result.get("pid", 0)

    # ── STEP 2: Verify incarnation (the Charisma check) ──
    _print(f"  [VERIFY] Checking incarnation of {spec.name} (PID {pid})...")
    time.sleep(2)  # Give the daemon time to fully start
    scry = spell_scrying(daemon_key)
    alive = scry.get("status") == "ALIVE"

    if not alive:
        _print(f"  [BINDING FAILED] {spec.name} did not survive incarnation")
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.planar_binding.error",
                        f"BINDING_FAILED:incarnation:{daemon_key}:{pid}",
                        {"daemon_key": daemon_key, "pid": pid,
                         "scrying_result": dict(scry) if hasattr(scry, 'keys') else scry})
            conn.close()
        except Exception:
            pass
        return {"status": "BINDING_FAILED", "error": "Daemon did not survive incarnation",
                "pid": pid, "scrying": scry}

    # ── STEP 3: Seal the binding circle ──
    seal_nonce = secrets.token_hex(8).upper()
    now = datetime.now(timezone.utc).isoformat()

    binding_data = {
        "daemon_key": daemon_key,
        "daemon_name": spec.name,
        "port": spec.port,
        "commander": spec.commander,
        "pid": pid,
        "seal_nonce": seal_nonce,
        "bound_at": now,
        "spell_cast": spec.spell_cast,
        "sla_heartbeat_max_s": 3600,
        "sla_max_restarts": 3,
        "model": spec.ollama_model or "none",
        "is_persistent": spec.is_persistent,
        "core_thesis": "Every binding circle drawn IS another plane claimed.",
    }
    seal_hash = hashlib.sha256(json.dumps(binding_data, sort_keys=True).encode()).hexdigest()
    binding_data["seal_hash"] = seal_hash

    # Write binding circle CloudEvent
    try:
        conn = get_db_rw()
        row_id = write_event(conn, f"hfo.gen{GEN}.p7.planar_binding.bind",
                             f"BIND:{daemon_key}:{spec.port}:{pid}:{seal_nonce}",
                             binding_data)
        conn.close()
    except Exception as e:
        _print(f"  [WARN] Could not write binding event: {e}")
        row_id = 0

    # Persist binding state
    bstate["bindings"][daemon_key] = {
        "daemon_key": daemon_key,
        "daemon_name": spec.name,
        "port": spec.port,
        "commander": spec.commander,
        "pid": pid,
        "seal_nonce": seal_nonce,
        "seal_hash": seal_hash,
        "bound_at": now,
        "sla_heartbeat_max_s": 3600,
        "sla_max_restarts": 3,
        "restarts": 0,
        "status": "SEALED",
    }
    _save_binding_state(bstate)

    _print(f"  [SEALED] {spec.name} is BOUND")
    _print(f"  [SEALED] PID: {pid} | Nonce: {seal_nonce}")
    _print(f"  [SEALED] Seal Hash: {seal_hash[:16]}...")
    _print(f"  [SEALED] SSOT Row: {row_id}")

    return {
        "status": "BOUND",
        "daemon": daemon_key,
        "name": spec.name,
        "pid": pid,
        "port": spec.port,
        "commander": spec.commander,
        "seal_nonce": seal_nonce,
        "seal_hash": seal_hash,
        "ssot_row": row_id,
        "sbe_given": f"Daemon {daemon_key} exists in DAEMON_REGISTRY",
        "sbe_when": f"PLANAR_BINDING bind cast for {daemon_key}",
        "sbe_then": f"Daemon summoned PID {pid}, verified alive, sealed with nonce {seal_nonce}",
    }


# ═══════════════════════════════════════════════════════════════
# § 5  SPELL: INSPECT — Check binding integrity
# ═══════════════════════════════════════════════════════════════

def spell_inspect(daemon_key: str, quiet: bool = False) -> dict[str, Any]:
    """
    PLANAR_BINDING INSPECT — Check binding circle integrity.

    SBE Contract:
      Given  daemon_key has an active binding
      When   spell_inspect(daemon_key) is called
      Then   daemon liveness, heartbeat count, SLA compliance are reported
    """
    _print = (lambda *a, **k: None) if quiet else print
    bstate = _load_binding_state()
    binding = bstate.get("bindings", {}).get(daemon_key)

    if not binding:
        return {"status": "NOT_BOUND", "daemon": daemon_key}

    # Check if daemon is still alive
    if _SPELL_GATE_AVAILABLE:
        scry = spell_scrying(daemon_key)
        alive = scry.get("status") == "ALIVE"
    else:
        alive = False

    # Query SSOT for heartbeat events
    heartbeat_count = 0
    last_heartbeat = None
    error_count = 0
    try:
        conn = get_db_ro()
        # Count heartbeats since binding
        bound_at = binding.get("bound_at", "1970-01-01")
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE (event_type LIKE '%heartbeat%' OR event_type LIKE '%singer%heartbeat%')
               AND source LIKE ? AND timestamp >= ?""",
            (f"%{daemon_key}%", bound_at),
        ).fetchone()
        heartbeat_count = row["cnt"] if row else 0

        # Last heartbeat
        row = conn.execute(
            """SELECT timestamp FROM stigmergy_events
               WHERE (event_type LIKE '%heartbeat%' OR event_type LIKE '%singer%heartbeat%')
               AND source LIKE ? ORDER BY id DESC LIMIT 1""",
            (f"%{daemon_key}%",),
        ).fetchone()
        last_heartbeat = row["timestamp"] if row else None

        # Error count
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE event_type LIKE '%error%' AND source LIKE ?
               AND timestamp >= ?""",
            (f"%{daemon_key}%", bound_at),
        ).fetchone()
        error_count = row["cnt"] if row else 0
        conn.close()
    except Exception as e:
        _print(f"  [WARN] SSOT query failed: {e}")

    # SLA compliance check
    sla_ok = True
    sla_violations = []
    if not alive:
        sla_ok = False
        sla_violations.append("daemon_dead")
    if binding.get("restarts", 0) > binding.get("sla_max_restarts", 3):
        sla_ok = False
        sla_violations.append("restart_limit_exceeded")

    # Update status
    now = datetime.now(timezone.utc).isoformat()
    if not alive and binding.get("status") == "SEALED":
        binding["status"] = "BROKEN"
        bstate["bindings"][daemon_key] = binding
        _save_binding_state(bstate)
        # Write broken event
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.planar_binding.broken",
                        f"BROKEN:{daemon_key}:{binding.get('pid', 0)}",
                        {"daemon_key": daemon_key, "pid": binding.get("pid", 0),
                         "seal_nonce": binding.get("seal_nonce"),
                         "bound_at": binding.get("bound_at"),
                         "detected_at": now,
                         "p4_adversarial": "Daemon process died after binding — binding circle broken"})
            conn.close()
        except Exception:
            pass

    binding["last_inspected"] = now

    result = {
        "status": binding.get("status", "UNKNOWN"),
        "daemon": daemon_key,
        "name": binding.get("daemon_name"),
        "port": binding.get("port"),
        "pid": binding.get("pid"),
        "alive": alive,
        "seal_nonce": binding.get("seal_nonce"),
        "bound_at": binding.get("bound_at"),
        "heartbeat_count": heartbeat_count,
        "last_heartbeat": last_heartbeat,
        "error_count": error_count,
        "restarts": binding.get("restarts", 0),
        "sla_compliant": sla_ok,
        "sla_violations": sla_violations,
    }

    # Emit inspect event
    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.planar_binding.inspect",
                    f"INSPECT:{daemon_key}:{binding.get('status', '?')}",
                    result)
        conn.close()
    except Exception:
        pass

    _print(f"  [{binding.get('status', '?')}] {binding.get('daemon_name', daemon_key)}")
    _print(f"  PID: {binding.get('pid')} | Alive: {alive}")
    _print(f"  Seal: {binding.get('seal_nonce')} | Bound: {binding.get('bound_at', '?')[:19]}")
    _print(f"  Heartbeats: {heartbeat_count} | Errors: {error_count}")
    _print(f"  SLA: {'COMPLIANT' if sla_ok else 'VIOLATED — ' + ', '.join(sla_violations)}")

    return result


# ═══════════════════════════════════════════════════════════════
# § 6  SPELL: RELEASE — Dissolve the binding circle
# ═══════════════════════════════════════════════════════════════

def spell_release(daemon_key: str, dry_run: bool = False, quiet: bool = False) -> dict[str, Any]:
    """
    PLANAR_BINDING RELEASE — Gracefully dissolve binding.

    SBE Contract:
      Given  daemon_key has an active binding
      When   spell_release(daemon_key) is called
      Then   daemon is banished via spell_gate, binding state cleared,
             binding_dissolved CloudEvent written
    """
    _print = (lambda *a, **k: None) if quiet else print
    bstate = _load_binding_state()
    binding = bstate.get("bindings", {}).get(daemon_key)

    if not binding:
        return {"status": "NOT_BOUND", "daemon": daemon_key}

    if dry_run:
        return {"status": "DRY_RUN", "daemon": daemon_key,
                "would_release": binding.get("daemon_name")}

    # Banish via spell_gate
    banish_result = {}
    if _SPELL_GATE_AVAILABLE:
        _print(f"  [RELEASE] Dissolving binding circle for {binding.get('daemon_name')}...")
        banish_result = spell_banish(daemon_key, quiet=quiet)

    # Update state
    now = datetime.now(timezone.utc).isoformat()
    old_status = binding.get("status")
    binding["status"] = "RELEASED"
    bstate["bindings"][daemon_key] = binding
    _save_binding_state(bstate)

    # Write release event
    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.planar_binding.release",
                    f"RELEASE:{daemon_key}:{binding.get('pid', 0)}",
                    {"daemon_key": daemon_key,
                     "daemon_name": binding.get("daemon_name"),
                     "seal_nonce": binding.get("seal_nonce"),
                     "previous_status": old_status,
                     "banish_result": banish_result,
                     "released_at": now})
        conn.close()
    except Exception:
        pass

    _print(f"  [RELEASED] {binding.get('daemon_name')} — binding circle dissolved")
    return {"status": "RELEASED", "daemon": daemon_key,
            "seal_nonce": binding.get("seal_nonce"),
            "banish_result": banish_result}


# ═══════════════════════════════════════════════════════════════
# § 7  SPELL: CENSUS — All binding statuses
# ═══════════════════════════════════════════════════════════════

def spell_census(quiet: bool = False) -> dict[str, Any]:
    """
    PLANAR_BINDING CENSUS — Report all binding statuses.

    SBE Contract:
      Given  some daemons are bound and some are not
      When   spell_census() is called
      Then   complete binding status for all registered daemons is returned
    """
    _print = (lambda *a, **k: None) if quiet else print
    bstate = _load_binding_state()
    registry_keys = list(DAEMON_REGISTRY.keys()) if DAEMON_REGISTRY else []

    census = {}
    for dk in registry_keys:
        binding = bstate.get("bindings", {}).get(dk)
        if binding:
            # Verify alive if sealed
            alive = False
            if binding.get("status") == "SEALED" and _SPELL_GATE_AVAILABLE:
                scry = spell_scrying(dk)
                alive = scry.get("status") == "ALIVE"
                if not alive:
                    binding["status"] = "BROKEN"
                    bstate["bindings"][dk] = binding
            census[dk] = {
                "name": binding.get("daemon_name"),
                "port": binding.get("port"),
                "status": binding.get("status"),
                "pid": binding.get("pid"),
                "alive": alive,
                "seal_nonce": binding.get("seal_nonce"),
                "bound_at": binding.get("bound_at", "?")[:19],
            }
        else:
            spec = DAEMON_REGISTRY.get(dk)
            census[dk] = {
                "name": spec.name if spec else dk,
                "port": spec.port if spec else "?",
                "status": "UNBOUND",
                "pid": None,
                "alive": False,
                "seal_nonce": None,
            }

    _save_binding_state(bstate)

    sealed = sum(1 for c in census.values() if c["status"] == "SEALED")
    broken = sum(1 for c in census.values() if c["status"] == "BROKEN")
    released = sum(1 for c in census.values() if c["status"] == "RELEASED")
    unbound = sum(1 for c in census.values() if c["status"] == "UNBOUND")

    result = {
        "census": census,
        "total": len(census),
        "sealed": sealed,
        "broken": broken,
        "released": released,
        "unbound": unbound,
    }

    _print(f"  Binding Census: {len(census)} daemons")
    _print(f"  SEALED: {sealed} | BROKEN: {broken} | RELEASED: {released} | UNBOUND: {unbound}")
    _print()
    for dk, info in sorted(census.items(), key=lambda x: x[1].get("port", "Z")):
        st = info["status"]
        icon = {"SEALED": ">>>", "BROKEN": "xxx", "RELEASED": "~~~", "UNBOUND": "..."}
        _print(f"  {icon.get(st, '???')} [{info.get('port', '?')}] {info.get('name', dk):<35s} {st}")

    return result


# ═══════════════════════════════════════════════════════════════
# § 8  SPELL: BIND-FLEET — Greater Planar Binding
# ═══════════════════════════════════════════════════════════════

def spell_bind_fleet(
    daemon_keys: list[str],
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
) -> dict[str, Any]:
    """
    GREATER PLANAR BINDING — Bind multiple daemons in priority order.

    SBE Contract:
      Given  a list of valid daemon keys
      When   spell_bind_fleet(keys) is called
      Then   each daemon is bound in priority order
      And    a fleet_binding_circle CloudEvent summarizes all results
    """
    results = {}
    for dk in daemon_keys:
        results[dk] = spell_bind(dk, force=force, dry_run=dry_run, quiet=quiet)

    # Write fleet event
    if not dry_run:
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.planar_binding.fleet",
                        f"FLEET_BIND:{','.join(daemon_keys)}",
                        {"keys": daemon_keys,
                         "bound": [dk for dk, r in results.items() if r.get("status") == "BOUND"],
                         "failed": [dk for dk, r in results.items() if r.get("status") != "BOUND"],
                         "results_summary": {dk: r.get("status") for dk, r in results.items()}})
            conn.close()
        except Exception:
            pass

    return {"status": "FLEET_BIND_COMPLETE", "results": results}


# ═══════════════════════════════════════════════════════════════
# § 9  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "=" * 64)
    print("  P7 SPIDER SOVEREIGN — PLANAR BINDING")
    print("  Summoner of Seals and Spheres — Aspect A: SEALS")
    print("  " + "-" * 64)
    print("  Conjuration (Calling) 6th/8th — PHB p.261-262")
    print("  Every binding circle drawn IS another plane claimed.")
    print("  " + "=" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — PLANAR_BINDING Spell (Gen90)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Spells:
  bind <key>             Bind one daemon (inscribe circle + summon + seal)
  inspect <key>          Check binding integrity + SLA compliance
  release <key>          Dissolve binding (banish + unseal)
  census                 Report all binding statuses
  bind-fleet <k1,k2,...> Greater Planar Binding — bind multiple daemons

Examples:
  python hfo_p7_planar_binding.py bind singer
  python hfo_p7_planar_binding.py bind singer --force
  python hfo_p7_planar_binding.py inspect singer
  python hfo_p7_planar_binding.py release singer
  python hfo_p7_planar_binding.py census
  python hfo_p7_planar_binding.py bind-fleet singer,tremorsense,pyre
""",
    )
    parser.add_argument("spell", choices=["bind", "inspect", "release", "census", "bind-fleet"],
                        help="Spell variant to cast")
    parser.add_argument("target", nargs="?", default=None,
                        help="Daemon key or comma-separated keys (for bind-fleet)")
    parser.add_argument("--force", action="store_true",
                        help="Force rebind (kill existing daemon first)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Pre-flight only, no actual binding")
    parser.add_argument("--json", action="store_true",
                        help="JSON output")
    parser.add_argument("--extra-args", nargs="*", default=None,
                        help="Extra arguments to pass to daemon")

    args = parser.parse_args()
    _print_banner()

    if args.spell == "bind":
        if not args.target:
            print("  ERROR: bind requires a daemon key. Run census to see options.")
            return
        result = spell_bind(args.target, force=args.force, dry_run=args.dry_run,
                            extra_args=args.extra_args)
    elif args.spell == "inspect":
        if not args.target:
            print("  ERROR: inspect requires a daemon key.")
            return
        result = spell_inspect(args.target)
    elif args.spell == "release":
        if not args.target:
            print("  ERROR: release requires a daemon key.")
            return
        result = spell_release(args.target, dry_run=args.dry_run)
    elif args.spell == "census":
        result = spell_census()
    elif args.spell == "bind-fleet":
        if not args.target:
            print("  ERROR: bind-fleet requires comma-separated daemon keys.")
            return
        keys = [k.strip() for k in args.target.split(",")]
        result = spell_bind_fleet(keys, force=args.force, dry_run=args.dry_run)
    else:
        result = {"error": "Unknown spell"}

    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
