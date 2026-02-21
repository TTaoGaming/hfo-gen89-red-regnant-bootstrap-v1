#!/usr/bin/env python3
"""
hfo_background_daemon.py — HFO Gen89 Background Process Daemon
===============================================================

Persistent background process that runs continuous enrichment loops
powered by Google Gemini (free tier via AI Studio API key).

4 Task Patterns:
  1. SSOT Enrichment  — Validate, classify, and enrich bronze documents
  2. Web Research     — Search topics from SSOT gaps, ingest findings
  3. Code Gen / Eval  — Generate code artifacts, run eval harnesses
  4. Stigmergy Patrol — Monitor event trail, detect anomalies, compact

Architecture:
  - Single-process, multi-task via asyncio
  - Each task pattern runs on a configurable interval
  - All output goes to bronze (never self-promotes)
  - Writes stigmergy events for every action
  - Respects Gemini rate limits (1500 RPD flash, 25 RPD pro)
  - Graceful shutdown on SIGINT/SIGTERM

Usage:
  # Start all background tasks
  python hfo_background_daemon.py

  # Start specific tasks only
  python hfo_background_daemon.py --tasks enrich,research

  # Dry run (no writes, just show what would happen)
  python hfo_background_daemon.py --dry-run

  # Custom intervals (seconds)
  python hfo_background_daemon.py --enrich-interval 300 --research-interval 600

  # Status check (shows what's running and recent activity)
  python hfo_background_daemon.py --status

Medallion: bronze
Port: P7 NAVIGATE (C2 / steering — daemon orchestrates background work)
Pointer key: daemon.background
"""

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

import psutil

# ── Path Resolution ────────────────────────────────────────────

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / os.getenv(
    "HFO_SSOT_DB",
    "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"
)
BRONZE_DIR = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze"
STATE_FILE = HFO_ROOT / ".hfo_daemon_state.json"

# ── Gemini Config (from centralized registry) ─────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hfo_gemini_models import (
from hfo_ssot_write import get_db_readwrite
    GEMINI_API_KEY,
    GEMINI_MODELS,
    GeminiRateLimiter,
    create_gemini_client,
    get_effective_limits,
    get_model,
    select_tier,
    VERTEX_AI_ENABLED,
    VERTEX_AI_PROJECT,
)

# ═══════════════════════════════════════════════════════════════
# Database Helpers
# ═══════════════════════════════════════════════════════════════

def get_db_readonly() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def write_stigmergy_event(conn: sqlite3.Connection, event_type: str,
                          subject: str, data: dict,
                          source: str = "hfo_background_daemon_gen89"):
    """Write a CloudEvent to the stigmergy trail via canonical write function.
    
    STRUCTURAL ENFORCEMENT: Delegates to hfo_ssot_write.write_stigmergy_event()
    which requires signal_metadata as a validated schema. This wrapper builds
    signal_metadata from daemon defaults — callers don't need to change.
    
    Replaces the old fail-open try/except:pass pattern with fail-closed gating.
    """
    from hfo_ssot_write import (
        write_stigmergy_event as canonical_write,
        build_signal_metadata,
    )
    
    # Build signal_metadata from daemon defaults
    sig = build_signal_metadata(
        port="P7",
        model_id=data.get("model", "gemini-2.5-flash"),
        daemon_name="Background Daemon",
        daemon_version="1.0",
        task_type=event_type.split(".")[-1],
    )
    
    # Delegate to canonical write (signal_metadata is REQUIRED, not optional)
    return canonical_write(
        event_type=event_type,
        subject=subject,
        data=data,
        signal_metadata=sig,
        source=source,
        conn=conn,
    )


# ═══════════════════════════════════════════════════════════════
# Paid-Tier Rate Limiter (Vertex AI / Ultra credits)
# ═══════════════════════════════════════════════════════════════

class _PaidTierRateLimiter(GeminiRateLimiter):
    """Rate limiter that uses Vertex AI paid-tier limits.
    
    Google AI Ultra gives $100/mo credits through Vertex AI.
    This unlocks:
      - Pro: 200 RPM (vs 2), unlimited RPD (vs 25)
      - Flash 2.5: 1000 RPM (vs 10), unlimited RPD (vs 500)
      - Nano: 3000 RPM (vs 30), unlimited RPD (vs 1500)
    """
    
    def check(self, model_id: str) -> tuple[bool, str]:
        """Check rate limits using paid-tier thresholds."""
        spec = GEMINI_MODELS.get(model_id)
        if not spec:
            return False, f"Unknown model: {model_id}"
        
        self._reset_day_if_needed()
        self._cleanup_minute(model_id)
        
        # Use paid-tier limits from registry
        paid_rpm, paid_rpd = get_effective_limits(model_id)
        
        # Check RPD (effectively unlimited with Vertex)
        day_count = self._day_counts.get(model_id, 0)
        if day_count >= paid_rpd:
            return False, f"{spec.display_name} daily limit reached ({day_count}/{paid_rpd} RPD)"
        
        # Check RPM (much higher with Vertex)
        minute_count = len(self._minute_counts.get(model_id, []))
        if minute_count >= paid_rpm:
            return False, f"{spec.display_name} per-minute limit ({minute_count}/{paid_rpm} RPM)"
        
        return True, "OK"


# ═══════════════════════════════════════════════════════════════
# Gemini Client (with rate limiting)
# ═══════════════════════════════════════════════════════════════

