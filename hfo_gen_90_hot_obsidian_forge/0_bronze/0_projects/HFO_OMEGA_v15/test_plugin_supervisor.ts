import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { PluginSupervisor, Plugin, PluginContext, LifecycleGateError, PathAbstractionLayer } from './plugin_supervisor';
import { EventBus } from './event_bus';

// ─── Helpers ─────────────────────────────────────────────────────────────────

class MockPlugin implements Plugin {
    name: string;
    version = '1.0.0';
    receivedContext: PluginContext | null = null;

    initCalled = 0;
    startCalled = 0;
    stopCalled = 0;
    destroyCalled = 0;
    
    shouldThrowOnInit = false;
    shouldThrowOnStart = false;
    shouldThrowOnStop = false;
    shouldThrowOnDestroy = false;

    constructor(name: string) {
        this.name = name;
    }

    async init(context: PluginContext): Promise<void> {
        this.initCalled++;
        this.receivedContext = context;
        if (this.shouldThrowOnInit) throw new Error(`Init error in ${this.name}`);
        context.pal.register(`${this.name}.data`, { secret: 42 });
    }

    async start(): Promise<void> {
        this.startCalled++;
        if (this.shouldThrowOnStart) throw new Error(`Start error in ${this.name}`);
    }

    async stop(): Promise<void> {
        this.stopCalled++;
        if (this.shouldThrowOnStop) throw new Error(`Stop error in ${this.name}`);
    }

    async destroy(): Promise<void> {
        this.destroyCalled++;
        if (this.shouldThrowOnDestroy) throw new Error(`Destroy error in ${this.name}`);
    }
}

describe('PluginSupervisor — constructor', () => {

    it('Given a new supervisor, Then getState() returns CREATED', () => {
        const sup = new PluginSupervisor();
        expect(sup.getState()).toBe('CREATED');
    });

    it('Given a new supervisor, Then getEventBus() returns an EventBus instance', () => {
        const sup = new PluginSupervisor();
        expect(sup.getEventBus()).toBeInstanceOf(EventBus);
    });

    it('Given a new supervisor, Then getPal() returns a PathAbstractionLayer instance', () => {
        const sup = new PluginSupervisor();
        expect(sup.getPal()).toBeInstanceOf(PathAbstractionLayer);
    });

    it('Given an external EventBus is injected, Then getEventBus() returns that exact instance', () => {
        const bus = new EventBus();
        const sup = new PluginSupervisor(bus);
        expect(sup.getEventBus()).toBe(bus);
    });

});

// ─── registerPlugin ───────────────────────────────────────────────────────────

describe('PluginSupervisor — registerPlugin', () => {

    let sup: PluginSupervisor;
    beforeEach(() => { sup = new PluginSupervisor(); });

    it('Given state=CREATED, When registerPlugin called, Then no error', () => {
        expect(() => sup.registerPlugin(new MockPlugin('Alpha'))).not.toThrow();
    });

    it('Given plugin registered, When same name registered again, Then throws /DUPLICATE PLUGIN/', () => {
        sup.registerPlugin(new MockPlugin('Alpha'));
        expect(() => sup.registerPlugin(new MockPlugin('Alpha'))).toThrow('DUPLICATE PLUGIN');
    });

    it('Given state=INITIALIZED, When registerPlugin called, Then throws LifecycleGateError', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        expect(() => sup.registerPlugin(new MockPlugin('Q'))).toThrow(LifecycleGateError);
    });

    it('Given state=RUNNING, When registerPlugin called, Then error message mentions RUNNING', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        await sup.startAll();
        expect(() => sup.registerPlugin(new MockPlugin('Q'))).toThrow(/RUNNING/);
    });

});

// ─── initAll ─────────────────────────────────────────────────────────────────

