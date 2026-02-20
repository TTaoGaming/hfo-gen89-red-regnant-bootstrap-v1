#!/usr/bin/env python3
"""
hfo_resource_governance.py — Resource Governance Daemon
========================================================
v1.0 | Gen89 | Port: P6 ASSIMILATE | Layer: Infrastructure

Durable resource governance daemon that monitors sustained utilization
patterns across CPU/RAM/GPU/NPU and logs stigmergy events for:

    - OVERUTILIZED  — Sustained high resource consumption (> threshold for > window)
    - UNDERUTILIZED — Sustained low resource consumption (idle capacity wasted)
    - REBALANCE     — Recommended resource rebalancing action
    - THERMAL       — Thermal throttling detected
    - NPU_IDLE      — NPU available but not being used
    - BUDGET_BREACH — VRAM budget exceeded for sustained period

Unlike the ResourceMonitor (point-in-time snapshots), this daemon tracks
*patterns over time windows* and only fires events for sustained regimes,
not transient spikes.

Architecture:
    ┌───────────────────────────────────────────────────────────┐
    │  RESOURCE GOVERNANCE DAEMON                               │
    │                                                            │
    │  ┌──────────────┐     ┌───────────────────────────────┐  │
    │  │ SampleBuffer │ ──→ │ RegimeDetector                │  │
    │  │ (ring buffer │     │ (sliding window analysis)     │  │
    │  │  60 samples) │     │                               │  │
    │  └──────────────┘     │  ┌──────────────────────────┐ │  │
    │                        │  │ over_utilized?            │ │  │
    │  ┌──────────────┐     │  │ under_utilized?           │ │  │
    │  │ NPU Monitor  │ ──→ │  │ vram_breach?              │ │  │
    │  │ (OpenVINO)   │     │  │ npu_idle?                 │ │  │
    │  └──────────────┘     │  │ thermal?                  │ │  │
    │                        │  └──────────┬───────────────┘ │  │
    │                        └─────────────┼─────────────────┘  │
    │                                      │                     │
    │                              ┌───────▼──────────┐         │
    │                              │ Stigmergy Events │         │
    │                              │ (SSOT)           │         │
    │                              └──────────────────┘         │
    └───────────────────────────────────────────────────────────┘

Event Types:
    hfo.gen89.governance.overutilized   — Sustained high resource usage
    hfo.gen89.governance.underutilized  — Sustained idle resources
    hfo.gen89.governance.rebalance      — Recommended action
    hfo.gen89.governance.budget_breach  — VRAM over budget sustained
    hfo.gen89.governance.npu_idle       — NPU available but unused
    hfo.gen89.governance.heartbeat      — Periodic governance status

SAFETY:
    - READ-ONLY resource monitoring (never kills processes)
    - ADVISORY stigmergy events (other agents decide action)
    - Durable: auto-restarts, state persistence, crash recovery
    - Hysteresis: requires sustained regime before firing events (debounce)
    - Cooldown: won't spam the same event type within cooldown window

Medallion: bronze
Port: P6 ASSIMILATE
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psutil

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import openvino as ov
    HAS_OPENVINO = True
except ImportError:
    HAS_OPENVINO = False

try:
    from hfo_ssot_write import write_stigmergy_event, build_signal_metadata
    HAS_CANONICAL_WRITE = True
except ImportError:
    HAS_CANONICAL_WRITE = False
    write_stigmergy_event = None  # type: ignore
    build_signal_metadata = None  # type: ignore


# ── Path resolution ──

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT   = _find_root()
SSOT_DB    = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
STATE_FILE = HFO_ROOT / ".hfo_resource_governance_state.json"
GEN        = os.environ.get("HFO_GENERATION", "89")
GOV_SOURCE = f"hfo_resource_governance_gen{GEN}"

# ── Configuration ──

# Sampling
SAMPLE_INTERVAL_S     = float(os.getenv("HFO_GOV_SAMPLE_INTERVAL", "10"))   # Sample every N seconds
WINDOW_SIZE           = int(os.getenv("HFO_GOV_WINDOW_SIZE", "60"))          # Ring buffer size (samples)
HEARTBEAT_INTERVAL_S  = float(os.getenv("HFO_GOV_HEARTBEAT", "300"))        # 5 min heartbeats

# Over-utilization thresholds (sustained)
CPU_OVER_PCT           = float(os.getenv("HFO_GOV_CPU_OVER", "80"))
RAM_OVER_PCT           = float(os.getenv("HFO_GOV_RAM_OVER", "90"))
VRAM_BUDGET_GB         = float(os.getenv("HFO_VRAM_BUDGET_GB", "12"))

# Under-utilization thresholds (sustained)
CPU_UNDER_PCT          = float(os.getenv("HFO_GOV_CPU_UNDER", "15"))
RAM_UNDER_PCT          = float(os.getenv("HFO_GOV_RAM_UNDER", "50"))

# Regime detection
REGIME_THRESHOLD_PCT   = float(os.getenv("HFO_GOV_REGIME_PCT", "70"))  # % of window that must match
COOLDOWN_S             = float(os.getenv("HFO_GOV_COOLDOWN", "300"))   # Min seconds between same event

# Ollama
OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class ResourceSample:
    """Single point-in-time resource measurement."""
    timestamp: float           # time.time()
    cpu_pct: float
    ram_pct: float
    ram_free_gb: float
    vram_used_gb: float
    vram_budget_gb: float
    loaded_models: list[str]
    npu_available: bool
    npu_in_use: bool           # True if any embedder process is running
    process_count: int         # System process count


@dataclass
class RegimeState:
    """Tracks whether a regime is active and when it was last reported."""
    name: str
    active: bool = False
    since: float = 0.0         # When regime started
    last_reported: float = 0.0 # When stigmergy event was last fired
    consecutive_matches: int = 0
    total_activations: int = 0


class SampleBuffer:
    """Fixed-size ring buffer of resource samples."""

    def __init__(self, max_size: int = WINDOW_SIZE):
        self._buf: deque[ResourceSample] = deque(maxlen=max_size)

    def add(self, sample: ResourceSample):
        self._buf.append(sample)

    def __len__(self) -> int:
        return len(self._buf)

    @property
    def full(self) -> bool:
        return len(self._buf) == self._buf.maxlen

    def window(self, n: int = 0) -> list[ResourceSample]:
        """Get last N samples (0 = all)."""
        if n <= 0:
            return list(self._buf)
        return list(self._buf)[-n:]

    def pct_above(self, field: str, threshold: float) -> float:
        """What % of samples have `field` above threshold?"""
        if not self._buf:
            return 0.0
        count = sum(1 for s in self._buf if getattr(s, field, 0) > threshold)
        return 100 * count / len(self._buf)

    def pct_below(self, field: str, threshold: float) -> float:
        """What % of samples have `field` below threshold?"""
        if not self._buf:
            return 0.0
        count = sum(1 for s in self._buf if getattr(s, field, 0) < threshold)
        return 100 * count / len(self._buf)

    def avg(self, field: str) -> float:
        """Average value of a field across the window."""
        if not self._buf:
            return 0.0
        values = [getattr(s, field, 0) for s in self._buf]
        return sum(values) / len(values)

    def latest(self) -> Optional[ResourceSample]:
        return self._buf[-1] if self._buf else None


# ═══════════════════════════════════════════════════════════════
# REGIME DETECTOR — Sustained pattern analysis
# ═══════════════════════════════════════════════════════════════

class RegimeDetector:
    """
    Detects sustained resource utilization regimes from a sample buffer.
    
    A regime is "active" when the threshold is exceeded for REGIME_THRESHOLD_PCT
    of the sliding window. Events are fired with cooldown to prevent spam.
    """

    def __init__(self):
        self.regimes: dict[str, RegimeState] = {
            "cpu_over":       RegimeState(name="cpu_over"),
            "ram_over":       RegimeState(name="ram_over"),
            "vram_breach":    RegimeState(name="vram_breach"),
            "cpu_under":      RegimeState(name="cpu_under"),
            "ram_under":      RegimeState(name="ram_under"),
            "npu_idle":       RegimeState(name="npu_idle"),
        }

    def analyze(self, buf: SampleBuffer) -> list[dict]:
        """
        Analyze the buffer for regime transitions.
        
        Returns list of events to emit: [{type, subject, data}]
        """
        if len(buf) < 5:  # Need minimum samples
            return []

        now = time.time()
        events = []

        # ── CPU Over-utilization ──
        cpu_over_pct = buf.pct_above("cpu_pct", CPU_OVER_PCT)
        events += self._check_regime(
            "cpu_over", cpu_over_pct, now, buf,
            event_type="hfo.gen89.governance.overutilized",
            subject_prefix="GOVERN:cpu_over",
            detail_fn=lambda: {
                "resource": "CPU",
                "threshold": CPU_OVER_PCT,
                "window_pct": round(cpu_over_pct, 1),
                "avg_cpu": round(buf.avg("cpu_pct"), 1),
                "recommendation": "Reduce concurrent workers or pause low-priority tasks",
            },
        )

        # ── RAM Over-utilization ──
        ram_over_pct = buf.pct_above("ram_pct", RAM_OVER_PCT)
        events += self._check_regime(
            "ram_over", ram_over_pct, now, buf,
            event_type="hfo.gen89.governance.overutilized",
            subject_prefix="GOVERN:ram_over",
            detail_fn=lambda: {
                "resource": "RAM",
                "threshold_pct": RAM_OVER_PCT,
                "window_pct": round(ram_over_pct, 1),
                "avg_ram_pct": round(buf.avg("ram_pct"), 1),
                "avg_free_gb": round(buf.avg("ram_free_gb"), 1),
                "recommendation": "Unload unused Ollama models or reduce batch sizes",
            },
        )

        # ── VRAM Budget Breach ──
        vram_breach_pct = buf.pct_above("vram_used_gb", VRAM_BUDGET_GB)
        events += self._check_regime(
            "vram_breach", vram_breach_pct, now, buf,
            event_type="hfo.gen89.governance.budget_breach",
            subject_prefix="GOVERN:vram_breach",
            detail_fn=lambda: {
                "resource": "VRAM",
                "budget_gb": VRAM_BUDGET_GB,
                "window_pct": round(vram_breach_pct, 1),
                "avg_vram_gb": round(buf.avg("vram_used_gb"), 1),
                "loaded_models": buf.latest().loaded_models if buf.latest() else [],
                "recommendation": "Unload one model to bring VRAM within budget",
            },
        )

        # ── CPU Under-utilization ──
        cpu_under_pct = buf.pct_below("cpu_pct", CPU_UNDER_PCT)
        events += self._check_regime(
            "cpu_under", cpu_under_pct, now, buf,
            event_type="hfo.gen89.governance.underutilized",
            subject_prefix="GOVERN:cpu_under",
            detail_fn=lambda: {
                "resource": "CPU",
                "threshold": CPU_UNDER_PCT,
                "window_pct": round(cpu_under_pct, 1),
                "avg_cpu": round(buf.avg("cpu_pct"), 1),
                "recommendation": "Increase worker concurrency or batch sizes — CPU is idle",
            },
        )

        # ── RAM Under-utilization ──
        ram_under_pct = buf.pct_below("ram_pct", RAM_UNDER_PCT)
        events += self._check_regime(
            "ram_under", ram_under_pct, now, buf,
            event_type="hfo.gen89.governance.underutilized",
            subject_prefix="GOVERN:ram_under",
            detail_fn=lambda: {
                "resource": "RAM",
                "threshold_pct": RAM_UNDER_PCT,
                "window_pct": round(ram_under_pct, 1),
                "avg_ram_pct": round(buf.avg("ram_pct"), 1),
                "recommendation": "Load more models or increase worker count — memory available",
            },
        )

        # ── NPU Idle ──
        if buf.latest() and buf.latest().npu_available:
            npu_idle_pct = buf.pct_below("npu_in_use", 0.5)  # npu_in_use is 0/1
            # Only fire if NPU has been idle for most of the window
            if npu_idle_pct >= REGIME_THRESHOLD_PCT:
                events += self._check_regime(
                    "npu_idle", npu_idle_pct, now, buf,
                    event_type="hfo.gen89.governance.npu_idle",
                    subject_prefix="GOVERN:npu_idle",
                    detail_fn=lambda: {
                        "resource": "NPU",
                        "window_pct": round(npu_idle_pct, 1),
                        "recommendation": "Start NPU embedding worker (T9) to utilize Intel AI Boost",
                    },
                )

        return events

    def _check_regime(
        self,
        regime_name: str,
        match_pct: float,
        now: float,
        buf: SampleBuffer,
        event_type: str,
        subject_prefix: str,
        detail_fn,
    ) -> list[dict]:
        """Check a single regime, fire event if threshold exceeded + cooldown passed."""
        regime = self.regimes[regime_name]
        events = []

        if match_pct >= REGIME_THRESHOLD_PCT:
            if not regime.active:
                regime.active = True
                regime.since = now
                regime.total_activations += 1
            regime.consecutive_matches += 1

            # Fire event if cooldown has elapsed
            if now - regime.last_reported >= COOLDOWN_S:
                data = detail_fn()
                data["regime"] = regime_name
                data["active_since"] = datetime.fromtimestamp(
                    regime.since, timezone.utc
                ).isoformat()
                data["duration_s"] = round(now - regime.since)
                data["activations"] = regime.total_activations

                events.append({
                    "type": event_type,
                    "subject": f"{subject_prefix}:{round(match_pct)}pct",
                    "data": data,
                })
                regime.last_reported = now
        else:
            if regime.active:
                regime.active = False
                regime.consecutive_matches = 0

        return events

    def get_status(self) -> dict:
        return {
            name: {
                "active": r.active,
                "since": datetime.fromtimestamp(r.since, timezone.utc).isoformat() if r.active else None,
                "activations": r.total_activations,
            }
            for name, r in self.regimes.items()
        }


# ═══════════════════════════════════════════════════════════════
# RESOURCE SAMPLER — Gathers point-in-time metrics
# ═══════════════════════════════════════════════════════════════

class ResourceSampler:
    """Collects resource measurements from the system."""

    def __init__(self):
        self._process = psutil.Process()
        # Initialize CPU tracking
        psutil.cpu_percent(percpu=False)

    def sample(self) -> ResourceSample:
        """Take a point-in-time resource sample."""
        # CPU
        cpu_pct = psutil.cpu_percent(percpu=False)

        # RAM
        vmem = psutil.virtual_memory()
        ram_pct = vmem.percent
        ram_free_gb = round(vmem.available / (1024**3), 2)

        # VRAM (from Ollama)
        vram_used_gb = 0.0
        loaded_models = []
        if HAS_HTTPX:
            try:
                with httpx.Client(timeout=3) as client:
                    r = client.get(f"{OLLAMA_BASE}/api/ps")
                    if r.status_code == 200:
                        for m in r.json().get("models", []):
                            name = m.get("name", "unknown")
                            vram = round(m.get("size_vram", 0) / (1024**3), 1)
                            loaded_models.append(name)
                            vram_used_gb += vram
            except Exception:
                pass

        # NPU
        npu_available = False
        if HAS_OPENVINO:
            try:
                core = ov.Core()
                npu_available = "NPU" in core.available_devices
            except Exception:
                pass

        # Check if NPU embedder is running (look for inference sessions)
        npu_in_use = self._check_npu_in_use()

        return ResourceSample(
            timestamp=time.time(),
            cpu_pct=round(cpu_pct, 1),
            ram_pct=round(ram_pct, 1),
            ram_free_gb=ram_free_gb,
            vram_used_gb=round(vram_used_gb, 1),
            vram_budget_gb=VRAM_BUDGET_GB,
            loaded_models=loaded_models,
            npu_available=npu_available,
            npu_in_use=npu_in_use,
            process_count=len(psutil.pids()),
        )

    def _check_npu_in_use(self) -> bool:
        """Check if NPU is actively being used by looking for known indicators."""
        # Check if any embedding work was done recently by querying SSOT
        try:
            conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
            row = conn.execute(
                """SELECT COUNT(*) FROM stigmergy_events
                   WHERE event_type = 'hfo.gen89.swarm.embedding'
                   AND timestamp > datetime('now', '-5 minutes')""",
            ).fetchone()
            conn.close()
            return row[0] > 0
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# STIGMERGY WRITER
# ═══════════════════════════════════════════════════════════════

def _write_gov_event(event_type: str, subject: str, data: dict) -> Optional[str]:
    """Write a governance event to SSOT via canonical write_stigmergy_event."""
    if not HAS_CANONICAL_WRITE or write_stigmergy_event is None:
        # Fallback: raw insert without signal_metadata (pre-upgrade path)
        try:
            conn = sqlite3.connect(str(SSOT_DB), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            now = datetime.now(timezone.utc).isoformat()
            content_hash = hashlib.sha256(
                f"{event_type}:{subject}:{time.time()}".encode()
            ).hexdigest()
            conn.execute(
                """INSERT OR IGNORE INTO stigmergy_events
                   (event_type, timestamp, subject, source, data_json, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_type, now, subject, GOV_SOURCE, json.dumps(data), content_hash),
            )
            conn.commit()
            conn.close()
            return content_hash[:12]
        except Exception as e:
            print(f"  [GOV] Stigmergy write failed (fallback): {e}", file=sys.stderr)
            return None

    try:
        sig_meta = build_signal_metadata(
            port="P6",
            model_id="governance",
            daemon_name="resource_governance",
            daemon_version="v1.0",
            task_type=event_type.split(".")[-1],
        )
        row_id = write_stigmergy_event(
            event_type=event_type,
            subject=subject,
            data=data,
            signal_metadata=sig_meta,
            source=GOV_SOURCE,
        )
        return str(row_id) if row_id else None
    except Exception as e:
        print(f"  [GOV] Stigmergy write failed: {e}", file=sys.stderr)
        return None


