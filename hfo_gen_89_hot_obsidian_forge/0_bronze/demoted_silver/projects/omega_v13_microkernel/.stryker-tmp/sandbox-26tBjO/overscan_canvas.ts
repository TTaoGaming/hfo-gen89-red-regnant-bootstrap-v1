/**
 * Omega v13 Microkernel - Overscan Canvas Plugin
 * 
 * This component separates the visual presentation of the camera feed from the
 * processing feed used by MediaPipe. It implements the "Overscan Pattern" invariant.
 * 
 * Key Invariant: MediaPipe ALWAYS processes the full, unzoomed video frame. The user
 * sees a zoomed-in (overscan) or zoomed-out (negative scan) version. Downstream
 * consumers (dumb apps) receive coordinates based on the FULL processing frame,
 * meaning tracking is not lost when the user's hand leaves the *visible* frame but
 * remains in the *processing* frame.
 */
// @ts-nocheck


/*
================================================================================
SBE / ATDD (Gherkin Specs)
================================================================================

Feature: Overscan Canvas (Visual vs Processing Separation)
  As the Omega v13 Microkernel
  I want to separate the visual camera feed from the processing feed
  So that I can zoom the visual feed (overscan) without affecting MediaPipe's tracking area

  Background:
    Given the OverscanCanvas is initialized with a video element (1280x720)
    And the processing canvas is set to match the video resolution (1280x720)
    And the presentation canvas is set to a fixed display size (e.g., 800x600)

  Scenario: Default state (No Zoom)
    When the zoom level is set to 1.0
    And a frame is rendered
    Then the processing canvas should contain the full 1280x720 video frame
    And the presentation canvas should display the full video frame, scaled to fit 800x600

  Scenario: Overscan (Zoom In)
    When the zoom level is set to 1.5 (150% zoom)
    And a frame is rendered
    Then the processing canvas MUST STILL contain the full, unzoomed 1280x720 video frame
    And the presentation canvas should display a cropped, centered 1.5x zoomed portion of the video
    And downstream consumers receiving coordinates from the processing canvas are unaffected by the visual zoom

  Scenario: Negative Scan (Zoom Out)
    When the zoom level is set to 0.8 (80% zoom)
    And a frame is rendered
    Then the processing canvas MUST STILL contain the full, unzoomed 1280x720 video frame
    And the presentation canvas should display the video scaled down, with letterboxing/pillarboxing if necessary
*/

export class OverscanCanvas {
  private videoElement: HTMLVideoElement;
  
  // The hidden canvas that MediaPipe reads from (ALWAYS full frame)
  private processingCanvas: HTMLCanvasElement;
  private processingCtx: CanvasRenderingContext2D;

  // The visible canvas the user sees (Zoomed/Cropped)
  private presentationCanvas: HTMLCanvasElement;
  private presentationCtx: CanvasRenderingContext2D;

  // Zoom level: 1.0 = normal, > 1.0 = overscan (zoom in), < 1.0 = negative scan (zoom out)
  private zoomLevel: number = 1.0;
  
  private isRendering: boolean = false;
  private animationFrameId: number | null = null;

  /**
   * Initializes the Overscan Canvas plugin.
   * @param videoElement The source video element (usually hidden).
   * @param presentationCanvas The canvas element visible to the user.
   */
  constructor(videoElement: HTMLVideoElement, presentationCanvas: HTMLCanvasElement) {
    this.videoElement = videoElement;
    this.presentationCanvas = presentationCanvas;
    
    const pCtx = this.presentationCanvas.getContext('2d');
    if (!pCtx) throw new Error("Could not get 2D context for presentation canvas");
    this.presentationCtx = pCtx;

    // Create the hidden processing canvas in memory
    this.processingCanvas = document.createElement('canvas');
    const procCtx = this.processingCanvas.getContext('2d', { willReadFrequently: true });
    if (!procCtx) throw new Error("Could not get 2D context for processing canvas");
    this.processingCtx = procCtx;

    // Bind the render loop
    this.renderLoop = this.renderLoop.bind(this);
  }

  /**
   * Sets the user-tunable zoom level.
   * @param zoom > 1.0 for overscan, < 1.0 for negative scan, 1.0 for normal.
   */
  public setZoomLevel(zoom: number): void {
    if (zoom <= 0) {
      console.warn("OverscanCanvas: Zoom level must be greater than 0. Ignoring.");
      return;
    }
    this.zoomLevel = zoom;
  }

  public getZoomLevel(): number {
    return this.zoomLevel;
  }

  /**
   * Returns the hidden processing canvas. This is what MUST be passed to MediaPipe.
   */
  public getProcessingCanvas(): HTMLCanvasElement {
    return this.processingCanvas;
  }

  /**
   * Starts the render loop, drawing the video to both canvases.
   */
  public startRendering(): void {
    if (this.isRendering) return;
    this.isRendering = true;
    this.renderLoop();
  }

  /**
   * Stops the render loop.
   */
  public stopRendering(): void {
    this.isRendering = false;
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  /**
   * The core render loop. Executes the invariant: Processing is full frame, Presentation is zoomed.
   */
  private renderLoop(): void {
    if (!this.isRendering) return;

    if (this.videoElement.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      const videoWidth = this.videoElement.videoWidth;
      const videoHeight = this.videoElement.videoHeight;

      // 1. Update Processing Canvas dimensions if video resolution changed (e.g., via Throttle)
      if (this.processingCanvas.width !== videoWidth || this.processingCanvas.height !== videoHeight) {
        this.processingCanvas.width = videoWidth;
        this.processingCanvas.height = videoHeight;
      }

      // 2. INVARIANT: Draw the FULL, UNZOOMED video frame to the processing canvas.
      // MediaPipe will read from this canvas.
      this.processingCtx.drawImage(this.videoElement, 0, 0, videoWidth, videoHeight);

      // 3. Draw the ZOOMED/CROPPED video frame to the presentation canvas.
      this.renderPresentation(videoWidth, videoHeight);
    }

    this.animationFrameId = requestAnimationFrame(this.renderLoop);
  }

  /**
   * Handles the math for zooming and centering the video on the presentation canvas.
   */
  private renderPresentation(videoWidth: number, videoHeight: number): void {
    const pWidth = this.presentationCanvas.width;
    const pHeight = this.presentationCanvas.height;

    // Clear previous frame
    this.presentationCtx.clearRect(0, 0, pWidth, pHeight);

    // Calculate the source rectangle (what part of the video we are looking at)
    // If zoomLevel > 1 (overscan), the source rect is SMALLER than the video (zoomed in).
    // If zoomLevel < 1 (negative scan), the source rect is LARGER than the video (zoomed out).
    const sourceWidth = videoWidth / this.zoomLevel;
    const sourceHeight = videoHeight / this.zoomLevel;

    // Center the crop
    const sourceX = (videoWidth - sourceWidth) / 2;
    const sourceY = (videoHeight - sourceHeight) / 2;

    // Draw the cropped/zoomed portion to fill the presentation canvas
    // Note: If zoomLevel < 1, sourceX/Y will be negative, which drawImage handles gracefully
    // by drawing the video smaller and leaving the edges transparent (which we cleared).
    this.presentationCtx.drawImage(
      this.videoElement,
      sourceX, sourceY, sourceWidth, sourceHeight, // Source Rect (Cropped/Zoomed)
      0, 0, pWidth, pHeight                        // Destination Rect (Full Presentation Canvas)
    );
  }
}
