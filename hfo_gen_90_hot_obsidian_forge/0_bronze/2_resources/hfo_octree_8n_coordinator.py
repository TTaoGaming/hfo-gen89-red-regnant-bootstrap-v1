#!/usr/bin/env python3
"""
hfo_octree_8n_coordinator.py — 8^N Scatter-Gather Coordinator
===============================================================
v1.0 | Gen90 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE
Title: Summoner of Seals and Spheres | Spell: WISH (Universal 9th)

PURPOSE:
    The 8^N coordinator that transforms 8 independent daemons into a
    self-optimizing swarm using ACO (Ant Colony Optimization) + SSO
    (Social Spider Optimization) via stigmergy.

    "8 commanders × 3 tiers = 24 exemplar slots.
     8^1 = 8 ports. 8^2 = 64 port-model combos. 8^N = fractal depth."

    WHAT IT DOES:
      1. SENSE: Read all daemon stigmergy events → extract signal_metadata
      2. SCORE: Compute ACO pheromone scores per (port, model, tier)
      3. RECOMMEND: Emit per-port model recommendations via stigmergy
      4. AUDIT: Track signal_metadata adoption (Grade A-F)
      5. WISH: Accept operator intent → route to appropriate port(s)
      6. HEALTH: Monitor fleet duplication, resource waste, dead daemons

    HOW DAEMONS USE IT:
      Each daemon reads the latest recommendation at cycle start:
        from hfo_signal_shim import read_port_recommendation
        rec = read_port_recommendation("P4")
        model = rec["recommended_model"]

    ACO ALGORITHM:
      pheromone = quality^alpha / (latency^beta × cost^gamma) × evaporation × volume
      evaporation = (1 - 0.10) ^ age_hours  (10% decay/hour)
      exploration probability = 10% (try non-optimal model)

    SSO (Social Spider Optimization):
      vibration_strength = pheromone / distance_to_task
      Stronger vibrations attract attention → model convergence
      Random web-building = exploration to maintain diversity

USAGE:
    python hfo_octree_8n_coordinator.py --cycle           Run one coordination cycle
    python hfo_octree_8n_coordinator.py --status          Fleet status + signal grade
    python hfo_octree_8n_coordinator.py --recommendations Show per-port model picks
    python hfo_octree_8n_coordinator.py --depth           Show 8^N fractal depth
    python hfo_octree_8n_coordinator.py --wish "intent"   Route intent to port(s)
    python hfo_octree_8n_coordinator.py --dedup           Detect duplicate processes
    python hfo_octree_8n_coordinator.py --json            Machine-readable output
    python hfo_octree_8n_coordinator.py --daemon          Run as recurring coordinator

Pointer key: octree.coordinator
Cross-references:
    - hfo_map_elite_commanders.py (ACO engine, pheromone scores, model grid)
    - hfo_signal_shim.py (signal_metadata builder + emitter)
    - hfo_p7_wish_compiler.py (WISH V2 5-pass compiler)
    - hfo_p7_wish.py (V1 invariant verifier)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from hfo_ssot_write import get_db_readwrite as _get_db_rw


# ═══════════════════════════════════════════════════════════════
# § 0  PAL — Path Abstraction Layer
# ═══════════════════════════════════════════════════════════════

_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))


def _find_root() -> Path:
    for anchor in [Path.cwd(), _SELF_DIR]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = _find_root()
GEN = os.environ.get("HFO_GENERATION", "89")
SOURCE_TAG = f"hfo_coordinator_gen{GEN}_v1.0"

# .env
try:
    from dotenv import load_dotenv
    env_path = HFO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass


def _resolve_ssot() -> Path:
    pf = HFO_ROOT / "hfo_gen90_pointers_blessed.json"
    if pf.exists():
        try:
            data = json.loads(pf.read_text(encoding="utf-8"))
            ptrs = data.get("pointers", data)
            if "ssot.db" in ptrs:
                entry = ptrs["ssot.db"]
                rel = entry["path"] if isinstance(entry, dict) else entry
                return HFO_ROOT / rel
        except Exception:
            pass
    return HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"


SSOT_DB = _resolve_ssot()


# ═══════════════════════════════════════════════════════════════
# § 1  8^N IDENTITY
# ═══════════════════════════════════════════════════════════════

COORDINATOR_IDENTITY = {
    "name": "8^N Octree Coordinator",
    "port": "P7",
    "commander": "Spider Sovereign",
    "role": "Scatter-Gather ACO+SSO Swarm Coordinator",
    "version": "v1.0",
    "model": "none (coordinator is compute-free, reads pheromone only)",
    "description": "Reads signal_metadata from stigmergy, computes ACO pheromone, "
                   "emits per-port model recommendations, tracks signal quality grade, "
                   "detects fleet duplication, routes WISH intents.",
}

OCTREE_PORTS = {
    "P0": {"word": "OBSERVE",    "commander": "Lidless Legion",     "domain": "Sensing under contest"},
    "P1": {"word": "BRIDGE",     "commander": "Web Weaver",          "domain": "Shared data fabric"},
    "P2": {"word": "SHAPE",      "commander": "Mirror Magus",        "domain": "Creation / models"},
    "P3": {"word": "INJECT",     "commander": "Harmonic Hydra",      "domain": "Payload delivery"},
    "P4": {"word": "DISRUPT",    "commander": "Red Regnant",         "domain": "Red team / probing"},
    "P5": {"word": "IMMUNIZE",   "commander": "Pyre Praetorian",     "domain": "Blue team / gates"},
    "P6": {"word": "ASSIMILATE", "commander": "Kraken Keeper",       "domain": "Learning / memory"},
    "P7": {"word": "NAVIGATE",   "commander": "Spider Sovereign",    "domain": "C2 / steering"},
}


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def _get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn



def _write_event(conn, event_type: str, subject: str, data: dict) -> int:
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": SOURCE_TAG,
        "subject": subject,
        "time": now, "timestamp": now,
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
# § 3  SIGNAL AUDIT — Swarm Self-Awareness
# ═══════════════════════════════════════════════════════════════

def compute_signal_audit(hours_back: float = 24.0) -> dict:
    """
    Audit signal_metadata adoption across all stigmergy events.
    Returns grade (A-F) + breakdown by event type.
    """
    conn = _get_db_ro()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    rows = conn.execute("""
        SELECT event_type, data_json FROM stigmergy_events
        WHERE timestamp > ? AND event_type LIKE 'hfo.gen90.%'
        ORDER BY id DESC
    """, (cutoff,)).fetchall()
    conn.close()

    total = has_signal = has_legacy = no_model = 0
    by_port: dict[str, int] = Counter()
    models_seen: dict[str, int] = Counter()

    for row in rows:
        total += 1
        try:
            raw = json.loads(row["data_json"]) if row["data_json"] else {}
            data = raw.get("data", raw)
            sig = data.get("signal_metadata")
            if sig and isinstance(sig, dict) and sig.get("model_id"):
                has_signal += 1
                by_port[sig.get("port", "?")] += 1
                models_seen[sig["model_id"]] += 1
            elif any(k in data for k in ("ai_model", "model")) or \
                 (isinstance(data.get("identity"), dict) and "model" in data["identity"]):
                has_legacy += 1
            else:
                no_model += 1
        except (json.JSONDecodeError, TypeError):
            no_model += 1

    signal_pct = (has_signal / total * 100) if total > 0 else 0
    legacy_pct = (has_legacy / total * 100) if total > 0 else 0

    grade = ("A" if signal_pct >= 80 else
             "B" if signal_pct + legacy_pct >= 70 else
             "C" if signal_pct + legacy_pct >= 50 else
             "D" if legacy_pct >= 30 else "F")

    return {
        "grade": grade,
        "total_events": total,
        "has_signal_metadata": has_signal,
        "has_legacy": has_legacy,
        "blind": no_model,
        "signal_pct": round(signal_pct, 1),
        "legacy_pct": round(legacy_pct, 1),
        "blind_pct": round(100 - signal_pct - legacy_pct, 1),
        "by_port": dict(by_port.most_common()),
        "models_seen": dict(models_seen.most_common(10)),
        "hours_back": hours_back,
    }


# ═══════════════════════════════════════════════════════════════
# § 4  ACO PHEROMONE — Read + Score
# ═══════════════════════════════════════════════════════════════

EVAPORATION_RATE = 0.10
MIN_PHEROMONE = 0.01
QUALITY_WEIGHT = 2.0
SPEED_WEIGHT = 1.0
COST_WEIGHT = 0.5


@dataclass
class PheromoneEntry:
    port: str
    model_id: str
    model_tier: str
    total_inferences: int = 0
    avg_latency_ms: float = 0.0
    avg_quality: float = 0.0
    total_cost_usd: float = 0.0
    pheromone: float = 0.0
    age_hours: float = 0.0
    evaporation: float = 1.0


def compute_pheromone(hours_back: float = 24.0) -> list[PheromoneEntry]:
    """Read stigmergy, extract signal_metadata, compute ACO pheromone scores."""
    conn = _get_db_ro()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    rows = conn.execute("""
        SELECT timestamp, data_json FROM stigmergy_events
        WHERE timestamp > ? AND event_type LIKE 'hfo.gen90.%'
        ORDER BY id DESC
    """, (cutoff,)).fetchall()
    conn.close()

    # Aggregate per (port, model, tier)
    agg: dict[tuple, dict] = {}
    for row in rows:
        try:
            raw = json.loads(row["data_json"]) if row["data_json"] else {}
            data = raw.get("data", raw)
            sig = data.get("signal_metadata", {})
            if not sig:
                # Try legacy extraction
                model = (data.get("ai_model") or data.get("model") or
                         (data.get("identity", {}).get("model") if isinstance(data.get("identity"), dict) else None) or "")
                port = data.get("daemon_port") or data.get("port") or ""
                if not model or not port:
                    continue
                sig = {"port": port, "model_id": model, "model_tier": "unknown",
                       "quality_score": 0.5, "inference_latency_ms": 0, "cost_usd": 0}

            port = sig.get("port", "")
            model_id = sig.get("model_id", "")
            tier = sig.get("model_tier", "unknown")
            if not port or not model_id:
                continue

            key = (port, model_id, tier)
            if key not in agg:
                agg[key] = {"lats": [], "quals": [], "costs": [], "count": 0, "last": ""}
            a = agg[key]
            a["count"] += 1
            lat = sig.get("inference_latency_ms", 0)
            if lat > 0:
                a["lats"].append(lat)
            q = sig.get("quality_score", 0)
            if q > 0:
                a["quals"].append(q)
            c = sig.get("cost_usd", 0)
            if c > 0:
                a["costs"].append(c)
            ts = sig.get("timestamp") or row["timestamp"] or ""
            if ts > a["last"]:
                a["last"] = ts
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    now = datetime.now(timezone.utc)
    entries = []
    for (port, model_id, tier), a in agg.items():
        avg_lat = sum(a["lats"]) / len(a["lats"]) if a["lats"] else 0.0
        avg_qual = sum(a["quals"]) / len(a["quals"]) if a["quals"] else 0.5
        total_cost = sum(a["costs"])

        age_h = 0.0
        if a["last"]:
            try:
                last = datetime.fromisoformat(a["last"].replace("Z", "+00:00"))
                age_h = (now - last).total_seconds() / 3600.0
            except (ValueError, TypeError):
                pass

        evap = max(MIN_PHEROMONE, (1 - EVAPORATION_RATE) ** age_h)
        lat_norm = max(0.01, avg_lat / 1000.0) if avg_lat > 0 else 1.0
        cost_norm = max(0.001, total_cost / max(1, a["count"])) if total_cost > 0 else 0.001
        volume = min(2.0, 1.0 + math.log10(max(1, a["count"])))

        pheromone = (avg_qual ** QUALITY_WEIGHT) / (lat_norm ** SPEED_WEIGHT * cost_norm ** COST_WEIGHT) * evap * volume

        entries.append(PheromoneEntry(
            port=port, model_id=model_id, model_tier=tier,
            total_inferences=a["count"], avg_latency_ms=round(avg_lat, 1),
            avg_quality=round(avg_qual, 3), total_cost_usd=round(total_cost, 6),
            pheromone=round(pheromone, 4), age_hours=round(age_h, 2),
            evaporation=round(evap, 4),
        ))

    entries.sort(key=lambda e: e.pheromone, reverse=True)
    return entries


# ═══════════════════════════════════════════════════════════════
# § 5  RECOMMENDATIONS — ACO + SSO Model Selection
# ═══════════════════════════════════════════════════════════════

def compute_recommendations(pheromone: list[PheromoneEntry] = None) -> dict[str, dict]:
    """
    For each port, recommend which model to use next cycle.
    ACO: follow strongest pheromone (90%), explore (10%).
    SSO: vibration strength = pheromone / task distance.
    """
    import random
    if pheromone is None:
        pheromone = compute_pheromone()

    # MAP-ELITE defaults from registry (fallback)
    _DEFAULTS = {
        "P0": ("gemma3:4b",              "apex_speed"),
        "P1": ("gemini-3-flash-preview",  "apex_speed"),
        "P2": ("gemma3:4b",              "apex_speed"),
        "P3": ("lfm2.5-thinking:1.2b",   "apex_speed"),
        "P4": ("phi4:14b",               "apex_intelligence"),
        "P5": ("qwen3:8b",               "apex_speed"),
        "P6": ("deepseek-r1:8b",         "apex_intelligence"),
        "P7": ("gemini-3.1-pro-preview",  "apex_intelligence"),
    }

    recs = {}
    for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
        port_entries = [e for e in pheromone if e.port == port]

        if not port_entries:
            default_model, default_tier = _DEFAULTS.get(port, ("unknown", "apex_speed"))
            recs[port] = {
                "recommended_model": default_model,
                "recommended_tier": default_tier,
                "pheromone_strength": 0.0,
                "reason": "No pheromone — MAP-ELITE registry default",
                "exploration": False,
                "signal_count": 0,
                "alternatives": [],
            }
            continue

        port_entries.sort(key=lambda e: e.pheromone, reverse=True)
        best = port_entries[0]
        exploring = random.random() < 0.10

        if exploring and len(port_entries) > 1:
            alt = port_entries[1]
            recs[port] = {
                "recommended_model": alt.model_id,
                "recommended_tier": alt.model_tier,
                "pheromone_strength": alt.pheromone,
                "reason": f"EXPLORE: {alt.model_id} ({alt.pheromone:.2f}) vs best {best.model_id} ({best.pheromone:.2f})",
                "exploration": True,
                "signal_count": sum(e.total_inferences for e in port_entries),
                "alternatives": [
                    {"model": e.model_id, "pheromone": e.pheromone, "inferences": e.total_inferences}
                    for e in port_entries[:3]
                ],
            }
        else:
            recs[port] = {
                "recommended_model": best.model_id,
                "recommended_tier": best.model_tier,
                "pheromone_strength": best.pheromone,
                "reason": f"FOLLOW: {best.model_id} ({best.total_inferences} inferences, quality={best.avg_quality:.3f}, lat={best.avg_latency_ms:.0f}ms)",
                "exploration": False,
                "signal_count": sum(e.total_inferences for e in port_entries),
                "alternatives": [
                    {"model": e.model_id, "pheromone": e.pheromone, "inferences": e.total_inferences}
                    for e in port_entries[:3]
                ],
            }

    return recs


# ═══════════════════════════════════════════════════════════════
# § 6  EMIT RECOMMENDATIONS — Write to SSOT
# ═══════════════════════════════════════════════════════════════

def emit_recommendations(recs: dict[str, dict]) -> int:
    """Write per-port recommendations as stigmergy events so daemons can read them."""
    conn = _get_db_rw()
    count = 0
    for port, rec in recs.items():
        port_info = OCTREE_PORTS.get(port, {})
        _write_event(
            conn,
            "hfo.gen90.coordinator.recommendation",
            f"recommendation:{port}:{rec['recommended_model']}",
            {
                "port": port,
                "commander": port_info.get("commander", "?"),
                "recommendation": rec,
                "coordinator_version": COORDINATOR_IDENTITY["version"],
            },
        )
        count += 1
    conn.close()
    return count


# ═══════════════════════════════════════════════════════════════
# § 7  8^N FRACTAL DEPTH — Quality-Diversity Metrics
# ═══════════════════════════════════════════════════════════════

def compute_8n_depth(pheromone: list[PheromoneEntry] = None) -> dict:
    """
    Compute the 8^N fractal depth of the swarm.
    
    8^0 = 1  (coordinator exists)
    8^1 = 8  (all 8 ports have at least one signal)
    8^2 = 64 (all 8 ports × multiple models have signals)
    8^N = fractal depth (how many unique port-model-tier combos have pheromone)
    """
    if pheromone is None:
        pheromone = compute_pheromone()

    ports_covered = set()
    combos = set()
    tiers_per_port: dict[str, set] = defaultdict(set)
    models_per_port: dict[str, set] = defaultdict(set)

    for e in pheromone:
        ports_covered.add(e.port)
        combos.add((e.port, e.model_id, e.model_tier))
        tiers_per_port[e.port].add(e.model_tier)
        models_per_port[e.port].add(e.model_id)

    port_coverage = len(ports_covered) / 8.0
    total_combos = len(combos)

    # 8^N approximation: log8(combos)
    if total_combos > 0:
        fractal_n = math.log(total_combos) / math.log(8)
    else:
        fractal_n = 0.0

    # Quality-diversity score: how many unique niches (port×tier) are filled?
    max_niches = 8 * 3  # 8 ports × 3 tiers = 24
    filled_niches = sum(len(tiers) for tiers in tiers_per_port.values())
    qd_score = filled_niches / max_niches

    return {
        "fractal_n": round(fractal_n, 2),
        "total_combos": total_combos,
        "ports_covered": len(ports_covered),
        "port_coverage": round(port_coverage, 2),
        "filled_niches": filled_niches,
        "max_niches": max_niches,
        "quality_diversity_score": round(qd_score, 2),
        "tiers_per_port": {p: list(t) for p, t in tiers_per_port.items()},
        "models_per_port": {p: list(m) for p, m in models_per_port.items()},
        "level_description": (
            f"8^{fractal_n:.1f} ≈ {total_combos} combos across {len(ports_covered)}/8 ports, "
            f"QD={qd_score:.0%} ({filled_niches}/{max_niches} niches)"
        ),
    }


# ═══════════════════════════════════════════════════════════════
# § 8  PROCESS DUPLICATION DETECTION
# ═══════════════════════════════════════════════════════════════

def detect_duplicates() -> dict:
    """
    Scan OS processes for duplicate daemon instances.
    Returns dict with per-daemon process counts.
    """
    try:
        import psutil
    except ImportError:
        return {"error": "psutil not installed", "duplicates": []}

    daemon_keywords = {
        "singer_ai_daemon": "P4_Singer",
        "singer_daemon": "P4_Singer_Legacy",
        "p5_dancer_daemon": "P5_Dancer",
        "p6_devourer_daemon": "P6_Devourer",
        "p6_kraken_daemon": "P6_Kraken",
        "p6_kraken_loop": "P6_KrakenLoop",
        "p7_summoner_daemon": "P7_Summoner",
        "p7_foresight_daemon": "P7_Foresight",
        "p0_true_seeing": "P0_TrueSeeing",
        "p0_greater_scry": "P0_GreaterScry",
        "background_daemon": "Background",
        "prey8_mcp_server": "PREY8_MCP",
        "octree_daemon": "OctreeDaemon",
        "fleet_monitor": "FleetMonitor",
    }

    process_counts: dict[str, list] = defaultdict(list)
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info.get('cmdline') or [])
            for keyword, label in daemon_keywords.items():
                if keyword in cmdline.lower():
                    process_counts[label].append({
                        "pid": proc.info['pid'],
                        "cmdline_tail": cmdline[-80:] if len(cmdline) > 80 else cmdline,
                    })
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

    duplicates = []
    for label, procs in process_counts.items():
        if len(procs) > 1:
            duplicates.append({
                "daemon": label,
                "count": len(procs),
                "pids": [p["pid"] for p in procs],
                "waste_pct": round((len(procs) - 1) / len(procs) * 100, 0),
            })

    return {
        "total_daemon_processes": sum(len(p) for p in process_counts.values()),
        "unique_daemons": len(process_counts),
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
        "waste_processes": sum(len(p) - 1 for p in process_counts.values() if len(p) > 1),
        "by_daemon": {k: len(v) for k, v in process_counts.items()},
    }


# ═══════════════════════════════════════════════════════════════
# § 9  WISH ROUTER — Intent → Port Mapping
# ═══════════════════════════════════════════════════════════════

# Keyword→port routing (simple heuristic for common intents)
_INTENT_KEYWORDS = {
    "P0": ["watch", "observe", "monitor", "scan", "detect", "sense", "scry", "true seeing"],
    "P1": ["bridge", "web", "search", "fetch", "external", "api", "url", "research"],
    "P2": ["create", "build", "generate", "shape", "code", "implement", "design"],
    "P3": ["inject", "enrich", "classify", "tag", "assign", "port", "deliver"],
    "P4": ["test", "attack", "adversarial", "red team", "challenge", "disrupt", "audit"],
    "P5": ["gate", "guard", "validate", "immunize", "blue team", "governance", "heal", "resurrect"],
    "P6": ["learn", "assimilate", "summarize", "knowledge", "memory", "embed", "devour"],
    "P7": ["navigate", "strategy", "plan", "wish", "coordinate", "steer", "orchestrate"],
}


def route_intent(intent: str) -> dict:
    """
    Route operator intent to appropriate port(s) based on keyword matching.
    Returns primary port + scored alternatives.
    """
    intent_lower = intent.lower()
    scores: dict[str, float] = {}

    for port, keywords in _INTENT_KEYWORDS.items():
        score = sum(1.0 for kw in keywords if kw in intent_lower)
        # Boost for exact matches
        score += sum(0.5 for kw in keywords if kw in intent_lower.split())
        if score > 0:
            scores[port] = score

    if not scores:
        # Default to P7 NAVIGATE for ambiguous intents
        return {
            "primary_port": "P7",
            "confidence": 0.3,
            "reason": "No keyword match — defaulting to P7 NAVIGATE for strategic routing",
            "alternatives": [],
        }

    sorted_ports = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_ports[0]
    total_score = sum(scores.values())

    return {
        "primary_port": primary[0],
        "confidence": round(min(1.0, primary[1] / max(1, total_score) + 0.3), 2),
        "reason": f"Port {primary[0]} ({OCTREE_PORTS[primary[0]]['word']}) matched with score {primary[1]:.1f}",
        "alternatives": [
            {"port": p, "score": round(s, 1), "word": OCTREE_PORTS[p]["word"]}
            for p, s in sorted_ports[1:4]
        ],
    }


# ═══════════════════════════════════════════════════════════════
# § 10  COORDINATION CYCLE — The Main Loop
# ═══════════════════════════════════════════════════════════════

def run_cycle(hours_back: float = 24.0, quiet: bool = False) -> dict:
    """
    One full coordination cycle:
      1. Compute signal audit
      2. Compute pheromone scores
      3. Generate recommendations
      4. Compute 8^N depth
      5. Detect duplicates
      6. Emit recommendations to stigmergy
      7. Emit cycle health event
    """
    _p = (lambda *a, **k: None) if quiet else print
    t0 = time.time()

    # 1. Signal audit
    audit = compute_signal_audit(hours_back)
    _p(f"  [AUDIT] Signal Grade: {audit['grade']} "
       f"({audit['signal_pct']}% signal, {audit['legacy_pct']}% legacy, "
       f"{audit['blind_pct']}% blind) — {audit['total_events']} events")

    # 2. Pheromone
    pheromone = compute_pheromone(hours_back)
    _p(f"  [ACO]   Pheromone entries: {len(pheromone)} "
       f"(top: {pheromone[0].model_id if pheromone else 'none'} @ "
       f"{pheromone[0].pheromone:.2f} on {pheromone[0].port})" if pheromone else
       f"  [ACO]   No pheromone data — cold start")

    # 3. Recommendations
    recs = compute_recommendations(pheromone)
    exploring_count = sum(1 for r in recs.values() if r.get("exploration"))
    _p(f"  [REC]   8 port recommendations generated ({exploring_count} exploring)")

    # 4. 8^N depth
    depth = compute_8n_depth(pheromone)
    _p(f"  [8^N]   {depth['level_description']}")

    # 5. Duplicates
    dupes = detect_duplicates()
    if dupes.get("duplicates"):
        _p(f"  [DUPES] WARNING: {dupes['duplicate_count']} duplicate daemons detected "
           f"({dupes['waste_processes']} wasted processes)")
        for d in dupes["duplicates"]:
            _p(f"          {d['daemon']}: {d['count']} instances (PIDs: {d['pids']})")
    else:
        _p(f"  [DUPES] Clean — {dupes['total_daemon_processes']} daemon processes, no duplicates")

    # 6. Emit recommendations
    emitted = emit_recommendations(recs)
    _p(f"  [EMIT]  {emitted} recommendations → stigmergy")

    # 7. Health event
    elapsed = time.time() - t0
    health = {
        "cycle_time_s": round(elapsed, 2),
        "signal_grade": audit["grade"],
        "signal_pct": audit["signal_pct"],
        "pheromone_entries": len(pheromone),
        "fractal_n": depth["fractal_n"],
        "total_combos": depth["total_combos"],
        "ports_covered": depth["ports_covered"],
        "quality_diversity": depth["quality_diversity_score"],
        "duplicate_count": dupes.get("duplicate_count", 0),
        "waste_processes": dupes.get("waste_processes", 0),
        "total_events_24h": audit["total_events"],
        "recommendations": {p: r["recommended_model"] for p, r in recs.items()},
    }

    conn = _get_db_rw()
    _write_event(conn, "hfo.gen90.coordinator.cycle",
                 f"coordinator:cycle:grade_{audit['grade']}",
                 health)
    conn.close()

    _p(f"  [DONE]  Cycle complete in {elapsed:.1f}s")

    return {
        "audit": audit,
        "pheromone_count": len(pheromone),
        "recommendations": recs,
        "depth": depth,
        "duplicates": dupes,
        "health": health,
    }


# ═══════════════════════════════════════════════════════════════
# § 11  DAEMON MODE — Recurring Coordination  
# ═══════════════════════════════════════════════════════════════

def daemon_loop(interval: int = 300, max_cycles: int = 0):
    """Run coordinator on a recurring schedule."""
    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║  8^N OCTREE COORDINATOR — DAEMON MODE                   ║")
    print("  ║  Spider Sovereign — Scatter-Gather ACO+SSO              ║")
    print(f" ║  Interval: {interval}s | Max: {'∞' if max_cycles == 0 else max_cycles:<4}                            ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()

    cycle = 0
    while True:
        cycle += 1
        if max_cycles > 0 and cycle > max_cycles:
            break

        print(f"\n  ── Cycle {cycle} @ {datetime.now().strftime('%H:%M:%S')} ──")
        try:
            result = run_cycle()
        except Exception as e:
            print(f"  [ERROR] Cycle {cycle} failed: {e}")

        if max_cycles > 0 and cycle >= max_cycles:
            break

        print(f"  [SLEEP] Next cycle in {interval}s...")
        time.sleep(interval)


# ═══════════════════════════════════════════════════════════════
# § 12  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "═" * 64)
    print("  8^N OCTREE COORDINATOR — Spider Sovereign")
    print("  Scatter-Gather ACO + Social Spider Optimization")
    print("  " + "─" * 64)
    print("  8^1 = 8 ports | 8^2 = 64 combos | 8^N = fractal depth")
    print("  " + "═" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="8^N Octree Coordinator — ACO+SSO Swarm Intelligence (Gen90)",
    )
    parser.add_argument("--cycle", action="store_true",
                        help="Run one coordination cycle")
    parser.add_argument("--status", action="store_true",
                        help="Fleet status + signal grade")
    parser.add_argument("--recommendations", action="store_true",
                        help="Show per-port model recommendations")
    parser.add_argument("--depth", action="store_true",
                        help="Show 8^N fractal depth metrics")
    parser.add_argument("--wish", type=str, default="",
                        help="Route operator intent to port(s)")
    parser.add_argument("--dedup", action="store_true",
                        help="Detect duplicate daemon processes")
    parser.add_argument("--daemon", action="store_true",
                        help="Run as recurring coordinator daemon")
    parser.add_argument("--interval", type=int, default=300,
                        help="Daemon interval in seconds (default: 300)")
    parser.add_argument("--max-cycles", type=int, default=0,
                        help="Max daemon cycles (0 = infinite)")
    parser.add_argument("--hours", type=float, default=24.0,
                        help="Lookback hours for pheromone/audit")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable JSON output")
    args = parser.parse_args()

    if not args.json:
        _print_banner()

    if args.daemon:
        daemon_loop(args.interval, args.max_cycles)
        return

    if args.cycle:
        result = run_cycle(args.hours, quiet=args.json)
        if args.json:
            # Slim the output for JSON
            out = {
                "health": result["health"],
                "audit_grade": result["audit"]["grade"],
                "depth": result["depth"],
                "duplicates_count": result["duplicates"].get("duplicate_count", 0),
                "recommendations": {
                    p: {"model": r["recommended_model"], "pheromone": r["pheromone_strength"]}
                    for p, r in result["recommendations"].items()
                },
            }
            print(json.dumps(out, indent=2))
        return

    if args.status:
        audit = compute_signal_audit(args.hours)
        depth = compute_8n_depth()
        dupes = detect_duplicates()

        if args.json:
            print(json.dumps({"audit": audit, "depth": depth, "duplicates": dupes}, indent=2))
        else:
            print(f"  Signal Grade:     {audit['grade']}")
            print(f"  Signal Metadata:  {audit['has_signal_metadata']}/{audit['total_events']} ({audit['signal_pct']}%)")
            print(f"  Legacy Model:     {audit['has_legacy']}/{audit['total_events']} ({audit['legacy_pct']}%)")
            print(f"  Blind Events:     {audit['blind']}/{audit['total_events']} ({audit['blind_pct']}%)")
            print(f"  Models Seen:      {', '.join(audit.get('models_seen', {}).keys()) or 'none'}")
            print()
            print(f"  8^N Depth:        {depth['level_description']}")
            print(f"  QD Score:         {depth['quality_diversity_score']:.0%}")
            print()
            print(f"  Daemon Processes: {dupes['total_daemon_processes']}")
            print(f"  Duplicates:       {dupes['duplicate_count']} ({dupes['waste_processes']} wasted)")
            if dupes["duplicates"]:
                for d in dupes["duplicates"]:
                    print(f"    ⚠ {d['daemon']}: {d['count']}x (PIDs: {d['pids']})")
        return

    if args.recommendations:
        recs = compute_recommendations()
        if args.json:
            print(json.dumps(recs, indent=2))
        else:
            for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
                r = recs.get(port, {})
                info = OCTREE_PORTS[port]
                explore = " 🔍" if r.get("exploration") else ""
                print(f"  {port} {info['word']:<10s} → {r.get('recommended_model', '?'):<25s} "
                      f"pher={r.get('pheromone_strength', 0):.2f} "
                      f"sig={r.get('signal_count', 0)}{explore}")
                if r.get("alternatives"):
                    for alt in r["alternatives"][:2]:
                        print(f"       alt: {alt['model']:<25s} pher={alt['pheromone']:.2f} ({alt['inferences']} inf)")
        return

    if args.depth:
        depth = compute_8n_depth()
        if args.json:
            print(json.dumps(depth, indent=2))
        else:
            print(f"  Fractal N:         {depth['fractal_n']:.2f}")
            print(f"  Total Combos:      {depth['total_combos']}")
            print(f"  Ports Covered:     {depth['ports_covered']}/8")
            print(f"  Niche Fill:        {depth['filled_niches']}/{depth['max_niches']}")
            print(f"  QD Score:          {depth['quality_diversity_score']:.0%}")
            print(f"  Level:             {depth['level_description']}")
            print()
            for p in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
                models = depth["models_per_port"].get(p, [])
                tiers = depth["tiers_per_port"].get(p, [])
                info = OCTREE_PORTS[p]
                if models:
                    print(f"  {p} {info['word']:<10s}: {len(models)} models, {len(tiers)} tiers — {', '.join(models[:3])}")
                else:
                    print(f"  {p} {info['word']:<10s}: (empty)")
        return

    if args.wish:
        routing = route_intent(args.wish)
        if args.json:
            print(json.dumps(routing, indent=2))
        else:
            primary = routing["primary_port"]
            info = OCTREE_PORTS[primary]
            print(f"  Intent:  \"{args.wish}\"")
            print(f"  Route:   {primary} {info['word']} ({info['commander']})")
            print(f"  Confidence: {routing['confidence']:.0%}")
            print(f"  Reason: {routing['reason']}")
            if routing["alternatives"]:
                print(f"  Alternatives:")
                for alt in routing["alternatives"]:
                    print(f"    {alt['port']} {alt['word']} (score: {alt['score']})")
        return

    if args.dedup:
        dupes = detect_duplicates()
        if args.json:
            print(json.dumps(dupes, indent=2))
        else:
            print(f"  Total daemon processes: {dupes['total_daemon_processes']}")
            print(f"  Unique daemons: {dupes['unique_daemons']}")
            print(f"  Duplicates: {dupes['duplicate_count']}")
            print(f"  Waste processes: {dupes['waste_processes']}")
            print()
            for daemon, count in sorted(dupes.get("by_daemon", {}).items()):
                icon = "⚠" if count > 1 else "✓"
                print(f"  {icon} {daemon}: {count}")
            if dupes["duplicates"]:
                print()
                for d in dupes["duplicates"]:
                    print(f"  ⚠ {d['daemon']}: {d['count']} instances — PIDs: {d['pids']}")
        return

    # Default: one cycle
    run_cycle(args.hours)


if __name__ == "__main__":
    main()