class GeminiClient:
    """Rate-limited Gemini client for background use.
    
    Uses centralized model registry (hfo_gemini_models.py) for:
    - Model ID resolution (tier names -> concrete model IDs)
    - Per-model rate limiting (RPM + RPD tracking)
    - Smart tier fallback when limits are hit
    - Auto Vertex AI routing when HFO_VERTEX_PROJECT is set
      (uses Ultra $100/mo credits instead of free tier)
    """
    
    def __init__(self, default_tier: str = "budget"):
        self._client = None
        self._mode = None  # "vertex" or "aistudio"
        self._default_tier = default_tier
        self._rate_limiter = GeminiRateLimiter()
        # Upgrade rate limiter to paid-tier limits when Vertex is active
        if VERTEX_AI_ENABLED:
            self._rate_limiter = _PaidTierRateLimiter()
    
    def _ensure_client(self):
        if self._client is None:
            # Use centralized factory — auto-detects Vertex AI vs AI Studio
            self._client, self._mode = create_gemini_client()
        return self._client
    
    def _resolve(self, tier_or_id: str) -> str:
        """Resolve tier name or model ID to concrete API model ID."""
        return get_model(tier_or_id).model_id
    
    def _log_stigmergy(self, model_id: str, task_type: str):
        """Log Gemini API usage to stigmergy for persistent tracking."""
        try:
            conn = get_db_readwrite()
            write_stigmergy_event(
                conn=conn,
                event_type=f"hfo.gemini.usage.{task_type}",
                subject=f"gemini:{model_id}",
                data={"model": model_id, "task": task_type}
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to log Gemini usage to stigmergy: {e}")
    
    async def chat(self, prompt: str, model: str = None,
                   system_instruction: str = "",
                   temperature: float = 0.5) -> str:
        """Send a prompt to Gemini, return response text.
        
        Uses any tier: budget, flash, frontier_flash, pro, frontier_pro, apex.
        Also accepts legacy names: nano, flash_25, lite_25, experimental.
        Default: instance default_tier (set via --model-tier CLI arg).
        """
        if model is None:
            model = self._default_tier
        model_id = self._resolve(model)
        
        allowed, reason = self._rate_limiter.check(model_id)
        if not allowed:
            # Try auto-fallback to cheaper tier
            fallback = select_tier(
                task_complexity="low", is_batch=True,
                rate_limiter=self._rate_limiter
            )
            model_id = fallback.model_id
            allowed, reason = self._rate_limiter.check(model_id)
            if not allowed:
                raise RuntimeError(f"All rate limits exhausted: {reason}")
        
        client = self._ensure_client()
        from google.genai import types
        
        config = types.GenerateContentConfig(temperature=temperature)
        if system_instruction:
            config.system_instruction = system_instruction
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=model_id, contents=prompt, config=config
            )
        )
        
        self._rate_limiter.record(model_id)
        self._log_stigmergy(model_id, "chat")
        return response.text
    
    async def search_grounded(self, query: str, model: str = "frontier_flash") -> dict:
        """Grounded search via Gemini with Google Search."""
        model_id = self._resolve(model)
        
        allowed, reason = self._rate_limiter.check(model_id)
        if not allowed:
            raise RuntimeError(f"Rate limit: {reason}")
        
        client = self._ensure_client()
        from google.genai import types
        
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        )
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=model_id, contents=query, config=config
            )
        )
        
        self._rate_limiter.record(model_id)
        self._log_stigmergy(model_id, "search_grounded")
        
        sources = []
        if (response.candidates and
            response.candidates[0].grounding_metadata and
            response.candidates[0].grounding_metadata.grounding_chunks):
            for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                if hasattr(chunk, 'web') and chunk.web:
                    sources.append({
                        "title": getattr(chunk.web, 'title', ''),
                        "uri": getattr(chunk.web, 'uri', ''),
                    })
        
        return {"text": response.text, "sources": sources}
    
    @property
    def usage_summary(self) -> dict:
        return self._rate_limiter.usage_summary()

    @property
    def mode(self) -> str:
        """Return 'vertex' or 'aistudio' depending on client routing."""
        if self._mode is None:
            self._ensure_client()
        return self._mode or "unknown"

    async def think(self, prompt: str, model: str = "apex",
                    budget: int = 8192,
                    thinking_level: str = "",
                    system_instruction: str = "") -> dict:
        """Deep thinking with Gemini's extended reasoning mode.
        
        Uses internal chain-of-thought before responding.
        All 2.5+ models support thinking. Best: apex (3.1 Pro), frontier_pro (3 Pro).
        
        Gemini 3.x uses thinking_level (minimal/low/medium/high).
        Gemini 2.5 uses thinking_budget (1024-32768).
        You CANNOT mix both — Gemini 3 returns 400 if thinking_budget is sent.
        This method auto-detects which API to use based on model ID.
        
        Args:
            prompt: The problem to think through
            model: "apex" (3.1 Pro), "frontier_pro" (3 Pro), "pro" (2.5 Pro),
                   "frontier_flash" (3 Flash), "flash" (2.5 Flash)
            budget: Thinking token budget for 2.5 models (1024-32768, higher = deeper)
            thinking_level: Override for 3.x models — "minimal", "low", "medium", "high"
                           If empty, auto-selects based on model (high for Pro, medium for Flash)
            system_instruction: Optional system prompt
        
        Returns:
            dict with 'thinking', 'answer', 'usage' keys
        """
        model_id = self._resolve(model)
        
        allowed, reason = self._rate_limiter.check(model_id)
        if not allowed:
            raise RuntimeError(f"Rate limit: {reason}")
        
        client = self._ensure_client()
        from google.genai import types
        
        # Auto-detect Gemini 3.x vs 2.5 — CRITICAL: cannot mix APIs
        # Gemini 3.x uses thinking_level, 2.5 uses thinking_budget
        is_gemini_3 = any(tag in model_id for tag in ("gemini-3", "gemini-3."))
        
        if is_gemini_3:
            # Gemini 3.x: use thinking_level (minimal/low/medium/high)
            if not thinking_level:
                # Auto-select: high for Pro (Deep Think), medium for Flash
                thinking_level = "high" if "pro" in model_id else "medium"
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level=thinking_level,
                ),
                temperature=0.0,
            )
        else:
            # Gemini 2.5: use thinking_budget (legacy but correct for 2.5)
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_budget=min(max(budget, 1024), 32768),
                ),
                temperature=0.0,
            )
        
        if system_instruction:
            config.system_instruction = system_instruction
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=model_id, contents=prompt, config=config
            )
        )
        
        self._rate_limiter.record(model_id)
        
        # Extract thinking vs answer parts
        thinking_text = ""
        answer_text = ""
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'thought') and part.thought:
                    thinking_text += part.text + "\n"
                else:
                    answer_text += part.text + "\n"
        
        return {
            "thinking": thinking_text.strip(),
            "answer": answer_text.strip() or response.text,
            "model": model_id,
            "usage": {
                "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                "thinking_tokens": getattr(response.usage_metadata, 'thoughts_token_count', 0),
                "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
            },
        }


