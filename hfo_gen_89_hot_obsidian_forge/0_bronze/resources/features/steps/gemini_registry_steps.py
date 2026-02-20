"""
BDD Step Definitions — Gemini Tiered Model Registry
=====================================================
SBE/ATDD coverage for hfo_gemini_models.py.
Tests the pure Python registry logic (no live API calls).

Medallion: bronze
Feature: gemini_model_registry.feature
"""

import sys
from pathlib import Path
from behave import given, when, then, use_step_matcher

# Ensure bronze/resources is importable
_res = str(Path(__file__).resolve().parent.parent.parent)
if _res not in sys.path:
    sys.path.insert(0, _res)

use_step_matcher("parse")

# ═══════════════════════════════════════════════════════════════
# Background
# ═══════════════════════════════════════════════════════════════

@given("the Gemini model registry module is importable")
def step_registry_importable(context):
    import hfo_gemini_models as mod
    context.registry = mod
    context.GeminiTier = mod.GeminiTier
    context.GEMINI_MODELS = mod.GEMINI_MODELS
    context.get_model = mod.get_model
    context.GeminiRateLimiter = mod.GeminiRateLimiter
    context.select_tier = mod.select_tier
    context.SWARM_ROLE_MAP = mod.SWARM_ROLE_MAP
    context.list_all_models = mod.list_all_models
    context.get_thinking_models = mod.get_thinking_models


# ═══════════════════════════════════════════════════════════════
# Tier 1 — Invariants
# ═══════════════════════════════════════════════════════════════

CORE_TIERS = {"nano", "flash", "flash_25", "lite_25", "pro", "experimental"}

@then("the registry contains exactly these core tiers")
@then("the registry contains exactly these core tiers:")
def step_has_core_tiers(context):
    expected = {row["tier"] for row in context.table}
    actual_tiers = set()
    for spec in context.GEMINI_MODELS.values():
        if spec.tier.value in CORE_TIERS:
            actual_tiers.add(spec.tier.value)
    assert expected == actual_tiers, f"Expected {expected}, got {actual_tiers}"


@then("every core tier resolves to a non-empty model_id")
def step_core_tiers_resolve(context):
    for tier_name in CORE_TIERS:
        spec = context.get_model(tier_name)
        assert spec.model_id, f"Tier {tier_name} has empty model_id"


@then("every registered model has rpm_limit > 0")
def step_rpm_positive(context):
    for spec in context.GEMINI_MODELS.values():
        assert spec.rpm_limit > 0, f"{spec.model_id}: rpm_limit={spec.rpm_limit}"


@then("every registered model has rpd_limit > 0")
def step_rpd_positive(context):
    for spec in context.GEMINI_MODELS.values():
        assert spec.rpd_limit > 0, f"{spec.model_id}: rpd_limit={spec.rpd_limit}"


@when('I look up the "{tier}" tier')
def step_lookup_tier(context, tier):
    context.looked_up_spec = context.get_model(tier)


@then("the model spec has supports_thinking = true")
def step_supports_thinking(context):
    assert context.looked_up_spec.supports_thinking is True, \
        f"{context.looked_up_spec.model_id} has supports_thinking={context.looked_up_spec.supports_thinking}"


@then("the model spec has the highest rpm_limit among core tiers")
def step_highest_rpm(context):
    spec = context.looked_up_spec
    core_specs = [s for s in context.GEMINI_MODELS.values() if s.tier.value in CORE_TIERS]
    max_rpm = max(s.rpm_limit for s in core_specs)
    assert spec.rpm_limit == max_rpm, \
        f"nano rpm={spec.rpm_limit} but max is {max_rpm}"


@given("GEMINI_API_KEY is set in the registry module")
def step_api_key_set(context):
    # The registry should have loaded the key from env
    pass


@then("the registry's GEMINI_API_KEY is a non-empty string")
def step_api_key_nonempty(context):
    key = context.registry.GEMINI_API_KEY
    assert isinstance(key, str) and len(key) > 0, "GEMINI_API_KEY is empty or missing"


@then("the registry module has a GEMINI_API_KEY attribute of type str")
def step_api_key_attr_exists(context):
    assert hasattr(context.registry, 'GEMINI_API_KEY'), "GEMINI_API_KEY attr missing"
    assert isinstance(context.registry.GEMINI_API_KEY, str), "GEMINI_API_KEY is not str"


# ═══════════════════════════════════════════════════════════════
# Tier 2 — Happy-Path
# ═══════════════════════════════════════════════════════════════

@when('I call get_model with "{tier}"')
def step_get_model_tier(context, tier):
    context.result_spec = context.get_model(tier)


@when('I call get_model with alias "{alias}"')
def step_get_model_alias(context, alias):
    context.result_spec = context.get_model(alias)


@when('I call get_model with model_id "{model_id}"')
def step_get_model_model_id(context, model_id):
    context.result_spec = context.get_model(model_id)


@then('the model_id is "{expected}"')
def step_model_id_is(context, expected):
    assert context.result_spec.model_id == expected, \
        f"Expected {expected}, got {context.result_spec.model_id}"


@then('the resolved tier is "{expected_tier}"')
def step_resolved_tier_is(context, expected_tier):
    assert context.result_spec.tier.value == expected_tier, \
        f"Expected tier {expected_tier}, got {context.result_spec.tier.value}"


@when("I get the list of thinking models")
def step_get_thinking_models(context):
    context.thinking_models = context.get_thinking_models()


