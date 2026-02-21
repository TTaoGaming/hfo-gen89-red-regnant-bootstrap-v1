#!/usr/bin/env python3
"""
hfo_p7_dimensional_anchor.py — P7 Spider Sovereign DIMENSIONAL_ANCHOR Spell (Gen90)
=====================================================================================
v1.0 | Gen90 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | Spell: DIMENSIONAL_ANCHOR (Abjuration 4th)
Title: Summoner of Seals and Spheres | Epic Class: Cosmic Descryer (ELH p.19)
                                       + Thaumaturgist (DMG p.184)
Aspect: A — SEALS (binding authority, C2 governance, correct-by-construction)

PURPOSE:
    Session pinning, anti-drift, context stability enforcement.
    Captures a baseline system snapshot (the "anchor"), then detects ANY drift
    from that baseline: config changes, daemon deaths, model swaps, SSOT
    mutations, file modifications, hardware resource shifts.

    "Nothing shifts between planes while the anchor holds."

    In a system with 71 AI models, 8+ daemons, and ~9M words of context,
    drift is the default state. DIMENSIONAL_ANCHOR creates a fixed reference
    point and alarms on any deviation — the anti-hallucination spell.

    v2.0 adds LIVE HARDWARE PROBES for the finicky bits:
      - RAM:    psutil memory — percent used, free GB, swap pressure
      - GPU:    Ollama VRAM usage, loaded model details, nvidia-smi where available
      - NPU:    Intel AI Boost / OpenVINO availability + embedder process status
      - GEMINI: Vertex AI / AI Studio reachability, mode, rate limit headroom

D&D 3.5e RAW (PHB p.223):
    Dimensional Anchor — Abjuration 4th — bars extradimensional movement.
    A green ray prevents target from using teleport, plane shift, blink, etc.
    Duration: 1 min/level. No save (but requires ranged touch attack).

SBE/ATDD SCENARIOS (Specification by Example):
═══════════════════════════════════════════════

  TIER 1 — INVARIANT (fail-closed safety):
    Scenario: Anchor requires baseline capture first
      Given no baseline snapshot exists
      When  DIMENSIONAL_ANCHOR check is cast
      Then  NO_ANCHOR error is returned (cannot detect drift without baseline)

  TIER 2 — HAPPY PATH:
    Scenario: Anchor set
      Given the system is in a known-good state
      When  DIMENSIONAL_ANCHOR anchor is cast
      Then  a baseline snapshot is captured (config, daemons, SSOT stats, file hashes)
      And   the anchor is persisted to state file + SSOT CloudEvent

    Scenario: No drift detected
      Given an active anchor exists
      When  DIMENSIONAL_ANCHOR check is cast
      Then  current state matches baseline on all dimensions
      And   ANCHORED verdict is returned

    Scenario: Drift detected
      Given an active anchor exists
      When  a daemon dies or config changes after anchoring
      Then  DIMENSIONAL_ANCHOR check detects the delta
      And   DRIFT_DETECTED verdict is returned with specific deltas
      And   a drift CloudEvent is written to SSOT

  TIER 3 — DIMENSIONS OF DRIFT (10 total):
    - daemon_fleet:   PID alive/dead, new/removed daemons
    - config:         .env values changed
    - ssot_stats:     document count, event count, FTS status
    - file_hashes:    key governance files (AGENTS.md, pointers, .env.example)
    - ollama_models:  Ollama loaded models changed
    - ram:            memory usage %, free GB, swap activity
    - gpu:            VRAM used/free, loaded model VRAM breakdown
    - npu:            OpenVINO runtime available, embedder process alive
    - gemini:         API reachable, mode (vertex/aistudio), credentials valid
    - system:         CPU %, disk free on forge drive, process count

  TIER 3b — PROBE (no anchor needed, immediate health report):
    Scenario: Operator wants live system health
      Given  no prior anchor is required
      When   DIMENSIONAL_ANCHOR probe is cast
      Then   live snapshot of RAM/GPU/NPU/Gemini/Ollama returned with verdicts

  TIER 4 — ADVERSARIAL:
    Scenario: Anchor tampering
      Given an active anchor exists
      When  the anchor state file is modified externally
      Then  anchor_hash validation fails
      And   ANCHOR_TAMPERED error is raised

Event Types:
    hfo.gen90.p7.dimensional_anchor.set        — Baseline captured
    hfo.gen90.p7.dimensional_anchor.check      — Drift check performed
    hfo.gen90.p7.dimensional_anchor.drift      — Drift detected
    hfo.gen90.p7.dimensional_anchor.release     — Anchor removed
    hfo.gen90.p7.dimensional_anchor.tampered   — Anchor state file tampered
    hfo.gen90.p7.dimensional_anchor.probe      — Live hardware health probe

USAGE:
    python hfo_p7_dimensional_anchor.py probe           # Live hardware health
    python hfo_p7_dimensional_anchor.py anchor          # Capture baseline
    python hfo_p7_dimensional_anchor.py check           # Check for drift
    python hfo_p7_dimensional_anchor.py status          # Show anchor state
    python hfo_p7_dimensional_anchor.py release         # Remove anchor
    python hfo_p7_dimensional_anchor.py --json probe    # Machine-readable

Pointer key: p7.dimensional_anchor
Medallion: bronze
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from hfo_ssot_write import get_db_readwrite as get_db_rw

# Force UTF-8 stdout on Windows (box-drawing characters in probes)
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION (PAL)
# ═══════════════════════════════════════════════════════════════

_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))

# Load .env for credentials (Gemini, Vertex, etc.)
try:
    from dotenv import load_dotenv
    load_dotenv(HFO_ROOT / ".env")
except ImportError:
    pass  # dotenv not installed — rely on system env vars

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
    SSOT_DB = None  # PAL-only — no hardcoded fallback (TRUE_SEEING upgrade)

GEN = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG = f"hfo_p7_dimensional_anchor_gen{GEN}"

# Forge root via PAL — no hardcoded path
try:
    FORGE_ROOT = _resolve_pointer("forge.root")
except (KeyError, FileNotFoundError):
    FORGE_ROOT = None  # PAL-only — no hardcoded fallback

# Anchor state file
ANCHOR_STATE_FILE = HFO_ROOT / ".p7_dimensional_anchor_state.json"

# Governance files — dynamically discovered from PAL pointer registry
# Replaces the static GOVERNANCE_FILES list (TRUE_SEEING upgrade)
_GOVERNANCE_POINTER_KEYS = [
    "root.agents_md",
    "root.pointers_blessed",
    "root.env_example",
    "root.gitignore",
]

def _discover_governance_files() -> list[str]:
    """Dynamically discover governance files from PAL pointer registry.
    No static lists. If a new governance file is added to PAL, it's
    automatically included in drift detection."""
    governance = []
    for key in _GOVERNANCE_POINTER_KEYS:
        try:
            path = _resolve_pointer(key)
            if path.exists():
                governance.append(str(path.relative_to(HFO_ROOT)))
        except (KeyError, FileNotFoundError):
            pass
    # Also discover any root-level governance files not in PAL
    for child in HFO_ROOT.iterdir():
        if child.is_file():
            rel = str(child.relative_to(HFO_ROOT))
            if rel not in governance and child.suffix in {".md", ".json", ".example"}:
                governance.append(rel)
    return sorted(set(governance))

GOVERNANCE_FILES = _discover_governance_files()

# Ollama
OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

# RAM thresholds
RAM_CRITICAL_PCT = 90.0   # Above this = CRITICAL
RAM_WARNING_PCT  = 80.0   # Above this = WARNING
RAM_FREE_CRITICAL_GB = 2.0  # Below this = CRITICAL


# ═══════════════════════════════════════════════════════════════
# § 1  DATABASE & CLOUDEVENT HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": SOURCE_TAG,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    content_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, SOURCE_TAG, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 2  BASELINE SNAPSHOT CAPTURE
# ═══════════════════════════════════════════════════════════════

def _hash_file(path: Path) -> str:
    """SHA256 hash of a file, or 'MISSING' if not found."""
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_daemon_fleet() -> dict[str, Any]:
    """Capture current daemon fleet state from spell_gate."""
    try:
        from hfo_p7_spell_gate import spell_scrying
        fleet = spell_scrying()
        if "fleet" in fleet:
            return {dk: {"status": info.get("status"), "pid": info.get("pid")}
                    for dk, info in fleet["fleet"].items()}
    except ImportError:
        pass
    return {}


def _capture_ssot_stats() -> dict[str, Any]:
    """Capture SSOT document + event counts."""
    stats = {"doc_count": 0, "event_count": 0, "fts_ok": False}
    if not SSOT_DB.exists():
        return stats
    try:
        conn = get_db_ro()
        row = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        stats["doc_count"] = row["cnt"] if row else 0
        row = conn.execute("SELECT COUNT(*) as cnt FROM stigmergy_events").fetchone()
        stats["event_count"] = row["cnt"] if row else 0
        try:
            conn.execute("SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'test' LIMIT 1")
            stats["fts_ok"] = True
        except Exception:
            stats["fts_ok"] = False
        conn.close()
    except Exception:
        pass
    return stats


def _capture_ollama_models() -> list[str]:
    """Get list of currently loaded Ollama models."""
    if not HAS_HTTPX:
        return []
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return sorted([m["name"] for m in data.get("models", [])])
    except Exception:
        pass
    return []


def _capture_env_hash() -> str:
    """Hash of .env file (or MISSING)."""
    return _hash_file(HFO_ROOT / ".env")


# ═══════════════════════════════════════════════════════════════
# § 2b  LIVE HARDWARE PROBES
# ═══════════════════════════════════════════════════════════════

def _probe_ram() -> dict[str, Any]:
    """
    RAM probe — psutil memory stats + swap.

    SBE:
      Given  psutil is available
      When   RAM is probed
      Then   total/used/free/percent returned with verdict
    """
    result: dict[str, Any] = {
        "available": False, "verdict": "UNKNOWN",
        "total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0,
        "swap_total_gb": 0, "swap_used_gb": 0, "swap_percent": 0,
    }
    if not HAS_PSUTIL:
        result["error"] = "psutil not installed (pip install psutil)"
        return result

    try:
        vm = psutil.virtual_memory()
        result["available"] = True
        result["total_gb"] = round(vm.total / (1024**3), 1)
        result["used_gb"]  = round(vm.used / (1024**3), 1)
        result["free_gb"]  = round(vm.available / (1024**3), 1)
        result["percent"]  = vm.percent

        sw = psutil.swap_memory()
        result["swap_total_gb"]  = round(sw.total / (1024**3), 1)
        result["swap_used_gb"]   = round(sw.used / (1024**3), 1)
        result["swap_percent"]   = sw.percent

        # Verdict
        if vm.percent >= RAM_CRITICAL_PCT or vm.available / (1024**3) < RAM_FREE_CRITICAL_GB:
            result["verdict"] = "CRITICAL"
        elif vm.percent >= RAM_WARNING_PCT:
            result["verdict"] = "WARNING"
        else:
            result["verdict"] = "OK"
    except Exception as e:
        result["error"] = str(e)
    return result


def _probe_gpu() -> dict[str, Any]:
    """
    GPU probe — Ollama /api/ps for VRAM + nvidia-smi if available.

    SBE:
      Given  Ollama is running (or nvidia-smi exists)
      When   GPU is probed
      Then   VRAM used/free, loaded models, driver info returned
    """
    result: dict[str, Any] = {
        "available": False, "verdict": "UNKNOWN",
        "vram_used_gb": 0, "vram_free_gb": 0,
        "loaded_models": [], "nvidia_smi": None,
        "ollama_alive": False,
    }

    # 1. Ollama /api/ps — live VRAM per model
    if HAS_HTTPX:
        try:
            resp = httpx.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
            if resp.status_code == 200:
                result["ollama_alive"] = True
                models = resp.json().get("models", [])
                total_vram = 0
                for m in models:
                    name = m.get("name", "?")
                    size_vram = m.get("size_vram", 0)
                    vram_gb = round(size_vram / (1024**3), 2)
                    total_vram += vram_gb
                    result["loaded_models"].append({
                        "name": name,
                        "vram_gb": vram_gb,
                        "expires": m.get("expires_at", ""),
                    })
                result["vram_used_gb"] = round(total_vram, 2)
                result["available"] = True
        except Exception:
            pass

    # 2. nvidia-smi — driver info + total VRAM
    try:
        nvsmi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if nvsmi.returncode == 0 and nvsmi.stdout.strip():
            parts = [p.strip() for p in nvsmi.stdout.strip().split(",")]
            if len(parts) >= 6:
                total_mb = float(parts[1])
                used_mb = float(parts[2])
                free_mb = float(parts[3])
                result["nvidia_smi"] = {
                    "gpu_name": parts[0],
                    "vram_total_gb": round(total_mb / 1024, 1),
                    "vram_used_gb": round(used_mb / 1024, 1),
                    "vram_free_gb": round(free_mb / 1024, 1),
                    "temperature_c": int(float(parts[4])) if parts[4].strip() else None,
                    "driver": parts[5],
                }
                result["vram_free_gb"] = round(free_mb / 1024, 1)
                result["available"] = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Verdict
    if not result["available"]:
        result["verdict"] = "NO_GPU"
    elif result.get("nvidia_smi") and result["nvidia_smi"].get("vram_free_gb", 99) < 1.0:
        result["verdict"] = "CRITICAL"
    elif result.get("nvidia_smi") and result["nvidia_smi"].get("temperature_c") and result["nvidia_smi"]["temperature_c"] > 85:
        result["verdict"] = "HOT"
    elif result["vram_used_gb"] > 10:
        result["verdict"] = "WARNING"
    else:
        result["verdict"] = "OK"
    return result


def _probe_npu() -> dict[str, Any]:
    """
    NPU probe — Intel AI Boost / OpenVINO availability.

    SBE:
      Given  the system may have Intel NPU hardware
      When   NPU is probed
      Then   OpenVINO availability, device list, embedder process status returned
    """
    result: dict[str, Any] = {
        "available": False, "verdict": "UNKNOWN",
        "openvino_installed": False, "openvino_version": None,
        "devices": [], "embedder_running": False,
    }

    # 1. OpenVINO runtime check
    try:
        import openvino as ov
        result["openvino_installed"] = True
        result["openvino_version"] = ov.__version__ if hasattr(ov, "__version__") else "?"

        core = ov.Core()
        devices = core.available_devices
        result["devices"] = list(devices)
        result["available"] = "NPU" in devices
    except ImportError:
        result["error"] = "openvino not installed"
    except Exception as e:
        result["error"] = f"OpenVINO probe failed: {e}"

    # 2. Check if embedder process is running (hfo_npu_embedder.py)
    if HAS_PSUTIL:
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                cmdline = proc.info.get("cmdline") or []
                if any("hfo_npu_embedder" in str(c) for c in cmdline):
                    result["embedder_running"] = True
                    result["embedder_pid"] = proc.info["pid"]
                    break
        except Exception:
            pass

    # Verdict
    if not result["openvino_installed"]:
        result["verdict"] = "NO_OPENVINO"
    elif not result["available"]:
        result["verdict"] = "NO_NPU_DEVICE"
    elif result["embedder_running"]:
        result["verdict"] = "ACTIVE"
    else:
        result["verdict"] = "IDLE"
    return result


def _probe_gemini() -> dict[str, Any]:
    """
    Gemini probe — API reachability, mode, credential validity.

    SBE:
      Given  Gemini may be configured via Vertex AI or AI Studio
      When   Gemini is probed
      Then   mode, reachability, and a lightweight model list call returned
    """
    result: dict[str, Any] = {
        "available": False, "verdict": "UNKNOWN",
        "mode": None, "project": None, "reachable": False,
        "error": None, "latency_ms": None,
    }

    # Check env config
    vertex_project = os.getenv("HFO_VERTEX_PROJECT", "")
    api_key = os.getenv("GEMINI_API_KEY", "")

    if vertex_project:
        result["mode"] = "vertex"
        result["project"] = vertex_project
    elif api_key:
        result["mode"] = "aistudio"
    else:
        result["verdict"] = "NO_CREDENTIALS"
        result["error"] = "Neither HFO_VERTEX_PROJECT nor GEMINI_API_KEY set"
        return result

    # Try to create client and list models (lightweight ping)
    try:
        import logging
        _prev_level = logging.getLogger().level
        logging.getLogger().setLevel(logging.ERROR)  # suppress SDK warnings
        from google import genai
        t0 = time.time()

        if result["mode"] == "vertex":
            client = genai.Client(
                vertexai=True,
                project=vertex_project,
                location=os.getenv("HFO_VERTEX_LOCATION", "us-central1"),
            )
        else:
            client = genai.Client(api_key=api_key)

        # Lightweight ping: list models with a limit
        models_iter = client.models.list(config={"page_size": 1})
        first_model = None
        for m in models_iter:
            first_model = m.name if hasattr(m, "name") else str(m)
            break
        latency = round((time.time() - t0) * 1000)

        result["reachable"] = True
        result["available"] = True
        result["latency_ms"] = latency
        result["sample_model"] = first_model

        # Verdict based on latency
        if latency > 5000:
            result["verdict"] = "SLOW"
        elif latency > 2000:
            result["verdict"] = "WARNING"
        else:
            result["verdict"] = "OK"

    except ImportError:
        result["error"] = "google-genai not installed"
        result["verdict"] = "NO_SDK"
    except Exception as e:
        err_str = str(e)
        result["error"] = err_str[:200]
        # Categorize common Gemini failures
        if "401" in err_str or "403" in err_str or "Unauthorized" in err_str:
            result["verdict"] = "AUTH_FAILED"
        elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            result["verdict"] = "RATE_LIMITED"
        elif "timeout" in err_str.lower() or "connect" in err_str.lower():
            result["verdict"] = "UNREACHABLE"
        else:
            result["verdict"] = "ERROR"
    finally:
        try:
            logging.getLogger().setLevel(_prev_level)
        except Exception:
            pass
    return result


def _probe_system() -> dict[str, Any]:
    """
    System probe — CPU, disk, process count.

    SBE:
      Given  psutil is available
      When   system is probed
      Then   CPU%, disk free on forge drive, process count returned
    """
    result: dict[str, Any] = {
        "cpu_percent": 0, "cpu_cores": 0,
        "disk_free_gb": 0, "disk_total_gb": 0, "disk_percent": 0,
        "process_count": 0, "platform": platform.platform(),
    }
    if HAS_PSUTIL:
        try:
            result["cpu_percent"] = psutil.cpu_percent(interval=0.5)
            result["cpu_cores"] = psutil.cpu_count()
            result["process_count"] = len(psutil.pids())
        except Exception:
            pass

    # Disk where forge lives
    try:
        disk_path = str(FORGE_ROOT) if FORGE_ROOT else str(HFO_ROOT)
        disk = shutil.disk_usage(disk_path)
        result["disk_total_gb"] = round(disk.total / (1024**3), 1)
        result["disk_free_gb"] = round(disk.free / (1024**3), 1)
        result["disk_percent"] = round(100 * disk.used / disk.total, 1)
    except Exception:
        pass

    return result


def capture_baseline() -> dict[str, Any]:
    """Capture complete system baseline snapshot."""
    now = datetime.now(timezone.utc).isoformat()

    # File hashes
    file_hashes = {}
    for fname in GOVERNANCE_FILES:
        fpath = HFO_ROOT / fname
        file_hashes[fname] = _hash_file(fpath)

    # SSOT DB file hash (size-based, not content — too slow for 149MB)
    ssot_size = SSOT_DB.stat().st_size if (SSOT_DB and SSOT_DB.exists()) else 0

    baseline = {
        "captured_at": now,
        "daemon_fleet": _capture_daemon_fleet(),
        "ssot_stats": _capture_ssot_stats(),
        "file_hashes": file_hashes,
        "env_hash": _capture_env_hash(),
        "ollama_models": _capture_ollama_models(),
        "ssot_db_size": ssot_size,
        "ram": _probe_ram(),
        "gpu": _probe_gpu(),
        "npu": _probe_npu(),
        "gemini": _probe_gemini(),
        "system": _probe_system(),
    }

    # Compute anchor hash (integrity seal)
    baseline["anchor_hash"] = hashlib.sha256(
        json.dumps(baseline, sort_keys=True).encode()
    ).hexdigest()

    return baseline


# ═══════════════════════════════════════════════════════════════
# § 3  DRIFT DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_drift(baseline: dict, current: dict) -> dict[str, list[str]]:
    """Compare baseline to current state, return drift by dimension."""
    drifts: dict[str, list[str]] = {}

    # Daemon fleet drift
    fleet_drifts = []
    base_fleet = baseline.get("daemon_fleet", {})
    curr_fleet = current.get("daemon_fleet", {})
    for dk in set(list(base_fleet.keys()) + list(curr_fleet.keys())):
        b = base_fleet.get(dk, {})
        c = curr_fleet.get(dk, {})
        if dk not in base_fleet:
            fleet_drifts.append(f"NEW daemon appeared: {dk}")
        elif dk not in curr_fleet:
            fleet_drifts.append(f"MISSING daemon: {dk}")
        elif b.get("status") != c.get("status"):
            fleet_drifts.append(
                f"{dk}: {b.get('status')} → {c.get('status')} (PID {b.get('pid')} → {c.get('pid')})"
            )
    if fleet_drifts:
        drifts["daemon_fleet"] = fleet_drifts

    # SSOT stats drift
    ssot_drifts = []
    base_ssot = baseline.get("ssot_stats", {})
    curr_ssot = current.get("ssot_stats", {})
    for key in ["doc_count", "event_count"]:
        bv = base_ssot.get(key, 0)
        cv = curr_ssot.get(key, 0)
        if bv != cv:
            ssot_drifts.append(f"{key}: {bv} → {cv} (delta: {cv - bv:+d})")
    if base_ssot.get("fts_ok") and not curr_ssot.get("fts_ok"):
        ssot_drifts.append("FTS5 was working, now broken")
    if ssot_drifts:
        drifts["ssot_stats"] = ssot_drifts

    # File hash drift
    file_drifts = []
    base_files = baseline.get("file_hashes", {})
    curr_files = current.get("file_hashes", {})
    for fname in set(list(base_files.keys()) + list(curr_files.keys())):
        bh = base_files.get(fname, "MISSING")
        ch = curr_files.get(fname, "MISSING")
        if bh != ch:
            file_drifts.append(f"{fname}: hash changed ({bh[:12]}... → {ch[:12]}...)")
    if file_drifts:
        drifts["file_hashes"] = file_drifts

    # Env drift
    if baseline.get("env_hash") != current.get("env_hash"):
        drifts["config"] = [
            f".env changed: {baseline.get('env_hash', '?')[:12]}... → {current.get('env_hash', '?')[:12]}..."
        ]

    # Model drift
    base_models = set(baseline.get("ollama_models", []))
    curr_models = set(current.get("ollama_models", []))
    model_drifts = []
    for m in curr_models - base_models:
        model_drifts.append(f"NEW model loaded: {m}")
    for m in base_models - curr_models:
        model_drifts.append(f"REMOVED model: {m}")
    if model_drifts:
        drifts["ollama_models"] = model_drifts

    # RAM drift (verdict change or large % swing)
    ram_drifts = []
    base_ram = baseline.get("ram", {})
    curr_ram = current.get("ram", {})
    if base_ram.get("verdict") != curr_ram.get("verdict"):
        ram_drifts.append(f"RAM verdict: {base_ram.get('verdict')} → {curr_ram.get('verdict')}")
    ram_delta = abs((curr_ram.get("percent", 0)) - (base_ram.get("percent", 0)))
    if ram_delta > 10:
        ram_drifts.append(
            f"RAM usage: {base_ram.get('percent', 0):.0f}% → {curr_ram.get('percent', 0):.0f}% "
            f"(Δ{ram_delta:+.0f}%)"
        )
    if ram_drifts:
        drifts["ram"] = ram_drifts

    # GPU drift (VRAM swing, model changes, temperature)
    gpu_drifts = []
    base_gpu = baseline.get("gpu", {})
    curr_gpu = current.get("gpu", {})
    if base_gpu.get("verdict") != curr_gpu.get("verdict"):
        gpu_drifts.append(f"GPU verdict: {base_gpu.get('verdict')} → {curr_gpu.get('verdict')}")
    vram_delta = abs((curr_gpu.get("vram_used_gb", 0)) - (base_gpu.get("vram_used_gb", 0)))
    if vram_delta > 1.0:
        gpu_drifts.append(
            f"VRAM used: {base_gpu.get('vram_used_gb', 0):.1f} GB → "
            f"{curr_gpu.get('vram_used_gb', 0):.1f} GB (Δ{vram_delta:+.1f} GB)"
        )
    if gpu_drifts:
        drifts["gpu"] = gpu_drifts

    # NPU drift (availability or embedder status change)
    npu_drifts = []
    base_npu = baseline.get("npu", {})
    curr_npu = current.get("npu", {})
    if base_npu.get("verdict") != curr_npu.get("verdict"):
        npu_drifts.append(f"NPU verdict: {base_npu.get('verdict')} → {curr_npu.get('verdict')}")
    if base_npu.get("embedder_running") != curr_npu.get("embedder_running"):
        npu_drifts.append(
            f"Embedder: {'running' if base_npu.get('embedder_running') else 'stopped'} → "
            f"{'running' if curr_npu.get('embedder_running') else 'stopped'}"
        )
    if npu_drifts:
        drifts["npu"] = npu_drifts

    # Gemini drift (reachability or mode change)
    gemini_drifts = []
    base_gem = baseline.get("gemini", {})
    curr_gem = current.get("gemini", {})
    if base_gem.get("verdict") != curr_gem.get("verdict"):
        gemini_drifts.append(f"Gemini verdict: {base_gem.get('verdict')} → {curr_gem.get('verdict')}")
    if base_gem.get("reachable") and not curr_gem.get("reachable"):
        gemini_drifts.append("Gemini was reachable, now UNREACHABLE")
    if base_gem.get("mode") != curr_gem.get("mode"):
        gemini_drifts.append(f"Gemini mode: {base_gem.get('mode')} → {curr_gem.get('mode')}")
    if gemini_drifts:
        drifts["gemini"] = gemini_drifts

    return drifts


# ═══════════════════════════════════════════════════════════════
# § 4  SPELL: ANCHOR — Capture baseline
# ═══════════════════════════════════════════════════════════════

def spell_anchor(quiet: bool = False) -> dict[str, Any]:
    """
    DIMENSIONAL_ANCHOR SET — Capture system baseline.

    SBE Contract:
      Given  the system is running
      When   spell_anchor is cast
      Then   complete baseline captured (fleet, SSOT, files, models, config)
      And    baseline persisted to state file + SSOT CloudEvent
    """
    _print = (lambda *a, **k: None) if quiet else print
    _print("  [ANCHOR] Capturing baseline snapshot...")

    baseline = capture_baseline()

    # Persist to state file
    state = {
        "baseline": baseline,
        "active": True,
        "set_at": baseline["captured_at"],
        "check_count": 0,
        "drift_count": 0,
    }
    ANCHOR_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Write SSOT event
    try:
        conn = get_db_rw()
        row_id = write_event(conn, f"hfo.gen{GEN}.p7.dimensional_anchor.set",
                             f"ANCHOR_SET:{baseline['anchor_hash'][:16]}",
                             {"baseline_summary": {
                                 "daemon_count": len(baseline.get("daemon_fleet", {})),
                                 "doc_count": baseline["ssot_stats"].get("doc_count"),
                                 "event_count": baseline["ssot_stats"].get("event_count"),
                                 "file_count": len(baseline.get("file_hashes", {})),
                                 "model_count": len(baseline.get("ollama_models", [])),
                                 "anchor_hash": baseline["anchor_hash"],
                              },
                              "core_thesis": "Nothing shifts between planes while the anchor holds."})
        conn.close()
    except Exception as e:
        _print(f"  [WARN] SSOT write failed: {e}")
        row_id = 0

    _print(f"  [ANCHORED] Baseline captured at {baseline['captured_at'][:19]}")
    _print(f"  Anchor hash: {baseline['anchor_hash'][:16]}...")
    _print(f"  Daemons: {len(baseline.get('daemon_fleet', {}))}")
    _print(f"  SSOT docs: {baseline['ssot_stats'].get('doc_count', 0)}")
    _print(f"  SSOT events: {baseline['ssot_stats'].get('event_count', 0)}")
    _print(f"  Governance files: {len(baseline.get('file_hashes', {}))}")
    _print(f"  Ollama models: {len(baseline.get('ollama_models', []))}")
    ram = baseline.get("ram", {})
    _print(f"  RAM: {ram.get('percent', '?')}% used ({ram.get('free_gb', '?')} GB free) [{ram.get('verdict', '?')}]")
    gpu = baseline.get("gpu", {})
    _print(f"  GPU: {gpu.get('vram_used_gb', '?')} GB VRAM used [{gpu.get('verdict', '?')}]")
    npu = baseline.get("npu", {})
    _print(f"  NPU: [{npu.get('verdict', '?')}] devices={npu.get('devices', [])}")
    gem = baseline.get("gemini", {})
    _print(f"  Gemini: [{gem.get('verdict', '?')}] mode={gem.get('mode', 'none')} latency={gem.get('latency_ms', '?')}ms")

    return {"status": "ANCHORED", "anchor_hash": baseline["anchor_hash"],
            "ssot_row": row_id, "baseline_summary": {
                "daemon_count": len(baseline.get("daemon_fleet", {})),
                "doc_count": baseline["ssot_stats"].get("doc_count"),
                "event_count": baseline["ssot_stats"].get("event_count"),
            }}


# ═══════════════════════════════════════════════════════════════
# § 5  SPELL: CHECK — Detect drift from anchor
# ═══════════════════════════════════════════════════════════════

def spell_check(quiet: bool = False) -> dict[str, Any]:
    """
    DIMENSIONAL_ANCHOR CHECK — Detect drift from baseline.

    SBE Contract:
      Given  an active anchor exists with baseline snapshot
      When   spell_check is cast
      Then   current state is compared to baseline on all dimensions
      And    ANCHORED (no drift) or DRIFT_DETECTED (with deltas) is returned
    """
    _print = (lambda *a, **k: None) if quiet else print

    if not ANCHOR_STATE_FILE.exists():
        _print("  [ERROR] No anchor set. Cast 'anchor' first.")
        return {"status": "NO_ANCHOR", "error": "No baseline captured"}

    state = json.loads(ANCHOR_STATE_FILE.read_text(encoding="utf-8"))
    if not state.get("active"):
        return {"status": "ANCHOR_RELEASED", "error": "Anchor was released"}

    baseline = state.get("baseline", {})

    # Verify anchor integrity (tamper check)
    stored_hash = baseline.get("anchor_hash", "")
    verify_data = dict(baseline)
    verify_data.pop("anchor_hash", None)
    computed_hash = hashlib.sha256(
        json.dumps(verify_data, sort_keys=True).encode()
    ).hexdigest()
    if stored_hash != computed_hash:
        _print("  [TAMPERED] Anchor state file has been modified!")
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.dimensional_anchor.tampered",
                        f"ANCHOR_TAMPERED:{stored_hash[:16]}",
                        {"stored_hash": stored_hash, "computed_hash": computed_hash,
                         "p4_adversarial": "State file tampering detected — anchor integrity violated"})
            conn.close()
        except Exception:
            pass
        return {"status": "ANCHOR_TAMPERED", "stored_hash": stored_hash,
                "computed_hash": computed_hash}

    # Capture current state
    _print("  [CHECK] Scanning for dimensional drift...")
    current = capture_baseline()

    # Detect drift
    drifts = detect_drift(baseline, current)

    state["check_count"] = state.get("check_count", 0) + 1
    now = datetime.now(timezone.utc).isoformat()

    if drifts:
        total_drifts = sum(len(v) for v in drifts.values())
        state["drift_count"] = state.get("drift_count", 0) + 1
        ANCHOR_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

        # Write drift CloudEvent
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.dimensional_anchor.drift",
                        f"DRIFT:{total_drifts}_changes:{','.join(drifts.keys())}",
                        {"drifts": drifts, "total_changes": total_drifts,
                         "dimensions_affected": list(drifts.keys()),
                         "anchor_set_at": state.get("set_at"),
                         "checks_since_anchor": state["check_count"]})
            conn.close()
        except Exception:
            pass

        _print(f"  [DRIFT DETECTED] {total_drifts} changes across {len(drifts)} dimensions")
        for dim, changes in drifts.items():
            _print(f"\n  [{dim.upper()}]:")
            for c in changes:
                _print(f"    → {c}")

        return {"status": "DRIFT_DETECTED", "drift_count": total_drifts,
                "dimensions": list(drifts.keys()), "drifts": drifts,
                "anchor_age_s": state.get("check_count", 0)}
    else:
        ANCHOR_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.dimensional_anchor.check",
                        f"CHECK_OK:no_drift:{state['check_count']}",
                        {"verdict": "ANCHORED", "checks": state["check_count"],
                         "anchor_set_at": state.get("set_at")})
            conn.close()
        except Exception:
            pass

        _print(f"  [ANCHORED] No drift detected. Check #{state['check_count']}.")
        return {"status": "ANCHORED", "checks": state["check_count"]}


# ═══════════════════════════════════════════════════════════════
# § 6  SPELL: STATUS — Show anchor state
# ═══════════════════════════════════════════════════════════════

def spell_status(quiet: bool = False) -> dict[str, Any]:
    """Show current anchor state without performing a drift check."""
    _print = (lambda *a, **k: None) if quiet else print

    if not ANCHOR_STATE_FILE.exists():
        _print("  [NO ANCHOR] No dimensional anchor is set.")
        return {"status": "NO_ANCHOR"}

    state = json.loads(ANCHOR_STATE_FILE.read_text(encoding="utf-8"))
    baseline = state.get("baseline", {})

    _print(f"  [ANCHOR STATUS]")
    _print(f"  Active: {state.get('active', False)}")
    _print(f"  Set at: {state.get('set_at', '?')[:19]}")
    _print(f"  Checks: {state.get('check_count', 0)}")
    _print(f"  Drifts detected: {state.get('drift_count', 0)}")
    _print(f"  Anchor hash: {baseline.get('anchor_hash', '?')[:16]}...")
    _print(f"  Baseline — Daemons: {len(baseline.get('daemon_fleet', {}))}")
    _print(f"  Baseline — SSOT docs: {baseline.get('ssot_stats', {}).get('doc_count', 0)}")
    _print(f"  Baseline — Models: {len(baseline.get('ollama_models', []))}")

    return {"status": "ACTIVE" if state.get("active") else "RELEASED",
            "set_at": state.get("set_at"), "check_count": state.get("check_count", 0),
            "drift_count": state.get("drift_count", 0),
            "anchor_hash": baseline.get("anchor_hash")}


# ═══════════════════════════════════════════════════════════════
# § 7  SPELL: RELEASE — Remove anchor
# ═══════════════════════════════════════════════════════════════

def spell_release(quiet: bool = False) -> dict[str, Any]:
    """
    DIMENSIONAL_ANCHOR RELEASE — Remove the anchor.

    SBE Contract:
      Given  an active anchor exists
      When   spell_release is cast
      Then   anchor is deactivated, release CloudEvent written
    """
    _print = (lambda *a, **k: None) if quiet else print

    if not ANCHOR_STATE_FILE.exists():
        return {"status": "NO_ANCHOR"}

    state = json.loads(ANCHOR_STATE_FILE.read_text(encoding="utf-8"))
    state["active"] = False

    ANCHOR_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.dimensional_anchor.release",
                    f"ANCHOR_RELEASED",
                    {"set_at": state.get("set_at"),
                     "total_checks": state.get("check_count", 0),
                     "total_drifts": state.get("drift_count", 0)})
        conn.close()
    except Exception:
        pass

    _print(f"  [RELEASED] Dimensional anchor removed.")
    _print(f"  Total checks: {state.get('check_count', 0)}")
    _print(f"  Total drifts: {state.get('drift_count', 0)}")

    return {"status": "RELEASED", "total_checks": state.get("check_count", 0),
            "total_drifts": state.get("drift_count", 0)}


# ═══════════════════════════════════════════════════════════════
# § 7b  SPELL: PROBE — Live hardware health (no anchor needed)
# ═══════════════════════════════════════════════════════════════

def spell_probe(quiet: bool = False) -> dict[str, Any]:
    """
    DIMENSIONAL_ANCHOR PROBE — Immediate live hardware health report.
    Does NOT require a prior anchor. One-shot diagnostic.

    SBE Contract:
      Given  the system is running
      When   spell_probe is cast
      Then   live snapshot of RAM/GPU/NPU/Gemini/Ollama/System returned
      And    each dimension has a verdict (OK/WARNING/CRITICAL/etc.)
      And    a probe CloudEvent is written to SSOT
    """
    _print = (lambda *a, **k: None) if quiet else print
    now = datetime.now(timezone.utc).isoformat()

    _print("  [PROBE] Running live hardware diagnostics...\n")

    # Run all probes
    ram     = _probe_ram()
    gpu     = _probe_gpu()
    npu     = _probe_npu()
    gemini  = _probe_gemini()
    system  = _probe_system()
    ollama_models = _capture_ollama_models()
    ssot    = _capture_ssot_stats()

    # ── RAM ──
    _print("  ┌─ RAM " + "─" * 56 + "┐")
    if ram["available"]:
        bar_len = 40
        filled = int(bar_len * ram["percent"] / 100)
        bar_char = "█" if ram["percent"] < RAM_WARNING_PCT else "▓" if ram["percent"] < RAM_CRITICAL_PCT else "░"
        bar = bar_char * filled + "·" * (bar_len - filled)
        _print(f"  │ [{bar}] {ram['percent']:.0f}%")
        _print(f"  │ Total: {ram['total_gb']:.1f} GB  Used: {ram['used_gb']:.1f} GB  "
               f"Free: {ram['free_gb']:.1f} GB")
        if ram["swap_used_gb"] > 0.1:
            _print(f"  │ Swap: {ram['swap_used_gb']:.1f}/{ram['swap_total_gb']:.1f} GB "
                   f"({ram['swap_percent']:.0f}%) ⚠ SWAPPING")
        verdict_color = {"OK": "✓", "WARNING": "⚠", "CRITICAL": "✗"}.get(ram["verdict"], "?")
        _print(f"  │ Verdict: {verdict_color} {ram['verdict']}")
    else:
        _print(f"  │ psutil not available: {ram.get('error', 'unknown')}")
    _print(f"  └{'─' * 63}┘\n")

    # ── GPU ──
    _print("  ┌─ GPU " + "─" * 56 + "┐")
    if gpu["available"]:
        nv = gpu.get("nvidia_smi")
        if nv:
            _print(f"  │ GPU: {nv['gpu_name']}")
            _print(f"  │ VRAM: {nv['vram_used_gb']:.1f}/{nv['vram_total_gb']:.1f} GB "
                   f"(free: {nv['vram_free_gb']:.1f} GB)")
            temp = nv.get("temperature_c")
            if temp:
                temp_icon = "🔥" if temp > 80 else "🌡️" if temp > 60 else "❄️"
                _print(f"  │ Temp: {temp}°C {temp_icon}  Driver: {nv['driver']}")
            else:
                _print(f"  │ Driver: {nv['driver']}")
        _print(f"  │ Ollama alive: {'✓' if gpu['ollama_alive'] else '✗'}")
        if gpu["loaded_models"]:
            _print(f"  │ Loaded models ({len(gpu['loaded_models'])}):")
            for m in gpu["loaded_models"]:
                _print(f"  │   {m['name']:30s}  {m['vram_gb']:.1f} GB VRAM")
        else:
            _print(f"  │ No models currently loaded in VRAM")
        verdict_icon = {"OK": "✓", "WARNING": "⚠", "CRITICAL": "✗", "HOT": "🔥"}.get(gpu["verdict"], "?")
        _print(f"  │ Verdict: {verdict_icon} {gpu['verdict']}")
    else:
        _print(f"  │ No GPU / Ollama not reachable")
    _print(f"  └{'─' * 63}┘\n")

    # ── NPU ──
    _print("  ┌─ NPU " + "─" * 56 + "┐")
    if npu["openvino_installed"]:
        _print(f"  │ OpenVINO: v{npu['openvino_version']}")
        _print(f"  │ Devices: {', '.join(npu['devices']) if npu['devices'] else 'none detected'}")
        if npu["embedder_running"]:
            _print(f"  │ Embedder: running (PID {npu.get('embedder_pid', '?')})")
        else:
            _print(f"  │ Embedder: not running")
    else:
        _print(f"  │ OpenVINO not installed (NPU probing unavailable)")
    verdict_icon = {"ACTIVE": "✓", "IDLE": "○", "NO_NPU_DEVICE": "⚠", "NO_OPENVINO": "—"}.get(npu["verdict"], "?")
    _print(f"  │ Verdict: {verdict_icon} {npu['verdict']}")
    _print(f"  └{'─' * 63}┘\n")

    # ── GEMINI ──
    _print("  ┌─ GEMINI " + "─" * 54 + "┐")
    _print(f"  │ Mode: {gemini.get('mode', 'none')}")
    if gemini.get("project"):
        _print(f"  │ Project: {gemini['project']}")
    if gemini.get("reachable"):
        _print(f"  │ Reachable: ✓  Latency: {gemini['latency_ms']}ms")
        if gemini.get("sample_model"):
            _print(f"  │ Sample model: {gemini['sample_model']}")
    elif gemini.get("error"):
        _print(f"  │ Error: {gemini['error'][:80]}")
    verdict_icon = {"OK": "✓", "SLOW": "⚠", "WARNING": "⚠",
                    "AUTH_FAILED": "✗", "RATE_LIMITED": "⛔",
                    "UNREACHABLE": "✗", "NO_CREDENTIALS": "—",
                    "NO_SDK": "—", "ERROR": "✗"}.get(gemini["verdict"], "?")
    _print(f"  │ Verdict: {verdict_icon} {gemini['verdict']}")
    _print(f"  └{'─' * 63}┘\n")

    # ── SYSTEM ──
    _print("  ┌─ SYSTEM " + "─" * 53 + "┐")
    _print(f"  │ Platform: {system.get('platform', '?')}")
    _print(f"  │ CPU: {system.get('cpu_percent', '?')}% across {system.get('cpu_cores', '?')} cores")
    _print(f"  │ Disk: {system.get('disk_free_gb', '?')} GB free of "
           f"{system.get('disk_total_gb', '?')} GB ({system.get('disk_percent', '?')}% used)")
    _print(f"  │ Processes: {system.get('process_count', '?')}")
    _print(f"  │ SSOT: {ssot.get('doc_count', '?')} docs, "
           f"{ssot.get('event_count', '?')} events, "
           f"FTS5: {'✓' if ssot.get('fts_ok') else '✗'}")
    _print(f"  │ Ollama models installed: {len(ollama_models)}")
    _print(f"  └{'─' * 63}┘\n")

    # Overall verdict
    verdicts = {
        "ram": ram["verdict"],
        "gpu": gpu["verdict"],
        "npu": npu["verdict"],
        "gemini": gemini["verdict"],
    }
    critical_any = any(v in ("CRITICAL", "AUTH_FAILED", "UNREACHABLE", "ERROR")
                       for v in verdicts.values())
    warning_any = any(v in ("WARNING", "SLOW", "HOT", "RATE_LIMITED")
                      for v in verdicts.values())

    if critical_any:
        overall = "CRITICAL"
        _print("  ╔═ OVERALL: ✗ CRITICAL ═══════════════════════════════════════╗")
    elif warning_any:
        overall = "WARNING"
        _print("  ╔═ OVERALL: ⚠ WARNING ════════════════════════════════════════╗")
    else:
        overall = "HEALTHY"
        _print("  ╔═ OVERALL: ✓ HEALTHY ════════════════════════════════════════╗")

    for dim, v in verdicts.items():
        icon = "✓" if v in ("OK", "ACTIVE", "IDLE") else "⚠" if v in ("WARNING", "SLOW", "HOT") else "—" if v.startswith("NO_") else "✗"
        _print(f"  ║  {dim:10s}: {icon} {v}")
    _print("  ╚═══════════════════════════════════════════════════════════════╝")

    # Write probe CloudEvent
    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.dimensional_anchor.probe",
                    f"PROBE:{overall}:ram={ram['verdict']}:gpu={gpu['verdict']}:"
                    f"npu={npu['verdict']}:gemini={gemini['verdict']}",
                    {"overall": overall, "verdicts": verdicts, "timestamp": now,
                     "ram": ram, "gpu": gpu, "npu": npu, "gemini": gemini,
                     "system": system, "ssot": ssot,
                     "ollama_model_count": len(ollama_models)})
        conn.close()
    except Exception as e:
        _print(f"\n  [WARN] SSOT write failed: {e}")

    return {
        "status": overall,
        "verdicts": verdicts,
        "ram": ram, "gpu": gpu, "npu": npu, "gemini": gemini,
        "system": system, "ssot": ssot,
        "ollama_model_count": len(ollama_models),
    }


# ═══════════════════════════════════════════════════════════════
# § 8  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "=" * 64)
    print("  P7 SPIDER SOVEREIGN — DIMENSIONAL ANCHOR")
    print("  Summoner of Seals and Spheres — Aspect A: SEALS")
    print("  " + "-" * 64)
    print("  Abjuration 4th — PHB p.223 — bars extradimensional movement")
    print("  Nothing shifts between planes while the anchor holds.")
    print("  " + "=" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — DIMENSIONAL_ANCHOR Spell (Gen90)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Spells:
  probe       Live hardware health (RAM/GPU/NPU/Gemini) — no anchor needed
  anchor      Capture baseline system snapshot
  check       Detect drift from baseline
  status      Show anchor state (no drift check)
  release     Remove anchor

Examples:
  python hfo_p7_dimensional_anchor.py probe           # immediate health report
  python hfo_p7_dimensional_anchor.py anchor
  python hfo_p7_dimensional_anchor.py check
  python hfo_p7_dimensional_anchor.py --json probe    # JSON health snapshot
""",
    )
    parser.add_argument("spell", choices=["probe", "anchor", "check", "status", "release"],
                        help="Spell variant")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    _print_banner()

    if args.spell == "probe":
        result = spell_probe()
    elif args.spell == "anchor":
        result = spell_anchor()
    elif args.spell == "check":
        result = spell_check()
    elif args.spell == "status":
        result = spell_status()
    elif args.spell == "release":
        result = spell_release()
    else:
        result = {"error": "Unknown spell"}

    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
