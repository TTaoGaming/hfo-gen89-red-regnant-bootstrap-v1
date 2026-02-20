/**
 * Omega v13: Behavioral Predictive Layer
 * 
 * This module implements a Genetic Algorithm that evolves both the predictive
 * parameters (Kalman/Havok) AND the feature descriptors (the MAP-Elites axes)
 * to perform Design Space Exploration (DSE) towards user intent.
 */

export interface Point3D {
    x: number;
    y: number;
    z: number;
    timestamp: number;
}

export interface Genotype {
    // Predictive Parameters (The Solution)
    kalmanQ: number; // Process noise covariance
    kalmanR: number; // Measurement noise covariance
    
    // Hyper-Heuristic Parameters (The Axes)
    // These represent weights for different feature extraction functions
    axis1WeightVelocity: number;
    axis1WeightFrequency: number;
    axis2WeightCurvature: number;
    axis2WeightAmplitude: number;

    // MAP-Elites specific
    cellId?: string;
    fitness?: number;
}

export interface UserTuningProfile {
    version: string;
    userIdHash: string; // Anonymized identifier
    lastUpdated: number;
    repertoire: Genotype[]; // The MAP-Elites grid/population
}

export class BehavioralPredictiveLayer {
    private populationSize: number;
    private mutationRate: number;
    private population: Genotype[];
    private worker: Worker | null = null;
    private isEvolving: boolean = false;
    private predictionBuffer: Float32Array | null = null;

    constructor(populationSize: number = 50, mutationRate: number = 0.1) {
        this.populationSize = populationSize;
        this.mutationRate = mutationRate;
        this.population = this.initializePopulation();
        this.initWorker();
    }

    private initWorker() {
        if (typeof Worker !== 'undefined') {
            // In a real environment, this would be a bundled worker file
            // For Jest tests, we might need to mock this or use a specific loader
            try {
                this.worker = new Worker('./dist/behavioral_predictive_worker.js');
                // The message listener is now handled per-call in evolveAsync
            } catch (e) {
                console.warn('Web Worker not supported or failed to load, falling back to synchronous evolution', e);
            }
        }
    }

    public terminate() {
        if (this.worker) {
            this.worker.terminate();
            this.worker = null;
        }
    }

    private initializePopulation(): Genotype[] {
        const pop: Genotype[] = [];
        for (let i = 0; i < this.populationSize; i++) {
            pop.push({
                kalmanQ: Math.random() * 0.1,
                kalmanR: Math.random() * 10,
                axis1WeightVelocity: Math.random(),
                axis1WeightFrequency: Math.random(),
                axis2WeightCurvature: Math.random(),
                axis2WeightAmplitude: Math.random()
            });
        }
        return pop;
    }

    /**
     * Simulates a simple 1D predictive filter for demonstration purposes.
     * In the full system, this would be the actual Kalman/Havok physics engine.
     * Refactored to use Float32Array to prevent GC churn (T-OMEGA-002).
     */
    public simulatePrediction(data: Point3D[], genotype: Genotype): Float32Array {
        if (!this.predictionBuffer || this.predictionBuffer.length !== data.length) {
            this.predictionBuffer = new Float32Array(data.length);
        }

        let estimate = data[0].x;
        let errorCovariance = 1.0;

        for (let i = 0; i < data.length; i++) {
            // 1. Predict (simplified)
            const predictedEstimate = estimate;
            const predictedErrorCovariance = errorCovariance + genotype.kalmanQ;

            // 2. Update
            const kalmanGain = predictedErrorCovariance / (predictedErrorCovariance + genotype.kalmanR);
            estimate = predictedEstimate + kalmanGain * (data[i].x - predictedEstimate);
            errorCovariance = (1 - kalmanGain) * predictedErrorCovariance;

            this.predictionBuffer[i] = estimate;
        }
        return this.predictionBuffer;
    }

