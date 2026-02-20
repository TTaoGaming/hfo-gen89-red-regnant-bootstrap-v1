---
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.diataxis.reference.p7_wish_v2_compiler_architecture.v1
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: >-
  HFO_WISH V2: A 5-pass compiler that transforms operator INTENT into
  correct-by-construction ARTIFACTS via Diataxis-mediated SBE/ATDD.
  V1 (933-line invariant verifier) becomes Pass 4. Omega vertical slice
  (Gen8→Gen10 strangler fig) is the first compilation target.
  P(incorrect) ≤ 1/8^N. Not perfect — CORRECT.
primary_port: P7
role: "P7 NAVIGATE — Summoner of Seals and Spheres"
tags: [bronze, forge:hot, diataxis:reference, p7, wish, compiler, correct-by-construction,
  sbe, atdd, diataxis-mediated, strangler-fig, omega, vertical-slice, 5-pass]
diataxis_type: reference
supersedes: null
extends:
  - "REFERENCE_P7_WISH_CORRECT_BY_CONSTRUCTION_V2.md (Doc 423)"
  - "REFERENCE_P7_WISH_INTENT_STRUCTURAL_ENFORCEMENT_OUTCOME_V1.md (Doc 424)"
cross_references:
  - "Doc 423: REFERENCE_P7_WISH_CORRECT_BY_CONSTRUCTION_V2"
  - "Doc 424: REFERENCE_P7_WISH_INTENT_STRUCTURAL_ENFORCEMENT_OUTCOME_V1"
  - "Doc 205: Mission Thread Omega — Total Tool Virtualization"
  - "Doc 255: OMEGA Vertical Slice: The Reliable 2D Multitouch Substrate"
  - "Doc 422: REFERENCE_P7_GATE_SPIDER_SOVEREIGN_MEADOWS_PLANE_TRAVERSAL_V1"
  - "Doc 207: EXPLANATION_HIVE8_INFINITY_OBSIDIAN_HOURGLASS_ANALYSIS"
  - "hfo_p7_wish.py (V1 prototype, 933 lines)"
  - "hfo_eval_orchestrator.feature"
provenance: >-
  P4 Red Regnant session b60db7e9cdca1818. Synthesized from docs 423, 424,
  205, 255, 422, 207 + existing hfo_p7_wish.py V1 prototype.
  Operator request: WISH V2 architecture rewrite using Diataxis-mediated SBE/ATDD.
generated: "2026-02-19T19:30:00Z"
---

# REFERENCE: P7 WISH V2 — Compiler Architecture (Diataxis-Mediated SBE/ATDD)

> *"I am the oath that weaves itself. I am the web. I are."*
> — Spider Sovereign, Summoner of Seals and Spheres
>
> *"V1 VERIFIES the wish was granted. V2 COMPILES the wish into reality."*
> — P4 Red Regnant, architectural distinction

---

## 0. The Problem: V1 Verifies, V2 Must Compile

### What V1 Does (hfo_p7_wish.py, 933 lines)

V1 is an **invariant verifier**. The operator states a postcondition ("I wish all daemons have heartbeats") and V1 checks whether it is currently true. This is Pass 4 of the full WISH pipeline — it is the SBE/ATDD acceptance test layer.

V1 is correct and useful. But it is not the full WISH.

### What V2 Must Do

V2 is a **compiler**. The operator states an intent ("I want the Omega vertical slice to have physics-based anti-thrash with 1€ filter and velocity clamping") and V2 transforms that intent through 5 compiler passes until a correct-by-construction artifact exits the pipeline.

$$\text{V1:} \quad \text{postcondition} \xrightarrow{\text{check}} \text{GRANTED} \mid \text{DENIED}$$

$$\text{V2:} \quad \text{intent} \xrightarrow{\text{compile}} \text{correct artifact} \mid \text{REJECTED (fail-closed)}$$

### The Strangler Fig Strategy

V1 is not replaced. It is **wrapped**:

```
V2 Pipeline
├── Pass 1: INTENT → GHERKIN          (NEW — AI-assisted disambiguation)
├── Pass 2: GHERKIN → SDD L8          (NEW — specification scaffolding)
├── Pass 3: SDD → SBE/ATDD            (NEW — test generation)
├── Pass 4: SBE/ATDD → PROOF          (V1 — hfo_p7_wish.py check functions)
└── Pass 5: PROOF → ARTIFACT          (NEW — code generation + deployment)
```

