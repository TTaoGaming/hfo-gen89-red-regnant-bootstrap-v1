#!/usr/bin/env python3
"""
hfo_p5_supervisor.py — P5 Pyre Praetorian Lifecycle & Defense Supervisor
=========================================================================
v1.0 | Port: P5 IMMUNIZE | Commander: Pyre Praetorian
Powerword: DEATH WARD | School: Necromancy (protective)

Purpose:
  Lifecycle management + defense supervisor for the daemon fleet.
  Combines process health monitoring with anomaly detection to form
  the immune system of the HFO octree.

  P7 Supervisor asks: "Is it running?"
  P5 Supervisor asks: "Is it behaving? Is it healthy? Is it honest?"

Architecture:
  This is Meadows L5 — negative feedback loops for defense:
  DETECT anomaly → QUARANTINE affected daemon → GATE enforcement → HARDEN
  P5 workflow: DETECT → QUARANTINE → GATE → HARDEN → TEACH

  Two defense layers:
  Layer 1 — Lifecycle: Process age, restart trends, resource abuse
  Layer 2 — Behavioral: Gate blocks, tamper alerts, orphan sessions,
            memory loss, event quality, signal-to-noise ratio

Design Decisions:
  • Reads fleet state from P7 supervisor and/or fleet_state.json
  • Reads stigmergy_events for anomaly detection (watermark-based)
  • Does NOT restart daemons — that's P7's job. P5 REPORTS and RECOMMENDS.
  • Writes defense events that P7 can act on (separation of concerns)
  • Tracks anomaly history for trend detection (is fleet getting healthier?)
  • Computes fleet defense score (0-100) aggregating all anomaly signals

Anomaly Classes (inherited from hfo_stigmergy_watchdog.py patterns):
  D1 — Gate Block Rate:      gate_block events per daemon exceeding threshold
  D2 — Tamper Alert Rate:    tamper_alert events indicating chain compromise
  D3 — Orphan Sessions:      perceive-without-yield (memory loss indicator)
  D4 — Signal-to-Noise:      ratio of document-producing events to total events
  D5 — Daemon Flapping:      daemon restart rate exceeding threshold (from P7 data)
  D6 — Event Quality:        events missing signal_metadata or with empty data
  D7 — Stale Daemon:         daemon alive but producing no events for N minutes

Usage:
  python hfo_p5_supervisor.py                    Run defense patrol (default 5min)
  python hfo_p5_supervisor.py --interval 120     Custom patrol interval (seconds)
  python hfo_p5_supervisor.py --once             Single patrol cycle
  python hfo_p5_supervisor.py --dry-run          Detect only, no SSOT writes
  python hfo_p5_supervisor.py --status           Show defense posture
  python hfo_p5_supervisor.py --json             Machine-readable output

Medallion: bronze
Pointer key: supervisor.p5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Path Resolution ────────────────────────────────────────

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
BRONZE_RES = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources"
SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
FLEET_STATE = HFO_ROOT / ".hfo_fleet_state.json"
P7_SUPERVISOR_STATE = HFO_ROOT / ".hfo_p7_supervisor_state.json"
P5_SUPERVISOR_STATE = HFO_ROOT / ".hfo_p5_supervisor_state.json"
P5_WATERMARK = BRONZE_RES / ".p5_supervisor_watermark.json"
PYTHON = sys.executable

# ── Load .env ────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    env_path = HFO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [P5-DEF] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("p5_supervisor")

# ── Constants ────────────────────────────────────────────────

GEN = int(os.getenv("HFO_GENERATION", "89"))

# Patrol interval
DEFAULT_PATROL_INTERVAL = 300     # 5 minutes between defense patrols
MIN_PATROL_INTERVAL = 60          # 1 min minimum
MAX_PATROL_INTERVAL = 1800        # 30 min max

# Anomaly thresholds
GATE_BLOCK_RATE_THRESHOLD = 10    # >10 gate blocks per patrol window = alarm
TAMPER_RATE_THRESHOLD = 3         # >3 tamper alerts per patrol window = alarm
ORPHAN_THRESHOLD = 5              # >5 orphaned sessions = alarm
SNR_THRESHOLD = 1.0               # <1% signal-to-noise = alarm
FLAPPING_RESTART_THRESHOLD = 5    # >5 restarts in P7 state = flapping
STALE_MINUTES = 30                # daemon alive but no events for 30 min = stale
EVENT_QUALITY_THRESHOLD = 10      # >10 events missing signal_metadata = alarm

# Defense score weights (total = 100)
WEIGHT_GATE_BLOCKS = 15
WEIGHT_TAMPER = 20
WEIGHT_ORPHANS = 10
WEIGHT_SNR = 15
WEIGHT_FLAPPING = 15
WEIGHT_EVENT_QUALITY = 10
WEIGHT_STALE = 15

# Signal metadata
SUPERVISOR_PORT = "P5"
SUPERVISOR_MODEL = "none"
SUPERVISOR_NAME = "P5_Supervisor"
SUPERVISOR_PROVIDER = "system"

# ── Import dependencies ──────────────────────────────────────

sys.path.insert(0, str(BRONZE_RES))

try:
    from hfo_daemon_fleet import FLEET, AUXILIARY_FLEET, DaemonSpec
except ImportError as e:
    log.error(f"Cannot import hfo_daemon_fleet: {e}")
    sys.exit(1)

try:
    from hfo_ssot_write import write_stigmergy_event
except ImportError:
    write_stigmergy_event = None
    log.warning("hfo_ssot_write not available — events will not be persisted")

try:
    from hfo_signal_shim import build_signal_metadata
except ImportError:
    def build_signal_metadata(port, model_id, daemon_name, **kw):
        return {
            "port": port, "model_id": model_id,
            "daemon_name": daemon_name, "model_provider": "system",
            "generation": GEN,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

# Known daemon names for event attribution
DAEMON_NAMES = {spec.name for spec in list(FLEET) + list(AUXILIARY_FLEET)}
PORT_DAEMON_MAP = {spec.port: spec.name for spec in FLEET}

# ═══════════════════════════════════════════════════════════════
# Database Helpers
# ═══════════════════════════════════════════════════════════════

def _get_db() -> sqlite3.Connection:
    """Read-only connection for anomaly scanning."""
    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# ═══════════════════════════════════════════════════════════════
# Watermark — incremental scanning
# ═══════════════════════════════════════════════════════════════

def _load_watermark() -> dict:
    if P5_WATERMARK.exists():
        try:
            return json.loads(P5_WATERMARK.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_event_id": 0, "last_scan_ts": None, "scan_count": 0}


def _save_watermark(wm: dict):
    wm["last_scan_ts"] = datetime.now(timezone.utc).isoformat()
    wm["scan_count"] = wm.get("scan_count", 0) + 1
    try:
        P5_WATERMARK.write_text(json.dumps(wm, indent=2), encoding="utf-8")
    except OSError as e:
        log.warning(f"Could not save watermark: {e}")


# ═══════════════════════════════════════════════════════════════
# Anomaly Detection Functions (D1-D7)
# ═══════════════════════════════════════════════════════════════

@dataclass
class AnomalyReport:
    """Single anomaly detection result."""
    code: str            # D1-D7
    severity: str        # INFO, WARN, CRITICAL
    description: str
    count: int = 0
    details: dict = field(default_factory=dict)
    score_deduction: float = 0.0  # how much to subtract from defense score


def _detect_gate_blocks(conn: sqlite3.Connection, since_id: int) -> AnomalyReport:
    """D1 — Gate Block Rate: excessive gate_block events."""
    cur = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE id > ? AND event_type LIKE '%gate_block%'""",
        (since_id,),
    )
    count = cur.fetchone()[0]

    # Per-agent breakdown
    cur2 = conn.execute(
        """SELECT data_json FROM stigmergy_events
           WHERE id > ? AND event_type LIKE '%gate_block%'""",
        (since_id,),
    )
    agent_counts = Counter()
    for row in cur2:
        try:
            data = json.loads(row[0])
            inner = data.get("data", data)
            agent = inner.get("agent_id", inner.get("caller", "unknown"))
            agent_counts[agent] += 1
        except (json.JSONDecodeError, TypeError):
            agent_counts["parse_error"] += 1

    severity = "INFO"
    deduction = 0.0
    if count > GATE_BLOCK_RATE_THRESHOLD * 2:
        severity = "CRITICAL"
        deduction = WEIGHT_GATE_BLOCKS
    elif count > GATE_BLOCK_RATE_THRESHOLD:
        severity = "WARN"
        deduction = WEIGHT_GATE_BLOCKS * 0.5

    return AnomalyReport(
        code="D1",
        severity=severity,
        description=f"Gate blocks: {count} since last scan",
        count=count,
        details={"by_agent": dict(agent_counts.most_common(5))},
        score_deduction=deduction,
    )


