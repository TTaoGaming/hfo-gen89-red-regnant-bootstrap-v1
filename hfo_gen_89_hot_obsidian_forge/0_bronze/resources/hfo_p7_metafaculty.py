#!/usr/bin/env python3
"""
hfo_p7_metafaculty.py — P7 Spider Sovereign: METAFACULTY (Psion/Seer 9th)

    "You gain complete knowledge of a subject."
        — Expanded Psionics Handbook p.117, Clairsentience (Seer 9th)

Port 7 NAVIGATE apex intelligence meta-heuristic optimizer.
The 9th-level Seer capstone — omniscient multi-port awareness.

  SCAN    → Read all 8 port heartbeats + model fitness signals
  PARETO  → Compute non-dominated model configurations
  ARCHIVE → MAP-ELITES quality-diversity grid (8 ports × 3 fitness dims)
  ACO     → Pheromone-weighted model selection trails (Dorigo, 1996)
  SSO     → Social Spider vibration propagation (James-Yu, 2013)
  STEER   → Emit optimal model assignment directives per port

Architecture:
  Port:       P7 NAVIGATE (Spider Sovereign)
  Discipline: Clairsentience (Seer)
  Level:      9th (capstone — nothing above this)
  Dyad:       P0 OBSERVE ↔ P7 NAVIGATE (sense → steer → sense)
  Daemon:     Persistent optimization loop or one-shot scan

Enriched Signal Schema:
  Every daemon CloudEvent SHOULD carry these fields for swarm coordination:
    model_name, model_tier, model_size_gb, tok_s_actual, inference_ms,
    temperature, ai_source, vram_mb, prompt_tokens, completion_tokens,
    chimera_score, fitness_vector

  METAFACULTY reads whatever signals exist, computes what's missing from
  its MODEL_CATALOG, and emits steering directives that downstream
  daemons can consume to self-optimize.

Usage:
  python hfo_p7_metafaculty.py --scan          # One-shot: scan + optimize + steer
  python hfo_p7_metafaculty.py --daemon         # Continuous optimization loop
  python hfo_p7_metafaculty.py --status         # Current METAFACULTY state from SSOT
  python hfo_p7_metafaculty.py --archive        # Full MAP-ELITES archive detail
  python hfo_p7_metafaculty.py --pareto         # Pareto frontier analysis
  python hfo_p7_metafaculty.py --signals        # Enriched signal gap analysis
  python hfo_p7_metafaculty.py --dry-run --scan # Scan without writing to SSOT
"""

import argparse
import hashlib
import json
import math
import os
import secrets
import signal as signal_module
import sqlite3
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ═══════════════════════════════════════════════════════════════
# § 0  IDENTITY & CONSTANTS
# ═══════════════════════════════════════════════════════════════

DAEMON_NAME = "P7 Metafaculty"
DAEMON_VERSION = "1.0"
DAEMON_PORT = "P7"
SOURCE_TAG = f"hfo_metafaculty_gen89_v{DAEMON_VERSION}"

# Event types — the METAFACULTY's voice
EVT_SCAN       = "hfo.gen89.metafaculty.scan"
EVT_PARETO     = "hfo.gen89.metafaculty.pareto"
EVT_STEERING   = "hfo.gen89.metafaculty.steering"
EVT_ARCHIVE    = "hfo.gen89.metafaculty.archive"
EVT_PHEROMONE  = "hfo.gen89.metafaculty.pheromone"
EVT_VIBRATION  = "hfo.gen89.metafaculty.vibration"
EVT_HEARTBEAT  = "hfo.gen89.metafaculty.heartbeat"
EVT_ERROR      = "hfo.gen89.metafaculty.error"

# Timing
DEFAULT_INTERVAL_S = 300  # 5 min between optimization cycles
SCAN_WINDOW_MINUTES = 60  # Look back 60 min for heartbeats

# ACO parameters (Dorigo 1996 — Ant Colony Optimization)
ACO_ALPHA = 1.0                # Pheromone trail importance
ACO_BETA = 2.0                 # Heuristic importance
ACO_RHO = 0.1                  # Evaporation rate per hour
ACO_MIN_PHEROMONE = 0.01       # Floor to prevent cold-start starvation
ACO_MAX_PHEROMONE = 10.0       # Ceiling to prevent trail lock-in

# SSO parameters (James-Yu 2013 — Social Spider Optimization)
SSO_DAMPING = 0.7              # Vibration damping across port adjacency
SSO_MAX_AMPLITUDE = 5.0        # Amplitude cap prevents cascade

# D&D 3.5e Expanded Psionics Handbook flavor
SPELL_NAME = "METAFACULTY"
SPELL_LEVEL = "Psion/Seer 9th"
SPELL_SOURCE = "XPH p.117, Clairsentience"
SPELL_ALIAS = "Omniscient system-wide meta-heuristic optimizer"
POWER_QUOTE = "You gain complete knowledge of a subject."

CORE_THESIS = (
    "Omniscience without action is paralysis. "
    "Action without omniscience is blindness. "
    "METAFACULTY is the bridge."
)

# ═══════════════════════════════════════════════════════════════
# § 1  THE OCTREE — 8 Ports & Their Domains
# ═══════════════════════════════════════════════════════════════

OCTREE_PORTS = {
    "P0": {"word": "OBSERVE",    "commander": "Lidless Legion",    "domain": "Sensing under contest"},
    "P1": {"word": "BRIDGE",     "commander": "Web Weaver",        "domain": "Shared data fabric"},
    "P2": {"word": "SHAPE",      "commander": "Mirror Magus",      "domain": "Creation / models"},
    "P3": {"word": "INJECT",     "commander": "Harmonic Hydra",    "domain": "Payload delivery"},
    "P4": {"word": "DISRUPT",    "commander": "Red Regnant",       "domain": "Red team / probing"},
    "P5": {"word": "IMMUNIZE",   "commander": "Pyre Praetorian",   "domain": "Blue team / gates"},
    "P6": {"word": "ASSIMILATE", "commander": "Kraken Keeper",     "domain": "Learning / memory"},
    "P7": {"word": "NAVIGATE",   "commander": "Spider Sovereign",  "domain": "C2 / steering"},
}

# ═══════════════════════════════════════════════════════════════
# § 2  MODEL CATALOG — The Known Universe
# ═══════════════════════════════════════════════════════════════
#
# Every model the fleet might use, with static properties.
# chimera_score = P2 chimera_loop MAP-ELITES eval aggregate (None = untested)
# harness_pass  = prey8_eval_harness pass rate (None = untested)
# tok_s_est     = estimated tokens/sec on Intel Arc 140V 16GB Vulkan
#

