@infra @ollama
Feature: Ollama Fleet Readiness — Models and API
  As an HFO operator
  I want the Ollama model fleet to be healthy and accessible
  So that 24/7 agents can switch roles without manual intervention

  Background:
    Given Ollama API is reachable at the configured host

  Scenario: Ollama version is recent enough
    When I query Ollama version
    Then the version is at least "0.16.0"

  Scenario: Minimum model fleet is available
    When I list available Ollama models
    Then at least the configured minimum number of models are available

  Scenario: Fleet covers multiple parameter sizes
    When I list available Ollama models
    Then there is at least 1 model under 2 GB
    And there is at least 1 model between 4 GB and 10 GB

  Scenario: No more than 2 models loaded simultaneously
    When I check loaded models
    Then at most 2 models are loaded in memory

  Scenario: Flash attention is enabled
    Then the environment variable "OLLAMA_FLASH_ATTENTION" is "1"
