/**
 * test_temporal_rollup.ts
 *
 * Mutation-hardened Jest tests for TemporalTuningRegistry.
 *
 * Coverage targets (mutation kills required):
 *   - addSnapshot / getSnapshots integrity
 *   - performRollup returns null when no snapshots in range
 *   - performRollup averages correctly (each genotype field / count)
 *   - averageProfiles throws on empty profiles
 *   - generateProceduralADR: kalmanQ_delta > 0.01 → "dynamic/erratic"
 *   - generateProceduralADR: kalmanQ_delta < -0.01 → "stabilized"
 *   - generateProceduralADR: |delta| <= 0.01 → "remained stable"
 *   - null prev → "Initial" summary
 *   - rollups are stored and retrievable via getRollups
 *   - RollupInterval enum values
 *
 * HFO Omega v15 | Stryker receipt required
 */

import { TemporalTuningRegistry, RollupInterval } from './temporal_rollup';
import type { UserTuningProfile, Genotype } from './behavioral_predictive_layer';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeGenotype(overrides: Partial<Genotype> = {}): Genotype {
    return {
        kalmanQ: 0.1,
        kalmanR: 0.01,
        axis1WeightVelocity: 0.5,
        axis1WeightFrequency: 0.3,
        axis2WeightCurvature: 0.4,
        axis2WeightAmplitude: 0.2,
        ...overrides,
    };
}

function makeProfile(lastUpdated: number, genotypeOverrides: Partial<Genotype> = {}): UserTuningProfile {
    return {
        version: '1.0',
        userIdHash: 'abc123',
        lastUpdated,
        repertoire: [makeGenotype(genotypeOverrides)],
    };
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('TemporalTuningRegistry — constructor', () => {
    it('initialises with empty snapshots', () => {
        const reg = new TemporalTuningRegistry();
        expect(reg.getSnapshots()).toHaveLength(0);
    });

    it('initialises rollup buckets for all RollupInterval values', () => {
        const reg = new TemporalTuningRegistry();
        for (const interval of Object.values(RollupInterval)) {
            expect(reg.getRollups(interval as RollupInterval)).toEqual([]);
        }
    });
});

describe('TemporalTuningRegistry — addSnapshot / getSnapshots', () => {
    it('stores a snapshot', () => {
        const reg = new TemporalTuningRegistry();
        const p = makeProfile(1000);
        reg.addSnapshot(p);
        expect(reg.getSnapshots()).toHaveLength(1);
        expect(reg.getSnapshots()[0]).toBe(p);
    });

    it('stores multiple snapshots in order', () => {
        const reg = new TemporalTuningRegistry();
        const p1 = makeProfile(1000);
        const p2 = makeProfile(2000);
        reg.addSnapshot(p1);
        reg.addSnapshot(p2);
        const snaps = reg.getSnapshots();
        expect(snaps[0]).toBe(p1);
        expect(snaps[1]).toBe(p2);
    });
});

describe('TemporalTuningRegistry — performRollup: null cases', () => {
    it('returns null when no snapshots exist', () => {
        const reg = new TemporalTuningRegistry();
        const result = reg.performRollup(RollupInterval.HOUR, 0, 9999);
        expect(result).toBeNull();
    });

    it('returns null when no snapshots fall in the time window', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(500));
        const result = reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        expect(result).toBeNull();
    });

    it('includes snapshots at exactly startTime (>=startTime)', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1000));
        const result = reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        expect(result).not.toBeNull();
    });

    it('includes snapshots at exactly endTime (<=endTime)', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(2000));
        const result = reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        expect(result).not.toBeNull();
    });

    it('excludes snapshots outside the window', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(999));   // before window
        reg.addSnapshot(makeProfile(2001));  // after window
        const result = reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        expect(result).toBeNull();
    });
});

describe('TemporalTuningRegistry — performRollup: result structure', () => {
    it('result has correct interval', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        const r = reg.performRollup(RollupInterval.DAY, 1000, 2000)!;
        expect(r.interval).toBe(RollupInterval.DAY);
    });

    it('result has correct startTime and endTime', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        const r = reg.performRollup(RollupInterval.MINUTE, 1000, 2000)!;
        expect(r.startTime).toBe(1000);
        expect(r.endTime).toBe(2000);
    });

    it('result.profile.lastUpdated equals endTime', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        const r = reg.performRollup(RollupInterval.HOUR, 1000, 2000)!;
        expect(r.profile.lastUpdated).toBe(2000);
    });

    it('result.adr.interval matches requested interval', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        const r = reg.performRollup(RollupInterval.WEEK, 1000, 2000)!;
        expect(r.adr.interval).toBe(RollupInterval.WEEK);
    });

    it('stores rollup into getRollups(interval)', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        reg.performRollup(RollupInterval.MONTH, 1000, 2000);
        expect(reg.getRollups(RollupInterval.MONTH)).toHaveLength(1);
    });

    it('accumulates multiple rollups for same interval', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        reg.addSnapshot(makeProfile(3500));
        reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        reg.performRollup(RollupInterval.HOUR, 3000, 4000);
        expect(reg.getRollups(RollupInterval.HOUR)).toHaveLength(2);
    });
});

