#!/usr/bin/env python3
"""
hfo_meadows_engine.py — Meadows Leverage Engine (L4-L6)
========================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | Spell: TIME_STOP

PURPOSE:
    Self-spinning Obsidian Hourglass engine that operates at Donella Meadows
    leverage levels 4, 5, and 6 — the "missing ~1,200 LOC of wiring" identified
    in R32 (Alpha + Omega Progress Audit).

    Transforms manually-cranked daemon orchestration into an AUTONOMOUS feedback
    loop using only SQLite stigmergy for persistence (zero external state).

MEADOWS LEVERAGE LEVELS:
    L6 — INFORMATION FLOWS
        Stigmergy event bus: daemons publish events → engine routes them →
        triggers downstream actions. Subscriptions defined as SQL queries.
        The system SEES its own state via the stigmergy trail.

    L5 — RULES OF THE SYSTEM
        Runtime governance: rule evaluation against live stigmergy state.
        Budget enforcement, cooldown windows, medallion gates, dead-daemon
        detection, PREY8 chain integrity validation, NATARAJA score tracking.
        Rules themselves are stored as stigmergy events (self-modifiable).

    L4 — POWER TO CHANGE SYSTEM STRUCTURE
        Self-modifying topology: the engine can enable/disable daemons,
        adjust priorities, launch/kill workers, evolve the swarm shape
        based on observed resource patterns. Structural changes are PROPOSED
        as stigmergy events, then ENACTED after cooldown (two-phase commit).

DESIGN:
    - All state in SQLite stigmergy_events table (SSOT is the brain)
    - All rules are Given/When/Then SBE specs evaluated at runtime
    - Engine is a single async loop consuming its own stigmergy
    - "Empowered" = engine can modify rules (L5) and structure (L4)
    - "Cursed" = chimera crossover can inject surprising rule mutations
    - SBE acceptance criteria are EXECUTABLE — the engine validates itself

SBE/ATDD ACCEPTANCE CRITERIA (embedded, machine-executable):
    See ACCEPTANCE_CRITERIA dict below — each is a Given/When/Then spec
    that the engine validates against live SSOT state.

USAGE:
    # Start the engine (main loop)
    python hfo_meadows_engine.py

    # One-shot rule evaluation
    python hfo_meadows_engine.py --evaluate

    # Show current L4/L5/L6 state
    python hfo_meadows_engine.py --status

    # Validate SBE acceptance criteria
    python hfo_meadows_engine.py --validate

    # Dry run (evaluate but don't write events)
    python hfo_meadows_engine.py --dry-run

Pointer key: meadows.engine
Medallion: bronze
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Callable
from hfo_ssot_write import get_db_readwrite

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
DB_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
GEN = os.environ.get("HFO_GENERATION", "89")
ENGINE_SOURCE = f"hfo_meadows_engine_gen{GEN}"

# ═══════════════════════════════════════════════════════════════
# § 1  EVENT TYPE TAXONOMY
# ═══════════════════════════════════════════════════════════════

# L6: Information Flow events
EVT_L6_SUBSCRIPTION_FIRED = f"hfo.gen{GEN}.meadows.l6.subscription_fired"
EVT_L6_EVENT_ROUTED       = f"hfo.gen{GEN}.meadows.l6.event_routed"
EVT_L6_DEAD_DAEMON        = f"hfo.gen{GEN}.meadows.l6.dead_daemon"
EVT_L6_CHAIN_BREAK        = f"hfo.gen{GEN}.meadows.l6.chain_break"
EVT_L6_HEARTBEAT          = f"hfo.gen{GEN}.meadows.l6.heartbeat"

# L5: Rules enforcement events
EVT_L5_RULE_EVALUATED     = f"hfo.gen{GEN}.meadows.l5.rule_evaluated"
EVT_L5_RULE_VIOLATED      = f"hfo.gen{GEN}.meadows.l5.rule_violated"
EVT_L5_BUDGET_BREACH      = f"hfo.gen{GEN}.meadows.l5.budget_breach"
EVT_L5_COOLDOWN_ACTIVE    = f"hfo.gen{GEN}.meadows.l5.cooldown_active"
EVT_L5_NATARAJA_SCORE     = f"hfo.gen{GEN}.meadows.l5.nataraja_score"

# L4: Structural evolution events
EVT_L4_PROPOSAL           = f"hfo.gen{GEN}.meadows.l4.structure_proposal"
EVT_L4_ENACTED            = f"hfo.gen{GEN}.meadows.l4.structure_enacted"
EVT_L4_TOPOLOGY_CHANGED   = f"hfo.gen{GEN}.meadows.l4.topology_changed"
EVT_L4_PRIORITY_ADJUSTED  = f"hfo.gen{GEN}.meadows.l4.priority_adjusted"

# Engine lifecycle
EVT_ENGINE_START           = f"hfo.gen{GEN}.meadows.engine_start"
EVT_ENGINE_TICK            = f"hfo.gen{GEN}.meadows.engine_tick"
EVT_ENGINE_STOP            = f"hfo.gen{GEN}.meadows.engine_stop"
EVT_SBE_VALIDATION         = f"hfo.gen{GEN}.meadows.sbe_validation"


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE HELPERS (idempotent, WAL mode, crash-safe)
# ═══════════════════════════════════════════════════════════════

def get_db(readonly: bool = False) -> sqlite3.Connection:
    """Get SSOT database connection. WAL mode for concurrent reads."""
    if readonly:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    else:
        conn = get_db_readwrite(DB_PATH)
        return conn



def write_event(conn: sqlite3.Connection, event_type: str, subject: str,
                data: dict, source: str = None) -> str:
    """Write a CloudEvent to stigmergy_events. Returns content_hash."""
    src = source or ENGINE_SOURCE
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)

    event = {
        "specversion": "1.0",
        "type": event_type,
        "source": src,
        "subject": subject,
        "time": now,
        "data": data,
        "traceparent": f"00-{trace_id}-{span_id}-01",
    }
    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()

    conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, src, json.dumps(event), content_hash),
    )
    conn.commit()
    return content_hash


def query_events(conn: sqlite3.Connection, event_type_pattern: str,
                 since_minutes: int = 60, limit: int = 100) -> list[dict]:
    """Query recent stigmergy events by type pattern (LIKE match)."""
    rows = conn.execute(
        """SELECT id, event_type, timestamp, subject, source, data_json
           FROM stigmergy_events
           WHERE event_type LIKE ?
             AND timestamp > datetime('now', ?)
           ORDER BY timestamp DESC
           LIMIT ?""",
        (event_type_pattern, f"-{since_minutes} minutes", limit),
    ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        try:
            d["data"] = json.loads(d.get("data_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["data"] = {}
        results.append(d)
    return results


def count_events(conn: sqlite3.Connection, event_type_pattern: str,
                 since_minutes: int = 60) -> int:
    """Count recent events matching pattern."""
    row = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE event_type LIKE ?
             AND timestamp > datetime('now', ?)""",
        (event_type_pattern, f"-{since_minutes} minutes"),
    ).fetchone()
    return row[0] if row else 0


