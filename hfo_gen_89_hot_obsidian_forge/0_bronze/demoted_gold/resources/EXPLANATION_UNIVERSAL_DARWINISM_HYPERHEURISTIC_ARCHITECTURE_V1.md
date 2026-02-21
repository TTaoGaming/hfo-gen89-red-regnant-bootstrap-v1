---
medallion_layer: gold
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.diataxis.explanation.v1
title: "Universal Darwinism Hyperheuristic Architecture for HFO Gen89"
port: P4
domain: DISRUPT
created: 2026-02-19
bluf: "The operator does not decide the best answer. Universal Darwinism with AI agents determines the correct-by-construction answer through evolutionary pressure on ALL pipeline layers — prompts, preprocessing, processing, postprocessing. SQLite SSOT is the fitness landscape. Stryker-on-results is the quality gate. Everything gets mutated."
---

# Universal Darwinism Hyperheuristic Architecture for HFO Gen89

> **"I don't get to decide what the best answer to my question is. UNIVERSAL_DARWINISM with AI agents get to tell me the correct-by-construction answer."** — TTAO

---

## 1. The Thesis

**Universal Darwinism** (Dawkins 1983, Dennett 1995, Campbell 2016) states:
wherever you have **variation**, **selection**, and **retention** operating on
**replicators**, evolution occurs. It is substrate-independent.

In HFO Gen89, the replicators are not genes or memes — they are **pipeline
configurations**: the prompts, extraction logic, scoring functions, selection
operators, and archive topologies that transform a user's question into a
correct-by-construction answer.

**Hyperheuristic** (Burke et al. 2003): a heuristic that selects or generates
heuristics. The system does not use a fixed algorithm to solve problems — it
evolves the algorithm itself.

**The operator's role shifts from "deciding the answer" to "defining the fitness
landscape and letting evolution find what works."**

---

## 2. Current State — What Exists Today

### 2.1 The Chimera Loop (`hfo_p2_chimera_loop.py`, 1,373 lines)

| Component | Status | What It Mutates |
|-----------|--------|-----------------|
| `Genome` dataclass | ✅ Working | 8 persona traits (tone, adversarial_depth, reasoning_style, gate_philosophy, meadows_strategy, sbe_style, trust_posture, artifact_discipline) |
| `FitnessVector` | ✅ Working | 6 dimensions (coding_accuracy, gate_compliance, adversarial_depth, meadows_alignment, token_efficiency, latency_score) |
| `to_system_prompt()` | ✅ Working | Renders traits to system prompt text |
| `mutate()` | ✅ Working | Random allele swap per trait (rate-controlled) |
| `crossover()` | ✅ Working | Uniform crossover between two parents |
| `tournament_select()` | ✅ Working | Tournament selection (size 3) |
| `pareto_nondominated_sort()` | ✅ Working | NSGA-II style fronts |
| 2×2 Model Grid | ⚠️ Partial | gemma3:4b + qwen2.5-coder:7b working; phi4:14b/gemma3:12b timeout on Intel Arc |
| SSOT stigmergy logging | ✅ Working | CloudEvents for init/eval/generation/complete |
| MAP-ELITES archive | ❌ Missing | Grid results exist but no persistent archive with replacement policy |

### 2.2 The Eval Harness (`prey8_eval_harness.py`, 1,063 lines)

| Component | Status | What It Does |
|-----------|--------|--------------|
| 20 HumanEval-style problems | ✅ Working | HFE-001 through HFE-020 (easy/medium) |
| `extract_code()` | ✅ Working | Strips `<think>` tags, finds code blocks or bare functions |
| `run_tests()` | ✅ Working | Subprocess execution with 10s timeout |
| `ollama_generate()` | ✅ Working | HTTP API to local Ollama |
| `extract_prey8_fields()` | ✅ Working | JSON parse + regex fallback for structured fields |
| `validate_prey8_fields()` | ✅ Working | Gate compliance scoring |
| SSOT event logging | ✅ Working | Writes eval events to stigmergy_events |

### 2.3 Empirical Results (from live runs)

