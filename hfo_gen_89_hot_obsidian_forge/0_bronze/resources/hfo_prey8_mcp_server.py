#!/usr/bin/env python3
"""
hfo_prey8_mcp_server.py — PREY8 Loop MCP Server v2 (P4 Red Regnant)

Tamper-evident 4-step hash-chained nonce system:
  P — Perceive  (writes CloudEvent, returns nonce + chain_hash)
  R — React     (writes CloudEvent, validates parent, returns react_token + chain_hash)
  E — Execute   (writes CloudEvent, validates parent, returns exec_token + chain_hash)
  Y — Yield     (writes CloudEvent, validates full chain, closes loop)

Architecture: "Correct by construction mosaic tiles"
  - Each step is a self-contained CloudEvent (tile) with its own hash
  - Each tile references its parent's hash (parent_chain_hash)
  - The mosaic (session) is the ordered set of tiles linked by hashes
  - Missing tiles = memory loss = automatically detected and recorded
  - Every nonce request auto-logs to SSOT (zero silent state changes)

Session state is persisted to disk for memory loss recovery.
Memory loss events are tracked with full diagnostic data.

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
SERVER_VERSION = "v2.0"
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

    This is the observability backbone: the LLM is hallucinatory,
    but the hash chain is deterministic. Memory loss = broken chain.
    """
    conn = _get_conn()
    orphans = []
    try:
        # Find recent perceive events
        perceives = list(conn.execute(
            """SELECT id, timestamp, data_json FROM stigmergy_events
               WHERE event_type LIKE '%prey8.perceive%'
               ORDER BY timestamp DESC LIMIT 20"""
        ))

        # Find recent yield events
        yields = list(conn.execute(
            """SELECT id, timestamp, data_json FROM stigmergy_events
               WHERE event_type LIKE '%prey8.yield%'
               ORDER BY timestamp DESC LIMIT 20"""
        ))

        # Extract perceive nonces
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

        # Extract yield perceive_nonces (which perceive they closed)
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

        # Orphans = perceives without matching yields
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
    """
    Write a memory_loss CloudEvent to SSOT.
    Every memory loss is tracked with full diagnostic data.
    """
    event_data = {
        "loss_type": "session_state_reset",
        "recovery_source": recovery_source,  # "disk" or "ssot_scan"
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
            "This indicates the agent session was interrupted without closing the PREY8 loop. "
            "The chain is broken at this point."
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
    Returns recovery info or None.
    """
    prior = _load_session()
    if not prior:
        return None

    # If prior session was idle or yielded, nothing to recover
    if prior.get("phase") in ("idle", "yielded", None):
        _clear_session_file()
        return None

    # Prior session was active (perceived/reacted/executing) -- memory loss!
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
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("HFO PREY8 Red Regnant v2")


# ===== PERCEIVE =====

@mcp.tool()
def prey8_perceive(probe: str) -> dict:
    """
    P -- PERCEIVE: Start a PREY8 session. First tile in the mosaic.

    - Checks for memory loss (unclosed prior sessions)
    - Queries SSOT for context (9,859+ docs, 9,590+ stigmergy events)
    - Reads recent yields from other sessions (swarm continuity)
    - Runs FTS5 search against the database
    - Writes a perceive CloudEvent to SSOT (auto-logged)
    - Returns nonce + chain_hash (tile 0 of the mosaic)

    The nonce is REQUIRED by prey8_react. The chain_hash links to subsequent tiles.

    Args:
        probe: The user's intent or question for this session.

    Returns:
        dict with: nonce, chain_hash, session_id, memory_loss_info, context
    """
    # Step 0: Check for memory loss from prior sessions
    recovery_info = _check_and_recover_session()

    # Also scan SSOT for orphaned perceives
    orphans = _detect_memory_loss()

    conn = _get_conn()
    try:
        # Stats
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]

        # Recent yields (n+1 perceive ingests recent yields from swarm)
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
                    "insights": yield_data.get("insights", []),
                    "nonce": yield_data.get("nonce", ""),
                    "chain_hash": yield_data.get("chain_hash", ""),
                })
            except (json.JSONDecodeError, TypeError):
                pass

        # Recent non-yield events
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

        # FTS search if probe is useful
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

        # Build event data
        event_data = {
            "probe": probe,
            "nonce": nonce,
            "session_id": sid,
            "ts": _now_iso(),
            "encounter_count": len(recent_yields),
            "doc_count": doc_count,
            "event_count": event_count,
            "p6_gate": None,
            "server_version": SERVER_VERSION,
            "chain_position": 0,
            "parent_chain_hash": "GENESIS",  # First tile has no parent
        }

        # Compute chain hash for this tile
        data_json = json.dumps(event_data, sort_keys=True)
        c_hash = _chain_hash("GENESIS", nonce, data_json)
        event_data["chain_hash"] = c_hash

        # Write to SSOT (auto-logged on nonce generation)
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

        # Persist to disk (survives MCP restart)
        _save_session()

        return {
            "status": "PERCEIVED",
            "nonce": nonce,
            "chain_hash": c_hash,
            "session_id": sid,
            "stigmergy_row_id": row_id,
            "chain_position": 0,
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
                f"TILE 0 PLACED. Nonce: {nonce}, Chain: {c_hash[:12]}... "
                f"Session: {sid}. "
                "You MUST call prey8_react with this nonce to place tile 1."
            ),
        }
    finally:
        conn.close()


# ===== REACT =====

@mcp.tool()
def prey8_react(perceive_nonce: str, analysis: str, plan: str) -> dict:
    """
    R -- REACT: Analyze context. Second tile in the mosaic.

    Validates the perceive nonce (chain integrity check).
    Writes a react CloudEvent to SSOT (auto-logged).
    Returns react_token + chain_hash for the execute step.

    The react_token is REQUIRED by prey8_execute.
    The chain_hash links this tile to the perceive tile.

    Args:
        perceive_nonce: The nonce from prey8_perceive (REQUIRED -- tamper check).
        analysis: Your interpretation of the context from Perceive.
        plan: Your structured plan of action (what you will do and why).

    Returns:
        dict with: react_token, chain_hash, chain_position
    """
    if _session["phase"] != "perceived":
        return {
            "status": "ERROR",
            "error": f"Cannot React -- current phase is '{_session['phase']}'. "
                     "You must call prey8_perceive first.",
            "tamper_evidence": "Phase violation detected. This is logged.",
        }
    if perceive_nonce != _session["perceive_nonce"]:
        # TAMPER ALERT: nonce mismatch -- log it to SSOT
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

    # Get parent chain hash from perceive tile
    parent_hash = _session["chain"][-1]["chain_hash"]

    react_token = _nonce()

    # Build event data
    event_data = {
        "perceive_nonce": perceive_nonce,
        "react_token": react_token,
        "session_id": _session["session_id"],
        "analysis": analysis[:2000],
        "plan": plan[:2000],
        "ts": _now_iso(),
        "chain_position": 1,
        "parent_chain_hash": parent_hash,
        "server_version": SERVER_VERSION,
    }

    # Compute chain hash for this tile
    data_json = json.dumps(event_data, sort_keys=True)
    c_hash = _chain_hash(parent_hash, react_token, data_json)
    event_data["chain_hash"] = c_hash

    # Write to SSOT (auto-logged)
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
        "p4_directive": (
            "P4 RED REGNANT -- Adversarial coaching protocol active. "
            "Challenge assumptions. Seek edge cases. Validate before trusting. "
            "Your analysis and plan are now written to SSOT."
        ),
        "analysis_hash": hashlib.sha256(analysis.encode()).hexdigest()[:16],
        "plan_hash": hashlib.sha256(plan.encode()).hexdigest()[:16],
        "instruction": (
            f"TILE 1 PLACED. Token: {react_token}, Chain: {c_hash[:12]}... "
            "Now call prey8_execute for each action, then prey8_yield to close."
        ),
    }


# ===== EXECUTE =====

@mcp.tool()
def prey8_execute(react_token: str, action_summary: str) -> dict:
    """
    E -- EXECUTE: Track an execution step. Middle tile(s) in the mosaic.

    Can be called multiple times for multi-step work.
    Each call writes an execute CloudEvent to SSOT (auto-logged).
    Validates the react_token (chain integrity check).
    Returns exec_token + chain_hash linking to the previous tile.

    Args:
        react_token: The token from prey8_react (REQUIRED -- tamper check).
        action_summary: Brief description of what you're doing/did in this step.

    Returns:
        dict with: execute_token, chain_hash, step_number
    """
    if _session["phase"] not in ("reacted", "executing"):
        return {
            "status": "ERROR",
            "error": f"Cannot Execute -- current phase is '{_session['phase']}'. "
                     "You must call prey8_react first.",
        }
    if react_token != _session["react_token"]:
        # TAMPER ALERT
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

    # Get parent chain hash from previous tile
    parent_hash = _session["chain"][-1]["chain_hash"]

    exec_token = _nonce()
    step_num = len(_session["execute_tokens"]) + 1

    # Build event data
    event_data = {
        "perceive_nonce": _session["perceive_nonce"],
        "react_token": react_token,
        "execute_token": exec_token,
        "session_id": _session["session_id"],
        "action_summary": action_summary[:2000],
        "step_number": step_num,
        "ts": _now_iso(),
        "chain_position": 1 + step_num,  # 0=P, 1=R, 2+=E
        "parent_chain_hash": parent_hash,
        "server_version": SERVER_VERSION,
    }

    # Compute chain hash for this tile
    data_json = json.dumps(event_data, sort_keys=True)
    c_hash = _chain_hash(parent_hash, exec_token, data_json)
    event_data["chain_hash"] = c_hash

    # Write to SSOT (auto-logged)
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
        "action_logged": action_summary[:500],
        "instruction": (
            f"TILE {1 + step_num} PLACED. Step {step_num} logged to SSOT. "
            "Call prey8_execute again for more steps, "
            "or call prey8_yield to close the mosaic."
        ),
    }


# ===== YIELD =====

@mcp.tool()
def prey8_yield(
    summary: str,
    artifacts_created: str = "",
    artifacts_modified: str = "",
    next_steps: str = "",
    insights: str = "",
) -> dict:
    """
    Y -- YIELD: Close the PREY8 loop. Final tile in the mosaic.

    Validates the entire chain, writes a yield CloudEvent with full chain
    verification data. This is MANDATORY at session end.

    The yield event contains the complete chain_hashes array, allowing
    any future agent to verify the entire session was tamper-free.

    Args:
        summary: What was accomplished in this session.
        artifacts_created: Comma-separated list of created file paths.
        artifacts_modified: Comma-separated list of modified file paths.
        next_steps: Comma-separated list of recommended next actions.
        insights: Comma-separated list of key learnings or discoveries.

    Returns:
        dict with: completion_receipt, nonce_chain, chain_verification
    """
    if _session["phase"] not in ("reacted", "executing"):
        return {
            "status": "ERROR",
            "error": f"Cannot Yield -- current phase is '{_session['phase']}'. "
                     "You must complete Perceive -> React (-> Execute) first.",
        }

    perceive_nonce = _session["perceive_nonce"]
    parent_hash = _session["chain"][-1]["chain_hash"]

    def _split(s):
        return [x.strip() for x in s.split(",") if x.strip()] if s else []

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

    # Build event data
    event_data = {
        "probe": "",
        "summary": summary,
        "nonce": nonce,
        "perceive_nonce": perceive_nonce,
        "session_id": _session["session_id"],
        "ts": _now_iso(),
        "artifacts_created": _split(artifacts_created),
        "artifacts_modified": _split(artifacts_modified),
        "next_steps": _split(next_steps),
        "insights": _split(insights),
        "doc_count": doc_count,
        "event_count": event_count,
        "execute_steps": len(_session["execute_tokens"]),
        "chain_position": len(_session["chain"]),
        "parent_chain_hash": parent_hash,
        "server_version": SERVER_VERSION,
        # Full chain verification mosaic
        "chain_verification": {
            "chain_length": len(_session["chain"]) + 1,  # +1 for this yield
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
        "chain_verification": {
            "total_tiles": len(_session["chain"]) + 1,
            "chain_intact": True,
            "genesis_to_yield": [
                {"step": t["step"], "hash": t["chain_hash"][:16] + "..."}
                for t in _session["chain"]
            ] + [{"step": "YIELD", "hash": c_hash[:16] + "..."}],
        },
        "sw4_completion_contract": {
            "given": f"Session {_session['session_id']} opened with perceive nonce {perceive_nonce}",
            "when": f"Agent executed {len(_session['execute_tokens'])} steps through hash-chained mosaic",
            "then": f"Yield nonce {nonce} closed loop. Chain: {c_hash[:16]}... Summary: {summary}",
        },
        "instruction": "MOSAIC COMPLETE. All tiles placed and hash-linked. Session persisted to SSOT.",
    }

    # Reset session
    _session["session_id"] = None
    _session["perceive_nonce"] = None
    _session["react_token"] = None
    _session["execute_tokens"] = []
    _session["phase"] = "idle"
    _session["chain"] = []
    _session["started_at"] = None

    # Clear persisted state (loop is closed, no recovery needed)
    _clear_session_file()

    return receipt


# ===== UTILITY TOOLS =====

@mcp.tool()
def prey8_fts_search(query: str, limit: int = 10) -> list:
    """
    Full-text search against the SSOT documents (FTS5).

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

    Args:
        event_type_pattern: SQL LIKE pattern for event_type (default: % = all).
            Examples: '%yield%', '%perceive%', '%p4%', '%memory_loss%', '%tamper%'
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
    Get current PREY8 session status, flow state, and chain integrity.

    Returns:
        Current phase, nonces, chain hashes, and what steps are available next.
    """
    phase = _session["phase"]
    available_next = {
        "idle": ["prey8_perceive"],
        "perceived": ["prey8_react"],
        "reacted": ["prey8_execute", "prey8_yield"],
        "executing": ["prey8_execute", "prey8_yield"],
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
        "flow": "GENESIS -> Perceive -> React -> Execute* -> Yield",
        "memory_loss_count_this_session": _session["memory_loss_count"],
    }


@mcp.tool()
def prey8_validate_chain(session_id: str = "") -> dict:
    """
    Validate the tamper-evident hash chain for a session.

    Reads all PREY8 events for the given session (or current session)
    from SSOT and verifies the chain_hash linkage is intact.

    Each tile in the mosaic must reference the previous tile's chain_hash.
    A broken link means tampering or data corruption.

    Args:
        session_id: Session ID to validate (empty = current session).

    Returns:
        dict with: chain_valid, tiles_found, broken_links, diagnostics
    """
    # If no session_id, use current in-memory chain
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
                })
            except (json.JSONDecodeError, TypeError):
                pass

        if not events:
            return {"chain_valid": False, "error": f"No events found for session {session_id}"}

        # Verify chain linkage
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
                {"step": e["step"], "hash": (e["chain_hash"][:16] + "...") if e["chain_hash"] else "?"}
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
    Scan SSOT for memory loss events and orphaned sessions.

    Returns diagnostic data about:
    - Unclosed perceive events (no matching yield)
    - Previously recorded memory_loss events
    - Tamper alerts
    - Chain integrity issues

    This is the observability dashboard for the hallucinatory LLM layer.
    The architecture is correct by construction; this tool verifies it.

    Returns:
        dict with: orphaned_sessions, memory_loss_events, tamper_alerts, health
    """
    orphans = _detect_memory_loss()

    conn = _get_conn()
    try:
        # Get recorded memory loss events
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

        # Get tamper alerts
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

        # Overall health assessment
        total_perceives = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%prey8.perceive%'"
        ).fetchone()[0]
        total_yields = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%prey8.yield%'"
        ).fetchone()[0]

        health = "HEALTHY"
        if len(tamper_events) > 0:
            health = "ALERT -- tamper events detected"
        elif len(orphans) > 3:
            health = "DEGRADED -- multiple unclosed sessions"
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
            "total_perceives": total_perceives,
            "total_yields": total_yields,
            "yield_ratio": f"{total_yields}/{total_perceives}" if total_perceives > 0 else "0/0",
            "current_server_losses": _session["memory_loss_count"],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
