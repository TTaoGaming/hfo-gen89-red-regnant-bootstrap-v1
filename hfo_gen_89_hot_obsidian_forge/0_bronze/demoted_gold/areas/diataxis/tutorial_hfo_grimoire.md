---
schema_id: hfo.gen89.diataxis.tutorial.v1
medallion_layer: gold
title: "Tutorial: Your First PREY8 Session"
type: tutorial
port: P6
bluf: "A step-by-step guide to executing a complete PREY8 session, from Perceive to Yield, navigating the fail-closed gates."
---

# Tutorial: Your First PREY8 Session

Welcome to the Hive Fleet Obsidian (HFO) Gen89 architecture. This tutorial will guide you through your first **PREY8** session. 

PREY8 is a mandatory 4-step cognitive persistence loop. It ensures that no agent session is a dead-end and that all work is recorded in the Single Source of Truth (SSOT) via stigmergy.

## Prerequisites
- You must be operating within the HFO Gen89 workspace.
- You must understand that the system is **fail-closed**. If you miss a required field at any gate, you will be blocked.

## Step 0: Pre-Perceive Research
Before you can even start a session, you must gather context. The `PERCEIVE` gate requires evidence that you have looked at the system state.

1. **Search the SSOT:** Use `prey8_fts_search` to find relevant documents.
2. **Read Documents:** Use `prey8_read_document` to read the documents you found. Note their IDs.
3. **Check Stigmergy:** Use `prey8_query_stigmergy` to see what other agents have done recently.

## Step 1: PERCEIVE (P0 + P6)
Now you open the session. This step pairs **P0 OBSERVE** (sensing) with **P6 ASSIMILATE** (memory).

Call `prey8_perceive` with:
- `probe`: Your intent (e.g., "I want to build a new feature").
- `observations`: What you learned from your FTS search.
- `memory_refs`: The document IDs you read.
- `stigmergy_digest`: A summary of recent events.

*If successful, you will receive a `nonce`. Keep it safe.*

## Step 2: REACT (P1 + P7)
With context gathered, you must form a strategy. This step pairs **P1 BRIDGE** (data fabric) with **P7 NAVIGATE** (steering).

Call `prey8_react` with:
- `perceive_nonce`: The nonce from Step 1.
- `analysis`: Your interpretation of the context.
- `plan`: Your high-level plan.
- `shared_data_refs`: Cross-references you are bridging.
- `navigation_intent`: Your strategic direction.
- `meadows_level`: The leverage level (1-12) of your intervention.
- `meadows_justification`: Why you chose this level.
- `sequential_plan`: Your step-by-step execution plan.

*If successful, you will receive a `react_token`.*

## Step 3: EXECUTE (P2 + P4)
Now you do the work. This step pairs **P2 SHAPE** (creation) with **P4 DISRUPT** (adversarial testing). You can repeat this step multiple times.

Call `prey8_execute` with:
- `react_token`: The token from Step 2.
- `action_summary`: What you are doing in this specific step.
- `sbe_given`, `sbe_when`, `sbe_then`: Your Specification by Example (BDD) contract.
- `artifacts`: Files you are creating or modifying.
- `p4_adversarial_check`: How you challenged your own assumptions.
- `fail_closed_gate`: Must be `true`.

## Step 4: YIELD (P3 + P5)
Finally, you close the loop and deliver your work. This step pairs **P3 INJECT** (delivery) with **P5 IMMUNIZE** (testing).

Call `prey8_yield` with:
- `summary`: What you accomplished overall.
- `delivery_manifest`: What you are injecting into the system.
- `test_evidence`: How you verified your work.
- `mutation_confidence`: A score (0-100) representing your test coverage.
- `immunization_status`: "PASSED", "FAILED", or "PARTIAL".
- `completion_given`, `completion_when`, `completion_then`: Your final SW-4 completion contract.

*Congratulations! You have successfully completed a PREY8 session. Your work is now permanently etched into the SSOT stigmergy trail.*