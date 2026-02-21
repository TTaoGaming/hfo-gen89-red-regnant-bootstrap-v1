#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════
  P0 GREATER_SCRY — Lidless Legion External Intelligence (Divination 7th)
  Grimoire V7 Slot B2+ — Web Intelligence Driven by P7 Seals & Spheres
══════════════════════════════════════════════════════════════════════

  "The Lidless Eye sees inward (TRUE_SEEING) and outward (GREATER_SCRY)."

  GREATER_SCRY reads the latest P7 Summoner seal/sphere events from SSOT
  stigmergy, extracts their targets, generates web search queries, runs
  DuckDuckGo searches via hfo_web_tools.py, and writes the intelligence
  back to SSOT as CloudEvent stigmergy. Repeat every 10 minutes.

  The P7 Spider Sovereign steers WHAT topics to scry.
  The P0 Lidless Legion executes the scrying.
  The swarm reads the intelligence via stigmergy.

  SBE Spec (Tier 2 — Happy Path):
    Given P7 Summoner has emitted seal/sphere events with strategic targets
    When  P0 GREATER_SCRY reads those targets and runs web searches
    Then  external web intelligence for each target is written as CloudEvent
          stigmergy, enriching the SSOT with real-world context for the
          swarm to consume

  Daemon Modes:
    --once            Single scry cycle (default)
    --daemon          Persistent daemon mode
    --interval N      Seconds between cycles (default: 600 = 10 min)
    --dry-run         Show queries without searching
    --max-results N   Max results per search (default: 5)
    --json            JSON output instead of text

  Event Types:
    hfo.gen90.p0.greater_scry.intel      — Web intelligence for a seal/sphere target
    hfo.gen90.p0.greater_scry.heartbeat  — Daemon alive pulse
    hfo.gen90.p0.greater_scry.cycle      — Cycle summary (targets scried, results)

  Port: P0 OBSERVE (Lidless Legion)
  Pair: P6 ASSIMILATE (Kraken Keeper)
  Driven by: P7 NAVIGATE (Spider Sovereign) seal/sphere targets
  Commander: Lidless Legion
  Mnemonic: O = OBSERVE = "See the world as it IS, not as we imagine"
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal as _signal
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from hfo_ssot_write import get_db_readwrite as _get_db_rw

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION (PAL — no hardcoding)
# ═══════════════════════════════════════════════════════════════

_SELF_DIR = Path(__file__).resolve().parent


def _find_root() -> Path:
    """Walk up from script dir and cwd to find AGENTS.md anchor."""
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))


def _load_pointer_registry() -> dict:
    """Load the PAL pointer registry. Returns empty dict on failure."""
    pf = HFO_ROOT / "hfo_gen90_pointers_blessed.json"
    if pf.exists():
        data = json.loads(pf.read_text(encoding="utf-8"))
        return data.get("pointers", data)
    return {}


def _resolve_pointer(key: str, pointers: Optional[dict] = None) -> Path:
    """Resolve a PAL pointer key to an absolute path."""
    ptrs = pointers or _load_pointer_registry()
    if key in ptrs:
        entry = ptrs[key]
        rel = entry["path"] if isinstance(entry, dict) else entry
        return HFO_ROOT / rel
    raise KeyError(f"Pointer key not found: {key}")


# Resolve paths through PAL
_POINTERS = _load_pointer_registry()

try:
    SSOT_DB = _resolve_pointer("ssot.db", _POINTERS)
except KeyError:
    SSOT_DB = None

try:
    WEB_TOOLS_PATH = _resolve_pointer("swarm.web_tools", _POINTERS)
except KeyError:
    WEB_TOOLS_PATH = None

# Import web tools
sys.path.insert(0, str(_SELF_DIR))
try:
    from hfo_web_tools import web_search, web_news, search_and_summarize
    WEB_TOOLS_AVAILABLE = True
