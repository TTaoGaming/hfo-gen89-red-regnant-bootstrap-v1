"""
Step definitions for medallion_promotion.feature — Medallion Gate SBE/ATDD.
RED PHASE: Medallion promotion module does not exist yet. 9860 bronze, 0 promoted.
"""

import json
import sqlite3

from behave import given, when, then


@given('the medallion promotion module is importable')
def step_promotion_importable(context):
    try:
        from hfo_medallion_promotion import promote_to_silver, check_promotion_criteria
        context.promote_to_silver = promote_to_silver
        context.check_promotion_criteria = check_promotion_criteria
    except ImportError:
        assert False, \
            "hfo_medallion_promotion module does not exist — RED gap. " \
            "Must create medallion promotion implementation."


@then('the promote_to_silver function is callable')
def step_promote_callable(context):
    assert callable(context.promote_to_silver), \
        "promote_to_silver is not callable"


@given('a bronze document without validation metadata')
def step_bronze_no_validation(context):
    context.test_doc_id = None
    # Find a real bronze doc with no validation
    cur = context.db_conn.execute(
        "SELECT id FROM documents WHERE medallion = 'bronze' LIMIT 1"
    )
    row = cur.fetchone()
    assert row, "No bronze documents found"
    context.test_doc_id = row[0]
    context.test_validation = None


@when('I attempt to promote it to silver')
def step_attempt_promote(context):
    try:
        from hfo_medallion_promotion import promote_to_silver
        context.promotion_result = promote_to_silver(
            context.ssot_db, context.test_doc_id,
            validation=context.test_validation
        )
    except ImportError:
        assert False, "hfo_medallion_promotion not importable — RED gap"
    except Exception as e:
        context.promotion_result = {"status": "error", "reason": str(e)}


@then('the promotion is rejected with reason "{reason}"')
def step_rejected(context, reason):
    assert context.promotion_result.get("status") in ("rejected", "error"), \
        f"Expected rejection, got {context.promotion_result}"
    assert reason.lower() in context.promotion_result.get("reason", "").lower(), \
        f"Expected reason containing '{reason}', got '{context.promotion_result.get('reason')}'"


@given('a bronze document with passing validation metadata')
def step_bronze_with_validation(context):
    cur = context.db_conn.execute(
        "SELECT id FROM documents WHERE medallion = 'bronze' LIMIT 1"
    )
    row = cur.fetchone()
    assert row, "No bronze documents found"
    context.test_doc_id = row[0]
    context.test_validation = {
        "reviewed_by": "TTAO",
        "review_date": "2026-02-19",
        "validation_type": "human_review",
        "claims_verified": True,
        "cross_referenced": True,
    }


@when('I promote it to silver')
def step_promote(context):
    try:
        from hfo_medallion_promotion import promote_to_silver
        context.promotion_result = promote_to_silver(
            context.ssot_db, context.test_doc_id,
            validation=context.test_validation
        )
    except ImportError:
        assert False, "hfo_medallion_promotion not importable — RED gap"
    except Exception as e:
        context.promotion_result = {"status": "error", "reason": str(e)}


@then('the document medallion field is updated to "{level}"')
def step_medallion_updated(context, level):
    assert context.promotion_result.get("status") == "promoted", \
        f"Expected promoted, got {context.promotion_result}"
    # Verify in DB
    cur = context.db_conn.execute(
        "SELECT medallion FROM documents WHERE id = ?",
        (context.test_doc_id,)
    )
    row = cur.fetchone()
    assert row and row[0] == level, \
        f"Document medallion is '{row[0] if row else None}', expected '{level}'"


@then('a promotion stigmergy event is logged')
def step_promotion_event(context):
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE event_type LIKE '%medallion%promotion%'"
    )
    count = cur.fetchone()[0]
    assert count > 0, \
        "No promotion stigmergy event found"


@when('I count documents with medallion "{level}" or higher')
def step_count_promoted(context, level):
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM documents WHERE medallion IN ('silver', 'gold', 'hyper_fractal_obsidian')"
    )
    context.promoted_count = cur.fetchone()[0]


@then('there is at least {n:d} promoted document')
def step_min_promoted(context, n):
    assert context.promoted_count >= n, \
        f"Only {context.promoted_count} promoted documents, need {n}. " \
        f"All 9860 documents are still bronze — medallion promotion not implemented. RED gap."
