# ╔═══════════════════════════════════════════════════════════════╗
# ║  HFO STRUCTURAL ENFORCEMENT — Gherkin SBE/ATDD Specs        ║
# ║  Written BEFORE code. Code exists to make these pass.        ║
# ║  PREY8 session f661e409bbd4480d | Meadows L8 RULES           ║
# ║  Operator directive: structural enforcement only.            ║
# ║  Semantic enforcement is an illusion at scale.               ║
# ╚═══════════════════════════════════════════════════════════════╝
#
# These specs define STRUCTURAL contracts — they are enforced by:
#   - Python type signatures (required parameters, not **kwargs)
#   - SQLite CHECK constraints (database rejects malformed data)
#   - File system locks (OS-level, not advisory)
#   - Import-time validation (fail at import, not at runtime)
#
# NOT enforced by:
#   - Prompting LLMs to "please follow the rules"
#   - Documentation that says "you should include signal_metadata"
#   - Code review (doesn't scale, humans forget)
#   - try/except: pass (fail-open = no enforcement)

# ═══════════════════════════════════════════════════════════════
# FEATURE 1: Canonical Stigmergy Write Function
# Task: T-SIGNAL-001 (Structural Signal Metadata Enforcement)
# ═══════════════════════════════════════════════════════════════

Feature: Canonical stigmergy write function enforces signal_metadata schema
  """
  PROBLEM: 34 independent write_event() copies across 34 files.
  Each implements its own CloudEvent envelope. Signal_metadata injection
  uses try/except:pass (fail-open). Any daemon can skip signal_metadata
  and the SSOT silently accepts garbage.

  STRUCTURAL FIX: One canonical function. signal_metadata is a REQUIRED
  parameter with a validated schema. The function is the ONLY way to
  write stigmergy events. Database CHECK constraint as second gate.
  """

  Background:
    Given the SSOT database at the PAL-resolved "ssot.db" path
    And the canonical write module "hfo_ssot_write.py" is importable
    And the stigmergy_events table has a CHECK constraint requiring valid signal_metadata in data_json

  # ─── INVARIANT TIER (fail-closed safety) ───

  Scenario: Write function rejects event without signal_metadata
    Given a caller provides event_type "hfo.gen89.test.event" and subject "test"
    And the caller provides event data {"action": "test"} with NO signal_metadata dict
    When the caller invokes write_stigmergy_event()
    Then the function raises SignalMetadataMissing error
    And NO row is inserted into stigmergy_events
    And a gate_block event is logged with reason "signal_metadata_missing"

  Scenario: Write function rejects signal_metadata missing required fields
    Given a caller provides signal_metadata with only {"port": "P4"}
    And required fields "model_id", "daemon_name", "model_provider" are missing
    When the caller invokes write_stigmergy_event()
    Then the function raises SignalMetadataIncomplete error with list of missing fields
    And NO row is inserted into stigmergy_events
    And a gate_block event is logged listing each missing field

  Scenario: Database CHECK constraint rejects bypass attempts
    Given a caller bypasses the canonical function and executes raw SQL
    And the INSERT contains data_json without a "signal_metadata" key at data.signal_metadata or data.data.signal_metadata
    When the raw INSERT is executed
    Then SQLite raises a CHECK constraint violation
    And the row is NOT inserted

  Scenario: Write function rejects empty string signal_metadata fields
    Given a caller provides signal_metadata where model_id is ""
    When the caller invokes write_stigmergy_event()
    Then the function raises SignalMetadataIncomplete error for "model_id"
    And NO row is inserted

  # ─── HAPPY PATH TIER ───

  Scenario: Write function accepts valid event with complete signal_metadata
    Given a caller provides event_type "hfo.gen89.singer.strife"
    And subject "strife:doc:1234"
    And data {"action": "code_eval", "file": "test.py"}
    And signal_metadata with port="P4", model_id="gemma3:4b", daemon_name="Singer", model_provider="ollama"
    When the caller invokes write_stigmergy_event()
    Then a row is inserted into stigmergy_events
    And the returned row_id is > 0
    And the data_json contains signal_metadata with all 4 required fields
    And the content_hash is a SHA256 hex digest
    And the CloudEvent envelope has specversion, id, type, source, time, traceparent

  Scenario: Write function deduplicates identical events
    Given a caller writes an event with content_hash "abc123"
    And a row with content_hash "abc123" already exists
    When the caller invokes write_stigmergy_event()
    Then the returned row_id is 0 (deduped)
    And no duplicate row exists

  Scenario: Build signal_metadata convenience function produces valid schema
    Given a caller invokes build_signal_metadata(port="P4", model_id="gemma3:4b", daemon_name="Singer")
    When the result dict is inspected
    Then it contains all 22 standard signal_metadata fields
    And port is "P4"
    And commander is auto-resolved to "Red Regnant"
    And model_family is auto-resolved from MODEL_DB
    And timestamp is a valid ISO 8601 string

  # ─── STRUCTURAL SEPARATION TIER ───

  Scenario: Function signature structurally requires signal_metadata
    Given the write_stigmergy_event function signature
    When inspected via inspect.signature()
    Then "signal_metadata" is a REQUIRED positional-or-keyword parameter (no default)
    And its type annotation is dict
    And it is NOT buried in **kwargs

  Scenario: Legacy write functions are import-time deprecated
    Given a file that defines its own write_event() or write_stigmergy_event()
    When hfo_ssot_write.py is imported alongside it
    Then a DeprecationWarning is emitted naming the file and suggesting migration
    # NOTE: This is a migration aid, not enforcement. Enforcement is the CHECK constraint.


