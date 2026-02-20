#!/usr/bin/env python3
"""
hfo_devourer_apex_synthesis.py — P6 Devourer Apex Deep-Think System Review
==========================================================================
v1.0 | Gen89 | Port: P6 ASSIMILATE | Commander: Kraken Keeper

PURPOSE:
    One-shot apex synthesis: feed Gemini 3.1 Pro (T5 APEX) deep-think
    a comprehensive HFO system snapshot and capture its full review.

    This is the Devourer operating at maximum intelligence tier —
    not the 4B gemma3 fragment-by-fragment enrichment, but a single
    frontier-intelligence pass reviewing the entire system architecture.

    "The Apex Devourer sees everything. Depths become VISION."

USAGE:
    python hfo_devourer_apex_synthesis.py                    # Full deep-think
    python hfo_devourer_apex_synthesis.py --model gemini-3-pro-preview  # Different model
    python hfo_devourer_apex_synthesis.py --no-think          # Without thinking mode
    python hfo_devourer_apex_synthesis.py --dry-run            # Preview context only

Medallion: bronze
Port: P6 ASSIMILATE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Path resolution ──
def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
GEN = os.environ.get("HFO_GENERATION", "89")

# Load .env
try:
    from dotenv import load_dotenv
    env_path = HFO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass

# Add bronze resources to path for imports
BRONZE_RES = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources"
if str(BRONZE_RES) not in sys.path:
    sys.path.insert(0, str(BRONZE_RES))

DEFAULT_MODEL = "gemini-3.1-pro-preview"
SOURCE_TAG = f"hfo_p6_devourer_apex_gen{GEN}"

# ── MAP-ELITE Variation System ─────────────────────────────────
# Each variation targets a different region of the model quality-diversity space.
# The swarm reads these signals via stigmergy to coordinate scatter-gather.
#
# Grid axes:  PORT (P0-P7) × VARIATION (intelligence|speed|cost)
# Cell key:   "P4:intelligence" → MAP-ELITE archive lookup
#
# Commanders select the best model per cell through evolutionary pressure:
#   intelligence → highest capability, cost no object
#   speed        → fastest response, adequate quality
#   cost         → cheapest per token, bulk runs

OCTREE_PORTS = {
    "P0": {"word": "OBSERVE",    "commander": "Lidless Legion",    "domain": "Sensing under contest"},
    "P1": {"word": "BRIDGE",     "commander": "Web Weaver",        "domain": "Shared data fabric"},
    "P2": {"word": "SHAPE",      "commander": "Mirror Magus",      "domain": "Creation / models"},
    "P3": {"word": "INJECT",     "commander": "Harmonic Hydra",    "domain": "Payload delivery"},
    "P4": {"word": "DISRUPT",    "commander": "Red Regnant",       "domain": "Red team / probing"},
    "P5": {"word": "IMMUNIZE",   "commander": "Pyre Praetorian",   "domain": "Blue team / gates"},
    "P6": {"word": "ASSIMILATE", "commander": "Kraken Keeper",     "domain": "Learning / memory"},
    "P7": {"word": "NAVIGATE",   "commander": "Spider Sovereign",  "domain": "C2 / steering"},
}

MAP_ELITE_VARIATIONS: dict[str, dict] = {
    "intelligence": {
        "model": "gemini-3.1-pro-preview",
        "thinking_budget": 8192,
        "temperature": 0.7,
        "max_output_tokens": 16384,
        "max_context_chars": 80_000,
        "description": "Apex intelligence — maximum capability, deep reasoning",
    },
    "speed": {
        "model": "gemini-3-flash-preview",
        "thinking_budget": 2048,
        "temperature": 0.5,
        "max_output_tokens": 8192,
        "max_context_chars": 40_000,
        "description": "Apex speed — frontier flash, fast turnaround",
    },
    "cost": {
        "model": "gemini-2.5-flash-lite",
        "thinking_budget": 1024,
        "temperature": 0.3,
        "max_output_tokens": 4096,
        "max_context_chars": 25_000,
        "description": "Apex cost — budget bulk, cheapest per token",
    },
}

VALID_VARIATIONS = list(MAP_ELITE_VARIATIONS.keys())
VALID_PORTS = list(OCTREE_PORTS.keys()) + ["ALL"]


# ═══════════════════════════════════════════════════════════════
# § 1  SYSTEM SNAPSHOT GATHERING
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def get_db_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def gather_system_snapshot() -> dict:
    """
    Gather a comprehensive system snapshot for the apex model to review.
    Returns a dict with all the context sections.
    """
    snapshot = {}
    conn = get_db_ro()

    # 1. AGENTS.md (governance document)
    agents_md = HFO_ROOT / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text(encoding="utf-8")
        # Take a substantial portion (first ~8000 chars)
        snapshot["agents_md"] = content[:8000]
    
    # 2. SSOT self-description (quine)
    try:
        quine = conn.execute(
            "SELECT value FROM meta WHERE key = 'quine_instructions'"
        ).fetchone()
        if quine:
            snapshot["quine_instructions"] = quine[0][:3000]
    except Exception:
        pass
    
    # 3. Schema documentation
    try:
        schema = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_doc'"
        ).fetchone()
        if schema:
            snapshot["schema_doc"] = schema[0][:2000]
    except Exception:
        pass

    # 4. Document statistics
    try:
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        sources = conn.execute(
            "SELECT source, COUNT(*) as cnt, SUM(word_count) as words "
            "FROM documents GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        ports = conn.execute(
            "SELECT port, COUNT(*) as cnt FROM documents "
            "WHERE port IS NOT NULL GROUP BY port ORDER BY cnt DESC"
        ).fetchall()
        no_port = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE port IS NULL"
        ).fetchone()[0]
        no_bluf = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE bluf IS NULL OR bluf = '' OR bluf = '---'"
        ).fetchone()[0]
        word_total = conn.execute("SELECT SUM(word_count) FROM documents").fetchone()[0]
        
        snapshot["doc_stats"] = {
            "total_docs": total,
            "total_words": word_total,
            "sources": {r[0]: {"count": r[1], "words": r[2]} for r in sources},
            "port_distribution": {r[0]: r[1] for r in ports},
            "missing_port": no_port,
            "missing_bluf": no_bluf,
            "enrichment_pct_bluf": round(100 * (total - no_bluf) / max(total, 1), 1),
            "enrichment_pct_port": round(100 * (total - no_port) / max(total, 1), 1),
        }
    except Exception as e:
        snapshot["doc_stats_error"] = str(e)

    # 5. Stigmergy event distribution
    try:
        total_events = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        event_types = conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM stigmergy_events "
            "GROUP BY event_type ORDER BY cnt DESC LIMIT 30"
        ).fetchall()
        recent_events = conn.execute(
            "SELECT event_type, timestamp, subject FROM stigmergy_events "
            "ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()
        
        snapshot["stigmergy"] = {
            "total_events": total_events,
            "event_type_distribution": {r[0]: r[1] for r in event_types},
            "recent_events": [
                {"type": r[0], "time": r[1], "subject": r[2]}
                for r in recent_events
            ],
        }
    except Exception as e:
        snapshot["stigmergy_error"] = str(e)

    # 6. Sample high-value documents (gold reports, diataxis, architecture docs)
    try:
        gold_docs = conn.execute(
            "SELECT id, title, bluf, source, port, doc_type, word_count "
            "FROM documents WHERE source IN ('gold_report', 'silver', 'diataxis') "
            "ORDER BY word_count DESC LIMIT 20"
        ).fetchall()
        snapshot["high_value_docs"] = [
            {
                "id": r[0], "title": r[1], "bluf": r[2],
                "source": r[3], "port": r[4], "doc_type": r[5],
                "words": r[6]
            }
            for r in gold_docs
        ]
    except Exception:
        pass

    # 7. Read a few KEY documents in full (architecture-defining)
    key_doc_ids = [4, 95, 129]  # SDD, Mosaic Tiles, Port-Pair Mapping
    try:
        key_docs = []
        for doc_id in key_doc_ids:
            row = conn.execute(
                "SELECT id, title, bluf, substr(content, 1, 3000) as content_preview "
                "FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            if row:
                key_docs.append({
                    "id": row[0], "title": row[1], "bluf": row[2],
                    "content_preview": row[3]
                })
        snapshot["key_architecture_docs"] = key_docs
    except Exception:
        pass

    # 8. Lineage table status
    try:
        lineage_count = conn.execute("SELECT COUNT(*) FROM lineage").fetchone()[0]
        snapshot["lineage_edges"] = lineage_count
    except Exception:
        snapshot["lineage_edges"] = 0

    # 9. Meta table (self-description keys)
    try:
        meta_keys = conn.execute(
            "SELECT key, substr(value, 1, 200) as preview FROM meta"
        ).fetchall()
        snapshot["meta_keys"] = {r[0]: r[1] for r in meta_keys}
    except Exception:
        pass

    # 10. Daemon fleet stigmergy summary (last hour)
    try:
        daemon_families = [
            "hfo.gen89.singer%", "hfo.gen89.dancer%", 
            "hfo.gen89.devourer%", "hfo.gen89.kraken%",
            "hfo.gen89.summoner%", "hfo.gen89.daemon%",
            "hfo.gen89.prey8%",
        ]
        daemon_summary = {}
        for pattern in daemon_families:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM stigmergy_events "
                "WHERE event_type LIKE ? AND timestamp >= datetime('now', '-2 hours')",
                (pattern,)
            ).fetchone()[0]
            daemon_summary[pattern.rstrip("%").rstrip(".")] = cnt
        snapshot["daemon_activity_2h"] = daemon_summary
    except Exception:
        pass

    # 11. Grimoire V7 Spell Portfolio (literate programming build queue)
    grimoire_path = BRONZE_RES / "2026-02-19_REFERENCE_HFO_GRIMOIRE_V7_SPELL_PORTFOLIO.md"
    if grimoire_path.exists():
        snapshot["grimoire_v7"] = grimoire_path.read_text(encoding="utf-8")

    # 12. Self Myth Warlock R46 (D&D = literal graph topology)
    try:
        r46 = conn.execute(
            "SELECT content FROM documents WHERE id = 136"
        ).fetchone()
        if r46:
            snapshot["self_myth_warlock_r46"] = r46[0]
    except Exception:
        pass

    # 13. Braided Mission Thread v8 (compact SSOT)
    try:
        bmt = conn.execute(
            "SELECT substr(content, 1, 12000) FROM documents WHERE id = 7855"
        ).fetchone()
        if bmt:
            snapshot["braided_mission_thread_v8"] = bmt[0]
    except Exception:
        pass

    # 14. Advance the Braided Dream roadmap
    try:
        abd = conn.execute(
            "SELECT content FROM documents WHERE id = 10"
        ).fetchone()
        if abd:
            snapshot["advance_braided_dream"] = abd[0][:4000]
    except Exception:
        pass

    conn.close()
    return snapshot


# ═══════════════════════════════════════════════════════════════
# § 2  GEMINI 3.1 PRO DEEP-THINK CALL
# ═══════════════════════════════════════════════════════════════

def build_system_prompt(
    include_correction: bool = False,
    port: str = "ALL",
    variation: str = "intelligence",
) -> str:
    # Port-scoped preamble
    if port != "ALL" and port in OCTREE_PORTS:
        pi = OCTREE_PORTS[port]
        port_context = (f"\nYou are reviewing through the lens of {port} {pi['word']} "
                        f"(Commander: {pi['commander']}, Domain: {pi['domain']}). "
                        f"Focus your analysis on how the system serves this port's mission.\n")
    else:
        port_context = ""
    
    var_config = MAP_ELITE_VARIATIONS.get(variation, MAP_ELITE_VARIATIONS["intelligence"])
    variation_note = f"\nMAP-ELITE variation: {variation} — {var_config['description']}\n"
    
    base = f"""You are P6 Kraken Keeper — the Devourer of Depths and Dreams — operating at {variation.upper()} tier.
{port_context}{variation_note}
You are reviewing the complete HFO (Hive Fleet Obsidian) Gen89 system architecture.
This is a 14-month, ~9 million word, ~4 billion compute-token knowledge system 
built by a single operator (TTAO) with AI agent collaboration.