@then('it contains at least "{tier1}" and "{tier2}"')
def step_thinking_contains(context, tier1, tier2):
    tiers = {s.tier.value for s in context.thinking_models}
    assert tier1 in tiers, f"{tier1} not in thinking models: {tiers}"
    assert tier2 in tiers, f"{tier2} not in thinking models: {tiers}"


@then('it does not contain "{tier1}" or "{tier2}"')
def step_thinking_excludes(context, tier1, tier2):
    tiers = {s.tier.value for s in context.thinking_models}
    assert tier1 not in tiers, f"{tier1} should not be in thinking models"
    assert tier2 not in tiers, f"{tier2} should not be in thinking models"


@when("I call list_all_models")
def step_list_all(context):
    context.all_models_list = context.list_all_models()


@then("each entry has keys: model_id, tier, display_name, rpm_limit, rpd_limit, supports_thinking")
def step_entry_has_keys(context):
    required_keys = {"model_id", "tier", "display_name", "rpm_limit", "rpd_limit", "supports_thinking"}
    for entry in context.all_models_list:
        assert required_keys.issubset(entry.keys()), \
            f"Entry missing keys: {required_keys - entry.keys()}"


# ═══════════════════════════════════════════════════════════════
# Tier 3 — Rate Limiter
# ═══════════════════════════════════════════════════════════════

@given("a fresh GeminiRateLimiter")
def step_fresh_rate_limiter(context):
    context.rate_limiter = context.GeminiRateLimiter()


@when('I check rate limit for "{model_id}"')
def step_check_rate_limit(context, model_id):
    context.rl_allowed, context.rl_reason = context.rate_limiter.check(model_id)


@then("it is allowed")
def step_is_allowed(context):
    assert context.rl_allowed is True, f"Expected allowed, got blocked: {context.rl_reason}"


@then("it is blocked with reason containing {keyword}")
def step_is_blocked_with(context, keyword):
    kw = keyword.strip('"').strip("'")
    assert context.rl_allowed is False, "Expected blocked, but was allowed"
    assert kw in context.rl_reason, \
        f"Expected '{kw}' in reason, got: {context.rl_reason}"


@given('I record {count:d} calls for "{model_id}" within 1 minute')
def step_record_calls_minute(context, count, model_id):
    for _ in range(count):
        context.rate_limiter.record(model_id)


@given('I record {count:d} calls for "{model_id}"')
def step_record_calls(context, count, model_id):
    for _ in range(count):
        context.rate_limiter.record(model_id)


@when("I get the usage summary")
def step_get_usage_summary(context):
    context.usage_summary = context.rate_limiter.usage_summary()


@then('"{model_id}" shows {count:d} calls used')
def step_usage_shows_count(context, model_id, count):
    model_usage = context.usage_summary.get(model_id, {})
    actual = model_usage.get("rpd_used", 0)
    assert actual == count, f"Expected {count} calls for {model_id}, got {actual}"


@given('I exhaust the RPM for "{model_id}"')
def step_exhaust_rpm(context, model_id):
    # Find the model's RPM limit and fill it
    spec = context.get_model(model_id) if hasattr(context, 'get_model') else None
    if spec is None:
        from hfo_gemini_models import get_model
        spec = get_model(model_id)
    rpm = spec.rpm_limit
    for _ in range(rpm):
        context.rate_limiter.record(model_id)


# ═══════════════════════════════════════════════════════════════
# Tier 4 — Smart Selector
# ═══════════════════════════════════════════════════════════════

@when('I call select_tier with task_complexity "{complexity}"')
def step_select_tier(context, complexity):
    result = context.select_tier(task_complexity=complexity)
    context.selected_tier = result.tier.value


@then('the selected tier is in "{tier_csv}"')
def step_selected_in(context, tier_csv):
    allowed = {t.strip() for t in tier_csv.split(",")}
    assert context.selected_tier in allowed, \
        f"Selected {context.selected_tier}, expected one of {allowed}"


@when('I call select_tier with task_complexity "{complexity}" and the rate_limiter')
def step_select_tier_with_limiter(context, complexity):
    result = context.select_tier(
        task_complexity=complexity,
        rate_limiter=context.rate_limiter
    )
    context.selected_tier = result.tier.value


@then('the selected tier is NOT "{tier}"')
def step_selected_not(context, tier):
    assert context.selected_tier != tier, \
        f"Expected NOT {tier}, but got {context.selected_tier}"


@when('I call select_tier with task_complexity "{complexity}" and is_batch true')
def step_select_tier_batch(context, complexity):
    result = context.select_tier(task_complexity=complexity, is_batch=True)
    context.selected_tier = result.tier.value


# ═══════════════════════════════════════════════════════════════
# Tier 5 — SWARM_ROLE_MAP
# ═══════════════════════════════════════════════════════════════

@then("SWARM_ROLE_MAP has entries for at least these roles")
@then("SWARM_ROLE_MAP has entries for at least these roles:")
def step_role_map_has_roles(context):
    required_roles = {row["role"] for row in context.table}
    actual_roles = set(context.SWARM_ROLE_MAP.keys())
    missing = required_roles - actual_roles
    assert not missing, f"Missing roles in SWARM_ROLE_MAP: {missing}"


@then('SWARM_ROLE_MAP maps "{role}" to "{tier}"')
def step_role_maps_to(context, role, tier):
    actual = context.SWARM_ROLE_MAP.get(role)
    if hasattr(actual, 'value'):
        actual = actual.value
    assert actual == tier, f"Role {role} maps to {actual}, expected {tier}"
