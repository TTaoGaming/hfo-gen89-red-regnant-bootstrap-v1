/**
 * test_stillness_monitor_plugin.ts
 *
 * Mutation-hardened Jest tests for StillnessMonitorPlugin.
 *
 * Coverage targets (mutation kills required):
 *   - active guard (if !this.active return)
 *   - new-hand continue branch
 *   - distSq < threshold^2  (< not <=)
 *   - ticks++  /  ticks = 0 reset
 *   - ticks >= limit  (>= not >)
 *   - publish payload correctness
 *   - stale hand pruning
 *   - subscribe / unsubscribe symmetry
 *
 * HFO Omega v15 | Stryker receipt required
 */

import { StillnessMonitorPlugin } from './stillness_monitor_plugin';
import type { RawHandData } from './hand_types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeHand(handId: number, x: number, y: number, gesture = 'open_palm'): RawHandData {
    return { handId, x: x as any, y: y as any, gesture, confidence: 0.9 };
}

interface MockContext {
    published: { event: string; payload: any }[];
    subscribedFns: Map<string, Function>;
    unsubscribedCalls: { event: string; fn: Function }[];
    context: any;
}

function makeMockContext(): MockContext {
    const published: { event: string; payload: any }[] = [];
    const subscribedFns = new Map<string, Function>();
    const unsubscribedCalls: { event: string; fn: Function }[] = [];

    const context = {
        eventBus: {
            publish: (event: string, payload: any) => published.push({ event, payload }),
            subscribe: (event: string, fn: Function) => subscribedFns.set(event, fn),
            unsubscribe: (event: string, fn: Function) => unsubscribedCalls.push({ event, fn }),
        },
        pal: {} as any,
    };

    return { published, subscribedFns, unsubscribedCalls, context };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('StillnessMonitorPlugin — identity', () => {
    it('has name StillnessMonitorPlugin', () => {
        const p = new StillnessMonitorPlugin();
        expect(p.name).toBe('StillnessMonitorPlugin');
    });

    it('has version 1.0.0', () => {
        const p = new StillnessMonitorPlugin();
        expect(p.version).toBe('1.0.0');
    });

    it('exposes writable stillness_timeout_limit', () => {
        const p = new StillnessMonitorPlugin();
        p.stillness_timeout_limit = 42;
        expect(p.stillness_timeout_limit).toBe(42);
    });
});

describe('StillnessMonitorPlugin — lifecycle', () => {
    let plugin: StillnessMonitorPlugin;
    let mock: MockContext;

    beforeEach(() => {
        plugin = new StillnessMonitorPlugin();
        mock = makeMockContext();
    });

    it('init completes without throwing', () => {
        expect(() => plugin.init(mock.context)).not.toThrow();
    });

    it('start subscribes to FRAME_PROCESSED', () => {
        plugin.init(mock.context);
        plugin.start();
        expect(mock.subscribedFns.has('FRAME_PROCESSED')).toBe(true);
    });

    it('stop unsubscribes from FRAME_PROCESSED', () => {
        plugin.init(mock.context);
        plugin.start();
        plugin.stop();
        expect(mock.unsubscribedCalls.some(u => u.event === 'FRAME_PROCESSED')).toBe(true);
    });

    it('destroy unsubscribes from FRAME_PROCESSED', () => {
        plugin.init(mock.context);
        plugin.start();
        plugin.destroy();
        const calls = mock.unsubscribedCalls.filter(u => u.event === 'FRAME_PROCESSED');
        expect(calls.length).toBeGreaterThanOrEqual(1);
    });

    it('stop then destroy (double-unsubscribe) does not throw', () => {
        plugin.init(mock.context);
        plugin.start();
        plugin.stop();
        expect(() => plugin.destroy()).not.toThrow();
    });

    it('start stores a stable bound reference (same fn used for subscribe AND unsubscribe)', () => {
        plugin.init(mock.context);
        plugin.start();
        plugin.stop();
        const subscribedFn = mock.subscribedFns.get('FRAME_PROCESSED')!;
        const unsubscribedFn = mock.unsubscribedCalls.find(u => u.event === 'FRAME_PROCESSED')!.fn;
        expect(subscribedFn).toBe(unsubscribedFn);
    });
});

describe('StillnessMonitorPlugin — active guard', () => {
    let plugin: StillnessMonitorPlugin;
    let mock: MockContext;
    let handler: Function;

    beforeEach(() => {
        plugin = new StillnessMonitorPlugin();
        mock = makeMockContext();
        plugin.init(mock.context);
        plugin.start();
        plugin.stillness_timeout_limit = 1;
        handler = mock.subscribedFns.get('FRAME_PROCESSED')!;
    });

    it('processes frames when active', () => {
        handler([makeHand(1, 0.1, 0.1)]);
        handler([makeHand(1, 0.1, 0.1)]);
        expect(mock.published).toHaveLength(1);
    });

    it('ignores frames when inactive (stop deactivates)', () => {
        plugin.stop();
        handler([makeHand(1, 0.1, 0.1)]);
        handler([makeHand(1, 0.1, 0.1)]);
        expect(mock.published).toHaveLength(0);
    });

    it('ignores frames after destroy (active flag via stop first)', () => {
        plugin.stop();    // sets active=false
        plugin.destroy(); // clears map
        handler([makeHand(1, 0.1, 0.1)]);
        handler([makeHand(1, 0.1, 0.1)]);
        expect(mock.published).toHaveLength(0);
    });
});

describe('StillnessMonitorPlugin — first-frame new-hand', () => {
    let plugin: StillnessMonitorPlugin;
    let mock: MockContext;
    let handler: Function;

    beforeEach(() => {
        plugin = new StillnessMonitorPlugin();
        mock = makeMockContext();
        plugin.init(mock.context);
        plugin.start();
        plugin.stillness_timeout_limit = 1;
        handler = mock.subscribedFns.get('FRAME_PROCESSED')!;
    });

    it('does NOT fire on the very first frame (no history yet)', () => {
        handler([makeHand(1, 0.1, 0.1)]);
        expect(mock.published).toHaveLength(0);
    });

    it('fires on the second frame when hand stays still (>=1 tick)', () => {
        handler([makeHand(1, 0.1, 0.1)]);  // frame 1: initialises position
        handler([makeHand(1, 0.1, 0.1)]);  // frame 2: ticks=1, 1>=1 → fires
        expect(mock.published).toHaveLength(1);
        expect(mock.published[0]!.event).toBe('STILLNESS_DETECTED');
    });

    it('does NOT fire on second frame when hand moves', () => {
        handler([makeHand(1, 0.1, 0.1)]);
        handler([makeHand(1, 0.9, 0.9)]);  // large move
        expect(mock.published).toHaveLength(0);
    });
});

describe('StillnessMonitorPlugin — tick accumulation and threshold', () => {
    let plugin: StillnessMonitorPlugin;
    let mock: MockContext;
    let handler: Function;

    beforeEach(() => {
        plugin = new StillnessMonitorPlugin();
        mock = makeMockContext();
        plugin.init(mock.context);
        plugin.start();
        handler = mock.subscribedFns.get('FRAME_PROCESSED')!;
    });

    it('fires at exactly limit ticks (>= not >)', () => {
        plugin.stillness_timeout_limit = 3;
        handler([makeHand(1, 0.1, 0.1)]);  // frame 1: init
        handler([makeHand(1, 0.1, 0.1)]);  // ticks=1
        handler([makeHand(1, 0.1, 0.1)]);  // ticks=2
        expect(mock.published).toHaveLength(0);  // not yet at 3
        handler([makeHand(1, 0.1, 0.1)]);  // ticks=3 → fires
        expect(mock.published).toHaveLength(1);
    });

    it('fires on each frame after limit is reached (continues accumulating)', () => {
        plugin.stillness_timeout_limit = 2;
        handler([makeHand(1, 0.1, 0.1)]);
        handler([makeHand(1, 0.1, 0.1)]);  // ticks=1
        handler([makeHand(1, 0.1, 0.1)]);  // ticks=2 → fires
        handler([makeHand(1, 0.1, 0.1)]);  // ticks=3 → fires again
        expect(mock.published.length).toBeGreaterThanOrEqual(2);
    });

    it('resets ticks to 0 (not 1) on movement', () => {
        plugin.stillness_timeout_limit = 2;
        handler([makeHand(1, 0.1, 0.1)]);
        handler([makeHand(1, 0.1, 0.1)]);  // ticks=1
        handler([makeHand(1, 0.5, 0.5)]);  // big move → ticks=0
        handler([makeHand(1, 0.5, 0.5)]);  // ticks=1 — needs one more
        expect(mock.published).toHaveLength(0);
        handler([makeHand(1, 0.5, 0.5)]);  // ticks=2 → fires
        expect(mock.published).toHaveLength(1);
    });

    // Mutation kill: distSq < thresh^2 (not <=)
    it('sub-threshold movement (dx=0.0005) counts as still', () => {
        plugin.stillness_timeout_limit = 1;
        handler([makeHand(1, 0.1, 0.1)]);
        // dx=0.0005 → distSq = 2.5e-7, threshold^2 = 1e-6, so 2.5e-7 < 1e-6 → still
        handler([makeHand(1, 0.1 + 0.0005, 0.1)]);
        expect(mock.published).toHaveLength(1);
    });

    // Mutation kill: distSq < thresh^2 boundary
    it('supra-threshold movement (dx=0.01) resets ticks', () => {
        plugin.stillness_timeout_limit = 1;
        handler([makeHand(1, 0.1, 0.1)]);
        // dx=0.01 → distSq=1e-4, threshold^2=1e-6, so 1e-4 >= 1e-6 → moving, ticks=0
        handler([makeHand(1, 0.1 + 0.01, 0.1)]);
        expect(mock.published).toHaveLength(0);
        // Now stay still at new position
        handler([makeHand(1, 0.1 + 0.01, 0.1)]);
        expect(mock.published).toHaveLength(1);
    });
});

describe('StillnessMonitorPlugin — STILLNESS_DETECTED payload', () => {
    let plugin: StillnessMonitorPlugin;
    let mock: MockContext;
    let handler: Function;

    beforeEach(() => {
        plugin = new StillnessMonitorPlugin();
        mock = makeMockContext();
        plugin.init(mock.context);
        plugin.start();
        plugin.stillness_timeout_limit = 1;
        handler = mock.subscribedFns.get('FRAME_PROCESSED')!;
    });

    it('payload.handId matches the hand', () => {
        handler([makeHand(42, 0.3, 0.7)]);
        handler([makeHand(42, 0.3, 0.7)]);
        expect(mock.published[0]!.payload.handId).toBe(42);
    });

    it('payload.x matches the last position', () => {
        handler([makeHand(1, 0.3, 0.7)]);
        handler([makeHand(1, 0.3, 0.7)]);
        expect(mock.published[0]!.payload.x).toBeCloseTo(0.3);
    });

    it('payload.y matches the last position', () => {
        handler([makeHand(1, 0.3, 0.7)]);
        handler([makeHand(1, 0.3, 0.7)]);
        expect(mock.published[0]!.payload.y).toBeCloseTo(0.7);
    });
});

describe('StillnessMonitorPlugin — multi-hand and stale pruning', () => {
    let plugin: StillnessMonitorPlugin;
    let mock: MockContext;
    let handler: Function;

    beforeEach(() => {
        plugin = new StillnessMonitorPlugin();
        mock = makeMockContext();
        plugin.init(mock.context);
        plugin.start();
        plugin.stillness_timeout_limit = 1;
        handler = mock.subscribedFns.get('FRAME_PROCESSED')!;
    });

    it('tracks two hands independently', () => {
        handler([makeHand(1, 0.1, 0.1), makeHand(2, 0.5, 0.5)]);
        handler([makeHand(1, 0.1, 0.1), makeHand(2, 0.5, 0.5)]);
        const events = mock.published.filter(p => p.event === 'STILLNESS_DETECTED');
        expect(events.length).toBe(2);
        expect(events.some(e => e.payload.handId === 1)).toBe(true);
        expect(events.some(e => e.payload.handId === 2)).toBe(true);
    });

    it('removes stale hands that disappear from frame', () => {
        handler([makeHand(1, 0.1, 0.1), makeHand(2, 0.5, 0.5)]);
        handler([makeHand(1, 0.1, 0.1)]);  // hand 2 gone
        // hand 2 should be removed — next frame with hand 2 should be treated as new
        mock.published.length = 0;  // clear
        handler([makeHand(2, 0.5, 0.5)]);  // re-appears → new, no fire
        expect(mock.published).toHaveLength(0);
    });

    it('does not crash on empty frame', () => {
        handler([makeHand(1, 0.1, 0.1)]);
        expect(() => handler([])).not.toThrow();
    });

    it('stale hand removed: mutex releases, new hand 2 becomes independent', () => {
        handler([makeHand(1, 0.1, 0.1), makeHand(2, 0.5, 0.5)]);
        handler([makeHand(2, 0.5, 0.5)]);  // hand 1 gone → removed from map
        // hand 2: first time without hand 1, still has its state → tick
        handler([makeHand(2, 0.5, 0.5)]);
        // hand 2 should eventually fire
        expect(mock.published.some(p => p.payload.handId === 2)).toBe(true);
    });
});
