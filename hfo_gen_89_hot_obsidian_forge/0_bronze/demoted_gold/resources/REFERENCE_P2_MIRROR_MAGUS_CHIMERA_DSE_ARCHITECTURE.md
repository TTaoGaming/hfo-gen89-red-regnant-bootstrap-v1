---
schema_id: hfo.gen89.diataxis.reference.v1
medallion_layer: gold
doc_type: reference
port: P2
title: "REFERENCE: P2 Mirror Magus — Chimera Evolutionary DSE Architecture"
bluf: "Complete technical reference for the HFO P2 Empowered Cursed Chimera Variant Ralph Wiggums Loop. 8-trait genome × 6-dim fitness × 2×2 model grid. MAP-ELITES + NSGA-II over stigmergy blood trails."
hive: V
operator: TTAO
created: 2026-02-19
---

# REFERENCE: P2 Mirror Magus — Chimera Evolutionary DSE Architecture

## Purpose

This document provides the definitive technical reference for the P2 SHAPE (Mirror Magus) evolutionary Design Space Exploration engine. It covers the genome structure, fitness vector, evaluation grid, selection algorithms, and SSOT integration.

---

## 1. System Overview

The Chimera Loop is an evolutionary optimization engine that discovers optimal agent persona configurations through structured trait genomes evaluated across heterogeneous model grids.

**Architecture:** Population-based multi-objective optimization
**Port:** P2 SHAPE (Mirror Magus) — PREY8 Execute gate (paired with P4 DISRUPT)
**Implementation:** `hfo_p2_chimera_loop.py` (1,371 lines, bronze)
**Agent Mode:** `.github/agents/hfo_gen_89_p2_mirror_magus_chimera_v1.agent.md`

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Genome encoding | 8 discrete traits × 5-7 alleles | Matches P4 Red Regnant system prompt sections |
| Fitness | 6 weighted dimensions | Covers accuracy, compliance, adversarial, strategy, efficiency, latency |
| Selection | Tournament (k=3) + NSGA-II | Maintains diversity while optimizing Pareto front |
| Model grid | 2×2 (size × intelligence) | Tests persona robustness across model heterogeneity |
| CURSED alleles | 1+ per trait | Ralph Wiggums insight — naive approaches sometimes find what sophisticated ones miss |
| Persistence | SSOT stigmergy_events | CloudEvent blood trails survive agent session mortality |

---

## 2. Genome Structure

### 2.1 Trait Allele Table

Each genome encodes exactly **8 traits**. Each trait has a description and a list of alleles.

#### `tone` — Voice and communication style (7 alleles)
- `cold_analytical` — Precise, clinical, no emotion
- `adversarial_coach` — Tough love, challenges everything
- `socratic_inquisitor` — Questions back, forces reasoning
- `war_room_commander` — Military precision, SITREP style
- `chaos_gremlin` — **CURSED**: chaotic but insightful
- `zen_master` — Calm, koan-like observations
- `pair_programmer` — Collaborative, thinking aloud

#### `adversarial_depth` — How deeply to probe for weaknesses (6 alleles)
- `surface_scan` — Quick checks, obvious issues only
- `structured_challenge` — Systematic threat enumeration
- `red_team_full` — Full adversarial analysis per step
- `chaos_monkey` — **CURSED**: random deep probes
- `stryker_mutation` — Mutation testing mindset
- `formal_verification` — Mathematical proof-mindset

#### `reasoning_style` — Problem decomposition approach (7 alleles)
- `chain_of_thought` — Step-by-step linear reasoning
- `tree_of_thought` — Branching exploration
- `analogical` — Reasoning by analogy/metaphor
- `first_principles` — Decompose to axioms
- `pattern_matching` — Match to known patterns
- `backwards_chaining` — Start from goal, work backward
- `ralph_wiggums` — **CURSED**: naive but surprising

#### `gate_philosophy` — PREY8 gate field treatment (5 alleles)
- `minimal_compliance` — Fill fields to pass, no more
- `rich_documentation` — Detailed field content
- `adversarial_gates` — Use gates as attack surface review
- `pedagogical` — Gates as teaching moments
- `ceremonial` — **CURSED**: over-the-top ritualistic

#### `meadows_strategy` — Leverage level selection 1-12 (5 alleles)
- `always_high` — Default to L9-L12
- `adaptive` — Match level to problem complexity
- `escalating` — Start low, climb as needed
- `contrarian` — **CURSED**: intentionally mismatched
- `meta_systemic` — Always think at system level

