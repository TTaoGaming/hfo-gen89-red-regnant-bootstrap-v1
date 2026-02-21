/**
 * gesture_bridge.ts
 *
 * The N-Hand Gesture Bridge.
 * Connects raw multi-touch tracking data (e.g., MediaPipe) to the W3C Pointer Fabric.
 * Spawns and manages an independent GestureFSM for each detected hand.
 */
// @ts-nocheck


import { HighlanderMutexAdapter } from './highlander_mutex_adapter';
// ATDD-ARCH-001: globalEventBus singleton deleted — bus injected via constructor DI
import { EventBus } from './event_bus';
import type { GestureEventPayload } from './mediapipe_gesture';
import type { RawHandData } from './hand_types';
import { asRaw } from './types.js';

// RawHandData is defined in hand_types.ts (no circular-dep risk).
// Re-exported here so existing consumers (e.g. stillness_monitor_plugin.ts)
// can keep their `import { RawHandData } from './gesture_bridge'` import unchanged.
export type { RawHandData, LandmarkPoint } from './hand_types';

export class GestureBridge {
    /** EventBus injected at construction — never a global singleton (ATDD-ARCH-001). */
    private readonly bus: EventBus;
    private mutexAdapter?: HighlanderMutexAdapter;

    // ATDD-ARCH-001: bus is the first required arg — no ?? fallback to a disconnected private bus
    constructor(bus: EventBus, mutexAdapter?: HighlanderMutexAdapter) {
        this.bus = bus;
        this.mutexAdapter = mutexAdapter;
    }

    /**
     * Process a frame of raw hand tracking data.
     * This should be called every frame (e.g., 60fps) with the currently detected hands.
     * 
     * @param hands Array of detected hands in the current frame
     */
    public processFrame(hands: RawHandData[]) {
        // Apply the Highlander Mutex if configured (enforces single-touch)
        const processedHands = this.mutexAdapter ? this.mutexAdapter.filterFrame(hands) : hands;

        // ATDD-ARCH-001: publish on injected bus, never a global singleton
        this.bus.publish('FRAME_PROCESSED', processedHands);
    }

    /**
     * Consume a raw MediaPipe payload and translate it into the internal RawHandData format.
     * This acts as the adapter between the noisy input harness and the FSM logic.
     */
    public consumeMediaPipePayload(payload: GestureEventPayload) {
        const translatedHands: RawHandData[] = payload.hands.map(hand => ({
            handId: hand.id,
            x: asRaw(hand.pointerX),
            y: asRaw(hand.pointerY),
            // Simple heuristic translation: if pinching, it's a closed fist (or pointer down), else open palm
            gesture: hand.isPinching ? 'closed_fist' : 'open_palm',
            confidence: 1.0 // MediaPipe tasks-vision doesn't expose per-landmark confidence easily in this mock, assume 1.0 for now
        }));

        this.processFrame(translatedHands);
    }
}
