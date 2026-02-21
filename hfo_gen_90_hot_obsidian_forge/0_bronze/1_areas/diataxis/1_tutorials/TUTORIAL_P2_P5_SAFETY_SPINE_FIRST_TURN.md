---
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.mosaic_microkernel_header.v3
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "Walkthrough tutorial: Create a shape package (P2), gate it (P5), and close the feedback loop — first safety spine turn"
primary_port: P2
secondary_port: P5
role: "P2 SHAPE ↔ P5 IMMUNIZE — the safety spine"
tags: [bronze, forge:hot, para:tutorial, p2, p5, diataxis, safety-spine, grimoire, walkthrough]
generated: "2026-02-11T00:00:00Z"
grimoire_ref: "hfo_hot_obsidian_forge/3_hfo/2_resources/HFO_GRIMOIRE_COMPENDIUM_GEN88_V8_8_2026_01_29.md"
---

# Tutorial: Your First P2–P5 Safety Spine Turn

> **What you'll learn**: How to create a validated shape package as P2, pass it through P5's gating, handle a rejection, and close the feedback loop — all within the 4-beat workflow.

## What You Need

- The HFO workspace set up and healthy (`npm run morning`)
- Familiarity with the Grimoire Quickstart (`blessed.5.p5_grimoire_v8_8_quickstart`)
- SSOT SQLite accessible (`blessed.6.mcp_memory_ssot_sqlite`)

## Overview

This tutorial walks you through one complete cycle of the P2–P5 safety spine:

1. **P2 creates** a digital twin / shape package (with intentional gap)
2. **P5 gates** and rejects (because of missing invariant)
3. **P2 learns** from the rejection and produces a corrected shape
4. **P5 approves** the corrected shape
5. **Both write** SSOT status updates

This demonstrates the **strange loop**: P5's rejection teaches P2, making the system smarter.

---

## Step 1: Set Up Context

First, check system health:

```bash
npm run morning
```

Read the braided mission thread to understand where you are:

```bash
head -30 braided_mission_thread_alpha_omega_hfo_gen88v8.yaml
```

Note the key concepts:
- **P2 (SHAPE)** = Mirror Magus = creation / digital twin / spike factory
- **P5 (IMMUNIZE)** = Pyre Praetorian = blue team / defense-in-depth / recovery
- **Stage 2** = Validated Foresight → Gate
- **Safety spine** = creation gated by immunization

## Step 2: P2 Creates a Shape Package (With Intentional Gap)

Let's create a simple shape package — a normalized model of a configuration change. We'll intentionally omit one invariant to see P5 reject it.

Create the shape package artifact:

```json
{
  "shape_package_v1": {
    "model": {
      "type": "config_change",
      "target": "feature_flags.env",
      "proposed_state": {
        "ENABLE_GESTURE_PIPELINE": true,
        "GESTURE_CONFIDENCE_THRESHOLD": 0.85
      },
      "schema_version": "1.0.0"
    },
    "constraints": [
      "confidence_threshold must be 0.0..1.0",
      "feature_flags.env must exist"
    ],
    "validation_evidence": {
      "schema_check": "pass",
      "range_check": "pass"
    },
    "provenance": {
      "source": "P2:tutorial",
      "trace_id": "tutorial-001",
      "budget_consumed_ms": 50
    }
  }
}
```

**Notice what's missing**: There's no rollback path or previous state. P5 will catch this.

## Step 3: P5 Gates the Shape Package

Now put on your P5 hat. Run through the gate checklist:

| Check | Status |
|-------|--------|
| Trace ID present? | ✅ tutorial-001 |
| Source is blessed P2? | ✅ P2:tutorial |
| Schema matches contract? | ✅ v1.0.0 |
| Constraints present? | ✅ 2 constraints |
| Validation evidence? | ✅ schema + range |
| **Rollback path?** | ❌ **MISSING** |
| **Previous state captured?** | ❌ **MISSING** |

**Verdict: REJECT**

Reason: Missing rollback path and previous state snapshot. Without these, the change is irreversible — violating P5's invariant that "every approval has a reversible path."

The rejection feedback to P2:

```json
{
  "verdict": "reject",
  "missing_invariants": [
    "rollback_path: every config change must include previous state for rollback",
    "previous_state: must capture current values before proposing new ones"
  ],
  "threat_constraint": "Irreversible config changes can break gesture pipeline with no recovery"
}
```

