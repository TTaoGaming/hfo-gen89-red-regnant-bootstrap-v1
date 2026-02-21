#!/usr/bin/env python3
"""
hfo_p7_astral_projection.py — P7 Spider Sovereign ASTRAL_PROJECTION Spell (Gen89)
==================================================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | Spell: ASTRAL_PROJECTION (Necromancy 9th)
Title: Summoner of Seals and Spheres | Epic Class: Cosmic Descryer (ELH p.19)
                                       + Thaumaturgist (DMG p.184)
Aspect: B — SPHERES (multiplanar navigation, multi-domain awareness, cosmic C2)

PURPOSE:
    Meta-view of SSOT topology — project consciousness across all planes.
    Generates the Cosmic Descryer's map: a complete picture of what exists
    across the 8 ports, 4 medallion layers, all document sources, and
    the stigmergy event trail. The "astral body" sees things the
    "material body" (an individual agent session) cannot.

    "The Cosmic Descryer sees all crystal spheres at once."

    While TREMORSENSE passively senses vibrations and FORESIGHT forecasts
    where they lead, ASTRAL_PROJECTION provides the omniscient snapshot:
    the full system topology, document distribution, event flow map,
    and inter-port relationship matrix.

D&D 3.5e RAW (PHB p.201):
    Astral Projection — Necromancy 9th — projects the caster's consciousness
    to the Astral Plane, creating a silver cord back to the material body.
    From the Astral Plane, one can see portals to ALL other planes.
    Duration: Permanent until you return to your body.

SBE/ATDD SCENARIOS (Specification by Example):
═══════════════════════════════════════════════

  TIER 1 — INVARIANT:
    Scenario: Projection requires accessible SSOT
      Given SSOT database does not exist
      When  ASTRAL_PROJECTION project is cast
      Then  PROJECTION_FAILED error is returned

  TIER 2 — HAPPY PATH:
    Scenario: Full SSOT topology projection
      Given SSOT with 9,859 documents across 8 ports
      When  ASTRAL_PROJECTION project is cast
      Then  a port × source matrix is generated
      And   document counts + word counts per cell are reported
      And   a topology CloudEvent is written

    Scenario: Stigmergy flow map
      Given stigmergy events exist with cross-port references
      When  ASTRAL_PROJECTION flows is cast
      Then  inter-port event flows are tallied
      And   top event type families are ranked

    Scenario: Medallion survey
      Given documents tagged with medallion layers + filesystem has layers
      When  ASTRAL_PROJECTION survey is cast
      Then  bronze/silver/gold/hfo document counts reported
      And   filesystem artifact counts per layer reported

  TIER 3 — DEEP PROJECTION:
    Scenario: Document type taxonomy
      Given documents have doc_type field
      When  ASTRAL_PROJECTION taxonomy is cast
      Then  all doc_types enumerated with counts

    Scenario: Temporal analysis
      Given documents span 2025-01 → 2026-02
      When  ASTRAL_PROJECTION timeline is cast
      Then  monthly document creation histogram generated

Event Types:
    hfo.gen89.p7.astral_projection.project    — Full topology snapshot
    hfo.gen89.p7.astral_projection.flows      — Stigmergy flow analysis
    hfo.gen89.p7.astral_projection.survey     — Medallion layer survey
    hfo.gen89.p7.astral_projection.taxonomy   — Document type breakdown
    hfo.gen89.p7.astral_projection.timeline   — Temporal analysis

USAGE:
    python hfo_p7_astral_projection.py project        # Full topology
    python hfo_p7_astral_projection.py flows          # Stigmergy flow map
    python hfo_p7_astral_projection.py survey         # Medallion layers
    python hfo_p7_astral_projection.py taxonomy       # Doc type breakdown
    python hfo_p7_astral_projection.py timeline       # Monthly histogram
    python hfo_p7_astral_projection.py --json project # Machine-readable

Pointer key: p7.astral_projection
Medallion: bronze
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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from hfo_ssot_write import get_db_readwrite as get_db_rw

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION (PAL)
# ═══════════════════════════════════════════════════════════════

_SELF_DIR = Path(__file__).resolve().parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

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

GEN = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG = f"hfo_p7_astral_projection_gen{GEN}"
FORGE_ROOT = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge"

# Port labels for display
PORT_LABELS = {
    "P0": "OBSERVE  (Lidless Legion)",
    "P1": "BRIDGE   (Web Weaver)",
    "P2": "SHAPE    (Mirror Magus)",
    "P3": "INJECT   (Harmonic Hydra)",
    "P4": "DISRUPT  (Red Regnant)",
    "P5": "IMMUNIZE (Pyre Praetorian)",
    "P6": "ASSIMILATE (Kraken Keeper)",
    "P7": "NAVIGATE (Spider Sovereign)",
}


# ═══════════════════════════════════════════════════════════════
# § 1  DATABASE & CLOUDEVENT HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": SOURCE_TAG,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    content_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, SOURCE_TAG, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 2  SPELL: PROJECT — Full SSOT topology
# ═══════════════════════════════════════════════════════════════

def spell_project(quiet: bool = False) -> dict[str, Any]:
    """
    ASTRAL PROJECTION — Generate complete SSOT topology map.

    SBE Contract:
      Given  SSOT database with documents across ports and sources
      When   spell_project is cast
      Then   port × source matrix with counts + word totals generated
      And    topology CloudEvent written to SSOT
    """
    _print = (lambda *a, **k: None) if quiet else print

    if not SSOT_DB.exists():
        return {"status": "PROJECTION_FAILED", "error": "SSOT not found"}

    try:
        conn = get_db_ro()
    except Exception as e:
        return {"status": "PROJECTION_FAILED", "error": str(e)}

    # ── Port × Source matrix ──
    port_source = conn.execute("""
        SELECT COALESCE(port, 'NULL') as port,
               COALESCE(source, 'unknown') as source,
               COUNT(*) as doc_count,
               SUM(word_count) as total_words
        FROM documents
        GROUP BY port, source
        ORDER BY port, source
    """).fetchall()

    matrix = defaultdict(lambda: defaultdict(lambda: {"docs": 0, "words": 0}))
    all_sources = set()
    for row in port_source:
        p = row["port"]
        s = row["source"]
        all_sources.add(s)
        matrix[p][s] = {"docs": row["doc_count"], "words": row["total_words"] or 0}

    # ── Summary stats ──
    total_row = conn.execute(
        "SELECT COUNT(*) as cnt, SUM(word_count) as words FROM documents"
    ).fetchone()
    event_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM stigmergy_events"
    ).fetchone()

    total_docs = total_row["cnt"] if total_row else 0
    total_words = total_row["words"] if total_row else 0
    total_events = event_row["cnt"] if event_row else 0

    # ── Port summary ──
    port_summary = conn.execute("""
        SELECT COALESCE(port, 'NULL') as port,
               COUNT(*) as doc_count,
               SUM(word_count) as total_words
        FROM documents
        GROUP BY port
        ORDER BY port
    """).fetchall()

    # ── Source summary ──
    source_summary = conn.execute("""
        SELECT COALESCE(source, 'unknown') as source,
               COUNT(*) as doc_count,
               SUM(word_count) as total_words
        FROM documents
        GROUP BY source
        ORDER BY doc_count DESC
    """).fetchall()

    conn.close()

    # Format port summary
    port_data = {}
    for row in port_summary:
        p = row["port"]
        label = PORT_LABELS.get(p, p)
        port_data[p] = {
            "label": label,
            "docs": row["doc_count"],
            "words": row["total_words"] or 0,
        }

    source_data = {}
    for row in source_summary:
        source_data[row["source"]] = {
            "docs": row["doc_count"],
            "words": row["total_words"] or 0,
        }

    # Display
    _print("  ╔══════════════════════════════════════════════════════════════╗")
    _print("  ║       ASTRAL PROJECTION — SSOT TOPOLOGY MAP                ║")
    _print("  ║       The Cosmic Descryer sees all crystal spheres          ║")
    _print("  ╚══════════════════════════════════════════════════════════════╝")
    _print()
    _print(f"  Total Documents: {total_docs:,}")
    _print(f"  Total Words:     {total_words:,}")
    _print(f"  Total Events:    {total_events:,}")
    _print()

    # Port breakdown
    _print("  ┌─── PORT DISTRIBUTION ────────────────────────────────┐")
    for p in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "NULL"]:
        if p in port_data:
            pd = port_data[p]
            bar_len = min(40, pd["docs"] // 30)
            bar = "█" * bar_len
            _print(f"  │ {p:4s} {pd.get('label', p):30s} {pd['docs']:>5,} docs {pd['words']:>9,} words")
            if bar:
                _print(f"  │      {bar}")
    _print("  └─────────────────────────────────────────────────────┘")
    _print()

    # Source breakdown
    _print("  ┌─── SOURCE DISTRIBUTION ──────────────────────────────┐")
    for src, sd in sorted(source_data.items(), key=lambda x: -x[1]["docs"]):
        _print(f"  │ {src:<20s} {sd['docs']:>5,} docs {sd['words']:>9,} words")
    _print("  └─────────────────────────────────────────────────────┘")

    # Write CloudEvent
    result = {
        "status": "PROJECTED",
        "total_docs": total_docs,
        "total_words": total_words,
        "total_events": total_events,
        "port_summary": port_data,
        "source_summary": source_data,
    }

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.astral_projection.project",
                    f"PROJECT:{total_docs}docs:{total_events}events",
                    {"total_docs": total_docs, "total_words": total_words,
                     "total_events": total_events,
                     "port_counts": {p: d["docs"] for p, d in port_data.items()},
                     "source_counts": {s: d["docs"] for s, d in source_data.items()},
                     "core_thesis": "The Cosmic Descryer sees all crystal spheres at once."})
        conn.close()
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════
# § 3  SPELL: FLOWS — Stigmergy event flow analysis
# ═══════════════════════════════════════════════════════════════

def spell_flows(limit: int = 20, quiet: bool = False) -> dict[str, Any]:
    """
    ASTRAL PROJECTION FLOWS — Map inter-port event flows.

    SBE Contract:
      Given  stigmergy events exist with event_type families
      When   spell_flows is cast
      Then   top event type families ranked by count
      And    port-to-port flow patterns identified
    """
    _print = (lambda *a, **k: None) if quiet else print

    if not SSOT_DB.exists():
        return {"status": "PROJECTION_FAILED", "error": "SSOT not found"}

    conn = get_db_ro()

    # Event type families
    rows = conn.execute("""
        SELECT event_type, COUNT(*) as cnt
        FROM stigmergy_events
        GROUP BY event_type
        ORDER BY cnt DESC
        LIMIT ?
    """, (limit,)).fetchall()

    event_families = {}
    for row in rows:
        et = row["event_type"]
        event_families[et] = row["cnt"]

    # Source distribution in events
    source_rows = conn.execute("""
        SELECT source, COUNT(*) as cnt
        FROM stigmergy_events
        GROUP BY source
        ORDER BY cnt DESC
        LIMIT 20
    """).fetchall()

    event_sources = {row["source"]: row["cnt"] for row in source_rows}

    # Infer port flows from event types
    port_flows = Counter()
    for et in event_families:
        parts = et.lower().split(".")
        ports_found = []
        for part in parts:
            if part.startswith("p") and len(part) == 2 and part[1].isdigit():
                ports_found.append(part.upper())
        if len(ports_found) >= 1:
            port_flows[ports_found[0]] += event_families[et]

    # Recent events timeline (last 50)
    recent = conn.execute("""
        SELECT event_type, timestamp, subject
        FROM stigmergy_events
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()

    conn.close()

    _print("  ┌─── STIGMERGY FLOW MAP ───────────────────────────────┐")
    _print(f"  │ Top {len(event_families)} event type families:")
    _print("  │")
    for et, cnt in list(event_families.items())[:limit]:
        bar_len = min(30, cnt // 50)
        bar = "█" * bar_len if bar_len > 0 else "▏"
        _print(f"  │  {cnt:>5,}  {bar}  {et}")
    _print("  │")
    _print("  │ Port activity (inferred from event types):")
    for port, cnt in port_flows.most_common():
        _print(f"  │  {port}: {cnt:,} events")
    _print("  └─────────────────────────────────────────────────────┘")

    result = {
        "status": "FLOWS_MAPPED",
        "event_families": event_families,
        "event_sources": event_sources,
        "port_flows": dict(port_flows),
        "recent_count": len(recent),
    }

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.astral_projection.flows",
                    f"FLOWS:{len(event_families)}families",
                    {"top_families": dict(list(event_families.items())[:10]),
                     "port_flows": dict(port_flows)})
        conn.close()
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════
# § 4  SPELL: SURVEY — Medallion layer survey
# ═══════════════════════════════════════════════════════════════

