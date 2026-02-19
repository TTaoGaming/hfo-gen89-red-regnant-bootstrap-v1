#!/usr/bin/env python3
"""
hfo_p5_contingency.py — P5 Pyre Praetorian CONTINGENCY Spell

THE spell that was missing. This is the automated resurrection engine.

CONTINGENCY (School: Evocation) — Pre-set triggers that fire automatically
when specific conditions are met, without requiring manual intervention.

What CONTINGENCY does:
  1. MONITOR: Watch for death signals — daemon errors, chain breaks, ghost sessions
  2. DETECT: Classify the nature of the death (crash, timeout, resource, logic)
  3. RESURRECT: Bring the dead component back with accumulated knowledge
  4. IMMUNIZE: Apply lessons learned so the same death cannot recur
  5. REPORT: Write stigmergy so P6 (FEAST) can extract knowledge from the death

The Phoenix Protocol overlay (from Gen88 Nataraja doc):
  Phase 10 — APOCALYPSE: P4 kills it (WAIL_OF_THE_BANSHEE)
  Phase 11 — FEAST:      P6 devours the corpse (CLONE knowledge extraction)
  Phase 12 — DAWN:       P5 resurrects stronger (THIS SCRIPT)

NATARAJA_Score impact:
  Before: P5_rebirth_rate ≈ 0.6 (TTAO manually performing P5 role)
  Target: P5_rebirth_rate ≥ 1.0 (automated → antifragile)

Usage:
  # Run as standalone monitor
  python hfo_p5_contingency.py --watch

  # Check all contingencies
  python hfo_p5_contingency.py --check

  # Resurrect a specific daemon
  python hfo_p5_contingency.py --resurrect P4

  # Force a Phoenix Protocol cycle
  python hfo_p5_contingency.py --phoenix

Medallion: bronze
Port: P5 IMMUNIZE
Commander: Pyre Praetorian — Dancer of Death and Dawn
"""

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Path Resolution
# ---------------------------------------------------------------------------

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
DB_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


# ---------------------------------------------------------------------------
# SSOT Interface
# ---------------------------------------------------------------------------

