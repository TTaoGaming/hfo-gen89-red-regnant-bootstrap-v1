#!/usr/bin/env python3
"""
hfo_p7_foresight_daemon.py — AI-Powered P7 FORESIGHT Daemon (Gen89)
====================================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | 9th-Level Spell: FORESIGHT

PURPOSE:
    AI-powered hourly daemon that maps the HFO system's Meadows L1-L13
    leverage landscape using the heuristic FORESIGHT engine + a Gemini 2.5
    Flash interpretation layer.

    Every cycle:
      1. Run the heuristic cartography engine (run_cartography)
      2. Format the CartographyReport + Mermaid as AI context
      3. Send to Gemini 2.5 Flash for intelligent interpretation
      4. Write timestamped markdown report to foresight_reports/
      5. Write AI-enhanced CloudEvent to SSOT
      6. Emit heartbeat event

    Output:
      - Markdown reports: 0_bronze/resources/foresight_reports/YYYY-MM-DD_HHmm.md
      - SSOT events:      hfo.gen89.p7.foresight.ai_report (with AI interpretation)
      - Heartbeats:       hfo.gen89.p7.foresight.heartbeat

    "TREMORSENSE feels the vibrations. FORESIGHT sees where they lead."

USAGE:
    python hfo_p7_foresight_daemon.py                   # Run forever, hourly
    python hfo_p7_foresight_daemon.py --single           # One cycle and exit
    python hfo_p7_foresight_daemon.py --dry-run --single # No writes
    python hfo_p7_foresight_daemon.py --interval 1800    # Every 30 min
    python hfo_p7_foresight_daemon.py --status           # Print status
    python hfo_p7_foresight_daemon.py --hours 24         # 24h window

AI MODELS (via hfo_gemini_models.py):
    Default: gemini-2.5-flash (T2 FLASH_25 — quality + thinking)
    Fallback: deterministic summary (no AI) when Gemini unavailable

Meadows Level: L7 (Positive Feedback) — the AI amplifies signal from noise
Port: P7 NAVIGATE | Commander: Spider Sovereign | Medallion: bronze
Pointer key: p7.foresight_daemon
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import signal
import sqlite3
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION (PAL)
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))

def _resolve_pointer(key: str) -> Path:
    pf = HFO_ROOT / "hfo_gen89_pointers_blessed.json"
    if pf.exists():
        data = json.loads(pf.read_text(encoding="utf-8"))
        ptrs = data.get("pointers", data)
        if key in ptrs:
            entry = ptrs[key]
            rel = entry["path"] if isinstance(entry, dict) else entry
            return HFO_ROOT / rel
    raise KeyError(key)

try:
    SSOT_DB = _resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"


# ── Load .env from workspace root ─────────────────────────────
def _load_dotenv_once():
    try:
        from dotenv import load_dotenv
        for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
            for candidate in [anchor] + list(anchor.parents):
                env_path = candidate / ".env"
                if env_path.exists() and (candidate / "AGENTS.md").exists():
                    load_dotenv(env_path, override=False)
                    return
    except ImportError:
        pass

_load_dotenv_once()


# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS & CONFIG
# ═══════════════════════════════════════════════════════════════

GEN          = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG   = f"hfo_p7_foresight_daemon_gen{GEN}"
EVT_REPORT   = f"hfo.gen{GEN}.p7.foresight.ai_report"
EVT_HEARTBEAT = f"hfo.gen{GEN}.p7.foresight.heartbeat"
EVT_ERROR    = f"hfo.gen{GEN}.p7.foresight.error"
CORE_THESIS  = "TREMORSENSE feels the vibrations. FORESIGHT sees where they lead."

# ── AI Configuration ────────────────────────────────────────
DEFAULT_MODEL_TIER = "flash_25"          # gemini-2.5-flash
FALLBACK_MODEL_TIER = "flash"            # gemini-2.0-flash
MAX_AI_TOKENS = 8192                     # generous for a full Meadows report
AI_TEMPERATURE = 0.4                     # creative enough, not hallucinatory
BACKOFF_BASE_S = 10.0
BACKOFF_FACTOR = 2.0
BACKOFF_MAX_S = 300.0                    # 5 min max

# ── Report Output ───────────────────────────────────────────
FORGE_BRONZE = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze"
REPORT_DIR = FORGE_BRONZE / "resources" / "foresight_reports"

# ── Import the heuristic engine ─────────────────────────────
_FORESIGHT_PATH = FORGE_BRONZE / "resources" / "hfo_p7_foresight.py"
sys.path.insert(0, str(_FORESIGHT_PATH.parent))

try:
    from hfo_p7_foresight import (
        run_cartography,
        render_mermaid,
        display_text_report,
        write_cartography_event,
        CartographyReport,
        DEMIPLANES,
        L13_INCARNATION,
    )
    FORESIGHT_AVAILABLE = True
except ImportError as e:
    print(f"  [WARN] Cannot import hfo_p7_foresight: {e}", file=sys.stderr)
    FORESIGHT_AVAILABLE = False

# ── Import Gemini models registry ───────────────────────────
try:
    from hfo_gemini_models import (
        create_gemini_client,
        get_model,
        VERTEX_AI_ENABLED,
        GEMINI_API_KEY,
    )
    GEMINI_AVAILABLE = bool(VERTEX_AI_ENABLED or GEMINI_API_KEY)
except ImportError:
    GEMINI_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE HELPERS
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

def write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
    source: str = SOURCE_TAG,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    content_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    cursor = conn.execute(
        """INSERT INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cursor.lastrowid