except ImportError:
    WEB_TOOLS_AVAILABLE = False
    print("⚠ hfo_web_tools not available — GREATER_SCRY requires web access", file=sys.stderr)

GEN = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG = f"hfo_p0_greater_scry_gen{GEN}"

EVT_INTEL = f"hfo.gen{GEN}.p0.greater_scry.intel"
EVT_HEARTBEAT = f"hfo.gen{GEN}.p0.greater_scry.heartbeat"
EVT_CYCLE = f"hfo.gen{GEN}.p0.greater_scry.cycle"

# ═══════════════════════════════════════════════════════════════
# § 1  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════


@dataclass
class ScryTarget:
    """A target extracted from P7 seal or sphere event."""
    source_event_id: int
    source_type: str           # "seal" or "sphere"
    spell: str                 # e.g. "IMPRISONMENT", "FORESIGHT"
    target: str                # The seal_target or sphere_target text
    reason: str                # The seal_reason or sphere_reason text
    meadows_level: int
    system_posture: str
    timestamp: str


@dataclass
class ScryResult:
    """Result of a web search for a target."""
    target: ScryTarget
    query: str                 # The generated search query
    search_type: str           # "web" or "news"
    result_count: int
    raw_results: str           # Formatted search results
    timestamp: str = ""


@dataclass
class ScryCycleReport:
    """Summary of one scry cycle."""
    cycle: int
    timestamp: str
    targets_found: int
    targets_scried: int
    total_results: int
    intel_events_written: int
    errors: List[str] = field(default_factory=list)
    targets: List[Dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════


def _get_db_ro() -> Optional[sqlite3.Connection]:
    """Read-only SSOT connection."""
    if SSOT_DB is None or not SSOT_DB.exists():
        return None
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn



def _write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
) -> int:
    """Write CloudEvent to stigmergy_events. Returns rowid."""
    ts = datetime.now(timezone.utc).isoformat()
    content_hash = hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode()
    ).hexdigest()
    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, source, subject, timestamp, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, SOURCE_TAG, subject, ts, json.dumps(data, default=str), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 3  P7 SEAL/SPHERE READER — The Scrying Lens
# ═══════════════════════════════════════════════════════════════


def read_latest_targets(limit: int = 5) -> List[ScryTarget]:
    """Read the latest P7 seal and sphere targets from stigmergy.

    Returns the most recent unique targets (deduped by target text).
    Reads both seal and sphere events, interleaved by timestamp.
    """
    conn = _get_db_ro()
    if conn is None:
        print("⚠ Cannot read SSOT — no DB connection", file=sys.stderr)
        return []

    targets = []
    seen_targets = set()

    try:
        # Read latest seals
        for row in conn.execute(
            """SELECT id, event_type, timestamp, subject, data_json
               FROM stigmergy_events
               WHERE event_type LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (f"hfo.gen{GEN}.summoner.seal%", limit),
        ):
            data = _safe_parse_data(row["data_json"])
            target_text = data.get("seal_target", "")
            if target_text and target_text not in seen_targets:
                seen_targets.add(target_text)
                targets.append(ScryTarget(
                    source_event_id=row["id"],
                    source_type="seal",
                    spell=data.get("seal_spell", "UNKNOWN"),
                    target=target_text,
                    reason=data.get("seal_reason", ""),
                    meadows_level=data.get("seal_meadows_level", 0),
                    system_posture=data.get("system_posture", "UNKNOWN"),
                    timestamp=row["timestamp"],
                ))

        # Read latest spheres
        for row in conn.execute(
            """SELECT id, event_type, timestamp, subject, data_json
               FROM stigmergy_events
               WHERE event_type LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (f"hfo.gen{GEN}.summoner.sphere%", limit),
        ):
            data = _safe_parse_data(row["data_json"])
            target_text = data.get("sphere_target", "")
            if target_text and target_text not in seen_targets:
                seen_targets.add(target_text)
                targets.append(ScryTarget(
                    source_event_id=row["id"],
                    source_type="sphere",
                    spell=data.get("sphere_spell", "UNKNOWN"),
                    target=target_text,
                    reason=data.get("sphere_reason", ""),
                    meadows_level=data.get("sphere_meadows_level", 0),
                    system_posture=data.get("system_posture", "UNKNOWN"),
                    timestamp=row["timestamp"],
                ))

    finally:
        conn.close()

    return targets