# ═══════════════════════════════════════════════════════════════
# Task 1: SSOT Enrichment
# ═══════════════════════════════════════════════════════════════

class SSOTEnrichmentTask:
    """
    Continuously validates and enriches bronze SSOT documents.
    
    Actions:
    - Classify untyped documents (assign doc_type)
    - Generate BLUFs for documents missing them
    - Validate tag consistency
    - Flag potential duplicates
    """
    
    def __init__(self, gemini: GeminiClient, dry_run: bool = False):
        self.gemini = gemini
        self.dry_run = dry_run
        self.name = "ssot_enrich"
        self._processed = 0
    
    async def run_once(self) -> dict:
        """Run one enrichment cycle."""
        db = get_db_readonly()
        
        # Find documents needing enrichment
        # Priority 1: Missing BLUF
        missing_bluf = db.execute(
            """SELECT id, title, substr(content, 1, 2000) as content_preview,
                      source, port, doc_type, word_count
               FROM documents 
               WHERE (bluf IS NULL OR bluf = '') 
               AND word_count > 50
               ORDER BY RANDOM() LIMIT 3"""
        ).fetchall()
        
        # Priority 2: Missing doc_type
        missing_type = db.execute(
            """SELECT id, title, substr(content, 1, 1500) as content_preview,
                      source, port, bluf, word_count
               FROM documents
               WHERE (doc_type IS NULL OR doc_type = '')
               AND word_count > 50
               ORDER BY RANDOM() LIMIT 3"""
        ).fetchall()
        
        db.close()
        
        results = {"bluf_generated": 0, "types_classified": 0, "errors": 0}
        
        # Generate BLUFs
        for row in missing_bluf:
            if self.dry_run:
                print(f"  [DRY] Would generate BLUF for doc {row['id']}: {row['title'][:60]}")
                continue
            
            try:
                bluf = await self.gemini.chat(
                    prompt=(
                        f"Write a 1-2 sentence BLUF (Bottom Line Up Front) for this document.\n"
                        f"Title: {row['title']}\n"
                        f"Source: {row['source']}, Port: {row['port']}\n\n"
                        f"{row['content_preview']}\n\n"
                        f"BLUF (be concise, factual, no filler):"
                    ),
                    system_instruction="You write concise BLUFs for technical documents. Max 2 sentences.",
                    temperature=0.2,
                )
                
                # Write to database
                wdb = get_db_readwrite()
                wdb.execute("UPDATE documents SET bluf = ? WHERE id = ?",
                           (bluf.strip()[:500], row['id']))
                write_stigmergy_event(
                    wdb, "hfo.gen89.daemon.enrich.bluf",
                    f"doc-{row['id']}", {
                        "doc_id": row['id'],
                        "doc_title": row['title'],
                        "bluf": bluf.strip()[:500],
                        "action": "generated_bluf",
                    }
                )
                wdb.close()
                results["bluf_generated"] += 1
                
                await asyncio.sleep(4)  # Rate limit spacing
                
            except Exception as e:
                results["errors"] += 1
                print(f"  [ERROR] BLUF gen for doc {row['id']}: {e}", file=sys.stderr)
        
        # Classify doc_types
        valid_types = [
            "portable_artifact", "explanation", "reference", "doctrine",
            "how_to", "tutorial", "recipe_card", "forge_report",
            "memory", "config", "incident_report", "project_spec",
        ]
        
        for row in missing_type:
            if self.dry_run:
                print(f"  [DRY] Would classify doc {row['id']}: {row['title'][:60]}")
                continue
            
            try:
                classification = await self.gemini.chat(
                    prompt=(
                        f"Classify this document into exactly one type.\n"
                        f"Valid types: {', '.join(valid_types)}\n\n"
                        f"Title: {row['title']}\n"
                        f"BLUF: {row['bluf']}\n"
                        f"Source: {row['source']}, Port: {row['port']}\n\n"
                        f"{row['content_preview']}\n\n"
                        f"Type (one word only):"
                    ),
                    system_instruction="Reply with exactly one type from the list. Nothing else.",
                    temperature=0.0,
                )
                
                doc_type = classification.strip().lower().replace(" ", "_")
                if doc_type in valid_types:
                    wdb = get_db_readwrite()
                    wdb.execute("UPDATE documents SET doc_type = ? WHERE id = ?",
                               (doc_type, row['id']))
                    write_stigmergy_event(
                        wdb, "hfo.gen89.daemon.enrich.classify",
                        f"doc-{row['id']}", {
                            "doc_id": row['id'],
                            "doc_title": row['title'],
                            "doc_type": doc_type,
                            "action": "classified_type",
                        }
                    )
                    wdb.close()
                    results["types_classified"] += 1
                
                await asyncio.sleep(4)
                
            except Exception as e:
                results["errors"] += 1
                print(f"  [ERROR] Classify doc {row['id']}: {e}", file=sys.stderr)
        
        self._processed += results["bluf_generated"] + results["types_classified"]
        return results


# ═══════════════════════════════════════════════════════════════
# Task 2: Web Research
# ═══════════════════════════════════════════════════════════════

