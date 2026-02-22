import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { AudioEnginePlugin } from './audio_engine_plugin';
import { EventBus } from './event_bus';
import { PluginContext, PathAbstractionLayer } from './plugin_supervisor';

// ---------------------------------------------------------------------------
// Helper: build a fully-mocked AudioContext factory.
// Returns { ctor, mockCtx, bufferDown, bufferUp, source }
// bufferDown = first buffer created (from synthesizeClick(true) in loadSounds)
// bufferUp   = second buffer created (from synthesizeClick(false) in loadSounds)
// ---------------------------------------------------------------------------
function makeMockAudioCtx() {
    const bufferDown = { length: 4410, getChannelData: jest.fn<() => Float32Array>().mockReturnValue(new Float32Array(4410)) };
    const bufferUp   = { length: 4410, getChannelData: jest.fn<() => Float32Array>().mockReturnValue(new Float32Array(4410)) };
    let createBufferCallCount = 0;

    const source = {
        buffer: null as unknown,
        connect: jest.fn<() => void>(),
        start: jest.fn<() => void>(),
    };

    const mockCtx = {
        sampleRate: 44100,
        state: 'running' as string,
        createBuffer: jest.fn<(...args: number[]) => typeof bufferDown>().mockImplementation(() => {
            createBufferCallCount++;
            return createBufferCallCount <= 1 ? bufferDown : bufferUp;
        }),
        createBufferSource: jest.fn<() => typeof source>().mockReturnValue(source),
        destination: {} as unknown,
        resume: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
        close: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
    };

    const ctor = jest.fn<() => typeof mockCtx>().mockReturnValue(mockCtx);
    return { ctor, mockCtx, bufferDown, bufferUp, source };
}

// ---------------------------------------------------------------------------
// T-OMEGA-005: Zombie listener fix — STATE_CHANGE
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

    it('Given an initialized plugin, When destroyed, Then STATE_CHANGE listener count drops to 0', async () => {
        await plugin.init(context);
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('STATE_CHANGE')?.length).toBe(1);
        plugin.destroy();
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('STATE_CHANGE')?.length).toBe(0);
    });

    it('Given an initialized plugin, When destroyed, Then AUDIO_UNLOCK listener count drops to 0', async () => {
        await plugin.init(context);
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('AUDIO_UNLOCK')?.length).toBe(1);
        plugin.destroy();
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('AUDIO_UNLOCK')?.length).toBe(0);
    });

    it('Given destroyed plugin, When AUDIO_UNLOCK fires, Then AudioContext ctor is NOT called (subscription removed)', async () => {
        const { ctor } = makeMockAudioCtx();
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
// T-OMEGA-006: Untrusted gesture audio trap — init does not eagerly create ctx
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

    it('Given init called, When AUDIO_UNLOCK published, Then AudioContext IS instantiated', async () => {
        await plugin.init(context);
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        expect(ctor).toHaveBeenCalledTimes(1);
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-007: onStateChange mutation coverage
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin — onStateChange (mutation coverage)', () => {
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
        // Unlock audio so audioContext + buffers get loaded
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
    });

    it('READY → COMMIT_POINTER: clickDown buffer plays (start called once)', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        expect(source.start).toHaveBeenCalledTimes(1);
    });

    it('READY → COMMIT_POINTER: source.buffer is clickDownBuffer, not clickUpBuffer', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        expect(source.buffer).toBe(bufferDown);
        expect(source.buffer).not.toBe(bufferUp);
    });

    it('COMMIT_POINTER → READY: clickUp buffer plays (start called once)', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'COMMIT_POINTER', currentState: 'READY' });
        expect(source.start).toHaveBeenCalledTimes(1);
    });

    it('COMMIT_POINTER → READY: source.buffer is clickUpBuffer', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'COMMIT_POINTER', currentState: 'READY' });
        expect(source.buffer).toBe(bufferUp);
    });

    it('COMMIT_POINTER → IDLE: clickUp buffer plays (IDLE branch)', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'COMMIT_POINTER', currentState: 'IDLE' });
        expect(source.start).toHaveBeenCalledTimes(1);
        expect(source.buffer).toBe(bufferUp);
    });

    it('IDLE → READY: no sound plays', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'IDLE', currentState: 'READY' });
        expect(source.start).not.toHaveBeenCalled();
    });

    it('READY → IDLE: no sound plays', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'IDLE' });
        expect(source.start).not.toHaveBeenCalled();
    });

    it('READY → READY: no sound plays', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'READY' });
        expect(source.start).not.toHaveBeenCalled();
    });

    it('playSound: createBufferSource called, connect called, start(0) called', () => {
        eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        expect(source.connect).toHaveBeenCalledTimes(1);
        expect(source.start).toHaveBeenCalledWith(0);
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-008: playSound null guard — no audio before AUDIO_UNLOCK
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin — playSound null guard', () => {
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
        // Do NOT publish AUDIO_UNLOCK — audioContext stays null
    });

    it('Given no AUDIO_UNLOCK fired, When STATE_CHANGE published, Then no error thrown', () => {
        expect(() => {
            eventBus.publish('STATE_CHANGE', { handId: 0, previousState: 'READY', currentState: 'COMMIT_POINTER' });
        }).not.toThrow();
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-009: onAudioUnlock suspended path — calls resume()
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin — onAudioUnlock suspended path', () => {
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
        // First unlock: creates the audioContext
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
    });

    it('Given audioContext was created, When AUDIO_UNLOCK fires again with state=suspended, Then resume() is called', async () => {
        mockCtx.state = 'suspended';
        mockCtx.resume.mockClear();
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        expect(mockCtx.resume).toHaveBeenCalledTimes(1);
    });

    it('Given audioContext was created and state=running, When AUDIO_UNLOCK fires again, Then resume() NOT called', async () => {
        mockCtx.state = 'running';
        mockCtx.resume.mockClear();
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        expect(mockCtx.resume).not.toHaveBeenCalled();
    });
});

// ---------------------------------------------------------------------------
// T-OMEGA-010: synthesizeClick buffer dimensions
// ---------------------------------------------------------------------------
describe('AudioEnginePlugin — synthesizeClick buffer dimensions', () => {
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

    it('Given sampleRate=44100, When AUDIO_UNLOCK fires, Then createBuffer called with length=4410 (sampleRate*0.1)', async () => {
        eventBus.publish('AUDIO_UNLOCK', null);
        await new Promise(r => setTimeout(r, 0));
        // loadSounds calls synthesizeClick(true) then synthesizeClick(false) → 2 createBuffer calls
        expect(mockCtx.createBuffer).toHaveBeenCalledTimes(2);
        // Both calls should use sampleRate * 0.1 = 4410 samples
        expect(mockCtx.createBuffer).toHaveBeenCalledWith(1, 4410, 44100);
    });
});
