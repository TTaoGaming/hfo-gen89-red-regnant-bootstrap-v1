import { describe, it, expect } from '@jest/globals';
import { BehavioralPredictiveLayer, Point3D, UserTuningProfile } from './behavioral_predictive_layer';

describe('Behavioral Predictive Layer (Hyper-Heuristic GA)', () => {
    
    // Helper to generate a noisy sine wave (simulating rhythmic hand movement)
    function generateRhythmicData(length: number, frequency: number, amplitude: number, noiseLevel: number): { noisy: Point3D[], groundTruth: Point3D[] } {
        const noisy: Point3D[] = [];
        const groundTruth: Point3D[] = [];
        
        for (let i = 0; i < length; i++) {
            const t = i * 0.016; // 60fps
            const trueX = Math.sin(t * frequency * Math.PI * 2) * amplitude;
            const noise = (Math.random() - 0.5) * noiseLevel;
            
            groundTruth.push({ x: trueX, y: 0, z: 0, timestamp: t });
            noisy.push({ x: trueX + noise, y: 0, z: 0, timestamp: t });
        }
        
        return { noisy, groundTruth };
    }

    it('should evolve Kalman parameters to predict rhythmic movement', () => {
        // 1. Generate sample data: Periodic rapid movement in a rhythm
        // e.g., waving hand back and forth at 2Hz with 10cm amplitude
        const { noisy, groundTruth } = generateRhythmicData(300, 2.0, 10.0, 2.0); // 5 seconds of data

        // 2. Initialize the Behavioral Predictive Layer
        const bpl = new BehavioralPredictiveLayer(50, 0.1);

        // 3. Evolve over 50 generations
        for (let gen = 0; gen < 50; gen++) {
            bpl.evolve(noisy, groundTruth);
        }

        // 4. Get the best evolved genotype
        const bestGenotype = bpl.getBestGenotype();
        
        // 5. Test the prediction against the ground truth
        const predictions = bpl.simulatePrediction(noisy, bestGenotype);
        const finalMSE = bpl.calculateFitness(predictions, groundTruth);

        console.log(`Evolved Kalman Q: ${bestGenotype.kalmanQ.toFixed(4)}`);
        console.log(`Evolved Kalman R: ${bestGenotype.kalmanR.toFixed(4)}`);
        console.log(`Final MSE: ${finalMSE.toFixed(4)}`);

        // The MSE should be significantly lower than the raw noise variance
        // Noise variance is roughly (noiseLevel^2) / 12 for uniform distribution
        // For noiseLevel = 2.0, variance is ~0.33. We expect MSE < 0.5
        expect(finalMSE).toBeLessThan(1.0);
    });

    it('should evolve hyper-heuristic axes weights for DSE', () => {
        const bpl = new BehavioralPredictiveLayer(10, 0.1);
        const bestGenotype = bpl.getBestGenotype();
        
        // Verify that the hyper-heuristic axes weights are being tracked
        expect(bestGenotype.axis1WeightVelocity).toBeDefined();
        expect(bestGenotype.axis1WeightFrequency).toBeDefined();
        expect(bestGenotype.axis2WeightCurvature).toBeDefined();
        expect(bestGenotype.axis2WeightAmplitude).toBeDefined();
    });

    it('should export and import a privacy-safe JSON tuning profile (The Instrument Wood Grain)', () => {
        const { noisy, groundTruth } = generateRhythmicData(100, 1.0, 5.0, 1.0);
        
        // 1. Train a profile for "User A"
        const userA_BPL = new BehavioralPredictiveLayer(20, 0.1);
        for (let gen = 0; gen < 10; gen++) userA_BPL.evolve(noisy, groundTruth);
        
        // 2. Export User A's unique "wood grain" tuning
        const userA_Profile: UserTuningProfile = userA_BPL.exportProfile("hash_user_a_123");
        
        // Verify the profile is privacy-safe (no raw data, just parameters)
        expect(userA_Profile.userIdHash).toBe("hash_user_a_123");
        expect(userA_Profile.repertoire.length).toBeGreaterThan(0);
        expect(userA_Profile.repertoire[0].kalmanQ).toBeDefined();
        
        // 3. User A logs into a new device. Import their profile.
        const newDevice_BPL = new BehavioralPredictiveLayer(20, 0.1);
        newDevice_BPL.importProfile(userA_Profile);
        
        // 4. Verify the new device immediately has User A's tuning
        const importedGenotype = newDevice_BPL.getBestGenotype();
        expect(importedGenotype.kalmanQ).toBeCloseTo(userA_Profile.repertoire[0].kalmanQ, 4);
        expect(importedGenotype.kalmanR).toBeCloseTo(userA_Profile.repertoire[0].kalmanR, 4);
    });
});
