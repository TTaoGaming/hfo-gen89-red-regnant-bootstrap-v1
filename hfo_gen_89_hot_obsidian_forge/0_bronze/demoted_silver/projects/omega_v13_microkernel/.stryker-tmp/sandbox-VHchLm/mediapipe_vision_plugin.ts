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
function stryNS_9fa48() {
  var g = typeof globalThis === 'object' && globalThis && globalThis.Math === Math && globalThis || new Function("return this")();
  var ns = g.__stryker__ || (g.__stryker__ = {});
  if (ns.activeMutant === undefined && g.process && g.process.env && g.process.env.__STRYKER_ACTIVE_MUTANT__) {
    ns.activeMutant = g.process.env.__STRYKER_ACTIVE_MUTANT__;
  }
  function retrieveNS() {
    return ns;
  }
  stryNS_9fa48 = retrieveNS;
  return retrieveNS();
}
stryNS_9fa48();
function stryCov_9fa48() {
  var ns = stryNS_9fa48();
  var cov = ns.mutantCoverage || (ns.mutantCoverage = {
    static: {},
    perTest: {}
  });
  function cover() {
    var c = cov.static;
    if (ns.currentTestId) {
      c = cov.perTest[ns.currentTestId] = cov.perTest[ns.currentTestId] || {};
    }
    var a = arguments;
    for (var i = 0; i < a.length; i++) {
      c[a[i]] = (c[a[i]] || 0) + 1;
    }
  }
  stryCov_9fa48 = cover;
  cover.apply(null, arguments);
}
function stryMutAct_9fa48(id) {
  var ns = stryNS_9fa48();
  function isActive(id) {
    if (ns.activeMutant === id) {
      if (ns.hitCount !== void 0 && ++ns.hitCount > ns.hitLimit) {
        throw new Error('Stryker: Hit count limit reached (' + ns.hitCount + ')');
      }
      return true;
    }
    return false;
  }
  stryMutAct_9fa48 = isActive;
  return isActive(id);
}
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
type ResolvedConfig = Required<Omit<MediaPipeVisionConfig, 'videoElement'>> & {
  videoElement?: HTMLVideoElement;
};
const DEFAULT_CONFIG: ResolvedConfig = stryMutAct_9fa48("551") ? {} : (stryCov_9fa48("551"), {
  targetFps: 15,
  numHands: 2,
  overscanScale: 1.0,
  wasmBasePath: stryMutAct_9fa48("552") ? "" : (stryCov_9fa48("552"), 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm'),
  modelAssetPath: stryMutAct_9fa48("553") ? "" : (stryCov_9fa48("553"), 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task')
});
export class MediaPipeVisionPlugin implements Plugin {
  public readonly name = stryMutAct_9fa48("554") ? "" : (stryCov_9fa48("554"), 'MediaPipeVisionPlugin');
  public readonly version = stryMutAct_9fa48("555") ? "" : (stryCov_9fa48("555"), '1.0.0');
  private context!: PluginContext;
  private config: ResolvedConfig;
  private videoElement: HTMLVideoElement | null = null;
  /** True only when this plugin created videoElement itself; false if it was passed in via config. */
  private ownedVideoElement = stryMutAct_9fa48("556") ? true : (stryCov_9fa48("556"), false);
  private startButton: HTMLButtonElement | null = null;
  private handLandmarker: HandLandmarkerType | null = null;
  private rafHandle: number | null = null;
  private lastVideoTime = stryMutAct_9fa48("557") ? +1 : (stryCov_9fa48("557"), -1);
  private lastProcessTime = 0;
  private running = stryMutAct_9fa48("558") ? true : (stryCov_9fa48("558"), false);
  constructor(config: MediaPipeVisionConfig = {}) {
    if (stryMutAct_9fa48("559")) {
      {}
    } else {
      stryCov_9fa48("559");
      this.config = stryMutAct_9fa48("560") ? {} : (stryCov_9fa48("560"), {
        ...DEFAULT_CONFIG,
        ...config
      });
    }
  }

  // ── Plugin lifecycle ─────────────────────────────────────────────────────

  public init(context: PluginContext): void {
    if (stryMutAct_9fa48("561")) {
      {}
    } else {
      stryCov_9fa48("561");
      this.context = context;
      // Read overscan scale from PAL if available
      const palScale = context.pal.resolve<number>(stryMutAct_9fa48("562") ? "" : (stryCov_9fa48("562"), 'OverscanScale'));
      if (stryMutAct_9fa48("565") ? palScale === undefined : stryMutAct_9fa48("564") ? false : stryMutAct_9fa48("563") ? true : (stryCov_9fa48("563", "564", "565"), palScale !== undefined)) {
        if (stryMutAct_9fa48("566")) {
          {}
        } else {
          stryCov_9fa48("566");
          this.config.overscanScale = palScale;
        }
      }
      // Scenario (ATDD-ARCH-002): Given bootstrap() publishes CAMERA_START_REQUESTED
      //   When Shell CTA is tapped
      //   Then MediaPipeVisionPlugin starts the camera without any bootstrapper code
      context.eventBus.subscribe(stryMutAct_9fa48("567") ? "" : (stryCov_9fa48("567"), 'CAMERA_START_REQUESTED'), stryMutAct_9fa48("568") ? () => undefined : (stryCov_9fa48("568"), () => this.startCamera()));
    }
  }
  public start(): void {
    if (stryMutAct_9fa48("569")) {
      {}
    } else {
      stryCov_9fa48("569");
      if (stryMutAct_9fa48("571") ? false : stryMutAct_9fa48("570") ? true : (stryCov_9fa48("570", "571"), this.config.videoElement)) {
        if (stryMutAct_9fa48("572")) {
          {}
        } else {
          stryCov_9fa48("572");
          // Use the bootstrapper-provided video so LayerManager and MediaPipe share
          // the same DOM element.  Fixes ghost-video / black screen (SABOTEUR-2).
          this.videoElement = this.config.videoElement;
          this.ownedVideoElement = stryMutAct_9fa48("573") ? true : (stryCov_9fa48("573"), false); // We do NOT own this — don't remove() on destroy
        }
      } else {
        if (stryMutAct_9fa48("574")) {
          {}
        } else {
          stryCov_9fa48("574");
          this.createVideoElement(); // Fallback for tests / headless environments
          this.ownedVideoElement = stryMutAct_9fa48("575") ? false : (stryCov_9fa48("575"), true);
        }
      }
      // DOM start button removed — Shell CTA publishes CAMERA_START_REQUESTED (ATDD-ARCH-002)
    }
  }
  public stop(): void {
    if (stryMutAct_9fa48("576")) {
      {}
    } else {
      stryCov_9fa48("576");
      this.running = stryMutAct_9fa48("577") ? true : (stryCov_9fa48("577"), false);
      if (stryMutAct_9fa48("580") ? this.rafHandle === null : stryMutAct_9fa48("579") ? false : stryMutAct_9fa48("578") ? true : (stryCov_9fa48("578", "579", "580"), this.rafHandle !== null)) {
        if (stryMutAct_9fa48("581")) {
          {}
        } else {
          stryCov_9fa48("581");
          cancelAnimationFrame(this.rafHandle);
          this.rafHandle = null;
        }
      }
      if (stryMutAct_9fa48("584") ? this.videoElement.srcObject : stryMutAct_9fa48("583") ? false : stryMutAct_9fa48("582") ? true : (stryCov_9fa48("582", "583", "584"), this.videoElement?.srcObject)) {
        if (stryMutAct_9fa48("585")) {
          {}
        } else {
          stryCov_9fa48("585");
          const stream = this.videoElement.srcObject as MediaStream;
          stream.getTracks().forEach(stryMutAct_9fa48("586") ? () => undefined : (stryCov_9fa48("586"), t => t.stop()));
          this.videoElement.srcObject = null;
        }
      }
    }
  }
  public destroy(): void {
    if (stryMutAct_9fa48("587")) {
      {}
    } else {
      stryCov_9fa48("587");
      this.stop();
      // Only remove the video element if this plugin created it internally.
      // If it was provided externally (config.videoElement), LayerManager owns it.
      if (stryMutAct_9fa48("589") ? false : stryMutAct_9fa48("588") ? true : (stryCov_9fa48("588", "589"), this.ownedVideoElement)) stryMutAct_9fa48("590") ? this.videoElement.remove() : (stryCov_9fa48("590"), this.videoElement?.remove());
      stryMutAct_9fa48("591") ? this.startButton.remove() : (stryCov_9fa48("591"), this.startButton?.remove());
      this.videoElement = null;
      this.startButton = null;
      this.handLandmarker = null;
    }
  }

  // ── Test injection hook (ATDD-ARCH-002, ATDD-ARCH-003) ──────────────────

  /**
   * Directly inject a synthetic frame into the pipeline without a real camera.
   * Available in test environments; no-op if context not yet initialised.
   */
  public injectTestFrame(hands: RawHandData[]): void {
    if (stryMutAct_9fa48("592")) {
      {}
    } else {
      stryCov_9fa48("592");
      if (stryMutAct_9fa48("595") ? false : stryMutAct_9fa48("594") ? true : stryMutAct_9fa48("593") ? this.context : (stryCov_9fa48("593", "594", "595"), !this.context)) return;
      this.context.eventBus.publish(stryMutAct_9fa48("596") ? "" : (stryCov_9fa48("596"), 'FRAME_PROCESSED'), hands);
    }
  }

  // ── Private: DOM setup ───────────────────────────────────────────────────

  private createVideoElement(): void {
    if (stryMutAct_9fa48("597")) {
      {}
    } else {
      stryCov_9fa48("597");
      const v = document.createElement(stryMutAct_9fa48("598") ? "" : (stryCov_9fa48("598"), 'video'));
      v.style.cssText = (stryMutAct_9fa48("599") ? [] : (stryCov_9fa48("599"), [stryMutAct_9fa48("600") ? "" : (stryCov_9fa48("600"), 'position:fixed'), stryMutAct_9fa48("601") ? "" : (stryCov_9fa48("601"), 'top:0'), stryMutAct_9fa48("602") ? "" : (stryCov_9fa48("602"), 'left:0'), stryMutAct_9fa48("603") ? "" : (stryCov_9fa48("603"), 'width:100vw'), stryMutAct_9fa48("604") ? "" : (stryCov_9fa48("604"), 'height:100vh'), stryMutAct_9fa48("605") ? "" : (stryCov_9fa48("605"), 'object-fit:cover'), stryMutAct_9fa48("606") ? "" : (stryCov_9fa48("606"), 'z-index:-1'), stryMutAct_9fa48("607") ? "" : (stryCov_9fa48("607"), 'transform:scaleX(-1)')])).join(stryMutAct_9fa48("608") ? "" : (stryCov_9fa48("608"), ';'));
      v.autoplay = stryMutAct_9fa48("609") ? false : (stryCov_9fa48("609"), true);
      v.playsInline = stryMutAct_9fa48("610") ? false : (stryCov_9fa48("610"), true);
      document.body.appendChild(v);
      this.videoElement = v;
    }
  }
  private createStartButton(): void {
    if (stryMutAct_9fa48("611")) {
      {}
    } else {
      stryCov_9fa48("611");
      // Deprecated: kept for headless/fallback use only.
      // Normal startup path: Shell CTA → bus.publish('CAMERA_START_REQUESTED') → startCamera()
      const btn = document.createElement(stryMutAct_9fa48("612") ? "" : (stryCov_9fa48("612"), 'button'));
      btn.innerText = stryMutAct_9fa48("613") ? "" : (stryCov_9fa48("613"), 'Tap to Calibrate Camera');
      btn.style.cssText = (stryMutAct_9fa48("614") ? [] : (stryCov_9fa48("614"), [stryMutAct_9fa48("615") ? "" : (stryCov_9fa48("615"), 'position:fixed'), stryMutAct_9fa48("616") ? "" : (stryCov_9fa48("616"), 'top:50%'), stryMutAct_9fa48("617") ? "" : (stryCov_9fa48("617"), 'left:50%'), stryMutAct_9fa48("618") ? "" : (stryCov_9fa48("618"), 'transform:translate(-50%,-50%)'), stryMutAct_9fa48("619") ? "" : (stryCov_9fa48("619"), 'z-index:10000'), stryMutAct_9fa48("620") ? "" : (stryCov_9fa48("620"), 'padding:20px 40px'), stryMutAct_9fa48("621") ? "" : (stryCov_9fa48("621"), 'font-size:24px'), stryMutAct_9fa48("622") ? "" : (stryCov_9fa48("622"), 'cursor:pointer'), stryMutAct_9fa48("623") ? "" : (stryCov_9fa48("623"), 'background:#4CAF50'), stryMutAct_9fa48("624") ? "" : (stryCov_9fa48("624"), 'color:white'), stryMutAct_9fa48("625") ? "" : (stryCov_9fa48("625"), 'border:none'), stryMutAct_9fa48("626") ? "" : (stryCov_9fa48("626"), 'border-radius:8px'), stryMutAct_9fa48("627") ? "" : (stryCov_9fa48("627"), 'box-shadow:0 4px 8px rgba(0,0,0,.2)')])).join(stryMutAct_9fa48("628") ? "" : (stryCov_9fa48("628"), ';'));
      btn.onclick = () => {
        if (stryMutAct_9fa48("629")) {
          {}
        } else {
          stryCov_9fa48("629");
          btn.remove();
          this.startCamera();
        }
      };
      document.body.appendChild(btn);
      this.startButton = btn;
    }
  }

  /** Start camera and MediaPipe — callable from bus event or DOM button. Idempotent. */
  public async startCamera(): Promise<void> {
    if (stryMutAct_9fa48("630")) {
      {}
    } else {
      stryCov_9fa48("630");
      if (stryMutAct_9fa48("633") ? this.running && !this.videoElement : stryMutAct_9fa48("632") ? false : stryMutAct_9fa48("631") ? true : (stryCov_9fa48("631", "632", "633"), this.running || (stryMutAct_9fa48("634") ? this.videoElement : (stryCov_9fa48("634"), !this.videoElement)))) return;
      this.context.eventBus.publish(stryMutAct_9fa48("635") ? "" : (stryCov_9fa48("635"), 'AUDIO_UNLOCK'), null);
      await this.handleUserGesture();
    }
  }

  /**
   * startVideoFile() — Start MediaPipe inference against a file src rather than getUserMedia.
   * Call AFTER the videoElement already has .src set and is playing/ready
   * (e.g. via VideoClipHarness.start()).  Bypasses getUserMedia entirely.
   * Used by golden master tests and offline video harnesses.
   */
  public async startVideoFile(): Promise<void> {
    if (stryMutAct_9fa48("636")) {
      {}
    } else {
      stryCov_9fa48("636");
      if (stryMutAct_9fa48("639") ? this.running && !this.videoElement : stryMutAct_9fa48("638") ? false : stryMutAct_9fa48("637") ? true : (stryCov_9fa48("637", "638", "639"), this.running || (stryMutAct_9fa48("640") ? this.videoElement : (stryCov_9fa48("640"), !this.videoElement)))) return;
      this.context.eventBus.publish(stryMutAct_9fa48("641") ? "" : (stryCov_9fa48("641"), 'AUDIO_UNLOCK'), null);
      try {
        if (stryMutAct_9fa48("642")) {
          {}
        } else {
          stryCov_9fa48("642");
          console.log(stryMutAct_9fa48("643") ? "" : (stryCov_9fa48("643"), '[MediaPipeVisionPlugin] startVideoFile — loading MediaPipe WASM…'));
          const {
            FilesetResolver,
            HandLandmarker
          } = await import(stryMutAct_9fa48("644") ? "" : (stryCov_9fa48("644"), '@mediapipe/tasks-vision'));
          const vision = await FilesetResolver.forVisionTasks(this.config.wasmBasePath);
          this.handLandmarker = await HandLandmarker.createFromOptions(vision, stryMutAct_9fa48("645") ? {} : (stryCov_9fa48("645"), {
            baseOptions: stryMutAct_9fa48("646") ? {} : (stryCov_9fa48("646"), {
              modelAssetPath: this.config.modelAssetPath,
              delegate: stryMutAct_9fa48("647") ? "" : (stryCov_9fa48("647"), 'GPU')
            }),
            runningMode: stryMutAct_9fa48("648") ? "" : (stryCov_9fa48("648"), 'VIDEO'),
            numHands: this.config.numHands,
            minHandDetectionConfidence: 0.5,
            minHandPresenceConfidence: 0.5,
            minTrackingConfidence: 0.5
          }));
          console.log(stryMutAct_9fa48("649") ? "" : (stryCov_9fa48("649"), '[MediaPipeVisionPlugin] HandLandmarker ready for video file ✓'));
          this.running = stryMutAct_9fa48("650") ? false : (stryCov_9fa48("650"), true);
          // Start immediately if video has data; otherwise wait for loadeddata
          if (stryMutAct_9fa48("654") ? this.videoElement.readyState < 2 : stryMutAct_9fa48("653") ? this.videoElement.readyState > 2 : stryMutAct_9fa48("652") ? false : stryMutAct_9fa48("651") ? true : (stryCov_9fa48("651", "652", "653", "654"), this.videoElement.readyState >= 2)) {
            if (stryMutAct_9fa48("655")) {
              {}
            } else {
              stryCov_9fa48("655");
              this.scheduleFrame();
            }
          } else {
            if (stryMutAct_9fa48("656")) {
              {}
            } else {
              stryCov_9fa48("656");
              this.videoElement.addEventListener(stryMutAct_9fa48("657") ? "" : (stryCov_9fa48("657"), 'loadeddata'), stryMutAct_9fa48("658") ? () => undefined : (stryCov_9fa48("658"), () => this.scheduleFrame()), stryMutAct_9fa48("659") ? {} : (stryCov_9fa48("659"), {
                once: stryMutAct_9fa48("660") ? false : (stryCov_9fa48("660"), true)
              }));
            }
          }
        }
      } catch (err) {
        if (stryMutAct_9fa48("661")) {
          {}
        } else {
          stryCov_9fa48("661");
          console.error(stryMutAct_9fa48("662") ? "" : (stryCov_9fa48("662"), '[MediaPipeVisionPlugin] startVideoFile failed:'), err);
          throw err;
        }
      }
    }
  }
  private async handleUserGesture(): Promise<void> {
    if (stryMutAct_9fa48("663")) {
      {}
    } else {
      stryCov_9fa48("663");
      try {
        if (stryMutAct_9fa48("664")) {
          {}
        } else {
          stryCov_9fa48("664");
          const stream = await navigator.mediaDevices.getUserMedia(stryMutAct_9fa48("665") ? {} : (stryCov_9fa48("665"), {
            video: stryMutAct_9fa48("666") ? false : (stryCov_9fa48("666"), true)
          }));
          const v = this.videoElement!;
          v.srcObject = stream;
          const {
            FilesetResolver,
            HandLandmarker
          } = await import(stryMutAct_9fa48("667") ? "" : (stryCov_9fa48("667"), '@mediapipe/tasks-vision'));
          const vision = await FilesetResolver.forVisionTasks(this.config.wasmBasePath);
          this.handLandmarker = await HandLandmarker.createFromOptions(vision, stryMutAct_9fa48("668") ? {} : (stryCov_9fa48("668"), {
            baseOptions: stryMutAct_9fa48("669") ? {} : (stryCov_9fa48("669"), {
              modelAssetPath: this.config.modelAssetPath,
              delegate: stryMutAct_9fa48("670") ? "" : (stryCov_9fa48("670"), 'GPU')
            }),
            runningMode: stryMutAct_9fa48("671") ? "" : (stryCov_9fa48("671"), 'VIDEO'),
            numHands: this.config.numHands,
            minHandDetectionConfidence: 0.5,
            minHandPresenceConfidence: 0.5,
            minTrackingConfidence: 0.5
          }));
          this.running = stryMutAct_9fa48("672") ? false : (stryCov_9fa48("672"), true);
          v.addEventListener(stryMutAct_9fa48("673") ? "" : (stryCov_9fa48("673"), 'loadeddata'), stryMutAct_9fa48("674") ? () => undefined : (stryCov_9fa48("674"), () => this.scheduleFrame()));
        }
      } catch (err) {
        if (stryMutAct_9fa48("675")) {
          {}
        } else {
          stryCov_9fa48("675");
          console.error(stryMutAct_9fa48("676") ? "" : (stryCov_9fa48("676"), '[MediaPipeVisionPlugin] Camera/MediaPipe init failed:'), err);
        }
      }
    }
  }
  private scheduleFrame(): void {
    if (stryMutAct_9fa48("677")) {
      {}
    } else {
      stryCov_9fa48("677");
      if (stryMutAct_9fa48("680") ? false : stryMutAct_9fa48("679") ? true : stryMutAct_9fa48("678") ? this.running : (stryCov_9fa48("678", "679", "680"), !this.running)) return;
      this.rafHandle = requestAnimationFrame(stryMutAct_9fa48("681") ? () => undefined : (stryCov_9fa48("681"), () => this.processFrame()));
    }
  }
  private processFrame(): void {
    if (stryMutAct_9fa48("682")) {
      {}
    } else {
      stryCov_9fa48("682");
      if (stryMutAct_9fa48("685") ? (!this.running || !this.handLandmarker) && !this.videoElement : stryMutAct_9fa48("684") ? false : stryMutAct_9fa48("683") ? true : (stryCov_9fa48("683", "684", "685"), (stryMutAct_9fa48("687") ? !this.running && !this.handLandmarker : stryMutAct_9fa48("686") ? false : (stryCov_9fa48("686", "687"), (stryMutAct_9fa48("688") ? this.running : (stryCov_9fa48("688"), !this.running)) || (stryMutAct_9fa48("689") ? this.handLandmarker : (stryCov_9fa48("689"), !this.handLandmarker)))) || (stryMutAct_9fa48("690") ? this.videoElement : (stryCov_9fa48("690"), !this.videoElement)))) return;
      const now = performance.now();
      const interval = stryMutAct_9fa48("691") ? 1000 * this.config.targetFps : (stryCov_9fa48("691"), 1000 / this.config.targetFps);
      if (stryMutAct_9fa48("694") ? this.videoElement.currentTime !== this.lastVideoTime || now - this.lastProcessTime > interval : stryMutAct_9fa48("693") ? false : stryMutAct_9fa48("692") ? true : (stryCov_9fa48("692", "693", "694"), (stryMutAct_9fa48("696") ? this.videoElement.currentTime === this.lastVideoTime : stryMutAct_9fa48("695") ? true : (stryCov_9fa48("695", "696"), this.videoElement.currentTime !== this.lastVideoTime)) && (stryMutAct_9fa48("699") ? now - this.lastProcessTime <= interval : stryMutAct_9fa48("698") ? now - this.lastProcessTime >= interval : stryMutAct_9fa48("697") ? true : (stryCov_9fa48("697", "698", "699"), (stryMutAct_9fa48("700") ? now + this.lastProcessTime : (stryCov_9fa48("700"), now - this.lastProcessTime)) > interval)))) {
        if (stryMutAct_9fa48("701")) {
          {}
        } else {
          stryCov_9fa48("701");
          this.lastVideoTime = this.videoElement.currentTime;
          this.lastProcessTime = now;
          const results = this.handLandmarker.detectForVideo(this.videoElement, now);
          // Always publish FRAME_PROCESSED — even an empty array lets GestureFSMPlugin
          // run its stale-hand cleanup loop and fire POINTER_COAST destroy events.
          // Without this, a hand that leaves the frame keeps its W3C pointer alive forever
          // (coast-timeout never advances because processFrame is never called).
          const handsData: RawHandData[] = (stryMutAct_9fa48("702") ? results.landmarks && [] : (stryCov_9fa48("702"), results.landmarks ?? (stryMutAct_9fa48("703") ? ["Stryker was here"] : (stryCov_9fa48("703"), [])))).map(stryMutAct_9fa48("704") ? () => undefined : (stryCov_9fa48("704"), (landmarks, index) => this.classifyHand(landmarks, index)));
          this.context.eventBus.publish(stryMutAct_9fa48("705") ? "" : (stryCov_9fa48("705"), 'FRAME_PROCESSED'), handsData);
        }
      }
      this.scheduleFrame();
    }
  }

  // ── Private: gesture classification (pure math — no buffers) ─────────────

  private classifyHand(landmarks: any[], index: number): RawHandData {
    if (stryMutAct_9fa48("706")) {
      {}
    } else {
      stryCov_9fa48("706");
      const indexCurl = this.fingerCurlScore(landmarks[5], landmarks[6], landmarks[7]);
      const middleCurl = this.fingerCurlScore(landmarks[9], landmarks[10], landmarks[11]);
      const ringCurl = this.fingerCurlScore(landmarks[13], landmarks[14], landmarks[15]);
      const pinkyCurl = this.fingerCurlScore(landmarks[17], landmarks[18], landmarks[19]);

      // Palm width (scale-invariant baseline)
      const palmWidth = this.dist3(landmarks[5], landmarks[17]);

      // Thumb scores
      const thumbScore = this.clamp01(stryMutAct_9fa48("707") ? (2.0 - this.dist3(landmarks[4], landmarks[9]) / palmWidth) * 1.0 : (stryCov_9fa48("707"), (stryMutAct_9fa48("708") ? 2.0 + this.dist3(landmarks[4], landmarks[9]) / palmWidth : (stryCov_9fa48("708"), 2.0 - (stryMutAct_9fa48("709") ? this.dist3(landmarks[4], landmarks[9]) * palmWidth : (stryCov_9fa48("709"), this.dist3(landmarks[4], landmarks[9]) / palmWidth)))) / 1.0));
      const thumbMiddleScore = this.clamp01(stryMutAct_9fa48("710") ? (1.5 - this.dist3(landmarks[4], landmarks[12]) / palmWidth) * 1.0 : (stryCov_9fa48("710"), (stryMutAct_9fa48("711") ? 1.5 + this.dist3(landmarks[4], landmarks[12]) / palmWidth : (stryCov_9fa48("711"), 1.5 - (stryMutAct_9fa48("712") ? this.dist3(landmarks[4], landmarks[12]) * palmWidth : (stryCov_9fa48("712"), this.dist3(landmarks[4], landmarks[12]) / palmWidth)))) / 1.0));
      const pointerUpScore = stryMutAct_9fa48("713") ? (1 - indexCurl) * 0.4 + middleCurl * 0.1 + ringCurl * 0.1 + pinkyCurl * 0.1 - thumbMiddleScore * 0.3 : (stryCov_9fa48("713"), (stryMutAct_9fa48("714") ? (1 - indexCurl) * 0.4 + middleCurl * 0.1 + ringCurl * 0.1 - pinkyCurl * 0.1 : (stryCov_9fa48("714"), (stryMutAct_9fa48("715") ? (1 - indexCurl) * 0.4 + middleCurl * 0.1 - ringCurl * 0.1 : (stryCov_9fa48("715"), (stryMutAct_9fa48("716") ? (1 - indexCurl) * 0.4 - middleCurl * 0.1 : (stryCov_9fa48("716"), (stryMutAct_9fa48("717") ? (1 - indexCurl) / 0.4 : (stryCov_9fa48("717"), (stryMutAct_9fa48("718") ? 1 + indexCurl : (stryCov_9fa48("718"), 1 - indexCurl)) * 0.4)) + (stryMutAct_9fa48("719") ? middleCurl / 0.1 : (stryCov_9fa48("719"), middleCurl * 0.1)))) + (stryMutAct_9fa48("720") ? ringCurl / 0.1 : (stryCov_9fa48("720"), ringCurl * 0.1)))) + (stryMutAct_9fa48("721") ? pinkyCurl / 0.1 : (stryCov_9fa48("721"), pinkyCurl * 0.1)))) + (stryMutAct_9fa48("722") ? thumbMiddleScore / 0.3 : (stryCov_9fa48("722"), thumbMiddleScore * 0.3)));
      const fistScore = stryMutAct_9fa48("723") ? indexCurl * 0.2 + middleCurl * 0.2 + ringCurl * 0.2 + pinkyCurl * 0.2 - thumbScore * 0.2 : (stryCov_9fa48("723"), (stryMutAct_9fa48("724") ? indexCurl * 0.2 + middleCurl * 0.2 + ringCurl * 0.2 - pinkyCurl * 0.2 : (stryCov_9fa48("724"), (stryMutAct_9fa48("725") ? indexCurl * 0.2 + middleCurl * 0.2 - ringCurl * 0.2 : (stryCov_9fa48("725"), (stryMutAct_9fa48("726") ? indexCurl * 0.2 - middleCurl * 0.2 : (stryCov_9fa48("726"), (stryMutAct_9fa48("727") ? indexCurl / 0.2 : (stryCov_9fa48("727"), indexCurl * 0.2)) + (stryMutAct_9fa48("728") ? middleCurl / 0.2 : (stryCov_9fa48("728"), middleCurl * 0.2)))) + (stryMutAct_9fa48("729") ? ringCurl / 0.2 : (stryCov_9fa48("729"), ringCurl * 0.2)))) + (stryMutAct_9fa48("730") ? pinkyCurl / 0.2 : (stryCov_9fa48("730"), pinkyCurl * 0.2)))) + (stryMutAct_9fa48("731") ? thumbScore / 0.2 : (stryCov_9fa48("731"), thumbScore * 0.2)));
      const palmScore = stryMutAct_9fa48("732") ? (1 - indexCurl) * 0.2 + (1 - middleCurl) * 0.2 + (1 - ringCurl) * 0.2 + (1 - pinkyCurl) * 0.2 - (1 - thumbScore) * 0.2 : (stryCov_9fa48("732"), (stryMutAct_9fa48("733") ? (1 - indexCurl) * 0.2 + (1 - middleCurl) * 0.2 + (1 - ringCurl) * 0.2 - (1 - pinkyCurl) * 0.2 : (stryCov_9fa48("733"), (stryMutAct_9fa48("734") ? (1 - indexCurl) * 0.2 + (1 - middleCurl) * 0.2 - (1 - ringCurl) * 0.2 : (stryCov_9fa48("734"), (stryMutAct_9fa48("735") ? (1 - indexCurl) * 0.2 - (1 - middleCurl) * 0.2 : (stryCov_9fa48("735"), (stryMutAct_9fa48("736") ? (1 - indexCurl) / 0.2 : (stryCov_9fa48("736"), (stryMutAct_9fa48("737") ? 1 + indexCurl : (stryCov_9fa48("737"), 1 - indexCurl)) * 0.2)) + (stryMutAct_9fa48("738") ? (1 - middleCurl) / 0.2 : (stryCov_9fa48("738"), (stryMutAct_9fa48("739") ? 1 + middleCurl : (stryCov_9fa48("739"), 1 - middleCurl)) * 0.2)))) + (stryMutAct_9fa48("740") ? (1 - ringCurl) / 0.2 : (stryCov_9fa48("740"), (stryMutAct_9fa48("741") ? 1 + ringCurl : (stryCov_9fa48("741"), 1 - ringCurl)) * 0.2)))) + (stryMutAct_9fa48("742") ? (1 - pinkyCurl) / 0.2 : (stryCov_9fa48("742"), (stryMutAct_9fa48("743") ? 1 + pinkyCurl : (stryCov_9fa48("743"), 1 - pinkyCurl)) * 0.2)))) + (stryMutAct_9fa48("744") ? (1 - thumbScore) / 0.2 : (stryCov_9fa48("744"), (stryMutAct_9fa48("745") ? 1 + thumbScore : (stryCov_9fa48("745"), 1 - thumbScore)) * 0.2)));

      // Raw winner — NO leaky bucket, NO debounce
      let rawGesture = stryMutAct_9fa48("746") ? "" : (stryCov_9fa48("746"), 'open_palm');
      let maxScore = palmScore;
      if (stryMutAct_9fa48("749") ? pointerUpScore > maxScore || pointerUpScore > 0.6 : stryMutAct_9fa48("748") ? false : stryMutAct_9fa48("747") ? true : (stryCov_9fa48("747", "748", "749"), (stryMutAct_9fa48("752") ? pointerUpScore <= maxScore : stryMutAct_9fa48("751") ? pointerUpScore >= maxScore : stryMutAct_9fa48("750") ? true : (stryCov_9fa48("750", "751", "752"), pointerUpScore > maxScore)) && (stryMutAct_9fa48("755") ? pointerUpScore <= 0.6 : stryMutAct_9fa48("754") ? pointerUpScore >= 0.6 : stryMutAct_9fa48("753") ? true : (stryCov_9fa48("753", "754", "755"), pointerUpScore > 0.6)))) {
        if (stryMutAct_9fa48("756")) {
          {}
        } else {
          stryCov_9fa48("756");
          rawGesture = stryMutAct_9fa48("757") ? "" : (stryCov_9fa48("757"), 'pointer_up');
          maxScore = pointerUpScore;
        }
      }
      if (stryMutAct_9fa48("760") ? fistScore > maxScore || fistScore > 0.6 : stryMutAct_9fa48("759") ? false : stryMutAct_9fa48("758") ? true : (stryCov_9fa48("758", "759", "760"), (stryMutAct_9fa48("763") ? fistScore <= maxScore : stryMutAct_9fa48("762") ? fistScore >= maxScore : stryMutAct_9fa48("761") ? true : (stryCov_9fa48("761", "762", "763"), fistScore > maxScore)) && (stryMutAct_9fa48("766") ? fistScore <= 0.6 : stryMutAct_9fa48("765") ? fistScore >= 0.6 : stryMutAct_9fa48("764") ? true : (stryCov_9fa48("764", "765", "766"), fistScore > 0.6)))) {
        if (stryMutAct_9fa48("767")) {
          {}
        } else {
          stryCov_9fa48("767");
          rawGesture = stryMutAct_9fa48("768") ? "" : (stryCov_9fa48("768"), 'closed_fist');
          maxScore = fistScore;
        }
      }

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
      const scale = this.config.overscanScale;
      const offset = stryMutAct_9fa48("769") ? (1 - 1 / scale) * 2 : (stryCov_9fa48("769"), (stryMutAct_9fa48("770") ? 1 + 1 / scale : (stryCov_9fa48("770"), 1 - (stryMutAct_9fa48("771") ? 1 * scale : (stryCov_9fa48("771"), 1 / scale)))) / 2);
      const tip = landmarks[8]; // index fingertip
      const mappedX = stryMutAct_9fa48("772") ? (1.0 - tip.x - offset) / scale : (stryCov_9fa48("772"), (stryMutAct_9fa48("773") ? 1.0 - tip.x + offset : (stryCov_9fa48("773"), (stryMutAct_9fa48("774") ? 1.0 + tip.x : (stryCov_9fa48("774"), 1.0 - tip.x)) - offset)) * scale);
      const mappedY = stryMutAct_9fa48("775") ? (tip.y - offset) / scale : (stryCov_9fa48("775"), (stryMutAct_9fa48("776") ? tip.y + offset : (stryCov_9fa48("776"), tip.y - offset)) * scale);

      // Mirror the full skeleton so VisualizationPlugin overlays align with the display.
      // INVARIANT: this is the ONLY (1 - x) operation in the pipeline.
      const mirroredLandmarks = landmarks.map(stryMutAct_9fa48("777") ? () => undefined : (stryCov_9fa48("777"), (pt: any) => stryMutAct_9fa48("778") ? {} : (stryCov_9fa48("778"), {
        ...pt,
        x: stryMutAct_9fa48("779") ? 1.0 + pt.x : (stryCov_9fa48("779"), 1.0 - pt.x)
      })));
      return stryMutAct_9fa48("780") ? {} : (stryCov_9fa48("780"), {
        handId: index,
        gesture: rawGesture,
        confidence: maxScore,
        x: asRaw(mappedX),
        y: asRaw(mappedY),
        rawLandmarks: mirroredLandmarks
      });
    }
  }

  // ── Geometric utilities ───────────────────────────────────────────────────

  private angle3(a: any, b: any, c: any): number {
    if (stryMutAct_9fa48("781")) {
      {}
    } else {
      stryCov_9fa48("781");
      const ba = stryMutAct_9fa48("782") ? {} : (stryCov_9fa48("782"), {
        x: stryMutAct_9fa48("783") ? a.x + b.x : (stryCov_9fa48("783"), a.x - b.x),
        y: stryMutAct_9fa48("784") ? a.y + b.y : (stryCov_9fa48("784"), a.y - b.y),
        z: stryMutAct_9fa48("785") ? a.z + b.z : (stryCov_9fa48("785"), a.z - b.z)
      });
      const bc = stryMutAct_9fa48("786") ? {} : (stryCov_9fa48("786"), {
        x: stryMutAct_9fa48("787") ? c.x + b.x : (stryCov_9fa48("787"), c.x - b.x),
        y: stryMutAct_9fa48("788") ? c.y + b.y : (stryCov_9fa48("788"), c.y - b.y),
        z: stryMutAct_9fa48("789") ? c.z + b.z : (stryCov_9fa48("789"), c.z - b.z)
      });
      const dot = stryMutAct_9fa48("790") ? ba.x * bc.x + ba.y * bc.y - ba.z * bc.z : (stryCov_9fa48("790"), (stryMutAct_9fa48("791") ? ba.x * bc.x - ba.y * bc.y : (stryCov_9fa48("791"), (stryMutAct_9fa48("792") ? ba.x / bc.x : (stryCov_9fa48("792"), ba.x * bc.x)) + (stryMutAct_9fa48("793") ? ba.y / bc.y : (stryCov_9fa48("793"), ba.y * bc.y)))) + (stryMutAct_9fa48("794") ? ba.z / bc.z : (stryCov_9fa48("794"), ba.z * bc.z)));
      const mag = Math.sqrt(stryMutAct_9fa48("795") ? (ba.x ** 2 + ba.y ** 2 + ba.z ** 2) / (bc.x ** 2 + bc.y ** 2 + bc.z ** 2) : (stryCov_9fa48("795"), (stryMutAct_9fa48("796") ? ba.x ** 2 + ba.y ** 2 - ba.z ** 2 : (stryCov_9fa48("796"), (stryMutAct_9fa48("797") ? ba.x ** 2 - ba.y ** 2 : (stryCov_9fa48("797"), ba.x ** 2 + ba.y ** 2)) + ba.z ** 2)) * (stryMutAct_9fa48("798") ? bc.x ** 2 + bc.y ** 2 - bc.z ** 2 : (stryCov_9fa48("798"), (stryMutAct_9fa48("799") ? bc.x ** 2 - bc.y ** 2 : (stryCov_9fa48("799"), bc.x ** 2 + bc.y ** 2)) + bc.z ** 2))));
      if (stryMutAct_9fa48("802") ? mag !== 0 : stryMutAct_9fa48("801") ? false : stryMutAct_9fa48("800") ? true : (stryCov_9fa48("800", "801", "802"), mag === 0)) return 0;
      return stryMutAct_9fa48("803") ? Math.acos(dot / mag) / (180 / Math.PI) : (stryCov_9fa48("803"), Math.acos(stryMutAct_9fa48("804") ? dot * mag : (stryCov_9fa48("804"), dot / mag)) * (stryMutAct_9fa48("805") ? 180 * Math.PI : (stryCov_9fa48("805"), 180 / Math.PI)));
    }
  }
  private fingerCurlScore(mcp: any, pip: any, dip: any): number {
    if (stryMutAct_9fa48("806")) {
      {}
    } else {
      stryCov_9fa48("806");
      return this.clamp01(stryMutAct_9fa48("807") ? (180 - this.angle3(mcp, pip, dip)) * 90 : (stryCov_9fa48("807"), (stryMutAct_9fa48("808") ? 180 + this.angle3(mcp, pip, dip) : (stryCov_9fa48("808"), 180 - this.angle3(mcp, pip, dip))) / 90));
    }
  }
  private dist3(a: any, b: any): number {
    if (stryMutAct_9fa48("809")) {
      {}
    } else {
      stryCov_9fa48("809");
      return Math.sqrt(stryMutAct_9fa48("810") ? (a.x - b.x) ** 2 + (a.y - b.y) ** 2 - (a.z - b.z) ** 2 : (stryCov_9fa48("810"), (stryMutAct_9fa48("811") ? (a.x - b.x) ** 2 - (a.y - b.y) ** 2 : (stryCov_9fa48("811"), (stryMutAct_9fa48("812") ? a.x + b.x : (stryCov_9fa48("812"), a.x - b.x)) ** 2 + (stryMutAct_9fa48("813") ? a.y + b.y : (stryCov_9fa48("813"), a.y - b.y)) ** 2)) + (stryMutAct_9fa48("814") ? a.z + b.z : (stryCov_9fa48("814"), a.z - b.z)) ** 2));
    }
  }
  private clamp01(v: number): number {
    if (stryMutAct_9fa48("815")) {
      {}
    } else {
      stryCov_9fa48("815");
      return stryMutAct_9fa48("816") ? Math.min(0, Math.min(1, v)) : (stryCov_9fa48("816"), Math.max(0, stryMutAct_9fa48("817") ? Math.max(1, v) : (stryCov_9fa48("817"), Math.min(1, v))));
    }
  }
}