class WebResearchTask:
    """
    Searches the web for topics identified from SSOT gaps,
    then ingests findings as bronze documents.
    
    Uses Gemini's grounded search (Google Search built-in).
    """
    
    def __init__(self, gemini: GeminiClient, dry_run: bool = False):
        self.gemini = gemini
        self.dry_run = dry_run
        self.name = "web_research"
        self._researched = 0
    
    async def run_once(self) -> dict:
        """Run one research cycle."""
        db = get_db_readonly()
        
        # Find recent high-value topics from stigmergy trail
        recent_topics = db.execute(
            """SELECT DISTINCT subject, data_json
               FROM stigmergy_events
               WHERE event_type LIKE '%prey8%'
               AND timestamp > datetime('now', '-24 hours')
               ORDER BY timestamp DESC
               LIMIT 5"""
        ).fetchall()
        
        # Extract research-worthy probes
        probes = []
        for row in recent_topics:
            try:
                data = json.loads(row['data_json'])
                inner = data.get("data", data)
                probe = inner.get("probe", "")
                if probe and len(probe) > 20:
                    probes.append(probe[:200])
            except (json.JSONDecodeError, KeyError):
                pass
        
        db.close()
        
        if not probes:
            return {"status": "no_topics", "researched": 0}
        
        results = {"researched": 0, "sources_found": 0, "errors": 0}
        
        # Research one topic per cycle to stay within rate limits
        probe = probes[0]
        
        if self.dry_run:
            print(f"  [DRY] Would research: {probe[:80]}...")
            return results
        
        try:
            research = await self.gemini.search_grounded(
                f"Latest developments, best practices, and key references for: {probe}",
                model="flash",
            )
            
            if research["text"]:
                results["researched"] = 1
                results["sources_found"] = len(research["sources"])
                
                # Write as stigmergy event (not a full document — that would need operator review)
                wdb = get_db_readwrite()
                write_stigmergy_event(
                    wdb, "hfo.gen89.daemon.research",
                    "web-research", {
                        "probe": probe,
                        "summary": research["text"][:2000],
                        "sources": research["sources"][:10],
                        "source_count": len(research["sources"]),
                        "action": "web_research",
                    }
                )
                wdb.close()
                self._researched += 1
            
        except Exception as e:
            results["errors"] += 1
            print(f"  [ERROR] Research: {e}", file=sys.stderr)
        
        return results


# ═══════════════════════════════════════════════════════════════
# Task 3: Code Generation / Eval
# ═══════════════════════════════════════════════════════════════

class CodeGenEvalTask:
    """
    Background code generation and evaluation.
    
    Actions:
    - Analyze existing bronze scripts for quality issues
    - Generate test stubs for untested code
    - Run lightweight static analysis
    """
    
    def __init__(self, gemini: GeminiClient, dry_run: bool = False):
        self.gemini = gemini
        self.dry_run = dry_run
        self.name = "code_eval"
        self._analyzed = 0
    
    async def run_once(self) -> dict:
        """Run one code eval cycle."""
        # Scan bronze resources for Python files
        resources_dir = BRONZE_DIR / "resources"
        py_files = sorted(resources_dir.glob("*.py"))
        
        if not py_files:
            return {"status": "no_files", "analyzed": 0}
        
        # Pick a random file to analyze
        import random
        target = random.choice(py_files)
        
        results = {"analyzed": 0, "issues_found": 0, "errors": 0}
        
        if self.dry_run:
            print(f"  [DRY] Would analyze: {target.name}")
            return results
        
        try:
            # Read first 3000 chars of the file
            content = target.read_text(encoding="utf-8", errors="replace")[:3000]
            
            analysis = await self.gemini.chat(
                prompt=(
                    f"Quick code review of {target.name}:\n\n"
                    f"```python\n{content}\n```\n\n"
                    f"List top 3 issues (bugs, security, maintainability). "
                    f"Be specific with line references. If no issues, say 'CLEAN'."
                ),
                system_instruction=(
                    "You are a senior Python code reviewer. Be concise. "
                    "Focus on real bugs and security issues, not style."
                ),
                temperature=0.2,
            )
            
            is_clean = "CLEAN" in analysis.upper()
            
            # Record analysis
            wdb = get_db_readwrite()
            write_stigmergy_event(
                wdb, "hfo.gen89.daemon.code_eval",
                f"file-{target.name}", {
                    "file": target.name,
                    "file_size": len(content),
                    "analysis": analysis[:1500],
                    "clean": is_clean,
                    "action": "code_review",
                }
            )
            wdb.close()
            
            results["analyzed"] = 1
            results["issues_found"] = 0 if is_clean else 1
            self._analyzed += 1
            
        except Exception as e:
            results["errors"] += 1
            print(f"  [ERROR] Code eval {target.name}: {e}", file=sys.stderr)
        
        return results


# ═══════════════════════════════════════════════════════════════
# Task 4: Stigmergy Patrol
# ═══════════════════════════════════════════════════════════════

class StigmergyPatrolTask:
    """
    Monitor the stigmergy event trail for anomalies.
    
    Actions:
    - Detect orphaned PREY8 sessions (perceive without yield)
    - Flag gate blocks and tamper alerts
    - Compact old events into digest summaries
    - Track event growth rate
    """
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.name = "stigmergy_patrol"
    
    async def run_once(self) -> dict:
        """Run one patrol cycle."""
        db = get_db_readonly()
        
        # Count events by type (last 24h)
        recent_counts = db.execute(
            """SELECT event_type, COUNT(*) as cnt
               FROM stigmergy_events
               WHERE timestamp > datetime('now', '-24 hours')
               GROUP BY event_type
               ORDER BY cnt DESC LIMIT 20"""
        ).fetchall()
        
        # Find orphaned perceives (perceive without matching yield)
        orphans = db.execute(
            """SELECT se1.id, se1.timestamp, se1.data_json
               FROM stigmergy_events se1
               WHERE se1.event_type = 'hfo.gen89.prey8.perceive'
               AND se1.timestamp > datetime('now', '-48 hours')
               AND NOT EXISTS (
                   SELECT 1 FROM stigmergy_events se2
                   WHERE se2.event_type = 'hfo.gen89.prey8.yield'
                   AND se2.timestamp > se1.timestamp
                   AND se2.data_json LIKE '%' || 
                       json_extract(se1.data_json, '$.data.nonce') || '%'
               )
               ORDER BY se1.timestamp DESC LIMIT 10"""
        ).fetchall()
        
        # Find gate blocks
        gate_blocks = db.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE event_type LIKE '%gate_blocked%'
               AND timestamp > datetime('now', '-24 hours')"""
        ).fetchone()
        
        # Find tamper alerts
        tamper_alerts = db.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE event_type LIKE '%tamper%'
               AND timestamp > datetime('now', '-24 hours')"""
        ).fetchone()
        
        # Total event count
        total = db.execute("SELECT COUNT(*) as cnt FROM stigmergy_events").fetchone()
        
        db.close()
        
        results = {
            "total_events": total['cnt'],
            "recent_24h": dict(recent_counts) if recent_counts else {},
            "orphaned_perceives": len(orphans),
            "gate_blocks_24h": gate_blocks['cnt'],
            "tamper_alerts_24h": tamper_alerts['cnt'],
            "status": "healthy" if (gate_blocks['cnt'] == 0 and tamper_alerts['cnt'] == 0) else "alert",
        }
        
        if not self.dry_run and (orphans or gate_blocks['cnt'] > 0 or tamper_alerts['cnt'] > 0):
            wdb = get_db_readwrite()
            write_stigmergy_event(
                wdb, "hfo.gen89.daemon.patrol",
                "stigmergy-patrol", {
                    "action": "patrol_report",
                    "orphaned_perceives": len(orphans),
                    "gate_blocks_24h": gate_blocks['cnt'],
                    "tamper_alerts_24h": tamper_alerts['cnt'],
                    "total_events": total['cnt'],
                    "status": results["status"],
                }
            )
            wdb.close()
        
        return results


