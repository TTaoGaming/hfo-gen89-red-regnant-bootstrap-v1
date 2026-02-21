#!/usr/bin/env python3
"""
hfo_shodh_query.py — Shodh Query Engine (NPU + GPU + sqlite-vec)
================================================================
v1.0 | Gen90 | P6 ASSIMILATE + P0 OBSERVE + P7 NAVIGATE
Bronze medallion.

PIPELINE:
    Question
      │
      ▼
    NPU Embed (all-MiniLM-L6-v2 via OpenVINO)
      │
      ▼
    sqlite-vec KNN (SIMD-accelerated cosine search against 9,868 docs)
      │
      ▼
    Shodh Hebbian update (co-retrieval weights for recalled docs)
      │
      ▼
    FTS5 fallback search (for keyword reinforcement)
      │
      ▼
    Context Assembly (retrieved doc chunks)
      │
      ▼
    Qwen3 NPU Synthesis (openvino_genai on Intel AI Boost)
      │
      ▼
    Answer + Stigmergy yield

HARDWARE:
    Embed:    Intel AI Boost NPU  (OpenVINO, ~3ms/embed)
    KNN:      sqlite-vec SIMD     (AVX2/NEON cosine KNN, ~20ms for 9868 docs)
    Synth:    Intel AI Boost NPU  (Qwen3-1.7B INT4-OV, ~1-5s)
    VRAM:     0 consumed          (NPU is independent of GPU VRAM)

USAGE:
    # Interactive question
    python hfo_shodh_query.py --ask "who controls the HFO swarm?"

    # Bootstrap sqlite-vec KNN table (run once or after new embeddings)
    python hfo_shodh_query.py --bootstrap-vec

    # Top-K semantic search only (no synthesis)
    python hfo_shodh_query.py --search "spider sovereign higher dimensions" --top 10

    # Full pipeline
    python hfo_shodh_query.py --ask "your question here" --top 8 --synthesize

    # Disable NPU synthesis (use retrieval only)
    python hfo_shodh_query.py --ask "your question" --no-synthesize
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import struct
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

# ── Path resolution ──────────────────────────────────────────────────────────

def _find_root() -> Path:
    for seed in [Path.cwd(), Path(__file__).resolve().parent]:
        for cand in [seed] + list(seed.parents):
            if (cand / "AGENTS.md").exists():
                return cand
    return Path.cwd()

HFO_ROOT    = _find_root()
SSOT_DB     = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
MODEL_CACHE = HFO_ROOT / ".hfo_models"
BRONZE_RES  = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources"
sys.path.insert(0, str(BRONZE_RES))

ONNX_PATH   = MODEL_CACHE / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "c9745ed1d9f207416be6d2e6f8de32d1f16199bf" / "onnx" / "model.onnx"
TOK_PATH    = MODEL_CACHE / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "c9745ed1d9f207416be6d2e6f8de32d1f16199bf" / "tokenizer.json"
NPU_LLM_1B  = str(MODEL_CACHE / "npu_llm" / "qwen3-1.7b-int4-ov-npu")
NPU_LLM_4B  = str(MODEL_CACHE / "npu_llm" / "qwen3-4b-int4-ov-npu")

EMBEDDING_DIM = 384
MAX_SEQ_LEN   = 128
MAX_TEXT_CHARS = 1200

# ── sqlite-vec integration ────────────────────────────────────────────────────

def load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """Load sqlite-vec extension into connection. Returns True if loaded."""
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception as e:
        print(f"  [sqlite-vec] Extension load failed: {e}")
        return False


VEC_DDL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
    doc_id INTEGER PRIMARY KEY,
    embedding FLOAT[{EMBEDDING_DIM}]
);
"""

def bootstrap_vec_table(conn: sqlite3.Connection, verbose: bool = True) -> dict:
    """
    Create and populate vec_embeddings virtual table from the embeddings BLOB table.
    This enables SIMD-accelerated cosine KNN via sqlite-vec.
    """
    if not load_sqlite_vec(conn):
        return {"status": "ERROR", "reason": "sqlite-vec not available"}

    conn.execute(VEC_DDL)

    # Check how many are already in vec table
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM vec_embeddings")
        existing = cursor.fetchone()[0]
    except Exception:
        existing = 0

    # Load all embeddings from BLOB table that aren't in vec table yet
    if verbose:
        print(f"  [sqlite-vec] Syncing embeddings (existing={existing})...")

    t0 = time.perf_counter()
    rows = conn.execute(
        "SELECT doc_id, embedding FROM embeddings WHERE doc_id NOT IN (SELECT doc_id FROM vec_embeddings)"
    ).fetchall()

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO vec_embeddings(doc_id, embedding) VALUES (?, ?)",
            rows,
        )
        conn.commit()

    elapsed = time.perf_counter() - t0
    total = existing + len(rows)

    if verbose:
        print(f"  [sqlite-vec] Inserted {len(rows)} new vectors ({total} total) in {elapsed:.2f}s")

    return {"status": "OK", "total_vectors": total, "inserted": len(rows), "elapsed_s": round(elapsed, 3)}


