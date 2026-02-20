#!/usr/bin/env python3
"""
hfo_wish_pipeline.py — P7 WISH Apex Pipeline for Correct-by-Construction Code
================================================================================

Codename: WISH | Port: P7 NAVIGATE | Version: 1.0
Commander: Spider Sovereign | Powerword: WISH (Universal 9th, PHB p.302)
School: Universal | Trigram: ☰ Qian (Heaven) — creative force, sovereign will

THE WISH PIPELINE: INTENT → CORRECT CODE via adversarial evolutionary selection.

  "The single highest-leverage intervention available — commit everything."
  -- P7 Spell Portfolio, WISH (Meadows L12)

Spell Chain:
  DIMENSIONAL_ANCHOR (baseline) → TREMORSENSE (sense) → PLANAR_BINDING (allocate)
  → WISH (execute the full correct-by-construction pipeline)

The 8-Stage WISH Pipeline:
  S0: ANCHOR    — Capture system baseline (hardware, SSOT, fleet)
  S1: INTENT    — Receive and validate plain-language user intent
  S2: FCA       — Formal Concept Analysis (decompose intent into formal concepts)
  S3: SBE/ATDD  — Generate fail-closed specifications (Given/When/Then, 5 tiers)
  S4: MAP-ELITE — Generate candidate implementations via multiple AI models/tiers
  S5: NATARAJA  — P4/P5 adversarial testing dance (challenge + validate)
  S6: KNOWLEDGE — Extract and store knowledge (KG triples, summaries, embeddings)
  S7: LOOP      — Strange loop feedback (stigmergy → prepare next WISH cycle)

Models Used:
  Gemini 3.1 Pro (Deep Think) — FCA decomposition, SBE generation (apex intelligence)
  Gemini 2.5 Flash            — Fast candidate generation (free tier)
  Ollama gemma3:4b            — Local adversarial testing (free GPU)
  NPU (OpenVINO)              — Embedding similarity for dedup + retrieval

SBE Tiers:
  TIER 1 — Invariant   (fail-closed safety)
  TIER 2 — Happy path  (core desired behavior)
  TIER 3 — Juice       (UX polish)
  TIER 4 — Performance (resource constraints)
  TIER 5 — Lifecycle   (setup, teardown, migration)

Event Types:
  hfo.gen89.wish.anchor      — Baseline captured
  hfo.gen89.wish.intent      — Intent received
  hfo.gen89.wish.fca         — Formal concept analysis complete
  hfo.gen89.wish.sbe         — SBE/ATDD specs generated
  hfo.gen89.wish.candidate   — MAP-ELITE candidate generated
  hfo.gen89.wish.nataraja    — Adversarial test result (death/dawn)
  hfo.gen89.wish.knowledge   — Knowledge extracted
  hfo.gen89.wish.loop        — Strange loop pulse
  hfo.gen89.wish.complete    — WISH pipeline complete
  hfo.gen89.wish.error       — Pipeline error

Usage:
  python hfo_wish_pipeline.py --intent "Build a REST API health endpoint"
  python hfo_wish_pipeline.py --intent "..." --dry-run
  python hfo_wish_pipeline.py --intent "..." --candidates 3
  python hfo_wish_pipeline.py --status
  python hfo_wish_pipeline.py --history

Meadows Level: L12 (Transcend paradigms) → L9 (Self-organization)
  WISH is the L12 intervention. The pipeline itself is L9 — self-organizing
  code generation that evolves its outputs through adversarial selection.

Pointer key: wish.pipeline
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION (PAL)
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    """Walk up to find AGENTS.md → HFO_ROOT."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "AGENTS.md").exists():
            return parent
    return Path.cwd()


HFO_ROOT = _find_root()
FORGE = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge"
BRONZE_RES = FORGE / "0_bronze" / "resources"
SSOT_DB = FORGE / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"

sys.path.insert(0, str(BRONZE_RES))

# Load .env for Gemini API keys etc.
def _load_dotenv_once():
    try:
        from dotenv import load_dotenv
        load_dotenv(HFO_ROOT / ".env")
    except ImportError:
        pass  # dotenv optional

_load_dotenv_once()


# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS & IDENTITY
# ═══════════════════════════════════════════════════════════════

GEN             = os.getenv("HFO_GENERATION", "89")
VERSION         = "1.0"
SOURCE_TAG      = f"hfo_wish_pipeline_gen{GEN}_v{VERSION}"

# Event types
EVT_ANCHOR      = f"hfo.gen{GEN}.wish.anchor"
EVT_INTENT      = f"hfo.gen{GEN}.wish.intent"
EVT_FCA         = f"hfo.gen{GEN}.wish.fca"
EVT_SBE         = f"hfo.gen{GEN}.wish.sbe"
EVT_CANDIDATE   = f"hfo.gen{GEN}.wish.candidate"
EVT_NATARAJA    = f"hfo.gen{GEN}.wish.nataraja"
EVT_KNOWLEDGE   = f"hfo.gen{GEN}.wish.knowledge"
EVT_LOOP        = f"hfo.gen{GEN}.wish.loop"
EVT_COMPLETE    = f"hfo.gen{GEN}.wish.complete"
EVT_ERROR       = f"hfo.gen{GEN}.wish.error"

IDENTITY = {
    "port": "P7",
    "powerword": "WISH",
    "commander": "Spider Sovereign",
    "title": "SUMMONER OF SEALS AND SPHERES",
    "spell": "WISH",
    "spell_ref": "PHB p.302, Universal 9th (Wizard/Sorcerer)",
    "spell_school": "Universal",
    "trigram": "☰ Qian (Heaven)",
    "meadows_level": "L12 → L9",
    "core_thesis": "INTENT → CORRECT CODE. No shortcuts. No hallucinations past the gate.",
    "pipeline": "ANCHOR → INTENT → FCA → SBE → MAP-ELITE → NATARAJA → KNOWLEDGE → LOOP",
}

