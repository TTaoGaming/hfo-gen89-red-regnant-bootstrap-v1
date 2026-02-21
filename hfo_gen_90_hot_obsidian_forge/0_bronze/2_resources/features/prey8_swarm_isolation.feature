@prey8 @swarm @deny-by-default
Feature: PREY8 Swarm Isolation and Deny-by-Default
  As the P5 Pyre Praetorian gate
  I need to verify that the PREY8 MCP server enforces agent identity,
  session isolation, and port-pair authorization
  So that the swarm hive is secure-by-construction against
  session pollution, reward hacking, and unauthorized access.

  Background: PREY8 v4.0 swarm architecture
    Given the PREY8 MCP server is v4.0 with AGENT_REGISTRY
    And 14 agents are registered in the AGENT_REGISTRY
    And deny-by-default is the authorization policy

  # ═══════════════════════════════════════════════════════
  #  A1: DENY-BY-DEFAULT — Unknown agents are BLOCKED
  # ═══════════════════════════════════════════════════════

  Scenario: Unknown agent is gate-blocked on perceive
    When an unknown agent "rogue_agent_007" calls prey8_perceive
    Then the response status is "GATE_BLOCKED"
    And the response contains "is not registered"
    And a gate_blocked event is written to stigmergy

  Scenario: Empty agent_id is gate-blocked
    When an agent with empty agent_id "" calls prey8_perceive
    Then the response status is "GATE_BLOCKED"
    And the response contains "agent_id is required"

  # ═══════════════════════════════════════════════════════
  #  A2: PORT-PAIR AUTHORIZATION — Least privilege
  # ═══════════════════════════════════════════════════════

  Scenario Outline: Agent can only use gates matching their port assignment
    Given agent "<agent_id>" is registered with allowed_gates <gates>
    When agent "<agent_id>" attempts to call "<tool>"
    Then the response enforces port-pair authorization

    Examples: Full-loop agents (P4, P5, P7, TTAO)
      | agent_id            | gates                                    | tool            |
      | p4_red_regnant      | PERCEIVE,REACT,EXECUTE,YIELD             | prey8_perceive  |
      | p5_pyre_praetorian  | PERCEIVE,REACT,EXECUTE,YIELD             | prey8_execute   |
      | p7_spider_sovereign | PERCEIVE,REACT,EXECUTE,YIELD             | prey8_yield     |
      | ttao_operator       | PERCEIVE,REACT,EXECUTE,YIELD             | prey8_react     |

    Examples: Restricted agents (port-specific)
      | agent_id            | gates                                    | tool            |
      | p0_lidless_legion   | PERCEIVE                                 | prey8_react     |
      | p2_mirror_magus     | EXECUTE                                  | prey8_perceive  |
      | p3_harmonic_hydra   | YIELD                                    | prey8_perceive  |

  Scenario: Watchdog daemon has zero gated access
    Given agent "watchdog_daemon" has allowed_gates []
    When agent "watchdog_daemon" calls prey8_perceive
    Then the response status is "GATE_BLOCKED"
    And the response contains "not authorized"

  # ═══════════════════════════════════════════════════════
  #  A3: SESSION ISOLATION — No cross-contamination
  # ═══════════════════════════════════════════════════════

  Scenario: Two agents have independent sessions
    Given agent "p4_red_regnant" has an active session with nonce "ABC123"
    And agent "ttao_operator" has an active session with nonce "DEF456"
    Then the sessions have different session_ids
    And agent "p4_red_regnant" cannot see agent "ttao_operator" session data

  Scenario: Per-agent session state files are isolated
    Given agent "p4_red_regnant" completes a perceive
    Then a session file ".prey8_session_p4_red_regnant.json" exists
    And no session file ".prey8_session_ttao_operator.json" is created
    And the session file contains "p4_red_regnant" as agent_id

  # ═══════════════════════════════════════════════════════
  #  A4: AGENT IDENTITY IN CLOUDEVENTS — Traceability
  # ═══════════════════════════════════════════════════════

  Scenario: All PREY8 CloudEvents contain agent_id
    When agent "p4_red_regnant" completes a full PREY8 loop
    Then every stigmergy event in the chain contains agent_id "p4_red_regnant"
    And the CloudEvent source includes "v4.0"
    And the CloudEvent envelope contains agent_id field

  Scenario: Agent_id is embedded in hash chain
    When agent "p4_red_regnant" completes perceive and react
    Then the chain_hash incorporates the agent_id
    And tampering with agent_id would invalidate the chain

  # ═══════════════════════════════════════════════════════
  #  A5: WATCHDOG ANOMALY DETECTION — Reward hacking defs
  # ═══════════════════════════════════════════════════════

  Scenario: Watchdog detects gate-block storm (A1)
    Given 6 gate_blocked events from agent "rogue_tester" in 5 minutes
    When the watchdog runs a scan
    Then an A1_GATE_BLOCK_STORM finding is emitted
    And the severity is "WARNING" or "CRITICAL"

  Scenario: Watchdog detects tamper cluster (A2)
    Given 3 tamper_alert events in 10 minutes
    When the watchdog runs a scan
    Then an A2_TAMPER_CLUSTER finding is emitted
    And the severity is "CRITICAL"

  Scenario: Watchdog detects session pollution (A4)
    Given session "abc123" has events from agents "p4_red_regnant" and "p0_lidless_legion"
    When the watchdog runs a scan
    Then an A4_SESSION_POLLUTION finding is emitted
    And the severity is "CRITICAL"
    And the finding contains both agent names

  Scenario: Watchdog detects agent impersonation (A7)
    Given events from unregistered agent_id "evil_agent"
    When the watchdog runs a scan
    Then an A7_AGENT_IMPERSONATION finding is emitted
    And the severity is "CRITICAL"

  # ═══════════════════════════════════════════════════════
  #  A6: AGENT_REGISTRY STRUCTURE — Correct by design
  # ═══════════════════════════════════════════════════════

  Scenario: AGENT_REGISTRY contains all 8 legendary commanders
    Then the registry contains agents:
      | agent_id              | display_name       | role       |
      | p0_lidless_legion     | Lidless Legion     | commander  |
      | p1_web_weaver         | Web Weaver         | commander  |
      | p2_mirror_magus       | Mirror Magus       | commander  |
      | p3_harmonic_hydra     | Harmonic Hydra     | commander  |
      | p4_red_regnant        | Red Regnant        | commander  |
      | p5_pyre_praetorian    | Pyre Praetorian    | commander  |
      | p6_kraken_keeper      | Kraken Keeper      | commander  |
      | p7_spider_sovereign   | Spider Sovereign   | commander  |

  Scenario: AGENT_REGISTRY contains swarm agents with minimal permissions
    Then the registry contains agents:
      | agent_id        | role   | max_gates |
      | swarm_triage    | swarm  | 2         |
      | swarm_research  | swarm  | 2         |
      | swarm_coder     | swarm  | 2         |
      | swarm_analyst   | swarm  | 2         |

  Scenario: Utility tools accept optional agent_id for swarm overview
    When prey8_session_status is called with no agent_id
    Then the response mode is "swarm_overview"
    And the response lists all active sessions across agents
    When prey8_session_status is called with agent_id "p4_red_regnant"
    Then the response contains agent-specific session details