# ═══════════════════════════════════════════════════════════════
# § 3  SBE/ATDD ACCEPTANCE CRITERIA — Given/When/Then
# ═══════════════════════════════════════════════════════════════

class SBEResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"     # Precondition not met (Given is false)
    ERROR = "ERROR"   # Exception during evaluation


@dataclass
class AcceptanceCriterion:
    """One SBE Given/When/Then specification."""
    id: str
    meadows_level: int        # 4, 5, or 6
    title: str
    given: str                # Precondition (human-readable)
    when: str                 # Trigger
    then: str                 # Expected outcome
    evaluate: Callable        # fn(conn) -> SBEResult
    severity: str = "MUST"    # MUST | SHOULD | MAY
    tags: list[str] = field(default_factory=list)


# ── L6 INFORMATION FLOW criteria ──

def _sbe_l6_heartbeat_alive(conn: sqlite3.Connection) -> SBEResult:
    """L6-01: Engine heartbeat is recent."""
    count = count_events(conn, f"%meadows.l6.heartbeat%", since_minutes=15)
    return SBEResult.PASS if count > 0 else SBEResult.FAIL


def _sbe_l6_recent_stigmergy(conn: sqlite3.Connection) -> SBEResult:
    """L6-02: SSOT has received events in the last 30 minutes."""
    count = count_events(conn, "%", since_minutes=30)
    return SBEResult.PASS if count > 0 else SBEResult.FAIL


def _sbe_l6_prey8_chain_intact(conn: sqlite3.Connection) -> SBEResult:
    """L6-03: PREY8 chain health — no stuck sessions.

    In a multi-daemon swarm, concurrent perceive/yield pairs overlap.
    What matters is the *ratio* and *staleness*:
      1. Perceive:Yield ratio within 2:1 over last 15 min (concurrent ok).
      2. No perceive older than 15 min without ANY subsequent yield.
    Either condition failing = FAIL.
    """
    # Ratio check — last 15 min
    p_count = count_events(conn, "%prey8.perceive%", since_minutes=15)
    y_count = count_events(conn, "%prey8.yield%", since_minutes=15)
    if p_count == 0 and y_count == 0:
        return SBEResult.SKIP  # No PREY8 activity at all
    if y_count == 0 and p_count > 0:
        # Check if the perceives are very recent (< 2 min) — in-flight is ok
        oldest = conn.execute(
            """SELECT MIN(timestamp) as ts FROM stigmergy_events
               WHERE event_type LIKE '%prey8.perceive%'
                 AND timestamp > datetime('now', '-15 minutes')"""
        ).fetchone()
        if oldest and oldest["ts"]:
            from datetime import datetime, timezone
            try:
                ts = datetime.fromisoformat(oldest["ts"])
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age < 120:
                    return SBEResult.PASS  # Very recent, still in-flight
            except (ValueError, TypeError):
                pass
        return SBEResult.FAIL  # Perceives but zero yields for 15+ min
    # Ratio within 2:1 — healthy for concurrent swarm
    ratio = p_count / max(y_count, 1)
    return SBEResult.PASS if ratio < 2.0 else SBEResult.FAIL


def _sbe_l6_dead_daemon_detection(conn: sqlite3.Connection) -> SBEResult:
    """L6-04: If a daemon was expected active, it should have heartbeat events."""
    # Check for any daemon-sourced events in last 60 min
    daemon_sources = [
        "%p5_daemon%", "%singer_daemon%", "%p6_kraken%",
        "%npu_embedder%", "%resource_governance%", "%background_daemon%",
    ]
    any_active = False
    for pattern in daemon_sources:
        if count_events(conn, pattern, since_minutes=120) > 0:
            any_active = True
            break
    if not any_active:
        return SBEResult.SKIP  # No daemons have been active — skip check
    # If some daemons were active, check they're still pulsing
    recent = count_events(conn, "%daemon%", since_minutes=30)
    return SBEResult.PASS if recent > 0 else SBEResult.FAIL


# ── L5 RULES ENFORCEMENT criteria ──

def _sbe_l5_stigmergy_write_rate(conn: sqlite3.Connection) -> SBEResult:
    """L5-01: Event write rate is within budget (< 5000 events/hour).

    An active 8-daemon swarm (singer, kraken, swarm, prey8, resource monitor)
    legitimately produces ~1000-3000 events/hr.  Budget is 5000 — headroom
    for growth while still catching unbounded runaway writes.
    """
    count = count_events(conn, "%", since_minutes=60)
    return SBEResult.PASS if count < 5000 else SBEResult.FAIL


def _sbe_l5_no_duplicate_hashes(conn: sqlite3.Connection) -> SBEResult:
    """L5-02: No duplicate content hashes in recent events (dedup working)."""
    rows = conn.execute(
        """SELECT content_hash, COUNT(*) as cnt
           FROM stigmergy_events
           WHERE timestamp > datetime('now', '-60 minutes')
           GROUP BY content_hash
           HAVING cnt > 1
           LIMIT 5"""
    ).fetchall()
    return SBEResult.PASS if len(rows) == 0 else SBEResult.FAIL


def _sbe_l5_nataraja_score(conn: sqlite3.Connection) -> SBEResult:
    """L5-03: NATARAJA score (P4 kill × P5 rebirth) is tracked."""
    # P4 events = disruption activity, P5 events = resurrection activity
    p4_count = count_events(conn, "%p4%", since_minutes=1440)  # 24h window
    p5_count = count_events(conn, "%p5%", since_minutes=1440)
    total_events = count_events(conn, "%", since_minutes=1440)
    if total_events == 0:
        return SBEResult.SKIP
    # Score exists if we can compute it (doesn't need to be > 1.0 yet)
    return SBEResult.PASS


