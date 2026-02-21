import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { AudioEnginePlugin } from './audio_engine_plugin';
import { EventBus } from './event_bus';
import { PluginContext, PathAbstractionLayer } from './plugin_supervisor';

describe('AudioEnginePlugin (T-OMEGA-005: Zombie Event Listeners)', () => {
    let plugin: AudioEnginePlugin;
    let eventBus: EventBus;
    let context: PluginContext;

    beforeEach(() => {
        eventBus = new EventBus();
        context = {
            eventBus,
            pal: new PathAbstractionLayer()
        };
        plugin = new AudioEnginePlugin();
        
        // Mock AudioContext to avoid browser API errors in Node
        const mockAudioContext = jest.fn().mockImplementation(() => ({
            sampleRate: 44100,
            createBuffer: jest.fn().mockReturnValue({
                getChannelData: jest.fn().mockReturnValue(new Float32Array(4410))
            }),
            close: jest.fn()
        }));
        context.pal.register('AudioContext', mockAudioContext as unknown);
    });

    afterEach(() => {
        // Cleanup
    });

    it('Given an initialized AudioEnginePlugin, When it is destroyed, Then it should unsubscribe from the event bus to prevent zombie listeners', async () => {
        await plugin.init(context);
        
        // Verify it subscribed
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('STATE_CHANGE')?.length).toBe(1);
        
        // Destroy the plugin
        plugin.destroy();
        
        // Verify it unsubscribed
        expect((eventBus as unknown as { listeners: Map<string, unknown[]> }).listeners.get('STATE_CHANGE')?.length).toBe(0);
    });
});

describe('AudioEnginePlugin (T-OMEGA-006: Untrusted Gesture Audio Trap)', () => {
    let plugin: AudioEnginePlugin;
    let eventBus: EventBus;
    let context: PluginContext;

    let mockAudioContext: unknown;

    beforeEach(() => {
        jest.clearAllMocks();
        eventBus = new EventBus();
        context = {
            eventBus,
            pal: new PathAbstractionLayer()
        };
        plugin = new AudioEnginePlugin();
        
        // Mock AudioContext to avoid browser API errors in Node
        mockAudioContext = jest.fn().mockImplementation(() => ({
            sampleRate: 44100,
            createBuffer: jest.fn().mockReturnValue({
                getChannelData: jest.fn().mockReturnValue(new Float32Array(4410)),
                length: 4410
            }),
            close: jest.fn(),
            state: 'suspended',
            resume: jest.fn().mockReturnValue(Promise.resolve())
        }));
        context.pal.register('AudioContext', mockAudioContext);
    });

    afterEach(() => {
        // Cleanup
    });

    it('Given an uninitialized AudioEnginePlugin, When init is called, Then it should NOT instantiate AudioContext immediately', async () => {
        await plugin.init(context);
        expect(mockAudioContext).not.toHaveBeenCalled();
    });

    it('Given an initialized AudioEnginePlugin, When AUDIO_UNLOCK is published, Then it should instantiate AudioContext', async () => {
        await plugin.init(context);
        eventBus.publish('AUDIO_UNLOCK', null);
        
        // Wait for async operations
        await new Promise(resolve => setTimeout(resolve, 0));
        
        expect(mockAudioContext).toHaveBeenCalled();
    });
});
