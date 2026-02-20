#!/usr/bin/env python3
"""
hfo_sandbox_launcher.py — Correct-by-Construction 4-Port Sandbox Launcher
=========================================================================
v1.0 | Gen89 | Port: P7 NAVIGATE (orchestration) | Medallion: bronze

PURPOSE:
    Boots a 24/7 AI sandbox with least-privilege port isolation.
    Implements the P2-P5 SAFETY SPINE: P2 SHAPE creates freely because
    P5 IMMUNIZE structurally gates everything.

BOOT SEQUENCE (fail-closed, order-dependent):
    Phase 0: Preflight — VRAM check, SSOT health, P6 swarm health
    Phase 1: P5 IMMUNIZE boots FIRST (immune system MUST be online)
    Phase 2: P4 DISRUPT boots SECOND (Singer + Song Prospector)
             Nataraja Dance activates when both P4+P5 online
    Phase 3: P2 SHAPE boots LAST (chimera loop in daemon mode)
             ONLY if P5 is healthy. P5 down = P2 paused.
    Phase 4: Supervisor watchdog monitors all ports, pauses P2 if P5 dies

PORT ISOLATION (least-privilege):
    P2 SHAPE:     Can write hfo.gen89.chimera.* events. Model: gemma3:4b.
                  Cannot write to gold/silver. Gated by P5.
    P4 DISRUPT:   Can write hfo.gen89.p4.singer.*, hfo.gen89.p4.song_prospector.* events.
                  Singer: no LLM (pure SSOT scan). Prospector: gemma3:4b.
    P5 IMMUNIZE:  Can write hfo.gen89.p5.* events + audit all other ports.
                  Model: phi4:14b (high intelligence). Ring 0/1/2 gates.
    P6 ASSIMILATE: Already running. Writes hfo.gen89.kraken.* events.
                   Model: gemma3:4b (swarm). Managed separately.

COMPUTE SURFACE BUDGET:
    P5 phi4:14b:          8.4 GB VRAM (high intelligence for immune system)
    P2 gemma3:4b:         3.1 GB VRAM (lightweight creation, P5 gates output)
    P4 Singer:            0   GB VRAM (no LLM — pure pattern scan)
    P4 Song Prospector:   PAUSED (qwen3:30b-a3b too large for concurrent)
                          → Uses gemma3:4b when P5+P2 idle budget allows
    ──────────────────────────────────────────────────────────────────
    Total new VRAM:       ~11.5 GB (fits within 16 GB with P6's 3.1 GB)

    P6 swarm manages its own VRAM budget via hfo_resource_monitor.py.
    If P6 unloads models during P5/P2 active window, headroom increases.

SAFETY SPINE (P2 → P5):
    1. P2 SHAPE creates artifacts (chimera genomes, code, persona specs)
    2. P5 Ring 0: Cantrip-first dispatch — deterministic structure check
    3. P5 Ring 1: Output schema gate — structured fields validated
    4. P5 Ring 2: Post-turn audit — drift/regression check
    5. Only PASSED artifacts can touch silver/gold layers

NATARAJA DANCE (P4 + P5):
    NATARAJA_Score = P4_kill_rate × P5_rebirth_rate
    When P4 kills something (WEIRD), P5 resurrects it stronger (CONTINGENCY).
    P6 feeds on the corpse (FEAST). P2 recreates with extracted knowledge.
    The dance is EMERGENT — stigmergy is the dance floor.

USAGE:
    # Start full sandbox (P5 → P4 → P2)
    python hfo_sandbox_launcher.py

    # Start specific ports only
    python hfo_sandbox_launcher.py --ports P5,P4

    # Dry run (show what would start, don't actually start)
    python hfo_sandbox_launcher.py --dry-run

    # Show status of all sandbox daemons
    python hfo_sandbox_launcher.py --status

    # Stop all sandbox daemons
    python hfo_sandbox_launcher.py --stop

    # Start with Song Prospector active (uses more VRAM)
    python hfo_sandbox_launcher.py --with-prospector

    # Override P2 model (default: gemma3:4b)
    python hfo_sandbox_launcher.py --p2-model qwen2.5-coder:7b

    # Override P5 model (default: phi4:14b)
    python hfo_sandbox_launcher.py --p5-model gemma3:12b

    # Force-unload all models before booting (clear VRAM)
    python hfo_sandbox_launcher.py --force-unload

Pointer key: sandbox.launcher
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
import textwrap
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import httpx
import psutil

# ═══════════════════════════════════════════════════════════════
# § 0  PATH + CONFIG
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
FORGE = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge"
DB_PATH = FORGE / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
BRONZE_RESOURCES = FORGE / "0_bronze" / "resources"
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
STATE_FILE = HFO_ROOT / ".hfo_sandbox_state.json"

# Launcher source identity
LAUNCHER_SOURCE = f"hfo_sandbox_launcher_gen{GEN}_v1.0"

# ═══════════════════════════════════════════════════════════════
# § 1  COMPUTE SURFACE BUDGET
# ═══════════════════════════════════════════════════════════════

# VRAM ceiling: 16 GB total (Intel Arc 140V)
# P6 swarm reserves: ~3.1 GB (gemma3:4b, managed by resource_monitor)
# Available for sandbox: ~12.9 GB
VRAM_CEILING_GB = 16.0
P6_RESERVED_GB = 3.1  # gemma3:4b for swarm workers

# Per-port model assignments (least-privilege: smallest model that works)
PORT_MODELS = {
    "P5": {
        "model": os.environ.get("P5_OLLAMA_MODEL", "phi4:14b"),
        "vram_gb": 8.4,
        "reason": "High intelligence needed for immune system — Ring 0/1/2 gates, "
                  "anomaly detection, resurrection decisions",
    },
    "P4_SINGER": {
        "model": None,  # No LLM — pure SSOT pattern scan
        "vram_gb": 0.0,
        "reason": "Singer daemon is deterministic — no LLM needed",
    },
    "P4_PROSPECTOR": {
        "model": "gemma3:4b",
        "vram_gb": 3.1,
        "reason": "Creative mining needs LLM but can be lightweight. "
                  "Paused by default (VRAM constrained). Activated when budget allows.",
        "default_enabled": False,
    },
    "P2": {
        "model": os.environ.get("P2_OLLAMA_MODEL", "gemma3:4b"),
        "vram_gb": 3.1,
        "reason": "Chimera loop in daemon mode — lightweight creation, "
                  "P5 gates everything. Full 2x2 grid for manual batch only.",
    },
}


class PortState(Enum):
    """States for sandbox port daemons."""
    STOPPED = "stopped"
    BOOTING = "booting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    PAUSED = "paused"      # Paused by watchdog (e.g., P2 paused when P5 down)
    DEAD = "dead"
    BLOCKED = "blocked"    # Cannot start (VRAM, dependency, gate failure)


@dataclass
class PortDaemon:
    """Tracks state and process for one port daemon."""
    port_id: str
    name: str
    model: Optional[str]
    vram_gb: float
    process: Optional[subprocess.Popen] = None
    thread: Optional[threading.Thread] = None
    state: PortState = PortState.STOPPED
    last_heartbeat: Optional[str] = None
    error_count: int = 0
    boot_time: Optional[str] = None
    stop_event: Optional[threading.Event] = None
    pid: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# § 2  SSOT INTERFACE
# ═══════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_stigmergy(event_type: str, data: dict, subject: str = "sandbox") -> int:
    """Write a sandbox event to SSOT stigmergy trail."""
    if not DB_PATH.exists():
        print(f"  [ERROR] SSOT not found: {DB_PATH}")
        return -1
    ts = _now_iso()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": LAUNCHER_SOURCE,
        "subject": subject,
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_type, ts, subject, LAUNCHER_SOURCE, json.dumps(event), c_hash),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception as e:
        print(f"  [ERROR] Stigmergy write failed: {e}")
        return -1
    finally:
        conn.close()


def _read_recent_events(pattern: str, limit: int = 5) -> list[dict]:
    """Read recent stigmergy events matching a pattern."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """SELECT id, event_type, timestamp, subject, data_json
               FROM stigmergy_events
               WHERE event_type LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (pattern, limit),
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


