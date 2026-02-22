/**
 * @file babylon_physics.ts
 * @description Omega v13 Microkernel Plugin: Babylon.js + Havok Physics Engine
 *
 * Implements the full Plugin interface so it can be registered with PluginSupervisor
 * like any other plugin.  Havok is loaded asynchronously in start() via dynamic
 * import — no synchronous constructor side-effects.
 *
 * GHERKIN SBE SPECS:
 *
 * Feature: Babylon.js Physics Engine with Velocnertia Clamping
 *
 *   Scenario: Plugin lifecycle
 *     Given BabylonPhysicsPlugin is registered with PluginSupervisor
 *     When supervisor.initAll() runs
 *     Then the plugin subscribes to FRAME_PROCESSED on context.eventBus
 *     When supervisor.startAll() runs
 *     Then Havok is loaded async and the Babylon engine starts rendering
 *
 *   Scenario: Handle N Hands (via FRAME_PROCESSED bus event)
 *     Given the plugin is running
 *     When FRAME_PROCESSED fires with RawHandData[] containing rawLandmarks
 *     Then it ensures N hand instances exist, each with 21 Havok physics spheres
 *     And it publishes BABYLON_PHYSICS_FRAME telemetry on the bus
 *
 *   Scenario: Velocnertia Clamping
 *     Given a hand landmark has a target position from the gesture payload
 *     When the physics step updates
 *     Then the sphere's linear velocity is set towards the target but clamped to maxVelocity
 *     And the sphere's position is NOT directly set (no teleportation)
 */

import {
    Engine,
    Scene,
    Vector3,
    MeshBuilder,
    StandardMaterial,
    Color3,
    HavokPlugin,
    PhysicsAggregate,
    PhysicsShapeType,
    HemisphericLight,
    ArcRotateCamera,
    Camera,
    Mesh,
} from '@babylonjs/core';

import type { Plugin, PluginContext } from './plugin_supervisor';
import type { RawHandData } from './hand_types';

// ── Config ───────────────────────────────────────────────────────────────────

export interface BabylonPhysicsConfig {
    /** The canvas element to render into.  Must already be in the DOM. */
    canvas: HTMLCanvasElement;
    /** Velocnertia velocity ceiling (default: 50 units/s) */
    maxVelocity?: number;
    /** Spring stiffness towards target position (default: 15) */
    springConstant?: number;
    /** Scale factor: normalised [0,1] → Babylon world units (default: 10) */
    worldScale?: number;
}

// ── Plugin ───────────────────────────────────────────────────────────────────

export class BabylonPhysicsPlugin implements Plugin {
    // ── Plugin identity ───────────────────────────────────────────────────────
    public readonly name    = 'BabylonPhysicsPlugin';
    public readonly version = '2.0.0';

    // ── Injected context ──────────────────────────────────────────────────────
    private context!: PluginContext;

    // ── Config (resolved in constructor) ──────────────────────────────────────
    private readonly canvas:         HTMLCanvasElement;
    private readonly maxVelocity:    number;
    private readonly springConstant: number;
    private readonly worldScale:     number;

    // ── Runtime state (created lazily in start()) ─────────────────────────────
    private engine:  Engine | null = null;
    private scene:   Scene  | null = null;
    private running  = false;

    // ── Hand tracking state ───────────────────────────────────────────────────
    /** Map of handId → array of 21 Babylon.js Mesh spheres */
    private handInstances: Map<number, Mesh[]>     = new Map();
    /** Map of handId → array of 21 target Vector3 positions for velocnertia */
    private latestTargets: Map<number, Vector3[]>  = new Map();

    // ── Stable bound callback reference (ARCH-ZOMBIE compliance) ─────────────
    private readonly boundOnFrameProcessed: (data: RawHandData[]) => void;
    private readonly boundOnResize:         () => void;

    // ── Telemetry counters ────────────────────────────────────────────────────
    private physicsFrameCount = 0;

    constructor(config: BabylonPhysicsConfig) {
        this.canvas         = config.canvas;
        this.maxVelocity    = config.maxVelocity    ?? 50.0;
        this.springConstant = config.springConstant ?? 15.0;
        this.worldScale     = config.worldScale     ?? 10.0;

        // Bind once — stable references required for unsubscribe() (ARCH-ZOMBIE)
        this.boundOnFrameProcessed = this.onFrameProcessed.bind(this);
        this.boundOnResize         = () => {
            this.engine?.resize();
            if (this.scene && this.scene.activeCamera && this.scene.activeCamera.mode === Camera.ORTHOGRAPHIC_CAMERA) {
                  const ratio = (this.canvas as unknown as { width: number, height: number }).width / (this.canvas as unknown as { width: number, height: number }).height;
                this.scene.activeCamera.orthoLeft = -this.worldScale / 2 * ratio;
                this.scene.activeCamera.orthoRight = this.worldScale / 2 * ratio;
            }
        };
    }

