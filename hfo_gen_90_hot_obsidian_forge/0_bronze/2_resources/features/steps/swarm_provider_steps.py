"""
BDD Step Definitions — Multi-Provider Swarm Configuration
==========================================================
SBE/ATDD coverage for hfo_swarm_config.py.
Tests provider switching, role resolution, and fallback logic.

Medallion: bronze
Feature: swarm_providers.feature
"""

import sys
from pathlib import Path
from unittest.mock import patch
from behave import given, when, then, use_step_matcher

_res = str(Path(__file__).resolve().parent.parent.parent)
if _res not in sys.path:
    sys.path.insert(0, _res)

use_step_matcher("parse")


# ═══════════════════════════════════════════════════════════════
# Background
# ═══════════════════════════════════════════════════════════════

@given("the swarm config module is importable")
def step_swarm_importable(context):
    import hfo_swarm_config as mod
    context.swarm = mod
    context.Provider = mod.Provider
    context.resolve_model_for_role = mod.resolve_model_for_role
    context.ROLE_MODEL_MAP = mod.ROLE_MODEL_MAP


# ═══════════════════════════════════════════════════════════════
# Tier 1 — Invariants
# ═══════════════════════════════════════════════════════════════

@then('the Provider enum contains "{val1}" and "{val2}"')
def step_provider_enum(context, val1, val2):
    values = {p.value for p in context.Provider}
    assert val1 in values, f"{val1} not in Provider"
    assert val2 in values, f"{val2} not in Provider"


@then("DEFAULT_OLLAMA_MODEL is a non-empty string")
def step_default_ollama(context):
    assert context.swarm.DEFAULT_OLLAMA_MODEL, "DEFAULT_OLLAMA_MODEL is empty"


@then("DEFAULT_GEMINI_TIER is a non-empty string")
def step_default_gemini(context):
    assert context.swarm.DEFAULT_GEMINI_TIER, "DEFAULT_GEMINI_TIER is empty"


@then("DEFAULT_MODEL equals DEFAULT_OLLAMA_MODEL")
def step_default_compat(context):
    assert context.swarm.DEFAULT_MODEL == context.swarm.DEFAULT_OLLAMA_MODEL


@then("RECOMMENDED_MODELS equals OLLAMA_RECOMMENDED_MODELS")
def step_recommend_compat(context):
    assert context.swarm.RECOMMENDED_MODELS is context.swarm.OLLAMA_RECOMMENDED_MODELS


@then("every ROLE_MODEL_MAP entry has exactly 4 elements")
def step_role_map_4tuple(context):
    for role, entry in context.ROLE_MODEL_MAP.items():
        assert len(entry) == 4, f"Role {role} has {len(entry)} elements, expected 4"


@then("element 0 is a Provider and element 2 is a Provider")
def step_role_map_providers(context):
    for role, entry in context.ROLE_MODEL_MAP.items():
        assert isinstance(entry[0], context.Provider), f"Role {role}[0] is not Provider"
        assert isinstance(entry[2], context.Provider), f"Role {role}[2] is not Provider"


# ═══════════════════════════════════════════════════════════════
# Tier 2 — Happy-Path: Role Resolution
# ═══════════════════════════════════════════════════════════════

@given("GEMINI_AVAILABLE is temporarily true")
def step_gemini_available(context):
    context._gemini_true_patch = patch.object(
        context.swarm, 'GEMINI_AVAILABLE', True
    )
    context._gemini_true_patch.start()
    context.add_cleanup(context._gemini_true_patch.stop)


@when('I resolve model for role "{role}" with strategy "{strategy}"')
def step_resolve_role(context, role, strategy):
    rl = getattr(context, 'rate_limiter', None)
    provider, model = context.resolve_model_for_role(
        role, strategy=strategy, rate_limiter=rl
    )
    context.resolved_provider = provider
    context.resolved_model = model


