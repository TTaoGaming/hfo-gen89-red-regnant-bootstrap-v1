"""
hfo_resource_governor.py — HFO Gen89 Resource Governor

Hard 80% ceiling on GPU/VRAM for background daemons.
NPU is ALWAYS preferred. Ollama GPU is last resort with backpressure.

Architecture:
  - get_resource_snapshot()     : poll RAM, swap, VRAM, CPU
  - check_gpu_headroom()        : True if safe to start GPU inference (VRAM < 80%)
  - wait_for_gpu_headroom()     : blocking poll until headroom available
  - evict_idle_ollama_models()  : force keep_alive=0s on all loaded models
  - gpu_inference_slot()        : context manager — wait for headroom, then run
  - check_swap_windows()        : verify Windows pagefile is adequate
  - emit_resource_event()       : write ResourceSnapshot to SSOT stigmergy

Tuning via environment variables:
  HFO_VRAM_BUDGET_GB      : max VRAM for background daemons (default 10.0)
  HFO_RAM_HIGH_WATER_PCT  : pause new work above this RAM% (default 85)
  HFO_GPU_SLOT_TIMEOUT_S  : max seconds to wait for headroom (default 120)
  HFO_GPU_MAX_CONCURRENT  : max concurrent Ollama inferences (default 1)
  OLLAMA_BASE             : Ollama base URL (default http://localhost:11434)

Usage:
    from hfo_resource_governor import wait_for_gpu_headroom, evict_idle_ollama_models

    # Before any Ollama call:
    ok = wait_for_gpu_headroom()
    if not ok:
        return None  # caller falls back to NPU

    # Or as a context manager:
    with gpu_inference_slot() as ok:
        if ok:
            result = ollama_generate(prompt, ...)
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psutil

# ─── Configuration ───────────────────────────────────────────────────────────

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")

# Intel Iris Xe on Meteor Lake uses shared system RAM as VRAM.
# 10 GB = ~80 % of the ~12-13 GB we've observed being addressable before crashes.
VRAM_BUDGET_GB: float = float(os.environ.get("HFO_VRAM_BUDGET_GB", "10.0"))

# RAM safety threshold — pause new GPU work when RAM usage is above this level.
# At 92% (2.5 GB free on 31.5 GB system) we are dangerously low.
RAM_HIGH_WATER_PCT: float = float(os.environ.get("HFO_RAM_HIGH_WATER_PCT", "85.0"))

# Max seconds to wait for VRAM headroom before giving up + fallback to NPU.
GPU_SLOT_TIMEOUT_S: int = int(os.environ.get("HFO_GPU_SLOT_TIMEOUT_S", "120"))

# Maximum concurrent Ollama inferences across ALL background daemons.
# 1 = serialized (safest — prevents VRAM spikes from concurrent loading).
GPU_MAX_CONCURRENT: int = int(os.environ.get("HFO_GPU_MAX_CONCURRENT", "1"))

# Minimum free VRAM headroom (GB) required before allowing a new inference.
# 2.0 GB leaves room for OS + one 1.2B model buffer.
VRAM_HEADROOM_MIN_GB: float = 2.0

# How long between polls when waiting for headroom (seconds).
POLL_INTERVAL_S: float = 5.0

# Poll interval for the background monitor thread.
MONITOR_INTERVAL_S: float = 30.0

# Path to the SSOT database (optional — governor works standalone without it).
_HFO_ROOT = Path(__file__).resolve().parents[4]
_SSOT_DB = (
    _HFO_ROOT
    / "hfo_gen_89_hot_obsidian_forge"
    / "2_gold"
    / "resources"
    / "hfo_gen89_ssot.sqlite"
)

# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class OllamaModel:
    name: str
    vram_mb: float
    size_mb: float
    digest: str = ""


@dataclass
class ResourceSnapshot:
    timestamp: str
    # RAM
    ram_total_gb: float
    ram_available_gb: float
    ram_used_pct: float
    # Swap
    swap_total_gb: float
    swap_used_gb: float
    swap_used_pct: float
    # CPU
    cpu_pct: float          # 1-second average
    cpu_cores: int
    # GPU / VRAM (via Ollama /api/ps — most accurate for Intel Xe shared memory)
    vram_used_gb: float
    vram_budget_gb: float
    vram_headroom_gb: float
    vram_pct_of_budget: float   # 0-100
    ollama_models_loaded: list[OllamaModel] = field(default_factory=list)
    # Derived status
    gpu_pressure: str = "OK"    # OK | MODERATE | HIGH | CRITICAL
    ram_pressure: str = "OK"
    safe_to_infer_gpu: bool = True
    throttle_reason: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ollama_models_loaded"] = [asdict(m) for m in self.ollama_models_loaded]
        return d


# ─── Thread-local GPU semaphore ──────────────────────────────────────────────

_gpu_semaphore = threading.Semaphore(GPU_MAX_CONCURRENT)
_semaphore_lock = threading.Lock()

# ─── Core Probes ─────────────────────────────────────────────────────────────

def _query_ollama_ps() -> list[OllamaModel]:
    """Query Ollama /api/ps — returns currently loaded models + their VRAM."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/ps", method="GET",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return [
            OllamaModel(
                name=m.get("name", "?"),
                vram_mb=m.get("size_vram", 0) / 1024**2,
                size_mb=m.get("size", 0) / 1024**2,
                digest=m.get("digest", ""),
            )
            for m in data.get("models", [])
        ]
    except Exception:
        return []


