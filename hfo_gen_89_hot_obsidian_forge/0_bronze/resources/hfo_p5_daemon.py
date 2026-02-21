#!/usr/bin/env python3
"""
hfo_p5_daemon.py — P5 Pyre Praetorian 24/7 Governance Daemon
=============================================================
v1.0 | Gen89 | Port: P5 IMMUNIZE | Commander: Pyre Praetorian
Powerword: IMMUNIZE | Spell: CONTINGENCY | School: Evocation
Title: Dancer of Death and Dawn | Trigram: ☲ Li (Fire)

PURPOSE:
    Continuous background daemon that enforces governance, detects
    anomalies, reaps orphaned sessions, manages Ollama model lifecycle,
    and runs periodic SSOT integrity audits.

    This is the P5 IMMUNIZE daemon — the immune system of HFO.
    It never sleeps. It never forgets. It writes every action as
    stigmergy for the swarm to observe.

PATROL TASKS (5 concurrent asyncio loops):
    T1 — SSOT Integrity Patrol   (every 120s)  Ring 0 cantrip checks
    T2 — Session Orphan Reaper   (every 180s)  Find + close orphaned sessions
    T3 — Ollama Model Governance (every 300s)  VRAM ceiling enforcement
    T4 — Anomaly Detection       (every  60s)  Watchdog 7-class detector
    T5 — LLM Policy Analyst      (every 600s)  Gemini/Ollama deep analysis

ARCHITECTURE:
    - Imports existing P5 cantrips from hfo_p5_pyre_praetorian.py (no duplication)
    - Imports watchdog anomaly detectors from hfo_stigmergy_watchdog.py
    - Uses dual-provider: Gemini (cloud) for bulk analysis, Ollama (local) for P5 reasoning
    - asyncio event loop with per-task intervals and signal-based shutdown
    - State persisted to .hfo_p5_daemon_state.json
    - All actions logged as CloudEvents to SSOT stigmergy_events

USAGE:
    # Start continuous daemon (24/7 mode)
    python hfo_p5_daemon.py

    # Run one patrol cycle then exit
    python hfo_p5_daemon.py --once

    # Dry run (detect but don't write to SSOT)
    python hfo_p5_daemon.py --dry-run

    # Specific tasks only
    python hfo_p5_daemon.py --tasks integrity,reaper,anomaly

    # Custom intervals (seconds)
    python hfo_p5_daemon.py --integrity-interval 120 --reaper-interval 180

    # Show status
    python hfo_p5_daemon.py --status

    # Install as Windows scheduled task (runs every 5 minutes)
    python hfo_p5_daemon.py --install-schedule

Medallion: bronze
Pointer key: daemon.p5
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Path Resolution ──────────────────────────────────────────

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
FORGE = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge"
DB_PATH = FORGE / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
BRONZE_RESOURCES = FORGE / "0_bronze" / "resources"
STATE_FILE = HFO_ROOT / ".hfo_p5_daemon_state.json"
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
P5_MODEL = os.environ.get("P5_OLLAMA_MODEL", "phi4:14b")
P5_SOURCE = f"hfo_p5_daemon_gen{GEN}_v1.0"

# ── Import existing P5 cantrips + watchdog ───────────────────

sys.path.insert(0, str(BRONZE_RESOURCES))

from hfo_p5_pyre_praetorian import (
from hfo_ssot_write import get_db_readwrite
    check_ollama_online,
    check_ollama_loaded,
    check_disk_free_gb,
    check_ssot_size_mb,
    get_ssot_event_count,
    check_orphaned_nonces,
    preflight_check,
    unload_model,
    unload_all_models,
    CEILINGS,
    FailClosedError,
)

# Watchdog anomaly detection (import the scanner functions)
try:
    from hfo_stigmergy_watchdog import (
        _fetch_events_since,
        _load_watermark as _watchdog_load_watermark,
        _save_watermark as _watchdog_save_watermark,
        KNOWN_AGENTS,
        GATE_BLOCK_STORM_THRESHOLD,
        TAMPER_CLUSTER_THRESHOLD,
        ORPHAN_RATIO_THRESHOLD,
    )
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# Gemini integration (optional)
try:
    from hfo_gemini_models import (
        GEMINI_API_KEY,
        GeminiRateLimiter,
        get_model,
        select_tier,
    )
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
except ImportError:
    GEMINI_AVAILABLE = False
    GEMINI_API_KEY = ""


# ═══════════════════════════════════════════════════════════════
# Database Helpers — ALL with busy_timeout
# ═══════════════════════════════════════════════════════════════

def get_db_readonly() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn



def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_p5_event(
    event_type: str,
    subject: str,
    data: dict,
    dry_run: bool = False,
) -> Optional[int]:
    """Write a P5 governance event to SSOT stigmergy trail."""
    ts = _now_iso()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": P5_SOURCE,
        "subject": subject,
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()

    if dry_run:
        return None

    conn = get_db_readwrite()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_type, ts, subject, P5_SOURCE, json.dumps(event), content_hash),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Gemini Client (rate-limited, optional)
# ═══════════════════════════════════════════════════════════════

class P5GeminiClient:
    """Lightweight Gemini client for P5 policy analysis."""

    def __init__(self):
        self._client = None
        self._rate_limiter = GeminiRateLimiter() if GEMINI_AVAILABLE else None

    def _ensure_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=GEMINI_API_KEY)
        return self._client

    async def analyze(self, prompt: str, model: str = "lite_25") -> str:
        """Send a governance analysis prompt to Gemini."""
        if not GEMINI_AVAILABLE:
            return "[Gemini unavailable — set GEMINI_API_KEY]"

        model_spec = get_model(model)
        model_id = model_spec.model_id

        if self._rate_limiter:
            allowed, reason = self._rate_limiter.check(model_id)
            if not allowed:
                return f"[Rate limited: {reason}]"

        client = self._ensure_client()
        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=0.2,
            system_instruction=(
                "You are P5 Pyre Praetorian, the governance and defense commander "
                "of HFO Gen89. Analyze the provided system state for anomalies, "
                "risks, and recommended governance actions. Be concise and actionable."
            ),
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=model_id, contents=prompt, config=config
            ),
        )

        if self._rate_limiter:
            self._rate_limiter.record(model_id)
        return response.text


# ═══════════════════════════════════════════════════════════════
# Ollama Client (local, for P5 deep reasoning)
# ═══════════════════════════════════════════════════════════════

class P5OllamaClient:
    """Local Ollama client for P5 reasoning — uses phi4:14b by default."""

    def __init__(self, model: str = P5_MODEL):
        self.model = model

    async def reason(self, prompt: str) -> str:
        """Send a governance reasoning prompt to local Ollama."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{OLLAMA_BASE}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": (
                            "You are P5 Pyre Praetorian — the immune system of HFO Gen89. "
                            "You analyze system health, detect threats, and recommend "
                            "defensive actions. Be precise and evidence-based."
                        ),
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 512},
                    },
                )
                response.raise_for_status()
                return response.json().get("response", "")
        except Exception as e:
            return f"[Ollama error: {e}]"