def spell_survey(quiet: bool = False) -> dict[str, Any]:
    """
    ASTRAL PROJECTION SURVEY — Survey medallion layers.

    SBE Contract:
      Given  forge directory has 4 medallion layers
      When   spell_survey is cast
      Then   file counts per layer + DB medallion tag distribution reported
    """
    _print = (lambda *a, **k: None) if quiet else print

    # Filesystem counts
    layers = {
        "0_bronze": FORGE_ROOT / "0_bronze",
        "1_silver": FORGE_ROOT / "1_silver",
        "2_gold": FORGE_ROOT / "2_gold",
        "3_hyper_fractal_obsidian": FORGE_ROOT / "3_hyper_fractal_obsidian",
    }

    fs_counts = {}
    for layer_name, layer_path in layers.items():
        if layer_path.exists():
            file_count = sum(1 for f in layer_path.rglob("*") if f.is_file())
            dir_count = sum(1 for d in layer_path.rglob("*") if d.is_dir())
            fs_counts[layer_name] = {"files": file_count, "dirs": dir_count}
        else:
            fs_counts[layer_name] = {"files": 0, "dirs": 0}

    # DB medallion distribution
    db_medallions = {}
    if SSOT_DB.exists():
        try:
            conn = get_db_ro()
            rows = conn.execute("""
                SELECT COALESCE(medallion, 'NULL') as medallion,
                       COUNT(*) as cnt, SUM(word_count) as words
                FROM documents
                GROUP BY medallion
            """).fetchall()
            for row in rows:
                db_medallions[row["medallion"]] = {
                    "docs": row["cnt"],
                    "words": row["words"] or 0,
                }
            conn.close()
        except Exception:
            pass

    _print("  ┌─── MEDALLION SURVEY ─────────────────────────────────┐")
    _print("  │")
    _print("  │ Filesystem layers:")
    for layer, counts in fs_counts.items():
        icon = {"0_bronze": "🥉", "1_silver": "🥈", "2_gold": "🥇",
                "3_hyper_fractal_obsidian": "💎"}.get(layer, " ")
        _print(f"  │  {icon} {layer:<35s} {counts['files']:>4} files  {counts['dirs']:>3} dirs")
    _print("  │")
    _print("  │ SSOT medallion tags:")
    for med, info in db_medallions.items():
        _print(f"  │  {med:<15s} {info['docs']:>6,} docs  {info['words']:>9,} words")
    _print("  │")
    _print("  └─────────────────────────────────────────────────────┘")

    result = {
        "status": "SURVEYED",
        "filesystem": fs_counts,
        "ssot_medallions": db_medallions,
    }

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.astral_projection.survey",
                    f"SURVEY:medallion_layers",
                    {"filesystem": fs_counts, "ssot_medallions": db_medallions})
        conn.close()
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════
# § 5  SPELL: TAXONOMY — Document type breakdown
# ═══════════════════════════════════════════════════════════════

