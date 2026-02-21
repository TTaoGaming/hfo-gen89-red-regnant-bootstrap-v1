@service @deployment @p7
Feature: 24/7 Agent Service Deployment Readiness
  As the HFO operator
  I need the eval orchestrator ready for autonomous 24/7 operation
  So that PREY8 loops run continuously without human intervention

  Background:
    Given the bronze resources path is configured

  # ── Invariant Tier: Script Validity ─────────────────────────

  Scenario: Eval orchestrator script parses without errors
    Given the script "hfo_eval_orchestrator.py" exists in bronze resources
    Then the script parses without syntax errors

  Scenario: Orchestrator has required CLI arguments
    When I inspect the orchestrator argument parser
    Then it accepts "--model" argument
    And it accepts "--interval" argument
    And it accepts "--once" argument
    And it accepts "--probe" argument

  Scenario: Orchestrator imports resolve
    When I check orchestrator import dependencies
    Then "httpx" is importable
    And "sqlite3" is importable
    And "json" is importable

  # ── Happy-Path Tier: Runtime Configuration ──────────────────

  Scenario: Environment variables for Ollama are configured
    Then the environment variable "OLLAMA_VULKAN" is "1"
    And the environment variable "OLLAMA_FLASH_ATTENTION" is "1"

  Scenario: Ollama API responds to health check
    Given Ollama API is reachable at the configured host
    When I query Ollama version
    Then the version is at least "0.16.0"

  # ── Performance Tier: Throughput Baseline ───────────────────

  Scenario: Single eval cycle completes within budget
    Given Ollama API is reachable at the configured host
    And model "qwen2.5:3b" is available
    When I run a single eval cycle with model "qwen2.5:3b"
    Then the cycle completes within 60 seconds
    And the response contains at least 3 tokens

  # ── Lifecycle Tier: Service Deployment Prerequisites ────────

  Scenario: SSOT database is writable for stigmergy events
    Given the SSOT database is connected
    When I check database write permissions
    Then the database allows INSERT to stigmergy_events

  Scenario: Log directory is writable
    When I check the bronze resources directory
    Then it is writable
