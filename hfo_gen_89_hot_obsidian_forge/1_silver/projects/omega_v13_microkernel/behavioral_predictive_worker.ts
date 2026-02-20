import { Genotype, Point3D } from './behavioral_predictive_layer';

// The worker needs to be able to run simulatePrediction and calculateFitness
// We'll duplicate the logic here or import it if the bundler supports it.
// For simplicity and to avoid bundler issues with workers, we'll implement the core logic here.

export interface WorkerMessage {
    type: 'EVOLVE';
    noisyData: Float32Array; // x values
    groundTruthData: Float32Array; // x values
    population: Genotype[];
    populationSize: number;
    mutationRate: number;
}

export interface WorkerResponse {
    type: 'EVOLVED';
    newPopulation: Genotype[];
}

// Pre-allocated array for predictions to avoid GC churn
let predictionBuffer: Float32Array | null = null;

function simulatePrediction(data: Float32Array, genotype: Genotype): Float32Array {
    if (!predictionBuffer || predictionBuffer.length !== data.length) {
        predictionBuffer = new Float32Array(data.length);
    }

    let estimate = data[0];
    let errorCovariance = 1.0;

    for (let i = 0; i < data.length; i++) {
        let predictedEstimate = estimate;
        let predictedErrorCovariance = errorCovariance + genotype.kalmanQ;

        const kalmanGain = predictedErrorCovariance / (predictedErrorCovariance + genotype.kalmanR);
        estimate = predictedEstimate + kalmanGain * (data[i] - predictedEstimate);
        errorCovariance = (1 - kalmanGain) * predictedErrorCovariance;

        predictionBuffer[i] = estimate;
    }
    return predictionBuffer;
}

function calculateFitness(predictions: Float32Array, groundTruth: Float32Array): number {
    if (predictions.length !== groundTruth.length) return Infinity;

    let mse = 0;
    for (let i = 0; i < predictions.length; i++) {
        const dx = predictions[i] - groundTruth[i];
        mse += dx * dx;
    }
    return mse / predictions.length;
}

function getCellId(genotype: Genotype): string {
    // Simple 2D grid based on two axes, discretized into 10x10 bins
    const bin1 = Math.floor(genotype.axis1WeightVelocity * 10);
    const bin2 = Math.floor(genotype.axis2WeightCurvature * 10);
    return `${bin1}_${bin2}`;
}

self.onmessage = (event: MessageEvent<WorkerMessage>) => {
    if (event.data.type === 'EVOLVE') {
        const { noisyData, groundTruthData, population, populationSize, mutationRate } = event.data;

        // T-OMEGA-004: True MAP-Elites Grid Implementation
        const grid = new Map<string, Genotype>();

        // 1. Evaluate Fitness and place in grid
        for (const genotype of population) {
            const predictions = simulatePrediction(noisyData, genotype);
            genotype.fitness = calculateFitness(predictions, groundTruthData);
            genotype.cellId = getCellId(genotype);

            const existing = grid.get(genotype.cellId);
            if (!existing || (genotype.fitness < (existing.fitness || Infinity))) {
                grid.set(genotype.cellId, genotype);
            }
        }

        // 2. Extract elites from the grid
        const elites = Array.from(grid.values());

        // 3. Crossover and Mutate to fill the rest of the population
        const newPopulation: Genotype[] = [...elites];

        while (newPopulation.length < populationSize) {
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
            if (Math.random() < mutationRate) child.kalmanQ += (Math.random() - 0.5) * 0.01;
            if (Math.random() < mutationRate) child.kalmanR += (Math.random() - 0.5) * 1.0;
            if (Math.random() < mutationRate) child.axis1WeightVelocity += (Math.random() - 0.5) * 0.2;
            if (Math.random() < mutationRate) child.axis1WeightFrequency += (Math.random() - 0.5) * 0.2;
            if (Math.random() < mutationRate) child.axis2WeightCurvature += (Math.random() - 0.5) * 0.2;
            if (Math.random() < mutationRate) child.axis2WeightAmplitude += (Math.random() - 0.5) * 0.2;

            // Ensure bounds
            child.kalmanQ = Math.max(0.0001, child.kalmanQ);
            child.kalmanR = Math.max(0.0001, child.kalmanR);
            child.axis1WeightVelocity = Math.max(0, Math.min(1, child.axis1WeightVelocity));
            child.axis2WeightCurvature = Math.max(0, Math.min(1, child.axis2WeightCurvature));

            newPopulation.push(child);
        }

        const response: WorkerResponse = {
            type: 'EVOLVED',
            newPopulation
        };

        self.postMessage(response);
    }
};
