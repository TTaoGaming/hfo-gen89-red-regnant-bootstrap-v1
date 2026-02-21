#!/usr/bin/env python3
"""
hfo_signal_shim.py — Standardized Signal Metadata Emission Shim
================================================================
v1.0 | Gen90 | Port: ALL | Medallion: bronze

PURPOSE:
    Zero-config shim that ANY daemon imports to emit standardized
    signal_metadata in every CloudEvent. This upgrades the swarm from
    Grade D (69.3% blind) to Grade A (80%+ signal_metadata).

    The shim provides TWO things:
      1. build_signal_metadata() — creates a SignalMetadata dict 
      2. emit_enriched_event()   — writes a CloudEvent with signal_metadata embedded

    Import pattern for existing daemons:
        from hfo_signal_shim import build_signal_metadata, emit_enriched_event

ARCHITECTURE:
    ACO (Ant Colony Optimization) pheromone loop:
      daemon emits event + signal_metadata → stigmergy_events table
      → hfo_map_elite_commanders.py reads signal_metadata → computes pheromone
      → hfo_octree_8n_coordinator.py reads pheromone → recommends model per port
      → daemon reads recommendation → selects model next cycle → emits event...
    
    The loop self-optimizes: strong models accumulate pheromone,
    weak models evaporate, 10% exploration prevents local optima.

SIGNAL_METADATA FIELDS (from MAP-ELITE schema v1.0):
    IDENTITY: port, commander, daemon_name, daemon_version
    MODEL:    model_id, model_family, model_params_b, model_provider, model_tier
    PERF:     inference_latency_ms, tokens_in, tokens_out, tokens_thinking
    QUALITY:  quality_score (0-1), quality_method
    COST:     cost_usd, vram_gb
    CONTEXT:  cycle, task_type, generation, timestamp

Pointer key: signal.shim
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from hfo_ssot_write import get_db_readwrite as _get_db_rw


# ═══════════════════════════════════════════════════════════════
# § 0  PAL — Path Abstraction Layer
# ═══════════════════════════════════════════════════════════════

_SELF_DIR = Path(__file__).resolve().parent


def _find_root() -> Path:
    for anchor in [Path.cwd(), _SELF_DIR]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = _find_root()
GEN = os.environ.get("HFO_GENERATION", "89")

# Load .env
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
# § 1  OCTREE PORT REGISTRY — Commander Identity
# ═══════════════════════════════════════════════════════════════

OCTREE_PORTS = {
    "P0": {"word": "OBSERVE",    "commander": "Lidless Legion"},
    "P1": {"word": "BRIDGE",     "commander": "Web Weaver"},
    "P2": {"word": "SHAPE",      "commander": "Mirror Magus"},
    "P3": {"word": "INJECT",     "commander": "Harmonic Hydra"},
    "P4": {"word": "DISRUPT",    "commander": "Red Regnant"},
    "P5": {"word": "IMMUNIZE",   "commander": "Pyre Praetorian"},
    "P6": {"word": "ASSIMILATE", "commander": "Kraken Keeper"},
    "P7": {"word": "NAVIGATE",   "commander": "Spider Sovereign"},
}

# Known model metadata (params_b, family, provider)
_MODEL_DB = {
    # Ollama local
    "deepseek-r1:32b":       {"family": "DeepSeek",       "params_b": 32.0, "provider": "ollama", "vram_gb": 19.0, "thinking": True},
    "phi4:14b":              {"family": "Microsoft Phi",   "params_b": 14.0, "provider": "ollama", "vram_gb": 9.1,  "thinking": False},
    "qwen3:30b-a3b":         {"family": "Alibaba Qwen",   "params_b": 30.0, "provider": "ollama", "vram_gb": 18.0, "thinking": True},
    "deepseek-r1:8b":        {"family": "DeepSeek",       "params_b": 8.0,  "provider": "ollama", "vram_gb": 5.2,  "thinking": True},
    "qwen2.5-coder:7b":      {"family": "Alibaba Qwen",   "params_b": 7.0,  "provider": "ollama", "vram_gb": 4.7,  "thinking": False},
    "qwen3:8b":              {"family": "Alibaba Qwen",   "params_b": 8.0,  "provider": "ollama", "vram_gb": 5.2,  "thinking": True},
    "gemma3:12b":            {"family": "Google Gemma",    "params_b": 12.0, "provider": "ollama", "vram_gb": 8.1,  "thinking": False},
    "gemma3:4b":             {"family": "Google Gemma",    "params_b": 4.0,  "provider": "ollama", "vram_gb": 3.3,  "thinking": False},
    "granite4:3b":           {"family": "IBM Granite",     "params_b": 3.0,  "provider": "ollama", "vram_gb": 2.1,  "thinking": False},
    "llama3.2:3b":           {"family": "Meta Llama",      "params_b": 3.0,  "provider": "ollama", "vram_gb": 2.0,  "thinking": False},
    "qwen2.5:3b":            {"family": "Alibaba Qwen",   "params_b": 3.0,  "provider": "ollama", "vram_gb": 1.9,  "thinking": False},
    "lfm2.5-thinking:1.2b":  {"family": "Liquid AI",      "params_b": 1.2,  "provider": "ollama", "vram_gb": 0.7,  "thinking": True},
    # Gemini cloud
    "gemini-3.1-pro-preview": {"family": "Google Gemini", "params_b": 0.0, "provider": "gemini_vertex", "vram_gb": 0.0, "thinking": True},
    "gemini-3-pro-preview":   {"family": "Google Gemini", "params_b": 0.0, "provider": "gemini_vertex", "vram_gb": 0.0, "thinking": True},
    "gemini-3-flash-preview":  {"family": "Google Gemini", "params_b": 0.0, "provider": "gemini_free",   "vram_gb": 0.0, "thinking": True},
    "gemini-2.5-flash":       {"family": "Google Gemini", "params_b": 0.0, "provider": "gemini_free",   "vram_gb": 0.0, "thinking": True},
    "gemini-2.5-flash-lite":  {"family": "Google Gemini", "params_b": 0.0, "provider": "gemini_free",   "vram_gb": 0.0, "thinking": True},
    # Claude (via Copilot)
    "claude-opus-4-6":        {"family": "Anthropic Claude", "params_b": 0.0, "provider": "claude", "vram_gb": 0.0, "thinking": True},
}

# MAP-ELITE tier classification thresholds
_TIER_THRESHOLDS = {
    # (min_params_b, supports_thinking) → tier
    # Rough heuristic: ≥14B or cloud apex = intelligence, ≥4B = speed, <4B = cost
}


def _classify_tier(model_id: str) -> str:
    """Classify a model into MAP-ELITE tier based on known metadata."""
    meta = _MODEL_DB.get(model_id, {})
    params = meta.get("params_b", 0.0)
    provider = meta.get("provider", "unknown")
    thinking = meta.get("thinking", False)

    # Cloud apex
    if provider in ("gemini_vertex",) and thinking:
        return "apex_intelligence"
    # Large local
    if params >= 14.0:
        return "apex_intelligence"
    # Medium
    if params >= 4.0 or (provider in ("gemini_free",) and thinking):
        return "apex_speed"
    # Small
    return "apex_cost"


# ═══════════════════════════════════════════════════════════════
# § 2  BUILD SIGNAL METADATA — The Core Function
# ═══════════════════════════════════════════════════════════════

def build_signal_metadata(
    port: str,
    model_id: str,
    daemon_name: str,
    daemon_version: str = "v1.0",
    *,
    inference_latency_ms: float = 0.0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    tokens_thinking: int = 0,
    quality_score: float = 0.0,
    quality_method: str = "none",
    cost_usd: float = 0.0,
    cycle: int = 0,
    task_type: str = "",
) -> dict:
    """
    Build a standardized signal_metadata dict for embedding in CloudEvents.

    This is the ONE function every daemon needs. Minimal required args:
      - port: "P0"-"P7"
      - model_id: "phi4:14b", "gemini-3.1-pro-preview", etc.
      - daemon_name: "Singer", "Dancer", "Kraken", etc.

    Everything else is auto-resolved from the model registry or defaulted.

    Returns a dict ready to embed as event_data["signal_metadata"].
    """
    port = port.upper()
    port_info = OCTREE_PORTS.get(port, {"word": "UNKNOWN", "commander": "Unknown"})
    model_meta = _MODEL_DB.get(model_id, {})

    return {
        # Identity
        "port": port,
        "commander": port_info["commander"],
        "daemon_name": daemon_name,
        "daemon_version": daemon_version,
        # Model
        "model_id": model_id,
        "model_family": model_meta.get("family", "Unknown"),
        "model_params_b": model_meta.get("params_b", 0.0),
        "model_provider": model_meta.get("provider", "unknown"),
        "model_tier": _classify_tier(model_id),
        # Performance
        "inference_latency_ms": round(inference_latency_ms, 1),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_thinking": tokens_thinking,
        # Quality
        "quality_score": round(quality_score, 3),
        "quality_method": quality_method,
        # Cost
        "cost_usd": round(cost_usd, 6),
        "vram_gb": model_meta.get("vram_gb", 0.0),
        # Context
        "cycle": cycle,
        "task_type": task_type,
        "generation": GEN,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# § 3  EMIT ENRICHED EVENT — Write to SSOT with signal_metadata
# ═══════════════════════════════════════════════════════════════


def emit_enriched_event(
    event_type: str,
    subject: str,
    data: dict,
    signal_meta: dict,
    source: str = "",
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """
    Write a CloudEvent to stigmergy_events with signal_metadata embedded.

    Args:
        event_type: CloudEvent type (e.g. "hfo.gen90.singer.strife")
        subject: CloudEvent subject (e.g. "strife:doc:1234")
        data: Event-specific payload dict
        signal_meta: Dict from build_signal_metadata()
        source: Event source tag (auto-generated if empty)
        conn: Optional existing DB connection (manages own if None)

    Returns:
        Row ID of the inserted event, or 0 if deduped/failed.
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_db_rw()

    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)

    if not source:
        daemon = signal_meta.get("daemon_name", "unknown")
        port = signal_meta.get("port", "P?")
        source = f"hfo_{daemon.lower()}_gen{GEN}_{port.lower()}"

    # Embed signal_metadata into data
    enriched_data = {**data, "signal_metadata": signal_meta}

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
        "data": enriched_data,
    }

    content_hash = hashlib.sha256(
        json.dumps(envelope, sort_keys=True).encode()
    ).hexdigest()

    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_type, now, subject, source, json.dumps(envelope), content_hash),
        )
        conn.commit()
        row_id = cur.lastrowid or 0
    except Exception:
        row_id = 0

    if own_conn:
        conn.close()

    return row_id