def _safe_parse_data(data_json: str) -> dict:
    """Parse data_json, handling CloudEvent envelope or flat data."""
    try:
        parsed = json.loads(data_json)
        # CloudEvent envelope — data is nested
        if isinstance(parsed, dict) and "data" in parsed and "specversion" in parsed:
            return parsed["data"]
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ═══════════════════════════════════════════════════════════════
# § 4  QUERY GENERATOR — Seal/Sphere → Search Query
# ═══════════════════════════════════════════════════════════════


def generate_queries(target: ScryTarget) -> List[Tuple[str, str]]:
    """Generate web search queries from a seal/sphere target.

    Returns list of (query_string, search_type) tuples.
    search_type is "web" or "news".

    Strategy: HFO targets describe PROBLEMS (seals) and OPPORTUNITIES (spheres).
    We map the underlying technical concept to a generic web-searchable query.
    """
    queries = []

    # Step 1: Try concept-mapping first (best results)
    concept_query = _concept_map(target)
    if concept_query:
        queries.append((concept_query, "web"))
        queries.append((concept_query + " 2025 2026", "news"))
        return queries

    # Step 2: Fall back to cleaned extraction
    raw_target = target.target.strip()
    cleaned = _extract_searchable_concepts(raw_target, target.reason)

    if not cleaned or len(cleaned) < 15:
        return queries

    queries.append((cleaned, "web"))
    if len(cleaned) <= 120:
        queries.append((cleaned, "news"))

    return queries


# ── Concept mapper: HFO themes → web-searchable queries ──

_CONCEPT_MAP = {
    # Seal themes (problems to search for solutions)
    "memory loss": "AI agent context window memory persistence techniques",
    "memory_loss": "AI agent context window memory persistence techniques",
    "gate block": "software quality gate enforcement automated pipeline",
    "gate drift": "configuration drift detection remediation devops",
    "protocol drift": "API protocol drift detection breaking changes",
    "integrity violation": "data integrity monitoring automated validation",
    "tamper alert": "software supply chain tamper detection verification",
    "fractured": "distributed system consistency partition recovery",
    "reaper": "process watchdog health check daemon monitoring",
    "antipattern": "software antipatterns detection refactoring strategies",
    "seal away": "software deprecation strategy safe removal patterns",
    "halt activity": "circuit breaker pattern distributed systems",
    "prevent drift": "infrastructure drift detection immutable deployment",
    # Sphere themes (opportunities to explore)
    "unrouted doc": "automated document classification tagging machine learning",
    "port classification": "multi-label document classification taxonomy",
    "port assignment": "automated content routing classification system",
    "port enrichment": "metadata enrichment document processing pipeline",
    "strategic potential": "knowledge management strategy document mining",
    "frontier": "AI research frontier emerging techniques",
    "reshape resource": "software architecture refactoring modernization patterns",
    "perspective shift": "lateral thinking software architecture innovation",
    "highest leverage": "systems thinking leverage points Donella Meadows",
    "foresight": "technology foresight strategic planning framework",
    "self-organization": "self-organizing systems emergence agent architecture",
    "explore": "knowledge discovery automated exploration techniques",
}


