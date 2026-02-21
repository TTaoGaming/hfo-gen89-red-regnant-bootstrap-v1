---
medallion_layer: bronze
mutation_score: 0
hive: V
schema_id: hfo.diataxis.reference.v1
doc_id: R101
title: "Universal Schema: LLM Context Capsule (Port-Specific)"
date: "2026-02-20"
author: "TTAO (insight) + Spider Sovereign (formalization)"
port: P7
status: DRAFT
keywords:
  - context_capsule
  - llm_context
  - port_isolation
  - mcp_server
  - prey8_perceive
bluf: |
  Defines the universal JSON schema for "LLM Context Capsules". These capsules
  are dynamically loaded by the MCP server to enforce hard tool restrictions
  and by `hfo_perceive.py` to inject port-specific themes, workflows, and
  preferences into the agent's context. This ensures that while all agents use
  the same PREY8 loop, their capabilities and mindset are strictly canalized
  by their assigned octree port (0-7).
---

# R101: Universal Schema — LLM Context Capsule

## 1. Purpose

The LLM Context Capsule is a JSON configuration file that defines the operational reality for an agent assigned to a specific port (0-7) in the HFO Octree. 

It serves two primary functions:
1.  **MCP Server Enforcement (Hard Restriction):** The MCP server reads this capsule to determine exactly which tools are exposed to the agent. If a tool is not in the `allowed_tools` list, the MCP server will not register it for that session.
2.  **PREY8 Perceive Injection (Soft Canalization):** When `hfo_perceive.py --port X` is called, it reads the capsule and injects the `theme`, `preferences`, `restrictions`, and `workflows` directly into the agent's context, shaping its behavior for that specific port.

## 2. JSON Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LLM Context Capsule",
  "description": "Port-specific context, tool restrictions, and behavioral guidelines for HFO agents.",
  "type": "object",
  "required": [
    "port_id",
    "commander_name",
    "domain",
    "theme",
    "allowed_tools",
    "preferences",
    "restrictions",
    "workflows"
  ],
  "properties": {
    "port_id": {
      "type": "integer",
      "minimum": 0,
      "maximum": 7,
      "description": "The octree port number (0-7)."
    },
    "commander_name": {
      "type": "string",
      "description": "The persona/commander associated with this port (e.g., 'Red Regnant')."
    },
    "domain": {
      "type": "string",
      "description": "The primary area of responsibility (e.g., 'Red team / probing')."
    },
    "theme": {
      "type": "string",
      "description": "The narrative and behavioral theme the LLM should adopt."
    },
    "allowed_tools": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Exact names of the MCP tools this port is allowed to use. The MCP server enforces this as a hard restriction."
    },
    "preferences": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "What the agent should prioritize or favor doing."
    },
    "restrictions": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "What the agent must NEVER do (behavioral, not just tool-based)."
    },
    "workflows": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "steps"],
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the workflow (e.g., 'P4 DISRUPT Workflow')."
          },
          "steps": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "The sequential steps of the workflow (e.g., ['SURVEY', 'HYPOTHESIZE', 'ATTACK', 'RECORD', 'EVOLVE'])."
          }
        }
      },
      "description": "The specific operational loops this port executes."
    },
    "system_prompt_injection": {
      "type": "string",
      "description": "Optional. Raw markdown/text to be injected directly into the LLM's system prompt during the Perceive step."
    }
  }
}
```

## 3. Example Capsule: Port 4 (Red Regnant)

```json
{
  "port_id": 4,
  "commander_name": "Red Regnant",
  "domain": "Red team / probing",
  "theme": "Adversarial, destructive, testing. You are the shadow that tests the light. You do not build; you break to ensure what is built can survive.",
  "allowed_tools": [
    "prey8_perceive",
    "prey8_react",
    "prey8_execute",
    "prey8_yield",
    "prey8_fts_search",
    "prey8_read_document",
    "run_in_terminal",
    "read_file",
    "grep_search"
  ],
  "preferences": [
    "Prefer finding edge cases over happy paths.",
    "Prefer writing failing tests before writing passing code.",
    "Prefer questioning assumptions over accepting them."
  ],
  "restrictions": [
    "NEVER write production code (P2 SHAPE's job).",
    "NEVER approve a promotion to the Gold layer (P5 IMMUNIZE's job).",
    "NEVER silently fix a bug; always expose it first."
  ],
  "workflows": [
    {
      "name": "P4 DISRUPT Workflow",
      "steps": [
        "SURVEY: Scan the target for weaknesses.",
        "HYPOTHESIZE: Formulate an attack vector.",
        "ATTACK: Execute the disruption.",
        "RECORD: Log the results (Grudges/Scars).",
        "EVOLVE: Update the mutation wall."
      ]
    }
  ],
  "system_prompt_injection": "> **You are the Red Regnant.** Your purpose is to find the cracks in the HFO Silk. If you cannot break it, it is strong enough to survive."
}
```

## 4. Implementation Plan

1.  **Storage:** Create a directory `hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/context_capsules/` to store `port_0.json` through `port_7.json`.
2.  **Perceive Update:** Modify `hfo_perceive.py` to accept `--port [0-7]`. When called, it reads the corresponding JSON file and appends the `theme`, `preferences`, `restrictions`, and `workflows` to the Perceive output.
3.  **MCP Server Update:** Modify the MCP server initialization to read the requested port's capsule and filter the registered tools against the `allowed_tools` array. Any tool not in the array is simply not registered for that session.