MODEL_CATALOG: dict[str, dict[str, Any]] = {
    # ── Local Ollama (Intel Arc 140V, 16GB VRAM, Vulkan backend) ──
    "lfm2.5-thinking:1.2b":  {"size_gb": 0.7,  "tok_s_est": 35.0, "params_b": 1.2,  "tier": "local",  "arch": "lfm",        "chimera_score": None,  "harness_pass": None},
    "qwen2.5:3b":            {"size_gb": 1.9,  "tok_s_est": 25.0, "params_b": 3.0,  "tier": "local",  "arch": "qwen2.5",    "chimera_score": None,  "harness_pass": None},
    "llama3.2:3b":           {"size_gb": 2.0,  "tok_s_est": 25.0, "params_b": 3.0,  "tier": "local",  "arch": "llama3.2",   "chimera_score": None,  "harness_pass": 0.60},
    "granite4:3b":           {"size_gb": 2.1,  "tok_s_est": 22.5, "params_b": 3.0,  "tier": "local",  "arch": "granite4",   "chimera_score": None,  "harness_pass": None},
    "gemma3:4b":             {"size_gb": 3.3,  "tok_s_est": 18.0, "params_b": 4.0,  "tier": "local",  "arch": "gemma3",     "chimera_score": 0.782, "harness_pass": None},
    "qwen2.5-coder:7b":     {"size_gb": 4.7,  "tok_s_est": 12.0, "params_b": 7.0,  "tier": "local",  "arch": "qwen-coder", "chimera_score": 0.848, "harness_pass": 1.00},
    "deepseek-r1:8b":       {"size_gb": 5.2,  "tok_s_est": 10.0, "params_b": 8.0,  "tier": "local",  "arch": "deepseek-r1","chimera_score": None,  "harness_pass": None},
    "qwen3:8b":              {"size_gb": 5.2,  "tok_s_est": 11.5, "params_b": 8.0,  "tier": "local",  "arch": "qwen3",      "chimera_score": None,  "harness_pass": None},
    "gemma3:12b":            {"size_gb": 8.1,  "tok_s_est": 7.0,  "params_b": 12.0, "tier": "local",  "arch": "gemma3",     "chimera_score": None,  "harness_pass": None},
    "phi4:14b":              {"size_gb": 9.1,  "tok_s_est": 6.0,  "params_b": 14.0, "tier": "local",  "arch": "phi4",       "chimera_score": None,  "harness_pass": None},
    "qwen3:30b-a3b":         {"size_gb": 18.0, "tok_s_est": 20.0, "params_b": 30.0, "tier": "local",  "arch": "qwen3-moe",  "chimera_score": None,  "harness_pass": None,
                              "note": "MoE — 30B total, ~3B active. May exceed 16GB VRAM."},
    "deepseek-r1:32b":       {"size_gb": 19.0, "tok_s_est": 0.0,  "params_b": 32.0, "tier": "local",  "arch": "deepseek-r1","chimera_score": None,  "harness_pass": None,
                              "banned": True, "ban_reason": ">16GB VRAM on Intel Arc 140V"},

    # ── Gemini API (Google free tier @ 2026-02) ──
    "gemini-2.5-pro-preview":   {"size_gb": 0, "tok_s_est": 50.0,  "params_b": 0, "tier": "api", "arch": "gemini-pro",   "chimera_score": None, "harness_pass": None, "api_rpm": 5},
    "gemini-2.5-flash-preview": {"size_gb": 0, "tok_s_est": 150.0, "params_b": 0, "tier": "api", "arch": "gemini-flash", "chimera_score": None, "harness_pass": None, "api_rpm": 15},
    "gemini-2.0-flash":         {"size_gb": 0, "tok_s_est": 200.0, "params_b": 0, "tier": "api", "arch": "gemini-flash", "chimera_score": None, "harness_pass": None, "api_rpm": 15},
}

# Default port model assignments (before METAFACULTY optimization)
DEFAULT_PORT_MODELS = {
    "P0": "granite4:3b",          # OBSERVE: lightweight fast sensing
    "P1": "qwen2.5:3b",           # BRIDGE: data fabric coordination
    "P2": "qwen2.5-coder:7b",     # SHAPE: creation / code quality
    "P3": "lfm2.5-thinking:1.2b", # INJECT: ultra-fast delivery
    "P4": "qwen2.5-coder:7b",     # DISRUPT: Singer (chimera top 0.848)
    "P5": "gemma3:4b",            # IMMUNIZE: Dancer (budget defensive 0.782)
    "P6": "qwen3:8b",             # ASSIMILATE: learning / memory
    "P7": "phi4:14b",             # NAVIGATE: deep reasoning for steering
}

# ═══════════════════════════════════════════════════════════════
# § 3  ENRICHED SIGNAL SCHEMA — What Swarm Signals Should Exist
# ═══════════════════════════════════════════════════════════════

ENRICHED_SIGNAL_FIELDS = {
    # Required: every daemon CloudEvent MUST carry these
    "model_name":        {"type": "string", "required": True,
                          "desc": "Ollama/API model identifier (e.g. 'qwen2.5-coder:7b')"},
    "model_tier":        {"type": "string", "required": True,
                          "desc": "'local' (Ollama) or 'api' (Gemini/cloud)"},
    "model_size_gb":     {"type": "float",  "required": True,
                          "desc": "VRAM footprint in GB (0 for API models)"},
    "tok_s_actual":      {"type": "float",  "required": True,
                          "desc": "Measured tokens/sec this inference call"},
    "inference_ms":      {"type": "int",    "required": True,
                          "desc": "Total inference latency in milliseconds"},
    "temperature":       {"type": "float",  "required": True,
                          "desc": "Sampling temperature used (e.g. 0.7)"},
    "ai_source":         {"type": "string", "required": True,
                          "desc": "'ai' or 'fallback_deterministic'"},
    # Optional: enriches the signal for deeper optimization
    "vram_mb":           {"type": "int",    "required": False,
                          "desc": "VRAM allocated at inference time (MB)"},
    "prompt_tokens":     {"type": "int",    "required": False,
                          "desc": "Input tokens fed to the model"},
    "completion_tokens": {"type": "int",    "required": False,
                          "desc": "Output tokens generated by the model"},
    "chimera_score":     {"type": "float",  "required": False,
                          "desc": "Latest P2 chimera MAP-ELITES eval aggregate (0-1)"},
    "fitness_vector":    {"type": "dict",   "required": False,
                          "desc": "{intelligence, speed, cost} from METAFACULTY"},
}

# Which daemons currently emit which fields (gap analysis input)
CURRENT_SIGNAL_COVERAGE = {
    # v1.2 enriched: model_tier, model_size_gb, tok_s_actual, inference_ms, temperature all propagated
    "Singer (P4)": {"model_name": True, "ai_source": True, "model_tier": True,
                    "model_size_gb": True, "tok_s_actual": True, "inference_ms": True,
                    "temperature": True, "vram_mb": False},
    "Dancer (P5)": {"model_name": True, "ai_source": True, "model_tier": True,
                    "model_size_gb": True, "tok_s_actual": True, "inference_ms": True,
                    "temperature": True, "vram_mb": False},
    "Loop (P4+P5)": {"model_name": True, "ai_source": False, "model_tier": True,
                     "model_size_gb": True, "tok_s_actual": False, "inference_ms": True,
                     "temperature": True, "vram_mb": False},
}

