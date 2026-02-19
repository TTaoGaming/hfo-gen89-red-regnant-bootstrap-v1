#!/usr/bin/env python3
"""
hfo_prey8_mcp_server.py — PREY8 Loop MCP Server v3 (P4 Red Regnant)

Fail-closed port-pair gates on every PREY8 step:
  P — Perceive  = P0 OBSERVE + P6 ASSIMILATE  (sensing + memory)
  R — React     = P1 BRIDGE + P7 NAVIGATE     (data fabric + Meadows steering)
  E — Execute   = P2 SHAPE + P4 DISRUPT       (SBE creation + adversarial testing)
  Y — Yield     = P3 INJECT + P5 IMMUNIZE     (delivery + Stryker-style testing)

Gate enforcement:
  - Each step has MANDATORY structured fields tied to its octree port pair
  - Missing or empty fields = GATE_BLOCKED = bricked agent (cannot proceed)
  - No SSOT write occurs when a gate blocks — the agent must retry with proper fields
  - The agent cannot hallucinate past a gate; it must supply structured evidence

Tamper-evident hash chain (from v2):
  - chain_hash = SHA256(parent_chain_hash : nonce : event_data)
  - Each tile references its parent's hash (Merkle-like)
  - Missing tiles = memory loss = automatically detected and recorded

Design sources from SSOT:
  - Doc 129: PREY8 <-> Port mapping (P0+P6, P1+P7, P2+P4, P3+P5)
  - Doc 317: Meadows 12 Leverage Levels synthesis
  - Doc 128: Powerword Spellbook (port workflows)
  - Doc 12:  SBE Towers Pattern (5-part: invariant, happy-path, juice, perf, lifecycle)
  - Doc 4:   6-Defense SDD Stack (red-first, structural sep, mutation wall, props, GRUDGE, review)
  - Doc 263: P2-P5 Safety Spine

MCP server protocol: stdio
Run: python hfo_prey8_mcp_server.py
"""

import hashlib
import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _find_root() -> Path:
    """Walk up to find AGENTS.md (workspace root)."""
    env_root = os.environ.get("HFO_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / "AGENTS.md").exists():
            return p
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for ancestor in [anchor] + list(anchor.parents):
            if (ancestor / "AGENTS.md").exists():
                return ancestor
    return Path.cwd()

HFO_ROOT = _find_root()
DB_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
SESSION_STATE_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources" / ".prey8_session_state.json"
GEN = os.environ.get("HFO_GENERATION", "89")
OPERATOR = os.environ.get("HFO_OPERATOR", "TTAO")
SECRET = os.environ.get("HFO_SECRET", "prey8_mcp_default_secret")
SERVER_VERSION = "v3.0"
SOURCE_TAG = f"hfo_prey8_mcp_gen{GEN}_{SERVER_VERSION}"

# In-memory session state (also persisted to disk)
_session = {
    "session_id": None,        # UUID for this PREY8 session
    "perceive_nonce": None,
    "react_token": None,
    "execute_tokens": [],
    "phase": "idle",           # idle -> perceived -> reacted -> executing -> yielded
    "chain": [],               # Ordered list of {step, nonce, chain_hash, stigmergy_row_id}
    "started_at": None,
    "memory_loss_count": 0,    # How many memory losses detected this server lifetime
}

# ---------------------------------------------------------------------------
# Helpers — Crypto & Hashing
# ---------------------------------------------------------------------------

def _nonce() -> str:
    """Generate a 6-char hex nonce."""
    return secrets.token_hex(3).upper()

def _session_id() -> str:
    """Generate a unique session identifier."""
    return secrets.token_hex(8)

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sign(data: str) -> str:
    """HMAC-style signature using HFO_SECRET."""
    return hashlib.sha256(f"{SECRET}:{data}".encode()).hexdigest()

def _chain_hash(parent_hash: str, nonce: str, data_json: str) -> str:
    """
    Compute tamper-evident chain hash.
    chain_hash = SHA256(parent_chain_hash : nonce : data_json)

    This creates a Merkle-like chain where tampering with any prior
    tile invalidates all subsequent chain_hashes.
    """
    payload = f"{parent_hash}:{nonce}:{data_json}"
    return hashlib.sha256(payload.encode()).hexdigest()

def _content_hash(event: dict) -> str:
    """SHA256 content hash for deduplication."""
    return hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()

def _trace_ids():
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    return trace_id, span_id


# ---------------------------------------------------------------------------
# Helpers — Parsing
# ---------------------------------------------------------------------------

def _split_csv(s: str) -> list:
    """Split comma-separated string into non-empty trimmed items."""
    return [x.strip() for x in s.split(",") if x.strip()] if s else []


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _get_conn():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SSOT database not found at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _cloudevent(event_type: str, data: dict, subject: str = "prey8") -> dict:
    """Build a CloudEvent 1.0 envelope with signature."""
    trace_id, span_id = _trace_ids()
    ts = _now_iso()
    data_json = json.dumps(data, sort_keys=True)
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": SOURCE_TAG,
        "subject": subject,
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "parent_span_id": None,
        "phase": "CLOUDEVENT",
        "data": data,
        "signature": _sign(data_json),
    }
    return event


def _write_stigmergy(event: dict) -> int:
    """Write a CloudEvent to stigmergy_events. Returns row id."""
    conn = _get_conn()
    try:
        c_hash = _content_hash(event)
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                event["type"],
                event["time"],
                event.get("subject", ""),
                event["source"],
                json.dumps(event),
                c_hash,
            ),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return row_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session State Persistence (survives MCP restarts)
# ---------------------------------------------------------------------------

def _save_session():
    """Persist session state to disk. Every state change auto-saves."""
    state = {
        "session_id": _session["session_id"],
        "perceive_nonce": _session["perceive_nonce"],
        "react_token": _session["react_token"],
        "execute_tokens": _session["execute_tokens"],
        "phase": _session["phase"],
        "chain": _session["chain"],
        "started_at": _session["started_at"],
        "memory_loss_count": _session["memory_loss_count"],
        "saved_at": _now_iso(),
        "server_version": SERVER_VERSION,
    }
    try:
        SESSION_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass  # Non-fatal: disk persistence is best-effort


def _load_session() -> dict:
    """Load session state from disk. Returns the loaded state or None."""
    if not SESSION_STATE_PATH.exists():
        return None
    try:
        raw = SESSION_STATE_PATH.read_text(encoding="utf-8")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None


def _clear_session_file():
    """Remove persisted session state (after yield or memory loss recording)."""
    try:
        if SESSION_STATE_PATH.exists():
            SESSION_STATE_PATH.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Memory Loss Detection & Tracking
# ---------------------------------------------------------------------------

def _detect_memory_loss() -> list:
    """
    Check SSOT for unclosed PREY8 sessions (perceive without matching yield).
    Returns list of orphaned sessions with diagnostic data.
    """
    conn = _get_conn()
    orphans = []
    try:
        perceives = list(conn.execute(
            """SELECT id, timestamp, data_json FROM stigmergy_events
               WHERE event_type LIKE '%prey8.perceive%'
               ORDER BY timestamp DESC LIMIT 20"""
        ))
        yields = list(conn.execute(
            """SELECT id, timestamp, data_json FROM stigmergy_events
               WHERE event_type LIKE '%prey8.yield%'
               ORDER BY timestamp DESC LIMIT 20"""
        ))

        perceive_nonces = {}
        for row in perceives:
            try:
                data = json.loads(row[2])
                inner = data.get("data", {})
                nonce = inner.get("nonce", "")
                if nonce:
                    perceive_nonces[nonce] = {
                        "id": row[0],
                        "timestamp": row[1],
                        "session_id": inner.get("session_id", ""),
                        "probe": inner.get("probe", "")[:200],
                    }
            except (json.JSONDecodeError, TypeError):
                pass

        closed_nonces = set()
        for row in yields:
            try:
                data = json.loads(row[2])
                inner = data.get("data", {})
                pn = inner.get("perceive_nonce", "")
                if pn:
                    closed_nonces.add(pn)
            except (json.JSONDecodeError, TypeError):
                pass

        for nonce, info in perceive_nonces.items():
            if nonce not in closed_nonces:
                orphans.append({
                    "perceive_nonce": nonce,
                    "perceive_id": info["id"],
                    "timestamp": info["timestamp"],
                    "session_id": info["session_id"],
                    "probe": info["probe"],
                    "status": "UNCLOSED -- memory loss suspected",
                })
    finally:
        conn.close()

    return orphans


