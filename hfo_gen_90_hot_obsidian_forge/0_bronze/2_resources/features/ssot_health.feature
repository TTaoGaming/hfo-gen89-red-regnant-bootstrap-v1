@infra @ssot
Feature: SSOT Database Health — Documents and Stigmergy
  As an HFO operator
  I want the SSOT database to be accessible, populated, and growing
  So that 24/7 agents have a knowledge base and leave traces

  Scenario: SSOT database file exists
    Given the SSOT database path is configured
    Then the database file exists on disk

  Scenario: SSOT has sufficient documents
    Given the SSOT database is connected
    When I count documents
    Then there are at least the configured minimum documents

  Scenario: SSOT has FTS5 search index
    Given the SSOT database is connected
    When I search FTS for "PREY8"
    Then at least 1 result is returned

  Scenario: Stigmergy trail is active
    Given the SSOT database is connected
    When I count stigmergy events
    Then there are at least the configured minimum events

  Scenario: Recent stigmergy activity exists
    Given the SSOT database is connected
    When I query the latest stigmergy event
    Then the latest event timestamp is within the last 7 days
