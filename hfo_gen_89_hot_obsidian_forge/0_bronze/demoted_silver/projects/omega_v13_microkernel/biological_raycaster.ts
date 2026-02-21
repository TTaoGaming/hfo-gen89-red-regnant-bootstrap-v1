export class BiologicalRaycaster {
    private active = true;

    isActive() {
        return this.active;
    }

    detectPinch(thumbIndexDistance: number, palmWidth: number): boolean {
        // Pinch threshold is < 20% of Palm Width
        const ratio = thumbIndexDistance / palmWidth;
        return ratio < 0.20;
    }
}