def get_resource_snapshot() -> ResourceSnapshot:
    """Poll RAM, swap, CPU, and VRAM state. Safe to call frequently."""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    cpu = psutil.cpu_percent(interval=0.2)

    models = _query_ollama_ps()
    vram_used_gb = sum(m.vram_mb for m in models) / 1024.0

    headroom_gb = VRAM_BUDGET_GB - vram_used_gb
    vram_pct = (vram_used_gb / VRAM_BUDGET_GB * 100.0) if VRAM_BUDGET_GB > 0 else 0.0

    # Pressure classification
    if vram_pct >= 100:
        gpu_p = "CRITICAL"
    elif vram_pct >= 90:
        gpu_p = "HIGH"
    elif vram_pct >= 75:
        gpu_p = "MODERATE"
    else:
        gpu_p = "OK"

    ram_pct = vm.percent
    if ram_pct >= 95:
        ram_p = "CRITICAL"
    elif ram_pct >= RAM_HIGH_WATER_PCT:
        ram_p = "HIGH"
    elif ram_pct >= 75:
        ram_p = "MODERATE"
    else:
        ram_p = "OK"

    # Single gate: is it safe to launch a new GPU inference right now?
    throttle_reason = ""
    safe = True
    if vram_used_gb + VRAM_HEADROOM_MIN_GB > VRAM_BUDGET_GB:
        safe = False
        throttle_reason = (
            f"VRAM {vram_used_gb:.1f}/{VRAM_BUDGET_GB:.1f} GB "
            f"({vram_pct:.0f}% of budget) — need {VRAM_HEADROOM_MIN_GB:.1f} GB headroom"
        )
    elif ram_pct > RAM_HIGH_WATER_PCT:
        safe = False
        throttle_reason = (
            f"RAM {ram_pct:.0f}% > {RAM_HIGH_WATER_PCT:.0f}% high-water — "
            f"only {vm.available/1024**3:.1f} GB free"
        )

    return ResourceSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        ram_total_gb=round(vm.total / 1024**3, 1),
        ram_available_gb=round(vm.available / 1024**3, 2),
        ram_used_pct=round(ram_pct, 1),
        swap_total_gb=round(sw.total / 1024**3, 1),
        swap_used_gb=round(sw.used / 1024**3, 2),
        swap_used_pct=round(sw.percent, 1),
        cpu_pct=round(cpu, 1),
        cpu_cores=psutil.cpu_count(logical=True),
        vram_used_gb=round(vram_used_gb, 2),
        vram_budget_gb=VRAM_BUDGET_GB,
        vram_headroom_gb=round(headroom_gb, 2),
        vram_pct_of_budget=round(vram_pct, 1),
        ollama_models_loaded=models,
        gpu_pressure=gpu_p,
        ram_pressure=ram_p,
        safe_to_infer_gpu=safe,
        throttle_reason=throttle_reason,
    )


# ─── Headroom Checks ─────────────────────────────────────────────────────────

def check_gpu_headroom() -> tuple[bool, str]:
    """
    Quick check — is it safe to start a GPU inference right now?

    Returns: (ok: bool, reason: str)
      ok=True  → go ahead
      ok=False → wait or use NPU
    """
    snap = get_resource_snapshot()
    return snap.safe_to_infer_gpu, snap.throttle_reason


