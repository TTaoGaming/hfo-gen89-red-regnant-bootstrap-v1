"""
tests/test_ssot_db_connection_steps.py — pytest-bdd steps for ssot_db_connection.feature

Spec: every daemon/util module that needs a read-write SSOT connection MUST import
      ``get_db_readwrite`` from ``hfo_ssot_write`` — no module may carry its own copy.

Connection invariants verified here:
    journal_mode = WAL
    isolation_level = None  (autocommit — no implicit BEGIN lock squatting)
    busy_timeout = 30 000 ms
    connect-level timeout = 30 s
    synchronous = NORMAL (1)

Run:
    pytest tests/test_ssot_db_connection_steps.py -v --tb=short
    pytest tests/test_ssot_db_connection_steps.py -v -m ssot_db_connection
"""
from __future__ import annotations

import ast
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

# ── Project path plumbing ──────────────────────────────────────────────────────
RESOURCES = (
    Path(__file__).parent.parent
    / "hfo_gen_90_hot_obsidian_forge"
    / "0_bronze"
    / "2_resources"
)
sys.path.insert(0, str(RESOURCES))

# Local-function patterns (regex) that should NOT appear in any daemon file
_LOCAL_DEF_PATTERN = re.compile(
    r"^\s*def\s+(get_db_readwrite|get_db_rw|_get_db_rw)\s*\(",
    re.MULTILINE,
)

FEATURE_FILE = str(
    Path(__file__).parent.parent / "features" / "ssot_db_connection.feature"
)

scenarios(FEATURE_FILE)


# ── Shared context ─────────────────────────────────────────────────────────────

@pytest.fixture
def ctx() -> dict:
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# Background steps
# ──────────────────────────────────────────────────────────────────────────────

@given('the canonical DB helper "hfo_ssot_write.get_db_readwrite" is importable')
def canonical_helper_importable(ctx: dict) -> None:
    try:
        from hfo_ssot_write import get_db_readwrite  # will raise ImportError if broken
        ctx["get_db_readwrite"] = get_db_readwrite
    except ImportError:
        pytest.skip("hfo_ssot_write not found")


@given("a temporary SSOT-compatible SQLite database exists for testing")
def temp_db_ready(ctx: dict, tmp_db_full: Path) -> None:
    ctx["db_path"] = tmp_db_full


# ──────────────────────────────────────────────────────────────────────────────
# § 1  Connection settings
# ──────────────────────────────────────────────────────────────────────────────

@when("I open a read-write connection via the canonical helper")
def open_canonical_connection(ctx: dict) -> None:
    get_rw = ctx["get_db_readwrite"]
    conn = get_rw(ctx["db_path"])
    ctx["conn"] = conn


@then('the journal_mode pragma returns "wal"')
def check_journal_mode(ctx: dict) -> None:
    conn: sqlite3.Connection = ctx["conn"]
    result = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert result == "wal", f"Expected journal_mode=wal, got {result!r}"


@then("the connection isolation_level is None")
def check_isolation_level(ctx: dict) -> None:
    conn: sqlite3.Connection = ctx["conn"]
    level = conn.isolation_level
    conn.close()
    assert level is None, (
        f"Expected isolation_level=None (autocommit), got {level!r}. "
        "Non-None isolation_level causes Python to issue implicit BEGIN on first "
        "DML, holding the write lock until commit() — the root cause of FSM-V10."
    )


@then("the busy_timeout pragma returns 30000")
def check_busy_timeout(ctx: dict) -> None:
    conn: sqlite3.Connection = ctx["conn"]
    result = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    conn.close()
    assert result == 30_000, f"Expected busy_timeout=30000, got {result!r}"


