/**
 * w3c_pointer_fabric.ts
 * 
 * The Shared Data Fabric for 2D projection of 3D hand landmarks.
 * This layer translates the raw MediaPipe/Babylon coordinates into standard
 * W3C Pointer Events (pointerdown, pointermove, pointerup) and dispatches
 * them to the DOM.
 * 
 * Crucially, it ensures iframe coordinate parity by calculating bounding
 * client rects and projecting the normalized coordinates correctly across
 * document boundaries.
 */
// @ts-nocheck


import { KalmanFilter2D } from './kalman_filter';
import { Plugin, PluginContext } from './plugin_supervisor';

// Scenario (ATDD-ARCH-004): Given W3CPointerFabric implements Plugin
//                            When PluginSupervisor.initAll() runs
//                            Then W3CPointerFabric subscribes via context.eventBus only
// Scenario (ATDD-ARCH-005): Given PAL has ScreenWidth/ScreenHeight registered
//                            When processLandmark() normalises coordinates
//                            Then window.innerWidth is never called

interface IElement {
    tagName: string;
    getBoundingClientRect(): { left: number, top: number, width: number, height: number };
    dispatchEvent(e: unknown): void;
    contentWindow?: { postMessage(msg: unknown, targetOrigin: string): void };
}
interface IWindow {
    getComputedStyle(el: IElement): { pointerEvents: string };
}
interface IPointerEventInit {
    pointerId: number;
    pointerType: string;
    isPrimary: boolean;
    clientX: number;
    clientY: number;
    screenX: number;
    screenY: number;
    button: number;
    buttons: number;
    pressure: number;
    bubbles: boolean;
    cancelable: boolean;
    composed: boolean;
}
interface IPointerEvent {
    type: string;
}

export interface PointerFabricConfig {
    targetElement: unknown;
    dispatchToIframes: boolean;
    lookaheadSteps: number;
    smoothingR: number;
    smoothingQ: number;
}

export class W3CPointerFabric implements Plugin {
    // ── Plugin identity (ATDD-ARCH-004) ────────────────────────────────────────
    public readonly name = 'W3CPointerFabricPlugin';
    public readonly version = '1.0.0';
    private context!: PluginContext;
    private boundOnPointerUpdate!: (data: { handId: number, x: number, y: number, isPinching: boolean }) => void;
    private boundOnPointerCoast!: (data: { handId: number, isPinching: boolean, destroy?: boolean }) => void;

    private config: PointerFabricConfig;
    private activePointers: Map<number, { x: number, y: number, isDown: boolean }>;
    private filters: Map<number, KalmanFilter2D>;
    private coalescedBuffer: Map<number, { x: number, y: number, time: number }[]>;
    /** Highlander V13: lock to first hand seen; drop second hand entirely.
     *  Prevents React isPrimary panic and MediaPipe hand-index-shuffle teleportation.
     *  Released when the primary hand is lost. V14 will route second hand to WheelEvents. */
    private primaryHandId: number | null = null;
    
    // We use a synthetic pointer ID range to avoid colliding with real mouse/touch events
    private readonly POINTER_ID_BASE = 10000;

    constructor(config: Partial<PointerFabricConfig> = {}) {
        this.config = {
            targetElement: null,
            dispatchToIframes: true,
            lookaheadSteps: 3,
            // MediaPipe tasks-vision has NO built-in landmark smoothing (verified Feb 2026).
            // The legacy @mediapipe/hands had LandmarksSmoothingCalculator (1 Euro Filter)
            // but it was dropped in the Tasks API rewrite. Kalman is our only smoother.
            // Q=0.05: trust the model (landmark jitter is real, model is stable).
            // R=10.0: high measurement noise because raw landmarks jump ~5px/frame at 30fps.
            smoothingR: 10,
            smoothingQ: 0.05,
            ...config
        };
        
        this.activePointers = new Map();
        this.filters = new Map();
        this.coalescedBuffer = new Map();
        // NOTE: subscriptions moved to init() — constructor never touches the bus (ATDD-ARCH-004)
    }

