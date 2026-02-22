---
schema_id: hfo.gen90.omega_v15.rewrite_brief.v1
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
bluf: "Operator brief for Omega v15 rewrite. For external AI analysts. Defines the honest assessment of v13 Potemkin Village, the 8 architectural rules, the 5 core pieces Definition of Done, and what to preserve vs delete. Meadows L8 governance artifact."
primary_port: P7
secondary_ports: [P3, P5]
generated: "2026-02-21"
operator: TTAO
related_bundle: OMEGA_V15_LLM_CONTEXT_BUNDLE.md
tags: [bronze, forge:hot, para:resources, omega, v15, rewrite, brief, external-ai, handoff, rules, gen90]
---

# OMEGA V15 — Operator Rewrite Brief

> **For:** External AI Analyst / Code Generation Agent
>
> **From:** TTAO (Operator) + P7 Spider Sovereign (HFO Gen90)
>
> **Date:** 2026-02-21
>
> **Purpose:** This is the authoritative mandate for the Omega v15 rewrite.
> Read this BEFORE reading any v13 source code. It will prevent you from
> re-implementing known-bad patterns.
>
> **Compute Scale:** ~5 billion tokens consumed across 88 generations (1.5B proven on OpenRouter + heavy Copilot usage via "cursed ralph wiggums loops").
>
> **Full context:** See `OMEGA_V15_LLM_CONTEXT_BUNDLE.md` in the same directory.

---

## TL;DR

**The Problem in One Sentence:**

Omega v13 appears to work (89 tests pass, cursor moves, gestures trigger) but contains 3 hidden critical bugs, 14+ dead code files, and 6 architectural antipatterns that will cause production failures at scale.

**The Decision:**

Rewrite as Omega v15 in HFO Gen90 hot bronze. Keep the 4 elite patterns. Delete the 6 antipatterns. Fix the 3 hidden bugs. Implement the 3-pillar Pareto architecture. Achieve 80–99% mutation score. Ship 5 core pieces.

---

## PART 1: WHAT OMEGA DOES

Omega is a Spatial OS that turns a smartphone camera into a cursor for any 2D display.

```
[Phone Camera] → [MediaPipe hand tracking] → [Gesture FSM]
              → [Kalman filter] → [W3C Pointer Events]
              → [postMessage → iframe Symbiote]
              → [Any web app responds to air gestures]
```

**The value proposition:** A $50 smartphone + a TV + unmodified web apps = a touchless spatial OS. No VR headset. No cloud. No specialized hardware.

**The architecture philosophy:** Plugin Microkernel. Host/Guest strict separation. Event bus only — no direct component calls. PAL (Platform Abstraction Layer) for all platform values.

---

## PART 2: THE HONEST V13 ASSESSMENT

### What APPEARS to work

| Feature | Status |
|---------|--------|
| Camera starts, hand skeleton visible | ✅ Appears to work |
| Pinch gesture detected | ✅ Appears to work |
| Cherry MX click sound on pinch | ✅ Appears to work |
| Cursor moves on tldraw whiteboard | ✅ Appears to work |
| 73 Jest + 16 Playwright tests pass | ✅ All green |
| 0 TypeScript errors | ✅ Clean |

### The Potemkin Village (What Is Actually Broken)

**Potemkin Village** = facade that visually passes while structurally broken.

