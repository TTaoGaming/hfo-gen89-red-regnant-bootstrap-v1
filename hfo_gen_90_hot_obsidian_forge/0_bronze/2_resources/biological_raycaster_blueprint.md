# CORE-2: Scale-Invariant Biological Raycasting Blueprint

**TARGET:** Host Context (MediaPipe Gesture Recognition)
**OBJECTIVE:** Robust, depth-independent pinch detection (`COMMIT_POINTER`) using 3D hand landmarks.

## 1. The Problem: Depth Ambiguity
Absolute pixel distance between fingers is useless for thresholding. A 2-inch pinch at 2 feet from the camera yields the same 2D pixel distance as a 10-inch gap at 10 feet. We must use a scale-invariant ratio based on the user's own anatomy.

## 2. The Solution: Anatomical Pinch-Ruler
We calculate the 3D Euclidean distance between the thumb tip and index finger tip, and normalize it by dividing by a stable anatomical reference distance: the distance between the wrist and the index finger MCP (knuckle).

### Key MediaPipe Landmarks:
*   `WRIST` = 0
*   `THUMB_TIP` = 4
*   `INDEX_FINGER_MCP` = 5
*   `INDEX_FINGER_TIP` = 8

## 3. Mathematical Implementation (TypeScript)

```typescript
interface Landmark {
  x: number;
  y: number;
  z: number;
}

/**
 * Calculates the 3D Euclidean distance between two MediaPipe landmarks.
 */
function calculateEuclideanDistance3D(p1: Landmark, p2: Landmark): number {
  const dx = p1.x - p2.x;
  const dy = p1.y - p2.y;
  const dz = p1.z - p2.z;
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

/**
 * Determines if a pinch gesture is active using a scale-invariant anatomical ratio.
 * 
 * @param landmarks Array of 21 MediaPipe hand landmarks.
 * @param pinchThreshold The ratio threshold below which a pinch is registered (e.g., 0.15).
 * @returns boolean indicating if the pinch is active.
 */
function isPinchActive(landmarks: Landmark[], pinchThreshold: number = 0.15): boolean {
  if (!landmarks || landmarks.length < 21) return false;

  const wrist = landmarks[0];
  const thumbTip = landmarks[4];
  const indexMcp = landmarks[5];
  const indexTip = landmarks[8];

  // 1. Calculate the absolute pinch distance
  const pinchDistance = calculateEuclideanDistance3D(thumbTip, indexTip);

  // 2. Calculate the anatomical reference distance (Wrist to Index MCP)
  // This distance scales linearly with the hand's distance from the camera.
  const referenceDistance = calculateEuclideanDistance3D(wrist, indexMcp);

  // Prevent division by zero in edge cases
  if (referenceDistance === 0) return false;

  // 3. Calculate the scale-invariant ratio
  const pinchRatio = pinchDistance / referenceDistance;

  // 4. Evaluate against threshold
  return pinchRatio < pinchThreshold;
}
```

## 4. Calibration & Thresholding
*   **Open Hand Ratio:** Typically > 0.8
*   **Closed Pinch Ratio:** Typically < 0.1
*   **Recommended `COMMIT_POINTER` Threshold:** `0.15` (Requires empirical tuning per camera FOV, but remains stable across depths).
