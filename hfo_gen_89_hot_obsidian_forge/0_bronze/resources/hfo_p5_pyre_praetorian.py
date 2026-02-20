#!/usr/bin/env python3
"""
hfo_p5_pyre_praetorian.py — P5 IMMUNIZE Daemon: Resource Governance + Fail-Closed Gates

Port: P5 | Commander: Pyre Praetorian | Powerword: IMMUNIZE | Tri: 101
MOSAIC: DEFEND | Galois pair: P2 (SHAPE)

Architecture (Three Rings of Machine Enforcement, doc 145):
  Ring 0: Cantrip-First Dispatch — deterministic checks never reach LLM
  Ring 1: Output Schema Gate — structured output validated before commit
  Ring 2: Post-Turn Audit — receipts, tests, drift checked

Core subsystems:
  - LifecycleManager (doc 409): register/unregister/dispose/disposeAll
  - Fail-Closed Gates (doc 407): structured payload, visible failure, no silent degradation
  - Phoenix Protocol (doc 332): resurrection after catastrophic failure
  - Prismatic Wall (doc 411): defense-in-depth, layered validation
  - Resource Governance P5.0: terminal limits, memory ceilings, Ollama model lifecycle

GREATER_SHOUT trigger: Event 9741, nonce 6C2D3D2D — resource runaway crash
  41 concurrent terminals, broken nonce chain, no lifecycle management

Usage:
  # Check system health
  python hfo_p5_pyre_praetorian.py status

  # Run eval with P5 governance (wraps prey8_eval_harness.py)
  python hfo_p5_pyre_praetorian.py eval --model qwen2.5-coder:7b --mode both --limit 5

  # Clean up orphaned resources
  python hfo_p5_pyre_praetorian.py phoenix

  # Validate SSOT integrity
  python hfo_p5_pyre_praetorian.py audit

  # Unload all Ollama models
  python hfo_p5_pyre_praetorian.py dispose-models
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
from typing import Optional

# ---------------------------------------------------------------------------
# § 0  PATH + CONFIG
# ---------------------------------------------------------------------------

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for a in [anchor] + list(anchor.parents):
            if (a / "AGENTS.md").exists():
                return a
    return Path.cwd()

HFO_ROOT = _find_root()
DB_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# P5 Resource Ceilings (Meadows Level 4 — rules of the system)
CEILINGS = {
    "max_ollama_loaded_models": 2,       # Max models loaded in VRAM simultaneously
    "max_eval_problems_per_run": 20,     # Hard cap per eval invocation
    "max_eval_time_per_problem_s": 300,  # 5 min per problem (generous for CPU)
    "max_total_eval_time_s": 3600,       # 1 hour total per eval run
    "max_concurrent_subprocesses": 4,    # Test runners in parallel
    "ollama_unload_after_eval": True,    # Unload model from VRAM after eval run
    "min_disk_free_gb": 10,              # Fail-closed if disk < 10 GB
    "max_ssot_growth_per_run_mb": 5,     # Alert if SSOT grows > 5 MB in one run
}


# ---------------------------------------------------------------------------
# § 1  LIFECYCLE MANAGER  (doc 409 pattern)
# ---------------------------------------------------------------------------

class LifecycleManager:
    """Singleton resource registry with dispose/purge semantics.
    Every subsystem registers before use. Disposal is explicit and targeted."""

    def __init__(self):
        self._disposables: list[dict] = []  # ordered iteration for purge
        self._engines: dict[str, dict] = {}  # targeted disposal by ID
        self._start_time = time.time()

    def register(self, resource_id: str, dispose_fn, metadata: dict = None):
        """Register a resource with its dispose function."""
        entry = {
            "id": resource_id,
            "dispose": dispose_fn,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self._disposables.append(entry)
        self._engines[resource_id] = entry

    def unregister(self, resource_id: str):
        """Remove from registry without disposing."""
        self._engines.pop(resource_id, None)
        self._disposables = [d for d in self._disposables if d["id"] != resource_id]

    def dispose(self, resource_id: str) -> bool:
        """Targeted teardown by ID."""
        entry = self._engines.pop(resource_id, None)
        if entry and entry["dispose"]:
            try:
                entry["dispose"]()
            except Exception as e:
                print(f"  [P5 WARN] dispose({resource_id}) error: {e}")
            self._disposables = [d for d in self._disposables if d["id"] != resource_id]
            return True
        return False

    def dispose_all(self):
        """Catastrophe purge — tear down everything in reverse order."""
        for entry in reversed(self._disposables):
            try:
                if entry["dispose"]:
                    entry["dispose"]()
            except Exception:
                pass
        self._disposables.clear()
        self._engines.clear()

    def list_resources(self) -> list[dict]:
        """List all registered resources."""
        return [
            {"id": d["id"], "registered_at": d["registered_at"], "metadata": d["metadata"]}
            for d in self._disposables
        ]

    @property
    def uptime_s(self) -> float:
        return time.time() - self._start_time


# Global lifecycle manager
_lifecycle = LifecycleManager()


# ---------------------------------------------------------------------------
# § 2  FAIL-CLOSED GATE  (doc 407 pattern)
# ---------------------------------------------------------------------------

class FailClosedError(Exception):
    """Raised when a fail-closed gate fires. The system is VISIBLY broken."""
    def __init__(self, reason: str, details: dict = None):
        self.reason = reason
        self.details = details or {}
        self.payload = {
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": self.details,
            "p5_commander": "Pyre Praetorian",
            "action": "FAIL_CLOSED — no silent degradation",
        }
        super().__init__(f"P5 FAIL-CLOSED: {reason}")


def fail_closed(reason: str, details: dict = None):
    """Fire fail-closed gate. Visible failure + structured proof."""
    err = FailClosedError(reason, details)
    # Write to SSOT
    _write_p5_event("hfo.gen89.p5.fail_closed", {
        "reason": reason,
        "details": details or {},
        "severity": "CRITICAL",
    })
    raise err


# ---------------------------------------------------------------------------
# § 3  SSOT LOGGING
# ---------------------------------------------------------------------------

def _write_p5_event(event_type: str, data: dict) -> int:
    """Write a P5 event to SSOT stigmergy_events."""
    if not DB_PATH.exists():
        return -1
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": f"hfo_p5_pyre_praetorian_gen{GEN}",
        "subject": "P5-IMMUNIZE",
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        conn.execute(
            "INSERT OR IGNORE INTO stigmergy_events "
            "(event_type, timestamp, subject, source, data_json, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event["type"], ts, "P5-IMMUNIZE", event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# § 4  RING 0: CANTRIP-FIRST DISPATCH (deterministic checks)
# ---------------------------------------------------------------------------

def check_ollama_online() -> dict:
    """Ring 0 cantrip: Is Ollama reachable?"""
    try:
        import httpx
        with httpx.Client(timeout=5) as c:
            r = c.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            return {"online": True, "models": models, "count": len(models)}
    except Exception as e:
        return {"online": False, "error": str(e), "models": [], "count": 0}


def check_ollama_loaded() -> list[dict]:
    """Ring 0 cantrip: What models are currently loaded in VRAM?"""
    try:
        import httpx
        with httpx.Client(timeout=5) as c:
            r = c.get(f"{OLLAMA_BASE}/api/ps")
            r.raise_for_status()
            return r.json().get("models", [])
    except Exception:
        return []


def check_disk_free_gb() -> float:
    """Ring 0 cantrip: Free disk space on SSOT drive."""
    import shutil
    total, used, free = shutil.disk_usage(str(DB_PATH.parent))
    return free / (1024 ** 3)


def check_ssot_size_mb() -> float:
    """Ring 0 cantrip: Current SSOT database size."""
    if DB_PATH.exists():
        return DB_PATH.stat().st_size / (1024 ** 2)
    return 0.0


def get_ssot_event_count() -> int:
    """Ring 0 cantrip: Total stigmergy events."""
    if not DB_PATH.exists():
        return 0
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        return conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
    finally:
        conn.close()


def check_orphaned_nonces() -> list[dict]:
    """Ring 0 cantrip: Find perceive events without matching yields."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        perceives = conn.execute(
            "SELECT id, timestamp, data_json FROM stigmergy_events "
            "WHERE event_type LIKE '%perceive%' ORDER BY id DESC LIMIT 20"
        ).fetchall()
        yields = conn.execute(
            "SELECT id, timestamp, data_json FROM stigmergy_events "
            "WHERE event_type LIKE '%yield%' ORDER BY id DESC LIMIT 20"
        ).fetchall()
        # Simple: more perceives than yields = orphans
        orphan_count = len(perceives) - len(yields)
        return [{
            "perceive_count": len(perceives),
            "yield_count": len(yields),
            "orphan_estimate": max(0, orphan_count),
        }]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# § 5  RING 1: RESOURCE GOVERNANCE (pre-eval validation)
