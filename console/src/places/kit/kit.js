// What the plan, Status, Problems and the report page share: rows, segmented controls whose choices are
// addresses, a list's own search, lists 50 at a time, the loading, empty and not-measured states, a problem's row and
// the build's next step. A kit: stateless helpers bundled into each place that imports them (scripts/build.mjs).
import { ac, t, num, esc, icon, code, sev, rich, L, href, parseHash, searchTyped, act, offline, model, normalize, skeletonRows, rowWords, pageHead } from 'eaos';

const q = () => parseHash().query;
export const enc = encodeURIComponent;
export const matches = normalize.matches;

/** The way back, as the core draws it (read when drawn: a part drawn on its own has no core). */
export const back = (path, label, query) => ac.back(path, label, query);

/** The report page's facts, drawn inside the place's own bundle (its parts are drawn and tested on their own, without
 *  the core's parts). */
export const facts = pairs => `<dl class="facts">${pairs.filter(Boolean).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`;

/* ---------- choices, a list's own search, lists a page at a time ---------- */

/** A segmented control whose choices are addresses (LNK-01): [value, label, count]. */
export function seg(param, items, cur, label, opts) {
  const r = parseHash();
  return `<nav class="seg ${opts && opts.cls ? opts.cls : ''}" aria-label="${esc(label)}">${items.map(([v, lab, n]) => {
    const query = Object.assign({}, r.query, { [param]: v === (opts && opts.dflt) ? null : v, n: null, sheet: null });
    return `<a href="${href(r.path, query)}" ${String(cur) === String(v) ? 'aria-current="true"' : ''}><span>${lab}</span>${n != null ? ` <b>${num(n)}</b>` : ''}</a>`;
  }).join('')}</nav>`;
}

/** Each view's own search (SRC-03), the same matching as everywhere (SRC-02); the address keeps it. */
export const search = (value, ph) => `<label class="field un-search">${icon('search')}<span class="sr-only">${esc(ph)}</span>
    <input type="search" data-input="unq" data-fk="unq" value="${esc(value || '')}" placeholder="${esc(ph)}" autocomplete="off"></label>`;
act('unq', el => searchTyped(el, 180, { n: null }));

/** A large list 50 rows at a time (?n= keeps how many are shown): the rows, the "Show 50 more" link, how many shown. */
export function page(items, render, step) {
  step = step || 50;
  const n = Math.max(step, parseInt(q().n, 10) || step);
  const shown = items.slice(0, n);
  const r = parseHash();
  const more = items.length > n ? `<a class="btn btn--secondary un-more" href="${href(r.path, Object.assign({}, r.query, { n: n + step }))}">${t('un.more', { n: num(Math.min(step, items.length - n)) })}</a>` : '';
  return { html: shown.map(render).join(''), more, shown: shown.length };
}
export const count = (shown, total) => `<span class="listhead__count" aria-live="polite">${esc(t('un.showing', { shown: num(shown), total: num(total) }))}</span>`;

/* ---------- state templates (DESIGN-SYSTEM section 10) ---------- */
export const loading = (title, rows) => `<div class="page page--wide" aria-busy="true"><h1 class="lede">${title}</h1>${skeletonRows(rows || 5, [45, 80], { cls: 'mt-6' })}</div>`;
/** What was not measured (or not checked: `o.tag` its word), why, and the action that measures it; `o.cls` the card's classes. */
export const nm = (title, why, actHTML, o = {}) => `<div class="nm${o.cls ? ' ' + o.cls : ''}"><div class="nm__title"><span class="tag tag--nm">${o.tag || t('nm')}</span>${title}</div><p class="small ink-2">${why}</p>${actHTML ? `<div>${actHTML}</div>` : ''}</div>`;
/** The empty state of a view (no check has written the report yet): what will be here, and the one action. */
export const empty = (lede, guide, head) => `<div class="page">${head || ''}${pageHead(lede, guide, checkAct('btn--primary'))}</div>`;
// a check is never offered in the read-only copy: there the action says how to open it live
const checkAct = cls => (offline() ? `<button class="btn ${cls}" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button>`
  : `<a class="btn ${cls}" href="${href('/activity', { sheet: 'check' })}">${t('st.empty.act')}</a>`);

/* ---------- a problem's row ---------- */
export const prow = (p, extra) => `<a class="row" href="${href('/problems/' + enc(p.id))}">${sev(p.severity, false)}${rowWords(`${code(p.id)} ${rich(L(p.title))}`, extra || null, { title: 'small' })}${p.state !== 'open' ? `<span class="tag tag--state">${t('state.' + p.state)}</span>` : ''}</a>`;

/** `code` spans of a report sentence (already escaped) drawn as code. */
export const ticks = h => h.replace(/`([^`]+)`/g, '<bdi class="mono">$1</bdi>');

/** The build's one next step (model.buildNext): the blueprint's questions first, else the milestone to build. */
export function buildStep() {
  const n = model.buildNext();
  if (!n) return '';
  if (n.link) return `<a class="btn btn--primary" href="${href(n.link)}">${esc(n.label)}</a>`;
  return `<button class="btn btn--primary" data-act="sheet" data-sheet="${offline() ? 'open-live' : n.sheet}">${icon('layers', 'icon--sm')}${esc(n.label)}</button>`;
}