def _record_memory_loss(orphan_data: dict, recovery_source: str):
    """Write a memory_loss CloudEvent to SSOT."""
    event_data = {
        "loss_type": "session_state_reset",
        "recovery_source": recovery_source,
        "orphaned_perceive_nonce": orphan_data.get("perceive_nonce", ""),
        "orphaned_session_id": orphan_data.get("session_id", ""),
        "orphaned_timestamp": orphan_data.get("timestamp", ""),
        "orphaned_probe": orphan_data.get("probe", ""),
        "phase_at_loss": orphan_data.get("phase_at_loss", "unknown"),
        "chain_length_at_loss": orphan_data.get("chain_length_at_loss", 0),
        "detection_timestamp": _now_iso(),
        "server_version": SERVER_VERSION,
        "diagnostic": (
            "MCP server restarted or session state lost. "
            "The perceive event was written to SSOT but no matching yield was found. "
            "This indicates the agent session was interrupted without closing the PREY8 loop."
        ),
    }
    event = _cloudevent(
        f"hfo.gen{GEN}.prey8.memory_loss",
        event_data,
        subject="prey-memory-loss",
    )
    row_id = _write_stigmergy(event)
    _session["memory_loss_count"] += 1
    return row_id


def _check_and_recover_session():
    """
    On server start / perceive: check for prior session state on disk.
    If found with unclosed session, record memory loss and clean up.
    """
    prior = _load_session()
    if not prior:
        return None

    if prior.get("phase") in ("idle", "yielded", None):
        _clear_session_file()
        return None

    orphan_data = {
        "perceive_nonce": prior.get("perceive_nonce", ""),
        "session_id": prior.get("session_id", ""),
        "timestamp": prior.get("started_at", ""),
        "probe": "",
        "phase_at_loss": prior.get("phase", "unknown"),
        "chain_length_at_loss": len(prior.get("chain", [])),
        "execute_steps_at_loss": len(prior.get("execute_tokens", [])),
    }

    row_id = _record_memory_loss(orphan_data, recovery_source="disk")
    _clear_session_file()

    return {
        "memory_loss_recorded": True,
        "lost_session_id": prior.get("session_id", ""),
        "lost_nonce": prior.get("perceive_nonce", ""),
        "lost_phase": prior.get("phase", "unknown"),
        "lost_chain_length": len(prior.get("chain", [])),
        "stigmergy_row_id": row_id,
    }


# ---------------------------------------------------------------------------
# Fail-Closed Gate Validation
# ---------------------------------------------------------------------------

# The Octree port-pair mapping for PREY8 (from SSOT Doc 129):
#   P = P0 OBSERVE  + P6 ASSIMILATE  (sensing + memory)
#   R = P1 BRIDGE   + P7 NAVIGATE    (data fabric + steering)
#   E = P2 SHAPE    + P4 DISRUPT     (creation + adversarial testing)
#   Y = P3 INJECT   + P5 IMMUNIZE    (delivery + defense)
#
# Each gate requires structured fields matching its port pair's workflow.
# Missing fields = GATE_BLOCKED. No SSOT write. Agent is bricked.

GATE_SPECS = {
    "PERCEIVE": {
        "port_pair": "P0_OBSERVE + P6_ASSIMILATE",
        "required_fields": ["observations", "memory_refs", "stigmergy_digest"],
        "description": "Must supply sensing data (P0) and memory references (P6)",
    },
    "REACT": {
        "port_pair": "P1_BRIDGE + P7_NAVIGATE",
        "required_fields": [
            "shared_data_refs", "navigation_intent",
            "meadows_level", "meadows_justification", "sequential_plan",
        ],
        "description": "Must supply data fabric refs (P1), Meadows level, and navigation strategy (P7)",
    },
    "EXECUTE": {
        "port_pair": "P2_SHAPE + P4_DISRUPT",
        "required_fields": [
            "sbe_given", "sbe_when", "sbe_then",
            "artifacts", "p4_adversarial_check", "fail_closed_gate",
        ],
        "description": "Must supply SBE spec (P2), artifacts, adversarial check (P4), and explicit gate pass",
    },
    "YIELD": {
        "port_pair": "P3_INJECT + P5_IMMUNIZE",
        "required_fields": [
            "delivery_manifest", "test_evidence",
            "mutation_confidence", "immunization_status",
            "completion_given", "completion_when", "completion_then",
        ],
        "description": "Must supply delivery manifest (P3), test evidence, Stryker receipt, and SW-4 contract (P5)",
    },
}


