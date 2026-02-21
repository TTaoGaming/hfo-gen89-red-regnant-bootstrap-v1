// @ts-nocheck
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
    /** Bound once in constructor — same reference for subscribe() AND unsubscribe() (ARCH-ZOMBIE guard). */
    private readonly boundHandler: (hands: RawHandData[]) => void;
    private active = false;

    constructor() {
        // Binding in the constructor guarantees a single stable function identity.
        // Using .bind(this) inline in subscribe() would create an anonymous function
        // that unsubscribe() can never locate — the classic zombie listener.
        this.boundHandler = this.onFrameProcessed.bind(this);
    }

    public init(context: PluginContext): void {
        this.context = context;
    }

    public start(): void {
        this.context.eventBus.subscribe('FRAME_PROCESSED', this.boundHandler);
        this.active = true;
        console.log('[StillnessMonitorPlugin] Started');
    }

    public stop(): void {
        this.context.eventBus.unsubscribe('FRAME_PROCESSED', this.boundHandler);
        this.active = false;
        console.log('[StillnessMonitorPlugin] Stopped');
    }

    public destroy(): void {
        // Defensive double-unsubscribe is safe — unsubscribe on an absent
        // handler is a no-op, so calling destroy() after stop() is fine.
        this.context.eventBus.unsubscribe('FRAME_PROCESSED', this.boundHandler);
        this.lastPositions.clear();
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
                // STILLNESS_DETECTED payload includes position so downstream consumers
                // (e.g. tldraw coasting) know which viewport coordinate went still.
                this.context.eventBus.publish('STILLNESS_DETECTED', {
                    handId: hand.handId,
                    x: state.x,
                    y: state.y,
                });
            }
        }

        for (const handId of this.lastPositions.keys()) {
            if (!currentHandIds.has(handId)) {
                this.lastPositions.delete(handId);
            }
        }
    }
}

