#!/usr/bin/env python3
"""
hfo_wish_llm_lattice.py — MAP-ELITE LLM Lattice for WISH V2 Compiler
======================================================================
v1.0 | Gen89 | Port: P7 NAVIGATE × P2 SHAPE | Medallion: bronze
Powerword: NAVIGATE × SHAPE | Spell: WISH V2 (Lattice Router)

PURPOSE:
    Tiered MAP-ELITE LLM lattice with Pareto-front non-dominated selection.
    WISH V2 compiler sends prompts to the HIGHEST available model first,
    optionally fans out to multiple models for diversity, and selects
    the non-dominated Pareto front candidate.

    The LLM layer is hallucinatory. The lattice is deterministic.
    Multiple models generate candidates → Pareto selection keeps the best.

LATTICE MODEL HIERARCHY (highest → lowest):

    ┌─────────────────────────────────────────────────────────────┐
    │  APEX TIER (external, rate-limited, highest quality)        │
    │    T4  Gemini 2.5 Pro        — Deep thinking, 2 RPM/25 RPD │
    │    T5  Gemini Experimental   — Bleeding edge, 2 RPM/50 RPD │
    │    —   Claude Opus 4.6       — Via Copilot (human-in-loop)  │
    ├─────────────────────────────────────────────────────────────┤
    │  CORE TIER (external, moderate rate limits)                  │
    │    T2  Gemini 2.5 Flash      — Thinking capable, 10 RPM    │
    │    T3  Gemini 2.5 Flash Lite — Background, 10 RPM          │
    │    T1  Gemini 2.0 Flash      — General purpose, 15 RPM     │
    ├─────────────────────────────────────────────────────────────┤
    │  LOCAL TIER (unlimited, free, latency-bound)                │
    │    L0  Ollama qwen2.5:14b    — Best local reasoning        │
    │    L1  Ollama qwen2.5:7b     — Fast local default          │
    │    L2  Ollama qwen2.5:3b     — Fastest local               │
    │    L3  Ollama deepseek-r1:8b — Deep reasoning chain        │
    │    L4  Ollama codestral      — Code-specialist             │
    └─────────────────────────────────────────────────────────────┘

LATTICE MODES:
    apex     — Use highest available model only (default for WISH)
    cascade  — Try highest, fall back on failure/rate-limit
    pareto   — Fan out to N models, Pareto-select non-dominated
    local    — Ollama only (offline mode)

PARETO OBJECTIVES (non-dominated selection):
    1. Quality   — scenario count, clause specificity, invariant coverage
    2. Coverage  — Given/When/Then completeness, edge case presence
    3. Cost      — tier cost (0=local, 1=flash, 2=flash25, 3=pro)
    4. Latency   — response time in milliseconds

NON-DOMINATED SELECTION:
    Candidate A dominates B iff A is ≥ B on all objectives and > on at least one.
    The Pareto front = set of all non-dominated candidates.
    Tie-break: highest quality → lowest cost → lowest latency.

USAGE:
    from hfo_wish_llm_lattice import WishLattice, LatticeMode

    lattice = WishLattice(mode=LatticeMode.APEX)
    result = lattice.generate(prompt, system_prompt)
    # result.content  — best response
    # result.model_id — which model produced it
    # result.scores   — Pareto objective scores

    # Pareto mode — fan out to top 3 models
    lattice = WishLattice(mode=LatticeMode.PARETO, fan_out=3)
    result = lattice.generate(prompt, system_prompt)
    # result.candidates      — all candidates
    # result.pareto_front    — non-dominated candidates
    # result.selected        — final selection from front

Pointer key: p7.wish_lattice
Cross-references:
    - hfo_gemini_models.py (GeminiTier, rate limiter, create_gemini_client)
    - hfo_swarm_config.py (Ollama config, recommended models)
    - hfo_p7_wish_compiler.py (consumer)
    - migration_map_elites.py (MAP-Elites behavioral grid pattern)
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION
# ═══════════════════════════════════════════════════════════════

_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

# Import Gemini infra
try:
    from hfo_gemini_models import (
        GeminiModelSpec,
        GeminiRateLimiter,
        GeminiTier,
        GEMINI_API_KEY,
        GEMINI_MODELS,
        VERTEX_AI_ENABLED,
        VERTEX_AI_PROJECT,
        create_gemini_client,
        get_model,
        get_thinking_models,
    )
    HAS_GEMINI_REGISTRY = True
except ImportError:
    HAS_GEMINI_REGISTRY = False

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434"))


# ═══════════════════════════════════════════════════════════════
# § 1  ENUMS AND DATA TYPES
# ═══════════════════════════════════════════════════════════════

class LatticeMode(str, Enum):
    """Lattice operation modes."""
    APEX    = "apex"     # Highest model only (default for WISH)
    CASCADE = "cascade"  # Highest → fallback chain
    PARETO  = "pareto"   # Fan out → Pareto-select
    LOCAL   = "local"    # Ollama only (offline)


class ProviderType(str, Enum):
    """Model provider types."""
    GEMINI  = "gemini"
    OLLAMA  = "ollama"
    COPILOT = "copilot"  # Claude 4.6 Opus — human-in-loop


@dataclass
class LatticeModelSpec:
    """A model in the lattice with its capabilities and cost."""
    model_id: str              # API identifier
    provider: ProviderType     # gemini | ollama | copilot
    display_name: str          # Human-readable
    tier_rank: int             # 0=highest/best, higher=lower quality
    cost_rank: int             # 0=free, 1=cheap, 2=medium, 3=expensive
    supports_thinking: bool    # Extended reasoning mode
    max_output_tokens: int     # Output window size
    rpm_limit: int             # Requests per minute (0=unlimited)
    rpd_limit: int             # Requests per day (0=unlimited)
    thinking_budget: int       # Thinking tokens budget (0=none)
    is_available: bool = True  # Runtime availability check

    @property
    def is_apex(self) -> bool:
        return self.tier_rank <= 1


@dataclass
class LatticeCandidate:
    """A single model's response with quality metrics."""
    content: str                  # Generated text
    model_id: str                 # Which model produced this
    provider: str                 # gemini | ollama | copilot
    latency_ms: float             # Response time
    cost_rank: int                # Cost tier
    # ── Quality scores (0.0-1.0) ──
    quality_score: float = 0.0    # Overall quality (computed)
    coverage_score: float = 0.0   # Gherkin coverage completeness
    specificity_score: float = 0.0  # Concreteness of scenarios
    invariant_score: float = 0.0  # Invariant scenario presence
    # ── Raw metrics ──
    scenario_count: int = 0
    has_given_when_then: bool = False
    has_invariant: bool = False
    has_edge_case: bool = False
    char_count: int = 0
    thinking_tokens_used: int = 0
    error: str = ""

    @property
    def is_valid(self) -> bool:
        return not self.error and self.content and self.has_given_when_then

    @property
    def objective_vector(self) -> tuple[float, float, float, float]:
        """4-objective vector for Pareto comparison.
        (quality↑, coverage↑, -cost↓, -latency↓)
        Maximize all — cost and latency are negated."""
        return (
            self.quality_score,
            self.coverage_score,
            1.0 - (self.cost_rank / 3.0),  # Invert: 0=expensive→0.0, 3=free→1.0
            max(0.0, 1.0 - (self.latency_ms / 60000.0)),  # Invert: 0ms→1.0
        )


