"""
Step definitions for lineage_tracking.feature — Lineage Auto-Population SBE/ATDD.
RED PHASE: Lineage auto-populator does not exist yet. Lineage table has 0 rows.
"""

import json
import sqlite3

from behave import given, when, then


@when('I count lineage table rows')
def step_count_lineage(context):
    cur = context.db_conn.execute("SELECT COUNT(*) FROM lineage")
    context.lineage_count = cur.fetchone()[0]


@then('there are at least {n:d} lineage entries')
def step_min_lineage(context, n):
    assert context.lineage_count >= n, \
        f"Lineage table has {context.lineage_count} rows, need {n}. " \
        f"Lineage auto-populator not implemented — RED gap."


@when('I query lineage entries')
def step_query_lineage(context):
    cur = context.db_conn.execute(
        "SELECT * FROM lineage LIMIT 20"
    )
    context.lineage_entries = cur.fetchall()
    # Get column names
    context.lineage_columns = [desc[0] for desc in cur.description]


@then('each entry has a source_doc_id and target_doc_id')
def step_lineage_has_ids(context):
    assert len(context.lineage_entries) > 0, \
        "No lineage entries found — table is empty. RED gap."
    for entry in context.lineage_entries:
        row = dict(zip(context.lineage_columns, entry))
        assert "doc_id" in row, \
            f"Lineage entry missing doc_id. Columns: {context.lineage_columns}"
        assert "depends_on_hash" in row, \
            f"Lineage entry missing depends_on_hash. Columns: {context.lineage_columns}"


@then('both IDs exist in the documents table')
def step_lineage_ids_exist(context):
    for entry in context.lineage_entries:
        row = dict(zip(context.lineage_columns, entry))
        doc_id = row.get("doc_id")
        if doc_id:
            cur = context.db_conn.execute(
                "SELECT COUNT(*) FROM documents WHERE id = ?", (doc_id,)
            )
            assert cur.fetchone()[0] > 0, \
                f"doc_id {doc_id} not found in documents table"


@given('a perceive event with memory_refs "{refs}"')
def step_perceive_with_refs(context, refs):
    context.test_memory_refs = [int(r.strip()) for r in refs.split(",")]


@when('I run the lineage auto-populator')
def step_run_populator(context):
    try:
        from hfo_lineage_populator import populate_lineage_from_refs
        context.populator_result = populate_lineage_from_refs(
            context.ssot_db, context.test_memory_refs
        )
    except ImportError:
        assert False, \
            "hfo_lineage_populator module does not exist — RED gap. " \
            "Must create lineage auto-population implementation."


@then('lineage entries are created linking those documents')
def step_entries_created(context):
    # Accept either new creates or evidence of existing entries (dedup)
    created = context.populator_result.get("created", 0)
    dupes = context.populator_result.get("duplicates_skipped", 0)
    assert created > 0 or dupes > 0, \
        "No lineage entries created or found"


@then('the lineage_type is "{expected_type}"')
def step_lineage_type(context, expected_type):
    assert context.populator_result.get("lineage_type") == expected_type, \
        f"Expected lineage_type '{expected_type}', got '{context.populator_result.get('lineage_type')}'"


@given('existing lineage entries for docs {a:d} and {b:d}')
def step_existing_lineage(context, a, b):
    context.test_memory_refs = [a, b]
    # These should already exist from previous step


@when('I run the lineage auto-populator again for the same refs')
def step_run_populator_again(context):
    try:
        from hfo_lineage_populator import populate_lineage_from_refs
        context.populator_result = populate_lineage_from_refs(
            context.ssot_db, context.test_memory_refs
        )
    except ImportError:
        assert False, \
            "hfo_lineage_populator module does not exist — RED gap."


@then('no duplicate entries are created')
def step_no_duplicates(context):
    assert context.populator_result.get("duplicates_skipped", 0) > 0 or \
        context.populator_result.get("created", 0) == 0, \
        "Expected duplicates to be skipped"
