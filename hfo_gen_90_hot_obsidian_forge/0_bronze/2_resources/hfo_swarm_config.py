"""
HFO Gen90 — Multi-Provider Swarm Configuration
================================================
Central config for the swarm: local Ollama + cloud Gemini.
Role-based model selection picks the best provider per task.

Pointer key: swarm.config
Medallion: bronze
"""

import os
import sys
from pathlib import Path
from enum import Enum
from typing import Optional

# ── Provider Enum ──────────────────────────────────────────────

class Provider(Enum):
    """Available inference providers."""
    OLLAMA = "ollama"      # Local GPU — free, unlimited, latency-bound
    GEMINI = "gemini"      # Cloud API — rate-limited, grounded search, thinking


# ── Ollama Server ──────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_API_BASE = f"{OLLAMA_HOST}/v1"

# ── Default Models (per provider) ─────────────────────────────
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
DEFAULT_GEMINI_TIER = os.getenv("GEMINI_DEFAULT_TIER", "flash_25")

# Backward-compat alias
DEFAULT_MODEL = DEFAULT_OLLAMA_MODEL

# ── Gemini Registry (import from centralized model registry) ──
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from hfo_gemini_models import (
        GEMINI_API_KEY,
        GEMINI_MODELS,
        GeminiRateLimiter,
        GeminiTier,
        get_model as gemini_get_model,
        select_tier as gemini_select_tier,
        list_all_models as gemini_list_all,
        SWARM_ROLE_MAP as GEMINI_ROLE_MAP,
    )
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
except ImportError:
    GEMINI_AVAILABLE = False
    GEMINI_API_KEY = ""
    GEMINI_MODELS = {}
    GEMINI_ROLE_MAP = {}

# ── Ollama Recommended Models ─────────────────────────────────
OLLAMA_RECOMMENDED_MODELS = {
    # Small & fast — good for routing, triage, tool-calling
    "qwen2.5:3b":       {"size_gb": 1.8,  "use": "routing, triage, fast tasks"},
    # Medium — good balance of quality and speed
    "qwen2.5:7b":       {"size_gb": 4.4,  "use": "general purpose, coding"},
    "llama3.1:8b":      {"size_gb": 4.7,  "use": "general purpose, reasoning"},
    "gemma3:12b":       {"size_gb": 7.6,  "use": "general purpose, multilingual"},
    "mistral:7b":       {"size_gb": 4.1,  "use": "general purpose, fast"},
    # Large — best quality, needs more RAM
    "qwen2.5:14b":      {"size_gb": 9.0,  "use": "complex reasoning, coding"},
    "deepseek-r1:14b":  {"size_gb": 9.0,  "use": "deep reasoning, chain-of-thought"},
    "llama3.1:70b":     {"size_gb": 40.0, "use": "best quality (needs 48GB+ RAM)"},
    # Coding specialists
    "qwen2.5-coder:7b": {"size_gb": 4.4,  "use": "code generation, review"},
    # Vision
    "llava:7b":         {"size_gb": 4.5,  "use": "multimodal, image understanding"},
}

# Backward-compat alias
RECOMMENDED_MODELS = OLLAMA_RECOMMENDED_MODELS

# ── Gemini Recommended Tiers ──────────────────────────────────
GEMINI_RECOMMENDED_TIERS = {
    "nano":         {"use": "batch enrichment, triage, summaries (30 RPM)"},
    "flash":        {"use": "general chat, fast tasks (15 RPM)"},
    "flash_25":     {"use": "balanced quality+speed, thinking capable (10 RPM)"},
    "lite_25":      {"use": "background enrichment, light thinking (10 RPM)"},
    "pro":          {"use": "deep reasoning, complex analysis (2 RPM)"},
    "experimental": {"use": "bleeding edge, research (2 RPM)"},
}

# ── Role → Provider+Model Mapping ─────────────────────────────

