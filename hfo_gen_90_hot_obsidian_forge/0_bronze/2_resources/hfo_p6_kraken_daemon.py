#!/usr/bin/env python3
"""
hfo_p6_kraken_daemon.py — P6 Kraken Keeper 24/7 SSOT Enrichment Daemon
========================================================================
v1.0 | Gen90 | Port: P6 ASSIMILATE | Commander: Kraken Keeper
Powerword: ASSIMILATE | Spell: CLONE | School: Necromancy
Title: Devourer of Depths and Dreams | Trigram: ☶ Gen (Mountain)

PURPOSE:
    Continuous background daemon that incrementally improves the SSOT
    through safe, additive enrichment powered by local Ollama models.

    This is the P6 ASSIMILATE daemon — the knowledge metabolism of HFO.
    It devours the corpus, extracts insights, and stores them back.
    Every cycle, the SSOT gets a little richer. Stigmergic accumulation.

ENRICHMENT TASKS (5 concurrent asyncio loops):
    T1 — BLUF Generation    (every 120s)  Summarize docs lacking BLUFs
    T2 — Port Classification (every 180s)  Assign octree ports to unclassified docs
    T3 — Doc Type Classify   (every 300s)  Assign doc_type to untyped docs
    T4 — Lineage Mining      (every 600s)  Discover cross-references between docs
    T5 — Heartbeat + Stats   (every  60s)  Daemon alive signal + progress report
    T6 — Stigmergy Rollup    (every 3600s) Auto-rollup stigmergy into daily/weekly summaries

SAFETY GUARANTEES:
    - ADDITIVE ONLY: Never deletes, never overwrites existing non-null fields
    - BLUF: Only touches docs where bluf IS NULL OR bluf = '---'
    - Port: Only touches docs where port IS NULL
    - Doc_type: Only touches docs where doc_type IS NULL
    - Lineage: Only INSERTs new edges, never DELETEs
    - Every write is logged as a CloudEvent to stigmergy_events
    - Dry-run mode available for testing

PROVIDERS (dual-engine, Ollama primary):
    - Ollama gemma3:4b       — all enrichment (fastest local, no think-tags)
    - Gemini (optional)      — grounded web research when quota allows

USAGE:
    # Start continuous daemon (24/7 mode)
    python hfo_p6_kraken_daemon.py

    # Run one enrichment cycle then exit
    python hfo_p6_kraken_daemon.py --once

    # Dry run (detect targets but don't write)
    python hfo_p6_kraken_daemon.py --dry-run

    # Specific tasks only
    python hfo_p6_kraken_daemon.py --tasks bluf,port,doctype

    # Custom model (any Ollama model)
    python hfo_p6_kraken_daemon.py --model qwen3:8b

    # Custom intervals (seconds)
    python hfo_p6_kraken_daemon.py --bluf-interval 120 --port-interval 180

    # Show status / progress
    python hfo_p6_kraken_daemon.py --status

Medallion: bronze
Port: P6 ASSIMILATE
Pointer key: daemon.p6_kraken
"""

from __future__ import annotations

import argparse
import asyncio
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

import httpx
from hfo_ssot_write import get_db_readwrite

# Resource governor — hard 80% GPU ceiling for background daemons
# Optional import: governor works standalone, daemon works without it
try:
    _rg_dir = str(Path(__file__).resolve().parent)
    if _rg_dir not in sys.path:
        sys.path.insert(0, _rg_dir)
    from hfo_resource_governor import (
        wait_for_gpu_headroom as _wait_gpu_headroom,
        evict_idle_ollama_models as _evict_ollama,
        start_background_monitor as _start_rg_monitor,
        get_resource_snapshot as _get_resource_snapshot,
        VRAM_BUDGET_GB as _VRAM_BUDGET_GB,
    )
    _RESOURCE_GOVERNOR_AVAILABLE = True
except ImportError:
    _RESOURCE_GOVERNOR_AVAILABLE = False
    def _wait_gpu_headroom(*a, **kw): return True   # no-op fallback
    def _evict_ollama(*a, **kw): return 0
    def _start_rg_monitor(*a, **kw): pass
    def _get_resource_snapshot(): return None
    _VRAM_BUDGET_GB = 10.0

# ═══════════════════════════════════════════════════════════════
# PATH RESOLUTION VIA PAL
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
POINTERS_FILE = HFO_ROOT / "hfo_gen90_pointers_blessed.json"


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
    SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite"

GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
P6_MODEL = os.environ.get("P6_OLLAMA_MODEL", "lfm2.5-thinking:1.2b")  # 0.7 GB VRAM, 47 tok/s — tiny-first to save GPU headroom
P6_SOURCE = f"hfo_p6_kraken_daemon_gen{GEN}"
STATE_FILE = HFO_ROOT / ".hfo_p6_kraken_state.json"
_NPU_STATE_PATH = HFO_ROOT / ".hfo_npu_state.json"  # read by P0 TRUE_SEEING

# ═══════════════════════════════════════════════════════════════
# KRAKEN KEEPER IDENTITY
# ═══════════════════════════════════════════════════════════════

KRAKEN_IDENTITY = {
    "port": "P6",
    "powerword": "ASSIMILATE",
    "commander": "Kraken Keeper",
    "title": "Devourer of Depths and Dreams",
    "spell": "CLONE",
    "spell_school": "Necromancy",
    "trigram": "☶ Gen (Mountain)",
    "galois_pair": "P1 BRIDGE (Web Weaver)",
    "prey8_gate": "PERCEIVE (paired with P0 OBSERVE)",
    "core_thesis": "Depths ARE dreams. Everything that dies feeds the knowledge graph.",
}

# Octree port definitions for classification
OCTREE_PORTS = {
    "P0": {"label": "OBSERVE", "domain": "Sensing, monitoring, observation, perception, awareness, reconnaissance, telemetry, metrics"},
    "P1": {"label": "BRIDGE", "domain": "Data fabric, integration, APIs, schemas, contracts, binding, shared protocols, interoperability"},
    "P2": {"label": "SHAPE", "domain": "Creation, code generation, modeling, design, architecture, construction, building, specification"},
    "P3": {"label": "INJECT", "domain": "Delivery, deployment, injection, distribution, publishing, dispatch, payload, transport"},
    "P4": {"label": "DISRUPT", "domain": "Red team, adversarial, testing, mutation, breaking, challenging, probing, attacking, auditing"},
    "P5": {"label": "IMMUNIZE", "domain": "Defense, security, governance, validation, gates, integrity, resilience, hardening, compliance"},
    "P6": {"label": "ASSIMILATE", "domain": "Knowledge, learning, memory, extraction, archiving, cataloging, indexing, post-action review"},
    "P7": {"label": "NAVIGATE", "domain": "Orchestration, steering, C2, strategy, routing, planning, prioritization, meta-coordination"},
}

# Document type taxonomy
DOC_TYPES = [
    "explanation", "reference", "how_to", "tutorial",
    "recipe_card", "template", "portable_artifact",
    "doctrine", "forge_report", "concordance", "catalog",
    "incident_report", "config", "project_spec",
]


# ═══════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_readonly() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn



