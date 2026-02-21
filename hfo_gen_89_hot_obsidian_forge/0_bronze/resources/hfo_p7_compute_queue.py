#!/usr/bin/env python3
"""
hfo_p7_compute_queue.py — GPU/NPU Unified Compute Queue
==========================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Layer: Infrastructure
Commander: SUMMONER OF SEALS AND SPHERES

PURPOSE:
    Unified work queue that keeps both GPU (Intel Arc 140V, 16 GB) and NPU
    (Intel AI Boost) saturated with useful work. The operator reports both
    are "underutilized and weird" — this queue fixes that by feeding work
    to both accelerators concurrently.

    This is the PLANAR_BINDING compute-plane extension:
    - HFO_DIMENSIONAL_ANCHOR diagnosed the problem (SEVERELY_UNDERUTILIZED)
    - HFO_PLANAR_BINDING binds daemon processes
    - This queue binds the COMPUTE PLANES: GPU plane + NPU plane

ARCHITECTURE:
    ┌───────────────────────────────────────────────────────────────┐
    │  COMPUTE QUEUE (P7)                                           │
    │                                                               │
    │  ┌───────────────────────────────────────────────────────┐   │
    │  │  WORK QUEUE (asyncio.PriorityQueue)                   │   │
    │  │  [embed_all, llm_summarize, embed_search, llm_eval]   │   │
    │  └───────────┬───────────────────────────┬───────────────┘   │
    │              │                           │                    │
    │   ┌──────────▼──────────┐   ┌───────────▼──────────────┐    │
    │   │  GPU WORKER         │   │  NPU WORKER              │    │
    │   │  Ollama LLM infer   │   │  OpenVINO embeddings     │    │
    │   │  phi4:14b, qwen3:8b │   │  all-MiniLM-L6-v2       │    │
    │   │  gemma3:4b, etc.    │   │  384-dim, ~213 emb/sec   │    │
    │   │                     │   │                           │    │
    │   │  Arc 140V (16 GB)   │   │  AI Boost (NPU 4000)     │    │
    │   └─────────┬───────────┘   └──────────┬───────────────┘    │
    │             │                           │                     │
    │             └─────────┬─────────────────┘                     │
    │                       │                                       │
    │            ┌──────────▼──────────┐                            │
    │            │  RESULT COLLECTOR   │                            │
    │            │  → SSOT stigmergy   │                            │
    │            └─────────────────────┘                            │
    └───────────────────────────────────────────────────────────────┘

WORK TYPES:
    ┌──────────────────┬────────┬─────────────────────────────────────┐
    │ Work Type        │ Device │ Description                         │
    ├──────────────────┼────────┼─────────────────────────────────────┤
    │ embed_batch      │ NPU    │ Embed SSOT docs (384-dim vectors)   │
    │ embed_search     │ NPU    │ Semantic similarity search          │
    │ llm_generate     │ GPU    │ LLM text generation via Ollama      │
    │ llm_summarize    │ GPU    │ Summarize document text             │
    │ llm_classify     │ GPU    │ Classify/tag documents              │
    │ llm_eval         │ GPU    │ Evaluate/score content quality      │
    └──────────────────┴────────┴─────────────────────────────────────┘

DEVICE AFFINITY:
    GPU: Large language model inference (Ollama, 100% VRAM offload)
    NPU: Small model inference (embeddings, classification), ~5ms per call
    CPU: Fallback only — both GPU and NPU have dedicated memory

SPELLS:
    start       Start the queue daemon (GPU + NPU workers)
    submit      Submit work items to the queue
    status      Queue status + worker utilization
    drain       Process all pending work and stop
    embed-all   Submit all unembedded SSOT docs to NPU queue
    enrich      Submit SSOT docs for GPU enrichment (summarize/classify/eval)

EVENT TYPES:
    hfo.gen89.p7.compute_queue.started    — Queue daemon started
    hfo.gen89.p7.compute_queue.completed  — Work item completed
    hfo.gen89.p7.compute_queue.drained    — Queue fully drained
    hfo.gen89.p7.compute_queue.error      — Work item failed
    hfo.gen89.p7.compute_queue.stats      — Periodic stats snapshot

Medallion: bronze
Port: P7 NAVIGATE
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import secrets
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from hfo_ssot_write import get_db_readwrite as get_db_rw

# Force UTF-8 stdout on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


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
SOURCE_TAG = f"hfo_p7_compute_queue_gen{GEN}"

# ── Constants ──
OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
VRAM_BUDGET_GB = 15.0
STATS_INTERVAL_S = 30  # How often to log stats


# ═══════════════════════════════════════════════════════════════
# § 1  WORK ITEMS
# ═══════════════════════════════════════════════════════════════

@dataclass(order=True)
class WorkItem:
    """A unit of work for the compute queue."""
    priority: int                        # Lower = higher priority (0 = urgent)
    work_type: str = field(compare=False)  # embed_batch, llm_generate, etc.
    device: str = field(compare=False)     # GPU, NPU
    payload: dict = field(compare=False, default_factory=dict)
    submitted_at: float = field(compare=False, default_factory=time.time)
    work_id: str = field(compare=False, default_factory=lambda: secrets.token_hex(6))

    @property
    def age_s(self) -> float:
        return time.time() - self.submitted_at


@dataclass
class WorkResult:
    """Result of processing a work item."""
    work_id: str
    work_type: str
    device: str
    status: str          # completed, error
    elapsed_s: float
    output: dict = field(default_factory=dict)
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
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
# § 3  NPU WORKER — Embedding inference on Intel AI Boost
# ═══════════════════════════════════════════════════════════════

class NPUWorker:
    """
    Processes NPU-bound work items (embeddings, small model inference).
    Uses OpenVINO pinned to NPU device — zero GPU VRAM impact.
    """

    def __init__(self):
        self._embedder = None
        self._loaded = False
        self.items_processed = 0
        self.items_errored = 0
        self.total_inference_ms = 0.0
        self._name = "NPU_WORKER"

    def load(self):
        """Load the NPU embedder (one-time compile ~620ms)."""
        if self._loaded:
            return
        try:
            from hfo_npu_embedder import NPUEmbedder, ensure_embeddings_table
            self._embedder = NPUEmbedder(device="NPU")
            self._embedder.load()
            self._loaded = True
            self._ensure_table = ensure_embeddings_table
            self._store_embedding_fn = None
            # Import store/search helpers
            from hfo_npu_embedder import (
                store_embedding, get_embedding_stats, embedding_to_blob,
                cosine_similarity, blob_to_embedding, find_similar,
                search_similar_to_text,
            )
            self._store_embedding = store_embedding
            self._get_stats = get_embedding_stats
            self._search_fn = search_similar_to_text
        except Exception as e:
            print(f"  [{self._name}] Failed to load: {e}")
            self._loaded = False

    async def process(self, item: WorkItem) -> WorkResult:
        """Process a single NPU work item."""
        if not self._loaded:
            self.load()
        if not self._loaded:
            return WorkResult(
                work_id=item.work_id, work_type=item.work_type,
                device="NPU", status="error", elapsed_s=0,
                error="NPU embedder not loaded",
            )

        t0 = time.time()
        try:
            if item.work_type == "embed_batch":
                result = await self._do_embed_batch(item.payload)
            elif item.work_type == "embed_search":
                result = await self._do_embed_search(item.payload)
            else:
                return WorkResult(
                    work_id=item.work_id, work_type=item.work_type,
                    device="NPU", status="error", elapsed_s=0,
                    error=f"Unknown NPU work type: {item.work_type}",
                )

            elapsed = time.time() - t0
            self.items_processed += 1
            self.total_inference_ms += elapsed * 1000
            return WorkResult(
                work_id=item.work_id, work_type=item.work_type,
                device="NPU", status="completed", elapsed_s=round(elapsed, 3),
                output=result,
            )

        except Exception as e:
            elapsed = time.time() - t0
            self.items_errored += 1
            return WorkResult(
                work_id=item.work_id, work_type=item.work_type,
                device="NPU", status="error", elapsed_s=round(elapsed, 3),
                error=str(e)[:200],
            )

    async def _do_embed_batch(self, payload: dict) -> dict:
        """Embed a batch of SSOT documents."""
        batch_size = payload.get("batch_size", 50)
        conn_ro = get_db_ro()

        # Find unembedded documents
        from hfo_npu_embedder import ensure_embeddings_table
        conn_rw = get_db_rw()
        ensure_embeddings_table(conn_rw)

        rows = conn_ro.execute(
            """SELECT d.id, d.title, d.bluf, substr(d.content, 1, 2000) as content_head
               FROM documents d
               LEFT JOIN embeddings e ON d.id = e.doc_id
               WHERE e.doc_id IS NULL
               ORDER BY d.id
               LIMIT ?""",
            (batch_size,),
        ).fetchall()
        conn_ro.close()

        if not rows:
            conn_rw.close()
            return {"embedded": 0, "note": "all docs already embedded"}

        embedded = 0
        errors = 0
        for row in rows:
            doc_id = row[0]
            title = row[1] or ""
            bluf = row[2] or ""
            content_head = row[3] or ""

            text_parts = []
            if title and title != "---":
                text_parts.append(title)
            if bluf and bluf != "---":
                text_parts.append(bluf)
            if content_head:
                text_parts.append(content_head[:500])
            text = " ".join(text_parts).strip()
            if not text:
                continue

            try:
                vec = self._embedder.embed(text)
                self._store_embedding(conn_rw, doc_id, vec, device=self._embedder.device)
                embedded += 1
            except Exception:
                errors += 1

            # Yield to event loop periodically
            if embedded % 10 == 0:
                await asyncio.sleep(0)

        stats = self._get_stats(conn_rw)
        conn_rw.close()

        return {
            "embedded": embedded,
            "errors": errors,
            "batch_size": batch_size,
            "coverage": stats,
            "embedder_stats": self._embedder.stats,
        }

    async def _do_embed_search(self, payload: dict) -> dict:
        """Semantic similarity search."""
        query = payload.get("query", "")
        top_k = payload.get("top_k", 10)
        min_score = payload.get("min_score", 0.3)

        results = self._search_fn(query, top_k=top_k, min_score=min_score)
        return {"query": query, "results": results, "count": len(results)}

    @property
    def stats(self) -> dict:
        base = {
            "worker": self._name,
            "loaded": self._loaded,
            "items_processed": self.items_processed,
            "items_errored": self.items_errored,
            "total_inference_ms": round(self.total_inference_ms, 1),
        }
        if self._loaded and self._embedder:
            base["embedder"] = self._embedder.stats
        return base


# ═══════════════════════════════════════════════════════════════
# § 4  GPU WORKER — LLM inference via Ollama on Intel Arc 140V
# ═══════════════════════════════════════════════════════════════

class GPUWorker:
    """
    Processes GPU-bound work items (LLM generation, summarization, classification).
    Uses Ollama with 100% GPU offload on Intel Arc 140V (16 GB VRAM).
    """

    def __init__(self, default_model: str = "phi4:14b"):
        self.default_model = default_model
        self.items_processed = 0
        self.items_errored = 0
        self.total_tokens = 0
        self.total_inference_ms = 0.0
        self._name = "GPU_WORKER"

    async def process(self, item: WorkItem) -> WorkResult:
        """Process a single GPU work item."""
        if not HAS_HTTPX:
            return WorkResult(
                work_id=item.work_id, work_type=item.work_type,
                device="GPU", status="error", elapsed_s=0,
                error="httpx not installed",
            )

        t0 = time.time()
        try:
            if item.work_type == "llm_generate":
                result = await self._do_generate(item.payload)
            elif item.work_type == "llm_summarize":
                result = await self._do_summarize(item.payload)
            elif item.work_type == "llm_classify":
                result = await self._do_classify(item.payload)
            elif item.work_type == "llm_eval":
                result = await self._do_eval(item.payload)
            else:
                return WorkResult(
                    work_id=item.work_id, work_type=item.work_type,
                    device="GPU", status="error", elapsed_s=0,
                    error=f"Unknown GPU work type: {item.work_type}",
                )

            elapsed = time.time() - t0
            self.items_processed += 1
            self.total_inference_ms += elapsed * 1000
            self.total_tokens += result.get("eval_count", 0)
            return WorkResult(
                work_id=item.work_id, work_type=item.work_type,
                device="GPU", status="completed", elapsed_s=round(elapsed, 3),
                output=result,
            )

        except Exception as e:
            elapsed = time.time() - t0
            self.items_errored += 1
            return WorkResult(
                work_id=item.work_id, work_type=item.work_type,
                device="GPU", status="error", elapsed_s=round(elapsed, 3),
                error=str(e)[:200],
            )

    async def _ollama_generate(self, model: str, prompt: str,
                                num_predict: int = 200,
                                system: str = "") -> dict:
        """Call Ollama /api/generate (non-streaming)."""
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": num_predict},
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{OLLAMA_BASE}/api/generate", json=body)
            r.raise_for_status()
            return r.json()

    async def _do_generate(self, payload: dict) -> dict:
        """Raw LLM generation."""
        model = payload.get("model", self.default_model)
        prompt = payload.get("prompt", "")
        num_predict = payload.get("num_predict", 200)
        system = payload.get("system", "")

        data = await self._ollama_generate(model, prompt, num_predict, system)
        return {
            "model": model,
            "response": data.get("response", ""),
            "eval_count": data.get("eval_count", 0),
            "eval_duration_ns": data.get("eval_duration", 0),
            "tok_s": round(
                data.get("eval_count", 0) / max(data.get("eval_duration", 1) / 1e9, 0.001), 1
            ),
        }

    async def _do_summarize(self, payload: dict) -> dict:
        """Summarize a document."""
        doc_id = payload.get("doc_id")
        text = payload.get("text", "")
        model = payload.get("model", self.default_model)

        if doc_id and not text:
            conn = get_db_ro()
            row = conn.execute(
                "SELECT title, bluf, substr(content, 1, 4000) FROM documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
            conn.close()
            if row:
                text = f"Title: {row[0]}\nBLUF: {row[1]}\n\n{row[2]}"

        if not text:
            return {"error": "No text to summarize"}

        prompt = f"Summarize the following document in 2-3 sentences:\n\n{text[:3000]}"
        data = await self._ollama_generate(model, prompt, num_predict=150,
                                           system="You are a precise summarizer. Be concise.")
        return {
            "model": model,
            "doc_id": doc_id,
            "summary": data.get("response", ""),
            "eval_count": data.get("eval_count", 0),
        }

    async def _do_classify(self, payload: dict) -> dict:
        """Classify/tag a document."""
        doc_id = payload.get("doc_id")
        text = payload.get("text", "")
        model = payload.get("model", self.default_model)
        categories = payload.get("categories",
            "architecture,governance,testing,operations,documentation,tooling,research,meta")

        if doc_id and not text:
            conn = get_db_ro()
            row = conn.execute(
                "SELECT title, bluf, substr(content, 1, 2000) FROM documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
            conn.close()
            if row:
                text = f"Title: {row[0]}\nBLUF: {row[1]}\n\n{row[2]}"

        if not text:
            return {"error": "No text to classify"}

        prompt = (
            f"Classify this document into exactly one of these categories: {categories}\n\n"
            f"Document:\n{text[:2000]}\n\n"
            f"Reply with ONLY the category name, nothing else."
        )
        data = await self._ollama_generate(model, prompt, num_predict=20,
                                           system="You are a document classifier. Reply with one word only.")
        return {
            "model": model,
            "doc_id": doc_id,
            "classification": data.get("response", "").strip().lower(),
            "eval_count": data.get("eval_count", 0),
        }

    async def _do_eval(self, payload: dict) -> dict:
        """Evaluate content quality (bronze → silver gate check)."""
        doc_id = payload.get("doc_id")
        text = payload.get("text", "")
        model = payload.get("model", self.default_model)

        if doc_id and not text:
            conn = get_db_ro()
            row = conn.execute(
                "SELECT title, bluf, substr(content, 1, 3000) FROM documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
            conn.close()
            if row:
                text = f"Title: {row[0]}\nBLUF: {row[1]}\n\n{row[2]}"

        if not text:
            return {"error": "No text to evaluate"}

        prompt = (
            "Rate this document's quality on a 1-10 scale across these dimensions:\n"
            "1. Factual accuracy (are claims verifiable?)\n"
            "2. Completeness (is the topic fully covered?)\n"
            "3. Clarity (is it well-written and unambiguous?)\n"
            "4. Actionability (can someone act on this?)\n\n"
            f"Document:\n{text[:2500]}\n\n"
            "Reply in JSON format: {\"accuracy\": N, \"completeness\": N, \"clarity\": N, "
            "\"actionability\": N, \"overall\": N, \"verdict\": \"promote|hold|reject\", "
            "\"reason\": \"brief explanation\"}"
        )
        data = await self._ollama_generate(model, prompt, num_predict=200,
                                           system="You are a quality evaluator. Reply in valid JSON only.")
        response = data.get("response", "")
        # Try to parse JSON from response
        eval_result: dict[str, Any] = {"raw_response": response}
        try:
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                eval_result.update(json.loads(response[start:end]))
        except (json.JSONDecodeError, ValueError):
            eval_result["parse_error"] = True

        eval_result["model"] = model
        eval_result["doc_id"] = doc_id
        eval_result["eval_count"] = data.get("eval_count", 0)
        return eval_result

    @property
    def stats(self) -> dict:
        return {
            "worker": self._name,
            "default_model": self.default_model,
            "items_processed": self.items_processed,
            "items_errored": self.items_errored,
            "total_tokens": self.total_tokens,
            "total_inference_ms": round(self.total_inference_ms, 1),
            "avg_tok_s": round(
                self.total_tokens / max(self.total_inference_ms / 1000, 0.001), 1
            ) if self.total_tokens > 0 else 0,
        }


# ═══════════════════════════════════════════════════════════════
# § 5  COMPUTE QUEUE — The unified dispatcher
# ═══════════════════════════════════════════════════════════════

class ComputeQueue:
    """
    Unified compute queue that dispatches work to GPU and NPU workers
    concurrently. Both accelerators run in parallel — embedding on NPU
    while LLM inference runs on GPU.

    SBE:
      Given  GPU worker (Ollama) and NPU worker (OpenVINO) are initialized
      When   work items are submitted to the queue
      Then   GPU items route to GPU worker and NPU items route to NPU worker
      And    both workers process in parallel
      And    results are collected and logged to SSOT
    """

    def __init__(self, gpu_model: str = "phi4:14b"):
        self.gpu_worker = GPUWorker(default_model=gpu_model)
        self.npu_worker = NPUWorker()
        self.gpu_queue: asyncio.PriorityQueue[WorkItem] = asyncio.PriorityQueue()
        self.npu_queue: asyncio.PriorityQueue[WorkItem] = asyncio.PriorityQueue()
        self.results: list[WorkResult] = []
        self._running = False
        self._gpu_task: Optional[asyncio.Task] = None
        self._npu_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
        self._start_time = 0.0

    def submit(self, item: WorkItem):
        """Submit a work item to the appropriate device queue."""
        if item.device == "NPU":
            self.npu_queue.put_nowait(item)
        elif item.device == "GPU":
            self.gpu_queue.put_nowait(item)
        else:
            raise ValueError(f"Unknown device: {item.device}")

    def submit_embed_batch(self, batch_size: int = 50, priority: int = 5):
        """Convenience: submit an embedding batch to NPU."""
        self.submit(WorkItem(
            priority=priority,
            work_type="embed_batch",
            device="NPU",
            payload={"batch_size": batch_size},
        ))

    def submit_embed_search(self, query: str, top_k: int = 10, priority: int = 1):
        """Convenience: submit a semantic search to NPU."""
        self.submit(WorkItem(
            priority=priority,
            work_type="embed_search",
            device="NPU",
            payload={"query": query, "top_k": top_k},
        ))

    def submit_llm_generate(self, prompt: str, model: str = "",
                            num_predict: int = 200, priority: int = 3):
        """Convenience: submit LLM generation to GPU."""
        self.submit(WorkItem(
            priority=priority,
            work_type="llm_generate",
            device="GPU",
            payload={"prompt": prompt, "model": model or self.gpu_worker.default_model,
                     "num_predict": num_predict},
        ))

    def submit_summarize(self, doc_id: int, model: str = "", priority: int = 5):
        """Convenience: submit document summarization to GPU."""
        self.submit(WorkItem(
            priority=priority,
            work_type="llm_summarize",
            device="GPU",
            payload={"doc_id": doc_id, "model": model or self.gpu_worker.default_model},
        ))

    def submit_classify(self, doc_id: int, model: str = "", priority: int = 5):
        """Convenience: submit document classification to GPU."""
        self.submit(WorkItem(
            priority=priority,
            work_type="llm_classify",
            device="GPU",
            payload={"doc_id": doc_id, "model": model or self.gpu_worker.default_model},
        ))

    def submit_eval(self, doc_id: int, model: str = "", priority: int = 5):
        """Convenience: submit document quality eval to GPU."""
        self.submit(WorkItem(
            priority=priority,
            work_type="llm_eval",
            device="GPU",
            payload={"doc_id": doc_id, "model": model or self.gpu_worker.default_model},
        ))

    async def _gpu_loop(self):
        """GPU worker loop — processes items from GPU queue."""
        print(f"  [GPU_WORKER] Started (model: {self.gpu_worker.default_model})")
        while self._running or not self.gpu_queue.empty():
            try:
                item = await asyncio.wait_for(self.gpu_queue.get(), timeout=2.0)
                print(f"  [GPU] Processing: {item.work_type} [{item.work_id}]")
                result = await self.gpu_worker.process(item)
                self.results.append(result)
                self._log_result(result)
                self.gpu_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"  [GPU_WORKER] Error: {e}")

    async def _npu_loop(self):
        """NPU worker loop — processes items from NPU queue."""
        self.npu_worker.load()
        print(f"  [NPU_WORKER] Started (device: {self.npu_worker._embedder.device if self.npu_worker._loaded else 'NOT_LOADED'})")
        while self._running or not self.npu_queue.empty():
            try:
                item = await asyncio.wait_for(self.npu_queue.get(), timeout=2.0)
                print(f"  [NPU] Processing: {item.work_type} [{item.work_id}]")
                result = await self.npu_worker.process(item)
                self.results.append(result)
                self._log_result(result)
                self.npu_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"  [NPU_WORKER] Error: {e}")

    async def _stats_loop(self):
        """Periodic stats reporter."""
        while self._running:
            await asyncio.sleep(STATS_INTERVAL_S)
            if self._running:
                self._print_stats()

    def _log_result(self, result: WorkResult):
        """Log a completed work item."""
        icon = "✓" if result.status == "completed" else "✗"
        detail = ""
        if result.work_type == "embed_batch":
            embedded = result.output.get("embedded", 0)
            coverage = result.output.get("coverage", {})
            detail = f" ({embedded} docs, {coverage.get('coverage_pct', '?')}% coverage)"
        elif result.work_type == "embed_search":
            count = result.output.get("count", 0)
            detail = f" ({count} results)"
        elif result.work_type in ("llm_generate", "llm_summarize", "llm_classify", "llm_eval"):
            tokens = result.output.get("eval_count", 0)
            detail = f" ({tokens} tokens)"
        print(f"  [{result.device}] {icon} {result.work_type} [{result.work_id}] "
              f"{result.elapsed_s:.2f}s{detail}")

    def _print_stats(self):
        """Print current queue/worker stats."""
        elapsed = time.time() - self._start_time
        print(f"\n  --- Queue Stats ({elapsed:.0f}s) ---")
        print(f"  GPU queue: {self.gpu_queue.qsize()} pending | "
              f"processed: {self.gpu_worker.items_processed} | "
              f"errors: {self.gpu_worker.items_errored}")
        print(f"  NPU queue: {self.npu_queue.qsize()} pending | "
              f"processed: {self.npu_worker.items_processed} | "
              f"errors: {self.npu_worker.items_errored}")
        total = self.gpu_worker.items_processed + self.npu_worker.items_processed
        print(f"  Total completed: {total}")
        print()

    async def run(self, drain: bool = False):
        """
        Start the queue and process items.
        If drain=True, stop when both queues are empty.
        """
        self._running = True
        self._start_time = time.time()

        # Start workers
        self._gpu_task = asyncio.create_task(self._gpu_loop())
        self._npu_task = asyncio.create_task(self._npu_loop())
        if not drain:
            self._stats_task = asyncio.create_task(self._stats_loop())

        # Write start event
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.compute_queue.started",
                        f"QUEUE_START:gpu={self.gpu_worker.default_model}",
                        {"gpu_model": self.gpu_worker.default_model,
                         "gpu_queue_size": self.gpu_queue.qsize(),
                         "npu_queue_size": self.npu_queue.qsize()})
            conn.close()
        except Exception:
            pass

        if drain:
            # Wait for both queues to drain
            await asyncio.gather(
                self.gpu_queue.join(),
                self.npu_queue.join(),
            )
            self._running = False
            # Give workers a moment to exit
            await asyncio.sleep(3)
        else:
            # Run until interrupted
            try:
                while self._running:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                self._running = False

        # Cleanup
        for task in [self._gpu_task, self._npu_task, self._stats_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        # Write drain/stop event
        elapsed = time.time() - self._start_time
        try:
            conn = get_db_rw()
            write_event(conn, f"hfo.gen{GEN}.p7.compute_queue.drained",
                        f"QUEUE_DRAIN:gpu={self.gpu_worker.items_processed}:npu={self.npu_worker.items_processed}",
                        {"elapsed_s": round(elapsed, 1),
                         "gpu_stats": self.gpu_worker.stats,
                         "npu_stats": self.npu_worker.stats,
                         "total_results": len(self.results)})
            conn.close()
        except Exception:
            pass

        return {
            "elapsed_s": round(elapsed, 1),
            "gpu": self.gpu_worker.stats,
            "npu": self.npu_worker.stats,
            "total_completed": len(self.results),
        }


# ═══════════════════════════════════════════════════════════════
# § 6  SPELL: EMBED-ALL — Fill NPU queue with all SSOT docs
# ═══════════════════════════════════════════════════════════════

async def spell_embed_all(batch_size: int = 100) -> dict:
    """
    Submit all unembedded SSOT docs to NPU for embedding.
    Runs the queue in drain mode — processes everything and stops.

    SBE:
      Given  SSOT has 9,861 docs and some are unembedded
      When   embed-all is cast
      Then   NPU embeds all remaining docs at ~213 emb/sec
      And    coverage reaches 100%
    """
    print("  [EMBED-ALL] Queuing all unembedded SSOT docs for NPU\n")

    # Check how many need embedding
    conn = get_db_ro()
    try:
        from hfo_npu_embedder import ensure_embeddings_table, get_embedding_stats
        conn_rw = get_db_rw()
        ensure_embeddings_table(conn_rw)
        stats = get_embedding_stats(conn_rw)
        conn_rw.close()
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.close()
        return {"error": str(e)}
    conn.close()

    remaining = stats["remaining"]
    print(f"  Coverage: {stats['total_embedded']}/{stats['total_docs']} ({stats['coverage_pct']}%)")
    print(f"  Remaining: {remaining}")

    if remaining == 0:
        print("  All documents already embedded!")
        return {"status": "ALREADY_COMPLETE", "coverage": stats}

    # Estimate time
    est_seconds = remaining / 213  # ~213 emb/sec measured
    print(f"  Estimated time: ~{est_seconds:.0f}s ({remaining} docs at ~213 emb/sec)")
    print()

    # Create queue and submit batches
    queue = ComputeQueue()
    num_batches = (remaining + batch_size - 1) // batch_size
    for i in range(num_batches):
        queue.submit_embed_batch(batch_size=batch_size, priority=5)

    print(f"  Submitted {num_batches} embed batches to NPU queue")
    print()

    # Drain
    result = await queue.run(drain=True)

    # Final stats
    try:
        conn_rw = get_db_rw()
        final_stats = get_embedding_stats(conn_rw)
        conn_rw.close()
    except Exception:
        final_stats = {}

    print(f"\n  ═══ EMBED-ALL COMPLETE ═══")
    print(f"  Final coverage: {final_stats.get('total_embedded', '?')}/{final_stats.get('total_docs', '?')} "
          f"({final_stats.get('coverage_pct', '?')}%)")
    print(f"  NPU stats: {queue.npu_worker.stats}")
    print(f"  Elapsed: {result['elapsed_s']}s")

    return {"status": "COMPLETE", "result": result, "coverage": final_stats}


# ═══════════════════════════════════════════════════════════════
# § 7  SPELL: ENRICH — Submit docs for GPU enrichment
# ═══════════════════════════════════════════════════════════════

async def spell_enrich(
    doc_ids: list[int] | None = None,
    task: str = "summarize",
    model: str = "",
    limit: int = 10,
) -> dict:
    """
    Submit SSOT docs for GPU enrichment (summarize/classify/eval).
    Runs both GPU and NPU concurrently — NPU embeds while GPU summarizes.

    SBE:
      Given  SSOT docs exist that haven't been enriched
      When   enrich is cast with task type
      Then   GPU processes the enrichment
      And    NPU simultaneously embeds any unembedded docs
      And    results are returned
    """
    print(f"  [ENRICH] Task: {task} | Limit: {limit}\n")

    # Get target docs
    conn = get_db_ro()
    if doc_ids:
        placeholders = ",".join("?" * len(doc_ids))
        rows = conn.execute(
            f"SELECT id, title FROM documents WHERE id IN ({placeholders}) LIMIT ?",
            (*doc_ids, limit),
        ).fetchall()
    else:
        # Pick docs with highest word count (most valuable to enrich)
        rows = conn.execute(
            "SELECT id, title FROM documents WHERE word_count > 100 ORDER BY word_count DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()

    if not rows:
        print("  No documents to enrich")
        return {"status": "NO_DOCS"}

    # Create queue
    queue = ComputeQueue(gpu_model=model or "phi4:14b")

    # Submit GPU enrichment tasks
    for row in rows:
        doc_id = row[0]
        if task == "summarize":
            queue.submit_summarize(doc_id, model=model, priority=3)
        elif task == "classify":
            queue.submit_classify(doc_id, model=model, priority=3)
        elif task == "eval":
            queue.submit_eval(doc_id, model=model, priority=3)

    # ALSO submit NPU embedding work in parallel
    queue.submit_embed_batch(batch_size=100, priority=5)

    print(f"  GPU: {len(rows)} {task} tasks queued")
    print(f"  NPU: 1 embed batch queued (background)")
    print()

    # Drain both queues concurrently
    result = await queue.run(drain=True)

    # Collect enrichment results
    enrichment_results = []
    for r in queue.results:
        if r.device == "GPU" and r.status == "completed":
            enrichment_results.append({
                "doc_id": r.output.get("doc_id"),
                "task": r.work_type.replace("llm_", ""),
                "result": {k: v for k, v in r.output.items()
                           if k not in ("raw_response",) and not k.startswith("eval_")},
                "elapsed_s": r.elapsed_s,
            })

    print(f"\n  ═══ ENRICH COMPLETE ═══")
    print(f"  GPU: {queue.gpu_worker.stats}")
    print(f"  NPU: {queue.npu_worker.stats}")

    return {
        "status": "COMPLETE",
        "task": task,
        "enrichments": enrichment_results,
        "queue_stats": result,
    }


# ═══════════════════════════════════════════════════════════════
# § 8  SPELL: STATUS — Queue + device utilization
# ═══════════════════════════════════════════════════════════════

def spell_status() -> dict:
    """Show current compute resource status across all devices."""
    print("  [STATUS] Compute Resource Status\n")

    result: dict[str, Any] = {"devices": {}}

    # GPU via Ollama
    if HAS_HTTPX:
        try:
            r = httpx.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
            models = r.json().get("models", [])
            total_vram = sum(m.get("size_vram", 0) / (1024**3) for m in models)
            result["devices"]["GPU"] = {
                "name": "Intel Arc 140V (16 GB)",
                "models_loaded": len(models),
                "vram_used_gb": round(total_vram, 1),
                "vram_budget_gb": VRAM_BUDGET_GB,
                "utilization_pct": round(total_vram / VRAM_BUDGET_GB * 100, 1),
                "models": [
                    {"name": m["name"],
                     "vram_gb": round(m.get("size_vram", 0) / (1024**3), 1),
                     "gpu_pct": round(m.get("size_vram", 0) / max(m.get("size", 1), 1) * 100)}
                    for m in models
                ],
            }
            gpu = result["devices"]["GPU"]
            print(f"  GPU: {gpu['models_loaded']} models, {gpu['vram_used_gb']:.1f}/{VRAM_BUDGET_GB:.0f} GB "
                  f"({gpu['utilization_pct']:.0f}%)")
            for m in gpu["models"]:
                print(f"    - {m['name']:30s} {m['vram_gb']:.1f} GB ({m['gpu_pct']}% GPU)")
        except Exception as e:
            result["devices"]["GPU"] = {"error": str(e)[:80]}
            print(f"  GPU: ERROR — {str(e)[:60]}")

    # NPU via OpenVINO
    try:
        import openvino as ov
        core = ov.Core()
        devices = core.available_devices
        npu_present = "NPU" in devices
        result["devices"]["NPU"] = {
            "name": "Intel AI Boost",
            "openvino_version": ov.__version__,
            "detected": npu_present,
            "all_devices": devices,
        }
        print(f"  NPU: {'✓ detected' if npu_present else '✗ not detected'} "
              f"(OpenVINO {ov.__version__})")
    except ImportError:
        result["devices"]["NPU"] = {"error": "OpenVINO not installed"}
        print(f"  NPU: ✗ OpenVINO not installed")

    # Embedding coverage
    try:
        from hfo_npu_embedder import get_embedding_stats, ensure_embeddings_table
        conn = get_db_rw()
        ensure_embeddings_table(conn)
        stats = get_embedding_stats(conn)
        conn.close()
        result["embeddings"] = stats
        print(f"  Embeddings: {stats['total_embedded']}/{stats['total_docs']} "
              f"({stats['coverage_pct']}%)")
    except Exception as e:
        print(f"  Embeddings: ERROR — {e}")

    # Recent queue events
    try:
        conn = get_db_ro()
        rows = conn.execute("""
            SELECT id, event_type, timestamp, subject
            FROM stigmergy_events
            WHERE event_type LIKE '%compute_queue%'
            ORDER BY timestamp DESC LIMIT 5
        """).fetchall()
        conn.close()
        if rows:
            print(f"\n  Recent queue events:")
            for r in rows:
                ts = r["timestamp"][:19]
                etype = r["event_type"].split(".")[-1]
                print(f"    {ts}  {etype:12s}  {r['subject'][:60]}")
        result["recent_events"] = [dict(r) for r in rows]
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════
# § 9  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "=" * 64)
    print("  P7 SUMMONER OF SEALS AND SPHERES — COMPUTE QUEUE")
    print("  " + "-" * 64)
    print("  GPU: Intel Arc 140V (16 GB) — Ollama LLM inference")
    print("  NPU: Intel AI Boost — OpenVINO embeddings (213 emb/sec)")
    print("  Unified queue: both accelerators saturated concurrently")
    print("  " + "=" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="P7 GPU/NPU Compute Queue (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Spells:
  status              Show GPU/NPU/embedding status
  embed-all           Embed all SSOT docs on NPU (~46s for 9,861 docs)
  enrich              GPU enrichment + NPU embedding in parallel
  search <query>      Semantic search using NPU embeddings

Examples:
  python hfo_p7_compute_queue.py status
  python hfo_p7_compute_queue.py embed-all
  python hfo_p7_compute_queue.py enrich --task summarize --limit 5
  python hfo_p7_compute_queue.py enrich --task classify --limit 10
  python hfo_p7_compute_queue.py enrich --task eval --doc-ids 1,2,3
  python hfo_p7_compute_queue.py search "GPU NPU utilization"
""",
    )
    parser.add_argument("spell",
                        choices=["status", "embed-all", "enrich", "search"],
                        help="Spell variant")
    parser.add_argument("query", nargs="?", default=None,
                        help="Search query (for search spell)")
    parser.add_argument("--task", default="summarize",
                        choices=["summarize", "classify", "eval"],
                        help="Enrichment task type")
    parser.add_argument("--model", default="", help="Override LLM model")
    parser.add_argument("--limit", type=int, default=5, help="Max docs to process")
    parser.add_argument("--batch-size", type=int, default=100, help="NPU batch size")
    parser.add_argument("--doc-ids", default="", help="Comma-separated doc IDs")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    _print_banner()

    if args.spell == "status":
        result = spell_status()
    elif args.spell == "embed-all":
        result = asyncio.run(spell_embed_all(batch_size=args.batch_size))
    elif args.spell == "enrich":
        doc_ids = [int(x) for x in args.doc_ids.split(",") if x.strip()] if args.doc_ids else None
        result = asyncio.run(spell_enrich(
            doc_ids=doc_ids, task=args.task,
            model=args.model, limit=args.limit,
        ))
    elif args.spell == "search":
        if not args.query:
            print("  ERROR: search requires a query argument")
            return
        # Quick inline search
        try:
            from hfo_npu_embedder import search_similar_to_text, get_embedding_stats, ensure_embeddings_table
            conn = get_db_rw()
            ensure_embeddings_table(conn)
            stats = get_embedding_stats(conn)
            conn.close()
            if stats["total_embedded"] == 0:
                print("  No embeddings yet. Run: python hfo_p7_compute_queue.py embed-all")
                result = {"error": "no embeddings"}
            else:
                results = search_similar_to_text(args.query, top_k=10)
                print(f"  Top results for: '{args.query}' ({stats['total_embedded']} docs indexed)\n")
                for r in results:
                    port = r.get('port') or '?'
                    title = (r.get('title') or '?')[:60]
                    print(f"  [{r['score']:.4f}] doc {r['doc_id']:5d} | {port:3s} | {title}")
                    bluf = r.get("bluf") or ""
                    if bluf and bluf != "---":
                        print(f"           {bluf[:100]}")
                result = {"query": args.query, "results": results}
        except Exception as e:
            print(f"  ERROR: {e}")
            result = {"error": str(e)}
    else:
        result = {"error": "Unknown spell"}

    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