# ═══════════════════════════════════════════════════════════════
# § 3  PREFLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════

def unload_all_ollama_models() -> list[str]:
    """Unload all currently loaded Ollama models to free VRAM.

    Uses both the API approach (keep_alive: 0) and the CLI `ollama stop` for reliability.
    Returns list of models that were unloaded.
    """
    loaded = check_ollama_loaded_models()
    unloaded = []
    for m in loaded:
        name = m["name"]
        try:
            # Method 1: API — POST /api/generate with keep_alive=0s
            with httpx.Client(timeout=30) as client:
                r = client.post(
                    f"{OLLAMA_BASE}/api/generate",
                    json={"model": name, "prompt": "", "keep_alive": "0s"},
                )
            # Method 2: CLI fallback — ollama stop <model>
            subprocess.run(
                ["ollama", "stop", name],
                capture_output=True, timeout=15,
            )
            unloaded.append(name)
            print(f"  [↓] Unloaded {name} ({m['size_vram_gb']:.1f} GB VRAM)")
        except Exception as e:
            print(f"  [!] Failed to unload {name}: {e}")
    return unloaded


def check_ollama_online() -> bool:
    """Check if Ollama server is responding."""
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def check_ollama_loaded_models() -> list[dict]:
    """Get currently loaded models and their VRAM usage."""
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{OLLAMA_BASE}/api/ps")
            r.raise_for_status()
            models = r.json().get("models", [])
            return [
                {
                    "name": m.get("name", "unknown"),
                    "size_gb": m.get("size", 0) / (1024**3),
                    "size_vram_gb": m.get("size_vram", 0) / (1024**3),
                }
                for m in models
            ]
    except Exception:
        return []


def check_vram_budget(needed_gb: float) -> tuple[bool, float, str]:
    """Check if there's enough VRAM for a new model load.

    Returns: (fits, available_gb, message)
    """
    loaded = check_ollama_loaded_models()
    used_gb = sum(m["size_vram_gb"] for m in loaded)
    available_gb = VRAM_CEILING_GB - used_gb

    fits = needed_gb <= available_gb
    loaded_names = ", ".join(m["name"] for m in loaded) if loaded else "none"

    msg = (f"VRAM: {used_gb:.1f}/{VRAM_CEILING_GB:.1f} GB used "
           f"({available_gb:.1f} GB free). Need: {needed_gb:.1f} GB. "
           f"Loaded: [{loaded_names}]")

    return fits, available_gb, msg


def check_ssot_health() -> tuple[bool, str]:
    """Verify SSOT database is healthy."""
    if not DB_PATH.exists():
        return False, f"SSOT not found: {DB_PATH}"
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        conn.close()
        if doc_count < 9000:
            return False, f"SSOT doc count suspiciously low: {doc_count}"
        return True, f"SSOT healthy: {doc_count} docs, {event_count} events"
    except Exception as e:
        return False, f"SSOT error: {e}"


def check_p6_swarm_health() -> tuple[bool, str]:
    """Check if P6 Kraken swarm is running by reading recent stigmergy."""
    events = _read_recent_events("hfo.gen89.kraken.%", limit=5)
    if not events:
        return False, "P6 Kraken swarm: no recent events found"

    latest = events[0]
    ts_str = latest.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age > 600:  # 10 minutes — swarm should have events within this window
            return False, f"P6 Kraken swarm: last event {age:.0f}s ago (stale)"
        return True, f"P6 Kraken swarm: alive ({age:.0f}s since last event)"
    except Exception:
        return True, f"P6 Kraken swarm: events found (timestamp parse issue)"


