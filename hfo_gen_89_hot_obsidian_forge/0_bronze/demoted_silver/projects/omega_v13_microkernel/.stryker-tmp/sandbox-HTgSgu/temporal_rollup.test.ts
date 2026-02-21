// @ts-nocheck
import { describe, it, expect } from '@jest/globals';
import { TemporalTuningRegistry, RollupInterval } from './temporal_rollup';
import { UserTuningProfile } from './behavioral_predictive_layer';

describe('Temporal Tuning Registry & Procedural ADRs', () => {
    
    const createMockProfile = (timestamp: number, q: number, r: number): UserTuningProfile => ({
        version: "1.0.0",
        userIdHash: "user_123",
        lastUpdated: timestamp,
        repertoire: [{
            kalmanQ: q, kalmanR: r,
            axis1WeightVelocity: 0.5, axis1WeightFrequency: 0.5,
            axis2WeightCurvature: 0.5, axis2WeightAmplitude: 0.5
        }]
    });

    it('should aggregate snapshots into a temporal rollup and generate a procedural ADR', () => {
        const registry = new TemporalTuningRegistry();
        const baseTime = 1000000;

        // Simulate 3 snapshots over a minute where the user gets progressively more erratic (higher Q)
        registry.addSnapshot(createMockProfile(baseTime + 10000, 0.05, 0.01));
        registry.addSnapshot(createMockProfile(baseTime + 30000, 0.07, 0.01));
        registry.addSnapshot(createMockProfile(baseTime + 50000, 0.09, 0.01));

        // Perform a MINUTE rollup
        const rollup1 = registry.performRollup(RollupInterval.MINUTE, baseTime, baseTime + 60000);
        
        expect(rollup1).toBeDefined();
        expect(rollup1?.profile.repertoire[0].kalmanQ).toBeCloseTo(0.07, 4); // Average of 0.05, 0.07, 0.09
        expect(rollup1?.adr.summary).toContain("Initial MINUTE tuning established");

        // Simulate the next minute where the user gets even MORE erratic
        registry.addSnapshot(createMockProfile(baseTime + 70000, 0.12, 0.01));
        registry.addSnapshot(createMockProfile(baseTime + 90000, 0.14, 0.01));

        // Perform the second MINUTE rollup
        const rollup2 = registry.performRollup(RollupInterval.MINUTE, baseTime + 60000, baseTime + 120000);
        
        expect(rollup2).toBeDefined();
        expect(rollup2?.profile.repertoire[0].kalmanQ).toBeCloseTo(0.13, 4); // Average of 0.12, 0.14
        
        // The ADR should procedurally note the increase in Q
        expect(rollup2?.adr.summary).toContain("User movement became more dynamic/erratic");
        expect(rollup2?.adr.deltaMetrics.kalmanQ_delta).toBeCloseTo(0.06, 4); // 0.13 - 0.07
    });
});