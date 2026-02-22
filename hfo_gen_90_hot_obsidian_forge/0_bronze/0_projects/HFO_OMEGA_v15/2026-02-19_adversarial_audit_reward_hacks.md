# Omega v13 Microkernel: Adversarial Audit (Reward Hacks)

**Date:** 2026-02-19
**Auditor:** P4 Red Regnant
**Target:** Omega v13 Microkernel (`w3c_pointer_fabric.ts`, `gesture_bridge.ts`, `gesture_fsm.ts`)

## Executive Summary

The current implementation of the Omega v13 Microkernel contains several "reward hacks"—shortcuts taken to achieve functionality quickly at the expense of the core architectural invariants. A true microkernel architecture relies on decoupled components communicating via a shared data fabric (message passing/event bus). The current implementation exhibits tight coupling, monolithic state management, and security boundary violations.

## Finding 1: Tight Coupling (Bypassing the Fabric)

**Location:** `gesture_bridge.ts`

**The Hack:**
`GestureBridge` directly instantiates `GestureFSM` and directly calls methods on `W3CPointerFabric` (`this.pointerFabric.processLandmark(...)`).

**Why it's a violation:**
In a microkernel, components should not know about each other. The "fabric" is supposed to be the intermediary. By directly calling the fabric's methods, the bridge is tightly coupled to a specific implementation of the fabric.

**The Microkernel Solution:**
1.  **Event Bus:** Introduce a true event bus (e.g., `EventTarget` or a custom PubSub system).
2.  **Decoupling:** `GestureBridge` should emit a `HAND_DETECTED` or `HAND_MOVED` event to the bus.
3.  **Subscription:** `W3CPointerFabric` should subscribe to these events on the bus.

## Finding 2: Iframe Piercing Security Violation

**Location:** `w3c_pointer_fabric.ts` (`elementFromPoint` method)

**The Hack:**
The code attempts to pierce iframes by directly accessing `iframe.contentDocument.elementFromPoint(...)`.

**Why it's a violation:**
This is a massive security violation and will fail in production for any cross-origin iframe due to CORS restrictions. The code catches the error and ignores it, meaning cross-origin iframes simply won't work.

**The Microkernel Solution:**
1.  **PostMessage:** The microkernel cannot directly manipulate the DOM of a cross-origin iframe. It must use `window.postMessage`.
2.  **Iframe Agent:** A lightweight script (an "agent") must be injected or included in the iframe's HTML.
3.  **Message Passing:** The `W3CPointerFabric` sends a message (e.g., `{ type: 'POINTER_EVENT', data: ... }`) to the iframe. The agent inside the iframe receives the message and dispatches the synthetic `PointerEvent` locally within its own DOM.

## Finding 3: Monolithic State Logic (Deadman Switch)

**Location:** `gesture_fsm.ts` (`processFrame` method)

**The Hack:**
The "deadman switch" (stillness coast) logic is hardcoded directly into the FSM. It manually calculates the Euclidean distance between frames to determine if the hand is still.

**Why it's a violation:**
This mixes spatial processing (distance calculation) with state logic. The FSM should only care about state transitions based on discrete events, not raw spatial math.

**The Microkernel Solution:**
1.  **Separate Plugin:** Create a `StillnessMonitorPlugin`.
2.  **Event Emission:** This plugin analyzes the raw spatial data stream. If it detects stillness for the threshold duration, it emits a `STILLNESS_DETECTED` event.
3.  **FSM Reaction:** The `GestureFSM` listens for the `STILLNESS_DETECTED` event and transitions to the `COAST` state accordingly.

## Conclusion

To restore the integrity of the Omega v13 Microkernel, these components must be refactored to use a true event-driven shared data fabric. Direct method calls between major components must be eliminated, and cross-boundary communication (iframes) must use standard web security protocols (`postMessage`).