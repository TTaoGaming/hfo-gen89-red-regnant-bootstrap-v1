#!/usr/bin/env python3
"""
══════════════════════════════════════════════════════════════════════
  P0 TRUE_SEEING — Lidless Legion Divination (6th Level)
  Grimoire V7 Slot A1 — Anti-Hallucination Incarnate
══════════════════════════════════════════════════════════════════════

  "Validate system state = reported state."

  This spell parses the AST of every Python file in bronze/resources,
  discovers hardcoded paths, builds a cross-file dependency graph,
  validates fleet model assignments against actual code, and writes
  findings to SSOT stigmergy. The system sees itself truthfully.

  SBE Spec (Tier 1 — Invariant):
    Given the HFO Gen90 workspace with ~60+ Python scripts in bronze
    When  P0 TRUE_SEEING is cast
    Then  every script is AST-parsed, all hardcoded forge paths
          are detected, cross-file dependencies are mapped, fleet
          model discrepancies are flagged, and findings are emitted
          as CloudEvent stigmergy — no hallucination, no cosmetic
          labels, only ground truth from the AST.

  Modes:
    --report          Full human-readable report (default)
    --json            Machine-readable JSON output
    --hardcoded-only  Only show hardcoded path violations
    --dependency      Cross-file dependency graph
    --fleet           Fleet model validation only
    --stigmergy       Write findings to SSOT as CloudEvent
    --summary         Executive summary (counts + grades)

  Port: P0 OBSERVE (Lidless Legion)
  Pair: P6 ASSIMILATE (Kraken Keeper)
  Commander: Lidless Legion
  Mnemonic: O = OBSERVE = "See the system as it IS, not as it claims"
══════════════════════════════════════════════════════════════════════
"""

import ast
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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

# Resolve all paths through PAL — zero hardcoding
_POINTERS = _load_pointer_registry()

try:
    SSOT_DB = _resolve_pointer("ssot.db", _POINTERS)
except KeyError:
    SSOT_DB = None  # No fallback. If PAL fails, we report it.

try:
    FORGE_ROOT = _resolve_pointer("forge.root", _POINTERS)
except KeyError:
    FORGE_ROOT = None

try:
    BRONZE_RESOURCES = _resolve_pointer("forge.bronze.resources", _POINTERS)
except KeyError:
    BRONZE_RESOURCES = None

GEN = os.getenv("HFO_GENERATION", "89")
SOURCE_TAG = f"hfo_p0_true_seeing_gen{GEN}"

# The forge path pattern to detect in AST — the string no one should hardcode
FORGE_PATH_PATTERN = re.compile(
    r"hfo_gen_\d+_hot_obsidian_forge"
    r"|c:\\\\?hfoDev"
    r"|/hfoDev/"
    r"|2_gold/resources"
    r"|0_bronze/resources"
    r"|1_silver/resources"
    r"|3_hyper_fractal_obsidian",
    re.IGNORECASE,
)

# Known PAL pointer keys for governance files
GOVERNANCE_POINTER_KEYS = [
    "root.agents_md",
    "root.pointers_blessed",
    "root.env_example",
    "root.gitignore",
]


# ═══════════════════════════════════════════════════════════════
# § 1  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class FunctionInfo:
    name: str
    args: List[str]
    line: int
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)

@dataclass
class ClassInfo:
    name: str
    bases: List[str]
    methods: List[FunctionInfo]
    line: int
    decorators: List[str] = field(default_factory=list)

@dataclass
class HardcodedRef:
    file: str
    line: int
    col: int
    value: str
    context: str  # "string_literal", "f_string", "assignment", "default_arg"
    severity: str  # "CRITICAL" (absolute path), "HIGH" (forge path), "MEDIUM" (partial)

@dataclass
class FileAnalysis:
    path: str
    basename: str
    lines: int
    parse_error: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    from_imports: List[str] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    constants: List[str] = field(default_factory=list)
    hardcoded_refs: List[HardcodedRef] = field(default_factory=list)
    has_resolve_pointer: bool = False
    has_pal_import: bool = False
    internal_deps: Set[str] = field(default_factory=set)
    external_deps: Set[str] = field(default_factory=set)
    risk_flags: List[str] = field(default_factory=list)
    content_hash: str = ""

@dataclass
class FleetDiscrepancy:
    port: str
    field_name: str
    fleet_value: str
    code_value: str
    file: str
    detail: str

