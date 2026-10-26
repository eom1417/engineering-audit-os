// The router: every screen and sheet has its own address (#/<path>?<query>, the prototype's addresses exactly), so it
// opens directly and can be shared. Before a screen draws, its place's bundle and the report sections it needs are
// read; meanwhile it shows its loading state. A redraw after a change keeps the focus and the scroll where they were.
import { prefs } from './prefs.js';
import { t } from './i18n.js';
import { bundleOfPath, loadBundle, isLoaded } from './places.js';
import { renderShell, renderBanner, renderStrip, renderSelbar } from './shell.js';
import { syncSheet, rerenderSheet, sheetOpen } from './sheets.js';
import { setLang, setTheme } from './settings.js';
import { clearSelection, picked } from '../data/selection.js';
import { need, pendingOf, state as dataState, mode } from '../data/source.js';
import { project } from '../data/model.js';
import { loadingHTML } from './loading.js';
import { parseHash, navigate } from './address.js';
import { a11yRegions, hold } from './a11y.js';

const screens = [];
const renderHooks = [];
/** The sections every screen's frame reads: the project's name and check, and what waits for the owner. */
const SHELL_NEEDS = ['head', 'decisions'];
/** Page states an address may ask for, to review a state the data does not have now (`?state=`); every other state
 *  comes from the data. */
const ASKABLE = ['loading', 'empty', 'offline', 'reconnecting'];

/** Registers a screen: {id, path ('/x/:param'), place, title(ctx), render(ctx), after(main, ctx), needs, loading(ctx)}.
 *  `needs`: the report sections it draws with (an array, or ctx => array). A later registration of the same address
 *  replaces the earlier one (a finished screen replaces its outline). */
export function screen(def) {
  const keys = [];
  // nosemgrep: javascript.lang.security.audit.detect-non-literal-regexp -- the path is a screen's own address in the code, never input
  const re = new RegExp('^' + def.path.replace(/:(\w+)/g, (m, k) => { keys.push(k); return '([^/]+)'; }) + '$');
  const i = screens.findIndex(x => x.path === def.path);
  if (i >= 0) screens.splice(i, 1);
  screens.push(Object.assign({}, def, { keys, re }));
}
export const allScreens = () => screens;
export const afterRender = fn => renderHooks.push(fn);

function match(path) {
  // fixed addresses before addresses with parameters; among equals the later registration wins
  const ordered = screens.map((x, i) => [x, i]).sort((a, b) => (a[0].keys.length - b[0].keys.length) || (b[1] - a[1])).map(x => x[0]);
  for (const s of ordered) {
    const m = s.re.exec(path);
    if (m) { const params = {}; s.keys.forEach((k, i) => { params[k] = decodeURIComponent(m[i + 1]); }); return { screen: s, params }; }
  }
  return null;
}

/** The read-only copy: opened from a file or without the launch token (or asked by ?state=offline to review it). */
export const offline = () => mode === 'snapshot' || parseHash().query.state === 'offline';

function context(r, m) {
  const asked = ASKABLE.includes(r.query.state) ? r.query.state : '';
  const ctx = { params: m ? m.params : {}, query: r.query, path: r.path, offline: offline() };
  const needs = m ? (typeof m.screen.needs === 'function' ? m.screen.needs(ctx) : m.screen.needs) || [] : [];
  ctx.needs = needs;
  ctx.state = asked === 'offline' ? '' : asked || (dataState() === 'empty' ? 'empty' : pendingOf(SHELL_NEEDS.concat(needs)).length ? 'loading' : '');
  return ctx;
}

let current = { key: null, path: null };
const scrollMemo = {};
let draws = 0;
function routeKey(r) { const q = Object.assign({}, r.query); delete q.sheet; delete q.lang; delete q.theme; delete q.ask; return r.path + '?' + new URLSearchParams(q).toString(); }

export function onRoute() {
  const r = parseHash();
  if (landOld(r) || addressPrefs(r) || !bundleReady(r)) return;
  const key = routeKey(r);
  if (key === current.key) { syncSheet(r.query.sheet || null); refreshAssist(); return; }
  leave(r);
  arrive(r, key);
  syncSheet(r.query.sheet || null);
}
/** Understand's views became the one report page (M8.2): an old address (a notice, a shared link) lands on it, a
 *  report file's sheet kept open; true when the address was replaced. */