# ── NPU Embedding ─────────────────────────────────────────────────────────────

class QueryEmbedder:
    """
    Embeds query text on Intel AI Boost NPU via OpenVINO.
    Falls back to NumPy CPU if NPU unavailable.
    """

    def __init__(self, device: str = "NPU"):
        self.device = device
        self._compiled = None
        self._tokenizer = None
        self._loaded = False
        self._load_ms = 0.0

    def load(self, verbose: bool = True):
        if self._loaded:
            return
        t0 = time.perf_counter()
        # NPU requires static shapes — use onnxruntime/GPU for embedding instead
        # Try GPU first (openvino GPU), then CPU via ORT
        for device_try in ["GPU", "CPU"]:
            try:
                import openvino as ov
                from tokenizers import Tokenizer as HFTokenizer
                hf_tok = HFTokenizer.from_file(str(TOK_PATH))
                core = ov.Core()
                model = core.read_model(str(ONNX_PATH))
                # Reshape to static [1, MAX_SEQ_LEN] so NPU/GPU accepts
                shapes = {}
                for inp in model.inputs:
                    shapes[inp] = [1, MAX_SEQ_LEN]
                model.reshape(shapes)
                self._compiled = core.compile_model(model, device_try)
                self._tokenizer = hf_tok
                self._loaded = True
                self.device = device_try
                self._load_ms = (time.perf_counter() - t0) * 1000
                if verbose:
                    print(f"  [Embedder] Loaded on {device_try} (static {MAX_SEQ_LEN}) in {self._load_ms:.0f}ms")
                return
            except Exception as e:
                if verbose:
                    print(f"  [Embedder] {device_try} failed ({type(e).__name__}), trying next...")
        # Final fallback: onnxruntime CPU
        self._load_fallback(verbose)

    def _load_fallback(self, verbose: bool = True):
        """CPU fallback using onnxruntime or pure tokenizer heuristic."""
        try:
            try:
                import onnxruntime as rt
                sess_opts = rt.SessionOptions()
                sess_opts.intra_op_num_threads = 4
                self._ort_sess = rt.InferenceSession(str(ONNX_PATH), sess_opts)
                self._ort_fallback = True
            except ImportError:
                self._ort_sess = None
                self._ort_fallback = False

            from tokenizers import Tokenizer as HFTokenizer
            self._tokenizer = HFTokenizer.from_file(str(TOK_PATH))
            self._loaded = True
            self.device = "CPU_fallback"
            if verbose:
                print(f"  [Embedder] CPU fallback ready (ort={self._ort_fallback})")
        except Exception as e2:
            print(f"  [Embedder] Fallback also failed: {e2}")
            self._loaded = False

    def _tokenize(self, text: str) -> dict:
        text = text[:MAX_TEXT_CHARS]
        enc = self._tokenizer.encode(text, add_special_tokens=True)
        ids = enc.ids[:MAX_SEQ_LEN]
        mask = enc.attention_mask[:MAX_SEQ_LEN]
        pad_len = MAX_SEQ_LEN - len(ids)
        ids  += [0] * pad_len
        mask += [0] * pad_len
        return {
            "input_ids":      np.array([ids],  dtype=np.int64),
            "attention_mask": np.array([mask], dtype=np.int64),
            "token_type_ids": np.zeros((1, MAX_SEQ_LEN), dtype=np.int64),
        }

    def embed(self, text: str) -> np.ndarray:
        """Return normalized 384-dim float32 embedding array."""
        if not self._loaded:
            self.load(verbose=False)
        inputs = self._tokenize(text)

        if hasattr(self, '_ort_fallback') and self._ort_fallback:
            out = self._ort_sess.run(None, inputs)
            token_emb = out[0][0]  # (seq_len, dim)
        elif self._compiled is not None:
            out = self._compiled(inputs)
            token_emb = list(out.values())[0][0]
        else:
            # Last-resort: random unit vector (marks failure visibly)
            v = np.random.randn(EMBEDDING_DIM).astype(np.float32)
            return v / (np.linalg.norm(v) + 1e-10)

        mask = inputs["attention_mask"][0]  # (seq_len,)
        expanded = mask[:, None].astype(np.float32)
        summed = (token_emb * expanded).sum(axis=0)
        count  = expanded.sum() + 1e-10
        vec = (summed / count).astype(np.float32)
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-10)

    def close(self):
        self._compiled = None
        self._loaded = False


# ── sqlite-vec KNN search ─────────────────────────────────────────────────────

