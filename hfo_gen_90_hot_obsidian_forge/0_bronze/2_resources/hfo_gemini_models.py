#!/usr/bin/env python3
"""
hfo_gemini_models.py — HFO Gen90 Gemini Model Registry
=======================================================

Centralized tiered model configuration for all Google Gemini models.
Single source of truth imported by:
  - hfo_gemini_mcp_server.py (MCP tools)
  - hfo_background_daemon.py (background tasks)
  - hfo_swarm_config.py (swarm provider layer)

Updated: 2026-02-20 from live Google docs (ai.google.dev + cloud.google.com).

MAP-ELITES Tier Architecture (quality-diversity):
  ──────────────────────────────────────────────────────────────────
  Tier │ Model ID                 │ $/1M In │ $/1M Out │ Free? │ Status
  ─────┼──────────────────────────┼─────────┼──────────┼───────┼────────
  T0   │ gemini-2.5-flash-lite    │  $0.10  │   $0.40  │  YES  │ GA Stable
  T1   │ gemini-2.5-flash         │  $0.30  │   $2.50  │  YES  │ GA Stable
  T2   │ gemini-3-flash-preview   │  $0.50  │   $3.00  │  YES  │ Preview
  T3   │ gemini-2.5-pro           │  $1.25  │  $10.00  │  YES  │ GA Stable
  T4   │ gemini-3-pro-preview     │  $2.00  │  $12.00  │  NO   │ Preview
  T5   │ gemini-3.1-pro-preview   │  $2.00  │  $12.00  │  NO   │ Preview
  ──────────────────────────────────────────────────────────────────

Specialty Models:
  COMPUTER_USE   — gemini-2.5-computer-use-preview-10-2025
  IMAGE_GEN      — gemini-2.5-flash-image (Nano Banana)
  IMAGE_PRO      — gemini-3-pro-image-preview (Nano Banana Pro, 4K)
  TTS_FLASH      — gemini-2.5-flash-preview-tts
  TTS_PRO        — gemini-2.5-pro-preview-tts
  DEEP_RESEARCH  — deep-research-pro-preview-12-2025
  EMBEDDING      — gemini-embedding-001

Deprecated (kept for backward compat):
  gemini-2.0-flash       — Deprecated on AI Studio, GA on Vertex only
  gemini-2.0-flash-lite  — Deprecated on AI Studio, GA on Vertex only
  gemini-exp-1206        — REMOVED by Google

MAP-ELITES Dimensions:
  D1 Intelligence: Lite → Flash → Pro → Deep Think
  D2 Cost:         $0.40/M → $2.50/M → $12/M output
  D3 Speed:        Budget bulk → Real-time → Deep reasoning
  D4 Capability:   Text → Multimodal → Agentic → Computer Use

Ultra Account Strategy ($100/mo Vertex credits):
  Bulk pass  (Flash-Lite): ~$18 for full 9,861-doc corpus
  Quality    (2.5 Flash):  ~$30 for targeted 3,000 docs
  Frontier   (3 Flash):    ~$35 for top 2,000 docs
  Deep       (3.1 Pro):    ~$14 for top 200 high-value docs

Medallion: bronze
Port: P1 BRIDGE (shared data fabric — model registry for all consumers)
Pointer key: gemini.models
"""

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path as _Path
from typing import Optional

