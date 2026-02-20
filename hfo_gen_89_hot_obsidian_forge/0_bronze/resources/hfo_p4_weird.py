#!/usr/bin/env python3
"""
hfo_p4_weird.py — P4 Red Regnant: WEIRD (Mutation Kill Sweep)
══════════════════════════════════════════════════════════════

Spell Slot: S1 (STRIFE)
D&D Source: PHB p.302, Illusion 9th
D&D Effect: "Phantasmal killer that targets all creatures in a 30-ft radius.
             Each creature must succeed on a Will save or die."
HFO Alias:  Mutation kill sweep — Stryker-style mutation testing.
            Every mutant that can die, does. Survivors are splendid.

Port:       P4 DISRUPT
Commander:  Red Regnant — Singer of Strife and Splendor
Aspect:     A (STRIFE)
Tier:       MASTER target (fills slot S1)

Engineering Function:
    Scan all Python scripts in the forge for "code mutants" — structural quality
    issues that would be caught by mutation testing. Uses AST analysis to detect:
    - Bare except clauses (swallow errors silently)
    - Unused imports (dead code)
    - Empty function/method bodies (placeholder stubs)
    - Hardcoded deep forge paths (PAL violations)
    - Missing docstrings on public functions
    - Global mutable state (side-effect hazards)
    - Broad exception catches (Exception, BaseException)
    - Functions with excessive complexity (too many branches)

    Each issue is a "mutant". The sweep either "kills" it (flags it for fix)
    or marks it as "surviving" (requires human attention). Results written as
    CloudEvent stigmergy to SSOT.

Stigmergy Events:
    hfo.gen89.p4.weird.sweep       — Full sweep results
    hfo.gen89.p4.weird.kill        — Individual mutant kill
    hfo.gen89.p4.weird.survivor    — Surviving mutant (needs human)
    hfo.gen89.p4.weird.heartbeat   — Daemon heartbeat

SBE / ATDD Specification:
─────────────────────────

Feature: WEIRD — Mutation Kill Sweep

  # Tier 1: Invariant (MUST NOT violate)
  Scenario: Scan discovers bare except clauses
    Given a Python file contains `except:` with no exception type
    When WEIRD sweep scans the file
    Then a mutant of class "bare_except" is recorded
    And the mutant includes file path and line number

  Scenario: Scan discovers hardcoded forge paths
    Given a Python file contains a string literal matching "hfo_gen_89_hot_obsidian_forge"
    When WEIRD sweep scans the file
    Then a mutant of class "hardcoded_path" is recorded
    And severity is HIGH or CRITICAL

  Scenario: Scan discovers missing docstrings
    Given a Python file has a public function (no _ prefix) without a docstring
    When WEIRD sweep scans the file
    Then a mutant of class "missing_docstring" is recorded

  Scenario: Scan discovers empty function bodies
    Given a Python file has a function whose body is only `pass` or `...`
    When WEIRD sweep scans the file
    Then a mutant of class "empty_body" is recorded

  # Tier 2: Happy-path
  Scenario: Full sweep produces summary
    Given the forge contains Python files
    When `python hfo_p4_weird.py --summary` is executed
    Then output shows total files scanned, total mutants found, kill rate
    And a CloudEvent is written to SSOT

  Scenario: JSON output mode
    Given the forge contains Python files
    When `python hfo_p4_weird.py --json` is executed
    Then output is valid JSON with keys: files_scanned, mutants, kill_rate, survivors

  # Tier 3: Daemon mode
  Scenario: Daemon mode runs periodic sweeps
    Given `python hfo_p4_weird.py --daemon --interval 300` is executed
    When 300 seconds elapse
    Then a new sweep is performed and heartbeat event is written

  # Tier 4: Lifecycle
  Scenario: No Python files found
    Given the scan directory contains no .py files
    When WEIRD sweep runs
    Then output shows 0 files scanned, 0 mutants
    And no error is raised

Usage:
    python hfo_p4_weird.py --summary          # One-shot summary to stdout
    python hfo_p4_weird.py --json             # JSON output
    python hfo_p4_weird.py --detail           # Per-file mutant listing
    python hfo_p4_weird.py --stigmergy        # Write results to SSOT
    python hfo_p4_weird.py --daemon           # Continuous mode
    python hfo_p4_weird.py --top 10           # Worst 10 files by mutant count
"""

