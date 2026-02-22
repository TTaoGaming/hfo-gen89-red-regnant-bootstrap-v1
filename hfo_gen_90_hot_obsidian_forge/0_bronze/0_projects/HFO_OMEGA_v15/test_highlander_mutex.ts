/**
 * test_highlander_mutex.ts  (rewritten as Jest)
 *
 * Mutation-hardened Jest tests for HighlanderMutexAdapter.
 * "There can be only one."
 *
 * Replaces the original console.log script runner.
 *
 * Coverage targets (mutation kills required):
 *   - activeHandId = null on empty frame (not keeps previous)
 *   - activeHandId = hand.handId on lock acquisition
 *   - sortedHands by handId ascending (not descending)
 *   - isCommitting check: gesture === 'pointer_up' && confidence > 0.8
 *   - lockOnCommitOnly branch
 *   - dropHoverEvents branch
 *   - processActiveHand: isCommitting gate
 *   - release() zeroes activeHandId
 *
 * HFO Omega v15 | Stryker receipt required
 */

import { HighlanderMutexAdapter } from './highlander_mutex_adapter';
import type { RawHandData } from './hand_types';

// --- Helper ---
function makeHand(handId: number, gesture = 'open_palm', confidence = 0.9): RawHandData {
    return { handId, x: 0.1 as any, y: 0.1 as any, gesture, confidence };
}

// --- Tests ---

describe('HighlanderMutexAdapter  empty frame', () => {
    it('returns empty array on empty frame', () => {
        const a = new HighlanderMutexAdapter();
        expect(a.filterFrame([])).toEqual([]);
    });

    it('releases mutex (activeHandId = null) on empty frame', () => {
        const a = new HighlanderMutexAdapter();
        a.filterFrame([makeHand(1)]);
        a.filterFrame([]);
        expect(a.getActiveHandId()).toBeNull();
    });

    it('getActiveHandId starts as null', () => {
        const a = new HighlanderMutexAdapter();
        expect(a.getActiveHandId()).toBeNull();
    });
});

describe('HighlanderMutexAdapter  lock on first sight (default config)', () => {
    let a: HighlanderMutexAdapter;

    beforeEach(() => {
        a = new HighlanderMutexAdapter({ lockOnCommitOnly: false, dropHoverEvents: false });
    });

    it('locks onto the first hand immediately', () => {
        a.filterFrame([makeHand(1)]);
        expect(a.getActiveHandId()).toBe(1);
    });

    it('returns only the locked hand when two appear simultaneously', () => {
        const result = a.filterFrame([makeHand(2), makeHand(1)]);
        expect(result).toHaveLength(1);
        expect(result[0]!.handId).toBe(1);
    });

    it('deterministic: lower handId wins when multiple appear together (ascending sort)', () => {
        const result = a.filterFrame([makeHand(5), makeHand(3), makeHand(1)]);
        expect(result[0]!.handId).toBe(1);
    });

    it('ignores second hand once first is locked', () => {
        a.filterFrame([makeHand(1)]);
        const result = a.filterFrame([makeHand(1), makeHand(2)]);
        expect(result).toHaveLength(1);
        expect(result[0]!.handId).toBe(1);
    });

    it('releases lock when active hand disappears, second hand takes over', () => {
        a.filterFrame([makeHand(1)]);
        const result = a.filterFrame([makeHand(2)]);
        expect(result).toHaveLength(1);
        expect(result[0]!.handId).toBe(2);
        expect(a.getActiveHandId()).toBe(2);
    });
});