# ═══════════════════════════════════════════════════════════════
# PATROL TASK 1 — SSOT Integrity Patrol (Ring 0 Cantrips)
# ═══════════════════════════════════════════════════════════════

class IntegrityPatrolTask:
    """Periodic SSOT + system health checks using existing P5 cantrips."""

    name = "integrity"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._cycle_count = 0

    async def run_once(self) -> dict:
        self._cycle_count += 1
        result = {"cycle": self._cycle_count, "checks": {}, "alerts": []}

        # 1. Disk space
        disk_gb = check_disk_free_gb()
        result["checks"]["disk_free_gb"] = round(disk_gb, 1)
        if disk_gb < CEILINGS["min_disk_free_gb"]:
            result["alerts"].append(f"LOW DISK: {disk_gb:.1f} GB < {CEILINGS['min_disk_free_gb']} GB")

        # 2. SSOT size + accessibility
        ssot_mb = check_ssot_size_mb()
        result["checks"]["ssot_size_mb"] = round(ssot_mb, 1)
        result["checks"]["ssot_exists"] = DB_PATH.exists()

        # 3. SSOT integrity check (every 10th cycle = ~20 min at 120s)
        if self._cycle_count % 10 == 1:
            try:
                conn = get_db_readwrite()
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                conn.close()
                result["checks"]["integrity"] = integrity
                if integrity != "ok":
                    result["alerts"].append(f"SSOT CORRUPTED: {integrity}")
            except Exception as e:
                result["checks"]["integrity"] = f"ERROR: {e}"
                result["alerts"].append(f"SSOT integrity check failed: {e}")

        # 4. Event count + growth
        event_count = get_ssot_event_count()
        result["checks"]["event_count"] = event_count

        # 5. Ollama status
        ollama = check_ollama_online()
        result["checks"]["ollama_online"] = ollama["online"]
        result["checks"]["ollama_model_count"] = ollama.get("count", 0)
        if not ollama["online"]:
            result["alerts"].append("Ollama OFFLINE")

        # Write event
        severity = "INFO" if not result["alerts"] else "WARNING"
        write_p5_event(
            "hfo.gen89.p5.integrity_patrol",
            "P5-INTEGRITY",
            {
                "severity": severity,
                "cycle": self._cycle_count,
                "checks": result["checks"],
                "alerts": result["alerts"],
            },
            dry_run=self.dry_run,
        )

        return result


# ═══════════════════════════════════════════════════════════════
# PATROL TASK 2 — Session Orphan Reaper
# ═══════════════════════════════════════════════════════════════

class OrphanReaperTask:
    """Find and auto-close PREY8 sessions that were perceived but never yielded.
    This combats the 87% session mortality documented in the silver audit."""

    name = "reaper"
    MAX_SESSION_AGE_SEC = 3600 * 2  # 2 hours — sessions older than this are reaped

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._reaped_total = 0

    async def run_once(self) -> dict:
        result = {"orphans_found": 0, "orphans_reaped": 0, "errors": 0}

        try:
            conn = get_db_readonly()

            # Find perceive events without matching yields (last 100)
            perceives = conn.execute(
                """SELECT id, timestamp, data_json
                   FROM stigmergy_events
                   WHERE event_type LIKE '%perceive%'
                   AND source LIKE '%prey8%'
                   ORDER BY id DESC LIMIT 100"""
            ).fetchall()

            yields = conn.execute(
                """SELECT data_json
                   FROM stigmergy_events
                   WHERE event_type LIKE '%yield%'
                   ORDER BY id DESC LIMIT 200"""
            ).fetchall()

            conn.close()

            # Build set of yielded session IDs
            yielded_sessions = set()
            for row in yields:
                try:
                    data = json.loads(row["data_json"])
                    inner = data.get("data", data)
                    sid = inner.get("session_id", "")
                    if sid:
                        yielded_sessions.add(sid)
                except (json.JSONDecodeError, KeyError):
                    pass

            # Find orphaned perceives
            now = datetime.now(timezone.utc)
            orphans = []
            for row in perceives:
                try:
                    data = json.loads(row["data_json"])
                    inner = data.get("data", data)
                    sid = inner.get("session_id", "")
                    nonce = inner.get("nonce", "")
                    probe = inner.get("probe", "")[:200]
                    ts_str = inner.get("ts", row["timestamp"])

                    if sid in yielded_sessions:
                        continue  # Already yielded

                    # Check age
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        age_sec = (now - ts).total_seconds()
                    except (ValueError, TypeError):
                        age_sec = self.MAX_SESSION_AGE_SEC + 1

                    if age_sec > self.MAX_SESSION_AGE_SEC:
                        orphans.append({
                            "event_id": row["id"],
                            "session_id": sid,
                            "nonce": nonce,
                            "probe": probe,
                            "age_hours": round(age_sec / 3600, 1),
                        })
                except (json.JSONDecodeError, KeyError):
                    pass

            result["orphans_found"] = len(orphans)

            # Reap orphans
            for orphan in orphans[:10]:  # Max 10 per cycle
                if not self.dry_run:
                    write_p5_event(
                        "hfo.gen89.prey8.yield",
                        "prey-yield-reaper",
                        {
                            "summary": f"REAPER: Auto-closed orphaned session {orphan['session_id']} "
                                       f"(age: {orphan['age_hours']}h, probe: {orphan['probe'][:100]})",
                            "session_id": orphan["session_id"],
                            "perceive_nonce": orphan["nonce"],
                            "reaper_action": "auto_close",
                            "age_hours": orphan["age_hours"],
                            "original_probe": orphan["probe"],
                            "p3_delivery_manifest": ["REAPER: orphan auto-closed"],
                            "p5_test_evidence": ["Session orphaned — no yield within threshold"],
                            "p5_mutation_confidence": 0,
                            "p5_immunization_status": "FAILED",
                            "sw4_completion_contract": {
                                "given": f"Session {orphan['session_id']} perceived but never yielded",
                                "when": f"Orphan reaper detected session aged {orphan['age_hours']}h",
                                "then": "Session auto-closed with failure yield to improve yield ratio",
                            },
                        },
                    )
                result["orphans_reaped"] += 1
                self._reaped_total += 1

        except Exception as e:
            result["errors"] += 1
            result["error_detail"] = str(e)

        # Log reaper cycle
        write_p5_event(
            "hfo.gen89.p5.reaper_cycle",
            "P5-REAPER",
            result,
            dry_run=self.dry_run,
        )

        return result


