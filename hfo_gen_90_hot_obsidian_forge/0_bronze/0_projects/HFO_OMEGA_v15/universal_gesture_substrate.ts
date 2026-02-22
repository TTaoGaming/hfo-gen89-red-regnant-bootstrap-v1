/**
 * universal_gesture_substrate.ts
 *
 * UNIVERSAL GESTURE SUBSTRATE — a fail-closed microkernel rule engine for
 * gesture-driven state machines.
 *
 * ── DESIGN PHILOSOPHY ──────────────────────────────────────────────────────
 * States are labels.  Behaviour lives entirely in registered TransitionRules.
 * A rule is the atomic unit of behaviour:
 *   fromState → toState, triggered by a ConditionEvaluator (the plugin),
 *   with its own accumulation threshold (conf_high) and millisecond dwell.
 *
 * To add a new gesture or sensor condition:
 *   1. Implement ConditionEvaluator (one method: evaluate(frame) → 0–1)
 *   2. Call substrate.register(rule)
 *   Zero FSM surgery required.  Correct by construction.
 *
 * ── LATCHING ───────────────────────────────────────────────────────────────
 * READY and COMMIT_POINTER are latched states.  They persist until an
 * explicit exit rule fires (e.g. clutch gesture) or tracking is fully lost
 * past the coast timeout.  There is NO implicit fallback from a latched state.
 *
 * ── COAST (substrate-built-in — not a plugin concern) ─────────────────────
 * When frame.confidence drops below coastConfLow, the FSM enters the
 * corresponding coast state.  Coast states are lifecycle-guaranteed: a
 * coastTimeoutMs timer ensures the FSM always terminates — no stuck pointers.
 * On confidence recovery above coastConfHigh, the FSM snaplocks back to the
 * pre-coast state with dwell accumulators preserved.
 * Future: FABRIK biomechanical fingerprinting and stillness monitors hook
 * into coast exit / entry here without touching rule logic.
 *
 * ── DWELL MODEL ────────────────────────────────────────────────────────────
 * Each TransitionRule has its own dwell accumulator (ms-based, framerate-
 * independent).  On a frame where rawConf >= conf_high: accumulate by deltaMs.
 * Otherwise: drain at 2:1 rate (max(0, dwell - 2*delta)).  No boolean
 * Schmitt state is tracked per-rule — just threshold + drain.
 *
 * ── MUTUAL INHIBITION (inhibits[]) ────────────────────────────────────────
 * A rule may declare inhibits: ['ruleId', ...].  Before dwell accumulation:
 * if the declaring rule's rawConf >= conf_high that frame, the listed rules
 * have their dwell accumulator immediately zeroed.  This models hard-reset
 * competition between gestures (e.g. open_palm vs closed_fist in COMMIT).
 *
 * ── MULTI-HAND ─────────────────────────────────────────────────────────────
 * Each tracked hand holds one GestureSubstrate instance.  The Highlander
 * single-hand policy is a higher-level application concern — not here.
 *
 * ── OPEN SENSOR FRAME ─────────────────────────────────────────────────────
 * SensorFrame.extras is an untyped bag (Record<string, unknown>).  Future
 * sensors — thermal cameras, FABRIK landmarks, finger-curl metrics, gaze, etc
 * — drop their data into extras without touching this file.
 */

// ── SensorFrame ──────────────────────────────────────────────────────────────

/**
 * The per-frame input to every ConditionEvaluator.
 * extras is deliberately open: conditions can read landmarks, thermal data,
 * FABRIK state, IMU readings — any sensor — through the extras bag.
 */
export interface SensorFrame {
    readonly gesture:    string;
    readonly confidence: number;
    readonly nowMs:      number;
    readonly extras:     Readonly<Record<string, unknown>>;
}

// ── Plugin interface ──────────────────────────────────────────────────────────

/**
 * A condition evaluator — the pluggable sensor or gesture classifier.
 * Returns a value in [0, 1].  The substrate applies the dwell model and
 * inhibition logic; the evaluator only needs to express "how confident am
 * I that the condition is met right now?"
 */
export interface ConditionEvaluator {
    readonly conditionId: string;
    evaluate(frame: SensorFrame): number;
}