@dataclass
class LatticeResult:
    """Final result from lattice generation."""
    content: str              # Selected best content
    model_id: str             # Which model produced it
    provider: str
    mode: str                 # Which lattice mode was used
    latency_ms: float         # Total time including all candidates
    # ── Pareto data ──
    candidates: list = field(default_factory=list)
    pareto_front: list = field(default_factory=list)
    selection_reason: str = ""
    # ── Scores ──
    quality_score: float = 0.0
    coverage_score: float = 0.0
    thinking_tokens_used: int = 0
    models_attempted: int = 0
    models_succeeded: int = 0
    fallback_used: bool = False


# ═══════════════════════════════════════════════════════════════
# § 2  LATTICE MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════

# The lattice ordered by tier_rank (0=best).
# Runtime availability dynamically determined.

def _build_lattice_registry() -> list[LatticeModelSpec]:
    """Build the ordered model lattice from available providers."""
    registry = []

    # ── APEX TIER: Gemini 2.5 Pro (deep thinking) ──
    registry.append(LatticeModelSpec(
        model_id="gemini-2.5-pro",
        provider=ProviderType.GEMINI,
        display_name="Gemini 2.5 Pro (Deep Think)",
        tier_rank=0,
        cost_rank=3,
        supports_thinking=True,
        max_output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=25,
        thinking_budget=32_768,
    ))

    # ── Gemini Experimental ──
    registry.append(LatticeModelSpec(
        model_id="gemini-exp-1206",
        provider=ProviderType.GEMINI,
        display_name="Gemini Experimental 1206",
        tier_rank=1,
        cost_rank=3,
        supports_thinking=True,
        max_output_tokens=65_536,
        rpm_limit=2,
        rpd_limit=50,
        thinking_budget=32_768,
    ))

    # ── CORE TIER: Gemini 2.5 Flash (thinking capable) ──
    registry.append(LatticeModelSpec(
        model_id="gemini-2.5-flash",
        provider=ProviderType.GEMINI,
        display_name="Gemini 2.5 Flash (Thinking)",
        tier_rank=2,
        cost_rank=2,
        supports_thinking=True,
        max_output_tokens=65_536,
        rpm_limit=10,
        rpd_limit=500,
        thinking_budget=16_384,
    ))

    # ── Gemini 2.5 Flash Lite ──
    registry.append(LatticeModelSpec(
        model_id="gemini-2.5-flash-lite",
        provider=ProviderType.GEMINI,
        display_name="Gemini 2.5 Flash Lite",
        tier_rank=3,
        cost_rank=1,
        supports_thinking=False,
        max_output_tokens=65_536,
        rpm_limit=10,
        rpd_limit=500,
        thinking_budget=0,
    ))

    # ── Gemini 2.0 Flash ──
    registry.append(LatticeModelSpec(
        model_id="gemini-2.0-flash",
        provider=ProviderType.GEMINI,
        display_name="Gemini 2.0 Flash",
        tier_rank=4,
        cost_rank=1,
        supports_thinking=False,
        max_output_tokens=8_192,
        rpm_limit=15,
        rpd_limit=1500,
        thinking_budget=0,
    ))

    # ── Gemini 2.0 Flash Lite (bulk) ──
    registry.append(LatticeModelSpec(
        model_id="gemini-2.0-flash-lite",
        provider=ProviderType.GEMINI,
        display_name="Gemini 2.0 Flash Lite",
        tier_rank=5,
        cost_rank=0,
        supports_thinking=False,
        max_output_tokens=8_192,
        rpm_limit=30,
        rpd_limit=1500,
        thinking_budget=0,
    ))

    # ── LOCAL TIER: Ollama models ──
    local_models = [
        ("qwen2.5:14b",    "Qwen 2.5 14B",     6, 0, False, 8192),
        ("qwen2.5:7b",     "Qwen 2.5 7B",      7, 0, False, 8192),
        ("deepseek-r1:8b", "DeepSeek R1 8B",    7, 0, True,  8192),
        ("qwen2.5:3b",     "Qwen 2.5 3B",      8, 0, False, 4096),
        ("codestral:latest","Codestral",         8, 0, False, 8192),
        ("llama3.2:3b",    "Llama 3.2 3B",      9, 0, False, 4096),
    ]
    for model_id, name, rank, cost, thinking, max_out in local_models:
        registry.append(LatticeModelSpec(
            model_id=model_id,
            provider=ProviderType.OLLAMA,
            display_name=name,
            tier_rank=rank,
            cost_rank=cost,
            supports_thinking=thinking,
            max_output_tokens=max_out,
            rpm_limit=0,
            rpd_limit=0,
            thinking_budget=8192 if thinking else 0,
        ))

    return registry