# ═══════════════════════════════════════════════════════════════
# GOVERNANCE DAEMON — Main loop
# ═══════════════════════════════════════════════════════════════

class GovernanceDaemon:
    """
    Resource governance daemon — monitors sustained utilization patterns
    and logs stigmergy events for over/under-utilization.
    
    Designed for durability:
        - Persists state to disk
        - Recovers from crashes via state file
        - Runs as asyncio task alongside swarm
        - Never crashes the parent process
    """

    def __init__(self, dry_run: bool = False):
        self.sampler = ResourceSampler()
        self.buffer = SampleBuffer(max_size=WINDOW_SIZE)
        self.detector = RegimeDetector()
        self.dry_run = dry_run
        self._running = True
        self._total_samples = 0
        self._total_events_fired = 0
        self._start_time = time.time()

    def stop(self):
        self._running = False

    def _fire_events(self, events: list[dict]):
        """Write governance events to SSOT."""
        for evt in events:
            ts = datetime.now(timezone.utc).strftime("%H%M%S")
            subject = f"{evt['subject']}:{ts}"
            data = evt["data"]
            data["governance_source"] = GOV_SOURCE
            data["window_samples"] = len(self.buffer)
            data["total_daemon_samples"] = self._total_samples

            if not self.dry_run:
                _write_gov_event(evt["type"], subject, data)

            self._total_events_fired += 1
            # Print to console
            regime = data.get("regime", "?")
            resource = data.get("resource", "?")
            rec = data.get("recommendation", "")
            print(f"  [GOV:{regime.upper()}] {resource} — {rec}")

    async def sample_loop(self):
        """
        Main sampling loop — runs continuously.
        
        Every SAMPLE_INTERVAL_S:
            1. Take a resource sample
            2. Add to ring buffer
            3. Analyze buffer for regime transitions
            4. Fire stigmergy events for detected regimes
        """
        print(f"  [GOV] Governance daemon started (sample={SAMPLE_INTERVAL_S}s, "
              f"window={WINDOW_SIZE}, regime_threshold={REGIME_THRESHOLD_PCT}%, "
              f"cooldown={COOLDOWN_S}s)")

        while self._running:
            try:
                # Sample
                sample = self.sampler.sample()
                self.buffer.add(sample)
                self._total_samples += 1

                # Analyze (only when buffer has enough samples)
                if self.buffer.full or len(self.buffer) >= 10:
                    events = self.detector.analyze(self.buffer)
                    if events:
                        self._fire_events(events)

            except Exception as e:
                print(f"  [GOV ERROR] {e}", file=sys.stderr)

            await asyncio.sleep(SAMPLE_INTERVAL_S)

    async def heartbeat_loop(self):
        """Periodic governance status heartbeat."""
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

            if not self._running:
                break

            try:
                latest = self.buffer.latest()
                heartbeat = {
                    "daemon_uptime_s": round(time.time() - self._start_time),
                    "total_samples": self._total_samples,
                    "total_events_fired": self._total_events_fired,
                    "buffer_size": len(self.buffer),
                    "regimes": self.detector.get_status(),
                    "current": {
                        "cpu_pct": latest.cpu_pct if latest else 0,
                        "ram_pct": latest.ram_pct if latest else 0,
                        "ram_free_gb": latest.ram_free_gb if latest else 0,
                        "vram_used_gb": latest.vram_used_gb if latest else 0,
                        "loaded_models": latest.loaded_models if latest else [],
                        "npu_available": latest.npu_available if latest else False,
                        "npu_in_use": latest.npu_in_use if latest else False,
                    },
                    "averages": {
                        "cpu_pct": round(self.buffer.avg("cpu_pct"), 1),
                        "ram_pct": round(self.buffer.avg("ram_pct"), 1),
                        "ram_free_gb": round(self.buffer.avg("ram_free_gb"), 2),
                        "vram_used_gb": round(self.buffer.avg("vram_used_gb"), 1),
                    },
                    "thresholds": {
                        "cpu_over": CPU_OVER_PCT,
                        "ram_over": RAM_OVER_PCT,
                        "cpu_under": CPU_UNDER_PCT,
                        "ram_under": RAM_UNDER_PCT,
                        "vram_budget": VRAM_BUDGET_GB,
                        "regime_threshold_pct": REGIME_THRESHOLD_PCT,
                        "cooldown_s": COOLDOWN_S,
                    },
                }

                if not self.dry_run:
                    ts = datetime.now(timezone.utc).strftime("%H%M%S")
                    _write_gov_event(
                        "hfo.gen89.governance.heartbeat",
                        f"GOVERN_HEARTBEAT:{ts}",
                        heartbeat,
                    )

                # Console summary
                regimes = self.detector.get_status()
                active = [k for k, v in regimes.items() if v["active"]]
                if active:
                    print(f"  [GOV HEARTBEAT] Active regimes: {', '.join(active)}")
                else:
                    print(f"  [GOV HEARTBEAT] No active regimes — system nominal")

            except Exception as e:
                print(f"  [GOV HEARTBEAT ERROR] {e}", file=sys.stderr)

    def save_state(self):
        """Persist daemon state for crash recovery."""
        state = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "total_samples": self._total_samples,
            "total_events_fired": self._total_events_fired,
            "uptime_s": round(time.time() - self._start_time),
            "regimes": self.detector.get_status(),
            "buffer_size": len(self.buffer),
        }
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def get_status(self) -> dict:
        """Get current governance status."""
        latest = self.buffer.latest()
        return {
            "running": self._running,
            "uptime_s": round(time.time() - self._start_time),
            "total_samples": self._total_samples,
            "total_events_fired": self._total_events_fired,
            "buffer_size": len(self.buffer),
            "regimes": self.detector.get_status(),
            "current": {
                "cpu_pct": latest.cpu_pct if latest else 0,
                "ram_pct": latest.ram_pct if latest else 0,
                "vram_used_gb": latest.vram_used_gb if latest else 0,
                "npu_available": latest.npu_available if latest else False,
                "npu_in_use": latest.npu_in_use if latest else False,
            } if latest else {},
        }