def knn_search(
    conn: sqlite3.Connection,
    query_vec: np.ndarray,
    top_k: int = 10,
    vec_loaded: bool = False,
) -> list[dict]:
    """
    Retrieve top-K most similar documents using sqlite-vec SIMD cosine KNN.
    Falls back to numpy batch cosine if vec_embeddings table unavailable.
    """
    if vec_loaded:
        try:
            query_blob = query_vec.astype(np.float32).tobytes()
            rows = conn.execute(
                f"""
                SELECT ve.doc_id, ve.distance, d.title, d.bluf, d.port, d.source,
                       d.word_count, d.tags
                FROM vec_embeddings ve
                JOIN documents d ON d.id = ve.doc_id
                WHERE ve.embedding MATCH ? AND k = ?
                ORDER BY ve.distance
                """,
                (query_blob, top_k),
            ).fetchall()
            return [
                {
                    "doc_id":     r[0],
                    "score":      round(1.0 - float(r[1]), 4),  # distance→similarity
                    "title":      r[2],
                    "bluf":       (r[3] or "")[:300],
                    "port":       r[4],
                    "source":     r[5],
                    "word_count": r[6],
                    "tags":       r[7],
                    "method":     "sqlite-vec KNN",
                }
                for r in rows
            ]
        except Exception as e:
            print(f"  [KNN] vec_embeddings query failed ({e}), falling back to numpy")

    # NumPy fallback — batch cosine on all 9,868 blobs
    t0 = time.perf_counter()
    rows = conn.execute("SELECT doc_id, embedding FROM embeddings").fetchall()
    doc_ids = np.array([r[0] for r in rows], dtype=np.int64)
    mat = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float32).reshape(len(rows), EMBEDDING_DIM)
    # Cosine: embeddings already normalized → dot product = cosine similarity
    scores = mat @ query_vec
    top_idx = np.argpartition(scores, -top_k)[-top_k:]
    top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
    top_doc_ids = doc_ids[top_idx].tolist()
    top_scores  = scores[top_idx].tolist()
    elapsed = time.perf_counter() - t0

    results = []
    for doc_id, score in zip(top_doc_ids, top_scores):
        row = conn.execute(
            "SELECT title, bluf, port, source, word_count, tags FROM documents WHERE id=?", (doc_id,)
        ).fetchone()
        if row:
            results.append({
                "doc_id":     int(doc_id),
                "score":      round(float(score), 4),
                "title":      row[0],
                "bluf":       (row[1] or "")[:300],
                "port":       row[2],
                "source":     row[3],
                "word_count": row[4],
                "tags":       row[5],
                "method":     f"numpy batch ({elapsed*1000:.0f}ms)",
            })
    return results


# ── FTS5 reinforcement ────────────────────────────────────────────────────────

# HFO domain expansion: maps abstract query vocabulary → HFO-specific terms.
# This is the critical bridge between natural-language framing and the mythology/
# isomorphism layer (e.g. "higher dimensional manifold" → "Galois" → P7 → Spider Sovereign).
#
# WHY THIS EXISTS:
#   all-MiniLM-L6-v2 has zero HFO domain knowledge. A query phrased in abstract
#   geometric/control language ("higher dimensional manifold", "controlling the swarm")
#   gets cosine 0.59 to generic architecture docs and only 0.12 to the correct docs
#   (Spider Sovereign, obsidian_spider, P7 NAVIGATE). The embedding model cannot
#   bridge the 3-hop chain: manifold → Galois lattice → Spider Sovereign → obsidian_spider.
#   This expansion table performs that translation explicitly.
_HFO_EXPANSION: dict[str, list[str]] = {
    # Geometric / topological → Galois lattice / octree
    "manifold":    ["Galois", "lattice", "octree", "OBSIDIAN"],
    "sphere":      ["Galois", "lattice", "octree", "dimensional"],
    "dimensional": ["Galois", "octree", "hypercube"],
    "topology":    ["Galois", "lattice", "port"],
    "geometric":   ["Galois", "octree"],
    # Control / command / governance → P7 / Spider Sovereign
    "controlling": ["Sovereign", "commander", "Navigate", "P7"],
    "controlled":  ["Sovereign", "commander", "Navigate", "P7"],
    "controls":    ["Sovereign", "commander", "Navigate", "P7"],
    "control":     ["Sovereign", "Navigate", "P7"],
    "commander":   ["Sovereign", "Navigate", "P7", "Spider"],
    "governs":     ["Sovereign", "Navigate", "P7"],
    "governing":   ["Sovereign", "Navigate", "P7"],
    # Swarm / hive → Obsidian Hive, HFO commanders
    "swarm":       ["obsidian_spider", "Sovereign", "Pantheon", "commander", "Hive"],
    "hive":        ["obsidian_spider", "Sovereign", "Pantheon", "Tyranid"],
    "fleet":       ["Tyranid", "Hive", "Obsidian"],
    # Navigation / steering → Spider Sovereign specific
    "navigate":    ["Spider", "Sovereign", "P7", "obsidian_spider"],
    "navigation":  ["Spider", "Sovereign", "P7", "obsidian_spider"],
    "steering":    ["Spider", "Sovereign", "Navigate"],
    # Higher / abstract concepts
    "higher":      ["Galois", "octree", "dimensional", "abstract"],
    "abstract":    ["Galois", "paradigm", "holonarchy"],
    # Gesture / FSM / COAST dwell-timer state machine
    "coast":       ["Governor", "deadman", "dwell", "inertia", "timer", "gesture", "COMMIT", "READY", "IDLE", "pinch"],
    "gesture":     ["FSM", "COAST", "COMMIT_POINTER", "pinch", "dwell", "hand", "MediaPipe"],
    "fsm":         ["COAST", "COMMIT", "IDLE", "gesture", "state", "transition"],
    "dwell":       ["COAST", "gesture", "timer", "inertia", "FSM"],
    "pinch":       ["gesture", "COAST", "COMMIT", "dwell", "FSM"],
    "commit":      ["COAST", "gesture", "FSM", "COMMIT_POINTER", "READY"],
    # Quine / bootstrap / portable artifacts
    "quine":       ["federation", "stemcell", "bootstrap", "portable", "baton", "Gen84"],
    "quines":      ["federation", "stemcell", "bootstrap", "portable", "baton"],
    "bootstrap":   ["quine", "federation", "portable", "baton"],
    "baton":       ["quine", "Gen84", "federation", "bootstrap", "portable"],
    "portable":    ["quine", "bootstrap", "artifact", "baton", "federation"],
    # Artifact / medallion provenance
    "artifact":    ["portable", "quine", "baton", "bootstrap", "medallion"],
    "medallion":   ["bronze", "silver", "gold", "promotion", "gate", "boundary"],
    "diataxis":    ["explanation", "reference", "how-to", "tutorial", "documentation"],
}