// ── Transition rule descriptor ────────────────────────────────────────────────

/**
 * Full transition descriptor.  Register one per desired state transition.
 *
 * conf_high : rawConf must reach this threshold to start accumulating dwell.
 * conf_low  : rawConf for this rule drops below coastConfLow to enter coast
 *             (handled at substrate level); kept here for documentation of
 *             the intended Schmitt range and future per-rule coast support.
 * dwell_ms  : ms the rule must remain hot (rawConf >= conf_high) before
 *             firing.  Use 0 for an instantaneous (stateless) transition.
 * priority  : when multiple rules are candidates, highest priority fires.
 * inhibits  : list of ruleIds whose dwell this rule resets to zero each
 *             frame its rawConf >= conf_high (mutual exclusion pattern).
 */
export interface TransitionRule {
    readonly ruleId:    string;
    readonly fromState: StateType;
    readonly toState:   StateType;
    readonly evaluator: ConditionEvaluator;
    readonly conf_high: number;
    readonly conf_low:  number;
    readonly dwell_ms:  number;
    readonly priority:  number;
    readonly inhibits?: ReadonlyArray<string>;
}

// ── State types ───────────────────────────────────────────────────────────────

export type StateType =
    | 'IDLE'
    | 'IDLE_COAST'
    | 'READY'
    | 'READY_COAST'
    | 'COMMIT_POINTER'
    | 'COMMIT_COAST';

// ── Snapshot ──────────────────────────────────────────────────────────────────

export interface StateSnapshot {
    readonly type:        StateType;
    /** true when in READY or COMMIT_POINTER — explicit exit required */
    readonly isLatched:   boolean;
    /** true when in any _COAST state */
    readonly isCoasting:  boolean;
    /** true when in COMMIT_POINTER or COMMIT_COAST */
    readonly isPinching:  boolean;
    /** ms timestamp when the current state was entered */
    readonly stateSince:  number;
}

// ── Substrate config ──────────────────────────────────────────────────────────

export interface SubstrateConfig {
    /** ms in a coast state before falling through to IDLE.  Default 500. */
    coastTimeoutMs:   number;
    /** Confidence below this triggers coast entry.  Default 0.50. */
    coastConfLow:     number;
    /** Confidence at or above this snaplocks out of coast.  Default 0.64. */
    coastConfHigh:    number;
}

// ── Internal runtime state per rule ──────────────────────────────────────────

interface RuleRuntime {
    dwellAccumMs: number;
}

// ── State classification sets ─────────────────────────────────────────────────

const LATCHED_STATES = new Set<StateType>(['READY', 'COMMIT_POINTER']);
const COAST_STATES   = new Set<StateType>(['IDLE_COAST', 'READY_COAST', 'COMMIT_COAST']);

// ── GestureSubstrate ─────────────────────────────────────────────────────────

export class GestureSubstrate {

    private readonly _rules:    Map<string, TransitionRule> = new Map();
    private readonly _runtimes: Map<string, RuleRuntime>    = new Map();

    private _state:        StateType = 'IDLE';
    private _stateSince:   number    = 0;
    private _lastFrameMs:  number    = NaN;
    private _coastElapsed: number    = 0;

    private _coastTimeoutMs:  number;
    private _coastConfLow:    number;
    private _coastConfHigh:   number;

    constructor(cfg: Partial<SubstrateConfig> = {}) {
        this._coastTimeoutMs = cfg.coastTimeoutMs ?? 500;
        this._coastConfLow   = cfg.coastConfLow   ?? 0.50;
        this._coastConfHigh  = cfg.coastConfHigh  ?? 0.64;
    }

    // ── Config hot-swap ───────────────────────────────────────────────────────

    /** Hot-swap coast parameters.  Safe to call mid-session. */
    setCoastConfig(cfg: Partial<SubstrateConfig>): void {
        if (cfg.coastTimeoutMs !== undefined) this._coastTimeoutMs = cfg.coastTimeoutMs;
        if (cfg.coastConfLow   !== undefined) this._coastConfLow   = cfg.coastConfLow;
        if (cfg.coastConfHigh  !== undefined) this._coastConfHigh  = cfg.coastConfHigh;
    }

    // ── Rule management ───────────────────────────────────────────────────────

