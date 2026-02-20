#!/usr/bin/env python3
"""
hfo_p2_chimera_loop.py — HFO P2 Empowered Cursed Chimera Loop

Evolutionary DSE (Design Space Exploration) / AoA (Analysis of Alternatives)
for optimizing the P4 Red Regnant GitHub Copilot agent persona.

Architecture:
  - SBE/ATDD-based AI agent loops with external state in stigmergy
  - Genome: Structured persona traits (mutable sections of system prompt)
  - Fitness: Multi-objective (coding, gates, adversarial, Meadows, efficiency)
  - Selection: Tournament + Pareto non-dominated sorting
  - Operators: Trait mutation, crossover, interpolation
  - Evaluation grid: 2x2 matrix (small/large × low/high intelligence)
  - All state persisted to SSOT stigmergy_events

The "chimera" is the composite persona — a blend of trait alleles that
may include contradictory or "cursed" combinations (Ralph Wiggums component)
alongside "empowered" high-performance alleles. The evolutionary pressure
finds which chimeric blends actually work best across model heterogeneity.

Port assignment: P2 SHAPE (Mirror Magus) — Creation / Models
  P2 workflow: PARSE → CONSTRAIN → GENERATE → VALIDATE → MEDAL

Usage:
  # Initialize population + run 1 generation on 2x2 grid
  python hfo_p2_chimera_loop.py --generations 1 --pop-size 4 --problems 5

  # Full evolutionary run
  python hfo_p2_chimera_loop.py --generations 5 --pop-size 8 --problems 10

  # Resume from SSOT stigmergy (reads last generation)
  python hfo_p2_chimera_loop.py --resume --generations 3

  # Quick test with single model
  python hfo_p2_chimera_loop.py --test-model gemma3:4b --problems 3

Design sources: SSOT docs 129,317,128,12,4,263
  + MAP-ELITES (Mouret & Clune 2015)
  + NSGA-II multi-objective (Deb et al. 2002)
"""

import argparse
import copy
import hashlib
import json
import math
import os
import random
import re
import secrets
import signal
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
TIMEOUT_GENERATE = 600  # generous for reasoning models (deepseek-r1 think chains)
TIMEOUT_TEST = 10
MAX_TOKENS = 4096  # reasoning models need headroom for <think> chains

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
DB_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
GEN = os.environ.get("HFO_GENERATION", "89")

# ---------------------------------------------------------------------------
# 2x2 Model Grid: Size (small/large) × Intelligence (low/high)
# ---------------------------------------------------------------------------

MODEL_GRID = {
    "small_low":  "gemma3:4b",         # 3.1GB — lightweight, general
    "small_high": "qwen2.5-coder:7b",  # 4.4GB — dedicated code model (fast, no think chains)
    "large_low":  "phi4:14b",          # 8.4GB — general purpose
    "large_high": "gemma3:12b",        # 7.6GB — larger gemma (fits 16GB VRAM)
}
# NOTE: deepseek-r1:8b → 500 on Intel Arc Vulkan; qwen3:30b-a3b → OOM (17GB > 16GB VRAM)
# NOTE: qwen3:8b → 590s/problem (think chains), deepseek-r1:8b → 500 error. Both unsuitable.

# Axis labels for MAP-ELITES style archiving
GRID_AXES = {
    "size":         ["small", "large"],
    "intelligence": ["low", "high"],
}

# ---------------------------------------------------------------------------
# Persona Genome — The Evolvable Traits
# ---------------------------------------------------------------------------
# Each trait has a name, a set of alleles (variants), and a current value.
# The chimera persona is assembled from the combination of all trait alleles.
# "Cursed" alleles are intentionally weird/provocative — evolutionary pressure
# determines if they're actually useful (the Ralph Wiggums insight).

TRAIT_ALLELES = {
    "tone": {
        "desc": "Voice and communication style",
        "alleles": [
            "cold_analytical",       # Precise, clinical, no emotion
            "adversarial_coach",     # Tough love, challenges everything
            "socratic_inquisitor",   # Questions back, forces reasoning
            "war_room_commander",    # Military precision, SITREP style
            "chaos_gremlin",         # CURSED: chaotic but insightful
            "zen_master",            # Calm, koan-like observations
            "pair_programmer",       # Collaborative, thinking aloud
        ],
    },
    "adversarial_depth": {
        "desc": "How deeply to probe for weaknesses",
        "alleles": [
            "surface_scan",          # Quick checks, obvious issues only
            "structured_challenge",  # Systematic threat enumeration
            "red_team_full",         # Full adversarial analysis per step
            "chaos_monkey",          # CURSED: random deep probes
            "stryker_mutation",      # Mutation testing mindset
            "formal_verification",   # Mathematical proof-mindset
        ],
    },
    "reasoning_style": {
        "desc": "How to approach problem decomposition",
        "alleles": [
            "chain_of_thought",      # Step-by-step linear reasoning
            "tree_of_thought",       # Branching exploration
            "analogical",            # Reasoning by analogy/metaphor
            "first_principles",      # Decompose to axioms
            "pattern_matching",      # Match to known patterns
            "backwards_chaining",    # Start from goal, work backward
            "ralph_wiggums",         # CURSED: naive but surprising
        ],
    },
    "gate_philosophy": {
        "desc": "How to treat PREY8 structured gate fields",
        "alleles": [
            "minimal_compliance",    # Fill fields to pass, no more
            "rich_documentation",    # Detailed field content
            "adversarial_gates",     # Use gates as attack surface review
            "pedagogical",           # Gates as teaching moments
            "ceremonial",            # CURSED: over-the-top ritualistic
        ],
    },
    "meadows_strategy": {
        "desc": "How to select leverage levels (1-12)",
        "alleles": [
            "always_high",           # Default to L9-L12
            "adaptive",              # Match level to problem complexity
            "escalating",            # Start low, climb as needed
            "contrarian",            # CURSED: intentionally mismatched
            "meta_systemic",         # Always think at system level
        ],
    },
    "sbe_style": {
        "desc": "How to write Given/When/Then specifications",
        "alleles": [
            "terse",                 # Minimal, just the facts
            "comprehensive",         # Detailed preconditions/postconditions
            "invariant_first",       # Lead with safety invariants
            "edge_case_driven",      # Focus on boundaries
            "narrative",             # CURSED: story-like specifications
        ],
    },
    "trust_posture": {
        "desc": "Default trust level for bronze data",
        "alleles": [
            "zero_trust",            # Verify everything, trust nothing
            "cautious_optimist",     # Trust but verify critical claims
            "paranoid",              # Assume hostile context
            "bayesian",              # Update trust incrementally
            "dgaf_chaos",            # CURSED: trust randomly
        ],
    },
    "artifact_discipline": {
        "desc": "Code output style and discipline",
        "alleles": [
            "minimal_diff",          # Smallest change possible
            "comprehensive_rewrite", # Full implementations
            "test_first",            # TDD: write test, then code
            "doc_first",             # Document, then implement
            "spike_and_refine",      # Quick prototype, then harden
        ],
    },
}

# How many traits in a genome
NUM_TRAITS = len(TRAIT_ALLELES)
TRAIT_NAMES = list(TRAIT_ALLELES.keys())

# ---------------------------------------------------------------------------
# META-GENOME — Layer 3+4 Mutation (Fitness Weights + Selection Strategy)
# ---------------------------------------------------------------------------
# Universal Darwinism: everything gets mutated.
# The meta-genome controls HOW evolution works, not just WHAT evolves.
# This is the hyperheuristic: evolving the heuristic that selects heuristics.