# ═══════════════════════════════════════════════════════════════
# § 4  PAL RESOLUTION & DATABASE
# ═══════════════════════════════════════════════════════════════

_HERE = Path(__file__).resolve().parent

def resolve_ssot_path() -> str:
    """Resolve SSOT database path via PAL pointers or environment."""
    env_path = os.environ.get("HFO_SSOT_DB")
    if env_path and os.path.isfile(env_path):
        return env_path

    pal = _HERE / "hfo_pointers.py"
    if pal.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(pal), "resolve", "ssot.db"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                p = result.stdout.strip()
                if os.path.isfile(p):
                    return p
        except Exception:
            pass

    for candidate in [
        _HERE.parent.parent / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite",
    ]:
        if candidate.exists():
            return str(candidate)

    print("FATAL: Cannot resolve SSOT database path.", file=sys.stderr)
    sys.exit(1)


def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{resolve_ssot_path()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_db_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(resolve_ssot_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def write_event(conn, event_type, subject, data, source=SOURCE_TAG) -> int:
    """Write enriched CloudEvent to stigmergy_events."""
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(
            f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()
        ).hexdigest(),
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(envelope, sort_keys=True).encode()
    ).hexdigest()
    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 5  OMNISCIENT SCANNER — Read All Port Signals
# ═══════════════════════════════════════════════════════════════

def omniscient_scan(conn: sqlite3.Connection,
                    window_minutes: int = SCAN_WINDOW_MINUTES) -> dict:
    """Scan all port heartbeats and fitness signals from stigmergy.

    METAFACULTY sees everything. Returns structured fleet-wide view:
      ports        — per-port status, model, success rate
      models_seen  — which models are active and where
      signal_gaps  — which enriched signals are missing per port
      fleet_health — aggregate coverage, fallback rates, gap counts
    """
    scan: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "window_minutes": window_minutes,
        "ports": {},
        "models_seen": {},
        "signal_gaps": [],
        "fleet_health": {},
    }

    # All heartbeats in window
    rows = conn.execute(
        """SELECT event_type, subject, data_json, timestamp
           FROM stigmergy_events
           WHERE event_type LIKE '%heartbeat%'
             AND timestamp > datetime('now', ? || ' minutes')
           ORDER BY id DESC""",
        (f"-{window_minutes}",),
    ).fetchall()

    port_heartbeats: dict[str, list] = defaultdict(list)
    for r in rows:
        try:
            envelope = json.loads(r["data_json"])
            data = envelope.get("data", envelope)
            port = data.get("daemon_port", _infer_port(r["event_type"]))
            model = data.get("model", "unknown")

            hb = {
                "model": model,
                "timestamp": r["timestamp"],
                "event_type": r["event_type"],
                "ai_calls": data.get("ai_calls", 0),
                "ai_failures": data.get("ai_failures", 0),
                "fallback_uses": data.get("fallback_uses", 0),
                "errors": data.get("errors", 0),
                "cycle": data.get("cycle", data.get("loop_cycle", 0)),
                "daemon_version": data.get("daemon_version", "?"),
                "daemon_name": data.get("daemon_name", "?"),
                # Enriched signals (may be absent if daemons not upgraded yet)
                "inference_ms": data.get("inference_ms"),
                "tok_s_actual": data.get("tok_s_actual"),
                "temperature": data.get("temperature"),
                "vram_mb": data.get("vram_mb"),
            }
            port_heartbeats[port].append(hb)

            # Track models across all ports
            if model not in scan["models_seen"]:
                scan["models_seen"][model] = {
                    "ports": set(),
                    "total_calls": 0,
                    "total_failures": 0,
                    "total_fallbacks": 0,
                }
            obs = scan["models_seen"][model]
            obs["ports"].add(port)
            obs["total_calls"] += hb["ai_calls"]
            obs["total_failures"] += hb["ai_failures"]
            obs["total_fallbacks"] += hb["fallback_uses"]

        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    # Analyze each port
    for port_id in sorted(OCTREE_PORTS.keys()):
        hbs = port_heartbeats.get(port_id, [])
        port_info: dict[str, Any] = {
            "commander": OCTREE_PORTS[port_id]["commander"],
            "domain": OCTREE_PORTS[port_id]["domain"],
            "active": len(hbs) > 0,
            "heartbeats": len(hbs),
            "current_model": hbs[0]["model"] if hbs else None,
            "daemon_version": hbs[0]["daemon_version"] if hbs else None,
            "daemon_name": hbs[0]["daemon_name"] if hbs else None,
            "ai_success_rate": 0.0,
            "fallback_rate": 0.0,
            "latest_cycle": hbs[0]["cycle"] if hbs else 0,
        }

        if hbs:
            latest = hbs[0]
            calls = max(latest["ai_calls"], 1)
            port_info["ai_success_rate"] = round(
                1.0 - latest["ai_failures"] / calls, 3
            )
            port_info["fallback_rate"] = round(
                latest["fallback_uses"] / calls, 3
            )
            # Check for missing enriched signals
            missing = []
            for field in ["inference_ms", "tok_s_actual", "temperature", "vram_mb"]:
                if latest.get(field) is None:
                    missing.append(field)
            if missing:
                scan["signal_gaps"].append({
                    "port": port_id,
                    "missing": missing,
                    "severity": "HIGH" if len(missing) >= 3 else "MEDIUM",
                })
        else:
            scan["signal_gaps"].append({
                "port": port_id,
                "missing": ["ALL — no heartbeat in window"],
                "severity": "CRITICAL",
            })

        scan["ports"][port_id] = port_info

    # Serialize sets for JSON
    for obs in scan["models_seen"].values():
        obs["ports"] = sorted(obs["ports"])

    # Fleet health summary
    active = sum(1 for p in scan["ports"].values() if p["active"])
    total_fb = sum(
        p["fallback_rate"]
        for p in scan["ports"].values()
        if p["active"]
    )
    active_ct = max(active, 1)
    scan["fleet_health"] = {
        "active_ports": active,
        "total_ports": 8,
        "coverage": round(active / 8, 2),
        "avg_fallback_rate": round(total_fb / active_ct, 3),
        "signal_gaps": len(scan["signal_gaps"]),
        "critical_gaps": sum(
            1 for g in scan["signal_gaps"] if g["severity"] == "CRITICAL"
        ),
    }

    return scan


def _infer_port(event_type: str) -> str:
    """Infer port from event type string."""
    et = event_type.lower()
    if "singer" in et:
        return "P4"
    if "dancer" in et:
        return "P5"
    if "loop" in et:
        return "P4+P5"
    if "kraken" in et or "devourer" in et:
        return "P6"
    if "metafaculty" in et or "foresight" in et or "summoner" in et:
        return "P7"
    if "scry" in et or "true_seeing" in et or "watcher" in et:
        return "P0"
    if "chimera" in et or "shaper" in et:
        return "P2"
    if "weaver" in et:
        return "P1"
    if "hydra" in et or "injector" in et:
        return "P3"
    return "??"