# Singleton - built once
LATTICE_REGISTRY: list[LatticeModelSpec] = _build_lattice_registry()


# ═══════════════════════════════════════════════════════════════
# § 3  QUALITY SCORER (Behavioral Descriptor Extraction)
# ═══════════════════════════════════════════════════════════════

def score_gherkin_candidate(content: str) -> dict:
    """
    Extract behavioral descriptors from Gherkin content.
    These become the MAP-ELITE grid coordinates.

    Returns dict with score components (all 0.0-1.0).
    """
    scores = {
        "quality_score": 0.0,
        "coverage_score": 0.0,
        "specificity_score": 0.0,
        "invariant_score": 0.0,
        "scenario_count": 0,
        "has_given_when_then": False,
        "has_invariant": False,
        "has_edge_case": False,
        "char_count": len(content),
    }

    if not content or not content.strip():
        return scores

    lines = content.splitlines()

    # ── Scenario counting ──
    scenario_blocks = re.findall(r"Scenario(?:\s+Outline)?:\s*(.+)", content, re.IGNORECASE)
    scores["scenario_count"] = len(scenario_blocks)

    # ── Given/When/Then coverage ──
    has_feature = bool(re.search(r"Feature:", content, re.IGNORECASE))
    has_given = bool(re.search(r"\bGiven\b", content))
    has_when = bool(re.search(r"\bWhen\b", content))
    has_then = bool(re.search(r"\bThen\b", content))
    has_and = bool(re.search(r"\bAnd\b", content))
    scores["has_given_when_then"] = has_given and has_when and has_then

    # ── Invariant detection (MUST NOT, fail-closed, rejection) ──
    invariant_patterns = [
        r"invariant",
        r"MUST\s+NOT",
        r"fail[\-\s]closed",
        r"reject",
        r"denied",
        r"blocked",
        r"never\s+(?:allow|accept|pass)",
    ]
    invariant_hits = sum(
        1 for pat in invariant_patterns
        if re.search(pat, content, re.IGNORECASE)
    )
    scores["has_invariant"] = invariant_hits >= 1
    scores["invariant_score"] = min(1.0, invariant_hits / 3.0)

    # ── Edge case detection ──
    edge_patterns = [
        r"edge\s+case",
        r"partial\s+(?:state|config|data)",
        r"concurrent",
        r"empty\s+(?:input|string|list)",
        r"timeout",
        r"unavailable",
        r"error\s+(?:handling|recovery)",
        r"race\s+condition",
    ]
    edge_hits = sum(
        1 for pat in edge_patterns
        if re.search(pat, content, re.IGNORECASE)
    )
    scores["has_edge_case"] = edge_hits >= 1

    # ── Specificity: concrete values vs vague language ──
    concrete_indicators = len(re.findall(
        r'"\w+"|\'[^\']+\'|\b\d+\b|SSOT|GRANTED|DENIED|REJECTED|CloudEvent',
        content
    ))
    vague_indicators = len(re.findall(
        r"\bsome\b|\bvarious\b|\bseveral\b|\bmany\b|\bappropriate\b",
        content, re.IGNORECASE
    ))
    total_words = len(content.split())
    if total_words > 0:
        specificity = min(1.0, (concrete_indicators * 3.0) / total_words)
        vague_penalty = min(0.3, vague_indicators * 0.1)
        scores["specificity_score"] = max(0.0, specificity - vague_penalty)

    # ── Coverage score (composite) ──
    coverage_components = [
        1.0 if has_feature else 0.0,
        1.0 if scores["has_given_when_then"] else 0.0,
        min(1.0, scores["scenario_count"] / 5.0),  # 5+ scenarios = full coverage
        1.0 if has_and else 0.0,
        scores["invariant_score"],
        0.5 if scores["has_edge_case"] else 0.0,
    ]
    scores["coverage_score"] = sum(coverage_components) / len(coverage_components)

    # ── Quality score (weighted composite) ──
    quality_weights = {
        "gwt": (0.25, 1.0 if scores["has_given_when_then"] else 0.0),
        "scenarios": (0.20, min(1.0, scores["scenario_count"] / 5.0)),
        "invariant": (0.20, scores["invariant_score"]),
        "specificity": (0.15, scores["specificity_score"]),
        "edge": (0.10, 1.0 if scores["has_edge_case"] else 0.0),
        "coverage": (0.10, scores["coverage_score"]),
    }
    scores["quality_score"] = sum(w * v for w, v in quality_weights.values())

    return scores


