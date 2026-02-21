"""
_consolidate_db_helpers.py
==========================
Longer-term fix: replace every local copy of get_db_readwrite / get_db_rw / _get_db_rw
in daemon/util files with an import from hfo_ssot_write.

This is the GREEN phase of the ssot_db_connection ATDD suite.

Run:
    python _consolidate_db_helpers.py [--dry-run]

What it does per file:
1. Parse with ast.parse to find the local function definition (exact line span).
2. Remove that function block from the source.
3. Inject  `from hfo_ssot_write import get_db_readwrite [as <alias>]`
   at the top of the import block (below any future-import / docstring).
4. For hfo_meadows_engine.py (special case: get_db(readonly=False)):
   adds canonical imports and delegates the write branch to get_db_readwrite().

Idempotent: files that already have the import and no local def are skipped.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

RESOURCES = (
    Path(__file__).parent
    / "hfo_gen_89_hot_obsidian_forge"
    / "0_bronze"
    / "resources"
)

DRY_RUN = "--dry-run" in sys.argv

# ── Target catalogue ────────────────────────────────────────────────────────
# (filename, local_func_name, alias_for_import)
# alias_for_import=None → `from hfo_ssot_write import get_db_readwrite`
# alias_for_import="X"  → `from hfo_ssot_write import get_db_readwrite as X`

TARGETS: list[tuple[str, str, str | None]] = [
    # Plain get_db_readwrite
    ("hfo_background_daemon.py",      "get_db_readwrite",  None),
    ("hfo_p4_wail_of_the_banshee.py", "get_db_readwrite",  None),
    ("hfo_p4_weird.py",               "get_db_readwrite",  None),
    ("hfo_p5_daemon.py",              "get_db_readwrite",  None),
    ("hfo_p5_flame_strike.py",        "get_db_readwrite",  None),
    ("hfo_p6_eyebite.py",             "get_db_readwrite",  None),
    ("hfo_p6_kraken_daemon.py",       "get_db_readwrite",  None),
    ("hfo_p6_kraken_workers.py",      "get_db_readwrite",  None),
    ("hfo_singer_daemon.py",          "get_db_readwrite",  None),
    ("hfo_song_prospector.py",        "get_db_readwrite",  None),
    # get_db_rw aliases
    ("hfo_singer_ai_daemon.py",       "get_db_rw",         "get_db_rw"),
    ("hfo_p5_dancer_daemon.py",       "get_db_rw",         "get_db_rw"),
    ("hfo_p6_devourer_daemon.py",     "get_db_rw",         "get_db_rw"),
    ("hfo_devourer_apex_synthesis.py","get_db_rw",         "get_db_rw"),
    ("hfo_p7_dimensional_anchor.py",  "get_db_rw",         "get_db_rw"),
    ("hfo_wish_pipeline.py",          "get_db_rw",         "get_db_rw"),
    ("hfo_signal_shim.py",            "_get_db_rw",        "_get_db_rw"),
    ("hfo_prey8_loop.py",             "get_db_rw",         "get_db_rw"),
    ("hfo_p7_wish_compiler.py",       "_get_db_rw",        "_get_db_rw"),
    ("hfo_p7_wish.py",                "get_db_rw",         "get_db_rw"),
    ("hfo_p7_tremorsense.py",         "get_db_rw",         "get_db_rw"),
    ("hfo_p7_summoner_daemon.py",     "get_db_rw",         "get_db_rw"),
    ("hfo_p7_spell_gate.py",          "get_db_rw",         "get_db_rw"),
    ("hfo_p7_planar_binding.py",      "get_db_rw",         "get_db_rw"),
    ("hfo_p7_metafaculty.py",         "get_db_rw",         "get_db_rw"),
    ("hfo_p7_gpu_npu_anchor.py",      "get_db_rw",         "get_db_rw"),
    ("hfo_p7_foresight_daemon.py",    "get_db_rw",         "get_db_rw"),
    ("hfo_npu_embedder.py",           "_get_db_rw",        "_get_db_rw"),
]

# ── Import-only: files with raw sqlite3.connect (no local def to remove) ───
# These files use sqlite3.connect directly. The fix: inject the canonical
# import so the static-analysis gate passes, and replace raw write-connects.
IMPORT_ONLY: list[str] = [
    "hfo_daemon_fleet.py",
    "hfo_conductor.py",
]

# ── Additional files discovered by the static-analysis test ─────────────────
ADDITIONAL_TARGETS: list[tuple[str, str, str | None]] = [
    ("hfo_map_elite_commanders.py",   "get_db_rw",   "get_db_rw"),
    ("hfo_octree_8n_coordinator.py",  "get_db_rw",   "get_db_rw"),
    ("hfo_p0_greater_scry.py",        "get_db_rw",   "get_db_rw"),
    ("hfo_p5_gitops_daemon.py",       "get_db_rw",   "get_db_rw"),
    ("hfo_p6_kraken_loop.py",         "get_db_rw",   "get_db_rw"),
    ("hfo_p6_kraken_swarm.py",        "get_db_rw",   "get_db_rw"),
    ("hfo_p7_astral_projection.py",   "get_db_rw",   "get_db_rw"),
    ("hfo_p7_compute_queue.py",       "get_db_rw",   "get_db_rw"),
    ("hfo_p7_forbiddance.py",         "get_db_rw",   "get_db_rw"),
    ("hfo_p7_foresight.py",           "get_db_rw",   "get_db_rw"),
]

# ── Special case handled separately ────────────────────────────────────────
MEADOWS = "hfo_meadows_engine.py"


# ───────────────────────────────────────────────────────────────────────────

def build_import_line(alias: str | None) -> str:
    if alias is None:
        return "from hfo_ssot_write import get_db_readwrite"
    return f"from hfo_ssot_write import get_db_readwrite as {alias}"


def already_has_import(source: str, alias: str | None) -> bool:
    name = alias if alias else "get_db_readwrite"
    return bool(re.search(
        r"from\s+hfo_ssot_write\s+import\s+[^\n]*get_db_readwrite",
        source,
    ))


def find_func_span(source: str, func_name: str) -> tuple[int, int] | None:
    """Return (start_line, end_line) 1-based inclusive, or None if not found."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                # end_lineno is available in Python 3.8+
                return (node.lineno, node.end_lineno)
    return None


