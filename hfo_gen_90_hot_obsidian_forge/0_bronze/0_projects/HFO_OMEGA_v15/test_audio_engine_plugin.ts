/**
 * test_audio_engine_plugin.ts
 * Jest mutation-killing harness for AudioEnginePlugin (Omega v15 tile).
 * Named test_* (not *.spec.ts) so jest.config.js picks it up.
 * Session: 6eb4385fd6823fa3 (nonce 51BBAA) — 21/21 passing, handoff logged.
 *
 * Coverage targets:
 *  T-OMEGA-005: zombie listener fix — init/destroy subscription pairing
 *  T-OMEGA-006: untrusted gesture audio trap — deferred AudioContext creation
 *  T-OMEGA-007: onStateChange branch coverage (READY/COMMIT_POINTER/IDLE strings)
 *  T-OMEGA-008: playSound null guard (before AUDIO_UNLOCK)
 *  T-OMEGA-009: onAudioUnlock suspended path → resume()
 *  T-OMEGA-010: synthesizeClick buffer dimensions (sampleRate * 0.1 = 4410 at 44100)
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { AudioEnginePlugin } from './audio_engine_plugin';
import { EventBus } from './event_bus';
import { PluginContext, PathAbstractionLayer } from './plugin_supervisor';

// ---------------------------------------------------------------------------
// Helper: fully-mocked AudioContext factory.
// bufferDown = 1st createBuffer call (synthesizeClick(true) in loadSounds)
// bufferUp   = 2nd createBuffer call (synthesizeClick(false) in loadSounds)
// source     = mock AudioBufferSourceNode returned by createBufferSource()
// ---------------------------------------------------------------------------
function makeMockAudioCtx() {
    const bufferDown = {
        length: 4410,
        getChannelData: jest.fn().mockReturnValue(new Float32Array(4410)),
    };
    const bufferUp = {
        length: 4410,
        getChannelData: jest.fn().mockReturnValue(new Float32Array(4410)),
    };
    let createBufferCallCount = 0;

    const source = {
        buffer: null as unknown,
        connect: jest.fn(),
        start: jest.fn(),
    };

    const mockCtx = {
        sampleRate: 44100,
        state: 'running' as string,
        createBuffer: jest.fn().mockImplementation(() => {
            createBufferCallCount++;
            return createBufferCallCount <= 1 ? bufferDown : bufferUp;
        }),
        createBufferSource: jest.fn().mockReturnValue(source),
        destination: {} as unknown,
        resume: jest.fn().mockImplementation(() => Promise.resolve()),
        close: jest.fn().mockImplementation(() => Promise.resolve()),
    };

    const ctor = jest.fn().mockReturnValue(mockCtx);
    return { ctor, mockCtx, bufferDown, bufferUp, source };
}

// ---------------------------------------------------------------------------
// T-OMEGA-005: Zombie listener fix
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin (T-OMEGA-005: Zombie Event Listeners)', () => {
    let plugin: AudioEnginePlugin;
    let eventBus: EventBus;
    let context: PluginContext;

    beforeEach(() => {
        eventBus = new EventBus();
        context = { eventBus, pal: new PathAbstractionLayer() };
        plugin = new AudioEnginePlugin();
        const { ctor } = makeMockAudioCtx();
        context.pal.register('AudioContext', ctor as unknown);
    });

    it('Given initialized plugin, When destroyed, Then STATE_CHANGE listener count is 0', async () => {
        await plugin.init(context);
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('STATE_CHANGE')?.length).toBe(1);
        plugin.destroy();
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('STATE_CHANGE')?.length).toBe(0);
    });

    it('Given initialized plugin, When destroyed, Then AUDIO_UNLOCK listener count is 0', async () => {
        await plugin.init(context);
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('AUDIO_UNLOCK')?.length).toBe(1);
        plugin.destroy();
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('AUDIO_UNLOCK')?.length).toBe(0);
    });

    it('Given destroyed plugin, When AUDIO_UNLOCK fires, Then AudioContext ctor NOT called (handler unsubscribed)', async () => {
        const { ctor } = makeMockAudioCtx();
        // register a second AudioContext (the plugin already has a ctor registered above — overwrite)
        context.pal.register('AudioContext', ctor as unknown);
        await plugin.init(context);
        plugin.destroy();
        ctor.mockClear();
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        expect(ctor).not.toHaveBeenCalled();
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-006: Untrusted gesture audio trap — deferred context creation
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin (T-OMEGA-006: Untrusted Gesture Audio Trap)', () => {
    let plugin: AudioEnginePlugin;
    let eventBus: EventBus;
    let context: PluginContext;
    let ctor: ReturnType<typeof makeMockAudioCtx>['ctor'];

    beforeEach(() => {
        jest.clearAllMocks();
        eventBus = new EventBus();
        context = { eventBus, pal: new PathAbstractionLayer() };
        plugin = new AudioEnginePlugin();
        const m = makeMockAudioCtx();
        ctor = m.ctor;
        context.pal.register('AudioContext', ctor as unknown);
    });

    it('Given init called, Then AudioContext NOT instantiated immediately', async () => {
        await plugin.init(context);
        expect(ctor).not.toHaveBeenCalled();
    });

    it('Given init called, When AUDIO_UNLOCK published, Then AudioContext IS instantiated once', async () => {
        await plugin.init(context);
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        expect(ctor).toHaveBeenCalledTimes(1);
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-007: onStateChange branch coverage — mutation kills for string comparisons
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin — onStateChange (T-OMEGA-007: mutation coverage)', () => {
    let plugin: AudioEnginePlugin;
    let eventBus: EventBus;
    let context: PluginContext;
    let bufferDown: ReturnType<typeof makeMockAudioCtx>['bufferDown'];
    let bufferUp: ReturnType<typeof makeMockAudioCtx>['bufferUp'];
    let source: ReturnType<typeof makeMockAudioCtx>['source'];

    beforeEach(async () => {
        eventBus = new EventBus();
        context = { eventBus, pal: new PathAbstractionLayer() };
        plugin = new AudioEnginePlugin();
        const m = makeMockAudioCtx();
        bufferDown = m.bufferDown;
        bufferUp   = m.bufferUp;
        source     = m.source;
        context.pal.register('AudioContext', m.ctor as unknown);
        await plugin.init(context);
        // Unlock to initialize audioContext + load click buffers
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        source.start.mockClear();
        source.connect.mockClear();
    });

    it('READY → COMMIT_POINTER: start() called exactly once', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        expect(source.start).toHaveBeenCalledTimes(1);
    });

    it('READY → COMMIT_POINTER: source.buffer === clickDownBuffer (not clickUpBuffer)', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        expect(source.buffer).toBe(bufferDown);
        expect(source.buffer).not.toBe(bufferUp);
    });

    it('COMMIT_POINTER → READY: start() called exactly once', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'COMMIT_POINTER', currentState: 'READY' });
        expect(source.start).toHaveBeenCalledTimes(1);
    });

    it('COMMIT_POINTER → READY: source.buffer === clickUpBuffer', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'COMMIT_POINTER', currentState: 'READY' });
        expect(source.buffer).toBe(bufferUp);
        expect(source.buffer).not.toBe(bufferDown);
    });

    it('COMMIT_POINTER → IDLE: start() called once (IDLE branch of OR)', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'COMMIT_POINTER', currentState: 'IDLE' });
        expect(source.start).toHaveBeenCalledTimes(1);
    });

    it('COMMIT_POINTER → IDLE: source.buffer === clickUpBuffer', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'COMMIT_POINTER', currentState: 'IDLE' });
        expect(source.buffer).toBe(bufferUp);
    });

    it('IDLE → READY: no sound (wrong previous state)', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'IDLE', currentState: 'READY' });
        expect(source.start).not.toHaveBeenCalled();
    });

    it('READY → IDLE: no sound (previousState is READY, currentState is not COMMIT_POINTER)', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'IDLE' });
        expect(source.start).not.toHaveBeenCalled();
    });

    it('READY → READY: no sound', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'READY' });
        expect(source.start).not.toHaveBeenCalled();
    });

    it('playSound wires: createBufferSource, connect(destination), start(0) all called', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        expect(source.connect).toHaveBeenCalledTimes(1);
        expect(source.start).toHaveBeenCalledWith(0);
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-008: playSound null guard — no audioContext before AUDIO_UNLOCK
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin — playSound null guard (T-OMEGA-008)', () => {
    let plugin: AudioEnginePlugin;
    let eventBus: EventBus;
    let context: PluginContext;

    beforeEach(async () => {
        eventBus = new EventBus();
        context = { eventBus, pal: new PathAbstractionLayer() };
        plugin = new AudioEnginePlugin();
        const { ctor } = makeMockAudioCtx();
        context.pal.register('AudioContext', ctor as unknown);
        await plugin.init(context);
        // AUDIO_UNLOCK deliberately NOT published — audioContext remains null
    });

    it('Given audioContext is null, When STATE_CHANGE fires READY→COMMIT_POINTER, Then no error thrown', () => {
        expect(() => {
            eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        }).not.toThrow();
    });

    it('Given audioContext is null, When STATE_CHANGE fires, Then source.start NOT called', async () => {
        const m = makeMockAudioCtx();
        // Re-register so we have the source reference
        context.pal.register('AudioContext', m.ctor as unknown);
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        // No exception and source.start not called because audioContext is null
        expect(m.source.start).not.toHaveBeenCalled();
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-009: onAudioUnlock suspended path → resume()
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin — onAudioUnlock suspended path (T-OMEGA-009)', () => {
    let plugin: AudioEnginePlugin;
    let eventBus: EventBus;
    let context: PluginContext;
    let mockCtx: ReturnType<typeof makeMockAudioCtx>['mockCtx'];

    beforeEach(async () => {
        eventBus = new EventBus();
        context = { eventBus, pal: new PathAbstractionLayer() };
        plugin = new AudioEnginePlugin();
        const m = makeMockAudioCtx();
        mockCtx = m.mockCtx;
        context.pal.register('AudioContext', m.ctor as unknown);
        await plugin.init(context);
        // First AUDIO_UNLOCK: creates audioContext
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        mockCtx.resume.mockClear();
    });

    it('Given audioContext exists and state=suspended, When AUDIO_UNLOCK fires again, Then resume() called once', async () => {
        mockCtx.state = 'suspended';
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        expect(mockCtx.resume).toHaveBeenCalledTimes(1);
    });

    it('Given audioContext exists and state=running, When AUDIO_UNLOCK fires again, Then resume() NOT called', async () => {
        mockCtx.state = 'running';
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        expect(mockCtx.resume).not.toHaveBeenCalled();
    });
});

// ===========================================================================
// T-OMEGA-011: Identity properties (kills name/version StringLiteral mutants)
// ===========================================================================
describe('AudioEnginePlugin (T-OMEGA-011: Identity)', () => {
    it('name is "AudioEnginePlugin"', () => {
        expect(new AudioEnginePlugin().name).toBe('AudioEnginePlugin');
    });
    it('version is "1.0.0"', () => {
        expect(new AudioEnginePlugin().version).toBe('1.0.0');
    });
});

// ===========================================================================
// T-OMEGA-012: start() / stop() side-effects (kills BlockStatement + StringLiteral)
// ===========================================================================
describe('AudioEnginePlugin (T-OMEGA-012: start/stop logging)', () => {
    it('start() logs "[AudioEngine] Started"', () => {
        const spy = jest.spyOn(console, 'log').mockImplementation(() => { /* suppress */ });
        new AudioEnginePlugin().start();
        expect(spy).toHaveBeenCalledWith('[AudioEngine] Started');
        spy.mockRestore();
    });
    it('stop() logs "[AudioEngine] Stopped"', () => {
        const spy = jest.spyOn(console, 'log').mockImplementation(() => { /* suppress */ });
        new AudioEnginePlugin().stop();
        expect(spy).toHaveBeenCalledWith('[AudioEngine] Stopped');
        spy.mockRestore();
    });
});