def _detect_tamper_alerts(conn: sqlite3.Connection, since_id: int) -> AnomalyReport:
    """D2 — Tamper Alert Rate: chain integrity violations."""
    cur = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE id > ? AND event_type LIKE '%tamper%'""",
        (since_id,),
    )
    count = cur.fetchone()[0]

    severity = "INFO"
    deduction = 0.0
    if count > TAMPER_RATE_THRESHOLD * 2:
        severity = "CRITICAL"
        deduction = WEIGHT_TAMPER
    elif count > TAMPER_RATE_THRESHOLD:
        severity = "WARN"
        deduction = WEIGHT_TAMPER * 0.5

    return AnomalyReport(
        code="D2",
        severity=severity,
        description=f"Tamper alerts: {count} since last scan",
        count=count,
        score_deduction=deduction,
    )


def _detect_orphan_sessions(conn: sqlite3.Connection, since_id: int) -> AnomalyReport:
    """D3 — Orphan Sessions: perceive without matching yield."""
    cur = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE id > ? AND event_type LIKE '%perceive%'""",
        (since_id,),
    )
    perceive_count = cur.fetchone()[0]

    cur2 = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE id > ? AND event_type LIKE '%yield%'""",
        (since_id,),
    )
    yield_count = cur2.fetchone()[0]

    # Also check memory_loss events
    cur3 = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE id > ? AND event_type LIKE '%memory_loss%'""",
        (since_id,),
    )
    memory_loss_count = cur3.fetchone()[0]

    orphans = max(0, perceive_count - yield_count)

    severity = "INFO"
    deduction = 0.0
    if orphans > ORPHAN_THRESHOLD * 2 or memory_loss_count > ORPHAN_THRESHOLD:
        severity = "CRITICAL"
        deduction = WEIGHT_ORPHANS
    elif orphans > ORPHAN_THRESHOLD:
        severity = "WARN"
        deduction = WEIGHT_ORPHANS * 0.5

    return AnomalyReport(
        code="D3",
        severity=severity,
        description=f"Orphan sessions: {orphans} (perceive={perceive_count}, yield={yield_count}, memory_loss={memory_loss_count})",
        count=orphans,
        details={
            "perceive_count": perceive_count,
            "yield_count": yield_count,
            "memory_loss_count": memory_loss_count,
        },
        score_deduction=deduction,
    )


