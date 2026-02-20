# features/daemon_fleet.feature
# HFO Gen89 — 8-Daemon Fleet ATDD Contract
#
# The fleet runs exactly 8 OctreeDaemon instances (P0–P7).
# All LLM calls route through hfo_llm_router.py.
# The governor reaps ghost processes. The fleet self-heals via watchdog.

@daemon_fleet
Feature: 8-Daemon Fleet Lifecycle

  Background:
    Given the daemon fleet manager is initialised
    And the SSOT database is accessible
    And the LLM router is available

  # ─────────────────────────────────────────────────────────────
  # Fleet size invariant (the ghost problem)
  # ─────────────────────────────────────────────────────────────

  Scenario: Fleet starts exactly 8 daemon processes
    When I call fleet.launch()
    Then exactly 8 daemon processes are running
    And each has a unique port index 0 through 7
    And each daemon PID is recorded in the fleet state file

  Scenario: Fleet launch is idempotent — second launch does not double processes
    Given the fleet is already running with 8 daemons
    When I call fleet.launch() a second time
    Then still exactly 8 daemon processes are running
    And no new processes are spawned

  Scenario: Watchdog respawns a dead daemon within 30 seconds
    Given the fleet is running with 8 daemons
    When daemon P4 is killed externally
    Then within 30 seconds the fleet has 8 running daemons again
    And a "hfo.gen89.fleet.respawn" stigmergy event is written for P4

  Scenario: Fleet nuke clears all processes and state before relaunch
    Given the fleet is running with 8 daemons
    When I call fleet.nuke()
    Then all 8 daemon processes are killed
    And the fleet state file is cleared
    And no zombie HFO Python processes remain

  # ─────────────────────────────────────────────────────────────
  # LLM router integration
  # ─────────────────────────────────────────────────────────────

  Scenario: Every daemon advisory uses the LLM router, not direct Ollama calls
    Given the fleet is running
    When any daemon's _advisory_tick() is called
    Then hfo_llm_router.generate() is invoked
    And no direct httpx.post to Ollama is made from within _advisory_tick

  Scenario: P0 TRUE_SEEING tick does not use any LLM
    Given the fleet is running
    When P0's _p0_true_seeing_tick() is called
    Then no LLM router call is made
    And only psutil and urllib are used for data collection

  Scenario Outline: Each daemon uses the correct role for LLM routing
    Given the fleet is running
    When daemon "<port_id>" completes one advisory tick
    Then the router was called with role "<role>"

    Examples:
      | port_id | role      |
      | P0      | advisory  |
      | P1      | analyst   |
      | P2      | coder     |
      | P3      | enricher  |
      | P4      | analyst   |
      | P5      | analyst   |
      | P6      | enricher  |
      | P7      | planner   |

  # ─────────────────────────────────────────────────────────────
  # Resource integration
  # ─────────────────────────────────────────────────────────────

  Scenario: Daemon backs off when governor returns HOLD
    Given the governor gate returns "HOLD"
    When a daemon's _advisory_tick() is called
    Then the LLM call is skipped
    And the daemon writes a "hfo.gen89.daemon.backpressure" stigmergy event
    And the daemon sleeps for its tick_rate before retrying

  Scenario: Daemon P0 TRUE_SEEING always runs regardless of governor gate
    Given the governor gate returns "HOLD"
    When P0's _advisory_tick() is called
    Then _p0_true_seeing_tick() is still executed
    And the status file is updated

  # ─────────────────────────────────────────────────────────────
  # Config / PAL
  # ─────────────────────────────────────────────────────────────

  Scenario: Daemon model assignment comes from CONFIG, not hardcoded strings
    Given ".env" contains "P0_MODEL=gemma3:4b"
    When P0 daemon is constructed
    Then daemon.config.model equals "gemma3:4b"
    And the string "gemma3:4b" does not appear hardcoded in hfo_octree_daemon.py

  Scenario: All 8 daemon models can be overridden via .env
    Given ".env" sets P0_MODEL through P7_MODEL
    When the fleet launches
    Then each daemon uses the model from its corresponding env var

  Scenario: Fleet reads tick rates from CONFIG
    Given ".env" contains "HFO_TICK_RATE_P0=60"
    When P0 daemon runs
    Then P0 sleeps 60 seconds between ticks

  # ─────────────────────────────────────────────────────────────
  # TRUE_SEEING stigmergy schedule
  # ─────────────────────────────────────────────────────────────

  Scenario: TRUE_SEEING writes to stigmergy at most once per 10 minutes
    Given P0 daemon has been running for 20 minutes
    When I count "hfo.gen89.p0.true_seeing" stigmergy events
    Then there are between 2 and 4 events (approximately 6 per hour)

  Scenario: TRUE_SEEING still updates the status file every 30 seconds
    Given P0 daemon has run 3 ticks
    When I read the status file modification times
    Then the file was updated every 30 seconds
    And exactly 1 stigmergy event was written (first tick only in first 10 min)