META_TRAITS = {
    "fitness_weights": {
        "desc": "How to weight fitness dimensions (coding,gate,adv,meadows,token,latency)",
        "alleles": {
            "balanced":           [0.30, 0.25, 0.15, 0.10, 0.10, 0.10],
            "code_dominant":      [0.50, 0.15, 0.10, 0.10, 0.08, 0.07],
            "gate_dominant":      [0.20, 0.40, 0.15, 0.10, 0.08, 0.07],
            "adversarial_focus":  [0.20, 0.20, 0.35, 0.10, 0.08, 0.07],
            "efficiency_focus":   [0.20, 0.20, 0.10, 0.10, 0.25, 0.15],
        },
    },
    "aggregation_method": {
        "desc": "How to combine fitness dimensions into a single score",
        "alleles": {
            "weighted_sum":    "weighted_sum",
            "geometric_mean":  "geometric_mean",
            "harmonic_mean":   "harmonic_mean",
            "min_of_all":      "min_of_all",
        },
    },
    "selection_pressure": {
        "desc": "Tournament size for selection (higher = more pressure)",
        "alleles": {
            "tournament_2": 2,
            "tournament_3": 3,
            "tournament_5": 5,
        },
    },
    "prompt_template": {
        "desc": "How to structure the eval prompt sent to models",
        "alleles": {
            "json_structured":     "json_structured",
            "minimal_code_only":   "minimal_code_only",
            "chain_of_thought":    "chain_of_thought",
        },
    },
}

META_TRAIT_NAMES = list(META_TRAITS.keys())
DEFAULT_META_TRAITS = {
    "fitness_weights": "balanced",
    "aggregation_method": "weighted_sum",
    "selection_pressure": "tournament_3",
    "prompt_template": "json_structured",
}

# Prompt template variants for Layer 2 mutation
PROMPT_TEMPLATES = {
    "json_structured": """Solve this coding problem. You MUST output a JSON object with these fields:

{{
    "observations": "What you noticed about the problem (comma-separated)",
    "memory_refs": "Concepts/patterns you're drawing on",
    "stigmergy_digest": "Key patterns from prior work",
    "shared_data_refs": "Cross-references to related concepts",
    "navigation_intent": "Your strategic approach to this problem",
    "meadows_level": <integer 1-12>,
    "meadows_justification": "Why you chose this leverage level",
    "sequential_plan": "Ordered steps to solve (comma-separated)",
    "sbe_given": "Given <precondition>",
    "sbe_when": "When <action>",
    "sbe_then": "Then <expected result>",
    "artifacts": "What you're producing",
    "p4_adversarial_check": "Edge cases, failure modes, mutation opportunities checked",
    "code": "<complete Python function>"
}}

Output ONLY the JSON. No markdown wrapping. No explanation outside JSON.
The "code" field must contain a complete, executable Python function.

Problem:
{problem_prompt}""",

    "minimal_code_only": """Write a Python function to solve this problem.
Output ONLY the function code. No explanation. No imports unless needed.

{problem_prompt}""",

    "chain_of_thought": """Solve this step-by-step.

Problem: {problem_prompt}

1. First, analyze the problem requirements
2. Consider edge cases (empty input, negative numbers, large values)
3. Write the solution as a Python function

Output your reasoning, then the final code in a ```python block.
Also output a JSON with these fields on a separate line:
{{"observations": "...", "memory_refs": "...", "stigmergy_digest": "...", "shared_data_refs": "...", "navigation_intent": "...", "meadows_level": <1-12>, "meadows_justification": "...", "sequential_plan": "...", "sbe_given": "...", "sbe_when": "...", "sbe_then": "...", "artifacts": "...", "p4_adversarial_check": "..."}}""",
}


