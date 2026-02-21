Feature: Eval Orchestrator — minimal user input
  As an operator I want a single command to run automated Perceive→Eval→Yield
  So that runs are recorded to the SSOT and artifacts are produced with minimal prompts

  Background:
    Given the repo contains `hfo_perceive.py`, `prey8_eval_harness.py`, and `hfo_yield.py`
    And `OLLAMA_HOST` is configured (default http://127.0.0.1:11434)

  Scenario: One-off orchestrator run with minimal input
    Given Ollama API is reachable and model "qwen2.5:7b" is available
    When I run `hfo_eval_orchestrator.py --model qwen2.5:7b --limit 5 --once`
    Then a PREY8 perceive event is written to the SSOT
    And an eval log file is created under `0_bronze/resources/orchestrator_outputs`
    And a PREY8 yield event is written to the SSOT

  Scenario: Continuous orchestrator run scheduled at startup
    Given Ollama API is reachable and the orchestrator script is accessible
    When I register a scheduled task to run the orchestrator at startup
    Then the scheduled task exists and runs the orchestrator command
    And periodic recap JSON files are created in `orchestrator_outputs`

  Scenario: GPU/NPU diagnostic execution
    Given the machine has an Intel Arc GPU and PowerShell access
    When I run `diagnose_gpu_npu.ps1`
    Then the script outputs video controller name and driver version
    And the script reports Ollama `/api/ps` and `/api/tags` reachability
