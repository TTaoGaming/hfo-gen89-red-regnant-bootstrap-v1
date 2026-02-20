#!/usr/bin/env python3
"""
hfo_p7_orchestrator.py — P7 Spider Sovereign Fleet Orchestrator
================================================================
v2.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | Major Spell: TIME_STOP

PURPOSE:
    Single command to see fleet health, manage GPU queue, enforce NPU policy,
    and take TIME_STOP snapshots for hour-by-hour resource telemetry.
    The Spider Sovereign sees all threads in the web and coordinates.

    P7 NAVIGATE workflow: MAP → LATTICE → PRUNE → SELECT → DISPATCH → VISUALIZE

CAPABILITIES:
    1. Health Check (--status):     Shows all daemon online/offline/degraded
    2. GPU Queue (--queue):         FIFO with priority — daemons request model slots
    3. Fleet Start (--start):       Coordinated boot respecting resource budget
    4. Fleet Stop (--stop):         Graceful shutdown of all daemons
    5. NPU Enforcement:             Auto-starts NPU embedder if configured
    6. TIME_STOP (--time-stop):     Snapshot all telemetry → SSOT CloudEvent
    7. Daemon Mode (--daemon):      Hourly TIME_STOP loop (background service)
    8. Snapshot History (--snapshots): Query/display TIME_STOP history + trends

TIME_STOP — P7's Major Spell:
    Freezes the runtime state into a CloudEvent written to SSOT.
    Each snapshot captures CPU, RAM, VRAM, loaded models, daemon fleet status,
    NPU state, GPU queue, and SSOT metrics. Enables hour-by-hour analysis of
    resource usage patterns — WHY does AI max out certain resources?

USAGE:
    python hfo_p7_orchestrator.py --status           # Fleet health dashboard
    python hfo_p7_orchestrator.py --start             # Boot enabled daemons
    python hfo_p7_orchestrator.py --start --dry-run   # Show what would start
    python hfo_p7_orchestrator.py --stop              # Stop all daemons
    python hfo_p7_orchestrator.py --queue             # GPU queue state
    python hfo_p7_orchestrator.py --json              # Machine-readable state
    python hfo_p7_orchestrator.py --time-stop         # One-shot TIME_STOP
    python hfo_p7_orchestrator.py --daemon            # Hourly TIME_STOP loop
    python hfo_p7_orchestrator.py --daemon --interval 1800  # Every 30 min
    python hfo_p7_orchestrator.py --snapshots         # Last 24 TIME_STOPs
    python hfo_p7_orchestrator.py --snapshots 48      # Last 48 snapshots

Pointer key: p7.orchestrator
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
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# § 0  IMPORTS — Use hfo_env_config for ALL decisions
# ═══════════════════════════════════════════════════════════════

# Ensure bronze/resources is importable
_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

from hfo_env_config import (
    HFO_ROOT, IDENTITY, DAEMON_FLAGS, PORT_MODELS, RESOURCE_BUDGET,
    OLLAMA, FEATURES, DB_PATH, BRONZE_RESOURCES, FORGE_PATH,
    MODEL_VRAM_ESTIMATES, config_snapshot, emit_config_loaded_event,
    validate as validate_config,
)

import httpx
import psutil

# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS
# ═══════════════════════════════════════════════════════════════

ORCHESTRATOR_SOURCE = f"hfo_p7_orchestrator_gen{IDENTITY.generation}_v1.0"
QUEUE_STATE_FILE = HFO_ROOT / ".hfo_gpu_queue.json"

# ═══════════════════════════════════════════════════════════════
# § 2  DAEMON REGISTRY — All known daemons
# ═══════════════════════════════════════════════════════════════

class DaemonStatus(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"


@dataclass
class DaemonEntry:
    """A known daemon in the fleet."""
    name: str               # Human name
    port: str               # P0-P7 or INFRA
    script: str             # Python filename
    flag_attr: str          # Attribute name on DAEMON_FLAGS
    needs_gpu: bool         # Requires Ollama model?
    model: Optional[str]    # Which model (from PORT_MODELS)?
    vram_gb: float          # VRAM needed (0 if no GPU)
    priority: int           # Boot priority (1=highest, 7=lowest)
    description: str        # What it does

    # Runtime state (filled by health check)
    status: DaemonStatus = DaemonStatus.OFFLINE
    pid: Optional[int] = None
    uptime_s: Optional[float] = None


# The registry — every daemon we know about, from .env config
def build_daemon_registry() -> list[DaemonEntry]:
    """Build daemon registry from hfo_env_config."""
    return [
        DaemonEntry(
            name="P5 Pyre Praetorian",
            port="P5",
            script="hfo_p5_daemon.py",
            flag_attr="p5_daemon_enabled",
            needs_gpu=True,
            model=PORT_MODELS.p5_model,
            vram_gb=RESOURCE_BUDGET.estimate_vram(PORT_MODELS.p5_model),
            priority=1,
            description="Immune system — Ring 0/1/2 gates, anomaly patrol",
        ),
        DaemonEntry(
            name="P4 Singer of Strife & Splendor",
            port="P4",
            script="hfo_singer_daemon.py",
            flag_attr="p4_singer_enabled",
            needs_gpu=False,
            model=None,
            vram_gb=0.0,
            priority=2,
            description="SSOT pattern scanner — no LLM, pure deterministic",
        ),
        DaemonEntry(
            name="P4 Song Prospector",
            port="P4",
            script="hfo_song_prospector.py",
            flag_attr="p4_prospector_enabled",
            needs_gpu=True,
            model=PORT_MODELS.p4_prospector_model,
            vram_gb=RESOURCE_BUDGET.estimate_vram(PORT_MODELS.p4_prospector_model),
            priority=5,
            description="Mines SSOT for new song candidates via LLM",
        ),
        DaemonEntry(
            name="P2 Chimera Loop",
            port="P2",
            script="hfo_p2_chimera_loop.py",
            flag_attr="p2_chimera_enabled",
            needs_gpu=True,
            model=PORT_MODELS.p2_model,
            vram_gb=RESOURCE_BUDGET.estimate_vram(PORT_MODELS.p2_model),
            priority=4,
            description="Creation engine — code/content, gated by P5",
        ),
        DaemonEntry(
            name="P6 Kraken Swarm",
            port="P6",
            script="hfo_p6_kraken_swarm.py",
            flag_attr="p6_swarm_enabled",
            needs_gpu=True,
            model=PORT_MODELS.p6_model,
            vram_gb=RESOURCE_BUDGET.estimate_vram(PORT_MODELS.p6_model),
            priority=3,
            description="9-worker enrichment swarm processing SSOT docs",
        ),
        DaemonEntry(
            name="NPU Embedder",
            port="INFRA",
            script="hfo_npu_embedder.py",
            flag_attr="npu_embedder_enabled",
            needs_gpu=False,
            model="OpenVINO/all-MiniLM-L6-v2",
            vram_gb=0.0,
            priority=1,  # Same priority as P5 — always-on
            description="Intel AI Boost NPU semantic embedding, 83 docs/sec",
        ),
        DaemonEntry(
            name="Resource Governor",
            port="INFRA",
            script="hfo_resource_governance.py",
            flag_attr="resource_governor_enabled",
            needs_gpu=False,
            model=None,
            vram_gb=0.0,
            priority=1,
            description="6-regime detector, resource pressure events",
        ),
    ]


# ═══════════════════════════════════════════════════════════════
# § 3  PROCESS DISCOVERY — What's actually running?
# ═══════════════════════════════════════════════════════════════

def discover_running_daemons() -> dict[str, dict]:
    """Scan running Python processes for known HFO daemon scripts.

    Returns dict mapping script_name -> {pid, cmd, create_time}.
    Uses psutil for cross-platform reliability.
    """
    found: dict[str, dict] = {}
    known_scripts = {d.script for d in build_daemon_registry()}

    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            info = proc.info
            if not info.get("name", "").lower().startswith("python"):
                continue
            cmdline = info.get("cmdline") or []
            cmd_str = " ".join(cmdline)
            for script in known_scripts:
                if script in cmd_str:
                    found[script] = {
                        "pid": info["pid"],
                        "cmd": cmd_str[:200],
                        "create_time": info.get("create_time", 0),
                    }
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return found


# ═══════════════════════════════════════════════════════════════
# § 4  OLLAMA STATE — What models are loaded?
# ═══════════════════════════════════════════════════════════════

def get_loaded_models() -> list[dict]:
    """Query Ollama /api/ps for currently loaded models.

    Returns list of {name, size_gb, expires_at} dicts.
    """
    try:
        resp = httpx.get(f"{OLLAMA.host}/api/ps", timeout=5.0)
        if resp.status_code != 200:
            return []
        data = resp.json()
        models = []
        for m in data.get("models", []):
            size_bytes = m.get("size", 0)
            size_gb = round(size_bytes / (1024**3), 1)
            models.append({
                "name": m.get("name", "?"),
                "size_gb": size_gb,
                "expires_at": m.get("expires_at", ""),
                "details": m.get("details", {}),
            })
        return models
    except Exception:
        return []


def get_vram_used() -> float:
    """Get total VRAM currently used by loaded models (GB)."""
    return sum(m["size_gb"] for m in get_loaded_models())


def ollama_alive() -> bool:
    """Check if Ollama server is responding."""
    try:
        resp = httpx.get(f"{OLLAMA.host}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# § 5  SSOT HEARTBEAT — Recent stigmergy events
# ═══════════════════════════════════════════════════════════════

def get_recent_heartbeats(minutes: int = 30) -> dict[str, dict]:
    """Check SSOT for recent daemon heartbeat/activity events.

    Returns dict mapping daemon_source -> {last_event, type, age_minutes}.
    """
    if not DB_PATH.exists():
        return {}

    heartbeats: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT event_type, timestamp, source, subject
               FROM stigmergy_events
               WHERE timestamp > datetime('now', ?)
               ORDER BY timestamp DESC""",
            (f"-{minutes} minutes",),
        ).fetchall()
        conn.close()

        for row in rows:
            src = row["source"] or ""
            if src not in heartbeats:
                heartbeats[src] = {
                    "last_event": row["timestamp"],
                    "type": row["event_type"],
                    "subject": row["subject"],
                }
    except Exception:
        pass

    return heartbeats


