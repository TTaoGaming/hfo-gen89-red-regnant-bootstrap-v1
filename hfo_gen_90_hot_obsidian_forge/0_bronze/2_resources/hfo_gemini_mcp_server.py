#!/usr/bin/env python3
"""
hfo_gemini_mcp_server.py — HFO Gen90 Google Gemini MCP Server
==============================================================

MCP server wrapping Google's Gemini API for use inside VS Code Copilot.
Provides thinking, chat, grounded search, and document analysis tools
powered by your Google Ultra subscription.

Tools:
  - gemini_chat         — General chat / reasoning with Gemini
  - gemini_think        — Deep thinking with thinking mode (Flash 2.5 or Pro)
  - gemini_search       — Grounded search (Gemini + Google Search)
  - gemini_analyze_doc  — Analyze a document from the SSOT
  - gemini_batch        — Batch multiple prompts (for background daemon use)
  - gemini_models       — List all available models with tiers and limits
  - gemini_usage        — Show current rate limit usage

Tiered Models (from hfo_gemini_models.py):
  T0 NANO        — gemini-2.0-flash-lite    (30 RPM, 1500 RPD)
  T1 FLASH       — gemini-2.0-flash         (15 RPM, 1500 RPD)
  T2 FLASH_25    — gemini-2.5-flash         (10 RPM,  500 RPD) + thinking
  T3 LITE_25     — gemini-2.5-flash-lite    (10 RPM,  500 RPD)
  T4 PRO         — gemini-2.5-pro           ( 2 RPM,   25 RPD) + thinking
  T5 EXPERIMENTAL— gemini-exp-1206          ( 2 RPM,   50 RPD) + thinking

Setup:
  1. Go to https://aistudio.google.com/apikey
  2. Sign in with your Google account (same one with Ultra)
  3. Click "Create API Key" -> copy it
  4. Set GEMINI_API_KEY in your .env file

Medallion: bronze
Port: P1 BRIDGE (shared data fabric — bridging Google <-> HFO)
Pointer key: gemini.mcp_server
"""

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── MCP SDK (FastMCP — same pattern as PREY8 server) ──────────
from mcp.server.fastmcp import FastMCP

# ── Google Generative AI ───────────────────────────────────────
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ═══════════════════════════════════════════════════════════════
# Path Resolution
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    """Walk up to find HFO_ROOT (directory containing AGENTS.md)."""
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / os.getenv(
    "HFO_SSOT_DB",
    "hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"
)

# ── Add resources dir to path for registry import ─────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hfo_gemini_models import (
    GEMINI_API_KEY,
    GEMINI_MODELS,
    GeminiRateLimiter,
    create_gemini_client,
    get_effective_limits,
    get_model,
    get_thinking_models,
    list_all_models,
    select_tier,
    VERTEX_AI_ENABLED,
    VERTEX_AI_PROJECT,
)

# ═══════════════════════════════════════════════════════════════
# Gemini Client (uses registry)
# ═══════════════════════════════════════════════════════════════

# Shared rate limiter instance
_rate_limiter = GeminiRateLimiter()

def _get_client():
    """Get a configured Gemini client (auto-detects Vertex AI vs AI Studio)."""
    if not HAS_GENAI:
        raise RuntimeError(
            "google-genai package not installed. Run: pip install google-genai"
        )
    client, mode = create_gemini_client()
    return client

def _resolve_model(tier_or_id: str) -> str:
    """Resolve a tier name or model ID to a concrete model_id string."""
    spec = get_model(tier_or_id)
    return spec.model_id


def _get_db() -> sqlite3.Connection:
    """Get a read-only SSOT database connection."""
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

# ═══════════════════════════════════════════════════════════════
# Tool Implementations
# ═══════════════════════════════════════════════════════════════

