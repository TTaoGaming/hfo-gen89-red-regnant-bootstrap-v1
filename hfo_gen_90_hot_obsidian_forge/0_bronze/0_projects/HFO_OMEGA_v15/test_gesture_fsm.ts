/**
 * test_gesture_fsm.ts
 *
 * Behavioral tests for GestureFSM.
 * All timestamps are injected via the `nowMs` parameter — no performance.now() calls.
 * Tests cover behavioral contracts, NOT threshold numeric literals.
 * Natural survivor pool (goldilocks): numeric boundaries in conf_high/conf_low,
 * exact NaN-guard first-frame delta, and Math.max(0) floor edges.
 *
 * HFO v15 | Gen90 | SCXML truth → TS is aligned (ms-based dwell as of Feb 2026).
 */

import { GestureFSM } from './gesture_fsm';
import { asRaw } from './types';

// ─── Test Driver ─────────────────────────────────────────────────────────────
/**
 * Wraps GestureFSM and manages a fake wall-clock so all tests are deterministic.
 * First tick always has deltaMs = 0 (matches the NaN-guard in processFrame).
 */
class FsmDriver {
    public readonly fsm: GestureFSM;
    private t = 0;

    constructor(fsm?: GestureFSM) {
        this.fsm = fsm ?? new GestureFSM();
    }

    /** Single tick. Advances time by deltaMs. Returns new state type. */
    tick(gesture: string, confidence: number, deltaMs = 20): string {
        this.t += deltaMs;
        this.fsm.processFrame(gesture, confidence, asRaw(-1), asRaw(-1), this.t);
        return this.fsm.state.type;
    }

    /** N identical ticks. Returns final state type. */
    tickN(gesture: string, confidence: number, n: number, deltaMs = 20): string {
        for (let i = 0; i < n; i++) this.tick(gesture, confidence, deltaMs);
        return this.fsm.state.type;
    }

    /** Advance time by ms without a gesture tick (simulates coast timer). */
    advanceTime(ms: number): void {
        this.t += ms;
    }

    /**
     * Drive IDLE → READY using the standard open_palm path.
     * 6 ticks × 20ms: first tick delta=0 (NaN guard), then 5 × 20ms = 100ms ≥ limit.
     */
    driveToReady(): void {
        this.tickN('open_palm', 0.8, 6);
    }

    /**
     * Drive IDLE → READY → COMMIT_POINTER.
     */
    driveToCommit(): void {
        this.driveToReady();
        this.tickN('pointer_up', 0.8, 5); // 5 × 20ms = 100ms ≥ limit (NaN guard already spent)
    }
}

// ─── Initial state ────────────────────────────────────────────────────────────

describe('GestureFSM — initial state', () => {

    it('Given a new FSM, Then state is IDLE', () => {
        const fsm = new GestureFSM();
        expect(fsm.state.type).toBe('IDLE');
    });

    it('Given a new FSM, Then isPinching() is false', () => {
        const fsm = new GestureFSM();
        expect(fsm.isPinching()).toBe(false);
    });

    it('Given a new FSM, Then isCoasting() is false', () => {
        const fsm = new GestureFSM();
        expect(fsm.isCoasting()).toBe(false);
    });

});

// ─── IDLE → IDLE_COAST (Schmitt trigger low) ─────────────────────────────────

describe('GestureFSM — IDLE Schmitt trigger (low)', () => {

    it('Given IDLE, When confidence drops below low threshold, Then state becomes IDLE_COAST', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.3); // below conf_low
        expect(d.fsm.state.type).toBe('IDLE_COAST');
    });

    it('Given IDLE with medium confidence, Then state stays IDLE (not low enough to coast)', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.55); // above conf_low
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given IDLE_COAST, When confidence recovers above high threshold, Then snaps back to IDLE', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.3); // → IDLE_COAST
        d.tick('open_palm', 0.9); // confidence high → IDLE
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given IDLE_COAST, When coast timeout elapsed, Then state resets to IDLE', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.3); // → IDLE_COAST
        // 25 ticks × 20ms: final tick brings coast_elapsed to 500ms = limit → IDLE.
        // Stopping here avoids the 26th tick re-entering coast with low confidence.
        for (let i = 0; i < 25; i++) d.tick('none', 0.1, 20); // 25 × 20ms = 500ms = limit
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given IDLE_COAST, When below coast timeout, Then stays in IDLE_COAST with low confidence', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.3); // → IDLE_COAST
        d.tick('none', 0.1, 20); // 20ms elapsed, < 500ms timeout
        expect(d.fsm.state.type).toBe('IDLE_COAST');
    });

});

// ─── IDLE leaky bucket → READY ────────────────────────────────────────────────

describe('GestureFSM — IDLE leaky bucket (open_palm → READY)', () => {

    it('Given open_palm with high confidence for full dwell, Then transitions to READY', () => {
        const d = new FsmDriver();
        d.driveToReady();
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given open_palm dwell not yet full, Then stays in IDLE', () => {
        const d = new FsmDriver();
        d.tickN('open_palm', 0.8, 3); // 3 ticks = 40ms < 100ms limit
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given closed_fist in IDLE with high confidence, Then dwell resets (cannot reach READY in same burst)', () => {
        const d = new FsmDriver();
        // Partially fill the bucket
        d.tickN('open_palm', 0.8, 3); // 40ms accumulated
        // Fist resets accumulator
        d.tick('closed_fist', 0.8);
        // Now we need a full new burst
        d.tickN('open_palm', 0.8, 3); // only 40ms again — won't reach limit
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given medium confidence (conf_low to conf_high), Then bucket drains (2:1 ratio prevents easy advance)', () => {
        const d = new FsmDriver();
        // Partially fill
        d.tickN('open_palm', 0.8, 3); // 40ms in bucket
        // Now drain with medium confidence
        d.tickN('open_palm', 0.52, 3); // each tick drains 2 × 20ms = 40ms
        // Bucket should be at 0 or very low — cannot reach 100ms
        d.tickN('open_palm', 0.8, 3); // even 40ms more won't reach limit
        expect(d.fsm.state.type).toBe('IDLE'); // still not READY
    });

    it('Given wrong gesture in IDLE, Then bucket drains (2:1 ratio)', () => {
        const d = new FsmDriver();
        d.tickN('open_palm', 0.8, 3); // 40ms
        d.tickN('pointing_up', 0.8, 3); // drains 2× — bucket goes negative → clipped to 0
        d.tickN('open_palm', 0.8, 3); // 40ms fresh — not enough for 100ms
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given transition to READY, Then dwell accumulator resets in new READY state', () => {
        const d = new FsmDriver();
        d.driveToReady();
        // If accumulator carried over, a single pointer_up tick could push immediately to COMMIT
        // We verify that does NOT happen — need full 100ms in READY
        d.tickN('pointer_up', 0.8, 3); // only 60ms, not enough
        expect(d.fsm.state.type).toBe('READY'); // not yet COMMIT
    });

});

