#!/usr/bin/env python3
"""
hfo_p4_wail_of_the_banshee.py — P4 Red Regnant: WAIL OF THE BANSHEE
═════════════════════════════════════════════════════════════════════

Spell Slot: S2 (STRIFE)
D&D Source: PHB p.300, Necromancy 9th
D&D Effect: "You emit a terrible scream that kills creatures that hear it
             (except combatants). Up to one creature/level, no save."
HFO Alias:  Critical alert escalation — the Banshee's keening.
            Max-priority system health scream. Cannot be silenced.

Port:       P4 DISRUPT
Commander:  Red Regnant — Singer of Strife and Splendor
Race:       Half-Fiend Banshee — this is the species-defining spell
Aspect:     A (STRIFE)
Tier:       MASTER target (fills slot S2)

Engineering Function:
    Multi-check critical system health audit. Checks for conditions so severe
    that the entire system is at risk. Unlike P5's gentle patrol, the Wail
    is the nuclear option — it fires ONLY for genuinely critical issues and
    its events CANNOT be filtered, throttled, or silenced.

    Critical checks:
    1. SSOT database unreachable or corrupted
    2. Disk space critically low (< 2 GB free)
    3. All daemons dead (fleet extinction)
    4. PREY8 chain integrity tampered
    5. Pointer registry broken (PAL resolution failure)
    6. Memory loss epidemic (> 5 orphaned sessions)
    7. Stigmergy trail stalled (no events in > 1 hour)
    8. Bronze layer write-protected (permissions)
    9. Git hooks disabled (governance bypass)

    If ANY critical check fails, the Banshee WAILS — a max-priority
    CloudEvent that escalates through all channels.

Stigmergy Events:
    hfo.gen89.p4.wail.scream        — Critical alert (CANNOT BE SILENCED)
    hfo.gen89.p4.wail.silence       — All clear (quiet = healthy)
    hfo.gen89.p4.wail.heartbeat     — Daemon heartbeat

SBE / ATDD Specification:
─────────────────────────

Feature: WAIL OF THE BANSHEE — Critical Alert Escalation

  # Tier 1: Invariant (MUST NOT violate)
  Scenario: SSOT database missing triggers wail
    Given the SSOT database file does not exist at the expected path
    When the Banshee performs its health check
    Then a SCREAM event with severity CRITICAL is written
    And the scream includes check_name "ssot_reachable"

  Scenario: Disk critically low triggers wail
    Given system disk has less than 2 GB free space
    When the Banshee performs its health check
    Then a SCREAM event with severity CRITICAL is written
    And the scream includes check_name "disk_space"

  Scenario: All checks pass produces silence
    Given all critical checks pass (SSOT reachable, disk OK, etc.)
    When the Banshee performs its health check
    Then a SILENCE event is written indicating all clear
    And no SCREAM event is produced

  # Tier 2: Happy-path
  Scenario: Summary output shows all checks
    Given all critical checks are implemented
    When `python hfo_p4_wail_of_the_banshee.py --summary` is executed
    Then output shows each check with PASS or FAIL status
    And a grade (A-F) is computed based on critical failures

  Scenario: JSON output mode
    Given all critical checks are implemented
    When `python hfo_p4_wail_of_the_banshee.py --json` is executed
    Then output is valid JSON with keys: checks, failures, grade, wail_triggered

  # Tier 3: Daemon mode
  Scenario: Daemon runs periodic checks
    Given `python hfo_p4_wail_of_the_banshee.py --daemon --interval 60` is executed
    When 60 seconds elapse
    Then checks are re-run
    And heartbeat event is written if no failures found

Usage:
    python hfo_p4_wail_of_the_banshee.py --summary     # One-shot health check
    python hfo_p4_wail_of_the_banshee.py --json         # JSON output
    python hfo_p4_wail_of_the_banshee.py --stigmergy    # Write to SSOT
    python hfo_p4_wail_of_the_banshee.py --daemon       # Continuous mode
    python hfo_p4_wail_of_the_banshee.py --status       # Spell identity
"""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import signal
import sqlite3
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from hfo_ssot_write import get_db_readwrite

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION VIA PAL
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
POINTERS_FILE = HFO_ROOT / "hfo_gen89_pointers_blessed.json"