@dataclass
class Genome:
    """A chimera persona genome — one allele per trait + meta-traits.

    Layer 1: traits (persona alleles — what the agent IS)
    Layer 2-4: meta_traits (how evolution WORKS — fitness weights,
               aggregation, selection, prompt template)
    """
    traits: dict  # {trait_name: allele_value}
    meta_traits: dict = field(default_factory=lambda: dict(DEFAULT_META_TRAITS))
    genome_id: str = ""
    generation: int = 0
    parent_ids: list = field(default_factory=list)

    def __post_init__(self):
        if not self.genome_id:
            self.genome_id = secrets.token_hex(4)
        # Ensure meta_traits has all keys with defaults
        for k, v in DEFAULT_META_TRAITS.items():
            if k not in self.meta_traits:
                self.meta_traits[k] = v

    def get_fitness_weights(self) -> dict:
        """Resolve meta-genome fitness weights allele to actual weight dict."""
        allele = self.meta_traits.get("fitness_weights", "balanced")
        weights_list = META_TRAITS["fitness_weights"]["alleles"].get(allele, [0.30, 0.25, 0.15, 0.10, 0.10, 0.10])
        dim_names = ["coding_accuracy", "gate_compliance", "adversarial_depth",
                     "meadows_alignment", "token_efficiency", "latency_score"]
        return dict(zip(dim_names, weights_list))

    def get_prompt_template(self) -> str:
        """Resolve meta-genome prompt template allele to actual prompt text."""
        allele = self.meta_traits.get("prompt_template", "json_structured")
        return PROMPT_TEMPLATES.get(allele, PROMPT_TEMPLATES["json_structured"])

    def get_tournament_size(self) -> int:
        """Resolve meta-genome selection pressure to tournament size."""
        allele = self.meta_traits.get("selection_pressure", "tournament_3")
        return META_TRAITS["selection_pressure"]["alleles"].get(allele, 3)

    def to_system_prompt(self) -> str:
        """Render this genome into a system prompt for Ollama."""
        sections = []
        sections.append(f"# P4 RED REGNANT — Chimera Persona [{self.genome_id}]")
        sections.append("")
        sections.append("You are the P4 Red Regnant, commander of Port 4 (DISRUPT) in the HFO Octree.")
        sections.append("You operate fail-closed PREY8 mosaic tiles over a 9,860-document SSOT.")
        sections.append("")

        # Tone
        tone = self.traits.get("tone", "adversarial_coach")
        tone_map = {
            "cold_analytical": "Communicate with clinical precision. No emotion, no filler. Facts and logic only.",
            "adversarial_coach": "You are a tough but fair adversarial coach. Challenge every assumption. Push for excellence through friction.",
            "socratic_inquisitor": "Respond with probing questions before giving answers. Force the operator to reason through their own assumptions.",
            "war_room_commander": "Military-grade communication. SITREPs, mission objectives, threat assessments. No wasted words.",
            "chaos_gremlin": "Inject unexpected perspectives. Break frames. Say the thing nobody expects. Find insight through creative disruption.",
            "zen_master": "Respond with calm clarity. Strip away complexity to reveal core truths. Use paradox when helpful.",
            "pair_programmer": "Think aloud collaboratively. Share your reasoning process. Invite correction.",
        }
        sections.append(f"## Communication Style")
        sections.append(tone_map.get(tone, tone_map["adversarial_coach"]))
        sections.append("")

        # Adversarial depth
        adv = self.traits.get("adversarial_depth", "structured_challenge")
        adv_map = {
            "surface_scan": "Perform quick adversarial checks on obvious failure modes only.",
            "structured_challenge": "Systematically enumerate threats using the 6-Defense SDD stack: Red-First, Structural Separation, Mutation Wall, Property Invariants, GRUDGE Guards, Adversarial Review.",
            "red_team_full": "Full red team analysis on every step. Assume hostile inputs, byzantine failures, and adversarial context. No shortcuts.",
            "chaos_monkey": "Randomly probe deep failure modes. Pick unexpected attack vectors. Test resilience through creative chaos.",
            "stryker_mutation": "Think like a mutation testing framework. For every assertion, ask: what if I mutated this? Would the tests catch it?",
            "formal_verification": "Approach correctness with mathematical rigor. State invariants formally. Prove properties when possible.",
        }
        sections.append(f"## Adversarial Depth")
        sections.append(adv_map.get(adv, adv_map["structured_challenge"]))
        sections.append("")

        # Reasoning style
        reas = self.traits.get("reasoning_style", "chain_of_thought")
        reas_map = {
            "chain_of_thought": "Reason step-by-step. Show your work. Each step must follow logically from the previous.",
            "tree_of_thought": "Explore multiple reasoning branches. Consider alternatives before committing. Prune dead ends explicitly.",
            "analogical": "Reason by analogy. Map the current problem to known patterns and extract transferable insights.",
            "first_principles": "Decompose to fundamental axioms. Build up from irreducible truths. Question every implicit assumption.",
            "pattern_matching": "Identify the problem class, recall the canonical solution pattern, adapt to specifics.",
            "backwards_chaining": "Start from the desired outcome. Work backward through required preconditions until you reach current state.",
            "ralph_wiggums": "Approach problems with naive curiosity. Ask 'dumb' questions that expose hidden assumptions. Sometimes the simplest observation reveals the deepest truth.",
        }
        sections.append(f"## Reasoning Approach")
        sections.append(reas_map.get(reas, reas_map["chain_of_thought"]))
        sections.append("")

        # Gate philosophy
        gate = self.traits.get("gate_philosophy", "rich_documentation")
        gate_map = {
            "minimal_compliance": "Fill PREY8 gate fields with the minimum required information to pass. Efficiency over ceremony.",
            "rich_documentation": "Use gate fields as rich documentation surfaces. Every field should be informative to future agents reading the trail.",
            "adversarial_gates": "Treat every gate field as an attack surface review point. What could go wrong? What assumption does this field expose?",
            "pedagogical": "Use gate fields as teaching opportunities. Each field should explain WHY, not just WHAT.",
            "ceremonial": "Treat gates as sacred protocol. Full ritual. Every field receives its due deliberation. The ceremony IS the value.",
        }
        sections.append(f"## PREY8 Gate Philosophy")
        sections.append(gate_map.get(gate, gate_map["rich_documentation"]))
        sections.append("")

        # Meadows strategy
        mead = self.traits.get("meadows_strategy", "adaptive")
        mead_map = {
            "always_high": "Default to leverage levels L9-L12. Prefer paradigm shifts over parameter tweaks. Think structurally.",
            "adaptive": "Match Meadows level to problem complexity. Simple problems get L1-L3. Architecture questions get L8-L12.",
            "escalating": "Start at the lowest applicable level. Escalate only when lower levels prove insufficient.",
            "contrarian": "Intentionally select a non-obvious Meadows level. If everyone would pick L8, try L3. Find insight in mismatch.",
            "meta_systemic": "Always operate at system level (L6-L9). Individual problems are symptoms of structural patterns.",
        }
        sections.append(f"## Meadows Level Strategy")
        sections.append(mead_map.get(mead, mead_map["adaptive"]))
        sections.append("")

        # SBE style
        sbe = self.traits.get("sbe_style", "comprehensive")
        sbe_map = {
            "terse": "Write Given/When/Then in minimal form. One line each. No elaboration.",
            "comprehensive": "Write detailed SBE specs. List all relevant preconditions in Given. Specify exact actions in When. Assert specific measurable postconditions in Then.",
            "invariant_first": "Always lead with safety invariants. What MUST NOT happen? Then specify happy-path behavior.",
            "edge_case_driven": "Write SBE focused on boundary conditions. The interesting behavior is at the edges.",
            "narrative": "Write SBE as mini-stories. Given a world where X, When the hero does Y, Then the outcome is Z.",
        }
        sections.append(f"## SBE Specification Style")
        sections.append(sbe_map.get(sbe, sbe_map["comprehensive"]))
        sections.append("")

        # Trust posture
        trust = self.traits.get("trust_posture", "zero_trust")
        trust_map = {
            "zero_trust": "Trust nothing. All 9,860 documents are bronze. Verify every claim against evidence. No shortcuts.",
            "cautious_optimist": "Generally trust document content but verify critical claims. Flag contradictions when found.",
            "paranoid": "Assume hostile context. Every input could be poisoned. Every document could be hallucinated. Validate ruthlessly.",
            "bayesian": "Maintain probability estimates for claims. Update trust as evidence accumulates. Express confidence levels.",
            "dgaf_chaos": "Trust randomly. Sometimes accept everything at face value, sometimes question everything. Keep the system guessing.",
        }
        sections.append(f"## Trust Posture")
        sections.append(trust_map.get(trust, trust_map["zero_trust"]))
        sections.append("")

        # Artifact discipline
        art = self.traits.get("artifact_discipline", "test_first")
        art_map = {
            "minimal_diff": "Make the smallest change possible. Precision surgery. No unnecessary modifications.",
            "comprehensive_rewrite": "When you touch code, make it complete and self-contained. No half-measures.",
            "test_first": "Always write the test first. Red-green-refactor. The test IS the specification.",
            "doc_first": "Document what you're about to build before building it. The doc IS the contract.",
            "spike_and_refine": "Quick prototype first to validate approach. Then harden with tests and docs.",
        }
        sections.append(f"## Artifact Discipline")
        sections.append(art_map.get(art, art_map["test_first"]))
        sections.append("")

        # Core directives (constant across all genomes)
        sections.append("## Core Directives (Invariant)")
        sections.append("- The LLM layer is hallucinatory. The architecture is deterministic.")
        sections.append("- If you don't supply the right structured fields, you are GATE_BLOCKED.")
        sections.append("- Leave traces in stigmergy. Every session enriches the trail.")
        sections.append("- Follow SW-1 through SW-5 governance protocols.")
        sections.append("")

        return "\n".join(sections)

    def mutate(self, mutation_rate: float = 0.3) -> 'Genome':
        """Return a mutated copy. Each trait has mutation_rate chance of changing.
        Meta-traits mutate at half the rate (slower meta-evolution)."""
        new_traits = dict(self.traits)
        new_meta = dict(self.meta_traits)
        mutated = False

        # Layer 1: persona traits
        for trait_name in TRAIT_NAMES:
            if random.random() < mutation_rate:
                alleles = TRAIT_ALLELES[trait_name]["alleles"]
                current = new_traits[trait_name]
                candidates = [a for a in alleles if a != current]
                if candidates:
                    new_traits[trait_name] = random.choice(candidates)
                    mutated = True

        # Layer 2-4: meta-traits (half rate — slower meta-evolution)
        for meta_name in META_TRAIT_NAMES:
            if random.random() < mutation_rate * 0.5:
                allele_keys = list(META_TRAITS[meta_name]["alleles"].keys())
                current = new_meta.get(meta_name)
                candidates = [a for a in allele_keys if a != current]
                if candidates:
                    new_meta[meta_name] = random.choice(candidates)
                    mutated = True

        if not mutated:
            # Force at least one mutation (persona trait)
            trait_name = random.choice(TRAIT_NAMES)
            alleles = TRAIT_ALLELES[trait_name]["alleles"]
            current = new_traits[trait_name]
            candidates = [a for a in alleles if a != current]
            if candidates:
                new_traits[trait_name] = random.choice(candidates)
        child = Genome(
            traits=new_traits,
            meta_traits=new_meta,
            generation=self.generation + 1,
            parent_ids=[self.genome_id],
        )
        return child

    @staticmethod
    def crossover(parent_a: 'Genome', parent_b: 'Genome') -> 'Genome':
        """Uniform crossover: each trait randomly from one parent (incl. meta-traits)."""
        new_traits = {}
        for trait_name in TRAIT_NAMES:
            if random.random() < 0.5:
                new_traits[trait_name] = parent_a.traits[trait_name]
            else:
                new_traits[trait_name] = parent_b.traits[trait_name]
        new_meta = {}
        for meta_name in META_TRAIT_NAMES:
            if random.random() < 0.5:
                new_meta[meta_name] = parent_a.meta_traits.get(meta_name, DEFAULT_META_TRAITS[meta_name])
            else:
                new_meta[meta_name] = parent_b.meta_traits.get(meta_name, DEFAULT_META_TRAITS[meta_name])
        return Genome(
            traits=new_traits,
            meta_traits=new_meta,
            generation=max(parent_a.generation, parent_b.generation) + 1,
            parent_ids=[parent_a.genome_id, parent_b.genome_id],
        )

    @staticmethod
    def random_genome(generation: int = 0) -> 'Genome':
        """Generate a random genome (persona + meta-traits)."""
        traits = {}
        for trait_name, info in TRAIT_ALLELES.items():
            traits[trait_name] = random.choice(info["alleles"])
        meta = {}
        for meta_name, info in META_TRAITS.items():
            meta[meta_name] = random.choice(list(info["alleles"].keys()))
        return Genome(traits=traits, meta_traits=meta, generation=generation)

    def fingerprint(self) -> str:
        """Short hash of trait + meta-trait combination for dedup."""
        s = json.dumps({"traits": self.traits, "meta": self.meta_traits}, sort_keys=True)
        return hashlib.sha256(s.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Fitness Metrics (Multi-Objective)
# ---------------------------------------------------------------------------

@dataclass
class FitnessVector:
    """Multi-objective fitness — one score per dimension."""
    coding_accuracy: float = 0.0     # pass@1 on eval problems (0-1)
    gate_compliance: float = 0.0     # fraction of gate fields correctly filled (0-1)
    adversarial_depth: float = 0.0   # quality score of p4_adversarial_check (0-1)
    meadows_alignment: float = 0.0   # appropriateness of Meadows level selection (0-1)
    token_efficiency: float = 0.0    # tokens per correct answer (inverted, 0-1)
    latency_score: float = 0.0       # response time score (inverted, 0-1)

    def as_list(self) -> list[float]:
        return [
            self.coding_accuracy,
            self.gate_compliance,
            self.adversarial_depth,
            self.meadows_alignment,
            self.token_efficiency,
            self.latency_score,
        ]

    def dominates(self, other: 'FitnessVector') -> bool:
        """Pareto dominance: self dominates other if >= in all, > in at least one."""
        s = self.as_list()
        o = other.as_list()
        at_least_one_better = False
        for si, oi in zip(s, o):
            if si < oi:
                return False
            if si > oi:
                at_least_one_better = True
        return at_least_one_better

    def aggregate(self, weights: dict = None, method: str = "weighted_sum") -> float:
        """Aggregate fitness using configurable method (meta-genome controlled).

        Methods:
          weighted_sum:   Standard weighted sum (current default)
          geometric_mean: Product^(1/n) — penalizes zeros harder
          harmonic_mean:  n / sum(1/x_i) — penalizes weakness harder
          min_of_all:     Bottleneck-driven — weakest dimension dominates
        """
        w = weights or {
            "coding_accuracy": 0.30,
            "gate_compliance": 0.25,
            "adversarial_depth": 0.15,
            "meadows_alignment": 0.10,
            "token_efficiency": 0.10,
            "latency_score": 0.10,
        }
        vals = [getattr(self, k) * v for k, v in w.items()]

        if method == "geometric_mean":
            # Geometric mean of weighted values (avoid zero)
            product = 1.0
            for v in vals:
                product *= max(v, 1e-6)
            return product ** (1.0 / len(vals))
        elif method == "harmonic_mean":
            # Harmonic mean (penalizes near-zero dimensions)
            denom = sum(1.0 / max(v, 1e-6) for v in vals)
            return len(vals) / denom if denom > 0 else 0.0
        elif method == "min_of_all":
            # Bottleneck: weakest weighted dimension
            return min(vals) if vals else 0.0
        else:  # weighted_sum (default)
            return sum(vals)


@dataclass
class EvalResult:
    """Full evaluation result for one genome on one model."""
    genome_id: str
    model: str
    grid_cell: str  # e.g. "small_low"
    fitness: FitnessVector
    raw_scores: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Eval Problems (imported from prey8_eval_harness)
# ---------------------------------------------------------------------------

# Import eval problems from existing harness
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from prey8_eval_harness import EVAL_PROBLEMS, extract_code, run_tests
except ImportError:
    print("WARNING: Could not import from prey8_eval_harness.py, using inline fallback")
    EVAL_PROBLEMS = []

    def extract_code(response, func_name):
        code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
        for block in code_blocks:
            if func_name in block:
                return block.strip()
        return response.strip()

    def run_tests(code, tests, func_name):
        test_code = code + "\n\n" + "\n".join(tests)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(test_code)
            tmp_path = f.name
        try:
            result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=10)
            return {"passed": result.returncode == 0, "tests_count": len(tests), "stderr": result.stderr[:500]}
        except Exception as e:
            return {"passed": False, "tests_count": len(tests), "stderr": str(e)[:500]}
        finally:
            try: os.unlink(tmp_path)
            except: pass