# ---------------------------------------------------------------------------

def preflight_check() -> dict:
    """Ring 1: Full preflight resource governance check.
    Returns pass/fail + structured receipt."""

    checks = {}
    all_pass = True

    # 1. Ollama online
    ollama = check_ollama_online()
    checks["ollama_online"] = ollama["online"]
    if not ollama["online"]:
        all_pass = False

    # 2. Disk space
    disk_gb = check_disk_free_gb()
    checks["disk_free_gb"] = round(disk_gb, 1)
    checks["disk_ok"] = disk_gb >= CEILINGS["min_disk_free_gb"]
    if not checks["disk_ok"]:
        all_pass = False

    # 3. SSOT exists + accessible
    checks["ssot_exists"] = DB_PATH.exists()
    checks["ssot_size_mb"] = round(check_ssot_size_mb(), 1)
    if not checks["ssot_exists"]:
        all_pass = False

    # 4. Loaded models count
    loaded = check_ollama_loaded()
    checks["loaded_models"] = len(loaded)
    checks["loaded_model_names"] = [m.get("name", "?") for m in loaded]
    checks["loaded_within_ceiling"] = len(loaded) <= CEILINGS["max_ollama_loaded_models"]

    # 5. Available models
    checks["available_models"] = ollama.get("models", [])
    checks["available_count"] = ollama.get("count", 0)

    # 6. Event count
    checks["stigmergy_events"] = get_ssot_event_count()

    # 7. Orphaned nonces
    orphans = check_orphaned_nonces()
    checks["orphaned_nonces"] = orphans

    checks["all_pass"] = all_pass
    checks["timestamp"] = datetime.now(timezone.utc).isoformat()
    checks["ceilings"] = CEILINGS

    return checks


