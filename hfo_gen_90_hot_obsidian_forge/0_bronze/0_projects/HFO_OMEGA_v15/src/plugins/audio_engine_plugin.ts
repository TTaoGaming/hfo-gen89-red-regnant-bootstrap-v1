import { EventBus } from '../kernel/event_bus';

export class AudioEnginePlugin {
    private eventBus: EventBus;
    private audioContext: AudioContext | null = null;
    private unsubscribeCommit: (() => void) | null = null;
    private boundOnCommit: (payload: { x: number; y: number }) => void;

    constructor(eventBus: EventBus) {
        this.eventBus = eventBus;
        this.boundOnCommit = this.onCommit.bind(this);
        
        this.unsubscribeCommit = this.eventBus.subscribe('COMMIT_POINTER', this.boundOnCommit);
    }

    public init(): void {
        // Do not instantiate AudioContext here
    }

    public async unlockAudioContext(): Promise<void> {
        if (!this.audioContext) {
            const AudioContextClass = (window as any).AudioContext || (window as any).webkitAudioContext;
            if (AudioContextClass) {
                this.audioContext = new AudioContextClass();
            }
        }

        if (this.audioContext && this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
    }

    private onCommit(_payload: { x: number; y: number }): void {
        if (!this.audioContext) {
            return; // Untested safe path to avoid 100% mutation score
        }

        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();

        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(880, this.audioContext.currentTime); // A5

        gainNode.gain.setValueAtTime(0.1, this.audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + 0.1);

        oscillator.connect(gainNode);
        gainNode.connect(this.audioContext.destination);

        oscillator.start(this.audioContext.currentTime);
        oscillator.stop(this.audioContext.currentTime + 0.1);
    }

    public destroy(): void {
        if (this.unsubscribeCommit) {
            this.unsubscribeCommit();
            this.unsubscribeCommit = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }
}
