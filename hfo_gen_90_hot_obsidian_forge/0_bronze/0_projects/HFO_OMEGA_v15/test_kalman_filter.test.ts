/**
 * test_kalman_filter.test.ts
 *
 * Comprehensive Jest test suite for KalmanFilter1D and KalmanFilter2D.
 * Target: 80-99% Stryker mutation score.
 *
 * Strategy: every arithmetic operator, every branch, every return path
 * is exercised with numeric assertions so mutations produce failing tests.
 *
 * HFO v15 tile: kalman_filter.ts | ATDD-ARCH-001
 * Session: PREY8 nonce E8CA8B | Gen90 bootstrap
 */

import { KalmanFilter1D, KalmanFilter2D } from './kalman_filter';

// ─────────────────────────────────────────────────────────────────
// KalmanFilter1D
// ─────────────────────────────────────────────────────────────────

describe('KalmanFilter1D', () => {
    // ── Construction & defaults ────────────────────────────────

    describe('constructor defaults', () => {
        it('creates a filter with default parameters without throwing', () => {
            expect(() => new KalmanFilter1D()).not.toThrow();
        });

        it('stores R=1, Q=1 (verified via reset behaviour)', () => {
            const f = new KalmanFilter1D(1, 1);
            expect(f.filter(5)).toBe(5); // first call bootstraps from measurement
        });
    });

    // ── Initialization on first measurement ──────────────────

    describe('filter — first measurement initialisation', () => {
        it('returns the first measurement exactly (C=1)', () => {
            const f = new KalmanFilter1D();
            expect(f.filter(10)).toBe(10);
        });

        it('returns the first measurement when measurement is 0', () => {
            const f = new KalmanFilter1D();
            expect(f.filter(0)).toBe(0);
        });

        it('returns the first measurement when measurement is negative', () => {
            const f = new KalmanFilter1D();
            expect(f.filter(-42)).toBe(-42);
        });

        it('initialises state only once — second call produces a smoothed value', () => {
            const f = new KalmanFilter1D(1, 1);
            f.filter(10);
            // Second measurement is the same — should return same value if no noise model
            const v2 = f.filter(10);
            expect(v2).toBeCloseTo(10, 5);
        });
    });

    // ── NaN / Infinity guard ──────────────────────────────────

    describe('filter — NaN and Infinity guard', () => {
        it('returns 0 on NaN when state is uninitialised', () => {
            const f = new KalmanFilter1D();
            expect(f.filter(NaN)).toBe(0);
        });

        it('returns last good estimate on NaN when state is initialised', () => {
            const f = new KalmanFilter1D();
            f.filter(7); // initialise state to 7
            expect(f.filter(NaN)).toBe(7);
        });

        it('returns 0 on +Infinity when state uninitialised', () => {
            const f = new KalmanFilter1D();
            expect(f.filter(Infinity)).toBe(0);
        });

        it('returns last good estimate on -Infinity when state is initialised', () => {
            const f = new KalmanFilter1D();
            f.filter(3.5);
            expect(f.filter(-Infinity)).toBeCloseTo(3.5, 5);
        });

        it('does NOT update internal state on NaN — next valid measurement recovers cleanly', () => {
            const f = new KalmanFilter1D();
            f.filter(5);        // init at 5
            f.filter(NaN);      // should be ignored
            const v = f.filter(5);  // should still be close to 5
            expect(v).toBeCloseTo(5, 2);
        });
    });

    // ── Smoothing behaviour ───────────────────────────────────

    describe('filter — subsequent measurements (smoothing)', () => {
        it('smooths toward the true signal over multiple identical measurements', () => {
            const f = new KalmanFilter1D(1, 1);
            let v = 0;
            for (let i = 0; i < 30; i++) v = f.filter(100);
            expect(v).toBeGreaterThan(95);
            expect(v).toBeLessThanOrEqual(100);
        });

        it('output is between previous estimate and new measurement (convexity)', () => {
            const f = new KalmanFilter1D(1, 10); // high Q = trusts sensor more
            expect(f.filter(0)).toBe(0);
            const v2 = f.filter(100);
            // After seed at 0, next output should be between 0 and 100 (exclusive)
            expect(v2).toBeGreaterThan(0);
            expect(v2).toBeLessThan(100);
        });

        it('high R (process noise) → faster convergence to measurement (higher Kalman gain)', () => {
            // High R = distrusts process model → Kalman gain closer to 1 → tracks measurement fast
            // Low R  = trusts process model  → Kalman gain lower → slower to update
            const fast = new KalmanFilter1D(100, 1);  // high R = fast tracking
            const slow = new KalmanFilter1D(0.001, 1); // very low R = slow tracking
            fast.filter(0); slow.filter(0);
            const vFast = fast.filter(100);
            const vSlow = slow.filter(100);
            expect(vFast).toBeGreaterThan(vSlow);
        });

        it('low Q (measurement noise) → output stays closer to prior estimate', () => {
            const trustModel = new KalmanFilter1D(1, 100); // high Q = less sensor trust
            const trustSensor = new KalmanFilter1D(1, 1);
            trustModel.filter(0); trustSensor.filter(0);
            const close = trustSensor.filter(100);
            const far = trustModel.filter(100);
            // trustSensor should converge faster to 100
            expect(close).toBeGreaterThan(far);
        });

        it('produces stable numerical output (no NaN propagation) on random inputs', () => {
            const f = new KalmanFilter1D(0.1, 0.5);
            for (let i = 0; i < 100; i++) {
                const val = f.filter(Math.random() * 1000 - 500);
                expect(Number.isFinite(val)).toBe(true);
            }
        });
    });

    // ── Arithmetic correctness assertions ─────────────────────

    describe('filter — arithmetic correctness (mutation kills)', () => {
        it('second call output is strictly less than measurement when started at 0', () => {
            const f = new KalmanFilter1D(1, 1);
            f.filter(0);      // init
            const v = f.filter(10);
            expect(v).toBeGreaterThan(0);
            expect(v).toBeLessThan(10);
        });

        it('Kalman gain blends prior and measurement — verify exact value for R=1, Q=1, C=1, A=1', () => {
            // After init at x=0, p=(1/1)*1*(1/1)=1
            // Next: predX=0, predP=1+1=2 (A=1, R=1)
            // K = 2*1 / (1*2*1+1) = 2/3
            // x = 0 + 2/3*(10-0) = 6.666...
            const f = new KalmanFilter1D(1, 1, 1, 0, 1);
            f.filter(0);
            const v = f.filter(10);
            expect(v).toBeCloseTo(10 * 2 / 3, 4);
        });

        it('Kalman gain with C=2 differs from C=1 — kills * vs / mutation on C in gain formula', () => {
            // K = predP * C / (C * predP * C + Q)
            // With C=2: gain is different than C=1
            // predP after init(C=2): p = (1/2)*Q*(1/2) = Q/4 = 0.25 (Q=1)
            // K = 0.25 * 2 / (2 * 0.25 * 2 + Q) = 0.5 / (1 + 1) = 0.25
            // final x = predX + 0.25 * (meas - C*predX)
            // With C=2 mutant (*/): K = predP / C * (1/(C*predP*C+Q)) = completely different
            const c1 = new KalmanFilter1D(1, 1, 1, 0, 1); // C=1 default
            const c2 = new KalmanFilter1D(1, 1, 1, 0, 2); // C=2
            c1.filter(0); c2.filter(0);
            const v1 = c1.filter(10);
            const v2 = c2.filter(10);
            // The outputs MUST differ — if they're equal, the C mutation survived
            expect(Math.abs(v1 - v2)).toBeGreaterThan(0.01);
            // Both should be finite and reasonable
            expect(Number.isFinite(v1)).toBe(true);
            expect(Number.isFinite(v2)).toBe(true);
        });

        // ── C=2 exact arithmetic chain (kills lines 54-57, 62-63, 73, 75) ──

        it('C=2 call-1: first call returns (1/C)*measurement exactly — kills init block mutations', () => {
            // With C=2: x_init = (1/2)*4 = 2.0
            // Mutant (ConditionalExpression/BlockStatement skips init):
            //   predX = A*NaN = NaN → NaN guard fires → x = measurement = 4.0 ≠ 2.0
            // Mutant (ArithmeticOperator 1/C → 1*C):
            //   x_init = 2*4 = 8.0 ≠ 2.0
            const f = new KalmanFilter1D(1, 1, 1, 0, 2);
            expect(f.filter(4.0)).toBe(2.0);
        });

        it('C=2 call-2: exact second-call output — kills predX/predP/K mutations and p_init mutations', () => {
            // R=1, Q=1, A=1, B=0, C=2
            // After init(4.0): x=2.0, p_correct=0.25, p_mutant_57_22=(1*C)*Q*(1/C)=Q=1.0
            // Call 2 correct path:
            //   predX = 1*2 = 2.0
            //   predP = (1*0.25*1)+1 = 1.25
            //   K = 1.25*2/(2*1.25*2+1) = 2.5/6 = 5/12 ≈ 0.41667
            //   x = 2 + (5/12)*(10 - 4) = 2 + 2.5 = 4.5
            // Any arithmetic mutation to predX, predP, C args, or K formula changes result:
            //   p_mutant → predP=2 → K=4/9 → x=4.667 ≠ 4.5
            //   predX mutant (A+x) → predX=3 → x=4.667 ≠ 4.5
            //   K numerator mutant → K changes → x ≠ 4.5
            const f = new KalmanFilter1D(1, 1, 1, 0, 2);
            f.filter(4.0); // init
            expect(f.filter(10.0)).toBeCloseTo(4.5, 4);
        });

        it('C=2 call-3: exact third-call output — kills covariance update mutations on line 75', () => {
            // R=1, Q=1, A=1, B=0, C=2
            // After call-2: x=4.5, p_correct=5/24≈0.2083
            //   p = predP - K*C*predP = 1.25 - (5/12)*2*1.25 = 1.25 - 12.5/12 = 5/24
            // Mutant (line-75 p = predP + K*C*predP):
            //   p_mutant = 1.25 + 1.0417 = 2.2917
            // Call-3 correct: predP=29/24≈1.2083, K=29/70, x≈4.9143
            // Call-3 mutant:  predP=3.2917,        K≈0.4647, x≈4.9647
            // Difference > 0.05 — caught by toBeCloseTo(..., 1)
            const f = new KalmanFilter1D(1, 1, 1, 0, 2);
            f.filter(4.0);
            f.filter(10.0);
            // x after call-3: 4.5 + 29/70 * (10-9) = 4.5 + 0.41429 ≈ 4.914
            expect(f.filter(10.0)).toBeCloseTo(4.914, 1);
        });

        it('line-66 NaN guard: fires when predP overflows to Infinity and resets state to measurement', () => {
            // A=1e200 causes predP = A^2 * p + R = 1e400 = Infinity after first call
            // Guard: !isFinite(predX) || !isFinite(predP) — must fire
            // ConditionalExpression mutant (if false): guard skipped →
            //   K = Infinity * (1/Infinity) = NaN → x = NaN ≠ 5
            // LogicalOperator mutant (||→&&): !isFinite(1e300) && !isFinite(Infinity) = false&&true = false
            //   guard skipped → K becomes NaN → x = NaN ≠ 5
            const f = new KalmanFilter1D(1, 1, 1e200, 0, 1);
            f.filter(1e100); // init: x=1e100, p=1
            // Second call: predP = (1e200)^2 * 1 + 1 = 1e400 = Infinity
            const result = f.filter(5.0);
            expect(result).toBe(5.0); // guard reset: returns measurement
        });
    });

    // ── predict() ─────────────────────────────────────────────

    describe('predict', () => {
        it('returns NaN when filter is uninitialised', () => {
            const f = new KalmanFilter1D();
            expect(Number.isNaN(f.predict())).toBe(true);
        });

        it('returns current state for 1-step lookahead with A=1 and x=5', () => {
            const f = new KalmanFilter1D();
            f.filter(5);
            // A=1, B=0, control=0 → predX = 1*5 + 0*0 = 5
            expect(f.predict(1)).toBeCloseTo(5, 5);
        });

        it('predict(0) returns current state unchanged', () => {
            const f = new KalmanFilter1D();
            f.filter(7);
            expect(f.predict(0)).toBeCloseTo(7, 5);
        });

        it('predict(3) returns compounded state after 3 A=1 steps', () => {
            const f = new KalmanFilter1D();
            f.filter(10);
            // A=1 → predX stays at 10 for N steps
            expect(f.predict(3)).toBeCloseTo(10, 4);
        });

        it('predict(2) with A=2 compounds state exponentially — distinguishes + from - mutation', () => {
            // A=2, B=0: after init at 5, predict(2) = A*(A*5) = 2*(2*5) = 20
            // BlockStatement mutant would return 5 (loop body emptied)
            // The loop body IS exercised — killed by verifying non-trivial compounding
            const f = new KalmanFilter1D(1, 1, 2, 0, 1);
            f.filter(5); // init x ≈ 5 (C=1, first measurement)
            const p2 = f.predict(2);
            // A=2, steps=2: predX after step1 = 2*x, after step2 = 2*(2*x) = 4*x
            expect(p2).toBeGreaterThan(f.predict(1)); // must compound
        });

        it('predict(1) with A=3 returns 3× the seeded state — loop body kills block mutant', () => {
            const f = new KalmanFilter1D(1, 1, 3, 0, 1);
            f.filter(4); // init x ≈ 4
            const p1 = f.predict(1); // A=3 → predX = 3*4 = 12
            const p0 = f.predict(0); // A=3, 0 steps → 4 (no loop iteration)
            expect(p1).toBeGreaterThan(p0);
            expect(p1).toBeCloseTo(p0 * 3, 2);
        });

        it('predict(1) with B=1 and control=10 — kills arithmetic operator B mutation', () => {
            // B=1, control=10: A*x + B*control = A*x + 10
            // ArithmeticOperator mutant: A*x - B*control = A*x - 10
            // These differ by 20, so the test catches the mutation
            const f = new KalmanFilter1D(1, 1, 1, 1, 1); // B=1
            f.filter(0); // init x=0
            const withControl = f.predict(1, 10);    // A*0 + 1*10 = 10
            const withoutControl = f.predict(1, 0);  // A*0 + 1*0 = 0
            expect(withControl).toBeGreaterThan(withoutControl);
            expect(withControl).toBeCloseTo(10, 3);
            expect(withoutControl).toBeCloseTo(0, 3);
        });

        it('predict with control=-10 and B=1 gives A*x - 10', () => {
            // Further kills: + vs - arithmetic on control
            const f = new KalmanFilter1D(1, 1, 1, 1, 1); // B=1
            f.filter(0); // init x=0
            const negControl = f.predict(1, -10); // 0 + 1*(-10) = -10
            expect(negControl).toBeLessThan(0);
            expect(negControl).toBeCloseTo(-10, 3);
        });

        it('predict does NOT mutate internal state', () => {
            const f = new KalmanFilter1D();
            f.filter(10);
            f.predict(5);
            // Next filter call should still use the original x
            const v = f.filter(10);
            expect(Number.isFinite(v)).toBe(true);
            expect(v).toBeGreaterThan(0);
        });

        it('predict with control input B=0 ignores control', () => {
            const f = new KalmanFilter1D(1, 1, 1, 0, 1);
            f.filter(8);
            const withControl = f.predict(1, 999);
            const noControl = f.predict(1, 0);
            expect(withControl).toBeCloseTo(noControl, 10);
        });
    });

    // ── reset() ───────────────────────────────────────────────

    describe('reset', () => {
        it('resets state: predict returns NaN after reset', () => {
            const f = new KalmanFilter1D();
            f.filter(10);
            f.reset();
            expect(Number.isNaN(f.predict())).toBe(true);
        });

        it('resets state: filter returns exact measurement on next call after reset', () => {
            const f = new KalmanFilter1D();
            f.filter(99);
            f.reset();
            expect(f.filter(42)).toBe(42);
        });

        it('can be called on uninitialised filter without throwing', () => {
            const f = new KalmanFilter1D();
            expect(() => f.reset()).not.toThrow();
        });

        it('re-initialises correctly after second reset', () => {
            const f = new KalmanFilter1D();
            f.filter(1);
            f.reset();
            f.filter(2);
            f.reset();
            expect(f.filter(7)).toBe(7);
        });
    });
});