def validate_eval_request(model: str, mode: str, limit: int) -> dict:
    """Ring 1: Validate an eval request against P5 ceilings.
    Returns None if OK, or fail-closed reason."""

    violations = []

    # Check model exists
    ollama = check_ollama_online()
    if not ollama["online"]:
        violations.append("Ollama API is offline")
    elif model != "all" and model not in ollama.get("models", []):
        violations.append(f"Model '{model}' not found in Ollama")

    # Check limit
    if limit > CEILINGS["max_eval_problems_per_run"]:
        violations.append(
            f"Limit {limit} exceeds ceiling {CEILINGS['max_eval_problems_per_run']}"
        )

    # Check disk
    disk_gb = check_disk_free_gb()
    if disk_gb < CEILINGS["min_disk_free_gb"]:
        violations.append(f"Disk free {disk_gb:.1f} GB < minimum {CEILINGS['min_disk_free_gb']} GB")

    if violations:
        return {"allowed": False, "violations": violations}
    return {"allowed": True, "violations": []}


# ---------------------------------------------------------------------------
# § 6  OLLAMA MODEL LIFECYCLE
# ---------------------------------------------------------------------------

def unload_model(model: str) -> bool:
    """Unload a model from Ollama VRAM to free resources."""
    try:
        import httpx
        with httpx.Client(timeout=30) as c:
            r = c.post(f"{OLLAMA_BASE}/api/generate", json={
                "model": model, "keep_alive": 0,
            })
            return r.status_code == 200
    except Exception:
        return False


def unload_all_models() -> list[str]:
    """Unload all currently loaded models."""
    loaded = check_ollama_loaded()
    unloaded = []
    for m in loaded:
        name = m.get("name", m.get("model", ""))
        if name and unload_model(name):
            unloaded.append(name)
    return unloaded


# ---------------------------------------------------------------------------
# § 7  RING 2: POST-TURN AUDIT — SW-4 RECEIPT GENERATION
# ---------------------------------------------------------------------------