describe('PluginSupervisor — initAll', () => {

    let sup: PluginSupervisor;
    beforeEach(() => { sup = new PluginSupervisor(); });

    it('Given state=CREATED, When initAll completes, Then state=INITIALIZED', async () => {
        sup.registerPlugin(new MockPlugin('P1'));
        await sup.initAll();
        expect(sup.getState()).toBe('INITIALIZED');
    });

    it('Given two plugins, When initAll runs, Then each plugin.init called exactly once', async () => {
        const p1 = new MockPlugin('P1');
        const p2 = new MockPlugin('P2');
        sup.registerPlugin(p1); sup.registerPlugin(p2);
        await sup.initAll();
        expect(p1.initCalled).toBe(1);
        expect(p2.initCalled).toBe(1);
    });

    it('Given plugin registered, When initAll runs, Then plugin.init receives PluginContext with EventBus', async () => {
        const p = new MockPlugin('P1');
        sup.registerPlugin(p);
        await sup.initAll();
        expect(p.receivedContext).not.toBeNull();
        expect(p.receivedContext!.eventBus).toBeInstanceOf(EventBus);
    });

    it('Given plugin registered, When initAll runs, Then injected EventBus === getEventBus()', async () => {
        const p = new MockPlugin('P1');
        sup.registerPlugin(p);
        await sup.initAll();
        expect(p.receivedContext!.eventBus).toBe(sup.getEventBus());
    });

    it('Given state=INITIALIZED, When initAll called again, Then throws LifecycleGateError', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        await expect(sup.initAll()).rejects.toThrow(LifecycleGateError);
    });

    it('Given LifecycleGateError, Then message contains LIFECYCLE GATE', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        const err = await sup.initAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/LIFECYCLE GATE/);
    });

    it('Given LifecycleGateError from double-initAll, Then message contains INITIALIZED (current state)', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        const err = await sup.initAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/INITIALIZED/);
    });

    it('Given LifecycleGateError, Then error.name is LifecycleGateError', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        const err = await sup.initAll().catch((e: unknown) => e);
        expect((err as Error).name).toBe('LifecycleGateError');
    });

    it('Given plugin that throws in init, When initAll runs, Then error is rethrown (fail-closed)', async () => {
        const throwing = new MockPlugin('Bad');
        throwing.shouldThrowOnInit = true;
        sup.registerPlugin(throwing);
        await expect(sup.initAll()).rejects.toThrow('Init error in Bad');
    });

    it('Given plugin that throws in init, When initAll throws, Then state remains CREATED (not INITIALIZED)', async () => {
        const throwing = new MockPlugin('Bad');
        throwing.shouldThrowOnInit = true;
        sup.registerPlugin(throwing);
        try { await sup.initAll(); } catch { /* expected */ }
        expect(sup.getState()).toBe('CREATED');
    });

    it('Given PAL registered value in init, When initAll completes, Then getPal().resolve returns it', async () => {
        const p = new MockPlugin('P1');
        sup.registerPlugin(p);
        await sup.initAll();
        expect(sup.getPal().resolve('P1.data')).toStrictEqual({ secret: 42 });
    });

});

// ─── startAll ────────────────────────────────────────────────────────────────

describe('PluginSupervisor — startAll', () => {

    let sup: PluginSupervisor;
    beforeEach(() => { sup = new PluginSupervisor(); });

    it('Given state=INITIALIZED, When startAll completes, Then state=RUNNING', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        await sup.startAll();
        expect(sup.getState()).toBe('RUNNING');
    });

    it('Given two plugins, When startAll runs, Then each plugin.start called exactly once', async () => {
        const p1 = new MockPlugin('P1');
        const p2 = new MockPlugin('P2');
        sup.registerPlugin(p1); sup.registerPlugin(p2);
        await sup.initAll(); await sup.startAll();
        expect(p1.startCalled).toBe(1);
        expect(p2.startCalled).toBe(1);
    });

    it('Given state=CREATED, When startAll called, Then throws LifecycleGateError', async () => {
        await expect(sup.startAll()).rejects.toThrow(LifecycleGateError);
    });

    it('Given state=RUNNING, When startAll called again, Then throws LifecycleGateError', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll(); await sup.startAll();
        await expect(sup.startAll()).rejects.toThrow(LifecycleGateError);
    });

    it('Given state=STOPPED, When startAll called (restart path), Then state=RUNNING', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll(); await sup.startAll(); await sup.stopAll();
        await sup.startAll();
        expect(sup.getState()).toBe('RUNNING');
    });

    it('Given restart from STOPPED, When startAll called, Then plugin.start called 2 total times', async () => {
        const p = new MockPlugin('P');
        sup.registerPlugin(p);
        await sup.initAll(); await sup.startAll(); await sup.stopAll(); await sup.startAll();
        expect(p.startCalled).toBe(2);
    });

    it('Given plugin that throws in start, When startAll runs, Then error is rethrown', async () => {
        const throwing = new MockPlugin('Bad');
        throwing.shouldThrowOnStart = true;
        sup.registerPlugin(throwing);
        await sup.initAll();
        await expect(sup.startAll()).rejects.toThrow('Start error in Bad');
    });

    it('Given plugin that throws in start, Then state does NOT advance to RUNNING', async () => {
        const throwing = new MockPlugin('Bad');
        throwing.shouldThrowOnStart = true;
        sup.registerPlugin(throwing);
        await sup.initAll();
        try { await sup.startAll(); } catch { /* expected */ }
        expect(sup.getState()).toBe('INITIALIZED');
    });

});

