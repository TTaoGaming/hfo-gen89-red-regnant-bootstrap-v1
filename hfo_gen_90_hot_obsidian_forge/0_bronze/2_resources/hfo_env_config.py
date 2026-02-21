#!/usr/bin/env python3
"""
hfo_env_config.py — Centralized .env Configuration Loader
==========================================================
v1.0 | Gen90 | Port: P7 NAVIGATE (governance) | Medallion: bronze

PURPOSE:
    Single source of truth for ALL daemon configuration.
    Reads .env via python-dotenv, exposes typed dataclasses.
    Every daemon imports from here instead of scattered os.getenv() calls.

DESIGN PRINCIPLES:
    1. dotenv-first: All config lives in .env, loaded once at import time.
    2. Typed: Dataclasses with int/float/bool/str — no stringly-typed config.
    3. Stigmergy proof: load_config() writes a CloudEvent to SSOT on startup.
    4. Feature flags: Per-daemon enable/disable via HFO_DAEMON_*_ENABLED.
    5. Resource budgets: CPU/RAM/GPU/NPU/API ceilings in one place.
    6. Fail-closed: Missing required config = daemon refuses to start.

USAGE:
    from hfo_env_config import CONFIG, RESOURCE_BUDGET, DAEMON_FLAGS

    if DAEMON_FLAGS.p5_enabled:
        model = CONFIG.p5_model
        ...

    if RESOURCE_BUDGET.npu_always_on:
        start_npu_embedder()

Pointer key: env.config
Medallion: bronze
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# § 0  DOTENV LOADING
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    """Walk up from CWD or __file__ to find AGENTS.md (HFO_ROOT)."""
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
_ENV_PATH = HFO_ROOT / ".env"

# Load .env into os.environ (won't override existing env vars)
try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH, override=False)
    _DOTENV_LOADED = True
except ImportError:
    _DOTENV_LOADED = False


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

def _env_bool(key: str, default: bool = False) -> bool:
    val = _env(key, str(default)).lower().strip()
    return val in ("true", "1", "yes", "on")

def _env_int(key: str, default: int = 0) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default

def _env_float(key: str, default: float = 0.0) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


# ═══════════════════════════════════════════════════════════════
# § 1  IDENTITY — Who are we?
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class IdentityConfig:
    generation: int = _env_int("HFO_GENERATION", 89)
    operator: str = _env("HFO_OPERATOR", "TTAO")
    hive: str = _env("HFO_HIVE", "V")
    forge_dir: str = _env("HFO_FORGE", "hfo_gen_90_hot_obsidian_forge")
    ssot_db: str = _env("HFO_SSOT_DB",
                        "hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite")


# ═══════════════════════════════════════════════════════════════
# § 2  DAEMON FEATURE FLAGS — What runs?
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DaemonFlags:
    """Per-daemon enable/disable flags. All default True except noted."""

    # Port daemons
    p2_chimera_enabled: bool = _env_bool("HFO_DAEMON_P2_CHIMERA_ENABLED", True)
    p4_singer_enabled: bool = _env_bool("HFO_DAEMON_P4_SINGER_ENABLED", True)
    p4_prospector_enabled: bool = _env_bool("HFO_DAEMON_P4_PROSPECTOR_ENABLED", False)
    p5_daemon_enabled: bool = _env_bool("HFO_DAEMON_P5_ENABLED", True)
    p6_swarm_enabled: bool = _env_bool("HFO_DAEMON_P6_SWARM_ENABLED", True)

    # Infrastructure daemons
    npu_embedder_enabled: bool = _env_bool("HFO_DAEMON_NPU_EMBEDDER_ENABLED", True)
    resource_governor_enabled: bool = _env_bool("HFO_DAEMON_RESOURCE_GOVERNOR_ENABLED", True)
    web_chat_enabled: bool = _env_bool("HFO_DAEMON_WEB_CHAT_ENABLED", False)
    stigmergy_watchdog_enabled: bool = _env_bool("HFO_DAEMON_WATCHDOG_ENABLED", True)

    # Master kill-switch (if False, no daemons start)
    all_daemons_enabled: bool = _env_bool("HFO_DAEMONS_ENABLED", True)

    def is_enabled(self, daemon_name: str) -> bool:
        """Check if a specific daemon should run."""
        if not self.all_daemons_enabled:
            return False
        key = f"{daemon_name}_enabled"
        return getattr(self, key, False)


# ═══════════════════════════════════════════════════════════════
# § 3  PORT MODEL ASSIGNMENTS — What model does each port use?
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PortModels:
    """Per-port Ollama model assignments."""
    p2_model: str = _env("HFO_P2_MODEL", "qwen3:8b")
    p4_singer_model: str = "none"  # Singer is deterministic, no LLM
    p4_prospector_model: str = _env("HFO_P4_PROSPECTOR_MODEL", "qwen3:8b")
    p5_model: str = _env("HFO_P5_MODEL", "phi4:14b")
    p6_model: str = _env("HFO_P6_MODEL", "qwen3:8b")
    p6_advanced_model: str = _env("HFO_P6_ADVANCED_MODEL", "qwen3:8b")


# ═══════════════════════════════════════════════════════════════
# § 4  RESOURCE BUDGETS — How much of each compute surface?
# ═══════════════════════════════════════════════════════════════

# Known model VRAM estimates (GB) — single source of truth
MODEL_VRAM_ESTIMATES: dict[str, float] = {
    "lfm2.5-thinking:1.2b": 1.0, "qwen2.5:3b": 2.0, "granite4:3b": 2.0,
    "llama3.2:3b": 2.2, "gemma3:4b": 3.0, "qwen2.5-coder:7b": 5.0,
    "qwen3:8b": 5.5, "deepseek-r1:8b": 5.5, "gemma3:12b": 8.0,
    "phi4:14b": 9.5, "qwen3:30b-a3b": 3.5, "deepseek-r1:32b": 20.0,
}


@dataclass(frozen=True)
class ResourceBudget:
    """Resource ceilings and policies for all 5 compute surfaces."""

    # ── GPU / VRAM ──
    vram_total_gb: float = _env_float("HFO_VRAM_TOTAL_GB", 16.0)
    vram_budget_gb: float = _env_float("HFO_VRAM_BUDGET_GB", 12.0)
    vram_reserve_gb: float = _env_float("HFO_VRAM_RESERVE_GB", 2.0)
    gpu_always_utilized: bool = _env_bool("HFO_GPU_ALWAYS_UTILIZED", True)

    # ── CPU ──
    cpu_throttle_pct: float = _env_float("HFO_CPU_THROTTLE_PCT", 75.0)
    cpu_resume_pct: float = _env_float("HFO_CPU_RESUME_PCT", 60.0)
    cpu_reserve_pct: float = _env_float("HFO_CPU_RESERVE_PCT", 30.0)
    # cpu_reserve_pct = headroom kept free for user work

    # ── RAM ──
    ram_throttle_gb: float = _env_float("HFO_RAM_THROTTLE_GB", 4.0)
    ram_resume_gb: float = _env_float("HFO_RAM_RESUME_GB", 6.0)
    ram_reserve_gb: float = _env_float("HFO_RAM_RESERVE_GB", 4.0)
    # ram_reserve_gb = minimum free RAM for user work

    # ── NPU (Intel AI Boost) ──
    npu_always_on: bool = _env_bool("HFO_NPU_ALWAYS_ON", True)
    npu_embedder_batch: int = _env_int("HFO_NPU_EMBEDDER_BATCH", 32)
    npu_embedder_interval_s: int = _env_int("HFO_NPU_EMBEDDER_INTERVAL_S", 60)

    # ── Cloud APIs ──
    gemini_enabled: bool = _env_bool("HFO_GEMINI_ENABLED", True)
    gemini_rpm_cap: int = _env_int("HFO_GEMINI_RPM_CAP", 15)
    gemini_rpd_cap: int = _env_int("HFO_GEMINI_RPD_CAP", 1500)
    openrouter_enabled: bool = _env_bool("HFO_OPENROUTER_ENABLED", False)

    # ── Governance thresholds ──
    gov_sample_interval_s: int = _env_int("HFO_GOV_SAMPLE_INTERVAL_S", 10)
    gov_window_size: int = _env_int("HFO_GOV_WINDOW_SIZE", 60)
    gov_cooldown_s: int = _env_int("HFO_GOV_COOLDOWN_S", 300)
    gov_heartbeat_s: int = _env_int("HFO_GOV_HEARTBEAT_S", 300)
    gov_cpu_over_pct: float = _env_float("HFO_GOV_CPU_OVER_PCT", 80.0)
    gov_ram_over_pct: float = _env_float("HFO_GOV_RAM_OVER_PCT", 85.0)
    gov_cpu_under_pct: float = _env_float("HFO_GOV_CPU_UNDER_PCT", 15.0)
    gov_regime_threshold_pct: float = _env_float("HFO_GOV_REGIME_THRESHOLD_PCT", 70.0)

    # ── Daemon intervals ──
    daemon_enrich_interval_s: int = _env_int("HFO_DAEMON_ENRICH_INTERVAL_S", 300)
    daemon_research_interval_s: int = _env_int("HFO_DAEMON_RESEARCH_INTERVAL_S", 600)
    daemon_codegen_interval_s: int = _env_int("HFO_DAEMON_CODEGEN_INTERVAL_S", 900)
    daemon_patrol_interval_s: int = _env_int("HFO_DAEMON_PATROL_INTERVAL_S", 120)
    daemon_watchdog_interval_s: int = _env_int("HFO_DAEMON_WATCHDOG_INTERVAL_S", 30)

    # ── Swarm ──
    swarm_max_concurrent: int = _env_int("HFO_SWARM_MAX_CONCURRENT", 2)
    swarm_provider_strategy: str = _env("HFO_SWARM_PROVIDER_STRATEGY", "gemini_first")

    def estimate_vram(self, model: str) -> float:
        """Estimate VRAM usage for a model name."""
        return MODEL_VRAM_ESTIMATES.get(model, 4.0)


# ═══════════════════════════════════════════════════════════════
# § 5  OLLAMA CONFIG — GPU backend settings
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OllamaConfig:
    host: str = _env("OLLAMA_HOST", "http://127.0.0.1:11434")
    vulkan: bool = _env_bool("OLLAMA_VULKAN", True)
    flash_attention: bool = _env_bool("OLLAMA_FLASH_ATTENTION", True)


# ═══════════════════════════════════════════════════════════════
# § 6  FEATURE FLAGS — System-wide toggles
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FeatureFlags:
    fts_enabled: bool = _env_bool("HFO_FTS_ENABLED", True)
    precommit_enabled: bool = _env_bool("HFO_PRECOMMIT_ENABLED", True)
    strict_medallion: bool = _env_bool("HFO_STRICT_MEDALLION", True)
    stigmergy_proof: bool = _env_bool("HFO_STIGMERGY_PROOF", True)


# ═══════════════════════════════════════════════════════════════
# § 7  SINGLETON INSTANCES — Import these
# ═══════════════════════════════════════════════════════════════

IDENTITY = IdentityConfig()
DAEMON_FLAGS = DaemonFlags()
PORT_MODELS = PortModels()
RESOURCE_BUDGET = ResourceBudget()
OLLAMA = OllamaConfig()
FEATURES = FeatureFlags()

# Convenience alias
CONFIG = IDENTITY


# ═══════════════════════════════════════════════════════════════
# § 8  SSOT PATHS — Resolved from identity
# ═══════════════════════════════════════════════════════════════

FORGE_PATH = HFO_ROOT / IDENTITY.forge_dir
DB_PATH = HFO_ROOT / IDENTITY.ssot_db
BRONZE_RESOURCES = FORGE_PATH / "0_bronze" / "2_resources"


# ═══════════════════════════════════════════════════════════════
# § 9  STIGMERGY PROOF — Write config snapshot on load
# ═══════════════════════════════════════════════════════════════

def config_snapshot() -> dict:
    """Return full config state as a JSON-serializable dict."""
    return {
        "identity": asdict(IDENTITY),
        "daemon_flags": asdict(DAEMON_FLAGS),
        "port_models": asdict(PORT_MODELS),
        "resource_budget": {
            k: v for k, v in asdict(RESOURCE_BUDGET).items()
            if k != "model_vram_estimates"  # Skip large dict
        },
        "ollama": asdict(OLLAMA),
        "features": asdict(FEATURES),
        "dotenv_loaded": _DOTENV_LOADED,
        "env_path": str(_ENV_PATH),
        "env_exists": _ENV_PATH.exists(),
        "hfo_root": str(HFO_ROOT),
    }


def emit_config_loaded_event(source: str = "hfo_env_config") -> Optional[int]:
    """Write a stigmergy event recording the config state at load time.
    
    Returns the row ID if successful, None if skipped/failed.
    """
    if not FEATURES.stigmergy_proof:
        return None
    if not DB_PATH.exists():
        return None

    ts = datetime.now(timezone.utc).isoformat()
    snap = config_snapshot()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": "hfo.gen90.config.loaded",
        "source": f"{source}_gen{IDENTITY.generation}",
        "subject": f"CONFIG:loaded:{source}",
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": snap,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event["type"], ts, event["subject"], event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return row_id
    except Exception as e:
        print(f"  [ENV_CONFIG] Stigmergy write failed: {e}", file=sys.stderr)
        return None


# ═══════════════════════════════════════════════════════════════
# § 10  VALIDATION — Fail-closed on bad config
# ═══════════════════════════════════════════════════════════════

def validate() -> list[str]:
    """Validate configuration. Returns list of error strings (empty = OK)."""
    errors = []

    if not _ENV_PATH.exists():
        errors.append(f".env not found at {_ENV_PATH}")

    if not DB_PATH.exists():
        errors.append(f"SSOT database not found at {DB_PATH}")

    if RESOURCE_BUDGET.vram_budget_gb > RESOURCE_BUDGET.vram_total_gb:
        errors.append(
            f"VRAM budget ({RESOURCE_BUDGET.vram_budget_gb}GB) exceeds "
            f"VRAM total ({RESOURCE_BUDGET.vram_total_gb}GB)"
        )

    if RESOURCE_BUDGET.cpu_throttle_pct <= RESOURCE_BUDGET.cpu_resume_pct:
        errors.append(
            f"CPU throttle ({RESOURCE_BUDGET.cpu_throttle_pct}%) must be > "
            f"resume ({RESOURCE_BUDGET.cpu_resume_pct}%)"
        )

    if RESOURCE_BUDGET.ram_throttle_gb >= RESOURCE_BUDGET.ram_resume_gb:
        errors.append(
            f"RAM throttle ({RESOURCE_BUDGET.ram_throttle_gb}GB free) must be < "
            f"resume ({RESOURCE_BUDGET.ram_resume_gb}GB free)"
        )

    # Check model VRAM fits budget
    if DAEMON_FLAGS.p5_daemon_enabled:
        p5_vram = RESOURCE_BUDGET.estimate_vram(PORT_MODELS.p5_model)
        if p5_vram > RESOURCE_BUDGET.vram_budget_gb:
            errors.append(
                f"P5 model {PORT_MODELS.p5_model} ({p5_vram}GB) exceeds "
                f"VRAM budget ({RESOURCE_BUDGET.vram_budget_gb}GB)"
            )

    return errors


def require_valid():
    """Validate config and raise SystemExit if invalid. Use in daemon startup."""
    errors = validate()
    if errors:
        print("═══ HFO CONFIG VALIDATION FAILED ═══", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        print("Fix .env and retry.", file=sys.stderr)
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# § 11  CLI — Show / validate config
# ═══════════════════════════════════════════════════════════════

def _print_section(title: str, data: dict, indent: int = 2):
    prefix = " " * indent
    print(f"\n{'─' * 3} {title} {'─' * (50 - len(title))}")
    for k, v in data.items():
        print(f"{prefix}{k:40s} = {v}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HFO Gen90 Environment Config")
    parser.add_argument("--validate", action="store_true", help="Validate and exit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--emit", action="store_true", help="Write config.loaded event to SSOT")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(config_snapshot(), indent=2))
        sys.exit(0)

    if args.validate:
        errors = validate()
        if errors:
            for e in errors:
                print(f"  ✗ {e}")
            sys.exit(1)
        print("  ✓ Config valid")
        sys.exit(0)

    print("═══ HFO Gen90 Environment Configuration ═══")
    print(f"  .env loaded: {_DOTENV_LOADED} ({_ENV_PATH})")
    print(f"  HFO_ROOT:    {HFO_ROOT}")

    _print_section("Identity", asdict(IDENTITY))
    _print_section("Daemon Feature Flags", asdict(DAEMON_FLAGS))
    _print_section("Port Model Assignments", asdict(PORT_MODELS))

    # Resource budget — split into subsections
    rb = asdict(RESOURCE_BUDGET)
    gpu_keys = [k for k in rb if "vram" in k or "gpu" in k]
    cpu_keys = [k for k in rb if "cpu" in k]
    ram_keys = [k for k in rb if "ram" in k]
    npu_keys = [k for k in rb if "npu" in k]
    api_keys = [k for k in rb if "gemini" in k or "openrouter" in k]
    gov_keys = [k for k in rb if "gov_" in k]
    daemon_keys = [k for k in rb if "daemon_" in k]
    swarm_keys = [k for k in rb if "swarm_" in k]

    _print_section("GPU / VRAM Budget", {k: rb[k] for k in gpu_keys})
    _print_section("CPU Budget", {k: rb[k] for k in cpu_keys})
    _print_section("RAM Budget", {k: rb[k] for k in ram_keys})
    _print_section("NPU (Intel AI Boost)", {k: rb[k] for k in npu_keys})
    _print_section("Cloud APIs", {k: rb[k] for k in api_keys})
    _print_section("Governance Thresholds", {k: rb[k] for k in gov_keys})
    _print_section("Daemon Intervals", {k: rb[k] for k in daemon_keys})
    _print_section("Swarm", {k: rb[k] for k in swarm_keys})
    _print_section("Ollama", asdict(OLLAMA))
    _print_section("Feature Flags", asdict(FEATURES))

    # Validation
    errors = validate()
    print(f"\n{'─' * 3} Validation {'─' * 42}")
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("  ✓ All checks passed")

    # Emit if requested
    if args.emit:
        row = emit_config_loaded_event()
        print(f"\n  → Config event written to SSOT (row {row})")
