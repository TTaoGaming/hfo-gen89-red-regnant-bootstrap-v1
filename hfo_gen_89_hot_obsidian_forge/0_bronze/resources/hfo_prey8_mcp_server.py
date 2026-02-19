#!/usr/bin/env python3
"""
hfo_prey8_mcp_server.py — PREY8 Loop MCP Server (P4 Red Regnant)

A structurally-enforced 4-step workflow MCP server:
  P — Perceive  (session start: query SSOT, read stigmergy, orient)
  R — React     (analyze context with P4 Red Regnant persona, form plan)
  E — Execute   (track work, log activity)
  Y — Yield     (session end: write stigmergy, close loop)

Each step returns a token required by the next step, enforcing sequential flow.
The n+1 Perceive ingests recent Yields from the HFO swarm.

Run: uv run --with "mcp[cli]" python hfo_prey8_mcp_server.py
  or: python hfo_prey8_mcp_server.py  (after pip install "mcp[cli]")

MCP server protocol: stdio
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
GEN = os.environ.get("HFO_GENERATION", "89")
OPERATOR = os.environ.get("HFO_OPERATOR", "TTAO")
SECRET = os.environ.get("HFO_SECRET", "prey8_mcp_default_secret")

# In-memory session state (tokens for flow enforcement)
_session = {
    "perceive_nonce": None,
    "react_token": None,
    "execute_tokens": [],
    "phase": "idle",  # idle → perceived → reacted → executing → yielded
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nonce() -> str:
    return secrets.token_hex(3).upper()

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sign(data: str) -> str:
    return hashlib.sha256(f"{SECRET}:{data}".encode()).hexdigest()

def _trace_ids():
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    return trace_id, span_id

def _get_conn():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SSOT database not found at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def _cloudevent(event_type: str, data: dict, subject: str = "prey8") -> dict:
    trace_id, span_id = _trace_ids()
    ts = _now_iso()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": f"hfo_prey8_mcp_gen{GEN}_v1",
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
    }
    event["signature"] = _sign(json.dumps(data, sort_keys=True))
    return event

def _write_stigmergy(event: dict) -> int:
    """Write a CloudEvent to stigmergy_events. Returns row id."""
    conn = _get_conn()
    try:
        content_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
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
                content_hash,
            ),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return row_id
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("HFO PREY8 Red Regnant")

# ===== PERCEIVE =====

@mcp.tool()
def prey8_perceive(probe: str) -> dict:
    """
    P — PERCEIVE: Start a PREY8 session.

    Queries the SSOT database for context. Reads recent stigmergy events
    (including recent Yields from other sessions for swarm continuity).
    Writes a perceive CloudEvent. Returns a nonce required by subsequent steps.

    Args:
        probe: The user's intent or question for this session.

    Returns:
        dict with: nonce, doc_count, event_count, recent_yields, recent_events, fts_results
    """
    conn = _get_conn()
    try:
        # Stats
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]

        # Recent yields (n+1 perceive ingests recent yields from swarm)
        recent_yields = []
        for row in conn.execute(
            """SELECT id, event_type, timestamp, substr(data_json, 1, 2000)
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
            # Sanitize for FTS5
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
                    pass  # FTS query error — non-fatal

        # Generate nonce and write perceive event
        nonce = _nonce()
        event_data = {
            "probe": probe,
            "nonce": nonce,
            "ts": _now_iso(),
            "encounter_count": len(recent_yields),
            "doc_count": doc_count,
            "event_count": event_count,
            "p6_gate": None,
        }
        event = _cloudevent(f"hfo.gen{GEN}.prey8.perceive", event_data, "prey-perceive")
        row_id = _write_stigmergy(event)

        # Update session state
        _session["perceive_nonce"] = nonce
        _session["react_token"] = None
        _session["execute_tokens"] = []
        _session["phase"] = "perceived"

        return {
            "status": "PERCEIVED",
            "nonce": nonce,
            "stigmergy_row_id": row_id,
            "doc_count": doc_count,
            "event_count": event_count + 1,
            "recent_yields": recent_yields,
            "recent_events": recent_events,
            "fts_results": fts_results,
            "instruction": (
                f"Perceive complete. Nonce: {nonce}. "
                "You MUST now call prey8_react with this nonce before doing work."
            ),
        }
    finally:
        conn.close()


# ===== REACT =====

@mcp.tool()
def prey8_react(perceive_nonce: str, analysis: str, plan: str) -> dict:
    """
    R — REACT: Analyze context with P4 Red Regnant persona.

    Validates the perceive nonce, records your analysis and plan.
    Returns a react_token required by prey8_execute.

    Args:
        perceive_nonce: The nonce from prey8_perceive (REQUIRED).
        analysis: Your interpretation of the context from Perceive.
        plan: Your structured plan of action (what you will do and why).

    Returns:
        dict with: react_token, p4_directive
    """
    if _session["phase"] != "perceived":
        return {
            "status": "ERROR",
            "error": f"Cannot React — current phase is '{_session['phase']}'. "
                     "You must call prey8_perceive first.",
        }
    if perceive_nonce != _session["perceive_nonce"]:
        return {
            "status": "ERROR",
            "error": f"Nonce mismatch. Expected '{_session['perceive_nonce']}', got '{perceive_nonce}'.",
        }

    react_token = _nonce()
    _session["react_token"] = react_token
    _session["phase"] = "reacted"

    return {
        "status": "REACTED",
        "react_token": react_token,
        "p4_directive": (
            "P4 RED REGNANT — You are operating under adversarial coaching protocol. "
            "Challenge assumptions. Seek edge cases. Validate before trusting. "
            "Your analysis has been logged. Proceed to prey8_execute with react_token."
        ),
        "analysis_logged": analysis[:500],
        "plan_logged": plan[:500],
        "instruction": (
            f"React complete. Token: {react_token}. "
            "Now call prey8_execute for each action, then prey8_yield to close."
        ),
    }