// ─── stopAll ─────────────────────────────────────────────────────────────────

describe('PluginSupervisor — stopAll', () => {

    let sup: PluginSupervisor;
    beforeEach(() => { sup = new PluginSupervisor(); });

    it('Given state=RUNNING, When stopAll completes, Then state=STOPPED', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll(); await sup.startAll();
        await sup.stopAll();
        expect(sup.getState()).toBe('STOPPED');
    });

    it('Given 3 plugins, When stopAll runs, Then stop is called in reverse registration order', async () => {
        const order: string[] = [];
        const make = (name: string): Plugin & MockPlugin =>
            Object.assign(new MockPlugin(name), {
                async stop() { order.push(name); }
            });
        sup.registerPlugin(make('A'));
        sup.registerPlugin(make('B'));
        sup.registerPlugin(make('C'));
        await sup.initAll(); await sup.startAll();
        await sup.stopAll();
        expect(order).toEqual(['C', 'B', 'A']); // reverse registration order
    });

    it('Given state=INITIALIZED (not running), When stopAll called, Then throws LifecycleGateError', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        await expect(sup.stopAll()).rejects.toThrow(LifecycleGateError);
    });

    it('Given plugin that throws in stop, When stopAll runs, Then state still becomes STOPPED (non-fatal)', async () => {
        const throwing = new MockPlugin('Bad');
        throwing.shouldThrowOnStop = true;
        sup.registerPlugin(new MockPlugin('Good'));
        sup.registerPlugin(throwing);
        await sup.initAll(); await sup.startAll();
        await sup.stopAll(); // must NOT re-throw
        expect(sup.getState()).toBe('STOPPED');
    });

    it('Given plugin that throws in stop, When stopAll runs, Then remaining plugins are still stopped', async () => {
        const good = new MockPlugin('Good');
        const throwing = new MockPlugin('Bad');
        throwing.shouldThrowOnStop = true;
        sup.registerPlugin(throwing); // throwing first (reversed-last in stop)
        sup.registerPlugin(good);
        await sup.initAll(); await sup.startAll();
        await sup.stopAll();
        expect(good.stopCalled).toBe(1); // good plugin ran despite the error
    });

});

// ─── destroyAll ───────────────────────────────────────────────────────────────