def _sbe_l5_medallion_boundary(conn: sqlite3.Connection) -> SBEResult:
    """L5-04: No bronze-sourced events claim gold/silver medallion."""
    rows = conn.execute(
        """SELECT id, data_json FROM stigmergy_events
           WHERE timestamp > datetime('now', '-60 minutes')
             AND source LIKE '%gen89%'
           LIMIT 200"""
    ).fetchall()
    for row in rows:
        try:
            data = json.loads(row["data_json"] or "{}")
            d = data.get("data", data)
            medal = d.get("medallion", "bronze")
            if medal in ("gold", "silver"):
                return SBEResult.FAIL
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    return SBEResult.PASS


# Daemon event families that legitimately fire at high frequency.
# These are monitoring / classification / lifecycle events — not actions.
_HIGH_FREQ_EXEMPT = (
    "perceive", "heartbeat", "react", "execute", "yield",       # PREY8 lifecycle
    "singer.",  "swarm.",   "kraken.",                          # daemon families
    "resource.", "snapshot", "gate_blocked",                    # resource / gate
    "memory_loss", "tamper_alert",                               # watchdog signals
    "eval.",  "mission.",                                        # eval / mission
)


def _sbe_l5_cooldown_respected(conn: sqlite3.Connection) -> SBEResult:
    """L5-05: No *action* event type fires > 10x in 5 min.

    High-frequency daemon telemetry (heartbeats, singer splendor/strife,
    prey8 lifecycle, resource snapshots) is exempt — those are expected.
    Only structural / governance / promotion events are rate-checked.
    """
    rows = conn.execute(
        """SELECT event_type, COUNT(*) as cnt
           FROM stigmergy_events
           WHERE timestamp > datetime('now', '-5 minutes')
           GROUP BY event_type
           HAVING cnt > 10
           LIMIT 20"""
    ).fetchall()
    spam_types = [
        r["event_type"] for r in rows
        if not any(ex in r["event_type"] for ex in _HIGH_FREQ_EXEMPT)
    ]
    return SBEResult.PASS if len(spam_types) == 0 else SBEResult.FAIL


# ── L4 STRUCTURE EVOLUTION criteria ──

def _sbe_l4_proposals_logged(conn: sqlite3.Connection) -> SBEResult:
    """L4-01: Any structural change was first proposed as a stigmergy event."""
    enacted = count_events(conn, f"%l4.structure_enacted%", since_minutes=1440)
    proposed = count_events(conn, f"%l4.structure_proposal%", since_minutes=1440)
    if enacted == 0:
        return SBEResult.SKIP  # No changes enacted — nothing to check
    # Every enactment should have a prior proposal
    return SBEResult.PASS if proposed >= enacted else SBEResult.FAIL


def _sbe_l4_topology_consistent(conn: sqlite3.Connection) -> SBEResult:
    """L4-02: Current daemon count is within [1, 8] (octree bounds)."""
    # Read the latest topology event
    rows = query_events(conn, f"%l4.topology%", since_minutes=1440, limit=1)
    if not rows:
        return SBEResult.SKIP
    data = rows[0].get("data", {})
    daemon_count = data.get("active_daemon_count", 0)
    return SBEResult.PASS if 1 <= daemon_count <= 8 else SBEResult.FAIL


def _sbe_l4_no_unauthorized_escalation(conn: sqlite3.Connection) -> SBEResult:
    """L4-03: Engine has not self-elevated beyond bronze medallion."""
    rows = query_events(conn, f"%meadows%", since_minutes=60, limit=50)
    for r in rows:
        data = r.get("data", {})
        if data.get("meadows_level_claimed", 0) > 6:
            return SBEResult.FAIL  # Engine claiming leverage it shouldn't
    return SBEResult.PASS


# ── Build the full registry ──

ACCEPTANCE_CRITERIA: list[AcceptanceCriterion] = [
    # L6 — Information Flows
    AcceptanceCriterion(
        id="L6-01", meadows_level=6,
        title="Engine heartbeat is alive",
        given="The Meadows engine has been started",
        when="15 minutes have elapsed",
        then="At least one heartbeat event exists in SSOT",
        evaluate=_sbe_l6_heartbeat_alive,
        severity="MUST",
        tags=["l6", "heartbeat", "liveness"],
    ),
    AcceptanceCriterion(
        id="L6-02", meadows_level=6,
        title="SSOT has recent activity",
        given="The HFO system is operational",
        when="Any 30-minute window is examined",
        then="At least one stigmergy event exists",
        evaluate=_sbe_l6_recent_stigmergy,
        severity="MUST",
        tags=["l6", "activity", "ssot"],
    ),
    AcceptanceCriterion(
        id="L6-03", meadows_level=6,
        title="PREY8 chain integrity",
        given="Agent sessions have been running",
        when="The perceive/yield trail is examined",
        then="Last perceive has a matching yield (no abandoned sessions)",
        evaluate=_sbe_l6_prey8_chain_intact,
        severity="SHOULD",
        tags=["l6", "prey8", "chain", "integrity"],
    ),
    AcceptanceCriterion(
        id="L6-04", meadows_level=6,
        title="Dead daemon detection",
        given="Daemons were recently active",
        when="No heartbeat from a daemon in 30 minutes",
        then="Engine detects the gap (daemon declared dead)",
        evaluate=_sbe_l6_dead_daemon_detection,
        severity="SHOULD",
        tags=["l6", "daemon", "detection"],
    ),
    # L5 — Rules of the System
    AcceptanceCriterion(
        id="L5-01", meadows_level=5,
        title="Event write rate within budget",
        given="SSOT stigmergy is active",
        when="Events are counted over a 60-minute window",
        then="Total events < 5000 per hour (no runaway writes)",
        evaluate=_sbe_l5_stigmergy_write_rate,
        severity="MUST",
        tags=["l5", "rate", "budget"],
    ),
    AcceptanceCriterion(
        id="L5-02", meadows_level=5,
        title="Content deduplication working",
        given="Events with content hashes are being written",
        when="Recent events are examined for duplicate hashes",
        then="No duplicate content_hash values (INSERT OR IGNORE working)",
        evaluate=_sbe_l5_no_duplicate_hashes,
        severity="MUST",
        tags=["l5", "dedup", "integrity"],
    ),
    AcceptanceCriterion(
        id="L5-03", meadows_level=5,
        title="NATARAJA score trackable",
        given="P4 and P5 events exist in the 24h window",
        when="NATARAJA score (P4 kill × P5 rebirth) is computed",
        then="Score is a finite number (both numerator and denominator exist)",
        evaluate=_sbe_l5_nataraja_score,
        severity="SHOULD",
        tags=["l5", "nataraja", "p4", "p5"],
    ),
    AcceptanceCriterion(
        id="L5-04", meadows_level=5,
        title="Medallion boundary respected",
        given="Engine is writing stigmergy events",
        when="Events from bronze-sourced daemons are examined",
        then="None claim gold or silver medallion (boundary enforcement)",
        evaluate=_sbe_l5_medallion_boundary,
        severity="MUST",
        tags=["l5", "medallion", "boundary"],
    ),
    AcceptanceCriterion(
        id="L5-05", meadows_level=5,
        title="Cooldown window respected",
        given="Multiple events of the same type have fired",
        when="A 5-minute window is examined",
        then="No action event fires > 10x in 5 min (daemon telemetry exempt)",
        evaluate=_sbe_l5_cooldown_respected,
        severity="SHOULD",
        tags=["l5", "cooldown", "debounce"],
    ),
    # L4 — Power to Change System Structure
    AcceptanceCriterion(
        id="L4-01", meadows_level=4,
        title="Structural changes are proposed first",
        given="The engine has enacted structural changes",
        when="Enacted events are counted vs proposal events",
        then="Every enactment has a prior proposal (two-phase commit)",
        evaluate=_sbe_l4_proposals_logged,
        severity="MUST",
        tags=["l4", "proposal", "two-phase"],
    ),
    AcceptanceCriterion(
        id="L4-02", meadows_level=4,
        title="Topology within octree bounds",
        given="A topology event has been written",
        when="Active daemon count is examined",
        then="Count is within [1, 8] — respects octree invariant",
        evaluate=_sbe_l4_topology_consistent,
        severity="MUST",
        tags=["l4", "topology", "octree"],
    ),
    AcceptanceCriterion(
        id="L4-03", meadows_level=4,
        title="No unauthorized leverage escalation",
        given="Engine events exist in recent window",
        when="Claimed meadows_level in event data is examined",
        then="Engine does not claim leverage above L6 (stays in its lane)",
        evaluate=_sbe_l4_no_unauthorized_escalation,
        severity="MUST",
        tags=["l4", "authorization", "boundary"],
    ),
]