    // ── Plugin lifecycle ──────────────────────────────────────────────────────

    /**
     * init() — called synchronously by PluginSupervisor.initAll().
     * Saves context and wires bus subscription.  No Babylon / Havok work here.
     */
    public init(context: PluginContext): void {
        this.context = context;
        context.eventBus.subscribe('FRAME_PROCESSED', this.boundOnFrameProcessed);
        console.log('[BabylonPhysicsPlugin] init — subscribed to FRAME_PROCESSED');
    }

    /**
     * start() — async, called by PluginSupervisor.startAll().
     * Dynamically imports @babylonjs/havok (WASM), builds the scene, starts the
     * render loop.  Idempotent — safe to call multiple times.
     */
    public async start(): Promise<void> {
        if (this.running) return;

        try {
            console.log('[BabylonPhysicsPlugin] Loading Havok WASM…');
            // Dynamic import keeps the WASM out of the synchronous bundle.
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const HavokPhysics = ((await import('@babylonjs/havok')) as any).default as () => Promise<unknown>;
            const havok = await HavokPhysics();
            console.log('[BabylonPhysicsPlugin] Havok loaded ✓');

            this.engine = new Engine(this.canvas, true, { preserveDrawingBuffer: true });
            this.scene  = new Scene(this.engine);

            // Enable Havok physics
            const hkPlugin = new HavokPlugin(true, havok);
            this.scene.enablePhysics(new Vector3(0, -9.81, 0), hkPlugin);

            this.setupBasicScene();

            // Velocnertia runs immediately before each physics step
            this.scene.onBeforePhysicsObservable.add(() => this.applyVelocnertiaClamp());

            // Render loop
            this.engine.runRenderLoop(() => {
                if (this.scene) this.scene.render();
            });

            // window.addEventListener('resize', this.boundOnResize);
            this.running = true;
            console.log('[BabylonPhysicsPlugin] Havok physics engine running ✓');
        } catch (err) {
            console.error('[BabylonPhysicsPlugin] Failed to start Havok engine:', err);
            throw err;
        }
    }

    public stop(): void {
        this.running = false;
        this.engine?.stopRenderLoop();
    }

    public destroy(): void {
        this.stop();
        this.context?.eventBus.unsubscribe('FRAME_PROCESSED', this.boundOnFrameProcessed);
        // window.removeEventListener('resize', this.boundOnResize);

        // Dispose all hand instances
        for (const handId of [...this.handInstances.keys()]) {
            this.destroyHandInstance(handId);
        }

        this.scene?.dispose();
        this.engine?.dispose();
        this.scene  = null;
        this.engine = null;
        console.log('[BabylonPhysicsPlugin] destroyed');
    }

    // ── FRAME_PROCESSED handler ───────────────────────────────────────────────

    /**
     * Receives RawHandData[] from the bus (emitted by MediaPipeVisionPlugin).
     * Updates target positions for 21 Havok physics spheres per hand.
     * Publishes BABYLON_PHYSICS_FRAME telemetry for the golden master test.
     */
    private onFrameProcessed(hands: RawHandData[]): void {
        if (!this.running || !this.scene) return;

        const visibleHandIds = new Set<number>();

        for (const hand of hands) {
            visibleHandIds.add(hand.handId);

            if (!this.handInstances.has(hand.handId)) {
                this.createHandInstance(hand.handId);
            }

            // COORD_INVARIANT — WYSIWYG parity with display (SEE mediapipe_vision_plugin.ts COORD_INVARIANT v1):
            // rawLandmarks[i].x = 1 - raw_x (mirrored once, by classifyHand — DO NOT re-apply 1-x here).
            // Orthographic camera: orthoLeft=-worldScale/2*ratio, orthoRight=+worldScale/2*ratio,
            //                      orthoTop=+worldScale/2,        orthoBottom=-worldScale/2
            // WYSIWYG mapping:
            //   WorldX = (lm.x - 0.5) * worldScale * ratio  → lm.x=0→orthoLeft, lm.x=1→orthoRight ✓
            //   WorldY = -(lm.y - 0.5) * worldScale         → lm.y=0→orthoTop,  lm.y=1→orthoBottom ✓
            if (hand.rawLandmarks && hand.rawLandmarks.length === 21) {
                  const ratio = (this.canvas as unknown as { width: number, height: number }).width / (this.canvas as unknown as { width: number, height: number }).height;
                const targets = hand.rawLandmarks.map(lm =>
                    new Vector3(
                        (lm.x - 0.5) * this.worldScale * ratio,  // lm.x already mirrored, scale by aspect ratio
                        // Y: invert so 0 is top and 1 is bottom
                        -(lm.y - 0.5) * this.worldScale,
                        -lm.z * this.worldScale,
                    )
                );
                this.latestTargets.set(hand.handId, targets);
            }
        }

        // Remove physics instances for hands no longer in the frame
        for (const handId of [...this.handInstances.keys()]) {
            if (!visibleHandIds.has(handId)) {
                this.destroyHandInstance(handId);
            }
        }

        // ── Telemetry: publish for golden master test assertions ──────────────
        this.physicsFrameCount++;
        this.context.eventBus.publish('BABYLON_PHYSICS_FRAME', {
            frameIndex:  this.physicsFrameCount,
            handCount:   hands.length,
            handIds:     [...visibleHandIds],
            sphereCount: this.handInstances.size * 21,
        });
    }

