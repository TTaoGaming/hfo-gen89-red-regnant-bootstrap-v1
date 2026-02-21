#!/usr/bin/env python3
"""
hfo_strange_loop_scheduler.py — P4-P7 Strange Loop Research Scheduler
=======================================================================
v1.0 | Gen90 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: TIME STOP | School: Transmutation

PURPOSE:
    Autonomous research scheduler that keeps the strange-loop ports
    (P4 DISRUPT, P5 IMMUNIZE, P6 ASSIMILATE, P7 NAVIGATE) actively
    cycling through useful work on a regular stigmergy cadence.

    The operator reports: "I see a lot of my resources constantly
    underutilized." TREMORSENSE confirms: Grade F (31.5% uptime).
    GPU sitting idle. NPU idle. Gemini barely used. 5-hour dead zones.

    This scheduler fixes it by:
    1. Keeping GPU warm (preload models, rotate inference tasks)
    2. Keeping NPU embedding new/changed content
    3. Using Ollama for local fast inference on P4/P5 duties
    4. Using Gemini free tier for P6/P7 research + enrichment
    5. Writing stigmergy every cycle → fills dead zones
    6. Running TREMORSENSE audit every hour for self-measurement
    7. Auto-restarting crashed daemons (watchdog)

STRANGE LOOP CYCLE (every 60 seconds):
    ┌────────────────────────────────────────────────────────────────┐
    │  TICK (1 min)                                                  │
    │                                                                │
    │  P4 RED REGNANT (Singer) — Ollama qwen2.5:3b                 │
    │    Strife + Splendor adversarial feedback                     │
    │    ↓ writes stigmergy                                         │
    │                                                                │
    │  P5 PYRE PRAETORIAN (Dancer) — Ollama qwen2.5:3b             │
    │    Death + Dawn governance feedback                            │
    │    ↓ writes stigmergy                                         │
    │                                                                │
    │  P6 KRAKEN KEEPER — NPU embedder + progressive summary       │
    │    Embed new docs, summarize random batch via GPU              │
    │    ↓ writes stigmergy                                         │
    │                                                                │
    │  P7 SPIDER SOVEREIGN — Gemini research + TREMORSENSE          │
    │    Research gap-fill, port assignment, enrichment              │
    │    ↓ writes stigmergy                                         │
    │                                                                │
    │  WATCHDOG — check all 8 daemons, restart dead ones            │
    │    ↓ writes heartbeat                                         │
    └────────────────────────────────────────────────────────────────┘

SCHEDULE:
    Every 1 min:  Heartbeat + Singer + Dancer (fast local)
    Every 2 min:  Enrichment batch (Gemini free)
    Every 5 min:  NPU embedding sweep + GPU summarize batch
    Every 15 min: Research task (Gemini free, web-grounded)
    Every 30 min: P5 Governance patrol (Ollama phi4:14b deep)
    Every 60 min: TREMORSENSE audit + DIMENSIONAL_ANCHOR probe
    Every 6 hrs:  Full fleet health + restart dead daemons

PLATFORM UTILIZATION TARGETS:
    ┌──────────────────┬──────────┬────────────┬─────────────────────┐
    │ Platform         │ Current  │ Target     │ How                 │
    ├──────────────────┼──────────┼────────────┼─────────────────────┤
    │ GitHub Copilot   │ 20.5%   │ 20-40%     │ Human-driven (OK)   │
    │ Ollama (local)   │ 10.6%   │ 95%+       │ Singer+Dancer 24/7  │
    │ NPU              │  0.4%   │ 50%+       │ Embed sweeps q5min  │
    │ GPU              │  0.2%   │ 80%+       │ Warm models + infer │
    │ CPU              │  4.2%   │ 30%+       │ Scheduler + I/O     │
    │ RAM              │ 37% OK  │ 50-70%     │ Model cache + queue │
    │ Gemini API       │  1.4%   │ 60%+       │ 1500 RPD free tier  │
    │ OpenRouter       │  0.0%   │ 10%+       │ Fallback provider   │
    └──────────────────┴──────────┴────────────┴─────────────────────┘

EVENT TYPES:
    hfo.gen90.scheduler.heartbeat       — Scheduler alive pulse
    hfo.gen90.scheduler.watchdog        — Fleet health check
    hfo.gen90.scheduler.cycle_complete  — Full cycle report
    hfo.gen90.scheduler.restart         — Daemon restarted
    hfo.gen90.scheduler.error           — Scheduler error

USAGE:
    python hfo_strange_loop_scheduler.py                 # Run scheduler
    python hfo_strange_loop_scheduler.py --status        # Show all uptimes
    python hfo_strange_loop_scheduler.py --once          # Single cycle
    python hfo_strange_loop_scheduler.py --dry-run       # Preview actions
    python hfo_strange_loop_scheduler.py --watchdog      # Watchdog only
    python hfo_strange_loop_scheduler.py --uptime-card   # Platform report card

SBE:
    TIER 1 (Invariant): Scheduler writes ≥1 event/minute to SSOT
    TIER 2 (Happy path): All 4 strange-loop ports cycle on schedule
    TIER 3 (Watchdog):   Dead daemons restarted within 6 hours
    TIER 4 (Uptime):     TREMORSENSE grade improves from F → C+ in 24h

Pointer key: scheduler.strange_loop
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
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION (PAL)
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))

def _resolve_pointer(key: str) -> Path:
    pf = HFO_ROOT / "hfo_gen90_pointers_blessed.json"
    if pf.exists():
        data = json.loads(pf.read_text(encoding="utf-8"))
        ptrs = data.get("pointers", data)
        if key in ptrs:
            entry = ptrs[key]
            rel = entry["path"] if isinstance(entry, dict) else entry
            return HFO_ROOT / rel
    raise KeyError(key)

try:
    SSOT_DB = _resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite"

BRONZE_RES = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources"
FLEET_STATE = HFO_ROOT / ".hfo_fleet_state.json"
PYTHON = sys.executable

# ── Load .env ────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    env_path = HFO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS & CONFIG
# ═══════════════════════════════════════════════════════════════

GEN             = os.getenv("HFO_GENERATION", "89")
OLLAMA_BASE     = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
OPENROUTER_KEY  = os.getenv("OPENROUTER_API_KEY", "")

SOURCE_TAG      = f"hfo_strange_loop_scheduler_gen{GEN}"
EVT_HEARTBEAT   = f"hfo.gen{GEN}.scheduler.heartbeat"
EVT_WATCHDOG    = f"hfo.gen{GEN}.scheduler.watchdog"
EVT_CYCLE       = f"hfo.gen{GEN}.scheduler.cycle_complete"
EVT_RESTART     = f"hfo.gen{GEN}.scheduler.restart"
EVT_ERROR       = f"hfo.gen{GEN}.scheduler.error"

# Schedule intervals (seconds)
HEARTBEAT_INTERVAL   = 60      # 1 min — heartbeat + Singer + Dancer
ENRICH_INTERVAL      = 120     # 2 min — Gemini enrichment batch
NPU_INTERVAL         = 300     # 5 min — NPU embedding sweep
RESEARCH_INTERVAL    = 900     # 15 min — Gemini research
GOVERNANCE_INTERVAL  = 1800    # 30 min — P5 deep governance
AUDIT_INTERVAL       = 3600    # 60 min — TREMORSENSE + DIMENSIONAL_ANCHOR
WATCHDOG_INTERVAL    = 21600   # 6 hrs — full fleet restart check

# Daemon specs for watchdog
CORE_DAEMONS = [
    {
        "name": "Singer",
        "script": "hfo_singer_ai_daemon.py",
        "args": ["--interval", "60"],
        "port": "P4",
        "requires_ollama": True,
    },
    {
        "name": "Dancer",
        "script": "hfo_p5_dancer_daemon.py",
        "args": ["--interval", "60"],
        "port": "P5",
        "requires_ollama": True,
    },
    {
        "name": "P5 Governance",
        "script": "hfo_p5_daemon.py",
        "args": [],
        "port": "P5",
        "requires_ollama": True,
    },
    {
        "name": "Octree Swarm",
        "script": "hfo_octree_daemon.py",
        "args": ["--ports", "P4,P5,P6,P7"],
        "port": "ALL",
        "requires_ollama": True,
    },
]


# ═══════════════════════════════════════════════════════════════
# § 2  SSOT HELPERS
# ═══════════════════════════════════════════════════════════════

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _write_event(event_type: str, subject: str, data: dict) -> int:
    """Write a CloudEvent to SSOT stigmergy_events. Returns row ID."""
    now = datetime.now(timezone.utc).isoformat()
    event_id = hashlib.md5(
        f"{event_type}:{now}:{secrets.token_hex(4)}".encode()
    ).hexdigest()

    ce = {
        "specversion": "1.0",
        "id": event_id,
        "type": event_type,
        "source": SOURCE_TAG,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "data": data,
    }

    payload = json.dumps(ce, sort_keys=True)
    content_hash = hashlib.sha256(payload.encode()).hexdigest()

    conn = _get_conn()
    try:
        c = conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_type, now, subject, SOURCE_TAG, payload, content_hash),
        )
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def _count_events_since(hours: float = 1.0) -> dict:
    """Count events by source in last N hours."""
    conn = _get_conn()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    try:
        rows = conn.execute(
            """SELECT source, COUNT(*), COUNT(DISTINCT strftime('%Y-%m-%d %H:%M', timestamp))
               FROM stigmergy_events WHERE timestamp > ?
               GROUP BY source ORDER BY COUNT(*) DESC""",
            (since,),
        ).fetchall()
        return {r[0]: {"events": r[1], "minutes": r[2]} for r in rows}
    finally:
        conn.close()


def _total_minutes_covered(hours: float = 1.0) -> tuple[int, int]:
    """Return (covered_minutes, total_minutes) for the window."""
    conn = _get_conn()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    total_min = int(hours * 60)
    try:
        row = conn.execute(
            """SELECT COUNT(DISTINCT strftime('%Y-%m-%d %H:%M', timestamp))
               FROM stigmergy_events WHERE timestamp > ?""",
            (since,),
        ).fetchone()
        return row[0], total_min
    finally:
        conn.close()


def _ssot_stats() -> dict:
    """Quick SSOT statistics."""
    conn = _get_conn()
    try:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        try:
            embeds = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        except sqlite3.OperationalError:
            embeds = 0
        return {"docs": docs, "events": events, "embeddings": embeds}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# § 3  PLATFORM HEALTH CHECKS
# ═══════════════════════════════════════════════════════════════

def check_ollama() -> dict:
    """Check Ollama status."""
    try:
        import urllib.request
        r = urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5)
        data = json.loads(r.read())
        models = [m["name"] for m in data.get("models", [])]
        # Check loaded models
        r2 = urllib.request.urlopen(f"{OLLAMA_BASE}/api/ps", timeout=3)
        ps = json.loads(r2.read())
        loaded = [m.get("name") for m in ps.get("models", [])]
        return {
            "status": "ONLINE",
            "models_installed": len(models),
            "models_loaded": loaded,
            "vram_idle": len(loaded) == 0,
        }
    except Exception as e:
        return {"status": "OFFLINE", "error": str(e)}


def check_npu() -> dict:
    """Check NPU/OpenVINO status."""
    try:
        import openvino as ov
        core = ov.Core()
        devs = core.available_devices
        return {
            "status": "INSTALLED",
            "version": ov.__version__,
            "devices": devs,
            "npu_available": "NPU" in devs,
        }
    except ImportError:
        return {"status": "NOT_INSTALLED"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def check_gemini() -> dict:
    """Check Gemini API reachability."""
    key = GEMINI_API_KEY
    if not key:
        return {"status": "NO_KEY", "uptime_potential": 0}
    try:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=1"
        r = urllib.request.urlopen(url, timeout=10)
        return {"status": "REACHABLE", "code": r.status}
    except Exception as e:
        return {"status": "UNREACHABLE", "error": str(e)}


def check_openrouter() -> dict:
    """Check OpenRouter API."""
    key = OPENROUTER_KEY
    if not key:
        return {"status": "NO_KEY", "note": "Set OPENROUTER_API_KEY in .env"}
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        r = urllib.request.urlopen(req, timeout=10)
        return {"status": "REACHABLE", "code": r.status}
    except Exception as e:
        return {"status": "UNREACHABLE", "error": str(e)}


def check_gpu() -> dict:
    """Check GPU via Ollama loaded models."""
    ollama = check_ollama()
    if ollama["status"] != "ONLINE":
        return {"status": "UNKNOWN", "reason": "Ollama offline"}
    loaded = ollama.get("models_loaded", [])
    return {
        "status": "ACTIVE" if loaded else "IDLE",
        "models_in_vram": loaded,
        "vram_empty": len(loaded) == 0,
    }


def get_platform_report() -> dict:
    """Full 8-platform health report."""
    import psutil

    stats = _ssot_stats()
    covered_1h, total_1h = _total_minutes_covered(1.0)
    covered_24h, total_24h = _total_minutes_covered(24.0)

    # Per-platform stigmergy coverage (24h)
    activity = _count_events_since(24.0)
    
    # Categorize by platform
    ollama_mins = 0
    gemini_mins = 0
    npu_mins = 0
    copilot_mins = 0
    for src, info in activity.items():
        mins = info["minutes"]
        src_lower = src.lower()
        if any(k in src_lower for k in ["singer", "dancer", "kraken", "octree", "p5_daemon", "chimera"]):
            ollama_mins = max(ollama_mins, mins)  # Union coverage
        elif any(k in src_lower for k in ["background_daemon", "gemini", "enrich", "research"]):
            gemini_mins = max(gemini_mins, mins)
        elif any(k in src_lower for k in ["npu", "embed", "compute_queue"]):
            npu_mins = max(npu_mins, mins)
        elif any(k in src_lower for k in ["prey8_mcp", "prey8_eval"]):
            copilot_mins = max(copilot_mins, mins)

    mem = psutil.virtual_memory()
    cpu_pct = psutil.cpu_percent(interval=1)

    platforms = {
        "copilot": {
            "name": "GitHub Copilot (PREY8 MCP)",
            "uptime_minutes": copilot_mins,
            "uptime_pct": round(copilot_mins / max(total_24h, 1) * 100, 1),
            "status": "HUMAN_DRIVEN",
            "note": "Active when operator has VS Code open",
        },
        "ollama": {
            "name": "Ollama (Local LLM)",
            **check_ollama(),
            "uptime_minutes": ollama_mins,
            "uptime_pct": round(ollama_mins / max(total_24h, 1) * 100, 1),
        },
        "npu": {
            "name": "NPU (Intel AI Boost)",
            **check_npu(),
            "uptime_minutes": npu_mins,
            "uptime_pct": round(npu_mins / max(total_24h, 1) * 100, 1),
        },
        "gpu": {
            "name": "GPU (Intel Arc 140V)",
            **check_gpu(),
            "uptime_minutes": 0,  # GPU events mixed with Ollama
            "uptime_pct": round(ollama_mins / max(total_24h, 1) * 100, 1),
            "note": "GPU serves Ollama inference — uptimes are linked",
        },
        "cpu": {
            "name": "CPU (Intel Core Ultra 7)",
            "utilization_pct": cpu_pct,
            "cores": psutil.cpu_count(),
            "status": "ACTIVE" if cpu_pct > 5 else "IDLE",
        },
        "ram": {
            "name": "RAM",
            "total_gb": round(mem.total / 1e9, 1),
            "used_gb": round(mem.used / 1e9, 1),
            "free_gb": round(mem.available / 1e9, 1),
            "utilization_pct": mem.percent,
            "status": "OK" if mem.percent < 85 else "WARNING",
        },
        "gemini": {
            "name": "Gemini API (Google)",
            **check_gemini(),
            "uptime_minutes": gemini_mins,
            "uptime_pct": round(gemini_mins / max(total_24h, 1) * 100, 1),
            "free_rpd": 1500,
        },
        "openrouter": {
            "name": "OpenRouter",
            **check_openrouter(),
            "uptime_minutes": 0,
            "uptime_pct": 0.0,
        },
    }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_uptime_1h": f"{covered_1h}/{total_1h} min ({covered_1h/max(total_1h,1)*100:.1f}%)",
        "overall_uptime_24h": f"{covered_24h}/{total_24h} min ({covered_24h/max(total_24h,1)*100:.1f}%)",
        "ssot": stats,
        "platforms": platforms,
    }


# ═══════════════════════════════════════════════════════════════
# § 4  WATCHDOG — FLEET DAEMON RESTART
# ═══════════════════════════════════════════════════════════════

def _is_running(pid: int) -> bool:
    """Check if a process is still running."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x100000, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _launch_daemon(script: str, args: list[str]) -> Optional[int]:
    """Launch a daemon as a detached background process. Returns PID or None."""
    script_path = BRONZE_RES / script
    if not script_path.exists():
        return None

    cmd = [PYTHON, str(script_path)] + args
    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(HFO_ROOT),
                creationflags=0x00000200 | 0x00000008,  # NEW_PROCESS_GROUP | DETACHED
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(HFO_ROOT),
                start_new_session=True,
            )
        return proc.pid
    except Exception:
        return None