describe('TemporalTuningRegistry — averageProfiles', () => {
    it('single profile average preserves kalmanQ', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500, { kalmanQ: 0.25 }));
        const r = reg.performRollup(RollupInterval.MINUTE, 1000, 2000)!;
        expect(r.profile.repertoire[0]!.kalmanQ).toBeCloseTo(0.25);
    });

    it('two profiles: averaged kalmanQ = mean of both', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1200, { kalmanQ: 0.1 }));
        reg.addSnapshot(makeProfile(1800, { kalmanQ: 0.3 }));
        const r = reg.performRollup(RollupInterval.MINUTE, 1000, 2000)!;
        // average: (0.1 + 0.3) / 2 = 0.2
        expect(r.profile.repertoire[0]!.kalmanQ).toBeCloseTo(0.2);
    });

    it('two profiles: averaged kalmanR = mean of both', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1200, { kalmanR: 0.01 }));
        reg.addSnapshot(makeProfile(1800, { kalmanR: 0.03 }));
        const r = reg.performRollup(RollupInterval.MINUTE, 1000, 2000)!;
        expect(r.profile.repertoire[0]!.kalmanR).toBeCloseTo(0.02);
    });

    it('three profiles: averaged axis1WeightVelocity = mean of all three', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1100, { axis1WeightVelocity: 0.3 }));
        reg.addSnapshot(makeProfile(1400, { axis1WeightVelocity: 0.6 }));
        reg.addSnapshot(makeProfile(1700, { axis1WeightVelocity: 0.9 }));
        const r = reg.performRollup(RollupInterval.HOUR, 1000, 2000)!;
        // (0.3 + 0.6 + 0.9) / 3 = 0.6
        expect(r.profile.repertoire[0]!.axis1WeightVelocity).toBeCloseTo(0.6);
    });
});

describe('TemporalTuningRegistry — generateProceduralADR summaries', () => {
    it('first rollup (no prior): summary is "Initial ... established"', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        const r = reg.performRollup(RollupInterval.MINUTE, 1000, 2000)!;
        expect(r.adr.summary).toContain('Initial');
        expect(r.adr.summary).toContain('established');
    });

    it('first rollup: deltaMetrics is empty', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        const r = reg.performRollup(RollupInterval.MINUTE, 1000, 2000)!;
        expect(Object.keys(r.adr.deltaMetrics)).toHaveLength(0);
    });

    // Mutation kill: > 0.01 not >= 0.01
    it('second rollup with kalmanQ_delta > 0.01 → "dynamic/erratic"', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500, { kalmanQ: 0.10 }));
        reg.performRollup(RollupInterval.HOUR, 1000, 2000);  // establishes prev
        reg.addSnapshot(makeProfile(3500, { kalmanQ: 0.25 }));  // delta = +0.15
        const r = reg.performRollup(RollupInterval.HOUR, 3000, 4000)!;
        expect(r.adr.summary).toContain('dynamic');
    });

    // Mutation kill: exactly 0.01 should NOT match the >0.01 branch
    it('second rollup with kalmanQ_delta = 0.01 → "remained stable"', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500, { kalmanQ: 0.10 }));
        reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        reg.addSnapshot(makeProfile(3500, { kalmanQ: 0.11 }));  // delta = +0.01 exactly
        const r = reg.performRollup(RollupInterval.HOUR, 3000, 4000)!;
        expect(r.adr.summary).toContain('stable');
    });

    // Mutation kill: < -0.01 not <= -0.01
    it('second rollup with kalmanQ_delta < -0.01 → "stabilized"', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500, { kalmanQ: 0.25 }));
        reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        reg.addSnapshot(makeProfile(3500, { kalmanQ: 0.10 }));  // delta = -0.15
        const r = reg.performRollup(RollupInterval.HOUR, 3000, 4000)!;
        expect(r.adr.summary).toContain('stabilized');
    });

    // Mutation kill: exactly -0.01 should NOT match < -0.01
    it('second rollup with kalmanQ_delta = -0.01 → "remained stable"', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500, { kalmanQ: 0.11 }));
        reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        reg.addSnapshot(makeProfile(3500, { kalmanQ: 0.10 }));  // delta = -0.01 exactly
        const r = reg.performRollup(RollupInterval.HOUR, 3000, 4000)!;
        expect(r.adr.summary).toContain('stable');
    });

    it('deltaMetrics includes kalmanQ_delta on second rollup', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500, { kalmanQ: 0.10 }));
        reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        reg.addSnapshot(makeProfile(3500, { kalmanQ: 0.25 }));
        const r = reg.performRollup(RollupInterval.HOUR, 3000, 4000)!;
        expect(r.adr.deltaMetrics['kalmanQ_delta']).toBeCloseTo(0.15);
    });

    it('deltaMetrics includes kalmanR_delta on second rollup', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500, { kalmanR: 0.01 }));
        reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        reg.addSnapshot(makeProfile(3500, { kalmanR: 0.05 }));
        const r = reg.performRollup(RollupInterval.HOUR, 3000, 4000)!;
        expect(r.adr.deltaMetrics['kalmanR_delta']).toBeCloseTo(0.04);
    });

    it('adr.timestamp equals the endTime of the rollup', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        const r = reg.performRollup(RollupInterval.MINUTE, 1000, 2000)!;
        expect(r.adr.timestamp).toBe(2000);
    });
});

describe('TemporalTuningRegistry — getRollups boundary', () => {
    it('returns empty array for interval with no rollups', () => {
        const reg = new TemporalTuningRegistry();
        expect(reg.getRollups(RollupInterval.DECADE)).toEqual([]);
    });

    it('different intervals have independent rollup buckets', () => {
        const reg = new TemporalTuningRegistry();
        reg.addSnapshot(makeProfile(1500));
        reg.performRollup(RollupInterval.HOUR, 1000, 2000);
        expect(reg.getRollups(RollupInterval.DAY)).toHaveLength(0);
        expect(reg.getRollups(RollupInterval.HOUR)).toHaveLength(1);
    });
});