describe('PluginSupervisor — destroyAll', () => {

    let sup: PluginSupervisor;
    beforeEach(() => { sup = new PluginSupervisor(); });

    it('Given state=STOPPED, When destroyAll completes, Then state=DESTROYED', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll(); await sup.startAll(); await sup.stopAll();
        await sup.destroyAll();
        expect(sup.getState()).toBe('DESTROYED');
    });

    it('Given state=RUNNING (emergency teardown), When destroyAll called, Then state=DESTROYED', async () => {
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll(); await sup.startAll();
        await sup.destroyAll();
        expect(sup.getState()).toBe('DESTROYED');
    });

    it('Given empty supervisor (CREATED), When destroyAll called, Then state=DESTROYED without error', async () => {
        await expect(sup.destroyAll()).resolves.not.toThrow();
        expect(sup.getState()).toBe('DESTROYED');
    });

    it('Given state=DESTROYED, When destroyAll called again, Then no error (idempotent)', async () => {
        await sup.destroyAll();
        await expect(sup.destroyAll()).resolves.not.toThrow();
    });

    it('Given state=DESTROYED, When destroyAll called again, Then state remains DESTROYED', async () => {
        await sup.destroyAll(); await sup.destroyAll();
        expect(sup.getState()).toBe('DESTROYED');
    });

    it('Given state=DESTROYED, When destroyAll called again, Then plugin.destroy NOT called twice', async () => {
        const p = new MockPlugin('P');
        sup.registerPlugin(p);
        await sup.initAll(); await sup.startAll(); await sup.stopAll();
        await sup.destroyAll();
        await sup.destroyAll();
        expect(p.destroyCalled).toBe(1); // NOT 2
    });

    it('Given 3 plugins, When destroyAll runs, Then destroy is called in reverse registration order', async () => {
        const order: string[] = [];
        const make = (name: string): Plugin & MockPlugin =>
            Object.assign(new MockPlugin(name), {
                async destroy() { order.push(name); }
            });
        sup.registerPlugin(make('A'));
        sup.registerPlugin(make('B'));
        sup.registerPlugin(make('C'));
        await sup.initAll(); await sup.startAll();
        await sup.destroyAll();
        expect(order).toEqual(['C', 'B', 'A']);
    });

    it('Given plugin that throws in destroy, When destroyAll runs, Then other plugins are still destroyed', async () => {
        const good = new MockPlugin('Good');
        const throwing = new MockPlugin('Bad');
        throwing.shouldThrowOnDestroy = true;
        sup.registerPlugin(good); sup.registerPlugin(throwing);
        await sup.initAll();
        await sup.destroyAll();
        expect(good.destroyCalled).toBe(1);
        expect(sup.getState()).toBe('DESTROYED');
    });

});

// ─── PathAbstractionLayer ────────────────────────────────────────────────────

describe('PathAbstractionLayer', () => {

    let pal: PathAbstractionLayer;
    beforeEach(() => { pal = new PathAbstractionLayer(); });

    it('Given key registered, When resolve<T> called, Then correct value returned', () => {
        pal.register('K', 42);
        expect(pal.resolve<number>('K')).toBe(42);
    });

    it('Given unregistered key, When resolve<T> called, Then undefined returned', () => {
        expect(pal.resolve<string>('NonExistent')).toBeUndefined();
    });

    it('Given key registered twice, When resolve called, Then second value returned (overwrite)', () => {
        pal.register('K', 'first');
        pal.register('K', 'second');
        expect(pal.resolve<string>('K')).toBe('second');
    });

    it('Given key overwrite, When second register called, Then console.warn is called with [PAL] message', () => {
        const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
        pal.register('K', 'v1');
        pal.register('K', 'v2');
        expect(warnSpy).toHaveBeenCalledWith(expect.stringMatching(/\[PAL\] Overwriting existing key: K/));
        warnSpy.mockRestore();
    });

    it('Given callable registered, When resolve<fn> called and invoked, Then it executes correctly', () => {
        const fn = jest.fn(() => 1920);
        pal.register('ScreenWidth', fn);
        const resolved = pal.resolve<() => number>('ScreenWidth');
        expect(typeof resolved).toBe('function');
        expect(resolved!()).toBe(1920);
    });

});

// ─── LifecycleGateError message contracts (mutation-kill target) ──────────────

describe('LifecycleGateError — message contracts', () => {

    it('Given RUNNING state, When initAll called, Then error lists allowed state CREATED', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll(); await sup.startAll();
        const err = await sup.initAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/CREATED/);
    });

    it('Given CREATED state, When stopAll called, Then error lists required state RUNNING', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.stopAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/RUNNING/);
    });

    it('Given INITIALIZED state, When stopAll called, Then error message mentions RUNNING as required', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        const err = await sup.stopAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/RUNNING/);
    });

    it('Given bad state call, Then error message includes Correct call order hint', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/Correct call order/);
    });

    it('Given CREATED state startAll call, Then error message includes INITIALIZED or STOPPED', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/INITIALIZED/);
    });

    it('Given CREATED state startAll call, Then error message includes Current state: CREATED', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/Current state: CREATED/);
    });

});