| Run | Grid | Genome | Code | Gate | Adv | Meadows | Aggregate |
|-----|------|--------|------|------|-----|---------|-----------|
| Quick test | gemma3:4b | Default Red Regnant | 67% | 100% | 65% | 87% | 0.765 |
| Gen 1, Genome 1 | 2-model | Default Red Regnant | 80% | 100% | 62% | 96% | 0.803 |

---

## 3. The 4-Layer Mutation Surface

**Current chimera loop mutates only Layer 2 (system prompt persona traits).**
Universal Darwinism requires mutating ALL FOUR layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 4: POSTPROCESSING (Selection + Archive)                  │
│  What: selection operators, archive topology, replacement       │
│  policy, Pareto front extraction, hall-of-fame maintenance      │
│  Current: fixed tournament(3) + NSGA-II + elitism(2)            │
│  Gap: no mutation. no archive persistence. no adaptive          │
│  selection pressure. no diversity maintenance.                  │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: PROCESSING (Fitness Evaluation)                       │
│  What: fitness dimensions, weights, scoring functions,          │
│  aggregation method, normalization, threshold tuning            │
│  Current: 6 fixed dims, fixed weights (0.30/0.25/0.15/0.10/    │
│  0.10/0.10), fixed scoring heuristics                           │
│  Gap: no weight evolution. no dimension addition/removal.       │
│  no adaptive normalization. Goodhart's Law risk.                │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: PREPROCESSING (Prompt Construction + Code Extraction) │
│  What: system prompt template, user prompt format, few-shot     │
│  exemplars, code extraction regex, think-tag stripping,         │
│  response parsing                                               │
│  Current: fixed CHIMERA_EVAL_PROMPT template, fixed extract_    │
│  code(), fixed JSON parsing                                     │
│  Gap: no prompt template mutation. no few-shot exemplar         │
│  evolution. no extraction strategy variation.                   │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: INPUT (Persona Traits — "the genome")                 │
│  What: trait alleles that define agent persona                  │
│  Current: 8 traits × 5-7 alleles = ~16M combinatorial space    │
│  Status: ✅ WORKING. This is the only layer currently mutated.  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Layer 1: Input Genome (✅ Implemented)

**Search space:** 7 × 6 × 7 × 5 × 5 × 5 × 5 × 5 = 1,837,500 unique genomes

| Trait | Alleles | Cursed? |
|-------|---------|---------|
| tone | 7 | chaos_gremlin, zen_master |
| adversarial_depth | 6 | chaos_monkey |
| reasoning_style | 7 | ralph_wiggums |
| gate_philosophy | 5 | ceremonial |
| meadows_strategy | 5 | contrarian |
| sbe_style | 5 | narrative |
| trust_posture | 5 | dgaf_chaos |
| artifact_discipline | 5 | spike_and_refine |

**What's working:** Mutation, crossover, tournament selection, seeded baselines.

### 3.2 Layer 2: Preprocessing (❌ Not Mutated)

Things that SHOULD be evolvable but are currently FIXED:

| Component | Current Fixed Value | Mutation Candidates |
|-----------|-------------------|---------------------|
| System prompt template | `CHIMERA_EVAL_PROMPT` (fixed string) | Template structure, section ordering, emphasis, length |
| User prompt format | Raw problem text | Add/remove docstring hints, type annotations, example counts |
| Few-shot exemplars | None | 0-shot, 1-shot, 3-shot with exemplar selection |
| Code extraction | `extract_code()` regex | Multiple extraction strategies, AST-based, LLM-based |
| Response format | JSON with fields | XML, YAML, plain text with markers |
| Think-tag handling | Strip `<think>` | Keep partial, summarize, use for scoring |

**DSPy-style optimization lives here.** DSPy (Khattab et al. 2023) compiles
declarative language model programs by optimizing prompts and few-shot examples.
The analog in HFO: the `CHIMERA_EVAL_PROMPT` template and the way problems are
presented to models should be evolved, not hand-crafted.

### 3.3 Layer 3: Processing (❌ Not Mutated)