// ─── READY → READY_COAST (Schmitt trigger low) ────────────────────────────────

describe('GestureFSM — READY Schmitt trigger (low)', () => {

    it('Given READY, When confidence drops below low threshold, Then state becomes READY_COAST', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2); // below conf_low → READY_COAST
        expect(d.fsm.state.type).toBe('READY_COAST');
    });

    it('Given READY_COAST, When confidence recovers above high threshold, Then snaps back to READY', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2); // → READY_COAST
        d.tick('open_palm', 0.9); // snaplock → READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given READY_COAST, When medium confidence, Then stays in READY_COAST (below high threshold)', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2); // → READY_COAST
        d.tick('open_palm', 0.55); // medium — not enough for snaplock
        expect(d.fsm.state.type).toBe('READY_COAST');
    });

    it('Given READY_COAST timeout elapsed, Then resets to IDLE', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2); // → READY_COAST
        // 25 ticks × 20ms = 500ms = limit; 26th would re-enter coast with low confidence.
        for (let i = 0; i < 25; i++) d.tick('none', 0.1, 20);
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given READY, When closed_fist with high confidence, Then returns directly to IDLE', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('closed_fist', 0.8);
        expect(d.fsm.state.type).toBe('IDLE');
    });

});

// ─── READY → COMMIT_POINTER (leaky bucket for pointer_up) ─────────────────────

describe('GestureFSM — READY leaky bucket (pointer_up → COMMIT_POINTER)', () => {

    it('Given READY, When pointer_up with high confidence for full dwell, Then transitions to COMMIT_POINTER', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given READY, When pointer_up dwell not yet full, Then stays in READY', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tickN('pointer_up', 0.8, 3); // 3 × 20ms = 60ms < 100ms
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given COMMIT_POINTER, Then isPinching() returns true', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        expect(d.fsm.isPinching()).toBe(true);
    });

    it('Given COMMIT_POINTER, Then isCoasting() returns false', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        expect(d.fsm.isCoasting()).toBe(false);
    });

});

// ─── COMMIT_POINTER → COMMIT_COAST (Schmitt trigger low) ─────────────────────

describe('GestureFSM — COMMIT Schmitt trigger (low)', () => {

    it('Given COMMIT_POINTER, When confidence drops below low threshold, Then state becomes COMMIT_COAST', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2); // below conf_low
        expect(d.fsm.state.type).toBe('COMMIT_COAST');
    });

    it('Given COMMIT_COAST, Then isPinching() returns true (still considered active)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2); // → COMMIT_COAST
        expect(d.fsm.isPinching()).toBe(true);
    });

    it('Given COMMIT_COAST, Then isCoasting() returns true', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2); // → COMMIT_COAST
        expect(d.fsm.isCoasting()).toBe(true);
    });

    it('Given COMMIT_COAST, When confidence recovers above high threshold, Then snaps back to COMMIT_POINTER', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2); // → COMMIT_COAST
        d.tick('pointer_up', 0.9); // snaplock → COMMIT_POINTER
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given COMMIT_COAST timeout elapsed, Then resets to IDLE', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2); // → COMMIT_COAST
        // 25 ticks × 20ms = 500ms = limit; 26th would re-enter coast with low confidence.
        for (let i = 0; i < 25; i++) d.tick('none', 0.1, 20);
        expect(d.fsm.state.type).toBe('IDLE');
    });

});

// ─── COMMIT_POINTER release: palm-vs-fist bifurcation ─────────────────────────
// Key architectural contract: open_palm release → READY, closed_fist release → IDLE

describe('GestureFSM — COMMIT release (palm-vs-fist)', () => {

    it('Given COMMIT_POINTER, When open_palm held for full dwell, Then releases to READY', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('open_palm', 0.8, 5); // 100ms → releases, open_palm wins → READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given COMMIT_POINTER, When closed_fist held for full dwell, Then releases to IDLE', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('closed_fist', 0.8, 5); // 100ms → releases, closed_fist wins → IDLE
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given COMMIT releasing to READY, Then dwell accumulator resets (cannot chain-commit immediately)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('open_palm', 0.8, 5); // → READY
        // pointer_up needs full new dwell from READY
        d.tickN('pointer_up', 0.8, 3); // 60ms < 100ms
        expect(d.fsm.state.type).toBe('READY'); // not COMMIT again yet
    });

    it('Given COMMIT releasing to IDLE, Then a fresh open_palm burst can re-enter READY', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('closed_fist', 0.8, 5); // → IDLE
        d.tickN('open_palm', 0.8, 6); // fresh 100ms → READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given COMMIT with mixed gestures (palm outlasts fist), Then releases to READY', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        // Substrate uses mutual inhibition: holding one gesture for full dwell_ms fires it.
        // Brief fist (2 ticks = 40ms) builds the fist bucket, then palm takes over.
        // When palm becomes hot it zeroes the fist bucket (inhibits commit_to_idle).
        // Palm then holds for 5 consecutive ticks (1st delta=20ms = 20; ×5 = 100ms).
        d.tickN('closed_fist', 0.8, 2);  // fist builds 40ms — then palm resets it
        d.tickN('open_palm',   0.8, 5);  // palm holds 100ms uninterrupted → READY
        expect(d.fsm.state.type).toBe('READY'); // palm held full dwell, fist bucket was zero (inhibited)
    });

});