# ═══════════════════════════════════════════════════════════════
# Task 5: Port Assignment (Vertex AI powered)
# ═══════════════════════════════════════════════════════════════

class PortAssignmentTask:
    """
    Assign octree port (P0-P7) to documents missing one.
    
    This is the single biggest enrichment gap: 7,676 of 9,861 docs
    (78%) have no port. Uses Flash 2.5 for bulk classification.
    With Vertex AI: 1000 RPM / unlimited RPD = can clear backlog
    in hours instead of days.
    
    Octree Ports:
      P0 OBSERVE    — Sensing, telemetry, monitoring, detection
      P1 BRIDGE     — Data fabric, APIs, integrations, shared infra
      P2 SHAPE      — Creation, code gen, models, artifacts
      P3 INJECT     — Delivery, payloads, deployment, publishing
      P4 DISRUPT    — Red team, adversarial, testing, probing
      P5 IMMUNIZE   — Blue team, defense, gates, validation
      P6 ASSIMILATE — Learning, memory, knowledge, embeddings
      P7 NAVIGATE   — C2, steering, orchestration, planning
    """
    
    VALID_PORTS = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]
    
    PORT_DESCRIPTIONS = """P0 OBSERVE: Sensing, telemetry, monitoring, observability, detection, data collection
P1 BRIDGE: Data fabric, APIs, integrations, shared infrastructure, schemas, protocols
P2 SHAPE: Creation, code generation, models, artifacts, building, synthesis
P3 INJECT: Delivery, payloads, deployment, publishing, injection, distribution
P4 DISRUPT: Red team, adversarial testing, probing, attack, mutation, chaos engineering
P5 IMMUNIZE: Blue team, defense, gates, validation, security, hardening, compliance
P6 ASSIMILATE: Learning, memory, knowledge management, embeddings, training, recall
P7 NAVIGATE: C2, steering, orchestration, planning, scheduling, strategic decisions"""
    
    def __init__(self, gemini: GeminiClient, dry_run: bool = False,
                 batch_size: int = 10):
        self.gemini = gemini
        self.dry_run = dry_run
        self.name = "port_assign"
        self.batch_size = batch_size
        self._assigned = 0
    
    async def run_once(self) -> dict:
        """Assign ports to a batch of unported documents."""
        db = get_db_readonly()
        
        # Get batch of unported docs with enough context to classify
        unported = db.execute(
            f"""SELECT id, title, bluf, doc_type, source, tags,
                       substr(content, 1, 1500) as content_preview,
                       word_count
                FROM documents
                WHERE (port IS NULL OR port = '')
                AND word_count > 20
                ORDER BY RANDOM() LIMIT {self.batch_size}"""
        ).fetchall()
        
        db.close()
        
        if not unported:
            return {"status": "all_ported", "assigned": 0}
        
        results = {"assigned": 0, "errors": 0, "skipped": 0, "batch_size": len(unported)}
        
        for row in unported:
            if self.dry_run:
                print(f"  [DRY] Would assign port for doc {row['id']}: {row['title'][:60]}")
                results["skipped"] += 1
                continue
            
            try:
                classification = await self.gemini.chat(
                    prompt=(
                        f"Classify this document into exactly ONE octree port.\n\n"
                        f"Ports:\n{self.PORT_DESCRIPTIONS}\n\n"
                        f"Document:\n"
                        f"  Title: {row['title']}\n"
                        f"  BLUF: {row['bluf'] or '(none)'}\n"
                        f"  Type: {row['doc_type']}\n"
                        f"  Source: {row['source']}\n"
                        f"  Tags: {row['tags']}\n\n"
                        f"  Content preview:\n{row['content_preview'][:1000]}\n\n"
                        f"Reply with ONLY the port code (P0, P1, P2, P3, P4, P5, P6, or P7):"
                    ),
                    model="frontier_flash",  # Gemini 3 Flash: frontier quality, free tier available
                    system_instruction=(
                        "You classify documents into octree ports. "
                        "Reply with exactly one port code: P0, P1, P2, P3, P4, P5, P6, or P7. "
                        "Nothing else."
                    ),
                    temperature=0.0,
                )
                
                # Parse port from response
                port = classification.strip().upper()[:2]
                if port not in self.VALID_PORTS:
                    # Try to extract from response
                    for p in self.VALID_PORTS:
                        if p in classification.upper():
                            port = p
                            break
                    else:
                        results["errors"] += 1
                        continue
                
                # Write to database
                wdb = get_db_readwrite()
                wdb.execute("UPDATE documents SET port = ? WHERE id = ?",
                           (port, row['id']))
                write_stigmergy_event(
                    wdb, "hfo.gen89.daemon.enrich.port_assign",
                    f"doc-{row['id']}", {
                        "doc_id": row['id'],
                        "doc_title": row['title'][:100],
                        "assigned_port": port,
                        "source": row['source'],
                        "action": "port_assigned",
                    }
                )
                wdb.close()
                results["assigned"] += 1
                self._assigned += 1
                
                await asyncio.sleep(0.5)  # Light spacing — Vertex can handle high RPM
                
            except Exception as e:
                results["errors"] += 1
                print(f"  [ERROR] Port assign doc {row['id']}: {e}", file=sys.stderr)
        
        return results