def get_ssot_stats() -> dict:
    """Quick SSOT stats: doc count, event count."""
    if not DB_PATH.exists():
        return {"docs": 0, "events": 0, "exists": False}
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        conn.close()
        return {"docs": docs, "events": events, "exists": True}
    except Exception:
        return {"docs": 0, "events": 0, "exists": False}


# ═══════════════════════════════════════════════════════════════
# § 6  HEALTH CHECK — The main dashboard
# ═══════════════════════════════════════════════════════════════

def health_check(verbose: bool = True) -> list[DaemonEntry]:
    """Run full fleet health check.

    Scans processes, Ollama, SSOT heartbeats. Updates each daemon's status.
    Returns the registry with status filled in.
    """
    registry = build_daemon_registry()
    running = discover_running_daemons()
    loaded_models = get_loaded_models()
    loaded_names = {m["name"].split(":")[0] for m in loaded_models}
    now = time.time()

    for daemon in registry:
        # Is it enabled in .env?
        if not DAEMON_FLAGS.all_daemons_enabled:
            daemon.status = DaemonStatus.DISABLED
            continue

        flag_val = getattr(DAEMON_FLAGS, daemon.flag_attr, False)
        if not flag_val:
            daemon.status = DaemonStatus.DISABLED
            continue

        # Is the process running?
        if daemon.script in running:
            proc_info = running[daemon.script]
            daemon.pid = proc_info["pid"]
            create_time = proc_info.get("create_time", 0)
            daemon.uptime_s = (now - create_time) if create_time else None

            # If it needs GPU, is the model actually loaded?
            if daemon.needs_gpu and daemon.model:
                model_base = daemon.model.split(":")[0]
                if model_base in loaded_names:
                    daemon.status = DaemonStatus.ONLINE
                else:
                    daemon.status = DaemonStatus.DEGRADED  # Running but model not loaded
            else:
                daemon.status = DaemonStatus.ONLINE
        else:
            daemon.status = DaemonStatus.OFFLINE

    return registry