// ─── isCoasting() across all COAST states ────────────────────────────────────

describe('GestureFSM — isCoasting() across all coast states', () => {

    it('Given IDLE_COAST, Then isCoasting() is true', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.2);
        expect(d.fsm.isCoasting()).toBe(true);
    });

    it('Given READY_COAST, Then isCoasting() is true', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2);
        expect(d.fsm.isCoasting()).toBe(true);
    });

    it('Given COMMIT_COAST, Then isCoasting() is true', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2);
        expect(d.fsm.isCoasting()).toBe(true);
    });

    it('Given READY (not coasting), Then isCoasting() is false', () => {
        const d = new FsmDriver();
        d.driveToReady();
        expect(d.fsm.isCoasting()).toBe(false);
    });

    it('Given COMMIT_POINTER (active commit, no coast), Then isCoasting() is false', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        expect(d.fsm.isCoasting()).toBe(false);
    });

});

// ─── forceCoast() ─────────────────────────────────────────────────────────────

describe('GestureFSM — forceCoast()', () => {

    it('Given IDLE, When forceCoast() called, Then state becomes IDLE_COAST', () => {
        const fsm = new GestureFSM();
        fsm.forceCoast();
        expect(fsm.state.type).toBe('IDLE_COAST');
    });

    it('Given READY, When forceCoast() called, Then state becomes READY_COAST', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.fsm.forceCoast();
        expect(d.fsm.state.type).toBe('READY_COAST');
    });

    it('Given COMMIT_POINTER, When forceCoast() called, Then state becomes COMMIT_COAST', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.fsm.forceCoast();
        expect(d.fsm.state.type).toBe('COMMIT_COAST');
    });

    it('Given IDLE_COAST, When forceCoast() called, Then state remains IDLE_COAST (no double-coast)', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.2); // → IDLE_COAST
        d.fsm.forceCoast();
        expect(d.fsm.state.type).toBe('IDLE_COAST');
    });

});

// ─── configure() hot-swap ─────────────────────────────────────────────────────

describe('GestureFSM — configure() hot-swap', () => {

    it('Given dwellReadyMs reduced to 20ms, When open_palm for 2 ticks (40ms), Then reaches READY faster', () => {
        const d = new FsmDriver();
        d.fsm.configure({ dwellReadyMs: 20 });
        d.tickN('open_palm', 0.8, 2); // tick1 delta=0, tick2 delta=20 → accum=20 ≥ 20 → READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given dwellReadyMs set very high (9999ms), When default burst, Then stays in IDLE', () => {
        const d = new FsmDriver();
        d.fsm.configure({ dwellReadyMs: 9999 });
        d.tickN('open_palm', 0.8, 10); // even 180ms << 9999ms
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given coastTimeoutMs reduced to 100ms, When coast ticks exceed 100ms, Then times out to IDLE faster', () => {
        const d = new FsmDriver();
        d.fsm.configure({ coastTimeoutMs: 100 });
        d.tick('open_palm', 0.2); // → IDLE_COAST
        // 5 ticks × 20ms = 100ms = limit; 6th would re-enter coast with low confidence.
        for (let i = 0; i < 5; i++) d.tick('none', 0.1, 20);
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given configure() called during tracking, When applied, Then takes effect on next frame', () => {
        const d = new FsmDriver();
        d.driveToReady();
        // Change commit dwell to 20ms
        d.fsm.configure({ dwellCommitMs: 20 });
        d.tickN('pointer_up', 0.8, 2); // tick1 delta=20 → accum=20 ≥ 20 → COMMIT
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

});

// ─── COMMIT — bucket internals (direct assertions on public fields) ───────────
// These tests kill Math.max→Math.min, arithmetic (+/÷ vs -/*), and hard-reset
// survivors seen in the Stryker round-1 report.

describe('GestureFSM — COMMIT bucket internals', () => {

    it('Given COMMIT, When open_palm tick, Then ready_bucket accumulates and idle_bucket hard-resets to 0', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('closed_fist', 0.8);                   // idle = 20ms, ready = 0
        expect(d.fsm.idle_bucket_ms).toBe(20);
        expect(d.fsm.ready_bucket_ms).toBe(0);
        d.tick('open_palm', 0.8);                      // hard-reset idle → 0, ready += 20
        expect(d.fsm.idle_bucket_ms).toBe(0);         // hard-reset confirmed
        expect(d.fsm.ready_bucket_ms).toBe(20);
    });

    it('Given COMMIT, When closed_fist tick, Then idle_bucket accumulates and ready_bucket hard-resets to 0', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('open_palm', 0.8);                      // ready = 20ms, idle = 0
        expect(d.fsm.ready_bucket_ms).toBe(20);
        expect(d.fsm.idle_bucket_ms).toBe(0);
        d.tick('closed_fist', 0.8);                   // hard-reset ready → 0, idle += 20
        expect(d.fsm.ready_bucket_ms).toBe(0);        // hard-reset confirmed
        expect(d.fsm.idle_bucket_ms).toBe(20);
    });

    it('Given COMMIT with idle_bucket built, When medium confidence, Then idle_bucket drains and clamps at 0', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('closed_fist', 0.8);                   // idle = 20ms, dwell = 20ms
        // Medium confidence drains 2× per 20ms tick: idle = max(0, 20 - 40) = 0
        d.tick('none', 0.55);                         // medium conf (conf_low ≤ conf < conf_high)
        expect(d.fsm.idle_bucket_ms).toBe(0);         // clamped at 0, not negative
        expect(d.fsm.ready_bucket_ms).toBe(0);
    });

    it('Given COMMIT with ready_bucket built, When medium confidence, Then ready_bucket drains and clamps at 0', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('open_palm', 0.8);                      // ready = 20ms
        d.tick('none', 0.55);                         // drain: ready = max(0, 20 - 40) = 0
        expect(d.fsm.ready_bucket_ms).toBe(0);        // clamped
        expect(d.fsm.idle_bucket_ms).toBe(0);
    });

    it('Given COMMIT with idle_bucket, When double medium-confidence drain, Then bucket stays at 0 (floor holds)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('closed_fist', 0.8);                   // idle = 20ms
        d.tick('none', 0.55);                         // drain → idle = 0
        d.tick('none', 0.55);                         // drain again → still 0 (floor, not negative)
        expect(d.fsm.idle_bucket_ms).toBe(0);
    });

    it('Given COMMIT during non-palm/non-fist gesture at any confidence, Then both buckets and dwell drain', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('open_palm', 0.8);                      // ready = 20ms, dwell = 20ms
        // pointer_up with high confidence falls into drain branch; drains all at 2×
        d.tick('pointer_up', 0.8);                    // ready = max(0,20-40)=0, dwell drains
        expect(d.fsm.ready_bucket_ms).toBe(0);
        expect(d.fsm.idle_bucket_ms).toBe(0);
    });

    it('Given COMMIT, When open_palm slowly accumulates to release threshold, Then releases to READY with correct bucket state', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('open_palm', 0.8, 5);                 // 5 × 20ms = 100ms → triggers READY
        expect(d.fsm.state.type).toBe('READY');
        // After release, buckets reset
        expect(d.fsm.ready_bucket_ms).toBe(0);
        expect(d.fsm.idle_bucket_ms).toBe(0);
    });

    it('Given COMMIT, When closed_fist slowly accumulates to release threshold, Then releases to IDLE with correct bucket state', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('closed_fist', 0.8, 5);              // 100ms → triggers IDLE
        expect(d.fsm.state.type).toBe('IDLE');
        expect(d.fsm.ready_bucket_ms).toBe(0);
        expect(d.fsm.idle_bucket_ms).toBe(0);
    });

});

