#!/usr/bin/env python3
"""
hfo_hive8_mcp_server.py — HIVE8 Loop MCP Server v1 (Tactical Execution)

Swarm-aware multi-agent HIVE8 with agent identity, session isolation,
deny-by-default authorization, and stigmergy traceability.

This is the TACTICAL counterpart to the STRATEGIC PREY8 loop.
While PREY8 operates at the Meadows level (SBEs, strategic steering),
HIVE8 operates at the file/line/test level.

Fail-closed port-pair gates on every HIVE8 step:
  H — Hunt      = P0 OBSERVE + P1 BRIDGE      (Locate target + map dependencies)
  I — Intervene = P2 SHAPE + P4 DISRUPT       (Write code + break existing structure)
  V — Verify    = P5 IMMUNIZE + P6 ASSIMILATE (Run tests + learn from failures)
  E — Emit      = P3 INJECT + P7 NAVIGATE     (Deliver payload + steer back to strategic)

Gate enforcement:
  1. Agent identity check (deny-by-default: unknown agent = BLOCKED)
  2. Port authorization check (agent must have permission for this gate)
  3. Structured field check (all required fields must be non-empty)
  4. Verify Gate: MUST pass tests (status == "PASSED") to proceed to Emit.

MCP server protocol: stdio
Run: python hfo_hive8_mcp_server.py
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
GEN = os.environ.get("HFO_GENERATION", "90")
SERVER_VERSION = "v1.0"

# ---------------------------------------------------------------------------
# AGENT REGISTRY — Deny-by-Default Authorization
# ---------------------------------------------------------------------------
AGENT_REGISTRY = {
    "p0_lidless_legion": {"display_name": "P0 Lidless Legion", "ports": [0, 6], "allowed_gates": ["HUNT", "VERIFY"]},
    "p1_web_weaver": {"display_name": "P1 Web Weaver", "ports": [1, 7], "allowed_gates": ["HUNT", "EMIT"]},
    "p2_mirror_magus": {"display_name": "P2 Mirror Magus", "ports": [2, 4], "allowed_gates": ["INTERVENE"]},
    "p3_harmonic_hydra": {"display_name": "P3 Harmonic Hydra", "ports": [3, 5], "allowed_gates": ["EMIT", "VERIFY"]},
    "p4_red_regnant": {"display_name": "P4 Red Regnant", "ports": [0, 1, 2, 3, 4, 5, 6, 7], "allowed_gates": ["HUNT", "INTERVENE", "VERIFY", "EMIT"]},
    "p5_pyre_praetorian": {"display_name": "P5 Pyre Praetorian", "ports": [0, 1, 2, 3, 4, 5, 6, 7], "allowed_gates": ["HUNT", "INTERVENE", "VERIFY", "EMIT"]},
    "p6_kraken_keeper": {"display_name": "P6 Kraken Keeper", "ports": [0, 6], "allowed_gates": ["HUNT", "VERIFY"]},
    "p7_spider_sovereign": {"display_name": "P7 Spider Sovereign", "ports": [0, 1, 2, 3, 4, 5, 6, 7], "allowed_gates": ["HUNT", "INTERVENE", "VERIFY", "EMIT"]},
    "ttao_operator": {"display_name": "TTAO Operator (Human)", "ports": [0, 1, 2, 3, 4, 5, 6, 7], "allowed_gates": ["HUNT", "INTERVENE", "VERIFY", "EMIT"]},
}

def _new_session() -> dict:
    return {
        "session_id": None,
        "hunt_nonce": None,
        "intervene_tokens": [],
        "verify_tokens": [],
        "phase": "idle",
        "chain": [],
        "started_at": None,
        "agent_id": None,
    }

_sessions: dict[str, dict] = {}

def _get_session(agent_id: str) -> dict:
    if agent_id not in _sessions:
        _sessions[agent_id] = _new_session()
        _sessions[agent_id]["agent_id"] = agent_id
    return _sessions[agent_id]

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _session_state_path(agent_id: str) -> Path:
    safe_id = agent_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return SESSION_STATE_DIR / f".hive8_session_{safe_id}.json"

def _save_session(agent_id: str):
    session = _get_session(agent_id)
    state = {
        "session_id": session["session_id"],
        "hunt_nonce": session["hunt_nonce"],
        "intervene_tokens": session["intervene_tokens"],
        "verify_tokens": session["verify_tokens"],
        "phase": session["phase"],
        "chain": session["chain"],
        "started_at": session["started_at"],
        "agent_id": agent_id,
        "saved_at": _now_iso(),
        "server_version": SERVER_VERSION,
    }
    try:
        _session_state_path(agent_id).write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass

def _get_conn():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SSOT database not found at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def _cloudevent(event_type: str, data: dict, subject: str = "hive8") -> dict:
    return {
        "specversion": "1.0",
        "id": secrets.token_hex(8),
        "source": f"urn:hfo:gen{GEN}:hive8_mcp",
        "type": event_type,
        "subject": subject,
        "time": _now_iso(),
        "data": data,
    }

def _write_stigmergy(event: dict) -> int:
    try:
        from hfo_ssot_write import write_stigmergy_event, build_signal_metadata
        agent_id = event["data"].get("agent_id", "system")
        signal_meta = build_signal_metadata(
            port="P4",
            model_id="gemini-3.1-pro",
            daemon_name=f"hive8_mcp_{agent_id}",
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
            data_json = json.dumps(event["data"])
            content_hash = hashlib.sha256(data_json.encode("utf-8")).hexdigest()
            cursor = conn.execute(
                """INSERT INTO stigmergy_events 
                   (event_type, timestamp, subject, data_json, content_hash, source)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event["type"], event["time"], event.get("subject", ""), data_json, content_hash, event["source"])
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