# ═══════════════════════════════════════════════════════════════
# § 4  PARETO FRONT SELECTION (Non-Dominated Sorting)
# ═══════════════════════════════════════════════════════════════

def _dominates(a: tuple, b: tuple) -> bool:
    """
    True if vector a dominates vector b.
    a dominates b iff: a[i] >= b[i] for all i, AND a[j] > b[j] for at least one j.
    (All objectives are to be MAXIMIZED.)
    """
    at_least_one_better = False
    for ai, bi in zip(a, b):
        if ai < bi:
            return False
        if ai > bi:
            at_least_one_better = True
    return at_least_one_better


def pareto_front(candidates: list[LatticeCandidate]) -> list[LatticeCandidate]:
    """
    Extract the Pareto front from a set of candidates.
    Returns the non-dominated set: no candidate in the front is
    dominated by any other candidate in the full set.
    """
    valid = [c for c in candidates if c.is_valid]
    if not valid:
        return []
    if len(valid) == 1:
        return valid

    front = []
    for i, ci in enumerate(valid):
        vi = ci.objective_vector
        dominated = False
        for j, cj in enumerate(valid):
            if i == j:
                continue
            vj = cj.objective_vector
            if _dominates(vj, vi):
                dominated = True
                break
        if not dominated:
            front.append(ci)

    return front


def select_from_front(front: list[LatticeCandidate]) -> LatticeCandidate:
    """
    Select the best candidate from the Pareto front.
    Tie-break ordering: quality → coverage → lowest cost → lowest latency.
    """
    if not front:
        raise ValueError("Empty Pareto front — no valid candidates")
    if len(front) == 1:
        return front[0]

    return max(front, key=lambda c: (
        c.quality_score,
        c.coverage_score,
        -c.cost_rank,
        -c.latency_ms,
    ))


# ═══════════════════════════════════════════════════════════════
# § 5  MODEL INVOCATION LAYER
# ═══════════════════════════════════════════════════════════════

