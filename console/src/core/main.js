// The console's core (assets/studio.js): the shell, the router, sheets, notices, search, the project menu, the
// floating assistant and the data layer, offered to every place's bundle as one object, self.EAOS (a place imports
// it as `import { t, screen } from 'eaos'`; console/README.md lists it). It starts once the person's dictionary is
// read: the report's manifest, then the live command state, then the screen of the address.
import { prefs, applyDocument } from './prefs.js';
import * as i18n from './i18n.js';
import * as format from './format.js';
import * as router from './router.js';
import * as address from './address.js';
import { a11yRegions } from './a11y.js';
import { loadingHTML } from './loading.js';
import * as sheets from './sheets.js';
import * as notices from './notices.js';
import * as settings from './settings.js';
import * as shell from './shell.js';
import * as outline from './outline.js';
import { act } from './events.js';
import { S } from './state.js';
import { redrawAssist } from './assist.js';
import './search.js';
import './menu.js';
import * as source from '../data/source.js';
import * as store from '../data/store.js';
import * as model from '../data/model.js';
import * as selection from '../data/selection.js';
import * as derive from '../data/derive.js';
import * as normalize from '../data/normalize.js';
import * as contract from '../data/contract.js';
import { client, ActionError, TERMINAL, ACTIVE, RETRYABLE } from '../data/actions.js';

act('sheet', el => sheets.openSheet(el.dataset.sheet));
act('sheet-close', () => sheets.closeSheet());
act('lang', el => settings.setLang(el.dataset.lang));
act('theme', () => settings.setTheme(prefs.theme === 'dark' ? 'light' : 'dark'));
act('theme-set', el => settings.setTheme(el.dataset.theme));
act('copy', el => notices.copyText(el.dataset.text || ''));
act('go', el => sheets.closeSheetThen(() => { location.hash = el.dataset.href; }));

self.EAOS = Object.assign({}, i18n, format, address, router, sheets, notices, settings, shell, outline, {
  act, S, prefs, redrawAssist, a11yRegions, loadingHTML,
  data: source, live: store.live, store, model, selection, derive, normalize, contract,
  client, ActionError, TERMINAL, ACTIVE, RETRYABLE,
});

// the theme follows the system until the person chooses one
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ev => {
  if (prefs.chosenTheme) return;
  prefs.theme = ev.matches ? 'dark' : 'light';
  applyDocument();
  router.refresh();
});
window.addEventListener('hashchange', router.onRoute);
window.addEventListener('eaos:redraw', () => { router.onRoute(); router.refresh(); });

(async () => {
  applyDocument();
  await i18n.loadWords(prefs.lang);
  if (!location.hash) history.replaceState(null, '', '#/status');
  await source.start();
  source.onChange(() => router.refreshSoon());
  store.onLive(what => { if (what === 'event' && store.live.last && store.live.last.text) notices.announce(i18n.L(store.live.last.text)); router.refreshSoon(); });
  store.begin();
  router.onRoute();
})();
