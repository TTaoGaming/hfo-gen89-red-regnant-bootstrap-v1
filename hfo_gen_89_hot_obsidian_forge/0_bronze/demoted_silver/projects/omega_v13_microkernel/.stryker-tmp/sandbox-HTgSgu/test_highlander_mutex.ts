// @ts-nocheck
import { asRaw } from './types.js';
/**
 * test_highlander_mutex.ts
 * 
 * JSON injection test for the HighlanderMutexAdapter.
 * Verifies that the adapter correctly enforces single-touch semantics
 * on a multi-touch substrate, handling hover dropping and commit locking.
 */

import { HighlanderMutexAdapter } from './highlander_mutex_adapter';
import { RawHandData } from './gesture_bridge';

function runTest(name: string, config: any, frames: RawHandData[][]) {
    console.log(`\n--- Running Test: ${name} ---`);
    const adapter = new HighlanderMutexAdapter(config);

    frames.forEach((frame, index) => {
        const filtered = adapter.filterFrame(frame);
        const activeId = adapter.getActiveHandId();
        
        console.log(`Frame ${index}: Input [${frame.map(h => h.handId).join(',')}] -> Output [${filtered.map(h => h.handId).join(',')}] | Active Lock: ${activeId}`);
    });
}

// Test 1: Basic First-Come, First-Served (Lock on Sight)
const frames1: RawHandData[][] = [
    [{ handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'open_palm', confidence: 0.9 }], // Hand 1 appears
    [
        { handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'open_palm', confidence: 0.9 },
        { handId: 2, x: asRaw(0.5), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }  // Hand 2 appears (should be ignored)
    ],
    [{ handId: 2, x: asRaw(0.5), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }], // Hand 1 disappears, Hand 2 takes over
    [] // All hands disappear
];

runTest('Basic First-Come, First-Served (Lock on Sight)', { lockOnCommitOnly: false, dropHoverEvents: false }, frames1);

// Test 2: Lock on Commit Only
const frames2: RawHandData[][] = [
    [
        { handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'open_palm', confidence: 0.9 }, // Hand 1 hovering
        { handId: 2, x: asRaw(0.5), y: asRaw(0.5), gesture: 'open_palm', confidence: 0.9 }  // Hand 2 hovering
    ],
    [
        { handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'open_palm', confidence: 0.9 }, // Hand 1 still hovering
        { handId: 2, x: asRaw(0.5), y: asRaw(0.5), gesture: 'pointer_up', confidence: 0.9 } // Hand 2 commits! (Should acquire lock)
    ],
    [
        { handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'pointer_up', confidence: 0.9 }, // Hand 1 tries to commit (Should be ignored)
        { handId: 2, x: asRaw(0.5), y: asRaw(0.5), gesture: 'pointer_up', confidence: 0.9 }  // Hand 2 still committing
    ],
    [{ handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'pointer_up', confidence: 0.9 }] // Hand 2 disappears, Hand 1 takes over
];

runTest('Lock on Commit Only', { lockOnCommitOnly: true, dropHoverEvents: false }, frames2);

// Test 3: Drop Hover Events
const frames3: RawHandData[][] = [
    [{ handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'open_palm', confidence: 0.9 }], // Hand 1 hovering (Should be dropped, but lock acquired)
    [{ handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'pointer_up', confidence: 0.9 }], // Hand 1 commits (Should be passed through)
    [{ handId: 1, x: asRaw(0.1), y: asRaw(0.1), gesture: 'open_palm', confidence: 0.9 }]  // Hand 1 hovering again (Should be dropped)
];

runTest('Drop Hover Events (Lock on Sight)', { lockOnCommitOnly: false, dropHoverEvents: true }, frames3);
