#!/usr/bin/env python3
"""
hfo_daemon_fleet.py — HFO Gen89 Daemon Fleet Orchestrator
==========================================================
v2.0 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Powerword: TIME STOP | School: Transmutation

8-Daemon Fleet — one per octree port, BFT consensus overlay.
No window spam. No port sprawl. Exactly 8 daemons, exactly 8 voters.

Fleet Architecture (v2.2 — 1 daemon per port, 7 model families):
  P0-P3: FAST + MEDIUM INTELLIGENCE (optimized for throughput)
  P4-P7: HIGH INTELLIGENCE + DIVERSITY (optimized for depth)
  ┌───────┬────────────────┬─────────────────────────────┬────────────┐
  │ Port  │ Daemon         │ Model (Family)              │ BFT Vote   │
  ├───────┼────────────────┼─────────────────────────────┼────────────┤
  │ P0    │ Watcher        │ Ollama granite4:3b (IBM)    │ HONEST     │
  │ P1    │ Weaver         │ gemini-3-flash (Google☁)    │ HONEST     │
  │ P2    │ Shaper         │ Ollama gemma3:4b (Google)   │ HONEST     │
  │ P3    │ Injector       │ Ollama lfm2.5-thinking:1.2b │ HONEST     │
  │       │                │   (Liquid AI)               │            │
  │ P4    │ Singer         │ Ollama phi4:14b (Microsoft) │ ☠ DISSENT  │
  │ P5    │ Dancer         │ Ollama qwen3:30b-a3b (Ali)  │ HONEST     │
  │ P6    │ Devourer       │ Ollama deepseek-r1:8b (DS)  │ HONEST     │
  │ P6+   │ Kraken (aux)   │ Ollama qwen2.5:3b (Ali)    │ —          │
  │ P7    │ Summoner       │ gemini-3.1-pro (Google☁)    │ HONEST     │
  └───────┴────────────────┴─────────────────────────────┴────────────┘
  Families: IBM Granite, Google Cloud, Google Gemma, Liquid AI, Microsoft Phi, Alibaba Qwen, DeepSeek

BFT Consensus (Doc 184, 8^N convergence):
  • 8 voters (1 per port), P4 Red Regnant ALWAYS dissents
  • Valid quorum band: 5/8 to 7/8
  • Below 5 = no BFT (insufficient agreement)
  • Above 7 = "all green is a lie" (suspicious unanimity)
  • n=8 tolerates f=2 Byzantine faults (3f+1=7<=8)

Window Fix:
  v1 used DETACHED_PROCESS (0x08) → visible console windows
  v2 uses CREATE_NO_WINDOW (0x08000000) → truly invisible

Usage:
  python hfo_daemon_fleet.py --free          Launch free-tier daemons only
  python hfo_daemon_fleet.py --all           Launch everything (free + paid)
  python hfo_daemon_fleet.py --status        Check fleet health
  python hfo_daemon_fleet.py --stop          Stop all daemons
  python hfo_daemon_fleet.py --map           Show fleet architecture
  python hfo_daemon_fleet.py --consensus     Run BFT consensus check
  python hfo_daemon_fleet.py --deep-think    Show Deep Think info

Medallion: bronze
Pointer key: daemon.fleet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Path Resolution ────────────────────────────────────────

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
BRONZE_RES = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources"
FLEET_STATE = HFO_ROOT / ".hfo_fleet_state.json"
SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
PYTHON = sys.executable  # Use same Python interpreter

# ── Load .env ────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    env_path = HFO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
except ImportError:
    pass

VERTEX_AI_ENABLED = bool(os.getenv("HFO_VERTEX_PROJECT", ""))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


# =====================================================================
# Fleet Configuration
# =====================================================================

@dataclass
class DaemonSpec:
    """Specification for a daemon process."""
    name: str                   # Human-readable name
    script: str                 # Python script filename (in bronze/resources)
    port: str                   # Octree port (P0-P7)
    tier: str                   # "free" or "paid"
    provider: str               # "ollama", "gemini_free", "gemini_vertex"
    model: str                  # Model used
    args: list[str] = field(default_factory=list)  # CLI args
    interval_note: str = ""     # Human note about cycle time
    requires_ollama: bool = False
    requires_gemini: bool = False
    requires_vertex: bool = False
    description: str = ""


# The Fleet — exactly 8 daemons, one per octree port (P0-P7)
# BFT: P4 always dissents. Quorum band: 5/8 to 7/8.
FLEET: list[DaemonSpec] = [
    # ── P0 OBSERVE — Lidless Legion (Watcher) ─────────────────
    DaemonSpec(
        name="Watcher",
        script="hfo_octree_daemon.py",
        port="P0",
        tier="free",
        provider="ollama",
        model="granite4:3b (IBM Granite — fast 3B)",
        args=["--ports", "P0", "--interval", "120", "--model-override", "granite4:3b"],
        interval_note="120s tremorsense",
        requires_ollama=True,
        description="P0 Lidless Legion — Octree health sensing + system tremorsense",
    ),

    # ── P1 BRIDGE — Web Weaver (Research) ─────────────────────
    DaemonSpec(
        name="Weaver",
        script="hfo_background_daemon.py",
        port="P1",
        tier="free",
        provider="gemini_free",
        model="gemini-3-flash-preview (Google Flash 3)",
        args=["--tasks", "research", "--research-interval", "300",
              "--model-tier", "frontier_flash"],
        interval_note="5min web research (Gemini 3 Flash)",
        requires_gemini=True,
        description="P1 Web Weaver — Web-grounded research bridging external data to SSOT",
    ),

    # ── P2 SHAPE — Mirror Magus (Deep Analysis + Code) ───────
    DaemonSpec(
        name="Shaper",
        script="hfo_background_daemon.py",
        port="P2",
        tier="free",
        provider="ollama",
        model="gemma3:4b (Google Gemma — fast 4B creation)",
        args=["--tasks", "deep_analysis,codegen", "--deep-analysis-interval", "120",
              "--codegen-interval", "180"],
        interval_note="2-3min fast creation cycles",
        requires_ollama=True,
        description="P2 Mirror Magus — Fast creation + code generation using Gemma 4B",
    ),

    # ── P3 INJECT — Harmonic Hydra (Enrichment + Port Assign) ─
    DaemonSpec(
        name="Injector",
        script="hfo_background_daemon.py",
        port="P3",
        tier="free",
        provider="ollama",
        model="lfm2.5-thinking:1.2b (Liquid AI — ultra-fast 1.2B thinking)",
        args=["--tasks", "enrich,port_assign,patrol",
              "--enrich-interval", "60",
              "--port-assign-interval", "45",
              "--patrol-interval", "30"],
        interval_note="30-60s ultra-fast delivery",
        requires_ollama=True,
        description="P3 Harmonic Hydra — SSOT enrichment, port assignment, stigmergy patrol (Liquid AI)",
    ),

    # ── P4 DISRUPT — Red Regnant (Singer) ☠ ALWAYS DISSENTS ─
    DaemonSpec(
        name="Singer",
        script="hfo_singer_ai_daemon.py",
        port="P4",
        tier="free",
        provider="ollama",
        model="phi4:14b (Microsoft Phi — deep adversarial reasoning)",
        args=["--interval", "120", "--model", "phi4:14b"],
        interval_note="120s deep adversarial (14B needs more time per cycle)",
        requires_ollama=True,
        description="P4 Red Regnant — Strife (antipattern) + Splendor (pattern). BFT: ALWAYS DISSENTS. Phi4 14B for deep reasoning.",
    ),

    # ── P5 IMMUNIZE — Pyre Praetorian (Dancer + Governance) ──
    DaemonSpec(
        name="Dancer",
        script="hfo_p5_dancer_daemon.py",
        port="P5",
        tier="free",
        provider="ollama",
        model="qwen3:30b-a3b (Alibaba Qwen MoE — 30B params, 3B active)",
        args=["--interval", "90", "--model", "qwen3:30b-a3b"],
        interval_note="90s governance + MoE depth (30B knowledge, 3B active speed)",
        requires_ollama=True,
        description="P5 Pyre Praetorian — Death/Dawn + governance patrols. Qwen3 MoE for deep policy knowledge.",
    ),

    # ── P6 ASSIMILATE — Devourer (Deep Reasoning Knowledge Loop) ────────
    # DeepSeek R1 8B brings chain-of-thought reasoning to knowledge extraction.
    # Different family from P4(Microsoft), P5(Alibaba), P7(Google) for max diversity.
    DaemonSpec(
        name="Devourer",
        script="hfo_p6_devourer_daemon.py",
        port="P6",
        tier="free",
        provider="ollama",
        model="deepseek-r1:8b (DeepSeek — reasoning 8B knowledge extraction)",
        args=["--interval", "60", "--batch", "2", "--model", "deepseek-r1:8b"],
        interval_note="60s reasoning-loop, 2 docs/cycle (R1 chain-of-thought overhead)",
        requires_ollama=True,
        description="P6 Devourer — 6D knowledge extraction with DeepSeek R1 reasoning for deeper analysis",
    ),

    # ── P7 NAVIGATE — Spider Sovereign (Summoner) ────────────
    DaemonSpec(
        name="Summoner",
        script="hfo_p7_summoner_daemon.py",
        port="P7",
        tier="paid",
        provider="gemini_vertex",
        model="gemini-3.1-pro-preview (apex, Deep Think)",
        args=["--interval", "1800", "--hours", "24"],
        interval_note="30min strategic nav (Deep Think is expensive — quality > frequency)",
        requires_vertex=True,
        description="P7 Spider Sovereign — Seals & Spheres, Meadows L1-L13, heuristic cartography",
    ),
]

# Auxiliary daemons — launched alongside the primary 8 for extra throughput.
# These don't count toward BFT quorum but support primary port daemons.
AUXILIARY_FLEET: list[DaemonSpec] = [
    # Kraken runs structured enrichment (bluf, port, doctype, lineage) at
    # moderate cadence using a DIFFERENT model family than Devourer (deepseek-r1:8b).
    # This gives P6 cross-family validation: Qwen + DeepSeek see the same docs differently.
    DaemonSpec(
        name="Kraken",
        script="hfo_p6_kraken_daemon.py",
        port="P6",
        tier="free",
        provider="ollama",
        model="qwen2.5:3b (Alibaba Qwen — fast structured enrichment)",
        args=["--tasks", "bluf,port,doctype,lineage",
              "--bluf-interval", "30", "--port-interval", "30",
              "--doctype-interval", "60", "--lineage-interval", "120"],
        interval_note="30-120s structured enrichment (aux, different family from Devourer)",
        requires_ollama=True,
        description="P6 Kraken Keeper (aux) — structured enrichment with Qwen 3B (cross-family with DeepSeek R1 Devourer)",
    ),
]

# Verify fleet invariant: exactly 8 daemons, one per port
assert len(FLEET) == 8, f"Fleet must have exactly 8 daemons, got {len(FLEET)}"
assert len({d.port for d in FLEET}) == 8, "Each port must have exactly one daemon"


# =====================================================================
# Fleet State Management
# =====================================================================

def _load_state() -> dict:
    if FLEET_STATE.exists():
        try:
            return json.loads(FLEET_STATE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"daemons": {}, "last_update": None}


def _save_state(state: dict):
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    FLEET_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _is_running(pid: int) -> bool:
    """Check if a process is still running (Windows + Unix)."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _check_ollama() -> bool:
    """Check if Ollama is reachable."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


# =====================================================================
# Fleet Commands
# =====================================================================

def show_map():
    """Display the 8-daemon fleet architecture map (one per port)."""
    print("=" * 74)
    print("  HFO Gen89 — 8-Daemon Fleet Architecture (v2.0)")
    print("  O·B·S·I·D·I·A·N = 8 ports = 1 octree")
    print("=" * 74)

    # Capability checks
    has_ollama = _check_ollama()
    has_gemini = bool(GEMINI_API_KEY)
    has_vertex = VERTEX_AI_ENABLED

    print(f"\n  Infrastructure:")
    print(f"    Ollama:     {'✓ ONLINE' if has_ollama else '✗ OFFLINE'} ({OLLAMA_BASE})")
    print(f"    Gemini Key: {'✓ SET' if has_gemini else '✗ MISSING'}")
    print(f"    Vertex AI:  {'✓ ENABLED (Ultra $100/mo)' if has_vertex else '✗ DISABLED (free only)'}")

    # Port names from octree
    PORT_NAMES = {
        "P0": "OBSERVE",  "P1": "BRIDGE",  "P2": "SHAPE",   "P3": "INJECT",
        "P4": "DISRUPT",  "P5": "IMMUNIZE", "P6": "ASSIMILATE", "P7": "NAVIGATE",
    }
    COMMANDERS = {
        "P0": "Lidless Legion",   "P1": "Web Weaver",      "P2": "Mirror Magus",
        "P3": "Harmonic Hydra",   "P4": "Red Regnant",     "P5": "Pyre Praetorian",
        "P6": "Kraken Keeper",    "P7": "Spider Sovereign",
    }

    # Fleet state for running/dead status
    state = _load_state()
    daemons_state = state.get("daemons", {})

    print(f"\n  ┌──────┬──────────┬───────────────────────┬──────────┬─────────┬───────────┐")
    print(f"  │ Port │ Word     │ Daemon                │ Model    │ Tier    │ BFT Vote  │")
    print(f"  ├──────┼──────────┼───────────────────────┼──────────┼─────────┼───────────┤")

    for d in FLEET:
        word = PORT_NAMES.get(d.port, "?")
        model_short = d.model.split(" ")[0][:10] if " " in d.model else d.model[:10]
        bft = "☠ DISSENT" if d.port == "P4" else "HONEST"

        # Check running status
        info = daemons_state.get(d.name, {})
        pid = info.get("pid", 0)
        alive = _is_running(pid) if pid else False

        # Check prerequisites met
        can_run = True
        if d.requires_ollama and not has_ollama:
            can_run = False
        if d.requires_gemini and not has_gemini:
            can_run = False
        if d.requires_vertex and not has_vertex:
            can_run = False

        if alive:
            status_ch = "●"  # running
        elif can_run:
            status_ch = "○"  # ready to launch
        else:
            status_ch = "✗"  # missing prereq

        name_display = f"{status_ch} {d.name}"

        print(f"  │ {d.port:4s} │ {word:8s} │ {name_display:21s} │ {model_short:8s} │ {d.tier:7s} │ {bft:9s} │")

    print(f"  └──────┴──────────┴───────────────────────┴──────────┴─────────┴───────────┘")

    print(f"\n  Legend: ● running  ○ ready  ✗ missing prereq")
    print(f"\n  BFT Consensus (Doc 184, 8^N convergence):")
    print(f"    • 8 voters, P4 Red Regnant ALWAYS dissents (adversarial by design)")
    print(f"    • Valid quorum band: 5/8 to 7/8 (5 = BFT minimum, 7 = max trust)")
    print(f"    • Below 5 = insufficient BFT  |  Above 7 = 'all green is a lie'")
    print(f"    • n=8 tolerates f=2 Byzantine faults (3f+1=7≤8)")

    print(f"\n  Free Daily Capacity:")
    print(f"    P0/P4/P5/P6 (Ollama): Unlimited local cycles")
    print(f"    P1 (Flash):   500 RPD → web research")
    print(f"    P3 (3 Flash): 500 RPD → enrichment + port assignment")
    if has_vertex:
        print(f"    P2 (3.1 Pro): ~60 deep analyses/day (~$0.05/doc)")
        print(f"    P7 (3.1 Pro): ~60 strategic scans/day (~$0.05/scan)")
    print()


def show_status():
    """Show status of all fleet daemons."""
    print("=" * 72)
    print("  HFO Gen89 — Daemon Fleet Status")
    print("=" * 72)
    
    state = _load_state()
    daemons = state.get("daemons", {})
    
    if not daemons:
        print("\n  No daemons tracked. Start fleet with: python hfo_daemon_fleet.py --free")
        print()
        return
    
    running = 0
    dead = 0
    
    for name, info in daemons.items():
        pid = info.get("pid", 0)
        alive = _is_running(pid) if pid else False
        status = "RUNNING" if alive else "DEAD"
        marker = "✓" if alive else "✗"
        
        if alive:
            running += 1
        else:
            dead += 1
        
        started = info.get("started", "?")[:19]
        print(f"  {marker} {name:20s}  PID {pid:6d}  {status:7s}  Started: {started}")
    
    print(f"\n  Summary: {running} running, {dead} dead, {running + dead} total")
    if state.get("last_update"):
        print(f"  Last state update: {state['last_update'][:19]}")
    print()


def launch_daemon(spec: DaemonSpec, dry_run: bool = False) -> Optional[int]:
    """Launch a single daemon as a background process. Returns PID."""
    script_path = BRONZE_RES / spec.script
    
    if not script_path.exists():
        print(f"  [WARN] Script not found: {script_path}", file=sys.stderr)
        return None
    
    cmd = [PYTHON, str(script_path)] + spec.args
    
    if dry_run:
        print(f"  [DRY] Would launch: {' '.join(cmd)}")
        return 0
    
    try:
        # Launch as truly invisible background process
        if sys.platform == "win32":
            # Windows: CREATE_NO_WINDOW + CREATE_NEW_PROCESS_GROUP
            # v1 bug: DETACHED_PROCESS (0x08) still shows console windows
            # v2 fix: CREATE_NO_WINDOW (0x08000000) is truly invisible
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                cwd=str(HFO_ROOT),
                creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(HFO_ROOT),
                start_new_session=True,
            )
        
        return proc.pid
    except Exception as e:
        print(f"  [ERROR] Failed to launch {spec.name}: {e}", file=sys.stderr)
        return None


def launch_fleet(tiers: list[str], dry_run: bool = False):
    """Launch daemons for specified tiers.

    SAFETY: Automatically nukes ALL existing daemon processes before launch
    to prevent stacking duplicates. This is fail-safe by design.
    """
    # ── SAFETY: Kill ALL existing daemon processes before launch ──
    # This prevents the #1 source of window/process spam: repeated
    # --all launches stacking duplicate processes that the state file
    # can't track because PIDs from previous sessions are gone.
    if not dry_run:
        print("  Pre-launch cleanup: killing existing daemon processes...")
        killed = nuke_all_daemons(quiet=True)
        if killed:
            print(f"  Cleaned up {killed} existing daemon process(es).")
        else:
            print(f"  No existing daemon processes found.")
        print()
        time.sleep(1)  # Let OS reclaim resources

    has_ollama = _check_ollama()
    has_gemini = bool(GEMINI_API_KEY)
    has_vertex = VERTEX_AI_ENABLED
    
    state = _load_state()
    # Fresh state after nuke
    if not dry_run:
        state["daemons"] = {}
    launched = 0
    skipped = 0
    
    print("=" * 72)
    print("  HFO Gen89 — Daemon Fleet Launch")
    print("=" * 72)
    print(f"  Tiers: {', '.join(tiers)}")
    print(f"  Ollama: {'✓' if has_ollama else '✗'}  Gemini: {'✓' if has_gemini else '✗'}  Vertex: {'✓' if has_vertex else '✗'}")
    print()
    
    all_specs = list(FLEET) + list(AUXILIARY_FLEET)
    for spec in all_specs:
        if spec.tier not in tiers:
            continue
        
        # Check prerequisites
        if spec.requires_ollama and not has_ollama:
            print(f"  [SKIP] {spec.name} — Ollama not available")
            skipped += 1
            continue
        if spec.requires_gemini and not has_gemini:
            print(f"  [SKIP] {spec.name} — GEMINI_API_KEY not set")
            skipped += 1
            continue
        if spec.requires_vertex and not has_vertex:
            print(f"  [SKIP] {spec.name} — Vertex AI not configured (need HFO_VERTEX_PROJECT)")
            skipped += 1
            continue
        
        # NOTE: No need to check "already running" — we nuked everything
        # before launch. This guarantees exactly 1 instance per daemon.
        
        print(f"  Launching {spec.name} ({spec.port}, {spec.provider})...")
        print(f"    Model: {spec.model}")
        print(f"    {spec.description}")
        
        pid = launch_daemon(spec, dry_run=dry_run)
        
        if pid is not None:
            state.setdefault("daemons", {})[spec.name] = {
                "pid": pid,
                "script": spec.script,
                "port": spec.port,
                "tier": spec.tier,
                "model": spec.model,
                "args": spec.args,
                "started": datetime.now(timezone.utc).isoformat(),
            }
            launched += 1
            if not dry_run:
                print(f"    → PID {pid}")
            time.sleep(0.5)  # Stagger launches
    
    _save_state(state)
    
    print(f"\n  Fleet launch complete: {launched} launched, {skipped} skipped")
    
    if launched > 0 and not dry_run:
        print(f"  State saved to: {FLEET_STATE}")
        print(f"  Check status: python hfo_daemon_fleet.py --status")
    print()


# Daemon scripts that the fleet manages — used for orphan detection
_DAEMON_SCRIPTS = {
    "hfo_octree_daemon", "hfo_background_daemon", "hfo_singer_ai_daemon",
    "hfo_p5_dancer_daemon", "hfo_p6_kraken_daemon", "hfo_p7_summoner_daemon",
    "hfo_p6_devourer_daemon", "hfo_p5_daemon",
    "hfo_p5_pyre_praetorian", "hfo_p5_contingency",
    "hfo_strange_loop_scheduler", "hfo_p2_chimera_loop",
}


def nuke_all_daemons(quiet: bool = False) -> int:
    """Kill ALL HFO daemon python processes by command-line pattern.

    Unlike stop_fleet() which only kills tracked PIDs, this scans every
    running Python process and kills anything matching a daemon script name.
    Protects MCP servers and non-HFO python processes.

    Returns number of processes killed.
    """
    if not quiet:
        print("=" * 72)
        print("  HFO Gen89 — NUKE: Killing ALL daemon processes")
        print("=" * 72)

    killed = 0

    if sys.platform == "win32":
        try:
            import ctypes
            # WMI query for all python processes
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name LIKE '%python%'\" | "
                 "Select-Object ProcessId, CommandLine | ConvertTo-Json -Depth 2"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                if not quiet:
                    print(f"  [WARN] PowerShell query failed: {result.stderr[:200]}")
                return 0

            procs = json.loads(result.stdout) if result.stdout.strip() else []
            if isinstance(procs, dict):  # Single result comes as dict, not list
                procs = [procs]

            my_pid = os.getpid()
            for p in procs:
                pid = p.get("ProcessId", 0)
                cmd = p.get("CommandLine", "") or ""
                if pid == my_pid or pid <= 0:
                    continue
                # Protect MCP servers
                if "mcp_server" in cmd or "mcp-server" in cmd:
                    continue
                # Match any known daemon script
                if any(s in cmd for s in _DAEMON_SCRIPTS):
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(pid)],
                            capture_output=True, timeout=5,
                        )
                        if not quiet:
                            # Show just the script name from cmdline
                            script = "unknown"
                            for s in _DAEMON_SCRIPTS:
                                if s in cmd:
                                    script = s
                                    break
                            print(f"  Killed PID {pid:6d}  ({script})")
                        killed += 1
                    except Exception:
                        pass
        except Exception as e:
            if not quiet:
                print(f"  [ERROR] Nuke scan failed: {e}")
    else:
        # Unix: use /proc or ps
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                if "python" not in line.lower():
                    continue
                if "mcp_server" in line or "mcp-server" in line:
                    continue
                if any(s in line for s in _DAEMON_SCRIPTS):
                    parts = line.split()
                    if len(parts) > 1:
                        pid = int(parts[1])
                        if pid != os.getpid():
                            try:
                                os.kill(pid, signal.SIGTERM)
                                killed += 1
                                if not quiet:
                                    print(f"  Killed PID {pid}")
                            except Exception:
                                pass
        except Exception as e:
            if not quiet:
                print(f"  [ERROR] Nuke scan failed: {e}")

    # Clear fleet state
    state = _load_state()
    state["daemons"] = {}
    _save_state(state)

    if not quiet:
        print(f"\n  {killed} daemon processes killed. Fleet state cleared.")
        print()

    return killed


def stop_fleet():
    """Stop all tracked daemons + scan for orphans."""
    state = _load_state()
    daemons = state.get("daemons", {})
    
    if not daemons:
        # Even if no tracked daemons, scan for orphans
        print("  No tracked daemons — scanning for orphans...")
        nuke_all_daemons(quiet=False)
        return
    
    print("=" * 72)
    print("  HFO Gen89 — Stopping Fleet")
    print("=" * 72)
    
    stopped = 0
    for name, info in daemons.items():
        pid = info.get("pid", 0)
        if pid and _is_running(pid):
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, timeout=10)
                else:
                    os.kill(pid, signal.SIGTERM)
                print(f"  Stopped {name} (PID {pid})")
                stopped += 1
            except Exception as e:
                print(f"  [WARN] Could not stop {name} (PID {pid}): {e}")
        else:
            print(f"  {name} already stopped (PID {pid})")
    
    # Clear state
    state["daemons"] = {}
    _save_state(state)
    print(f"\n  {stopped} tracked daemons stopped.")

    # Now scan for orphans that weren't tracked
    print("  Scanning for orphan daemon processes...")
    orphans = nuke_all_daemons(quiet=True)
    if orphans:
        print(f"  Killed {orphans} orphan daemon processes.")
    else:
        print(f"  No orphans found.")
    print()


def run_bft_consensus():
    """Run BFT consensus check across all 8 ports.

    Reads the most recent heartbeat/health event from each port's daemon,
    evaluates quorum band (5/8 to 7/8), P4 always dissents.

    BFT Rules (from Doc 184 + Doc 76):
      • n=8, f=2 → can tolerate 2 Byzantine faults (3f+1=7≤8)
      • P4 Red Regnant structurally ALWAYS dissents (adversarial by design)
      • Valid quorum: 5 to 7 agreeing ports
      • <5 = insufficient BFT, >7 = suspicious unanimity
    """
    print("=" * 74)
    print("  HFO Gen89 — BFT Consensus Check (8^N Convergence)")
    print("=" * 74)

    if not SSOT_DB.exists():
        print(f"\n  [ERROR] SSOT database not found at {SSOT_DB}")
        return

    # Event type patterns for each port's daemon heartbeat
    PORT_EVENT_PATTERNS = {
        "P0": "hfo.gen89.octree%",
        "P1": "hfo.gen89.daemon.research",
        "P2": "hfo.gen89.daemon.deep_analysis",
        "P3": "hfo.gen89.daemon.enrich%",
        "P4": "hfo.gen89.singer%",
        "P5": "hfo.gen89.dancer%",
        "P6": "hfo.gen89.kraken%",
        "P7": "hfo.gen89.summoner%",
    }

    PORT_NAMES = {
        "P0": "OBSERVE",  "P1": "BRIDGE",  "P2": "SHAPE",   "P3": "INJECT",
        "P4": "DISRUPT",  "P5": "IMMUNIZE", "P6": "ASSIMILATE", "P7": "NAVIGATE",
    }

    conn = sqlite3.connect(str(SSOT_DB), timeout=5)
    conn.row_factory = sqlite3.Row

    votes: dict[str, dict[str, Any]] = {}
    now = datetime.now(timezone.utc)
    STALE_MINUTES = 15  # Heartbeat older than this = stale

    for port, pattern in PORT_EVENT_PATTERNS.items():
        try:
            row = conn.execute(
                """SELECT id, event_type, timestamp, subject,
                          json_extract(data_json, '$.status') as status,
                          json_extract(data_json, '$.alerts') as alerts,
                          json_extract(data_json, '$.posture') as posture
                   FROM stigmergy_events
                   WHERE event_type LIKE ?
                   ORDER BY timestamp DESC LIMIT 1""",
                (pattern,)
            ).fetchone()

            if row:
                ts_str = row["timestamp"] or ""
                try:
                    ts = datetime.fromisoformat(ts_str.replace("+00:00", "+00:00"))
                    age_min = (now - ts).total_seconds() / 60.0
                except (ValueError, TypeError):
                    age_min = 999.0

                stale = age_min > STALE_MINUTES
                has_alerts = bool(row["alerts"] and row["alerts"] != "[]")
                posture = row["posture"] or ""

                # Determine health signal
                if stale:
                    health = "STALE"
                elif has_alerts or posture in ("STRESSED", "CRITICAL"):
                    health = "DEGRADED"
                else:
                    health = "HEALTHY"

                votes[port] = {
                    "event_id": row["id"],
                    "event_type": row["event_type"],
                    "age_min": round(age_min, 1),
                    "health": health,
                    "stale": stale,
                    "subject": (row["subject"] or "")[:50],
                }
            else:
                votes[port] = {
                    "event_id": None,
                    "health": "SILENT",
                    "age_min": None,
                    "stale": True,
                    "subject": "No events found",
                }
        except Exception as e:
            votes[port] = {
                "event_id": None,
                "health": "ERROR",
                "age_min": None,
                "stale": True,
                "subject": str(e)[:50],
            }

    conn.close()

    # ── BFT Vote Aggregation ──
    # P4 ALWAYS dissents. All other ports vote honestly based on health.
    honest_healthy = 0
    total_reporting = 0

    print(f"\n  ┌──────┬──────────┬─────────────┬─────────┬──────────────────────────────┐")
    print(f"  │ Port │ Word     │ Health      │ Age     │ Last Signal                  │")
    print(f"  ├──────┼──────────┼─────────────┼─────────┼──────────────────────────────┤")

    for port in ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
        v = votes.get(port, {"health": "UNKNOWN", "age_min": None, "subject": "?"})
        word = PORT_NAMES[port]
        health = v["health"]
        age = f"{v['age_min']}m" if v["age_min"] is not None else "N/A"
        subj = v.get("subject", "")[:30]

        # Vote logic
        if port == "P4":
            vote_icon = "☠"  # Always dissents
        elif health == "HEALTHY":
            vote_icon = "✓"
            honest_healthy += 1
            total_reporting += 1
        elif health == "DEGRADED":
            vote_icon = "△"
            total_reporting += 1
        elif health in ("STALE", "SILENT", "ERROR"):
            vote_icon = "✗"
        else:
            vote_icon = "?"

        print(f"  │ {port:4s} │ {word:8s} │ {vote_icon} {health:10s} │ {age:7s} │ {subj:28s} │")

    print(f"  └──────┴──────────┴─────────────┴─────────┴──────────────────────────────┘")

    # ── Quorum Evaluation ──
    # P4 always dissents, so max possible agreement = 7/8
    # total_reporting = ports with HEALTHY or DEGRADED signals (excluding P4)
    quorum = honest_healthy  # Only HEALTHY ports count for strong quorum
    max_quorum = 7  # P4 always dissents

    print(f"\n  BFT Quorum: {quorum}/{max_quorum} honest-healthy (P4 always dissents)")
    print(f"  Reporting ports: {total_reporting}/7 (+P4 dissent)")

    if quorum >= 7:
        verdict = "⚠ SUSPICIOUS — All 7 honest ports agree. 'All green is a lie.'"
        verdict_code = "SUSPICIOUS_UNANIMITY"
    elif quorum >= 5:
        verdict = f"✓ BFT ACHIEVED — {quorum}/7 honest ports healthy (quorum band 5-7)"
        verdict_code = "BFT_ACHIEVED"
    elif quorum >= 3:
        verdict = f"△ DEGRADED — {quorum}/7 honest. Below BFT minimum (need 5+)."
        verdict_code = "DEGRADED"
    else:
        verdict = f"✗ NO BFT — Only {quorum}/7 honest ports healthy. System unreliable."
        verdict_code = "NO_BFT"

    print(f"\n  Verdict: {verdict}")

    # ── Write consensus event to SSOT ──
    try:
        conn_rw = sqlite3.connect(str(SSOT_DB), timeout=10)
        consensus_data = {
            "quorum": quorum,
            "max_quorum": max_quorum,
            "verdict": verdict_code,
            "votes": {port: v["health"] for port, v in votes.items()},
            "p4_dissent": True,
            "bft_band": "5/8 to 7/8",
            "source_doc": "Doc 184: 8^N BFT Convergence",
        }
        data_str = json.dumps(consensus_data)
        content_hash = hashlib.sha256(data_str.encode()).hexdigest()

        conn_rw.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "hfo.gen89.fleet.bft_consensus",
                now.isoformat(),
                f"BFT:{verdict_code}:quorum_{quorum}_of_{max_quorum}",
                "hfo_daemon_fleet_gen89_v2.0",
                data_str,
                content_hash,
            )
        )
        conn_rw.commit()
        conn_rw.close()
        print(f"  Consensus event written to SSOT.")
    except Exception as e:
        print(f"  [WARN] Could not write consensus event: {e}")

    print()


def show_deep_think_info():
    """Display Deep Think capabilities and usage."""
    print("=" * 72)
    print("  Gemini 3.1 Pro — Deep Think Mode")
    print("=" * 72)
    print("""
  Deep Think is Gemini 3's extended reasoning mode, activated via
  thinking_level="high" in the API. It's NOT a separate model —
  it's a parameter on gemini-3.1-pro-preview (and gemini-3-pro-preview).

  Benchmarks (Gemini 3 Pro Deep Think):
    ══════════════════════════════════════════════════
    HLE (Humanity's Last Exam):     41.0%   (SOTA)
    GPQA-Diamond (PhD science):     93.8%   (SOTA)
    ARC-AGI-2 (general reasoning):  45.1%   (SOTA)
    ══════════════════════════════════════════════════

  Gemini 3.1 Pro (Feb 2026) improves on 3 Pro:
    - Better thinking efficiency (fewer wasted tokens)
    - Improved factual consistency
    - Enhanced agentic workflow execution
    - Custom tools variant (-customtools) for bash+MCP

  API Usage:
    thinking_level="high"     → Deep Think (default for Pro, max reasoning)
    thinking_level="medium"   → Balanced (3.1 Pro only)
    thinking_level="low"      → Fast (minimal reasoning, lower latency)
    thinking_level="minimal"  → Near-zero thinking (3 Flash only)

  ⚠ CANNOT mix thinking_level (3.x) with thinking_budget (2.5) — 400 error

  Pricing: $2/1M input, $12/1M output (includes thinking tokens)
  NO free tier for Pro models. Requires Vertex AI or pay-per-use.

  With Ultra ($100/mo):
    ~60 deep analyses/day ($0.05 avg per doc)
    ~1,800 deep analyses/month
    Each analysis: ~500 input + ~2000 output tokens typical
""")


# =====================================================================
# Main CLI
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="HFO Gen89 Daemon Fleet Orchestrator — launch all daemons",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hfo_daemon_fleet.py --free          Launch free-tier daemons only
  python hfo_daemon_fleet.py --all           Launch everything (free + paid)
  python hfo_daemon_fleet.py --status        Check fleet health
  python hfo_daemon_fleet.py --stop          Stop all daemons
  python hfo_daemon_fleet.py --map           Show 8-daemon architecture
  python hfo_daemon_fleet.py --consensus     Run BFT consensus check
  python hfo_daemon_fleet.py --deep-think    Show Deep Think info
        """
    )
    parser.add_argument("--free", action="store_true",
                        help="Launch free-tier daemons (Ollama + Gemini AI Studio)")
    parser.add_argument("--paid", action="store_true",
                        help="Launch paid-tier daemons (Vertex AI)")
    parser.add_argument("--all", action="store_true",
                        help="Launch all daemons (free + paid)")
    parser.add_argument("--status", action="store_true",
                        help="Show fleet status")
    parser.add_argument("--stop", action="store_true",
                        help="Stop all tracked daemons")
    parser.add_argument("--map", action="store_true",
                        help="Display fleet architecture map")
    parser.add_argument("--consensus", action="store_true",
                        help="Run BFT consensus check across all 8 ports")
    parser.add_argument("--deep-think", action="store_true",
                        help="Show Gemini 3.1 Pro Deep Think info")
    parser.add_argument("--nuke", action="store_true",
                        help="Kill ALL daemon processes (tracked + orphans)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would launch without starting")
    
    args = parser.parse_args()
    
    if args.map:
        show_map()
        return
    
    if args.consensus:
        run_bft_consensus()
        return
    
    if args.deep_think:
        show_deep_think_info()
        return
    
    if args.status:
        show_status()
        return
    
    if args.stop:
        stop_fleet()
        return
    
    if args.nuke:
        nuke_all_daemons()
        return
    
    # Determine which tiers to launch
    tiers = []
    if args.all:
        tiers = ["free", "paid"]
    else:
        if args.free:
            tiers.append("free")
        if args.paid:
            tiers.append("paid")
    
    if not tiers:
        # Default: show map + usage
        show_map()
        print("  To launch: python hfo_daemon_fleet.py --free")
        print("  For everything: python hfo_daemon_fleet.py --all")
        print()
        return
    
    launch_fleet(tiers, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