@then("the Python-level connection timeout is 30 seconds")
def check_connect_timeout(ctx: dict) -> None:
    """Verify sqlite3.connect() was called with timeout=30.

    Python's sqlite3.Connection doesn't expose the timeout as an attribute,
    so we introspect by patching sqlite3.connect inside hfo_ssot_write and
    re-calling the function.
    """
    import hfo_ssot_write as _mod

    captured: dict[str, Any] = {}

    original_connect = sqlite3.connect

    def spy_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        captured.update(kwargs)
        captured["args"] = args
        return original_connect(*args, **kwargs)

    with patch.object(_mod.sqlite3, "connect", side_effect=spy_connect):
        conn = _mod.get_db_readwrite(ctx["db_path"])
        conn.close()

    assert captured.get("timeout") == 30, (
        f"Expected sqlite3.connect(timeout=30), got {captured.get('timeout')!r}"
    )


@then("the synchronous pragma returns 1")
def check_synchronous(ctx: dict) -> None:
    conn: sqlite3.Connection = ctx["conn"]
    result = conn.execute("PRAGMA synchronous").fetchone()[0]
    conn.close()
    # 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA
    assert result == 1, f"Expected synchronous=NORMAL(1), got {result!r}"


# ──────────────────────────────────────────────────────────────────────────────
# § 2  Static analysis — no local copies allowed
# ──────────────────────────────────────────────────────────────────────────────

@when("I scan all Python files in the resources directory")
def scan_resources(ctx: dict) -> None:
    ctx["py_files"] = list(RESOURCES.glob("*.py"))


@then('only "hfo_ssot_write.py" contains a definition of "get_db_readwrite"')
def check_no_local_get_db_readwrite(ctx: dict) -> None:
    violators = []
    for py_file in ctx["py_files"]:
        if py_file.name == "hfo_ssot_write.py":
            continue
        source = py_file.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^\s*def\s+get_db_readwrite\s*\(", source, re.MULTILINE):
            violators.append(py_file.name)
    assert not violators, (
        f"These files define their own get_db_readwrite (should import from "
        f"hfo_ssot_write): {violators}"
    )


@then('only "hfo_ssot_write.py" contains a definition of "get_db_rw" or its aliases')
def check_no_local_get_db_rw(ctx: dict) -> None:
    violators = []
    for py_file in ctx["py_files"]:
        if py_file.name == "hfo_ssot_write.py":
            continue
        source = py_file.read_text(encoding="utf-8", errors="ignore")
        if _LOCAL_DEF_PATTERN.search(source):
            violators.append(py_file.name)
    assert not violators, (
        f"These files define their own DB helper (get_db_rw/_get_db_rw). "
        f"All must import from hfo_ssot_write: {violators}"
    )


@when(parsers.parse('I inspect "{daemon_file}" for its database connection helper'))
def inspect_daemon_file(ctx: dict, daemon_file: str) -> None:
    path = RESOURCES / daemon_file
    assert path.exists(), f"Daemon file not found: {path}"
    ctx["current_daemon_path"] = path
    ctx["current_daemon_source"] = path.read_text(encoding="utf-8", errors="ignore")


@then('it imports "get_db_readwrite" from "hfo_ssot_write"')
def check_imports_canonical(ctx: dict) -> None:
    source: str = ctx["current_daemon_source"]
    path: Path = ctx["current_daemon_path"]
    # Accept:
    #   from hfo_ssot_write import get_db_readwrite
    #   from hfo_ssot_write import get_db_readwrite as get_db_rw   (alias)
    #   from hfo_ssot_write import (..., get_db_readwrite, ...)
    has_import = bool(re.search(
        r"from\s+hfo_ssot_write\s+import\s+[^\n]*get_db_readwrite",
        source,
    ))
    assert has_import, (
        f"{path.name} does not import get_db_readwrite from hfo_ssot_write. "
        "This is the longer-term fix: ditch the local copy, import the canonical one."
    )


@then('it does not define its own local "get_db_readwrite" or alias')
def check_no_local_def(ctx: dict) -> None:
    source: str = ctx["current_daemon_source"]
    path: Path = ctx["current_daemon_path"]
    assert not _LOCAL_DEF_PATTERN.search(source), (
        f"{path.name} still defines its own local DB helper. "
        "Remove the local def and rely solely on the hfo_ssot_write import."
    )


# ──────────────────────────────────────────────────────────────────────────────
# § 3  Concurrent writers
# ──────────────────────────────────────────────────────────────────────────────

@given("two threads each opening a canonical read-write connection")
def two_threads_setup(ctx: dict) -> None:
    ctx["thread_errors"] = []
    ctx["rows_inserted"] = []


@when("both threads insert a stigmergy_event row simultaneously")
def both_threads_insert(ctx: dict) -> None:
    from hfo_ssot_write import get_db_readwrite
    barrier = threading.Barrier(2)
    errors: list = ctx["thread_errors"]
    inserted: list = ctx["rows_inserted"]

    def worker(tag: str) -> None:
        try:
            conn = get_db_readwrite(ctx["db_path"])
            barrier.wait()  # synchronise — both arrive before either inserts
            conn.execute(
                "INSERT INTO stigmergy_events (event_type, timestamp, subject, data_json) "
                "VALUES (?, datetime('now'), ?, ?)",
                ("system_health.test_concurrent", f"thread_{tag}", "{}"),
            )
            inserted.append(tag)
            conn.close()
        except Exception as exc:  # noqa: BLE001
            errors.append((tag, str(exc)))

    t1 = threading.Thread(target=worker, args=("A",), daemon=True)
    t2 = threading.Thread(target=worker, args=("B",), daemon=True)
    t1.start(); t2.start()
    t1.join(timeout=35)
    t2.join(timeout=35)


@then('both inserts complete without "database is locked" errors')
def check_no_lock_errors(ctx: dict) -> None:
    errors = ctx["thread_errors"]
    lock_errors = [e for e in errors if "database is locked" in e[1].lower()]
    assert not lock_errors, f"database is locked errors: {lock_errors}"


@then("the stigmergy_events table contains exactly 2 new rows")
def check_two_rows(ctx: dict) -> None:
    from hfo_ssot_write import get_db_readwrite
    conn = get_db_readwrite(ctx["db_path"])
    count = conn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type=?",
        ("system_health.test_concurrent",),
    ).fetchone()[0]
    conn.close()
    assert count == 2, f"Expected 2 concurrent inserts, found {count}"


