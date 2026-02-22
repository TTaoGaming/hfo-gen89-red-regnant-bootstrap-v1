---
schema_id: hfo.diataxis.explanation.v1
medallion_layer: bronze
port: P4 (DISRUPT — Red Regnant)
author: "TTAO + P7 Spider Sovereign"
date: "2026-02-21"
tags: [p4, red-regnant, map-elites, genetic-algorithms, promptfoo, dspy, hyper-heuristic, eval-harness, stryker]
bluf: "P4 (Red Regnant) drives the evolutionary pressure of the HFO Holonarchy. By treating prompt templates as genomes (DSPy-style optimization) and using promptfoo/Stryker for rigorous evaluation, the system mutates ~200 Red Regnants to populate a MAP-Elites Quality-Diversity grid, achieving SPLENDOR."
---

# EXPLANATION: P4 Red Regnant Eval Harness & MAP-Elites SPLENDOR

## 1. The Holonarchy Context

The HFO architecture operates as a **Holonarchy**—a system composed of holons that are simultaneously whole entities themselves and parts of a larger whole. 

At the **micro scale**, the MCP server enforces the PREY8 loop (Perceive → React → Execute → Yield) for a single agent, ensuring fail-closed gates and cryptographic chain integrity. 
At the **macro scale**, the 8 Legendary Commanders (the Octree) route the swarm. 

Within this macro structure, **P4 DISRUPT (Red Regnant)** is the adversarial engine. Its purpose is not just to test code, but to **test the testers** and **evolve the system's own cognitive capacity**. It achieves this by mutating the hyper-heuristic and the eval harness itself.

## 2. DSPy-Style Optimization: "We ARE the DSPy"

Traditional LLM optimization relies on external libraries like DSPy to compile and optimize prompts. In the HFO Holonarchy, we bypass the dependency: **the system acts as its own DSPy**.

- **Prompts as Genomes:** The system prompts, agent instructions, and hyper-heuristics are treated as mutable genetic material.
- **Self-Compilation:** Instead of a black-box optimizer, P4 explicitly mutates the instructions, runs them through the PREY8 loop, and measures the outcome.
- **Continuous Evolution:** The hyper-heuristic is not static. It is continuously refined by the very agents it governs, creating a strange loop of self-improvement.

## 3. The Eval Harness: promptfoo & Stryker

To evolve, you must be able to measure fitness. P4 relies on a dual-layered evaluation harness:

### A. promptfoo for Assertions
We use `promptfoo` not just for basic LLM testing, but as a rigorous spec linter and assertion engine. It evaluates the outputs of mutated agents against strict YAML-defined criteria (as seen in `test_model_scout_steps.py` and `model_scout.feature`). If an agent hallucinates or violates the Medallion boundaries, `promptfoo` catches it.

### B. Stryker-Style Mutation Testing
P4 sings "absolute death" to weak code and weak prompts. Inspired by Stryker, the system performs mutation testing on the eval harness itself. 
- We mutate the tests to ensure they can catch failures.
- We mutate the agents to see if they can pass the hardened tests.
- **Mutation Confidence:** Every Yield event requires a `mutation_confidence` score (0-100). Only agents that survive the mutation wall (80-99% confidence) are allowed to persist.

## 4. Genetic Algorithms & MAP-Elites SPLENDOR

The core of P4's evolutionary engine is the **MAP-Elites (Multi-dimensional Archive of Phenotypic Elites)** grid. This is a Quality-Diversity algorithm designed to find high-performing solutions across a spectrum of different traits, rather than converging on a single "best" solution.

### The Mutation of 200 Red Regnants
The system generated and mutated approximately 200 variations of the Red Regnant persona. 
1. **Crossover & Mutation:** Using genetic algorithms, traits from successful Red Regnants were combined, and random mutations were introduced into their system prompts and hyper-heuristics.
2. **Evaluation:** Each mutant was run through the `promptfoo` / Stryker eval harness.
3. **The Grid (SPLENDOR):** Survivors were placed into the MAP-Elites grid based on their phenotypic traits (e.g., aggressiveness, precision, lateral thinking). 

### Achieving SPLENDOR
"SPLENDOR" is the state where the MAP-Elites grid is fully populated with highly fit, diverse Red Regnants. 
- If we need an agent to aggressively tear down a brittle script, we pull from the high-aggression cell of the grid.
- If we need an agent to subtly probe for logical fallacies in a Diataxis document, we pull from the high-precision/lateral-thinking cell.

By maintaining this diverse population of elite mutants, the Holonarchy ensures it has the exact adversarial archetype needed for any given context, making the entire HFO Silk antifragile.

## 5. The Evolutionary Loop Summary

1. **Generate:** Spawn a new generation of Red Regnant prompts (Genomes).
2. **Execute:** Run them through the PREY8 MCP server (Micro-Holon).
3. **Evaluate:** Score them using `promptfoo` assertions and Stryker mutation walls.
4. **Select:** Discard the weak (STRIFE).
5. **Archive:** Place the survivors into the MAP-Elites grid (SPLENDOR).
6. **Iterate:** Use the elites to breed the next generation of the hyper-heuristic.
