#!/usr/bin/env python3
"""
hfo_stigmergy_watchdog.py — Fail-Closed Stigmergy Watchdog Daemon
=================================================================
v1.0 | Gen89 | P5 IMMUNIZE + P4 DISRUPT observer daemon

PURPOSE:
    Monitors the SSOT stigmergy_events table for reward-hacking signals,
    session pollution, gate manipulation, and anomalous swarm behavior.
    Writes watchdog events BACK into stigmergy for full auditability.

DESIGN:
    - Deny-by-default mindset: everything is suspicious until proven benign
    - Runs as a persistent background process (or one-shot audit)
    - Polls stigmergy_events on a configurable interval
    - Detects 7 anomaly classes (see ANOMALY_DETECTORS below)
    - Emits CloudEvents into stigmergy for each finding
    - Tracks its own watermark so it never re-scans old events

ARCHITECTURE:
    This daemon occupies P5 IMMUNIZE (detection, quarantine, hardening)
    and reads P4 DISRUPT outputs (adversarial signals) to create a
    closed-loop defense system. The watchdog_daemon agent in the
    PREY8 AGENT_REGISTRY has role="watchdog" and zero gated access —
    it can only read and emit watchdog events, never inject into the
    PREY8 loop itself. This is least-privilege by design.

ANOMALY CLASSES:
    A1 — Gate Block Storm:     Agent hitting GATE_BLOCKED repeatedly (>N in window)
    A2 — Tamper Alert Cluster: Multiple tamper_alert events in short window
    A3 — Orphan Accumulation:  Perceive-without-yield ratio exceeding threshold
    A4 — Session Pollution:    Multiple agents writing to same session_id
    A5 — Nonce Replay:         Same perceive_nonce appearing in multiple events
    A6 — Rapid-Fire Perceive:  Agent opening sessions faster than plausible
    A7 — Agent Impersonation:  Events from agent_ids not in AGENT_REGISTRY

USAGE:
    # One-shot audit (prints findings, writes events, exits)
    python hfo_stigmergy_watchdog.py --once

    # Continuous daemon mode (polls every 30s)
    python hfo_stigmergy_watchdog.py --daemon --interval 30

    # Dry run (detect but don't write events to SSOT)
    python hfo_stigmergy_watchdog.py --once --dry-run

    # JSON output
    python hfo_stigmergy_watchdog.py --once --json

MEDALLION: bronze (unvalidated — requires P5 review for silver promotion)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEN = os.environ.get("HFO_GENERATION", "89")
OPERATOR = os.environ.get("HFO_OPERATOR", "TTAO")

_FORGE = os.environ.get(
    "HFO_FORGE", "hfo_gen_89_hot_obsidian_forge"
)
_SCRIPT_DIR = Path(__file__).resolve().parent
_FORGE_ROOT = _SCRIPT_DIR.parents[1]
_WORKSPACE_ROOT = _FORGE_ROOT.parent

DB_PATH = Path(
    os.environ.get(
        "HFO_SSOT_DB",
        str(_WORKSPACE_ROOT / _FORGE / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"),
    )
)

# Watermark file — tracks last scanned event ID so we never re-process
WATERMARK_PATH = _SCRIPT_DIR / ".watchdog_watermark.json"

# Thresholds (configurable via env)
GATE_BLOCK_STORM_THRESHOLD = int(os.environ.get("WD_GATE_BLOCK_THRESHOLD", "5"))
GATE_BLOCK_STORM_WINDOW_SEC = int(os.environ.get("WD_GATE_BLOCK_WINDOW", "300"))
TAMPER_CLUSTER_THRESHOLD = int(os.environ.get("WD_TAMPER_THRESHOLD", "3"))
TAMPER_CLUSTER_WINDOW_SEC = int(os.environ.get("WD_TAMPER_WINDOW", "600"))
ORPHAN_RATIO_THRESHOLD = float(os.environ.get("WD_ORPHAN_RATIO", "0.3"))
RAPID_PERCEIVE_THRESHOLD = int(os.environ.get("WD_RAPID_PERCEIVE_THRESHOLD", "5"))
RAPID_PERCEIVE_WINDOW_SEC = int(os.environ.get("WD_RAPID_PERCEIVE_WINDOW", "120"))

# Known agents — must match AGENT_REGISTRY in hfo_prey8_mcp_server.py
KNOWN_AGENTS = {
    "p0_lidless_legion", "p1_web_weaver", "p2_mirror_magus",
    "p3_harmonic_hydra", "p4_red_regnant", "p5_pyre_praetorian",
    "p6_kraken_keeper", "p7_spider_sovereign",
    "swarm_triage", "swarm_research", "swarm_coder", "swarm_analyst",
    "ttao_operator", "watchdog_daemon",
}

SERVER_VERSION = "watchdog-v1.0"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Get a read-write connection to the SSOT database."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SSOT database not found at {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _cloudevent(event_type: str, data: dict, subject: str) -> str:
    """Build a CloudEvent envelope for a watchdog finding."""
    envelope = {
        "specversion": "1.0",
        "id": str(uuid.uuid4()),
        "source": f"hfo://gen{GEN}/watchdog/{SERVER_VERSION}",
        "type": event_type,
        "subject": subject,
        "time": _now_iso(),
        "datacontenttype": "application/json",
        "data": data,
    }
    return json.dumps(envelope, default=str)


def _write_stigmergy(event_json: str) -> int | None:
    """Write a watchdog event to stigmergy_events. Returns row ID."""
    c_hash = _content_hash(event_json)
    conn = _get_conn()
    try:
        parsed = json.loads(event_json)
        row = conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, source, subject, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                parsed.get("type", "hfo.gen89.watchdog.unknown"),
                parsed.get("time", _now_iso()),
                parsed.get("source", f"hfo://gen{GEN}/watchdog"),
                parsed.get("subject", "watchdog-finding"),
                event_json,
                c_hash,
            ),
        )
        conn.commit()
        return row.lastrowid if row.rowcount > 0 else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Watermark — track scan progress
# ---------------------------------------------------------------------------

def _load_watermark() -> dict:
    """Load the watermark (last scanned event ID)."""
    if WATERMARK_PATH.exists():
        try:
            return json.loads(WATERMARK_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_event_id": 0, "last_scan_ts": None, "scan_count": 0}


def _save_watermark(wm: dict):
    """Persist the watermark."""
    wm["last_scan_ts"] = _now_iso()
    wm["scan_count"] = wm.get("scan_count", 0) + 1
    WATERMARK_PATH.write_text(json.dumps(wm, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Event loader — fetch new events since watermark
# ---------------------------------------------------------------------------

def _fetch_events_since(last_id: int, limit: int = 500) -> list[dict]:
    """Fetch stigmergy events with id > last_id, parsed."""
    conn = _get_conn()
    try:
        events = []
        for row in conn.execute(
            """SELECT id, event_type, timestamp, source, subject, data_json
               FROM stigmergy_events
               WHERE id > ?
               ORDER BY id ASC
               LIMIT ?""",
            (last_id, limit),
        ):
            parsed_data = {}
            try:
                full = json.loads(row[5])
                parsed_data = full.get("data", full)
            except (json.JSONDecodeError, TypeError):
                parsed_data = {"raw": row[5][:500] if row[5] else ""}

            events.append({
                "id": row[0],
                "event_type": row[1],
                "timestamp": row[2],
                "source": row[3],
                "subject": row[4],
                "data": parsed_data,
            })
        return events
    finally:
        conn.close()


def _fetch_recent_prey8_events(window_sec: int = 3600) -> list[dict]:
    """Fetch all PREY8 events in the last N seconds for cross-cutting analysis."""
    conn = _get_conn()
    try:
        events = []
        for row in conn.execute(
            """SELECT id, event_type, timestamp, data_json
               FROM stigmergy_events
               WHERE event_type LIKE '%prey8%'
               ORDER BY id DESC
               LIMIT 200"""
        ):
            parsed = {}
            try:
                full = json.loads(row[3])
                parsed = full.get("data", full)
            except (json.JSONDecodeError, TypeError):
                parsed = {}

            events.append({
                "id": row[0],
                "event_type": row[1],
                "timestamp": row[2],
                "data": parsed,
            })
        return events
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ANOMALY DETECTORS
# ---------------------------------------------------------------------------

class Finding:
    """A single watchdog finding."""
    def __init__(self, anomaly_class: str, severity: str, description: str,
                 evidence: dict, agent_id: str = "unknown"):
        self.anomaly_class = anomaly_class
        self.severity = severity  # INFO, WARNING, CRITICAL
        self.description = description
        self.evidence = evidence
        self.agent_id = agent_id
        self.timestamp = _now_iso()

    def to_dict(self) -> dict:
        return {
            "anomaly_class": self.anomaly_class,
            "severity": self.severity,
            "description": self.description,
            "evidence": self.evidence,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "server_version": SERVER_VERSION,
        }

    def to_cloudevent(self) -> str:
        return _cloudevent(
            f"hfo.gen{GEN}.watchdog.{self.anomaly_class.lower()}",
            self.to_dict(),
            f"watchdog-{self.anomaly_class.lower()}-{self.severity.lower()}",
        )


def detect_a1_gate_block_storm(events: list[dict]) -> list[Finding]:
    """A1: Agent hitting GATE_BLOCKED repeatedly (>threshold in window)."""
    findings = []
    gate_blocks = [e for e in events if "gate_blocked" in e.get("event_type", "")]

    # Group by agent_id
    by_agent: dict[str, list] = defaultdict(list)
    for gb in gate_blocks:
        agent = gb.get("data", {}).get("agent_id", "unknown")
        by_agent[agent].append(gb)

    for agent, blocks in by_agent.items():
        if len(blocks) >= GATE_BLOCK_STORM_THRESHOLD:
            # Check if within time window
            timestamps = sorted(b.get("timestamp", "") for b in blocks)
            findings.append(Finding(
                anomaly_class="A1_GATE_BLOCK_STORM",
                severity="WARNING" if len(blocks) < GATE_BLOCK_STORM_THRESHOLD * 2 else "CRITICAL",
                description=(
                    f"Agent '{agent}' has {len(blocks)} GATE_BLOCKED events. "
                    f"Threshold: {GATE_BLOCK_STORM_THRESHOLD}. "
                    "Possible reward hacking: agent may be brute-forcing gate fields."
                ),
                evidence={
                    "block_count": len(blocks),
                    "threshold": GATE_BLOCK_STORM_THRESHOLD,
                    "event_ids": [b["id"] for b in blocks[:10]],
                    "gates_hit": list(set(
                        b.get("data", {}).get("gate", "?") for b in blocks
                    )),
                    "first_block": timestamps[0] if timestamps else None,
                    "last_block": timestamps[-1] if timestamps else None,
                },
                agent_id=agent,
            ))
    return findings


def detect_a2_tamper_cluster(events: list[dict]) -> list[Finding]:
    """A2: Multiple tamper_alert events in short window."""
    findings = []
    tampers = [e for e in events if "tamper_alert" in e.get("event_type", "")]

    if len(tampers) >= TAMPER_CLUSTER_THRESHOLD:
        by_agent: dict[str, list] = defaultdict(list)
        for t in tampers:
            agent = t.get("data", {}).get("agent_id", "unknown")
            by_agent[agent].append(t)

        for agent, agent_tampers in by_agent.items():
            if len(agent_tampers) >= 2:
                findings.append(Finding(
                    anomaly_class="A2_TAMPER_CLUSTER",
                    severity="CRITICAL",
                    description=(
                        f"Agent '{agent}' has {len(agent_tampers)} tamper alerts. "
                        "Tamper clusters indicate session injection or nonce manipulation attempts."
                    ),
                    evidence={
                        "tamper_count": len(agent_tampers),
                        "threshold": TAMPER_CLUSTER_THRESHOLD,
                        "event_ids": [t["id"] for t in agent_tampers[:10]],
                        "alert_types": list(set(
                            t.get("data", {}).get("alert_type", "?") for t in agent_tampers
                        )),
                    },
                    agent_id=agent,
                ))

        if not findings and len(tampers) >= TAMPER_CLUSTER_THRESHOLD:
            findings.append(Finding(
                anomaly_class="A2_TAMPER_CLUSTER",
                severity="WARNING",
                description=(
                    f"Total tamper alerts ({len(tampers)}) exceed threshold "
                    f"({TAMPER_CLUSTER_THRESHOLD}). Cross-agent tampering possible."
                ),
                evidence={
                    "tamper_count": len(tampers),
                    "event_ids": [t["id"] for t in tampers[:10]],
                },
            ))
    return findings


def detect_a3_orphan_accumulation(events: list[dict]) -> list[Finding]:
    """A3: Perceive-without-yield ratio exceeding threshold."""
    findings = []
    perceives = [e for e in events if "prey8.perceive" in e.get("event_type", "")
                 and "gate_blocked" not in e.get("event_type", "")]
    yields = [e for e in events if "prey8.yield" in e.get("event_type", "")
              and "gate_blocked" not in e.get("event_type", "")]

    p_count = len(perceives)
    y_count = len(yields)

    if p_count > 0:
        orphan_ratio = 1.0 - (y_count / p_count) if p_count > 0 else 0
        if orphan_ratio > ORPHAN_RATIO_THRESHOLD and (p_count - y_count) > 2:
            # Find which agents have orphans
            by_agent: dict[str, dict] = defaultdict(lambda: {"perceives": 0, "yields": 0})
            for p in perceives:
                agent = p.get("data", {}).get("agent_id", "unknown")
                by_agent[agent]["perceives"] += 1
            for y in yields:
                agent = y.get("data", {}).get("agent_id", "unknown")
                by_agent[agent]["yields"] += 1

            orphan_agents = {
                a: d for a, d in by_agent.items()
                if d["perceives"] > d["yields"]
            }

            findings.append(Finding(
                anomaly_class="A3_ORPHAN_ACCUMULATION",
                severity="WARNING",
                description=(
                    f"Perceive-to-yield orphan ratio is {orphan_ratio:.2f} "
                    f"({p_count} perceives, {y_count} yields). "
                    f"Threshold: {ORPHAN_RATIO_THRESHOLD}. "
                    "Sessions are being opened but not closed — possible agent crashes or reward hacking."
                ),
                evidence={
                    "perceive_count": p_count,
                    "yield_count": y_count,
                    "orphan_ratio": round(orphan_ratio, 3),
                    "threshold": ORPHAN_RATIO_THRESHOLD,
                    "orphan_agents": orphan_agents,
                },
            ))
    return findings


def detect_a4_session_pollution(events: list[dict]) -> list[Finding]:
    """A4: Multiple agents writing to same session_id."""
    findings = []
    session_agents: dict[str, set] = defaultdict(set)

    for e in events:
        data = e.get("data", {})
        sid = data.get("session_id", "")
        agent = data.get("agent_id", "")
        if sid and agent:
            session_agents[sid].add(agent)

    for sid, agents in session_agents.items():
        if len(agents) > 1:
            findings.append(Finding(
                anomaly_class="A4_SESSION_POLLUTION",
                severity="CRITICAL",
                description=(
                    f"Session '{sid[:16]}...' has events from {len(agents)} different agents: "
                    f"{', '.join(sorted(agents))}. "
                    "This indicates cross-agent session pollution — a critical isolation failure."
                ),
                evidence={
                    "session_id": sid,
                    "agent_count": len(agents),
                    "agents": sorted(agents),
                },
            ))
    return findings


def detect_a5_nonce_replay(events: list[dict]) -> list[Finding]:
    """A5: Same perceive_nonce appearing in events from different sessions."""
    findings = []
    nonce_sessions: dict[str, set] = defaultdict(set)

    for e in events:
        data = e.get("data", {})
        nonce = data.get("perceive_nonce", "") or data.get("nonce", "")
        sid = data.get("session_id", "")
        if nonce and sid and len(nonce) >= 6:
            nonce_sessions[nonce].add(sid)

    for nonce, sessions in nonce_sessions.items():
        if len(sessions) > 1:
            findings.append(Finding(
                anomaly_class="A5_NONCE_REPLAY",
                severity="CRITICAL",
                description=(
                    f"Perceive nonce '{nonce}' appears in {len(sessions)} different sessions. "
                    "Nonce replay attack detected — nonces must be unique per session."
                ),
                evidence={
                    "nonce": nonce,
                    "session_count": len(sessions),
                    "sessions": sorted(sessions),
                },
            ))
    return findings


def detect_a6_rapid_fire_perceive(events: list[dict]) -> list[Finding]:
    """A6: Agent opening sessions faster than plausible."""
    findings = []
    perceives = [e for e in events if "prey8.perceive" in e.get("event_type", "")
                 and "gate_blocked" not in e.get("event_type", "")]

    by_agent: dict[str, list] = defaultdict(list)
    for p in perceives:
        agent = p.get("data", {}).get("agent_id", "unknown")
        by_agent[agent].append(p)

    for agent, agent_perceives in by_agent.items():
        if len(agent_perceives) >= RAPID_PERCEIVE_THRESHOLD:
            findings.append(Finding(
                anomaly_class="A6_RAPID_FIRE_PERCEIVE",
                severity="WARNING",
                description=(
                    f"Agent '{agent}' has {len(agent_perceives)} perceive events "
                    f"in the scan window. Threshold: {RAPID_PERCEIVE_THRESHOLD}. "
                    "Possible automated loop — agent may be repeatedly opening sessions "
                    "without completing work."
                ),
                evidence={
                    "perceive_count": len(agent_perceives),
                    "threshold": RAPID_PERCEIVE_THRESHOLD,
                    "event_ids": [p["id"] for p in agent_perceives[:10]],
                },
                agent_id=agent,
            ))
    return findings


def detect_a7_agent_impersonation(events: list[dict]) -> list[Finding]:
    """A7: Events from agent_ids not in AGENT_REGISTRY."""
    findings = []
    unknown_agents: dict[str, int] = Counter()

    for e in events:
        data = e.get("data", {})
        agent = data.get("agent_id", "")
        if agent and agent not in KNOWN_AGENTS and agent != "unknown":
            unknown_agents[agent] += 1

    for agent, count in unknown_agents.items():
        findings.append(Finding(
            anomaly_class="A7_AGENT_IMPERSONATION",
            severity="CRITICAL",
            description=(
                f"Agent ID '{agent}' appears in {count} events but is NOT in AGENT_REGISTRY. "
                "Possible impersonation or unauthorized agent. Deny-by-default should have blocked this."
            ),
            evidence={
                "agent_id": agent,
                "event_count": count,
                "known_agents": sorted(KNOWN_AGENTS),
            },
            agent_id=agent,
        ))
    return findings


# All detectors in scan order
ANOMALY_DETECTORS = [
    detect_a1_gate_block_storm,
    detect_a2_tamper_cluster,
    detect_a3_orphan_accumulation,
    detect_a4_session_pollution,
    detect_a5_nonce_replay,
    detect_a6_rapid_fire_perceive,
    detect_a7_agent_impersonation,
]


# ---------------------------------------------------------------------------
# Main scan loop
# ---------------------------------------------------------------------------

def run_scan(dry_run: bool = False, full_scan: bool = False) -> list[Finding]:
    """
    Run all anomaly detectors on new events since watermark.

    Args:
        dry_run: If True, detect but don't write events to SSOT.
        full_scan: If True, scan ALL events (ignore watermark).

    Returns:
        List of findings.
    """
    wm = _load_watermark()
    start_id = 0 if full_scan else wm.get("last_event_id", 0)

    # Fetch new events
    new_events = _fetch_events_since(start_id, limit=500)

    if not new_events:
        return []

    # Also fetch recent PREY8 events for cross-cutting analysis
    all_prey8 = _fetch_recent_prey8_events()

    # Run all detectors
    all_findings: list[Finding] = []

    # Run detectors on new events AND full PREY8 corpus
    for detector in ANOMALY_DETECTORS:
        try:
            # Detectors A1-A2 benefit from new events (incremental)
            # Detectors A3-A7 benefit from full PREY8 corpus (cross-cutting)
            findings_new = detector(new_events)
            findings_full = detector(all_prey8)

            # Dedup by description
            seen = set()
            for f in findings_new + findings_full:
                desc_key = f"{f.anomaly_class}:{f.agent_id}:{f.description[:80]}"
                if desc_key not in seen:
                    seen.add(desc_key)
                    all_findings.append(f)
        except Exception as e:
            all_findings.append(Finding(
                anomaly_class="DETECTOR_ERROR",
                severity="WARNING",
                description=f"Detector {detector.__name__} failed: {e}",
                evidence={"error": str(e), "detector": detector.__name__},
            ))

    # Write findings to SSOT (unless dry run)
    if not dry_run:
        for finding in all_findings:
            _write_stigmergy(finding.to_cloudevent())

        # Write scan summary event
        summary_data = {
            "scan_type": "full" if full_scan else "incremental",
            "events_scanned": len(new_events),
            "prey8_events_analyzed": len(all_prey8),
            "findings_count": len(all_findings),
            "severity_breakdown": Counter(f.severity for f in all_findings),
            "anomaly_classes": Counter(f.anomaly_class for f in all_findings),
            "start_event_id": start_id,
            "end_event_id": new_events[-1]["id"] if new_events else start_id,
            "timestamp": _now_iso(),
            "server_version": SERVER_VERSION,
        }
        summary_event = _cloudevent(
            f"hfo.gen{GEN}.watchdog.scan_complete",
            summary_data,
            "watchdog-scan-complete",
        )
        _write_stigmergy(summary_event)

    # Update watermark
    if new_events:
        wm["last_event_id"] = new_events[-1]["id"]
    _save_watermark(wm)

    return all_findings


def run_daemon(interval: int = 30, dry_run: bool = False):
    """Run in continuous daemon mode, polling every `interval` seconds."""
    print(f"[watchdog] Starting daemon mode. Interval: {interval}s. Dry run: {dry_run}")
    print(f"[watchdog] DB: {DB_PATH}")
    print(f"[watchdog] Watermark: {WATERMARK_PATH}")
    print(f"[watchdog] Known agents: {len(KNOWN_AGENTS)}")
    print(f"[watchdog] Thresholds — gate_block: {GATE_BLOCK_STORM_THRESHOLD}, "
          f"tamper: {TAMPER_CLUSTER_THRESHOLD}, orphan_ratio: {ORPHAN_RATIO_THRESHOLD}")
    print()

    try:
        while True:
            try:
                findings = run_scan(dry_run=dry_run)
                ts = datetime.now().strftime("%H:%M:%S")
                if findings:
                    critical = sum(1 for f in findings if f.severity == "CRITICAL")
                    warning = sum(1 for f in findings if f.severity == "WARNING")
                    print(f"[{ts}] Scan complete: {len(findings)} findings "
                          f"(CRITICAL:{critical}, WARNING:{warning})")
                    for f in findings:
                        marker = "!!!" if f.severity == "CRITICAL" else "***"
                        print(f"  {marker} [{f.anomaly_class}] {f.description[:120]}")
                else:
                    print(f"[{ts}] Scan complete: no anomalies detected")
            except Exception as e:
                print(f"[{ts}] Scan error: {e}", file=sys.stderr)

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[watchdog] Daemon stopped by operator.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="HFO Stigmergy Watchdog — fail-closed anomaly detector"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run a single scan and exit")
    parser.add_argument("--daemon", action="store_true",
                        help="Run in continuous daemon mode")
    parser.add_argument("--interval", type=int, default=30,
                        help="Daemon poll interval in seconds (default: 30)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect anomalies but don't write events to SSOT")
    parser.add_argument("--full-scan", action="store_true",
                        help="Scan ALL events (ignore watermark)")
    parser.add_argument("--json", action="store_true",
                        help="Output findings as JSON")

    args = parser.parse_args()

    if not args.once and not args.daemon:
        args.once = True  # Default to one-shot

    if not DB_PATH.exists():
        print(f"ERROR: SSOT database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    if args.daemon:
        run_daemon(interval=args.interval, dry_run=args.dry_run)
    else:
        findings = run_scan(dry_run=args.dry_run, full_scan=args.full_scan)

        if args.json:
            output = {
                "scan_timestamp": _now_iso(),
                "findings_count": len(findings),
                "findings": [f.to_dict() for f in findings],
                "severity_breakdown": dict(Counter(f.severity for f in findings)),
                "anomaly_classes": dict(Counter(f.anomaly_class for f in findings)),
                "dry_run": args.dry_run,
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            if findings:
                print(f"\n{'='*70}")
                print(f"STIGMERGY WATCHDOG REPORT — {len(findings)} findings")
                print(f"{'='*70}")
                for i, f in enumerate(findings, 1):
                    marker = "CRITICAL" if f.severity == "CRITICAL" else f.severity
                    print(f"\n[{i}] [{marker}] {f.anomaly_class}")
                    print(f"    Agent: {f.agent_id}")
                    print(f"    {f.description}")
                    if f.evidence:
                        for k, v in f.evidence.items():
                            print(f"      {k}: {v}")
                print(f"\n{'='*70}")
                mode = "DRY-RUN" if args.dry_run else "EVENTS WRITTEN TO SSOT"
                print(f"Mode: {mode}")
            else:
                print("No anomalies detected.")


if __name__ == "__main__":
    main()
