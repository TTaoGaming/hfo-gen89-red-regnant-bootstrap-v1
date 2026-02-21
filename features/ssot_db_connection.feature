# features/ssot_db_connection.feature
# HFO Gen90 — SSOT Database Connection ATDD Contract
#
# Root cause of FSM-V10 through FSM-V17 write-lock failures:
#   15+ daemon files each had a HARDCODED COPY of get_db_readwrite() with
#   busy_timeout=5000 (5 s) and Python's default isolation_level="" which
#   auto-issues BEGIN on first DML and holds the write lock until commit().
#   Under concurrent daemon operation a 5-second timeout is far too short.
#
# The fix: ONE canonical source — hfo_ssot_write.get_db_readwrite():
#   • timeout=30           (Python-level wait before giving up)
#   • isolation_level=None (autocommit: no implicit BEGIN / lock squatting)
#   • busy_timeout=30000   (SQLite-level 30 s retry window)
#   • synchronous=NORMAL   (safe with WAL, faster than FULL)
#
# SBE Contract: every other module IMPORTS from hfo_ssot_write.
# No module may define its own get_db_readwrite / get_db_rw / _get_db_rw.

@ssot_db_connection
Feature: SSOT database connection — canonical source of truth

  Background:
    Given the canonical DB helper "hfo_ssot_write.get_db_readwrite" is importable
    And a temporary SSOT-compatible SQLite database exists for testing

  # ─────────────────────────────────────────────────────────────
  # § 1  Connection settings invariants
  # ─────────────────────────────────────────────────────────────

  Scenario: WAL journal mode is enabled on every canonical connection
    When I open a read-write connection via the canonical helper
    Then the journal_mode pragma returns "wal"

  Scenario: isolation_level is None (autocommit) to prevent implicit BEGIN lock-holding
    When I open a read-write connection via the canonical helper
    Then the connection isolation_level is None

  Scenario: busy_timeout is 30 000 ms — covers long LLM inference write cycles
    When I open a read-write connection via the canonical helper
    Then the busy_timeout pragma returns 30000

  Scenario: connect-level timeout is 30 seconds
    When I open a read-write connection via the canonical helper
    Then the Python-level connection timeout is 30 seconds

  Scenario: synchronous pragma is NORMAL for WAL safety
    When I open a read-write connection via the canonical helper
    Then the synchronous pragma returns 1

  # ─────────────────────────────────────────────────────────────
  # § 2  No daemon may define its own DB connection helper
  # ─────────────────────────────────────────────────────────────

  Scenario: No resource module other than hfo_ssot_write defines get_db_readwrite
    When I scan all Python files in the resources directory
    Then only "hfo_ssot_write.py" contains a definition of "get_db_readwrite"

  Scenario: No resource module other than hfo_ssot_write defines get_db_rw
    When I scan all Python files in the resources directory
    Then only "hfo_ssot_write.py" contains a definition of "get_db_rw" or its aliases

  Scenario Outline: Each daemon imports get_db_readwrite from hfo_ssot_write
    When I inspect "<daemon_file>" for its database connection helper
    Then it imports "get_db_readwrite" from "hfo_ssot_write"
    And it does not define its own local "get_db_readwrite" or alias

    Examples:
      | daemon_file                    |
      | hfo_background_daemon.py       |
      | hfo_p6_kraken_daemon.py        |
      | hfo_p6_kraken_workers.py       |
      | hfo_singer_ai_daemon.py        |
      | hfo_singer_daemon.py           |
      | hfo_p5_dancer_daemon.py        |
      | hfo_p6_devourer_daemon.py      |
      | hfo_p6_eyebite.py              |
      | hfo_p4_wail_of_the_banshee.py  |
      | hfo_p4_weird.py                |
      | hfo_p5_daemon.py               |
      | hfo_p5_flame_strike.py         |
      | hfo_npu_embedder.py            |
      | hfo_meadows_engine.py          |
      | hfo_daemon_fleet.py            |
      | hfo_conductor.py               |
      | hfo_song_prospector.py         |
      | hfo_devourer_apex_synthesis.py |
      | hfo_p7_dimensional_anchor.py   |
      | hfo_wish_pipeline.py           |
      | hfo_signal_shim.py             |
      | hfo_prey8_loop.py              |
      | hfo_p7_wish_compiler.py        |
      | hfo_p7_wish.py                 |
      | hfo_p7_tremorsense.py          |
      | hfo_p7_summoner_daemon.py      |
      | hfo_p7_spell_gate.py           |
      | hfo_p7_planar_binding.py       |
      | hfo_p7_metafaculty.py          |
      | hfo_p7_gpu_npu_anchor.py       |
      | hfo_p7_foresight_daemon.py     |

  # ─────────────────────────────────────────────────────────────
  # § 3  Write-lock contention — WAL multi-writer guarantees
  # ─────────────────────────────────────────────────────────────

  Scenario: Two concurrent writers both succeed without database-is-locked error
    Given two threads each opening a canonical read-write connection
    When both threads insert a stigmergy_event row simultaneously
    Then both inserts complete without "database is locked" errors
    And the stigmergy_events table contains exactly 2 new rows

  Scenario: A write succeeds within 30 seconds when another writer holds the lock briefly
    Given a thread holds the write lock for 1 second
    When a second thread attempts a write via the canonical helper
    Then the second write succeeds (busy_timeout covers the contention window)
    And no "OperationalError: database is locked" is raised

  # ─────────────────────────────────────────────────────────────
  # § 4  Autocommit discipline — no open transactions at rest
  # ─────────────────────────────────────────────────────────────

  Scenario: An autocommit write is visible to a reader immediately without explicit commit
    When I insert a row using the canonical helper (no explicit commit)
    Then a second read-only connection can see that row immediately
    And no explicit conn.commit() call is required

  Scenario: A caller that needs a transaction uses explicit BEGIN / COMMIT
    When I open a canonical connection and issue "BEGIN"
    Then I can perform multiple inserts atomically
    And after "COMMIT" the rows are visible to other connections
    And the isolation_level of the connection remains None throughout