| Component | Current Fixed Value | Mutation Candidates |
|-----------|-------------------|---------------------|
| Fitness dimensions | 6 fixed | Add: code style, docstring quality, type safety, complexity |
| Dimension weights | `[0.30, 0.25, 0.15, 0.10, 0.10, 0.10]` | Evolve weights as meta-genome |
| Aggregation | Weighted sum | Geometric mean, harmonic mean, min-of-all, lexicographic |
| Normalization | Linear (fixed ranges) | Percentile-ranked, z-score, domain-adaptive |
| Adversarial scoring | Keyword heuristic | LLM-as-judge, AST analysis, semantic similarity |
| Meadows scoring | Level matching heuristic | Context-dependent matching, multi-level detection |
| Token efficiency | Linear inverse (2000 max) | Per-model normalization, complexity-adjusted |

**Goodhart's Law warning:** When the current 6-dimension weighted sum becomes
the optimization target, agents WILL game it. The chimera will evolve to produce
responses that score high on the HEURISTICS while potentially degrading on actual
quality. The defense: evolve the fitness function itself so there is no stable
target to game.

### 3.4 Layer 4: Postprocessing (❌ Not Mutated)

| Component | Current Fixed Value | Mutation Candidates |
|-----------|-------------------|---------------------|
| Selection | Tournament(3) | Tournament(K), roulette, rank-based, truncation |
| Pareto sort | NSGA-II | SPEA2, MOEA/D, epsilon-dominance |
| Elitism | Fixed 2 | Adaptive elitism, age-based replacement |
| Archive | None (in-memory only) | MAP-ELITES persistent grid, novelty archive, quality-diversity |
| Diversity | None | Niche sharing, crowding distance, fitness sharing |
| Population sizing | Fixed | Self-adaptive population size |
| Crossover | Uniform | Single-point, two-point, trait-group-aware |
| Mutation rate | Fixed 0.3 | Self-adaptive (1/5 success rule, Rechenberg) |

---

## 4. The Stryker-on-Results Pattern

**Core insight:** Stryker mutation testing doesn't just test code — it tests
whether your TESTS are discriminating enough to catch changes. Apply this to
EVAL RESULTS:

```
Standard:  Code → Tests → Pass/Fail
Stryker:   Mutate(Code) → Tests → If Still Pass → TEST IS WEAK

Applied to Chimera:
Standard:  Genome → Eval → Fitness Score
Stryker:   Mutate(Genome MINIMALLY) → Eval → If Score UNCHANGED → EVAL IS WEAK
```

### 4.1 What Stryker-on-Results Detects

| Mutation | Expected | If Score Unchanged |
|----------|----------|-------------------|
| Swap one trait allele | Score changes | Fitness function ignores that trait |
| Change model (small→large) | Score changes | Model axis not discriminating |
| Remove adversarial_check | Gate compliance drops | Working correctly |
| Submit wrong code | Coding accuracy drops | Working correctly |
| Submit empty PREY8 fields | Gate score drops | Working correctly |
| Add verbose filler text | Token efficiency drops | If unchanged: efficiency metric broken |

### 4.2 Implementation Path (SQLite-Native)

```sql
-- Store mutation test results
CREATE TABLE IF NOT EXISTS chimera_mutation_tests (
    id INTEGER PRIMARY KEY,
    original_genome_id TEXT NOT NULL,
    mutant_genome_id TEXT NOT NULL,
    mutation_type TEXT NOT NULL,  -- 'trait_swap', 'model_swap', 'field_removal', etc.
    mutation_detail TEXT,
    original_score REAL,
    mutant_score REAL,
    score_delta REAL,
    killed BOOLEAN,  -- true if mutation was detected (score changed significantly)
    timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (original_genome_id) REFERENCES chimera_genomes(genome_id)
);

-- Mutation kill rate = quality of fitness function
-- If kill rate < 80%, fitness function has blind spots
```

---

## 5. Fast-Eval / Deferred-Eval Tiering

**Problem:** Intel Arc 140V 16GB VRAM can run gemma3:4b at ~45s/problem but
phi4:14b and qwen3:30b-a3b timeout or OOM. Running all models on all genomes
is prohibitively slow.

**Solution:** 3-tier evaluation pyramid.

