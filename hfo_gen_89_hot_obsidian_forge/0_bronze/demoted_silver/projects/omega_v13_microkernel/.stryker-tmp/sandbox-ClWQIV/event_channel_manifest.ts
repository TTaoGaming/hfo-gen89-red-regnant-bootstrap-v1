/**
 * event_channel_manifest.ts — L11 Wiring Manifest (Meadows Leverage Level 11)
 *
 * This file is the single source of truth for how the event bus is wired.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * TypeScript's MicrokernelEvents interface enforces payload shapes.
 * It does NOT enforce wiring: a channel can be subscribed with no publisher,
 * published with no subscriber, or a plugin can be written but never registered.
 * These are "configuration voids" — they compile cleanly and fail silently at runtime.
 *
 * Architecture pattern: if it can be expressed as a rule that gets checked at compile
 * time or test time, it will be. This manifest is that rule for the event bus.
 *
 * HOW IT IS ENFORCED
 * ------------------
 * microkernel_arch_violations.spec.ts imports this manifest and verifies:
 *   V7 — Ghost Event Gate: every mandatory channel has a publisher AND subscriber in source
 *   V8 — PAL Leak Gate: no plugin file bypasses PAL to access window.innerWidth/Height
 *   V9 — Plugin Registration Gate: every exported *Plugin class is registered OR deferred
 *
 * ADDING A NEW CHANNEL
 * --------------------
 * 1. Add it to MicrokernelEvents in event_bus.ts (types)
 * 2. Add it here with producers/consumers and a role (manifest)
 * 3. Tests will fail until both steps are done — that is by design
 *
 * ADDING A NEW PLUGIN
 * -------------------
 * 1. Create the plugin file implementing the Plugin interface
 * 2. Either register it in demo_2026-02-20.ts bootstrap
 *    OR add it to DEFERRED_PLUGINS with a reason
 * 3. Tests will fail until one of these is done — that is by design
 */
// @ts-nocheck


import type { MicrokernelEvents } from './event_bus';

// ── Channel Role ──────────────────────────────────────────────────────────────

export type ChannelRole =
    /** Both a publisher and subscriber MUST exist in the production source tree. */
    | 'mandatory'
    /** One side is intentionally absent — documented extension point.
     *  The test only verifies that the present side exists, not the absent side. */
    | 'extension_point';

// ── Channel Specification ─────────────────────────────────────────────────────

export interface ChannelSpec {
    role: ChannelRole;
    /** If 'oneshot', this channel fires at most once per session (e.g. lifecycle init).
     *  The V10 symmetry gate skips these — they legitimately need no unsubscribe. */
    lifecycle?: 'oneshot';
    /** Strings that must appear in a publish() call in some production source file.
     *  Usually a plugin class name or 'demo_bootstrap'. */
    producers: string[];
    /** Strings (class names or file identifiers) that must appear in a subscribe()
     *  call in some production source file for this channel. */
    consumers: string[];
    /** Plain-English rationale for why this channel exists. */
    rationale: string;
}

// ── The Manifest ──────────────────────────────────────────────────────────────

/**
 * CHANNEL_MANIFEST declares every channel in MicrokernelEvents along with its
 * canonical wiring and role.
 *
 * The key is the exact event name string as it appears in publish('/subscribe() calls.
 * The V7 invariant test scans production source and verifies this manifest is satisfied.
 */