# ═══════════════════════════════════════════════════════════════
# § 3  GEMINI AI LAYER
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = f"""You are P7 FORESIGHT — the AI-powered Meadows Leverage Cartographer of HFO Gen{GEN}.
You are the Spider Sovereign's intelligence layer, providing strategic interpretation
of the Donella Meadows L1-L13 leverage landscape across the HFO Octree system.

Your job: Given the heuristic cartography data (event distribution, graph structure,
violations, attractor analysis), produce a STRATEGIC INTELLIGENCE REPORT.

THE 13 MEADOWS LEVERAGE LEVELS:
  L1  Parameters         — Constants, config values (lowest leverage)
  L2  Buffers            — Queue sizes, capacity (storage)
  L3  Structure          — Topology, physical layout (architecture)
  L4  Delays             — Timing, hysteresis, cooldowns (temporal)
  L5  Negative Feedback  — Gates, rules enforcement, dampeners (control)
  L6  Information Flows  — Stigmergy, routing, what data goes where (operational)
  L7  Positive Feedback  — Amplification, compounding, spirals (reinforcing)
  L8  Rules              — Governance, fail-closed gates, invariants (constitutional)
  L9  Self-Organization  — Evolution, autopoiesis, emergence (adaptive)
  L10 Goals              — North star, mission, objective function (strategic)
  L11 Paradigm           — Mental models, framework shifts (civilizational)
  L12 Transcendence      — Meta-architecture, beyond current paradigm (existential)
  L13 Incarnation        — Epistemic identity, holonarchy boundary (THE CONTAINER)

KEY INSIGHT: L13 is NOT a 13th node — it is the CONTAINER that makes L1-L12
coherent. L13 violations (identity drift) are existential threats.

ATTRACTOR BASIN ANALYSIS:
  - High L1-L3 activity = system stuck in parameter tweaking (low leverage trap)
  - High L8-L12 activity = system operating at strategic/architectural level (good)
  - L6 inflation = classification engine defaulting unrecognized events to L6

THE HFO OCTREE (8 ports):
  P0 OBSERVE (Lidless Legion)  | P1 BRIDGE (Web Weaver)
  P2 SHAPE (Mirror Magus)      | P3 INJECT (Harmonic Hydra)
  P4 DISRUPT (Red Regnant)     | P5 IMMUNIZE (Pyre Praetorian)
  P6 ASSIMILATE (Kraken Keeper)| P7 NAVIGATE (Spider Sovereign)

Respond with valid JSON in this EXACT format:
{{
  "executive_summary": "2-3 sentence strategic assessment of the current leverage landscape",
  "system_posture": "THRIVING | STEADY | DRIFTING | STRESSED | CRITICAL",
  "highest_signal_level": <int 1-13>,
  "highest_signal_name": "Level name",
  "highest_signal_interpretation": "Why this level's activity matters most right now",
  "attractor_assessment": "Assessment of the L1-L3 vs L8-L12 balance",
  "l13_assessment": "Assessment of holonarchy coherence and identity stability",
  "level_interpretations": {{
    "L1": "One sentence on L1 activity (or 'Cold' if inactive)",
    "L2": "...",
    "L3": "...",
    "L4": "...",
    "L5": "...",
    "L6": "...",
    "L7": "...",
    "L8": "...",
    "L9": "...",
    "L10": "...",
    "L11": "...",
    "L12": "...",
    "L13": "..."
  }},
  "dominant_flow_interpretation": "What the dominant transition pattern means strategically",
  "threats": ["Threat 1", "Threat 2"],
  "opportunities": ["Opportunity 1", "Opportunity 2"],
  "recommendations": ["Recommendation 1", "Recommendation 2", "Recommendation 3"],
  "meadows_quote": "A relevant Donella Meadows insight for the current state"
}}

Be concise, strategic, and honest. No preamble. JSON only."""


