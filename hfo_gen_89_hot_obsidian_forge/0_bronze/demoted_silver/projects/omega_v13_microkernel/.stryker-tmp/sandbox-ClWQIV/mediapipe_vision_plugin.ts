/**
 * mediapipe_vision_plugin.ts
 *
 * A strictly encapsulated Plugin that owns the camera, MediaPipe inference,
 * and gesture classification.  This is a pure SOURCE plugin — it only
 * PUBLISHES events; it never subscribes.
 *
 * Architectural contract (ATDD-ARCH-002 + ATDD-ARCH-003):
 *   • Implements the full Plugin interface (name/version/init/start/stop/destroy).
 *   • Does NOT contain gestureBuckets or any debounce/smoothing logic.
 *     The GestureFSM is the sole intent smoother downstream.
 *   • Emits FRAME_PROCESSED and AUDIO_UNLOCK on context.eventBus only.
 *   • Provides injectTestFrame() so unit tests can drive the pipeline without
 *     a real camera or MediaPipe WASM bundle.
 *
 * Event emitted:
 *   FRAME_PROCESSED  →  RawHandData[]
 *   AUDIO_UNLOCK     →  null  (on first user interaction)
 */
// @ts-nocheck


import { Plugin, PluginContext } from './plugin_supervisor';
import type { RawHandData } from './gesture_bridge';
import { asRaw } from './types.js';

// ── MediaPipe types — only imported in browser context ──────────────────────
// We use dynamic import inside start() so the module is tree-shaken in test
// environments that have no @mediapipe/tasks-vision installed.
type HandLandmarkerType = import('@mediapipe/tasks-vision').HandLandmarker;

export interface MediaPipeVisionConfig {
    /** Target inference rate (fps) */
    targetFps?: number;
    /** Maximum number of hands to track */
    numHands?: number;
    /** Overscan scale — set via PAL key 'OverscanScale' or default 1.0 */
    overscanScale?: number;
    /** MediaPipe WASM CDN base path */
    wasmBasePath?: string;
    /** MediaPipe model asset URL */
    modelAssetPath?: string;
    /**
     * External video element provided by the bootstrapper.
     * When set, the plugin uses this element instead of creating its own hidden one,
     * so the LayerManager-registered video is both displayed and fed to MediaPipe.
     * Fixes: ghost-video (black screen) + ensures CSS scaleX(-1) mirror is on the
     * correct element.
     */
    videoElement?: HTMLVideoElement;
}

// videoElement is always optional — bootstrapper-provided or undefined in headless/test mode.
// All numeric/string fields have safe fallback values.
// Using Omit so Required<> does not force an HTMLVideoElement into the defaults object.
type ResolvedConfig = Required<Omit<MediaPipeVisionConfig, 'videoElement'>> & { videoElement?: HTMLVideoElement };

const DEFAULT_CONFIG: ResolvedConfig = {
    targetFps: 15,
    numHands: 2,
    overscanScale: 1.0,
    wasmBasePath: 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm',
    modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
};

export class MediaPipeVisionPlugin implements Plugin {
    public readonly name = 'MediaPipeVisionPlugin';
    public readonly version = '1.0.0';

    private context!: PluginContext;
    private config: ResolvedConfig;

    private videoElement: HTMLVideoElement | null = null;
    /** True only when this plugin created videoElement itself; false if it was passed in via config. */
    private ownedVideoElement = false;
    private startButton: HTMLButtonElement | null = null;
    private handLandmarker: HandLandmarkerType | null = null;
    private rafHandle: number | null = null;
    private lastVideoTime = -1;
    private lastProcessTime = 0;
    private running = false;

    constructor(config: MediaPipeVisionConfig = {}) {
        this.config = { ...DEFAULT_CONFIG, ...config };
    }

    // ── Plugin lifecycle ─────────────────────────────────────────────────────

    public init(context: PluginContext): void {
        this.context = context;
        // Read overscan scale from PAL if available
        const palScale = context.pal.resolve<number>('OverscanScale');
        if (palScale !== undefined) {
            this.config.overscanScale = palScale;
        }
        // Scenario (ATDD-ARCH-002): Given bootstrap() publishes CAMERA_START_REQUESTED
        //   When Shell CTA is tapped
        //   Then MediaPipeVisionPlugin starts the camera without any bootstrapper code
        context.eventBus.subscribe('CAMERA_START_REQUESTED', () => this.startCamera());
    }