def _call_gemini_model(
    model_id: str,
    prompt: str,
    system_prompt: str = "",
    thinking_budget: int = 0,
) -> tuple[str, float, int]:
    """
    Call a Gemini model via google-genai SDK.
    Uses Vertex AI if configured, otherwise AI Studio.

    Returns: (content, latency_ms, thinking_tokens_used)
    """
    if not HAS_GEMINI_REGISTRY:
        raise RuntimeError("hfo_gemini_models not available")

    client, mode = create_gemini_client()

    # Build generation config
    gen_config = {"temperature": 0.3, "max_output_tokens": 8192}

    # Enable thinking mode for capable models
    if thinking_budget > 0:
        gen_config["thinking_config"] = {"thinking_budget": thinking_budget}
        gen_config["max_output_tokens"] = 65536

    # Build contents
    contents = []
    if system_prompt:
        contents.append({"role": "user", "parts": [{"text": f"[System instruction]\n{system_prompt}\n\n[User request]\n{prompt}"}]})
    else:
        contents.append({"role": "user", "parts": [{"text": prompt}]})

    t0 = time.time()
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=gen_config,
        )
        latency_ms = (time.time() - t0) * 1000

        # Extract text from response
        text = ""
        thinking_tokens = 0
        if hasattr(response, 'text'):
            text = response.text or ""
        elif hasattr(response, 'candidates') and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'thought') and part.thought:
                    thinking_tokens += len(part.text.split()) if hasattr(part, 'text') else 0
                elif hasattr(part, 'text'):
                    text += part.text

        # Count thinking tokens from usage metadata
        if hasattr(response, 'usage_metadata'):
            um = response.usage_metadata
            if hasattr(um, 'thoughts_token_count'):
                thinking_tokens = um.thoughts_token_count or 0

        return text, latency_ms, thinking_tokens

    except Exception as e:
        latency_ms = (time.time() - t0) * 1000
        raise RuntimeError(f"Gemini {model_id} failed ({latency_ms:.0f}ms): {e}")


def _call_ollama_model(
    model_id: str,
    prompt: str,
    system_prompt: str = "",
) -> tuple[str, float, int]:
    """
    Call an Ollama model via REST API.
    Returns: (content, latency_ms, thinking_tokens_used=0)
    """
    import urllib.request

    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model_id,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 8192},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode())
            latency_ms = (time.time() - t0) * 1000
            text = result.get("response", "")
            return text, latency_ms, 0
    except Exception as e:
        latency_ms = (time.time() - t0) * 1000
        raise RuntimeError(f"Ollama {model_id} failed ({latency_ms:.0f}ms): {e}")


def _check_ollama_alive() -> bool:
    """Check if Ollama server is reachable."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _get_ollama_models() -> set[str]:
    """Get set of locally available Ollama model names."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return {m["name"] for m in data.get("models", [])}
    except Exception:
        return set()


# ═══════════════════════════════════════════════════════════════
# § 6  WISH LATTICE — Main Interface
# ═══════════════════════════════════════════════════════════════