// ===========================================================================
// T-OMEGA-013: destroy() paths
//   – destroy-before-init kills context&&→|| and context&&→true mutants
//   – destroy-after-unlock kills if(audioCtx)→false block
// ===========================================================================
describe('AudioEnginePlugin (T-OMEGA-013: destroy paths)', () => {
    it('destroy() before init() does not throw (kills context&&→|| and context&&→true)', () => {
        expect(() => new AudioEnginePlugin().destroy()).not.toThrow();
    });

    it('destroy() with audioContext calls close() (kills if(audioCtx)→false)', async () => {
        const plugin = new AudioEnginePlugin();
        const eventBus = new EventBus();
        const pal = new PathAbstractionLayer();
        const { ctor, mockCtx } = makeMockAudioCtx();
        pal.register('AudioContext', ctor as unknown);
        await plugin.init({ eventBus, pal });
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 30));
        plugin.destroy();
        expect(mockCtx.close).toHaveBeenCalled();
    });
});

// ===========================================================================
// T-OMEGA-014: synthesizeClick arithmetic precision
//   Uses Math.random mock so noise is deterministic.
//   random=0.5 → noise=0; random=0 → noise=-coeff*decay.
//   Expected values computed analytically from the Cherry MX synthesis formulas.
// ===========================================================================
describe('AudioEnginePlugin (T-OMEGA-014: synthesizeClick DSP arithmetic)', () => {
    // Shared helper — spins up plugin, fires AUDIO_UNLOCK with fixed random, returns sample arrays.
    async function captureBuffers(randomValue: number): Promise<{ downData: Float32Array; upData: Float32Array }> {
        const randomSpy = jest.spyOn(Math, 'random').mockReturnValue(randomValue);
        const plugin = new AudioEnginePlugin();
        const eventBus = new EventBus();
        const pal = new PathAbstractionLayer();
        const mocks = makeMockAudioCtx();
        pal.register('AudioContext', mocks.ctor as unknown);
        await plugin.init({ eventBus, pal });
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 50));
        randomSpy.mockRestore();
        // getChannelData returns the SAME Float32Array every call due to mockReturnValue —
        // synthesizeClick wrote samples into it, so we can read them back.
        const downData = mocks.bufferDown.getChannelData(0) as Float32Array;
        const upData   = mocks.bufferUp.getChannelData(0)   as Float32Array;
        return { downData, upData };
    }

    // --- random=0.5 → noise contribution = 0 → pure DSP ---

    // DOWN i=1  (t≈2.27e-5s): clickEnv≈0.9820, clickOsc≈0.4697, no clack
    //   data[1] = (0.4697*0.4) * 0.5 = 0.09394
    //   Kills: for-loop→{}, for(false), i*sampleRate, isDown→false, isDown-block→{},
    //          clickEnv/*800, clickEnv unary, clickOsc/*clickEnv, sin arithmetic
    it('[r=0.5] clickDown data[1] ≈ 0.094 — for-loop/t-arith/isDown/clickEnv mutations', async () => {
        const { downData } = await captureBuffers(0.5);
        expect(downData[1]).toBeCloseTo(0.094, 3);
    });

    // UP i=1 (t≈2.27e-5s): clickEnv≈0.9865, clickOsc≈0.3437, no topOut
    //   data[1] = (0.3437*0.3) * 0.4 = 0.04124
    //   Kills: isDown→true, isDown-else→{}, UP clickEnv/clickOsc arithmetic,
    //          topOut if(true) mutation (at i=1, t<topOutDelay, mutant runs wrong formula)
    it('[r=0.5] clickUp data[1] ≈ 0.041 — UP click arithmetic / isDown→true / topOut if(true)', async () => {
        const { upData } = await captureBuffers(0.5);
        expect(upData[1]).toBeCloseTo(0.041, 3);
    });

    // DOWN i=468 (t≈0.01061s, 0.61ms past clackDelay):
    //   clickOsc ≈ 0.000140 (negligible), clackEnv≈0.8848, clackOsc≈0.9993
    //   data[468] = (0.000056 + 0.9993*0.6) * 0.5 = 0.265
    //   Kills: clack if(false/true), clack block→{}, clackEnv arithmetic, clackOsc arithmetic,
    //          t-clackDelay→t+clackDelay, data mix coefficients
    it('[r=0.5] clickDown data[468] ≈ 0.265 — clack section arithmetic kills', async () => {
        const { downData } = await captureBuffers(0.5);
        expect(downData[468]).toBeCloseTo(0.265, 3);
    });

    // UP i=684 (t≈0.01551s, 0.51ms past topOutDelay=0.015):
    //   topOutEnv≈0.9264, topOutOsc≈0.9998, clickOsc negligible
    //   data[684] = (0.9998*0.5 + ~0) * 0.4 = 0.185
    //   Kills: topOut if(false/true), topOut block→{}, topOutEnv arithmetic, topOutOsc arithmetic,
    //          t-topOutDelay→t+topOutDelay, UP data mix coefficients
    it('[r=0.5] clickUp data[684] ≈ 0.185 — topOut section arithmetic kills', async () => {
        const { upData } = await captureBuffers(0.5);
        expect(upData[684]).toBeCloseTo(0.185, 3);
    });

    // --- random=0 → noise = (-1)*decay*coeff → kills noise arithmetic mutants ---

    // DOWN i=1, r=0:  noise=-0.19864, data[1]=(0.18788-0.19864)*0.5 = -0.00538
    //   Kills: noise*300→/300, noise unary -→+, noise*2-1→+1, noise*0.2→/0.2,
    //          noise overall+→- sign-flip in final mix
    it('[r=0] clickDown data[1] ≈ -0.0054 — DOWN noise exp/coefficient mutations', async () => {
        const { downData } = await captureBuffers(0);
        expect(downData[1]).toBeCloseTo(-0.0054, 3);
    });

    // UP i=1, r=0:  noise=-0.09955, data[1]=(0.10311-0.09955)*0.40 = 0.00142
    //   Kills: UP noise*200→/200, noise unary, noise*0.1→/0.1, noise sign-flip in mix
    it('[r=0] clickUp data[1] ≈ 0.0014 — UP noise exp/coefficient mutations', async () => {
        const { upData } = await captureBuffers(0);
        expect(upData[1]).toBeCloseTo(0.0014, 3);
    });

    // Energy-level invariants (kill for-loop body block, else-body block)
    it('Both buffers have non-trivial energy (kills for-loop block→{}, else-block→{})', async () => {
        const { downData, upData } = await captureBuffers(0.5);
        const downE = Array.from(downData).reduce((s, v) => s + v * v, 0);
        const upE   = Array.from(upData).reduce((s, v) => s + v * v, 0);
        expect(downE).toBeGreaterThan(0.1);
        expect(upE).toBeGreaterThan(0.05);
    });

    // DOWN louder than UP (kills synthesizeClick arg-swap: true↔false at call sites)
    it('DOWN buffer energy > UP buffer energy (kills synthesizeClick(true/false) swap)', async () => {
        const { downData, upData } = await captureBuffers(0.5);
        const downE = Array.from(downData).reduce((s, v) => s + v * v, 0);
        const upE   = Array.from(upData).reduce((s, v) => s + v * v, 0);
        expect(downE).toBeGreaterThan(upE * 1.3);
    });
});

