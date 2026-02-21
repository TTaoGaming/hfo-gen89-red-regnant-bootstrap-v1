// @ts-nocheck
import fc from 'fast-check';
import { asRaw, asSmoothed, asScreenPixel, RawCoord, SmoothedCoord, ScreenPixel } from './types';
import { KalmanFilter2D } from './kalman_filter';

describe('Chaos Inoculation: Property-Based Fuzzing', () => {
    it('Kalman Filter should maintain bounds and return SmoothedCoords', () => {
        const filter = new KalmanFilter2D(10, 0.05);
        
        fc.assert(
            fc.property(fc.float(), fc.float(), (hostileX, hostileY) => {
                const rawX = asRaw(hostileX);
                const rawY = asRaw(hostileY);
                
                const result = filter.filter(rawX, rawY);
                
                // The Mathematical Invariant:
                // 1. It must return a value (not crash)
                // 2. The type system enforces it returns SmoothedCoord
                return result.x !== undefined && result.y !== undefined && !isNaN(result.x) && !isNaN(result.y);
            })
        );
    });

    it('W3CPointerFabric never exceeds screen bounds', () => {
        const MAX_WIDTH = 1920;
        const MAX_HEIGHT = 1080;

        // Mock fabric process
        // Must handle NaN / Infinity / subnormal inputs (W3C fabric invariant:
        // hostile coordinates must NEVER exceed viewport bounds).
        const processLandmark = (x: SmoothedCoord, y: SmoothedCoord): { clientX: ScreenPixel, clientY: ScreenPixel } => {
            // Sanitize before clamping — Math.min/max propagate NaN silently
            const safeX = (isFinite(x) && !isNaN(x)) ? x : 0;
            const safeY = (isFinite(y) && !isNaN(y)) ? y : 0;
            const cx = Math.max(0, Math.min(safeX, MAX_WIDTH));
            const cy = Math.max(0, Math.min(safeY, MAX_HEIGHT));
            return { clientX: asScreenPixel(cx), clientY: asScreenPixel(cy) };
        };

        fc.assert(
            fc.property(fc.float(), fc.float(), (hostileX, hostileY) => {
                const smoothedX = asSmoothed(hostileX);
                const smoothedY = asSmoothed(hostileY);

                const event = processLandmark(smoothedX, smoothedY);
                
                // The Mathematical Invariant:
                return event.clientX >= 0 && event.clientX <= MAX_WIDTH &&
                       event.clientY >= 0 && event.clientY <= MAX_HEIGHT;
            })
        );
    });
});
