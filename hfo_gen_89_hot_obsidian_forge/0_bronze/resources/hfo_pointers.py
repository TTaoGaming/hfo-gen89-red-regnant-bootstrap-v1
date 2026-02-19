#!/usr/bin/env python3
"""
hfo_pointers.py — Gen89 Blessed Path Abstraction Layer (PAL)

Usage:
    python hfo_pointers.py resolve <key>        # Print resolved absolute path
    python hfo_pointers.py list                  # List all pointer keys
    python hfo_pointers.py check                 # Verify all pointers resolve
    python hfo_pointers.py env                   # Print .env as shell exports

Rule: NEVER hardcode a deep forge path. Use a pointer key and resolve it.
"""

import json
import os
import sys
from pathlib import Path


def find_root() -> Path:
    """Walk up from this script or CWD to find AGENTS.md (workspace root)."""
    # Prefer HFO_ROOT env var
    env_root = os.environ.get("HFO_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / "AGENTS.md").exists():
            return p

    # Walk up from CWD
    current = Path.cwd()
    for ancestor in [current] + list(current.parents):
        if (ancestor / "AGENTS.md").exists():
            return ancestor

    # Walk up from script location
    script_dir = Path(__file__).resolve().parent
    for ancestor in [script_dir] + list(script_dir.parents):
        if (ancestor / "AGENTS.md").exists():
            return ancestor

    print("ERROR: Cannot find HFO_ROOT (no AGENTS.md found in ancestors)", file=sys.stderr)
    sys.exit(1)


def load_env(root: Path) -> dict:
    """Parse .env file into dict (no dependency on python-dotenv)."""
    env_file = root / ".env"
    env = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def load_pointers(root: Path) -> dict:
    """Load the blessed pointer registry."""
    # Try well-known names
    for name in ["hfo_gen89_pointers_blessed.json", "hfo_pointers_blessed.json"]:
        fp = root / name
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            return data.get("pointers", data)

    print("ERROR: No blessed pointer file found in root", file=sys.stderr)
    sys.exit(1)


def resolve(root: Path, pointers: dict, key: str) -> Path:
    """Resolve a pointer key to an absolute path."""
    if key not in pointers:
        print(f"ERROR: Unknown pointer key '{key}'", file=sys.stderr)
        print(f"  Available: {', '.join(sorted(pointers.keys()))}", file=sys.stderr)
        sys.exit(1)

    entry = pointers[key]
    rel_path = entry["path"] if isinstance(entry, dict) else entry
    return root / rel_path


def cmd_resolve(root, pointers, args):
    if not args:
        print("Usage: hfo_pointers.py resolve <key>", file=sys.stderr)
        sys.exit(1)
    path = resolve(root, pointers, args[0])
    print(str(path))


def cmd_list(root, pointers, args):
    max_key = max(len(k) for k in pointers)
    for key, entry in sorted(pointers.items()):
        desc = entry.get("desc", "") if isinstance(entry, dict) else ""
        rel = entry["path"] if isinstance(entry, dict) else entry
        exists = "✓" if (root / rel).exists() else "✗"
        print(f"  {exists} {key:{max_key}}  →  {rel}")
        if desc:
            print(f"    {'':>{max_key}}     {desc}")


def cmd_check(root, pointers, args):
    errors = 0
    for key, entry in sorted(pointers.items()):
        rel = entry["path"] if isinstance(entry, dict) else entry
        full = root / rel
        if full.exists():
            print(f"  ✓ {key} → {rel}")
        else:
            print(f"  ✗ {key} → {rel}  [MISSING]")
            errors += 1
    if errors:
        print(f"\n{errors} pointer(s) unresolved.")
        sys.exit(1)
    else:
        print(f"\nAll {len(pointers)} pointers resolved.")


def cmd_env(root, pointers, args):
    env = load_env(root)
    for k, v in sorted(env.items()):
        if "SECRET" in k:
            v = "***"
        print(f"export {k}={v}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    root = find_root()
    pointers = load_pointers(root)

    commands = {
        "resolve": cmd_resolve,
        "list": cmd_list,
        "check": cmd_check,
        "env": cmd_env,
    }

    if cmd in commands:
        commands[cmd](root, pointers, sys.argv[2:])
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(f"Available: {', '.join(commands.keys())}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
