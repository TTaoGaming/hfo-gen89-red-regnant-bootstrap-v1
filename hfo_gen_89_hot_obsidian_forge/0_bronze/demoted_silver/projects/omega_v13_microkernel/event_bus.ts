import type { RawHandData, LandmarkPoint } from './hand_types';

// ── ARCH-TYPED-EVENTS (L6 — Information Flows leverage level) ────────────────
//
// All EventBus event names and their payload types are declared ONCE here.
// Consequences enforced at compile time:
//   • Misspelled event name   → compile error (not a silent no-op at runtime)
//   • Wrong payload shape     → compile error (not a silent undefined at runtime)
//   • New events MUST be registered below before they can be used
//
// The open extension point [key: string]: unknown allows test events and
// future experimental events without breaking type safety on known events.
// Known events still resolve to their specific types; unknown keys → unknown.
//
// ATDD-ARCH-001 compliance: globalEventBus singleton DELETED (see below).
// Every consumer receives an isolated EventBus via PluginContext.eventBus.

export interface MicrokernelEvents {
    // ── Sensor layer ──────────────────────────────────────────────────────────
    /** MediaPipeVisionPlugin → all subscribers: raw frame of detected hands */
    'FRAME_PROCESSED'       : RawHandData[];

    // ── FSM output ────────────────────────────────────────────────────────────
    /** GestureFSMPlugin → AudioEngine/Viz: FSM state transition per hand */
    'STATE_CHANGE'          : { handId: number; previousState: string; currentState: string };
    /** GestureFSMPlugin → W3CPointerFabric/SymbioteInjector: cooked pointer */
    'POINTER_UPDATE'        : { handId: number; x: number; y: number; isPinching: boolean;
                                gesture?: string; confidence?: number; rawLandmarks?: LandmarkPoint[] };
    /** GestureFSMPlugin → W3CPointerFabric: hand left coast or left scene */
    'POINTER_COAST'         : { handId: number; isPinching: boolean; destroy: boolean };

    // ── Stillness ─────────────────────────────────────────────────────────────
    /** StillnessMonitorPlugin → GestureFSMPlugin: hand held still past timeout */
    'STILLNESS_DETECTED'    : { handId: number; x: number; y: number };

    // ── Audio / camera lifecycle ───────────────────────────────────────────────
    /** User gesture → AudioEnginePlugin: unlock the suspended AudioContext */
    'AUDIO_UNLOCK'          : null;
    /** Shell/bootstrap → MediaPipeVisionPlugin: begin camera acquisition */
    'CAMERA_START_REQUESTED': null;

    // ── Config UI ─────────────────────────────────────────────────────────────
    /** External source → Shell: toggle the settings drawer open/closed */
    'SETTINGS_TOGGLE'       : null;
    /** Shell → listeners: new open/closed state of the settings drawer */
    'SETTINGS_PANEL_STATE'  : { open: boolean };
    /** LayerManager → listeners: a layer's CSS opacity changed */
    'LAYER_OPACITY_CHANGE'  : { id: string; opacity: number };
    /** Config UI → demo bootstrap: overscan scale factor changed (plain number) */
    'OVERSCAN_SCALE_CHANGE' : number;

    // ── Physics telemetry ──────────────────────────────────────────────────────
    /** BabylonPhysicsPlugin → golden master test: per-frame physics stats */
    'BABYLON_PHYSICS_FRAME' : { frameIndex: number; handCount: number; handIds: number[]; sphereCount: number };

    // ── Open extension point ───────────────────────────────────────────────────
    // Known events above are strictly typed.
    // Unknown keys (test events, forward-declared future events) accept any payload.
    [key: string]: unknown;
}

// ── EventCallback ─────────────────────────────────────────────────────────────

export type EventCallback<T = unknown> = (data: T) => void;

// ── Typed EventBus ────────────────────────────────────────────────────────────

/**
 * Isolating typed event bus. Generic over event map M (defaults to MicrokernelEvents).
 *
 * ARCH rules enforced:
 *   ATDD-ARCH-001  No global singleton — each PluginSupervisor owns one instance.
 *   ARCH-ZOMBIE    Callbacks passed to subscribe() MUST be stable references
 *                  (readonly class properties bound in the constructor).
 *                  Inline .bind() in subscribe() is a build error (ESLint ARCH-ZOMBIE).
 *   ARCH-TYPED-EVENTS  All event names resolve to a declared payload type.
 */
export class EventBus<M extends Record<string, unknown> = MicrokernelEvents> {
    /**
     * @internal — accessed only by tests via `(bus as any).listeners`.
     * Production code outside this class must never read this field.
     */
    private readonly listeners: Map<string, EventCallback<unknown>[]> = new Map();