# ═══════════════════════════════════════════════════════════════
# FEATURE 2: PID Lockfile Fleet Single-Instance Enforcement
# Task: T-FLEET-001 (Kill Zombie .venv Daemon Processes)
# ═══════════════════════════════════════════════════════════════

Feature: PID lockfile prevents duplicate daemon instances
  """
  PROBLEM: Every daemon runs as 2 processes — a zombie 4MB .venv
  launcher that never exits, plus the real 33-112MB system Python
  worker. 8 zombies = 400MB wasted, GPU scheduling contention.

  STRUCTURAL FIX: Each daemon acquires an exclusive file lock at
  startup. If the lock is held, the new process exits immediately
  with a clear error. OS-level enforcement, not process-name matching.
  """

  Background:
    Given the lockfile directory is at "{HFO_ROOT}/.locks/"
    And each daemon has a unique lock name derived from its port and role

  # ─── INVARIANT TIER ───

  Scenario: Second daemon instance cannot start when first holds lock
    Given daemon "Singer_P4" is running and holds lock file ".locks/singer_p4.lock"
    When a second "Singer_P4" process attempts to acquire the same lock
    Then the second process fails to acquire the lock
    And the second process exits with code 1
    And the second process prints "LOCK_HELD: Singer_P4 already running (PID {pid})"
    And NO zombie process remains

  Scenario: Lock is released when daemon exits normally
    Given daemon "Singer_P4" is running and holds lock file ".locks/singer_p4.lock"
    When the daemon process exits (code 0 or signal)
    Then the lock file is released (other processes can acquire it)
    And the lock file contains stale PID (informational only, not relied upon)

  Scenario: Lock is released when daemon crashes
    Given daemon "Singer_P4" is running with PID 12345
    When the process is killed (SIGKILL / taskkill /F)
    Then the OS releases the file handle
    And a new "Singer_P4" instance can acquire the lock

  # ─── HAPPY PATH TIER ───

  Scenario: Daemon acquires lock and writes PID to lockfile
    Given no other "Singer_P4" instance is running
    When daemon "Singer_P4" starts and calls acquire_daemon_lock("singer_p4")
    Then the function returns a lock handle (truthy)
    And file ".locks/singer_p4.lock" exists
    And the file contains the current PID as text

  Scenario: Fleet launcher uses lockfile for all 8 daemons
    Given the fleet launcher starts daemons for P0 through P7
    When each daemon calls acquire_daemon_lock() with its unique name
    Then 8 lock files exist in ".locks/"
    And each contains a different PID
    And no duplicate processes exist

  # ─── WINDOWS COMPATIBILITY TIER ───

  Scenario: Lockfile works on Windows without fcntl
    Given the platform is Windows (no fcntl module)
    When acquire_daemon_lock() is called
    Then it uses msvcrt.locking() for exclusive file lock
    And the behavior is identical to Unix fcntl.flock()


# ═══════════════════════════════════════════════════════════════
# FEATURE 3: Compute Route Table for Model Selection
# Task: T-GEMINI-001 (Route Singer+Dancer to Gemini Flash)
# Task: T-COORD-001 (Connect Daemons to Coordinator Recommendations)
# ═══════════════════════════════════════════════════════════════

