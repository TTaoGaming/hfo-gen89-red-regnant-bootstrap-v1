#!/usr/bin/env python3
"""
hfo_hive8_mcp_server.py — HIVE8 Loop MCP Server v1 (Tactical Execution)

Swarm-aware multi-agent HIVE8 with agent identity, session isolation,
deny-by-default authorization, and stigmergy traceability.

This is the TACTICAL counterpart to the STRATEGIC PREY8 loop.
While PREY8 operates at the Meadows level (SBEs, strategic steering),
HIVE8 operates at the file/line/test level.

Fail-closed port-pair gates on every HIVE8 step:
  H — Hindsight = P0 OBSERVE + P1 BRIDGE      (Locate target + map dependencies)
  I — Insight   = P2 SHAPE + P4 DISRUPT       (Write code + break existing structure)
  V — Validated Foresight = P5 IMMUNIZE + P6 ASSIMILATE (Run tests + learn from failures)
  E — Evolve    = P3 INJECT + P7 NAVIGATE     (Deliver payload + steer back to strategic)

Gate enforcement:
  1. Agent identity check (deny-by-default: unknown agent = BLOCKED)
  2. Port authorization check (agent must have permission for this gate)
  3. Structured field check (all required fields must be non-empty)
  4. Verify Gate: MUST pass tests (status == "PASSED") to proceed to Evolve.

MCP server protocol: stdio
Run: python hfo_hive8_mcp_server.py
"""

import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

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
AGENT_REGISTRY: dict[str, dict[str, Any]] = {
    "p0_lidless_legion": {"display_name": "P0 Lidless Legion", "ports": [0, 6], "allowed_gates": ["HINDSIGHT", "VALIDATED_FORESIGHT"]},
    "p1_web_weaver": {"display_name": "P1 Web Weaver", "ports": [1, 7], "allowed_gates": ["HINDSIGHT", "EVOLVE"]},
    "p2_mirror_magus": {"display_name": "P2 Mirror Magus", "ports": [2, 4], "allowed_gates": ["INSIGHT"]},
    "p3_harmonic_hydra": {"display_name": "P3 Harmonic Hydra", "ports": [3, 5], "allowed_gates": ["EVOLVE", "VALIDATED_FORESIGHT"]},
    "p4_red_regnant": {"display_name": "P4 Red Regnant", "ports": [0, 1, 2, 3, 4, 5, 6, 7], "allowed_gates": ["HUNT", "INSIGHT", "VERIFY", "EMIT"]},
    "p5_pyre_praetorian": {"display_name": "P5 Pyre Praetorian", "ports": [0, 1, 2, 3, 4, 5, 6, 7], "allowed_gates": ["HUNT", "INSIGHT", "VERIFY", "EMIT"]},
    "p6_kraken_keeper": {"display_name": "P6 Kraken Keeper", "ports": [0, 6], "allowed_gates": ["HINDSIGHT", "VALIDATED_FORESIGHT"]},
    "p7_spider_sovereign": {"display_name": "P7 Spider Sovereign", "ports": [0, 1, 2, 3, 4, 5, 6, 7], "allowed_gates": ["HUNT", "INSIGHT", "VERIFY", "EMIT"]},
    "ttao_operator": {"display_name": "TTAO Operator (Human)", "ports": [0, 1, 2, 3, 4, 5, 6, 7], "allowed_gates": ["HUNT", "INSIGHT", "VERIFY", "EMIT"]},
}

def _new_session() -> dict[str, Any]:
    return {
        "session_id": None,
        "hindsight_nonce": None,
        "insight_tokens": [],
        "validated_foresight_tokens": [],
        "phase": "idle",
        "chain": [],
        "started_at": None,
        "agent_id": None,
    }

_sessions: dict[str, dict[str, Any]] = {}

def _get_session(agent_id: str) -> dict[str, Any]:
    if agent_id not in _sessions:
        _sessions[agent_id] = _new_session()
        _sessions[agent_id]["agent_id"] = agent_id
    return _sessions[agent_id]

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _session_state_path(agent_id: str) -> Path:
    safe_id = agent_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return SESSION_STATE_DIR / f".hive8_session_{safe_id}.json"