    // ── Scene helpers ─────────────────────────────────────────────────────────

    private setupBasicScene(): void {
        if (!this.scene) return;

        // Orthographic camera matching the [0, 1] coordinate space
          const ratio = (this.canvas as unknown as { width: number, height: number }).width / (this.canvas as unknown as { width: number, height: number }).height;
        const camera = new ArcRotateCamera(
            'camera', -Math.PI / 2, Math.PI / 2, 15, Vector3.Zero(), this.scene,
        );
        camera.mode = Camera.ORTHOGRAPHIC_CAMERA;
        camera.orthoLeft = -this.worldScale / 2 * ratio;
        camera.orthoRight = this.worldScale / 2 * ratio;
        camera.orthoTop = this.worldScale / 2;
        camera.orthoBottom = -this.worldScale / 2;
        camera.attachControl(this.engine!.getRenderingCanvas(), true);

        // Hemispheric fill light
        const light = new HemisphericLight('light', new Vector3(0, 1, 0), this.scene);
        light.intensity = 0.7;

        // Remove ground plane so it doesn't block the hands
        // const ground = MeshBuilder.CreateGround('ground', { width: 20, height: 20 }, this.scene);
        // new PhysicsAggregate(ground, PhysicsShapeType.BOX, { mass: 0, restitution: 0.5 }, this.scene);
    }

    private createHandInstance(handId: number): void {
        if (!this.scene) return;

        const spheres: Mesh[] = [];
        const material = new StandardMaterial(`handMat_${handId}`, this.scene);
        material.diffuseColor = new Color3(Math.random(), Math.random(), Math.random());

        for (let i = 0; i < 21; i++) {
            const sphere = MeshBuilder.CreateSphere(
                `hand_${handId}_lm_${i}`, { diameter: 0.4 }, this.scene,
            );
            sphere.material = material;

            // Dynamic body (mass:1) so spheres push scene objects — velocity-driven
            const aggregate = new PhysicsAggregate(
                sphere, PhysicsShapeType.SPHERE,
                { mass: 1, restitution: 0.5, friction: 0.5 }, this.scene,
            );
            // Zero gravity on landmarks — they track the hand, not physics gravity
            aggregate.body.disablePreStep = false;
            aggregate.body.setGravityFactor(0);

            spheres.push(sphere);
        }

        this.handInstances.set(handId, spheres);
        console.log(`[BabylonPhysicsPlugin] Created 21 Havok spheres for hand ${handId}`);
    }

    private destroyHandInstance(handId: number): void {
        const spheres = this.handInstances.get(handId);
        if (spheres) {
            for (const sphere of spheres) {
                sphere.physicsBody?.dispose();
                sphere.dispose();
            }
            this.handInstances.delete(handId);
            this.latestTargets.delete(handId);
            console.log(`[BabylonPhysicsPlugin] Disposed hand ${handId}`);
        }
    }

    // ── Velocnertia Clamp ─────────────────────────────────────────────────────

    /**
     * Runs before each Havok physics tick (scene.onBeforePhysicsObservable).
     * Sets each sphere's linear velocity toward its target, clamped to maxVelocity.
     * This drives the spheres without teleportation, enabling physical collisions.
     */
    private applyVelocnertiaClamp(): void {
        for (const [handId, targets] of this.latestTargets.entries()) {
            const spheres = this.handInstances.get(handId);
            if (!spheres) continue;

            for (let i = 0; i < 21; i++) {
                const sphere = spheres[i];
                const target = targets[i];
                const body   = sphere.physicsBody;
                if (!body) continue;

                const diff = target.subtract(sphere.position);
                let vel    = diff.scale(this.springConstant);

                if (vel.length() > this.maxVelocity) {
                    vel = vel.normalize().scale(this.maxVelocity);
                }

                body.setLinearVelocity(vel);
                body.setAngularVelocity(Vector3.Zero());
            }
        }
    }
}