@dataclass
class TrueSeeingReport:
    timestamp: str
    hfo_root: str
    bronze_resources: str
    total_files: int = 0
    total_lines: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_hardcoded: int = 0
    total_critical: int = 0
    total_high: int = 0
    files_with_pal: int = 0
    files_without_pal: int = 0
    files_with_hardcoded: int = 0
    pal_health_pct: float = 0.0
    grade: str = "F"
    file_analyses: List[FileAnalysis] = field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    fleet_discrepancies: List[FleetDiscrepancy] = field(default_factory=list)
    pointer_registry_keys: int = 0
    pointer_health: str = "UNKNOWN"


# ═══════════════════════════════════════════════════════════════
# § 2  AST ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════

def _extract_decorators(node) -> List[str]:
    """Extract decorator names from a class/function node."""
    decorators = []
    for d in getattr(node, "decorator_list", []):
        if isinstance(d, ast.Name):
            decorators.append(d.id)
        elif isinstance(d, ast.Attribute):
            decorators.append(getattr(d, "attr", "?"))
        elif isinstance(d, ast.Call):
            if isinstance(d.func, ast.Name):
                decorators.append(d.func.id)
            elif isinstance(d.func, ast.Attribute):
                decorators.append(getattr(d.func, "attr", "?"))
    return decorators


def _scan_hardcoded_strings(tree: ast.AST, filepath: str) -> List[HardcodedRef]:
    """Walk the AST and find all string literals containing hardcoded forge paths."""
    refs = []

    for node in ast.walk(tree):
        strings_to_check: List[Tuple[str, int, int, str]] = []

        # Regular string constants
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings_to_check.append((node.value, node.lineno, node.col_offset, "string_literal"))

        # JoinedStr (f-strings) — check each string part
        elif isinstance(node, ast.JoinedStr):
            for val in node.values:
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    strings_to_check.append(
                        (val.value, node.lineno, node.col_offset, "f_string")
                    )

        for value, line, col, context in strings_to_check:
            if FORGE_PATH_PATTERN.search(value):
                # Determine severity
                if re.search(r"[a-zA-Z]:\\\\?", value) or value.startswith("/"):
                    severity = "CRITICAL"  # Absolute path
                elif "hfo_gen_" in value.lower():
                    severity = "HIGH"  # Full forge path
                else:
                    severity = "MEDIUM"  # Partial forge reference
                refs.append(HardcodedRef(
                    file=os.path.basename(filepath),
                    line=line,
                    col=col,
                    value=value[:120],  # Truncate long strings
                    context=context,
                    severity=severity,
                ))

    return refs


def _check_for_pal_usage(tree: ast.AST) -> Tuple[bool, bool]:
    """Check if the file uses _resolve_pointer or imports from hfo_pointers."""
    has_resolve = False
    has_import = False

    for node in ast.walk(tree):
        # Check for _resolve_pointer function definition or call
        if isinstance(node, ast.FunctionDef) and node.name == "_resolve_pointer":
            has_resolve = True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "_resolve_pointer":
                has_resolve = True
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "_resolve_pointer":
                has_resolve = True

        # Check for hfo_pointers import
        if isinstance(node, ast.ImportFrom):
            if node.module and "hfo_pointers" in node.module:
                has_import = True

    return has_resolve, has_import


