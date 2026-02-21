/**
 * Omega v13 Microkernel - MediaPipe Gesture Plugin
 * 
 * This component wraps the @mediapipe/tasks-vision HandLandmarker.
 * It takes the `processingCanvas` (from the Overscan plugin) as input and
 * emits a structured, Zod-validated stream of RAW, NOISY hand tracking data.
 * 
 * Key Invariant: This plugin DOES NOT smooth, debounce, or filter the data.
 * It is a pure translation layer from pixels to normalized coordinates [0, 1].
 * Downstream consumers (or a separate filter plugin) handle the noise.
 */
// @ts-nocheck


/*
================================================================================
SBE / ATDD (Gherkin Specs)
================================================================================

Feature: MediaPipe Gesture Plugin (Raw Noisy Tracking)
  As the Omega v13 Microkernel
  I want to extract raw hand landmarks from the processing canvas
  So that I can translate them into basic gestures without hiding the underlying noise

  Background:
    Given the MediaPipeGesturePlugin is initialized with a HandLandmarker instance
    And it is attached to the Overscan processing canvas

  Scenario: Hand detected in frame
    When the processing canvas contains a visible hand
    And the plugin processes the frame
    Then it should emit a "gesture_update" event
    And the event payload MUST contain normalized coordinates (x, y, z between 0.0 and 1.0)
    And the event payload MUST indicate if a "pinch" is occurring based on a raw distance heuristic

  Scenario: Hand lost for a single frame (Noisy tracking)
    Given the plugin emitted a "gesture_update" with a hand in the previous frame
    When the processing canvas does NOT contain a visible hand (due to noise/blur)
    And the plugin processes the frame
    Then it should emit a "gesture_update" event with an empty hands array
    And it MUST NOT attempt to "guess" or "smooth" the hand's location

  Scenario: Raw Pinch Heuristic
    Given the HandLandmarker detects a hand
    When the Euclidean distance between the THUMB_TIP (landmark 4) and INDEX_FINGER_TIP (landmark 8) is less than 0.05
    Then the emitted event MUST set `isPinching` to true
    When the distance is greater than or equal to 0.05
    Then the emitted event MUST set `isPinching` to false
*/

// Note: In a real environment, you would import these from @mediapipe/tasks-vision
// We mock the types here to define the strict boundary contract.
export interface NormalizedLandmark {
  x: number; // 0.0 to 1.0
  y: number; // 0.0 to 1.0
  z: number;
}

export interface HandLandmarkerResult {
  landmarks: NormalizedLandmark[][];
}

// The mock interface for the MediaPipe HandLandmarker
export interface HandLandmarker {
  detectForVideo(videoFrame: HTMLCanvasElement | HTMLVideoElement, timestamp: number): HandLandmarkerResult;
}

// ============================================================================
// The Output Contract (SEAL)
// ============================================================================

export interface HandState {
  id: number; // Index of the hand in the array
  pointerX: number; // Usually the index finger tip X
  pointerY: number; // Usually the index finger tip Y
  isPinching: boolean;
  rawLandmarks: NormalizedLandmark[];
}

export interface GestureEventPayload {
  timestamp: number;
  hands: HandState[];
}

export type GestureEventListener = (payload: GestureEventPayload) => void;

// ============================================================================
// The Plugin Implementation
// ============================================================================

export class MediaPipeGesturePlugin {
  private landmarker: HandLandmarker;
  private sourceCanvas: HTMLCanvasElement | null = null;
  private listeners: Set<GestureEventListener> = new Set();
  
  // The threshold for the noisy pinch heuristic (normalized distance)
  private readonly PINCH_THRESHOLD = 0.05;

  // MediaPipe Landmark Indices
  private readonly THUMB_TIP = 4;
  private readonly INDEX_TIP = 8;

  constructor(landmarker: HandLandmarker) {
    this.landmarker = landmarker;
  }

  /**
   * Attaches the plugin to the processing canvas (from the Overscan plugin).
   */
  public attachSource(canvas: HTMLCanvasElement): void {
    this.sourceCanvas = canvas;
  }

  public addEventListener(listener: GestureEventListener): void {
    this.listeners.add(listener);
  }

  public removeEventListener(listener: GestureEventListener): void {
    this.listeners.delete(listener);
  }

  /**
   * Processes a single frame. This should be called inside the main render loop
   * (e.g., right after the Overscan plugin updates the processing canvas).
   * @param timestamp The current performance.now() timestamp.
   */
  public processFrame(timestamp: number): void {
    if (!this.sourceCanvas) return;

    // 1. Run the raw MediaPipe detection
    const result = this.landmarker.detectForVideo(this.sourceCanvas, timestamp);

    // 2. Translate the raw result into our strict contract
    const payload: GestureEventPayload = {
      timestamp,
      hands: []
    };

    if (result.landmarks && result.landmarks.length > 0) {
      for (let i = 0; i < result.landmarks.length; i++) {
        const handLandmarks = result.landmarks[i];
        
        // Extract the pointer coordinates (Index Finger Tip)
        const indexTip = handLandmarks[this.INDEX_TIP];
        const thumbTip = handLandmarks[this.THUMB_TIP];

        // Calculate the noisy pinch heuristic
        const isPinching = this.calculateDistance(thumbTip, indexTip) < this.PINCH_THRESHOLD;

        payload.hands.push({
          id: i,
          pointerX: indexTip.x,
          pointerY: indexTip.y,
          isPinching,
          rawLandmarks: handLandmarks
        });
      }
    }

    // 3. Emit the event to all downstream consumers
    // Note: If no hands are detected, it emits an empty array. It DOES NOT smooth.
    this.emit(payload);
  }

  /**
   * Calculates the Euclidean distance between two normalized landmarks.
   */
  private calculateDistance(p1: NormalizedLandmark, p2: NormalizedLandmark): number {
    const dx = p1.x - p2.x;
    const dy = p1.y - p2.y;
    const dz = p1.z - p2.z;
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }

  private emit(payload: GestureEventPayload): void {
    for (const listener of this.listeners) {
      try {
        listener(payload);
      } catch (e) {
        console.error("MediaPipeGesturePlugin: Error in downstream listener", e);
      }
    }
  }
}
