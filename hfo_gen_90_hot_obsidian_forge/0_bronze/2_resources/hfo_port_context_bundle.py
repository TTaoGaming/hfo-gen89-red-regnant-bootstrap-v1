"""
hfo_port_context_bundle.py — P7 NAVIGATE Port Context Bundle Assembler

Assembles the port context bundle for a given P0-P7 port by:
1. Loading the static baseline JSON from port_bundles/p{n}_bundle.json
2. Querying the `port_bundle_overrides` table in the SSOT SQLite for any
   operator-specified overrides (deeply merged onto the baseline).
3. Returning the final merged bundle dict.

The bundle is injected into the prey8_perceive return dict so the LLM agent
receives full port cosmology, tool restrictions, workflow enforcement, and
commander lore at session open.

Port mapping (OBSIDIAN mnemonic):
  O=P0 OBSERVE / Lidless Legion    / ☰ Qian Heaven 111
  B=P1 BRIDGE  / Web Weaver        / ☱ Dui Lake    110
  S=P2 SHAPE   / Mirror Magus      / ☲ Li Fire     101
  I=P3 INJECT  / Harmonic Hydra    / ☳ Zhen Thunder 100
  D=P4 DISRUPT / Red Regnant       / ☴ Xun Wind    011
  I=P5 IMMUNIZE/ Pyre Praetorian   / ☵ Kan Water   010
  A=P6 ASSIMILATE/ Kraken Keeper   / ☶ Gen Mountain 001
  N=P7 NAVIGATE/ Spider Sovereign  / ☷ Kun Earth   000
"""

from __future__ import annotations

import copy
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# The 8 valid port numbers
VALID_PORTS = tuple(range(8))  # 0-7

# Resolve bundle directory relative to this file
_BUNDLE_DIR = Path(__file__).parent / "port_bundles"

# Default SSOT database path via PAL pointer key resolution
_DEFAULT_DB_RELATIVE = (
    "hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"
)


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_db_path(db_path: Optional[str] = None) -> str:
    """Return an absolute path to the SSOT SQLite database.

    Priority order:
    1. Explicit ``db_path`` argument
    2. HFO_SSOT_DB environment variable
    3. Default relative path from HFO_ROOT (workspace root)
    """
    if db_path:
        return db_path

    env_path = os.environ.get("HFO_SSOT_DB")
    if env_path:
        return env_path

    # Walk up from this file to find the workspace root (contains AGENTS.md)
    candidate = Path(__file__)
    for _ in range(10):  # max 10 levels up
        candidate = candidate.parent
        if (candidate / "AGENTS.md").exists():
            return str(candidate / _DEFAULT_DB_RELATIVE)

    # Fallback: relative from cwd
    return _DEFAULT_DB_RELATIVE


