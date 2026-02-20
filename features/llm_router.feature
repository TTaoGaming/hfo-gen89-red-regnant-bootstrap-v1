# features/llm_router.feature
# HFO Gen89 — Vendor-Agnostic LLM Router
# ATDD contract for hfo_llm_router.py
#
# Providers: NPU (OpenVINO) → Ollama (local GPU) → Gemini (cloud) → OpenRouter (cloud)
# Priority order: NPU first (free, local, zero VRAM), Ollama second,
#                 Gemini third (grounded), OpenRouter last (paid fallback).

@llm_router
Feature: Vendor-Agnostic LLM Router

  Background:
    Given the LLM router is initialised with default config
    And the resource status file exists

  # ─────────────────────────────────────────────────────────────
  # Provider selection
  # ─────────────────────────────────────────────────────────────

  Scenario: Router prefers NPU when configured and resources allow
    Given the NPU model is configured at "P6_NPU_LLM_MODEL"
    And RAM usage is below 80 percent
    And the prompt is under 512 tokens
    When I call the router with provider_strategy "npu_first"
    Then the router selects provider "npu"
    And no Ollama request is made

  Scenario: Router falls back to Ollama when NPU is unavailable
    Given the NPU model path does not exist
    And VRAM headroom is above 2 GB
    When I call the router with provider_strategy "npu_first"
    Then the router selects provider "ollama"
    And the fallback is recorded in the router log

  Scenario: Router falls back to Gemini when Ollama VRAM is exhausted
    Given Ollama VRAM usage is above 80 percent of budget
    And GEMINI_API_KEY is set
    When I call the router with provider_strategy "npu_first"
    Then the router selects provider "gemini"
    And a "vram_pressure" reason is attached to the event

  Scenario: Router falls back to OpenRouter when Gemini rate-limited
    Given Ollama VRAM usage is above 80 percent of budget
    And Gemini returns a 429 rate-limit response
    And OPENROUTER_API_KEY is set
    When I call the router with provider_strategy "npu_first"
    Then the router selects provider "openrouter"
    And a "gemini_rate_limited" reason is attached to the event

  Scenario: Router raises RouterExhausted when all providers fail
    Given the NPU model path does not exist
    And Ollama returns a connection error
    And GEMINI_API_KEY is not set
    And OPENROUTER_API_KEY is not set
    When I call the router with provider_strategy "npu_first"
    Then a RouterExhausted exception is raised
    And the failure is written to stigmergy as "hfo.gen89.llm_router.exhausted"

  # ─────────────────────────────────────────────────────────────
  # Ollama-only strategy (for high-context tasks)
  # ─────────────────────────────────────────────────────────────

  Scenario: Ollama-only strategy skips NPU and cloud
    Given VRAM headroom is above 2 GB
    When I call the router with provider_strategy "ollama_only"
    Then the router selects provider "ollama"
    And provider "npu" is never attempted
    And provider "gemini" is never attempted

  # ─────────────────────────────────────────────────────────────
  # Role-based model selection
  # ─────────────────────────────────────────────────────────────

  Scenario Outline: Role selects the correct model
    When I request inference for role "<role>"
    Then the preferred provider is "<preferred_provider>"
    And the preferred model is "<preferred_model>"

    Examples:
      | role         | preferred_provider | preferred_model            |
      | advisory     | npu                | ${P6_NPU_LLM_MODEL}        |
      | enricher     | npu                | ${P6_NPU_LLM_MODEL}        |
      | analyst      | ollama             | gemma3:4b                  |
      | researcher   | gemini             | flash_25                   |
      | planner      | gemini             | pro                        |
      | coder        | gemini             | flash_25                   |

  # ─────────────────────────────────────────────────────────────
  # Resource-aware throttling
  # ─────────────────────────────────────────────────────────────

  Scenario: Router blocks Ollama call when RAM above 88 percent
    Given RAM usage is 92 percent
    And the OLLAMA provider would be selected
    When I call the router with provider_strategy "npu_first"
    Then the router skips Ollama due to "ram_pressure"
    And the router escalates to "gemini"

  Scenario: Router blocks all inference when RAM above 95 percent
    Given RAM usage is 96 percent
    When I call the router with any strategy
    Then a ResourcePressureError is raised with message containing "RAM"
    And the event "hfo.gen89.llm_router.ram_blocked" is written to stigmergy

  # ─────────────────────────────────────────────────────────────
  # Observability contract
  # ─────────────────────────────────────────────────────────────

  Scenario: Every successful inference writes a routing event to stigmergy
    Given the NPU model is configured
    When I call the router and inference succeeds
    Then a "hfo.gen89.llm_router.inference" event is in stigmergy
    And the event contains fields: provider, model, latency_ms, tokens, port

  Scenario: Router tracks NPU utilisation rate over 10-minute window
    Given 10 inferences have completed in the last 10 minutes
    And 3 of them used the NPU
    When I query router.npu_utilisation_rate()
    Then the result is 0.30

  # ─────────────────────────────────────────────────────────────
  # Config / PAL layer
  # ─────────────────────────────────────────────────────────────

  Scenario: Router reads all config from .env via CONFIG object
    Given ".env" contains "LLM_ROUTER_STRATEGY=ollama_first"
    When the router is constructed
    Then router.strategy equals "ollama_first"
    And no os.getenv() calls are made outside the Config dataclass

  Scenario: Changing provider strategy via env var takes effect on next call
    Given the router is running
    When the environment variable "LLM_ROUTER_STRATEGY" is changed to "gemini_first"
    And the router is reloaded
    Then the next call uses provider "gemini" as first choice
