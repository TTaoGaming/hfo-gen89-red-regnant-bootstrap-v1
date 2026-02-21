/**
 * @file babylon_landmark_plugin.ts
 * @description Omega v13 — BabylonLandmarkPlugin (Exemplar B — Architectural Path)
 *
 * ──────────────────────────────────────────────────────────────────────────
 * WHAT THIS IS
 * ──────────────────────────────────────────────────────────────────────────
 * A drop-in Plugin that slots into the existing PluginSupervisor and renders
 * 21 Babylon.js spheres per detected hand on top of the camera feed.
 *
 * No Havok.  No physics engine.  Direct position updates at camera frame rate.
 * Canvas background is TRANSPARENT so the video layer shows through.
 *
 * Landmark 8 (index fingertip) colour-codes the FSM state:
 *   open_palm   → #1aff80  lime
 *   pointer_up  → #ff8800  orange
 *   closed_fist → #ff2222  red
 *   (all other landmarks) → #cccccc  white
 *
 * ──────────────────────────────────────────────────────────────────────────
 * INTEGRATION (demo_2026-02-20.ts / any bootstrap that builds the z-stack)
 * ──────────────────────────────────────────────────────────────────────────
 *
 *   // 1. Keep the existing BABYLON canvas at z=10 (already in layer_manager)
 *   const babylonCanvas = document.getElementById('omega-babylon-canvas') as HTMLCanvasElement;
 *
 *   // 2. Register INSTEAD OF (or alongside) BabylonPhysicsPlugin
 *   supervisor.registerPlugin(new BabylonLandmarkPlugin({ canvas: babylonCanvas }));
 *
 *   // 3. That's it.  The plugin auto-subscribes to FRAME_PROCESSED on start().
 *
 * ──────────────────────────────────────────────────────────────────────────
 * FRAME_PROCESSED payload shape (from demo_2026-02-20.ts)
 * ──────────────────────────────────────────────────────────────────────────
 *   Array<{
 *     handId:       number,
 *     gesture:      'open_palm' | 'pointer_up' | 'closed_fist',
 *     confidence:   number,
 *     x:            number,   // mirrored fingertip X (0..1)
 *     y:            number,   // fingertip Y (0..1)
 *     rawLandmarks: Array<{ x: number, y: number, z: number }>  // 21 items, already X-mirrored
 *   }>
 *
 * NOTE: rawLandmarks are already mirrored (X = 1 - original_x) in demo_2026-02-20.ts.
 *       This plugin uses them directly — no additional flip required.
 *
 * ──────────────────────────────────────────────────────────────────────────
 * BUILD
 * ──────────────────────────────────────────────────────────────────────────
 *   npx esbuild babylon_landmark_plugin.ts --bundle --outfile=dist/babylon_landmark_plugin.js \
 *     --format=esm --platform=browser --target=chrome120
 *
 *   Or bundle with demo_2026-02-20.ts by importing it there instead of babylon_physics.
 */

import {
    Engine,
    Scene,
    ArcRotateCamera,
    Camera,
    HemisphericLight,
    Vector3,
    MeshBuilder,
    StandardMaterial,
    Color3,
    Color4,
    Mesh,
} from '@babylonjs/core';

import type { Plugin, PluginContext } from './plugin_supervisor';
import type { RawHandData, LandmarkPoint } from './hand_types';

// ── Types ──────────────────────────────────────────────────────────────────
// LandmarkPoint and RawHandData are imported from hand_types.ts (single source of
// truth for frame payload shapes, ARCH-RULE: no circular deps).
// HandFrame local alias removed — align with RawHandData directly so the typed
// EventBus constraint (FRAME_PROCESSED: RawHandData[]) is satisfied at compile time.

// interface _RemovedHandFrame { // kept as tombstone comment only — see RawHandData
//     handId:       number;
//     gesture:      string;
//     confidence?:  number;
//     x?:           number;
//     y?:           number;
//     rawLandmarks?: LandmarkPoint[];
// }
// ─────────────────────────────────────────────────────────────────────────────

export interface BabylonLandmarkConfig {
    /** The canvas element to render into.  Must be positioned at z=10 over the video. */
    canvas: HTMLCanvasElement;
    /** World-size of a normal landmark dot (NDC units, default 0.012). */
    dotSize?: number;
    /** World-size of the fingertip dot, landmark 8 (default 0.024). */
    tipSize?: number;
    /** Landmark index to treat as the "state dot".  Default 8 (index fingertip). */
    stateLandmark?: number;
}

// ── State → Colour map ─────────────────────────────────────────────────────

const STATE_COLORS: Record<string, Color3> = {
    open_palm:   new Color3(0.10, 1.00, 0.50), // #1aff80 lime
    pointer_up:  new Color3(1.00, 0.53, 0.00), // #ff8800 orange
    closed_fist: new Color3(1.00, 0.13, 0.13), // #ff2222 red
};

const DEFAULT_COLOR = new Color3(0.80, 0.80, 0.80); // #cccccc white

// ── BabylonLandmarkPlugin ──────────────────────────────────────────────────

export class BabylonLandmarkPlugin implements Plugin {
    readonly name    = 'BabylonLandmarkPlugin';
    readonly version = '1.0.0';

    private engine!:  Engine;
    private scene!:   Scene;

    // handId → { meshes[21], materials[21] }
    private pools = new Map<number, { meshes: Mesh[]; mats: StandardMaterial[] }>();

    /** Bound once in constructor — identity is stable for unsubscribe (ARCH-ZOMBIE guard). */
    private readonly boundFrameHandler: (hands: RawHandData[]) => void;