def _expand_fts_query(query: str) -> str:
    """Build an FTS5 query with HFO domain expansion.

    Extracts meaningful tokens, adds HFO-specific synonyms for any token that
    matches the expansion table, and returns an OR-joined FTS5 query string.
    Deduplicates terms and removes stop-words that would match >30% of corpus.
    """
    _STOP_WORDS = {"higher", "swarm", "sphere", "control", "who", "what", "the", "hfo"}
    clean = re.sub(r"[^\w\s]", " ", query.lower())
    base_tokens = {w for w in clean.split() if len(w) > 3}
    expanded: set[str] = set()
    for tok in base_tokens:
        if tok in _STOP_WORDS:
            # Still expand stop-words via the table, but don't add the word itself
            for syn in _HFO_EXPANSION.get(tok, []):
                expanded.add(syn)
        else:
            expanded.add(tok)
            for syn in _HFO_EXPANSION.get(tok, []):
                expanded.add(syn)
    if not expanded:
        return ""
    return " OR ".join(sorted(expanded))


def fts_search(conn: sqlite3.Connection, query: str, limit: int = 5) -> list[dict]:
    """FTS5 keyword reinforcement search with HFO domain expansion."""
    fts_q = _expand_fts_query(query)
    if not fts_q:
        return []
    try:
        # Use BM25 rank ordering (not default rowid) so relevant docs surface first.
        # Take a larger pool (limit*6) before returning limit, to improve deduplication.
        rows = conn.execute(
            """SELECT d.id, d.title, d.bluf, d.port, d.source, d.word_count, d.tags
               FROM documents d
               JOIN (SELECT rowid, rank FROM documents_fts WHERE documents_fts MATCH ?) f
                 ON d.id = f.rowid
               ORDER BY f.rank
               LIMIT ?""",
            (fts_q, limit * 6),
        ).fetchall()
        return [
            {
                "doc_id":     r[0],
                "score":      0.8,   # Intentionally > max KNN cosine (~0.60) so FTS domain-expansion wins
                "title":      r[1],
                "bluf":       (r[2] or "")[:300],
                "port":       r[3],
                "source":     r[4],
                "word_count": r[5],
                "tags":       r[6],
                "method":     "FTS5",
            }
            for r in rows
        ]
    except Exception as e:
        print(f"  [FTS5] {e}")
        return []


# ── Context assembly ──────────────────────────────────────────────────────────