// ─── IDLE — drain arithmetic (2× rate behavioral proof) ───────────────────────

describe('GestureFSM — IDLE drain arithmetic', () => {

    it('Given IDLE partially filled, When two medium-confidence ticks, Then dwell drains fully to 0', () => {
        const d = new FsmDriver();
        // Build dwell to 40ms: tick1(delta=0 accum=0), tick2(delta=20 accum=20), tick3(delta=20 accum=40)
        d.tickN('open_palm', 0.8, 3);                // accum ≈ 40ms
        // 2 medium ticks: each drains 2×20=40ms → accum = max(0, 40-40) = 0, then max(0,0-40)=0
        d.tick('open_palm', 0.55);
        d.tick('open_palm', 0.55);
        expect(d.fsm.state.type).toBe('IDLE');       // not READY; dwell drained away
    });

    it('Given IDLE after drain, When fresh open_palm burst, Then needs full dwell from zero to reach READY', () => {
        const d = new FsmDriver();
        d.tickN('open_palm', 0.8, 3);                // ~40ms dwell
        d.tickN('open_palm', 0.55, 2);               // drain back to 0
        // From 0: needs 100ms (first tick delta=0, then 5 × 20ms = 100ms → READY on 6th cumulative)
        // After draining, lastFrameMs is set, so first fresh tick has proper delta
        d.tickN('open_palm', 0.8, 5);               // 5 × 20ms = 100ms → READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given IDLE with wrong gesture at high confidence, Then dwell drains (2:1 ratio — non-palm/fist branch)', () => {
        const d = new FsmDriver();
        d.tickN('open_palm', 0.8, 3);                // ~40ms
        // 'pointer_up' at high conf → else-if drain branch (not palm, not fist)
        d.tickN('pointer_up', 0.9, 2);               // drains 2×20=40ms per tick → back to 0
        d.tickN('open_palm', 0.8, 4);                // only 80ms fresh (<100) → not yet READY
        expect(d.fsm.state.type).toBe('IDLE');
        d.tick('open_palm', 0.8);                    // 80+20=100ms → READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given IDLE, When closed_fist at high confidence, Then resets dwell accumulator to 0', () => {
        const d = new FsmDriver();
        d.tickN('open_palm', 0.8, 3);               // ~40ms dwell
        d.tick('closed_fist', 0.8);                 // hard reset: dwell = 0, ready_bucket = 0
        // Now needs a full fresh 100ms burst
        d.tickN('open_palm', 0.8, 5);               // 100ms → READY
        expect(d.fsm.state.type).toBe('READY');
    });

});

// ─── READY — drain arithmetic & coverage ──────────────────────────────────────

describe('GestureFSM — READY drain arithmetic', () => {

    it('Given READY partially filled toward COMMIT, When medium confidence, Then dwell drains back', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tickN('pointer_up', 0.8, 2);              // 40ms toward COMMIT
        d.tick('pointer_up', 0.55);                 // medium conf → drain 40ms → 0
        expect(d.fsm.state.type).toBe('READY');
        // Needs fresh 100ms to reach COMMIT
        d.tickN('pointer_up', 0.8, 4);             // 80ms < 100ms
        expect(d.fsm.state.type).toBe('READY');
        d.tick('pointer_up', 0.8);                 // +20ms → 100ms → COMMIT
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given READY with wrong gesture at high confidence, Then dwell drains (non-pointer_up/fist branch)', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tickN('pointer_up', 0.8, 2);             // 40ms
        d.tickN('open_palm', 0.8, 2);              // open_palm in READY falls into drain (not pointer_up, not fist → 3rd branch)
        // Wait — open_palm in READY: gesture !== 'pointer_up' && gesture !== 'closed_fist' → drain
        expect(d.fsm.state.type).toBe('READY');    // drained, still READY
    });

});

// ─── forceCoast — already-coasting states ─────────────────────────────────────

describe('GestureFSM — forceCoast on already-coasting states', () => {

    it('Given READY_COAST, When forceCoast() called, Then stays READY_COAST (idempotent)', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2);                  // → READY_COAST
        d.fsm.forceCoast();
        expect(d.fsm.state.type).toBe('READY_COAST');
    });

    it('Given COMMIT_COAST, When forceCoast() called, Then stays COMMIT_COAST (idempotent)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2);                 // → COMMIT_COAST
        d.fsm.forceCoast();
        expect(d.fsm.state.type).toBe('COMMIT_COAST');
    });

});

