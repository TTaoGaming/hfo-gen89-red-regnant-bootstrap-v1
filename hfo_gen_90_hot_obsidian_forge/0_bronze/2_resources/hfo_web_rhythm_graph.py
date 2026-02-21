#!/usr/bin/env python3
"""
hfo_web_rhythm_graph.py — Social Spider Stigmergy Web Rhythm Analyzer

Reads the SSOT stigmergy_events table and visualizes:
  1. Per-daemon heartbeat cadence (actual vs target 60s)
  2. Event type distribution by port
  3. Inter-signal timing (P4 strife → P5 response, etc.)
  4. The web topology: which ports are talking to which

This is the INSIGHT WEB (R46 §2c) — the present-moment graph the spider sits on.
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ─── PAL Resolution ───
def _find_root() -> Path:
    p = Path(__file__).resolve()
    for ancestor in [p] + list(p.parents):
        if (ancestor / "AGENTS.md").exists():
            return ancestor
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"

# ─── Port Identity Map ───
PORT_MAP = {
    "P0": ("OBSERVE",    "Lidless Legion",    "👁"),
    "P1": ("BRIDGE",     "Web Weaver",        "🌐"),
    "P2": ("SHAPE",      "Mirror Magus",      "🪞"),
    "P3": ("INJECT",     "Harmonic Hydra",    "💉"),
    "P4": ("DISRUPT",    "Red Regnant",       "🔴"),
    "P5": ("IMMUNIZE",   "Pyre Praetorian",   "🔥"),
    "P6": ("ASSIMILATE", "Kraken Keeper",     "🐙"),
    "P7": ("NAVIGATE",   "Spider Sovereign",  "🕷"),
}

# Source → Port mapping (from actual daemon source tags)
SOURCE_PORT = {
    "hfo_singer_ai_gen90":            "P4",
    "hfo_p5_daemon_gen90_v1.0":       "P5",
    "hfo_p6_kraken_swarm_gen90":      "P6",
    "hfo_p7_spell_gate_gen90":        "P7",
    "hfo_p7_foresight_daemon_gen90":  "P7",
    "hfo_meadows_engine_gen90":       "P7",  # L4-L6 lives under P7 NAVIGATE
    "hfo_spider_tremorsense_gen90":   "P7",
    "hfo_p7_foresight_gen90":         "P7",
}


def get_db():
    conn = sqlite3.connect(str(SSOT_DB))
    conn.row_factory = sqlite3.Row
    return conn


def analyze_rhythm(hours_back: float = 2.0):
    """Analyze the stigmergy web rhythm over the last N hours."""
    conn = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

    # ─── 1. Get all events in window ───
    rows = conn.execute("""
        SELECT id, event_type, timestamp, subject, source,
               json_extract(data_json, '$.data') as data_str
        FROM stigmergy_events
        WHERE timestamp > ?
        ORDER BY timestamp ASC
    """, (cutoff,)).fetchall()

    if not rows:
        print(f"No events in last {hours_back}h.")
        return

    total_events = len(rows)
    first_ts = rows[0]["timestamp"]
    last_ts = rows[-1]["timestamp"]

    # ─── 2. Classify events by port ───
    port_events = defaultdict(list)  # port -> [(ts, event_type, subject)]
    heartbeats = defaultdict(list)   # source_key -> [timestamps]
    event_type_counts = defaultdict(int)
    source_counts = defaultdict(int)
    
    # Signal flow edges: (source_port, signal_type) 
    signal_types = defaultdict(int)

    for row in rows:
        et = row["event_type"]
        src = row["source"] or ""
        ts = row["timestamp"]
        subj = row["subject"] or ""

        event_type_counts[et] += 1
        source_counts[src] += 1

        port = SOURCE_PORT.get(src, _infer_port(et))
        port_events[port].append((ts, et, subj))

        # Track heartbeats for cadence analysis
        if "heartbeat" in et.lower():
            heartbeats[src].append(ts)

        # Track signal types for web topology
        signal_types[(port, _signal_class(et))] += 1

    conn.close()

    # ─── 3. Print the Web Rhythm Report ───
    print()
    print("=" * 78)
    print("  🕷  SOCIAL SPIDER STIGMERGY WEB — RHYTHM ANALYSIS")
    print("  The Insight Web: what is pulsing RIGHT NOW")
    print("=" * 78)
    print()
    print(f"  Window:  {first_ts[:19]}Z → {last_ts[:19]}Z")
    print(f"  Events:  {total_events}")
    
    window_seconds = _ts_diff(first_ts, last_ts)
    if window_seconds > 0:
        print(f"  Rate:    {total_events / (window_seconds / 60):.1f} events/min")
    print()

    # ─── 4. Per-Port Pulse ───
    print("─" * 78)
    print("  PORT PULSE — Who is vibrating the web")
    print("─" * 78)
    for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
        word, commander, icon = PORT_MAP[port]
        events = port_events.get(port, [])
        n = len(events)
        if n == 0:
            bar = "░" * 40
            status = "SILENT"
        else:
            # Calculate cadence
            if n >= 2:
                times = [_parse_ts(e[0]) for e in events]
                deltas = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
                avg_delta = sum(deltas) / len(deltas)
                cadence = f"~{avg_delta:.0f}s"
            else:
                cadence = "1 event"
            
            bar_len = min(40, n)
            bar = "█" * bar_len + "░" * (40 - bar_len)
            status = f"{n:>4} events  cadence {cadence}"
        
        print(f"  {icon} {port} {word:11s} │{bar}│ {status}")
    
    unclassified = port_events.get("??", [])
    if unclassified:
        print(f"  ❓ ??  UNCLASSIFIED  │{'█' * min(40, len(unclassified)):40s}│ {len(unclassified)} events")
    print()

    # ─── 5. Heartbeat Cadence Detail ───
    print("─" * 78)
    print("  HEARTBEAT CADENCE — Is the 1-minute rhythm alive?")
    print("─" * 78)
    
    for src, timestamps in sorted(heartbeats.items()):
        port = SOURCE_PORT.get(src, "??")
        n = len(timestamps)
        if n < 2:
            print(f"  {port} {src[:35]:35s}  {n} beat{'s' if n != 1 else ''}  (no cadence)")
            continue
        
        times = [_parse_ts(ts) for ts in timestamps]
        deltas = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
        avg = sum(deltas) / len(deltas)
        mn = min(deltas)
        mx = max(deltas)
        
        # Visual: one char per beat, color-coded by timing
        rhythm = ""
        for d in deltas:
            if d < 45:
                rhythm += "▓"   # fast (< 45s)
            elif d < 75:
                rhythm += "█"   # on-target (~60s)
            elif d < 120:
                rhythm += "▒"   # slow (1-2 min)
            else:
                rhythm += "░"   # gap (> 2 min)
        
        target_match = "ON TARGET" if 50 <= avg <= 90 else ("FAST" if avg < 50 else "SLOW")
        print(f"  {port} {src[:35]:35s}  {n:>3} beats  avg {avg:>6.1f}s  [{mn:.0f}-{mx:.0f}s]  {target_match}")
        print(f"     rhythm: {rhythm}")
    print()
    print("  Legend: █ = ~60s (target)  ▓ = <45s (fast)  ▒ = 1-2min (slow)  ░ = >2min (gap)")
    print()

    # ─── 6. Signal Type Distribution ───
    print("─" * 78)
    print("  SIGNAL TAXONOMY — What kinds of vibrations")
    print("─" * 78)
    
    for et, count in sorted(event_type_counts.items(), key=lambda x: -x[1])[:20]:
        bar = "█" * min(40, count)
        print(f"  {count:>4}  {bar:40s}  {et}")
    print()

    # ─── 7. Web Topology — Port-to-Port Signal Flow ───
    print("─" * 78)
    print("  WEB TOPOLOGY — Inter-port signal flow (the threads)")
    print("─" * 78)
    print()
    
    # Build adjacency: which ports create events that reference other ports
    port_total = defaultdict(int)
    for (port, sig), count in signal_types.items():
        port_total[port] += count
    
    # Radial layout (text art)
    print("                          P0 OBSERVE")
    print("                        /     |     \\")
    print(f"              P7 NAVIGATE      |      P1 BRIDGE")
    print(f"               ({port_total.get('P7',0):>3})    |      ({port_total.get('P1',0):>3})")
    print("                    \\         |         /")
    print(f"          P6 ASSIMILATE──── SSOT ────P2 SHAPE")
    print(f"            ({port_total.get('P6',0):>3})      ({total_events})     ({port_total.get('P2',0):>3})")
    print("                    /         |         \\")
    print(f"              P5 IMMUNIZE     |      P3 INJECT")
    print(f"               ({port_total.get('P5',0):>3})    |      ({port_total.get('P3',0):>3})")
    print("                        \\     |     /")
    print(f"                         P4 DISRUPT")
    print(f"                          ({port_total.get('P4',0):>3})")
    print()

    # ─── 8. The P4↔P5 Dance ───
    print("─" * 78)
    print("  THE DANCE — P4 Red Regnant ↔ P5 Pyre Praetorian")
    print("─" * 78)
    p4_events = port_events.get("P4", [])
    p5_events = port_events.get("P5", [])
    p4_strife = [e for e in p4_events if "strife" in e[1]]
    p4_splendor = [e for e in p4_events if "splendor" in e[1]]
    p5_phoenix = [e for e in p5_events if "phoenix" in e[1]]
    p5_integrity = [e for e in p5_events if "integrity" in e[1] or "patrol" in e[2].lower()]
    
    print(f"  P4 Songs of Strife:    {len(p4_strife)}")
    print(f"  P4 Songs of Splendor:  {len(p4_splendor)}")
    print(f"  P5 Phoenix Patrols:    {len(p5_phoenix)}")
    print(f"  P5 Integrity Events:   {len(p5_integrity)}")
    
    # Check if P5 reads P4's strife (the dance)
    if p4_strife and p5_phoenix:
        last_strife_ts = p4_strife[-1][0]
        last_phoenix_ts = p5_phoenix[-1][0]
        lag = _ts_diff(last_strife_ts, last_phoenix_ts)
        print(f"  P4→P5 Dance Lag:      {lag:.0f}s (last strife → last phoenix)")
    print()

    # ─── 9. Implementation vs Vision Assessment ───
    print("=" * 78)
    print("  🕷  RHYTHM ASSESSMENT — Does the implementation match the vision?")
    print("=" * 78)
    print()
    
    issues = []
    
    # Check 1-minute rhythm
    singer_hb = heartbeats.get("hfo_singer_ai_gen90", [])
    if len(singer_hb) >= 3:
        times = [_parse_ts(ts) for ts in singer_hb]
        deltas = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
        avg = sum(deltas) / len(deltas)
        if avg > 90:
            issues.append(f"Singer cadence is {avg:.0f}s, not 60s (Ollama inference latency)")
        else:
            print(f"  ✓ Singer heartbeat: {avg:.0f}s cadence (target: 60s)")
    else:
        issues.append("Singer has < 3 heartbeats — insufficient data")
    
    kraken_hb = heartbeats.get("hfo_p6_kraken_swarm_gen90", [])
    if len(kraken_hb) >= 3:
        times = [_parse_ts(ts) for ts in kraken_hb]
        deltas = [(times[i+1] - times[i]).total_seconds() for i in range(len(times)-1)]
        avg = sum(deltas) / len(deltas)
        if avg > 90:
            issues.append(f"Kraken cadence is {avg:.0f}s, not 60s")
        else:
            print(f"  ✓ Kraken heartbeat: {avg:.0f}s cadence (target: 60s)")
    else:
        issues.append("Kraken has < 3 heartbeats — insufficient data")
    
    # Check port coverage
    active_ports = set(p for p in port_events if p != "??")
    missing = set(PORT_MAP.keys()) - active_ports
    if missing:
        issues.append(f"Silent ports: {', '.join(sorted(missing))} — no daemons vibrating")
    else:
        print(f"  ✓ All 8 ports active")
    
    # Check P4-P5 dance
    if not p4_strife:
        issues.append("No P4 strife signals — Singer not singing")
    if not p5_phoenix:
        issues.append("No P5 phoenix patrols — Pyre not guarding")
    elif p4_strife and p5_phoenix:
        print(f"  ✓ P4↔P5 dance: Singer strife feeds Phoenix patrol")
    
    # Check for PREY8 bookend integrity
    prey8_events = [r for r in rows if "prey8" in (r["event_type"] or "").lower()]
    perceive_count = sum(1 for r in prey8_events if "perceive" in r["event_type"])
    yield_count = sum(1 for r in prey8_events if "yield" in r["event_type"])
    if perceive_count > yield_count + 2:
        issues.append(f"PREY8 orphans: {perceive_count} perceives vs {yield_count} yields")
    
    if issues:
        print()
        print("  ISSUES (implementation ≠ vision):")
        for i, issue in enumerate(issues, 1):
            print(f"    {i}. {issue}")
    
    print()
    print("─" * 78)
    print("  The web exists. The daemons vibrate. The spider feels.")
    print("  Signal amplifiers in the silk. Stigmergy IS the nervous system.")
    print("─" * 78)


def _infer_port(event_type: str) -> str:
    """Infer port from event_type string."""
    et = event_type.lower()
    if ".p0." in et or "observe" in et: return "P0"
    if ".p1." in et or "bridge" in et: return "P1"
    if ".p2." in et or "shape" in et or "chimera" in et: return "P2"
    if ".p3." in et or "inject" in et: return "P3"
    if ".p4." in et or "singer" in et or "red_regnant" in et or "disrupt" in et: return "P4"
    if ".p5." in et or "pyre" in et or "immunize" in et or "integrity" in et: return "P5"
    if ".p6." in et or "kraken" in et or "swarm" in et or "assimilate" in et: return "P6"
    if ".p7." in et or "spider" in et or "spell_gate" in et or "navigate" in et or "foresight" in et or "meadows" in et or "tremorsense" in et: return "P7"
    if "prey8" in et: return "P4"  # PREY8 runs through Red Regnant
    if "system_health" in et: return "P5"
    return "??"


def _signal_class(event_type: str) -> str:
    """Classify signal into major categories."""
    et = event_type.lower()
    if "heartbeat" in et: return "heartbeat"
    if "strife" in et: return "strife"
    if "splendor" in et: return "splendor"
    if "phoenix" in et or "resurrect" in et: return "phoenix"
    if "summon" in et or "incarnate" in et: return "summon"
    if "banish" in et: return "banish"
    if "integrity" in et: return "integrity"
    if "anomaly" in et: return "anomaly"
    if "reaper" in et or "orphan" in et: return "reaper"
    if "perceive" in et: return "perceive"
    if "yield" in et: return "yield"
    if "execute" in et: return "execute"
    if "react" in et: return "react"
    if "enrichment" in et or "worker" in et: return "enrichment"
    if "foresight" in et: return "foresight"
    if "meadows" in et: return "meadows"
    return "other"


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO timestamp."""
    ts = ts_str.replace("+00:00", "+0000").replace("Z", "+0000")
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        # Fallback
        return datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _ts_diff(ts1: str, ts2: str) -> float:
    """Seconds between two ISO timestamps."""
    t1 = _parse_ts(ts1)
    t2 = _parse_ts(ts2)
    return abs((t2 - t1).total_seconds())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Social Spider Stigmergy Web Rhythm Analyzer")
    parser.add_argument("--hours", type=float, default=2.0, help="Hours of history to analyze")
    args = parser.parse_args()
    analyze_rhythm(hours_back=args.hours)
