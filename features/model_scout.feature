# features/model_scout.feature
# HFO Gen90 — Model Scout Spell v1
# ATDD contract: Discover → Eval → GA → MAP-Elite → .env patch
#
# Guarded by pytest-bdd steps in tests/test_model_scout_steps.py
# These scenarios encode the invariants that were found broken in the first run:
#   - phi4 T3 returned "" (empty response, now caught by EMPTY_RESPONSE guard)
#   - phi4 T5 returned garbage binary (now caught by GARBAGE_OUTPUT guard)
#   - APEX_SPEED was incorrectly wired to HFO_P2_MODEL (now enforced by SLOT_TO_HFO_ENV)
#   - BFT was not verified post-GA (now MapEliteResult.validate() raises before .env write)
#   - task_scores were stripped from all_results (Pareto table showed only "-")

@model_scout
Feature: HFO Model Scout — MAP-Elite Portfolio Selection

  # ─────────────────────────────────────────────────────────────────────────
  # Slot → port mapping
  # ─────────────────────────────────────────────────────────────────────────

  Scenario: SLOT_TO_HFO_ENV covers every SLOT_NAME
    # If SLOT_NAMES grows (e.g. APEX_CLOUD added), test fails unless SLOT_TO_HFO_ENV is updated.
    # This is structurally enforced by an import-time assert in ga_select.py AND here.
    Given ga_select module is imported
    Then SLOT_TO_HFO_ENV keys equal SLOT_NAMES exactly

  Scenario: APEX_SPEED maps only to conductor warm model, not to P2 or P4
    # The first run incorrectly assigned APEX_SPEED (lfm2.5:1.2b, quality=18.8%) to
    # HFO_P2_MODEL and HFO_P4_PROSPECTOR_MODEL. Those ports need quality models.
    Given ga_select module is imported
    Then SLOT_TO_HFO_ENV "APEX_SPEED" contains "HFO_CONDUCTOR_GPU_WARM_MODEL"
    And SLOT_TO_HFO_ENV "APEX_SPEED" does not contain "HFO_P2_MODEL"
    And SLOT_TO_HFO_ENV "APEX_SPEED" does not contain "HFO_P4_PROSPECTOR_MODEL"

  Scenario: APEX_AUX maps to creation and red-team ports
    Given ga_select module is imported
    Then SLOT_TO_HFO_ENV "APEX_AUX" contains "HFO_P2_MODEL"
    And SLOT_TO_HFO_ENV "APEX_AUX" contains "HFO_P4_PROSPECTOR_MODEL"

  Scenario: APEX_COST maps to high-freq worker ports
    Given ga_select module is imported
    Then SLOT_TO_HFO_ENV "APEX_COST" contains "HFO_P5_MODEL"
    And SLOT_TO_HFO_ENV "APEX_COST" contains "HFO_P6_MODEL"

  Scenario: APEX_INTEL maps to advanced reasoning port
    Given ga_select module is imported
    Then SLOT_TO_HFO_ENV "APEX_INTEL" contains "HFO_P6_ADVANCED_MODEL"

  # ─────────────────────────────────────────────────────────────────────────
  # MapEliteResult validation
  # ─────────────────────────────────────────────────────────────────────────

  Scenario: validate() passes when BFT is satisfied
    Given a MapEliteResult with 4 distinct families and all SLOT_NAMES present
    When validate() is called
    Then no exception is raised

  Scenario: validate() raises ValueError on BFT violation
    Given a MapEliteResult with only 2 distinct families
    When validate() is called
    Then ValueError is raised containing "BFT VIOLATION"

  Scenario: validate() raises ValueError when a slot is missing
    Given a MapEliteResult missing slot "APEX_INTEL"
    When validate() is called
    Then ValueError is raised containing "SLOT SCHEMA VIOLATION"

  Scenario: validate() raises ValueError for unknown slot name
    # An unknown slot name (e.g. APEX_CLOUD replacing APEX_AUX) changes the slot-name
    # set and is caught by the SLOT SCHEMA VIOLATION check before env mapping.
    # The import-time assert in ga_select.py catches SLOT_TO_HFO_ENV divergence even earlier.
    Given a MapEliteResult with an unknown slot name "APEX_CLOUD"
    When validate() is called
    Then ValueError is raised containing "SLOT SCHEMA VIOLATION"

  # ─────────────────────────────────────────────────────────────────────────
  # promptfoo assertion guards (spec lint — checks YAML source not execution)
  # ─────────────────────────────────────────────────────────────────────────

  Scenario: Every promptfoo assertion has an EMPTY_RESPONSE guard
    # Catches the phi4 T3 bug: empty string passed through to startsWith check
    # which returned False silently with no diagnostic reason.
    Given promptfoo.yaml is loaded
    Then every assertion value contains "EMPTY_RESPONSE"

  Scenario: T5 assertion has a GARBAGE_OUTPUT printable-ratio guard
    # Catches the phi4 T5 bug: binary/garbage output that JSON.parse fails on
    # but with no reason recorded, making it hard to distinguish from a
    # genuine wrong-answer vs a model crash.
    Given promptfoo.yaml is loaded
    Then the T5_INSTRUCT assertion value contains "GARBAGE_OUTPUT"

  Scenario: T4 and T5 assertions return structured failure objects not bare booleans
    # Bare `return false` is opaque. Structured {pass, score, reason} allows
    # promptfoo to report WHY, and allows parse_promptfoo_output to distinguish
    # EMPTY_RESPONSE from a genuine logic failure at score-aggregation time.
    Given promptfoo.yaml is loaded
    Then the T4_JSON assertion value does not contain "return false"
    And the T5_INSTRUCT assertion value does not contain "return false"

  # ─────────────────────────────────────────────────────────────────────────
  # Output JSON schema
  # ─────────────────────────────────────────────────────────────────────────

  Scenario: map_elite_latest.json has required top-level keys
    Given map_elite_latest.json exists
    Then the JSON contains keys "slots", "families", "bft_satisfied", "ga_fitness", "all_results"

  Scenario: all_results entries include task_scores
    # First run: task_scores were stripped from all_results, causing the Pareto
    # table to display "-" instead of P/F for every model.
    Given map_elite_latest.json exists
    Then every entry in all_results has a "task_scores" field

  Scenario: map_elite_latest.json bft_satisfied is true
    Given map_elite_latest.json exists
    Then bft_satisfied is true
    And families list has at least 4 entries

  # ── Freshness enforcement ──────────────────────────────────────────────────
  # These scenarios fail CI when the model catalog goes stale or when an installed
  # model has a known better replacement that hasn't been flagged. The point is:
  # staleness is a TEST FAILURE, not a tribal knowledge problem.
  @model_scout
  Scenario: CURATED_PULL_CANDIDATES is not stale
    # Fails if CURATED_REFRESH_DATE in discover.py is more than 30 days ago.
    # This forces the developer to update the model list at least monthly.
    Given the discover module is imported
    Then CURATED_REFRESH_DATE is not more than 30 days old

  @model_scout
  Scenario: SUPERSEDED_BY registry covers known stale models
    # qwen2.5:3b is the model installed on this machine that has a known upgrade.
    # If it's not in SUPERSEDED_BY, the registry is incomplete.
    Given the discover module is imported
    Then SUPERSEDED_BY contains an entry for "qwen2.5:3b"
    And SUPERSEDED_BY contains an entry for "qwen2.5-coder:7b"
    And SUPERSEDED_BY contains an entry for "llama3.1:8b"
    And SUPERSEDED_BY contains an entry for "granite3.3:2b"

  @model_scout
  Scenario: SUPERSEDED_BY replacement models are all in CURATED or KNOWN_SIZES_GB
    # Every replacement target must be a known model so size estimation works.
    # Unknown replacements would silently filter out in VRAM budget check.
    Given the discover module is imported
    Then every SUPERSEDED_BY target appears in CURATED_PULL_CANDIDATES or KNOWN_SIZES_GB
