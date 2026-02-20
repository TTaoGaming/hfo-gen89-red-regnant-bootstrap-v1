---
schema_id: hfo.mosaic_microkernel_header.v3
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
bluf: "Step-by-step tutorial: wire MediaPipe hand landmarks through a biomechanical classifier and an Anti-Midas FSM to produce a working gesture-controlled dot cursor on a canvas. By the end you will have a functional pointer that fires pointer events, respects the IDLE→READY→COMMIT state graph, and coasts gracefully on hand loss."
primary_port: P2
secondary_ports: [P0, P1]
diataxis_type: tutorial
tags: [bronze, forge:hot, omega, v13, gesture, cursor, mediapipe, fsm, tutorial, anti-midas, canvas, pointer-events, leaky-bucket]
generated: "2026-02-20"
status: DRAFT — operator review required
related:
  - EXPLANATION_BIOMECHANICAL_GESTURE_HEURISTICS_OMEGA_V13.md
  - REFERENCE_GESTURE_FSM_ANTI_MIDAS_STATE_MACHINE_OMEGA_V13.md
  - HOWTO_TUNE_GESTURE_FSM_THRESHOLDS_OMEGA_V13.md
---

# Tutorial: Build a Gesture-Controlled Cursor from Scratch

> **What you will build:** A browser page with a webcam feed. Your extended index finger drives a dot cursor. Open palm arms the system. Pointing fires a `pointerdown` event. Lowering your hand disarms.
> 
> **What you will learn:** How the biomechanical sensor, the leaky-bucket FSM, and pointer event emission compose as independent layers with clean interfaces.
> 
> **Time:** ~90 minutes. No framework required — TypeScript and a `<canvas>` element.

---

## Before You Start

You need:
- Node.js with TypeScript (`npx tsc` works)
- A browser with webcam (Chrome recommended)
- The [MediaPipe Tasks Vision](https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision) package loaded via CDN or npm

You do NOT need:
- Any existing Omega v13 codebase
- BabylonJS (we use a plain 2D canvas)

---

## Part 1 — Understand the Three Layers Before Writing Code

Before touching any file, read this diagram. It is the architecture you will build in three discrete steps.

```
[Camera Frame]
    │
    ▼
┌──────────────────────────────────────────────┐
│  Layer 1: Biomechanical Sensor               │  ← p0_mediapipe-like
│  Input:  21 raw landmarks (x,y,z)            │
│  Output: { gesture: string, confidence: 0-1, │
│            x: number, y: number }            │
│  Memory: ZERO. Pure frame-by-frame function. │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  Layer 2: Intent FSM                         │  ← p2_hand_fsm-like
│  Input:  per-frame { gesture, confidence }    │
│  Output: GestureState (IDLE/READY/COMMIT/...)│
│  Memory: bucket counts + coast ticks         │
└──────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────┐
│  Layer 3: Cursor Emitter                     │  ← p2_cursor_2d-like
│  Input:  FSM state + cursor (x, y)           │
│  Output: DOM pointer events + canvas dot     │
│  Memory: previous state (for edge detection) │
└──────────────────────────────────────────────┘
```

**Key insight for this tutorial:** Each layer talks to the next through a simple typed object. You can test each layer independently. You can swap the sensor without touching the FSM. This is why the layers exist.

---

## Part 2 — Build Layer 1: The Biomechanical Sensor

Create `sensor.ts`.

### 2.1 Define the output type

```typescript
export interface RawHandData {
    gesture: 'open_palm' | 'pointer_up' | 'closed_fist' | 'none';
    confidence: number;  // 0.0–1.0 structural score
    x: number;           // normalised 0–1, left of screen = 0
    y: number;           // normalised 0–1, top = 0
}
```

### 2.2 Write the three utility functions

These are pure functions. Test them in isolation before wiring to MediaPipe.

```typescript
// Euclidean distance in 3D landmark space (z is depth estimate, less reliable)
function dist3(a: {x:number,y:number,z:number}, b: {x:number,y:number,z:number}): number {
    return Math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2);
}

// How curled is a finger? 0 = straight, 1 = fully curled
// mcp = metacarpal joint, pip = proximal interphalangeal, tip = fingertip
function fingerCurlScore(mcp: any, pip: any, tip: any): number {
    const extended = dist3(mcp, tip);
    const curled   = dist3(mcp, pip) + dist3(pip, tip);
    return Math.max(0, Math.min(1, 1 - (extended / (curled || 1))));
}

function clamp01(v: number): number {
    return Math.max(0, Math.min(1, v));
}
```