def format_uptime(seconds: Optional[float]) -> str:
    """Format uptime in human-readable form."""
    if seconds is None:
        return "?"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    return f"{hours}h{mins}m"


def print_status():
    """Print the fleet health dashboard."""
    registry = health_check()
    loaded_models = get_loaded_models()
    vram_used = get_vram_used()
    is_ollama = ollama_alive()
    stats = get_ssot_stats()

    # System resources
    mem = psutil.virtual_memory()
    cpu_pct = psutil.cpu_percent(interval=0.5)
    ram_used_gb = round(mem.used / (1024**3), 1)
    ram_total_gb = round(mem.total / (1024**3), 1)
    ram_free_gb = round(mem.available / (1024**3), 1)

    print()
    print("=" * 66)
    print("  P7 SPIDER SOVEREIGN — Fleet Health Dashboard")
    print("=" * 66)

    # System overview
    print()
    print("  SYSTEM RESOURCES")
    print(f"  {'CPU':20s}  {cpu_pct:.0f}% used  (reserve: {RESOURCE_BUDGET.cpu_reserve_pct}%)")
    print(f"  {'RAM':20s}  {ram_used_gb}/{ram_total_gb} GB  ({ram_free_gb} GB free, reserve: {RESOURCE_BUDGET.ram_reserve_gb} GB)")
    print(f"  {'GPU VRAM':20s}  {vram_used}/{RESOURCE_BUDGET.vram_total_gb} GB  (budget: {RESOURCE_BUDGET.vram_budget_gb} GB)")
    print(f"  {'Ollama':20s}  {'ALIVE' if is_ollama else 'DOWN'}")
    print(f"  {'SSOT':20s}  {stats['docs']:,} docs, {stats['events']:,} events")

    # NPU status
    npu_running = "hfo_npu_embedder.py" in discover_running_daemons()
    npu_policy = "ALWAYS ON" if RESOURCE_BUDGET.npu_always_on else "on-demand"
    npu_status = "RUNNING" if npu_running else "IDLE"
    npu_icon = "[*]" if npu_running else "[!]" if RESOURCE_BUDGET.npu_always_on else "[ ]"
    print(f"  {'NPU (Intel AI Boost)':20s}  {npu_icon} {npu_status}  (policy: {npu_policy})")

    if RESOURCE_BUDGET.npu_always_on and not npu_running:
        print(f"  {'':20s}  WARNING: NPU configured ALWAYS_ON but not running!")

    # Fleet table
    print()
    print("  DAEMON FLEET")
    print(f"  {'Port':<6} {'Name':<32} {'Status':<10} {'PID':<8} {'Model':<16} {'VRAM':<6} {'Uptime':<8}")
    print(f"  {'-'*6} {'-'*32} {'-'*10} {'-'*8} {'-'*16} {'-'*6} {'-'*8}")

    status_icons = {
        DaemonStatus.ONLINE: "[*]",
        DaemonStatus.OFFLINE: "[ ]",
        DaemonStatus.DEGRADED: "[~]",
        DaemonStatus.DISABLED: "[-]",
    }

    online_count = 0
    total_vram_needed = 0.0

    for d in sorted(registry, key=lambda x: x.priority):
        icon = status_icons[d.status]
        pid_str = str(d.pid) if d.pid else "-"
        model_str = (d.model or "-")[:16]
        vram_str = f"{d.vram_gb:.1f}GB" if d.vram_gb > 0 else "-"
        uptime_str = format_uptime(d.uptime_s) if d.pid else "-"

        if d.status == DaemonStatus.ONLINE:
            online_count += 1
        if d.status in (DaemonStatus.ONLINE, DaemonStatus.DEGRADED):
            total_vram_needed += d.vram_gb

        print(f"  {d.port:<6} {icon} {d.name:<29} {d.status.value:<10} {pid_str:<8} {model_str:<16} {vram_str:<6} {uptime_str:<8}")

    total_enabled = sum(1 for d in registry if d.status != DaemonStatus.DISABLED)
    print()
    print(f"  SUMMARY: {online_count}/{total_enabled} daemons online, "
          f"VRAM: {vram_used:.1f}/{RESOURCE_BUDGET.vram_budget_gb:.1f} GB budget used")

    # Loaded models
    if loaded_models:
        print()
        print("  LOADED MODELS (Ollama)")
        for m in loaded_models:
            print(f"    {m['name']:<30} {m['size_gb']:.1f} GB")
    elif is_ollama:
        print()
        print("  LOADED MODELS: none (GPU idle)")

    # Warnings
    warnings = []
    if RESOURCE_BUDGET.npu_always_on and not npu_running:
        warnings.append("NPU embedder should be running (HFO_NPU_ALWAYS_ON=true)")
    if vram_used > RESOURCE_BUDGET.vram_budget_gb:
        warnings.append(f"VRAM {vram_used:.1f}GB exceeds budget {RESOURCE_BUDGET.vram_budget_gb:.1f}GB!")
    if ram_free_gb < RESOURCE_BUDGET.ram_reserve_gb:
        warnings.append(f"RAM free {ram_free_gb:.1f}GB below reserve {RESOURCE_BUDGET.ram_reserve_gb:.1f}GB!")
    if not is_ollama:
        warnings.append("Ollama server is not responding!")

    if warnings:
        print()
        print("  WARNINGS")
        for w in warnings:
            print(f"    [!] {w}")

    print()
    print("=" * 66)
    print()


# ═══════════════════════════════════════════════════════════════
# § 7  GPU QUEUE — Simple FIFO with priority
# ═══════════════════════════════════════════════════════════════

