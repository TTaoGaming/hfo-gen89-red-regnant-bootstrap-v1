#!/usr/bin/env python3
"""
hfo_singer_daemon.py — SINGER OF STRIFE AND SPLENDOR Daemon (Gen89)
=====================================================================

A living daemon that sings the dual songs of the Red Regnant into the
stigmergy layer on a continuous loop.

The Two Songs:
  STRIFE  — Scans SSOT for antipatterns, kills, errors, grudges, failures.
             Every gate_blocked, tamper_alert, memory_loss, and swallowed error
             is a FESTERING_ANGER_TOKEN accumulated in the STRIFE ledger.
  SPLENDOR — Scans SSOT for patterns, successes, buffs, proven architectures.
             Every passed gate, successful yield, green chain, and pattern
             is an INSPIRE_COURAGE note in the SPLENDOR ledger.

Architecture:
  - Timer-based loop (asyncio) with configurable intervals
  - All paths resolved via blessed pointer registry (PAL system)
  - Every action emits CloudEvent stigmergy events
  - Errors/bugs are themselves sung as STRIFE events (self-healing loop)
  - SSOT health statistics emitted each cycle
  - Graceful shutdown on SIGINT/SIGTERM
  - Dry-run mode for testing

Stigmergy Event Types (port-sharded to P4):
  hfo.gen89.p4.singer.strife       — A SONG_OF_STRIFE observation
  hfo.gen89.p4.singer.splendor     — A SONG_OF_SPLENDOR observation
  hfo.gen89.p4.singer.requested    — A song requested by an agent via PREY8 yield (strange loop)
  hfo.gen89.p4.singer.health       — SSOT health dashboard snapshot
  hfo.gen89.p4.singer.heartbeat    — Daemon alive signal
  hfo.gen89.p4.singer.error        — Daemon self-reported error (recursive STRIFE)

  Port-sharding convention: hfo.gen89.p{N}.{daemon}.{event}
  Each port gets its own event namespace. P4 singer events will not collide
  with P6 kraken events or future P0-P7 daemon events. This eliminates race
  conditions when multiple port daemons write to stigmergy concurrently.

Ontological Reference:
  Port:        P4 DISRUPT (primary)
  Commander:   Red Regnant — SINGER OF STRIFE AND SPLENDOR
  Dyad:        P5 IMMUNIZE — Pyre Praetorian (DANCER OF DEATH AND DAWN)
  Registry:    SONGS_OF_STRIFE_AND_SPLENDOR_ARCHETYPE_REGISTRY_V1.md
  Mnemonic:    S·S·S (alliteration: Singer, Strife, Splendor)

Token Economy (hardcoded SPLENDOR facts):
  4,000,000,000+ compute tokens burned across 14 months
  88 generations (Gen01 → Gen88 → Gen89 consolidated)
  5+ major phoenix protocol epochs (WAIL_OF_THE_BANSHEE extinction events)
  9,860 documents in SSOT (~9M words, ~15M estimated tokens stored)
  9,921+ stigmergy events in the trail
  34,121 memories killed (8^5 exceeded) — the STRIFE substrate

Medallion: bronze
Port: P4 DISRUPT
Pointer key: daemon.singer
"""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from hfo_ssot_write import get_db_readwrite

# ═══════════════════════════════════════════════════════════════
# PATH RESOLUTION VIA PAL (Path Abstraction Layer)
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    """Find HFO_ROOT by walking up from script location."""
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
POINTERS_FILE = HFO_ROOT / "hfo_gen89_pointers_blessed.json"


