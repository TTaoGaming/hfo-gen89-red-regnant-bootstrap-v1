---
schema_id: hfo.mosaic_microkernel_header.v3
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
bluf: "Complete specification of the GestureFSM tile for Omega v13. Covers states, legal transitions, bucket parameters, Schmitt trigger thresholds, coast/timeout behaviour, and P4 vulnerability register. Intended as implementation contract and tuning target."
primary_port: P2
secondary_ports: [P4, P5]
diataxis_type: reference
tags: [bronze, forge:hot, omega, v13, gesture, fsm, state-machine, anti-midas, anti-thrash, leaky-bucket, schmitt, hysteresis, coast, reference]
generated: "2026-02-20"
status: DRAFT — operator review required
related:
  - EXPLANATION_BIOMECHANICAL_GESTURE_HEURISTICS_OMEGA_V13.md
  - HOWTO_TUNE_GESTURE_FSM_THRESHOLDS.md
  - TUTORIAL_BUILD_GESTURE_CURSOR_FROM_SCRATCH.md
  - REFERENCE_OMEGA_GEN10_TOUCH2D_VERTICAL_SLICE_TILE_SPEC_V1 (doc 106)
---

# Reference: GestureFSM — Anti-Midas Touch State Machine

> **One sentence:** GestureFSM is a strictly-typed intent accumulator that converts a noisy per-frame gesture stream into durable, debounced state transitions using three independent defence layers.

---

## State Inventory

| State | Classification | Semantics |
|-------|---------------|-----------|
| `IDLE` | **Latched** | System disarmed. No pointer active. |
| `IDLE_COAST` | **Transient** | Was IDLE; hand signal temporarily lost. |
| `READY` | **Latched** | System armed. Cursor tracking active. No click. |
| `READY_COAST` | **Transient** | Was READY; hand signal temporarily lost. |
| `COMMIT_POINTER` | **Latched** | Active click. `pointerdown` has fired. Cursor still tracking. |
| `COMMIT_COAST` | **Transient** | Was COMMIT_POINTER; hand signal temporarily lost. |

### State Classification Rules

- **Latched:** Requires sustained gesture evidence (bucket overflow) to enter. Does not self-exit.
- **Transient (Coast):** Entered automatically when signal quality drops below `conf_low` or gesture is `'none'`. Self-terminates via `coast_timeout_limit`.

---

## Transition Graph

```
                          ┌──────────────┐
            open_palm     │              │      closed_fist OR
   ┌────────────────────► │    READY     │ ──────────────────────────►┐
   │                      │              │                            │
   │                      └──────┬───────┘                           ▼
IDLE                             │ pointer_up                      IDLE
   ▲                             ▼                                   ▲
   │                      ┌──────────────┐                           │
   │    closed_fist        │   COMMIT     │   closed_fist             │
   └──────────────────── ◄ │   POINTER   │ ─────────────────────────┘
                      ─── │              │ ──► open_palm ──► READY
                           └──────────────┘

ILLEGAL (no path exists):
  IDLE → COMMIT_POINTER directly
```

**Anti-Midas invariant:** `IDLE` has exactly ONE legal latched exit: `READY`. A child jamming their index finger up from a resting fist cannot trigger a click. They must open their hand first.

---

## Defence Layers

### Layer 1 — Schmitt Trigger (Confidence Hysteresis)

Prevents high-frequency threshold bouncing from destabilising bucket counts.

| Parameter | Default | Semantics |
|-----------|---------|-----------|
| `conf_high` | `0.60` | Minimum structural confidence required to process gesture transitions |
| `conf_low` | `0.40` | Below this, all buckets leak and coast is entered |
| Gap (conf_low..conf_high) | `0.20` | Hysteresis band — in-band frames leak buckets but do not accumulate |

**Behaviour:** Once you enter the hysteresis band from above, the system does not immediately coast — it leaks buckets slowly. You must either drop below `conf_low` (coast) or recover above `conf_high` (resume). This prevents short-lived drops from disrupting accumulated intent.

### Layer 2 — Strict State Graph (Legal Transition Enforcement)

Each state defines an explicit allow-list of `(target_state, required_gesture)` pairs. Any gesture not on the allow-list for the current state causes all buckets to leak (`-1`/frame). Any gesture actively opposing a valid exit causes its bucket to leak aggressively (`-2`/frame).

**Example:** While in `READY`, if a `closed_fist` is detected, the `IDLE` bucket fills. If the next frame is `pointer_up`, the `IDLE` bucket leaks aggressively (`-2`) and the `COMMIT_POINTER` bucket fills instead. These are **independent** — they cannot race.

### Layer 3 — Independent Leaky Buckets (Anti-Thrash)

Each legal exit from a state has its own bucket. Buckets are never shared.

| Transition Target | Dwell Limit (frames) | At 30fps (≈) |
|-------------------|---------------------|--------------|
| `READY` | 5 | ~167 ms |
| `COMMIT_POINTER` | 3 | ~100 ms |
| `IDLE` | 4 | ~133 ms |

**Reset on transition:** When a bucket overflows and triggers a transition, ALL buckets are wiped to zero. This prevents accidental rapid-fire transitions immediately after a state change.

---

## Coast Subsystem

### Entry
`forceCoast()` is called when:
- `gesture === 'none'` or `confidence === 0.0`
- `confidence < conf_low`

