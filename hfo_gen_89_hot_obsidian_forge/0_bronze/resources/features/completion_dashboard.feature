@completion @dashboard @pareto
Feature: Pareto Completion Dashboard
  As the HFO operator
  I need a real-time view of task fitness across the braided mission thread
  So that I can identify the highest-leverage next actions

  Background:
    Given the SSOT database is connected

  # ── Invariant Tier: Dashboard Data Availability ─────────────

  Scenario: Mission state has at least 10 tasks
    When I count mission_state tasks
    Then there are at least 10 tasks

  Scenario: Average fitness across all tasks meets minimum
    When I calculate average task fitness
    Then the average is above 0.4

  Scenario: No task has negative fitness
    When I query all task fitness values
    Then every fitness is between 0.0 and 1.0

  # ── Happy-Path Tier: Confidence Distribution ────────────────

  Scenario: At least 3 tasks have HIGH confidence (fitness >= 0.7)
    When I count tasks with fitness at least 0.7
    Then there are at least 3 in the HIGH tier

  Scenario: No more than 3 tasks have LOW confidence (fitness < 0.3)
    When I count tasks with fitness below 0.3
    Then there are at most 3 in the LOW tier

  # ── Performance Tier: Braided Thread Velocity ───────────────

  Scenario: Recent stigmergy shows active work
    When I count stigmergy events in the last 24 hours
    Then there are at least 5 recent events

  Scenario: PREY8 sessions are completing (not orphaning)
    When I count yield events vs perceive events in the last 24 hours
    Then the yield-to-perceive ratio is at least 0.15