// ─── Mutation-killing: LifecycleGateError method names ───────────────────────
// Kills: StringLiteral "" survivors for method name args in LifecycleGateError
//        StringLiteral "" for 'STOPPED' in startAll allowed array
//        ArrayDeclaration [] and StringLiteral [""] for registerPlugin ['CREATED']
//        StringLiteral "" for 'join(' or ')' separator (line 55)
//        StringLiteral "" for 'join(", ")' separator (line 58)
//        StringLiteral "" for "but supervisor is in state" line (line 56)
//        StringLiteral "" for "destroyAll" hint in duplicate-plugin error (line 101)

describe('LifecycleGateError — method name embedded in message', () => {

    it('Given INITIALIZED state, When initAll called again, Then error message includes "initAll"', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        const err = await sup.initAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/initAll/);
    });

    // Precision kill: "LIFECYCLE GATE: initAll()" — differentiates from hint text
    it('Given INITIALIZED state, When initAll called again, Then error message opens with "LIFECYCLE GATE: initAll()"', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        const err = await sup.initAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/LIFECYCLE GATE: initAll\(\)/);
    });

    it('Given CREATED state, When startAll called, Then error message includes "startAll"', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/startAll/);
    });

    // Precision kill: "LIFECYCLE GATE: startAll()"
    it('Given CREATED state, When startAll called, Then error message opens with "LIFECYCLE GATE: startAll()"', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/LIFECYCLE GATE: startAll\(\)/);
    });

    it('Given INITIALIZED state, When stopAll called, Then error message includes "stopAll"', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        const err = await sup.stopAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/stopAll/);
    });

    // Precision kill: "LIFECYCLE GATE: stopAll()"
    it('Given INITIALIZED state, When stopAll called, Then error message opens with "LIFECYCLE GATE: stopAll()"', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        const err = await sup.stopAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/LIFECYCLE GATE: stopAll\(\)/);
    });

    it('Given INITIALIZED state, When registerPlugin called, Then error message includes "registerPlugin"', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        let err: unknown;
        try { sup.registerPlugin(new MockPlugin('Q')); } catch (e) { err = e; }
        expect((err as Error).message).toMatch(/registerPlugin/);
    });

    // Precision kill: "LIFECYCLE GATE: registerPlugin(" — not in hint text
    it('Given INITIALIZED state, When registerPlugin called, Then error message opens with "LIFECYCLE GATE: registerPlugin("', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        let err: unknown;
        try { sup.registerPlugin(new MockPlugin('Q')); } catch (e) { err = e; }
        expect((err as Error).message).toMatch(/LIFECYCLE GATE: registerPlugin\(/);
    });

    it('Given INITIALIZED state, When registerPlugin called, Then error message includes "CREATED" (allowed state)', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        let err: unknown;
        try { sup.registerPlugin(new MockPlugin('Q')); } catch (e) { err = e; }
        expect((err as Error).message).toMatch(/CREATED/);
    });

    it('Given CREATED state startAll error, Then message includes "STOPPED" in allowed states', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/STOPPED/);
    });

    it('Given CREATED state startAll error, Then allowed states are joined with " or " separator', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/INITIALIZED or STOPPED/);
    });

    it('Given CREATED state startAll error, Then Allowed field uses ", " separator', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/INITIALIZED, STOPPED/);
    });

    it('Given error from wrong-state call, Then message includes "but supervisor is in state"', async () => {
        const sup = new PluginSupervisor();
        const err = await sup.startAll().catch((e: unknown) => e);
        expect((err as Error).message).toMatch(/but supervisor is in state/);
    });

    it('Given duplicate plugin error, Then message includes hint about "destroyAll"', () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        let err: unknown;
        try { sup.registerPlugin(new MockPlugin('P')); } catch (e) { err = e; }
        expect((err as Error).message).toMatch(/destroyAll/);
    });

});