def analyze_file(filepath: str, all_basenames: Set[str]) -> FileAnalysis:
    """Full AST analysis of a single Python file."""
    basename = os.path.basename(filepath)
    analysis = FileAnalysis(path=filepath, basename=basename, lines=0)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            src = f.read()
    except (OSError, UnicodeDecodeError) as e:
        analysis.parse_error = str(e)
        return analysis

    analysis.lines = len(src.splitlines())
    analysis.content_hash = hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]

    try:
        tree = ast.parse(src, filename=filepath)
    except SyntaxError as e:
        analysis.parse_error = f"SyntaxError: {e}"
        return analysis

    # Walk top-level nodes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                analysis.imports.append(a.name)
                dep = a.name.split(".")[0]
                stem = dep.replace(".py", "")
                if stem + ".py" in all_basenames or stem in all_basenames:
                    analysis.internal_deps.add(stem)
                else:
                    analysis.external_deps.add(dep)

        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            analysis.from_imports.append(mod)
            dep = mod.split(".")[0]
            stem = dep.replace(".py", "")
            if stem + ".py" in all_basenames or stem in all_basenames:
                analysis.internal_deps.add(stem)
            else:
                analysis.external_deps.add(dep)

        elif isinstance(node, ast.ClassDef):
            methods = []
            for n in ast.iter_child_nodes(node):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = [a.arg for a in n.args.args if a.arg != "self"]
                    methods.append(FunctionInfo(
                        name=n.name, args=args, line=n.lineno,
                        is_async=isinstance(n, ast.AsyncFunctionDef),
                        decorators=_extract_decorators(n),
                    ))
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(getattr(b, "attr", "?"))
            analysis.classes.append(ClassInfo(
                name=node.name, bases=bases, methods=methods,
                line=node.lineno, decorators=_extract_decorators(node),
            ))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            analysis.functions.append(FunctionInfo(
                name=node.name, args=args, line=node.lineno,
                is_async=isinstance(node, ast.AsyncFunctionDef),
                decorators=_extract_decorators(node),
            ))

        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    analysis.constants.append(t.id)

    # Hardcoded path detection
    analysis.hardcoded_refs = _scan_hardcoded_strings(tree, filepath)

    # PAL usage
    analysis.has_resolve_pointer, analysis.has_pal_import = _check_for_pal_usage(tree)

    # Risk flags
    all_deps = analysis.external_deps | analysis.internal_deps
    if "subprocess" in all_deps:
        analysis.risk_flags.append("subprocess (shell injection risk)")
    if "eval" in all_deps or "exec" in all_deps:
        analysis.risk_flags.append("eval/exec (code injection risk)")
    if "pickle" in all_deps:
        analysis.risk_flags.append("pickle (deserialization risk)")

    # Check for security-sensitive patterns
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec"):
                    analysis.risk_flags.append(f"{node.func.id}() call at L{node.lineno}")
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == "system" and isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "os":
                        analysis.risk_flags.append(f"os.system() at L{node.lineno}")

    return analysis


# ═══════════════════════════════════════════════════════════════
# § 3  DISCOVERY ENGINE
# ═══════════════════════════════════════════════════════════════