| Hidden Fault | Severity | Impact |
|-------------|----------|--------|
| `SymbioteInjectorPlugin` was never registered in the live demo | CRITICAL | Actual DOM `PointerEvent` injection was **completely dead** — cursor appeared to move but tldraw was not actually receiving events |
| `StillnessMonitorPlugin` was never registered in the live demo | CRITICAL | Stillness detection and FSM idle timer were **completely broken** |
| PAL leak in `visualization_plugin.ts` — reading `window.omegaOverscanScale` instead of PAL | MAJOR | Silent split-brain bug in overscan — PAL updates would not propagate to skeleton |
| 14+ orphan files compile + have tests but never enter the demo bootstrap chain | STRUCTURAL | False sense of feature completeness |
| GA (`behavioral_predictive_layer.ts`) runs but never writes Q/R back to Kalman filter | LOGIC | Self-tuning is an illusion — GA runs, nothing changes |
| MAP-Elites is documented but the code is a standard single-objective GA | FALSE CLAIM | No quality diversity, no grid, no repertoire |
| `evolve()` runs on main thread — 20ms block = 120Hz pointer freeze | PERF | Blocks render on every GA generation |

**The honest summary:** v13 would fail in a real demo because SymbioteInjector (the component that makes tldraw actually respond) was not plugged in. This is classic Potemkin Village — every sub-component looks fine in isolation, but the wiring in the live bootstrap was broken.

---

## PART 3: WHAT TO PRESERVE IN V15

These 4 patterns are architectural superpowers. They must survive the rewrite:

### PRESERVE-1: Privacy-by-Math (`UserTuningProfile`)
Store user interaction style as Kalman coefficients and GA axis weights, NOT as video or skeletal data. This is GDPR/COPPA compliant by construction — mathematically impossible to reverse-engineer to video. Location: `behavioral_predictive_layer.ts` → `UserTuningProfile`.

### PRESERVE-2: Synthesized Synesthesia (Cherry MX clicks)
Synthesize the mechanical keyboard click sound via `AudioContext` oscillators at the exact FSM `COMMIT_POINTER` state transition. Zero I/O latency. No .mp3 loading. Tricks the somatosensory cortex. Location: `audio_engine_plugin.ts` → `synthesizeClick()`.

### PRESERVE-3: Procedural Observability (Self-Writing ADRs)
The `temporal_rollup.ts` system translates floating-point matrix deltas into English logs. The AI writes its own Architecture Decision Records as it evolves. Must survive into v15.

### PRESERVE-4: Physics-as-UI (Velocnertia Clamp)
Havok physics spring constant + max velocity clamp on the cursor — it has mass and cannot teleport. Creates the "heavy, premium, tethered-to-reality" feel. Location: `babylon_physics.ts`.

---

## PART 4: WHAT TO DELETE IN V15

Do NOT port these patterns — they are architecturally broken and documented as such:

| Delete | Reason |
|--------|--------|
| `gesture_bridge.ts` (class) | Tight coupling — directly calls `pointerFabric.processLandmark()`. Bypass the event bus. Delete and reroute via EventBus. |
| `iframe.contentDocument.elementFromPoint()` in pointer fabric | Security violation — breaks on cross-origin iframes. Replace with `postMessage` only. |
| Stillness detection hardcoded in `gesture_fsm.ts` `processFrame()` | Mixed concerns — spatial math in state logic. Already fixed in v13 via `StillnessMonitorPlugin` but the old code may still exist. |
| `predictions.push({...})` in GA hot loop | GC churn — replace with `Float32Array` pre-allocation. |
| `evolve()` on main thread | Frame-dropper — must be in Web Worker. |
| `demo.ts` | Superseded by `demo_2026-02-20.ts`. |
| All 14 orphan files in the "deferred" category | They are not tested in production context — they are false confidence. Bring them in only when actively wired. |

---

## PART 5: THE 8 ARCHITECTURAL RULES FOR V15

These are not guidelines. They are laws. Any code violating these rules MUST fail its tests.