// ─── Hard behavioral: destroyAll DESTROYED guard (idempotency + skip) ────────
// Kills: ConditionalExpression if(false) and StringLiteral 'DESTROYED'→''
// The log-message string inside the guard is INTENTIONALLY NOT tested — those
// are implementation-detail StringLiteral mutants we allow to survive (goldilocks).

describe('PluginSupervisor — destroyAll DESTROYED guard (behavioral)', () => {

    it('Given state=DESTROYED, When destroyAll called again, Then getState() still returns DESTROYED', async () => {
        const sup = new PluginSupervisor();
        await sup.destroyAll();
        await sup.destroyAll(); // second call
        expect(sup.getState()).toBe('DESTROYED');
    });

    it('Given plugin destroyed once, When destroyAll called twice, Then plugin.destroy NOT called on second call', async () => {
        const sup = new PluginSupervisor();
        const p = new MockPlugin('P');
        sup.registerPlugin(p);
        await sup.initAll(); await sup.startAll(); await sup.stopAll();
        await sup.destroyAll();
        const countAfterFirst = p.destroyCalled;
        await sup.destroyAll();
        // Count must NOT increase — the guard must short-circuit
        expect(p.destroyCalled).toBe(countAfterFirst);
    });

});

// ─── Hard behavioral: PAL conditional (registry.has guard) ──────────────────
// Tests the BEHAVIOR of the guard (overwrite semantics), not the log string.

describe('PathAbstractionLayer — overwrite guard contract', () => {

    it('Given a key registered once, When registered again with a different value, Then resolve returns second value', () => {
        const pal = new PathAbstractionLayer();
        pal.register('K', 'first');
        pal.register('K', 'second');
        expect(pal.resolve<string>('K')).toBe('second');
    });

    it('Given a key NOT previously registered, When registered, Then resolve immediately returns it', () => {
        const pal = new PathAbstractionLayer();
        pal.register('Fresh', { x: 1 });
        expect(pal.resolve<{ x: number }>('Fresh')).toEqual({ x: 1 });
    });

    it('Given two different keys, When both registered, Then each resolves independently', () => {
        const pal = new PathAbstractionLayer();
        pal.register('A', 100);
        pal.register('B', 200);
        expect(pal.resolve<number>('A')).toBe(100);
        expect(pal.resolve<number>('B')).toBe(200);
    });

});

// ─── Hard behavioral: fail-closed semantics in initAll + startAll ─────────────
// Tests WHAT gets skipped when a throw occurs — not the log messages.

describe('PluginSupervisor — fail-closed ordering contract', () => {

    it('Given [Good, Bad] registration order, When initAll throws on Bad, Then Good was initialized but Bad was not', async () => {
        const sup = new PluginSupervisor();
        const good = new MockPlugin('Good');
        const bad = new MockPlugin('Bad');
        bad.shouldThrowOnInit = true;
        sup.registerPlugin(good);
        sup.registerPlugin(bad);
        try { await sup.initAll(); } catch { /* expected */ }
        expect(good.initCalled).toBe(1);  // ran before Bad
        expect(bad.initCalled).toBe(1);   // attempted, threw
    });

    it('Given [Bad, Good] registration order, When initAll throws on Bad, Then Good.init is NEVER called (fail-closed)', async () => {
        const sup = new PluginSupervisor();
        const bad = new MockPlugin('Bad');
        const good = new MockPlugin('Good');
        bad.shouldThrowOnInit = true;
        sup.registerPlugin(bad);  // Bad first
        sup.registerPlugin(good); // Good after
        try { await sup.initAll(); } catch { /* expected */ }
        expect(bad.initCalled).toBe(1);   // attempted, threw
        expect(good.initCalled).toBe(0);  // never reached — fail-closed
    });

    it('Given [Bad, Good] registration order, When startAll throws on Bad, Then Good.start is NEVER called (fail-closed)', async () => {
        const sup = new PluginSupervisor();
        const bad = new MockPlugin('Bad');
        const good = new MockPlugin('Good');
        bad.shouldThrowOnStart = true;
        sup.registerPlugin(bad);
        sup.registerPlugin(good);
        await sup.initAll();
        try { await sup.startAll(); } catch { /* expected */ }
        expect(good.startCalled).toBe(0); // never reached
    });

});

