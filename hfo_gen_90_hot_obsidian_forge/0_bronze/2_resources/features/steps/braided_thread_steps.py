"""
Step definitions for braided_thread.feature.
Validates mission_state table integrity in the SSOT database.
"""

import json
import sqlite3

from behave import given, when, then


# ═══════════════════════════════════════════════════════════════════
#  STRUCTURAL INTEGRITY
# ═══════════════════════════════════════════════════════════════════

@when('I inspect the mission_state table')
def step_inspect_mission_state(context):
    cur = context.db_conn.execute("PRAGMA table_info(mission_state)")
    context.ms_columns = [row[1] for row in cur.fetchall()]


@then('it has columns "{column_list}"')
def step_has_columns(context, column_list):
    expected = [c.strip() for c in column_list.split(",")]
    for col in expected:
        assert col in context.ms_columns, \
            f"Missing column '{col}' — found: {context.ms_columns}"


@when('I query mission threads')
def step_query_missions(context):
    cur = context.db_conn.execute(
        "SELECT thread_key, thread_type FROM mission_state "
        "WHERE thread_type = 'mission'")
    context.missions = {row[0]: row[1] for row in cur.fetchall()}


@then('thread "{key}" exists with type "{ttype}"')
def step_thread_exists_with_type(context, key, ttype):
    assert key in context.missions, \
        f"Thread '{key}' not found — have: {list(context.missions.keys())}"
    assert context.missions[key] == ttype, \
        f"Thread '{key}' is type '{context.missions[key]}', expected '{ttype}'"


@when('I query era threads')
def step_query_eras(context):
    cur = context.db_conn.execute(
        "SELECT thread_key, status, fitness FROM mission_state "
        "WHERE thread_type = 'era'")
    context.eras = {}
    for row in cur.fetchall():
        context.eras[row[0]] = {"status": row[1], "fitness": row[2]}


@then('thread "{key}" has status "{expected}"')
def step_thread_status(context, key, expected):
    assert key in context.eras, \
        f"Thread '{key}' not found in eras"
    actual = context.eras[key]["status"]
    assert actual == expected, \
        f"Thread '{key}' status is '{actual}', expected '{expected}'"


@then('thread "{key}" has fitness at least {val:f}')
def step_thread_fitness_min(context, key, val):
    data = context.eras.get(key) or context.task_detail
    assert data is not None, f"Thread '{key}' not found"
    actual = data.get("fitness", data.get("fitness", 0))
    assert actual >= val, \
        f"Thread '{key}' fitness {actual} < {val}"


# ═══════════════════════════════════════════════════════════════════
#  TASK COVERAGE
# ═══════════════════════════════════════════════════════════════════

@when('I query tasks grouped by port')
def step_tasks_by_port(context):
    cur = context.db_conn.execute(
        "SELECT port, COUNT(*) FROM mission_state "
        "WHERE thread_type = 'task' AND port IS NOT NULL "
        "GROUP BY port")
    context.tasks_by_port = {row[0]: row[1] for row in cur.fetchall()}


@then('port "{port}" has at least {n:d} task')
def step_port_task_count(context, port, n):
    count = context.tasks_by_port.get(port, 0)
    assert count >= n, \
        f"Port {port} has {count} tasks, need {n}"


@when('I query tasks with fitness above {val:f}')
def step_high_fitness_tasks(context, val):
    cur = context.db_conn.execute(
        "SELECT thread_key, fitness, mutation_confidence FROM mission_state "
        "WHERE thread_type = 'task' AND fitness >= ?", (val,))
    context.high_fitness_tasks = cur.fetchall()


@then('at least {n:d} tasks meet the threshold')
def step_min_high_fitness(context, n):
    actual = len(context.high_fitness_tasks)
    assert actual >= n, \
        f"Only {actual} tasks meet the threshold, need {n}"


@then('each has mutation_confidence above {val:d}')
def step_all_mutation_confidence(context, val):
    for key, fitness, mc in context.high_fitness_tasks:
        assert mc > val, \
            f"Task {key} (fitness {fitness}) has mutation_confidence {mc} <= {val}"


@when('I query thread "{key}"')
def step_query_specific_thread(context, key):
    cur = context.db_conn.execute(
        "SELECT title, fitness, port, status, mutation_confidence "
        "FROM mission_state WHERE thread_key = ?", (key,))
    row = cur.fetchone()
    assert row is not None, f"Thread '{key}' not found in mission_state"
    context.task_detail = {
        "title": row[0], "fitness": row[1], "port": row[2],
        "status": row[3], "mutation_confidence": row[4]
    }


@then('the title contains "{fragment}"')
def step_title_contains(context, fragment):
    actual = context.task_detail["title"]
    assert fragment.lower() in actual.lower(), \
        f"Title '{actual}' does not contain '{fragment}'"


@then('the title matches "{frag1}" or "{frag2}"')
def step_title_matches_or(context, frag1, frag2):
    actual = context.task_detail["title"].lower()
    assert frag1.lower() in actual or frag2.lower() in actual, \
        f"Title '{context.task_detail['title']}' doesn't contain '{frag1}' or '{frag2}'"


@then('the fitness is at least {val:f}')
def step_fitness_at_least(context, val):
    actual = context.task_detail["fitness"]
    assert actual >= val, \
        f"Fitness {actual} < {val}"


@then('the port is "{expected}"')
def step_port_is(context, expected):
    actual = context.task_detail["port"]
    assert actual == expected, \
        f"Port is '{actual}', expected '{expected}'"


@then('the status is "{expected}"')
def step_status_is(context, expected):
    actual = context.task_detail["status"]
    assert actual == expected, \
        f"Status is '{actual}', expected '{expected}'"


# ═══════════════════════════════════════════════════════════════════
#  PARENT-CHILD INTEGRITY
# ═══════════════════════════════════════════════════════════════════

@when('I query all tasks')
def step_query_all_tasks(context):
    cur = context.db_conn.execute(
        "SELECT thread_key, parent_key FROM mission_state "
        "WHERE thread_type = 'task'")
    context.all_tasks = cur.fetchall()
    cur2 = context.db_conn.execute(
        "SELECT thread_key FROM mission_state")
    context.all_thread_keys = {row[0] for row in cur2.fetchall()}


@then("every task's parent_key references an existing thread")
def step_tasks_parented(context):
    orphans = [t[0] for t in context.all_tasks
               if t[1] not in context.all_thread_keys]
    assert not orphans, \
        f"Orphan tasks (parent_key not found): {orphans}"


@when('I query all waypoints')
def step_query_all_waypoints(context):
    cur = context.db_conn.execute(
        "SELECT thread_key, parent_key FROM mission_state "
        "WHERE thread_type = 'waypoint'")
    context.all_waypoints = cur.fetchall()
    # Get era keys
    cur2 = context.db_conn.execute(
        "SELECT thread_key FROM mission_state WHERE thread_type = 'era'")
    context.era_keys = {row[0] for row in cur2.fetchall()}


@then("every waypoint's parent_key references an existing era")
def step_waypoints_parented(context):
    orphans = [w[0] for w in context.all_waypoints
               if w[1] not in context.era_keys]
    assert not orphans, \
        f"Orphan waypoints (parent_key not found): {orphans}"
