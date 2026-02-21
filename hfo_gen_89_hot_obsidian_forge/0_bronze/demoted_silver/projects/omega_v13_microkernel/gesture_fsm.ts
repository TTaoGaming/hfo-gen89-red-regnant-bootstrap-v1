/**
 * gesture_fsm.ts
 * 
 * A lightweight TypeScript implementation of the SCXML logic defined in gesture_fsm.scxml.
 * This class manages the state of a single hand, including confidence hysteresis (Schmitt trigger)
 * and asymmetrical leaky bucket (dwell) logic.
 * 
 * ARCHITECTURAL NOTE (SCXML vs TS Sync):
 * While this manual TS implementation is highly optimized for a 60fps render loop, 
 * it carries the risk of drifting out of sync with the formal `gesture_fsm.scxml` specification.
 * In a future iteration, consider a build-step compiler that generates this TS class 
 * directly from the SCXML file to guarantee "correct by construction" parity.
 */

import { FsmState, StateIdle, StateIdleCoast, StateReady, StateReadyCoast, StateCommit, StateCommitCoast, RawCoord } from './types.js';

export class GestureFSM {
    public state: FsmState = new StateIdle();

    // Schmitt Trigger Thresholds (framerate-independent — no change needed)
    private readonly conf_high = 0.64;
    private readonly conf_low  = 0.50;

    // Dwell limits — milliseconds, NOT frames (framerate-independent)
    private dwell_limit_ready_ms  = 100;
    private dwell_limit_commit_ms = 100;

    // Current State Variables
    private current_confidence   = 0.0;
    /** Accumulated qualifying-gesture time in ms (leaky bucket, 2:1 leak ratio). */
    private dwell_accumulator_ms = 0;
    public ready_bucket_ms = 0;
    public idle_bucket_ms = 0;

    // Coast Timeout — ms until COAST states hard-reset to IDLE
    private coast_elapsed_ms = 0;
    private coast_timeout_ms = 500;

    /** Timestamp (ms) of the previous processFrame call.  NaN = first call. */
    private lastFrameMs = NaN;

    /**
     * Hot-swap dwell and coast thresholds from the ConfigMosaic.
     * Safe to call during live tracking — takes effect on the next frame.
     */
    public configure(cfg: {
        dwellReadyMs?:   number;
        dwellCommitMs?:  number;
        coastTimeoutMs?: number;
    }): void {
        if (cfg.dwellReadyMs   !== undefined) this.dwell_limit_ready_ms  = cfg.dwellReadyMs;
        if (cfg.dwellCommitMs  !== undefined) this.dwell_limit_commit_ms = cfg.dwellCommitMs;
        if (cfg.coastTimeoutMs !== undefined) this.coast_timeout_ms      = cfg.coastTimeoutMs;
    }

    /**
     * Process a frame of data for this specific hand
     * @param gesture The detected gesture name (e.g., 'open_palm', 'closed_fist', 'pointer_up')
     * @param confidence The confidence score of the gesture (0.0 to 1.0)
     * @param x The normalized X coordinate (0.0 to 1.0)
     * @param y The normalized Y coordinate (0.0 to 1.0)
     */
    /**
     * @param nowMs  Wall-clock timestamp in ms (performance.now()).
     *               Caller should supply the same timestamp used to build the
     *               RawHandData.frameTimeMs so dwell is framerate-independent.
     *               Default falls back to performance.now() at call time.
     */
    public processFrame(
        gesture: string,
        confidence: number,
        x: RawCoord = -1 as RawCoord,
        y: RawCoord = -1 as RawCoord,
        nowMs = performance.now()
    ) {
        // Delta-time in ms since last frame.  First call → 0 (no accumulation).
        const deltaMs = isNaN(this.lastFrameMs) ? 0 : nowMs - this.lastFrameMs;
        this.lastFrameMs = nowMs;

        this.current_confidence = confidence;

        // 1. Handle Coast Timeouts (Total Loss)
        if (this.state.type.includes('COAST')) {
            this.coast_elapsed_ms += deltaMs;
            if (this.coast_elapsed_ms >= this.coast_timeout_ms) {
                this.state = new StateIdle(); // Reset to IDLE on total loss
                this.dwell_accumulator_ms = 0;
                return;
            }
        } else {
            this.coast_elapsed_ms = 0; // Reset coast timer when tracking is active
        }

        // 2. State Machine Logic
        switch (this.state.type) {
            case 'IDLE':
                this.handleIdle(gesture, deltaMs);
                break;
            case 'IDLE_COAST':
                this.handleIdleCoast();
                break;
            case 'READY':
                this.handleReady(gesture, deltaMs);
                break;
            case 'READY_COAST':
                this.handleReadyCoast();
                break;
            case 'COMMIT_POINTER':
                this.handleCommitPointer(gesture, deltaMs);
                break;
            case 'COMMIT_COAST':
                this.handleCommitCoast();
                break;
        }
    }

