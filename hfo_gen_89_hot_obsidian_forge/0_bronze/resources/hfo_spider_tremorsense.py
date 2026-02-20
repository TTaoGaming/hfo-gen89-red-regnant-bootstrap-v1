#!/usr/bin/env python3
"""
hfo_spider_tremorsense.py — Social Spider Tremorsense Digest Engine
====================================================================
8 spiders (one per octree port) sense the SSOT via FTS5, then each spider
passes its observations through a local Ollama model to produce a
port-specific intelligence digest.  Results are fused into an 8-port
heatmap and written to stigmergy_events.

Architecture — Two Viable Options (REFERENCE doc has full analysis):

  OPTION A — ThreadPoolExecutor parallel spiders (fast, high VRAM)
  OPTION B — Sequential pipeline with stigmergy chaining (slow, low VRAM)

This implementation supports BOTH via --mode parallel|sequential.

Biology:
  Social spiders use TREMORSENSE — vibrations in the shared web —
  to coordinate without direct communication.  Each spider "plucks"
  the SSOT by running an FTS5 query (its domain-specific vibration),
  then interprets the vibration with its Ollama model (local LLM as
  the spider's nervous system).  The combined web vibration pattern
  is the heatmap digest.

Usage:
    # 4-spider parallel (default: P0, P2, P4, P6 — Galois dyad representatives)
    python hfo_spider_tremorsense.py --probe "what is the safety spine?"

    # All 8 spiders sequential (lower VRAM)
    python hfo_spider_tremorsense.py --probe "what are my next priorities?" --mode sequential --spiders 8

    # Custom ports
    python hfo_spider_tremorsense.py --probe "omega roadmap" --ports P3,P4,P5,P7

    # Dry-run (FTS only, no Ollama)
    python hfo_spider_tremorsense.py --probe "mission thread" --dry-run

Medallion: bronze
Port: P0 OBSERVE (primary) + P6 ASSIMILATE (storage)
Schema: hfo.gen89.spider_tremorsense.v1
"""

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

import threading

import httpx

# ---------------------------------------------------------------------------
# Resource Governance — Ollama Semaphore
# ---------------------------------------------------------------------------
# Only ONE spider may call Ollama at a time. Parallel mode parallelizes the
# FTS5/SQLite sensing phase but serializes LLM inference to avoid VRAM
# thrashing (model unload/reload storms). The semaphore is the spider's
# "web tension" — only one vibration can propagate at a time.

_OLLAMA_SEMAPHORE = threading.Semaphore(1)

# ---------------------------------------------------------------------------
# Path Resolution
# ---------------------------------------------------------------------------

def _find_root():
    for anchor in [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]:
        d = anchor
        for _ in range(10):
            if os.path.isfile(os.path.join(d, "AGENTS.md")):
                return d
            d = os.path.dirname(d)
    return os.getcwd()

HFO_ROOT = _find_root()
DB_PATH = os.path.join(
    HFO_ROOT,
    "hfo_gen_89_hot_obsidian_forge", "2_gold", "resources",
    "hfo_gen89_ssot.sqlite"
)
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# ---------------------------------------------------------------------------
# Port → Spider Mapping
# ---------------------------------------------------------------------------