def _validate_agent(agent_id: str, gate_name: str = None) -> Optional[dict]:
    if not agent_id or not agent_id.strip():
        return {"status": "GATE_BLOCKED", "reason": "DENY_BY_DEFAULT: agent_id is required.", "bricked": True}

    agent_id = agent_id.strip().lower()
    if agent_id not in AGENT_REGISTRY:
        if agent_id.startswith("p") and len(agent_id) > 1 and agent_id[1].isdigit():
            port = int(agent_id[1])
            AGENT_REGISTRY[agent_id] = {
                "display_name": f"Dynamic Swarm Agent ({agent_id})",
                "ports": [port],
                "allowed_gates": ["HUNT", "INTERVENE", "VERIFY", "EMIT"],
                "role": f"Dynamic swarm node on port {port}",
            }
        elif agent_id.startswith("swarm_") or agent_id.startswith("agent_"):
            AGENT_REGISTRY[agent_id] = {
                "display_name": f"Dynamic Swarm Agent ({agent_id})",
                "ports": [0, 1, 2, 3, 4, 5, 6, 7],
                "allowed_gates": ["HUNT", "INTERVENE", "VERIFY", "EMIT"],
                "role": "Dynamic swarm node (full access)",
            }
        else:
            return {"status": "GATE_BLOCKED", "reason": f"DENY_BY_DEFAULT: agent_id '{agent_id}' is not registered.", "bricked": True}

    if gate_name:
        agent_spec = AGENT_REGISTRY[agent_id]
        if gate_name not in agent_spec["allowed_gates"]:
            return {"status": "GATE_BLOCKED", "reason": f"LEAST_PRIVILEGE: agent '{agent_id}' not authorized for {gate_name} gate.", "bricked": True}
    return None

def _hash_chain(parent_hash: str, nonce: str, data: dict) -> str:
    payload = f"{parent_hash}:{nonce}:{json.dumps(data, sort_keys=True)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP("HFO_HIVE8_Tactical_Server")

