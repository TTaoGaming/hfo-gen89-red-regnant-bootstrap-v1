# Omega v13: Behavioral Predictive Layer (Hyper-Heuristic GA)

## 1. The Core Concept: Evolving the Axes

In a standard MAP-Elites implementation, the feature descriptors (the orthogonal axes of the grid) are hand-designed by the engineer (e.g., Speed vs. Jerk). 

However, human movement is highly idiosyncratic. What constitutes a "meaningful" behavioral dimension for one user might be irrelevant for another. 

To solve this, we introduce a **Hyper-Heuristic Genetic Algorithm**. Instead of just evolving the Kalman/Havok parameters (the *solutions*), we also evolve the *feature descriptors themselves* (the *axes*).

### The 3-Layer Architecture

1. **Noisy MediaPipe Input:** The raw, jittery spatial data from the camera.
2. **Partial Observability Best Estimate (Ground Truth):** An offline-smoothed, zero-lag trajectory representing the user's *intended* path.
3. **Behavioral Predictive Layer (GA):** A real-time predictive model (Kalman + Havok) tuned by a GA to match the Ground Truth.

## 2. Design Space Exploration (DSE) Towards User Intent

By evolving the axes, the system performs Design Space Exploration (DSE) to discover the latent dimensions of the user's specific movement style. 

For example, the GA might discover that for User A, the most predictive orthogonal axes are:
* **Axis 1:** Rhythmic Frequency (Hz)
* **Axis 2:** Amplitude of Oscillation

While for User B, the axes might be:
* **Axis 1:** Linear Velocity
* **Axis 2:** Curvature (Deviation from a straight line)

## 3. The Physics of Intent

Because human hands follow the laws of physics (mass, momentum, muscle elasticity), rhythmic and periodic movements are highly predictable once the underlying physical parameters are identified. 

If a user is making a periodic rapid movement (e.g., waving, scrubbing, or tapping to a beat), the GA can identify the frequency and amplitude, and the predictive layer can anticipate the hand's position *before* the noisy MediaPipe data even registers it.

## 4. Implementation Strategy

We will implement a `BehavioralPredictiveLayer` class that:
1. Takes a stream of historical data (the ring buffer).
2. Uses a GA to evolve both the predictive parameters (Kalman Q/R) and the feature extraction functions (the axes).
3. Evaluates fitness based on the Mean Squared Error (MSE) against a smoothed "intended" path.

We will test this with synthetic rhythmic data (e.g., a sine wave with added Gaussian noise) to prove that the GA can lock onto the underlying frequency and predict future states.

## 5. The Instrument Wood Grain (Privacy-Safe JSON Profiles)

The ultimate goal of this system is to create a spatial OS that feels like a finely tuned instrument, unique to each user. 

As the user interacts with the system, the `BehavioralPredictiveLayer` continuously evolves their MAP-Elites repertoire. This repertoire is periodically serialized into a **Privacy-Safe JSON Configuration File** (`UserTuningProfile`).

### Why it's Privacy-Safe:
The JSON profile **never** contains raw spatial data, camera feeds, or identifiable movement recordings. It only contains the *evolved mathematical parameters* (the Genotypes):
* Kalman $Q$ and $R$ matrices.
* Havok physics coefficients (friction, mass).
* The hyper-heuristic axis weights.

### The "Wood Grain" Effect:
When a user logs into a new device, their JSON profile is imported. The system instantly adopts their unique "wood grain." If they play on someone else's setup, it will feel "off"—not broken, but noticeably tuned for a different set of hands, just like playing someone else's guitar.

This ensures that every child gets a spatial OS that grows with them, learning their unique rhythms and adapting to their physical development over time.
