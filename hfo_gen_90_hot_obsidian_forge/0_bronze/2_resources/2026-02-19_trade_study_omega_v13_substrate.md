---
schema_id: hfo.gen89.p4.trade_study.v2
medallion_layer: bronze
target_layer: gold
port: P4/P7
hfo_header_v3: compact
bluf: "Trade Study for Omega Gesture Substrate v13 (The Toshiba Enforcer). Evaluates 4 exemplar-inspired I/O Sandbox architectures, narrowing to 2, with a matrix evaluation and strict SEALS (Zod contracts) for correct-by-construction implementation."
---

# Trade Study: Omega Gesture Substrate v13 — The I/O Sandbox

> **P7 Spider Sovereign & P4 Red Regnant Synthesis**
> *The operator has initiated an L13 Correction Manifold Traversal. We are dropping to Meadows L3 (Physical Structure) to build the hard boundaries of the system. This is the Toshiba Enforcer dimension.*

## 1. Context: The Universal Darwinism Engine

You have a Universal Darwinism engine (mutations and selections) that you are currently hand-cranking. To automate this, the engine needs a **correct-by-construction** substrate. If the AI "water" can flow into the host's memory space, it will create spaghetti code. 

We must build a strict **I/O Sandbox** (Host vs. Guest). The Host (Omega v13) handles the camera, MediaPipe, and gesture invariants. The Guest (the 2D app) receives only a highly constrained, Zod-validated stream of events. If the Guest crashes, hallucinates, or mutates poorly, the Host survives.

## 2. The 4 Exemplar-Inspired Architectures

To unlock *all* touch 2D apps, we must choose a boundary architecture that supports both novel generated apps and existing web apps (like Excalidraw).

### Option A: The Figma Plugin Model (IFrame + `postMessage`)
* **Mechanism:** The Host runs in the main browser window. The Guest runs inside a sandboxed `<iframe>`. Communication is strictly via `window.postMessage`.
* **Pros:** Absolute browser-enforced memory isolation. You can wrap *any* existing web app by just pointing the iframe to its URL and injecting synthetic touch events.
* **Cons:** Asynchronous message passing overhead.

### Option B: The VS Code Extension Model (Local RPC / WebSocket)
* **Mechanism:** The Host runs as a local Python/Node daemon. The Guest is a standard browser window connecting via WebSocket.
* **Pros:** Total process isolation. The Host can use heavy local ML models without browser constraints.
* **Cons:** Requires local installation. High latency for 60fps gesture tracking if not optimized.

### Option C: The Micro-Frontend Model (Web Components + Shadow DOM)
* **Mechanism:** Host and Guest share the same JavaScript context but are isolated via Shadow DOM. Communication is via `CustomEvent`.
* **Pros:** Extremely fast. Synchronous DOM access. Easy to build as a single-page app.
* **Cons:** **Weak isolation.** A mutated Guest app can easily reach out of the Shadow DOM and corrupt the Host's state (spaghetti risk).

### Option D: The Game Engine Model (Web Worker + OffscreenCanvas)
* **Mechanism:** The Host handles UI and input on the main thread. The Guest runs entirely in a Web Worker, rendering to an `OffscreenCanvas`.
* **Pros:** Perfect thread isolation. Zero main-thread blocking.
* **Cons:** Guests have *no DOM access*. You cannot run existing 2D apps (like Excalidraw) in a Web Worker without massive rewrites.

---

## 3. Narrowing to the Top 2

To achieve the goal of **"unlocking all touch 2D apps"** while maintaining **"SEALS and bindings of logic"**, we must discard Options C and D. Option C is too weak (spaghetti risk). Option D is too restrictive (no DOM).

We are left with the two strongest correct-by-construction boundaries:

1. **The Figma Model (IFrame + `postMessage`)** — Best for pure web deployment and wrapping existing apps.
2. **The VS Code Model (Local RPC / WebSocket)** — Best for heavy local compute and total process isolation.