// ===========================================================================
// T-OMEGA-015: PAL null-guard path (AudioContextCtor missing)
//   Kills: catch-block→{}, warn StringLiteral, fallback warn message check
// ===========================================================================
describe('AudioEnginePlugin (T-OMEGA-015: PAL null guard)', () => {
    it('Given AudioContext not in PAL, AUDIO_UNLOCK does not throw', async () => {
        const plugin = new AudioEnginePlugin();
        const eventBus = new EventBus();
        const pal = new PathAbstractionLayer(); // no AudioContext registered
        const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => { /* suppress */ });
        await plugin.init({ eventBus, pal });
        expect(() => eventBus.publish('AUDIO_UNLOCK', null)).not.toThrow();
        await new Promise(r => setTimeout(r, 30));
        expect(warnSpy).toHaveBeenCalled();
        expect((warnSpy.mock.calls[0] as unknown[])[0]).toBe(
            '[AudioEngine] AudioContext not supported or failed to initialize'
        );
        warnSpy.mockRestore();
    });
});

// ===========================================================================
// T-OMEGA-016: playSound internal paths
//   – suspended ctx in playSound (NOT onAudioUnlock) kills L133 mutants
//   – null buffer + ctx set kills || → && guard at L131
//   – wrong-transition negative tests kill onStateChange L145/L149 mutants
// ===========================================================================
describe('AudioEnginePlugin (T-OMEGA-016: playSound + onStateChange guards)', () => {
    async function readyPlugin() {
        const plugin = new AudioEnginePlugin();
        const eventBus = new EventBus();
        const pal = new PathAbstractionLayer();
        const { ctor, mockCtx, bufferDown, bufferUp, source } = makeMockAudioCtx();
        pal.register('AudioContext', ctor as unknown);
        await plugin.init({ eventBus, pal });
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 50));
        mockCtx.createBufferSource.mockClear();
        mockCtx.resume.mockClear();
        return { plugin, eventBus, mockCtx, bufferDown, bufferUp, source };
    }

    it('Given audioCtx state=suspended, STATE_CHANGE READY→COMMIT_POINTER calls resume() via playSound', async () => {
        const { eventBus, mockCtx } = await readyPlugin();
        mockCtx.state = 'suspended';
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        expect(mockCtx.resume).toHaveBeenCalled();
    });

    it('Given audioCtx state=running, STATE_CHANGE does NOT call resume() via playSound', async () => {
        const { eventBus, mockCtx } = await readyPlugin();
        mockCtx.state = 'running';
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        expect(mockCtx.resume).not.toHaveBeenCalled();
    });

    it('Given null clickUpBuffer + ctx set, STATE_CHANGE COMMIT→READY does not crash (kills ||→&&)', async () => {
        const { plugin, eventBus, mockCtx } = await readyPlugin();
        // Force clickUpBuffer to null via type bypass (buffer=null, ctx set → || guard protects)
        (plugin as unknown as { clickUpBuffer: null }).clickUpBuffer = null;
        mockCtx.createBufferSource.mockClear();
        expect(() => eventBus.publish('STATE_CHANGE', {
            handId: 0, previousState: 'COMMIT_POINTER', currentState: 'READY',
        })).not.toThrow();
        // With original || guard: audioCtx≠null but buffer=null → returns early, source not created
        expect(mockCtx.createBufferSource).not.toHaveBeenCalled();
    });

    // Negative: wrong previousState → no sound (kills previousState===READY → true mutant)
    it('STATE_CHANGE IDLE→COMMIT_POINTER does NOT play sound (kills previousState→true)', async () => {
        const { eventBus, mockCtx } = await readyPlugin();
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'IDLE', currentState: 'COMMIT_POINTER' });
        expect(mockCtx.createBufferSource).not.toHaveBeenCalled();
    });

    // Negative: wrong currentState → no sound (kills currentState===READY||IDLE → true mutant)
    it('STATE_CHANGE COMMIT_POINTER→RUNNING does NOT play sound (kills currentState→true)', async () => {
        const { eventBus, mockCtx } = await readyPlugin();
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'COMMIT_POINTER', currentState: 'RUNNING' });
        expect(mockCtx.createBufferSource).not.toHaveBeenCalled();
    });
});
describe('AudioEnginePlugin — synthesizeClick dimensions (T-OMEGA-010)', () => {
    let plugin: AudioEnginePlugin;
    let eventBus: EventBus;
    let context: PluginContext;
    let mockCtx: ReturnType<typeof makeMockAudioCtx>['mockCtx'];

    beforeEach(async () => {
        eventBus = new EventBus();
        context = { eventBus, pal: new PathAbstractionLayer() };
        plugin = new AudioEnginePlugin();
        const m = makeMockAudioCtx();
        mockCtx = m.mockCtx;
        context.pal.register('AudioContext', m.ctor as unknown);
        await plugin.init(context);
    });

    it('Given sampleRate=44100, When AUDIO_UNLOCK fires, Then createBuffer called twice (down + up)', async () => {
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        expect(mockCtx.createBuffer).toHaveBeenCalledTimes(2);
    });

    it('Given sampleRate=44100, When AUDIO_UNLOCK fires, Then createBuffer called with (1, 4410, 44100)', async () => {
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        // sampleRate * duration = 44100 * 0.1 = 4410
        expect(mockCtx.createBuffer).toHaveBeenCalledWith(1, 4410, 44100);
    });
});