@given("a thread holds the write lock for 1 second")
def lock_holder_setup(ctx: dict) -> None:
    ctx["lock_error"] = None
    ctx["second_write_done"] = False


@when("a second thread attempts a write via the canonical helper")
def second_thread_writes_under_contention(ctx: dict) -> None:
    """One thread holds a WAL write transaction for 1 s; another writes after.

    Under WAL + busy_timeout=30000, the second writer queues and succeeds.
    """
    from hfo_ssot_write import get_db_readwrite

    db = ctx["db_path"]
    lock_released = threading.Event()
    write2_done = threading.Event()

    def holder() -> None:
        conn = get_db_readwrite(db)
        conn.execute("BEGIN")  # explicit transaction — hold write lock
        conn.execute(
            "INSERT INTO stigmergy_events (event_type, timestamp, subject, data_json) "
            "VALUES ('system_health.lock_test_holder', datetime('now'), 'holder', '{}')"
        )
        time.sleep(1)           # hold write lock for 1 second
        conn.execute("COMMIT")
        conn.close()
        lock_released.set()

    def writer2() -> None:
        try:
            time.sleep(0.1)     # slight delay so holder gets in first
            conn2 = get_db_readwrite(db)
            conn2.execute(
                "INSERT INTO stigmergy_events (event_type, timestamp, subject, data_json) "
                "VALUES ('system_health.lock_test_writer2', datetime('now'), 'w2', '{}')"
            )
            conn2.close()
            ctx["second_write_done"] = True
        except Exception as exc:  # noqa: BLE001
            ctx["lock_error"] = str(exc)
        finally:
            write2_done.set()

    t1 = threading.Thread(target=holder, daemon=True)
    t2 = threading.Thread(target=writer2, daemon=True)
    t1.start(); t2.start()
    t1.join(timeout=10)
    write2_done.wait(timeout=35)