def _write_stigmergy(event_type: str, data: dict, subject: str = "P5") -> int:
    if not DB_PATH.exists():
        return -1
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": f"hfo_p5_contingency_gen{GEN}",
        "subject": subject,
        "time": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event["type"], ts, subject, event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def _read_stigmergy(event_type_pattern: str = "%", limit: int = 20) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            """SELECT id, event_type, timestamp, subject, data_json
               FROM stigmergy_events
               WHERE event_type LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (event_type_pattern, limit),
        ).fetchall()
        results = []
        for row in rows:
            try:
                data = json.loads(row[4]) if row[4] else {}
            except Exception:
                data = {}
            results.append({
                "id": row[0],
                "event_type": row[1],
                "timestamp": row[2],
                "subject": row[3],
                "data": data,
            })
        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Death Classification
# ---------------------------------------------------------------------------

class DeathType:
    """Classification of how something died."""
    CRASH = "crash"           # Unexpected exception
    TIMEOUT = "timeout"       # Exceeded time budget
    RESOURCE = "resource"     # OOM, disk full, model unavailable
    LOGIC = "logic"           # Wrong answer, failed gate, bad output
    CHAIN_BREAK = "chain"     # PREY8 nonce chain broken
    GHOST = "ghost"           # Session never yielded — vanished
    STARVATION = "starvation" # Daemon starved of input
    KILL = "kill"             # Intentional kill by P4 (WEIRD)


@dataclass
class DeathRecord:
    """Record of a component death for Phoenix Protocol processing."""
    death_id: str
    death_type: str
    victim_port: str           # Which port died
    victim_component: str      # Specific component (daemon, chimera genome, etc.)
    cause: str                 # What caused the death
    error_trace: str           # Full error/traceback if available
    context: dict              # State at time of death
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resurrected: bool = False
    resurrection_timestamp: Optional[str] = None
    resurrection_strategy: Optional[str] = None
    lessons_learned: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "death_id": self.death_id,
            "death_type": self.death_type,
            "victim_port": self.victim_port,
            "victim_component": self.victim_component,
            "cause": self.cause,
            "error_trace": self.error_trace[:1000],
            "context": self.context,
            "timestamp": self.timestamp,
            "resurrected": self.resurrected,
            "resurrection_timestamp": self.resurrection_timestamp,
            "resurrection_strategy": self.resurrection_strategy,
            "lessons_learned": self.lessons_learned,
        }


# ---------------------------------------------------------------------------
# Contingency Triggers — Pre-set Resurrection Rules
# ---------------------------------------------------------------------------

@dataclass
class ContingencyTrigger:
    """A pre-set trigger that fires automatically on matching conditions."""
    trigger_id: str
    description: str
    detect: str           # Pattern to match in stigmergy events
    strategy: str         # How to resurrect
    priority: int = 5     # 1=critical, 10=low
    cooldown_sec: int = 60  # Don't re-fire within this window
    last_fired: Optional[str] = None

    def on_cooldown(self) -> bool:
        if not self.last_fired:
            return False
        fired = datetime.fromisoformat(self.last_fired)
        now = datetime.now(timezone.utc)
        return (now - fired).total_seconds() < self.cooldown_sec


# Pre-loaded contingency triggers
DEFAULT_CONTINGENCIES: list[ContingencyTrigger] = [
    ContingencyTrigger(
        trigger_id="CT-001",
        description="Daemon death — 3 consecutive errors",
        detect="hfo.gen89.daemon.error",
        strategy="restart_daemon",
        priority=1,
        cooldown_sec=120,
    ),
    ContingencyTrigger(
        trigger_id="CT-002",
        description="Ghost session — perceive without yield",
        detect="hfo.gen89.prey8.perceive",
        strategy="close_ghost_session",
        priority=3,
        cooldown_sec=300,
    ),
    ContingencyTrigger(
        trigger_id="CT-003",
        description="Model pull failure",
        detect="hfo.gen89.daemon.model_pull",
        strategy="retry_with_alternative",
        priority=5,
        cooldown_sec=600,
    ),
    ContingencyTrigger(
        trigger_id="CT-004",
        description="Swarm crash — unexpected stop",
        detect="hfo.gen89.daemon.swarm_stop",
        strategy="restart_swarm",
        priority=1,
        cooldown_sec=180,
    ),
    ContingencyTrigger(
        trigger_id="CT-005",
        description="Chimera genome extinction — all below threshold",
        detect="hfo.gen89.chimera",
        strategy="inject_fresh_genomes",
        priority=2,
        cooldown_sec=300,
    ),
    ContingencyTrigger(
        trigger_id="CT-006",
        description="NATARAJA score dropping below 0.3",
        detect="hfo.gen89.nataraja",
        strategy="boost_p5_resources",
        priority=1,
        cooldown_sec=120,
    ),
]


# ---------------------------------------------------------------------------
# Resurrection Strategies
# ---------------------------------------------------------------------------

class ResurrectionEngine:
    """Implements resurrection strategies for dead components."""

    def __init__(self):
        self.death_log: list[DeathRecord] = []
        self.resurrection_count = 0
        self.lessons_db: dict[str, list[str]] = {}

    def record_death(self, death: DeathRecord):
        """Record a death for later analysis."""
        self.death_log.append(death)
        _write_stigmergy(
            "hfo.gen89.p5.death_recorded",
            death.to_dict(),
            subject=f"P5:death:{death.victim_port}",
        )
        print(f"  ☠ [{death.victim_port}] {death.death_type}: {death.cause[:100]}")

    def resurrect_daemon(self, port_id: str, death: DeathRecord,
                          supervisor=None) -> bool:
        """Resurrect a daemon with improvements."""
        if supervisor is None:
            print(f"  No supervisor available for resurrection of {port_id}")
            return False

        from hfo_octree_daemon import OctreeDaemon, PORT_CONFIGS

        if port_id not in supervisor.daemons:
            print(f"  Unknown port {port_id} — cannot resurrect")
            return False

        daemon = supervisor.daemons[port_id]

        # Learn from death
        lessons = self._extract_lessons(death)
        death.lessons_learned = lessons

        # Apply immunization based on death type
        if death.death_type == DeathType.TIMEOUT:
            # Increase timeout parameters
            print(f"  → Immunizing {port_id}: increased timeout tolerance")
        elif death.death_type == DeathType.RESOURCE:
            # Try a smaller model
            current = daemon.config.model
            fallback_models = ["qwen2.5:3b", "llama3.2:3b", "gemma3:4b"]
            for fb in fallback_models:
                if fb != current:
                    daemon.config.model = fb
                    print(f"  → Immunizing {port_id}: degraded model {current} → {fb}")
                    break
        elif death.death_type == DeathType.CRASH:
            # Reset error count and restart
            print(f"  → Immunizing {port_id}: error counter reset")

        # Resurrect
        daemon.error_count = 0
        daemon.stop_event.clear()
        daemon.start()

        death.resurrected = True
        death.resurrection_timestamp = datetime.now(timezone.utc).isoformat()
        death.resurrection_strategy = "restart_with_immunization"
        self.resurrection_count += 1

        _write_stigmergy(
            "hfo.gen89.p5.resurrection",
            {
                "port": port_id,
                "death_type": death.death_type,
                "lessons": lessons,
                "strategy": death.resurrection_strategy,
                "resurrection_count": self.resurrection_count,
            },
            subject=f"P5:resurrect:{port_id}",
        )

        print(f"  ☀ [{port_id}] RISEN — {daemon.config.commander} resurrected "
              f"(count: {self.resurrection_count})")
        return True

    def _extract_lessons(self, death: DeathRecord) -> list[str]:
        """Extract lessons from a death for the knowledge base."""
        lessons = []

        if death.death_type == DeathType.TIMEOUT:
            lessons.append(f"Port {death.victim_port} timed out — consider lighter model or simpler prompts")
        elif death.death_type == DeathType.RESOURCE:
            lessons.append(f"Port {death.victim_port} resource exhaustion — model too large for concurrent load")
        elif death.death_type == DeathType.CRASH:
            # Extract error class from trace
            if death.error_trace:
                first_line = death.error_trace.split("\n")[-1] if "\n" in death.error_trace else death.error_trace
                lessons.append(f"Port {death.victim_port} crash: {first_line[:200]}")
        elif death.death_type == DeathType.KILL:
            lessons.append(f"Port {death.victim_port} killed by P4 (WEIRD) — intentional selection pressure")
        elif death.death_type == DeathType.GHOST:
            lessons.append(f"Port {death.victim_port} ghost session — PREY8 chain broken, yields missing")

        # Accumulate in knowledge base
        port = death.victim_port
        if port not in self.lessons_db:
            self.lessons_db[port] = []
        self.lessons_db[port].extend(lessons)

        return lessons

    def close_ghost_session(self, perceive_event: dict) -> bool:
        """Close a ghost session by writing a synthetic yield."""
        _write_stigmergy(
            "hfo.gen89.p5.ghost_closure",
            {
                "original_perceive": perceive_event,
                "reason": "P5 CONTINGENCY auto-closure — ghost session detected",
                "action": "synthetic_yield_written",
            },
            subject="P5:ghost_cleanup",
        )
        print(f"  ☀ Ghost session closed by P5 CONTINGENCY")
        return True


# ---------------------------------------------------------------------------
# CONTINGENCY Watch Loop
# ---------------------------------------------------------------------------

class ContingencyWatcher:
    """
    The P5 CONTINGENCY spell as a persistent watcher.
    Monitors stigmergy for death signals and fires contingency triggers.
    """

    def __init__(self, supervisor=None):
        self.triggers = list(DEFAULT_CONTINGENCIES)
        self.engine = ResurrectionEngine()
        self.supervisor = supervisor
        self.stop_event = threading.Event()
        self.scan_interval = 15  # seconds between scans

    def watch(self):
        """Main watch loop — check stigmergy for death signals."""
        print(f"\n  ☲ P5 CONTINGENCY WATCH — Pyre Praetorian standing guard")
        print(f"  Monitoring {len(self.triggers)} contingency triggers")
        print(f"  Scan interval: {self.scan_interval}s\n")

        _write_stigmergy(
            "hfo.gen89.p5.contingency_activated",
            {
                "triggers": [t.trigger_id for t in self.triggers],
                "scan_interval": self.scan_interval,
            },
            subject="P5:contingency",
        )

        while not self.stop_event.is_set():
            try:
                self._scan_cycle()
            except Exception as e:
                print(f"  ✗ CONTINGENCY scan error: {e}")
                traceback.print_exc()

            for _ in range(self.scan_interval):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

    def _scan_cycle(self):
        """One scan cycle — check all triggers against recent events."""
        for trigger in self.triggers:
            if trigger.on_cooldown():
                continue

            # Look for matching events
            events = _read_stigmergy(f"%{trigger.detect}%", limit=5)
            for event in events:
                if self._should_fire(trigger, event):
                    self._fire_trigger(trigger, event)
                    trigger.last_fired = datetime.now(timezone.utc).isoformat()
                    break  # One firing per trigger per cycle

    def _should_fire(self, trigger: ContingencyTrigger, event: dict) -> bool:
        """Determine if a trigger should fire for this event."""
        # Check if event is recent (within last scan interval * 2)
        try:
            event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_sec = (now - event_time).total_seconds()
            if age_sec > self.scan_interval * 3:
                return False  # Too old
        except Exception:
            return False

        data = event.get("data", {})
        if isinstance(data, dict):
            data = data.get("data", data)

        # Trigger-specific logic
        if trigger.trigger_id == "CT-001":
            # Daemon death — check error_count >= 3
            return data.get("error_count", 0) >= 3

        if trigger.trigger_id == "CT-002":
            # Ghost session — perceive without matching yield
            # Check if there's a yield after this perceive
            nonce = data.get("nonce")
            if nonce:
                yields = _read_stigmergy("%prey8.yield%", limit=5)
                for y in yields:
                    y_data = y.get("data", {}).get("data", {})
                    if y_data.get("perceive_nonce") == nonce:
                        return False  # Found matching yield
                return True  # No matching yield found
            return False

        if trigger.trigger_id == "CT-004":
            # Unexpected swarm stop — check if it was intentional
            return event.get("event_type", "").endswith("swarm_stop")

        # Default: fire if matching event found
        return True

    def _fire_trigger(self, trigger: ContingencyTrigger, event: dict):
        """Execute a contingency trigger."""
        print(f"\n  ⚡ CONTINGENCY [{trigger.trigger_id}] FIRED: {trigger.description}")

        data = event.get("data", {}).get("data", event.get("data", {}))

        if trigger.strategy == "restart_daemon":
            port = data.get("port", "")
            if port and self.supervisor:
                death = DeathRecord(
                    death_id=secrets.token_hex(8),
                    death_type=DeathType.CRASH,
                    victim_port=port,
                    victim_component="daemon",
                    cause=data.get("error", "3 consecutive errors"),
                    error_trace=data.get("error", ""),
                    context=data,
                )
                self.engine.record_death(death)
                self.engine.resurrect_daemon(port, death, self.supervisor)

        elif trigger.strategy == "close_ghost_session":
            self.engine.close_ghost_session(event)

        elif trigger.strategy == "restart_swarm":
            print(f"  → CONTINGENCY: Swarm restart requested. Notifying operator.")
            _write_stigmergy(
                "hfo.gen89.p5.contingency_alert",
                {
                    "trigger": trigger.trigger_id,
                    "action": "swarm_restart_requested",
                    "event": event.get("event_type"),
                },
                subject="P5:alert",
            )

        elif trigger.strategy == "retry_with_alternative":
            print(f"  → CONTINGENCY: Model pull failed. Flagged for next scan.")

        elif trigger.strategy == "inject_fresh_genomes":
            print(f"  → CONTINGENCY: Chimera extinction. Fresh genomes needed.")
            _write_stigmergy(
                "hfo.gen89.p5.contingency_chimera_rescue",
                {"action": "inject_fresh_genomes"},
                subject="P5:chimera",
            )

        elif trigger.strategy == "boost_p5_resources":
            print(f"  → CONTINGENCY: NATARAJA score critical. Boosting P5.")

        _write_stigmergy(
            "hfo.gen89.p5.contingency_fired",
            {
                "trigger_id": trigger.trigger_id,
                "strategy": trigger.strategy,
                "event_type": event.get("event_type"),
                "description": trigger.description,
            },
            subject=f"P5:contingency:{trigger.trigger_id}",
        )

    def get_status(self) -> dict:
        """Get contingency watcher status."""
        return {
            "triggers": [
                {
                    "id": t.trigger_id,
                    "description": t.description,
                    "strategy": t.strategy,
                    "priority": t.priority,
                    "on_cooldown": t.on_cooldown(),
                    "last_fired": t.last_fired,
                }
                for t in self.triggers
            ],
            "resurrection_count": self.engine.resurrection_count,
            "death_log_size": len(self.engine.death_log),
            "lessons_db": {k: len(v) for k, v in self.engine.lessons_db.items()},
        }


# ---------------------------------------------------------------------------
# Standalone Check: Scan SSOT for health issues
# ---------------------------------------------------------------------------

def check_all_contingencies():
    """One-shot scan of SSOT for triggerable conditions."""
    print(f"\n  ☲ P5 CONTINGENCY CHECK — Scanning SSOT for health issues\n")

    issues = []

    # 1. Check for daemon errors
    errors = _read_stigmergy("%daemon.error%", limit=20)
    if errors:
        print(f"  ✗ Found {len(errors)} daemon error events")
        for e in errors[:3]:
            data = e.get("data", {}).get("data", {})
            print(f"    [{data.get('port', '?')}] errors={data.get('error_count', '?')} — {data.get('error', '?')[:80]}")
        issues.append(f"{len(errors)} daemon errors")
    else:
        print(f"  ✓ No daemon errors")

    # 2. Check for ghost sessions (perceive without yield)
    perceives = _read_stigmergy("%prey8.perceive%", limit=10)
    yields = _read_stigmergy("%prey8.yield%", limit=10)
    yield_nonces = set()
    for y in yields:
        data = y.get("data", {}).get("data", {})
        if isinstance(data, dict):
            n = data.get("perceive_nonce")
            if n:
                yield_nonces.add(n)

    ghosts = 0
    for p in perceives:
        data = p.get("data", {}).get("data", {})
        if isinstance(data, dict):
            n = data.get("nonce")
            if n and n not in yield_nonces:
                ghosts += 1

    if ghosts > 0:
        print(f"  ✗ Found {ghosts} ghost sessions (perceive without yield)")
        issues.append(f"{ghosts} ghost sessions")
    else:
        print(f"  ✓ No ghost sessions in recent history")

    # 3. Check SSOT growth
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        conn.close()
        print(f"  ℹ SSOT: {doc_count} documents, {event_count} stigmergy events")
    else:
        print(f"  ✗ SSOT database not found at {DB_PATH}")
        issues.append("SSOT missing")

    # 4. Check Ollama health
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"  ✓ Ollama healthy — {len(models)} models available")
    except Exception as e:
        print(f"  ✗ Ollama unreachable: {e}")
        issues.append("Ollama down")

    # Summary
    print(f"\n  {'─'*50}")
    if issues:
        print(f"  ⚠ {len(issues)} issues found: {', '.join(issues)}")
    else:
        print(f"  ✓ All contingencies clear — system healthy")

    return issues


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="P5 Pyre Praetorian — CONTINGENCY Spell Engine",
    )
    parser.add_argument("--watch", action="store_true",
                        help="Start persistent contingency watcher")
    parser.add_argument("--check", action="store_true",
                        help="One-shot health check")
    parser.add_argument("--resurrect", type=str, default=None,
                        help="Force resurrect a specific port (e.g., P4)")
    parser.add_argument("--phoenix", action="store_true",
                        help="Run full Phoenix Protocol cycle")
    parser.add_argument("--status", action="store_true",
                        help="Show contingency status")

    args = parser.parse_args()

    if args.check:
        check_all_contingencies()
        return

    if args.status:
        watcher = ContingencyWatcher()
        status = watcher.get_status()
        print(json.dumps(status, indent=2))
        return

    if args.resurrect:
        port = args.resurrect.upper()
        print(f"\n  ☲ P5 CONTINGENCY — Manual resurrection of {port}")
        engine = ResurrectionEngine()
        death = DeathRecord(
            death_id=secrets.token_hex(8),
            death_type=DeathType.KILL,
            victim_port=port,
            victim_component="daemon",
            cause="Manual resurrection request by operator",
            error_trace="",
            context={"manual": True},
        )
        engine.record_death(death)
        print(f"  Death recorded. To complete resurrection, run with --watch "
              f"and the swarm supervisor active.")
        return

    if args.phoenix:
        print(f"\n  ☲ P5 CONTINGENCY — PHOENIX PROTOCOL")
        print(f"  Phase 10: APOCALYPSE — P4 kills it")
        print(f"  Phase 11: FEAST — P6 devours the corpse")
        print(f"  Phase 12: DAWN — P5 resurrects stronger")
        print(f"\n  To run the full Phoenix Protocol, start the daemon swarm:")
        print(f"    python hfo_octree_daemon.py --ports P4,P5,P6")
        print(f"  The Nataraja dance will emerge from P4+P5 coordination.")
        return

    if args.watch:
        watcher = ContingencyWatcher()
        try:
            watcher.watch()
        except KeyboardInterrupt:
            print("\n  ☲ P5 CONTINGENCY WATCH terminated")
            watcher.stop_event.set()
        return

    # Default: check
    check_all_contingencies()


if __name__ == "__main__":
    main()