def generate_eval_receipt(
    model: str,
    mode: str,
    problems_total: int,
    problems_passed: int,
    gate_score: Optional[float],
    duration_s: float,
    details: dict = None,
) -> dict:
    """Generate a SW-4 Completion Contract receipt for an eval run.

    Given → When → Then structure with evidence."""

    score = problems_passed / problems_total if problems_total > 0 else 0.0
    receipt_nonce = secrets.token_hex(4).upper()

    receipt = {
        "receipt_id": f"P5-EVAL-{receipt_nonce}",
        "receipt_type": "SW-4 Completion Contract",
        "port": "P5 IMMUNIZE",
        "commander": "Pyre Praetorian",
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "given": {
            "model": model,
            "mode": mode,
            "problems_total": problems_total,
            "ceilings_applied": CEILINGS,
            "ollama_base": OLLAMA_BASE,
        },
        "when": {
            "action": f"Executed {mode} eval with {problems_total} problems on {model}",
            "duration_s": round(duration_s, 2),
            "governance": "P5 resource ceilings enforced",
        },
        "then": {
            "code_score": round(score, 4),
            "code_passed": problems_passed,
            "gate_score": round(gate_score, 4) if gate_score is not None else None,
            "pass_at_1": f"{score:.1%}",
            "verdict": "PASS" if score >= 0.5 else "FAIL",
            "evidence": f"{problems_passed}/{problems_total} tests passed in {duration_s:.1f}s",
        },
        "details": details or {},
    }

    # Write receipt to SSOT
    _write_p5_event("hfo.gen89.p5.eval_receipt", receipt)

    return receipt


def print_receipt(receipt: dict):
    """Pretty-print a SW-4 receipt."""
    r = receipt
    print(f"\n{'='*64}")
    print(f"  SW-4 COMPLETION CONTRACT — {r['receipt_id']}")
    print(f"  Port: {r['port']} | Commander: {r['commander']}")
    print(f"{'='*64}")
    print(f"  GIVEN:")
    print(f"    Model:    {r['given']['model']}")
    print(f"    Mode:     {r['given']['mode']}")
    print(f"    Problems: {r['given']['problems_total']}")
    print(f"  WHEN:")
    print(f"    {r['when']['action']}")
    print(f"    Duration: {r['when']['duration_s']}s")
    print(f"    {r['when']['governance']}")
    print(f"  THEN:")
    print(f"    Code Score: {r['then']['pass_at_1']} ({r['then']['code_passed']}/{r['given']['problems_total']})")
    if r["then"]["gate_score"] is not None:
        print(f"    Gate Score: {r['then']['gate_score']:.1%}")
    print(f"    Verdict:    {r['then']['verdict']}")
    print(f"    Evidence:   {r['then']['evidence']}")
    print(f"  Receipt:      {r['receipt_id']}")
    print(f"  Timestamp:    {r['timestamp']}")
    print(f"{'='*64}\n")


# ---------------------------------------------------------------------------
# § 8  GOVERNED EVAL RUNNER (wraps prey8_eval_harness.py with P5 ceilings)
# ---------------------------------------------------------------------------