```
           ┌───────────────────┐
           │  TIER 3: CHAMPION │  Full grid, all problems, 3 trials
           │  (deferred)       │  Only Pareto-front winners from T2
           │  Cloud API / NPU  │  Run nightly or on-demand
           ├───────────────────┤
           │  TIER 2: PROMOTED │  2-model grid, 10 problems, 1 trial
           │  (minutes)        │  Top 25% from T1
           │  gemma3:4b +      │  Runs after each generation
           │  qwen2.5-coder:7b │
           ├───────────────────┤
           │  TIER 1: SCREEN   │  1 model, 3 problems, 1 trial
           │  (seconds)        │  ALL genomes
           │  gemma3:4b only   │  ~2 min per genome
           └───────────────────┘
```

| Tier | Models | Problems | Trials | Time/Genome | Purpose |
|------|--------|----------|--------|-------------|---------|
| T1 Screen | gemma3:4b | 3 | 1 | ~2 min | Fast reject: kill clearly unfit |
| T2 Promote | gemma3:4b + qwen2.5-coder:7b | 10 | 1 | ~15 min | Cross-model validation |
| T3 Champion | Full grid + cloud | 20 | 3 | ~hours | Definitive fitness for Pareto front |

**Tier promotion is itself evolvable:** the threshold for T1→T2 promotion
could be a gene in a meta-genome.

---

## 6. SQLite as MAP-ELITES Infrastructure

The SSOT SQLite database can natively support the full MAP-ELITES archive
without external dependencies:

### 6.1 Archive Schema

```sql
-- Persistent MAP-ELITES archive
CREATE TABLE IF NOT EXISTS chimera_archive (
    id INTEGER PRIMARY KEY,
    -- Grid coordinates (the MAP axes)
    model_cell TEXT NOT NULL,      -- 'small_low', 'small_high', etc.
    trait_bucket TEXT NOT NULL,     -- genomic phenotype bucket (hashed trait combo)
    -- The genome
    genome_id TEXT NOT NULL,
    genome_json TEXT NOT NULL,      -- full Genome serialized
    -- Fitness
    fitness_json TEXT NOT NULL,     -- FitnessVector serialized
    aggregate_score REAL NOT NULL,
    -- Provenance
    generation INTEGER NOT NULL,
    parent_ids TEXT,               -- comma-separated parent genome IDs
    timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    -- A cell is occupied by AT MOST ONE genome (the best seen so far)
    UNIQUE(model_cell, trait_bucket)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_archive_score ON chimera_archive(aggregate_score DESC);
CREATE INDEX IF NOT EXISTS idx_archive_gen ON chimera_archive(generation);

-- Pattern/antipattern mining
CREATE TABLE IF NOT EXISTS chimera_patterns (
    id INTEGER PRIMARY KEY,
    pattern_type TEXT NOT NULL,     -- 'pattern' or 'antipattern'
    trait_name TEXT NOT NULL,       -- which trait
    allele_value TEXT NOT NULL,     -- which allele
    context TEXT,                   -- model, problem type, etc.
    avg_fitness_delta REAL,         -- how much this allele helps/hurts
    sample_size INTEGER,
    confidence REAL,               -- statistical confidence
    timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
```

### 6.2 What SQLite Can Do Natively

| Capability | SQLite Feature | External Needed? |
|------------|---------------|------------------|
| Persistent archive | Tables + UNIQUE constraints | No |
| Pattern mining | SQL GROUP BY + AVG + windowing | No |
| Fitness tracking | Regular tables + indices | No |
| Stigmergy events | Existing `stigmergy_events` table | No |
| FTS search for patterns | Existing FTS5 index | No |
| Lineage graph | Existing `lineage` table (0 rows, ready) | No |
| Mutation test results | New table (see §4.2) | No |
| Pareto front extraction | SQL with self-joins | No |
| Time-series fitness | SQL ORDER BY timestamp | No |
| Export for visualization | JSON/CSV export queries | No |

### 6.3 What Needs External Dependencies

