import { PluginSupervisor } from './plugin_supervisor';
import { GestureFSMPlugin } from './gesture_fsm_plugin';
import { AudioEnginePlugin } from './audio_engine_plugin';
import { VisualizationPlugin } from './visualization_plugin';
import { SymbioteInjectorPlugin } from './symbiote_injector_plugin';
import { MediaPipeVisionPlugin } from './mediapipe_vision_plugin';

async function bootstrap() {
    console.log('Bootstrapping Omega v13 Demo...');

    const supervisor = new PluginSupervisor();

    // Register PAL capabilities  only bootstrap knows the host environment
    supervisor.getPal().register('ScreenWidth',      () => (globalThis as unknown as { window: { innerWidth: number } }).window.innerWidth);
    supervisor.getPal().register('ScreenHeight',     () => (globalThis as unknown as { window: { innerHeight: number } }).window.innerHeight);
    supervisor.getPal().register('ElementFromPoint', (x: number, y: number) => (globalThis as unknown as { document: { elementFromPoint: (x: number, y: number) => unknown } }).document.elementFromPoint(x, y));
    supervisor.getPal().register('OverscanScale',    () => (globalThis as unknown as { window: { omegaOverscanScale?: number } }).window.omegaOverscanScale ?? 1.0);

    // Register plugins  assembler only, no business logic here
    supervisor.registerPlugin(new MediaPipeVisionPlugin());
    supervisor.registerPlugin(new GestureFSMPlugin());
    supervisor.registerPlugin(new AudioEnginePlugin());
    supervisor.registerPlugin(new VisualizationPlugin());
    supervisor.registerPlugin(new SymbioteInjectorPlugin());

    await supervisor.initAll();
    await supervisor.startAll();

    console.log('Omega v13 Demo Running.');
}

// Run bootstrap when DOM is ready
if ((globalThis as unknown as { document: { readyState: string } }).document.readyState === 'loading') {
    (globalThis as unknown as { document: { addEventListener: (event: string, cb: () => void) => void } }).document.addEventListener('DOMContentLoaded', bootstrap);
} else {
    bootstrap();
}