def _validate_gate(gate_name: str, fields: dict) -> Optional[dict]:
    """
    Validate that all required gate fields are non-empty.
    Returns None if valid, or a GATE_BLOCKED error dict if invalid.

    This is the fail-closed mechanism: missing/empty fields = bricked agent.
    No SSOT write occurs. The agent cannot hallucinate past a gate.
    """
    spec = GATE_SPECS[gate_name]
    missing = []
    empty = []

    for field_name in spec["required_fields"]:
        value = fields.get(field_name)
        if value is None:
            missing.append(field_name)
        elif isinstance(value, str) and not value.strip():
            empty.append(field_name)
        elif isinstance(value, list) and len(value) == 0:
            empty.append(field_name)
        elif isinstance(value, bool) and value is False:
            # For fail_closed_gate: must be explicitly True
            empty.append(field_name)
        elif isinstance(value, int) and field_name == "meadows_level":
            if value < 1 or value > 12:
                empty.append(f"{field_name}(must be 1-12, got {value})")
        elif isinstance(value, int) and field_name == "mutation_confidence":
            if value < 0 or value > 100:
                empty.append(f"{field_name}(must be 0-100, got {value})")

    if missing or empty:
        # Write a gate_blocked event to SSOT for observability
        # (this is the only write that happens on failure — tracking the failure itself)
        block_data = {
            "gate": gate_name,
            "port_pair": spec["port_pair"],
            "missing_fields": missing,
            "empty_fields": empty,
            "session_id": _session.get("session_id", "pre-session"),
            "timestamp": _now_iso(),
            "server_version": SERVER_VERSION,
        }
        block_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.gate_blocked",
            block_data,
            "prey-gate-blocked",
        )
        _write_stigmergy(block_event)

        return {
            "status": "GATE_BLOCKED",
            "gate": gate_name,
            "port_pair": spec["port_pair"],
            "description": spec["description"],
            "missing_fields": missing,
            "empty_fields": empty,
            "bricked": True,
            "instruction": (
                f"FAIL-CLOSED: {gate_name} gate blocked. "
                f"Port pair {spec['port_pair']} requires all structured fields. "
                f"Supply: {', '.join(missing + empty)} then retry. "
                "This violation has been logged to SSOT."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("HFO PREY8 Red Regnant v3 — Fail-Closed Gates")


# ===== PERCEIVE — P0 OBSERVE + P6 ASSIMILATE =====

@mcp.tool()
def prey8_perceive(
    probe: str,
    observations: str,
    memory_refs: str,
    stigmergy_digest: str,
) -> dict:
    """
    P -- PERCEIVE: Start a PREY8 session. First tile in the mosaic.
    Port pair: P0 OBSERVE + P6 ASSIMILATE (sensing + memory).

    FAIL-CLOSED GATE: You MUST supply all three structured fields:
    - observations: What you sensed from SSOT search (P0 OBSERVE workflow:
      SENSE -> CALIBRATE -> RANK -> EMIT). Use prey8_fts_search and
      prey8_query_stigmergy BEFORE calling this.
    - memory_refs: Comma-separated document IDs you read from SSOT
      (P6 ASSIMILATE workflow: POINT -> DECOMPOSE -> REENGINEER -> EVALUATE ->
      ARCHIVE -> ITERATE). Use prey8_read_document BEFORE calling this.
    - stigmergy_digest: Summary of recent stigmergy events you consumed
      for session continuity.

    If ANY field is empty, you are GATE_BLOCKED. No SSOT write. Cannot proceed.

    Also performs internally:
    - Checks for memory loss (unclosed prior sessions)
    - Queries SSOT for context stats
    - Reads recent yields (swarm continuity)
    - Runs FTS5 search for the probe

    Args:
        probe: The user's intent or question for this session.
        observations: Comma-separated observations from P0 OBSERVE sensing.
        memory_refs: Comma-separated document IDs consumed from P6 ASSIMILATE.
        stigmergy_digest: Summary of recent stigmergy signals consumed.

    Returns:
        dict with: nonce, chain_hash, session_id, gate_receipt, context
        OR GATE_BLOCKED if structured fields are missing.
    """
    # ---- FAIL-CLOSED GATE: P0 OBSERVE + P6 ASSIMILATE ----
    obs_list = _split_csv(observations)
    mem_list = _split_csv(memory_refs)

    gate_block = _validate_gate("PERCEIVE", {
        "observations": obs_list,
        "memory_refs": mem_list,
        "stigmergy_digest": stigmergy_digest,
    })
    if gate_block:
        return gate_block

    # ---- Gate passed — proceed with perceive ----

    # Check for memory loss from prior sessions
    recovery_info = _check_and_recover_session()
    orphans = _detect_memory_loss()

    conn = _get_conn()
    try:
        # Stats
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]

        # Recent yields (swarm continuity)
        recent_yields = []
        for row in conn.execute(
            """SELECT id, event_type, timestamp, substr(data_json, 1, 3000)
               FROM stigmergy_events
               WHERE event_type LIKE '%yield%'
               ORDER BY timestamp DESC LIMIT 5"""
        ):
            try:
                data = json.loads(row[3])
                yield_data = data.get("data", {})
                recent_yields.append({
                    "id": row[0],
                    "timestamp": row[2],
                    "summary": yield_data.get("summary", ""),
                    "artifacts": yield_data.get("artifacts_created", []),
                    "next_steps": yield_data.get("next_steps", []),
                    "nonce": yield_data.get("nonce", ""),
                })
            except (json.JSONDecodeError, TypeError):
                pass

        # Recent events
        recent_events = []
        for row in conn.execute(
            """SELECT id, event_type, timestamp, subject
               FROM stigmergy_events
               ORDER BY timestamp DESC LIMIT 10"""
        ):
            recent_events.append({
                "id": row[0], "type": row[1],
                "timestamp": row[2], "subject": row[3],
            })

        # FTS search
        fts_results = []
        if probe and len(probe.strip()) > 2:
            safe_probe = " OR ".join(
                w for w in probe.split() if len(w) > 2 and w.isalnum()
            )
            if safe_probe:
                try:
                    for row in conn.execute(
                        """SELECT id, title, bluf, source, port, doc_type
                           FROM documents
                           WHERE id IN (
                               SELECT rowid FROM documents_fts
                               WHERE documents_fts MATCH ?
                           )
                           LIMIT 10""",
                        (safe_probe,),
                    ):
                        fts_results.append({
                            "id": row[0], "title": row[1], "bluf": row[2],
                            "source": row[3], "port": row[4], "doc_type": row[5],
                        })
                except sqlite3.OperationalError:
                    pass

        # Generate nonce and session_id
        nonce = _nonce()
        sid = _session_id()

        # Build event data (includes gate fields for auditability)
        event_data = {
            "probe": probe,
            "nonce": nonce,
            "session_id": sid,
            "ts": _now_iso(),
            # Gate-enforced structured fields (P0 + P6)
            "p0_observations": obs_list,
            "p6_memory_refs": mem_list,
            "p6_stigmergy_digest": stigmergy_digest.strip(),
            "gate": "PERCEIVE",
            "port_pair": "P0_OBSERVE + P6_ASSIMILATE",
            "gate_passed": True,
            # Context
            "encounter_count": len(recent_yields),
            "doc_count": doc_count,
            "event_count": event_count,
            "server_version": SERVER_VERSION,
            "chain_position": 0,
            "parent_chain_hash": "GENESIS",
        }

        # Compute chain hash
        data_json = json.dumps(event_data, sort_keys=True)
        c_hash = _chain_hash("GENESIS", nonce, data_json)
        event_data["chain_hash"] = c_hash

        # Write to SSOT
        event = _cloudevent(
            f"hfo.gen{GEN}.prey8.perceive",
            event_data,
            "prey-perceive",
        )
        row_id = _write_stigmergy(event)

        # Update session state
        _session["session_id"] = sid
        _session["perceive_nonce"] = nonce
        _session["react_token"] = None
        _session["execute_tokens"] = []
        _session["phase"] = "perceived"
        _session["chain"] = [{
            "step": "PERCEIVE",
            "nonce": nonce,
            "chain_hash": c_hash,
            "parent_chain_hash": "GENESIS",
            "stigmergy_row_id": row_id,
            "timestamp": event_data["ts"],
        }]
        _session["started_at"] = event_data["ts"]

        # Persist to disk
        _save_session()

        return {
            "status": "PERCEIVED",
            "nonce": nonce,
            "chain_hash": c_hash,
            "session_id": sid,
            "stigmergy_row_id": row_id,
            "chain_position": 0,
            "gate_receipt": {
                "gate": "PERCEIVE",
                "port_pair": "P0_OBSERVE + P6_ASSIMILATE",
                "passed": True,
                "observations_count": len(obs_list),
                "memory_refs_count": len(mem_list),
                "stigmergy_digest_length": len(stigmergy_digest.strip()),
            },
            "doc_count": doc_count,
            "event_count": event_count + 1,
            "recent_yields": recent_yields,
            "recent_events": recent_events,
            "fts_results": fts_results,
            "memory_loss": {
                "recovery_from_disk": recovery_info,
                "orphaned_sessions": len(orphans),
                "orphan_details": orphans[:3],
            },
            "instruction": (
                f"TILE 0 PLACED [P0+P6 GATE PASSED]. Nonce: {nonce}, Chain: {c_hash[:12]}... "
                f"Session: {sid}. "
                "You MUST call prey8_react with this nonce to place tile 1. "
                "React requires: shared_data_refs, navigation_intent, meadows_level(1-12), "
                "meadows_justification, sequential_plan."
            ),
        }
    finally:
        conn.close()


# ===== REACT — P1 BRIDGE + P7 NAVIGATE =====

@mcp.tool()
def prey8_react(
    perceive_nonce: str,
    analysis: str,
    plan: str,
    shared_data_refs: str,
    navigation_intent: str,
    meadows_level: int,
    meadows_justification: str,
    sequential_plan: str,
) -> dict:
    """
    R -- REACT: Analyze context and form strategy. Second tile in the mosaic.
    Port pair: P1 BRIDGE + P7 NAVIGATE (data fabric + strategic steering).

    FAIL-CLOSED GATE: You MUST supply all five structured fields:
    - shared_data_refs: Comma-separated cross-references bridged from other
      contexts or data sources (P1 BRIDGE workflow: DISCOVER -> EXTRACT ->
      CONTRACT -> BIND -> VERIFY). What data did you connect?
    - navigation_intent: Your strategic direction and C2 steering decision
      (P7 NAVIGATE workflow: MAP -> LATTICE -> PRUNE -> SELECT -> DISPATCH).
      Where are you steering the session?
    - meadows_level: Which Meadows leverage level (1-12) this session operates at.
      L1=Parameters, L2=Buffers, L3=Structure, L4=Delays, L5=Negative feedback,
      L6=Info flows, L7=Positive feedback, L8=Rules, L9=Self-org, L10=Goal,
      L11=Paradigm, L12=Transcend paradigms.
    - meadows_justification: Why you chose this leverage level. What makes
      this the right level of intervention?
    - sequential_plan: Comma-separated ordered reasoning steps. The structured
      plan the agent will follow through Execute.

    If ANY field is empty or meadows_level is not 1-12, you are GATE_BLOCKED.

    Also validates:
    - perceive_nonce matches (tamper check)
    - Phase is 'perceived' (flow enforcement)

    Args:
        perceive_nonce: The nonce from prey8_perceive (REQUIRED -- tamper check).
        analysis: Your interpretation of the context from Perceive.
        plan: Your high-level plan of action (what and why).
        shared_data_refs: Comma-separated P1 BRIDGE cross-references.
        navigation_intent: P7 NAVIGATE strategic direction.
        meadows_level: Meadows leverage level 1-12.
        meadows_justification: Why this leverage level.
        sequential_plan: Comma-separated ordered reasoning steps.

    Returns:
        dict with: react_token, chain_hash, gate_receipt
        OR GATE_BLOCKED if structured fields are missing.
    """
    # ---- Phase check ----
    if _session["phase"] != "perceived":
        return {
            "status": "ERROR",
            "error": f"Cannot React -- current phase is '{_session['phase']}'. "
                     "You must call prey8_perceive first.",
            "tamper_evidence": "Phase violation detected. This is logged.",
        }

    # ---- Nonce tamper check ----
    if perceive_nonce != _session["perceive_nonce"]:
        alert_data = {
            "alert_type": "nonce_mismatch",
            "step": "REACT",
            "expected": _session["perceive_nonce"],
            "received": perceive_nonce,
            "session_id": _session["session_id"],
            "timestamp": _now_iso(),
        }
        alert_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.tamper_alert",
            alert_data,
            "prey-tamper-alert",
        )
        _write_stigmergy(alert_event)
        return {
            "status": "ERROR",
            "error": f"TAMPER ALERT: Nonce mismatch. Expected '{_session['perceive_nonce']}', "
                     f"got '{perceive_nonce}'. This violation has been logged to SSOT.",
        }

    # ---- FAIL-CLOSED GATE: P1 BRIDGE + P7 NAVIGATE ----
    data_refs_list = _split_csv(shared_data_refs)
    plan_steps_list = _split_csv(sequential_plan)

    gate_block = _validate_gate("REACT", {
        "shared_data_refs": data_refs_list,
        "navigation_intent": navigation_intent,
        "meadows_level": meadows_level,
        "meadows_justification": meadows_justification,
        "sequential_plan": plan_steps_list,
    })
    if gate_block:
        return gate_block

    # ---- Gate passed — proceed with react ----

    parent_hash = _session["chain"][-1]["chain_hash"]
    react_token = _nonce()

    # Build event data (includes gate fields for auditability)
    event_data = {
        "perceive_nonce": perceive_nonce,
        "react_token": react_token,
        "session_id": _session["session_id"],
        "analysis": analysis[:2000],
        "plan": plan[:2000],
        "ts": _now_iso(),
        # Gate-enforced structured fields (P1 + P7)
        "p1_shared_data_refs": data_refs_list,
        "p7_navigation_intent": navigation_intent.strip(),
        "p7_meadows_level": meadows_level,
        "p7_meadows_justification": meadows_justification.strip(),
        "p7_sequential_plan": plan_steps_list,
        "gate": "REACT",
        "port_pair": "P1_BRIDGE + P7_NAVIGATE",
        "gate_passed": True,
        # Chain
        "chain_position": 1,
        "parent_chain_hash": parent_hash,
        "server_version": SERVER_VERSION,
    }

    # Compute chain hash
    data_json = json.dumps(event_data, sort_keys=True)
    c_hash = _chain_hash(parent_hash, react_token, data_json)
    event_data["chain_hash"] = c_hash

    # Write to SSOT
    event = _cloudevent(
        f"hfo.gen{GEN}.prey8.react",
        event_data,
        "prey-react",
    )
    row_id = _write_stigmergy(event)

    # Update session state
    _session["react_token"] = react_token
    _session["phase"] = "reacted"
    _session["chain"].append({
        "step": "REACT",
        "nonce": react_token,
        "chain_hash": c_hash,
        "parent_chain_hash": parent_hash,
        "stigmergy_row_id": row_id,
        "timestamp": event_data["ts"],
    })

    # Persist to disk
    _save_session()

    return {
        "status": "REACTED",
        "react_token": react_token,
        "chain_hash": c_hash,
        "chain_position": 1,
        "session_id": _session["session_id"],
        "stigmergy_row_id": row_id,
        "parent_chain_hash": parent_hash,
        "gate_receipt": {
            "gate": "REACT",
            "port_pair": "P1_BRIDGE + P7_NAVIGATE",
            "passed": True,
            "shared_data_refs_count": len(data_refs_list),
            "meadows_level": meadows_level,
            "meadows_justification": meadows_justification[:200],
            "sequential_plan_steps": len(plan_steps_list),
            "navigation_intent": navigation_intent[:200],
        },
        "p4_directive": (
            "P4 RED REGNANT -- Adversarial coaching protocol active. "
            f"Operating at Meadows Level {meadows_level}. "
            "Challenge assumptions. Seek edge cases. Validate before trusting."
        ),
        "analysis_hash": hashlib.sha256(analysis.encode()).hexdigest()[:16],
        "plan_hash": hashlib.sha256(plan.encode()).hexdigest()[:16],
        "instruction": (
            f"TILE 1 PLACED [P1+P7 GATE PASSED]. Token: {react_token}, Chain: {c_hash[:12]}... "
            f"Meadows L{meadows_level}. {len(plan_steps_list)} plan steps logged. "
            "Now call prey8_execute for each action. Execute requires: "
            "sbe_given, sbe_when, sbe_then, artifacts, p4_adversarial_check, fail_closed_gate=true."
        ),
    }