// ─── isPinching + isCoasting combined state ────────────────────────────────────

describe('GestureFSM — isPinching() + isCoasting() combined state', () => {

    it('Given COMMIT_COAST, Then isPinching() && isCoasting() both true (unique COMMIT_COAST signature)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2);                 // → COMMIT_COAST
        expect(d.fsm.isPinching()).toBe(true);
        expect(d.fsm.isCoasting()).toBe(true);
    });

    it('Given IDLE_COAST, Then isPinching() is false but isCoasting() is true', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.2);                  // → IDLE_COAST
        expect(d.fsm.isPinching()).toBe(false);
        expect(d.fsm.isCoasting()).toBe(true);
    });

    it('Given READY_COAST, Then isPinching() is false but isCoasting() is true', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2);                  // → READY_COAST
        expect(d.fsm.isPinching()).toBe(false);
        expect(d.fsm.isCoasting()).toBe(true);
    });

    it('Given COMMIT_POINTER (active), Then isPinching() true and isCoasting() false', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        expect(d.fsm.isPinching()).toBe(true);
        expect(d.fsm.isCoasting()).toBe(false);
    });

});

// ─── configure() isolation — partial calls must NOT overwrite other settings ──

describe('GestureFSM — configure() isolation (partial calls)', () => {

    it('Given configure() with only coastTimeoutMs, Then dwellReadyMs unchanged (drive-to-READY works)', () => {
        const d = new FsmDriver();
        d.fsm.configure({ coastTimeoutMs: 9999 }); // Only coast; dwell unchanged
        d.driveToReady();                           // Uses default 100ms dwell
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given configure() with only coastTimeoutMs, Then dwellCommitMs unchanged (drive-to-COMMIT works)', () => {
        const d = new FsmDriver();
        d.fsm.configure({ coastTimeoutMs: 9999 }); // Only coast; commit dwell unchanged
        d.driveToCommit();
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given configure() with only dwellReadyMs, Then coastTimeoutMs unchanged (default 500ms coast holds)', () => {
        const d = new FsmDriver();
        d.fsm.configure({ dwellReadyMs: 20 }); // Only ready dwell; coast timeout unchanged
        d.tick('open_palm', 0.2);               // → IDLE_COAST
        // 24 ticks × 20ms = 480ms — should still be coasting (default 500ms unchanged)
        for (let i = 0; i < 24; i++) d.tick('none', 0.1, 20);
        expect(d.fsm.state.type).toBe('IDLE_COAST'); // still coasting at 480ms
        d.tick('none', 0.1, 20);                     // 25th tick → 500ms → IDLE
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given configure() with only dwellCommitMs, Then dwellReadyMs unchanged (drive-to-READY still works)', () => {
        const d = new FsmDriver();
        d.fsm.configure({ dwellCommitMs: 40 }); // Only commit dwell; ready dwell unchanged
        d.driveToReady();                        // Default 100ms ready dwell
        expect(d.fsm.state.type).toBe('READY');
    });

});

// ─── Schmitt trigger exact boundary values (kills >= vs >, < vs <=) ────────────

describe('GestureFSM — Schmitt trigger exact boundary values', () => {

    it('Given IDLE, When confidence exactly at conf_low (0.50), Then Schmitt trigger does NOT fire (stays IDLE)', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.50); // 0.50 is NOT < 0.50 → stays IDLE, not IDLE_COAST
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given IDLE, When open_palm at exactly conf_high (0.64), Then dwell accumulates to READY', () => {
        const d = new FsmDriver();
        d.tickN('open_palm', 0.64, 6); // 0.64 >= 0.64 → accumulates dwell → READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given IDLE, When closed_fist at exactly conf_high (0.64), Then dwell resets (cannot reach READY in partial burst)', () => {
        const d = new FsmDriver();
        d.tickN('open_palm', 0.8, 3);   // ~40ms dwell built (ticks 2-3 = 40ms)
        d.tick('closed_fist', 0.64);    // 0.64 >= 0.64 → triggers hard reset
        // After reset: need fresh 100ms burst. Only 3 ticks given → 40ms < 100ms → still IDLE
        d.tickN('open_palm', 0.8, 3);
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given IDLE_COAST, When confidence exactly at conf_high (0.64), Then snaps back to IDLE', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.2);       // → IDLE_COAST
        d.tick('open_palm', 0.64);      // 0.64 >= 0.64 → snaplock to IDLE
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given IDLE_COAST, When confidence just below conf_high (0.63), Then stays in IDLE_COAST', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.2);       // → IDLE_COAST
        d.tick('open_palm', 0.63);      // 0.63 < 0.64 → NOT a snaplock; stays in IDLE_COAST
        expect(d.fsm.state.type).toBe('IDLE_COAST');
    });

    it('Given READY_COAST, When confidence exactly at conf_high (0.64), Then snaps back to READY', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2);       // → READY_COAST
        d.tick('open_palm', 0.64);      // 0.64 >= 0.64 → snaplock to READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given READY_COAST, When confidence just below conf_high (0.63), Then stays in READY_COAST', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.2);       // → READY_COAST
        d.tick('open_palm', 0.63);      // 0.63 < 0.64 → not a snaplock
        expect(d.fsm.state.type).toBe('READY_COAST');
    });

    it('Given COMMIT_COAST, When confidence exactly at conf_high (0.64), Then snaps back to COMMIT_POINTER', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2);      // → COMMIT_COAST
        d.tick('pointer_up', 0.64);     // 0.64 >= 0.64 → snaplock to COMMIT_POINTER
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given COMMIT_COAST, When confidence just below conf_high (0.63), Then stays in COMMIT_COAST', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2);      // → COMMIT_COAST
        d.tick('pointer_up', 0.63);     // 0.63 < 0.64 → not a snaplock
        expect(d.fsm.state.type).toBe('COMMIT_COAST');
    });

});

// ─── IDLE bucket value assertions (kills arithmetic and Math.max survivors) ────

