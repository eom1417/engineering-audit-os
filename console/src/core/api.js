// The core's API, written once: what every place's bundle reaches as `import { t, screen } from 'eaos'`. main.js offers
// it as self.EAOS, the build maps 'eaos' to self.EAOS (scripts/build.mjs), and knip reads it here (knip.json `paths`).
export * from './i18n.js';
export * from './format.js';
export * from './address.js';
export * from './router.js';
export * from './sheets.js';
export * from './notices.js';
export * from './settings.js';
export * from './shell.js';
export * from './outline.js';
export * from './parts.js';
export { act, tickAct } from './events.js';
export { S } from './state.js';
export { prefs } from './prefs.js';
export { redrawAssist } from './assist.js';
export * as ac from './marks.js';
export { a11yRegions } from './a11y.js';
export { loadingHTML } from './loading.js';
export { md } from './markdown.js';
export * as data from '../data/source.js';
export { live } from '../data/store.js';
export * as store from '../data/store.js';
export * as model from '../data/model.js';
export * as selection from '../data/selection.js';
export * as derive from '../data/derive.js';
export * as normalize from '../data/normalize.js';
export * as contract from '../data/contract.js';
export { client, ActionError, said, TERMINAL, ACTIVE, RETRYABLE } from '../data/actions.js';