def discover_python_files(root_dir: Optional[Path] = None) -> List[str]:
    """Dynamically discover all .py files in bronze/resources.
    NO hardcoded file lists. The AST sees what IS, not what we expect.
    """
    target = root_dir or BRONZE_RESOURCES
    if target is None or not target.exists():
        return []

    files = []
    for child in sorted(target.iterdir()):
        if child.suffix == ".py" and child.is_file():
            files.append(str(child))

    # Also check subdirectories (e.g., features/)
    for subdir in sorted(target.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            for child in sorted(subdir.rglob("*.py")):
                if child.is_file():
                    files.append(str(child))

    return files


def discover_governance_files() -> List[str]:
    """Dynamically discover governance files from PAL pointer registry.
    Replaces the static GOVERNANCE_FILES list in dimensional_anchor.
    """
    governance = []
    for key in GOVERNANCE_POINTER_KEYS:
        try:
            path = _resolve_pointer(key, _POINTERS)
            if path.exists():
                governance.append(str(path.relative_to(HFO_ROOT)))
        except KeyError:
            pass

    # Also scan root for allowed governance files not in pointer registry
    allowed_extensions = {".md", ".json", ".example", ".gitignore", ".gitattributes"}
    if HFO_ROOT.exists():
        for child in HFO_ROOT.iterdir():
            if child.is_file():
                rel = str(child.relative_to(HFO_ROOT))
                if rel not in governance:
                    if child.suffix in allowed_extensions or child.name.startswith(".git"):
                        governance.append(rel)

    return sorted(set(governance))


# ═══════════════════════════════════════════════════════════════
# § 4  FLEET VALIDATION
# ═══════════════════════════════════════════════════════════════

def validate_fleet(file_analyses: List[FileAnalysis]) -> List[FleetDiscrepancy]:
    """Check fleet config model assignments against actual code.
    Detects cosmetic labels that don't match real implementation.
    """
    discrepancies = []

    # Build a lookup of file contents by basename
    analysis_by_name = {a.basename: a for a in file_analyses}

    # Look for fleet config file
    fleet_file = analysis_by_name.get("hfo_daemon_fleet.py")
    if not fleet_file:
        return discrepancies

    # Parse the fleet file's AST for model assignments
    try:
        fleet_path = fleet_file.path
        with open(fleet_path, "r", encoding="utf-8") as f:
            fleet_src = f.read()

        # Find model= assignments in the fleet config
        # Pattern: model="some_model" in FLEET_CONFIG or similar structures
        model_pattern = re.compile(
            r'"model"\s*:\s*"([^"]+)".*?"script"\s*:\s*"([^"]+)"'
            r'|"script"\s*:\s*"([^"]+)".*?"model"\s*:\s*"([^"]+)"',
            re.DOTALL,
        )

        # Find port → model → script mappings
        port_pattern = re.compile(
            r'"ports"\s*:\s*"(P\d)".*?"model"\s*:\s*"([^"]+)".*?"script"\s*:\s*"([^"]+)"'
            r'|"script"\s*:\s*"([^"]+)".*?"ports"\s*:\s*"(P\d)".*?"model"\s*:\s*"([^"]+)"',
            re.DOTALL,
        )

        # Check each script mentioned in fleet for actual model usage
        # Look for GeminiClient, OllamaClient, or model string literals
        for analysis in file_analyses:
            # Check if this file has model="budget" hardcoded (the bug we found before)
            for ref in analysis.hardcoded_refs:
                if "budget" in ref.value.lower() and "model" in ref.context:
                    discrepancies.append(FleetDiscrepancy(
                        port="?",
                        field_name="model",
                        fleet_value="(fleet-assigned)",
                        code_value=ref.value,
                        file=analysis.basename,
                        detail=f"Hardcoded model='budget' at L{ref.line} — fleet model assignment is cosmetic",
                    ))

            # Check for Gemini usage in files that claim Ollama
            uses_gemini = any(
                "gemini" in imp.lower() or "hfo_gemini" in imp.lower()
                for imp in analysis.imports + analysis.from_imports
            )
            uses_ollama = any(
                "ollama" in imp.lower()
                for imp in analysis.imports + analysis.from_imports
            )

            if uses_gemini and not uses_ollama:
                # Check if fleet claims this is an Ollama script
                basename = analysis.basename
                if any(
                    f'"{basename}"' in fleet_src and "ollama" in fleet_src[
                        max(0, fleet_src.index(f'"{basename}"') - 200):
                        fleet_src.index(f'"{basename}"') + 200
                    ].lower()
                    for _ in [None]
                    if f'"{basename}"' in fleet_src
                ):
                    discrepancies.append(FleetDiscrepancy(
                        port="?",
                        field_name="backend",
                        fleet_value="Ollama (fleet claim)",
                        code_value="Gemini (actual import)",
                        file=basename,
                        detail="Fleet claims Ollama but code imports GeminiClient",
                    ))

    except Exception as e:
        discrepancies.append(FleetDiscrepancy(
            port="?", field_name="parse_error", fleet_value="N/A",
            code_value=str(e), file="hfo_daemon_fleet.py",
            detail=f"Could not parse fleet config: {e}",
        ))

    return discrepancies


# ═══════════════════════════════════════════════════════════════
# § 5  REPORT GENERATION
# ═══════════════════════════════════════════════════════════════

def build_report(file_analyses: List[FileAnalysis]) -> TrueSeeingReport:
    """Assemble the full TRUE_SEEING report from individual file analyses."""
    report = TrueSeeingReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        hfo_root=str(HFO_ROOT),
        bronze_resources=str(BRONZE_RESOURCES) if BRONZE_RESOURCES else "UNRESOLVED",
        pointer_registry_keys=len(_POINTERS),
    )

    report.file_analyses = file_analyses
    report.total_files = len(file_analyses)

    for a in file_analyses:
        report.total_lines += a.lines
        report.total_classes += len(a.classes)
        report.total_functions += len(a.functions)
        report.total_hardcoded += len(a.hardcoded_refs)
        report.total_critical += sum(1 for r in a.hardcoded_refs if r.severity == "CRITICAL")
        report.total_high += sum(1 for r in a.hardcoded_refs if r.severity == "HIGH")

        if a.has_resolve_pointer or a.has_pal_import:
            report.files_with_pal += 1
        elif a.hardcoded_refs:
            report.files_without_pal += 1

        if a.hardcoded_refs:
            report.files_with_hardcoded += 1

        # Dependency graph
        if a.internal_deps:
            report.dependency_graph[a.basename] = sorted(a.internal_deps)

    # Fleet validation
    report.fleet_discrepancies = validate_fleet(file_analyses)

    # PAL health: % of files with hardcoded refs that also have PAL
    if report.files_with_hardcoded > 0:
        report.pal_health_pct = round(
            (report.files_with_pal / report.files_with_hardcoded) * 100, 1
        )
    else:
        report.pal_health_pct = 100.0

    # Pointer health
    if not _POINTERS:
        report.pointer_health = "MISSING"
    elif SSOT_DB is None or FORGE_ROOT is None or BRONZE_RESOURCES is None:
        report.pointer_health = "PARTIAL"
    else:
        report.pointer_health = "HEALTHY"

    # Grade (A-F based on hardcoded density + PAL adoption)
    if report.total_hardcoded == 0:
        report.grade = "A"
    elif report.total_critical == 0 and report.pal_health_pct >= 80:
        report.grade = "B"
    elif report.total_critical <= 3 and report.pal_health_pct >= 50:
        report.grade = "C"
    elif report.total_critical <= 10:
        report.grade = "D"
    else:
        report.grade = "F"

    return report


