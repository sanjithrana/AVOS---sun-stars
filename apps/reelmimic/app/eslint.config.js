// Correctness rules only; formatting is left to the existing (dense) house style.
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrors: 'none' }],
      '@typescript-eslint/no-unused-expressions': ['error', { allowTernary: true, allowShortCircuit: true }],   // `ok ? a() : b()` is house style
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  { files: ['server/**', 'scripts/**', 'shared/**', '*.js'], languageOptions: { globals: globals.node } },
  // Only the rules of hooks: memos here are keyed on lengths / last timestamps on purpose (logs grow to hundreds of entries)
  { files: ['web/**'], languageOptions: { globals: globals.browser }, plugins: { 'react-hooks': reactHooks }, rules: { 'react-hooks/rules-of-hooks': 'error' } },
);
