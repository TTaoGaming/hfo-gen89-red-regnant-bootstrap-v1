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
    supervisor.getPal().register('ScreenWidth',      () => window.innerWidth);
    supervisor.getPal().register('ScreenHeight',     () => window.innerHeight);
    supervisor.getPal().register('ElementFromPoint', (x: number, y: number) => document.elementFromPoint(x, y));
    supervisor.getPal().register('OverscanScale',    () => (window as any).omegaOverscanScale ?? 1.0);

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
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
} else {
    bootstrap();
}
