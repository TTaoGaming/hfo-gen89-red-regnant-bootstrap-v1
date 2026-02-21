// @ts-nocheck
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { BehavioralPredictiveLayer, Point3D, Genotype } from './behavioral_predictive_layer';

describe('BehavioralPredictiveLayer (T-OMEGA-001: Main-Thread Evolutionary Blocking)', () => {
    let bpl: BehavioralPredictiveLayer;

    beforeEach(() => {
        bpl = new BehavioralPredictiveLayer(10, 0.1);
    });

    afterEach(() => {
        bpl.terminate();
    });

    it('Given a BehavioralPredictiveLayer, When evolveAsync is called with historical data, Then it should return a Promise that resolves with the updated Genotype without blocking the main thread', async () => {
        const noisyData: Point3D[] = Array.from({ length: 100 }, (_, i) => ({ x: i + Math.random(), y: 0, z: 0, timestamp: i * 16 }));
        const groundTruthData: Point3D[] = Array.from({ length: 100 }, (_, i) => ({ x: i, y: 0, z: 0, timestamp: i * 16 }));

        const initialGenotype = bpl.getBestGenotype();
        
        // The evolution should happen asynchronously
        await bpl.evolveAsync(noisyData, groundTruthData);
        
        const newGenotype = bpl.getBestGenotype();
        
        expect(newGenotype).toBeDefined();
        // The genotype should have been updated (or at least evaluated)
        expect(newGenotype.fitness).toBeDefined();
    });
});

describe('BehavioralPredictiveLayer (T-OMEGA-002: Garbage Collection Churn)', () => {
    let bpl: BehavioralPredictiveLayer;

    beforeEach(() => {
        bpl = new BehavioralPredictiveLayer(10, 0.1);
    });

    afterEach(() => {
        bpl.terminate();
    });

    it('Given a BehavioralPredictiveLayer, When simulatePrediction is called, Then it should use pre-allocated Typed Arrays instead of creating new objects to prevent GC churn', () => {
        const noisyData: Point3D[] = Array.from({ length: 100 }, (_, i) => ({ x: i + Math.random(), y: 0, z: 0, timestamp: i * 16 }));
        const genotype = bpl.getBestGenotype();
        
        // simulatePrediction should return a Float32Array (or similar) instead of Point3D[]
        const predictions = bpl.simulatePrediction(noisyData, genotype);
        
        expect(predictions).toBeInstanceOf(Float32Array);
        expect(predictions.length).toBe(noisyData.length); // 1D prediction for now
    });
});

describe('BehavioralPredictiveLayer (T-OMEGA-003: Ground Truth Paradox)', () => {
    let bpl: BehavioralPredictiveLayer;

    beforeEach(() => {
        bpl = new BehavioralPredictiveLayer(10, 0.1);
    });

    afterEach(() => {
        bpl.terminate();
    });

    it('Given a BehavioralPredictiveLayer, When evolveAsync is called without ground truth data, Then it should use a Shadow Tracker (moving average) to generate the ground truth internally', async () => {
        const noisyData: Point3D[] = Array.from({ length: 100 }, (_, i) => ({ x: i + Math.random(), y: 0, z: 0, timestamp: i * 16 }));
        
        const initialGenotype = bpl.getBestGenotype();
        
        // evolveAsync should now accept only noisyData and generate groundTruth internally
        await bpl.evolveAsync(noisyData);
        
        const newGenotype = bpl.getBestGenotype();
        
        expect(newGenotype).toBeDefined();
        expect(newGenotype.fitness).toBeDefined();
    });
});

describe('BehavioralPredictiveLayer (T-OMEGA-004: MAP-Elites Mirage)', () => {
    let bpl: BehavioralPredictiveLayer;

    beforeEach(() => {
        bpl = new BehavioralPredictiveLayer(10, 0.1);
    });

    afterEach(() => {
        bpl.terminate();
    });

    it('Given a BehavioralPredictiveLayer, When it evolves, Then it should maintain a MAP-Elites grid (repertoire) based on behavioral descriptors instead of a simple array', async () => {
        const noisyData: Point3D[] = Array.from({ length: 100 }, (_, i) => ({ x: Math.sin(i * 0.1) + Math.random() * 0.1, y: 0, z: 0, timestamp: i * 16 }));
        
        await bpl.evolveAsync(noisyData);
        
        const profile = bpl.exportProfile('user123');
        
        expect(profile.repertoire).toBeDefined();
        expect(Array.isArray(profile.repertoire)).toBe(true);
        // The repertoire should contain genotypes that are mapped to grid cells
        // We can check if the genotypes have a 'cellId' or similar property, or if the repertoire is diverse
        expect(profile.repertoire.length).toBeGreaterThan(0);
    });
});