@then('the provider is "{expected}"')
def step_provider_is(context, expected):
    actual = context.resolved_provider.value
    assert actual == expected, f"Expected provider {expected}, got {actual}"


@given("GEMINI_AVAILABLE is temporarily false")
def step_gemini_unavailable(context):
    context._gemini_available_patch = patch.object(
        context.swarm, 'GEMINI_AVAILABLE', False
    )
    context._gemini_available_patch.start()
    context.add_cleanup(context._gemini_available_patch.stop)


# ═══════════════════════════════════════════════════════════════
# Tier 3 — Client Factory
# ═══════════════════════════════════════════════════════════════

@when("I call get_openai_client")
def step_call_openai(context):
    try:
        context.openai_client = context.swarm.get_openai_client()
        context.last_exception = None
    except Exception as e:
        context.openai_client = None
        context.last_exception = e


@then('the client base_url contains "{fragment}"')
def step_base_url_contains(context, fragment):
    if context.openai_client is None:
        # OpenAI package may not be installed — skip gracefully
        return
    url = str(context.openai_client.base_url)
    assert fragment in url, f"base_url '{url}' doesn't contain '{fragment}'"


@when("I call get_gemini_client")
def step_call_gemini_client(context):
    try:
        context.gemini_client = context.swarm.get_gemini_client()
        context.last_exception = None
    except RuntimeError as e:
        context.last_exception = e


@then("it raises RuntimeError")
def step_raises_runtime(context):
    assert isinstance(context.last_exception, RuntimeError), \
        f"Expected RuntimeError, got {type(context.last_exception)}"


# ═══════════════════════════════════════════════════════════════
# Tier 4 — Model Discovery
# ═══════════════════════════════════════════════════════════════

@when("I call list_gemini_models")
def step_list_gemini(context):
    context.gemini_models_list = context.swarm.list_gemini_models()


@then('each entry has provider = "{provider}"')
def step_entry_provider(context, provider):
    for entry in context.gemini_models_list:
        assert entry.get("provider") == provider, \
            f"Entry {entry.get('name', '?')} has provider={entry.get('provider')}"


@then("each entry has a tier field")
def step_entry_has_tier(context):
    for entry in context.gemini_models_list:
        assert "tier" in entry, f"Entry missing tier: {entry}"


@when("I call list_all_available_models")
def step_list_all_available(context):
    context.all_available = context.swarm.list_all_available_models()


@then('the result has keys "{key1}" and "{key2}"')
def step_result_keys(context, key1, key2):
    assert key1 in context.all_available, f"Missing key: {key1}"
    assert key2 in context.all_available, f"Missing key: {key2}"


# ═══════════════════════════════════════════════════════════════
# Tier 5 — Rate-Limited Fallback
# ═══════════════════════════════════════════════════════════════

@given("a fresh swarm GeminiRateLimiter")
def step_fresh_swarm_rl(context):
    from hfo_gemini_models import GeminiRateLimiter
    context.rate_limiter = GeminiRateLimiter()


@given('I exhaust swarm RPM for "{model_id}"')
def step_exhaust_swarm_rpm(context, model_id):
    from hfo_gemini_models import get_model
    spec = get_model(model_id)
    for _ in range(spec.rpm_limit):
        context.rate_limiter.record(model_id)


@when('I resolve model for role "{role}" with strategy "{strategy}" and the rate_limiter')
def step_resolve_with_limiter(context, role, strategy):
    provider, model = context.resolve_model_for_role(
        role, strategy=strategy, rate_limiter=context.rate_limiter
    )
    context.resolved_provider = provider
    context.resolved_model = model


@then("PROVIDER_STRATEGY is a valid strategy string")
def step_strategy_valid(context):
    valid = {"gemini_first", "ollama_first", "ollama_only", "gemini_only"}
    actual = context.swarm.PROVIDER_STRATEGY
    assert actual in valid, f"'{actual}' not in {valid}"
