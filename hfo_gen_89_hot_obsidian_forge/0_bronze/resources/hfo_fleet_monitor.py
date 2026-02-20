#!/usr/bin/env python3
"""
HFO Gen89 Fleet Uptime Monitor — Hourly % Uptime Per Port
==========================================================

Monitors the stigmergy trail to calculate per-port % uptime.
Sleeps on 10-minute intervals for 1 hour (6 samples), then
prints a cumulative hourly uptime report.

Usage:
    python hfo_fleet_monitor.py                 # 1-hour run, 10-min interval
    python hfo_fleet_monitor.py --interval 5    # 5-min sample interval
    python hfo_fleet_monitor.py --duration 30   # 30-min total run
    python hfo_fleet_monitor.py --once           # Single snapshot, no loop
    python hfo_fleet_monitor.py --history 60    # Look back 60 min (no live wait)

Event-to-Port Mapping:
  P0 OBSERVE  — hfo.gen89.daemon.{start,stop,advisory,swarm_*,model_*}
  P1 BRIDGE   — hfo.gen89.daemon.research
  P2 SHAPE    — hfo.gen89.daemon.{deep_analysis,code_eval}, hfo.gen89.chimera.*
  P3 INJECT   — hfo.gen89.daemon.{enrich.*,patrol,port_assign}
  P4 DISRUPT  — hfo.gen89.singer.*
  P5 IMMUNIZE — hfo.gen89.dancer.*
  P6 ASSIMILATE — hfo.gen89.{devourer.*,kraken.*}
  P7 NAVIGATE — hfo.gen89.summoner.*
"""

import argparse
import os
import io
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

# Also set PYTHONUNBUFFERED for child-compat
os.environ["PYTHONUNBUFFERED"] = "1"

# ── Resolve SSOT DB path ──────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
FORGE_ROOT = SCRIPT_DIR.parent.parent
SSOT_DB = FORGE_ROOT / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"

# Fallback via .env or environment
if not SSOT_DB.exists():
    env_path = os.environ.get("HFO_SSOT_DB", "")
    if env_path and Path(env_path).exists():
        SSOT_DB = Path(env_path)
    else:
        print(f"[FATAL] SSOT database not found at {SSOT_DB}")
        sys.exit(1)


# ── Port Configuration ─────────────────────────────────────────────
# Each port has:
#   - event_patterns: SQL LIKE patterns that match its stigmergy events
#   - expected_per_hour: how many events/hour at designed cadence
#   - cadence_note: human-readable cadence

PORT_CONFIG = {
    "P0": {
        "name": "OBSERVE (Watcher)",
        "event_patterns": [
            "hfo.gen89.daemon.start",
            "hfo.gen89.daemon.stop",
            "hfo.gen89.daemon.error",
            "hfo.gen89.daemon.advisory",
            "hfo.gen89.daemon.swarm%",
            "hfo.gen89.daemon.model%",
        ],
        "expected_per_hour": 30,
        "cadence_note": "120s tremorsense",
    },
    "P1": {
        "name": "BRIDGE (Weaver)",
        "event_patterns": [
            "hfo.gen89.daemon.research",
        ],
        "expected_per_hour": 12,
        "cadence_note": "300s research",
    },
    "P2": {
        "name": "SHAPE (Shaper)",
        "event_patterns": [
            "hfo.gen89.daemon.deep_analysis",
            "hfo.gen89.daemon.code_eval",
            "hfo.gen89.chimera.%",
        ],
        "expected_per_hour": 4,
        "cadence_note": "600-900s Deep Think",
    },
    "P3": {
        "name": "INJECT (Injector)",
        "event_patterns": [
            "hfo.gen89.daemon.enrich%",
            "hfo.gen89.daemon.patrol",
            "hfo.gen89.daemon.enrich.port_assign",
        ],
        "expected_per_hour": 30,
        "cadence_note": "60-120s delivery",
    },
    "P4": {
        "name": "DISRUPT (Singer)",
        "event_patterns": [
            "hfo.gen89.singer.%",
        ],
        "expected_per_hour": 60,
        "cadence_note": "60s adversarial",
    },
    "P5": {
        "name": "IMMUNIZE (Dancer)",
        "event_patterns": [
            "hfo.gen89.dancer.%",
        ],
        "expected_per_hour": 60,
        "cadence_note": "60s death/dawn",
    },
    "P6": {
        "name": "ASSIMILATE (Devourer+Kraken)",
        "event_patterns": [
            "hfo.gen89.devourer.%",
            "hfo.gen89.kraken.%",
        ],
        "expected_per_hour": 360,
        "cadence_note": "10s fast-loop + 30-120s structured",
    },
    "P7": {
        "name": "NAVIGATE (Summoner)",
        "event_patterns": [
            "hfo.gen89.summoner.%",
        ],
        "expected_per_hour": 2,
        "cadence_note": "1800s strategic",
    },
}