def _concept_map(target: ScryTarget) -> Optional[str]:
    """Map a seal/sphere target to a web-searchable concept query.

    Searches the target text and reason for known concept patterns and
    returns a generic technical query that will produce useful web results.
    """
    full_text = f"{target.target} {target.reason}".lower()

    # Check for known concept patterns (longest match first)
    best_match = ""
    best_query = ""
    for pattern, query in _CONCEPT_MAP.items():
        if pattern.lower() in full_text and len(pattern) > len(best_match):
            best_match = pattern
            best_query = query

    if best_query:
        # Add seal/sphere flavor
        if target.source_type == "seal":
            return f"{best_query} best practices"
        else:
            return f"{best_query} latest research"

    return None


def _extract_searchable_concepts(target: str, reason: str) -> str:
    """Extract searchable concepts from HFO-internal language.

    P7 seal/sphere targets are phrased in HFO jargon. We need to
    extract the underlying technical concepts that would produce
    useful web results.
    """
    # Combine target + reason for richer context
    full_text = f"{target} {reason}"

    # Remove HFO-specific terms that won't help web search
    hfo_noise = [
        r"\bL\d{1,2}\b",                    # L1-L13 levels
        r"\bP\d\b",                          # P0-P7 ports
        r"\bport\s*\d\b",                    # port 0, port 7, etc.
        r"\boctree\b",                       # octree (HFO-specific)
        r"\bstigmergy\b",                    # stigmergy
        r"\bCloudEvent\b",                   # CloudEvent
        r"\bSSO[T]?\b",                      # SSOT
        r"\bMeadows\b",                      # Meadows leverage
        r"\bgrimore|grimoire\b",             # grimoire
        r"\bHFO\b",                          # HFO
        r"\bGen\d+\b",                       # Gen90, Gen90
        r"\bspell\b",                        # spell
        r"\bseal\b",                         # seal (HFO sense)
        r"\bsphere\b",                       # sphere (HFO sense)
        r"\bswarm\b",                        # swarm
        r"\bdaemon\b",                       # daemon (HFO sense)
        r"\bFRACTURED\b",                    # internal status
        r"\bPRISMATIC_WALL\b",               # internal spell name
        r"\bDEATH_WARD\b",                   # internal spell name
        r"\bgate\s*block\b",                 # gate block
        r"\btamper\s*alert\b",               # tamper alert
        r"\bPREY8\b",                        # PREY8 loop
        r"\bmedallion\b",                    # medallion
        r"\bbronze|silver|gold\b",           # medallion layers
        r"\bantipattern\b",                  # too generic
    ]

    cleaned = full_text
    for pattern in hfo_noise:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # If the cleaned text is too short (stripped too much), use a simpler approach
    if len(cleaned) < 20:
        # Fall back to extracting noun phrases from original
        words = re.findall(r"\b[A-Za-z]{4,}\b", full_text)
        # Remove common stop words
        stops = {"this", "that", "with", "from", "have", "been", "will",
                 "must", "should", "which", "their", "these", "those",
                 "about", "into", "also", "what", "when", "where", "need",
                 "currently", "specifically", "representing", "remaining",
                 "crucial", "critical", "permanent", "persistent", "active"}
        words = [w for w in words if w.lower() not in stops]
        cleaned = " ".join(words[:8])

    # Truncate to reasonable search query length
    if len(cleaned) > 150:
        # Try to break at word boundary
        cleaned = cleaned[:150].rsplit(" ", 1)[0]

    return cleaned


# ═══════════════════════════════════════════════════════════════
# § 5  WEB SEARCH ENGINE — The Scrying Pool
# ═══════════════════════════════════════════════════════════════


def execute_search(query: str, search_type: str, max_results: int = 5) -> str:
    """Execute a web or news search. Returns formatted results."""
    if not WEB_TOOLS_AVAILABLE:
        return "ERROR: hfo_web_tools not available"

    try:
        if search_type == "news":
            return web_news(query, max_results=max_results)
        else:
            return web_search(query, max_results=max_results)
    except Exception as e:
        return f"Search error: {e}"


# ═══════════════════════════════════════════════════════════════
# § 6  STIGMERGY OUTPUT — Intelligence to SSOT
# ═══════════════════════════════════════════════════════════════


