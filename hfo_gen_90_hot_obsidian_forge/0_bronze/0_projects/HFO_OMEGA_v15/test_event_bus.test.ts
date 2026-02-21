/**
 * test_event_bus.test.ts
 *
 * Comprehensive Jest test suite for EventBus<MicrokernelEvents>.
 * Target: 80-99% Stryker mutation score.
 *
 * Strategy: every branch (subscribe/unsubscribe/publish), every side-effect
 * guard, the ATDD-ARCH-001 trap, and the dead-letter dev warning are exercised
 * with explicit assertion values so mutations produce failing tests.
 *
 * HFO v15 tile: event_bus.ts | ATDD-ARCH-001
 * Session: PREY8 nonce E8CA8B | Gen90 bootstrap
 */

import { EventBus, globalEventBus, type MicrokernelEvents } from './event_bus';

// ─────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────

function makeBus(): EventBus<MicrokernelEvents> {
    return new EventBus<MicrokernelEvents>();
}

// ─────────────────────────────────────────────────────────────────
// EventBus — subscribe / publish
// ─────────────────────────────────────────────────────────────────

describe('EventBus — subscribe and publish', () => {
    it('calls subscribed handler when event is published', () => {
        const bus = makeBus();
        const calls: unknown[] = [];
        bus.subscribe('SETTINGS_TOGGLE', () => calls.push('called'));
        bus.publish('SETTINGS_TOGGLE', null);
        expect(calls).toHaveLength(1);
        expect(calls[0]).toBe('called');
    });

    it('delivers the payload to the subscriber', () => {
        const bus = makeBus();
        const received: unknown[] = [];
        bus.subscribe('SETTINGS_PANEL_STATE', (d) => received.push(d));
        bus.publish('SETTINGS_PANEL_STATE', { open: true });
        expect(received).toHaveLength(1);
        expect((received[0] as { open: boolean }).open).toBe(true);
    });

    it('delivers false in payload correctly (not treated as falsy no-call)', () => {
        const bus = makeBus();
        const received: unknown[] = [];
        bus.subscribe('SETTINGS_PANEL_STATE', (d) => received.push(d));
        bus.publish('SETTINGS_PANEL_STATE', { open: false });
        expect(received).toHaveLength(1);
        expect((received[0] as { open: boolean }).open).toBe(false);
    });

    it('delivers null payload for null-typed events', () => {
        const bus = makeBus();
        const calls: number[] = [];
        bus.subscribe('AUDIO_UNLOCK', () => calls.push(1));
        bus.publish('AUDIO_UNLOCK', null);
        expect(calls).toHaveLength(1);
    });

    it('calls ALL subscribers when multiple are registered for the same event', () => {
        const bus = makeBus();
        const order: number[] = [];
        bus.subscribe('SETTINGS_TOGGLE', () => order.push(1));
        bus.subscribe('SETTINGS_TOGGLE', () => order.push(2));
        bus.subscribe('SETTINGS_TOGGLE', () => order.push(3));
        bus.publish('SETTINGS_TOGGLE', null);
        expect(order).toEqual([1, 2, 3]);
    });

    it('does NOT call a handler for a different event', () => {
        const bus = makeBus();
        const calls: number[] = [];
        bus.subscribe('AUDIO_UNLOCK', () => calls.push(1));
        bus.publish('SETTINGS_TOGGLE', null);
        expect(calls).toHaveLength(0);
    });

    it('calls handler N times for N publishes', () => {
        const bus = makeBus();
        let count = 0;
        bus.subscribe('CAMERA_START_REQUESTED', () => count++);
        bus.publish('CAMERA_START_REQUESTED', null);
        bus.publish('CAMERA_START_REQUESTED', null);
        bus.publish('CAMERA_START_REQUESTED', null);
        expect(count).toBe(3);
    });

    it('does NOT throw when publishing to an event with no subscribers', () => {
        const bus = makeBus();
        expect(() => bus.publish('SETTINGS_TOGGLE', null)).not.toThrow();
    });

    it('delivers numeric payload for OVERSCAN_SCALE_CHANGE', () => {
        const bus = makeBus();
        const received: number[] = [];
        bus.subscribe('OVERSCAN_SCALE_CHANGE', (n) => received.push(n));
        bus.publish('OVERSCAN_SCALE_CHANGE', 1.5);
        expect(received).toEqual([1.5]);
    });

    it('delivers complex payload correctly for LAYER_OPACITY_CHANGE', () => {
        const bus = makeBus();
        const received: Array<{ id: string; opacity: number }> = [];
        bus.subscribe('LAYER_OPACITY_CHANGE', (d) => received.push(d));
        bus.publish('LAYER_OPACITY_CHANGE', { id: 'cam', opacity: 0.5 });
        expect(received[0]).toEqual({ id: 'cam', opacity: 0.5 });
    });
});

