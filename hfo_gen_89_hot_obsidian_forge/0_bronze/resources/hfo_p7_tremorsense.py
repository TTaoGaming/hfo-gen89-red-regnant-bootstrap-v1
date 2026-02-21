#!/usr/bin/env python3
"""
hfo_p7_tremorsense.py — P7 Spider Sovereign TREMORSENSE Spell (Gen89)
======================================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | Minor Spell: TREMORSENSE

PURPOSE:
    Hourly uptime audit that checks per-minute daemon coverage
    via stigmergy receipts ONLY. No AI claims — only CloudEvent
    timestamps in SSOT prove a daemon was alive during a given minute.

    The Spider Sovereign's seismograph: detects vibrations (events)
    through the web (stigmergy). Dead silence = dead zone.

UPTIME CALCULATION:
    For each 1-minute bin in the audit window:
      - COVERED if at least 1 stigmergy event exists with that minute's timestamp
      - DEAD if zero events exist for that minute
    uptime_pct = covered_minutes / total_minutes * 100

    Target: 99% (≤0.6 dead minutes per hour)
    Expected reality: catastrophic failure until 24/7 daemons are deployed

GRADING:
    A+  99.0-100%  (≤0.6 dead min/hr)  — Production grade
    A   95.0-98.9%  (≤3 dead min/hr)    — Near production
    B   90.0-94.9%  (≤6 dead min/hr)    — Developing
    C   75.0-89.9%  (≤15 dead min/hr)   — Work in progress
    D   50.0-74.9%  (≤30 dead min/hr)   — Significant gaps
    F   0.0-49.9%   (>30 dead min/hr)   — Catastrophic

EVENT TYPES:
    hfo.gen89.p7.tremorsense.audit      — Hourly uptime report
    hfo.gen89.p7.tremorsense.heartbeat  — Daemon alive pulse
    hfo.gen89.p7.tremorsense.alert      — Uptime below threshold

P7 NAVIGATE workflow: MAP → LATTICE → PRUNE → SELECT → DISPATCH
    MAP      = scan stigmergy_events for the audit window
    LATTICE  = bucket into 1-minute bins, overlay daemon sources
    PRUNE    = discard duplicate events within same minute-bin
    SELECT   = identify dead zones and worst offenders
    DISPATCH = emit audit report CloudEvent to SSOT

Meadows Level: L6 (Information Flows)
    "You cannot improve what you cannot measure."
    This spell creates the measurement that makes uptime gaps visible.

USAGE:
    python hfo_p7_tremorsense.py --audit              # Audit last hour
    python hfo_p7_tremorsense.py --audit --hours 24   # Audit last 24 hours
    python hfo_p7_tremorsense.py --daemon              # Hourly audit loop
    python hfo_p7_tremorsense.py --history             # Last 24 audit reports
    python hfo_p7_tremorsense.py --history 48          # Last 48 reports
    python hfo_p7_tremorsense.py --json                # Machine-readable audit
    python hfo_p7_tremorsense.py --grid                # ASCII uptime grid (last 24h)

Core Thesis: "The web feels all. Dead silence is the loudest signal."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from hfo_ssot_write import get_db_readwrite as get_db_rw


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
# § 1  CONSTANTS & CONFIG
# ═══════════════════════════════════════════════════════════════

GEN             = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG      = f"hfo_p7_tremorsense_gen{GEN}"
EVT_AUDIT       = f"hfo.gen{GEN}.p7.tremorsense.audit"
EVT_HEARTBEAT   = f"hfo.gen{GEN}.p7.tremorsense.heartbeat"
EVT_ALERT       = f"hfo.gen{GEN}.p7.tremorsense.alert"

# Uptime target
TARGET_UPTIME_PCT = 99.0

# Grading scale
GRADES = [
    (99.0, "A+", "Production grade"),
    (95.0, "A",  "Near production"),
    (90.0, "B",  "Developing"),
    (75.0, "C",  "Work in progress"),
    (50.0, "D",  "Significant gaps"),
    (0.0,  "F",  "Catastrophic"),
]

# Known daemon source tags — what qualifies as "alive" evidence
DAEMON_SOURCES = {
    # source tag → (display name, port, expected interval seconds)
    f"hfo_singer_ai_gen{GEN}":          ("Singer AI",       "P4", 60),
    f"hfo_singer_daemon_gen{GEN}":      ("Singer Classic",  "P4", 60),
    f"hfo_p6_kraken_swarm_gen{GEN}":    ("Kraken Swarm",    "P6", 65),
    f"hfo_p5_daemon_gen{GEN}":          ("Pyre Praetorian", "P5", 60),
    f"hfo_p5_pyre_gen{GEN}":            ("Pyre Guardian",   "P5", 60),
    f"hfo_meadows_engine_gen{GEN}":     ("Meadows Engine",  "L5", 300),
    f"hfo_p7_orchestrator_gen{GEN}_v1.0": ("P7 Orchestrator", "P7", 3600),
    f"hfo_p7_tremorsense_gen{GEN}":     ("Tremorsense",     "P7", 3600),
    f"hfo_p2_chimera_gen{GEN}":         ("Chimera Loop",    "P2", 300),
    f"hfo_resource_gov_gen{GEN}":       ("Resource Gov",    "INFRA", 60),
    f"hfo_npu_embedder_gen{GEN}":       ("NPU Embedder",    "INFRA", 120),
}

# Additional event-type patterns that count as "alive" (catch-all for unknown daemons)
ALIVE_EVENT_PATTERNS = [
    "heartbeat", "strife", "splendor", "health", "snapshot",
    "time_stop", "swarm.", "kraken.", "singer.", "p5.", "p7.",
    "meadows.", "chimera.", "resource.", "embedder.",
    "perceive", "react", "execute", "yield",
]

CORE_THESIS = "The web feels all. Dead silence is the loudest signal."


# ═══════════════════════════════════════════════════════════════
# § 2  DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_ro() -> sqlite3.Connection:
    """Read-only SSOT connection."""
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def write_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
    source: str = SOURCE_TAG,
) -> int:
    """Write CloudEvent to stigmergy_events. Returns rowid."""
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)

    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(
            f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()
        ).hexdigest(),
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(envelope, sort_keys=True).encode()
    ).hexdigest()

    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 3  MINUTE-BUCKET SCANNER (MAP phase)
# ═══════════════════════════════════════════════════════════════

def _minute_key(ts_str: str) -> str:
    """Extract YYYY-MM-DDTHH:MM from a timestamp string."""
    # Handle both ISO formats
    return ts_str[:16]  # "2026-02-19T16:45" — minute-level truncation


def scan_stigmergy_window(
    conn: sqlite3.Connection,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, list[dict]]:
    """Scan stigmergy events in time window, bucket by minute.

    Returns: {minute_key: [event_summaries]}
    """
    start_iso = window_start.isoformat()
    end_iso = window_end.isoformat()

    rows = conn.execute(
        """SELECT id, event_type, timestamp, subject, source
           FROM stigmergy_events
           WHERE timestamp >= ? AND timestamp < ?
           ORDER BY timestamp ASC""",
        (start_iso, end_iso),
    ).fetchall()

    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        mk = _minute_key(row["timestamp"])
        buckets[mk].append({
            "id": row["id"],
            "event_type": row["event_type"],
            "source": row["source"],
            "subject": row["subject"],
        })
    return dict(buckets)


# ═══════════════════════════════════════════════════════════════
# § 4  UPTIME CALCULATION (LATTICE + PRUNE phases)
# ═══════════════════════════════════════════════════════════════

def _generate_minute_keys(start: datetime, end: datetime) -> list[str]:
    """Generate all minute keys between start and end (UTC)."""
    keys = []
    current = start.replace(second=0, microsecond=0)
    while current < end:
        keys.append(current.strftime("%Y-%m-%dT%H:%M"))
        current += timedelta(minutes=1)
    return keys


def grade_uptime(pct: float) -> tuple[str, str]:
    """Return (grade_letter, grade_description) for an uptime percentage."""
    for threshold, letter, desc in GRADES:
        if pct >= threshold:
            return letter, desc
    return "F", "Catastrophic"


def compute_uptime(
    minute_keys: list[str],
    buckets: dict[str, list[dict]],
) -> dict:
    """Compute per-minute uptime from bucketed events.

    Returns comprehensive audit report dict.
    """
    total_minutes = len(minute_keys)
    if total_minutes == 0:
        return {"error": "No minutes in window", "uptime_pct": 0.0}

    covered_minutes = 0
    dead_minutes = 0
    per_minute: list[dict] = []
    daemon_coverage: dict[str, int] = defaultdict(int)  # source → minutes covered
    dead_zones: list[dict] = []
    current_dead_start: Optional[str] = None

    for mk in minute_keys:
        events = buckets.get(mk, [])
        is_covered = len(events) > 0

        if is_covered:
            covered_minutes += 1
            # Track which daemons were responsible
            sources_seen = set()
            for evt in events:
                src = evt.get("source", "unknown")
                if src not in sources_seen:
                    daemon_coverage[src] += 1
                    sources_seen.add(src)
            # Close any open dead zone
            if current_dead_start is not None:
                dead_zones.append({
                    "start": current_dead_start,
                    "end": mk,
                    "duration_min": len([
                        k for k in minute_keys
                        if k >= current_dead_start and k < mk
                    ]),
                })
                current_dead_start = None
        else:
            dead_minutes += 1
            if current_dead_start is None:
                current_dead_start = mk

        per_minute.append({
            "minute": mk,
            "covered": is_covered,
            "event_count": len(events),
        })

    # Close trailing dead zone
    if current_dead_start is not None:
        dead_zones.append({
            "start": current_dead_start,
            "end": minute_keys[-1] + "+1m",
            "duration_min": len([
                k for k in minute_keys if k >= current_dead_start
            ]),
        })

    uptime_pct = (covered_minutes / total_minutes) * 100.0
    grade_letter, grade_desc = grade_uptime(uptime_pct)

    # Daemon leaderboard (sorted by coverage)
    daemon_leaderboard = []
    for src, mins in sorted(daemon_coverage.items(), key=lambda x: -x[1]):
        info = DAEMON_SOURCES.get(src, (src, "?", 0))
        daemon_leaderboard.append({
            "source": src,
            "name": info[0],
            "port": info[1],
            "minutes_covered": mins,
            "coverage_pct": round(mins / total_minutes * 100.0, 1),
        })

    return {
        "total_minutes": total_minutes,
        "covered_minutes": covered_minutes,
        "dead_minutes": dead_minutes,
        "uptime_pct": round(uptime_pct, 2),
        "target_pct": TARGET_UPTIME_PCT,
        "meets_target": uptime_pct >= TARGET_UPTIME_PCT,
        "grade": grade_letter,
        "grade_desc": grade_desc,
        "dead_zones": dead_zones,
        "dead_zone_count": len(dead_zones),
        "longest_dead_zone_min": max(
            (dz["duration_min"] for dz in dead_zones), default=0
        ),
        "daemon_leaderboard": daemon_leaderboard,
        "active_daemon_count": len(daemon_leaderboard),
        "per_minute": per_minute,
    }


# ═══════════════════════════════════════════════════════════════
# § 5  AUDIT REPORT (SELECT + DISPATCH phases)
# ═══════════════════════════════════════════════════════════════

def run_audit(
    hours: int = 1,
    write_to_ssot: bool = True,
) -> dict:
    """Run a full tremorsense audit for the last N hours.

    Returns the audit report dict.
    """
    now = datetime.now(timezone.utc)
    window_end = now
    window_start = now - timedelta(hours=hours)

    # MAP: scan stigmergy
    conn_ro = get_db_ro()
    try:
        buckets = scan_stigmergy_window(conn_ro, window_start, window_end)

        # Also get total event count for context
        total_events = conn_ro.execute(
            "SELECT COUNT(*) FROM stigmergy_events"
        ).fetchone()[0]

        events_in_window = conn_ro.execute(
            """SELECT COUNT(*) FROM stigmergy_events
               WHERE timestamp >= ? AND timestamp < ?""",
            (window_start.isoformat(), window_end.isoformat()),
        ).fetchone()[0]
    finally:
        conn_ro.close()

    # LATTICE + PRUNE: compute uptime
    minute_keys = _generate_minute_keys(window_start, window_end)
    report = compute_uptime(minute_keys, buckets)

    # Enrich with metadata
    report["audit_timestamp"] = now.isoformat()
    report["window_start"] = window_start.isoformat()
    report["window_end"] = window_end.isoformat()
    report["window_hours"] = hours
    report["total_ssot_events"] = total_events
    report["events_in_window"] = events_in_window
    report["source"] = SOURCE_TAG
    report["spell"] = "TREMORSENSE"
    report["port"] = "P7"
    report["commander"] = "Spider Sovereign"
    report["core_thesis"] = CORE_THESIS
    report["p7_workflow"] = "MAP → LATTICE → PRUNE → SELECT → DISPATCH"

    # DISPATCH: write to SSOT
    if write_to_ssot:
        # Write compact version (exclude per_minute from SSOT — too large)
        ssot_report = {k: v for k, v in report.items() if k != "per_minute"}
        ssot_report["per_minute_summary"] = {
            "total": report["total_minutes"],
            "covered": report["covered_minutes"],
            "dead": report["dead_minutes"],
        }

        conn_rw = get_db_rw()
        try:
            grade = report["grade"]
            pct = report["uptime_pct"]
            subject = f"TREMORSENSE:{grade}:{pct}%:{hours}h"

            audit_row = write_event(
                conn_rw, EVT_AUDIT, subject, ssot_report,
            )
            report["ssot_row_id"] = audit_row

            # Emit alert if below target
            if not report["meets_target"]:
                alert_data = {
                    "grade": grade,
                    "uptime_pct": pct,
                    "target_pct": TARGET_UPTIME_PCT,
                    "dead_minutes": report["dead_minutes"],
                    "total_minutes": report["total_minutes"],
                    "longest_dead_zone_min": report["longest_dead_zone_min"],
                    "dead_zone_count": report["dead_zone_count"],
                    "window_hours": hours,
                    "message": (
                        f"UPTIME ALERT: {pct}% < {TARGET_UPTIME_PCT}% target. "
                        f"Grade {grade}. {report['dead_minutes']} dead minutes "
                        f"in {hours}h window. "
                        f"Longest gap: {report['longest_dead_zone_min']}min."
                    ),
                    "core_thesis": CORE_THESIS,
                }
                write_event(
                    conn_rw, EVT_ALERT,
                    f"ALERT:BELOW_TARGET:{grade}:{pct}%",
                    alert_data,
                )
        finally:
            conn_rw.close()

    return report


# ═══════════════════════════════════════════════════════════════
# § 6  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════

def _uptime_bar(pct: float, width: int = 40) -> str:
    """ASCII progress bar for uptime percentage."""
    filled = int(pct / 100. * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:.1f}%"


def _grade_color(grade: str) -> str:
    """Return ANSI color code for grade letter."""
    colors = {
        "A+": "\033[92m",  # bright green
        "A":  "\033[32m",  # green
        "B":  "\033[33m",  # yellow
        "C":  "\033[33m",  # yellow
        "D":  "\033[91m",  # bright red
        "F":  "\033[31m",  # red
    }
    return colors.get(grade, "")


RESET = "\033[0m"


def print_audit_report(report: dict) -> None:
    """Print human-readable audit report to stdout."""
    grade = report.get("grade", "?")
    gc = _grade_color(grade)

    print()
    print("=" * 72)
    print("  P7 SPIDER SOVEREIGN — TREMORSENSE AUDIT")
    print(f"  \"{CORE_THESIS}\"")
    print("=" * 72)
    print()
    print(f"  Window:  {report.get('window_start', '?')[:19]}")
    print(f"       →   {report.get('window_end', '?')[:19]}  ({report.get('window_hours', '?')}h)")
    print()
    print(f"  {gc}GRADE:  {grade}  — {report.get('grade_desc', '')}{RESET}")
    print(f"  UPTIME: {_uptime_bar(report.get('uptime_pct', 0))}")
    print(f"  TARGET: {report.get('target_pct', 99.0)}%  "
          f"{'✓ MET' if report.get('meets_target') else '✗ NOT MET'}")
    print()
    print(f"  Minutes Total:    {report.get('total_minutes', 0)}")
    print(f"  Minutes Covered:  {report.get('covered_minutes', 0)}")
    print(f"  Minutes Dead:     {report.get('dead_minutes', 0)}")
    print(f"  Events in Window: {report.get('events_in_window', 0)}")
    print(f"  Total SSOT Events:{report.get('total_ssot_events', 0)}")
    print()

    # Dead zones
    dead_zones = report.get("dead_zones", [])
    if dead_zones:
        print(f"  DEAD ZONES ({len(dead_zones)} gaps):")
        # Show top 10 longest
        sorted_dz = sorted(dead_zones, key=lambda d: -d.get("duration_min", 0))
        for i, dz in enumerate(sorted_dz[:10]):
            start = dz.get("start", "?")
            end = dz.get("end", "?")
            dur = dz.get("duration_min", 0)
            # Timestamp display — just HH:MM for readability
            s_short = start[11:16] if len(start) >= 16 else start
            e_short = end[11:16] if len(end) >= 16 else end
            print(f"    [{i+1:>2}] {s_short} → {e_short}  ({dur} min)")
        if len(sorted_dz) > 10:
            remaining = len(sorted_dz) - 10
            print(f"    ... and {remaining} more gaps")
    else:
        print("  DEAD ZONES: None — full coverage!")
    print()

    # Daemon leaderboard
    leaders = report.get("daemon_leaderboard", [])
    if leaders:
        print(f"  DAEMON LEADERBOARD ({len(leaders)} active sources):")
        print(f"    {'Source':<40} {'Port':<6} {'Mins':<6} {'Cov%'}")
        print(f"    {'-'*40} {'-'*5} {'-'*5} {'-'*5}")
        for d in leaders[:15]:
            name = d.get("name", d.get("source", "?"))
            port = d.get("port", "?")
            mins = d.get("minutes_covered", 0)
            cov = d.get("coverage_pct", 0)
            print(f"    {name:<40} {port:<6} {mins:<6} {cov:.1f}%")
    else:
        print("  DAEMON LEADERBOARD: No daemons detected in window!")
    print()

    # ASCII minute grid (compact — show 60 chars per hour)
    per_minute = report.get("per_minute", [])
    if per_minute:
        _print_minute_grid(per_minute, report.get("window_hours", 1))

    # SSOT write confirmation
    row_id = report.get("ssot_row_id")
    if row_id:
        print(f"  → Audit report written to SSOT row {row_id}")
    print()
    print("=" * 72)
    print()


def _print_minute_grid(per_minute: list[dict], hours: int) -> None:
    """Print ASCII grid: each char = 1 minute, █=covered, ░=dead."""
    print("  MINUTE-BY-MINUTE GRID (█=alive, ░=dead):")
    print()

    for h in range(hours):
        start_idx = h * 60
        end_idx = min(start_idx + 60, len(per_minute))
        chunk = per_minute[start_idx:end_idx]
        if not chunk:
            break

        hour_label = chunk[0]["minute"][11:13] if chunk else "??"
        chars = ""
        for m in chunk:
            chars += "█" if m["covered"] else "░"

        # Pad to 60 if needed
        chars = chars.ljust(60, " ")

        # Count coverage for this hour
        covered = sum(1 for m in chunk if m["covered"])
        total = len(chunk)
        pct = (covered / total * 100) if total > 0 else 0

        # Grid with 10-min markers
        grid = ""
        for i in range(0, len(chars), 10):
            grid += chars[i:i+10] + "|"

        print(f"    {hour_label}h [{grid}] {covered}/{total} ({pct:.0f}%)")

    # Legend
    print()
    print("    └─ Each char = 1 minute. | = 10-min marker.")
    print()


def print_history(count: int = 24) -> None:
    """Print recent tremorsense audit history."""
    conn = get_db_ro()
    try:
        rows = conn.execute(
            """SELECT id, timestamp, subject, data_json
               FROM stigmergy_events
               WHERE event_type = ?
               ORDER BY id DESC LIMIT ?""",
            (EVT_AUDIT, count),
        ).fetchall()
    finally:
        conn.close()

    print()
    print("=" * 72)
    print("  P7 TREMORSENSE — AUDIT HISTORY")
    print("=" * 72)
    print()

    if not rows:
        print("  No audit reports found. Run --audit first.")
        print()
        return

    print(f"  {'ID':<8} {'Timestamp':<22} {'Grade':<6} {'Uptime':<10} "
          f"{'Covered':<10} {'Dead':<8} {'Daemons'}")
    print(f"  {'-'*7} {'-'*21} {'-'*5} {'-'*9} {'-'*9} {'-'*7} {'-'*10}")

    for row in rows:
        try:
            data = json.loads(row["data_json"])
            # Navigate CloudEvent envelope
            inner = data.get("data", data)
            grade = inner.get("grade", "?")
            pct = inner.get("uptime_pct", 0)
            covered = inner.get("covered_minutes", 0)
            dead = inner.get("dead_minutes", 0)
            total = inner.get("total_minutes", 0)
            daemons = inner.get("active_daemon_count", 0)
            ts = row["timestamp"][:19]

            gc = _grade_color(grade)
            uptime_str = f"{pct:.1f}%"
            cov_str = f"{covered}/{total}"
            print(f"  {row['id']:<8} {ts:<22} {gc}{grade:<6}{RESET} "
                  f"{uptime_str:<10} {cov_str:<10} {dead:<8} {daemons}")
        except (json.JSONDecodeError, KeyError):
            print(f"  {row['id']:<8} {row['timestamp'][:19]:<22} [parse error]")

    print()

    # Trend line
    if len(rows) >= 2:
        try:
            newest = json.loads(rows[0]["data_json"]).get("data", {})
            oldest = json.loads(rows[-1]["data_json"]).get("data", {})
            new_pct = newest.get("uptime_pct", 0)
            old_pct = oldest.get("uptime_pct", 0)
            delta = new_pct - old_pct
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            sign = "+" if delta > 0 else ""
            print(f"  TREND: {old_pct:.1f}% → {new_pct:.1f}%  {arrow} {sign}{delta:.1f}%")
        except (json.JSONDecodeError, KeyError):
            pass

    print()
    print("=" * 72)
    print()


def print_grid_24h() -> None:
    """Print 24-hour ASCII uptime grid."""
    report = run_audit(hours=24, write_to_ssot=False)
    per_minute = report.get("per_minute", [])

    print()
    print("=" * 80)
    print("  P7 TREMORSENSE — 24-HOUR UPTIME GRID")
    print(f"  \"{CORE_THESIS}\"")
    print("=" * 80)
    print()
    print(f"  Overall: {report['uptime_pct']:.1f}% "
          f"({report['covered_minutes']}/{report['total_minutes']} min) "
          f"Grade: {report['grade']}")
    print()

    _print_minute_grid(per_minute, 24)

    # Per-hour summary
    print("  HOURLY BREAKDOWN:")
    print(f"    {'Hour':<6} {'Covered':<10} {'Dead':<8} {'Uptime':<10} {'Grade'}")
    print(f"    {'-'*5} {'-'*9} {'-'*7} {'-'*9} {'-'*5}")

    for h in range(24):
        start_idx = h * 60
        end_idx = min(start_idx + 60, len(per_minute))
        chunk = per_minute[start_idx:end_idx]
        if not chunk:
            break

        hour_label = chunk[0]["minute"][11:13] if chunk else f"{h:02d}"
        covered = sum(1 for m in chunk if m["covered"])
        total = len(chunk)
        dead = total - covered
        pct = (covered / total * 100) if total > 0 else 0
        g, _ = grade_uptime(pct)
        gc = _grade_color(g)

        print(f"    {hour_label}:00 {covered}/{total:<6}  {dead:<8} "
              f"{pct:<9.0f}% {gc}{g}{RESET}")

    print()
    print("=" * 80)
    print()


# ═══════════════════════════════════════════════════════════════
# § 7  DAEMON MODE — Hourly audit loop
# ═══════════════════════════════════════════════════════════════

_DAEMON_RUNNING = True

def _signal_handler(signum, frame):
    global _DAEMON_RUNNING
    _DAEMON_RUNNING = False
    print(f"\n  [SIGNAL] Shutting down tremorsense daemon...")


def daemon_loop(interval_seconds: int = 3600) -> None:
    """Run hourly tremorsense audits in a loop."""
    global _DAEMON_RUNNING
    _DAEMON_RUNNING = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    interval_min = interval_seconds / 60.0

    print()
    print("=" * 66)
    print("  P7 SPIDER SOVEREIGN — TREMORSENSE DAEMON")
    print(f"  Audit every {interval_min:.0f} minutes ({interval_seconds}s)")
    print(f"  Target: {TARGET_UPTIME_PCT}% per-minute uptime")
    print(f"  \"{CORE_THESIS}\"")
    print("  Press Ctrl+C to stop")
    print("=" * 66)
    print()

    # Emit daemon start heartbeat
    conn = get_db_rw()
    try:
        write_event(conn, EVT_HEARTBEAT, "DAEMON:START", {
            "mode": "TREMORSENSE_LOOP",
            "interval_seconds": interval_seconds,
            "target_uptime_pct": TARGET_UPTIME_PCT,
            "pid": os.getpid(),
            "core_thesis": CORE_THESIS,
        })
    finally:
        conn.close()

    audit_count = 0

    while _DAEMON_RUNNING:
        try:
            audit_count += 1
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            # Calculate hours to audit (1 hour for normal, full window for first)
            audit_hours = 1

            print(f"  [{ts}] TREMORSENSE #{audit_count} ({audit_hours}h window)...")
            report = run_audit(hours=audit_hours, write_to_ssot=True)

            grade = report.get("grade", "?")
            pct = report.get("uptime_pct", 0)
            covered = report.get("covered_minutes", 0)
            total = report.get("total_minutes", 0)
            dead = report.get("dead_minutes", 0)
            row_id = report.get("ssot_row_id", "?")
            gc = _grade_color(grade)

            met = "✓" if report.get("meets_target") else "✗"
            print(f"    {gc}Grade {grade}{RESET} | {pct:.1f}% "
                  f"({covered}/{total} min, {dead} dead) "
                  f"{met} → SSOT row {row_id}")

            # Write heartbeat
            conn = get_db_rw()
            try:
                write_event(conn, EVT_HEARTBEAT, f"HEARTBEAT:audit_{audit_count}", {
                    "audit_number": audit_count,
                    "grade": grade,
                    "uptime_pct": pct,
                    "covered_minutes": covered,
                    "dead_minutes": dead,
                    "total_minutes": total,
                    "meets_target": report.get("meets_target", False),
                    "pid": os.getpid(),
                    "core_thesis": CORE_THESIS,
                })
            finally:
                conn.close()

        except Exception as e:
            print(f"    ERROR: {e}")

        # Sleep in 1-second increments for responsive shutdown
        for _ in range(interval_seconds):
            if not _DAEMON_RUNNING:
                break
            time.sleep(1)

    # Emit daemon stop event
    conn = get_db_rw()
    try:
        write_event(conn, EVT_HEARTBEAT, "DAEMON:STOP", {
            "mode": "TREMORSENSE_LOOP",
            "audits_completed": audit_count,
            "pid": os.getpid(),
            "core_thesis": CORE_THESIS,
        })
    finally:
        conn.close()

    print(f"\n  Tremorsense daemon stopped after {audit_count} audit(s).")
    print()


# ═══════════════════════════════════════════════════════════════
# § 8  CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — TREMORSENSE uptime audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python hfo_p7_tremorsense.py --audit              # Audit last 1 hour
  python hfo_p7_tremorsense.py --audit --hours 24   # Audit last 24 hours
  python hfo_p7_tremorsense.py --daemon              # Hourly audit loop
  python hfo_p7_tremorsense.py --history             # Last 24 audit reports
  python hfo_p7_tremorsense.py --history 48          # Last 48 reports
  python hfo_p7_tremorsense.py --grid                # 24-hour uptime grid
  python hfo_p7_tremorsense.py --json                # Machine-readable audit

Core Thesis: "The web feels all. Dead silence is the loudest signal."
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audit", action="store_true",
                       help="Run uptime audit for the last N hours")
    group.add_argument("--daemon", action="store_true",
                       help="Run hourly audit loop (background service)")
    group.add_argument("--history", nargs="?", type=int, const=24, default=None,
                       metavar="N", help="Show last N audit reports (default: 24)")
    group.add_argument("--grid", action="store_true",
                       help="24-hour minute-by-minute uptime grid")
    group.add_argument("--json", action="store_true",
                       help="Machine-readable audit (last 1h)")

    parser.add_argument("--hours", type=int, default=1,
                       help="Audit window in hours (default: 1)")
    parser.add_argument("--interval", type=int, default=3600,
                       help="Seconds between daemon audits (default: 3600)")
    parser.add_argument("--no-write", action="store_true",
                       help="Don't write audit to SSOT (dry run)")

    args = parser.parse_args()

    if args.audit:
        report = run_audit(
            hours=args.hours,
            write_to_ssot=not args.no_write,
        )
        print_audit_report(report)
    elif args.daemon:
        daemon_loop(interval_seconds=args.interval)
    elif args.history is not None:
        print_history(args.history)
    elif args.grid:
        print_grid_24h()
    elif args.json:
        report = run_audit(
            hours=args.hours,
            write_to_ssot=not args.no_write,
        )
        # Strip per_minute for compact JSON output (still available via per_minute_summary)
        compact = {k: v for k, v in report.items() if k != "per_minute"}
        compact["per_minute_sample"] = report.get("per_minute", [])[:5]
        print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