# ═══════════════════════════════════════════════════════════════
# Task 6: Deep Analysis (Pro Thinking — Vertex AI powered)
# ═══════════════════════════════════════════════════════════════

class DeepAnalysisTask:
    """
    Use Gemini 3.1 Pro with Deep Think mode for deep document analysis.
    
    This is the HIGHEST INTELLIGENCE option available through Google.
    Gemini 3.1 Pro: thinking_level="high" activates Deep Think.
    With Ultra credits ($100/mo), Pro gets 200 RPM / unlimited RPD.
    No free tier for 3.x Pro models.
    
    Actions:
    - Deep analysis of high-value documents (>2000 words)
    - Cross-reference validation against other docs
    - Quality scoring and confidence assessment
    - Structural integrity checking
    - Key insight extraction
    
    Deep Think benchmarks (3 Pro):
      41.0% HLE, 93.8% GPQA-D, 45.1% ARC-AGI-2
    3.1 Pro improves: better thinking, token efficiency, factual consistency.
    """
    
    def __init__(self, gemini: GeminiClient, dry_run: bool = False,
                 thinking_level: str = "high"):
        self.gemini = gemini
        self.dry_run = dry_run
        self.name = "deep_analysis"
        self.thinking_level = thinking_level  # high = Deep Think
        self._analyzed = 0
    
    async def run_once(self) -> dict:
        """Deeply analyze one high-value document using Pro thinking."""
        db = get_db_readonly()
        
        # Pick a high-value doc that hasn't been deeply analyzed yet
        # Prioritize: large docs, diataxis, artifacts, silver, gold_report
        doc = db.execute(
            """SELECT d.id, d.title, d.bluf, d.content, d.source, d.port,
                      d.doc_type, d.word_count, d.tags, d.metadata_json
               FROM documents d
               WHERE d.word_count > 500
               AND d.source IN ('diataxis', 'artifact', 'silver', 'gold_report',
                                'p4_payload', 'forge_report', 'project')
               AND d.id NOT IN (
                   SELECT CAST(
                       json_extract(se.data_json, '$.data.doc_id') AS INTEGER
                   )
                   FROM stigmergy_events se
                   WHERE se.event_type = 'hfo.gen89.daemon.deep_analysis'
                   AND json_extract(se.data_json, '$.data.doc_id') IS NOT NULL
               )
               ORDER BY d.word_count DESC
               LIMIT 1"""
        ).fetchone()
        
        if not doc:
            # Fall back to any large unanalyzed doc
            doc = db.execute(
                """SELECT d.id, d.title, d.bluf, d.content, d.source, d.port,
                          d.doc_type, d.word_count, d.tags, d.metadata_json
                   FROM documents d
                   WHERE d.word_count > 1000
                   AND d.id NOT IN (
                       SELECT CAST(
                           json_extract(se.data_json, '$.data.doc_id') AS INTEGER
                       )
                       FROM stigmergy_events se
                       WHERE se.event_type = 'hfo.gen89.daemon.deep_analysis'
                       AND json_extract(se.data_json, '$.data.doc_id') IS NOT NULL
                   )
                   ORDER BY RANDOM()
                   LIMIT 1"""
            ).fetchone()
        
        db.close()
        
        if not doc:
            return {"status": "all_analyzed", "analyzed": 0}
        
        results = {"analyzed": 0, "quality_score": None, "errors": 0}
        
        if self.dry_run:
            print(f"  [DRY] Would deep-analyze doc {doc['id']}: "
                  f"{doc['title'][:60]} ({doc['word_count']} words)")
            return results
        
        try:
            # Truncate content to fit in context window (leave room for thinking)
            # Pro has 1M input tokens but we send reasonable chunks
            content_limit = min(len(doc['content']), 50000)
            doc_content = doc['content'][:content_limit]
            
            analysis = await self.gemini.think(
                prompt=(
                    f"You are performing a deep quality analysis of an SSOT document.\n\n"
                    f"# Document Metadata\n"
                    f"- ID: {doc['id']}\n"
                    f"- Title: {doc['title']}\n"
                    f"- Source: {doc['source']}\n"
                    f"- Port: {doc['port'] or 'unassigned'}\n"
                    f"- Type: {doc['doc_type']}\n"
                    f"- Words: {doc['word_count']}\n"
                    f"- Tags: {doc['tags']}\n"
                    f"- BLUF: {doc['bluf'] or '(none)'}\n\n"
                    f"# Content\n{doc_content}\n\n"
                    f"# Analysis Required\n"
                    f"Provide a structured analysis with:\n"
                    f"1. **Quality Score** (0-100): Overall document quality\n"
                    f"2. **Key Claims**: List the top 3-5 factual claims made\n"
                    f"3. **Evidence Quality**: Rate evidence backing (strong/moderate/weak/none)\n"
                    f"4. **Internal Consistency**: Any contradictions or gaps?\n"
                    f"5. **Actionable Insights**: What's useful from this document?\n"
                    f"6. **Cross-References**: What other topics/concepts should this link to?\n"
                    f"7. **Improvement Suggestions**: How could this document be improved?\n"
                    f"8. **Bronze→Silver Readiness**: Is this ready for medallion promotion? Why/why not?\n\n"
                    f"Start your response with 'QUALITY_SCORE: XX' where XX is 0-100."
                ),
                model="flash",  # P2 fast tier — medium intelligence, high throughput
                thinking_level=self.thinking_level,
            )
            
            answer = analysis.get("answer", "")
            
            # Extract quality score
            quality_score = None
            for line in answer.split("\n")[:5]:
                if "QUALITY_SCORE" in line.upper():
                    try:
                        score_str = line.split(":")[-1].strip()
                        quality_score = int(''.join(c for c in score_str if c.isdigit())[:3])
                        if quality_score > 100:
                            quality_score = quality_score // 10  # Handle "085" etc
                    except (ValueError, IndexError):
                        pass
                    break
            
            results["quality_score"] = quality_score
            results["analyzed"] = 1
            
            # Write detailed analysis to SSOT
            wdb = get_db_readwrite()
            write_stigmergy_event(
                wdb, "hfo.gen89.daemon.deep_analysis",
                f"doc-{doc['id']}", {
                    "doc_id": doc['id'],
                    "doc_title": doc['title'][:200],
                    "doc_source": doc['source'],
                    "doc_words": doc['word_count'],
                    "quality_score": quality_score,
                    "analysis": answer[:4000],
                    "thinking_tokens": analysis.get("usage", {}).get("thinking_tokens", 0),
                    "total_tokens": analysis.get("usage", {}).get("total_tokens", 0),
                    "model": analysis.get("model", "gemini-3.1-pro-preview"),
                    "thinking_level": self.thinking_level,
                    "action": "deep_analysis_deep_think",
                }
            )
            wdb.close()
            self._analyzed += 1
            
        except Exception as e:
            results["errors"] += 1
            print(f"  [ERROR] Deep analysis doc {doc['id']}: {e}", file=sys.stderr)
        
        return results


