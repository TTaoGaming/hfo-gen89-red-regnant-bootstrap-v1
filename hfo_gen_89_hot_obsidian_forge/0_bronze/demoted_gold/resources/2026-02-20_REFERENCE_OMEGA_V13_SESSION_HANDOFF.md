---
schema_id: hfo.gen89.omega_v13.sota_handoff.v1
medallion_layer: gold
mutation_score: 0
hive: V
hfo_header_v3: compact
bluf: "Omega v13 session handoff: 4 elite patterns, 6 lethal antipatterns with fixes, 5 SOTA signal-processing upgrades. 1 Euro Filter + Kalman lookahead is the correct signal stack."
primary_port: P2
role: P2 SHAPE — reference/doctrine for next Omega v13 session
tags: [gold, forge:hot, para:resources, diataxis:reference, omega, braided, mission, thread, signal-processing, kalman, one-euro-filter, mediapipe, w3c-pointer, spatial-os, handoff]
generated: "2026-02-20"
session_nonce: "72A41B"
source_session: "2026-02-20 Omega v13 architecture + SOTA review"
---

# REFERENCE: Omega v13 Microkernel — Session Handoff & SOTA Architecture

## TL;DR

This session built and reviewed the Omega v13 Microkernel. The codebase has **4 architectural superpowers** and **6 production saboteurs**. All 6 saboteurs have documented fixes. Additionally, **5 SOTA signal-processing patterns** were captured from HCI academia and big-tech peers to inform the next evolution phase.

**The most important correction from this session:** The project was using 1 Euro Filter with MediaPipe. The operator confirmed: **1 Euro Filter + Kalman is the correct stack**. MediaPipe is their backend — use 1 Euro for velocity-dependent smoothing, add Kalman *on top* for lookahead prediction.

---

## 1. What Was Built (Omega v13 Microkernel State)

| Component | File | Status |
|-----------|------|--------|
| Plugin Microkernel | `shell.ts`, `plugin_supervisor.ts` | Active |
| Gesture FSM | `gesture_fsm.ts`, `gesture_fsm_plugin.ts` | Active |
| Signal Processing | `kalman_filter.ts` | Active (needs 1€ hybrid) |
| MediaPipe Integration | `mediapipe_vision_plugin.ts` | Active |
| W3C Pointer Fabric | `w3c_pointer_fabric.ts` | Active |
| iframe Delivery | `iframe_delivery_adapter.ts`, `symbiote_injector.ts` | Active |
| Behavioral Predictive Layer | `behavioral_predictive_layer.ts` | Active (see antipatterns) |
| Audio Engine | `audio_engine_plugin.ts` | Active (has zombie listener bug) |
| Babylonian Physics | `babylon_physics.ts` | Active (Velocnertia Clamp) |
| Foveated Cropper | `foveated_cropper.ts` | Stub — not implemented |
| WebRTC Transport | `webrtc_udp_transport.ts` | Stub — not implemented |
| UI Shell | `index_demo2.html`, `demo_2026-02-20.ts` | Active |
| Built bundle | `dist/demo2.js` | Built (esbuild, ESM, Chrome120) |

**Current mission state items IN scope (omega thread, active):**

| ID | Priority | Title |
|----|----------|-------|
| `omega.v13.arch.v1_global_singleton` | P99 | V1 Fix: Remove globalEventBus singleton — EventBus isolation |
| `omega.v13.arch.v4_rogue_agents` | P95 | V4 Fix: Wrap StillnessMonitor + W3CPointerFabric as Plugin |
| `omega.v13.arch.v5_pal_leaks` | P93 | V5 Fix: Route window.innerWidth/Height through PAL capabilities |
| `omega.v13.ui.hud` | P50 | HUD — fps/state/pos readout bottom-left |
| `T-OMEGA-001` | P10 | Fix Main-Thread Evolutionary Blocking |
| `T-OMEGA-002` | P9 | Fix Garbage Collection Churn |
| `T-OMEGA-006` | P9 | Fix Untrusted Gesture Audio Trap |
| `T-OMEGA-003` | P8 | Fix Ground Truth Paradox |
| `T-OMEGA-005` | P8 | Fix Zombie Event Listeners |

---

