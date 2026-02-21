/**
 * @file layer_manager.ts
 * @description Omega v13 — Layer Compositor
 *
 * Owns the complete z-stack. Every visual surface (video, babylon, tldraw,
 * settings, viz) is registered here so opacity, z-index and pointer-event
 * routing can be changed at runtime from the Config Mosaic.
 *
 * Z-STACK CONTRACT (do not change order without updating event bus layer IDs):
 *
 *   z=0   VIDEO_BG     — live camera, full-viewport backdrop
 *   z=10  BABYLON      — Babylon.js canvas, physics dots + state halos
 *   z=20  TLDRAW       — tldraw iframe, WYSIWYG whiteboard
 *   z=30  SETTINGS     — Config Mosaic panel (human-operated)
 *   z=40  VIZ          — hand skeleton / dot-ring overlay (pointer-events:none)
 *
 * WYSIWYG invariant:
 *   The index fingertip's (mappedX, mappedY) in [0,1] normalised screen space
 *   maps 1-to-1 to CSS pixels in every layer.  W3CPointerFabric dispatches a
 *   real PointerEvent to document.elementFromPoint(screenX, screenY).  tldraw
 *   at z=20 is hit as long as nothing with pointer-events:auto sits above it
 *   at that coordinate.  The viz layer at z=40 is always pointer-events:none
 *   so it is invisible to elementFromPoint.
 */
// @ts-nocheck


import { EventBus } from './event_bus';

// ─── Layer identifiers ───────────────────────────────────────────────────────

export const LAYER = {
    VIDEO_BG: 'VIDEO_BG',
    BABYLON:  'BABYLON',
    TLDRAW:   'TLDRAW',
    SETTINGS: 'SETTINGS',
    VIZ:      'VIZ',
} as const;

export type LayerId = typeof LAYER[keyof typeof LAYER];

// ─── Types ───────────────────────────────────────────────────────────────────

export interface LayerDescriptor {
    id: LayerId;
    zIndex: number;
    opacity: number;
    /** 'none' = invisible to pointer hit-testing; 'auto' = normal */
    pointerEvents: 'none' | 'auto';
    element: HTMLElement | HTMLCanvasElement | HTMLIFrameElement | HTMLVideoElement | null;
    label: string;
}

// ─── LayerManager ────────────────────────────────────────────────────────────

export class LayerManager {
    private layers = new Map<LayerId, LayerDescriptor>();
    /** Injected by PluginSupervisor or bootstrapper — never a global singleton. */
    private eventBus: EventBus | null;

    // Scenario: Given LayerManager constructed with an EventBus
    //           When setOpacity() is called
    //           Then LAYER_OPACITY_CHANGE is published on the injected bus (not a global)
    constructor(eventBus?: EventBus) {
        this.eventBus = eventBus ?? null;
        // Seed defaults — elements are null until registerElement() is called
        const defaults: Omit<LayerDescriptor, 'element'>[] = [
            { id: LAYER.VIDEO_BG, zIndex: 0,  opacity: 1.0, pointerEvents: 'none', label: 'Video Background' },
            { id: LAYER.BABYLON,  zIndex: 10, opacity: 0.7, pointerEvents: 'none', label: 'Babylon Physics' },
            { id: LAYER.TLDRAW,   zIndex: 20, opacity: 0.8, pointerEvents: 'auto', label: 'tldraw Canvas' },
            { id: LAYER.SETTINGS, zIndex: 30, opacity: 1.0, pointerEvents: 'none', label: 'Settings Panel' }, // LIE2 FIX: starts 'none'; Shell.toggleSettings() sets 'auto' on open
            { id: LAYER.VIZ,      zIndex: 40, opacity: 1.0, pointerEvents: 'none', label: 'Hand Viz Overlay' },
        ];
        for (const d of defaults) {
            this.layers.set(d.id, { ...d, element: null });
        }
    }

    /**
     * Attach (or replace) the DOM element for a layer and apply its styles.
     */
    public registerElement(id: LayerId, el: HTMLElement): void {
        const desc = this.layers.get(id);
        if (!desc) throw new Error(`LayerManager: unknown layer id "${id}"`);
        desc.element = el;
        this.applyStyles(desc);
        document.body.appendChild(el);
    }

    /** Change opacity [0–1] at runtime. Publishes LAYER_OPACITY_CHANGE. */
    public setOpacity(id: LayerId, opacity: number): void {
        const desc = this.layers.get(id);
        if (!desc) return;
        desc.opacity = Math.max(0, Math.min(1, opacity));
        if (desc.element) desc.element.style.opacity = String(desc.opacity);
        this.eventBus?.publish('LAYER_OPACITY_CHANGE', { id, opacity: desc.opacity });
    }

    /** Toggle pointer-event passthrough at runtime. */
    public setPointerEvents(id: LayerId, mode: 'none' | 'auto'): void {
        const desc = this.layers.get(id);
        if (!desc) return;
        desc.pointerEvents = mode;
        if (desc.element) desc.element.style.pointerEvents = mode;
    }

    public getDescriptor(id: LayerId): LayerDescriptor | undefined {
        return this.layers.get(id);
    }

    /** Sorted ascending by zIndex. */
    public allLayers(): LayerDescriptor[] {
        return [...this.layers.values()].sort((a, b) => a.zIndex - b.zIndex);
    }

    // ── Private ──────────────────────────────────────────────────────────────

    private applyStyles(desc: LayerDescriptor): void {
        const el = desc.element;
        if (!el) return;

        // Full-viewport fixed positioning for every layer
        el.style.position   = 'fixed';
        el.style.top        = '0';
        el.style.left       = '0';
        el.style.width      = '100vw';
        el.style.height     = '100vh';
        el.style.margin     = '0';
        el.style.padding    = '0';
        el.style.border     = 'none';
        el.style.zIndex     = String(desc.zIndex);
        el.style.opacity    = String(desc.opacity);
        el.style.pointerEvents = desc.pointerEvents;

        // Video-specific: object-fit cover + mirror
        if (el.tagName === 'VIDEO') {
            (el as HTMLVideoElement).style.objectFit = 'cover';
            el.style.transform = 'scaleX(-1)';
        }

        // Canvas-specific: transparent background
        if (el.tagName === 'CANVAS') {
            (el as HTMLCanvasElement).style.background = 'transparent';
        }

        // iframe-specific: no background
        if (el.tagName === 'IFRAME') {
            (el as HTMLIFrameElement).style.background = 'transparent';
            (el as HTMLIFrameElement).allowFullscreen = true;
        }
    }
}

// ── ATDD-ARCH-001 compliance ────────────────────────────────────────────────
// globalLayerManager singleton DELETED. Create LayerManager(bus) in the
// bootstrapper and pass it through ShellCallbacks / CompositorPlugin context.
//
// Scenario: Given globalLayerManager export removed
//           When the bootstrapper runs
//           Then LayerManager is created with the supervisor's EventBus
//                and passed to Shell via ShellCallbacks.layerManager