// ─────────────────────────────────────────────────────────────────
// EventBus — unsubscribe
// ─────────────────────────────────────────────────────────────────

describe('EventBus — unsubscribe', () => {
    it('stops calling the handler after unsubscribe', () => {
        const bus = makeBus();
        let count = 0;
        const handler = () => count++;
        bus.subscribe('SETTINGS_TOGGLE', handler);
        bus.publish('SETTINGS_TOGGLE', null);
        expect(count).toBe(1);

        bus.unsubscribe('SETTINGS_TOGGLE', handler);
        bus.publish('SETTINGS_TOGGLE', null);
        expect(count).toBe(1); // still 1 — not called again
    });

    it('does NOT remove other handlers for the same event when unsubscribing one', () => {
        const bus = makeBus();
        const calls1: number[] = [];
        const calls2: number[] = [];
        const h1 = () => calls1.push(1);
        const h2 = () => calls2.push(2);
        bus.subscribe('SETTINGS_TOGGLE', h1);
        bus.subscribe('SETTINGS_TOGGLE', h2);

        bus.unsubscribe('SETTINGS_TOGGLE', h1);
        bus.publish('SETTINGS_TOGGLE', null);

        expect(calls1).toHaveLength(0);
        expect(calls2).toHaveLength(1);
    });

    it('does NOT throw when unsubscribing from event with no registered handlers', () => {
        const bus = makeBus();
        const handler = () => {};
        expect(() => bus.unsubscribe('SETTINGS_TOGGLE', handler)).not.toThrow();
    });

    it('does NOT throw when unsubscribing a handler that is not registered', () => {
        const bus = makeBus();
        bus.subscribe('SETTINGS_TOGGLE', () => {});
        const unregistered = () => {};
        expect(() => bus.unsubscribe('SETTINGS_TOGGLE', unregistered)).not.toThrow();
    });

    it('can re-subscribe after unsubscribe and handler is called again', () => {
        const bus = makeBus();
        let count = 0;
        const handler = () => count++;

        bus.subscribe('SETTINGS_TOGGLE', handler);
        bus.publish('SETTINGS_TOGGLE', null);
        bus.unsubscribe('SETTINGS_TOGGLE', handler);
        bus.subscribe('SETTINGS_TOGGLE', handler);
        bus.publish('SETTINGS_TOGGLE', null);

        expect(count).toBe(2);
    });

    it('removes ONLY the first occurrence when the same handler is registered twice', () => {
        const bus = makeBus();
        let count = 0;
        const handler = () => count++;

        bus.subscribe('SETTINGS_TOGGLE', handler);
        bus.subscribe('SETTINGS_TOGGLE', handler);
        bus.unsubscribe('SETTINGS_TOGGLE', handler);
        bus.publish('SETTINGS_TOGGLE', null);

        // One handler remains — should be called once
        expect(count).toBe(1);
    });
});

// ─────────────────────────────────────────────────────────────────
// EventBus — internals (mutation kill: listeners Map)
// ─────────────────────────────────────────────────────────────────