def _detect_snr(conn: sqlite3.Connection, since_id: int) -> AnomalyReport:
    """D4 — Signal-to-Noise Ratio: document-producing vs total events."""
    cur = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE id > ?", (since_id,),
    )
    total_events = cur.fetchone()[0]

    # Documents added since last scan
    cur2 = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE id > (SELECT COALESCE(MAX(id)-?, 0) FROM documents)",
        (total_events // 10,),  # rough approximation
    )
    # Better: count document-creating events
    cur3 = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE id > ? AND (
               event_type LIKE '%document%'
               OR event_type LIKE '%enrich%'
               OR event_type LIKE '%ingest%'
               OR event_type LIKE '%devour%'
               OR event_type LIKE '%extract%'
           )""",
        (since_id,),
    )
    signal_events = cur3.fetchone()[0]

    snr_pct = round(100.0 * signal_events / total_events, 2) if total_events > 0 else 100.0

    severity = "INFO"
    deduction = 0.0
    if total_events > 100 and snr_pct < SNR_THRESHOLD * 0.5:
        severity = "CRITICAL"
        deduction = WEIGHT_SNR
    elif total_events > 50 and snr_pct < SNR_THRESHOLD:
        severity = "WARN"
        deduction = WEIGHT_SNR * 0.5

    return AnomalyReport(
        code="D4",
        severity=severity,
        description=f"Signal-to-noise: {snr_pct}% ({signal_events} signal / {total_events} total)",
        count=total_events,
        details={"signal_events": signal_events, "total_events": total_events, "snr_pct": snr_pct},
        score_deduction=deduction,
    )


def _detect_flapping(p7_state: dict) -> AnomalyReport:
    """D5 — Daemon Flapping: excessive restarts from P7 supervisor data."""
    flapping_daemons = []
    total_restarts = 0

    for key, hdata in p7_state.get("health", {}).items():
        restarts = hdata.get("total_restarts", 0)
        total_restarts += restarts
        if restarts >= FLAPPING_RESTART_THRESHOLD:
            flapping_daemons.append({
                "daemon": key,
                "restarts": restarts,
                "uptime_pct": hdata.get("avg_uptime_pct", 0),
                "consecutive_failures": hdata.get("consecutive_failures", 0),
            })

    severity = "INFO"
    deduction = 0.0
    if len(flapping_daemons) >= 3:
        severity = "CRITICAL"
        deduction = WEIGHT_FLAPPING
    elif len(flapping_daemons) >= 1:
        severity = "WARN"
        deduction = WEIGHT_FLAPPING * 0.5

    return AnomalyReport(
        code="D5",
        severity=severity,
        description=f"Flapping daemons: {len(flapping_daemons)} (total fleet restarts: {total_restarts})",
        count=len(flapping_daemons),
        details={"flapping": flapping_daemons, "total_restarts": total_restarts},
        score_deduction=deduction,
    )


def _detect_event_quality(conn: sqlite3.Connection, since_id: int) -> AnomalyReport:
    """D6 — Event Quality: events missing signal_metadata."""
    # Count events that SHOULD have signal_metadata but don't
    cur = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE id > ?
             AND event_type NOT LIKE '%prey8%'
             AND event_type NOT LIKE '%gate_block%'
             AND event_type NOT LIKE 'system_health%'
             AND event_type NOT LIKE '%chimera%'
             AND data_json NOT LIKE '%signal_metadata%'""",
        (since_id,),
    )
    missing_sm = cur.fetchone()[0]

    # Count events with empty data
    cur2 = conn.execute(
        """SELECT COUNT(*) FROM stigmergy_events
           WHERE id > ?
             AND (data_json IS NULL OR data_json = '' OR data_json = '{}')""",
        (since_id,),
    )
    empty_data = cur2.fetchone()[0]

    total_bad = missing_sm + empty_data

    severity = "INFO"
    deduction = 0.0
    if total_bad > EVENT_QUALITY_THRESHOLD * 3:
        severity = "CRITICAL"
        deduction = WEIGHT_EVENT_QUALITY
    elif total_bad > EVENT_QUALITY_THRESHOLD:
        severity = "WARN"
        deduction = WEIGHT_EVENT_QUALITY * 0.5

    return AnomalyReport(
        code="D6",
        severity=severity,
        description=f"Event quality issues: {total_bad} ({missing_sm} missing signal_metadata, {empty_data} empty data)",
        count=total_bad,
        details={"missing_signal_metadata": missing_sm, "empty_data": empty_data},
        score_deduction=deduction,
    )