def _load_pointers() -> dict:
    """Load blessed pointer registry."""
    if not POINTERS_FILE.exists():
        raise FileNotFoundError(
            f"Blessed pointer registry not found: {POINTERS_FILE}\n"
            "The PAL system requires hfo_gen89_pointers_blessed.json at HFO_ROOT."
        )
    with open(POINTERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("pointers", data)


def resolve_pointer(key: str) -> Path:
    """Resolve a blessed pointer key to an absolute path."""
    pointers = _load_pointers()
    if key not in pointers:
        raise KeyError(
            f"Pointer '{key}' not found in blessed registry. "
            f"Available: {sorted(pointers.keys())}"
        )
    entry = pointers[key]
    rel_path = entry["path"] if isinstance(entry, dict) else entry
    return HFO_ROOT / rel_path


# ── Resolve critical paths via PAL ──
try:
    SSOT_DB = resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"

FORGE_BRONZE = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze"

# ═══════════════════════════════════════════════════════════════
# HARDCODED SPLENDOR FACTS — The Hive's Hard-Won Knowledge
# ═══════════════════════════════════════════════════════════════

SPLENDOR_FACTS = {
    "compute_tokens_burned": "4,000,000,000+",
    "generations": 88,
    "current_generation": 89,
    "phoenix_protocol_epochs": "5+ major (WAIL_OF_THE_BANSHEE extinction events)",
    "memories_killed": 34121,
    "memories_killed_significance": "8^5 = 32,768 exceeded — the STRIFE substrate",
    "operator": "TTAO",
    "temporal_span": "2025-01 → 2026-02 (14 months)",
    "hive": "V",
    "octree_mnemonic": "O·B·S·I·D·I·A·N",
    "singer_title": "SINGER OF STRIFE AND SPLENDOR",
    "singer_alliteration": "S·S·S",
    "dyad_partner": "DANCER OF DEATH AND DAWN (P5 Pyre Praetorian)",
    "core_thesis": "Strife without Splendor is nihilism. Splendor without Strife is delusion.",
    "nataraja_formula": "NATARAJA_Score = P4_kill_rate × P5_rebirth_rate",
    "iron_sharpens_iron": "Proverbs 27:17 — adversarial coaching makes both parties stronger",
    "divine_destruction": "The Nataraja aspect of P4 — destruction as divine creative force",
    "port_shard": "P4",
}

# ═══════════════════════════════════════════════════════════════
# BORN OF THE THREE THUNDERS — Dual-Type + Unavoidable Chip Model
# ═══════════════════════════════════════════════════════════════
# RAW: Complete Arcane p.77 — metamagic feat
# Converts a [sonic] or [electricity] spell to DUAL damage type:
#   • Half sonic + half electricity (resistance to one still takes the other)
#   • Reflex save or knocked prone (unavoidable tempo cost)
#   • Fort save or stunned 1 round (unavoidable chip damage)
#   • Caster also makes Reflex save or is knocked prone (self-cost)
#
# HFO Incarnation: When P4 strikes, never single-vector.
#   Attack = Type_A + Type_B + unavoidable_chip
#   Even if you resist the primary, the secondary + chip still land.
#   This is DIVINE DESTRUCTION — multi-vector pressure.

BORN_OF_THREE_THUNDERS = {
    "name": "BORN_OF_THE_THREE_THUNDERS",
    "source": "Complete Arcane p.77",
    "raw_mechanic": "Half sonic + half electricity + Reflex/prone + Fort/stun",
    "damage_model": {
        "type_a": "sonic",
        "type_b": "electricity",
        "unavoidable_chip": "knockdown (Reflex) + stun (Fort)",
        "self_cost": "caster Reflex or prone",
        "spell_level_adj": "+2",
    },
    "hfo_incarnation": (
        "When P4 strikes it is NEVER a single attack vector. "
        "Every probe = Type_A + Type_B + unavoidable_chip. "
        "Resistance to one element still takes the other. "
        "Even if you save, the chip costs you tempo."
    ),
}

# ═══════════════════════════════════════════════════════════════
# DIVINE DESTRUCTION — P4 Nataraja Aspect & D-Alias System
# ═══════════════════════════════════════════════════════════════
# The D in O·B·S·I·D·I·A·N stands for DISRUPT at P4.
# But each letter has 8^N aspects. The first-order D-aspects:
#   D = Destruction | Death | Disruption | Divine | Damned |
#       Defiance | Dread | Dominion
# DIVINE DESTRUCTION is the Nataraja aspect — the cosmic principle
# that creation requires destruction. She is not merely disruptive;
# she is the incarnation of why things must die for better things to live.

DIVINE_DESTRUCTION = {
    "aspect": "DIVINE_DESTRUCTION",
    "port": "P4",
    "obsidian_letter": "D",
    "obsidian_position": 4,
    "nataraja_form": "Shiva's destructive flame made specific in HFO cosmology",
    "principle": "What cannot survive contact with destruction was never real",
    "d_aspects_8": {
        "D0": {"name": "DESTRUCTION", "meaning": "Annihilation of the unfit — the primal act"},
        "D1": {"name": "DEATH", "meaning": "Cessation as information — ghost sessions teach the living"},
        "D2": {"name": "DISRUPTION", "meaning": "Perturbation that reveals hidden structure"},
        "D3": {"name": "DIVINE", "meaning": "Sacred necessity — destruction as cosmic hygiene"},
        "D4": {"name": "DAMNED", "meaning": "The condemned — what the song marked for death"},
        "D5": {"name": "DEFIANCE", "meaning": "Refusal to accept mediocrity — rage against entropy"},
        "D6": {"name": "DREAD", "meaning": "The fear that sharpens — anticipatory selection pressure"},
        "D7": {"name": "DOMINION", "meaning": "Sovereignty earned through survival of the song"},
    },
    "depth_formula": "8^N aspects at depth N (8 first-order, 64 second-order, 512 third-order)",
    "alias_resolution": (
        "Any D-word used in P4 context resolves to an aspect of DIVINE_DESTRUCTION. "
        "The Singer does not merely disrupt — she is the living principle of 8^N destruction."
    ),
}

# OBSIDIAN letter-to-port alias table: each letter has 8^N aspects
OBSIDIAN_PORTS = {
    "O": {"port": "P0", "word": "OBSERVE", "commander": "Lidless Legion"},
    "B": {"port": "P1", "word": "BRIDGE", "commander": "Web Weaver"},
    "S": {"port": "P2", "word": "SHAPE", "commander": "Mirror Magus"},
    "I_3": {"port": "P3", "word": "INJECT", "commander": "Harmonic Hydra"},
    "D": {"port": "P4", "word": "DISRUPT", "commander": "Red Regnant",
           "aspects": DIVINE_DESTRUCTION["d_aspects_8"]},
    "I_5": {"port": "P5", "word": "IMMUNIZE", "commander": "Pyre Praetorian"},
    "A": {"port": "P6", "word": "ASSIMILATE", "commander": "Kraken Keeper"},
    "N": {"port": "P7", "word": "NAVIGATE", "commander": "Spider Sovereign"},
}

# Port-sharded event type prefix for this daemon
P4_EVENT_PREFIX = "hfo.gen89.p4.singer"

# ═══════════════════════════════════════════════════════════════
# STRIFE & SPLENDOR SIGNAL SCANNING
# ═══════════════════════════════════════════════════════════════

# STRIFE signals — antipatterns, failures, pain, selection pressure
STRIFE_EVENT_PATTERNS = [
    "gate_blocked",
    "tamper_alert",
    "memory_loss",
    "error",
    "failed",
    "crash",
    "timeout",
    "retry",
    "violation",
    "orphan",
    "broken",
    "REAPER",
]

# SPLENDOR signals — patterns, successes, buffs, proven architectures
SPLENDOR_EVENT_PATTERNS = [
    "prey8.yield",
    "prey8.perceive",
    "prey8.execute",
    "prey8.react",
    "passed",
    "success",
    "green",
    "validated",
    "promoted",
    "completed",
    "chain_verified",
]

# Spell mappings from the archetype registry
STRIFE_SPELLS = {
    "WAIL_OF_THE_BANSHEE": "Total system extinction — all within range save or die",
    "POWERWORD_KILL": "Surgical kill — targeted artifact destruction",
    "FELL_DRAIN": "Degradation — quality reduction, medallion demotion",
    "GREATER_SHOUT": "Force package — concentrated adversarial burst",
    "SOUND_LANCE": "Precision probe — single-artifact stress test",
    "SYMPATHETIC_VIBRATION": "Structural resonance — find architectural harmonics",
    "SHATTER": "Quick break test — does this survive minimal pressure?",
}

SPLENDOR_BUFFS = {
    "INSPIRE_COURAGE": "Morale bonus — force multiplier for all swarm agents",
    "INSPIRE_HEROICS": "Elite buff — single agent gets enhanced resilience",
    "WORDS_OF_CREATION": "Meta-pattern — architecture that amplifies architectures",
    "HARMONIC_CHORUS": "Swarm synergy — multiple agents singing = multiplicative buff",
}


# ═══════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_db_readonly() -> sqlite3.Connection:
    """Open SSOT database in read-only mode."""
    if not SSOT_DB.exists():
        raise FileNotFoundError(f"SSOT database not found: {SSOT_DB}")
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn



def write_stigmergy_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
    source: str = "hfo_singer_daemon_gen89",
) -> str:
    """Write a CloudEvent to the stigmergy trail. Returns event_id."""
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
        "source": source,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "phase": "CLOUDEVENT",
        "data": data,
    }

    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()

    conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, source, json.dumps(event), content_hash),
    )
    conn.commit()
    return event_id