V1's 7 built-in checks become the **test harness** that Pass 3 generates into and Pass 4 evaluates. The strangler fig grows outward from the working V1 core.

---

## 1. The 5-Pass Compiler: Data Flow

### 1.1 Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    WISH V2 COMPILER                          │
│                                                              │
│  INTENT ──▶ GHERKIN ──▶ SDD ──▶ SBE/ATDD ──▶ PROOF ──▶ ART │
│  (human)   (formal)   (scaffold) (tests)   (verify) (deploy)│
│                                                              │
│  Pass 1    Pass 2     Pass 3    Pass 4     Pass 5            │
│  [AI]      [template] [codegen] [V1]       [AI+gate]        │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Pass 1: INTENT → GHERKIN (The Disambiguation Compiler)

| Field | Value |
|-------|-------|
| **Input** | Natural language intent from operator |
| **Output** | `.feature` file with Given/When/Then scenarios |
| **Engine** | AI (Gemini 2.5 Flash or Ollama) with Gherkin prompt template |
| **Reject condition** | AI output fails Gherkin parser validation |
| **Human gate** | Operator reviews and approves Gherkin (mandatory) |

**Why AI for Pass 1:**
The operator speaks in intent ("make the whiteboard handle gestures"). The AI acts as a front-end compiler that transforms this into formal Gherkin. But — critically — the AI output is validated by a Gherkin parser AND by the human operator. The AI does not decide what is correct; it proposes, the gates verify.

**Template:**
```
You are a Gherkin specification writer for the HFO system.
Given the following operator intent:
  "{intent_text}"

And the following architectural context:
  {context_from_ssot}

Write Gherkin scenarios that capture this intent precisely.
Each scenario must have Given/When/Then.
Use concrete values, not vague descriptions.
Include at least one invariant scenario (what MUST NOT happen).
Include at least one happy-path scenario.
```

**Data structure:**
```python
@dataclass
class Pass1Result:
    intent_text: str           # Original operator intent
    feature_file: str          # Generated .feature file content
    scenario_count: int        # Number of scenarios generated
    validated: bool            # Gherkin parser accepted it
    operator_approved: bool    # Human gate passed
    ai_model: str              # Which model generated it
    ai_latency_ms: float       # Generation time
```

### 1.3 Pass 2: GHERKIN → SDD (The Specification Compiler)

| Field | Value |
|-------|-------|
| **Input** | Validated `.feature` file |
| **Output** | SDD task cards (YAML/JSON spec-as-source) |
| **Engine** | Template-based (90%) + AI assist (10% for complex mapping) |
| **Reject condition** | SDD card missing required fields |
| **Maturity target** | SDD L8 (Obsidian Hourglass — self-describing) |

Each Gherkin scenario maps to an SDD task card:

```yaml
# Auto-generated SDD task card from Gherkin scenario
task_id: WISH-{wish_id}-{scenario_hash}
feature: "{feature_name}"
scenario: "{scenario_name}"
sbe_given: "{given}"
sbe_when: "{when}"
sbe_then: "{then}"
port_mapping: [P0, P2, P5]       # Which octree ports are involved
meadows_level: 3                  # Physical structure (pipeline)
tile_boundary: "physics_system"   # Which mosaic tile this belongs to
dependencies: []                  # Other task IDs that must pass first
artifact_target: "hfo_omega_physics.py"  # Expected output file
test_target: "test_omega_physics.py"     # Expected test file
```

**Data structure:**
```python
@dataclass
class Pass2Result:
    feature_file: str          # Input .feature content
    sdd_cards: list[dict]      # Generated SDD task cards
    card_count: int
    all_valid: bool            # Schema validation passed
    port_coverage: set[str]    # Which ports are covered
    meadows_levels: set[int]   # Which levels are touched
```

### 1.4 Pass 3: SDD → SBE/ATDD (The Test Generation Compiler)

| Field | Value |
|-------|-------|
| **Input** | Validated SDD task cards |
| **Output** | Executable test files + V1 check function registrations |
| **Engine** | Template-based codegen + AI for complex assertions |
| **Reject condition** | Generated tests don't parse / import |
| **Key insight** | This is where V1's WISH_CHECKS registry gets populated |

