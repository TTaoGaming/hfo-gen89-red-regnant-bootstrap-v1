---
schema_id: hfo.gen89.diataxis.howto.v1
medallion_layer: gold
title: "How-To: Translate a D&D Spell into HFO Code"
type: how_to
port: P2
bluf: "A practical guide to using the 8-stage Translation Pipeline to convert a D&D spell concept into correct-by-construction, adversarially-tested code."
---

# How-To: Translate a D&D Spell into HFO Code

In the HFO architecture, D&D spells are the **source language**, and running, tested code is the **target language**. Everything in between is compilation. 

This guide shows you how to move a concept through the 8-stage Translation Pipeline.

## The 8-Stage Pipeline

### Design-Time (Stages 1-4)
These stages can be completed in a document. They define the *what* and the *why*.

1. **Stage 1: D&D Spell (The Narrative Source)**
   *Action:* Select a real D&D 3.5e spell that matches the capability you need.
   *Example:* `TRUE SEEING` (Divination 6th) - "See things as they REALLY are."

2. **Stage 2: Plain Language (The Translation)**
   *Action:* Strip away the fantasy jargon. Describe what the tool actually does in plain English.
   *Example:* A health-check tool that verifies the system isn't lying to itself.

3. **Stage 3: Capacity Archetype (The Engineering Capability)**
   *Action:* Define the core engineering function.
   *Example:* **Ground Truth Validator.** The capacity to distinguish real system state from reported system state.

4. **Stage 4: Meadows Leverage (The Systemic Intervention)**
   *Action:* Assign a Meadows Leverage Level (L1-L12) and justify it.
   *Example:* **L6 — Information Flows.** It changes what information the operator sees, which drives all downstream decisions.

### Build-Time (Stages 5-8)
These stages require actual code and execution. They define the *how*.

5. **Stage 5: Gherkin (Behavioral Specs)**
   *Action:* Write Given/When/Then scenarios that define the expected behavior.
   *Example:* 
   ```gherkin
   Given a blessed pointer "ssot.db"
   When the target file is moved
   Then TRUE SEEING reports "VEIL PIERCED"
   ```

6. **Stage 6: SBE / ATDD (Acceptance Tests)**
   *Action:* Convert the Gherkin into executable tests (e.g., using `pytest-bdd`). Do not write implementation code yet.

7. **Stage 7: Code (Correct-by-Construction Implementation)**
   *Action:* Write the actual code to make the tests pass. Follow the Red-Green-Refactor cycle.

8. **Stage 8: P4 Test Suite (Adversarial Validation)**
   *Action:* The Red Regnant writes adversarial tests beyond the happy path. Inject faults (mutation testing) and ensure the system survives the "Song of Strife". What survives becomes "Splendor".

## Summary
By following this pipeline, you ensure that every piece of code in HFO is deeply rooted in a clear conceptual archetype, operates at a known leverage point, and is rigorously tested against adversarial conditions.