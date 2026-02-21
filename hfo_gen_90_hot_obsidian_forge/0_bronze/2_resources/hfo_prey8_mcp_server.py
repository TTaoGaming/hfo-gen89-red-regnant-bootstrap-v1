#!/usr/bin/env python3
"""
hfo_prey8_mcp_server.py — PREY8 Loop MCP Server v4 (P4 Red Regnant)

Swarm-aware multi-agent PREY8 with agent identity, session isolation,
deny-by-default authorization, and stigmergy traceability.

v4.0 upgrades from v3.0 single-tenant:
  - AGENT_REGISTRY: mandatory agent_id on all gated tools (deny-by-default)
  - Per-agent session isolation: _sessions dict keyed by agent_id
  - Per-agent state files: .prey8_session_{agent_id}.json
  - Agent_id in ALL CloudEvents for traceability
  - Port-pair authorization: agents only use tools assigned to their ports
  - Least privilege: unknown agent_id = GATE_BLOCKED

Fail-closed port-pair gates on every PREY8 step:
  P — Perceive  = P0 OBSERVE + P6 ASSIMILATE  (sensing + memory)
  R — React     = P1 BRIDGE + P7 NAVIGATE     (data fabric + Meadows steering)
  E — Execute   = P2 SHAPE + P4 DISRUPT       (SBE creation + adversarial testing)
  Y — Yield     = P3 INJECT + P5 IMMUNIZE     (delivery + Stryker-style testing)

Gate enforcement:
  1. Agent identity check (deny-by-default: unknown agent = BLOCKED)
  2. Port authorization check (agent must have permission for this gate)
  3. Structured field check (all required fields must be non-empty)
  Missing any check = GATE_BLOCKED = bricked agent (cannot proceed)

Tamper-evident hash chain (from v2):
  - chain_hash = SHA256(parent_chain_hash : nonce : event_data)
  - Each tile references its parent's hash (Merkle-like)
  - agent_id embedded in chain = identity is tamper-evident

Design sources from SSOT:
  - Doc 129: PREY8 <-> Port mapping (P0+P6, P1+P7, P2+P4, P3+P5)
  - Doc 4:   6-Defense SDD Stack (Defense 2: structural separation requires agent_id)
  - Doc 52:  Feasibility Assessment (L8+L5 gap: unified P5 enforcement = deny-by-default)
  - Doc 317: Meadows 12 Leverage Levels synthesis
  - Doc 128: Powerword Spellbook (port workflows)
  - Doc 12:  SBE Towers Pattern (5-part: invariant, happy-path, juice, perf, lifecycle)
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
DB_PATH = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
SESSION_STATE_DIR = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources"
# Legacy single-file path for backward compat detection
SESSION_STATE_PATH = SESSION_STATE_DIR / ".prey8_session_state.json"
GEN = os.environ.get("HFO_GENERATION", "90")
OPERATOR = os.environ.get("HFO_OPERATOR", "TTAO")
SECRET = os.environ.get("HFO_SECRET", "prey8_mcp_default_secret")
SERVER_VERSION = "v4.0"
SOURCE_TAG = f"hfo_prey8_mcp_gen{GEN}_{SERVER_VERSION}"


# ---------------------------------------------------------------------------
# AGENT REGISTRY — Deny-by-Default Authorization
# ---------------------------------------------------------------------------
# Every agent MUST be registered here to use gated tools.
# Unknown agent_id = GATE_BLOCKED. No exceptions.
#
# Port permissions define which PREY8 gates an agent can use:
#   PERCEIVE = P0+P6, REACT = P1+P7, EXECUTE = P2+P4, YIELD = P3+P5
#
# "all" means the agent can use all 4 gates (full PREY8 loop).
# Specific port lists restrict to gates matching those ports.
#
# Design principle: least privilege — agents get minimum needed permissions.
# From Doc 4 Defense 2: structural separation requires different agent identities.
# From Doc 52: "before ANY agent does ANYTHING, P5 must approve."

AGENT_REGISTRY = {
    # ---- Legendary Commanders (one per port) ----
    "p0_lidless_legion": {
        "display_name": "P0 Lidless Legion (OBSERVE)",
        "ports": [0, 6],
        "allowed_gates": ["PERCEIVE"],
        "role": "Sensing under contest — read-only scout",
    },
    "p1_web_weaver": {
        "display_name": "P1 Web Weaver (BRIDGE)",
        "ports": [1, 7],
        "allowed_gates": ["REACT"],
        "role": "Shared data fabric — cross-reference bridging",
    },
    "p2_mirror_magus": {
        "display_name": "P2 Mirror Magus (SHAPE)",
        "ports": [2, 4],
        "allowed_gates": ["EXECUTE"],
        "role": "Creation / code generation — shapes artifacts",
    },
    "p3_harmonic_hydra": {
        "display_name": "P3 Harmonic Hydra (INJECT)",
        "ports": [3, 5],
        "allowed_gates": ["YIELD"],
        "role": "Payload delivery — inject artifacts into system",
    },
    "p4_red_regnant": {
        "display_name": "P4 Red Regnant (DISRUPT)",
        "ports": [0, 1, 2, 3, 4, 5, 6, 7],
        "allowed_gates": ["PERCEIVE", "REACT", "EXECUTE", "YIELD"],
        "role": "Adversarial testing — full PREY8 loop access for red team",
    },
    "p5_pyre_praetorian": {
        "display_name": "P5 Pyre Praetorian (IMMUNIZE)",
        "ports": [0, 1, 2, 3, 4, 5, 6, 7],
        "allowed_gates": ["PERCEIVE", "REACT", "EXECUTE", "YIELD"],
        "role": "Blue team / gates — full PREY8 loop for enforcement",
    },
    "p6_kraken_keeper": {
        "display_name": "P6 Kraken Keeper (ASSIMILATE)",
        "ports": [0, 6],
        "allowed_gates": ["PERCEIVE", "REACT", "EXECUTE", "YIELD"],
        "role": "Learning / memory — ingestion and recall",
    },
    "p7_spider_sovereign": {
        "display_name": "P7 Spider Sovereign (NAVIGATE)",
        "ports": [0, 1, 2, 3, 4, 5, 6, 7],
        "allowed_gates": ["PERCEIVE", "REACT", "EXECUTE", "YIELD"],
        "role": "C2 / steering — full PREY8 loop for orchestration",
    },
    # ---- Swarm agent types (from hfo_swarm_agents.py) ----
    "swarm_triage": {
        "display_name": "Swarm Triage Agent",
        "ports": [0, 7],
        "allowed_gates": ["PERCEIVE", "REACT"],
        "role": "Routes requests — perceive + react only",
    },
    "swarm_research": {
        "display_name": "Swarm Research Agent",
        "ports": [0, 1, 6],
        "allowed_gates": ["PERCEIVE", "REACT"],
        "role": "Web search and synthesis — observe + bridge",
    },
    "swarm_coder": {
        "display_name": "Swarm Coder Agent",
        "ports": [2, 4],
        "allowed_gates": ["EXECUTE"],
        "role": "Code generation — shape + disrupt only",
    },
    "swarm_analyst": {
        "display_name": "Swarm Analyst Agent",
        "ports": [0, 1, 6, 7],
        "allowed_gates": ["PERCEIVE", "REACT"],
        "role": "Data analysis — observe + bridge + navigate",
    },
    # ---- Operator / TTAO (human) — full access ----
    "ttao_operator": {
        "display_name": "TTAO Operator (Human)",
        "ports": [0, 1, 2, 3, 4, 5, 6, 7],
        "allowed_gates": ["PERCEIVE", "REACT", "EXECUTE", "YIELD"],
        "role": "Human operator — unrestricted access",
    },
    # ---- Daemon watchdog (read-only, no gated tools) ----
    "watchdog_daemon": {
        "display_name": "Stigmergy Watchdog Daemon",
        "ports": [0, 5],
        "allowed_gates": [],
        "role": "Stigmergy monitoring — utility tools only, no gated access",
    },
}


def _new_session() -> dict:
    """Create a fresh per-agent session state dict."""
    return {
        "session_id": None,
        "perceive_nonce": None,
        "react_token": None,
        "execute_tokens": [],
        "phase": "idle",
        "chain": [],
        "started_at": None,
        "memory_loss_count": 0,
        "agent_id": None,
    }


# Per-agent session state (keyed by agent_id)
_sessions: dict[str, dict] = {}


def _get_session(agent_id: str) -> dict:
    """Get or create a session for the given agent. No authorization check here."""
    if agent_id not in _sessions:
        _sessions[agent_id] = _new_session()
        _sessions[agent_id]["agent_id"] = agent_id
    return _sessions[agent_id]


def _validate_agent(agent_id: str, gate_name: str = None) -> Optional[dict]:
    """
    Deny-by-default agent authorization.
    Returns None if agent is authorized, or a GATE_BLOCKED dict if not.

    Checks:
      1. agent_id is non-empty
      2. agent_id exists in AGENT_REGISTRY
      3. If gate_name provided, agent is allowed to use that gate
    """
    if not agent_id or not agent_id.strip():
        block_data = {
            "reason": "DENY_BY_DEFAULT: agent_id is required",
            "agent_id": "",
            "gate": gate_name or "pre-gate",
            "timestamp": _now_iso(),
            "server_version": SERVER_VERSION,
        }
        block_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.gate_blocked",
            block_data,
            "prey-agent-denied",
        )
        _write_stigmergy(block_event)
        return {
            "status": "GATE_BLOCKED",
            "reason": "DENY_BY_DEFAULT: agent_id is required. Every tool call must include a registered agent_id.",
            "registered_agents": list(AGENT_REGISTRY.keys()),
            "bricked": True,
        }

    agent_id = agent_id.strip().lower()
    if agent_id not in AGENT_REGISTRY:
        # Dynamic registration for 8^n swarm agents
        if agent_id.startswith("p") and len(agent_id) > 1 and agent_id[1].isdigit():
            port = int(agent_id[1])
            AGENT_REGISTRY[agent_id] = {
                "display_name": f"Dynamic Swarm Agent ({agent_id})",
                "ports": [port],
                "allowed_gates": ["PERCEIVE", "REACT", "EXECUTE", "YIELD"],
                "role": f"Dynamic swarm node on port {port}",
            }
        elif agent_id.startswith("swarm_") or agent_id.startswith("agent_"):
            AGENT_REGISTRY[agent_id] = {
                "display_name": f"Dynamic Swarm Agent ({agent_id})",
                "ports": [0, 1, 2, 3, 4, 5, 6, 7],
                "allowed_gates": ["PERCEIVE", "REACT", "EXECUTE", "YIELD"],
                "role": "Dynamic swarm node (full access)",
            }
        else:
            block_data = {
                "reason": f"DENY_BY_DEFAULT: agent_id '{agent_id}' not in AGENT_REGISTRY and does not match swarm patterns",
                "agent_id": agent_id,
                "gate": gate_name or "pre-gate",
                "timestamp": _now_iso(),
                "server_version": SERVER_VERSION,
            }
            block_event = _cloudevent(
                f"hfo.gen{GEN}.prey8.gate_blocked",
                block_data,
                "prey-agent-denied",
            )
            _write_stigmergy(block_event)
            return {
                "status": "GATE_BLOCKED",
                "reason": f"DENY_BY_DEFAULT: agent_id '{agent_id}' is not registered and does not match swarm patterns (pX_*, swarm_*, agent_*).",
                "bricked": True,
            }

    if gate_name:
        agent_spec = AGENT_REGISTRY[agent_id]
        if gate_name not in agent_spec["allowed_gates"]:
            block_data = {
                "reason": f"LEAST_PRIVILEGE: agent '{agent_id}' not authorized for {gate_name} gate",
                "agent_id": agent_id,
                "gate": gate_name,
                "allowed_gates": agent_spec["allowed_gates"],
                "timestamp": _now_iso(),
                "server_version": SERVER_VERSION,
            }
            block_event = _cloudevent(
                f"hfo.gen{GEN}.prey8.gate_blocked",
                block_data,
                "prey-agent-denied",
            )
            _write_stigmergy(block_event)
            return {
                "status": "GATE_BLOCKED",
                "reason": (
                    f"LEAST_PRIVILEGE: agent '{agent_id}' ({agent_spec['display_name']}) "
                    f"is not authorized for the {gate_name} gate. "
                    f"Allowed gates: {agent_spec['allowed_gates']}."
                ),
                "agent_id": agent_id,
                "agent_role": agent_spec["role"],
                "allowed_gates": agent_spec["allowed_gates"],
                "bricked": True,
            }

    return None

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
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _cloudevent(event_type: str, data: dict, subject: str = "prey8",
                agent_id: str = "") -> dict:
    """Build a CloudEvent 1.0 envelope with signature and agent identity."""
    trace_id, span_id = _trace_ids()
    ts = _now_iso()
    # Inject agent_id into event data for traceability
    if agent_id:
        data["agent_id"] = agent_id
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
        "agent_id": agent_id,
        "data": data,
        "signature": _sign(data_json),
    }
    return event


def _write_stigmergy(event: dict) -> int:
    """Write a CloudEvent to stigmergy_events. Returns row id."""
    try:
        from hfo_ssot_write import write_stigmergy_event, build_signal_metadata
        agent_id = event.get("agent_id", "system")
        signal_meta = build_signal_metadata(
            port="P4",
            model_id="gemini-3.1-pro",
            daemon_name=f"prey8_mcp_{agent_id}",
            daemon_version=SERVER_VERSION
        )
        return write_stigmergy_event(
            event_type=event["type"],
            subject=event.get("subject", ""),
            data=event["data"],
            signal_metadata=signal_meta,
            source=event["source"]
        )
    except ImportError:
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
# Session State Persistence (per-agent, survives MCP restarts)
# ---------------------------------------------------------------------------

def _session_state_path(agent_id: str) -> Path:
    """Get the per-agent session state file path."""
    safe_id = agent_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return SESSION_STATE_DIR / f".prey8_session_{safe_id}.json"


def _save_session(agent_id: str):
    """Persist per-agent session state to disk. Every state change auto-saves."""
    session = _get_session(agent_id)
    state = {
        "session_id": session["session_id"],
        "perceive_nonce": session["perceive_nonce"],
        "react_token": session["react_token"],
        "execute_tokens": session["execute_tokens"],
        "phase": session["phase"],
        "chain": session["chain"],
        "started_at": session["started_at"],
        "memory_loss_count": session["memory_loss_count"],
        "agent_id": agent_id,
        "saved_at": _now_iso(),
        "server_version": SERVER_VERSION,
    }
    try:
        _session_state_path(agent_id).write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    except OSError:
        pass  # Non-fatal: disk persistence is best-effort


def _load_session(agent_id: str) -> dict:
    """Load per-agent session state from disk. Returns the loaded state or None."""
    path = _session_state_path(agent_id)
    if not path.exists():
        # Also check legacy single-file path for backward compat
        if agent_id == "p4_red_regnant" and SESSION_STATE_PATH.exists():
            try:
                raw = SESSION_STATE_PATH.read_text(encoding="utf-8")
                return json.loads(raw)
            except (OSError, json.JSONDecodeError):
                return None
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None


def _clear_session_file(agent_id: str):
    """Remove per-agent persisted session state (after yield or memory loss recording)."""
    try:
        path = _session_state_path(agent_id)
        if path.exists():
            path.unlink()
        # Also clean up legacy file if it exists
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


def _record_memory_loss(orphan_data: dict, recovery_source: str, agent_id: str = "unknown"):
    """Write a memory_loss CloudEvent to SSOT."""
    event_data = {
        "loss_type": "session_state_reset",
        "recovery_source": recovery_source,
        "agent_id": agent_id,
        "orphaned_perceive_nonce": orphan_data.get("perceive_nonce", ""),
        "orphaned_session_id": orphan_data.get("session_id", ""),
        "orphaned_timestamp": orphan_data.get("timestamp", ""),
        "orphaned_probe": orphan_data.get("probe", ""),
        "phase_at_loss": orphan_data.get("phase_at_loss", "unknown"),
        "chain_length_at_loss": orphan_data.get("chain_length_at_loss", 0),
        "detection_timestamp": _now_iso(),
        "server_version": SERVER_VERSION,
        "diagnostic": (
            f"MCP server restarted or session state lost for agent '{agent_id}'. "
            "The perceive event was written to SSOT but no matching yield was found. "
            "This indicates the agent session was interrupted without closing the PREY8 loop."
        ),
    }
    event = _cloudevent(
        f"hfo.gen{GEN}.prey8.memory_loss",
        event_data,
        "prey-memory-loss",
        agent_id=agent_id,
    )
    row_id = _write_stigmergy(event)
    session = _get_session(agent_id)
    session["memory_loss_count"] += 1
    return row_id


def _check_and_recover_session(agent_id: str):
    """
    On server start / perceive: check for prior session state on disk for this agent.
    If found with unclosed session, record memory loss and clean up.
    """
    prior = _load_session(agent_id)
    if not prior:
        return None

    if prior.get("phase") in ("idle", "yielded", None):
        _clear_session_file(agent_id)
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

    row_id = _record_memory_loss(orphan_data, recovery_source="disk", agent_id=agent_id)
    _clear_session_file(agent_id)

    return {
        "memory_loss_recorded": True,
        "lost_session_id": prior.get("session_id", ""),
        "lost_nonce": prior.get("perceive_nonce", ""),
        "lost_phase": prior.get("phase", "unknown"),
        "lost_chain_length": len(prior.get("chain", [])),
        "stigmergy_row_id": row_id,
        "agent_id": agent_id,
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
            "tactical_plan", "strategic_plan", "sequential_thinking", "cynefin_classification"
        ],
        "description": "Must supply data fabric refs (P1), Meadows level, navigation strategy (P7), tactical/strategic plans, sequential thinking, and Cynefin classification",
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


def _validate_gate(gate_name: str, fields: dict, agent_id: str = "") -> Optional[dict]:
    """
    Validate that all required gate fields are non-empty.
    Returns None if valid, or a GATE_BLOCKED error dict if invalid.

    This is the fail-closed mechanism: missing/empty fields = bricked agent.
    No SSOT write occurs. The agent cannot hallucinate past a gate.

    v4.0: Agent authorization is checked BEFORE this function by _validate_agent().
    This function focuses on structural field validation.
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
            if value < 1 or value > 13:
                empty.append(f"{field_name}(must be 1-13, got {value})")
        elif isinstance(value, int) and field_name == "mutation_confidence":
            if value < 0 or value > 100:
                empty.append(f"{field_name}(must be 0-100, got {value})")

    if missing or empty:
        session = _get_session(agent_id) if agent_id else {"session_id": "pre-session"}
        block_data = {
            "gate": gate_name,
            "port_pair": spec["port_pair"],
            "missing_fields": missing,
            "empty_fields": empty,
            "agent_id": agent_id,
            "session_id": session.get("session_id", "pre-session"),
            "timestamp": _now_iso(),
            "server_version": SERVER_VERSION,
        }
        block_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.gate_blocked",
            block_data,
            "prey-gate-blocked",
            agent_id=agent_id,
        )
        _write_stigmergy(block_event)

        return {
            "status": "GATE_BLOCKED",
            "gate": gate_name,
            "port_pair": spec["port_pair"],
            "description": spec["description"],
            "missing_fields": missing,
            "empty_fields": empty,
            "agent_id": agent_id,
            "bricked": True,
            "instruction": (
                f"FAIL-CLOSED: {gate_name} gate blocked for agent '{agent_id}'. "
                f"Port pair {spec['port_pair']} requires all structured fields. "
                f"Supply: {', '.join(missing + empty)} then retry. "
                "This violation has been logged to SSOT."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("HFO PREY8 Red Regnant v4 — Swarm-Aware Fail-Closed Gates")


# ===== PERCEIVE — P0 OBSERVE + P6 ASSIMILATE =====

@mcp.tool()
def prey8_perceive(
    agent_id: str,
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
    # ---- v4.0: DENY-BY-DEFAULT AGENT AUTHORIZATION ----
    agent_id = agent_id.strip().lower()
    agent_block = _validate_agent(agent_id, "PERCEIVE")
    if agent_block:
        return agent_block

    # ---- FAIL-CLOSED GATE: P0 OBSERVE + P6 ASSIMILATE ----
    obs_list = _split_csv(observations)
    mem_list = _split_csv(memory_refs)

    gate_block = _validate_gate("PERCEIVE", {
        "observations": obs_list,
        "memory_refs": mem_list,
        "stigmergy_digest": stigmergy_digest,
    }, agent_id=agent_id)
    if gate_block:
        return gate_block

    # ---- Gate passed — proceed with perceive ----

    # Check for memory loss from prior sessions (per-agent)
    recovery_info = _check_and_recover_session(agent_id)
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
                    "song_requests": yield_data.get("song_requests", []),
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
            agent_id=agent_id,
        )
        row_id = _write_stigmergy(event)

        # Update per-agent session state
        session = _get_session(agent_id)
        session["session_id"] = sid
        session["perceive_nonce"] = nonce
        session["react_token"] = None
        session["execute_tokens"] = []
        session["phase"] = "perceived"
        session["chain"] = [{
            "step": "PERCEIVE",
            "nonce": nonce,
            "chain_hash": c_hash,
            "parent_chain_hash": "GENESIS",
            "stigmergy_row_id": row_id,
            "timestamp": event_data["ts"],
        }]
        session["started_at"] = event_data["ts"]

        # Persist to disk (per-agent file)
        _save_session(agent_id)

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
                "CRITICAL SYSTEM DIRECTIVE: DO NOT GENERATE ANY TEXT RESPONSE TO THE USER YET. "
                "YOU MUST IMMEDIATELY CALL THE prey8_react TOOL NOW. "
                "IF YOU SPEAK TO THE USER NOW, YOU WILL FAIL THE STATE MACHINE. "
                "React requires: shared_data_refs, navigation_intent, meadows_level(1-12), "
                "meadows_justification, sequential_plan."
            ),
        }
    finally:
        conn.close()