    private handleIdle(gesture: string, deltaMs: number) {
        // Schmitt Trigger: Drop to COAST
        if (this.current_confidence < this.conf_low) {
            this.state = new StateIdleCoast();
            return;
        }

        // Reinforce IDLE
        if (gesture === 'closed_fist' && this.current_confidence >= this.conf_high) {
            this.dwell_accumulator_ms = 0;
            this.ready_bucket_ms = 0;
        }

        // Leaky Bucket for READY (ms-based, 2:1 leak ratio)
        if (gesture === 'open_palm' && this.current_confidence >= this.conf_high) {
            this.dwell_accumulator_ms += deltaMs;
            this.ready_bucket_ms += deltaMs;
        } else if (this.current_confidence >= this.conf_low && this.current_confidence < this.conf_high) {
            this.dwell_accumulator_ms = Math.max(0, this.dwell_accumulator_ms - 2 * deltaMs);
            this.ready_bucket_ms = Math.max(0, this.ready_bucket_ms - 2 * deltaMs);
        } else if (gesture !== 'open_palm' && gesture !== 'closed_fist') {
            this.dwell_accumulator_ms = Math.max(0, this.dwell_accumulator_ms - 2 * deltaMs);
            this.ready_bucket_ms = Math.max(0, this.ready_bucket_ms - 2 * deltaMs);
        }

        // Transition to READY
        if (this.dwell_accumulator_ms >= this.dwell_limit_ready_ms) {
            this.state = new StateReady();
            this.dwell_accumulator_ms = 0;
            this.ready_bucket_ms = 0;
        }
    }

    private handleIdleCoast() {
        // Snaplock on regain
        if (this.current_confidence >= this.conf_high) {
            this.state = new StateIdle();
        }
    }

    private handleReady(gesture: string, deltaMs: number) {
        // Schmitt Trigger: Drop to COAST
        if (this.current_confidence < this.conf_low) {
            this.state = new StateReadyCoast();
            return;
        }

        // Return to IDLE (deny by default)
        if (gesture === 'closed_fist' && this.current_confidence >= this.conf_high) {
            this.state = new StateIdle();
            this.dwell_accumulator_ms = 0;
            return;
        }

        // Leaky Bucket for COMMIT (ms-based, 2:1 leak ratio)
        if (gesture === 'pointer_up' && this.current_confidence >= this.conf_high) {
            this.dwell_accumulator_ms += deltaMs;
        } else if (this.current_confidence >= this.conf_low && this.current_confidence < this.conf_high) {
            this.dwell_accumulator_ms = Math.max(0, this.dwell_accumulator_ms - 2 * deltaMs);
        } else if (gesture !== 'pointer_up' && gesture !== 'closed_fist') {
            this.dwell_accumulator_ms = Math.max(0, this.dwell_accumulator_ms - 2 * deltaMs);
        }

        // Transition to COMMIT
        if (this.dwell_accumulator_ms >= this.dwell_limit_commit_ms) {
            this.state = new StateCommit();
            this.dwell_accumulator_ms = 0;
        }
    }

    private handleReadyCoast() {
        // Snaplock on regain
        if (this.current_confidence >= this.conf_high) {
            this.state = new StateReady();
        }
    }

    private handleCommitPointer(gesture: string, deltaMs: number) {
        // Schmitt Trigger: Drop to COAST
        if (this.current_confidence < this.conf_low) {
            this.state = new StateCommitCoast();
            return;
        }

        // Leaky Bucket for RELEASE (ms-based, 2:1 leak ratio)
        if ((gesture === 'open_palm' || gesture === 'closed_fist') && this.current_confidence >= this.conf_high) {
            this.dwell_accumulator_ms += deltaMs;
            if (gesture === 'open_palm') {
                this.ready_bucket_ms += deltaMs;
                this.idle_bucket_ms = 0;
            } else {
                this.idle_bucket_ms += deltaMs;
                this.ready_bucket_ms = 0;
            }
        } else if (this.current_confidence >= this.conf_low && this.current_confidence < this.conf_high) {
            this.dwell_accumulator_ms = Math.max(0, this.dwell_accumulator_ms - 2 * deltaMs);
            this.ready_bucket_ms = Math.max(0, this.ready_bucket_ms - 2 * deltaMs);
            this.idle_bucket_ms = Math.max(0, this.idle_bucket_ms - 2 * deltaMs);
        } else if (gesture !== 'open_palm' && gesture !== 'closed_fist') {
            this.dwell_accumulator_ms = Math.max(0, this.dwell_accumulator_ms - 2 * deltaMs);
            this.ready_bucket_ms = Math.max(0, this.ready_bucket_ms - 2 * deltaMs);
            this.idle_bucket_ms = Math.max(0, this.idle_bucket_ms - 2 * deltaMs);
        }

        // Transition to READY or IDLE
        if (this.dwell_accumulator_ms >= this.dwell_limit_commit_ms) {
            if (this.ready_bucket_ms >= this.idle_bucket_ms) {
                this.state = new StateReady();
            } else {
                this.state = new StateIdle();
            }
            this.dwell_accumulator_ms = 0;
            this.ready_bucket_ms = 0;
            this.idle_bucket_ms = 0;
        }
    }

    private handleCommitCoast() {
        // Snaplock on regain
        if (this.current_confidence >= this.conf_high) {
            this.state = new StateCommit();
        }
    }

    /**
     * Returns true if the FSM is in a state that should trigger a W3C pointerdown/move (pinching)
     */
    public isPinching(): boolean {
        return this.state.type === 'COMMIT_POINTER' || this.state.type === 'COMMIT_COAST';
    }

    /**
     * Returns true if the FSM is currently in ANY coast state.
     * The caller can combine isPinching() && isCoasting() to detect COMMIT_COAST specifically —
     * the condition that produces ghost-draw teleport strokes on coast recovery (FSM-V5).
     */
    public isCoasting(): boolean {
        return this.state.type === 'IDLE_COAST' || this.state.type === 'READY_COAST' || this.state.type === 'COMMIT_COAST';
    }

    /**
     * Force the FSM into a coasting state (e.g., due to stillness)
     */
    public forceCoast() {
        if (this.state.type === 'IDLE') this.state = new StateIdleCoast();
        else if (this.state.type === 'READY') this.state = new StateReadyCoast();
        else if (this.state.type === 'COMMIT_POINTER') this.state = new StateCommitCoast();
    }
}
