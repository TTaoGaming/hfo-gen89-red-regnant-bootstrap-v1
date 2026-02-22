/**
 * gesture_fsm.ts — built-in wiring layer for the Universal Gesture Substrate
 *
 * This class is the CONCRETE WIRING of the microkernel.  It sits on top of
 * GestureSubstrate and registers the six canonical gesture-transition rules
 * used by the Omega v15 touchless whiteboard:
 *
 *   IDLE  ──open_palm+dwell──►  READY  (latch)
 *   READY ──closed_fist──────►  IDLE   (clutch, instant)
 *   READY ──pointer_up+dwell─►  COMMIT_POINTER  (latch)
 *   COMMIT──open_palm+dwell──►  READY  (release, palm wins tie)
 *   COMMIT──closed_fist+dwell►  IDLE   (clutch from commit)
 *   IDLE  ──closed_fist──────►  IDLE   (reinforce, resets ready dwell)
 *
 *   Coast states are substrate-built-in and provide graceful degradation on
 *   tracking loss, with a hard timeout to guarantee lifecycle termination.
 *
 * ── EXTENSION POINT ────────────────────────────────────────────────────────
 * The substrate is correct by construction.  To add a new gesture condition:
 *
 *   fsm.registerRule({
 *     ruleId:    'my_new_condition',
 *     fromState: 'READY',
 *     toState:   'COMMIT_POINTER',
 *     evaluator: myFingerCurlEvaluator,   // implements ConditionEvaluator
 *     conf_high: 0.70,
 *     conf_low:  0.45,
 *     dwell_ms:  80,
 *     priority:  0,
 *   });
 *
 * Zero FSM surgery.  Works for: finger curl, landmark distance, thermal
 * camera confidence, gaze direction, IMU, or any sensor returning 0–1.
 *
 * ── BACKWARD COMPATIBILITY ─────────────────────────────────────────────────
 * The public API is pin-compatible with the previous gesture_fsm.ts:
 *   state, ready_bucket_ms, idle_bucket_ms, processFrame(), configure(),
 *   isPinching(), isCoasting(), forceCoast()
 */

import {
    GestureSubstrate,
    SensorFrame,
    ConditionEvaluator,
    TransitionRule,
    StateType,
} from './universal_gesture_substrate.js';

import {
    FsmState,
    StateIdle,
    StateIdleCoast,
    StateReady,
    StateReadyCoast,
    StateCommit,
    StateCommitCoast,
    RawCoord,
} from './types.js';

// ── Condition evaluator factory ───────────────────────────────────────────────

/**
 * Creates a simple gesture-match evaluator.
 * Returns frame.confidence when frame.gesture matches targetGesture, else 0.
 * The substrate's dwell and coast model handles the rest.
 */
function makeGestureEvaluator(targetGesture: string): ConditionEvaluator {
    return {
        conditionId: `gesture:${targetGesture}`,
        evaluate(frame: SensorFrame): number {
            return frame.gesture === targetGesture ? frame.confidence : 0;
        },
    };
}

// ── GestureFSM ────────────────────────────────────────────────────────────────

export class GestureFSM {

    private readonly _substrate: GestureSubstrate;

    // Schmitt thresholds — stored here for configure() hot-swap patchRule calls
    private readonly _conf_high = 0.64;
    private readonly _conf_low  = 0.50;

    // Dwell budgets — mutable via configure()
    private _dwellReadyMs  = 100;
    private _dwellCommitMs = 100;
    private _coastTimeoutMs = 500;

    // Cached FsmState object — recreated only when state type changes
    private _stateCache: FsmState = new StateIdle();

    constructor() {
        this._substrate = new GestureSubstrate({
            coastTimeoutMs: this._coastTimeoutMs,
            coastConfLow:   this._conf_low,
            coastConfHigh:  this._conf_high,
        });
        this._registerBuiltinRules();
    }

    // ── Built-in transition rules ─────────────────────────────────────────────