@dataclass
class QueueEntry:
    """A request to load a model into GPU."""
    daemon_name: str
    port: str
    model: str
    vram_gb: float
    priority: int           # 1=highest (P5), 7=lowest
    requested_at: str       # ISO timestamp
    status: str = "WAITING"  # WAITING, LOADING, LOADED, EVICTED


class GPUQueue:
    """Simple FIFO queue for GPU model access with priority ordering.

    How it works:
    1. Daemon requests a model slot via request_slot()
    2. Queue checks if VRAM budget allows it
    3. If YES → model is loaded via Ollama
    4. If NO → request waits in queue (priority-sorted)
    5. When a daemon yields → release_slot() frees the model
    6. Next highest-priority waiting request gets loaded

    State persisted to .hfo_gpu_queue.json for crash recovery.
    """

    def __init__(self):
        self.entries: list[QueueEntry] = []
        self._load_state()

    def _state_path(self) -> Path:
        return QUEUE_STATE_FILE

    def _load_state(self):
        """Load queue state from disk."""
        p = self._state_path()
        if p.exists():
            try:
                data = json.loads(p.read_text())
                self.entries = [
                    QueueEntry(**e) for e in data.get("entries", [])
                ]
            except Exception:
                self.entries = []

    def _save_state(self):
        """Persist queue state to disk."""
        data = {
            "entries": [asdict(e) for e in self.entries],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._state_path().write_text(json.dumps(data, indent=2))

    def request_slot(self, daemon_name: str, port: str, model: str,
                     vram_gb: float, priority: int) -> str:
        """Request a GPU model slot. Returns status: LOADED or WAITING."""
        # Check if already in queue
        for e in self.entries:
            if e.daemon_name == daemon_name and e.model == model:
                return e.status

        vram_used = get_vram_used()
        vram_available = RESOURCE_BUDGET.vram_budget_gb - vram_used

        entry = QueueEntry(
            daemon_name=daemon_name,
            port=port,
            model=model,
            vram_gb=vram_gb,
            priority=priority,
            requested_at=datetime.now(timezone.utc).isoformat(),
        )

        if vram_gb <= vram_available:
            # Load immediately
            if self._load_model(model):
                entry.status = "LOADED"
            else:
                entry.status = "WAITING"
        else:
            entry.status = "WAITING"

        self.entries.append(entry)
        # Sort by priority (lowest number = highest priority)
        self.entries.sort(key=lambda x: x.priority)
        self._save_state()
        return entry.status

    def release_slot(self, daemon_name: str) -> bool:
        """Release a daemon's GPU slot and process waiting queue."""
        released = False
        for e in self.entries[:]:
            if e.daemon_name == daemon_name and e.status == "LOADED":
                self._unload_model(e.model)
                self.entries.remove(e)
                released = True
                break

        if released:
            # Process waiting queue
            self._process_waiting()

        self._save_state()
        return released

    def _process_waiting(self):
        """Try to load the next waiting request(s) if VRAM allows."""
        vram_used = get_vram_used()
        for e in self.entries:
            if e.status != "WAITING":
                continue
            available = RESOURCE_BUDGET.vram_budget_gb - vram_used
            if e.vram_gb <= available:
                if self._load_model(e.model):
                    e.status = "LOADED"
                    vram_used += e.vram_gb

    def _load_model(self, model: str) -> bool:
        """Load a model into Ollama (warm it up with a trivial prompt)."""
        try:
            resp = httpx.post(
                f"{OLLAMA.host}/api/generate",
                json={"model": model, "prompt": "hi", "stream": False},
                timeout=120.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _unload_model(self, model: str) -> bool:
        """Unload a model from Ollama by setting keep_alive to 0."""
        try:
            resp = httpx.post(
                f"{OLLAMA.host}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": 0, "stream": False},
                timeout=30.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def status(self) -> list[dict]:
        """Return queue state as list of dicts."""
        return [asdict(e) for e in self.entries]

    def clear(self):
        """Clear the queue (e.g., on full fleet stop)."""
        for e in self.entries:
            if e.status == "LOADED":
                self._unload_model(e.model)
        self.entries.clear()
        self._save_state()


def print_queue():
    """Print the GPU queue dashboard."""
    queue = GPUQueue()
    entries = queue.status()
    vram_used = get_vram_used()

    print()
    print("  P7 GPU QUEUE")
    print(f"  VRAM: {vram_used:.1f}/{RESOURCE_BUDGET.vram_budget_gb:.1f} GB budget")
    print()

    if not entries:
        print("  Queue is empty — no active model requests.")
    else:
        print(f"  {'Daemon':<28} {'Port':<6} {'Model':<16} {'VRAM':<6} {'Pri':<4} {'Status':<10}")
        print(f"  {'-'*28} {'-'*6} {'-'*16} {'-'*6} {'-'*4} {'-'*10}")
        for e in entries:
            print(f"  {e['daemon_name']:<28} {e['port']:<6} {e['model']:<16} "
                  f"{e['vram_gb']:.1f}GB {e['priority']:<4} {e['status']:<10}")

    print()


# ═══════════════════════════════════════════════════════════════
# § 8  FLEET START — Coordinated boot
# ═══════════════════════════════════════════════════════════════

def start_fleet(dry_run: bool = False):
    """Start all enabled daemons in priority order, respecting resource budget.

    Boot order (by priority):
        1. NPU Embedder + Resource Governor (always-on infra, 0 VRAM)
        2. P5 Pyre Praetorian (immune system, must boot first)
        3. P4 Singer (no GPU needed)
        4. P6 Kraken Swarm (shares model with P2)
        5. P2 Chimera Loop (P5 must be up)
        6. P4 Song Prospector (low priority, VRAM permitting)
    """
    registry = build_daemon_registry()
    running = discover_running_daemons()
    queue = GPUQueue()
    vram_used = get_vram_used()

    print()
    print("  P7 SPIDER SOVEREIGN — Fleet Start")
    print("=" * 50)

    if not ollama_alive():
        print("  [!] Ollama is DOWN — cannot start GPU daemons")
        print("  Start Ollama first: ollama serve")
        return

    # Sort by priority
    enabled = [
        d for d in registry
        if getattr(DAEMON_FLAGS, d.flag_attr, False) and DAEMON_FLAGS.all_daemons_enabled
    ]
    enabled.sort(key=lambda x: x.priority)

    for daemon in enabled:
        # Skip if already running
        if daemon.script in running:
            print(f"  [*] {daemon.name:<32} already running (PID {running[daemon.script]['pid']})")
            continue

        # Check VRAM budget for GPU daemons
        if daemon.needs_gpu:
            available = RESOURCE_BUDGET.vram_budget_gb - vram_used
            if daemon.vram_gb > available:
                print(f"  [Q] {daemon.name:<32} QUEUED (needs {daemon.vram_gb}GB, "
                      f"only {available:.1f}GB available)")
                if not dry_run:
                    queue.request_slot(
                        daemon.name, daemon.port, daemon.model,
                        daemon.vram_gb, daemon.priority,
                    )
                continue
            else:
                vram_used += daemon.vram_gb

        script_path = BRONZE_RESOURCES / daemon.script
        if not script_path.exists():
            print(f"  [!] {daemon.name:<32} MISSING ({daemon.script} not found)")
            continue

        if dry_run:
            print(f"  [>] {daemon.name:<32} WOULD START "
                  f"({daemon.model or 'no model'}, {daemon.vram_gb:.1f}GB)")
        else:
            print(f"  [>] {daemon.name:<32} STARTING...", end="", flush=True)
            try:
                proc = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    cwd=str(HFO_ROOT),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32" else 0,
                )
                # Request GPU slot if needed
                if daemon.needs_gpu and daemon.model:
                    queue.request_slot(
                        daemon.name, daemon.port, daemon.model,
                        daemon.vram_gb, daemon.priority,
                    )
                print(f" PID {proc.pid}")
            except Exception as e:
                print(f" FAILED: {e}")

    # Emit start event to SSOT
    if not dry_run:
        _emit_fleet_event("hfo.gen89.p7.fleet.started", {
            "enabled_count": len(enabled),
            "vram_used": vram_used,
            "vram_budget": RESOURCE_BUDGET.vram_budget_gb,
        })

    print()
    print("  Use --status to verify fleet health")
    print()


# ═══════════════════════════════════════════════════════════════
# § 9  FLEET STOP — Graceful shutdown
# ═══════════════════════════════════════════════════════════════

def stop_fleet(dry_run: bool = False):
    """Stop all running HFO daemons."""
    running = discover_running_daemons()
    queue = GPUQueue()

    print()
    print("  P7 SPIDER SOVEREIGN — Fleet Stop")
    print("=" * 50)

    if not running:
        print("  No HFO daemons are running.")
        print()
        return

    for script, info in running.items():
        pid = info["pid"]
        if dry_run:
            print(f"  [>] WOULD STOP PID {pid}: {script}")
        else:
            try:
                p = psutil.Process(pid)
                p.terminate()
                p.wait(timeout=10)
                print(f"  [x] Stopped PID {pid}: {script}")
            except psutil.NoSuchProcess:
                print(f"  [-] PID {pid} already gone: {script}")
            except psutil.TimeoutExpired:
                try:
                    p.kill()
                    print(f"  [!] Force-killed PID {pid}: {script}")
                except Exception:
                    print(f"  [!] Failed to kill PID {pid}: {script}")
            except Exception as e:
                print(f"  [!] Error stopping PID {pid}: {e}")

    # Clear GPU queue
    if not dry_run:
        queue.clear()
        _emit_fleet_event("hfo.gen89.p7.fleet.stopped", {
            "stopped_count": len(running),
        })

    print()


# ═══════════════════════════════════════════════════════════════
# § 10  STIGMERGY — Write fleet events to SSOT
# ═══════════════════════════════════════════════════════════════

def _emit_fleet_event(event_type: str, data: dict) -> Optional[int]:
    """Write a fleet orchestration event to SSOT."""
    if not DB_PATH.exists():
        return None

    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": ORCHESTRATOR_SOURCE,
        "subject": f"P7:NAVIGATE:{event_type.split('.')[-1]}",
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_type, ts, event["subject"], event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return row_id
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# § 11  JSON OUTPUT — Machine-readable fleet state
# ═══════════════════════════════════════════════════════════════

def fleet_state_json() -> dict:
    """Return complete fleet state as JSON-serializable dict."""
    registry = health_check(verbose=False)
    loaded_models = get_loaded_models()
    mem = psutil.virtual_memory()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": {
            "cpu_pct": psutil.cpu_percent(interval=0.5),
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_free_gb": round(mem.available / (1024**3), 1),
            "vram_used_gb": get_vram_used(),
            "vram_budget_gb": RESOURCE_BUDGET.vram_budget_gb,
            "ollama_alive": ollama_alive(),
        },
        "daemons": [
            {
                "name": d.name,
                "port": d.port,
                "script": d.script,
                "status": d.status.value,
                "pid": d.pid,
                "model": d.model,
                "vram_gb": d.vram_gb,
                "uptime_s": d.uptime_s,
            }
            for d in registry
        ],
        "loaded_models": loaded_models,
        "gpu_queue": GPUQueue().status(),
        "ssot": get_ssot_stats(),
        "config": {
            "npu_always_on": RESOURCE_BUDGET.npu_always_on,
            "gpu_always_utilized": RESOURCE_BUDGET.gpu_always_utilized,
            "vram_budget_gb": RESOURCE_BUDGET.vram_budget_gb,
            "cpu_reserve_pct": RESOURCE_BUDGET.cpu_reserve_pct,
            "ram_reserve_gb": RESOURCE_BUDGET.ram_reserve_gb,
        },
    }


