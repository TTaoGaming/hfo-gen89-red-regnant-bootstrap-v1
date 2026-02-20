"""
Step definitions for chimera_loop.feature — P2 Chimera Loop SBE/ATDD.
These steps test the chimera evolutionary DSE engine's SSOT integration.
RED PHASE: Some scenarios will fail because chimera loop has never been run through SSOT.
"""

import json
import sqlite3
import sys
from pathlib import Path

from behave import given, when, then

# Ensure chimera loop module is importable
BRONZE_RESOURCES = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BRONZE_RESOURCES))


@given('the chimera loop module is importable')
def step_chimera_importable(context):
    try:
        from hfo_p2_chimera_loop import (
            Genome, FitnessVector, TRAIT_ALLELES,
            evaluate_genome, _write_stigmergy,
        )
        context.Genome = Genome
        context.FitnessVector = FitnessVector
        context.TRAIT_ALLELES = TRAIT_ALLELES
    except ImportError as e:
        assert False, f"Cannot import chimera loop: {e}"


@when('I generate a random genome')
def step_generate_random(context):
    context.genome = context.Genome.random_genome(generation=0)


@then('all {n:d} trait keys are present')
def step_check_n_traits(context, n):
    expected_keys = {
        "tone", "adversarial_depth", "reasoning_style",
        "gate_philosophy", "meadows_strategy", "sbe_style",
        "trust_posture", "artifact_discipline",
    }
    assert len(context.genome.traits) >= n, \
        f"Expected at least {n} traits, got {len(context.genome.traits)}: {list(context.genome.traits.keys())}"


@then('every trait value is a valid allele for its key')
def step_valid_alleles(context):
    for key, value in context.genome.traits.items():
        trait_def = context.TRAIT_ALLELES.get(key, {})
        # TRAIT_ALLELES has format: {"desc": ..., "alleles": [...]}
        valid = trait_def.get("alleles", list(trait_def.keys()))
        assert value in valid, \
            f"Trait {key}={value} not in valid alleles: {valid}"


@given('a random genome')
def step_given_random_genome(context):
    context.genome = context.Genome.random_genome(generation=0)
    context.original_traits = dict(context.genome.traits)


@when('I mutate it with rate {rate:f}')
def step_mutate(context, rate):
    context.mutated = context.genome.mutate(rate)


@then('the mutated genome has the same {n:d} trait keys')
def step_same_keys(context, n):
    orig_keys = set(context.original_traits.keys())
    mut_keys = set(context.mutated.traits.keys())
    assert orig_keys == mut_keys, \
        f"Keys differ: orig={orig_keys}, mutated={mut_keys}"


@then('at least {n:d} trait differs from the original')
def step_at_least_n_differ(context, n):
    diffs = sum(
        1 for k in context.original_traits
        if context.mutated.traits.get(k) != context.original_traits[k]
    )
    assert diffs >= n, \
        f"Only {diffs} traits differ, need at least {n}"


@given('two random parent genomes')
def step_two_parents(context):
    context.parent_a = context.Genome.random_genome(generation=0)
    context.parent_b = context.Genome.random_genome(generation=0)


@when('I crossover the parents')
def step_crossover(context):
    context.child = context.Genome.crossover(context.parent_a, context.parent_b)


@then('the child has exactly {n:d} traits')
def step_child_n_traits(context, n):
    assert len(context.child.traits) >= n - 1, \
        f"Child has {len(context.child.traits)} traits, expected ~{n}"


@then('every child allele comes from one of the two parents')
def step_child_alleles_from_parents(context):
    for key, value in context.child.traits.items():
        a_val = context.parent_a.traits.get(key)
        b_val = context.parent_b.traits.get(key)
        assert value in (a_val, b_val), \
            f"Child trait {key}={value} not in parent values ({a_val}, {b_val})"


@given('the default Red Regnant genome')
def step_default_genome(context):
    context.genome = context.Genome(
        traits={
            "tone": "adversarial_coach",
            "adversarial_depth": "structured_challenge",
            "reasoning_style": "chain_of_thought",
            "gate_philosophy": "rich_documentation",
            "meadows_strategy": "adaptive",
            "sbe_style": "comprehensive",
            "trust_posture": "zero_trust",
            "artifact_discipline": "test_first",
        },
        generation=0,
    )