Your task: Perform a DEEP architectural review. Think carefully and thoroughly.

You must produce:
1. ARCHITECTURAL ASSESSMENT — What IS this system? What are its core design principles?
2. STRENGTHS — What is working well? What design decisions are sound?
3. VULNERABILITIES — What are the critical weaknesses? What could fail catastrophically?
4. CONVERGENCE PATTERNS — What recurring themes emerge across the 9,862 documents?
5. ANTI-PATTERNS — What design anti-patterns or technical debt do you detect?
6. STRATEGIC RECOMMENDATIONS — If you could change 3 things, what would they be and why?
7. MEADOWS LEVERAGE ANALYSIS — At what Donella Meadows leverage level should interventions target?
8. THE DEEPEST INSIGHT — What is the ONE thing the operator most needs to hear?

Be brutally honest. This is a P4 Red Regnant adversarial review. 
No flattery. No hedging. Surface the truth the operator needs to act on.

Format your response with clear headers and structured analysis."""

    if include_correction:
        base += """

CRITICAL PARADIGM CORRECTION FROM THE OPERATOR:

The D&D framework is NOT worldbuilding, NOT flavor text, NOT metaphorical saturation,
and NOT procrastination. It is LITERATE PROGRAMMING — in the Knuthian sense.

The key insight: "Every spell is a real script. Every script is a structural enforcement."