    /** Plugin context injected by PluginSupervisor — never a global singleton. */
    private context!: PluginContext;

    private cfg: Required<BabylonLandmarkConfig>;

    constructor(config: BabylonLandmarkConfig) {
        this.cfg = {
            canvas:        config.canvas,
            dotSize:       config.dotSize       ?? 0.012,
            tipSize:       config.tipSize       ?? 0.024,
            stateLandmark: config.stateLandmark ?? 8,
        };
        // Bind once — same reference used for subscribe() AND unsubscribe() (ARCH-ZOMBIE guard).
        this.boundFrameHandler = (hands: RawHandData[]) => this.onFrame(hands);
    }

    // ── IPlugin lifecycle ──────────────────────────────────────────────────

    async init(context: PluginContext): Promise<void> {
        this.context = context;
        const { canvas } = this.cfg;

        // alpha:true so the engine respects our transparent clearColor
        this.engine = new Engine(canvas, true, { alpha: true });
        this.scene  = new Scene(this.engine);

        // Transparent background — the <video> layer below shows through
        this.scene.clearColor = new Color4(0, 0, 0, 0);

        // Orthographic camera: MediaPipe normalized coords (0→1, 0→1) → world space.
        // orthoTop=0, orthoBottom=1 so Y increases downward (matches MediaPipe convention).
        const cam        = new ArcRotateCamera('lm-cam', -Math.PI / 2, Math.PI / 2, 10,
                                               Vector3.Zero(), this.scene);
        cam.mode         = Camera.ORTHOGRAPHIC_CAMERA;
        cam.orthoLeft    = 0;
        cam.orthoRight   = 1;
        cam.orthoTop     = 0; // Y=0 at top of screen
        cam.orthoBottom  = 1;
        cam.position     = new Vector3(0.5, 0.5, -10);
        cam.setTarget(Vector3.Zero());

        // Ambient light — emissive spheres still need a light source to render
        const light       = new HemisphericLight('lm-light', new Vector3(0, 1, 0), this.scene);
        light.intensity   = 1.4;

        this.engine.runRenderLoop(() => this.scene.render());
        // window.addEventListener('resize', () => this.engine.resize());

        console.log('[BabylonLandmarkPlugin] Initialized (transparent canvas, orthographic, no physics).');
    }

    async start(): Promise<void> {
        // ATDD-ARCH-001: subscribe via injected context.eventBus, never a global singleton
        // boundFrameHandler was fixed in constructor — same identity every time (ARCH-ZOMBIE guard)
        this.context.eventBus.subscribe('FRAME_PROCESSED', this.boundFrameHandler);
        console.log('[BabylonLandmarkPlugin] Subscribed to FRAME_PROCESSED.');
    }

    async stop(): Promise<void> {
        // ATDD-ARCH-001: use injected bus, never globalEventBus
        this.context.eventBus.unsubscribe('FRAME_PROCESSED', this.boundFrameHandler);
        this.hideAll();
    }

    async destroy(): Promise<void> {
        // ATDD-ARCH-001: use injected bus, never globalEventBus
        this.context.eventBus.unsubscribe('FRAME_PROCESSED', this.boundFrameHandler);
        this.engine.dispose();
        this.pools.clear();
    }

    // ── Frame handler ──────────────────────────────────────────────────────

    private onFrame(hands: RawHandData[]): void {
        // Hide everything first — only re-show what's actively detected this frame
        this.hideAll();

        for (const hand of hands) {
            if (!hand.rawLandmarks || hand.rawLandmarks.length < 21) continue;

            const pool     = this.getOrCreate(hand.handId);
            const tipColor = STATE_COLORS[hand.gesture] ?? DEFAULT_COLOR;

            for (let i = 0; i < 21; i++) {
                const pt = hand.rawLandmarks[i];

                // rawLandmarks have already been X-mirrored in demo_2026-02-20.ts
                // (x = 1 - original_x) to match the CSS scaleX(-1) video.
                pool.meshes[i].position.set(pt.x, pt.y, 0);
                pool.meshes[i].isVisible = true;

                const col = (i === this.cfg.stateLandmark) ? tipColor : DEFAULT_COLOR;
                pool.mats[i].diffuseColor.copyFrom(col);
                pool.mats[i].emissiveColor.copyFrom(col);
            }
        }
    }

    private hideAll(): void {
        for (const { meshes } of this.pools.values())
            for (const m of meshes) m.isVisible = false;
    }

    // ── Sphere pool ────────────────────────────────────────────────────────

    private getOrCreate(handId: number) {
        if (this.pools.has(handId)) return this.pools.get(handId)!;

        const meshes: Mesh[]              = [];
        const mats:   StandardMaterial[]  = [];

        for (let i = 0; i < 21; i++) {
            const isState = (i === this.cfg.stateLandmark);
            const size    = isState ? this.cfg.tipSize : this.cfg.dotSize;

            const mesh = MeshBuilder.CreateSphere(
                `h${handId}_lm${i}`,
                { diameter: size, segments: 4 }, // segments=4 → low-poly for perf
                this.scene);

            const mat   = new StandardMaterial(`h${handId}_mat${i}`, this.scene);
            mat.diffuseColor  = DEFAULT_COLOR.clone();
            mat.emissiveColor = DEFAULT_COLOR.clone(); // self-lit — pops over the video
            mat.specularColor = Color3.Black();

            mesh.material   = mat;
            mesh.isPickable = false;
            mesh.isVisible  = false;

            meshes.push(mesh);
            mats.push(mat);
        }

        const pool = { meshes, mats };
        this.pools.set(handId, pool);
        return pool;
    }
}
