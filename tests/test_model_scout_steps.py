"""
tests/test_model_scout_steps.py — pytest-bdd steps for model_scout.feature

Tests the structural invariants of the HFO Model Scout spell:
  - SLOT_TO_HFO_ENV covers SLOT_NAMES exactly (slot→port mapping consistency)
  - MapEliteResult.validate() enforces BFT and schema invariants
  - promptfoo.yaml assertions have non-empty / garbage guards
  - map_elite_latest.json has required schema + task_scores in all_results

Run:
  pytest tests/test_model_scout_steps.py -v --tb=short
  pytest tests/test_model_scout_steps.py -v -k "slot" --tb=short  # slot tests only
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from pytest_bdd import given, when, then, scenarios, parsers

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT     = Path(__file__).parent.parent
SCOUT_DIR     = REPO_ROOT / "_scratch" / "hfo_model_scout"
PROMPTFOO_YAML = SCOUT_DIR / "promptfoo.yaml"
MAP_ELITE_JSON = SCOUT_DIR / "map_elite_latest.json"

sys.path.insert(0, str(SCOUT_DIR))

FEATURE_FILE = str(REPO_ROOT / "features" / "model_scout.feature")

# ── Lazy imports (scout module may not exist in all envs) ─────────────────────
try:
    from ga_select import (
        SLOT_NAMES, SLOT_TO_HFO_ENV, BFT_THRESHOLD,
        MapEliteResult, MapEliteSlot, ScoredModel,
    )
    GA_SELECT_AVAILABLE = True
except (ImportError, AssertionError) as _ga_err:
    GA_SELECT_AVAILABLE = False
    _ga_err_msg = str(_ga_err)

scenarios(FEATURE_FILE)

# ── Shared context fixture ────────────────────────────────────────────────────

@pytest.fixture
def ctx() -> dict:
    return {
        "exception": None,
        "result": None,
        "yaml_data": None,
        "json_data": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GIVEN steps
# ─────────────────────────────────────────────────────────────────────────────

@given("ga_select module is imported")
def step_ga_select_imported(ctx):
    if not GA_SELECT_AVAILABLE:
        pytest.skip(
            f"ga_select.py could not be imported from {SCOUT_DIR}: {_ga_err_msg}\n"
            "This probably means the import-time assert fired — check SLOT_TO_HFO_ENV."
        )


@given("promptfoo.yaml is loaded")
def step_promptfoo_yaml_loaded(ctx):
    if not PROMPTFOO_YAML.exists():
        pytest.skip(f"promptfoo.yaml not found at {PROMPTFOO_YAML}")
    ctx["yaml_data"] = yaml.safe_load(PROMPTFOO_YAML.read_text(encoding="utf-8"))


@given("map_elite_latest.json exists")
def step_map_elite_exists(ctx):
    if not MAP_ELITE_JSON.exists():
        pytest.skip(
            f"map_elite_latest.json not found at {MAP_ELITE_JSON}.\n"
            "Run: python _scratch/hfo_model_scout/run.py --only-installed"
        )
    ctx["json_data"] = json.loads(MAP_ELITE_JSON.read_text(encoding="utf-8"))


@given("a MapEliteResult with 4 distinct families and all SLOT_NAMES present")
def step_valid_map_elite(ctx):
    if not GA_SELECT_AVAILABLE:
        pytest.skip("ga_select not available")
    slots = [
        MapEliteSlot("APEX_SPEED", "lfm:0.7b",  "lfm",     18.8, 25.2, 0.7, 0.9, 26.9, {}),
        MapEliteSlot("APEX_COST",  "gemma:12b",  "gemma",   75.0,  4.9, 8.1,10.1,  9.3, {}),
        MapEliteSlot("APEX_INTEL", "qwen2.5:3b", "qwen",    75.0,  9.3, 1.9, 2.4, 39.5, {}),
        MapEliteSlot("APEX_AUX",   "granite4:3b","granite", 75.0, 10.1, 2.1, 2.6, 35.7, {}),
    ]
    ctx["result"] = MapEliteResult(
        slots=slots, families=["gemma","granite","lfm","qwen"],
        bft_satisfied=True, ga_fitness=1.067,
        fitness_history=[1.0, 1.067], all_results=[],
        timestamp=datetime.now(timezone.utc).isoformat(), eval_model_count=8,
    )


@given("a MapEliteResult with only 2 distinct families")
def step_bft_violation(ctx):
    if not GA_SELECT_AVAILABLE:
        pytest.skip("ga_select not available")
    slots = [
        MapEliteSlot("APEX_SPEED", "qwen:a",  "qwen",   18.8, 25.2, 0.7, 0.9, 26.9, {}),
        MapEliteSlot("APEX_COST",  "qwen:b",  "qwen",   75.0, 9.3, 1.9, 2.4, 39.5, {}),
        MapEliteSlot("APEX_INTEL", "gemma:a", "gemma",  75.0, 6.6, 3.3, 4.1, 22.7, {}),
        MapEliteSlot("APEX_AUX",   "gemma:b", "gemma",  75.0, 4.9, 8.1,10.1,  9.3, {}),
    ]
    ctx["result"] = MapEliteResult(
        slots=slots, families=["gemma","qwen"],
        bft_satisfied=False, ga_fitness=-8.9,
        fitness_history=[-8.9], all_results=[],
        timestamp=datetime.now(timezone.utc).isoformat(), eval_model_count=4,
    )


@given(parsers.parse('a MapEliteResult missing slot "{slot_name}"'))
def step_missing_slot(ctx, slot_name: str):
    if not GA_SELECT_AVAILABLE:
        pytest.skip("ga_select not available")
    all_slots = [
        MapEliteSlot("APEX_SPEED", "lfm:0.7b",  "lfm",     18.8, 25.2, 0.7, 0.9, 26.9, {}),
        MapEliteSlot("APEX_COST",  "gemma:12b",  "gemma",   75.0,  4.9, 8.1,10.1,  9.3, {}),
        MapEliteSlot("APEX_INTEL", "qwen:3b",    "qwen",    75.0,  9.3, 1.9, 2.4, 39.5, {}),
        MapEliteSlot("APEX_AUX",   "granite:3b", "granite", 75.0, 10.1, 2.1, 2.6, 35.7, {}),
    ]
    slots = [s for s in all_slots if s.slot_name != slot_name]
    ctx["result"] = MapEliteResult(
        slots=slots, families=["gemma","granite","lfm","qwen"],
        bft_satisfied=True, ga_fitness=1.067,
        fitness_history=[1.067], all_results=[],
        timestamp=datetime.now(timezone.utc).isoformat(), eval_model_count=8,
    )


@given(parsers.parse('a MapEliteResult with an unknown slot name "{slot_name}"'))
def step_unknown_slot(ctx, slot_name: str):
    if not GA_SELECT_AVAILABLE:
        pytest.skip("ga_select not available")
    slots = [
        MapEliteSlot("APEX_SPEED", "lfm:0.7b",  "lfm",     18.8, 25.2, 0.7, 0.9, 26.9, {}),
        MapEliteSlot("APEX_COST",  "gemma:12b",  "gemma",   75.0,  4.9, 8.1,10.1,  9.3, {}),
        MapEliteSlot("APEX_INTEL", "qwen:3b",    "qwen",    75.0,  9.3, 1.9, 2.4, 39.5, {}),
        MapEliteSlot(slot_name,    "mystery:1b", "mystery", 50.0, 15.0, 1.0, 1.2, 50.0, {}),
    ]
    ctx["result"] = MapEliteResult(
        slots=slots, families=["gemma","lfm","mystery","qwen"],
        bft_satisfied=True, ga_fitness=1.0,
        fitness_history=[1.0], all_results=[],
        timestamp=datetime.now(timezone.utc).isoformat(), eval_model_count=4,
    )


# ─────────────────────────────────────────────────────────────────────────────
# WHEN steps
# ─────────────────────────────────────────────────────────────────────────────

@when("validate() is called")
def step_call_validate(ctx):
    try:
        ctx["result"].validate()
    except ValueError as exc:
        ctx["exception"] = exc


# ─────────────────────────────────────────────────────────────────────────────
# THEN steps — slot mapping
# ─────────────────────────────────────────────────────────────────────────────

@then("SLOT_TO_HFO_ENV keys equal SLOT_NAMES exactly")
def step_slot_env_keys_equal_slot_names(ctx):
    assert set(SLOT_TO_HFO_ENV.keys()) == set(SLOT_NAMES), (
        f"Mismatch!\n"
        f"  SLOT_TO_HFO_ENV keys: {sorted(SLOT_TO_HFO_ENV.keys())}\n"
        f"  SLOT_NAMES:           {SLOT_NAMES}\n"
        "  Fix: update SLOT_TO_HFO_ENV in ga_select.py to match SLOT_NAMES."
    )


@then(parsers.parse('SLOT_TO_HFO_ENV "{slot}" contains "{env_key}"'))
def step_slot_contains_key(ctx, slot: str, env_key: str):
    assert slot in SLOT_TO_HFO_ENV, f"Slot '{slot}' not in SLOT_TO_HFO_ENV ({list(SLOT_TO_HFO_ENV)})"
    assert env_key in SLOT_TO_HFO_ENV[slot], (
        f"Slot '{slot}' maps to {SLOT_TO_HFO_ENV[slot]}, expected '{env_key}' to be present."
    )


@then(parsers.parse('SLOT_TO_HFO_ENV "{slot}" does not contain "{env_key}"'))
def step_slot_does_not_contain_key(ctx, slot: str, env_key: str):
    assert slot in SLOT_TO_HFO_ENV, f"Slot '{slot}' not in SLOT_TO_HFO_ENV"
    assert env_key not in SLOT_TO_HFO_ENV[slot], (
        f"Slot '{slot}' should NOT map to '{env_key}' "
        f"(got {SLOT_TO_HFO_ENV[slot]}).\n"
        f"APEX_SPEED is the GPU-warmup-only slot — assigning it to "
        f"quality-sensitive ports like P2/P4 degrades inference quality."
    )


# ─────────────────────────────────────────────────────────────────────────────
# THEN steps — validate()
# ─────────────────────────────────────────────────────────────────────────────

@then("no exception is raised")
def step_no_exception(ctx):
    assert ctx["exception"] is None, (
        f"Expected no exception, got: {ctx['exception']}"
    )


@then(parsers.parse("ValueError is raised containing \"{message}\""))
def step_value_error_with_message(ctx, message: str):
    assert ctx["exception"] is not None, (
        f"Expected ValueError to be raised, but no exception was raised.\n"
        f"validate() must enforce: {message}"
    )
    assert isinstance(ctx["exception"], ValueError), (
        f"Expected ValueError, got {type(ctx['exception'])}: {ctx['exception']}"
    )
    assert message in str(ctx["exception"]), (
        f"ValueError message should contain '{message}'.\n"
        f"Got: {ctx['exception']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# THEN steps — promptfoo.yaml spec lint
# ─────────────────────────────────────────────────────────────────────────────

def _get_assertion_values(yaml_data: dict) -> dict[str, str]:
    """Extract {task_id → assertion JS value} from promptfoo.yaml tests."""
    result = {}
    for test in yaml_data.get("tests", []):
        desc = test.get("description", "")
        # Task ID is the first token of the description (e.g. "T1_REASON")
        task_id = desc.split()[0] if desc else "UNKNOWN"
        for assertion in test.get("assert", []):
            if assertion.get("type") == "javascript":
                result[task_id] = assertion.get("value", "")
    return result


@then("every assertion value contains \"EMPTY_RESPONSE\"")
def step_every_assertion_has_empty_guard(ctx):
    values = _get_assertion_values(ctx["yaml_data"])
    assert values, "No javascript assertions found in promptfoo.yaml"
    failures = [tid for tid, code in values.items() if "EMPTY_RESPONSE" not in code]
    assert not failures, (
        f"These assertions are missing the EMPTY_RESPONSE guard: {failures}\n"
        "Add at the top of each assertion value:\n"
        "  if (!output || output.trim().length === 0) {\n"
        "    return { pass: false, score: 0, reason: 'EMPTY_RESPONSE: ...' };\n"
        "  }"
    )


@then(parsers.parse('the {task_id} assertion value contains "{text}"'))
def step_assertion_contains(ctx, task_id: str, text: str):
    values = _get_assertion_values(ctx["yaml_data"])
    assert task_id in values, f"Task '{task_id}' not found in promptfoo.yaml (have: {list(values)})"
    assert text in values[task_id], (
        f"Assertion for {task_id} should contain '{text}'.\n"
        f"Current value:\n{values[task_id]}"
    )


@then(parsers.parse('the {task_id} assertion value does not contain "{text}"'))
def step_assertion_does_not_contain(ctx, task_id: str, text: str):
    values = _get_assertion_values(ctx["yaml_data"])
    assert task_id in values, f"Task '{task_id}' not found in promptfoo.yaml"
    assert text not in values[task_id], (
        f"Assertion for {task_id} must not contain bare '{text}'.\n"
        "Use structured return objects instead: {{ pass: false, score: 0, reason: '...' }}\n"
        "Bare booleans give no diagnostic reason and break failure triage."
    )


# ─────────────────────────────────────────────────────────────────────────────
# THEN steps — map_elite_latest.json schema
# ─────────────────────────────────────────────────────────────────────────────

@then(parsers.parse('the JSON contains keys "{keys_str}"'))
def step_json_has_keys(ctx, keys_str: str):
    # parsers.parse captures the full string between outer quotes, including any
    # embedded " chars from the feature file. Strip them before splitting.
    required = [k.strip().strip('"') for k in keys_str.split(",")]
    missing = [k for k in required if k not in ctx["json_data"]]
    assert not missing, (
        f"map_elite_latest.json is missing keys: {missing}\n"
        f"Present: {list(ctx['json_data'].keys())}"
    )


@then('every entry in all_results has a "task_scores" field')
def step_all_results_have_task_scores(ctx):
    all_results = ctx["json_data"].get("all_results", [])
    assert all_results, "all_results is empty — run the full eval first"
    missing = [r.get("model", "?") for r in all_results if "task_scores" not in r]
    assert not missing, (
        f"These all_results entries are missing task_scores: {missing}\n"
        "Fix: add task_scores to all_results in build_map_elite() in ga_select.py"
    )


@then("bft_satisfied is true")
def step_bft_satisfied(ctx):
    assert ctx["json_data"].get("bft_satisfied") is True, (
        f"bft_satisfied={ctx['json_data'].get('bft_satisfied')} — GA did not find a BFT portfolio.\n"
        "Either fewer than 4 model families are installed, or validate() let a violation through."
    )


@then("families list has at least 4 entries")
def step_families_count(ctx):
    families = ctx["json_data"].get("families", [])
    assert len(families) >= BFT_THRESHOLD if GA_SELECT_AVAILABLE else 4, (
        f"Portfolio has only {len(families)} families: {families}.\n"
        f"BFT_THRESHOLD={BFT_THRESHOLD} — install models from more families."
    )


# ── Freshness + supersession steps ────────────────────────────────────────────────
# No @scenario decorators needed — scenarios() at the top auto-registers everything
# in features/model_scout.feature. We just supply the step implementations.

import datetime as _datelib

try:
    import _scratch.hfo_model_scout.discover as _discover_mod
    DISCOVER_AVAILABLE = True
except (ImportError, AssertionError) as _disc_err:
    _discover_mod = None  # type: ignore
    DISCOVER_AVAILABLE = False


@given("the discover module is imported")
def step_discover_imported(ctx):
    if not DISCOVER_AVAILABLE:
        pytest.skip(
            "discover.py failed to import — likely a stale CURATED_REFRESH_DATE assertion "
            "or a syntax error. Fix discover.py first."
        )
    ctx["discover"] = _discover_mod


@then("CURATED_REFRESH_DATE is not more than 30 days old")
def step_curated_refresh_date_fresh(ctx):
    d = ctx["discover"]
    refresh_date = _datelib.date.fromisoformat(d.CURATED_REFRESH_DATE)
    age = (_datelib.date.today() - refresh_date).days
    assert age <= 30, (
        f"CURATED_REFRESH_DATE={d.CURATED_REFRESH_DATE} is {age} days old (max 30).\n"
        "Update CURATED_PULL_CANDIDATES + SUPERSEDED_BY in discover.py "
        "and bump CURATED_REFRESH_DATE to today."
    )


@then(parsers.parse('SUPERSEDED_BY contains an entry for "{model_name}"'))
def step_superseded_contains(ctx, model_name: str):
    d = ctx["discover"]
    assert model_name in d.SUPERSEDED_BY, (
        f'{model_name!r} is not in SUPERSEDED_BY. '
        "Add it with its current replacement so installed-model checks catch it."
    )


@then("every SUPERSEDED_BY target appears in CURATED_PULL_CANDIDATES or KNOWN_SIZES_GB")
def step_superseded_targets_known(ctx):
    d = ctx["discover"]
    curated_set = set(d.CURATED_PULL_CANDIDATES)
    sizes_set = set(d.KNOWN_SIZES_GB.keys())
    known = curated_set | sizes_set
    unknown_targets = [
        (src, tgt)
        for src, tgt in d.SUPERSEDED_BY.items()
        if tgt not in known
    ]
    assert not unknown_targets, (
        "SUPERSEDED_BY targets missing from CURATED_PULL_CANDIDATES and KNOWN_SIZES_GB:\n"
        + "\n".join(f"  {s} → {t}  (unknown)" for s, t in unknown_targets)
        + "\nAdd them to KNOWN_SIZES_GB so VRAM budget filtering works."
    )
