Feature: MCP Server-Side PREY8 Enforcement
  As a system architect
  I want the MCP server to enforce the PREY8 state machine
  So that AI agents cannot bypass the cognitive persistence loop

  Scenario: Agent attempts to React before Perceiving
    Given a new AI agent session is idle
    When the agent calls "prey8_react"
    Then the MCP server should return a "GATE_BLOCKED" error
    And the error should state "You must call prey8_perceive first"
    And a "tamper_alert" event should be logged to the SSOT

  Scenario: Agent attempts to Execute before Reacting
    Given an AI agent session is in the "perceived" state
    When the agent calls "prey8_execute"
    Then the MCP server should return a "GATE_BLOCKED" error
    And the error should state "You must call prey8_react first"
    And a "tamper_alert" event should be logged to the SSOT

  Scenario: Agent successfully completes the PREY8 loop
    Given a new AI agent session is idle
    When the agent calls "prey8_perceive" with valid gate fields
    And the agent calls "prey8_react" with valid gate fields
    And the agent calls "prey8_execute" with valid gate fields
    And the agent calls "prey8_yield" with valid gate fields
    Then the session state should return to "idle"
    And all 4 events should be written to the SSOT with a valid hash chain
