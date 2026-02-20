/**
 * @file demo_2026-02-20.ts
 * @description Omega v13 — Layered Compositor Demo (timestamped 2026-02-20)
 *
 * LAYER Z-STACK (bottom → top)
 * ─────────────────────────────────────────────────────────────
 *   z=0   VIDEO_BG   <video>     live camera, mirrored, full-viewport
 *   z=10  BABYLON    <canvas>    Babylon.js physics dots + state halos
 *   z=20  TLDRAW     <iframe>    tldraw whiteboard at 80% opacity
 *   z=30  SETTINGS   <div>       Config Mosaic panel, always on top
 *   z=40  VIZ        <div>       Hand skeleton / dot-ring — pointer-events:none
 * ─────────────────────────────────────────────────────────────
 *
 * WYSIWYG INVARIANT
 *   Index fingertip normalized (mapX, mapY) → W3CPointerFabric.processLandmark()
 *   → Kalman smooth → screen px (sx, sy) → document.elementFromPoint(sx, sy)
 *   → returns the tldraw <iframe> (z=20, pointer-events:auto)
 *   → postMessage({type:'SYNTHETIC_POINTER_EVENT', clientX:sx-iframeRect.left, …})
 *   → symbiote in tldraw_layer.html re-dispatches into tldraw's React tree
 *   Result: wherever your index tip is on screen = where tldraw cursor is.
 *
 * FABRIC WIRING (event bus)
 *   MediaPipe      ──FRAME_PROCESSED──►  GestureFSMPlugin
 *   GestureFSMPlugin──POINTER_UPDATE──►  W3CPointerFabric  (→ DOM PointerEvent)
 *   GestureFSMPlugin──POINTER_UPDATE──►  VisualizationPlugin (→ VIZ layer)
 *   GestureFSMPlugin──POINTER_UPDATE──►  BabylonAdapter     (→ Babylon canvas)
 *   GestureFSMPlugin──STATE_CHANGE───►  AudioEnginePlugin  (→ click sound)
 *   FRAME_PROCESSED──────────────────►  BabylonAdapter     (→ 21 dot physics)
 */

import { PluginSupervisor } from './plugin_supervisor';
import { GestureFSMPlugin } from './gesture_fsm_plugin';
import { AudioEnginePlugin } from './audio_engine_plugin';
import { VisualizationPlugin } from './visualization_plugin';
import { W3CPointerFabric } from './w3c_pointer_fabric';
import { MediaPipeVisionPlugin } from './mediapipe_vision_plugin';
import { LayerManager, LAYER } from './layer_manager';
import { EventBus } from './event_bus';
import { ConfigManager, DebugUI } from './config_ui';
import { Shell } from './shell';

// ── Optional: Babylon.  Import lazily so the demo still boots without it. ──
let babylonStarted = false;

// Scenario (ATDD-ARCH-002): Given bootstrap() contains no HandLandmarker or predictWebcam
//                            When demo loads
//                            Then MediaPipe is owned exclusively by MediaPipeVisionPlugin
async function startBabylon(canvas: HTMLCanvasElement, bus: EventBus) {
    try {
        // Lazy-import so esbuild can tree-shake if babylon isn't installed
        const { BabylonPhysicsPlugin } = await import('./babylon_physics') as any;
        // Havok is loaded via CDN in index_demo2.html
        const HavokPhysics = (window as any).HavokPhysics;
        if (!HavokPhysics) {
            console.warn('[Babylon] HavokPhysics not available on window — skipping physics');
            return null;
        }
        const havok = await HavokPhysics();
        const plugin = new BabylonPhysicsPlugin({ canvas, havokInstance: havok });

        // Bridge FRAME_PROCESSED → Babylon (injected bus — ATDD-ARCH-001)
        bus.subscribe('FRAME_PROCESSED', (hands: any[]) => {
            if (!hands || hands.length === 0) return;
            const payload = {
                hands: hands
                    .filter(h => h.rawLandmarks && h.rawLandmarks.length === 21)
                    .map(h => ({
                        id: h.handId,
                        pointerX: h.x,
                        pointerY: h.y,
                        isPinching: false,
                        rawLandmarks: h.rawLandmarks,
                    }))
            };
            if (payload.hands.length > 0) {
                plugin.consumeGesturePayload(payload);
            }
        });

        babylonStarted = true;
        console.log('[Babylon] Physics engine running');
        return plugin;
    } catch (err) {
        console.warn('[Babylon] Could not start:', err);
        return null;
    }
}

// ── Layer Settings Panel (extends DebugUI with opacity sliders) ─────────────

