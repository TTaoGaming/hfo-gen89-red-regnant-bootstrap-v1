@infra @agent @24x7
Feature: Agent 24/7 Readiness — Orchestrator and PREY8 Loop
  As an HFO operator
  I want a stable orchestrator that runs continuously
  So that a single agent performs Perceive→Eval→Yield without manual input

  Scenario: Orchestrator script exists and is syntactically valid
    Given the orchestrator script "hfo_eval_orchestrator.py" exists
    Then the script parses without syntax errors

  Scenario: Perceive bookend script is operational
    Given the script "hfo_perceive.py" exists
    When I run perceive with probe "BDD health check"
    Then a perceive event is written to the SSOT

  Scenario: Yield bookend script is operational
    Given the script "hfo_yield.py" exists
    When I run yield with summary "BDD health check yield"
    Then a yield event is written to the SSOT

  Scenario: PREY8 MCP server script exists
    Given the script "hfo_prey8_mcp_server.py" exists
    Then the script parses without syntax errors

  Scenario: Eval harness script exists and is syntactically valid
    Given the script "prey8_eval_harness.py" exists
    Then the script parses without syntax errors
