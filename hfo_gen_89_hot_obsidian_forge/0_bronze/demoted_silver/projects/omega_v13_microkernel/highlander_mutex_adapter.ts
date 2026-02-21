/**
 * highlander_mutex_adapter.ts
 * 
 * "There can be only one."
 * 
 * This adapter sits in front of the GestureBridge and enforces single-touch
 * semantics on a multi-touch substrate. It acts as a mutex, locking onto the
 * first hand that appears (or the first hand to commit, depending on config)
 * and ignoring all other hands until the active hand is lost or released.
 */

import { RawHandData } from './gesture_bridge';

export interface HighlanderConfig {
    /**
     * If true, the mutex only locks when a hand actually commits (pinches).
     * If false, the mutex locks as soon as any hand appears (hovers).
     */
    lockOnCommitOnly: boolean;
    
    /**
     * If true, hover events (moving without pinching) are completely dropped.
     * The app will only see the pointer when it is actively clicking/dragging.
     */
    dropHoverEvents: boolean;
}

export class HighlanderMutexAdapter {
    private activeHandId: number | null = null;
    private config: HighlanderConfig;

    constructor(config: Partial<HighlanderConfig> = {}) {
        this.config = {
            lockOnCommitOnly: config.lockOnCommitOnly ?? false,
            dropHoverEvents: config.dropHoverEvents ?? false
        };
    }

    /**
     * Filters an array of raw hand data, returning only the data for the active hand.
     * Manages the mutex state internally.
     * 
     * @param hands The raw multi-touch frame data
     * @returns An array containing at most one hand (the active one)
     */
    public filterFrame(hands: RawHandData[]): RawHandData[] {
        if (hands.length === 0) {
            // No hands visible. Release the mutex.
            this.activeHandId = null;
            return [];
        }

        // 1. Check if our currently active hand is still present
        if (this.activeHandId !== null) {
            const activeHand = hands.find(h => h.handId === this.activeHandId);
            if (activeHand) {
                // The active hand is still here. Keep the lock.
                return this.processActiveHand(activeHand);
            } else {
                // The active hand disappeared. Release the lock.
                this.activeHandId = null;
            }
        }

        // 2. We don't have an active hand. Try to acquire the lock.
        // Sort by handId to ensure deterministic behavior if multiple hands appear simultaneously
        const sortedHands = [...hands].sort((a, b) => a.handId - b.handId);

        for (const hand of sortedHands) {
            const isCommitting = hand.gesture === 'pointer_up' && hand.confidence > 0.8; // Simple heuristic for commit

            if (this.config.lockOnCommitOnly) {
                if (isCommitting) {
                    this.activeHandId = hand.handId;
                    return this.processActiveHand(hand);
                }
            } else {
                // Lock on first sight
                this.activeHandId = hand.handId;
                return this.processActiveHand(hand);
            }
        }

        // No hand acquired the lock (e.g., lockOnCommitOnly is true and no one is pinching)
        return [];
    }

    /**
     * Applies the dropHoverEvents configuration to the active hand.
     */
    private processActiveHand(hand: RawHandData): RawHandData[] {
        if (this.config.dropHoverEvents) {
            const isCommitting = hand.gesture === 'pointer_up' && hand.confidence > 0.8;
            if (!isCommitting) {
                // Drop the event, but keep the lock (we return an empty array so the bridge sees 'none')
                return [];
            }
        }
        return [hand];
    }

    /**
     * Force release the mutex (useful for programmatic resets)
     */
    public release() {
        this.activeHandId = null;
    }

    public getActiveHandId(): number | null {
        return this.activeHandId;
    }
}
