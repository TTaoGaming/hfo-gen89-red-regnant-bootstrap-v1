# HFO_WISH V2 — Correct-by-Construction Compiler
# P7 Spider Sovereign — Summoner of Seals and Spheres
# SBE/ATDD Specification (meta: WISH specifying itself)
# Generated: 2026-02-19 by P4 Red Regnant session b60db7e9cdca1818
#
# Tier structure follows SBE Towers (Doc 12):
#   Tier 1 — Invariant (fail-closed safety: MUST NOT violate)
#   Tier 2 — Happy-path (core desired behavior)
#   Tier 3 — Edge cases (recovery, degradation)
#   Tier 4 — Lifecycle (setup, teardown, migration)

Feature: WISH V2 Compiler — 5-Pass Correct-by-Construction Pipeline
  As the Spider Sovereign (P7 NAVIGATE)
  I want a 5-pass compiler that transforms operator INTENT into correct ARTIFACTS
  So that every artifact either fully passes all gates or is fail-closed rejected
  And the probability of an incorrect artifact surviving is ≤ 1/8^N

  Background:
    Given the SSOT database is accessible at the PAL-resolved path
    And hfo_p7_wish.py (V1) is importable as the Pass 4 engine
    And at least one AI model is available (Gemini or Ollama)

  # ═══════════════════════════════════════════════════════════════
  # TIER 1 — INVARIANT SCENARIOS (fail-closed safety)
  # ═══════════════════════════════════════════════════════════════

  Scenario: Empty intent is rejected at Pass 1
    Given no intent text is provided
    When the WISH V2 compiler is invoked
    Then the pipeline status is "REJECTED"
    And the error log contains "empty intent"
    And no Gherkin feature file is generated
    And no SSOT artifact events are written

  Scenario: Pass 5 is blocked when Pass 4 has DENIED verdicts
    Given a pipeline has reached Pass 4
    And Pass 4 returned 1 DENIED verdict with 2 violations
    When Pass 5 is attempted
    Then Pass 5 does not execute
    And the pipeline status is "DENIED"
    And the SSOT event type is "hfo.gen89.p7.wish.v2.pass4.denied"
    And no artifact files are created

  Scenario: Invalid Gherkin output from AI is rejected at Pass 1
    Given an intent "build the omega physics system" is provided
    And the AI model returns output that is not valid Gherkin syntax
    When Pass 1 validates the output
    Then the pipeline status is "REJECTED"
    And the error log contains "Gherkin validation failed"
    And the SSOT event type is "hfo.gen89.p7.wish.v2.pass1.rejected"

  Scenario: Pipeline state survives process restart
    Given a pipeline is in Pass 2 (GHERKIN_TO_SDD)
    And the process terminates unexpectedly
    When the compiler is restarted and status is queried
    Then the pipeline shows current_pass = 2 and status = "COMPILING"
    And all Pass 1 results are preserved

  Scenario: No silent state changes — every transition is logged
    Given a pipeline transitions from Pass 1 to Pass 2
    Then a CloudEvent with type "hfo.gen89.p7.wish.v2.pass1.completed" exists in SSOT
    And the event data contains the pipeline ID and scenario count

  # ═══════════════════════════════════════════════════════════════
  # TIER 2 — HAPPY-PATH SCENARIOS (core desired behavior)
  # ═══════════════════════════════════════════════════════════════

  Scenario: Full pipeline — intent to artifact via 5 passes
    Given the intent "verify SSOT database health including tables and FTS"
    And context documents [423, 424] are provided
    When the WISH V2 compiler runs the full pipeline
    Then Pass 1 produces a .feature file with at least 3 scenarios
    And Pass 2 produces at least 3 SDD task cards in YAML format
    And Pass 3 registers at least 3 check functions in V1 WISH_CHECKS
    And Pass 4 evaluates all wishes and returns verdicts
    And if all Pass 4 verdicts are GRANTED then Pass 5 produces an artifact
    And the pipeline status is "GRANTED"
    And a completion receipt exists in SSOT

  Scenario: Pass 1 generates valid Gherkin from natural language
    Given the intent "all bound daemons must have heartbeat within 1 hour"
    When Pass 1 (Intent → Gherkin) is invoked
    Then the output is syntactically valid Gherkin
    And the output contains at least 1 "Feature:" declaration
    And the output contains at least 2 "Scenario:" blocks
    And each Scenario has Given, When, and Then clauses
    And the Pass 1 result includes ai_model and ai_latency_ms

  Scenario: Pass 2 generates SDD task cards from Gherkin
    Given a validated .feature file with 3 scenarios
    When Pass 2 (Gherkin → SDD) is invoked
    Then 3 SDD task cards are produced
    And each card has fields: task_id, feature, scenario, sbe_given, sbe_when, sbe_then
    And each card has port_mapping and meadows_level
    And each card has artifact_target and test_target

  Scenario: Pass 3 generates executable tests from SDD
    Given 3 validated SDD task cards
    When Pass 3 (SDD → SBE/ATDD) is invoked
    Then at least 3 Python test functions are generated
    And each test function is syntactically valid (passes ast.parse)
    And each test is registered as a V1 WISH_CHECKS entry
    And the coverage_map links each SDD card to its test

  Scenario: Pass 4 delegates to V1 for verification
    Given 3 registered check functions in V1 WISH_CHECKS
    When Pass 4 (SBE → Proof) invokes V1 spell_audit()
    Then each wish receives a GRANTED or DENIED verdict
    And verdicts are recorded in the pipeline state
    And CloudEvents are written to SSOT for each verdict

  Scenario: Pass 5 generates artifact only after all-GRANTED proof
    Given Pass 4 returned all-GRANTED for 3 wishes
    And the SDD cards target file "hfo_omega_ssot_health.py"
    When Pass 5 (Proof → Artifact) is invoked
    Then the target file is created
    And a deployment receipt is written to SSOT
    And the pipeline status transitions to "GRANTED"

  # ═══════════════════════════════════════════════════════════════
  # TIER 3 — EDGE CASE SCENARIOS (recovery, degradation)
  # ═══════════════════════════════════════════════════════════════

  Scenario: AI unavailable falls back gracefully in Pass 1
    Given the intent "check daemon heartbeats"
    And no AI model is reachable (Gemini timeout, Ollama down)
    When Pass 1 is attempted
    Then the pipeline status is "REJECTED"
    And the error log contains "AI model unavailable"
    And a diagnostic CloudEvent is written to SSOT
    And the operator is informed of available fallback options

  Scenario: Partial pipeline can be resumed from last successful pass
    Given a pipeline completed Pass 2 and failed at Pass 3
    When the operator runs "resume {wish_id} --from-pass 3"
    Then Pass 3 re-runs using the Pass 2 results
    And Pass 1 and Pass 2 are not re-executed
    And the pipeline continues from Pass 3 onward

  Scenario: Operator can reject AI Gherkin and re-run Pass 1
    Given Pass 1 generated Gherkin output
    And the operator reviews and rejects the output
    When the operator re-runs Pass 1 with refined intent
    Then a new Pass 1 result replaces the rejected one
    And the rejection is logged to SSOT
    And the pipeline continues to Pass 2 with the new output

  Scenario: Concurrent pipelines do not interfere
    Given pipeline A is at Pass 3
    And pipeline B is at Pass 1
    When both pipelines advance simultaneously
    Then pipeline A's Pass 3 results do not contaminate pipeline B
    And each pipeline's V1 wish IDs are distinct
    And each pipeline's CloudEvents reference their own pipeline ID

  # ═══════════════════════════════════════════════════════════════
  # TIER 4 — LIFECYCLE SCENARIOS (setup, teardown, migration)
  # ═══════════════════════════════════════════════════════════════

  Scenario: First run initializes pipeline state file
    Given no .p7_wish_v2_pipelines.json exists
    When the WISH V2 compiler is invoked for the first time
    Then .p7_wish_v2_pipelines.json is created
    And it contains an empty pipelines dict and next_id = 1

  Scenario: V1 wish state is not corrupted by V2 operations
    Given V1 has 5 active wishes in .p7_wish_state.json
    When V2 creates 3 new pipelines that each register 3 V1 wishes
    Then V1's original 5 wishes still exist unchanged
    And V1's wish IDs 6-14 are used by V2's registrations
    And V1 spell_list() shows all 14 wishes

  Scenario: Pipeline cleanup after successful completion
    Given a pipeline is in status "GRANTED"
    When the operator runs "cleanup {wish_id}"
    Then the pipeline is archived (status = "ARCHIVED")
    And its V1 wishes remain active for ongoing auditing
    And the generated artifacts are not deleted

  # ═══════════════════════════════════════════════════════════════
  # OMEGA-SPECIFIC SCENARIOS (Mission Thread compilation targets)
  # ═══════════════════════════════════════════════════════════════

  Scenario: Omega Touch Parity compilation target
    Given the compilation target "omega_vertical_slice"
    And the intent "touch parity: every Omega pointer interaction must produce
      the same state change as a human finger tap"
    When the WISH V2 compiler processes this target
    Then the Gherkin includes scenarios for:
      | scenario                          | tier      |
      | Single tap produces click         | happy     |
      | No accidental activation          | invariant |
      | Jitter does not produce duplicates| invariant |
    And the SDD cards map to ports P0, P1, P2, P3, P5
    And the generated tests reference the Omega 6-stage pipeline

  Scenario: Omega Physics Anti-Thrash compilation target
    Given the compilation target "omega_vertical_slice"
    And the intent "physics anti-thrash: 1-Euro filter with velocity clamping
      reduces 30Hz MediaPipe jitter to stable cursor position"
    When Pass 1 generates Gherkin
    Then the scenarios reference concrete filter parameters
    And at least one scenario tests the 1-Euro filter cutoff frequency
    And at least one invariant scenario tests boundary thrash rejection