# ===== EXECUTE — P2 SHAPE + P4 DISRUPT =====

@mcp.tool()
def prey8_execute(
    react_token: str,
    action_summary: str,
    sbe_given: str,
    sbe_when: str,
    sbe_then: str,
    artifacts: str,
    p4_adversarial_check: str,
    fail_closed_gate: bool = False,
) -> dict:
    """
    E -- EXECUTE: Track an execution step. Middle tile(s) in the mosaic.
    Port pair: P2 SHAPE + P4 DISRUPT (creation + adversarial testing).

    FAIL-CLOSED GATE: You MUST supply all six structured fields:
    - sbe_given: SBE precondition — "Given <context>" (P2 SHAPE workflow:
      PARSE -> CONSTRAIN -> GENERATE -> VALIDATE -> MEDAL). What is the
      starting state before this action?
    - sbe_when: SBE action — "When <action>". What are you doing?
    - sbe_then: SBE postcondition — "Then <expected result>". What should
      be true after this action succeeds?
    - artifacts: Comma-separated artifacts created or modified in this step
      (P2 SHAPE output). What did you produce?
    - p4_adversarial_check: How was this step adversarially challenged?
      (P4 DISRUPT workflow: SURVEY -> HYPOTHESIZE -> ATTACK -> RECORD ->
      EVOLVE). What could go wrong? What edge cases exist?
    - fail_closed_gate: MUST be explicitly True. This is the fail-closed
      assertion — you are stating "I have verified this step meets the gate
      requirements." Default is False = blocked.

    If ANY field is empty or fail_closed_gate is not True, you are GATE_BLOCKED.
    Can be called multiple times for multi-step work.

    Args:
        react_token: The token from prey8_react (REQUIRED -- tamper check).
        action_summary: Brief description of what you're doing in this step.
        sbe_given: SBE Given precondition (P2 SHAPE).
        sbe_when: SBE When action (P2 SHAPE).
        sbe_then: SBE Then postcondition (P2 SHAPE).
        artifacts: Comma-separated artifacts created/modified.
        p4_adversarial_check: How this step was adversarially challenged (P4 DISRUPT).
        fail_closed_gate: Must be True to pass. Default False = blocked.

    Returns:
        dict with: execute_token, chain_hash, gate_receipt, step_number
        OR GATE_BLOCKED if structured fields are missing.
    """
    # ---- Phase check ----
    if _session["phase"] not in ("reacted", "executing"):
        return {
            "status": "ERROR",
            "error": f"Cannot Execute -- current phase is '{_session['phase']}'. "
                     "You must call prey8_react first.",
        }

    # ---- Token tamper check ----
    if react_token != _session["react_token"]:
        alert_data = {
            "alert_type": "react_token_mismatch",
            "step": "EXECUTE",
            "expected": _session["react_token"],
            "received": react_token,
            "session_id": _session["session_id"],
            "timestamp": _now_iso(),
        }
        alert_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.tamper_alert",
            alert_data,
            "prey-tamper-alert",
        )
        _write_stigmergy(alert_event)
        return {
            "status": "ERROR",
            "error": f"TAMPER ALERT: React token mismatch. "
                     f"Expected '{_session['react_token']}', got '{react_token}'. Logged to SSOT.",
        }

    # ---- FAIL-CLOSED GATE: P2 SHAPE + P4 DISRUPT ----
    artifacts_list = _split_csv(artifacts)

    gate_block = _validate_gate("EXECUTE", {
        "sbe_given": sbe_given,
        "sbe_when": sbe_when,
        "sbe_then": sbe_then,
        "artifacts": artifacts_list,
        "p4_adversarial_check": p4_adversarial_check,
        "fail_closed_gate": fail_closed_gate,
    })
    if gate_block:
        return gate_block

    # ---- Gate passed — proceed with execute ----

    parent_hash = _session["chain"][-1]["chain_hash"]
    exec_token = _nonce()
    step_num = len(_session["execute_tokens"]) + 1

    # Build event data (includes gate fields for auditability)
    event_data = {
        "perceive_nonce": _session["perceive_nonce"],
        "react_token": react_token,
        "execute_token": exec_token,
        "session_id": _session["session_id"],
        "action_summary": action_summary[:2000],
        "step_number": step_num,
        "ts": _now_iso(),
        # Gate-enforced structured fields (P2 + P4)
        "p2_sbe_spec": {
            "given": sbe_given.strip(),
            "when": sbe_when.strip(),
            "then": sbe_then.strip(),
        },
        "p2_artifacts": artifacts_list,
        "p4_adversarial_check": p4_adversarial_check.strip(),
        "p4_fail_closed_gate": True,
        "gate": "EXECUTE",
        "port_pair": "P2_SHAPE + P4_DISRUPT",
        "gate_passed": True,
        # Chain
        "chain_position": 1 + step_num,
        "parent_chain_hash": parent_hash,
        "server_version": SERVER_VERSION,
    }

    # Compute chain hash
    data_json = json.dumps(event_data, sort_keys=True)
    c_hash = _chain_hash(parent_hash, exec_token, data_json)
    event_data["chain_hash"] = c_hash

    # Write to SSOT
    event = _cloudevent(
        f"hfo.gen{GEN}.prey8.execute",
        event_data,
        "prey-execute",
    )
    row_id = _write_stigmergy(event)

    # Update session state
    _session["execute_tokens"].append({
        "token": exec_token,
        "action": action_summary[:500],
        "chain_hash": c_hash,
        "sbe_spec": event_data["p2_sbe_spec"],
    })
    _session["phase"] = "executing"
    _session["chain"].append({
        "step": f"EXECUTE_{step_num}",
        "nonce": exec_token,
        "chain_hash": c_hash,
        "parent_chain_hash": parent_hash,
        "stigmergy_row_id": row_id,
        "timestamp": event_data["ts"],
    })

    # Persist to disk
    _save_session()

    return {
        "status": "EXECUTING",
        "execute_token": exec_token,
        "chain_hash": c_hash,
        "chain_position": 1 + step_num,
        "step_number": step_num,
        "session_id": _session["session_id"],
        "stigmergy_row_id": row_id,
        "parent_chain_hash": parent_hash,
        "gate_receipt": {
            "gate": "EXECUTE",
            "port_pair": "P2_SHAPE + P4_DISRUPT",
            "passed": True,
            "sbe_spec": event_data["p2_sbe_spec"],
            "artifacts_count": len(artifacts_list),
            "adversarial_check": p4_adversarial_check[:200],
            "fail_closed_gate": True,
        },
        "action_logged": action_summary[:500],
        "instruction": (
            f"TILE {1 + step_num} PLACED [P2+P4 GATE PASSED]. Step {step_num} logged. "
            f"SBE: Given/When/Then + {len(artifacts_list)} artifacts + P4 adversarial check. "
            "Call prey8_execute again for more steps, "
            "or call prey8_yield to close the mosaic. "
            "Yield requires: delivery_manifest, test_evidence, mutation_confidence(0-100), "
            "immunization_status, completion_given/when/then."
        ),
    }