# Maps swarm roles to (provider, model_or_tier) with fallback
ROLE_MODEL_MAP = {
    # Role:           (preferred_provider, preferred_model,      fallback_provider, fallback_model)
    "triage":         (Provider.OLLAMA, "qwen2.5:3b",           Provider.GEMINI, "nano"),
    "router":         (Provider.OLLAMA, "qwen2.5:3b",           Provider.GEMINI, "nano"),
    "researcher":     (Provider.GEMINI, "flash_25",             Provider.OLLAMA, "qwen2.5:7b"),
    "coder":          (Provider.GEMINI, "flash_25",             Provider.OLLAMA, "qwen2.5-coder:7b"),
    "analyst":        (Provider.GEMINI, "flash_25",             Provider.OLLAMA, "llama3.1:8b"),
    "planner":        (Provider.GEMINI, "pro",                  Provider.OLLAMA, "deepseek-r1:14b"),
    "validator":      (Provider.GEMINI, "pro",                  Provider.OLLAMA, "qwen2.5:14b"),
    "enricher":       (Provider.GEMINI, "lite_25",              Provider.OLLAMA, "qwen2.5:3b"),
    "summarizer":     (Provider.GEMINI, "nano",                 Provider.OLLAMA, "qwen2.5:3b"),
    "web_searcher":   (Provider.GEMINI, "flash_25",             Provider.OLLAMA, "llama3.1:8b"),
    "deep_thinker":   (Provider.GEMINI, "pro",                  Provider.OLLAMA, "deepseek-r1:14b"),
    "batch_worker":   (Provider.GEMINI, "nano",                 Provider.OLLAMA, "qwen2.5:3b"),
    "vision":         (Provider.GEMINI, "flash_25",             Provider.OLLAMA, "llava:7b"),
}

# ── Swarm Settings ─────────────────────────────────────────────
MAX_TURNS = int(os.getenv("SWARM_MAX_TURNS", "30"))
TEMPERATURE = float(os.getenv("SWARM_TEMPERATURE", "0.7"))
STREAM = os.getenv("SWARM_STREAM", "true").lower() == "true"

# Provider preference: "gemini_first", "ollama_first", "ollama_only", "gemini_only"
PROVIDER_STRATEGY = os.getenv("SWARM_PROVIDER_STRATEGY", "gemini_first")

# ── Web Research Settings ──────────────────────────────────────
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "10"))
WEB_SEARCH_REGION = os.getenv("WEB_SEARCH_REGION", "wt-wt")  # worldwide
WEB_SEARCH_SAFESEARCH = os.getenv("WEB_SEARCH_SAFESEARCH", "moderate")


# ═══════════════════════════════════════════════════════════════
# Provider Clients
# ═══════════════════════════════════════════════════════════════

def get_openai_client():
    """Return an OpenAI client pointed at the local Ollama instance."""
    from openai import OpenAI
    return OpenAI(
        base_url=OLLAMA_API_BASE,
        api_key="ollama",  # Ollama doesn't need a real key
    )


def get_ollama_client():
    """Return the native Ollama Python client."""
    import ollama
    return ollama.Client(host=OLLAMA_HOST)


def get_gemini_client():
    """Return a google-genai Client if API key is available."""
    if not GEMINI_AVAILABLE:
        raise RuntimeError(
            "Gemini not available. Set GEMINI_API_KEY in .env"
        )
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


# ═══════════════════════════════════════════════════════════════
# Model Discovery
# ═══════════════════════════════════════════════════════════════

def list_local_models():
    """List models currently available in the local Ollama instance."""
    client = get_ollama_client()
    response = client.list()
    models = response.models if hasattr(response, 'models') else []
    return [
        {
            "name": getattr(m, 'model', getattr(m, 'name', str(m))),
            "size_gb": round(getattr(m, 'size', 0) / (1024**3), 2),
            "modified": str(getattr(m, 'modified_at', '')),
            "provider": "ollama",
        }
        for m in models
    ]


def list_gemini_models():
    """List available Gemini models from the registry."""
    if not GEMINI_AVAILABLE:
        return []
    return [
        {
            "name": spec.display_name,
            "model_id": spec.model_id,
            "tier": spec.tier.value,
            "rpm": spec.rpm_limit,
            "rpd": spec.rpd_limit,
            "thinking": spec.supports_thinking,
            "provider": "gemini",
        }
        for spec in GEMINI_MODELS.values()
    ]


