import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.ts'],
    rules: {
      // ATDD-ARCH-001: No global singletons / contraband
      'no-restricted-globals': [
        'error',
        {
          name: 'window',
          message: 'Use PathAbstractionLayer (PAL) instead of global window.',
        },
        {
          name: 'globalThis',
          message: 'Use PathAbstractionLayer (PAL) instead of globalThis.',
        },
        {
          name: 'document',
          message: 'Use PathAbstractionLayer (PAL) instead of global document.',
        }
      ],
      // ATDD-ARCH-004: Rogue Agents / Plugin Isolation
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['*_plugin'],
              message: 'Plugins must not import other plugins directly. Use the EventBus.',
            }
          ]
        }
      ]
    },
  },
  {
    // Allow PAL and tests to use globals
    files: ['plugin_supervisor.ts', '**/*.spec.ts', '**/*.test.ts', 'demo*.ts', 'shell.ts'],
    rules: {
      'no-restricted-globals': 'off',
      'no-restricted-imports': 'off'
    }
  }
);