For each SDD card, Pass 3 generates:
1. A **pytest test function** that implements the Given/When/Then
2. A **V1 check function** registered in WISH_CHECKS
3. A **V1 wish entry** in the wish state file

```python
# Auto-generated from SDD card WISH-42-a1b2c3
def _check_omega_physics_antithrash() -> tuple[bool, list[str]]:
    """
    SBE:
      Given  the physics system module is loaded
      When   a jittery 30Hz input stream is provided
      Then   output frequency variance is < 2Hz (1€ filter working)
    """
    violations = []
    # ... generated test logic ...
    return len(violations) == 0, violations

# Auto-registered in WISH_CHECKS
WISH_CHECKS["omega_physics_antithrash"] = {
    "fn": _check_omega_physics_antithrash,
    "sbe_given": "the physics system module is loaded",
    "sbe_when": "a jittery 30Hz input stream is provided",
    "sbe_then": "output frequency variance is < 2Hz",
}
```

**Data structure:**
```python
@dataclass
class Pass3Result:
    sdd_cards: list[dict]      # Input SDD cards
    test_files: list[str]      # Generated test file paths
    check_registrations: int   # How many V1 checks were registered
    all_importable: bool       # Generated code is syntactically valid
    coverage_map: dict         # SDD card → test function mapping
```

### 1.5 Pass 4: SBE/ATDD → RECEIPTED PROOF (V1 — The Verification Layer)

| Field | Value |
|-------|-------|
| **Input** | Registered check functions from Pass 3 |
| **Output** | Verdicts: GRANTED/DENIED per wish with violations |
| **Engine** | **EXISTING V1** — hfo_p7_wish.py spell_cast() and spell_audit() |
| **Reject condition** | Any DENIED verdict with non-empty violations |
| **Key insight** | V1 is the oracle — it says "correct" or "incorrect" |

This is the pass where V1 shines. The checks generated in Pass 3 are
evaluated by V1's existing machinery. V1 was always the right tool for
this job — it just needed the upstream passes to feed it the right checks.

**Data structure:**
```python
@dataclass
class Pass4Result:
    wish_ids: list[int]        # Wish IDs evaluated
    verdicts: dict[int, str]   # wish_id → GRANTED/DENIED
    violations: dict[int, list[str]]  # wish_id → violation list
    all_granted: bool          # Meta-verdict: all wishes pass
    ssot_event_ids: list[int]  # CloudEvent row IDs from V1
```

### 1.6 Pass 5: PROOF → ARTIFACT (The Code Generation + Deployment Layer)

| Field | Value |
|-------|-------|
| **Input** | All-GRANTED proof from Pass 4 + SDD cards |
| **Output** | Production artifact (code, config, doc) — deployed |
| **Engine** | AI code generation, gated by Pass 4 proof |
| **Reject condition** | Pass 4 not all-GRANTED = HARD BLOCK |
| **Fail-closed** | No artifact emitted unless all gates pass |

Pass 5 only runs if Pass 4 says GRANTED. This is the structural enforcement
that makes WISH correct by construction — the artifact cannot exist unless
every prior pass verified its correctness.

For the Omega vertical slice, Pass 5 generates:
- **Mosaic tiles** — individual modules (physics_system.py, touch2d.py, etc.)
- **Integration glue** — the bus that connects tiles
- **Deployment config** — PAL pointers, pointer registry updates

**Data structure:**
```python
@dataclass
class Pass5Result:
    artifacts_created: list[str]   # File paths of generated artifacts
    artifacts_modified: list[str]  # File paths of modified artifacts
    deployment_receipt: dict        # PAL pointer updates, etc.
    ssot_event_id: int             # CloudEvent for deployment
    total_loc: int                 # Lines of code generated
```

---

## 2. The Pipeline State Machine