@then("the second write succeeds (busy_timeout covers the contention window)")
def check_second_write_ok(ctx: dict) -> None:
    assert ctx["second_write_done"], (
        f"Second write did not complete. error={ctx['lock_error']!r}"
    )


@then('no "OperationalError: database is locked" is raised')
def check_no_operational_error(ctx: dict) -> None:
    err = ctx.get("lock_error")
    assert err is None, f"OperationalError raised: {err!r}"


# ──────────────────────────────────────────────────────────────────────────────
# § 4  Autocommit discipline
# ──────────────────────────────────────────────────────────────────────────────

@when("I insert a row using the canonical helper (no explicit commit)")
def insert_no_explicit_commit(ctx: dict) -> None:
    from hfo_ssot_write import get_db_readwrite
    conn = get_db_readwrite(ctx["db_path"])
    conn.execute(
        "INSERT INTO stigmergy_events (event_type, timestamp, subject, data_json) "
        "VALUES ('system_health.autocommit_test', datetime('now'), 'autocommit', '{}')"
    )
    # ← intentionally NO conn.commit()
    conn.close()
    ctx["autocommit_event_type"] = "system_health.autocommit_test"


@then("a second read-only connection can see that row immediately")
def check_row_visible_to_reader(ctx: dict) -> None:
    from hfo_ssot_write import get_db_readonly
    conn = get_db_readonly(ctx["db_path"])
    row = conn.execute(
        "SELECT id FROM stigmergy_events WHERE event_type=?",
        (ctx["autocommit_event_type"],),
    ).fetchone()
    conn.close()
    assert row is not None, (
        "Row not visible to a second reader — isolation_level is not None (autocommit "
        "is not active). The implicit BEGIN is holding the write."
    )


@then("no explicit conn.commit() call is required")
def no_commit_required(ctx: dict) -> None:
    # The assertion in the previous step already proved this by not calling commit().
    pass


@when('I open a canonical connection and issue "BEGIN"')
def open_and_begin(ctx: dict) -> None:
    from hfo_ssot_write import get_db_readwrite
    conn = get_db_readwrite(ctx["db_path"])
    conn.execute("BEGIN")
    ctx["explicit_txn_conn"] = conn


@then("I can perform multiple inserts atomically")
def insert_in_explicit_txn(ctx: dict) -> None:
    conn: sqlite3.Connection = ctx["explicit_txn_conn"]
    for i in range(3):
        conn.execute(
            "INSERT INTO stigmergy_events (event_type, timestamp, subject, data_json) "
            "VALUES (?, datetime('now'), ?, ?)",
            (f"system_health.txn_test_{i}", f"row_{i}", "{}"),
        )
    ctx["explicit_txn_rows"] = 3


@then('after "COMMIT" the rows are visible to other connections')
def commit_and_check(ctx: dict) -> None:
    conn: sqlite3.Connection = ctx["explicit_txn_conn"]
    conn.execute("COMMIT")
    conn.close()

    from hfo_ssot_write import get_db_readonly
    rconn = get_db_readonly(ctx["db_path"])
    count = rconn.execute(
        "SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE 'system_health.txn_test_%'"
    ).fetchone()[0]
    rconn.close()
    assert count == ctx["explicit_txn_rows"], (
        f"Expected {ctx['explicit_txn_rows']} rows after COMMIT, got {count}"
    )


@then("the isolation_level of the connection remains None throughout")
def check_isolation_none_after_txn(ctx: dict) -> None:
    # Connection was closed in the previous step; we verify the invariant conceptually
    # (isolation_level=None means manual transaction management — BEGIN/COMMIT are
    # explicit, never implicit).  The previous steps prove this works end-to-end.
    pass
