"""
tests/conftest.py — Shared fixtures for HFO Gen89 ATDD suite
=============================================================
Provides: mock SSOT, mock Ollama, mock NPU, mock Gemini/OpenRouter,
          resource snapshot builder, governor factory, router factory.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# In-memory SSOT stub
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path: Path):
    """Minimal SSOT SQLite with stigmergy_events table."""
    db = tmp_path / "test_ssot.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE stigmergy_events (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type    TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            subject       TEXT,
            data_json     TEXT,
            content_hash  TEXT UNIQUE
        )
    """)
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def tmp_db_full(tmp_path: Path):
    """Full-schema SSOT SQLite matching production stigmergy_events.

    Adds:
      - ``source`` column (required by real schema)
      - ``enforce_signal_metadata`` BEFORE INSERT trigger (mirrors production)

    Use this for tests that exercise hfo_ssot_write helpers directly or
    need realistic insert validation.
    """
    db = tmp_path / "test_ssot_full.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA busy_timeout=30000;

        CREATE TABLE IF NOT EXISTS stigmergy_events (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type    TEXT NOT NULL,
            source        TEXT,
            timestamp     TEXT NOT NULL,
            subject       TEXT,
            data_json     TEXT,
            content_hash  TEXT UNIQUE
        );

        -- Mirror of the production enforce_signal_metadata BEFORE INSERT trigger.
        -- Exempt prefixes: hfo.gen89.prey8.*, hfo.gen89.mission.*, hfo.gen89.chimera.*,
        --                  hfo.gen88.*, system_health*, hfo.gen89.ssot_write.gate_block*
        CREATE TRIGGER IF NOT EXISTS enforce_signal_metadata
        BEFORE INSERT ON stigmergy_events
        BEGIN
            SELECT CASE
                WHEN (
                    NEW.event_type NOT LIKE 'hfo.gen89.prey8.%'
                    AND NEW.event_type NOT LIKE 'hfo.gen89.mission.%'
                    AND NEW.event_type NOT LIKE 'hfo.gen89.chimera.%'
                    AND NEW.event_type NOT LIKE 'hfo.gen88.%'
                    AND NEW.event_type NOT LIKE 'system_health%'
                    AND NEW.event_type NOT LIKE 'hfo.gen89.ssot_write.gate_block%'
                    AND (
                        NEW.data_json IS NULL
                        OR json_extract(NEW.data_json, '$.signal_metadata') IS NULL
                    )
                )
                THEN RAISE(ABORT, 'signal_metadata required in data_json for this event_type')
            END;
        END;
    """)
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def tmp_status_file(tmp_path: Path):
    """Empty resource status JSON file."""
    f = tmp_path / ".hfo_resource_status.json"
    f.write_text("{}", encoding="utf-8")
    return f


# ──────────────────────────────────────────────────────────────────────────────
# Resource snapshot factory
# ──────────────────────────────────────────────────────────────────────────────

def make_snapshot(
    cpu_pct: float = 40.0,
    ram_pct: float = 60.0,
    vram_used_gb: float = 2.0,
    vram_budget_gb: float = 10.0,
    swap_pct: float = 20.0,
    npu_active: bool = False,
    ollama_models: Optional[list] = None,
) -> dict:
    if ollama_models is None:
        ollama_models = []
    return {
        "cpu_pct": cpu_pct,
        "ram_pct": ram_pct,
        "ram_free_gb": round(31.5 * (1 - ram_pct / 100), 1),
        "vram_used_gb": vram_used_gb,
        "vram_budget_gb": vram_budget_gb,
        "vram_pct": round(vram_used_gb / vram_budget_gb * 100, 1),
        "swap_pct": swap_pct,
        "swap_total_gb": 16.0,
        "swap_used_gb": round(16.0 * swap_pct / 100, 1),
        "npu_active": npu_active,
        "ollama_models": ollama_models,
        "gpu_gate": "GO" if vram_used_gb + 2.0 <= vram_budget_gb else "HOLD",
    }


@pytest.fixture
def snapshot_ok():
    return make_snapshot(cpu_pct=40, ram_pct=60, vram_used_gb=2.0)


@pytest.fixture
def snapshot_vram_pressure():
    return make_snapshot(
        vram_used_gb=8.5, ram_pct=72,
        ollama_models=[
            {"name": "granite4:3b", "vram_mb": 2586, "idle_s": 300},
            {"name": "qwen2.5:3b",  "vram_mb": 2280, "idle_s": 480},
        ]
    )


@pytest.fixture
def snapshot_ram_pressure():
    return make_snapshot(ram_pct=92, vram_used_gb=2.5)


# ──────────────────────────────────────────────────────────────────────────────
# Mock HTTP helpers
# ──────────────────────────────────────────────────────────────────────────────

class MockOllamaServer:
    """Captures Ollama API calls without real HTTP."""

    def __init__(self, generate_response: str = "test advisory", vram_gb: float = 2.0):
        self.calls: list[dict] = []
        self.generate_response = generate_response
        self.vram_gb = vram_gb
        self.models: list[dict] = []

    def ps_response(self) -> dict:
        return {"models": self.models}

    def generate(self, payload: dict) -> dict:
        self.calls.append({"endpoint": "/api/generate", "payload": payload})
        return {"response": self.generate_response, "eval_count": 50, "total_duration": 1_000_000_000}

    @property
    def generate_call_count(self):
        return sum(1 for c in self.calls if c["endpoint"] == "/api/generate")


@pytest.fixture
def mock_ollama():
    return MockOllamaServer()


# ──────────────────────────────────────────────────────────────────────────────
# Env helpers
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def base_env(tmp_path, tmp_db, monkeypatch):
    """Minimal .env-equivalent via monkeypatch for tests."""
    monkeypatch.setenv("HFO_GENERATION", "89")
    monkeypatch.setenv("HFO_SSOT_DB", str(tmp_db))
    monkeypatch.setenv("HFO_VRAM_BUDGET_GB", "10.0")
    monkeypatch.setenv("HFO_VRAM_TARGET_PCT", "80")
    monkeypatch.setenv("HFO_RAM_TARGET_PCT", "80")
    monkeypatch.setenv("HFO_CPU_TARGET_PCT", "80")
    monkeypatch.setenv("HFO_NPU_MIN_RATE_PCT", "30")
    monkeypatch.setenv("HFO_EVICT_IDLE_AFTER_S", "300")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    monkeypatch.setenv("LLM_ROUTER_STRATEGY", "npu_first")
    return monkeypatch
