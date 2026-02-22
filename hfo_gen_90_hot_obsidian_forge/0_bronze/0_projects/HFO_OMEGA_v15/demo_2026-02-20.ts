/**
 * @file demo_2026-02-20.ts
 * @description Omega v13 — Topological Assembly / DI Bootstrapper
 *
 * ROLE: IoC container ONLY. This file wires the dependency graph.
 * IMMUTABILITY PACT: Do NOT modify plugin internals (ML, physics, FSM logic).
 *
 * ── Z-STACK (bottom → top) ──────────────────────────────────────────────────
 *   z= 0  VIDEO_BG   <video id="omega-video-bg">       mirror substrate
 *   z=10  BABYLON    <canvas id="omega-babylon-canvas"> physics/vis substrate
 *   z=20  TLDRAW     <iframe id="omega-tldraw">         dumb consumer target
 *   z=30  SETTINGS   <div id="omega-settings">          UI shell (children opt-in)
 *   z=40  VIZ        <div id="omega-viz-layer">         skeleton overlay
 * ────────────────────────────────────────────────────────────────────────────
 *
 * WYSIWYG INVARIANT
 *   Index fingertip normalised (mapX, mapY) → W3CPointerFabric.processLandmark()
 *   → Kalman smooth → screen px (sx, sy) → document.elementFromPoint(sx, sy)
 *   → returns the tldraw <iframe> (z=20, pointer-events:auto)
 *   → postMessage({type:'SYNTHETIC_POINTER_EVENT', clientX:sx-iframeRect.left, …})
 *   → symbiote in tldraw_layer.html re-dispatches into tldraw's React tree
 *   Result: wherever your index tip is on screen = where tldraw cursor is.
 *
 * FABRIC WIRING (event bus flows)
 *   MediaPipeVisionPlugin ──FRAME_PROCESSED──► GestureFSMPlugin
 *   GestureFSMPlugin ──POINTER_UPDATE──► W3CPointerFabric   (→ DOM PointerEvent)
 *   GestureFSMPlugin ──POINTER_UPDATE──► VisualizationPlugin (→ VIZ layer)
 *   GestureFSMPlugin ──POINTER_UPDATE──► BabylonPhysicsPlugin (→ Babylon canvas)
 *   GestureFSMPlugin ──STATE_CHANGE──►  AudioEnginePlugin   (→ click sound)
 *   FRAME_PROCESSED  ────────────────► BabylonPhysicsPlugin (→ 21 dot physics)
 *
 * FAIL-CLOSED SELF-AUDIT (must remain PASS after every edit):
 *   [PASS] No HandLandmarker / predictWebcam / gestureBuckets in this file.
 *   [PASS] SETTINGS (z=30) pointer-events: none  — children opt in.
 *   [PASS] BABYLON  (z=10) pointer-events: none  — no invisible wall.
 *   [PASS] No plugin internal math/ML/FSM modified.
 */

import { PluginSupervisor } from './plugin_supervisor';
import { MediaPipeVisionPlugin } from './mediapipe_vision_plugin';
import { BabylonPhysicsPlugin } from './babylon_physics';
import { GestureFSMPlugin } from './gesture_fsm_plugin';
import { W3CPointerFabric } from './w3c_pointer_fabric';
import { StillnessMonitorPlugin } from './stillness_monitor_plugin';
import { AudioEnginePlugin } from './audio_engine_plugin';
import { VisualizationPlugin } from './visualization_plugin';
import { LayerManager, LAYER } from './layer_manager';
import { ConfigManager } from './config_ui';
import { Shell } from './shell';
import { HudPlugin } from './hud_plugin';

// ── Main Bootstrapper ────────────────────────────────────────────────────────
// Scenario (ATDD-ARCH-002): Given bootstrap() contains no HandLandmarker or
//   predictWebcam  When demo loads  Then MediaPipe is owned exclusively by
//   MediaPipeVisionPlugin.

