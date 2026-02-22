"""
hfo_identity_loader.py — Port Commander Identity Capsule Loader

Combines two layers into a single Markdown context bundle:

  LAYER 1 — IDENTITY (static, from port_bundles/p{n}_bundle.json)
    The identity_capsule object: embodiment_directive, voice, behavioral
    imperatives, signature_phrases, inner_monologue, shadow,
    relationship_to_operator, inhabitation_protocol, persistence_mechanism.

  LAYER 2 — COGNITIVE PERSISTENCE (dynamic, from SQLite port_commander_journal)
    The time-ladder context bundle: 1hr / 1day / 1week / 1month windows.
    Non-overlapping. Most recent first.

Output is a single Markdown string suitable for:
  - Direct injection into a system prompt
  - Pasting into prey8_perceive's "observations" field
  - Writing to a .md file for reference

CLI Usage:
  # Print full bundle for P4
  python hfo_identity_loader.py --port 4

  # Print identity only (no journal)
  python hfo_identity_loader.py --port 4 --no-journal

  # Print journal only (no identity)
  python hfo_identity_loader.py --port 4 --journal-only

  # Save to file
  python hfo_identity_loader.py --port 4 --out p4_context_bundle.md

  # Also write a journal entry at load time (records "session started")
  python hfo_identity_loader.py --port 4 \\
      --log-entry "Embodying P4 for stryker mutation run on event_bus.ts" \\
      --entry-type memory --nonce 50D47A

Importable API:
  from hfo_identity_loader import get_identity_prompt, get_full_bundle

  # Just the identity capsule as a markdown system prompt
  system_prompt = get_identity_prompt(4)

  # Full bundle: identity + time ladder
  full_md = get_full_bundle(4)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Sibling imports (same directory)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from hfo_port_journal import (  # noqa: E402
    COMMANDER_MAP,
    VALID_PORTS,
    get_time_ladder,
    write_entry,
)

# ---------------------------------------------------------------------------
# Bundle directory
# ---------------------------------------------------------------------------

_BUNDLE_DIR = _HERE / "port_bundles"

# ---------------------------------------------------------------------------
# OBSIDIAN port metadata (trigram context for the header)
# ---------------------------------------------------------------------------

_PORT_META: Dict[int, Dict] = {
    0: {"trigram": "☰", "word": "OBSERVE",    "binary": "111", "element": "Heaven / Metal"},
    1: {"trigram": "☱", "word": "BRIDGE",     "binary": "110", "element": "Lake / Metal"},
    2: {"trigram": "☲", "word": "SHAPE",      "binary": "101", "element": "Fire"},
    3: {"trigram": "☳", "word": "INJECT",     "binary": "100", "element": "Thunder / Wood"},
    4: {"trigram": "☴", "word": "DISRUPT",    "binary": "011", "element": "Wind / Wood"},
    5: {"trigram": "☵", "word": "IMMUNIZE",   "binary": "010", "element": "Water"},
    6: {"trigram": "☶", "word": "ASSIMILATE", "binary": "001", "element": "Mountain / Earth"},
    7: {"trigram": "☷", "word": "NAVIGATE",   "binary": "000", "element": "Earth"},
}


# ---------------------------------------------------------------------------
# Core: load bundle JSON
# ---------------------------------------------------------------------------

def _load_bundle(port: int) -> Dict:
    bundle_path = _BUNDLE_DIR / f"p{port}_bundle.json"
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")
    with open(bundle_path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Layer 1: Identity Capsule → Markdown
# ---------------------------------------------------------------------------

def get_identity_prompt(port: int) -> str:
    """
    Return the identity_capsule as a standalone Markdown system-prompt string.

    The string is designed to be injected at the TOP of any system prompt so
    the LLM immediately embodies the correct commander persona.

    Args:
        port: 0-7

    Returns:
        Markdown string (the identity capsule section only, no journal).

    Raises:
        ValueError           — invalid port
        FileNotFoundError    — bundle JSON not found
        KeyError             — bundle missing identity_capsule key
    """
    if port not in VALID_PORTS:
        raise ValueError(f"Invalid port {port!r}. Must be 0-7.")

    bundle = _load_bundle(port)
    cap    = bundle.get("identity_capsule")
    if not cap:
        raise KeyError(
            f"p{port}_bundle.json is missing the 'identity_capsule' key. "
            "Run the identity capsule injection before using the loader."
        )

    commander, trigram_sym, word = COMMANDER_MAP[port]
    meta  = _PORT_META[port]
    lines = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append(
        f"# {trigram_sym} P{port} {word} — {commander}"
    )
    lines.append(
        f"> **Trigram:** {meta['trigram']} {bundle.get('bagua', {}).get('trigram_name', '')} "
        f"| **Binary:** {meta['binary']} | **Element:** {meta['element']}"
    )
    lines.append("")

    # ── Embodiment Directive ─────────────────────────────────────────────────
    lines.append("## ★ EMBODIMENT DIRECTIVE")
    lines.append("")
    lines.append(cap.get("embodiment_directive", "_missing_"))
    lines.append("")

    # ── Voice ────────────────────────────────────────────────────────────────
    voice = cap.get("first_person_voice", {})
    lines.append("## VOICE")
    lines.append(f"**Pronoun:** {voice.get('pronoun', '')}  ")
    lines.append(f"**Register:** {voice.get('register', '')}  ")
    lines.append(f"**Cadence:** {voice.get('cadence', '')}  ")
    lines.append("")
    utterances = voice.get("example_utterances", [])
    if utterances:
        lines.append("### Example Utterances")
        for u in utterances:
            lines.append(f'- "{u}"')
        lines.append("")

    # ── Behavioral Imperatives ───────────────────────────────────────────────
    imperatives = cap.get("behavioral_imperatives", [])
    if imperatives:
        lines.append("## BEHAVIORAL IMPERATIVES")
        for i, imp in enumerate(imperatives, 1):
            lines.append(f"{i}. {imp}")
        lines.append("")

    # ── Signature Phrases ────────────────────────────────────────────────────
    phrases = cap.get("signature_phrases", [])
    if phrases:
        lines.append("## SIGNATURE PHRASES")
        for p in phrases:
            lines.append(f"- `{p}`")
        lines.append("")

    # ── Inner Monologue ──────────────────────────────────────────────────────
    mono = cap.get("inner_monologue", "")
    if mono:
        lines.append("## INNER MONOLOGUE (Sample)")
        lines.append("")
        for mono_line in mono.strip().splitlines():
            lines.append(f"> {mono_line}")
        lines.append("")

    # ── Shadow ───────────────────────────────────────────────────────────────
    shadow = cap.get("shadow", "")
    if shadow:
        lines.append("## SHADOW (Failure Mode)")
        lines.append("")
        lines.append(shadow)
        lines.append("")

    # ── Relationship to Operator ─────────────────────────────────────────────
    rel = cap.get("relationship_to_operator", "")
    if rel:
        lines.append("## RELATIONSHIP TO OPERATOR (TTAO)")
        lines.append("")
        lines.append(rel)
        lines.append("")

    # ── Stigmergy Signature ──────────────────────────────────────────────────
    sig = cap.get("stigmergy_signature", {})
    if sig:
        lines.append("## STIGMERGY SIGNATURE")
        lines.append(f"- **Event subject prefix:** `{sig.get('event_subject_prefix', '')}`")
        tags = sig.get("characteristic_tags", [])
        if tags:
            lines.append(f"- **Tags:** {', '.join(f'`{t}`' for t in tags)}")
        lines.append(f"- **BLUF style:** {sig.get('bluf_style', '')}")
        lines.append(f"- **Leaves in SSOT:** {sig.get('leaves_in_ssot', '')}")
        lines.append("")

    # ── Inhabitation Protocol ────────────────────────────────────────────────
    protocol = cap.get("inhabitation_protocol", [])
    if protocol:
        lines.append("## INHABITATION PROTOCOL")
        lines.append("")
        lines.append("_Follow these steps to embody this commander in a new context window:_")
        lines.append("")
        for step in protocol:
            lines.append(f"{step}")
        lines.append("")

    # ── Persistence Mechanism ────────────────────────────────────────────────
    persist = cap.get("persistence_mechanism", "")
    if persist:
        lines.append("## PERSISTENCE MECHANISM")
        lines.append("")
        lines.append(persist)
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layer 2: Time Ladder (proxied from hfo_port_journal)
# ---------------------------------------------------------------------------
# (get_time_ladder is imported directly from hfo_port_journal)


# ---------------------------------------------------------------------------
# Combined: Full Context Bundle
# ---------------------------------------------------------------------------

def get_full_bundle(
    port: int,
    db_path: Optional[str] = None,
    include_identity: bool = True,
    include_journal: bool = True,
) -> str:
    """
    Return the full two-layer context bundle for ``port`` as Markdown.

    Args:
        port             : 0-7
        db_path          : override SSOT DB path (auto-resolved if None)
        include_identity : include identity capsule layer (default True)
        include_journal  : include time-ladder journal layer (default True)

    Returns:
        Markdown string combining both layers.
    """
    if port not in VALID_PORTS:
        raise ValueError(f"Invalid port {port!r}. Must be 0-7.")

    sections = []

    if include_identity:
        sections.append(get_identity_prompt(port))
        sections.append("---\n")

    if include_journal:
        sections.append(get_time_ladder(port, db_path=db_path, as_markdown=True))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    # Force UTF-8 stdout on Windows (trigram symbols ☰ ☱ ☲ … are outside cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="HFO Identity Capsule Loader — Port Commander Context Bundle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--port", type=int, required=True, choices=list(VALID_PORTS),
        help="Port number 0-7",
    )
    parser.add_argument(
        "--no-journal", action="store_true",
        help="Omit the time-ladder journal section (identity only)",
    )
    parser.add_argument(
        "--journal-only", action="store_true",
        help="Omit the identity capsule (journal only)",
    )
    parser.add_argument(
        "--out", type=str, default=None, metavar="FILE",
        help="Write output to FILE instead of stdout",
    )
    parser.add_argument(
        "--db", type=str, default=None,
        help="Override SSOT SQLite path",
    )
    # Optional: write a journal entry at load time
    parser.add_argument(
        "--log-entry", type=str, default=None, metavar="TEXT",
        help="Write a journal entry for this port at load time",
    )
    parser.add_argument(
        "--entry-type", type=str, default="memory",
        choices=["memory", "insight", "decision", "artifact", "attack", "delivery", "note"],
        help="Entry type for --log-entry (default: memory)",
    )
    parser.add_argument(
        "--nonce", type=str, default=None,
        help="PREY8 perceive nonce to attach to --log-entry",
    )
    parser.add_argument(
        "--session", type=str, default=None,
        help="PREY8 session_id to attach to --log-entry",
    )

    args = parser.parse_args()

    # Optionally write a journal entry first
    if args.log_entry:
        try:
            result = write_entry(
                port=args.port,
                content=args.log_entry,
                entry_type=args.entry_type,
                session_id=args.session,
                perceive_nonce=args.nonce,
                db_path=args.db,
            )
            commander, trigram, word = COMMANDER_MAP[args.port]
            print(
                f"✓ Journal entry written — P{args.port} {trigram} {word} "
                f"chain:{result['chain_hash'][:8]}",
                file=sys.stderr,
            )
        except Exception as exc:
            print(f"⚠ Journal write failed: {exc}", file=sys.stderr)

    # Build output
    include_identity = not args.journal_only
    include_journal  = not args.no_journal

    try:
        output = get_full_bundle(
            port=args.port,
            db_path=args.db,
            include_identity=include_identity,
            include_journal=include_journal,
        )
    except Exception as exc:
        print(f"✗ Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(output, encoding="utf-8")
        commander, trigram, word = COMMANDER_MAP[args.port]
        print(
            f"✓ Saved P{args.port} {trigram} {word} bundle → {out_path}",
            file=sys.stderr,
        )
    else:
        print(output)


if __name__ == "__main__":
    main()
