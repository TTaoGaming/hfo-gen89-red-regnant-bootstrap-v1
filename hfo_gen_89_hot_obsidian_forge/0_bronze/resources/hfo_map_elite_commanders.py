#!/usr/bin/env python3
"""
hfo_map_elite_commanders.py — MAP-Elite Port Commander Framework
=================================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Powerword: GATE | School: Divination/Transmutation

PURPOSE:
    Quality-Diversity model selection for 8^N octree architecture.
    Each port gets 3 MAP-Elite exemplar tiers:
      - APEX_INTELLIGENCE: Smartest model available (deep think, max params)
      - APEX_SPEED:        Fastest model available (low latency, high throughput)  
      - APEX_COST:         Most cost-effective (free, low VRAM, still capable)

    ACO (Ant Colony Optimization) pheromone framework:
      - Every daemon emits standardized SIGNAL_METADATA in CloudEvent data
      - Pheromone accumulator reads stigmergy, scores model-port-tier combos
      - Evaporation decays stale scores so the swarm adapts
      - Scatter-gather coordinator recommends tier selection per cycle

    "8 commanders × 3 tiers = 24 exemplar slots.
     8^1 = 8 ports. 8^2 = 64 port-model combos. 8^N = fractal depth."

USAGE:
    python hfo_map_elite_commanders.py --registry     Show MAP-Elite model grid
    python hfo_map_elite_commanders.py --pheromone     Show ACO pheromone scores
    python hfo_map_elite_commanders.py --recommend      Recommend tier per port
    python hfo_map_elite_commanders.py --apex --port P4 Run apex intelligence on port
    python hfo_map_elite_commanders.py --signal-schema  Show standardized signal fields
    python hfo_map_elite_commanders.py --audit-signals  Audit current signal quality
    python hfo_map_elite_commanders.py --json           Machine-readable output

Medallion: bronze
Pointer key: map_elite.commanders
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
# § 0  PAL — Path Abstraction Layer
# ═══════════════════════════════════════════════════════════════

_SELF_DIR = Path(__file__).resolve().parent

def _find_root() -> Path:
    for anchor in [Path.cwd(), _SELF_DIR]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
GEN = os.environ.get("HFO_GENERATION", "89")
SOURCE_TAG = f"hfo_map_elite_gen{GEN}_v1.0"

# Load .env
try:
    from dotenv import load_dotenv
    env_path = HFO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass

# PAL pointer resolution
def _load_pointer_registry() -> dict:
    p = HFO_ROOT / "hfo_gen89_pointers_blessed.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("pointers", {})
    return {}

def _resolve_pointer(key: str) -> Path:
    ptrs = _load_pointer_registry()
    if key in ptrs:
        return HFO_ROOT / ptrs[key]["path"]
    raise FileNotFoundError(f"Pointer key '{key}' not found")

# Resolve SSOT
try:
    SSOT_DB = _resolve_pointer("ssot.db")
except FileNotFoundError:
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"

# Add bronze resources to path
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))


# ═══════════════════════════════════════════════════════════════
# § 1  MAP-ELITE TIER ARCHITECTURE
# ═══════════════════════════════════════════════════════════════

class ModelTier(str, Enum):
    """Three MAP-Elite tiers per port for quality-diversity selection."""
    APEX_INTELLIGENCE = "apex_intelligence"   # Max reasoning, largest model
    APEX_SPEED        = "apex_speed"          # Min latency, fastest inference
    APEX_COST         = "apex_cost"           # Min cost, free/cheap/small VRAM


class ModelProvider(str, Enum):
    """Model provider classification."""
    OLLAMA       = "ollama"        # Local Ollama (free, VRAM-bound)
    GEMINI_FREE  = "gemini_free"   # Google AI Studio free tier
    GEMINI_VERTEX = "gemini_vertex"  # Google Vertex AI (paid, $100/mo credits)
    CLAUDE       = "claude"        # Anthropic Claude (via Copilot/MCP)


@dataclass(frozen=True)
class ModelExemplar:
    """A specific model assigned to a port-tier slot in the MAP-Elite grid."""
    model_id: str                 # e.g., "phi4:14b", "gemini-3.1-pro-preview"
    model_family: str             # e.g., "Microsoft Phi", "Google Gemini"
    params_billions: float        # Parameter count in billions
    provider: ModelProvider       # Where this model runs
    tier: ModelTier              # Which MAP-Elite tier
    vram_gb: float = 0.0        # VRAM footprint (Ollama only)
    est_tok_per_sec: float = 0.0 # Estimated tokens/sec on this hardware
    cost_per_1m_tokens: float = 0.0  # USD per 1M output tokens
    supports_thinking: bool = False  # Deep think / chain-of-thought
    notes: str = ""


@dataclass
class PortCommander:
    """A port commander with 3 MAP-Elite model exemplars."""
    port: str                    # P0-P7
    word: str                    # OBSERVE, BRIDGE, SHAPE, etc.
    commander: str               # Lidless Legion, Web Weaver, etc.
    exemplars: dict[ModelTier, ModelExemplar] = field(default_factory=dict)
    
    @property
    def apex_intelligence(self) -> Optional[ModelExemplar]:
        return self.exemplars.get(ModelTier.APEX_INTELLIGENCE)
    
    @property
    def apex_speed(self) -> Optional[ModelExemplar]:
        return self.exemplars.get(ModelTier.APEX_SPEED)
    
    @property
    def apex_cost(self) -> Optional[ModelExemplar]:
        return self.exemplars.get(ModelTier.APEX_COST)


# ═══════════════════════════════════════════════════════════════
# § 2  MODEL REGISTRY — Populated from Ollama + Gemini
# ═══════════════════════════════════════════════════════════════

# Ollama model metadata (from `ollama list` + manual specs)
_OLLAMA_MODELS = {
    "deepseek-r1:32b": ModelExemplar(
        model_id="deepseek-r1:32b", model_family="DeepSeek",
        params_billions=32.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_INTELLIGENCE, vram_gb=19.0,
        est_tok_per_sec=5.0, supports_thinking=True,
        notes="Largest local model. Deep reasoning. VRAM hog — can't coexist with others.",
    ),
    "phi4:14b": ModelExemplar(
        model_id="phi4:14b", model_family="Microsoft Phi",
        params_billions=14.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_INTELLIGENCE, vram_gb=9.1,
        est_tok_per_sec=12.0, supports_thinking=False,
        notes="Strong reasoning + coding. Current P4 Singer model.",
    ),
    "qwen3:30b-a3b": ModelExemplar(
        model_id="qwen3:30b-a3b", model_family="Alibaba Qwen",
        params_billions=30.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_INTELLIGENCE, vram_gb=18.0,
        est_tok_per_sec=8.0, supports_thinking=True,
        notes="MoE: 30B total, 3B active. Deep policy knowledge. Current P5 Dancer.",
    ),
    "deepseek-r1:8b": ModelExemplar(
        model_id="deepseek-r1:8b", model_family="DeepSeek",
        params_billions=8.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_INTELLIGENCE, vram_gb=5.2,
        est_tok_per_sec=15.0, supports_thinking=True,
        notes="Reasoning chain-of-thought. Current P6 Devourer.",
    ),
    "qwen2.5-coder:7b": ModelExemplar(
        model_id="qwen2.5-coder:7b", model_family="Alibaba Qwen",
        params_billions=7.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_SPEED, vram_gb=4.7,
        est_tok_per_sec=18.0,
        notes="Code specialist. Chimera evalavg 0.848.",
    ),
    "qwen3:8b": ModelExemplar(
        model_id="qwen3:8b", model_family="Alibaba Qwen",
        params_billions=8.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_SPEED, vram_gb=5.2,
        est_tok_per_sec=15.0, supports_thinking=True,
        notes="Balanced 8B with thinking support.",
    ),
    "gemma3:12b": ModelExemplar(
        model_id="gemma3:12b", model_family="Google Gemma",
        params_billions=12.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_INTELLIGENCE, vram_gb=8.1,
        est_tok_per_sec=10.0,
        notes="Large Gemma. Good for analysis.",
    ),
    "gemma3:4b": ModelExemplar(
        model_id="gemma3:4b", model_family="Google Gemma",
        params_billions=4.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_SPEED, vram_gb=3.3,
        est_tok_per_sec=25.0,
        notes="Fast Gemma. Current P2 Shaper model.",
    ),
    "granite4:3b": ModelExemplar(
        model_id="granite4:3b", model_family="IBM Granite",
        params_billions=3.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_COST, vram_gb=2.1,
        est_tok_per_sec=30.0,
        notes="Cheapest/fastest local. Current P0 Watcher.",
    ),
    "llama3.2:3b": ModelExemplar(
        model_id="llama3.2:3b", model_family="Meta Llama",
        params_billions=3.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_COST, vram_gb=2.0,
        est_tok_per_sec=30.0,
        notes="Meta Llama small. Solid general-purpose.",
    ),
    "qwen2.5:3b": ModelExemplar(
        model_id="qwen2.5:3b", model_family="Alibaba Qwen",
        params_billions=3.0, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_COST, vram_gb=1.9,
        est_tok_per_sec=35.0,
        notes="Cheapest Qwen. Current P6 Kraken aux.",
    ),
    "lfm2.5-thinking:1.2b": ModelExemplar(
        model_id="lfm2.5-thinking:1.2b", model_family="Liquid AI",
        params_billions=1.2, provider=ModelProvider.OLLAMA,
        tier=ModelTier.APEX_COST, vram_gb=0.7,
        est_tok_per_sec=50.0, supports_thinking=True,
        notes="Ultra-compact thinker. Current P3 Injector.",
    ),
}

# Gemini model exemplars
_GEMINI_MODELS = {
    "gemini-3.1-pro-preview": ModelExemplar(
        model_id="gemini-3.1-pro-preview", model_family="Google Gemini",
        params_billions=0.0,  # Unknown, cloud-hosted
        provider=ModelProvider.GEMINI_VERTEX,
        tier=ModelTier.APEX_INTELLIGENCE,
        cost_per_1m_tokens=12.0,
        supports_thinking=True,
        notes="T5 APEX. Strongest Gemini. Deep Think. $2/$12 per 1M. Current P7 Summoner.",
    ),
    "gemini-3-pro-preview": ModelExemplar(
        model_id="gemini-3-pro-preview", model_family="Google Gemini",
        params_billions=0.0,
        provider=ModelProvider.GEMINI_VERTEX,
        tier=ModelTier.APEX_INTELLIGENCE,
        cost_per_1m_tokens=12.0,
        supports_thinking=True,
        notes="T4 FRONTIER_PRO. SOTA multimodal.",
    ),
    "gemini-3-flash-preview": ModelExemplar(
        model_id="gemini-3-flash-preview", model_family="Google Gemini",
        params_billions=0.0,
        provider=ModelProvider.GEMINI_FREE,
        tier=ModelTier.APEX_SPEED,
        cost_per_1m_tokens=3.0,
        supports_thinking=True,
        notes="T2 FRONTIER_FLASH. Free tier. Fast + smart. Current P1 Weaver.",
    ),
    "gemini-2.5-flash": ModelExemplar(
        model_id="gemini-2.5-flash", model_family="Google Gemini",
        params_billions=0.0,
        provider=ModelProvider.GEMINI_FREE,
        tier=ModelTier.APEX_SPEED,
        cost_per_1m_tokens=2.5,
        supports_thinking=True,
        notes="T1 FLASH. GA stable. Free tier workhorse.",
    ),
    "gemini-2.5-flash-lite": ModelExemplar(
        model_id="gemini-2.5-flash-lite", model_family="Google Gemini",
        params_billions=0.0,
        provider=ModelProvider.GEMINI_FREE,
        tier=ModelTier.APEX_COST,
        cost_per_1m_tokens=0.4,
        supports_thinking=True,
        notes="T0 BUDGET. Cheapest Gemini. Bulk enrichment.",
    ),
}

# Claude (via Copilot — special, not directly invokable by daemons but present in swarm)
_CLAUDE_MODELS = {
    "claude-opus-4-6": ModelExemplar(
        model_id="claude-opus-4-6", model_family="Anthropic Claude",
        params_billions=0.0,
        provider=ModelProvider.CLAUDE,
        tier=ModelTier.APEX_INTELLIGENCE,
        cost_per_1m_tokens=75.0,
        supports_thinking=True,
        notes="P4 Red Regnant operator-side. Extended thinking. Via Copilot chat.",
    ),
}

ALL_MODELS = {**_OLLAMA_MODELS, **_GEMINI_MODELS, **_CLAUDE_MODELS}


# ═══════════════════════════════════════════════════════════════
# § 3  PORT COMMANDER ASSIGNMENTS — MAP-Elite Grid
# ═══════════════════════════════════════════════════════════════

def build_port_commanders() -> dict[str, PortCommander]:
    """
    Build the 8-port MAP-Elite commander grid.
    Each port gets 3 exemplars: apex_intelligence, apex_speed, apex_cost.
    
    Selection criteria:
    - APEX_INTELLIGENCE: Largest/smartest model appropriate for port function
    - APEX_SPEED: Fastest model that still handles port function
    - APEX_COST: Cheapest free model that minimally handles port function
    """
    commanders = {}
    
    # P0 OBSERVE — Lidless Legion: Sensing, TRUE_SEEING, GREATER_SCRY
    # Needs: pattern detection in code/signals, web search interpretation
    commanders["P0"] = PortCommander(
        port="P0", word="OBSERVE", commander="Lidless Legion",
        exemplars={
            ModelTier.APEX_INTELLIGENCE: ALL_MODELS["gemma3:12b"],
            ModelTier.APEX_SPEED:        ALL_MODELS["gemma3:4b"],
            ModelTier.APEX_COST:         ALL_MODELS["granite4:3b"],
        },
    )
    
    # P1 BRIDGE — Web Weaver: External data bridging, web research
    # Needs: large context, grounding, URL fetching, search
    commanders["P1"] = PortCommander(
        port="P1", word="BRIDGE", commander="Web Weaver",
        exemplars={
            ModelTier.APEX_INTELLIGENCE: ALL_MODELS["gemini-3.1-pro-preview"],
            ModelTier.APEX_SPEED:        ALL_MODELS["gemini-3-flash-preview"],
            ModelTier.APEX_COST:         ALL_MODELS["gemini-2.5-flash-lite"],
        },
    )
    
    # P2 SHAPE — Mirror Magus: Code generation, creation, SBE towers
    # Needs: code generation, structured output, creativity
    commanders["P2"] = PortCommander(
        port="P2", word="SHAPE", commander="Mirror Magus",
        exemplars={
            ModelTier.APEX_INTELLIGENCE: ALL_MODELS["qwen2.5-coder:7b"],
            ModelTier.APEX_SPEED:        ALL_MODELS["gemma3:4b"],
            ModelTier.APEX_COST:         ALL_MODELS["lfm2.5-thinking:1.2b"],
        },
    )
    
    # P3 INJECT — Harmonic Hydra: Payload delivery, enrichment, port assignment
    # Needs: fast classification, structured output, throughput
    commanders["P3"] = PortCommander(
        port="P3", word="INJECT", commander="Harmonic Hydra",
        exemplars={
            ModelTier.APEX_INTELLIGENCE: ALL_MODELS["qwen3:8b"],
            ModelTier.APEX_SPEED:        ALL_MODELS["lfm2.5-thinking:1.2b"],
            ModelTier.APEX_COST:         ALL_MODELS["qwen2.5:3b"],
        },
    )
    
    # P4 DISRUPT — Red Regnant: Adversarial testing, mutation, red team
    # Needs: deep reasoning, adversarial challenge, complex analysis
    commanders["P4"] = PortCommander(
        port="P4", word="DISRUPT", commander="Red Regnant",
        exemplars={
            ModelTier.APEX_INTELLIGENCE: ALL_MODELS["phi4:14b"],
            ModelTier.APEX_SPEED:        ALL_MODELS["qwen3:8b"],
            ModelTier.APEX_COST:         ALL_MODELS["llama3.2:3b"],
        },
    )
    
    # P5 IMMUNIZE — Pyre Praetorian: Blue team, gates, governance
    # Needs: policy reasoning, structured validation, rule enforcement
    commanders["P5"] = PortCommander(
        port="P5", word="IMMUNIZE", commander="Pyre Praetorian",
        exemplars={
            ModelTier.APEX_INTELLIGENCE: ALL_MODELS["qwen3:30b-a3b"],
            ModelTier.APEX_SPEED:        ALL_MODELS["qwen3:8b"],
            ModelTier.APEX_COST:         ALL_MODELS["granite4:3b"],
        },
    )
    
    # P6 ASSIMILATE — Kraken Keeper: Knowledge extraction, learning, memory
    # Needs: deep reading, reasoning chains, synthesis
    commanders["P6"] = PortCommander(
        port="P6", word="ASSIMILATE", commander="Kraken Keeper",
        exemplars={
            ModelTier.APEX_INTELLIGENCE: ALL_MODELS["deepseek-r1:8b"],
            ModelTier.APEX_SPEED:        ALL_MODELS["qwen2.5-coder:7b"],
            ModelTier.APEX_COST:         ALL_MODELS["qwen2.5:3b"],
        },
    )
    
    # P7 NAVIGATE — Spider Sovereign: C2, strategy, Meadows leverage
    # Needs: strongest reasoning, strategic planning, deep think
    commanders["P7"] = PortCommander(
        port="P7", word="NAVIGATE", commander="Spider Sovereign",
        exemplars={
            ModelTier.APEX_INTELLIGENCE: ALL_MODELS["gemini-3.1-pro-preview"],
            ModelTier.APEX_SPEED:        ALL_MODELS["gemini-3-flash-preview"],
            ModelTier.APEX_COST:         ALL_MODELS["gemini-2.5-flash-lite"],
        },
    )
    
    return commanders


# ═══════════════════════════════════════════════════════════════
# § 4  SIGNAL METADATA SCHEMA — Standardized ACO Pheromone
# ═══════════════════════════════════════════════════════════════

@dataclass
class SignalMetadata:
    """
    Standardized metadata fields that EVERY daemon event should include.
    This is the pheromone that ACO reads to score model-port-tier combos.
    
    Emit this in the 'signal_metadata' key of every CloudEvent data dict.
    The swarm reads these to self-optimize model selection.
    """
    # Identity (WHO emitted this signal)
    port: str                      # P0-P7
    commander: str                 # Lidless Legion, etc.
    daemon_name: str               # Singer, Dancer, etc.
    daemon_version: str            # v1.0, v2.3, etc.
    
    # Model (WHAT intelligence was used)
    model_id: str                  # "phi4:14b", "gemini-3.1-pro-preview"
    model_family: str              # "Microsoft Phi", "Google Gemini"
    model_params_b: float          # Parameter count in billions (0 for cloud)
    model_provider: str            # "ollama", "gemini_free", "gemini_vertex"
    model_tier: str                # "apex_intelligence", "apex_speed", "apex_cost"
    
    # Performance (HOW WELL did inference perform)
    inference_latency_ms: float = 0.0   # Wall-clock time for this inference
    tokens_in: int = 0                   # Input/prompt tokens consumed
    tokens_out: int = 0                  # Output/completion tokens generated
    tokens_thinking: int = 0             # Thinking/reasoning tokens (if applicable)
    
    # Quality (HOW GOOD was the result)
    quality_score: float = 0.0           # 0.0–1.0 self-assessed quality
    quality_method: str = "none"         # How quality was measured
    # Quality methods: "none", "self_eval", "chimera_eval", "sbe_pass",
    #   "gate_pass", "human_validated", "mutation_tested"
    
    # Cost (WHAT DID IT COST)
    cost_usd: float = 0.0               # Estimated USD cost (0.0 for Ollama)
    vram_gb: float = 0.0                # VRAM used for this inference
    
    # Context (WHAT WAS THIS FOR)
    cycle: int = 0                       # Daemon cycle number
    task_type: str = ""                  # "strife", "splendor", "enrich", "patrol", etc.
    generation: str = GEN                # HFO generation
    timestamp: str = ""                  # ISO timestamp
    
    def to_dict(self) -> dict:
        """Serialize for CloudEvent data embedding."""
        d = asdict(self)
        if not d["timestamp"]:
            d["timestamp"] = datetime.now(timezone.utc).isoformat()
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> "SignalMetadata":
        """Deserialize from CloudEvent data."""
        # Handle missing fields gracefully
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in fields}
        return cls(**filtered)


# Field documentation for human/agent consumption
SIGNAL_SCHEMA_DOC = {
    "description": "MAP-Elite ACO Pheromone Signal Schema v1.0",
    "purpose": "Standardized metadata every daemon emits so the swarm can self-optimize",
    "fields": {
        "port":              {"type": "str", "required": True, "example": "P4",
                             "doc": "Octree port P0-P7"},
        "commander":         {"type": "str", "required": True, "example": "Red Regnant",
                             "doc": "Port commander name"},
        "daemon_name":       {"type": "str", "required": True, "example": "Singer",
                             "doc": "Daemon process name"},
        "daemon_version":    {"type": "str", "required": True, "example": "v1.1",
                             "doc": "Daemon software version"},
        "model_id":          {"type": "str", "required": True, "example": "phi4:14b",
                             "doc": "Exact model identifier (Ollama tag or Gemini model ID)"},
        "model_family":      {"type": "str", "required": True, "example": "Microsoft Phi",
                             "doc": "Model family for diversity tracking"},
        "model_params_b":    {"type": "float", "required": True, "example": 14.0,
                             "doc": "Parameter count in billions (0 for cloud models)"},
        "model_provider":    {"type": "str", "required": True, "example": "ollama",
                             "doc": "oneOf: ollama, gemini_free, gemini_vertex, claude"},
        "model_tier":        {"type": "str", "required": True, "example": "apex_intelligence",
                             "doc": "MAP-Elite tier: apex_intelligence, apex_speed, apex_cost"},
        "inference_latency_ms": {"type": "float", "required": False, "example": 3200.0,
                             "doc": "Wall-clock inference time in milliseconds"},
        "tokens_in":         {"type": "int", "required": False, "example": 1500,
                             "doc": "Input/prompt tokens consumed"},
        "tokens_out":        {"type": "int", "required": False, "example": 800,
                             "doc": "Output/completion tokens generated"},
        "tokens_thinking":   {"type": "int", "required": False, "example": 2000,
                             "doc": "Thinking/reasoning tokens (deep-think models)"},
        "quality_score":     {"type": "float", "required": False, "example": 0.72,
                             "doc": "Quality 0.0-1.0. ACO pheromone strength."},
        "quality_method":    {"type": "str", "required": False, "example": "chimera_eval",
                             "doc": "How quality was measured"},
        "cost_usd":          {"type": "float", "required": False, "example": 0.003,
                             "doc": "Estimated USD cost (0.0 for local/free)"},
        "vram_gb":           {"type": "float", "required": False, "example": 9.1,
                             "doc": "VRAM footprint in GB (Ollama models)"},
        "cycle":             {"type": "int", "required": False, "example": 42,
                             "doc": "Daemon cycle number"},
        "task_type":         {"type": "str", "required": False, "example": "strife",
                             "doc": "What kind of work this inference performed"},
        "generation":        {"type": "str", "required": False, "example": "89",
                             "doc": "HFO generation number"},
        "timestamp":         {"type": "str", "required": False, "example": "2026-02-19T23:00:00+00:00",
                             "doc": "ISO 8601 timestamp"},
    },
    "embedding_key": "signal_metadata",
    "example_event_data": {
        "song": "strife",
        "signal": "gate_block_pattern",
        "reason": "175 gate blocks in 12 hours",
        "signal_metadata": {
            "port": "P4", "commander": "Red Regnant",
            "daemon_name": "Singer", "daemon_version": "v1.1",
            "model_id": "phi4:14b", "model_family": "Microsoft Phi",
            "model_params_b": 14.0, "model_provider": "ollama",
            "model_tier": "apex_intelligence",
            "inference_latency_ms": 3200.0,
            "tokens_in": 1500, "tokens_out": 800,
            "quality_score": 0.72, "quality_method": "self_eval",
            "cost_usd": 0.0, "vram_gb": 9.1,
            "cycle": 42, "task_type": "strife", "generation": "89",
        },
    },
}


# ═══════════════════════════════════════════════════════════════
# § 5  ACO PHEROMONE ENGINE — Ant Colony Optimization
# ═══════════════════════════════════════════════════════════════

@dataclass
class PheromoneScore:
    """ACO pheromone score for a model-port-tier combination."""
    port: str
    model_id: str
    model_tier: str
    
    # Accumulated pheromone metrics
    total_inferences: int = 0
    avg_latency_ms: float = 0.0
    avg_quality: float = 0.0
    total_cost_usd: float = 0.0
    avg_tokens_out: float = 0.0
    
    # Composite ACO score: quality / (latency_norm * cost_norm)
    # Higher = better path to follow
    pheromone_strength: float = 0.0
    
    # Evaporation tracking
    last_seen: str = ""
    age_hours: float = 0.0
    evaporation_factor: float = 1.0  # 1.0 = fresh, decays toward 0


# Evaporation constants (from ACO literature)
EVAPORATION_RATE = 0.1   # 10% decay per hour
MIN_PHEROMONE = 0.01     # Floor — never fully evaporate
QUALITY_WEIGHT = 2.0     # Alpha: how much quality matters
SPEED_WEIGHT = 1.0       # Beta: how much speed matters
COST_WEIGHT = 0.5        # Gamma: how much cost matters (inverted: less cost = better)


def _get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _get_db_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def compute_pheromone_scores(hours_back: float = 24.0) -> list[PheromoneScore]:
    """
    Read stigmergy events from the last N hours, extract signal_metadata,
    and compute ACO pheromone scores for each model-port-tier combination.
    
    This is the ACCUMULATION phase of the ACO algorithm.
    """
    conn = _get_db_ro()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    
    # Read all events with signal_metadata
    rows = conn.execute("""
        SELECT event_type, timestamp, data_json 
        FROM stigmergy_events
        WHERE timestamp > ? AND event_type LIKE 'hfo.gen89.%'
        ORDER BY id DESC
    """, (cutoff,)).fetchall()
    conn.close()
    
    # Aggregate by (port, model_id, model_tier)
    aggregates: dict[tuple, dict] = {}
    
    for row in rows:
        try:
            raw = json.loads(row["data_json"]) if row["data_json"] else {}
            data = raw.get("data", raw)
            
            # Look for signal_metadata (new schema) OR legacy fields
            sig = data.get("signal_metadata", {})
            
            # Fallback: reconstruct from legacy fields
            if not sig:
                model = (data.get("ai_model") or data.get("model") or 
                        (data.get("identity", {}).get("model") if isinstance(data.get("identity"), dict) else None) or
                        "")
                port = data.get("daemon_port") or data.get("port") or ""
                if not model or not port:
                    continue
                sig = {
                    "port": port,
                    "model_id": model,
                    "model_tier": "unknown",
                    "inference_latency_ms": 0.0,
                    "tokens_out": 0,
                    "quality_score": 0.5,  # Default 0.5 for legacy
                    "cost_usd": 0.0,
                }
            
            port = sig.get("port", "")
            model_id = sig.get("model_id", "")
            model_tier = sig.get("model_tier", "unknown")
            
            if not port or not model_id:
                continue
            
            key = (port, model_id, model_tier)
            if key not in aggregates:
                aggregates[key] = {
                    "latencies": [],
                    "qualities": [],
                    "costs": [],
                    "tokens_out": [],
                    "count": 0,
                    "last_seen": "",
                }
            
            agg = aggregates[key]
            agg["count"] += 1
            if sig.get("inference_latency_ms", 0) > 0:
                agg["latencies"].append(sig["inference_latency_ms"])
            if sig.get("quality_score", 0) > 0:
                agg["qualities"].append(sig["quality_score"])
            if sig.get("cost_usd", 0) > 0:
                agg["costs"].append(sig["cost_usd"])
            if sig.get("tokens_out", 0) > 0:
                agg["tokens_out"].append(sig["tokens_out"])
            
            ts = sig.get("timestamp") or row["timestamp"] or ""
            if ts > agg["last_seen"]:
                agg["last_seen"] = ts
                
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    
    # Compute pheromone scores
    now = datetime.now(timezone.utc)
    scores = []
    
    for (port, model_id, model_tier), agg in aggregates.items():
        avg_lat = sum(agg["latencies"]) / len(agg["latencies"]) if agg["latencies"] else 0.0
        avg_qual = sum(agg["qualities"]) / len(agg["qualities"]) if agg["qualities"] else 0.5
        total_cost = sum(agg["costs"])
        avg_tok = sum(agg["tokens_out"]) / len(agg["tokens_out"]) if agg["tokens_out"] else 0.0
        
        # Compute age for evaporation
        age_hours = 0.0
        if agg["last_seen"]:
            try:
                last = datetime.fromisoformat(agg["last_seen"].replace("Z", "+00:00"))
                age_hours = (now - last).total_seconds() / 3600.0
            except (ValueError, TypeError):
                pass
        
        # Evaporation: decay = (1 - rate) ^ age_hours
        evap = max(MIN_PHEROMONE, (1 - EVAPORATION_RATE) ** age_hours)
        
        # Composite pheromone: quality^alpha / (latency_norm^beta * cost_norm^gamma)
        # Normalize latency: 1.0 at 1000ms, scale proportionally
        lat_norm = max(0.01, avg_lat / 1000.0) if avg_lat > 0 else 1.0
        # Normalize cost: 1.0 at $0.001, scale proportionally (free = 0.001)
        cost_norm = max(0.001, total_cost / max(1, agg["count"])) if total_cost > 0 else 0.001
        
        # Pheromone = quality^alpha / (latency^beta * cost^gamma) * evaporation * volume_bonus
        volume_bonus = min(2.0, 1.0 + math.log10(max(1, agg["count"])))
        
        pheromone = (
            (avg_qual ** QUALITY_WEIGHT) /
            (lat_norm ** SPEED_WEIGHT * cost_norm ** COST_WEIGHT)
        ) * evap * volume_bonus
        
        scores.append(PheromoneScore(
            port=port,
            model_id=model_id,
            model_tier=model_tier,
            total_inferences=agg["count"],
            avg_latency_ms=round(avg_lat, 1),
            avg_quality=round(avg_qual, 3),
            total_cost_usd=round(total_cost, 6),
            avg_tokens_out=round(avg_tok, 1),
            pheromone_strength=round(pheromone, 4),
            last_seen=agg["last_seen"],
            age_hours=round(age_hours, 2),
            evaporation_factor=round(evap, 4),
        ))
    
    # Sort by pheromone strength descending
    scores.sort(key=lambda s: s.pheromone_strength, reverse=True)
    return scores


# ═══════════════════════════════════════════════════════════════
# § 6  SCATTER-GATHER COORDINATOR
# ═══════════════════════════════════════════════════════════════

def recommend_tiers(pheromone_scores: list[PheromoneScore] = None) -> dict[str, dict]:
    """
    For each port, recommend which MAP-Elite tier to use next.
    
    ACO-inspired: follow the strongest pheromone trail per port,
    but with exploration probability (10%) to try other tiers.
    
    Social Spider Optimization (SSO) twist: 
    Vibration strength = pheromone_strength / distance.
    Stronger vibrations from successful model-port combos attract attention.
    
    Returns dict: port -> {recommended_tier, recommended_model, pheromone, reason}
    """
    if pheromone_scores is None:
        pheromone_scores = compute_pheromone_scores()
    
    commanders = build_port_commanders()
    recommendations = {}
    
    for port, cmd in commanders.items():
        # Find all pheromone scores for this port
        port_scores = [s for s in pheromone_scores if s.port == port]
        
        if not port_scores:
            # No pheromone data → default to apex_speed (safe default)
            default = cmd.apex_speed or cmd.apex_cost
            recommendations[port] = {
                "recommended_tier": ModelTier.APEX_SPEED.value,
                "recommended_model": default.model_id if default else "unknown",
                "pheromone": 0.0,
                "reason": "No pheromone data — defaulting to apex_speed",
                "exploration": False,
                "signal_count": 0,
            }
            continue
        
        # Sort by pheromone strength
        port_scores.sort(key=lambda s: s.pheromone_strength, reverse=True)
        best = port_scores[0]
        
        # 10% exploration probability — try a DIFFERENT tier
        import random
        exploring = random.random() < 0.10
        
        if exploring and len(port_scores) > 1:
            # Pick second-best or random alternative
            alt = port_scores[1] if len(port_scores) > 1 else port_scores[0]
            recommendations[port] = {
                "recommended_tier": alt.model_tier,
                "recommended_model": alt.model_id,
                "pheromone": alt.pheromone_strength,
                "reason": f"EXPLORATION: trying {alt.model_id} (pheromone {alt.pheromone_strength}) instead of best {best.model_id} ({best.pheromone_strength})",
                "exploration": True,
                "signal_count": sum(s.total_inferences for s in port_scores),
            }
        else:
            recommendations[port] = {
                "recommended_tier": best.model_tier,
                "recommended_model": best.model_id,
                "pheromone": best.pheromone_strength,
                "reason": f"Best pheromone: {best.model_id} with {best.total_inferences} inferences, avg quality {best.avg_quality}, avg latency {best.avg_latency_ms}ms",
                "exploration": False,
                "signal_count": sum(s.total_inferences for s in port_scores),
            }
    
    return recommendations


# ═══════════════════════════════════════════════════════════════
# § 7  SIGNAL AUDIT — Check Current Event Metadata Health
# ═══════════════════════════════════════════════════════════════

def audit_signal_quality(hours_back: float = 24.0) -> dict:
    """
    Audit how many stigmergy events include proper signal_metadata
    vs. legacy/missing metadata. This measures the swarm's self-awareness.
    """
    conn = _get_db_ro()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    
    rows = conn.execute("""
        SELECT event_type, data_json 
        FROM stigmergy_events
        WHERE timestamp > ? AND event_type LIKE 'hfo.gen89.%'
        ORDER BY id DESC
    """, (cutoff,)).fetchall()
    conn.close()
    
    total = 0
    has_signal_metadata = 0
    has_legacy_model = 0
    no_model_info = 0
    by_event_type: dict[str, dict] = {}
    
    for row in rows:
        total += 1
        etype = row["event_type"]
        
        if etype not in by_event_type:
            by_event_type[etype] = {"total": 0, "has_signal": 0, "has_legacy": 0, "no_model": 0}
        by_event_type[etype]["total"] += 1
        
        try:
            raw = json.loads(row["data_json"]) if row["data_json"] else {}
            data = raw.get("data", raw)
            
            if "signal_metadata" in data:
                has_signal_metadata += 1
                by_event_type[etype]["has_signal"] += 1
            elif any(k in data for k in ("ai_model", "model")):
                has_legacy_model += 1
                by_event_type[etype]["has_legacy"] += 1
            elif isinstance(data.get("identity"), dict) and "model" in data["identity"]:
                has_legacy_model += 1
                by_event_type[etype]["has_legacy"] += 1
            else:
                no_model_info += 1
                by_event_type[etype]["no_model"] += 1
        except (json.JSONDecodeError, TypeError):
            no_model_info += 1
            by_event_type[etype]["no_model"] += 1
    
    signal_pct = (has_signal_metadata / total * 100) if total > 0 else 0
    legacy_pct = (has_legacy_model / total * 100) if total > 0 else 0
    blind_pct = (no_model_info / total * 100) if total > 0 else 0
    
    # Grade the signal quality
    if signal_pct >= 80:
        grade = "A"
    elif signal_pct + legacy_pct >= 70:
        grade = "B"
    elif signal_pct + legacy_pct >= 50:
        grade = "C"
    elif legacy_pct >= 30:
        grade = "D"
    else:
        grade = "F"
    
    return {
        "hours_back": hours_back,
        "total_events": total,
        "has_signal_metadata": has_signal_metadata,
        "has_legacy_model": has_legacy_model,
        "no_model_info": no_model_info,
        "signal_pct": round(signal_pct, 1),
        "legacy_pct": round(legacy_pct, 1),
        "blind_pct": round(blind_pct, 1),
        "grade": grade,
        "by_event_type": dict(sorted(
            by_event_type.items(),
            key=lambda x: x[1]["total"],
            reverse=True,
        )),
    }


# ═══════════════════════════════════════════════════════════════
# § 8  APEX INVOCATION — Any Port, Any Tier
# ═══════════════════════════════════════════════════════════════

def apex_invoke(port: str, tier: str = "apex_intelligence", 
                prompt: str = "", dry_run: bool = False) -> dict:
    """
    Invoke the apex model for a given port at the specified tier.
    Uses the MAP-Elite registry to select the correct model.
    
    For Ollama models: calls ollama.chat()
    For Gemini models: uses hfo_gemini_models.create_gemini_client()
    
    Returns dict with response + full signal_metadata.
    """
    commanders = build_port_commanders()
    
    if port not in commanders:
        return {"error": f"Unknown port: {port}. Valid: P0-P7"}
    
    cmd = commanders[port]
    tier_enum = ModelTier(tier)
    exemplar = cmd.exemplars.get(tier_enum)
    
    if not exemplar:
        return {"error": f"No exemplar for {port} tier {tier}"}
    
    # Build signal metadata
    sig = SignalMetadata(
        port=port,
        commander=cmd.commander,
        daemon_name=f"apex_invoke_{port}",
        daemon_version="v1.0",
        model_id=exemplar.model_id,
        model_family=exemplar.model_family,
        model_params_b=exemplar.params_billions,
        model_provider=exemplar.provider.value,
        model_tier=tier,
        vram_gb=exemplar.vram_gb,
        task_type="apex_synthesis",
    )
    
    if dry_run:
        return {
            "dry_run": True,
            "port": port,
            "tier": tier,
            "model": exemplar.model_id,
            "provider": exemplar.provider.value,
            "signal_metadata": sig.to_dict(),
        }
    
    start_ms = time.time() * 1000
    result = {"response_text": "", "thinking_text": ""}
    
    if exemplar.provider == ModelProvider.OLLAMA:
        # Call Ollama
        try:
            import urllib.request
            payload = json.dumps({
                "model": exemplar.model_id,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 4096},
            }).encode()
            
            ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            req = urllib.request.Request(
                f"{ollama_base}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = json.loads(resp.read())
                result["response_text"] = body.get("response", "")
                sig.tokens_in = body.get("prompt_eval_count", 0)
                sig.tokens_out = body.get("eval_count", 0)
                
        except Exception as e:
            result["error"] = str(e)
    
    elif exemplar.provider in (ModelProvider.GEMINI_FREE, ModelProvider.GEMINI_VERTEX):
        # Call Gemini
        try:
            from hfo_gemini_models import create_gemini_client
            from google.genai import types
            
            client, mode = create_gemini_client()
            config_kwargs = {"temperature": 0.7, "max_output_tokens": 8192}
            
            if exemplar.supports_thinking:
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=4096,
                )
            
            config = types.GenerateContentConfig(**config_kwargs)
            response = client.models.generate_content(
                model=exemplar.model_id,
                contents=prompt,
                config=config,
            )
            
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'thought') and part.thought:
                        result["thinking_text"] += (part.text or "")
                    else:
                        result["response_text"] += (part.text or "")
            
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                sig.tokens_in = getattr(usage, 'prompt_token_count', 0)
                sig.tokens_out = getattr(usage, 'candidates_token_count', 0)
                sig.tokens_thinking = getattr(usage, 'thoughts_token_count', 0) if hasattr(usage, 'thoughts_token_count') else 0
                
                # Cost calculation
                model_specs = _GEMINI_MODELS.get(exemplar.model_id)
                if model_specs:
                    sig.cost_usd = round(
                        (sig.tokens_out + sig.tokens_thinking) / 1_000_000 * model_specs.cost_per_1m_tokens, 6
                    )
                    
        except Exception as e:
            result["error"] = str(e)
    
    # Record timing
    elapsed_ms = time.time() * 1000 - start_ms
    sig.inference_latency_ms = round(elapsed_ms, 1)
    
    # Self-assess quality (basic: response length proportional to quality)
    resp_len = len(result.get("response_text", ""))
    if resp_len > 2000:
        sig.quality_score = 0.8
    elif resp_len > 500:
        sig.quality_score = 0.6
    elif resp_len > 100:
        sig.quality_score = 0.4
    else:
        sig.quality_score = 0.2
    sig.quality_method = "response_length_heuristic"
    
    if "error" in result:
        sig.quality_score = 0.0
        sig.quality_method = "error"
    
    result["signal_metadata"] = sig.to_dict()
    result["model"] = exemplar.model_id
    result["port"] = port
    result["tier"] = tier
    result["elapsed_ms"] = round(elapsed_ms, 1)
    
    return result


def write_apex_event(result: dict) -> int:
    """Write an apex invocation result as a stigmergy event with signal_metadata."""
    conn = _get_db_rw()
    now = datetime.now(timezone.utc).isoformat()
    port = result.get("port", "??")
    tier = result.get("tier", "??")
    model = result.get("model", "??")
    
    event_type = f"hfo.gen{GEN}.map_elite.apex_invoke"
    subject = f"apex:{port}:{tier}:{model}"
    
    data = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": SOURCE_TAG,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "data": {
            "port": port,
            "tier": tier,
            "model": model,
            "response_length": len(result.get("response_text", "")),
            "thinking_length": len(result.get("thinking_text", "")),
            "elapsed_ms": result.get("elapsed_ms", 0),
            "error": result.get("error"),
            "signal_metadata": result.get("signal_metadata", {}),
            # Store response (truncated for event size)
            "response_preview": result.get("response_text", "")[:5000],
        },
    }
    
    payload = json.dumps(data, sort_keys=True)
    content_hash = hashlib.sha256(payload.encode()).hexdigest()
    
    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, SOURCE_TAG, payload, content_hash),
    )
    conn.commit()
    row_id = cur.lastrowid or 0
    conn.close()
    return row_id


# ═══════════════════════════════════════════════════════════════
# § 9  DISPLAY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def display_registry(as_json: bool = False):
    """Display the full MAP-Elite model grid."""
    commanders = build_port_commanders()
    
    if as_json:
        out = {}
        for port, cmd in commanders.items():
            out[port] = {
                "word": cmd.word,
                "commander": cmd.commander,
                "exemplars": {
                    tier.value: {
                        "model_id": ex.model_id,
                        "model_family": ex.model_family,
                        "params_b": ex.params_billions,
                        "provider": ex.provider.value,
                        "vram_gb": ex.vram_gb,
                        "est_tok_per_sec": ex.est_tok_per_sec,
                        "cost_per_1m": ex.cost_per_1m_tokens,
                        "thinking": ex.supports_thinking,
                    }
                    for tier, ex in cmd.exemplars.items()
                },
            }
        print(json.dumps(out, indent=2))
        return
    
    print("=" * 100)
    print("  MAP-ELITE PORT COMMANDER GRID — 8 Ports × 3 Tiers = 24 Exemplar Slots")
    print("  Quality-Diversity Selection: Intelligence | Speed | Cost")
    print("=" * 100)
    
    for port, cmd in commanders.items():
        print(f"\n  {port} {cmd.word} — {cmd.commander}")
        print(f"  {'─' * 94}")
        print(f"  {'Tier':<22s} {'Model':<25s} {'Family':<16s} {'Params':<8s} {'VRAM':<7s} {'tok/s':<7s} {'$/1M':<8s} {'Think':>5s}")
        print(f"  {'─' * 94}")
        
        for tier in [ModelTier.APEX_INTELLIGENCE, ModelTier.APEX_SPEED, ModelTier.APEX_COST]:
            ex = cmd.exemplars.get(tier)
            if ex:
                tier_label = tier.value.replace("apex_", "").upper()
                params = f"{ex.params_billions:.1f}B" if ex.params_billions > 0 else "cloud"
                vram = f"{ex.vram_gb:.1f}G" if ex.vram_gb > 0 else "—"
                tps = f"{ex.est_tok_per_sec:.0f}" if ex.est_tok_per_sec > 0 else "—"
                cost = f"${ex.cost_per_1m_tokens:.2f}" if ex.cost_per_1m_tokens > 0 else "FREE"
                think = "✓" if ex.supports_thinking else "—"
                print(f"  {tier_label:<22s} {ex.model_id:<25s} {ex.model_family:<16s} {params:<8s} {vram:<7s} {tps:<7s} {cost:<8s} {think:>5s}")
    
    # Summary statistics
    all_models_used = set()
    all_families = set()
    for cmd in commanders.values():
        for ex in cmd.exemplars.values():
            all_models_used.add(ex.model_id)
            all_families.add(ex.model_family)
    
    print(f"\n  {'═' * 94}")
    print(f"  Grid: 8 ports × 3 tiers = 24 slots | {len(all_models_used)} unique models | {len(all_families)} families")
    print(f"  Families: {', '.join(sorted(all_families))}")
    print(f"  {'═' * 94}")


def display_pheromone(as_json: bool = False):
    """Display ACO pheromone scores."""
    scores = compute_pheromone_scores()
    
    if as_json:
        print(json.dumps([asdict(s) for s in scores], indent=2))
        return
    
    if not scores:
        print("  No pheromone data found (no events with model metadata in last 24h)")
        return
    
    print("=" * 100)
    print("  ACO PHEROMONE SCORES — Ant Colony Optimization Model Rankings")
    print("  Pheromone = quality^2 / (latency × cost) × evaporation × volume")
    print("=" * 100)
    
    print(f"\n  {'Port':<5s} {'Model':<25s} {'Tier':<20s} {'Inferences':<11s} {'Avg Lat':<10s} {'Avg Qual':<9s} {'Cost$':<8s} {'Evap':<6s} {'Pheromone':>10s}")
    print(f"  {'─' * 98}")
    
    for s in scores:
        lat_str = f"{s.avg_latency_ms:.0f}ms" if s.avg_latency_ms > 0 else "—"
        cost_str = f"${s.total_cost_usd:.4f}" if s.total_cost_usd > 0 else "FREE"
        print(f"  {str(s.port):<5s} {str(s.model_id):<25s} {str(s.model_tier):<20s} {s.total_inferences:<11d} {lat_str:<10s} {s.avg_quality:<9.3f} {cost_str:<8s} {s.evaporation_factor:<6.2f} {s.pheromone_strength:>10.4f}")
    
    print(f"\n  Total model-port combinations with pheromone: {len(scores)}")


def display_recommendations(as_json: bool = False):
    """Display scatter-gather coordinator recommendations."""
    scores = compute_pheromone_scores()
    recs = recommend_tiers(scores)
    
    if as_json:
        print(json.dumps(recs, indent=2))
        return
    
    print("=" * 100)
    print("  SCATTER-GATHER COORDINATOR — ACO + SSO Tier Recommendations")
    print("  Social Spider Optimization: follow strongest vibration (90%) or explore (10%)")
    print("=" * 100)
    
    commanders = build_port_commanders()
    
    for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
        rec = recs.get(port, {})
        cmd = commanders.get(port)
        word = cmd.word if cmd else "?"
        
        tier = rec.get("recommended_tier", "?")
        model = rec.get("recommended_model", "?")
        pheromone = rec.get("pheromone", 0)
        exploring = "🔍 EXPLORE" if rec.get("exploration") else "🐜 FOLLOW"
        signals = rec.get("signal_count", 0)
        reason = rec.get("reason", "")
        
        print(f"\n  {port} {word}: {exploring}")
        print(f"    Tier: {tier} → Model: {model}")
        print(f"    Pheromone: {pheromone:.4f} | Signals: {signals}")
        print(f"    Reason: {reason}")


def display_signal_audit(as_json: bool = False):
    """Display signal quality audit."""
    audit = audit_signal_quality()
    
    if as_json:
        print(json.dumps(audit, indent=2))
        return
    
    print("=" * 80)
    print("  SIGNAL METADATA AUDIT — Swarm Self-Awareness Score")
    print("=" * 80)
    
    print(f"\n  Grade: {audit['grade']} ({audit['hours_back']}h lookback)")
    print(f"  Total events:      {audit['total_events']}")
    print(f"  signal_metadata:   {audit['has_signal_metadata']} ({audit['signal_pct']}%)")
    print(f"  Legacy model info: {audit['has_legacy_model']} ({audit['legacy_pct']}%)")
    print(f"  BLIND (no model):  {audit['no_model_info']} ({audit['blind_pct']}%)")
    
    print(f"\n  Top event types:")
    for etype, counts in list(audit["by_event_type"].items())[:15]:
        sig = counts["has_signal"]
        leg = counts["has_legacy"]
        no_m = counts["no_model"]
        total = counts["total"]
        status = "✓" if sig > 0 else ("~" if leg > 0 else "✗")
        print(f"    {status} {etype:<50s} total={total:>4d} signal={sig:>3d} legacy={leg:>3d} blind={no_m:>3d}")


# ═══════════════════════════════════════════════════════════════
# § 10  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="MAP-Elite Port Commander Framework — 8^N Quality-Diversity Model Selection",
    )
    parser.add_argument("--registry", action="store_true",
                       help="Show MAP-Elite model grid (8 ports × 3 tiers)")
    parser.add_argument("--pheromone", action="store_true",
                       help="Show ACO pheromone scores from stigmergy")
    parser.add_argument("--recommend", action="store_true",
                       help="Scatter-gather tier recommendations")
    parser.add_argument("--apex", action="store_true",
                       help="Run apex intelligence on a port")
    parser.add_argument("--port", type=str, default="P4",
                       help="Port for apex invocation (default: P4)")
    parser.add_argument("--tier", type=str, default="apex_intelligence",
                       choices=["apex_intelligence", "apex_speed", "apex_cost"],
                       help="MAP-Elite tier (default: apex_intelligence)")
    parser.add_argument("--prompt", type=str, default="",
                       help="Prompt for apex invocation")
    parser.add_argument("--signal-schema", action="store_true",
                       help="Show standardized signal metadata schema")
    parser.add_argument("--audit-signals", action="store_true",
                       help="Audit current signal quality across stigmergy")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview without executing")
    parser.add_argument("--json", action="store_true",
                       help="Machine-readable JSON output")
    parser.add_argument("--stigmergy", action="store_true",
                       help="Write results to SSOT")
    parser.add_argument("--hours", type=float, default=24.0,
                       help="Hours lookback for pheromone/audit (default: 24)")
    args = parser.parse_args()
    
    if args.signal_schema:
        if args.json:
            print(json.dumps(SIGNAL_SCHEMA_DOC, indent=2))
        else:
            print("=" * 80)
            print("  SIGNAL METADATA SCHEMA v1.0 — ACO Pheromone Fields")
            print("=" * 80)
            print(f"\n  Embedding key: '{SIGNAL_SCHEMA_DOC['embedding_key']}'")
            print(f"  Purpose: {SIGNAL_SCHEMA_DOC['purpose']}")
            print(f"\n  {'Field':<24s} {'Type':<8s} {'Req':<5s} {'Example':<30s} Description")
            print(f"  {'─' * 90}")
            for fname, fspec in SIGNAL_SCHEMA_DOC["fields"].items():
                req = "YES" if fspec.get("required") else "—"
                print(f"  {fname:<24s} {fspec['type']:<8s} {req:<5s} {str(fspec['example']):<30s} {fspec['doc']}")
        return
    
    if args.registry:
        display_registry(args.json)
        return
    
    if args.pheromone:
        display_pheromone(args.json)
        return
    
    if args.recommend:
        display_recommendations(args.json)
        return
    
    if args.audit_signals:
        display_signal_audit(args.json)
        return
    
    if args.apex:
        port = args.port.upper()
        prompt = args.prompt or f"You are the {port} commander of HFO Gen89. Assess the current state of your port's domain and identify the single highest-leverage action to take next."
        
        print(f"\n  MAP-Elite Apex Invocation: {port} @ {args.tier}")
        result = apex_invoke(port, args.tier, prompt, args.dry_run)
        
        if args.json:
            # Don't dump full response text in JSON, too large
            out = {k: v for k, v in result.items() if k != "response_text"}
            out["response_length"] = len(result.get("response_text", ""))
            print(json.dumps(out, indent=2))
        elif args.dry_run:
            print(f"  [DRY RUN] Would invoke {result.get('model')} on {port}")
            print(f"  Signal metadata: {json.dumps(result.get('signal_metadata', {}), indent=2)}")
        else:
            # Display response
            if result.get("error"):
                print(f"  [ERROR] {result['error']}")
            else:
                print(f"\n  Model: {result.get('model')} | Elapsed: {result.get('elapsed_ms', 0):.0f}ms")
                sig = result.get("signal_metadata", {})
                print(f"  Tokens: {sig.get('tokens_in', 0)} in / {sig.get('tokens_out', 0)} out")
                print(f"  Quality: {sig.get('quality_score', 0):.2f} ({sig.get('quality_method', 'none')})")
                print(f"\n{'─' * 80}")
                print(result.get("response_text", "")[:8000])
            
            if args.stigmergy:
                row_id = write_apex_event(result)
                print(f"\n  Written to SSOT row {row_id}")
        return
    
    # Default: show overview
    print("=" * 80)
    print("  MAP-ELITE PORT COMMANDER FRAMEWORK v1.0")
    print("  8^N Quality-Diversity Model Selection + ACO Stigmergy Coordination")
    print("=" * 80)
    print()
    print("  Commands:")
    print("    --registry         Show 24-slot model grid (8 ports × 3 tiers)")
    print("    --pheromone        Show ACO pheromone scores from stigmergy trail")
    print("    --recommend        Scatter-gather coordinator tier recommendations")
    print("    --apex --port P4   Run apex intelligence model on port P4")
    print("    --signal-schema    Show standardized signal metadata schema")
    print("    --audit-signals    Audit signal quality across stigmergy events")
    print("    --json             Machine-readable output")
    print()
    
    # Quick status
    commanders = build_port_commanders()
    total_models = len(set(
        ex.model_id for cmd in commanders.values() for ex in cmd.exemplars.values()
    ))
    total_families = len(set(
        ex.model_family for cmd in commanders.values() for ex in cmd.exemplars.values()
    ))
    
    print(f"  Grid: 8 ports × 3 tiers = 24 slots")
    print(f"  Models: {total_models} unique across {total_families} families")
    print(f"  Providers: Ollama (local free) + Gemini (free+vertex) + Claude (copilot)")
    
    audit = audit_signal_quality()
    print(f"  Signal Grade: {audit['grade']} ({audit['signal_pct']}% new schema, {audit['legacy_pct']}% legacy, {audit['blind_pct']}% blind)")
    print()


if __name__ == "__main__":
    main()