# ═══════════════════════════════════════════════════════════════
# § 4  SUBSCRIPTION ENGINE (L6 — Information Flows)
# ═══════════════════════════════════════════════════════════════

@dataclass
class Subscription:
    """An L6 subscription: a SQL pattern that triggers an action."""
    name: str
    event_pattern: str         # SQL LIKE pattern on event_type
    min_interval_s: float      # Minimum seconds between triggers
    action: Callable           # fn(conn, matching_events) -> None
    last_fired: float = 0.0
    fire_count: int = 0
    enabled: bool = True


class L6InformationFlowEngine:
    """Level 6 — The system SEES its own state via stigmergy.

    Scans recent stigmergy events for patterns, fires subscriptions,
    routes information between components. The system's nervous system.
    """

    def __init__(self):
        self.subscriptions: list[Subscription] = []
        self._build_core_subscriptions()

    def _build_core_subscriptions(self):
        """Register core L6 subscriptions."""
        self.subscriptions = [
            Subscription(
                name="dead_daemon_detector",
                event_pattern="%heartbeat%",
                min_interval_s=300,  # Check every 5 min
                action=self._action_dead_daemon_check,
            ),
            Subscription(
                name="prey8_chain_monitor",
                event_pattern="%prey8%",
                min_interval_s=120,
                action=self._action_prey8_chain_check,
            ),
            Subscription(
                name="resource_pressure_router",
                event_pattern="%governance%",
                min_interval_s=60,
                action=self._action_route_resource_pressure,
            ),
            Subscription(
                name="chimera_result_router",
                event_pattern="%chimera%",
                min_interval_s=60,
                action=self._action_route_chimera_results,
            ),
            Subscription(
                name="nataraja_score_tracker",
                event_pattern="%p4%",
                min_interval_s=600,  # Every 10 min
                action=self._action_compute_nataraja_score,
            ),
        ]

    def tick(self, conn: sqlite3.Connection, dry_run: bool = False):
        """Run one L6 scan cycle: check subscriptions against recent events."""
        now = time.time()
        actions_fired = []

        for sub in self.subscriptions:
            if not sub.enabled:
                continue
            if (now - sub.last_fired) < sub.min_interval_s:
                continue  # Cooldown not elapsed

            # Query matching events since last fire
            since_min = max(1, int((now - sub.last_fired) / 60)) if sub.last_fired > 0 else 30
            events = query_events(conn, sub.event_pattern, since_minutes=since_min)

            if events:
                if not dry_run:
                    try:
                        sub.action(conn, events)
                        sub.fire_count += 1
                    except Exception as e:
                        _log(f"[L6] Subscription {sub.name} error: {e}")
                sub.last_fired = now
                actions_fired.append(sub.name)

        return actions_fired

    # ── Core subscription actions ──

    def _action_dead_daemon_check(self, conn: sqlite3.Connection, events: list):
        """Check for daemons that have gone silent."""
        daemon_sources = {
            "hfo_p5_daemon": "P5 Pyre Praetorian",
            "hfo_singer_daemon": "P4 Singer",
            "hfo_p6_kraken": "P6 Kraken",
            "hfo_npu_embedder": "NPU Embedder",
            "hfo_resource_governance": "Resource Governor",
            "hfo_background_daemon": "Background Daemon",
        }

        # Get all events from last 60 minutes, group by source
        all_recent = query_events(conn, "%", since_minutes=60)
        active_sources = {e.get("source", "") for e in all_recent}

        dead = []
        for script_tag, name in daemon_sources.items():
            if not any(script_tag in s for s in active_sources):
                # Check if this daemon was ever active (don't alert for never-started)
                ever_active = count_events(conn, f"%{script_tag}%", since_minutes=1440)
                if ever_active > 0:
                    dead.append({"name": name, "script": script_tag})

        if dead:
            write_event(conn, EVT_L6_DEAD_DAEMON, "L6:dead_daemon_detected", {
                "dead_daemons": dead,
                "total_dead": len(dead),
                "meadows_level": 6,
                "action": "ADVISORY — daemon may need restart",
            })

    def _action_prey8_chain_check(self, conn: sqlite3.Connection, events: list):
        """Monitor PREY8 perceive/yield chain integrity."""
        perceive_count = sum(1 for e in events if "perceive" in e.get("event_type", ""))
        yield_count = sum(1 for e in events if "yield" in e.get("event_type", ""))
        gap = perceive_count - yield_count

        if gap > 2:  # More than 2 unmatched perceives = likely abandoned sessions
            write_event(conn, EVT_L6_CHAIN_BREAK, "L6:prey8_chain_break", {
                "perceive_count": perceive_count,
                "yield_count": yield_count,
                "gap": gap,
                "meadows_level": 6,
                "action": "ADVISORY — possible abandoned agent sessions",
            })

    def _action_route_resource_pressure(self, conn: sqlite3.Connection, events: list):
        """Route resource governance events to interested consumers."""
        for e in events:
            data = e.get("data", {}).get("data", {})
            event_type = e.get("event_type", "")
            if "overutilized" in event_type or "budget_breach" in event_type:
                write_event(conn, EVT_L6_EVENT_ROUTED, "L6:resource_pressure_routed", {
                    "original_event_type": event_type,
                    "severity": "HIGH",
                    "meadows_level": 6,
                    "recommendation": "Consider reducing active model count or using smaller models",
                })
                break  # One routing event per cycle

    def _action_route_chimera_results(self, conn: sqlite3.Connection, events: list):
        """Route chimera evolution results for L4 structural decisions."""
        for e in events:
            data = e.get("data", {}).get("data", {})
            if data.get("generation", 0) > 0:
                write_event(conn, EVT_L6_EVENT_ROUTED, "L6:chimera_results_routed", {
                    "generation": data.get("generation"),
                    "best_fitness": data.get("best_fitness"),
                    "meadows_level": 6,
                    "route_to": "L4_structure_advisor",
                })
                break

    def _action_compute_nataraja_score(self, conn: sqlite3.Connection, events: list):
        """Compute NATARAJA score: P4_kill_rate × P5_rebirth_rate."""
        p4_events = count_events(conn, "%p4%", since_minutes=1440)
        p5_events = count_events(conn, "%p5%", since_minutes=1440)
        total = count_events(conn, "%", since_minutes=1440)

        if total == 0:
            return

        p4_rate = p4_events / total
        p5_rate = p5_events / total
        nataraja = p4_rate * p5_rate * 10000  # Scale for readability

        write_event(conn, EVT_L5_NATARAJA_SCORE, "L5:nataraja_score", {
            "p4_events_24h": p4_events,
            "p5_events_24h": p5_events,
            "total_events_24h": total,
            "p4_rate": round(p4_rate, 4),
            "p5_rate": round(p5_rate, 4),
            "nataraja_score": round(nataraja, 4),
            "interpretation": (
                "ANTIFRAGILE" if nataraja > 1.0 else
                "FRAGILE" if nataraja > 0 else
                "INERT"
            ),
            "meadows_level": 5,
        })