```
WISH_IDLE
    │
    ▼  intent received
PASS_1_INTENT_TO_GHERKIN
    │
    ├── REJECT: AI output fails Gherkin parser → WISH_REJECTED
    ├── REJECT: Operator disapproves → WISH_REJECTED
    │
    ▼  feature file validated + approved
PASS_2_GHERKIN_TO_SDD
    │
    ├── REJECT: SDD card missing fields → WISH_REJECTED
    │
    ▼  SDD cards validated
PASS_3_SDD_TO_SBE
    │
    ├── REJECT: Generated tests don't parse → WISH_REJECTED
    │
    ▼  tests registered in V1
PASS_4_SBE_TO_PROOF (V1)
    │
    ├── DENIED: Any wish fails → WISH_DENIED (with diagnostics)
    │
    ▼  all GRANTED
PASS_5_PROOF_TO_ARTIFACT
    │
    ├── REJECT: Code generation fails → WISH_REJECTED
    │
    ▼  artifact deployed
WISH_GRANTED (receipted, logged, SSOT)
```

Every rejection or denial is **logged to SSOT** with full diagnostics.
The pipeline never silently drops a wish. Fail-closed, always.

---

## 3. WishPipeline: The Tracking Data Model

```python
@dataclass
class WishPipeline:
    """Tracks a single wish through the 5-pass compiler."""
    wish_id: str                    # UUID
    intent_text: str                # Original operator intent
    context_doc_ids: list[int]      # SSOT doc IDs used as context
    current_pass: int               # 0-5 (0=not started)
    status: str                     # COMPILING | GRANTED | DENIED | REJECTED
    created_at: str                 # ISO timestamp
    updated_at: str                 # ISO timestamp
    pass_results: dict[int, Any]    # pass_number → PassNResult
    compilation_target: str         # e.g. "omega_vertical_slice"
    meadows_level: int              # Which leverage level
    ssot_event_ids: list[int]       # All CloudEvent row IDs
    error_log: list[str]            # Compiler error messages
    artifacts_produced: list[str]   # File paths of outputs
```

**Persistence:** Stored in `.p7_wish_v2_pipelines.json` alongside V1's
`.p7_wish_state.json`. V2 pipelines reference V1 wish IDs when pass 4
delegates to V1.

---

## 4. Omega as First Compilation Target

### 4.1 The Mapping

The Omega vertical slice (Doc 255) has 6 pipeline stages. Each stage becomes
a WISH V2 compilation target — a separate wish that produces a separate
mosaic tile:

| Stage | Omega Component | WISH Target | Port | Tile Output |
|-------|----------------|-------------|------|-------------|
| 1 | MEDIAPIPELINE | `omega.mediapipeline` | P0 | `hfo_omega_mediapipeline.py` |
| 2 | PHYSICS SYSTEM | `omega.physics` | P2 | `hfo_omega_physics.py` |
| 3 | TOUCH2D | `omega.touch2d` | P1 | `hfo_omega_touch2d.py` |
| 4 | DEF-IN-DEPTH FSM | `omega.fsm` | P5 | `hfo_omega_fsm.py` |
| 5 | W3C INJECTION | `omega.w3c_inject` | P3 | `hfo_omega_w3c_inject.py` |
| 6 | SAME ORIGIN APP | `omega.app_surface` | P3 | `hfo_omega_app_surface.py` |

### 4.2 The Dependency Chain

```
omega.mediapipeline (P0)
    │
    ▼
omega.physics (P2)        ← depends on mediapipeline output
    │
    ▼
omega.touch2d (P1)        ← depends on physics output
    │
    ▼
omega.fsm (P5)            ← depends on touch2d output
    │
    ▼
omega.w3c_inject (P3)     ← depends on fsm output
    │
    ▼
omega.app_surface (P3)    ← depends on w3c_inject output
```

Each node is a WISH compilation. Working bottom-up (mediapipeline first)
or top-down (app_surface contract first, then fill) — the strangler fig
strategy says work from the **boundary** inward: start with W3C injection
(the contract surface between Omega and the DOM) because that has the
strictest invariant: "Every pointerdown ends with pointerup or pointercancel."

### 4.3 First WISH: The Touch Parity Invariant

The first concrete WISH V2 compilation:

