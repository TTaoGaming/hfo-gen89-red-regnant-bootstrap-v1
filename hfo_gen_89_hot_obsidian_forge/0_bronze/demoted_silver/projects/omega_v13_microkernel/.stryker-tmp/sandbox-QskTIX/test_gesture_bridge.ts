// @ts-nocheck
import { asRaw } from './types.js';
/**
 * test_gesture_bridge.ts
 * 
 * A test script to validate the correct-by-construction architecture of the 
 * N-Hand Gesture Bridge, including multi-touch and the deadman switch (stillness coast).
 */

import { GestureBridge, RawHandData } from './gesture_bridge';
import { EventBus } from './event_bus';
import { W3CPointerFabric } from './w3c_pointer_fabric';
import { HighlanderMutexAdapter } from './highlander_mutex_adapter';
import { GestureFSMPlugin } from './gesture_fsm_plugin';
import { StillnessMonitorPlugin } from './stillness_monitor_plugin';
import type { GestureEventPayload } from './mediapipe_gesture';

// Mock the DOM environment for testing
(global as any).window = {
    innerWidth: 1920,
    innerHeight: 1080,
    performance: { now: () => Date.now() }
};
(global as any).document = {
    elementFromPoint: (x: number, y: number) => ({ tagName: 'DIV', dispatchEvent: (e: any) => console.log(`[DOM] Dispatched ${e.type} to element at ${x},${y}`) })
};
(global as any).PointerEvent = class {
    type: string;
    constructor(type: string, init: any) {
        this.type = type;
        Object.assign(this, init);
    }
};

// ATDD-ARCH-001: EventBus injected — bridge and all consumers share the same instance
const testBus = new EventBus();
// Initialize the fabric and bridge
const fabric = new W3CPointerFabric({ dispatchToIframes: false });
const bridge = new GestureBridge(testBus); // ATDD-ARCH-001: bus first, mutexAdapter=none
const fsmPlugin = new GestureFSMPlugin();
const stillnessPlugin = new StillnessMonitorPlugin();

console.log("--- TEST 1: Multi-Touch (2 Hands) ---");

// Frame 1: Two hands appear, both open palm (high confidence)
console.log("Frame 1: Two hands appear (open_palm)");
bridge.processFrame([
    { handId: 0, x: asRaw(0.2), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 },
    { handId: 1, x: asRaw(0.8), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }
]);
console.log(`Hand 0 State: ${fsmPlugin.getHandState(0)}`); // Should be IDLE (bucket filling)
console.log(`Hand 1 State: ${fsmPlugin.getHandState(1)}`); // Should be IDLE (bucket filling)

// Fast forward 15 frames to fill the READY bucket
console.log("\nFast forwarding 15 frames...");
for (let i = 0; i < 15; i++) {
    bridge.processFrame([
        { handId: 0, x: asRaw(0.2), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 },
        { handId: 1, x: asRaw(0.8), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }
    ]);
}
console.log(`Hand 0 State: ${fsmPlugin.getHandState(0)}`); // Should be READY
console.log(`Hand 1 State: ${fsmPlugin.getHandState(1)}`); // Should be READY

// Frame 17: Hand 0 commits (pointer_up), Hand 1 stays ready
console.log("\nFrame 17: Hand 0 commits (pointer_up)");
bridge.processFrame([
    { handId: 0, x: asRaw(0.2), y: asRaw(0.5), gesture: 'pointer_up', confidence: 0.9 },
    { handId: 1, x: asRaw(0.8), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }
]);

// Fast forward 10 frames to fill the COMMIT bucket for Hand 0
console.log("\nFast forwarding 10 frames...");
for (let i = 0; i < 10; i++) {
    bridge.processFrame([
        { handId: 0, x: asRaw(0.2), y: asRaw(0.5), gesture: 'pointer_up', confidence: 0.9 },
        { handId: 1, x: asRaw(0.8), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }
    ]);
}
console.log(`Hand 0 State: ${fsmPlugin.getHandState(0)}`); // Should be COMMIT_POINTER
console.log(`Hand 1 State: ${fsmPlugin.getHandState(1)}`); // Should be READY