    // ── Plugin lifecycle (ATDD-ARCH-004) ───────────────────────────────────────
    public init(context: PluginContext): void {
        this.context = context;
        this.boundOnPointerUpdate = this.onPointerUpdate.bind(this);
        this.boundOnPointerCoast  = this.onPointerCoast.bind(this);
        context.eventBus.subscribe('POINTER_UPDATE', this.boundOnPointerUpdate);
        context.eventBus.subscribe('POINTER_COAST',  this.boundOnPointerCoast);
        // Subscribe to live config changes so Kalman Q/R can be tuned via the settings drawer
        // without reloading. Existing filter instances are reset — they re-init on next frame.
        const configManager = context.pal.resolve<{ subscribe: (cb: (cfg: { kalman_q?: number, kalman_r?: number }) => void) => void }>('ConfigManager');
        if (configManager) {
            configManager.subscribe((cfg: { kalman_q?: number, kalman_r?: number }) => {
                if (cfg.kalman_q !== undefined) this.config.smoothingQ = cfg.kalman_q;
                if (cfg.kalman_r !== undefined) this.config.smoothingR = cfg.kalman_r;
                // Reset filters so they pick up new params on next landmark frame.
                this.filters.forEach(f => f.reset());
            });
        }
    }

    public start(): void { /* subscriptions active after init() */ }

    public stop(): void {
        if (!this.context) return;
        this.context.eventBus.unsubscribe('POINTER_UPDATE', this.boundOnPointerUpdate);
        this.context.eventBus.unsubscribe('POINTER_COAST',  this.boundOnPointerCoast);
    }

    public destroy(): void {
        this.stop();
        this.activePointers.clear();
        this.filters.clear();
        this.coalescedBuffer.clear();
    }

    private onPointerUpdate(data: { handId: number, x: number, y: number, isPinching: boolean }) {
        // Highlander V13: lock to first hand that appears; drop second.
        // MediaPipe may shuffle hand indices when hands cross — locking to the
        // first-seen handId prevents cursor teleportation and React isPrimary panic.
        if (this.primaryHandId === null) this.primaryHandId = data.handId;
        else if (data.handId !== this.primaryHandId) return;
        this.processLandmark(data.handId, data.x, data.y, data.isPinching);
    }

    private onPointerCoast(data: { handId: number, isPinching: boolean, destroy?: boolean }) {
        // Highlander V13: only coast the primary hand
        if (this.primaryHandId !== null && data.handId !== this.primaryHandId) return;
        if (data.destroy) {
            // removeHand() fires pointerup + pointercancel then cleans all state.
            // Must NOT call coastLandmark first — that emits spurious pointermove events
            // after the pointer should already be cancelled (SABOTEUR-4 / stuck-pointer fix).
            this.removeHand(data.handId);
        } else {
            this.coastLandmark(data.handId, data.isPinching);
        }
    }

    /**
     * Update the configuration (e.g., from the ConfigMosaic)
     */
    public updateConfig(newConfig: Partial<PointerFabricConfig>) {
        this.config = { ...this.config, ...newConfig };
        
        // If smoothing parameters changed, we might want to reset filters
        // but for now we just let them adapt.
    }