def write_intel_event(result: ScryResult) -> Optional[int]:
    """Write a web intelligence result to SSOT stigmergy."""
    conn = _get_db_rw()
    if conn is None:
        return None

    try:
        data = {
            "source_event_id": result.target.source_event_id,
            "source_type": result.target.source_type,
            "spell": result.target.spell,
            "target": result.target.target[:200],
            "query": result.query,
            "search_type": result.search_type,
            "result_count": result.result_count,
            "results": result.raw_results[:4000],  # Truncate for DB
            "meadows_level": result.target.meadows_level,
            "system_posture": result.target.system_posture,
            "scry_timestamp": result.timestamp,
        }

        subject = (
            f"SCRY:{result.target.source_type.upper()}"
            f":{result.target.spell}"
            f":{result.search_type}"
            f":{result.result_count}results"
        )

        row_id = _write_event(conn, EVT_INTEL, subject, data)
        return row_id
    except Exception as e:
        print(f"⚠ Intel event write failed: {e}", file=sys.stderr)
        return None
    finally:
        conn.close()


def write_cycle_event(report: ScryCycleReport) -> Optional[int]:
    """Write a cycle summary event to SSOT stigmergy."""
    conn = _get_db_rw()
    if conn is None:
        return None

    try:
        data = asdict(report)
        subject = (
            f"SCRY_CYCLE:{report.cycle}"
            f":targets_{report.targets_scried}"
            f":intel_{report.intel_events_written}"
        )
        row_id = _write_event(conn, EVT_CYCLE, subject, data)
        return row_id
    except Exception as e:
        print(f"⚠ Cycle event write failed: {e}", file=sys.stderr)
        return None
    finally:
        conn.close()


def write_heartbeat(cycle: int, targets_scried: int) -> Optional[int]:
    """Write daemon heartbeat to SSOT."""
    conn = _get_db_rw()
    if conn is None:
        return None

    try:
        ts = datetime.now(timezone.utc).isoformat()
        data = {
            "daemon": "P0_GREATER_SCRY",
            "cycle": cycle,
            "targets_scried": targets_scried,
            "uptime_cycles": cycle,
        }
        # Use ts+cycle for unique hash
        content_hash = hashlib.sha256(
            json.dumps({"heartbeat": True, "ts": ts, "cycle": cycle}).encode()
        ).hexdigest()
        cur = conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, source, subject, timestamp, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (EVT_HEARTBEAT, SOURCE_TAG,
             f"HEARTBEAT:cycle_{cycle}:scried_{targets_scried}",
             ts, json.dumps(data), content_hash),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id
    except Exception as e:
        print(f"⚠ Heartbeat write failed: {e}", file=sys.stderr)
        return None


# ═══════════════════════════════════════════════════════════════
# § 7  SPELL INTERFACE — Cast GREATER_SCRY
# ═══════════════════════════════════════════════════════════════