describe('EventBus — internal listener Map state', () => {
    it('starts with no listeners', () => {
        const bus = makeBus();
        const internals = (bus as unknown as { listeners: Map<string, unknown[]> }).listeners;
        expect(internals.size).toBe(0);
    });

    it('adds a listener entry after subscribe', () => {
        const bus = makeBus();
        bus.subscribe('SETTINGS_TOGGLE', () => {});
        const internals = (bus as unknown as { listeners: Map<string, unknown[]> }).listeners;
        expect(internals.has('SETTINGS_TOGGLE')).toBe(true);
        expect(internals.get('SETTINGS_TOGGLE')).toHaveLength(1);
    });

    it('adds a second listener to the same key', () => {
        const bus = makeBus();
        bus.subscribe('SETTINGS_TOGGLE', () => {});
        bus.subscribe('SETTINGS_TOGGLE', () => {});
        const internals = (bus as unknown as { listeners: Map<string, unknown[]> }).listeners;
        expect(internals.get('SETTINGS_TOGGLE')).toHaveLength(2);
    });

    it('removes the listener entry (splice) after unsubscribe', () => {
        const bus = makeBus();
        const h = () => {};
        bus.subscribe('SETTINGS_TOGGLE', h);
        bus.unsubscribe('SETTINGS_TOGGLE', h);
        const internals = (bus as unknown as { listeners: Map<string, unknown[]> }).listeners;
        expect(internals.get('SETTINGS_TOGGLE')).toHaveLength(0);
    });

    it('separate event keys are independent in the map', () => {
        const bus = makeBus();
        bus.subscribe('SETTINGS_TOGGLE', () => {});
        bus.subscribe('AUDIO_UNLOCK', () => {});
        const internals = (bus as unknown as { listeners: Map<string, unknown[]> }).listeners;
        expect(internals.size).toBe(2);
    });
});

// ─────────────────────────────────────────────────────────────────
// EventBus — generic / custom events
// ─────────────────────────────────────────────────────────────────

describe('EventBus — generic custom events', () => {
    it('can subscribe/publish/unsubscribe on a custom string key', () => {
        const bus = new EventBus<{ 'TEST_EVENT': { value: number } }>();
        const received: number[] = [];
        bus.subscribe('TEST_EVENT', (d) => received.push(d.value));
        bus.publish('TEST_EVENT', { value: 42 });
        expect(received).toEqual([42]);
    });

    it('handles an isolated bus with no cross-contamination', () => {
        const bus1 = makeBus();
        const bus2 = makeBus();
        const calls1: number[] = [];
        const calls2: number[] = [];

        bus1.subscribe('SETTINGS_TOGGLE', () => calls1.push(1));
        bus2.subscribe('SETTINGS_TOGGLE', () => calls2.push(2));

        bus1.publish('SETTINGS_TOGGLE', null);

        expect(calls1).toHaveLength(1);
        expect(calls2).toHaveLength(0); // bus2 not involved
    });
});

// ─────────────────────────────────────────────────────────────────
// ATDD-ARCH-001 — globalEventBus trap
// ─────────────────────────────────────────────────────────────────

describe('ATDD-ARCH-001 — globalEventBus violation trap', () => {
    it('throws an informative error when any property is accessed on globalEventBus', () => {
        expect(() => {
            // Access via property — runtime Proxy trap fires
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (globalEventBus as any)['subscribe']();
        }).toThrow('[ATDD-ARCH-001]');
    });

    it('error message contains the fix instruction', () => {
        let message = '';
        try {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (globalEventBus as any)['publish']();
        } catch (e) {
            message = (e as Error).message;
        }
        expect(message).toContain('globalEventBus');
        expect(message).toContain('context.eventBus');
    });

    it('error message contains singleton deletion notice — kills line 169 StringLiteral', () => {
        // StringLiteral "The globalEventBus singleton has been deleted" → ""
        // Without this assertion, mutating that line to "" still passes all other checks
        let message = '';
        try { (globalEventBus as any)['any_prop'](); } catch (e) { message = (e as Error).message; }
        expect(message).toContain('been deleted');
    });

    it('error message references initAll — kills line 171 StringLiteral', () => {
        // StringLiteral "The PluginSupervisor injects...initAll()" → ""
        let message = '';
        try { (globalEventBus as any)['subscribe'](); } catch (e) { message = (e as Error).message; }
        expect(message).toContain('initAll');
    });

    it('error message references plugin_supervisor.ts — kills line 172 StringLiteral', () => {
        // StringLiteral "See plugin_supervisor.ts → PluginContext.eventBus" → ""
        let message = '';
        try { (globalEventBus as any)['unsubscribe'](); } catch (e) { message = (e as Error).message; }
        expect(message).toContain('plugin_supervisor.ts');
    });
});

// ─────────────────────────────────────────────────────────────────
// EventBus — dev-mode dead-letter warning
// ─────────────────────────────────────────────────────────────────