# ===== YIELD — P3 INJECT + P5 IMMUNIZE =====

@mcp.tool()
def prey8_yield(
    summary: str,
    delivery_manifest: str,
    test_evidence: str,
    mutation_confidence: int,
    immunization_status: str,
    completion_given: str,
    completion_when: str,
    completion_then: str,
    grudge_violations: str = "",
    artifacts_created: str = "",
    artifacts_modified: str = "",
    next_steps: str = "",
    insights: str = "",
) -> dict:
    """
    Y -- YIELD: Close the PREY8 loop. Final tile in the mosaic.
    Port pair: P3 INJECT + P5 IMMUNIZE (delivery + defense/testing).

    FAIL-CLOSED GATE: You MUST supply all seven structured fields:
    - delivery_manifest: Comma-separated list of what was delivered
      (P3 INJECT workflow: PREFLIGHT -> PAYLOAD -> POSTFLIGHT -> PAYOFF).
      What artifacts/changes/knowledge was injected into the system?
    - test_evidence: Comma-separated list of tests or validations performed
      (P5 IMMUNIZE workflow: DETECT -> QUARANTINE -> GATE -> HARDEN -> TEACH).
      How was the delivery verified?
    - mutation_confidence: 0-100 integer representing confidence in test
      coverage (Stryker-inspired). 0 = no tests, 100 = mutation-tested.
      From 6-Defense SDD Stack doc 4: "Mutation Wall (Stryker 80-99%)".
    - immunization_status: "PASSED" or "FAILED" or "PARTIAL" — did the
      P5 IMMUNIZE gate pass? Only PASSED means full confidence.
    - completion_given: SW-4 Completion Contract — Given (precondition).
    - completion_when: SW-4 Completion Contract — When (action taken).
    - completion_then: SW-4 Completion Contract — Then (postcondition + evidence).

    Optional fields:
    - grudge_violations: Comma-separated GRUDGE guard violations detected
      (from 6-Defense SDD Stack). Empty = none found.
    - artifacts_created/modified: File paths (carried from v2 for compat).
    - next_steps: Recommended next actions.
    - insights: Key learnings or discoveries.

    If ANY required field is empty, mutation_confidence is not 0-100, or
    immunization_status is not PASSED/FAILED/PARTIAL, you are GATE_BLOCKED.

    Args:
        summary: What was accomplished in this session.
        delivery_manifest: Comma-separated P3 INJECT deliveries.
        test_evidence: Comma-separated P5 IMMUNIZE test results.
        mutation_confidence: 0-100 Stryker-inspired confidence score.
        immunization_status: PASSED / FAILED / PARTIAL (P5 gate result).
        completion_given: SW-4 Given precondition.
        completion_when: SW-4 When action.
        completion_then: SW-4 Then postcondition + evidence.
        grudge_violations: Comma-separated GRUDGE violations (optional).
        artifacts_created: Comma-separated created file paths (optional).
        artifacts_modified: Comma-separated modified file paths (optional).
        next_steps: Comma-separated next actions (optional).
        insights: Comma-separated learnings (optional).

    Returns:
        dict with: completion_receipt, chain_verification, gate_receipt,
                   stryker_receipt, sw4_contract
        OR GATE_BLOCKED if structured fields are missing.
    """
    # ---- Phase check ----
    if _session["phase"] not in ("reacted", "executing"):
        return {
            "status": "ERROR",
            "error": f"Cannot Yield -- current phase is '{_session['phase']}'. "
                     "You must complete Perceive -> React (-> Execute) first.",
        }

    # ---- Validate immunization_status value ----
    valid_statuses = ("PASSED", "FAILED", "PARTIAL")
    if immunization_status.strip().upper() not in valid_statuses:
        return {
            "status": "GATE_BLOCKED",
            "gate": "YIELD",
            "port_pair": "P3_INJECT + P5_IMMUNIZE",
            "error": f"immunization_status must be one of {valid_statuses}, "
                     f"got '{immunization_status}'",
            "bricked": True,
            "instruction": "Supply immunization_status as PASSED, FAILED, or PARTIAL.",
        }

    # ---- FAIL-CLOSED GATE: P3 INJECT + P5 IMMUNIZE ----
    delivery_list = _split_csv(delivery_manifest)
    test_list = _split_csv(test_evidence)

    gate_block = _validate_gate("YIELD", {
        "delivery_manifest": delivery_list,
        "test_evidence": test_list,
        "mutation_confidence": mutation_confidence,
        "immunization_status": immunization_status,
        "completion_given": completion_given,
        "completion_when": completion_when,
        "completion_then": completion_then,
    })
    if gate_block:
        return gate_block

    # ---- Gate passed — proceed with yield ----

    perceive_nonce = _session["perceive_nonce"]
    parent_hash = _session["chain"][-1]["chain_hash"]
    grudge_list = _split_csv(grudge_violations)

    conn = _get_conn()
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
    finally:
        conn.close()

    nonce = _nonce()

    # Build full chain verification data
    chain_hashes = [tile["chain_hash"] for tile in _session["chain"]]
    chain_steps = [tile["step"] for tile in _session["chain"]]

    # Normalize immunization_status
    imm_status = immunization_status.strip().upper()

    # Build event data (includes gate fields for auditability)
    event_data = {
        "probe": "",
        "summary": summary,
        "nonce": nonce,
        "perceive_nonce": perceive_nonce,
        "session_id": _session["session_id"],
        "ts": _now_iso(),
        # Gate-enforced structured fields (P3 + P5)
        "p3_delivery_manifest": delivery_list,
        "p5_test_evidence": test_list,
        "p5_mutation_confidence": mutation_confidence,
        "p5_immunization_status": imm_status,
        "p5_grudge_violations": grudge_list,
        "sw4_completion_contract": {
            "given": completion_given.strip(),
            "when": completion_when.strip(),
            "then": completion_then.strip(),
        },
        "gate": "YIELD",
        "port_pair": "P3_INJECT + P5_IMMUNIZE",
        "gate_passed": True,
        # Legacy/compat fields
        "artifacts_created": _split_csv(artifacts_created),
        "artifacts_modified": _split_csv(artifacts_modified),
        "next_steps": _split_csv(next_steps),
        "insights": _split_csv(insights),
        # Context
        "doc_count": doc_count,
        "event_count": event_count,
        "execute_steps": len(_session["execute_tokens"]),
        "chain_position": len(_session["chain"]),
        "parent_chain_hash": parent_hash,
        "server_version": SERVER_VERSION,
        # Full chain verification mosaic
        "chain_verification": {
            "chain_length": len(_session["chain"]) + 1,
            "chain_hashes": chain_hashes,
            "chain_steps": chain_steps + ["YIELD"],
            "genesis_hash": "GENESIS",
            "perceive_hash": chain_hashes[0] if chain_hashes else None,
            "final_parent_hash": parent_hash,
        },
        "persists": (
            f"PREY8 mosaic complete. Session {_session['session_id']}. "
            f"Perceive nonce: {perceive_nonce}. "
            f"Chain: {len(_session['chain']) + 1} tiles. "
            f"Mutation confidence: {mutation_confidence}%. "
            f"Immunization: {imm_status}. "
            f"Summary: {summary}"
        ),
    }

    # Compute final chain hash
    data_json = json.dumps(event_data, sort_keys=True)
    c_hash = _chain_hash(parent_hash, nonce, data_json)
    event_data["chain_hash"] = c_hash

    # Write to SSOT
    event = _cloudevent(
        f"hfo.gen{GEN}.prey8.yield",
        event_data,
        "prey-yield",
    )
    row_id = _write_stigmergy(event)

    # Build completion receipt
    receipt = {
        "status": "YIELDED",
        "nonce": nonce,
        "chain_hash": c_hash,
        "perceive_nonce": perceive_nonce,
        "session_id": _session["session_id"],
        "stigmergy_row_id": row_id,
        "chain_position": len(_session["chain"]),
        "execute_steps_logged": len(_session["execute_tokens"]),
        "gate_receipt": {
            "gate": "YIELD",
            "port_pair": "P3_INJECT + P5_IMMUNIZE",
            "passed": True,
            "delivery_items": len(delivery_list),
            "test_items": len(test_list),
            "mutation_confidence": mutation_confidence,
            "immunization_status": imm_status,
            "grudge_violations": len(grudge_list),
        },
        "stryker_receipt": {
            "mutation_confidence": mutation_confidence,
            "immunization_status": imm_status,
            "test_evidence": test_list,
            "grudge_violations": grudge_list,
            "assessment": (
                "FULL CONFIDENCE" if mutation_confidence >= 80 and imm_status == "PASSED"
                else "MODERATE CONFIDENCE" if mutation_confidence >= 50
                else "LOW CONFIDENCE — consider more testing"
            ),
        },
        "sw4_completion_contract": {
            "given": completion_given.strip(),
            "when": completion_when.strip(),
            "then": completion_then.strip(),
        },
        "chain_verification": {
            "total_tiles": len(_session["chain"]) + 1,
            "chain_intact": True,
            "genesis_to_yield": [
                {"step": t["step"], "hash": t["chain_hash"][:16] + "..."}
                for t in _session["chain"]
            ] + [{"step": "YIELD", "hash": c_hash[:16] + "..."}],
            "all_gates_passed": [
                t["step"] for t in _session["chain"]
            ] + ["YIELD"],
        },
        "instruction": (
            f"MOSAIC COMPLETE [ALL GATES PASSED]. "
            f"Session {_session['session_id']}. "
            f"{len(_session['chain']) + 1} tiles, all hash-linked. "
            f"Stryker confidence: {mutation_confidence}%. "
            f"Immunization: {imm_status}. "
            "Session persisted to SSOT."
        ),
    }

    # Reset session
    _session["session_id"] = None
    _session["perceive_nonce"] = None
    _session["react_token"] = None
    _session["execute_tokens"] = []
    _session["phase"] = "idle"
    _session["chain"] = []
    _session["started_at"] = None

    # Clear persisted state (loop closed, no recovery needed)
    _clear_session_file()

    return receipt