def format_report_text(report: TrueSeeingReport) -> str:
    """Human-readable TRUE_SEEING report."""
    lines = []
    bar = "═" * 70

    lines.append(bar)
    lines.append("  P0 TRUE_SEEING — System AST Introspection Report")
    lines.append(f"  Cast: {report.timestamp}")
    lines.append(f"  Grade: {report.grade} | PAL Health: {report.pal_health_pct}%")
    lines.append(bar)
    lines.append("")

    # Executive summary
    lines.append("┌─ EXECUTIVE SUMMARY ─────────────────────────────────────┐")
    lines.append(f"│  Files analyzed:   {report.total_files:>5}                              │")
    lines.append(f"│  Total lines:      {report.total_lines:>5}                              │")
    lines.append(f"│  Classes:          {report.total_classes:>5}                              │")
    lines.append(f"│  Functions:        {report.total_functions:>5}                              │")
    lines.append(f"│  Hardcoded refs:   {report.total_hardcoded:>5}  (CRITICAL: {report.total_critical}, HIGH: {report.total_high})   │")
    lines.append(f"│  Files w/ PAL:     {report.files_with_pal:>5}                              │")
    lines.append(f"│  Files w/o PAL:    {report.files_without_pal:>5}                              │")
    lines.append(f"│  PAL pointer keys: {report.pointer_registry_keys:>5}                              │")
    lines.append(f"│  Pointer health:   {report.pointer_health:<10}                         │")
    lines.append(f"│  Fleet issues:     {len(report.fleet_discrepancies):>5}                              │")
    lines.append("└──────────────────────────────────────────────────────────┘")
    lines.append("")

    # Hardcoded path violations
    all_refs = []
    for a in report.file_analyses:
        for ref in a.hardcoded_refs:
            all_refs.append(ref)

    if all_refs:
        lines.append("┌─ HARDCODED PATH VIOLATIONS ──────────────────────────────┐")
        for sev in ["CRITICAL", "HIGH", "MEDIUM"]:
            sev_refs = [r for r in all_refs if r.severity == sev]
            if sev_refs:
                lines.append(f"│  [{sev}]")
                for r in sev_refs[:20]:  # Cap per severity
                    lines.append(f"│    {r.file}:L{r.line} — {r.value[:60]}")
                if len(sev_refs) > 20:
                    lines.append(f"│    ... +{len(sev_refs) - 20} more")
        lines.append("└──────────────────────────────────────────────────────────┘")
        lines.append("")

    # Fleet discrepancies
    if report.fleet_discrepancies:
        lines.append("┌─ FLEET MODEL DISCREPANCIES ──────────────────────────────┐")
        for d in report.fleet_discrepancies:
            lines.append(f"│  {d.file}: {d.detail}")
        lines.append("└──────────────────────────────────────────────────────────┘")
        lines.append("")

    # Cross-file dependency graph
    if report.dependency_graph:
        lines.append("┌─ CROSS-FILE DEPENDENCY GRAPH ────────────────────────────┐")
        for fname, deps in sorted(report.dependency_graph.items()):
            lines.append(f"│  {fname} → {', '.join(deps)}")
        lines.append("└──────────────────────────────────────────────────────────┘")
        lines.append("")

    # Risk flags
    risk_files = [a for a in report.file_analyses if a.risk_flags]
    if risk_files:
        lines.append("┌─ STRUCTURAL RISK FLAGS ──────────────────────────────────┐")
        for a in risk_files:
            for flag in a.risk_flags:
                lines.append(f"│  ⚠ {a.basename}: {flag}")
        lines.append("└──────────────────────────────────────────────────────────┘")
        lines.append("")

    # Parse errors
    errors = [a for a in report.file_analyses if a.parse_error]
    if errors:
        lines.append("┌─ PARSE ERRORS ───────────────────────────────────────────┐")
        for a in errors:
            lines.append(f"│  ✗ {a.basename}: {a.parse_error}")
        lines.append("└──────────────────────────────────────────────────────────┘")
        lines.append("")

    # Per-file detail (abbreviated)
    lines.append("┌─ FILE INVENTORY ─────────────────────────────────────────┐")
    for a in sorted(report.file_analyses, key=lambda x: x.basename):
        if a.parse_error:
            lines.append(f"│  ✗ {a.basename} (PARSE ERROR)")
            continue
        pal_icon = "🔑" if (a.has_resolve_pointer or a.has_pal_import) else "  "
        hc_icon = f"⚠{len(a.hardcoded_refs)}" if a.hardcoded_refs else "  "
        lines.append(
            f"│  {pal_icon} {hc_icon:>3}  {a.basename:<45} "
            f"{a.lines:>5}L  {len(a.classes)}C {len(a.functions)}F"
        )
    lines.append("└──────────────────────────────────────────────────────────┘")

    return "\n".join(lines)


