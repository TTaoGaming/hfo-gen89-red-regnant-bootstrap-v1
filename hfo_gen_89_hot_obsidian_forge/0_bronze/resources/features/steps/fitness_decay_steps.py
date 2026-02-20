"""
Step definitions for fitness_decay.feature — Fitness Decay Half-Life SBE/ATDD.
RED PHASE: Fitness decay module does not exist yet.
"""

import math
import sqlite3
from datetime import datetime, timedelta, timezone

from behave import given, when, then


@when('I query mission_state tasks')
def step_query_tasks(context):
    cur = context.db_conn.execute(
        "SELECT * FROM mission_state WHERE thread_type = 'task'"
    )
    context.task_rows = cur.fetchall()
    context.task_columns = [desc[0] for desc in cur.description]


@then('each task row has a non-null last_touched timestamp')
def step_tasks_have_timestamp(context):
    assert len(context.task_rows) > 0, "No tasks in mission_state"
    for row in context.task_rows:
        row_dict = dict(zip(context.task_columns, row))
        last_touched = row_dict.get("updated_at")
        assert last_touched is not None, \
            f"Task {row_dict.get('thread_key', '?')} has no updated_at timestamp — RED gap."


@given('the fitness decay module is importable')
def step_decay_importable(context):
    try:
        from hfo_fitness_decay import compute_decayed_fitness
        context.compute_decayed_fitness = compute_decayed_fitness
    except ImportError:
        assert False, \
            "hfo_fitness_decay module does not exist — RED gap. " \
            "Must create fitness decay implementation."


@when('I call compute_decayed_fitness with fitness {fitness:f} and age {days:d} days')
def step_call_decay(context, fitness, days):
    context.decayed_fitness = context.compute_decayed_fitness(
        fitness=fitness, age_days=days
    )


@then('the decayed fitness is less than {threshold:f}')
def step_less_than(context, threshold):
    assert context.decayed_fitness < threshold, \
        f"Decayed fitness {context.decayed_fitness} not less than {threshold}"


@given('a task with fitness {fitness:f} last touched {days:d} day ago')
@given('a task with fitness {fitness:f} last touched {days:d} days ago')
def step_task_with_age(context, fitness, days):
    context.test_fitness = fitness
    context.test_age_days = days


@when('I compute decayed fitness with half-life {hl:d} days')
def step_compute_with_halflife(context, hl):
    try:
        from hfo_fitness_decay import compute_decayed_fitness
        context.decayed_fitness = compute_decayed_fitness(
            fitness=context.test_fitness,
            age_days=context.test_age_days,
            half_life_days=hl,
        )
    except ImportError:
        assert False, "hfo_fitness_decay module not implemented — RED gap"


@then('the decayed fitness is approximately {expected:f}')
def step_approx_fitness(context, expected):
    assert abs(context.decayed_fitness - expected) < 0.05, \
        f"Decayed fitness {context.decayed_fitness:.4f} not approximately {expected}"


@then('the decayed fitness is at least {minimum:f}')
def step_min_fitness(context, minimum):
    assert context.decayed_fitness >= minimum, \
        f"Decayed fitness {context.decayed_fitness:.4f} below minimum {minimum}"
