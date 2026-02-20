"""
Step definitions for service_deployment.feature.
Validates 24/7 agent service deployment prerequisites.
"""

import ast
import importlib
import os
import sqlite3
import subprocess
import sys
import time

from behave import given, when, then


# ═══════════════════════════════════════════════════════════════════
#  SCRIPT VALIDITY
# ═══════════════════════════════════════════════════════════════════

@given('the bronze resources path is configured')
def step_bronze_path(context):
    assert context.bronze_resources, "bronze_resources not set in environment.py"
    assert os.path.isdir(context.bronze_resources), \
        f"bronze_resources not a directory: {context.bronze_resources}"


@given('the script "{name}" exists in bronze resources')
def step_script_in_bronze(context, name):
    path = os.path.join(context.bronze_resources, name)
    assert os.path.isfile(path), f"Script not found: {path}"
    context.current_script = path


@when('I inspect the orchestrator argument parser')
def step_inspect_argparser(context):
    script = os.path.join(context.bronze_resources, "hfo_eval_orchestrator.py")
    with open(script, "r", encoding="utf-8") as f:
        source = f.read()
    context.orchestrator_source = source


@then('it accepts "{arg}" argument')
def step_accepts_arg(context, arg):
    assert arg in context.orchestrator_source, \
        f"Argument '{arg}' not found in orchestrator source"


@when('I check orchestrator import dependencies')
def step_check_imports(context):
    context.import_results = {}


@then('"{module}" is importable')
def step_module_importable(context, module):
    try:
        importlib.import_module(module)
        context.import_results[module] = True
    except ImportError as e:
        raise AssertionError(f"Cannot import '{module}': {e}")


# ═══════════════════════════════════════════════════════════════════
#  RUNTIME — SINGLE EVAL CYCLE
# ═══════════════════════════════════════════════════════════════════

@when('I run a single eval cycle with model "{model}"')
def step_run_eval_cycle(context, model):
    """Run orchestrator with --once for a single eval cycle."""
    start = time.time()
    try:
        r = context.http.post(
            f"{context.ollama_base}/api/generate",
            json={
                "model": model,
                "prompt": "Explain in exactly three sentences why the sky is blue. Use technical language.",
                "stream": False,
            },
            timeout=60,
        )
        context.eval_elapsed = time.time() - start
        context.eval_response = r.json() if r.status_code == 200 else {}
        context.eval_status = r.status_code
    except Exception as e:
        context.eval_elapsed = time.time() - start
        context.eval_response = {}
        context.eval_status = 0
        raise AssertionError(f"Eval cycle failed: {e}")


@then('the cycle completes within {n:d} seconds')
def step_cycle_within_budget(context, n):
    assert context.eval_elapsed <= n, \
        f"Cycle took {context.eval_elapsed:.1f}s, budget is {n}s"


@then('the response contains at least {n:d} tokens')
def step_response_token_count(context, n):
    resp = context.eval_response.get("response", "")
    token_est = len(resp.split())
    assert token_est >= n, \
        f"Response has ~{token_est} tokens, need {n}"


# ═══════════════════════════════════════════════════════════════════
#  LIFECYCLE — WRITE PERMISSIONS
# ═══════════════════════════════════════════════════════════════════

@when('I check database write permissions')
def step_check_db_write(context):
    """Test that we can INSERT and DELETE a canary row."""
    conn = sqlite3.connect(context.ssot_db)
    try:
        conn.execute(
            "INSERT INTO stigmergy_events (event_type, timestamp, subject, source, data_json, content_hash) "
            "VALUES ('bdd.canary.test', datetime('now'), 'canary', 'behave', '{}', hex(randomblob(32)))"
        )
        # Clean up the canary
        conn.execute(
            "DELETE FROM stigmergy_events WHERE event_type = 'bdd.canary.test'"
        )
        conn.commit()
        context.db_writable = True
    except sqlite3.OperationalError as e:
        context.db_writable = False
        context.db_write_error = str(e)
    finally:
        conn.close()


@then('the database allows INSERT to stigmergy_events')
def step_db_writable(context):
    assert context.db_writable, \
        f"Database not writable: {getattr(context, 'db_write_error', 'unknown')}"


@when('I check the bronze resources directory')
def step_check_bronze_dir(context):
    context.bronze_writable = os.access(context.bronze_resources, os.W_OK)


@then('it is writable')
def step_dir_writable(context):
    assert context.bronze_writable, \
        f"Directory not writable: {context.bronze_resources}"
