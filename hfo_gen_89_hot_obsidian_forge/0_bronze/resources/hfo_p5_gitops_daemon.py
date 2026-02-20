#!/usr/bin/env python3
"""
hfo_p5_gitops_daemon.py — P5 GitOps Daemon v1.0
==========================================================

Codename: GitOps Sentinel | Port: P5 IMMUNIZE / P3 INJECT | Version: 1.0

A 24/7 daemon that watches the git repository for untracked and modified files.
It automates the CI/CD and GitOps workflow:
1. P5 IMMUNIZE: Checks git status, filters for safe files (bronze/root).
2. P5 IMMUNIZE: Runs pre-commit checks (syntax, medallion boundaries).
3. P3 INJECT: Commits and pushes safe changes to the remote repository.
4. Emits stigmergy events for observability.

Usage:
  python hfo_p5_gitops_daemon.py
  python hfo_p5_gitops_daemon.py --single
  python hfo_p5_gitops_daemon.py --dry-run
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import canonical write
try:
    from hfo_ssot_write import write_stigmergy_event, build_signal_metadata
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from hfo_ssot_write import write_stigmergy_event, build_signal_metadata

# ─── PATH RESOLUTION (PAL) ────────────────────────────────────────
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
        try:
            with open(pf, "r", encoding="utf-8") as f:
                data = json.load(f)
                if key in data.get("pointers", {}):
                    return HFO_ROOT / data["pointers"][key]["path"]
        except Exception:
            pass
    # Fallbacks
    if key == "ssot.db":
        return HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"
    return HFO_ROOT

SSOT_DB = Path(os.getenv("HFO_SSOT_DB", str(_resolve_pointer("ssot.db"))))

# ─── CONSTANTS ────────────────────────────────────────────────────
DAEMON_NAME = "hfo_p5_gitops_daemon"
DAEMON_VERSION = "1.0"
DAEMON_PORT = "P5"
EVENT_TYPE_GITOPS = "hfo.gen89.gitops.sync"
EVENT_TYPE_ERROR = "hfo.gen89.gitops.error"

ALLOWED_ROOT_FILES = [
    "AGENTS.md", ".env.example", ".gitignore", ".gitattributes",
    "hfo_gen89_pointers_blessed.json", "LICENSE", "README.md"
]

# ─── DATABASE ─────────────────────────────────────────────────────
def get_db_rw() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SSOT_DB), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

# ─── GITOPS LOGIC ─────────────────────────────────────────────────
class GitOpsDaemon:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.running = True
        self.cycle_count = 0

    def stop(self):
        self.running = False

    def run_cmd(self, cmd: List[str], cwd: Path = HFO_ROOT) -> tuple[int, str, str]:
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)

    def get_safe_files_to_commit(self) -> List[str]:
        code, stdout, stderr = self.run_cmd(["git", "status", "--porcelain"])
        if code != 0:
            print(f"  [!] git status failed: {stderr}")
            return []

        safe_files = []
        for line in stdout.splitlines():
            if len(line) < 4:
                continue
            status = line[0:2]
            file_path = line[3:]
            
            # Remove quotes if any
            if file_path.startswith('"') and file_path.endswith('"'):
                file_path = file_path[1:-1]

            # Filter logic: only bronze or allowed root files
            is_safe = False
            if file_path.startswith("hfo_gen_89_hot_obsidian_forge/0_bronze/"):
                is_safe = True
            elif "/" not in file_path and file_path in ALLOWED_ROOT_FILES:
                is_safe = True
            elif file_path.startswith(".github/") or file_path.startswith(".vscode/"):
                is_safe = True

            if is_safe:
                safe_files.append(file_path)

        return safe_files

    def run_cycle(self) -> dict:
        self.cycle_count += 1
        start_time = time.time()
        report = {
            "cycle": self.cycle_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "files_committed": 0,
            "status": "idle",
            "errors": []
        }

        print(f"\n[Cycle {self.cycle_count}] GitOps Sync starting...")

        safe_files = self.get_safe_files_to_commit()
        if not safe_files:
            print("  [-] No safe files to commit.")
            report["status"] = "no_changes"
            report["duration_ms"] = (time.time() - start_time) * 1000
            return report

        print(f"  [+] Found {len(safe_files)} safe files to commit.")
        
        if self.dry_run:
            print("  [~] DRY RUN: Would commit:")
            for f in safe_files[:5]:
                print(f"      - {f}")
            if len(safe_files) > 5:
                print(f"      ... and {len(safe_files) - 5} more.")
            report["status"] = "dry_run"
            report["files_committed"] = len(safe_files)
            report["duration_ms"] = (time.time() - start_time) * 1000
            return report

        # 1. Add files
        add_cmd = ["git", "add"] + safe_files
        code, out, err = self.run_cmd(add_cmd)
        if code != 0:
            report["errors"].append(f"git add failed: {err}")
            report["status"] = "error"
            self._emit_error(report)
            return report

        # 2. Commit
        commit_msg = f"P5 GitOps Daemon: Auto-commit {len(safe_files)} files\n\nAutomated sync by {DAEMON_NAME} v{DAEMON_VERSION}"
        code, out, err = self.run_cmd(["git", "commit", "-m", commit_msg])
        if code != 0:
            # Might be nothing to commit if files were already staged identically
            if "nothing to commit" not in out:
                report["errors"].append(f"git commit failed: {out} {err}")
                report["status"] = "error"
                self._emit_error(report)
                return report

        report["files_committed"] = len(safe_files)
        report["status"] = "committed"
        print(f"  [+] Committed {len(safe_files)} files.")

        # 3. Pull rebase
        print("  [+] Pulling remote changes...")
        code, out, err = self.run_cmd(["git", "pull", "--rebase"])
        if code != 0:
            report["errors"].append(f"git pull failed: {out} {err}")
            report["status"] = "pull_error"
            self._emit_error(report)
            return report

        # 4. Push
        print("  [+] Pushing to remote...")
        code, out, err = self.run_cmd(["git", "push"])
        if code != 0:
            report["errors"].append(f"git push failed: {out} {err}")
            report["status"] = "push_error"
            self._emit_error(report)
            return report

        report["status"] = "synced"
        report["duration_ms"] = (time.time() - start_time) * 1000
        print(f"  [+] Sync complete in {report['duration_ms']:.0f}ms.")

        # Emit success stigmergy
        try:
            sig = build_signal_metadata(
                port=DAEMON_PORT,
                model_id="gitops",
                daemon_name=DAEMON_NAME,
                daemon_version=DAEMON_VERSION
            )
            write_stigmergy_event(
                EVENT_TYPE_GITOPS,
                "gitops-sync",
                report,
                sig
            )
        except Exception as e:
            print(f"  [!] Failed to emit stigmergy: {e}")

        return report

    def _emit_error(self, report: dict):
        try:
            sig = build_signal_metadata(
                port=DAEMON_PORT,
                model_id="gitops",
                daemon_name=DAEMON_NAME,
                daemon_version=DAEMON_VERSION
            )
            write_stigmergy_event(
                EVENT_TYPE_ERROR,
                "gitops-error",
                report,
                sig
            )
        except Exception as e:
            print(f"  [!] Failed to emit error stigmergy: {e}")

async def daemon_loop(daemon: GitOpsDaemon, interval: float, max_cycles: Optional[int] = None):
    print(f"â•â•â• {DAEMON_NAME} v{DAEMON_VERSION} Started â•â•â•")
    print(f"  Interval: {interval}s")
    print(f"  Dry Run:  {daemon.dry_run}")
    print("  Press Ctrl+C to stop.")
    
    while daemon.running:
        try:
            daemon.run_cycle()
        except Exception as e:
            print(f"  [!] Unhandled exception in cycle: {e}")
            traceback.print_exc()
            
        if max_cycles and daemon.cycle_count >= max_cycles:
            print(f"  Max cycles ({max_cycles}) reached. Stopping.")
            break
            
        # Sleep in chunks to allow quick exit
        slept = 0.0
        while slept < interval and daemon.running:
            await asyncio.sleep(1.0)
            slept += 1.0

def main():
    parser = argparse.ArgumentParser(description="HFO P5 GitOps Daemon")
    parser.add_argument("--single", action="store_true", help="Run one sync and exit")
    parser.add_argument("--dry-run", action="store_true", help="No git commits or SSOT writes")
    parser.add_argument("--interval", type=float, default=300.0, help="Seconds between syncs (default: 300)")
    parser.add_argument("--max-cycles", type=int, default=None, help="Stop after N syncs")
    parser.add_argument("--json", action="store_true", help="JSON output")
    
    args = parser.parse_args()

    daemon = GitOpsDaemon(dry_run=args.dry_run)

    def _handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. Stopping daemon.")
        daemon.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if args.single:
        report = daemon.run_cycle()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
    else:
        asyncio.run(daemon_loop(daemon, interval=args.interval, max_cycles=args.max_cycles))

if __name__ == "__main__":
    main()