def format_hardcoded_only(report: TrueSeeingReport) -> str:
    """Just the hardcoded violations — for quick remediation."""
    lines = []
    lines.append(f"TRUE_SEEING Hardcoded Path Audit — {report.timestamp}")
    lines.append(f"Total violations: {report.total_hardcoded} across {report.files_with_hardcoded} files")
    lines.append(f"Grade: {report.grade}")
    lines.append("")

    for a in sorted(report.file_analyses, key=lambda x: -len(x.hardcoded_refs)):
        if not a.hardcoded_refs:
            continue
        pal_status = "PAL:YES" if a.has_resolve_pointer else "PAL:NO"
        lines.append(f"--- {a.basename} ({pal_status}) ---")
        for ref in a.hardcoded_refs:
            lines.append(f"  [{ref.severity}] L{ref.line}: {ref.value[:80]}")
        lines.append("")

    return "\n".join(lines)


def format_dependency_graph(report: TrueSeeingReport) -> str:
    """DOT-format dependency graph for visualization."""
    lines = ["digraph HFO_TRUE_SEEING {", '  rankdir=LR;', '  node [shape=box, fontsize=10];']

    for fname, deps in sorted(report.dependency_graph.items()):
        for dep in deps:
            lines.append(f'  "{fname}" -> "{dep}";')

    lines.append("}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 6  SSOT STIGMERGY OUTPUT
# ═══════════════════════════════════════════════════════════════

def write_stigmergy(report: TrueSeeingReport) -> Optional[int]:
    """Write TRUE_SEEING findings as a CloudEvent to the SSOT stigmergy trail."""
    if SSOT_DB is None or not SSOT_DB.exists():
        print("⚠ SSOT_DB not resolved via PAL — cannot write stigmergy", file=sys.stderr)
        return None

    event_data = {
        "grade": report.grade,
        "total_files": report.total_files,
        "total_lines": report.total_lines,
        "total_hardcoded": report.total_hardcoded,
        "total_critical": report.total_critical,
        "total_high": report.total_high,
        "files_with_pal": report.files_with_pal,
        "files_without_pal": report.files_without_pal,
        "pal_health_pct": report.pal_health_pct,
        "pointer_health": report.pointer_health,
        "fleet_discrepancies": len(report.fleet_discrepancies),
        "risk_files": sum(1 for a in report.file_analyses if a.risk_flags),
        "parse_errors": sum(1 for a in report.file_analyses if a.parse_error),
        "top_offenders": [
            {"file": a.basename, "count": len(a.hardcoded_refs), "pal": a.has_resolve_pointer}
            for a in sorted(report.file_analyses, key=lambda x: -len(x.hardcoded_refs))[:10]
            if a.hardcoded_refs
        ],
        "governance_files_discovered": discover_governance_files(),
    }

    ts = datetime.now(timezone.utc).isoformat()
    content_hash = hashlib.sha256(json.dumps(event_data, sort_keys=True).encode()).hexdigest()

    try:
        conn = sqlite3.connect(str(SSOT_DB), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, source, subject, timestamp, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                f"hfo.gen{GEN}.p0.true_seeing",
                SOURCE_TAG,
                f"TRUE_SEEING:grade_{report.grade}:hardcoded_{report.total_hardcoded}",
                ts,
                json.dumps(event_data),
                content_hash,
            ),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id
    except Exception as e:
        print(f"⚠ Stigmergy write failed: {e}", file=sys.stderr)
        return None


# ═══════════════════════════════════════════════════════════════
# § 7  SPELL INTERFACE (CLI)
# ═══════════════════════════════════════════════════════════════

def spell_true_seeing(
    mode: str = "report",
    write_stig: bool = False,
    target_dir: Optional[str] = None,
) -> TrueSeeingReport:
    """Cast TRUE_SEEING — the main entry point."""
    target = Path(target_dir) if target_dir else BRONZE_RESOURCES

    # Discover files
    files = discover_python_files(target)
    if not files:
        print("⚠ No Python files found to analyze.", file=sys.stderr)
        return TrueSeeingReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            hfo_root=str(HFO_ROOT),
            bronze_resources=str(target) if target else "UNRESOLVED",
        )

    # Build all-basenames set for internal dep detection
    all_basenames = {os.path.basename(f) for f in files}
    all_stems = {os.path.splitext(os.path.basename(f))[0] for f in files}
    all_names = all_basenames | all_stems

    # Analyze each file
    analyses = []
    for fpath in files:
        analysis = analyze_file(fpath, all_names)
        analyses.append(analysis)

    # Build report
    report = build_report(analyses)

    # Output
    if mode == "json":
        # Serialize with custom handling for sets
        def default_ser(obj):
            if isinstance(obj, set):
                return sorted(obj)
            if isinstance(obj, Path):
                return str(obj)
            return str(obj)
        print(json.dumps(asdict(report), indent=2, default=default_ser))
    elif mode == "hardcoded":
        print(format_hardcoded_only(report))
    elif mode == "dependency":
        print(format_dependency_graph(report))
    elif mode == "fleet":
        if report.fleet_discrepancies:
            for d in report.fleet_discrepancies:
                print(f"[{d.port}] {d.file}: {d.detail}")
        else:
            print("✓ No fleet model discrepancies detected.")
    elif mode == "summary":
        print(f"Grade: {report.grade}")
        print(f"Files: {report.total_files} | Lines: {report.total_lines}")
        print(f"Hardcoded: {report.total_hardcoded} (CRIT:{report.total_critical} HIGH:{report.total_high})")
        print(f"PAL Health: {report.pal_health_pct}% | Pointer: {report.pointer_health}")
        print(f"Fleet Issues: {len(report.fleet_discrepancies)}")
    else:
        print(format_report_text(report))

    # Stigmergy
    if write_stig:
        row_id = write_stigmergy(report)
        if row_id:
            print(f"\n✓ Stigmergy written: row {row_id}", file=sys.stderr)

    return report