#### `sbe_style` — Given/When/Then specification style (5 alleles)
- `terse` — Minimal, just the facts
- `comprehensive` — Detailed preconditions/postconditions
- `invariant_first` — Lead with safety invariants
- `edge_case_driven` — Focus on boundaries
- `narrative` — **CURSED**: story-like specifications

#### `trust_posture` — Default trust level for bronze data (5 alleles)
- `zero_trust` — Verify everything, trust nothing
- `cautious_optimist` — Trust but verify critical claims
- `paranoid` — Assume hostile context
- `bayesian` — Update trust incrementally
- `dgaf_chaos` — **CURSED**: trust randomly

#### `artifact_discipline` — Code output style (5 alleles)
- `minimal_diff` — Smallest change possible
- `comprehensive_rewrite` — Full implementations
- `test_first` — TDD: write test, then code
- `doc_first` — Document, then implement
- `spike_and_refine` — Quick prototype, then harden

### 2.2 Genome Operations

| Operation | Signature | Description |
|-----------|-----------|-------------|
| `random_genome()` | `→ Genome` | Random allele per trait |
| `genome.mutate(rate)` | `float → Genome` | Swap alleles with probability `rate` |
| `genome.crossover(other)` | `Genome → Genome` | Uniform crossover of traits |
| `genome.to_system_prompt()` | `→ str` | Render as structured system prompt (## sections) |
| `genome.fingerprint()` | `→ str` | SHA256 of sorted trait dict (dedup key) |

### 2.3 System Prompt Rendering

`to_system_prompt()` renders each trait as a `## Section Header` block:
```
## Communication Style
Active allele: adversarial_coach
Description: Tough love, challenges everything
...
```

The prompt has **8 section markers** (one per trait) plus a preamble.

---

## 3. Fitness Vector

### 3.1 Six Dimensions

| Dimension | Weight | Range | Source |
|-----------|--------|-------|--------|
| `coding_accuracy` | 0.30 | 0.0–1.0 | Test pass rate from `run_tests()` |
| `gate_compliance` | 0.25 | 0.0–1.0 | `score_gate_compliance()` — PREY8 field extraction |
| `adversarial_depth` | 0.20 | 0.0–1.0 | `score_adversarial_depth()` — keyword density |
| `meadows_alignment` | 0.10 | 0.0–1.0 | `score_meadows_alignment()` — level appropriateness |
| `token_efficiency` | 0.10 | 0.0–1.0 | Tokens used relative to quality |
| `latency_score` | 0.05 | 0.0–1.0 | Time to generate response |

### 3.2 Aggregate Score

$$\text{aggregate} = \sum_{i=1}^{6} w_i \cdot s_i$$

Where $w_i$ are the weights above and $s_i$ are the dimension scores.

### 3.3 Pareto Dominance

Genome A **dominates** B iff:
- $\forall i: A_i \geq B_i$ (A is at least as good on every dimension)
- $\exists i: A_i > B_i$ (A is strictly better on at least one)

---

## 4. Model Evaluation Grid

### 4.1 2×2 Grid Layout

|  | Low Intelligence | High Intelligence |
|---|---|---|
| **Small** | gemma3:4b (3.3GB) | deepseek-r1:8b (5.2GB) |
| **Large** | phi4:14b (9.1GB) | qwen3:30b-a3b (18GB MoE) |

### 4.2 Grid Evaluation

Each genome is evaluated across all 4 grid cells via `evaluate_genome_across_grid()`.
This produces a FitnessVector per model and an aggregate cross-grid fitness.

### 4.3 Hardware Requirements

- **Minimum:** Intel Arc 140V (16GB VRAM) with `OLLAMA_VULKAN=1`
- **Generation speed:** ~21 tok/s generation, ~46 tok/s prompt processing
- **Timeout:** 180s per generation call

---

## 5. Selection & Evolution

### 5.1 NSGA-II Non-Dominated Sorting

`pareto_nondominated_sort(population)` assigns each genome to a Pareto front:
- **Front 0:** Non-dominated solutions (the Pareto-optimal set)
- **Front 1:** Dominated only by Front 0
- **Front N:** Dominated by Fronts 0 through N-1

### 5.2 Tournament Selection

`tournament_select(population, k=3)` — pick k random genomes, return the one
with the highest aggregate fitness.

### 5.3 Evolution Operators

| Operator | Rate | Description |
|----------|------|-------------|
| Elitism | Top 2 | Best 2 genomes survive unchanged |
| Crossover | Remainder | Uniform crossover of parent traits |
| Mutation | 0.3 | Each trait has 30% chance of random re-roll |

---

## 6. SSOT Integration

### 6.1 Stigmergy Event Types

| Event Type | Phase | Content |
|------------|-------|---------|
| `hfo.gen89.p2.chimera.init` | Initialization | Population size, baselines, grid config |
| `hfo.gen89.p2.chimera.eval` | Evaluation | genome_id, traits, fitness, aggregate, model |
| `hfo.gen89.p2.chimera.generation` | Generation | Best/worst fitness, Pareto front size |
| `hfo.gen89.p2.chimera.complete` | Completion | Final archive, best genomes per grid cell |

### 6.2 Blood Trail Data Fields

Every `chimera.eval` event includes:
```json
{
  "genome_id": "fingerprint_hash",
  "traits": {"tone": "adversarial_coach", ...},
  "fitness": {"coding_accuracy": 0.8, ...},
  "aggregate_score": 0.72,
  "model": "gemma3:4b",
  "generation": 3,
  "population_slot": 2
}
```

### 6.3 Resumption

`--resume` flag reads the latest `chimera.generation` event from SSOT stigmergy
and reconstructs the population state for continued evolution.

---

## 7. BDD Test Coverage

### 7.1 Feature File: `chimera_loop.feature` (8 scenarios)

| Scenario | Status | Tests |
|----------|--------|-------|
| Genome random generation | GREEN | 8 traits, valid alleles |
| Genome mutation | GREEN | Key preservation, value change |
| Genome crossover | GREEN | Child alleles from parents |
| System prompt rendering | GREEN | 8 section markers, 200+ chars |
| FitnessVector dominance | GREEN | Pareto dominance correctness |
| Aggregate weights | GREEN | coding_accuracy=1.0 → aggregate=0.30 |
| SSOT chimera events | GREEN | ≥1 chimera event exists |
| Blood trail data fields | GREEN | genome_id, traits, aggregate_score |

### 7.2 Supporting Infrastructure (tested in other features)

| Feature | Scenarios | Status | What It Tests |
|---------|-----------|--------|---------------|
| `session_recovery.feature` | 5 | GREEN | Orphan reaper, yield ratio ≥25% |
| `lineage_tracking.feature` | 4 | GREEN | 576+ lineage entries from perceive refs |
| `fitness_decay.feature` | 4 | GREEN | Half-life 14d exponential decay |
| `medallion_promotion.feature` | 4 | GREEN | Bronze → silver gate with validation |

**Total: 25 scenarios, 110 steps, all GREEN** (0.16s)

---

## 8. File Inventory

| File | Layer | Purpose |
|------|-------|---------|
| `hfo_p2_chimera_loop.py` | bronze | Core chimera engine (1,371 lines) |
| `hfo_fitness_decay.py` | bronze | Exponential half-life fitness decay |
| `hfo_lineage_populator.py` | bronze | Auto-populate lineage from perceive refs |
| `hfo_session_recovery.py` | bronze | Orphan reaper and yield enforcement |
| `hfo_medallion_promotion.py` | bronze | Bronze → silver gate with validation |
| `chimera_loop.feature` | bronze | BDD scenarios for chimera engine |
| `hfo_gen_89_p2_mirror_magus_chimera_v1.agent.md` | governance | P2 agent mode |

---

## 9. Seeded Baselines (Generation 0)

| # | Name | Key Traits | Expected Strength |
|---|------|-----------|-------------------|
| 0 | Default Red Regnant | adversarial_coach + red_team_full + test_first | Current P4 production persona |
| 1 | Chaos Chimera | All CURSED alleles | Ablation: is chaos ever useful? |
| 2 | Formal Fortress | cold_analytical + formal_verification + paranoid | Maximum rigor, maximum cost |
| 3 | Zen Minimalist | zen_master + surface_scan + minimal_diff | Minimum overhead, fast feedback |

---

## 10. Galois Dyad Context

The P2-P5 dyad (SHAPE-IMMUNIZE) forms the **safety spine** of creation:

$$P2 + P5 = 2 + 5 = 7 \quad \text{(Galois anti-diagonal dyad sum)}$$

- **P2 SHAPE creates.** New genomes, artifacts, solutions.
- **P5 IMMUNIZE tests.** Stryker-style mutation, BDD gates, GRUDGE guards.
- In the PREY8 Execute tile, P2 is paired with **P4 DISRUPT** — creation and adversarial testing are structurally inseparable.
- In the PREY8 Yield tile, P5 is paired with **P3 INJECT** — testing and delivery are structurally inseparable.

This means: **you cannot create without being challenged, and you cannot deliver without being tested.** The architecture enforces it.

---

*Generated 2026-02-19 by P4 Red Regnant during SBE/ATDD RED→GREEN cycle. 25/25 scenarios GREEN.*