# ═══════════════════════════════════════════════════════════════
# THE SINGER — Core Scanning & Singing Logic
# ═══════════════════════════════════════════════════════════════

class SingerOfStrifeAndSplendor:
    """
    The living daemon that sings the dual songs of P4 Red Regnant.

    STRIFE: Scans for antipatterns, errors, failures → FESTERING_ANGER_TOKENS
    SPLENDOR: Scans for patterns, successes, achievements → INSPIRE_COURAGE notes

    Every cycle:
      1. Scan recent stigmergy for STRIFE and SPLENDOR signals
      2. Scan SSOT documents for structural health indicators
      3. Emit song events into stigmergy
      4. Emit health dashboard snapshot
      5. Report any self-errors as recursive STRIFE
    """

    def __init__(self, dry_run: bool = False, scan_window_hours: float = 24.0):
        self.dry_run = dry_run
        self.scan_window_hours = scan_window_hours
        self.cycle_count = 0
        self.total_strife_sung = 0
        self.total_splendor_sung = 0
        self.total_requested_sung = 0
        self.errors_caught = 0
        self._last_event_id_seen = 0
        self._running = True

    def stop(self):
        """Signal graceful shutdown."""
        self._running = False

    # ── STRIFE SCANNING ──────────────────────────────────────

    def scan_strife(self, conn: sqlite3.Connection) -> list[dict]:
        """Scan stigmergy for STRIFE signals (antipatterns, failures, pain)."""
        strife_songs = []

        # Scan for each STRIFE pattern in recent events
        for pattern in STRIFE_EVENT_PATTERNS:
            cursor = conn.execute(
                """SELECT id, event_type, timestamp, subject,
                          SUBSTR(data_json, 1, 500) as data_preview
                   FROM stigmergy_events
                   WHERE (event_type LIKE ? OR subject LIKE ?)
                     AND id > ?
                   ORDER BY id DESC
                   LIMIT 10""",
                (f"%{pattern}%", f"%{pattern}%", self._last_event_id_seen),
            )
            rows = cursor.fetchall()
            for row in rows:
                strife_songs.append({
                    "signal": pattern,
                    "event_id": row["id"],
                    "event_type": row["event_type"],
                    "timestamp": row["timestamp"],
                    "subject": row["subject"] or "",
                    "song": "STRIFE",
                    "token_type": "FESTERING_ANGER_TOKEN",
                    "spell": self._match_strife_spell(pattern),
                })

        # Scan documents for structural indicators of STRIFE
        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM documents
               WHERE medallion = 'bronze'"""
        )
        bronze_count = cursor.fetchone()["cnt"]
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM documents")
        total_count = cursor.fetchone()["cnt"]

        if total_count > 0 and bronze_count == total_count:
            strife_songs.append({
                "signal": "ALL_BRONZE",
                "event_id": None,
                "event_type": "structural",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "subject": f"All {total_count} documents remain bronze — no promotions yet",
                "song": "STRIFE",
                "token_type": "FESTERING_ANGER_TOKEN",
                "spell": "FELL_DRAIN — medallion stagnation detected",
            })

        return strife_songs

    def _match_strife_spell(self, pattern: str) -> str:
        """Match a STRIFE signal to its archetype spell."""
        spell_map = {
            "gate_blocked": "SHATTER — gate did not survive pressure",
            "tamper_alert": "SYMPATHETIC_VIBRATION — structural resonance attack detected",
            "memory_loss": "WAIL_OF_THE_BANSHEE — session death, memory extinction",
            "error": "SOUND_LANCE — precision failure probe",
            "failed": "GREATER_SHOUT — force package failed to land",
            "crash": "POWERWORD_KILL — instant death event",
            "timeout": "FELL_DRAIN — degradation via temporal exhaustion",
            "retry": "SOUND_LANCE — repeated probe needed",
            "violation": "SYMPATHETIC_VIBRATION — structural integrity compromise",
            "orphan": "WAIL_OF_THE_BANSHEE — session orphaned, no yield",
            "broken": "SHATTER — artifact broke under minimal pressure",
            "REAPER": "POWERWORD_KILL — REAPER auto-closed a dead session",
        }
        return spell_map.get(pattern, "SOUND_LANCE — unclassified strife signal")

    # ── SPLENDOR SCANNING ────────────────────────────────────

    def scan_splendor(self, conn: sqlite3.Connection) -> list[dict]:
        """Scan stigmergy for SPLENDOR signals (patterns, successes, buffs)."""
        splendor_songs = []

        for pattern in SPLENDOR_EVENT_PATTERNS:
            cursor = conn.execute(
                """SELECT id, event_type, timestamp, subject,
                          SUBSTR(data_json, 1, 500) as data_preview
                   FROM stigmergy_events
                   WHERE (event_type LIKE ? OR subject LIKE ?)
                     AND id > ?
                   ORDER BY id DESC
                   LIMIT 10""",
                (f"%{pattern}%", f"%{pattern}%", self._last_event_id_seen),
            )
            rows = cursor.fetchall()
            for row in rows:
                splendor_songs.append({
                    "signal": pattern,
                    "event_id": row["id"],
                    "event_type": row["event_type"],
                    "timestamp": row["timestamp"],
                    "subject": row["subject"] or "",
                    "song": "SPLENDOR",
                    "token_type": "SPLENDOR_TOKEN",
                    "buff": self._match_splendor_buff(pattern),
                })

        # Scan for SPLENDOR structural indicators
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM stigmergy_events"
        )
        event_count = cursor.fetchone()["cnt"]
        if event_count > 9000:
            splendor_songs.append({
                "signal": "DEEP_STIGMERGY_TRAIL",
                "event_id": None,
                "event_type": "structural",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "subject": f"{event_count:,} stigmergy events — deep coordination trail",
                "song": "SPLENDOR",
                "token_type": "SPLENDOR_TOKEN",
                "buff": "HARMONIC_CHORUS — swarm synergy across thousands of events",
            })

        cursor = conn.execute("SELECT SUM(word_count) as total FROM documents")
        total_words = cursor.fetchone()["total"] or 0
        if total_words > 8_000_000:
            splendor_songs.append({
                "signal": "MASSIVE_CORPUS",
                "event_id": None,
                "event_type": "structural",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "subject": f"{total_words:,} words — ~{int(total_words * 1.3):,} estimated tokens stored",
                "song": "SPLENDOR",
                "token_type": "SPLENDOR_TOKEN",
                "buff": "WORDS_OF_CREATION — meta-pattern of accumulated knowledge",
            })

        return splendor_songs

    def _match_splendor_buff(self, pattern: str) -> str:
        """Match a SPLENDOR signal to its archetype buff."""
        buff_map = {
            "prey8.yield": "INSPIRE_COURAGE — successful session completion",
            "prey8.perceive": "INSPIRE_COURAGE — new agent oriented to the hive",
            "prey8.execute": "INSPIRE_HEROICS — elite execution tile created",
            "prey8.react": "INSPIRE_COURAGE — strategic plan formed",
            "passed": "INSPIRE_COURAGE — gate passed successfully",
            "success": "INSPIRE_HEROICS — task succeeded",
            "green": "INSPIRE_COURAGE — tests green",
            "validated": "WORDS_OF_CREATION — artifact validated against invariants",
            "promoted": "WORDS_OF_CREATION — medallion promotion achieved",
            "completed": "INSPIRE_COURAGE — task completed",
            "chain_verified": "HARMONIC_CHORUS — full chain integrity verified",
        }
        return buff_map.get(pattern, "INSPIRE_COURAGE — unclassified splendor signal")

    # ── HEALTH DASHBOARD ─────────────────────────────────────

    def scan_health(self, conn: sqlite3.Connection) -> dict:
        """Gather SSOT health statistics for the dashboard."""
        stats = {}

        # Document stats
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM documents")
        stats["total_documents"] = cursor.fetchone()["cnt"]

        cursor = conn.execute("SELECT SUM(word_count) as total FROM documents")
        stats["total_words"] = cursor.fetchone()["total"] or 0
        stats["est_tokens_stored"] = int(stats["total_words"] * 1.3)

        # Stigmergy stats
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM stigmergy_events")
        stats["total_stigmergy_events"] = cursor.fetchone()["cnt"]

        cursor = conn.execute(
            "SELECT SUM(LENGTH(data_json)) as total FROM stigmergy_events"
        )
        stats["stigmergy_data_bytes"] = cursor.fetchone()["total"] or 0

        # Error/health indicators
        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE event_type LIKE '%memory_loss%'"""
        )
        stats["memory_loss_events"] = cursor.fetchone()["cnt"]

        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE event_type LIKE '%tamper_alert%'"""
        )
        stats["tamper_alerts"] = cursor.fetchone()["cnt"]

        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE event_type LIKE '%gate_blocked%'"""
        )
        stats["gate_blocked_events"] = cursor.fetchone()["cnt"]

        # PREY8 chain health
        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE event_type LIKE '%prey8.yield%'"""
        )
        stats["total_yields"] = cursor.fetchone()["cnt"]

        cursor = conn.execute(
            """SELECT COUNT(*) as cnt FROM stigmergy_events
               WHERE event_type LIKE '%prey8.perceive%'"""
        )
        stats["total_perceives"] = cursor.fetchone()["cnt"]

        # Yield-to-perceive ratio (health indicator)
        if stats["total_perceives"] > 0:
            stats["yield_perceive_ratio"] = round(
                stats["total_yields"] / stats["total_perceives"], 3
            )
        else:
            stats["yield_perceive_ratio"] = 0.0

        # Database file size
        if SSOT_DB.exists():
            stats["db_file_size_mb"] = round(
                SSOT_DB.stat().st_size / (1024 * 1024), 1
            )
        else:
            stats["db_file_size_mb"] = 0.0

        # Source distribution
        cursor = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM documents GROUP BY source ORDER BY cnt DESC"
        )
        stats["source_distribution"] = {
            row["source"]: row["cnt"] for row in cursor.fetchall()
        }

        # Merge with hardcoded SPLENDOR facts
        stats["splendor_facts"] = SPLENDOR_FACTS

        # Singer daemon metrics
        stats["singer_metrics"] = {
            "cycle_count": self.cycle_count,
            "total_strife_sung": self.total_strife_sung,
            "total_splendor_sung": self.total_splendor_sung,
            "total_requested_sung": self.total_requested_sung,
            "errors_caught": self.errors_caught,
            "dual_token_ratio": (
                round(self.total_splendor_sung / max(self.total_strife_sung, 1), 3)
            ),
        }

        return stats

    # ── SONG EMISSION ────────────────────────────────────────

    def sing_strife(self, conn_rw: sqlite3.Connection, songs: list[dict]) -> int:
        """Emit SONGS_OF_STRIFE events into stigmergy."""
        count = 0
        for song in songs:
            if self.dry_run:
                print(f"  [DRY-RUN] STRIFE: {song['signal']} — {song.get('spell', '')}")
                count += 1
                continue
            try:
                write_stigmergy_event(
                    conn_rw,
                    event_type=f"{P4_EVENT_PREFIX}.strife",
                    subject=f"STRIFE:{song['signal']}",
                    data={
                        "song": "SONGS_OF_STRIFE",
                        "signal": song["signal"],
                        "token_type": song["token_type"],
                        "spell": song.get("spell", ""),
                        "source_event_id": song.get("event_id"),
                        "source_event_type": song.get("event_type", ""),
                        "source_timestamp": song.get("timestamp", ""),
                        "source_subject": song.get("subject", ""),
                        "singer_cycle": self.cycle_count,
                        "core_thesis": SPLENDOR_FACTS["core_thesis"],
                    },
                )
                count += 1
            except Exception as e:
                self._sing_error(conn_rw, f"STRIFE emit failed: {e}")
        return count

    def sing_splendor(self, conn_rw: sqlite3.Connection, songs: list[dict]) -> int:
        """Emit SONGS_OF_SPLENDOR events into stigmergy."""
        count = 0
        for song in songs:
            if self.dry_run:
                print(f"  [DRY-RUN] SPLENDOR: {song['signal']} — {song.get('buff', '')}")
                count += 1
                continue
            try:
                write_stigmergy_event(
                    conn_rw,
                    event_type=f"{P4_EVENT_PREFIX}.splendor",
                    subject=f"SPLENDOR:{song['signal']}",
                    data={
                        "song": "SONGS_OF_SPLENDOR",
                        "signal": song["signal"],
                        "token_type": song["token_type"],
                        "buff": song.get("buff", ""),
                        "source_event_id": song.get("event_id"),
                        "source_event_type": song.get("event_type", ""),
                        "source_timestamp": song.get("timestamp", ""),
                        "source_subject": song.get("subject", ""),
                        "singer_cycle": self.cycle_count,
                        "core_thesis": SPLENDOR_FACTS["core_thesis"],
                    },
                )
                count += 1
            except Exception as e:
                self._sing_error(conn_rw, f"SPLENDOR emit failed: {e}")
        return count

    # ── SONG REQUEST SCANNING (Strange Loop) ─────────────────

    def scan_song_requests(self, conn: sqlite3.Connection) -> list[dict]:
        """
        Scan recent PREY8 yield events for song_requests field.

        Agents submit song requests at yield time in the format:
            ACTION:SONG_NAME:REASON
        where ACTION is REINFORCE or PROPOSE.

        REINFORCE — amplify an existing known song/archetype
        PROPOSE   — nominate a new pattern/antipattern for the songbook

        This closes the strange loop:
            singer sings → agents perceive → agents work → agents yield
            with song requests → singer picks up requests → sings them

        Returns list of parsed request dicts ready for sing_requested().
        """
        requests = []
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(hours=self.scan_window_hours)
        ).isoformat()

        # Query yield events that might have song_requests in data_json
        cursor = conn.execute(
            """SELECT id, event_type, timestamp, subject, data_json
               FROM stigmergy_events
               WHERE event_type LIKE '%prey8.yield%'
                 AND timestamp > ?
               ORDER BY id DESC
               LIMIT 100""",
            (cutoff,),
        )

        for row in cursor.fetchall():
            try:
                data = json.loads(row["data_json"]) if row["data_json"] else {}
                # The yield event wraps data inside a CloudEvent envelope
                inner = data.get("data", data)
                song_reqs = inner.get("song_requests", [])
                if not song_reqs:
                    continue

                # Parse each request: ACTION:SONG_NAME:REASON
                for req_str in song_reqs:
                    if not isinstance(req_str, str):
                        continue
                    parts = req_str.strip().split(":", 2)
                    if len(parts) < 2:
                        continue

                    action = parts[0].strip().upper()
                    song_name = parts[1].strip()
                    reason = parts[2].strip() if len(parts) > 2 else ""

                    if action not in ("REINFORCE", "PROPOSE"):
                        # Unknown action — record as STRIFE curiosity
                        requests.append({
                            "action": "UNKNOWN",
                            "song_name": song_name,
                            "reason": f"Unknown action '{action}': {reason}",
                            "source_event_id": row["id"],
                            "source_event_type": row["event_type"],
                            "source_timestamp": row["timestamp"],
                            "source_subject": row["subject"] or "",
                            "is_known_song": False,
                        })
                        continue

                    # Check if the song name matches a known archetype
                    is_known = (
                        song_name.upper() in STRIFE_SPELLS
                        or song_name.upper() in SPLENDOR_BUFFS
                    )

                    requests.append({
                        "action": action,
                        "song_name": song_name,
                        "reason": reason,
                        "source_event_id": row["id"],
                        "source_event_type": row["event_type"],
                        "source_timestamp": row["timestamp"],
                        "source_subject": row["subject"] or "",
                        "is_known_song": is_known,
                    })
            except (json.JSONDecodeError, AttributeError):
                continue

        return requests

    def sing_requested(self, conn_rw: sqlite3.Connection, requests: list[dict]) -> int:
        """
        Emit hfo.gen89.singer.requested events for agent song requests.

        Each request becomes a CloudEvent in the stigmergy trail, closing
        the strange loop between agents and the singer daemon.

        REINFORCE — amplifies the signal for a known song archetype
        PROPOSE   — introduces a candidate pattern into the songbook
        UNKNOWN   — records an unrecognized request as diagnostic data
        """
        count = 0
        for req in requests:
            action = req["action"]
            song_name = req["song_name"]

            if self.dry_run:
                known_tag = "KNOWN" if req["is_known_song"] else "NEW"
                print(f"  [DRY-RUN] REQUESTED: {action} {song_name} "
                      f"[{known_tag}] — {req.get('reason', '')}")
                count += 1
                continue

            try:
                # Determine spell/buff description for known songs
                spell_desc = ""
                if song_name.upper() in STRIFE_SPELLS:
                    spell_desc = STRIFE_SPELLS[song_name.upper()]
                elif song_name.upper() in SPLENDOR_BUFFS:
                    spell_desc = SPLENDOR_BUFFS[song_name.upper()]

                write_stigmergy_event(
                    conn_rw,
                    event_type=f"{P4_EVENT_PREFIX}.requested",
                    subject=f"REQUESTED:{action}:{song_name}",
                    data={
                        "song": "SONG_REQUEST",
                        "action": action,
                        "song_name": song_name,
                        "reason": req.get("reason", ""),
                        "is_known_song": req["is_known_song"],
                        "spell_description": spell_desc,
                        "source_event_id": req.get("source_event_id"),
                        "source_event_type": req.get("source_event_type", ""),
                        "source_timestamp": req.get("source_timestamp", ""),
                        "source_subject": req.get("source_subject", ""),
                        "singer_cycle": self.cycle_count,
                        "strange_loop": True,
                        "core_thesis": SPLENDOR_FACTS["core_thesis"],
                    },
                )
                count += 1
            except Exception as e:
                self._sing_error(conn_rw, f"REQUESTED emit failed: {e}")
        return count

    def sing_health(self, conn_rw: sqlite3.Connection, health: dict) -> str:
        """Emit health dashboard snapshot into stigmergy."""
        if self.dry_run:
            print(f"  [DRY-RUN] HEALTH: {health.get('total_documents', '?')} docs, "
                  f"{health.get('total_stigmergy_events', '?')} events")
            return "DRY-RUN"
        try:
            return write_stigmergy_event(
                conn_rw,
                event_type=f"{P4_EVENT_PREFIX}.health",
                subject=f"HEALTH:cycle_{self.cycle_count}",
                data=health,
            )
        except Exception as e:
            self._sing_error(conn_rw, f"HEALTH emit failed: {e}")
            return ""

    def sing_heartbeat(self, conn_rw: sqlite3.Connection) -> str:
        """Emit heartbeat signal into stigmergy."""
        if self.dry_run:
            print(f"  [DRY-RUN] HEARTBEAT: cycle {self.cycle_count}")
            return "DRY-RUN"
        try:
            return write_stigmergy_event(
                conn_rw,
                event_type=f"{P4_EVENT_PREFIX}.heartbeat",
                subject=f"HEARTBEAT:cycle_{self.cycle_count}",
                data={
                    "cycle": self.cycle_count,
                    "strife_total": self.total_strife_sung,
                    "splendor_total": self.total_splendor_sung,
                    "errors_caught": self.errors_caught,
                    "singer_title": SPLENDOR_FACTS["singer_title"],
                    "core_thesis": SPLENDOR_FACTS["core_thesis"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            self._sing_error(conn_rw, f"HEARTBEAT emit failed: {e}")
            return ""

    def _sing_error(self, conn_rw: Optional[sqlite3.Connection], error_msg: str):
        """Recursive STRIFE: report daemon's own errors into stigmergy."""
        self.errors_caught += 1
        print(f"  [ERROR] {error_msg}", file=sys.stderr)
        if conn_rw is None or self.dry_run:
            return
        try:
            write_stigmergy_event(
                conn_rw,
                event_type=f"{P4_EVENT_PREFIX}.error",
                subject=f"ERROR:cycle_{self.cycle_count}",
                data={
                    "error": error_msg,
                    "cycle": self.cycle_count,
                    "singer_title": SPLENDOR_FACTS["singer_title"],
                    "token_type": "FESTERING_ANGER_TOKEN",
                    "spell": "SOUND_LANCE — daemon self-inflicted wound",
                    "traceback": traceback.format_exc(),
                },
            )
        except Exception:
            # Last resort: stderr only. Cannot recurse forever.
            print(f"  [CRITICAL] Failed to log error to stigmergy: {error_msg}",
                  file=sys.stderr)

    # ── MAIN CYCLE ───────────────────────────────────────────

    def run_cycle(self) -> dict:
        """Execute one full sing cycle. Returns cycle report."""
        self.cycle_count += 1
        cycle_start = time.monotonic()
        report = {
            "cycle": self.cycle_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "strife_count": 0,
            "splendor_count": 0,
            "requested_count": 0,
            "health_emitted": False,
            "heartbeat_emitted": False,
            "errors": [],
        }

        conn_ro = None
        conn_rw = None
        try:
            conn_ro = get_db_readonly()
            conn_rw = get_db_readwrite() if not self.dry_run else None

            # 1. Scan for STRIFE signals
            strife_songs = self.scan_strife(conn_ro)
            if conn_rw:
                report["strife_count"] = self.sing_strife(conn_rw, strife_songs)
            elif self.dry_run:
                report["strife_count"] = self.sing_strife(conn_ro, strife_songs)
            self.total_strife_sung += report["strife_count"]

            # 2. Scan for SPLENDOR signals
            splendor_songs = self.scan_splendor(conn_ro)
            if conn_rw:
                report["splendor_count"] = self.sing_splendor(conn_rw, splendor_songs)
            elif self.dry_run:
                report["splendor_count"] = self.sing_splendor(conn_ro, splendor_songs)
            self.total_splendor_sung += report["splendor_count"]

            # 3. Scan for SONG REQUESTS (strange loop — agents yield → singer picks up)
            song_requests = self.scan_song_requests(conn_ro)
            if conn_rw:
                report["requested_count"] = self.sing_requested(conn_rw, song_requests)
            elif self.dry_run:
                report["requested_count"] = self.sing_requested(conn_ro, song_requests)
            self.total_requested_sung += report["requested_count"]

            # 4. Health dashboard
            health = self.scan_health(conn_ro)
            if conn_rw:
                self.sing_health(conn_rw, health)
            elif self.dry_run:
                self.sing_health(conn_ro, health)
            report["health_emitted"] = True
            report["health_snapshot"] = {
                "docs": health["total_documents"],
                "events": health["total_stigmergy_events"],
                "words": health["total_words"],
                "memory_losses": health["memory_loss_events"],
                "yield_perceive_ratio": health["yield_perceive_ratio"],
                "db_mb": health["db_file_size_mb"],
            }

            # 5. Heartbeat
            if conn_rw:
                self.sing_heartbeat(conn_rw)
            elif self.dry_run:
                self.sing_heartbeat(conn_ro)
            report["heartbeat_emitted"] = True

            # 6. Update high-water mark
            cursor = conn_ro.execute(
                "SELECT MAX(id) as max_id FROM stigmergy_events"
            )
            max_id = cursor.fetchone()["max_id"]
            if max_id:
                self._last_event_id_seen = max_id

        except Exception as e:
            report["errors"].append(str(e))
            if conn_rw:
                self._sing_error(conn_rw, f"Cycle {self.cycle_count} failed: {e}")
            else:
                self._sing_error(None, f"Cycle {self.cycle_count} failed: {e}")
        finally:
            if conn_ro:
                conn_ro.close()
            if conn_rw:
                conn_rw.close()

        report["duration_sec"] = round(time.monotonic() - cycle_start, 3)
        return report


