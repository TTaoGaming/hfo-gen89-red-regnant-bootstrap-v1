#!/usr/bin/env python3
"""
hfo_resource_monitor.py — P6 Resource-Aware Swarm Infrastructure
=================================================================
v1.0 | Gen89 | Port: P6 ASSIMILATE | Layer: Infrastructure

Provides three core capabilities:
    1. ResourceMonitor — Real-time CPU/RAM/GPU/VRAM sensing via psutil + Ollama API
    2. ResourceSlotManager — Model slot allocation with VRAM budgeting
    3. SwarmOrchestrator — Concurrent worker lifecycle with back-pressure

The Kraken Keeper imports this module to become resource-aware and multi-headed.

Architecture:
    ┌──────────────── SwarmOrchestrator ─────────────────┐
    │  ResourceMonitor (sense)  <──>  SlotManager (gate) │
    │       ↕                              ↕             │
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
    │  │Worker-0 │  │Worker-1 │  │Worker-N │  ...       │
    │  │(gemma3) │  │(qwen3)  │  │(ds-r1)  │           │
    │  └────┬────┘  └────┬────┘  └────┬────┘           │
    │       └──────────────┴──────────────┘              │
    │                     SSOT                            │
    └─────────────────────────────────────────────────────┘

Resource Signals (stigmergy-based):
    hfo.gen89.resource.request  — Another agent wants GPU/CPU
    hfo.gen89.resource.yield    — Kraken yields resources
    hfo.gen89.resource.resume   — Resources freed, resume work
    hfo.gen89.resource.snapshot — Periodic resource state dump

SAFETY:
    - VRAM budget enforced BEFORE model load (fail-closed)
    - CPU throttle: workers pause when system CPU > 85%
    - RAM throttle: workers pause when free RAM < 2 GB
    - External yield: any agent can request resources via stigmergy
    - All resource events logged to SSOT

Medallion: bronze
Port: P6 ASSIMILATE (infrastructure)
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Any

import httpx
import psutil


# ═══════════════════════════════════════════════════════════════
# CONSTANTS & THRESHOLDS
# ═══════════════════════════════════════════════════════════════

# Resource thresholds (configurable via env)
CPU_THROTTLE_PCT     = float(os.getenv("HFO_CPU_THROTTLE", "85"))    # Pause workers above this
CPU_RESUME_PCT       = float(os.getenv("HFO_CPU_RESUME", "70"))      # Resume below this
RAM_THROTTLE_GB      = float(os.getenv("HFO_RAM_THROTTLE_GB", "2"))  # Pause if free < this
RAM_RESUME_GB        = float(os.getenv("HFO_RAM_RESUME_GB", "4"))    # Resume above this
VRAM_BUDGET_GB       = float(os.getenv("HFO_VRAM_BUDGET_GB", "12"))  # Max VRAM for Kraken swarm
VRAM_RESERVE_GB      = float(os.getenv("HFO_VRAM_RESERVE_GB", "2")) # Keep free for other agents
SENSE_INTERVAL_S     = float(os.getenv("HFO_SENSE_INTERVAL", "5"))  # How often to poll resources
YIELD_CHECK_INTERVAL = float(os.getenv("HFO_YIELD_CHECK", "15"))    # How often to check stigmergy for yield requests

# Ollama
OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

# Known model VRAM sizes (approximate, in GB)
MODEL_VRAM_ESTIMATES: dict[str, float] = {
    "lfm2.5-thinking:1.2b": 1.0,
    "qwen2.5:3b":           2.0,
    "granite4:3b":          2.0,
    "llama3.2:3b":          2.2,
    "gemma3:4b":            3.0,
    "qwen2.5-coder:7b":    5.0,
    "qwen3:8b":             5.5,
    "deepseek-r1:8b":       5.5,
    "gemma3:12b":           8.0,
    "phi4:14b":             9.5,
    "qwen3:30b-a3b":        3.5,   # MoE — only active params loaded
    "deepseek-r1:32b":      20.0,
}


class ResourcePressure(Enum):
    """Resource pressure levels — drives throttling decisions."""
    IDLE       = "idle"        # Lots of headroom — can spawn more workers
    NOMINAL    = "nominal"     # Normal operating load
    ELEVATED   = "elevated"    # Approaching limits — don't spawn new
    THROTTLED  = "throttled"   # Over threshold — pause non-essential workers
    CRITICAL   = "critical"    # Near OOM / thermal — pause ALL workers
    YIELDED    = "yielded"     # External agent requested resources — paused


@dataclass
class ResourceSnapshot:
    """Point-in-time resource state."""
    timestamp: str
    cpu_pct: float           # Overall CPU % across all cores
    cpu_per_core: list[float] # Per-core CPU %
    ram_total_gb: float
    ram_used_gb: float
    ram_free_gb: float
    ram_pct: float
    vram_used_gb: float      # From Ollama /api/ps
    vram_budget_gb: float
    vram_free_gb: float      # budget - used
    loaded_models: list[dict] # [{name, size_gb, vram_gb}]
    pressure: ResourcePressure
    process_cpu_pct: float   # This process's CPU usage
    process_ram_mb: float    # This process's RAM usage

    def to_dict(self) -> dict:
        d = {
            "timestamp": self.timestamp,
            "cpu_pct": self.cpu_pct,
            "cpu_cores": len(self.cpu_per_core),
            "ram_total_gb": self.ram_total_gb,
            "ram_used_gb": self.ram_used_gb,
            "ram_free_gb": self.ram_free_gb,
            "ram_pct": self.ram_pct,
            "vram_used_gb": self.vram_used_gb,
            "vram_budget_gb": self.vram_budget_gb,
            "vram_free_gb": self.vram_free_gb,
            "loaded_models": self.loaded_models,
            "pressure": self.pressure.value,
            "process_cpu_pct": self.process_cpu_pct,
            "process_ram_mb": self.process_ram_mb,
        }
        return d


# ═══════════════════════════════════════════════════════════════
# RESOURCE MONITOR — Senses hardware state
# ═══════════════════════════════════════════════════════════════

class ResourceMonitor:
    """
    Real-time hardware resource monitor.
    Polls CPU, RAM, GPU/VRAM at configurable intervals.
    Computes pressure level for throttling decisions.
    """

    def __init__(self):
        self._process = psutil.Process()
        self._last_snapshot: Optional[ResourceSnapshot] = None
        self._yielded = False  # External yield request active
        # Initialize CPU percent tracking (first call returns 0)
        psutil.cpu_percent(percpu=True)
        self._process.cpu_percent()

    def _query_ollama_models(self) -> list[dict]:
        """Query Ollama /api/ps for currently loaded models + VRAM."""
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(f"{OLLAMA_BASE}/api/ps")
                if r.status_code != 200:
                    return []
                models = r.json().get("models", [])
                result = []
                for m in models:
                    name = m.get("name", "unknown")
                    size_gb = round(m.get("size", 0) / (1024**3), 1)
                    vram_gb = round(m.get("size_vram", 0) / (1024**3), 1)
                    result.append({
                        "name": name,
                        "size_gb": size_gb,
                        "vram_gb": vram_gb,
                    })
                return result
        except Exception:
            return []

    def _compute_pressure(
        self, cpu_pct: float, ram_free_gb: float, vram_free_gb: float,
    ) -> ResourcePressure:
        """Compute resource pressure level from current metrics."""
        if self._yielded:
            return ResourcePressure.YIELDED

        # Critical: near OOM
        if ram_free_gb < 1.0 or cpu_pct > 95:
            return ResourcePressure.CRITICAL

        # Throttled: over threshold
        if cpu_pct > CPU_THROTTLE_PCT or ram_free_gb < RAM_THROTTLE_GB:
            return ResourcePressure.THROTTLED

        # Elevated: approaching limits
        if cpu_pct > CPU_RESUME_PCT or ram_free_gb < RAM_RESUME_GB or vram_free_gb < VRAM_RESERVE_GB:
            return ResourcePressure.ELEVATED

        # Idle: lots of headroom
        if cpu_pct < 30 and ram_free_gb > 8 and vram_free_gb > 4:
            return ResourcePressure.IDLE

        return ResourcePressure.NOMINAL

    def sense(self) -> ResourceSnapshot:
        """Take a point-in-time resource snapshot."""
        now = datetime.now(timezone.utc).isoformat()

        # CPU
        cpu_per_core = psutil.cpu_percent(percpu=True)
        cpu_pct = sum(cpu_per_core) / max(len(cpu_per_core), 1)

        # RAM
        vmem = psutil.virtual_memory()
        ram_total_gb = round(vmem.total / (1024**3), 1)
        ram_used_gb = round(vmem.used / (1024**3), 1)
        ram_free_gb = round(vmem.available / (1024**3), 1)
        ram_pct = vmem.percent

        # VRAM (from Ollama)
        loaded_models = self._query_ollama_models()
        vram_used_gb = round(sum(m["vram_gb"] for m in loaded_models), 1)
        vram_free_gb = round(VRAM_BUDGET_GB - vram_used_gb, 1)

        # Process-level
        try:
            proc_cpu = self._process.cpu_percent()
            proc_ram = round(self._process.memory_info().rss / (1024**2), 1)
        except Exception:
            proc_cpu = 0.0
            proc_ram = 0.0

        # Pressure
        pressure = self._compute_pressure(cpu_pct, ram_free_gb, vram_free_gb)

        snap = ResourceSnapshot(
            timestamp=now,
            cpu_pct=round(cpu_pct, 1),
            cpu_per_core=[round(c, 1) for c in cpu_per_core],
            ram_total_gb=ram_total_gb,
            ram_used_gb=ram_used_gb,
            ram_free_gb=ram_free_gb,
            ram_pct=ram_pct,
            vram_used_gb=vram_used_gb,
            vram_budget_gb=VRAM_BUDGET_GB,
            vram_free_gb=vram_free_gb,
            loaded_models=loaded_models,
            pressure=pressure,
            process_cpu_pct=round(proc_cpu, 1),
            process_ram_mb=proc_ram,
        )
        self._last_snapshot = snap
        return snap

    @property
    def last(self) -> Optional[ResourceSnapshot]:
        return self._last_snapshot

    def set_yielded(self, yielded: bool):
        """External yield control — pause everything when another agent needs resources."""
        self._yielded = yielded

    def can_load_model(self, model_name: str) -> bool:
        """Check if VRAM budget allows loading this model."""
        snap = self._last_snapshot or self.sense()
        est = MODEL_VRAM_ESTIMATES.get(model_name, 4.0)
        return snap.vram_free_gb >= est

    def estimate_concurrent_workers(self) -> int:
        """Estimate how many concurrent workers the system can support."""
        snap = self._last_snapshot or self.sense()
        # VRAM-limited: each worker needs a model slot
        # CPU-limited: leave 2 cores for system + other agents
        vram_workers = max(1, int(snap.vram_free_gb / 3.0))  # ~3GB per small model
        cpu_workers = max(1, len(snap.cpu_per_core) - 2)
        ram_workers = max(1, int((snap.ram_free_gb - RAM_THROTTLE_GB) / 2.0))  # ~2GB per worker

        # Practical limit: Ollama serializes GPU inference, so
        # "concurrent" means concurrent CPU work + queued GPU calls
        return min(vram_workers, cpu_workers, ram_workers, 4)  # cap at 4 for safety


# ═══════════════════════════════════════════════════════════════
# RESOURCE SLOT MANAGER — Tracks model slots + VRAM budget
# ═══════════════════════════════════════════════════════════════

@dataclass
class ModelSlot:
    """A model slot in the VRAM budget."""
    name: str
    vram_gb: float
    loaded_at: str
    worker_id: str  # Which worker owns this slot
    in_use: bool = True


class SlotManager:
    """
    Manages VRAM budget for concurrent model loading.
    Tracks which models are loaded and who owns them.
    """

    def __init__(self, monitor: ResourceMonitor):
        self.monitor = monitor
        self.slots: dict[str, ModelSlot] = {}  # model_name -> slot
        self._lock = asyncio.Lock()

    def sync_from_ollama(self):
        """
        Sync slot state with what Ollama actually has loaded.
        Call at startup to recognize already-loaded models.
        """
        loaded = self.monitor._query_ollama_models()
        for m in loaded:
            name = m["name"]
            if name not in self.slots:
                self.slots[name] = ModelSlot(
                    name=name,
                    vram_gb=m["vram_gb"],
                    loaded_at=datetime.now(timezone.utc).isoformat(),
                    worker_id="ollama_preloaded",
                    in_use=False,  # Not actively claimed by a worker yet
                )

    async def acquire_slot(self, model_name: str, worker_id: str) -> bool:
        """
        Try to acquire a model slot. Returns True if model can be loaded.
        If model is already loaded in Ollama (tracked or live), allows use
        without additional VRAM budget check.
        """
        async with self._lock:
            # Already tracked in slot manager? Just reassign
            if model_name in self.slots:
                self.slots[model_name].worker_id = worker_id
                self.slots[model_name].in_use = True
                return True

            # Check if Ollama already has this model loaded (not tracked yet)
            snap = self.monitor.last or self.monitor.sense()
            already_in_ollama = any(
                m["name"] == model_name for m in snap.loaded_models
            )
            if already_in_ollama:
                # Model is loaded — register it and allow use (zero additional VRAM)
                actual_vram = next(
                    (m["vram_gb"] for m in snap.loaded_models if m["name"] == model_name),
                    MODEL_VRAM_ESTIMATES.get(model_name, 4.0),
                )
                self.slots[model_name] = ModelSlot(
                    name=model_name,
                    vram_gb=actual_vram,
                    loaded_at=datetime.now(timezone.utc).isoformat(),
                    worker_id=worker_id,
                    in_use=True,
                )
                return True

            # New model — check VRAM budget before loading
            if not self.monitor.can_load_model(model_name):
                return False

            # Reserve the slot
            est = MODEL_VRAM_ESTIMATES.get(model_name, 4.0)
            self.slots[model_name] = ModelSlot(
                name=model_name,
                vram_gb=est,
                loaded_at=datetime.now(timezone.utc).isoformat(),
                worker_id=worker_id,
                in_use=True,
            )
            return True

    async def release_slot(self, model_name: str):
        """Release a model slot (model may stay loaded in Ollama but we don't count it)."""
        async with self._lock:
            if model_name in self.slots:
                self.slots[model_name].in_use = False

    @property
    def used_vram_gb(self) -> float:
        return sum(s.vram_gb for s in self.slots.values() if s.in_use)

    @property
    def active_slots(self) -> list[dict]:
        return [
            {"name": s.name, "vram_gb": s.vram_gb, "worker": s.worker_id, "in_use": s.in_use}
            for s in self.slots.values()
        ]

    def refresh_from_ollama(self):
        """Sync slot state with what Ollama actually has loaded."""
        loaded = self.monitor._query_ollama_models()
        loaded_names = {m["name"] for m in loaded}
        # Remove slots for models no longer loaded
        stale = [k for k in self.slots if k not in loaded_names]
        for k in stale:
            del self.slots[k]


# ═══════════════════════════════════════════════════════════════
# WORKER TYPES — Different knowledge enrichment strategies
# ═══════════════════════════════════════════════════════════════

class WorkerType(Enum):
    """Enrichment worker types — each targets a different knowledge dimension."""
    BLUF            = "bluf"               # T1: Generate BLUFs
    PORT            = "port"               # T2: Classify ports
    DOCTYPE         = "doctype"            # T3: Classify doc types
    LINEAGE         = "lineage"            # T4: Mine cross-references
    PROG_SUMMARY    = "progressive_summary" # T5: Progressive summarization (multi-pass)
    KNOWLEDGE_GRAPH = "knowledge_graph"     # T6: Extract entity/relation triples
    TAG_EXPANSION   = "tag_expansion"       # T7: Enrich tags from content
    QUALITY_AUDIT   = "quality_audit"       # T8: Audit existing enrichments
    EMBEDDING       = "npu_embedding"       # T9: NPU-accelerated semantic embeddings


@dataclass
class WorkerConfig:
    """Configuration for a swarm worker."""
    worker_type: WorkerType
    model: str
    batch_size: int = 3
    interval_s: float = 120.0
    priority: int = 1        # Higher = more important, gets resources first
    cpu_only: bool = False   # Can this worker run without GPU?

    @property
    def worker_id(self) -> str:
        return f"p6_{self.worker_type.value}_{self.model.replace(':', '_')}"


# Default worker configurations — the 8^1 base swarm
DEFAULT_WORKERS: list[WorkerConfig] = [
    # Core enrichment (priority 3 — always runs)
    WorkerConfig(WorkerType.BLUF, "gemma3:4b", batch_size=3, interval_s=90, priority=3),
    WorkerConfig(WorkerType.PORT, "gemma3:4b", batch_size=5, interval_s=120, priority=3),

    # Secondary enrichment (priority 2 — runs when resources available)
    WorkerConfig(WorkerType.DOCTYPE, "gemma3:4b", batch_size=3, interval_s=180, priority=2),
    WorkerConfig(WorkerType.LINEAGE, "gemma3:4b", batch_size=2, interval_s=300, priority=2, cpu_only=True),
    WorkerConfig(WorkerType.TAG_EXPANSION, "gemma3:4b", batch_size=3, interval_s=240, priority=2),

    # Advanced enrichment (priority 1 — only when idle)
    WorkerConfig(WorkerType.PROG_SUMMARY, "qwen3:8b", batch_size=1, interval_s=600, priority=1),
    WorkerConfig(WorkerType.KNOWLEDGE_GRAPH, "gemma3:4b", batch_size=2, interval_s=450, priority=1),
    WorkerConfig(WorkerType.QUALITY_AUDIT, "gemma3:4b", batch_size=5, interval_s=900, priority=1, cpu_only=True),
]


# ═══════════════════════════════════════════════════════════════
# SWARM ORCHESTRATOR — Manages concurrent workers
# ═══════════════════════════════════════════════════════════════

class SwarmOrchestrator:
    """
    Manages concurrent enrichment workers with resource awareness.

    The orchestrator:
    1. Monitors resources every SENSE_INTERVAL_S seconds
    2. Decides which workers to run based on pressure level + priority
    3. Pauses/resumes workers based on resource availability
    4. Checks stigmergy for external resource requests
    5. Emits resource snapshots to SSOT for observability
    """

    def __init__(
        self,
        db_path: Path,
        worker_configs: list[WorkerConfig] | None = None,
        dry_run: bool = False,
        max_concurrent: int = 0,  # 0 = auto-detect
    ):
        self.db_path = db_path
        self.dry_run = dry_run
        self.monitor = ResourceMonitor()
        self.slots = SlotManager(self.monitor)
        self.worker_configs = worker_configs or DEFAULT_WORKERS
        self._running = True
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Start unpaused

        # Auto-detect max concurrent
        if max_concurrent <= 0:
            self._max_concurrent = self.monitor.estimate_concurrent_workers()
        else:
            self._max_concurrent = max_concurrent

        # Worker state tracking
        self._active_workers: dict[str, asyncio.Task] = {}
        self._worker_stats: dict[str, dict] = {}

        # Stats
        self.stats = {
            "start_time": datetime.now(timezone.utc).isoformat(),
            "total_sense_cycles": 0,
            "throttle_events": 0,
            "yield_events": 0,
            "resume_events": 0,
            "workers_spawned": 0,
            "workers_killed": 0,
        }

    def stop(self):
        self._running = False
        self._pause_event.set()  # Wake anyone waiting

    async def check_stigmergy_yields(self):
        """
        Check SSOT stigmergy for resource yield requests from other agents.
        Other agents can write hfo.gen89.resource.request events.
        The Kraken responds by pausing workers and yielding GPU.
        """
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            # Look for recent resource requests not yet honored
            rows = conn.execute(
                """SELECT id, data_json, timestamp FROM stigmergy_events
                   WHERE event_type = 'hfo.gen89.resource.request'
                   AND timestamp > datetime('now', '-5 minutes')
                   ORDER BY timestamp DESC LIMIT 1""",
            ).fetchall()
            conn.close()

            if rows:
                data = json.loads(rows[0][1]) if rows[0][1] else {}
                req_data = data.get("data", data)
                # Check if we've already yielded for this request
                if not self._paused:
                    duration_s = req_data.get("duration_s", 60)
                    requestor = req_data.get("requestor", "unknown")
                    print(f"  [YIELD] Resource request from {requestor} — pausing for {duration_s}s")
                    self._paused = True
                    self._pause_event.clear()
                    self.monitor.set_yielded(True)
                    self.stats["yield_events"] += 1

                    # Log yield event
                    if not self.dry_run:
                        self._log_resource_event(
                            "hfo.gen89.resource.yield",
                            f"YIELD:to:{requestor}",
                            {"requestor": requestor, "duration_s": duration_s},
                        )

                    # Schedule resume
                    asyncio.get_event_loop().call_later(
                        duration_s, self._resume_from_yield
                    )
            elif self._paused and self.monitor._yielded:
                # No active requests — resume
                self._resume_from_yield()

        except Exception as e:
            pass  # Don't crash on stigmergy read failures

    def _resume_from_yield(self):
        """Resume after yield period."""
        if self._paused:
            self._paused = False
            self._pause_event.set()
            self.monitor.set_yielded(False)
            self.stats["resume_events"] += 1
            print("  [RESUME] Resource yield period ended — resuming workers")

    def _log_resource_event(self, event_type: str, subject: str, data: dict):
        """Write a resource event to SSOT."""
        try:
            import hashlib, secrets
            conn = sqlite3.connect(str(self.db_path), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")

            now = datetime.now(timezone.utc).isoformat()
            trace_id = secrets.token_hex(16)
            span_id = secrets.token_hex(8)
            event = {
                "specversion": "1.0",
                "type": event_type,
                "source": "hfo_p6_kraken_swarm_gen89",
                "subject": subject,
                "time": now,
                "data": data,
            }
            content_hash = hashlib.sha256(
                json.dumps(event, sort_keys=True).encode()
            ).hexdigest()
            conn.execute(
                """INSERT OR IGNORE INTO stigmergy_events
                   (event_type, timestamp, subject, source, data_json, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_type, now, subject, "hfo_p6_kraken_swarm_gen89",
                 json.dumps(event), content_hash),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_active_worker_count(self) -> int:
        """Count workers with active asyncio tasks."""
        return sum(1 for t in self._active_workers.values() if not t.done())

    def select_workers_for_pressure(
        self, pressure: ResourcePressure,
    ) -> list[WorkerConfig]:
        """
        Select which workers should run at current pressure level.
        Higher pressure = fewer workers, only high priority.
        """
        if pressure == ResourcePressure.YIELDED:
            return []  # Everything stops

        if pressure == ResourcePressure.CRITICAL:
            return []  # Everything stops

        if pressure == ResourcePressure.THROTTLED:
            # Only priority 3 (core) workers
            return [w for w in self.worker_configs if w.priority >= 3]

        if pressure == ResourcePressure.ELEVATED:
            # Priority 2+ workers
            return [w for w in self.worker_configs if w.priority >= 2]

        # NOMINAL or IDLE — all workers
        return list(self.worker_configs)

    async def sense_loop(self):
        """
        Continuous resource sensing loop.
        Adjusts worker pool based on resource pressure.
        """
        while self._running:
            snap = self.monitor.sense()
            self.stats["total_sense_cycles"] += 1

            # Check for external yield requests
            await self.check_stigmergy_yields()

            # Log periodic snapshots (every 12 cycles = ~1 minute)
            if self.stats["total_sense_cycles"] % 12 == 0 and not self.dry_run:
                self._log_resource_event(
                    "hfo.gen89.resource.snapshot",
                    f"RESOURCE:pressure:{snap.pressure.value}",
                    snap.to_dict(),
                )

            # Adjust pause state based on pressure
            was_paused = self._paused
            if snap.pressure in (ResourcePressure.CRITICAL, ResourcePressure.YIELDED):
                if not self._paused:
                    self._paused = True
                    self._pause_event.clear()
                    self.stats["throttle_events"] += 1
                    print(f"  [THROTTLE] Pressure={snap.pressure.value} — pausing workers")
            elif snap.pressure in (ResourcePressure.IDLE, ResourcePressure.NOMINAL):
                if self._paused and not self.monitor._yielded:
                    self._paused = False
                    self._pause_event.set()
                    self.stats["resume_events"] += 1
                    print(f"  [UNTHROTTLE] Pressure={snap.pressure.value} — resuming workers")

            await asyncio.sleep(SENSE_INTERVAL_S)

    async def wait_if_paused(self):
        """Workers call this to block if the swarm is paused."""
        await self._pause_event.wait()

    def get_status(self) -> dict:
        """Get comprehensive swarm status."""
        snap = self.monitor.sense()
        return {
            "running": self._running,
            "paused": self._paused,
            "pressure": snap.pressure.value,
            "max_concurrent": self._max_concurrent,
            "active_workers": self.get_active_worker_count(),
            "total_workers_configured": len(self.worker_configs),
            "workers": [
                {
                    "id": w.worker_id,
                    "type": w.worker_type.value,
                    "model": w.model,
                    "priority": w.priority,
                    "active": w.worker_id in self._active_workers
                        and not self._active_workers[w.worker_id].done(),
                }
                for w in self.worker_configs
            ],
            "resources": snap.to_dict(),
            "model_slots": self.slots.active_slots,
            "orchestrator_stats": dict(self.stats),
        }


# ═══════════════════════════════════════════════════════════════
# STANDALONE RESOURCE CLI (for testing and monitoring)
# ═══════════════════════════════════════════════════════════════

def _cli_status():
    """Print a resource snapshot to stdout."""
    mon = ResourceMonitor()
    # Wait a beat for CPU measurement
    time.sleep(0.5)
    snap = mon.sense()
    d = snap.to_dict()

    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  HFO RESOURCE MONITOR — System Status                    ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    print(f"  Pressure: {snap.pressure.value.upper()}")
    print()
    print(f"  CPU:  {snap.cpu_pct:.1f}%  ({len(snap.cpu_per_core)} cores)")
    print(f"  RAM:  {snap.ram_used_gb:.1f} / {snap.ram_total_gb:.1f} GB  ({snap.ram_pct:.0f}%)  Free: {snap.ram_free_gb:.1f} GB")
    print(f"  VRAM: {snap.vram_used_gb:.1f} / {snap.vram_budget_gb:.1f} GB budget  Free: {snap.vram_free_gb:.1f} GB")
    print()
    if snap.loaded_models:
        print("  Loaded Ollama Models:")
        for m in snap.loaded_models:
            print(f"    {m['name']:30s}  {m['vram_gb']:.1f} GB VRAM")
    else:
        print("  No Ollama models loaded")
    print()
    print(f"  Thresholds:")
    print(f"    CPU throttle: {CPU_THROTTLE_PCT}% → resume at {CPU_RESUME_PCT}%")
    print(f"    RAM throttle: free < {RAM_THROTTLE_GB} GB → resume at > {RAM_RESUME_GB} GB")
    print(f"    VRAM budget: {VRAM_BUDGET_GB} GB (reserve {VRAM_RESERVE_GB} GB for other agents)")
    print()
    print(f"  Estimated concurrent workers: {mon.estimate_concurrent_workers()}")
    print()
    print(f"  Process: CPU {snap.process_cpu_pct:.1f}%, RAM {snap.process_ram_mb:.0f} MB")


def _cli_json():
    """Print resource snapshot as JSON."""
    mon = ResourceMonitor()
    time.sleep(0.5)
    snap = mon.sense()
    print(json.dumps(snap.to_dict(), indent=2))


if __name__ == "__main__":
    import sys
    if "--json" in sys.argv:
        _cli_json()
    else:
        _cli_status()