class WishLattice:
    """
    MAP-ELITE LLM Lattice for WISH V2 compiler.

    Manages multi-model generation and Pareto-front selection.
    Default mode: APEX (use highest available model — Gemini 2.5 Pro).

    Usage:
        lattice = WishLattice(mode=LatticeMode.APEX)
        result = lattice.generate(prompt, system_prompt)
    """

    def __init__(
        self,
        mode: LatticeMode = LatticeMode.APEX,
        fan_out: int = 3,
        require_thinking: bool = True,
        rate_limiter: Optional[GeminiRateLimiter] = None,
    ):
        self.mode = mode
        self.fan_out = max(1, min(fan_out, 6))  # Cap at 6
        self.require_thinking = require_thinking
        self.rate_limiter = rate_limiter or (GeminiRateLimiter() if HAS_GEMINI_REGISTRY else None)
        self._ollama_alive: Optional[bool] = None
        self._ollama_models: Optional[set] = None

    def _check_availability(self, spec: LatticeModelSpec) -> bool:
        """Check if a model is available right now."""
        if spec.provider == ProviderType.GEMINI:
            if not HAS_GEMINI_REGISTRY:
                return False
            if not (GEMINI_API_KEY or VERTEX_AI_ENABLED):
                return False
            # Check rate limits
            if self.rate_limiter:
                allowed, _ = self.rate_limiter.check(spec.model_id)
                if not allowed:
                    return False
            return True

        elif spec.provider == ProviderType.OLLAMA:
            if self._ollama_alive is None:
                self._ollama_alive = _check_ollama_alive()
            if not self._ollama_alive:
                return False
            if self._ollama_models is None:
                self._ollama_models = _get_ollama_models()
            return spec.model_id in self._ollama_models

        elif spec.provider == ProviderType.COPILOT:
            return False  # Human-in-loop only

        return False

    def _get_available_models(self, thinking_only: bool = False) -> list[LatticeModelSpec]:
        """Get available models sorted by tier_rank (best first)."""
        available = []
        for spec in LATTICE_REGISTRY:
            if thinking_only and not spec.supports_thinking:
                continue
            if self._check_availability(spec):
                available.append(spec)
        return sorted(available, key=lambda s: s.tier_rank)

    def _invoke_model(
        self,
        spec: LatticeModelSpec,
        prompt: str,
        system_prompt: str = "",
    ) -> LatticeCandidate:
        """Invoke a single model and score the result."""
        try:
            if spec.provider == ProviderType.GEMINI:
                budget = spec.thinking_budget if self.require_thinking and spec.supports_thinking else 0
                content, latency_ms, thinking_tokens = _call_gemini_model(
                    spec.model_id, prompt, system_prompt, thinking_budget=budget
                )
                # Record rate limit usage
                if self.rate_limiter:
                    self.rate_limiter.record(spec.model_id)

            elif spec.provider == ProviderType.OLLAMA:
                content, latency_ms, thinking_tokens = _call_ollama_model(
                    spec.model_id, prompt, system_prompt
                )
            else:
                raise RuntimeError(f"Unsupported provider: {spec.provider}")

            # Score the candidate
            scores = score_gherkin_candidate(content)
            return LatticeCandidate(
                content=content,
                model_id=spec.model_id,
                provider=spec.provider.value,
                latency_ms=latency_ms,
                cost_rank=spec.cost_rank,
                thinking_tokens_used=thinking_tokens,
                **scores,
            )

        except Exception as e:
            return LatticeCandidate(
                content="",
                model_id=spec.model_id,
                provider=spec.provider.value,
                latency_ms=0,
                cost_rank=spec.cost_rank,
                error=str(e),
            )

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> LatticeResult:
        """
        Generate content using the lattice strategy.

        APEX:    Use highest available model only
        CASCADE: Walk down from highest, stop on first success
        PARETO:  Fan out to N models, Pareto-select
        LOCAL:   Ollama only
        """
        t0 = time.time()

        if self.mode == LatticeMode.APEX:
            return self._generate_apex(prompt, system_prompt, t0)
        elif self.mode == LatticeMode.CASCADE:
            return self._generate_cascade(prompt, system_prompt, t0)
        elif self.mode == LatticeMode.PARETO:
            return self._generate_pareto(prompt, system_prompt, t0)
        elif self.mode == LatticeMode.LOCAL:
            return self._generate_local(prompt, system_prompt, t0)
        else:
            raise ValueError(f"Unknown lattice mode: {self.mode}")

    def _generate_apex(self, prompt: str, system_prompt: str, t0: float) -> LatticeResult:
        """Use the single highest available model."""
        available = self._get_available_models(
            thinking_only=self.require_thinking
        )
        if not available:
            # Fallback: any model, no thinking requirement
            available = self._get_available_models(thinking_only=False)
        if not available:
            return LatticeResult(
                content="", model_id="none", provider="none",
                mode="apex", latency_ms=0,
                selection_reason="No models available",
            )

        best = available[0]
        candidate = self._invoke_model(best, prompt, system_prompt)
        total_ms = (time.time() - t0) * 1000

        return LatticeResult(
            content=candidate.content,
            model_id=candidate.model_id,
            provider=candidate.provider,
            mode="apex",
            latency_ms=total_ms,
            candidates=[asdict(candidate)],
            pareto_front=[asdict(candidate)] if candidate.is_valid else [],
            selection_reason=f"Apex: {best.display_name} (tier {best.tier_rank})",
            quality_score=candidate.quality_score,
            coverage_score=candidate.coverage_score,
            thinking_tokens_used=candidate.thinking_tokens_used,
            models_attempted=1,
            models_succeeded=1 if candidate.is_valid else 0,
        )

    def _generate_cascade(self, prompt: str, system_prompt: str, t0: float) -> LatticeResult:
        """Try models from highest to lowest, stop on first success."""
        available = self._get_available_models(
            thinking_only=self.require_thinking
        )
        if not available:
            available = self._get_available_models(thinking_only=False)

        all_candidates = []
        for spec in available:
            candidate = self._invoke_model(spec, prompt, system_prompt)
            all_candidates.append(candidate)

            if candidate.is_valid:
                total_ms = (time.time() - t0) * 1000
                return LatticeResult(
                    content=candidate.content,
                    model_id=candidate.model_id,
                    provider=candidate.provider,
                    mode="cascade",
                    latency_ms=total_ms,
                    candidates=[asdict(c) for c in all_candidates],
                    pareto_front=[asdict(candidate)],
                    selection_reason=f"Cascade: {spec.display_name} (try {len(all_candidates)})",
                    quality_score=candidate.quality_score,
                    coverage_score=candidate.coverage_score,
                    thinking_tokens_used=candidate.thinking_tokens_used,
                    models_attempted=len(all_candidates),
                    models_succeeded=1,
                    fallback_used=len(all_candidates) > 1,
                )

        total_ms = (time.time() - t0) * 1000
        return LatticeResult(
            content="", model_id="none", provider="none",
            mode="cascade", latency_ms=total_ms,
            candidates=[asdict(c) for c in all_candidates],
            selection_reason=f"Cascade exhausted — {len(all_candidates)} models tried, all failed",
            models_attempted=len(all_candidates),
        )

    def _generate_pareto(self, prompt: str, system_prompt: str, t0: float) -> LatticeResult:
        """
        Fan out to top N models, collect candidates, Pareto-select.
        This is the MAP-ELITE strategy — behavioral diversity across the lattice.
        """
        available = self._get_available_models()
        if not available:
            return LatticeResult(
                content="", model_id="none", provider="none",
                mode="pareto", latency_ms=0,
                selection_reason="No models available for Pareto fan-out",
            )

        # Select top fan_out models, preferring tier diversity
        selected_specs = available[:self.fan_out]

        # Invoke all selected models (sequential — rate limit protection)
        all_candidates = []
        for spec in selected_specs:
            candidate = self._invoke_model(spec, prompt, system_prompt)
            all_candidates.append(candidate)

        # Extract Pareto front
        front = pareto_front(all_candidates)
        succeeded = sum(1 for c in all_candidates if c.is_valid)

        if front:
            winner = select_from_front(front)
            total_ms = (time.time() - t0) * 1000

            return LatticeResult(
                content=winner.content,
                model_id=winner.model_id,
                provider=winner.provider,
                mode="pareto",
                latency_ms=total_ms,
                candidates=[asdict(c) for c in all_candidates],
                pareto_front=[asdict(c) for c in front],
                selection_reason=(
                    f"Pareto: {len(front)} non-dominated from {len(all_candidates)} candidates. "
                    f"Winner: {winner.model_id} "
                    f"(Q={winner.quality_score:.2f}, C={winner.coverage_score:.2f})"
                ),
                quality_score=winner.quality_score,
                coverage_score=winner.coverage_score,
                thinking_tokens_used=winner.thinking_tokens_used,
                models_attempted=len(all_candidates),
                models_succeeded=succeeded,
            )
        else:
            total_ms = (time.time() - t0) * 1000
            return LatticeResult(
                content="", model_id="none", provider="none",
                mode="pareto", latency_ms=total_ms,
                candidates=[asdict(c) for c in all_candidates],
                selection_reason=f"Pareto: all {len(all_candidates)} candidates invalid",
                models_attempted=len(all_candidates),
                models_succeeded=0,
            )

    def _generate_local(self, prompt: str, system_prompt: str, t0: float) -> LatticeResult:
        """Ollama only — offline mode."""
        available = [s for s in self._get_available_models()
                     if s.provider == ProviderType.OLLAMA]
        if not available:
            return LatticeResult(
                content="", model_id="none", provider="none",
                mode="local", latency_ms=0,
                selection_reason="No local Ollama models available",
            )

        best = available[0]
        candidate = self._invoke_model(best, prompt, system_prompt)
        total_ms = (time.time() - t0) * 1000

        return LatticeResult(
            content=candidate.content,
            model_id=candidate.model_id,
            provider=candidate.provider,
            mode="local",
            latency_ms=total_ms,
            candidates=[asdict(candidate)],
            pareto_front=[asdict(candidate)] if candidate.is_valid else [],
            selection_reason=f"Local: {best.display_name}",
            quality_score=candidate.quality_score,
            coverage_score=candidate.coverage_score,
            models_attempted=1,
            models_succeeded=1 if candidate.is_valid else 0,
        )

    def status(self) -> dict:
        """Return lattice status for diagnostics."""
        available = self._get_available_models()
        thinking = [s for s in available if s.supports_thinking]
        gemini = [s for s in available if s.provider == ProviderType.GEMINI]
        ollama = [s for s in available if s.provider == ProviderType.OLLAMA]

        return {
            "mode": self.mode.value,
            "fan_out": self.fan_out,
            "require_thinking": self.require_thinking,
            "total_available": len(available),
            "apex_model": available[0].model_id if available else "none",
            "apex_display": available[0].display_name if available else "none",
            "thinking_capable": len(thinking),
            "gemini_count": len(gemini),
            "ollama_count": len(ollama),
            "vertex_ai": VERTEX_AI_ENABLED if HAS_GEMINI_REGISTRY else False,
            "gemini_api_key": bool(GEMINI_API_KEY) if HAS_GEMINI_REGISTRY else False,
            "ollama_alive": self._ollama_alive if self._ollama_alive is not None else "unchecked",
            "rate_limiter_usage": self.rate_limiter.usage_summary() if self.rate_limiter else {},
            "model_ladder": [
                {
                    "rank": s.tier_rank,
                    "model_id": s.model_id,
                    "provider": s.provider.value,
                    "thinking": s.supports_thinking,
                    "cost": s.cost_rank,
                    "available": True,
                }
                for s in available
            ],
        }


