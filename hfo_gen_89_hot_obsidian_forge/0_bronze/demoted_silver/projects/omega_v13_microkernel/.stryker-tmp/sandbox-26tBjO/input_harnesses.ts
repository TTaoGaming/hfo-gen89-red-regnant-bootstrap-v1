/**
 * @file input_harnesses.ts
 * @description Omega v13 Microkernel Plugin: Input Harnesses (VideoClip & JSON)
 * 
 * GHERKIN SBE SPECS:
 * 
 * Feature: Agnostic Input Harnesses
 * 
 *   Scenario: Video Clip Harness
 *     Given a VideoClipHarness is instantiated with an MP4 URL
 *     When the harness is started
 *     Then it plays the video and provides a standard HTMLVideoElement for downstream plugins (like Overscan)
 * 
 *   Scenario: JSON Payload Harness
 *     Given a JsonPayloadHarness is instantiated with a URL to a JSON array of GestureEventPayloads
 *     When the harness is started
 *     Then it replays the payloads at the specified framerate, bypassing the MediaPipe plugin entirely
 *     And it emits the payloads directly to the downstream consumers (like the SCXML FSM or Babylon Physics)
 */
// @ts-nocheck


import type { GestureEventPayload } from "./mediapipe_gesture";

/**
 * The base interface for any input harness.
 * A harness is responsible for starting, stopping, and cleaning up its data source.
 */
export interface InputHarness {
    start(): Promise<void>;
    stop(): void;
    dispose(): void;
}

// ============================================================================
// VIDEO CLIP HARNESS
// ============================================================================

export interface VideoClipHarnessConfig {
    videoUrl: string;
    loop?: boolean;
    muted?: boolean;
    playbackRate?: number;
}

/**
 * Harness for playing an MP4 (or other video file) as if it were a webcam feed.
 * Downstream plugins (like OverscanCanvas) can consume `harness.getVideoElement()`.
 */
export class VideoClipHarness implements InputHarness {
    private videoElement: HTMLVideoElement;
    private config: VideoClipHarnessConfig;

    constructor(config: VideoClipHarnessConfig) {
        this.config = {
            loop: true,
            muted: true,
            playbackRate: 1.0,
            ...config
        };

        this.videoElement = document.createElement("video");
        this.videoElement.src = this.config.videoUrl;
        this.videoElement.loop = this.config.loop!;
        this.videoElement.muted = this.config.muted!;
        this.videoElement.playbackRate = this.config.playbackRate!;
        
        // Required for inline playback on many mobile browsers
        this.videoElement.setAttribute("playsinline", "true");
        
        // Hide it by default, as the OverscanCanvas will handle presentation
        this.videoElement.style.display = "none";
        document.body.appendChild(this.videoElement);
    }

    public async start(): Promise<void> {
        try {
            await this.videoElement.play();
        } catch (err) {
            console.error("VideoClipHarness failed to play:", err);
            throw err;
        }
    }

    public stop(): void {
        this.videoElement.pause();
    }

    public dispose(): void {
        this.stop();
        this.videoElement.removeAttribute("src");
        this.videoElement.load();
        if (this.videoElement.parentNode) {
            this.videoElement.parentNode.removeChild(this.videoElement);
        }
    }

    /**
     * Returns the video element so downstream plugins (like OverscanCanvas) can draw it.
     */
    public getVideoElement(): HTMLVideoElement {
        return this.videoElement;
    }
}

// ============================================================================
// JSON PAYLOAD HARNESS
// ============================================================================

export interface JsonPayloadHarnessConfig {
    jsonUrl: string;
    fps?: number; // Target framerate for playback (default: 30)
    loop?: boolean;
    onPayloadEmitted: (payload: GestureEventPayload) => void; // Callback for downstream consumers
}

/**
 * Harness for replaying pre-recorded MediaPipe gesture payloads.
 * This completely bypasses the webcam, video element, and MediaPipe plugin.
 * It feeds data directly into the SCXML FSM or Babylon Physics engine.
 */
export class JsonPayloadHarness implements InputHarness {
    private config: JsonPayloadHarnessConfig;
    private payloads: GestureEventPayload[] = [];
    private currentIndex: number = 0;
    private animationFrameId: number | null = null;
    private lastFrameTime: number = 0;
    private isLoaded: boolean = false;

    constructor(config: JsonPayloadHarnessConfig) {
        this.config = {
            fps: 30,
            loop: true,
            ...config
        };
    }

    /**
     * Fetches the JSON file and parses it into an array of payloads.
     */
    private async loadPayloads(): Promise<void> {
        if (this.isLoaded) return;

        try {
            const response = await fetch(this.config.jsonUrl);
            if (!response.ok) {
                throw new Error(`Failed to fetch JSON payload: ${response.statusText}`);
            }
            
            const data = await response.json();
            if (!Array.isArray(data)) {
                throw new Error("JSON payload must be an array of GestureEventPayload objects.");
            }

            this.payloads = data as GestureEventPayload[];
            this.isLoaded = true;
            console.log(`JsonPayloadHarness loaded ${this.payloads.length} frames.`);
        } catch (err) {
            console.error("JsonPayloadHarness failed to load:", err);
            throw err;
        }
    }

    public async start(): Promise<void> {
        await this.loadPayloads();

        if (this.payloads.length === 0) {
            console.warn("JsonPayloadHarness: No payloads to play.");
            return;
        }

        if (this.animationFrameId !== null) {
            this.stop();
        }

        this.lastFrameTime = performance.now();
        this.animationFrameId = requestAnimationFrame((time) => this.tick(time));
    }

    private tick(currentTime: number): void {
        const msPerFrame = 1000 / this.config.fps!;
        const deltaTime = currentTime - this.lastFrameTime;

        if (deltaTime >= msPerFrame) {
            if (this.currentIndex >= this.payloads.length) {
                if (this.config.loop) {
                    this.currentIndex = 0; // Loop back to start
                } else {
                    this.stop();
                    return;
                }
            }

            const payload = this.payloads[this.currentIndex];
            
            // Update the timestamp to simulate real-time playback
            const simulatedPayload: GestureEventPayload = {
                ...payload,
                timestamp: currentTime
            };

            // Emit to downstream consumers (FSM, Physics, etc.)
            this.config.onPayloadEmitted(simulatedPayload);

            this.currentIndex++;
            
            // Adjust lastFrameTime to maintain consistent pacing, avoiding drift
            this.lastFrameTime = currentTime - (deltaTime % msPerFrame);
        }

        this.animationFrameId = requestAnimationFrame((time) => this.tick(time));
    }

    public stop(): void {
        if (this.animationFrameId !== null) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    public dispose(): void {
        this.stop();
        this.payloads = [];
        this.isLoaded = false;
        this.currentIndex = 0;
    }
}
