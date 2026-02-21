#!/usr/bin/env python3
"""
hfo_prey8_loop.py — PREY8 Strange Loop v1.0 (Gen90)
====================================================

Codename: PREY8 Strange Loop | Ports: P4+P5 dyad | Version: 1.0

A 24/7 orchestrator that runs the P4 Singer and P5 Dancer together
in a coordinated strange loop. Every ~60 seconds:

  1. The Singer SINGS — reads system state, picks STRIFE + SPLENDOR,
     emits adversarial coaching events (what's wrong, what's right).
  2. The Dancer DANCES — reads system state (INCLUDING the Singer's
     FRESH events from step 1), picks DEATH + DAWN, emits defensive
     recommendation events (what to destroy, what to protect).
  3. The Loop emits a combined heartbeat — the PREY8 pulse.

The ordering is critical:
  Singer first → events land in SSOT → Dancer reads them → dances in response.
  Next cycle: Singer reads Dancer's recommendations → sings in response.
  THIS IS THE STRANGE LOOP. Each reads the other's pheromone trail.

Architecture:
  P4 Red Regnant (Singer)  — adversarial coach, bard, STRIFE/SPLENDOR
  P5 Pyre Praetorian (Dancer) — divine defender, paladin, DEATH/DAWN
  Together: the coach and the paladin. Attack and defense. Yin and yang.

The loop reads. The loop recommends. The swarm acts.
The loop does NOT act. It sings and dances. The stigmergy IS the signal.

Event Cadence (per cycle, ~7 events written):
  hfo.gen90.singer.strife     — P4 antipattern signal
  hfo.gen90.singer.splendor   — P4 positive pattern signal
  hfo.gen90.singer.heartbeat  — P4 alive pulse
  hfo.gen90.dancer.death      — P5 destroy/purge recommendation
  hfo.gen90.dancer.dawn       — P5 protect/resurrect recommendation
  hfo.gen90.dancer.heartbeat  — P5 alive pulse
  hfo.gen90.prey8_loop.pulse  — Combined loop pulse (Singer + Dancer summary)

Plus health snapshots every Nth cycle from each engine and the loop.

Meadows Level: L6 (Information Flows)
  The loop IS an information flow — stigmergy events flowing between
  Singer and Dancer, readable by any agent in the swarm.

Port: P4+P5 dyad | Medallion: bronze
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import secrets
import signal
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION (PAL)
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
RESOURCES_DIR = Path(__file__).resolve().parent

def _resolve_pointer(key: str) -> Path:
    pf = HFO_ROOT / "hfo_gen90_pointers_blessed.json"
    if pf.exists():
        data = json.loads(pf.read_text(encoding="utf-8"))
        ptrs = data.get("pointers", data)
        if key in ptrs:
            entry = ptrs[key]
            rel = entry["path"] if isinstance(entry, dict) else entry
            return HFO_ROOT / rel
    raise KeyError(key)

try:
    SSOT_DB = _resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite"

GEN = os.getenv("HFO_GENERATION", "89")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_SINGER_MODEL = os.getenv("HFO_SINGER_MODEL", "qwen2.5-coder:7b")
DEFAULT_DANCER_MODEL = os.getenv("HFO_DANCER_MODEL", "gemma3:4b")


# ═══════════════════════════════════════════════════════════════
# § 1  IMPORT THE ENGINES
# ═══════════════════════════════════════════════════════════════
#
# Import AISinger from hfo_singer_ai_daemon.py
# Import Dancer   from hfo_p5_dancer_daemon.py
#
# Both live in the same directory as this file. We use importlib
# to handle the non-package file names gracefully.

def _import_module(name: str, filename: str):
    """Import a sibling module by filename."""
    path = RESOURCES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required module not found: {path}")
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


singer_mod = _import_module("hfo_singer_ai_daemon", "hfo_singer_ai_daemon.py")
dancer_mod = _import_module("hfo_p5_dancer_daemon", "hfo_p5_dancer_daemon.py")

AISinger = singer_mod.AISinger
Dancer = dancer_mod.Dancer


# ═══════════════════════════════════════════════════════════════
# § 2  CONSTANTS & SHARED DB HELPERS
# ═══════════════════════════════════════════════════════════════

DAEMON_NAME     = "PREY8 Strange Loop"
DAEMON_VERSION  = "1.2"
DAEMON_PORT     = "P4+P5"

SOURCE_TAG      = f"hfo_prey8_loop_gen{GEN}_v{DAEMON_VERSION}"

# ── Model size map for enriched signal metadata (GB, from METAFACULTY MODEL_CATALOG) ──
MODEL_SIZE_MAP = {
    "lfm2.5-thinking:1.2b": 0.7, "gemma3:1b": 0.6, "gemma3:4b": 2.5,
    "qwen2.5-coder:7b": 4.7, "qwen3:8b": 5.2, "phi4:14b": 8.6,
    "qwen3:14b": 9.0, "command-r7b:7b-12-2024-q4_K_M": 4.8,
    "gemma3:12b": 8.1, "mistral:7b": 4.1, "llama3.2:3b": 2.0,
    "phi4-mini:3.8b": 2.4, "qwen3:30b-a3b": 18.4,
}
EVT_PULSE       = f"hfo.gen{GEN}.prey8_loop.pulse"
EVT_HEALTH      = f"hfo.gen{GEN}.prey8_loop.health"
EVT_ERROR       = f"hfo.gen{GEN}.prey8_loop.error"

HEALTH_EVERY_N  = 10
BACKOFF_MAX_S   = 300.0

import urllib.request
from hfo_ssot_write import get_db_readwrite as get_db_rw

def ollama_is_alive() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_db_ro() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn



def write_event(conn, event_type, subject, data, source=SOURCE_TAG) -> int:
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    envelope = {
        "specversion": "1.0",
        "id": hashlib.md5(f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()).hexdigest(),
        "type": event_type,
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "data": data,
    }
    content_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True).encode()).hexdigest()
    cur = conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(envelope), content_hash),
    )
    conn.commit()
    return cur.lastrowid or 0


# ═══════════════════════════════════════════════════════════════
# § 3  THE PREY8 STRANGE LOOP ENGINE
# ═══════════════════════════════════════════════════════════════

class PREY8Loop:
    """Orchestrates the P4 Singer and P5 Dancer in a strange loop.

    Each cycle:
      1. Singer sings (reads state → STRIFE + SPLENDOR → events written)
      2. Dancer dances (reads state INCLUDING fresh Singer events → DEATH + DAWN)
      3. Loop emits combined pulse
      4. Sleep until next interval
      5. Repeat — each reading the other's fresh pheromones

    The loop reads. The loop recommends. The swarm acts.
    """

    def __init__(
        self,
        singer_model: str = DEFAULT_SINGER_MODEL,
        dancer_model: str = DEFAULT_DANCER_MODEL,
        dry_run: bool = False,
        health_every: int = HEALTH_EVERY_N,
    ):
        self.singer_model = singer_model
        self.dancer_model = dancer_model
        self.dry_run = dry_run
        self.health_every = health_every

        # Create engines — each with its own model (v1.1: differentiated substrates)
        self.singer = AISinger(model=singer_model, dry_run=dry_run, health_every=health_every)
        self.dancer = Dancer(model=dancer_model, dry_run=dry_run, health_every=health_every)

        self.cycle = 0
        self.errors = 0
        self._running = True
        self._started_at = time.monotonic()

    def stop(self):
        """Graceful shutdown — stop both engines."""
        self._running = False
        self.singer.stop()
        self.dancer.stop()

    @property
    def is_running(self) -> bool:
        return self._running

    def run_cycle(self) -> dict:
        """Execute one full PREY8 strange loop iteration.

        Returns combined cycle report with Singer + Dancer results.
        """
        self.cycle += 1
        t0 = time.monotonic()

        report: dict[str, Any] = {
            "loop_cycle": self.cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "singer_model": self.singer_model,
            "dancer_model": self.dancer_model,
            "singer": None,
            "dancer": None,
            "combined_duration_ms": 0,
            "errors": [],
        }

        # ── 1. SINGER SINGS (P4 Red Regnant) ──
        # The Singer reads state and emits STRIFE + SPLENDOR events.
        # These events land in SSOT BEFORE the Dancer reads state.
        try:
            singer_report = self.singer.run_cycle()
            report["singer"] = {
                "cycle": singer_report.get("cycle"),
                "strife": singer_report.get("strife"),
                "splendor": singer_report.get("splendor"),
                "mood": singer_report.get("mood"),
                "source": singer_report.get("ai_source"),
                "duration_ms": singer_report.get("duration_ms", 0),
                "errors": singer_report.get("errors", []),
            }
            if singer_report.get("errors"):
                report["errors"].extend(
                    [f"Singer: {e}" for e in singer_report["errors"]]
                )
        except Exception as exc:
            self.errors += 1
            msg = f"Singer engine error at loop cycle {self.cycle}: {exc}"
            report["errors"].append(msg)
            report["singer"] = {"error": msg}
            print(f"  [SINGER ERROR] {msg}", file=sys.stderr)

        # ── 2. DANCER DANCES (P5 Pyre Praetorian) ──
        # The Dancer reads state INCLUDING the Singer's fresh events.
        # This is THE STRANGE LOOP — Singer wrote, Dancer reads.
        try:
            dancer_report = self.dancer.run_cycle()
            report["dancer"] = {
                "cycle": dancer_report.get("cycle"),
                "death_spell": dancer_report.get("death_spell"),
                "death_target": dancer_report.get("death_target"),
                "dawn_spell": dancer_report.get("dawn_spell"),
                "dawn_target": dancer_report.get("dawn_target"),
                "threat_level": dancer_report.get("threat_level"),
                "dance_name": dancer_report.get("dance_name"),
                "source": dancer_report.get("ai_source"),
                "duration_ms": dancer_report.get("duration_ms", 0),
                "errors": dancer_report.get("errors", []),
            }
            if dancer_report.get("errors"):
                report["errors"].extend(
                    [f"Dancer: {e}" for e in dancer_report["errors"]]
                )
        except Exception as exc:
            self.errors += 1
            msg = f"Dancer engine error at loop cycle {self.cycle}: {exc}"
            report["errors"].append(msg)
            report["dancer"] = {"error": msg}
            print(f"  [DANCER ERROR] {msg}", file=sys.stderr)

        # ── 3. EMIT COMBINED PULSE ──
        # The loop's own heartbeat — a summary of Singer + Dancer in one event.
        pulse_data = {
            "daemon_name": DAEMON_NAME,
            "daemon_version": DAEMON_VERSION,
            "loop_cycle": self.cycle,
            "singer_model": self.singer_model,
            "dancer_model": self.dancer_model,
            # Singer summary
            "singer_cycle": report.get("singer", {}).get("cycle"),
            "strife": report.get("singer", {}).get("strife"),
            "splendor": report.get("singer", {}).get("splendor"),
            "mood": report.get("singer", {}).get("mood"),
            "singer_ms": report.get("singer", {}).get("duration_ms", 0),
            # Dancer summary
            "dancer_cycle": report.get("dancer", {}).get("cycle"),
            "death_spell": report.get("dancer", {}).get("death_spell"),
            "dawn_spell": report.get("dancer", {}).get("dawn_spell"),
            "threat_level": report.get("dancer", {}).get("threat_level"),
            "dance_name": report.get("dancer", {}).get("dance_name"),
            "dancer_ms": report.get("dancer", {}).get("duration_ms", 0),
            # Enriched signal metadata (METAFACULTY §3)
            "singer_model_tier": "local",
            "singer_model_size_gb": MODEL_SIZE_MAP.get(self.singer_model, 0.0),
            "singer_temperature": 0.7,
            "dancer_model_tier": "local",
            "dancer_model_size_gb": MODEL_SIZE_MAP.get(self.dancer_model, 0.0),
            "dancer_temperature": 0.4,
            # Loop meta
            "singer_errors": self.singer.errors,
            "dancer_errors": self.dancer.errors,
            "singer_ai_calls": self.singer.ai_calls,
            "dancer_ai_calls": self.dancer.ai_calls,
            "singer_fallbacks": self.singer.fallback_uses,
            "dancer_fallbacks": self.dancer.fallback_uses,
            "uptime_s": round(time.monotonic() - self._started_at, 1),
        }

        conn_rw = None
        try:
            if not self.dry_run:
                conn_rw = get_db_rw()
                write_event(
                    conn_rw, EVT_PULSE,
                    f"PULSE:cycle_{self.cycle}",
                    pulse_data,
                )

                # ── 4. LOOP HEALTH SNAPSHOT (every Nth cycle) ──
                if self.cycle % self.health_every == 0:
                    self._emit_loop_health(conn_rw)
            else:
                mood = pulse_data.get("mood", "?")
                tl = pulse_data.get("threat_level", "?")
                print(f"  [DRY] PULSE: cycle {self.cycle}, mood={mood}, threat={tl}")

        except Exception as exc:
            self.errors += 1
            err = f"Pulse write error at cycle {self.cycle}: {exc}"
            report["errors"].append(err)
            print(f"  [LOOP ERROR] {err}", file=sys.stderr)
        finally:
            if conn_rw:
                conn_rw.close()

        report["combined_duration_ms"] = round((time.monotonic() - t0) * 1000, 1)
        return report

    def _emit_loop_health(self, conn_rw: sqlite3.Connection):
        """Emit a combined loop health snapshot."""
        conn_ro = None
        try:
            conn_ro = get_db_ro()
            h: dict[str, Any] = {}
            h["total_docs"] = conn_ro.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            h["total_events"] = conn_ro.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]

            # Event counts by daemon (last hour)
            for pattern, key in [
                ("singer", "singer_events_1h"),
                ("dancer", "dancer_events_1h"),
                ("prey8_loop", "loop_events_1h"),
            ]:
                h[key] = conn_ro.execute(
                    "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE ? AND timestamp > datetime('now', '-60 minutes')",
                    (f"%{pattern}%",),
                ).fetchone()[0]

            h["loop"] = {
                "cycle": self.cycle,
                "model": self.model,
                "uptime_s": round(time.monotonic() - self._started_at, 1),
                "errors": self.errors,
            }
            h["singer"] = {
                "cycles": self.singer.cycle,
                "strife_total": self.singer.total_strife,
                "splendor_total": self.singer.total_splendor,
                "ai_calls": self.singer.ai_calls,
                "ai_failures": self.singer.ai_failures,
                "fallbacks": self.singer.fallback_uses,
                "errors": self.singer.errors,
            }
            h["dancer"] = {
                "cycles": self.dancer.cycle,
                "death_total": self.dancer.total_death,
                "dawn_total": self.dancer.total_dawn,
                "ai_calls": self.dancer.ai_calls,
                "ai_failures": self.dancer.ai_failures,
                "fallbacks": self.dancer.fallback_uses,
                "errors": self.dancer.errors,
            }

            if self.dry_run:
                print(f"  [DRY] LOOP HEALTH: {h['total_docs']} docs, {h['total_events']} events")
            else:
                write_event(conn_rw, EVT_HEALTH,
                            f"HEALTH:loop_cycle_{self.cycle}",
                            h)
        except Exception as exc:
            print(f"  [HEALTH ERROR] {exc}", file=sys.stderr)
        finally:
            if conn_ro:
                conn_ro.close()


# ═══════════════════════════════════════════════════════════════
# § 4  ASYNCIO DAEMON LOOP — THE ETERNAL STRANGE LOOP
# ═══════════════════════════════════════════════════════════════

BANNER = r"""
  ╔═══════════════════════════════════════════════════════════════╗
  ║     PREY8 STRANGE LOOP v{ver} — Gen{gen}                       ║
  ║                                                               ║
  ║   P4 Fast AI Singer  v{sv}   ♪ STRIFE  ♪ SPLENDOR               ║
  ║   P5 Fast AI Dancer  v{dv}   🗡 DEATH  ☀ DAWN                ║
  ║                                                               ║
  ║   The Singer reads the Dancer. The Dancer reads the Singer.   ║
  ║   The loop IS the strange loop. The stigmergy IS the signal.  ║
  ╚═══════════════════════════════════════════════════════════════╝