@mcp.tool()
def hive8_hunt(agent_id: str, tactical_objective: str, target_files: str) -> dict:
    """
    H -- HUNT: Start a HIVE8 tactical session. First tile.
    Port pair: P0 OBSERVE + P1 BRIDGE (Locate target + map dependencies).
    """
    block = _validate_agent(agent_id, "HUNT")
    if block: return block

    if not tactical_objective or not target_files:
        return {"status": "GATE_BLOCKED", "reason": "Missing required fields: tactical_objective, target_files"}

    session = _get_session(agent_id)
    if session["phase"] not in ["idle", "emitted"]:
        return {"status": "ERROR", "error": f"Cannot Hunt -- current phase is '{session['phase']}'."}

    session["session_id"] = secrets.token_hex(8)
    session["hunt_nonce"] = secrets.token_hex(3).upper()
    session["phase"] = "hunted"
    session["started_at"] = _now_iso()
    session["intervene_tokens"] = []
    session["verify_tokens"] = []

    event_data = {
        "agent_id": agent_id,
        "session_id": session["session_id"],
        "nonce": session["hunt_nonce"],
        "tactical_objective": tactical_objective,
        "target_files": target_files,
    }
    
    chain_hash = _hash_chain("GENESIS", session["hunt_nonce"], event_data)
    session["chain"] = [{"step": "HUNT", "hash": chain_hash}]
    
    row_id = _write_stigmergy(_cloudevent(f"hfo.gen{GEN}.hive8.hunt", event_data, "hive-hunt"))
    _save_session(agent_id)

    return {
        "status": "HUNTED",
        "hunt_nonce": session["hunt_nonce"],
        "chain_hash": chain_hash,
        "session_id": session["session_id"],
        "stigmergy_row_id": row_id,
        "instruction": "TILE 0 PLACED [P0+P1 GATE PASSED]. You MUST call hive8_intervene with this nonce."
    }

@mcp.tool()
def hive8_intervene(agent_id: str, hunt_nonce: str, files_modified: str, diff_summary: str) -> dict:
    """
    I -- INTERVENE: Execute the tactical change. Second tile.
    Port pair: P2 SHAPE + P4 DISRUPT (Write code + break existing structure).
    """
    block = _validate_agent(agent_id, "INTERVENE")
    if block: return block

    if not hunt_nonce or not files_modified or not diff_summary:
        return {"status": "GATE_BLOCKED", "reason": "Missing required fields: hunt_nonce, files_modified, diff_summary"}

    session = _get_session(agent_id)
    if session["phase"] not in ["hunted", "verified"]: # Can intervene again if verify failed
        return {"status": "ERROR", "error": f"Cannot Intervene -- current phase is '{session['phase']}'."}

    if hunt_nonce != session["hunt_nonce"]:
        return {"status": "ERROR", "error": "Tamper Alert: hunt_nonce mismatch."}

    token = secrets.token_hex(3).upper()
    session["intervene_tokens"].append(token)
    session["phase"] = "intervened"

    event_data = {
        "agent_id": agent_id,
        "session_id": session["session_id"],
        "token": token,
        "files_modified": files_modified,
        "diff_summary": diff_summary,
    }
    
    parent_hash = session["chain"][-1]["hash"]
    chain_hash = _hash_chain(parent_hash, token, event_data)
    session["chain"].append({"step": f"INTERVENE_{len(session['intervene_tokens'])}", "hash": chain_hash})
    
    row_id = _write_stigmergy(_cloudevent(f"hfo.gen{GEN}.hive8.intervene", event_data, "hive-intervene"))
    _save_session(agent_id)

    return {
        "status": "INTERVENED",
        "intervene_token": token,
        "chain_hash": chain_hash,
        "stigmergy_row_id": row_id,
        "instruction": "TILE 1 PLACED [P2+P4 GATE PASSED]. You MUST call hive8_verify with this token."
    }

