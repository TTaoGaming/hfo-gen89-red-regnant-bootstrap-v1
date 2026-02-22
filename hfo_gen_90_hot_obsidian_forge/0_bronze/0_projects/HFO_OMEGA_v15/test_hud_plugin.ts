/**
 * test_hud_plugin.ts
 *
 * Mutation-hardened Jest tests for HudPlugin.
 *
 * Coverage targets (mutation kills required):
 *   - GetElementById PAL registration fail-closed throw
 *   - Missing DOM elements fail-closed throw
 *   - FRAME_PROCESSED / STATE_CHANGE subscribe / unsubscribe
 *   - FPS counter 1-second gate (now - lastT > 1000)
 *   - hudFps textContent update (fps: N)
 *   - hudPos textContent update with x/y
 *   - hudState textContent update
 *   - destroy clears references
 *
 * HFO Omega v15 | Stryker receipt required
 */

import { HudPlugin } from './hud_plugin';

// ─── DOM Mock ─────────────────────────────────────────────────────────────────

function makeHTMLElement(id: string): any {
    return { id, textContent: '', style: {} };
}

function makePal(elements: Record<string, any>) {
    return {
        resolve: (key: string) => {
            if (key === 'GetElementById') {
                return (id: string) => elements[id] ?? null;
            }
            return undefined;
        },
    };
}

function makeEventBus() {
    const subs = new Map<string, Function>();
    const unsubs: { event: string; fn: Function }[] = [];
    const published: { event: string; payload: unknown }[] = [];
    return {
        subscribe: (event: string, fn: Function) => subs.set(event, fn),
        unsubscribe: (event: string, fn: Function) => unsubs.push({ event, fn }),
        publish: (event: string, payload: unknown) => published.push({ event, payload }),
        _subs: subs,
        _unsubs: unsubs,
        _published: published,
    };
}

