#!/usr/bin/env python3
"""
hfo_p7_foresight.py — P7 Spider Sovereign FORESIGHT Spell (Gen89)
=====================================================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | 9th-Level Spell: FORESIGHT

PURPOSE:
    Belief Space Foresight — maps the H-POMDP state-action landscape of the
    entire HFO system across all 13 Meadows leverage levels (L1-L13).

    TREMORSENSE feels vibrations in the web.
    FORESIGHT sees where they lead.

    Generates:
      1. Directed graph of Meadows leverage flows (nodes = levels, edges = event transitions)
      2. Mermaid markdown for static rendering (default output)
      3. L13 holonarchy enforcement report (identity violations)
      4. CloudEvent audit report to SSOT

    NOTE: PyVis / Plotly HTML visualization planned for v2.

FORMAL DECISION THEORY:
    - H-POMDP Belief Space Reachability Graph
    - JADC2 Common Operating Picture (COP) at Meadows leverage level
    - Belief simplex visualization where each dimension = a Meadows demiplane

THE 13 DEMIPLANES:
    L1  Parameters      — Material Plane (constants, config)
    L2  Buffers          — The Threshold (sizes, capacity)
    L3  Structure        — The Architecture (topology, layout)
    L4  Delays           — The Hourglass (timing, hysteresis)
    L5  Negative Feedback — The Dampener (rules enforcement, gates)
    L6  Information Flows — The Whispering Gallery (stigmergy, routing)
    L7  Positive Feedback — The Amplifier (compounding, spirals)
    L8  Rules            — The Iron Court (governance, fail-closed)
    L9  Self-Organization — The Living Forge (evolution, autopoiesis)
    L10 Goals            — The Throne Room (north star, mission)
    L11 Paradigm         — The Mindscape (framework shifts)
    L12 Transcendence    — The Unnameable Void (meta-architecture)
    L13 Incarnation      — The Divine Mirror (epistemic identity, holonarchy)

    L13 is NOT a 13th node. It is the CONTAINER — the outermost boundary
    that makes L1-L12 coherent. In the graph, L13 is rendered as the
    enclosing halo/boundary, not as a peer node.

P7 NAVIGATE workflow: MAP → LATTICE → PRUNE → SELECT → DISPATCH → VISUALIZE

USAGE:
    python hfo_p7_foresight.py                      # Mermaid graph (default)
    python hfo_p7_foresight.py --hours 24           # Last 24 hours
    python hfo_p7_foresight.py --text               # ASCII text report
    python hfo_p7_foresight.py --json               # JSON report
    python hfo_p7_foresight.py --daemon             # Hourly loop
    python hfo_p7_foresight.py --history            # Past map reports

Core Thesis: "TREMORSENSE feels the vibrations. FORESIGHT sees where they lead."
Pointer key: p7.foresight
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import signal
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
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


# ═══════════════════════════════════════════════════════════════
# § 1  CONSTANTS & MEADOWS TAXONOMY
# ═══════════════════════════════════════════════════════════════

GEN          = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG   = f"hfo_p7_cartography_gen{GEN}"
EVT_MAP      = f"hfo.gen{GEN}.p7.cartography.map"
EVT_ALERT    = f"hfo.gen{GEN}.p7.cartography.alert"
CORE_THESIS  = "TREMORSENSE feels the vibrations. FORESIGHT sees where they lead."

# ── The 13 Meadows Demiplanes ──────────────────────────────────

@dataclass
class Demiplane:
    level: int
    name: str
    demiplane_name: str
    color: str          # for visualization
    timescale: str
    danger: str
    event_patterns: list  # regex patterns that match events at this level

DEMIPLANES: list[Demiplane] = [
    Demiplane(1,  "Parameters",        "Material Plane",       "#90CAF9", "T0: 10 min",   "Minimal",
              [r"config[_.]change", r"threshold[_.]", r"parameter[_.]", r"param_set"]),
    Demiplane(2,  "Buffers",           "The Threshold",        "#80DEEA", "T1: 1 hour",   "Tuning",
              [r"ssot[_.]write", r"queue[_.]", r"capacity[_.]", r"buffer[_.]"]),
    Demiplane(3,  "Structure",         "The Architecture",     "#A5D6A7", "T1: 1 hour",   "Engineering",
              [r"daemon[_.]start", r"daemon[_.]stop", r"schema[_.]", r"file[_.]create",
               r"structural[_.]", r"topology[_.]"]),
    Demiplane(4,  "Delays",            "The Hourglass",        "#C5E1A5", "T2: 1 day",    "Diagnostic",
              [r"cooldown[_.]", r"timer[_.]", r"hysteresis[_.]", r"delay[_.]", r"dwell[_.]"]),
    Demiplane(5,  "Negative Feedback", "The Dampener",         "#FFF59D", "T2: 1 day",    "Tactical",
              [r"gate[_.]block", r"rule[_.]violation", r"budget[_.]", r"medallion[_.]gate",
               r"gate_blocked", r"mutation[_.]score", r"contingency", r"pyre[_.]"]),
    Demiplane(6,  "Information Flows", "The Whispering Gallery","#FFE082", "T3: 1 week",   "Operational",
              [r"stigmergy[_.]", r"search[_.]", r"subscription[_.]", r"perceive",
               r"yield", r"fts[_.]", r"information[_.]", r"prey8[_.]perceive",
               r"prey8[_.]yield", r"tremorsense"]),
    Demiplane(7,  "Positive Feedback", "The Amplifier",        "#FFCC80", "T3: 1 week",   "Tactical",
              [r"spike[_.]", r"compound[_.]", r"spiral[_.]", r"splendor",
               r"strife", r"amplif", r"reinforce"]),
    Demiplane(8,  "Rules",             "The Iron Court",       "#EF9A9A", "T4: 1 month",  "Architectural",
              [r"fail[_.]closed", r"governance[_.]", r"decree[_.]", r"invariant[_.]",
               r"rule[_.]change", r"prey8[_.]react"]),
    Demiplane(9,  "Self-Organization", "The Living Forge",     "#CE93D8", "T5: 1 quarter","Structural",
              [r"capability[_.]", r"evolution[_.]", r"autopoietic[_.]", r"chimera[_.]",
               r"self[_.]org", r"emergence", r"prey8[_.]execute"]),
    Demiplane(10, "Goals",             "The Throne Room",      "#B39DDB", "T6: 1 year",   "Strategic",
              [r"mission[_.]", r"north[_.]star", r"goal[_.]", r"thread[_.]update",
               r"braided[_.]"]),
    Demiplane(11, "Paradigm",          "The Mindscape",        "#9FA8DA", "T7: 10 years", "Civilizational",
              [r"paradigm[_.]", r"framework[_.]shift", r"shift[_.]"]),
    Demiplane(12, "Transcendence",     "The Unnameable Void",  "#F48FB1", "T8: 100 years","Existential",
              [r"meta[_.]arch", r"transcend", r"beyond[_.]", r"void[_.]"]),
]

# L13 is the holonarchy container — not a node
L13_INCARNATION = Demiplane(
    13, "Incarnation", "The Divine Mirror", "#FFD700", "8^∞", "Asymptotic",
    [r"identity[_.]", r"incarnation[_.]", r"epistemic[_.]", r"holonarchy[_.]",
     r"blood[_.]oath", r"divine[_.]"]
)

# ── Port Identity Anchors (L13 enforcement) ──────────────────

PORT_IDENTITY: dict[str, dict] = {
    "P0": {"cmd": "Lidless Legion",    "anchor": "Sense everything; trust nothing without provenance",
           "violation": "accepting data without evidence"},
    "P1": {"cmd": "Web Weaver",        "anchor": "If it crosses a boundary, it validates",
           "violation": "unbridged data flows"},
    "P2": {"cmd": "Mirror Magus",      "anchor": "Constrain before anyone sees it",
           "violation": "unconstrained creation without spec"},
    "P3": {"cmd": "Harmonic Hydra",    "anchor": "Trace + rollback, or nothing",
           "violation": "untraceable delivery"},
    "P4": {"cmd": "Red Regnant",       "anchor": "Break it before the enemy does — TEST FIRST",
           "violation": "code creation without prior test/spec"},
    "P5": {"cmd": "Pyre Praetorian",   "anchor": "No bypass, no exception, fail closed",
           "violation": "open gates, bypassed checks"},
    "P6": {"cmd": "Kraken Keeper",     "anchor": "If it's not in the DB, it didn't happen",
           "violation": "unrecorded actions"},
    "P7": {"cmd": "Spider Sovereign",  "anchor": "One decision per turn, explicit uncertainty",
           "violation": "ambiguous multi-decisions"},
}

# ── Source tag → Port mapping ─────────────────────────────────

SOURCE_PORT_MAP: dict[str, str] = {
    "singer":      "P4",
    "p4":          "P4",
    "red_regnant": "P4",
    "p5":          "P5",
    "pyre":        "P5",
    "p6":          "P6",
    "kraken":      "P6",
    "p7":          "P7",
    "spider":      "P7",
    "orchestrat":  "P7",
    "tremorsense": "P7",
    "cartograph":  "P7",
    "p2":          "P2",
    "mirror":      "P2",
    "chimera":     "P2",
    "p3":          "P3",
    "harmonic":    "P3",
    "hydra":       "P3",
    "p0":          "P0",
    "lidless":     "P0",
    "p1":          "P1",
    "weaver":      "P1",
    "meadows":     "P7",
    "resource":    "INFRA",
    "npu":         "INFRA",
    "embedder":    "INFRA",
    "prey8":       "MULTI",
}

# Commander native planes (from Doc 422)
COMMANDER_NATIVE_PLANES: dict[str, list[int]] = {
    "P0": [5, 6, 7],
    "P1": [3, 4, 5, 6],
    "P2": [6, 7, 8, 9],
    "P3": [3, 4, 5],
    "P4": [6, 7, 8, 9, 10],
    "P5": [7, 8, 9],
    "P6": [1, 2, 3, 4, 5, 6],
    "P7": list(range(1, 13)),  # all planes
}


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
# § 3  EVENT CLASSIFICATION ENGINE (MAP step)
# ═══════════════════════════════════════════════════════════════

@dataclass
class ClassifiedEvent:
    """A stigmergy event classified by Meadows level and port."""
    event_id: int
    event_type: str
    timestamp: str
    source: str
    subject: str
    meadows_level: int
    port: str
    confidence: float  # 0.0 - 1.0


def classify_event(row: sqlite3.Row) -> ClassifiedEvent:
    """Classify a stigmergy event into a Meadows demiplane and port.

    Classification priority:
      1. L13 pattern match (identity/incarnation events)
      2. Event type/subject pattern match against demiplane regex
      3. Source tag → port → commander native planes (default level)
    """
    evt_type = (row["event_type"] or "").lower()
    subject  = (row["subject"] or "").lower()
    source   = (row["source"] or "").lower()
    text     = f"{evt_type} {subject} {source}"

    # ── Determine port from source ─────────────────────────────
    port = "?"
    for key, p in SOURCE_PORT_MAP.items():
        if key in source:
            port = p
            break

    # Also check event_type for agent_id hints
    if "p4_red_regnant" in text or "red_regnant" in text:
        port = "P4"
    elif "p7_spider_sovereign" in text or "spider_sovereign" in text:
        port = "P7"
    elif "p2_mirror_magus" in text:
        port = "P2"
    elif "p5_pyre" in text:
        port = "P5"
    elif "p6_kraken" in text:
        port = "P6"

    # ── Check L13 first ────────────────────────────────────────
    for pattern in L13_INCARNATION.event_patterns:
        if re.search(pattern, text):
            return ClassifiedEvent(
                event_id=row["id"], event_type=row["event_type"],
                timestamp=row["timestamp"], source=row["source"],
                subject=row["subject"] or "", meadows_level=13,
                port=port, confidence=0.8,
            )

    # ── Check L1-L12 ──────────────────────────────────────────
    best_level = 0
    best_confidence = 0.0
    for dp in DEMIPLANES:
        for pattern in dp.event_patterns:
            if re.search(pattern, text):
                # Higher-level matches get higher confidence
                confidence = 0.5 + (dp.level / 24.0)
                if confidence > best_confidence:
                    best_level = dp.level
                    best_confidence = confidence
                break

    # ── PREY8 event special classification ─────────────────────
    if best_level == 0:
        if "perceive" in evt_type:
            best_level, best_confidence = 6, 0.7
        elif "react" in evt_type:
            best_level, best_confidence = 8, 0.7
        elif "execute" in evt_type:
            best_level, best_confidence = 9, 0.7
        elif "yield" in evt_type:
            best_level, best_confidence = 6, 0.7
        elif "heartbeat" in evt_type:
            best_level, best_confidence = 3, 0.6
        elif "health" in evt_type or "snapshot" in evt_type:
            best_level, best_confidence = 6, 0.6
        elif "time_stop" in evt_type:
            best_level, best_confidence = 6, 0.7
        elif "gate_block" in evt_type or "tamper" in evt_type:
            best_level, best_confidence = 5, 0.8
        elif "memory_loss" in evt_type:
            best_level, best_confidence = 5, 0.7
        elif "tremorsense" in evt_type:
            best_level, best_confidence = 6, 0.7
        elif "alert" in evt_type:
            best_level, best_confidence = 5, 0.7

    # ── Fallback: port native planes ───────────────────────────
    if best_level == 0 and port in COMMANDER_NATIVE_PLANES:
        native = COMMANDER_NATIVE_PLANES[port]
        best_level = native[len(native) // 2]  # median native plane
        best_confidence = 0.3

    # ── Default to L6 (information flows) ──────────────────────
    if best_level == 0:
        best_level = 6
        best_confidence = 0.2

    return ClassifiedEvent(
        event_id=row["id"], event_type=row["event_type"],
        timestamp=row["timestamp"], source=row["source"],
        subject=row["subject"] or "", meadows_level=best_level,
        port=port, confidence=best_confidence,
    )


# ═══════════════════════════════════════════════════════════════
# § 4  GRAPH BUILDER (LATTICE + PRUNE steps)
# ═══════════════════════════════════════════════════════════════

@dataclass
class MeadowsNode:
    level: int
    name: str
    demiplane: str
    color: str
    event_count: int = 0
    ports_active: set = field(default_factory=set)
    latest_event: str = ""
    avg_confidence: float = 0.0

@dataclass
class MeadowsEdge:
    source_level: int
    target_level: int
    weight: int = 0         # number of transitions observed
    ports: set = field(default_factory=set)
    latest_ts: str = ""

@dataclass
class IdentityViolation:
    port: str
    commander: str
    violation_type: str
    event_id: int
    event_type: str
    timestamp: str
    detail: str


def build_graph(
    events: list[ClassifiedEvent],
) -> tuple[dict[int, MeadowsNode], list[MeadowsEdge], list[IdentityViolation]]:
    """Build the Meadows leverage graph from classified events.

    Returns: (nodes, edges, violations)
    """
    # ── Build nodes ────────────────────────────────────────────
    nodes: dict[int, MeadowsNode] = {}
    for dp in DEMIPLANES:
        nodes[dp.level] = MeadowsNode(
            level=dp.level, name=dp.name,
            demiplane=dp.demiplane_name, color=dp.color,
        )
    # L13 as special node
    nodes[13] = MeadowsNode(
        level=13, name=L13_INCARNATION.name,
        demiplane=L13_INCARNATION.demiplane_name,
        color=L13_INCARNATION.color,
    )

    # ── Populate nodes ─────────────────────────────────────────
    confidences: dict[int, list[float]] = defaultdict(list)
    for evt in events:
        lvl = evt.meadows_level
        if lvl in nodes:
            nodes[lvl].event_count += 1
            if evt.port != "?":
                nodes[lvl].ports_active.add(evt.port)
            nodes[lvl].latest_event = max(nodes[lvl].latest_event, evt.timestamp)
            confidences[lvl].append(evt.confidence)

    for lvl, confs in confidences.items():
        if confs and lvl in nodes:
            nodes[lvl].avg_confidence = sum(confs) / len(confs)

    # ── Build edges (temporal transitions) ─────────────────────
    edge_map: dict[tuple[int, int], MeadowsEdge] = {}
    sorted_events = sorted(events, key=lambda e: e.timestamp)

    for i in range(1, len(sorted_events)):
        prev = sorted_events[i - 1]
        curr = sorted_events[i]
        if prev.meadows_level == curr.meadows_level:
            continue  # skip self-loops for clarity
        key = (prev.meadows_level, curr.meadows_level)
        if key not in edge_map:
            edge_map[key] = MeadowsEdge(
                source_level=prev.meadows_level,
                target_level=curr.meadows_level,
            )
        edge = edge_map[key]
        edge.weight += 1
        if curr.port != "?":
            edge.ports.add(curr.port)
        edge.latest_ts = max(edge.latest_ts, curr.timestamp)

    edges = list(edge_map.values())

    # ── L13 Holonarchy Enforcement ─────────────────────────────
    violations: list[IdentityViolation] = []
    violations.extend(_check_p4_identity(events))
    violations.extend(_check_gate_violations(events))

    return nodes, edges, violations


def _check_p4_identity(events: list[ClassifiedEvent]) -> list[IdentityViolation]:
    """Check if P4 Red Regnant has execute events without prior react (test-first).

    L13 enforcement: P4's identity IS 'test before build.' An execute without
    a preceding react/spec is an identity violation, not just a rule violation.
    """
    violations = []
    p4_events = [e for e in events if e.port == "P4"]
    saw_react = False
    for evt in sorted(p4_events, key=lambda e: e.timestamp):
        if "react" in evt.event_type.lower():
            saw_react = True
        elif "execute" in evt.event_type.lower():
            if not saw_react:
                violations.append(IdentityViolation(
                    port="P4", commander="Red Regnant",
                    violation_type="L13_IDENTITY: execute without prior react/spec",
                    event_id=evt.event_id, event_type=evt.event_type,
                    timestamp=evt.timestamp,
                    detail="P4 Red Regnant identity: 'Break it before the enemy does — TEST FIRST.' "
                           "An execute tile was found without a preceding react (spec) tile in this window."
                ))
            saw_react = False  # reset after each execute
    return violations


def _check_gate_violations(events: list[ClassifiedEvent]) -> list[IdentityViolation]:
    """Check for gate blocks and memory losses as L13 violations."""
    violations = []
    for evt in events:
        if "gate_block" in evt.event_type.lower():
            violations.append(IdentityViolation(
                port=evt.port, commander=PORT_IDENTITY.get(evt.port, {}).get("cmd", "?"),
                violation_type="L5/L13: gate block (structural enforcement failure)",
                event_id=evt.event_id, event_type=evt.event_type,
                timestamp=evt.timestamp,
                detail="A gate block means the agent failed to supply required structured fields. "
                       "This is both an L5 rule violation and an L13 identity coherence failure."
            ))
        elif "memory_loss" in evt.event_type.lower():
            violations.append(IdentityViolation(
                port=evt.port, commander="System",
                violation_type="L13_IDENTITY: memory loss (cognitive persistence failure)",
                event_id=evt.event_id, event_type=evt.event_type,
                timestamp=evt.timestamp,
                detail="Memory loss = broken nonce chain = session knowledge vanished. "
                       "The identity of the system cannot persist through amnesia."
            ))
    return violations


# ═══════════════════════════════════════════════════════════════
# § 5  MERMAID RENDERER
# ═══════════════════════════════════════════════════════════════

def render_mermaid(
    nodes: dict[int, MeadowsNode],
    edges: list[MeadowsEdge],
    violations: list[IdentityViolation],
    hours: float,
    total_events: int,
) -> str:
    """Render the Meadows landscape as a Mermaid graph."""
    lines = [
        "```mermaid",
        "graph TD",
        f"  %% FORESIGHT — Meadows Leverage Landscape ({hours}h window, {total_events} events)",
        "  %% Generated by P7 Spider Sovereign",
        "",
    ]

    # ── L13 Container ──────────────────────────────────────────
    lines.append("  subgraph L13_INCARNATION [\"✦ L13 INCARNATION — The Divine Mirror ✦\"]")
    lines.append("    direction TB")
    lines.append("")

    # ── High leverage subgraph (L8-L12) ────────────────────────
    lines.append("    subgraph HIGH [\"High Leverage (L8-L12)\"]")
    lines.append("      direction LR")
    for lvl in range(12, 7, -1):
        n = nodes.get(lvl)
        if n:
            count_str = f"({n.event_count})" if n.event_count > 0 else "(0)"
            ports_str = ",".join(sorted(n.ports_active)) if n.ports_active else "—"
            lines.append(f"      L{lvl}[\"L{lvl} {n.name}\\n{count_str} events\\n{ports_str}\"]")
    lines.append("    end")
    lines.append("")

    # ── Mid leverage subgraph (L4-L7) ──────────────────────────
    lines.append("    subgraph MID [\"Mid Leverage (L4-L7)\"]")
    lines.append("      direction LR")
    for lvl in range(7, 3, -1):
        n = nodes.get(lvl)
        if n:
            count_str = f"({n.event_count})" if n.event_count > 0 else "(0)"
            ports_str = ",".join(sorted(n.ports_active)) if n.ports_active else "—"
            lines.append(f"      L{lvl}[\"L{lvl} {n.name}\\n{count_str} events\\n{ports_str}\"]")
    lines.append("    end")
    lines.append("")

    # ── Low leverage subgraph (L1-L3) ──────────────────────────
    lines.append("    subgraph LOW [\"Low Leverage (L1-L3) ⚠ Attractor Basin\"]")
    lines.append("      direction LR")
    for lvl in range(3, 0, -1):
        n = nodes.get(lvl)
        if n:
            count_str = f"({n.event_count})" if n.event_count > 0 else "(0)"
            ports_str = ",".join(sorted(n.ports_active)) if n.ports_active else "—"
            lines.append(f"      L{lvl}[\"L{lvl} {n.name}\\n{count_str} events\\n{ports_str}\"]")
    lines.append("    end")
    lines.append("")

    # ── Edges ──────────────────────────────────────────────────
    # Only show edges with weight > 1 for clarity, or if few edges
    threshold = 1 if len(edges) < 30 else 2
    significant_edges = sorted(edges, key=lambda e: e.weight, reverse=True)[:30]
    for e in significant_edges:
        if e.weight >= threshold:
            arrow = "==>" if e.weight >= 5 else "-->"
            label = f"|{e.weight}x|"
            lines.append(f"    L{e.source_level} {arrow} {label} L{e.target_level}")

    lines.append("  end")
    lines.append("")

    # ── Styling ────────────────────────────────────────────────
    for lvl, n in nodes.items():
        if n.event_count > 0 and lvl <= 12:
            lines.append(f"  style L{lvl} fill:{n.color},stroke:#333,stroke-width:2px")
        elif lvl <= 12:
            lines.append(f"  style L{lvl} fill:#eee,stroke:#999,stroke-width:1px,stroke-dasharray: 5 5")

    lines.append(f"  style L13_INCARNATION fill:#FFF8E1,stroke:#FFD700,stroke-width:3px")
    lines.append(f"  style HIGH fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px")
    lines.append(f"  style MID fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px")
    lines.append(f"  style LOW fill:#FFEBEE,stroke:#C62828,stroke-width:2px")

    lines.append("```")

    # ── Violations ─────────────────────────────────────────────
    if violations:
        lines.append("")
        lines.append(f"### ⚠ L13 Holonarchy Violations ({len(violations)})")
        for v in violations[:10]:
            lines.append(f"- **{v.port} {v.commander}**: {v.violation_type}")
            lines.append(f"  Event {v.event_id} at {v.timestamp[:19]}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 6  (RESERVED — PyVis / Plotly HTML renderer, planned for v2)
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# § 7  CARTOGRAPHY ENGINE (main orchestration)
# ═══════════════════════════════════════════════════════════════

@dataclass
class CartographyReport:
    window_hours: float
    total_events: int
    classified_events: int
    active_levels: list[int]
    cold_levels: list[int]
    hottest_level: int
    hottest_count: int
    violations: list[dict]
    level_distribution: dict[int, int]
    port_distribution: dict[str, int]
    edge_count: int
    dominant_flow: str
    l13_status: str
    attractor_basin_pct: float  # % of events in L1-L3
    high_leverage_pct: float    # % of events in L8-L12
    timestamp: str


def run_cartography(hours: float = 1.0) -> tuple[CartographyReport, dict[int, MeadowsNode], list[MeadowsEdge], list[IdentityViolation]]:
    """Execute the full FORESIGHT spell.

    MAP → LATTICE → PRUNE → SELECT → DISPATCH → VISUALIZE
    """
    conn = get_db_ro()
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)

    # ── MAP: Scan stigmergy events ─────────────────────────────
    rows = conn.execute(
        """SELECT id, event_type, timestamp, source, subject, data_json
           FROM stigmergy_events
           WHERE timestamp >= ?
           ORDER BY timestamp ASC""",
        (window_start.isoformat(),),
    ).fetchall()
    conn.close()

    total_events = len(rows)

    # ── LATTICE: Classify each event ───────────────────────────
    classified: list[ClassifiedEvent] = []
    for row in rows:
        classified.append(classify_event(row))

    # ── PRUNE: Build graph ─────────────────────────────────────
    nodes, edges, violations = build_graph(classified)

    # ── SELECT: Analyze ────────────────────────────────────────
    level_dist: dict[int, int] = {}
    port_dist: Counter = Counter()
    for evt in classified:
        level_dist[evt.meadows_level] = level_dist.get(evt.meadows_level, 0) + 1
        if evt.port != "?":
            port_dist[evt.port] += 1

    active_levels = [lvl for lvl, count in level_dist.items() if count > 0]
    cold_levels = [lvl for lvl in range(1, 14) if lvl not in active_levels]

    hottest = max(level_dist.items(), key=lambda x: x[1]) if level_dist else (0, 0)

    # Attractor basin analysis
    low_events = sum(level_dist.get(lvl, 0) for lvl in [1, 2, 3])
    high_events = sum(level_dist.get(lvl, 0) for lvl in range(8, 13))
    total_classified = len(classified)
    attractor_basin_pct = (low_events / total_classified * 100) if total_classified > 0 else 0
    high_leverage_pct = (high_events / total_classified * 100) if total_classified > 0 else 0

    # Dominant flow
    dominant_edge = max(edges, key=lambda e: e.weight) if edges else None
    dominant_flow = (
        f"L{dominant_edge.source_level}→L{dominant_edge.target_level} ({dominant_edge.weight}x)"
        if dominant_edge else "no transitions"
    )

    # L13 holonarchy status
    if not violations:
        l13_status = "COHERENT — no identity violations detected"
    elif len(violations) <= 3:
        l13_status = f"STRESSED — {len(violations)} minor violations"
    else:
        l13_status = f"FRACTURED — {len(violations)} violations (identity under pressure)"

    report = CartographyReport(
        window_hours=hours,
        total_events=total_events,
        classified_events=len(classified),
        active_levels=sorted(active_levels),
        cold_levels=sorted(cold_levels),
        hottest_level=hottest[0],
        hottest_count=hottest[1],
        violations=[asdict(v) for v in violations[:20]],
        level_distribution=level_dist,
        port_distribution=dict(port_dist),
        edge_count=len(edges),
        dominant_flow=dominant_flow,
        l13_status=l13_status,
        attractor_basin_pct=round(attractor_basin_pct, 1),
        high_leverage_pct=round(high_leverage_pct, 1),
        timestamp=now.isoformat(),
    )

    return report, nodes, edges, violations


# ═══════════════════════════════════════════════════════════════
# § 8  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════

def display_text_report(report: CartographyReport) -> str:
    """ASCII text cartography report."""
    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║  ✦ FORESIGHT — Meadows Leverage Landscape ✦                ║",
        "║  P7 Spider Sovereign | Gen89 | NAVIGATE                     ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
        f"  Window:     {report.window_hours}h",
        f"  Events:     {report.total_events} total, {report.classified_events} classified",
        f"  Hottest:    L{report.hottest_level} ({report.hottest_count} events)",
        f"  Active:     L{', L'.join(str(l) for l in report.active_levels)}",
        f"  Cold:       L{', L'.join(str(l) for l in report.cold_levels)}" if report.cold_levels else "  Cold:       none",
        f"  Transitions: {report.edge_count}",
        f"  Dominant:   {report.dominant_flow}",
        "",
        "─── LEVERAGE DISTRIBUTION ─────────────────────────────────────",
        "",
    ]

    # ASCII bar chart
    max_count = max(report.level_distribution.values()) if report.level_distribution else 1
    for lvl in range(13, 0, -1):
        count = report.level_distribution.get(lvl, 0)
        bar_len = int((count / max_count) * 40) if max_count > 0 else 0
        bar = "█" * bar_len + "░" * (40 - bar_len)
        dp = DEMIPLANES[lvl - 1] if lvl <= 12 else L13_INCARNATION
        name = dp.name[:16].ljust(16)
        marker = "✦" if lvl == 13 else " "
        lines.append(f"  {marker}L{lvl:2d} {name} │{bar}│ {count:4d}")

    lines.extend([
        "",
        "─── BELIEF SPACE ANALYSIS ─────────────────────────────────────",
        "",
        f"  Attractor Basin (L1-L3):    {report.attractor_basin_pct:5.1f}%",
        f"  High Leverage (L8-L12):     {report.high_leverage_pct:5.1f}%",
        "",
    ])

    if report.attractor_basin_pct > 50:
        lines.append("  ⚠ ATTRACTOR WARNING: Majority of activity in L1-L3 basin.")
        lines.append("     The system is stuck tweaking parameters, not changing structure.")
    elif report.high_leverage_pct > 40:
        lines.append("  ✓ HIGH LEVERAGE: System operating above the structural threshold.")
    else:
        lines.append("  → MID-RANGE: Mixed leverage activity.")

    lines.extend([
        "",
        "─── L13 HOLONARCHY STATUS ─────────────────────────────────────",
        "",
        f"  Status: {report.l13_status}",
    ])
    if report.violations:
        for v in report.violations[:5]:
            lines.append(f"  ⚠ {v['port']} {v['commander']}: {v['violation_type']}")
    else:
        lines.append("  ✦ All port identities coherent. The divine mirror reflects true.")

    lines.extend([
        "",
        "─── PORT ACTIVITY ─────────────────────────────────────────────",
        "",
    ])
    for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "MULTI", "INFRA"]:
        count = report.port_distribution.get(port, 0)
        if count > 0:
            cmd = PORT_IDENTITY.get(port, {}).get("cmd", port)
            lines.append(f"  {port} {cmd:20s}: {count:4d} events")

    lines.extend([
        "",
        f"  Core Thesis: \"{CORE_THESIS}\"",
        "",
    ])

    return "\n".join(lines)


def display_history(limit: int = 24) -> str:
    """Show past cartography reports from SSOT."""
    conn = get_db_ro()
    rows = conn.execute(
        f"""SELECT id, timestamp, subject, data_json
           FROM stigmergy_events
           WHERE event_type = ?
           ORDER BY timestamp DESC
           LIMIT ?""",
        (EVT_MAP, limit),
    ).fetchall()
    conn.close()

    if not rows:
        return "\n  No cartography reports found in SSOT.\n  Run the script first to generate a report.\n"

    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║  FORESIGHT HISTORY                                          ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
    ]
    for row in rows:
        try:
            envelope = json.loads(row["data_json"])
            data = envelope.get("data", envelope)
        except (json.JSONDecodeError, TypeError):
            data = {}
        ts = row["timestamp"][:19]
        hot = data.get("hottest_level", "?")
        events = data.get("total_events", "?")
        l13_stat = data.get("l13_status", "?")[:40]
        basin = data.get("attractor_basin_pct", "?")
        high = data.get("high_leverage_pct", "?")
        lines.append(f"  [{ts}] L{hot} hottest | {events} events | Basin:{basin}% High:{high}% | {l13_stat}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 9  SSOT WRITER
# ═══════════════════════════════════════════════════════════════

def write_cartography_event(report: CartographyReport) -> int:
    """Write cartography map CloudEvent to SSOT."""
    conn = get_db_rw()
    subject = (
        f"CARTOGRAPHY:L{report.hottest_level}:basin{report.attractor_basin_pct}%:"
        f"high{report.high_leverage_pct}%:{report.window_hours}h"
    )
    data = {
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
        "spell": "FORESIGHT",
        "port": "P7",
        "commander": "Spider Sovereign",
        "core_thesis": CORE_THESIS,
        "p7_workflow": "MAP → LATTICE → PRUNE → SELECT → DISPATCH → VISUALIZE",
    }
    row_id = write_event(conn, EVT_MAP, subject, data)
    conn.close()
    return row_id


# ═══════════════════════════════════════════════════════════════
# § 10  CLI
# ═══════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hfo_p7_foresight",
        description="P7 Spider Sovereign FORESIGHT — Meadows L1-L13 Belief Space Divination",
    )
    p.add_argument("--text", action="store_true", help="ASCII text report instead of Mermaid")
    p.add_argument("--json", action="store_true", help="JSON report to stdout")
    p.add_argument("--hours", type=float, default=1.0, help="Time window in hours (default: 1)")
    p.add_argument("--daemon", action="store_true", help="Hourly cartography daemon loop")
    p.add_argument("--interval", type=int, default=3600, help="Daemon interval in seconds (default: 3600)")
    p.add_argument("--history", nargs="?", const=24, type=int, help="Show past N cartography reports")
    p.add_argument("--no-write", action="store_true", help="Don't write CloudEvent to SSOT")
    return p


def main():
    # Ensure UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args()

    # ── History mode ───────────────────────────────────────────
    if args.history is not None:
        print(display_history(args.history))
        return

    # ── Daemon mode ────────────────────────────────────────────
    if args.daemon:
        print(f"\n  ✦ FORESIGHT DAEMON — hourly ({args.interval}s interval)")
        print(f"  SSOT: {SSOT_DB}")
        print(f"  Window: {args.hours}h")
        print(f"  Press Ctrl+C to stop.\n")

        running = True
        def handle_sig(*_):
            nonlocal running
            running = False
        signal.signal(signal.SIGINT, handle_sig)
        signal.signal(signal.SIGTERM, handle_sig)

        while running:
            try:
                report, nodes, edges, violations = run_cartography(args.hours)
                if not args.no_write:
                    row_id = write_cartography_event(report)
                    print(f"  [{report.timestamp[:19]}] Map written (row {row_id}) | "
                          f"L{report.hottest_level} hottest | "
                          f"basin:{report.attractor_basin_pct}% high:{report.high_leverage_pct}% | "
                          f"L13: {report.l13_status[:30]}")
                else:
                    print(f"  [{report.timestamp[:19]}] Map generated (dry run) | "
                          f"L{report.hottest_level} hottest")

                for _ in range(args.interval):
                    if not running:
                        break
                    time.sleep(1)
            except Exception as e:
                print(f"  ERROR: {e}")
                time.sleep(60)
        print("\n  ✦ FORESIGHT DAEMON stopped.\n")
        return

    # ── One-shot modes ─────────────────────────────────────────
    report, nodes, edges, violations = run_cartography(args.hours)

    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))

    elif args.text:
        print(display_text_report(report))

    else:
        # Default: Mermaid graph
        mermaid_output = render_mermaid(nodes, edges, violations, args.hours, report.total_events)
        print(mermaid_output)

    # ── Write to SSOT ──────────────────────────────────────────
    if not args.no_write:
        row_id = write_cartography_event(report)
        print(f"\n  CloudEvent written to SSOT (row {row_id})")
    else:
        print("\n  (dry run — no SSOT write)")


if __name__ == "__main__":
    main()