def write_stigmergy_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
    source: str = P6_SOURCE,
) -> str:
    # ── Signal metadata auto-injection (8^N coordinator retrofit) ──
    if "signal_metadata" not in data:
        try:
            from hfo_signal_shim import build_signal_metadata
            data["signal_metadata"] = build_signal_metadata(
                port="P6",
                model_id=data.get("model", P6_MODEL),
                daemon_name="P6 Kraken",
                daemon_version="1.0",
                task_type=event_type.split(".")[-1],
            )
        except Exception:
            pass  # Fail open — don't break daemon if shim missing
    event_id = hashlib.md5(
        f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()
    ).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    event = {
        "specversion": "1.0",
        "id": event_id,
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "phase": "CLOUDEVENT",
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(event), content_hash),
    )
    conn.commit()
    return event_id


# ═══════════════════════════════════════════════════════════════
# OLLAMA CLIENT
# ═══════════════════════════════════════════════════════════════

def ollama_generate(
    prompt: str,
    system: str = "",
    model: str = P6_MODEL,
    timeout: float = 180,
    temperature: float = 0.3,
    num_predict: int = 1024,
    keep_alive: str = "0s",  # evict model from VRAM after call — frees GPU headroom
    _caller: str = "kraken",
) -> str:
    """
    Call Ollama generate API. Returns response text or empty on error.

    Resource governor gate (80% VRAM ceiling):
      Before each call, waits for GPU headroom. If VRAM budget is saturated
      for more than GPU_SLOT_TIMEOUT_S seconds, returns "" so the caller
      falls back to NPU. This prevents the system from ever pushing GPU to 100%.
    """
    # ── Resource governor gate ──────────────────────────────────────────
    if _RESOURCE_GOVERNOR_AVAILABLE:
        ok = _wait_gpu_headroom(caller=f"ollama_generate/{_caller}", verbose=False)
        if not ok:
            # Don't crash — return empty so caller falls back to NPU or skips
            print(
                f"[RESOURCE GOV] ollama_generate/{_caller}: VRAM budget saturated — "
                "skipping GPU call (NPU/skip fallback)",
                file=sys.stderr,
            )
            return ""
    # ───────────────────────────────────────────────────────────────────
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "num_predict": num_predict,
            "temperature": temperature,
        },
    }
    if system:
        payload["system"] = system

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return data.get("response", "").strip()
    except Exception as e:
        print(f"  [OLLAMA ERROR] {e}", file=sys.stderr)
        return ""


def ollama_available() -> bool:
    """Check if Ollama is reachable."""
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════
# NPU-GPU HYBRID INTELLIGENCE — VRAM Governor + NPU Triage
# ═══════════════════════════════════════════════════════════════

# Tiny-first model hierarchy (ascending VRAM cost)
MODEL_HIERARCHY = [
    ("lfm2.5-thinking:1.2b", 0.7),    # 47 tok/s — zero-impact enrichment
    ("llama3.2:3b",          1.9),    # fallback tier 1
    ("qwen2.5:3b",           1.9),    # fallback tier 2
    ("gemma3:4b",            3.1),    # fallback heavy
]
VRAM_SATURATED_GB = 13.0   # Above this: tiny models only
VRAM_MODERATE_GB  = 10.0   # Above this: prefer small models


def get_vram_state() -> dict:
    """Query Ollama /api/ps for current VRAM load."""
    try:
        with httpx.Client(timeout=5) as c:
            r = c.get(f"{OLLAMA_BASE}/api/ps")
            if r.status_code == 200:
                models = r.json().get("models", [])
                total_gb = sum(m.get("size_vram", 0) for m in models) / 1_073_741_824
                return {
                    "total_gb": round(total_gb, 2),
                    "loaded": [m.get("name", "") for m in models],
                }
    except Exception:
        pass
    return {"total_gb": 0.0, "loaded": []}


def vram_governor() -> str:
    """
    Return the smallest safe model given current VRAM load.

    Strategy — tiny-first:
      >13 GB (saturated) : lfm2.5-thinking:1.2b  (0.7 GB)
      >10 GB (moderate)  : llama3.2:3b or qwen2.5:3b  (1.9 GB)
      <10 GB (relaxed)   : gemma3:4b  (3.1 GB)

    Always prefers a model already hot in VRAM (zero swap cost).
    Falls back to P6_MODEL if nothing in hierarchy is installed.
    """
    state = get_vram_state()
    vram = state["total_gb"]
    loaded = state["loaded"]

    # Prefer hot models (already in VRAM = zero eviction overhead)
    for name, _ in MODEL_HIERARCHY:
        if any(name in ln for ln in loaded):
            return name

    # Capacity-based selection
    if vram >= VRAM_SATURATED_GB:
        return "lfm2.5-thinking:1.2b"
    elif vram >= VRAM_MODERATE_GB:
        return "qwen2.5:3b"
    else:
        return "gemma3:4b"