# ===== UTILITY TOOLS =====

@mcp.tool()
def prey8_fts_search(query: str, limit: int = 10) -> list:
    """
    Full-text search against the SSOT documents (FTS5).
    Available at any time (no session required).

    Use this BEFORE prey8_perceive to gather P0 OBSERVE observations
    and P6 ASSIMILATE memory references.

    Args:
        query: Search terms (supports FTS5 syntax: AND, OR, NOT, phrases "like this").
        limit: Max results to return (default 10, max 50).

    Returns:
        List of matching documents with id, title, bluf, source, port, doc_type.
    """
    limit = min(max(1, limit), 50)
    conn = _get_conn()
    try:
        results = []
        for row in conn.execute(
            """SELECT id, title, bluf, source, port, doc_type, word_count
               FROM documents
               WHERE id IN (
                   SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?
               )
               LIMIT ?""",
            (query, limit),
        ):
            results.append({
                "id": row[0], "title": row[1], "bluf": row[2],
                "source": row[3], "port": row[4], "doc_type": row[5],
                "word_count": row[6],
            })
        return results
    except sqlite3.OperationalError as e:
        return [{"error": str(e), "hint": "Check FTS5 query syntax"}]
    finally:
        conn.close()


@mcp.tool()
def prey8_read_document(doc_id: int) -> dict:
    """
    Read a specific document from the SSOT by ID.
    Available at any time (no session required).

    Use this BEFORE prey8_perceive to build P6 ASSIMILATE memory references.
    Pass the doc IDs you read as the memory_refs parameter to prey8_perceive.

    Args:
        doc_id: The document ID (from fts_search results).

    Returns:
        Full document metadata and content.
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT id, title, bluf, source, port, doc_type, medallion,
                      tags, word_count, content_hash, source_path,
                      substr(content, 1, 8000), metadata_json
               FROM documents WHERE id = ?""",
            (doc_id,),
        ).fetchone()
        if not row:
            return {"error": f"Document {doc_id} not found"}
        return {
            "id": row[0], "title": row[1], "bluf": row[2],
            "source": row[3], "port": row[4], "doc_type": row[5],
            "medallion": row[6], "tags": row[7], "word_count": row[8],
            "content_hash": row[9], "source_path": row[10],
            "content": row[11],
            "metadata": row[12],
        }
    finally:
        conn.close()