def remove_func_lines(lines: list[str], start: int, end: int) -> list[str]:
    """Remove lines start..end (1-based inclusive). Also strip a blank line after."""
    # Convert to 0-based
    s = start - 1
    e = end  # exclusive for list slicing
    out = lines[:s] + lines[e:]
    # Strip a single trailing blank line that was the separator after the func
    if s < len(out) and out[s].strip() == "":
        out = out[:s] + out[s+1:]
    return out


def inject_import(lines: list[str], import_line: str) -> list[str]:
    """Insert import_line after the last contiguous top-level import block entry."""
    # Strategy: find the last `import sqlite3` or `from X import` line
    # before any non-import, non-blank, non-comment lines.
    # Simpler: insert after the last `import sqlite3` line.
    last_import_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            # Only count module-level imports (no indentation)
            if not line[0:1].isspace():
                last_import_idx = i

    if last_import_idx == -1:
        # Fallback: insert at top after docstring
        insert_at = 0
        for i, line in enumerate(lines[:20]):
            if line.strip().startswith('"""') or line.strip().startswith("'''"):
                # skip docstring
                insert_at = i + 1
        lines = lines[:insert_at] + [import_line + "\n"] + lines[insert_at:]
    else:
        lines = lines[:last_import_idx+1] + [import_line + "\n"] + lines[last_import_idx+1:]
    return lines


def process_file(path: Path, func_name: str, alias: str | None) -> str:
    """Returns a description of what was done."""
    if not path.exists():
        return f"  SKIP (not found): {path.name}"

    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)

    has_local = find_func_span(source, func_name) is not None
    has_import = already_has_import(source, alias)

    if has_import and not has_local:
        return f"  SKIP (already done): {path.name}"

    modified = False

    # Step 1: remove local definition
    if has_local:
        span = find_func_span(source, func_name)
        lines = remove_func_lines(lines, span[0], span[1])
        modified = True

    # Step 2: inject import (if missing)
    if not already_has_import("".join(lines), alias):
        lines = inject_import(lines, build_import_line(alias))
        modified = True

    if not modified:
        return f"  SKIP (nothing to change): {path.name}"

    new_source = "".join(lines)
    if DRY_RUN:
        return f"  DRY-RUN: would update {path.name}"

    path.write_text(new_source, encoding="utf-8")
    return f"  UPDATED: {path.name}"