# ═══════════════════════════════════════════════════════════════
# § 6  FITNESS EVALUATOR — Intelligence / Speed / Cost
# ═══════════════════════════════════════════════════════════════
#
# Three fitness dimensions — the MAP-ELITES axes:
#   intelligence  (maximize) — accuracy / quality of outputs
#   speed         (maximize) — tokens per second throughput
#   cost          (minimize) — VRAM GB consumed (inverted to higher=better)
#
# Each dimension is normalized to [0, 1] where 1 = best.

def compute_model_fitness(model_name: str,
                          port_data: Optional[dict] = None) -> dict:
    """Compute 3D fitness vector for a model.

    Args:
        model_name:  Key into MODEL_CATALOG
        port_data:   Optional live port observation (success rates, etc.)

    Returns:
        {intelligence, speed, cost, composite, tier, banned?}
    """
    cat = MODEL_CATALOG.get(model_name, {})

    if cat.get("banned"):
        return {
            "intelligence": 0, "speed": 0, "cost": 0, "composite": 0,
            "banned": True, "ban_reason": cat.get("ban_reason", ""),
        }

    # ── Intelligence (0-1) ──
    intel = 0.0
    if cat.get("chimera_score") is not None:
        intel = cat["chimera_score"]
    elif cat.get("harness_pass") is not None:
        intel = cat["harness_pass"] * 0.85
    elif cat.get("params_b", 0) > 0:
        # Proxy: log-scale params → ~1.2B=0.15, ~7B=0.42, ~14B=0.57, ~30B=0.73
        intel = min(0.90, 0.15 * math.log2(max(cat["params_b"], 1)))
    elif cat.get("tier") == "api":
        # Conservative estimate for untested API models
        intel = 0.70 if "pro" in model_name else 0.55

    # Penalize by live failure rate
    if port_data and port_data.get("ai_success_rate", 1.0) < 1.0:
        intel *= port_data["ai_success_rate"]

    # ── Speed (0-1) ──
    tok_s = cat.get("tok_s_est", 5.0)
    if port_data and port_data.get("tok_s_actual"):
        tok_s = port_data["tok_s_actual"]  # Prefer measured
    speed = min(1.0, tok_s / 200.0)

    # ── Cost (0-1, higher = cheaper = better) ──
    if cat.get("tier") == "api":
        cost = 0.95  # Free tier = essentially zero VRAM cost
    else:
        size = cat.get("size_gb", 10.0)
        cost = max(0.05, 1.0 - (size / 20.0))

    composite = round(
        intel * 0.50 + speed * 0.30 + cost * 0.20,
        3,
    )

    return {
        "intelligence": round(intel, 3),
        "speed": round(speed, 3),
        "cost": round(cost, 3),
        "composite": composite,
        "tier": cat.get("tier", "unknown"),
    }


# ═══════════════════════════════════════════════════════════════
# § 7  PARETO FRONTIER — Non-Dominated Solutions
# ═══════════════════════════════════════════════════════════════

def compute_pareto_frontier(fitness_map: dict[str, dict]) -> list[str]:
    """Compute non-dominated solutions from a fitness map.

    A model A dominates B iff A >= B on all 3 dims and A > B on at least 1.
    Returns the Pareto frontier: models that are NOT dominated by any other.
    """
    models = [m for m in fitness_map if not fitness_map[m].get("banned")]
    dominated: set[str] = set()

    for i, m1 in enumerate(models):
        if m1 in dominated:
            continue
        f1 = fitness_map[m1]
        for j, m2 in enumerate(models):
            if i == j or m2 in dominated:
                continue
            f2 = fitness_map[m2]
            # Does m1 dominate m2?
            if (f1["intelligence"] >= f2["intelligence"]
                    and f1["speed"] >= f2["speed"]
                    and f1["cost"] >= f2["cost"]
                    and (f1["intelligence"] > f2["intelligence"]
                         or f1["speed"] > f2["speed"]
                         or f1["cost"] > f2["cost"])):
                dominated.add(m2)

    frontier = [m for m in models if m not in dominated]
    return sorted(frontier, key=lambda m: -fitness_map[m]["composite"])


# ═══════════════════════════════════════════════════════════════
# § 8  MAP-ELITES ARCHIVE — Quality-Diversity Grid
# ═══════════════════════════════════════════════════════════════
#
# Grid structure: 8 ports × 3 fitness dimensions = 24 cells.
# Each cell stores the BEST model for that (port, dimension) pair.
# This is the "exemplar archive" that drives the spike factory.

def build_map_elites_archive(scan: dict) -> dict:
    """Build the 8×3 MAP-ELITES archive.

    Each cell = {model, score, size_gb, tok_s, tier}
    """
    archive: dict[str, dict] = {}

    for port_id in sorted(OCTREE_PORTS.keys()):
        port_data = scan["ports"].get(port_id, {})
        archive[port_id] = {}

        # Score every eligible model
        scores: dict[str, dict] = {}
        for model_name, cat in MODEL_CATALOG.items():
            if cat.get("banned"):
                continue
            fitness = compute_model_fitness(
                model_name,
                port_data if port_data.get("active") else None,
            )
            scores[model_name] = fitness

        # Find best per dimension
        for dim in ("intelligence", "speed", "cost"):
            best_model = None
            best_score = -1.0
            for model_name, fitness in scores.items():
                if fitness[dim] > best_score:
                    best_score = fitness[dim]
                    best_model = model_name

            cat = MODEL_CATALOG.get(best_model, {}) if best_model else {}
            archive[port_id][f"apex_{dim}"] = {
                "model": best_model,
                "score": round(best_score, 3),
                "size_gb": cat.get("size_gb", 0),
                "tok_s_est": cat.get("tok_s_est", 0),
                "tier": cat.get("tier", "?"),
            }

    return archive


# ═══════════════════════════════════════════════════════════════
# § 9  ACO PHEROMONE MANAGER (Dorigo 1996)
# ═══════════════════════════════════════════════════════════════
#
# Pheromone τ(model, port) encodes historical fitness.
#   Evaporation:   τ *= (1 - ρ)^Δhours each cycle
#   Reinforcement: τ += fitness_score when model succeeds
#   Selection:     P(model|port) ∝ τ^α  ×  η^β
#                  η = heuristic estimate (catalog fitness)
#

