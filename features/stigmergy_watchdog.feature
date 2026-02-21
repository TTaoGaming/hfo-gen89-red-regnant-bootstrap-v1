Feature: Port 0 Stigmergy Watchdog
  As a system architect
  I want a background daemon to monitor the stigmergy trail
  So that AI agents who bypass the MCP server or fail to complete the PREY8 loop are caught

  Scenario: Agent leaves an orphaned Perceive event
    Given an AI agent writes a "prey8.perceive" event to the SSOT
    And 5 minutes pass without a corresponding "prey8.yield" event
    When the Port 0 Stigmergy Watchdog scans the database
    Then the Watchdog should detect the orphaned session
    And the Watchdog should write a "prey8.memory_loss" event to the SSOT
    And the event should contain the orphaned session ID and agent ID

  Scenario: Agent writes a Yield event without a Perceive event
    Given an AI agent writes a "prey8.yield" event to the SSOT
    And there is no corresponding "prey8.perceive" event in the chain
    When the Port 0 Stigmergy Watchdog scans the database
    Then the Watchdog should detect the broken chain
    And the Watchdog should write a "prey8.tamper_alert" event to the SSOT
    And the event should flag the invalid nonce

  Scenario: Agent completes a valid PREY8 loop
    Given an AI agent writes a complete Perceive, React, Execute, Yield chain
    When the Port 0 Stigmergy Watchdog scans the database
    Then the Watchdog should validate the chain hashes
    And the Watchdog should take no action
