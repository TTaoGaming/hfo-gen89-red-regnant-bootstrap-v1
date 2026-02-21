// @ts-nocheck
import { Plugin, PluginContext } from './plugin_supervisor';
import { EventBus } from './event_bus';

export class HudPlugin implements Plugin {
    public name = 'HudPlugin';
    public version = '1.0.0';

    private bus: EventBus | null = null;
    private hudFps: HTMLElement | null = null;
    private hudState: HTMLElement | null = null;
    private hudPos: HTMLElement | null = null;

    private frames = 0;
    private lastT = performance.now();

    private onFrameProcessed = this.handleFrameProcessed.bind(this);
    private onStateChange = this.handleStateChange.bind(this);

    public async init(context: PluginContext): Promise<void> {
        this.bus = context.eventBus;

        const getElementById = context.pal.resolve<(id: string) => HTMLElement | null>('GetElementById');
        if (!getElementById) {
            throw new Error('[HudPlugin] GetElementById not registered in PAL');
        }

        this.hudFps = getElementById('hud-fps');
        this.hudState = getElementById('hud-state');
        this.hudPos = getElementById('hud-pos');

        // Fail-closed: If the HUD DOM elements are missing, halt the boot sequence.
        if (!this.hudFps || !this.hudState || !this.hudPos) {
            throw new Error('[HudPlugin] Missing HUD DOM elements. Fail-closed boot.');
        }
    }

    public async start(): Promise<void> {
        if (!this.bus) throw new Error('[HudPlugin] Cannot start without EventBus');

        this.bus.subscribe('FRAME_PROCESSED', this.onFrameProcessed);
        this.bus.subscribe('STATE_CHANGE', this.onStateChange);
    }

    public async stop(): Promise<void> {
        if (!this.bus) return;
        this.bus.unsubscribe('FRAME_PROCESSED', this.onFrameProcessed);
        this.bus.unsubscribe('STATE_CHANGE', this.onStateChange);
    }

    public async destroy(): Promise<void> {
        await this.stop();
        this.bus = null;
        this.hudFps = null;
        this.hudState = null;
        this.hudPos = null;
    }

    private handleFrameProcessed(hands: unknown[]): void {
        this.frames++;
        const now = performance.now();
        if (now - this.lastT > 1000) {
            if (this.hudFps) this.hudFps.textContent = `fps: ${this.frames}`;
            this.frames = 0;
            this.lastT = now;
        }

        if (hands && hands.length > 0 && this.hudPos) {
            const h = hands[0] as { x: number; y: number };
            this.hudPos.textContent = `pos: (${(h.x * 100).toFixed(1)}%, ${(h.y * 100).toFixed(1)}%)`;
        }
    }

    private handleStateChange(payload: unknown): void {
        const p = payload as { currentState: string };
        if (this.hudState && p && p.currentState) {
            this.hudState.textContent = `state: ${p.currentState}`;
        }
    }
}