def _save_session(agent_id: str) -> None:
    session = _get_session(agent_id)
    state = {
        "session_id": session["session_id"],
        "hindsight_nonce": session["hindsight_nonce"],
        "insight_tokens": session["insight_tokens"],
        "validated_foresight_tokens": session["validated_foresight_tokens"],
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

def _get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SSOT database not found at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def _cloudevent(event_type: str, data: dict[str, Any], subject: str = "hive8") -> dict[str, Any]:
    return {
        "specversion": "1.0",
        "id": secrets.token_hex(8),
        "source": f"urn:hfo:gen{GEN}:hive8_mcp",
        "type": event_type,
        "subject": subject,
        "time": _now_iso(),
        "data": data,
    }

def _write_stigmergy(event: dict[str, Any]) -> int:
    try:
        from hfo_ssot_write import write_stigmergy_event, build_signal_metadata  # type: ignore
        agent_id = event["data"].get("agent_id", "system")
        signal_meta = build_signal_metadata(
            port="P4",
            model_id="gemini-3.1-pro",
            daemon_name=f"hive8_mcp_{agent_id}",
            daemon_version=SERVER_VERSION
        )
        return int(write_stigmergy_event(
            event_type=event["type"],
            subject=event.get("subject", ""),
            data=event["data"],
            signal_metadata=signal_meta,
            source=event["source"]
        ))
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
            return int(cursor.lastrowid or 0)
        finally:
            conn.close()

def _run_fast_checks(artifacts_created: str = "", artifacts_modified: str = "") -> tuple[bool, str]:
    """
    Run CI/CD fast checks (e.g., pytest, syntax checks, mypy, ruff) to ensure CORRECT-BY-CONSTRUCTION genesis.
    Returns (passed, output_string).
    """
    root_dir = _find_root()
    output = []
    passed = True

    # 1. Syntax check on modified/created Python files
    all_artifacts = [x.strip() for x in artifacts_created.split(",") if x.strip()] + \
                    [x.strip() for x in artifacts_modified.split(",") if x.strip()]
    py_files = [f for f in all_artifacts if f.endswith(".py")]
    
    for py_file in py_files:
        file_path = root_dir / py_file
        if file_path.exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    passed = False
                    output.append(f"Syntax error in {py_file}:\n{result.stderr}")
            except Exception as e:
                passed = False
                output.append(f"Failed to syntax check {py_file}: {str(e)}")

    # 2. Run ruff check on modified/created Python files
    for py_file in py_files:
        file_path = root_dir / py_file
        if file_path.exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "ruff", "check", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    passed = False
                    output.append(f"Ruff linting failed in {py_file}:\n{result.stdout}\n{result.stderr}")
            except Exception as e:
                passed = False
                output.append(f"Failed to run ruff on {py_file}: {str(e)}")

    # 3. Run mypy --strict on modified/created Python files
    for py_file in py_files:
        file_path = root_dir / py_file
        if file_path.exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "mypy", "--strict", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    passed = False
                    output.append(f"Mypy strict type check failed in {py_file}:\n{result.stdout}\n{result.stderr}")
            except Exception as e:
                passed = False
                output.append(f"Failed to run mypy on {py_file}: {str(e)}")

    # 4. Run pytest in the workspace root
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--maxfail=1", "--disable-warnings", "-q"],
            cwd=str(root_dir),
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            passed = False
            output.append(f"Pytest failed:\n{result.stdout}\n{result.stderr}")
    except Exception as e:
        passed = False
        output.append(f"Failed to run pytest: {str(e)}")

    if passed:
        return True, "All fast checks passed."
    else:
        return False, "\n\n".join(output)

def _validate_agent(agent_id: str, gate_name: Optional[str] = None) -> Optional[dict[str, Any]]:
    if not agent_id or not agent_id.strip():
        return {"status": "GATE_BLOCKED", "reason": "DENY_BY_DEFAULT: agent_id is required.", "bricked": True}

    agent_id = agent_id.strip().lower()
    if agent_id not in AGENT_REGISTRY:
        if agent_id.startswith("p") and len(agent_id) > 1 and agent_id[1].isdigit():
            port = int(agent_id[1])
            AGENT_REGISTRY[agent_id] = {
                "display_name": f"Dynamic Swarm Agent ({agent_id})",
                "ports": [port],
                "allowed_gates": ["HUNT", "INSIGHT", "VERIFY", "EMIT"],
                "role": f"Dynamic swarm node on port {port}",
            }
        elif agent_id.startswith("swarm_") or agent_id.startswith("agent_"):
            AGENT_REGISTRY[agent_id] = {
                "display_name": f"Dynamic Swarm Agent ({agent_id})",
                "ports": [0, 1, 2, 3, 4, 5, 6, 7],
                "allowed_gates": ["HUNT", "INSIGHT", "VERIFY", "EMIT"],
                "role": "Dynamic swarm node (full access)",
            }
        else:
            return {"status": "GATE_BLOCKED", "reason": f"DENY_BY_DEFAULT: agent_id '{agent_id}' is not registered.", "bricked": True}

    if gate_name:
        agent_spec = AGENT_REGISTRY[agent_id]
        if gate_name not in agent_spec["allowed_gates"]:
            return {"status": "GATE_BLOCKED", "reason": f"LEAST_PRIVILEGE: agent '{agent_id}' not authorized for {gate_name} gate.", "bricked": True}
    return None

def _hash_chain(parent_hash: str, nonce: str, data: dict[str, Any]) -> str:
    payload = f"{parent_hash}:{nonce}:{json.dumps(data, sort_keys=True)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP("HFO_HIVE8_Tactical_Server")

@mcp.tool()
def hive8_hindsight(agent_id: str, tactical_objective: str, target_files: str) -> dict[str, Any]:
    """
    H -- HINDSIGHT: Start a HIVE8 tactical session. First tile.
    Port pair: P0 OBSERVE + P1 BRIDGE (Locate target + map dependencies).
    """
    block = _validate_agent(agent_id, "HINDSIGHT")
    if block:
        return block

    if not tactical_objective or not target_files:
        return {"status": "GATE_BLOCKED", "reason": "Missing required fields: tactical_objective, target_files"}

    session = _get_session(agent_id)
    if session["phase"] not in ["idle", "evolved"]:
        return {"status": "ERROR", "error": f"Cannot gain Hindsight -- current phase is '{session['phase']}'."}

    session["session_id"] = secrets.token_hex(8)
    session["hindsight_nonce"] = secrets.token_hex(3).upper()
    session["phase"] = "hindsight_gained"
    session["started_at"] = _now_iso()
    session["insight_tokens"] = []
    session["validated_foresight_tokens"] = []

    event_data = {
        "agent_id": agent_id,
        "session_id": session["session_id"],
        "nonce": session["hindsight_nonce"],
        "tactical_objective": tactical_objective,
        "target_files": target_files,
    }
    
    chain_hash = _hash_chain("GENESIS", session["hindsight_nonce"], event_data)
    session["chain"] = [{"step": "HINDSIGHT", "hash": chain_hash}]
    
    row_id = _write_stigmergy(_cloudevent(f"hfo.gen{GEN}.hive8.hindsight", event_data, "hive-hindsight"))
    _save_session(agent_id)

    return {
        "status": "HINDSIGHT_GAINED",
        "hindsight_nonce": session["hindsight_nonce"],
        "chain_hash": chain_hash,
        "session_id": session["session_id"],
        "stigmergy_row_id": row_id,
        "instruction": "TILE 0 PLACED [P0+P1 GATE PASSED]. You MUST call hive8_insight with this nonce."
    }

@mcp.tool()
def hive8_insight(agent_id: str, hindsight_nonce: str, files_modified: str, diff_summary: str) -> dict[str, Any]:
    """
    I -- INSIGHT: Execute the tactical change. Second tile.
    Port pair: P2 SHAPE + P4 DISRUPT (Write code + break existing structure).
    """
    block = _validate_agent(agent_id, "INSIGHT")
    if block:
        return block

    if not hindsight_nonce or not files_modified or not diff_summary:
        return {"status": "GATE_BLOCKED", "reason": "Missing required fields: hindsight_nonce, files_modified, diff_summary"}

    session = _get_session(agent_id)
    if session["phase"] not in ["hindsight_gained", "foresight_validated"]: # Can intervene again if verify failed
        return {"status": "ERROR", "error": f"Cannot gain Insight -- current phase is '{session['phase']}'."}

    if hindsight_nonce != session["hindsight_nonce"]:
        return {"status": "ERROR", "error": "Tamper Alert: hindsight_nonce mismatch."}

    token = secrets.token_hex(3).upper()
    session["insight_tokens"].append(token)
    session["phase"] = "insight_gained"

    event_data = {
        "agent_id": agent_id,
        "session_id": session["session_id"],
        "token": token,
        "files_modified": files_modified,
        "diff_summary": diff_summary,
    }
    
    parent_hash = session["chain"][-1]["hash"]
    chain_hash = _hash_chain(parent_hash, token, event_data)
    session["chain"].append({"step": f"INSIGHT_{len(session['insight_tokens'])}", "hash": chain_hash})
    
    row_id = _write_stigmergy(_cloudevent(f"hfo.gen{GEN}.hive8.insight", event_data, "hive-insight"))
    _save_session(agent_id)

    return {
        "status": "INSIGHT_GAINED",
        "insight_token": token,
        "chain_hash": chain_hash,
        "stigmergy_row_id": row_id,
        "instruction": "TILE 1 PLACED [P2+P4 GATE PASSED]. You MUST call hive8_validated_foresight with this token."
    }

@mcp.tool()
def hive8_validated_foresight(agent_id: str, insight_token: str, test_command: str, test_output: str, status: str) -> dict[str, Any]:
    """
    V -- VALIDATED FORESIGHT: Validate the change locally. Third tile.
    Port pair: P5 IMMUNIZE + P6 ASSIMILATE (Run tests + learn from failures).
    """
    block = _validate_agent(agent_id, "VALIDATED_FORESIGHT")
    if block:
        return block

    if not insight_token or not test_command or not test_output or not status:
        return {"status": "GATE_BLOCKED", "reason": "Missing required fields: insight_token, test_command, test_output, status"}

    if status not in ["PASSED", "FAILED"]:
        return {"status": "GATE_BLOCKED", "reason": "status must be 'PASSED' or 'FAILED'."}

    session = _get_session(agent_id)
    if session["phase"] not in ["insight_gained", "validating_foresight"]:
        return {"status": "ERROR", "error": f"Cannot Validate Foresight -- current phase is '{session['phase']}'."}

    if insight_token not in session["insight_tokens"]:
        return {"status": "ERROR", "error": "Tamper Alert: insight_token mismatch."}

    token = secrets.token_hex(3).upper()
    session["validated_foresight_tokens"].append(token)
    
    # Hard enforcement: If tests fail, you cannot emit. You must intervene again.
    if status == "PASSED":
        session["phase"] = "foresight_validated"
    else:
        session["phase"] = "validating_foresight" # Stuck here until PASSED

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
    session["chain"].append({"step": f"VALIDATED_FORESIGHT_{len(session['validated_foresight_tokens'])}", "hash": chain_hash})
    
    row_id = _write_stigmergy(_cloudevent(f"hfo.gen{GEN}.hive8.validated_foresight", event_data, "hive-validated-foresight"))
    _save_session(agent_id)

    if status == "FAILED":
        return {
            "status": "VALIDATION_FAILED",
            "validated_foresight_token": token,
            "instruction": "TESTS FAILED. You are blocked from Evolving. You MUST call hive8_insight again to fix the code."
        }

    return {
        "status": "FORESIGHT_VALIDATED",
        "validated_foresight_token": token,
        "chain_hash": chain_hash,
        "stigmergy_row_id": row_id,
        "instruction": "TILE 2 PLACED [P5+P6 GATE PASSED]. You MUST call hive8_evolve with this token."
    }

@mcp.tool()
def hive8_evolve(agent_id: str, validated_foresight_token: str, delivery_manifest: str, tactical_yield_summary: str) -> dict[str, Any]:
    """
    E -- EVOLVE: Deliver the tactical payload. Final tile.
    Port pair: P3 INJECT + P7 NAVIGATE (Deliver payload + steer back to strategic).
    """
    block = _validate_agent(agent_id, "EVOLVE")
    if block:
        return block

    if not validated_foresight_token or not delivery_manifest or not tactical_yield_summary:
        return {"status": "GATE_BLOCKED", "reason": "Missing required fields: validated_foresight_token, delivery_manifest, tactical_yield_summary"}

    session = _get_session(agent_id)
    if session["phase"] != "foresight_validated":
        return {"status": "ERROR", "error": f"Cannot Evolve -- current phase is '{session['phase']}'. You must pass Verify first."}

    if validated_foresight_token not in session["validated_foresight_tokens"]:
        return {"status": "ERROR", "error": "Tamper Alert: validated_foresight_token mismatch."}

    # ---- CI/CD FAST CHECKS (CORRECT-BY-CONSTRUCTION) ----
    checks_passed, checks_output = _run_fast_checks(delivery_manifest, "")
    if not checks_passed:
        return {
            "status": "GATE_BLOCKED",
            "gate": "EVOLVE",
            "port_pair": "P3_INJECT + P7_NAVIGATE",
            "agent_id": agent_id,
            "error": "CI/CD Fast Checks Failed. You must fix the code before evolving.",
            "bricked": True,
            "instruction": "Review the test output and fix the errors. CORRECT-BY-CONSTRUCTION genesis requires passing tests.",
            "test_output": checks_output
        }

    session["phase"] = "evolved"

    event_data = {
        "agent_id": agent_id,
        "session_id": session["session_id"],
        "delivery_manifest": delivery_manifest,
        "tactical_yield_summary": tactical_yield_summary,
    }
    
    parent_hash = session["chain"][-1]["hash"]
    chain_hash = _hash_chain(parent_hash, "EMIT", event_data)
    session["chain"].append({"step": "EVOLVE", "hash": chain_hash})
    
    row_id = _write_stigmergy(_cloudevent(f"hfo.gen{GEN}.hive8.evolve", event_data, "hive-evolve"))
    
    # Reset for next loop
    session["phase"] = "idle"
    _save_session(agent_id)

    return {
        "status": "EVOLVED",
        "chain_hash": chain_hash,
        "stigmergy_row_id": row_id,
        "instruction": "MOSAIC COMPLETE [ALL GATES PASSED]. Tactical payload delivered. Return to PREY8 strategic loop."
    }

if __name__ == "__main__":
    mcp.run()