**Checkpoint:** Open the browser console and test `fingerCurlScore` manually with dummy landmark objects before proceeding. Knowing these work saves debugging later.

### 2.3 Write `classifyHand`

This is the entire biomechanical heuristic. It takes 21 landmarks and returns `RawHandData`.

```typescript
export function classifyHand(landmarks: any[], handIndex: number): RawHandData {
    // Structural scores
    const indexCurl  = fingerCurlScore(landmarks[5],  landmarks[6],  landmarks[8]);
    const middleCurl = fingerCurlScore(landmarks[9],  landmarks[10], landmarks[12]);
    const ringCurl   = fingerCurlScore(landmarks[13], landmarks[14], landmarks[16]);
    const pinkyCurl  = fingerCurlScore(landmarks[17], landmarks[18], landmarks[20]);

    const palmWidth   = dist3(landmarks[5], landmarks[17]) || 0.001;
    const thumbTucked = clamp01((2.0 - dist3(landmarks[4], landmarks[9]) / palmWidth) / 1.0);
    const pointerLock = clamp01((1.5 - dist3(landmarks[4], landmarks[10]) / palmWidth) / 1.0);

    // Gesture scores
    const fistScore    = (indexCurl + middleCurl + ringCurl + pinkyCurl) * 0.2 + thumbTucked * 0.2;
    const palmScore    = (1-indexCurl + 1-middleCurl + 1-ringCurl + 1-pinkyCurl) * 0.2 + (1-thumbTucked) * 0.2;
    const pointerScore = (1-indexCurl)*0.35 + middleCurl*0.15 + ringCurl*0.1 + pinkyCurl*0.1 + pointerLock*0.3;

    // Winner-takes-all above threshold
    let gesture: RawHandData['gesture'] = 'none';
    let confidence = 0;
    if (palmScore    > 0.5 && palmScore    > confidence) { gesture = 'open_palm';    confidence = palmScore; }
    if (pointerScore > 0.5 && pointerScore > confidence) { gesture = 'pointer_up';   confidence = pointerScore; }
    if (fistScore    > 0.5 && fistScore    > confidence) { gesture = 'closed_fist';  confidence = fistScore; }

    // Mirror X (webcam is front-facing) and normalise cursor position
    const tip = landmarks[8];
    return {
        gesture, confidence,
        x: 1.0 - tip.x,
        y: tip.y,
    };
}
```

**Why mirror X?** A webcam outputs a selfie-view by default. If you move your hand right, the landmark x coordinate *decreases*. Mirroring makes the cursor move in the direction your hand moves.

---

## Part 3 — Build Layer 2: The Intent FSM

Create `gesture_fsm.ts`. Copy the full GestureFSM class from the Reference document or from the implementation. Do not modify it yet.

### 3.1 Unit-test the state machine before wiring it

Paste this minimal test into your browser console (or a test file):

```typescript
const fsm = new GestureFSM();
console.assert(fsm.state === 'IDLE', 'starts IDLE');

// 6 frames of open_palm at high confidence — should arm
for (let i = 0; i < 6; i++) fsm.processFrame('open_palm', 0.75);
console.assert(fsm.state === 'READY', `arm test failed — got ${fsm.state}`);

// 4 frames of pointer_up — should commit
for (let i = 0; i < 4; i++) fsm.processFrame('pointer_up', 0.75);
console.assert(fsm.state === 'COMMIT_POINTER', `commit test failed — got ${fsm.state}`);

// 2 frames of open_palm — should NOT break commit (anti-thrash)
fsm.processFrame('open_palm', 0.75);
fsm.processFrame('open_palm', 0.75);
console.assert(fsm.state === 'COMMIT_POINTER', `anti-thrash test failed — got ${fsm.state}`);

console.log('✓ All FSM unit tests passed');
```

**Do not proceed until all assertions pass.** Fixing FSM bugs here takes 5 minutes. Fixing them after wiring to MediaPipe takes 45.

---

## Part 4 — Build Layer 3: Cursor Emitter

Create `cursor.ts`.

### 4.1 Canvas setup

In your HTML, add:

```html
<video id="webcam" width="640" height="480" autoplay playsinline style="display:none"></video>
<canvas id="overlay" width="640" height="480" style="cursor:none"></canvas>
```

The video element captures the camera feed. The canvas shows the cursor dot.

### 4.2 The emitter class