# ===== EXECUTE =====

@mcp.tool()
def prey8_execute(react_token: str, action_summary: str) -> dict:
    """
    E — EXECUTE: Track an execution step.

    Can be called multiple times for multi-step work. Each call logs the action.
    Validates the react_token from prey8_react.

    Args:
        react_token: The token from prey8_react (REQUIRED).
        action_summary: Brief description of what you're doing/did in this step.

    Returns:
        dict with: execute_token, step_number
    """
    if _session["phase"] not in ("reacted", "executing"):
        return {
            "status": "ERROR",
            "error": f"Cannot Execute — current phase is '{_session['phase']}'. "
                     "You must call prey8_react first.",
        }
    if react_token != _session["react_token"]:
        return {
            "status": "ERROR",
            "error": f"React token mismatch. Expected '{_session['react_token']}', got '{react_token}'.",
        }

    exec_token = _nonce()
    _session["execute_tokens"].append({"token": exec_token, "action": action_summary})
    _session["phase"] = "executing"

    return {
        "status": "EXECUTING",
        "execute_token": exec_token,
        "step_number": len(_session["execute_tokens"]),
        "action_logged": action_summary[:500],
        "instruction": (
            "Execution step logged. You may call prey8_execute again for more steps, "
            "or call prey8_yield to close the PREY8 loop."
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
    Y — YIELD: Close the PREY8 loop. Write stigmergy back to SSOT.

    Validates the session chain, writes a yield CloudEvent with summary,
    artifacts, next steps, and insights. This is MANDATORY at session end.

    Args:
        summary: What was accomplished in this session.
        artifacts_created: Comma-separated list of created file paths.
        artifacts_modified: Comma-separated list of modified file paths.
        next_steps: Comma-separated list of recommended next actions.
        insights: Comma-separated list of key learnings or discoveries.

    Returns:
        dict with: completion_receipt, nonce_chain
    """
    if _session["phase"] not in ("reacted", "executing"):
        return {
            "status": "ERROR",
            "error": f"Cannot Yield — current phase is '{_session['phase']}'. "
                     "You must complete Perceive → React (→ Execute) first.",
        }

    perceive_nonce = _session["perceive_nonce"]

    # Parse comma-separated lists
    def _split(s):
        return [x.strip() for x in s.split(",") if x.strip()] if s else []

    conn = _get_conn()
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
    finally:
        conn.close()

    nonce = _nonce()
    event_data = {
        "probe": "",
        "summary": summary,
        "nonce": nonce,
        "perceive_nonce": perceive_nonce,
        "ts": _now_iso(),
        "artifacts_created": _split(artifacts_created),
        "artifacts_modified": _split(artifacts_modified),
        "next_steps": _split(next_steps),
        "insights": _split(insights),
        "doc_count": doc_count,
        "event_count": event_count,
        "execute_steps": len(_session["execute_tokens"]),
        "persists": (
            f"PREY8 yield closed. Perceived nonce: {perceive_nonce}. "
            f"Summary: {summary}"
        ),
    }
    event = _cloudevent(f"hfo.gen{GEN}.prey8.yield", event_data, "prey-yield")
    row_id = _write_stigmergy(event)

    # Reset session
    receipt = {
        "status": "YIELDED",
        "nonce": nonce,
        "perceive_nonce": perceive_nonce,
        "stigmergy_row_id": row_id,
        "execute_steps_logged": len(_session["execute_tokens"]),
        "sw4_completion_contract": {
            "given": f"Perceive nonce {perceive_nonce} opened session",
            "when": f"Agent executed {len(_session['execute_tokens'])} steps",
            "then": f"Yield nonce {nonce} closed loop. Summary: {summary}",
        },
        "instruction": "PREY8 loop complete. Session persisted to SSOT stigmergy.",
    }

    _session["perceive_nonce"] = None
    _session["react_token"] = None
    _session["execute_tokens"] = []
    _session["phase"] = "idle"

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
        event_type_pattern: SQL LIKE pattern for event_type (default: % = all). Examples: '%yield%', '%perceive%', '%p4%'.
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
        dict with doc_count, event_count, sources breakdown, latest events.
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

        session_phase = _session["phase"]
        perceive_nonce = _session["perceive_nonce"]

        return {
            "doc_count": doc_count,
            "event_count": event_count,
            "total_words": total_words,
            "sources": sources,
            "db_path": str(DB_PATH),
            "db_size_mb": round(DB_PATH.stat().st_size / (1024 * 1024), 1),
            "current_session": {
                "phase": session_phase,
                "perceive_nonce": perceive_nonce,
                "execute_steps": len(_session["execute_tokens"]),
            },
        }
    finally:
        conn.close()


@mcp.tool()
def prey8_session_status() -> dict:
    """
    Get current PREY8 session status and flow state.

    Returns:
        Current phase, nonces, and what steps are available next.
    """
    phase = _session["phase"]
    available_next = {
        "idle": ["prey8_perceive"],
        "perceived": ["prey8_react"],
        "reacted": ["prey8_execute", "prey8_yield"],
        "executing": ["prey8_execute", "prey8_yield"],
    }
    return {
        "phase": phase,
        "perceive_nonce": _session["perceive_nonce"],
        "react_token": _session["react_token"],
        "execute_steps": len(_session["execute_tokens"]),
        "available_next_tools": available_next.get(phase, []),
        "flow": "Perceive → React → Execute (repeat) → Yield",
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