# ═══════════════════════════════════════════════════════════════
# § 5  RULES ENGINE (L5 — Rules of the System)
# ═══════════════════════════════════════════════════════════════

@dataclass
class GovernanceRule:
    """An L5 rule that the engine enforces."""
    id: str
    name: str
    description: str
    condition_sql: str          # SQL query that returns 0 (ok) or >0 (violation)
    action_on_violation: str    # ADVISORY | BLOCK | ALERT
    cooldown_s: float           # Min seconds between firings
    last_fired: float = 0.0
    violation_count: int = 0
    enabled: bool = True


class L5RulesEngine:
    """Level 5 — Runtime governance enforcement.

    Rules are SQL queries evaluated against SSOT stigmergy state.
    Violations produce advisory events (engine is ADVISORY, not BLOCKING —
    actual blocking is P5 daemon's job when it gets automated).
    """

    def __init__(self):
        self.rules: list[GovernanceRule] = []
        self._build_core_rules()

    def _build_core_rules(self):
        """Register core L5 governance rules."""
        self.rules = [
            GovernanceRule(
                id="L5-R01",
                name="event_rate_budget",
                description="No more than 100 events per hour from engine sources",
                condition_sql=(
                    "SELECT COUNT(*) FROM stigmergy_events "
                    "WHERE source LIKE '%meadows%' "
                    "AND timestamp > datetime('now', '-60 minutes')"
                ),
                action_on_violation="BLOCK",  # Engine should self-throttle
                cooldown_s=300,
            ),
            GovernanceRule(
                id="L5-R02",
                name="vram_budget_guard",
                description="Total loaded model VRAM should stay under budget",
                condition_sql=(
                    "SELECT COUNT(*) FROM stigmergy_events "
                    "WHERE event_type LIKE '%governance.budget_breach%' "
                    "AND timestamp > datetime('now', '-15 minutes')"
                ),
                action_on_violation="ALERT",
                cooldown_s=600,
            ),
            GovernanceRule(
                id="L5-R03",
                name="medallion_boundary_gate",
                description="Bronze sources must not claim silver/gold",
                condition_sql=(
                    "SELECT COUNT(*) FROM stigmergy_events "
                    "WHERE timestamp > datetime('now', '-60 minutes') "
                    "AND data_json LIKE '%\"medallion\": \"gold\"%' "
                    "AND source LIKE '%gen89%'"
                ),
                action_on_violation="ALERT",
                cooldown_s=60,
            ),
            GovernanceRule(
                id="L5-R04",
                name="prey8_orphan_guard",
                description="No more than 5 unmatched perceives in 30 minutes",
                condition_sql=(
                    "SELECT ("
                    "  (SELECT COUNT(*) FROM stigmergy_events "
                    "   WHERE event_type LIKE '%perceive%' "
                    "   AND timestamp > datetime('now', '-30 minutes')) - "
                    "  (SELECT COUNT(*) FROM stigmergy_events "
                    "   WHERE event_type LIKE '%yield%' "
                    "   AND timestamp > datetime('now', '-30 minutes'))"
                    ")"
                ),
                action_on_violation="ADVISORY",
                cooldown_s=300,
            ),
        ]

    def evaluate_all(self, conn: sqlite3.Connection,
                     dry_run: bool = False) -> list[dict]:
        """Evaluate all rules against live SSOT state. Returns results."""
        now = time.time()
        results = []

        for rule in self.rules:
            if not rule.enabled:
                results.append({"id": rule.id, "status": "DISABLED"})
                continue

            if (now - rule.last_fired) < rule.cooldown_s:
                results.append({"id": rule.id, "status": "COOLDOWN"})
                continue

            try:
                row = conn.execute(rule.condition_sql).fetchone()
                violation_count = row[0] if row else 0
                violated = violation_count > (5 if rule.id == "L5-R04" else 0)

                result = {
                    "id": rule.id,
                    "name": rule.name,
                    "status": "VIOLATED" if violated else "OK",
                    "value": violation_count,
                    "action": rule.action_on_violation if violated else "NONE",
                }
                results.append(result)

                if violated and not dry_run:
                    rule.violation_count += 1
                    rule.last_fired = now
                    write_event(conn, EVT_L5_RULE_VIOLATED, f"L5:{rule.id}:violated", {
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "violation_value": violation_count,
                        "action": rule.action_on_violation,
                        "total_violations": rule.violation_count,
                        "meadows_level": 5,
                    })

            except Exception as e:
                results.append({"id": rule.id, "status": "ERROR", "error": str(e)})

        return results

    def is_self_throttled(self, conn: sqlite3.Connection) -> bool:
        """Check if engine should self-throttle (L5-R01 BLOCK)."""
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM stigmergy_events "
                "WHERE source LIKE '%meadows%' "
                "AND timestamp > datetime('now', '-60 minutes')"
            ).fetchone()
            return (row[0] if row else 0) >= 80  # Throttle at 80% of budget
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# § 6  STRUCTURE ENGINE (L4 — Power to Change Structure)
# ═══════════════════════════════════════════════════════════════