# ═══════════════════════════════════════════════════════════════
# PATROL TASK 3 — Ollama Model Governance
# ═══════════════════════════════════════════════════════════════

class ModelGovernanceTask:
    """Enforce Ollama VRAM ceilings — unload excess models, track lifecycle."""

    name = "model_gov"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    async def run_once(self) -> dict:
        result = {"loaded": 0, "unloaded": [], "ceiling": CEILINGS["max_ollama_loaded_models"]}

        loaded = check_ollama_loaded()
        result["loaded"] = len(loaded)
        result["loaded_names"] = [m.get("name", m.get("model", "?")) for m in loaded]

        # Enforce ceiling
        if len(loaded) > CEILINGS["max_ollama_loaded_models"]:
            excess = len(loaded) - CEILINGS["max_ollama_loaded_models"]

            # Sort by size descending — unload largest first (except P5 model)
            candidates = sorted(
                loaded,
                key=lambda m: m.get("size", 0),
                reverse=True,
            )

            for model in candidates:
                if excess <= 0:
                    break
                name = model.get("name", model.get("model", ""))
                # Never unload the P5 model if it's active
                if P5_MODEL in name:
                    continue
                if not self.dry_run:
                    success = unload_model(name)
                    if success:
                        result["unloaded"].append(name)
                        excess -= 1
                else:
                    result["unloaded"].append(f"[DRY] {name}")
                    excess -= 1

        if result["unloaded"]:
            write_p5_event(
                "hfo.gen89.p5.model_governance",
                "P5-MODEL-GOV",
                {
                    "action": "unloaded_excess_models",
                    "unloaded": result["unloaded"],
                    "ceiling": CEILINGS["max_ollama_loaded_models"],
                    "was_loaded": result["loaded"],
                },
                dry_run=self.dry_run,
            )

        return result


# ═══════════════════════════════════════════════════════════════
# PATROL TASK 4 — Anomaly Detection (from Watchdog)
# ═══════════════════════════════════════════════════════════════

class AnomalyPatrolTask:
    """Integrated anomaly detection using watchdog patterns.
    Detects: gate block storms, tamper clusters, orphan ratio,
    session pollution, nonce replay, rapid-fire perceive, agent impersonation."""

    name = "anomaly"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._watermark = 0

    async def run_once(self) -> dict:
        result = {"anomalies_found": 0, "classes": {}, "scanned": 0}

        try:
            conn = get_db_readonly()

            # Fetch events since last scan
            events = conn.execute(
                """SELECT id, event_type, timestamp, source, subject, data_json
                   FROM stigmergy_events
                   WHERE id > ?
                   ORDER BY id ASC
                   LIMIT 500""",
                (self._watermark,),
            ).fetchall()
            conn.close()

            result["scanned"] = len(events)
            if not events:
                return result

            # Update watermark
            self._watermark = max(e["id"] for e in events)

            # Parse events
            parsed = []
            for e in events:
                try:
                    data = json.loads(e["data_json"]) if e["data_json"] else {}
                    inner = data.get("data", data)
                    parsed.append({
                        "id": e["id"],
                        "type": e["event_type"],
                        "ts": e["timestamp"],
                        "source": e["source"],
                        "subject": e["subject"],
                        "data": inner,
                    })
                except (json.JSONDecodeError, KeyError):
                    pass

            # A1 — Gate Block Storm
            gate_blocks = [e for e in parsed if "gate_blocked" in str(e["type"]).lower()
                           or (e["data"].get("gate_passed") is False)]
            if len(gate_blocks) >= GATE_BLOCK_STORM_THRESHOLD:
                result["classes"]["A1_gate_block_storm"] = len(gate_blocks)
                result["anomalies_found"] += 1
                write_p5_event(
                    "hfo.gen89.p5.anomaly.gate_block_storm",
                    "P5-ANOMALY-A1",
                    {"count": len(gate_blocks), "threshold": GATE_BLOCK_STORM_THRESHOLD},
                    dry_run=self.dry_run,
                )

            # A2 — Tamper Alert Cluster
            tampers = [e for e in parsed if "tamper" in str(e["type"]).lower()]
            if len(tampers) >= TAMPER_CLUSTER_THRESHOLD:
                result["classes"]["A2_tamper_cluster"] = len(tampers)
                result["anomalies_found"] += 1
                write_p5_event(
                    "hfo.gen89.p5.anomaly.tamper_cluster",
                    "P5-ANOMALY-A2",
                    {"count": len(tampers), "threshold": TAMPER_CLUSTER_THRESHOLD},
                    dry_run=self.dry_run,
                )

            # A3 — Orphan Ratio
            perceives = [e for e in parsed if "perceive" in str(e["type"]).lower()]
            yields_found = [e for e in parsed if "yield" in str(e["type"]).lower()]
            if perceives and len(yields_found) / max(len(perceives), 1) < (1 - ORPHAN_RATIO_THRESHOLD):
                result["classes"]["A3_orphan_ratio"] = {
                    "perceives": len(perceives),
                    "yields": len(yields_found),
                    "ratio": round(len(yields_found) / max(len(perceives), 1), 2),
                }
                result["anomalies_found"] += 1

            # A7 — Agent Impersonation
            if WATCHDOG_AVAILABLE:
                unknown_agents = set()
                for e in parsed:
                    agent_id = e["data"].get("agent_id", "")
                    if agent_id and agent_id not in KNOWN_AGENTS:
                        unknown_agents.add(agent_id)
                if unknown_agents:
                    result["classes"]["A7_agent_impersonation"] = list(unknown_agents)
                    result["anomalies_found"] += 1
                    write_p5_event(
                        "hfo.gen89.p5.anomaly.agent_impersonation",
                        "P5-ANOMALY-A7",
                        {"unknown_agents": list(unknown_agents)},
                        dry_run=self.dry_run,
                    )

        except Exception as e:
            result["error"] = str(e)

        return result