// Scenario (ATDD-ARCH-001): Given no globalLayerManager import
//                            When buildLayerControls is called
//                            Then it uses the LayerManager injected by the bootstrapper
function buildLayerControls(panel: HTMLElement, layerManager: LayerManager) {
    const section = document.createElement('div');
    section.style.borderTop = '1px solid #00ff00';
    section.style.marginTop = '10px';
    section.style.paddingTop = '8px';

    const title = document.createElement('div');
    title.textContent = '── Layer Opacity ──';
    title.style.color = '#00ff00';
    title.style.fontSize = '11px';
    title.style.marginBottom = '6px';
    section.appendChild(title);

    for (const layer of layerManager.allLayers()) {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.alignItems = 'center';
        row.style.gap = '8px';
        row.style.marginBottom = '4px';

        const label = document.createElement('label');
        label.textContent = layer.label;
        label.style.width = '120px';
        label.style.fontSize = '11px';
        label.style.color = '#ccc';

        const slider = document.createElement('input');
        slider.type = 'range';
        slider.min = '0';
        slider.max = '1';
        slider.step = '0.05';
        slider.value = String(layer.opacity);
        slider.style.flex = '1';

        const val = document.createElement('span');
        val.textContent = String(layer.opacity.toFixed(2));
        val.style.width = '34px';
        val.style.fontSize = '11px';
        val.style.color = '#aaa';

        slider.addEventListener('input', () => {
            const op = parseFloat(slider.value);
            layerManager.setOpacity(layer.id, op);
            val.textContent = op.toFixed(2);
        });

        row.appendChild(label);
        row.appendChild(slider);
        row.appendChild(val);
        section.appendChild(row);
    }

    panel.appendChild(section);
}

// ── Main Bootstrap ───────────────────────────────────────────────────────────