def get_db():
    """Open read-only connection to SSOT."""
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def count_events(conn, patterns: list[str], since_iso: str) -> int:
    """Count stigmergy events matching any of the LIKE patterns since a timestamp."""
    if not patterns:
        return 0
    # Build OR clause for all patterns
    clauses = " OR ".join(["event_type LIKE ?" for _ in patterns])
    sql = f"""
        SELECT COUNT(*) as cnt FROM stigmergy_events
        WHERE ({clauses}) AND timestamp >= ?
    """
    params = patterns + [since_iso]
    row = conn.execute(sql, params).fetchone()
    return row["cnt"] if row else 0


def count_errors(conn, since_iso: str) -> dict:
    """Count error events per port family."""
    sql = """
        SELECT event_type, COUNT(*) as cnt FROM stigmergy_events
        WHERE event_type LIKE '%error%' AND timestamp >= ?
        GROUP BY event_type
    """
    rows = conn.execute(sql, (since_iso,)).fetchall()
    return {r["event_type"]: r["cnt"] for r in rows}


def latest_event(conn, patterns: list[str]) -> str | None:
    """Find the most recent event timestamp matching any pattern."""
    if not patterns:
        return None
    clauses = " OR ".join(["event_type LIKE ?" for _ in patterns])
    sql = f"""
        SELECT MAX(timestamp) as latest FROM stigmergy_events
        WHERE ({clauses})
    """
    row = conn.execute(sql, patterns).fetchone()
    return row["latest"] if row else None