# ── Auto-load .env from workspace root (before env reads) ──────
def _load_dotenv_once():
    """Find HFO_ROOT/.env and load it if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        for anchor in [_Path.cwd(), _Path(__file__).resolve().parent]:
            for candidate in [anchor] + list(anchor.parents):
                env_path = candidate / ".env"
                if env_path.exists() and (candidate / "AGENTS.md").exists():
                    load_dotenv(env_path, override=False)
                    return
    except ImportError:
        pass  # dotenv not installed — rely on shell env

_load_dotenv_once()

# =====================================================================
# Environment — single canonical env var name
# =====================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))

# ── Vertex AI Configuration (for Google Cloud credits) ─────────
# Google AI Pro = $10/mo credits, Ultra = $100/mo credits
# Credits ONLY work through Vertex AI, NOT direct AI Studio API.
# Setup: developers.google.com/program → claim → link GCP billing
VERTEX_AI_PROJECT = os.getenv("HFO_VERTEX_PROJECT", "")
VERTEX_AI_LOCATION = os.getenv("HFO_VERTEX_LOCATION", "global")  # global for Gemini 3.x models
VERTEX_AI_ENABLED = bool(VERTEX_AI_PROJECT)  # Auto-detect from env

# Rate limits upgrade to paid tier when Vertex AI is active
_PAID_RPM_MULTIPLIER = 100   # Free 10 → Paid 1000+ RPM
_PAID_RPD_UNLIMITED = 999999  # Effectively unlimited with billing


# =====================================================================
# Tier Enum
# =====================================================================

class GeminiTier(str, Enum):
    """Model tiers ordered by cost/capability (MAP-ELITES aligned)."""
    # Core tiers (T0-T5) — ordered by intelligence × cost
    BUDGET         = "budget"           # T0 — 2.5 Flash-Lite, cheapest, bulk
    FLASH          = "flash"            # T1 — 2.5 Flash, balanced workhorse
    FRONTIER_FLASH = "frontier_flash"   # T2 — 3 Flash, frontier at flash price
    PRO            = "pro"              # T3 — 2.5 Pro, GA stable reasoning
    FRONTIER_PRO   = "frontier_pro"     # T4 — 3 Pro, SOTA multimodal
    APEX           = "apex"             # T5 — 3.1 Pro, latest agentic + coding
    # Specialty
    COMPUTER_USE   = "computer_use"
    IMAGE_GEN      = "image_gen"
    IMAGE_PRO      = "image_pro"
    TTS_FLASH      = "tts_flash"
    TTS_PRO        = "tts_pro"
    AUDIO_FLASH    = "audio_flash"
    DEEP_RESEARCH  = "deep_research"
    EMBEDDING      = "embedding"
    # Legacy (deprecated — kept for backward compat)
    LEGACY_FLASH   = "legacy_flash"     # gemini-2.0-flash (deprecated)
    LEGACY_NANO    = "legacy_nano"      # gemini-2.0-flash-lite (deprecated)
    # Backward-compat aliases (old enum values → mapped internally)
    NANO           = "nano"             # ALIAS → BUDGET
    FLASH_25       = "flash_25"         # ALIAS → FLASH
    LITE_25        = "lite_25"          # ALIAS → BUDGET
    EXPERIMENTAL   = "experimental"     # ALIAS → APEX


# =====================================================================
# Model Spec
# =====================================================================

@dataclass(frozen=True)
class GeminiModelSpec:
    """Immutable spec for a single Gemini model."""
    model_id: str                    # API model identifier
    tier: GeminiTier                 # Which tier
    display_name: str                # Human-readable name
    input_tokens: int                # Max input context window
    output_tokens: int               # Max output tokens
    rpm_limit: int                   # Requests per minute (free tier)
    rpd_limit: int                   # Requests per day (free tier)
    # Pricing (paid tier, per 1M tokens in USD, ≤200k prompt)
    price_input: float = 0.0        # $/1M input tokens
    price_output: float = 0.0       # $/1M output tokens (incl thinking)
    price_input_long: float = 0.0   # $/1M input tokens (>200k prompt)
    price_output_long: float = 0.0  # $/1M output tokens (>200k prompt)
    # Capability flags
    supports_thinking: bool = False  # Has thinking/reasoning mode
    supports_grounding: bool = True  # Supports Google Search grounding
    supports_tools: bool = True      # Supports function calling
    supports_vision: bool = False    # Accepts image inputs
    supports_audio: bool = False     # Accepts audio inputs
    supports_video: bool = False     # Accepts video inputs
    supports_caching: bool = False   # Supports context caching
    supports_batch: bool = False     # Supports Batch API (50% discount)
    supports_computer_use: bool = False  # Computer use capability
    # Metadata
    status: str = "ga"               # "ga", "preview", "deprecated", "experimental"
    released: str = ""               # Release/update date
    knowledge_cutoff: str = ""       # Knowledge cutoff date
    use_cases: str = ""              # Recommended use cases
    notes: str = ""                  # Additional notes


# =====================================================================
# Model Registry — all known Gemini models
# =====================================================================

GEMINI_MODELS: dict[str, GeminiModelSpec] = {

    # ══════════════════════════════════════════════════════════════
    # T0 BUDGET — Cheapest, highest throughput, bulk enrichment
    # $0.10/$0.40 per 1M tokens — ~$18 for full 9,861-doc corpus
    # ══════════════════════════════════════════════════════════════
    "gemini-2.5-flash-lite": GeminiModelSpec(
        model_id="gemini-2.5-flash-lite",
        tier=GeminiTier.BUDGET,
        display_name="Gemini 2.5 Flash-Lite",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=10,
        rpd_limit=500,
        price_input=0.10,
        price_output=0.40,
        price_input_long=0.10,
        price_output_long=0.40,
        supports_thinking=True,
        supports_vision=True,
        supports_audio=True,
        supports_video=True,
        supports_caching=True,
        supports_batch=True,
        status="ga",
        released="2025-07",
        knowledge_cutoff="2025-01",
        use_cases="Bulk enrichment, classification, tagging, port assignment, BLUF generation",
        notes="Cheapest 2.5 model. Can do 5 full-corpus passes/month on Ultra budget. Thinking enabled.",
    ),

    # ══════════════════════════════════════════════════════════════
    # T1 FLASH — Best price-performance, workhorse reasoning
    # $0.30/$2.50 per 1M tokens — GA stable
    # ══════════════════════════════════════════════════════════════
    "gemini-2.5-flash": GeminiModelSpec(
        model_id="gemini-2.5-flash",
        tier=GeminiTier.FLASH,
        display_name="Gemini 2.5 Flash",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=10,
        rpd_limit=500,
        price_input=0.30,
        price_output=2.50,
        price_input_long=0.30,
        price_output_long=2.50,
        supports_thinking=True,
        supports_vision=True,
        supports_audio=True,
        supports_video=True,
        supports_caching=True,
        supports_batch=True,
        status="ga",
        released="2025-06",
        knowledge_cutoff="2025-01",
        use_cases="General analysis, code review, thinking tasks, quality enrichment",
        notes="Best price-performance. Stable GA. Thinking mode + 65K output. Maps grounding.",
    ),

    # ══════════════════════════════════════════════════════════════
    # T2 FRONTIER FLASH — Gemini 3 Flash, frontier at flash price
    # $0.50/$3.00 per 1M tokens — FREE TIER AVAILABLE!
    # ══════════════════════════════════════════════════════════════
    "gemini-3-flash-preview": GeminiModelSpec(
        model_id="gemini-3-flash-preview",
        tier=GeminiTier.FRONTIER_FLASH,
        display_name="Gemini 3 Flash",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=10,
        rpd_limit=500,
        price_input=0.50,
        price_output=3.00,
        price_input_long=0.50,
        price_output_long=3.00,
        supports_thinking=True,
        supports_vision=True,
        supports_audio=True,
        supports_video=True,
        supports_caching=True,
        supports_batch=True,
        supports_computer_use=True,
        status="preview",
        released="2025-12",
        knowledge_cutoff="2025-01",
        use_cases="Frontier agentic, vibe-coding, complex multimodal, near-zero thinking option",
        notes="SOTA Flash. Free tier available! Rivals larger models at fraction of cost. Computer use.",
    ),

    # ══════════════════════════════════════════════════════════════
    # T3 PRO — GA Stable reasoning, proven reliability
    # $1.25/$10.00 per 1M tokens — thinking + grounding
    # ══════════════════════════════════════════════════════════════
    "gemini-2.5-pro": GeminiModelSpec(
        model_id="gemini-2.5-pro",
        tier=GeminiTier.PRO,
        display_name="Gemini 2.5 Pro",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=25,
        price_input=1.25,
        price_output=10.00,
        price_input_long=2.50,
        price_output_long=15.00,
        supports_thinking=True,
        supports_vision=True,
        supports_audio=True,
        supports_video=True,
        supports_caching=True,
        supports_batch=True,
        status="ga",
        released="2025-06",
        knowledge_cutoff="2025-01",
        use_cases="Complex reasoning, architecture, proofs, math, deep analysis",
        notes="Stable GA Pro. #1 on LMArena for 6 months. Maps + Search grounding.",
    ),

    # ══════════════════════════════════════════════════════════════
    # T4 FRONTIER PRO — Gemini 3 Pro, SOTA multimodal reasoning
    # $2.00/$12.00 per 1M tokens — NO free tier
    # 1501 Elo, 91.9% GPQA Diamond, 37.5% HLE
    # ══════════════════════════════════════════════════════════════
    "gemini-3-pro-preview": GeminiModelSpec(
        model_id="gemini-3-pro-preview",
        tier=GeminiTier.FRONTIER_PRO,
        display_name="Gemini 3 Pro",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=25,
        price_input=2.00,
        price_output=12.00,
        price_input_long=4.00,
        price_output_long=18.00,
        supports_thinking=True,
        supports_vision=True,
        supports_audio=True,
        supports_video=True,
        supports_caching=True,
        supports_batch=True,
        status="preview",
        released="2025-11",
        knowledge_cutoff="2025-01",
        use_cases="SOTA reasoning, PhD-level problems, multimodal, Deep Think mode",
        notes="1501 Elo LMArena. 91.9% GPQA-D. Deep Think: 41% HLE, 93.8% GPQA-D, 45.1% ARC-AGI-2.",
    ),

    # ══════════════════════════════════════════════════════════════
    # T5 APEX — Gemini 3.1 Pro, latest and most capable
    # $2.00/$12.00 per 1M tokens — NO free tier
    # Feb 2026: improved thinking, token efficiency, agentic
    # ══════════════════════════════════════════════════════════════
    "gemini-3.1-pro-preview": GeminiModelSpec(
        model_id="gemini-3.1-pro-preview",
        tier=GeminiTier.APEX,
        display_name="Gemini 3.1 Pro",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=25,
        price_input=2.00,
        price_output=12.00,
        price_input_long=4.00,
        price_output_long=18.00,
        supports_thinking=True,
        supports_vision=True,
        supports_audio=True,
        supports_video=True,
        supports_caching=True,
        supports_batch=True,
        status="preview",
        released="2026-02",
        knowledge_cutoff="2025-01",
        use_cases="Agentic workflows, vibe-coding, multi-step execution, custom tools",
        notes="Latest. Better thinking, token efficiency, factual consistency. Has -customtools variant.",
    ),

    # Also register the custom-tools variant
    "gemini-3.1-pro-preview-customtools": GeminiModelSpec(
        model_id="gemini-3.1-pro-preview-customtools",
        tier=GeminiTier.APEX,
        display_name="Gemini 3.1 Pro (Custom Tools)",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=25,
        price_input=2.00,
        price_output=12.00,
        price_input_long=4.00,
        price_output_long=18.00,
        supports_thinking=True,
        supports_vision=True,
        supports_audio=True,
        supports_video=True,
        supports_caching=True,
        supports_batch=True,
        status="preview",
        released="2026-02",
        knowledge_cutoff="2025-01",
        use_cases="Agentic workflows with custom tool + bash priority",
        notes="Optimized for custom tools over built-in. Use when mixing bash + MCP tools.",
    ),

    # ══════════════════════════════════════════════════════════════
    # SPECIALTY MODELS
    # ══════════════════════════════════════════════════════════════

    "gemini-2.5-computer-use-preview-10-2025": GeminiModelSpec(
        model_id="gemini-2.5-computer-use-preview-10-2025",
        tier=GeminiTier.COMPUTER_USE,
        display_name="Gemini 2.5 Computer Use",
        input_tokens=131_072,
        output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=25,
        price_input=1.25,
        price_output=10.00,
        supports_vision=True,
        status="preview",
        released="2025-10",
        use_cases="GUI automation, screen understanding, browser tasks",
        notes="Preview — computer use agent. Vision-only input.",
    ),

    "gemini-2.5-flash-image": GeminiModelSpec(
        model_id="gemini-2.5-flash-image",
        tier=GeminiTier.IMAGE_GEN,
        display_name="Nano Banana (2.5 Flash Image)",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=10,
        rpd_limit=500,
        price_input=0.30,
        price_output=0.039,  # per image (via token pricing)
        supports_vision=True,
        supports_batch=True,
        status="ga",
        released="2025-06",
        use_cases="Image generation, conversational editing, creative workflows",
        notes="Nano Banana. $0.039/image output. Same text pricing as 2.5 Flash.",
    ),

    "gemini-3-pro-image-preview": GeminiModelSpec(
        model_id="gemini-3-pro-image-preview",
        tier=GeminiTier.IMAGE_PRO,
        display_name="Nano Banana Pro (3 Pro Image)",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=25,
        price_input=2.00,
        price_output=0.134,  # per image at 1K-2K, $0.24 at 4K
        supports_vision=True,
        supports_batch=True,
        status="preview",
        released="2025-12",
        use_cases="4K image gen, reasoning-enhanced composition, legible text, studio quality",
        notes="Nano Banana Pro. 14 reference inputs. $0.134/image 1K-2K, $0.24/4K.",
    ),

    "gemini-2.5-flash-preview-tts": GeminiModelSpec(
        model_id="gemini-2.5-flash-preview-tts",
        tier=GeminiTier.TTS_FLASH,
        display_name="Gemini 2.5 Flash TTS",
        input_tokens=8_192,
        output_tokens=16_384,
        rpm_limit=10,
        rpd_limit=500,
        price_input=0.50,
        price_output=10.00,  # audio output
        supports_audio=True,
        supports_batch=True,
        status="preview",
        use_cases="Text-to-speech, controllable speech, real-time assistants",
        notes="TTS preview — Flash quality. $0.50 text in, $10/M audio out.",
    ),

    "gemini-2.5-pro-preview-tts": GeminiModelSpec(
        model_id="gemini-2.5-pro-preview-tts",
        tier=GeminiTier.TTS_PRO,
        display_name="Gemini 2.5 Pro TTS",
        input_tokens=8_192,
        output_tokens=16_384,
        rpm_limit=2,
        rpd_limit=25,
        price_input=0.50,
        price_output=10.00,  # audio output
        supports_audio=True,
        supports_batch=True,
        status="preview",
        use_cases="High-fidelity speech, podcasts, audiobooks",
        notes="TTS preview — Pro quality. Best for structured audio workflows.",
    ),

    "gemini-2.5-flash-native-audio-preview-12-2025": GeminiModelSpec(
        model_id="gemini-2.5-flash-native-audio-preview-12-2025",
        tier=GeminiTier.AUDIO_FLASH,
        display_name="Gemini 2.5 Flash Live Audio",
        input_tokens=131_072,
        output_tokens=8_192,
        rpm_limit=10,
        rpd_limit=500,
        price_input=0.50,  # text; $3.00 audio/video
        price_output=2.00,  # text; $12.00 audio
        supports_audio=True,
        status="preview",
        released="2025-12",
        use_cases="Live API, bidirectional streaming, native audio reasoning, voice agents",
        notes="Native audio model. Sub-second latency. Affective dialogue.",
    ),

    "deep-research-pro-preview-12-2025": GeminiModelSpec(
        model_id="deep-research-pro-preview-12-2025",
        tier=GeminiTier.DEEP_RESEARCH,
        display_name="Gemini Deep Research",
        input_tokens=1_048_576,
        output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=25,
        price_input=2.00,
        price_output=12.00,
        supports_grounding=True,
        status="preview",
        released="2025-12",
        use_cases="Multi-step research across hundreds of sources, cited reports",
        notes="Agentic research model. Autonomously plans + executes research.",
    ),

    "gemini-embedding-001": GeminiModelSpec(
        model_id="gemini-embedding-001",
        tier=GeminiTier.EMBEDDING,
        display_name="Gemini Embeddings",
        input_tokens=8_192,
        output_tokens=0,
        rpm_limit=100,
        rpd_limit=10000,
        price_input=0.00,  # Free!
        price_output=0.00,
        supports_thinking=False,
        supports_grounding=False,
        supports_tools=False,
        status="ga",
        use_cases="Semantic search, text classification, clustering, RAG",
        notes="High-dimensional vector embeddings. FREE!",
    ),

    # ══════════════════════════════════════════════════════════════
    # LEGACY (DEPRECATED) — Kept for backward compat only
    # ══════════════════════════════════════════════════════════════

    "gemini-2.0-flash": GeminiModelSpec(
        model_id="gemini-2.0-flash",
        tier=GeminiTier.LEGACY_FLASH,
        display_name="Gemini 2.0 Flash [DEPRECATED]",
        input_tokens=1_048_576,
        output_tokens=8_192,
        rpm_limit=15,
        rpd_limit=1500,
        price_input=0.10,
        price_output=0.40,
        supports_vision=True,
        status="deprecated",
        use_cases="DEPRECATED — migrate to gemini-2.5-flash or gemini-3-flash-preview",
        notes="Deprecated on AI Studio. Still GA on Vertex. Migrate to 2.5+.",
    ),

    "gemini-2.0-flash-lite": GeminiModelSpec(
        model_id="gemini-2.0-flash-lite",
        tier=GeminiTier.LEGACY_NANO,
        display_name="Gemini 2.0 Flash Lite [DEPRECATED]",
        input_tokens=1_048_576,
        output_tokens=8_192,
        rpm_limit=30,
        rpd_limit=1500,
        price_input=0.075,
        price_output=0.30,
        status="deprecated",
        use_cases="DEPRECATED — migrate to gemini-2.5-flash-lite",
        notes="Deprecated on AI Studio. Still GA on Vertex. Migrate to 2.5-flash-lite.",
    ),
}


# =====================================================================
# Tier-based lookups
# =====================================================================

def get_model(tier_or_id: str) -> GeminiModelSpec:
    """
    Get a model spec by tier name or model ID.
    
    Args:
        tier_or_id: One of:
            - Tier name: "nano", "flash", "flash_25", "lite_25", "pro", "experimental"
            - Model ID: "gemini-2.5-pro", "gemini-2.0-flash-lite", etc.
            - Legacy aliases: "flash" resolves to flash_25 (best flash), 
              "lite" resolves to nano
    
    Returns:
        GeminiModelSpec for the requested model
    
    Raises:
        KeyError if model/tier not found
    """
    # Legacy alias mapping (for backward compat with MCP server)
    ALIASES = {
        "lite": "budget",
        "fast": "flash",
        "think": "apex",
        "deep": "frontier_pro",
        "best": "apex",
        "cheap": "budget",
        "quick": "budget",
        # Old tier names → new tier names
        "nano": "budget",
        "flash_25": "flash",
        "lite_25": "budget",
        "experimental": "apex",
        # Gemini 3 shortcuts
        "g3": "frontier_flash",
        "g3flash": "frontier_flash",
        "g3pro": "frontier_pro",
        "g31": "apex",
        "g31pro": "apex",
        "frontier": "frontier_pro",
    }
    
    key = tier_or_id.lower().strip()
    
    # Direct model ID match
    if key in GEMINI_MODELS:
        return GEMINI_MODELS[key]
    
    # Check aliases
    if key in ALIASES:
        key = ALIASES[key]
    
    # Tier name match — return the primary model for that tier
    TIER_DEFAULTS = {
        "budget": "gemini-2.5-flash-lite",
        "flash": "gemini-2.5-flash",
        "frontier_flash": "gemini-3-flash-preview",
        "pro": "gemini-2.5-pro",
        "frontier_pro": "gemini-3-pro-preview",
        "apex": "gemini-3.1-pro-preview",
        "computer_use": "gemini-2.5-computer-use-preview-10-2025",
        "image_gen": "gemini-2.5-flash-image",
        "image_pro": "gemini-3-pro-image-preview",
        "tts_flash": "gemini-2.5-flash-preview-tts",
        "tts_pro": "gemini-2.5-pro-preview-tts",
        "audio_flash": "gemini-2.5-flash-native-audio-preview-12-2025",
        "deep_research": "deep-research-pro-preview-12-2025",
        "embedding": "gemini-embedding-001",
        # Legacy tiers
        "legacy_flash": "gemini-2.0-flash",
        "legacy_nano": "gemini-2.0-flash-lite",
    }
    
    if key in TIER_DEFAULTS:
        return GEMINI_MODELS[TIER_DEFAULTS[key]]
    
    raise KeyError(
        f"Unknown model or tier: '{tier_or_id}'. "
        f"Valid tiers: {list(TIER_DEFAULTS.keys())}. "
        f"Valid models: {list(GEMINI_MODELS.keys())}"
    )


def get_models_by_tier(tier: GeminiTier) -> list[GeminiModelSpec]:
    """Get all models in a given tier."""
    return [m for m in GEMINI_MODELS.values() if m.tier == tier]


def get_thinking_models() -> list[GeminiModelSpec]:
    """Get all models that support thinking/reasoning mode."""
    return [m for m in GEMINI_MODELS.values() if m.supports_thinking]


def get_core_tiers() -> list[GeminiModelSpec]:
    """Get the 6 core tier models (T0-T5), excluding specialty."""
    core = [GeminiTier.BUDGET, GeminiTier.FLASH, GeminiTier.FRONTIER_FLASH,
            GeminiTier.PRO, GeminiTier.FRONTIER_PRO, GeminiTier.APEX]
    return [get_model(t.value) for t in core]


def list_all_models() -> list[dict]:
    """Return all models as a list of dicts (for MCP tool output)."""
    result = []
    for spec in GEMINI_MODELS.values():
        result.append({
            "model_id": spec.model_id,
            "tier": spec.tier.value,
            "display_name": spec.display_name,
            "input_tokens": spec.input_tokens,
            "output_tokens": spec.output_tokens,
            "rpm_limit": spec.rpm_limit,
            "rpd_limit": spec.rpd_limit,
            "supports_thinking": spec.supports_thinking,
            "supports_grounding": spec.supports_grounding,
            "supports_vision": spec.supports_vision,
            "use_cases": spec.use_cases,
        })
    return result


# =====================================================================
# Rate Limit Tracker
# =====================================================================

class GeminiRateLimiter:
    """
    Per-model rate limit tracker.
    Tracks RPM and RPD for each model independently.
    Thread-safe for single-process async use.
    """
    
    def __init__(self):
        self._minute_counts: dict[str, list[float]] = {}  # model_id -> list of timestamps
        self._day_counts: dict[str, int] = {}              # model_id -> count today
        self._day_start: float = time.time()
    
    def _cleanup_minute(self, model_id: str):
        """Remove timestamps older than 60 seconds."""
        now = time.time()
        if model_id in self._minute_counts:
            self._minute_counts[model_id] = [
                t for t in self._minute_counts[model_id] if now - t < 60
            ]
    
    def _reset_day_if_needed(self):
        """Reset daily counts if 24 hours have passed."""
        if time.time() - self._day_start > 86400:
            self._day_counts.clear()
            self._day_start = time.time()
    
    def check(self, model_id: str) -> tuple[bool, str]:
        """
        Check if a request to this model is allowed.
        
        Returns:
            (allowed: bool, reason: str)
        """
        spec = GEMINI_MODELS.get(model_id)
        if not spec:
            return False, f"Unknown model: {model_id}"
        
        self._reset_day_if_needed()
        self._cleanup_minute(model_id)
        
        # Check RPD
        day_count = self._day_counts.get(model_id, 0)
        if day_count >= spec.rpd_limit:
            return False, f"{spec.display_name} daily limit reached ({day_count}/{spec.rpd_limit} RPD)"
        
        # Check RPM
        minute_count = len(self._minute_counts.get(model_id, []))
        if minute_count >= spec.rpm_limit:
            return False, f"{spec.display_name} per-minute limit reached ({minute_count}/{spec.rpm_limit} RPM)"
        
        return True, "OK"
    
    def record(self, model_id: str):
        """Record a successful API call."""
        now = time.time()
        if model_id not in self._minute_counts:
            self._minute_counts[model_id] = []
        self._minute_counts[model_id].append(now)
        self._day_counts[model_id] = self._day_counts.get(model_id, 0) + 1
    
    def wait_time(self, model_id: str) -> float:
        """
        How long to wait before the next request is allowed (seconds).
        Returns 0.0 if allowed now.
        """
        allowed, _ = self.check(model_id)
        if allowed:
            return 0.0
        
        spec = GEMINI_MODELS.get(model_id)
        if not spec:
            return 60.0
        
        # Check if it's a daily limit issue
        day_count = self._day_counts.get(model_id, 0)
        if day_count >= spec.rpd_limit:
            return 86400 - (time.time() - self._day_start)
        
        # It's a per-minute issue — wait for oldest to expire
        self._cleanup_minute(model_id)
        timestamps = self._minute_counts.get(model_id, [])
        if timestamps and len(timestamps) >= spec.rpm_limit:
            oldest = min(timestamps)
            return max(0.0, 60.0 - (time.time() - oldest))
        
        return 0.0
    
    def usage_summary(self) -> dict:
        """Get current usage stats for all tracked models."""
        self._reset_day_if_needed()
        summary = {}
        for model_id, spec in GEMINI_MODELS.items():
            day_used = self._day_counts.get(model_id, 0)
            self._cleanup_minute(model_id)
            min_used = len(self._minute_counts.get(model_id, []))
            if day_used > 0 or min_used > 0:
                summary[model_id] = {
                    "display_name": spec.display_name,
                    "tier": spec.tier.value,
                    "rpm_used": min_used,
                    "rpm_limit": spec.rpm_limit,
                    "rpd_used": day_used,
                    "rpd_limit": spec.rpd_limit,
                    "rpd_remaining": spec.rpd_limit - day_used,
                }
        return summary


# =====================================================================
# Smart Tier Router
# =====================================================================

def select_tier(
    task_complexity: str = "medium",
    needs_thinking: bool = False,
    needs_grounding: bool = False,
    is_batch: bool = False,
    rate_limiter: Optional[GeminiRateLimiter] = None,
) -> GeminiModelSpec:
    """
    Automatically select the best model tier for a given task profile.
    
    Args:
        task_complexity: "trivial", "low", "medium", "high", "extreme"
        needs_thinking: Requires extended reasoning / thinking mode
        needs_grounding: Requires Google Search grounding
        is_batch: Is this a batch/bulk operation (prefer cheap)
        rate_limiter: If provided, will fallback to lower tiers if limit hit
    
    Returns:
        Best available GeminiModelSpec
    """
    # Complexity -> preferred tier mapping
    COMPLEXITY_MAP = {
        "trivial": "budget",
        "low": "flash",
        "medium": "frontier_flash",
        "high": "frontier_pro",
        "extreme": "apex",
    }
    
    preferred = COMPLEXITY_MAP.get(task_complexity, "frontier_flash")
    
    # Override for thinking requirement
    if needs_thinking:
        if preferred in ("budget",):
            preferred = "flash"  # Minimum thinking-capable tier (all 2.5+ support it)
    
    # Override for batch — prefer cheaper
    if is_batch and preferred not in ("frontier_pro", "apex"):
        if preferred == "frontier_flash":
            preferred = "flash"
        elif preferred == "flash":
            preferred = "budget"
    
    # Fallback chain for rate limits
    FALLBACK_CHAIN = ["apex", "frontier_pro", "pro", "frontier_flash", "flash", "budget"]
    
    # Try preferred first
    model = get_model(preferred)
    
    if rate_limiter:
        allowed, _ = rate_limiter.check(model.model_id)
        if not allowed:
            # Walk fallback chain from preferred's position downward
            try:
                start_idx = FALLBACK_CHAIN.index(preferred)
            except ValueError:
                start_idx = 0
            
            for fallback_tier in FALLBACK_CHAIN[start_idx + 1:]:
                fallback_model = get_model(fallback_tier)
                allowed, _ = rate_limiter.check(fallback_model.model_id)
                if allowed:
                    return fallback_model
            
            # Everything exhausted — return preferred anyway (caller handles limit)
            return model
    
    return model


# =====================================================================
# Swarm Role -> Model Mapping
# =====================================================================

# Role-based model selection for swarm agents
# Maps agent roles to their preferred Gemini tier
SWARM_ROLE_MAP: dict[str, str] = {
    # High-volume roles use budget tier
    "triage": "budget",
    "router": "budget",
    "classifier": "budget",
    "tagger": "budget",
    
    # General work roles use flash tiers
    "researcher": "frontier_flash",
    "executor": "frontier_flash",
    "coder": "frontier_flash",
    "analyst": "flash",
    
    # Critical decision roles use pro tiers
    "planner": "frontier_pro",
    "validator": "frontier_pro",
    "architect": "apex",
    "reviewer": "pro",
    
    # Background enrichment uses budget/flash
    "enricher": "budget",
    "cataloger": "budget",
    "summarizer": "flash",
    "patrol": "budget",
}


def get_model_for_role(role: str) -> GeminiModelSpec:
    """Get the recommended Gemini model for a swarm agent role."""
    tier = SWARM_ROLE_MAP.get(role.lower(), "frontier_flash")
    return get_model(tier)


# =====================================================================
# MAP-ELITES Grid — Quality-Diversity Model Selection
# =====================================================================
# MAP-ELITES: Multi-dimensional Archive of Phenotypic Elites
# Each cell is the "elite" (best model) for that behavioral niche.
#
# Dimensions:
#   D1 (rows) — Task Intelligence Level: bulk, general, complex, frontier
#   D2 (cols) — Cost Constraint: free, budget(<$20/pass), standard(<$50), premium
#
# Usage: map_elite_select("complex", "budget") → gemini-2.5-pro
# =====================================================================

# Niche → model_id mapping
_MAP_ELITES_GRID: dict[tuple[str, str], str] = {
    # (intelligence_level, cost_constraint) → model_id
    
    #                        FREE                    BUDGET               STANDARD              PREMIUM
    ("bulk", "free"):        "gemini-2.5-flash-lite",
    ("bulk", "budget"):      "gemini-2.5-flash-lite",
    ("bulk", "standard"):    "gemini-2.5-flash-lite",
    ("bulk", "premium"):     "gemini-2.5-flash",       # overpay for reliability
    
    ("general", "free"):     "gemini-2.5-flash",
    ("general", "budget"):   "gemini-2.5-flash",
    ("general", "standard"): "gemini-3-flash-preview",
    ("general", "premium"):  "gemini-3-flash-preview",
    
    ("complex", "free"):     "gemini-2.5-pro",          # free tier available!
    ("complex", "budget"):   "gemini-3-flash-preview",  # better per-$ than pro
    ("complex", "standard"): "gemini-2.5-pro",
    ("complex", "premium"):  "gemini-3-pro-preview",
    
    ("frontier", "free"):    "gemini-3-flash-preview",  # free tier, frontier flash
    ("frontier", "budget"):  "gemini-3-flash-preview",
    ("frontier", "standard"):"gemini-3-pro-preview",
    ("frontier", "premium"): "gemini-3.1-pro-preview",
}


def map_elite_select(
    intelligence: str = "general",
    cost: str = "budget",
    rate_limiter: Optional[GeminiRateLimiter] = None,
) -> GeminiModelSpec:
    """
    MAP-ELITES model selection — pick the elite for your niche.
    
    Args:
        intelligence: "bulk", "general", "complex", "frontier"
        cost: "free", "budget", "standard", "premium"
        rate_limiter: Optional — falls back along cost axis if rate limited
    
    Returns:
        The elite GeminiModelSpec for the requested niche
    """
    key = (intelligence.lower(), cost.lower())
    model_id = _MAP_ELITES_GRID.get(key)
    
    if model_id is None:
        # Default fallback
        model_id = _MAP_ELITES_GRID.get(("general", "budget"), "gemini-2.5-flash")
    
    model = GEMINI_MODELS[model_id]
    
    # Rate limit fallback: try cheaper cost levels
    if rate_limiter:
        allowed, _ = rate_limiter.check(model.model_id)
        if not allowed:
            cost_chain = ["premium", "standard", "budget", "free"]
            try:
                idx = cost_chain.index(cost.lower())
            except ValueError:
                idx = 0
            for fallback_cost in cost_chain[idx + 1:]:
                fb_key = (intelligence.lower(), fallback_cost)
                fb_id = _MAP_ELITES_GRID.get(fb_key)
                if fb_id:
                    fb_model = GEMINI_MODELS[fb_id]
                    allowed, _ = rate_limiter.check(fb_model.model_id)
                    if allowed:
                        return fb_model
    
    return model


def map_elite_grid() -> str:
    """Return a formatted MAP-ELITES grid string for display."""
    lines = []
    header = f"  {'Intelligence':<12s} | {'FREE':<28s} | {'BUDGET':<28s} | {'STANDARD':<28s} | {'PREMIUM':<28s}"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    
    for intel in ["bulk", "general", "complex", "frontier"]:
        row = f"  {intel:<12s}"
        for cost in ["free", "budget", "standard", "premium"]:
            model_id = _MAP_ELITES_GRID.get((intel, cost), "?")
            # Shorten display
            short = model_id.replace("gemini-", "").replace("-preview", "⚡")
            row += f" | {short:<28s}"
        lines.append(row)
    
    return "\n".join(lines)


def estimate_corpus_cost(
    num_docs: int = 9861,
    avg_input_tokens: int = 2000,
    avg_output_tokens: int = 4000,
    model_id: str = "gemini-2.5-flash-lite",
) -> dict:
    """
    Estimate cost for processing a document corpus.
    
    Returns dict with cost breakdown and budget analysis.
    """
    spec = GEMINI_MODELS.get(model_id)
    if not spec:
        return {"error": f"Unknown model: {model_id}"}
    
    total_input_tokens = num_docs * avg_input_tokens
    total_output_tokens = num_docs * avg_output_tokens
    
    input_cost = (total_input_tokens / 1_000_000) * spec.price_input
    output_cost = (total_output_tokens / 1_000_000) * spec.price_output
    total_cost = input_cost + output_cost
    
    passes_per_month = int(100 / total_cost) if total_cost > 0 else 999
    
    return {
        "model": spec.display_name,
        "model_id": model_id,
        "tier": spec.tier.value,
        "num_docs": num_docs,
        "total_input_M": round(total_input_tokens / 1_000_000, 2),
        "total_output_M": round(total_output_tokens / 1_000_000, 2),
        "input_cost": round(input_cost, 2),
        "output_cost": round(output_cost, 2),
        "total_cost_per_pass": round(total_cost, 2),
        "passes_per_100_budget": passes_per_month,
        "monthly_budget_used_pct": round(total_cost, 1),
    }


# =====================================================================
# CLI
# =====================================================================

def _cli():
    """Print model registry to stdout."""
    print("=" * 80)
    print("  HFO Gen90 — Gemini Model Registry (Updated 2026-02-20)")
    print("=" * 80)
    print(f"\n  API Key: {'SET' if GEMINI_API_KEY else 'NOT SET'}")
    print(f"  Vertex AI: {'ENABLED (' + VERTEX_AI_PROJECT + ')' if VERTEX_AI_ENABLED else 'DISABLED'}")
    print(f"  Total models: {len(GEMINI_MODELS)}")
    
    print("\n  Core Tiers (T0-T5) — MAP-ELITES Architecture:")
    print(f"  {'Tier':<16s} {'Model ID':<38s} {'$/M In':>7s} {'$/M Out':>8s} {'Think':>6s} {'Status':>8s}")
    print("  " + "-" * 85)
    for spec in get_core_tiers():
        think = "YES" if spec.supports_thinking else ""
        print(f"  {spec.tier.value:<16s} {spec.model_id:<38s} "
              f"${spec.price_input:>5.2f} ${spec.price_output:>6.2f} "
              f"{think:>6s} {spec.status:>8s}")
    
    print("\n  Specialty Models:")
    core_tiers = {GeminiTier.BUDGET, GeminiTier.FLASH, GeminiTier.FRONTIER_FLASH,
                  GeminiTier.PRO, GeminiTier.FRONTIER_PRO, GeminiTier.APEX,
                  GeminiTier.LEGACY_FLASH, GeminiTier.LEGACY_NANO,
                  GeminiTier.NANO, GeminiTier.FLASH_25, GeminiTier.LITE_25,
                  GeminiTier.EXPERIMENTAL}
    specialty = [m for m in GEMINI_MODELS.values() if m.tier not in core_tiers]
    for spec in specialty:
        print(f"    {spec.tier.value:<16s} {spec.model_id}")
    
    print("\n  Deprecated (backward compat only):")
    for spec in GEMINI_MODELS.values():
        if spec.status == "deprecated":
            print(f"    ⚠ {spec.model_id} → migrate to {spec.use_cases.split('migrate to ')[-1] if 'migrate to' in spec.use_cases else 'newer model'}")
    
    print("\n  Thinking-capable models:")
    for spec in get_thinking_models():
        print(f"    {spec.model_id} ({spec.tier.value}) ${spec.price_output:.2f}/M out")
    
    # MAP-ELITES grid
    print("\n  " + "=" * 80)
    print("  MAP-ELITES Grid — Quality × Cost × Capability")
    print("  " + "=" * 80)
    print(map_elite_grid())
    
    print("\n  Ultra Budget Planner ($100/mo):")
    print("  " + "-" * 50)
    print("    Full corpus (9,861 docs, ~2K in + 4K out avg):")
    for spec in get_core_tiers():
        in_cost = 19.7 * spec.price_input / 1.0  # 19.7M tokens
        out_cost = 39.4 * spec.price_output / 1.0  # 39.4M tokens
        total = in_cost + out_cost
        passes = int(100 / total) if total > 0 else 999
        print(f"    {spec.display_name:<30s} ${total:>7.2f}/pass  ({passes} passes/mo)")
    
    print("\n  Swarm Role Mapping:")
    for role, tier in sorted(SWARM_ROLE_MAP.items()):
        model = get_model(tier)
        print(f"    {role:<14s} -> {tier:<18s} ({model.model_id})")
    
    print()


if __name__ == "__main__":
    _cli()


# =====================================================================
# Dual-Mode Client Factory — AI Studio or Vertex AI
# =====================================================================

def create_gemini_client():
    """
    Create a google-genai Client with automatic mode detection.

    Priority:
      1. VERTEX AI (if HFO_VERTEX_PROJECT is set) → Uses Cloud credits
         - AI Pro: $10/mo credits, AI Ultra: $100/mo credits
         - Requires: gcloud auth application-default login
      2. AI STUDIO (if GEMINI_API_KEY is set) → Free tier or pay-as-you-go
         - Free: rate limited (25 RPD Pro, 500 RPD Flash)
         - Paid: enable billing at aistudio.google.com/billing

    Returns:
        tuple: (client, mode_str) where mode_str is "vertex" or "aistudio"

    Raises:
        RuntimeError: If neither Vertex AI nor API key is configured
    """
    try:
        from google import genai
    except ImportError:
        raise RuntimeError(
            "google-genai package not installed. Run: pip install google-genai"
        )

    if VERTEX_AI_ENABLED:
        # Vertex AI mode — uses Application Default Credentials
        # Cloud credits are applied automatically when billed through Vertex
        client = genai.Client(
            vertexai=True,
            project=VERTEX_AI_PROJECT,
            location=VERTEX_AI_LOCATION,
        )
        return client, "vertex"

    if GEMINI_API_KEY:
        # AI Studio mode — direct API key
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client, "aistudio"

    raise RuntimeError(
        "No Gemini credentials configured.\n"
        "Option A (recommended — uses your Ultra $100/mo credits):\n"
        "  1. Go to developers.google.com/program → Claim premium benefits\n"
        "  2. Run: gcloud auth application-default login\n"
        "  3. Set HFO_VERTEX_PROJECT=your-gcp-project-id in .env\n\n"
        "Option B (free tier):\n"
        "  1. Go to aistudio.google.com/apikey → Create key\n"
        "  2. Set GEMINI_API_KEY=your-key in .env"
    )


def get_effective_limits(model_id: str) -> tuple[int, int]:
    """
    Get effective RPM/RPD limits based on billing mode.

    Returns:
        tuple: (rpm_limit, rpd_limit) — upgraded if Vertex AI is active
    """
    spec = GEMINI_MODELS.get(model_id)
    if spec is None:
        return 10, 500  # Safe defaults

    if VERTEX_AI_ENABLED:
        # Vertex AI paid tier — much higher limits
        return spec.rpm_limit * _PAID_RPM_MULTIPLIER, _PAID_RPD_UNLIMITED

    return spec.rpm_limit, spec.rpd_limit