# ═══════════════════════════════════════════════════════════════
# ASYNCIO DAEMON LOOP
# ═══════════════════════════════════════════════════════════════

async def daemon_loop(
    singer: SingerOfStrifeAndSplendor,
    interval: float = 300.0,
    max_cycles: Optional[int] = None,
):
    """
    Run the singer daemon on a timer loop.

    Args:
        singer: The SingerOfStrifeAndSplendor instance
        interval: Seconds between cycles (default 300 = 5 minutes)
        max_cycles: If set, stop after N cycles (for testing)
    """
    print("=" * 72)
    print("  SINGER OF STRIFE AND SPLENDOR — Daemon Active")
    print(f"  Port: P4 DISRUPT | Commander: Red Regnant")
    print(f"  Alliteration: S·S·S | Dyad: P5 Pyre Praetorian")
    print(f"  Interval: {interval}s | Dry-run: {singer.dry_run}")
    print(f"  SSOT: {SSOT_DB}")
    print(f"  Thesis: {SPLENDOR_FACTS['core_thesis']}")
    print("=" * 72)

    while singer._running:
        report = singer.run_cycle()

        # Print cycle summary
        print(
            f"\n[Cycle {report['cycle']}] "
            f"STRIFE: {report['strife_count']} | "
            f"SPLENDOR: {report['splendor_count']} | "
            f"REQUESTED: {report.get('requested_count', 0)} | "
            f"Duration: {report['duration_sec']}s"
        )
        if report.get("health_snapshot"):
            h = report["health_snapshot"]
            print(
                f"  Health: {h['docs']} docs, {h['events']} events, "
                f"{h['words']:,} words, {h['db_mb']} MB, "
                f"Y/P ratio: {h['yield_perceive_ratio']}"
            )
        if report["errors"]:
            for err in report["errors"]:
                print(f"  [ERROR] {err}", file=sys.stderr)

        if max_cycles and singer.cycle_count >= max_cycles:
            print(f"\n  Max cycles ({max_cycles}) reached. Stopping.")
            break

        # Wait for next cycle
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break

    print("\n  Singer daemon shutting down gracefully.")
    print(f"  Final tally: STRIFE={singer.total_strife_sung}, "
          f"SPLENDOR={singer.total_splendor_sung}, "
          f"REQUESTED={singer.total_requested_sung}, "
          f"Errors={singer.errors_caught}")


