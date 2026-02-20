/**
 * @file babylon_physics.ts
 * @description Omega v13 Microkernel Plugin: Babylon.js + Havok Physics Engine
 * 
 * GHERKIN SBE SPECS:
 * 
 * Feature: Babylon.js Physics Engine with Velocnertia Clamping
 * 
 *   Scenario: Initialize Physics Engine
 *     Given the BabylonPhysicsPlugin is instantiated with a canvas and Havok instance
 *     When the plugin initializes
 *     Then it creates a Babylon engine, scene, and Havok physics plugin
 * 
 *   Scenario: Handle N Hands
 *     Given the plugin receives a GestureEventPayload with N hands
 *     When the payload is processed
 *     Then it ensures N hand instances exist in the scene, each with 21 physics spheres
 * 
 *   Scenario: Velocnertia Clamping
 *     Given a hand landmark has a target position from the gesture payload
 *     And the corresponding physics sphere has a current position
 *     When the physics step updates
 *     Then the sphere's linear velocity is set towards the target but clamped to a maximum magnitude (velocnertia clamp)
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
    Mesh
} from "@babylonjs/core";

// We import the types from the gesture plugin to maintain the contract
import type { GestureEventPayload, HandState } from "./mediapipe_gesture";

export interface BabylonPhysicsConfig {
    canvas: HTMLCanvasElement;
    havokInstance: any; // The initialized Havok instance (await HavokPhysics())
    maxVelocity?: number; // The "velocnertia" clamp limit (default: 50)
    springConstant?: number; // How fast it tries to reach the target (default: 15)
    worldScale?: number; // Scale factor from normalized [0,1] to physics world (default: 10)
}

export class BabylonPhysicsPlugin {
    private engine: Engine;
    private scene: Scene;
    private hkPlugin: HavokPlugin;
    
    private maxVelocity: number;
    private springConstant: number;
    private worldScale: number;

    // Map of handId to an array of 21 physics spheres
    private handInstances: Map<number, Mesh[]> = new Map();
    
    // Store the latest target positions for the physics step to consume
    private latestTargets: Map<number, Vector3[]> = new Map();

    constructor(config: BabylonPhysicsConfig) {
        this.maxVelocity = config.maxVelocity ?? 50.0;
        this.springConstant = config.springConstant ?? 15.0;
        this.worldScale = config.worldScale ?? 10.0;

        this.engine = new Engine(config.canvas, true);
        this.scene = new Scene(this.engine);
        
        // Initialize Havok
        this.hkPlugin = new HavokPlugin(true, config.havokInstance);
        this.scene.enablePhysics(new Vector3(0, -9.81, 0), this.hkPlugin);

        this.setupBasicScene();

        // Register the physics update loop (runs before the physics engine steps)
        this.scene.onBeforePhysicsObservable.add(() => {
            this.applyVelocnertiaClamp();
        });

        this.engine.runRenderLoop(() => {
            this.scene.render();
        });

        // Handle window resize
        window.addEventListener("resize", () => {
            this.engine.resize();
        });
    }

    private setupBasicScene() {
        // Basic camera
        const camera = new ArcRotateCamera("camera", -Math.PI / 2, Math.PI / 2.5, 15, Vector3.Zero(), this.scene);
        camera.attachControl(this.engine.getRenderingCanvas(), true);

        // Basic light
        const light = new HemisphericLight("light", new Vector3(0, 1, 0), this.scene);
        light.intensity = 0.7;

        // Ground plane for things to bounce on
        const ground = MeshBuilder.CreateGround("ground", { width: 20, height: 20 }, this.scene);
        new PhysicsAggregate(ground, PhysicsShapeType.BOX, { mass: 0, restitution: 0.5 }, this.scene);
    }

    /**
     * Consumes the raw, noisy gesture payload from the MediaPipe plugin.
     * Updates the target positions for the physics spheres.
     */
    public consumeGesturePayload(payload: GestureEventPayload) {
        // Track which hands are currently visible
        const visibleHandIds = new Set<number>();

        for (const hand of payload.hands) {
            visibleHandIds.add(hand.id);
            
            // Ensure the hand instance exists
            if (!this.handInstances.has(hand.id)) {
                this.createHandInstance(hand.id);
            }

            // Convert normalized coordinates to world coordinates
            const targets = hand.rawLandmarks.map(lm => {
                // MediaPipe coordinates: x is [0,1] left-to-right, y is [0,1] top-to-bottom, z is depth
                // Babylon coordinates: x is right, y is up, z is forward
                // We center it by subtracting 0.5
                return new Vector3(
                    (lm.x - 0.5) * this.worldScale,
                    -(lm.y - 0.5) * this.worldScale + (this.worldScale / 2), // Offset Y so it's above ground
                    -lm.z * this.worldScale
                );
            });

            this.latestTargets.set(hand.id, targets);
        }

        // Cleanup hands that are no longer visible
        for (const [handId, meshes] of this.handInstances.entries()) {
            if (!visibleHandIds.has(handId)) {
                this.destroyHandInstance(handId);
            }
        }
    }

    private createHandInstance(handId: number) {
        const spheres: Mesh[] = [];
        const material = new StandardMaterial(`handMat_${handId}`, this.scene);
        // Assign a random color per hand for visual debugging
        material.diffuseColor = new Color3(Math.random(), Math.random(), Math.random());

        for (let i = 0; i < 21; i++) {
            const sphere = MeshBuilder.CreateSphere(`hand_${handId}_lm_${i}`, { diameter: 0.4 }, this.scene);
            sphere.material = material;
            
            // Create a kinematic physics aggregate (mass: 1, but we control velocity)
            // We use a dynamic body so it can push other objects, but we override its velocity
            const aggregate = new PhysicsAggregate(sphere, PhysicsShapeType.SPHERE, { mass: 1, restitution: 0.5, friction: 0.5 }, this.scene);
            
            // Disable gravity for the hand landmarks so they don't fall when tracking is lost
            aggregate.body.disablePreStep = false;
            aggregate.body.setGravityFactor(0);

            spheres.push(sphere);
        }

        this.handInstances.set(handId, spheres);
    }

    private destroyHandInstance(handId: number) {
        const spheres = this.handInstances.get(handId);
        if (spheres) {
            for (const sphere of spheres) {
                sphere.physicsBody?.dispose();
                sphere.dispose();
            }
            this.handInstances.delete(handId);
            this.latestTargets.delete(handId);
        }
    }

    /**
     * The core "Velocnertia Clamp" logic.
     * Runs before every physics step.
     * Calculates the velocity needed to reach the target, clamps it, and applies it.
     * This prevents teleportation and allows the hands to interact physically with the world.
     */
    private applyVelocnertiaClamp() {
        for (const [handId, targets] of this.latestTargets.entries()) {
            const spheres = this.handInstances.get(handId);
            if (!spheres) continue;

            for (let i = 0; i < 21; i++) {
                const sphere = spheres[i];
                const target = targets[i];
                const body = sphere.physicsBody;

                if (!body) continue;

                // Calculate vector from current position to target
                const currentPos = sphere.position;
                const diff = target.subtract(currentPos);

                // Calculate desired velocity (spring-like behavior)
                let desiredVelocity = diff.scale(this.springConstant);

                // Velocnertia Clamp: Limit the maximum velocity
                if (desiredVelocity.length() > this.maxVelocity) {
                    desiredVelocity = desiredVelocity.normalize().scale(this.maxVelocity);
                }

                // Apply the clamped velocity
                body.setLinearVelocity(desiredVelocity);
                
                // Dampen angular velocity so they don't spin wildly
                body.setAngularVelocity(Vector3.Zero());
            }
        }
    }

    public dispose() {
        this.scene.dispose();
        this.engine.dispose();
    }
}