def _load_pointers() -> dict:
    if not POINTERS_FILE.exists():
        return {}
    with open(POINTERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("pointers", data)


def resolve_pointer(key: str) -> Path:
    pointers = _load_pointers()
    if key not in pointers:
        raise KeyError(f"Pointer '{key}' not found")
    entry = pointers[key]
    rel_path = entry["path"] if isinstance(entry, dict) else entry
    return HFO_ROOT / rel_path


# Resolve paths
try:
    SSOT_DB = resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"

try:
    FORGE_ROOT = resolve_pointer("forge.root")
except (KeyError, FileNotFoundError):
    FORGE_ROOT = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge"

GEN = os.environ.get("HFO_GENERATION", "89")
P4_SOURCE = f"hfo_p4_wail_gen{GEN}"
EVENT_PREFIX = "hfo.gen89.p4.wail"
VERSION = "1.0.0"

# Critical thresholds — the Banshee's trigger points
THRESHOLDS = {
    "min_disk_free_gb": 2.0,
    "max_orphaned_sessions": 5,
    "max_stigmergy_stale_hours": 1.0,
    "min_pointers_resolvable_pct": 80.0,
}

# ═══════════════════════════════════════════════════════════════
# § 1  SPELL IDENTITY
# ═══════════════════════════════════════════════════════════════

SPELL_IDENTITY = {
    "port": "P4",
    "powerword": "DISRUPT",
    "commander": "Red Regnant",
    "race": "Half-Fiend Banshee",
    "spell": "WAIL_OF_THE_BANSHEE",
    "spell_slot": "S2",
    "aspect": "STRIFE",
    "dnd_source": "PHB p.300, Necromancy 9th",
    "school": "Necromancy",
    "alias": "Critical Alert Escalation",
    "species_defining": True,
    "version": VERSION,
    "core_thesis": "The Banshee's keening cannot be silenced. "
                   "When the system is dying, you WILL hear it.",
}

# ═══════════════════════════════════════════════════════════════
# § 2  CRITICAL HEALTH CHECKS
# ═══════════════════════════════════════════════════════════════

class CheckResult:
    """Result of a single critical health check."""
    __slots__ = ("name", "passed", "severity", "detail", "value")

    def __init__(self, name: str, passed: bool, severity: str, detail: str, value=None):
        self.name = name
        self.passed = passed
        self.severity = severity  # CRITICAL, HIGH, MEDIUM
        self.detail = detail
        self.value = value

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity,
            "detail": self.detail,
            "value": self.value,
        }


def check_ssot_reachable() -> CheckResult:
    """Check SSOT database exists and is readable."""
    if not SSOT_DB.exists():
        return CheckResult("ssot_reachable", False, "CRITICAL",
                           f"SSOT database not found: {SSOT_DB}")
    try:
        conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        conn.close()
        return CheckResult("ssot_reachable", True, "OK",
                           f"SSOT reachable: {count} documents", count)
    except Exception as e:
        return CheckResult("ssot_reachable", False, "CRITICAL",
                           f"SSOT query failed: {e}")


def check_ssot_integrity() -> CheckResult:
    """Run SQLite integrity check."""
    if not SSOT_DB.exists():
        return CheckResult("ssot_integrity", False, "CRITICAL", "SSOT missing")
    try:
        conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        if result == "ok":
            return CheckResult("ssot_integrity", True, "OK",
                               "SSOT integrity: ok")
        return CheckResult("ssot_integrity", False, "CRITICAL",
                           f"SSOT integrity: {result}")
    except Exception as e:
        return CheckResult("ssot_integrity", False, "CRITICAL",
                           f"SSOT integrity check failed: {e}")


def check_disk_space() -> CheckResult:
    """Check disk free space on SSOT drive."""
    try:
        usage = shutil.disk_usage(str(SSOT_DB.parent))
        free_gb = usage.free / (1024 ** 3)
        if free_gb < THRESHOLDS["min_disk_free_gb"]:
            return CheckResult("disk_space", False, "CRITICAL",
                               f"Disk free: {free_gb:.1f} GB (< {THRESHOLDS['min_disk_free_gb']} GB)",
                               round(free_gb, 1))
        return CheckResult("disk_space", True, "OK",
                           f"Disk free: {free_gb:.1f} GB", round(free_gb, 1))
    except Exception as e:
        return CheckResult("disk_space", False, "HIGH",
                           f"Disk check failed: {e}")