def spell_greater_scry(
    max_results: int = 5,
    target_limit: int = 5,
    dry_run: bool = False,
    write_stig: bool = True,
    output_json: bool = False,
    cycle: int = 1,
) -> ScryCycleReport:
    """Cast GREATER_SCRY — read P7 targets, search web, write intelligence.

    Args:
        max_results: Max web results per search query
        target_limit: Max seal/sphere targets to read per cycle
        dry_run: If True, show queries but don't actually search
        write_stig: If True, write results to SSOT stigmergy
        output_json: If True, output JSON instead of text
        cycle: Current daemon cycle number
    """
    ts = datetime.now(timezone.utc).isoformat()

    report = ScryCycleReport(
        cycle=cycle,
        timestamp=ts,
        targets_found=0,
        targets_scried=0,
        total_results=0,
        intel_events_written=0,
    )

    # 1. Read P7 seal/sphere targets
    targets = read_latest_targets(limit=target_limit)
    report.targets_found = len(targets)

    if not targets:
        msg = "No P7 seal/sphere targets found in stigmergy."
        report.errors.append(msg)
        if not output_json:
            print(f"⚠ {msg}", file=sys.stderr)
        return report

    if not output_json:
        print(f"═══ GREATER_SCRY Cycle {cycle} — {len(targets)} targets ═══")

    # 2. For each target, generate queries and search
    for target in targets:
        queries = generate_queries(target)
        if not queries:
            report.errors.append(f"No searchable query for: {target.target[:60]}")
            continue

        target_info = {
            "type": target.source_type,
            "spell": target.spell,
            "target": target.target[:100],
            "queries": [],
        }

        if not output_json:
            print(f"\n┌─ {target.source_type.upper()} {target.spell} "
                  f"(L{target.meadows_level}, {target.system_posture}) ─┐")
            print(f"│  Target: {target.target[:80]}")

        for query, search_type in queries:
            if not output_json:
                print(f"│  Query ({search_type}): {query[:80]}")

            if dry_run:
                target_info["queries"].append({"query": query, "type": search_type, "dry_run": True})
                continue

            # Execute the search
            results_text = execute_search(query, search_type, max_results=max_results)
            result_count = results_text.count("[") if results_text else 0

            result = ScryResult(
                target=target,
                query=query,
                search_type=search_type,
                result_count=result_count,
                raw_results=results_text,
                timestamp=ts,
            )

            report.total_results += result_count
            report.targets_scried += 1

            target_info["queries"].append({
                "query": query,
                "type": search_type,
                "result_count": result_count,
            })

            if not output_json:
                print(f"│  → {result_count} results")
                # Show first 3 lines of results
                for line in results_text.split("\n")[:3]:
                    print(f"│    {line[:80]}")

            # Write intel event to SSOT
            if write_stig and not dry_run:
                row_id = write_intel_event(result)
                if row_id:
                    report.intel_events_written += 1
                    if not output_json:
                        print(f"│  ✓ Intel written: row {row_id}")

            # Rate limit between searches (be nice to DuckDuckGo)
            time.sleep(1.5)

        report.targets.append(target_info)

        if not output_json:
            print(f"└──────────────────────────────────────────────┘")

    # 3. Write cycle summary event
    if write_stig and not dry_run:
        cycle_row = write_cycle_event(report)
        if not output_json and cycle_row:
            print(f"\n✓ Cycle summary written: row {cycle_row}")

    # 4. Output
    if output_json:
        print(json.dumps(asdict(report), indent=2, default=str))
    elif not dry_run:
        print(f"\n═══ Cycle {cycle} complete: "
              f"{report.targets_scried} scried, "
              f"{report.total_results} results, "
              f"{report.intel_events_written} intel events ═══")

    return report


# ═══════════════════════════════════════════════════════════════
# § 8  DAEMON MODE — The Far-Seeing Eye
# ═══════════════════════════════════════════════════════════════

_DAEMON_SHUTDOWN = False


def _daemon_signal_handler(signum, frame):
    """Graceful shutdown on SIGINT/SIGTERM."""
    global _DAEMON_SHUTDOWN
    _DAEMON_SHUTDOWN = True
    print(f"\n⊗ GREATER_SCRY daemon received signal {signum} — shutting down...", file=sys.stderr)


