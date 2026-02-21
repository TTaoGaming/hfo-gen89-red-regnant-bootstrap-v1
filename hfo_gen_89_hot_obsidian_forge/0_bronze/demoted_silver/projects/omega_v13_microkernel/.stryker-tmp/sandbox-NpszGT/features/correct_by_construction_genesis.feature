Feature: Correct-by-Construction (CbC) Genesis
  As a system architect
  I want to enforce structural constraints (Vocabulary Deprivation, Typestate, Defunctionalization, Chaos Inoculation)
  So that LLM malicious compliance and invalid states are mathematically unrepresentable and uncompilable.

  @cbc @vocabulary-deprivation
  Scenario: Vocabulary Deprivation (Compiler-Level OCap)
    Given the Omega v13 microkernel `tsconfig.json`
    When the compiler options are evaluated
    Then the `lib` array MUST NOT contain `"DOM"`
    And any reference to `window` or `document` in the microkernel source MUST trigger a compilation error
    And the microkernel MUST rely exclusively on `PluginContext.pal` for DOM interactions

  @cbc @typestate @branded-types
  Scenario: The Galois Lattice in Types (Typestate & Branding)
    Given the Omega v13 microkernel type definitions
    When coordinate data is passed between plugins
    Then primitive `number` types MUST NOT be used for coordinates
    And coordinates MUST use Branded Types (e.g., `RawCoord`, `SmoothedCoord`, `ScreenPixel`)
    And the FSM MUST use the Typestate Pattern (e.g., `class StateIdle`, `class StateReady`)
    And invalid state transitions (e.g., `StateIdle` to `StateCommit`) MUST trigger a compilation error

  @cbc @defunctionalization
  Scenario: Defunctionalization (Model-Driven Genesis)
    Given the Omega v13 gesture FSM
    When the FSM logic is generated
    Then the source of truth MUST be the `gesture_fsm.scxml` statechart
    And the TypeScript implementation MUST be auto-generated from the SCXML
    And manual edits to the generated FSM TypeScript MUST be forbidden or overwritten by the build step

  @cbc @chaos-inoculation @pbt
  Scenario: Chaos Inoculation (Property-Based Fuzzing)
    Given the Omega v13 test suite
    When the W3C Pointer Fabric and Kalman Filter are tested
    Then static "happy path" examples MUST be replaced or augmented with Property-Based Tests (PBT) using `fast-check`
    And the PBT MUST generate 10,000 chaotic inputs (NaN, Infinity, negative arrays, out-of-bounds)
    And the tests MUST assert mathematical invariants (e.g., `variance(output) < variance(input)`, bounds maintained)
