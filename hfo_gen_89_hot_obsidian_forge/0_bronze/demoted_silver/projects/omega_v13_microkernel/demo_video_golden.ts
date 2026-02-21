/**
 * @file demo_video_golden.ts
 * @description Omega v13 — Golden Master Integration Test Driver
 *
 * Wires the full pipeline using WIN_20260220_14_09_04_Pro.mp4 as input.
 * Uses VideoClipHarness to feed the file into MediaPipeVisionPlugin,
 * bypassing getUserMedia entirely.
 *
 * PIPELINE:
 *   VideoClipHarness (MP4)
 *     → VideoElement (z=0, mirrored)
 *     → MediaPipeVisionPlugin.startVideoFile()
 *     → FRAME_PROCESSED (RawHandData[])
 *     → GestureFSMPlugin  → STATE_CHANGE
 *     → W3CPointerFabric  → POINTER_UPDATE
 *     → VisualizationPlugin → VIZ layer dots
 *     → BabylonPhysicsPlugin (Havok) → BABYLON_PHYSICS_FRAME
 *     → StillnessMonitorPlugin → STILLNESS_DETECTED
 *     → SymbioteInjectorPlugin → DOM PointerEvent dispatch
 *
 * TELEMETRY (window.__omegaTelemetry):
 *   .frameProcessedCount   — number of FRAME_PROCESSED events received
 *   .stateChanges          — STATE_CHANGE events array
 *   .pointerUpdates        — POINTER_UPDATE events array (first 10)
 *   .babylonFrames         — BABYLON_PHYSICS_FRAME events array (first 10)
 *   .errors                — any caught errors during pipeline execution
 *   .mediaPipeReady        — true once HandLandmarker loads successfully
 *   .videoPlaying          — true once videoElement fires 'playing'
 *
 * 5-check golden master assertions (Playwright reads window.__omegaTelemetry):
 *   CHECK 1  videoPlaying === true          VIDEO feed established
 *   CHECK 2  frameProcessedCount > 0        Landmark tracking firing
 *   CHECK 3  stateChanges.length > 0        FSM transitions happening
 *   CHECK 4  babylonFrames.length > 0       Havok physics frames rendering
 *   CHECK 5  pointerUpdates.length > 0      W3C pointer output flowing
 */

import { PluginSupervisor }         from './plugin_supervisor';
import { GestureFSMPlugin }          from './gesture_fsm_plugin';
import { AudioEnginePlugin }         from './audio_engine_plugin';
import { VisualizationPlugin }       from './visualization_plugin';
import { W3CPointerFabric }          from './w3c_pointer_fabric';
import { MediaPipeVisionPlugin }     from './mediapipe_vision_plugin';
import { StillnessMonitorPlugin }    from './stillness_monitor_plugin';
import { SymbioteInjectorPlugin }    from './symbiote_injector_plugin';
import { BabylonPhysicsPlugin }      from './babylon_physics';
import { LayerManager, LAYER }       from './layer_manager';
import { ConfigManager }             from './config_ui';
import { VideoClipHarness }          from './input_harnesses';

// ── Telemetry accumulator (read by Playwright) ────────────────────────────────

interface GoldenTelemetry {
    videoPlaying:         boolean;
    mediaPipeReady:       boolean;
    havokReady:           boolean;
    frameProcessedCount:  number;
    stateChanges:         Array<{ handId: number; previousState: string; currentState: string }>;
    pointerUpdates:       Array<{ handId: number; x: number; y: number; isPinching: boolean; rawLandmarks?: Array<{ x: number; y: number }> }>;
    babylonFrames:        Array<{ frameIndex: number; handCount: number; sphereCount: number }>;
    stillnessEvents:      Array<{ handId: number }>;
    errors:               string[];
    bootstrapDoneAt:      number | null;
}

const TEL: GoldenTelemetry = {
    videoPlaying:        false,
    mediaPipeReady:      false,
    havokReady:          false,
    frameProcessedCount: 0,
    stateChanges:        [],
    pointerUpdates:      [],
    babylonFrames:       [],
    stillnessEvents:     [],
    errors:              [],
    bootstrapDoneAt:     null,
};
(window as any).__omegaTelemetry = TEL;

// ── Status overlay ────────────────────────────────────────────────────────────