## Step 4: P2 Encodes the Feedback and Produces Corrected Shape

P2 receives the rejection and learns. The **dyad Gherkin** fires:

> Given P5 rejects shape with missing_invariant:rollback_path
> When P2 receives → Then encode rollback_path; next candidate includes rollback_path

Corrected shape package:

```json
{
  "shape_package_v1": {
    "model": {
      "type": "config_change",
      "target": "feature_flags.env",
      "proposed_state": {
        "ENABLE_GESTURE_PIPELINE": true,
        "GESTURE_CONFIDENCE_THRESHOLD": 0.85
      },
      "previous_state": {
        "ENABLE_GESTURE_PIPELINE": false,
        "GESTURE_CONFIDENCE_THRESHOLD": 0.70
      },
      "schema_version": "1.0.0"
    },
    "constraints": [
      "confidence_threshold must be 0.0..1.0",
      "feature_flags.env must exist",
      "previous_state must be captured before mutation",
      "rollback_path must restore previous_state on failure"
    ],
    "validation_evidence": {
      "schema_check": "pass",
      "range_check": "pass",
      "rollback_dry_run": "pass",
      "previous_state_snapshot": "captured"
    },
    "rollback": {
      "method": "restore_previous_state",
      "previous_state_hash": "sha256:abc123...",
      "tested": true
    },
    "provenance": {
      "source": "P2:tutorial",
      "trace_id": "tutorial-002",
      "budget_consumed_ms": 80,
      "iteration": 2,
      "learned_from": "tutorial-001 rejection"
    }
  }
}
```

**What changed**:
- Added `previous_state` to the model
- Added 2 new constraints (previous_state capture + rollback path)
- Added rollback section with tested dry-run
- Provenance shows this is iteration 2, learned from rejection

## Step 5: P5 Re-Gates the Corrected Shape

| Check | Status |
|-------|--------|
| Trace ID present? | ✅ tutorial-002 |
| Source is blessed P2? | ✅ P2:tutorial |
| Schema matches contract? | ✅ v1.0.0 |
| Constraints present? | ✅ 4 constraints (expanded) |
| Validation evidence? | ✅ 4 checks (expanded) |
| Rollback path? | ✅ restore_previous_state, tested |
| Previous state captured? | ✅ with hash |

**Verdict: APPROVE**

The shape is promoted from bronze to silver. P5 returns admissibility constraints for future shapes:

```json
{
  "verdict": "approve",
  "admissibility_constraints": [
    "All config changes must include previous_state + rollback (now permanent invariant)",
    "Rollback must be dry-run tested before promotion"
  ]
}
```

## Step 6: Write SSOT Status Updates

Both ports record the turn:

```bash
# P2 status update
bash scripts/mcp_env_wrap.sh ./.venv/bin/python hfo_ssot_status_update.py \
  --topic "p2_tutorial_shape_turn" \
  --payload-json '{
    "summary": "First safety spine turn: produced 2 shape packages, 1 rejected (missing rollback), 1 approved after encoding constraint",
    "shapes_produced": 2,
    "approved": 1,
    "rejected": 1,
    "lesson": "Always include previous_state and rollback_path in config change shapes",
    "trace_ids": ["tutorial-001", "tutorial-002"]
  }'

# P5 status update
bash scripts/mcp_env_wrap.sh ./.venv/bin/python hfo_ssot_status_update.py \
  --topic "p5_tutorial_gate_turn" \
  --payload-json '{
    "summary": "Gated 2 shape packages from P2 tutorial. Rejected first for missing rollback invariant. Approved second after P2 encoded fix. New permanent invariant added.",
    "gated": 2,
    "approved": 1,
    "rejected": 1,
    "new_invariants": ["config_change_requires_rollback_path"],
    "trace_ids": ["tutorial-001", "tutorial-002"]
  }'
```

## What You've Learned

1. **P2 creates** validated digital twins with models + constraints + evidence + provenance
2. **P5 gates** using fail-closed checks — no bypasses, no exceptions
3. **Rejections teach**: every P5 rejection feeds new constraints back to P2
4. **The strange loop tightens**: P2 gets better, P5 discovers new edge cases, the system improves
5. **SSOT records everything**: both ports write status updates so the next turn starts from truth
