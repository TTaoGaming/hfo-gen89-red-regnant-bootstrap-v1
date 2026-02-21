@braided @ssot @mission
Feature: Braided Mission Thread Integrity
  As the HFO operator
  I need the braided mission thread to accurately reflect current system state
  So that PREY8 agents can make informed steering decisions from the SSOT

  Background:
    Given the SSOT database is connected

  # ── Invariant Tier: Structural Integrity ────────────────────

  Scenario: Mission state table exists with correct schema
    When I inspect the mission_state table
    Then it has columns "thread_key, parent_key, thread_type, title, port, fitness, mutation_confidence, status"

  Scenario: Both alpha and omega mission threads exist
    When I query mission threads
    Then thread "alpha" exists with type "mission"
    And thread "omega" exists with type "mission"

  Scenario: ERA_4 is the current active era
    When I query era threads
    Then thread "ERA_4" has status "active"
    And thread "ERA_4" has fitness at least 0.4

  # ── Happy-Path Tier: Task Coverage ─────────────────────────

  Scenario: All 8 octree ports have at least one task
    When I query tasks grouped by port
    Then port "P0" has at least 1 task
    And port "P2" has at least 1 task
    And port "P3" has at least 1 task
    And port "P4" has at least 1 task
    And port "P5" has at least 1 task
    And port "P6" has at least 1 task
    And port "P7" has at least 1 task

  Scenario: High-confidence tasks have fitness above 0.7
    When I query tasks with fitness above 0.7
    Then at least 3 tasks meet the threshold
    And each has mutation_confidence above 60

  Scenario: BDD infrastructure task is recorded
    When I query thread "T-P5-002"
    Then the title contains "BDD"
    And the fitness is at least 0.8
    And the port is "P5"

  Scenario: GPU Vulkan task is recorded
    When I query thread "T-P0-002"
    Then the title contains "GPU"
    And the fitness is at least 0.8
    And the port is "P0"

  Scenario: 24/7 service deployment task exists
    When I query thread "T-P7-002"
    Then the title matches "Service" or "Orchestrator"
    And the status is "active"
    And the port is "P7"

  # ── Lifecycle Tier: Parent-Child Integrity ──────────────────

  Scenario: All tasks have valid parent keys
    When I query all tasks
    Then every task's parent_key references an existing thread

  Scenario: No orphan waypoints
    When I query all waypoints
    Then every waypoint's parent_key references an existing era