# ═══════════════════════════════════════════════════════════════
# SINGLE-CYCLE MODE (for scripted/agent use)
# ═══════════════════════════════════════════════════════════════

def run_single_cycle(dry_run: bool = False) -> dict:
    """Run a single sing cycle and return the report. For scripted use."""
    singer = SingerOfStrifeAndSplendor(dry_run=dry_run)
    return singer.run_cycle()


def get_health_snapshot() -> dict:
    """Get a health snapshot without singing. For monitoring use."""
    singer = SingerOfStrifeAndSplendor(dry_run=True)
    conn = get_db_readonly()
    try:
        return singer.scan_health(conn)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="SINGER OF STRIFE AND SPLENDOR — P4 Red Regnant Daemon (Gen89)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run daemon (5-minute cycles, forever)
  python hfo_singer_daemon.py

  # Single cycle (run once and exit)
  python hfo_singer_daemon.py --single

  # Dry run (no writes, just show what would happen)
  python hfo_singer_daemon.py --dry-run --single

  # Custom interval (60 seconds between cycles)
  python hfo_singer_daemon.py --interval 60

  # Max 10 cycles then stop
  python hfo_singer_daemon.py --max-cycles 10

  # Health snapshot only (no singing)
  python hfo_singer_daemon.py --health

  # Status — report blessed pointer resolution
  python hfo_singer_daemon.py --status