# ═══════════════════════════════════════════════════════════════
# § 12  TIME_STOP — P7's Major Spell (Snapshot + Stigmergy)
# ═══════════════════════════════════════════════════════════════
#
# TIME_STOP freezes the runtime state at a point in time, captures
# all telemetry, and writes it as a CloudEvent to SSOT.  Running
# hourly via --daemon mode builds hour-by-hour resource profiles.
#
# Event type:  hfo.gen89.p7.time_stop
# Subject:     P7:NAVIGATE:TIME_STOP
# Data:        Full fleet_state_json() + snapshot metadata
# ═══════════════════════════════════════════════════════════════

_TIME_STOP_EVENT_TYPE = "hfo.gen89.p7.time_stop"
_TIME_STOP_SUBJECT = "P7:NAVIGATE:TIME_STOP"

_SNAPSHOT_STATE_FILE = HFO_ROOT / ".hfo_time_stop_last.json"


def time_stop_snapshot() -> dict:
    """Execute TIME_STOP: capture full telemetry and write to SSOT.

    Returns the snapshot dict (also written as CloudEvent).
    """
    ts = datetime.now(timezone.utc).isoformat()
    fleet = fleet_state_json()

    # ── Build enriched snapshot ──────────────────────────────
    snapshot = {
        "spell": "TIME_STOP",
        "port": "P7",
        "commander": "Spider Sovereign",
        "workflow_step": "MAP→LATTICE→PRUNE→SELECT→DISPATCH→VISUALIZE",
        "timestamp": ts,
        "snapshot_id": secrets.token_hex(8),
        "telemetry": fleet,
    }

    # ── Compute diff from previous snapshot ──────────────────
    prev = _load_previous_snapshot()
    if prev:
        diff = _compute_diff(prev, fleet)
        snapshot["delta_from_previous"] = diff
        snapshot["previous_snapshot_id"] = prev.get("snapshot_id", "?")
        prev_ts = prev.get("timestamp", "")
        if prev_ts:
            try:
                prev_dt = datetime.fromisoformat(prev_ts)
                now_dt = datetime.fromisoformat(ts)
                gap_min = (now_dt - prev_dt).total_seconds() / 60
                snapshot["minutes_since_previous"] = round(gap_min, 1)
            except Exception:
                pass

    # ── Content hash for dedup ───────────────────────────────
    snapshot["content_hash"] = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True).encode()
    ).hexdigest()

    # ── Write to SSOT ────────────────────────────────────────
    row_id = _emit_fleet_event(_TIME_STOP_EVENT_TYPE, snapshot)
    snapshot["ssot_row_id"] = row_id

    # ── Save as "last snapshot" for next diff ────────────────
    _save_snapshot_state(snapshot)

    return snapshot