```typescript
export class CursorEmitter {
    private canvas: HTMLCanvasElement;
    private ctx: CanvasRenderingContext2D;
    private prevState = 'IDLE';

    constructor(canvas: HTMLCanvasElement) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d')!;
    }

    // Called every frame with FSM state and normalised cursor position
    update(fsmState: string, normX: number, normY: number) {
        const screenX = normX * this.canvas.width;
        const screenY = normY * this.canvas.height;

        // Edge detection: fire pointer events only on state change
        if (fsmState === 'COMMIT_POINTER' && this.prevState !== 'COMMIT_POINTER') {
            this.canvas.dispatchEvent(new PointerEvent('pointerdown', {
                clientX: screenX, clientY: screenY, bubbles: true
            }));
        }
        if (this.prevState === 'COMMIT_POINTER' && fsmState !== 'COMMIT_POINTER' && fsmState !== 'COMMIT_COAST') {
            this.canvas.dispatchEvent(new PointerEvent('pointerup', {
                clientX: screenX, clientY: screenY, bubbles: true
            }));
        }
        this.prevState = fsmState;

        // Draw cursor
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        if (fsmState === 'IDLE' || fsmState === 'IDLE_COAST') return; // No cursor when idle

        const colour = fsmState.startsWith('COMMIT') ? '#FF4444' :
                       fsmState.startsWith('READY')  ? '#44FF44' : '#AAAAAA';
        this.ctx.beginPath();
        this.ctx.arc(screenX, screenY, 12, 0, Math.PI * 2);
        this.ctx.fillStyle = colour;
        this.ctx.fill();
    }
}
```

**Colour legend:**
- Green dot = `READY` (armed, cursor tracking)
- Red dot = `COMMIT_POINTER` (active click)
- No dot = `IDLE`

---

## Part 5 — Wire Everything Together

Create `main.ts`. This is the only file that knows about all three layers.

```typescript
import { classifyHand } from './sensor';
import { GestureFSM } from './gesture_fsm';
import { CursorEmitter } from './cursor';
import { HandLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

async function main() {
    // 1. Start webcam
    const video = document.getElementById('webcam') as HTMLVideoElement;
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    await new Promise(r => video.addEventListener('loadeddata', r, { once: true }));

    // 2. Load MediaPipe
    const vision = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm'
    );
    const detector = await HandLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task' },
        numHands: 1,
        runningMode: 'VIDEO',
    });

    // 3. Create one FSM per hand (here: one hand only)
    const fsm = new GestureFSM();
    const cursor = new CursorEmitter(document.getElementById('overlay') as HTMLCanvasElement);

    // 4. Main loop
    function tick() {
        const result = detector.detectForVideo(video, performance.now());

        if (result.landmarks.length > 0) {
            const raw = classifyHand(result.landmarks[0], 0);
            fsm.processFrame(raw.gesture, raw.confidence, raw.x, raw.y);
            cursor.update(fsm.state, raw.x, raw.y);
        } else {
            fsm.processFrame('none', 0); // signal loss
            cursor.update(fsm.state, -1, -1);
        }

        requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

main();
```

---

## Part 6 — Verify the Three Core Behaviours

Before using the cursor for anything, verify these manually:

### Test A — Anti-Midas: Cannot click from IDLE
1. Start the page. Make a fist (IDLE state — no dot).
2. Without opening your hand, extend only your index finger.
3. **Expected:** The dot does NOT appear. No pointerdown fires.

### Test B — Arm → Click
1. Open your hand fully (READY — green dot appears).
2. Extend index finger while keeping thumb braced.
3. **Expected:** Dot turns red. A `pointerdown` event fires.

### Test C — Coast: Short occlusion does not break draw
1. Get into COMMIT_POINTER (red dot).
2. Briefly put your other hand in front of the camera for ~1 second.
3. **Expected:** Dot may flicker or go to coast-red, but DOES NOT fire `pointerup` until after the coast timeout, and recovers to COMMIT on hand re-detection.

---

## What You Have Built

By completing this tutorial, you have a three-layer gesture cursor that:

1. **Reads biomechanical structural state** — not just ML shape confidence
2. **Accumulates intent** — transitions only when gestures are sustained
3. **Enforces the strict state graph** — Anti-Midas is a structural property, not a runtime check
4. **Degrades gracefully** — short occlusion does not break ongoing interactions

This is the foundation layer. From here you can add:
- 1€ filter smoothing on landmark positions (eliminate jitter)
- Overscan transform in P7 orchestrator (extend cursor to screen edges)
- BabylonJS hand skeleton visualisation overlay
- Multi-hand support (instantiate a second FSM for `handIndex=1`)

See the Reference and How-To docs for the parameter registry and tuning procedure.

---

*Generated 2026-02-20 by P4 Red Regnant. Bronze layer — validate before promotion.*