def check_model_available(model: str) -> bool:
    """Check if a model is pulled in Ollama."""
    if not model:
        return True  # No model needed
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
            available = [m["name"] for m in r.json().get("models", [])]
            # Match base name (model:tag or just model)
            base = model.split(":")[0]
            return any(base in m for m in available)
    except Exception:
        return False


def check_conflicting_daemons() -> list[dict]:
    """Detect running Python daemons that will compete for VRAM.

    Returns list of conflicting processes with PID, script, and estimated VRAM.
    """
    conflicts = []
    # Known scripts that load Ollama models
    model_scripts = [
        ("hfo_p2_chimera_loop.py", "P2 chimera"),
        ("hfo_song_prospector.py", "P4 prospector"),
        ("hfo_p6_kraken_swarm.py", "P6 swarm"),
        ("hfo_p6_kraken_daemon.py", "P6 daemon"),
        ("hfo_octree_daemon.py", "Octree daemon"),
        ("hfo_p5_daemon.py", "P5 daemon"),
        ("hfo_background_daemon.py", "Background daemon"),
    ]
    try:
        # Use tasklist to find Python processes (cross-platform would use psutil)
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | "
             "Select-Object ProcessId, CommandLine | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []

        procs = json.loads(result.stdout or "[]")
        if isinstance(procs, dict):
            procs = [procs]

        for proc in procs:
            cmd = proc.get("CommandLine", "") or ""
            pid = proc.get("ProcessId", 0)
            for script_name, desc in model_scripts:
                if script_name in cmd:
                    conflicts.append({
                        "pid": pid,
                        "script": script_name,
                        "desc": desc,
                        "cmd": cmd[:120],
                    })
                    break
    except Exception:
        pass  # If we can't check, don't block — just proceed
    return conflicts


def kill_conflicting_daemons(conflicts: list[dict]) -> list[int]:
    """Kill conflicting daemon processes. Returns list of killed PIDs."""
    killed = []
    for c in conflicts:
        pid = c["pid"]
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True, timeout=10,
            )
            killed.append(pid)
            print(f"  [☠] Killed PID {pid}: {c['desc']} ({c['script']})")
        except Exception as e:
            print(f"  [!] Failed to kill PID {pid}: {e}")
    return killed


def run_preflight(
    verbose: bool = True,
    force_unload: bool = False,
    kill_existing: bool = False,
) -> tuple[bool, list[str]]:
    """Run all preflight checks. Returns (all_passed, messages).

    If force_unload=True, unloads all Ollama models before VRAM check.
    If kill_existing=True, kills conflicting daemon processes first.
    """
    checks = []
    all_ok = True

    # 1. Ollama online
    ok = check_ollama_online()
    checks.append(f"{'✓' if ok else '✗'} Ollama server: {'online' if ok else 'OFFLINE'}")
    if not ok:
        all_ok = False

    # 2. SSOT health
    ok, msg = check_ssot_health()
    checks.append(f"{'✓' if ok else '✗'} {msg}")
    if not ok:
        all_ok = False

    # 3. P6 swarm health (advisory — not blocking)
    ok, msg = check_p6_swarm_health()
    checks.append(f"{'✓' if ok else '⚠'} {msg}")
    # P6 not running is a warning, not a block

    # 3b. Conflicting daemon detection
    conflicts = check_conflicting_daemons()
    if conflicts:
        conflict_summary = "; ".join(
            f"PID {c['pid']} {c['desc']}" for c in conflicts
        )
        if kill_existing:
            checks.append(f"⚡ Killing {len(conflicts)} conflicting daemon(s): {conflict_summary}")
            killed = kill_conflicting_daemons(conflicts)
            checks.append(f"  ↓ Killed PIDs: {', '.join(str(p) for p in killed)}")
            time.sleep(5)  # Let processes release resources
        else:
            checks.append(f"⚠ {len(conflicts)} conflicting daemon(s) active: {conflict_summary}")
            checks.append(f"  Hint: Use --kill-existing to stop them, or stop manually")

    # 4. VRAM budget for P5 (first daemon to boot)
    if force_unload:
        loaded = check_ollama_loaded_models()
        if loaded:
            checks.append(f"⚡ Force-unloading {len(loaded)} Ollama model(s) to clear VRAM...")
            unloaded = unload_all_ollama_models()
            checks.append(f"  ↓ Unloaded: {', '.join(unloaded) if unloaded else 'none'}")
            # Wait for Ollama to actually release VRAM (keep_alive=0 is async)
            for wait_i in range(6):
                time.sleep(5)
                still_loaded = check_ollama_loaded_models()
                if not still_loaded:
                    checks.append(f"  ✓ All models evicted after {(wait_i+1)*5}s")
                    break
            else:
                names = [m["name"] for m in still_loaded]
                checks.append(f"  ⚠ Models still in VRAM after 30s: {', '.join(names)}")

    p5_model = PORT_MODELS["P5"]["model"]
    fits, avail, msg = check_vram_budget(PORT_MODELS["P5"]["vram_gb"])
    checks.append(f"{'✓' if fits else '✗'} {msg}")
    if not fits:
        all_ok = False

    # 5. Model availability
    for port_key, port_info in PORT_MODELS.items():
        model = port_info.get("model")
        if model:
            ok = check_model_available(model)
            checks.append(f"{'✓' if ok else '✗'} Model {model}: "
                          f"{'available' if ok else 'NOT FOUND — run: ollama pull ' + model}")
            if not ok and port_key in ("P5", "P2"):
                all_ok = False  # Critical models must be available

    if verbose:
        print(f"\n  {'─'*60}")
        print(f"  PREFLIGHT CHECKS")
        print(f"  {'─'*60}")
        for c in checks:
            print(f"  {c}")
        print(f"  {'─'*60}")
        print(f"  Result: {'ALL PASSED' if all_ok else 'BLOCKED — fix issues above'}")
        print()

    return all_ok, checks


