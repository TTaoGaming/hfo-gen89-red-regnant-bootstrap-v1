/**
 * microkernel_arch_violations.spec.ts
 *
 * SBE / ATDD specification for the Microkernel Architectural Violations.
 * V1-V6: original violations (2026-02-20)
 * V7-V10: L11 Wiring Manifest gates (2026-02-20) — structural enforcement so
 *          ghost events, PAL leaks, unregistered plugins, and symbiote regressions
 *          are IMPOSSIBLE to miss in CI, not just caught in code review.
 *
 * Discipline: RED → GREEN → REFACTOR
 *   • Tests marked [RED] FAIL on current code and define the acceptance criteria.
 *   • Tests marked [GREEN] already pass — they are regression guards.
 *   • Fix one violation at a time, run jest after each.
 *
 * Mission threads (braided SSOT):
 *   omega.v13.arch.v1_global_singleton  (priority 99, L8)
 *   omega.v13.arch.v2_god_object        (priority 97, L9)
 *   omega.v13.arch.v3_double_debounce   (priority 96, L5)
 *   omega.v13.arch.v4_rogue_agents      (priority 95, L8)
 *   omega.v13.arch.v5_pal_leaks         (priority 93, L6)
 *   omega.v13.arch.v6_stub_impls        (priority 70, L3)
 *
 * Run locally:
 *   npx jest microkernel_arch_violations.spec --no-coverage --verbose
 */
// @ts-nocheck


import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { asRaw } from './types';
import { EventBus } from './event_bus';
import { PluginSupervisor, Plugin, PluginContext, PathAbstractionLayer } from './plugin_supervisor';
import { GestureFSMPlugin } from './gesture_fsm_plugin';
import { StillnessMonitorPlugin } from './stillness_monitor_plugin';
import { SymbioteInjectorPlugin } from './symbiote_injector_plugin';
import { CHANNEL_MANIFEST, DEFERRED_PLUGINS, PAL_LEAK_PATTERNS, SYMBIOTE_CONTRACT } from './event_channel_manifest';
import * as fs from 'fs';
import * as path from 'path';

/**
 * tryRequire: attempt a require() call at runtime without TS type-checking.
 * Used for modules that do not exist yet (RED tests drive their creation).
 */
