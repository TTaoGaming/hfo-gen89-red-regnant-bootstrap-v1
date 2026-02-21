// @ts-nocheck
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
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': 'warn',

      // ── ARCH-ZOMBIE GUARD (L8 — Rules leverage level) ────────────────────
      // Inline .bind() inside subscribe() creates an anonymous function that
      // EventBus.unsubscribe() can NEVER match — a silent zombie listener.
      // Pattern: bus.subscribe('EVT', this.method.bind(this))  ← FORBIDDEN
      // Fix:     store as readonly class property in constructor, pass that ref.
      // Selector: a bind() CallExpression that is a DIRECT CHILD (argument) of
      // a subscribe() CallExpression — covers all call shapes without false positives.
      'no-restricted-syntax': [
        'error',
        {
          selector:
            'CallExpression[callee.property.name="subscribe"] > CallExpression[callee.property.name="bind"]',
          message:
            'ARCH-ZOMBIE: Do not pass inline .bind() to subscribe(). ' +
            'Store the bound reference as a readonly class property in the constructor. ' +
            'Inline bind() creates an anonymous function that EventBus.unsubscribe() can NEVER remove.',
        },
      ],

      // ── No non-null assertions (L5 — Negative Feedback) ────────────────
      // The ! operator silences TypeScript's null-safety system. Every ! is a
      // potential NPE waiting to happen at runtime. Prefer explicit guards.
      '@typescript-eslint/no-non-null-assertion': 'warn',
    },
  },

  // ── ARCH RULE P4/V1: Guest zone must not touch DOM directly ──────────────
  // Apply to ALL files by default.
  // These receive browser capabilities via PluginContext.pal, not globals.
  {
    rules: {
      'no-restricted-globals': [
        'error',
        {
          name: 'window',
          message:
            'ARCH-V5: Use pal.resolve("ScreenWidth") etc. instead of window. ' +
            'Guest code must receive Host capabilities via PluginContext.pal.',
        },
        {
          name: 'document',
          message:
            'ARCH-V5: Request DOM refs via PluginContext.pal instead of document. ' +
            'Guest code must not query the DOM directly.',
        },
        {
          name: 'globalThis',
          message: 'ARCH-V5: Use pal.resolve() instead of globalThis in Guest code.',
        },
      ],
    },
  },

  // ARCH-V4: Plugins must not import each other — only via EventBus
  {
    files: ['**/*_plugin.ts'],
    rules: {
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
      'mediapipe_vision_plugin.ts',   // Host sensor — camera + MediaPipe
      'visualization_plugin.ts',      // Host renderer — dot/ring HUD in DOM
      'babylon_landmark_plugin.ts',   // Host renderer — Babylon.js 3D layer
      'babylon_physics.ts',           // Host physics — Babylon.js Havok
      'symbiote_injector_plugin.ts',  // Host bridge — pal.resolve() → globalThis.dispatchEvent fallback
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
      'no-restricted-globals':                        'off',
      'no-restricted-imports':                        'off',
      'no-restricted-syntax':                         'off', // test files may use .bind() in subscribe() freely
      '@typescript-eslint/no-unused-vars':            'off',
      '@typescript-eslint/no-require-imports':        'off', // tryRequire() pattern in arch spec
      '@typescript-eslint/no-non-null-assertion':     'off', // test assertions commonly use !
      '@typescript-eslint/no-unsafe-function-type':   'warn',
    },
  },
);