# ═══════════════════════════════════════════════════════════════
# § 7b  DAEMON MODE — The Lidless Eye Never Closes
# ═══════════════════════════════════════════════════════════════

_DAEMON_SHUTDOWN = False

def _daemon_signal_handler(signum, frame):
    """Graceful shutdown on SIGINT/SIGTERM."""
    global _DAEMON_SHUTDOWN
    _DAEMON_SHUTDOWN = True
    print(f"\n⊗ TRUE_SEEING daemon received signal {signum} — shutting down gracefully...", file=sys.stderr)

def _write_heartbeat(cycle: int, last_grade: str, last_hardcoded: int) -> Optional[int]:
    """Write a heartbeat event so the fleet knows we're alive."""
    if SSOT_DB is None or not SSOT_DB.exists():
        return None
    try:
        ts = datetime.now(timezone.utc).isoformat()
        data = {
            "daemon": "P0_TRUE_SEEING",
            "cycle": cycle,
            "last_grade": last_grade,
            "last_hardcoded": last_hardcoded,
            "uptime_cycles": cycle,
        }
        content_hash = hashlib.sha256(
            json.dumps({"heartbeat": True, "ts": ts, "cycle": cycle}).encode()
        ).hexdigest()
        conn = sqlite3.connect(str(SSOT_DB), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, source, subject, timestamp, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                f"hfo.gen{GEN}.p0.true_seeing.heartbeat",
                SOURCE_TAG,
                f"HEARTBEAT:cycle_{cycle}:grade_{last_grade}",
                ts,
                json.dumps(data),
                content_hash,
            ),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id
    except Exception as e:
        print(f"⚠ Heartbeat write failed: {e}", file=sys.stderr)
        return None