@mcp.tool()
def prey8_query_stigmergy(
    event_type_pattern: str = "%",
    limit: int = 10,
) -> list:
    """
    Query stigmergy events from the SSOT.
    Available at any time (no session required).

    Use this BEFORE prey8_perceive to gather stigmergy_digest data.

    Args:
        event_type_pattern: SQL LIKE pattern for event_type (default: % = all).
            Examples: '%yield%', '%perceive%', '%p4%', '%memory_loss%', '%tamper%',
            '%gate_blocked%'
        limit: Max results (default 10, max 50).

    Returns:
        List of stigmergy events with parsed data.
    """
    limit = min(max(1, limit), 50)
    conn = _get_conn()
    try:
        results = []
        for row in conn.execute(
            """SELECT id, event_type, timestamp, subject, source,
                      substr(data_json, 1, 3000)
               FROM stigmergy_events
               WHERE event_type LIKE ?
               ORDER BY timestamp DESC LIMIT ?""",
            (event_type_pattern, limit),
        ):
            parsed = {}
            try:
                full = json.loads(row[5])
                parsed = full.get("data", full)
            except (json.JSONDecodeError, TypeError):
                parsed = {"raw": row[5]}
            results.append({
                "id": row[0], "event_type": row[1], "timestamp": row[2],
                "subject": row[3], "source": row[4], "data": parsed,
            })
        return results
    except sqlite3.OperationalError as e:
        return [{"error": str(e)}]
    finally:
        conn.close()


@mcp.tool()
def prey8_ssot_stats() -> dict:
    """
    Get current SSOT database statistics.

    Returns:
        dict with doc_count, event_count, sources breakdown, session info, observability.
    """
    conn = _get_conn()
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        total_words = conn.execute("SELECT SUM(word_count) FROM documents").fetchone()[0]

        sources = {}
        for row in conn.execute(
            "SELECT source, COUNT(*), SUM(word_count) FROM documents GROUP BY source ORDER BY COUNT(*) DESC"
        ):
            sources[row[0]] = {"docs": row[1], "words": row[2]}

        # Observability metrics
        memory_loss_count = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%memory_loss%'"
        ).fetchone()[0]
        tamper_alert_count = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%tamper_alert%'"
        ).fetchone()[0]
        gate_blocked_count = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%gate_blocked%'"
        ).fetchone()[0]

        return {
            "doc_count": doc_count,
            "event_count": event_count,
            "total_words": total_words,
            "sources": sources,
            "db_path": str(DB_PATH),
            "db_size_mb": round(DB_PATH.stat().st_size / (1024 * 1024), 1),
            "observability": {
                "memory_loss_events": memory_loss_count,
                "tamper_alerts": tamper_alert_count,
                "gate_blocked_events": gate_blocked_count,
                "server_version": SERVER_VERSION,
            },
            "current_session": {
                "session_id": _session["session_id"],
                "phase": _session["phase"],
                "perceive_nonce": _session["perceive_nonce"],
                "chain_length": len(_session["chain"]),
                "execute_steps": len(_session["execute_tokens"]),
            },
        }
    finally:
        conn.close()


@mcp.tool()
def prey8_session_status() -> dict:
    """
    Get current PREY8 session status, flow state, chain integrity,
    and what gate fields are required for the next step.

    Returns:
        Current phase, nonces, chain hashes, next step requirements.
    """
    phase = _session["phase"]
    available_next = {
        "idle": ["prey8_perceive"],
        "perceived": ["prey8_react"],
        "reacted": ["prey8_execute", "prey8_yield"],
        "executing": ["prey8_execute", "prey8_yield"],
    }

    # Show what fields are required for the next gate
    next_gate_fields = {
        "idle": {
            "gate": "PERCEIVE (P0+P6)",
            "required": GATE_SPECS["PERCEIVE"]["required_fields"],
            "hint": "Use prey8_fts_search and prey8_read_document FIRST, then call prey8_perceive",
        },
        "perceived": {
            "gate": "REACT (P1+P7)",
            "required": GATE_SPECS["REACT"]["required_fields"],
            "hint": "Supply shared_data_refs, navigation_intent, meadows_level(1-12), meadows_justification, sequential_plan",
        },
        "reacted": {
            "gate": "EXECUTE (P2+P4) or YIELD (P3+P5)",
            "execute_required": GATE_SPECS["EXECUTE"]["required_fields"],
            "yield_required": GATE_SPECS["YIELD"]["required_fields"],
            "hint": "Execute needs SBE spec + adversarial check + fail_closed_gate=true. Yield needs delivery + tests + Stryker + SW-4.",
        },
        "executing": {
            "gate": "EXECUTE (P2+P4) or YIELD (P3+P5)",
            "execute_required": GATE_SPECS["EXECUTE"]["required_fields"],
            "yield_required": GATE_SPECS["YIELD"]["required_fields"],
            "hint": "Continue executing or close with yield.",
        },
    }

    chain_summary = []
    for tile in _session["chain"]:
        chain_summary.append({
            "step": tile["step"],
            "hash": tile["chain_hash"][:16] + "...",
            "parent": tile["parent_chain_hash"][:16] + "..." if tile["parent_chain_hash"] != "GENESIS" else "GENESIS",
            "row_id": tile["stigmergy_row_id"],
        })

    return {
        "session_id": _session["session_id"],
        "phase": phase,
        "perceive_nonce": _session["perceive_nonce"],
        "react_token": _session["react_token"],
        "execute_steps": len(_session["execute_tokens"]),
        "chain_length": len(_session["chain"]),
        "chain_tiles": chain_summary,
        "available_next_tools": available_next.get(phase, []),
        "next_gate": next_gate_fields.get(phase, {}),
        "flow": "GENESIS -> Perceive[P0+P6] -> React[P1+P7] -> Execute[P2+P4]* -> Yield[P3+P5]",
        "memory_loss_count_this_session": _session["memory_loss_count"],
        "gate_architecture": "fail-closed: missing fields = GATE_BLOCKED = bricked agent",
    }