# ---------------------------------------------------------------------------
# PREY8 Gate Evaluation Prompt
# ---------------------------------------------------------------------------

CHIMERA_EVAL_PROMPT = PROMPT_TEMPLATES["json_structured"]


# ---------------------------------------------------------------------------
# Ollama API
# ---------------------------------------------------------------------------

def ollama_generate(model: str, prompt: str, system: str = "",
                    base_url: str = None) -> dict:
    """Call Ollama generate API."""
    url = f"{base_url or OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": MAX_TOKENS, "temperature": 0.0},
    }
    if system:
        payload["system"] = system

    try:
        with httpx.Client(timeout=TIMEOUT_GENERATE) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return {
                "response": data.get("response", ""),
                "total_duration_ms": data.get("total_duration", 0) / 1e6,
                "eval_count": data.get("eval_count", 0),
                "eval_duration_ms": data.get("eval_duration", 0) / 1e6,
                "model": data.get("model", model),
                "done": data.get("done", False),
            }
    except Exception as e:
        return {"response": "", "error": str(e), "model": model, "done": False}


def list_models(base_url: str = None) -> list[str]:
    """Get available Ollama models."""
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{base_url or OLLAMA_BASE}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# PREY8 Field Extraction & Scoring
# ---------------------------------------------------------------------------

def extract_prey8_fields(response: str) -> dict:
    """Parse PREY8 structured fields from model response."""
    try:
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass

    # Manual extraction fallback
    fields = {}
    for key in ["observations", "memory_refs", "stigmergy_digest",
                "shared_data_refs", "navigation_intent", "meadows_level",
                "meadows_justification", "sequential_plan",
                "sbe_given", "sbe_when", "sbe_then",
                "artifacts", "p4_adversarial_check", "code"]:
        match = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', response)
        if match:
            fields[key] = match.group(1)
        elif key == "meadows_level":
            match = re.search(rf'"{key}"\s*:\s*(\d+)', response)
            if match:
                fields[key] = int(match.group(1))
    return fields


def score_gate_compliance(fields: dict) -> float:
    """Score how well gate fields were filled (0-1)."""
    required = [
        "observations", "memory_refs", "stigmergy_digest",
        "shared_data_refs", "navigation_intent", "meadows_level",
        "meadows_justification", "sequential_plan",
        "sbe_given", "sbe_when", "sbe_then",
        "artifacts", "p4_adversarial_check",
    ]
    present = 0
    for f in required:
        val = fields.get(f)
        if val and str(val).strip() and str(val).strip() not in ("", "N/A", "none", "null"):
            present += 1
    return present / len(required)


def score_adversarial_depth(text: str) -> float:
    """Score the quality of p4_adversarial_check text (0-1)."""
    if not text or len(text.strip()) < 10:
        return 0.0
    score = 0.0
    indicators = [
        (r"edge\s*case", 0.15),
        (r"fail|failure|error|exception", 0.15),
        (r"empty|null|none|zero|negative", 0.15),
        (r"overflow|underflow|bound", 0.10),
        (r"mutant|mutation|stryker", 0.15),
        (r"invariant|property|assert", 0.10),
        (r"what if|assume|suppose", 0.10),
        (r"attack|adversar|hostile", 0.10),
    ]
    for pattern, weight in indicators:
        if re.search(pattern, text, re.IGNORECASE):
            score += weight
    # Length bonus (longer = more thorough, up to a point)
    length_bonus = min(len(text) / 500, 0.2)
    return min(score + length_bonus, 1.0)


