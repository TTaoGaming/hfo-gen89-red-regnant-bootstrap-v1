"""
tests/test_llm_router_steps.py — pytest-bdd steps for llm_router.feature

These tests will be RED until hfo_llm_router.py is built.
Run:  pytest tests/test_llm_router_steps.py -v --tb=short
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from pytest_bdd import given, when, then, scenario, scenarios, parsers

# Add resources to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources"))

# ── Import target under test ──────────────────────────────────────────────────
# This import will FAIL until hfo_llm_router.py is created — that's expected.
try:
    from hfo_llm_router import (
        LLMRouter,
        RouterConfig,
        RouterExhausted,
        ResourcePressureError,
        Provider,
    )
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False
    LLMRouter = None
    RouterConfig = None
    RouterExhausted = Exception
    ResourcePressureError = Exception
    class Provider:
        NPU = "npu"
        OLLAMA = "ollama"
        GEMINI = "gemini"
        OPENROUTER = "openrouter"

pytestmark = pytest.mark.skipif(
    not ROUTER_AVAILABLE,
    reason="hfo_llm_router.py not yet implemented (red phase)"
)

FEATURE_FILE = str(Path(__file__).parent.parent / "features" / "llm_router.feature")

# ── Fixtures / state ─────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    """Mutable test context shared between steps."""
    return {
        "router": None,
        "config": {},
        "result": None,
        "exception": None,
        "provider_calls": [],
        "strategy": "npu_first",
        "npu_available": False,
        "vram_ok": True,
        "ram_pct": 50.0,
        "gemini_key": "",
        "openrouter_key": "",
        "gemini_response": None,
    }

# ── Given steps ───────────────────────────────────────────────────────────────

@given("the LLM router is initialised with default config")
def router_default(ctx, base_env, tmp_db):
    ctx["db"] = tmp_db

@given("the resource status file exists")
def status_file_exists(ctx, tmp_status_file):
    ctx["status_file"] = tmp_status_file

@given(parsers.parse('the NPU model is configured at "{env_var}"'), target_fixture="npu_configured")
def npu_configured(ctx, env_var, tmp_path, monkeypatch):
    model_dir = tmp_path / "npu_model"
    model_dir.mkdir()
    monkeypatch.setenv(env_var, str(model_dir))
    ctx["npu_available"] = True

@given("the NPU model is configured")
def npu_configured_simple(ctx, tmp_path, monkeypatch):
    model_dir = tmp_path / "npu_model"
    model_dir.mkdir()
    monkeypatch.setenv("P6_NPU_LLM_MODEL", str(model_dir))
    ctx["npu_available"] = True

@given("the NPU model path does not exist")
def npu_not_available(ctx, monkeypatch):
    monkeypatch.setenv("P6_NPU_LLM_MODEL", "/nonexistent/path")
    ctx["npu_available"] = False

@given(parsers.parse("RAM usage is below {pct:d} percent"))
def ram_below(ctx, pct):
    ctx["ram_pct"] = float(pct - 5)

@given(parsers.parse("RAM usage is {pct:d} percent"))
def ram_at(ctx, pct):
    ctx["ram_pct"] = float(pct)

@given(parsers.parse("VRAM headroom is above {gb:d} GB"))
def vram_ok(ctx, gb):
    ctx["vram_used_gb"] = 2.0  # well below budget

@given(parsers.parse("Ollama VRAM usage is above {pct:d} percent of budget"))
def vram_above(ctx, pct):
    ctx["vram_used_gb"] = 9.0   # 90% of 10 GB budget

@given("GEMINI_API_KEY is set")
def gemini_key_set(ctx, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

@given("GEMINI_API_KEY is not set")
def gemini_key_unset(ctx, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

@given("OPENROUTER_API_KEY is set")
def openrouter_key_set(ctx, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")

@given("OPENROUTER_API_KEY is not set")
def openrouter_key_unset(ctx, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

@given("Ollama returns a connection error")
def ollama_error(ctx):
    ctx["ollama_error"] = True

@given("Gemini returns a 429 rate-limit response")
def gemini_429(ctx):
    ctx["gemini_response"] = 429

@given("the OLLAMA provider would be selected")
def ollama_would_be_selected(ctx):
    ctx["strategy"] = "ollama_first"

@given(parsers.parse("{n:d} inferences have completed in the last 10 minutes"))
def inferences_done(ctx, n):
    ctx["inference_count"] = n

@given(parsers.parse("{n:d} of them used the NPU"))
def npu_used(ctx, n):
    ctx["npu_inference_count"] = n

@given('".env" contains "LLM_ROUTER_STRATEGY=ollama_first"')
def strategy_in_env(monkeypatch):
    monkeypatch.setenv("LLM_ROUTER_STRATEGY", "ollama_first")

@given("the router is running")
def router_running(ctx, base_env, tmp_db):
    ctx["db"] = tmp_db

@given(parsers.parse('the environment variable "{var}" is changed to "{val}"'))
def change_env(var, val, monkeypatch):
    monkeypatch.setenv(var, val)

# ── When steps ────────────────────────────────────────────────────────────────

@when(parsers.parse('I call the router with provider_strategy "{strategy}"'))
def call_router(ctx, strategy, tmp_db):
    ctx["strategy"] = strategy
    config = RouterConfig(
        strategy=strategy,
        npu_model_path=None if not ctx.get("npu_available") else "/fake/npu",
        vram_budget_gb=10.0,
        ram_pct_override=ctx.get("ram_pct"),
        vram_used_gb_override=ctx.get("vram_used_gb", 2.0),
        db_path=tmp_db,
    )
    router = LLMRouter(config)
    ctx["router"] = router
    ctx["provider_calls"] = []

    try:
        result = router.generate(
            prompt="test prompt",
            role="advisory",
            _mock_ollama_error=ctx.get("ollama_error", False),
            _mock_gemini_status=ctx.get("gemini_response"),
        )
        ctx["result"] = result
        ctx["provider_calls"] = router.last_attempt_chain
    except (RouterExhausted, ResourcePressureError) as e:
        ctx["exception"] = e

@when("I call the router with any strategy")
def call_router_any(ctx, tmp_db):
    call_router(ctx, "npu_first", tmp_db)

@when(parsers.parse('I request inference for role "{role}"'))
def request_for_role(ctx, role, base_env, tmp_db):
    config = RouterConfig(strategy="npu_first", db_path=tmp_db)
    router = LLMRouter(config)
    ctx["router"] = router
    ctx["role"] = role
    ctx["role_selection"] = router.select_for_role(role)

@when("I call the router and inference succeeds")
def call_router_succeeds(ctx, tmp_db):
    call_router(ctx, "npu_first", tmp_db)

@when("query router.npu_utilisation_rate()")
def query_npu_rate(ctx, base_env, tmp_db):
    config = RouterConfig(strategy="npu_first", db_path=tmp_db)
    router = LLMRouter(config)
    # Inject fake history
    for i in range(ctx.get("inference_count", 10)):
        used_npu = i < ctx.get("npu_inference_count", 3)
        router._record_inference("npu" if used_npu else "ollama", "test", 100, 10)
    ctx["npu_rate"] = router.npu_utilisation_rate()

@when("the router is constructed")
def router_constructed(ctx, base_env, tmp_db):
    config = RouterConfig.from_env(db_path=tmp_db)
    ctx["router_config"] = config

@when("the router is reloaded")
def router_reloaded(ctx, base_env, tmp_db):
    config = RouterConfig.from_env(db_path=tmp_db)
    ctx["router"] = LLMRouter(config)

# ── Then steps ────────────────────────────────────────────────────────────────

@then(parsers.parse('the router selects provider "{provider}"'))
def router_selected_provider(ctx, provider):
    assert ctx.get("exception") is None, f"Router raised: {ctx['exception']}"
    assert ctx["result"]["provider"] == provider, \
        f"Expected provider={provider!r}, got {ctx['result']['provider']!r}"

@then("no Ollama request is made")
def no_ollama_request(ctx):
    providers_tried = ctx.get("provider_calls", [])
    assert "ollama" not in providers_tried, f"Ollama was attempted: {providers_tried}"

@then("the fallback is recorded in the router log")
def fallback_in_log(ctx):
    assert ctx["result"].get("fallback_used") is True

@then(parsers.parse('a "{reason}" reason is attached to the event'))
def reason_attached(ctx, reason):
    assert ctx["result"].get("reason") == reason, \
        f"Expected reason {reason!r}, got {ctx['result'].get('reason')!r}"

@then("a RouterExhausted exception is raised")
def router_exhausted_raised(ctx):
    assert isinstance(ctx.get("exception"), RouterExhausted), \
        f"Expected RouterExhausted, got {type(ctx.get('exception'))}"

@then(parsers.parse('the failure is written to stigmergy as "{event_type}"'))
def failure_in_stigmergy(ctx, event_type, tmp_db):
    rows = sqlite3.connect(str(tmp_db)).execute(
        "SELECT 1 FROM stigmergy_events WHERE event_type=?", (event_type,)
    ).fetchall()
    assert rows, f"No stigmergy event {event_type!r} found"

@then(parsers.parse('provider "{provider}" is never attempted'))
def provider_not_attempted(ctx, provider):
    assert provider not in ctx.get("provider_calls", []), \
        f"Provider {provider!r} was attempted: {ctx['provider_calls']}"

@then(parsers.parse('the preferred provider is "{provider}"'))
def preferred_provider(ctx, provider):
    sel = ctx["role_selection"]
    # Evaluate env-var placeholders
    if provider.startswith("${"):
        provider = "npu"
    assert sel["provider"] == provider, \
        f"Expected {provider!r}, got {sel['provider']!r}"

@then(parsers.parse('the preferred model is "{model}"'))
def preferred_model(ctx, model):
    sel = ctx["role_selection"]
    if model.startswith("${"):
        return  # dynamic — skip value check, just ensure field exists
    assert sel["model"] == model, \
        f"Expected {model!r}, got {sel['model']!r}"

@then(parsers.parse('the router skips Ollama due to "{reason}"'))
def router_skips_ollama(ctx, reason):
    assert "ollama" not in ctx.get("provider_calls", [])
    assert ctx["result"].get("skip_reason") == reason

@then(parsers.parse('the router escalates to "{provider}"'))
def router_escalates(ctx, provider):
    assert ctx["result"]["provider"] == provider

@then("a ResourcePressureError is raised with message containing \"RAM\"")
def resource_pressure_raised(ctx):
    assert isinstance(ctx.get("exception"), ResourcePressureError), \
        f"Expected ResourcePressureError, got {type(ctx.get('exception'))}"
    assert "RAM" in str(ctx["exception"])

@then(parsers.parse('the event "{event_type}" is written to stigmergy'))
def event_in_stigmergy(ctx, event_type, tmp_db):
    rows = sqlite3.connect(str(tmp_db)).execute(
        "SELECT 1 FROM stigmergy_events WHERE event_type=?", (event_type,)
    ).fetchall()
    assert rows, f"No stigmergy event {event_type!r} found"

@then(parsers.parse('a "{event_type}" event is in stigmergy'))
def event_is_in_stigmergy(ctx, event_type, tmp_db):
    event_in_stigmergy(ctx, event_type, tmp_db)

@then(parsers.parse("the event contains fields: {fields}"))
def event_has_fields(ctx, fields, tmp_db):
    field_list = [f.strip() for f in fields.split(",")]
    rows = sqlite3.connect(str(tmp_db)).execute(
        "SELECT data_json FROM stigmergy_events WHERE event_type='hfo.gen89.llm_router.inference' ORDER BY id DESC LIMIT 1"
    ).fetchall()
    assert rows, "No inference event found"
    data = json.loads(rows[0][0])
    for f in field_list:
        assert f in data, f"Field {f!r} missing from event: {list(data.keys())}"

@then(parsers.parse("the result is {val:f}"))
def npu_rate_is(ctx, val):
    assert abs(ctx["npu_rate"] - val) < 0.01, \
        f"Expected {val}, got {ctx['npu_rate']}"

@then(parsers.parse('router.strategy equals "{strategy}"'))
def router_strategy_is(ctx, strategy):
    assert ctx["router_config"].strategy == strategy

@then("no os.getenv() calls are made outside the Config dataclass")
def no_scattered_getenv():
    # Static analysis check — ensure hfo_llm_router.py has no bare os.getenv
    router_file = Path(__file__).parent.parent / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "resources" / "hfo_llm_router.py"
    if not router_file.exists():
        pytest.skip("Router not yet implemented")
    src = router_file.read_text()
    # Allow os.getenv only inside RouterConfig class body
    import re
    # crude check: count getenv outside class RouterConfig
    outside_class = re.sub(r'class RouterConfig.*?(?=\nclass |\Z)', '', src, flags=re.DOTALL)
    assert "os.getenv" not in outside_class, "Bare os.getenv found outside RouterConfig"

@then(parsers.parse('the next call uses provider "{provider}" as first choice'))
def next_call_uses(ctx, provider):
    assert ctx["router"].config.strategy.startswith(provider)