def spell_taxonomy(quiet: bool = False) -> dict[str, Any]:
    """
    ASTRAL PROJECTION TAXONOMY — Enumerate all document types.

    SBE Contract:
      Given  documents have doc_type field
      When   spell_taxonomy is cast
      Then   all doc_types listed with counts, sorted by frequency
    """
    _print = (lambda *a, **k: None) if quiet else print

    if not SSOT_DB.exists():
        return {"status": "PROJECTION_FAILED", "error": "SSOT not found"}

    conn = get_db_ro()
    rows = conn.execute("""
        SELECT COALESCE(doc_type, 'NULL') as doc_type,
               COUNT(*) as cnt, SUM(word_count) as words
        FROM documents
        GROUP BY doc_type
        ORDER BY cnt DESC
    """).fetchall()
    conn.close()

    taxonomy = {}
    for row in rows:
        taxonomy[row["doc_type"]] = {"docs": row["cnt"], "words": row["words"] or 0}

    _print("  ┌─── DOCUMENT TAXONOMY ────────────────────────────────┐")
    for dt, info in taxonomy.items():
        _print(f"  │ {dt:<40s} {info['docs']:>5,} docs  {info['words']:>8,} words")
    _print(f"  │ {'TOTAL':<40s} {sum(v['docs'] for v in taxonomy.values()):>5,} docs")
    _print("  └─────────────────────────────────────────────────────┘")

    result = {"status": "TAXONOMY_MAPPED", "taxonomy": taxonomy}

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.astral_projection.taxonomy",
                    f"TAXONOMY:{len(taxonomy)}types",
                    {"taxonomy_summary": {k: v["docs"] for k, v in taxonomy.items()}})
        conn.close()
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════
# § 6  SPELL: TIMELINE — Temporal analysis
# ═══════════════════════════════════════════════════════════════