async def gemini_chat(prompt: str, model: str = "flash_25",
                      system_instruction: str = "",
                      temperature: float = 0.7) -> dict:
    """
    Chat with Gemini. Good for general reasoning, Q&A, analysis.
    
    Args:
        prompt: Your message
        model: Tier or model ID. Tiers: nano, flash, flash_25, lite_25, pro, experimental.
               Aliases: "quick"->nano, "think"/"deep"->pro. Or full model ID.
        system_instruction: Optional system prompt
        temperature: 0.0 = deterministic, 1.0 = creative
    """
    client = _get_client()
    model_id = _resolve_model(model)
    
    # Rate limit check
    allowed, reason = _rate_limiter.check(model_id)
    if not allowed:
        return {"error": reason, "model": model_id, "rate_limited": True}
    
    config = types.GenerateContentConfig(
        temperature=temperature,
    )
    if system_instruction:
        config.system_instruction = system_instruction
    
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=config,
    )
    
    _rate_limiter.record(model_id)
    
    return {
        "model": model_id,
        "tier": get_model(model).tier.value,
        "response": response.text,
        "usage": {
            "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
            "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
            "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
        },
        "finish_reason": str(response.candidates[0].finish_reason) if response.candidates else "unknown",
    }


async def gemini_think(prompt: str, budget: int = 8192,
                       model: str = "pro") -> dict:
    """
    Deep thinking with Gemini's extended reasoning mode.
    Uses internal chain-of-thought before responding.
    
    Thinking-capable models: gemini-2.5-pro, gemini-2.5-flash, gemini-exp-1206
    
    Args:
        prompt: The problem to think through
        budget: Thinking token budget (1024-32768, higher = deeper)
        model: "pro" (deepest), "flash_25" (fast thinking), "experimental"
    """
    client = _get_client()
    model_id = _resolve_model(model)
    spec = get_model(model)
    
    if not spec.supports_thinking:
        return {
            "error": f"{spec.display_name} ({model_id}) does not support thinking mode. "
                     f"Use: {', '.join(m.model_id for m in get_thinking_models())}",
            "model": model_id,
        }
    
    # Rate limit check
    allowed, reason = _rate_limiter.check(model_id)
    if not allowed:
        return {"error": reason, "model": model_id, "rate_limited": True}
    
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_budget=min(max(budget, 1024), 32768),
        ),
        temperature=0.0,  # Deterministic for thinking tasks
    )
    
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=config,
    )
    
    _rate_limiter.record(model_id)
    
    # Extract thinking content if available
    thinking_text = ""
    answer_text = ""
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'thought') and part.thought:
                thinking_text += part.text + "\n"
            else:
                answer_text += part.text + "\n"
    
    return {
        "model": model_id,
        "tier": spec.tier.value,
        "mode": "thinking",
        "thinking_budget": budget,
        "thinking": thinking_text.strip() if thinking_text else "(thinking hidden)",
        "answer": answer_text.strip() or response.text,
        "usage": {
            "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
            "thinking_tokens": getattr(response.usage_metadata, 'thoughts_token_count', 0),
            "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
            "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
        },
    }


async def gemini_search(query: str, model: str = "flash_25") -> dict:
    """
    Search-grounded Gemini query. Gemini searches Google first,
    then synthesizes an answer with citations.
    
    Args:
        query: What to search for
        model: Any tier or model ID (default: flash_25 for quality + speed)
    """
    client = _get_client()
    model_id = _resolve_model(model)
    spec = get_model(model)
    
    # Rate limit check
    allowed, reason = _rate_limiter.check(model_id)
    if not allowed:
        return {"error": reason, "model": model_id, "rate_limited": True}
    
    # Enable Google Search grounding
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.3,
    )
    
    response = client.models.generate_content(
        model=model_id,
        contents=query,
        config=config,
    )
    
    _rate_limiter.record(model_id)
    
    # Extract grounding metadata
    grounding_chunks = []
    if (response.candidates and 
        response.candidates[0].grounding_metadata and
        response.candidates[0].grounding_metadata.grounding_chunks):
        for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
            if hasattr(chunk, 'web') and chunk.web:
                grounding_chunks.append({
                    "title": getattr(chunk.web, 'title', ''),
                    "uri": getattr(chunk.web, 'uri', ''),
                })
    
    return {
        "model": model_id,
        "tier": spec.tier.value,
        "grounded": True,
        "response": response.text,
        "sources": grounding_chunks,
        "source_count": len(grounding_chunks),
        "usage": {
            "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
            "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
            "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
        },
    }