def _load_previous_snapshot() -> Optional[dict]:
    """Load the last TIME_STOP snapshot from disk."""
    if not _SNAPSHOT_STATE_FILE.exists():
        return None
    try:
        data = json.loads(_SNAPSHOT_STATE_FILE.read_text())
        return data
    except Exception:
        return None


def _save_snapshot_state(snapshot: dict):
    """Persist the latest snapshot for delta comparison."""
    # Save a trimmed version (just telemetry + metadata, not recursive)
    save = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "timestamp": snapshot.get("timestamp"),
        "telemetry": snapshot.get("telemetry"),
    }
    try:
        _SNAPSHOT_STATE_FILE.write_text(json.dumps(save, indent=2))
    except Exception:
        pass


def _compute_diff(prev: dict, current_fleet: dict) -> dict:
    """Compute delta between previous and current fleet state."""
    prev_tel = prev.get("telemetry", {})
    prev_sys = prev_tel.get("system", {})
    curr_sys = current_fleet.get("system", {})

    diff: dict = {}

    # Numeric deltas
    for key in ["cpu_pct", "ram_used_gb", "ram_free_gb", "vram_used_gb"]:
        old_val = prev_sys.get(key, 0)
        new_val = curr_sys.get(key, 0)
        if old_val != new_val:
            diff[key] = {
                "was": old_val,
                "now": new_val,
                "delta": round(new_val - old_val, 2),
            }

    # Daemon status changes
    prev_daemons = {d["name"]: d["status"] for d in prev_tel.get("daemons", [])}
    curr_daemons = {d["name"]: d["status"] for d in current_fleet.get("daemons", [])}
    daemon_changes = {}
    for name in set(prev_daemons) | set(curr_daemons):
        was = prev_daemons.get(name, "UNKNOWN")
        now = curr_daemons.get(name, "UNKNOWN")
        if was != now:
            daemon_changes[name] = {"was": was, "now": now}
    if daemon_changes:
        diff["daemon_status_changes"] = daemon_changes

    # Model loading changes
    prev_models = {m["name"] for m in prev_tel.get("loaded_models", [])}
    curr_models = {m["name"] for m in current_fleet.get("loaded_models", [])}
    if prev_models != curr_models:
        diff["models_loaded"] = sorted(curr_models - prev_models) or None
        diff["models_unloaded"] = sorted(prev_models - curr_models) or None

    # SSOT growth
    prev_ssot = prev_tel.get("ssot", {})
    curr_ssot = current_fleet.get("ssot", {})
    if prev_ssot.get("events", 0) != curr_ssot.get("events", 0):
        diff["ssot_events_added"] = curr_ssot.get("events", 0) - prev_ssot.get("events", 0)

    return diff