# ═══════════════════════════════════════════════════════════════
# PATROL TASK 5 — LLM Policy Analyst
# ═══════════════════════════════════════════════════════════════

class PolicyAnalystTask:
    """Uses Gemini or Ollama to analyze recent system activity and
    produce governance recommendations. Runs least frequently."""

    name = "analyst"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.gemini = P5GeminiClient() if GEMINI_AVAILABLE else None
        self.ollama = P5OllamaClient()
        self._cycle_count = 0

    async def run_once(self) -> dict:
        self._cycle_count += 1
        result = {"provider": "none", "analysis": "", "cycle": self._cycle_count}

        # Build context from recent SSOT state
        try:
            conn = get_db_readonly()

            # Recent events summary
            recent = conn.execute(
                """SELECT event_type, COUNT(*) as cnt
                   FROM stigmergy_events
                   WHERE timestamp > datetime('now', '-1 hour')
                   GROUP BY event_type
                   ORDER BY cnt DESC
                   LIMIT 15"""
            ).fetchall()

            # Recent anomalies
            anomalies = conn.execute(
                """SELECT event_type, timestamp, data_json
                   FROM stigmergy_events
                   WHERE event_type LIKE '%anomaly%' OR event_type LIKE '%fail_closed%'
                   ORDER BY id DESC LIMIT 5"""
            ).fetchall()

            # Session health
            total_perceives = conn.execute(
                "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%perceive%'"
            ).fetchone()[0]
            total_yields = conn.execute(
                "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%yield%'"
            ).fetchone()[0]

            conn.close()

            events_str = "\n".join(
                f"  {r['event_type']}: {r['cnt']} events" for r in recent
            )
            anomaly_str = "\n".join(
                f"  {a['event_type']} @ {a['timestamp']}" for a in anomalies
            ) or "  None detected"

            yield_ratio = round(total_yields / max(total_perceives, 1) * 100, 1)

            prompt = f"""P5 GOVERNANCE ANALYSIS — System Health Report

Last Hour Events:
{events_str}

Recent Anomalies:
{anomaly_str}

Session Health:
  Total Perceives: {total_perceives}
  Total Yields: {total_yields}
  Yield Ratio: {yield_ratio}%
  Session Mortality: {100 - yield_ratio}%

Analyze this state. What governance actions are needed? Are there patterns
that suggest reward-hacking, session pollution, or resource exhaustion?
Provide max 3 actionable recommendations."""

            # Try Gemini first, fallback to Ollama
            if self.gemini and GEMINI_AVAILABLE:
                try:
                    analysis = await self.gemini.analyze(prompt)
                    result["provider"] = "gemini"
                    result["analysis"] = analysis[:2000]
                except Exception as e:
                    result["gemini_error"] = str(e)
                    analysis = await self.ollama.reason(prompt)
                    result["provider"] = "ollama"
                    result["analysis"] = analysis[:2000]
            else:
                analysis = await self.ollama.reason(prompt)
                result["provider"] = "ollama"
                result["analysis"] = analysis[:2000]

            # Write analysis event
            write_p5_event(
                "hfo.gen89.p5.policy_analysis",
                "P5-ANALYST",
                {
                    "provider": result["provider"],
                    "analysis": result["analysis"],
                    "yield_ratio": yield_ratio,
                    "event_summary": events_str[:500],
                },
                dry_run=self.dry_run,
            )

        except Exception as e:
            result["error"] = str(e)

        return result


# ═══════════════════════════════════════════════════════════════
# PATROL TASK 6 — Spell Gate Phoenix (Daemon Resurrection)
# ═══════════════════════════════════════════════════════════════