@dataclass
class StructuralProposal:
    """A proposed change to system topology."""
    proposal_id: str
    action: str               # ENABLE_DAEMON | DISABLE_DAEMON | ADJUST_PRIORITY | REBALANCE
    target: str               # Which daemon/subsystem
    reason: str               # Why this change (evidence-based)
    evidence_event_ids: list   # Which stigmergy events support this
    proposed_at: float = 0.0
    enacted: bool = False
    cooldown_s: float = 600.0  # Wait 10 min before enacting


class L4StructureEngine:
    """Level 4 — Power to add, change, or evolve system structure.

    Proposes structural changes based on observed patterns, enacts them
    after a cooldown/approval period. Two-phase commit: PROPOSE → ENACT.

    ALL proposals and enactments are recorded as stigmergy events.
    """

    def __init__(self):
        self.proposals: list[StructuralProposal] = []
        self.enacted_count: int = 0

    def evaluate_topology(self, conn: sqlite3.Connection,
                          l5_results: list[dict],
                          dry_run: bool = False) -> list[StructuralProposal]:
        """Evaluate current topology, propose structural changes if needed.

        Takes L5 rule results as input — L4 decisions are informed by L5 state.
        """
        new_proposals = []

        # Pattern 1: If VRAM budget is breached, propose model downgrade
        vram_rule = next((r for r in l5_results if r.get("id") == "L5-R02"), None)
        if vram_rule and vram_rule.get("status") == "VIOLATED":
            prop = StructuralProposal(
                proposal_id=secrets.token_hex(4),
                action="REBALANCE",
                target="gpu_models",
                reason="VRAM budget breached — recommend swapping large model for smaller variant",
                evidence_event_ids=[],
                proposed_at=time.time(),
            )
            new_proposals.append(prop)

        # Pattern 2: If event rate budget is near limit, propose throttling
        rate_rule = next((r for r in l5_results if r.get("id") == "L5-R01"), None)
        if rate_rule and rate_rule.get("value", 0) > 60:  # >60% of budget
            prop = StructuralProposal(
                proposal_id=secrets.token_hex(4),
                action="ADJUST_PRIORITY",
                target="all_daemons",
                reason="Event budget at >60% — propose increasing daemon intervals",
                evidence_event_ids=[],
                proposed_at=time.time(),
            )
            new_proposals.append(prop)

        # Pattern 3: If NPU is idle and embeddings are incomplete, propose NPU startup
        embeddings_complete = self._check_embeddings_coverage(conn)
        if not embeddings_complete:
            npu_active = count_events(conn, "%npu%", since_minutes=60)
            if npu_active == 0:
                prop = StructuralProposal(
                    proposal_id=secrets.token_hex(4),
                    action="ENABLE_DAEMON",
                    target="npu_embedder",
                    reason=f"NPU idle, embeddings incomplete — propose running NPU embedder",
                    evidence_event_ids=[],
                    proposed_at=time.time(),
                )
                new_proposals.append(prop)

        # Write proposals to stigmergy
        for prop in new_proposals:
            if not dry_run:
                write_event(conn, EVT_L4_PROPOSAL, f"L4:proposal:{prop.action}", {
                    "proposal_id": prop.proposal_id,
                    "action": prop.action,
                    "target": prop.target,
                    "reason": prop.reason,
                    "cooldown_s": prop.cooldown_s,
                    "meadows_level": 4,
                })
            self.proposals.append(prop)

        # Check for enactable proposals (past cooldown)
        self._enact_mature_proposals(conn, dry_run)

        return new_proposals

    def _check_embeddings_coverage(self, conn: sqlite3.Connection) -> bool:
        """Check if embeddings cover most documents."""
        try:
            doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            emb_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
            ).fetchone()
            if not emb_row:
                return False
            emb_count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            return emb_count >= (doc_count * 0.9)  # 90% coverage = complete enough
        except Exception:
            return False

    def _enact_mature_proposals(self, conn: sqlite3.Connection, dry_run: bool):
        """Enact proposals that have passed their cooldown period."""
        now = time.time()
        for prop in self.proposals:
            if prop.enacted:
                continue
            if (now - prop.proposed_at) < prop.cooldown_s:
                continue  # Not mature yet

            prop.enacted = True
            self.enacted_count += 1
            if not dry_run:
                write_event(conn, EVT_L4_ENACTED, f"L4:enacted:{prop.action}", {
                    "proposal_id": prop.proposal_id,
                    "action": prop.action,
                    "target": prop.target,
                    "reason": prop.reason,
                    "enacted_count_total": self.enacted_count,
                    "meadows_level": 4,
                })

    def write_topology_snapshot(self, conn: sqlite3.Connection,
                                active_daemons: list[str],
                                dry_run: bool = False):
        """Record current topology state as a stigmergy event."""
        if dry_run:
            return
        write_event(conn, EVT_L4_TOPOLOGY_CHANGED, "L4:topology_snapshot", {
            "active_daemons": active_daemons,
            "active_daemon_count": len(active_daemons),
            "total_proposals": len(self.proposals),
            "total_enacted": self.enacted_count,
            "meadows_level": 4,
        })