def _detect_stale_daemons(conn: sqlite3.Connection, fleet_pids: dict) -> AnomalyReport:
    """D7 — Stale Daemon: alive but producing no recent events."""
    stale_daemons = []
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)).isoformat()

    for spec in list(FLEET) + list(AUXILIARY_FLEET):
        pid = fleet_pids.get(spec.name)
        if not pid:
            continue

        # Check if PID is alive
        alive = False
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=0x08000000,
                )
                alive = str(pid) in result.stdout
            else:
                os.kill(pid, 0)
                alive = True
        except Exception:
            pass

        if not alive:
            continue

        # Daemon is alive — check if it produced recent events
        # Look for events from this daemon's port or name
        port_lower = spec.port.lower()
        name_lower = spec.name.lower()
        cur = conn.execute(
            """SELECT COUNT(*) FROM stigmergy_events
               WHERE timestamp > ?
                 AND (
                     source LIKE ? OR source LIKE ?
                     OR data_json LIKE ? OR data_json LIKE ?
                 )""",
            (cutoff, f"%{name_lower}%", f"%{port_lower}%",
             f"%{name_lower}%", f"%{port_lower}%"),
        )
        recent_events = cur.fetchone()[0]

        if recent_events == 0:
            stale_daemons.append({
                "name": spec.name,
                "port": spec.port,
                "pid": pid,
                "stale_minutes": STALE_MINUTES,
            })

    severity = "INFO"
    deduction = 0.0
    if len(stale_daemons) >= 4:
        severity = "CRITICAL"
        deduction = WEIGHT_STALE
    elif len(stale_daemons) >= 2:
        severity = "WARN"
        deduction = WEIGHT_STALE * 0.5

    return AnomalyReport(
        code="D7",
        severity=severity,
        description=f"Stale daemons: {len(stale_daemons)} alive but silent for >{STALE_MINUTES} min",
        count=len(stale_daemons),
        details={"stale": stale_daemons},
        score_deduction=deduction,
    )


