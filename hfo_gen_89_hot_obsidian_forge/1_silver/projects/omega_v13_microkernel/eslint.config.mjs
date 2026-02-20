import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  // ── GLOBAL IGNORES: compiled/bundled output, vendor ─────────────────────
  {
    ignores: ['dist/**', 'exemplars/**', 'node_modules/**', 'jest.config.js', 'stryker.config.mjs'],
  },

  // ── BASE RULES: ESLint + TypeScript-ESLint recommended ──────────────────
  eslint.configs.recommended,
  ...tseslint.configs.recommended,

  // ── GLOBAL OVERRIDES: tune noise, fix browser-env false positives ───────
  {
    rules: {
      // TypeScript handles undefined-variable checking at type level
      'no-undef': 'off',
      // Code-quality hints — not arch gates; violations are warnings not blockers
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': 'warn',
    },
  },

  // ── ARCH RULE P4/V1: Guest zone plugins must not touch DOM directly ──────
  // Apply ONLY to *_plugin.ts files (the Guest zone).
  // These receive browser capabilities via PluginContext.pal, not globals.
  {
    files: ['**/*_plugin.ts'],
    rules: {
      'no-restricted-globals': [
        'error',
        {
          name: 'window',
          message:
            'ARCH-V5: Use pal.resolve("ScreenWidth") etc. instead of window. ' +
            'Plugins must receive Host capabilities via PluginContext.pal.',
        },
        {
          name: 'document',
          message:
            'ARCH-V5: Request DOM refs via PluginContext.pal instead of document. ' +
            'Plugins must not query the DOM directly.',
        },
        {
          name: 'globalThis',
          message: 'ARCH-V5: Use pal.resolve() instead of globalThis in plugins.',
        },
      ],
      // ARCH-V4: Plugins must not import each other — only via EventBus
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['*_plugin'],
              message:
                'ARCH-V4: Plugins must not import other plugins directly. ' +
                'Communicate via context.eventBus.',
            },
          ],
        },
      ],
    },
  },

  // ── HOST-BOUNDARY EXCEPTIONS ─────────────────────────────────────────────
  // These *_plugin.ts files are Host-facing adapters that bridge to browser APIs.
  // They MUST use DOM/camera APIs by nature — PAL is the wrong layer for them.
  // Doc: ATDD-ARCH-002 describes MediaPipeVisionPlugin as the Host sensor.
  {
    files: [
      'mediapipe_vision_plugin.ts', // Host sensor — camera + MediaPipe
      'visualization_plugin.ts',    // Host renderer — dot/ring HUD in DOM
      'babylon_landmark_plugin.ts', // Host renderer — Babylon.js 3D layer
      'babylon_physics.ts',         // Host physics — Babylon.js Havok
    ],
    rules: {
      'no-restricted-globals': 'off',
    },
  },

  // ── HOST INFRASTRUCTURE ───────────────────────────────────────────────────
  // Non-plugin files that are Host-layer components and legitimately use DOM.
  {
    files: [
      'shell.ts',
      'demo.ts',
      'demo_2026-02-20.ts',
      'config_ui.ts',
      'layer_manager.ts',
      'w3c_pointer_fabric.ts',
      'iframe_delivery_adapter.ts',
      'overscan_canvas.ts',
      'symbiote_injector.ts',
    ],
    rules: {
      'no-restricted-globals': 'off',
    },
  },

  // ── TEST / SPEC FILES ─────────────────────────────────────────────────────
  // Tests MUST import plugins to test them — override arch import rule.
  // Also relax strict TS rules that add noise in test scaffolding.
  {
    files: ['**/*.spec.ts', '**/*.test.ts', 'test_*.ts'],
    rules: {
      'no-restricted-globals': 'off',
      'no-restricted-imports': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/no-require-imports': 'off', // tryRequire() pattern in arch spec
      '@typescript-eslint/no-unsafe-function-type': 'warn',
    },
  },
);
