# features/resource_governor.feature
# HFO Gen90 — Resource Governor ATDD Contract
#
# Targets: CPU ≤ 80%, RAM ≤ 80%, VRAM ≤ 80% of budget, NPU ≥ 30% utilisation.
# Governor enforces these by: evicting idle VRAM models, emitting NPU-prefer
# signals, blocking new inferences above high-water marks.

@resource_governor
Feature: Resource Governor Enforcement

  Background:
    Given the resource governor is initialised
    And the SSOT database is accessible
    And Ollama is reachable at OLLAMA_BASE

  # ─────────────────────────────────────────────────────────────
  # Thresholds and targets
  # ─────────────────────────────────────────────────────────────

  Scenario: Governor reports GO when all resources below 80 percent
    Given CPU is 55 percent
    And RAM is 65 percent
    And VRAM is 4.0 GB of a 10.0 GB budget
    When I call governor.gate()
    Then gate returns "GO"
    And no eviction occurs

  Scenario: Governor evicts idle models when VRAM exceeds 80 percent
    Given VRAM is 8.5 GB of a 10.0 GB budget
    And Ollama has 2 models loaded: "granite4:3b" idle 5 min, "qwen2.5:3b" idle 8 min
    When I call governor.enforce()
    Then Ollama DELETE keep_alive is called for "qwen2.5:3b" first
    And a "hfo.gen90.governor.eviction" stigmergy event is written
    And the eviction reason is "vram_above_80pct"

  Scenario: Governor evicts all loaded models when VRAM exceeds 95 percent
    Given VRAM is 9.6 GB of a 10.0 GB budget
    And Ollama has 3 models loaded
    When I call governor.enforce()
    Then Ollama DELETE keep_alive is called for all 3 models
    And gate returns "HOLD" until re-polled below threshold

  Scenario: Governor blocks new Ollama inference when RAM above 88 percent
    Given RAM is 90 percent
    When a daemon requests an Ollama inference slot
    Then governor.wait_for_gpu_headroom() raises ResourcePressureError
    And the event "hfo.gen90.governor.ram_blocked" is written

  Scenario: Governor emits NPU-prefer signal when RAM above 80 percent
    Given RAM is 83 percent
    When I call governor.enforce()
    Then a "hfo.gen90.governor.npu_prefer" event is written to stigmergy
    And the signal contains field "ram_pct" equal to 83

  Scenario: Governor emits NPU-prefer signal when NPU utilisation below 30 percent
    Given the last 10 inferences show NPU used 2 times
    When I call governor.enforce()
    Then a "hfo.gen90.governor.npu_underutilised" event is written
    And the signal contains field "npu_rate_pct" equal to 20

  # ─────────────────────────────────────────────────────────────
  # Ghost process cleanup
  # ─────────────────────────────────────────────────────────────

  Scenario: Governor detects and kills duplicate HFO daemon processes
    Given 18 Python processes matching "hfo_" are running
    And the expected fleet size is 8
    When I call governor.reap_ghost_processes()
    Then processes above the fleet size limit are killed
    And a "hfo.gen90.governor.ghost_reaped" event records the killed PIDs
    And exactly 8 HFO daemon processes remain

  Scenario: Governor does not kill the fleet manager or watchdog
    Given a Python process named "hfo_daemon_fleet.py --watchdog" is running
    When I call governor.reap_ghost_processes()
    Then "hfo_daemon_fleet.py" is never killed

  # ─────────────────────────────────────────────────────────────
  # Scheduling and auto-enforcement
  # ─────────────────────────────────────────────────────────────

  Scenario: Governor runs enforcement automatically every 60 seconds
    Given the governor background thread is started
    When 65 seconds pass
    Then governor.enforce() has been called at least once
    And at least one "hfo.gen90.governor.cycle" event is in stigmergy

  Scenario: Governor writes a 10-minute rolling summary every 10 minutes
    Given 20 governor snapshots have been collected
    When I query stigmergy for "hfo.gen90.governor.summary"
    Then at least one summary event exists
    And it contains fields: avg_cpu_pct, avg_ram_pct, avg_vram_pct, npu_rate_pct

  # ─────────────────────────────────────────────────────────────
  # Config / PAL contract
  # ─────────────────────────────────────────────────────────────

  Scenario: All thresholds are read from CONFIG, not hardcoded
    Given ".env" contains "HFO_VRAM_TARGET_PCT=70"
    When the governor initialises
    Then governor.vram_target_pct equals 70.0
    And no numeric literal "80" appears in the governor enforcement logic

  Scenario Outline: Threshold env vars override defaults
    Given ".env" contains "<env_var>=<value>"
    When the governor initialises
    Then the governor attribute "<attr>" equals <expected>

    Examples:
      | env_var                  | value | attr              | expected |
      | HFO_VRAM_TARGET_PCT      | 70    | vram_target_pct   | 70.0     |
      | HFO_RAM_TARGET_PCT       | 75    | ram_target_pct    | 75.0     |
      | HFO_CPU_TARGET_PCT       | 80    | cpu_target_pct    | 80.0     |
      | HFO_NPU_MIN_RATE_PCT     | 30    | npu_min_rate_pct  | 30.0     |
      | HFO_EVICT_IDLE_AFTER_S   | 180   | evict_idle_after_s| 180.0    |