def wait_for_gpu_headroom(
    timeout_s: int = GPU_SLOT_TIMEOUT_S,
    caller: str = "daemon",
    verbose: bool = True,
) -> bool:
    """
    Block until GPU has enough headroom for a new inference, or timeout.

    Returns True if headroom is available, False if timeout expired.
    On timeout the caller should fall back to NPU or skip the task.
    """
    deadline = time.monotonic() + timeout_s
    warned = False
    while time.monotonic() < deadline:
        ok, reason = check_gpu_headroom()
        if ok:
            return True
        if not warned and verbose:
            print(
                f"[RESOURCE GOV] {caller}: GPU backpressure — waiting "
                f"(up to {timeout_s}s). Reason: {reason}",
                file=sys.stderr,
            )
            warned = True
        time.sleep(POLL_INTERVAL_S)

    # Timeout — emit warning and return False to trigger NPU/skip fallback
    if verbose:
        snap = get_resource_snapshot()
        print(
            f"[RESOURCE GOV] {caller}: TIMEOUT ({timeout_s}s). "
            f"VRAM={snap.vram_used_gb:.1f}/{VRAM_BUDGET_GB:.1f} GB  "
            f"RAM={snap.ram_used_pct:.0f}%  — falling back to NPU",
            file=sys.stderr,
        )
    return False


# ─── Model Eviction ──────────────────────────────────────────────────────────

