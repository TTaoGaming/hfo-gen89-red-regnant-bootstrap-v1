# Omega v13: Temporal Tuning Registry & Procedural ADRs

## 1. The Concept: Lifelong Tuning Rollups

A spatial OS that grows with a child cannot just tune itself moment-by-moment. It needs to track how the user's "wood grain" (their unique MAP-Elites tuning profile) evolves over time. 

To achieve this, we implement a **Temporal Tuning Registry**. This system takes high-frequency snapshots of the user's tuning profile and aggregates them into progressively larger time buckets:
* Minute-by-Minute
* Hourly
* Daily
* Weekly
* Monthly
* Yearly
* Decade

## 2. Procedural Architecture Decision Records (ADRs)

As the system rolls up these snapshots, it procedurally generates **ADR notes**. These notes act as a historical log of *how* and *why* the user's spatial OS changed.

Instead of a human engineer writing an ADR, the system writes it for the user.

### Example Procedural ADRs:
* **Daily Rollup:** "User movement became more dynamic/erratic. Increased process noise (Q) by 0.06 to adapt."
* **Weekly Rollup:** "User established a strong rhythmic pattern in Axis 1 (Frequency). Shifted hyper-heuristic weights to prioritize frequency tracking."
* **Yearly Rollup:** "User's spatial volume (Axis 3) expanded by 15%, indicating physical growth. Adjusted Havok restitution bounds."

## 3. The Implementation (`temporal_rollup.ts`)

The `TemporalTuningRegistry` class manages this process:
1. **`addSnapshot(profile)`**: Captures the current state of the `BehavioralPredictiveLayer`.
2. **`performRollup(interval, start, end)`**: Averages the snapshots within the time window to create a representative `TemporalRollup`.
3. **`generateProceduralADR(prev, current)`**: Compares the new rollup to the previous one and generates a human-readable summary of the delta.

## 4. Privacy and Exportability

Just like the base `UserTuningProfile`, these temporal rollups and ADRs contain **zero raw data**. They only contain the mathematical deltas and the procedural summaries. 

This entire registry can be exported as a single JSON manifest, allowing a user to take their entire "tuning history" with them to a new device, preserving not just their current state, but the entire trajectory of their growth.
