import { Plugin, PluginContext } from './plugin_supervisor';

interface IAudioBuffer {
    length: number;
    getChannelData(channel: number): Float32Array;
}
interface IAudioBufferSourceNode {
    buffer: IAudioBuffer | null;
    connect(destination: unknown): void;
    start(when?: number): void;
}
interface IAudioContext {
    state: string;
    sampleRate: number;
    resume(): Promise<void>;
    createBuffer(numOfChannels: number, length: number, sampleRate: number): IAudioBuffer;
    createBufferSource(): IAudioBufferSourceNode;
    destination: unknown;
    close(): Promise<void>;
}

export class AudioEnginePlugin implements Plugin {
    public name = 'AudioEnginePlugin';
    public version = '1.0.0';
    private context!: PluginContext;
    private audioContext: IAudioContext | null = null;
    private clickDownBuffer: IAudioBuffer | null = null;
    private clickUpBuffer: IAudioBuffer | null = null;
    private boundOnStateChange: (data: { handId: number; previousState: string; currentState: string; }) => void;
    private boundOnAudioUnlock: () => void;

    constructor() {
        this.boundOnStateChange = this.onStateChange.bind(this);
        this.boundOnAudioUnlock = this.onAudioUnlock.bind(this);
    }

    public async init(context: PluginContext): Promise<void> {
        this.context = context;
        
        this.context.eventBus.subscribe('STATE_CHANGE', this.boundOnStateChange);
        this.context.eventBus.subscribe('AUDIO_UNLOCK', this.boundOnAudioUnlock);
    }

    private async onAudioUnlock() {
        if (!this.audioContext) {
            try {
                // ARCH-V5 PAL injection: bootstrapper registers 'AudioContext' in PAL.
                // Plugins must receive Host capabilities via PluginContext.pal
                const AudioContextCtor = this.context.pal.resolve<new () => IAudioContext>('AudioContext');
                if (!AudioContextCtor) {
                    throw new Error('AudioContext not available in this environment');
                }
                this.audioContext = new AudioContextCtor();
                await this.loadSounds();
                console.log('[AudioEngine] AudioContext instantiated and unlocked');
            } catch (e) {
                console.warn('[AudioEngine] AudioContext not supported or failed to initialize', e);
            }
        } else if (this.audioContext.state === 'suspended') {
            this.audioContext.resume().then(() => {
                console.log('[AudioEngine] AudioContext unlocked and resumed');
            }).catch((e: unknown) => {
                console.warn('[AudioEngine] Failed to resume AudioContext', e);
            });
        }
    }

    private async loadSounds() {
        if (!this.audioContext) return;

        // In a real scenario, we would fetch actual audio files.
        // For this implementation, we'll synthesize a mechanical keyboard sound.
        this.clickDownBuffer = this.synthesizeClick(true);
        this.clickUpBuffer = this.synthesizeClick(false);
    }

    private synthesizeClick(isDown: boolean): IAudioBuffer | null {
        if (!this.audioContext) return null;
        
        const sampleRate = this.audioContext.sampleRate;
        const duration = 0.1; // 100ms
        const buffer = this.audioContext.createBuffer(1, sampleRate * duration, sampleRate);
        const data = buffer.getChannelData(0);
        
        for (let i = 0; i < buffer.length; i++) {
            const t = i / sampleRate;
            
            if (isDown) {
                // Cherry MX Blue Click Down
                // Sharp high-frequency click at the start
                const clickEnv = Math.exp(-t * 800);
                const clickOsc = Math.sin(2 * Math.PI * 3500 * t) * clickEnv;
                
                // Lower frequency "clack" (bottom out) slightly delayed
                const clackDelay = 0.01;
                let clackOsc = 0;
                if (t > clackDelay) {
                    const clackEnv = Math.exp(-(t - clackDelay) * 200);
                    clackOsc = Math.sin(2 * Math.PI * 400 * (t - clackDelay)) * clackEnv;
                }
                
                // Noise for texture
                const noise = (Math.random() * 2 - 1) * Math.exp(-t * 300) * 0.2;
                
                data[i] = (clickOsc * 0.4 + clackOsc * 0.6 + noise) * 0.5;
            } else {
                // Cherry MX Blue Click Up
                // Softer click
                const clickEnv = Math.exp(-t * 600);
                const clickOsc = Math.sin(2 * Math.PI * 2500 * t) * clickEnv;
                
                // Top out sound
                const topOutDelay = 0.015;
                let topOutOsc = 0;
                if (t > topOutDelay) {
                    const topOutEnv = Math.exp(-(t - topOutDelay) * 150);
                    topOutOsc = Math.sin(2 * Math.PI * 500 * (t - topOutDelay)) * topOutEnv;
                }
                
                // Noise
                const noise = (Math.random() * 2 - 1) * Math.exp(-t * 200) * 0.1;
                
                data[i] = (clickOsc * 0.3 + topOutOsc * 0.5 + noise) * 0.4;
            }
        }
        
        return buffer;
    }

    private playSound(buffer: IAudioBuffer | null) {
        if (!this.audioContext || !buffer) return;
        
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }

        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(this.audioContext.destination);
        source.start(0);
    }

    private onStateChange(data: { handId: number, previousState: string, currentState: string }) {
        // Ready to Commit (click down)
        if (data.previousState === 'READY' && data.currentState === 'COMMIT_POINTER') {
            this.playSound(this.clickDownBuffer);
        }
        // Commit to Ready/Idle (click up)
        else if (data.previousState === 'COMMIT_POINTER' && (data.currentState === 'READY' || data.currentState === 'IDLE')) {
            this.playSound(this.clickUpBuffer);
        }
    }

    public start(): void {
        console.log('[AudioEngine] Started');
    }

    public stop(): void {
        console.log('[AudioEngine] Stopped');
    }

    public destroy(): void {
        if (this.context && this.context.eventBus) {
            this.context.eventBus.unsubscribe('STATE_CHANGE', this.boundOnStateChange);
            this.context.eventBus.unsubscribe('AUDIO_UNLOCK', this.boundOnAudioUnlock);
        }
        if (this.audioContext) {
            this.audioContext.close();
        }
    }
}