    private _registerBuiltinRules(): void {
        const h = this._conf_high;
        const l = this._conf_low;

        // ── IDLE rules ────────────────────────────────────────────────────────

        // Advance: open palm + dwell → READY (latch entry)
        this._substrate.register({
            ruleId:    'idle_to_ready',
            fromState: 'IDLE',
            toState:   'READY',
            evaluator: makeGestureEvaluator('open_palm'),
            conf_high: h, conf_low: l,
            dwell_ms:  this._dwellReadyMs,
            priority:  0,
        });

        // Reinforce IDLE: closed fist resets the ready-advance dwell.
        // Self-loop (IDLE → IDLE): fires instantly when hot, no state change.
        // inhibits idle_to_ready = hard resets open_palm accumulation.
        this._substrate.register({
            ruleId:    'idle_reinforce_fist',
            fromState: 'IDLE',
            toState:   'IDLE',
            evaluator: makeGestureEvaluator('closed_fist'),
            conf_high: h, conf_low: l,
            dwell_ms:  0,
            priority:  5,
            inhibits:  ['idle_to_ready'],
        });

        // ── READY rules ───────────────────────────────────────────────────────

        // Clutch: closed fist → IDLE instantly (highest priority — outranks advance)
        // inhibits ready_to_commit = also resets pointer-up accumulation
        this._substrate.register({
            ruleId:    'ready_to_idle',
            fromState: 'READY',
            toState:   'IDLE',
            evaluator: makeGestureEvaluator('closed_fist'),
            conf_high: h, conf_low: l,
            dwell_ms:  0,
            priority:  10,
            inhibits:  ['ready_to_commit'],
        });

        // Advance: pointer up + dwell → COMMIT_POINTER (latch entry)
        this._substrate.register({
            ruleId:    'ready_to_commit',
            fromState: 'READY',
            toState:   'COMMIT_POINTER',
            evaluator: makeGestureEvaluator('pointer_up'),
            conf_high: h, conf_low: l,
            dwell_ms:  this._dwellCommitMs,
            priority:  0,
            inhibits:  ['ready_to_idle'],
        });

        // ── COMMIT_POINTER rules ──────────────────────────────────────────────

        // Release to READY: open palm + dwell.  priority=2 → palm wins ties.
        // inhibits commit_to_idle = zeros fist vote bucket while palm is hot.
        this._substrate.register({
            ruleId:    'commit_to_ready',
            fromState: 'COMMIT_POINTER',
            toState:   'READY',
            evaluator: makeGestureEvaluator('open_palm'),
            conf_high: h, conf_low: l,
            dwell_ms:  this._dwellCommitMs,
            priority:  2,
            inhibits:  ['commit_to_idle'],
        });

        // Clutch from COMMIT: closed fist + dwell → IDLE.
        // inhibits commit_to_ready = zeros palm vote bucket while fist is hot.
        this._substrate.register({
            ruleId:    'commit_to_idle',
            fromState: 'COMMIT_POINTER',
            toState:   'IDLE',
            evaluator: makeGestureEvaluator('closed_fist'),
            conf_high: h, conf_low: l,
            dwell_ms:  this._dwellCommitMs,
            priority:  1,
            inhibits:  ['commit_to_ready'],
        });
    }

    // ── Backward-compatible public API ────────────────────────────────────────

    /**
     * Current FSM state as a typestate object.  Callers check .state.type.
     * Object is cached and only reallocated on state type change.
     */
    get state(): FsmState {
        const t = this._substrate.state;
        if (this._stateCache.type !== t) {
            this._stateCache = this._makeState(t);
        }
        return this._stateCache;
    }

    /**
     * Advance vote bucket — palm side.  Context-sensitive:
     *   • In IDLE / IDLE_COAST  → ms of open_palm accumulated towards READY (idle_to_ready dwell)
     *   • In COMMIT / COMMIT_COAST → ms of open_palm accumulated towards COMMIT release (commit_to_ready dwell)
     * This matches the original single-field semantics where `ready_bucket_ms` tracked
     * the active palm accumulator regardless of which transition it drives.
     */
    get ready_bucket_ms(): number {
        const s = this._substrate.state;
        if (s === 'IDLE' || s === 'IDLE_COAST') {
            return this._substrate.getRuleDwell('idle_to_ready');
        }
        return this._substrate.getRuleDwell('commit_to_ready');
    }

    /**
     * COMMIT release vote bucket — fist side.
     * Reflects how many ms of closed_fist have accumulated towards an IDLE exit.
     */
    get idle_bucket_ms(): number {
        return this._substrate.getRuleDwell('commit_to_idle');
    }