# ═══════════════════════════════════════════════════════════════
# § 4  DAEMON BOOT SEQUENCE
# ═══════════════════════════════════════════════════════════════

class SandboxSupervisor:
    """
    Orchestrates the correct-by-construction boot sequence.

    Boot order:  P5 → P4 → P2  (immune system first, creator last)
    Stop order:  P2 → P4 → P5  (creator first, immune system last)

    Invariant: P2 NEVER runs without P5 being healthy.
    """

    def __init__(
        self,
        p2_model: Optional[str] = None,
        p5_model: Optional[str] = None,
        enable_prospector: bool = False,
        dry_run: bool = False,
        force_unload: bool = False,
        kill_existing: bool = False,
    ):
        self.dry_run = dry_run
        self.enable_prospector = enable_prospector
        self.force_unload = force_unload
        self.kill_existing = kill_existing
        self.shutdown_event = threading.Event()

        # Resolve models
        if p5_model:
            PORT_MODELS["P5"]["model"] = p5_model
        if p2_model:
            PORT_MODELS["P2"]["model"] = p2_model

        # Initialize port daemons
        self.daemons: dict[str, PortDaemon] = {
            "P5": PortDaemon(
                port_id="P5",
                name="Pyre Praetorian — Dancer of Death and Dawn",
                model=PORT_MODELS["P5"]["model"],
                vram_gb=PORT_MODELS["P5"]["vram_gb"],
            ),
            "P4_SINGER": PortDaemon(
                port_id="P4",
                name="Red Regnant Singer — Singer of Strife and Splendor",
                model=None,
                vram_gb=0.0,
            ),
            "P4_PROSPECTOR": PortDaemon(
                port_id="P4",
                name="Red Regnant Song Prospector",
                model=PORT_MODELS["P4_PROSPECTOR"]["model"],
                vram_gb=PORT_MODELS["P4_PROSPECTOR"]["vram_gb"],
            ),
            "P2": PortDaemon(
                port_id="P2",
                name="Mirror Magus — Cursed Chimera Loop",
                model=PORT_MODELS["P2"]["model"],
                vram_gb=PORT_MODELS["P2"]["vram_gb"],
            ),
        }

        # Watchdog thread
        self._watchdog_thread: Optional[threading.Thread] = None

    # ── Boot Helpers ─────────────────────────────────────────

    def _start_daemon_process(
        self, daemon_key: str, script: str, args: list[str] = None
    ) -> bool:
        """Start a daemon as a subprocess.

        Returns True if started successfully.
        """
        daemon = self.daemons[daemon_key]
        daemon.state = PortState.BOOTING

        script_path = BRONZE_RESOURCES / script
        if not script_path.exists():
            daemon.state = PortState.BLOCKED
            print(f"  [✗] {daemon_key}: Script not found: {script_path}")
            return False

        # VRAM check for models that need VRAM
        if daemon.vram_gb > 0:
            fits, avail, msg = check_vram_budget(daemon.vram_gb)
            if not fits:
                daemon.state = PortState.BLOCKED
                print(f"  [✗] {daemon_key}: VRAM blocked — {msg}")
                return False

        cmd = [sys.executable, str(script_path)] + (args or [])

        if self.dry_run:
            print(f"  [DRY] Would start: {' '.join(cmd)}")
            daemon.state = PortState.HEALTHY
            daemon.boot_time = _now_iso()
            return True

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(HFO_ROOT),
            )
            daemon.process = proc
            daemon.pid = proc.pid
            daemon.boot_time = _now_iso()

            # Give it a moment to crash or stabilize
            time.sleep(3)

            if proc.poll() is not None:
                # Process already exited
                output = proc.stdout.read()[:500] if proc.stdout else ""
                daemon.state = PortState.DEAD
                print(f"  [✗] {daemon_key}: Died immediately (exit={proc.returncode})")
                if output:
                    print(f"      Output: {output[:200]}")
                return False

            daemon.state = PortState.HEALTHY
            print(f"  [✓] {daemon_key}: Started (PID {proc.pid})")
            return True

        except Exception as e:
            daemon.state = PortState.DEAD
            print(f"  [✗] {daemon_key}: Failed to start: {e}")
            return False

    def _start_daemon_threaded(
        self, daemon_key: str, target_func, args: tuple = ()
    ) -> bool:
        """Start a daemon as a thread within this process.

        For daemons that we want tighter control over (like P2 chimera daemon mode).
        """
        daemon = self.daemons[daemon_key]
        daemon.state = PortState.BOOTING
        daemon.stop_event = threading.Event()

        if self.dry_run:
            print(f"  [DRY] Would start thread: {daemon_key}")
            daemon.state = PortState.HEALTHY
            daemon.boot_time = _now_iso()
            return True

        try:
            t = threading.Thread(
                target=target_func,
                args=args + (daemon.stop_event,),
                name=f"sandbox-{daemon_key}",
                daemon=True,
            )
            t.start()
            daemon.thread = t
            daemon.boot_time = _now_iso()
            daemon.state = PortState.HEALTHY
            print(f"  [✓] {daemon_key}: Thread started")
            return True
        except Exception as e:
            daemon.state = PortState.DEAD
            print(f"  [✗] {daemon_key}: Thread failed: {e}")
            return False

    # ── Phase 0: Preflight ───────────────────────────────────

    def phase0_preflight(self) -> bool:
        """Phase 0: All preflight checks must pass."""
        print(f"\n{'█'*70}")
        print(f"  HFO CORRECT-BY-CONSTRUCTION SANDBOX — Gen{GEN}")
        print(f"  Boot Sequence: P5 → P4 → P2 (immune system first)")
        print(f"  Safety Spine: P2 creates freely ↔ P5 gates everything")
        print(f"{'█'*70}")

        passed, checks = run_preflight(
            verbose=True,
            force_unload=self.force_unload,
            kill_existing=self.kill_existing,
        )
        if not passed and not self.dry_run:
            _write_stigmergy(
                "hfo.gen89.sandbox.preflight_failed",
                {"checks": checks},
                subject="sandbox:preflight",
            )
            return False

        _write_stigmergy(
            "hfo.gen89.sandbox.preflight_passed",
            {
                "checks": checks,
                "port_models": {
                    k: {"model": v["model"], "vram_gb": v["vram_gb"]}
                    for k, v in PORT_MODELS.items()
                },
                "vram_ceiling_gb": VRAM_CEILING_GB,
            },
            subject="sandbox:preflight",
        )
        return True

    # ── Phase 1: P5 IMMUNIZE ─────────────────────────────────

    def phase1_boot_p5(self) -> bool:
        """Phase 1: Boot P5 Pyre Praetorian FIRST.

        P5 is the immune system. Nothing else starts until P5 is healthy.
        Runs hfo_p5_daemon.py with all 5 patrol tasks.
        """
        print(f"\n  {'─'*60}")
        print(f"  PHASE 1: P5 IMMUNIZE — Pyre Praetorian")
        print(f"  Model: {PORT_MODELS['P5']['model']} ({PORT_MODELS['P5']['vram_gb']} GB)")
        print(f"  Reason: {PORT_MODELS['P5']['reason']}")
        print(f"  {'─'*60}")

        ok = self._start_daemon_process(
            "P5",
            "hfo_p5_daemon.py",
            args=[],  # Default: all 5 tasks, continuous mode
        )

        if ok:
            _write_stigmergy(
                "hfo.gen89.sandbox.p5_boot",
                {
                    "model": PORT_MODELS["P5"]["model"],
                    "pid": self.daemons["P5"].pid,
                    "phase": "phase1",
                },
                subject="sandbox:P5",
            )

            # Wait for P5 to establish its first patrol
            print(f"  Waiting for P5 to complete first patrol cycle...")
            time.sleep(10)

            # Verify P5 is still alive
            proc = self.daemons["P5"].process
            if proc and proc.poll() is not None:
                print(f"  [✗] P5 died during initial patrol (exit={proc.returncode})")
                self.daemons["P5"].state = PortState.DEAD
                return False

            print(f"  [✓] P5 IMMUNIZE: Online and patrolling")

        return ok

    # ── Phase 2: P4 DISRUPT ──────────────────────────────────

    def phase2_boot_p4(self) -> bool:
        """Phase 2: Boot P4 Red Regnant Singer + optionally Song Prospector.

        Singer daemon: NO LLM (pure SSOT scan) — always safe.
        Song Prospector: Uses LLM — only if VRAM budget allows.
        """
        print(f"\n  {'─'*60}")
        print(f"  PHASE 2: P4 DISRUPT — Red Regnant")
        print(f"  Singer: No LLM (pure SSOT scan)")
        print(f"  Song Prospector: {'ENABLED' if self.enable_prospector else 'PAUSED (VRAM constrained)'}")
        print(f"  {'─'*60}")

        # Singer daemon (always starts — no VRAM needed)
        singer_ok = self._start_daemon_process(
            "P4_SINGER",
            "hfo_singer_daemon.py",
            args=[],
        )

        if singer_ok:
            _write_stigmergy(
                "hfo.gen89.sandbox.p4_singer_boot",
                {
                    "pid": self.daemons["P4_SINGER"].pid,
                    "model": None,
                    "phase": "phase2",
                },
                subject="sandbox:P4:singer",
            )

        # Song Prospector (conditional)
        prospector_ok = True
        if self.enable_prospector:
            prospector_ok = self._start_daemon_process(
                "P4_PROSPECTOR",
                "hfo_song_prospector.py",
                args=[],
            )
            if prospector_ok:
                _write_stigmergy(
                    "hfo.gen89.sandbox.p4_prospector_boot",
                    {
                        "pid": self.daemons["P4_PROSPECTOR"].pid,
                        "model": PORT_MODELS["P4_PROSPECTOR"]["model"],
                        "phase": "phase2",
                    },
                    subject="sandbox:P4:prospector",
                )
        else:
            self.daemons["P4_PROSPECTOR"].state = PortState.PAUSED

        # Check Nataraja activation
        p5_alive = self.daemons["P5"].state == PortState.HEALTHY
        p4_alive = singer_ok
        if p5_alive and p4_alive:
            print(f"\n  ☳☲ NATARAJA DANCE ACTIVATED — Singer + Dancer online ☲☳")
            _write_stigmergy(
                "hfo.gen89.sandbox.nataraja_activated",
                {"p4_state": "healthy", "p5_state": "healthy"},
                subject="sandbox:nataraja",
            )

        return singer_ok

    # ── Phase 3: P2 SHAPE ────────────────────────────────────

    def phase3_boot_p2(self) -> bool:
        """Phase 3: Boot P2 Mirror Magus — Cursed Chimera Loop.

        INVARIANT: P5 MUST be healthy before P2 starts.
        If P5 is not healthy, P2 is BLOCKED.

        Runs chimera loop in single-model daemon mode (lightweight).
        Full 2x2 evolutionary grid available via manual batch runs.
        """
        print(f"\n  {'─'*60}")
        print(f"  PHASE 3: P2 SHAPE — Mirror Magus (Cursed Chimera Loop)")
        print(f"  Model: {PORT_MODELS['P2']['model']} ({PORT_MODELS['P2']['vram_gb']} GB)")
        print(f"  Mode: Single-model daemon (24/7 lightweight)")
        print(f"  Safety: Gated by P5 IMMUNIZE structural validation")
        print(f"  {'─'*60}")

        # SAFETY SPINE GATE: P5 must be healthy
        p5 = self.daemons["P5"]
        if p5.state != PortState.HEALTHY:
            self.daemons["P2"].state = PortState.BLOCKED
            print(f"  [✗] P2 BLOCKED: P5 is {p5.state.value} — "
                  f"safety spine requires P5 healthy before P2 starts")
            _write_stigmergy(
                "hfo.gen89.sandbox.p2_blocked",
                {
                    "reason": f"P5 state is {p5.state.value}, not healthy",
                    "safety_spine": "P2 cannot create without P5 immune system",
                },
                subject="sandbox:P2:blocked",
            )
            return False

        # Boot P2 chimera loop in quick-test daemon mode
        ok = self._start_daemon_process(
            "P2",
            "hfo_p2_chimera_loop.py",
            args=[
                "--test-model", PORT_MODELS["P2"]["model"],
                "--problems", "5",
            ],
        )

        if ok:
            _write_stigmergy(
                "hfo.gen89.sandbox.p2_boot",
                {
                    "model": PORT_MODELS["P2"]["model"],
                    "pid": self.daemons["P2"].pid,
                    "phase": "phase3",
                    "mode": "single-model-daemon",
                    "safety_spine": "P5 healthy — gate passed",
                },
                subject="sandbox:P2",
            )

        return ok

    # ── Phase 4: Watchdog ────────────────────────────────────

    def phase4_watchdog(self):
        """Phase 4: Supervisor watchdog that monitors all ports.

        Key invariant:  If P5 dies, P2 is PAUSED immediately.
                        When P5 recovers, P2 resumes.
        """
        print(f"\n  {'─'*60}")
        print(f"  PHASE 4: WATCHDOG — Monitoring all sandbox ports")
        print(f"  Invariant: P5 down → P2 paused")
        print(f"  Check interval: 30s")
        print(f"  {'─'*60}")

        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="sandbox-watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _watchdog_loop(self):
        """Continuous monitoring loop."""
        p2_was_paused = False
        check_count = 0

        while not self.shutdown_event.is_set():
            check_count += 1
            now = _now_iso()

            # Check each daemon's subprocess health
            for key, daemon in self.daemons.items():
                if daemon.state in (PortState.STOPPED, PortState.BLOCKED, PortState.PAUSED):
                    continue

                if daemon.process:
                    if daemon.process.poll() is not None:
                        # Process exited
                        old_state = daemon.state
                        daemon.state = PortState.DEAD
                        daemon.error_count += 1
                        if old_state == PortState.HEALTHY:
                            print(f"  [☠] {key} ({daemon.name[:30]}) DIED "
                                  f"(exit={daemon.process.returncode})")
                            _write_stigmergy(
                                "hfo.gen89.sandbox.daemon_death",
                                {
                                    "port_key": key,
                                    "exit_code": daemon.process.returncode,
                                    "error_count": daemon.error_count,
                                },
                                subject=f"sandbox:{key}:death",
                            )

            # SAFETY SPINE ENFORCEMENT: P5 down → P2 paused
            p5 = self.daemons["P5"]
            p2 = self.daemons["P2"]

            if p5.state != PortState.HEALTHY and p2.state == PortState.HEALTHY:
                # P5 died! Pause P2 immediately
                if p2.process and p2.process.poll() is None:
                    p2.process.terminate()
                    print(f"  [⚠] P2 PAUSED — P5 is {p5.state.value}. "
                          f"Safety spine requires P5 healthy.")
                p2.state = PortState.PAUSED
                p2_was_paused = True
                _write_stigmergy(
                    "hfo.gen89.sandbox.p2_paused",
                    {
                        "reason": f"P5 state: {p5.state.value}",
                        "safety_spine": "P2 cannot create without P5 immune system",
                    },
                    subject="sandbox:P2:paused",
                )

            elif p5.state == PortState.HEALTHY and p2.state == PortState.PAUSED:
                # P5 recovered! Resume P2
                print(f"  [✓] P5 recovered — resuming P2...")
                ok = self._start_daemon_process(
                    "P2",
                    "hfo_p2_chimera_loop.py",
                    args=[
                        "--test-model", PORT_MODELS["P2"]["model"],
                        "--problems", "5",
                    ],
                )
                if ok:
                    p2_was_paused = False
                    _write_stigmergy(
                        "hfo.gen89.sandbox.p2_resumed",
                        {"safety_spine": "P5 recovered, P2 resumed"},
                        subject="sandbox:P2:resumed",
                    )

            # Heartbeat event (every 5 checks = ~150s)
            if check_count % 5 == 0:
                states = {
                    k: d.state.value for k, d in self.daemons.items()
                }
                healthy_count = sum(
                    1 for d in self.daemons.values()
                    if d.state == PortState.HEALTHY
                )
                _write_stigmergy(
                    "hfo.gen89.sandbox.heartbeat",
                    {
                        "states": states,
                        "healthy_count": healthy_count,
                        "total_count": len(self.daemons),
                        "check_count": check_count,
                        "p5_p2_spine": "intact" if p5.state == PortState.HEALTHY else "broken",
                    },
                    subject="sandbox:heartbeat",
                )

            # Sleep in small increments for responsive shutdown
            for _ in range(30):
                if self.shutdown_event.is_set():
                    return
                time.sleep(1)

    # ── FULL BOOT SEQUENCE ───────────────────────────────────

    def boot(self, ports: Optional[list[str]] = None) -> bool:
        """Execute the full boot sequence.

        Default boots all: P5 → P4 → P2.
        Can specify subset: --ports P5,P4 to skip P2.
        """
        boot_all = ports is None
        boot_ports = set(p.upper() for p in (ports or ["P5", "P4", "P2"]))

        # Phase 0: Preflight
        if not self.phase0_preflight():
            print(f"\n  ABORT: Preflight failed. Fix issues above and retry.")
            return False

        # Phase 1: P5 IMMUNIZE (always boot if in scope)
        if "P5" in boot_ports:
            if not self.phase1_boot_p5():
                print(f"\n  ABORT: P5 failed to start. "
                      f"Cannot proceed without immune system.")
                return False
        else:
            print(f"\n  SKIP: P5 not in boot ports. "
                  f"Warning: no immune system active!")

        # Phase 2: P4 DISRUPT
        if "P4" in boot_ports:
            if not self.phase2_boot_p4():
                print(f"\n  WARNING: P4 Singer failed. "
                      f"Continuing without adversarial pressure.")
                # Non-fatal — P2 can still run (P5 is the gate)

        # Phase 3: P2 SHAPE (only if P5 is healthy)
        if "P2" in boot_ports:
            if not self.phase3_boot_p2():
                print(f"\n  WARNING: P2 blocked or failed to start.")
                # Non-fatal for the launcher itself

        # Phase 4: Watchdog (always)
        self.phase4_watchdog()

        # Boot complete
        _write_stigmergy(
            "hfo.gen89.sandbox.boot_complete",
            {
                "ports_requested": sorted(boot_ports),
                "states": {k: d.state.value for k, d in self.daemons.items()},
                "safety_spine": (
                    "intact" if self.daemons["P5"].state == PortState.HEALTHY
                    else "broken"
                ),
            },
            subject="sandbox:boot",
        )

        return True

    # ── SHUTDOWN ─────────────────────────────────────────────

    def shutdown(self):
        """Graceful shutdown: P2 → P4 → P5 (opposite of boot)."""
        print(f"\n  Shutting down sandbox (P2 → P4 → P5)...")

        self.shutdown_event.set()

        # Stop order: creator first, immune system last
        for key in ["P2", "P4_PROSPECTOR", "P4_SINGER", "P5"]:
            daemon = self.daemons[key]
            if daemon.process and daemon.process.poll() is None:
                print(f"  Stopping {key} (PID {daemon.pid})...")
                daemon.process.terminate()
                try:
                    daemon.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    daemon.process.kill()
            elif daemon.stop_event:
                daemon.stop_event.set()
            daemon.state = PortState.STOPPED

        _write_stigmergy(
            "hfo.gen89.sandbox.shutdown",
            {
                "states": {k: d.state.value for k, d in self.daemons.items()},
            },
            subject="sandbox:shutdown",
        )

        print(f"  Sandbox shutdown complete.\n")

    # ── STATUS ───────────────────────────────────────────────

    def print_status(self):
        """Print formatted sandbox status."""
        states = {k: d for k, d in self.daemons.items()}

        p5 = states["P5"]
        p5_alive = p5.state == PortState.HEALTHY
        p2 = states["P2"]

        print(f"\n{'═'*70}")
        print(f"  HFO CORRECT-BY-CONSTRUCTION SANDBOX — Gen{GEN}")
        print(f"  Safety Spine: {'INTACT ✓' if p5_alive else 'BROKEN ✗'}")
        print(f"{'═'*70}")

        icon_map = {
            "healthy": "●",
            "booting": "○",
            "stopped": "○",
            "degraded": "◉",
            "paused": "◎",
            "dead": "☠",
            "blocked": "✗",
        }

        for key, daemon in states.items():
            icon = icon_map.get(daemon.state.value, "?")
            model_str = daemon.model or "(no LLM)"
            pid_str = f"PID={daemon.pid}" if daemon.pid else ""
            vram_str = f"{daemon.vram_gb:.1f}GB" if daemon.vram_gb > 0 else "0GB"

            print(f"  {icon} {key:<15} {daemon.state.value:<10} "
                  f"model={model_str:<16} vram={vram_str:<6} {pid_str}")

        # VRAM summary
        total_vram = sum(
            d.vram_gb for d in self.daemons.values()
            if d.state in (PortState.HEALTHY, PortState.BOOTING)
        )
        print(f"\n  VRAM: {total_vram:.1f}/{VRAM_CEILING_GB:.1f} GB allocated")
        print(f"  P6 swarm: ~{P6_RESERVED_GB:.1f} GB (managed separately)")

        # Safety spine status
        if p5_alive:
            if p2.state == PortState.HEALTHY:
                print(f"\n  SAFETY SPINE: P2 creating ↔ P5 gating [ACTIVE]")
            elif p2.state == PortState.PAUSED:
                print(f"\n  SAFETY SPINE: P2 paused (will resume when P5 ok)")
            elif p2.state == PortState.BLOCKED:
                print(f"\n  SAFETY SPINE: P2 blocked (dependency issue)")
            else:
                print(f"\n  SAFETY SPINE: P5 ready, P2 not started yet")
        else:
            print(f"\n  SAFETY SPINE: BROKEN — P5 is {p5.state.value}")

        # Nataraja status
        p4_alive = any(
            states[k].state == PortState.HEALTHY
            for k in ["P4_SINGER", "P4_PROSPECTOR"]
        )
        if p4_alive and p5_alive:
            print(f"  NATARAJA: ACTIVE ☳☲ (Singer + Dancer both online)")
        elif p4_alive:
            print(f"  NATARAJA: WAIL_ONLY (Singer sings but no dancer)")
        elif p5_alive:
            print(f"  NATARAJA: VIGIL (Dancer watches but no singer)")
        else:
            print(f"  NATARAJA: SILENT (both offline)")

        print(f"{'═'*70}\n")


