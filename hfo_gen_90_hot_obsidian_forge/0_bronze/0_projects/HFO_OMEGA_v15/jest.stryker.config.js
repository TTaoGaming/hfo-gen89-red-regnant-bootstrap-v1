/**
 * jest.stryker.config.js
 *
 * Stryker-specific Jest configuration.
 * Only runs test files for tiles currently being mutation-tested.
 * This prevents Stryker from hitting spec files that depend on unbuilt
 * WASM modules (omega_core_rs, babylon_physics) which would crash the
 * dry-run phase.
 *
 * HFO v15 | PREY8 nonce E8CA8B | Gen90
 * DO NOT use this config for regular Jest runs — use jest.config.js.
 * UPDATE testMatch here as new tiles are hardened.
 */

const { createDefaultPreset } = require("ts-jest");

const tsJestTransformCfg = createDefaultPreset().transform;

/** @type {import("jest").Config} **/
module.exports = {
  testEnvironment: "node",
  transform: {
    ...tsJestTransformCfg,
  },
  // Remap `.js` extension imports → extensionless so ts-jest resolves them as `.ts`.
  moduleNameMapper: {
    "^(.*)\\.js$": "$1",
  },
  testPathIgnorePatterns: [
    "/node_modules/",
  ],
  // ── STRYKER ACTIVE TILES ──────────────────────────────────────────────────
  // Add new tiles here as they enter the mutation-testing queue.
  // Remove tiles that have graduated to 'hardened' status.
  testMatch: [
    "**/test_kalman_filter.test.ts",
    "**/test_event_bus.test.ts",
    "**/test_plugin_supervisor.ts",
    "**/event_bus.spec.ts",
  ],
};