describe('GestureFSM — IDLE bucket value assertions', () => {

    it('Given IDLE, When open_palm with high confidence tick, Then ready_bucket_ms is positive (not zero or negative)', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.8); // tick1: delta=0, ready=0
        d.tick('open_palm', 0.8); // tick2: delta=20, ready += 20 = 20
        expect(d.fsm.ready_bucket_ms).toBeGreaterThan(0);
    });

    it('Given IDLE with ready_bucket at 20ms, When one medium-confidence tick, Then ready_bucket clamps to 0', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.8); // delta=0, ready=0
        d.tick('open_palm', 0.8); // delta=20, ready=20
        d.tick('open_palm', 0.55); // medium drain: max(0, 20 - 2×20) = max(0,-20) = 0
        expect(d.fsm.ready_bucket_ms).toBe(0);  // clamped at 0, not -20
    });

    it('Given IDLE with ready_bucket at 0, When medium-confidence tick, Then ready_bucket stays at 0 (floor holds)', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.8);
        d.tick('open_palm', 0.8); // ready=20
        d.tick('open_palm', 0.55); // drain → 0
        d.tick('open_palm', 0.55); // drain again: max(0, 0-40) = 0 (floor holds)
        expect(d.fsm.ready_bucket_ms).toBe(0);
    });

    it('Given IDLE with ready_bucket at 40ms, When one medium-confidence tick, Then bucket reaches exactly 0 (2× drain rate)', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.8); // delta=0
        d.tick('open_palm', 0.8); // ready=20
        d.tick('open_palm', 0.8); // ready=40
        d.tick('open_palm', 0.55); // 2× drain: max(0, 40 - 2×20) = max(0, 0) = 0
        expect(d.fsm.ready_bucket_ms).toBe(0);
    });

    it('Given IDLE, When wrong-gesture drain, Then ready_bucket clamps to 0 (not negative)', () => {
        const d = new FsmDriver();
        d.tick('open_palm', 0.8);
        d.tick('open_palm', 0.8); // ready=20
        d.tick('pointer_up', 0.8); // wrong gesture drain: max(0, 20-40)=0
        expect(d.fsm.ready_bucket_ms).toBe(0);
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given IDLE dwell drained, Then needs full fresh burst to reach READY', () => {
        const d = new FsmDriver();
        d.tickN('open_palm', 0.8, 4);     // build dwell: tick1=0, tick2=20, tick3=40, tick4=60ms
        d.tick('open_palm', 0.55);        // drain: 60-40=20ms remaining
        d.tick('open_palm', 0.55);        // drain: max(0,20-40)=0
        expect(d.fsm.state.type).toBe('IDLE'); // drained, not READY
        d.tickN('open_palm', 0.8, 5);     // 5 × 20ms = 100ms → READY
        expect(d.fsm.state.type).toBe('READY');
    });

});

// ─── Full round-trip: IDLE → READY → COMMIT → READY → COMMIT → IDLE ──────────

describe('GestureFSM — multi-cycle round-trips', () => {

    it('Given a full IDLE→READY→COMMIT→READY→COMMIT→IDLE cycle, Then FSM ends in IDLE', () => {
        const d = new FsmDriver();
        d.driveToCommit();                  // → COMMIT
        d.tickN('open_palm', 0.8, 5);       // → READY (palm release)
        d.tickN('pointer_up', 0.8, 5);      // → COMMIT (second commit)
        d.tickN('closed_fist', 0.8, 5);     // → IDLE (fist release)
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given coast mid-sequence COMMIT_COAST recovers, Then can still release to READY from COMMIT', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.2);          // → COMMIT_COAST (confidence drop)
        d.tick('pointer_up', 0.9);          // → COMMIT_POINTER (snaplock)
        d.tickN('open_palm', 0.8, 5);       // → READY (palm release)
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given three consecutive commits via palm release, Then each cycle starts fresh', () => {
        const d = new FsmDriver();
        for (let cycle = 0; cycle < 3; cycle++) {
            d.tickN('pointer_up', 0.8, 5);  // → COMMIT
            d.tickN('open_palm', 0.8, 5);   // → READY
        }
        expect(d.fsm.state.type).toBe('READY');
    });

});

// ─── READY state — exact boundary + drain tests ────────────────────────────────