# ═══════════════════════════════════════════════════════════════
# § 5  LOAD STATE / STATUS COMMAND
# ═══════════════════════════════════════════════════════════════

def show_status_from_stigmergy():
    """Show sandbox status from SSOT events (no running supervisor needed)."""
    events = _read_recent_events("hfo.gen89.sandbox.%", limit=20)

    if not events:
        print("\n  No sandbox events in SSOT. Sandbox has not been started.")
        return

    print(f"\n{'═'*70}")
    print(f"  HFO SANDBOX — Recent Events (from SSOT)")
    print(f"{'═'*70}")

    for evt in events[:15]:
        ts = evt["timestamp"][:19]
        etype = evt["event_type"].replace("hfo.gen89.sandbox.", "")
        data = evt.get("data", {})
        # Handle nested data structures
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        summary = ""
        if isinstance(data, dict):
            if "states" in data:
                summary = " | ".join(
                    f"{k}={v}" for k, v in data.get("states", {}).items()
                )
            elif "reason" in data:
                summary = data["reason"][:80]
            elif "model" in data:
                summary = f"model={data['model']}"
            elif "checks" in data:
                summary = f"{len(data.get('checks', []))} checks"

        print(f"  {ts}  {etype:<30} {summary[:50]}")

    print(f"{'═'*70}\n")


