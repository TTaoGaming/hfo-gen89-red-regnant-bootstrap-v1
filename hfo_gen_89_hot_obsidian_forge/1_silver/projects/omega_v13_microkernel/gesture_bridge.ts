/**
 * gesture_bridge.ts
 * 
 * The N-Hand Gesture Bridge.
 * This class connects raw multi-touch tracking data (e.g., MediaPipe) to the 
 * W3C Pointer Fabric. It dynamically spawns and manages an independent GestureFSM 
 * for each detected hand, ensuring true multi-touch support up to N hands.
 */

import { HighlanderMutexAdapter } from './highlander_mutex_adapter';
import { globalEventBus } from './event_bus';
import type { GestureEventPayload } from './mediapipe_gesture';

export interface RawHandData {
    handId: number;
    x: number; // Normalized X (0.0 to 1.0)
    y: number; // Normalized Y (0.0 to 1.0)
    gesture: string; // e.g., 'open_palm', 'closed_fist', 'pointer_up'
    confidence: number; // 0.0 to 1.0
    rawLandmarks?: any[]; // Optional raw landmarks for visualization
    /** Wall-clock timestamp in ms (performance.now()) for this hand's reading.
     *  If omitted the plugin falls back to performance.now() at dispatch time.
     *  Used to drive frame-rate-independent ms dwell in the FSM. */
    frameTimeMs?: number;
}

export class GestureBridge {
    private mutexAdapter?: HighlanderMutexAdapter;

    constructor(mutexAdapter?: HighlanderMutexAdapter) {
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

        // Emit the processed frame to the event bus
        globalEventBus.publish('FRAME_PROCESSED', processedHands);
    }

    /**
     * Consume a raw MediaPipe payload and translate it into the internal RawHandData format.
     * This acts as the adapter between the noisy input harness and the FSM logic.
     */
    public consumeMediaPipePayload(payload: GestureEventPayload) {
        const translatedHands: RawHandData[] = payload.hands.map(hand => ({
            handId: hand.id,
            x: hand.pointerX,
            y: hand.pointerY,
            // Simple heuristic translation: if pinching, it's a closed fist (or pointer down), else open palm
            gesture: hand.isPinching ? 'closed_fist' : 'open_palm',
            confidence: 1.0 // MediaPipe tasks-vision doesn't expose per-landmark confidence easily in this mock, assume 1.0 for now
        }));

        this.processFrame(translatedHands);
    }
}