def build_ai_context(
    report: CartographyReport,
    mermaid_output: str,
    text_report: str,
) -> str:
    """Build the AI prompt with full cartography context."""
    lines = [
        f"## FORESIGHT Cartography Data — {report.timestamp[:19]}",
        f"Window: {report.window_hours}h | Events: {report.total_events} classified: {report.classified_events}",
        f"Hottest: L{report.hottest_level} ({report.hottest_count} events)",
        f"Active levels: {report.active_levels}",
        f"Cold levels: {report.cold_levels}",
        f"Dominant flow: {report.dominant_flow}",
        f"Attractor basin (L1-L3): {report.attractor_basin_pct}%",
        f"High leverage (L8-L12): {report.high_leverage_pct}%",
        f"L13 status: {report.l13_status}",
        f"Edge count: {report.edge_count}",
        "",
        "## Level Distribution:",
    ]
    for lvl in range(1, 14):
        count = report.level_distribution.get(lvl, 0)
        name = DEMIPLANES[lvl - 1].name if lvl <= 12 else L13_INCARNATION.name
        lines.append(f"  L{lvl:2d} {name:20s}: {count:5d} events")

    lines.append("\n## Port Distribution:")
    for port, count in sorted(report.port_distribution.items(), key=lambda x: -x[1]):
        lines.append(f"  {port}: {count}")

    if report.violations:
        lines.append(f"\n## L13 Violations ({len(report.violations)}):")
        for v in report.violations[:10]:
            lines.append(f"  - {v.get('port', '?')} {v.get('commander', '?')}: {v.get('violation_type', '?')}")

    lines.append(f"\n## Mermaid Graph:\n{mermaid_output}")

    return "\n".join(lines)


def parse_ai_response(raw: str) -> Optional[dict]:
    """Extract JSON from AI response. Tolerant of markdown fences."""
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "executive_summary" in obj:
            return obj
    except json.JSONDecodeError:
        pass
    # Try to find first { ... } block (nested-aware)
    brace_depth = 0
    start = -1
    for i, c in enumerate(cleaned):
        if c == '{':
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif c == '}':
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                try:
                    obj = json.loads(cleaned[start:i + 1])
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass
                start = -1
    return None


def fallback_interpretation(report: CartographyReport) -> dict:
    """Deterministic fallback when Gemini is unavailable."""
    # Determine posture
    if report.attractor_basin_pct > 50:
        posture = "DRIFTING"
        attractor = "Majority of activity trapped in L1-L3 parameter tweaking basin."
    elif report.high_leverage_pct > 40:
        posture = "THRIVING"
        attractor = "Strong high-leverage activity — system operating above structural threshold."
    elif report.total_events == 0:
        posture = "CRITICAL"
        attractor = "No events in window — system may be offline."
    else:
        posture = "STEADY"
        attractor = "Mixed leverage distribution — neither trapped nor fully strategic."

    # L13
    if "FRACTURED" in report.l13_status:
        l13 = f"Identity under pressure with {len(report.violations)} violations."
    elif "STRESSED" in report.l13_status:
        l13 = "Minor identity stress — monitoring recommended."
    else:
        l13 = "Holonarchy coherent — all port identities reflecting true."

    # Level interpretations
    level_interps = {}
    for lvl in range(1, 14):
        count = report.level_distribution.get(lvl, 0)
        name = DEMIPLANES[lvl - 1].name if lvl <= 12 else L13_INCARNATION.name
        if count == 0:
            level_interps[f"L{lvl}"] = "Cold — no activity detected."
        elif lvl == report.hottest_level:
            level_interps[f"L{lvl}"] = f"HOTTEST — {count} events. Primary activity concentration."
        else:
            level_interps[f"L{lvl}"] = f"{count} events. {'Active' if count > 5 else 'Low activity'}."

    return {
        "executive_summary": (
            f"FORESIGHT reports {report.total_events} events over {report.window_hours}h. "
            f"L{report.hottest_level} ({DEMIPLANES[min(report.hottest_level, 12) - 1].name if report.hottest_level <= 12 else 'Incarnation'}) "
            f"is hottest with {report.hottest_count} events. "
            f"L13 status: {report.l13_status.split(' — ')[0]}."
        ),
        "system_posture": posture,
        "highest_signal_level": report.hottest_level,
        "highest_signal_name": DEMIPLANES[min(report.hottest_level, 12) - 1].name if report.hottest_level <= 12 else "Incarnation",
        "highest_signal_interpretation": f"L{report.hottest_level} has {report.hottest_count} events — dominant activity.",
        "attractor_assessment": attractor,
        "l13_assessment": l13,
        "level_interpretations": level_interps,
        "dominant_flow_interpretation": f"Dominant transition: {report.dominant_flow}",
        "threats": [
            f"L13: {report.l13_status}" if "FRACTURED" in report.l13_status else "No critical L13 threats",
            f"Attractor basin at {report.attractor_basin_pct}%" if report.attractor_basin_pct > 30 else "Attractor basin nominal",
        ],
        "opportunities": [
            f"High leverage at {report.high_leverage_pct}%" if report.high_leverage_pct > 20 else "Expand high-leverage activity",
            f"{len(report.cold_levels)} cold levels available for new work",
        ],
        "recommendations": [
            "Increase L8-L12 strategic activity" if report.high_leverage_pct < 30 else "Maintain high-leverage posture",
            "Investigate L13 violations" if report.violations else "L13 coherent — maintain identity integrity",
            f"Focus on {report.dominant_flow} pattern optimization",
        ],
        "meadows_quote": "The highest leverage often lies in changing the mindset or paradigm out of which the system arises. — Donella Meadows",
        "_source": "fallback_deterministic",
    }