# ═══════════════════════════════════════════════════════════════
# Defense Score Calculator
# ═══════════════════════════════════════════════════════════════

def compute_defense_score(anomalies: list[AnomalyReport]) -> float:
    """
    Compute fleet defense score (0-100).
    Starts at 100, each anomaly deducts based on severity.
    """
    score = 100.0
    for a in anomalies:
        score -= a.score_deduction
    return max(0.0, round(score, 1))


def grade_defense(score: float) -> str:
    """Letter grade for defense score."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


# ═══════════════════════════════════════════════════════════════
# P5 Supervisor Core
# ═══════════════════════════════════════════════════════════════

class P5Supervisor:
    """
    P5 Pyre Praetorian — Lifecycle & Defense Supervisor.

    Responsibilities:
     1. Run defense patrols detecting 7 anomaly classes (D1-D7)
     2. Compute fleet defense score (0-100)
     3. Track anomaly trends over time (is fleet getting healthier?)
     4. Write defense events to SSOT for observability
     5. Provide actionable recommendations (but never restart — that's P7)
    """

    def __init__(self, interval: int = DEFAULT_PATROL_INTERVAL,
                 dry_run: bool = False, json_mode: bool = False):
        self.interval = max(MIN_PATROL_INTERVAL, min(interval, MAX_PATROL_INTERVAL))
        self.dry_run = dry_run
        self.json_mode = json_mode
        self.cycle = 0
        self.start_ts = datetime.now(timezone.utc)
        self._shutdown = False
        self.score_history: list[float] = []

        self._load_state()

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        log.info(f"Received signal {signum} — shutting down gracefully")
        self._shutdown = True

    # ── State Persistence ────────────────────────────────────

    def _load_state(self):
        if not P5_SUPERVISOR_STATE.exists():
            return
        try:
            data = json.loads(P5_SUPERVISOR_STATE.read_text(encoding="utf-8"))
            self.cycle = data.get("cycle", 0)
            self.score_history = data.get("score_history", [])[-50:]  # keep last 50
        except (json.JSONDecodeError, OSError):
            pass

    def _save_state(self, last_score: float, last_grade: str):
        data = {
            "supervisor": "hfo_p5_supervisor",
            "version": "1.0",
            "updated": datetime.now(timezone.utc).isoformat(),
            "cycle": self.cycle,
            "interval": self.interval,
            "last_score": last_score,
            "last_grade": last_grade,
            "score_history": self.score_history[-50:],
        }
        try:
            P5_SUPERVISOR_STATE.write_text(
                json.dumps(data, indent=2, default=str), encoding="utf-8",
            )
        except OSError as e:
            log.warning(f"Failed to save P5 state: {e}")

    # ── Fleet PID Loading ────────────────────────────────────

    def _load_fleet_pids(self) -> dict[str, int]:
        if not FLEET_STATE.exists():
            return {}
        try:
            state = json.loads(FLEET_STATE.read_text(encoding="utf-8"))
            pids = {}
            for name, info in state.get("daemons", {}).items():
                pid = info.get("pid")
                if pid:
                    pids[name] = int(pid)
            return pids
        except (json.JSONDecodeError, OSError, ValueError):
            return {}

    def _load_p7_state(self) -> dict:
        if not P7_SUPERVISOR_STATE.exists():
            return {}
        try:
            return json.loads(P7_SUPERVISOR_STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    # ── SSOT Event Writing ───────────────────────────────────

    def _write_event(self, event_type: str, subject: str, data: dict):
        if self.dry_run or not write_stigmergy_event:
            return 0
        try:
            sig = build_signal_metadata(
                port=SUPERVISOR_PORT,
                model_id=SUPERVISOR_MODEL,
                daemon_name=SUPERVISOR_NAME,
            )
            return write_stigmergy_event(
                event_type=event_type,
                subject=subject,
                data=data,
                signal_metadata=sig,
            )
        except Exception as e:
            log.error(f"Failed to write event {event_type}: {e}")
            return 0

    # ── Core Patrol Cycle ────────────────────────────────────

    def patrol(self) -> dict:
        """
        Single defense patrol: scan for all 7 anomaly classes,
        compute defense score, write events.
        """
        self.cycle += 1
        now = datetime.now(timezone.utc)

        # Load watermark for incremental scanning
        wm = _load_watermark()
        since_id = wm.get("last_event_id", 0)

        # Load external state
        fleet_pids = self._load_fleet_pids()
        p7_state = self._load_p7_state()

        anomalies: list[AnomalyReport] = []
        recommendations: list[str] = []

        try:
            conn = _get_db()

            # Run all 7 detectors
            d1 = _detect_gate_blocks(conn, since_id)
            anomalies.append(d1)
            if d1.severity != "INFO":
                top_agent = list(d1.details.get("by_agent", {}).keys())[:1]
                if top_agent:
                    recommendations.append(f"Investigate gate blocks from {top_agent[0]}")

            d2 = _detect_tamper_alerts(conn, since_id)
            anomalies.append(d2)
            if d2.severity != "INFO":
                recommendations.append("Chain integrity compromised — run prey8_validate_chain")

            d3 = _detect_orphan_sessions(conn, since_id)
            anomalies.append(d3)
            if d3.severity != "INFO":
                recommendations.append(
                    f"Memory loss detected: {d3.details.get('memory_loss_count', 0)} loss events, "
                    f"{d3.count} orphans — investigate MCP server stability"
                )

            d4 = _detect_snr(conn, since_id)
            anomalies.append(d4)
            if d4.severity != "INFO":
                recommendations.append(
                    f"Signal-to-noise at {d4.details.get('snr_pct', 0)}% — "
                    "reduce patrol/heartbeat frequency or increase enrichment output"
                )

            d5 = _detect_flapping(p7_state)
            anomalies.append(d5)
            if d5.severity != "INFO":
                for fd in d5.details.get("flapping", []):
                    recommendations.append(
                        f"Flapping: {fd['daemon']} restarted {fd['restarts']}x — "
                        "check script health, model availability, or increase cooldown"
                    )

            d6 = _detect_event_quality(conn, since_id)
            anomalies.append(d6)
            if d6.severity != "INFO":
                recommendations.append(
                    f"Event quality: {d6.details.get('missing_signal_metadata', 0)} events "
                    "missing signal_metadata — fix daemon event writing"
                )

            d7 = _detect_stale_daemons(conn, fleet_pids)
            anomalies.append(d7)
            if d7.severity != "INFO":
                for sd in d7.details.get("stale", []):
                    recommendations.append(
                        f"Stale: {sd['name']} ({sd['port']}) PID {sd['pid']} alive but "
                        f"silent for >{sd['stale_minutes']}min — check if daemon main loop is stuck"
                    )

            # Update watermark
            cur = conn.execute("SELECT MAX(id) FROM stigmergy_events")
            max_id = cur.fetchone()[0] or since_id
            wm["last_event_id"] = max_id
            _save_watermark(wm)

            conn.close()

        except Exception as e:
            log.error(f"Error during patrol: {e}", exc_info=True)
            anomalies.append(AnomalyReport(
                code="DX", severity="CRITICAL",
                description=f"Patrol error: {e}",
                score_deduction=10,
            ))

        # Compute defense score
        defense_score = compute_defense_score(anomalies)
        grade = grade_defense(defense_score)
        self.score_history.append(defense_score)

        # Trend analysis
        trend = "stable"
        if len(self.score_history) >= 3:
            recent = self.score_history[-3:]
            if all(recent[i] > recent[i-1] for i in range(1, len(recent))):
                trend = "improving"
            elif all(recent[i] < recent[i-1] for i in range(1, len(recent))):
                trend = "degrading"

        # Count by severity
        crit = sum(1 for a in anomalies if a.severity == "CRITICAL")
        warn = sum(1 for a in anomalies if a.severity == "WARN")
        info = sum(1 for a in anomalies if a.severity == "INFO")

        summary = {
            "cycle": self.cycle,
            "timestamp": now.isoformat(),
            "defense_score": defense_score,
            "grade": grade,
            "trend": trend,
            "anomalies_critical": crit,
            "anomalies_warn": warn,
            "anomalies_info": info,
            "anomalies": [
                {"code": a.code, "severity": a.severity, "description": a.description,
                 "count": a.count, "details": a.details}
                for a in anomalies
            ],
            "recommendations": recommendations,
            "events_scanned_since": since_id,
        }

        # Log summary
        if not self.json_mode:
            log.info(
                f"Patrol {self.cycle}: Defense Score {defense_score}/100 (Grade {grade}, "
                f"trend={trend}) | {crit} CRITICAL, {warn} WARN, {info} INFO"
            )
            for r in recommendations:
                log.info(f"  >> {r}")

        # Write patrol event
        self._write_event(
            event_type="hfo.gen90.supervisor.p5.patrol",
            subject=f"supervisor:p5:patrol:{self.cycle}",
            data={
                "cycle": self.cycle,
                "defense_score": defense_score,
                "grade": grade,
                "trend": trend,
                "anomalies_critical": crit,
                "anomalies_warn": warn,
                "anomalies_info": info,
                "recommendations": recommendations,
                "dry_run": self.dry_run,
            },
        )

        # Write individual anomaly events for CRITICAL/WARN
        for a in anomalies:
            if a.severity in ("CRITICAL", "WARN"):
                self._write_event(
                    event_type=f"hfo.gen90.supervisor.p5.anomaly.{a.code.lower()}",
                    subject=f"supervisor:p5:anomaly:{a.code.lower()}",
                    data={
                        "code": a.code,
                        "severity": a.severity,
                        "description": a.description,
                        "count": a.count,
                        "details": a.details,
                    },
                )

        # Persist state
        self._save_state(defense_score, grade)

        return summary

    # ── Main Loop ────────────────────────────────────────────

    def run_once(self) -> dict:
        """Single patrol cycle."""
        if not self.json_mode:
            log.info(f"P5 Defense Patrol — single pass (dry_run={self.dry_run})")
        result = self.patrol()
        if self.json_mode:
            print(json.dumps(result, indent=2, default=str))
        return result

    def run_forever(self):
        """Continuous defense patrol loop."""
        log.info(f"P5 Pyre Praetorian starting — interval={self.interval}s, dry_run={self.dry_run}")
        log.info(f"7 anomaly detectors active: D1-D7")

        while not self._shutdown:
            try:
                self.patrol()
            except Exception as e:
                log.error(f"Error in patrol cycle: {e}", exc_info=True)

            # Sleep in small increments for responsive shutdown
            for _ in range(self.interval):
                if self._shutdown:
                    break
                time.sleep(1)

        log.info("P5 Pyre Praetorian shutdown complete")

    # ── Status Display ───────────────────────────────────────

    def show_status(self) -> dict:
        """Display current defense posture without running full patrol."""
        # Quick read of latest state
        last_score = 0.0
        last_grade = "?"
        if P5_SUPERVISOR_STATE.exists():
            try:
                data = json.loads(P5_SUPERVISOR_STATE.read_text(encoding="utf-8"))
                last_score = data.get("last_score", 0)
                last_grade = data.get("last_grade", "?")
            except (json.JSONDecodeError, OSError):
                pass

        # Quick anomaly snapshot
        recent_anomalies = {}
        try:
            conn = _get_db()
            for code in ["d1", "d2", "d3", "d4", "d5", "d6", "d7"]:
                cur = conn.execute(
                    """SELECT COUNT(*) FROM stigmergy_events
                       WHERE event_type LIKE ?
                       ORDER BY id DESC LIMIT 1""",
                    (f"%p5.anomaly.{code}%",),
                )
                recent_anomalies[code.upper()] = cur.fetchone()[0]
            conn.close()
        except Exception:
            pass

        result = {
            "supervisor": "P5 Pyre Praetorian",
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": self.cycle,
            "interval": self.interval,
            "last_defense_score": last_score,
            "last_grade": last_grade,
            "score_trend": self.score_history[-10:] if self.score_history else [],
            "anomaly_event_counts": recent_anomalies,
        }

        if self.json_mode:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"\n  P5 Pyre Praetorian — Defense Posture")
            print(f"  {'='*50}")
            print(f"  Cycle: {self.cycle} | Interval: {self.interval}s")
            print(f"  Defense Score: {last_score}/100 (Grade {last_grade})")
            if self.score_history:
                trend = self.score_history[-5:]
                print(f"  Score Trend: {' -> '.join(f'{s:.0f}' for s in trend)}")
            print(f"\n  Anomaly Event History:")
            for code, count in recent_anomalies.items():
                print(f"    {code}: {count} events logged")
            print()

        return result


# ═══════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P5 Pyre Praetorian — Lifecycle & Defense Supervisor"
    )
    parser.add_argument("--interval", type=int, default=DEFAULT_PATROL_INTERVAL,
                        help=f"Seconds between patrols (default: {DEFAULT_PATROL_INTERVAL})")
    parser.add_argument("--once", action="store_true",
                        help="Single patrol cycle, then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect only, no SSOT event writes")
    parser.add_argument("--status", action="store_true",
                        help="Show defense posture")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable JSON output")

    args = parser.parse_args()

    sup = P5Supervisor(
        interval=args.interval,
        dry_run=args.dry_run,
        json_mode=args.json,
    )

    if args.status:
        sup.show_status()
    elif args.once:
        sup.run_once()
    else:
        sup.run_forever()


if __name__ == "__main__":
    main()
