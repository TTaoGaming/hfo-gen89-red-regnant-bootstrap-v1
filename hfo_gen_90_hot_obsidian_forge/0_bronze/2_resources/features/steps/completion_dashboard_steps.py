"""
Step definitions for completion_dashboard.feature.
Validates Pareto completion metrics across the braided mission thread.
"""

import sqlite3
from datetime import datetime, timedelta

from behave import given, when, then


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD DATA
# ═══════════════════════════════════════════════════════════════════

@when('I count mission_state tasks')
def step_count_ms_tasks(context):
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM mission_state WHERE thread_type = 'task'")
    context.ms_task_count = cur.fetchone()[0]


@then('there are at least {n:d} tasks')
def step_min_tasks(context, n):
    assert context.ms_task_count >= n, \
        f"Only {context.ms_task_count} tasks, need {n}"


@when('I calculate average task fitness')
def step_avg_fitness(context):
    cur = context.db_conn.execute(
        "SELECT AVG(fitness) FROM mission_state WHERE thread_type = 'task'")
    context.avg_fitness = cur.fetchone()[0] or 0.0


@then('the average is above {val:f}')
def step_avg_above(context, val):
    assert context.avg_fitness > val, \
        f"Average fitness {context.avg_fitness:.3f} <= {val}"


@when('I query all task fitness values')
def step_all_fitness(context):
    cur = context.db_conn.execute(
        "SELECT thread_key, fitness FROM mission_state "
        "WHERE thread_type = 'task'")
    context.all_fitness = cur.fetchall()


@then('every fitness is between {lo:f} and {hi:f}')
def step_fitness_range(context, lo, hi):
    violations = [(k, f) for k, f in context.all_fitness
                  if f < lo or f > hi]
    assert not violations, \
        f"Fitness out of range [{lo}, {hi}]: {violations}"


# ═══════════════════════════════════════════════════════════════════
#  CONFIDENCE DISTRIBUTION
# ═══════════════════════════════════════════════════════════════════

@when('I count tasks with fitness at least {val:f}')
def step_count_high_fitness(context, val):
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM mission_state "
        "WHERE thread_type = 'task' AND fitness >= ?", (val,))
    context.high_count = cur.fetchone()[0]


@then('there are at least {n:d} in the HIGH tier')
def step_min_high(context, n):
    assert context.high_count >= n, \
        f"Only {context.high_count} tasks in HIGH tier, need {n}"


@when('I count tasks with fitness below {val:f}')
def step_count_low_fitness(context, val):
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM mission_state "
        "WHERE thread_type = 'task' AND fitness < ?", (val,))
    context.low_count = cur.fetchone()[0]


@then('there are at most {n:d} in the LOW tier')
def step_max_low(context, n):
    assert context.low_count <= n, \
        f"{context.low_count} tasks in LOW tier, max allowed {n}"


# ═══════════════════════════════════════════════════════════════════
#  BRAIDED THREAD VELOCITY
# ═══════════════════════════════════════════════════════════════════

@when('I count stigmergy events in the last 24 hours')
def step_recent_events(context):
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE timestamp >= ?",
        (cutoff,))
    context.recent_event_count = cur.fetchone()[0]


@then('there are at least {n:d} recent events')
def step_min_recent(context, n):
    assert context.recent_event_count >= n, \
        f"Only {context.recent_event_count} events in last 24h, need {n}"


@when('I count yield events vs perceive events in the last 24 hours')
def step_yield_vs_perceive(context):
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    cur_y = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE timestamp >= ? AND event_type LIKE '%yield%'",
        (cutoff,))
    context.recent_yields = cur_y.fetchone()[0]

    cur_p = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE timestamp >= ? AND event_type LIKE '%perceive%'",
        (cutoff,))
    context.recent_perceives = cur_p.fetchone()[0]


@then('the yield-to-perceive ratio is at least {val:f}')
def step_yield_ratio(context, val):
    if context.recent_perceives == 0:
        ratio = 0.0
    else:
        ratio = context.recent_yields / context.recent_perceives
    assert ratio >= val, \
        f"Yield/Perceive ratio {ratio:.2f} ({context.recent_yields}/{context.recent_perceives}) < {val}"
