# correct_by_construction_structural_fixes.feature
#
# SBE / ATDD for the L8 + L5 structural fixes applied 2026-02-20.
# These are NOT parameter tweaks — they are enforcement changes.
# If a spec here is RED, the system has a structural defect.
#
# Red Regnant P4 session: "any enforcement not structurally enforced is a time bomb"
# Meadows L8 (rules) + L5 (negative feedback) — not L1 (parameters).

Feature: Microkernel MOSAIC — Correct-by-Construction Structural Enforcement

  Background:
    Given the omega_v13_microkernel TypeScript project compiles with zero tsc errors
    And all plugins implement the Plugin interface lifecycle contract
    And no plugin imports globalEventBus (deleted singleton — ATDD-ARCH-001)

  # ── FIX-ARCH-S1: babylon_landmark_plugin.ts ──────────────────────────────

  Scenario: [S1] BabylonLandmarkPlugin wires FRAME_PROCESSED to context.eventBus
    Given BabylonLandmarkPlugin previously imported the deleted globalEventBus singleton
    When PluginSupervisor.initAll() calls init(context) on BabylonLandmarkPlugin
    Then BabylonLandmarkPlugin stores the injected context
    And start() subscribes this.context.eventBus.subscribe('FRAME_PROCESSED')
    And stop() calls this.context.eventBus.unsubscribe('FRAME_PROCESSED')
    And destroy() calls this.context.eventBus.unsubscribe('FRAME_PROCESSED')
    And tsc --noEmit reports zero errors for babylon_landmark_plugin.ts

  Scenario: [S1-GRUDGE] BabylonLandmarkPlugin must NOT reference globalEventBus
    Given the globalEventBus export has been removed from event_bus.ts
    When tsc --noEmit is executed
    Then no error "has no exported member 'globalEventBus'" appears for babylon_landmark_plugin.ts

  # ── FIX-ARCH-S2: gesture_bridge.ts ───────────────────────────────────────

  Scenario: [S2] GestureBridge accepts EventBus via constructor injection
    Given GestureBridge previously called globalEventBus.publish (deleted)
    When GestureBridge is constructed with an explicit EventBus instance
    Then processFrame() publishes FRAME_PROCESSED on the injected EventBus
    And no singleton state is shared with any other GestureBridge instance
    And tsc --noEmit reports zero errors for gesture_bridge.ts

  Scenario: [S2-ISOLATION] Two GestureBridge instances with different buses do not cross-talk
    Given Bridge A has EventBus-1 and Bridge B has EventBus-2
    When Bridge A processes a frame
    Then EventBus-1 receives FRAME_PROCESSED
    And EventBus-2 receives nothing

  Scenario: [S2-COMPAT] GestureBridge constructed without args uses its own private EventBus
    Given no EventBus is passed to the GestureBridge constructor
    When GestureBridge is instantiated
    Then it creates an internal EventBus and publishes to it on processFrame
    And the constructor does not throw

  # ── FIX-ARCH-S3: mediapipe_vision_plugin.ts type fix ─────────────────────

  Scenario: [S3] MediaPipeVisionPlugin loads in Node/Jest without browser globals
    Given DEFAULT_CONFIG was typed as Required<MediaPipeVisionConfig> which forced videoElement
    When tryRequire('./mediapipe_vision_plugin') is called in a Jest test environment
    Then the module loads without a TypeScript compile error
    And MediaPipeVisionPlugin class is exported and instantiable
    And new MediaPipeVisionPlugin() does not throw

  Scenario: [S3-V2-GREEN] ATDD-ARCH-002 V2 god-object tests execute (no longer return null)
    Given mediapipe_vision_plugin.ts compiles cleanly
    When microkernel_arch_violations.spec.ts ATDD-ARCH-002 suite runs
    Then tryRequire('./mediapipe_vision_plugin') returns a non-null module
    And MediaPipeVisionPlugin implements the Plugin interface

  Scenario: [S3-V3-GREEN] ATDD-ARCH-003 V3 double-debounce test verifies no gestureBuckets
    Given MediaPipeVisionPlugin is loadable
    When new MediaPipeVisionPlugin() is instantiated in a test
    Then (plugin as any).gestureBuckets is undefined
    And injectTestFrame() publishes FRAME_PROCESSED immediately on frame 1

  # ── FIX-ARCH-W1: isCoasting() gate — W-HIGH-001 ──────────────────────────

  Scenario: [W1] GestureFSM exposes public isCoasting()
    Given GestureFSM previously had no public isCoasting() method
    When fsm.state is 'IDLE_COAST' or 'READY_COAST' or 'COMMIT_COAST'
    Then fsm.isCoasting() returns true
    And when fsm.state is 'IDLE' or 'READY' or 'COMMIT_POINTER'
    Then fsm.isCoasting() returns false

  Scenario: [W1-PINCH-COAST] isPinching() and isCoasting() together identify COMMIT_COAST
    Given a GestureFSM in state COMMIT_COAST
    When isPinching() and isCoasting() are both called
    Then isPinching() returns true
    And isCoasting() returns true
    And this is the specific state that triggers the ghost-draw teleport risk

  Scenario: [W1-GATE] Velocity teleport gate fires on coast recovery with large jump
    Given a hand is in COMMIT_COAST at normalised position (0.1, 0.5)
    And the hand exits the camera frame (confidence < 0.5)
    When the hand re-enters at normalised position (0.9, 0.5) — an 80% horizontal jump
    And COMMIT_COAST recovers to COMMIT_POINTER
    Then GestureFSMPlugin emits a synthetic POINTER_UPDATE with isPinching=false at (0.1, 0.5)
    And the next POINTER_UPDATE with isPinching=true is at (0.9, 0.5)
    And no pointerdown-to-pointerdown ghost stroke is drawn on the canvas

  Scenario: [W1-GRUDGE] Normal coast recovery with small position delta must NOT fire synthetic pointerup
    Given a hand is in COMMIT_COAST at position (0.5, 0.5)
    When the hand recovers to COMMIT_POINTER at position (0.52, 0.51) — a 2% jump
    Then no synthetic POINTER_UPDATE with isPinching=false is emitted
    And the W3C pointer stream continues the stroke without interruption

  Scenario: [W1-LOCATION] isCoasting() gate is structurally in gesture_fsm_plugin.ts
    Given gesture_bridge.ts is zombie code with a broken globalEventBus import
    When the velocity teleport gate is applied
    Then it lives in GestureFSMPlugin.onFrameProcessed() only
    And gesture_bridge.ts is NOT the gate enforcement site

  # ── FIX-STRYKER-S4: Mutation testing expanded to gesture pipeline ─────────

  Scenario: [S4] Stryker mutate array includes gesture_fsm.ts
    Given gesture_fsm.ts previously had zero mutation test coverage
    When stryker.config.json is updated
    Then the mutate array contains "gesture_fsm.ts"
    And the mutate array contains "gesture_fsm_plugin.ts"
    And the mutate array contains "mediapipe_vision_plugin.ts"
    And npx stryker run uses npx jest as the test command (not ts-node scripts)

  Scenario: [S4-GATE] L1 parameter changes are gated behind Stryker green
    Given W-MED-001 (palmWidth lm[5]→lm[0]/lm[9]) and W-MED-002 (thumbMiddle lm[12]→lm[9]) are known issues
    When a developer considers making the landmark parameter change
    Then they MUST have gesture_fsm.ts in the Stryker mutate array first
    And at least one Jest test that exercises the classifyHand() scoring path
    And the mutation score must be >= 60% before the parameter is promoted

  # ── GRUDGE regression guards ──────────────────────────────────────────────

  Scenario: [GRUDGE-1] globalEventBus export must never be re-added to event_bus.ts
    Given event_bus.ts exports only EventBus class and EventCallback type
    When any developer adds "export const globalEventBus" to event_bus.ts
    Then the ATDD-ARCH-001 suite must immediately turn RED
    And tsc --noEmit will pass (the singleton itself is valid TypeScript)
    But the arch violation spec is the structural guard against its re-introduction

  Scenario: [GRUDGE-2] Plugin init() must never use _ctx (ignored parameter pattern)
    Given init(_ctx: PluginContext) ignores the injected context
    When a plugin stores nothing from _ctx
    Then it will inevitably reach for a global — the ignored parameter IS the violation
    And code review must reject any init() with an underscore-prefixed context parameter

  Scenario: [GRUDGE-3] DEFAULT_CONFIG must not use Required<T> for types with optional DOM refs
    Given Required<MediaPipeVisionConfig> forces HTMLVideoElement into defaults
    When the test environment has no DOM
    Then ts-jest bails on compilation and tryRequire() returns null silently
    And ATDD tests are bypassed instead of failing — the worst kind of false RED