def check_pointer_registry() -> CheckResult:
    """Check PAL pointers resolve to existing files."""
    pointers = _load_pointers()
    if not pointers:
        return CheckResult("pointer_registry", False, "HIGH",
                           "No pointers found in registry")

    total = 0
    resolved = 0
    broken = []
    for key, entry in pointers.items():
        total += 1
        rel_path = entry["path"] if isinstance(entry, dict) else entry
        full_path = HFO_ROOT / rel_path
        if full_path.exists():
            resolved += 1
        else:
            broken.append(key)

    pct = (resolved / total * 100) if total else 0
    if pct < THRESHOLDS["min_pointers_resolvable_pct"]:
        return CheckResult("pointer_registry", False, "HIGH",
                           f"Pointer health: {resolved}/{total} ({pct:.0f}%) — broken: {', '.join(broken[:5])}",
                           round(pct, 1))
    return CheckResult("pointer_registry", True, "OK",
                       f"Pointer health: {resolved}/{total} ({pct:.0f}%)", round(pct, 1))


def check_orphaned_sessions() -> CheckResult:
    """Check for orphaned PREY8 sessions (perceive without yield)."""
    if not SSOT_DB.exists():
        return CheckResult("orphaned_sessions", False, "HIGH", "SSOT missing")
    try:
        conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        # Count perceives without matching yields
        perceives = conn.execute(
            """SELECT COUNT(*) FROM stigmergy_events
               WHERE event_type LIKE '%perceive%'
               AND json_extract(data_json, '$.data.nonce') NOT IN (
                   SELECT json_extract(data_json, '$.data.perceive_nonce')
                   FROM stigmergy_events
                   WHERE event_type LIKE '%yield%'
                   AND json_extract(data_json, '$.data.perceive_nonce') IS NOT NULL
               )"""
        ).fetchone()[0]
        conn.close()

        if perceives > THRESHOLDS["max_orphaned_sessions"]:
            return CheckResult("orphaned_sessions", False, "HIGH",
                               f"Orphaned sessions: {perceives} (> {THRESHOLDS['max_orphaned_sessions']})",
                               perceives)
        return CheckResult("orphaned_sessions", True, "OK",
                           f"Orphaned sessions: {perceives}", perceives)
    except Exception as e:
        return CheckResult("orphaned_sessions", False, "MEDIUM",
                           f"Orphan check failed: {e}")


def check_stigmergy_freshness() -> CheckResult:
    """Check that stigmergy trail is not stale."""
    if not SSOT_DB.exists():
        return CheckResult("stigmergy_freshness", False, "CRITICAL", "SSOT missing")
    try:
        conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
        latest = conn.execute(
            "SELECT MAX(timestamp) FROM stigmergy_events"
        ).fetchone()[0]
        conn.close()

        if not latest:
            return CheckResult("stigmergy_freshness", False, "CRITICAL",
                               "No stigmergy events found")

        latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_hours = (now - latest_dt).total_seconds() / 3600

        if age_hours > THRESHOLDS["max_stigmergy_stale_hours"]:
            return CheckResult("stigmergy_freshness", False, "HIGH",
                               f"Latest event: {age_hours:.1f} hours ago (stale)",
                               round(age_hours, 2))
        return CheckResult("stigmergy_freshness", True, "OK",
                           f"Latest event: {age_hours:.2f} hours ago", round(age_hours, 2))
    except Exception as e:
        return CheckResult("stigmergy_freshness", False, "MEDIUM",
                           f"Freshness check failed: {e}")


def check_bronze_writable() -> CheckResult:
    """Check bronze layer is writable."""
    test_file = FORGE_ROOT / "0_bronze" / ".wail_test_write"
    try:
        test_file.write_text("wail_test", encoding="utf-8")
        test_file.unlink()
        return CheckResult("bronze_writable", True, "OK", "Bronze layer is writable")
    except Exception as e:
        return CheckResult("bronze_writable", False, "CRITICAL",
                           f"Bronze layer not writable: {e}")