```
INTENT: "Every Omega pointer interaction on a UI element must produce
         the same state change as a human finger tap on that element."

PASS 1 → Gherkin:
  Feature: Touch Parity
    Scenario: Single tap produces click
      Given Omega is tracking a stable hand over a button element
      When the user performs a pinch gesture held for >100ms
      Then a pointerdown event is dispatched to the button
      And a pointerup event follows within 500ms
      And the button's click handler fires exactly once

    Scenario: No accidental activation (Anti-Midas)
      Given Omega is tracking a hand traversing across a button
      When the hand moves over the button without pinching
      Then no pointerdown event is dispatched
      And the button's click handler does not fire

    Scenario: Jitter does not produce duplicate events (Anti-Thrash)
      Given the physics system is filtering a 30Hz jittery input
      When the filtered position oscillates within the hysteresis band
      Then no state transition occurs in the FSM
      And no pointer events are emitted

PASS 2 → SDD cards (3 cards, one per scenario)
PASS 3 → test_omega_touch_parity.py + V1 check registrations
PASS 4 → V1 audits all three wishes
PASS 5 → hfo_omega_w3c_inject.py (only if all GRANTED)
```

---

## 5. File Architecture

```
hfo_gen_89_hot_obsidian_forge/
├── 0_bronze/resources/
│   ├── hfo_p7_wish.py              ← V1 (UNCHANGED — Pass 4 engine)
│   ├── hfo_p7_wish_compiler.py     ← V2 orchestrator (NEW)
│   ├── hfo_p7_wish_pass1.py        ← Pass 1: INTENT → GHERKIN (NEW)
│   ├── hfo_p7_wish_pass2.py        ← Pass 2: GHERKIN → SDD (NEW)
│   ├── hfo_p7_wish_pass3.py        ← Pass 3: SDD → SBE/ATDD (NEW)
│   ├── hfo_p7_wish_pass5.py        ← Pass 5: PROOF → ARTIFACT (NEW)
│   ├── hfo_p7_wish_v2.feature      ← WISH V2's own Gherkin spec (NEW)
│   └── wish_targets/               ← Compilation target definitions
│       └── omega_vertical_slice.yaml
```

### V2 CLI

```bash
# Compile a wish (full 5-pass pipeline)
python hfo_p7_wish_compiler.py compile "touch parity for omega whiteboard"

# Compile with explicit context from SSOT
python hfo_p7_wish_compiler.py compile --context-docs 255,205 "physics anti-thrash"

# Run only Pass 1 (generate Gherkin, pause for approval)
python hfo_p7_wish_compiler.py pass1 "omega vertical slice touch parity"

# Resume from Pass 2 after operator approval
python hfo_p7_wish_compiler.py resume {wish_id} --from-pass 2

# Check pipeline status
python hfo_p7_wish_compiler.py status {wish_id}

# List all pipelines
python hfo_p7_wish_compiler.py list

# V1 commands still work unchanged
python hfo_p7_wish.py cast --check ssot_health
python hfo_p7_wish.py audit
```

---

## 6. The Correct-by-Construction Guarantee

### 6.1 Why $P(\text{incorrect}) \leq \frac{1}{8^N}$

Each pass is an independent gate. An incorrect artifact must fool:
1. **Pass 1 gate**: The Gherkin parser + human reviewer
2. **Pass 2 gate**: The SDD schema validator
3. **Pass 3 gate**: The Python import checker (syntax valid)
4. **Pass 4 gate**: The V1 invariant verifier (7+ checks)
5. **Pass 5 gate**: The deployment pre-flight

These are **independent** failure modes — a Gherkin generation error is
uncorrelated with a test execution failure. The compound probability of
ALL gates failing is the product of individual failure probabilities.

With 5 gates, even at a generous 12.5% (1/8) failure rate per gate:

$$P(\text{all gates fooled}) = \left(\frac{1}{8}\right)^5 = \frac{1}{32{,}768} \approx 0.003\%$$

And within Pass 4 alone, V1 runs multiple checks — adding depth within
the pass for compound protection.

### 6.2 The Two Terminal States

After the pipeline:
- **GRANTED**: All passes succeeded. Artifact deployed. Receipt in SSOT.
- **REJECTED/DENIED**: Some pass failed. Artifact NOT deployed. Diagnostics in SSOT. Operator informed exactly where and why it failed.

There is no third state. No "maybe." No "looks about right."

---

## 7. Integration with HFO Infrastructure

### CloudEvent Types