describe('GestureFSM — READY state exact boundary + drain', () => {

    it('Given READY, When confidence exactly at conf_low (0.50), Then Schmitt trigger does NOT fire (stays READY)', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('open_palm', 0.50); // 0.50 is NOT < 0.50 → stays READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given READY, When closed_fist with medium confidence (0.55 < conf_high), Then stays READY (no back-to-IDLE)', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('closed_fist', 0.55); // conf < conf_high → NOT the closed_fist→IDLE branch
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given READY, When closed_fist with exactly conf_high (0.64), Then returns to IDLE', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tick('closed_fist', 0.64); // 0.64 >= 0.64 → triggers IDLE return
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given READY, When pointer_up with medium confidence (0.55), Then dwell drains (not accumulates)', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tickN('pointer_up', 0.8, 3);   // build ~40ms dwell toward COMMIT
        d.tick('pointer_up', 0.55);      // medium conf → drains 40ms, dwell back to 0
        d.tick('pointer_up', 0.55);      // drain: max(0, 0-40)=0 (floor)
        // Dwell drained; now needs fresh 100ms to reach COMMIT
        d.tickN('pointer_up', 0.8, 4);   // 80ms < 100ms → not yet COMMIT
        expect(d.fsm.state.type).toBe('READY');
        d.tick('pointer_up', 0.8);       // +20ms → 100ms → COMMIT
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given READY, When pointer_up at exactly conf_high (0.64), Then dwell accumulates to COMMIT', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tickN('pointer_up', 0.64, 5); // 0.64 >= 0.64 → accumulates 100ms → COMMIT
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given READY with partial dwell, When wrong-gesture drain with 2x rate, Then dwell clears and fresh burst needed', () => {
        const d = new FsmDriver();
        d.driveToReady();
        d.tickN('pointer_up', 0.8, 3);   // ~40ms dwell (ticks 1-3: 0+20+20=40ms effective)
        // open_palm in READY = wrong gesture (pointer_up expected) → drain at 2×
        d.tick('open_palm', 0.8);        // drain: max(0, 40-40)=0
        d.tick('open_palm', 0.8);        // drain: max(0, 0-40)=0 (floor)
        expect(d.fsm.state.type).toBe('READY');
        d.tickN('pointer_up', 0.8, 5);  // fresh 100ms burst → COMMIT
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

});

// ─── COMMIT state — exact boundary + drain tests ──────────────────────────────

describe('GestureFSM — COMMIT state exact boundary + drain', () => {

    it('Given COMMIT_POINTER, When confidence exactly at conf_low (0.50), Then Schmitt trigger does NOT fire', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('pointer_up', 0.50); // NOT < 0.50 → stays COMMIT_POINTER
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given COMMIT, When open_palm with medium confidence (0.55), Then dwell does NOT accumulate toward release', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        // Medium conf: drain branch, not accumulate. 5 ticks should drain (not fill dwell to 100ms)
        d.tickN('open_palm', 0.55, 6);  // 6 ticks of medium conf = drain; dwell stays 0
        expect(d.fsm.state.type).toBe('COMMIT_POINTER'); // not released
    });

    it('Given COMMIT, When open_palm at exactly conf_high (0.64), Then dwell accumulates to release at READY', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('open_palm', 0.64, 5); // 0.64 >= 0.64 → accumulates; 5 × 20ms = 100ms → READY
        expect(d.fsm.state.type).toBe('READY');
    });

    it('Given COMMIT, When closed_fist at exactly conf_high (0.64), Then dwell accumulates to release at IDLE', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('closed_fist', 0.64, 5); // 0.64 >= 0.64 → accumulates; 100ms → IDLE
        expect(d.fsm.state.type).toBe('IDLE');
    });

    it('Given COMMIT with partial dwell built, When medium confidence, Then dwell drains at 2× rate', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tickN('open_palm', 0.8, 3);   // dwell += 3×20ms = 60ms; ready_bucket=60
        d.tick('pointer_up', 0.55);     // medium drain: dwell = max(0, 60-40) = 20ms; buckets drain too
        expect(d.fsm.state.type).toBe('COMMIT_POINTER'); // not released (dwell 20<100ms)
        // One more: dwell = max(0, 20-40) = 0
        d.tick('pointer_up', 0.55);
        expect(d.fsm.state.type).toBe('COMMIT_POINTER'); // still COMMIT (dwell=0 < 100ms)
    });

    it('Given COMMIT, When pointer_up drain (non-palm/fist), Then ready_bucket drains to 0', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.tick('open_palm', 0.8);       // ready_bucket=20ms, dwell=20ms
        d.tick('pointer_up', 0.8);      // pointer_up = non-palm/fist drain: ready=max(0,20-40)=0
        expect(d.fsm.ready_bucket_ms).toBe(0);
        expect(d.fsm.idle_bucket_ms).toBe(0);
    });

});

// ─── Extension points: substrate getter, registerRule, unregisterRule ─────────
// These tests cover the three BlockStatement no-coverage mutants at lines 310-324.

describe('GestureFSM — extension points (substrate / registerRule / unregisterRule)', () => {

    it('substrate getter returns the underlying substrate (not undefined)', () => {
        const d = new FsmDriver();
        const sub = d.fsm.substrate;
        expect(sub).toBeDefined();
        expect(typeof sub.getRuleDwell).toBe('function');
    });

    it('registerRule adds a custom rule that fires and transitions state', () => {
        const d = new FsmDriver();
        // Register a custom IDLE→READY rule with no dwell requirement
        d.fsm.registerRule({
            ruleId:    'custom_magic',
            fromState: 'IDLE',
            toState:   'READY',
            evaluator: { conditionId: 'magic', evaluate: (frame: any) => frame.gesture === 'magic_gesture' ? frame.confidence : 0 },
            conf_high: 0.64,
            conf_low:  0.50,
            dwell_ms:  0,
            priority:  99,
        } as any);
        d.tick('magic_gesture', 0.8);       // custom rule fires instantly (dwell_ms=0)
        expect(d.fsm.state.type).toBe('READY');
    });

    it('unregisterRule removes a custom rule so a subsequent matching gesture no longer fires', () => {
        const d = new FsmDriver();
        d.fsm.registerRule({
            ruleId:    'temp_rule',
            fromState: 'IDLE',
            toState:   'READY',
            evaluator: { conditionId: 'tmp', evaluate: (frame: any) => frame.gesture === 'tmp_gesture' ? frame.confidence : 0 },
            conf_high: 0.64,
            conf_low:  0.50,
            dwell_ms:  0,
            priority:  99,
        } as any);
        d.fsm.unregisterRule('temp_rule');  // remove before it can fire
        d.tick('tmp_gesture', 0.8);         // rule is gone → no transition
        // confidence 0.8 > coastConfLow 0.50 → no coast; no rule → stays IDLE
        expect(d.fsm.state.type).toBe('IDLE');
    });

});

// ─── IDLE inhibition hard-reset vs drain ────────────────────────────────────
// Kills: ObjectLiteral(line 125), fromState:""(127), evaluator:""(129),
//        inhibits:[](133), inhibits:[""](133).
// With idle_reinforce_fist missing/broken: closed_fist can only DRAIN idle_to_ready at the
// 2:1 rate (40ms per 20ms tick), not hard-reset it to 0.

describe('GestureFSM — idle_reinforce_fist hard-reset proof', () => {

    it('Given idle_to_ready dwell at 80ms, When closed_fist fires, Then dwell hard-resets to 0 (not 40ms drain remainder)', () => {
        const d = new FsmDriver();
        // Tick 1 (delta=0 NaN guard) → 0ms; ticks 2-5 (4 × 20ms) → 80ms accumulated
        d.tickN('open_palm', 0.8, 5);
        expect(d.fsm.ready_bucket_ms).toBe(80);
        // Closed fist: idle_reinforce_fist inhibits idle_to_ready → hard-reset to 0.
        // Without inhibition the 2:1 drain would only reduce by 40ms → 40ms remaining.
        d.tick('closed_fist', 0.8);
        expect(d.fsm.ready_bucket_ms).toBe(0);   // hard reset confirms inhibition fired
        expect(d.fsm.state.type).toBe('IDLE');
    });

});