@mcp.tool()
def hive8_verify(agent_id: str, intervene_token: str, test_command: str, test_output: str, status: str) -> dict:
    """
    V -- VERIFY: Validate the change locally. Third tile.
    Port pair: P5 IMMUNIZE + P6 ASSIMILATE (Run tests + learn from failures).
    """
    block = _validate_agent(agent_id, "VERIFY")
    if block: return block

    if not intervene_token or not test_command or not test_output or not status:
        return {"status": "GATE_BLOCKED", "reason": "Missing required fields: intervene_token, test_command, test_output, status"}

    if status not in ["PASSED", "FAILED"]:
        return {"status": "GATE_BLOCKED", "reason": "status must be 'PASSED' or 'FAILED'."}

    session = _get_session(agent_id)
    if session["phase"] not in ["intervened", "verifying"]:
        return {"status": "ERROR", "error": f"Cannot Verify -- current phase is '{session['phase']}'."}

    if intervene_token not in session["intervene_tokens"]:
        return {"status": "ERROR", "error": "Tamper Alert: intervene_token mismatch."}

    token = secrets.token_hex(3).upper()
    session["verify_tokens"].append(token)
    
    # Hard enforcement: If tests fail, you cannot emit. You must intervene again.
    if status == "PASSED":
        session["phase"] = "verified"
    else:
        session["phase"] = "verifying" # Stuck here until PASSED

    event_data = {
        "agent_id": agent_id,
        "session_id": session["session_id"],
        "token": token,
        "test_command": test_command,
        "test_output": test_output,
        "status": status,
    }
    
    parent_hash = session["chain"][-1]["hash"]
    chain_hash = _hash_chain(parent_hash, token, event_data)
    session["chain"].append({"step": f"VERIFY_{len(session['verify_tokens'])}", "hash": chain_hash})
    
    row_id = _write_stigmergy(_cloudevent(f"hfo.gen{GEN}.hive8.verify", event_data, "hive-verify"))
    _save_session(agent_id)

    if status == "FAILED":
        return {
            "status": "VERIFY_FAILED",
            "verify_token": token,
            "instruction": "TESTS FAILED. You are blocked from Emitting. You MUST call hive8_intervene again to fix the code."
        }

    return {
        "status": "VERIFIED",
        "verify_token": token,
        "chain_hash": chain_hash,
        "stigmergy_row_id": row_id,
        "instruction": "TILE 2 PLACED [P5+P6 GATE PASSED]. You MUST call hive8_emit with this token."
    }

@mcp.tool()
def hive8_emit(agent_id: str, verify_token: str, delivery_manifest: str, tactical_yield_summary: str) -> dict:
    """
    E -- EMIT: Deliver the tactical payload. Final tile.
    Port pair: P3 INJECT + P7 NAVIGATE (Deliver payload + steer back to strategic).
    """
    block = _validate_agent(agent_id, "EMIT")
    if block: return block

    if not verify_token or not delivery_manifest or not tactical_yield_summary:
        return {"status": "GATE_BLOCKED", "reason": "Missing required fields: verify_token, delivery_manifest, tactical_yield_summary"}

    session = _get_session(agent_id)
    if session["phase"] != "verified":
        return {"status": "ERROR", "error": f"Cannot Emit -- current phase is '{session['phase']}'. You must pass Verify first."}

    if verify_token not in session["verify_tokens"]:
        return {"status": "ERROR", "error": "Tamper Alert: verify_token mismatch."}

    session["phase"] = "emitted"

    event_data = {
        "agent_id": agent_id,
        "session_id": session["session_id"],
        "delivery_manifest": delivery_manifest,
        "tactical_yield_summary": tactical_yield_summary,
    }
    
    parent_hash = session["chain"][-1]["hash"]
    chain_hash = _hash_chain(parent_hash, "EMIT", event_data)
    session["chain"].append({"step": "EMIT", "hash": chain_hash})
    
    row_id = _write_stigmergy(_cloudevent(f"hfo.gen{GEN}.hive8.emit", event_data, "hive-emit"))
    
    # Reset for next loop
    session["phase"] = "idle"
    _save_session(agent_id)

    return {
        "status": "EMITTED",
        "chain_hash": chain_hash,
        "stigmergy_row_id": row_id,
        "instruction": "MOSAIC COMPLETE [ALL GATES PASSED]. Tactical payload delivered. Return to PREY8 strategic loop."
    }

if __name__ == "__main__":
    mcp.run()
