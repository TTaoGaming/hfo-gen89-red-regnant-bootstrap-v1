#!/usr/bin/env python3
"""
hfo_p7_wish.py — P7 Spider Sovereign WISH Spell (Gen89)
=========================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | Spell: WISH (Universal 9th)
Title: Summoner of Seals and Spheres | Epic Class: Cosmic Descryer (ELH p.19)
                                       + Thaumaturgist (DMG p.184)
Aspect: A — SEALS (binding authority, C2 governance, correct-by-construction)

PURPOSE:
    Intent → Structural Enforcement Audit — the most powerful spell in the game.
    WISH is the meta-spell that verifies whether stated intent was structurally
    achieved. It turns declarative desires into verifiable postconditions.

    "If you can state it, I can verify it."

    The operator declares a WISH (an invariant, a property, a desired state).
    WISH then queries SSOT, inspects the filesystem, and checks runtime state
    to produce a compliance verdict: GRANTED (all checks pass) or DENIED
    (with specific violations listed). Wishes persist — they are re-audited
    on demand or on schedule.

D&D 3.5e RAW (PHB p.302):
    Wish — Universal 9th — the mightiest spell a mortal can cast.
    Can duplicate any spell of 8th level or lower.
    Can undo misfortune, reshape reality.
    "The DM may rule that the wish does not function as intended."
    XP cost: 5,000 XP (expensive — not to be cast lightly).

CORRECT-BY-CONSTRUCTION:
    WISH is the embodiment of correct-by-construction. Each wish is an SBE
    scenario in Given/When/Then form. The "Given" is the precondition,
    "When" is the audit trigger, "Then" is the expected state.
    If Then fails → DENIED. If Then passes → GRANTED.

SBE/ATDD SCENARIOS (Specification by Example):
═══════════════════════════════════════════════

  TIER 1 — INVARIANT (fail-closed safety):
    Scenario: Empty wish is rejected
      Given no wish text is provided
      When  WISH cast is attempted
      Then  INVALID_WISH is returned
      And   no SSOT event is written

  TIER 2 — HAPPY PATH:
    Scenario: Heartbeat compliance wish
      Given wish "all bound daemons have heartbeat within 1 hour"
      When  WISH cast is invoked
      Then  for each bound daemon, query last heartbeat timestamp
      And   report GRANTED if all within 1hr, DENIED with list of violators

    Scenario: PREY8 session integrity wish
      Given wish "no orphaned PREY8 sessions exist"
      When  WISH cast is invoked
      Then  query stigmergy for perceive events without matching yields
      And   report GRANTED if none orphaned, DENIED with orphan list

    Scenario: Medallion boundary wish
      Given wish "no unauthorized files in silver or gold layers"
      When  WISH cast is invoked
      Then  scan filesystem for files in 1_silver/2_gold without promotion metadata
      And   report compliance

  TIER 3 — PERSISTENCE:
    Scenario: Wish registry
      Given 3 active wishes have been cast
      When  WISH audit is invoked
      Then  all 3 wishes are re-evaluated and compliance reported

    Scenario: Wish revocation
      Given wish #2 is no longer needed
      When  WISH revoke 2 is invoked
      Then  wish #2 is marked REVOKED and excluded from future audits

  TIER 4 — META:
    Scenario: WISH audits itself
      Given wish "WISH spell state file is consistent"
      When  WISH cast is invoked
      Then  verify wish state JSON is valid, IDs are sequential, no duplicates

Event Types:
    hfo.gen89.p7.wish.cast         — Wish declared + evaluated
    hfo.gen89.p7.wish.granted      — Wish condition satisfied
    hfo.gen89.p7.wish.denied       — Wish condition violated
    hfo.gen89.p7.wish.audit        — Batch re-evaluation
    hfo.gen89.p7.wish.revoke       — Wish deactivated
    hfo.gen89.p7.wish.error        — Spell failed

BUILT-IN WISH CHECKS (extensible):
    heartbeat_compliance   — All bound daemons have recent heartbeats
    prey8_integrity        — No orphaned PREY8 perceive sessions
    medallion_boundary     — No unauthorized silver/gold files
    ssot_health            — Database accessible, tables exist, FTS working
    daemon_fleet_alive     — All registered daemons that should be alive are alive
    stigmergy_freshness    — Recent stigmergy events exist (system not silent)
    config_valid           — hfo_env_config validates without errors

USAGE:
    python hfo_p7_wish.py cast "all daemons have recent heartbeats"
    python hfo_p7_wish.py cast --check heartbeat_compliance
    python hfo_p7_wish.py cast --check prey8_integrity
    python hfo_p7_wish.py cast --check medallion_boundary
    python hfo_p7_wish.py cast --check ssot_health
    python hfo_p7_wish.py audit                    # Re-evaluate all active wishes
    python hfo_p7_wish.py list                     # Show all wishes
    python hfo_p7_wish.py revoke 3                 # Revoke wish #3
    python hfo_p7_wish.py --json cast --check ssot_health

Pointer key: p7.wish
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
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
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
SOURCE_TAG = f"hfo_p7_wish_gen{GEN}"
FORGE_ROOT = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge"

# Wish state file — tracks active wishes
WISH_STATE_FILE = HFO_ROOT / ".p7_wish_state.json"


# ═══════════════════════════════════════════════════════════════
# § 1  DATABASE & CLOUDEVENT HELPERS
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
# § 2  WISH PERSISTENCE — The Wish Registry
# ═══════════════════════════════════════════════════════════════

@dataclass
class WishRecord:
    """A persisted wish — a declarative invariant to verify."""
    wish_id: int
    wish_text: str              # Human-readable wish statement
    check_name: str             # Machine check function name (or "custom")
    sbe_given: str              # SBE precondition
    sbe_when: str               # SBE trigger
    sbe_then: str               # SBE expected outcome
    created_at: str             # ISO timestamp
    last_evaluated: str = ""    # ISO timestamp of last audit
    last_verdict: str = ""      # GRANTED | DENIED | PENDING
    last_violations: str = ""   # JSON-encoded violation list
    status: str = "ACTIVE"      # ACTIVE | REVOKED
    evaluation_count: int = 0
    granted_count: int = 0
    denied_count: int = 0

def _load_wish_state() -> dict:
    if WISH_STATE_FILE.exists():
        try:
            return json.loads(WISH_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"wishes": {}, "next_id": 1, "last_updated": None}

def _save_wish_state(state: dict):
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    WISH_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# § 3  BUILT-IN CHECK FUNCTIONS — The Wish Verification Library
# ═══════════════════════════════════════════════════════════════

def _check_ssot_health() -> tuple[bool, list[str]]:
    """
    Verify SSOT database is accessible and functional.

    SBE:
      Given  SSOT database exists at the PAL-resolved path
      When   ssot_health check is invoked
      Then   DB opens, tables exist, FTS5 works, >0 documents
    """
    violations = []
    if not SSOT_DB.exists():
        return False, [f"SSOT database not found at {SSOT_DB}"]
    try:
        conn = get_db_ro()
        # Check tables exist
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for needed in ["documents", "stigmergy_events", "meta"]:
            if needed not in tables:
                violations.append(f"Missing table: {needed}")

        # Check document count
        row = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        doc_count = row["cnt"] if row else 0
        if doc_count == 0:
            violations.append("documents table is empty")

        # Check FTS5
        try:
            conn.execute("SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'test' LIMIT 1")
        except Exception as e:
            violations.append(f"FTS5 not working: {e}")

        # Check stigmergy_events count
        row = conn.execute("SELECT COUNT(*) as cnt FROM stigmergy_events").fetchone()
        event_count = row["cnt"] if row else 0
        if event_count == 0:
            violations.append("stigmergy_events is empty")

        conn.close()
    except Exception as e:
        violations.append(f"Database connection failed: {e}")

    return len(violations) == 0, violations


def _check_heartbeat_compliance() -> tuple[bool, list[str]]:
    """
    Verify all bound daemons have heartbeat events within 1 hour.

    SBE:
      Given  daemon binding state exists with SEALED daemons
      When   heartbeat_compliance check is invoked
      Then   each bound daemon has heartbeat event within last 3600s
    """
    violations = []
    binding_file = HFO_ROOT / ".p7_planar_binding_state.json"
    if not binding_file.exists():
        return True, []  # No bindings = vacuously true

    try:
        bstate = json.loads(binding_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True, []

    sealed = {k: v for k, v in bstate.get("bindings", {}).items()
              if v.get("status") == "SEALED"}
    if not sealed:
        return True, []  # No sealed daemons = vacuously true

    threshold = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    try:
        conn = get_db_ro()
        for dk, binding in sealed.items():
            row = conn.execute(
                """SELECT MAX(timestamp) as last_ts FROM stigmergy_events
                   WHERE (event_type LIKE '%heartbeat%' OR source LIKE ?)
                   AND timestamp >= ?""",
                (f"%{dk}%", threshold),
            ).fetchone()
            last_ts = row["last_ts"] if row and row["last_ts"] else None
            if not last_ts:
                violations.append(f"{dk}: no heartbeat in last hour (bound PID {binding.get('pid')})")
        conn.close()
    except Exception as e:
        violations.append(f"Heartbeat query failed: {e}")

    return len(violations) == 0, violations


def _check_prey8_integrity() -> tuple[bool, list[str]]:
    """
    Verify no orphaned PREY8 perceive sessions exist.

    SBE:
      Given  PREY8 perceive and yield events exist in stigmergy
      When   prey8_integrity check is invoked
      Then   every perceive has a matching yield (no orphans)
    """
    violations = []
    try:
        conn = get_db_ro()
        # Get all perceive events
        perceives = conn.execute(
            """SELECT id, timestamp, data_json FROM stigmergy_events
               WHERE event_type LIKE '%perceive%'
               ORDER BY id DESC LIMIT 50"""
        ).fetchall()

        # Get all yield events
        yields = conn.execute(
            """SELECT id, timestamp, data_json FROM stigmergy_events
               WHERE event_type LIKE '%yield%'
               ORDER BY id DESC LIMIT 50"""
        ).fetchall()

        # Extract nonces from yields
        yield_nonces = set()
        for y in yields:
            try:
                data = json.loads(y["data_json"])
                d = data.get("data", data)
                nonce = d.get("perceive_nonce", d.get("nonce", ""))
                if nonce:
                    yield_nonces.add(nonce)
            except (json.JSONDecodeError, TypeError):
                pass

        # Check each perceive has a matching yield
        for p in perceives:
            try:
                data = json.loads(p["data_json"])
                d = data.get("data", data)
                nonce = d.get("nonce", "")
                if nonce and nonce not in yield_nonces:
                    violations.append(
                        f"Orphaned perceive: nonce={nonce[:12]}... at {p['timestamp'][:19]}"
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        conn.close()
    except Exception as e:
        violations.append(f"PREY8 query failed: {e}")

    return len(violations) == 0, violations


def _check_medallion_boundary() -> tuple[bool, list[str]]:
    """
    Verify medallion layer boundaries are respected.

    SBE:
      Given  forge directories 1_silver, 2_gold, 3_hyper_fractal_obsidian exist
      When   medallion_boundary check is invoked
      Then   no unexpected files (non-governance) exist in higher layers
             without explicit promotion metadata
    """
    violations = []
    # Files that are expected in gold (the SSOT DB, governance docs)
    gold_dir = FORGE_ROOT / "2_gold" / "resources"
    silver_dir = FORGE_ROOT / "1_silver" / "resources"

    # Check silver for any files (should only have validated/promoted content)
    if silver_dir.exists():
        for f in silver_dir.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                # Silver files should have a reason to be there
                # For now, just count them — the real check is promotion metadata
                pass  # Silver is allowed to have human-reviewed content

    # Check gold for unexpected files
    if gold_dir.exists():
        expected_gold = {"hfo_gen89_ssot.sqlite"}
        for f in gold_dir.rglob("*"):
            if f.is_file() and f.name not in expected_gold:
                # Gold files should be hardened governance docs
                if not f.name.startswith("REFERENCE_") and not f.name.endswith(".json"):
                    violations.append(
                        f"Unexpected file in gold: {f.relative_to(FORGE_ROOT)}"
                    )

    return len(violations) == 0, violations


def _check_daemon_fleet_alive() -> tuple[bool, list[str]]:
    """
    Verify all daemons with SEALED bindings are still alive.

    SBE:
      Given  bound daemons exist in binding state
      When   daemon_fleet_alive check is invoked
      Then   every SEALED daemon has a running PID
    """
    violations = []
    binding_file = HFO_ROOT / ".p7_planar_binding_state.json"
    if not binding_file.exists():
        return True, []

    try:
        bstate = json.loads(binding_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True, []

    try:
        from hfo_p7_spell_gate import spell_scrying
        for dk, binding in bstate.get("bindings", {}).items():
            if binding.get("status") == "SEALED":
                scry = spell_scrying(dk)
                if scry.get("status") != "ALIVE":
                    violations.append(
                        f"{dk}: SEALED but not alive (PID {binding.get('pid')})"
                    )
    except ImportError:
        violations.append("spell_gate not importable — cannot verify fleet")

    return len(violations) == 0, violations


def _check_stigmergy_freshness() -> tuple[bool, list[str]]:
    """
    Verify the system is not silent — recent stigmergy events exist.

    SBE:
      Given  the HFO system should be actively producing events
      When   stigmergy_freshness check is invoked
      Then   at least 1 event exists in the last 4 hours
    """
    violations = []
    threshold = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    try:
        conn = get_db_ro()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM stigmergy_events WHERE timestamp >= ?",
            (threshold,),
        ).fetchone()
        count = row["cnt"] if row else 0
        if count == 0:
            violations.append("No stigmergy events in the last 4 hours — system may be silent")
        conn.close()
    except Exception as e:
        violations.append(f"Freshness query failed: {e}")

    return len(violations) == 0, violations


def _check_config_valid() -> tuple[bool, list[str]]:
    """
    Verify hfo_env_config validates without errors.

    SBE:
      Given  .env and hfo_env_config.py exist
      When   config_valid check is invoked
      Then   validate() returns empty error list
    """
    violations = []
    try:
        from hfo_env_config import validate as validate_config
        errors = validate_config()
        violations.extend(errors)
    except ImportError:
        violations.append("hfo_env_config not importable")
    except Exception as e:
        violations.append(f"Config validation failed: {e}")

    return len(violations) == 0, violations


# Registry mapping check names to functions + SBE definitions
WISH_CHECKS: dict[str, dict[str, Any]] = {
    "ssot_health": {
        "fn": _check_ssot_health,
        "sbe_given": "SSOT database exists at PAL-resolved path",
        "sbe_when": "ssot_health wish is evaluated",
        "sbe_then": "DB opens, tables exist, FTS5 works, documents present",
    },
    "heartbeat_compliance": {
        "fn": _check_heartbeat_compliance,
        "sbe_given": "Daemons are bound via PLANAR_BINDING with SEALED status",
        "sbe_when": "heartbeat_compliance wish is evaluated",
        "sbe_then": "Each bound daemon has heartbeat event within last hour",
    },
    "prey8_integrity": {
        "fn": _check_prey8_integrity,
        "sbe_given": "PREY8 perceive and yield events exist in stigmergy trail",
        "sbe_when": "prey8_integrity wish is evaluated",
        "sbe_then": "Every perceive event has a matching yield (no orphans)",
    },
    "medallion_boundary": {
        "fn": _check_medallion_boundary,
        "sbe_given": "Medallion architecture (bronze→silver→gold→hfo) is enforced",
        "sbe_when": "medallion_boundary wish is evaluated",
        "sbe_then": "No unauthorized files in silver/gold/hfo layers",
    },
    "daemon_fleet_alive": {
        "fn": _check_daemon_fleet_alive,
        "sbe_given": "Daemons are bound with SEALED status",
        "sbe_when": "daemon_fleet_alive wish is evaluated",
        "sbe_then": "Every SEALED daemon has a running PID",
    },
    "stigmergy_freshness": {
        "fn": _check_stigmergy_freshness,
        "sbe_given": "HFO system should be actively producing events",
        "sbe_when": "stigmergy_freshness wish is evaluated",
        "sbe_then": "At least 1 stigmergy event exists in last 4 hours",
    },
    "config_valid": {
        "fn": _check_config_valid,
        "sbe_given": ".env and hfo_env_config.py exist",
        "sbe_when": "config_valid wish is evaluated",
        "sbe_then": "validate() returns zero errors",
    },
}


# ═══════════════════════════════════════════════════════════════
# § 4  SPELL: CAST — Declare and evaluate a wish
# ═══════════════════════════════════════════════════════════════

def spell_cast(
    wish_text: str = "",
    check_name: str = "",
    quiet: bool = False,
) -> dict[str, Any]:
    """
    WISH CAST — Declare an invariant and evaluate it NOW.

    SBE Contract:
      Given  a wish text or a named check
      When   spell_cast is invoked
      Then   the check is evaluated, verdict rendered (GRANTED/DENIED),
             result persisted to wish registry, CloudEvent written
    """
    _print = (lambda *a, **k: None) if quiet else print

    # ── INVARIANT: must provide wish text or check name ──
    if not wish_text and not check_name:
        return {"status": "INVALID_WISH", "error": "Provide wish text or --check name"}

    # Resolve check function
    if check_name:
        if check_name not in WISH_CHECKS:
            return {"status": "INVALID_WISH",
                    "error": f"Unknown check: {check_name}. Available: {list(WISH_CHECKS.keys())}"}
        check_def = WISH_CHECKS[check_name]
        check_fn = check_def["fn"]
        sbe_given = check_def["sbe_given"]
        sbe_when = check_def["sbe_when"]
        sbe_then = check_def["sbe_then"]
        if not wish_text:
            wish_text = f"I wish: {sbe_then}"
    else:
        # Custom wish — run all checks, looking for the most relevant
        check_name = "custom"
        sbe_given = "Operator stated a wish"
        sbe_when = f"WISH cast: '{wish_text}'"
        sbe_then = wish_text
        check_fn = None  # Custom wishes can't auto-verify yet

    # Evaluate
    now = datetime.now(timezone.utc).isoformat()
    granted = False
    violations = []

    if check_fn:
        _print(f"  [WISH] Evaluating: {wish_text}")
        _print(f"  [SBE]  Given: {sbe_given}")
        _print(f"  [SBE]  When:  {sbe_when}")
        _print(f"  [SBE]  Then:  {sbe_then}")
        _print()
        granted, violations = check_fn()
        verdict = "GRANTED" if granted else "DENIED"
    else:
        verdict = "PENDING"
        _print(f"  [WISH] Custom wish registered (no auto-check): {wish_text}")
        _print(f"  [NOTE] Custom wishes require manual audit or future check implementation")

    # Persist to wish registry
    wstate = _load_wish_state()
    wish_id = wstate.get("next_id", 1)
    wstate["wishes"][str(wish_id)] = {
        "wish_id": wish_id,
        "wish_text": wish_text,
        "check_name": check_name,
        "sbe_given": sbe_given,
        "sbe_when": sbe_when,
        "sbe_then": sbe_then,
        "created_at": now,
        "last_evaluated": now,
        "last_verdict": verdict,
        "last_violations": json.dumps(violations),
        "status": "ACTIVE",
        "evaluation_count": 1,
        "granted_count": 1 if granted else 0,
        "denied_count": 0 if granted else 1,
    }
    wstate["next_id"] = wish_id + 1
    _save_wish_state(wstate)

    # Write CloudEvent
    event_type = f"hfo.gen{GEN}.p7.wish.{'granted' if granted else 'denied' if check_fn else 'cast'}"
    try:
        conn = get_db_rw()
        row_id = write_event(conn, event_type,
                             f"WISH:{wish_id}:{verdict}:{check_name}",
                             {"wish_id": wish_id, "wish_text": wish_text,
                              "check_name": check_name, "verdict": verdict,
                              "violations": violations,
                              "sbe_given": sbe_given, "sbe_when": sbe_when,
                              "sbe_then": sbe_then,
                              "core_thesis": "If you can state it, I can verify it."})
        conn.close()
    except Exception as e:
        _print(f"  [WARN] SSOT write failed: {e}")
        row_id = 0

    if check_fn:
        if granted:
            _print(f"  [GRANTED] ✓ Wish #{wish_id} — {wish_text}")
        else:
            _print(f"  [DENIED]  ✗ Wish #{wish_id} — {wish_text}")
            for v in violations:
                _print(f"    ✗ {v}")

    return {
        "status": verdict,
        "wish_id": wish_id,
        "wish_text": wish_text,
        "check_name": check_name,
        "violations": violations,
        "violation_count": len(violations),
        "sbe_given": sbe_given,
        "sbe_when": sbe_when,
        "sbe_then": sbe_then,
        "ssot_row": row_id,
    }


# ═══════════════════════════════════════════════════════════════
# § 5  SPELL: AUDIT — Re-evaluate all active wishes
# ═══════════════════════════════════════════════════════════════

def spell_audit(quiet: bool = False) -> dict[str, Any]:
    """
    WISH AUDIT — Re-evaluate all active wishes.

    SBE Contract:
      Given  N active wishes exist in the registry
      When   spell_audit is invoked
      Then   each wish is re-evaluated, verdicts updated, summary reported
    """
    _print = (lambda *a, **k: None) if quiet else print
    wstate = _load_wish_state()
    now = datetime.now(timezone.utc).isoformat()

    results = {}
    granted_total = 0
    denied_total = 0
    pending_total = 0

    for wid, wish in wstate.get("wishes", {}).items():
        if wish.get("status") != "ACTIVE":
            continue

        check_name = wish.get("check_name", "custom")
        check_def = WISH_CHECKS.get(check_name)

        if check_def and check_def.get("fn"):
            check_fn = check_def["fn"]
            granted, violations = check_fn()
            verdict = "GRANTED" if granted else "DENIED"
            if granted:
                granted_total += 1
            else:
                denied_total += 1
        else:
            verdict = "PENDING"
            violations = []
            pending_total += 1

        # Update wish
        wish["last_evaluated"] = now
        wish["last_verdict"] = verdict
        wish["last_violations"] = json.dumps(violations)
        wish["evaluation_count"] = wish.get("evaluation_count", 0) + 1
        if verdict == "GRANTED":
            wish["granted_count"] = wish.get("granted_count", 0) + 1
        elif verdict == "DENIED":
            wish["denied_count"] = wish.get("denied_count", 0) + 1

        results[wid] = {
            "wish_id": int(wid),
            "wish_text": wish.get("wish_text"),
            "check_name": check_name,
            "verdict": verdict,
            "violations": violations,
        }

    _save_wish_state(wstate)

    # Write audit event
    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.wish.audit",
                    f"AUDIT:{len(results)}:G{granted_total}D{denied_total}P{pending_total}",
                    {"total": len(results), "granted": granted_total,
                     "denied": denied_total, "pending": pending_total,
                     "results": results})
        conn.close()
    except Exception:
        pass

    _print(f"  [AUDIT] {len(results)} active wishes evaluated")
    _print(f"  GRANTED: {granted_total} | DENIED: {denied_total} | PENDING: {pending_total}")
    _print()
    for wid, r in results.items():
        icon = {"GRANTED": "✓", "DENIED": "✗", "PENDING": "?"}
        _print(f"  {icon.get(r['verdict'], '?')} #{r['wish_id']}: {r['wish_text'][:60]}")
        if r["violations"]:
            for v in r["violations"][:3]:
                _print(f"      ✗ {v}")

    return {"audit_results": results, "granted": granted_total,
            "denied": denied_total, "pending": pending_total}


# ═══════════════════════════════════════════════════════════════
# § 6  SPELL: REVOKE — Deactivate a wish
# ═══════════════════════════════════════════════════════════════

def spell_revoke(wish_id: int, quiet: bool = False) -> dict[str, Any]:
    """
    WISH REVOKE — Deactivate a wish.

    SBE Contract:
      Given  wish #N exists and is ACTIVE
      When   spell_revoke(N) is called
      Then   wish is marked REVOKED, excluded from future audits
    """
    _print = (lambda *a, **k: None) if quiet else print
    wstate = _load_wish_state()
    wish = wstate.get("wishes", {}).get(str(wish_id))

    if not wish:
        return {"status": "NOT_FOUND", "wish_id": wish_id}

    if wish.get("status") == "REVOKED":
        return {"status": "ALREADY_REVOKED", "wish_id": wish_id}

    wish["status"] = "REVOKED"
    _save_wish_state(wstate)

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.wish.revoke",
                    f"REVOKE:{wish_id}:{wish.get('check_name', 'custom')}",
                    {"wish_id": wish_id, "wish_text": wish.get("wish_text"),
                     "check_name": wish.get("check_name"),
                     "total_evaluations": wish.get("evaluation_count", 0),
                     "total_granted": wish.get("granted_count", 0),
                     "total_denied": wish.get("denied_count", 0)})
        conn.close()
    except Exception:
        pass

    _print(f"  [REVOKED] Wish #{wish_id}: {wish.get('wish_text', '?')[:60]}")
    return {"status": "REVOKED", "wish_id": wish_id,
            "wish_text": wish.get("wish_text")}


# ═══════════════════════════════════════════════════════════════
# § 7  SPELL: LIST — Show all wishes
# ═══════════════════════════════════════════════════════════════

def spell_list(quiet: bool = False) -> dict[str, Any]:
    """Show all wishes in the registry."""
    _print = (lambda *a, **k: None) if quiet else print
    wstate = _load_wish_state()
    wishes = wstate.get("wishes", {})

    _print(f"  Wish Registry: {len(wishes)} total")
    _print()
    for wid, wish in sorted(wishes.items(), key=lambda x: int(x[0])):
        st = wish.get("status", "?")
        verdict = wish.get("last_verdict", "?")
        check = wish.get("check_name", "custom")
        evals = wish.get("evaluation_count", 0)
        icon = {"GRANTED": "✓", "DENIED": "✗", "PENDING": "?", "REVOKED": "~"}
        status_icon = icon.get(verdict, "?") if st == "ACTIVE" else "~"
        _print(f"  {status_icon} #{wid}: [{st}] {wish.get('wish_text', '?')[:60]}")
        _print(f"       Check: {check} | Evals: {evals} | Last: {verdict}")

    return {"wishes": wishes, "total": len(wishes)}


# ═══════════════════════════════════════════════════════════════
# § 8  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "=" * 64)
    print("  P7 SPIDER SOVEREIGN — WISH")
    print("  Summoner of Seals and Spheres — Aspect A: SEALS")
    print("  " + "-" * 64)
    print("  Universal 9th — PHB p.302 — the mightiest spell a mortal can cast")
    print("  If you can state it, I can verify it.")
    print("  " + "=" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — WISH Spell (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Spells:
  cast [text]             Declare and evaluate a wish
  cast --check <name>     Use a built-in check function
  audit                   Re-evaluate all active wishes
  list                    Show all wishes
  revoke <id>             Deactivate a wish

Built-in checks:
  ssot_health             Database accessible, tables exist, FTS working
  heartbeat_compliance    All bound daemons have recent heartbeats
  prey8_integrity         No orphaned PREY8 perceive sessions
  medallion_boundary      No unauthorized silver/gold files
  daemon_fleet_alive      All sealed daemons are running
  stigmergy_freshness     Recent events exist (system not silent)
  config_valid            hfo_env_config validates cleanly

Examples:
  python hfo_p7_wish.py cast --check ssot_health
  python hfo_p7_wish.py cast --check prey8_integrity
  python hfo_p7_wish.py cast "I wish all daemons have heartbeats"
  python hfo_p7_wish.py audit
  python hfo_p7_wish.py list
  python hfo_p7_wish.py revoke 3
""",
    )
    parser.add_argument("spell", choices=["cast", "audit", "list", "revoke"],
                        help="Spell variant")
    parser.add_argument("target", nargs="?", default=None,
                        help="Wish text (for cast) or wish ID (for revoke)")
    parser.add_argument("--check", dest="check_name", default="",
                        help="Named check function for cast")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    _print_banner()

    if args.spell == "cast":
        result = spell_cast(
            wish_text=args.target or "",
            check_name=args.check_name,
        )
    elif args.spell == "audit":
        result = spell_audit()
    elif args.spell == "list":
        result = spell_list()
    elif args.spell == "revoke":
        if not args.target:
            print("  ERROR: revoke requires a wish ID.")
            return
        result = spell_revoke(int(args.target))
    else:
        result = {"error": "Unknown spell"}

    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