    /**
     * Hot-swap dwell and coast thresholds.
     * Safe to call during live tracking — takes effect on the next frame.
     */
    public configure(cfg: {
        dwellReadyMs?:   number;
        dwellCommitMs?:  number;
        coastTimeoutMs?: number;
    }): void {
        if (cfg.dwellReadyMs !== undefined) {
            this._dwellReadyMs = cfg.dwellReadyMs;
            this._substrate.patchRule('idle_to_ready', { dwell_ms: cfg.dwellReadyMs });
        }
        if (cfg.dwellCommitMs !== undefined) {
            this._dwellCommitMs = cfg.dwellCommitMs;
            this._substrate.patchRule('ready_to_commit', { dwell_ms: cfg.dwellCommitMs });
            this._substrate.patchRule('commit_to_ready', { dwell_ms: cfg.dwellCommitMs });
            this._substrate.patchRule('commit_to_idle',  { dwell_ms: cfg.dwellCommitMs });
        }
        if (cfg.coastTimeoutMs !== undefined) {
            this._coastTimeoutMs = cfg.coastTimeoutMs;
            this._substrate.setCoastConfig({ coastTimeoutMs: cfg.coastTimeoutMs });
        }
    }

    /**
     * Process a frame of data for this specific hand.
     * @param gesture    Detected gesture label ('open_palm', 'closed_fist', 'pointer_up', …)
     * @param confidence Confidence score 0–1
     * @param _x         Normalised X coordinate (unused in substrate; reserved for future landmark routing)
     * @param _y         Normalised Y coordinate (unused in substrate; reserved for future landmark routing)
     * @param nowMs      Wall-clock timestamp in ms (performance.now())
     */
    public processFrame(
        gesture: string,
        confidence: number,
        _x: RawCoord = -1 as RawCoord,
        _y: RawCoord = -1 as RawCoord,
        nowMs = performance.now()
    ): void {
        const frame: SensorFrame = {
            gesture,
            confidence,
            nowMs,
            extras: {},
        };
        this._substrate.processFrame(frame);
    }

    /** true when in COMMIT_POINTER or COMMIT_COAST (pointer is pinching / active) */
    public isPinching(): boolean {
        return this._substrate.snapshot.isPinching;
    }

    /** true when in any _COAST state */
    public isCoasting(): boolean {
        return this._substrate.snapshot.isCoasting;
    }

    /** Force the FSM into a coasting state (e.g. due to stillness monitor) */
    public forceCoast(): void {
        this._substrate.forceCoast();
    }

    // ── Universal substrate extension points ──────────────────────────────────

    /**
     * Register a custom transition rule at runtime.
     *
     * This is the primary UNIVERSAL_SUBSTRATE extension point.  Any
     * ConditionEvaluator can drive any transition:
     *   - finger curl (landmark angles from MediaPipe)
     *   - distance between landmarks
     *   - IMU stillness / motion magnitude
     *   - thermal camera confidence
     *   - gaze direction or eye-tracking confidence
     *   - any composite multi-sensor condition
     *
     * The substrate handles Schmitt hysteresis, dwell-leaky-bucket, coast,
     * and inhibition.  The evaluator only needs to return a 0–1 confidence.
     */
    public registerRule(rule: TransitionRule): void {
        this._substrate.register(rule);
    }

    /** Unregister a previously registered rule by its ruleId. */
    public unregisterRule(ruleId: string): void {
        this._substrate.unregister(ruleId);
    }

    /**
     * Direct access to the underlying GestureSubstrate.
     * For advanced use: inspect rule dwells, call patchRule(), subscribe to
     * state snapshots, or integrate with a custom host FSM.
     */
    public get substrate(): GestureSubstrate {
        return this._substrate;
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private _makeState(t: StateType): FsmState {
        switch (t) {
            case 'IDLE':           return new StateIdle();
            case 'IDLE_COAST':     return new StateIdleCoast();
            case 'READY':          return new StateReady();
            case 'READY_COAST':    return new StateReadyCoast();
            case 'COMMIT_POINTER': return new StateCommit();
            case 'COMMIT_COAST':   return new StateCommitCoast();
        }
    }
}

