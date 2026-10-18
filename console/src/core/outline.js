// The outline of a screen not ported yet (its address opens, says it is being built and which features
// it covers). A ported screen registered at the same address replaces its outline.
import { esc } from './format.js';
import { t } from './i18n.js';
import { screen } from './router.js';
import { sheet } from './sheets.js';

const body = features => `<p class="guide">${t('todo.next')}</p>${features ? `<div class="block-title" style="margin-top:24px">${t('todo.covers')}</div><p class="small mono">${esc(features)}</p>` : ''}`;

/** The outline of a screen: {id, path, place, title: dictionary key, features: 'PRJ-01, …'}. */
export function outline(def) {
  screen({ id: def.id, path: def.path, place: def.place, title: () => t(def.title),
    render: () => `<div class="page"><h1 class="lede">${esc(t(def.title))}</h1>${body(def.features)}</div>` });
}

/** The outline of a sheet. */
export function outlineSheet(name, title, features) {
  sheet(name, { kind: 'drawer', render: () => ({ title: esc(t(title)), body: body(features) }) });
}