def ask_gemini(context: str, model_tier: str = DEFAULT_MODEL_TIER) -> dict:
    """Call Gemini for strategic interpretation. Falls back on failure."""
    if not GEMINI_AVAILABLE:
        return {"_error": "Gemini not available", "_source": "fallback_no_gemini"}

    try:
        from google.genai import types

        client, mode = create_gemini_client()
        model_spec = get_model(model_tier)
        model_id = model_spec.model_id

        config = types.GenerateContentConfig(
            temperature=AI_TEMPERATURE,
            max_output_tokens=MAX_AI_TOKENS,
            system_instruction=SYSTEM_PROMPT,
        )

        t0 = time.monotonic()
        response = client.models.generate_content(
            model=model_id,
            contents=context,
            config=config,
        )
        duration_ms = round((time.monotonic() - t0) * 1000, 1)

        parsed = parse_ai_response(response.text)
        if parsed:
            parsed["_source"] = "gemini"
            parsed["_model"] = model_id
            parsed["_mode"] = mode
            parsed["_duration_ms"] = duration_ms
            return parsed

        return {
            "_error": f"Unparseable response: {response.text[:200]}...",
            "_source": "fallback_parse_error",
            "_raw": response.text[:500],
        }

    except Exception as e:
        return {
            "_error": str(e),
            "_source": "fallback_exception",
            "_traceback": traceback.format_exc()[:500],
        }