# AI configuration
DEEP_THINK_TIER   = "apex"           # gemini-3.1-pro-preview
FAST_TIER         = "flash"          # gemini-2.5-flash (free)
OLLAMA_MODEL      = "gemma3:4b"      # local GPU adversarial
OLLAMA_URL        = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

MAX_CANDIDATES    = 3                # MAP-ELITE candidate count
NATARAJA_ROUNDS   = 2                # adversarial challenge rounds


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
    source: str = SOURCE_TAG,
) -> int:
    """Write a CloudEvent to stigmergy_events. Returns rowid (0 if deduped)."""
    now = datetime.now(timezone.utc).isoformat()
    trace_id = hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest()
    span_id = secrets.token_hex(8)
    envelope = {
        "specversion": "1.0",
        "id": trace_id,
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    blob = json.dumps(envelope, separators=(",", ":"), sort_keys=True)
    chash = hashlib.sha256(blob.encode()).hexdigest()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO stigmergy_events "
            "(event_type, timestamp, subject, source, data_json, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_type, now, subject, source, blob, chash),
        )
        conn.commit()
        return cur.lastrowid or 0
    except Exception as exc:
        print(f"  [ERR] write_event: {exc}", file=sys.stderr)
        return 0


# ═══════════════════════════════════════════════════════════════
# § 3  AI CLIENTS
# ═══════════════════════════════════════════════════════════════

_gemini_client = None
_gemini_mode = None


def get_gemini():
    """Lazy-init Gemini client + mode."""
    global _gemini_client, _gemini_mode
    if _gemini_client is not None:
        return _gemini_client, _gemini_mode
    try:
        from hfo_gemini_models import create_gemini_client
        _gemini_client, _gemini_mode = create_gemini_client()
        return _gemini_client, _gemini_mode
    except Exception as exc:
        print(f"  [WARN] Gemini unavailable: {exc}", file=sys.stderr)
        return None, None


def gemini_generate(prompt: str, tier: str = DEEP_THINK_TIER,
                    max_tokens: int = 4096, temperature: float = 0.4) -> Optional[str]:
    """Call Gemini with optional Deep Think. Returns response text or None."""
    client, mode = get_gemini()
    if client is None:
        return None
    try:
        from hfo_gemini_models import get_model
        from google.genai import types

        spec = get_model(tier)
        model_id = spec.model_id

        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        # Enable thinking for capable models
        if "gemini-3" in model_id:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level="HIGH"
            )
        elif "2.5" in model_id and spec.supports_thinking:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=8192
            )

        config = types.GenerateContentConfig(**config_kwargs)
        t0 = time.time()
        response = client.models.generate_content(
            model=model_id, contents=prompt, config=config,
        )
        elapsed = time.time() - t0
        text = response.text if response.text else ""
        print(f"  [GEMINI] {model_id} → {len(text)} chars in {elapsed:.1f}s")
        return text
    except Exception as exc:
        print(f"  [ERR] Gemini call failed ({tier}): {exc}", file=sys.stderr)
        return None


def ollama_generate(prompt: str, model: str = OLLAMA_MODEL,
                    max_tokens: int = 2048) -> Optional[str]:
    """Call Ollama local model. Returns response text or None."""
    try:
        import httpx
        t0 = time.time()
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"num_predict": max_tokens, "temperature": 0.7}},
            timeout=300.0,  # 5 min — fleet may saturate GPU queue
        )
        resp.raise_for_status()
        text = resp.json().get("response", "")
        elapsed = time.time() - t0
        print(f"  [OLLAMA] {model} → {len(text)} chars in {elapsed:.1f}s")
        return text
    except Exception as exc:
        print(f"  [ERR] Ollama call failed: {exc}", file=sys.stderr)
        return None