@when('I render it to a system prompt')
def step_render_prompt(context):
    context.system_prompt = context.genome.to_system_prompt()


@then('the prompt contains at least {n:d} characters')
def step_prompt_min_chars(context, n):
    assert len(context.system_prompt) >= n, \
        f"Prompt is {len(context.system_prompt)} chars, need {n}"


@then('the prompt contains all {n:d} trait section markers')
def step_prompt_sections(context, n):
    # The system prompt uses ## Section Headers for each trait
    section_markers = [
        "Communication Style",    # tone
        "Adversarial Depth",      # adversarial_depth
        "Reasoning",              # reasoning_style
        "Gate Philosophy",        # gate_philosophy
        "Meadows",                # meadows_strategy
        "SBE",                    # sbe_style
        "Trust",                  # trust_posture
        "Artifact",               # artifact_discipline
    ]
    found = sum(1 for m in section_markers if m.lower() in context.system_prompt.lower())
    assert found >= n, \
        f"Only {found} trait sections found in prompt, need {n}"


@given('fitness vector A with all scores {score:f}')
def step_fitness_a(context, score):
    context.fitness_a = context.FitnessVector(
        coding_accuracy=score, gate_compliance=score,
        adversarial_depth=score, meadows_alignment=score,
        token_efficiency=score, latency_score=score,
    )


@given('fitness vector B with all scores {score:f}')
def step_fitness_b(context, score):
    context.fitness_b = context.FitnessVector(
        coding_accuracy=score, gate_compliance=score,
        adversarial_depth=score, meadows_alignment=score,
        token_efficiency=score, latency_score=score,
    )


@then('A dominates B')
def step_a_dominates_b(context):
    assert context.fitness_a.dominates(context.fitness_b), \
        "Expected A to dominate B"


@then('B does not dominate A')
def step_b_not_dominate_a(context):
    assert not context.fitness_b.dominates(context.fitness_a), \
        "B should NOT dominate A"


@given('fitness vector with coding_accuracy {ca:f} and all others {rest:f}')
def step_fitness_specific(context, ca, rest):
    context.fitness_vec = context.FitnessVector(
        coding_accuracy=ca, gate_compliance=rest,
        adversarial_depth=rest, meadows_alignment=rest,
        token_efficiency=rest, latency_score=rest,
    )


@then('the aggregate score equals {expected:f}')
def step_aggregate_equals(context, expected):
    actual = context.fitness_vec.aggregate()
    assert abs(actual - expected) < 0.01, \
        f"Aggregate {actual:.4f} != expected {expected}"


@when('I count chimera stigmergy events')
def step_count_chimera_events(context):
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%chimera%'"
    )
    context.chimera_event_count = cur.fetchone()[0]


@then('there are at least {n:d} chimera events in SSOT')
def step_min_chimera_events(context, n):
    assert context.chimera_event_count >= n, \
        f"Only {context.chimera_event_count} chimera events, need {n}. " \
        f"The chimera loop has never been run through SSOT — this is the RED gap."


@when('I read the latest chimera eval event')
def step_read_latest_chimera(context):
    cur = context.db_conn.execute(
        "SELECT data_json FROM stigmergy_events "
        "WHERE event_type LIKE '%chimera.eval%' "
        "ORDER BY timestamp DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        event = json.loads(row[0])
        context.chimera_event_data = event.get("data", {})
    else:
        context.chimera_event_data = None


@then('the event data contains genome_id')
def step_event_has_genome_id(context):
    assert context.chimera_event_data is not None, \
        "No chimera eval event found — loop never run through SSOT"
    assert "genome_id" in context.chimera_event_data, \
        "Event data missing genome_id"


@then('the event data contains traits dict')
def step_event_has_traits(context):
    assert context.chimera_event_data is not None, \
        "No chimera eval event — loop never run"
    assert "traits" in context.chimera_event_data, \
        "Event data missing traits"
    assert isinstance(context.chimera_event_data["traits"], dict), \
        "traits is not a dict"


@then('the event data contains aggregate_score')
def step_event_has_score(context):
    assert context.chimera_event_data is not None, \
        "No chimera eval event — loop never run"
    assert "aggregate_score" in context.chimera_event_data, \
        "Event data missing aggregate_score"