class SpellGatePhoenixTask:
    """P5's PHOENIX PROTOCOL — detect dead daemons via the P7 Spell Gate
    and auto-resurrect them.  This is the P4-P5 dance: the Singer
    detects patterns (strife/splendor), the Phoenix defends and resurrects.

    Every cycle:
      1. Import the P7 Spell Gate's fleet check
      2. Scry the fleet for dead daemons
      3. Read last singer strife signal (P4-P5 dance)
      4. Auto-resummon dead daemons in priority order (if enabled)
      5. Write resurrection CloudEvents
    """

    name = "phoenix"

    # Daemons to auto-resummon in priority order (lowest number = highest priority)
    # P5 itself is excluded (can't resummon yourself)
    SELF_KEY = "pyre"
    # Resurrection cooldown: after N consecutive failures, back off
    MAX_CONSECUTIVE_FAILS = 3       # escalate after 3 fails
    COOLDOWN_BACKOFF_S = 1800       # 30 min cooldown on repeat failures

    def __init__(self, dry_run: bool = False, auto_summon: bool = True,
                 boot_summon_fleet: bool = False):
        self.dry_run = dry_run
        self.auto_summon = auto_summon
        self.boot_summon_fleet = boot_summon_fleet
        self._cycle_count = 0
        self._resurrections_total = 0
        self._boot_summon_done = False
        self._spell_gate = None
        self._fail_tracker: dict[str, dict] = {}  # key -> {count, last_attempt}
        self._load_spell_gate()

    def _load_spell_gate(self):
        """Import spell gate functions lazily."""
        try:
            import importlib.util
            gate_path = BRONZE_RESOURCES / "hfo_p7_spell_gate.py"
            spec = importlib.util.spec_from_file_location("hfo_p7_spell_gate", gate_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._spell_gate = mod
        except Exception as e:
            print(f"  [PHOENIX] WARN: Could not import spell gate: {e}", file=sys.stderr)
            self._spell_gate = None

    def _read_last_strife(self) -> dict:
        """Read the latest P4 singer strife signal (P4-P5 dance)."""
        try:
            conn = get_db_readonly()
            row = conn.execute(
                """SELECT data_json FROM stigmergy_events
                   WHERE event_type = 'hfo.gen89.singer.strife'
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            conn.close()
            if row:
                data = json.loads(row["data_json"])
                return data.get("data", data)
        except Exception:
            pass
        return {}

    def _read_last_heartbeat(self) -> dict:
        """Read latest singer heartbeat for fleet health context."""
        try:
            conn = get_db_readonly()
            row = conn.execute(
                """SELECT data_json FROM stigmergy_events
                   WHERE event_type = 'hfo.gen89.singer.heartbeat'
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            conn.close()
            if row:
                data = json.loads(row["data_json"])
                return data.get("data", data)
        except Exception:
            pass
        return {}

    def _is_on_cooldown(self, daemon_key: str) -> bool:
        """Check if daemon is in resurrection cooldown (repeated failures)."""
        info = self._fail_tracker.get(daemon_key)
        if not info:
            return False
        if info["count"] >= self.MAX_CONSECUTIVE_FAILS:
            elapsed = time.time() - info["last_attempt"]
            if elapsed < self.COOLDOWN_BACKOFF_S:
                return True
            # Cooldown expired — reset for a fresh attempt
            info["count"] = 0
        return False

    def _record_fail(self, daemon_key: str):
        info = self._fail_tracker.setdefault(daemon_key, {"count": 0, "last_attempt": 0})
        info["count"] += 1
        info["last_attempt"] = time.time()

    def _record_success(self, daemon_key: str):
        self._fail_tracker.pop(daemon_key, None)

    def _check_feature_flag(self, daemon_key: str) -> bool:
        """Check if daemon is enabled via feature flags."""
        flag_map = {
            "singer": "HFO_DAEMON_P4_SINGER_ENABLED",
            "pyre": "HFO_DAEMON_P5_ENABLED",
            "tremorsense": "HFO_DAEMONS_ENABLED",
            "cartography": "HFO_DAEMONS_ENABLED",
            "meadows": "HFO_DAEMONS_ENABLED",
            "kraken": "HFO_DAEMON_P6_SWARM_ENABLED",
        }
        env_key = flag_map.get(daemon_key, "HFO_DAEMONS_ENABLED")
        val = os.environ.get(env_key, "true").lower()
        if val in ("false", "0", "no"):
            return False
        # Master kill-switch
        master = os.environ.get("HFO_DAEMONS_ENABLED", "true").lower()
        return master not in ("false", "0", "no")

    async def run_once(self) -> dict:
        self._cycle_count += 1
        result = {
            "cycle": self._cycle_count,
            "fleet_status": {},
            "resurrections": [],
            "singer_strife": {},
            "errors": [],
        }

        if not self._spell_gate:
            result["errors"].append("Spell gate not loaded")
            return result

        # ── 1. Scry the fleet ──
        try:
            fleet_data = self._spell_gate.spell_scrying()
            fleet = fleet_data.get("fleet", {})
            result["fleet_status"] = {
                "total": fleet_data.get("total", 0),
                "alive": fleet_data.get("alive", 0),
                "dead": fleet_data.get("dead", 0),
            }
        except Exception as e:
            result["errors"].append(f"Fleet scry failed: {e}")
            return result

        # ── 2. Read P4 singer strife (P4-P5 dance) ──
        strife = self._read_last_strife()
        heartbeat = self._read_last_heartbeat()
        result["singer_strife"] = {
            "signal": strife.get("signal", "unknown"),
            "description": strife.get("description", "")[:200],
            "mood": heartbeat.get("mood", "unknown"),
            "cycle": heartbeat.get("cycle", 0),
        }

        # ── 3. Boot-summon fleet (first cycle only) ──
        if self.boot_summon_fleet and not self._boot_summon_done:
            self._boot_summon_done = True
            # Sort by priority, skip self
            registry = self._spell_gate.DAEMON_REGISTRY
            boot_order = sorted(
                [(k, s) for k, s in registry.items() if k != self.SELF_KEY],
                key=lambda x: x[1].priority,
            )
            for dk, spec in boot_order:
                if not spec.is_persistent:
                    result["resurrections"].append({
                        "daemon": dk, "action": "SKIP_ONE_SHOT",
                        "reason": "is_persistent=False",
                    })
                    continue
                if not self._check_feature_flag(dk):
                    result["resurrections"].append({
                        "daemon": dk, "action": "SKIP_DISABLED",
                        "reason": "feature_flag_off",
                    })
                    continue
                status = fleet.get(dk, {}).get("status", "NEVER_SUMMONED")
                if status == "ALIVE":
                    self._record_success(dk)
                    continue
                if self._is_on_cooldown(dk):
                    result["resurrections"].append({
                        "daemon": dk, "action": "COOLDOWN",
                        "fails": self._fail_tracker[dk]["count"],
                    })
                    continue
                if not self.dry_run:
                    try:
                        receipt = self._spell_gate.spell_summon_familiar(dk, force=True, quiet=True)
                        action = receipt.get("status", "FAILED")
                        if receipt.get("alive"):
                            self._record_success(dk)
                        else:
                            self._record_fail(dk)
                        self._resurrections_total += 1
                        result["resurrections"].append({
                            "daemon": dk, "action": f"BOOT_SUMMON:{action}",
                            "pid": receipt.get("pid", 0),
                        })
                    except Exception as e:
                        self._record_fail(dk)
                        result["resurrections"].append({
                            "daemon": dk, "action": "BOOT_SUMMON_FAILED",
                            "error": str(e),
                        })
                else:
                    result["resurrections"].append({
                        "daemon": dk, "action": "DRY_BOOT_SUMMON",
                    })

        # ── 4. Detect and resurrect dead persistent daemons ──
        registry = self._spell_gate.DAEMON_REGISTRY
        for dk, info in fleet.items():
            if dk == self.SELF_KEY:
                continue
            spec = registry.get(dk)
            if spec and not spec.is_persistent:
                continue  # One-shot probes — don't resurrect
            status = info.get("status", "NEVER_SUMMONED")
            if status == "DEAD" and self.auto_summon:
                # Guard: only resurrect daemons that were previously alive
                # NEVER_SUMMONED = not Phoenix's job (operator must summon first)
                if status == "NEVER_SUMMONED":
                    continue
                if not self._check_feature_flag(dk):
                    continue  # Silent skip — no log entry for disabled daemons
                if self._is_on_cooldown(dk):
                    continue  # Silent skip on cooldown
                if not self.dry_run:
                    try:
                        receipt = self._spell_gate.spell_summon_familiar(dk, force=True, quiet=True)
                        action = receipt.get("status", "FAILED")
                        if receipt.get("alive"):
                            self._record_success(dk)
                        else:
                            self._record_fail(dk)
                        self._resurrections_total += 1
                        result["resurrections"].append({
                            "daemon": dk, "action": f"RESURRECTED:{action}",
                            "pid": receipt.get("pid", 0),
                        })
                    except Exception as e:
                        self._record_fail(dk)
                        result["resurrections"].append({
                            "daemon": dk, "action": "RESURRECTION_FAILED",
                            "error": str(e),
                        })
                else:
                    result["resurrections"].append({
                        "daemon": dk, "action": "DRY_RESURRECT",
                    })

        # ── 5. Write phoenix patrol event (ONLY if something happened) ──
        has_actions = any(
            r["action"] not in ("SKIP_ONE_SHOT", "SKIP_DISABLED", "COOLDOWN")
            for r in result["resurrections"]
        )
        if has_actions or result["errors"]:
            severity = "PHOENIX" if has_actions else "ERROR"
            write_p5_event(
                "hfo.gen89.p5.phoenix_patrol",
                f"P5-PHOENIX-C{self._cycle_count}",
                {
                    "severity": severity,
                    "cycle": self._cycle_count,
                    "fleet": result["fleet_status"],
                    "resurrections": result["resurrections"],
                    "singer_strife": result["singer_strife"],
                    "total_resurrections": self._resurrections_total,
                },
                dry_run=self.dry_run,
            )
        # Silent OK cycles: no event, no noise

        return result


# ═══════════════════════════════════════════════════════════════
# P5 Daemon Engine
# ═══════════════════════════════════════════════════════════════

class P5Daemon:
    """The P5 Pyre Praetorian 24/7 Governance Daemon.

    6 concurrent patrol tasks running on independent intervals.
    asyncio-based, single-process, signal-handled, state-persisted.
    T6 (Phoenix) checks the P7 Spell Gate fleet and auto-resurrects dead daemons.
    """

    def __init__(
        self,
        tasks: list[str] | None = None,
        dry_run: bool = False,
        once: bool = False,
        integrity_interval: int = 120,
        reaper_interval: int = 180,
        model_gov_interval: int = 300,
        anomaly_interval: int = 60,
        analyst_interval: int = 600,
        phoenix_interval: int = 120,
    ):
        self.dry_run = dry_run
        self.once = once
        self.running = False
        self.start_time: Optional[str] = None

        all_tasks = tasks or ["integrity", "reaper", "model_gov", "anomaly", "analyst", "phoenix"]
        self._tasks: dict[str, object] = {}
        self._intervals: dict[str, int] = {}

        if "integrity" in all_tasks:
            self._tasks["integrity"] = IntegrityPatrolTask(dry_run=dry_run)
            self._intervals["integrity"] = integrity_interval

        if "reaper" in all_tasks:
            self._tasks["reaper"] = OrphanReaperTask(dry_run=dry_run)
            self._intervals["reaper"] = reaper_interval

        if "model_gov" in all_tasks:
            self._tasks["model_gov"] = ModelGovernanceTask(dry_run=dry_run)
            self._intervals["model_gov"] = model_gov_interval

        if "anomaly" in all_tasks:
            self._tasks["anomaly"] = AnomalyPatrolTask(dry_run=dry_run)
            self._intervals["anomaly"] = anomaly_interval

        if "analyst" in all_tasks:
            self._tasks["analyst"] = PolicyAnalystTask(dry_run=dry_run)
            self._intervals["analyst"] = analyst_interval

        if "phoenix" in all_tasks:
            auto_summon = os.environ.get("HFO_SPELL_GATE_AUTO_SUMMON", "true").lower() not in ("false", "0")
            boot_summon = os.environ.get("HFO_DAEMON_P5_BOOT_SUMMON_FLEET", "false").lower() in ("true", "1")
            phoenix_int = int(os.environ.get("HFO_DAEMON_P5_PHOENIX_INTERVAL_S", str(phoenix_interval)))
            self._tasks["phoenix"] = SpellGatePhoenixTask(
                dry_run=dry_run, auto_summon=auto_summon, boot_summon_fleet=boot_summon,
            )
            self._intervals["phoenix"] = phoenix_int

    def _save_state(self):
        """Persist daemon state to disk."""
        state = {
            "pid": os.getpid(),
            "start_time": self.start_time,
            "running": self.running,
            "daemon": "P5 Pyre Praetorian",
            "version": "v1.0",
            "tasks": list(self._tasks.keys()),
            "intervals": self._intervals,
            "dry_run": self.dry_run,
            "ollama_model": P5_MODEL,
            "gemini_available": GEMINI_AVAILABLE,
            "watchdog_available": WATCHDOG_AVAILABLE,
            "last_update": _now_iso(),
        }
        try:
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass  # Non-fatal

    def _print_banner(self):
        print("=" * 64)
        print("  P5 PYRE PRAETORIAN -- 24/7 GOVERNANCE DAEMON")
        print("  Dancer of Death and Dawn | Port: P5 | IMMUNIZE")
        print("  Spell: CONTINGENCY (Evocation) | Trigram: Li (Fire)")
        print("  Phoenix Protocol: DANCE_OF_DEATH_AND_REBIRTH")
        print("=" * 64)
        print(f"  Root:          {HFO_ROOT}")
        print(f"  SSOT:          {DB_PATH}")
        print(f"  Ollama:        {OLLAMA_BASE}")
        print(f"  P5 Model:      {P5_MODEL}")
        print(f"  Gemini:        {'CONNECTED' if GEMINI_AVAILABLE else 'NOT AVAILABLE'}")
        print(f"  Watchdog:      {'LOADED' if WATCHDOG_AVAILABLE else 'IMPORT FAILED'}")
        phoenix_task = self._tasks.get("phoenix")
        gate_loaded = getattr(phoenix_task, "_spell_gate", None) is not None if phoenix_task else False
        print(f"  Spell Gate:    {'LINKED' if gate_loaded else 'NOT LOADED'}")
        print(f"  Auto-summon:   {getattr(phoenix_task, 'auto_summon', False) if phoenix_task else 'N/A'}")
        print(f"  Boot-summon:   {getattr(phoenix_task, 'boot_summon_fleet', False) if phoenix_task else 'N/A'}")
        print(f"  Mode:          {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"  Run mode:      {'ONE-SHOT' if self.once else 'CONTINUOUS'}")
        print(f"  Tasks:         {', '.join(self._tasks.keys()) or 'none'}")
        print()
        for name, interval in self._intervals.items():
            print(f"    {name:14s} every {interval:>5d}s ({interval // 60}m {interval % 60}s)")
        print()
        if not self.once:
            print("  Press Ctrl+C to stop gracefully.")
        print("  You cannot kill what regenerates from ashes.")
        print("=" * 64)
        print()

    async def _run_task_loop(self, name: str, task, interval: int):
        """Run a single patrol task on a recurring interval."""
        while self.running:
            try:
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"  [{ts}] [P5] {name}...", flush=True)

                result = await task.run_once()

                ts2 = datetime.now(timezone.utc).strftime("%H:%M:%S")
                status = json.dumps(result, default=str)[:120]
                print(f"  [{ts2}] OK {name} -> {status}", flush=True)

                self._save_state()

            except Exception as e:
                ts2 = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"  [{ts2}] FAIL {name} ERROR: {e}", file=sys.stderr, flush=True)
                traceback.print_exc(file=sys.stderr)

            if self.once:
                break

            # Wait for next cycle (interruptible)
            for _ in range(interval):
                if not self.running:
                    break
                await asyncio.sleep(1)

    async def run(self):
        """Start all patrol task loops."""
        self.running = True
        self.start_time = _now_iso()

        self._print_banner()
        self._save_state()

        if not self._tasks:
            print("  No tasks configured. Nothing to do.")
            return

        # Log daemon start
        write_p5_event(
            "hfo.gen89.p5.daemon_start",
            "P5-DAEMON-LIFECYCLE",
            {
                "action": "daemon_start",
                "tasks": list(self._tasks.keys()),
                "intervals": self._intervals,
                "pid": os.getpid(),
                "mode": "one-shot" if self.once else "continuous",
                "dry_run": self.dry_run,
                "p5_model": P5_MODEL,
                "gemini_available": GEMINI_AVAILABLE,
            },
            dry_run=self.dry_run,
        )

        # Launch all task loops concurrently
        loops = []
        for name, task in self._tasks.items():
            interval = self._intervals[name]
            loops.append(self._run_task_loop(name, task, interval))

        try:
            await asyncio.gather(*loops)
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            self._save_state()

            # Log daemon stop
            write_p5_event(
                "hfo.gen89.p5.daemon_stop",
                "P5-DAEMON-LIFECYCLE",
                {
                    "action": "daemon_stop",
                    "start_time": self.start_time,
                    "stop_time": _now_iso(),
                    "pid": os.getpid(),
                },
                dry_run=self.dry_run,
            )

            print("\n  P5 Pyre Praetorian daemon stopped. The ashes remember.")

    def stop(self):
        """Signal graceful shutdown."""
        self.running = False


# ═══════════════════════════════════════════════════════════════
# Status Command
# ═══════════════════════════════════════════════════════════════

def show_status():
    """Show P5 daemon status."""
    print("=" * 64)
    print("  P5 PYRE PRAETORIAN — DAEMON STATUS")
    print("=" * 64)

    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            print(f"  PID:           {state.get('pid', '?')}")
            print(f"  Running:       {state.get('running', False)}")
            print(f"  Started:       {state.get('start_time', '?')}")
            print(f"  Last update:   {state.get('last_update', '?')}")
            print(f"  Tasks:         {', '.join(state.get('tasks', []))}")
            print(f"  P5 Model:      {state.get('ollama_model', '?')}")
            print(f"  Gemini:        {state.get('gemini_available', False)}")
            print(f"  Watchdog:      {state.get('watchdog_available', False)}")
            print(f"  Dry run:       {state.get('dry_run', False)}")
            print()
            for task, interval in state.get("intervals", {}).items():
                print(f"    {task:14s} every {interval}s")
        except (json.JSONDecodeError, OSError):
            print("  State file corrupted.")
    else:
        print("  No daemon state found.")
        print("  Start with: python hfo_p5_daemon.py")

    # Recent P5 daemon events
    if DB_PATH.exists():
        try:
            conn = get_db_readonly()
            events = conn.execute(
                """SELECT event_type, timestamp, subject
                   FROM stigmergy_events
                   WHERE event_type LIKE '%p5.daemon%' OR event_type LIKE '%p5.integrity%'
                         OR event_type LIKE '%p5.reaper%' OR event_type LIKE '%p5.anomaly%'
                         OR event_type LIKE '%p5.model_gov%' OR event_type LIKE '%p5.policy%'
                         OR event_type LIKE '%p5.phoenix%'
                   ORDER BY id DESC LIMIT 15"""
            ).fetchall()
            conn.close()

            if events:
                print(f"\n  Recent P5 daemon events:")
                for e in events:
                    print(f"    {e['timestamp'][:19]}  {e['event_type']:45s}  {e['subject']}")
            else:
                print("\n  No P5 daemon events found yet.")
        except Exception:
            pass

    print("=" * 64)


# ═══════════════════════════════════════════════════════════════
# Windows Scheduled Task Installer
# ═══════════════════════════════════════════════════════════════

def install_schedule():
    """Install a Windows Scheduled Task for P5 Phoenix daemon with boot persistence.

    Creates TWO tasks:
      1. HFO_P5_PyrePraetorian_Boot — runs continuous P5 daemon at logon (with phoenix)
      2. HFO_P5_PyrePraetorian_Patrol — runs --once patrol every 5 min as safety net

    The boot task starts P5 as a continuous daemon with phoenix enabled.
    Phoenix will auto-summon the fleet (singer, tremorsense, etc.) at startup.
    The patrol task is a safety net — if the continuous daemon dies, 
    the patrol still runs independently.
    """
    script_path = Path(__file__).resolve()
    python_path = sys.executable

    # Task 1: Boot-trigger continuous daemon
    boot_xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>HFO P5 Pyre Praetorian — Phoenix daemon starts at logon, resurrects fleet</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <Hidden>false</Hidden>
    <RestartOnFailure>
      <Interval>PT5M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions>
    <Exec>
      <Command>{python_path}</Command>
      <Arguments>-u "{script_path}" --tasks integrity,reaper,model_gov,anomaly,phoenix</Arguments>
      <WorkingDirectory>{HFO_ROOT}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    # Task 2: Periodic patrol safety net (every 5 min, --once)
    patrol_xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>HFO P5 Pyre Praetorian — one-shot patrol every 5 min (safety net)</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>PT5M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>{python_path}</Command>
      <Arguments>-u "{script_path}" --once --tasks integrity,phoenix</Arguments>
      <WorkingDirectory>{HFO_ROOT}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    # Write XMLs
    boot_xml_path = HFO_ROOT / ".hfo_p5_boot_task.xml"
    patrol_xml_path = HFO_ROOT / ".hfo_p5_patrol_task.xml"
    boot_xml_path.write_text(boot_xml, encoding="utf-16")
    patrol_xml_path.write_text(patrol_xml, encoding="utf-16")

    print("  " + "=" * 64)
    print("  P5 PYRE PRAETORIAN — WINDOWS TASK SCHEDULER SETUP")
    print("  " + "=" * 64)
    print()
    print(f"  Boot task XML:    {boot_xml_path}")
    print(f"  Patrol task XML:  {patrol_xml_path}")
    print()

    # Try to auto-install (needs admin for some operations, but try anyway)
    installed = 0
    for task_name, xml_path, desc in [
        ("HFO_P5_PyrePraetorian_Boot", boot_xml_path, "Boot daemon"),
        ("HFO_P5_PyrePraetorian_Patrol", patrol_xml_path, "Patrol safety net"),
    ]:
        try:
            result = subprocess.run(
                ["schtasks", "/Create", "/TN", task_name, "/XML", str(xml_path), "/F"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                print(f"  >>> INSTALLED: {task_name} ({desc})")
                installed += 1
            else:
                print(f"  WARN: {task_name} — auto-install failed: {result.stderr.strip()}")
                print(f"    Manual install: schtasks /Create /TN \"{task_name}\" /XML \"{xml_path}\"")
        except Exception as e:
            print(f"  WARN: {task_name} — {e}")
            print(f"    Manual install: schtasks /Create /TN \"{task_name}\" /XML \"{xml_path}\"")

    print()
    if installed == 2:
        print("  Both tasks installed. P5 will survive reboot.")
    else:
        print("  If auto-install failed, run from elevated PowerShell:")
        print(f"    schtasks /Create /TN \"HFO_P5_PyrePraetorian_Boot\" /XML \"{boot_xml_path}\" /F")
        print(f"    schtasks /Create /TN \"HFO_P5_PyrePraetorian_Patrol\" /XML \"{patrol_xml_path}\" /F")
    print()
    print("  To remove:")
    print("    schtasks /Delete /TN \"HFO_P5_PyrePraetorian_Boot\" /F")
    print("    schtasks /Delete /TN \"HFO_P5_PyrePraetorian_Patrol\" /F")
    print()
    print("  The Phoenix remembers. You cannot kill what regenerates from ashes.")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P5 Pyre Praetorian — 24/7 Governance Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tasks",
        default="integrity,reaper,model_gov,anomaly,analyst,phoenix",
        help="Comma-separated tasks (default: all 6 including phoenix)",
    )
    parser.add_argument("--once", action="store_true",
                        help="Run one patrol cycle then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect but don't write to SSOT")
    parser.add_argument("--status", action="store_true",
                        help="Show daemon status and exit")
    parser.add_argument("--install-schedule", action="store_true",
                        help="Create + install Windows scheduled tasks (boot + patrol)")

    # Intervals
    parser.add_argument("--integrity-interval", type=int, default=120)
    parser.add_argument("--reaper-interval", type=int, default=180)
    parser.add_argument("--model-gov-interval", type=int, default=300)
    parser.add_argument("--anomaly-interval", type=int, default=60)
    parser.add_argument("--analyst-interval", type=int, default=600)
    parser.add_argument("--phoenix-interval", type=int, default=120)

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.install_schedule:
        install_schedule()
        return

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]

    daemon = P5Daemon(
        tasks=tasks,
        dry_run=args.dry_run,
        once=args.once,
        integrity_interval=args.integrity_interval,
        reaper_interval=args.reaper_interval,
        model_gov_interval=args.model_gov_interval,
        anomaly_interval=args.anomaly_interval,
        analyst_interval=args.analyst_interval,
        phoenix_interval=args.phoenix_interval,
    )

    # Graceful shutdown via Ctrl+C
    def _signal_handler(sig, frame):
        print("\n  [P5] Shutdown signal received...", flush=True)
        daemon.stop()

    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)

    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
