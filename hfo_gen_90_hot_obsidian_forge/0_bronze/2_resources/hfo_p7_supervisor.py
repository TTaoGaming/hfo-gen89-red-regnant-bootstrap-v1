#!/usr/bin/env python3
"""
hfo_p7_supervisor.py — P7 Spider Sovereign Process Supervisor
==============================================================
v1.0 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Powerword: STRANGE LOOP | School: Transmutation

Purpose:
  Process-level heartbeat supervisor for the entire 8+1 daemon fleet.
  Checks ALL daemon PIDs every CHECK_INTERVAL seconds, restarts dead ones,
  tracks uptime metrics for strange loop self-improvement.

Architecture:
  This is Meadows L5 — a negative feedback loop.
  detect_death → restart → verify_alive → log → repeat
  The strange loop adds L7 (positive feedback): trending metrics improve
  the supervisor's own behavior over time (backoff tuning, priority ordering).

Design Decisions:
  • Imports FLEET + AUXILIARY_FLEET from hfo_daemon_fleet.py (single source)
  • Uses launch_daemon() pattern (CREATE_NO_WINDOW, PYTHONIOENCODING=utf-8)
  • Writes CloudEvents via hfo_ssot_write.write_stigmergy_event()
  • Tracks per-daemon MTBF, restart count, consecutive failures
  • Exponential backoff on repeated failures (max 5 restarts before cooldown)
  • Cooldown period = 10 minutes after max consecutive failures
  • Strange loop: every TREND_INTERVAL, analyzes restart patterns and adjusts

Usage:
  python hfo_p7_supervisor.py                    Run supervisor (default 90s check)
  python hfo_p7_supervisor.py --interval 60      Custom check interval
  python hfo_p7_supervisor.py --once             Single check + restart cycle
  python hfo_p7_supervisor.py --dry-run          Check only, no restarts
  python hfo_p7_supervisor.py --status           Show fleet status and metrics
  python hfo_p7_supervisor.py --json             Machine-readable output

Medallion: bronze
Pointer key: supervisor.p7
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import signal
import sqlite3
import subprocess
import sys
import time
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
SUPERVISOR_STATE = HFO_ROOT / ".hfo_p7_supervisor_state.json"
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
    format="%(asctime)s [P7-SUP] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("p7_supervisor")

# ── Constants ────────────────────────────────────────────────

GEN = int(os.getenv("HFO_GENERATION", "89"))

# Check interval — the heartbeat frequency
DEFAULT_CHECK_INTERVAL = 90       # seconds between fleet health checks
MIN_CHECK_INTERVAL = 30           # absolute minimum
MAX_CHECK_INTERVAL = 600          # 10 min max

# Restart policy
MAX_CONSECUTIVE_FAILURES = 5      # max restarts before cooldown
COOLDOWN_SECONDS = 600            # 10 min cooldown after max failures
RESTART_VERIFY_DELAY = 3          # seconds to wait after launching before PID check

# Strange loop trending
TREND_INTERVAL = 1800             # 30 min — analyze patterns and self-tune
METRICS_HISTORY_SIZE = 100        # keep last N check cycles in memory

# Signal metadata for this supervisor
SUPERVISOR_PORT = "P7"
SUPERVISOR_MODEL = "none"         # supervisor is deterministic, no AI model
SUPERVISOR_NAME = "P7_Supervisor"
SUPERVISOR_PROVIDER = "system"

# ── Import fleet definitions ────────────────────────────────

sys.path.insert(0, str(BRONZE_RES))

try:
    from hfo_daemon_fleet import FLEET, AUXILIARY_FLEET, DaemonSpec, launch_daemon, FLEET_STATE as FLEET_STATE_PATH
except ImportError as e:
    log.error(f"Cannot import hfo_daemon_fleet: {e}")
    log.error("hfo_daemon_fleet.py must be in bronze/resources")
    sys.exit(1)

try:
    from hfo_ssot_write import write_stigmergy_event
except ImportError:
    write_stigmergy_event = None
    log.warning("hfo_ssot_write not available — events will not be persisted to SSOT")

try:
    from hfo_signal_shim import build_signal_metadata
except ImportError:
    # Minimal fallback
    def build_signal_metadata(port, model_id, daemon_name, **kw):
        return {
            "port": port, "model_id": model_id,
            "daemon_name": daemon_name, "model_provider": "system",
            "generation": GEN,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

# Prerequisite check helpers (from hfo_daemon_fleet.py patterns)
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
VERTEX_AI_ENABLED = bool(os.getenv("HFO_VERTEX_PROJECT", ""))


def _check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _check_prerequisites(spec: DaemonSpec) -> tuple[bool, str]:
    """Check if prerequisites for a daemon are met. Returns (ok, reason)."""
    if spec.requires_ollama and not _check_ollama():
        return False, "Ollama not running"
    if spec.requires_gemini and not GEMINI_API_KEY:
        return False, "No Gemini API key"
    if spec.requires_vertex and not VERTEX_AI_ENABLED:
        return False, "Vertex AI not configured"
    script_path = BRONZE_RES / spec.script
    if not script_path.exists():
        return False, f"Script not found: {spec.script}"
    return True, "OK"


# ═══════════════════════════════════════════════════════════════
# Per-Daemon Health Tracking
# ═══════════════════════════════════════════════════════════════

@dataclass
class DaemonHealth:
    """Per-daemon health metrics for strange loop trending."""
    name: str
    port: str
    pid: Optional[int] = None
    alive: bool = False
    total_restarts: int = 0
    consecutive_failures: int = 0
    last_restart_ts: Optional[str] = None
    last_seen_alive_ts: Optional[str] = None
    cooldown_until: Optional[str] = None
    uptime_samples: list[bool] = field(default_factory=list)
    # Strange loop metrics
    mtbf_seconds: float = 0.0     # Mean Time Between Failures
    avg_uptime_pct: float = 0.0   # Rolling uptime percentage

    def is_in_cooldown(self) -> bool:
        if not self.cooldown_until:
            return False
        try:
            cd = datetime.fromisoformat(self.cooldown_until)
            return datetime.now(timezone.utc) < cd
        except (ValueError, TypeError):
            return False

    def record_alive(self):
        self.alive = True
        self.consecutive_failures = 0
        self.last_seen_alive_ts = datetime.now(timezone.utc).isoformat()
        self.uptime_samples.append(True)
        self._trim_samples()

    def record_dead(self):
        self.alive = False
        self.uptime_samples.append(False)
        self._trim_samples()

    def record_restart(self, new_pid: int):
        self.total_restarts += 1
        self.pid = new_pid
        self.last_restart_ts = datetime.now(timezone.utc).isoformat()

    def record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            cd = datetime.now(timezone.utc) + timedelta(seconds=COOLDOWN_SECONDS)
            self.cooldown_until = cd.isoformat()
            log.warning(
                f"{self.name} ({self.port}): {self.consecutive_failures} consecutive "
                f"failures — cooldown until {cd.strftime('%H:%M:%S')}"
            )

    def _trim_samples(self):
        if len(self.uptime_samples) > METRICS_HISTORY_SIZE:
            self.uptime_samples = self.uptime_samples[-METRICS_HISTORY_SIZE:]

    def compute_metrics(self, interval: float):
        """Recompute rolling metrics."""
        if self.uptime_samples:
            up = sum(1 for s in self.uptime_samples if s)
            self.avg_uptime_pct = round(100.0 * up / len(self.uptime_samples), 1)
        if self.total_restarts > 0 and self.uptime_samples:
            total_time = len(self.uptime_samples) * interval
            self.mtbf_seconds = round(total_time / self.total_restarts, 1)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Don't persist uptime_samples raw — just the computed metrics
        d.pop("uptime_samples", None)
        d["sample_count"] = len(self.uptime_samples)
        return d


# ═══════════════════════════════════════════════════════════════
# Supervisor Core
# ═══════════════════════════════════════════════════════════════

class P7Supervisor:
    """
    Process-level daemon fleet supervisor.

    Responsibilities:
     1. Check all 8+1 daemon PIDs every CHECK_INTERVAL seconds
     2. Restart dead daemons (respecting prerequisites and cooldown)
     3. Track per-daemon health metrics (MTBF, uptime %, restart count)
     4. Write CloudEvents to SSOT for observability
     5. Strange loop: trend analysis adjusts behavior over time
    """

    def __init__(self, interval: int = DEFAULT_CHECK_INTERVAL,
                 dry_run: bool = False, json_mode: bool = False):
        self.interval = max(MIN_CHECK_INTERVAL, min(interval, MAX_CHECK_INTERVAL))
        self.dry_run = dry_run
        self.json_mode = json_mode
        self.cycle = 0
        self.start_ts = datetime.now(timezone.utc)
        self.last_trend_ts = datetime.now(timezone.utc)
        self._shutdown = False

        # Build health trackers for all fleet daemons
        self.health: dict[str, DaemonHealth] = {}
        all_specs = list(FLEET) + list(AUXILIARY_FLEET)
        for spec in all_specs:
            key = f"{spec.port}_{spec.name}"
            self.health[key] = DaemonHealth(name=spec.name, port=spec.port)

        # Load persisted state if available
        self._load_state()

        # Signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        log.info(f"Received signal {signum} — shutting down gracefully")
        self._shutdown = True

    # ── State Persistence ────────────────────────────────────

    def _load_state(self):
        """Load persisted supervisor state."""
        if not SUPERVISOR_STATE.exists():
            return
        try:
            data = json.loads(SUPERVISOR_STATE.read_text(encoding="utf-8"))
            for key, hdata in data.get("health", {}).items():
                if key in self.health:
                    h = self.health[key]
                    h.total_restarts = hdata.get("total_restarts", 0)
                    h.consecutive_failures = hdata.get("consecutive_failures", 0)
                    h.last_restart_ts = hdata.get("last_restart_ts")
                    h.last_seen_alive_ts = hdata.get("last_seen_alive_ts")
                    h.cooldown_until = hdata.get("cooldown_until")
                    h.mtbf_seconds = hdata.get("mtbf_seconds", 0.0)
                    h.avg_uptime_pct = hdata.get("avg_uptime_pct", 0.0)
            log.info(f"Loaded supervisor state from {SUPERVISOR_STATE.name}")
        except (json.JSONDecodeError, OSError, KeyError) as e:
            log.warning(f"Could not load supervisor state: {e}")

    def _save_state(self):
        """Persist supervisor state to disk."""
        data = {
            "supervisor": "hfo_p7_supervisor",
            "version": "1.0",
            "updated": datetime.now(timezone.utc).isoformat(),
            "cycle": self.cycle,
            "interval": self.interval,
            "health": {k: v.to_dict() for k, v in self.health.items()},
        }
        try:
            SUPERVISOR_STATE.write_text(
                json.dumps(data, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            log.error(f"Failed to save state: {e}")

    # ── PID Checking ─────────────────────────────────────────

    def _is_pid_alive(self, pid: int) -> bool:
        """Check if a process with given PID is still running."""
        if pid is None or pid <= 0:
            return False
        try:
            if sys.platform == "win32":
                # Use tasklist to check specific PID
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                )
                return str(pid) in result.stdout
            else:
                os.kill(pid, 0)
                return True
        except (subprocess.TimeoutExpired, OSError, PermissionError):
            return False

    def _load_fleet_pids(self) -> dict[str, int]:
        """Load PIDs from fleet state file."""
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

    def _update_fleet_state(self, daemon_name: str, pid: int):
        """Update fleet state file with new PID for a daemon."""
        try:
            if FLEET_STATE.exists():
                state = json.loads(FLEET_STATE.read_text(encoding="utf-8"))
            else:
                state = {"daemons": {}, "last_update": None}

            if daemon_name not in state["daemons"]:
                state["daemons"][daemon_name] = {}
            state["daemons"][daemon_name]["pid"] = pid
            state["daemons"][daemon_name]["launched"] = datetime.now(timezone.utc).isoformat()
            state["daemons"][daemon_name]["launched_by"] = "p7_supervisor"
            state["last_update"] = datetime.now(timezone.utc).isoformat()

            FLEET_STATE.write_text(
                json.dumps(state, indent=2, default=str),
                encoding="utf-8",
            )
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"Failed to update fleet state: {e}")

    # ── SSOT Event Writing ───────────────────────────────────

    def _write_event(self, event_type: str, subject: str, data: dict):
        """Write a CloudEvent to SSOT via hfo_ssot_write."""
        if not write_stigmergy_event:
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

    # ── Core Check Cycle ─────────────────────────────────────

    def check_fleet(self) -> dict:
        """
        Single check cycle: verify all daemon PIDs, restart dead ones.
        Returns summary dict.
        """
        self.cycle += 1
        now = datetime.now(timezone.utc)
        fleet_pids = self._load_fleet_pids()
        all_specs = list(FLEET) + list(AUXILIARY_FLEET)

        alive_count = 0
        dead_count = 0
        restarted = []
        skipped = []
        failed = []
        cooldown_list = []

        for spec in all_specs:
            key = f"{spec.port}_{spec.name}"
            h = self.health[key]
            pid = fleet_pids.get(spec.name) or h.pid

            # Check if alive
            is_alive = self._is_pid_alive(pid) if pid else False

            if is_alive:
                alive_count += 1
                h.pid = pid
                h.record_alive()
            else:
                dead_count += 1
                h.record_dead()

                # Should we restart?
                if self.dry_run:
                    skipped.append(spec.name)
                    continue

                if h.is_in_cooldown():
                    cooldown_list.append(spec.name)
                    log.info(f"  {spec.name} ({spec.port}): DEAD — in cooldown until {h.cooldown_until[:19]}")
                    continue

                # Check prerequisites
                prereq_ok, prereq_reason = _check_prerequisites(spec)
                if not prereq_ok:
                    skipped.append(spec.name)
                    h.record_failure()
                    log.info(f"  {spec.name} ({spec.port}): DEAD — skip restart ({prereq_reason})")
                    continue

                # Restart
                log.info(f"  {spec.name} ({spec.port}): DEAD (was PID {pid or '?'}) — restarting...")
                new_pid = launch_daemon(spec)

                if new_pid and new_pid > 0:
                    # Verify it's actually alive after brief delay
                    time.sleep(RESTART_VERIFY_DELAY)
                    if self._is_pid_alive(new_pid):
                        h.record_restart(new_pid)
                        h.consecutive_failures = 0
                        self._update_fleet_state(spec.name, new_pid)
                        restarted.append({"name": spec.name, "port": spec.port, "pid": new_pid})
                        log.info(f"  {spec.name} ({spec.port}): RESTARTED -> PID {new_pid}")
                    else:
                        h.record_failure()
                        failed.append(spec.name)
                        log.warning(f"  {spec.name} ({spec.port}): Launched PID {new_pid} but died immediately")
                else:
                    h.record_failure()
                    failed.append(spec.name)
                    log.warning(f"  {spec.name} ({spec.port}): Failed to launch")

        # Compute metrics for all daemons
        for h in self.health.values():
            h.compute_metrics(self.interval)

        summary = {
            "cycle": self.cycle,
            "timestamp": now.isoformat(),
            "interval": self.interval,
            "alive": alive_count,
            "dead": dead_count,
            "total": len(all_specs),
            "restarted": restarted,
            "skipped": skipped,
            "failed": failed,
            "cooldown": cooldown_list,
            "fleet_health_pct": round(100.0 * alive_count / len(all_specs), 1) if all_specs else 0,
        }

        # Log summary
        if not self.json_mode:
            log.info(
                f"Cycle {self.cycle}: {alive_count}/{len(all_specs)} alive "
                f"({summary['fleet_health_pct']}%), "
                f"{len(restarted)} restarted, {len(failed)} failed, "
                f"{len(cooldown_list)} in cooldown"
            )

        # Write heartbeat event
        self._write_event(
            event_type="hfo.gen90.supervisor.p7.heartbeat",
            subject=f"supervisor:p7:cycle:{self.cycle}",
            data={
                "cycle": self.cycle,
                "alive": alive_count,
                "dead": dead_count,
                "total": len(all_specs),
                "restarted": [r["name"] for r in restarted],
                "failed": failed,
                "cooldown": cooldown_list,
                "fleet_health_pct": summary["fleet_health_pct"],
                "dry_run": self.dry_run,
            },
        )

        # Write individual restart events
        for r in restarted:
            h = self.health[f"{r['port']}_{r['name']}"]
            self._write_event(
                event_type="hfo.gen90.supervisor.p7.restart",
                subject=f"supervisor:p7:restart:{r['name'].lower()}",
                data={
                    "daemon_name": r["name"],
                    "daemon_port": r["port"],
                    "new_pid": r["pid"],
                    "total_restarts": h.total_restarts,
                    "consecutive_failures": h.consecutive_failures,
                    "mtbf_seconds": h.mtbf_seconds,
                    "avg_uptime_pct": h.avg_uptime_pct,
                },
            )

        # Persist state
        self._save_state()

        return summary

    # ── Strange Loop Trending ────────────────────────────────

    def strange_loop_trend(self):
        """
        Strange loop self-improvement analysis.
        Runs every TREND_INTERVAL to detect patterns and adjust behavior.

        Current L7 positive feedback mechanisms:
        1. Track per-daemon MTBF — if a daemon keeps dying, log it as a GRUDGE
        2. Track fleet-wide uptime % — trending up = system improving
        3. Detect "flapping" daemons (restart > 10 times in trend window)
        4. Report which daemons are the most reliable vs least reliable
        """
        now = datetime.now(timezone.utc)

        # Compute fleet-wide stats
        total_restarts = sum(h.total_restarts for h in self.health.values())
        avg_uptime = 0.0
        samples = [h.avg_uptime_pct for h in self.health.values() if h.avg_uptime_pct > 0]
        if samples:
            avg_uptime = round(sum(samples) / len(samples), 1)

        # Find problem children (flapping daemons)
        flapping = []
        reliable = []
        for key, h in self.health.items():
            if h.total_restarts >= 10:
                flapping.append({
                    "name": h.name, "port": h.port,
                    "restarts": h.total_restarts,
                    "uptime_pct": h.avg_uptime_pct,
                    "mtbf_s": h.mtbf_seconds,
                })
            elif h.avg_uptime_pct >= 90:
                reliable.append({"name": h.name, "port": h.port, "uptime_pct": h.avg_uptime_pct})

        trend_data = {
            "cycle": self.cycle,
            "uptime_since": self.start_ts.isoformat(),
            "total_fleet_restarts": total_restarts,
            "avg_fleet_uptime_pct": avg_uptime,
            "flapping_daemons": flapping,
            "reliable_daemons": reliable,
            "health_by_daemon": {
                k: {"restarts": v.total_restarts, "uptime_pct": v.avg_uptime_pct,
                     "mtbf_s": v.mtbf_seconds, "consecutive_failures": v.consecutive_failures}
                for k, v in self.health.items()
            },
        }

        if not self.json_mode:
            log.info(f"Strange Loop Trend: fleet avg uptime {avg_uptime}%, "
                     f"total restarts {total_restarts}, "
                     f"{len(flapping)} flapping, {len(reliable)} reliable")

        # Write trend event
        self._write_event(
            event_type="hfo.gen90.supervisor.p7.trend",
            subject="supervisor:p7:strange_loop_trend",
            data=trend_data,
        )

        self.last_trend_ts = now
        return trend_data

    # ── Main Loop ────────────────────────────────────────────

    def run_once(self) -> dict:
        """Single check cycle."""
        if not self.json_mode:
            log.info(f"P7 Supervisor — single check (interval={self.interval}s, dry_run={self.dry_run})")
        result = self.check_fleet()
        if self.json_mode:
            print(json.dumps(result, indent=2, default=str))
        return result

    def run_forever(self):
        """Continuous supervisor loop."""
        log.info(f"P7 Supervisor starting — interval={self.interval}s, dry_run={self.dry_run}")
        log.info(f"Tracking {len(self.health)} daemons (8 primary + {len(AUXILIARY_FLEET)} auxiliary)")

        while not self._shutdown:
            try:
                self.check_fleet()

                # Strange loop trend check
                elapsed = (datetime.now(timezone.utc) - self.last_trend_ts).total_seconds()
                if elapsed >= TREND_INTERVAL:
                    self.strange_loop_trend()

            except Exception as e:
                log.error(f"Error in check cycle: {e}", exc_info=True)

            # Sleep in small increments for responsive shutdown
            for _ in range(self.interval):
                if self._shutdown:
                    break
                time.sleep(1)

        log.info("P7 Supervisor shutdown complete")
        self._save_state()

    # ── Status Display ───────────────────────────────────────

    def show_status(self) -> dict:
        """Display current fleet status and health metrics."""
        fleet_pids = self._load_fleet_pids()
        all_specs = list(FLEET) + list(AUXILIARY_FLEET)
        status_rows = []

        for spec in all_specs:
            key = f"{spec.port}_{spec.name}"
            h = self.health[key]
            pid = fleet_pids.get(spec.name) or h.pid
            alive = self._is_pid_alive(pid) if pid else False

            row = {
                "port": spec.port,
                "name": spec.name,
                "pid": pid or "-",
                "alive": alive,
                "restarts": h.total_restarts,
                "uptime_pct": h.avg_uptime_pct,
                "mtbf_s": h.mtbf_seconds,
                "consec_fail": h.consecutive_failures,
                "cooldown": h.is_in_cooldown(),
            }
            status_rows.append(row)

        alive_count = sum(1 for r in status_rows if r["alive"])
        total = len(status_rows)

        result = {
            "supervisor": "P7 Spider Sovereign",
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": self.cycle,
            "interval": self.interval,
            "fleet_alive": alive_count,
            "fleet_total": total,
            "fleet_health_pct": round(100.0 * alive_count / total, 1) if total else 0,
            "daemons": status_rows,
        }

        if self.json_mode:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"\n  P7 Spider Sovereign — Fleet Supervisor Status")
            print(f"  {'='*55}")
            print(f"  Cycle: {self.cycle} | Interval: {self.interval}s")
            print(f"  Fleet: {alive_count}/{total} alive ({result['fleet_health_pct']}%)")
            print()
            print(f"  {'Port':<6} {'Name':<12} {'PID':<8} {'Status':<8} {'Restarts':<10} {'Uptime%':<9} {'MTBF':<8}")
            print(f"  {'-'*6} {'-'*12} {'-'*8} {'-'*8} {'-'*10} {'-'*9} {'-'*8}")
            for r in status_rows:
                status = "ALIVE" if r["alive"] else ("COOL" if r["cooldown"] else "DEAD")
                mtbf = f"{r['mtbf_s']:.0f}s" if r["mtbf_s"] > 0 else "-"
                print(f"  {r['port']:<6} {r['name']:<12} {str(r['pid']):<8} {status:<8} "
                      f"{r['restarts']:<10} {r['uptime_pct']:<9.1f} {mtbf:<8}")
            print()

        return result


# ═══════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — Fleet Process Supervisor"
    )
    parser.add_argument("--interval", type=int, default=DEFAULT_CHECK_INTERVAL,
                        help=f"Seconds between checks (default: {DEFAULT_CHECK_INTERVAL})")
    parser.add_argument("--once", action="store_true",
                        help="Single check cycle, then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check only, do not restart daemons")
    parser.add_argument("--status", action="store_true",
                        help="Show fleet status and metrics")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable JSON output")

    args = parser.parse_args()

    sup = P7Supervisor(
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
