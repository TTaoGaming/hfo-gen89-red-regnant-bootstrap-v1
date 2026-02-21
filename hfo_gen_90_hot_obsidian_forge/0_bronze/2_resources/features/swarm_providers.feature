@infra @swarm @sbe
Feature: Multi-Provider Swarm Configuration
  As the HFO Gen89 operator
  I need the swarm config to support both Ollama and Gemini providers
  So that agents can pick the best model per role with automatic fallback

  Background:
    Given the swarm config module is importable

  # ═══════════════════════════════════════════════════════════════
  # Tier 1 — Invariant Scenarios
  # ═══════════════════════════════════════════════════════════════

  @invariant @tier1
  Scenario: Provider enum has both Ollama and Gemini
    Then the Provider enum contains "ollama" and "gemini"

  @invariant @tier1
  Scenario: Default models are defined for both providers
    Then DEFAULT_OLLAMA_MODEL is a non-empty string
    And DEFAULT_GEMINI_TIER is a non-empty string

  @invariant @tier1
  Scenario: Backward-compat aliases exist
    Then DEFAULT_MODEL equals DEFAULT_OLLAMA_MODEL
    And RECOMMENDED_MODELS equals OLLAMA_RECOMMENDED_MODELS

  @invariant @tier1
  Scenario: ROLE_MODEL_MAP has 4-tuple entries
    Then every ROLE_MODEL_MAP entry has exactly 4 elements
    And element 0 is a Provider and element 2 is a Provider

  # ═══════════════════════════════════════════════════════════════
  # Tier 2 — Happy-Path: Role Resolution
  # ═══════════════════════════════════════════════════════════════

  @happy @tier2
  Scenario Outline: Role resolves to expected provider under gemini_first strategy
    Given GEMINI_AVAILABLE is temporarily true
    When I resolve model for role "<role>" with strategy "gemini_first"
    Then the provider is "<expected_provider>"

    Examples:
      | role        | expected_provider |
      | triage      | gemini            |
      | researcher  | gemini            |
      | coder       | gemini            |
      | planner     | gemini            |
      | web_searcher| gemini            |

  @happy @tier2
  Scenario Outline: Role resolves under ollama_only strategy
    When I resolve model for role "<role>" with strategy "ollama_only"
    Then the provider is "ollama"

    Examples:
      | role        |
      | triage      |
      | researcher  |
      | planner     |
      | deep_thinker|

  @happy @tier2
  Scenario: Gemini-preferred roles fall back to Ollama when Gemini unavailable
    Given GEMINI_AVAILABLE is temporarily false
    When I resolve model for role "researcher" with strategy "gemini_first"
    Then the provider is "ollama"

  # ═══════════════════════════════════════════════════════════════
  # Tier 3 — Client Factory Scenarios
  # ═══════════════════════════════════════════════════════════════

  @client @tier3
  Scenario: get_openai_client returns an OpenAI client
    When I call get_openai_client
    Then the client base_url contains "11434"

  @client @tier3
  Scenario: get_gemini_client raises when no API key
    Given GEMINI_AVAILABLE is temporarily false
    When I call get_gemini_client
    Then it raises RuntimeError

  # ═══════════════════════════════════════════════════════════════
  # Tier 4 — Model Discovery Scenarios
  # ═══════════════════════════════════════════════════════════════

  @discovery @tier4
  Scenario: list_gemini_models returns structured data
    When I call list_gemini_models
    Then each entry has provider = "gemini"
    And each entry has a tier field

  @discovery @tier4
  Scenario: list_all_available_models has both provider keys
    When I call list_all_available_models
    Then the result has keys "ollama" and "gemini"

  # ═══════════════════════════════════════════════════════════════
  # Tier 5 — Rate-Limited Fallback
  # ═══════════════════════════════════════════════════════════════

  @ratelimit @tier5
  Scenario: Gemini role falls back to Ollama when rate-limited
    Given a fresh swarm GeminiRateLimiter
    And GEMINI_AVAILABLE is temporarily true
    And I exhaust swarm RPM for "gemini-2.5-pro"
    When I resolve model for role "planner" with strategy "gemini_first" and the rate_limiter
    Then the provider is "ollama"

  @ratelimit @tier5
  Scenario: Strategy environment variable is respected
    Then PROVIDER_STRATEGY is a valid strategy string