    /**
     * Calculates the Mean Squared Error between the prediction and the ground truth.
     */
    public calculateFitness(predictions: Float32Array, groundTruth: Point3D[]): number {
        if (predictions.length !== groundTruth.length) return Infinity;

        let mse = 0;
        for (let i = 0; i < predictions.length; i++) {
            const dx = predictions[i] - groundTruth[i].x;
            mse += dx * dx;
        }
        return mse / predictions.length;
    }

    /**
     * Generates a delayed "Ground Truth" using a moving average (Shadow Tracker).
     * This solves the Ground Truth Paradox (T-OMEGA-003).
     */
    private generateShadowTracker(noisyData: Point3D[], windowSize: number = 5): Point3D[] {
        const shadowTruth: Point3D[] = [];
        for (let i = 0; i < noisyData.length; i++) {
            let sumX = 0;
            let count = 0;
            for (let j = Math.max(0, i - windowSize); j <= i; j++) {
                sumX += noisyData[j].x;
                count++;
            }
            shadowTruth.push({
                x: sumX / count,
                y: noisyData[i].y,
                z: noisyData[i].z,
                timestamp: noisyData[i].timestamp
            });
        }
        return shadowTruth;
    }

    /**
     * Evolves the population asynchronously using a Web Worker (T-OMEGA-001).
     */
    public async evolveAsync(noisyData: Point3D[], groundTruthData?: Point3D[]): Promise<void> {
        if (this.isEvolving) return; // Prevent overlapping evolutions

        // T-OMEGA-003: Use Shadow Tracker if ground truth is not provided
        const truthData = groundTruthData || this.generateShadowTracker(noisyData);

        if (this.worker) {
            this.isEvolving = true;
            
            // Extract x values into TypedArrays for efficient transfer
            const noisyX = new Float32Array(noisyData.length);
            const truthX = new Float32Array(truthData.length);
            for (let i = 0; i < noisyData.length; i++) {
                noisyX[i] = noisyData[i].x;
                truthX[i] = truthData[i].x;
            }

            return new Promise((resolve) => {
                const onMessage = (event: MessageEvent) => {
                    if (event.data.type === 'EVOLVED') {
                        this.population = event.data.newPopulation;
                        this.worker?.removeEventListener('message', onMessage);
                        this.isEvolving = false;
                        resolve();
                    }
                };
                this.worker?.addEventListener('message', onMessage);
                
                this.worker?.postMessage({
                    type: 'EVOLVE',
                    noisyData: noisyX,
                    groundTruthData: truthX,
                    population: this.population,
                    populationSize: this.populationSize,
                    mutationRate: this.mutationRate
                });
            });
        } else {
            // Fallback to synchronous if worker is not available
            this.evolve(noisyData, truthData);
        }
    }

private getCellId(genotype: Genotype): string {
        const bin1 = Math.floor(genotype.axis1WeightVelocity * 10);
        const bin2 = Math.floor(genotype.axis2WeightCurvature * 10);
        return `${bin1}_${bin2}`;
    }

