/**
 * test_symbiote_injector_plugin.ts
 * Jest mutation-killing harness for SymbioteInjectorPlugin (Omega v15 tile).
 * Named test_* so jest.config.js picks it up.
 *
 * Coverage targets:
 *  T-OMEGA-SYM-001: Zombie fix — boundOnPointerUpdate is stable ref (not inline bind)
 *  T-OMEGA-SYM-002: init() subscribes once; stop() unsubscribes; destroy() unsubscribes
 *  T-OMEGA-SYM-003: pointer event type routing (pointermove/pointerdown/pointerup)
 *  T-OMEGA-SYM-004: coordinate arithmetic (screenX = x * screenWidth)
 *  T-OMEGA-SYM-005: PAL ScreenWidth/Height — static number vs callable function
 *  T-OMEGA-SYM-006: PAL DispatchEvent absent → safe no-op (no crash)
 *  T-OMEGA-SYM-007: isPinchingMap cleared on destroy()
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { SymbioteInjectorPlugin } from './symbiote_injector_plugin';
import { EventBus } from './event_bus';
import { PluginContext, PathAbstractionLayer } from './plugin_supervisor';

// Helpers to peek into EventBus listener count
type BusInternal = { listeners: Map<string, unknown[]> };
function listenerCount(bus: EventBus, event: string): number {
    return (bus as unknown as BusInternal).listeners.get(event)?.length ?? 0;
}

// Helper: build a PluginContext with a mock PAL + optional DispatchEvent
function makeContext(opts: {
    screenWidth?: number | (() => number);
    screenHeight?: number | (() => number);
    withDispatch?: boolean;
} = {}): {
    context: PluginContext;
    eventBus: EventBus;
    dispatch: ReturnType<typeof jest.fn>;
} {
    const eventBus = new EventBus();
    const pal = new PathAbstractionLayer();
    const dispatch = jest.fn();

    if (opts.screenWidth !== undefined) {
        pal.register('ScreenWidth', opts.screenWidth as unknown);
    }
    if (opts.screenHeight !== undefined) {
        pal.register('ScreenHeight', opts.screenHeight as unknown);
    }
    if (opts.withDispatch !== false) {
        pal.register('DispatchEvent', dispatch as unknown);
    }

    return { context: { eventBus, pal }, eventBus, dispatch };
}

// ---------------------------------------------------------------------------
// T-OMEGA-SYM-001: Zombie fix — stable bound reference
// ---------------------------------------------------------------------------
describe('SymbioteInjectorPlugin (T-OMEGA-SYM-001: Zombie Fix)', () => {
    it('Given constructor called, Then boundOnPointerUpdate is a bound function (not undefined)', () => {
        const plugin = new SymbioteInjectorPlugin();
        // Access the private field via type bypass — confirms bound ref exists
        const bound = (plugin as unknown as { boundOnPointerUpdate: unknown }).boundOnPointerUpdate;
        expect(typeof bound).toBe('function');
    });

    it('Given two SymbioteInjectorPlugins, Then their boundOnPointerUpdate refs are distinct', () => {
        const a = new SymbioteInjectorPlugin();
        const b = new SymbioteInjectorPlugin();
        const refA = (a as unknown as { boundOnPointerUpdate: unknown }).boundOnPointerUpdate;
        const refB = (b as unknown as { boundOnPointerUpdate: unknown }).boundOnPointerUpdate;
        expect(refA).not.toBe(refB);
    });

    it('Given same plugin, boundOnPointerUpdate ref is stable across calls', () => {
        const plugin = new SymbioteInjectorPlugin();
        const ref1 = (plugin as unknown as { boundOnPointerUpdate: unknown }).boundOnPointerUpdate;
        const ref2 = (plugin as unknown as { boundOnPointerUpdate: unknown }).boundOnPointerUpdate;
        expect(ref1).toBe(ref2);
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-SYM-002: Subscription lifecycle
// ---------------------------------------------------------------------------
describe('SymbioteInjectorPlugin (T-OMEGA-SYM-002: Subscription Lifecycle)', () => {
    let plugin: SymbioteInjectorPlugin;
    let eventBus: EventBus;
    let context: PluginContext;

    beforeEach(() => {
        plugin = new SymbioteInjectorPlugin();
        const m = makeContext({ screenWidth: 1920, screenHeight: 1080 });
        eventBus = m.eventBus;
        context = m.context;
    });

    it('Given init() called, Then POINTER_UPDATE listener count is 1', () => {
        plugin.init(context);
        expect(listenerCount(eventBus, 'POINTER_UPDATE')).toBe(1);
    });

    it('Given init() called twice (restart path), Then POINTER_UPDATE listener count is 2', () => {
        plugin.init(context);
        plugin.init(context);
        expect(listenerCount(eventBus, 'POINTER_UPDATE')).toBe(2);
    });

    it('Given init then stop(), Then POINTER_UPDATE listener count is 0', () => {
        plugin.init(context);
        plugin.stop();
        expect(listenerCount(eventBus, 'POINTER_UPDATE')).toBe(0);
    });

    it('Given init then destroy(), Then POINTER_UPDATE listener count is 0', () => {
        plugin.init(context);
        plugin.destroy();
        expect(listenerCount(eventBus, 'POINTER_UPDATE')).toBe(0);
    });

    it('Given init then destroy(), When POINTER_UPDATE fires, Then dispatch NOT called', () => {
        const { dispatch } = makeContext({ screenWidth: 1920, screenHeight: 1080, withDispatch: true });
        const ctx2 = { eventBus, pal: context.pal };
        ctx2.pal.register('DispatchEvent', dispatch as unknown);
        plugin.init(context);
        plugin.destroy();
        dispatch.mockClear();
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: false });
        expect(dispatch).not.toHaveBeenCalled();
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-SYM-003: Event type routing (state machine mutations)
// ---------------------------------------------------------------------------
describe('SymbioteInjectorPlugin (T-OMEGA-SYM-003: Event Type Routing)', () => {
    let plugin: SymbioteInjectorPlugin;
    let eventBus: EventBus;
    let dispatch: ReturnType<typeof jest.fn>;

    beforeEach(() => {
        plugin = new SymbioteInjectorPlugin();
        const m = makeContext({ screenWidth: 1920, screenHeight: 1080, withDispatch: true });
        eventBus = m.eventBus;
        dispatch = m.dispatch;
        plugin.init(m.context);
    });

    it('First event with isPinching=false → CustomEvent type is pointermove', () => {
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: false });
        expect(dispatch).toHaveBeenCalledTimes(1);
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.type).toBe('pointermove');
    });

    it('isPinching false → true → CustomEvent type is pointerdown', () => {
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: false });
        dispatch.mockClear();
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: true });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.type).toBe('pointerdown');
    });

    it('isPinching true → false → CustomEvent type is pointerup', () => {
        // seed pinching=true
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: true });
        dispatch.mockClear();
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: false });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.type).toBe('pointerup');
    });

    it('isPinching true → true (stays pinching) → CustomEvent type is pointermove', () => {
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: true });
        dispatch.mockClear();
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: true });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.type).toBe('pointermove');
    });

    it('Two hands tracked independently — hand0 pointerdown does not affect hand1 state', () => {
        // hand 0: false → true (pointerdown)
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: false });
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: true });
        dispatch.mockClear();
        // hand 1: first event should be pointermove (not pointerup, state starts as false/unset)
        eventBus.publish('POINTER_UPDATE', { handId: 1, x: 0.5, y: 0.5, isPinching: false });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.type).toBe('pointermove');
        expect(event.detail.handId).toBe(1);
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-SYM-004: Coordinate arithmetic  (kills x*width mutants)
// ---------------------------------------------------------------------------
describe('SymbioteInjectorPlugin (T-OMEGA-SYM-004: Coordinate Arithmetic)', () => {
    let plugin: SymbioteInjectorPlugin;
    let eventBus: EventBus;
    let dispatch: ReturnType<typeof jest.fn>;

    beforeEach(() => {
        plugin = new SymbioteInjectorPlugin();
        const m = makeContext({ screenWidth: 1920, screenHeight: 1080, withDispatch: true });
        eventBus = m.eventBus;
        dispatch = m.dispatch;
        plugin.init(m.context);
    });

    it('screenX = x * screenWidth (0.5 * 1920 = 960)', () => {
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.0, isPinching: false });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.x).toBe(960);
    });

    it('screenY = y * screenHeight (0.25 * 1080 = 270)', () => {
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.0, y: 0.25, isPinching: false });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.y).toBe(270);
    });

    it('x=0 → screenX=0 (zero boundary kill)', () => {
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.0, y: 0.5, isPinching: false });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.x).toBe(0);
    });

    it('x=1.0 → screenX=1920 (full-width boundary)', () => {
        eventBus.publish('POINTER_UPDATE', { handId: 0, x: 1.0, y: 0.5, isPinching: false });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.x).toBe(1920);
    });

    it('detail.handId is propagated correctly', () => {
        eventBus.publish('POINTER_UPDATE', { handId: 7, x: 0.5, y: 0.5, isPinching: false });
        const event = dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.handId).toBe(7);
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-SYM-005: PAL ScreenWidth/Height — static number vs callable
// ---------------------------------------------------------------------------
describe('SymbioteInjectorPlugin (T-OMEGA-SYM-005: PAL Resolution)', () => {
    it('Given ScreenWidth is a static number, Then screenX = x * number', () => {
        const plugin = new SymbioteInjectorPlugin();
        const m = makeContext({ screenWidth: 800, screenHeight: 600, withDispatch: true });
        plugin.init(m.context);
        m.eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: false });
        const event = m.dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.x).toBe(400); // 0.5 * 800
    });

    it('Given ScreenWidth is a function, Then screenX = x * fn()', () => {
        const plugin = new SymbioteInjectorPlugin();
        const m = makeContext({ screenWidth: () => 2560, screenHeight: 1440, withDispatch: true });
        plugin.init(m.context);
        m.eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: false });
        const event = m.dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.x).toBe(1280); // 0.5 * 2560
    });

    it('Given ScreenHeight is a function, Then screenY = y * fn()', () => {
        const plugin = new SymbioteInjectorPlugin();
        const m = makeContext({ screenWidth: 1920, screenHeight: () => 1080, withDispatch: true });
        plugin.init(m.context);
        m.eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.0, y: 0.5, isPinching: false });
        const event = m.dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.y).toBe(540); // 0.5 * 1080
    });

    it('Given ScreenWidth not registered in PAL, Then screenX = x * 1 (fallback)', () => {
        const plugin = new SymbioteInjectorPlugin();
        // No screenWidth registered
        const m = makeContext({ screenHeight: 1080, withDispatch: true });
        plugin.init(m.context);
        m.eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.75, y: 0.0, isPinching: false });
        const event = m.dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.x).toBe(0.75); // 0.75 * 1 (fallback)
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-SYM-006: DispatchEvent absent → safe no-op
// ---------------------------------------------------------------------------
describe('SymbioteInjectorPlugin (T-OMEGA-SYM-006: DispatchEvent absent)', () => {
    it('Given DispatchEvent not registered, When POINTER_UPDATE fires, Then no error thrown', () => {
        const plugin = new SymbioteInjectorPlugin();
        const m = makeContext({ screenWidth: 1920, screenHeight: 1080, withDispatch: false });
        plugin.init(m.context);
        expect(() => {
            m.eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: false });
        }).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-SYM-007: isPinchingMap cleared on destroy()
// ---------------------------------------------------------------------------
describe('SymbioteInjectorPlugin (T-OMEGA-SYM-007: isPinchingMap cleared on destroy)', () => {
    it('Given pinching state recorded, When destroy() called, Then fresh init sees clean state (pointerdown on next true)', () => {
        const plugin = new SymbioteInjectorPlugin();
        const m = makeContext({ screenWidth: 1920, screenHeight: 1080, withDispatch: true });
        plugin.init(m.context);

        // Seed isPinchingMap: hand0 is pinching
        m.eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: true });
        plugin.destroy();

        // Re-init on a new bus so we can test clean-slate behavior
        const m2 = makeContext({ screenWidth: 1920, screenHeight: 1080, withDispatch: true });
        plugin.init(m2.context);
        // After destroy() + re-init, hand0's state should be gone → false → true = pointerdown
        m2.eventBus.publish('POINTER_UPDATE', { handId: 0, x: 0.5, y: 0.5, isPinching: true });
        const event = m2.dispatch.mock.calls[0]![0] as CustomEvent;
        expect(event.detail.type).toBe('pointerdown');
    });
});