def print_time_stop():
    """Execute TIME_STOP and display a summary dashboard."""
    print()
    print("=" * 66)
    print("  P7 SPIDER SOVEREIGN — TIME_STOP ⏸")
    print("  Powerword: NAVIGATE | Spell: TIME_STOP")
    print("=" * 66)

    snap = time_stop_snapshot()
    tel = snap.get("telemetry", {})
    sys_info = tel.get("system", {})

    print()
    print(f"  Snapshot ID:  {snap['snapshot_id']}")
    print(f"  Timestamp:    {snap['timestamp']}")
    if snap.get("ssot_row_id"):
        print(f"  SSOT Row:     {snap['ssot_row_id']}")
    print()
    print("  FROZEN STATE")
    print(f"  {'CPU':20s}  {sys_info.get('cpu_pct', '?')}%")
    print(f"  {'RAM Used':20s}  {sys_info.get('ram_used_gb', '?')}/{sys_info.get('ram_total_gb', '?')} GB")
    print(f"  {'RAM Free':20s}  {sys_info.get('ram_free_gb', '?')} GB")
    print(f"  {'VRAM Used':20s}  {sys_info.get('vram_used_gb', '?')}/{tel.get('config', {}).get('vram_budget_gb', '?')} GB budget")
    print(f"  {'Ollama':20s}  {'ALIVE' if sys_info.get('ollama_alive') else 'DOWN'}")

    # Models
    models = tel.get("loaded_models", [])
    if models:
        print()
        print("  LOADED MODELS")
        for m in models:
            print(f"    {m['name']:<30} {m['size_gb']:.1f} GB")
    else:
        print(f"  {'Models':20s}  none loaded (GPU idle)")

    # Daemons
    print()
    print("  DAEMON FLEET")
    for d in tel.get("daemons", []):
        icon = {"ONLINE": "[*]", "OFFLINE": "[ ]", "DEGRADED": "[~]", "DISABLED": "[-]"}.get(d["status"], "[?]")
        print(f"    {icon} {d['name']:<32} {d['status']}")

    # Delta
    delta = snap.get("delta_from_previous")
    if delta:
        print()
        print("  CHANGES SINCE LAST SNAPSHOT")
        mins = snap.get("minutes_since_previous")
        if mins:
            print(f"    Time gap: {mins:.0f} minutes")
        for key in ["cpu_pct", "ram_used_gb", "ram_free_gb", "vram_used_gb"]:
            if key in delta:
                d = delta[key]
                sign = "+" if d["delta"] > 0 else ""
                unit = "%" if "pct" in key else "GB"
                print(f"    {key:<20s}  {d['was']} → {d['now']} ({sign}{d['delta']}{unit})")
        if "daemon_status_changes" in delta:
            for name, chg in delta["daemon_status_changes"].items():
                print(f"    {name}: {chg['was']} → {chg['now']}")
        if delta.get("models_loaded"):
            print(f"    Models loaded:   {', '.join(delta['models_loaded'])}")
        if delta.get("models_unloaded"):
            print(f"    Models unloaded: {', '.join(delta['models_unloaded'])}")
        if "ssot_events_added" in delta:
            print(f"    SSOT events added: {delta['ssot_events_added']}")
    else:
        print()
        print("  [First snapshot — no previous to compare against]")

    # SSOT
    ssot = tel.get("ssot", {})
    print()
    print(f"  SSOT: {ssot.get('docs', '?'):,} docs, {ssot.get('events', '?'):,} events")

    print()
    print("  [TIME_STOP written to SSOT as hfo.gen89.p7.time_stop]")
    print("=" * 66)
    print()


# ═══════════════════════════════════════════════════════════════
# § 13  SNAPSHOT HISTORY — Query TIME_STOP trail from SSOT
# ═══════════════════════════════════════════════════════════════