    /**
     * Process a raw 3D landmark and project it to the 2D screen
     * @param handId 0 for left, 1 for right (or arbitrary IDs)
     * @param normalizedX 0.0 to 1.0 (left to right)
     * @param normalizedY 0.0 to 1.0 (top to bottom)
     * @param isPinching True if the gesture FSM is in COMMIT state
     */
    public processLandmark(handId: number, normalizedX: number, normalizedY: number, isPinching: boolean) {
        const pointerId = this.POINTER_ID_BASE + handId;
        
        // 1. Get or create the Kalman filter for this hand
        if (!this.filters.has(pointerId)) {
            this.filters.set(pointerId, new KalmanFilter2D(this.config.smoothingR, this.config.smoothingQ));
        }
        const filter = this.filters.get(pointerId)!;

        // 2. Convert normalized coordinates to screen pixels
        // PAL-sourced dimensions (ATDD-ARCH-005): never window.innerWidth
        const screenWidth  = this.context?.pal?.resolve<number>('ScreenWidth')  || 1920;
        const screenHeight = this.context?.pal?.resolve<number>('ScreenHeight') || 1080;
        
        const rawPixelX = normalizedX * screenWidth;
        const rawPixelY = normalizedY * screenHeight;

        // Buffer the raw input for getCoalescedEvents
        if (!this.coalescedBuffer.has(pointerId)) {
            this.coalescedBuffer.set(pointerId, []);
        }
        this.coalescedBuffer.get(pointerId)!.push({ x: rawPixelX, y: rawPixelY, time: performance.now() });

        // 3. Apply Kalman filtering (smoothing)
        const smoothed = filter.filter(rawPixelX, rawPixelY);
        
        // 4. Apply predictive lookahead (if configured)
        let finalX = smoothed.x;
        let finalY = smoothed.y;
        
        // Generate predicted events array
        const predictedEvents: { x: number, y: number, time: number }[] = [];
        if (this.config.lookaheadSteps > 0) {
            for (let i = 1; i <= this.config.lookaheadSteps; i++) {
                const predicted = filter.predict(i);
                predictedEvents.push({
                    x: Math.max(0, Math.min(screenWidth - 1, predicted.x)),
                    y: Math.max(0, Math.min(screenHeight - 1, predicted.y)),
                    time: performance.now() + (i * 16.67) // Approximate 60Hz frame time
                });
            }
            // The main event uses the first predicted step (or we could use the smoothed one and only expose predictions via getPredictedEvents)
            // For true W3C Level 3, the main event is the current smoothed state, and getPredictedEvents returns the future.
            // Let's keep the main event as the smoothed state to avoid rubber-banding the main cursor.
            finalX = smoothed.x;
            finalY = smoothed.y;
        }

        // 5. Clamp to screen bounds
        // screenWidth/Height is 1-past-end; valid pixel range is [0, W-1] × [0, H-1].
        // Clamping to W-1 / H-1 keeps coords inside the viewport so that
        // document.elementsFromPoint() never returns an empty stack for edge values.
        // Defensive NaN/Infinity guard: Math.max/min propagate NaN silently —
        // sanitize first so a single bad frame never freezes the pointer.
        if (!isFinite(finalX) || isNaN(finalX)) finalX = this.activePointers.get(pointerId)?.x ?? 0;
        if (!isFinite(finalY) || isNaN(finalY)) finalY = this.activePointers.get(pointerId)?.y ?? 0;
        finalX = Math.max(0, Math.min(screenWidth - 1, finalX));
        finalY = Math.max(0, Math.min(screenHeight - 1, finalY));

        // 6. Dispatch W3C Pointer Events
        this.dispatchEvents(pointerId, finalX, finalY, isPinching, predictedEvents);
    }

    /**
     * Coast a landmark when tracking is temporarily lost.
     * Uses the Kalman filter's prediction to continue the trajectory without a new measurement.
     */
    public coastLandmark(handId: number, isPinching: boolean) {
        const pointerId = this.POINTER_ID_BASE + handId;
        
        if (!this.filters.has(pointerId)) return;
        const filter = this.filters.get(pointerId)!;

        // Predict the next state without a measurement
        const predicted = filter.predict(1);
        // PAL-sourced dimensions (ATDD-ARCH-005)
        const screenWidth  = this.context?.pal?.resolve<number>('ScreenWidth')  ?? 1920;
        const screenHeight = this.context?.pal?.resolve<number>('ScreenHeight') ?? 1080;

        const finalX = Math.max(0, Math.min(screenWidth - 1, predicted.x));
        const finalY = Math.max(0, Math.min(screenHeight - 1, predicted.y));

        // Generate predicted events array for the coasting state
        const predictedEvents: { x: number, y: number, time: number }[] = [];
        if (this.config.lookaheadSteps > 0) {
            for (let i = 1; i <= this.config.lookaheadSteps; i++) {
                const future = filter.predict(i + 1);
                predictedEvents.push({
                    x: Math.max(0, Math.min(screenWidth - 1, future.x)),
                    y: Math.max(0, Math.min(screenHeight - 1, future.y)),
                    time: performance.now() + (i * 16.67)
                });
            }
        }

        this.dispatchEvents(pointerId, finalX, finalY, isPinching, predictedEvents);
    }