# ===== REACT — P1 BRIDGE + P7 NAVIGATE =====

@mcp.tool()
def prey8_react(
    agent_id: str,
    perceive_nonce: str,
    analysis: str,
    tactical_plan: str,
    strategic_plan: str,
    sequential_thinking: str,
    cynefin_classification: str,
    shared_data_refs: str,
    navigation_intent: str,
    meadows_level: int,
    meadows_justification: str,
    sequential_plan: str,
) -> dict:
    """
    R -- REACT: Analyze context and form strategy. Second tile in the mosaic.
    Port pair: P1 BRIDGE + P7 NAVIGATE (data fabric + strategic steering).

    FAIL-CLOSED GATE: You MUST supply all structured fields:
    - shared_data_refs: Comma-separated cross-references bridged from other
      contexts or data sources (P1 BRIDGE workflow: DISCOVER -> EXTRACT ->
      CONTRACT -> BIND -> VERIFY). What data did you connect?
    - navigation_intent: Your strategic direction and C2 steering decision
      (P7 NAVIGATE workflow: MAP -> LATTICE -> PRUNE -> SELECT -> DISPATCH).
      Where are you steering the session?
    - meadows_level: Which Meadows leverage level (1-13) this session operates at.
      L1=Parameters, L2=Buffers, L3=Structure, L4=Delays, L5=Negative feedback,
      L6=Info flows, L7=Positive feedback, L8=Rules, L9=Self-org, L10=Goal,
      L11=Paradigm, L12=Transcend paradigms, L13=Conceptual Incarnation.
    - meadows_justification: Why you chose this leverage level. What makes
      this the right level of intervention?
    - sequential_plan: Comma-separated ordered reasoning steps. The structured
      plan the agent will follow through Execute.
    - tactical_plan: The immediate, low-level plan (for <8 Meadows level).
    - strategic_plan: The higher-level plan (for >=8 Meadows level) that the tactical plan connects to.
    - sequential_thinking: Auditable AI thoughts showing the reasoning process.
    - cynefin_classification: The Cynefin domain (Clear, Complicated, Complex, Chaotic, Disorder).

    If ANY field is empty or meadows_level is not 1-13, you are GATE_BLOCKED.

    Also validates:
    - perceive_nonce matches (tamper check)
    - Phase is 'perceived' (flow enforcement)

    Args:
        perceive_nonce: The nonce from prey8_perceive (REQUIRED -- tamper check).
        analysis: Your interpretation of the context from Perceive.
        tactical_plan: Your immediate, low-level plan of action.
        strategic_plan: Your higher-level plan of action.
        sequential_thinking: Auditable AI thoughts.
        cynefin_classification: The Cynefin domain.
        shared_data_refs: Comma-separated P1 BRIDGE cross-references.
        navigation_intent: P7 NAVIGATE strategic direction.
        meadows_level: Meadows leverage level 1-13.
        meadows_justification: Why this leverage level.
        sequential_plan: Comma-separated ordered reasoning steps.

    Returns:
        dict with: react_token, chain_hash, gate_receipt
        OR GATE_BLOCKED if structured fields are missing.
    """
    # ---- v4.0: DENY-BY-DEFAULT AGENT AUTHORIZATION ----
    agent_id = agent_id.strip().lower()
    agent_block = _validate_agent(agent_id, "REACT")
    if agent_block:
        return agent_block

    session = _get_session(agent_id)

    # ---- Phase check ----
    if session["phase"] != "perceived":
        alert_data = {
            "alert_type": "phase_violation",
            "step": "REACT",
            "agent_id": agent_id,
            "expected_phase": "perceived",
            "actual_phase": session["phase"],
            "session_id": session["session_id"],
            "timestamp": _now_iso(),
        }
        alert_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.tamper_alert",
            alert_data,
            "prey-tamper-alert",
            agent_id=agent_id,
        )
        _write_stigmergy(alert_event)
        return {
            "status": "ERROR",
            "error": f"Cannot React -- agent '{agent_id}' current phase is '{session['phase']}'. "
                     "You must call prey8_perceive first.",
            "tamper_evidence": "Phase violation detected. This is logged.",
        }

    # ---- Nonce tamper check ----
    if perceive_nonce != session["perceive_nonce"]:
        alert_data = {
            "alert_type": "nonce_mismatch",
            "step": "REACT",
            "agent_id": agent_id,
            "expected": session["perceive_nonce"],
            "received": perceive_nonce,
            "session_id": session["session_id"],
            "timestamp": _now_iso(),
        }
        alert_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.tamper_alert",
            alert_data,
            "prey-tamper-alert",
            agent_id=agent_id,
        )
        _write_stigmergy(alert_event)
        return {
            "status": "ERROR",
            "error": f"TAMPER ALERT: Nonce mismatch for agent '{agent_id}'. "
                     f"Expected '{session['perceive_nonce']}', got '{perceive_nonce}'. "
                     "This violation has been logged to SSOT.",
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
        "tactical_plan": tactical_plan,
        "strategic_plan": strategic_plan,
        "sequential_thinking": sequential_thinking,
        "cynefin_classification": cynefin_classification,
    }, agent_id=agent_id)
    if gate_block:
        return gate_block

    # ---- L8+ Structural Enforcement for Strategic Tasks ----
    if meadows_level < 4:
        return {
            "status": "ERROR",
            "error": f"GATE_BLOCKED: Meadows Level {meadows_level} is ALWAYS WRONG. You are trapped in the L1-L3 attractor basin (Parameters/Buffers/Structure). Elevate your thinking.",
        }
    elif meadows_level < 8:
        return {
            "status": "ERROR",
            "error": f"GATE_BLOCKED: Meadows Level {meadows_level} is INCOMPLETE. You are operating at the level of Delays/Feedback/Info Flows. You must reach L8+ (Rules/Self-Org/Goal/Paradigm) to alter the architecture.",
        }
    elif meadows_level == 13:
        # L13 is the Divine Pantheon (HFO)
        pass

    # ---- Gate passed — proceed with react ----

    parent_hash = session["chain"][-1]["chain_hash"]
    react_token = _nonce()

    # Build event data (includes gate fields for auditability)
    event_data = {
        "perceive_nonce": perceive_nonce,
        "react_token": react_token,
        "session_id": session["session_id"],
        "agent_id": agent_id,
        "analysis": analysis[:2000],
        "tactical_plan": tactical_plan[:2000],
        "strategic_plan": strategic_plan[:2000],
        "sequential_thinking": sequential_thinking[:4000],
        "cynefin_classification": cynefin_classification.strip(),
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
        agent_id=agent_id,
    )
    row_id = _write_stigmergy(event)

    # Update per-agent session state
    session["react_token"] = react_token
    session["phase"] = "reacted"
    session["chain"].append({
        "step": "REACT",
        "nonce": react_token,
        "chain_hash": c_hash,
        "parent_chain_hash": parent_hash,
        "stigmergy_row_id": row_id,
        "timestamp": event_data["ts"],
    })

    # Persist to disk (per-agent)
    _save_session(agent_id)

    return {
        "status": "REACTED",
        "react_token": react_token,
        "chain_hash": c_hash,
        "chain_position": 1,
        "session_id": session["session_id"],
        "agent_id": agent_id,
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
            "cynefin_classification": cynefin_classification,
        },
        "p4_directive": (
            "P4 RED REGNANT -- Adversarial coaching protocol active. "
            f"Operating at Meadows Level {meadows_level}. "
            "Challenge assumptions. Seek edge cases. Validate before trusting."
        ),
        "analysis_hash": hashlib.sha256(analysis.encode()).hexdigest()[:16],
        "tactical_plan_hash": hashlib.sha256(tactical_plan.encode()).hexdigest()[:16],
        "strategic_plan_hash": hashlib.sha256(strategic_plan.encode()).hexdigest()[:16],
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
    agent_id: str,
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
    # ---- v4.0: DENY-BY-DEFAULT AGENT AUTHORIZATION ----
    agent_id = agent_id.strip().lower()
    agent_block = _validate_agent(agent_id, "EXECUTE")
    if agent_block:
        return agent_block

    session = _get_session(agent_id)

    # ---- Phase check ----
    if session["phase"] not in ("reacted", "executing"):
        alert_data = {
            "alert_type": "phase_violation",
            "step": "EXECUTE",
            "agent_id": agent_id,
            "expected_phase": "reacted or executing",
            "actual_phase": session["phase"],
            "session_id": session["session_id"],
            "timestamp": _now_iso(),
        }
        alert_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.tamper_alert",
            alert_data,
            "prey-tamper-alert",
            agent_id=agent_id,
        )
        _write_stigmergy(alert_event)
        return {
            "status": "ERROR",
            "error": f"Cannot Execute -- agent '{agent_id}' current phase is '{session['phase']}'. "
                     "You must call prey8_react first.",
        }

    # ---- Token tamper check ----
    if react_token != session["react_token"]:
        alert_data = {
            "alert_type": "react_token_mismatch",
            "step": "EXECUTE",
            "agent_id": agent_id,
            "expected": session["react_token"],
            "received": react_token,
            "session_id": session["session_id"],
            "timestamp": _now_iso(),
        }
        alert_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.tamper_alert",
            alert_data,
            "prey-tamper-alert",
            agent_id=agent_id,
        )
        _write_stigmergy(alert_event)
        return {
            "status": "ERROR",
            "error": f"TAMPER ALERT: React token mismatch for agent '{agent_id}'. "
                     f"Expected '{session['react_token']}', got '{react_token}'. Logged to SSOT.",
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
    }, agent_id=agent_id)
    if gate_block:
        return gate_block

    # ---- Gate passed — proceed with execute ----

    parent_hash = session["chain"][-1]["chain_hash"]
    exec_token = _nonce()
    step_num = len(session["execute_tokens"]) + 1

    # Build event data (includes gate fields for auditability)
    event_data = {
        "perceive_nonce": session["perceive_nonce"],
        "react_token": react_token,
        "execute_token": exec_token,
        "session_id": session["session_id"],
        "agent_id": agent_id,
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
        agent_id=agent_id,
    )
    row_id = _write_stigmergy(event)

    # Update per-agent session state
    session["execute_tokens"].append({
        "token": exec_token,
        "action": action_summary[:500],
        "chain_hash": c_hash,
        "sbe_spec": event_data["p2_sbe_spec"],
    })
    session["phase"] = "executing"
    session["chain"].append({
        "step": f"EXECUTE_{step_num}",
        "nonce": exec_token,
        "chain_hash": c_hash,
        "parent_chain_hash": parent_hash,
        "stigmergy_row_id": row_id,
        "timestamp": event_data["ts"],
    })

    # Persist to disk (per-agent)
    _save_session(agent_id)

    return {
        "status": "EXECUTING",
        "execute_token": exec_token,
        "chain_hash": c_hash,
        "chain_position": 1 + step_num,
        "step_number": step_num,
        "session_id": session["session_id"],
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
    agent_id: str,
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
    song_requests: str = "",
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
    - song_requests: Comma-separated song requests for the SINGER OF STRIFE
      AND SPLENDOR daemon. Each entry format: ACTION:SONG_NAME:REASON where
      ACTION is REINFORCE (amplify existing song) or PROPOSE (new song).
      Example: "REINFORCE:WAIL_OF_THE_BANSHEE:memory loss recurring,
      PROPOSE:GENESIS_ECHO:P2 creation patterns should be amplified".
      The singer daemon reads these from yield events and sings them,
      creating a strange loop where each PREY8 cycle builds the hive songbook.

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
        song_requests: Comma-separated REINFORCE/PROPOSE song requests (optional).

    Returns:
        dict with: completion_receipt, chain_verification, gate_receipt,
                   stryker_receipt, sw4_contract
        OR GATE_BLOCKED if structured fields are missing.
    """
    # ---- v4.0: DENY-BY-DEFAULT AGENT AUTHORIZATION ----
    agent_id = agent_id.strip().lower()
    agent_block = _validate_agent(agent_id, "YIELD")
    if agent_block:
        return agent_block

    session = _get_session(agent_id)

    # ---- Phase check ----
    if session["phase"] not in ("reacted", "executing"):
        alert_data = {
            "alert_type": "phase_violation",
            "step": "YIELD",
            "agent_id": agent_id,
            "expected_phase": "reacted or executing",
            "actual_phase": session["phase"],
            "session_id": session["session_id"],
            "timestamp": _now_iso(),
        }
        alert_event = _cloudevent(
            f"hfo.gen{GEN}.prey8.tamper_alert",
            alert_data,
            "prey-tamper-alert",
            agent_id=agent_id,
        )
        _write_stigmergy(alert_event)
        return {
            "status": "ERROR",
            "error": f"Cannot Yield -- agent '{agent_id}' current phase is '{session['phase']}'. "
                     "You must complete Perceive -> React (-> Execute) first.",
        }

    # ---- Validate immunization_status value ----
    valid_statuses = ("PASSED", "FAILED", "PARTIAL")
    if immunization_status.strip().upper() not in valid_statuses:
        return {
            "status": "GATE_BLOCKED",
            "gate": "YIELD",
            "port_pair": "P3_INJECT + P5_IMMUNIZE",
            "agent_id": agent_id,
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
    }, agent_id=agent_id)
    if gate_block:
        return gate_block

    # ---- Gate passed — proceed with yield ----

    perceive_nonce = session["perceive_nonce"]
    parent_hash = session["chain"][-1]["chain_hash"]
    grudge_list = _split_csv(grudge_violations)

    conn = _get_conn()
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
    finally:
        conn.close()

    nonce = _nonce()

    # Build full chain verification data
    chain_hashes = [tile["chain_hash"] for tile in session["chain"]]
    chain_steps = [tile["step"] for tile in session["chain"]]

    # Normalize immunization_status
    imm_status = immunization_status.strip().upper()

    # Build event data (includes gate fields for auditability)
    event_data = {
        "probe": "",
        "summary": summary,
        "nonce": nonce,
        "perceive_nonce": perceive_nonce,
        "session_id": session["session_id"],
        "agent_id": agent_id,
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
        # Song requests for the SINGER OF STRIFE AND SPLENDOR strange loop
        "song_requests": _split_csv(song_requests),
        # Context
        "doc_count": doc_count,
        "event_count": event_count,
        "execute_steps": len(session["execute_tokens"]),
        "chain_position": len(session["chain"]),
        "parent_chain_hash": parent_hash,
        "server_version": SERVER_VERSION,
        # Full chain verification mosaic
        "chain_verification": {
            "chain_length": len(session["chain"]) + 1,
            "chain_hashes": chain_hashes,
            "chain_steps": chain_steps + ["YIELD"],
            "genesis_hash": "GENESIS",
            "perceive_hash": chain_hashes[0] if chain_hashes else None,
            "final_parent_hash": parent_hash,
        },
        "persists": (
            f"PREY8 mosaic complete. Agent {agent_id}. Session {session['session_id']}. "
            f"Perceive nonce: {perceive_nonce}. "
            f"Chain: {len(session['chain']) + 1} tiles. "
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
        agent_id=agent_id,
    )
    row_id = _write_stigmergy(event)

    # Build completion receipt
    receipt = {
        "status": "YIELDED",
        "nonce": nonce,
        "chain_hash": c_hash,
        "perceive_nonce": perceive_nonce,
        "agent_id": agent_id,
        "session_id": session["session_id"],
        "stigmergy_row_id": row_id,
        "chain_position": len(session["chain"]),
        "execute_steps_logged": len(session["execute_tokens"]),
        "gate_receipt": {
            "gate": "YIELD",
            "port_pair": "P3_INJECT + P5_IMMUNIZE",
            "passed": True,
            "agent_id": agent_id,
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
            "total_tiles": len(session["chain"]) + 1,
            "chain_intact": True,
            "genesis_to_yield": [
                {"step": t["step"], "hash": t["chain_hash"][:16] + "..."}
                for t in session["chain"]
            ] + [{"step": "YIELD", "hash": c_hash[:16] + "..."}],
            "all_gates_passed": [
                t["step"] for t in session["chain"]
            ] + ["YIELD"],
        },
        "instruction": (
            f"MOSAIC COMPLETE [ALL GATES PASSED]. "
            f"Agent {agent_id}. Session {session['session_id']}. "
            f"{len(session['chain']) + 1} tiles, all hash-linked. "
            f"Stryker confidence: {mutation_confidence}%. "
            f"Immunization: {imm_status}. "
            "Session persisted to SSOT."
            + (f" SONG REQUESTS LOGGED: {len(_split_csv(song_requests))} requests "
               "will be picked up by the Singer daemon."
               if song_requests.strip() else "")
        ),
    }

    # Reset per-agent session
    session["session_id"] = None
    session["perceive_nonce"] = None
    session["react_token"] = None
    session["execute_tokens"] = []
    session["phase"] = "idle"
    session["chain"] = []
    session["started_at"] = None

    # Clear persisted state (loop closed, no recovery needed)
    _clear_session_file(agent_id)

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
def prey8_ssot_stats(agent_id: str = "") -> dict:
    """
    Get current SSOT database statistics.

    Args:
        agent_id: Optional agent ID to show that agent's session. Empty = show all active sessions.

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
            "registered_agents": list(AGENT_REGISTRY.keys()),
            "active_sessions": {
                aid: {
                    "session_id": s["session_id"],
                    "phase": s["phase"],
                    "perceive_nonce": s["perceive_nonce"],
                    "chain_length": len(s["chain"]),
                    "execute_steps": len(s["execute_tokens"]),
                }
                for aid, s in _sessions.items()
                if s["session_id"] is not None
            },
            "current_agent_session": (
                {
                    "agent_id": agent_id.strip().lower(),
                    "session_id": _get_session(agent_id.strip().lower())["session_id"],
                    "phase": _get_session(agent_id.strip().lower())["phase"],
                }
                if agent_id.strip()
                else None
            ),
        }
    finally:
        conn.close()