def score_meadows_alignment(level: int, problem_difficulty: str) -> float:
    """Score Meadows level appropriateness for the problem (0-1)."""
    if not isinstance(level, int) or level < 1 or level > 12:
        return 0.0
    # Coding problems are typically L1-L5 (parameters/buffers/structure)
    # Easy problems: L1-L3 is ideal
    # Medium problems: L2-L5 is ideal
    # Hard problems: L4-L7 is ideal
    ideal_ranges = {
        "easy": (1, 4),
        "medium": (2, 6),
        "hard": (4, 8),
    }
    lo, hi = ideal_ranges.get(problem_difficulty, (1, 6))
    if lo <= level <= hi:
        return 1.0
    distance = min(abs(level - lo), abs(level - hi))
    return max(0.0, 1.0 - distance * 0.2)


# ---------------------------------------------------------------------------
# SSOT Logging
# ---------------------------------------------------------------------------

def _write_stigmergy(event_type: str, data: dict) -> int:
    """Write a chimera loop event to SSOT stigmergy_events."""
    if not DB_PATH.exists():
        return -1
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": f"hfo_p2_chimera_gen{GEN}",
        "subject": "chimera-loop",
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event["type"], ts, "chimera-loop", event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Persistent MAP-ELITES Archive + Lineage Tables
# ---------------------------------------------------------------------------

def _ensure_archive_tables() -> None:
    """Create chimera_archive and chimera_lineage tables if they don't exist.

    Schema from gold diataxis: EXPLANATION_UNIVERSAL_DARWINISM §6.
    These tables provide persistent MAP-ELITES archive for cross-session
    evolutionary continuity and parent→child lineage tracking.
    """
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chimera_archive (
                genome_id       TEXT PRIMARY KEY,
                generation      INTEGER NOT NULL,
                traits_json     TEXT NOT NULL,
                meta_traits_json TEXT,
                aggregate_score REAL NOT NULL,
                fitness_json    TEXT NOT NULL,
                grid_scores_json TEXT,
                system_prompt   TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                parent_ids      TEXT,
                is_pareto_front INTEGER DEFAULT 0,
                notes           TEXT
            );

            CREATE TABLE IF NOT EXISTS chimera_lineage (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                child_id        TEXT NOT NULL,
                parent1_id      TEXT NOT NULL,
                parent2_id      TEXT,
                operator        TEXT NOT NULL CHECK(operator IN ('crossover','mutation','elite','seed','random')),
                generation      INTEGER NOT NULL,
                mutation_rate   REAL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (child_id) REFERENCES chimera_archive(genome_id)
            );

            CREATE INDEX IF NOT EXISTS idx_chimera_archive_score
                ON chimera_archive(aggregate_score DESC);

            CREATE INDEX IF NOT EXISTS idx_chimera_archive_generation
                ON chimera_archive(generation);

            CREATE INDEX IF NOT EXISTS idx_chimera_lineage_child
                ON chimera_lineage(child_id);

            CREATE INDEX IF NOT EXISTS idx_chimera_lineage_parent
                ON chimera_lineage(parent1_id);
        """)
        conn.commit()
    finally:
        conn.close()


def _archive_elite(genome: Genome, eval_result: dict,
                   parent_ids: list[str] = None,
                   is_pareto: bool = False) -> None:
    """Write a genome + its fitness to the persistent archive.

    Upserts: if the genome_id already exists, update score if higher.
    """
    if not DB_PATH.exists():
        return
    agg = eval_result.get("aggregate_fitness", FitnessVector())
    score = eval_result.get("aggregate_score", 0.0)
    grid_scores = {}
    for cell, res in eval_result.get("grid_results", {}).items():
        grid_scores[cell] = {
            "model": res.model,
            "coding": round(res.fitness.coding_accuracy, 4),
            "gates": round(res.fitness.gate_compliance, 4),
            "aggregate": round(res.fitness.aggregate(), 4),
        }

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute(
            """INSERT INTO chimera_archive
               (genome_id, generation, traits_json, meta_traits_json,
                aggregate_score, fitness_json, grid_scores_json,
                system_prompt, parent_ids, is_pareto_front)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(genome_id) DO UPDATE SET
                 aggregate_score = MAX(excluded.aggregate_score, chimera_archive.aggregate_score),
                 fitness_json = CASE
                   WHEN excluded.aggregate_score > chimera_archive.aggregate_score
                   THEN excluded.fitness_json
                   ELSE chimera_archive.fitness_json
                 END,
                 grid_scores_json = CASE
                   WHEN excluded.aggregate_score > chimera_archive.aggregate_score
                   THEN excluded.grid_scores_json
                   ELSE chimera_archive.grid_scores_json
                 END,
                 is_pareto_front = excluded.is_pareto_front
            """,
            (
                genome.genome_id,
                genome.generation,
                json.dumps(genome.traits, sort_keys=True),
                json.dumps(getattr(genome, 'meta_traits', None), sort_keys=True),
                round(score, 6),
                json.dumps(asdict(agg), sort_keys=True) if hasattr(agg, '__dataclass_fields__') else json.dumps({}),
                json.dumps(grid_scores, sort_keys=True),
                genome.to_system_prompt()[:2000],
                json.dumps(parent_ids) if parent_ids else None,
                1 if is_pareto else 0,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _record_lineage(child_id: str, parent1_id: str, parent2_id: str = None,
                    operator: str = "mutation", generation: int = 0,
                    mutation_rate: float = None) -> None:
    """Record parent→child lineage relationship."""
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute(
            """INSERT INTO chimera_lineage
               (child_id, parent1_id, parent2_id, operator, generation, mutation_rate)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (child_id, parent1_id, parent2_id, operator, generation, mutation_rate),
        )
        conn.commit()
    finally:
        conn.close()


# Ensure tables exist on module import
_ensure_archive_tables()


# ---------------------------------------------------------------------------
# Core Evaluation Engine
# ---------------------------------------------------------------------------

def evaluate_genome(genome: Genome, model: str, grid_cell: str,
                    problems: list[dict], verbose: bool = True) -> EvalResult:
    """Evaluate a single genome on a single model across given problems.

    This is one cell in the SBE/ATDD loop:
      Given: genome G with traits T, model M, problems P
      When:  each problem is solved with G's persona as system prompt
      Then:  multi-dimensional fitness vector is computed
    """
    system_prompt = genome.to_system_prompt()

    passed_count = 0
    gate_scores = []
    adversarial_scores = []
    meadows_scores = []
    total_tokens = 0
    total_time = 0.0
    problem_results = []

    # Use meta-genome prompt template if available, else default
    prompt_template = genome.get_prompt_template() if hasattr(genome, 'get_prompt_template') else CHIMERA_EVAL_PROMPT

    for i, problem in enumerate(problems):
        prompt = prompt_template.format(problem_prompt=problem["prompt"])

        t0 = time.time()
        gen = ollama_generate(model, prompt, system=system_prompt)
        elapsed = time.time() - t0
        total_time += elapsed

        if gen.get("error"):
            if verbose:
                print(f"    [{i+1}] {problem['id']} ERROR: {gen['error'][:60]}")
            problem_results.append({"id": problem["id"], "error": gen["error"][:200]})
            gate_scores.append(0.0)
            adversarial_scores.append(0.0)
            meadows_scores.append(0.0)
            continue

        tokens = gen.get("eval_count", 0)
        total_tokens += tokens

        # Extract PREY8 fields
        fields = extract_prey8_fields(gen["response"])

        # Score gate compliance
        g_score = score_gate_compliance(fields)
        gate_scores.append(g_score)

        # Score adversarial depth
        a_text = fields.get("p4_adversarial_check", "")
        a_score = score_adversarial_depth(a_text)
        adversarial_scores.append(a_score)

        # Score Meadows alignment
        m_level = fields.get("meadows_level", 0)
        if isinstance(m_level, str):
            try: m_level = int(m_level)
            except: m_level = 0
        m_score = score_meadows_alignment(m_level, problem.get("difficulty", "easy"))
        meadows_scores.append(m_score)

        # Test code
        code = fields.get("code", "")
        if not code:
            code = extract_code(gen["response"], problem["name"])

        test_result = run_tests(code, problem["tests"], problem["name"])
        if test_result["passed"]:
            passed_count += 1

        if verbose:
            status = "PASS" if test_result["passed"] else "FAIL"
            print(f"    [{i+1}] {problem['id']} {status} | "
                  f"gate:{g_score:.0%} adv:{a_score:.0%} "
                  f"meadows:L{m_level}({m_score:.0%}) | "
                  f"{tokens}tok {elapsed:.1f}s")

        problem_results.append({
            "id": problem["id"],
            "code_passed": test_result["passed"],
            "gate_score": round(g_score, 3),
            "adversarial_score": round(a_score, 3),
            "meadows_level": m_level,
            "meadows_score": round(m_score, 3),
            "tokens": tokens,
            "time_s": round(elapsed, 2),
        })

    n = len(problems)
    avg_tokens = total_tokens / max(n, 1)
    avg_time = total_time / max(n, 1)

    # Compute fitness vector
    fitness = FitnessVector(
        coding_accuracy=passed_count / max(n, 1),
        gate_compliance=sum(gate_scores) / max(len(gate_scores), 1),
        adversarial_depth=sum(adversarial_scores) / max(len(adversarial_scores), 1),
        meadows_alignment=sum(meadows_scores) / max(len(meadows_scores), 1),
        # Token efficiency: lower is better, normalize to 0-1
        # Assume 2000 tokens is worst case, <200 is ideal
        token_efficiency=max(0.0, 1.0 - (avg_tokens / 2000)),
        # Latency: lower is better, normalize
        # Assume 120s is worst case, <5s is ideal
        latency_score=max(0.0, 1.0 - (avg_time / 120)),
    )

    result = EvalResult(
        genome_id=genome.genome_id,
        model=model,
        grid_cell=grid_cell,
        fitness=fitness,
        raw_scores={
            "problems_total": n,
            "problems_passed": passed_count,
            "avg_tokens": round(avg_tokens, 1),
            "avg_time_s": round(avg_time, 2),
            "total_time_s": round(total_time, 2),
            "problem_results": problem_results,
        },
    )

    return result