def daemon_loop(interval: int = 60, mode: str = "summary"):
    """Run TRUE_SEEING in persistent daemon mode.

    Casts TRUE_SEEING every `interval` seconds, writing stigmergy
    and heartbeats. The Lidless Eye never closes.

    Args:
        interval: Seconds between casts (default 60)
        mode:     Output mode per cast (default "summary")
    """
    global _DAEMON_SHUTDOWN
    import signal as _signal

    # Register signal handlers for graceful shutdown
    _signal.signal(_signal.SIGINT, _daemon_signal_handler)
    _signal.signal(_signal.SIGTERM, _daemon_signal_handler)

    cycle = 0
    last_grade = "?"
    last_hardcoded = -1

    print(f"═══════════════════════════════════════════════════", file=sys.stderr)
    print(f"  P0 TRUE_SEEING — Daemon Mode Activated", file=sys.stderr)
    print(f"  Interval: {interval}s | Mode: {mode} | Stigmergy: ON", file=sys.stderr)
    print(f"  The Lidless Eye never closes.", file=sys.stderr)
    print(f"═══════════════════════════════════════════════════", file=sys.stderr)

    while not _DAEMON_SHUTDOWN:
        cycle += 1
        ts_start = time.time()
        print(f"\n─── Cycle {cycle} @ {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} ───", file=sys.stderr)

        try:
            report = spell_true_seeing(mode=mode, write_stig=True)
            last_grade = report.grade
            last_hardcoded = report.total_hardcoded
        except Exception as e:
            print(f"⚠ Cycle {cycle} cast failed: {e}", file=sys.stderr)

        # Heartbeat every cycle
        hb_row = _write_heartbeat(cycle, last_grade, last_hardcoded)
        elapsed = time.time() - ts_start
        print(
            f"  → Grade {last_grade} | {last_hardcoded} hardcoded | "
            f"{elapsed:.1f}s | heartbeat row {hb_row}",
            file=sys.stderr,
        )

        # Sleep in small increments so we can catch shutdown signals
        remaining = max(0, interval - elapsed)
        sleep_step = min(5.0, remaining)
        slept = 0.0
        while slept < remaining and not _DAEMON_SHUTDOWN:
            time.sleep(sleep_step)
            slept += sleep_step

    print(f"\n⊗ TRUE_SEEING daemon stopped after {cycle} cycles.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="P0 TRUE_SEEING — AST System Introspection (Lidless Legion)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  --report          Full human-readable report (default)
  --json            Machine-readable JSON output
  --hardcoded-only  Only show hardcoded path violations
  --dependency      Cross-file dependency graph (DOT format)
  --fleet           Fleet model validation only
  --summary         Executive summary (one-liner)

Examples:
  python hfo_p0_true_seeing.py --report
  python hfo_p0_true_seeing.py --hardcoded-only --stigmergy
  python hfo_p0_true_seeing.py --json > true_seeing_snapshot.json
  python hfo_p0_true_seeing.py --summary
        """,
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--report", action="store_true", default=True, help="Full report (default)")
    mode_group.add_argument("--json", action="store_true", help="JSON output")
    mode_group.add_argument("--hardcoded-only", action="store_true", help="Hardcoded violations only")
    mode_group.add_argument("--dependency", action="store_true", help="Dependency graph (DOT)")
    mode_group.add_argument("--fleet", action="store_true", help="Fleet validation only")
    mode_group.add_argument("--summary", action="store_true", help="Executive summary")

    parser.add_argument("--stigmergy", action="store_true", help="Write findings to SSOT")
    parser.add_argument("--target", type=str, help="Override target directory")
    parser.add_argument("--daemon", action="store_true", help="Persistent daemon mode — cast continuously")
    parser.add_argument("--interval", type=int, default=60, help="Daemon interval in seconds (default: 60)")

    args = parser.parse_args()

    if args.json:
        mode = "json"
    elif args.hardcoded_only:
        mode = "hardcoded"
    elif args.dependency:
        mode = "dependency"
    elif args.fleet:
        mode = "fleet"
    elif args.summary:
        mode = "summary"
    else:
        mode = "report"

    if args.daemon:
        daemon_loop(interval=args.interval, mode=mode)
    else:
        spell_true_seeing(mode=mode, write_stig=args.stigmergy, target_dir=args.target)


if __name__ == "__main__":
    main()