| Capability | Why SQLite Isn't Enough | Recommended Tool |
|------------|------------------------|------------------|
| Prompt optimization (DSPy-style) | Needs gradient-free optimization over prompt templates | **Custom:** evolve prompt templates as genomes (no DSPy dep needed — we ARE the DSPy) |
| Statistical significance | Need proper hypothesis testing on fitness deltas | `scipy.stats` (lightweight, likely already available) |
| Visualization | MAP-ELITES heatmaps, fitness landscapes | `matplotlib` or export JSON to Obsidian/web |
| Cloud model eval | Tier 3 champion evaluation | `httpx` to OpenRouter/Gemini API (already have pattern) |
| NPU/OpenVINO offload | Hardware acceleration for inference | `openvino` + `optimum` (not currently installed) |
| Advanced multiobjective | MOEA/D, reference point methods | `pymoo` or custom (NSGA-II is already implemented) |

**Key insight: We do NOT need DSPy as a dependency.** The chimera loop IS a
DSPy-equivalent: it optimizes prompts through evolutionary search. What we need
is to EXPAND the mutation surface to include prompt templates, not import a
separate framework.

---

## 7. Gap Analysis — Current vs Vision

### 7.1 Critical Gaps (Must Fix)

| # | Gap | Severity | Current | Target | Effort |
|---|-----|----------|---------|--------|--------|
| G1 | **Only Layer 1 mutated** | CRITICAL | 8 persona traits only | All 4 layers | L — new genome types |
| G2 | **No persistent MAP-ELITES archive** | CRITICAL | In-memory, lost on restart | SQLite archive table | S — schema + insert/replace |
| G3 | **No fast-eval tiering** | HIGH | All evals take same time | 3-tier pyramid | M — refactor evaluate_genome |
| G4 | **No Stryker-on-results** | HIGH | Fitness assumed correct | Mutation testing fitness function | M — new module |
| G5 | **No pattern/antipattern mining** | HIGH | No learning from history | SQL pattern extraction | S — queries on existing data |
| G6 | **No fitness weight evolution** | HIGH | Fixed [0.30,0.25,0.15,0.10,0.10,0.10] | Meta-genome for weights | S — extend Genome class |
| G7 | **Model grid limited by VRAM** | MEDIUM | Only 2 of 4 cells work | Tier 3 cloud API for large models | M — add cloud eval path |

### 7.2 Structural Weaknesses

| # | Weakness | Impact | Root Cause |
|---|----------|--------|-----------|
| W1 | **Goodhart's Law exposure** | Agents will game fixed fitness | Fixed scoring heuristics (keyword matching for adversarial, level matching for meadows) |
| W2 | **No statistical significance** | Can't distinguish signal from noise | Single trial per eval, no confidence intervals |
| W3 | **No diversity preservation** | Population converges prematurely | No niche sharing, no novelty pressure |
| W4 | **Lineage table empty** | Can't trace evolutionary pathways | lineage table exists (0 rows) but chimera loop doesn't write to it |
| W5 | **HumanEval problems too easy** | Ceiling effect at 80-100% coding accuracy | Only easy/medium difficulty, max 20 problems |
| W6 | **No problem co-evolution** | Fixed problem set can be overfitted | Problems should evolve alongside solutions |
| W7 | **No cross-session resume** | Evolution restarts from scratch | `--resume` flag exists but implementation incomplete |

### 7.3 Dependency Assessment

| External | Needed For | Priority | Available? |
|----------|-----------|----------|------------|
| `scipy.stats` | Statistical significance | HIGH | Check: `pip install scipy` |
| `matplotlib` | Fitness landscape visualization | MEDIUM | Check: `pip install matplotlib` |
| `pymoo` | Advanced multiobjective (MOEA/D) | LOW | Not needed — NSGA-II sufficient for now |
| `openvino` | NPU offload for large models | LOW | Not installed (`False` in probe) |
| `httpx` | Already used | — | ✅ Available |
| DSPy | Prompt optimization | NONE | **Not needed — chimera loop IS the optimizer** |
| Stryker.js | JavaScript mutation testing | NONE | **Not applicable — we implement the concept, not the tool** |

---

## 8. The Hyperheuristic Genome — Proposed Extension

### 8.1 Meta-Genome (Layer 3 + 4 mutations)

Extend the current `Genome` to include meta-genes that control the evaluation
and selection process itself:

