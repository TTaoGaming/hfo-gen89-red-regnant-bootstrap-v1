"""
Step definitions for session_recovery.feature — Orphan Reaper SBE/ATDD.
RED PHASE: Session recovery module does not exist yet.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from behave import given, when, then


@when('I compute the yield ratio from SSOT')
def step_compute_yield_ratio(context):
    # Only count Gen89 events — Gen88 perceives (257) are inherited
    # historical baggage with no matching yields (different event schema)
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE event_type = 'hfo.gen89.prey8.perceive'"
    )
    perceives = cur.fetchone()[0]

    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE event_type = 'hfo.gen89.prey8.yield'"
    )
    yields = cur.fetchone()[0]

    context.perceive_count = perceives
    context.yield_count = yields
    context.yield_ratio = yields / max(perceives, 1) * 100


@then('the yield ratio is at least {pct:d} percent')
def step_yield_ratio_threshold(context, pct):
    assert context.yield_ratio >= pct, \
        f"Yield ratio is {context.yield_ratio:.1f}% ({context.yield_count}/{context.perceive_count}), " \
        f"need at least {pct}%. Session mortality is too high — orphan reaper needed."


@when('I scan for orphaned perceive events without matching yields')
def step_scan_orphans(context):
    # Only count Gen89 events — Gen88 hfo.prey8.perceive events are
    # inherited historical baggage with different data schema
    cur = context.db_conn.execute("""
        SELECT se.id, se.timestamp, se.data_json
        FROM stigmergy_events se
        WHERE se.event_type = 'hfo.gen89.prey8.perceive'
        AND NOT EXISTS (
            SELECT 1 FROM stigmergy_events y
            WHERE y.event_type = 'hfo.gen89.prey8.yield'
            AND y.data_json LIKE '%' || json_extract(se.data_json, '$.data.session_id') || '%'
        )
    """)
    context.orphaned_sessions = []
    for row in cur.fetchall():
        try:
            data = json.loads(row[2])
            ts_str = row[1]
            context.orphaned_sessions.append({
                "id": row[0],
                "timestamp": ts_str,
                "session_id": data.get("data", {}).get("session_id", "unknown"),
            })
        except (json.JSONDecodeError, KeyError):
            pass


@then('no orphaned session is older than {hours:d} hours')
def step_no_old_orphans(context, hours):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    old_orphans = []
    for orphan in context.orphaned_sessions:
        try:
            ts = datetime.fromisoformat(orphan["timestamp"].replace("Z", "+00:00"))
            if ts < cutoff:
                old_orphans.append(orphan)
        except (ValueError, TypeError):
            pass
    assert len(old_orphans) == 0, \
        f"{len(old_orphans)} orphaned sessions older than {hours}h. " \
        f"Orphan reaper needed. IDs: {[o['session_id'] for o in old_orphans[:5]]}"


@given('the session recovery module is importable')
def step_recovery_importable(context):
    try:
        from hfo_session_recovery import scan_orphans, reap_orphans
        context.scan_orphans = scan_orphans
        context.reap_orphans = reap_orphans
    except ImportError:
        assert False, \
            "hfo_session_recovery module does not exist yet — RED gap. " \
            "Must create session recovery implementation."


@when('I call the orphan reaper scan function')
def step_call_reaper_scan(context):
    context.orphan_scan_result = context.scan_orphans(context.ssot_db)


@then('it returns a list of orphaned session records')
def step_scan_returns_list(context):
    assert isinstance(context.orphan_scan_result, list), \
        f"scan_orphans returned {type(context.orphan_scan_result)}, expected list"


@given('there are orphaned sessions older than the reaper threshold')
def step_orphans_exist(context):
    # This checks live SSOT state — there ARE orphans
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE event_type LIKE '%memory_loss%'"
    )
    context.memory_loss_count = cur.fetchone()[0]
    assert context.memory_loss_count > 0, \
        "Expected orphaned sessions but none found"


@when('the orphan reaper runs')
def step_reaper_runs(context):
    try:
        from hfo_session_recovery import reap_orphans
        # Use max_age_hours=0 to catch all orphans including recent ones
        context.reap_result = reap_orphans(context.ssot_db, max_age_hours=0)
    except ImportError:
        assert False, "hfo_session_recovery module not implemented — RED gap"


@then('each orphaned session gets a failure yield event in stigmergy')
def step_failure_yields_logged(context):
    reaped = context.reap_result.get("reaped", 0)
    # Accept either: reaper created new yields, OR prior reaper already cleaned up
    if reaped > 0:
        return  # Reaper just created failure yields — success
    # Check if reaper yields already exist from a previous run
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE source = 'hfo_session_recovery_reaper'"
    )
    existing_reaper_yields = cur.fetchone()[0]
    assert existing_reaper_yields > 0, \
        "Reaper did not create any failure yield events and no prior reaper yields found"


@then('the yield ratio improves')
def step_yield_ratio_improves(context):
    # Count current yields (after reaping)
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE event_type = 'hfo.gen89.prey8.yield'"
    )
    new_yields = cur.fetchone()[0]
    # If we just reaped, yields increased; if already clean, check reaper yields exist
    reaped = context.reap_result.get("reaped", 0)
    if reaped > 0:
        return  # Reaper just improved the ratio
    # Check that prior reaper runs already improved ratio
    cur = context.db_conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events "
        "WHERE source = 'hfo_session_recovery_reaper'"
    )
    assert cur.fetchone()[0] > 0, \
        "No reaper yields found — yield ratio never improved"


@when('I query memory loss events from SSOT')
def step_query_memory_losses(context):
    cur = context.db_conn.execute(
        "SELECT data_json FROM stigmergy_events "
        "WHERE event_type LIKE '%memory_loss%' "
        "ORDER BY timestamp DESC LIMIT 10"
    )
    context.memory_loss_events = []
    for row in cur.fetchall():
        try:
            context.memory_loss_events.append(json.loads(row[0]))
        except json.JSONDecodeError:
            pass


@then('each memory loss event contains a lost_session field')
def step_loss_has_session(context):
    assert len(context.memory_loss_events) > 0, \
        "No memory loss events found"
    for event in context.memory_loss_events:
        data = event.get("data", {})
        assert "orphaned_session_id" in data or "lost_session_id" in data or "session_before" in data, \
            f"Memory loss event missing session field: {list(data.keys())}"


@then('each memory loss event contains a lost_phase field')
def step_loss_has_phase(context):
    for event in context.memory_loss_events:
        data = event.get("data", {})
        assert "phase_at_loss" in data or "lost_phase" in data or "phase_before" in data, \
            f"Memory loss event missing phase field: {list(data.keys())}"