    /**
     * Register a transition rule.  Replaces any existing rule with the same
     * ruleId (safe for hot-swap configure calls) but preserves the existing
     * runtime state (dwell accumulator) so in-progress gestures survive.
     * To reset dwell on hot-swap, call unregister() first.
     */
    register(rule: TransitionRule): void {
        this._rules.set(rule.ruleId, rule);
        if (!this._runtimes.has(rule.ruleId)) {
            this._runtimes.set(rule.ruleId, { dwellAccumMs: 0 });
        }
    }

    /** Unregister a rule and discard its runtime state. */
    unregister(ruleId: string): void {
        this._rules.delete(ruleId);
        this._runtimes.delete(ruleId);
    }

    /**
     * Patch a rule's numeric fields without resetting its dwell accumulator.
     * Intended for live configure() calls that adjust thresholds mid-session.
     */
    patchRule(ruleId: string, patch: {
        dwell_ms?:  number;
        conf_high?: number;
        conf_low?:  number;
        priority?:  number;
    }): void {
        const existing = this._rules.get(ruleId);
        if (!existing) return;
        this._rules.set(ruleId, { ...existing, ...patch });
    }

    /**
     * Read the current dwell accumulator for a rule (ms).
     * Used by wiring layers to expose vote-bucket metrics (e.g. ready_bucket_ms).
     */
    getRuleDwell(ruleId: string): number {
        return this._runtimes.get(ruleId)?.dwellAccumMs ?? 0;
    }

    // ── Frame processing ──────────────────────────────────────────────────────

    processFrame(frame: SensorFrame): StateSnapshot {

        const deltaMs = isNaN(this._lastFrameMs) ? 0 : frame.nowMs - this._lastFrameMs;
        this._lastFrameMs = frame.nowMs;

        // ── 1. Coast timeout (total tracking loss) ───────────────────────────
        if (COAST_STATES.has(this._state)) {
            this._coastElapsed += deltaMs;
            if (this._coastElapsed >= this._coastTimeoutMs) {
                // Full dwell reset before hard-landing to IDLE.
                // Coast→IDLE in _enterState is a coast transition (no rule resets),
                // so we must clear runtimes explicitly — matches original's
                // `this.dwell_accumulator_ms = 0` on coast timeout.
                for (const runtime of this._runtimes.values()) {
                    runtime.dwellAccumMs = 0;
                }
                this._enterState('IDLE', frame.nowMs);
                return this.snapshot;
            }
        } else {
            this._coastElapsed = 0;
        }

        // ── 2. Tracking loss → enter coast ───────────────────────────────────
        if (!COAST_STATES.has(this._state) && frame.confidence < this._coastConfLow) {
            const coastState = this._coastStateFor(this._state);
            if (coastState !== null) {
                this._enterState(coastState, frame.nowMs);
                return this.snapshot;
            }
        }

        // ── 3. Snaplock: regain tracking while in coast ───────────────────────
        if (COAST_STATES.has(this._state) && frame.confidence >= this._coastConfHigh) {
            this._enterState(this._resumeStateFor(this._state), frame.nowMs);
            return this.snapshot;
        }

        // ── 4. Evaluate registered rules ─────────────────────────────────────

        // Pass A: compute raw confidence for each active rule (one evaluator
        //         call per rule; result is reused in passes B and C).
        const rawConfs = new Map<string, number>();
        for (const [ruleId, rule] of this._rules) {
            if (rule.fromState !== this._state) continue;
            rawConfs.set(ruleId, rule.evaluator.evaluate(frame));
        }

        // Pass B: apply inhibitions BEFORE dwell accumulation.
        //   If rule X is "hot" (rawConf >= conf_high), zero the dwell of
        //   every rule in X.inhibits[].  This models mutual hard-reset
        //   between competing gestures (e.g. palm vs fist in COMMIT release).
        for (const [ruleId, rule] of this._rules) {
            if (rule.fromState !== this._state || !rule.inhibits) continue;
            if ((rawConfs.get(ruleId) ?? 0) >= rule.conf_high) {
                for (const inhibitedId of rule.inhibits) {
                    const inhibited = this._runtimes.get(inhibitedId);
                    if (inhibited) inhibited.dwellAccumMs = 0;
                }
            }
        }

        // Pass C: accumulate / drain dwell; collect firing candidates.
        const candidates: Array<{ rule: TransitionRule; runtime: RuleRuntime }> = [];

        for (const [ruleId, rule] of this._rules) {
            if (rule.fromState !== this._state) continue;
            const runtime  = this._runtimes.get(ruleId)!;
            const rawConf  = rawConfs.get(ruleId)!;

            if (rawConf >= rule.conf_high) {
                runtime.dwellAccumMs += deltaMs;
            } else {
                // 2:1 drain rate (framerate-independent leaky bucket)
                runtime.dwellAccumMs = Math.max(0, runtime.dwellAccumMs - 2 * deltaMs);
            }

            // Candidate if hot AND dwell budget met (dwell_ms=0 fires immediately)
            if (rawConf >= rule.conf_high && runtime.dwellAccumMs >= rule.dwell_ms) {
                candidates.push({ rule, runtime });
            }
        }

        // ── 5. Fire highest-priority candidate ───────────────────────────────
        if (candidates.length > 0) {
            candidates.sort((a, b) => b.rule.priority - a.rule.priority);
            const winner = candidates[0]!;
            winner.runtime.dwellAccumMs = 0;              // reset fired rule
            this._enterState(winner.rule.toState, frame.nowMs);
        }

        return this.snapshot;
    }

