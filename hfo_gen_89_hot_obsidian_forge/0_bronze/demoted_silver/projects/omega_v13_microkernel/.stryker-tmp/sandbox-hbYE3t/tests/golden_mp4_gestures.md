---
schema_id: hfo.gen89.diataxis.v1
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "Reference: Golden MP4 Gesture Sequence for Omega v13 Babylon.js + W3C Pointer Pipeline Testing."
---

# REFERENCE: Golden MP4 Gesture Sequence for Omega v13

To fully test the 5-Layer Z-Stack, the FSM, the Babylon.js physics engine, and the W3C Pointer Fabric, we need a "Golden MP4" recording. This recording will be fed into MediaPipe to generate deterministic JSON landmarks for our Playwright SBE/ATDD test suite.

## The Golden Sequence (2 Hands)

This sequence is designed to test all edge cases: idle states, intent locking, physics inertia, multi-hand collision, and edge gestures (overscan).

### Phase 1: Single Hand Calibration & Intent (0:00 - 0:10)
1. **Idle Entry**: Right hand enters the frame from the bottom, open palm. (Tests: `POINTER_ENTER`, initial Havok cursor spawn).
2. **Hover & Move**: Move the open palm slowly across the screen. (Tests: `POINTER_MOVE`, Havok spring following the visual dots).
3. **Intent Lock (Pinch)**: Pinch index and thumb together. (Tests: FSM transition to `COMMIT_POINTER`, Havok cursor color/scale change, W3C `pointerdown`).
4. **Drag**: Move the pinched hand. (Tests: W3C `pointermove` while down, dragging elements in tldraw).
5. **Release**: Open the hand. (Tests: FSM transition to `READY`, W3C `pointerup`).

### Phase 2: Edge Gestures & Overscan (0:10 - 0:20)
6. **Off-Screen Exit**: Move the right hand completely off the right edge of the camera frame. (Tests: `POINTER_LEAVE`, Havok cursor destruction/hiding).
7. **Overscan Entry**: Bring the right hand back in from the top edge, already pinched. (Tests: Overscan math mapping coordinates correctly, immediate `pointerdown` on entry).

### Phase 3: Multi-Hand & Physics Constraints (0:20 - 0:35)
8. **Bimanual Entry**: Both left and right hands enter the frame, open palms. (Tests: Two independent Havok cursors spawned, two W3C pointers tracked).
9. **Bimanual Pinch**: Pinch both hands simultaneously. (Tests: Multi-touch `pointerdown` events).
10. **Collision Course**: Move both pinched hands towards each other until they cross paths. (Tests: Havok physics collision constraints—do the cursors bounce off each other or pass through? W3C pointers should track the physical cursors, not just the raw landmarks).
11. **Asymmetric State**: Left hand opens (idle), right hand remains pinched (dragging). (Tests: Independent FSM state tracking per hand).

### Phase 4: Edge Cases & Noise (0:35 - 0:45)
12. **Occlusion**: Pass one hand completely in front of the other. (Tests: MediaPipe tracking loss/recovery, FSM hysteresis preventing rapid state thrashing).
13. **Fast Flick**: Flick the right hand extremely fast across the screen. (Tests: Havok `maxVelocity` clamping, ensuring the cursor doesn't break the physics simulation or fly off-screen).
14. **Exit**: Both hands drop out of frame. (Tests: Clean teardown of all pointers and physics meshes).

## How to Use This MP4
1. Record the video following the sequence above.
2. Run the video through a headless MediaPipe script to extract the raw JSON landmarks per frame.
3. Feed the JSON array into the Playwright test suite, injecting the frames into the `EventBus` at 30fps.
4. Assert that the resulting W3C pointer events match the expected sequence.