# ═══════════════════════════════════════════════════════════════
# § 4  CONVENIENCE: build + emit in one call
# ═══════════════════════════════════════════════════════════════

def signal_emit(
    event_type: str,
    subject: str,
    data: dict,
    *,
    port: str,
    model_id: str,
    daemon_name: str,
    daemon_version: str = "v1.0",
    inference_latency_ms: float = 0.0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    tokens_thinking: int = 0,
    quality_score: float = 0.0,
    quality_method: str = "none",
    cost_usd: float = 0.0,
    cycle: int = 0,
    task_type: str = "",
    source: str = "",
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """
    All-in-one: build signal_metadata + emit enriched CloudEvent.

    Typical daemon usage:
        from hfo_signal_shim import signal_emit

        row_id = signal_emit(
            "hfo.gen90.singer.strife",
            f"strife:doc:{doc_id}",
            {"song": "strife", "signal": "pattern_found", "doc_id": doc_id},
            port="P4", model_id="phi4:14b", daemon_name="Singer",
            inference_latency_ms=3200, tokens_out=800,
            quality_score=0.72, quality_method="self_eval",
            cycle=42, task_type="strife",
        )
    """
    sig = build_signal_metadata(
        port=port,
        model_id=model_id,
        daemon_name=daemon_name,
        daemon_version=daemon_version,
        inference_latency_ms=inference_latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_thinking=tokens_thinking,
        quality_score=quality_score,
        quality_method=quality_method,
        cost_usd=cost_usd,
        cycle=cycle,
        task_type=task_type,
    )
    return emit_enriched_event(
        event_type=event_type,
        subject=subject,
        data=data,
        signal_meta=sig,
        source=source,
        conn=conn,
    )


# ═══════════════════════════════════════════════════════════════
# § 5  READ RECOMMENDATION — What model should I use?
# ═══════════════════════════════════════════════════════════════

def read_port_recommendation(port: str) -> dict:
    """
    Read the latest ACO-based model recommendation for a port.

    The 8^N coordinator writes these as stigmergy events.
    Daemons can call this at cycle start to dynamically select their model.

    Returns dict with recommended_model, recommended_tier, pheromone_strength.
    Falls back to MAP-ELITE registry default if no recommendation exists.
    """
    port = port.upper()
    try:
        conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT data_json FROM stigmergy_events
               WHERE event_type = 'hfo.gen90.coordinator.recommendation'
               AND subject LIKE ?
               ORDER BY id DESC LIMIT 1""",
            (f"%{port}%",),
        ).fetchone()
        conn.close()

        if row:
            raw = json.loads(row["data_json"])
            data = raw.get("data", raw)
            rec = data.get("recommendation", {})
            if rec.get("recommended_model"):
                return rec
    except Exception:
        pass

    # Fallback: return MAP-ELITE registry default
    return {
        "recommended_model": "unknown",
        "recommended_tier": "apex_speed",
        "pheromone_strength": 0.0,
        "reason": "No coordinator recommendation found — using default",
        "exploration": False,
    }


# ═══════════════════════════════════════════════════════════════
# § 6  CLI — Self-test
# ═══════════════════════════════════════════════════════════════

def main():
    """Self-test: build signal_metadata and emit a test event."""
    import argparse
    parser = argparse.ArgumentParser(description="Signal Metadata Shim — self-test")
    parser.add_argument("--emit-test", action="store_true",
                        help="Emit a test signal_metadata event to SSOT")
    parser.add_argument("--build-test", action="store_true",
                        help="Build a test signal_metadata dict (no SSOT write)")
    parser.add_argument("--read-rec", type=str, default="",
                        help="Read recommendation for port (e.g. P4)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.build_test:
        sig = build_signal_metadata(
            port="P4", model_id="phi4:14b", daemon_name="Singer_Test",
            daemon_version="v1.0",
            inference_latency_ms=3200.0, tokens_in=1500, tokens_out=800,
            quality_score=0.72, quality_method="self_eval",
            cycle=1, task_type="strife",
        )
        if args.json:
            print(json.dumps(sig, indent=2))
        else:
            print("\n  Signal Metadata (test build):")
            for k, v in sig.items():
                print(f"    {k}: {v}")
        return

    if args.emit_test:
        row_id = signal_emit(
            "hfo.gen90.signal_shim.self_test",
            "self_test:signal_shim:v1.0",
            {"test": True, "purpose": "Verify signal_metadata emission works"},
            port="P7", model_id="gemini-3.1-pro-preview",
            daemon_name="SignalShim_SelfTest", daemon_version="v1.0",
            inference_latency_ms=0.0, quality_score=1.0,
            quality_method="self_test", cycle=0, task_type="self_test",
        )
        if args.json:
            print(json.dumps({"row_id": row_id, "status": "emitted"}))
        else:
            print(f"\n  Signal shim self-test event emitted → SSOT row {row_id}")
        return

    if args.read_rec:
        rec = read_port_recommendation(args.read_rec)
        if args.json:
            print(json.dumps(rec, indent=2))
        else:
            print(f"\n  Recommendation for {args.read_rec.upper()}:")
            for k, v in rec.items():
                print(f"    {k}: {v}")
        return

    # Default: show overview
    print("\n  HFO Signal Metadata Shim v1.0")
    print("  ─────────────────────────────")
    print(f"  SSOT: {SSOT_DB}")
    print(f"  Generation: {GEN}")
    print(f"  Known models: {len(_MODEL_DB)}")
    print(f"  Octree ports: {len(OCTREE_PORTS)}")
    print()
    print("  Usage for daemon authors:")
    print("    from hfo_signal_shim import signal_emit")
    print("    row_id = signal_emit(")
    print('        "hfo.gen90.singer.strife",')
    print('        f"strife:doc:{doc_id}",')
    print("        {your_data_dict},")
    print('        port="P4", model_id="phi4:14b",')
    print('        daemon_name="Singer",')
    print('        inference_latency_ms=3200,')
    print('        quality_score=0.72, quality_method="self_eval",')
    print("    )")
    print()
    print("  Self-test:")
    print(f"    python {Path(__file__).name} --build-test")
    print(f"    python {Path(__file__).name} --emit-test")
    print(f"    python {Path(__file__).name} --read-rec P4")
    print()


if __name__ == "__main__":
    main()