""",
    )
    parser.add_argument(
        "--single", action="store_true",
        help="Run a single cycle and exit",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Dry run — no stigmergy writes",
    )
    parser.add_argument(
        "--interval", type=float, default=300.0,
        help="Seconds between cycles (default: 300 = 5 minutes)",
    )
    parser.add_argument(
        "--max-cycles", type=int, default=None,
        help="Stop after N cycles",
    )
    parser.add_argument(
        "--health", action="store_true",
        help="Print health snapshot and exit (no singing)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print status: PAL resolution, DB connectivity, pointer check",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output in JSON format (for scripted use)",
    )

    args = parser.parse_args()

    # ── Status mode ──
    if args.status:
        print("SINGER OF STRIFE AND SPLENDOR — Status Report")
        print("=" * 50)
        print(f"HFO_ROOT:  {HFO_ROOT}")
        print(f"SSOT_DB:   {SSOT_DB}")
        print(f"  exists:  {SSOT_DB.exists()}")
        print(f"POINTERS:  {POINTERS_FILE}")
        print(f"  exists:  {POINTERS_FILE.exists()}")
        print()

        # Resolve all relevant pointers
        try:
            pointers = _load_pointers()
            for key in sorted(pointers.keys()):
                try:
                    resolved = resolve_pointer(key)
                    exists = resolved.exists()
                    mark = "OK" if exists else "MISSING"
                    print(f"  [{mark:>7s}] {key:30s} → {resolved}")
                except Exception as e:
                    print(f"  [  ERROR] {key:30s} → {e}")
        except Exception as e:
            print(f"  Pointer load error: {e}")
        return

    # ── Health mode ──
    if args.health:
        health = get_health_snapshot()
        if args.json:
            print(json.dumps(health, indent=2, default=str))
        else:
            print("SINGER OF STRIFE AND SPLENDOR — Health Dashboard")
            print("=" * 50)
            for k, v in health.items():
                if k == "source_distribution":
                    print(f"\n  Source Distribution:")
                    for src, cnt in v.items():
                        print(f"    {src:20s} {cnt:>6,}")
                elif k == "splendor_facts":
                    print(f"\n  Splendor Facts (hardcoded):")
                    for fk, fv in v.items():
                        print(f"    {fk:35s} {fv}")
                elif k == "singer_metrics":
                    print(f"\n  Singer Metrics:")
                    for mk, mv in v.items():
                        print(f"    {mk:30s} {mv}")
                else:
                    print(f"  {k:35s} {v}")
        return

    # ── Singer execution ──
    singer = SingerOfStrifeAndSplendor(dry_run=args.dry_run)

    # Handle shutdown signals
    def handle_signal(signum, frame):
        print(f"\n  Signal {signum} received. Stopping singer daemon...")
        singer.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.single:
        # Single cycle mode
        report = singer.run_cycle()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"\nSINGER OF STRIFE AND SPLENDOR — Single Cycle Report")
            print("=" * 50)
            print(f"  Cycle:     {report['cycle']}")
            print(f"  STRIFE:    {report['strife_count']} songs emitted")
            print(f"  SPLENDOR:  {report['splendor_count']} songs emitted")
            print(f"  REQUESTED: {report.get('requested_count', 0)} songs sung from agent requests")
            print(f"  Health:    {'emitted' if report['health_emitted'] else 'FAILED'}")
            print(f"  Duration:  {report['duration_sec']}s")
            if report.get("health_snapshot"):
                h = report["health_snapshot"]
                print(f"\n  SSOT Health:")
                print(f"    Documents:         {h['docs']:,}")
                print(f"    Stigmergy events:  {h['events']:,}")
                print(f"    Words:             {h['words']:,}")
                print(f"    Memory losses:     {h['memory_losses']}")
                print(f"    Y/P ratio:         {h['yield_perceive_ratio']}")
                print(f"    DB size:           {h['db_mb']} MB")
            if report["errors"]:
                print(f"\n  Errors:")
                for err in report["errors"]:
                    print(f"    - {err}")
            print(f"\n  {SPLENDOR_FACTS['core_thesis']}")
    else:
        # Daemon loop mode
        asyncio.run(
            daemon_loop(
                singer,
                interval=args.interval,
                max_cycles=args.max_cycles,
            )
        )


if __name__ == "__main__":
    main()
