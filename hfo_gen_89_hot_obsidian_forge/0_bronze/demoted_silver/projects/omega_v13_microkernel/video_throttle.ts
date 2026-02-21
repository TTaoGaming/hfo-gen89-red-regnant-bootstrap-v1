/**
 * Omega v13 Microkernel - Video Resource Throttle
 * 
 * This component is responsible for stably stepping the resolution of a running
 * MediaStreamTrack up or down based on external commands. It implements the
 * Gherkin specs defined in `2026-02-19_omega_v13_microkernel_project.md`.
 * 
 * Key Invariant: It uses `applyConstraints()` to avoid stopping the stream and
 * causing a black screen flash. It gracefully handles `OverconstrainedError`.
 */

export interface ResolutionLevel {
  width: number;
  height: number;
}

export class VideoResourceThrottle {
  private track: MediaStreamTrack | null = null;
  private currentLevelIndex: number;
  private readonly ladder: ResolutionLevel[];
  private isApplying: boolean = false;

  /**
   * Initializes the throttle with a predefined resolution ladder.
   * @param ladder An array of ResolutionLevels, ordered from lowest to highest quality.
   * @param initialLevelIndex The starting index in the ladder.
   */
  constructor(ladder: ResolutionLevel[], initialLevelIndex: number = 0) {
    if (!ladder || ladder.length === 0) {
      throw new Error("Resolution ladder must contain at least one level.");
    }
    if (initialLevelIndex < 0 || initialLevelIndex >= ladder.length) {
      throw new Error("Initial level index is out of bounds.");
    }
    this.ladder = ladder;
    this.currentLevelIndex = initialLevelIndex;
  }

  /**
   * Attaches the throttle to a running video track.
   * @param track The MediaStreamVideoTrack to manage.
   */
  public attachTrack(track: MediaStreamTrack): void {
    this.track = track;
    // Optionally apply the initial constraints immediately
    // this.applyCurrentLevel();
  }

  /**
   * Detaches the throttle from the current track.
   */
  public detachTrack(): void {
    this.track = null;
  }

  /**
   * Steps the resolution down to the next lower level in the ladder.
   * @returns A promise that resolves to true if the step was successful, false otherwise.
   */
  public async stepDown(): Promise<boolean> {
    if (this.currentLevelIndex <= 0) {
      console.warn("VideoResourceThrottle: Already at lowest resolution level. Ignoring step down.");
      return false; // Scenario: Attempt to step down at the lowest level
    }
    return this.attemptStep(this.currentLevelIndex - 1);
  }

  /**
   * Steps the resolution up to the next higher level in the ladder.
   * @returns A promise that resolves to true if the step was successful, false otherwise.
   */
  public async stepUp(): Promise<boolean> {
    if (this.currentLevelIndex >= this.ladder.length - 1) {
      console.warn("VideoResourceThrottle: Already at highest resolution level. Ignoring step up.");
      return false; // Scenario: Attempt to step up at the highest level
    }
    return this.attemptStep(this.currentLevelIndex + 1);
  }

  /**
   * Gets the current resolution level index.
   */
  public getCurrentLevelIndex(): number {
    return this.currentLevelIndex;
  }

  /**
   * Gets the current resolution level configuration.
   */
  public getCurrentLevel(): ResolutionLevel {
    return this.ladder[this.currentLevelIndex];
  }

  /**
   * Internal method to attempt applying constraints for a specific level.
   * @param targetIndex The index of the level to attempt.
   * @returns A promise that resolves to true if successful, false if it failed or was ignored.
   */
  private async attemptStep(targetIndex: number): Promise<boolean> {
    if (!this.track) {
      console.error("VideoResourceThrottle: No track attached. Cannot apply constraints.");
      return false;
    }

    if (this.isApplying) {
      console.warn("VideoResourceThrottle: Constraints are currently being applied. Ignoring request.");
      return false; // Prevent concurrent constraint applications
    }

    this.isApplying = true;
    const targetLevel = this.ladder[targetIndex];

    try {
      // Scenario: Step down/up resolution successfully
      // We use ideal constraints to allow the browser some flexibility,
      // but we could use exact if strict adherence is required.
      await this.track.applyConstraints({
        width: { ideal: targetLevel.width },
        height: { ideal: targetLevel.height }
      });
      
      // Only update the index if the constraints were successfully applied
      this.currentLevelIndex = targetIndex;
      console.log(`VideoResourceThrottle: Successfully stepped to level ${targetIndex} (${targetLevel.width}x${targetLevel.height})`);
      return true;

    } catch (error) {
      // Scenario: Browser rejects the requested constraints (OverconstrainedError)
      if (error instanceof Error && error.name === 'OverconstrainedError') {
        console.error(`VideoResourceThrottle: Browser rejected constraints for level ${targetIndex}. Maintaining current level ${this.currentLevelIndex}.`, error);
      } else {
        console.error(`VideoResourceThrottle: Unexpected error applying constraints for level ${targetIndex}.`, error);
      }
      // The currentLevelIndex remains unchanged, and the stream continues at the old resolution.
      return false;
    } finally {
      this.isApplying = false;
    }
  }
}