```
RULE 1 — EVENT BUS ONLY
No component may directly call another component's methods.
All inter-component communication goes through EventBus.
Test: Static analysis MUST find zero direct method calls between plugins.

RULE 2 — PAL FOR ALL PLATFORM VALUES
No component reads from raw `window.*`, `document.*`, or `navigator.*`.
All platform values resolved via `context.pal.resolve(key)`.
Test: Static analysis MUST find zero `window.inner*`, `window.screen.*` outside PAL init.

RULE 3 — POSTMESSAGE ONLY FOR HOST→GUEST
Host NEVER touches Guest DOM directly.
All Host→Guest communication via `window.postMessage`.
All synthetic pointer IDs MUST be >= 10000.
Test: Static analysis MUST find zero `iframe.contentDocument.*` access.

RULE 4 — ZERO HOT-LOOP ALLOCATION
No heap allocation inside any function called at 30fps+.
All buffers pre-allocated as Float32Arrays at class init.
Test: Static analysis MUST find zero `new {}` or `Array.push()` in hot paths.

RULE 5 — WEB WORKER FOR EVOLUTION
GA/ML evolution runs in a Web Worker ONLY.
Main thread is reserved for render + pointer dispatch.
Test: `evolve()` MUST be in a file ending with `_worker.ts`.

RULE 6 — DESTROY UNSUBSCRIBES EVERYTHING
Every plugin MUST implement `destroy()` that unsubscribes ALL event listeners.
ALL event subscriptions stored as class fields (bound references, never anonymous).
Test: Property invariant — every `subscribe()` call must have a matching `unsubscribe()` in `destroy()`.

RULE 7 — BOOT SEQUENCE AUDIO ANCHOR
`AudioContext` MUST be created and `.resume()`d during the FIRST physical tap on the display.
Never create AudioContext before a trusted user gesture.
Test: `AudioContext` constructor MUST only appear inside a `isTrusted === true` click handler.

RULE 8 — GOLDILOCKS MUTATION SCORE
Stryker mutation score MUST be 80%–99%.
100% kill rate = Green Lie = instant fail (GRUDGE_016).
Below 80% = insufficient test coverage = instant fail.
Test: `npm run mutate` must exit with score in [80, 99].
```

---

## PART 6: THE 6 ATDD INVARIANTS (NON-NEGOTIABLE)

These 6 Gherkin scenarios MUST pass before any feature ship. They are the launch gate.

1. **PAL Viewport Binding** — No `window.screen.*` references; only `window.inner*` + resize listener
2. **Z-Stack Penetration** — `LAYER.SETTINGS` defaults to `pointerEvents: 'none'`
3. **Synthetic Pointer Compatibility** — `eventInit.buttons > 0` maps to `button: 0`; `setPointerCapture` polyfilled for IDs ≥ 10000
4. **GC Zero-Allocation** — `W3CPointerFabric` MUST NOT import `zod` or call `.parse()` in hot path
5. **Orthogonal FSM** — IDLE→COMMIT is illegal; COMMIT→IDLE must route through COAST
6. **Host/Guest Separation** — Guest iframe contains no MediaPipe references; all events via postMessage

---

## PART 7: DEFINITION OF DONE (PARETO BLUEPRINT)

Build exactly these **5 Core Pieces** and the MVP is mathematically complete:

### CORE-1: Foveated ROI Cropping
Phone finds the hand at full resolution, then crops to a 256×256 px bounding box and feeds ONLY that box to MediaPipe. Enables 120Hz inference on a $50 phone.

**Status in v13:** `foveated_cropper.ts` exists as stub. Orphan — MediaPipe Tasks API crops its tracking input internally. **Verify behavior before implementing.**

### CORE-2: Scale-Invariant Biological Raycasting
Pinch threshold = `(thumb_tip to index_tip distance) / (wrist to index_knuckle distance)`. This anatomical ratio is constant regardless of depth, arm extension, or display distance. Anti-Gorilla-Arm by design.

**Status in v13:** `biological_raycaster.ts` exists as exploratory spec-only. Must be connected to GestureFSM.

### CORE-3: WebRTC UDP Data Channel
`RTCDataChannel({ ordered: false, maxRetransmits: 0 })` — UDP semantics. Phone → TV. If Wi-Fi drops a packet, TCP would halt all traffic to request retransmit (cursor freezes). UDP just continues. This is the zero-latency wireless transport.