// ─── Hard behavioral: emergency teardown (RUNNING → destroyAll skips stop) ────

describe('PluginSupervisor — emergency teardown from RUNNING', () => {

    it('Given state=RUNNING, When destroyAll called directly, Then plugin.stop is NOT called', async () => {
        const sup = new PluginSupervisor();
        const p = new MockPlugin('P');
        sup.registerPlugin(p);
        await sup.initAll(); await sup.startAll();
        await sup.destroyAll(); // bypass stopAll
        expect(p.stopCalled).toBe(0); // stop must NOT have been called
    });

    it('Given state=RUNNING, When destroyAll called, Then plugin.destroy IS called once', async () => {
        const sup = new PluginSupervisor();
        const p = new MockPlugin('P');
        sup.registerPlugin(p);
        await sup.initAll(); await sup.startAll();
        await sup.destroyAll();
        expect(p.destroyCalled).toBe(1);
    });

    it('Given state=CREATED (never initialized), When destroyAll called, Then plugin.destroy IS called', async () => {
        const sup = new PluginSupervisor();
        const p = new MockPlugin('P');
        sup.registerPlugin(p);
        await sup.destroyAll(); // cold teardown
        expect(p.destroyCalled).toBe(1);
    });

});

// ─── Hard behavioral: full multi-cycle restart ───────────────────────────────

describe('PluginSupervisor — multi-cycle restart correctness', () => {

    it('Given two full start→stop→restart cycles, When completed, Then state=RUNNING', async () => {
        const sup = new PluginSupervisor();
        sup.registerPlugin(new MockPlugin('P'));
        await sup.initAll();
        await sup.startAll(); await sup.stopAll(); // cycle 1
        await sup.startAll(); await sup.stopAll(); // cycle 2
        await sup.startAll();
        expect(sup.getState()).toBe('RUNNING');
    });

    it('Given two restart cycles, When completed, Then plugin.start count matches cycle count', async () => {
        const sup = new PluginSupervisor();
        const p = new MockPlugin('P');
        sup.registerPlugin(p);
        await sup.initAll();
        await sup.startAll(); await sup.stopAll();
        await sup.startAll(); await sup.stopAll();
        await sup.startAll();
        expect(p.startCalled).toBe(3); // exactly 3 starts, not 1 or 0
    });

    it('Given two restart cycles, When completed, Then plugin.init count is exactly 1 (init is not repeated)', async () => {
        const sup = new PluginSupervisor();
        const p = new MockPlugin('P');
        sup.registerPlugin(p);
        await sup.initAll();
        await sup.startAll(); await sup.stopAll();
        await sup.startAll(); await sup.stopAll();
        expect(p.initCalled).toBe(1);
    });

});

// ─── Hard behavioral: EventBus identity across plugins ───────────────────────

describe('PluginSupervisor — EventBus identity contract', () => {

    it('Given two plugins, When both initialized, Then both receive the same EventBus reference', async () => {
        const sup = new PluginSupervisor();
        const p1 = new MockPlugin('P1');
        const p2 = new MockPlugin('P2');
        sup.registerPlugin(p1); sup.registerPlugin(p2);
        await sup.initAll();
        expect(p1.receivedContext!.eventBus).toBe(p2.receivedContext!.eventBus);
    });

    it('Given external EventBus injected, When plugins initialized, Then all receive the injected instance', async () => {
        const externalBus = new EventBus();
        const sup = new PluginSupervisor(externalBus);
        const p1 = new MockPlugin('P1');
        const p2 = new MockPlugin('P2');
        sup.registerPlugin(p1); sup.registerPlugin(p2);
        await sup.initAll();
        expect(p1.receivedContext!.eventBus).toBe(externalBus);
        expect(p2.receivedContext!.eventBus).toBe(externalBus);
    });

});