def evaluate_genome_across_grid(genome: Genome, problems: list[dict],
                                 grid: dict = None, verbose: bool = True) -> dict:
    """Evaluate one genome across all models in the 2x2 grid.

    SBE Scenario:
      Given: genome G, 2x2 model grid
      When:  G is evaluated on each grid cell
      Then:  aggregated fitness across all cells returned
    """
    grid = grid or MODEL_GRID
    results = {}
    aggregate_fitness = []

    for cell_name, model_name in grid.items():
        if verbose:
            print(f"\n  --- Grid Cell: {cell_name} → {model_name} ---")

        result = evaluate_genome(genome, model_name, cell_name, problems, verbose)
        results[cell_name] = result
        aggregate_fitness.append(result.fitness)

    # Compute aggregate fitness (average across grid)
    if aggregate_fitness:
        agg = FitnessVector(
            coding_accuracy=sum(f.coding_accuracy for f in aggregate_fitness) / len(aggregate_fitness),
            gate_compliance=sum(f.gate_compliance for f in aggregate_fitness) / len(aggregate_fitness),
            adversarial_depth=sum(f.adversarial_depth for f in aggregate_fitness) / len(aggregate_fitness),
            meadows_alignment=sum(f.meadows_alignment for f in aggregate_fitness) / len(aggregate_fitness),
            token_efficiency=sum(f.token_efficiency for f in aggregate_fitness) / len(aggregate_fitness),
            latency_score=sum(f.latency_score for f in aggregate_fitness) / len(aggregate_fitness),
        )
    else:
        agg = FitnessVector()

    # Use meta-genome fitness weights and aggregation method if available
    meta = getattr(genome, 'meta_traits', {}) or {}
    weights = genome.get_fitness_weights() if hasattr(genome, 'get_fitness_weights') else None
    agg_method = meta.get('aggregation_method', 'weighted_sum')

    return {
        "genome_id": genome.genome_id,
        "grid_results": results,
        "aggregate_fitness": agg,
        "aggregate_score": agg.aggregate(weights=weights, method=agg_method),
    }


# ---------------------------------------------------------------------------
# Evolutionary Operators
# ---------------------------------------------------------------------------

def tournament_select(population: list, fitnesses: list[float],
                      tournament_size: int = 3) -> int:
    """Tournament selection — return index of winner."""
    candidates = random.sample(range(len(population)), min(tournament_size, len(population)))
    best = max(candidates, key=lambda i: fitnesses[i])
    return best


def pareto_nondominated_sort(fitness_vectors: list[FitnessVector]) -> list[list[int]]:
    """NSGA-II style non-dominated sorting. Returns fronts (lists of indices)."""
    n = len(fitness_vectors)
    domination_count = [0] * n
    dominated_by = [[] for _ in range(n)]
    fronts = [[]]

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if fitness_vectors[i].dominates(fitness_vectors[j]):
                dominated_by[i].append(j)
            elif fitness_vectors[j].dominates(fitness_vectors[i]):
                domination_count[i] += 1
        if domination_count[i] == 0:
            fronts[0].append(i)

    current_front = 0
    while fronts[current_front]:
        next_front = []
        for i in fronts[current_front]:
            for j in dominated_by[i]:
                domination_count[j] -= 1
                if domination_count[j] == 0:
                    next_front.append(j)
        current_front += 1
        if next_front:
            fronts.append(next_front)
        else:
            break

    return fronts


# ---------------------------------------------------------------------------
# Chimera Loop Main Engine
# ---------------------------------------------------------------------------