# ---------------------------------------------------------------------------
# Deep merge utility
# ---------------------------------------------------------------------------

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Return a NEW dict that is ``base`` deep-merged with ``override``.

    - Dicts are merged recursively.
    - Lists are REPLACED (not extended) by the override value.
    - Scalar values are replaced by the override value.
    """
    result = copy.deepcopy(base)
    for key, override_val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(override_val, dict):
            result[key] = _deep_merge(result[key], override_val)
        else:
            result[key] = copy.deepcopy(override_val)
    return result


def _apply_field_path(bundle: Dict[str, Any], field_path: str, value_json: str) -> None:
    """Set a nested value in ``bundle`` using a dot-separated ``field_path``.

    Example:
        field_path="tool_list.BLOCKED"
        value_json='["run_in_terminal"]'
    """
    parts = field_path.split(".")
    target = bundle
    for part in parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]

    try:
        target[parts[-1]] = json.loads(value_json)
    except json.JSONDecodeError:
        # Treat as raw string if it's not valid JSON
        target[parts[-1]] = value_json


# ---------------------------------------------------------------------------
# Static bundle loading
# ---------------------------------------------------------------------------

def _load_static_bundle(port: int) -> Dict[str, Any]:
    """Load the static JSON baseline for ``port`` from the bundle directory."""
    if port not in VALID_PORTS:
        raise ValueError(f"Invalid port {port!r}. Must be 0-7.")

    bundle_path = _BUNDLE_DIR / f"p{port}_bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(
            f"Port bundle file not found: {bundle_path}\n"
            f"Expected one of: {[str(_BUNDLE_DIR / f'p{n}_bundle.json') for n in VALID_PORTS]}"
        )

    with bundle_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# SQLite override loading
# ---------------------------------------------------------------------------

def _load_overrides(port: int, db_path: str) -> Dict[str, Any]:
    """Query ``port_bundle_overrides`` in the SSOT database and return a
    merged override dict for ``port``.

    Returns an empty dict if the table does not exist or no overrides are found.
    """
    if not Path(db_path).exists():
        return {}

    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # Check table exists
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='port_bundle_overrides'"
        )
        if cur.fetchone() is None:
            return {}

        cur.execute(
            "SELECT field_path, override_value, operator_note "
            "FROM port_bundle_overrides WHERE port = ? ORDER BY id ASC",
            (port,),
        )
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error:
        return {}

    if not rows:
        return {}

    # Build a synthetic override dict by applying each (field_path, value) pair
    override_bundle: Dict[str, Any] = {}
    for field_path, override_value, _note in rows:
        _apply_field_path(override_bundle, field_path, override_value)

    return override_bundle


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_bundle(port: int, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return the fully-assembled port context bundle for ``port`` (0-7).

    Steps:
    1. Load static JSON baseline from ``port_bundles/p{port}_bundle.json``
    2. Load operator overrides from ``port_bundle_overrides`` SQLite table
    3. Deep-merge overrides onto baseline
    4. Inject ``_meta`` key with assembly provenance

    Args:
        port:    Port number (0-7). Raises ValueError for invalid values.
        db_path: Absolute path to the SSOT SQLite database.  When omitted,
                 the path is resolved via HFO_SSOT_DB env var or default PAL
                 pointer.

    Returns:
        The merged bundle dict, ready for injection into prey8_perceive.
    """
    if port not in VALID_PORTS:
        raise ValueError(f"Invalid port {port!r}. Must be 0-7.")

    resolved_db = _resolve_db_path(db_path)

    static_bundle = _load_static_bundle(port)
    overrides = _load_overrides(port, resolved_db)

    if overrides:
        final_bundle = _deep_merge(static_bundle, overrides)
        source = "static+overrides"
    else:
        final_bundle = copy.deepcopy(static_bundle)
        source = "static_only"

    # Inject assembly metadata
    final_bundle["_meta"] = {
        "assembled_by": "hfo_port_context_bundle.py",
        "port": port,
        "source": source,
        "bundle_dir": str(_BUNDLE_DIR),
        "db_path": resolved_db,
        "override_count": len(overrides),
    }

    return final_bundle


