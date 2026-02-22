/**
 * test_wood_grain_tuning.ts
 *
 * Mutation-hardened Jest tests for WoodGrainTuner.
 *
 * Coverage targets (mutation kills required):
 *   - maturationMonths += months  (not months - X)
 *   - profileUpdated = true  (not false)
 *   - smoothingQ += months * 0.05  (not 0.04 or 0.06, not -= )
 *   - springConstant += months * 0.1  (not 0.09, not -=)
 *   - exportProfile returns JSON of config
 *   - getConfig returns correct initial values
 *
 * HFO Omega v15 | Stryker receipt required
 */

import { WoodGrainTuner } from './wood_grain_tuning';

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('WoodGrainTuner — initial state', () => {
    let tuner: WoodGrainTuner;

    beforeEach(() => {
        tuner = new WoodGrainTuner();
    });

    it('initial smoothingQ is 0.1', () => {
        expect(tuner.getConfig().smoothingQ).toBeCloseTo(0.1);
    });

    it('initial springConstant is 0.5', () => {
        expect(tuner.getConfig().springConstant).toBeCloseTo(0.5);
    });

    it('initial maturationMonths is 0', () => {
        expect(tuner.getMaturationMonths()).toBe(0);
    });

    it('profileUpdated starts false', () => {
        expect(tuner.isProfileUpdated()).toBe(false);
    });

    it('exportProfile reflects initial config', () => {
        const exported = JSON.parse(tuner.exportProfile());
        expect(exported.smoothingQ).toBeCloseTo(0.1);
        expect(exported.springConstant).toBeCloseTo(0.5);
    });
});

describe('WoodGrainTuner — simulateMaturation', () => {
    let tuner: WoodGrainTuner;

    beforeEach(() => {
        tuner = new WoodGrainTuner();
    });

    it('sets profileUpdated to true after maturation', () => {
        tuner.simulateMaturation(1);
        expect(tuner.isProfileUpdated()).toBe(true);
    });

    it('adds months to maturationMonths (not subtracts)', () => {
        tuner.simulateMaturation(6);
        expect(tuner.getMaturationMonths()).toBe(6);
    });

    it('accumulates maturationMonths across multiple calls', () => {
        tuner.simulateMaturation(3);
        tuner.simulateMaturation(5);
        expect(tuner.getMaturationMonths()).toBe(8);
    });

    // Mutation kill: smoothingQ += months * 0.05 (not 0.04, not 0.06)
    it('smoothingQ increases by months * 0.05 (1 month → +0.05)', () => {
        tuner.simulateMaturation(1);
        expect(tuner.getConfig().smoothingQ).toBeCloseTo(0.1 + 0.05, 10);
    });

    it('smoothingQ increases by months * 0.05 (4 months → +0.20)', () => {
        tuner.simulateMaturation(4);
        expect(tuner.getConfig().smoothingQ).toBeCloseTo(0.1 + 4 * 0.05, 10);
    });

    // Mutation kill: springConstant += months * 0.1 (not 0.09, not 0.11)
    it('springConstant increases by months * 0.1 (1 month → +0.1)', () => {
        tuner.simulateMaturation(1);
        expect(tuner.getConfig().springConstant).toBeCloseTo(0.5 + 0.1, 10);
    });

    it('springConstant increases by months * 0.1 (3 months → +0.3)', () => {
        tuner.simulateMaturation(3);
        expect(tuner.getConfig().springConstant).toBeCloseTo(0.5 + 3 * 0.1, 10);
    });

    it('second maturation call accumulates on previous values', () => {
        tuner.simulateMaturation(2);
        tuner.simulateMaturation(2);
        // smoothingQ: 0.1 + 2*0.05 + 2*0.05 = 0.1 + 0.2 = 0.3
        expect(tuner.getConfig().smoothingQ).toBeCloseTo(0.1 + 4 * 0.05, 10);
        // springConstant: 0.5 + 2*0.1 + 2*0.1 = 0.5 + 0.4 = 0.9
        expect(tuner.getConfig().springConstant).toBeCloseTo(0.5 + 4 * 0.1, 10);
    });

    it('zero months does not change config values', () => {
        tuner.simulateMaturation(0);
        expect(tuner.getConfig().smoothingQ).toBeCloseTo(0.1);
        expect(tuner.getConfig().springConstant).toBeCloseTo(0.5);
    });

    it('zero months still sets profileUpdated to true', () => {
        tuner.simulateMaturation(0);
        expect(tuner.isProfileUpdated()).toBe(true);
    });
});

describe('WoodGrainTuner — exportProfile', () => {
    let tuner: WoodGrainTuner;

    beforeEach(() => {
        tuner = new WoodGrainTuner();
    });

    it('returns a valid JSON string', () => {
        expect(() => JSON.parse(tuner.exportProfile())).not.toThrow();
    });

    it('exported smoothingQ matches getConfig() after maturation', () => {
        tuner.simulateMaturation(5);
        const exported = JSON.parse(tuner.exportProfile());
        expect(exported.smoothingQ).toBeCloseTo(tuner.getConfig().smoothingQ);
    });

    it('exported springConstant matches getConfig() after maturation', () => {
        tuner.simulateMaturation(5);
        const exported = JSON.parse(tuner.exportProfile());
        expect(exported.springConstant).toBeCloseTo(tuner.getConfig().springConstant);
    });

    it('getConfig() returns a reference that reflects live state', () => {
        tuner.simulateMaturation(1);
        // The config object is returned by reference — live state
        expect(tuner.getConfig().smoothingQ).toBeCloseTo(0.1 + 0.05);
    });
});