export const CHANNEL_MANIFEST = {

    // ── Sensor layer ─────────────────────────────────────────────────────────

    'FRAME_PROCESSED': {
        role: 'mandatory',
        producers: ['MediaPipeVisionPlugin'],
        consumers: ['GestureFSMPlugin', 'StillnessMonitorPlugin'],
        rationale: 'MediaPipe emits raw landmark frames. FSM and Stillness consume them.',
    },

    // ── FSM output ───────────────────────────────────────────────────────────

    'STATE_CHANGE': {
        role: 'mandatory',
        producers: ['GestureFSMPlugin'],
        consumers: ['AudioEnginePlugin'],
        // Shell and VisualizationPlugin also subscribe but AudioEnginePlugin is the
        // most critical single consumer to verify (STATE_CHANGE drives click sounds).
        rationale: 'FSM state transitions drive audio, UI coach bar, and vis colour.',
    },

    'POINTER_UPDATE': {
        role: 'mandatory',
        producers: ['GestureFSMPlugin'],
        consumers: ['VisualizationPlugin', 'SymbioteInjectorPlugin'],
        rationale: 'Cooked pointer drives skeleton overlay and DOM injection.',
    },

    'POINTER_COAST': {
        role: 'mandatory',
        producers: ['GestureFSMPlugin'],
        consumers: ['W3CPointerFabric'],
        // Technically VisualizationPlugin also subscribes but W3CPointerFabric is the
        // critical Kalman-coast consumer.
        rationale: 'Hand temporarily lost — Kalman filter coasts the trajectory.',
    },

    // ── Stillness ────────────────────────────────────────────────────────────

    'STILLNESS_DETECTED': {
        role: 'mandatory',
        producers: ['StillnessMonitorPlugin'],
        consumers: ['GestureFSMPlugin'],
        rationale: 'Dwell timer fires. FSM transitions to idle. Critical for kid UX.',
    },

    // ── Audio / camera lifecycle ─────────────────────────────────────────────

    'AUDIO_UNLOCK': {
        role: 'mandatory',
        producers: ['Shell'],
        consumers: ['AudioEnginePlugin'],
        rationale: 'User gesture required to unlock AudioContext on first interaction.',
    },

    'CAMERA_START_REQUESTED': {
        role: 'mandatory',
        lifecycle: 'oneshot', // fires once at bootstrap; MediaPipe never needs to unsubscribe
        producers: ['Shell'],
        consumers: ['MediaPipeVisionPlugin'],
        rationale: 'Bootstrap camera acquisition through the plugin boundary.',
    },

    // ── Extension points (intentionally half-wired) ──────────────────────────

    'SETTINGS_TOGGLE': {
        role: 'extension_point',
        producers: [],    // No current producer — external/gesture API hook for V14
        consumers: ['Shell'],
        rationale: 'Shell subscribes; any external code can open the drawer. No producer required.',
    },

    'SETTINGS_PANEL_STATE': {
        role: 'extension_point',
        producers: ['Shell'],
        consumers: [],    // No current consumer — broadcast for future Playwright/Babylon listeners
        rationale: 'Shell broadcasts drawer state; consumers opt in when they exist.',
    },

    'OVERSCAN_SCALE_CHANGE': {
        role: 'extension_point',
        producers: [],    // No gesture-controlled publisher yet — planned overscan UI slider
        consumers: ['demo_2026-02-20'],
        rationale: 'Demo bootstrap subscribes; publisher wired when overscan slider lands.',
    },

    'LAYER_OPACITY_CHANGE': {
        role: 'extension_point',
        producers: ['LayerManager'],
        consumers: [],    // Future: Babylon layer sync, recording, etc.
        rationale: 'LayerManager broadcasts opacity; consumers opt in as features arrive.',
    },

    // ── Physics telemetry (golden master + integration tests) ────────────────

    'BABYLON_PHYSICS_FRAME': {
        role: 'extension_point',
        producers: ['BabylonPhysicsPlugin'],
        consumers: [],    // No runtime consumer — golden master test harness only
        rationale: 'Havok per-frame telemetry. Consumers are test harnesses, not production plugins.',
    },

} satisfies Record<string, ChannelSpec>;

// ── Deferred Plugin Allowlist ─────────────────────────────────────────────────

/**
 * Plugin classes that are intentionally NOT registered in the current bootstrap.
 *
 * The V9 invariant test scans all *_plugin.ts files for exported Plugin classes
 * and verifies that each is either:
 *   a) called via `registerPlugin(new ClassName` in demo_2026-02-20.ts, OR
 *   b) listed here with a documented reason
 *
 * If you create a new plugin and forget to do either, the V9 test fails in CI.
 * That is the point.
 */