def evict_idle_ollama_models(verbose: bool = True) -> int:
    """
    Evict ALL currently loaded Ollama models from VRAM by sending keep_alive=0.

    Call this when VRAM is saturated and you need to free headroom quickly.
    Returns number of models evicted.
    """
    models = _query_ollama_ps()
    if not models:
        return 0

    evicted = 0
    for m in models:
        try:
            payload = json.dumps(
                {"model": m.name, "keep_alive": "0s", "prompt": ""}
            ).encode()
            req = urllib.request.Request(
                f"{OLLAMA_BASE}/api/generate",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            # Fire-and-forget — just trigger the eviction
            with urllib.request.urlopen(req, timeout=10) as _:
                pass
            if verbose:
                print(
                    f"[RESOURCE GOV] Evicted {m.name} ({m.vram_mb:.0f} MB VRAM freed)",
                    file=sys.stderr,
                )
            evicted += 1
        except Exception as e:
            if verbose:
                print(f"[RESOURCE GOV] Evict {m.name} failed: {e}", file=sys.stderr)

    return evicted


def evict_and_wait(
    timeout_s: int = 60,
    caller: str = "daemon",
    verbose: bool = True,
) -> bool:
    """
    Evict idle models then wait for VRAM to settle.

    Use when pre-emptive eviction is needed (e.g. about to load a heavy model).
    Returns True if headroom achieved within timeout.
    """
    ok, _ = check_gpu_headroom()
    if ok:
        return True

    if verbose:
        print(f"[RESOURCE GOV] {caller}: proactive eviction before new inference", file=sys.stderr)
    evict_idle_ollama_models(verbose=verbose)

    # Wait up to timeout for eviction to take effect
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        time.sleep(3.0)
        ok, reason = check_gpu_headroom()
        if ok:
            return True

    return False


# ─── Context Manager ─────────────────────────────────────────────────────────

@contextlib.contextmanager
def gpu_inference_slot(
    timeout_s: int = GPU_SLOT_TIMEOUT_S,
    caller: str = "daemon",
    verbose: bool = True,
    evict_first: bool = False,
):
    """
    Context manager for safe GPU inference.

    Acquires the process-level semaphore (max GPU_MAX_CONCURRENT concurrent)
    AND waits for system-wide VRAM headroom.

    Usage:
        with gpu_inference_slot(caller="kraken_t1") as ok:
            if ok:
                result = call_ollama(...)
            else:
                result = npu_fallback(...)

    ok=True  → headroom available, semaphore acquired
    ok=False → timeout — caller should use NPU or skip
    """
    acquired = _gpu_semaphore.acquire(timeout=timeout_s)
    if not acquired:
        if verbose:
            print(
                f"[RESOURCE GOV] {caller}: semaphore timeout ({timeout_s}s) — "
                f"too many concurrent inferences, falling back to NPU",
                file=sys.stderr,
            )
        yield False
        return

    try:
        if evict_first:
            evict_and_wait(timeout_s=30, caller=caller, verbose=verbose)
        else:
            ok = wait_for_gpu_headroom(timeout_s=timeout_s, caller=caller, verbose=verbose)
            if not ok:
                yield False
                return
        yield True
    finally:
        _gpu_semaphore.release()


# ─── Swap Check (Windows) ────────────────────────────────────────────────────

def check_swap_windows() -> dict:
    """
    Check Windows pagefile (swap) adequacy.

    Recommended: pagefile >= max(8 GB, 1.5 × RAM).
    At 31.5 GB RAM, recommended pagefile = ~47 GB.
    The existing 19 GB pagefile is a minimum floor; Windows auto-expands it.

    Returns a dict with status and recommendations.
    """
    sw = psutil.swap_memory()
    vm = psutil.virtual_memory()
    ram_gb = vm.total / 1024**3
    swap_gb = sw.total / 1024**3
    recommended_min_gb = max(8.0, ram_gb * 0.5)  # at least 50% of RAM, min 8 GB

    status = "OK"
    recommendations = []

    if swap_gb < 4.0:
        status = "CRITICAL"
        recommendations.append(
            f"Pagefile is only {swap_gb:.1f} GB. Increase to at least "
            f"{recommended_min_gb:.0f} GB:  "
            f"System Properties → Advanced → Performance → Virtual Memory → "
            f"Set initial={int(recommended_min_gb*1024)} MB, max={int(ram_gb*1.5*1024)} MB"
        )
    elif swap_gb < recommended_min_gb:
        status = "LOW"
        recommendations.append(
            f"Pagefile {swap_gb:.1f} GB is below recommended {recommended_min_gb:.0f} GB. "
            f"Consider expanding to {int(recommended_min_gb * 1024)} MB."
        )

    if sw.percent > 80:
        recommendations.append(
            f"Swap is {sw.percent:.0f}% full ({sw.used/1024**3:.1f}/{swap_gb:.1f} GB). "
            "High swap usage indicates RAM pressure — close unused applications."
        )

    return {
        "status": status,
        "swap_total_gb": round(swap_gb, 1),
        "swap_used_gb": round(sw.used / 1024**3, 1),
        "swap_used_pct": round(sw.percent, 1),
        "ram_total_gb": round(ram_gb, 1),
        "recommended_min_swap_gb": round(recommended_min_gb, 1),
        "recommendations": recommendations,
    }


# ─── SSOT Stigmergy Emission ─────────────────────────────────────────────────

def emit_resource_snapshot(snap: Optional[ResourceSnapshot] = None) -> bool:
    """
    Write a resource snapshot to SSOT stigmergy_events.

    No-op if database not found (governor works standalone without SSOT).
    Returns True if written, False otherwise.
    """
    if not _SSOT_DB.exists():
        return False
    try:
        import sqlite3, uuid
        if snap is None:
            snap = get_resource_snapshot()
        conn = sqlite3.connect(str(_SSOT_DB))
        conn.execute(
            """
            INSERT INTO stigmergy_events
                (event_id, event_type, source, subject, data_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                "hfo.gen89.resource.snapshot",
                "hfo_resource_governor",
                f"gpu:{snap.gpu_pressure} ram:{snap.ram_pressure}",
                json.dumps(snap.to_dict()),
                snap.timestamp,
            ),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ─── Background Monitor Thread ───────────────────────────────────────────────

_monitor_running = False
_monitor_thread: Optional[threading.Thread] = None


def start_background_monitor(interval_s: float = MONITOR_INTERVAL_S) -> None:
    """
    Start a background thread that polls resources and emits stigmergy snapshots.

    Daemons can call this once at startup to get auto-monitoring.
    """
    global _monitor_running, _monitor_thread

    if _monitor_running:
        return

    def _loop():
        while _monitor_running:
            try:
                snap = get_resource_snapshot()
                # Log locally on HIGH/CRITICAL pressure
                if snap.gpu_pressure in ("HIGH", "CRITICAL"):
                    print(
                        f"[RESOURCE GOV] ⚠ GPU {snap.gpu_pressure}: "
                        f"VRAM {snap.vram_used_gb:.1f}/{VRAM_BUDGET_GB:.1f} GB "
                        f"({snap.vram_pct_of_budget:.0f}%) — "
                        + (f"⚡ THROTTLED: {snap.throttle_reason}" if not snap.safe_to_infer_gpu else "headroom OK"),
                        file=sys.stderr,
                    )
                if snap.ram_pressure in ("HIGH", "CRITICAL"):
                    print(
                        f"[RESOURCE GOV] ⚠ RAM {snap.ram_pressure}: "
                        f"{snap.ram_used_pct:.0f}% used, "
                        f"{snap.ram_available_gb:.1f} GB free",
                        file=sys.stderr,
                    )
                # Write to SSOT every 5 minutes, or immediately on HIGH/CRITICAL
                if snap.gpu_pressure in ("HIGH", "CRITICAL") or snap.ram_pressure in ("HIGH", "CRITICAL"):
                    emit_resource_snapshot(snap)
            except Exception as e:
                pass  # Monitor must never crash the daemon
            time.sleep(interval_s)

    _monitor_running = True
    _monitor_thread = threading.Thread(target=_loop, name="ResourceMonitor", daemon=True)
    _monitor_thread.start()


def stop_background_monitor() -> None:
    global _monitor_running
    _monitor_running = False


# ─── CLI / Standalone ────────────────────────────────────────────────────────

def _print_status():
    """Print a human-readable resource status report."""
    snap = get_resource_snapshot()
    swap = check_swap_windows()

    gate = "GO" if snap.safe_to_infer_gpu else "HOLD"
    gate_color = "" if snap.safe_to_infer_gpu else " ⛔"

    print("=" * 62)
    print("  HFO Resource Governor — System Status")
    print("=" * 62)
    print(f"\n  GPU Inference Gate : [{gate}]{gate_color}")
    if snap.throttle_reason:
        print(f"  Throttle reason    : {snap.throttle_reason}")
    print(f"\n  VRAM (Ollama /api/ps):")
    print(f"    Budget  : {VRAM_BUDGET_GB:.1f} GB  (80% daemon ceiling)")
    print(f"    In use  : {snap.vram_used_gb:.2f} GB  ({snap.vram_pct_of_budget:.0f}% of budget)")
    print(f"    Headroom: {snap.vram_headroom_gb:.2f} GB  — {snap.gpu_pressure}")
    if snap.ollama_models_loaded:
        for m in snap.ollama_models_loaded:
            print(f"    Loaded  : {m.name:30s}  {m.vram_mb:6.0f} MB VRAM")
    else:
        print(f"    Loaded  : (none — VRAM free)")
    print(f"\n  RAM:")
    print(f"    Total   : {snap.ram_total_gb:.1f} GB")
    print(f"    Free    : {snap.ram_available_gb:.2f} GB  ({100-snap.ram_used_pct:.0f}% free) — {snap.ram_pressure}")
    if snap.ram_used_pct > RAM_HIGH_WATER_PCT:
        print(f"    ⚠ HIGH WATER ({snap.ram_used_pct:.0f}% > {RAM_HIGH_WATER_PCT:.0f}% limit) — new GPU work paused")
    print(f"\n  Swap (Windows Pagefile):")
    print(f"    Total   : {snap.swap_total_gb:.1f} GB  — {swap['status']}")
    print(f"    Used    : {snap.swap_used_gb:.2f} GB  ({snap.swap_used_pct:.0f}%)")
    if swap["recommendations"]:
        for rec in swap["recommendations"]:
            print(f"    ⚠  {rec}")
    print(f"\n  CPU : {snap.cpu_pct:.0f}%  ({snap.cpu_cores} logical cores)")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HFO Resource Governor")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="Print current resource status")
    sub.add_parser("evict", help="Evict all loaded Ollama models from VRAM")
    sub.add_parser("wait", help="Block until GPU headroom is available")
    sub.add_parser("swap", help="Check Windows pagefile adequacy")
    sub.add_parser("monitor", help="Run background monitor (prints to stderr)")

    args = parser.parse_args()

    if args.cmd == "status" or args.cmd is None:
        _print_status()

    elif args.cmd == "evict":
        n = evict_idle_ollama_models()
        print(f"Evicted {n} model(s)")
        time.sleep(4)
        _print_status()

    elif args.cmd == "wait":
        print("Waiting for GPU headroom...")
        ok = wait_for_gpu_headroom(verbose=True)
        print(f"Result: {'READY' if ok else 'TIMEOUT — use NPU'}")

    elif args.cmd == "swap":
        sw = check_swap_windows()
        print(json.dumps(sw, indent=2))

    elif args.cmd == "monitor":
        print("Starting background monitor (Ctrl-C to stop)...")
        start_background_monitor(interval_s=10.0)
        try:
            while True:
                time.sleep(10)
                _print_status()
        except KeyboardInterrupt:
            stop_background_monitor()
