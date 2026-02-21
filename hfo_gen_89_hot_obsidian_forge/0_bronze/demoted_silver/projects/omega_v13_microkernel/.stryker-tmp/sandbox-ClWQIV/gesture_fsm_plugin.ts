// @ts-nocheck
import { GestureFSM } from './gesture_fsm';
import { RawHandData } from './gesture_bridge';
import { Plugin, PluginContext } from './plugin_supervisor';
import type { ConfigManager, ConfigMosaic } from './config_ui';

export class GestureFSMPlugin implements Plugin {
    public name = 'GestureFSMPlugin';
    public version = '1.0.0';
    private fsmInstances: Map<number, GestureFSM> = new Map();
    private context!: PluginContext;

    // Config wiring — resolved from PAL at init()
    private configManager?: ConfigManager;
    private configListener?: (cfg: ConfigMosaic) => void;
    /** Cached FSM config applied to new instances and on config-change. */
    private fsmConfig: { dwellReadyMs: number; dwellCommitMs: number; coastTimeoutMs: number } | null = null;

    /**
     * Last known position of each hand during COMMIT_COAST.  Used by the velocity
     * teleport gate (FSM-V5 fix) to detect coast-recovery jumps > TELEPORT_THRESHOLD.
     * Keyed by handId; cleared when the hand leaves coast state.
     */
    private coastPositions: Map<number, { x: number; y: number }> = new Map();

    /** Squared distance threshold above which a coast-recovery transition is considered
     *  a teleport and a synthetic pointerup is injected before the recovery pointerdown.
     *  0.15 normalised units = 15% of viewport width.  Tunable via PAL key 'TeleportThresholdSq'. */
    private readonly TELEPORT_THRESHOLD_SQ = 0.15 * 0.15;

    // Stable bound references — required so unsubscribe() can remove the exact same fn object.
    // Using .bind(this) inline in subscribe() creates an anonymous fn that can never be removed.
    // Scenario: Given GestureFSMPlugin destroyed, Then FRAME_PROCESSED/STILLNESS_DETECTED listeners
    //           are removed from the bus (no zombie callbacks on a dead plugin instance).
    private readonly boundOnFrameProcessed: (data: any) => void;
    private readonly boundOnStillnessDetected: (data: any) => void;

    constructor() {
        this.boundOnFrameProcessed    = this.onFrameProcessed.bind(this);
        this.boundOnStillnessDetected = this.onStillnessDetected.bind(this);
    }

    public init(context: PluginContext): void {
        this.context = context;
        this.context.eventBus.subscribe('FRAME_PROCESSED',    this.boundOnFrameProcessed);
        this.context.eventBus.subscribe('STILLNESS_DETECTED', this.boundOnStillnessDetected);

        // Wire ConfigManager from PAL so dwell thresholds are hot-swappable
        const cm = context.pal.resolve<ConfigManager>('ConfigManager');
        if (cm) {
            this.configManager = cm;
            this.configListener = (cfg: ConfigMosaic) => {
                this.fsmConfig = {
                    dwellReadyMs:   cfg.fsm_dwell_ready,
                    dwellCommitMs:  cfg.fsm_dwell_commit,
                    coastTimeoutMs: cfg.fsm_coast_timeout_ms,
                };
                // Hot-update all live FSM instances
                for (const fsm of this.fsmInstances.values()) {
                    fsm.configure(this.fsmConfig);
                }
            };
            // subscribe() fires immediately with the current config
            cm.subscribe(this.configListener);
        }
    }

    public start(): void {
        console.log('[GestureFSMPlugin] Started');
    }

    public stop(): void {
        if (this.configManager && this.configListener) {
            this.configManager.unsubscribe(this.configListener);
        }
        console.log('[GestureFSMPlugin] Stopped');
    }

    public destroy(): void {
        if (this.context?.eventBus) {
            this.context.eventBus.unsubscribe('FRAME_PROCESSED',    this.boundOnFrameProcessed);
            this.context.eventBus.unsubscribe('STILLNESS_DETECTED', this.boundOnStillnessDetected);
        }
        this.fsmInstances.clear();
    }