Feature: Compute route table structurally controls daemon model selection
  """
  PROBLEM: Every daemon hardcodes its model string (e.g. MODEL = "gemma3:4b").
  The 8^N coordinator emits recommendations to stigmergy but zero daemons read
  them. Changing a model requires editing source code. Gemini Flash at 0.02%
  capacity because only Background daemon routes to it.

  STRUCTURAL FIX: compute_route table in SSOT. Each daemon reads its model
  assignment from the table at startup — NOT from a source code constant.
  The coordinator writes to this table. Model selection is data, not code.
  """

  Background:
    Given the SSOT database has a "compute_route" table with schema:
      | column          | type    | constraint                     |
      | port            | TEXT    | NOT NULL                       |
      | daemon_name     | TEXT    | NOT NULL                       |
      | task_type       | TEXT    | NOT NULL DEFAULT 'default'     |
      | model_id        | TEXT    | NOT NULL                       |
      | provider        | TEXT    | NOT NULL                       |
      | priority        | INTEGER | NOT NULL DEFAULT 0             |
      | updated_at      | TEXT    | NOT NULL                       |
      | updated_by      | TEXT    | NOT NULL                       |
      | reason          | TEXT    |                                |
    And PRIMARY KEY is (port, daemon_name, task_type)

  # ─── INVARIANT TIER ───

  Scenario: Daemon refuses to start without a compute_route entry
    Given no compute_route entry exists for port "P4" daemon "Singer"
    When Singer daemon starts and queries compute_route
    Then the daemon logs "NO_ROUTE: No compute_route entry for P4/Singer, cannot select model"
    And the daemon exits with code 1
    # NOT: silently falls back to hardcoded default. That's semantic enforcement.

  Scenario: Daemon uses route table model, not source code constant
    Given compute_route has entry: port="P4", daemon="Singer", model_id="gemini-2.5-flash", provider="gemini_free"
    And the Singer source code has MODEL = "qwen2.5-coder:7b" (legacy constant)
    When Singer daemon starts and calls get_compute_route("P4", "Singer")
    Then the returned model_id is "gemini-2.5-flash"
    And the returned provider is "gemini_free"
    And the legacy MODEL constant is IGNORED

  # ─── HAPPY PATH TIER ───

  Scenario: Coordinator updates compute_route with ACO recommendation
    Given the 8^N coordinator runs a cycle
    And ACO pheromone scoring recommends "gemini-2.5-flash" for P4
    When the coordinator writes to compute_route
    Then the entry for port="P4" is updated with model_id="gemini-2.5-flash"
    And updated_by is "coordinator"
    And reason contains pheromone score

  Scenario: Operator can override coordinator recommendation
    Given compute_route has coordinator entry for P4: model="gemini-2.5-flash"
    When operator runs: set_compute_route("P4", "Singer", "phi4:14b", "ollama", updated_by="TTAO")
    Then the P4 entry is updated to model="phi4:14b", provider="ollama"
    And updated_by is "TTAO" (operator override)

  Scenario: Multiple task types per daemon have independent routes
    Given Singer has routes: task_type="code_eval" -> "gemini-2.5-flash" AND task_type="classification" -> "gemma3:4b"
    When Singer queries route for task_type="code_eval"
    Then it gets "gemini-2.5-flash"
    When Singer queries route for task_type="classification"
    Then it gets "gemma3:4b"

  Scenario: Default route fallback for unknown task types
    Given Singer has route for task_type="default" -> "gemini-2.5-flash"
    And no route for task_type="new_task"
    When Singer queries route for task_type="new_task"
    Then it falls back to the "default" task_type route
    And gets "gemini-2.5-flash"


# ═══════════════════════════════════════════════════════════════
# FEATURE 4: NPU Re-Embed Trigger on Document Enrichment
# Task: T-NPU-001 (Reactivate NPU for Continuous Embedding)
# ═══════════════════════════════════════════════════════════════