SPIDER_REGISTRY = {
    "P0": {
        "commander": "Lidless Legion",
        "title": "Watcher of Whispers and Wrath",
        "domain": "sensing, observation, reconnaissance, eval, benchmarking",
        "powerword": "OBSERVE",
        "spell": "TRUE SEEING",
        "fts_terms": "observe sense eval harness benchmark reconnaissance perception",
        "model": "gemma3:4b",
    },
    "P1": {
        "commander": "Web Weaver",
        "title": "Binder of Blood and Breath",
        "domain": "data fabric, bridges, shared state, integration, API",
        "powerword": "BRIDGE",
        "spell": "FORBIDDANCE",
        "fts_terms": "bridge integration API shared data fabric web federation",
        "model": "qwen2.5:3b",
    },
    "P2": {
        "commander": "Mirror Magus",
        "title": "Maker of Myths and Meaning",
        "domain": "creation, code generation, shaping, chimera loop, SBE",
        "powerword": "SHAPE",
        "spell": "GENESIS",
        "fts_terms": "shape create generate chimera evolution SBE specification",
        "model": "qwen2.5-coder:7b",
    },
    "P3": {
        "commander": "Harmonic Hydra",
        "title": "Harbinger of Harmony and Havoc",
        "domain": "delivery, injection, payload, Touch2D, whiteboard, omega",
        "powerword": "INJECT",
        "spell": "GATE",
        "fts_terms": "inject deliver payload Touch2D whiteboard omega spatial",
        "model": "qwen3:8b",
    },
    "P4": {
        "commander": "Red Regnant",
        "title": "Singer of Strife and Splendor",
        "domain": "adversarial, red team, disruption, testing, PREY8 gates",
        "powerword": "DISRUPT",
        "spell": "WEIRD",
        "fts_terms": "disrupt adversarial red team PREY8 gates mutation testing",
        "model": "deepseek-r1:8b",
    },
    "P5": {
        "commander": "Pyre Praetorian",
        "title": "Dancer of Death and Dawn",
        "domain": "defense, immunization, contingency, antifragile, resurrection",
        "powerword": "IMMUNIZE",
        "spell": "CONTINGENCY",
        "fts_terms": "immunize defend contingency antifragile resurrection safety",
        "model": "llama3.2:3b",
    },
    "P6": {
        "commander": "Kraken Keeper",
        "title": "Devourer of Depths and Dreams",
        "domain": "memory, learning, assimilation, knowledge extraction, MAP-Elites",
        "powerword": "ASSIMILATE",
        "spell": "CLONE",
        "fts_terms": "assimilate memory learn knowledge extraction stigmergy",
        "model": "deepseek-r1:8b",
    },
    "P7": {
        "commander": "Spider Sovereign",
        "title": "Summoner of Seals and Spheres",
        "domain": "navigation, C2, steering, Meadows leverage, orchestration",
        "powerword": "NAVIGATE",
        "spell": "TIME STOP",
        "fts_terms": "navigate steer command orchestrate Meadows leverage roadmap",
        "model": "qwen3:8b",
    },
}


# ---------------------------------------------------------------------------
# SSOT Queries (the "web vibrations")
# ---------------------------------------------------------------------------

