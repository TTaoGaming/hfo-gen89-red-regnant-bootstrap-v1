@infra @fitness @red
Feature: Fitness Decay — Staleness Detection with Half-Life
  As an HFO operator
  I want task fitness scores to decay over time with a configurable half-life
  So that stale tasks are surfaced rather than hiding behind frozen scores

  Background:
    Given the SSOT database is connected

  Scenario: Tasks have last_touched timestamps
    When I query mission_state tasks
    Then each task row has a non-null last_touched timestamp

  Scenario: Fitness decay function exists and is callable
    Given the fitness decay module is importable
    When I call compute_decayed_fitness with fitness 0.8 and age 30 days
    Then the decayed fitness is less than 0.8

  Scenario: Half-life of 14 days halves the fitness
    Given a task with fitness 1.0 last touched 14 days ago
    When I compute decayed fitness with half-life 14 days
    Then the decayed fitness is approximately 0.5

  Scenario: Recently touched tasks retain full fitness
    Given a task with fitness 0.9 last touched 1 day ago
    When I compute decayed fitness with half-life 14 days
    Then the decayed fitness is at least 0.85
