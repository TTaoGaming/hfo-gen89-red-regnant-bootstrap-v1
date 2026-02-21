@infra @gemini @sbe
Feature: Gemini Tiered Model Registry
  As the HFO Gen89 swarm operator
  I need a centralized tiered model registry
  So that all agents use correct model IDs, rate limits, and capabilities
  Without hardcoding model strings across the codebase

  Background:
    Given the Gemini model registry module is importable

  # ═══════════════════════════════════════════════════════════════
  # Tier 1 — Invariant Scenarios (MUST NOT violate)
  # ═══════════════════════════════════════════════════════════════

  @invariant @tier1
  Scenario: Registry exports all 6 core tiers
    Then the registry contains exactly these core tiers:
      | tier         |
      | nano         |
      | flash        |
      | flash_25     |
      | lite_25      |
      | pro          |
      | experimental |

  @invariant @tier1
  Scenario: Each core tier maps to a valid model ID
    Then every core tier resolves to a non-empty model_id

  @invariant @tier1
  Scenario: Rate limits are positive integers for all models
    Then every registered model has rpm_limit > 0
    And every registered model has rpd_limit > 0

  @invariant @tier1
  Scenario: Pro tier supports thinking
    When I look up the "pro" tier
    Then the model spec has supports_thinking = true

  @invariant @tier1
  Scenario: Nano tier is the cheapest
    When I look up the "nano" tier
    Then the model spec has the highest rpm_limit among core tiers

  @invariant @tier1
  Scenario: API key env var resolver reads both names
    Then the registry module has a GEMINI_API_KEY attribute of type str

  # ═══════════════════════════════════════════════════════════════
  # Tier 2 — Happy-Path Scenarios (core desired behavior)
  # ═══════════════════════════════════════════════════════════════

  @happy @tier2
  Scenario Outline: Tier lookup resolves correct model ID
    When I call get_model with "<tier>"
    Then the model_id is "<expected_model_id>"

    Examples:
      | tier         | expected_model_id            |
      | nano         | gemini-2.0-flash-lite        |
      | flash        | gemini-2.0-flash             |
      | flash_25     | gemini-2.5-flash             |
      | lite_25      | gemini-2.5-flash-lite        |
      | pro          | gemini-2.5-pro               |
      | experimental | gemini-exp-1206              |

  @happy @tier2
  Scenario Outline: Legacy alias resolves to correct tier
    When I call get_model with alias "<alias>"
    Then the resolved tier is "<expected_tier>"

    Examples:
      | alias  | expected_tier |
      | quick  | nano          |
      | fast   | flash         |
      | think  | pro           |
      | deep   | pro           |

  @happy @tier2
  Scenario Outline: Direct model ID passthrough works
    When I call get_model with model_id "<model_id>"
    Then the model_id is "<model_id>"

    Examples:
      | model_id              |
      | gemini-2.5-pro        |
      | gemini-2.0-flash      |
      | gemini-2.5-flash-lite |

  @happy @tier2
  Scenario: Thinking-capable models are correctly identified
    When I get the list of thinking models
    Then it contains at least "pro" and "flash_25"
    And it does not contain "nano" or "flash"

  @happy @tier2
  Scenario: list_all_models returns structured data for every model
    When I call list_all_models
    Then each entry has keys: model_id, tier, display_name, rpm_limit, rpd_limit, supports_thinking

  # ═══════════════════════════════════════════════════════════════
  # Tier 3 — Rate Limiter Scenarios
  # ═══════════════════════════════════════════════════════════════

  @ratelimit @tier3
  Scenario: Fresh rate limiter allows first request
    Given a fresh GeminiRateLimiter
    When I check rate limit for "gemini-2.5-pro"
    Then it is allowed

  @ratelimit @tier3
  Scenario: Rate limiter blocks after RPM exceeded
    Given a fresh GeminiRateLimiter
    And I record 2 calls for "gemini-2.5-pro" within 1 minute
    When I check rate limit for "gemini-2.5-pro"
    Then it is blocked with reason containing "RPM"

  @ratelimit @tier3
  Scenario: Rate limiter tracks per-model independently
    Given a fresh GeminiRateLimiter
    And I record 2 calls for "gemini-2.5-pro" within 1 minute
    When I check rate limit for "gemini-2.0-flash"
    Then it is allowed

  @ratelimit @tier3
  Scenario: Usage summary reflects recorded calls
    Given a fresh GeminiRateLimiter
    And I record 3 calls for "gemini-2.0-flash-lite"
    When I get the usage summary
    Then "gemini-2.0-flash-lite" shows 3 calls used

  # ═══════════════════════════════════════════════════════════════
  # Tier 4 — Smart Selector Scenarios
  # ═══════════════════════════════════════════════════════════════

  @selector @tier4
  Scenario Outline: select_tier routes by complexity
    When I call select_tier with task_complexity "<complexity>"
    Then the selected tier is in "<expected_tiers>"

    Examples:
      | complexity | expected_tiers      |
      | trivial    | nano                |
      | low        | flash               |
      | medium     | flash_25            |
      | high       | pro                 |
      | extreme    | pro                 |

  @selector @tier4
  Scenario: select_tier falls back when rate-limited
    Given a fresh GeminiRateLimiter
    And I exhaust the RPM for "gemini-2.5-pro"
    When I call select_tier with task_complexity "high" and the rate_limiter
    Then the selected tier is NOT "pro"

  @selector @tier4
  Scenario: Batch flag prefers cheaper tiers
    When I call select_tier with task_complexity "medium" and is_batch true
    Then the selected tier is in "nano,flash,lite_25"

  # ═══════════════════════════════════════════════════════════════
  # Tier 5 — Swarm Role Mapping Scenarios
  # ═══════════════════════════════════════════════════════════════

  @swarm @tier5
  Scenario: SWARM_ROLE_MAP covers all critical roles
    Then SWARM_ROLE_MAP has entries for at least these roles:
      | role       |
      | triage     |
      | router     |
      | researcher |
      | coder      |
      | planner    |
      | validator  |

  @swarm @tier5
  Scenario: Triage and router map to cheapest tier
    Then SWARM_ROLE_MAP maps "triage" to "nano"
    And SWARM_ROLE_MAP maps "router" to "nano"

  @swarm @tier5
  Scenario: Planner and validator map to pro tier
    Then SWARM_ROLE_MAP maps "planner" to "pro"
    And SWARM_ROLE_MAP maps "validator" to "pro"