def get_bundle_summary(port: int, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return a lightweight summary of the bundle (no full lore text).

    Useful for logging without flooding the context window.
    """
    bundle = get_bundle(port, db_path)
    return {
        "port": bundle.get("port"),
        "mnemonic_letter": bundle.get("mnemonic_letter"),
        "mnemonic_word": bundle.get("mnemonic_word"),
        "commander": bundle.get("commander"),
        "domain": bundle.get("domain"),
        "bagua_symbol": bundle.get("bagua", {}).get("trigram_symbol"),
        "bagua_name": bundle.get("bagua", {}).get("trigram_name"),
        "bagua_binary": bundle.get("bagua", {}).get("binary"),
        "meadows_primary": bundle.get("meadows_hint", {}).get("primary"),
        "prey8_hexagram_name": bundle.get("bagua", {}).get("prey8_hexagram", {}).get("name"),
        "prey8_hexagram_number": bundle.get("bagua", {}).get("prey8_hexagram", {}).get("number"),
        "tool_blocked_count": len(bundle.get("tool_list", {}).get("BLOCKED", [])),
        "workflow_steps": bundle.get("workflow_enforcement", {}).get("mandatory_sequence", []),
        "_meta": bundle.get("_meta"),
    }


def list_bundles() -> Dict[int, Dict[str, str]]:
    """Return a catalog of all available port bundles (without loading full lore).

    Returns dict keyed by port number with high-level metadata.
    """
    catalog: Dict[int, Dict[str, str]] = {}
    for port in VALID_PORTS:
        path = _BUNDLE_DIR / f"p{port}_bundle.json"
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                catalog[port] = {
                    "letter": data.get("mnemonic_letter", "?"),
                    "word": data.get("mnemonic_word", "?"),
                    "commander": data.get("commander", "?"),
                    "domain": data.get("domain", "?"),
                    "trigram": f"{data.get('bagua', {}).get('trigram_symbol', '?')} {data.get('bagua', {}).get('trigram_name', '?')} ({data.get('bagua', {}).get('binary', '?')})",
                    "file": str(path),
                }
            except (json.JSONDecodeError, KeyError):
                catalog[port] = {"error": f"Failed to parse {path}"}
        else:
            catalog[port] = {"missing": str(path)}
    return catalog


# ---------------------------------------------------------------------------
# Identity Capsule API  (re-exported from hfo_identity_loader)
# ---------------------------------------------------------------------------
# Lazy import to avoid circular dependencies — hfo_identity_loader imports
# hfo_port_journal which is independent of this module.

def get_identity_prompt(port: int) -> str:
    """Return the identity_capsule for ``port`` as a Markdown system-prompt string.

    Thin re-export of ``hfo_identity_loader.get_identity_prompt``.
    See that module for full documentation.
    """
    import importlib
    _loader = importlib.import_module("hfo_identity_loader")
    return _loader.get_identity_prompt(port)


def get_full_bundle_md(
    port: int,
    db_path: Optional[str] = None,
    include_identity: bool = True,
    include_journal: bool = True,
) -> str:
    """Return the combined identity + cognitive-persistence Markdown bundle.

    Thin re-export of ``hfo_identity_loader.get_full_bundle``.
    """
    import importlib
    _loader = importlib.import_module("hfo_identity_loader")
    return _loader.get_full_bundle(
        port,
        db_path=db_path,
        include_identity=include_identity,
        include_journal=include_journal,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="hfo_port_context_bundle",
        description="HFO Port Context Bundle Assembler — P0-P7 Bagua Cosmology",
    )
    sub = parser.add_subparsers(dest="cmd")

    # list command
    list_p = sub.add_parser("list", help="List all available port bundles")

    # summary command
    sum_p = sub.add_parser("summary", help="Get summary for a port")
    sum_p.add_argument("port", type=int, help="Port number 0-7")
    sum_p.add_argument("--db", default=None, help="Path to SSOT SQLite database")

    # get command
    get_p = sub.add_parser("get", help="Get full bundle for a port")
    get_p.add_argument("port", type=int, help="Port number 0-7")
    get_p.add_argument("--db", default=None, help="Path to SSOT SQLite database")
    get_p.add_argument("--no-lore", action="store_true", help="Omit commander_lore and grimoire_summary")

    args = parser.parse_args()

    if args.cmd == "list":
        catalog = list_bundles()
        print("\nHFO Port Bundle Catalog — OBSIDIAN Octree\n")
        print(f"{'Port':<6} {'Letter':<8} {'Word':<12} {'Commander':<22} {'Trigram':<22} {'Domain'}")
        print("─" * 100)
        for port_num in sorted(catalog.keys()):
            row = catalog[port_num]
            if "error" in row or "missing" in row:
                print(f"P{port_num:<5} {'ERR':<8} {row.get('error', row.get('missing', '?'))}")
            else:
                print(f"P{port_num:<5} {row['letter']:<8} {row['word']:<12} {row['commander']:<22} {row['trigram']:<22} {row['domain']}")

    elif args.cmd == "summary":
        try:
            summary = get_bundle_summary(args.port, args.db)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        except (ValueError, FileNotFoundError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.cmd == "get":
        try:
            bundle = get_bundle(args.port, args.db)
            if args.no_lore:
                bundle.pop("commander_lore", None)
                bundle.pop("grimoire_summary", None)
            print(json.dumps(bundle, indent=2, ensure_ascii=False))
        except (ValueError, FileNotFoundError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()
