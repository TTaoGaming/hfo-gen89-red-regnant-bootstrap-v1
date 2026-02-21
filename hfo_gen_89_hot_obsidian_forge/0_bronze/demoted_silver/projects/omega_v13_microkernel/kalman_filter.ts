/**
 * kalman_filter.ts
 * 
 * A lightweight 1D Kalman filter implementation for smoothing noisy tracking data
 * and providing predictive lookahead without the rubber-banding of a physics engine.
 * 
 * Used for the Omega v13 Microkernel to stabilize MediaPipe landmarks before
 * they hit the W3C Pointer fabric.
 */

export class KalmanFilter1D {
    private R: number; // Process noise (how much we trust the model)
    private Q: number; // Measurement noise (how much we trust the sensor)
    private A: number; // State transition model
    private B: number; // Control input model
    private C: number; // Observation model

    private x: number; // Estimated state
    private p: number; // Estimation error covariance

    /**
     * @param R Process noise (default: 1)
     * @param Q Measurement noise (default: 1)
     * @param A State transition (default: 1)
     * @param B Control input (default: 0)
     * @param C Observation model (default: 1)
     */
    constructor(R = 1, Q = 1, A = 1, B = 0, C = 1) {
        this.R = R;
        this.Q = Q;
        this.A = A;
        this.B = B;
        this.C = C;

        this.x = NaN; // Initial state unknown
        this.p = NaN; // Initial error unknown
    }

    /**
     * Filter a new measurement
     * @param measurement The noisy input value
     * @param control Optional control input
     * @returns The smoothed estimate
     */
    public filter(measurement: number, control: number = 0): number {
        // Sanity-guard: reject NaN / Infinity / subnormal inputs that would
        // poison the running state and propagate NaN downstream forever.
        // Return the last good estimate (or 0 on first call) so the pipeline
        // silently skips the bad frame rather than corrupting all future output.
        if (!isFinite(measurement) || isNaN(measurement)) {
            return isNaN(this.x) ? 0 : this.x;
        }

        if (isNaN(this.x)) {
            // Initialize on first measurement
            this.x = (1 / this.C) * measurement;
            this.p = (1 / this.C) * this.Q * (1 / this.C);
            return this.x;
        }

        // Prediction step
        const predX = (this.A * this.x) + (this.B * control);
        const predP = ((this.A * this.p) * this.A) + this.R;

        // Guard: if accumulated numerical error produced NaN in state, reset
        if (!isFinite(predX) || !isFinite(predP)) {
            this.x = measurement;
            this.p = this.Q;
            return this.x;
        }

        // Update step
        const K = predP * this.C * (1 / ((this.C * predP * this.C) + this.Q)); // Kalman gain
        this.x = predX + K * (measurement - (this.C * predX));
        this.p = predP - (K * this.C * predP);

        return this.x;
    }

    /**
     * Predict the next state without updating the filter
     * Useful for lookahead
     * @param steps Number of steps to look ahead
     * @param control Optional control input
     */
    public predict(steps: number = 1, control: number = 0): number {
        if (isNaN(this.x)) return NaN;
        
        let predX = this.x;
        for (let i = 0; i < steps; i++) {
            predX = (this.A * predX) + (this.B * control);
        }
        return predX;
    }
    
    /**
     * Reset the filter state
     */
    public reset(): void {
        this.x = NaN;
        this.p = NaN;
    }
}

/**
 * A 2D Kalman filter for smoothing X/Y coordinates
 */
export class KalmanFilter2D {
    private kx: KalmanFilter1D;
    private ky: KalmanFilter1D;

    constructor(R = 1, Q = 1) {
        this.kx = new KalmanFilter1D(R, Q);
        this.ky = new KalmanFilter1D(R, Q);
    }

    public filter(x: number, y: number): { x: number, y: number } {
        return {
            x: this.kx.filter(x),
            y: this.ky.filter(y)
        };
    }

    public predict(steps: number = 1): { x: number, y: number } {
        return {
            x: this.kx.predict(steps),
            y: this.ky.predict(steps)
        };
    }
    
    public reset(): void {
        this.kx.reset();
        this.ky.reset();
    }
}