    // ── Escape hatches ────────────────────────────────────────────────────────

    /**
     * Immediately force the FSM to IDLE and clear all dwell accumulators.
     * Use for hard resets (e.g. hand lost from scene, user disengaged).
     */
    forceIdle(nowMs?: number): void {
        this._enterState('IDLE', nowMs ?? this._lastFrameMs);
        for (const runtime of this._runtimes.values()) {
            runtime.dwellAccumMs = 0;
        }
    }

    /**
     * Force the current active state into its corresponding coast state.
     * Useful for stillness-monitor hooks and predictive inertia.
     */
    forceCoast(nowMs?: number): void {
        const coastState = this._coastStateFor(this._state);
        if (coastState !== null) {
            this._enterState(coastState, nowMs ?? this._lastFrameMs);
        }
    }

    // ── Getters ───────────────────────────────────────────────────────────────

    get snapshot(): StateSnapshot {
        return {
            type:       this._state,
            isLatched:  LATCHED_STATES.has(this._state),
            isCoasting: COAST_STATES.has(this._state),
            isPinching: this._state === 'COMMIT_POINTER' || this._state === 'COMMIT_COAST',
            stateSince: this._stateSince,
        };
    }

    get state(): StateType { return this._state; }

    // ── Private helpers ───────────────────────────────────────────────────────

    /**
     * Transition to a new state.  On non-coast → non-coast transitions,
     * resets the dwell accumulators of rules that fire FROM the new state
     * so each latched-state entry starts clean.
     *
     * Coast ↔ active transitions deliberately preserve dwell (coast is
     * inertia — the FSM is mid-gesture, just waiting for tracking recovery).
     */
    private _enterState(next: StateType, nowMs: number): void {
        if (next === this._state) return;

        const prev = this._state;
        this._state      = next;
        this._stateSince = nowMs;

        const isCoastTransition = COAST_STATES.has(next) || COAST_STATES.has(prev);
        if (!isCoastTransition) {
            // Clean slate for rules in the new state
            for (const rule of this._rules.values()) {
                if (rule.fromState === next) {
                    const runtime = this._runtimes.get(rule.ruleId);
                    if (runtime) runtime.dwellAccumMs = 0;
                }
            }
        }
    }

    private _coastStateFor(state: StateType): StateType | null {
        switch (state) {
            case 'IDLE':           return 'IDLE_COAST';
            case 'READY':          return 'READY_COAST';
            case 'COMMIT_POINTER': return 'COMMIT_COAST';
            default:               return null;   // already in a coast state
        }
    }

    private _resumeStateFor(coastState: StateType): StateType {
        switch (coastState) {
            case 'IDLE_COAST':   return 'IDLE';
            case 'READY_COAST':  return 'READY';
            case 'COMMIT_COAST': return 'COMMIT_POINTER';
            default:             return 'IDLE';
        }
    }
}
