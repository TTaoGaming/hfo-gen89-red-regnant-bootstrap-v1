---
medallion_layer: bronze
mutation_score: 0
hive: V
type: explanation
title: "Explanation: Obsidian Hourglass Fractal Workflow"
bluf: "The Obsidian Hourglass is a fractal planning primitive (scatter-gather diamond) that repeats across 11 timescales, each mapping to a Donella Meadows leverage point."
---

# Explanation: Obsidian Hourglass Fractal Workflow

## The Core Concept

The Obsidian Hourglass is HFO's planning primitive: a scatter-gather diamond (e.g., 3-2-1-2-3). This pattern is **fractal**, repeating at 11 different timescales, from 10 minutes to infinity.

Each timescale maps to a specific **Donella Meadows leverage point** and an **H-POMDP state partition**. The core insight is that short timescales can only move low-leverage parameters, while long timescales can shift paradigms. The hourglass shape ensures convergence to a single commit at the waist, regardless of scale.

## The Fractal Timescale Ladder

| Scale | Duration | Meadows # | Leverage Name | HFO Variant | What You Can Change |
|-------|----------|-----------|---------------|-------------|---------------------|
| **T0** | 10 min | #12 | Parameters | Pebble Flip (1-1-1) | Fix a bug, tweak a value |
| **T1** | 1 hour | #11–#10 | Buffers & Stocks | Scoutglass (2-1-2) | Design a component, run tests |
| **T2** | 1 workday | #9–#8 | Delays & Feedback | Hourglass (3-2-1-2-3) | Ship a feature, pass gates |
| **T3** | 1 week | #7–#6 | Positive Feedback & Info Flows | Stormglass (3-2-3) | Sprint goal, architecture refactor |
| **T4** | 1 month | #5 | Rules of the System | Starglass (5-3-1-3-5) | Milestone, pivot decision, new rules |
| **T5** | 1 quarter | #4 | Self-Organization | Nested Hourglass ×3 | Roadmap, re-org, new capabilities |
| **T6** | 1 year | #3 | System Goals | Nested Hourglass ×12 | Vision revision, north star waypoint |
| **T7** | 10 years | #2 | Paradigm | Campaign Hourglass | Career pivot, paradigm shift |
| **T8** | 100 years | #1 | Transcend Paradigm | Legacy Hourglass | Institution, legacy, lineage |
| **T9** | 1,000 years | #0 | Civilizational Memory | Species Hourglass | Culture, knowledge persistence |
| **T∞** | → ∞ | Beyond | Omega Point | Eternal Hourglass | Total Tool Virtualization complete |

## The Master SCXML State Machine

The top-level state machine allows you to enter at any timescale, run that scale's hourglass, and zoom in or out as needed.

- **Scatter:** Explore options, read context, identify approaches.
- **Waist (Commit):** Make the single smallest change, pick the best approach, commit to a path.
- **Gather:** Verify the change, execute the approach, validate, and emit a receipt (stigmergy signal).

Any Scatter or Gather node can itself contain a full hourglass at a smaller timescale (T(n-1)), demonstrating the fractal nature of the workflow.