    public start(): void {
        if (this.config.videoElement) {
            // Use the bootstrapper-provided video so LayerManager and MediaPipe share
            // the same DOM element.  Fixes ghost-video / black screen (SABOTEUR-2).
            this.videoElement = this.config.videoElement;
            this.ownedVideoElement = false; // We do NOT own this — don't remove() on destroy
        } else {
            this.createVideoElement(); // Fallback for tests / headless environments
            this.ownedVideoElement = true;
        }
        // DOM start button removed — Shell CTA publishes CAMERA_START_REQUESTED (ATDD-ARCH-002)
    }

    public stop(): void {
        this.running = false;
        if (this.rafHandle !== null) {
            cancelAnimationFrame(this.rafHandle);
            this.rafHandle = null;
        }
        if (this.videoElement?.srcObject) {
            const stream = this.videoElement.srcObject as MediaStream;
            stream.getTracks().forEach(t => t.stop());
            this.videoElement.srcObject = null;
        }
    }

    public destroy(): void {
        this.stop();
        // Only remove the video element if this plugin created it internally.
        // If it was provided externally (config.videoElement), LayerManager owns it.
        if (this.ownedVideoElement) this.videoElement?.remove();
        this.startButton?.remove();
        this.videoElement = null;
        this.startButton = null;
        this.handLandmarker = null;
    }

    // ── Test injection hook (ATDD-ARCH-002, ATDD-ARCH-003) ──────────────────

    /**
     * Directly inject a synthetic frame into the pipeline without a real camera.
     * Available in test environments; no-op if context not yet initialised.
     */
    public injectTestFrame(hands: RawHandData[]): void {
        if (!this.context) return;
        this.context.eventBus.publish('FRAME_PROCESSED', hands);
    }

    // ── Private: DOM setup ───────────────────────────────────────────────────

    private createVideoElement(): void {
        const v = document.createElement('video');
        v.style.cssText = [
            'position:fixed', 'top:0', 'left:0',
            'width:100vw', 'height:100vh',
            'object-fit:cover', 'z-index:-1',
            'transform:scaleX(-1)',
        ].join(';');
        v.autoplay = true;
        v.playsInline = true;
        document.body.appendChild(v);
        this.videoElement = v;
    }

    private createStartButton(): void {
        // Deprecated: kept for headless/fallback use only.
        // Normal startup path: Shell CTA → bus.publish('CAMERA_START_REQUESTED') → startCamera()
        const btn = document.createElement('button');
        btn.innerText = 'Tap to Calibrate Camera';
        btn.style.cssText = [
            'position:fixed', 'top:50%', 'left:50%',
            'transform:translate(-50%,-50%)',
            'z-index:10000', 'padding:20px 40px',
            'font-size:24px', 'cursor:pointer',
            'background:#4CAF50', 'color:white',
            'border:none', 'border-radius:8px',
            'box-shadow:0 4px 8px rgba(0,0,0,.2)',
        ].join(';');
        btn.onclick = () => { btn.remove(); this.startCamera(); };
        document.body.appendChild(btn);
        this.startButton = btn;
    }

    /** Start camera and MediaPipe — callable from bus event or DOM button. Idempotent. */
    public async startCamera(): Promise<void> {
        if (this.running || !this.videoElement) return;
        this.context.eventBus.publish('AUDIO_UNLOCK', null);
        await this.handleUserGesture();
    }

    /**
     * startVideoFile() — Start MediaPipe inference against a file src rather than getUserMedia.
     * Call AFTER the videoElement already has .src set and is playing/ready
     * (e.g. via VideoClipHarness.start()).  Bypasses getUserMedia entirely.
     * Used by golden master tests and offline video harnesses.
     */
    public async startVideoFile(): Promise<void> {
        if (this.running || !this.videoElement) return;
        this.context.eventBus.publish('AUDIO_UNLOCK', null);

        try {
            console.log('[MediaPipeVisionPlugin] startVideoFile — loading MediaPipe WASM…');
            const { FilesetResolver, HandLandmarker } = await import('@mediapipe/tasks-vision');
            const vision = await FilesetResolver.forVisionTasks(this.config.wasmBasePath);
            this.handLandmarker = await HandLandmarker.createFromOptions(vision, {
                baseOptions: {
                    modelAssetPath: this.config.modelAssetPath,
                    delegate: 'GPU',
                },
                runningMode: 'VIDEO',
                numHands: this.config.numHands,
                minHandDetectionConfidence: 0.5,
                minHandPresenceConfidence: 0.5,
                minTrackingConfidence: 0.5,
            });
            console.log('[MediaPipeVisionPlugin] HandLandmarker ready for video file ✓');
            this.running = true;
            // Start immediately if video has data; otherwise wait for loadeddata
            if (this.videoElement.readyState >= 2) {
                this.scheduleFrame();
            } else {
                this.videoElement.addEventListener('loadeddata', () => this.scheduleFrame(), { once: true });
            }
        } catch (err) {
            console.error('[MediaPipeVisionPlugin] startVideoFile failed:', err);
            throw err;
        }
    }

