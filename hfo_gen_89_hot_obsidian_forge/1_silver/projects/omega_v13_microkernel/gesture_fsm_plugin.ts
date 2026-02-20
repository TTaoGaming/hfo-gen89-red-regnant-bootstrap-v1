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

    constructor() {
        // We'll subscribe in init instead of constructor
    }

    public init(context: PluginContext): void {
        this.context = context;
        this.context.eventBus.subscribe('FRAME_PROCESSED', this.onFrameProcessed.bind(this));
        this.context.eventBus.subscribe('STILLNESS_DETECTED', this.onStillnessDetected.bind(this));

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
            // Use caller-supplied timestamp when available (e.g. Playwright test harness)
            // to keep dwell framerate-independent regardless of actual MediaPipe fps.
            const nowMs = hand.frameTimeMs ?? performance.now();
            fsm.processFrame(hand.gesture, hand.confidence, hand.x, hand.y, nowMs);
            const currentState = fsm.state;

            if (previousState !== currentState) {
                this.context.eventBus.publish('STATE_CHANGE', {
                    handId: hand.handId,
                    previousState,
                    currentState
                });
            }

            const isPinching = fsm.isPinching();

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

                if (fsm.state === 'IDLE') {
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
        return fsm ? fsm.state : null;
    }
}
