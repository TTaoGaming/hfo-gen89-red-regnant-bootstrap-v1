const { createDefaultPreset } = require("ts-jest");

const tsJestTransformCfg = createDefaultPreset().transform;

/** @type {import("jest").Config} **/
module.exports = {
  testEnvironment: "node",
  transform: {
    ...tsJestTransformCfg,
  },
  // Remap `.js` extension imports → extensionless so ts-jest resolves them as `.ts`.
  // Required because gesture_fsm.ts uses ESM-style `import from './types.js'`.
  moduleNameMapper: {
    "^(.*)\\.js$": "$1",
  },
  // Exclude Playwright E2E specs — they must run via `npx playwright test`, not Jest.
  // Jest crashes with "Playwright Test needs to be invoked via npx playwright test"
  // when it picks up *.spec.ts files from the `tests/` directory.
  // Also exclude *.spec.ts in root — they may import WASM modules (omega_core_rs)
  // that are not built in a Jest environment.
  testPathIgnorePatterns: [
    "/node_modules/",
    "<rootDir>/tests/",
    "\\.spec\\.ts$",
  ],
  testMatch: [
    "**/?(*.)+(test).ts",
    "**/test_*.ts"
  ],
};