# ═══════════════════════════════════════════════════════════════
# Daemon Orchestrator
# ═══════════════════════════════════════════════════════════════

class BackgroundDaemon:
    """Orchestrates all background tasks with configurable intervals."""
    
    def __init__(self, tasks: list[str], dry_run: bool = False,
                 model_tier: str = "budget",
                 enrich_interval: int = 300,
                 research_interval: int = 600,
                 codegen_interval: int = 900,
                 patrol_interval: int = 120,
                 port_assign_interval: int = 60,
                 deep_analysis_interval: int = 600):
        
        self.dry_run = dry_run
        self.running = False
        self.model_tier = model_tier
        self.gemini = GeminiClient(default_tier=model_tier) if (GEMINI_API_KEY or VERTEX_AI_ENABLED) else None
        self.start_time = None
        
        # Task registry
        self._tasks = {}
        self._intervals = {}
        
        if "enrich" in tasks and self.gemini:
            self._tasks["enrich"] = SSOTEnrichmentTask(self.gemini, dry_run)
            self._intervals["enrich"] = enrich_interval
        
        if "research" in tasks and self.gemini:
            self._tasks["research"] = WebResearchTask(self.gemini, dry_run)
            self._intervals["research"] = research_interval
        
        if "codegen" in tasks and self.gemini:
            self._tasks["codegen"] = CodeGenEvalTask(self.gemini, dry_run)
            self._intervals["codegen"] = codegen_interval
        
        if "patrol" in tasks:
            self._tasks["patrol"] = StigmergyPatrolTask(dry_run)
            self._intervals["patrol"] = patrol_interval
        
        if "port_assign" in tasks and self.gemini:
            batch_size = 20 if VERTEX_AI_ENABLED else 5  # Higher throughput with Vertex
            self._tasks["port_assign"] = PortAssignmentTask(
                self.gemini, dry_run, batch_size=batch_size)
            self._intervals["port_assign"] = port_assign_interval
        
        if "deep_analysis" in tasks and self.gemini:
            self._tasks["deep_analysis"] = DeepAnalysisTask(
                self.gemini, dry_run, thinking_level="high")
            self._intervals["deep_analysis"] = deep_analysis_interval
    
    def _save_state(self):
        """Persist daemon state to disk."""
        state = {
            "pid": os.getpid(),
            "start_time": self.start_time,
            "running": self.running,
            "tasks": list(self._tasks.keys()),
            "intervals": self._intervals,
            "gemini_usage": self.gemini.usage_summary if self.gemini else {},
            "last_update": datetime.now(timezone.utc).isoformat(),
        }
        STATE_FILE.write_text(json.dumps(state, indent=2))
    
    def _print_banner(self):
        print("=" * 60)
        print("  HFO Gen89 — Background Daemon")
        print("=" * 60)
        print(f"  Root:    {HFO_ROOT}")
        print(f"  SSOT:    {SSOT_DB}")
        if self.gemini:
            mode = self.gemini.mode
            tier_label = self.model_tier
            if mode == "vertex":
                print(f"  Gemini:  VERTEX AI ({VERTEX_AI_PROJECT}) — Ultra credits active")
            else:
                print(f"  Gemini:  AI Studio (free tier)")
            print(f"  Tier:    {tier_label} → {self.gemini._resolve(tier_label)}")
        else:
            print(f"  Gemini:  NOT AVAILABLE")
        print(f"  Mode:    {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"  Tasks:   {', '.join(self._tasks.keys()) or 'none'}")
        print()
        for name, interval in self._intervals.items():
            print(f"    {name:16s} every {interval:>5d}s ({interval//60}m)")
        print()
        print("  Press Ctrl+C to stop gracefully.")
        print("=" * 60)
    
    async def _check_throttle(self, name: str):
        """Check resource limits and throttle if necessary."""
        cpu_limit = float(os.getenv("HFO_CPU_THROTTLE_PCT", "75.0"))
        ram_limit_gb = float(os.getenv("HFO_RAM_THROTTLE_GB", "4.0"))
        
        while self.running:
            cpu_pct = psutil.cpu_percent(interval=0.5)
            ram_free_gb = psutil.virtual_memory().available / (1024**3)
            
            throttled = False
            reasons = []
            if cpu_pct > cpu_limit:
                throttled = True
                reasons.append(f"CPU {cpu_pct:.1f}% > {cpu_limit}%")
            if ram_free_gb < ram_limit_gb:
                throttled = True
                reasons.append(f"RAM {ram_free_gb:.1f}GB < {ram_limit_gb}GB")
                
            if throttled:
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"  [{ts}] [THROTTLE] {name} paused: {', '.join(reasons)}", flush=True)
                await asyncio.sleep(10)
            else:
                break

    async def _run_task_loop(self, name: str, task, interval: int):
        """Run a single task on a recurring interval."""
        while self.running:
            try:
                await self._check_throttle(name)
                if not self.running:
                    break
                
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"  [{ts}] Running {name}...", flush=True)
                
                result = await task.run_once()
                
                ts2 = datetime.now(timezone.utc).strftime("%H:%M:%S")
                status = json.dumps(result, default=str)[:120]
                print(f"  [{ts2}] {name} → {status}", flush=True)
                
                self._save_state()
                
            except Exception as e:
                print(f"  [ERROR] {name}: {e}", file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)
            
            # Wait for next cycle
            for _ in range(interval):
                if not self.running:
                    break
                await asyncio.sleep(1)
    
    async def run(self):
        """Start all task loops."""
        self.running = True
        self.start_time = datetime.now(timezone.utc).isoformat()
        
        self._print_banner()
        self._save_state()
        
        if not self._tasks:
            print("  No tasks configured. Nothing to do.")
            if not self.gemini:
                print("  Set GEMINI_API_KEY in .env to enable Gemini-powered tasks.")
                print("  Get one free: https://aistudio.google.com/apikey")
            return
        
        # Log daemon start
        if not self.dry_run:
            try:
                wdb = get_db_readwrite()
                write_stigmergy_event(
                    wdb, "hfo.gen89.daemon.start",
                    "daemon-lifecycle", {
                        "action": "daemon_start",
                        "tasks": list(self._tasks.keys()),
                        "intervals": self._intervals,
                        "pid": os.getpid(),
                        "dry_run": self.dry_run,
                    }
                )
                wdb.close()
            except Exception as e:
                print(f"  [WARN] Could not log daemon start: {e}", file=sys.stderr)
        
        # Launch all task loops
        loops = []
        for name, task in self._tasks.items():
            interval = self._intervals[name]
            loops.append(self._run_task_loop(name, task, interval))
        
        try:
            await asyncio.gather(*loops)
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            self._save_state()
            print("\n  Daemon stopped gracefully.")
    
    def stop(self):
        """Signal the daemon to stop."""
        self.running = False