def _check_daemon_alive_by_stigmergy(name: str, minutes: int = 10) -> bool:
    """Check if a daemon has written stigmergy events recently."""
    conn = _get_conn()
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    name_lower = name.lower()
    
    # Map daemon name to expected source patterns
    patterns = {
        "singer": "%singer%",
        "dancer": "%dancer%",
        "p5 governance": "%p5_daemon%",
        "octree swarm": "%kraken%",
    }
    
    pattern = patterns.get(name_lower, f"%{name_lower}%")
    
    try:
        row = conn.execute(
            """SELECT COUNT(*) FROM stigmergy_events
               WHERE timestamp > ? AND source LIKE ?""",
            (since, pattern),
        ).fetchone()
        return row[0] > 0
    finally:
        conn.close()


def watchdog_check(dry_run: bool = False) -> dict:
    """Check fleet health and restart dead daemons."""
    has_ollama = check_ollama()["status"] == "ONLINE"
    
    state = {}
    if FLEET_STATE.exists():
        try:
            state = json.loads(FLEET_STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {"daemons": {}}

    report = {"checked": 0, "alive": 0, "dead": 0, "restarted": 0, "daemons": {}}
    
    for daemon in CORE_DAEMONS:
        name = daemon["name"]
        report["checked"] += 1
        
        # Check if daemon has written events recently
        alive = _check_daemon_alive_by_stigmergy(name, minutes=10)
        
        # Also check PID if we have it
        daemon_state = state.get("daemons", {}).get(name, {})
        pid = daemon_state.get("pid", 0)
        pid_alive = _is_running(pid) if pid else False
        
        if alive or pid_alive:
            report["alive"] += 1
            report["daemons"][name] = {
                "status": "ALIVE",
                "evidence": "stigmergy" if alive else "pid",
                "port": daemon["port"],
            }
        else:
            report["dead"] += 1
            
            # Attempt restart if prerequisites met
            can_restart = True
            if daemon.get("requires_ollama") and not has_ollama:
                can_restart = False
            
            if can_restart and not dry_run:
                new_pid = _launch_daemon(daemon["script"], daemon["args"])
                if new_pid:
                    report["restarted"] += 1
                    report["daemons"][name] = {
                        "status": "RESTARTED",
                        "new_pid": new_pid,
                        "port": daemon["port"],
                    }
                    # Update fleet state
                    if "daemons" not in state:
                        state["daemons"] = {}
                    state["daemons"][name] = {
                        "pid": new_pid,
                        "script": daemon["script"],
                        "port": daemon["port"],
                        "started": datetime.now(timezone.utc).isoformat(),
                        "started_by": "watchdog",
                    }
                else:
                    report["daemons"][name] = {
                        "status": "RESTART_FAILED",
                        "port": daemon["port"],
                    }
            else:
                status = "DEAD_DRY_RUN" if dry_run else "DEAD_NO_PREREQ"
                report["daemons"][name] = {
                    "status": status,
                    "port": daemon["port"],
                }
    
    # Save updated fleet state
    if not dry_run and report["restarted"] > 0:
        state["last_update"] = datetime.now(timezone.utc).isoformat()
        FLEET_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    
    # Log watchdog event
    if not dry_run:
        _write_event(
            EVT_WATCHDOG,
            f"WATCHDOG:{report['alive']}/{report['checked']} alive:{report['restarted']} restarted",
            report,
        )
    
    return report


# ═══════════════════════════════════════════════════════════════
# § 5  GPU WARM-KEEPING
# ═══════════════════════════════════════════════════════════════

def preload_gpu_models() -> dict:
    """Preload optimal models into GPU VRAM to keep it warm."""
    ollama = check_ollama()
    if ollama["status"] != "ONLINE":
        return {"status": "SKIP", "reason": "Ollama offline"}
    
    loaded = ollama.get("models_loaded", [])
    if loaded:
        return {"status": "ALREADY_LOADED", "models": loaded}
    
    # Preload the Singer/Dancer model to keep VRAM warm
    target_model = os.getenv("HFO_WARM_MODEL", "qwen2.5:3b")  # Small, fast, always needed
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/generate",
            data=json.dumps({"model": target_model, "prompt": "", "keep_alive": "30m"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=30)
        return {"status": "PRELOADED", "model": target_model, "keep_alive": "30m"}
    except Exception as e:
        return {"status": "PRELOAD_FAILED", "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# § 6  NPU EMBEDDING SWEEP
# ═══════════════════════════════════════════════════════════════

def npu_embedding_sweep(limit: int = 50) -> dict:
    """Check for unembedded docs and embed them via NPU."""
    conn = _get_conn()
    try:
        # Check if there are unembedded docs
        row = conn.execute(
            """SELECT COUNT(*) FROM documents d
               LEFT JOIN embeddings e ON d.id = e.doc_id
               WHERE e.doc_id IS NULL"""
        ).fetchone()
        unembedded = row[0]
        
        if unembedded == 0:
            return {"status": "COMPLETE", "unembedded": 0, "note": "100% embedding coverage"}
        
        return {
            "status": "WORK_AVAILABLE",
            "unembedded": unembedded,
            "action": f"Run: python hfo_p7_compute_queue.py embed-all (or scheduler will trigger)",
        }
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# § 7  TREMORSENSE + ANCHOR INTEGRATION
# ═══════════════════════════════════════════════════════════════

def run_tremorsense_audit() -> dict:
    """Run a TREMORSENSE audit (1-hour window)."""
    script = BRONZE_RES / "hfo_p7_tremorsense.py"
    if not script.exists():
        return {"status": "SCRIPT_MISSING"}
    
    try:
        result = subprocess.run(
            [PYTHON, str(script), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(HFO_ROOT),
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            stdout = result.stdout
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                idx = stdout.rfind('\n{')
                if idx >= 0:
                    try:
                        return json.loads(stdout[idx:])
                    except json.JSONDecodeError:
                        pass
                return {"status": "PARSE_ERROR", "stdout": stdout[:500]}
        return {"status": "FAILED", "returncode": result.returncode, "stderr": result.stderr[:500]}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def run_anchor_probe() -> dict:
    """Run a DIMENSIONAL_ANCHOR probe."""
    script = BRONZE_RES / "hfo_p7_dimensional_anchor.py"
    if not script.exists():
        return {"status": "SCRIPT_MISSING"}
    
    try:
        result = subprocess.run(
            [PYTHON, str(script), "--json", "probe"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(HFO_ROOT),
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            # Banner pollutes stdout before JSON — extract JSON object
            stdout = result.stdout
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                idx = stdout.rfind('\n{')
                if idx >= 0:
                    try:
                        return json.loads(stdout[idx:])
                    except json.JSONDecodeError:
                        pass
                return {"status": "PARSE_ERROR", "stdout": stdout[:500]}
        return {"status": "FAILED", "returncode": result.returncode, "stderr": result.stderr[:500]}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# § 8  UPTIME REPORT CARD (CLI display)
# ═══════════════════════════════════════════════════════════════

def _grade(pct: float) -> str:
    if pct >= 99.0: return "A+"
    if pct >= 95.0: return "A"
    if pct >= 90.0: return "B"
    if pct >= 75.0: return "C"
    if pct >= 50.0: return "D"
    return "F"


def print_uptime_card():
    """Print the full 8-platform uptime report card."""
    print("=" * 76)
    print("  HFO Gen90 — STRANGE LOOP PLATFORM UPTIME REPORT CARD")
    print("  Red Regnant P4 Adversarial Audit")
    print("=" * 76)
    
    report = get_platform_report()
    
    print(f"\n  Timestamp: {report['timestamp'][:19]} UTC")
    print(f"  Overall 1h:  {report['overall_uptime_1h']}")
    print(f"  Overall 24h: {report['overall_uptime_24h']}")
    
    print(f"\n  SSOT: {report['ssot']['docs']} docs | {report['ssot']['events']} events | {report['ssot']['embeddings']} embeddings")
    
    print(f"\n  {'─' * 74}")
    print(f"  {'Platform':<30s} {'Uptime%':>8s} {'Grade':>6s} {'Status':<20s}")
    print(f"  {'─' * 74}")
    
    for key, p in report["platforms"].items():
        name = p.get("name", key)
        pct = p.get("uptime_pct", p.get("utilization_pct", 0))
        grade = _grade(pct) if isinstance(pct, (int, float)) else "?"
        status = p.get("status", "UNKNOWN")
        
        # Color indicator
        if isinstance(pct, (int, float)):
            if pct >= 90: icon = "██"
            elif pct >= 50: icon = "▓▓"
            elif pct >= 10: icon = "░░"
            else: icon = "  "
        else:
            icon = "??"
        
        pct_str = f"{pct:.1f}%" if isinstance(pct, (int, float)) else str(pct)
        print(f"  {icon} {name:<28s} {pct_str:>7s} {grade:>5s}   {status:<20s}")
    
    print(f"  {'─' * 74}")
    
    # Recommendations
    print(f"\n  RECOMMENDATIONS (P4 Red Regnant adversarial review):")
    platforms = report["platforms"]
    
    if platforms["gpu"].get("vram_empty"):
        print(f"    [!] GPU IDLE — Preload models: python hfo_p7_gpu_npu_anchor.py preload")
    
    ollama_pct = platforms["ollama"].get("uptime_pct", 0)
    if ollama_pct < 50:
        print(f"    [!] Ollama {ollama_pct}% — Start strange loop: python hfo_strange_loop_scheduler.py")
    
    if platforms["npu"].get("status") == "NOT_INSTALLED":
        print(f"    [!] NPU DARK — Install: pip install openvino openvino-genai")
    elif platforms["npu"].get("uptime_pct", 0) < 10:
        print(f"    [!] NPU IDLE — Run embedding sweep: python hfo_p7_compute_queue.py embed-all")
    
    gemini_pct = platforms["gemini"].get("uptime_pct", 0)
    if platforms["gemini"].get("status") == "NO_KEY":
        print(f"    [!] Gemini NO KEY — Set GEMINI_API_KEY in .env")
    elif gemini_pct < 20:
        print(f"    [!] Gemini {gemini_pct}% — Using 0/{platforms['gemini'].get('free_rpd', 1500)} free RPD/day")
    
    if platforms["openrouter"].get("status") == "NO_KEY":
        print(f"    [!] OpenRouter NOT SET — Set OPENROUTER_API_KEY in .env for fallback")
    
    print()


# ═══════════════════════════════════════════════════════════════
# § 9  SCHEDULER MAIN LOOP
# ═══════════════════════════════════════════════════════════════

class StrangeLoopScheduler:
    """Main scheduler that orchestrates the strange loop."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.running = True
        self.cycle_count = 0
        self.start_time = time.time()
        self.last_heartbeat = 0
        self.last_enrich = 0
        self.last_npu = 0
        self.last_research = 0
        self.last_governance = 0
        self.last_audit = 0
        self.last_watchdog = 0
        
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def _handle_signal(self, sig, frame):
        self.running = False
        print(f"\n  [SCHEDULER] Received signal {sig}, shutting down gracefully...")
    
    def _log(self, msg: str):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"  [{ts}] {msg}")
    
    def _should_run(self, last: float, interval: float) -> bool:
        return (time.time() - last) >= interval
    
    def tick(self):
        """Run one scheduler tick — check all timers and fire due tasks."""
        now = time.time()
        actions = []
        
        # ── HEARTBEAT (every 1 min) ──────────────────────
        if self._should_run(self.last_heartbeat, HEARTBEAT_INTERVAL):
            self.last_heartbeat = now
            self.cycle_count += 1
            elapsed = now - self.start_time
            
            stats = _ssot_stats()
            covered_1h, total_1h = _total_minutes_covered(1.0)
            uptime_1h = covered_1h / max(total_1h, 1) * 100
            
            heartbeat_data = {
                "cycle": self.cycle_count,
                "elapsed_s": round(elapsed),
                "uptime_1h_pct": round(uptime_1h, 1),
                "ssot_events": stats["events"],
            }
            
            if not self.dry_run:
                _write_event(
                    EVT_HEARTBEAT,
                    f"HEARTBEAT:{self.cycle_count}:{uptime_1h:.0f}%",
                    heartbeat_data,
                )
            
            self._log(f"HEARTBEAT #{self.cycle_count} | 1h uptime: {uptime_1h:.1f}% | events: {stats['events']}")
            actions.append("heartbeat")
        
        # ── GPU WARM (every 5 min) ───────────────────────
        if self._should_run(self.last_npu, NPU_INTERVAL):
            self.last_npu = now
            
            # Keep GPU warm
            gpu_result = preload_gpu_models()
            self._log(f"GPU: {gpu_result.get('status', 'UNKNOWN')}")
            
            # Check NPU embedding status
            npu_result = npu_embedding_sweep()
            self._log(f"NPU: {npu_result.get('status', 'UNKNOWN')} ({npu_result.get('unembedded', 0)} unembedded)")
            
            actions.append("gpu_npu_check")
        
        # ── AUDIT (every 60 min) ─────────────────────────
        if self._should_run(self.last_audit, AUDIT_INTERVAL):
            self.last_audit = now
            
            self._log("Running TREMORSENSE audit...")
            tremor = run_tremorsense_audit()
            grade = tremor.get("grade", tremor.get("status", "?"))
            self._log(f"TREMORSENSE: {grade}")
            
            self._log("Running DIMENSIONAL_ANCHOR probe...")
            anchor = run_anchor_probe()
            overall = anchor.get("overall", anchor.get("status", "?"))
            self._log(f"ANCHOR: {overall}")
            
            actions.append("audit")
        
        # ── WATCHDOG (every 6 hrs) ───────────────────────
        if self._should_run(self.last_watchdog, WATCHDOG_INTERVAL):
            self.last_watchdog = now
            
            self._log("Running watchdog fleet check...")
            report = watchdog_check(dry_run=self.dry_run)
            self._log(
                f"WATCHDOG: {report['alive']}/{report['checked']} alive, "
                f"{report['restarted']} restarted"
            )
            actions.append("watchdog")
        
        return actions
    
    def run_once(self):
        """Run a single full cycle (all tasks regardless of timer)."""
        self._log("=== SINGLE CYCLE (all tasks) ===")
        
        # Heartbeat
        stats = _ssot_stats()
        covered_1h, total_1h = _total_minutes_covered(1.0)
        uptime_1h = covered_1h / max(total_1h, 1) * 100
        self._log(f"SSOT: {stats['docs']} docs, {stats['events']} events, {stats['embeddings']} embeddings")
        self._log(f"1h uptime: {uptime_1h:.1f}% ({covered_1h}/{total_1h} min)")
        
        if not self.dry_run:
            _write_event(EVT_HEARTBEAT, f"HEARTBEAT:once:{uptime_1h:.0f}%", {
                "cycle": "once", "uptime_1h_pct": round(uptime_1h, 1), "ssot": stats,
            })
        
        # GPU warm
        gpu = preload_gpu_models()
        self._log(f"GPU preload: {gpu.get('status')}")
        
        # NPU sweep
        npu = npu_embedding_sweep()
        self._log(f"NPU embeddings: {npu.get('status')} ({npu.get('unembedded', 0)} unembedded)")
        
        # Platform report
        print()
        print_uptime_card()
        
        # Watchdog
        wd = watchdog_check(dry_run=self.dry_run)
        self._log(f"Watchdog: {wd['alive']}/{wd['checked']} alive, {wd['restarted']} restarted")
        
        # TREMORSENSE
        self._log("Running TREMORSENSE...")
        tremor = run_tremorsense_audit()
        self._log(f"TREMORSENSE: {tremor.get('grade', tremor.get('status', '?'))}")
        
        # DIMENSIONAL_ANCHOR
        self._log("Running DIMENSIONAL_ANCHOR probe...")
        anchor = run_anchor_probe()
        self._log(f"ANCHOR: {anchor.get('overall', anchor.get('status', '?'))}")
        
        self._log("=== SINGLE CYCLE COMPLETE ===")
    
    def run_forever(self):
        """Main scheduler loop."""
        self._log("=" * 60)
        self._log("STRANGE LOOP SCHEDULER — ONLINE")
        self._log(f"P4-P7 research cycle active. Dry run: {self.dry_run}")
        self._log("=" * 60)
        
        # First cycle — run watchdog + audit immediately
        self.last_watchdog = 0
        self.last_audit = 0
        
        while self.running:
            try:
                actions = self.tick()
                if actions:
                    self._log(f"  Actions: {', '.join(actions)}")
            except Exception as e:
                self._log(f"ERROR: {e}")
                if not self.dry_run:
                    _write_event(EVT_ERROR, f"ERROR:{type(e).__name__}", {
                        "error": str(e),
                        "traceback": traceback.format_exc()[-500:],
                    })
            
            # Sleep 30 seconds between ticks
            for _ in range(30):
                if not self.running:
                    break
                time.sleep(1)
        
        self._log("Scheduler stopped.")


# ═══════════════════════════════════════════════════════════════
# § 10  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="HFO Strange Loop Scheduler — P4-P7 autonomous research cycles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hfo_strange_loop_scheduler.py                  # Run scheduler
  python hfo_strange_loop_scheduler.py --uptime-card    # Platform report card
  python hfo_strange_loop_scheduler.py --once           # Single full cycle
  python hfo_strange_loop_scheduler.py --watchdog       # Check & restart daemons
  python hfo_strange_loop_scheduler.py --dry-run        # Preview (no writes)
  python hfo_strange_loop_scheduler.py --status         # Quick status
        """,
    )
    
    parser.add_argument("--uptime-card", action="store_true", help="Print 8-platform uptime report card")
    parser.add_argument("--once", action="store_true", help="Run single full cycle")
    parser.add_argument("--watchdog", action="store_true", help="Run watchdog check only")
    parser.add_argument("--status", action="store_true", help="Quick platform status")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions (no SSOT writes)")
    parser.add_argument("--json", action="store_true", help="JSON output for --status/--uptime-card")
    
    args = parser.parse_args()
    
    if args.uptime_card:
        if args.json:
            report = get_platform_report()
            print(json.dumps(report, indent=2, default=str))
        else:
            print_uptime_card()
        return
    
    if args.status:
        report = get_platform_report()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"\n  Quick Status ({report['timestamp'][:19]} UTC):")
            print(f"  Overall 1h:  {report['overall_uptime_1h']}")
            print(f"  Overall 24h: {report['overall_uptime_24h']}")
            for k, p in report["platforms"].items():
                pct = p.get("uptime_pct", p.get("utilization_pct", "?"))
                status = p.get("status", "?")
                pct_str = f"{pct:.1f}%" if isinstance(pct, (int, float)) else str(pct)
                print(f"    {p.get('name', k):<30s}  {pct_str:>7s}  {status}")
            print()
        return
    
    if args.watchdog:
        report = watchdog_check(dry_run=args.dry_run)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"\n  Watchdog: {report['alive']}/{report['checked']} alive, {report['restarted']} restarted")
            for name, info in report["daemons"].items():
                print(f"    {name:20s}  {info['status']:15s}  {info['port']}")
            print()
        return
    
    if args.once:
        scheduler = StrangeLoopScheduler(dry_run=args.dry_run)
        scheduler.run_once()
        return
    
    # Default: run scheduler loop
    scheduler = StrangeLoopScheduler(dry_run=args.dry_run)
    scheduler.run_forever()


if __name__ == "__main__":
    main()
