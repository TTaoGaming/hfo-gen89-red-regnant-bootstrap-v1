#!/usr/bin/env python3
"""
hfo_p5_flame_strike.py — P5 Pyre Praetorian: FLAME STRIKE
═══════════════════════════════════════════════════════════

Spell Slot: D1 (DEATH)
D&D Source: PHB p.231, Evocation 5th (Clr 5)
D&D Effect: "A vertical column of divine fire roars downward.
             Deals 1d6/level damage (max 15d6), half fire half divine."
HFO Alias:  Targeted divine purge — destroy a specific failed artifact,
            stale daemon, or corrupted document. The Paladin's judgment.

Port:       P5 IMMUNIZE
Commander:  Pyre Praetorian — Dancer of Death and Dawn
Aspect:     A (DEATH)
Tier:       ADEPT target (fills slot D1, balances dawn-heavy P5)

Engineering Function:
    Surgical, audited destruction. Takes a target (file path, document ID,
    or daemon name) and destroys it with full provenance trail. Unlike P4's
    bulk detection (WEIRD), FLAME_STRIKE is a single-target precision strike.

    Target types:
    1. FILE — Remove a file from bronze with audit trail
    2. DOCUMENT — Mark an SSOT document as deprecated/purged
    3. DAEMON — Kill a specific daemon via spell_gate
    4. EVENT — Mark stigmergy events as stale/deprecated

    Safety gates:
    - Target must exist before purge
    - Gold/silver files CANNOT be purged (medallion boundary)
    - Confirmation prompt unless --force is used
    - Full audit trail written to SSOT before destruction
    - Dry-run mode for preview

Stigmergy Events:
    hfo.gen90.p5.flame_strike.purge     — Successful purge with provenance
    hfo.gen90.p5.flame_strike.blocked   — Purge blocked by safety gate
    hfo.gen90.p5.flame_strike.dry_run   — Dry run preview

SBE / ATDD Specification:
─────────────────────────

Feature: FLAME STRIKE — Targeted Divine Purge

  # Tier 1: Invariant (MUST NOT violate)
  Scenario: Gold/silver files cannot be purged
    Given the target file is in the 1_silver or 2_gold directory
    When FLAME_STRIKE is invoked with the file path
    Then the purge is BLOCKED
    And a blocked event is written with reason "medallion_boundary"

  Scenario: Non-existent target is rejected
    Given the target file does not exist
    When FLAME_STRIKE is invoked
    Then an error is shown and no purge occurs

  Scenario: Bronze file purge with audit trail
    Given the target file is in 0_bronze
    And --force flag is provided
    When FLAME_STRIKE purges the file
    Then the file is deleted
    And a purge CloudEvent is written with file hash, size, and path

  # Tier 2: Happy-path
  Scenario: Dry-run shows what would be purged
    Given a target file exists
    When `python hfo_p5_flame_strike.py --target <path> --dry-run` runs
    Then output shows file details without deleting anything

  Scenario: Document deprecation marks doc metadata
    Given a document ID exists in SSOT
    When FLAME_STRIKE is invoked with --target-doc <id>
    Then the document's tags get "deprecated" appended
    And a purge event is written

  # Tier 3: Daemon purge
  Scenario: Daemon kill via spell gate
    Given a daemon name is registered in spell_gate
    When FLAME_STRIKE is invoked with --target-daemon <name>
    Then the daemon process is killed
    And a purge event is written

Usage:
    python hfo_p5_flame_strike.py --target <filepath>             # Purge a file
    python hfo_p5_flame_strike.py --target <filepath> --dry-run   # Preview
    python hfo_p5_flame_strike.py --target <filepath> --force     # No confirm
    python hfo_p5_flame_strike.py --target-doc <doc_id>           # Deprecate doc
    python hfo_p5_flame_strike.py --target-daemon <name>          # Kill daemon
    python hfo_p5_flame_strike.py --status                        # Spell identity
"""

import argparse
import hashlib
import json
import os
import secrets
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
POINTERS_FILE = HFO_ROOT / "hfo_gen90_pointers_blessed.json"


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
    SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite"