    /**
     * Handle the state machine of pointer events (down, move, up)
     */
    private dispatchEvents(pointerId: number, x: number, y: number, isPinching: boolean, predictedEvents: { x: number, y: number, time: number }[]) {
        const prevState = this.activePointers.get(pointerId) || { x, y, isDown: false };
        const stateChanged = prevState.isDown !== isPinching;
        
        // Always update the stored state
        this.activePointers.set(pointerId, { x, y, isDown: isPinching });

        // Determine which element is under the pointer
        const targetElement = this.elementFromPoint(x, y);
        if (!targetElement) return;

        // Get and clear the coalesced buffer
        const coalescedEvents = this.coalescedBuffer.get(pointerId) || [];
        this.coalescedBuffer.set(pointerId, []); // Clear buffer after dispatch

        // Dispatch the appropriate events
        if (stateChanged) {
            if (isPinching) {
                // Transition from hover to pinch -> pointerdown
                this.firePointerEvent('pointerdown', targetElement, pointerId, x, y, 1, coalescedEvents, predictedEvents); // button 1 = primary
            } else {
                // Transition from pinch to hover -> pointerup
                this.firePointerEvent('pointerup', targetElement, pointerId, x, y, 0, coalescedEvents, predictedEvents);
            }
        } else {
            // No state change -> pointermove
            // We fire move events whether pinching or just hovering
            this.firePointerEvent('pointermove', targetElement, pointerId, x, y, isPinching ? 1 : 0, coalescedEvents, predictedEvents);
        }
    }

    /**
     * Find the best target element at the given coordinates.
     *
     * Strategy — walk the full z-order stack returned by document.elementsFromPoint
     * (plural) and apply two priority passes:
     *
     *   Pass 1 — IFRAME  : If any iframe sits in the z-stack (even below opaque
     *            overlay divs at higher z-index), return it first.  This is the
     *            critical path for the tldraw same-origin injection: the SETTINGS
     *            layer div (z=30, pointer-events:auto) covers the tldraw iframe
     *            (z=20) but we want the gesture to pass through to tldraw.
     *
     *   Pass 2 — NON-NONE : First element whose computed pointer-events ≠ 'none'.
     *            Handles edge-cases where no iframe exists (e.g. native-DOM targets).
     *
     *   Fallback: return topmost element (stack[0]) so the caller always has a
     *            non-null target.
     *
     * Cross-origin note: we return the iframe *element itself* and never pierce
     * into its contentDocument — postMessage handles the cross-document boundary.
     */
    private elementFromPoint(x: number, y: number): IElement | null {
        const elementsFromPoint = this.context.pal.resolve<(x: number, y: number) => IElement[]>('ElementsFromPoint');
        if (!elementsFromPoint) return null;
        const stack = elementsFromPoint(x, y);
        if (stack.length === 0) return null;

        // Pass 1: prefer iframes — gesture input should reach tldraw even when
        // higher-z-index overlay panels sit on top.
        const iframeEl = stack.find((el: IElement) => el.tagName.toLowerCase() === 'iframe');
        if (iframeEl) return iframeEl;

        // Pass 2: first element that can receive pointer events
        const getComputedStyle = this.context.pal.resolve<(el: IElement) => { pointerEvents: string }>('GetComputedStyle');
        if (getComputedStyle) {
            const interactive = stack.find((el: IElement) => getComputedStyle(el).pointerEvents !== 'none');
            if (interactive) return interactive;
        }

        // Fallback: topmost element regardless of pointer-events
        return stack[0];
    }