Feature: Document enrichment structurally triggers NPU re-embedding
  """
  PROBLEM: NPU completed bulk embed (9861/9862) then went IDLE.
  No daemon drives incremental NPU work. New docs written by
  Devourer/Kraken never get re-embedded.

  STRUCTURAL FIX: A queue table. Any write to document_enrichments
  or documents inserts a row into embed_queue. A lightweight daemon
  or cron drains the queue through NPU. The trigger is structural
  (database trigger or mandatory post-write call), not semantic
  (hoping someone remembers to re-embed).
  """

  Background:
    Given the SSOT database has an "embed_queue" table with schema:
      | column     | type    | constraint                     |
      | doc_id     | INTEGER | NOT NULL REFERENCES documents  |
      | reason     | TEXT    | NOT NULL                       |
      | queued_at  | TEXT    | NOT NULL                       |
      | status     | TEXT    | NOT NULL DEFAULT 'pending'     |
      | claimed_by | TEXT    |                                |
      | claimed_at | TEXT    |                                |
    And a SQLite trigger fires on INSERT/UPDATE to document_enrichments

  # ─── INVARIANT TIER ───

  Scenario: Document enrichment automatically queues re-embed
    Given document 1234 has an existing embedding from 2026-02-19
    When Kraken daemon updates document_enrichments for doc_id 1234
    Then a row appears in embed_queue with doc_id=1234, reason="enrichment_updated", status="pending"
    And this happens WITHOUT Kraken daemon calling any embed function
    # The trigger fires structurally — Kraken cannot forget.

  Scenario: New document insertion queues initial embed
    Given a new document is inserted into documents with id 9863
    When the INSERT completes
    Then a row appears in embed_queue with doc_id=9863, reason="new_document", status="pending"

  # ─── HAPPY PATH TIER ───

  Scenario: NPU embedder drains queue and updates embeddings table
    Given embed_queue has 5 pending entries
    When the NPU embed worker runs a batch
    Then it claims entries (status="claimed", claimed_by="npu_worker")
    And processes each through OpenVINO NPU pipeline
    And UPSERTs into embeddings table with device="NPU", model="all-MiniLM-L6-v2"
    And marks queue entries as status="done"

  Scenario: Queue deduplication prevents redundant re-embeds
    Given embed_queue already has doc_id=1234 with status="pending"
    When another enrichment update triggers for doc_id=1234
    Then no duplicate row is created (INSERT OR IGNORE on doc_id+status='pending')

  Scenario: Stale claims are reclaimed after timeout
    Given an embed_queue entry was claimed 10 minutes ago but never completed
    When the NPU worker scans for stale claims
    Then the entry is reset to status="pending"
    And a stigmergy warning event is logged


# ═══════════════════════════════════════════════════════════════
# FEATURE 5: Devourer Structured Error Capture
# Task: T-DEVOURER-001 (Fix Devourer Non-Dry-Run Mode)
# ═══════════════════════════════════════════════════════════════

Feature: Devourer failure produces structured error evidence, not silent exit code 1
  """
  PROBLEM: Devourer --single --batch 2 exits with code 1.
  No error event in stigmergy. No diagnostic data captured.
  Silent failure = no learning = repeated failure.

  STRUCTURAL FIX: Every Devourer run writes a completion event
  to stigmergy — success OR failure. The event schema requires
  error_type, error_message, traceback_hash. This is mandatory,
  not optional error handling.
  """

  # ─── INVARIANT TIER ───

  Scenario: Devourer failure writes structured error event to SSOT
    Given Devourer runs with --single --batch 2 (non-dry-run)
    When the run encounters an error (encoding, model timeout, DB lock, etc.)
    Then a stigmergy event "hfo.gen89.devourer.failure" is written
    And the event data contains:
      | field           | type   | description                        |
      | error_type      | string | exception class name               |
      | error_message   | string | exception message (first 500 chars) |
      | traceback_hash  | string | SHA256 of full traceback           |
      | batch_size      | int    | requested batch size               |
      | docs_attempted  | int    | how many docs were tried           |
      | docs_succeeded  | int    | how many succeeded before failure  |
      | dry_run         | bool   | false (this was a real run)        |
    And signal_metadata is present (enforced by canonical write function)
    And the exit code is still non-zero (failure IS failure)

  Scenario: Devourer success writes structured completion event
    Given Devourer runs with --single --batch 2 (non-dry-run)
    When the run completes successfully
    Then a stigmergy event "hfo.gen89.devourer.completion" is written
    And the event contains docs_attempted, docs_succeeded, duration_ms
    And the exit code is 0

  # ─── HAPPY PATH TIER ───

  Scenario: Devourer dry-run also writes diagnostic event
    Given Devourer runs with --single --dry-run --batch 1
    When the dry-run completes
    Then a stigmergy event "hfo.gen89.devourer.dry_run" is written
    And the event contains docs_found, model_selected, would_enrich (list of doc_ids)
    And dry_run is true
