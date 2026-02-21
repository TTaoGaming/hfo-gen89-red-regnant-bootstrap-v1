"""
omega_v13_amalgam.py — Omega v13 Source Amalgamation Tool
==========================================================

Industry term: SOURCE AMALGAMATION
  Coined by SQLite, which ships its entire source as a single "amalgamation"
  file (sqlite3.c) for portability and ease of review. In LLM/AI workflows
  the same concept is called a "context bundle" or "LLM context pack".

What this produces:
  A single, self-describing Markdown file containing:
    - Header: timestamp, source root, stats
    - File tree (visual directory listing)
    - Table of Contents with per-file metadata (size, lines)
    - All source files, each fenced in the correct language
    - Token estimate footer (chars / 4, rough but useful)

  Output: dist/OMEGA_V13_AMALGAM_<YYYY-MM-DD_HHMMSS>.md

Usage:
    python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/omega_v13_amalgam.py

    # Dry-run (list files, no write):
    python ... --dry-run

    # Specify alternate output dir:
    python ... --out-dir C:\\some\\path

    # Include test files (excluded by default):
    python ... --include-tests
"""

from __future__ import annotations

import argparse
import datetime
import os
import pathlib
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = pathlib.Path(
    r"C:\hfoDev\hfo_gen_89_hot_obsidian_forge\1_silver\projects\omega_v13_microkernel"
)

DEFAULT_OUT_DIR = PROJECT_ROOT / "dist"

# Directories to never descend into
SKIP_DIRS: set[str] = {
    "node_modules",
    "dist",
    "exemplars",
    "test-results",
    "reports",
    ".git",
    "__pycache__",
}

# Filenames to always skip
SKIP_FILES: set[str] = {
    "package-lock.json",
}

# Extensions to include
INCLUDE_EXT: set[str] = {
    ".ts",
    ".tsx",
    ".mjs",
    ".js",
    ".json",
    ".html",
    ".md",
    ".scxml",
    ".py",
    ".txt",
    ".css",
    ".scss",
}

# Extension → fenced-code language label
EXT_LANG: dict[str, str] = {
    ".ts":    "typescript",
    ".tsx":   "tsx",
    ".mjs":   "javascript",
    ".js":    "javascript",
    ".json":  "json",
    ".html":  "html",
    ".md":    "markdown",
    ".scxml": "xml",
    ".py":    "python",
    ".txt":   "text",
    ".css":   "css",
    ".scss":  "scss",
}

# Sort priority: lower number = earlier in output
# Docs/specs first → source → configs → tests
SORT_ORDER: dict[str, int] = {
    ".md":    0,    # docs / specs / SBEs
    ".scxml": 1,    # state machine definitions
    ".ts":    2,    # TypeScript source
    ".tsx":   3,
    ".mjs":   4,
    ".js":    5,
    ".html":  6,
    ".json":  7,    # configs
    ".py":    8,
    ".txt":   9,
    ".css":   10,
    ".scss":  11,
}