// ─── State cache identity ────────────────────────────────────────────────────
// Kills ConditionalExpression(line 200): `if (this._stateCache.type !== t)` → `if (true)`.
// With `if (true)` the getter reallocates on every access → two consecutive calls
// return different object references.  With the real guard they return the same one.

describe('GestureFSM — state cache identity', () => {

    it('state getter returns the same cached object when state has not changed', () => {
        const d = new FsmDriver();
        const s1 = d.fsm.state;
        const s2 = d.fsm.state;    // no tick — state unchanged
        expect(s1).toBe(s2);        // strict reference equality: cache hit
    });

});

// ─── ready_bucket_ms in IDLE_COAST ───────────────────────────────────────────
// Kills ConditionalExpression(line 215) `s === 'IDLE_COAST' → false`
// AND StringLiteral(line 215) `s === 'IDLE_COAST' → s === ""`.
// With either mutation, ready_bucket_ms in IDLE_COAST falls through to the
// `commit_to_ready` branch (always 0) instead of `idle_to_ready` (holds preserved dwell).

describe('GestureFSM — ready_bucket_ms branch in IDLE_COAST', () => {

    it('Given IDLE with 40ms dwell, When forceCoast(), Then ready_bucket_ms still reads idle_to_ready dwell', () => {
        const d = new FsmDriver();
        // 3 ticks: tick1 delta=0 → 0ms; ticks 2–3 (2×20ms) → 40ms
        d.tickN('open_palm', 0.8, 3);
        expect(d.fsm.state.type).toBe('IDLE');
        expect(d.fsm.ready_bucket_ms).toBe(40);
        // Coast transition preserves dwell accumulators (not a state reset)
        d.fsm.forceCoast();
        expect(d.fsm.state.type).toBe('IDLE_COAST');
        // Must still return the idle_to_ready dwell (40ms), not commit_to_ready (0)
        expect(d.fsm.ready_bucket_ms).toBe(40);
    });

});

// ─── configure() dwellCommitMs patches commit_to_ready AND commit_to_idle ───
// Kills StringLiteral(line 245) patchRule('commit_to_ready' → ''),
//       ObjectLiteral(line 245)  patchRule(..., { dwell_ms } → {}),
//       StringLiteral(line 246)  patchRule('commit_to_idle'  → ''),
//       ObjectLiteral(line 246)  patchRule(..., { dwell_ms } → {}).
// The existing configure test (line 452) only covers `ready_to_commit` (pointer_up→COMMIT path).
// These two new tests cover the COMMIT release paths.

describe('GestureFSM — configure() patches commit release rules', () => {

    it('configure dwellCommitMs takes effect on COMMIT → READY path (open_palm release)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.fsm.configure({ dwellCommitMs: 20 });
        // One tick of 20ms with open_palm ≥ new 20ms dwell → transitions to READY
        d.tick('open_palm', 0.8);
        expect(d.fsm.state.type).toBe('READY');
    });

    it('configure dwellCommitMs takes effect on COMMIT → IDLE path (closed_fist release)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        d.fsm.configure({ dwellCommitMs: 20 });
        // One tick of 20ms with closed_fist ≥ new 20ms dwell → transitions to IDLE
        d.tick('closed_fist', 0.8);
        expect(d.fsm.state.type).toBe('IDLE');
    });

});

// ─── COMMIT mutual inhibition hard-reset proofs ───────────────────────────────
// Kills inhibits:[](line 175), inhibits:[""](line 175) — commit_to_ready inhibits commit_to_idle.
// Kills inhibits:[](line 188), inhibits:[""](line 188) — commit_to_idle inhibits commit_to_ready.
//
// Strategy: accumulate 60ms in the TARGET bucket so that a single drain tick (40ms)
// leaves 20ms if inhibition is absent, but 0 if inhibition fires (hard-reset then drain from 0).

describe('GestureFSM — COMMIT mutual inhibition hard-resets (lines 175 & 188)', () => {

    it('Given COMMIT with 60ms idle_bucket, When open_palm fires, Then idle_bucket hard-resets to 0 (not 20ms)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        // Build idle_bucket to 60ms (3 ticks × 20ms; inhibition keeps ready_bucket at 0)
        d.tick('closed_fist', 0.8);   // idle=20ms
        d.tick('closed_fist', 0.8);   // idle=40ms
        d.tick('closed_fist', 0.8);   // idle=60ms  (< 100ms dwell → no IDLE transition)
        expect(d.fsm.idle_bucket_ms).toBe(60);
        // Open palm fires commit_to_ready → inhibits commit_to_idle → hard-reset idle_bucket
        d.tick('open_palm', 0.8);     // delta=20ms; 20ms < 100ms dwell → still COMMIT
        expect(d.fsm.idle_bucket_ms).toBe(0);    // hard reset: 0.  Drain-only: max(0,60-40)=20
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

    it('Given COMMIT with 60ms ready_bucket, When closed_fist fires, Then ready_bucket hard-resets to 0 (not 20ms)', () => {
        const d = new FsmDriver();
        d.driveToCommit();
        // Build ready_bucket to 60ms (3 ticks × 20ms)
        d.tick('open_palm', 0.8);     // ready=20ms
        d.tick('open_palm', 0.8);     // ready=40ms
        d.tick('open_palm', 0.8);     // ready=60ms  (< 100ms → no READY transition)
        expect(d.fsm.ready_bucket_ms).toBe(60);
        // Closed fist fires commit_to_idle → inhibits commit_to_ready → hard-reset ready_bucket
        d.tick('closed_fist', 0.8);   // delta=20ms; 20ms < 100ms dwell → still COMMIT
        expect(d.fsm.ready_bucket_ms).toBe(0);   // hard reset: 0.  Drain-only: max(0,60-40)=20
        expect(d.fsm.state.type).toBe('COMMIT_POINTER');
    });

});
