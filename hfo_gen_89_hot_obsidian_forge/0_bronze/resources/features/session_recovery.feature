@infra @session @red
Feature: Session Recovery — Orphan Reaper and Yield Enforcement
  As an HFO operator
  I want orphaned PREY8 sessions to be detected and reaped
  So that session mortality (currently 87.3%) is reduced through structural enforcement

  Background:
    Given the SSOT database is connected

  Scenario: Yield ratio exceeds minimum threshold
    When I compute the yield ratio from SSOT
    Then the yield ratio is at least 25 percent

  Scenario: No orphaned sessions older than 24 hours
    When I scan for orphaned perceive events without matching yields
    Then no orphaned session is older than 24 hours

  Scenario: Orphan reaper function exists and is callable
    Given the session recovery module is importable
    When I call the orphan reaper scan function
    Then it returns a list of orphaned session records

  Scenario: Orphan reaper closes stale sessions with failure yield
    Given there are orphaned sessions older than the reaper threshold
    When the orphan reaper runs
    Then each orphaned session gets a failure yield event in stigmergy
    And the yield ratio improves

  Scenario: Memory loss events reference their lost session
    When I query memory loss events from SSOT
    Then each memory loss event contains a lost_session field
    And each memory loss event contains a lost_phase field