def spell_timeline(quiet: bool = False) -> dict[str, Any]:
    """
    ASTRAL PROJECTION TIMELINE — Monthly document creation histogram.

    SBE Contract:
      Given  documents span 2025-01 → 2026-02
      When   spell_timeline is cast
      Then   monthly document counts + event counts generated
    """
    _print = (lambda *a, **k: None) if quiet else print

    if not SSOT_DB.exists():
        return {"status": "PROJECTION_FAILED", "error": "SSOT not found"}

    conn = get_db_ro()

    # Document timeline (from metadata_json or timestamp fields)
    # Use stigmergy event timestamps as primary timeline
    event_months = conn.execute("""
        SELECT SUBSTR(timestamp, 1, 7) as month, COUNT(*) as cnt
        FROM stigmergy_events
        WHERE timestamp IS NOT NULL AND timestamp != ''
        GROUP BY month
        ORDER BY month
    """).fetchall()

    conn.close()

    timeline = {}
    for row in event_months:
        timeline[row["month"]] = row["cnt"]

    _print("  ┌─── TEMPORAL TIMELINE ────────────────────────────────┐")
    _print("  │ Stigmergy events by month:")
    _print("  │")
    max_cnt = max(timeline.values()) if timeline else 1
    for month, cnt in sorted(timeline.items()):
        bar_len = int(40 * cnt / max_cnt)
        bar = "█" * bar_len
        _print(f"  │ {month}  {cnt:>5,}  {bar}")
    _print("  └─────────────────────────────────────────────────────┘")

    result = {"status": "TIMELINE_MAPPED", "event_timeline": timeline}

    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.astral_projection.timeline",
                    f"TIMELINE:{len(timeline)}months",
                    {"event_timeline": timeline})
        conn.close()
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════
# § 7  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "=" * 64)
    print("  P7 SPIDER SOVEREIGN — ASTRAL PROJECTION")
    print("  Summoner of Seals and Spheres — Aspect B: SPHERES")
    print("  " + "-" * 64)
    print("  Necromancy 9th — PHB p.201 — see all crystal spheres at once")
    print("  The Cosmic Descryer maps the multiverse.")
    print("  " + "=" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — ASTRAL_PROJECTION Spell (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Spells:
  project     Full SSOT topology map (port × source matrix)
  flows       Stigmergy event flow analysis
  survey      Medallion layer survey (filesystem + DB)
  taxonomy    Document type breakdown
  timeline    Monthly event histogram

Examples:
  python hfo_p7_astral_projection.py project
  python hfo_p7_astral_projection.py flows
  python hfo_p7_astral_projection.py survey
  python hfo_p7_astral_projection.py taxonomy
  python hfo_p7_astral_projection.py timeline
  python hfo_p7_astral_projection.py --json project
""",
    )
    parser.add_argument("spell", choices=["project", "flows", "survey", "taxonomy", "timeline"],
                        help="Spell variant")
    parser.add_argument("--limit", type=int, default=20,
                        help="Max event families for flows (default: 20)")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    _print_banner()

    if args.spell == "project":
        result = spell_project()
    elif args.spell == "flows":
        result = spell_flows(limit=args.limit)
    elif args.spell == "survey":
        result = spell_survey()
    elif args.spell == "taxonomy":
        result = spell_taxonomy()
    elif args.spell == "timeline":
        result = spell_timeline()
    else:
        result = {"error": "Unknown spell"}

    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