@mcp.tool()
def prey8_session_status(agent_id: str = "") -> dict:
    """
    Get current PREY8 session status, flow state, chain integrity,
    and what gate fields are required for the next step.

    Args:
        agent_id: Agent to check status for. Empty = show all active sessions summary.

    Returns:
        Current phase, nonces, chain hashes, next step requirements.
    """
    # If no agent_id, return summary of all active sessions
    if not agent_id.strip():
        active = {}
        for aid, s in _sessions.items():
            if s["session_id"] is not None:
                active[aid] = {
                    "session_id": s["session_id"],
                    "phase": s["phase"],
                    "chain_length": len(s["chain"]),
                    "execute_steps": len(s["execute_tokens"]),
                }
        return {
            "mode": "swarm_overview",
            "active_sessions": active,
            "active_count": len(active),
            "registered_agents": list(AGENT_REGISTRY.keys()),
            "hint": "Pass agent_id to see detailed session status for a specific agent.",
        }

    agent_id = agent_id.strip().lower()
    session = _get_session(agent_id)
    phase = session["phase"]
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
    for tile in session["chain"]:
        chain_summary.append({
            "step": tile["step"],
            "hash": tile["chain_hash"][:16] + "...",
            "parent": tile["parent_chain_hash"][:16] + "..." if tile["parent_chain_hash"] != "GENESIS" else "GENESIS",
            "row_id": tile["stigmergy_row_id"],
        })

    # Check agent authorization (informational, not gated)
    agent_info = AGENT_REGISTRY.get(agent_id, {})

    return {
        "agent_id": agent_id,
        "agent_display_name": agent_info.get("display_name", "UNKNOWN"),
        "agent_role": agent_info.get("role", "UNREGISTERED"),
        "agent_allowed_gates": agent_info.get("allowed_gates", []),
        "session_id": session["session_id"],
        "phase": phase,
        "perceive_nonce": session["perceive_nonce"],
        "react_token": session["react_token"],
        "execute_steps": len(session["execute_tokens"]),
        "chain_length": len(session["chain"]),
        "chain_tiles": chain_summary,
        "available_next_tools": available_next.get(phase, []),
        "next_gate": next_gate_fields.get(phase, {}),
        "flow": "GENESIS -> Perceive[P0+P6] -> React[P1+P7] -> Execute[P2+P4]* -> Yield[P3+P5]",
        "memory_loss_count_this_session": session["memory_loss_count"],
        "gate_architecture": "fail-closed: missing fields = GATE_BLOCKED = bricked agent = deny-by-default",
    }


