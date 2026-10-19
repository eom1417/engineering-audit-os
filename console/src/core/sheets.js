// Sheets: bottom sheets on the phone, end drawers (previews) and centred dialogs (confirms) on the desktop, each with
// its own address (?sheet=<name>:<arg>), so Back closes it and a link opens it. A sheet of a place not read yet is
// read first (places.js bundleOfSheet). Focus opens inside (on [data-autofocus]), stays inside, and returns where it
// was. `local()` holds what the person did inside the open sheet (a tick, a choice, the preview the server gave), so a
// redraw keeps it; it goes when the sheet closes.
import { t } from './i18n.js';
import { esc, icon } from './format.js';
import { href, navigate, parseHash, setQuery } from './address.js';
import { a11yRegions, holdFocus } from './a11y.js';
import { bundleOfSheet, loadBundle } from './places.js';
import { need, pendingOf } from '../data/source.js';

const sheets = {};
let open = null;
let pushed = false;
let pushedAt = '';   // the address the opening pushed; a sheet that changed the query (filters) is closed in place

/** Registers a sheet: {kind: drawer | dialog | menu | search, confirm, full, needs: [sections], render(arg, query,
 *  local) -> {title, sub, top, body, foot, head: false}, after(el, arg, local)}. It draws once its sections are read. */
export function sheet(name, def) { sheets[name] = def; }
export const hasSheet = name => !!sheets[name];
export const sheetOpen = () => !!open;
/** The open sheet's own state (see above); {} when none is open. */
export const local = () => (open ? open.local : {});

export function openSheet(key) {
  const r = parseHash();
  if (r.query.sheet === key) return;
  pushed = true;
  pushedAt = href(r.path, Object.assign({}, r.query, { sheet: key }));
  navigate(r.path, Object.assign({}, r.query, { sheet: key }));
}
/** Back undoes the opening only while the address is still the one it pushed: going back from a sheet that changed
 *  the query (a filter ticked, a grouping chosen) would throw the change away with the sheet's history entry. */
const backCloses = () => pushed && location.hash === pushedAt;
export function closeSheet() {
  if (!open) return;
  if (backCloses()) { pushed = false; history.back(); } else { pushed = false; setQuery({ sheet: null }); }
}
/** Closes the open sheet, then runs `fn` once the address has settled. */
export function closeSheetThen(fn) {
  if (open && backCloses()) {
    pushed = false;
    const once = () => { window.removeEventListener('hashchange', once); setTimeout(fn, 0); };
    window.addEventListener('hashchange', once);
    history.back();
  } else { pushed = false; if (open) { setQuery({ sheet: null }); destroy(); } fn(); }
}

export function syncSheet(key) {
  if (open && open.key === key) return;
  if (open) destroy();
  if (!key) { pushed = false; return; }
  const [name, ...rest] = key.split(':');
  if (sheets[name]) return create(key, name, rest.join(':'), sheets[name]);
  const bundle = bundleOfSheet(name);
  if (bundle) loadBundle(bundle).then(() => { if (parseHash().query.sheet === key && sheets[name]) create(key, name, rest.join(':'), sheets[name]); });
}

function inner(def, arg, state) {
  let r;
  const waiting = pendingOf(def.needs);
  if (waiting.length) {
    need(waiting).then(() => { if (open && open.def === def) rerenderSheet(); });
    r = { title: esc(t('st.loading')), body: `<p class="small muted" aria-busy="true">${t('st.loading')}</p>` };
  } else try { r = def.render(arg, parseHash().query, state) || {}; } catch (e) {
    console.error('sheet', arg, e);
    r = { title: esc(t('pd.notfound', { id: arg || '' })), body: `<p class="small ink-2">${t('pd.notfound.guide')}</p>` };
  }
  return `<div class="sheet__grab" aria-hidden="true"></div>
    ${r.head === false ? '' : `<div class="sheet__head"><div class="sheet__titles"><h2 class="sheet__title" id="sheet-title">${r.title || ''}</h2>${r.sub ? `<p class="sheet__sub">${r.sub}</p>` : ''}</div>
      <button class="btn btn--icon" data-act="sheet-close" aria-label="${esc(t('close'))}" data-fk="sheet-x">${icon('x')}</button></div>`}
    ${r.top || ''}
    <div class="sheet__body">${r.body || ''}</div>
    ${r.foot ? `<div class="sheet__foot">${r.foot}</div>` : ''}`;
}

function create(key, name, arg, def) {
  const host = document.getElementById('sheets');
  const scrim = document.createElement('div');
  scrim.className = 'scrim'; scrim.dataset.act = 'sheet-close';
  const el = document.createElement('div');
  el.className = `sheet sheet--${def.kind || 'drawer'}${def.confirm ? ' sheet--confirm' : ''}${def.full ? ' sheet--full' : ''}`;
  el.setAttribute('role', def.confirm ? 'alertdialog' : 'dialog');
  el.setAttribute('aria-modal', 'true');
  el.setAttribute('aria-labelledby', 'sheet-title');
  el.tabIndex = -1;
  open = { key, name, arg, def, el, scrim, ret: document.activeElement, local: {} };
  el.innerHTML = inner(def, arg, open.local);
  host.append(scrim, el);
  document.documentElement.style.overflow = 'hidden';
  requestAnimationFrame(() => {
    scrim.classList.add('is-open'); el.classList.add('is-open');
    (el.querySelector('[data-autofocus]') || el).focus({ preventScroll: true });
  });
  if (def.after) def.after(el, arg, open.local);
  a11yRegions(el);
}

/** Redraws the open sheet from its definition, keeping its scroll and focus. */
export function rerenderSheet() {
  const st = open;
  if (!st) return;
  const back = holdFocus(st.el);
  const body = st.el.querySelector('.sheet__body');
  const top = body ? body.scrollTop : 0;
  st.el.innerHTML = inner(st.def, st.arg, st.local);
  const nb = st.el.querySelector('.sheet__body'); if (nb) nb.scrollTop = top;
  if (st.def.after) st.def.after(st.el, st.arg, st.local);
  a11yRegions(st.el);
  back();
}

function destroy() {
  const st = open;
  if (!st) return;
  open = null;
  st.el.classList.remove('is-open'); st.scrim.classList.remove('is-open');
  const done = () => { st.el.remove(); st.scrim.remove(); };
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) done(); else setTimeout(done, 180);
  document.documentElement.style.overflow = '';
  if (st.ret && document.contains(st.ret)) st.ret.focus({ preventScroll: true });
}

export function trapFocus(e) {
  if (!open || e.key !== 'Tab') return;
  const f = Array.from(open.el.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), textarea, select, summary, [tabindex]:not([tabindex="-1"])')).filter(x => x.offsetParent !== null);
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}