# Test-file patterns — excluded by default, included with --include-tests
TEST_PATTERNS: tuple[str, ...] = (
    ".spec.ts",
    ".test.ts",
    ".spec.tsx",
    ".test.tsx",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_test_file(p: pathlib.Path) -> bool:
    name = p.name.lower()
    return any(name.endswith(pat) for pat in TEST_PATTERNS) or p.parent.name == "tests"


def sort_key(p: pathlib.Path, root: pathlib.Path) -> tuple[int, str]:
    ext = p.suffix.lower()
    rel = str(p.relative_to(root)).replace("\\", "/").lower()
    return (SORT_ORDER.get(ext, 99), rel)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: chars / 4 (standard LLM approximation)."""
    return len(text) // 4


def build_file_tree(files: list[pathlib.Path], root: pathlib.Path) -> str:
    """Render a visual directory tree from the file list."""
    # Collect unique directories
    dirs: set[pathlib.Path] = {root}
    for f in files:
        dirs.update(f.parents)
    dirs = {d for d in dirs if root in d.parents or d == root}

    # Build tree as lines
    lines: list[str] = [f"{root.name}/"]
    processed_dirs: set[pathlib.Path] = set()

    def render(parent: pathlib.Path, prefix: str = "") -> None:
        if parent in processed_dirs:
            return
        processed_dirs.add(parent)

        children_dirs = sorted(
            d for d in dirs
            if d.parent == parent and d != parent
        )
        children_files = sorted(
            f for f in files
            if f.parent == parent
        )
        all_children: list[tuple[str, bool]] = (
            [(d.name + "/", True) for d in children_dirs] +
            [(f.name, False) for f in children_files]
        )
        for i, (name, is_dir) in enumerate(all_children):
            connector = "└── " if i == len(all_children) - 1 else "├── "
            lines.append(f"{prefix}{connector}{name}")
            if is_dir:
                extension = "    " if i == len(all_children) - 1 else "│   "
                # Find the actual Path object
                actual_dir = next(d for d in children_dirs if d.name + "/" == name)
                render(actual_dir, prefix + extension)

    render(root)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def collect_files(root: pathlib.Path, include_tests: bool) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for p in root.rglob("*"):
        # Skip hidden / system
        if any(part.startswith(".") for part in p.parts[len(root.parts):]):
            continue
        # Skip excluded dirs
        if any(skip in p.parts for skip in SKIP_DIRS):
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() not in INCLUDE_EXT:
            continue
        if p.name in SKIP_FILES:
            continue
        # Skip existing amalgam / concat outputs (any previous run of this tool
        # or the old ad-hoc _concat_omega_v13.py scripts)
        n = p.name.upper()
        if n.startswith("OMEGA_V13_AMALGAM_") or n.startswith("OMEGA_V13_CONCAT_"):
            continue
        if not include_tests and is_test_file(p):
            continue
        files.append(p)

    files.sort(key=lambda p: sort_key(p, root))
    return files


def build_amalgam(
    root: pathlib.Path,
    files: list[pathlib.Path],
    include_tests: bool,
    timestamp: str,
) -> str:
    fence = "```"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    sections: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────
    sections.append(
        f"# Omega v13 Microkernel — Source Amalgamation\n\n"
        f"> **Amalgamation** (n.): A single, self-describing file containing all "
        f"source code of a project, structured for portability and external review.  \n"
        f"> Coined by SQLite; used in AI workflows as a \"context bundle\" or "
        f"\"LLM context pack\".\n\n"
        f"| Key | Value |\n"
        f"|-----|-------|\n"
        f"| Generated | `{now_iso}` |\n"
        f"| Source root | `{root}` |\n"
        f"| Files included | `{len(files)}` |\n"
        f"| Tests included | `{include_tests}` |\n"
    )

    # ── File tree ─────────────────────────────────────────────────────────
    tree = build_file_tree(files, root)
    sections.append(
        f"## File Tree\n\n"
        f"{fence}text\n{tree}\n{fence}\n"
    )

    # ── Table of Contents ─────────────────────────────────────────────────
    toc_rows = ["| # | File | Lines | Size |", "|---|------|-------|------|"]
    total_lines = 0
    total_bytes = 0
    file_contents: list[tuple[pathlib.Path, str]] = []

    for i, p in enumerate(files, 1):
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raw = f"[ERROR READING: {e}]"
        lines_n = raw.count("\n")
        size_b = len(raw.encode("utf-8"))
        total_lines += lines_n
        total_bytes += size_b
        rel = str(p.relative_to(root)).replace("\\", "/")
        anchor = rel.lower().replace("/", "").replace(".", "").replace("_", "").replace("-", "")
        toc_rows.append(
            f"| {i} | [`{rel}`](#{anchor}) | {lines_n:,} | {size_b / 1024:.1f} KB |"
        )
        file_contents.append((p, raw))

    sections.append(
        f"## Table of Contents\n\n"
        + "\n".join(toc_rows)
        + f"\n\n**Total:** {len(files)} files · {total_lines:,} lines · "
        f"{total_bytes / 1024:.1f} KB\n"
    )

    # ── Source files ──────────────────────────────────────────────────────
    sections.append("## Source Files\n")

    for p, raw in file_contents:
        rel = str(p.relative_to(root)).replace("\\", "/")
        ext = p.suffix.lower()
        lang = EXT_LANG.get(ext, "text")
        size_kb = len(raw.encode("utf-8")) / 1024

        sections.append(
            f"---\n\n"
            f"### `{rel}`\n\n"
            f"*{size_kb:.1f} KB · {raw.count(chr(10)):,} lines*\n\n"
        )
        if lang == "markdown":
            # Render inline rather than fencing to preserve formatting
            sections.append(raw)
            if not raw.endswith("\n"):
                sections.append("\n")
        else:
            sections.append(f"{fence}{lang}\n{raw}\n{fence}\n")

    # ── Footer / token estimate ────────────────────────────────────────────
    full_text_so_far = "\n\n".join(sections)
    est_tokens = estimate_tokens(full_text_so_far)

    sections.append(
        f"---\n\n"
        f"## Amalgamation Footer\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Total files | {len(files)} |\n"
        f"| Total lines | {total_lines:,} |\n"
        f"| Total size | {total_bytes / 1024:.1f} KB |\n"
        f"| Estimated tokens | ~{est_tokens:,} |\n"
        f"| Timestamp | `{now_iso}` |\n\n"
        f"> Token estimate: `len(text) / 4` — standard approximation.  \n"
        f"> Actual token count varies by model tokenizer.\n"
    )

    return "\n\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a single-file source amalgamation of Omega v13."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List files that would be included but don't write output."
    )
    parser.add_argument(
        "--include-tests", action="store_true",
        help="Include .spec.ts and .test.ts files (excluded by default)."
    )
    parser.add_argument(
        "--out-dir", type=str, default=None,
        help=f"Output directory (default: {DEFAULT_OUT_DIR})"
    )
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_file = out_dir / f"OMEGA_V13_AMALGAM_{timestamp}.md"

    if not PROJECT_ROOT.exists():
        print(f"ERROR: Project root not found: {PROJECT_ROOT}", file=sys.stderr)
        return 1

    files = collect_files(PROJECT_ROOT, include_tests=args.include_tests)

    if not files:
        print("ERROR: No files matched. Check INCLUDE_EXT and SKIP_DIRS.", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"DRY RUN — {len(files)} files would be included:")
        for f in files:
            rel = str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")
            size = f.stat().st_size
            print(f"  [{f.suffix:5s}] {rel:60s} {size / 1024:>7.1f} KB")
        return 0

    print(f"Building amalgamation of {len(files)} files...")
    content = build_amalgam(PROJECT_ROOT, files, args.include_tests, timestamp)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file.write_text(content, encoding="utf-8")

    size_kb = out_file.stat().st_size / 1024
    est_tokens = estimate_tokens(content)

    print(f"\n✓ Amalgamation written")
    print(f"  Output  : {out_file}")
    print(f"  Files   : {len(files)}")
    print(f"  Size    : {size_kb:.1f} KB")
    print(f"  ~Tokens : ~{est_tokens:,}")
    print()
    print("To review with an external AI, share:")
    print(f"  {out_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