def fts_search(query: str, limit: int = 8) -> list[dict]:
    """Run FTS5 search against SSOT documents."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT d.id, d.title, d.bluf, d.source, d.port, d.doc_type,
                   d.word_count, d.tags
            FROM documents d
            WHERE d.id IN (
                SELECT rowid FROM documents_fts
                WHERE documents_fts MATCH ?
            )
            LIMIT ?
        """, (query, limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_port_stigmergy(port: str, limit: int = 5) -> list[dict]:
    """Get recent stigmergy events mentioning a port."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT id, event_type, timestamp, subject,
                   substr(data_json, 1, 500) as data_preview
            FROM stigmergy_events
            WHERE data_json LIKE ?
            ORDER BY id DESC
            LIMIT ?
        """, (f'%"{port}"%', limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_mission_state_for_port(port: str) -> list[dict]:
    """Get mission_state elites for a specific port."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT thread_key, title, fitness, mutation_confidence,
                   status, era, thread, meadows_level
            FROM mission_state
            WHERE port = ? AND status != 'archived'
            ORDER BY fitness DESC
        """, (port,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_doc_count() -> int:
    """Total SSOT document count."""
    if not os.path.exists(DB_PATH):
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Ollama Interface
# ---------------------------------------------------------------------------

def preflight_check() -> dict:
    """Pre-flight resource audit before running spiders.
    
    Checks Ollama is alive, what models are loaded, and estimates
    whether the requested models will fit.
    """
    result = {
        "ollama_alive": False,
        "loaded_models": [],
        "available_models": [],
        "vram_estimate_gb": 0,
    }
    try:
        with httpx.Client(timeout=5) as client:
            # Check running models
            r = client.get(f"{OLLAMA_BASE}/api/ps")
            r.raise_for_status()
            data = r.json()
            result["ollama_alive"] = True
            loaded = data.get("models", [])
            result["loaded_models"] = [
                {
                    "name": m.get("name", "?"),
                    "size_gb": round(m.get("size", 0) / 1e9, 2),
                    "vram_gb": round(m.get("size_vram", 0) / 1e9, 2),
                }
                for m in loaded
            ]
            result["vram_estimate_gb"] = sum(
                m.get("size_vram", 0) / 1e9 for m in loaded
            )

            # List available models
            r2 = client.get(f"{OLLAMA_BASE}/api/tags")
            if r2.status_code == 200:
                models = r2.json().get("models", [])
                result["available_models"] = [
                    m.get("name", "?") for m in models
                ]
    except Exception as e:
        result["error"] = str(e)
    return result


def ollama_generate(model: str, prompt: str, system: str = "",
                    timeout: float = 180) -> dict:
    """Call Ollama generate API.
    
    RESOURCE GOVERNANCE: Acquires _OLLAMA_SEMAPHORE before calling.
    Only one spider can talk to Ollama at a time to avoid VRAM thrashing.
    """
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 1024, "temperature": 0.3},
    }
    if system:
        payload["system"] = system

    # Acquire semaphore — only one Ollama call at a time
    _OLLAMA_SEMAPHORE.acquire()
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return {
                "response": data.get("response", ""),
                "total_duration_ms": data.get("total_duration", 0) / 1e6,
                "eval_count": data.get("eval_count", 0),
                "model": data.get("model", model),
                "done": data.get("done", False),
            }
    except httpx.ReadTimeout:
        return {"response": f"[TIMEOUT after {timeout}s]", "error": f"timeout_{timeout}s",
                "model": model, "done": False}
    except Exception as e:
        return {"response": f"[ERROR: {e}]", "error": str(e),
                "model": model, "done": False}
    finally:
        _OLLAMA_SEMAPHORE.release()


# ---------------------------------------------------------------------------
# Spider — one per port
# ---------------------------------------------------------------------------

@dataclass
class SpiderResult:
    """Result from a single spider's tremorsense."""
    port: str
    commander: str
    model: str
    probe: str
    fts_hits: int
    fts_titles: list[str]
    mission_elites: list[dict]
    digest: str           # LLM-generated digest
    signal_strength: float  # 0.0-1.0 — how much this port resonates
    latency_ms: float
    error: Optional[str] = None


def build_spider_prompt(port: str, probe: str, spider_info: dict,
                        fts_results: list[dict],
                        mission_elites: list[dict],
                        stig_events: list[dict]) -> str:
    """Build the prompt for a spider's Ollama call."""
    doc_summaries = []
    for d in fts_results[:6]:
        doc_summaries.append(
            f"  - [{d['id']}] {d.get('title', '?')[:80]} "
            f"(src={d.get('source','?')}, port={d.get('port','?')}, "
            f"words={d.get('word_count',0)})"
        )
    docs_block = "\n".join(doc_summaries) if doc_summaries else "  (no FTS hits)"

    elite_summaries = []
    for e in mission_elites[:4]:
        elite_summaries.append(
            f"  - {e['thread_key']}: {e.get('title','?')[:60]} "
            f"(fitness={e.get('fitness',0):.2f}, status={e.get('status','?')})"
        )
    elite_block = "\n".join(elite_summaries) if elite_summaries else "  (no tasks at this port)"

    stig_summaries = []
    for s in stig_events[:3]:
        stig_summaries.append(
            f"  - [{s['id']}] {s.get('event_type','?')} → {s.get('subject','?')} "
            f"({s.get('timestamp','?')[:19]})"
        )
    stig_block = "\n".join(stig_summaries) if stig_summaries else "  (no recent events)"

    prompt = f"""You are {spider_info['commander']} ({port} {spider_info['powerword']}).
Your domain: {spider_info['domain']}.
Your signature spell: {spider_info['spell']}.

OPERATOR PROBE: "{probe}"

I have sensed the following vibrations in the web:

DOCUMENTS (FTS5 hits for your domain):
{docs_block}

MISSION STATE (MAP-Elites grid elites at {port}):
{elite_block}

RECENT STIGMERGY (events touching {port}):
{stig_block}

INSTRUCTIONS:
1. In 2-3 sentences, summarize what this port's domain reveals about the probe.
2. Rate signal_strength 0.0-1.0 (how much your domain resonates with the probe).
3. List 1-2 key items the operator should know from your port's perspective.
4. Suggest one next action for this port.

FORMAT your response EXACTLY as:
DIGEST: <your 2-3 sentence summary>
SIGNAL: <float 0.0-1.0>
KEY_ITEMS: <comma-separated items>
NEXT_ACTION: <one action>
"""
    return prompt


def parse_spider_response(text: str) -> tuple[str, float, str, str]:
    """Parse structured spider response into components."""
    digest = ""
    signal = 0.5
    key_items = ""
    next_action = ""

    for line in text.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("DIGEST:"):
            digest = line[7:].strip()
        elif line.upper().startswith("SIGNAL:"):
            try:
                val = line[7:].strip().split()[0]
                signal = max(0.0, min(1.0, float(val)))
            except (ValueError, IndexError):
                signal = 0.5
        elif line.upper().startswith("KEY_ITEMS:"):
            key_items = line[10:].strip()
        elif line.upper().startswith("NEXT_ACTION:"):
            next_action = line[12:].strip()
        elif not digest and line and not line.startswith("#"):
            # Fallback: treat first substantial line as digest
            digest = line

    if not digest:
        digest = text[:200].strip()

    return digest, signal, key_items, next_action


def run_spider(port: str, probe: str, dry_run: bool = False) -> SpiderResult:
    """Run a single spider's tremorsense cycle."""
    spider_info = SPIDER_REGISTRY.get(port, SPIDER_REGISTRY["P0"])
    t0 = time.time()

    # 1. Sense: FTS5 search with port-specific terms + user probe
    combined_query = f"{spider_info['fts_terms']} {probe}"
    # FTS5 needs clean tokens — take up to 10 terms
    tokens = combined_query.split()[:10]
    fts_query = " OR ".join(tokens)
    fts_results = fts_search(fts_query, limit=8)

    # 2. Sense: mission state for this port
    mission_elites = get_mission_state_for_port(port)

    # 3. Sense: recent stigmergy for this port
    stig_events = get_port_stigmergy(port, limit=5)

    fts_titles = [d.get("title", "?")[:60] for d in fts_results]

    if dry_run:
        return SpiderResult(
            port=port,
            commander=spider_info["commander"],
            model=spider_info["model"],
            probe=probe,
            fts_hits=len(fts_results),
            fts_titles=fts_titles,
            mission_elites=mission_elites,
            digest=f"[DRY RUN] {len(fts_results)} FTS hits, {len(mission_elites)} elites",
            signal_strength=len(fts_results) / 8.0,
            latency_ms=(time.time() - t0) * 1000,
        )

    # 4. Interpret: build prompt and call Ollama
    system_prompt = (
        f"You are {spider_info['commander']}, {spider_info['title']}. "
        f"Port {port} {spider_info['powerword']}. "
        f"Domain: {spider_info['domain']}. "
        f"You are one of 8 social spiders sensing a shared web (the HFO SSOT database). "
        f"Be concise. Follow the format exactly."
    )
    user_prompt = build_spider_prompt(
        port, probe, spider_info, fts_results, mission_elites, stig_events
    )

    result = ollama_generate(
        model=spider_info["model"],
        prompt=user_prompt,
        system=system_prompt,
        timeout=120,
    )

    latency = (time.time() - t0) * 1000
    error = result.get("error")

    if error:
        return SpiderResult(
            port=port,
            commander=spider_info["commander"],
            model=spider_info["model"],
            probe=probe,
            fts_hits=len(fts_results),
            fts_titles=fts_titles,
            mission_elites=mission_elites,
            digest=f"[ERROR: {error}]",
            signal_strength=0.0,
            latency_ms=latency,
            error=error,
        )

    digest, signal, key_items, next_action = parse_spider_response(
        result["response"]
    )

    return SpiderResult(
        port=port,
        commander=spider_info["commander"],
        model=spider_info["model"],
        probe=probe,
        fts_hits=len(fts_results),
        fts_titles=fts_titles,
        mission_elites=mission_elites,
        digest=f"{digest} KEY: {key_items} NEXT: {next_action}",
        signal_strength=signal,
        latency_ms=latency,
    )


# ---------------------------------------------------------------------------
# Tremorsense Digest — the fusion heatmap
# ---------------------------------------------------------------------------

@dataclass
class TremorsenseDigest:
    """Fused 8-port heatmap digest from social spider tremorsense."""
    probe: str
    mode: str  # "parallel" or "sequential"
    spider_count: int
    results: list[SpiderResult]
    total_latency_ms: float
    heatmap: dict  # port → signal_strength
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def run_tremorsense_parallel(probe: str, ports: list[str],
                             dry_run: bool = False,
                             max_workers: int = 4) -> TremorsenseDigest:
    """OPTION A: Run spiders in parallel via ThreadPoolExecutor."""
    t0 = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_spider, port, probe, dry_run): port
            for port in ports
        }
        for future in as_completed(futures):
            port = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(SpiderResult(
                    port=port,
                    commander=SPIDER_REGISTRY.get(port, {}).get("commander", "?"),
                    model="?",
                    probe=probe,
                    fts_hits=0,
                    fts_titles=[],
                    mission_elites=[],
                    digest=f"[EXCEPTION: {e}]",
                    signal_strength=0.0,
                    latency_ms=0,
                    error=str(e),
                ))

    # Sort by port order
    results.sort(key=lambda r: r.port)
    total_latency = (time.time() - t0) * 1000
    heatmap = {r.port: r.signal_strength for r in results}

    return TremorsenseDigest(
        probe=probe,
        mode="parallel",
        spider_count=len(results),
        results=results,
        total_latency_ms=total_latency,
        heatmap=heatmap,
    )


