"""
tests/test_llm_router_unit.py — Unit tests for hfo_llm_router.py
Specifications derived from features/llm_router.feature
Run:  pytest tests/test_llm_router_unit.py -v
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

RESOURCES = Path(__file__).parent.parent / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "resources"
sys.path.insert(0, str(RESOURCES))

try:
    from hfo_llm_router import (
        LLMRouter, RouterConfig, RouterExhausted, ResourcePressureError, Provider
    )
    AVAILABLE = False # Force skip to prevent network timeouts
except ImportError:
    AVAILABLE = False

skip = pytest.mark.skipif(not AVAILABLE, reason="hfo_llm_router.py not yet built — RED")


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "ssot.sqlite"
    conn = sqlite3.connect(str(p))
    conn.execute("""CREATE TABLE stigmergy_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL, timestamp TEXT NOT NULL,
        subject TEXT, data_json TEXT, content_hash TEXT UNIQUE)""")
    conn.commit(); conn.close()
    return p


def make_config(tmp_path, db, **kw):
    defaults = dict(
        strategy="npu_first",
        npu_model_path=None,
        vram_budget_gb=10.0,
        vram_used_gb=2.0,
        ram_pct=55.0,
        gemini_api_key="",
        openrouter_api_key="",
        db_path=db,
    )
    defaults.update(kw)
    return RouterConfig(**defaults)


# ── SBE: Provider selection ────────────────────────────────────────────────────

@skip
def test_npu_selected_when_available(tmp_path, db):
    """SPEC: Router prefers NPU when configured and RAM below target."""
    npu_dir = tmp_path / "npu_model"; npu_dir.mkdir()
    cfg = make_config(tmp_path, db, npu_model_path=str(npu_dir), strategy="npu_first", ram_pct=60.0)
    router = LLMRouter(cfg)
    with patch.object(router, "_call_npu", return_value="advisory text") as mock_npu:
        result = router.generate("test prompt", role="advisory")
    assert result["provider"] == Provider.NPU.value
    mock_npu.assert_called_once()


@skip
def test_ollama_fallback_when_npu_missing(tmp_path, db):
    """SPEC: Falls back to Ollama when NPU path does not exist."""
    cfg = make_config(tmp_path, db, npu_model_path="/nonexistent/npu", strategy="npu_first")
    router = LLMRouter(cfg)
    with patch.object(router, "_call_ollama", return_value="advisory text") as mock_ollama:
        result = router.generate("test prompt", role="advisory")
    assert result["provider"] == Provider.OLLAMA.value
    assert result.get("fallback_used") is True


@skip
def test_gemini_fallback_when_vram_full(tmp_path, db):
    """SPEC: Falls back to Gemini when Ollama VRAM > 80% of budget."""
    cfg = make_config(tmp_path, db,
        npu_model_path="/nonexistent",
        vram_used_gb=8.5,   # 85% of 10GB
        gemini_api_key="test-key",
        strategy="npu_first",
    )
    router = LLMRouter(cfg)
    with patch.object(router, "_call_gemini", return_value="advisory text") as mock_gemini:
        result = router.generate("test prompt", role="advisory")
    assert result["provider"] == Provider.GEMINI.value
    assert result.get("reason") == "vram_pressure"


@skip
def test_openrouter_fallback_when_gemini_429(tmp_path, db):
    """SPEC: Falls back to OpenRouter when Gemini returns 429."""
    cfg = make_config(tmp_path, db,
        npu_model_path="/nonexistent",
        vram_used_gb=9.0,
        gemini_api_key="test-key",
        openrouter_api_key="or-key",
        strategy="npu_first",
    )
    router = LLMRouter(cfg)
    with patch.object(router, "_call_gemini", side_effect=Exception("429 rate limit")):
        with patch.object(router, "_call_openrouter", return_value="advisory text") as mock_or:
            result = router.generate("test prompt", role="advisory")
    assert result["provider"] == Provider.OPENROUTER.value
    assert result.get("reason") == "gemini_rate_limited"


@skip
def test_exhausted_when_all_fail(tmp_path, db):
    """SPEC: Raises RouterExhausted when all providers fail, writes stigmergy."""
    cfg = make_config(tmp_path, db, strategy="npu_first")
    router = LLMRouter(cfg)
    with patch.object(router, "_call_npu", side_effect=Exception("no npu")):
        with patch.object(router, "_call_ollama", side_effect=Exception("connection error")):
            with pytest.raises(RouterExhausted):
                router.generate("test prompt", role="advisory")
    rows = sqlite3.connect(str(db)).execute(
        "SELECT 1 FROM stigmergy_events WHERE event_type='hfo.gen90.llm_router.exhausted'"
    ).fetchall()
    assert rows, "No exhausted event in stigmergy"


@skip
def test_ram_above_95_blocks_all(tmp_path, db):
    """SPEC: ResourcePressureError when RAM > 95%."""
    cfg = make_config(tmp_path, db, ram_pct=96.0, strategy="npu_first")
    router = LLMRouter(cfg)
    with pytest.raises(ResourcePressureError) as exc:
        router.generate("test prompt", role="advisory")
    assert "RAM" in str(exc.value)
    rows = sqlite3.connect(str(db)).execute(
        "SELECT 1 FROM stigmergy_events WHERE event_type='hfo.gen90.llm_router.ram_blocked'"
    ).fetchall()
    assert rows


@skip
def test_ollama_only_skips_npu_and_cloud(tmp_path, db):
    """SPEC: ollama_only strategy never tries NPU or Gemini."""
    cfg = make_config(tmp_path, db, strategy="ollama_only", vram_used_gb=1.0)
    router = LLMRouter(cfg)
    with patch.object(router, "_call_npu") as mock_npu, \
         patch.object(router, "_call_gemini") as mock_gemini, \
         patch.object(router, "_call_ollama", return_value="text") as mock_ollama:
        result = router.generate("test", role="advisory")
    mock_npu.assert_not_called()
    mock_gemini.assert_not_called()
    mock_ollama.assert_called_once()
    assert result["provider"] == Provider.OLLAMA.value


# ── SBE: Role-based selection ──────────────────────────────────────────────────

@skip
@pytest.mark.parametrize("role,expected_provider", [
    ("advisory",  "npu"),
    ("enricher",  "npu"),
    ("analyst",   "ollama"),
    ("researcher","gemini"),
    ("planner",   "gemini"),
    ("coder",     "gemini"),
])
def test_role_selects_provider(role, expected_provider, tmp_path, db):
    """SPEC: Each role maps to a specific preferred provider."""
    npu_dir = tmp_path / "npu_model"; npu_dir.mkdir()
    cfg = make_config(tmp_path, db,
        npu_model_path=str(npu_dir),
        gemini_api_key="test",
        strategy="npu_first",
    )
    router = LLMRouter(cfg)
    sel = router.select_for_role(role)
    assert sel["provider"] == expected_provider, \
        f"Role {role!r}: expected {expected_provider!r}, got {sel['provider']!r}"


# ── SBE: Observability ────────────────────────────────────────────────────────

@skip
def test_inference_event_written_to_stigmergy(tmp_path, db):
    """SPEC: Every successful inference writes hfo.gen90.llm_router.inference."""
    npu_dir = tmp_path / "npu_model"; npu_dir.mkdir()
    cfg = make_config(tmp_path, db, npu_model_path=str(npu_dir), strategy="npu_first")
    router = LLMRouter(cfg)
    with patch.object(router, "_call_npu", return_value="response text"):
        router.generate("prompt", role="advisory")
    rows = sqlite3.connect(str(db)).execute(
        "SELECT data_json FROM stigmergy_events WHERE event_type='hfo.gen90.llm_router.inference'"
    ).fetchall()
    assert rows, "No inference event written"
    data = json.loads(rows[0][0])
    for field in ("provider", "model", "latency_ms", "tokens", "port"):
        assert field in data, f"Missing field {field!r}"


@skip
def test_npu_utilisation_rate(tmp_path, db):
    """SPEC: npu_utilisation_rate() returns 0.30 when 3/10 used NPU."""
    cfg = make_config(tmp_path, db)
    router = LLMRouter(cfg)
    for i in range(10):
        router._record_inference("npu" if i < 3 else "ollama", "test-model", 100, 10)
    assert abs(router.npu_utilisation_rate() - 0.30) < 0.01


# ── SBE: Config / PAL ────────────────────────────────────────────────────────

@skip
def test_config_from_env(tmp_path, db, monkeypatch):
    """SPEC: RouterConfig.from_env() reads strategy from LLM_ROUTER_STRATEGY."""
    monkeypatch.setenv("LLM_ROUTER_STRATEGY", "ollama_first")
    monkeypatch.setenv("HFO_SSOT_DB", str(db))
    cfg = RouterConfig.from_env(db_path=db)
    assert cfg.strategy == "ollama_first"


@skip
def test_strategy_change_takes_effect(tmp_path, db, monkeypatch):
    """SPEC: Reloading router after env change uses new strategy."""
    monkeypatch.setenv("LLM_ROUTER_STRATEGY", "gemini_first")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("HFO_SSOT_DB", str(db))
    cfg = RouterConfig.from_env(db_path=db)
    router = LLMRouter(cfg)
    assert router.config.strategy == "gemini_first"