    private onStillnessDetected(data: { handId: number }) {
        const fsm = this.fsmInstances.get(data.handId);
        if (fsm) {
            fsm.forceCoast();
        }
    }

    private onFrameProcessed(hands: RawHandData[]) {
        const currentHandIds = new Set<number>();

        for (const hand of hands) {
            currentHandIds.add(hand.handId);

            if (!this.fsmInstances.has(hand.handId)) {
                const newFsm = new GestureFSM();
                if (this.fsmConfig) newFsm.configure(this.fsmConfig);
                this.fsmInstances.set(hand.handId, newFsm);
            }

            const fsm = this.fsmInstances.get(hand.handId)!;
            const previousState = fsm.state;

            // Capture pre-frame coast/pinch status for FSM-V5 velocity teleport gate
            const prevIsPinching = fsm.isPinching();
            const prevIsCoasting = fsm.isCoasting();
            const prevCoastPos   = this.coastPositions.get(hand.handId);

            // Use caller-supplied timestamp when available (e.g. Playwright test harness)
            // to keep dwell framerate-independent regardless of actual MediaPipe fps.
            const nowMs = hand.frameTimeMs ?? performance.now();
            fsm.processFrame(hand.gesture, hand.confidence, hand.x, hand.y, nowMs);
            const currentState = fsm.state;

            if (previousState !== currentState) {
                this.context.eventBus.publish('STATE_CHANGE', {
                    handId: hand.handId,
                    previousState: previousState.type,
                    currentState:  currentState.type
                });
            }

            const isPinching = fsm.isPinching();
            const isCoasting = fsm.isCoasting();

            // ── FSM-V5 velocity teleport gate ─────────────────────────────────────────────
            // COMMIT_COAST → COMMIT_POINTER recovery with a large position jump = ghost stroke.
            // Inject a synthetic pointerup at the *last coast position* so W3CPointerFabric
            // fires pointerup before the recovered pointerdown at the new position.
            if (prevIsPinching && prevIsCoasting && isPinching && !isCoasting && prevCoastPos) {
                const dx = hand.x - prevCoastPos.x;
                const dy = hand.y - prevCoastPos.y;
                const threshold = this.context.pal.resolve<number>('TeleportThresholdSq') ?? this.TELEPORT_THRESHOLD_SQ;
                if ((dx * dx + dy * dy) > threshold) {
                    // Emit synthetic pointerup at the last safe coast position to break the stroke
                    this.context.eventBus.publish('POINTER_UPDATE', {
                        handId:       hand.handId,
                        x:            prevCoastPos.x,
                        y:            prevCoastPos.y,
                        isPinching:   false, // forces pointerup in W3CPointerFabric
                        gesture:      hand.gesture,
                        confidence:   hand.confidence,
                        rawLandmarks: undefined,
                    });
                }
            }

            // Track the hand's position while it is in COMMIT_COAST so the gate above
            // always has a valid “last safe” reference on recovery.
            if (isPinching && isCoasting) {
                this.coastPositions.set(hand.handId, { x: hand.x, y: hand.y });
            } else {
                this.coastPositions.delete(hand.handId);
            }

            this.context.eventBus.publish('POINTER_UPDATE', {
                handId: hand.handId,
                x: hand.x,
                y: hand.y,
                isPinching,
                gesture: hand.gesture,
                confidence: hand.confidence,
                rawLandmarks: hand.rawLandmarks
            });
        }

        for (const [handId, fsm] of this.fsmInstances.entries()) {
            if (!currentHandIds.has(handId)) {
                fsm.processFrame('none', 0.0, -1, -1, performance.now());

                if (fsm.state.type === 'IDLE') {
                    this.context.eventBus.publish('POINTER_COAST', { handId, isPinching: false, destroy: true });
                    this.fsmInstances.delete(handId);
                } else {
                    const isPinching = fsm.isPinching();
                    this.context.eventBus.publish('POINTER_COAST', { handId, isPinching, destroy: false });
                }
            }
        }
    }

    public getHandState(handId: number): string | null {
        const fsm = this.fsmInstances.get(handId);
        return fsm ? fsm.state.type : null;
    }
}