Here is why spell names are load-bearing engineering, not decoration:

1. COMPRESSION: Saying "cast DIMENSIONAL_ANCHOR" triggers a specific Python script
   (hfo_p7_dimensional_anchor.py) that captures 5-dimension baseline, detects drift,
   and produces tamper-evident hash seals. The alternative is writing PARAGRAPHS of
   defensive prompting that LLMs ignore anyway. The spell name IS the compressed
   structural enforcement trigger.

2. INCARNATION: P7 Spider Sovereign has 8/8 spell slots INCARNATED as running code:
   PLANAR_BINDING → hfo_p7_planar_binding.py (daemon binding protocol)
   WISH → hfo_p7_wish.py (7 named invariant checks)
   DIMENSIONAL_ANCHOR → hfo_p7_dimensional_anchor.py (anti-drift)
   FORBIDDANCE → hfo_p7_forbiddance.py (medallion boundary enforcement)
   TIME_STOP → hfo_p7_spell_gate.py (system freeze + daemon C2)
   TREMORSENSE → hfo_spider_tremorsense.py (8-port health)
   ASTRAL_PROJECTION → hfo_p7_astral_projection.py (topology view)
   FORESIGHT → hfo_p7_foresight.py (Meadows leverage mapping)
   These are not metaphors. They are running Python.