describe('EventBus — dead-letter detection (dev mode)', () => {
    const originalEnv = process.env['NODE_ENV'];

    beforeEach(() => {
        (process.env as Record<string, string>)['NODE_ENV'] = 'development';
    });

    afterEach(() => {
        if (originalEnv === undefined) {
            delete process.env['NODE_ENV'];
        } else {
            (process.env as Record<string, string>)['NODE_ENV'] = originalEnv;
        }
    });

    it('emits a console.warn when a sentinel event is published with no subscribers', () => {
        const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
        const bus = makeBus();
        bus.publish('FRAME_PROCESSED', []);
        expect(warn).toHaveBeenCalled();
        const msg = warn.mock.calls[0]?.[0] as string;
        expect(msg).toContain('DEAD-LETTER');
        warn.mockRestore();
    });

    it('does NOT emit dead-letter warning for non-sentinel events', () => {
        const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
        const bus = makeBus();
        bus.publish('SETTINGS_TOGGLE', null);
        expect(warn).not.toHaveBeenCalled();
        warn.mockRestore();
    });

    it('does NOT emit dead-letter warning when a subscriber IS registered', () => {
        const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
        const bus = makeBus();
        bus.subscribe('FRAME_PROCESSED', () => {});
        bus.publish('FRAME_PROCESSED', []);
        expect(warn).not.toHaveBeenCalled();
        warn.mockRestore();
    });

    it('emits dead-letter warning after ALL subscribers are removed (empty list case)', () => {
        // This case: list exists but length === 0 (after unsubscribe)
        // Kills: !list || list.length === 0 → !list && list.length === 0 mutation
        const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
        const bus = makeBus();
        const h = () => {};
        bus.subscribe('FRAME_PROCESSED', h);
        bus.unsubscribe('FRAME_PROCESSED', h);
        // Now list exists but is empty
        bus.publish('FRAME_PROCESSED', []);
        expect(warn).toHaveBeenCalled();
        warn.mockRestore();
    });

    it('emits warning for each of the sentinel events', () => {
        const sentinels = [
            'FRAME_PROCESSED', 'STATE_CHANGE', 'POINTER_UPDATE',
            'POINTER_COAST', 'STILLNESS_DETECTED',
        ] as const;

        for (const evt of sentinels) {
            const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
            const bus = makeBus();
            // Publish with the minimal required shape for each
            if (evt === 'FRAME_PROCESSED') bus.publish(evt, []);
            else if (evt === 'STATE_CHANGE') bus.publish(evt, { handId: 0, previousState: 'IDLE', currentState: 'READY' });
            else if (evt === 'POINTER_UPDATE') bus.publish(evt, { handId: 0, x: 0, y: 0, isPinching: false });
            else if (evt === 'POINTER_COAST') bus.publish(evt, { handId: 0, isPinching: false, destroy: false });
            else if (evt === 'STILLNESS_DETECTED') bus.publish(evt, { handId: 0, x: 0, y: 0 });
            expect(warn).toHaveBeenCalled();
            warn.mockRestore();
        }
    });
});

describe('EventBus — dead-letter only fires in development (production gate)', () => {
    const originalEnv = process.env['NODE_ENV'];

    afterEach(() => {
        if (originalEnv === undefined) {
            delete process.env['NODE_ENV'];
        } else {
            (process.env as Record<string, string>)['NODE_ENV'] = originalEnv;
        }
    });

    it('does NOT emit dead-letter warning in production mode', () => {
        // Kills: NODE_ENV === 'development' → NODE_ENV !== 'development' mutation
        (process.env as Record<string, string>)['NODE_ENV'] = 'production';
        const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
        const bus = makeBus();
        bus.publish('FRAME_PROCESSED', []);
        expect(warn).not.toHaveBeenCalled();
        warn.mockRestore();
    });

    it('does NOT emit dead-letter warning when NODE_ENV is test', () => {
        (process.env as Record<string, string>)['NODE_ENV'] = 'test';
        const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
        const bus = makeBus();
        bus.publish('POINTER_UPDATE', { handId: 0, x: 0, y: 0, isPinching: false });
        expect(warn).not.toHaveBeenCalled();
        warn.mockRestore();
    });
});