def list_all_available_models():
    """List models from all providers."""
    result = {"ollama": [], "gemini": []}
    try:
        result["ollama"] = list_local_models()
    except Exception:
        pass
    result["gemini"] = list_gemini_models()
    return result


# ═══════════════════════════════════════════════════════════════
# Role-Based Model Selection
# ═══════════════════════════════════════════════════════════════

def resolve_model_for_role(
    role: str,
    strategy: Optional[str] = None,
    rate_limiter: Optional["GeminiRateLimiter"] = None,
) -> tuple[Provider, str]:
    """Pick the best (provider, model) for a swarm role.

    Args:
        role: Agent role name (e.g. "researcher", "coder", "triage")
        strategy: Override PROVIDER_STRATEGY for this call
        rate_limiter: Optional GeminiRateLimiter to check quota

    Returns:
        (Provider, model_name_or_tier) tuple
    """
    strat = strategy or PROVIDER_STRATEGY
    mapping = ROLE_MODEL_MAP.get(role, ROLE_MODEL_MAP.get("enricher"))

    pref_provider, pref_model, fall_provider, fall_model = mapping

    # Strategy overrides
    if strat == "ollama_only":
        return (Provider.OLLAMA, fall_model if pref_provider == Provider.GEMINI else pref_model)
    if strat == "gemini_only":
        if not GEMINI_AVAILABLE:
            raise RuntimeError("gemini_only strategy but GEMINI_API_KEY not set")
        return (Provider.GEMINI, pref_model if pref_provider == Provider.GEMINI else fall_model)

    # gemini_first or ollama_first
    if strat == "gemini_first" and GEMINI_AVAILABLE:
        first_p, first_m = (Provider.GEMINI, pref_model if pref_provider == Provider.GEMINI else fall_model)
        second_p, second_m = (Provider.OLLAMA, fall_model if pref_provider == Provider.GEMINI else pref_model)
    else:
        first_p, first_m = (Provider.OLLAMA, pref_model if pref_provider == Provider.OLLAMA else fall_model)
        second_p, second_m = (Provider.GEMINI, pref_model if pref_provider == Provider.GEMINI else fall_model)

    # Rate limit check for Gemini
    if first_p == Provider.GEMINI and rate_limiter:
        try:
            spec = gemini_get_model(first_m)
            allowed, _ = rate_limiter.check(spec.model_id)
            if not allowed:
                return (second_p, second_m)
        except KeyError:
            return (second_p, second_m)

    return (first_p, first_m)


def pull_model(name: str):
    """Pull a model from the Ollama registry."""
    client = get_ollama_client()
    print(f"Pulling {name}... (this may take a while)")
    for progress in client.pull(name, stream=True):
        status = getattr(progress, 'status', str(progress))
        total = getattr(progress, 'total', 0) or 0
        completed = getattr(progress, 'completed', 0) or 0
        if total > 0:
            pct = round(completed / total * 100, 1)
            print(f"\r  {status}: {pct}%", end="", flush=True)
        else:
            print(f"\r  {status}", end="", flush=True)
    print(f"\n  ✓ {name} ready")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    print("═══ HFO Gen90 Swarm Configuration ═══\n")
    print(f"Provider strategy: {PROVIDER_STRATEGY}")
    print(f"Gemini available:  {GEMINI_AVAILABLE}")
    print(f"Default Ollama:    {DEFAULT_OLLAMA_MODEL}")
    print(f"Default Gemini:    {DEFAULT_GEMINI_TIER}")
    print()

    print("─── Role → Model Mapping ───")
    for role in ROLE_MODEL_MAP:
        provider, model = resolve_model_for_role(role)
        print(f"  {role:15s} → {provider.value}:{model}")
    print()

    print("─── Gemini Tiers ───")
    for tier, info in GEMINI_RECOMMENDED_TIERS.items():
        print(f"  {tier:15s} — {info['use']}")
    print()

    print("─── Ollama Recommended ───")
    for model, info in OLLAMA_RECOMMENDED_MODELS.items():
        print(f"  {model:22s} ({info['size_gb']:5.1f} GB) — {info['use']}")
