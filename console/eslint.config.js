// The Studio's JavaScript (src/) read for names never defined and imports or variables never used, nothing else
// (tools/quality.py runs it and fails on any finding).
import globals from 'globals';

export default [{
  files: ['src/**/*.js'],
  languageOptions: {ecmaVersion: 'latest', sourceType: 'module', globals: globals.browser},
  rules: {'no-undef': 'error', 'no-unused-vars': ['error', {caughtErrors: 'none'}]},
}];
