/**
 * @file hand_types.ts
 * @description Shared hand-tracking payload types.
 *
 * ARCH-RULE: This file has ZERO infrastructure imports (no event_bus, no
 * plugin_supervisor, no schemas).  It is safe to import from ANY layer of the
 * system without introducing circular dependencies.
 *
 * Placement here rather than in gesture_bridge.ts breaks the import cycle:
 *   gesture_bridge.ts → event_bus.ts → (needs RawHandData) → gesture_bridge.ts  ← CYCLE
 * With this file:
 *   event_bus.ts      → hand_types.ts  ✓
 *   gesture_bridge.ts → hand_types.ts  ✓  (re-exports for backward compat)
 */

import { RawCoord } from './types.js';

// ── Landmark geometry ────────────────────────────────────────────────────────

/** Single (x, y, z) MediaPipe landmark in normalised viewport space. */
export interface LandmarkPoint {
    /** Normalised X, already X-mirrored where relevant. */
    x: RawCoord;
    /** Normalised Y. */
    y: RawCoord;
    /** Normalised Z (depth); 0 = wrist plane, negative = closer to camera. */
    z: RawCoord;
}

// ── Per-hand frame data ───────────────────────────────────────────────────────

/**
 * One hand's state as emitted by MediaPipeVisionPlugin on FRAME_PROCESSED.
 * This is the only payload type that should transit the FRAME_PROCESSED event.
 *
 * ARCH-RULE: Downstream consumers (GestureFSM, BabylonLandmark, etc.) must
 * accept this exact shape — do NOT add plugin-specific fields here.  Use the
 * extension fields `rawLandmarks` and `frameTimeMs` for auxiliary data.
 */
export interface RawHandData {
    /** Numeric hand identity assigned by MediaPipe (0…N-1). */
    handId: number;
    /** Index-fingertip X in normalised viewport space (0.0–1.0). */
    x: RawCoord;
    /** Index-fingertip Y in normalised viewport space (0.0–1.0). */
    y: RawCoord;
    /** Gesture classification string, e.g. 'open_palm' | 'pointer_up' | 'closed_fist'. */
    gesture: string;
    /** MediaPipe confidence score (0.0–1.0). */
    confidence: number;
    /** All 21 MediaPipe hand landmarks in normalised space (already X-mirrored). */
    rawLandmarks?: LandmarkPoint[];
    /**
     * Wall-clock capture timestamp in ms (performance.now()).
     * When provided, FSMs use this for frame-rate-independent dwell calculations.
     * Falls back to performance.now() at dispatch time when absent.
     */
    frameTimeMs?: number;
}