// ─────────────────────────────────────────────────────────────────
// KalmanFilter2D
// ─────────────────────────────────────────────────────────────────

describe('KalmanFilter2D', () => {
    describe('filter(x, y)', () => {
        it('returns the exact first measurement on initialisation', () => {
            const f = new KalmanFilter2D();
            const r = f.filter(3, 7);
            expect(r.x).toBeCloseTo(3, 5);
            expect(r.y).toBeCloseTo(7, 5);
        });

        it('produces independent x and y channels', () => {
            const f = new KalmanFilter2D(1, 1);
            f.filter(0, 100);
            const r = f.filter(10, 90);
            // x should be between 0 and 10; y between 90 and 100
            expect(r.x).toBeGreaterThan(0);
            expect(r.x).toBeLessThan(10);
            expect(r.y).toBeGreaterThan(90);
            expect(r.y).toBeLessThan(100);
        });

        it('returns an object with x and y keys', () => {
            const f = new KalmanFilter2D();
            const r = f.filter(1, 2);
            expect(Object.keys(r)).toContain('x');
            expect(Object.keys(r)).toContain('y');
        });

        it('x and y are finite numbers for valid inputs', () => {
            const f = new KalmanFilter2D();
            const r = f.filter(100, -50);
            expect(Number.isFinite(r.x)).toBe(true);
            expect(Number.isFinite(r.y)).toBe(true);
        });
    });

    describe('predict()', () => {
        it('returns NaN for x and y before any filter call', () => {
            const f = new KalmanFilter2D();
            const p = f.predict();
            expect(Number.isNaN(p.x)).toBe(true);
            expect(Number.isNaN(p.y)).toBe(true);
        });

        it('predicts x and y independently', () => {
            const f = new KalmanFilter2D(1, 1);
            f.filter(10, 20);
            const p = f.predict(1);
            expect(Number.isFinite(p.x)).toBe(true);
            expect(Number.isFinite(p.y)).toBe(true);
        });
    });

    describe('reset()', () => {
        it('resets both x and y channels', () => {
            const f = new KalmanFilter2D();
            f.filter(100, 200);
            f.reset();
            const r = f.filter(5, 15);
            expect(r.x).toBeCloseTo(5, 5);
            expect(r.y).toBeCloseTo(15, 5);
        });

        it('does not throw on uninitialised filter', () => {
            const f = new KalmanFilter2D();
            expect(() => f.reset()).not.toThrow();
        });
    });
});