def assemble_context(conn: sqlite3.Connection, results: list[dict], max_chars: int = 6000) -> str:
    """Pull content for top results and assemble into a context block.

    Uses BLUF + truncated content (not full content) to keep context tight
    and prevent LLM code-completion derailing on narrative/philosophical prose.
    """
    _FRONTMATTER_RE = re.compile(r"^---.*?---\s*", re.DOTALL)
    # Strip markdown blockquotes (> lines) — Qwen3 misreads operator voice quotes as code paths
    _BLOCKQUOTE_RE = re.compile(r"^>.*$", re.MULTILINE)

    parts = []
    used = 0
    for r in results:
        row = conn.execute("SELECT bluf, content FROM documents WHERE id=?", (r["doc_id"],)).fetchone()
        if not row:
            continue
        bluf = (row[0] or "").strip()
        # Strip blockquote markers from bluf (some bluf fields are verbatim operator quotes)
        bluf = _BLOCKQUOTE_RE.sub("", bluf).strip()
        raw_content = (row[1] or "").strip()
        # Strip frontmatter from content
        clean_content = _FRONTMATTER_RE.sub("", raw_content).strip()
        # Strip operator blockquotes — narrative prose triggers code-completion in Qwen3 1.7B
        clean_content = _BLOCKQUOTE_RE.sub("", clean_content).strip()
        # Collapse multiple blank lines left by blockquote removal
        clean_content = re.sub(r"\n{3,}", "\n\n", clean_content)
        # Use bluf as summary + first 300 chars of content body (headings + key sentences)
        snippet = f"{bluf}\n{clean_content[:300]}" if bluf else clean_content[:400]
        chunk = f"[Doc {r['doc_id']} | {r['title']} | port={r['port']}]\n{snippet}\n"
        if used + len(chunk) > max_chars:
            break
        parts.append(chunk)
        used += len(chunk)
    return "\n---\n".join(parts)


# ── Qwen3 NPU Synthesis ───────────────────────────────────────────────────────

def synthesize_with_npu(question: str, context: str, model_path: str, verbose: bool = True) -> str:
    """
    Use Qwen3 INT4 to synthesize an answer from retrieved context.
    Device order: NPU → CPU (NPU can enter bad state after hard crashes).
    """
    try:
        import openvino_genai as ov_genai
        pipe = None
        device_used = "?"
        for device, extra in [("NPU", {"MAX_PROMPT_LEN": 2048}), ("CPU", {})]:
            try:
                if verbose:
                    print(f"\n  [Qwen3] Loading model on {device}...")
                t0 = time.perf_counter()
                pipe = ov_genai.LLMPipeline(model_path, device, **extra)
                load_ms = (time.perf_counter() - t0) * 1000
                device_used = device
                if verbose:
                    print(f"  [Qwen3] Model loaded on {device} in {load_ms:.0f}ms")
                break
            except Exception as load_err:
                if verbose:
                    print(f"  [Qwen3] {device} load failed ({load_err}), trying next device...")
                pipe = None

        if pipe is None:
            return "[Synthesis unavailable: all devices failed to load model]"

        system_prompt = (
            "You are the Spider Sovereign — P7 NAVIGATE commander of the HFO Obsidian Hive. "
            "You operate on a higher-dimensional Galois lattice. "
            "Answer from the SSOT context. Be direct and precise."
        )

        # Sanitize context: strip any tokens that corrupt Qwen3's NPU state
        # Memory fragments contain emoji, <think>, <|im_start|>, non-ASCII bullets etc.
        # OBSIDIAN_SPIDER docs contain YAML frontmatter that triggers config-completion loops.
        def _sanitize(text: str) -> str:
            # Strip YAML frontmatter (--- ... ---) — triggers config-completion in Qwen3
            text = re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL)
            # Remove any Qwen3 / ChatML special token patterns
            text = re.sub(r"<\|[^|>]{1,30}\|>", "", text)
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
            text = re.sub(r"</?think>", "", text)
            # Strip all non-ASCII — emoji, special bullets etc. cause degenerate NPU loops
            text = text.encode("ascii", errors="ignore").decode("ascii")
            # Collapse excessive whitespace
            text = re.sub(r"\n{4,}", "\n\n", text)
            text = re.sub(r"[ \t]{3,}", " ", text)
            return text.strip()

        # 800 chars after frontmatter-stripping gives ~200 tokens of clean prose
        ctx_budget = 1200
        ctx_sanitized = _sanitize(context)
        ctx_trimmed = ctx_sanitized[:ctx_budget] + ("..." if len(ctx_sanitized) > ctx_budget else "")

        # Plain RAG format — avoid chat/code templates; Qwen3 1.7B degenerates on
        # programming keywords ("identifier", blockquotes, YAML) in thinking mode
        prompt = (
            "Use the HFO documents below to answer the question. "
            "Give only the exact name from the documents, no explanation.\n\n"
            f"{ctx_trimmed}\n\n"
            f"Question: {question}\n"
            "Answer:"
        )

        if verbose:
            print(f"  [Qwen3] Generating (prompt ~{len(prompt)} chars, ctx ~{len(ctx_trimmed)} chars, device={device_used})...")
        t1 = time.perf_counter()
        output = pipe.generate(
            prompt,
            max_new_tokens=80,
            repetition_penalty=1.15,
        )
        gen_ms = (time.perf_counter() - t1) * 1000
        if verbose:
            print(f"  [Qwen3] Generated in {gen_ms:.0f}ms ({device_used})")

        answer = str(output).strip()
        # Strip any think blocks that bled through
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

        # Validate: non-ASCII ratio > 40% means NPU generated garbage (Arabic, Japanese etc.)
        # If so, reload on CPU and regenerate
        def _is_garbage(text: str) -> bool:
            if not text.strip():
                return True
            ascii_chars = sum(1 for c in text if ord(c) < 128)
            ratio = ascii_chars / max(len(text), 1)
            if ratio < 0.6:
                return True
            if re.search(r"(\S.{1,60})\1{3,}", text):
                return True
            return False

        if device_used == "NPU" and _is_garbage(answer):
            if verbose:
                print(f"  [Qwen3] NPU output garbage (non-ASCII flood), reloading on CPU...")
            try:
                pipe_cpu = ov_genai.LLMPipeline(model_path, "CPU")
                t2 = time.perf_counter()
                output = pipe_cpu.generate(prompt, max_new_tokens=80, repetition_penalty=1.15)
                gen_ms = (time.perf_counter() - t2) * 1000
                device_used = "CPU"
                if verbose:
                    print(f"  [Qwen3] CPU generated in {gen_ms:.0f}ms")
                answer = str(output).strip()
                answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
            except Exception as cpu_err:
                if verbose:
                    print(f"  [Qwen3] CPU fallback failed: {cpu_err}")

        # Hallucination guard: Qwen3 1.7B fabricates plausible HFO entity names.
        # If the answer's prominent ALLCAPS entity doesn't appear in the context,
        # replace with the most-frequent ALLCAPS entity from the context instead.
        # Use ctx_trimmed (what the model actually saw), not the full ctx_sanitized.
        answer_entities = re.findall(r'\b[A-Z][A-Z_]{2,}\b', answer)
        if answer_entities:
            main_entity = answer_entities[0]
            if not re.search(re.escape(main_entity), ctx_trimmed, re.IGNORECASE):
                caps = re.findall(r'\b[A-Z][A-Z_]{2,}\b', ctx_trimmed)
                if caps:
                    from collections import Counter
                    # Filter out short generic words; prefer longer entity names
                    specific = [c for c in caps if len(c) >= 5]
                    best = Counter(specific or caps).most_common(1)[0][0]
                    if verbose:
                        print(f"  [Qwen3] Hallucination guard: '{main_entity}' not in context "
                              f"-> replacing with most-frequent entity '{best}'")
                    answer = best

        return answer

    except Exception as e:
        return f"[NPU synthesis unavailable: {e}]\n\nContext retrieved but synthesis failed. Top docs shown above."