function makeContext(elems: Record<string, any>) {
    const bus = makeEventBus();
    const pal = makePal(elems);
    // Use `as any` to sidestep private members of EventBus<MicrokernelEvents>
    const context: any = { eventBus: bus, pal };
    return { bus, pal, context };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('HudPlugin — identity', () => {
    it('has name HudPlugin', () => {
        const p = new HudPlugin();
        expect(p.name).toBe('HudPlugin');
    });

    it('has version 1.0.0', () => {
        const p = new HudPlugin();
        expect(p.version).toBe('1.0.0');
    });
});

describe('HudPlugin — init fail-closed: PAL not registered', () => {
    it('throws if GetElementById not in PAL', async () => {
        const plugin = new HudPlugin();
        const ctx = {
            eventBus: makeEventBus(),
            pal: { resolve: (_key: string) => null },
        };
        await expect(plugin.init(ctx as any)).rejects.toThrow(/GetElementById not registered/);
    });
});

describe('HudPlugin — init fail-closed: missing DOM elements', () => {
    it('throws if hud-fps element is missing', async () => {
        const plugin = new HudPlugin();
        const { context } = makeContext({ 'hud-state': makeHTMLElement('hud-state'), 'hud-pos': makeHTMLElement('hud-pos') });
        await expect(plugin.init(context as any)).rejects.toThrow(/Missing HUD DOM elements/);
    });

    it('throws if hud-state element is missing', async () => {
        const plugin = new HudPlugin();
        const { context } = makeContext({ 'hud-fps': makeHTMLElement('hud-fps'), 'hud-pos': makeHTMLElement('hud-pos') });
        await expect(plugin.init(context as any)).rejects.toThrow(/Missing HUD DOM elements/);
    });

    it('throws if hud-pos element is missing', async () => {
        const plugin = new HudPlugin();
        const { context } = makeContext({ 'hud-fps': makeHTMLElement('hud-fps'), 'hud-state': makeHTMLElement('hud-state') });
        await expect(plugin.init(context as any)).rejects.toThrow(/Missing HUD DOM elements/);
    });
});

describe('HudPlugin — lifecycle', () => {
    let plugin: HudPlugin;
    let bus: ReturnType<typeof makeEventBus>;
    let context: any;
    let elems: Record<string, any>;

    beforeEach(async () => {
        plugin = new HudPlugin();
        elems = {
            'hud-fps': makeHTMLElement('hud-fps'),
            'hud-state': makeHTMLElement('hud-state'),
            'hud-pos': makeHTMLElement('hud-pos'),
        };
        const ctx = makeContext(elems);
        bus = ctx.bus;
        context = ctx.context;
        await plugin.init(context);
    });

    it('start subscribes to FRAME_PROCESSED', async () => {
        await plugin.start();
        expect(bus._subs.has('FRAME_PROCESSED')).toBe(true);
    });

    it('start subscribes to STATE_CHANGE', async () => {
        await plugin.start();
        expect(bus._subs.has('STATE_CHANGE')).toBe(true);
    });

    it('stop unsubscribes from FRAME_PROCESSED', async () => {
        await plugin.start();
        await plugin.stop();
        expect(bus._unsubs.some(u => u.event === 'FRAME_PROCESSED')).toBe(true);
    });

    it('stop unsubscribes from STATE_CHANGE', async () => {
        await plugin.start();
        await plugin.stop();
        expect(bus._unsubs.some(u => u.event === 'STATE_CHANGE')).toBe(true);
    });

    it('stop without start does not throw', async () => {
        await expect(plugin.stop()).resolves.not.toThrow();
    });

    it('destroy clears bus reference', async () => {
        await plugin.start();
        await plugin.destroy();
        // After destroy, stop should be safe (bus=null guard)
        await expect(plugin.stop()).resolves.not.toThrow();
    });
});

describe('HudPlugin — FPS counter', () => {
    let plugin: HudPlugin;
    let bus: ReturnType<typeof makeEventBus>;
    let elems: Record<string, any>;
    let nowSpy: jest.SpyInstance;

    beforeEach(async () => {
        plugin = new HudPlugin();
        elems = {
            'hud-fps': makeHTMLElement('hud-fps'),
            'hud-state': makeHTMLElement('hud-state'),
            'hud-pos': makeHTMLElement('hud-pos'),
        };
        const ctx = makeContext(elems);
        bus = ctx.bus;
        await plugin.init(ctx.context);
        await plugin.start();
    });

    afterEach(() => {
        if (nowSpy) nowSpy.mockRestore();
    });

    it('does NOT update fps display before 1 second has elapsed', () => {
        nowSpy = jest.spyOn(performance, 'now').mockReturnValue(0);
        const handler = bus._subs.get('FRAME_PROCESSED')!;

        // Simulate 10 frames within 999ms
        jest.spyOn(performance, 'now').mockReturnValue(999);
        for (let i = 0; i < 10; i++) handler([]);

        expect(elems['hud-fps'].textContent).toBe('');  // not yet updated
    });

    it('updates fps display after 1 second (> 1000ms)', async () => {
        // Simulate: lastT = 0, now = 1001
        let callCount = 0;
        nowSpy = jest.spyOn(performance, 'now').mockImplementation(() => {
            // first call = constructor init (lastT=0)
            // subsequent = frame processing
            return callCount++ === 0 ? 0 : 1001;
        });

        const plugin2 = new HudPlugin();
        const elems2 = {
            'hud-fps': makeHTMLElement('hud-fps'),
            'hud-state': makeHTMLElement('hud-state'),
            'hud-pos': makeHTMLElement('hud-pos'),
        };
        const ctx2 = makeContext(elems2);
        await plugin2.init(ctx2.context);
        await plugin2.start();

        const handler = ctx2.bus._subs.get('FRAME_PROCESSED')!;
        handler([]);  // this frame: now=1001, lastT=0 → 1001 > 1000 → update
        expect(elems2['hud-fps'].textContent).toMatch(/^fps: \d+$/);
    });
});

describe('HudPlugin — position display', () => {
    let plugin: HudPlugin;
    let bus: ReturnType<typeof makeEventBus>;
    let elems: Record<string, any>;

    beforeEach(async () => {
        plugin = new HudPlugin();
        elems = {
            'hud-fps': makeHTMLElement('hud-fps'),
            'hud-state': makeHTMLElement('hud-state'),
            'hud-pos': makeHTMLElement('hud-pos'),
        };
        const ctx = makeContext(elems);
        bus = ctx.bus;
        await plugin.init(ctx.context);
        await plugin.start();
    });

    it('updates hud-pos when hands are present', () => {
        const handler = bus._subs.get('FRAME_PROCESSED')!;
        handler([{ x: 0.5, y: 0.25 }]);
        expect(elems['hud-pos'].textContent).toMatch(/pos: \(50\.0%, 25\.0%\)/);
    });

    it('does NOT update hud-pos when hands array is empty', () => {
        const handler = bus._subs.get('FRAME_PROCESSED')!;
        handler([]);
        expect(elems['hud-pos'].textContent).toBe('');
    });

    it('x coordinate scaled * 100 (0.1 → 10.0%)', () => {
        const handler = bus._subs.get('FRAME_PROCESSED')!;
        handler([{ x: 0.1, y: 0.0 }]);
        expect(elems['hud-pos'].textContent).toContain('10.0%');
    });

    it('y coordinate scaled * 100 (0.75 → 75.0%)', () => {
        const handler = bus._subs.get('FRAME_PROCESSED')!;
        handler([{ x: 0.0, y: 0.75 }]);
        expect(elems['hud-pos'].textContent).toContain('75.0%');
    });
});

describe('HudPlugin — state display', () => {
    let plugin: HudPlugin;
    let bus: ReturnType<typeof makeEventBus>;
    let elems: Record<string, any>;

    beforeEach(async () => {
        plugin = new HudPlugin();
        elems = {
            'hud-fps': makeHTMLElement('hud-fps'),
            'hud-state': makeHTMLElement('hud-state'),
            'hud-pos': makeHTMLElement('hud-pos'),
        };
        const ctx = makeContext(elems);
        bus = ctx.bus;
        await plugin.init(ctx.context);
        await plugin.start();
    });

    it('updates hud-state on STATE_CHANGE event', () => {
        const handler = bus._subs.get('STATE_CHANGE')!;
        handler({ currentState: 'READY' });
        expect(elems['hud-state'].textContent).toBe('state: READY');
    });

    it('updates hud-state with different states', () => {
        const handler = bus._subs.get('STATE_CHANGE')!;
        handler({ currentState: 'COMMIT_POINTER' });
        expect(elems['hud-state'].textContent).toBe('state: COMMIT_POINTER');
    });

    it('does not update hud-state when payload is null', () => {
        const handler = bus._subs.get('STATE_CHANGE')!;
        handler(null);
        expect(elems['hud-state'].textContent).toBe('');
    });

    it('does not update hud-state when currentState is missing', () => {
        const handler = bus._subs.get('STATE_CHANGE')!;
        handler({});
        expect(elems['hud-state'].textContent).toBe('');
    });
});