## 2. The 4 Elite Patterns (Preserve These)

### E1. Privacy-by-Math (The "Wood Grain" Profile)
**Location:** `UserTuningProfile` in `behavioral_predictive_layer.ts`

Serializes *mathematical coefficients* of movement (Kalman, GA axis weights). Zero raw video. Mathematically impossible to reverse-engineer back to a video feed. GDPR/COPPA-compliant by construction.

> **Insight:** The "Wood Grain" fingerprint of a human's motor skill encoded as pure math is the **anti-surveillance spatial computing unlock**.

### E2. Synthesized Synesthesia (Zero-Latency Tactile Feedback)
**Location:** `synthesizeClick()` in `audio_engine_plugin.ts`

AudioContext oscillators synthesize the mechanical keyboard click at the exact `COMMIT_POINTER` FSM state change. No .mp3 I/O. Literally zero latency. Tricks the somatosensory cortex into feeling a physical boundary that doesn't exist.

### E3. Procedural Observability (Self-Writing ADRs)
**Location:** `temporal_rollup.ts`

Translates temporal rollups of floating-point matrix deltas into human-readable English logs. The system writes its own Architecture Decision Records as it evolves. Black-box prevention.

### E4. Physics-as-UI (The Velocnertia Clamp)
**Location:** `babylon_physics.ts`

Havok physics spring constant + max velocity clamp. Cursor has mass and momentum. Cannot teleport. Enforces thermodynamics on the digital pointer.

---

## 3. The 6 Lethal Antipatterns (Fix These Next)

### A1. Main-Thread Evolutionary Blocking (`T-OMEGA-001`, P10)
**Location:** `evolve()` in `behavioral_predictive_layer.ts`

GA evaluates 50 genotypes synchronously on the main JS thread. 20ms block = 120Hz pointer freeze.

**Fix:** Web Worker isolation. Main thread sends ring-buffer via `postMessage`. Worker returns improved `Genotype` for hot-swap only when fitness improves.

```typescript
// behavioral_predictive_worker.ts already exists — wire it in
const worker = new Worker('./behavioral_predictive_worker.js');
worker.postMessage({ type: 'EVOLVE', ringBuffer: this.ringBuffer });
worker.onmessage = (e) => { if (e.data.fitness > this.currentFitness) this.activeGenotype = e.data.genotype; };
```

### A2. Garbage Collection Churn (`T-OMEGA-002`, P9)
**Location:** `simulatePrediction()` in `behavioral_predictive_layer.ts`

`predictions.push({x, y, z, timestamp})` inside the hot GA fitness loop = V8 heap flood = GC stop-the-world freeze (50-100ms).

**Fix:** Pre-allocated `Float32Array`. Pool recycled per-generation. Zero heap allocation in the hot path.

```typescript
// Pre-allocate once at class init
private predBuffer = new Float32Array(MAX_HISTORY * 4); // x,y,z,t interleaved

// In hot loop — overwrite by index, never push
this.predBuffer[i * 4 + 0] = estimate;
this.predBuffer[i * 4 + 1] = data[i].y;
this.predBuffer[i * 4 + 2] = data[i].z;
this.predBuffer[i * 4 + 3] = data[i].timestamp;
```

### A3. Ground Truth Paradox (`T-OMEGA-003`, P8)
**Location:** `bpl.evolve(noisyData, groundTruthData)`

Tests use a perfect sine wave as Ground Truth. Production has no ground truth. MSE fitness can't be calculated.

**Fix:** "Shadow Tracker" pattern — run a heavily delayed (500ms lag) Savitzky-Golay filter or moving average in the background. It IS the pseudo-ground-truth. Train the real-time Kalman/GA to predict where the delayed Shadow Tracker will be.

```typescript
// Shadow tracker emits delayed "true" position
const delayed = this.shadowTracker.getDelayed(500); // 500ms lag
const fitness = this.mse(predicted, delayed);
```

### A4. MAP-Elites Mirage (`T-OMEGA-004`, P9)
**Location:** `behavioral_predictive_layer.ts`

Code is a standard single-objective GA, not MAP-Elites. Documentation says MAP-Elites. Fitness is just MSE sort.

