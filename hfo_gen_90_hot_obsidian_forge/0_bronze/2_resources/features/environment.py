"""
Behave environment hooks for HFO infrastructure BDD tests.

Sets up shared context (Ollama base URL, DB path, thresholds)
so feature steps can validate real system state.
"""

import os
import sqlite3
from pathlib import Path

import httpx


def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for ancestor in [anchor] + list(anchor.parents):
            if (ancestor / "AGENTS.md").exists():
                return ancestor
    return Path.cwd()


HFO_ROOT = _find_root()
DB_REL = "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"
BRONZE_RESOURCES = "hfo_gen_89_hot_obsidian_forge/0_bronze/resources"
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


def before_all(context):
    """Populate shared context once before any feature runs."""
    context.hfo_root = HFO_ROOT
    context.ollama_base = OLLAMA_BASE
    context.ssot_db = str(HFO_ROOT / DB_REL)
    context.bronze_resources = str(HFO_ROOT / BRONZE_RESOURCES)
    context.http = httpx.Client(timeout=30)

    # Pareto thresholds — tuneable per role
    context.thresholds = {
        "min_gen_tps": 5.0,        # minimum generation tok/s (warm)
        "min_prompt_tps": 40.0,    # minimum prompt eval tok/s (Vulkan on Arc 140V)
        "max_cold_load_s": 120.0,  # max seconds for cold model load
        "min_vram_pct": 50.0,      # % of model that should be on VRAM
        "min_models_available": 3,  # at least N models pulled
        "min_ssot_docs": 1000,     # SSOT should have docs
        "min_stigmergy_events": 100,
    }


def after_all(context):
    context.http.close()