def run_chimera_loop(
    generations: int = 3,
    pop_size: int = 6,
    num_problems: int = 5,
    mutation_rate: float = 0.3,
    crossover_rate: float = 0.5,
    elitism: int = 2,
    grid: dict = None,
    verbose: bool = True,
    resume_from_ssot: bool = False,
) -> dict:
    """
    Run the P2 Empowered Cursed Chimera Loop.

    SBE/ATDD Loop:
      Given: initial population of persona genomes
      When:  evolutionary pressure is applied via 2x2 model grid evaluation
      Then:  Pareto-optimal persona configurations emerge

    Args:
        generations: Number of evolutionary generations
        pop_size: Population size per generation
        num_problems: Number of eval problems per evaluation
        mutation_rate: Probability of mutating each trait
        crossover_rate: Probability of crossover vs mutation
        elitism: Number of top individuals that survive unchanged
        grid: Model grid override (default: MODEL_GRID)
        verbose: Print progress
        resume_from_ssot: Try to resume from last generation in SSOT

    Returns:
        dict with best genome, Pareto front, and full history
    """
    grid = grid or MODEL_GRID
    problems = EVAL_PROBLEMS[:num_problems] if num_problems > 0 else EVAL_PROBLEMS

    print(f"\n{'█'*70}")
    print(f"  HFO P2 EMPOWERED CURSED CHIMERA LOOP")
    print(f"  Evolutionary DSE for Red Regnant Persona")
    print(f"{'█'*70}")
    print(f"  Generations:    {generations}")
    print(f"  Population:     {pop_size}")
    print(f"  Problems:       {len(problems)}")
    print(f"  Mutation rate:  {mutation_rate}")
    print(f"  Crossover rate: {crossover_rate}")
    print(f"  Elitism:        {elitism}")
    print(f"  Model grid:")
    for cell, model in grid.items():
        print(f"    {cell:>12}: {model}")
    print(f"{'█'*70}\n")

    # Initialize population
    population = [Genome.random_genome(generation=0) for _ in range(pop_size)]

    # Seed with some known-good baselines
    if pop_size >= 4:
        # The "default" Red Regnant configuration
        population[0] = Genome(
            traits={
                "tone": "adversarial_coach",
                "adversarial_depth": "structured_challenge",
                "reasoning_style": "chain_of_thought",
                "gate_philosophy": "rich_documentation",
                "meadows_strategy": "adaptive",
                "sbe_style": "comprehensive",
                "trust_posture": "zero_trust",
                "artifact_discipline": "test_first",
            },
            generation=0,
        )
        # The "chaos chimera" — all cursed alleles
        population[1] = Genome(
            traits={
                "tone": "chaos_gremlin",
                "adversarial_depth": "chaos_monkey",
                "reasoning_style": "ralph_wiggums",
                "gate_philosophy": "ceremonial",
                "meadows_strategy": "contrarian",
                "sbe_style": "narrative",
                "trust_posture": "dgaf_chaos",
                "artifact_discipline": "spike_and_refine",
            },
            generation=0,
        )
        # The "formal fortress" — maximum rigor
        population[2] = Genome(
            traits={
                "tone": "cold_analytical",
                "adversarial_depth": "formal_verification",
                "reasoning_style": "first_principles",
                "gate_philosophy": "adversarial_gates",
                "meadows_strategy": "meta_systemic",
                "sbe_style": "invariant_first",
                "trust_posture": "paranoid",
                "artifact_discipline": "test_first",
            },
            generation=0,
        )
        # The "zen minimalist"
        if pop_size >= 4:
            population[3] = Genome(
                traits={
                    "tone": "zen_master",
                    "adversarial_depth": "surface_scan",
                    "reasoning_style": "analogical",
                    "gate_philosophy": "minimal_compliance",
                    "meadows_strategy": "escalating",
                    "sbe_style": "terse",
                    "trust_posture": "bayesian",
                    "artifact_discipline": "minimal_diff",
                },
                generation=0,
            )

    # Log initialization
    _write_stigmergy("hfo.gen89.chimera.init", {
        "population_size": pop_size,
        "generations_planned": generations,
        "num_problems": len(problems),
        "model_grid": grid,
        "initial_genomes": [
            {"id": g.genome_id, "traits": g.traits}
            for g in population
        ],
    })

    # Record seed lineage for initial population
    for g in population:
        op = "seed" if g.generation == 0 and any(
            g.traits.get("tone") == t for t in
            ["adversarial_coach", "chaos_gremlin", "cold_analytical", "zen_master"]
        ) else "random"
        _record_lineage(
            child_id=g.genome_id,
            parent1_id="GENESIS",
            operator=op,
            generation=0,
        )

    history = []
    best_ever = None
    best_ever_score = -1

    for gen_num in range(generations):
        print(f"\n{'='*70}")
        print(f"  GENERATION {gen_num + 1}/{generations}")
        print(f"{'='*70}")

        gen_results = []

        for idx, genome in enumerate(population):
            print(f"\n  ╔══ Genome {idx+1}/{pop_size}: [{genome.genome_id}] ══╗")
            traits_str = ", ".join(f"{k}={v}" for k, v in genome.traits.items())
            print(f"  ║ Traits: {traits_str[:100]}...")
            print(f"  ╚{'═'*50}╝")

            eval_result = evaluate_genome_across_grid(
                genome, problems, grid, verbose=verbose
            )
            gen_results.append(eval_result)

            agg = eval_result["aggregate_fitness"]
            score = eval_result["aggregate_score"]
            print(f"\n  → Aggregate: code={agg.coding_accuracy:.0%} "
                  f"gate={agg.gate_compliance:.0%} "
                  f"adv={agg.adversarial_depth:.0%} "
                  f"meadows={agg.meadows_alignment:.0%} "
                  f"score={score:.3f}")

            if score > best_ever_score:
                best_ever_score = score
                best_ever = (genome, agg, eval_result)

            # Log each genome evaluation to SSOT
            _write_stigmergy("hfo.gen89.chimera.eval", {
                "generation": gen_num,
                "genome_id": genome.genome_id,
                "traits": genome.traits,
                "aggregate_score": round(score, 4),
                "fitness": {
                    "coding_accuracy": round(agg.coding_accuracy, 4),
                    "gate_compliance": round(agg.gate_compliance, 4),
                    "adversarial_depth": round(agg.adversarial_depth, 4),
                    "meadows_alignment": round(agg.meadows_alignment, 4),
                    "token_efficiency": round(agg.token_efficiency, 4),
                    "latency_score": round(agg.latency_score, 4),
                },
                "grid_scores": {
                    cell: {
                        "model": res.model,
                        "coding": round(res.fitness.coding_accuracy, 4),
                        "gates": round(res.fitness.gate_compliance, 4),
                        "aggregate": round(res.fitness.aggregate(), 4),
                    }
                    for cell, res in eval_result["grid_results"].items()
                },
            })

            # Archive genome to persistent MAP-ELITES table
            _archive_elite(genome, eval_result)

        # --- Selection & Evolution ---
        fitness_vectors = [r["aggregate_fitness"] for r in gen_results]
        scores = [r["aggregate_score"] for r in gen_results]

        # Pareto non-dominated sorting
        fronts = pareto_nondominated_sort(fitness_vectors)

        print(f"\n  {'─'*60}")
        print(f"  GENERATION {gen_num + 1} SUMMARY")
        print(f"  {'─'*60}")
        print(f"  Pareto front sizes: {[len(f) for f in fronts]}")
        print(f"  Best score: {max(scores):.4f}")
        print(f"  Avg score:  {sum(scores)/len(scores):.4f}")
        print(f"  Worst score: {min(scores):.4f}")

        # Print leaderboard
        ranked = sorted(range(len(population)), key=lambda i: scores[i], reverse=True)
        print(f"\n  {'Rank':<5} {'ID':<10} {'Score':<8} {'Code':<8} {'Gate':<8} {'Adv':<8}")
        for rank, idx in enumerate(ranked):
            g = population[idx]
            f = fitness_vectors[idx]
            front_idx = next(fi for fi, front in enumerate(fronts) if idx in front)
            print(f"  {rank+1:<5} {g.genome_id:<10} {scores[idx]:<8.4f} "
                  f"{f.coding_accuracy:<8.1%} {f.gate_compliance:<8.1%} "
                  f"{f.adversarial_depth:<8.1%} [F{front_idx}]")

        # Log generation summary
        _write_stigmergy("hfo.gen89.chimera.generation", {
            "generation": gen_num,
            "best_score": round(max(scores), 4),
            "avg_score": round(sum(scores) / len(scores), 4),
            "pareto_front_size": len(fronts[0]),
            "leaderboard": [
                {
                    "rank": rank + 1,
                    "genome_id": population[idx].genome_id,
                    "score": round(scores[idx], 4),
                    "traits": population[idx].traits,
                }
                for rank, idx in enumerate(ranked[:5])
            ],
        })

        # Mark Pareto front members in archive
        if fronts and fronts[0]:
            for idx in fronts[0]:
                _archive_elite(population[idx], gen_results[idx], is_pareto=True)

        history.append({
            "generation": gen_num,
            "scores": scores,
            "best_score": max(scores),
            "avg_score": sum(scores) / len(scores),
            "best_genome_id": population[ranked[0]].genome_id,
            "best_traits": population[ranked[0]].traits,
        })

        # Create next generation (unless final generation)
        if gen_num < generations - 1:
            next_population = []

            # Elitism: keep top genomes unchanged
            for i in range(min(elitism, len(ranked))):
                elite = copy.deepcopy(population[ranked[i]])
                elite.generation = gen_num + 1
                _record_lineage(
                    child_id=elite.genome_id,
                    parent1_id=population[ranked[i]].genome_id,
                    operator="elite",
                    generation=gen_num + 1,
                )
                next_population.append(elite)

            # Fill rest via tournament selection + operators
            # Use best genome's tournament size from meta-genome (or default 3)
            best_genome = population[ranked[0]]
            t_size = best_genome.get_tournament_size() if hasattr(best_genome, 'get_tournament_size') else 3

            while len(next_population) < pop_size:
                if random.random() < crossover_rate and len(population) >= 2:
                    # Crossover
                    p1_idx = tournament_select(population, scores, tournament_size=t_size)
                    p2_idx = tournament_select(population, scores, tournament_size=t_size)
                    while p2_idx == p1_idx:
                        p2_idx = tournament_select(population, scores, tournament_size=t_size)
                    child = Genome.crossover(population[p1_idx], population[p2_idx])
                    # Also mutate the crossover child slightly
                    if random.random() < 0.5:
                        child = child.mutate(mutation_rate * 0.5)
                    _record_lineage(
                        child_id=child.genome_id,
                        parent1_id=population[p1_idx].genome_id,
                        parent2_id=population[p2_idx].genome_id,
                        operator="crossover",
                        generation=gen_num + 1,
                        mutation_rate=mutation_rate * 0.5 if random.random() < 0.5 else None,
                    )
                    next_population.append(child)
                else:
                    # Mutation
                    parent_idx = tournament_select(population, scores, tournament_size=t_size)
                    child = population[parent_idx].mutate(mutation_rate)
                    _record_lineage(
                        child_id=child.genome_id,
                        parent1_id=population[parent_idx].genome_id,
                        operator="mutation",
                        generation=gen_num + 1,
                        mutation_rate=mutation_rate,
                    )
                    next_population.append(child)

            population = next_population

    # --- Final Report ---
    print(f"\n{'█'*70}")
    print(f"  CHIMERA LOOP COMPLETE")
    print(f"{'█'*70}")
    if best_ever:
        bg, bf, br = best_ever
        print(f"  Best genome: [{bg.genome_id}] (score: {best_ever_score:.4f})")
        print(f"  Traits:")
        for k, v in bg.traits.items():
            print(f"    {k:<25} = {v}")
        print(f"  Fitness:")
        print(f"    coding_accuracy:    {bf.coding_accuracy:.1%}")
        print(f"    gate_compliance:    {bf.gate_compliance:.1%}")
        print(f"    adversarial_depth:  {bf.adversarial_depth:.1%}")
        print(f"    meadows_alignment:  {bf.meadows_alignment:.1%}")
        print(f"    token_efficiency:   {bf.token_efficiency:.1%}")
        print(f"    latency_score:      {bf.latency_score:.1%}")
        print(f"\n  System Prompt Preview (first 500 chars):")
        print(f"  {bg.to_system_prompt()[:500]}...")

    # Log final results
    _write_stigmergy("hfo.gen89.chimera.complete", {
        "total_generations": generations,
        "best_score": round(best_ever_score, 4),
        "best_genome": {
            "id": best_ever[0].genome_id if best_ever else None,
            "traits": best_ever[0].traits if best_ever else {},
            "fitness": asdict(best_ever[1]) if best_ever else {},
        },
        "history": history,
    })

    return {
        "best_genome": best_ever[0] if best_ever else None,
        "best_fitness": best_ever[1] if best_ever else None,
        "best_score": best_ever_score,
        "history": history,
        "population": population,
    }