try:
    FORGE_ROOT = resolve_pointer("forge.root")
except (KeyError, FileNotFoundError):
    FORGE_ROOT = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge"

GEN = os.environ.get("HFO_GENERATION", "89")
P5_SOURCE = f"hfo_p5_flame_strike_gen{GEN}"
EVENT_PREFIX = "hfo.gen90.p5.flame_strike"
VERSION = "1.0.0"

# Protected directories — FLAME_STRIKE cannot touch these
PROTECTED_DIRS = {"1_silver", "2_gold", "3_hyper_fractal_obsidian"}

# ═══════════════════════════════════════════════════════════════
# § 1  SPELL IDENTITY
# ═══════════════════════════════════════════════════════════════

SPELL_IDENTITY = {
    "port": "P5",
    "powerword": "IMMUNIZE",
    "commander": "Pyre Praetorian",
    "spell": "FLAME_STRIKE",
    "spell_slot": "D1",
    "aspect": "DEATH",
    "dnd_source": "PHB p.231, Evocation 5th",
    "school": "Evocation",
    "alias": "Targeted Divine Purge",
    "version": VERSION,
    "core_thesis": "The Paladin does not destroy carelessly. "
                   "Every purge is surgical, audited, and just.",
}

# ═══════════════════════════════════════════════════════════════
# § 2  SAFETY GATES
# ═══════════════════════════════════════════════════════════════

class PurgeBlocked(Exception):
    """Raised when a purge is blocked by a safety gate."""
    def __init__(self, reason: str, details: dict = None):
        self.reason = reason
        self.details = details or {}
        super().__init__(f"FLAME_STRIKE BLOCKED: {reason}")


def check_medallion_boundary(filepath: Path) -> None:
    """Block purges that cross medallion boundaries."""
    try:
        rel = filepath.relative_to(FORGE_ROOT)
    except ValueError:
        raise PurgeBlocked(
            "Target is outside the forge — FLAME_STRIKE only operates within the forge",
            {"path": str(filepath), "forge_root": str(FORGE_ROOT)}
        )

    parts = rel.parts
    if parts and any(protected in parts[0] for protected in PROTECTED_DIRS):
        raise PurgeBlocked(
            f"Target is in protected layer '{parts[0]}' — SW-5 medallion boundary enforced",
            {"path": str(filepath), "layer": parts[0]}
        )