function mkOverlay(): HTMLDivElement {
    const d = document.createElement('div');
    d.id    = 'golden-status';
    Object.assign(d.style, {
        position:   'fixed',
        top:        '8px',
        left:       '8px',
        zIndex:     '9999',
        background: 'rgba(0,0,0,0.75)',
        color:      '#0f0',
        fontFamily: 'monospace',
        fontSize:   '12px',
        padding:    '8px 12px',
        borderRadius: '6px',
        pointerEvents: 'none',
        whiteSpace: 'pre',
    });
    document.body.appendChild(d);
    return d;
}

function refreshOverlay(el: HTMLDivElement): void {
    const chk = (v: boolean, label: string) => `${v ? '✓' : '○'} ${label}`;
    el.textContent = [
        '── OMEGA v13 GOLDEN MASTER ──',
        chk(TEL.videoPlaying,        `CHECK 1  VIDEO playing`),
        chk(TEL.frameProcessedCount > 0, `CHECK 2  FRAME_PROCESSED (${TEL.frameProcessedCount})`),
        chk(TEL.stateChanges.length > 0, `CHECK 3  FSM STATE_CHANGE  (${TEL.stateChanges.length})`),
        chk(TEL.babylonFrames.length > 0,`CHECK 4  BABYLON_PHYSICS_FRAME (${TEL.babylonFrames.length})`),
        chk(TEL.pointerUpdates.length > 0,`CHECK 5  POINTER_UPDATE (${TEL.pointerUpdates.length})`),
        (() => {
            const pu = TEL.pointerUpdates.find(p => p.rawLandmarks && p.rawLandmarks.length === 21);
            if (!pu) return '○ CHECK 6  COORD_INVARIANT (no landmark data yet)';
            const delta = Math.abs(pu.rawLandmarks![8].x - pu.x);
            return chk(delta < 0.05, `CHECK 6  COORD_INVARIANT Δ=${delta.toFixed(4)}`);
        })(),
        TEL.errors.length > 0 ? `ERRORS: ${TEL.errors.slice(-2).join(' | ')}` : '',
    ].filter(Boolean).join('\n');
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

async function bootstrap(): Promise<void> {
    console.log('[GoldenMaster] Bootstrap start');

    const overlay = mkOverlay();
    const tick    = setInterval(() => refreshOverlay(overlay), 400);

    // ── 0. Supervisor ─────────────────────────────────────────────────────────
    const supervisor = new PluginSupervisor();
    const bus        = supervisor.getEventBus();
    const pal        = supervisor.getPal();

    pal.register('ScreenWidth',       window.innerWidth);
    pal.register('ScreenHeight',      window.innerHeight);
    pal.register('OverscanScale',     1.0);
    pal.register('ElementFromPoint',  (x: number, y: number) => document.elementFromPoint(x, y));
    pal.register('AudioContext',      (window.AudioContext ?? (window as any).webkitAudioContext) as typeof AudioContext);

    const configManager = new ConfigManager();
    pal.register('ConfigManager', configManager);

    // ── 1. Layer z-stack ──────────────────────────────────────────────────────

    const layerManager = new LayerManager(bus);

    // VIDEO_BG — z=0:  the VideoClipHarness element will be swapped in here
    const videoEl      = document.createElement('video');
    videoEl.id         = 'omega-video-bg';
    videoEl.autoplay   = false;  // VideoClipHarness calls .play() via start()
    videoEl.playsInline = true;
    videoEl.muted      = true;
    videoEl.loop       = true;
    videoEl.style.transform = 'scaleX(-1)';
    layerManager.registerElement(LAYER.VIDEO_BG, videoEl);

    videoEl.addEventListener('playing', () => {
        TEL.videoPlaying = true;
        console.log('[GoldenMaster] ✓ CHECK 1 — Video playing');
    });

    // BABYLON canvas — z=10
    const babylonCanvas     = document.createElement('canvas');
    babylonCanvas.id        = 'omega-babylon-canvas';
    layerManager.registerElement(LAYER.BABYLON, babylonCanvas);

    // VIZ — z=40
    const vizDiv = document.createElement('div');
    vizDiv.id    = 'omega-viz-layer';
    layerManager.registerElement(LAYER.VIZ, vizDiv);

    // ── 2. Telemetry wire-up (before plugins init) ────────────────────────────

    bus.subscribe('FRAME_PROCESSED', () => {
        TEL.frameProcessedCount++;
        if (TEL.frameProcessedCount === 1) console.log('[GoldenMaster] ✓ CHECK 2 — FRAME_PROCESSED first hit');
    });

    bus.subscribe('STATE_CHANGE', (ev) => {
        TEL.stateChanges.push(ev);
        if (TEL.stateChanges.length === 1) console.log('[GoldenMaster] ✓ CHECK 3 — First FSM STATE_CHANGE:', ev);
    });

    bus.subscribe('POINTER_UPDATE', (ev) => {
        if (TEL.pointerUpdates.length < 20) TEL.pointerUpdates.push(ev);
        if (TEL.pointerUpdates.length === 1) console.log('[GoldenMaster] ✓ CHECK 5 — First POINTER_UPDATE:', ev);
    });

    bus.subscribe('BABYLON_PHYSICS_FRAME', (ev: any) => {
        if (TEL.babylonFrames.length < 20) TEL.babylonFrames.push(ev);
        if (TEL.babylonFrames.length === 1) {
            TEL.havokReady = true;
            console.log('[GoldenMaster] ✓ CHECK 4 — Havok BABYLON_PHYSICS_FRAME:', ev);
        }
    });

    bus.subscribe('STILLNESS_DETECTED', (ev) => {
        TEL.stillnessEvents.push(ev);
    });

    // ── 3. Register plugins ───────────────────────────────────────────────────

    // MediaPipeVisionPlugin receives the shared video element
    const mpPlugin = new MediaPipeVisionPlugin({ videoElement: videoEl });
    supervisor.registerPlugin(mpPlugin);
    supervisor.registerPlugin(new GestureFSMPlugin());
    supervisor.registerPlugin(new AudioEnginePlugin());
    supervisor.registerPlugin(new VisualizationPlugin());
    supervisor.registerPlugin(new W3CPointerFabric({ dispatchToIframes: false, lookaheadSteps: 3 }));
    supervisor.registerPlugin(new StillnessMonitorPlugin());
    supervisor.registerPlugin(new SymbioteInjectorPlugin());
    supervisor.registerPlugin(new BabylonPhysicsPlugin({ canvas: babylonCanvas }));

    // ── 4. Init + start ───────────────────────────────────────────────────────

    await supervisor.initAll();
    await supervisor.startAll();

    TEL.bootstrapDoneAt = performance.now();
    console.log('[GoldenMaster] Supervisor init+start complete');

    // ── 5. VideoClipHarness: replace the video element src with the MP4 ──────
    //
    //  MediaPipeVisionPlugin already holds a reference to videoEl.
    //  We just set videoEl.src directly and call .play() via the harness.
    //  The 'playing' event fires → TEL.videoPlaying = true.
    //  MediaPipeVisionPlugin.startVideoFile() then latches onto the same element.

    const harness = new VideoClipHarness({
        videoUrl:     './WIN_20260220_14_09_04_Pro.mp4',
        loop:         true,
        muted:        true,
        playbackRate: 1.0,
    });

    // We need the harness to drive OUR videoEl (the one registered to LayerManager
    // and already held by MediaPipeVisionPlugin), not create a new one.
    // Override: set src directly on videoEl, then call harness approach.
    videoEl.src = './WIN_20260220_14_09_04_Pro.mp4';
    videoEl.loop = true;

    try {
        await videoEl.play();
        console.log('[GoldenMaster] videoEl.play() resolved');
    } catch (err) {
        // Some browsers require user gesture for play() — log but continue
        // (MediaPipe will still get data once it's loaded)
        console.warn('[GoldenMaster] videoEl.play() rejected (expected in headless):', err);
        TEL.errors.push(`play(): ${String(err)}`);
    }

    // ── 6. Start MediaPipe against the video file ─────────────────────────────

    try {
        console.log('[GoldenMaster] Starting MediaPipe via startVideoFile()…');
        await mpPlugin.startVideoFile();
        TEL.mediaPipeReady = true;
        console.log('[GoldenMaster] MediaPipe video file mode active ✓');
    } catch (err) {
        const msg = `MediaPipe startVideoFile: ${String(err)}`;
        TEL.errors.push(msg);
        console.error('[GoldenMaster]', msg);
    }

    // ── 7. Expose for Playwright + console harness ────────────────────────────

    (window as any).__omegaExports = {
        bus,
        supervisor,
        mpPlugin,
        layerManager,
        telemetry: TEL,
    };

    (window as any).omegaInjectFrame = (json: string | any[]) => {
        const hands = typeof json === 'string' ? JSON.parse(json) : json;
        bus.publish('FRAME_PROCESSED', hands);
    };

    console.log('[GoldenMaster] Bootstrap complete. window.__omegaTelemetry available.');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
} else {
    bootstrap();
}
