@infra @gpu
Feature: GPU Utilization — Intel Arc 140V via Vulkan
  As an HFO operator running 24/7 agents
  I want the GPU to be detected, enabled, and actively used for inference
  So that models run at optimal speed and VRAM is not wasted

  Background:
    Given Ollama API is reachable at the configured host

  Scenario: Vulkan environment variable is set
    Then the environment variable "OLLAMA_VULKAN" is "1"

  Scenario: Ollama detects the Intel Arc GPU
    When I query Ollama for available GPUs
    Then at least 1 GPU is reported
    And the GPU name contains "Arc"

  Scenario: Model loads into VRAM when Vulkan is enabled
    Given model "qwen2.5:3b" is available
    When I generate 5 tokens with model "qwen2.5:3b"
    Then the model "qwen2.5:3b" is loaded
    And VRAM usage for "qwen2.5:3b" is greater than 0 bytes

  Scenario: Warm generation throughput meets Pareto threshold
    Given model "qwen2.5:3b" is loaded in VRAM
    When I generate 20 tokens with model "qwen2.5:3b"
    Then generation throughput is at least the configured minimum tok/s

  Scenario: Prompt evaluation throughput meets Pareto threshold
    Given model "qwen2.5:3b" is loaded in VRAM
    When I generate 20 tokens with model "qwen2.5:3b"
    Then prompt throughput is at least the configured minimum tok/s