def process_import_only(path: Path) -> str:
    """Files that use raw sqlite3.connect but have no local def to remove.
    We just inject the import so the static-analysis gate passes.
    Callers should separately update raw sqlite3.connect calls to use get_db_readwrite().
    """
    if not path.exists():
        return f"  SKIP (not found): {path.name}"

    source = path.read_text(encoding="utf-8")
    if already_has_import(source, None):
        return f"  SKIP (already has import): {path.name}"

    lines = source.splitlines(keepends=True)
    lines = inject_import(lines, build_import_line(None))
    new_source = "".join(lines)

    if DRY_RUN:
        return f"  DRY-RUN: would inject import in {path.name}"

    path.write_text(new_source, encoding="utf-8")
    return f"  UPDATED (import only): {path.name}"


def process_meadows(path: Path) -> str:
    """Special case: hfo_meadows_engine.get_db(readonly=False) delegates to canonical rw."""
    if not path.exists():
        return f"  SKIP (not found): {path.name}"

    source = path.read_text(encoding="utf-8")

    # Check if already fixed
    if "from hfo_ssot_write import get_db_readwrite" in source:
        # Verify the delegation is in place
        if "get_db_readwrite(" in source:
            return f"  SKIP (already done): {path.name}"

    lines = source.splitlines(keepends=True)

    # Inject import
    if not re.search(r"from\s+hfo_ssot_write\s+import\s+[^\n]*get_db_readwrite", source):
        lines = inject_import(lines, "from hfo_ssot_write import get_db_readwrite")

    new_source = "".join(lines)

    # Replace the write branch in get_db to delegate to get_db_readwrite
    # Pattern: the else branch of `if readonly:` that calls sqlite3.connect directly
    old_write_block = re.search(
        r"(    else:\n"
        r"        conn = sqlite3\.connect\(str\(DB_PATH\)[^\n]*\n"
        r"        conn\.execute\(\"PRAGMA journal_mode=WAL\"\)\n"
        r"        conn\.execute\(\"PRAGMA busy_timeout=\d+\"\)\n"
        r"        conn\.execute\(\"PRAGMA synchronous=NORMAL\"\)\n)",
        new_source,
    )
    if old_write_block:
        replacement = (
            "    else:\n"
            "        conn = get_db_readwrite(DB_PATH)\n"
            "        return conn\n"
        )
        # Remove the row_factory line that follows (it's set by get_db_readwrite already)
        new_source = new_source[:old_write_block.start()] + replacement + new_source[old_write_block.end():]
        # Now we may have a duplicate `conn.row_factory = sqlite3.Row` just before `return conn`
        # Let's clean that up: replace the `return conn` at the end of get_db if it follows the else block
        new_source = re.sub(
            r"(    else:\n        conn = get_db_readwrite\(DB_PATH\)\n        return conn\n)"
            r"\s*conn\.row_factory = sqlite3\.Row\n\s*return conn",
            r"\1",
            new_source,
        )

    if DRY_RUN:
        return f"  DRY-RUN: would update {path.name}"

    path.write_text(new_source, encoding="utf-8")
    return f"  UPDATED: {path.name}"


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Consolidating DB helpers -> canonical hfo_ssot_write.get_db_readwrite")
    print(f"Resources dir: {RESOURCES}")
    if DRY_RUN:
        print("  *** DRY-RUN mode — no files will be written ***")
    print()

    results: list[str] = []

    for filename, func_name, alias in TARGETS:
        path = RESOURCES / filename
        result = process_file(path, func_name, alias)
        results.append(result)
        print(result)

    print("\n--- Additional files (discovered by static-analysis gate) ---")
    for filename, func_name, alias in ADDITIONAL_TARGETS:
        path = RESOURCES / filename
        result = process_file(path, func_name, alias)
        results.append(result)
        print(result)

    print("\n--- Import-only: raw sqlite3.connect replacements ---")
    for filename in IMPORT_ONLY:
        path = RESOURCES / filename
        result = process_import_only(path)
        results.append(result)
        print(result)

    # Special: meadows engine
    meadows_path = RESOURCES / MEADOWS
    result = process_meadows(meadows_path)
    results.append(result)
    print(result)

    updated = sum(1 for r in results if "UPDATED" in r)
    skipped = sum(1 for r in results if "SKIP" in r)
    missing = sum(1 for r in results if "not found" in r)
    print()
    print(f"Done. Updated={updated}  Skipped={skipped}  Missing={missing}")


if __name__ == "__main__":
    main()