    subscribe<K extends keyof M & string>(event: K, callback: EventCallback<M[K]>): void {
        const list = this.listeners.get(event) ?? [];
        list.push(callback as EventCallback<unknown>);
        this.listeners.set(event, list);
    }

    unsubscribe<K extends keyof M & string>(event: K, callback: EventCallback<M[K]>): void {
        const list = this.listeners.get(event);
        if (!list) return;
        const idx = list.indexOf(callback as EventCallback<unknown>);
        if (idx !== -1) list.splice(idx, 1);
    }

    publish<K extends keyof M & string>(event: K, data: M[K]): void {
        // ── Dev-mode dead-letter detection ───────────────────────────────────
        // A known, high-traffic event published with no subscribers is a wiring bug:
        //   (a) the subscriber plugin was not registered/initialized before publish, OR
        //   (b) the wrong bus instance is being used — ARCH-V1 isolation violation.
        // This warning fires only in development; process.env.NODE_ENV is replaced
        // at bundle time and the block is tree-shaken in production builds.
        if (process.env.NODE_ENV === 'development') {
            const list = this.listeners.get(event);
            if (!list || list.length === 0) {
                const sentinelEvents: ReadonlyArray<string> = [
                    'FRAME_PROCESSED', 'STATE_CHANGE', 'POINTER_UPDATE',
                    'POINTER_COAST', 'STILLNESS_DETECTED',
                ];
                if (sentinelEvents.includes(event)) {
                    console.warn(
                        `[EventBus] DEAD-LETTER '${event}': published to a known event` +
                        ` with 0 subscribers.\n` +
                        `  Likely causes:\n` +
                        `  1. Subscriber plugin not registered/initialized before this publish.\n` +
                        `  2. Wrong bus instance — ARCH-V1 isolation violation (two buses in play).\n` +
                        `  3. Plugin destroyed before publisher stopped.\n` +
                        `  Fix: verify PluginSupervisor.initAll() completes before startAll().`
                    );
                }
            }
        }
        const list = this.listeners.get(event);
        if (!list) return;
        for (const cb of list) cb(data);
    }
}

// ── ATDD-ARCH-001 compile-time + runtime violation trap ──────────────────────
//
// `globalEventBus` is kept as a TRAP to give useful errors when old code tries
// to use it.
//
//  COMPILE-TIME: The type `_GlobalEventBusTrap` exposes NO methods.
//  Attempting to call .subscribe() / .publish() / .unsubscribe() produces:
//    "Property 'subscribe' does not exist on type '{ readonly ATDD_ARCH_001: ... }'"
//  The property name in the error message IS the fix instruction.
//
//  RUNTIME: The Proxy's get trap throws Error('[ATDD-ARCH-001] ...') with the
//  full migration instruction visible in the stack trace.
//
//  FIX: Receive EventBus via `context.eventBus` in Plugin.init(context).
//  PluginSupervisor.initAll() injects the isolated bus into every plugin.
//
type _GlobalEventBusTrap = Readonly<{
    /** @deprecated VIOLATION — see [ATDD-ARCH-001]. Call site: the property name you accessed describes the violation. Fix: use context.eventBus from PluginSupervisor.initAll(). */
    ATDD_ARCH_001: 'VIOLATION: globalEventBus is deleted. Receive EventBus via context.eventBus injected by PluginSupervisor.initAll(). See plugin_supervisor.ts → PluginContext.eventBus';
}>;

/**
 * @deprecated ⚠️  ATDD-ARCH-001 VIOLATION ⚠️
 *
 * `globalEventBus` has been **permanently deleted**.
 *
 * **Fix:** Receive `EventBus` via `context.eventBus` in `Plugin.init(context: PluginContext)`.
 * The supervisor injects the bus:  `PluginSupervisor.initAll()` → `plugin.init(context)`.
 * See `plugin_supervisor.ts` → `PluginContext.eventBus`.
 *
 * Attempting to call `.subscribe()`, `.publish()`, or `.unsubscribe()` **will not compile**.
 * The TypeScript error message IS the fix instruction — read the type literal in the error.
 */
export const globalEventBus: _GlobalEventBusTrap = new Proxy({} as _GlobalEventBusTrap, {
    get(_target, prop: string | symbol) {
        const name = String(prop);
        throw new Error(
            `[ATDD-ARCH-001] globalEventBus.${name}() is a violation.\n` +
            `The globalEventBus singleton has been deleted.\n` +
            `Fix: Receive EventBus via context.eventBus in Plugin.init(context: PluginContext).\n` +
            `The PluginSupervisor injects the correct isolated bus during initAll().\n` +
            `See plugin_supervisor.ts → PluginContext.eventBus`
        );
    },
});