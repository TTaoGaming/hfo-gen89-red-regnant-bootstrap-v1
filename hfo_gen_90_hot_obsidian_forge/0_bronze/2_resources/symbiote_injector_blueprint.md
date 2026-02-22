# CORE-4: W3C Level 3 Symbiote Injector Blueprint

**TARGET:** Guest Context (Injected into `tldraw` iframe)
**OBJECTIVE:** Flawless synthetic W3C PointerEvent generation for passive stylus tracking.

Here is the strict technical blueprint to resolve the 4 Synthetic Pointer Failure Modes. Hand this directly to Agent 1 for implementation.

---

### 1. Pointer Capture (The Mid-Air Drop Fix)
**Problem:** Native `setPointerCapture` throws `DOMException: InvalidStateError` for untrusted events or inactive pointer IDs. Fast drags escape the target element.
**Solution:** Monkey-patch the Element prototype within the Guest context to intercept capture requests and route events manually.

```javascript
// Symbiote State
const symbioteState = {
  capturedTarget: null,
  capturedPointerId: null,
  lastHovered: null
};

// 1. Monkey-patch Capture API
const originalSetCapture = Element.prototype.setPointerCapture;
const originalReleaseCapture = Element.prototype.releasePointerCapture;

Element.prototype.setPointerCapture = function(pointerId) {
  if (pointerId >= 10000) { // Our synthetic ID range
    symbioteState.capturedTarget = this;
    symbioteState.capturedPointerId = pointerId;
    // Dispatch synthetic gotpointercapture
    this.dispatchEvent(new PointerEvent('gotpointercapture', { pointerId, bubbles: true }));
    return;
  }
  return originalSetCapture.call(this, pointerId);
};

Element.prototype.releasePointerCapture = function(pointerId) {
  if (pointerId >= 10000 && symbioteState.capturedPointerId === pointerId) {
    const target = symbioteState.capturedTarget;
    symbioteState.capturedTarget = null;
    symbioteState.capturedPointerId = null;
    target?.dispatchEvent(new PointerEvent('lostpointercapture', { pointerId, bubbles: true }));
    return;
  }
  return originalReleaseCapture.call(this, pointerId);
};
```

### 2. Event Cascade (The Boundary Crossing)
**Problem:** Raw x/y coordinates don't trigger the `pointerenter`/`pointerleave` cascade required by React/tldraw hover states.
**Solution:** Compute the target per-frame, diff against the last known element, and synthesize the boundary cascade BEFORE the `pointermove`.

```javascript
function dispatchSyntheticMove(x, y, pointerId) {
  // 1. Determine Target: Use captured target OR calculate from point
  const target = symbioteState.capturedTarget || document.elementFromPoint(x, y) || document.body;
  
  // 2. Handle Boundary Cascade
  if (symbioteState.lastHovered !== target) {
    if (symbioteState.lastHovered) {
      symbioteState.lastHovered.dispatchEvent(createPointerEvent('pointerout', x, y, pointerId));
      symbioteState.lastHovered.dispatchEvent(createPointerEvent('pointerleave', x, y, pointerId, { bubbles: false }));
    }
    target.dispatchEvent(createPointerEvent('pointerover', x, y, pointerId));
    target.dispatchEvent(createPointerEvent('pointerenter', x, y, pointerId, { bubbles: false }));
    symbioteState.lastHovered = target;
  }

  // 3. Dispatch Actual Move
  target.dispatchEvent(createPointerEvent('pointermove', x, y, pointerId));
}
```

### 3. Trust & Focus (The Potemkin Bypass)
**Problem:** `event.isTrusted` is strictly `false`. Elements won't receive focus, breaking keyboard shortcuts and text inputs in `tldraw`.
**Solution:** Force manual focus during the `pointerdown` phase. If strict React event delegation blocks the event due to `isTrusted`, use `Object.defineProperty` to spoof it on the event instance (works in most Chromium contexts for synthetic events).

```javascript
function dispatchSyntheticDown(x, y, pointerId) {
  const target = document.elementFromPoint(x, y) || document.body;
  
  // 1. Force Focus
  if (typeof target.focus === 'function') {
    target.focus({ preventScroll: true });
  }

  // 2. Create Event & Spoof Trust (if required by strict frameworks)
  const event = createPointerEvent('pointerdown', x, y, pointerId, { button: 0, buttons: 1 });
  
  try {
    Object.defineProperty(event, 'isTrusted', { get: () => true });
  } catch (e) { /* Ignore if sealed */ }

  target.dispatchEvent(event);
}
```

### 4. Pen Mode (The Inking Enforcer)
**Problem:** `tldraw` defaults to panning the canvas unless it explicitly detects a stylus.
**Solution:** The `createPointerEvent` factory MUST hardcode `pointerType: 'pen'` and provide valid `pressure` and `buttons` states.

```javascript
function createPointerEvent(type, x, y, pointerId, overrides = {}) {
  return new PointerEvent(type, {
    pointerId: pointerId,
    pointerType: 'pen', // CRITICAL: Forces tldraw into draw mode instead of pan
    isPrimary: true,
    clientX: x,
    clientY: y,
    screenX: x,
    screenY: y,
    bubbles: true,
    cancelable: true,
    composed: true,     // CRITICAL: Penetrate Shadow DOMs
    pressure: overrides.buttons ? 0.5 : 0, // 0.5 when drawing, 0 when hovering
    button: -1,         // Default to no button
    buttons: 0,         // Default to no buttons pressed
    ...overrides
  });
}
```

### Implementation Directives for Agent 1:
1. Wrap this logic in a `SymbioteInjector` class.
2. Expose a `receiveHostMessage(payload)` method to accept `[x, y, state]` tuples from the Host via `window.postMessage`.
3. Map Host states (`HOVER`, `DRAW`) to the correct synthetic event sequences (`pointermove` vs `pointerdown` + `pointermove` with `buttons: 1`).
