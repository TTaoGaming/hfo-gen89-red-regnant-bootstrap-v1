import { BiologicalRaycaster } from './biological_raycaster';

describe('Distance-Invariant Pinch Detection (Ergonomic Pareto)', () => {
    let raycaster: BiologicalRaycaster;

    beforeEach(() => {
        raycaster = new BiologicalRaycaster();
    });

    it('Given the Biological Raycaster is active', () => {
        expect(raycaster.isActive()).toBe(true);
    });

    it('When the user pinches their fingers 2 feet from the camera, Then the telemetry payload MUST emit `isPinching: true`', () => {
        // 2 feet away: large pixel distances
        const palmWidth = 100; // pixels
        const thumbIndexDist = 15; // pixels (< 20% of 100)
        
        const isPinching = raycaster.detectPinch(thumbIndexDist, palmWidth);
        expect(isPinching).toBe(true);
    });

    it('When the user steps back 15 feet from the camera, Then the telemetry payload MUST STILL emit `isPinching: true`', () => {
        // 15 feet away: small pixel distances (shrunk by 90%)
        const palmWidth = 10; // pixels
        const thumbIndexDist = 1.5; // pixels (< 20% of 10)
        
        const isPinching = raycaster.detectPinch(thumbIndexDist, palmWidth);
        expect(isPinching).toBe(true);
    });
});