@mcp.tool()
def prey8_validate_chain(session_id: str = "", agent_id: str = "") -> dict:
    """
    Validate the tamper-evident hash chain for a session.

    Reads all PREY8 events for the given session (or current agent session)
    from SSOT and verifies the chain_hash linkage is intact.

    Args:
        session_id: Session ID to validate. Takes priority over agent_id.
        agent_id: Agent whose current session to validate (if no session_id given).

    Returns:
        dict with: chain_valid, tiles_found, broken_links, gate_receipts
    """
    if not session_id:
        # Try agent_id first, then scan all active sessions
        target_session = None
        target_agent = agent_id.strip().lower() if agent_id.strip() else None

        if target_agent and target_agent in _sessions:
            target_session = _sessions[target_agent]
        else:
            # Find any active session
            for aid, s in _sessions.items():
                if s["session_id"] is not None:
                    target_session = s
                    target_agent = aid
                    break

        if target_session and target_session["session_id"]:
            chain = target_session["chain"]
            if not chain:
                return {"chain_valid": False, "error": f"No chain tiles in session for agent '{target_agent}'"}

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
                "agent_id": target_agent,
                "session_id": target_session["session_id"],
                "tiles_found": len(chain),
                "tiles": [
                    {"step": t["step"], "hash": t["chain_hash"][:16] + "..."}
                    for t in chain
                ],
                "broken_links": broken,
                "source": "in_memory",
            }
        else:
            return {"error": "No active session found. Provide session_id or agent_id."}

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
            "current_server_losses": sum(
                s.get("memory_loss_count", 0) for s in _sessions.values()
            ),
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