    private async handleUserGesture(): Promise<void> {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            const v = this.videoElement!;
            v.srcObject = stream;

            const { FilesetResolver, HandLandmarker } = await import('@mediapipe/tasks-vision');
            const vision = await FilesetResolver.forVisionTasks(this.config.wasmBasePath);
            this.handLandmarker = await HandLandmarker.createFromOptions(vision, {
                baseOptions: {
                    modelAssetPath: this.config.modelAssetPath,
                    delegate: 'GPU',
                },
                runningMode: 'VIDEO',
                numHands: this.config.numHands,
                minHandDetectionConfidence: 0.5,
                minHandPresenceConfidence: 0.5,
                minTrackingConfidence: 0.5,
            });

            this.running = true;
            
            const startPlaying = async () => {
                try {
                    await v.play();
                    this.scheduleFrame();
                } catch (e) {
                    console.warn('[MediaPipeVisionPlugin] play() failed:', e);
                }
            };

            if (v.readyState >= 2) {
                startPlaying();
            } else {
                v.addEventListener('loadeddata', startPlaying, { once: true });
            }
        } catch (err) {
            console.error('[MediaPipeVisionPlugin] Camera/MediaPipe init failed:', err);
        }
    }

    private scheduleFrame(): void {
        if (!this.running) return;
        this.rafHandle = requestAnimationFrame(() => this.processFrame());
    }

    private processFrame(): void {
        if (!this.running || !this.handLandmarker || !this.videoElement) return;

        const now = performance.now();
        const interval = 1000 / this.config.targetFps;

        if (
            this.videoElement.currentTime !== this.lastVideoTime &&
            now - this.lastProcessTime > interval
        ) {
            this.lastVideoTime = this.videoElement.currentTime;
            this.lastProcessTime = now;

            const results = this.handLandmarker.detectForVideo(this.videoElement, now);
            // Always publish FRAME_PROCESSED — even an empty array lets GestureFSMPlugin
            // run its stale-hand cleanup loop and fire POINTER_COAST destroy events.
            // Without this, a hand that leaves the frame keeps its W3C pointer alive forever
            // (coast-timeout never advances because processFrame is never called).
            const handsData: RawHandData[] = (results.landmarks ?? []).map((landmarks, index) =>
                this.classifyHand(landmarks, index)
            );
            this.context.eventBus.publish('FRAME_PROCESSED', handsData);
        }

        this.scheduleFrame();
    }

    // ── Private: gesture classification (pure math — no buffers) ─────────────

    private classifyHand(landmarks: any[], index: number): RawHandData {
        const indexCurl  = this.fingerCurlScore(landmarks[5],  landmarks[6],  landmarks[7]);
        const middleCurl = this.fingerCurlScore(landmarks[9],  landmarks[10], landmarks[11]);
        const ringCurl   = this.fingerCurlScore(landmarks[13], landmarks[14], landmarks[15]);
        const pinkyCurl  = this.fingerCurlScore(landmarks[17], landmarks[18], landmarks[19]);

        // Palm width (scale-invariant baseline)
        const palmWidth = this.dist3(landmarks[5], landmarks[17]);

        // Thumb scores
        const thumbScore       = this.clamp01((2.0 - this.dist3(landmarks[4], landmarks[9])  / palmWidth) / 1.0);
        const thumbMiddleScore = this.clamp01((1.5 - this.dist3(landmarks[4], landmarks[12]) / palmWidth) / 1.0);

        const pointerUpScore = (1 - indexCurl) * 0.4 + middleCurl * 0.1 + ringCurl * 0.1 + pinkyCurl * 0.1 + thumbMiddleScore * 0.3;
        const fistScore      = indexCurl * 0.2 + middleCurl * 0.2 + ringCurl * 0.2 + pinkyCurl * 0.2 + thumbScore * 0.2;
        const palmScore      = (1 - indexCurl) * 0.2 + (1 - middleCurl) * 0.2 + (1 - ringCurl) * 0.2 + (1 - pinkyCurl) * 0.2 + (1 - thumbScore) * 0.2;

        // Raw winner — NO leaky bucket, NO debounce
        let rawGesture = 'open_palm';
        let maxScore = palmScore;
        if (pointerUpScore > maxScore && pointerUpScore > 0.6) { rawGesture = 'pointer_up';   maxScore = pointerUpScore; }
        if (fistScore      > maxScore && fistScore      > 0.6) { rawGesture = 'closed_fist';  maxScore = fistScore; }

        // ── COORD_INVARIANT v1 (ONE-WAY MIRROR) ──────────────────────────────────
        // This is the SINGLE and ONLY place where X is flipped in the entire pipeline.
        //
        // MediaPipe raw:        x ∈ [0,1], left=0 (unreflected camera space)
        // CSS scaleX(-1):       visual display mirror only — does NOT affect MediaPipe values
        //
        // After this block the following invariant holds for ALL downstream consumers:
        //
        //   rawLandmarks[i].x  = 1.0 - raw_x[i]                   (mirror-only, no overscan)
        //   rawLandmarks[i].y  = raw_y[i]                          (unchanged)
        //   hand.x             = (rawLandmarks[8].x - offset)*scale (tip + overscan correction)
        //   hand.y             = (rawLandmarks[8].y - offset)*scale (tip + overscan correction)
        //
        // Consumers MUST NOT re-apply (1 - x) to rawLandmarks — doing so double-mirrors.
        // All consumers target the same WYSIWYG screen position:
        //   W3CPointerFabric / VisualizationPlugin: apply overscan to rawLandmarks → matches hand.x/y
        //   BabylonPhysicsPlugin: applies aspect-ratio-corrected ortho formula → WYSIWYG on canvas
        //
        // ───────────────────────────────────────────────────────────────────────────────
        // Overscan coordinate remap with mirror correction (SABOTEUR-3).
        // CSS scaleX(-1) is visual-only; MediaPipe tip.x is unreflected (0 = left edge
        // of the raw camera frame).  Invert X so the child's physical left → digital left.
        const scale  = this.config.overscanScale;
        const offset = (1 - 1 / scale) / 2;
        const tip    = landmarks[8]; // index fingertip
        const mappedX = (1.0 - tip.x - offset) * scale;
        const mappedY = (tip.y - offset) * scale;

        // Mirror the full skeleton so VisualizationPlugin overlays align with the display.
        // INVARIANT: this is the ONLY (1 - x) operation in the pipeline.
        const mirroredLandmarks = landmarks.map((pt: any) => ({ ...pt, x: 1.0 - pt.x }));

        return {
            handId: index,
            gesture: rawGesture,
            confidence: maxScore,
            x: asRaw(mappedX),
            y: asRaw(mappedY),
            rawLandmarks: mirroredLandmarks,
        };
    }

    // ── Geometric utilities ───────────────────────────────────────────────────

    private angle3(a: any, b: any, c: any): number {
        const ba = { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
        const bc = { x: c.x - b.x, y: c.y - b.y, z: c.z - b.z };
        const dot = ba.x * bc.x + ba.y * bc.y + ba.z * bc.z;
        const mag = Math.sqrt((ba.x**2 + ba.y**2 + ba.z**2) * (bc.x**2 + bc.y**2 + bc.z**2));
        if (mag === 0) return 0;
        return Math.acos(dot / mag) * (180 / Math.PI);
    }

    private fingerCurlScore(mcp: any, pip: any, dip: any): number {
        return this.clamp01((180 - this.angle3(mcp, pip, dip)) / 90);
    }

    private dist3(a: any, b: any): number {
        return Math.sqrt((a.x - b.x)**2 + (a.y - b.y)**2 + (a.z - b.z)**2);
    }

    private clamp01(v: number): number {
        return Math.max(0, Math.min(1, v));
    }
}
