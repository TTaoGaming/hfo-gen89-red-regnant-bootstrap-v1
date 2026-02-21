---
schema_id: hfo.gen89.diataxis.v1
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "Reference: Omega v13 5-Layer Z-Stack and Strict Linear Pipeline for Babylon.js + Havok + W3C PointerEvents integration."
---

# REFERENCE: Omega v13 Babylon.js + W3C Pointer Pipeline

## 1. The Z-Stack Compositor (Visual Architecture)

The DOM must be structured with strict `pointer-events` control to ensure the W3C Fabric catches events while Babylon renders the visual cursor.

| Z-Index | Layer Name | Tech | `pointer-events` | Purpose |
| --- | --- | --- | --- | --- |
| **`z=0`** | **VIDEO_BG** | `<video>` | `none` | The Substrate. Mirrored and scaled (Overscan) via CSS so edge gestures work. |
| **`z=10`** | **W3C_FABRIC** | *Logical* | `none` | Invisible. Reads Babylon's physical output and injects DOM events. |
| **`z=20`** | **TLDRAW** | `<iframe>` | **`auto`** | The "dumb consumer" target. Catches the W3C pointers. |
| **`z=30`** | **UI_SHELL** | `<div>` | `none`* | The OS interface. (*Children like buttons are `auto`). |
| **`z=40`** | **BABYLON** | `<canvas>` | `none` | **Transparent background.** Renders the skeleton & Havok cursor exactly on top of everything. |

## 2. The Strict Linear Pipeline

Data flows strictly in one direction across the EventBus to prevent visual cursor and DOM click divergence:

`Camera` ➔ `MediaPipe (Mirror/Overscan Math)` ➔ `FSM (Intent)` ➔ `Babylon (Havok Mass/Springs)` ➔ `W3C Fabric (Iframe Click)`

### 2.1. Universal Substrate Math (MediaPipe)

Handles Mirror (`scaleX(-1)`) and Overscan Zoom before data hits the bus.

```typescript
// ── WYSIWYG OVERSCAN + MIRROR PARITY MATH ──
const scale  = this.context.pal.resolve<number>('OverscanScale') ?? 1.2;
const offset = (1.0 - (1.0 / scale)) / 2.0;

const tip = landmarks[8]; // Index fingertip

// 1. MIRROR X: The video element has CSS scaleX(-1), so we invert X mathematically.
const mirroredX = 1.0 - tip.x;

// 2. APPLY OVERSCAN 
const mappedX = (mirroredX - offset) * scale;
const mappedY = (tip.y - offset) * scale;

// 3. Mirror & Scale the whole skeleton for Babylon to render 1:1
const mappedLandmarks = landmarks.map((pt: any) => ({
    ...pt,
    x: ((1.0 - pt.x) - offset) * scale,
    y: (pt.y - offset) * scale,
    z: pt.z * scale // Scale depth proportionally
}));

return {
    handId: index, gesture: rawGesture, confidence: maxScore,
    x: mappedX, y: mappedY, rawLandmarks: mappedLandmarks,
};
```

### 2.2. Orthographic Physics Engine (Babylon.js)

Uses an Orthographic Camera mapped exactly to `window.innerWidth/Height`. Babylon calculates physics and publishes the actual physical pixel location back to the bus.

```typescript
// Setup Orthographic Camera
const cam = new ArcRotateCamera("cam", -Math.PI/2, Math.PI/2, 10, Vector3.Zero(), this.scene);
cam.mode = Camera.ORTHOGRAPHIC_CAMERA;

const updateCamera = () => {
    const w = this.context.pal.resolve<number>('ScreenWidth') || window.innerWidth;
    const h = this.context.pal.resolve<number>('ScreenHeight') || window.innerHeight;
    cam.orthoLeft = 0;   cam.orthoRight = w;
    cam.orthoTop = 0;    cam.orthoBottom = -h; // 3D Y goes UP, DOM Y goes DOWN. We invert Y here.
};
updateCamera();

// Broadcast to Fabric
private broadcastToFabric() {
    for (const [id, target] of this.targets.entries()) {
        const cursor = this.handMeshes.get(id)?.[8];
        if (cursor) {
            this.context.eventBus.publish('PHYSICS_POINTER_MOVED', {
                handId: id,
                pixelX: cursor.position.x,
                pixelY: Math.abs(cursor.position.y), // Undo the 3D Y-inversion
                isPinching: target.isPinching
            });
        }
    }
}
```

### 2.3. W3C Fabric Shift

The W3C Fabric listens to Babylon Physics, not the raw camera pipeline. Havok's mass acts as the filter.

```typescript
public init(context: PluginContext): void {
    this.context = context;
    // Listen to Babylon Physics, NOT the raw camera pipeline!
    context.eventBus.subscribe('PHYSICS_POINTER_MOVED', this.onPhysicsMoved.bind(this));
}

private onPhysicsMoved(data: any) {
    const pointerId = this.POINTER_ID_BASE + data.handId;
    
    // Clamp to screen bounds to prevent off-screen document.elementFromPoint exceptions
    const finalX = Math.max(0, Math.min(window.innerWidth - 1, data.pixelX));
    const finalY = Math.max(0, Math.min(window.innerHeight - 1, data.pixelY));

    this.dispatchEvents(pointerId, finalX, finalY, data.isPinching, []);
}
```