def query_snapshots(limit: int = 24) -> list[dict]:
    """Retrieve recent TIME_STOP events from SSOT.

    Returns list of snapshot data dicts, newest first.
    """
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        rows = conn.execute(
            """SELECT timestamp, data_json FROM stigmergy_events
               WHERE event_type = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (_TIME_STOP_EVENT_TYPE, limit),
        ).fetchall()
        conn.close()

        snapshots = []
        for ts, data_json in rows:
            try:
                event = json.loads(data_json)
                data = event.get("data", event)
                data["_event_timestamp"] = ts
                snapshots.append(data)
            except Exception:
                continue
        return snapshots
    except Exception:
        return []


def print_snapshots(limit: int = 24):
    """Display TIME_STOP history as a table with trend indicators."""
    snapshots = query_snapshots(limit)

    print()
    print("=" * 80)
    print("  P7 SPIDER SOVEREIGN — TIME_STOP History")
    print(f"  Showing last {limit} snapshots")
    print("=" * 80)

    if not snapshots:
        print()
        print("  No TIME_STOP snapshots found in SSOT.")
        print("  Run: python hfo_p7_orchestrator.py --time-stop")
        print()
        return

    # Table header
    print()
    print(f"  {'Timestamp':<22} {'CPU%':<7} {'RAM GB':<9} {'VRAM GB':<9} "
          f"{'Models':<8} {'Daemons':<10} {'SSOT Evts':<10}")
    print(f"  {'-'*22} {'-'*7} {'-'*9} {'-'*9} {'-'*8} {'-'*10} {'-'*10}")

    for snap in snapshots:
        tel = snap.get("telemetry", {})
        sys_info = tel.get("system", {})
        daemons = tel.get("daemons", [])
        models = tel.get("loaded_models", [])
        ssot = tel.get("ssot", {})

        ts_str = snap.get("_event_timestamp", snap.get("timestamp", "?"))[:19]
        cpu = f"{sys_info.get('cpu_pct', '?')}%"
        ram = f"{sys_info.get('ram_used_gb', '?')}/{sys_info.get('ram_total_gb', '?')}"
        vram = f"{sys_info.get('vram_used_gb', '?')}/{tel.get('config', {}).get('vram_budget_gb', '?')}"
        n_models = str(len(models))
        online = sum(1 for d in daemons if d.get("status") == "ONLINE")
        total = len(daemons)
        daemon_str = f"{online}/{total}"
        events = str(ssot.get("events", "?"))

        print(f"  {ts_str:<22} {cpu:<7} {ram:<9} {vram:<9} "
              f"{n_models:<8} {daemon_str:<10} {events:<10}")

    # Trend analysis (if >= 2 snapshots)
    if len(snapshots) >= 2:
        newest = snapshots[0].get("telemetry", {}).get("system", {})
        oldest = snapshots[-1].get("telemetry", {}).get("system", {})
        print()
        print("  TREND (oldest → newest)")

        for key, label, unit in [
            ("cpu_pct", "CPU", "%"),
            ("ram_used_gb", "RAM", "GB"),
            ("vram_used_gb", "VRAM", "GB"),
        ]:
            old_v = oldest.get(key, 0)
            new_v = newest.get(key, 0)
            delta = round(new_v - old_v, 2)
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            sign = "+" if delta > 0 else ""
            print(f"    {label:<8} {old_v} → {new_v}  {arrow} {sign}{delta}{unit}")

    print()
    print("=" * 80)
    print()


# ═══════════════════════════════════════════════════════════════
# § 14  DAEMON MODE — Hourly TIME_STOP loop
# ═══════════════════════════════════════════════════════════════

_DAEMON_RUNNING = True


def _signal_handler(signum, frame):
    """Handle graceful shutdown."""
    global _DAEMON_RUNNING
    _DAEMON_RUNNING = False
    print(f"\n  [SIGINT/SIGTERM] Shutting down daemon loop...")


def daemon_loop(interval_seconds: int = 3600):
    """Run TIME_STOP on a recurring schedule.

    Args:
        interval_seconds: Seconds between snapshots (default: 3600 = 1 hour)
    """
    global _DAEMON_RUNNING
    _DAEMON_RUNNING = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    interval_min = interval_seconds / 60

    print()
    print("=" * 66)
    print("  P7 SPIDER SOVEREIGN — Daemon Mode")
    print(f"  TIME_STOP every {interval_min:.0f} minutes ({interval_seconds}s)")
    print("  Press Ctrl+C to stop")
    print("=" * 66)
    print()

    # Emit daemon start event
    _emit_fleet_event("hfo.gen89.p7.daemon.started", {
        "mode": "TIME_STOP_LOOP",
        "interval_seconds": interval_seconds,
        "pid": os.getpid(),
    })

    snapshot_count = 0

    while _DAEMON_RUNNING:
        try:
            snapshot_count += 1
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"  [{ts}] TIME_STOP #{snapshot_count}...", end="", flush=True)

            snap = time_stop_snapshot()
            row = snap.get("ssot_row_id", "?")
            tel = snap.get("telemetry", {}).get("system", {})
            cpu = tel.get("cpu_pct", "?")
            ram = tel.get("ram_used_gb", "?")
            vram = tel.get("vram_used_gb", "?")

            print(f" ✓ CPU={cpu}% RAM={ram}GB VRAM={vram}GB → SSOT row {row}")

            # Delta highlights
            delta = snap.get("delta_from_previous")
            if delta:
                changes = []
                for key in ["cpu_pct", "ram_used_gb", "vram_used_gb"]:
                    if key in delta:
                        d = delta[key]
                        if abs(d["delta"]) > 0.1:
                            sign = "+" if d["delta"] > 0 else ""
                            changes.append(f"{key}: {sign}{d['delta']:.1f}")
                if changes:
                    print(f"    Δ {', '.join(changes)}")
                if "daemon_status_changes" in delta:
                    for name, chg in delta["daemon_status_changes"].items():
                        print(f"    Δ {name}: {chg['was']} → {chg['now']}")

        except Exception as e:
            print(f" ERROR: {e}")

        # Sleep in small increments for responsive shutdown
        for _ in range(interval_seconds):
            if not _DAEMON_RUNNING:
                break
            time.sleep(1)

    # Emit daemon stop event
    _emit_fleet_event("hfo.gen89.p7.daemon.stopped", {
        "mode": "TIME_STOP_LOOP",
        "snapshots_taken": snapshot_count,
        "pid": os.getpid(),
    })

    print(f"\n  Daemon stopped after {snapshot_count} TIME_STOP snapshot(s).")
    print()


# ═══════════════════════════════════════════════════════════════
# § 15  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — Fleet Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python hfo_p7_orchestrator.py --status           # Fleet health dashboard
              python hfo_p7_orchestrator.py --start             # Boot enabled daemons
              python hfo_p7_orchestrator.py --start --dry-run   # Show what would start
              python hfo_p7_orchestrator.py --stop              # Stop all daemons
              python hfo_p7_orchestrator.py --queue             # GPU queue state
              python hfo_p7_orchestrator.py --json              # Machine-readable state
              python hfo_p7_orchestrator.py --time-stop         # One-shot TIME_STOP
              python hfo_p7_orchestrator.py --daemon            # Hourly TIME_STOP loop
              python hfo_p7_orchestrator.py --daemon --interval 1800  # Every 30 min
              python hfo_p7_orchestrator.py --snapshots         # Last 24 TIME_STOPs
              python hfo_p7_orchestrator.py --snapshots 48      # Last 48 snapshots
        """),
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Show fleet health dashboard")
    group.add_argument("--start", action="store_true", help="Start enabled daemons")
    group.add_argument("--stop", action="store_true", help="Stop all daemons")
    group.add_argument("--queue", action="store_true", help="Show GPU queue state")
    group.add_argument("--json", action="store_true", help="Output fleet state as JSON")
    group.add_argument("--time-stop", action="store_true", dest="time_stop",
                       help="One-shot TIME_STOP — snapshot all telemetry to SSOT")
    group.add_argument("--daemon", action="store_true",
                       help="Run hourly TIME_STOP loop (background service)")
    group.add_argument("--snapshots", nargs="?", type=int, const=24, default=None,
                       metavar="N", help="Show last N TIME_STOP snapshots (default: 24)")

    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would happen without doing it")
    parser.add_argument("--interval", type=int, default=3600,
                       help="Seconds between daemon snapshots (default: 3600 = 1 hour)")

    args = parser.parse_args()

    # Validate config on every run
    errors = validate_config()
    if errors:
        print("  [!] Config validation warnings:")
        for e in errors:
            print(f"      {e}")
        print()

    if args.status:
        print_status()
    elif args.start:
        start_fleet(dry_run=args.dry_run)
    elif args.stop:
        stop_fleet(dry_run=args.dry_run)
    elif args.queue:
        print_queue()
    elif args.json:
        print(json.dumps(fleet_state_json(), indent=2))
    elif args.time_stop:
        print_time_stop()
    elif args.daemon:
        daemon_loop(interval_seconds=args.interval)
    elif args.snapshots is not None:
        print_snapshots(args.snapshots)


if __name__ == "__main__":
    import textwrap
    main()
