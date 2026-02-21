#!/usr/bin/env python3
"""
hfo_p6_kraken_swarm.py — Resource-Aware P6 Kraken Swarm Launcher
=================================================================
v1.0 | Gen89 | Port: P6 ASSIMILATE | Commander: Kraken Keeper
Powerword: ASSIMILATE | Spell: CLONE | School: Necromancy
Title: Devourer of Depths and Dreams | Trigram: ☶ Gen (Mountain)

PURPOSE:
    Unified swarm launcher that subsumes the original P6 Kraken Daemon
    with resource-aware scheduling, VRAM budget management, and
    8 concurrent knowledge enrichment worker types.

    This is the 8^1 swarm: 8 worker types, resource-adaptive,
    pressure-based scheduling, stigmergy-integrated.

ARCHITECTURE:
    ┌─────────────────────────────────────────────────┐
    │                SWARM LAUNCHER                    │
    │                                                  │
    │  ┌──────────────┐  ┌─────────────────────────┐  │
    │  │ ResourceMonitor│  │  SwarmOrchestrator      │  │
    │  │ (sense_loop)  │──│  (pressure scheduling)  │  │
    │  └──────────────┘  └─────────────────────────┘  │
    │                       │                          │
    │  ┌────────────────────┴───────────────────────┐  │
    │  │           Worker Pool (8 types)            │  │
    │  ├────────────────────────────────────────────┤  │
    │  │ T1 BLUF       │ T5 Progressive Summary    │  │
    │  │ T2 Port       │ T6 Knowledge Graph        │  │
    │  │ T3 DocType    │ T7 Tag Expansion          │  │
    │  │ T4 Lineage    │ T8 Quality Audit (CPU)    │  │
    │  └────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────┘

WORKER PRIORITIES:
    Priority 3 (CORE — runs under THROTTLED pressure):
        T1 BLUF, T2 Port
    Priority 2 (STANDARD — runs under ELEVATED pressure):
        T3 DocType, T4 Lineage, T7 Tag Expansion
    Priority 1 (ADVANCED — runs only at NOMINAL/IDLE):
        T5 Progressive Summary, T6 Knowledge Graph, T8 Quality Audit

RESOURCE PRESSURE LEVELS:
    IDLE      → All 8 workers active, fast intervals
    NOMINAL   → All 8 workers active, normal intervals
    ELEVATED  → Priority 2+ workers only (6 of 8)
    THROTTLED → Priority 3 only (2 of 8)
    CRITICAL  → All workers paused
    YIELDED   → All workers paused (external request)

USAGE:
    # 24/7 swarm mode (replaces old daemon)
    python hfo_p6_kraken_swarm.py

    # Run one cycle of all workers
    python hfo_p6_kraken_swarm.py --once

    # Dry run (no writes to SSOT)
    python hfo_p6_kraken_swarm.py --dry-run --once

    # Select specific workers
    python hfo_p6_kraken_swarm.py --workers bluf,port,knowledge_graph

    # Custom model
    python hfo_p6_kraken_swarm.py --model qwen3:8b

    # Show swarm status
    python hfo_p6_kraken_swarm.py --status

    # JSON status
    python hfo_p6_kraken_swarm.py --status --json

Medallion: bronze
Port: P6 ASSIMILATE
Pointer key: daemon.p6_kraken_swarm
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from hfo_ssot_write import get_db_readwrite as _get_db_rw

# ═══════════════════════════════════════════════════════════════
# PATH RESOLUTION — ensure sibling modules are importable
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    """Walk up to find HFO_ROOT (dir containing AGENTS.md)."""
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
RESOURCES_DIR = Path(__file__).resolve().parent

# Ensure resources dir is on sys.path for sibling imports
if str(RESOURCES_DIR) not in sys.path:
    sys.path.insert(0, str(RESOURCES_DIR))

# ── PAL pointer resolution ──
POINTERS_FILE = HFO_ROOT / "hfo_gen89_pointers_blessed.json"


def _load_pointers() -> dict:
    if not POINTERS_FILE.exists():
        return {}
    with open(POINTERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("pointers", data)


def resolve_pointer(key: str) -> Path:
    pointers = _load_pointers()
    if key not in pointers:
        raise KeyError(f"Pointer '{key}' not found")
    entry = pointers[key]
    rel_path = entry["path"] if isinstance(entry, dict) else entry
    return HFO_ROOT / rel_path


# ── Resolve critical paths ──
try:
    SSOT_DB = resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"

GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
P6_MODEL = os.environ.get("P6_OLLAMA_MODEL", "gemma3:4b")
STATE_FILE = HFO_ROOT / ".hfo_p6_kraken_swarm_state.json"
SWARM_SOURCE = f"hfo_p6_kraken_swarm_gen{GEN}"

# ═══════════════════════════════════════════════════════════════
# IMPORT SIBLING MODULES — graceful degradation if missing
# ═══════════════════════════════════════════════════════════════

_import_errors: list[str] = []

# Resource Monitor (sense loop + orchestrator)
try:
    from hfo_resource_monitor import (
        ResourceMonitor,
        ResourcePressure,
        ResourceSnapshot,
        SlotManager,
        SwarmOrchestrator,
        WorkerConfig,
        WorkerType,
        DEFAULT_WORKERS,
        VRAM_BUDGET_GB,
    )
    HAS_RESOURCE_MONITOR = True
except ImportError as e:
    HAS_RESOURCE_MONITOR = False
    _import_errors.append(f"hfo_resource_monitor: {e}")

# Extended Workers T5-T8
try:
    from hfo_p6_kraken_workers import (
        progressive_summarization,
        knowledge_graph_extraction,
        tag_expansion,
        quality_audit,
        WORKER_REGISTRY,
    )
    HAS_EXTENDED_WORKERS = True
except ImportError as e:
    HAS_EXTENDED_WORKERS = False
    _import_errors.append(f"hfo_p6_kraken_workers: {e}")

# NPU Embedding Worker T9
try:
    from hfo_npu_embedder import (
        npu_embedding_worker,
        get_embedding_stats,
        NPUEmbedder,
    )
    HAS_NPU_EMBEDDER = True
except ImportError as e:
    HAS_NPU_EMBEDDER = False
    _import_errors.append(f"hfo_npu_embedder: {e}")

# Resource Governance Daemon
try:
    from hfo_resource_governance import GovernanceDaemon
    HAS_GOVERNANCE = True
except ImportError as e:
    HAS_GOVERNANCE = False
    _import_errors.append(f"hfo_resource_governance: {e}")

# Original Daemon T1-T4
try:
    from hfo_p6_kraken_daemon import (
        KrakenKeeper,
        ollama_generate,
        ollama_available,
        write_stigmergy_event,
        get_db_readwrite,
        get_db_readonly,
        KRAKEN_IDENTITY,
        KRAKEN_SYSTEM_PROMPT,
    )
    HAS_DAEMON = True
except ImportError as e:
    HAS_DAEMON = False
    _import_errors.append(f"hfo_p6_kraken_daemon: {e}")


# ═══════════════════════════════════════════════════════════════
# SWARM IDENTITY
# ═══════════════════════════════════════════════════════════════

SWARM_IDENTITY = {
    "port": "P6",
    "powerword": "ASSIMILATE",
    "commander": "Kraken Keeper",
    "title": "Devourer of Depths and Dreams — Swarm Mode",
    "spell": "CLONE",
    "spell_school": "Necromancy",
    "trigram": "☶ Gen (Mountain)",
    "galois_pair": "P1 BRIDGE (Web Weaver)",
    "architecture": "8^1+1 Resource-Governed Swarm (9 worker types + governance)",
    "core_thesis": "Everything that dies feeds the knowledge graph. The swarm devours.",
    "compute_axes": "GPU (Ollama) + NPU (OpenVINO) + CPU",
}

# 8 worker types with their configurations
SWARM_WORKER_DEFS: dict[str, dict] = {
    "bluf": {
        "type": WorkerType.BLUF if HAS_RESOURCE_MONITOR else None,
        "task": "T1",
        "desc": "BLUF Generation",
        "model": "gemma3:4b",
        "interval": 90,
        "batch_size": 3,
        "priority": 3,
        "cpu_only": False,
        "source": "daemon",  # dispatched by KrakenKeeper
    },
    "port": {
        "type": WorkerType.PORT if HAS_RESOURCE_MONITOR else None,
        "task": "T2",
        "desc": "Port Classification",
        "model": "gemma3:4b",
        "interval": 120,
        "batch_size": 5,
        "priority": 3,
        "cpu_only": False,
        "source": "daemon",
    },
    "doctype": {
        "type": WorkerType.DOCTYPE if HAS_RESOURCE_MONITOR else None,
        "task": "T3",
        "desc": "Doc Type Classification",
        "model": "gemma3:4b",
        "interval": 180,
        "batch_size": 3,
        "priority": 2,
        "cpu_only": False,
        "source": "daemon",
    },
    "lineage": {
        "type": WorkerType.LINEAGE if HAS_RESOURCE_MONITOR else None,
        "task": "T4",
        "desc": "Lineage Mining",
        "model": "gemma3:4b",
        "interval": 300,
        "batch_size": 2,
        "priority": 2,
        "cpu_only": True,  # CPU-intensive FTS, not GPU
        "source": "daemon",
    },
    "progressive_summary": {
        "type": WorkerType.PROG_SUMMARY if HAS_RESOURCE_MONITOR else None,
        "task": "T5",
        "desc": "Progressive Summarization (3-pass)",
        "model": "qwen3:8b",
        "interval": 600,
        "batch_size": 1,
        "priority": 1,
        "cpu_only": False,
        "source": "workers",
    },
    "knowledge_graph": {
        "type": WorkerType.KNOWLEDGE_GRAPH if HAS_RESOURCE_MONITOR else None,
        "task": "T6",
        "desc": "Knowledge Graph Extraction",
        "model": "gemma3:4b",
        "interval": 450,
        "batch_size": 2,
        "priority": 1,
        "cpu_only": False,
        "source": "workers",
    },
    "tag_expansion": {
        "type": WorkerType.TAG_EXPANSION if HAS_RESOURCE_MONITOR else None,
        "task": "T7",
        "desc": "Tag Expansion",
        "model": "gemma3:4b",
        "interval": 240,
        "batch_size": 3,
        "priority": 2,
        "cpu_only": False,
        "source": "workers",
    },
    "quality_audit": {
        "type": WorkerType.QUALITY_AUDIT if HAS_RESOURCE_MONITOR else None,
        "task": "T8",
        "desc": "Quality Audit",
        "model": "gemma3:4b",
        "interval": 900,
        "batch_size": 5,
        "priority": 1,
        "cpu_only": True,
        "source": "workers",
    },
    "npu_embedding": {
        "type": WorkerType.EMBEDDING if HAS_RESOURCE_MONITOR else None,
        "task": "T9",
        "desc": "NPU Semantic Embedding",
        "model": "all-MiniLM-L6-v2",
        "interval": 60,
        "batch_size": 50,
        "priority": 2,
        "cpu_only": True,   # Runs on NPU, not Ollama GPU
        "source": "npu_embedder",
    },
}


# ═══════════════════════════════════════════════════════════════
# DATABASE HELPERS (fallback if daemon import fails)
# ═══════════════════════════════════════════════════════════════


def _get_db_ro() -> sqlite3.Connection:
    """Get a read-only connection to SSOT."""
    if HAS_DAEMON:
        return get_db_readonly()
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _write_stigmergy(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
) -> str:
    """Write a CloudEvent to stigmergy_events."""
    if HAS_DAEMON:
        return write_stigmergy_event(conn, event_type, subject, data, source=SWARM_SOURCE)

    event_id = hashlib.md5(
        f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()
    ).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": event_id,
        "type": event_type,
        "source": SWARM_SOURCE,
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
        (event_type, now, subject, SWARM_SOURCE, json.dumps(event), content_hash),
    )
    conn.commit()
    return event_id


# ═══════════════════════════════════════════════════════════════
# ENRICHMENT PROGRESS
# ═══════════════════════════════════════════════════════════════

def get_enrichment_progress() -> dict:
    """Get current enrichment coverage from SSOT."""
    try:
        conn = _get_db_ro()
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        missing_bluf = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE bluf IS NULL OR bluf = '---'"
        ).fetchone()[0]
        missing_port = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE port IS NULL"
        ).fetchone()[0]
        missing_doctype = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE doc_type IS NULL"
        ).fetchone()[0]
        lineage_edges = conn.execute("SELECT COUNT(*) FROM lineage").fetchone()[0]
        total_events = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]

        # Swarm-specific: count KG triples and prog summaries
        kg_count = conn.execute(
            """SELECT COUNT(*) FROM documents
               WHERE json_extract(metadata_json, '$.p6_enrichment.kg_triples') IS NOT NULL"""
        ).fetchone()[0]
        progsumm_count = conn.execute(
            """SELECT COUNT(*) FROM documents
               WHERE json_extract(metadata_json, '$.p6_enrichment.summary_3sent') IS NOT NULL"""
        ).fetchone()[0]

        swarm_events = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE source = ?",
            (SWARM_SOURCE,),
        ).fetchone()[0]
        kraken_events = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events WHERE source LIKE '%kraken%'"
        ).fetchone()[0]

        # Embedding stats
        embedding_count = 0
        try:
            embedding_count = conn.execute(
                "SELECT COUNT(*) FROM embeddings"
            ).fetchone()[0]
        except Exception:
            pass  # Table may not exist yet

        conn.close()
        return {
            "total_docs": total,
            "missing_bluf": missing_bluf,
            "missing_port": missing_port,
            "missing_doctype": missing_doctype,
            "lineage_edges": lineage_edges,
            "kg_extractions": kg_count,
            "prog_summaries": progsumm_count,
            "embeddings": embedding_count,
            "total_events": total_events,
            "swarm_events": swarm_events,
            "kraken_events": kraken_events,
            "enrichment_pct": {
                "bluf": round(100 * (total - missing_bluf) / max(total, 1), 1),
                "port": round(100 * (total - missing_port) / max(total, 1), 1),
                "doctype": round(100 * (total - missing_doctype) / max(total, 1), 1),
                "embedding": round(100 * embedding_count / max(total, 1), 1),
            },
        }
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# SWARM WORKER LOOP — Unified worker lifecycle
# ═══════════════════════════════════════════════════════════════

async def swarm_worker_loop(
    name: str,
    worker_key: str,
    worker_fn,
    interval: float,
    priority: int,
    model: str,
    batch_size: int,
    cpu_only: bool,
    orchestrator: Optional[SwarmOrchestrator],
    kraken: Optional[KrakenKeeper],
    dry_run: bool = False,
    single: bool = False,
):
    """
    Unified worker loop with resource-aware scheduling.

    Each iteration:
    1. Check if orchestrator is paused → wait
    2. Check pressure level → skip if priority too low
    3. Acquire VRAM slot (if GPU worker) → skip if no budget
    4. Run the worker function
    5. Release VRAM slot
    6. Log result to stigmergy
    7. Sleep until next cycle (responsive to shutdown)
    """
    cycle = 0

    while True:
        cycle += 1

        # ── Step 1: Check pause state ──
        if orchestrator:
            await orchestrator.wait_if_paused()
            if not orchestrator._running:
                break

        # ── Step 2: Pressure check — skip if too loaded ──
        if orchestrator:
            snap = orchestrator.monitor.last or orchestrator.monitor.sense()
            allowed = orchestrator.select_workers_for_pressure(snap.pressure)
            allowed_types = {w.worker_type for w in allowed}

            worker_def = SWARM_WORKER_DEFS.get(worker_key, {})
            w_type = worker_def.get("type")
            if w_type and w_type not in allowed_types:
                # This worker's priority is too low for current pressure
                if single:
                    print(f"  [{name}] SKIPPED — pressure {snap.pressure.value}, priority {priority} too low")
                    break
                # Short sleep, check again soon
                await asyncio.sleep(min(interval / 4, 30))
                continue

        # ── Step 3: Acquire VRAM slot (GPU workers only) ──
        slot_acquired = False
        if orchestrator and not cpu_only:
            slot_acquired = await orchestrator.slots.acquire_slot(
                model, f"swarm_{worker_key}"
            )
            if not slot_acquired:
                if single:
                    print(f"  [{name}] SKIPPED — no VRAM budget for {model}")
                    break
                await asyncio.sleep(30)
                continue

        # ── Step 4: Run the worker function ──
        t0 = time.time()
        result = {}
        try:
            result = await worker_fn()
            elapsed = round(time.time() - t0, 1)
            errors = result.get("errors", 0) if isinstance(result, dict) else 0

            # Print summary
            summary_parts = []
            if isinstance(result, dict):
                for key in ["enriched", "classified", "extracted", "edges_added", "audited"]:
                    if key in result and result[key]:
                        summary_parts.append(f"{key}={result[key]}")
            summary_str = ", ".join(summary_parts) if summary_parts else "OK"
            print(f"  [{name}] {summary_str} ({elapsed}s)" +
                  (f" [{errors} errors]" if errors else ""))

            # Log to stigmergy
            if not dry_run:
                try:
                    conn = _get_db_rw()
                    _write_stigmergy(
                        conn,
                        f"hfo.gen89.swarm.{worker_key}",
                        f"SWARM:{worker_key}:cycle_{cycle}",
                        {
                            "worker": worker_key,
                            "cycle": cycle,
                            "result": result if isinstance(result, dict) else str(result),
                            "elapsed_s": elapsed,
                            "model": model,
                            "batch_size": batch_size,
                            "priority": priority,
                        },
                    )
                    conn.close()
                except Exception:
                    pass

        except Exception as e:
            elapsed = round(time.time() - t0, 1)
            print(f"  [{name} ERROR] {e} ({elapsed}s)", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

        # ── Step 5: Release VRAM slot ──
        if orchestrator and slot_acquired:
            await orchestrator.slots.release_slot(model)

        # ── Single mode: exit after one cycle ──
        if single:
            break

        # ── Step 6: Sleep with responsive shutdown ──
        for _ in range(int(interval)):
            if orchestrator and not orchestrator._running:
                return
            await asyncio.sleep(1)

        # Periodic GC
        if cycle % 10 == 0:
            gc.collect()


# ═══════════════════════════════════════════════════════════════
# HEARTBEAT — Periodic swarm status to SSOT
# ═══════════════════════════════════════════════════════════════

async def heartbeat_loop(
    orchestrator: Optional[SwarmOrchestrator],
    dry_run: bool = False,
    single: bool = False,
):
    """Emit swarm heartbeat with enrichment progress + resource status."""
    while True:
        progress = get_enrichment_progress()
        resource_status = {}
        if orchestrator:
            snap = orchestrator.monitor.sense()
            resource_status = {
                "pressure": snap.pressure.value,
                "cpu_pct": snap.cpu_pct,
                "ram_free_gb": snap.ram_free_gb,
                "vram_used_gb": snap.vram_used_gb,
                "vram_budget_gb": snap.vram_budget_gb,
                "loaded_models": [m["name"] for m in snap.loaded_models],
                "active_workers": orchestrator.get_active_worker_count(),
                "max_concurrent": orchestrator._max_concurrent,
                "paused": orchestrator._paused,
            }

        heartbeat = {
            "identity": SWARM_IDENTITY,
            "progress": progress,
            "resources": resource_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if not dry_run:
            try:
                conn = _get_db_rw()
                _write_stigmergy(
                    conn,
                    "hfo.gen89.swarm.heartbeat",
                    f"SWARM_HEARTBEAT:{datetime.now(timezone.utc).strftime('%H%M%S')}",
                    heartbeat,
                )
                conn.close()
            except Exception as e:
                print(f"  [HEARTBEAT ERROR] {e}", file=sys.stderr)

        if single:
            return heartbeat

        # Sleep 60s with responsive shutdown
        for _ in range(60):
            if orchestrator and not orchestrator._running:
                return heartbeat
            await asyncio.sleep(1)


# ═══════════════════════════════════════════════════════════════
# WORKER FUNCTION FACTORY — Maps worker keys to callables
# ═══════════════════════════════════════════════════════════════

def build_worker_fn(
    worker_key: str,
    kraken: Optional[KrakenKeeper],
    orchestrator: Optional[SwarmOrchestrator],
    model: str,
    batch_size: int,
    dry_run: bool,
):
    """
    Build the async callable for a given worker key.

    T1-T4 → delegate to KrakenKeeper methods
    T5-T8 → delegate to hfo_p6_kraken_workers functions
    """
    # T1-T4: KrakenKeeper methods
    if worker_key == "bluf" and kraken:
        return kraken.enrich_blufs
    elif worker_key == "port" and kraken:
        return kraken.classify_ports
    elif worker_key == "doctype" and kraken:
        return kraken.classify_doctypes
    elif worker_key == "lineage" and kraken:
        return kraken.mine_lineage

    # T5-T8: Extended workers
    elif worker_key == "progressive_summary" and HAS_EXTENDED_WORKERS:
        async def _run():
            return await progressive_summarization(
                model=model, batch_size=batch_size,
                dry_run=dry_run, orchestrator=orchestrator,
            )
        return _run
    elif worker_key == "knowledge_graph" and HAS_EXTENDED_WORKERS:
        async def _run():
            return await knowledge_graph_extraction(
                model=model, batch_size=batch_size,
                dry_run=dry_run, orchestrator=orchestrator,
            )
        return _run
    elif worker_key == "tag_expansion" and HAS_EXTENDED_WORKERS:
        async def _run():
            return await tag_expansion(
                model=model, batch_size=batch_size,
                dry_run=dry_run, orchestrator=orchestrator,
            )
        return _run
    elif worker_key == "quality_audit" and HAS_EXTENDED_WORKERS:
        async def _run():
            return await quality_audit(
                model=model, batch_size=batch_size,
                dry_run=dry_run, orchestrator=orchestrator,
            )
        return _run
    elif worker_key == "npu_embedding" and HAS_NPU_EMBEDDER:
        async def _run():
            return await npu_embedding_worker(
                batch_size=batch_size,
                dry_run=dry_run, orchestrator=orchestrator,
            )
        return _run

    # Fallback — disabled worker
    return None


# ═══════════════════════════════════════════════════════════════
# MAIN SWARM LOOP
# ═══════════════════════════════════════════════════════════════

async def swarm_loop(
    model: str = P6_MODEL,
    batch_size: int = 3,
    dry_run: bool = False,
    single: bool = False,
    enabled_workers: Optional[set[str]] = None,
):
    """
    Main swarm loop — launches resource monitor + all workers concurrently.
    """
    if enabled_workers is None:
        enabled_workers = set(SWARM_WORKER_DEFS.keys())

    # ── Banner ──
    banner = f"""
  ╔═══════════════════════════════════════════════════════════╗
  ║  P6 KRAKEN SWARM — Devourer of Depths and Dreams         ║
  ║  Port: P6 ASSIMILATE | Spell: CLONE (Necromancy)         ║
  ║  Architecture: 8^1 Resource-Aware Swarm                   ║
  ║  Model: {model:48s} ║
  ║  Mode: {'DRY RUN' if dry_run else ('SINGLE CYCLE' if single else '24/7 SWARM'):48s} ║
  ╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)

    # ── Import status ──
    if _import_errors:
        print("  Import warnings:")
        for err in _import_errors:
            print(f"    ⚠ {err}")
        print()

    # ── Verify Ollama ──
    try:
        import httpx
        with httpx.Client(timeout=5) as c:
            r = c.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code != 200:
                print(f"  [FATAL] Ollama returned {r.status_code}. Exiting.", file=sys.stderr)
                return
    except Exception as e:
        print(f"  [FATAL] Ollama not reachable at {OLLAMA_BASE}: {e}", file=sys.stderr)
        return

    print(f"  Ollama: ONLINE at {OLLAMA_BASE}")
    print(f"  SSOT:   {SSOT_DB} ({SSOT_DB.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  Model:  {model}")
    print(f"  Workers: {', '.join(sorted(enabled_workers))}")
    print(f"  Batch:  {batch_size} docs per worker cycle")

    # ── Initialize components ──
    orchestrator = None
    if HAS_RESOURCE_MONITOR:
        worker_configs = [
            WorkerConfig(
                worker_type=SWARM_WORKER_DEFS[k]["type"],
                model=SWARM_WORKER_DEFS[k]["model"],
                batch_size=SWARM_WORKER_DEFS[k]["batch_size"],
                interval_s=SWARM_WORKER_DEFS[k]["interval"],
                priority=SWARM_WORKER_DEFS[k]["priority"],
                cpu_only=SWARM_WORKER_DEFS[k]["cpu_only"],
            )
            for k in enabled_workers
            if SWARM_WORKER_DEFS[k]["type"] is not None
        ]
        orchestrator = SwarmOrchestrator(
            db_path=SSOT_DB,
            worker_configs=worker_configs,
            dry_run=dry_run,
        )
        # Sync slot manager with Ollama's currently-loaded models
        orchestrator.slots.sync_from_ollama()
        snap = orchestrator.monitor.sense()
        print(f"  Pressure: {snap.pressure.value.upper()}")
        print(f"  CPU: {snap.cpu_pct:.1f}%  RAM free: {snap.ram_free_gb:.1f} GB"
              f"  VRAM: {snap.vram_used_gb:.1f}/{snap.vram_budget_gb:.1f} GB")
        print(f"  Max concurrent workers: {orchestrator._max_concurrent}")
    else:
        print("  Resource monitor: DEGRADED (no psutil or import failure)")

    # ── Initialize KrakenKeeper for T1-T4 ──
    kraken = None
    if HAS_DAEMON:
        kraken = KrakenKeeper(dry_run=dry_run, model=model, batch_size=batch_size)
        print(f"  KrakenKeeper: ONLINE (T1-T4)")
    else:
        print(f"  KrakenKeeper: DEGRADED (import failure)")

    # ── Initial progress report ──
    progress = get_enrichment_progress()
    if "error" not in progress:
        print()
        print(f"  Enrichment baseline:")
        print(f"    BLUFs:        {progress['enrichment_pct']['bluf']:.1f}% ({progress['missing_bluf']} remaining)")
        print(f"    Ports:        {progress['enrichment_pct']['port']:.1f}% ({progress['missing_port']} remaining)")
        print(f"    DocTypes:     {progress['enrichment_pct']['doctype']:.1f}% ({progress['missing_doctype']} remaining)")
        print(f"    Lineage:      {progress['lineage_edges']} edges")
        print(f"    KG Triples:   {progress['kg_extractions']} docs")
        print(f"    Prog Summary: {progress['prog_summaries']} docs")
        print(f"    Events:       {progress['total_events']} total ({progress.get('swarm_events', 0)} swarm)")

    # ── Log swarm start ──
    if not dry_run:
        try:
            conn = _get_db_rw()
            _write_stigmergy(
                conn,
                "hfo.gen89.swarm.start",
                "SWARM_START",
                {
                    "action": "swarm_start",
                    "model": model,
                    "batch_size": batch_size,
                    "enabled_workers": sorted(enabled_workers),
                    "dry_run": dry_run,
                    "single": single,
                    "identity": SWARM_IDENTITY,
                    "initial_progress": progress,
                    "resource_monitor": HAS_RESOURCE_MONITOR,
                    "extended_workers": HAS_EXTENDED_WORKERS,
                    "daemon_core": HAS_DAEMON,
                },
            )
            conn.close()
        except Exception as e:
            print(f"  [WARN] Could not log start: {e}", file=sys.stderr)

    print()

    # ═══════════════════════════════════════════════════════
    # Build worker tasks
    # ═══════════════════════════════════════════════════════

    tasks: list[asyncio.Task] = []

    for wkey in sorted(enabled_workers):
        wdef = SWARM_WORKER_DEFS.get(wkey)
        if not wdef:
            print(f"  [WARN] Unknown worker: {wkey}", file=sys.stderr)
            continue

        # Override model if user specified
        w_model = model if model != P6_MODEL else wdef["model"]
        w_batch = batch_size if batch_size != 3 else wdef["batch_size"]

        worker_fn = build_worker_fn(
            wkey, kraken, orchestrator, w_model, w_batch, dry_run
        )
        if worker_fn is None:
            print(f"  [{wdef['task']}:{wkey}] DISABLED — missing dependencies")
            continue

        name = f"{wdef['task']}:{wkey.upper()}"
        print(f"  [{name}] armed — model={w_model}, interval={wdef['interval']}s, priority={wdef['priority']}")

        task = asyncio.create_task(
            swarm_worker_loop(
                name=name,
                worker_key=wkey,
                worker_fn=worker_fn,
                interval=wdef["interval"],
                priority=wdef["priority"],
                model=w_model,
                batch_size=w_batch,
                cpu_only=wdef["cpu_only"],
                orchestrator=orchestrator,
                kraken=kraken,
                dry_run=dry_run,
                single=single,
            )
        )
        tasks.append(task)

        # Track in orchestrator
        if orchestrator:
            orchestrator._active_workers[f"swarm_{wkey}"] = task

    # ── Heartbeat task ──
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(orchestrator, dry_run, single)
    )
    tasks.append(heartbeat_task)

    # ── Sense loop task (resource monitoring) ──
    if orchestrator and not single:
        sense_task = asyncio.create_task(orchestrator.sense_loop())
        tasks.append(sense_task)

    # ── Governance daemon (resource utilization tracking) ──
    governance = None
    if HAS_GOVERNANCE and not single:
        governance = GovernanceDaemon(dry_run=dry_run)
        gov_sample_task = asyncio.create_task(governance.sample_loop())
        gov_heartbeat_task = asyncio.create_task(governance.heartbeat_loop())
        tasks.append(gov_sample_task)
        tasks.append(gov_heartbeat_task)
        print("  [GOVERNANCE] armed — utilization regime detection active")

    n_extras = sum([
        1,  # heartbeat always
        1 if orchestrator and not single else 0,  # sense_loop
        2 if governance else 0,  # governance sample + heartbeat
    ])
    n_workers = len(tasks) - n_extras
    print(f"\n  Launching {n_workers} workers + heartbeat"
          + (" + sense_loop" if orchestrator and not single else "")
          + (" + governance" if governance else "")
          + (" (single cycle)" if single else " (Ctrl+C to stop)")
          + "\n")

    # ═══════════════════════════════════════════════════════
    # Run all tasks
    # ═══════════════════════════════════════════════════════

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    finally:
        # Stop orchestrator
        if orchestrator:
            orchestrator.stop()
        if kraken:
            kraken.stop()
        if governance:
            governance.stop()
            governance.save_state()

        # Log stop
        if not dry_run:
            try:
                conn = _get_db_rw()
                _write_stigmergy(
                    conn,
                    "hfo.gen89.swarm.stop",
                    "SWARM_STOP",
                    {
                        "action": "swarm_stop",
                        "final_progress": get_enrichment_progress(),
                        "swarm_stats": orchestrator.stats if orchestrator else {},
                        "daemon_stats": dict(kraken.stats) if kraken else {},
                    },
                )
                conn.close()
            except Exception:
                pass

        # Save state
        _save_state(orchestrator, kraken)
        print("\n  Kraken Swarm stopped. The depths remember.\n")