async def gemini_analyze_doc(doc_id: int, question: str = "",
                              model: str = "flash_25") -> dict:
    """
    Analyze an SSOT document using Gemini.
    Reads the document from the database and sends it to Gemini for analysis.
    
    Args:
        doc_id: Document ID from the SSOT database
        question: Optional specific question about the document
        model: Any tier or model ID (default: flash_25)
    """
    db = _get_db()
    row = db.execute(
        "SELECT id, title, bluf, content, source, port, doc_type, word_count "
        "FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    db.close()
    
    if not row:
        return {"error": f"Document {doc_id} not found in SSOT"}
    
    doc_context = (
        f"# SSOT Document {row['id']}: {row['title']}\n"
        f"Source: {row['source']} | Port: {row['port']} | "
        f"Type: {row['doc_type']} | Words: {row['word_count']}\n"
        f"BLUF: {row['bluf']}\n\n"
        f"---\n\n{row['content']}"
    )
    
    if question:
        prompt = f"{doc_context}\n\n---\n\nQuestion: {question}"
    else:
        prompt = (
            f"{doc_context}\n\n---\n\n"
            "Analyze this document. Provide:\n"
            "1. Key claims and their evidence quality\n"
            "2. Internal consistency assessment\n"
            "3. Actionable insights or concerns\n"
            "4. Connections to other concepts mentioned"
        )
    
    result = await gemini_chat(prompt, model=model, temperature=0.3)
    result["doc_id"] = doc_id
    result["doc_title"] = row['title']
    result["doc_words"] = row['word_count']
    return result


async def gemini_batch(prompts: list, model: str = "flash",
                       system_instruction: str = "") -> dict:
    """
    Batch multiple prompts to Gemini. Good for background processing.
    Processes sequentially with rate limiting.
    
    Args:
        prompts: List of prompt strings
        model: "flash" or "pro"
        system_instruction: Shared system prompt for all
    """
    results = []
    total_tokens = 0
    errors = 0
    
    for i, prompt in enumerate(prompts):
        try:
            result = await gemini_chat(
                prompt, model=model,
                system_instruction=system_instruction,
            )
            results.append({
                "index": i,
                "status": "ok",
                "response": result["response"],
                "tokens": result["usage"]["total_tokens"],
            })
            total_tokens += result["usage"]["total_tokens"]
            
            # Rate limit: 100ms between calls
            if i < len(prompts) - 1:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            errors += 1
            results.append({
                "index": i,
                "status": "error",
                "error": str(e),
            })
    
    return {
        "total_prompts": len(prompts),
        "successful": len(prompts) - errors,
        "errors": errors,
        "total_tokens": total_tokens,
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════
# MCP Server (FastMCP)
# ═══════════════════════════════════════════════════════════════

mcp = FastMCP("HFO Gemini Gen90 — Google AI Bridge")

# Startup diagnostics
print(f"[HFO Gemini MCP] Gen90 | Root: {HFO_ROOT}", file=sys.stderr)
print(f"[HFO Gemini MCP] SSOT: {SSOT_DB}", file=sys.stderr)
print(f"[HFO Gemini MCP] API Key: {'SET' if GEMINI_API_KEY else 'NOT SET'}", file=sys.stderr)
print(f"[HFO Gemini MCP] google-genai: {'installed' if HAS_GENAI else 'MISSING'}", file=sys.stderr)
print(f"[HFO Gemini MCP] Models: {len(GEMINI_MODELS)} registered", file=sys.stderr)

if not HAS_GENAI:
    print("[HFO Gemini MCP] WARNING: pip install google-genai", file=sys.stderr)
if not GEMINI_API_KEY:
    print("[HFO Gemini MCP] WARNING: Set GEMINI_API_KEY in .env", file=sys.stderr)
    print("[HFO Gemini MCP] Get one free: https://aistudio.google.com/apikey", file=sys.stderr)


@mcp.tool()
async def gemini_chat_tool(
    prompt: str,
    model: str = "flash_25",
    system_instruction: str = "",
    temperature: float = 0.7,
) -> str:
    """Chat with Google Gemini. General reasoning, Q&A, code review, analysis.
    
    Model tiers (or use full model ID):
      nano         - gemini-2.0-flash-lite  (30 RPM, 1500 RPD) cheapest/fastest
      flash        - gemini-2.0-flash       (15 RPM, 1500 RPD) fast general
      flash_25     - gemini-2.5-flash       (10 RPM,  500 RPD) quality + thinking
      lite_25      - gemini-2.5-flash-lite  (10 RPM,  500 RPD) light 2.5
      pro          - gemini-2.5-pro         ( 2 RPM,   25 RPD) deepest reasoning
      experimental - gemini-exp-1206        ( 2 RPM,   50 RPD) bleeding edge
    Aliases: quick->nano, think/deep->pro"""
    try:
        result = await gemini_chat(prompt, model, system_instruction, temperature)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def gemini_think_tool(
    prompt: str,
    budget: int = 8192,
    model: str = "pro",
) -> str:
    """Deep thinking with Gemini's extended reasoning mode.
    Uses internal chain-of-thought before answering.
    Good for complex problems, architecture decisions, proofs.
    
    Thinking-capable models: pro (gemini-2.5-pro), flash_25 (gemini-2.5-flash),
    experimental (gemini-exp-1206).
    budget: 1024-32768 (higher = deeper reasoning)."""
    try:
        result = await gemini_think(prompt, budget, model)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def gemini_search_tool(
    query: str,
    model: str = "flash_25",
) -> str:
    """Search-grounded Gemini query. Gemini searches Google first,
    then synthesizes an answer with source citations.
    Great for current events, technical lookups, market research.
    Any tier works. Default: flash_25 for quality + speed."""
    try:
        result = await gemini_search(query, model)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def gemini_analyze_doc_tool(
    doc_id: int,
    question: str = "",
    model: str = "flash_25",
) -> str:
    """Analyze an SSOT document using Gemini.
    Reads the document from the HFO SSOT database and sends it to Gemini
    for analysis, consistency checking, or question answering.
    Any tier works. Default: flash_25."""
    try:
        result = await gemini_analyze_doc(doc_id, question, model)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def gemini_batch_tool(
    prompts: list[str],
    model: str = "nano",
    system_instruction: str = "",
) -> str:
    """Batch multiple prompts to Gemini. Processes sequentially with rate limiting.
    Good for background enrichment, batch document analysis, bulk classification.
    Default: nano (cheapest, highest rate limit)."""
    try:
        result = await gemini_batch(prompts, model, system_instruction)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def gemini_models_tool() -> str:
    """List all available Gemini models with their tiers, token limits,
    rate limits, and capabilities. Shows the full model registry."""
    try:
        models = list_all_models()
        return json.dumps({
            "total_models": len(models),
            "api_key_set": bool(GEMINI_API_KEY),
            "genai_installed": HAS_GENAI,
            "models": models,
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def gemini_usage_tool() -> str:
    """Show current Gemini API rate limit usage for this session.
    Displays per-model RPM and RPD consumption and remaining budget."""
    try:
        usage = _rate_limiter.usage_summary()
        if not usage:
            return json.dumps({
                "message": "No API calls made yet this session.",
                "models_tracked": 0,
            }, indent=2)
        return json.dumps({
            "models_tracked": len(usage),
            "usage": usage,
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run(transport="stdio")