function landOld(r) {
  if (r.path !== '/understand' && !r.path.startsWith('/understand/')) return false;
  const sheet = (r.query.sheet || '').startsWith('file:') ? r.query.sheet : null;
  navigate('/report', { sheet, lang: r.query.lang, theme: r.query.theme }, { replace: true });
  return true;
}
/** Language and theme in the address (LNK-01) apply and are remembered; true when the language draws everything again. */
function addressPrefs(r) {
  if (r.query.lang && r.query.lang !== prefs.lang) { setLang(r.query.lang); return true; }
  if (r.query.theme && r.query.theme !== prefs.theme) setTheme(r.query.theme, true);
  return false;
}
/** Whether the screen's code is read; if not it is read (its loading state drawn on the first route) and the route taken again. */
function bundleReady(r) {
  const bundle = bundleOfPath(r.path);
  if (isLoaded(bundle)) return true;
  if (!draws) draw(r, null, true);
  loadBundle(bundle).then(() => { current.key = null; onRoute(); });
  return false;
}
/** Leaving a path for another: its scroll is kept, and the selection, which belongs to Problems and the plan (SEL-03), goes. */
function leave(r) {
  if (!current.path || current.path === r.path) return;
  scrollMemo[current.path] = window.scrollY;
  if (current.path.startsWith('/problems') && !r.path.startsWith('/problems') && picked.ids.size) clearSelection();
}
/** The route's screen: drawn again in place on the same path, else drawn with the scroll it had and the focus on its title. */
function arrive(r, key) {
  const samePath = current.path === r.path;
  current = { key, path: r.path };
  if (samePath) return refresh();
  draw(r, match(r.path) || match('/status'));
  window.scrollTo(0, scrollMemo[r.path] || 0);
  if (draws > 1) focusMain();
}

function refreshAssist() { renderHooks.forEach(fn => fn(context(parseHash(), match(parseHash().path)))); }

function focusMain() {
  const h = document.querySelector('#main h1');
  if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); }
}

let waiting = null;
function screenHTML(sc, ctx, bundlePending) {
  if (bundlePending || !sc) return loadingHTML();
  if (ctx.state === 'loading') return sc.loading ? sc.loading(ctx) : loadingHTML();
  return sc.render(ctx);
}
/** The sections the screen and its frame read that are not here yet: read once, then the screen drawn again. */
function readMissing(ctx, bundlePending) {
  const wanted = SHELL_NEEDS.concat(ctx.needs || []);
  if (bundlePending || !pendingOf(wanted).length || waiting === current.key) return;
  waiting = current.key;
  const key = current.key;
  need(wanted).then(() => { waiting = null; if (current.key === key) refresh(); });
}
/** Draws the screen of `r`; while its bundle or sections are read, its loading state, then itself. */
function draw(r, m, bundlePending) {
  draws += 1;
  const ctx = context(r, m);
  const sc = m && m.screen;
  const main = document.getElementById('main');
  document.title = t('doc.title', { place: sc && sc.title ? sc.title(ctx) : 'EAOS', project: project().name || 'EAOS' });
  // nosemgrep: javascript.browser.security.insecure-document-method, javascript.browser.security.insecure-innerhtml -- each screen's render escapes every value it draws (esc, rich, code: core/format.js)
  main.innerHTML = screenHTML(sc, ctx, bundlePending);
  main.dataset.screen = sc ? sc.id : '';
  renderShell(sc ? sc.place || null : null);
  renderBanner(ctx);
  renderStrip();
  renderSelbar();
  if (sc && sc.after && ctx.state !== 'loading') sc.after(main, ctx);
  a11yRegions(main);
  renderHooks.forEach(fn => fn(ctx));
  readMissing(ctx, bundlePending);
}

/** Redraws in place after a change, keeping the focus on the same control and the scroll where it was. */
export function refresh() {
  const back = hold(document.documentElement);
  const y = window.scrollY;
  const r = parseHash();
  if (!isLoaded(bundleOfPath(r.path))) return;
  draw(r, match(r.path) || match('/status'));
  draws -= 1;
  if (sheetOpen()) rerenderSheet();
  window.scrollTo(0, y);
  back();
}

let pending = 0;
/** A redraw at the next frame, however many changes arrive before it (the live data). */
export function refreshSoon() {
  if (pending) return;
  pending = requestAnimationFrame(() => { pending = 0; if (!document.querySelector('#main textarea:focus, #main input[type=search]:focus')) refresh(); else renderShell(match(parseHash().path) ? match(parseHash().path).screen.place : null); });
}