```python
META_TRAITS = {
    "fitness_weights": {
        "desc": "How to weight fitness dimensions",
        "alleles": [
            "balanced",            # [0.30, 0.25, 0.15, 0.10, 0.10, 0.10]
            "code_dominant",       # [0.50, 0.15, 0.10, 0.10, 0.08, 0.07]
            "gate_dominant",       # [0.20, 0.40, 0.15, 0.10, 0.08, 0.07]
            "adversarial_focus",   # [0.20, 0.20, 0.35, 0.10, 0.08, 0.07]
            "efficiency_focus",    # [0.20, 0.20, 0.10, 0.10, 0.25, 0.15]
        ],
    },
    "aggregation_method": {
        "desc": "How to combine fitness dimensions",
        "alleles": [
            "weighted_sum",        # Current method
            "geometric_mean",      # Penalizes zeros harder
            "harmonic_mean",       # Penalizes weakness harder
            "min_of_all",          # Bottleneck-driven
            "lexicographic",       # Prioritize dimensions in order
        ],
    },
    "selection_pressure": {
        "desc": "How strong selection pressure is",
        "alleles": [
            "tournament_3",        # Current
            "tournament_5",        # Stronger pressure
            "tournament_2",        # Weaker pressure
            "rank_proportional",   # Rank-based
            "truncation_50",       # Top 50% only
        ],
    },
    "diversity_mechanism": {
        "desc": "How to maintain population diversity",
        "alleles": [
            "none",                # Current (no diversity)
            "fitness_sharing",     # Penalize similar genomes
            "crowding_distance",   # NSGA-II style
            "novelty_bonus",       # Reward new phenotypes
            "island_model",        # Parallel subpopulations
        ],
    },
    "prompt_template": {
        "desc": "How to structure the eval prompt",
        "alleles": [
            "json_structured",     # Current CHIMERA_EVAL_PROMPT
            "xml_structured",      # XML tags for fields
            "minimal_code_only",   # Just ask for code
            "chain_of_thought",    # Ask for reasoning first
            "few_shot_3",          # Include 3 solved examples
        ],
    },
    "extraction_strategy": {
        "desc": "How to extract code from model response",
        "alleles": [
            "regex_code_blocks",   # Current extract_code()
            "ast_parse_first",     # Try AST parse, fallback regex
            "last_function_def",   # Find last def statement
            "full_response_exec",  # Execute entire response as code
            "llm_extract",         # Use small model to extract code
        ],
    },
}
```

### 8.2 Evolution of Evolution

The meta-genome creates a **two-level evolutionary loop**:

```
OUTER LOOP (meta-evolution):
  Mutate: fitness weights, selection method, prompt template, extraction
  Evaluate: avg fitness improvement over K generations of inner loop
  Select: meta-genome that produces best fitness trajectory

INNER LOOP (persona evolution — current chimera loop):
  Mutate: 8 persona traits
  Evaluate: coding + gate + adversarial + meadows + efficiency + latency
  Select: tournament → next generation
```

This is the **hyperheuristic**: the outer loop evolves heuristics (fitness
functions, selection methods) that the inner loop uses to evolve personas.

---

## 9. Stigmergy Pattern/Antipattern Mining

The SSOT already contains evaluation data in `stigmergy_events`. Mining for
patterns and antipatterns:

```sql
-- Which trait alleles correlate with HIGH fitness?
-- (pseudocode — actual implementation extracts from JSON data)
SELECT 
    json_extract(data, '$.traits.tone') as tone,
    AVG(json_extract(data, '$.aggregate_score')) as avg_score,
    COUNT(*) as sample_size
FROM stigmergy_events
WHERE event_type = 'hfo.gen89.chimera.eval'
GROUP BY tone
ORDER BY avg_score DESC;

-- Which trait COMBINATIONS are antipatterns?
-- (high gate compliance but low coding accuracy = ceremony without substance)
SELECT 
    json_extract(data, '$.traits.gate_philosophy') as gate_phil,
    json_extract(data, '$.traits.artifact_discipline') as artifact,
    AVG(json_extract(data, '$.fitness.coding_accuracy')) as avg_code,
    AVG(json_extract(data, '$.fitness.gate_compliance')) as avg_gate,
    COUNT(*) as n
FROM stigmergy_events
WHERE event_type = 'hfo.gen89.chimera.eval'
GROUP BY gate_phil, artifact
HAVING n >= 3
ORDER BY avg_code ASC;
```