# ═══════════════════════════════════════════════════════════════
# § 6  MAIN CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="HFO Correct-by-Construction Sandbox Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Boot Sequence (fail-closed, order-dependent):
              Phase 0: Preflight — VRAM, SSOT, P6 swarm health
              Phase 1: P5 IMMUNIZE — immune system MUST be online first
              Phase 2: P4 DISRUPT — Singer (no LLM) + optional Prospector
              Phase 3: P2 SHAPE  — Chimera loop (only if P5 healthy)
              Phase 4: Watchdog  — P5 down → P2 paused automatically

            Safety Spine:
              P2 creates ↔ P5 gates. P2 NEVER runs without P5 healthy.

            VRAM Budget (16 GB total):
              P5 phi4:14b:   ~8.4 GB  (high intelligence immune system)
              P2 gemma3:4b:  ~3.1 GB  (lightweight creation)
              P4 Singer:      0 GB    (no LLM — pure SSOT scan)
              P6 swarm:      ~3.1 GB  (managed separately)
              ─────────────────────
              Total:         ~14.6 GB  (within 16 GB ceiling)

            Examples:
              python hfo_sandbox_launcher.py                      # Full sandbox
              python hfo_sandbox_launcher.py --ports P5,P4        # P5+P4 only
              python hfo_sandbox_launcher.py --dry-run             # Preview
              python hfo_sandbox_launcher.py --status              # Check SSOT
              python hfo_sandbox_launcher.py --with-prospector     # Enable mining
              python hfo_sandbox_launcher.py --p5-model gemma3:12b # Override P5
        """),
    )
    parser.add_argument("--ports", type=str, default=None,
                        help="Comma-separated ports to start (default: P5,P4,P2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would start without starting")
    parser.add_argument("--status", action="store_true",
                        help="Show sandbox status from SSOT and exit")
    parser.add_argument("--stop", action="store_true",
                        help="Signal running sandbox to stop (writes stop event)")
    parser.add_argument("--with-prospector", action="store_true",
                        help="Enable P4 Song Prospector (uses extra VRAM)")
    parser.add_argument("--p2-model", type=str, default=None,
                        help="Override P2 model (default: gemma3:4b)")
    parser.add_argument("--p5-model", type=str, default=None,
                        help="Override P5 model (default: phi4:14b)")
    parser.add_argument("--force-unload", action="store_true",
                        help="Unload all Ollama models before booting (clears VRAM)")
    parser.add_argument("--kill-existing", action="store_true",
                        help="Kill existing daemon processes before booting")

    args = parser.parse_args()

    # Status mode
    if args.status:
        show_status_from_stigmergy()
        return

    # Stop mode (write a stop event to SSOT for watchers)
    if args.stop:
        _write_stigmergy(
            "hfo.gen89.sandbox.stop_requested",
            {"operator": "CLI", "timestamp": _now_iso()},
            subject="sandbox:stop",
        )
        print("  Stop event written to SSOT. Running sandboxes should wind down.")
        return

    # Parse ports
    ports = None
    if args.ports:
        ports = [p.strip().upper() for p in args.ports.split(",")]

    # Create supervisor
    supervisor = SandboxSupervisor(
        p2_model=args.p2_model,
        p5_model=args.p5_model,
        enable_prospector=args.with_prospector,
        dry_run=args.dry_run,
        force_unload=args.force_unload,
        kill_existing=args.kill_existing,
    )

    # Boot
    ok = supervisor.boot(ports=ports)
    if not ok and not args.dry_run:
        print(f"\n  Sandbox boot FAILED. Check errors above.")
        sys.exit(1)

    if args.dry_run:
        print(f"\n  DRY RUN complete. No daemons started.")
        supervisor.print_status()
        return

    # Interactive / monitoring loop
    supervisor.print_status()
    print("  Sandbox running. Commands: status | stop | quit")
    print("  (Watchdog monitors P5→P2 safety spine every 30s)\n")

    try:
        while True:
            try:
                cmd = input("  > ").strip().lower()
            except EOFError:
                break

            if cmd in ("quit", "exit", "q", "stop"):
                break
            elif cmd == "status":
                supervisor.print_status()
            elif cmd == "help":
                print("  Commands: status | stop | quit")
            else:
                print(f"  Unknown: {cmd}. Try: status, quit")
    except KeyboardInterrupt:
        pass
    finally:
        supervisor.shutdown()


if __name__ == "__main__":
    main()