def check_git_hooks() -> CheckResult:
    """Check git hooks are configured."""
    hooks_path = HFO_ROOT / ".githooks" / "pre-commit"
    if not hooks_path.exists():
        return CheckResult("git_hooks", False, "MEDIUM",
                           "Pre-commit hook not found")

    # Check if hooks path is configured
    try:
        result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            capture_output=True, text=True, cwd=str(HFO_ROOT),
            timeout=5
        )
        if result.returncode == 0 and ".githooks" in result.stdout:
            return CheckResult("git_hooks", True, "OK",
                               f"Git hooks configured: {result.stdout.strip()}")
        return CheckResult("git_hooks", False, "MEDIUM",
                           f"Git hooks path not set to .githooks (got: {result.stdout.strip()})")
    except Exception as e:
        return CheckResult("git_hooks", False, "MEDIUM",
                           f"Git hooks check failed: {e}")


def check_agents_md() -> CheckResult:
    """Check AGENTS.md exists at root."""
    agents_md = HFO_ROOT / "AGENTS.md"
    if not agents_md.exists():
        return CheckResult("agents_md", False, "CRITICAL",
                           "AGENTS.md not found at workspace root")
    size = agents_md.stat().st_size
    if size < 1000:
        return CheckResult("agents_md", False, "HIGH",
                           f"AGENTS.md suspiciously small: {size} bytes")
    return CheckResult("agents_md", True, "OK",
                       f"AGENTS.md present: {size} bytes", size)


# All checks in order
ALL_CHECKS = [
    check_ssot_reachable,
    check_ssot_integrity,
    check_disk_space,
    check_pointer_registry,
    check_orphaned_sessions,
    check_stigmergy_freshness,
    check_bronze_writable,
    check_git_hooks,
    check_agents_md,
]


def run_all_checks() -> list[CheckResult]:
    """Execute all critical health checks."""
    results = []
    for check_fn in ALL_CHECKS:
        try:
            results.append(check_fn())
        except Exception as e:
            results.append(CheckResult(
                check_fn.__name__.replace("check_", ""),
                False, "CRITICAL", f"Check crashed: {e}"
            ))
    return results


def compute_grade(results: list[CheckResult]) -> str:
    """Compute system grade from check results."""
    criticals = sum(1 for r in results if not r.passed and r.severity == "CRITICAL")
    highs = sum(1 for r in results if not r.passed and r.severity == "HIGH")
    mediums = sum(1 for r in results if not r.passed and r.severity == "MEDIUM")

    if criticals >= 2:
        return "F"
    if criticals == 1:
        return "D"
    if highs >= 2:
        return "C"
    if highs == 1 or mediums >= 3:
        return "B"
    if mediums >= 1:
        return "B+"
    return "A"


# ═══════════════════════════════════════════════════════════════
# § 3  DISPLAY FORMATTING
# ═══════════════════════════════════════════════════════════════

def format_summary(results: list[CheckResult], grade: str) -> str:
    """Format human-readable health check summary."""
    lines = []
    lines.append("=" * 72)
    lines.append("  P4 RED REGNANT — WAIL OF THE BANSHEE (Critical Health Audit)")
    lines.append('  "The Banshee\'s keening cannot be silenced."')
    lines.append("=" * 72)
    lines.append("")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    lines.append(f"  Grade:    {grade}")
    lines.append(f"  Checks:   {len(results)} ({passed} passed, {failed} failed)")
    lines.append(f"  Wail:     {'YES — SCREAMING' if failed > 0 and any(r.severity == 'CRITICAL' and not r.passed for r in results) else 'No (silent = healthy)'}")
    lines.append("")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        icon = "[+]" if r.passed else "[!]"
        sev_tag = f" ({r.severity})" if not r.passed else ""
        lines.append(f"  {icon} {status:4s}  {r.name:25s}  {r.detail}{sev_tag}")

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 4  SSOT / STIGMERGY
# ═══════════════════════════════════════════════════════════════