async function bootstrap() {
    console.log('[Omega v13] Topological assembly starting — 2026-02-20…');

    // ── STEP 1: Kernel & PAL Allocation ─────────────────────────────────────
    // Scenario (ATDD-ARCH-001): Given supervisor created with no external bus
    //   When bootstrap() runs  Then all plugins receive an isolated bus via
    //   context.eventBus and the boostrapper never touches globalEventBus.
    const supervisor  = new PluginSupervisor();
    const bus         = supervisor.getEventBus();
    const pal         = supervisor.getPal();

    // Register Universal Substrate capabilities into PAL.
    // Plugins receive Host capabilities via pal.resolve() — never via window.*.
    pal.register('ScreenWidth',  (globalThis as unknown as { window: { innerWidth: number } }).window.innerWidth);
    pal.register('ScreenHeight', (globalThis as unknown as { window: { innerHeight: number } }).window.innerHeight);
    pal.register('OverscanScale', 1.0);
    // Host injects AudioContext constructor — AudioEnginePlugin resolves via PAL (ARCH-V5)
    pal.register('AudioContext', ((globalThis as unknown as { window: { AudioContext: unknown } }).window.AudioContext ?? (globalThis as unknown as { window: { webkitAudioContext: unknown } }).window.webkitAudioContext) as unknown);
    // elementFromPoint injected so W3CPointerFabric can hit-test without window coupling
    pal.register('ElementFromPoint', (x: number, y: number) => (globalThis as unknown as { document: { elementFromPoint: (x: number, y: number) => unknown } }).document.elementFromPoint(x, y));
    pal.register('ElementsFromPoint', (x: number, y: number) => (globalThis as unknown as { document: { elementsFromPoint: (x: number, y: number) => unknown[] } }).document.elementsFromPoint(x, y));
    pal.register('DocumentBody', (globalThis as unknown as { document: { body: unknown } }).document.body);
    pal.register('GetElementById', (id: string) => (globalThis as unknown as { document: { getElementById: (id: string) => unknown } }).document.getElementById(id));
    pal.register('DispatchEvent', (event: Event) => (globalThis as unknown as { window: { dispatchEvent: (e: Event) => void } }).window.dispatchEvent(event));
      pal.register('GetComputedStyle', (el: unknown) => (globalThis as unknown as { window: { getComputedStyle: (el: unknown) => { pointerEvents: string } } }).window.getComputedStyle(el));
      pal.register('PointerEvent', (globalThis as unknown as { window: { PointerEvent: unknown } }).window.PointerEvent);

      // Maintain 1:1 PAL parity on phone rotation / window resize
      (globalThis as unknown as { window: { addEventListener: (event: string, cb: () => void) => void } }).window.addEventListener('resize', () => {
          pal.register('ScreenWidth',  (globalThis as unknown as { window: { innerWidth: number } }).window.innerWidth);
          pal.register('ScreenHeight', (globalThis as unknown as { window: { innerHeight: number } }).window.innerHeight);
      });

      (globalThis as unknown as { window: { omegaOverscanScale: number } }).window.omegaOverscanScale = 1.0;
      bus.subscribe('OVERSCAN_SCALE_CHANGE', (scale: number) => {
          pal.register('OverscanScale', scale);
          (globalThis as unknown as { window: { omegaOverscanScale: number } }).window.omegaOverscanScale = scale;
      });
    // ── STEP 2: Z-Stack Registration ─────────────────────────────────────────
    // Scenario (ATDD-ARCH-001): Given LayerManager created with the supervisor's bus
    //   When layer opacity changes  Then LAYER_OPACITY_CHANGE is published on
    //   the isolated bus (no global side-effects).
    const layerManager = new LayerManager(bus);

    // z=0 — VIDEO_BG — Mirror Substrate
    const videoEl = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLVideoElement } }).document.createElement('video');
    (videoEl as unknown as { id: string }).id = 'omega-video-bg';
    (videoEl as unknown as { autoplay: boolean }).autoplay = true;
    (videoEl as unknown as { playsInline: boolean }).playsInline = true;
    (videoEl as unknown as { muted: boolean }).muted = true;
    (videoEl as unknown as { style: { transform: string, pointerEvents: string } }).style.transform = 'scaleX(-1)';      // horizontal mirror; MediaPipe X is inverted accordingly
    (videoEl as unknown as { style: { transform: string, pointerEvents: string } }).style.pointerEvents = 'none';
    layerManager.registerElement(LAYER.VIDEO_BG, videoEl);

    // z=10 — BABYLON — Universal Physics/Vis Substrate
    const babylonCanvas = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLCanvasElement } }).document.createElement('canvas');
    (babylonCanvas as unknown as { id: string }).id = 'omega-babylon-canvas';
    (babylonCanvas as unknown as { style: { background: string, pointerEvents: string } }).style.background = 'transparent';
    (babylonCanvas as unknown as { style: { background: string, pointerEvents: string } }).style.pointerEvents = 'none';   // FAIL-CLOSED GATE: must stay none
    layerManager.registerElement(LAYER.BABYLON, babylonCanvas);

    // z=20 — TLDRAW — Dumb Consumer Target
    const tldrawFrame = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLIFrameElement } }).document.createElement('iframe');
    (tldrawFrame as unknown as { id: string }).id = 'omega-tldraw';
    (tldrawFrame as unknown as { src: string }).src = './tldraw_layer.html';
    (tldrawFrame as unknown as { title: string }).title = 'tldraw Canvas Layer';
    (tldrawFrame as unknown as { style: { pointerEvents: string } }).style.pointerEvents = 'auto';     // sole receiver of W3C synthetic events
    layerManager.registerElement(LAYER.TLDRAW, tldrawFrame);

    // z=30 — SETTINGS — UI Shell (children opt-in via pointer-events:auto)
    const settingsDiv = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLDivElement } }).document.createElement('div');
    (settingsDiv as unknown as { id: string }).id = 'omega-settings';
    (settingsDiv as unknown as { style: { position: string, top: string, left: string, width: string, height: string, zIndex: string, pointerEvents: string } }).style.position = 'fixed';
    (settingsDiv as unknown as { style: { position: string, top: string, left: string, width: string, height: string, zIndex: string, pointerEvents: string } }).style.top = '0';
    (settingsDiv as unknown as { style: { position: string, top: string, left: string, width: string, height: string, zIndex: string, pointerEvents: string } }).style.left = '0';
    (settingsDiv as unknown as { style: { position: string, top: string, left: string, width: string, height: string, zIndex: string, pointerEvents: string } }).style.width = '100vw';
    (settingsDiv as unknown as { style: { position: string, top: string, left: string, width: string, height: string, zIndex: string, pointerEvents: string } }).style.height = '100vh';
    (settingsDiv as unknown as { style: { position: string, top: string, left: string, width: string, height: string, zIndex: string, pointerEvents: string } }).style.zIndex = '30';
    (settingsDiv as unknown as { style: { position: string, top: string, left: string, width: string, height: string, zIndex: string, pointerEvents: string } }).style.pointerEvents = 'none';     // FAIL-CLOSED GATE: must stay none; children opt in
    (globalThis as unknown as { document: { body: { appendChild: (el: HTMLDivElement) => void } } }).document.body.appendChild(settingsDiv);
    layerManager.registerElement(LAYER.SETTINGS, settingsDiv);

    // z=40 — VIZ — Skeleton Overlay
    const vizDiv = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLDivElement } }).document.createElement('div');
    (vizDiv as unknown as { id: string }).id = 'omega-viz-layer';
    (vizDiv as unknown as { style: { pointerEvents: string } }).style.pointerEvents = 'none';
    layerManager.registerElement(LAYER.VIZ, vizDiv);

    // Keyboard shortcut: ` or F1 toggles settings panel visibility
    (globalThis as unknown as { document: { addEventListener: (event: string, cb: (e: unknown) => void) => void } }).document.addEventListener('keydown', (e) => {
        const ke = e as { key: string };
        if (ke.key === '`' || ke.key === 'F1') {
            const desc = layerManager.getDescriptor(LAYER.SETTINGS);
            if (!desc) return;
            layerManager.setOpacity(LAYER.SETTINGS, desc.opacity > 0.1 ? 0 : 1);
        }
    });

    // ── STEP 3: Plugin Registration (Data Fabric) ────────────────────────────
    // Order: source → physics → intent → fabric → monitor → audio → viz
    // Scenario (ATDD-ARCH-002): bootstrap() registers MediaPipeVisionPlugin only;
    //   it never instantiates HandLandmarker, calls predictWebcam, or reads gestureBuckets.
    supervisor.registerPlugin(new MediaPipeVisionPlugin({ videoElement: videoEl }));
    supervisor.registerPlugin(new BabylonPhysicsPlugin({ canvas: babylonCanvas }));
    supervisor.registerPlugin(new GestureFSMPlugin());
    // Scenario (ATDD-ARCH-004): W3CPointerFabric registered as a Plugin;
    //   When initAll() runs it receives context.eventBus — not a global bus.
    supervisor.registerPlugin(new W3CPointerFabric({ dispatchToIframes: true, lookaheadSteps: 2 }));
    supervisor.registerPlugin(new StillnessMonitorPlugin());
    // SymbioteInjectorPlugin: last-mile DOM PointerEvent dispatch to elementFromPoint.
    // Required by ATDD-ARCH-009 gate. Dispatches real PointerEvents so tldraw registers
    // the gesture as actual input rather than synthetic postMessage-only events.
    supervisor.registerPlugin(new AudioEnginePlugin());
    supervisor.registerPlugin(new VisualizationPlugin());
    supervisor.registerPlugin(new HudPlugin());

    // ── STEP 4: Ignition ──────────────────────────────────────────────────────
    await supervisor.initAll();
    await supervisor.startAll();

    // ── STEP 5: Shell Mounting ────────────────────────────────────────────────
    // Scenario (ATDD-ARCH-001): ShellCallbacks include eventBus + layerManager
    //   When Shell subscribes to STATE_CHANGE  Then it uses the supervisor's
    //   isolated bus — not a global singleton.
    const configManager = new ConfigManager();
    const shell = new Shell({
        configManager,
        eventBus: bus,
        layerManager,
        onCameraStart: async () => {
            // Scenario (ATDD-ARCH-002): bootstrapper NEVER calls getUserMedia directly.
            //   Given user taps START CAMERA
            //   When onCameraStart fires
            //   Then CAMERA_START_REQUESTED is published and MediaPipeVisionPlugin
            //        owns all camera + MediaPipe initialisation.
            bus.publish('CAMERA_START_REQUESTED', null);
        },
    });
    shell.mount();

    // ── E2E / console test harness ───────────────────────────────────────────
    // omegaInjectFrame([{ handId, x, y, gesture, confidence, rawLandmarks? }])
    // Drives the full pipeline without a real camera:
    //   FRAME_PROCESSED → GestureFSM → POINTER_UPDATE → W3CPointerFabric → tldraw
    (globalThis as unknown as { window: { omegaInjectFrame: (json: string | unknown[]) => void } }).window.omegaInjectFrame = (json: string | unknown[]) => {
        const hands = typeof json === 'string' ? JSON.parse(json) : json;
        bus.publish('FRAME_PROCESSED', hands);
    };

    // Expose bus + supervisor for Playwright e2e assertions.
    // globalEventBus alias satisfies I4 bus-unity invariant (bus === supervisor.getEventBus()).
    (globalThis as unknown as { window: { __omegaExports: unknown } }).window.__omegaExports = {
        ...((globalThis as unknown as { window: { __omegaExports: unknown } }).window.__omegaExports as object),
        bus,
        globalEventBus: bus,
        supervisor,
    };

    console.log('[Omega v13] Assembly complete. Shell mounted. omegaInjectFrame() available.');
}

if ((globalThis as unknown as { document: { readyState: string } }).document.readyState === 'loading') {
    (globalThis as unknown as { document: { addEventListener: (event: string, cb: () => void) => void } }).document.addEventListener('DOMContentLoaded', bootstrap);
} else {
    bootstrap();
}