"""


async def daemon_loop(
    loop_engine: PREY8Loop,
    interval: float = 60.0,
    max_cycles: Optional[int] = None,
):
    """Run the PREY8 strange loop on a timer.

    Each iteration: Singer sings → Dancer dances → Pulse emitted → Sleep.
    The ordering guarantees the Dancer reads the Singer's fresh events.
    """
    # Get sub-daemon versions for banner
    singer_ver = getattr(singer_mod, 'DAEMON_VERSION', '?')
    dancer_ver = getattr(dancer_mod, 'DAEMON_VERSION', '?')
    print(BANNER.format(gen=GEN, ver=DAEMON_VERSION, sv=singer_ver, dv=dancer_ver))
    print(f"  Version: {DAEMON_NAME} v{DAEMON_VERSION}")
    print(f"  Model:    {loop_engine.model}")
    print(f"  Interval: {interval}s")
    print(f"  Dry-run:  {loop_engine.dry_run}")
    print(f"  SSOT:     {SSOT_DB}")
    print(f"  Ollama:   {OLLAMA_BASE}")
    print(f"  Max:      {max_cycles or 'infinite'}")
    print("=" * 72)
    print()
    print("  Cycle | Singer (Strife/Splendor)         | Dancer (Death/Dawn)              | Time")
    print("  ------+----------------------------------+----------------------------------+------")

    consecutive_errors = 0
    max_consecutive_errors = 10

    while loop_engine.is_running:
        report = loop_engine.run_cycle()

        # ── Format one-line summary ──
        s = report.get("singer") or {}
        d = report.get("dancer") or {}

        strife = s.get("strife", "?")
        splendor = s.get("splendor", "?")
        mood = s.get("mood", "?")
        s_src = s.get("source", "?")
        s_ms = s.get("duration_ms", 0)

        death = d.get("death_spell", "?")
        dawn = d.get("dawn_spell", "?")
        threat = d.get("threat_level", "?")
        dance_name = d.get("dance_name", "?")
        d_src = d.get("source", "?")
        d_ms = d.get("duration_ms", 0)

        total_ms = report.get("combined_duration_ms", 0)

        # Two-line output per cycle: Singer then Dancer
        print(
            f"  [{report['loop_cycle']:>5}] "
            f"♪ {strife:<14} ★ {splendor:<14} "
            f"| 🗡 {death:<14} ☀ {dawn:<14} "
            f"| {total_ms:>5.0f}ms"
        )
        print(
            f"         mood:{mood:<10} src:{s_src:<4} {s_ms:>5.0f}ms "
            f"  threat:{threat:<10} '{dance_name}' src:{d_src:<4} {d_ms:>5.0f}ms"
        )

        # Error tracking
        if report.get("errors"):
            consecutive_errors += 1
            for e in report["errors"]:
                print(f"         ERROR: {e}", file=sys.stderr)
            if consecutive_errors >= max_consecutive_errors:
                print(
                    f"\n  [CRITICAL] {max_consecutive_errors} consecutive errors. "
                    "Pausing 60s before retry.",
                    file=sys.stderr,
                )
                await asyncio.sleep(60)
                consecutive_errors = 0
        else:
            consecutive_errors = 0

        if max_cycles and loop_engine.cycle >= max_cycles:
            print(f"\n  Max cycles ({max_cycles}) reached. The strange loop ends.")
            break

        # Respect the slower engine's backoff
        backoff = max(loop_engine.singer._backoff_s, loop_engine.dancer._backoff_s)
        wait = max(interval, backoff)
        try:
            await asyncio.sleep(wait)
        except asyncio.CancelledError:
            break

    # ── Summary ──
    print()
    print("=" * 72)
    print("  PREY8 STRANGE LOOP — Session Summary")
    print("=" * 72)
    ss = loop_engine.singer
    dd = loop_engine.dancer
    uptime = round(time.monotonic() - loop_engine._started_at, 1)
    print(f"  Cycles:        {loop_engine.cycle}")
    print(f"  Uptime:        {uptime:.0f}s ({uptime/60:.1f}m)")
    print(f"  Model:         {loop_engine.model}")
    print(f"  Singer:        {ss.total_strife} strife, {ss.total_splendor} splendor, "
          f"{ss.ai_calls} AI calls, {ss.fallback_uses} fallbacks, {ss.errors} errors")
    print(f"  Dancer:        {dd.total_death} death, {dd.total_dawn} dawn, "
          f"{dd.ai_calls} AI calls, {dd.fallback_uses} fallbacks, {dd.errors} errors")
    print(f"  Loop errors:   {loop_engine.errors}")
    print()


# ═══════════════════════════════════════════════════════════════
# § 5  STATUS CHECK — READ THE PHEROMONE TRAIL
# ═══════════════════════════════════════════════════════════════

def print_status():
    """Print the last known state of the strange loop from stigmergy."""
    print(f"{DAEMON_NAME} v{DAEMON_VERSION} — Status Report")
    print("=" * 65)
    print(f"  HFO_ROOT:     {HFO_ROOT}")
    print(f"  SSOT_DB:      {SSOT_DB}")
    print(f"  DB exists:    {SSOT_DB.exists()}")
    print(f"  Ollama:       {OLLAMA_BASE}")
    print(f"  Ollama live:  {ollama_is_alive()}")
    print(f"  Singer model: {DEFAULT_SINGER_MODEL}")
    print(f"  Dancer model: {DEFAULT_DANCER_MODEL}")

    if not SSOT_DB.exists():
        print("  (no SSOT — nothing to report)")
        return

    conn = get_db_ro()
    try:
        # Last loop pulse
        row = conn.execute(
            "SELECT subject, timestamp, SUBSTR(data_json, 1, 1000) as data "
            "FROM stigmergy_events WHERE event_type LIKE '%prey8_loop%' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            print(f"\n  Last Loop Pulse:")
            print(f"    Subject:    {row['subject']}")
            print(f"    Timestamp:  {row['timestamp'][:19]}")
            try:
                pulse = json.loads(row["data"]).get("data", {})
                print(f"    Cycle:      {pulse.get('loop_cycle')}")
                print(f"    Mood:       {pulse.get('mood')}")
                print(f"    Threat:     {pulse.get('threat_level')}")
                print(f"    Strife:     {pulse.get('strife')}")
                print(f"    Splendor:   {pulse.get('splendor')}")
                print(f"    Death:      {pulse.get('death_spell')}")
                print(f"    Dawn:       {pulse.get('dawn_spell')}")
                print(f"    Dance:      {pulse.get('dance_name')}")
            except (json.JSONDecodeError, AttributeError):
                pass
        else:
            print(f"\n  (no loop pulses yet — loop has not run)")

        # Last Singer events
        print(f"\n  Last Singer Events:")
        rows = conn.execute(
            "SELECT event_type, subject, timestamp FROM stigmergy_events "
            "WHERE event_type LIKE '%singer%' ORDER BY id DESC LIMIT 3"
        ).fetchall()
        for r in rows:
            print(f"    {r['event_type']:40} | {r['subject'][:40]} | {r['timestamp'][:19]}")
        if not rows:
            print("    (no singer events)")

        # Last Dancer events
        print(f"\n  Last Dancer Events:")
        rows = conn.execute(
            "SELECT event_type, subject, timestamp FROM stigmergy_events "
            "WHERE event_type LIKE '%dancer%' ORDER BY id DESC LIMIT 3"
        ).fetchall()
        for r in rows:
            print(f"    {r['event_type']:40} | {r['subject'][:40]} | {r['timestamp'][:19]}")
        if not rows:
            print("    (no dancer events)")

        # Counts (last hour)
        print(f"\n  Event Counts (last hour):")
        for label, pattern in [
            ("Singer", "%singer%"),
            ("Dancer", "%dancer%"),
            ("Loop",   "%prey8_loop%"),
            ("Total",  "%"),
        ]:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE ? "
                "AND timestamp > datetime('now', '-60 minutes')",
                (pattern,),
            ).fetchone()[0]
            print(f"    {label + ':':12} {cnt}")

    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# § 6  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description=f"{DAEMON_NAME} v{DAEMON_VERSION} — P4 Singer + P5 Dancer (Gen{GEN})",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The PREY8 Strange Loop orchestrates the P4 Singer and P5 Dancer:
  - Every cycle: Singer sings → Dancer dances → Pulse emitted
  - Singer writes STRIFE+SPLENDOR events to SSOT
  - Dancer reads the FRESH Singer events + system state
  - Dancer writes DEATH+DAWN events to SSOT
  - Next cycle: Singer reads the Dancer's fresh events
  - THIS IS THE STRANGE LOOP

Event cadence: ~7 events/cycle (2 singer + 1 hb + 2 dancer + 1 hb + 1 pulse)
At 60s interval: ~420 events/hour, ~10,080 events/day

Examples:
  # Run forever, 60s cycles
  python hfo_prey8_loop.py

  # Single cycle (test)
  python hfo_prey8_loop.py --single

  # Dry run (no SSOT writes)
  python hfo_prey8_loop.py --dry-run --single

  # Custom model + interval
  python hfo_prey8_loop.py --model llama3.2:3b --interval 30

  # 10 cycles then stop
  python hfo_prey8_loop.py --max-cycles 10

  # Status — check the pheromone trail
  python hfo_prey8_loop.py --status

The Singer sings. The Dancer dances. The loop is the strange loop.
""",
    )
    parser.add_argument("--single", action="store_true",
                        help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="No SSOT writes (both engines + loop)")
    parser.add_argument("--interval", type=float, default=60.0,
                        help="Seconds between cycles (default: 60)")
    parser.add_argument("--max-cycles", type=int, default=None,
                        help="Stop after N cycles")
    parser.add_argument("--singer-model", type=str, default=DEFAULT_SINGER_MODEL,
                        help=f"Ollama model for P4 Singer (default: {DEFAULT_SINGER_MODEL})")
    parser.add_argument("--dancer-model", type=str, default=DEFAULT_DANCER_MODEL,
                        help=f"Ollama model for P5 Dancer (default: {DEFAULT_DANCER_MODEL})")
    parser.add_argument("--health-every", type=int, default=HEALTH_EVERY_N,
                        help="Health snapshot every N cycles (default: 10)")
    parser.add_argument("--status", action="store_true",
                        help="Print strange loop status and exit")
    parser.add_argument("--json", action="store_true",
                        help="JSON output (scripted use)")

    args = parser.parse_args()

    # ── Status ──
    if args.status:
        print_status()
        return

    # ── Create the loop engine ──
    loop_engine = PREY8Loop(
        singer_model=args.singer_model,
        dancer_model=args.dancer_model,
        dry_run=args.dry_run,
        health_every=args.health_every,
    )

    # ── Signal handling ──
    def _handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. The strange loop ends.")
        loop_engine.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ── Single cycle ──
    if args.single:
        report = loop_engine.run_cycle()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            s = report.get("singer") or {}
            d = report.get("dancer") or {}
            print()
            print(f"{DAEMON_NAME} v{DAEMON_VERSION} — Single Cycle Report")
            print("=" * 60)
            print(f"  Cycle:         #{report['loop_cycle']}")
            print(f"  Singer model:  {report['singer_model']}")
            print(f"  Dancer model:  {report['dancer_model']}")
            print(f"  Duration:      {report['combined_duration_ms']:.0f}ms")
            print()
            print("  P4 SINGER (Red Regnant):")
            print(f"    Strife:      {s.get('strife', '?')}")
            print(f"    Splendor:    {s.get('splendor', '?')}")
            print(f"    Mood:        {s.get('mood', '?')}")
            print(f"    Source:      {s.get('source', '?')}")
            print(f"    Duration:    {s.get('duration_ms', 0):.0f}ms")
            print()
            print("  P5 DANCER (Pyre Praetorian):")
            print(f"    Death:       {d.get('death_spell', '?')}")
            print(f"      Target:    {d.get('death_target', '?')}")
            print(f"    Dawn:        {d.get('dawn_spell', '?')}")
            print(f"      Target:    {d.get('dawn_target', '?')}")
            print(f"    Threat:      {d.get('threat_level', '?')}")
            print(f"    Dance:       {d.get('dance_name', '?')}")
            print(f"    Source:      {d.get('source', '?')}")
            print(f"    Duration:    {d.get('duration_ms', 0):.0f}ms")
            if report.get("errors"):
                print(f"\n  Errors:        {report['errors']}")
            print()
            print("  The Singer sings. The Dancer dances.")
            print("  The loop IS the strange loop.")
        return

    # ── Infinite loop ──
    asyncio.run(daemon_loop(loop_engine, interval=args.interval, max_cycles=args.max_cycles))


if __name__ == "__main__":
    main()