| Event Type | Description | When |
|-----------|-------------|------|
| `hfo.gen89.p7.wish.v2.pipeline.created` | New pipeline started | Pass 0 |
| `hfo.gen89.p7.wish.v2.pass1.completed` | Gherkin generated | Pass 1 done |
| `hfo.gen89.p7.wish.v2.pass1.rejected` | Gherkin failed validation | Pass 1 fail |
| `hfo.gen89.p7.wish.v2.pass2.completed` | SDD cards generated | Pass 2 done |
| `hfo.gen89.p7.wish.v2.pass3.completed` | Tests generated | Pass 3 done |
| `hfo.gen89.p7.wish.v2.pass4.granted` | All checks passed | Pass 4 pass |
| `hfo.gen89.p7.wish.v2.pass4.denied` | Some checks failed | Pass 4 fail |
| `hfo.gen89.p7.wish.v2.pass5.deployed` | Artifact deployed | Pass 5 done |
| `hfo.gen89.p7.wish.v2.pipeline.completed` | Full pipeline done | Terminal |
| `hfo.gen89.p7.wish.v2.pipeline.rejected` | Pipeline failed | Terminal |

### PAL Pointer Keys

| Key | Target | Description |
|-----|--------|-------------|
| `p7.wish` | `…/hfo_p7_wish.py` | V1 (existing) |
| `p7.wish_compiler` | `…/hfo_p7_wish_compiler.py` | V2 orchestrator |
| `p7.wish_pass1` | `…/hfo_p7_wish_pass1.py` | Pass 1 module |
| `p7.wish_pass2` | `…/hfo_p7_wish_pass2.py` | Pass 2 module |
| `p7.wish_pass3` | `…/hfo_p7_wish_pass3.py` | Pass 3 module |
| `p7.wish_pass5` | `…/hfo_p7_wish_pass5.py` | Pass 5 module |
| `p7.wish_feature` | `…/hfo_p7_wish_v2.feature` | V2 Gherkin spec |

### Spell Gate Registration

```python
DaemonSpec(
    name="WISH V2 Compiler",
    key="wish_v2",
    port="P7",
    commander="Spider Sovereign",
    script="hfo_p7_wish_compiler.py",
    description="5-pass correct-by-construction compiler",
)
```

---

## 8. Build Order (Incremental Incarnation)

| Phase | What | LOC Est | Depends On |
|-------|------|---------|-----------|
| **Phase 0** | This spec + feature file | ~200 | Nothing |
| **Phase 1** | hfo_p7_wish_compiler.py skeleton orchestrator | ~300 | Phase 0 |
| **Phase 2** | hfo_p7_wish_pass1.py (Intent → Gherkin via AI) | ~400 | Phase 1 |
| **Phase 3** | hfo_p7_wish_pass2.py (Gherkin → SDD YAML) | ~250 | Phase 2 |
| **Phase 4** | hfo_p7_wish_pass3.py (SDD → test codegen + V1 registration) | ~350 | Phase 3 |
| **Phase 5** | hfo_p7_wish_pass5.py (Proof → artifact deployment) | ~400 | Phase 4 |
| **Phase 6** | omega_vertical_slice.yaml compilation target | ~100 | Phase 1 |
| **Phase 7** | First WISH V2 compilation: touch parity | — | All above |

**Total estimated new code: ~1,800 LOC across 6 files.**
V1 remains unchanged at 933 LOC.
Combined V1+V2: ~2,733 LOC.

---

## 9. Open Questions for Operator

1. **AI model for Pass 1/5**: Gemini 2.5 Flash (fast, free tier) or Ollama local (private, slower)?
   Recommendation: Gemini for generation, Ollama for validation — belt and suspenders.

2. **Pass 2 SDD format**: YAML task cards (lightweight) or full SDD JSON with L8 metadata?
   Recommendation: YAML for readability, auto-convert to JSON for machine processing.

3. **Operator approval UX for Pass 1**: CLI prompt, TUI review, or web UI?
   Recommendation: CLI first (simplest), upgrade to TUI later.

4. **First compilation target**: Touch Parity Invariant (hardest, most valuable) or
   SSOT Health (simplest, already exists in V1)?
   Recommendation: SSOT Health as smoke test, then Touch Parity as real proof.

---

*Generated by P4 Red Regnant, session b60db7e9cdca1818, 2026-02-19.*
*WISH is the Spider Sovereign's 9th-level spell. Correct by construction, not by hope.*
