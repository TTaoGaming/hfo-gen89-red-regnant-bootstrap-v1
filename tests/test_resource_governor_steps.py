"""
tests/test_resource_governor_steps.py — pytest-bdd steps for resource_governor.feature

Run:  pytest tests/test_resource_governor_steps.py -v --tb=short
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

sys.path.insert(0, str(Path(__file__).parent.parent / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "resources"))

try:
    from hfo_resource_governor import (
        ResourceGovernor,
        GovernorConfig,
        ResourcePressureError,
    )
    GOVERNOR_AVAILABLE = True
except (ImportError, AttributeError):
    GOVERNOR_AVAILABLE = False
    ResourceGovernor = None
    GovernorConfig = None
    ResourcePressureError = Exception

pytestmark = pytest.mark.skipif(
    not GOVERNOR_AVAILABLE,
    reason="ResourceGovernor class not yet implemented (red phase)"
)

FEATURE_FILE = str(Path(__file__).parent.parent / "features" / "resource_governor.feature")


@pytest.fixture
def ctx():
    return {
        "governor": None,
        "gate": None,
        "exception": None,
        "eviction_calls": [],
        "snapshot": {},
    }


# ── Given ─────────────────────────────────────────────────────────────────────

@given("the resource governor is initialised")
def gov_init(ctx, base_env, tmp_db):
    ctx["db"] = tmp_db

@given("the SSOT database is accessible")
def ssot_ok(ctx):
    pass

@given("Ollama is reachable at OLLAMA_BASE")
def ollama_reachable():
    pass

@given(parsers.parse("CPU is {pct:d} percent"))
def cpu_pct(ctx, pct):
    ctx["snapshot"]["cpu_pct"] = float(pct)

@given(parsers.parse("RAM is {pct:d} percent"))
def ram_pct(ctx, pct):
    ctx["snapshot"]["ram_pct"] = float(pct)

@given(parsers.parse("VRAM is {used:f} GB of a {budget:f} GB budget"))
def vram_set(ctx, used, budget):
    ctx["snapshot"]["vram_used_gb"] = used
    ctx["snapshot"]["vram_budget_gb"] = budget
    ctx["snapshot"]["vram_pct"] = round(used / budget * 100, 1)

@given(parsers.parse('Ollama has {n:d} models loaded: {model_desc}'))
def models_loaded(ctx, n, model_desc):
    models = []
    for part in model_desc.split(","):
        part = part.strip().strip('"')
        name = part.split(" idle")[0].strip()
        idle_s = 0
        if "idle" in part:
            mins = float(part.split("idle ")[1].split(" min")[0])
            idle_s = int(mins * 60)
        models.append({"name": name, "vram_mb": 2500, "idle_s": idle_s})
    ctx["snapshot"]["ollama_models"] = models
    ctx["snapshot"]["gpu_model_count"] = n

@given(parsers.parse("Ollama has {n:d} models loaded"))
def models_loaded_n(ctx, n):
    ctx["snapshot"]["ollama_models"] = [
        {"name": f"model{i}", "vram_mb": 2500, "idle_s": 400} for i in range(n)
    ]
    ctx["snapshot"]["gpu_model_count"] = n

@given("a daemon requests an Ollama inference slot")
def inference_request(ctx):
    ctx["inference_request"] = True

@given(parsers.parse("the last {n:d} inferences show NPU used {k:d} times"))
def npu_usage(ctx, n, k):
    ctx["inference_history"] = [{"provider": "npu" if i < k else "ollama"} for i in range(n)]

@given(parsers.parse("{n:d} Python processes matching \"hfo_\" are running"))
def ghost_procs(ctx, n):
    ctx["hfo_proc_count"] = n

@given(parsers.parse("the expected fleet size is {n:d}"))
def fleet_size(ctx, n):
    ctx["fleet_size"] = n

@given('a Python process named "hfo_daemon_fleet.py --watchdog" is running')
def watchdog_running(ctx):
    ctx["watchdog_running"] = True

@given("the governor background thread is started")
def gov_thread_started(ctx, base_env, tmp_db):
    config = GovernorConfig.from_env(db_path=tmp_db)
    ctx["governor"] = ResourceGovernor(config)

@given(parsers.parse("{n:d} governor snapshots have been collected"))
def snapshots_collected(ctx, n):
    ctx["snapshot_count"] = n

@given(parsers.parse('".env" contains "{key}={val}"'))
def env_set(key, val, monkeypatch):
    monkeypatch.setenv(key, val)


# ── When ──────────────────────────────────────────────────────────────────────

@when("I call governor.gate()")
def call_gate(ctx, base_env, tmp_db):
    snap = ctx.get("snapshot", {})
    config = GovernorConfig.from_env(db_path=tmp_db)
    gov = ResourceGovernor(config)
    ctx["governor"] = gov
    ctx["gate"] = gov.gate(snapshot=snap)

@when("I call governor.enforce()")
def call_enforce(ctx, base_env, tmp_db):
    snap = ctx.get("snapshot", {})
    config = GovernorConfig.from_env(db_path=tmp_db)
    gov = ResourceGovernor(config, _mock_ollama_evict=True)
    gov._inference_history = ctx.get("inference_history", [])
    ctx["governor"] = gov
    ctx["eviction_calls"] = []

    def mock_evict(model_name):
        ctx["eviction_calls"].append(model_name)

    gov._evict_model = mock_evict
    gov.enforce(snapshot=snap)
    ctx["gate"] = gov.gate(snapshot=snap)

@when("a daemon requests an Ollama inference slot")
def request_slot(ctx, base_env, tmp_db):
    config = GovernorConfig.from_env(db_path=tmp_db)
    gov = ResourceGovernor(config)
    try:
        gov.wait_for_gpu_headroom(snapshot=ctx.get("snapshot", {}))
    except ResourcePressureError as e:
        ctx["exception"] = e

@when("I call governor.reap_ghost_processes()")
def reap_ghosts(ctx, base_env, tmp_db):
    config = GovernorConfig.from_env(db_path=tmp_db)
    gov = ResourceGovernor(config)
    # Mock process list
    mock_procs = [
        MagicMock(info={"pid": 1000 + i, "name": "python.exe",
                        "cmdline": [f"hfo_octree_daemon.py", f"--port=P{i%8}"]})
        for i in range(ctx.get("hfo_proc_count", 18))
    ]
    if ctx.get("watchdog_running"):
        mock_procs.append(
            MagicMock(info={"pid": 9999, "name": "python.exe",
                            "cmdline": ["hfo_daemon_fleet.py", "--watchdog"]})
        )
    ctx["reaped_pids"] = gov.reap_ghost_processes(
        mock_process_list=mock_procs,
        fleet_size=ctx.get("fleet_size", 8),
    )

@when(parsers.parse("{n:d} seconds pass"))
def time_passes(ctx, n):
    import time
    time.sleep(min(n, 2))  # cap at 2s in tests

@when('I query stigmergy for "hfo.gen90.governor.summary"')
def query_summary(ctx, tmp_db):
    ctx["summary_rows"] = sqlite3.connect(str(tmp_db)).execute(
        "SELECT data_json FROM stigmergy_events WHERE event_type='hfo.gen90.governor.summary' ORDER BY id DESC LIMIT 1"
    ).fetchall()

@when("the governor initialises")
def gov_initialises(ctx, base_env, tmp_db):
    config = GovernorConfig.from_env(db_path=tmp_db)
    ctx["governor_config"] = config


# ── Then ──────────────────────────────────────────────────────────────────────

@then(parsers.parse('gate returns "{val}"'))
def gate_val(ctx, val):
    assert ctx["gate"] == val, f"Expected gate={val!r}, got {ctx['gate']!r}"

@then("no eviction occurs")
def no_eviction(ctx):
    assert ctx.get("eviction_calls", []) == []

@then(parsers.parse('Ollama DELETE keep_alive is called for "{model}" first'))
def evicted_first(ctx, model):
    assert ctx["eviction_calls"], "No evictions occurred"
    assert ctx["eviction_calls"][0] == model, \
        f"Expected {model!r} first, got {ctx['eviction_calls'][0]!r}"

@then(parsers.parse('a "{event_type}" stigmergy event is written'))
def stigmergy_event_written(ctx, event_type, tmp_db):
    rows = sqlite3.connect(str(tmp_db)).execute(
        "SELECT 1 FROM stigmergy_events WHERE event_type=?", (event_type,)
    ).fetchall()
    assert rows, f"No stigmergy event {event_type!r} found"

@then(parsers.parse('the eviction reason is "{reason}"'))
def eviction_reason(ctx, reason, tmp_db):
    rows = sqlite3.connect(str(tmp_db)).execute(
        "SELECT data_json FROM stigmergy_events WHERE event_type='hfo.gen90.governor.eviction' ORDER BY id DESC LIMIT 1"
    ).fetchall()
    assert rows
    data = json.loads(rows[0][0])
    assert data.get("reason") == reason, f"Expected {reason!r}, got {data.get('reason')!r}"

@then(parsers.parse("Ollama DELETE keep_alive is called for all {n:d} models"))
def evicted_all(ctx, n):
    assert len(ctx["eviction_calls"]) >= n, \
        f"Expected {n} evictions, got {len(ctx['eviction_calls'])}: {ctx['eviction_calls']}"

@then("gate returns \"HOLD\" until re-polled below threshold")
def gate_hold(ctx):
    assert ctx["gate"] == "HOLD"

@then(parsers.parse("governor.wait_for_gpu_headroom() raises ResourcePressureError"))
def ram_blocked_raised(ctx):
    assert isinstance(ctx.get("exception"), ResourcePressureError), \
        f"Expected ResourcePressureError, got {type(ctx.get('exception'))}"

@then(parsers.parse('the event "{event_type}" is written'))
def event_written(ctx, event_type, tmp_db):
    stigmergy_event_written(ctx, event_type, tmp_db)

@then(parsers.parse('the signal contains field "{field}" equal to {val:d}'))
def signal_has_field(ctx, field, val, tmp_db):
    rows = sqlite3.connect(str(tmp_db)).execute(
        "SELECT data_json FROM stigmergy_events ORDER BY id DESC LIMIT 5"
    ).fetchall()
    found = False
    for (dj,) in rows:
        data = json.loads(dj)
        if str(data.get(field)) == str(val) or data.get(field) == val:
            found = True
            break
    assert found, f"No event with field {field}={val} found"

@then(parsers.parse("processes above the fleet size limit are killed"))
def processes_killed(ctx):
    assert ctx.get("reaped_pids"), "No processes were reaped"

@then(parsers.parse('a "{event_type}" event records the killed PIDs'))
def ghost_event(ctx, event_type, tmp_db):
    stigmergy_event_written(ctx, event_type, tmp_db)

@then(parsers.parse("exactly {n:d} HFO daemon processes remain"))
def procs_remain(ctx, n):
    remaining = ctx.get("hfo_proc_count", 0) - len(ctx.get("reaped_pids", []))
    assert remaining == n, f"Expected {n} remaining, got {remaining}"

@then('"hfo_daemon_fleet.py" is never killed')
def watchdog_not_killed(ctx):
    killed = ctx.get("reaped_pids", [])
    assert 9999 not in killed, "Watchdog process was killed!"

@then("governor.enforce() has been called at least once")
def enforce_called(ctx):
    gov = ctx.get("governor")
    assert gov is not None
    assert gov.enforce_call_count >= 1

@then(parsers.parse('at least one "hfo.gen90.governor.cycle" event is in stigmergy'))
def cycle_event(ctx, tmp_db):
    rows = sqlite3.connect(str(tmp_db)).execute(
        "SELECT 1 FROM stigmergy_events WHERE event_type='hfo.gen90.governor.cycle'"
    ).fetchall()
    assert rows

@then("at least one summary event exists")
def summary_exists(ctx):
    assert ctx.get("summary_rows"), "No governor summary events found"

@then(parsers.parse("it contains fields: {fields}"))
def summary_has_fields(ctx, fields):
    assert ctx["summary_rows"]
    data = json.loads(ctx["summary_rows"][0][0])
    for f in [x.strip() for x in fields.split(",")]:
        assert f in data, f"Field {f!r} missing from summary"

@then(parsers.parse("governor.{attr} equals {val:f}"))
def governor_attr_equals(ctx, attr, val):
    config = ctx.get("governor_config")
    assert config is not None
    actual = getattr(config, attr, None)
    assert actual == val, f"Expected {attr}={val}, got {actual}"

@then(parsers.parse('no numeric literal "{lit}" appears in the governor enforcement logic'))
def no_hardcoded_literal(lit):
    gov_file = Path(__file__).parent.parent / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "resources" / "hfo_resource_governor.py"
    if not gov_file.exists():
        pytest.skip("Governor file not found")
    import re
    src = gov_file.read_text()
    # Look for standalone numeric usage (not in strings/comments)
    # This is a heuristic check
    matches = re.findall(rf'\b{re.escape(lit)}\b', re.sub(r'#.*$', '', src, flags=re.MULTILINE))
    assert not matches, f"Hardcoded literal {lit!r} found in governor"