**Fix:** Implement the grid. On evaluation, calculate behavioral descriptor `[frequency, amplitude]`, map to 2D grid cell, keep only if fitness beats current occupant of that cell.

```typescript
const freq = this.estimateFrequency(genotype);
const amp = this.estimateAmplitude(genotype);
const cell = `${Math.floor(freq * 10)}_${Math.floor(amp * 10)}`;
if (!this.grid.has(cell) || this.grid.get(cell)!.fitness < fitness) {
    this.grid.set(cell, { genotype, fitness });
}
```

### A5. Zombie Event Listeners (`T-OMEGA-005`, P8)
**Location:** `audio_engine_plugin.ts`

`init()` subscribes with `.bind(this)` but `destroy()` doesn't unsubscribe. New anonymous function each bind = unsubscribable = memory leak on hot-swap.

**Fix:**

```typescript
// Class field — same reference always
private boundOnStateChange = this.onStateChange.bind(this);

init() { this.context.eventBus.subscribe('STATE_CHANGE', this.boundOnStateChange); }
destroy() { this.context.eventBus.unsubscribe('STATE_CHANGE', this.boundOnStateChange); }
```

### A6. Untrusted Gesture Audio Trap (`T-OMEGA-006`, P9)
**Location:** Bootstrap AudioContext initialization

Synthetic W3C pointer events have `isTrusted === false`. Chrome's autoplay policy permanently mutes AudioContext on untrusted events.

**Fix (cannot be bypassed in code):** The FIRST action on the 100-inch screen MUST be a physical glass tap. Full-screen "TAP TO START" splash. That single trusted tap resumes the global AudioContext.

```typescript
document.addEventListener('pointerdown', (e) => {
    if (e.isTrusted && audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
}, { once: true });
```

---

## 4. The 5 SOTA Upgrade Patterns (Inserted into mission_state as T-OMEGA-ARCH-001..005)

These were captured from HCI academia and big-tech engineering and stored in the braided mission thread as architectural constraints.

### S1. Signal Processing: 1 Euro Filter + Kalman Lookahead (`T-OMEGA-ARCH-001`)

**The stack:** 1 Euro Filter *on top of* MediaPipe output, Kalman added for prediction lookahead.

- **1 Euro Filter:** Velocity-dependent cutoff. Slow movement = heavy smoothing (kill jitter). Fast movement = no smoothing (zero latency). Industry standard from Géry Casiez 2012.
- **Kalman:** Adds lookahead. Predicts where the hand will be 2-3 frames ahead, eliminating the perception of lag on fast gestures.
- **MediaPipe is the optical backend** — it doesn't provide these layers internally.

**Why not pure Kalman:** Kalman is for linear physics (ballistic missiles). Human hands are non-linear (accelerate violently, stop suddenly). Pure Kalman over-smooths critical motion edges.

### S2. Physics & Kinematics: Soft Contact from Ultraleap (`T-OMEGA-ARCH-002`)

Ultraleap spent $100M+ solving bare-hand-to-digital-UI. Key insight: digital cursors rigidly locked to hands cause "push-through" — hand momentum is absorbed by the UI accidentally triggering it. 

**Fix:** Physics springs. Cursor stops *on top* of UI elements, absorbing shock. Anti-pattern: Z-Axis punching causes Gorilla Arm fatigue in 3 minutes. Pinch (thumb to index) is the only ergonomically sustainable click mechanic.

### S3. Ergonomics: Target Magnetism (Gravity Wells) from Apple WWDC `T-OMEGA-ARCH-003`)

Even with 1 Euro filtering, heartbeat and breathing cause 1-2mm jitter at 10ft range. Apple solves this with "Magnetism": when velocity approaches zero, snap `clientX/Y` to the center of the nearest clickable element's `getBoundingClientRect()`.

**Implementation in `W3CPointerFabric`:**

```typescript
if (velocity < SNAP_THRESHOLD) {
    const target = document.elementFromPoint(rawX, rawY);
    if (target?.matches('button, a, [role="button"]')) {
        const rect = target.getBoundingClientRect();
        pointerX = rect.left + rect.width / 2;
        pointerY = rect.top + rect.height / 2;
    }
}
```

### S4. Zero-Latency Transport: Forward Error Correction (`T-OMEGA-ARCH-004`)