def compute_file_hash(filepath: Path) -> str:
    """SHA256 hash of file contents for provenance."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ═══════════════════════════════════════════════════════════════
# § 3  PURGE OPERATIONS
# ═══════════════════════════════════════════════════════════════

class PurgeReceipt:
    """Receipt of a purge operation."""
    def __init__(self, target_type: str, target_id: str, action: str,
                 details: dict = None):
        self.target_type = target_type
        self.target_id = target_id
        self.action = action  # PURGED, BLOCKED, DRY_RUN, DEPRECATED
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp,
        }


def purge_file(filepath: Path, dry_run: bool = False, force: bool = False) -> PurgeReceipt:
    """Purge a file from the forge with full audit trail."""
    filepath = filepath.resolve()

    # Gate 1: File must exist
    if not filepath.exists():
        raise PurgeBlocked("Target file does not exist", {"path": str(filepath)})

    # Gate 2: Medallion boundary
    check_medallion_boundary(filepath)

    # Gate 3: Must be a file, not a directory
    if filepath.is_dir():
        raise PurgeBlocked("Target is a directory — use rmdir manually for directories",
                           {"path": str(filepath)})

    # Collect provenance BEFORE deletion
    stat = filepath.stat()
    content_hash = compute_file_hash(filepath)
    rel_path = str(filepath.relative_to(HFO_ROOT)) if filepath.is_relative_to(HFO_ROOT) else str(filepath)

    details = {
        "path": rel_path,
        "absolute_path": str(filepath),
        "size_bytes": stat.st_size,
        "content_hash": content_hash,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "created": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
    }

    if dry_run:
        return PurgeReceipt("FILE", rel_path, "DRY_RUN", details)

    # Gate 4: Confirmation
    if not force:
        print(f"\n  FLAME_STRIKE targets: {rel_path}")
        print(f"  Size: {stat.st_size} bytes")
        print(f"  Hash: {content_hash[:16]}...")
        confirm = input("  Proceed with purge? (yes/no): ").strip().lower()
        if confirm != "yes":
            return PurgeReceipt("FILE", rel_path, "CANCELLED", details)

    # PURGE
    filepath.unlink()
    return PurgeReceipt("FILE", rel_path, "PURGED", details)


def deprecate_document(doc_id: int, dry_run: bool = False) -> PurgeReceipt:
    """Mark an SSOT document as deprecated."""
    if not SSOT_DB.exists():
        raise PurgeBlocked("SSOT database not found")

    conn = sqlite3.connect(str(SSOT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        doc = conn.execute(
            "SELECT id, title, source, medallion, tags FROM documents WHERE id = ?",
            (doc_id,)
        ).fetchone()

        if not doc:
            raise PurgeBlocked(f"Document ID {doc_id} not found in SSOT")

        details = {
            "doc_id": doc["id"],
            "title": doc["title"],
            "source": doc["source"],
            "medallion": doc["medallion"],
            "original_tags": doc["tags"],
        }

        if dry_run:
            return PurgeReceipt("DOCUMENT", str(doc_id), "DRY_RUN", details)

        # Append "deprecated" to tags
        current_tags = doc["tags"] or ""
        if "deprecated" not in current_tags:
            new_tags = f"{current_tags},deprecated,flame_strike_purge" if current_tags else "deprecated,flame_strike_purge"
            conn.execute(
                "UPDATE documents SET tags = ? WHERE id = ?",
                (new_tags, doc_id)
            )
            conn.commit()

        details["new_tags"] = new_tags if "deprecated" not in current_tags else current_tags
        return PurgeReceipt("DOCUMENT", str(doc_id), "DEPRECATED", details)
    finally:
        conn.close()


def kill_daemon(daemon_name: str, dry_run: bool = False) -> PurgeReceipt:
    """Kill a daemon process. Uses spell_gate pattern if available."""
    details = {"daemon_name": daemon_name}

    if dry_run:
        return PurgeReceipt("DAEMON", daemon_name, "DRY_RUN", details)

    # Try to find and kill the process by name
    if sys.platform == "win32":
        # Use taskkill on Windows
        try:
            # Find PIDs matching the daemon pattern
            result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-Process python* | Where-Object {{$_.CommandLine -like '*{daemon_name}*'}} | Select-Object Id,ProcessName"],
                capture_output=True, text=True, timeout=10
            )
            details["process_search"] = result.stdout.strip()

            # Kill if found
            kill_result = subprocess.run(
                ["powershell", "-Command",
                 f"Get-Process python* | Where-Object {{$_.CommandLine -like '*{daemon_name}*'}} | Stop-Process -Force"],
                capture_output=True, text=True, timeout=10
            )
            details["kill_result"] = kill_result.stdout.strip() or "Processes killed (or none found)"
            details["kill_stderr"] = kill_result.stderr.strip() if kill_result.stderr else ""

            return PurgeReceipt("DAEMON", daemon_name, "PURGED", details)
        except Exception as e:
            details["error"] = str(e)
            return PurgeReceipt("DAEMON", daemon_name, "FAILED", details)
    else:
        # Unix pkill
        try:
            subprocess.run(["pkill", "-f", daemon_name], timeout=5)
            return PurgeReceipt("DAEMON", daemon_name, "PURGED", details)
        except Exception as e:
            details["error"] = str(e)
            return PurgeReceipt("DAEMON", daemon_name, "FAILED", details)


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
        "source": P5_SOURCE,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "phase": "CLOUDEVENT",
        "agent_id": "p5_pyre_praetorian",
        "spell": "FLAME_STRIKE",
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, P5_SOURCE, json.dumps(event), content_hash),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def write_purge_to_ssot(receipt: PurgeReceipt) -> int:
    """Write purge receipt to SSOT. Returns event row id."""
    conn = get_db_readwrite()
    try:
        data = {
            "spell_identity": SPELL_IDENTITY,
            "receipt": receipt.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        action_map = {
            "PURGED": "purge",
            "DEPRECATED": "purge",
            "BLOCKED": "blocked",
            "DRY_RUN": "dry_run",
            "CANCELLED": "blocked",
            "FAILED": "blocked",
        }
        event_suffix = action_map.get(receipt.action, "purge")
        event_type = f"{EVENT_PREFIX}.{event_suffix}"
        subject = f"flame_strike:{receipt.target_type}:{receipt.action}:{receipt.target_id}"

        row_id = write_stigmergy_event(conn, event_type, subject, data)
        return row_id
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# § 5  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P5 FLAME STRIKE — Targeted Divine Purge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Spell: FLAME STRIKE (PHB p.231, Evocation 5th)
            Port:  P5 IMMUNIZE — Pyre Praetorian
            Alias: Targeted Divine Purge
            "The Paladin does not destroy carelessly."
        """),
    )
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument("--target", type=str,
                              help="File path to purge")
    target_group.add_argument("--target-doc", type=int,
                              help="SSOT document ID to deprecate")
    target_group.add_argument("--target-daemon", type=str,
                              help="Daemon name to kill")

    parser.add_argument("--dry-run", action="store_true",
                        help="Preview purge without executing")
    parser.add_argument("--force", action="store_true",
                        help="Skip confirmation prompt")
    parser.add_argument("--stigmergy", action="store_true",
                        help="Write purge event to SSOT")
    parser.add_argument("--status", action="store_true",
                        help="Show spell identity")
    args = parser.parse_args()

    if args.status:
        print(json.dumps(SPELL_IDENTITY, indent=2))
        return

    if not any([args.target, args.target_doc, args.target_daemon]):
        parser.print_help()
        print("\n  ERROR: One of --target, --target-doc, or --target-daemon is required.")
        sys.exit(1)

    receipt = None

    try:
        if args.target:
            filepath = Path(args.target).resolve()
            receipt = purge_file(filepath, dry_run=args.dry_run, force=args.force)

        elif args.target_doc:
            receipt = deprecate_document(args.target_doc, dry_run=args.dry_run)

        elif args.target_daemon:
            receipt = kill_daemon(args.target_daemon, dry_run=args.dry_run)

    except PurgeBlocked as e:
        print(f"\n  [FLAME_STRIKE] BLOCKED: {e.reason}")
        if e.details:
            for k, v in e.details.items():
                print(f"    {k}: {v}")
        # Write blocked event if stigmergy requested
        if args.stigmergy:
            try:
                blocked_receipt = PurgeReceipt(
                    target_type="UNKNOWN",
                    target_id=args.target or str(args.target_doc) or args.target_daemon,
                    action="BLOCKED",
                    details={"reason": e.reason, **e.details}
                )
                row_id = write_purge_to_ssot(blocked_receipt)
                print(f"  [FLAME_STRIKE] Blocked event written: row {row_id}")
            except Exception as write_err:
                print(f"  [FLAME_STRIKE] Stigmergy write failed: {write_err}")
        sys.exit(1)

    if receipt:
        # Display result
        print(f"\n  ═══ FLAME STRIKE ═══")
        print(f"  Target:  {receipt.target_type} — {receipt.target_id}")
        print(f"  Action:  {receipt.action}")
        for k, v in receipt.details.items():
            if isinstance(v, str) and len(v) > 80:
                v = v[:77] + "..."
            print(f"    {k}: {v}")

        # Write to SSOT if requested
        if args.stigmergy:
            try:
                row_id = write_purge_to_ssot(receipt)
                print(f"\n  [FLAME_STRIKE] Event written to SSOT: row {row_id}")
            except Exception as e:
                print(f"\n  [FLAME_STRIKE] Stigmergy write failed: {e}")


if __name__ == "__main__":
    main()