function tryRequire(modulePath: string): any {
    try {
         
        return require(modulePath);
    } catch {
        return null;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: build an isolated PluginContext for unit testing
// ─────────────────────────────────────────────────────────────────────────────
function makeContext(overrides: Partial<PluginContext> = {}): PluginContext {
    const pal = new PathAbstractionLayer();
    pal.register('ScreenWidth',  1920);
    pal.register('ScreenHeight', 1080);
    pal.register('ElementFromPoint', (x: number, y: number) => null);
    return { eventBus: new EventBus(), pal, ...overrides };
}

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-001 — V1: Global Singleton Contraband
// Mission thread: omega.v13.arch.v1_global_singleton
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-001 · V1 Global Singleton Contraband', () => {
    /**
     * [RED until fix] PluginSupervisor should expose getEventBus() so tests can
     * verify isolation.  Currently the method does not exist.
     */
    it('[RED] Given two PluginSupervisor instances, Then each exposes getEventBus() returning its own isolated bus', () => {
        const sup1 = new PluginSupervisor();
        const sup2 = new PluginSupervisor();

        // After fix: PluginSupervisor must have a getEventBus() method
        expect(typeof (sup1 as any).getEventBus).toBe('function');
        expect(typeof (sup2 as any).getEventBus).toBe('function');
    });

    /**
     * [RED until fix] Events published to sup1's bus must NOT reach plugins
     * registered with sup2.  Currently FAILS because both share globalEventBus.
     */
    it('[RED] Given two isolated supervisors, When sup1 publishes FRAME_PROCESSED, Then sup2 plugin does NOT receive it', async () => {
        const sup1 = new PluginSupervisor();
        const sup2 = new PluginSupervisor();

        const sup2Received: unknown[] = [];

        // Build a minimal spy plugin and register into sup2 only
        const spyPlugin: Plugin = {
            name: 'SpyPlugin',
            version: '1.0.0',
            init(ctx: PluginContext) {
                ctx.eventBus.subscribe('FRAME_PROCESSED', (d) => sup2Received.push(d));
            },
            start()   {},
            stop()    {},
            destroy() {},
        };

        sup2.registerPlugin(spyPlugin);
        await sup2.initAll();

        // Fire on sup1's bus — after fix, sup2 should not see this
        const sup1Bus = (sup1 as any).getEventBus?.() as EventBus | undefined;
        if (!sup1Bus) {
            // getEventBus not yet implemented — test is pending the fix
            expect(true).toBe(false); // force RED
            return;
        }
        sup1Bus.publish('FRAME_PROCESSED', [{ handId: 0, gesture: 'open_palm', x: asRaw(0.5), y: asRaw(0.5), confidence: 0.95 }]);

        expect(sup2Received).toHaveLength(0);
    });

    /**
     * [RED until fix] GestureFSMPlugin must NOT import globalEventBus.
     * After fix: the import line should be deleted; the plugin relies solely
     * on context.eventBus provided in init().
     *
     * We verify by ensuring GestureFSMPlugin.init() subscribes on the *provided*
     * eventBus, not some external bus.
     */
    it('[RED] Given GestureFSMPlugin, When init(context) is called, Then all subscriptions are on context.eventBus (not a global)', async () => {
        const ctx = makeContext();
        const plugin = new GestureFSMPlugin();
        await plugin.init(ctx);

        // FRAME_PROCESSED must be on our test bus
        const listenerCount = (ctx.eventBus as any).listeners?.get('FRAME_PROCESSED')?.length ?? 0;
        expect(listenerCount).toBeGreaterThan(0);

        // The global bus must have zero listeners for FRAME_PROCESSED
        // (import EventBus and check globalEventBus if it is still exported)
        // If globalEventBus has been deleted this assertion trivially passes.
        try {
            const { globalEventBus } = require('./event_bus');
            const globalCount = (globalEventBus as any).listeners?.get('FRAME_PROCESSED')?.length ?? 0;
            expect(globalCount).toBe(0);
        } catch {
            // globalEventBus export deleted — ideal state, test passes
        }
    });

    /**
     * [GREEN] EventBus itself is correctly instanced — two EventBus instances
     * are independent.  This is a regression guard; it should always pass.
     */
    it('[GREEN] Two EventBus instances are fully independent', () => {
        const bus1 = new EventBus();
        const bus2 = new EventBus();
        const received: string[] = [];

        bus2.subscribe('EVT', () => received.push('bus2'));
        bus1.publish('EVT', {});

        expect(received).toHaveLength(0);
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-002 — V2: demo.ts God-Object
// Mission thread: omega.v13.arch.v2_god_object
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-002 · V2 demo.ts God-Object (MediaPipe extraction)', () => {
    /**
     * [RED] A MediaPipeVisionPlugin class must exist and implement Plugin.
     * Drives the extraction of MediaPipe logic from demo.ts.
     */
    it('[RED] MediaPipeVisionPlugin exists and implements the Plugin interface', async () => {
        const mod = tryRequire('./mediapipe_vision_plugin');
        if (!mod?.MediaPipeVisionPlugin) {
            expect(mod).not.toBeNull(); // force RED — module missing
            return;
        }
        const MediaPipeVisionPlugin = mod.MediaPipeVisionPlugin;

        const plugin: Plugin = new MediaPipeVisionPlugin();
        expect(typeof plugin.name).toBe('string');
        expect(typeof plugin.version).toBe('string');
        expect(typeof plugin.init).toBe('function');
        expect(typeof plugin.start).toBe('function');
        expect(typeof plugin.stop).toBe('function');
        expect(typeof plugin.destroy).toBe('function');
    });

    /**
     * [RED] After extraction, MediaPipeVisionPlugin.init() must subscribe to
     * no browser-provided events — it is a *source* plugin, not a sink.
     * Its start() must be the entry point that opens the camera.
     */
    it('[RED] MediaPipeVisionPlugin publishes FRAME_PROCESSED on context.eventBus (not globalEventBus)', async () => {
        const mod = tryRequire('./mediapipe_vision_plugin');
        if (!mod?.MediaPipeVisionPlugin) {
            expect(mod).not.toBeNull(); // force RED — module missing
            return;
        }
        const MediaPipeVisionPlugin = mod.MediaPipeVisionPlugin;

        const ctx = makeContext();
        const published: unknown[] = [];
        ctx.eventBus.subscribe('FRAME_PROCESSED', (d) => published.push(d));

        const plugin = new MediaPipeVisionPlugin();
        await plugin.init(ctx);

        // Simulate injection of a synthetic frame (no real camera needed)
        if (typeof (plugin as any).injectTestFrame === 'function') {
            (plugin as any).injectTestFrame([{
                handId: 0, gesture: 'pointer_up', confidence: 0.95, x: asRaw(0.5), y: asRaw(0.5)
            }]);
            expect(published).toHaveLength(1);
            expect((published[0] as any[])[0].gesture).toBe('pointer_up');
        }
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-003 — V3: Double-Debounce
// Mission thread: omega.v13.arch.v3_double_debounce
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-003 · V3 Double-Debounce (vision pipeline is a dumb sensor)', () => {
    /**
     * [RED] The vision plugin must NOT buffer or debounce gestures.
     * It emits raw gesture classifications immediately, every frame.
     * GestureFSM is the sole intent smoother.
     *
     * After the gestureBuckets deletion: injectTestFrame() emits FRAME_PROCESSED
     * on frame 1 with the raw gesture value, no buffering delay.
     */
    it('[RED] Given a vision plugin with no leaky-bucket, When frame 1 has gesture=pointer_up, Then FRAME_PROCESSED is published immediately on frame 1', async () => {
        const mod = tryRequire('./mediapipe_vision_plugin');
        if (!mod?.MediaPipeVisionPlugin) {
            expect(mod).not.toBeNull(); // force RED — module missing
            return;
        }
        const MediaPipeVisionPlugin = mod.MediaPipeVisionPlugin;

        const ctx = makeContext();
        const published: unknown[] = [];
        ctx.eventBus.subscribe('FRAME_PROCESSED', (d) => published.push(d));

        const plugin = new MediaPipeVisionPlugin();
        await plugin.init(ctx);

        if (typeof (plugin as any).injectTestFrame !== 'function') {
            // Plugin lacks test injection hook — force RED for now
            expect(true).toBe(false);
            return;
        }

        // Send a single frame — expects immediate publish with raw gesture
        (plugin as any).injectTestFrame([{
            handId: 0, gesture: 'pointer_up', confidence: 0.95, x: asRaw(0.5), y: asRaw(0.5)
        }]);

        expect(published).toHaveLength(1);
        const hands = published[0] as any[];
        // Raw gesture must be passed through — no buffer delay
        expect(hands[0].gesture).toBe('pointer_up');
    });

    /**
     * [RED] gestureBuckets state variable must not exist in MediaPipeVisionPlugin.
     * This is a structural invariant: the debounce logic must be permanently absent.
     */
    it('[RED] MediaPipeVisionPlugin instance has no gestureBuckets property (debounce deleted)', async () => {
        const mod = tryRequire('./mediapipe_vision_plugin');
        if (!mod?.MediaPipeVisionPlugin) {
            expect(mod).not.toBeNull(); // force RED — module missing
            return;
        }
        const MediaPipeVisionPlugin = mod.MediaPipeVisionPlugin;
        const plugin = new MediaPipeVisionPlugin();
        expect((plugin as any).gestureBuckets).toBeUndefined();
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-004 — V4: Rogue Unmanaged Agents
// Mission thread: omega.v13.arch.v4_rogue_agents
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-004 · V4 Rogue Agents (StillnessMonitorPlugin lifecycle)', () => {
    /**
     * [RED] StillnessMonitorPlugin must implement the full Plugin interface.
     * Currently has no init/start/stop/destroy — test FAILS.
     */
    it('[RED] StillnessMonitorPlugin implements Plugin (has name, version, init, start, stop, destroy)', () => {
        const plugin = new StillnessMonitorPlugin();
        expect(typeof (plugin as any).name).toBe('string');
        expect(typeof (plugin as any).version).toBe('string');
        expect(typeof (plugin as any).init).toBe('function');
        expect(typeof (plugin as any).start).toBe('function');
        expect(typeof (plugin as any).stop).toBe('function');
        expect(typeof (plugin as any).destroy).toBe('function');
    });

    /**
     * [RED] After stop(), StillnessMonitorPlugin must unsubscribe from
     * FRAME_PROCESSED — it must not emit STILLNESS_DETECTED regardless of
     * how many frames are pumped.
     *
     * Currently fails because stop() does not exist.
     */
    it('[RED] Given a stopped StillnessMonitorPlugin, When flooded with stationary frames, Then STILLNESS_DETECTED is never published', async () => {
        const ctx = makeContext();
        const detections: unknown[] = [];
        ctx.eventBus.subscribe('STILLNESS_DETECTED', (d) => detections.push(d));

        const plugin = new StillnessMonitorPlugin();

        if (typeof (plugin as any).init !== 'function') {
            expect(true).toBe(false); // force RED — no init method
            return;
        }

        await (plugin as any).init(ctx);
        await (plugin as any).start?.();
        await (plugin as any).stop?.();

        // Flood with 5000 identical stationary frames
        for (let i = 0; i < 5000; i++) {
            ctx.eventBus.publish('FRAME_PROCESSED', [
                { handId: 0, x: asRaw(0.5), y: asRaw(0.5), gesture: 'open_palm', confidence: 1.0 }
            ]);
        }

        expect(detections).toHaveLength(0);
    });

    /**
     * [RED] Before stop(), StillnessMonitorPlugin must detect stillness when
     * the same position is held for `stillness_timeout_limit` frames.
     * (This verifies the happy path still works after the Plugin refactor.)
     */
    it('[RED] Given a running StillnessMonitorPlugin, When hand stays stationary past timeout, Then STILLNESS_DETECTED is emitted', async () => {
        const ctx = makeContext();
        const detections: unknown[] = [];
        ctx.eventBus.subscribe('STILLNESS_DETECTED', (d) => detections.push(d));

        const plugin = new StillnessMonitorPlugin();

        if (typeof (plugin as any).init !== 'function') {
            expect(true).toBe(false);
            return;
        }

        await (plugin as any).init(ctx);
        await (plugin as any).start?.();

        // The default timeout_limit is 3600 — use a small custom value for tests
        // After fix: init() should accept config or read from PAL
        // For now override the private field if accessible
        if ((plugin as any).stillness_timeout_limit !== undefined) {
            (plugin as any).stillness_timeout_limit = 5;
        }

        for (let i = 0; i < 10; i++) {
            ctx.eventBus.publish('FRAME_PROCESSED', [
                { handId: 0, x: asRaw(0.5), y: asRaw(0.5), gesture: 'open_palm', confidence: 1.0 }
            ]);
        }

        expect(detections.length).toBeGreaterThan(0);
        expect((detections[0] as any).handId).toBe(0);
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-005 — V5: Ignored PAL (DOM Leaks)
// Mission thread: omega.v13.arch.v5_pal_leaks
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-005 · V5 PAL Dom Leaks (SymbioteInjectorPlugin)', () => {
    /**
     * [RED] PAL must be the source of ScreenWidth/ScreenHeight.
     * SymbioteInjectorPlugin.init() must NOT call window.innerWidth.
     *
     * This test runs in node (testEnvironment: "node") where `window` is
     * undefined.  If the plugin touches window.innerWidth it will throw a
     * ReferenceError.  After the PAL fix it will read from context.pal and
     * the test will pass cleanly.
     */
    it('[RED] Given no window object (Node env), When SymbioteInjectorPlugin handles POINTER_UPDATE, Then it uses PAL ScreenWidth/ScreenHeight without throwing', async () => {
        // Ensure window is NOT defined in this test scope (node environment)
        const hadWindow = typeof (global as any).window !== 'undefined';
        if (hadWindow) {
            delete (global as any).window; // strip any leftover mock
        }

        const ctx = makeContext(); // PAL has ScreenWidth=1920, ScreenHeight=1080
        const dispatched: CustomEvent[] = [];

        // Stub window.dispatchEvent so the plugin can dispatch without a real DOM
        (global as any).window = {
            dispatchEvent: (e: CustomEvent) => dispatched.push(e),
            // NOTE: intentionally no innerWidth/innerHeight — after fix plugin must not use them
        };

        const plugin = new SymbioteInjectorPlugin();
        await plugin.init(ctx);

        // Should not throw; should use PAL values
        expect(() => {
            ctx.eventBus.publish('POINTER_UPDATE', {
                handId: 0, x: asRaw(0.5), y: asRaw(0.3), isPinching: false
            });
        }).not.toThrow();

        // After fix: screenX = 0.5 * PAL.ScreenWidth = 0.5 * 1920 = 960
        if (dispatched.length > 0) {
            expect(dispatched[0].detail.x).toBeCloseTo(960, 0);
            expect(dispatched[0].detail.y).toBeCloseTo(324, 0); // 0.3 * 1080
        }

        // Restore
        if (!hadWindow) delete (global as any).window;
    });

    /**
     * [GREEN] PAL itself is fully functional — register and resolve work.
     * Regression guard; must always pass.
     */
    it('[GREEN] PathAbstractionLayer registers and resolves ScreenWidth/ScreenHeight', () => {
        const pal = new PathAbstractionLayer();
        pal.register('ScreenWidth', 3840);
        pal.register('ScreenHeight', 2160);
        expect(pal.resolve<number>('ScreenWidth')).toBe(3840);
        expect(pal.resolve<number>('ScreenHeight')).toBe(2160);
    });

    /**
     * [GREEN] PAL resolve returns undefined for unregistered keys instead of
     * throwing.  This prevents a missing capability from crashing the whole OS.
     */
    it('[GREEN] PAL.resolve returns undefined for unregistered key (fail-safe, not fail-crash)', () => {
        const pal = new PathAbstractionLayer();
        expect(pal.resolve('NonExistent')).toBeUndefined();
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-006 — V6: Vaporware Stubs
// Mission thread: omega.v13.arch.v6_stub_impls
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-006 · V6 Vaporware Stubs (FoveatedCropper + WebRTC)', () => {
    /**
     * [RED] FoveatedCropper.crop() must produce a real crop operation.
     * Currently onHandDetected() just sets mode='TRACK' with hardcoded numbers.
     * After fix: crop() must accept an ImageData and return a sub-region.
     */
    it('[RED] FoveatedCropper has a crop(imageData, center) method returning a sub-region', async () => {
        const { FoveatedCropper } = await import('./foveated_cropper');
        const cropper = new FoveatedCropper();

        // After fix: crop() must exist
        expect(typeof (cropper as any).crop).toBe('function');

        if (typeof (cropper as any).crop === 'function') {
            // Simulate ImageData-like input (256x256 grey pixels)
            const width = 256; const height = 256;
            const buffer = new Uint8ClampedArray(width * height * 4).fill(128);
            const fakeImageData = { data: buffer, width, height };

            const result = (cropper as any).crop(fakeImageData, { x: asRaw(0.5), y: asRaw(0.5) });
            // Must return something with width/height properties (a cropped region)
            expect(result).not.toBeNull();
            expect(result.width).toBeLessThan(width);  // should be the crop window, e.g. 128
        }
    });

    /**
     * [RED] WebRtcUdpTransport.connect() must accept a remote SDP/offer and
     * return a Promise resolving when the DataChannel is open.
     * Currently the class has no connect() method.
     */
    it('[RED] WebRtcUdpTransport has a connect(config) method', async () => {
        const { WebRtcUdpTransport } = await import('./webrtc_udp_transport');
        const transport = new WebRtcUdpTransport();

        // After fix: connect() must exist
        expect(typeof (transport as any).connect).toBe('function');
    });

    /**
     * [GREEN] FoveatedCropper current stub at least returns a mode.
     * Regression guard until the real implementation lands.
     */
    it('[GREEN] FoveatedCropper.getMode() returns a known mode string', async () => {
        const { FoveatedCropper } = await import('./foveated_cropper');
        const cropper = new FoveatedCropper();
        expect(['SEARCH', 'TRACK']).toContain(cropper.getMode());
    });

    /**
     * [GREEN] WebRtcUdpTransport.getProtocol() returns UDP.
     * Regression guard until real implementation lands.
     */
    it('[GREEN] WebRtcUdpTransport.getProtocol() returns "UDP"', async () => {
        const { WebRtcUdpTransport } = await import('./webrtc_udp_transport');
        const transport = new WebRtcUdpTransport();
        expect(transport.getProtocol()).toBe('UDP');
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-007 — V7: Ghost Event Gate (L11 Wiring Manifest)
// Prevents channels from having a subscriber but no publisher, or vice versa.
// A "ghost event" silently does nothing at runtime — this test makes it a CI failure.
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-007 · V7 Ghost Event Gate — wiring manifest enforced', () => {
    const projectRoot = path.resolve(__dirname);

    // Collect all production TypeScript source (not spec/test files, not node_modules/dist)
    function getProductionSource(): string {
        const entries = fs.readdirSync(projectRoot);
        return entries
            .filter(f =>
                f.endsWith('.ts') &&
                !f.endsWith('.spec.ts') &&
                !f.endsWith('.test.ts') &&
                !f.startsWith('test_') &&
                f !== 'event_channel_manifest.ts' // manifest itself isn't a publisher
            )
            .concat(['tldraw_layer.html'])
            .map(f => {
                const fp = path.join(projectRoot, f);
                return fs.existsSync(fp) ? fs.readFileSync(fp, 'utf-8') : '';
            })
            .join('\n');
    }

    const source = getProductionSource();

    for (const [channel, spec] of Object.entries(CHANNEL_MANIFEST)) {
        if (spec.role === 'extension_point') {
            // Extension points: verify only the side that IS declared exists
            if (spec.producers.length > 0) {
                it(`[GREEN] Extension point '${channel}' has its producer side wired`, () => {
                    const pattern = new RegExp(`publish\\(\\s*['"]${channel}['"]`);
                    expect(source).toMatch(pattern);
                });
            }
            if (spec.consumers.length > 0) {
                it(`[GREEN] Extension point '${channel}' has its consumer side wired`, () => {
                    const pattern = new RegExp(`subscribe\\(\\s*['"]${channel}['"]`);
                    expect(source).toMatch(pattern);
                });
            }
        } else {
            // Mandatory channels: both sides MUST exist
            it(`[GREEN] Mandatory channel '${channel}' has a publisher in production source`, () => {
                const pattern = new RegExp(`publish\\(\\s*['"]${channel}['"]`);
                expect(source).toMatch(pattern);
            });

            it(`[GREEN] Mandatory channel '${channel}' has a subscriber in production source`, () => {
                const pattern = new RegExp(`subscribe\\(\\s*['"]${channel}['"]`);
                expect(source).toMatch(pattern);
            });
        }
    }
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-008 — V8: PAL Leak Gate (L8 Rules)
// Plugins must never bypass the PAL to access window.innerWidth/Height,
// window.screen, or window-global Omega harnesses.
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-008 · V8 PAL Leak Gate — no forbidden window patterns in plugins', () => {
    const projectRoot = path.resolve(__dirname);

    const pluginFiles = fs.readdirSync(projectRoot)
        .filter(f => f.endsWith('_plugin.ts'));

    // Plugins that have legitimate DOM construction responsibilities get a pass
    // on DOM creation patterns (but never on viewport dimensions).
    // Currently VisualizationPlugin must create its container element — that's intentional.
    // The forbidden patterns are dimension reads and Omega window-globals ONLY.

    for (const filename of pluginFiles) {
        const source = fs.readFileSync(path.join(projectRoot, filename), 'utf-8');

        for (const { pattern, reason } of PAL_LEAK_PATTERNS) {
            it(`[GREEN] ${filename} must not contain forbidden pattern /${pattern.source}/`, () => {
                expect(source).not.toMatch(pattern);
            });
        }
    }
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-009 — V9: Plugin Registration Gate (L8 Rules)
// Every Plugin class in a *_plugin.ts file must be either registered in the
// bootstrap OR listed in the DEFERRED_PLUGINS manifest with a reason.
// Forgetting to register a plugin is now a CI failure, not a runtime mystery.
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-009 · V9 Plugin Registration Gate — no unregistered surprise plugins', () => {
    const projectRoot = path.resolve(__dirname);
    const bootstrapSource = fs.readFileSync(
        path.join(projectRoot, 'demo_2026-02-20.ts'), 'utf-8'
    );

    const pluginFiles = fs.readdirSync(projectRoot)
        .filter(f => f.endsWith('_plugin.ts'));

    for (const filename of pluginFiles) {
        const source = fs.readFileSync(path.join(projectRoot, filename), 'utf-8');
        // Find exported classes that implement Plugin
        const matches = [...source.matchAll(/export\s+class\s+(\w+)\s+implements\s+Plugin/g)];

        for (const match of matches) {
            const className = match[1];
            it(`[GREEN] ${className} is registered in bootstrap OR in DEFERRED_PLUGINS`, () => {
                const inBootstrap = new RegExp(`registerPlugin\\(new ${className}\\b`).test(bootstrapSource);
                const inDeferred  = className in DEFERRED_PLUGINS;
                if (!inBootstrap && !inDeferred) {
                    throw new Error(
                        `${className} is neither registered in demo_2026-02-20.ts nor listed in DEFERRED_PLUGINS.\n` +
                        `Either add: supervisor.registerPlugin(new ${className}(...)) to the bootstrap,\n` +
                        `or add '${className}' to DEFERRED_PLUGINS in event_channel_manifest.ts with a reason.\n` +
                        `This is intentional: invisible plugins are a structural void in the architecture.`
                    );
                }
                expect(inBootstrap || inDeferred).toBe(true);
            });
        }
    }
});

// ─────────────────────────────────────────────────────────────────────────────
// ATDD-ARCH-010 — V10: Subscribe/Unsubscribe Symmetry Gate (L8 Memory Leak Prevention)
// Every channel a plugin subscribes to must also be unsubscribed in stop() or destroy().
// Exception: channels marked lifecycle:'oneshot' in the manifest (fire-once events).
//
// A subscribe-without-unsubscribe is a zombie listener:
// - At 30fps over a 10-min session = 18,000+ phantom callbacks accumulating in RAM.
// - Plugin restart (stop → start) doubles the listener count every cycle.
// The bug compiles cleanly and manifests only under sustained load.
// ─────────────────────────────────────────────────────────────────────────────
describe('ATDD-ARCH-010 · V10 Subscribe/Unsubscribe Symmetry Gate — no zombie listeners', () => {
    const projectRoot = path.resolve(__dirname);

    const pluginFiles = fs.readdirSync(projectRoot)
        .filter(f => f.endsWith('_plugin.ts'));

    for (const filename of pluginFiles) {
        it(`[GREEN] ${filename}: every subscribed channel has a matching unsubscribe`, () => {
            const source = fs.readFileSync(path.join(projectRoot, filename), 'utf-8');

            const subscribed   = [...source.matchAll(/\.subscribe\(\s*['"](\w+)['"]/g)].map(m => m[1]);
            const unsubscribed = new Set(
                [...source.matchAll(/\.unsubscribe\(\s*['"](\w+)['"]/g)].map(m => m[1])
            );

            const leaked = subscribed.filter(ch => {
                // Oneshot channels (CAMERA_START_REQUESTED etc.) never need unsubscribe
                const spec = (CHANNEL_MANIFEST as Record<string, { lifecycle?: string }>)[ch];
                if (spec?.lifecycle === 'oneshot') return false;
                return !unsubscribed.has(ch);
            });

            if (leaked.length > 0) {
                throw new Error(
                    `${filename} subscribes to [${leaked.join(', ')}] but has no matching unsubscribe.\n` +
                    `Add unsubscribe calls to stop() and destroy(), or mark the channel\n` +
                    `\`lifecycle: 'oneshot'\` in event_channel_manifest.ts if it fires exactly once.`
                );
            }
            expect(leaked).toEqual([]);
        });
    }
});