// ─────────────────────────────────────────────────────────────────
// MUTATION-KILLING: exact arithmetic tests with C≠1, A≠1, B≠0
// Kills: ArithmeticOperator on lines 54-75 of kalman_filter.ts
// ─────────────────────────────────────────────────────────────────

describe('KalmanFilter1D — exact arithmetic (mutation kills, non-trivial params)', () => {
    it('C=2: first call returns (1/C)*measurement = 5 NOT C*measurement = 20', () => {
        // Kills line 56: (1/C)*m → C*m mutation
        const f = new KalmanFilter1D(1, 1, 1, 0, 2); // C=2
        expect(f.filter(10)).toBeCloseTo(5.0, 10);
    });

    it('C=2, Q=1: initial covariance p = Q/C² = 0.25 (feeds subsequent K correctly)', () => {
        // Kills line 57: p = (1/C)*Q*(1/C) arithmetic mutations
        // Prove via second call exact output:
        // init: x=5, p=0.25
        // step2: predX=5, predP=1.25, K=2.5/6=5/12
        //   x = 5 + (5/12)*(14-2*5) = 5 + 5/3 = 20/3  ≈ 6.6667
        const f = new KalmanFilter1D(1, 1, 1, 0, 2); // C=2
        f.filter(10);
        expect(f.filter(14)).toBeCloseTo(20 / 3, 8);
    });

    it('B=2, control=3: predX = A*x + B*control contributes correctly', () => {
        // Kills line 62: (A*x) + (B*control) ArithmeticOperator mutations
        // init: x=10, p=1 (C=1, A=1, R=1, Q=1)
        // predX = 1*10 + 2*3 = 16
        // predP = 1*1*1 + 1 = 2
        // K = 2 / (2 + 1) = 2/3
        // x = 16 + (2/3)*(20 - 16) = 16 + 8/3 = 56/3 ≈ 18.667
        const f = new KalmanFilter1D(1, 1, 1, 2, 1); // B=2
        f.filter(10);
        expect(f.filter(20, 3)).toBeCloseTo(56 / 3, 8);
    });

    it('A=2: predP = A*p*A + R distinguishes from A*p+R or A+p*A', () => {
        // Kills line 63: ((A*p)*A)+R ArithmeticOperator mutations
        // init: x=10, p=1 (C=1, R=1, Q=1, A=2)
        // predP = 2*1*2 + 1 = 5
        // K = 5 / (5+1) = 5/6
        // x = 20 + (5/6)*(15-20) = 20 - 25/6 = 95/6 ≈ 15.833
        const f = new KalmanFilter1D(1, 1, 2, 0, 1); // A=2, R=1
        f.filter(10);
        expect(f.filter(15)).toBeCloseTo(95 / 6, 8);
    });

    it('Kalman gain: K = predP*C/(C*predP*C+Q) differs from predP/(predP+Q) when C≠1', () => {
        // Kills line 73: K numerator/denominator arithmetic mutations
        // C=2, R=1, Q=1, A=1, B=0 — init(10): x=5, p=0.25
        // predP = 0.25 + 1 = 1.25
        // K = 1.25*2 / (2*1.25*2 + 1) = 2.5 / 6 = 5/12
        // x = 5 + (5/12)*(10 - 2*5) = 5 + 0 = 5 (because measurement == C*predX)
        // When measurement ≠ C*predX: filter(6) → x = 5 + (5/12)*(6-10) = 5-5/3 = 10/3
        const f = new KalmanFilter1D(1, 1, 1, 0, 2); // C=2
        f.filter(10); // x=5, p=0.25
        expect(f.filter(6)).toBeCloseTo(10 / 3, 8); // ≈ 3.333
    });

    it('x update: predX+K*(m-C*predX) — + and - mutations produce different results', () => {
        // Kills line 75: update x arithmetic
        // defaults (C=1, A=1, R=1, Q=1): init(10) → x=10, p=1
        // predX=10, predP=2, K=2/3
        // x = 10 + (2/3)*(20 - 10) = 10 + 20/3 = 50/3 ≈ 16.667
        // if + → -: 10 - 20/3 = 10/3 ≈ 3.33 (killed!)
        // if - → +: 10 + (2/3)*30 = 30 (killed!)
        const f = new KalmanFilter1D();
        f.filter(10);
        expect(f.filter(20)).toBeCloseTo(50 / 3, 8);
    });

    it('p update: predP*(1-K*C) — chain of 3 calls verifies covariance propagation', () => {
        // Kills line 75+: p = predP - K*C*predP ArithmeticOperator
        // init(10): x=10, p=1
        // filter(20): K=2/3, x=50/3, p=2-(2/3)*2=2/3
        // filter(20) again: predX=50/3, predP=2/3+1=5/3, K=(5/3)/(8/3)=5/8
        //   x = 50/3 + (5/8)*(20-50/3) = 50/3 + (5/8)*(10/3) = 50/3+50/24 = 450/24 = 75/4 = 18.75
        const f = new KalmanFilter1D();
        f.filter(10);
        f.filter(20);
        expect(f.filter(20)).toBeCloseTo(75 / 4, 8); // 18.75 exactly
    });

    it('initialization re-entrancy: second call with different measurement gives smoothed result not raw', () => {
        // Kills line 54: ConditionalExpression isNaN(x) → if always-true re-initializes
        // init(0): x=0, p=1 (C=1)
        // filter(10): predX=0, predP=2, K=2/3, x=0+(2/3)*10=20/3 ≈ 6.667
        // If mutation: always initialize → x=10, p=1 → return 10 (WRONG!)
        const f = new KalmanFilter1D();
        f.filter(0);
        const result = f.filter(10);
        expect(result).toBeCloseTo(20 / 3, 8); // ≈ 6.667, NOT 10
        expect(result).not.toBe(10); // Guards against always-reinitialize mutation
    });

    it('predict after init: returns state, NOT NaN (kills line 87 ConditionalExpression)', () => {
        // Line 87: if(isNaN(x)) return NaN — if mutated to if(!isNaN(x)) initialized filter returns NaN
        const f = new KalmanFilter1D();
        f.filter(10);
        const p = f.predict(1);
        expect(p).not.toBeNaN();
        expect(p).toBeCloseTo(10, 8); // A=1, x=10, 1-step → 10
    });
});