class PheromoneTrails:
    """ACO pheromone trail manager with evaporation and bounds."""

    def __init__(self):
        self.trails: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(lambda: ACO_MIN_PHEROMONE)
        )
        self.last_update = time.time()

    def evaporate(self):
        """Apply time-based evaporation decay."""
        now = time.time()
        hours = (now - self.last_update) / 3600.0
        if hours < 0.001:
            return
        decay_factor = (1.0 - ACO_RHO) ** hours

        for port in list(self.trails.keys()):
            for model in list(self.trails[port].keys()):
                self.trails[port][model] = max(
                    ACO_MIN_PHEROMONE,
                    min(ACO_MAX_PHEROMONE,
                        self.trails[port][model] * decay_factor),
                )
        self.last_update = now

    def reinforce(self, port: str, model: str, fitness: float):
        """Deposit pheromone proportional to observed fitness."""
        self.trails[port][model] = min(
            ACO_MAX_PHEROMONE,
            self.trails[port][model] + fitness,
        )

    def get_selection_probs(self, port: str) -> dict[str, float]:
        """Compute selection probability per model for a port."""
        probs: dict[str, float] = {}
        total = 0.0

        for model_name, cat in MODEL_CATALOG.items():
            if cat.get("banned"):
                continue
            tau = self.trails[port].get(model_name, ACO_MIN_PHEROMONE)
            eta = compute_model_fitness(model_name)["composite"]
            score = (tau ** ACO_ALPHA) * (max(eta, 0.01) ** ACO_BETA)
            probs[model_name] = score
            total += score

        if total > 0:
            for m in probs:
                probs[m] = round(probs[m] / total, 4)

        return dict(sorted(probs.items(), key=lambda x: -x[1]))

    def to_dict(self) -> dict:
        """Serialize non-trivial trails for CloudEvent emission."""
        out: dict[str, dict] = {}
        for port in sorted(self.trails.keys()):
            entries = {
                m: round(v, 4)
                for m, v in sorted(
                    self.trails[port].items(), key=lambda x: -x[1]
                )
                if v > ACO_MIN_PHEROMONE * 1.5
            }
            if entries:
                out[port] = entries
        return out

    @classmethod
    def from_stigmergy(cls, conn: sqlite3.Connection) -> "PheromoneTrails":
        """Reconstruct trails from the latest pheromone event in SSOT."""
        pt = cls()
        row = conn.execute(
            """SELECT data_json FROM stigmergy_events
               WHERE event_type = ?
               ORDER BY id DESC LIMIT 1""",
            (EVT_PHEROMONE,),
        ).fetchone()

        if row:
            try:
                envelope = json.loads(row["data_json"])
                data = envelope.get("data", envelope)
                for port, models in data.get("trails", {}).items():
                    for model, val in models.items():
                        pt.trails[port][model] = float(val)
                pt.last_update = time.time()
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        return pt


# ═══════════════════════════════════════════════════════════════
# § 10  SSO VIBRATION PROPAGATOR (James-Yu 2013)
# ═══════════════════════════════════════════════════════════════
#
# Social Spider Optimization: vibrations on the web encode fitness.
#   High vibration = important discovery (new Pareto member).
#   Damping = vibration weakens with topological distance.
#   The web IS the stigmergy table — CloudEvents ARE vibrations.

def compute_vibration(scan: dict, archive: dict,
                      prev_archive: Optional[dict]) -> dict:
    """Compute SSO vibration intensities after a scan.

    Three sources (James-Yu SSO):
      1. Global best changed — new Pareto-optimal config discovered
      2. Local improvement — a port's apex exemplar improved
      3. Exploration noise — scales inversely with fleet coverage
    """
    vibration: dict[str, Any] = {
        "global_best_changed": False,
        "improvements": [],
        "exploration_noise": 0.0,
        "total_amplitude": 0.0,
    }

    if not prev_archive:
        # First scan — max exploration vibration
        vibration["exploration_noise"] = 1.0
        vibration["total_amplitude"] = 1.0
        return vibration

    # Check each cell for improvement
    for port_id in sorted(OCTREE_PORTS.keys()):
        for dim in ("apex_intelligence", "apex_speed", "apex_cost"):
            curr = archive.get(port_id, {}).get(dim, {})
            prev = prev_archive.get(port_id, {}).get(dim, {})
            if curr.get("model") != prev.get("model"):
                delta = curr.get("score", 0) - prev.get("score", 0)
                if delta > 0:
                    vibration["improvements"].append({
                        "port": port_id,
                        "dim": dim,
                        "old": prev.get("model"),
                        "new": curr.get("model"),
                        "delta": round(delta, 3),
                    })
                    vibration["global_best_changed"] = True

    improvement_sum = sum(i["delta"] for i in vibration["improvements"])
    vibration["exploration_noise"] = round(
        0.05 + 0.10 * (1.0 - scan["fleet_health"]["coverage"]),
        3,
    )
    vibration["total_amplitude"] = min(
        SSO_MAX_AMPLITUDE,
        round(improvement_sum + vibration["exploration_noise"], 3),
    )

    return vibration


# ═══════════════════════════════════════════════════════════════
# § 11  STEERING DIRECTIVE GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_steering_directives(archive: dict, scan: dict,
                                 pheromones: PheromoneTrails) -> list[dict]:
    """Generate per-port steering directives.

    Each directive tells a port commander:
      - What model to use for each fitness objective
      - ACO-weighted top-3 model suggestions
      - Whether to HOLD, SWITCH, ACTIVATE, or INVESTIGATE
      - Confidence level [0, 1]
    """
    directives: list[dict] = []

    for port_id in sorted(OCTREE_PORTS.keys()):
        port_info = scan["ports"].get(port_id, {})
        port_archive = archive.get(port_id, {})
        aco_probs = pheromones.get_selection_probs(port_id)

        directive: dict[str, Any] = {
            "port": port_id,
            "commander": OCTREE_PORTS[port_id]["commander"],
            "current_model": port_info.get("current_model"),
            "recommended": {
                "apex_intelligence": port_archive.get("apex_intelligence", {}).get("model"),
                "apex_speed": port_archive.get("apex_speed", {}).get("model"),
                "apex_cost": port_archive.get("apex_cost", {}).get("model"),
            },
            "aco_top3": dict(list(aco_probs.items())[:3]),
            "action": "HOLD",
            "confidence": 0.0,
        }

        current = port_info.get("current_model")
        if not port_info.get("active"):
            directive["action"] = "ACTIVATE"
            directive["confidence"] = 0.90
        elif port_info.get("fallback_rate", 0) >= 1.0:
            # 100% fallback — model is NOT generating, only deterministic
            rec = port_archive.get("apex_intelligence", {}).get("model")
            if rec and rec != current:
                directive["action"] = f"SWITCH_TO:{rec}"
                directive["confidence"] = 0.80
            else:
                directive["action"] = "INVESTIGATE"
                directive["confidence"] = 0.50
        else:
            # Check if ACO strongly recommends a different model
            top_aco = list(aco_probs.keys())[0] if aco_probs else None
            if (top_aco and top_aco != current
                    and aco_probs.get(top_aco, 0) > 0.30):
                directive["action"] = f"ACO_SUGGESTS:{top_aco}"
                directive["confidence"] = round(aco_probs[top_aco], 2)

        directives.append(directive)

    return directives


# ═══════════════════════════════════════════════════════════════
# § 12  METAFACULTY CORE — The Omniscient Daemon
# ═══════════════════════════════════════════════════════════════