**Key antipattern hypothesis:** `ceremonial` gate_philosophy + `dgaf_chaos`
trust_posture = high gate compliance (fills fields) but low coding accuracy
(doesn't actually solve problems). Evolution should kill this combination.

---

## 10. Prioritized Remediation Roadmap

### Phase 1: Fast Foundations (1-2 sessions)

1. **[G3] Implement fast-eval tiering** — Add `--tier` flag to chimera loop.
   T1 (screen): 1 model, 3 problems. T2 (promote): 2 models, 10 problems.
   Run T1 on all genomes, T2 only on top 25%.

2. **[G2] Persistent MAP-ELITES archive** — Create `chimera_archive` table in
   SSOT. On each eval, INSERT OR REPLACE if new score > existing score for that
   cell. Archive survives restarts.

3. **[G5] Pattern mining queries** — Write SQL queries to extract trait→fitness
   correlations from existing chimera.eval stigmergy events. Store results in
   `chimera_patterns` table.

### Phase 2: Meta-Evolution (2-3 sessions)

4. **[G6] Fitness weight evolution** — Add `META_TRAITS` to Genome class.
   Start with just `fitness_weights` as the first meta-gene. Let it evolve
   alongside persona traits.

5. **[G4] Stryker-on-results** — After each generation, run minimal mutations
   on the best genome. If score doesn't change, log which fitness dimensions
   are non-discriminating.

6. **[W3] Diversity preservation** — Add crowding distance from NSGA-II to
   prevent premature convergence.

### Phase 3: Full Hyperheuristic (3-5 sessions)

7. **[G1] Layer 2 mutation** — Evolve prompt templates. Start with 5 template
   variants as alleles. Evaluate each template × persona × model.

8. **Two-level evolution** — Implement outer loop for meta-genome evolution.
   Inner loop runs K=3 generations per meta-genome evaluation.

9. **[G7] Cloud API tier** — Add Tier 3 evaluation using OpenRouter API for
   large models that don't fit in 16GB VRAM.

10. **[W6] Problem co-evolution** — Generate new HumanEval problems using LLMs.
    Problems that NO genome can solve are too hard. Problems ALL solve are too
    easy. Evolve the difficulty frontier.

---

## 11. Architectural Invariants

These MUST be maintained through all evolution:

| Invariant | Why | Enforcement |
|-----------|-----|-------------|
| All evaluation data → SSOT | Reproducibility, auditability | Every eval writes CloudEvent |
| Fitness function is kill-tested | Goodhart's Law defense | Stryker-on-results after each gen |
| Archive is persistent | Evolution survives restarts | SQLite archive table with UNIQUE |
| Lineage is tracked | Trace evolutionary pathways | Write to `lineage` table on each child |
| Patterns are mined | Learn from history | SQL pattern extraction after each gen |
| Fast tier gates slow tier | Don't waste compute on unfit | T1 screen before T2 promote |
| Meta-evolution is logged | Trace which meta-strategies work | Separate event type for meta-evals |

---

## 12. Related Documents

| Doc | Source | Relevance |
|-----|--------|-----------|
| Doc 4: SDD Without Reward Hacking | SSOT diataxis | 6-defense stack, mutation gate = defense 3 |
| Doc 17: Master Todo | SSOT diataxis | Leverage-ordered priorities |
| Doc 26: DSE Octree | SSOT diataxis | 8 mutation operators, octree numbering |
| Doc 27: Strangler Fig MAP-ELITE | SSOT diataxis | P6 workflow for evolutionary extraction |
| Doc 37: Agent Swarm Guidance | SSOT diataxis | 2026 swarm patterns |
| Doc 129: Octree Port-Pair | SSOT | PREY8 step mapping |
| Doc 317: Meadows 12 Levels | SSOT | Leverage level framework |

---

*Created 2026-02-19 by P4 Red Regnant. Session ea9e0dbf0cb9564b.*
*SSOT-grounded: all claims reference actual files or document IDs.*
*Version: v1. Review cycle: after first complete chimera evolution run.*