async function bootstrap() {
    console.log('[Omega v13] Bootstrapping layered compositor demo 2026-02-20…');

    // ── 0. Supervisor — owns EventBus (ATDD-ARCH-001) ─────────────────────
    // Scenario: Given supervisor is created with no globalEventBus argument
    //           When bootstrap() runs
    //           Then all plugins receive an isolated bus via context.eventBus
    const supervisor = new PluginSupervisor();
    const bus = supervisor.getEventBus();
    const pal = supervisor.getPal();
    pal.register('ScreenWidth',  window.screen.width);
    pal.register('ScreenHeight', window.screen.height);
    pal.register('OverscanScale', 1.0);
    pal.register('ElementFromPoint', (x: number, y: number) => document.elementFromPoint(x, y));

    // ConfigManager registered in PAL so plugins can resolve it without tight coupling
    const configManager = new ConfigManager();
    pal.register('ConfigManager', configManager);

    // Overscan: keep window-global for Playwright console harness + backwards compat
    (window as any).omegaOverscanScale = 1.0;
    bus.subscribe('OVERSCAN_SCALE_CHANGE', (scale: number) => {
        pal.register('OverscanScale', scale);
        (window as any).omegaOverscanScale = scale;
    });

    // ── 1. Build the layer z-stack ─────────────────────────────────────────
    // Scenario: Given LayerManager is created with the supervisor's EventBus
    //           When layer opacity changes
    //           Then LAYER_OPACITY_CHANGE is published on the isolated bus
    const layerManager = new LayerManager(bus);

    // VIDEO_BG — z=0
    const videoEl = document.createElement('video');
    videoEl.id = 'omega-video-bg';
    videoEl.autoplay = true;
    videoEl.playsInline = true;
    videoEl.muted = true;
    // Mirror horizontally so the user sees themselves like a mirror (not a camera).
    // All MediaPipe X coordinates must be inverted to match (see WYSIWYG mapping below).
    videoEl.style.transform = 'scaleX(-1)';
    layerManager.registerElement(LAYER.VIDEO_BG, videoEl);

    // BABYLON — z=10 (transparent canvas; Babylon clears it each frame)
    const babylonCanvas = document.createElement('canvas');
    babylonCanvas.id = 'omega-babylon-canvas';
    layerManager.registerElement(LAYER.BABYLON, babylonCanvas);

    // TLDRAW — z=20, 80% opacity, pointer-events:auto (receives W3C events via postMessage)
    const tldrawFrame = document.createElement('iframe');
    tldrawFrame.id = 'omega-tldraw';
    tldrawFrame.src = './tldraw_layer.html?v=3';  // v=2: react@19 fix
    tldrawFrame.title = 'tldraw Canvas Layer';
    layerManager.registerElement(LAYER.TLDRAW, tldrawFrame);

    // SETTINGS — z=30, auto pointer-events (human-operated panel)
    const settingsDiv = document.createElement('div');
    settingsDiv.id = 'omega-settings';
    settingsDiv.style.position = 'fixed';
    settingsDiv.style.top = '0';
    settingsDiv.style.left = '0';
    settingsDiv.style.width = '100vw';
    settingsDiv.style.height = '100vh';
    settingsDiv.style.zIndex = '30';
    settingsDiv.style.pointerEvents = 'none'; // children opt in
    document.body.appendChild(settingsDiv);
    layerManager.registerElement(LAYER.SETTINGS, settingsDiv);

    // VIZ — z=40, pointer-events:none (VisualizationPlugin appends inside)
    const vizDiv = document.createElement('div');
    vizDiv.id = 'omega-viz-layer';
    layerManager.registerElement(LAYER.VIZ, vizDiv);

    // ── 2. Keyboard shortcut: toggle settings panel visibility ────────────
    document.addEventListener('keydown', (e) => {
        if (e.key === '`' || e.key === 'F1') {
            const desc = layerManager.getDescriptor(LAYER.SETTINGS);
            if (!desc) return;
            const newOp = desc.opacity > 0.1 ? 0 : 1;
            layerManager.setOpacity(LAYER.SETTINGS, newOp);
        }
    });

    // ── 3. Register plugins (ATDD-ARCH-002: no MediaPipe in bootstrapper) ─
    // Scenario: Given bootstrap() registers MediaPipeVisionPlugin
    //           When supervisor.initAll() runs
    //           Then the Vision plugin subscribes to CAMERA_START_REQUESTED
    //                and the bootstrapper contains zero HandLandmarker code
    supervisor.registerPlugin(new MediaPipeVisionPlugin({ videoElement: videoEl }));
    supervisor.registerPlugin(new GestureFSMPlugin());
    supervisor.registerPlugin(new AudioEnginePlugin());
    supervisor.registerPlugin(new VisualizationPlugin());
    // Scenario (ATDD-ARCH-004): W3CPointerFabric registered as a Plugin
    //                           When initAll() runs it receives context.eventBus
    supervisor.registerPlugin(new W3CPointerFabric({ dispatchToIframes: true, lookaheadSteps: 3 }));
    await supervisor.initAll();
    await supervisor.startAll();

    // Start Babylon (non-blocking) — receives isolated bus
    startBabylon(babylonCanvas, bus);

    // Override viz plugin's container z-index to match our layer stack
    const vizContainer = document.getElementById('omega-visualization-container');
    if (vizContainer) {
        vizContainer.style.zIndex = '40';
    }

    // ── 4. Config Mosaic + Shell UI ─────────────────────────────────────
    // Scenario (ATDD-ARCH-001): Given ShellCallbacks includes eventBus + layerManager
    //                           When Shell subscribes to STATE_CHANGE
    //                           Then it uses the supervisor's isolated bus
    const shell = new Shell({
        configManager,
        eventBus: bus,
        layerManager,
        onCameraStart: async () => {
            // Scenario (ATDD-ARCH-002): bootstrapper never calls camera API directly
            //   Given user taps START CAMERA
            //   When onCameraStart fires
            //   Then CAMERA_START_REQUESTED is published on the bus
            //        and MediaPipeVisionPlugin owns all camera + MediaPipe setup
            bus.publish('CAMERA_START_REQUESTED', null);
        },
    });
    shell.mount();

    // ── JSON test harness — call from console or Playwright ─────────────────
    // omegaInjectFrame([{handId, x, y, gesture, confidence, rawLandmarks?}])
    // Drives the full pipeline: FRAME_PROCESSED → FSM → POINTER_UPDATE → W3C → tldraw
    // Scenario (ATDD-ARCH-002): Given bootstrapper uses bus not globalEventBus
    //                           When Playwright calls omegaInjectFrame
    //                           Then FRAME_PROCESSED flows through the isolated bus
    (window as any).omegaInjectFrame = (json: string | any[]) => {
        const hands = typeof json === 'string' ? JSON.parse(json) : json;
        bus.publish('FRAME_PROCESSED', hands);
    };

    // Expose bus + supervisor for e2e assertions
    // globalEventBus alias satisfies Playwright bootstrap + I4 bus-unity invariant
    (window as any).__omegaExports = {
        ...(window as any).__omegaExports,
        bus,
        globalEventBus: bus,   // alias: bus === supervisor.getEventBus()
        supervisor,
    };

    console.log('[Omega v13] Layered demo ready. Shell mounted. omegaInjectFrame() available.');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
} else {
    bootstrap();
}
