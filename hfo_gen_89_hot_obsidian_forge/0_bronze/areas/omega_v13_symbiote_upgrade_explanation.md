---
schema_id: hfo.gen89.omega_v13.symbiote_upgrade.diataxis.v1
medallion_layer: bronze
port: P1
doc_type: explanation
bluf: "Why synthetic PointerEvents fail, what the browser C++ engine provides for free, and how the Stateful Symbiote Agent v2 closes the 10% gap."
tags: omega_v13,pointer_events,symbiote,tldraw,pen_type,pointer_capture,event_cascade,click_synthesizer,highlander,multi_hand
date: 2026-02-20
---

# Understanding the Synthetic Pointer Gap — Omega v13 Symbiote Architecture

> **The thesis is 90% correct.** Hijacking the W3C DOM delivers a universal spatial substrate without requiring native AR/VR SDK access. The 10% gap is that the browser's C++ engine provides 4 invisible behaviors to hardware mice that JavaScript cannot replicate automatically. This document explains each failure mode and the architectural fix.

---

## The Core Insight

A physical mouse has a dedicated kernel-level driver. When the user clicks and drags, the OS maintains a **pointer capture lock** in C++ before any JavaScript fires. Your synthetic events bypass this entirely — JavaScript events are dispatched *above* the C++ layer.

This is not a bug in your architecture. It is the expected boundary between the web platform's JavaScript surface area and its C++ internals. The Stateful Symbiote Agent v2 implements those 4 C++ behaviors manually in the iframe context.

---

## Failure Mode 1: Fast Drag Drop (Missing Pointer Capture)

### What hardware mice get for free
When a user clicks and holds a mouse button, the browser calls `setPointerCapture` in C++. This creates a strict lock: all pointer events for that pointer ID route to the initially-clicked element until the button is released, regardless of where the mouse physically moves. This is how you can drag a slider to the very edge of the screen without "losing" it.

### What breaks with synthetic events
`document.elementFromPoint(x, y)` is called on every `pointermove`. When a child pinches and whips their hand fast across the TV, the visual position races ahead. `elementFromPoint` returns the canvas background. tldraw thinks the user "slipped off" the shape and drops it.

### The fix
The Stateful Symbiote intercepts `Element.prototype.setPointerCapture` and `releasePointerCapture`. When tldraw calls `setPointerCapture(pid)` during a drag, the element is stored in an `activeCaptures` map keyed by pointer ID. All subsequent events route to that element, bypassing `elementFromPoint`, until `releasePointerCapture` is called or `pointerup` fires.

```javascript
Element.prototype.setPointerCapture = function(id) {
  if (id >= 10000) {           // Only intercept our synthetic IDs
    activeCaptures.set(id, this);
    this.dispatchEvent(new PointerEvent('gotpointercapture', ...));
    return;
  }
  try { origSet.call(this, id); } catch (e) {}
};
```

---

## Failure Mode 2: Dead Hover States and Ghost Buttons (Missing Event Cascade)

### What hardware mice get for free
Moving a mouse fires a precisely ordered event symphony: `pointerenter` → `pointermove` → (on enter of new element) `pointerleave` + `pointerenter`. CSS `:hover` responds to these enter/leave events. React's synthetic event system normalizes them into `onMouseEnter`/`onMouseLeave`. Standard HTML `<button>` elements execute their action on the `click` event, which the browser automatically generates after a trusted `pointerup`.

### What breaks with synthetic events
If you only fire `pointermove`, `pointerdown`, and `pointerup`:
1. CSS `:hover` states never animate — no `pointerenter` was sent.
2. React tooltips stay dark — `onMouseEnter` never fires.
3. **HTML buttons do not click.** Native `<button>` tags execute on the `click` event, which the browser only auto-generates after a *trusted* (hardware) `pointerup`. Synthetic `pointerup` does not trigger this cascade.

### The fix
Two additions in the symbiote:

**Hover cascade on pointermove:**
```javascript
const prevTarget = lastHovered.get(pid);
if (prevTarget !== target && eventType === 'pointermove') {
  if (prevTarget) prevTarget.dispatchEvent(new PointerEvent('pointerleave', ...));
  target.dispatchEvent(new PointerEvent('pointerenter', ...));
  lastHovered.set(pid, target);
}
```

**Click synthesizer on pointerup:**
```javascript
if (eventType === 'pointerup') {
  target.dispatchEvent(new MouseEvent('click', {
    bubbles: true, cancelable: true, clientX, clientY, button: 0
  }));
  // Focus text inputs (bypasses isTrusted keyboard requirements)
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
    target.focus();
  }
}
```

---

## Failure Mode 3: Sluggish Cursor (The `pointerType:'touch'` Trap)

### What the browser infers from `pointerType`
When a complex canvas app like tldraw receives a `PointerEvent` with `pointerType:'touch'`, it applies **touch slop**: a 10-pixel deadzone where initial movement is ignored while the browser decides if the user is trying to scroll the page. This is correct behavior for a fat finger on a mobile screen. It is catastrophic for a spatial cursor that must respond to sub-pixel movement immediately.

### The fix: masquerade as Apple Pencil
`pointerType:'pen'` signals to every consumer (tldraw, Excalidraw, Figma, any web canvas) that input is coming from a precision stylus. All deadzones are bypassed. Movement begins at pixel 0. Response is immediate and sub-pixel.

