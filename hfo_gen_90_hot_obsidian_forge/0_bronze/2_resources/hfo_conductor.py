#!/usr/bin/env python3
"""
hfo_conductor.py — Hive Fleet Obsidian Orchestrator
====================================================
v1.1 | Port: P7 NAVIGATE | Commander: Spider Sovereign
Medallion: bronze

PURPOSE
-------
Single long-running process that cycles all 8 ports through a work queue
with dynamic concurrency scaled by live resource headroom.

NPU / GPU PRIORITY POLICY
--------------------------
The orchestrator is designed to PRESERVE CPU for operator work (Stryker
mutation testing, builds, interactive tasks).  All LLM inference is routed
NPU-first → GPU/Ollama → Gemini API → OpenRouter API.  The CPU target is
set LOW (default 60%) so the orchestrator backs off as soon as CPU climbs,
leaving at least 40 % for the operator.  VRAM and GPU can be used freely
up to their own targets (80 %).

The orchestrator owns a ThreadPool whose size dynamically scales as a
power-of-2 ladder based on live resource pressure:

    1 thread  →  2 threads  →  4 threads  →  8 threads
       ↑______________________________________________|
              (scale-down on pressure, scale-up on headroom)

All LLM inference goes through hfo_llm_router.py using strategy=npu_first:
  NPU (openvino_genai) → Ollama/GPU → Gemini API → OpenRouter API.

CONCURRENCY LADDER
------------------
- Start at concurrency = START_CONCURRENCY  (default 1)
- Every SCALE_INTERVAL_S seconds:
    - Read resource snapshot from hfo_resource_governor
    - CPU check is PRIMARY — scale down as soon as CPU > cpu_target (60%)
    - VRAM/RAM checks are SECONDARY — allow GPU to stay loaded (up to 80%)
    - If CPU headroom ≥ 15pp AND VRAM/RAM OK: scale up
    - On scale-down: evict idle Ollama models immediately
- Emit hfo.gen90.orchestrator.scale event to stigmergy on every change

QUEUE BEHAVIOUR
---------------
- Port queue:  P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P0 → ...
- Each "job" = run one advisory tick for that port
- With concurrency=1, this is pure round-robin sequential
- With concurrency=N, up to N ports tick simultaneously
- The queue refills automatically (circular) — no daemon ever starves

ENV / CONFIG (all override-able via .env or environment)
--------------------------------------------------------
HFO_CONDUCTOR_CONCURRENCY     = 1     # starting concurrency (1/2/4/8)
HFO_CONDUCTOR_MAX_CONCURRENCY = 8     # hard ceiling
HFO_CONDUCTOR_SCALE_INTERVAL  = 60    # seconds between scale decisions
HFO_CONDUCTOR_SCALE_UP_HEADROOM = 15  # pp headroom required to scale up
HFO_CONDUCTOR_PORT_INTERVAL   = 30    # min seconds between same-port ticks
HFO_VRAM_TARGET_PCT  = 80             # GPU can stay loaded up to this
HFO_RAM_TARGET_PCT   = 80
HFO_CPU_TARGET_PCT   = 60             # LOW — reserves ~40% CPU for operator

Usage
-----
    # Sequential mode (1 at a time, NPU-first inference)
    python hfo_conductor.py --sequential

    # Start at concurrency-2 with ceiling of 4
    python hfo_conductor.py --concurrency 2 --max-concurrency 4

    # Custom CPU reserve (keep 50% free)
    python hfo_conductor.py --cpu-target 50

    # Status snapshot and exit
    python hfo_conductor.py --status

    # Kill the running orchestrator
    python hfo_conductor.py --stop
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import queue
import signal
import sqlite3
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from hfo_ssot_write import get_db_readwrite

# ── dotenv ────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv as _ldenv
    for _p in [Path.cwd()] + list(Path.cwd().parents):
        _ep = _p / ".env"
        if _ep.exists() and (_p / "AGENTS.md").exists():
            _ldenv(_ep, override=False)
            break
except ImportError:
    pass

# ── Path resolution ───────────────────────────────────────────────────────────
def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT   = _find_root()
_RES_DIR   = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources"
DB_PATH    = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
_PID_FILE  = HFO_ROOT / ".hfo_orchestrator.pid"
_STAT_FILE = HFO_ROOT / ".hfo_orchestrator_status.json"

if str(_RES_DIR) not in sys.path:
    sys.path.insert(0, str(_RES_DIR))

# ── Optional modules (fail-soft) ─────────────────────────────────────────────
try:
    from hfo_llm_router import LLMRouter, RouterConfig
    _ROUTER_OK = True
except ImportError:
    LLMRouter = None  # type: ignore
    RouterConfig = None  # type: ignore
    _ROUTER_OK = False

try:
    from hfo_resource_governor import (
        GovernorConfig, ResourceGovernor, get_resource_snapshot,
        evict_idle_ollama_models,
    )
    _GOV_OK = True
except ImportError:
    _GOV_OK = False

try:
    from hfo_octree_daemon import PORT_CONFIGS, build_daemon_persona, _write_stigmergy  # type: ignore
    _DAEMON_OK = True
except ImportError:
    _DAEMON_OK = False

# ── Config ────────────────────────────────────────────────────────────────────
PORT_ORDER: list[str] = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]


@dataclass
class OrchestratorConfig:
    start_concurrency: int   = 1
    max_concurrency: int     = 8
    scale_interval_s: float  = 10.0       # tight preemptive loop — 10s
    scale_up_headroom_pct: float = 15.0   # pp below target before scaling up
    port_interval_s: float   = 30.0       # min gap between same-port ticks
    vram_target_pct: float   = 80.0       # GPU can stay loaded up to here
    ram_target_pct: float    = 80.0
    cpu_target_pct: float    = 60.0       # LOW: reserves ~40% CPU for operator
    max_tokens: int          = 200
    db_path: Optional[Path]  = None
    # GPU warm-up — keep a small model resident so first inference hits GPU not CPU
    gpu_warm_model: str      = "lfm2.5-thinking:1.2b"   # smallest confirmed-working
    gpu_warm_interval_s: float = 120.0    # keep-alive ping frequency

    @classmethod
    def from_env(cls) -> "OrchestratorConfig":
        return cls(
            start_concurrency  = int(os.getenv("HFO_CONDUCTOR_CONCURRENCY",    "1")),
            max_concurrency    = int(os.getenv("HFO_CONDUCTOR_MAX_CONCURRENCY","8")),
            scale_interval_s   = float(os.getenv("HFO_CONDUCTOR_SCALE_INTERVAL","10")),  # 10s preemptive
            scale_up_headroom_pct = float(os.getenv("HFO_CONDUCTOR_SCALE_UP_HEADROOM","15")),
            port_interval_s    = float(os.getenv("HFO_CONDUCTOR_PORT_INTERVAL","30")),
            vram_target_pct    = float(os.getenv("HFO_VRAM_TARGET_PCT",  "80")),
            ram_target_pct     = float(os.getenv("HFO_RAM_TARGET_PCT",   "80")),
            # Default CPU target 60 — preserves ~40% CPU for Stryker / operator work
            cpu_target_pct     = float(os.getenv("HFO_CPU_TARGET_PCT",   "60")),
            max_tokens         = int(os.getenv("HFO_CONDUCTOR_MAX_TOKENS","200")),
            db_path            = DB_PATH if DB_PATH.exists() else None,
            gpu_warm_model     = os.getenv("HFO_CONDUCTOR_GPU_WARM_MODEL", "lfm2.5-thinking:1.2b"),
            gpu_warm_interval_s = float(os.getenv("HFO_CONDUCTOR_GPU_WARM_INTERVAL", "120")),
        )

    @property
    def valid_concurrency_levels(self) -> list[int]:
        """Power-of-2 ladder from 1 up to max_concurrency."""
        lvls, n = [], 1
        while n <= self.max_concurrency:
            lvls.append(n)
            n *= 2
        return lvls

    def next_up(self, current: int) -> int:
        lvls = self.valid_concurrency_levels
        idx = lvls.index(current) if current in lvls else 0
        return lvls[min(idx + 1, len(lvls) - 1)]

    def next_down(self, current: int) -> int:
        lvls = self.valid_concurrency_levels
        idx = lvls.index(current) if current in lvls else 0
        return lvls[max(idx - 1, 0)]


# ── Stigmergy writer ──────────────────────────────────────────────────────────
def _stigmergy(event_type: str, data: dict, db_path: Optional[Path] = None) -> None:
    path = db_path or DB_PATH
    if not path or not path.exists():
        return
    import hashlib, secrets as _sec
    ts  = datetime.now(timezone.utc).isoformat()
    evt = {"specversion":"1.0","id":_sec.token_hex(8),"type":event_type,
           "source":"orchestrator","subject":"orchestrator","time":ts,
           "timestamp":ts,"datacontenttype":"application/json","data":data}
    raw = json.dumps(evt, sort_keys=True, default=str)
    ch  = hashlib.sha256(raw.encode()).hexdigest()
    try:
        con = sqlite3.connect(str(path), timeout=30, isolation_level=None)
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("""
            INSERT OR IGNORE INTO stigmergy_events
                (event_type, timestamp, subject, source, data_json, content_hash)
            VALUES (?,?,?,?,?,?)""",
            (event_type, ts, "orchestrator", "orchestrator", raw, ch))
        con.commit(); con.close()
    except Exception:
        pass


# ── Resource sampler ─────────────────────────────────────────────────────────
def _sample_resources() -> dict:
    """Return a lightweight resource dict without importing heavy deps."""
    snap: dict = {
        "vram_pct": 0.0, "ram_pct": 0.0, "cpu_pct": 0.0,
        "npu_active": False, "ok": False,
    }
    if _GOV_OK:
        try:
            raw = get_resource_snapshot()
            if hasattr(raw, "vram_pct_of_budget"):
                snap["vram_pct"] = raw.vram_pct_of_budget
                snap["ram_pct"]  = raw.ram_used_pct
                snap["cpu_pct"]  = raw.cpu_pct
                snap["npu_active"] = raw.npu_active if hasattr(raw, "npu_active") else False
            elif isinstance(raw, dict):
                snap["vram_pct"] = float(raw.get("vram_pct", 0))
                snap["ram_pct"]  = float(raw.get("ram_pct",  0))
                snap["cpu_pct"]  = float(raw.get("cpu_pct",  0))
                snap["npu_active"] = bool(raw.get("npu_active", False))
            snap["ok"] = True
        except Exception:
            pass
    else:
        # Fallback: psutil only
        try:
            import psutil
            snap["cpu_pct"] = psutil.cpu_percent(interval=0.2)
            snap["ram_pct"] = psutil.virtual_memory().percent
            snap["ok"] = True
        except Exception:
            pass
    return snap


# ── Scale decision ────────────────────────────────────────────────────────────
def _scale_decision(snap: dict, current: int, cfg: OrchestratorConfig) -> tuple[int, str]:
    """
    Return (new_concurrency, reason).

    CPU is the PRIMARY gate — the orchestrator is designed to leave CPU
    headroom for the operator (Stryker mutations, builds, etc.).  LLM work
    is pushed to NPU/GPU instead.

    Scale-down triggers (immediate, in priority order):
      1. CPU > cpu_target_pct  (default 60%) — primary, operator-protecting
      2. RAM > ram_target_pct  (default 80%) — secondary
      3. VRAM > vram_target_pct (default 80%) — secondary

    Scale-up requires ALL of:
      - CPU headroom ≥ scale_up_headroom_pct (default 15pp)
      - RAM and VRAM OK (not over their targets)
    """
    vram_headroom = cfg.vram_target_pct - snap.get("vram_pct", 0)
    ram_headroom  = cfg.ram_target_pct  - snap.get("ram_pct",  0)
    cpu_headroom  = cfg.cpu_target_pct  - snap.get("cpu_pct",  0)   # PRIMARY

    # CPU is checked first — it has the lowest target intentionally
    if cpu_headroom < 0:
        return cfg.next_down(current), (
            f"SCALE_DOWN(CPU): {snap.get('cpu_pct',0):.0f}% > target {cfg.cpu_target_pct:.0f}%"
            " — pushing inference to NPU/GPU, freeing CPU for operator"
        )
    if ram_headroom < 0:
        return cfg.next_down(current), f"SCALE_DOWN(RAM): {snap.get('ram_pct',0):.0f}%>{cfg.ram_target_pct:.0f}%"
    if vram_headroom < 0:
        return cfg.next_down(current), f"SCALE_DOWN(VRAM): {snap.get('vram_pct',0):.0f}%>{cfg.vram_target_pct:.0f}%"

    h = cfg.scale_up_headroom_pct
    # CPU headroom is the binding constraint for scale-up
    if cpu_headroom >= h and ram_headroom >= 0 and vram_headroom >= 0:
        new = cfg.next_up(current)
        if new != current:
            return new, (
                f"SCALE_UP: CPU+{cpu_headroom:.0f}pp VRAM+{vram_headroom:.0f}pp RAM+{ram_headroom:.0f}pp"
            )
    return current, "HOLD"


# ── Port tick ─────────────────────────────────────────────────────────────────
def _run_port_tick(port_id: str, cfg: OrchestratorConfig, stats: dict) -> dict:
    """
    Execute one advisory tick for `port_id`.
    Returns a result dict with timing, provider, tokens, and any error.

    PRE-TICK CPU GATE (structural, not reactive):
    Checks CPU *before* starting any inference.  If CPU is already above
    cfg.cpu_target_pct, the tick is aborted immediately with SKIP_CPU_GATE.
    This is the hard enforcement — it fires in the tick thread, not the
    60s scaler.  The scaler changes concurrency; this gate prevents a single
    in-flight tick from burning CPU when the operator is already under load.
    """
    t0 = time.monotonic()
    result = {"port": port_id, "ok": False, "provider": "?", "tokens": 0,
              "error": None, "duration_ms": 0.0}

    # ── PRE-TICK CPU GATE ────────────────────────────────────────────────────
    try:
        import psutil as _psu
        live_cpu = _psu.cpu_percent(interval=0.1)
        if live_cpu > cfg.cpu_target_pct:
            result["error"] = f"SKIP_CPU_GATE: {live_cpu:.0f}% > {cfg.cpu_target_pct:.0f}%"
            result["provider"] = "skipped"
            print(
                f"  [{port_id}] SKIP  CPU={live_cpu:.0f}%>{cfg.cpu_target_pct:.0f}%  "
                f"(gate protecting operator headroom)"
            )
            return result
    except Exception:
        pass  # if psutil fails, proceed anyway — don't block on monitoring failure
    # ─────────────────────────────────────────────────────────────────────────

    try:
        # Build prompt and persona from daemon config
        persona = system = ""
        if _DAEMON_OK and port_id in PORT_CONFIGS:
            pcfg   = PORT_CONFIGS[port_id]
            persona = build_daemon_persona(pcfg)
            role   = pcfg.role
        else:
            role = "advisory"
            pcfg = None

        # Minimal context from recent stigmergy (avoid heavy DB reads in tight loop)
        context = "(no recent context)"
        try:
            if DB_PATH.exists():
                con = sqlite3.connect(str(DB_PATH), timeout=30)
                rows = con.execute(
                    "SELECT event_type, timestamp, data_json FROM stigmergy_events "
                    "ORDER BY id DESC LIMIT 3"
                ).fetchall()
                con.close()
                if rows:
                    context = "\n".join(
                        f"[{r[0]}] {r[1]}: {(json.loads(r[2] or '{}').get('data') or {})}"
                        for r in rows
                    )
        except Exception:
            pass

        if pcfg:
            prompt = (
                f"Recent stigmergy:\n{context}\n\n"
                f"As {pcfg.commander} ({pcfg.port_id} {pcfg.powerword}), "
                f"provide a brief advisory (≤{cfg.max_tokens} words):\n"
                f"1. What do you observe?\n"
                f"2. Any threats or opportunities?\n"
                f"3. One recommendation for the operator.\n"
                f"Sign as [{pcfg.port_id}:{pcfg.commander}]."
            )
        else:
            prompt = (
                f"Recent stigmergy:\n{context}\n\n"
                f"As {port_id} daemon, provide a brief advisory."
            )

        # ── Router inference (NPU-first → GPU/Ollama → Gemini → OpenRouter) ──
        advice   = f"[{port_id}] NO_INFERENCE — router unavailable"
        provider = "none"
        tokens   = 0
        if _ROUTER_OK and LLMRouter is not None:
            r_cfg  = RouterConfig.from_env(db_path=cfg.db_path)
            # Enforce npu_first: keeps CPU free for operator work
            if hasattr(r_cfg, 'strategy'):
                r_cfg.strategy = 'npu_first'
            router = LLMRouter(r_cfg)
            res    = router.generate(
                prompt,
                role=role,
                system=persona,
                max_tokens=cfg.max_tokens,
            )
            advice   = res["response"]
            provider = res.get("provider", "?")
            tokens   = res.get("tokens", 0)
        else:
            # Raw Ollama fallback (no router) — force GPU layers to keep inference off CPU
            import urllib.request, json as _json
            model = (pcfg.model if pcfg else "qwen2.5:3b")
            # num_gpu_layers=-1 means "all layers on GPU" — prevents CPU thread inference
            body  = _json.dumps({
                "model": model,
                "prompt": prompt,
                "system": persona,
                "stream": False,
                "options": {"num_gpu": -1},   # force all layers to GPU
            }).encode()
            req   = urllib.request.Request(
                f"{os.getenv('OLLAMA_HOST','http://127.0.0.1:11434')}/api/generate",
                data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    d    = _json.loads(r.read())
                    advice   = d.get("response", "")
                    tokens   = d.get("eval_count", 0)
                    provider = "ollama_direct"
            except Exception as e:
                advice = f"[{port_id}] Ollama error: {e}"

        result.update(ok=True, provider=provider, tokens=tokens,
                      duration_ms=round((time.monotonic() - t0) * 1000, 1))

        # Write advisory stigmergy
        _stigmergy("hfo.gen90.orchestrator.advisory", {
            "port": port_id,
            "commander": (pcfg.commander if pcfg else port_id),
            "provider": provider,
            "tokens": tokens,
            "duration_ms": result["duration_ms"],
            "advisory": advice[:800],
            "concurrency": stats.get("concurrency", 1),
        }, db_path=cfg.db_path)

        # Update stats
        stats.setdefault("ticks", {})[port_id] = stats["ticks"].get(port_id, 0) + 1
        stats.setdefault("tokens_total", 0)
        stats["tokens_total"] = stats.get("tokens_total", 0) + tokens

        label = "NPU" if provider == "npu" else provider.upper()
        print(
            f"  [{port_id}] {label:12s}  {tokens:4d}tok  "
            f"{result['duration_ms']:6.0f}ms  "
            f"(concurrency={stats.get('concurrency',1)})"
        )

    except Exception as e:
        result["error"] = str(e)[:300]
        print(f"  [{port_id}] ERROR: {result['error']}", file=sys.stderr)
        _stigmergy("hfo.gen90.orchestrator.error",
                   {"port": port_id, "error": result["error"]},
                   db_path=cfg.db_path)

    result["duration_ms"] = round((time.monotonic() - t0) * 1000, 1)
    return result


# ── Orchestrator ──────────────────────────────────────────────────────────────
class Orchestrator:
    """
    Hive Fleet Obsidian Orchestrator — single-process, adaptive-concurrency
    port scheduler that keeps CPU free for the operator.

    - Internal circular deque of (port_id, last_tick_time)
    - ThreadPoolExecutor with dynamic max_workers (power-of-2 ladder)
    - Background scaler thread: CPU is primary gate (target 60%)
    - All inference routed NPU-first → GPU → API (never burns CPU)
    """

    def __init__(self, cfg: OrchestratorConfig) -> None:
        self.cfg            = cfg
        self._stop          = threading.Event()
        self._concurrency   = cfg.start_concurrency  # current live value
        self._lock          = threading.Lock()

        # Circular port queue — deque of (port_id, last_tick_ts)
        self._port_queue: collections.deque = collections.deque(
            [(p, 0.0) for p in PORT_ORDER]
        )
        self._in_flight: set[str] = set()    # ports currently being ticked

        # Shared stats (written by tick workers, read by scaler/status)
        self._stats: dict = {
            "concurrency":    cfg.start_concurrency,
            "scale_events":   [],
            "ticks":          {p: 0 for p in PORT_ORDER},
            "tokens_total":   0,
            "started_at":     datetime.now(timezone.utc).isoformat(),
            "resource_snap":  {},
        }

        # Governor
        self._gov: Optional[ResourceGovernor] = None
        if _GOV_OK:
            try:
                self._gov = ResourceGovernor(GovernorConfig.from_env())
            except Exception:
                pass

        # Executor — will be replaced on scale events
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures:  list[Future] = []

    # ── Public API ─────────────────────────────────────────────────────────

    def run(self) -> None:
        """Block until stopped (Ctrl-C or --stop)."""
        _PID_FILE.write_text(str(os.getpid()))
        cpu_reserve = 100 - self.cfg.cpu_target_pct
        print(f"\n{'═'*70}")
        print(f"  HIVE FLEET OBSIDIAN ORCHESTRATOR v1.2  (preemptive)")
        print(f"  Inference priority : NPU → GPU/Ollama → Gemini → OpenRouter")
        print(f"  CPU reserve        : {cpu_reserve:.0f}%  (for Stryker / operator work)")
        print(f"  Start concurrency  : {self.cfg.start_concurrency} "
              f"(max {self.cfg.max_concurrency})")
        print(f"  Scale ladder       : {self.cfg.valid_concurrency_levels}")
        print(f"  Scale interval     : {self.cfg.scale_interval_s}s  [PREEMPTIVE LOOP]")
        print(f"  GPU warm model     : {self.cfg.gpu_warm_model or 'disabled'}  "
              f"(keep-alive every {self.cfg.gpu_warm_interval_s:.0f}s)")
        print(f"  Resource targets   : "
              f"CPU {self.cfg.cpu_target_pct:.0f}% (PRIMARY)  "
              f"RAM {self.cfg.ram_target_pct:.0f}%  "
              f"VRAM {self.cfg.vram_target_pct:.0f}%")
        print(f"  Port order         : {' → '.join(PORT_ORDER)}")
        print(f"{'═'*70}\n")

        _stigmergy("hfo.gen90.orchestrator.start", {
            "name":              "Hive Fleet Obsidian Orchestrator",
            "version":           "1.2",
            "preemptive":        True,
            "start_concurrency": self.cfg.start_concurrency,
            "max_concurrency":   self.cfg.max_concurrency,
            "cpu_target_pct":    self.cfg.cpu_target_pct,
            "cpu_reserve_pct":   100 - self.cfg.cpu_target_pct,
            "inference_priority": "npu_first",
            "gpu_warm_model":    self.cfg.gpu_warm_model,
            "gpu_warm_interval_s": self.cfg.gpu_warm_interval_s,
            "scale_interval_s":  self.cfg.scale_interval_s,
            "ports":             PORT_ORDER,
            "scale_ladder":      self.cfg.valid_concurrency_levels,
        }, db_path=self.cfg.db_path)

        # Start background threads
        self._start_executor(self._concurrency)
        scaler_t = threading.Thread(target=self._scaler_loop, daemon=True,
                                    name="orchestrator-scaler")
        scaler_t.start()
        warmup_t = threading.Thread(target=self._gpu_warmup_loop, daemon=True,
                                    name="orchestrator-gpu-warmup")
        warmup_t.start()

        # Main scheduling loop
        try:
            self._schedule_loop()
        except KeyboardInterrupt:
            print("\n  [ORCHESTRATOR] KeyboardInterrupt — stopping.")
        finally:
            self._stop.set()
            self._shutdown_executor()
            self._write_status()
            _stigmergy("hfo.gen90.orchestrator.stop",
                       {"stats": self._stats}, db_path=self.cfg.db_path)
            try:
                _PID_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            print("\n  [ORCHESTRATOR] Stopped.")

    # ── Scheduling mechanics ───────────────────────────────────────────────

    def _schedule_loop(self) -> None:
        """
        Round-robin dispatcher.  Continuously picks the next eligible port
        from the queue and submits it to the executor — up to `_concurrency`
        slots at a time.  Eligible = not currently in flight AND waited
        ≥ port_interval_s since its last tick.
        """
        while not self._stop.is_set():
            self._reap_done_futures()

            with self._lock:
                slots_free = self._concurrency - len(self._in_flight)

            if slots_free <= 0:
                time.sleep(0.5)
                continue

            submitted = 0
            now = time.monotonic()
            queue_len = len(self._port_queue)

            for _ in range(queue_len):
                if submitted >= slots_free:
                    break
                if self._stop.is_set():
                    break

                with self._lock:
                    if not self._port_queue:
                        break
                    port_id, last_t = self._port_queue.popleft()

                wait_needed = self.cfg.port_interval_s - (now - last_t)
                if port_id in self._in_flight or wait_needed > 0:
                    # Not ready — put back at end
                    with self._lock:
                        self._port_queue.append((port_id, last_t))
                    continue

                # Submit
                with self._lock:
                    self._in_flight.add(port_id)
                    self._stats["concurrency"] = self._concurrency

                fut = self._executor.submit(
                    self._tick_wrapper, port_id
                )
                self._futures.append(fut)
                submitted += 1

            if submitted == 0:
                time.sleep(1.0)

    def _tick_wrapper(self, port_id: str) -> dict:
        """Wraps _run_port_tick; updates queue and in-flight on completion."""
        try:
            result = _run_port_tick(port_id, self.cfg, self._stats)
        except Exception as e:
            result = {"port": port_id, "ok": False, "error": str(e)}
        finally:
            now = time.monotonic()
            with self._lock:
                self._in_flight.discard(port_id)
                # Re-enqueue at end with updated timestamp
                self._port_queue.append((port_id, now))
        return result

    def _reap_done_futures(self) -> None:
        pending = []
        for f in self._futures:
            if not f.done():
                pending.append(f)
        self._futures = pending

    # ── Executor management ────────────────────────────────────────────────

    def _start_executor(self, workers: int) -> None:
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        self._executor = ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="orchestrator-worker",
        )

    def _shutdown_executor(self) -> None:
        if self._executor:
            try:
                self._executor.shutdown(wait=True, cancel_futures=False)
            except Exception:
                pass

    # ── GPU warm-up ────────────────────────────────────────────────────────

    def _warm_gpu_if_cold(self) -> None:
        """
        Proactively keep a small model resident in GPU VRAM.

        Fires when VRAM is near-zero AND CPU has headroom.  Sends an Ollama
        keepalive ping that loads the warm model with keep_alive=10m so
        subsequent inference hits GPU immediately instead of cold-starting
        on CPU.

        This is the PREEMPTIVE fix: it runs in a dedicated background loop
        (every gpu_warm_interval_s), independent of the scale cycle.
        """
        if not self.cfg.gpu_warm_model:
            return
        snap = _sample_resources()
        vram_cold = snap.get("vram_pct", 0.0) < 5.0
        cpu_ok    = snap.get("cpu_pct",  0.0) < self.cfg.cpu_target_pct
        if not (vram_cold and cpu_ok):
            return  # GPU already warm or CPU too busy — skip

        model       = self.cfg.gpu_warm_model
        ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        body        = json.dumps({
            "model":      model,
            "prompt":     "",        # empty prompt = load-only ping
            "stream":     False,
            "keep_alive": "10m",     # keep model resident for 10 minutes
            "options":    {"num_gpu": -1},  # all layers on GPU
        }).encode()
        try:
            import urllib.request as _ur
            req = _ur.Request(
                f"{ollama_host}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with _ur.urlopen(req, timeout=90) as resp:
                resp.read()
            print(
                f"  [ORCHESTRATOR] GPU_WARM: {model} loaded "
                f"(VRAM was {snap.get('vram_pct',0):.1f}%, CPU {snap.get('cpu_pct',0):.0f}%)"
            )
            _stigmergy("hfo.gen90.orchestrator.gpu_warm", {
                "model":          model,
                "vram_pct_before": snap.get("vram_pct", 0),
                "cpu_pct":        snap.get("cpu_pct", 0),
                "action":         "warm_success",
            }, db_path=self.cfg.db_path)
        except Exception as e:
            print(f"  [ORCHESTRATOR] GPU_WARM failed ({model}): {e}", file=sys.stderr)

    def _gpu_warmup_loop(self) -> None:
        """
        Background thread: keep GPU primed.

        Runs every gpu_warm_interval_s.  Initial fire after 3 s so the
        orchestrator prints its banner before the first Ollama ping.
        This thread is what makes the orchestrator PREEMPTIVE — it does not
        wait for a CPU spike before deciding to use GPU.
        """
        time.sleep(3)  # let startup banner print first
        self._warm_gpu_if_cold()
        while not self._stop.is_set():
            self._stop.wait(timeout=self.cfg.gpu_warm_interval_s)
            if self._stop.is_set():
                break
            try:
                self._warm_gpu_if_cold()
            except Exception as e:
                print(f"  [ORCHESTRATOR GPU_WARMUP] {e}", file=sys.stderr)

    # ── Scaler loop ────────────────────────────────────────────────────────

    def _scaler_loop(self) -> None:
        """Background thread: every scale_interval_s, read resources and scale."""
        while not self._stop.is_set():
            time.sleep(self.cfg.scale_interval_s)
            if self._stop.is_set():
                break
            try:
                self._maybe_scale()
            except Exception as e:
                print(f"  [ORCHESTRATOR SCALER] {e}", file=sys.stderr)

    def _maybe_scale(self) -> None:
        snap = _sample_resources()
        self._stats["resource_snap"] = snap

        with self._lock:
            current = self._concurrency

        new, reason = _scale_decision(snap, current, self.cfg)

        if new != current:
            # On scale-down, evict models to free VRAM immediately
            if new < current:
                if _GOV_OK:
                    try:
                        evict_idle_ollama_models(verbose=False)
                    except Exception:
                        pass
                print(
                    f"\n  [ORCHESTRATOR SCALER] {reason}  "
                    f"→ {current}→{new} workers\n"
                )
            else:
                # Scale-up: preemptively warm GPU so next tick hits VRAM not CPU
                print(
                    f"\n  [ORCHESTRATOR SCALER] {reason}  "
                    f"→ {current}→{new} workers\n"
                )
                try:
                    self._warm_gpu_if_cold()
                except Exception:
                    pass

            with self._lock:
                self._concurrency = new
                self._stats["concurrency"] = new

            # Resize the thread pool
            # We don't stop in-flight jobs — just change the ceiling for
            # new submissions by recreating the executor.  Workers already
            # running will finish naturally.
            self._start_executor(new)

            event = {
                "old_concurrency": current,
                "new_concurrency": new,
                "reason": reason,
                "vram_pct": snap.get("vram_pct"),
                "ram_pct":  snap.get("ram_pct"),
                "cpu_pct":  snap.get("cpu_pct"),
            }
            self._stats["scale_events"].append(event)
            if len(self._stats["scale_events"]) > 50:
                self._stats["scale_events"] = self._stats["scale_events"][-50:]

            _stigmergy("hfo.gen90.orchestrator.scale", event,
                       db_path=self.cfg.db_path)

        self._write_status()

    # ── Status file ────────────────────────────────────────────────────────

    def _write_status(self) -> None:
        with self._lock:
            snap = {
                "pid":             os.getpid(),
                "concurrency":     self._concurrency,
                "max_concurrency": self.cfg.max_concurrency,
                "scale_ladder":    self.cfg.valid_concurrency_levels,
                "in_flight":       list(self._in_flight),
                "ticks":           dict(self._stats.get("ticks", {})),
                "tokens_total":    self._stats.get("tokens_total", 0),
                "resource_snap":   self._stats.get("resource_snap", {}),
                "scale_events":    self._stats.get("scale_events", [])[-5:],
                "started_at":      self._stats.get("started_at"),
                "updated_at":      datetime.now(timezone.utc).isoformat(),
            }
        try:
            _STAT_FILE.write_text(json.dumps(snap, indent=2, default=str))
        except Exception:
            pass


# ── CLI helpers ───────────────────────────────────────────────────────────────
def _status_cmd() -> None:
    if not _STAT_FILE.exists():
        print("  No orchestrator running (no status file).")
        return
    try:
        s = json.loads(_STAT_FILE.read_text())
    except Exception:
        print("  Status file unreadable.")
        return
    pid = s.get("pid", "?")
    import psutil as _ps
    try:
        alive = _ps.pid_exists(int(pid))
    except Exception:
        alive = False
    status = "RUNNING" if alive else "DEAD (stale status file)"
    print(f"\n  HIVE FLEET OBSIDIAN ORCHESTRATOR STATUS — {status}")
    print(f"  PID            : {pid}")
    print(f"  Concurrency    : {s.get('concurrency','?')} / {s.get('max_concurrency','?')}")
    print(f"  Scale ladder   : {s.get('scale_ladder','?')}")
    print(f"  Ports in-flight: {s.get('in_flight','?')}")
    print(f"  Started        : {s.get('started_at','?')}")
    print(f"  Updated        : {s.get('updated_at','?')}")
    print(f"  Tokens total   : {s.get('tokens_total',0):,}")
    print(f"\n  Tick counts:")
    for p, n in sorted((s.get("ticks") or {}).items()):
        print(f"    {p}: {n}")
    snap = s.get("resource_snap") or {}
    if snap:
        print(f"\n  Last resource snap:")
        print(f"    VRAM {snap.get('vram_pct',0):.1f}%  "
              f"RAM {snap.get('ram_pct',0):.1f}%  "
              f"CPU {snap.get('cpu_pct',0):.1f}%  "
              f"NPU {'●' if snap.get('npu_active') else '○'}")
    evts = s.get("scale_events") or []
    if evts:
        print(f"\n  Recent scale events:")
        for e in evts[-3:]:
            print(f"    {e.get('old_concurrency')}→{e.get('new_concurrency')}  {e.get('reason','')}")
    print()


def _stop_cmd() -> None:
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            import psutil as _ps
            p = _ps.Process(pid)
            p.terminate()
            p.wait(timeout=10)
            print(f"  Orchestrator PID {pid} terminated.")
        except Exception as e:
            print(f"  Stop failed: {e}")
        finally:
            _PID_FILE.unlink(missing_ok=True)
    else:
        print("  No orchestrator PID file found.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hive Fleet Obsidian Orchestrator — NPU/GPU-first adaptive port scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python hfo_conductor.py --sequential             # 1 port at a time, NPU-first
  python hfo_conductor.py --concurrency 2          # start at 2, auto-scales
  python hfo_conductor.py --concurrency 1 --max-concurrency 4  # ladder: 1→2→4
  python hfo_conductor.py --cpu-target 50          # keep 50%% CPU free for operator
  python hfo_conductor.py --status                 # show live status
  python hfo_conductor.py --stop                   # kill running orchestrator
        """,
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="Start at concurrency=1 (sequential mode). Same as --concurrency 1.",
    )
    parser.add_argument(
        "--concurrency", type=int, default=None,
        help="Starting concurrency (1/2/4/8). Default: HFO_CONDUCTOR_CONCURRENCY or 1.",
    )
    parser.add_argument(
        "--max-concurrency", type=int, default=None,
        help="Hard concurrency ceiling (1/2/4/8). Default: HFO_CONDUCTOR_MAX_CONCURRENCY or 8.",
    )
    parser.add_argument(
        "--scale-interval", type=float, default=None,
        help="Seconds between scale decisions. Default: 60.",
    )
    parser.add_argument(
        "--port-interval", type=float, default=None,
        help="Min seconds between same-port ticks. Default: 30.",
    )
    parser.add_argument(
        "--vram-target", type=float, default=None,
        help="VRAM target pct (evict + scale-down above this). Default: 80.",
    )
    parser.add_argument(
        "--ram-target", type=float, default=None,
        help="RAM target pct. Default: 80.",
    )
    parser.add_argument(
        "--cpu-target", type=float, default=None,
        help="CPU target pct. Default: 60 (reserves 40%% for operator). Lower = more CPU free.",
    )
    parser.add_argument(
        "--no-scale", action="store_true",
        help="Disable auto-scaling — hold at start concurrency forever.",
    )
    parser.add_argument("--status", action="store_true", help="Print status and exit.")
    parser.add_argument("--stop",   action="store_true", help="Kill running conductor.")
    args = parser.parse_args()

    if args.status:
        _status_cmd(); return
    if args.stop:
        _stop_cmd();   return

    # Check singleton
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            import psutil as _ps
            if _ps.pid_exists(pid):
                print(
                    f"  [ORCHESTRATOR] Already running (PID {pid}). "
                    f"Use --stop to kill it first.",
                    file=sys.stderr,
                )
                sys.exit(1)
        except Exception:
            pass
        _PID_FILE.unlink(missing_ok=True)

    # Build config
    cfg = OrchestratorConfig.from_env()
    if args.sequential:
        cfg.start_concurrency = 1
    if args.concurrency is not None:
        cfg.start_concurrency = args.concurrency
    if args.max_concurrency is not None:
        cfg.max_concurrency = args.max_concurrency
    if args.scale_interval is not None:
        cfg.scale_interval_s = args.scale_interval
    if args.port_interval is not None:
        cfg.port_interval_s = args.port_interval
    if args.vram_target is not None:
        cfg.vram_target_pct = args.vram_target
    if args.ram_target is not None:
        cfg.ram_target_pct = args.ram_target
    if args.cpu_target is not None:
        cfg.cpu_target_pct = args.cpu_target
    if args.no_scale:
        cfg.max_concurrency = cfg.start_concurrency

    # Clamp to valid ladder
    valid = cfg.valid_concurrency_levels
    if cfg.start_concurrency not in valid:
        cfg.start_concurrency = min(valid, key=lambda x: abs(x - cfg.start_concurrency))

    orchestrator = Orchestrator(cfg)
    orchestrator.run()


if __name__ == "__main__":
    main()
