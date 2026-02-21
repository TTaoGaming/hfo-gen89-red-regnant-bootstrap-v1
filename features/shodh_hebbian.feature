# features/shodh_hebbian.feature
# HFO Gen89 — Shodh Hebbian Learning ATDD Contract
#
# SBE: Specifies the Hebbian co-retrieval learning loop that strengthens
# shodh_associations AND emits CloudEvents into stigmergy_events.
#
# Architecture under test (hfo_shodh.py):
#   1. cmd_co_retrieve() receives a list of doc_ids co-retrieved in one turn
#   2. Hub docs (catalog + orientation docs) are EXCLUDED from pairing
#   3. For every non-hub pair (a, b): weight += GAMMA, capped at 1.0
#   4. A CloudEvent (hfo.gen89.shodh.hebbian.co_retrieval) is written to
#      stigmergy_events with full signal_metadata — closing the feedback loop
#
# P4 Adversarial Invariants (GRUDGE guards):
#   - Hub doc IDs MUST NEVER appear as doc_a or doc_b in new association rows
#   - Weight MUST NOT exceed 1.0 regardless of activation count
#   - stigmergy_events write MUST contain valid signal_metadata (gate enforced)
#   - Returning fewer than 2 non-hub docs MUST NOT write anything

@shodh_hebbian
Feature: Shodh Hebbian co-retrieval learning loop

  Background:
    Given the Shodh module "hfo_shodh" is importable
    And an isolated in-memory SSOT database with full schema exists

  # ──────────────────────────────────────────────────────────────
  # § 1  INVARIANTS — Fail-closed gate: must never be violated
  # ──────────────────────────────────────────────────────────────

  Scenario: Hub docs are excluded from association pairs
    Given doc_ids [37, 53, 157, 304] where doc 37 is a hub
    When cmd_co_retrieve is called
    Then shodh_associations contains no row where doc_a=37 or doc_b=37
    And the result reports hub_excluded containing 37

  Scenario: Weight ceiling is 1.0 — repeated activation cannot overflow
    Given doc_ids [100, 200] with no hubs
    When cmd_co_retrieve is called 15 times for the same pair
    Then the weight for pair (100, 200) is exactly 1.0
    And co_activation_count for pair (100, 200) is 15

  Scenario: Fewer than 2 non-hub docs produces a SKIPPED result without writing
    Given doc_ids [37] where all docs are hubs
    When cmd_co_retrieve is called
    Then no rows are inserted into shodh_associations
    And no rows are inserted into shodh_co_retrieval
    And the result status is "SKIPPED"

  # ──────────────────────────────────────────────────────────────
  # § 2  HAPPY PATH — Core desired behaviour
  # ──────────────────────────────────────────────────────────────

  Scenario: Co-retrieved docs accumulate association weight
    Given doc_ids [53, 157, 304] with no hubs
    When cmd_co_retrieve is called
    Then 3 association pairs are created
    And each pair has weight equal to GAMMA (0.1)
    And shodh_co_retrieval contains 3 rows for this session

  Scenario: Repeated co-retrieval strengthens weight additively
    Given doc_ids [53, 304] with no hubs
    When cmd_co_retrieve is called 3 times with the same session
    Then the weight for pair (53, 304) is approximately 0.3

  Scenario: Result dict carries correct metadata
    Given doc_ids [53, 157] with no hubs
    When cmd_co_retrieve is called
    Then the result status is "OK"
    And the result docs_recorded is 2
    And the result pairs_updated is 1
    And the result hub_excluded is empty

  # ──────────────────────────────────────────────────────────────
  # § 3  STIGMERGY FEEDBACK — Hebbian strengthens the event trail
  # ──────────────────────────────────────────────────────────────

  Scenario: Successful co-retrieval emits a CloudEvent to stigmergy_events
    Given doc_ids [53, 157, 304] with no hubs
    When cmd_co_retrieve is called
    Then a stigmergy event of type "hfo.gen89.shodh.hebbian.co_retrieval" is written
    And the event data_json contains a "signal_metadata" key
    And the signal_metadata port is "P6"
    And the event data_json contains "pairs_updated"
    And the event data_json contains "hub_excluded"

  Scenario: No stigmergy event is written when all docs are hubs
    Given doc_ids [37] where all docs are hubs
    When cmd_co_retrieve is called
    Then no stigmergy event of type "hfo.gen89.shodh.hebbian.co_retrieval" is written

  # ──────────────────────────────────────────────────────────────
  # § 4  GRUDGE GUARDS — Negative specs prevent regressions
  # ──────────────────────────────────────────────────────────────

  Scenario: GRUDGE — hub IDs are not silently dropped from docs_recorded count
    Given doc_ids [37, 53, 157] where doc 37 is a hub
    When cmd_co_retrieve is called
    Then the result docs_recorded is 3
    And the result pairs_updated is 1

  Scenario: GRUDGE — stigmergy write failure does not raise or block retrieval
    Given doc_ids [53, 157] with no hubs
    And stigmergy writes are patched to raise an exception
    When cmd_co_retrieve is called
    Then no exception is raised
    And shodh_associations still contains the pair (53, 157)