def daemon_loop(interval: int = 600, max_results: int = 5, target_limit: int = 5):
    """Run GREATER_SCRY in persistent daemon mode.

    Scries the web every `interval` seconds based on the latest P7
    seal/sphere targets. Default: 10 minutes.

    Args:
        interval: Seconds between scry cycles (default 600 = 10 min)
        max_results: Max web results per query
        target_limit: Max targets per cycle
    """
    global _DAEMON_SHUTDOWN

    _signal.signal(_signal.SIGINT, _daemon_signal_handler)
    _signal.signal(_signal.SIGTERM, _daemon_signal_handler)

    cycle = 0

    print(f"═══════════════════════════════════════════════════", file=sys.stderr)
    print(f"  P0 GREATER_SCRY — Daemon Mode Activated", file=sys.stderr)
    print(f"  Interval: {interval}s | Max Results: {max_results}", file=sys.stderr)
    print(f"  Target Limit: {target_limit} | Stigmergy: ON", file=sys.stderr)
    print(f"  Web tools: {'AVAILABLE' if WEB_TOOLS_AVAILABLE else 'MISSING'}", file=sys.stderr)
    print(f"  The Far-Seeing Eye opens.", file=sys.stderr)
    print(f"═══════════════════════════════════════════════════", file=sys.stderr)

    while not _DAEMON_SHUTDOWN:
        cycle += 1
        ts_start = time.time()
        print(f"\n─── Scry Cycle {cycle} @ "
              f"{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} ───",
              file=sys.stderr)

        try:
            report = spell_greater_scry(
                max_results=max_results,
                target_limit=target_limit,
                dry_run=False,
                write_stig=True,
                cycle=cycle,
            )
        except Exception as e:
            print(f"⚠ Cycle {cycle} failed: {e}", file=sys.stderr)
            report = ScryCycleReport(
                cycle=cycle,
                timestamp=datetime.now(timezone.utc).isoformat(),
                targets_found=0, targets_scried=0,
                total_results=0, intel_events_written=0,
                errors=[str(e)],
            )

        # Heartbeat
        hb_row = write_heartbeat(cycle, report.targets_scried)
        elapsed = time.time() - ts_start
        print(
            f"  → {report.targets_scried} scried | "
            f"{report.intel_events_written} intel | "
            f"{elapsed:.1f}s | heartbeat {hb_row}",
            file=sys.stderr,
        )

        # Sleep in small increments for signal responsiveness
        remaining = max(0, interval - elapsed)
        sleep_step = min(5.0, remaining)
        slept = 0.0
        while slept < remaining and not _DAEMON_SHUTDOWN:
            time.sleep(sleep_step)
            slept += sleep_step

    print(f"\n⊗ GREATER_SCRY daemon stopped after {cycle} cycles.", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════
# § 9  CLI
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="P0 GREATER_SCRY — Web Intelligence via P7 Seal/Sphere Targets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  --once            Single scry cycle (default)
  --daemon          Persistent daemon mode (every 10 min)
  --dry-run         Show queries without searching

Examples:
  python hfo_p0_greater_scry.py --once
  python hfo_p0_greater_scry.py --daemon --interval 600
  python hfo_p0_greater_scry.py --dry-run
  python hfo_p0_greater_scry.py --json --max-results 3
        """,
    )

    parser.add_argument("--once", action="store_true", default=True,
                        help="Single scry cycle (default)")
    parser.add_argument("--daemon", action="store_true",
                        help="Persistent daemon mode")
    parser.add_argument("--interval", type=int, default=600,
                        help="Daemon interval in seconds (default: 600 = 10 min)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show queries without searching")
    parser.add_argument("--max-results", type=int, default=5,
                        help="Max results per search (default: 5)")
    parser.add_argument("--target-limit", type=int, default=5,
                        help="Max seal/sphere targets per cycle (default: 5)")
    parser.add_argument("--json", action="store_true",
                        help="JSON output instead of text")
    parser.add_argument("--no-stigmergy", action="store_true",
                        help="Don't write results to SSOT")

    args = parser.parse_args()

    if args.daemon:
        daemon_loop(
            interval=args.interval,
            max_results=args.max_results,
            target_limit=args.target_limit,
        )
    else:
        spell_greater_scry(
            max_results=args.max_results,
            target_limit=args.target_limit,
            dry_run=args.dry_run,
            write_stig=not args.no_stigmergy,
            output_json=args.json,
        )


if __name__ == "__main__":
    main()