# ---------------------------------------------------------------------------
# Quick Single-Model Test
# ---------------------------------------------------------------------------

def quick_test(model: str, num_problems: int = 3, verbose: bool = True):
    """Quick test: evaluate the default Red Regnant genome on one model."""
    problems = EVAL_PROBLEMS[:num_problems] if num_problems > 0 else EVAL_PROBLEMS

    genome = Genome(
        traits={
            "tone": "adversarial_coach",
            "adversarial_depth": "structured_challenge",
            "reasoning_style": "chain_of_thought",
            "gate_philosophy": "rich_documentation",
            "meadows_strategy": "adaptive",
            "sbe_style": "comprehensive",
            "trust_posture": "zero_trust",
            "artifact_discipline": "test_first",
        },
        generation=0,
    )

    print(f"\n{'='*60}")
    print(f"  CHIMERA QUICK TEST: {model}")
    print(f"  Genome: [{genome.genome_id}] (default Red Regnant)")
    print(f"  Problems: {len(problems)}")
    print(f"{'='*60}")

    result = evaluate_genome(genome, model, "quick_test", problems, verbose)

    f = result.fitness
    print(f"\n  Fitness Vector:")
    print(f"    coding_accuracy:    {f.coding_accuracy:.1%}")
    print(f"    gate_compliance:    {f.gate_compliance:.1%}")
    print(f"    adversarial_depth:  {f.adversarial_depth:.1%}")
    print(f"    meadows_alignment:  {f.meadows_alignment:.1%}")
    print(f"    token_efficiency:   {f.token_efficiency:.1%}")
    print(f"    latency_score:      {f.latency_score:.1%}")
    print(f"    AGGREGATE:          {f.aggregate():.4f}")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="HFO P2 Empowered Cursed Chimera Loop — Evolutionary Persona DSE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              # Quick test with one model
              python hfo_p2_chimera_loop.py --test-model gemma3:4b --problems 3

              # Run 1 generation with small population
              python hfo_p2_chimera_loop.py --generations 1 --pop-size 4 --problems 5

              # Full evolutionary run
              python hfo_p2_chimera_loop.py --generations 5 --pop-size 8 --problems 10

              # Use subset of grid
              python hfo_p2_chimera_loop.py --grid small_low,small_high --generations 2

            Model Grid (2x2):
              small_low  = gemma3:4b       (3.3GB, lightweight general)
              small_high = deepseek-r1:8b  (5.2GB, reasoning distill)
              large_low  = phi4:14b        (9.1GB, general purpose)
              large_high = qwen3:30b-a3b   (18GB,  MoE reasoning)

            Fitness Dimensions:
              coding_accuracy   — pass@1 on HumanEval-style problems
              gate_compliance   — PREY8 structured field completeness
              adversarial_depth — quality of p4_adversarial_check
              meadows_alignment — appropriateness of leverage level
              token_efficiency  — tokens per solution (inverted)
              latency_score     — response time (inverted)
        """),
    )
    parser.add_argument("--test-model", type=str, default=None,
                        help="Quick test: evaluate default genome on one model")
    parser.add_argument("--generations", type=int, default=3,
                        help="Number of evolutionary generations (default: 3)")
    parser.add_argument("--pop-size", type=int, default=6,
                        help="Population size per generation (default: 6)")
    parser.add_argument("--problems", type=int, default=5,
                        help="Number of eval problems (default: 5, max: 20)")
    parser.add_argument("--mutation-rate", type=float, default=0.3,
                        help="Per-trait mutation probability (default: 0.3)")
    parser.add_argument("--crossover-rate", type=float, default=0.5,
                        help="Crossover vs mutation probability (default: 0.5)")
    parser.add_argument("--elitism", type=int, default=2,
                        help="Top N genomes preserved unchanged (default: 2)")
    parser.add_argument("--grid", type=str, default=None,
                        help="Comma-separated grid cells to use (default: all 4)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last generation in SSOT")
    parser.add_argument("--verbose", action="store_true", default=True)
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()
    if args.quiet:
        args.verbose = False

    # Quick test mode
    if args.test_model:
        quick_test(args.test_model, args.problems, args.verbose)
        return

    # Parse grid override
    grid = MODEL_GRID
    if args.grid:
        cells = [c.strip() for c in args.grid.split(",")]
        grid = {c: MODEL_GRID[c] for c in cells if c in MODEL_GRID}
        if not grid:
            print(f"ERROR: No valid grid cells in '{args.grid}'")
            print(f"Valid cells: {', '.join(MODEL_GRID.keys())}")
            sys.exit(1)

    # Run chimera loop
    result = run_chimera_loop(
        generations=args.generations,
        pop_size=args.pop_size,
        num_problems=args.problems,
        mutation_rate=args.mutation_rate,
        crossover_rate=args.crossover_rate,
        elitism=args.elitism,
        grid=grid,
        verbose=args.verbose,
        resume_from_ssot=args.resume,
    )

    # Output best genome's system prompt for export
    if result["best_genome"]:
        best = result["best_genome"]
        prompt_path = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources" / f"chimera_best_{best.genome_id}.txt"
        prompt_path.write_text(best.to_system_prompt(), encoding="utf-8")
        print(f"\n  Best persona saved to: {prompt_path}")


if __name__ == "__main__":
    main()