describe('HighlanderMutexAdapter  lockOnCommitOnly', () => {
    let a: HighlanderMutexAdapter;

    beforeEach(() => {
        a = new HighlanderMutexAdapter({ lockOnCommitOnly: true, dropHoverEvents: false });
    });

    it('does NOT lock when hands are only hovering', () => {
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        expect(a.getActiveHandId()).toBeNull();
    });

    it('returns empty while no hand commits', () => {
        const result = a.filterFrame([makeHand(1, 'open_palm', 0.9), makeHand(2, 'open_palm', 0.9)]);
        expect(result).toHaveLength(0);
    });

    it('locks when a hand commits (pointer_up + confidence > 0.8)', () => {
        a.filterFrame([makeHand(1, 'pointer_up', 0.9)]);
        expect(a.getActiveHandId()).toBe(1);
    });

    it('first committing hand wins, hoverers ignored', () => {
        a.filterFrame([makeHand(1, 'open_palm', 0.9), makeHand(2, 'pointer_up', 0.9)]);
        expect(a.getActiveHandId()).toBe(2);
    });

    it('does NOT lock at confidence exactly 0.8 (must be strictly > 0.8)', () => {
        a.filterFrame([makeHand(1, 'pointer_up', 0.8)]);
        expect(a.getActiveHandId()).toBeNull();
    });

    it('locks at confidence 0.81 (strictly > 0.8)', () => {
        a.filterFrame([makeHand(1, 'pointer_up', 0.81)]);
        expect(a.getActiveHandId()).toBe(1);
    });

    it('does NOT lock on closed_fist even at high confidence', () => {
        a.filterFrame([makeHand(1, 'closed_fist', 0.99)]);
        expect(a.getActiveHandId()).toBeNull();
    });

    it('returns the committing hand in the result', () => {
        const result = a.filterFrame([makeHand(1, 'pointer_up', 0.9)]);
        expect(result).toHaveLength(1);
        expect(result[0]!.handId).toBe(1);
    });
});

describe('HighlanderMutexAdapter  dropHoverEvents', () => {
    let a: HighlanderMutexAdapter;

    beforeEach(() => {
        a = new HighlanderMutexAdapter({ lockOnCommitOnly: false, dropHoverEvents: true });
    });

    it('acquires lock on first hand (lock-on-sight)', () => {
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        expect(a.getActiveHandId()).toBe(1);
    });

    it('drops hover events (returns empty array)', () => {
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        const result = a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        expect(result).toHaveLength(0);
    });

    it('passes through commit events', () => {
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        const result = a.filterFrame([makeHand(1, 'pointer_up', 0.9)]);
        expect(result).toHaveLength(1);
        expect(result[0]!.handId).toBe(1);
    });

    it('lock is retained even when hover is dropped', () => {
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        expect(a.getActiveHandId()).toBe(1);
    });

    it('drops commit with low confidence (confidence <= 0.8)', () => {
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        const result = a.filterFrame([makeHand(1, 'pointer_up', 0.5)]);
        expect(result).toHaveLength(0);
    });
});

describe('HighlanderMutexAdapter  release()', () => {
    it('release() sets activeHandId to null', () => {
        const a = new HighlanderMutexAdapter();
        a.filterFrame([makeHand(1)]);
        expect(a.getActiveHandId()).toBe(1);
        a.release();
        expect(a.getActiveHandId()).toBeNull();
    });

    it('release() on already-null mutex is safe', () => {
        const a = new HighlanderMutexAdapter();
        expect(() => a.release()).not.toThrow();
        expect(a.getActiveHandId()).toBeNull();
    });

    it('after release, next frame acquires new lock', () => {
        const a = new HighlanderMutexAdapter();
        a.filterFrame([makeHand(1)]);
        a.release();
        a.filterFrame([makeHand(2)]);
        expect(a.getActiveHandId()).toBe(2);
    });
});

describe('HighlanderMutexAdapter  default config fallbacks', () => {
    it('partial config: lockOnCommitOnly defaults to false (lock on sight)', () => {
        const a = new HighlanderMutexAdapter({});
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        expect(a.getActiveHandId()).toBe(1);
    });

    it('partial config: dropHoverEvents defaults to false (hover not dropped)', () => {
        const a = new HighlanderMutexAdapter({});
        a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        const result = a.filterFrame([makeHand(1, 'open_palm', 0.9)]);
        expect(result).toHaveLength(1);
    });

    it('no-arg constructor uses safe defaults', () => {
        const a = new HighlanderMutexAdapter();
        a.filterFrame([makeHand(1)]);
        expect(a.getActiveHandId()).toBe(1);
    });
});