console.log("\n--- TEST 2: Deadman Switch (Stillness Coast) ---");

// Hand 1 stays perfectly still for 3600 frames (1 minute at 60fps)
console.log("Hand 1 stays perfectly still for 3600 frames...");
for (let i = 0; i < 3600; i++) {
    bridge.processFrame([
        { handId: 1, x: asRaw(0.8), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }
    ]);
}
console.log(`Hand 1 State: ${fsmPlugin.getHandState(1)}`); // Should be READY_COAST (deadman switch triggered)

// Hand 1 moves slightly, should snaplock back to READY
console.log("\nHand 1 moves slightly...");
bridge.processFrame([
    { handId: 1, x: asRaw(0.81), y: asRaw(0.51), gesture: 'open_palm', confidence: 0.9 }
]);
console.log(`Hand 1 State: ${fsmPlugin.getHandState(1)}`); // Should be READY

console.log("\n--- TEST 3: Hand Loss Cleanup ---");

// Hand 1 disappears
console.log("Hand 1 disappears for 30 frames...");
for (let i = 0; i < 30; i++) {
    bridge.processFrame([]); // Empty array = no hands detected
}
console.log(`Hand 1 State: ${fsmPlugin.getHandState(1)}`); // Should be null (cleaned up)

console.log("\n--- TEST 4: Highlander Mutex Adapter Integration ---");
const mutexAdapter = new HighlanderMutexAdapter({ lockOnCommitOnly: true });
const mutexBridge = new GestureBridge(testBus, mutexAdapter); // ATDD-ARCH-001: bus first

const mutexFrames: RawHandData[][] = [
    // Frame 0: Both hands hover (should be ignored by lockOnCommitOnly)
    [
        { handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'open_palm', confidence: 0.9 },
        { handId: 2, x: asRaw(0.5), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }
    ],
    // Frame 1: Hand 2 commits (acquires lock)
    [
        { handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'open_palm', confidence: 0.9 },
        { handId: 2, x: asRaw(0.5), y: asRaw(0.5), gesture: 'pointer_up', confidence: 0.9 }
    ],
    // Frame 2: Hand 1 tries to commit (ignored because Hand 2 has lock)
    [
        { handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'pointer_up', confidence: 0.9 },
        { handId: 2, x: asRaw(0.5), y: asRaw(0.5), gesture: 'pointer_up', confidence: 0.9 }
    ]
];

mutexFrames.forEach((frame, index) => {
    console.log(`\nProcessing Mutex Frame ${index}...`);
    mutexBridge.processFrame(frame);
    console.log(`Hand 1 State: ${fsmPlugin.getHandState(1)}`);
    console.log(`Hand 2 State: ${fsmPlugin.getHandState(2)}`);
});

console.log("\n--- TEST 5: MediaPipe Payload Integration ---");
const mediaPipePayload: GestureEventPayload = {
    timestamp: 12345,
    hands: [
        {
            id: 0,
            pointerX: 0.25,
            pointerY: 0.75,
            isPinching: true,
            rawLandmarks: [] // Mock empty array for test
        },
        {
            id: 1,
            pointerX: 0.85,
            pointerY: 0.25,
            isPinching: false,
            rawLandmarks: [] // Mock empty array for test
        }
    ]
};

console.log("Consuming MediaPipe Payload...");
bridge.consumeMediaPipePayload(mediaPipePayload);
console.log(`Hand 0 State: ${fsmPlugin.getHandState(0)}`); // Should be processing a 'closed_fist'
console.log(`Hand 1 State: ${fsmPlugin.getHandState(1)}`); // Should be processing an 'open_palm'