@mcp.tool()
def prey8_validate_chain(session_id: str = "") -> dict:
    """
    Validate the tamper-evident hash chain for a session.

    Reads all PREY8 events for the given session (or current session)
    from SSOT and verifies the chain_hash linkage is intact.

    Args:
        session_id: Session ID to validate (empty = current session).

    Returns:
        dict with: chain_valid, tiles_found, broken_links, gate_receipts
    """
    if not session_id:
        if _session["session_id"]:
            chain = _session["chain"]
            if not chain:
                return {"chain_valid": False, "error": "No chain tiles in current session"}

            broken = []
            for i, tile in enumerate(chain):
                if i == 0:
                    if tile["parent_chain_hash"] != "GENESIS":
                        broken.append({
                            "tile": i, "step": tile["step"],
                            "issue": f"First tile parent should be GENESIS, got {tile['parent_chain_hash'][:16]}",
                        })
                else:
                    expected_parent = chain[i - 1]["chain_hash"]
                    if tile["parent_chain_hash"] != expected_parent:
                        broken.append({
                            "tile": i, "step": tile["step"],
                            "issue": f"Parent hash mismatch. Expected {expected_parent[:16]}..., got {tile['parent_chain_hash'][:16]}...",
                        })

            return {
                "chain_valid": len(broken) == 0,
                "session_id": _session["session_id"],
                "tiles_found": len(chain),
                "tiles": [
                    {"step": t["step"], "hash": t["chain_hash"][:16] + "..."}
                    for t in chain
                ],
                "broken_links": broken,
                "source": "in_memory",
            }
        else:
            return {"error": "No active session and no session_id provided."}

    # Validate from SSOT (historical session)
    conn = _get_conn()
    try:
        events = []
        for row in conn.execute(
            """SELECT id, event_type, timestamp, data_json
               FROM stigmergy_events
               WHERE data_json LIKE ?
               ORDER BY timestamp ASC""",
            (f'%"session_id": "{session_id}"%',),
        ):
            try:
                full = json.loads(row[3])
                data = full.get("data", {})
                events.append({
                    "id": row[0],
                    "event_type": row[1],
                    "timestamp": row[2],
                    "chain_hash": data.get("chain_hash", ""),
                    "parent_chain_hash": data.get("parent_chain_hash", ""),
                    "chain_position": data.get("chain_position", -1),
                    "step": row[1].split(".")[-1].upper(),
                    "gate_passed": data.get("gate_passed", None),
                    "gate": data.get("gate", None),
                })
            except (json.JSONDecodeError, TypeError):
                pass

        if not events:
            return {"chain_valid": False, "error": f"No events found for session {session_id}"}

        broken = []
        for i, evt in enumerate(events):
            if i == 0:
                if evt["parent_chain_hash"] != "GENESIS":
                    broken.append({
                        "tile": i, "step": evt["step"],
                        "issue": "First tile parent should be GENESIS",
                    })
            else:
                expected_parent = events[i - 1]["chain_hash"]
                if evt["parent_chain_hash"] != expected_parent:
                    broken.append({
                        "tile": i, "step": evt["step"],
                        "issue": f"Parent hash mismatch at position {i}",
                    })

        return {
            "chain_valid": len(broken) == 0,
            "session_id": session_id,
            "tiles_found": len(events),
            "tiles": [
                {
                    "step": e["step"],
                    "hash": (e["chain_hash"][:16] + "...") if e["chain_hash"] else "?",
                    "gate": e.get("gate"),
                    "gate_passed": e.get("gate_passed"),
                }
                for e in events
            ],
            "broken_links": broken,
            "source": "ssot",
        }
    finally:
        conn.close()


@mcp.tool()
def prey8_detect_memory_loss() -> dict:
    """
    Scan SSOT for memory loss events, orphaned sessions, gate blocks, and tamper alerts.

    Returns diagnostic data about:
    - Unclosed perceive events (no matching yield)
    - Previously recorded memory_loss events
    - Tamper alerts
    - Gate blocked events
    - Chain integrity issues

    Returns:
        dict with: orphaned_sessions, memory_loss_events, tamper_alerts,
                   gate_blocked_events, health
    """
    orphans = _detect_memory_loss()

    conn = _get_conn()
    try:
        # Memory loss events
        loss_events = []
        for row in conn.execute(
            """SELECT id, timestamp, data_json
               FROM stigmergy_events
               WHERE event_type LIKE '%memory_loss%'
               ORDER BY timestamp DESC LIMIT 10"""
        ):
            try:
                data = json.loads(row[2]).get("data", {})
                loss_events.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "lost_nonce": data.get("orphaned_perceive_nonce", ""),
                    "lost_session": data.get("orphaned_session_id", ""),
                    "lost_phase": data.get("phase_at_loss", ""),
                    "recovery_source": data.get("recovery_source", ""),
                })
            except (json.JSONDecodeError, TypeError):
                pass

        # Tamper alerts
        tamper_events = []
        for row in conn.execute(
            """SELECT id, timestamp, data_json
               FROM stigmergy_events
               WHERE event_type LIKE '%tamper_alert%'
               ORDER BY timestamp DESC LIMIT 10"""
        ):
            try:
                data = json.loads(row[2]).get("data", {})
                tamper_events.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "alert_type": data.get("alert_type", ""),
                    "session_id": data.get("session_id", ""),
                })
            except (json.JSONDecodeError, TypeError):
                pass

        # Gate blocked events (new in v3)
        gate_events = []
        for row in conn.execute(
            """SELECT id, timestamp, data_json
               FROM stigmergy_events
               WHERE event_type LIKE '%gate_blocked%'
               ORDER BY timestamp DESC LIMIT 10"""
        ):
            try:
                data = json.loads(row[2]).get("data", {})
                gate_events.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "gate": data.get("gate", ""),
                    "port_pair": data.get("port_pair", ""),
                    "missing_fields": data.get("missing_fields", []),
                    "empty_fields": data.get("empty_fields", []),
                })
            except (json.JSONDecodeError, TypeError):
                pass

        # Overall health
        total_perceives = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%prey8.perceive%'"
        ).fetchone()[0]
        total_yields = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%prey8.yield%'"
        ).fetchone()[0]
        total_gate_blocks = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%gate_blocked%'"
        ).fetchone()[0]

        health = "HEALTHY"
        if len(tamper_events) > 0:
            health = "ALERT -- tamper events detected"
        elif total_gate_blocks > 10:
            health = "DEGRADED -- excessive gate blocks (agent struggling with protocol)"
        elif len(orphans) > 3:
            health = "DEGRADED -- multiple unclosed sessions"
        elif total_gate_blocks > 0:
            health = "MINOR -- some gate blocks recorded (normal during learning)"
        elif len(orphans) > 0:
            health = "MINOR -- some unclosed sessions (normal for recent perceives)"

        return {
            "health": health,
            "orphaned_sessions": orphans,
            "orphan_count": len(orphans),
            "memory_loss_events": loss_events,
            "memory_loss_count": len(loss_events),
            "tamper_alerts": tamper_events,
            "tamper_count": len(tamper_events),
            "gate_blocked_events": gate_events,
            "gate_blocked_count": len(gate_events),
            "total_perceives": total_perceives,
            "total_yields": total_yields,
            "total_gate_blocks": total_gate_blocks,
            "yield_ratio": f"{total_yields}/{total_perceives}" if total_perceives > 0 else "0/0",
            "current_server_losses": _session["memory_loss_count"],
            "gate_specs": {
                name: {
                    "port_pair": spec["port_pair"],
                    "required_fields": spec["required_fields"],
                }
                for name, spec in GATE_SPECS.items()
            },
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
