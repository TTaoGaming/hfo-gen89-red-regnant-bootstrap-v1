# Omega v13 — Feature Trade Study
*Single-page decision reference. Feb 20 2026.*

---

## What we're building

**Phone camera → hand tracking → cursor on a big screen.**  
You move your finger, a dot follows it. Pinch = click. That's the core loop.  
Everything else is layered on top of that loop.

---

## Executive Summary

The core loop **works today**: camera → MediaPipe → gesture → pointer → tldraw iframe.  
Tests pass (73 Jest, 16 Playwright, 0 TypeScript errors).

**The honest gaps are:**
1. The cursor feels jittery (no jitter fix wired end-to-end yet)
2. Babylon/physics spheres exist as code but are not plugged in
3. The GA evolves numbers but never feeds them back to the filter
4. WebRTC (phone-to-TV screen-cast) is a stub

Everything else either exists and works, or is a nice-to-have.

---

## Decision Matrix

Each row = one feature. You pick a tier: **0 = ship it now**, **1 = next sprint**, **2 = later**, **X = drop it**.

| # | Plain Name | What it does | Code state | Cost to finish | Unlocks | Your tier |
|---|---|---|---|---|---|---|
| **A1** | Kalman smoother | Smooths jittery cursor. Also predicts 1-2 frames ahead so fast gestures don't lag. | ✅ Fully working | — | Core feel | — |
| **A2** | GA tunes Kalman | Genetic algorithm learns YOUR hand's Q+R noise params over time. Personalizes smoothing. | ⚠️ GA runs but never writes back | Wire 3 lines; close the feedback loop | Personalization | — |
| **A3** | Shadow Tracker | Records where the cursor "should" have been vs where it went. Gives the GA a score to optimize. | ❌ Missing | ~1 day | A2 is useless without this | — |
| **A4** | 1 Euro Filter | Alternative smoother: no lag when moving fast, heavy smoothing when still. Stack on top of Kalman OR replace it. | ❌ Missing | ~2 hours | Better feel, ONLY if MediaPipe isn't already smoothing internally — **needs verification first** | — |
| **A5** | Wood Grain Tuner | Simulates "seasoning" — smoothing loosens as the user racks up hours. | ✅ Exists | Wire to GA profile | Long-term feel improvement | — |
| **A6** | Temporal rollup | Saves per-minute/hour/day snapshots of your tuning profile. | ✅ Exists | Wire to GA profile | Profile persistence | — |
| **B1** | Babylon dots (no physics) | Renders 21 colored dots on the hand skeleton via Babylon.js. Transparent layer over camera. No physics. | ✅ Fully written, implements Plugin | Register 1 line in demo | Visual feedback; prerequisite for B2 | — |
| **B2** | Babylon + Havok physics | Dots become physics balls. Cursor spring-follows your finger with real inertia. Havok engine. | ⚠️ Logic written, wrong interface | Adapt to Plugin interface (~3 hours) | Soft cursor spring, gamification | — |
| **B3** | Wire Babylon into app | Actually turn on B1 or B2 at startup. | ❌ Commented out | 30 min | B1 or B2 going live | — |
| **C1** | GA on background thread | Moves the genetic algorithm off the main thread so it can't freeze the camera at 120Hz. | ⚠️ Worker file exists, path broken | Fix bundler output path | Removes jank during GA evolution | — |
| **C2** | Stop garbage per frame | Pre-allocate typed arrays in the hot path (camera runs 60fps, we allocate small objects every frame). | ❌ Missing | ~4 hours | Removes GC stutters on mobile | — |
| **C3** | Video resolution throttle | Step camera quality down when CPU is overloaded, up when idle. Graceful degradation. | ✅ Exists | Wire to MediaPipe plugin | Thermal stability on phone | — |
| **C4** | Foveated crop / overscan | Zoom visual feed without moving the tracking area. "Zoom in on your hand without breaking MediaPipe." | ✅ Exists | Already wired | — | — |
| **D1** | tldraw iframe delivery | Pointer events sent into the tldraw whiteboard iframe. | ✅ Exists | — | Core loop working | — |
| **D2** | WebRTC (phone → TV) | Send cursor from phone to TV over UDP DataChannel. No cable. | ❌ Stub only | ~3 days full impl | Wireless big-screen mirror | — |
| **E1–E4** | Gesture + FSM | open_palm / pointer_up / fist detection + anti-Midas dwell timer + stillness detection. | ✅ All working | — | Core loop | — |
| **F1** | Settings drawer | Gear button opens a panel with sliders for all tuning params. | ✅ Working | — | — | — |
| **F2** | Cherry MX click audio | Synthesized click sound on pinch. Boot unlock handled. | ✅ Working | — | Feel | — |
| **F3** | Hand skeleton overlay | Draws colored dots + lines on top of camera showing where MediaPipe sees your hand. | ✅ Working | — | Debuggability | — |
| **F4** | HUD overlay | fps / FSM state / cursor position shown in corner. Debug only. | ❌ Missing | ~2 hours | Debuggability | — |
| **F5** | DOM event injection | On pinch, fires real `PointerEvent` at whatever DOM element is under the cursor. | ✅ Working | — | Core interaction | — |

---

## The 5 real decision points

**1. Jitter fix: Kalman-only vs Kalman + 1 Euro**  
Kalman is already wired. 1 Euro could sit on top. The question: does MediaPipe's `HandLandmarker` tasks-vision v0.10.3 already smooth landmarks internally? If yes → adding 1 Euro is double-smoothing and will feel sluggish. If no → 1 Euro is a big feel improvement.  
*Decision: do we check and then add 1 Euro? Or accept Kalman-only for v13?*

**2. Babylon: dots only (B1) vs physics spring (B2)**  
B1 is ready to flip on (30 min). B2 needs ~3 hours of interface work. B2 is what unlocks soft-contact cursor spring.  
*Decision: ship B1 now and leave B2 for next sprint? Or fix B2 now?*

**3. GA feedback loop: wire it or skip it**  
A2+A3 together give you a self-tuning cursor. Without A3 (Shadow Tracker), A2 is just running and wasting CPU. Either close the loop (A2+A3 together, ~2 days) or disable GA entirely for v13.  
*Decision: close the loop now, or defer both A2+A3?*

**4. WebRTC: now or v14**  
Real wireless phone→TV is 3 days of signaling work. Current scope is "single device, mirror to big screen via cable/chromecast."  
*Decision already made (v14) — confirming it stays deferred?*

**5. GC / performance: now or later**  
C2 (TypedArrays) and C1 (Worker path fix) are only noticeable on mid-range phones at 60fps. On modern phones they probably won't matter at v13 demo time.  
*Decision: ship with allocation overhead and fix if it stutters, or pre-empt now?*

---

## Suggested v13 cut if you approve

| Tier 0 (ship it, it works) | Tier 1 (finish this sprint) | Tier 2 (next sprint) | Drop / v14 |
|---|---|---|---|
| A1, C4, D1, E1-E4, F1-F3, F5, G1-G7 | B1+B3 (Babylon dots on), F4 (HUD), C3 (throttle wire-up) | B2 (physics spring), A2+A3 (GA loop), C1 (Worker fix), C2 (TypedArrays), A5+A6 (profile persist) | D2 (WebRTC), A4 (1 Euro — pending MediaPipe smoothing check) |

---

*All code lives at: `hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel/`*