**Status in v13:** `webrtc_udp_transport.ts` exists as stub. ~3 days full implementation.

### CORE-4: W3C Level 3 Symbiote Injector (Stateful Agent v2)
All 4 synthetic pointer failure modes fixed:
- Pointer capture via `Element.prototype.setPointerCapture` intercept
- Event cascade: `pointerenter`/`pointerleave` + `click` synthesizer
- isTrusted focus: explicit `.focus()` on pointer targets
- `pointerType: 'pen'` for tldraw ink mode

**Status in v13:** Stateful Symbiote Agent v2 implemented in `tldraw_layer.html`. MUST be verified working end-to-end with the SymbioteInjectorPlugin properly wired.

### CORE-5: Wood Grain Tuning Profile (Privacy-Safe)
`UserTuningProfile` JSON containing:
```json
{
  "kalmanQ": 0.05,
  "kalmanR": 10.0,
  "havokSpringK": 0.3,
  "schmittCommitThreshold": 0.85,
  "schmittReleaseThreshold": 0.6,
  "gaGeneration": 0,
  "createdAt": "2026-02-21",
  "deviceClass": "mid-range-phone"
}
```

Grows with user via background chron-job measuring average jitter and adjusting sliders. No video. No skeletal data.

**Status in v13:** `wood_grain_tuning.ts` exists. No live wiring.

---

## PART 8: SIGNAL PROCESSING FACTS

**Before writing any signal code, internalize these facts:**

1. **MediaPipe Tasks API has NO built-in smoothing.** The deprecated `@mediapipe/hands` package had 1 Euro Filter internally. The current `@mediapipe/tasks-vision` HandLandmarker does not. Our `KalmanFilter1D` is the ONLY temporal smoother.

2. **Kalman defaults:** `smoothingQ: 0.05, smoothingR: 10.0` for 30fps phone camera. Q=0.05 means "trust the model"; R=10.0 means "landmarks jump ±5px per frame."

3. **1 Euro Filter** — NOT in v13. COULD be added ON TOP of Kalman for v15. Would add velocity-dependent smoothing (heavy when still, light when fast). Not a replacement — a stackable additive layer.

4. **The Kalman `predict(steps)` method is the ONLY predictive lookahead in the stack.** MediaPipe provides no lookahead.

---

## PART 9: V15 STARTING POINT

```
Source:  hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/
Status:  v13 source files copied; npm install done; base scaffold ready
Runtime: TypeScript + esbuild + Jest + Playwright + Stryker
Target:  Chrome 120+ (ESM, no IE, no polyfills)
```

**First session tasks:**
1. Wire `SymbioteInjectorPlugin` correctly and write an e2e test proving tldraw receives `PointerEvent`
2. Wire `StillnessMonitorPlugin` correctly and write a unit test proving `STILLNESS_DETECTED` fires after threshold
3. Fix the PAL leak in `visualization_plugin.ts`
4. Run Stryker and get mutation score into 80–99% zone
5. Implement CORE-4 (Symbiote v2) with all 4 failure mode fixes verified

---

## PART 10: THE THREE THINGS THAT DISTINGUISH V15 FROM V13

1. **Honest bootstrap** — `demo_v15.ts` registers EVERY plugin it depends on. No ghost channels. No orphan subscribers. All plugins or none.

2. **Rule-enforced architecture** — The 8 rules above are ATDD-tested, not just documented. Static analysis specs enforce them.

3. **Goldilocks mutation gate** — Stryker must pass 80–99% before any feature is considered done. No Green Lies.

---

*Generated: 2026-02-21 | HFO Gen90 | PREY8 session d7a2f2819cff6b2a | React token 46FCFF | Meadows L8*
*See OMEGA_V15_LLM_CONTEXT_BUNDLE.md for full technical reference.*