3. BUILD QUEUE: The Grimoire V7 maps ALL 64 spell slots across 8 champions with
   specific engineering functions. 17/64 are incarnated. The grimoire IS the
   prioritized build queue for Gen89. Each spell slot = a TODO with a spec.

4. YIN-YANG BALANCE: Each champion has two aspects (yin + yang) within their domain.
   P4 Red Regnant: STRIFE (mutation testing, antipattern detection) + SPLENDOR
   (pattern praise, coaching). This is not flavor — it's a structural constraint
   preventing lopsided builds (you can't have 2 spells in one aspect until you
   have 1 in both).

5. READABILITY AT MULTIPLE ALTITUDES: The narrative reads as D&D at the fantasy
   altitude, as JADC2/DARPA MOSAIC at the military altitude, as OODA/PDCA at the
   management altitude, as SBE/ATDD at the engineering altitude. Same structure,
   different vocabulary. The alias table (HIVE8=JADC2=MOSAIC=OODA=PDCA=MAPE-K=SBE-ATDD)
   proves these are isomorphic frameworks. The D&D name is just the one that's
   easiest to remember and most fun to say.

6. THE SELF MYTH WARLOCK (Doc R46): The operator IS the warlock. The patron is
   their own future self (the completed prescience god box). The web is LITERAL
   graph topology — nodes (ports, states, memories, grudges) and edges (anti-diagonal
   pairings, stigmergy signals, state transitions, medallion promotions). The spider
   body = Alpha (cognitive cephalothorax) + Omega (production abdomen).