def npu_bluf_thief(doc_id: int, threshold: float = 0.88) -> Optional[str]:
    """
    Steal a BLUF from a semantically near-identical document (zero GPU cost).

    Uses stored NPU embeddings (cosine similarity via all-MiniLM-L6-v2).
    Returns an existing BLUF string, or None if no similar doc found.

    Threshold guide:
      0.95+ near-duplicate  (safe to copy verbatim)
      0.88+ same topic      (adapt/reuse BLUF)     ← default
      0.70+ related topic   (reference only)
    """
    try:
        _npu_res = str(HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources")
        if _npu_res not in sys.path:
            sys.path.insert(0, _npu_res)
        from hfo_npu_embedder import get_embedding, find_similar

        conn_ro = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
        conn_ro.row_factory = sqlite3.Row

        query_vec = get_embedding(conn_ro, doc_id)
        if query_vec is None:
            conn_ro.close()
            return None

        similar = find_similar(conn_ro, query_vec, top_k=5, min_score=threshold)
        for r in similar:
            if r["doc_id"] == doc_id:
                continue
            row = conn_ro.execute(
                "SELECT bluf FROM documents WHERE id = ? "
                "AND bluf IS NOT NULL AND bluf != '' AND bluf != '---' AND LENGTH(bluf) > 20",
                (r["doc_id"],),
            ).fetchone()
            if row:
                conn_ro.close()
                return row[0]

        conn_ro.close()
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
# P6 KRAKEN KEEPER — Core Enrichment Engine
# ═══════════════════════════════════════════════════════════════

KRAKEN_SYSTEM_PROMPT = f"""You are the Kraken Keeper, commander of Port 6 (ASSIMILATE) in the HFO Octree.
Your title: Devourer of Depths and Dreams. Your spell: CLONE (Necromancy).
You devour knowledge from documents and extract their essence.

RULES:
- Be concise and precise. No filler. No markdown formatting.
- Answer ONLY what is asked. No preamble, no explanation of your process.
- When generating a BLUF (Bottom Line Up Front), write 1-3 sentences capturing the document's core value proposition.
- When classifying a port, respond ONLY with the port ID (P0, P1, P2, P3, P4, P5, P6, P7).
- When classifying a doc type, respond ONLY with the type name.
- Strip any <think> tags or reasoning traces from your output.
"""


# ═══════════════════════════════════════════════════════════════
# NPU LLM BACKEND — openvino_genai persistent pipeline (no GPU)
# ═══════════════════════════════════════════════════════════════

# Path to pre-downloaded INT4 NPU model (override via env var)
NPU_LLM_MODEL_DIR = os.environ.get(
    "P6_NPU_LLM_MODEL",
    str(HFO_ROOT / ".hfo_models" / "npu_llm" / "qwen3-1.7b-int4-ov-npu")
)
_npu_pipeline = None          # lazy-loaded singleton
_npu_pipeline_lock = __import__('threading').Lock()


def _get_npu_pipeline():
    """Return cached openvino_genai LLMPipeline, loading on first call."""
    global _npu_pipeline
    if _npu_pipeline is not None:
        return _npu_pipeline
    with _npu_pipeline_lock:
        if _npu_pipeline is not None:   # double-checked locking
            return _npu_pipeline
        model_path = NPU_LLM_MODEL_DIR
        if not os.path.isfile(os.path.join(model_path, "openvino_model.xml")):
            return None   # model not downloaded yet
        try:
            import openvino_genai as ov_genai   # optional dependency
            print(f"[NPU LLM] Loading {model_path} on NPU (one-time cold start)...")
            t0 = __import__('time').time()
            _npu_pipeline = ov_genai.LLMPipeline(model_path, "NPU")
            elapsed = __import__('time').time() - t0
            print(f"[NPU LLM] Ready — loaded in {elapsed:.1f}s")
        except Exception as e:
            print(f"[NPU LLM] Load failed: {e}")
            _npu_pipeline = None
    return _npu_pipeline


def npu_llm_generate(prompt: str, max_new_tokens: int = 180) -> Optional[str]:
    """
    Generate text on the NPU via openvino_genai (zero GPU / zero Ollama).

    Uses the persistent singleton pipeline — no reload overhead after first call.
    Appends /no_think to suppress Qwen3 reasoning chains.
    Sets repetition_penalty=1.3 to prevent token-loop failures seen on Meteor Lake NPU.
    Returns None on any failure (or garbage output) so caller falls back to Ollama.
    """
    pipe = _get_npu_pipeline()
    if pipe is None:
        return None
    try:
        import openvino_genai as ov_genai
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens = max_new_tokens
        cfg.repetition_penalty = 1.3  # prevents 'põe\npõe\n...' loops on NPU
        # /no_think suppresses Qwen3 <think> reasoning block
        result = pipe.generate(prompt + " /no_think", cfg)
        clean = _strip_think_tags(str(result)).strip()
        if not _npu_output_valid(clean):
            print(f"[NPU LLM] output failed quality gate — falling back")
            return None
        # ── Stamp NPU state file so P0 TRUE_SEEING knows NPU is active ───────
        try:
            _NPU_STATE_PATH.write_text(
                json.dumps({
                    "active": True,
                    "last_inference_ts": datetime.now(timezone.utc).isoformat(),
                    "model": os.environ.get("P6_NPU_LLM_MODEL", "unknown"),
                    "tokens_generated": max_new_tokens,
                }),
                encoding="utf-8",
            )
        except Exception:
            pass
        return clean
    except Exception as e:
        print(f"[NPU LLM] generate error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════


def _strip_think_tags(text: str) -> str:
    """Strip <think>...</think> blocks from deepseek-r1 / Qwen3 output.
    Handles both complete blocks and unclosed blocks (NPU hit max_new_tokens
    mid-reasoning before writing the closing tag).
    """
    import re
    # Remove complete <think>...</think> blocks first
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Remove any remaining incomplete <think> block (runs to end of string)
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()
    return cleaned if cleaned else text.strip()


def _npu_output_valid(text: str) -> bool:
    """Quality gate: return False for looping, think-leaking, or near-empty NPU output.

    Catches failure modes observed on Meteor Lake NPU:
      1. Incomplete <think> block (token budget exhausted mid-reasoning)
      2. Newline-separated token loops  (e.g. 'põe\npõe\npõe...' / 'apsed\n...')
      3. Excessive line-level duplication (>60% duplicate lines)
      4. Inline-repetition loops: same phrase repeated 5+ times without newlines
         (catches Chinese CJK loops like '系统正在处理您的请求。请稍候。' repeated)
    """
    import re
    if len(text) < 20:
        return False
    # Residual think tag after stripping (should be gone, but paranoia is free)
    if re.search(r'<think>', text, re.IGNORECASE):
        return False
    # Newline-separated loop: same short token repeated 5+ times
    if re.search(r'(.{1,25})\n\1\n\1\n\1\n\1', text):
        return False
    # High duplicate-line ratio
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines and len(set(lines)) / len(lines) < 0.4:  # >60% dupes
        return False
    # Inline-repetition loop: a substring of 10-40 chars repeated so many times
    # it dominates the output (>40% of total text). Catches CJK phrase loops
    # and space-separated repeating phrases without triggering on common terms.
    for m in re.finditer(r'(.{10,40})', text):
        phrase = m.group(1)
        count = text.count(phrase)
        if count >= 5 and (count * len(phrase)) > 0.4 * len(text):
            return False
    return True


class KrakenKeeper:
    """The P6 ASSIMILATE daemon — incremental SSOT enrichment via Ollama."""

    def __init__(self, dry_run: bool = False, model: str = P6_MODEL,
                 batch_size: int = 3):
        self.dry_run = dry_run
        self.model = model
        self.batch_size = batch_size
        self._running = True

        # Enrichment counters
        self.stats = {
            "cycles": 0,
            "blufs_generated": 0,
            "blufs_stolen_npu": 0,
            "ports_classified": 0,
            "doctypes_classified": 0,
            "lineage_edges_added": 0,
            "npu_lineage_edges": 0,
            "errors": 0,
            "ollama_calls": 0,
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

    def stop(self):
        self._running = False

    # ── T1: BLUF GENERATION ──────────────────────────────────

    async def enrich_blufs(self) -> dict:
        """Find docs without BLUFs, generate them via Ollama."""
        results = {"enriched": 0, "skipped": 0, "errors": 0, "docs": []}

        try:
            conn = get_db_readwrite()
            # Find docs missing BLUFs
            cursor = conn.execute(
                """SELECT id, title, SUBSTR(content, 1, 2000) as content_preview,
                          source, word_count
                   FROM documents
                   WHERE (bluf IS NULL OR bluf = '---')
                   ORDER BY word_count DESC
                   LIMIT ?""",
                (self.batch_size,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            for row in rows:
                if not self._running:
                    break

                doc_id = row["id"]
                title = row["title"] or "(untitled)"
                content = row["content_preview"] or ""
                source = row["source"] or "unknown"

                if not content or len(content) < 50:
                    results["skipped"] += 1
                    continue

                # Generate BLUF via Ollama
                prompt = (
                    f"Write a BLUF (Bottom Line Up Front) summary for this document.\n"
                    f"Title: {title}\nSource: {source}\n\n"
                    f"Content (first 2000 chars):\n{content}\n\n"
                    f"BLUF (1-3 sentences, no quotes, no markdown):"
                )

                # ── NPU TRIAGE: steal BLUF from similar doc (zero GPU cost) ──
                stolen = await asyncio.get_event_loop().run_in_executor(
                    None, lambda d=doc_id: npu_bluf_thief(d, threshold=0.88)
                )
                if stolen:
                    bluf = stolen
                    self.stats["blufs_stolen_npu"] += 1
                    print(f"  [NPU THIEF] doc {doc_id}: BLUF stolen from similar doc (0 GPU)")
                else:
                    # ── NPU LLM: generate with openvino_genai (no GPU) ────────
                    npu_result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda p=prompt: npu_llm_generate(p)
                    )
                    if npu_result:
                        bluf = npu_result
                        self.stats["npu_llm_calls"] = self.stats.get("npu_llm_calls", 0) + 1
                        print(f"  [NPU LLM] doc {doc_id}: BLUF generated on NPU (0 GPU)")
                    else:
                        # ── VRAM GOVERNOR: Ollama fallback (GPU last resort) ──
                        active_model = vram_governor()
                        raw_response = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda p=prompt, m=active_model: ollama_generate(
                                p, system=KRAKEN_SYSTEM_PROMPT, model=m, keep_alive="0s"
                            ),
                        )
                        self.stats["ollama_calls"] += 1
                        bluf = _strip_think_tags(raw_response)
                        if not bluf or len(bluf) < 10:
                            results["errors"] += 1
                            continue

                # Truncate excessively long BLUFs
                if len(bluf) > 500:
                    bluf = bluf[:497] + "..."

                if not self.dry_run:
                    try:
                        wconn = get_db_readwrite()
                        wconn.execute(
                            "UPDATE documents SET bluf = ? WHERE id = ? AND (bluf IS NULL OR bluf = '---')",
                            (bluf, doc_id),
                        )
                        write_stigmergy_event(
                            wconn, "hfo.gen90.kraken.bluf_enriched",
                            f"BLUF:doc_{doc_id}",
                            {
                                "doc_id": doc_id,
                                "title": title[:100],
                                "source": source,
                                "bluf_length": len(bluf),
                                "bluf_preview": bluf[:200],
                                "model": self.model,
                                "task": "T1_BLUF_GENERATION",
                            },
                        )
                        wconn.close()
                    except Exception as e:
                        print(f"  [T1 DB ERROR] {e}", file=sys.stderr)
                        results["errors"] += 1
                        continue

                results["enriched"] += 1
                results["docs"].append({"id": doc_id, "title": title[:60]})
                self.stats["blufs_generated"] += 1
                print(f"  [BLUF] doc {doc_id}: {title[:50]}... ({len(bluf)} chars)")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T1 ERROR] {e}", file=sys.stderr)

        return results

    # ── T2: PORT CLASSIFICATION ──────────────────────────────

    async def classify_ports(self) -> dict:
        """Find docs without port assignment, classify via Ollama."""
        results = {"classified": 0, "skipped": 0, "errors": 0, "docs": []}

        try:
            conn = get_db_readwrite()
            cursor = conn.execute(
                """SELECT id, title, bluf, SUBSTR(content, 1, 1500) as content_preview,
                          source, tags
                   FROM documents
                   WHERE port IS NULL
                   ORDER BY RANDOM()
                   LIMIT ?""",
                (self.batch_size,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            port_descriptions = "\n".join(
                f"  {pid}: {info['label']} — {info['domain']}"
                for pid, info in OCTREE_PORTS.items()
            )

            for row in rows:
                if not self._running:
                    break

                doc_id = row["id"]
                title = row["title"] or "(untitled)"
                bluf = row["bluf"] or ""
                content = row["content_preview"] or ""
                source = row["source"] or "unknown"
                tags = row["tags"] or ""

                context = f"Title: {title}\nBLUF: {bluf}\nSource: {source}\nTags: {tags}"
                if bluf and len(bluf) > 20:
                    # Use BLUF if available, cheaper than full content
                    text_for_classification = context
                else:
                    text_for_classification = f"{context}\nContent preview: {content[:800]}"

                prompt = (
                    f"Classify this document into exactly ONE octree port.\n\n"
                    f"Port definitions:\n{port_descriptions}\n\n"
                    f"Document:\n{text_for_classification}\n\n"
                    f"Reply with ONLY the port ID (e.g., P4). Nothing else:"
                )

                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(
                        p, system=KRAKEN_SYSTEM_PROMPT, model=self.model,
                        num_predict=64,
                    ),
                )
                self.stats["ollama_calls"] += 1

                response = _strip_think_tags(raw_response).upper().strip()

                # Extract port ID — look for P0-P7 pattern
                import re
                port_match = re.search(r"P[0-7]", response)
                if not port_match:
                    results["errors"] += 1
                    continue

                port = port_match.group(0)

                if not self.dry_run:
                    try:
                        wconn = get_db_readwrite()
                        wconn.execute(
                            "UPDATE documents SET port = ? WHERE id = ? AND port IS NULL",
                            (port, doc_id),
                        )
                        write_stigmergy_event(
                            wconn, "hfo.gen90.kraken.port_classified",
                            f"PORT:{port}:doc_{doc_id}",
                            {
                                "doc_id": doc_id,
                                "title": title[:100],
                                "assigned_port": port,
                                "port_label": OCTREE_PORTS[port]["label"],
                                "source": source,
                                "model": self.model,
                                "task": "T2_PORT_CLASSIFICATION",
                            },
                        )
                        wconn.close()
                    except Exception as e:
                        print(f"  [T2 DB ERROR] {e}", file=sys.stderr)
                        results["errors"] += 1
                        continue

                results["classified"] += 1
                results["docs"].append({"id": doc_id, "port": port, "title": title[:60]})
                self.stats["ports_classified"] += 1
                print(f"  [PORT] doc {doc_id} → {port} {OCTREE_PORTS[port]['label']}: {title[:50]}...")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T2 ERROR] {e}", file=sys.stderr)

        return results

    # ── T3: DOC TYPE CLASSIFICATION ──────────────────────────

    async def classify_doctypes(self) -> dict:
        """Find docs without doc_type, classify via Ollama."""
        results = {"classified": 0, "skipped": 0, "errors": 0, "docs": []}

        try:
            conn = get_db_readwrite()
            cursor = conn.execute(
                """SELECT id, title, bluf, SUBSTR(content, 1, 1000) as content_preview,
                          source, tags
                   FROM documents
                   WHERE doc_type IS NULL
                   ORDER BY id
                   LIMIT ?""",
                (self.batch_size,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            types_list = ", ".join(DOC_TYPES)

            for row in rows:
                if not self._running:
                    break

                doc_id = row["id"]
                title = row["title"] or "(untitled)"
                bluf = row["bluf"] or ""
                content = row["content_preview"] or ""
                source = row["source"] or "unknown"

                prompt = (
                    f"Classify this document into exactly ONE type.\n\n"
                    f"Valid types: {types_list}\n\n"
                    f"Document:\n  Title: {title}\n  BLUF: {bluf}\n"
                    f"  Source: {source}\n  Content: {content[:500]}\n\n"
                    f"Reply with ONLY the type name (e.g., explanation). Nothing else:"
                )

                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(
                        p, system=KRAKEN_SYSTEM_PROMPT, model=self.model,
                        num_predict=64,
                    ),
                )
                self.stats["ollama_calls"] += 1

                response = _strip_think_tags(raw_response).lower().strip()

                # Match to known types
                matched_type = None
                for dt in DOC_TYPES:
                    if dt in response:
                        matched_type = dt
                        break

                if not matched_type:
                    results["errors"] += 1
                    continue

                if not self.dry_run:
                    try:
                        wconn = get_db_readwrite()
                        wconn.execute(
                            "UPDATE documents SET doc_type = ? WHERE id = ? AND doc_type IS NULL",
                            (matched_type, doc_id),
                        )
                        write_stigmergy_event(
                            wconn, "hfo.gen90.kraken.doctype_classified",
                            f"DOCTYPE:{matched_type}:doc_{doc_id}",
                            {
                                "doc_id": doc_id,
                                "title": title[:100],
                                "assigned_type": matched_type,
                                "source": source,
                                "model": self.model,
                                "task": "T3_DOCTYPE_CLASSIFICATION",
                            },
                        )
                        wconn.close()
                    except Exception as e:
                        print(f"  [T3 DB ERROR] {e}", file=sys.stderr)
                        results["errors"] += 1
                        continue

                results["classified"] += 1
                results["docs"].append({"id": doc_id, "type": matched_type})
                self.stats["doctypes_classified"] += 1
                print(f"  [TYPE] doc {doc_id} → {matched_type}: {title[:50]}...")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T3 ERROR] {e}", file=sys.stderr)

        return results

    # ── T4: LINEAGE CROSS-REFERENCE MINING ───────────────────

    async def mine_lineage(self) -> dict:
        """Discover cross-references between documents, populate lineage table."""
        results = {"edges_added": 0, "docs_scanned": 0, "errors": 0}

        try:
            conn = get_db_readwrite()
            # Pick a random doc with content
            cursor = conn.execute(
                """SELECT id, title, SUBSTR(content, 1, 3000) as content_preview,
                          content_hash, source, port
                   FROM documents
                   WHERE word_count > 100
                   ORDER BY RANDOM()
                   LIMIT ?""",
                (self.batch_size,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            for row in rows:
                if not self._running:
                    break

                doc_id = row["id"]
                title = row["title"] or "(untitled)"
                content = row["content_preview"] or ""
                doc_hash = row["content_hash"] or ""
                source = row["source"] or "unknown"

                # Ask Ollama to extract document references
                prompt = (
                    f"This document is from the HFO knowledge system (Gen90, ~9860 docs).\n"
                    f"Extract any EXPLICIT references to other documents, concepts, or topics.\n\n"
                    f"Title: {title}\nSource: {source}\n"
                    f"Content:\n{content}\n\n"
                    f"List up to 5 referenced topics/concepts, one per line.\n"
                    f"Format: TOPIC: <topic name>\n"
                    f"If no references found, reply: NONE"
                )

                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(
                        p, system=KRAKEN_SYSTEM_PROMPT, model=self.model,
                        num_predict=512,
                    ),
                )
                self.stats["ollama_calls"] += 1

                response = _strip_think_tags(raw_response)
                results["docs_scanned"] += 1

                if "NONE" in response.upper() and len(response) < 20:
                    continue

                # Parse topics and attempt FTS match
                topics = []
                for line in response.split("\n"):
                    line = line.strip()
                    if line.upper().startswith("TOPIC:"):
                        topic = line[6:].strip().strip("-").strip()
                        if topic and len(topic) > 3:
                            topics.append(topic)

                for topic in topics[:5]:
                    # FTS search for matching documents
                    try:
                        # Sanitize topic for FTS5
                        safe_topic = " ".join(
                            w for w in topic.split()
                            if w.isalnum() or w.replace("-", "").isalnum()
                        )
                        if not safe_topic:
                            continue

                        wconn = get_db_readwrite()
                        target_cursor = wconn.execute(
                            """SELECT id, content_hash FROM documents
                               WHERE id IN (
                                   SELECT rowid FROM documents_fts
                                   WHERE documents_fts MATCH ?
                               ) AND id != ?
                               LIMIT 1""",
                            (safe_topic, doc_id),
                        )
                        target = target_cursor.fetchone()

                        if target:
                            target_hash = target["content_hash"] or ""
                            # Check if edge already exists
                            existing = wconn.execute(
                                """SELECT 1 FROM lineage
                                   WHERE doc_id = ? AND depends_on_hash = ?""",
                                (doc_id, target_hash),
                            ).fetchone()

                            if not existing and target_hash and not self.dry_run:
                                wconn.execute(
                                    """INSERT INTO lineage (doc_id, depends_on_hash, relation)
                                       VALUES (?, ?, ?)""",
                                    (doc_id, target_hash, f"references:{topic[:100]}"),
                                )
                                wconn.commit()
                                results["edges_added"] += 1
                                self.stats["lineage_edges_added"] += 1
                        wconn.close()

                    except sqlite3.OperationalError:
                        # FTS query syntax issue — skip
                        pass

                if results["edges_added"] > 0 and not self.dry_run:
                    wconn = get_db_readwrite()
                    write_stigmergy_event(
                        wconn, "hfo.gen90.kraken.lineage_mined",
                        f"LINEAGE:doc_{doc_id}",
                        {
                            "doc_id": doc_id,
                            "title": title[:100],
                            "topics_found": len(topics),
                            "edges_added": results["edges_added"],
                            "model": self.model,
                            "task": "T4_LINEAGE_MINING",
                        },
                    )
                    wconn.commit()
                    wconn.close()
                    print(f"  [LINEAGE] doc {doc_id}: {results['edges_added']} new edges")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T4 ERROR] {e}", file=sys.stderr)

        return results

    # ── T7: NPU LINEAGE MINING ─────────────────────────────────

    async def npu_lineage_mine(self) -> dict:
        """
        Build SSOT lineage edges using NPU cosine similarity — zero GPU cost.

        Replaces the LLM-based T4 approach for high-volume lineage discovery:
          1. Find docs with no existing lineage edges (up to batch_size * 3)
          2. Use stored NPU embeddings to find top-5 similar docs per doc
          3. Insert lineage edge for any pair with cosine > 0.65

        This runs entirely on NPU ONNX cosine math — no Ollama calls.
        T4 LLM lineage still runs for richer semantic cross-referencing.
        """
        results = {"edges_added": 0, "docs_scanned": 0, "skipped": 0, "errors": 0}
        try:
            _npu_res = str(HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources")
            if _npu_res not in sys.path:
                sys.path.insert(0, _npu_res)
            from hfo_npu_embedder import get_embedding, find_similar
        except ImportError:
            results["errors"] = 1
            return results  # OpenVINO not available — skip silently

        try:
            conn_ro = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
            conn_ro.row_factory = sqlite3.Row

            # Docs with fewest lineage edges (prioritise orphans)
            doc_rows = conn_ro.execute(
                """
                SELECT d.id FROM documents d
                LEFT JOIN lineage l ON d.id = l.doc_id
                GROUP BY d.id
                HAVING COUNT(l.doc_id) = 0
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (self.batch_size * 3,),
            ).fetchall()
            conn_ro.close()
        except Exception as e:
            results["errors"] += 1
            print(f"  [T7 QUERY ERROR] {e}", file=sys.stderr)
            return results

        NPU_LINEAGE_THRESHOLD = 0.65

        for row in doc_rows:
            if not self._running:
                break
            doc_id = row[0]
            results["docs_scanned"] += 1

            try:
                conn_ro = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
                conn_ro.row_factory = sqlite3.Row
                query_vec = get_embedding(conn_ro, doc_id)
                if query_vec is None:
                    conn_ro.close()
                    results["skipped"] += 1
                    continue

                similar = find_similar(
                    conn_ro, query_vec, top_k=6, min_score=NPU_LINEAGE_THRESHOLD
                )
                conn_ro.close()

                for s in similar:
                    if s["doc_id"] == doc_id:
                        continue
                    target_id = s["doc_id"]
                    score = round(s["score"], 4)

                    if not self.dry_run:
                        try:
                            wconn = get_db_readwrite()
                            # Use content_hash of target for lineage table
                            target_hash = wconn.execute(
                                "SELECT content_hash FROM documents WHERE id = ?",
                                (target_id,),
                            ).fetchone()
                            if target_hash and target_hash[0]:
                                existing = wconn.execute(
                                    "SELECT 1 FROM lineage WHERE doc_id = ? AND depends_on_hash = ?",
                                    (doc_id, target_hash[0]),
                                ).fetchone()
                                if not existing:
                                    wconn.execute(
                                        "INSERT INTO lineage (doc_id, depends_on_hash, relation) VALUES (?, ?, ?)",
                                        (doc_id, target_hash[0], f"npu_similarity:{score}"),
                                    )
                                    wconn.commit()
                                    results["edges_added"] += 1
                                    self.stats["lineage_edges_added"] += 1
                            wconn.close()
                        except Exception:
                            pass

            except Exception as e:
                results["errors"] += 1
                print(f"  [T7 DOC ERROR] doc {doc_id}: {e}", file=sys.stderr)

        if results["edges_added"] > 0 and not self.dry_run:
            try:
                wconn = get_db_readwrite()
                write_stigmergy_event(
                    wconn, "hfo.gen90.kraken.npu_lineage",
                    f"NPU_LINEAGE:batch_{results['docs_scanned']}",
                    {
                        "docs_scanned": results["docs_scanned"],
                        "edges_added": results["edges_added"],
                        "threshold": NPU_LINEAGE_THRESHOLD,
                        "task": "T7_NPU_LINEAGE",
                    },
                )
                wconn.close()
            except Exception:
                pass

        print(f"  [T7:NPU-LINEAGE] scanned={results['docs_scanned']} edges={results['edges_added']} errs={results['errors']}")
        return results

    # ── T5: STIGMERGY ROLLUP ─────────────────────────────────

    async def rollup_stigmergy(self) -> dict:
        """Auto-rollup stigmergy events into daily/weekly summaries."""
        results = {"rollups_created": 0, "errors": 0}

        try:
            conn = get_db_readwrite()
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            
            # 1. Daily Rollup (for yesterday)
            yesterday = now - timedelta(days=1)
            day_str = yesterday.strftime("%Y-%m-%d")
            title_daily = f"Stigmergy Daily Rollup: {day_str}"
            
            # Check if exists
            cursor = conn.execute("SELECT id FROM documents WHERE title = ?", (title_daily,))
            daily_exists = cursor.fetchone() is not None
            
            daily_events = []
            if not daily_exists:
                start_time = yesterday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
                
                daily_events = [dict(row) for row in conn.execute(
                    """SELECT event_type, timestamp, subject, substr(data_json, 1, 500) as data_preview
                       FROM stigmergy_events
                       WHERE timestamp >= ? AND timestamp <= ?
                       ORDER BY timestamp ASC""",
                    (start_time, end_time)
                ).fetchall()]

            # 2. Weekly Rollup (for last week)
            weekly_exists = True
            weekly_events = []
            week_str = ""
            title_weekly = ""
            if now.weekday() == 0: # Monday
                last_monday = now - timedelta(days=7)
                last_sunday = now - timedelta(days=1)
                week_str = f"{last_monday.strftime('%Y-%m-%d')} to {last_sunday.strftime('%Y-%m-%d')}"
                title_weekly = f"Stigmergy Weekly Rollup: {week_str}"
                
                cursor = conn.execute("SELECT id FROM documents WHERE title = ?", (title_weekly,))
                weekly_exists = cursor.fetchone() is not None
                if not weekly_exists:
                    start_time = last_monday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                    end_time = last_sunday.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
                    
                    weekly_events = [dict(row) for row in conn.execute(
                        """SELECT event_type, timestamp, subject, substr(data_json, 1, 500) as data_preview
                           FROM stigmergy_events
                           WHERE timestamp >= ? AND timestamp <= ?
                           ORDER BY timestamp ASC""",
                        (start_time, end_time)
                    ).fetchall()]
            conn.close()
        except Exception as e:
            results["errors"] = 1
            return results

        try:
            if not daily_exists and daily_events:
                events_text = "\n".join([f"[{e['timestamp'][:19]}] {e['event_type']} - {e['subject']}" for e in daily_events])
                prompt = (
                    f"Summarize the following stigmergy events for {day_str} into a concise daily rollup report. "
                    f"Group by major themes or ports if possible.\n\nEvents:\n{events_text[:8000]}"
                )
                
                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(p, system="You are the Kraken Keeper. Summarize the swarm's daily activity.", model=self.model),
                )
                self.stats["ollama_calls"] += 1
                summary = _strip_think_tags(raw_response)
                
                if summary and not self.dry_run:
                    content = f"# {title_daily}\n\n{summary}\n\n## Raw Event Count: {len(daily_events)}"
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    bluf = f"Daily stigmergy rollup for {day_str} covering {len(daily_events)} events."
                    
                    wconn = get_db_readwrite()
                    wconn.execute(
                        """INSERT INTO documents (title, bluf, source, port, doc_type, content, content_hash, word_count, ingested_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (title_daily, bluf, "kraken_rollup", "P6", "rollup", content, content_hash, len(content.split()), now.isoformat())
                    )
                    wconn.commit()
                    wconn.close()
                    results["rollups_created"] += 1
                    print(f"  [ROLLUP] Created daily rollup for {day_str}")

            if not weekly_exists and weekly_events:
                events_text = "\n".join([f"[{e['timestamp'][:19]}] {e['event_type']} - {e['subject']}" for e in weekly_events])
                prompt = (
                    f"Summarize the following stigmergy events for the week of {week_str} into a concise weekly rollup report. "
                    f"Group by major themes or ports if possible.\n\nEvents:\n{events_text[:8000]}"
                )
                
                raw_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p=prompt: ollama_generate(p, system="You are the Kraken Keeper. Summarize the swarm's weekly activity.", model=self.model),
                )
                self.stats["ollama_calls"] += 1
                summary = _strip_think_tags(raw_response)
                
                if summary and not self.dry_run:
                    content = f"# {title_weekly}\n\n{summary}\n\n## Raw Event Count: {len(weekly_events)}"
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    bluf = f"Weekly stigmergy rollup for {week_str} covering {len(weekly_events)} events."
                    
                    wconn = get_db_readwrite()
                    wconn.execute(
                        """INSERT INTO documents (title, bluf, source, port, doc_type, content, content_hash, word_count, ingested_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (title_weekly, bluf, "kraken_rollup", "P6", "rollup", content, content_hash, len(content.split()), now.isoformat())
                    )
                    wconn.commit()
                    wconn.close()
                    results["rollups_created"] += 1
                    print(f"  [ROLLUP] Created weekly rollup for {week_str}")

        except Exception as e:
            results["errors"] += 1
            self.stats["errors"] += 1
            print(f"  [T5 ERROR] {e}", file=sys.stderr)

        return results

    # ── T6: HEARTBEAT + STATS ────────────────────────────────

    def get_enrichment_progress(self) -> dict:
        """Query current SSOT enrichment state."""
        try:
            conn = get_db_readonly()
            total = conn.execute("SELECT COUNT(1) FROM documents").fetchone()[0]
            no_bluf_null = conn.execute("SELECT COUNT(1) FROM documents WHERE bluf IS NULL").fetchone()[0]
            no_bluf_dash = conn.execute("SELECT COUNT(1) FROM documents WHERE bluf = '---'").fetchone()[0]
            no_port = conn.execute("SELECT COUNT(1) FROM documents WHERE port IS NULL").fetchone()[0]
            no_doctype = conn.execute("SELECT COUNT(1) FROM documents WHERE doc_type IS NULL").fetchone()[0]
            lineage_count = conn.execute("SELECT COUNT(1) FROM lineage").fetchone()[0]
            events = conn.execute("SELECT COUNT(1) FROM stigmergy_events").fetchone()[0]
            kraken_events = conn.execute(
                "SELECT COUNT(1) FROM stigmergy_events WHERE event_type LIKE '%kraken%'"
            ).fetchone()[0]
            conn.close()
            return {
                "total_docs": total,
                "missing_bluf": no_bluf_null + no_bluf_dash,
                "missing_port": no_port,
                "missing_doctype": no_doctype,
                "lineage_edges": lineage_count,
                "total_events": events,
                "kraken_events": kraken_events,
                "enrichment_pct": {
                    "bluf": round(100 * (1 - (no_bluf_null + no_bluf_dash) / max(total, 1)), 1),
                    "port": round(100 * (1 - no_port / max(total, 1)), 1),
                    "doctype": round(100 * (1 - no_doctype / max(total, 1)), 1),
                },
            }
        except Exception as e:
            return {"error": str(e)}

    async def emit_heartbeat(self) -> dict:
        """Emit daemon heartbeat + enrichment progress."""
        progress = self.get_enrichment_progress()

        heartbeat = {
            "cycle": self.stats["cycles"],
            "identity": KRAKEN_IDENTITY,
            "model": self.model,
            "progress": progress,
            "daemon_stats": dict(self.stats),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if not self.dry_run:
            try:
                conn = get_db_readwrite()
                write_stigmergy_event(
                    conn, "hfo.gen90.kraken.heartbeat",
                    f"HEARTBEAT:cycle_{self.stats['cycles']}",
                    heartbeat,
                )
                conn.close()
            except Exception as e:
                print(f"  [HEARTBEAT ERROR] {e}", file=sys.stderr)

        return heartbeat


# ═══════════════════════════════════════════════════════════════
# ASYNC DAEMON LOOP
# ═══════════════════════════════════════════════════════════════

async def task_loop(
    name: str,
    coroutine_fn,
    interval: float,
    kraken: KrakenKeeper,
):
    """Run an enrichment task on a repeating interval."""
    while kraken._running:
        try:
            result = await coroutine_fn()
            if isinstance(result, dict) and result.get("errors", 0) > 0:
                print(f"  [{name}] completed with {result['errors']} errors", file=sys.stderr)
        except Exception as e:
            print(f"  [{name} CRASH] {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            kraken.stats["errors"] += 1

        # Sleep in small increments for responsive shutdown
        for _ in range(int(interval)):
            if not kraken._running:
                break
            await asyncio.sleep(1)


async def daemon_loop(
    kraken: KrakenKeeper,
    intervals: dict,
    enabled_tasks: set,
    single: bool = False,
):
    """Main daemon loop — runs all enabled tasks concurrently."""
    banner = f"""
  ╔═══════════════════════════════════════════════════════════╗
  ║  P6 KRAKEN KEEPER — Devourer of Depths and Dreams        ║
  ║  Port: P6 ASSIMILATE | Spell: CLONE (Necromancy)         ║
  ║  Model: {kraken.model:48s} ║
  ║  Mode: {'DRY RUN' if kraken.dry_run else '24/7 ENRICHMENT':48s} ║
  ╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)

    # Verify Ollama
    if not ollama_available():
        print("  [FATAL] Ollama not reachable at {OLLAMA_BASE}. Exiting.", file=sys.stderr)
        return

    print(f"  Ollama: ONLINE at {OLLAMA_BASE}")
    print(f"  Model:  {kraken.model}")
    print(f"  DB:     {SSOT_DB} ({SSOT_DB.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  Tasks:  {', '.join(sorted(enabled_tasks))}")
    print(f"  Batch:  {kraken.batch_size} docs per task cycle")
    print()

    # Initial progress report
    progress = kraken.get_enrichment_progress()
    if "error" not in progress:
        print(f"  Enrichment baseline:")
        print(f"    BLUFs:    {progress['enrichment_pct']['bluf']:.1f}% complete ({progress['missing_bluf']} remaining)")
        print(f"    Ports:    {progress['enrichment_pct']['port']:.1f}% complete ({progress['missing_port']} remaining)")
        print(f"    DocTypes: {progress['enrichment_pct']['doctype']:.1f}% complete ({progress['missing_doctype']} remaining)")
        print(f"    Lineage:  {progress['lineage_edges']} edges")
        print()

    # Log daemon start
    if not kraken.dry_run:
        try:
            conn = get_db_readwrite()
            write_stigmergy_event(
                conn, "hfo.gen90.kraken.start",
                "KRAKEN_START",
                {
                    "action": "daemon_start",
                    "model": kraken.model,
                    "batch_size": kraken.batch_size,
                    "enabled_tasks": sorted(enabled_tasks),
                    "intervals": intervals,
                    "dry_run": kraken.dry_run,
                    "initial_progress": progress,
                    "identity": KRAKEN_IDENTITY,
                },
            )
            conn.close()
        except Exception as e:
            print(f"  [WARN] Could not log start: {e}", file=sys.stderr)

    if single:
        # Run one cycle of each task
        kraken.stats["cycles"] = 1
        print("  === SINGLE CYCLE MODE ===\n")

        if "bluf" in enabled_tasks:
            print("  --- T1: BLUF Generation ---")
            r = await kraken.enrich_blufs()
            print(f"    Enriched: {r['enriched']}, Errors: {r['errors']}\n")

        if "port" in enabled_tasks:
            print("  --- T2: Port Classification ---")
            r = await kraken.classify_ports()
            print(f"    Classified: {r['classified']}, Errors: {r['errors']}\n")

        if "doctype" in enabled_tasks:
            print("  --- T3: Doc Type Classification ---")
            r = await kraken.classify_doctypes()
            print(f"    Classified: {r['classified']}, Errors: {r['errors']}\n")

        if "lineage" in enabled_tasks:
            print("  --- T4: Lineage Mining ---")
            r = await kraken.mine_lineage()
            print(f"    Edges added: {r['edges_added']}, Scanned: {r['docs_scanned']}\n")

        if "rollup" in enabled_tasks:
            print("  --- T6: Stigmergy Rollup ---")
            r = await kraken.rollup_stigmergy()
            print(f"    Rollups created: {r['rollups_created']}, Errors: {r['errors']}\n")

        if "npu_lineage" in enabled_tasks:
            print("  --- T7: NPU Lineage Mining ---")
            r = await kraken.npu_lineage_mine()
            print(f"    Edges added: {r['edges_added']}, Scanned: {r['docs_scanned']}\n")

        hb = await kraken.emit_heartbeat()
        progress = hb.get("progress", {})
        print("  --- Final Progress ---")
        if "enrichment_pct" in progress:
            print(f"    BLUFs:    {progress['enrichment_pct']['bluf']:.1f}%")
            print(f"    Ports:    {progress['enrichment_pct']['port']:.1f}%")
            print(f"    DocTypes: {progress['enrichment_pct']['doctype']:.1f}%")
            print(f"    Lineage:  {progress.get('lineage_edges', 0)} edges")
        print(f"    Ollama calls: {kraken.stats['ollama_calls']}")
        print(f"\n  Depths ARE dreams. The Kraken feeds.\n")
        return

    # Build concurrent task list
    tasks = []
    if "bluf" in enabled_tasks:
        tasks.append(task_loop("T1:BLUF", kraken.enrich_blufs, intervals.get("bluf", 120), kraken))
    if "port" in enabled_tasks:
        tasks.append(task_loop("T2:PORT", kraken.classify_ports, intervals.get("port", 180), kraken))
    if "doctype" in enabled_tasks:
        tasks.append(task_loop("T3:TYPE", kraken.classify_doctypes, intervals.get("doctype", 300), kraken))
    if "lineage" in enabled_tasks:
        tasks.append(task_loop("T4:LINEAGE", kraken.mine_lineage, intervals.get("lineage", 600), kraken))
    if "rollup" in enabled_tasks:
        tasks.append(task_loop("T6:ROLLUP", kraken.rollup_stigmergy, intervals.get("rollup", 3600), kraken))
    if "npu_lineage" in enabled_tasks:
        tasks.append(task_loop("T7:NPU-LINEAGE", kraken.npu_lineage_mine, intervals.get("npu_lineage", 900), kraken))
    # Heartbeat always runs
    tasks.append(task_loop("T5:HEARTBEAT", kraken.emit_heartbeat, intervals.get("heartbeat", 60), kraken))

    print(f"  Starting {len(tasks)} concurrent tasks... (Ctrl+C to stop)\n")

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        # Log daemon stop
        if not kraken.dry_run:
            try:
                conn = get_db_readwrite()
                write_stigmergy_event(
                    conn, "hfo.gen90.kraken.stop",
                    "KRAKEN_STOP",
                    {
                        "action": "daemon_stop",
                        "final_stats": dict(kraken.stats),
                        "final_progress": kraken.get_enrichment_progress(),
                    },
                )
                conn.close()
            except Exception:
                pass

        # Save state
        _save_state(kraken)
        print("\n  Kraken Keeper stopped. The depths remember.\n")


def _save_state(kraken: KrakenKeeper):
    """Persist daemon state to disk."""
    state = {
        "stats": dict(kraken.stats),
        "model": kraken.model,
        "progress": kraken.get_enrichment_progress(),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P6 KRAKEN KEEPER — Devourer of Depths and Dreams (Gen90)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hfo_p6_kraken_daemon.py                     # 24/7 mode
  python hfo_p6_kraken_daemon.py --once              # Single cycle
  python hfo_p6_kraken_daemon.py --dry-run --once    # Dry run
  python hfo_p6_kraken_daemon.py --tasks bluf,port   # Specific tasks
  python hfo_p6_kraken_daemon.py --model qwen3:8b    # Different model
  python hfo_p6_kraken_daemon.py --status             # Show progress
""",
    )
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="No writes, just show targets")
    parser.add_argument("--tasks", type=str, default="bluf,port,doctype,lineage,rollup,npu_lineage",
                        help="Comma-separated tasks: bluf,port,doctype,lineage,rollup,npu_lineage")
    parser.add_argument("--model", type=str, default=P6_MODEL, help=f"Ollama model (default: {P6_MODEL})")
    parser.add_argument("--batch-size", type=int, default=3, help="Docs per task cycle (default: 3)")
    parser.add_argument("--bluf-interval", type=float, default=120, help="BLUF cycle interval (seconds)")
    parser.add_argument("--port-interval", type=float, default=180, help="Port cycle interval (seconds)")
    parser.add_argument("--doctype-interval", type=float, default=300, help="DocType cycle interval (seconds)")
    parser.add_argument("--lineage-interval", type=float, default=600, help="Lineage cycle interval (seconds)")
    parser.add_argument("--rollup-interval", type=float, default=3600, help="Rollup cycle interval (seconds)")
    parser.add_argument("--npu-lineage-interval", type=float, default=900, help="NPU lineage cycle interval in seconds (default 15 min)")
    parser.add_argument("--status", action="store_true", help="Show enrichment progress and exit")
    parser.add_argument("--json", action="store_true", help="Output in JSON")

    args = parser.parse_args()

    if args.status:
        print("P6 KRAKEN KEEPER — Enrichment Status")
        print("=" * 50)
        print(f"  SSOT:  {SSOT_DB}")
        print(f"  Model: {args.model}")
        print(f"  State: {STATE_FILE}")
        print()

        kraken = KrakenKeeper(model=args.model)
        progress = kraken.get_enrichment_progress()

        if args.json:
            # Load saved state too
            saved = {}
            if STATE_FILE.exists():
                with open(STATE_FILE, "r") as f:
                    saved = json.load(f)
            print(json.dumps({"progress": progress, "saved_state": saved}, indent=2))
            return

        if "error" in progress:
            print(f"  ERROR: {progress['error']}")
            return

        print(f"  Documents:  {progress['total_docs']:,}")
        print(f"  Events:     {progress['total_events']:,} ({progress['kraken_events']} from Kraken)")
        print(f"  Lineage:    {progress['lineage_edges']} edges")
        print()
        print(f"  Enrichment Coverage:")
        print(f"    BLUFs:    {progress['enrichment_pct']['bluf']:5.1f}%  ({progress['missing_bluf']:,} remaining)")
        print(f"    Ports:    {progress['enrichment_pct']['port']:5.1f}%  ({progress['missing_port']:,} remaining)")
        print(f"    DocTypes: {progress['enrichment_pct']['doctype']:5.1f}%  ({progress['missing_doctype']:,} remaining)")
        print()

        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)
            print(f"  Last Run:")
            stats = saved.get("stats", {})
            print(f"    BLUFs generated:  {stats.get('blufs_generated', 0)}")
            print(f"    Ports classified: {stats.get('ports_classified', 0)}")
            print(f"    Types classified: {stats.get('doctypes_classified', 0)}")
            print(f"    Lineage edges:    {stats.get('lineage_edges_added', 0)}")
            print(f"    Ollama calls:     {stats.get('ollama_calls', 0)}")
            print(f"    Saved at:         {saved.get('saved_at', '?')}")
        else:
            print("  No previous state found. Daemon has not been run yet.")

        print(f"\n  Depths ARE dreams. The Kraken feeds.")
        return

    # Build daemon
    kraken = KrakenKeeper(
        dry_run=args.dry_run,
        model=args.model,
        batch_size=args.batch_size,
    )

    enabled_tasks = set(args.tasks.split(","))
    intervals = {
        "bluf": args.bluf_interval,
        "port": args.port_interval,
        "doctype": args.doctype_interval,
        "lineage": args.lineage_interval,
        "rollup": args.rollup_interval,
        "npu_lineage": args.npu_lineage_interval,
        "heartbeat": 60,
    }

    # Resource governor — start background VRAM / RAM monitor
    if _RESOURCE_GOVERNOR_AVAILABLE and not args.dry_run:
        _start_rg_monitor(interval_s=30.0)
        snap = _get_resource_snapshot()
        if snap is not None:
            print(
                f"  [RESOURCE GOV] VRAM {snap.vram_used_gb:.1f}/{_VRAM_BUDGET_GB:.1f} GB  "
                f"RAM {snap.ram_used_pct:.0f}%  "
                f"GPU gate: {'GO' if snap.safe_to_infer_gpu else 'HOLD — ' + snap.throttle_reason}",
                file=sys.stderr,
            )
            if not snap.safe_to_infer_gpu:
                print("  [RESOURCE GOV] Evicting idle Ollama models to free headroom...", file=sys.stderr)
                _evict_ollama(verbose=True)

    # Signal handling
    def handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. Stopping Kraken Keeper...")
        kraken.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    asyncio.run(daemon_loop(kraken, intervals, enabled_tasks, single=args.once))


if __name__ == "__main__":
    main()