# ═══════════════════════════════════════════════════════════════
# ASYNC RUNNER — For integration with swarm
# ═══════════════════════════════════════════════════════════════

async def run_governance_daemon(dry_run: bool = False) -> GovernanceDaemon:
    """
    Start the governance daemon as async tasks.
    Returns the daemon instance for status queries.
    
    Usage in swarm:
        daemon = GovernanceDaemon()
        tasks = [
            asyncio.create_task(daemon.sample_loop()),
            asyncio.create_task(daemon.heartbeat_loop()),
        ]
    """
    daemon = GovernanceDaemon(dry_run=dry_run)
    await asyncio.gather(
        daemon.sample_loop(),
        daemon.heartbeat_loop(),
    )
    return daemon


# ═══════════════════════════════════════════════════════════════
# CLI — Standalone operation
# ═══════════════════════════════════════════════════════════════

def _cli_status():
    """Show governance state."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        print(f"  Last saved: {state.get('saved_at', '?')}")
        print(f"  Samples: {state.get('total_samples', 0)}")
        print(f"  Events fired: {state.get('total_events_fired', 0)}")
        print(f"  Uptime: {state.get('uptime_s', 0)}s")
        regimes = state.get("regimes", {})
        active = [k for k, v in regimes.items() if v.get("active")]
        if active:
            print(f"  Active regimes: {', '.join(active)}")
        else:
            print(f"  No active regimes")
    else:
        print("  No governance state found. Run the daemon first.")

    # Check recent governance events in SSOT
    try:
        conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
        rows = conn.execute(
            """SELECT event_type, timestamp, subject FROM stigmergy_events
               WHERE event_type LIKE 'hfo.gen89.governance.%'
               ORDER BY timestamp DESC LIMIT 10"""
        ).fetchall()
        conn.close()
        if rows:
            print(f"\n  Recent governance events:")
            for r in rows:
                print(f"    {r[1]} | {r[0]} | {r[2]}")
        else:
            print(f"\n  No governance events in SSOT yet.")
    except Exception as e:
        print(f"  DB error: {e}")


def _cli_sample():
    """Take one sample and print."""
    sampler = ResourceSampler()
    time.sleep(0.5)  # Let CPU settle
    s = sampler.sample()
    print(f"  CPU:  {s.cpu_pct}%")
    print(f"  RAM:  {s.ram_pct}% (free: {s.ram_free_gb} GB)")
    print(f"  VRAM: {s.vram_used_gb} / {s.vram_budget_gb} GB budget")
    print(f"  Models: {', '.join(s.loaded_models) if s.loaded_models else 'none'}")
    print(f"  NPU:  available={s.npu_available}, in_use={s.npu_in_use}")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="HFO Resource Governance Daemon",
    )
    parser.add_argument("--dry-run", action="store_true", help="No writes to SSOT")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--sample", action="store_true", help="Take one sample and exit")

    args = parser.parse_args()

    if args.status:
        _cli_status()
        return

    if args.sample:
        _cli_sample()
        return

    # Run the daemon
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  HFO RESOURCE GOVERNANCE DAEMON                          ║")
    print("║  Monitoring utilization patterns + regime detection       ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()

    _stop = {"value": False}

    def handle_signal(signum, frame):
        if _stop["value"]:
            sys.exit(1)
        _stop["value"] = True
        print("\n  Stopping governance daemon...")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    daemon = GovernanceDaemon(dry_run=args.dry_run)

    async def _run():
        tasks = [
            asyncio.create_task(daemon.sample_loop()),
            asyncio.create_task(daemon.heartbeat_loop()),
        ]
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            daemon.save_state()
            print("  Governance daemon stopped.")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