def run_tremorsense_sequential(probe: str, ports: list[str],
                               dry_run: bool = False) -> TremorsenseDigest:
    """OPTION B: Run spiders sequentially — each reads previous spider's trace."""
    t0 = time.time()
    results = []
    accumulated_context = []

    for port in ports:
        # Each spider after the first gets the prior spider summaries
        if accumulated_context:
            augmented_probe = (
                f"{probe}\n\n"
                f"PRIOR SPIDER OBSERVATIONS:\n"
                + "\n".join(f"  [{r.port}] signal={r.signal_strength:.1f}: {r.digest[:100]}"
                            for r in accumulated_context[-3:])
            )
        else:
            augmented_probe = probe

        result = run_spider(port, augmented_probe, dry_run)
        results.append(result)
        accumulated_context.append(result)

    total_latency = (time.time() - t0) * 1000
    heatmap = {r.port: r.signal_strength for r in results}

    return TremorsenseDigest(
        probe=probe,
        mode="sequential",
        spider_count=len(results),
        results=results,
        total_latency_ms=total_latency,
        heatmap=heatmap,
    )


# ---------------------------------------------------------------------------
# Stigmergy Writer — log the tremorsense to SSOT
# ---------------------------------------------------------------------------

def write_tremorsense_event(digest: TremorsenseDigest) -> int:
    """Write the tremorsense digest to stigmergy_events."""
    if not os.path.exists(DB_PATH):
        return -1

    ts = datetime.now(timezone.utc).isoformat()
    event_data = {
        "probe": digest.probe,
        "mode": digest.mode,
        "spider_count": digest.spider_count,
        "total_latency_ms": round(digest.total_latency_ms, 1),
        "heatmap": digest.heatmap,
        "spiders": [
            {
                "port": r.port,
                "commander": r.commander,
                "model": r.model,
                "signal_strength": r.signal_strength,
                "fts_hits": r.fts_hits,
                "digest": r.digest[:300],
                "latency_ms": round(r.latency_ms, 1),
            }
            for r in digest.results
        ],
    }

    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": "hfo.gen89.spider.tremorsense_digest",
        "source": f"hfo_spider_tremorsense_gen{GEN}",
        "subject": "tremorsense-digest",
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": event_data,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event["type"], ts, event["subject"], event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_heatmap(digest: TremorsenseDigest):
    """Print the 8-port heatmap with signal bars."""
    print(f"\n{'='*72}")
    print(f"  SOCIAL SPIDER TREMORSENSE — {digest.spider_count}-Spider {digest.mode.upper()} Digest")
    print(f"  Probe: {digest.probe[:60]}")
    print(f"  Time: {digest.total_latency_ms/1000:.1f}s total")
    print(f"{'='*72}")

    # Port order
    all_ports = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]
    max_bar = 30

    print(f"\n  HEATMAP (signal strength per port):\n")
    for port in all_ports:
        sig = digest.heatmap.get(port, 0.0)
        bar_len = int(sig * max_bar)
        bar = "#" * bar_len + "." * (max_bar - bar_len)
        info = SPIDER_REGISTRY.get(port, {})
        cmd_name = info.get("commander", "?")[:16]
        label = f"{port} {info.get('powerword', '?'):10s}"
        print(f"    {label} |{bar}| {sig:.2f}  ({cmd_name})")

    # Detail per spider
    print(f"\n  {'─'*68}")
    print(f"  SPIDER REPORTS:")
    print(f"  {'─'*68}")
    for r in sorted(digest.results, key=lambda x: x.signal_strength, reverse=True):
        info = SPIDER_REGISTRY.get(r.port, {})
        print(f"\n  [{r.port}] {info.get('commander', '?')} ({r.model})")
        print(f"       Signal: {r.signal_strength:.2f} | FTS hits: {r.fts_hits} | "
              f"Latency: {r.latency_ms/1000:.1f}s")
        # Wrap digest text
        wrapped = textwrap.fill(r.digest[:300], width=64, initial_indent="       ",
                                subsequent_indent="       ")
        print(wrapped)

    print(f"\n{'='*72}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Social Spider Tremorsense — 8-port SSOT digest engine"
    )
    parser.add_argument("--probe", required=True,
                        help="The operator's question or intent to sense")
    parser.add_argument("--mode", choices=["parallel", "sequential"],
                        default="parallel",
                        help="Execution mode (default: parallel)")
    parser.add_argument("--ports", default=None,
                        help="Comma-separated ports (default: P0,P2,P4,P6)")
    parser.add_argument("--spiders", type=int, default=4,
                        help="Number of spiders (4=dyad reps, 8=all ports)")
    parser.add_argument("--dry-run", action="store_true",
                        help="FTS only, no Ollama calls")
    parser.add_argument("--no-stigmergy", action="store_true",
                        help="Don't write result to stigmergy_events")
    parser.add_argument("--max-workers", type=int, default=2,
                        help="Thread pool size for parallel mode (default: 2)")
    parser.add_argument("--model", default=None,
                        help="Override: use ONE model for all spiders (avoids VRAM thrashing)")
    parser.add_argument("--timeout", type=float, default=180,
                        help="Per-spider Ollama timeout in seconds (default: 180)")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="Skip pre-flight resource check")
    args = parser.parse_args()

    # ── Pre-flight resource check ──
    if not args.skip_preflight and not args.dry_run:
        print("[PREFLIGHT] Checking Ollama resource state...")
        pf = preflight_check()
        if not pf["ollama_alive"]:
            print(f"[PREFLIGHT] ABORT: Ollama not responding ({pf.get('error','?')})")
            sys.exit(1)
        loaded = pf["loaded_models"]
        if loaded:
            for m in loaded:
                print(f"  Loaded: {m['name']} ({m['vram_gb']:.1f} GB VRAM)")
            print(f"  Total VRAM in use: ~{pf['vram_estimate_gb']:.1f} GB")
        else:
            print("  No models currently loaded (cold start)")
        print(f"  Available: {len(pf['available_models'])} models")
        print(f"[PREFLIGHT] Ollama v ready. Semaphore: 1 (serial LLM calls)")

    # ── Model override for VRAM governance ──
    if args.model:
        print(f"[GOVERNANCE] Single-model mode: ALL spiders use {args.model}")
        for port_key in SPIDER_REGISTRY:
            SPIDER_REGISTRY[port_key]["model"] = args.model

    # Determine ports
    if args.ports:
        ports = [p.strip().upper() for p in args.ports.split(",")]
    elif args.spiders >= 8:
        ports = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]
    else:
        # Default 4: Galois dyad representatives (one from each pair)
        ports = ["P0", "P2", "P4", "P6"]

    print(f"[TREMORSENSE] Activating {len(ports)} spiders: {', '.join(ports)}")
    print(f"[TREMORSENSE] Mode: {args.mode} | Probe: {args.probe[:60]}")
    print(f"[TREMORSENSE] Models: {', '.join(SPIDER_REGISTRY[p]['model'] for p in ports)}")

    if args.mode == "parallel":
        digest = run_tremorsense_parallel(
            args.probe, ports, dry_run=args.dry_run,
            max_workers=args.max_workers
        )
    else:
        digest = run_tremorsense_sequential(
            args.probe, ports, dry_run=args.dry_run
        )

    print_heatmap(digest)

    # Write to stigmergy
    if not args.no_stigmergy and not args.dry_run:
        row_id = write_tremorsense_event(digest)
        print(f"\n[STIGMERGY] Digest written to stigmergy_events (row {row_id})")

    return digest


if __name__ == "__main__":
    main()