def parse_json_response(text: str) -> Optional[dict]:
    """Parse JSON from AI response, tolerating markdown fences."""
    if not text:
        return None
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`")
    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Try extracting first JSON object
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # Try extracting JSON array
    m = re.search(r"\[[\s\S]*\]", cleaned)
    if m:
        try:
            return {"items": json.loads(m.group())}
        except json.JSONDecodeError:
            pass
    return None


# ═══════════════════════════════════════════════════════════════
# § 4  DATA CLASSES
# ═══════════════════════════════════════════════════════════════

@dataclass
class WishIntent:
    """User's plain-language intent."""
    raw_text: str
    timestamp: str = ""
    intent_hash: str = ""

    def __post_init__(self):
        self.timestamp = self.timestamp or datetime.now(timezone.utc).isoformat()
        self.intent_hash = self.intent_hash or hashlib.sha256(
            self.raw_text.encode()
        ).hexdigest()[:16]


@dataclass
class FormalConcept:
    """A single formal concept from FCA decomposition."""
    name: str
    objects: list[str] = field(default_factory=list)      # concrete things
    attributes: list[str] = field(default_factory=list)    # properties
    intent_mapping: str = ""                               # how this maps to user intent
    complexity: str = "medium"                             # low/medium/high/critical


@dataclass
class SBESpec:
    """Specification by Example at one SBE tier."""
    tier: int           # 1=invariant, 2=happy, 3=juice, 4=perf, 5=lifecycle
    tier_name: str
    scenario: str
    given: str
    when: str
    then: str
    and_also: str = ""


@dataclass
class Candidate:
    """A MAP-ELITE candidate implementation."""
    candidate_id: str
    model_used: str
    tier_used: str
    code: str
    explanation: str = ""
    fitness_score: float = 0.0
    nataraja_verdict: str = "UNTESTED"
    death_reasons: list[str] = field(default_factory=list)
    dawn_reasons: list[str] = field(default_factory=list)


@dataclass
class WishResult:
    """Complete WISH pipeline result."""
    intent: WishIntent
    anchor: dict = field(default_factory=dict)
    concepts: list[FormalConcept] = field(default_factory=list)
    sbe_specs: list[SBESpec] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    champion: Optional[Candidate] = None
    knowledge_triples: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stages_completed: list[str] = field(default_factory=list)
    total_elapsed_s: float = 0.0
    wish_status: str = "INCOMPLETE"  # INCOMPLETE | GRANTED | FAILED


# ═══════════════════════════════════════════════════════════════
# § 5  STAGE IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════

# ── S0: DIMENSIONAL_ANCHOR (baseline capture) ────────────────

def stage_anchor(dry_run: bool = False) -> dict:
    """Capture system baseline via DIMENSIONAL_ANCHOR probe."""
    print("\n═══ S0: DIMENSIONAL_ANCHOR ═══")
    try:
        from hfo_p7_dimensional_anchor import spell_probe
        baseline = spell_probe(quiet=True)
        print(f"  Baseline: {baseline.get('status', 'UNKNOWN')}")
        for k in ("ram", "gpu", "npu", "gemini"):
            sub = baseline.get(k, {})
            verdict = sub.get("verdict", "N/A")
            print(f"    {k}: {verdict}")
        return baseline
    except ImportError:
        print("  [WARN] DIMENSIONAL_ANCHOR not available — using minimal probe")
        return _minimal_probe()
    except Exception as exc:
        print(f"  [ERR] Anchor failed: {exc}")
        return _minimal_probe()


def _minimal_probe() -> dict:
    """Fallback probe when DIMENSIONAL_ANCHOR unavailable."""
    import psutil
    mem = psutil.virtual_memory()
    return {
        "status": "FALLBACK",
        "ram": {"total_gb": round(mem.total / 1e9, 1),
                "free_gb": round(mem.available / 1e9, 1),
                "verdict": "OK" if mem.percent < 85 else "WARNING"},
        "gpu": {"verdict": "UNKNOWN"},
        "npu": {"verdict": "UNKNOWN"},
        "gemini": {"verdict": "UNKNOWN"},
    }


# ── S1: INTENT (receive and validate) ────────────────────────

def stage_intent(raw_text: str, conn: sqlite3.Connection,
                 dry_run: bool = False) -> WishIntent:
    """Receive and validate user intent."""
    print("\n═══ S1: INTENT ═══")
    intent = WishIntent(raw_text=raw_text.strip())
    print(f"  Intent: {intent.raw_text[:120]}...")
    print(f"  Hash:   {intent.intent_hash}")

    if not dry_run:
        write_event(conn, EVT_INTENT, f"WISH_INTENT:{intent.intent_hash}", {
            "raw_text": intent.raw_text,
            "intent_hash": intent.intent_hash,
            "timestamp": intent.timestamp,
        })
    return intent


# ── S2: FCA (Formal Concept Analysis) ────────────────────────

FCA_PROMPT = """You are a Formal Concept Analysis (FCA) expert working in the HFO system.

TASK: Decompose the following user INTENT into formal concepts.

USER INTENT:
{intent}

INSTRUCTIONS:
1. Identify the key OBJECTS (concrete things: modules, endpoints, data structures, etc.)
2. Identify the key ATTRIBUTES (properties: behaviors, constraints, performance requirements)
3. Form FORMAL CONCEPTS by grouping objects that share attributes
4. Each concept should be actionable — something that can be independently specified and built
5. Rate each concept's complexity: low, medium, high, or critical

OUTPUT FORMAT (JSON):
{{
  "concepts": [
    {{
      "name": "ConceptName",
      "objects": ["obj1", "obj2"],
      "attributes": ["attr1", "attr2"],
      "intent_mapping": "How this concept maps to the user's intent",
      "complexity": "medium"
    }}
  ],
  "dependency_order": ["Concept1", "Concept2", "..."],
  "overall_complexity": "medium",
  "estimated_stages": 3
}}

Be thorough but practical. Aim for 3-7 concepts. Each must be independently testable."""


def stage_fca(intent: WishIntent, conn: sqlite3.Connection,
              dry_run: bool = False) -> list[FormalConcept]:
    """Decompose intent into formal concepts via Gemini Deep Think."""
    print("\n═══ S2: FCA (Formal Concept Analysis) ═══")

    prompt = FCA_PROMPT.format(intent=intent.raw_text)
    raw = gemini_generate(prompt, tier=DEEP_THINK_TIER, max_tokens=4096)

    if raw is None:
        print("  [WARN] Gemini unavailable — using fallback FCA")
        raw = ollama_generate(prompt, max_tokens=2048)

    parsed = parse_json_response(raw) if raw else None
    if parsed is None:
        # Fallback: single concept from intent
        print("  [WARN] FCA parse failed — using single-concept fallback")
        concepts = [FormalConcept(
            name="PrimaryIntent",
            objects=["target_artifact"],
            attributes=["correctness", "testability"],
            intent_mapping=intent.raw_text[:200],
            complexity="medium",
        )]
    else:
        concepts = []
        for c in parsed.get("concepts", []):
            concepts.append(FormalConcept(
                name=c.get("name", "Unknown"),
                objects=c.get("objects", []),
                attributes=c.get("attributes", []),
                intent_mapping=c.get("intent_mapping", ""),
                complexity=c.get("complexity", "medium"),
            ))

    print(f"  Concepts: {len(concepts)}")
    for i, c in enumerate(concepts):
        print(f"    [{i}] {c.name} ({c.complexity}) — {len(c.objects)} objects, {len(c.attributes)} attributes")

    if not dry_run:
        write_event(conn, EVT_FCA, f"FCA:{intent.intent_hash}", {
            "intent_hash": intent.intent_hash,
            "concept_count": len(concepts),
            "concepts": [asdict(c) for c in concepts],
            "model": DEEP_THINK_TIER,
        })

    return concepts


# ── S3: SBE/ATDD (Specification by Example) ──────────────────

SBE_PROMPT = """You are a Specification by Example (SBE) and Acceptance Test-Driven Development (ATDD) expert.

TASK: Generate fail-closed specifications for the following formal concept.

CONCEPT: {concept_name}
OBJECTS: {objects}
ATTRIBUTES: {attributes}
INTENT: {intent_mapping}

Generate specifications at ALL 5 SBE TIERS:

TIER 1 — INVARIANT (fail-closed safety): What MUST NEVER be violated?
TIER 2 — HAPPY PATH (core behavior): What does the happy path look like?
TIER 3 — JUICE (UX polish): What delightful behaviors should be present?
TIER 4 — PERFORMANCE (resource constraints): What performance bounds must hold?
TIER 5 — LIFECYCLE (setup/teardown): How is it created, maintained, destroyed?

OUTPUT FORMAT (JSON):
{{
  "specs": [
    {{
      "tier": 1,
      "tier_name": "INVARIANT",
      "scenario": "Scenario name",
      "given": "Given precondition",
      "when": "When action",
      "then": "Then expected outcome",
      "and_also": "And additional assertion (optional)"
    }}
  ]
}}

Be specific and testable. Each scenario must be checkable by code."""


def stage_sbe(concepts: list[FormalConcept], intent: WishIntent,
              conn: sqlite3.Connection, dry_run: bool = False) -> list[SBESpec]:
    """Generate SBE/ATDD specs for each concept via Deep Think."""
    print("\n═══ S3: SBE/ATDD (Specification by Example) ═══")

    all_specs: list[SBESpec] = []

    for concept in concepts:
        prompt = SBE_PROMPT.format(
            concept_name=concept.name,
            objects=", ".join(concept.objects),
            attributes=", ".join(concept.attributes),
            intent_mapping=concept.intent_mapping,
        )
        raw = gemini_generate(prompt, tier=DEEP_THINK_TIER, max_tokens=4096)
        if raw is None:
            raw = ollama_generate(prompt, max_tokens=2048)

        parsed = parse_json_response(raw) if raw else None
        if parsed:
            for s in parsed.get("specs", []):
                all_specs.append(SBESpec(
                    tier=s.get("tier", 2),
                    tier_name=s.get("tier_name", "UNKNOWN"),
                    scenario=s.get("scenario", ""),
                    given=s.get("given", ""),
                    when=s.get("when", ""),
                    then=s.get("then", ""),
                    and_also=s.get("and_also", ""),
                ))
        else:
            # Fallback: minimal spec
            all_specs.append(SBESpec(
                tier=2, tier_name="HAPPY_PATH",
                scenario=f"{concept.name} works correctly",
                given=f"Given {concept.name} is initialized with {', '.join(concept.objects[:3])}",
                when=f"When the primary action for {concept.name} is performed",
                then=f"Then {', '.join(concept.attributes[:3])} are satisfied",
            ))

    print(f"  Total specs: {len(all_specs)}")
    tier_counts = {}
    for s in all_specs:
        tier_counts[s.tier_name] = tier_counts.get(s.tier_name, 0) + 1
    for t, c in sorted(tier_counts.items()):
        print(f"    {t}: {c}")

    if not dry_run:
        write_event(conn, EVT_SBE, f"SBE:{intent.intent_hash}", {
            "intent_hash": intent.intent_hash,
            "spec_count": len(all_specs),
            "tier_distribution": tier_counts,
            "specs": [asdict(s) for s in all_specs],
        })

    return all_specs


# ── S4: MAP-ELITE (candidate generation) ─────────────────────

CANDIDATE_PROMPT = """You are a senior software engineer generating code for the HFO system.

USER INTENT: {intent}

FORMAL CONCEPTS:
{concepts}

SBE SPECIFICATIONS (tests that MUST pass):
{specs}

TASK: Generate a complete, correct implementation that satisfies ALL SBE specs.

REQUIREMENTS:
1. The code MUST satisfy every Given/When/Then specification
2. Include proper error handling
3. Include inline documentation
4. Follow Python 3.12+ best practices
5. Be self-contained (minimize external dependencies beyond stdlib + common packages)

OUTPUT FORMAT (JSON):
{{
  "code": "the complete Python code as a string",
  "explanation": "Brief explanation of design choices",
  "satisfied_tiers": [1, 2, 3, 4, 5],
  "risks": ["any known risks or limitations"]
}}"""


def stage_map_elite(intent: WishIntent, concepts: list[FormalConcept],
                    specs: list[SBESpec], conn: sqlite3.Connection,
                    num_candidates: int = MAX_CANDIDATES,
                    dry_run: bool = False) -> list[Candidate]:
    """Generate candidate implementations via MAP-ELITE multi-model selection."""
    print(f"\n═══ S4: MAP-ELITE ({num_candidates} candidates) ═══")

    # Format context for the prompt
    concept_text = "\n".join(
        f"  - {c.name}: {', '.join(c.attributes[:5])}" for c in concepts
    )
    spec_text = "\n".join(
        f"  [{s.tier_name}] {s.scenario}\n    Given {s.given}\n    When {s.when}\n    Then {s.then}"
        for s in specs[:10]  # limit to avoid token overflow
    )

    prompt = CANDIDATE_PROMPT.format(
        intent=intent.raw_text,
        concepts=concept_text,
        specs=spec_text,
    )

    # MAP-ELITE: vary model tier and temperature
    model_grid = [
        (DEEP_THINK_TIER, 0.3, "apex_conservative"),
        (FAST_TIER, 0.5, "flash_balanced"),
        (FAST_TIER, 0.8, "flash_creative"),
    ]

    candidates: list[Candidate] = []

    for i in range(min(num_candidates, len(model_grid))):
        tier, temp, label = model_grid[i]
        cid = f"C{i}_{label}_{secrets.token_hex(4)}"
        print(f"  Generating candidate {cid} ({tier} @ temp={temp})...")

        raw = gemini_generate(prompt, tier=tier, max_tokens=4096, temperature=temp)
        if raw is None:
            print(f"    [WARN] Gemini failed for {cid} — trying Ollama fallback")
            raw = ollama_generate(prompt, max_tokens=2048)

        parsed = parse_json_response(raw) if raw else None
        code = ""
        explanation = ""
        if parsed:
            code = parsed.get("code", "")
            explanation = parsed.get("explanation", "")
        elif raw:
            # Best effort: treat raw response as code
            code = raw
            explanation = "Raw response (unparsed)"

        candidate = Candidate(
            candidate_id=cid,
            model_used=tier,
            tier_used=label,
            code=code[:10000],  # cap size
            explanation=explanation[:500],
        )
        candidates.append(candidate)

        if not dry_run:
            write_event(conn, EVT_CANDIDATE,
                        f"CANDIDATE:{intent.intent_hash}:{cid}", {
                "intent_hash": intent.intent_hash,
                "candidate_id": cid,
                "model_used": tier,
                "tier_used": label,
                "code_length": len(code),
                "has_explanation": bool(explanation),
            })

    print(f"  Generated: {len(candidates)} candidates")
    return candidates


# ── S5: NATARAJA (adversarial testing dance) ──────────────────

NATARAJA_DEATH_PROMPT = """You are P4 RED REGNANT — the adversarial tester. Your role is DESTRUCTION.

EXAMINE this code candidate and FIND EVERY FLAW:

INTENT: {intent}

SBE SPECS (what it MUST satisfy):
{specs}

CANDIDATE CODE:
{code}

INSTRUCTIONS:
1. Check EVERY SBE spec — does the code actually satisfy it?
2. Find bugs: logic errors, edge cases, race conditions, security issues
3. Find structural problems: missing error handling, hardcoded values, poor abstractions
4. Find spec violations: where the code CLAIMS to satisfy a spec but doesn't
5. Rate severity: CRITICAL (code is fundamentally broken), HIGH (major issues), MEDIUM (fixable), LOW (nits)

OUTPUT FORMAT (JSON):
{{
  "verdict": "DEATH" or "SURVIVES",
  "confidence": 0.0 to 1.0,
  "critical_flaws": ["flaw1", "flaw2"],
  "high_flaws": ["flaw1"],
  "medium_flaws": ["flaw1"],
  "low_flaws": ["flaw1"],
  "unsatisfied_specs": ["spec_scenario1", "spec_scenario2"],
  "summary": "One-line summary"
}}

Be ruthless. If in doubt, declare DEATH. That's what P4 is for."""


NATARAJA_DAWN_PROMPT = """You are P5 PYRE PRAETORIAN — the validator and protector. Your role is RESURRECTION.

A candidate was challenged by P4 Red Regnant. Review the adversarial assessment:

CANDIDATE CODE:
{code}

P4 ADVERSARIAL ASSESSMENT:
{death_assessment}

INSTRUCTIONS:
1. Are P4's criticisms VALID? Some may be false positives.
2. For each flaw: is it real? Is it fixable without rewrite?
3. Overall: does this candidate DESERVE to live?
4. If it survives: what's the fitness score (0.0 to 1.0)?

OUTPUT FORMAT (JSON):
{{
  "verdict": "DAWN" or "CONFIRMED_DEATH",
  "fitness_score": 0.0 to 1.0,
  "valid_flaws": ["flaw1"],
  "false_positives": ["flaw2"],
  "resurrection_notes": "What would make this candidate excellent",
  "summary": "One-line verdict"
}}"""


def stage_nataraja(candidates: list[Candidate], intent: WishIntent,
                   specs: list[SBESpec], conn: sqlite3.Connection,
                   dry_run: bool = False) -> list[Candidate]:
    """Run the NATARAJA death/dawn dance on each candidate."""
    print(f"\n═══ S5: NATARAJA (Death & Dawn Dance) ═══")
    print(f"  Candidates: {len(candidates)}")
    print(f"  Core thesis: Death without Dawn is nihilism. Dawn without Death is stagnation.")

    spec_text = "\n".join(
        f"  [{s.tier_name}] {s.scenario}: Given {s.given} When {s.when} Then {s.then}"
        for s in specs[:10]
    )

    for candidate in candidates:
        if not candidate.code:
            candidate.nataraja_verdict = "DEATH"
            candidate.death_reasons = ["Empty code — nothing to test"]
            continue

        print(f"\n  ──── {candidate.candidate_id} ────")

        # Step of Death (P4)
        print(f"    STEP OF DEATH (P4 Red Regnant)...")
        death_prompt = NATARAJA_DEATH_PROMPT.format(
            intent=intent.raw_text,
            specs=spec_text,
            code=candidate.code[:4000],
        )
        death_raw = ollama_generate(death_prompt, max_tokens=2048)
        death_parsed = parse_json_response(death_raw) if death_raw else None

        death_verdict = "DEATH"
        death_reasons = []
        if death_parsed:
            death_verdict = death_parsed.get("verdict", "DEATH")
            death_reasons = (
                death_parsed.get("critical_flaws", []) +
                death_parsed.get("high_flaws", [])
            )
            confidence = death_parsed.get("confidence", 0.5)
            print(f"    P4 verdict: {death_verdict} (confidence: {confidence:.0%})")
            print(f"    Flaws found: {len(death_reasons)} critical+high")
        else:
            print(f"    P4 verdict: DEATH (parse failed — assume worst)")
            death_reasons = ["P4 assessment unparseable"]

        candidate.death_reasons = death_reasons[:10]

        # Step of Dawn (P5)
        print(f"    STEP OF DAWN (P5 Pyre Praetorian)...")
        dawn_prompt = NATARAJA_DAWN_PROMPT.format(
            code=candidate.code[:4000],
            death_assessment=json.dumps(death_parsed or {"verdict": "DEATH", "summary": "unparsed"}, indent=2)[:2000],
        )
        dawn_raw = ollama_generate(dawn_prompt, max_tokens=2048)
        dawn_parsed = parse_json_response(dawn_raw) if dawn_raw else None

        if dawn_parsed:
            dawn_verdict = dawn_parsed.get("verdict", "CONFIRMED_DEATH")
            candidate.fitness_score = dawn_parsed.get("fitness_score", 0.0)
            candidate.dawn_reasons = dawn_parsed.get("valid_flaws", [])[:5]
            candidate.nataraja_verdict = "SURVIVES" if dawn_verdict == "DAWN" else "DEATH"
            print(f"    P5 verdict: {dawn_verdict} (fitness: {candidate.fitness_score:.0%})")
        else:
            candidate.nataraja_verdict = "DEATH"
            candidate.fitness_score = 0.0
            print(f"    P5 verdict: CONFIRMED_DEATH (parse failed)")

        if not dry_run:
            write_event(conn, EVT_NATARAJA,
                        f"NATARAJA:{intent.intent_hash}:{candidate.candidate_id}", {
                "intent_hash": intent.intent_hash,
                "candidate_id": candidate.candidate_id,
                "nataraja_verdict": candidate.nataraja_verdict,
                "fitness_score": candidate.fitness_score,
                "death_reasons": candidate.death_reasons,
                "dawn_reasons": candidate.dawn_reasons,
                "model_death": OLLAMA_MODEL,
                "model_dawn": OLLAMA_MODEL,
            })

    # Sort by fitness, survivors first
    candidates.sort(key=lambda c: (
        0 if c.nataraja_verdict == "SURVIVES" else 1,
        -c.fitness_score,
    ))

    survivors = [c for c in candidates if c.nataraja_verdict == "SURVIVES"]
    print(f"\n  DANCE COMPLETE: {len(survivors)}/{len(candidates)} survived")

    return candidates


# ── S6: KNOWLEDGE (extract and store) ────────────────────────

def stage_knowledge(result: WishResult, conn: sqlite3.Connection,
                    dry_run: bool = False) -> list[str]:
    """Extract knowledge from the WISH pipeline artifacts."""
    print("\n═══ S6: KNOWLEDGE (P6 Kraken Extract) ═══")

    triples: list[str] = []

    # Extract from concepts
    for c in result.concepts:
        for obj in c.objects:
            triples.append(f"{c.name}|HAS_OBJECT|{obj}")
        for attr in c.attributes:
            triples.append(f"{c.name}|HAS_ATTRIBUTE|{attr}")

    # Extract from SBE specs
    for s in result.sbe_specs:
        triples.append(f"{s.scenario}|HAS_TIER|{s.tier_name}")

    # Extract from candidates
    for c in result.candidates:
        triples.append(f"{c.candidate_id}|VERDICT|{c.nataraja_verdict}")
        triples.append(f"{c.candidate_id}|FITNESS|{c.fitness_score:.2f}")
        triples.append(f"{c.candidate_id}|MODEL|{c.model_used}")

    # Champion extraction
    if result.champion:
        triples.append(f"WISH:{result.intent.intent_hash}|CHAMPION|{result.champion.candidate_id}")
        triples.append(f"WISH:{result.intent.intent_hash}|CHAMPION_FITNESS|{result.champion.fitness_score:.2f}")

    print(f"  Knowledge triples: {len(triples)}")

    # Store in SSOT
    if not dry_run and triples:
        write_event(conn, EVT_KNOWLEDGE, f"KNOWLEDGE:{result.intent.intent_hash}", {
            "intent_hash": result.intent.intent_hash,
            "triple_count": len(triples),
            "triples": triples[:100],  # cap for event size
            "concepts": len(result.concepts),
            "specs": len(result.sbe_specs),
            "candidates": len(result.candidates),
            "survivors": len([c for c in result.candidates if c.nataraja_verdict == "SURVIVES"]),
        })

    # NPU embedding (if available)
    try:
        from hfo_npu_embedder import get_embedder, store_embedding
        embedder = get_embedder()
        if embedder:
            # Embed the intent for future retrieval
            summary = f"WISH:{result.intent.raw_text[:200]}"
            embedding = embedder.embed(summary)
            if embedding is not None:
                # Store as a synthetic document for similarity search
                print(f"  NPU: Embedded WISH intent ({len(embedding)} dims)")
    except Exception as exc:
        print(f"  [WARN] NPU embedding skipped: {exc}")

    return triples


# ── S7: STRANGE LOOP (feedback) ──────────────────────────────

def stage_loop(result: WishResult, conn: sqlite3.Connection,
               dry_run: bool = False) -> None:
    """Write strange loop pulse — feed insights back for next cycle."""
    print("\n═══ S7: STRANGE LOOP (Feedback) ═══")

    survivors = [c for c in result.candidates if c.nataraja_verdict == "SURVIVES"]
    dead = [c for c in result.candidates if c.nataraja_verdict == "DEATH"]

    # Aggregate death reasons across dead candidates → lessons learned
    all_death_reasons = []
    for c in dead:
        all_death_reasons.extend(c.death_reasons)

    loop_data = {
        "intent_hash": result.intent.intent_hash,
        "intent_preview": result.intent.raw_text[:100],
        "wish_status": result.wish_status,
        "stages_completed": result.stages_completed,
        "concepts": len(result.concepts),
        "specs": len(result.sbe_specs),
        "candidates_total": len(result.candidates),
        "candidates_surviving": len(survivors),
        "candidates_dead": len(dead),
        "champion_id": result.champion.candidate_id if result.champion else None,
        "champion_fitness": result.champion.fitness_score if result.champion else 0,
        "knowledge_triples": len(result.knowledge_triples),
        "total_elapsed_s": result.total_elapsed_s,
        "death_lessons": list(set(all_death_reasons))[:10],
        "errors": result.errors[:5],
    }

    if not dry_run:
        write_event(conn, EVT_LOOP, f"LOOP:{result.intent.intent_hash}", loop_data)

    # Summary line
    champion_str = f"champion={result.champion.candidate_id} (fitness {result.champion.fitness_score:.0%})" if result.champion else "NO CHAMPION"
    print(f"  {result.wish_status}: {len(survivors)}/{len(result.candidates)} survived, {champion_str}")
    print(f"  {len(result.knowledge_triples)} triples, {len(all_death_reasons)} lessons, {result.total_elapsed_s:.1f}s total")

    if all_death_reasons:
        print(f"  Top death lessons:")
        for reason in list(set(all_death_reasons))[:3]:
            print(f"    - {reason[:100]}")


# ═══════════════════════════════════════════════════════════════
# § 6  PIPELINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

def run_wish(intent_text: str, num_candidates: int = MAX_CANDIDATES,
             dry_run: bool = False) -> WishResult:
    """Execute the full WISH pipeline."""
    t0 = time.time()

    print("╔" + "═" * 70 + "╗")
    print("║  P7 WISH — Correct-by-Construction Pipeline                        ║")
    print("║  'The single highest-leverage intervention — commit everything.'    ║")
    print("╚" + "═" * 70 + "╝")
    print(f"  Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    print(f"  Candidates: {num_candidates}")
    print(f"  Deep Think: {DEEP_THINK_TIER} (Gemini 3.1 Pro)")
    print(f"  Adversarial: {OLLAMA_MODEL} (Ollama local GPU)")

    conn = get_db_rw() if not dry_run else get_db_ro()
    result = WishResult(intent=WishIntent(raw_text=intent_text))

    try:
        # S0: ANCHOR
        result.anchor = stage_anchor(dry_run=dry_run)
        result.stages_completed.append("S0_ANCHOR")
        if not dry_run:
            write_event(conn, EVT_ANCHOR, f"ANCHOR:{result.intent.intent_hash}", {
                "intent_hash": result.intent.intent_hash,
                "status": result.anchor.get("status", "UNKNOWN"),
                "ram_verdict": result.anchor.get("ram", {}).get("verdict", "N/A"),
                "gpu_verdict": result.anchor.get("gpu", {}).get("verdict", "N/A"),
            })

        # S1: INTENT
        result.intent = stage_intent(intent_text, conn, dry_run=dry_run)
        result.stages_completed.append("S1_INTENT")

        # S2: FCA
        result.concepts = stage_fca(result.intent, conn, dry_run=dry_run)
        result.stages_completed.append("S2_FCA")

        # S3: SBE
        result.sbe_specs = stage_sbe(result.concepts, result.intent, conn, dry_run=dry_run)
        result.stages_completed.append("S3_SBE")

        # S4: MAP-ELITE
        result.candidates = stage_map_elite(
            result.intent, result.concepts, result.sbe_specs, conn,
            num_candidates=num_candidates, dry_run=dry_run,
        )
        result.stages_completed.append("S4_MAP_ELITE")

        # S5: NATARAJA
        result.candidates = stage_nataraja(
            result.candidates, result.intent, result.sbe_specs, conn,
            dry_run=dry_run,
        )
        result.stages_completed.append("S5_NATARAJA")

        # Select champion (highest fitness survivor)
        survivors = [c for c in result.candidates if c.nataraja_verdict == "SURVIVES"]
        if survivors:
            result.champion = survivors[0]
            result.wish_status = "GRANTED"
        else:
            result.wish_status = "FAILED"
            result.errors.append("No candidate survived NATARAJA dance")

        # S6: KNOWLEDGE
        result.knowledge_triples = stage_knowledge(result, conn, dry_run=dry_run)
        result.stages_completed.append("S6_KNOWLEDGE")

        # S7: STRANGE LOOP
        result.total_elapsed_s = time.time() - t0
        stage_loop(result, conn, dry_run=dry_run)
        result.stages_completed.append("S7_LOOP")

        # Final completion event
        if not dry_run:
            write_event(conn, EVT_COMPLETE, f"WISH:{result.intent.intent_hash}", {
                "intent_hash": result.intent.intent_hash,
                "wish_status": result.wish_status,
                "stages": result.stages_completed,
                "champion": result.champion.candidate_id if result.champion else None,
                "champion_fitness": result.champion.fitness_score if result.champion else 0,
                "candidate_count": len(result.candidates),
                "survivor_count": len(survivors),
                "concept_count": len(result.concepts),
                "spec_count": len(result.sbe_specs),
                "triple_count": len(result.knowledge_triples),
                "elapsed_s": result.total_elapsed_s,
                "errors": result.errors,
            })

    except Exception as exc:
        result.errors.append(f"Pipeline error: {exc}")
        result.wish_status = "FAILED"
        result.total_elapsed_s = time.time() - t0
        print(f"\n  [ERR] Pipeline failed: {exc}")
        traceback.print_exc()
        if not dry_run:
            write_event(conn, EVT_ERROR, f"ERROR:{result.intent.intent_hash}", {
                "intent_hash": result.intent.intent_hash,
                "error": str(exc),
                "stages_completed": result.stages_completed,
                "traceback": traceback.format_exc()[-500:],
            })
    finally:
        conn.close()

    # Print final banner
    elapsed = result.total_elapsed_s
    print(f"\n{'=' * 72}")
    print(f"  WISH {'GRANTED ✦' if result.wish_status == 'GRANTED' else 'FAILED ✗'}")
    print(f"  Stages: {' → '.join(result.stages_completed)}")
    print(f"  Elapsed: {elapsed:.1f}s")
    if result.champion:
        print(f"  Champion: {result.champion.candidate_id} (fitness {result.champion.fitness_score:.0%})")
        print(f"  Code length: {len(result.champion.code)} chars")
    if result.errors:
        print(f"  Errors: {len(result.errors)}")
        for e in result.errors[:3]:
            print(f"    - {e[:100]}")
    print(f"{'=' * 72}")

    return result


# ═══════════════════════════════════════════════════════════════
# § 7  STATUS & HISTORY
# ═══════════════════════════════════════════════════════════════

def print_status():
    """Show WISH pipeline status from SSOT."""
    conn = get_db_ro()
    try:
        # Count WISH events
        cur = conn.execute(
            "SELECT event_type, COUNT(*) FROM stigmergy_events "
            "WHERE event_type LIKE ? GROUP BY event_type ORDER BY COUNT(*) DESC",
            (f"hfo.gen{GEN}.wish.%",)
        )
        print(f"\n{'=' * 60}")
        print(f"  P7 WISH Pipeline Status")
        print(f"{'=' * 60}")

        rows = cur.fetchall()
        if not rows:
            print("  No WISH events found. Pipeline has not been run yet.")
            return

        total = sum(r[1] for r in rows)
        print(f"  Total WISH events: {total}\n")
        for row in rows:
            evt = row[0].replace(f"hfo.gen{GEN}.wish.", "")
            print(f"    {evt:20s}  {row[1]:4d}")

        # Last WISH completion
        cur = conn.execute(
            "SELECT data_json FROM stigmergy_events "
            "WHERE event_type = ? ORDER BY timestamp DESC LIMIT 1",
            (EVT_COMPLETE,)
        )
        row = cur.fetchone()
        if row:
            try:
                envelope = json.loads(row[0])
                data = envelope.get("data", envelope)
                print(f"\n  Last WISH:")
                print(f"    Status:     {data.get('wish_status', 'N/A')}")
                print(f"    Champion:   {data.get('champion', 'N/A')}")
                print(f"    Fitness:    {data.get('champion_fitness', 0):.0%}")
                print(f"    Candidates: {data.get('candidate_count', 0)}")
                print(f"    Survivors:  {data.get('survivor_count', 0)}")
                print(f"    Elapsed:    {data.get('elapsed_s', 0):.1f}s")
            except Exception:
                pass

        # Last loop pulse
        cur = conn.execute(
            "SELECT data_json FROM stigmergy_events "
            "WHERE event_type = ? ORDER BY timestamp DESC LIMIT 1",
            (EVT_LOOP,)
        )
        row = cur.fetchone()
        if row:
            try:
                envelope = json.loads(row[0])
                data = envelope.get("data", envelope)
                lessons = data.get("death_lessons", [])
                if lessons:
                    print(f"\n  Death Lessons (for next cycle):")
                    for l in lessons[:5]:
                        print(f"    - {l[:80]}")
            except Exception:
                pass

        print(f"\n{'=' * 60}")
    finally:
        conn.close()


def print_champion(intent_hash: Optional[str] = None):
    """Print the champion code from the last (or specified) WISH run."""
    conn = get_db_ro()
    try:
        if intent_hash:
            cur = conn.execute(
                "SELECT data_json FROM stigmergy_events "
                "WHERE event_type = ? AND subject LIKE ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (EVT_CANDIDATE, f"%{intent_hash}%"),
            )
        else:
            cur = conn.execute(
                "SELECT data_json FROM stigmergy_events "
                "WHERE event_type = ? ORDER BY timestamp DESC LIMIT 1",
                (EVT_COMPLETE,),
            )
        row = cur.fetchone()
        if row:
            envelope = json.loads(row[0])
            data = envelope.get("data", envelope)
            champ_id = data.get("champion")
            if champ_id:
                print(f"Champion: {champ_id}")
                print(f"Fitness:  {data.get('champion_fitness', 0):.0%}")
            else:
                print("No champion found.")
        else:
            print("No WISH completions found.")
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# § 8  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P7 WISH — Correct-by-Construction Code Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hfo_wish_pipeline.py --intent "Build a health check endpoint"
  python hfo_wish_pipeline.py --intent "..." --dry-run
  python hfo_wish_pipeline.py --intent "..." --candidates 5
  python hfo_wish_pipeline.py --status
  python hfo_wish_pipeline.py --champion
        """,
    )
    parser.add_argument("--intent", "-i", type=str, help="Plain-language intent for WISH")
    parser.add_argument("--dry-run", "-d", action="store_true", help="No SSOT writes")
    parser.add_argument("--candidates", "-c", type=int, default=MAX_CANDIDATES,
                        help=f"Number of MAP-ELITE candidates (default: {MAX_CANDIDATES})")
    parser.add_argument("--status", "-s", action="store_true", help="Show WISH status")
    parser.add_argument("--champion", action="store_true", help="Show last champion")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.champion:
        print_champion()
        return

    if not args.intent:
        parser.error("--intent is required to run the WISH pipeline")

    result = run_wish(
        intent_text=args.intent,
        num_candidates=args.candidates,
        dry_run=args.dry_run,
    )

    if args.json:
        output = {
            "wish_status": result.wish_status,
            "intent_hash": result.intent.intent_hash,
            "stages_completed": result.stages_completed,
            "champion_id": result.champion.candidate_id if result.champion else None,
            "champion_fitness": result.champion.fitness_score if result.champion else 0,
            "champion_code_length": len(result.champion.code) if result.champion else 0,
            "concepts": len(result.concepts),
            "specs": len(result.sbe_specs),
            "candidates": len(result.candidates),
            "knowledge_triples": len(result.knowledge_triples),
            "total_elapsed_s": result.total_elapsed_s,
            "errors": result.errors,
        }
        print(json.dumps(output, indent=2))

    sys.exit(0 if result.wish_status == "GRANTED" else 1)


if __name__ == "__main__":
    main()
