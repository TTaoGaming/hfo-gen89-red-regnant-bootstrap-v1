import { Plugin, PluginContext } from './plugin_supervisor';
import type { RawHandData } from './gesture_bridge';

export class StillnessMonitorPlugin implements Plugin {
    public readonly name = 'StillnessMonitorPlugin';
    public readonly version = '1.0.0';

    private context!: PluginContext;
    private lastPositions: Map<number, { x: number, y: number, ticks: number }> = new Map();
    /** Writable so unit tests can override the default 1-minute threshold. */
    public stillness_timeout_limit = 3600; // 1 minute at 60fps
    private readonly stillness_threshold = 0.001;
    private boundHandler: ((hands: RawHandData[]) => void) | null = null;
    private active = false;

    public init(context: PluginContext): void {
        this.context = context;
        this.boundHandler = this.onFrameProcessed.bind(this);
    }

    public start(): void {
        if (this.boundHandler) {
            this.context.eventBus.subscribe('FRAME_PROCESSED', this.boundHandler);
            this.active = true;
        }
        console.log('[StillnessMonitorPlugin] Started');
    }

    public stop(): void {
        if (this.boundHandler) {
            this.context.eventBus.unsubscribe('FRAME_PROCESSED', this.boundHandler);
            this.active = false;
        }
        console.log('[StillnessMonitorPlugin] Stopped');
    }

    public destroy(): void {
        this.stop();
        this.lastPositions.clear();
        this.boundHandler = null;
    }

    private onFrameProcessed(hands: RawHandData[]) {
        if (!this.active) return;
        const currentHandIds = new Set<number>();

        for (const hand of hands) {
            currentHandIds.add(hand.handId);

            if (!this.lastPositions.has(hand.handId)) {
                this.lastPositions.set(hand.handId, { x: hand.x, y: hand.y, ticks: 0 });
                continue;
            }

            const state = this.lastPositions.get(hand.handId)!;
            const dx = hand.x - state.x;
            const dy = hand.y - state.y;
            const distSq = dx * dx + dy * dy;

            if (distSq < this.stillness_threshold * this.stillness_threshold) {
                state.ticks++;
            } else {
                state.ticks = 0;
            }

            state.x = hand.x;
            state.y = hand.y;

            if (state.ticks >= this.stillness_timeout_limit) {
                this.context.eventBus.publish('STILLNESS_DETECTED', { handId: hand.handId });
            }
        }

        for (const handId of this.lastPositions.keys()) {
            if (!currentHandIds.has(handId)) {
                this.lastPositions.delete(handId);
            }
        }
    }
}

