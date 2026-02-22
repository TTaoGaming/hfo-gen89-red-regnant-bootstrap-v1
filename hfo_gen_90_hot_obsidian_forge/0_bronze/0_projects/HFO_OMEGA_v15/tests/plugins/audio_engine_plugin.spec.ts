import { AudioEnginePlugin } from '../../src/plugins/audio_engine_plugin';
import { EventBus } from '../../src/kernel/event_bus';

describe('AudioEnginePlugin', () => {
    let eventBus: EventBus;
    let plugin: AudioEnginePlugin;
    let mockAudioContext: any;
    let mockOscillator: any;
    let mockGainNode: any;

    beforeEach(() => {
        eventBus = new EventBus();
        
        mockOscillator = {
            type: 'sine',
            frequency: { setValueAtTime: jest.fn() },
            connect: jest.fn(),
            start: jest.fn(),
            stop: jest.fn(),
        };

        mockGainNode = {
            gain: { setValueAtTime: jest.fn(), exponentialRampToValueAtTime: jest.fn() },
            connect: jest.fn(),
        };

        mockAudioContext = {
            state: 'suspended',
            resume: jest.fn().mockResolvedValue(undefined),
            createOscillator: jest.fn().mockReturnValue(mockOscillator),
            createGain: jest.fn().mockReturnValue(mockGainNode),
            close: jest.fn().mockResolvedValue(undefined),
            destination: {},
            currentTime: 0,
        };

        (global as any).window = {
            AudioContext: jest.fn().mockImplementation(() => mockAudioContext),
            webkitAudioContext: jest.fn().mockImplementation(() => mockAudioContext),
        };

        plugin = new AudioEnginePlugin(eventBus);
    });

    afterEach(() => {
        plugin.destroy();
        delete (global as any).window;
    });

    it('should not instantiate AudioContext in constructor or init', () => {
        plugin.init();
        expect(global.window.AudioContext).not.toHaveBeenCalled();
        expect((global.window as any).webkitAudioContext).not.toHaveBeenCalled();
    });

    it('should instantiate and resume AudioContext when unlockAudioContext is called', async () => {
        await plugin.unlockAudioContext();
        expect(global.window.AudioContext).toHaveBeenCalled();
        expect(mockAudioContext.resume).toHaveBeenCalled();
    });

    it('should not resume AudioContext if it is not suspended', async () => {
        mockAudioContext.state = 'running';
        await plugin.unlockAudioContext();
        expect(mockAudioContext.resume).not.toHaveBeenCalled();
    });

    it('should not instantiate AudioContext if AudioContextClass is undefined', async () => {
        delete (global.window as any).AudioContext;
        delete (global.window as any).webkitAudioContext;
        await plugin.unlockAudioContext();
        expect(mockAudioContext.resume).not.toHaveBeenCalled();
    });

    it('should play a synthesized beep on COMMIT_POINTER if context is unlocked', async () => {
        await plugin.unlockAudioContext();
        
        eventBus.publish('COMMIT_POINTER', { x: 100, y: 100 });
        
        expect(mockAudioContext.createOscillator).toHaveBeenCalled();
        expect(mockAudioContext.createGain).toHaveBeenCalled();
        expect(mockOscillator.type).toBe('sine');
        expect(mockOscillator.connect).toHaveBeenCalledWith(mockGainNode);
        expect(mockGainNode.connect).toHaveBeenCalledWith(mockAudioContext.destination);
        expect(mockOscillator.start).toHaveBeenCalledWith(0);
        expect(mockOscillator.stop).toHaveBeenCalledWith(0.1);
        expect(mockGainNode.gain.exponentialRampToValueAtTime).toHaveBeenCalledWith(0.001, 0.1);
    });

    it('should not play a beep on COMMIT_POINTER if context is not unlocked', () => {
        eventBus.publish('COMMIT_POINTER', { x: 100, y: 100 });
        expect(mockAudioContext.createOscillator).not.toHaveBeenCalled();
    });

    it('Rule 5 (Zombie Defense): should cleanly unsubscribe in destroy()', async () => {
        await plugin.unlockAudioContext();
        
        plugin.destroy();
        
        eventBus.publish('COMMIT_POINTER', { x: 100, y: 100 });
        expect(mockAudioContext.createOscillator).not.toHaveBeenCalled();
        expect(mockAudioContext.close).toHaveBeenCalled();
    });

    it('should not throw in destroy if already destroyed', async () => {
        await plugin.unlockAudioContext();
        plugin.destroy();
        expect(() => plugin.destroy()).not.toThrow();
    });
});