def sample_snapshot(conn, lookback_minutes: float) -> dict:
    """Take a snapshot of all port activity over the lookback window."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=lookback_minutes)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S")

    snapshot = {
        "timestamp": now.isoformat(),
        "lookback_minutes": lookback_minutes,
        "ports": {},
    }

    for port, cfg in PORT_CONFIG.items():
        actual = count_events(conn, cfg["event_patterns"], since_iso)
        # Scale expected to lookback window
        expected_scaled = cfg["expected_per_hour"] * (lookback_minutes / 60.0)
        # Uptime % — capped at 100%, min 0%
        if expected_scaled > 0:
            uptime_pct = min(100.0, (actual / expected_scaled) * 100.0)
        else:
            uptime_pct = 0.0 if actual == 0 else 100.0

        last = latest_event(conn, cfg["event_patterns"])

        snapshot["ports"][port] = {
            "name": cfg["name"],
            "actual": actual,
            "expected": round(expected_scaled, 1),
            "uptime_pct": round(uptime_pct, 1),
            "last_event": last,
            "cadence": cfg["cadence_note"],
        }

    # Error summary
    snapshot["errors"] = count_errors(conn, since_iso)

    return snapshot


def print_snapshot(snap: dict, header: str = ""):
    """Pretty-print a snapshot as a table."""
    w = 92
    if header:
        print(f"\n{'=' * w}")
        print(f"  {header}")
        print(f"  Lookback window: {snap['lookback_minutes']:.0f} min | Sampled: {snap['timestamp'][:19]}Z")
        print(f"{'=' * w}")
    else:
        print(f"\n{'-' * w}")
        print(f"  Snapshot @ {snap['timestamp'][:19]}Z (last {snap['lookback_minutes']:.0f}min)")
        print(f"{'-' * w}")

    print(f"  {'Port':<6} {'Name':<30} {'Actual':>7} {'Expected':>9} {'Uptime%':>8}  {'Last Event'}")
    print(f"  {'-'*6} {'-'*30} {'-'*7} {'-'*9} {'-'*8}  {'-'*22}")

    total_actual = 0
    total_expected = 0
    port_uptimes = []

    for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
        p = snap["ports"][port]
        total_actual += p["actual"]
        total_expected += p["expected"]
        port_uptimes.append(p["uptime_pct"])

        last_str = p["last_event"][:19] if p["last_event"] else "-- SILENT --"
        # Color code the uptime
        pct = p["uptime_pct"]
        if pct >= 80:
            bar = "##"
        elif pct >= 50:
            bar = "#."
        elif pct > 0:
            bar = ".."
        else:
            bar = "  "

        print(f"  {port:<6} {p['name']:<30} {p['actual']:>7} {p['expected']:>9} {pct:>7.1f}% {bar} {last_str}")

    # Fleet totals
    fleet_uptime = sum(port_uptimes) / len(port_uptimes) if port_uptimes else 0
    print(f"  {'-'*6} {'-'*30} {'-'*7} {'-'*9} {'-'*8}  {'-'*22}")
    print(f"  {'FLEET':<6} {'ALL PORTS (avg)':<30} {total_actual:>7} {total_expected:>9.0f} {fleet_uptime:>7.1f}%")

    # Errors
    if snap.get("errors"):
        print(f"\n  [!] Errors detected:")
        for etype, cnt in snap["errors"].items():
            print(f"    {etype}: {cnt}")

    return fleet_uptime


def run_monitor(interval_min: float = 10, duration_min: float = 60, once: bool = False):
    """Main monitoring loop."""
    conn = get_db()
    samples = []
    n_samples = 1 if once else max(1, int(duration_min / interval_min))

    print("=" * 92)
    print("  HFO Gen89 Fleet Uptime Monitor")
    print(f"  SSOT: {SSOT_DB}")
    print(f"  Plan: {'Single snapshot' if once else f'{n_samples} samples x {interval_min:.0f}min = {duration_min:.0f}min'}")
    print(f"  Started: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("=" * 92)

    for i in range(n_samples):
        # For the first sample, look back over the interval window
        # For subsequent, look back over the interval since last sample
        lookback = interval_min if i > 0 else interval_min

        snap = sample_snapshot(conn, lookback)
        samples.append(snap)

        label = f"Sample {i+1}/{n_samples}" if not once else "Snapshot"
        fleet_avg = print_snapshot(snap, label)

        if i < n_samples - 1:
            next_time = datetime.now(timezone.utc) + timedelta(minutes=interval_min)
            print(f"\n  [ZZZ] Sleeping {interval_min:.0f}min until {next_time.strftime('%H:%M:%S')}Z ...")
            try:
                time.sleep(interval_min * 60)
            except KeyboardInterrupt:
                print("\n  [INTERRUPTED] Printing summary with data collected so far...")
                break

    # ── Hourly Summary ──────────────────────────────────────────
    if len(samples) > 1:
        print_hourly_summary(conn, samples, duration_min)
    elif len(samples) == 1 and once:
        # For --once or --history, use lookup window instead
        pass

    conn.close()


def run_history(lookback_min: float = 60):
    """Look back over historical data without waiting."""
    conn = get_db()

    snap = sample_snapshot(conn, lookback_min)
    print_snapshot(snap, f"Historical Lookback: Last {lookback_min:.0f} Minutes")

    # Also show per-10min breakdown if lookback > 10 min
    if lookback_min > 10:
        print(f"\n{'=' * 92}")
        print(f"  Per-Interval Breakdown (10-min windows over last {lookback_min:.0f}min)")
        print(f"{'=' * 92}")

        now = datetime.now(timezone.utc)
        windows = int(lookback_min / 10)
        # Build table header
        print(f"\n  {'Window':<18}", end="")
        for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
            print(f" {port:>6}", end="")
        print(f" {'Fleet':>7}")
        print(f"  {'-'*18}" + "".join([f" {'-'*6}" for _ in range(8)]) + f" {'-'*7}")

        for w in range(windows):
            win_end = now - timedelta(minutes=w * 10)
            win_start = win_end - timedelta(minutes=10)
            since_iso = win_start.strftime("%Y-%m-%dT%H:%M:%S")
            until_iso = win_end.strftime("%Y-%m-%dT%H:%M:%S")

            label = f"  {win_start.strftime('%H:%M')}-{win_end.strftime('%H:%M')}Z"
            print(f"{label:<20}", end="")

            pcts = []
            for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
                cfg = PORT_CONFIG[port]
                # Count events in this 10-min window
                clauses = " OR ".join(["event_type LIKE ?" for _ in cfg["event_patterns"]])
                sql = f"""
                    SELECT COUNT(*) as cnt FROM stigmergy_events
                    WHERE ({clauses}) AND timestamp >= ? AND timestamp < ?
                """
                params = cfg["event_patterns"] + [since_iso, until_iso]
                row = conn.execute(sql, params).fetchone()
                actual = row["cnt"] if row else 0
                expected = cfg["expected_per_hour"] * (10 / 60.0)
                pct = min(100.0, (actual / expected * 100.0)) if expected > 0 else 0
                pcts.append(pct)
                print(f" {pct:>5.0f}%", end="")
            fleet = sum(pcts) / len(pcts) if pcts else 0
            print(f" {fleet:>6.0f}%")

    conn.close()


def print_hourly_summary(conn, samples: list[dict], duration_min: float):
    """Print the cumulative hourly summary at the end."""
    print(f"\n{'═' * 92}")
    print(f"  *** HOURLY UPTIME SUMMARY ({duration_min:.0f}min observation) ***")
    print(f"{'═' * 92}")

    # Use total lookback for the final authoritative numbers
    final_snap = sample_snapshot(conn, duration_min)
    print_snapshot(final_snap, f"Cumulative {duration_min:.0f}-min Uptime")

    # Health grade
    uptimes = [final_snap["ports"][p]["uptime_pct"] for p in PORT_CONFIG]
    avg = sum(uptimes) / len(uptimes)
    silent = sum(1 for u in uptimes if u == 0)

    print(f"\n  Fleet Health Grade: ", end="")
    if avg >= 90 and silent == 0:
        print("A+ (EXCELLENT)")
    elif avg >= 75 and silent <= 1:
        print("B  (GOOD — minor gaps)")
    elif avg >= 50:
        print("C  (FAIR — some ports underperforming)")
    elif avg >= 25:
        print("D  (POOR — significant gaps)")
    else:
        print("F  (CRITICAL — fleet down)")

    if silent > 0:
        dead_ports = [p for p in PORT_CONFIG if final_snap["ports"][p]["uptime_pct"] == 0]
        print(f"  [!] Silent ports ({silent}): {', '.join(dead_ports)}")

    print(f"{'═' * 92}")


def main():
    parser = argparse.ArgumentParser(
        description="HFO Gen89 Fleet Uptime Monitor — per-port hourly %% uptime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--interval", type=float, default=10,
                        help="Sample interval in minutes (default: 10)")
    parser.add_argument("--duration", type=float, default=60,
                        help="Total monitoring duration in minutes (default: 60)")
    parser.add_argument("--once", action="store_true",
                        help="Single snapshot, no looping")
    parser.add_argument("--history", type=float, default=0,
                        help="Look back N minutes into historical data (no live wait)")
    args = parser.parse_args()

    if args.history > 0:
        run_history(args.history)
    elif args.once:
        run_monitor(interval_min=args.interval, duration_min=args.interval, once=True)
    else:
        run_monitor(interval_min=args.interval, duration_min=args.duration)


if __name__ == "__main__":
    main()
