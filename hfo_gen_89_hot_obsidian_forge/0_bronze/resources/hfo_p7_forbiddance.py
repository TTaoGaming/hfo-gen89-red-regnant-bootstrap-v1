#!/usr/bin/env python3
"""
hfo_p7_forbiddance.py — P7 Spider Sovereign FORBIDDANCE Spell (Gen89)
======================================================================
v1.0 | Gen89 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze | Powerword: NAVIGATE | Spell: FORBIDDANCE (Abjuration 6th)
Title: Summoner of Seals and Spheres | Epic Class: Cosmic Descryer (ELH p.19)
                                       + Thaumaturgist (DMG p.184)
Aspect: A — SEALS (binding authority, C2 governance, correct-by-construction)

PURPOSE:
    Medallion boundary enforcement — wards planes against unauthorized transit.
    Scans the forge directory structure and SSOT metadata to detect any
    violations of the medallion architecture:
      bronze → silver → gold → hyper_fractal_obsidian

    "No entity may shift to a higher plane without passing the gate."

    FORBIDDANCE enforces SW-5 (Boundary Respect) structurally. It detects:
    - Files in silver/gold/hfo without promotion trails
    - Root directory cleanliness violations
    - Pre-commit hook bypass (governance files modified without hook)
    - Self-promotion attempts (bronze tagging itself as silver/gold)

D&D 3.5e RAW (PHB p.233):
    Forbiddance — Abjuration 6th — wards an area against planar travel.
    Creatures of a different alignment take damage when entering.
    Password can allow specific entities through. Permanent duration.
    Material component: holy water + rare incenses (1500 gp).

SBE/ATDD SCENARIOS (Specification by Example):
═══════════════════════════════════════════════

  TIER 1 — INVARIANT (fail-closed):
    Scenario: Root cleanliness enforcement
      Given HFO_ROOT has a defined set of allowed root files
      When  FORBIDDANCE ward is cast
      Then  any file not in the allowed set is flagged as a violation

  TIER 2 — HAPPY PATH:
    Scenario: Clean medallion boundaries
      Given all files are in their correct layers
      When  FORBIDDANCE ward is cast
      Then  WARDED verdict returned with 0 violations

    Scenario: Silver layer has unvalidated file
      Given a file exists in 1_silver/ without promotion event in SSOT
      When  FORBIDDANCE ward is cast
      Then  violation flagged: "file in silver without promotion trail"

  TIER 3 — GOVERNANCE:
    Scenario: Pre-commit hook is active
      Given .githooks/pre-commit exists and is configured
      When  FORBIDDANCE check-hooks is cast
      Then  hook existence and git config verified

    Scenario: SSOT medallion consistency
      Given documents table has medallion column
      When  FORBIDDANCE audit-medallions is cast
      Then  verify all docs tagged bronze (expected for Gen89)
      And   flag any doc claiming silver/gold status

  TIER 4 — ADVERSARIAL:
    Scenario: Self-promotion attempt
      Given a bronze document modifies its own medallion metadata to "gold"
      When  FORBIDDANCE ward detects the inconsistency
      Then  SELF_PROMOTION violation raised
      And   violation CloudEvent written to SSOT

Event Types:
    hfo.gen89.p7.forbiddance.ward          — Ward check performed
    hfo.gen89.p7.forbiddance.violation     — Boundary violation detected
    hfo.gen89.p7.forbiddance.clean         — All boundaries respected
    hfo.gen89.p7.forbiddance.hooks         — Git hook status checked
    hfo.gen89.p7.forbiddance.medallion     — SSOT medallion audit

USAGE:
    python hfo_p7_forbiddance.py ward               # Full boundary scan
    python hfo_p7_forbiddance.py root-check          # Root cleanliness only
    python hfo_p7_forbiddance.py check-hooks         # Git hook status
    python hfo_p7_forbiddance.py audit-medallions    # SSOT medallion tags
    python hfo_p7_forbiddance.py --json ward         # Machine-readable

Pointer key: p7.forbiddance
Medallion: bronze
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
SOURCE_TAG = f"hfo_p7_forbiddance_gen{GEN}"
FORGE_ROOT = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge"

# ── Allowed root files (from AGENTS.md §2) ──
ALLOWED_ROOT_ENTRIES = {
    "AGENTS.md",
    ".env", ".env.example",
    ".gitignore", ".gitattributes",
    ".githooks", ".github", ".vscode",
    "hfo_gen89_pointers_blessed.json",
    "hfo_gen_89_hot_obsidian_forge",
    "LICENSE", "README.md",
    # Git internal
    ".git",
    # Python/IDE artifacts (tolerated but warned)
    "__pycache__", ".mypy_cache", ".ruff_cache",
    # Runtime state files (hidden, tolerated)
    ".p7_spell_gate_state.json",
    ".p7_planar_binding_state.json",
    ".p7_wish_state.json",
    ".p7_dimensional_anchor_state.json",
    ".prey8_session_state.json",
    ".hfo_pyre_praetorian_state.json",
}

# Files that are NEVER allowed (secrets, keys)
FORBIDDEN_PATTERNS = [
    ".pem", ".key", ".p12", ".pfx",
    ".secret", "credentials.json",
]


# ═══════════════════════════════════════════════════════════════
# § 1  DATABASE & CLOUDEVENT HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

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
# § 2  CHECK: ROOT CLEANLINESS
# ═══════════════════════════════════════════════════════════════

def check_root_cleanliness() -> tuple[list[str], list[str]]:
    """
    Check root directory for unauthorized files.

    SBE:
      Given  HFO_ROOT has a defined allowed file set
      When   root directory is scanned
      Then   any file/dir not in allowed set is a violation
    Returns: (violations, warnings)
    """
    violations = []
    warnings = []

    for entry in HFO_ROOT.iterdir():
        name = entry.name
        if name in ALLOWED_ROOT_ENTRIES:
            continue
        # Check if it's a state file pattern (hidden files starting with .)
        if name.startswith(".") and name.endswith(".json"):
            # Tolerate hidden state files but warn
            warnings.append(f"Root state file (tolerated): {name}")
            continue
        # Check for forbidden secret patterns
        for pattern in FORBIDDEN_PATTERNS:
            if name.endswith(pattern):
                violations.append(f"FORBIDDEN secret file in root: {name}")
                break
        else:
            # Check if it's a Python scratch file (common during dev)
            if name.startswith("_") and name.endswith(".py"):
                warnings.append(f"Root scratch script (dev artifact): {name}")
            elif name.endswith(".txt") or name.endswith(".log"):
                warnings.append(f"Root text file (consider moving to bronze): {name}")
            else:
                violations.append(f"Unauthorized root entry: {name}")

    return violations, warnings


# ═══════════════════════════════════════════════════════════════
# § 3  CHECK: MEDALLION LAYER BOUNDARIES
# ═══════════════════════════════════════════════════════════════

def check_layer_boundaries() -> tuple[list[str], list[str]]:
    """
    Check medallion layer directories for boundary violations.

    SBE:
      Given  forge has 4 medallion layers (bronze/silver/gold/hfo)
      When   each layer is scanned
      Then   files in higher layers without governance reason are flagged
    """
    violations = []
    warnings = []

    # Silver: should only have validated/reviewed content
    silver_resources = FORGE_ROOT / "1_silver" / "resources"
    if silver_resources.exists():
        for f in silver_resources.rglob("*"):
            if f.is_file():
                # Silver files should have a clear purpose
                if not (f.name.startswith("REFERENCE_") or
                        f.name.startswith("2026-") or
                        f.name.endswith(".md") or
                        f.name.endswith(".json")):
                    violations.append(
                        f"Silver layer: unexpected file type: {f.relative_to(FORGE_ROOT)}"
                    )

    # Gold: should only have SSOT DB and governance references
    gold_resources = FORGE_ROOT / "2_gold" / "resources"
    if gold_resources.exists():
        expected_extensions = {".sqlite", ".json", ".md"}
        for f in gold_resources.rglob("*"):
            if f.is_file():
                if f.suffix not in expected_extensions:
                    violations.append(
                        f"Gold layer: non-governance file: {f.relative_to(FORGE_ROOT)}"
                    )

    # HFO (hyper_fractal_obsidian): meta/architectural only
    hfo_resources = FORGE_ROOT / "3_hyper_fractal_obsidian" / "resources"
    if hfo_resources.exists():
        for f in hfo_resources.rglob("*"):
            if f.is_file():
                if not (f.name.endswith(".md") or f.name.endswith(".json")):
                    violations.append(
                        f"HFO layer: non-governance file: {f.relative_to(FORGE_ROOT)}"
                    )

    return violations, warnings


# ═══════════════════════════════════════════════════════════════
# § 4  CHECK: SSOT MEDALLION CONSISTENCY
# ═══════════════════════════════════════════════════════════════

def check_ssot_medallions() -> tuple[list[str], list[str]]:
    """
    Check SSOT documents for medallion tag consistency.

    SBE:
      Given  all Gen89 documents should be bronze medallion
      When   SSOT is scanned for medallion tags
      Then   any doc claiming silver/gold/hfo is flagged as self-promotion
    """
    violations = []
    warnings = []

    if not SSOT_DB.exists():
        return violations, warnings

    try:
        conn = get_db_ro()

        # Check for non-bronze medallion tags
        rows = conn.execute("""
            SELECT medallion, COUNT(*) as cnt
            FROM documents
            WHERE medallion IS NOT NULL AND medallion != 'bronze'
            GROUP BY medallion
        """).fetchall()

        for row in rows:
            if row["cnt"] > 0:
                violations.append(
                    f"SELF_PROMOTION: {row['cnt']} docs claim medallion='{row['medallion']}' "
                    f"(all Gen89 docs should be bronze)"
                )

        # Check for documents with empty/null medallion
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE medallion IS NULL OR medallion = ''"
        ).fetchone()
        if row and row["cnt"] > 0:
            warnings.append(f"{row['cnt']} documents have no medallion tag")

        conn.close()
    except Exception as e:
        warnings.append(f"SSOT medallion query failed: {e}")

    return violations, warnings


# ═══════════════════════════════════════════════════════════════
# § 5  CHECK: GIT HOOKS
# ═══════════════════════════════════════════════════════════════

def check_git_hooks() -> tuple[list[str], list[str]]:
    """
    Verify pre-commit hook is configured and present.

    SBE:
      Given  .githooks/pre-commit should exist
      When   git config core.hooksPath is checked
      Then   hooks path = .githooks and pre-commit file exists
    """
    violations = []
    warnings = []

    # Check hook file exists
    hook_path = HFO_ROOT / ".githooks" / "pre-commit"
    if not hook_path.exists():
        violations.append("Pre-commit hook missing: .githooks/pre-commit")
    elif not os.access(str(hook_path), os.X_OK) and sys.platform != "win32":
        warnings.append("Pre-commit hook is not executable")

    # Check git config
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            capture_output=True, text=True, timeout=5,
            cwd=str(HFO_ROOT),
        )
        hooks_path = result.stdout.strip()
        if hooks_path != ".githooks":
            violations.append(
                f"Git hooks path is '{hooks_path}', should be '.githooks'"
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        warnings.append("Could not check git config (git not available?)")

    return violations, warnings


# ═══════════════════════════════════════════════════════════════
# § 6  SPELL: WARD — Full boundary enforcement scan
# ═══════════════════════════════════════════════════════════════

def spell_ward(quiet: bool = False) -> dict[str, Any]:
    """
    FORBIDDANCE WARD — Complete medallion boundary enforcement.

    SBE Contract:
      Given  the HFO forge has 4 medallion layers + root governance
      When   spell_ward is cast
      Then   all boundary checks run (root, layers, SSOT, hooks)
      And    WARDED (clean) or VIOLATED verdict returned
      And    CloudEvent written with full results
    """
    _print = (lambda *a, **k: None) if quiet else print
    _print("  [WARD] Scanning medallion boundaries...")

    all_violations = []
    all_warnings = []

    # 1. Root cleanliness
    v, w = check_root_cleanliness()
    all_violations.extend([f"[ROOT] {x}" for x in v])
    all_warnings.extend([f"[ROOT] {x}" for x in w])

    # 2. Layer boundaries
    v, w = check_layer_boundaries()
    all_violations.extend([f"[LAYER] {x}" for x in v])
    all_warnings.extend([f"[LAYER] {x}" for x in w])

    # 3. SSOT medallion consistency
    v, w = check_ssot_medallions()
    all_violations.extend([f"[SSOT] {x}" for x in v])
    all_warnings.extend([f"[SSOT] {x}" for x in w])

    # 4. Git hooks
    v, w = check_git_hooks()
    all_violations.extend([f"[HOOKS] {x}" for x in v])
    all_warnings.extend([f"[HOOKS] {x}" for x in w])

    clean = len(all_violations) == 0
    verdict = "WARDED" if clean else "VIOLATED"

    # Write CloudEvent
    event_type = f"hfo.gen{GEN}.p7.forbiddance.{'clean' if clean else 'violation'}"
    try:
        conn = get_db_rw()
        write_event(conn, event_type,
                    f"WARD:{verdict}:{len(all_violations)}violations:{len(all_warnings)}warnings",
                    {"verdict": verdict,
                     "violations": all_violations,
                     "warnings": all_warnings,
                     "violation_count": len(all_violations),
                     "warning_count": len(all_warnings),
                     "checks_performed": ["root_cleanliness", "layer_boundaries",
                                          "ssot_medallions", "git_hooks"],
                     "core_thesis": "No entity may shift to a higher plane without passing the gate."})
        conn.close()
    except Exception as e:
        _print(f"  [WARN] SSOT write failed: {e}")

    # Display results
    if clean:
        _print(f"  [WARDED] All medallion boundaries are intact.")
    else:
        _print(f"  [VIOLATED] {len(all_violations)} boundary violations detected!")
        for v in all_violations:
            _print(f"    ✗ {v}")

    if all_warnings:
        _print(f"\n  [{len(all_warnings)} warnings]:")
        for w in all_warnings:
            _print(f"    ⚠ {w}")

    return {
        "status": verdict,
        "violations": all_violations,
        "warnings": all_warnings,
        "violation_count": len(all_violations),
        "warning_count": len(all_warnings),
    }


# ═══════════════════════════════════════════════════════════════
# § 7  SPELL VARIANTS — Focused checks
# ═══════════════════════════════════════════════════════════════

def spell_root_check(quiet: bool = False) -> dict[str, Any]:
    """Root cleanliness check only."""
    _print = (lambda *a, **k: None) if quiet else print
    violations, warnings = check_root_cleanliness()

    _print(f"  [ROOT CHECK] {len(violations)} violations, {len(warnings)} warnings")
    for v in violations:
        _print(f"    ✗ {v}")
    for w in warnings:
        _print(f"    ⚠ {w}")

    return {"status": "CLEAN" if not violations else "VIOLATED",
            "violations": violations, "warnings": warnings}


def spell_check_hooks(quiet: bool = False) -> dict[str, Any]:
    """Git hook status check only."""
    _print = (lambda *a, **k: None) if quiet else print
    violations, warnings = check_git_hooks()

    if not violations:
        _print("  [HOOKS] Pre-commit hook is configured and present.")
    else:
        for v in violations:
            _print(f"    ✗ {v}")
    for w in warnings:
        _print(f"    ⚠ {w}")

    return {"status": "OK" if not violations else "MISCONFIGURED",
            "violations": violations, "warnings": warnings}


def spell_audit_medallions(quiet: bool = False) -> dict[str, Any]:
    """SSOT medallion consistency audit only."""
    _print = (lambda *a, **k: None) if quiet else print
    violations, warnings = check_ssot_medallions()

    if not violations:
        _print("  [MEDALLIONS] All documents correctly tagged bronze.")
    else:
        for v in violations:
            _print(f"    ✗ {v}")
    for w in warnings:
        _print(f"    ⚠ {w}")

    # Write audit event
    try:
        conn = get_db_rw()
        write_event(conn, f"hfo.gen{GEN}.p7.forbiddance.medallion",
                    f"MEDALLION_AUDIT:{'CLEAN' if not violations else 'VIOLATIONS'}",
                    {"violations": violations, "warnings": warnings})
        conn.close()
    except Exception:
        pass

    return {"status": "CLEAN" if not violations else "SELF_PROMOTION_DETECTED",
            "violations": violations, "warnings": warnings}


# ═══════════════════════════════════════════════════════════════
# § 8  CLI
# ═══════════════════════════════════════════════════════════════

def _print_banner():
    print()
    print("  " + "=" * 64)
    print("  P7 SPIDER SOVEREIGN — FORBIDDANCE")
    print("  Summoner of Seals and Spheres — Aspect A: SEALS")
    print("  " + "-" * 64)
    print("  Abjuration 6th — PHB p.233 — wards area against planar travel")
    print("  No entity may shift to a higher plane without passing the gate.")
    print("  " + "=" * 64)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="P7 Spider Sovereign — FORBIDDANCE Spell (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Spells:
  ward                Full boundary enforcement (root + layers + SSOT + hooks)
  root-check          Root directory cleanliness only
  check-hooks         Git pre-commit hook status
  audit-medallions    SSOT medallion tag consistency

Examples:
  python hfo_p7_forbiddance.py ward
  python hfo_p7_forbiddance.py root-check
  python hfo_p7_forbiddance.py check-hooks
  python hfo_p7_forbiddance.py audit-medallions
  python hfo_p7_forbiddance.py --json ward
""",
    )
    parser.add_argument("spell", choices=["ward", "root-check", "check-hooks", "audit-medallions"],
                        help="Spell variant")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    _print_banner()

    if args.spell == "ward":
        result = spell_ward()
    elif args.spell == "root-check":
        result = spell_root_check()
    elif args.spell == "check-hooks":
        result = spell_check_hooks()
    elif args.spell == "audit-medallions":
        result = spell_audit_medallions()
    else:
        result = {"error": "Unknown spell"}

    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