    /**
     * Construct and dispatch a synthetic W3C PointerEvent
     */
    private firePointerEvent(
        type: string,
        target: IElement,
        pointerId: number,
        clientX: number,
        clientY: number,
        buttons: number,
        coalescedRaw: { x: number, y: number, time: number }[] = [],
        predictedRaw: { x: number, y: number, time: number }[] = []
    ) {
        const eventInit: IPointerEventInit = {
            pointerId: pointerId,
            pointerType: 'pen',   // 'pen' masquerades as Apple Pencil: zero touch-slop deadzone, sub-pixel precision
            isPrimary: true,
            clientX: clientX,
            clientY: clientY,
            screenX: clientX, // Simplified for now
            screenY: clientY,
            bubbles: true,
            cancelable: true,
            composed: true,
            buttons: buttons,
            button: buttons > 0 ? 0 : -1,
            pressure: buttons > 0 ? 0.5 : 0 // Arbitrary pressure when pinching
        };

        const PointerEventCtor = this.context.pal.resolve<new (type: string, init: IPointerEventInit) => IPointerEvent>('PointerEvent');
        if (!PointerEventCtor) return;
        const event = new PointerEventCtor(type, eventInit);

        // Create synthetic sub-events for coalesced and predicted arrays
        const createSubEvent = (raw: { x: number, y: number, time: number }) => {
            const subEvent = new PointerEventCtor(type, {
                ...eventInit,
                clientX: raw.x,
                clientY: raw.y,
                screenX: raw.x,
                screenY: raw.y
            });
            // timeStamp is read-only on the Event interface, so we can't set it in the constructor
            // We could use Object.defineProperty if we really needed to mock it, but for now we'll omit it
            return subEvent;
        };

        const coalescedEvents = coalescedRaw.map(createSubEvent);
        const predictedEvents = predictedRaw.map(createSubEvent);

        // Dynamically attach the Level 3 methods to the event instance
        // This ensures compatibility even if the browser's PointerEvent constructor
        // doesn't fully support injecting these arrays directly.
        (event as IPointerEvent & { getCoalescedEvents: () => IPointerEvent[] }).getCoalescedEvents = () => coalescedEvents;
        (event as IPointerEvent & { getPredictedEvents: () => IPointerEvent[] }).getPredictedEvents = () => predictedEvents;

        // If the target is an iframe, we must use postMessage to cross the security boundary
        if (this.config.dispatchToIframes && target.tagName.toLowerCase() === 'iframe') {
            const iframe = target as IElement;
            if (iframe.contentWindow) {
                const rect = iframe.getBoundingClientRect();
                const iframeX = clientX - rect.left;
                const iframeY = clientY - rect.top;

                const message = {
                    type: 'SYNTHETIC_POINTER_EVENT',
                    eventType: type,
                    eventInit: {
                        ...eventInit,
                        clientX: iframeX,
                        clientY: iframeY,
                        screenX: iframeX,
                        screenY: iframeY
                    }
                };
                iframe.contentWindow.postMessage(message, '*');
            }
        } else {
            target.dispatchEvent(event);
        }
    }
    
    /**
     * Clean up a pointer when a hand is lost
     */
    public removeHand(handId: number) {
        // Release Highlander lock so the next hand can acquire it
        if (handId === this.primaryHandId) this.primaryHandId = null;
        const pointerId = this.POINTER_ID_BASE + handId;
        const state = this.activePointers.get(pointerId);
        
        if (state) {
            // If it was down, fire a pointerup and pointercancel
            if (state.isDown) {
                const documentBody = this.context.pal.resolve<IElement>('DocumentBody');
                const target = this.elementFromPoint(state.x, state.y) || documentBody;
                if (!target) return;
                this.firePointerEvent('pointerup', target, pointerId, state.x, state.y, 0);
            }
            
            const documentBody = this.context.pal.resolve<IElement>('DocumentBody');
            const target = this.elementFromPoint(state.x, state.y) || documentBody;
            if (!target) return;
            this.firePointerEvent('pointercancel', target, pointerId, state.x, state.y, 0);
            
            this.activePointers.delete(pointerId);
        }
        
        this.filters.delete(pointerId);
        this.coalescedBuffer.delete(pointerId);
    }
}