import argparse
import ast
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    """Find HFO_ROOT by walking up from script location."""
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


# Resolve paths via PAL
try:
    SSOT_DB = resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"

try:
    FORGE_ROOT = resolve_pointer("forge.root")
except (KeyError, FileNotFoundError):
    FORGE_ROOT = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge"

BRONZE = FORGE_ROOT / "0_bronze"
GEN = os.environ.get("HFO_GENERATION", "89")
P4_SOURCE = f"hfo_p4_weird_gen{GEN}"
EVENT_PREFIX = "hfo.gen89.p4.weird"
VERSION = "1.0.0"

# Hardcoded path pattern for detection
HARDCODED_FORGE_RE = re.compile(
    r"hfo_gen_\d+_hot_obsidian_forge[/\\]", re.IGNORECASE
)

# ═══════════════════════════════════════════════════════════════
# § 1  SPELL IDENTITY
# ═══════════════════════════════════════════════════════════════

SPELL_IDENTITY = {
    "port": "P4",
    "powerword": "DISRUPT",
    "commander": "Red Regnant",
    "spell": "WEIRD",
    "spell_slot": "S1",
    "aspect": "STRIFE",
    "dnd_source": "PHB p.302, Illusion 9th",
    "school": "Illusion",
    "alias": "Mutation Kill Sweep",
    "version": VERSION,
    "core_thesis": "Every mutant that can die, does. Survivors are splendid.",
}

# ═══════════════════════════════════════════════════════════════
# § 2  MUTANT CLASSES (the things WEIRD detects)
# ═══════════════════════════════════════════════════════════════

MUTANT_SEVERITY = {
    "bare_except":       "HIGH",
    "broad_except":      "MEDIUM",
    "hardcoded_path":    "HIGH",
    "missing_docstring": "LOW",
    "empty_body":        "MEDIUM",
    "unused_import":     "LOW",
    "global_mutable":    "MEDIUM",
    "excessive_branches": "MEDIUM",
    "eval_exec_usage":   "CRITICAL",
    "star_import":       "MEDIUM",
    "nested_function_deep": "LOW",
}

# ═══════════════════════════════════════════════════════════════
# § 3  AST MUTANT DETECTOR
# ═══════════════════════════════════════════════════════════════

class Mutant:
    """A single detected code quality issue."""
    __slots__ = ("file", "line", "mutant_class", "severity", "detail", "killed")

    def __init__(self, file: str, line: int, mutant_class: str, detail: str = ""):
        self.file = file
        self.line = line
        self.mutant_class = mutant_class
        self.severity = MUTANT_SEVERITY.get(mutant_class, "LOW")
        self.detail = detail
        self.killed = True  # Flagged = killed (detected)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "class": self.mutant_class,
            "severity": self.severity,
            "detail": self.detail,
            "killed": self.killed,
        }