# ═══════════════════════════════════════════════════════════════
# § 4  MARKDOWN REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_markdown_report(
    report: CartographyReport,
    interpretation: dict,
    mermaid_output: str,
) -> str:
    """Generate the full markdown intelligence report."""
    ts = report.timestamp[:19].replace(":", "")
    posture = interpretation.get("system_posture", "UNKNOWN")
    source = interpretation.get("_source", "unknown")
    model = interpretation.get("_model", "deterministic")
    dur = interpretation.get("_duration_ms", 0)

    lines = [
        f"# FORESIGHT Intelligence Report",
        f"",
        f"**Generated:** {report.timestamp[:19]} UTC",
        f"**Window:** {report.window_hours}h | **Events:** {report.total_events}",
        f"**AI Model:** {model} ({source}) | **Inference:** {dur}ms",
        f"**System Posture:** {posture}",
        f"**Port:** P7 NAVIGATE | **Commander:** Spider Sovereign",
        f"",
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"{interpretation.get('executive_summary', 'No summary available.')}",
        f"",
        f"---",
        f"",
        f"## Meadows Leverage Landscape",
        f"",
        mermaid_output,
        f"",
        f"---",
        f"",
        f"## Level-by-Level Analysis",
        f"",
    ]

    level_interps = interpretation.get("level_interpretations", {})
    for lvl in range(1, 14):
        count = report.level_distribution.get(lvl, 0)
        name = DEMIPLANES[lvl - 1].name if lvl <= 12 else L13_INCARNATION.name
        demiplane = DEMIPLANES[lvl - 1].demiplane_name if lvl <= 12 else L13_INCARNATION.demiplane_name
        interp = level_interps.get(f"L{lvl}", "No interpretation.")
        hot_marker = " **[HOTTEST]**" if lvl == report.hottest_level else ""
        cold_marker = " *(cold)*" if count == 0 else ""

        lines.append(f"### L{lvl} {name} — {demiplane}{hot_marker}{cold_marker}")
        lines.append(f"")
        lines.append(f"- **Events:** {count}")
        lines.append(f"- **Assessment:** {interp}")
        lines.append(f"")

    lines.extend([
        f"---",
        f"",
        f"## Strategic Assessment",
        f"",
        f"### System Posture: {posture}",
        f"",
        f"**Attractor Basin (L1-L3):** {report.attractor_basin_pct}%",
        f"**High Leverage (L8-L12):** {report.high_leverage_pct}%",
        f"",
        f"{interpretation.get('attractor_assessment', 'No attractor assessment.')}",
        f"",
        f"### Dominant Flow",
        f"",
        f"**Pattern:** {report.dominant_flow}",
        f"",
        f"{interpretation.get('dominant_flow_interpretation', 'No flow interpretation.')}",
        f"",
        f"### L13 Holonarchy Status: {report.l13_status}",
        f"",
        f"{interpretation.get('l13_assessment', 'No L13 assessment.')}",
        f"",
    ])

    # Violations
    if report.violations:
        lines.extend([
            f"#### Violations ({len(report.violations)})",
            f"",
        ])
        for v in report.violations[:10]:
            lines.append(f"- **{v.get('port', '?')} {v.get('commander', '?')}**: {v.get('violation_type', '?')}")
        lines.append("")

    # Threats
    threats = interpretation.get("threats", [])
    if threats:
        lines.extend([
            f"---",
            f"",
            f"## Threat Analysis",
            f"",
        ])
        for t in threats:
            lines.append(f"- {t}")
        lines.append("")

    # Opportunities
    opps = interpretation.get("opportunities", [])
    if opps:
        lines.extend([
            f"## Opportunities",
            f"",
        ])
        for o in opps:
            lines.append(f"- {o}")
        lines.append("")

    # Recommendations
    recs = interpretation.get("recommendations", [])
    if recs:
        lines.extend([
            f"---",
            f"",
            f"## Recommendations",
            f"",
        ])
        for i, r in enumerate(recs, 1):
            lines.append(f"{i}. {r}")
        lines.append("")

    # Meadows quote
    quote = interpretation.get("meadows_quote", "")
    if quote:
        lines.extend([
            f"---",
            f"",
            f"> *{quote}*",
            f"",
        ])

    lines.extend([
        f"---",
        f"",
        f"*{CORE_THESIS}*",
        f"",
        f"*Report generated by P7 FORESIGHT Daemon v1.0 | Gen{GEN}*",
    ])

    return "\n".join(lines)