```javascript
// Before (in w3c_pointer_fabric.ts and tldraw_layer.html):
pointerType: 'touch'

// After:
pointerType: 'pen'   // Apple Pencil semantics: zero deadzone, sub-pixel precision
```

This change applies in two places: `w3c_pointer_fabric.ts` `firePointerEvent()` (what gets serialized into the postMessage) and `tldraw_layer.html` (the iframe override — hardcoded to `'pen'` regardless of what the postMessage carries).

---

## Failure Mode 4: Multi-Hand React Panic (Missing Highlander Mutex)

### The two multi-hand bugs

**1. React `isPrimary` panic.** The W3C spec defines exactly one pointer as primary per pointer type. Your logic sends both hands with `isPrimary: true`. React's synthetic event pool uses `isPrimary` to manage its internal pointer state. Two simultaneous `isPrimary: true` events cause a DOM exception and dropped strokes.

**2. MediaPipe index shuffle.** MediaPipe evaluates frames independently. When Hand A (left) crosses over Hand B (right), their array indices swap instantly. `pointerId` is `POINTER_ID_BASE + handId`. The swap causes the two cursors on screen to violently teleport and exchange positions.

### The fix: Highlander V13
A single lock field `primaryHandId: number | null` in `W3CPointerFabric`. The first hand to appear acquires the lock. All subsequent `POINTER_UPDATE` events for other hand IDs are dropped before any processing. When the primary hand disappears (via `removeHand`), the lock releases and the next hand can acquire it.

```typescript
// In onPointerUpdate:
if (this.primaryHandId === null) this.primaryHandId = data.handId;
else if (data.handId !== this.primaryHandId) return;  // Drop second hand

// In removeHand:
if (handId === this.primaryHandId) this.primaryHandId = null;  // Release lock
```

**V14 trajectory:** The second hand will be translated into `WheelEvent` messages for pinch-to-zoom. The index-shuffle problem becomes irrelevant because the second hand only generates zoom deltas, not cursor position.

---

## Architecture Diagram: The Injection Chain (Post-Fix)

```
MediaPipeVisionPlugin
  │  FRAME_PROCESSED (RawHandData[])
  ▼
GestureFSMPlugin
  │  POINTER_UPDATE (handId, x, y, isPinching)
  ▼
W3CPointerFabric.onPointerUpdate()
  │  Highlander check: only primaryHandId passes ─── (drops second hand)
  │  Kalman filter (Q=0.05, R=10.0)
  │  Predictive lookahead (3 steps)
  │  elementFromPoint → iframe found
  │  postMessage({type:'SYNTHETIC_POINTER_EVENT', pointerType:'pen', ...})
  ▼
tldraw_layer.html — Stateful Symbiote Agent v2
  │  Capture routing: activeCaptures.get(pid) ?? elementFromPoint
  │  Hover cascade: pointerleave + pointerenter on target change
  │  Main event dispatch: PointerEvent(type, {pointerType:'pen', ...})
  │  Click synthesizer: MouseEvent('click') on pointerup
  │  Capture cleanup: activeCaptures.delete + lastHovered.delete
  ▼
tldraw React tree (treats input as Apple Pencil)
  → Shape drag held through capture lock
  → Tooltips animate from hover cascade
  → Buttons respond to synthesized click
  → Zero deadzone from pen type
```

---

## What Was Changed

| File | Change | Failure Mode Fixed |
|---|---|---|
| `tldraw_layer.html` | Replaced no-op setPointerCapture with stateful capture polyfill | #1 Fast drag drop |
| `tldraw_layer.html` | Added hover cascade (pointerenter/pointerleave) | #2 Dead hover states |
| `tldraw_layer.html` | Changed `pointerType` from `eventInit.pointerType\|\|'touch'` to hardcoded `'pen'` | #3 Touch deadzone |
| `tldraw_layer.html` | Added click synthesizer + input focus on pointerup | #2 Dead HTML buttons |
| `w3c_pointer_fabric.ts` | Changed `pointerType:'touch'` to `'pen'` in firePointerEvent | #3 Touch deadzone (source) |
| `w3c_pointer_fabric.ts` | Added `primaryHandId` field + Highlander lock in onPointerUpdate/onPointerCoast/removeHand | #4 Multi-hand panic |

---

## What Remains the Same

The full spatial substrate thesis holds:
- Same-origin iframe injection via `postMessage` — no CORS issues
- Only one hand active (V13) — HighlanderMutex enforces this
- Kalman filter + predictive lookahead still active (Q=0.05, R=10.0 tunable via shell)
- PAL contracts for screen dimensions — no raw `window` access
- W3C Level 3 coalesced + predicted event arrays on all dispatched events

---

## V14 Forward Path

| Feature | What it unlocks |
|---|---|
| Second hand → WheelEvents | Pinch-to-zoom in tldraw; rotate gesture |
| GA-evolved Kalman params | Self-tuning Q/R per user's physical tremor profile |
| 1 Euro Filter comparison | Benchmark against Kalman at 30fps; pick winner |
| WebRTC transport | Multi-device — share one hand's cursor to a second display |
