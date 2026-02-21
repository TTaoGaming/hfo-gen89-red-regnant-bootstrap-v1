// @ts-nocheck
import { UserTuningProfile, Genotype } from './behavioral_predictive_layer';

export enum RollupInterval {
    MINUTE = 'MINUTE',
    HOUR = 'HOUR',
    DAY = 'DAY',
    WEEK = 'WEEK',
    MONTH = 'MONTH',
    YEAR = 'YEAR',
    DECADE = 'DECADE'
}

export interface ProceduralADR {
    timestamp: number;
    interval: RollupInterval;
    summary: string;
    deltaMetrics: Record<string, number>;
}

export interface TemporalRollup {
    interval: RollupInterval;
    startTime: number;
    endTime: number;
    profile: UserTuningProfile;
    adr: ProceduralADR;
}

export class TemporalTuningRegistry {
    private snapshots: UserTuningProfile[] = [];
    private rollups: Map<RollupInterval, TemporalRollup[]> = new Map();

    constructor() {
        Object.values(RollupInterval).forEach(interval => {
            this.rollups.set(interval as RollupInterval, []);
        });
    }

    public addSnapshot(profile: UserTuningProfile): void {
        this.snapshots.push(profile);
    }

    public getSnapshots(): UserTuningProfile[] {
        return this.snapshots;
    }

    public getRollups(interval: RollupInterval): TemporalRollup[] {
        return this.rollups.get(interval) || [];
    }

    /**
     * Averages a list of profiles into a single representative profile for the time period.
     */
    private averageProfiles(profiles: UserTuningProfile[], newTimestamp: number): UserTuningProfile {
        if (profiles.length === 0) throw new Error("Cannot average empty profiles");
        
        const base = profiles[0];
        const avgGenotype: Genotype = {
            kalmanQ: 0, kalmanR: 0,
            axis1WeightVelocity: 0, axis1WeightFrequency: 0,
            axis2WeightCurvature: 0, axis2WeightAmplitude: 0
        };

        // Average the top elite from each profile for simplicity in this proof
        profiles.forEach(p => {
            const elite = p.repertoire[0];
            avgGenotype.kalmanQ += elite.kalmanQ;
            avgGenotype.kalmanR += elite.kalmanR;
            avgGenotype.axis1WeightVelocity += elite.axis1WeightVelocity;
            avgGenotype.axis1WeightFrequency += elite.axis1WeightFrequency;
            avgGenotype.axis2WeightCurvature += elite.axis2WeightCurvature;
            avgGenotype.axis2WeightAmplitude += elite.axis2WeightAmplitude;
        });

        const count = profiles.length;
        avgGenotype.kalmanQ /= count;
        avgGenotype.kalmanR /= count;
        avgGenotype.axis1WeightVelocity /= count;
        avgGenotype.axis1WeightFrequency /= count;
        avgGenotype.axis2WeightCurvature /= count;
        avgGenotype.axis2WeightAmplitude /= count;

        return {
            version: base.version,
            userIdHash: base.userIdHash,
            lastUpdated: newTimestamp,
            repertoire: [avgGenotype] // Storing the averaged elite
        };
    }

    /**
     * Procedurally generates an Architecture Decision Record (ADR) note based on the delta.
     */
    private generateProceduralADR(prev: UserTuningProfile | null, current: UserTuningProfile, interval: RollupInterval, timestamp: number): ProceduralADR {
        const currentElite = current.repertoire[0];
        const deltaMetrics: Record<string, number> = {};
        let summary = `Initial ${interval} tuning established.`;

        if (prev) {
            const prevElite = prev.repertoire[0];
            deltaMetrics.kalmanQ_delta = currentElite.kalmanQ - prevElite.kalmanQ;
            deltaMetrics.kalmanR_delta = currentElite.kalmanR - prevElite.kalmanR;

            if (deltaMetrics.kalmanQ_delta > 0.01) {
                summary = `User movement became more dynamic/erratic. Increased process noise (Q) by ${deltaMetrics.kalmanQ_delta.toFixed(4)} to adapt.`;
            } else if (deltaMetrics.kalmanQ_delta < -0.01) {
                summary = `User movement stabilized. Decreased process noise (Q) by ${Math.abs(deltaMetrics.kalmanQ_delta).toFixed(4)} for smoother tracking.`;
            } else {
                summary = `Tuning remained stable over the ${interval}.`;
            }
        }

        return {
            timestamp,
            interval,
            summary,
            deltaMetrics
        };
    }

    /**
     * Performs a rollup of snapshots within a time window.
     */
    public performRollup(interval: RollupInterval, startTime: number, endTime: number): TemporalRollup | null {
        const relevantSnapshots = this.snapshots.filter(s => s.lastUpdated >= startTime && s.lastUpdated <= endTime);
        if (relevantSnapshots.length === 0) return null;

        const averagedProfile = this.averageProfiles(relevantSnapshots, endTime);
        
        const existingRollups = this.rollups.get(interval) || [];
        const previousRollup = existingRollups.length > 0 ? existingRollups[existingRollups.length - 1].profile : null;

        const adr = this.generateProceduralADR(previousRollup, averagedProfile, interval, endTime);

        const rollup: TemporalRollup = {
            interval,
            startTime,
            endTime,
            profile: averagedProfile,
            adr
        };

        existingRollups.push(rollup);
        this.rollups.set(interval, existingRollups);

        return rollup;
    }
}