Phone (Optical Nerve) → TV (Motor Cortex) over WebRTC UDP. Wi-Fi drops packets. 

**FEC pattern:** Encode `[currentFrame, prevFrameDelta]` into every packet. If packet N drops, packet N+1 has enough delta to reconstruct it instantly.

**Binary payload** (never JSON.stringify at 120Hz — triggers GC):

```typescript
// Pack into Float32Array: [handId, x, y, pinchState]
const buf = new Float32Array(4);
buf[0] = handId;
buf[1] = normalizedX;
buf[2] = normalizedY;
buf[3] = pinchState;
channel.send(buf.buffer); // ArrayBuffer — no GC
```

### S5. DOM Symbiote: Full Event Cascade + CDP (`T-OMEGA-ARCH-005`)

`PointerDown` + `PointerUp` alone is rejected by React/Vue/Google Docs internal state machines. Must synthesize the full W3C cascade:

`pointerover → pointerenter → mousemove → mousedown → pointerdown → focus → click`

**Ultimate escape hatch:** Wrap the 100-inch TV host in **Electron or Tauri**. This exposes the CDP `Input.dispatchMouseEvent` API. The Chromium engine registers these as 100% native, hardware-trusted inputs (`isTrusted === true`). Bypasses all CORS, iframe, and autoplay restrictions.

---

## 5. The 4 Decoupled Node Architecture (Solo Developer Strategy)

Stop building apps. Build the transport layer. 100% focus on:

| Node | Role | Primary Tech |
|------|------|-------------|
| `Optical Nerve` | Phone — captures and sends | MediaPipe HandLandmarker, foveated cropping |
| `Spinal Cord` | Network — transmits | WebRTC UDP, Float32Array payloads, FEC |
| `Motor Cortex` | TV — receives and filters | 1 Euro + Kalman, Velocnertia Clamp, Target Magnetism |
| `The Muscles` | DOM — injects | Full W3C cascade, Electron CDP for trusted input |

If Wikipedia feels like a premium physics-backed spatial app from 10 feet away — the community will build all the apps.

---

## 6. Critical Architecture Violations Still Open

From `microkernel_arch_violations.spec.ts`, these are structurally gated:

| Violation ID | Description | Fix Path |
|-------------|-------------|----------|
| V1 | `globalEventBus` singleton imported in 8+ files | Each plugin gets its own `eventBus` via `PluginContext` |
| V4 | `StillnessMonitorPlugin` / `W3CPointerFabric` not wrapped as Plugin | Implement `Plugin` interface (init/start/stop/destroy) |
| V5 | 20 hardcoded `window.innerWidth/Height` and `document.elementFromPoint` | Route through PAL capabilities object |

V2 (demoted MediaPipeVisionPlugin from demo.ts) and V3 (removed double debounce) are **DONE**.

---

## 7. Current Build State

```bash
# Build command (from omega_v13_microkernel dir)
npx esbuild demo_2026-02-20.ts --bundle --outfile=dist/demo2.js \
  --sourcemap --format=esm --platform=browser --target=chrome120 \
  --external:./babylon_physics

# Serve (from omega_v13_microkernel dir)
python -m http.server 5173
# Then open: http://localhost:5173/index_demo2.html
```

Bundle: `dist/demo2.js` — ESM, Chrome120, babylon_physics externalized.

---

## 8. Next Session Priority Order

1. **Fix V1 (globalEventBus)** — P99, precondition for all other plugin work
2. **Fix Zombie Event Listeners (A5)** — 30 min, `audio_engine_plugin.ts`
3. **Implement trusted audio tap** — boot screen `isTrusted` solution
4. **Integrate 1 Euro Filter** — on top of KalmanFilter, before W3C emission
5. **Implement Shadow Tracker** — unlocks real-world GA training
6. **Wire behavioral_predictive_worker.ts** — unblock main thread
7. **Fix V4 + V5** — rogue agents + PAL leaks

---

*SW-4 Contract: Given this session reviewed Omega v13 architecture and captured SOTA patterns. When operator returns for next session. Then they have a complete reference: 4 elites to preserve, 6 antipatterns to fix (in order), 5 SOTA upgrades to implement, current build state.*