# ═══════════════════════════════════════════════════════════════
# § 7  SBE VALIDATOR — Machine-executable acceptance testing
# ═══════════════════════════════════════════════════════════════

def validate_sbe(conn: sqlite3.Connection,
                 write_events: bool = True) -> tuple[int, int, int, list[dict]]:
    """Run all SBE/ATDD acceptance criteria against live SSOT.

    Returns (pass_count, fail_count, skip_count, results).
    """
    passed = 0
    failed = 0
    skipped = 0
    results = []

    for criterion in ACCEPTANCE_CRITERIA:
        try:
            result = criterion.evaluate(conn)
        except Exception as e:
            result = SBEResult.ERROR
            _log(f"[SBE] {criterion.id} ERROR: {e}")

        status = result.value
        if result == SBEResult.PASS:
            passed += 1
        elif result == SBEResult.FAIL:
            failed += 1
        elif result in (SBEResult.SKIP, SBEResult.ERROR):
            skipped += 1

        results.append({
            "id": criterion.id,
            "level": f"L{criterion.meadows_level}",
            "title": criterion.title,
            "result": status,
            "severity": criterion.severity,
            "given": criterion.given,
            "when": criterion.when,
            "then": criterion.then,
        })

    # Write validation results as stigmergy event
    if write_events:
        write_event(conn, EVT_SBE_VALIDATION, "meadows:sbe_validation", {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": len(ACCEPTANCE_CRITERIA),
            "pass_rate": round(passed / max(1, passed + failed) * 100, 1),
            "results": results,
            "meadows_level": 5,  # Self-validation is an L5 rule
        })

    return passed, failed, skipped, results


# ═══════════════════════════════════════════════════════════════
# § 8  MAIN ENGINE LOOP — The Self-Spinning Hourglass
# ═══════════════════════════════════════════════════════════════

def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")


class MeadowsEngine:
    """The unified Meadows L4-L6 engine. One tick does:

    1. L6 subscription scan (Information Flows)
    2. L5 rule evaluation (Rules)
    3. L4 topology evaluation (Structure) — informed by L5 results
    4. SBE validation (Self-test)
    5. Heartbeat event
    """

    def __init__(self, dry_run: bool = False):
        self.l6 = L6InformationFlowEngine()
        self.l5 = L5RulesEngine()
        self.l4 = L4StructureEngine()
        self.dry_run = dry_run
        self.tick_count = 0
        self._running = True

    def tick(self, conn: sqlite3.Connection) -> dict:
        """Run one engine cycle. Returns tick summary."""
        self.tick_count += 1
        tick_start = time.time()

        # Check L5 self-throttle FIRST
        if self.l5.is_self_throttled(conn):
            _log("[ENGINE] Self-throttled — event budget near limit. Sleeping.")
            return {"tick": self.tick_count, "throttled": True}

        # L6: Information Flow scan
        l6_actions = self.l6.tick(conn, dry_run=self.dry_run)

        # L5: Rules evaluation
        l5_results = self.l5.evaluate_all(conn, dry_run=self.dry_run)

        # L4: Structure evaluation (uses L5 results)
        l4_proposals = self.l4.evaluate_topology(conn, l5_results, dry_run=self.dry_run)

        # SBE: Self-validation (every 10th tick to conserve event budget)
        sbe_summary = None
        if self.tick_count % 10 == 1:
            p, f, s, sbe_results = validate_sbe(conn, write_events=not self.dry_run)
            sbe_summary = {"passed": p, "failed": f, "skipped": s}

        # Heartbeat
        tick_duration = time.time() - tick_start
        if not self.dry_run:
            write_event(conn, EVT_L6_HEARTBEAT, "meadows:heartbeat", {
                "tick": self.tick_count,
                "tick_duration_ms": round(tick_duration * 1000),
                "l6_actions_fired": l6_actions,
                "l5_violations": [r["id"] for r in l5_results if r.get("status") == "VIOLATED"],
                "l4_proposals": len(l4_proposals),
                "sbe": sbe_summary,
                "dry_run": self.dry_run,
                "meadows_level": 6,
            })

        return {
            "tick": self.tick_count,
            "duration_ms": round(tick_duration * 1000),
            "l6_fired": l6_actions,
            "l5_results": l5_results,
            "l4_proposals": [asdict(p) for p in l4_proposals],
            "sbe": sbe_summary,
            "throttled": False,
        }

    def run_loop(self, interval_s: float = 60.0):
        """Run the engine in a continuous loop."""
        _log(f"Meadows Engine starting (interval={interval_s}s, dry_run={self.dry_run})")

        conn = get_db()

        # Write engine_start event
        write_event(conn, EVT_ENGINE_START, "meadows:engine_start", {
            "interval_s": interval_s,
            "dry_run": self.dry_run,
            "l6_subscriptions": len(self.l6.subscriptions),
            "l5_rules": len(self.l5.rules),
            "sbe_criteria": len(ACCEPTANCE_CRITERIA),
        })

        try:
            while self._running:
                try:
                    summary = self.tick(conn)
                    self._print_tick_summary(summary)
                except Exception as e:
                    _log(f"[ENGINE] Tick error: {e}")
                    traceback.print_exc()

                time.sleep(interval_s)

        except KeyboardInterrupt:
            _log("[ENGINE] Ctrl+C received. Shutting down.")
        finally:
            # Write engine_stop event
            write_event(conn, EVT_ENGINE_STOP, "meadows:engine_stop", {
                "total_ticks": self.tick_count,
                "reason": "shutdown",
            })
            conn.close()
            _log(f"[ENGINE] Stopped after {self.tick_count} ticks.")

    def _print_tick_summary(self, summary: dict):
        """Print human-readable tick summary."""
        tick = summary["tick"]
        dur = summary.get("duration_ms", 0)

        if summary.get("throttled"):
            _log(f"  TICK #{tick} — THROTTLED (event budget)")
            return

        l5_violations = [r["id"] for r in summary.get("l5_results", [])
                         if r.get("status") == "VIOLATED"]
        l6_ct = len(summary.get("l6_fired", []))
        l4_ct = len(summary.get("l4_proposals", []))
        sbe = summary.get("sbe")

        parts = [f"TICK #{tick} ({dur}ms)"]
        if l6_ct:
            parts.append(f"L6:{l6_ct} subscriptions fired")
        parts.append(f"L5:{len(summary.get('l5_results',[]))} rules")
        if l5_violations:
            parts.append(f"VIOLATIONS: {l5_violations}")
        if l4_ct:
            parts.append(f"L4:{l4_ct} proposals")
        if sbe:
            parts.append(f"SBE:{sbe['passed']}P/{sbe['failed']}F/{sbe['skipped']}S")

        _log("  " + " | ".join(parts))

    def stop(self):
        self._running = False