# ═══════════════════════════════════════════════════════════════
# STATE PERSISTENCE
# ═══════════════════════════════════════════════════════════════

def _save_state(
    orchestrator: Optional[SwarmOrchestrator],
    kraken: Optional[KrakenKeeper],
):
    """Persist swarm state to disk for resumption."""
    state = {
        "progress": get_enrichment_progress(),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "swarm_stats": orchestrator.stats if orchestrator else {},
        "daemon_stats": dict(kraken.stats) if kraken else {},
        "resource_snapshot": (
            orchestrator.monitor.sense().to_dict()
            if orchestrator else {}
        ),
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# STATUS DISPLAY
# ═══════════════════════════════════════════════════════════════

def show_status(as_json: bool = False):
    """Display current swarm status."""
    progress = get_enrichment_progress()

    # Resource snapshot
    resource = {}
    if HAS_RESOURCE_MONITOR:
        mon = ResourceMonitor()
        time.sleep(0.5)
        snap = mon.sense()
        resource = snap.to_dict()

    # Saved state
    saved = {}
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)
        except Exception:
            pass

    if as_json:
        print(json.dumps({
            "progress": progress,
            "resources": resource,
            "saved_state": saved,
            "import_status": {
                "resource_monitor": HAS_RESOURCE_MONITOR,
                "extended_workers": HAS_EXTENDED_WORKERS,
                "daemon_core": HAS_DAEMON,
            },
        }, indent=2))
        return

    print("P6 KRAKEN SWARM — Status")
    print("=" * 58)
    print(f"  SSOT:  {SSOT_DB}")
    print(f"  State: {STATE_FILE}")
    print()

    # Modules
    print("  Module Status:")
    print(f"    Resource Monitor: {'✓' if HAS_RESOURCE_MONITOR else '✗'}")
    print(f"    Extended Workers: {'✓' if HAS_EXTENDED_WORKERS else '✗'}")
    print(f"    Daemon Core:     {'✓' if HAS_DAEMON else '✗'}")
    if _import_errors:
        for err in _import_errors:
            print(f"    ⚠ {err}")
    print()

    # Resources
    if resource:
        print("  Resources:")
        print(f"    Pressure: {resource.get('pressure', '?').upper()}")
        print(f"    CPU:  {resource.get('cpu_pct', 0):.1f}% ({len(resource.get('cpu_per_core', []))} cores)")
        print(f"    RAM:  {resource.get('ram_free_gb', 0):.1f} GB free / {resource.get('ram_total_gb', 0):.1f} GB total")
        print(f"    VRAM: {resource.get('vram_used_gb', 0):.1f} / {resource.get('vram_budget_gb', 0):.1f} GB budget")
        models = resource.get("loaded_models", [])
        if models:
            for m in models:
                print(f"      {m.get('name', '?'):30s} {m.get('vram_gb', 0):.1f} GB")
        print()

    # Enrichment
    if "error" not in progress:
        print("  Enrichment Coverage:")
        print(f"    BLUFs:        {progress['enrichment_pct']['bluf']:5.1f}%  ({progress['missing_bluf']:,} remaining)")
        print(f"    Ports:        {progress['enrichment_pct']['port']:5.1f}%  ({progress['missing_port']:,} remaining)")
        print(f"    DocTypes:     {progress['enrichment_pct']['doctype']:5.1f}%  ({progress['missing_doctype']:,} remaining)")
        print(f"    Lineage:      {progress['lineage_edges']:,} edges")
        print(f"    KG Triples:   {progress['kg_extractions']:,} docs enriched")
        print(f"    Prog Summary: {progress['prog_summaries']:,} docs enriched")
        print(f"    Events:       {progress['total_events']:,} total ({progress.get('swarm_events', 0)} swarm, {progress.get('kraken_events', 0)} kraken)")
    print()

    # Workers
    print("  Worker Definitions (8^1 swarm):")
    for wkey, wdef in SWARM_WORKER_DEFS.items():
        status = "✓" if wkey in {"bluf", "port", "doctype", "lineage"} or HAS_EXTENDED_WORKERS else "✗"
        print(f"    {status} {wdef['task']:3s} {wdef['desc']:35s} P{wdef['priority']} model={wdef['model']} interval={wdef['interval']}s")
    print()

    # Saved state
    if saved:
        print("  Last Run:")
        d_stats = saved.get("daemon_stats", {})
        s_stats = saved.get("swarm_stats", {})
        print(f"    Saved at:         {saved.get('saved_at', '?')}")
        if d_stats:
            print(f"    BLUFs generated:  {d_stats.get('blufs_generated', 0)}")
            print(f"    Ports classified: {d_stats.get('ports_classified', 0)}")
            print(f"    Ollama calls:     {d_stats.get('ollama_calls', 0)}")
        if s_stats:
            print(f"    Sense cycles:     {s_stats.get('total_sense_cycles', 0)}")
            print(f"    Throttle events:  {s_stats.get('throttle_events', 0)}")
            print(f"    Yield events:     {s_stats.get('yield_events', 0)}")
    else:
        print("  No previous swarm state found.")

    print(f"\n  Everything that dies feeds the knowledge graph. The swarm devours.")


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P6 KRAKEN SWARM — Resource-Aware Knowledge Enrichment (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hfo_p6_kraken_swarm.py                           # 24/7 swarm mode
  python hfo_p6_kraken_swarm.py --once                    # Single cycle
  python hfo_p6_kraken_swarm.py --dry-run --once          # Dry run
  python hfo_p6_kraken_swarm.py --workers bluf,port,knowledge_graph
  python hfo_p6_kraken_swarm.py --model qwen3:8b          # Override model
  python hfo_p6_kraken_swarm.py --status                  # Show progress
  python hfo_p6_kraken_swarm.py --status --json           # JSON status

Worker types:
  bluf                 T1  BLUF Generation (Priority 3)
  port                 T2  Port Classification (Priority 3)
  doctype              T3  Doc Type Classification (Priority 2)
  lineage              T4  Lineage Mining (Priority 2)
  progressive_summary  T5  Progressive Summarization (Priority 1)
  knowledge_graph      T6  Knowledge Graph Extraction (Priority 1)
  tag_expansion        T7  Tag Expansion (Priority 2)
  quality_audit        T8  Quality Audit — CPU only (Priority 1)

Priority scheduling:
  IDLE/NOMINAL → All 8 workers    THROTTLED → Priority 3 only (2 of 8)
  ELEVATED     → Priority 2+ (6)  CRITICAL  → All paused
""",
    )
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="No writes to SSOT")
    parser.add_argument("--workers", type=str, default=None,
                        help="Comma-separated worker types (default: all)")
    parser.add_argument("--model", type=str, default=P6_MODEL,
                        help=f"Override Ollama model (default: {P6_MODEL})")
    parser.add_argument("--batch-size", type=int, default=3,
                        help="Docs per worker cycle (default: 3)")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--json", action="store_true", help="JSON output (with --status)")

    args = parser.parse_args()

    if args.status:
        show_status(args.json)
        return

    # Parse workers
    enabled_workers = None
    if args.workers:
        enabled_workers = set(args.workers.split(","))
        invalid = enabled_workers - set(SWARM_WORKER_DEFS.keys())
        if invalid:
            print(f"  [ERROR] Unknown workers: {invalid}")
            print(f"  Valid: {', '.join(SWARM_WORKER_DEFS.keys())}")
            sys.exit(1)

    # Signal handling
    _stop_flag = {"value": False}

    def handle_signal(signum, frame):
        if _stop_flag["value"]:
            print("\n  Force quit.")
            sys.exit(1)
        _stop_flag["value"] = True
        print(f"\n  Signal {signum} received. Stopping swarm gracefully...")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    asyncio.run(swarm_loop(
        model=args.model,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        single=args.once,
        enabled_workers=enabled_workers,
    ))


if __name__ == "__main__":
    main()
