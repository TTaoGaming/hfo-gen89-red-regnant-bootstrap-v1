"""
Step definitions for ssot_health.feature and agent_readiness.feature.
"""

import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

from behave import given, when, then


# ═══════════════════════════════════════════════════════════════════
#  SSOT HEALTH
# ═══════════════════════════════════════════════════════════════════

@given('the SSOT database path is configured')
def step_db_path_configured(context):
    assert context.ssot_db, "ssot_db not set in environment.py"


@then('the database file exists on disk')
def step_db_exists_on_disk(context):
    assert os.path.isfile(context.ssot_db), \
        f"SSOT DB not found at {context.ssot_db}"


@given('the SSOT database is connected')
def step_db_connected(context):
    assert os.path.isfile(context.ssot_db), \
        f"SSOT DB not found at {context.ssot_db}"
    context.db_conn = sqlite3.connect(context.ssot_db)


@when('I count documents')
def step_count_documents(context):
    cur = context.db_conn.execute("SELECT COUNT(*) FROM documents")
    context.doc_count = cur.fetchone()[0]


@then('there are at least the configured minimum documents')
def step_min_documents(context):
    n = context.thresholds["min_ssot_docs"]
    assert context.doc_count >= n, \
        f"Only {context.doc_count} documents, need {n}"


@when('I search FTS for "{term}"')
def step_fts_search(context, term):
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM documents WHERE id IN "
        "(SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?)",
        (term,))
    context.fts_hits = cur.fetchone()[0]


@then('at least {n:d} result is returned')
def step_fts_results(context, n):
    assert context.fts_hits >= n, \
        f"FTS returned {context.fts_hits} hits, need {n}"


@when('I count stigmergy events')
def step_count_stigmergy(context):
    cur = context.db_conn.execute("SELECT COUNT(*) FROM stigmergy_events")
    context.stigmergy_count = cur.fetchone()[0]


@then('there are at least the configured minimum events')
def step_min_stigmergy(context):
    n = context.thresholds["min_stigmergy_events"]
    assert context.stigmergy_count >= n, \
        f"Only {context.stigmergy_count} stigmergy events, need {n}"


@when('I query the latest stigmergy event')
def step_latest_stigmergy(context):
    cur = context.db_conn.execute(
        "SELECT MAX(timestamp) FROM stigmergy_events")
    row = cur.fetchone()
    if row and row[0]:
        ts = row[0].replace("T", " ")[:19]
        try:
            context.last_stigmergy = datetime.fromisoformat(ts)
        except ValueError:
            context.last_stigmergy = None
    else:
        context.last_stigmergy = None


@then('the latest event timestamp is within the last {n:d} days')
def step_recent_check(context, n):
    assert context.last_stigmergy is not None, \
        "No stigmergy timestamps found"
    cutoff = datetime.utcnow() - timedelta(days=n)
    assert context.last_stigmergy >= cutoff, \
        f"Last stigmergy at {context.last_stigmergy}, cutoff {cutoff}"


# ═══════════════════════════════════════════════════════════════════
#  AGENT READINESS
# ═══════════════════════════════════════════════════════════════════

def _syntax_check(script_path):
    """Run Python syntax check on a script."""
    r = subprocess.run(
        [sys.executable, "-m", "py_compile", script_path],
        capture_output=True, text=True, timeout=30)
    return r.returncode == 0, r.stderr


@given('the orchestrator script "{name}" exists')
def step_orchestrator_exists(context, name):
    path = os.path.join(context.bronze_resources, name)
    assert os.path.isfile(path), f"Script not found: {path}"
    context.current_script = path


@given('the script "{name}" exists')
def step_script_exists(context, name):
    path = os.path.join(context.bronze_resources, name)
    assert os.path.isfile(path), f"Script not found: {path}"
    context.current_script = path


@then('the script parses without syntax errors')
def step_syntax_valid(context):
    ok, err = _syntax_check(context.current_script)
    assert ok, f"Syntax error in {context.current_script}: {err}"


@when('I run perceive with probe "{probe}"')
def step_run_perceive(context, probe):
    script = os.path.join(context.bronze_resources, "hfo_perceive.py")
    r = subprocess.run(
        [sys.executable, script, "--json", "--probe", probe],
        capture_output=True, text=True, timeout=60,
        cwd=context.bronze_resources)
    context.perceive_rc = r.returncode
    context.perceive_out = r.stdout + r.stderr


@then('a perceive event is written to the SSOT')
def step_perceive_event(context):
    conn = sqlite3.connect(context.ssot_db)
    cur = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE event_type LIKE '%perceive%'")
    count = cur.fetchone()[0]
    conn.close()
    assert count > 0, "No perceive events found in SSOT"


@when('I run yield with summary "{summary}"')
def step_run_yield(context, summary):
    script = os.path.join(context.bronze_resources, "hfo_yield.py")
    r = subprocess.run(
        [sys.executable, script, "--summary", summary, "--json"],
        capture_output=True, text=True, timeout=60,
        cwd=context.bronze_resources)
    context.yield_rc = r.returncode
    context.yield_out = r.stdout + r.stderr


@then('a yield event is written to the SSOT')
def step_yield_event(context):
    conn = sqlite3.connect(context.ssot_db)
    cur = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE event_type LIKE '%yield%'")
    count = cur.fetchone()[0]
    conn.close()
    assert count > 0, "No yield events found in SSOT"