    /**
     * Evolves the population for one generation based on the historical ring buffer data.
     * (Synchronous fallback)
     */
    public evolve(noisyData: Point3D[], groundTruthData?: Point3D[]): void {
        const truthData = groundTruthData || this.generateShadowTracker(noisyData);
        
        // T-OMEGA-004: True MAP-Elites Grid Implementation
        const grid = new Map<string, Genotype>();

        // 1. Evaluate Fitness and place in grid
        for (const genotype of this.population) {
            const predictions = this.simulatePrediction(noisyData, genotype);
            genotype.fitness = this.calculateFitness(predictions, truthData);
            genotype.cellId = this.getCellId(genotype);

            const existing = grid.get(genotype.cellId);
            if (!existing || (genotype.fitness < (existing.fitness || Infinity))) {
                grid.set(genotype.cellId, genotype);
            }
        }

        // 2. Extract elites from the grid
        const elites = Array.from(grid.values());

        // 3. Crossover and Mutate to fill the rest
        const newPopulation: Genotype[] = [...elites];

        while (newPopulation.length < this.populationSize) {
            const parentA = elites[Math.floor(Math.random() * elites.length)];
            const parentB = elites[Math.floor(Math.random() * elites.length)];

            const child: Genotype = {
                kalmanQ: (parentA.kalmanQ + parentB.kalmanQ) / 2,
                kalmanR: (parentA.kalmanR + parentB.kalmanR) / 2,
                axis1WeightVelocity: (parentA.axis1WeightVelocity + parentB.axis1WeightVelocity) / 2,
                axis1WeightFrequency: (parentA.axis1WeightFrequency + parentB.axis1WeightFrequency) / 2,
                axis2WeightCurvature: (parentA.axis2WeightCurvature + parentB.axis2WeightCurvature) / 2,
                axis2WeightAmplitude: (parentA.axis2WeightAmplitude + parentB.axis2WeightAmplitude) / 2
            };

            // Mutate
            if (Math.random() < this.mutationRate) child.kalmanQ += (Math.random() - 0.5) * 0.01;
            if (Math.random() < this.mutationRate) child.kalmanR += (Math.random() - 0.5) * 1.0;
            if (Math.random() < this.mutationRate) child.axis1WeightVelocity += (Math.random() - 0.5) * 0.2;
            if (Math.random() < this.mutationRate) child.axis1WeightFrequency += (Math.random() - 0.5) * 0.2;
            if (Math.random() < this.mutationRate) child.axis2WeightCurvature += (Math.random() - 0.5) * 0.2;
            if (Math.random() < this.mutationRate) child.axis2WeightAmplitude += (Math.random() - 0.5) * 0.2;

            // Ensure bounds
            child.kalmanQ = Math.max(0.0001, child.kalmanQ);
            child.kalmanR = Math.max(0.0001, child.kalmanR);
            child.axis1WeightVelocity = Math.max(0, Math.min(1, child.axis1WeightVelocity));
            child.axis2WeightCurvature = Math.max(0, Math.min(1, child.axis2WeightCurvature));

            newPopulation.push(child);
        }

        this.population = newPopulation;
    }

    public getBestGenotype(): Genotype {
        if (this.population.length === 0) return null as any;
        let best = this.population[0];
        for (let i = 1; i < this.population.length; i++) {
            if ((this.population[i].fitness ?? Infinity) < (best.fitness ?? Infinity)) {
                best = this.population[i];
            }
        }
        return best;
    }

    /**
     * Exports the current MAP-Elites repertoire as a privacy-safe JSON profile.
     * This is the user's "instrument tuning".
     */
    public exportProfile(userIdHash: string): UserTuningProfile {
        return {
            version: "1.0.0",
            userIdHash: userIdHash,
            lastUpdated: Date.now(),
            // Export the top 10% of the population as the repertoire
            repertoire: this.population.slice(0, Math.max(1, Math.floor(this.populationSize * 0.1)))
        };
    }

    /**
     * Imports a user's tuning profile, seeding the GA with their historical "wood grain".
     */
    public importProfile(profile: UserTuningProfile): void {
        if (!profile.repertoire || profile.repertoire.length === 0) return;

        // Seed the population with the imported repertoire
        const newPopulation: Genotype[] = [...profile.repertoire];
        
        // Fill the rest with mutated versions of the repertoire to maintain diversity
        while (newPopulation.length < this.populationSize) {
            const parent = profile.repertoire[Math.floor(Math.random() * profile.repertoire.length)];
            const child: Genotype = { ...parent };
            
            // Slight mutation for exploration
            child.kalmanQ += (Math.random() - 0.5) * 0.001;
            child.kalmanR += (Math.random() - 0.5) * 0.1;
            child.kalmanQ = Math.max(0.0001, child.kalmanQ);
            child.kalmanR = Math.max(0.0001, child.kalmanR);
            
            newPopulation.push(child);
        }
        
        this.population = newPopulation;
    }
}