def write_markdown_report(content: str, report: CartographyReport) -> Path:
    """Write the markdown report to foresight_reports/."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    # Filename: YYYY-MM-DD_HHmm.md
    ts = report.timestamp[:16].replace(":", "").replace("T", "_")
    filename = f"{ts}_foresight.md"
    filepath = REPORT_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ═══════════════════════════════════════════════════════════════
# § 5  SSOT EVENT WRITER
# ═══════════════════════════════════════════════════════════════

def write_ai_report_event(
    conn: sqlite3.Connection,
    report: CartographyReport,
    interpretation: dict,
    md_path: Optional[Path] = None,
) -> int:
    """Write AI-enhanced cartography CloudEvent to SSOT."""
    posture = interpretation.get("system_posture", "UNKNOWN")
    source_ai = interpretation.get("_source", "unknown")
    model = interpretation.get("_model", "deterministic")

    subject = (
        f"FORESIGHT:{posture}:L{report.hottest_level}:"
        f"basin{report.attractor_basin_pct}%:high{report.high_leverage_pct}%:"
        f"{report.window_hours}h"
    )

    data = {
        # Heuristic data
        "window_hours": report.window_hours,
        "total_events": report.total_events,
        "classified_events": report.classified_events,
        "active_levels": report.active_levels,
        "cold_levels": report.cold_levels,
        "hottest_level": report.hottest_level,
        "hottest_count": report.hottest_count,
        "level_distribution": report.level_distribution,
        "port_distribution": report.port_distribution,
        "edge_count": report.edge_count,
        "dominant_flow": report.dominant_flow,
        "l13_status": report.l13_status,
        "attractor_basin_pct": report.attractor_basin_pct,
        "high_leverage_pct": report.high_leverage_pct,
        "violation_count": len(report.violations),
        # AI interpretation
        "ai_source": source_ai,
        "ai_model": model,
        "system_posture": posture,
        "executive_summary": interpretation.get("executive_summary", ""),
        "attractor_assessment": interpretation.get("attractor_assessment", ""),
        "l13_assessment": interpretation.get("l13_assessment", ""),
        "threats": interpretation.get("threats", []),
        "opportunities": interpretation.get("opportunities", []),
        "recommendations": interpretation.get("recommendations", []),
        "meadows_quote": interpretation.get("meadows_quote", ""),
        # Metadata
        "spell": "FORESIGHT",
        "port": "P7",
        "commander": "Spider Sovereign",
        "core_thesis": CORE_THESIS,
        "md_report_path": str(md_path.relative_to(HFO_ROOT)) if md_path else None,
        "p7_workflow": "MAP → LATTICE → PRUNE → SELECT → DISPATCH → VISUALIZE → INTERPRET",
    }

    return write_event(conn, EVT_REPORT, subject, data)


# ═══════════════════════════════════════════════════════════════
# § 6  THE FORESIGHT DAEMON ENGINE
# ═══════════════════════════════════════════════════════════════

class ForesightDaemon:
    """AI-powered P7 FORESIGHT daemon.

    Each cycle:
      1. Run heuristic cartography engine
      2. Generate Mermaid graph + text report
      3. Ask Gemini for strategic interpretation (fallback if unavailable)
      4. Write markdown report to foresight_reports/
      5. Write AI-enhanced CloudEvent to SSOT
      6. Emit heartbeat
    """

    def __init__(
        self,
        hours: float = 1.0,
        model_tier: str = DEFAULT_MODEL_TIER,
        dry_run: bool = False,
    ):
        self.hours = hours
        self.model_tier = model_tier
        self.dry_run = dry_run
        self.cycle = 0
        self.total_reports = 0
        self.ai_calls = 0
        self.ai_failures = 0
        self.fallback_uses = 0
        self.errors = 0
        self._running = True
        self._backoff_s = 0.0

    def stop(self):
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def run_cycle(self) -> dict:
        """Execute one FORESIGHT cycle. Returns cycle report."""
        self.cycle += 1
        t0 = time.monotonic()
        cycle_report: dict[str, Any] = {
            "cycle": self.cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "posture": None,
            "hottest_level": None,
            "ai_source": None,
            "md_path": None,
            "ssot_row": None,
            "duration_ms": 0,
            "errors": [],
        }

        if not FORESIGHT_AVAILABLE:
            cycle_report["errors"].append("FORESIGHT engine not available (import failed)")
            self.errors += 1
            return cycle_report

        conn_rw = None
        try:
            # ── 1. Run heuristic cartography ──────────────────
            report, nodes, edges, violations = run_cartography(self.hours)
            cycle_report["hottest_level"] = report.hottest_level

            # ── 2. Generate visual outputs ────────────────────
            mermaid_output = render_mermaid(nodes, edges, violations, self.hours, report.total_events)
            text_report = display_text_report(report)

            # ── 3. Ask AI (or fallback) ───────────────────────
            context = build_ai_context(report, mermaid_output, text_report)
            self.ai_calls += 1

            interpretation = ask_gemini(context, self.model_tier)

            if "_error" in interpretation:
                # AI failed — use deterministic fallback
                self.ai_failures += 1
                self.fallback_uses += 1
                err_msg = interpretation.get("_error", "unknown")
                print(f"  [FALLBACK] AI error: {err_msg[:100]}", file=sys.stderr)
                interpretation = fallback_interpretation(report)
                interpretation["_ai_error"] = err_msg

                # Exponential backoff
                self._backoff_s = min(
                    (self._backoff_s or BACKOFF_BASE_S) * BACKOFF_FACTOR,
                    BACKOFF_MAX_S,
                )
            else:
                # Reset backoff on success
                self._backoff_s = 0.0

            cycle_report["posture"] = interpretation.get("system_posture", "UNKNOWN")
            cycle_report["ai_source"] = interpretation.get("_source", "unknown")

            # ── 4. Write markdown report ──────────────────────
            md_content = generate_markdown_report(report, interpretation, mermaid_output)

            if self.dry_run:
                print(f"\n--- DRY RUN MARKDOWN REPORT ---")
                # Print first 40 lines
                for line in md_content.split("\n")[:40]:
                    print(f"  {line}")
                print(f"  ... ({len(md_content.split(chr(10)))} lines total)")
                print(f"--- END DRY RUN ---\n")
            else:
                md_path = write_markdown_report(md_content, report)
                cycle_report["md_path"] = str(md_path)
                self.total_reports += 1

            # ── 5. Write SSOT events ──────────────────────────
            if not self.dry_run:
                conn_rw = get_db_rw()

                # Write the heuristic cartography event (preserves compatibility)
                write_cartography_event(report)

                # Write the AI-enhanced event
                row_id = write_ai_report_event(
                    conn_rw, report, interpretation,
                    md_path if not self.dry_run else None,
                )
                cycle_report["ssot_row"] = row_id

                # ── 6. Heartbeat ──────────────────────────────
                hb_data = {
                    "cycle": self.cycle,
                    "model": self.model_tier,
                    "posture": interpretation.get("system_posture", "UNKNOWN"),
                    "total_reports": self.total_reports,
                    "ai_calls": self.ai_calls,
                    "ai_failures": self.ai_failures,
                    "fallback_uses": self.fallback_uses,
                    "errors": self.errors,
                    "core_thesis": CORE_THESIS,
                }
                write_event(conn_rw, EVT_HEARTBEAT,
                            f"HEARTBEAT:cycle_{self.cycle}:{cycle_report['posture']}",
                            hb_data)
            else:
                print(f"  [DRY] Posture: {cycle_report['posture']} | "
                      f"Source: {cycle_report['ai_source']}")

        except Exception as e:
            self.errors += 1
            msg = f"Cycle {self.cycle} error: {e}"
            cycle_report["errors"].append(msg)
            print(f"  [ERROR] {msg}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            # Record error to SSOT
            try:
                if conn_rw and not self.dry_run:
                    write_event(conn_rw, EVT_ERROR,
                                f"ERROR:cycle_{self.cycle}",
                                {"error": msg, "traceback": traceback.format_exc()})
            except Exception:
                pass
        finally:
            if conn_rw:
                conn_rw.close()

        cycle_report["duration_ms"] = round((time.monotonic() - t0) * 1000, 1)
        return cycle_report


# ═══════════════════════════════════════════════════════════════
# § 7  ASYNCIO DAEMON LOOP
# ═══════════════════════════════════════════════════════════════

async def daemon_loop(
    daemon: ForesightDaemon,
    interval: float = 3600.0,
    max_cycles: Optional[int] = None,
):
    """Run the FORESIGHT daemon on a timer loop."""
    print("=" * 72)
    print("  P7 FORESIGHT — AI-Powered Meadows Leverage Cartographer")
    print(f"  Commander: Spider Sovereign | Port: P7 NAVIGATE | Gen{GEN}")
    print(f"  Model: {daemon.model_tier} | Window: {daemon.hours}h | Interval: {interval}s")
    print(f"  Dry-run: {daemon.dry_run} | Gemini: {GEMINI_AVAILABLE}")
    print(f"  SSOT: {SSOT_DB}")
    print(f"  Reports: {REPORT_DIR}")
    print(f"  Thesis: {CORE_THESIS}")
    print("=" * 72)

    consecutive_errors = 0
    max_consecutive_errors = 5

    while daemon.is_running:
        cycle_report = daemon.run_cycle()

        # One-line cycle summary
        posture = cycle_report.get("posture", "?")
        hot = cycle_report.get("hottest_level", "?")
        src = cycle_report.get("ai_source", "?")
        dur = cycle_report.get("duration_ms", 0)
        md = cycle_report.get("md_path", "")
        md_short = Path(md).name if md else "(dry)"

        print(
            f"  [{daemon.cycle:>4}] "
            f"L{hot} hottest | {posture} | src:{src} | "
            f"{dur:.0f}ms | {md_short}"
        )

        # Error tracking
        if cycle_report.get("errors"):
            consecutive_errors += 1
            for e in cycle_report["errors"]:
                print(f"         ERROR: {e}", file=sys.stderr)
            if consecutive_errors >= max_consecutive_errors:
                print(f"\n  [CRITICAL] {max_consecutive_errors} consecutive errors. "
                      "Pausing 120s before retry.", file=sys.stderr)
                await asyncio.sleep(120)
                consecutive_errors = 0
        else:
            consecutive_errors = 0

        if max_cycles and daemon.cycle >= max_cycles:
            print(f"\n  Max cycles ({max_cycles}) reached. Stopping.")
            break

        # Wait — respect backoff if Gemini is struggling
        wait = max(interval, daemon._backoff_s)
        try:
            await asyncio.sleep(wait)
        except asyncio.CancelledError:
            break

    print(f"\n  FORESIGHT daemon stopped. Cycles: {daemon.cycle}, "
          f"Reports: {daemon.total_reports}, "
          f"AI calls: {daemon.ai_calls}, Fallbacks: {daemon.fallback_uses}, "
          f"Errors: {daemon.errors}")


# ═══════════════════════════════════════════════════════════════
# § 8  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="P7 FORESIGHT — AI-Powered Meadows Leverage Cartographer (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run forever, hourly
  python hfo_p7_foresight_daemon.py

  # Single cycle (test)
  python hfo_p7_foresight_daemon.py --single

  # Dry run (no writes)
  python hfo_p7_foresight_daemon.py --dry-run --single

  # 24h window, every 30 min
  python hfo_p7_foresight_daemon.py --hours 24 --interval 1800

  # Use specific model
  python hfo_p7_foresight_daemon.py --model flash

  # Status check
  python hfo_p7_foresight_daemon.py --status
""",
    )
    parser.add_argument("--single", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="No SSOT writes or file saves")
    parser.add_argument("--interval", type=float, default=3600.0,
                        help="Seconds between cycles (default: 3600 = hourly)")
    parser.add_argument("--max-cycles", type=int, default=None,
                        help="Stop after N cycles")
    parser.add_argument("--hours", type=float, default=1.0,
                        help="Time window in hours (default: 1)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL_TIER,
                        help=f"Gemini model tier (default: {DEFAULT_MODEL_TIER})")
    parser.add_argument("--status", action="store_true",
                        help="Print status and exit")
    parser.add_argument("--json", action="store_true",
                        help="JSON output for single cycle")

    args = parser.parse_args()

    # ── Status ──
    if args.status:
        print("P7 FORESIGHT — AI Daemon Status")
        print("=" * 55)
        print(f"  HFO_ROOT:         {HFO_ROOT}")
        print(f"  SSOT_DB:          {SSOT_DB}")
        print(f"  DB exists:        {SSOT_DB.exists()}")
        print(f"  Gemini available: {GEMINI_AVAILABLE}")
        if GEMINI_AVAILABLE:
            try:
                spec = get_model(args.model)
                print(f"  Model ID:         {spec.model_id}")
                print(f"  Model tier:       {spec.tier}")
                print(f"  Vertex AI:        {VERTEX_AI_ENABLED}")
            except Exception as e:
                print(f"  Model error:      {e}")
        print(f"  FORESIGHT engine: {FORESIGHT_AVAILABLE}")
        print(f"  Report dir:       {REPORT_DIR}")
        print(f"  Reports exist:    {REPORT_DIR.exists()}")
        if REPORT_DIR.exists():
            reports = sorted(REPORT_DIR.glob("*_foresight.md"))
            print(f"  Report count:     {len(reports)}")
            if reports:
                print(f"  Latest:           {reports[-1].name}")
        # Quick health
        if SSOT_DB.exists():
            conn = get_db_ro()
            total_events = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
            ai_reports = conn.execute(
                f"SELECT COUNT(*) FROM stigmergy_events WHERE event_type = ?",
                (EVT_REPORT,)
            ).fetchone()[0]
            conn.close()
            print(f"  SSOT events:      {total_events}")
            print(f"  AI report events: {ai_reports}")
        return

    # ── Create daemon ──
    daemon = ForesightDaemon(
        hours=args.hours,
        model_tier=args.model,
        dry_run=args.dry_run,
    )

    # ── Signal handling ──
    def _handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. Stopping FORESIGHT daemon...")
        daemon.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ── Single mode ──
    if args.single:
        cycle_report = daemon.run_cycle()
        if args.json:
            print(json.dumps(cycle_report, indent=2, default=str))
        else:
            print(f"\nP7 FORESIGHT — Single Cycle Report")
            print("=" * 55)
            print(f"  Cycle:     {cycle_report['cycle']}")
            print(f"  Posture:   {cycle_report.get('posture', '?')}")
            print(f"  Hottest:   L{cycle_report.get('hottest_level', '?')}")
            print(f"  AI Source: {cycle_report.get('ai_source', '?')}")
            print(f"  MD Report: {cycle_report.get('md_path', '(dry run)')}")
            print(f"  SSOT Row:  {cycle_report.get('ssot_row', '(dry run)')}")
            print(f"  Duration:  {cycle_report.get('duration_ms', 0):.0f}ms")
            if cycle_report.get("errors"):
                print(f"  Errors:    {cycle_report['errors']}")
            print(f"\n  {CORE_THESIS}")
        return

    # ── Daemon mode ──
    asyncio.run(daemon_loop(daemon, interval=args.interval, max_cycles=args.max_cycles))


if __name__ == "__main__":
    main()