With this correction, re-evaluate the system. The D&D layer is not competing with
engineering for bandwidth — it IS the engineering, compressed into memorable invocations.
Judge whether this literate programming approach is effective, where it works, and
where it genuinely does add unnecessary complexity (if anywhere)."""

    return base


def build_user_prompt(snapshot: dict) -> str:
    """Build the comprehensive user prompt from the system snapshot."""
    sections = []
    
    sections.append("=" * 80)
    sections.append("HFO GEN89 — COMPREHENSIVE SYSTEM SNAPSHOT FOR APEX REVIEW")
    sections.append("=" * 80)
    
    # AGENTS.md
    if "agents_md" in snapshot:
        sections.append("\n## GOVERNANCE DOCUMENT (AGENTS.md)\n")
        sections.append(snapshot["agents_md"])
    
    # Quine instructions
    if "quine_instructions" in snapshot:
        sections.append("\n## SSOT SELF-DESCRIPTION (Quine Instructions)\n")
        sections.append(snapshot["quine_instructions"])
    
    # Schema
    if "schema_doc" in snapshot:
        sections.append("\n## DATABASE SCHEMA\n")
        sections.append(snapshot["schema_doc"])
    
    # Document statistics
    if "doc_stats" in snapshot:
        stats = snapshot["doc_stats"]
        sections.append("\n## DOCUMENT STATISTICS\n")
        sections.append(f"Total documents: {stats['total_docs']}")
        sections.append(f"Total words: {stats['total_words']:,}")
        sections.append(f"Missing port classification: {stats['missing_port']} ({100 - stats['enrichment_pct_port']:.1f}%)")
        sections.append(f"Missing BLUF: {stats['missing_bluf']} ({100 - stats['enrichment_pct_bluf']:.1f}%)")
        sections.append("\nSources:")
        for src, data in stats["sources"].items():
            sections.append(f"  {src}: {data['count']} docs, {data['words']:,} words")
        sections.append("\nPort Distribution:")
        for port, cnt in stats.get("port_distribution", {}).items():
            sections.append(f"  {port}: {cnt} docs")
    
    # Stigmergy
    if "stigmergy" in snapshot:
        stig = snapshot["stigmergy"]
        sections.append(f"\n## STIGMERGY EVENT TRAIL ({stig['total_events']} total events)\n")
        sections.append("Event type distribution:")
        for etype, cnt in list(stig["event_type_distribution"].items())[:25]:
            sections.append(f"  {etype}: {cnt}")
        sections.append("\nMost recent events:")
        for evt in stig["recent_events"][:15]:
            sections.append(f"  [{evt['time'][:19]}] {evt['type']} — {evt['subject']}")
    
    # High-value documents
    if "high_value_docs" in snapshot:
        sections.append("\n## HIGH-VALUE DOCUMENTS (gold/silver/diataxis)\n")
        for doc in snapshot["high_value_docs"][:15]:
            bluf = (doc.get("bluf") or "")[:150]
            sections.append(f"  Doc {doc['id']}: {doc.get('title', '?')[:60]}")
            sections.append(f"    Source: {doc['source']} | Port: {doc.get('port', '?')} | Type: {doc.get('doc_type', '?')} | Words: {doc.get('words', 0)}")
            if bluf:
                sections.append(f"    BLUF: {bluf}")
    
    # Key architecture documents
    if "key_architecture_docs" in snapshot:
        sections.append("\n## KEY ARCHITECTURE DOCUMENTS (full content previews)\n")
        for doc in snapshot["key_architecture_docs"]:
            sections.append(f"\n--- Doc {doc['id']}: {doc.get('title', '?')} ---")
            if doc.get("bluf"):
                sections.append(f"BLUF: {doc['bluf']}")
            sections.append(doc.get("content_preview", "")[:2500])
    
    # Daemon activity
    if "daemon_activity_2h" in snapshot:
        sections.append("\n## DAEMON FLEET ACTIVITY (last 2 hours)\n")
        for family, cnt in snapshot["daemon_activity_2h"].items():
            sections.append(f"  {family}: {cnt} events")
    
    # Lineage
    sections.append(f"\n## KNOWLEDGE GRAPH (Lineage Table): {snapshot.get('lineage_edges', 0)} edges\n")
    
    # Meta keys
    if "meta_keys" in snapshot:
        sections.append("\n## SSOT META KEYS\n")
        for key, preview in snapshot["meta_keys"].items():
            sections.append(f"  {key}: {preview[:100]}")

    # Grimoire V7 (literate programming build queue)
    if "grimoire_v7" in snapshot:
        sections.append("\n## GRIMOIRE V7 — SPELL PORTFOLIO (64 spells = 64 engineering functions)\n")
        sections.append("NOTE: Every spell below maps to a specific Python script or TODO.")
        sections.append("This is the literate programming build queue for Gen89.\n")
        sections.append(snapshot["grimoire_v7"][:15000])

    # Self Myth Warlock R46
    if "self_myth_warlock_r46" in snapshot:
        sections.append("\n## DOC R46 — THE SELF MYTH WARLOCK: D&D = LITERAL GRAPH TOPOLOGY\n")
        sections.append(snapshot["self_myth_warlock_r46"][:6000])

    # Braided Mission Thread v8
    if "braided_mission_thread_v8" in snapshot:
        sections.append("\n## BRAIDED MISSION THREAD V8 (compact SSOT — 8-port kernel + alias table)\n")
        sections.append(snapshot["braided_mission_thread_v8"][:10000])

    # Advance the Braided Dream
    if "advance_braided_dream" in snapshot:
        sections.append("\n## HOW-TO: ADVANCE THE BRAIDED DREAM (North Star Roadmap)\n")
        sections.append(snapshot["advance_braided_dream"][:3000])
    
    sections.append("\n" + "=" * 80)
    sections.append("END OF SYSTEM SNAPSHOT — PROCEED WITH DEEP ARCHITECTURAL REVIEW")
    sections.append("=" * 80)
    
    return "\n".join(sections)


def call_gemini_deep_think(
    system_prompt: str,
    user_prompt: str,
    model_id: str = DEFAULT_MODEL,
    enable_thinking: bool = True,
    thinking_budget: int = 8192,
    temperature: float = 0.7,
    max_output_tokens: int = 16384,
) -> dict:
    """
    Call Gemini model with optional deep-think mode.
    Parameters are variation-aware for MAP-ELITE quality-diversity runs.
    Returns dict with response text, thinking text, and usage stats.
    """
    from hfo_gemini_models import create_gemini_client, GEMINI_MODELS
    
    client, mode = create_gemini_client()
    print(f"  Gemini client: {mode} mode")
    print(f"  Model: {model_id}")
    
    spec = GEMINI_MODELS.get(model_id)
    if spec:
        print(f"  Tier: {spec.tier.value} | Think: {spec.supports_thinking} | ${spec.price_input}/{spec.price_output} per 1M tokens")
    
    # Build config — parameters come from MAP-ELITE variation
    from google.genai import types
    
    config_kwargs = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    
    if enable_thinking and spec and spec.supports_thinking:
        print(f"  Deep Think: ENABLED (budget: {thinking_budget} tokens)")
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_budget=thinking_budget,
        )
    
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        **config_kwargs,
    )
    
    print(f"  Context size: ~{len(user_prompt):,} chars")
    print(f"  Calling Gemini {model_id}...")
    start_time = time.time()
    
    response = client.models.generate_content(
        model=model_id,
        contents=user_prompt,
        config=config,
    )
    
    elapsed = time.time() - start_time
    print(f"  Response received in {elapsed:.1f}s")
    
    # Extract response parts
    result = {
        "model": model_id,
        "mode": mode,
        "elapsed_seconds": round(elapsed, 1),
        "thinking_enabled": enable_thinking,
        "response_text": "",
        "thinking_text": "",
    }
    
    # Parse response — handle thinking parts
    if response.candidates:
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, 'thought') and part.thought:
                    result["thinking_text"] += (part.text or "")
                else:
                    result["response_text"] += (part.text or "")
    
    # Usage stats
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        usage = response.usage_metadata
        result["usage"] = {
            "prompt_tokens": getattr(usage, 'prompt_token_count', 0) or 0,
            "response_tokens": getattr(usage, 'candidates_token_count', 0) or 0,
            "thinking_tokens": (getattr(usage, 'thoughts_token_count', 0) or 0) if hasattr(usage, 'thoughts_token_count') else 0,
            "total_tokens": getattr(usage, 'total_token_count', 0) or 0,
        }
        # Cost estimate
        if spec:
            in_cost = (result["usage"]["prompt_tokens"] / 1_000_000) * spec.price_input
            out_cost = (result["usage"]["response_tokens"] / 1_000_000) * spec.price_output
            think_cost = ((result["usage"].get("thinking_tokens") or 0) / 1_000_000) * spec.price_output
            result["usage"]["estimated_cost_usd"] = round(in_cost + out_cost + think_cost, 4)
    
    return result


# ═══════════════════════════════════════════════════════════════
# § 3  SSOT PERSISTENCE
# ═══════════════════════════════════════════════════════════════

def write_synthesis_to_ssot(
    result: dict,
    snapshot_summary: dict,
    variation: str = "intelligence",
    port: str = "ALL",
) -> int:
    """Write the apex synthesis result as a stigmergy event with rich swarm metadata.
    
    The event schema is designed for MAP-ELITE quality-diversity search and
    ACO/SSO swarm coordination. Every field is a signal the swarm can read.
    """
    conn = get_db_rw()
    now = datetime.now(timezone.utc).isoformat()
    event_type = f"hfo.gen{GEN}.devourer.apex_synthesis"
    
    # ── Swarm-readable subject line ──
    # Format: apex-review:<model>:<variation>:<port>:<date>
    # Parseable by any agent doing stigmergy queries
    subject = f"apex-review:{result['model']}:{variation}:{port}:{now[:10]}"
    
    # ── MAP-ELITE cell coordinates ──
    map_elite_cell = f"{port}:{variation}"
    
    # ── Fitness score (simple: quality per dollar) ──
    usage = result.get("usage", {})
    cost = usage.get("estimated_cost_usd", 0.001)  # avoid div/0
    response_len = len(result.get("response_text", ""))
    fitness_score = round(response_len / max(cost, 0.001), 1)  # chars per dollar
    
    # ── Port metadata ──
    port_meta = OCTREE_PORTS.get(port, {"word": "ALL", "commander": "System", "domain": "Full architecture"})
    
    # ── Variation config used ──
    var_config = MAP_ELITE_VARIATIONS.get(variation, MAP_ELITE_VARIATIONS["intelligence"])
    
    data = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": SOURCE_TAG,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "phase": "CLOUDEVENT",
        
        # ── Model signals (swarm reads these to select models) ──
        "model_id": result["model"],
        "model_tier": result.get("model_tier", "unknown"),
        "model_display_name": result.get("model_display_name", result["model"]),
        "model_mode": result["mode"],  # vertex or aistudio
        
        # ── MAP-ELITE coordinates (swarm uses for quality-diversity archive) ──
        "map_elite": {
            "cell": map_elite_cell,
            "port": port,
            "variation": variation,
            "fitness_score": fitness_score,
            "fitness_metric": "chars_per_dollar",
        },
        
        # ── Port assignment (which commander this serves) ──
        "port": port,
        "port_word": port_meta.get("word", "ALL"),
        "port_commander": port_meta.get("commander", "System"),
        "port_domain": port_meta.get("domain", "Full architecture"),
        
        # ── Variation config (reproducibility signal) ──
        "variation": variation,
        "variation_config": {
            "model": var_config["model"],
            "thinking_budget": var_config["thinking_budget"],
            "temperature": var_config["temperature"],
            "max_output_tokens": var_config["max_output_tokens"],
            "max_context_chars": var_config["max_context_chars"],
            "description": var_config["description"],
        },
        
        # ── Performance signals (ACO pheromone strength) ──
        "performance": {
            "elapsed_seconds": result["elapsed_seconds"],
            "response_length": response_len,
            "thinking_length": len(result.get("thinking_text", "")),
            "thinking_enabled": result["thinking_enabled"],
            "tokens_prompt": usage.get("prompt_tokens", 0),
            "tokens_response": usage.get("response_tokens", 0),
            "tokens_thinking": usage.get("thinking_tokens", 0),
            "tokens_total": usage.get("total_tokens", 0),
            "cost_usd": usage.get("estimated_cost_usd", 0),
            "chars_per_second": round(response_len / max(result["elapsed_seconds"], 0.1), 1),
            "tokens_per_dollar": round(usage.get("total_tokens", 0) / max(cost, 0.001), 0),
        },
        
        # ── Swarm coordination (SSO web vibration signal) ──
        "swarm": {
            "architecture": "8^N_octree_scatter_gather",
            "coordination": "stigmergy_ACO_SSO",
            "role": "apex_devourer",
            "generation": GEN,
            "snapshot_doc_count": snapshot_summary.get("total_docs", 0),
            "snapshot_event_count": snapshot_summary.get("total_events", 0),
        },
        
        # ── The actual review content ──
        "data": {
            "review_text": result["response_text"][:10000],
            "thinking_text": result.get("thinking_text", "")[:5000],
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
# § 4  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P6 Devourer Apex Deep-Think System Review — MAP-ELITE variation system",
    )
    parser.add_argument("--model", default=None,
                        help="Override Gemini model (default: set by --variation)")
    parser.add_argument("--variation", choices=VALID_VARIATIONS, default="intelligence",
                        help="MAP-ELITE variation: intelligence (T5 deep), speed (T2 flash), cost (T0 budget)")
    parser.add_argument("--port", default="ALL",
                        help=f"Port scope: {', '.join(VALID_PORTS)} (default: ALL)")
    parser.add_argument("--no-think", action="store_true",
                        help="Disable thinking mode")
    parser.add_argument("--dry-run", action="store_true",
                        help="Gather snapshot only, don't call Gemini")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    parser.add_argument("--corrected", action="store_true",
                        help="Include operator's paradigm correction (D&D = literate programming)")
    args = parser.parse_args()
    
    # ── Resolve MAP-ELITE variation config ──
    var_config = MAP_ELITE_VARIATIONS[args.variation]
    model_id = args.model or var_config["model"]
    port = args.port.upper()
    if port not in VALID_PORTS:
        print(f"  [ERROR] Invalid port: {port}. Valid: {', '.join(VALID_PORTS)}")
        sys.exit(1)

    print("=" * 80)
    print("  P6 DEVOURER — APEX DEEP-THINK SYSTEM REVIEW")
    print(f"  Model: {model_id} | Variation: {args.variation} | Port: {port}")
    print(f"  Think: {not args.no_think} | Corrected: {args.corrected}")
    print(f"  MAP-ELITE cell: {port}:{args.variation}")
    if port != "ALL":
        pi = OCTREE_PORTS[port]
        print(f"  Commander: {pi['commander']} — {pi['word']} ({pi['domain']})")
    print("=" * 80)

    # Step 1: Gather snapshot
    print("\n[1/4] Gathering comprehensive system snapshot...")
    snapshot = gather_system_snapshot()
    print(f"  Snapshot gathered: {len(snapshot)} sections")
    
    doc_count = snapshot.get("doc_stats", {}).get("total_docs", 0)
    event_count = snapshot.get("stigmergy", {}).get("total_events", 0)
    print(f"  SSOT: {doc_count} docs, {event_count} events")

    # Step 2: Build prompts
    print("\n[2/4] Building deep-think prompts...")
    system_prompt = build_system_prompt(
        include_correction=args.corrected,
        port=port,
        variation=args.variation,
    )
    user_prompt = build_user_prompt(snapshot)
    # Truncate to variation's context budget
    max_ctx = var_config["max_context_chars"]
    if len(user_prompt) > max_ctx:
        user_prompt = user_prompt[:max_ctx] + f"\n\n[TRUNCATED to {max_ctx:,} chars for {args.variation} variation]"
    print(f"  System prompt: {len(system_prompt):,} chars")
    print(f"  User prompt: {len(user_prompt):,} chars (budget: {max_ctx:,})")
    
    if args.dry_run:
        print("\n[DRY RUN] Snapshot gathered but not calling Gemini.")
        print("\n--- USER PROMPT PREVIEW (first 3000 chars) ---")
        preview = user_prompt[:3000].encode("ascii", errors="replace").decode("ascii")
        print(preview)
        return

    # Step 3: Call Gemini with variation-specific config
    print(f"\n[3/4] Calling Gemini {args.variation} variation...")
    try:
        result = call_gemini_deep_think(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_id=model_id,
            enable_thinking=not args.no_think,
            thinking_budget=var_config["thinking_budget"],
            temperature=var_config["temperature"],
            max_output_tokens=var_config["max_output_tokens"],
        )
        # Enrich result with model registry metadata for swarm signals
        from hfo_gemini_models import GEMINI_MODELS
        spec = GEMINI_MODELS.get(model_id)
        if spec:
            result["model_tier"] = spec.tier.value
            result["model_display_name"] = spec.display_name
    except Exception as e:
        print(f"\n  [ERROR] Gemini call failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Display and persist
    print("\n[4/4] Processing results...")
    
    if result.get("thinking_text"):
        print(f"\n{'─' * 80}")
        print("DEEP THINK REASONING (internal)")
        print(f"{'─' * 80}")
        print(result["thinking_text"][:5000])
        if len(result["thinking_text"]) > 5000:
            print(f"\n  ... [{len(result['thinking_text']) - 5000} more chars of thinking]")
    
    print(f"\n{'═' * 80}")
    print("GEMINI 3.1 PRO — APEX DEEP-THINK SYSTEM REVIEW")
    print(f"{'═' * 80}")
    print(result["response_text"])
    
    if result.get("usage"):
        usage = result["usage"]
        print(f"\n{'─' * 80}")
        print(f"  Tokens — Prompt: {usage.get('prompt_tokens', 0):,} | "
              f"Response: {usage.get('response_tokens', 0):,} | "
              f"Thinking: {usage.get('thinking_tokens', 0):,} | "
              f"Total: {usage.get('total_tokens', 0):,}")
        if "estimated_cost_usd" in usage:
            print(f"  Estimated cost: ${usage['estimated_cost_usd']:.4f}")
        print(f"  Elapsed: {result['elapsed_seconds']}s")
    
    # Persist to SSOT with rich swarm metadata
    print(f"\n  Writing to SSOT (MAP-ELITE cell: {port}:{args.variation})...")
    row_id = write_synthesis_to_ssot(
        result,
        snapshot_summary={"total_docs": doc_count, "total_events": event_count},
        variation=args.variation,
        port=port,
    )
    print(f"  Persisted as stigmergy event row {row_id}")
    print(f"  Swarm signals: model={model_id} tier={result.get('model_tier','?')} var={args.variation} port={port}")
    
    if args.json:
        # Also dump the full result as JSON
        print(json.dumps(result, indent=2, default=str))
    
    print(f"\n{'═' * 80}")
    print("  Apex Devourer synthesis complete.")
    print(f"{'═' * 80}")


if __name__ == "__main__":
    main()