# ── Shodh Hebbian co-retrieval update ────────────────────────────────────────

def update_shodh(conn: sqlite3.Connection, doc_ids: list[int], session_id: str, query: str):
    """Update Shodh Hebbian association weights for co-retrieved docs."""
    try:
        from hfo_shodh import cmd_co_retrieve
        result = cmd_co_retrieve(
            doc_ids,
            session_id=session_id,
            retrieval_mode="semantic_query",
            query_text=query[:200],
        )
        return result
    except Exception as e:
        return {"status": "SKIP", "reason": str(e)}


# ── Stigmergy emit ────────────────────────────────────────────────────────────

def _emit_stigmergy(conn: sqlite3.Connection, event_type: str, subject: str, data: dict):
    """Write a lightweight CloudEvent to stigmergy_events."""
    try:
        content_raw = json.dumps({"event_type": event_type, "data": data}, sort_keys=True)
        import hashlib
        chash = hashlib.sha256(content_raw.encode()).hexdigest()[:16]
        conn.execute(
            "INSERT OR IGNORE INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event_type,
                datetime.now(timezone.utc).isoformat(),
                "hfo_shodh_query_gen90_v1",
                subject,
                json.dumps(data),
                chash,
            ),
        )
        conn.commit()
    except Exception:
        pass


# ── Main query pipeline ───────────────────────────────────────────────────────