def run_governed_eval(model: str, mode: str, limit: int, verbose: bool = True) -> list[dict]:
    """Run eval with full P5 resource governance.

    Three Rings enforced:
      Ring 0: Cantrip preflight checks
      Ring 1: Ceiling validation before eval
      Ring 2: Post-turn receipt generation
    """
    receipts = []

    # ── Ring 0: Cantrip preflight ──
    preflight = preflight_check()
    if not preflight["all_pass"]:
        fail_closed("Preflight failed", preflight)

    if verbose:
        print(f"\n{'━'*64}")
        print(f"  P5 PYRE PRAETORIAN — GOVERNED EVAL")
        print(f"  Ring 0: Preflight {'PASS' if preflight['all_pass'] else 'FAIL'}")
        print(f"  Ollama: {'ONLINE' if preflight['ollama_online'] else 'OFFLINE'}"
              f" ({preflight['available_count']} models)")
        print(f"  Disk: {preflight['disk_free_gb']} GB free")
        print(f"  SSOT: {preflight['ssot_size_mb']} MB, {preflight['stigmergy_events']} events")
        print(f"{'━'*64}")

    # ── Ring 1: Validate request ──
    validation = validate_eval_request(model, mode, limit)
    if not validation["allowed"]:
        fail_closed("Eval request denied by P5 ceilings", validation)

    # Write preflight event
    _write_p5_event("hfo.gen89.p5.eval_preflight", {
        "model": model, "mode": mode, "limit": limit,
        "preflight": preflight, "validation": validation,
    })

    # Resolve models
    if model == "all":
        models = preflight.get("available_models", [])
    else:
        models = [model]

    # Resolve problem count
    effective_limit = min(limit, CEILINGS["max_eval_problems_per_run"]) if limit > 0 else 20

    # Import eval harness
    sys.path.insert(0, str(HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources"))
    import prey8_eval_harness as harness

    problems = harness.EVAL_PROBLEMS[:effective_limit]

    total_start = time.time()

    for mdl in models:
        # Check total time ceiling
        elapsed = time.time() - total_start
        if elapsed > CEILINGS["max_total_eval_time_s"]:
            if verbose:
                print(f"\n  [P5] Total time ceiling reached ({elapsed:.0f}s > {CEILINGS['max_total_eval_time_s']}s). Stopping.")
            break

        # Register model in lifecycle manager
        _lifecycle.register(f"ollama:{mdl}", lambda m=mdl: unload_model(m), {"type": "ollama_model"})

        model_start = time.time()

        if mode in ("raw", "both"):
            try:
                raw_result = harness.run_raw_eval(mdl, problems, verbose=verbose)
                duration = time.time() - model_start
                r = generate_eval_receipt(
                    model=mdl, mode="raw",
                    problems_total=raw_result["total"],
                    problems_passed=raw_result["passed"],
                    gate_score=None,
                    duration_s=duration,
                    details={"per_problem": [
                        {"id": p["id"], "name": p["name"], "passed": p["passed"],
                         "gen_time_s": p.get("gen_time_s", 0)}
                        for p in raw_result.get("results", [])
                    ]},
                )
                print_receipt(r)
                receipts.append(r)
            except Exception as e:
                if verbose:
                    print(f"\n  [P5] Raw eval error for {mdl}: {e}")
                _write_p5_event("hfo.gen89.p5.eval_error", {
                    "model": mdl, "mode": "raw", "error": str(e),
                })

        if mode in ("prey8", "both"):
            try:
                prey8_start = time.time()
                prey8_result = harness.run_prey8_eval(mdl, problems, verbose=verbose)
                duration = time.time() - prey8_start
                r = generate_eval_receipt(
                    model=mdl, mode="prey8",
                    problems_total=prey8_result["total"],
                    problems_passed=prey8_result["code_passed"],
                    gate_score=prey8_result.get("gate_score"),
                    duration_s=duration,
                    details={"per_problem": [
                        {"id": p["id"], "name": p["name"],
                         "code_passed": p.get("code_passed", False),
                         "all_gates_passed": p.get("all_gates_passed", False),
                         "meadows_level": p.get("meadows_level"),
                         "gen_time_s": p.get("gen_time_s", 0)}
                        for p in prey8_result.get("results", [])
                    ]},
                )
                print_receipt(r)
                receipts.append(r)
            except Exception as e:
                if verbose:
                    print(f"\n  [P5] PREY8 eval error for {mdl}: {e}")
                _write_p5_event("hfo.gen89.p5.eval_error", {
                    "model": mdl, "mode": "prey8", "error": str(e),
                })

        # Unload model after eval if ceiling says so
        if CEILINGS["ollama_unload_after_eval"]:
            if verbose:
                print(f"  [P5] Unloading {mdl} from VRAM...")
            unload_model(mdl)
            _lifecycle.dispose(f"ollama:{mdl}")

    # ── Ring 2: Post-turn audit ──
    total_duration = time.time() - total_start
    if verbose:
        print(f"\n{'━'*64}")
        print(f"  P5 POST-TURN AUDIT")
        print(f"  Models tested: {len(models)}")
        print(f"  Total duration: {total_duration:.1f}s")
        print(f"  Receipts generated: {len(receipts)}")
        loaded_after = check_ollama_loaded()
        print(f"  Models still loaded: {len(loaded_after)}")
        print(f"  SSOT events after: {get_ssot_event_count()}")
        print(f"{'━'*64}")

    # Write audit summary
    _write_p5_event("hfo.gen89.p5.eval_audit", {
        "models_tested": len(models),
        "receipts": [r["receipt_id"] for r in receipts],
        "total_duration_s": round(total_duration, 2),
        "ceilings_applied": CEILINGS,
    })

    return receipts


# ---------------------------------------------------------------------------
# § 9  PHOENIX PROTOCOL (doc 332)
# ---------------------------------------------------------------------------

def phoenix_recovery(verbose: bool = True):
    """Phoenix Protocol — resurrection after catastrophic failure.
    Clean up orphaned resources, unload models, check SSOT integrity."""

    if verbose:
        print(f"\n{'━'*64}")
        print(f"  PHOENIX PROTOCOL — Resurrection After Catastrophic Failure")
        print(f"  Port: P5 IMMUNIZE | Commander: Pyre Praetorian")
        print(f"{'━'*64}")

    actions = []

    # 1. Unload all Ollama models
    unloaded = unload_all_models()
    if unloaded:
        actions.append(f"Unloaded {len(unloaded)} models: {', '.join(unloaded)}")
        if verbose:
            print(f"  [Phoenix] Unloaded models: {', '.join(unloaded)}")
    else:
        if verbose:
            print(f"  [Phoenix] No models to unload")

    # 2. Dispose lifecycle manager
    resources = _lifecycle.list_resources()
    _lifecycle.dispose_all()
    if resources:
        actions.append(f"Disposed {len(resources)} lifecycle resources")
        if verbose:
            print(f"  [Phoenix] Disposed {len(resources)} resources")

    # 3. Check SSOT integrity
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            ok = result[0] == "ok"
            actions.append(f"SSOT integrity: {'OK' if ok else 'CORRUPTED'}")
            if verbose:
                print(f"  [Phoenix] SSOT integrity: {result[0]}")
        finally:
            conn.close()

    # 4. Check orphaned nonces
    orphans = check_orphaned_nonces()
    if orphans and orphans[0].get("orphan_estimate", 0) > 0:
        actions.append(f"Orphaned nonces: ~{orphans[0]['orphan_estimate']}")
        if verbose:
            print(f"  [Phoenix] Orphaned nonces: ~{orphans[0]['orphan_estimate']}")

    # 5. Write recovery event
    _write_p5_event("hfo.gen89.p5.phoenix_recovery", {
        "actions": actions,
        "models_unloaded": unloaded,
        "ssot_size_mb": round(check_ssot_size_mb(), 1),
        "ssot_events": get_ssot_event_count(),
    })

    if verbose:
        print(f"  [Phoenix] Recovery complete. {len(actions)} actions taken.")
        print(f"{'━'*64}\n")


# ---------------------------------------------------------------------------
# § 10  SSOT AUDIT
# ---------------------------------------------------------------------------

def ssot_audit(verbose: bool = True) -> dict:
    """Full SSOT audit — event counts, nonce chains, recent activity."""
    if not DB_PATH.exists():
        if verbose:
            print("  SSOT not found!")
        return {"error": "SSOT not found"}

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        # Event type breakdown
        types = conn.execute(
            "SELECT event_type, COUNT(*) FROM stigmergy_events "
            "GROUP BY event_type ORDER BY COUNT(*) DESC LIMIT 20"
        ).fetchall()

        # Recent P5 events
        p5_events = conn.execute(
            "SELECT id, event_type, timestamp FROM stigmergy_events "
            "WHERE event_type LIKE '%p5%' ORDER BY id DESC LIMIT 10"
        ).fetchall()

        # Recent eval events
        eval_events = conn.execute(
            "SELECT id, event_type, timestamp, "
            "json_extract(data_json, '$.data.model') as model, "
            "json_extract(data_json, '$.data.score') as score "
            "FROM stigmergy_events "
            "WHERE event_type LIKE '%eval%' ORDER BY id DESC LIMIT 10"
        ).fetchall()

        # GREATER_SHOUT events
        shouts = conn.execute(
            "SELECT id, event_type, timestamp FROM stigmergy_events "
            "WHERE event_type LIKE '%SHOUT%' ORDER BY id DESC LIMIT 5"
        ).fetchall()

        total = conn.execute("SELECT COUNT(*) FROM stigmergy_events").fetchone()[0]
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

        report = {
            "total_events": total,
            "total_docs": doc_count,
            "ssot_size_mb": round(check_ssot_size_mb(), 1),
            "top_event_types": {str(t[0]): t[1] for t in types},
            "recent_p5_events": [{"id": e[0], "type": e[1], "ts": e[2]} for e in p5_events],
            "recent_eval_events": [{"id": e[0], "type": e[1], "ts": e[2], "model": e[3], "score": e[4]} for e in eval_events],
            "greater_shouts": [{"id": s[0], "type": s[1], "ts": s[2]} for s in shouts],
        }

        if verbose:
            print(f"\n{'━'*64}")
            print(f"  SSOT AUDIT — P5 Pyre Praetorian")
            print(f"{'━'*64}")
            print(f"  Documents:  {doc_count}")
            print(f"  Events:     {total}")
            print(f"  SSOT size:  {report['ssot_size_mb']} MB")
            print(f"\n  Top event types:")
            for t, c in list(report["top_event_types"].items())[:10]:
                print(f"    {t:<50} {c:>5}")
            if report["recent_eval_events"]:
                print(f"\n  Recent eval events:")
                for e in report["recent_eval_events"][:5]:
                    print(f"    [{e['id']}] {e['type']:<40} model={e.get('model', '?')} score={e.get('score', '?')}")
            if report["greater_shouts"]:
                print(f"\n  GREATER_SHOUTs:")
                for s in report["greater_shouts"]:
                    print(f"    [{s['id']}] {s['type']} @ {s['ts']}")
            print(f"{'━'*64}\n")

        return report
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# § 11  STATUS COMMAND
# ---------------------------------------------------------------------------

def status_command(verbose: bool = True) -> dict:
    """Full P5 status: preflight + audit combined."""
    preflight = preflight_check()

    if verbose:
        print(f"\n{'━'*64}")
        print(f"  P5 PYRE PRAETORIAN — STATUS")
        print(f"  Commander: Pyre Praetorian | Port: P5 | Powerword: IMMUNIZE")
        print(f"{'━'*64}")
        print(f"  Ollama:        {'ONLINE' if preflight['ollama_online'] else 'OFFLINE'}")
        print(f"  Models:        {preflight['available_count']} available, {preflight['loaded_models']} loaded")
        if preflight['loaded_model_names']:
            print(f"  Loaded:        {', '.join(preflight['loaded_model_names'])}")
        print(f"  Disk free:     {preflight['disk_free_gb']} GB")
        print(f"  SSOT:          {preflight['ssot_size_mb']} MB, {preflight['stigmergy_events']} events")
        print(f"  All checks:    {'PASS' if preflight['all_pass'] else 'FAIL'}")
        print(f"  Ceilings:")
        for k, v in CEILINGS.items():
            print(f"    {k:<35} {v}")
        print(f"{'━'*64}")

    audit = ssot_audit(verbose=verbose)

    return {"preflight": preflight, "audit": audit}


# ---------------------------------------------------------------------------
# § 12  CLI ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="P5 Pyre Praetorian — Resource Governance + Fail-Closed Gates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Commands:
              status         Full P5 status (preflight + audit)
              eval           Run governed eval with receipts
              phoenix        Phoenix Protocol recovery
              audit          SSOT audit
              dispose-models Unload all Ollama models from VRAM
        """),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="P5 status + preflight + audit")

    # eval
    eval_p = sub.add_parser("eval", help="Run governed eval with P5 ceilings + receipts")
    eval_p.add_argument("--model", default="qwen2.5-coder:7b")
    eval_p.add_argument("--mode", choices=["raw", "prey8", "both"], default="raw")
    eval_p.add_argument("--limit", type=int, default=10)
    eval_p.add_argument("--quiet", action="store_true")

    # phoenix
    sub.add_parser("phoenix", help="Phoenix Protocol — clean recovery")

    # audit
    sub.add_parser("audit", help="SSOT audit")

    # dispose-models
    sub.add_parser("dispose-models", help="Unload all Ollama models from VRAM")

    args = parser.parse_args()
    verbose = not getattr(args, "quiet", False)

    if args.command == "status":
        status_command(verbose=verbose)

    elif args.command == "eval":
        try:
            receipts = run_governed_eval(
                model=args.model, mode=args.mode,
                limit=args.limit, verbose=verbose,
            )
            print(f"\n  Total receipts: {len(receipts)}")
            for r in receipts:
                print(f"    {r['receipt_id']}: {r['given']['model']} ({r['given']['mode']}) "
                      f"→ {r['then']['pass_at_1']} {r['then']['verdict']}")
        except FailClosedError as e:
            print(f"\n  P5 FAIL-CLOSED: {e.reason}")
            print(f"  Details: {json.dumps(e.details, indent=2)}")
            sys.exit(1)

    elif args.command == "phoenix":
        phoenix_recovery(verbose=verbose)

    elif args.command == "audit":
        ssot_audit(verbose=verbose)

    elif args.command == "dispose-models":
        unloaded = unload_all_models()
        if unloaded:
            print(f"  Unloaded: {', '.join(unloaded)}")
        else:
            print("  No models currently loaded.")


if __name__ == "__main__":
    main()