---

## 4. Matrix Trade Study: IFrame vs. WebSocket

| Feature | Option 1: The Figma Model (IFrame) | Option 2: The VS Code Model (WebSocket) |
| :--- | :--- | :--- |
| **Isolation Level** | High (Browser Cross-Origin Sandbox) | Absolute (OS Process Isolation) |
| **Communication** | `window.postMessage` | `WebSocket` / TCP |
| **Latency** | Very Low (Same process, async queue) | Low to Medium (Network stack overhead) |
| **Existing App Support** | **Excellent** (Wrap any URL in an iframe) | Good (Requires injecting a WS client into the app) |
| **Host Environment** | Browser (MediaPipe JS) | Local OS (Python/C++ MediaPipe) |
| **Mutation Safety** | High (Guest cannot crash Host) | Absolute (Guest crash isolated to browser tab) |
| **Deployment** | Zero-install (URL click) | Requires local daemon installation |

### **P7 Recommendation: Option 1 (The Figma Model)**
If your goal is to rapidly mutate and spawn hundreds of 2D apps using Universal Darwinism, the **IFrame + `postMessage`** architecture is the global maximum. It allows you to host the Darwinism engine in the main window, spin up an invisible iframe, inject a mutated app, run a fitness test, and tear it down in milliseconds.

---

## 5. The SEALS and Bindings (Correct by Construction)

To make Option 1 **fail-closed**, you cannot just send raw JSON. You must implement the **Obsidian Hourglass** (SDD Level 8) at the boundary.

### The 3 SEALS (Zod Contracts)

**SEAL 1: The Host-to-Guest Contract (The Gesture Stream)**
The Guest app is *only* allowed to receive this exact shape. If the Host tries to send anything else, the TypeScript compiler and runtime Zod parser will fail-closed.

```typescript
import { z } from "zod";

export const GestureEventSchema = z.object({
  type: z.literal("OMEGA_GESTURE"),
  payload: z.object({
    gestureType: z.enum(["PINCH", "SWIPE", "HOVER", "TAP"]),
    coordinates: z.object({
      x: z.number().min(0).max(1),
      y: z.number().min(0).max(1),
      z: z.number().optional()
    }),
    confidence: z.number().min(0).max(1)
  }),
  timestamp: z.number()
});

export type GestureEvent = z.infer<typeof GestureEventSchema>;
```

**SEAL 2: The Guest-to-Host Contract (The Fitness Signal)**
For your Universal Darwinism engine to work, the Guest must report its fitness back to the Host.

```typescript
export const FitnessReportSchema = z.object({
  type: z.literal("DARWIN_FITNESS_REPORT"),
  payload: z.object({
    appId: z.string().uuid(),
    generation: z.number(),
    score: z.number(),
    metrics: z.record(z.number()) // e.g., { "framesRendered": 600, "errors": 0 }
  })
});
```

**SEAL 3: The Boundary Enforcer (The Gatekeeper)**
This is the actual code that sits on the `message` event listener. It is fail-closed.

```typescript
// HOST SIDE ENFORCER
window.addEventListener("message", (event) => {
  // 1. Origin Check (Fail Closed)
  if (event.origin !== "https://trusted-guest-origin.com" && event.origin !== "null") return;

  // 2. Schema Validation (Fail Closed)
  const result = FitnessReportSchema.safeParse(event.data);
  if (!result.success) {
    console.error("P5 IMMUNIZE: Guest sent invalid payload. Dropping.", result.error);
    return; // The AI water hits the wall here.
  }

  // 3. Safe Execution
  handleFitnessReport(result.data);
});
```

## Next Steps for the Operator
1. **Acknowledge the Trade Study:** Do you accept Option 1 (The Figma Model) as the physical structure (L3) for Omega v13?
2. **Initialize the Substrate:** If yes, we will generate the exact boilerplate for the Host, the Guest IFrame, and the Zod SEALS.