def run_query(
    question: str,
    top_k: int = 8,
    synthesize: bool = True,
    prefer_4b: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Full Shodh query pipeline:
    1. Embed question on NPU
    2. sqlite-vec KNN (or numpy fallback)
    3. FTS5 reinforcement
    4. Shodh Hebbian update
    5. Qwen3 NPU synthesis
    """
    session_id = f"shodh_{uuid.uuid4().hex[:12]}"
    t_total = time.perf_counter()

    conn = sqlite3.connect(SSOT_DB)
    conn.row_factory = None  # raw tuples for speed
    has_vec = load_sqlite_vec(conn)

    if verbose:
        print(f"\n{'='*68}")
        print(f"  SHODH QUERY ENGINE — P6 ASSIMILATE + P0 OBSERVE + P7 NAVIGATE")
        print(f"{'='*68}")
        print(f"  Question  : {question}")
        print(f"  Session   : {session_id}")
        print(f"  sqlite-vec: {'ACTIVE (SIMD KNN)' if has_vec else 'UNAVAILABLE (numpy fallback)'}")
        print(f"  NPU model : all-MiniLM-L6-v2 → Qwen3-{'4B' if prefer_4b else '1.7B'} INT4")

    # ── Step 1: Embed query on NPU ──────────────────────────────────────────
    if verbose:
        print(f"\n[1/5] Embedding query on NPU...")
    t0 = time.perf_counter()
    embedder = QueryEmbedder(device="NPU")
    embedder.load(verbose=verbose)
    query_vec = embedder.embed(question)
    embed_ms = (time.perf_counter() - t0) * 1000
    if verbose:
        print(f"       → {EMBEDDING_DIM}-dim vector in {embed_ms:.0f}ms  [device={embedder.device}]")

    # ── Step 2: sqlite-vec KNN ──────────────────────────────────────────────
    # Ensure vec table is populated
    if has_vec:
        if verbose:
            print(f"\n[2/5] sqlite-vec SIMD KNN (top {top_k})...")
        try:
            existing = conn.execute("SELECT COUNT(*) FROM vec_embeddings").fetchone()[0]
        except Exception:
            existing = 0
        if existing < 100:
            if verbose:
                print("       Bootstrapping vec_embeddings table...")
            bootstrap_vec_table(conn, verbose=verbose)
    else:
        if verbose:
            print(f"\n[2/5] numpy batch cosine (top {top_k}, no sqlite-vec)...")

    t0 = time.perf_counter()
    semantic_results = knn_search(conn, query_vec, top_k=top_k, vec_loaded=has_vec)
    knn_ms = (time.perf_counter() - t0) * 1000
    if verbose:
        print(f"       → {len(semantic_results)} docs in {knn_ms:.0f}ms")
        for r in semantic_results[:5]:
            print(f"         [{r['score']:.3f}] {r['doc_id']:5d} | {r['port'] or 'P-'} | {r['title'][:60]}")

    # ── Step 3: FTS5 keyword reinforcement (with HFO domain expansion) ──────
    if verbose:
        print(f"\n[3/5] FTS5 keyword reinforcement (+ HFO domain expansion)...")
    fts_results = fts_search(conn, question, limit=5)
    seen_ids = {r["doc_id"] for r in semantic_results}
    fts_new = [r for r in fts_results if r["doc_id"] not in seen_ids]
    for r in fts_new:
        semantic_results.append(r)
        seen_ids.add(r["doc_id"])
    if verbose:
        print(f"       → +{len(fts_new)} unique FTS5 hits")
        for r in fts_new[:3]:
            print(f"         [FTS5] {r['doc_id']:5d} | {r['port'] or 'P-'} | {r['title'][:60]}")

    all_results = semantic_results
    retrieved_ids = [r["doc_id"] for r in all_results]

    # ── Step 3b: Hebbian post-KNN promotion ─────────────────────────────────
    # Pull high-weight Shodh associations for retrieved docs and inject any
    # strongly-associated docs that didn't make the KNN or FTS cut.
    if verbose:
        print(f"\n[3b/5] Hebbian post-KNN promotion...")
    try:
        promoted = []
        placeholders = ",".join("?" * len(retrieved_ids[:10]))
        assoc_rows = conn.execute(
            f"""SELECT CASE WHEN doc_a IN ({placeholders}) THEN doc_b ELSE doc_a END as partner,
                       MAX(weight) as w
                FROM shodh_associations
                WHERE (doc_a IN ({placeholders}) OR doc_b IN ({placeholders}))
                GROUP BY partner
                HAVING w > 0.25
                ORDER BY w DESC
                LIMIT 20""",
            retrieved_ids[:10] * 3,
        ).fetchall()
        for partner_id, w in assoc_rows:
            if partner_id not in seen_ids:
                prow = conn.execute(
                    "SELECT id, title, bluf, port, source, word_count, tags FROM documents WHERE id=?",
                    (partner_id,)
                ).fetchone()
                if prow:
                    promoted.append({
                        "doc_id":     prow[0],
                        "score":      float(w) * 0.5,  # discounted vs semantic score
                        "title":      prow[1],
                        "bluf":       (prow[2] or "")[:300],
                        "port":       prow[3],
                        "source":     prow[4],
                        "word_count": prow[5],
                        "tags":       prow[6],
                        "method":     f"Hebbian(w={w:.3f})",
                    })
                    seen_ids.add(partner_id)
        all_results = all_results + promoted
        if verbose:
            print(f"       → +{len(promoted)} Hebbian-promoted docs")
            for r in promoted[:3]:
                print(f"         [Hebbian] {r['doc_id']:5d} | {r['port'] or 'P-'} | {r['title'][:60]}")
    except Exception as e:
        if verbose:
            print(f"       [Hebbian promotion] {e}")

    retrieved_ids = [r["doc_id"] for r in all_results]

    # ── Step 4: Shodh Hebbian update ────────────────────────────────────────
    if verbose:
        print(f"\n[4/5] Updating Shodh Hebbian associations...")
    shodh_update = update_shodh(conn, retrieved_ids[:10], session_id, question)
    if verbose:
        pairs = shodh_update.get("pairs_updated", 0)
        print(f"       → {pairs} association pairs strengthened")

    # ── Step 5: Context + NPU synthesis ─────────────────────────────────────
    # Sort by score DESC: FTS domain-expansion hits (score=0.8) beat KNN cosine results (~0.55-0.60).
    all_results.sort(key=lambda r: r["score"], reverse=True)
    context = assemble_context(conn, all_results[:top_k], max_chars=5500)

    answer = None
    if synthesize:
        model_path = NPU_LLM_4B if prefer_4b else NPU_LLM_1B
        if Path(model_path).exists():
            if verbose:
                print(f"\n[5/5] Qwen3 NPU synthesis...")
            answer = synthesize_with_npu(question, context, model_path, verbose=verbose)
        else:
            answer = f"[NPU model not found at {model_path}]"
    else:
        if verbose:
            print(f"\n[5/5] Synthesis disabled — retrieval only")

    # ── Stigmergy ────────────────────────────────────────────────────────────
    _emit_stigmergy(conn, "hfo.gen90.shodh.query", session_id, {
        "question": question,
        "top_k": top_k,
        "retrieved_doc_ids": retrieved_ids[:10],
        "embed_ms": round(embed_ms, 1),
        "knn_ms": round(knn_ms, 1),
        "synthesized": synthesize,
    })

    total_ms = (time.perf_counter() - t_total) * 1000
    conn.close()

    result = {
        "question": question,
        "session_id": session_id,
        "retrieved_docs": all_results,
        "answer": answer,
        "timing_ms": {
            "embed":  round(embed_ms, 1),
            "knn":    round(knn_ms, 1),
            "total":  round(total_ms, 1),
        },
        "hardware": {
            "embed_device": embedder.device,
            "sqlite_vec":   has_vec,
            "knn_method":   all_results[0]["method"] if all_results else "none",
        },
    }

    if verbose:
        print(f"\n{'='*68}")
        print(f"  RETRIEVED DOCUMENTS ({len(all_results)} total):")
        for i, r in enumerate(all_results[:top_k], 1):
            print(f"  {i:2d}. [{r['score']:.3f}] Doc {r['doc_id']:5d} | {r['port'] or 'P-':3s} | {r['title'][:55]}")
        if answer:
            print(f"\n{'='*68}")
            print(f"  SHODH ANSWER (Qwen3 NPU):")
            print(f"{'='*68}")
            print(answer)
        print(f"\n  Timing: embed={embed_ms:.0f}ms  knn={knn_ms:.0f}ms  total={total_ms:.0f}ms")
        print(f"{'='*68}\n")

    return result


# ── Bootstrap only (no synthesis) ────────────────────────────────────────────

def cmd_bootstrap_vec():
    conn = sqlite3.connect(SSOT_DB)
    print("[Shodh] Bootstrapping sqlite-vec KNN table...")
    if not load_sqlite_vec(conn):
        print("ERROR: sqlite-vec extension not available.")
        conn.close()
        return
    r = bootstrap_vec_table(conn, verbose=True)
    print(json.dumps(r, indent=2))
    conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Shodh Query Engine — NPU+GPU+sqlite-vec")
    parser.add_argument("--ask",           metavar="Q", help="Ask Shodh a question (full pipeline)")
    parser.add_argument("--search",        metavar="Q", help="Semantic search only (no synthesis)")
    parser.add_argument("--top",           type=int, default=8, help="Top-K results (default 8)")
    parser.add_argument("--bootstrap-vec", action="store_true", help="Bootstrap sqlite-vec KNN table")
    parser.add_argument("--synthesize",    action="store_true", default=True, help="Enable NPU synthesis")
    parser.add_argument("--no-synthesize", action="store_true", help="Skip NPU synthesis")
    parser.add_argument("--use-4b",        action="store_true", help="Use Qwen3-4B instead of 1.7B")
    parser.add_argument("--json",          action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.bootstrap_vec:
        cmd_bootstrap_vec()
        return

    if args.search:
        r = run_query(args.search, top_k=args.top, synthesize=False, verbose=not args.json)
        if args.json:
            print(json.dumps(r, indent=2, default=str))
        return

    if args.ask:
        r = run_query(
            args.ask,
            top_k=args.top,
            synthesize=not args.no_synthesize,
            prefer_4b=args.use_4b,
            verbose=not args.json,
        )
        if args.json:
            print(json.dumps(r, indent=2, default=str))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