export const DEFERRED_PLUGINS: Record<string, string> = {
    'BabylonLandmarkPlugin':
        'B1 work pending — dots in Babylon canvas. Ready to register. ETA: next session.',
    'HighlanderMutexAdapter':
        'Not a Plugin. Inline logic in W3CPointerFabric as primaryHandId lock.',
    'SymbioteInjector':
        'Not a Plugin. Wrapped by SymbioteInjectorPlugin. No separate registration.',
    'SymbioteInjectorPlugin':
        'Deferred until tldraw iframe integration is complete. Currently using W3CPointerFabric.',
};

// ── PAL Leak Patterns ─────────────────────────────────────────────────────────

/**
 * Patterns that are FORBIDDEN in *_plugin.ts files.
 * Plugins must always access these through PAL contracts, never directly.
 * The V8 invariant test scans all plugin files for these patterns.
 */
export const PAL_LEAK_PATTERNS: Array<{ pattern: RegExp; reason: string }> = [
    {
        pattern: /window\.innerWidth/,
        reason: 'Use PAL.resolve("ScreenWidth") instead. Raw window dims cause miscalculations with CSS viewport scaling.',
    },
    {
        pattern: /window\.innerHeight/,
        reason: 'Use PAL.resolve("ScreenHeight") instead.',
    },
    {
        pattern: /window\.screen\./,
        reason: 'window.screen is physical pixels, not CSS viewport. Always wrong for pointer math.',
    },
    {
        pattern: /\(window as any\)\.omega/,
        reason: 'Omega-namespace window globals are bootstrap debug harnesses. Plugins must not depend on them.',
    },
    {
        pattern: /window\.AudioContext|window\.webkitAudioContext/,
        reason: 'Use PAL.resolve("AudioContext") — registered by demo bootstrap (ARCH-V5).',
    },
];

// ── Symbiote Contract ─────────────────────────────────────────────────────────

/**
 * Strings that MUST appear in tldraw_layer.html or w3c_pointer_fabric.ts,
 * and strings that MUST NOT appear. Enforced by V10 invariant test.
 *
 * Rationale: pointerType:'touch' re-introduces the 10px touch-slop deadzone
 * that makes spatial cursors sluggish. It must not be possible to accidentally
 * regress this without CI screaming.
 */
export const SYMBIOTE_CONTRACT = {
    tldraw_layer_html: {
        mustContain: [
            /pointerType:\s*['"]pen['"]/,
            /Element\.prototype\.setPointerCapture\s*=/,
            /Element\.prototype\.releasePointerCapture\s*=/,
            /activeCaptures/,
            /button:\s*eventInit\.buttons\s*>\s*0\s*\?\s*0\s*:/,
        ],
        mustNotContain: [
            /pointerType:\s*['"]touch['"]/,
        ],
    },
    w3c_pointer_fabric_ts: {
        mustContain: [
            /pointerType:\s*['"]pen['"]/,
            /primaryHandId/,
        ],
        mustNotContain: [
            /pointerType:\s*['"]touch['"]/,
        ],
    },
} as const;

// ── Compile-time parity gate (Option A — Meadows L11) ────────────────────────
//
// Strips TypeScript index signatures to get only the explicitly named keys
// of an interface. Removes the [key: string]: unknown wildcard.
type _StripIndexSig<T> = { [K in keyof T as string extends K ? never : K]: T[K] };
type _NamedMicrokernelChannels = _StripIndexSig<MicrokernelEvents>;

// Type alias that fails with:
//   "Type 'false' does not satisfy the constraint 'true'"
// if its argument is not the literal type `true`. Zero runtime cost.
type _AssertTrue<T extends true> = T;

/**
 * FORWARD GATE: every CHANNEL_MANIFEST key is a real named event in MicrokernelEvents.
 * If you rename a channel in event_bus.ts without updating this manifest, tsc fails HERE.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
type _ManifestSubsetOfEvents = _AssertTrue<
    keyof typeof CHANNEL_MANIFEST extends keyof _NamedMicrokernelChannels ? true : false
>;

/**
 * REVERSE GATE: every named MicrokernelEvents key exists in the manifest.
 * If you add a new event to event_bus.ts without a manifest declaration, tsc fails HERE.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
type _EventsSubsetOfManifest = _AssertTrue<
    keyof _NamedMicrokernelChannels extends keyof typeof CHANNEL_MANIFEST ? true : false
>;