`forceCoast()` maps each latched state to its coast equivalent:
- `IDLE` → `IDLE_COAST`
- `READY` → `READY_COAST`
- `COMMIT_POINTER` → `COMMIT_COAST`

**⚠ Note:** Calling `forceCoast()` when already in a coast state is a no-op (idempotent). This is correct and intentional.

### Timeout
`coast_ticks` increments each frame when in coast. On `coast_ticks >= coast_timeout_limit` (default: 15 frames ≈ 500ms):
- `forceState('IDLE')` is called unconditionally.
- This resets all buckets.

### `isPinching()` in Coast State

```typescript
isPinching(): boolean {
    return this.state === 'COMMIT_POINTER' || this.state === 'COMMIT_COAST';
}
```

**⚠ P4 Vulnerability — Ghost-Click / Ghost-Draw:** While in `COMMIT_COAST`, `isPinching()` returns `true`. This is intentional for short-duration coasts (e.g., 2–3 frames of hand occlusion — the line should not break). However callers must be aware:

- If the user turns away mid-draw and returns before the 15-frame timeout, `isPinching()` is still `true` at the moment of return.
- The transition OUT of `COMMIT_COAST` when hand signal returns is handled by the Schmitt trigger snaplock: `state = state.replace('_COAST', '')` — returning the FSM to `COMMIT_POINTER`.
- **Caller responsibility:** Pointer event emitters should check whether the cursor position has teleported (velocity gate) before re-emitting `pointermove` from a coast-recovery. This is a P1 bus consumer responsibility, not an FSM responsibility.

### Recovery from Coast
On frame where `confidence >= conf_high` and current state is a coast state:
- State is promoted to its latched equivalent (snaplock): `COMMIT_COAST → COMMIT_POINTER`
- `coast_ticks` is reset to 0
- Bucket evaluation resumes immediately

---

## Full Parameter Registry

| Parameter | Default | Layer | Description |
|-----------|---------|-------|-------------|
| `conf_high` | `0.60` | L1 Schmitt | Enter-high threshold |
| `conf_low` | `0.40` | L1 Schmitt | Exit-low threshold |
| `limits.READY` | `5` | L3 Bucket | Frames to arm system |
| `limits.COMMIT_POINTER` | `3` | L3 Bucket | Frames to fire click |
| `limits.IDLE` | `4` | L3 Bucket | Frames to disarm |
| `coast_timeout_limit` | `15` | Coast | Frames until total-loss → IDLE |

All parameters are tunable. See [HOWTO_TUNE_GESTURE_FSM_THRESHOLDS.md](HOWTO_TUNE_GESTURE_FSM_THRESHOLDS.md) for the tuning procedure.

---

## P4 Known Vulnerability Register

| ID | Vulnerability | Severity | Mitigation |
|----|--------------|----------|------------|
| FSM-V1 | `isPinching()` returns `true` during `COMMIT_COAST` — potential ghost-draw | Medium | Callers must apply velocity teleport gate before re-emitting pointer events on coast recovery |
| FSM-V2 | Two-hand scenarios require TWO separate FSM instances — single instance fed alternating hand data causes inter-hand thrash | High | Instantiate one FSM per `handId`; use wrist-to-wrist distance for hand identity |
| FSM-V3 | `forceCoast()` does not handle transitions from one coast state to another if gestures are re-classified during coast window | Low | Acceptable — coast is a transient pass-through, not a classification target |
| FSM-V4 | `coast_ticks` is not reset when `forceCoast()` is called redundantly in the same coast window | Low | Idempotent on state, tick continues incrementing — correct behaviour |

---

## Public API

```typescript
class GestureFSM {
    // Current state — read-only in consumers
    public state: GestureState;

    // Primary input: call every frame with sensor output
    processFrame(gesture: string, confidence: number, x?: number, y?: number): void;

    // Query whether a pointer action is currently active
    isPinching(): boolean;

    // Force coast (for external signal-loss events, e.g. MediaPipe loses hand entirely)
    forceCoast(): void;
}
```

---

## SBE Invariants (Minimum acceptance gate)

```gherkin
Scenario: Anti-Midas — cannot commit from IDLE
  Given the FSM is in state IDLE
  When 10 frames of high-confidence 'pointer_up' are processed
  Then the FSM state is still IDLE (never COMMIT_POINTER)

Scenario: Must arm before commit
  Given the FSM is in state IDLE
  When 5 frames of 'open_palm' followed by 3 frames of 'pointer_up' are processed
  Then the FSM transitions IDLE → READY → COMMIT_POINTER

Scenario: Anti-thrash — transient open_palm does not break draw
  Given the FSM is in state COMMIT_POINTER
  When 2 frames of high-confidence 'open_palm' are processed
  Then the READY bucket is 2/5 and no transition fires
  And the FSM remains in COMMIT_POINTER

Scenario: Coast timeout
  Given the FSM is in state READY
  When 15 consecutive frames of 'none' gesture are processed
  Then the FSM is in state IDLE
  And isPinching() returns false

Scenario: Ghost-draw guard — coast recovery does not fire duplicate pointerdown
  Given the FSM is in state COMMIT_COAST (was COMMIT_POINTER)
  When 1 frame of high-confidence 'pointer_up' is processed after 5 coast frames
  Then the FSM re-enters COMMIT_POINTER
  And no new pointerdown event is emitted (caller gate responsibility)
```

---

*Generated 2026-02-20 by P4 Red Regnant. Bronze layer — validate before promotion.*