# ═══════════════════════════════════════════════════════════════
# § 7  CLI
# ═══════════════════════════════════════════════════════════════

def _cli():
    """Print lattice status and run test generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WISH V2 MAP-ELITE LLM Lattice (Gen89)"
    )
    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "test", "pareto-test"],
                        help="Command to run")
    parser.add_argument("--prompt", default="Write a Gherkin feature for verifying SSOT health",
                        help="Test prompt")
    parser.add_argument("--mode", default="apex",
                        choices=["apex", "cascade", "pareto", "local"],
                        help="Lattice mode")
    parser.add_argument("--fan-out", type=int, default=3,
                        help="Pareto fan-out count")
    parser.add_argument("--no-thinking", action="store_true",
                        help="Disable thinking mode requirement")
    parser.add_argument("--json", action="store_true",
                        help="JSON output")
    args = parser.parse_args()

    lattice = WishLattice(
        mode=LatticeMode(args.mode),
        fan_out=args.fan_out,
        require_thinking=not args.no_thinking,
    )

    if args.command == "status":
        st = lattice.status()
        if args.json:
            print(json.dumps(st, indent=2, default=str))
        else:
            print()
            print("  " + "=" * 62)
            print("  MAP-ELITE LLM LATTICE — WISH V2 Compiler")
            print("  Non-Dominated Pareto Front Model Selection")
            print("  " + "-" * 62)
            print(f"  Mode:       {st['mode']}")
            print(f"  Fan-out:    {st['fan_out']}")
            print(f"  Thinking:   {'required' if st['require_thinking'] else 'optional'}")
            print(f"  Apex Model: {st['apex_display']}")
            print(f"  Available:  {st['total_available']} models "
                  f"({st['gemini_count']} Gemini, {st['ollama_count']} Ollama)")
            print(f"  Thinking:   {st['thinking_capable']} thinking-capable models")
            print(f"  Vertex AI:  {st['vertex_ai']}")
            print(f"  Ollama:     {st['ollama_alive']}")
            print()
            print("  Model Ladder (best → worst):")
            for m in st.get("model_ladder", []):
                think = "🧠" if m["thinking"] else "  "
                cost = ["FREE", "$", "$$", "$$$"][m["cost"]]
                print(f"    {m['rank']:2d}. {think} {m['model_id']:<30s} "
                      f"{m['provider']:<8s} {cost}")
            print()
            print("  " + "=" * 62)
            print()

    elif args.command in ("test", "pareto-test"):
        if args.command == "pareto-test":
            lattice.mode = LatticeMode.PARETO

        print(f"\n  Testing lattice ({lattice.mode.value} mode)...")
        print(f"  Prompt: {args.prompt[:60]}...")
        result = lattice.generate(args.prompt)

        if args.json:
            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print(f"\n  Result:")
            print(f"    Model:    {result.model_id}")
            print(f"    Provider: {result.provider}")
            print(f"    Latency:  {result.latency_ms:.0f}ms")
            print(f"    Quality:  {result.quality_score:.2f}")
            print(f"    Coverage: {result.coverage_score:.2f}")
            print(f"    Thinking: {result.thinking_tokens_used} tokens")
            print(f"    Reason:   {result.selection_reason}")
            print(f"    Models:   {result.models_succeeded}/{result.models_attempted} succeeded")
            if result.content:
                print(f"\n  ── Generated Content ──")
                for line in result.content.splitlines()[:30]:
                    print(f"    {line}")
                if len(result.content.splitlines()) > 30:
                    print(f"    ... ({len(result.content.splitlines()) - 30} more lines)")
            else:
                print(f"\n  (no content generated)")
            print()


if __name__ == "__main__":
    _cli()