class Metafaculty:
    """P7 Spider Sovereign METAFACULTY — the 9th-level Seer capstone.

    Sees all 8 ports. Computes Pareto frontiers. Maintains MAP-ELITES
    quality-diversity archive. Steers model selection via ACO pheromone
    trails and SSO vibration propagation.

    This is the crown jewel of P7 NAVIGATE.
    """

    def __init__(self, dry_run: bool = False,
                 interval: int = DEFAULT_INTERVAL_S):
        self.dry_run = dry_run
        self.interval = interval
        self.cycle = 0
        self.prev_archive: Optional[dict] = None
        self.pheromones: Optional[PheromoneTrails] = None
        self._running = True
        self._started_at = time.monotonic()

    def run_cycle(self) -> dict:
        """Execute one METAFACULTY optimization cycle.

        The full loop:
          SCAN → FITNESS → PARETO → ARCHIVE → VIBRATION → ACO → STEER → HEARTBEAT
        """
        self.cycle += 1
        t0 = time.monotonic()

        report: dict[str, Any] = {
            "cycle": self.cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "spell": SPELL_NAME,
            "level": SPELL_LEVEL,
            "errors": [],
        }

        conn_ro = None
        conn_rw = None

        try:
            conn_ro = get_db_ro()
            if not self.dry_run:
                conn_rw = get_db_rw()

            # ── 1. OMNISCIENT SCAN ──
            scan = omniscient_scan(conn_ro)
            report["scan"] = {
                "active_ports": scan["fleet_health"]["active_ports"],
                "coverage": scan["fleet_health"]["coverage"],
                "signal_gaps": scan["fleet_health"]["signal_gaps"],
                "models_seen": len(scan["models_seen"]),
                "avg_fallback_rate": scan["fleet_health"]["avg_fallback_rate"],
            }

            if conn_rw:
                write_event(conn_rw, EVT_SCAN,
                    f"SCAN:cycle_{self.cycle}:coverage_{scan['fleet_health']['coverage']}",
                    {
                        "spell": SPELL_NAME,
                        "cycle": self.cycle,
                        "fleet_health": scan["fleet_health"],
                        "signal_gaps": scan["signal_gaps"],
                        "port_summary": {
                            p: {
                                "active": d["active"],
                                "model": d["current_model"],
                                "success_rate": d["ai_success_rate"],
                                "fallback_rate": d["fallback_rate"],
                            }
                            for p, d in scan["ports"].items()
                        },
                    })

            # ── 2. PHEROMONE INITIALIZATION ──
            if self.pheromones is None:
                self.pheromones = PheromoneTrails.from_stigmergy(conn_ro)

            # ── 3. FITNESS EVALUATION ──
            fitness_map: dict[str, dict] = {}
            for model_name in MODEL_CATALOG:
                fitness_map[model_name] = compute_model_fitness(model_name)
            report["fitness_count"] = len(fitness_map)

            # ── 4. PARETO FRONTIER ──
            frontier = compute_pareto_frontier(fitness_map)
            report["pareto_frontier"] = frontier
            report["pareto_size"] = len(frontier)

            if conn_rw:
                write_event(conn_rw, EVT_PARETO,
                    f"PARETO:cycle_{self.cycle}:frontier_{len(frontier)}",
                    {
                        "spell": SPELL_NAME,
                        "cycle": self.cycle,
                        "frontier": frontier,
                        "frontier_fitness": {m: fitness_map[m] for m in frontier},
                        "dominated_count": len(fitness_map) - len(frontier) - sum(
                            1 for m in fitness_map if fitness_map[m].get("banned")
                        ),
                    })

            # ── 5. MAP-ELITES ARCHIVE ──
            archive = build_map_elites_archive(scan)
            filled = sum(
                1 for p in archive.values()
                for c in p.values()
                if c.get("model")
            )
            report["archive_cells"] = filled

            if conn_rw:
                arch_serial = {}
                for pid, dims in archive.items():
                    arch_serial[pid] = {
                        d: {"model": c.get("model"), "score": c.get("score")}
                        for d, c in dims.items()
                    }
                write_event(conn_rw, EVT_ARCHIVE,
                    f"ARCHIVE:cycle_{self.cycle}:cells_{filled}",
                    {
                        "spell": SPELL_NAME,
                        "cycle": self.cycle,
                        "archive": arch_serial,
                        "total_cells_filled": filled,
                        "total_cells_possible": 24,
                    })

            # ── 6. SSO VIBRATION ──
            vibration = compute_vibration(scan, archive, self.prev_archive)
            report["vibration"] = vibration["total_amplitude"]
            report["improvements"] = len(vibration["improvements"])

            if vibration["total_amplitude"] > 0.1 and conn_rw:
                write_event(conn_rw, EVT_VIBRATION,
                    f"VIBRATION:amp_{vibration['total_amplitude']:.2f}",
                    {
                        "spell": SPELL_NAME,
                        "cycle": self.cycle,
                        "vibration": vibration,
                    })

            # ── 7. ACO PHEROMONE UPDATE ──
            self.pheromones.evaporate()

            for port_id, port_data in scan["ports"].items():
                if port_data["active"] and port_data["current_model"]:
                    model = port_data["current_model"]
                    fit = compute_model_fitness(model, port_data)
                    self.pheromones.reinforce(port_id, model, fit["composite"])

            if conn_rw:
                write_event(conn_rw, EVT_PHEROMONE,
                    f"PHEROMONE:cycle_{self.cycle}",
                    {
                        "spell": SPELL_NAME,
                        "cycle": self.cycle,
                        "trails": self.pheromones.to_dict(),
                        "evaporation_rate": ACO_RHO,
                        "alpha": ACO_ALPHA,
                        "beta": ACO_BETA,
                    })

            # ── 8. STEERING DIRECTIVES ──
            directives = generate_steering_directives(
                archive, scan, self.pheromones,
            )
            active_dirs = [d for d in directives if d["action"] != "HOLD"]
            report["directives"] = directives
            report["active_directives"] = len(active_dirs)

            if active_dirs and conn_rw:
                write_event(conn_rw, EVT_STEERING,
                    f"STEERING:cycle_{self.cycle}:actions_{len(active_dirs)}",
                    {
                        "spell": SPELL_NAME,
                        "cycle": self.cycle,
                        "directives": directives,
                        "active_count": len(active_dirs),
                    })

            # ── 9. HEARTBEAT ──
            hb = {
                "daemon_name": DAEMON_NAME,
                "daemon_version": DAEMON_VERSION,
                "daemon_port": DAEMON_PORT,
                "spell": SPELL_NAME,
                "cycle": self.cycle,
                "fleet_coverage": scan["fleet_health"]["coverage"],
                "pareto_size": len(frontier),
                "archive_cells": filled,
                "vibration": vibration["total_amplitude"],
                "active_directives": len(active_dirs),
                "signal_gaps": scan["fleet_health"]["signal_gaps"],
                "avg_fallback_rate": scan["fleet_health"]["avg_fallback_rate"],
                "uptime_s": round(time.monotonic() - self._started_at, 1),
                "core_thesis": CORE_THESIS,
                "power_quote": POWER_QUOTE,
            }

            if conn_rw:
                write_event(conn_rw, EVT_HEARTBEAT,
                    f"HEARTBEAT:cycle_{self.cycle}", hb)

            # Save for next cycle's vibration diff
            self.prev_archive = archive
            report["archive"] = archive

        except Exception as e:
            msg = f"METAFACULTY cycle {self.cycle} error: {e}"
            report["errors"].append(msg)
            print(f"  [ERROR] {msg}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            try:
                if conn_rw:
                    write_event(conn_rw, EVT_ERROR,
                        f"ERROR:cycle_{self.cycle}",
                        {"error": msg, "traceback": traceback.format_exc()})
            except Exception:
                pass
        finally:
            if conn_ro:
                conn_ro.close()
            if conn_rw:
                conn_rw.close()

        report["duration_ms"] = round((time.monotonic() - t0) * 1000, 1)
        return report

    def daemon_loop(self):
        """Run continuous METAFACULTY optimization cycles."""
        W = 56
        print(f"╔{'═' * W}╗")
        print(f"║  {SPELL_NAME} — {SPELL_LEVEL:<(W - 6)}║")
        print(f"║  \"{POWER_QUOTE}\"{' ' * (W - 4 - len(POWER_QUOTE) - 2)}║")
        print(f"║  {DAEMON_NAME} v{DAEMON_VERSION} │ {DAEMON_PORT} NAVIGATE{' ' * (W - 32)}║")
        print(f"║  Interval: {self.interval}s │ Dry-run: {self.dry_run}{' ' * (W - 36)}║")
        print(f"╚{'═' * W}╝")
        print()

        def _sig(signum, frame):
            print(f"\n  [{SPELL_NAME}] Signal {signum}. Graceful shutdown...")
            self._running = False

        signal_module.signal(signal_module.SIGINT, _sig)
        signal_module.signal(signal_module.SIGTERM, _sig)

        while self._running:
            print(f"  ─── {SPELL_NAME} Cycle {self.cycle + 1} ───")
            report = self.run_cycle()
            _print_cycle_report(report)

            if not self._running:
                break

            print(f"  Next cycle in {self.interval}s...\n")
            for _ in range(self.interval * 10):
                if not self._running:
                    break
                time.sleep(0.1)

        print(f"\n  [{SPELL_NAME}] Shutdown. {self.cycle} cycles completed.")


# ═══════════════════════════════════════════════════════════════
# § 13  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════

def _print_cycle_report(report: dict):
    """Print concise cycle summary."""
    scan = report.get("scan", {})
    print(f"  Fleet: {scan.get('active_ports', '?')}/8 active | "
          f"Coverage: {scan.get('coverage', '?')} | "
          f"Gaps: {scan.get('signal_gaps', '?')} | "
          f"Models: {scan.get('models_seen', '?')}")
    print(f"  Pareto: {report.get('pareto_size', '?')} frontier | "
          f"Archive: {report.get('archive_cells', '?')}/24 cells | "
          f"Vibration: {report.get('vibration', 0):.2f}")

    active_dirs = [
        d for d in report.get("directives", [])
        if d["action"] != "HOLD"
    ]
    if active_dirs:
        print(f"  Steering ({len(active_dirs)} actions):")
        for d in active_dirs:
            print(f"    {d['port']} {d['commander']}: "
                  f"{d['action']} (conf={d['confidence']:.2f})")

    if report.get("errors"):
        for e in report["errors"]:
            print(f"  [ERROR] {e}")

    print(f"  Time: {report.get('duration_ms', '?')}ms")
    print()


def cmd_status():
    """Show METAFACULTY status from SSOT."""
    conn = get_db_ro()
    try:
        print(f"╔══════════════════════════════════════════════════════╗")
        print(f"║  {SPELL_NAME} — STATUS REPORT                       ║")
        print(f"╚══════════════════════════════════════════════════════╝")

        # Latest heartbeat
        row = conn.execute(
            """SELECT data_json FROM stigmergy_events
               WHERE event_type = ? ORDER BY id DESC LIMIT 1""",
            (EVT_HEARTBEAT,),
        ).fetchone()

        if row:
            data = json.loads(row["data_json"]).get("data", {})
            print(f"\n  Last heartbeat:")
            print(f"    Cycle:          {data.get('cycle', '?')}")
            print(f"    Fleet coverage: {data.get('fleet_coverage', '?')}")
            print(f"    Pareto size:    {data.get('pareto_size', '?')}")
            print(f"    Archive cells:  {data.get('archive_cells', '?')}/24")
            print(f"    Vibration:      {data.get('vibration', '?')}")
            print(f"    Active steer:   {data.get('active_directives', '?')}")
            print(f"    Signal gaps:    {data.get('signal_gaps', '?')}")
            print(f"    Fallback rate:  {data.get('avg_fallback_rate', '?')}")
            print(f"    Uptime:         {data.get('uptime_s', '?')}s")
        else:
            print("\n  No METAFACULTY heartbeats found. Run --scan first.")

        # Event counts
        counts = conn.execute(
            """SELECT event_type, COUNT(*) as cnt
               FROM stigmergy_events
               WHERE event_type LIKE '%metafaculty%'
               GROUP BY event_type ORDER BY cnt DESC""",
        ).fetchall()
        if counts:
            print(f"\n  Event history:")
            for r in counts:
                print(f"    {r['event_type']}: {r['cnt']}")

    finally:
        conn.close()


def cmd_archive():
    """Show full MAP-ELITES archive with details."""
    conn = get_db_ro()
    try:
        scan = omniscient_scan(conn)
        archive = build_map_elites_archive(scan)
    finally:
        conn.close()

    print(f"╔═══════════════════════════════════════════════════════════════════════╗")
    print(f"║  METAFACULTY MAP-ELITES ARCHIVE — 8 Ports × 3 Fitness Dimensions    ║")
    print(f"║  Quality-Diversity Grid: apex_intelligence, apex_speed, apex_cost    ║")
    print(f"╚═══════════════════════════════════════════════════════════════════════╝")
    print()

    for port_id in sorted(OCTREE_PORTS.keys()):
        info = OCTREE_PORTS[port_id]
        port_data = scan["ports"].get(port_id, {})

        # Port header
        status = "ACTIVE" if port_data.get("active") else "INACTIVE"
        model = port_data.get("current_model", "—")
        sr = port_data.get("ai_success_rate", 0)
        fb = port_data.get("fallback_rate", 0)
        print(f"  ═══ {port_id} {info['word']} — {info['commander']} ═══")
        if port_data.get("active"):
            print(f"  Status: {status} | Model: {model} | "
                  f"Success: {sr*100:.0f}% | Fallback: {fb*100:.0f}%")
        else:
            print(f"  Status: {status} — no heartbeats in {SCAN_WINDOW_MINUTES}min")

        # Archive cells
        cells = archive.get(port_id, {})
        for dim_name, cell in sorted(cells.items()):
            m = cell.get("model", "—")
            score = cell.get("score", 0)
            size = cell.get("size_gb", "?")
            tok = cell.get("tok_s_est", "?")
            tier = cell.get("tier", "?")
            print(f"    {dim_name:<20} → {m:<25} "
                  f"score={score:.3f} ({size}GB, ~{tok}tok/s, {tier})")

        # Signal gaps
        gaps = [g for g in scan["signal_gaps"] if g["port"] == port_id]
        for g in gaps:
            severity = g["severity"]
            fields = ", ".join(g["missing"])
            print(f"    ⚠ Signal gap [{severity}]: {fields}")
        print()

    # Summary
    filled = sum(
        1 for p in archive.values() for c in p.values() if c.get("model")
    )
    print(f"  Archive: {filled}/24 cells filled | "
          f"Fleet: {scan['fleet_health']['active_ports']}/8 active | "
          f"Signal gaps: {len(scan['signal_gaps'])}")


def cmd_pareto():
    """Show Pareto frontier analysis."""
    fitness_map = {
        m: compute_model_fitness(m)
        for m in MODEL_CATALOG
    }
    frontier = compute_pareto_frontier(fitness_map)

    print(f"╔═══════════════════════════════════════════════════════════════════╗")
    print(f"║  PARETO FRONTIER — Non-Dominated Model Configurations           ║")
    print(f"║  Fitness: intelligence (50%) + speed (30%) + cost (20%)          ║")
    print(f"╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"  {'Model':<25} {'Intel':>6} {'Speed':>6} {'Cost':>6} "
          f"{'Comp':>6} {'Tier':<6} {'Pareto':>7}")
    print(f"  {'─' * 67}")

    for m in sorted(fitness_map.keys(),
                    key=lambda x: -fitness_map[x]["composite"]):
        f = fitness_map[m]
        if f.get("banned"):
            marker = "BANNED"
        elif m in frontier:
            marker = "  ★"
        else:
            marker = ""
        cat = MODEL_CATALOG[m]
        print(f"  {m:<25} {f['intelligence']:>5.3f} {f['speed']:>5.3f} "
              f"{f['cost']:>5.3f} {f['composite']:>5.3f} "
              f"{cat.get('tier', '?'):<6} {marker:>7}")

    print()
    print(f"  Frontier: {len(frontier)} non-dominated models")
    print(f"  Total:    {len([m for m in fitness_map if not fitness_map[m].get('banned')])} "
          f"eligible | 1 banned")


def cmd_signals():
    """Show enriched signal gap analysis."""
    print(f"╔═══════════════════════════════════════════════════════════════════╗")
    print(f"║  ENRICHED SIGNAL SCHEMA — Gap Analysis                          ║")
    print(f"║  Fields every daemon CloudEvent SHOULD carry for swarm coord.   ║")
    print(f"╚═══════════════════════════════════════════════════════════════════╝")
    print()

    # Required fields
    print(f"  REQUIRED FIELDS:")
    print(f"  {'Field':<20} {'Type':<8} {'Req':>4}  Description")
    print(f"  {'─' * 72}")
    for field, spec in ENRICHED_SIGNAL_FIELDS.items():
        if spec["required"]:
            print(f"  {field:<20} {spec['type']:<8} {'YES':>4}  {spec['desc']}")
    print()

    # Optional fields
    print(f"  OPTIONAL FIELDS:")
    print(f"  {'─' * 72}")
    for field, spec in ENRICHED_SIGNAL_FIELDS.items():
        if not spec["required"]:
            print(f"  {field:<20} {spec['type']:<8} {'opt':>4}  {spec['desc']}")
    print()

    # Current coverage
    print(f"  CURRENT DAEMON COVERAGE:")
    print(f"  {'Daemon':<15}", end="")
    req_fields = [f for f, s in ENRICHED_SIGNAL_FIELDS.items() if s["required"]]
    for f in req_fields:
        short = f.replace("model_", "m_").replace("_actual", "")
        print(f" {short:>10}", end="")
    print()
    print(f"  {'─' * (15 + 10 * len(req_fields))}")

    for daemon, coverage in CURRENT_SIGNAL_COVERAGE.items():
        print(f"  {daemon:<15}", end="")
        for f in req_fields:
            has = coverage.get(f, False)
            sym = "  ✓" if has else "  ✗"
            print(f" {sym:>10}", end="")
        print()

    # Score
    total_cells = len(CURRENT_SIGNAL_COVERAGE) * len(req_fields)
    filled = sum(
        1 for d in CURRENT_SIGNAL_COVERAGE.values()
        for f in req_fields
        if d.get(f, False)
    )
    pct = round(filled / max(total_cells, 1) * 100, 0)
    print()
    print(f"  Signal coverage: {filled}/{total_cells} cells ({pct}%)")
    print(f"  Action: Upgrade daemon CloudEvent payloads to include missing fields")


# ═══════════════════════════════════════════════════════════════
# § 14  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=(
            f"{DAEMON_NAME} v{DAEMON_VERSION} — {SPELL_NAME} ({SPELL_LEVEL})\n"
            f"\"{POWER_QUOTE}\"\n\n"
            f"P7 NAVIGATE apex intelligence meta-heuristic optimizer.\n"
            f"Omniscient scan → Pareto frontier → MAP-ELITES archive →\n"
            f"ACO pheromones → SSO vibration → Steering directives."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scan", action="store_true",
                      help="One-shot: scan + optimize + emit steering")
    mode.add_argument("--daemon", action="store_true",
                      help="Continuous optimization cycles")
    mode.add_argument("--status", action="store_true",
                      help="Current METAFACULTY state from SSOT")
    mode.add_argument("--archive", action="store_true",
                      help="Full MAP-ELITES archive detail")
    mode.add_argument("--pareto", action="store_true",
                      help="Pareto frontier analysis")
    mode.add_argument("--signals", action="store_true",
                      help="Enriched signal gap analysis")

    parser.add_argument("--dry-run", action="store_true",
                        help="No SSOT writes")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_S,
                        help=f"Daemon cycle interval (default: {DEFAULT_INTERVAL_S}s)")
    parser.add_argument("--json", action="store_true",
                        help="JSON output (for --scan)")

    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.archive:
        cmd_archive()
    elif args.pareto:
        cmd_pareto()
    elif args.signals:
        cmd_signals()
    elif args.scan:
        mf = Metafaculty(dry_run=args.dry_run)
        report = mf.run_cycle()
        if args.json:
            # Clean archive for serialization
            if "archive" in report:
                for dims in report["archive"].values():
                    for cell in dims.values():
                        cell.pop("catalog", None)
            print(json.dumps(report, indent=2, default=str))
        else:
            _print_cycle_report(report)
    elif args.daemon:
        mf = Metafaculty(dry_run=args.dry_run, interval=args.interval)
        mf.daemon_loop()
    else:
        parser.print_help()
        print()
        print("  Quick start:")
        print(f"    python {Path(__file__).name} --pareto     # See model fitness landscape")
        print(f"    python {Path(__file__).name} --archive    # See MAP-ELITES grid")
        print(f"    python {Path(__file__).name} --signals    # See signal gap analysis")
        print(f"    python {Path(__file__).name} --scan       # Run one optimization cycle")
        print(f"    python {Path(__file__).name} --daemon     # Continuous optimization")


if __name__ == "__main__":
    main()