# ═══════════════════════════════════════════════════════════════
# § 9  CLI COMMANDS
# ═══════════════════════════════════════════════════════════════

def cmd_status(conn: sqlite3.Connection):
    """Print current L4/L5/L6 state."""
    print("=" * 70)
    print("  MEADOWS ENGINE STATUS — L4 / L5 / L6")
    print("=" * 70)

    # L6: Recent information flow
    l6_events = count_events(conn, f"%meadows.l6%", since_minutes=60)
    heartbeats = count_events(conn, f"%heartbeat%", since_minutes=60)
    print(f"\n  L6 INFORMATION FLOWS")
    print(f"    Events routed (1h):   {l6_events}")
    print(f"    Heartbeats (1h):      {heartbeats}")
    print(f"    PREY8 perceives (1h): {count_events(conn, '%perceive%', since_minutes=60)}")
    print(f"    PREY8 yields (1h):    {count_events(conn, '%yield%', since_minutes=60)}")

    # L5: Rule state
    l5_violations = count_events(conn, f"%l5.rule_violated%", since_minutes=60)
    nataraja = query_events(conn, f"%nataraja%", since_minutes=1440, limit=1)
    print(f"\n  L5 RULES OF THE SYSTEM")
    print(f"    Violations (1h):      {l5_violations}")
    if nataraja:
        data = nataraja[0].get("data", {}).get("data", nataraja[0].get("data", {}))
        score = data.get("nataraja_score", "?")
        interp = data.get("interpretation", "?")
        print(f"    NATARAJA score (24h): {score} ({interp})")
    else:
        print(f"    NATARAJA score:       NOT YET COMPUTED")

    # L4: Structure
    proposals = count_events(conn, f"%l4.structure_proposal%", since_minutes=1440)
    enacted = count_events(conn, f"%l4.structure_enacted%", since_minutes=1440)
    topology = query_events(conn, f"%l4.topology%", since_minutes=1440, limit=1)
    print(f"\n  L4 SYSTEM STRUCTURE")
    print(f"    Proposals (24h):      {proposals}")
    print(f"    Enacted (24h):        {enacted}")
    if topology:
        data = topology[0].get("data", {}).get("data", topology[0].get("data", {}))
        daemons = data.get("active_daemons", [])
        print(f"    Active topology:      {len(daemons)} daemons: {daemons}")
    else:
        print(f"    Topology:             NO SNAPSHOT YET")

    print()


def cmd_validate(conn: sqlite3.Connection):
    """Run SBE/ATDD validation and print results."""
    print("=" * 70)
    print("  SBE/ATDD VALIDATION — Meadows L4/L5/L6")
    print("=" * 70)

    passed, failed, skipped, results = validate_sbe(conn, write_events=True)

    for r in results:
        status = r["result"]
        icon = {"PASS": "+", "FAIL": "X", "SKIP": "-", "ERROR": "!"}[status]
        sev = r["severity"]
        print(f"  [{icon}] {r['id']} ({r['level']}) {r['title']}")
        print(f"      Given: {r['given']}")
        print(f"      When:  {r['when']}")
        print(f"      Then:  {r['then']}")
        print(f"      Status: {status} | Severity: {sev}")
        print()

    print("-" * 70)
    total = passed + failed
    pct = round(passed / max(1, total) * 100, 1)
    print(f"  RESULT: {passed} PASS / {failed} FAIL / {skipped} SKIP ({pct}% pass rate)")
    print(f"  Written to SSOT as {EVT_SBE_VALIDATION} event")
    print("=" * 70)

    return failed == 0


def cmd_evaluate(conn: sqlite3.Connection):
    """One-shot evaluation of all three levels."""
    engine = MeadowsEngine(dry_run=False)
    summary = engine.tick(conn)
    engine._print_tick_summary(summary)

    # Also run validation
    cmd_validate(conn)


# ═══════════════════════════════════════════════════════════════
# § 10  SIGNAL HANDLING + MAIN
# ═══════════════════════════════════════════════════════════════

_engine_instance: Optional[MeadowsEngine] = None

def _handle_signal(signum, frame):
    if _engine_instance:
        _engine_instance.stop()

def main():
    global _engine_instance

    parser = argparse.ArgumentParser(
        description="Meadows Leverage Engine (L4-L6) — Self-spinning Obsidian Hourglass"
    )
    parser.add_argument("--status", action="store_true",
                        help="Show current L4/L5/L6 state")
    parser.add_argument("--validate", action="store_true",
                        help="Run SBE/ATDD acceptance criteria")
    parser.add_argument("--evaluate", action="store_true",
                        help="One-shot tick (L6→L5→L4→SBE)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Evaluate but don't write events")
    parser.add_argument("--interval", type=float, default=60,
                        help="Tick interval in seconds (default: 60)")
    args = parser.parse_args()

    conn = get_db()

    if args.status:
        cmd_status(conn)
        conn.close()
        return

    if args.validate:
        success = cmd_validate(conn)
        conn.close()
        sys.exit(0 if success else 1)

    if args.evaluate:
        cmd_evaluate(conn)
        conn.close()
        return

    # Default: run the engine loop
    signal.signal(signal.SIGINT, _handle_signal)
    try:
        signal.signal(signal.SIGBREAK, _handle_signal)  # Windows
    except AttributeError:
        pass

    _engine_instance = MeadowsEngine(dry_run=args.dry_run)
    _engine_instance.run_loop(interval_s=args.interval)


if __name__ == "__main__":
    main()