# ═══════════════════════════════════════════════════════════════
# Status Command
# ═══════════════════════════════════════════════════════════════

def show_status():
    """Show daemon status from state file."""
    print("=" * 60)
    print("  HFO Gen89 — Background Daemon Status")
    print("=" * 60)
    
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        print(f"  PID:          {state.get('pid', '?')}")
        print(f"  Running:      {state.get('running', False)}")
        print(f"  Started:      {state.get('start_time', '?')}")
        print(f"  Last update:  {state.get('last_update', '?')}")
        print(f"  Tasks:        {', '.join(state.get('tasks', []))}")
        
        usage = state.get("gemini_usage", {})
        if usage:
            print(f"\n  Gemini Usage (per-model):")
            for mid, info in usage.items():
                print(f"    {info.get('display_name', mid)}: "
                      f"{info.get('rpd_used', 0)}/{info.get('rpd_limit', '?')} RPD")
    else:
        print("  No daemon state found. Start with: python hfo_background_daemon.py")
    
    # Show recent daemon events from SSOT
    if SSOT_DB.exists():
        db = get_db_readonly()
        events = db.execute(
            """SELECT event_type, timestamp, subject
               FROM stigmergy_events
               WHERE event_type LIKE '%daemon%'
               ORDER BY timestamp DESC LIMIT 10"""
        ).fetchall()
        db.close()
        
        if events:
            print(f"\n  Recent daemon events:")
            for e in events:
                print(f"    {e['timestamp'][:19]}  {e['event_type']:40s}  {e['subject']}")
    
    print()


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="HFO Gen89 Background Daemon — continuous SSOT enrichment"
    )
    parser.add_argument(
        "--tasks", default="enrich,research,codegen,patrol,port_assign,deep_analysis",
        help="Comma-separated tasks: enrich,research,codegen,patrol,port_assign,deep_analysis (default: all)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    parser.add_argument("--status", action="store_true",
                        help="Show daemon status and exit")
    parser.add_argument("--enrich-interval", type=int, default=300,
                        help="SSOT enrichment interval in seconds (default: 300)")
    parser.add_argument("--research-interval", type=int, default=600,
                        help="Web research interval in seconds (default: 600)")
    parser.add_argument("--codegen-interval", type=int, default=900,
                        help="Code eval interval in seconds (default: 900)")
    parser.add_argument("--patrol-interval", type=int, default=120,
                        help="Stigmergy patrol interval in seconds (default: 120)")
    parser.add_argument("--port-assign-interval", type=int, default=60,
                        help="Port assignment interval in seconds (default: 60)")
    parser.add_argument("--deep-analysis-interval", type=int, default=600,
                        help="Deep analysis interval in seconds (default: 600)")
    parser.add_argument("--model-tier", default="budget",
                        help="Gemini model tier: budget, flash, frontier_flash, pro, frontier_pro, apex (default: budget)")
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
        return
    
    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    
    daemon = BackgroundDaemon(
        tasks=tasks,
        dry_run=args.dry_run,
        model_tier=args.model_tier,
        enrich_interval=args.enrich_interval,
        research_interval=args.research_interval,
        codegen_interval=args.codegen_interval,
        patrol_interval=args.patrol_interval,
        port_assign_interval=args.port_assign_interval,
        deep_analysis_interval=args.deep_analysis_interval,
    )
    
    # Graceful shutdown
    def _signal_handler(sig, frame):
        print("\n  Shutting down...", flush=True)
        daemon.stop()
    
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _signal_handler)
    
    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
