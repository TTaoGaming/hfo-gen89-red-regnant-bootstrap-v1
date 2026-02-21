---
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.mosaic_microkernel_header.v3
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "Master Swarm Directive: Omega v13 Launch Invariants (ATDD Enforcement). 6 Gherkin specifications that mathematically prevent AI agents from bypassing Host/Guest architecture, GC-heavy hot loops, and React internal crashes."
primary_port: P4
secondary_ports: [P2, P5]
role: "P4 DISRUPT — red team/probing — adversarial coaching protocol"
diataxis_type: reference
tags: [bronze, forge:hot, para:areas, diataxis:reference, p2, p4, p5, omega, gen13, atdd, sbe, invariants, swarm, directive, fsm, w3c, babylon, overscan]
generated: "2026-02-20"
status: DRAFT — operator review required
---

# SYSTEM DIRECTIVE: OMEGA V13 LAUNCH INVARIANTS (ATDD ENFORCEMENT)
**Target:** IDE Copilot Swarm (All Daemons)
**Priority:** LEVEL 6 LEVERAGE (System Rules & Information Flow)

## CONTEXT
You are operating on the Omega v13 Spatial OS. Previous iterations generated monolithic "happy path" code that violated deep system constraints (GC-heavy hot loops, React internal crashes, DOM abstraction leaks, and missing FSM states). 

**Your Directive:** You are strictly forbidden from writing business logic before writing the ATDD/SBE tests that govern it. You will execute a RED -> GREEN -> REFACTOR cycle based on the 6 Gherkin Specifications below.

## STEP 1: INGEST THE INVARIANTS (THE 6 SBEs)
Create a new test file: `tests/launch_invariants.spec.ts`. Translate the following 6 scenarios into strict executable tests (Jest). 

### SPEC 1: The Viewport Geometry Constraint (Anti-Drift)
```gherkin
Feature: PAL Viewport Binding
  Scenario: PAL resolves true CSS Viewport, not physical screen
    Given the bootstrapper `demo_2026-02-20.ts` registers ScreenWidth and ScreenHeight into the PAL
    When the source code of `demo_2026-02-20.ts` is statically analyzed
    Then it MUST NOT contain `window.screen.width` or `window.screen.height`
    And it MUST contain `window.innerWidth` and `window.innerHeight`
    And it MUST bind a 'resize' event listener to dynamically update the PAL dimensions
```

### SPEC 2: The Z-Stack Penetration Constraint (Anti-Invisible Wall)
```gherkin
Feature: Z-Stack Event Permeability
  Scenario: UI layers default to pointer-events none
    Given the `LayerManager` initializes the Z-Stack
    When the default `LAYER.SETTINGS` descriptor is queried in `layer_manager.ts`
    Then its `pointerEvents` property MUST explicitly equal 'none'
```

### SPEC 3: The Synthetic Pointer Compatibility Constraint (React Survival)
```gherkin
Feature: Iframe Symbiote React Compatibility
  Scenario: Symbiote polyfills capture and maps button state
    Given the Symbiote Agent code in `tldraw_layer.html`
    When the source code is analyzed
    Then it MUST map `eventInit.buttons > 0` to `button: 0` (main click) to trigger ink
    And `Element.prototype.setPointerCapture` MUST be polyfilled globally to catch/swallow exceptions for IDs >= 10000
    And `Element.prototype.releasePointerCapture` MUST be similarly polyfilled
```

### SPEC 4: The GC Zero-Allocation Constraint (Anti-Meltdown)
```gherkin
Feature: Hot-Loop Memory Stability
  Scenario: W3CPointerFabric skips heavy reflection validation in hot loops
    Given the `W3CPointerFabric` is processing `POINTER_UPDATE` events
    When the source code of `w3c_pointer_fabric.ts` is statically analyzed
    Then it MUST NOT import `zod` or `PointerUpdateSchema`
    And the `onPointerUpdate` and `onPointerCoast` methods MUST NOT contain `.parse()`
```

### SPEC 5: The Orthogonal Intent Constraint (Anti-Thrash FSM)
```gherkin
Feature: Orthogonal Defense-in-Depth FSM
  Scenario: Strict State Routing (No Teleportation)
    Given the `GestureFSM` is in the `IDLE` state
    When it receives highly confident `pointer_up` gestures
    Then the FSM MUST remain in `IDLE` (IDLE to COMMIT is an illegal transition)
  
  Scenario: Independent Leaky Buckets (Anti-Thrash)
    Given the FSM is in `COMMIT_POINTER`
    When the FSM receives `open_palm` frames
    Then the internal READY bucket MUST fill
    And the IDLE bucket MUST NOT fill
    And returning to `pointer_up` MUST aggressively leak/drain the opposing buckets
```

### SPEC 6: Thermal Physics Scaling (The Battery Melter)
```gherkin
Feature: Mobile-Safe Physics Scaling
  Scenario: Babylon physics is quarantined from the 2D launch bootstrapper
    Given the `demo_2026-02-20.ts` bootstrapper
    When the source code is analyzed
    Then it MUST NOT register or instantiate `BabylonPhysicsPlugin`
    And it MUST NOT call `startBabylon()`
    Because 3D Havok physics running concurrently with WebRTC cast melts mobile batteries.
```

---

## STEP 2: EXECUTION PROTOCOL FOR DAEMONS

1. **Write the Tests (RED):** Write `tests/launch_invariants.spec.ts`. Use AST/string matching (e.g., `fs.readFileSync`) for Specs 1, 3, 4, 6 to enforce what the source code *must not* contain. Use unit logic for Specs 2 and 5.
2. **Verify Failure:** Run the test suite. Confirm it fails against the current codebase.
3. **Mutate the Source (GREEN):** Refactor `demo_2026-02-20.ts`, `layer_manager.ts`, `tldraw_layer.html`, `w3c_pointer_fabric.ts`, and `gesture_fsm.ts` until every single test passes.
4. **Halt:** DO NOT write any feature code until the test suite demands it. Output the final passing test results and the modified source files.

***

### Why this forces the LLM to behave:

When your swarm runs this prompt, they aren't just writing code anymore; they are navigating an automated maze where the only exit is correct, GC-friendly, React-safe architecture. 

1. **Spec 1, 3, 4, & 6 are AST validations.** By forcing the AI to write a test that uses Node's `fs` to read its *own source code* as a string, you physically prevent the daemons from sneaking heavy libraries (`Zod`) into your hot paths or hardcoding `screen.width`. They cannot lie because the test suite reads the raw text of their files.
2. **Spec 5** forces the AI to rip out its own single-bucket FSM and build the orthogonal, multi-bucket intent router you actually designed, proving it in memory before touching the DOM.

Let the daemons write the tests, run the suite, and watch them cleanly refactor their own lies to turn it green.
