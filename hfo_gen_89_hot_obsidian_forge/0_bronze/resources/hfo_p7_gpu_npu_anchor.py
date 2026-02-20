#!/usr/bin/env python3
"""
hfo_p7_gpu_npu_anchor.py — GPU/NPU Utilization Anchor
========================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Layer: Diagnostics
Commander: SUMMONER OF SEALS AND SPHERES

PURPOSE:
    DIMENSIONAL ANCHOR focused exclusively on GPU (Intel Arc 140V, 16 GB)
    and NPU (Intel AI Boost) utilization. The operator reports both are
    "underutilized and weird." This anchor:

    1. DIAGNOSES the full hardware capability stack
    2. MEASURES actual utilization vs capacity
    3. GENERATES actionable upgrade path recommendations
    4. ANCHORS a baseline for drift detection over time
    5. WRITES structured CloudEvents to SSOT for governance

HARDWARE CONTEXT (from live probing 2026-02-19):
    GPU:  Intel(R) Arc(TM) 140V  — 16 GB VRAM, Level Zero runtime present
          Ollama 0.16.2 does 100% GPU offload via OneAPI/Level Zero
          phi4:14b (9.5 GB) + gemma3:4b (4.0 GB) = 13.5 GB VRAM used at peak
    NPU:  Intel(R) AI Boost — PCI VEN_8086&DEV_643E, Status: OK
          OpenVINO NOT installed — device is completely dark
          hfo_npu_embedder.py exists but cannot run (no openvino pip package)

SPELLS:
    diagnose    Full hardware capability audit + utilization + recommendations
    benchmark   Quick inference benchmarks per model tier (small/medium/large)
    preload     Load optimal model set into VRAM based on capacity
    unload      Release all VRAM (unload all models from Ollama)
    history     Show GPU/NPU utilization history from SSOT stigmergy

SBE/ATDD TIERS:
    TIER 1 — Invariant: Never exceed 15 GB VRAM (leave 1 GB headroom)
    TIER 2 — Happy path: diagnose produces structured report with verdicts
    TIER 3 — Benchmark: measurable tok/s per model with GPU offload %
    TIER 4 — Preload: load models up to VRAM budget, verify offload
    TIER 5 — History: query stigmergy for utilization trend

EVENT TYPES:
    hfo.gen89.p7.gpu_npu_anchor.diagnose   — Full diagnostic report
    hfo.gen89.p7.gpu_npu_anchor.benchmark  — Inference benchmark results
    hfo.gen89.p7.gpu_npu_anchor.preload    — Model preload event
    hfo.gen89.p7.gpu_npu_anchor.unload     — VRAM release event

USAGE:
    python hfo_p7_gpu_npu_anchor.py diagnose           # Full hardware audit
    python hfo_p7_gpu_npu_anchor.py benchmark          # Inference speed test
    python hfo_p7_gpu_npu_anchor.py preload            # Load optimal model set
    python hfo_p7_gpu_npu_anchor.py unload             # Clear VRAM
    python hfo_p7_gpu_npu_anchor.py history             # Utilization history
    python hfo_p7_gpu_npu_anchor.py --json diagnose    # JSON output

Medallion: bronze
Port: P7 NAVIGATE
"""

from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import hashlib
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Force UTF-8 stdout on Windows
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

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(HFO_ROOT / ".env")
except ImportError:
    pass

def _resolve_pointer(key: str) -> Path:
    pf = HFO_ROOT / "hfo_gen89_pointers_blessed.json"
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
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"

GEN = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG = f"hfo_p7_gpu_npu_anchor_gen{GEN}"

# ── Constants ──
OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
VRAM_TOTAL_GB = 16.0       # Intel Arc 140V
VRAM_HEADROOM_GB = 1.0     # Never exceed 15 GB
VRAM_BUDGET_GB = VRAM_TOTAL_GB - VRAM_HEADROOM_GB  # 15 GB usable

# Model tiers for benchmark/preload (name → approximate VRAM GB)
MODEL_TIERS = {
    "small": [
        ("lfm2.5-thinking:1.2b", 0.7),
        ("llama3.2:3b", 1.9),
        ("granite4:3b", 2.0),
        ("qwen2.5:3b", 1.8),
    ],
    "medium": [
        ("gemma3:4b", 3.1),
        ("qwen3:8b", 4.9),
        ("deepseek-r1:8b", 4.9),
        ("qwen2.5-coder:7b", 4.4),
    ],
    "large": [
        ("gemma3:12b", 7.6),
        ("phi4:14b", 8.4),
    ],
    "xl": [
        ("qwen3:30b-a3b", 17.3),
        ("deepseek-r1:32b", 18.5),
    ],
}