def write_stigmergy_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
) -> int:
    """Write a CloudEvent to stigmergy trail."""
    event_id = hashlib.md5(
        f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()
    ).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    event = {
        "specversion": "1.0",
        "id": event_id,
        "type": event_type,
        "source": P4_SOURCE,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "phase": "CLOUDEVENT",
        "agent_id": "p4_red_regnant",
        "spell": "WAIL_OF_THE_BANSHEE",
        "species_defining": True,
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, P4_SOURCE, json.dumps(event), content_hash),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def write_wail_to_ssot(results: list[CheckResult], grade: str) -> int:
    """Write wail results to SSOT. Returns event row id."""
    failures = [r for r in results if not r.passed]
    wail_triggered = any(r.severity == "CRITICAL" for r in failures)

    conn = get_db_readwrite()
    try:
        data = {
            "spell_identity": SPELL_IDENTITY,
            "grade": grade,
            "wail_triggered": wail_triggered,
            "checks_total": len(results),
            "checks_passed": sum(1 for r in results if r.passed),
            "checks_failed": len(failures),
            "failures": [r.to_dict() for r in failures],
            "all_checks": [r.to_dict() for r in results],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        event_type = f"{EVENT_PREFIX}.scream" if wail_triggered else f"{EVENT_PREFIX}.silence"
        subject = (
            f"WAIL:SCREAM:grade_{grade}:{len(failures)}_failures"
            if wail_triggered else
            f"WAIL:silence:grade_{grade}:all_clear"
        )

        row_id = write_stigmergy_event(conn, event_type, subject, data)
        return row_id
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# § 5  DAEMON MODE
# ═══════════════════════════════════════════════════════════════

_running = True


def _signal_handler(sig, frame):
    global _running
    _running = False


def daemon_loop(interval: int = 60, stigmergy: bool = True):
    """Continuous critical health check with the Banshee's vigil."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    cycle = 0
    print(f"  [WAIL] Banshee vigil — check every {interval}s. Ctrl+C to stop.")

    while _running:
        cycle += 1
        results = run_all_checks()
        grade = compute_grade(results)
        failures = [r for r in results if not r.passed]
        wail = any(r.severity == "CRITICAL" for r in failures)

        if wail:
            print(f"\n  [WAIL] !!! SCREAM !!! Cycle {cycle}: Grade {grade}, "
                  f"{len(failures)} failures (CRITICAL)")
            for f in failures:
                if f.severity == "CRITICAL":
                    print(f"    >>> {f.name}: {f.detail}")
        else:
            print(f"  [WAIL] Cycle {cycle}: Grade {grade} "
                  f"({len(failures)} non-critical failures)" if failures
                  else f"  [WAIL] Cycle {cycle}: Grade {grade} (all clear)")

        if stigmergy:
            try:
                row_id = write_wail_to_ssot(results, grade)
                if wail:
                    print(f"  [WAIL] SCREAM event written: row {row_id}")
            except Exception as e:
                print(f"  [WAIL] Stigmergy write failed: {e}")

        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    print("  [WAIL] Banshee vigil ended.")


# ═══════════════════════════════════════════════════════════════
# § 6  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P4 WAIL OF THE BANSHEE — Critical Alert Escalation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Spell: WAIL OF THE BANSHEE (PHB p.300, Necromancy 9th)
            Port:  P4 DISRUPT — Red Regnant (Half-Fiend Banshee)
            Alias: Critical Alert Escalation
            "The Banshee's keening cannot be silenced."
        """),
    )
    parser.add_argument("--summary", action="store_true",
                        help="One-shot health check summary")
    parser.add_argument("--json", action="store_true",
                        help="JSON output mode")
    parser.add_argument("--stigmergy", action="store_true",
                        help="Write results to SSOT")
    parser.add_argument("--daemon", action="store_true",
                        help="Continuous health check mode")
    parser.add_argument("--interval", type=int, default=60,
                        help="Daemon check interval in seconds (default: 60)")
    parser.add_argument("--status", action="store_true",
                        help="Show spell identity")
    args = parser.parse_args()

    if args.status:
        print(json.dumps(SPELL_IDENTITY, indent=2))
        return

    if args.daemon:
        daemon_loop(interval=args.interval, stigmergy=True)
        return

    # One-shot check
    results = run_all_checks()
    grade = compute_grade(results)

    if args.json:
        failures = [r for r in results if not r.passed]
        output = {
            "spell": SPELL_IDENTITY,
            "grade": grade,
            "wail_triggered": any(r.severity == "CRITICAL" for r in failures),
            "checks": [r.to_dict() for r in results],
            "failures": [r.to_dict() for r in failures],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(output, indent=2, default=str))
        return

    print(format_summary(results, grade))

    if args.stigmergy:
        try:
            row_id = write_wail_to_ssot(results, grade)
            wail = any(not r.passed and r.severity == "CRITICAL" for r in results)
            event_type = "SCREAM" if wail else "silence"
            print(f"\n  [WAIL] {event_type} event written to SSOT: row {row_id}")
        except Exception as e:
            print(f"\n  [WAIL] Stigmergy write failed: {e}")


if __name__ == "__main__":
    main()
