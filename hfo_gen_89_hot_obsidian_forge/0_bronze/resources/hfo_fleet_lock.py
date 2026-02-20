#!/usr/bin/env python3
"""
hfo_fleet_lock.py — PID Lockfile Fleet Single-Instance Enforcement
==================================================================
v1.0 | Gen89 | Port: ALL | Medallion: bronze

PURPOSE:
    OS-level file lock that prevents duplicate daemon instances.
    Replaces zombie .venv launchers that waste 400MB RAM and cause
    GPU scheduling contention.

STRUCTURAL ENFORCEMENT:
    - Uses msvcrt.locking() on Windows, fcntl.flock() on Unix
    - Lock is OS-level (kernel holds it), not advisory
    - If process crashes, OS releases the file handle automatically
    - PID written to lockfile for diagnostics only (not relied upon)

GHERKIN CONTRACT: hfo_structural_enforcement.feature Feature 2

Usage:
    from hfo_fleet_lock import acquire_daemon_lock

    lock = acquire_daemon_lock("singer_p4")
    if lock is None:
        # Already running — acquire_daemon_lock printed error and returned None
        sys.exit(1)
    # ... daemon runs ...
    # Lock auto-released on process exit (OS handles it)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# § 0  PAL — Lockfile directory
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = _find_root()
LOCK_DIR = HFO_ROOT / ".locks"


# ═══════════════════════════════════════════════════════════════
# § 1  PLATFORM-SPECIFIC LOCKING
# ═══════════════════════════════════════════════════════════════

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import msvcrt

    def _try_lock(fd: int) -> bool:
        """Try to acquire an exclusive lock on fd (Windows). Returns True if acquired."""
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except (OSError, IOError):
            return False

else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        """Try to acquire an exclusive lock on fd (Unix). Returns True if acquired."""
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError):
            return False


# ═══════════════════════════════════════════════════════════════
# § 2  ACQUIRE DAEMON LOCK — The Core Function
# ═══════════════════════════════════════════════════════════════

# Module-level storage to prevent GC from closing the file handle.
# If the handle is garbage-collected, the OS releases the lock.
_held_locks: dict[str, object] = {}


def acquire_daemon_lock(
    daemon_name: str,
    lock_dir: Optional[Path] = None,
) -> Optional[object]:
    """
    Acquire an exclusive file lock for a daemon instance.

    If another process already holds the lock, prints an error message
    and returns None. The caller should exit with code 1.

    The lock is automatically released when the process exits (OS handles it).
    The returned file handle MUST be kept alive (stored in a variable) or
    the lock will be released when garbage-collected.

    Args:
        daemon_name: Unique daemon identifier (e.g. "singer_p4", "kraken_p6")
        lock_dir:    Lock directory (default: {HFO_ROOT}/.locks/)

    Returns:
        File handle (truthy) if lock acquired, or None if already held.
    """
    lock_path = (lock_dir or LOCK_DIR) / f"{daemon_name.lower()}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Open file for read/write, create if needed, DON'T truncate yet
        fh = open(lock_path, "a+")
    except OSError as e:
        print(f"LOCK_ERROR: Cannot open lockfile {lock_path}: {e}", file=sys.stderr)
        return None

    fd = fh.fileno()

    if not _try_lock(fd):
        # Lock is held by another process. Read the PID for diagnostics.
        try:
            fh.seek(0)
            existing_pid = fh.read().strip()
        except Exception:
            existing_pid = "unknown"
        fh.close()

        print(
            f"LOCK_HELD: {daemon_name} already running (PID {existing_pid}). "
            f"Lockfile: {lock_path}",
            file=sys.stderr,
        )
        return None

    # Lock acquired. Write our PID.
    try:
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
    except OSError:
        pass  # Non-critical — PID is diagnostic only

    # Store handle to prevent GC from releasing the lock
    _held_locks[daemon_name] = fh

    return fh


def release_daemon_lock(daemon_name: str) -> bool:
    """
    Explicitly release a daemon lock. Usually not needed — OS releases on exit.

    Returns True if lock was held and released, False otherwise.
    """
    fh = _held_locks.pop(daemon_name, None)
    if fh is None:
        return False
    try:
        fh.close()
    except Exception:
        pass
    return True


def is_daemon_locked(
    daemon_name: str,
    lock_dir: Optional[Path] = None,
) -> tuple[bool, Optional[int]]:
    """
    Check if a daemon lock is held WITHOUT acquiring it.

    Returns (is_locked, pid_or_none).
    """
    lock_path = (lock_dir or LOCK_DIR) / f"{daemon_name.lower()}.lock"

    if not lock_path.exists():
        return False, None

    try:
        fh = open(lock_path, "a+")
        fd = fh.fileno()
        if _try_lock(fd):
            # We got the lock — nobody else has it. Release immediately.
            if _IS_WINDOWS:
                try:
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            # On Unix, closing the fd releases flock
            fh.close()
            return False, None
        else:
            # Locked by someone else. Read PID.
            fh.seek(0)
            pid_text = fh.read().strip()
            fh.close()
            try:
                return True, int(pid_text)
            except ValueError:
                return True, None
    except OSError:
        return False, None


# ═══════════════════════════════════════════════════════════════
# § 3  FLEET STATUS — Show all locks
# ═══════════════════════════════════════════════════════════════

# Standard daemon names mapped to their ports
FLEET_DAEMONS = {
    "watcher_p0":    "P0",
    "background_p7": "P7",
    "singer_p4":     "P4",
    "dancer_p5":     "P5",
    "kraken_p6":     "P6",
    "devourer_p6":   "P6",
    "foresight_p7":  "P7",
    "summoner_p7":   "P7",
}


def fleet_lock_status(lock_dir: Optional[Path] = None) -> dict:
    """
    Check lock status for all known fleet daemons.

    Returns dict mapping daemon_name → {"locked": bool, "pid": int|None, "port": str}
    """
    result = {}
    for name, port in FLEET_DAEMONS.items():
        locked, pid = is_daemon_locked(name, lock_dir)
        result[name] = {"locked": locked, "pid": pid, "port": port}
    return result


# ═══════════════════════════════════════════════════════════════
# § 4  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="HFO Fleet Lock — daemon single-instance enforcement")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="Show lock status for all fleet daemons")
    acq = sub.add_parser("acquire", help="Acquire a lock (for testing)")
    acq.add_argument("name", help="Daemon lock name")
    chk = sub.add_parser("check", help="Check if a specific daemon is locked")
    chk.add_argument("name", help="Daemon lock name")

    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.cmd == "status":
        status = fleet_lock_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(f"\n  Fleet Lock Status ({LOCK_DIR})")
            print("  " + "═" * 50)
            for name, info in sorted(status.items()):
                icon = "🔒" if info["locked"] else "  "
                pid = f"PID {info['pid']}" if info["pid"] else "no PID"
                state = "LOCKED" if info["locked"] else "free"
                print(f"  {icon} {info['port']:<4} {name:<16} {state:<8} {pid}")

    elif args.cmd == "acquire":
        lock = acquire_daemon_lock(args.name)
        if lock:
            print(f"Lock acquired: {args.name} (PID {os.getpid()})")
            print("Press Ctrl+C to release and exit...")
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                release_daemon_lock(args.name)
                print("\nReleased.")
        else:
            sys.exit(1)

    elif args.cmd == "check":
        locked, pid = is_daemon_locked(args.name)
        if args.json:
            print(json.dumps({"locked": locked, "pid": pid}))
        else:
            if locked:
                print(f"  {args.name}: LOCKED (PID {pid})")
            else:
                print(f"  {args.name}: free")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