# ═══════════════════════════════════════════════════════════════
# § 1  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def get_db_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def write_event(conn: sqlite3.Connection, event_type: str, subject: str,
                data: dict) -> int:
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(data, default=str)
    content_hash = hashlib.sha256(
        f"{event_type}:{subject}:{payload}".encode("utf-8")
    ).hexdigest()
    cur = conn.execute("""
        INSERT OR IGNORE INTO stigmergy_events
        (event_type, source, subject, timestamp, data_json, content_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (event_type, SOURCE_TAG, subject, now, payload, content_hash))
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 2  HARDWARE DISCOVERY
# ═══════════════════════════════════════════════════════════════

def discover_gpu() -> dict[str, Any]:
    """
    Deep GPU discovery — Intel Arc 140V via WMI + Level Zero + Ollama.

    SBE:
      Given  system has Intel Arc 140V GPU
      When   GPU is discovered
      Then   name, VRAM, driver, Level Zero status, Ollama backend returned
    """
    result: dict[str, Any] = {
        "name": "UNKNOWN",
        "vram_total_gb": 0,
        "driver_version": "UNKNOWN",
        "level_zero": {"ze_loader": False, "ze_gpu_rt": False},
        "ollama": {"alive": False, "version": None, "gpu_offload": None},
        "wmi_status": "UNKNOWN",
    }

    # 1. WMI via PowerShell (fast, reliable)
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | "
             "Select-Object Name, DriverVersion, AdapterRAM, Status | "
             "ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
        )
        if ps.returncode == 0 and ps.stdout.strip():
            gpu_data = json.loads(ps.stdout)
            if isinstance(gpu_data, list):
                gpu_data = gpu_data[0]
            result["name"] = gpu_data.get("Name", "UNKNOWN")
            adapter_ram = gpu_data.get("AdapterRAM", 0)
            # WMI caps at 2GB for AdapterRAM — use known value for Arc 140V
            if "Arc" in result["name"] and "140V" in result["name"]:
                result["vram_total_gb"] = 16.0
            else:
                result["vram_total_gb"] = round(adapter_ram / (1024**3), 1) if adapter_ram else 0
            result["driver_version"] = gpu_data.get("DriverVersion", "UNKNOWN")
            result["wmi_status"] = gpu_data.get("Status", "UNKNOWN")
    except Exception:
        pass

    # 2. Level Zero runtime check
    sys32 = Path("C:/Windows/System32")
    result["level_zero"]["ze_loader"] = (sys32 / "ze_loader.dll").exists()
    result["level_zero"]["ze_gpu_rt"] = (sys32 / "ze_intel_gpu_raytracing.dll").exists()
    # Also check for tracing/validation layers
    for dll in ["ze_tracing_layer.dll", "ze_validation_layer.dll"]:
        result["level_zero"][dll.replace(".dll", "")] = (sys32 / dll).exists()

    # 3. Ollama status
    if HAS_HTTPX:
        try:
            r = httpx.get(f"{OLLAMA_BASE}/api/version", timeout=5)
            if r.status_code == 200:
                result["ollama"]["alive"] = True
                result["ollama"]["version"] = r.json().get("version", "?")
        except Exception:
            pass

    return result


def discover_npu() -> dict[str, Any]:
    """
    Deep NPU discovery — Intel AI Boost via WMI + OpenVINO.

    SBE:
      Given  system has Intel AI Boost NPU
      When   NPU is discovered
      Then   device ID, driver status, OpenVINO availability, device list returned
    """
    result: dict[str, Any] = {
        "device_name": None,
        "device_id": None,
        "wmi_status": "NOT_FOUND",
        "openvino_installed": False,
        "openvino_version": None,
        "available_devices": [],
        "npu_in_device_list": False,
        "embedder_script_exists": False,
        "model_cache_exists": False,
        "onnx_model_exists": False,
    }

    # 1. WMI check for NPU hardware
    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_PnPEntity | "
             "Where-Object { $_.Name -like '*AI Boost*' } | "
             "Select-Object Name, DeviceID, Status | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
        )
        if ps.returncode == 0 and ps.stdout.strip():
            npu_data = json.loads(ps.stdout)
            if isinstance(npu_data, list):
                npu_data = npu_data[0]
            result["device_name"] = npu_data.get("Name")
            result["device_id"] = npu_data.get("DeviceID")
            result["wmi_status"] = npu_data.get("Status", "UNKNOWN")
    except Exception:
        pass

    # 2. OpenVINO check
    try:
        import openvino as ov
        result["openvino_installed"] = True
        result["openvino_version"] = ov.__version__
        core = ov.Core()
        result["available_devices"] = core.available_devices
        result["npu_in_device_list"] = "NPU" in result["available_devices"]
    except ImportError:
        pass
    except Exception as e:
        result["openvino_error"] = str(e)[:100]

    # 3. Embedder infrastructure check
    embedder_path = _SELF_DIR / "hfo_npu_embedder.py"
    result["embedder_script_exists"] = embedder_path.exists()

    model_cache = HFO_ROOT / ".hfo_models"
    result["model_cache_exists"] = model_cache.exists()
    if model_cache.exists():
        onnx_hits = list(model_cache.rglob("model.onnx"))
        result["onnx_model_exists"] = len(onnx_hits) > 0

    return result


def discover_ollama_models() -> dict[str, Any]:
    """
    Full Ollama model inventory with VRAM fit analysis.

    SBE:
      Given  Ollama is running
      When   models are queried
      Then   full inventory with VRAM fit classification returned
    """
    result: dict[str, Any] = {
        "installed": [],
        "loaded": [],
        "total_disk_gb": 0,
        "total_vram_used_gb": 0,
        "vram_remaining_gb": VRAM_BUDGET_GB,
        "fits_in_vram": [],       # Models that fit without eviction
        "needs_eviction": [],     # Models that require evicting others
        "too_large": [],          # Models that exceed total VRAM
    }

    if not HAS_HTTPX:
        return result

    # Get installed models
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            total_disk = 0
            for m in sorted(models, key=lambda x: x.get("size", 0), reverse=True):
                name = m["name"]
                size_gb = round(m.get("size", 0) / (1024**3), 1)
                total_disk += size_gb
                quant = m.get("details", {}).get("quantization_level", "?")
                params = m.get("details", {}).get("parameter_size", "?")
                result["installed"].append({
                    "name": name,
                    "size_gb": size_gb,
                    "params": params,
                    "quant": quant,
                })

                # Classify by VRAM fit
                if size_gb <= VRAM_BUDGET_GB:
                    result["fits_in_vram"].append(name)
                else:
                    result["too_large"].append(name)

            result["total_disk_gb"] = round(total_disk, 1)
    except Exception:
        pass

    # Get currently loaded models
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
        if r.status_code == 200:
            running = r.json().get("models", [])
            total_vram = 0
            for m in running:
                vram_gb = round(m.get("size_vram", 0) / (1024**3), 1)
                total_gb = round(m.get("size", 0) / (1024**3), 1)
                total_vram += vram_gb
                gpu_pct = round(vram_gb / total_gb * 100) if total_gb > 0 else 0
                result["loaded"].append({
                    "name": m["name"],
                    "total_gb": total_gb,
                    "vram_gb": vram_gb,
                    "gpu_offload_pct": gpu_pct,
                    "context_length": m.get("context_length", 0),
                    "expires_at": m.get("expires_at", ""),
                })
            result["total_vram_used_gb"] = round(total_vram, 1)
            result["vram_remaining_gb"] = round(VRAM_BUDGET_GB - total_vram, 1)
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════
# § 3  UTILIZATION ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyze_utilization(gpu: dict, npu: dict, models: dict) -> dict[str, Any]:
    """
    Compute utilization % and generate underutilization verdicts.

    SBE:
      Given  GPU has 16GB VRAM and NPU has AI Boost
      When   utilization is analyzed
      Then   each resource gets a utilization %, verdict, and recommendation
    """
    result: dict[str, Any] = {
        "gpu": {
            "vram_used_gb": models["total_vram_used_gb"],
            "vram_budget_gb": VRAM_BUDGET_GB,
            "utilization_pct": 0,
            "models_loaded": len(models["loaded"]),
            "models_installed": len(models["installed"]),
            "verdict": "UNKNOWN",
            "recommendations": [],
        },
        "npu": {
            "hardware_present": npu["wmi_status"] == "OK",
            "software_ready": npu["openvino_installed"],
            "npu_detected": npu["npu_in_device_list"],
            "utilization_pct": 0,
            "verdict": "UNKNOWN",
            "recommendations": [],
        },
        "combined": {
            "verdict": "UNKNOWN",
            "total_compute_utilization_pct": 0,
            "upgrade_path": [],
        },
    }

    # ── GPU utilization ──
    gpu_util = result["gpu"]
    if models["total_vram_used_gb"] > 0:
        gpu_util["utilization_pct"] = round(
            models["total_vram_used_gb"] / VRAM_BUDGET_GB * 100, 1
        )

    if gpu_util["models_loaded"] == 0:
        gpu_util["verdict"] = "IDLE"
        gpu_util["recommendations"].append(
            "No models loaded. 16 GB VRAM sitting completely idle."
        )
        gpu_util["recommendations"].append(
            "RUN: python hfo_p7_gpu_npu_anchor.py preload  — to load optimal model set"
        )
    elif gpu_util["utilization_pct"] < 30:
        gpu_util["verdict"] = "UNDERUTILIZED"
        remaining = round(VRAM_BUDGET_GB - models["total_vram_used_gb"], 1)
        gpu_util["recommendations"].append(
            f"Only {gpu_util['utilization_pct']}% VRAM used. {remaining} GB free."
        )
        # Find models that could fill the gap
        for m in models["installed"]:
            if m["size_gb"] <= remaining and m["name"] not in [
                l["name"] for l in models["loaded"]
            ]:
                gpu_util["recommendations"].append(
                    f"Could also load: {m['name']} ({m['size_gb']} GB)"
                )
    elif gpu_util["utilization_pct"] < 70:
        gpu_util["verdict"] = "MODERATE"
        gpu_util["recommendations"].append(
            f"{gpu_util['utilization_pct']}% VRAM used — room for more."
        )
    elif gpu_util["utilization_pct"] < 95:
        gpu_util["verdict"] = "GOOD"
    else:
        gpu_util["verdict"] = "SATURATED"
        gpu_util["recommendations"].append(
            "VRAM near capacity. Consider unloading unused models."
        )

    # Check GPU offload quality
    for loaded in models["loaded"]:
        if loaded["gpu_offload_pct"] < 100:
            gpu_util["recommendations"].append(
                f"WARNING: {loaded['name']} only {loaded['gpu_offload_pct']}% GPU offload "
                f"(split CPU/GPU = slower)"
            )

    # ── NPU utilization ──
    npu_util = result["npu"]
    if not npu_util["hardware_present"]:
        npu_util["verdict"] = "NO_HARDWARE"
    elif not npu_util["software_ready"]:
        npu_util["verdict"] = "DARK"
        npu_util["utilization_pct"] = 0
        npu_util["recommendations"].extend([
            "Intel AI Boost NPU is PRESENT but software stack not installed.",
            "STEP 1: pip install openvino openvino-genai",
            "STEP 2: python -c \"import openvino; print(openvino.Core().available_devices)\"",
            "STEP 3: If NPU appears, run hfo_npu_embedder.py to embed all 9,861 SSOT docs",
            "BENEFIT: ~3ms/embedding on NPU, zero GPU VRAM impact, ~300 docs/sec",
            "BENEFIT: Semantic search across entire SSOT (cosine similarity)",
        ])
    elif not npu_util["npu_detected"]:
        npu_util["verdict"] = "DRIVER_ISSUE"
        npu_util["recommendations"].extend([
            "OpenVINO installed but NPU device not detected.",
            "Check Intel NPU driver: https://www.intel.com/content/www/us/en/download/794734/",
            "Try: pip install --upgrade openvino",
        ])
    else:
        # OpenVINO installed, NPU detected — check if actually in use
        embedder_running = False
        if HAS_PSUTIL:
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    cmdline = " ".join(proc.info.get("cmdline") or [])
                    if "npu_embedder" in cmdline:
                        embedder_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        if embedder_running:
            npu_util["verdict"] = "ACTIVE"
            npu_util["utilization_pct"] = 50  # approximate
        else:
            npu_util["verdict"] = "IDLE"
            npu_util["utilization_pct"] = 0
            npu_util["recommendations"].extend([
                "NPU is ready but not running any workloads.",
                "RUN: python hfo_npu_embedder.py embed-all  — embed SSOT docs",
            ])

    # ── Combined verdict ──
    combined = result["combined"]
    gpu_pct = gpu_util["utilization_pct"]
    npu_pct = npu_util["utilization_pct"]
    # Weight GPU 70%, NPU 30% (GPU is primary compute)
    combined["total_compute_utilization_pct"] = round(gpu_pct * 0.7 + npu_pct * 0.3, 1)

    if gpu_util["verdict"] in ("IDLE", "UNDERUTILIZED") and npu_util["verdict"] in ("DARK", "IDLE", "NO_HARDWARE"):
        combined["verdict"] = "SEVERELY_UNDERUTILIZED"
    elif gpu_util["verdict"] in ("IDLE", "UNDERUTILIZED") or npu_util["verdict"] in ("DARK", "IDLE"):
        combined["verdict"] = "UNDERUTILIZED"
    elif gpu_util["verdict"] in ("GOOD", "SATURATED") and npu_util["verdict"] == "ACTIVE":
        combined["verdict"] = "WELL_UTILIZED"
    else:
        combined["verdict"] = "MODERATE"

    # Upgrade path (prioritized actions)
    if npu_util["verdict"] == "DARK":
        combined["upgrade_path"].append({
            "priority": 1,
            "action": "Install OpenVINO for NPU",
            "command": "pip install openvino openvino-genai",
            "impact": "Unlocks NPU for embeddings (zero GPU impact, ~300 docs/sec)",
            "effort": "5 minutes",
        })
    if gpu_util["verdict"] in ("IDLE", "UNDERUTILIZED"):
        combined["upgrade_path"].append({
            "priority": 2,
            "action": "Pre-load models into VRAM",
            "command": "python hfo_p7_gpu_npu_anchor.py preload",
            "impact": f"Fill {round(VRAM_BUDGET_GB - models['total_vram_used_gb'], 1)} GB idle VRAM",
            "effort": "30 seconds",
        })
    if npu_util["verdict"] == "IDLE":
        combined["upgrade_path"].append({
            "priority": 3,
            "action": "Run NPU embedder on SSOT",
            "command": "python hfo_npu_embedder.py embed-all",
            "impact": "Semantic search across 9,861 docs",
            "effort": "~30 seconds for full SSOT",
        })
    combined["upgrade_path"].append({
        "priority": 4,
        "action": "Enable resource governance daemon",
        "command": "python hfo_resource_governance.py",
        "impact": "Continuous monitoring of GPU/NPU utilization with stigmergy events",
        "effort": "Background daemon",
    })

    return result


# ═══════════════════════════════════════════════════════════════
# § 4  SPELLS
# ═══════════════════════════════════════════════════════════════

def spell_diagnose(quiet: bool = False) -> dict[str, Any]:
    """
    DIAGNOSE — Full GPU/NPU hardware audit with utilization analysis.

    SBE:
      Given  system has Intel Arc 140V GPU and Intel AI Boost NPU
      When   diagnose is cast
      Then   structured report with verdicts and upgrade path returned
      And    CloudEvent written to SSOT
    """
    _print = (lambda *a, **k: None) if quiet else print
    now = datetime.now(timezone.utc).isoformat()

    _print("  [DIAGNOSE] GPU/NPU Hardware Utilization Anchor\n")

    # Discovery
    _print("  Discovering hardware...")
    gpu = discover_gpu()
    npu = discover_npu()
    models = discover_ollama_models()

    # Analysis
    _print("  Analyzing utilization...\n")
    analysis = analyze_utilization(gpu, npu, models)

    # ── GPU Section ──
    _print("  ┌─ GPU " + "─" * 56 + "┐")
    _print(f"  │ {gpu['name']}")
    _print(f"  │ VRAM: {gpu['vram_total_gb']} GB total, {VRAM_BUDGET_GB} GB budget (1 GB headroom)")
    _print(f"  │ Driver: {gpu['driver_version']}  WMI: {gpu['wmi_status']}")

    # Level Zero
    lz = gpu["level_zero"]
    lz_status = "✓" if lz["ze_loader"] else "✗"
    _print(f"  │ Level Zero: {lz_status} ze_loader={lz['ze_loader']} ze_gpu_rt={lz['ze_gpu_rt']}")

    # Ollama
    ollama = gpu["ollama"]
    _print(f"  │ Ollama: {'✓ v' + ollama['version'] if ollama['alive'] else '✗ NOT RUNNING'}")

    # Loaded models
    ga = analysis["gpu"]
    if models["loaded"]:
        _print(f"  │")
        _print(f"  │ Loaded models ({len(models['loaded'])}):")
        for m in models["loaded"]:
            icon = "✓" if m["gpu_offload_pct"] == 100 else "⚠"
            _print(f"  │   {icon} {m['name']:30s} {m['vram_gb']:5.1f} GB VRAM "
                   f"({m['gpu_offload_pct']}% GPU)")
        _print(f"  │")
        _print(f"  │ VRAM: {models['total_vram_used_gb']:.1f} / {VRAM_BUDGET_GB:.0f} GB "
               f"({ga['utilization_pct']:.0f}% utilized)")
    else:
        _print(f"  │")
        _print(f"  │ ⚠ NO MODELS LOADED — 16 GB VRAM completely idle")

    # VRAM budget bar
    bar_len = 40
    filled = min(bar_len, int(bar_len * ga["utilization_pct"] / 100))
    if ga["utilization_pct"] < 30:
        bar_char = "░"
    elif ga["utilization_pct"] < 70:
        bar_char = "▓"
    else:
        bar_char = "█"
    bar = bar_char * filled + "·" * (bar_len - filled)
    _print(f"  │ [{bar}] {ga['utilization_pct']:.0f}%")

    verdict_icon = {"IDLE": "✗", "UNDERUTILIZED": "⚠", "MODERATE": "○",
                    "GOOD": "✓", "SATURATED": "█"}.get(ga["verdict"], "?")
    _print(f"  │ Verdict: {verdict_icon} {ga['verdict']}")
    _print(f"  └{'─' * 63}┘\n")

    # ── NPU Section ──
    _print("  ┌─ NPU " + "─" * 56 + "┐")
    if npu["device_name"]:
        _print(f"  │ {npu['device_name']}")
        _print(f"  │ Device ID: {(npu['device_id'] or 'unknown')[:60]}")
        _print(f"  │ WMI Status: {npu['wmi_status']}")
    else:
        _print(f"  │ ⚠ No NPU device detected via WMI")

    na = analysis["npu"]
    _print(f"  │")
    _print(f"  │ OpenVINO: {'✓ v' + str(npu['openvino_version']) if npu['openvino_installed'] else '✗ NOT INSTALLED'}")
    if npu["openvino_installed"]:
        _print(f"  │ Devices: {', '.join(npu['available_devices']) if npu['available_devices'] else 'none detected'}")
        _print(f"  │ NPU in device list: {'✓' if npu['npu_in_device_list'] else '✗'}")
    _print(f"  │ Embedder script: {'✓' if npu['embedder_script_exists'] else '✗'}")
    _print(f"  │ ONNX model cached: {'✓' if npu['onnx_model_exists'] else '✗'}")

    verdict_icon = {"DARK": "✗", "NO_HARDWARE": "—", "DRIVER_ISSUE": "⚠",
                    "IDLE": "○", "ACTIVE": "✓"}.get(na["verdict"], "?")
    _print(f"  │ Verdict: {verdict_icon} {na['verdict']}")
    _print(f"  └{'─' * 63}┘\n")

    # ── Installed Models ──
    _print("  ┌─ MODEL INVENTORY " + "─" * 44 + "┐")
    _print(f"  │ {len(models['installed'])} models installed ({models['total_disk_gb']:.1f} GB on disk)")
    _print(f"  │")
    for tier_name in ["small", "medium", "large", "xl"]:
        tier_models = MODEL_TIERS.get(tier_name, [])
        installed_names = [m["name"] for m in models["installed"]]
        present = [n for n, _ in tier_models if n in installed_names]
        if present:
            fit_icon = "✓" if all(
                next((m["size_gb"] for m in models["installed"] if m["name"] == n), 99) <= VRAM_BUDGET_GB
                for n in present
            ) else "⚠"
            _print(f"  │ {tier_name.upper():8s} {fit_icon} {', '.join(present)}")
    _print(f"  │")
    _print(f"  │ Fits in 15 GB VRAM: {len(models['fits_in_vram'])} models")
    _print(f"  │ Too large (>15 GB): {len(models['too_large'])} models "
           f"({', '.join(models['too_large'][:3])})")
    _print(f"  └{'─' * 63}┘\n")

    # ── Overall Verdict ──
    ca = analysis["combined"]
    verdict_color = {
        "SEVERELY_UNDERUTILIZED": "✗✗",
        "UNDERUTILIZED": "✗",
        "MODERATE": "○",
        "WELL_UTILIZED": "✓",
    }.get(ca["verdict"], "?")

    _print(f"  ╔═ OVERALL: {verdict_color} {ca['verdict']} "
           f"({ca['total_compute_utilization_pct']:.0f}% compute) "
           + "═" * max(0, 38 - len(ca["verdict"])) + "╗")
    _print(f"  ║  GPU: {ga['verdict']:20s} ({ga['utilization_pct']:.0f}% VRAM)")
    _print(f"  ║  NPU: {na['verdict']:20s} ({na['utilization_pct']:.0f}% active)")
    _print(f"  ╚{'═' * 63}╝\n")

    # ── Upgrade Path ──
    if ca["upgrade_path"]:
        _print("  ┌─ UPGRADE PATH (prioritized) " + "─" * 33 + "┐")
        for step in sorted(ca["upgrade_path"], key=lambda x: x["priority"]):
            _print(f"  │ [{step['priority']}] {step['action']}")
            _print(f"  │     $ {step['command']}")
            _print(f"  │     Impact: {step['impact']}")
            _print(f"  │     Effort: {step['effort']}")
            _print(f"  │")
        _print(f"  └{'─' * 63}┘\n")

    # ── Recommendations ──
    all_recs = ga["recommendations"] + na["recommendations"]
    if all_recs:
        _print("  ┌─ RECOMMENDATIONS " + "─" * 44 + "┐")
        for i, rec in enumerate(all_recs, 1):
            _print(f"  │ {i}. {rec}")
        _print(f"  └{'─' * 63}┘")

    # Write CloudEvent
    report = {
        "timestamp": now,
        "gpu": gpu,
        "npu": npu,
        "models": models,
        "analysis": analysis,
    }
    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.gpu_npu_anchor.diagnose",
                    f"DIAGNOSE:{ca['verdict']}:gpu={ga['verdict']}:npu={na['verdict']}"
                    f":compute={ca['total_compute_utilization_pct']}pct",
                    report)
        conn.close()
    except Exception as e:
        _print(f"\n  [WARN] SSOT write failed: {e}")

    return report


def spell_benchmark(quiet: bool = False) -> dict[str, Any]:
    """
    BENCHMARK — Quick inference speed test per model tier.

    SBE:
      Given  Ollama is running with GPU offload
      When   benchmark is cast
      Then   tok/s measured for representative model from each tier
      And    GPU offload % verified per model
    """
    _print = (lambda *a, **k: None) if quiet else print
    now = datetime.now(timezone.utc).isoformat()

    _print("  [BENCHMARK] Inference speed test\n")

    if not HAS_HTTPX:
        _print("  ERROR: httpx not installed")
        return {"error": "httpx not installed"}

    installed_names = []
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        installed_names = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        _print("  ERROR: Cannot reach Ollama")
        return {"error": "Ollama unreachable"}

    results = []
    prompt = "Explain what a GPU is in exactly one sentence."

    for tier_name in ["small", "medium", "large"]:
        tier_models = MODEL_TIERS.get(tier_name, [])
        # Pick first installed model from tier
        candidate = None
        for name, _ in tier_models:
            if name in installed_names:
                candidate = name
                break
        if not candidate:
            _print(f"  {tier_name.upper():8s} — no installed model, skipping")
            continue

        _print(f"  {tier_name.upper():8s} benchmarking {candidate}...", end="", flush=True)

        try:
            t0 = time.time()
            r = httpx.post(
                f"{OLLAMA_BASE}/api/generate",
                json={
                    "model": candidate,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 50},
                },
                timeout=120,
            )
            elapsed = time.time() - t0
            data = r.json()

            eval_count = data.get("eval_count", 0)
            eval_duration_ns = data.get("eval_duration", 1)
            tok_s = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns > 0 else 0

            load_duration_ms = round(data.get("load_duration", 0) / 1e6)
            prompt_eval_ms = round(data.get("prompt_eval_duration", 0) / 1e6)

            # Check GPU offload
            ps = httpx.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
            loaded = ps.json().get("models", [])
            gpu_offload = 0
            vram_gb = 0
            for m in loaded:
                if m["name"] == candidate:
                    total = m.get("size", 1)
                    vram = m.get("size_vram", 0)
                    gpu_offload = round(vram / total * 100) if total > 0 else 0
                    vram_gb = round(vram / (1024**3), 1)
                    break

            entry = {
                "tier": tier_name,
                "model": candidate,
                "tok_s": round(tok_s, 1),
                "eval_tokens": eval_count,
                "total_s": round(elapsed, 1),
                "load_ms": load_duration_ms,
                "prompt_eval_ms": prompt_eval_ms,
                "gpu_offload_pct": gpu_offload,
                "vram_gb": vram_gb,
            }
            results.append(entry)
            _print(f" {tok_s:.1f} tok/s, {gpu_offload}% GPU, {vram_gb} GB VRAM, "
                   f"load={load_duration_ms}ms")

        except Exception as e:
            _print(f" ERROR: {str(e)[:60]}")
            results.append({
                "tier": tier_name,
                "model": candidate,
                "error": str(e)[:100],
            })

    # Summary
    _print()
    if results:
        _print("  ┌─ BENCHMARK RESULTS " + "─" * 42 + "┐")
        for r in results:
            if "error" not in r:
                icon = "✓" if r["gpu_offload_pct"] == 100 else "⚠"
                _print(f"  │ {icon} {r['tier']:8s} {r['model']:25s} "
                       f"{r['tok_s']:6.1f} tok/s  {r['vram_gb']:4.1f} GB VRAM")
            else:
                _print(f"  │ ✗ {r['tier']:8s} {r['model']:25s} ERROR")
        _print(f"  └{'─' * 63}┘")

    report = {"timestamp": now, "results": results}

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.gpu_npu_anchor.benchmark",
                    f"BENCH:{len(results)}_models",
                    report)
        conn.close()
    except Exception as e:
        _print(f"\n  [WARN] SSOT write failed: {e}")

    return report


def spell_preload(quiet: bool = False) -> dict[str, Any]:
    """
    PRELOAD — Load optimal model combination into VRAM.

    Strategy: Fill VRAM with most capable models that fit.
    Priority: 1 large reasoning model + 1 medium coder + 1 small fast model.

    SBE:
      Given  VRAM budget is 15 GB
      When   preload is cast
      Then   optimal model set loaded with 100% GPU offload
      And    VRAM utilization > 70%
    """
    _print = (lambda *a, **k: None) if quiet else print
    now = datetime.now(timezone.utc).isoformat()

    _print("  [PRELOAD] Loading optimal model set into VRAM\n")

    if not HAS_HTTPX:
        return {"error": "httpx not installed"}

    # Get installed models
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        installed = {m["name"]: round(m.get("size", 0) / (1024**3), 1)
                     for m in r.json().get("models", [])}
    except Exception:
        return {"error": "Ollama unreachable"}

    # Get currently loaded
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
        loaded = {m["name"]: round(m.get("size_vram", 0) / (1024**3), 1)
                  for m in r.json().get("models", [])}
    except Exception:
        loaded = {}

    current_vram = sum(loaded.values())
    _print(f"  Current VRAM: {current_vram:.1f} / {VRAM_BUDGET_GB:.0f} GB")
    _print(f"  Currently loaded: {list(loaded.keys()) or 'none'}\n")

    # Optimal load strategy for 15 GB budget:
    # Priority order (preference for reasoning + coding diversity)
    preferred_set = [
        ("phi4:14b", "large_reasoning"),
        ("gemma3:12b", "large_multimodal"),
        ("qwen3:8b", "medium_reasoning"),
        ("qwen2.5-coder:7b", "medium_coder"),
        ("deepseek-r1:8b", "medium_reasoning_alt"),
        ("gemma3:4b", "medium_multimodal"),
        ("qwen3:30b-a3b", "xl_moe"),  # MoE — only 3B active params
        ("granite4:3b", "small_fast"),
        ("llama3.2:3b", "small_general"),
        ("qwen2.5:3b", "small_general_alt"),
        ("lfm2.5-thinking:1.2b", "tiny_thinking"),
    ]

    to_load = []
    budget_remaining = VRAM_BUDGET_GB - current_vram

    for model_name, role in preferred_set:
        if model_name not in installed:
            continue
        if model_name in loaded:
            continue  # already loaded
        size = installed[model_name]
        if size <= budget_remaining:
            to_load.append((model_name, size, role))
            budget_remaining -= size

    if not to_load:
        _print("  ✓ VRAM already optimally filled (or no models fit remaining space)")
        return {"status": "ALREADY_OPTIMAL", "loaded": list(loaded.keys())}

    _print(f"  Loading {len(to_load)} models:")
    loaded_results = []
    for model_name, size, role in to_load:
        _print(f"    Loading {model_name} ({size} GB, {role})...", end="", flush=True)
        try:
            r = httpx.post(
                f"{OLLAMA_BASE}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "hi",
                    "stream": False,
                    "options": {"num_predict": 1},
                },
                timeout=180,
            )
            if r.status_code == 200:
                _print(" ✓")
                loaded_results.append({"model": model_name, "size_gb": size,
                                      "role": role, "status": "loaded"})
            else:
                _print(f" ✗ HTTP {r.status_code}")
                loaded_results.append({"model": model_name, "error": f"HTTP {r.status_code}"})
        except Exception as e:
            _print(f" ✗ {str(e)[:40]}")
            loaded_results.append({"model": model_name, "error": str(e)[:80]})

    # Verify final state
    _print()
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
        final_models = r.json().get("models", [])
        final_vram = sum(m.get("size_vram", 0) / (1024**3) for m in final_models)
        _print(f"  Final VRAM: {final_vram:.1f} / {VRAM_BUDGET_GB:.0f} GB "
               f"({final_vram/VRAM_BUDGET_GB*100:.0f}%)")
        for m in final_models:
            vram = m.get("size_vram", 0) / (1024**3)
            gpu_pct = round(vram / (m.get("size", 1) / (1024**3)) * 100) if m.get("size") else 0
            _print(f"    ✓ {m['name']:30s} {vram:.1f} GB ({gpu_pct}% GPU)")
    except Exception:
        pass

    report = {
        "timestamp": now,
        "models_loaded": loaded_results,
        "budget_gb": VRAM_BUDGET_GB,
    }

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.gpu_npu_anchor.preload",
                    f"PRELOAD:{len(loaded_results)}_models",
                    report)
        conn.close()
    except Exception:
        pass

    return report


def spell_unload(quiet: bool = False) -> dict[str, Any]:
    """
    UNLOAD — Release all models from VRAM.

    SBE:
      Given  models are loaded in VRAM
      When   unload is cast
      Then   all models removed and VRAM freed
    """
    _print = (lambda *a, **k: None) if quiet else print

    _print("  [UNLOAD] Releasing all models from VRAM\n")

    if not HAS_HTTPX:
        return {"error": "httpx not installed"}

    # Get loaded models
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
        loaded = r.json().get("models", [])
    except Exception:
        return {"error": "Ollama unreachable"}

    if not loaded:
        _print("  No models loaded — nothing to unload")
        return {"status": "ALREADY_EMPTY"}

    unloaded = []
    for m in loaded:
        name = m["name"]
        _print(f"  Unloading {name}...", end="", flush=True)
        try:
            r = httpx.post(
                f"{OLLAMA_BASE}/api/generate",
                json={"model": name, "keep_alive": 0},
                timeout=30,
            )
            _print(" ✓")
            unloaded.append(name)
        except Exception as e:
            _print(f" ✗ {str(e)[:40]}")

    _print(f"\n  Unloaded {len(unloaded)} models")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "unloaded": unloaded,
    }

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.gpu_npu_anchor.unload",
                    f"UNLOAD:{len(unloaded)}_models",
                    report)
        conn.close()
    except Exception:
        pass

    return report


def spell_history(quiet: bool = False) -> dict[str, Any]:
    """
    HISTORY — GPU/NPU utilization history from SSOT stigmergy.

    SBE:
      Given  SSOT has GPU/NPU anchor events
      When   history is cast
      Then   summary of utilization trend returned
    """
    _print = (lambda *a, **k: None) if quiet else print

    _print("  [HISTORY] GPU/NPU Utilization History\n")

    try:
        conn = get_db_ro()
        cur = conn.execute("""
            SELECT id, event_type, timestamp, subject, data
            FROM stigmergy_events
            WHERE event_type LIKE '%gpu_npu_anchor%'
               OR event_type LIKE '%dimensional_anchor.probe%'
               OR event_type LIKE '%governance%'
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        _print(f"  ERROR: {e}")
        return {"error": str(e)}

    if not rows:
        _print("  No GPU/NPU events found in stigmergy trail")
        return {"events": []}

    _print(f"  Found {len(rows)} events:\n")
    events = []
    for row in rows:
        ts = row["timestamp"][:19]
        etype = row["event_type"].split(".")[-1]
        subject = row["subject"][:70]
        _print(f"  {ts}  {etype:12s}  {subject}")
        events.append({
            "id": row["id"],
            "type": row["event_type"],
            "timestamp": row["timestamp"],
            "subject": row["subject"],
        })

    # Extract trend if we have diagnose events
    diagnose_events = [r for r in rows if "diagnose" in r["event_type"]]
    if diagnose_events:
        _print(f"\n  ── Utilization Trend ({len(diagnose_events)} diagnoses) ──")
        for r in diagnose_events[:5]:
            try:
                data = json.loads(r["data"])
                ga = data.get("analysis", {}).get("gpu", {})
                na = data.get("analysis", {}).get("npu", {})
                ca = data.get("analysis", {}).get("combined", {})
                _print(f"  {r['timestamp'][:19]}  GPU:{ga.get('verdict','?'):15s} "
                       f"NPU:{na.get('verdict','?'):10s} "
                       f"Combined:{ca.get('verdict','?')}")
            except Exception:
                pass

    return {"events": events}


# ═══════════════════════════════════════════════════════════════
# § 5  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "=" * 64)
    print("  P7 SUMMONER OF SEALS AND SPHERES — GPU/NPU ANCHOR")
    print("  " + "-" * 64)
    print("  Intel Arc 140V (16 GB) + Intel AI Boost NPU")
    print("  Dimensional Anchor for compute utilization")
    print("  " + "=" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="P7 GPU/NPU Utilization Anchor (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Spells:
  diagnose    Full hardware audit + utilization + recommendations
  benchmark   Inference speed test per model tier
  preload     Load optimal model set into VRAM
  unload      Release all VRAM
  history     Utilization history from SSOT

Examples:
  python hfo_p7_gpu_npu_anchor.py diagnose
  python hfo_p7_gpu_npu_anchor.py benchmark
  python hfo_p7_gpu_npu_anchor.py preload
  python hfo_p7_gpu_npu_anchor.py --json diagnose
""",
    )
    parser.add_argument("spell",
                        choices=["diagnose", "benchmark", "preload", "unload", "history"],
                        help="Spell variant")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    _print_banner()

    if args.spell == "diagnose":
        result = spell_diagnose()
    elif args.spell == "benchmark":
        result = spell_benchmark()
    elif args.spell == "preload":
        result = spell_preload()
    elif args.spell == "unload":
        result = spell_unload()
    elif args.spell == "history":
        result = spell_history()
    else:
        result = {"error": "Unknown spell"}

    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