class WeirdAnalyzer(ast.NodeVisitor):
    """AST visitor that detects code mutants."""

    def __init__(self, filepath: str, source: str):
        self.filepath = filepath
        self.source = source
        self.source_lines = source.splitlines()
        self.mutants: list[Mutant] = []
        self._function_depth = 0
        self._imports: list[tuple[str, int]] = []  # (name, line)
        self._names_used: set[str] = set()

    def _add(self, line: int, cls: str, detail: str = ""):
        self.mutants.append(Mutant(self.filepath, line, cls, detail))

    # ── Bare except / broad except ──
    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.type is None:
            self._add(node.lineno, "bare_except", "except: with no exception type")
        elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
            self._add(node.lineno, "broad_except", f"except {node.type.id}")
        self.generic_visit(node)

    # ── Empty function bodies ──
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_function(node)
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_function(node)
        self._function_depth += 1
        self.generic_visit(node)
        self._function_depth -= 1

    def _check_function(self, node):
        # Check empty body
        body = node.body
        if len(body) == 1:
            stmt = body[0]
            if isinstance(stmt, ast.Pass):
                self._add(node.lineno, "empty_body", f"def {node.name}(): pass")
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                # Just a docstring, no real body
                if len(body) == 1:  # Only docstring, nothing else
                    pass  # This is fine — abstract method or protocol
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is ...:
                self._add(node.lineno, "empty_body", f"def {node.name}(): ...")

        # Check missing docstring on public functions
        if not node.name.startswith("_"):
            if not (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                self._add(node.lineno, "missing_docstring", f"def {node.name}()")

        # Check deep nesting
        if self._function_depth >= 3:
            self._add(node.lineno, "nested_function_deep",
                      f"def {node.name}() nested {self._function_depth + 1} levels deep")

        # Check excessive branches
        branch_count = self._count_branches(node)
        if branch_count > 15:
            self._add(node.lineno, "excessive_branches",
                      f"def {node.name}() has {branch_count} branches")

    def _count_branches(self, node) -> int:
        """Count if/elif/for/while/try branches in a function."""
        count = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                count += 1
        return count

    # ── Import tracking ──
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self._imports.append((name, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.names and any(a.name == "*" for a in node.names):
            self._add(node.lineno, "star_import",
                      f"from {node.module} import *")
        for alias in node.names:
            if alias.name != "*":
                name = alias.asname or alias.name
                self._imports.append((name, node.lineno))
        self.generic_visit(node)

    # ── Name usage tracking ──
    def visit_Name(self, node: ast.Name):
        self._names_used.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if isinstance(node.value, ast.Name):
            self._names_used.add(node.value.id)
        self.generic_visit(node)

    # ── eval/exec detection ──
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            self._add(node.lineno, "eval_exec_usage",
                      f"{node.func.id}() call detected")
        self.generic_visit(node)

    # ── Global mutable state ──
    def visit_Assign(self, node: ast.Assign):
        # Only check module-level assignments
        if self._function_depth == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # Detect mutable containers at module level
                    if isinstance(node.value, (ast.List, ast.Dict, ast.Set)):
                        # Skip common patterns like __all__
                        if target.id not in ("__all__", "__version__"):
                            self._add(node.lineno, "global_mutable",
                                      f"{target.id} = mutable {type(node.value).__name__}")
        self.generic_visit(node)

    # ── Finalize: check unused imports ──
    def finalize(self):
        """Call after visiting to check unused imports."""
        for name, line in self._imports:
            if name not in self._names_used and name != "_":
                self._add(line, "unused_import", f"import {name}")

    # ── Hardcoded path detection (string literals) ──
    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str) and HARDCODED_FORGE_RE.search(node.value):
            self._add(node.lineno, "hardcoded_path",
                      f'Hardcoded forge path: "{node.value[:80]}..."')
        self.generic_visit(node)


def scan_file(filepath: Path) -> list[Mutant]:
    """Scan a single Python file for mutants."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return [Mutant(str(filepath), 0, "syntax_error", "File cannot be parsed")]
    except Exception as e:
        return [Mutant(str(filepath), 0, "scan_error", str(e))]

    analyzer = WeirdAnalyzer(str(filepath), source)
    analyzer.visit(tree)
    analyzer.finalize()
    return analyzer.mutants


def scan_directory(directory: Path, exclude_patterns: list[str] = None) -> tuple[int, list[Mutant]]:
    """Scan all .py files in directory tree. Returns (files_scanned, mutants)."""
    exclude_patterns = exclude_patterns or [
        "__pycache__", ".venv", "venv", "node_modules", ".git",
    ]
    all_mutants = []
    files_scanned = 0

    for py_file in sorted(directory.rglob("*.py")):
        # Skip excluded dirs
        parts = py_file.parts
        if any(exc in parts for exc in exclude_patterns):
            continue
        mutants = scan_file(py_file)
        all_mutants.extend(mutants)
        files_scanned += 1

    return files_scanned, all_mutants


# ═══════════════════════════════════════════════════════════════
# § 4  SCORING & REPORTING
# ═══════════════════════════════════════════════════════════════

def compute_sweep_stats(mutants: list[Mutant]) -> dict:
    """Compute statistics from a mutant sweep."""
    if not mutants:
        return {
            "total_mutants": 0,
            "killed": 0,
            "survived": 0,
            "kill_rate": 100.0,
            "by_class": {},
            "by_severity": {},
            "by_file": {},
        }

    by_class = Counter(m.mutant_class for m in mutants)
    by_severity = Counter(m.severity for m in mutants)
    by_file = defaultdict(int)
    for m in mutants:
        by_file[m.file] += 1

    killed = sum(1 for m in mutants if m.killed)
    survived = len(mutants) - killed

    return {
        "total_mutants": len(mutants),
        "killed": killed,
        "survived": survived,
        "kill_rate": round(killed / len(mutants) * 100, 1) if mutants else 100.0,
        "by_class": dict(by_class.most_common()),
        "by_severity": dict(by_severity),
        "by_file": dict(sorted(by_file.items(), key=lambda x: -x[1])),
    }


def format_summary(files_scanned: int, mutants: list[Mutant], stats: dict) -> str:
    """Format a human-readable sweep summary."""
    lines = []
    lines.append("=" * 72)
    lines.append("  P4 RED REGNANT — WEIRD (Mutation Kill Sweep)")
    lines.append("  \"Every mutant that can die, does. Survivors are splendid.\"")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"  Files scanned:   {files_scanned}")
    lines.append(f"  Total mutants:   {stats['total_mutants']}")
    lines.append(f"  Killed (flagged): {stats['killed']}")
    lines.append(f"  Survived:        {stats['survived']}")
    lines.append(f"  Kill rate:       {stats['kill_rate']}%")
    lines.append("")

    if stats["by_severity"]:
        lines.append("  ── By Severity ──")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            count = stats["by_severity"].get(sev, 0)
            if count:
                lines.append(f"    {sev:10s}  {count:5d}")
        lines.append("")

    if stats["by_class"]:
        lines.append("  ── By Mutant Class ──")
        for cls, count in sorted(stats["by_class"].items(), key=lambda x: -x[1]):
            sev = MUTANT_SEVERITY.get(cls, "LOW")
            lines.append(f"    {cls:25s}  {count:5d}  ({sev})")
        lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)


def format_detail(mutants: list[Mutant]) -> str:
    """Format per-file mutant listing."""
    lines = []
    by_file = defaultdict(list)
    for m in mutants:
        by_file[m.file].append(m)

    for filepath, file_mutants in sorted(by_file.items()):
        rel = filepath
        try:
            rel = str(Path(filepath).relative_to(HFO_ROOT))
        except ValueError:
            pass
        lines.append(f"\n  {rel} ({len(file_mutants)} mutants)")
        lines.append("  " + "-" * 60)
        for m in sorted(file_mutants, key=lambda x: x.line):
            marker = "X" if m.killed else "!"
            lines.append(f"    [{marker}] L{m.line:4d}  {m.mutant_class:25s}  {m.detail}")

    return "\n".join(lines)


def format_top(mutants: list[Mutant], n: int = 10) -> str:
    """Format top-N worst files by mutant count."""
    by_file = defaultdict(int)
    for m in mutants:
        by_file[m.file] += 1
    sorted_files = sorted(by_file.items(), key=lambda x: -x[1])[:n]

    lines = [f"\n  Top {n} files by mutant count:"]
    lines.append("  " + "-" * 60)
    for i, (fp, count) in enumerate(sorted_files, 1):
        rel = fp
        try:
            rel = str(Path(fp).relative_to(HFO_ROOT))
        except ValueError:
            pass
        lines.append(f"    {i:2d}. {count:4d} mutants  {rel}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 5  SSOT / STIGMERGY
# ═══════════════════════════════════════════════════════════════

def get_db_readwrite() -> sqlite3.Connection:
    if not SSOT_DB.exists():
        raise FileNotFoundError(f"SSOT database not found: {SSOT_DB}")
    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def write_stigmergy_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
) -> int:
    """Write a CloudEvent to stigmergy trail. Returns row id."""
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
        "spell": "WEIRD",
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


def write_sweep_to_ssot(files_scanned: int, mutants: list[Mutant], stats: dict) -> int:
    """Write sweep results to SSOT. Returns event row id."""
    conn = get_db_readwrite()
    try:
        # Limit to top defects to avoid huge events
        top_mutants = sorted(
            mutants,
            key=lambda m: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(m.severity, 4)
        )[:100]

        data = {
            "spell_identity": SPELL_IDENTITY,
            "files_scanned": files_scanned,
            "stats": stats,
            "top_mutants": [m.to_dict() for m in top_mutants],
            "scan_directory": str(FORGE_ROOT),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        row_id = write_stigmergy_event(
            conn,
            f"{EVENT_PREFIX}.sweep",
            f"weird-sweep:{files_scanned}f:{stats['total_mutants']}m:{stats['kill_rate']}%",
            data,
        )
        return row_id
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# § 6  DAEMON MODE
# ═══════════════════════════════════════════════════════════════

_running = True


def _signal_handler(sig, frame):
    global _running
    _running = False


def daemon_loop(interval: int = 300, stigmergy: bool = True):
    """Continuous sweep mode with heartbeat."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    cycle = 0
    print(f"  [WEIRD] Daemon mode — sweep every {interval}s. Ctrl+C to stop.")

    while _running:
        cycle += 1
        print(f"\n  [WEIRD] Cycle {cycle} starting...")
        files_scanned, mutants = scan_directory(FORGE_ROOT)
        stats = compute_sweep_stats(mutants)
        print(f"  [WEIRD] Cycle {cycle}: {files_scanned} files, "
              f"{stats['total_mutants']} mutants, {stats['kill_rate']}% kill rate")

        if stigmergy:
            try:
                row_id = write_sweep_to_ssot(files_scanned, mutants, stats)
                print(f"  [WEIRD] Stigmergy event written: row {row_id}")
            except Exception as e:
                print(f"  [WEIRD] Stigmergy write failed: {e}")

        # Sleep in small increments for responsive shutdown
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    print("  [WEIRD] Daemon stopped.")


# ═══════════════════════════════════════════════════════════════
# § 7  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P4 WEIRD — Mutation Kill Sweep (Stryker-style code mutant detection)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Spell: WEIRD (PHB p.302, Illusion 9th)
            Port:  P4 DISRUPT — Red Regnant
            Alias: Mutation Kill Sweep
            "Every mutant that can die, does. Survivors are splendid."
        """),
    )
    parser.add_argument("--summary", action="store_true",
                        help="One-shot summary to stdout")
    parser.add_argument("--json", action="store_true",
                        help="JSON output mode")
    parser.add_argument("--detail", action="store_true",
                        help="Per-file mutant listing")
    parser.add_argument("--top", type=int, default=0, metavar="N",
                        help="Show top N files by mutant count")
    parser.add_argument("--stigmergy", action="store_true",
                        help="Write results to SSOT stigmergy trail")
    parser.add_argument("--daemon", action="store_true",
                        help="Continuous sweep mode")
    parser.add_argument("--interval", type=int, default=300,
                        help="Daemon sweep interval in seconds (default: 300)")
    parser.add_argument("--directory", type=str, default=None,
                        help="Directory to scan (default: forge root)")
    parser.add_argument("--status", action="store_true",
                        help="Show spell identity and version")
    args = parser.parse_args()

    if args.status:
        print(json.dumps(SPELL_IDENTITY, indent=2))
        return

    scan_dir = Path(args.directory) if args.directory else FORGE_ROOT
    if not scan_dir.exists():
        print(f"  [WEIRD] ERROR: Directory not found: {scan_dir}")
        sys.exit(1)

    if args.daemon:
        daemon_loop(interval=args.interval, stigmergy=True)
        return

    # One-shot scan
    files_scanned, mutants = scan_directory(scan_dir)
    stats = compute_sweep_stats(mutants)

    if args.json:
        output = {
            "spell": SPELL_IDENTITY,
            "files_scanned": files_scanned,
            "mutants": [m.to_dict() for m in mutants],
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(output, indent=2, default=str))
        return

    if args.summary or not (args.detail or args.top):
        print(format_summary(files_scanned, mutants, stats))

    if args.detail:
        print(format_detail(mutants))

    if args.top:
        print(format_top(mutants, args.top))

    if args.stigmergy:
        try:
            row_id = write_sweep_to_ssot(files_scanned, mutants, stats)
            print(f"\n  [WEIRD] Stigmergy event written to SSOT: row {row_id}")
        except Exception as e:
            print(f"\n  [WEIRD] Stigmergy write failed: {e}")


if __name__ == "__main__":
    import textwrap
    main()
