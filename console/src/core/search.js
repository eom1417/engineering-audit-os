// Search or ask (SRC-01, SRC-02): one light search over the whole project, opened from every screen (Ctrl/Cmd+K).
// Places, decisions, problems, actions, runs, branches, plan steps, your app's screens and the report's documents
// (title, path, headings). It reads the sections it searches when it opens and never the large ones: the documents'
// text is searched through "Search the check's records" (PRB-13). Every word must match (src/data/normalize.js); each
// result opens its screen.
import { prefs } from './prefs.js';
import { t, L } from './i18n.js';
import { esc, icon, code, rich, sev } from './format.js';
import { allScreens } from './router.js';
import { href } from './address.js';
import { sheet, rerenderSheet } from './sheets.js';
import { matches } from '../data/normalize.js';
import { need, section } from '../data/source.js';
import { live } from '../data/store.js';
import { client } from '../data/actions.js';
import { ACTIONS } from '../data/contract.js';
import { labelOf } from '../data/derive.js';
import { decisions, plan, problems } from '../data/model.js';

// The documents written beside the report, not in it (eaos/report/studio/library.py BESIDE): /api/report-file reads only
// the report's own folder, so they are not offered here.
const BESIDE = ['blueprint/BLUEPRINT.md', 'DESIGN.md', 'extend/SOURCE.md'];

const SEARCHED = ['cards', 'decisions', 'plans', 'screens', 'docs'];
const enc = encodeURIComponent;
const PLACE_ICON = { status: 'status', waiting: 'waiting', problems: 'problems', activity: 'activity', report: 'understand' };
let branches = null;

function titleIn(sc, lang) {
  const was = prefs.lang;
  prefs.lang = lang;
  try { return sc.title ? String(sc.title({ params: {}, query: {}, path: sc.path })) : ''; } catch (e) { return ''; } finally { prefs.lang = was; }
}
/** Every screen without parameters is a place, its title indexed in both languages (a place whose code is not read
 *  yet is found once it is). */
function places() {
  return allScreens().filter(sc => !sc.keys.length && sc.title).map(sc => ({
    href: sc.path, icon: PLACE_ICON[sc.place] || (sc.path.startsWith('/project') ? 'gear' : sc.path === '/ask' ? 'ask' : 'layers'),
    ar: titleIn(sc, 'ar'), en: titleIn(sc, 'en'),
  })).filter((x, i, all) => all.findIndex(y => y.href === x.href) === i);
}
const FIRST = () => [
  ['nav.status', '/status', 'status'], ['nav.waiting.long', '/waiting', 'waiting'], ['nav.problems', '/problems', 'problems'],
  ['pb.view.plan', '/problems/plan', 'layers'], ['nav.activity', '/activity', 'activity'], ['nav.report', '/report', 'understand'],
  ['proj.branches', '/project/branches', 'branch'], ['proj.assistants', '/project/assistants', 'ai'], ['proj.settings', '/project/settings', 'gear'],
].map(([key, path, ic]) => ({ icon: ic, html: esc(t(key)), href: path }));

/** The list a section of the check holds, or none while it is not read. */
const listOf = (name, key) => (section(name) && section(name)[key]) || [];
/** Each kind of result: [group, how many at most, its items, the text searched in one, how one is shown]. */
const GROUPS = [
  ['places', 6, places, p => `${p.ar} ${p.en} ${p.href.replace(/[/-]/g, ' ')}`, p => ({ icon: p.icon, html: esc(prefs.lang === 'ar' ? p.ar : p.en), href: p.href })],
  ['decisions', 4, () => decisions().filter(d => d.state === 'waiting'), d => L(d.question), d => ({ icon: 'waiting', html: esc(L(d.question)), href: '/waiting/' + enc(d.id) })],
  ['problems', 6, problems, p => [p.id, L(p.title), p.paths.join(' '), p.kind, p.category, p.why ? L(p.why) : ''].join(' '), p => ({ sev: p.severity, html: `${code(p.id)} ${rich(L(p.title))}`, href: '/problems/' + p.id })],
  ['actions', 5, () => ACTIONS, a => [a.id, a.label.ar, a.label.en, a.description.ar, a.description.en].join(' '), a => ({ icon: 'play', html: esc(L(a.label)), href: href('/activity', { sheet: 'action:' + a.id }).slice(1) })],
  ['runs', 4, () => live.runs, r => [r.id, labelOf(r.label, 'ar'), labelOf(r.label, 'en'), r.action, (r.cards || []).join(' ')].join(' '), r => ({ icon: 'activity', html: `${code(r.id)} ${esc(labelOf(r.label, prefs.lang))}`, href: '/activity/run/' + enc(r.id) })],
  ['branches', 4, () => (branches && branches.branches) || [], b => [b.name, b.subject || '', b.upstream || ''].join(' '), b => ({ icon: 'branch', html: code(b.name), href: '/project/branches/' + enc(b.name) })],
  ['steps', 4, () => plan().steps, st => `${st.id} ${L(st.title || '')} ${L(st.gate || '')}`, st => ({ icon: 'layers', html: `${code(st.id)} ${rich(L(st.title || st.gate || ''))}`, href: '/problems/plan/' + st.id })],
  ['screens', 4, () => listOf('screens', 'screens'), sc => [sc.id, sc.title, sc.route, sc.file].join(' '), sc => ({ icon: 'screen', html: `${esc(L(sc.title || sc.id))} ${code(sc.route || '')}`, href: '/report?part=screens' })],
  ['docs', 5, () => listOf('docs', 'docs').filter(d => !BESIDE.includes(d.path)), d => [d.id, d.title, (d.titles && (d.titles.ar || '') + ' ' + (d.titles.en || '')) || '', d.path, (d.headings || []).map(h => h.text).join(' ')].join(' '),
    d => ({ icon: 'book', html: `${esc((d.titles && d.titles[prefs.lang]) || d.title)} ${code(d.path)}`, href: `/report?part=files&sheet=file:${enc(enc(d.path))}` })],
];
function results(q) {
  if (!q.trim()) return [{ group: 'places', items: FIRST() }];
  let left = 40; // up to 40 results, grouped by kind
  return GROUPS.map(([group, cap, items, text, shown]) => {
    const take = items().filter(x => matches(text(x), q)).slice(0, Math.min(cap, left));
    left -= take.length;
    return { group, items: take.map(shown) };
  }).filter(g => g.items.length);
}

function listHTML(q) {
  const r = results(q);
  const item = (it, target) => `<button class="result" data-act="go" data-href="${esc(target)}">${it.sev ? sev(it.sev, false) : icon(it.icon)}<span class="result__text">${it.html}</span></button>`;
  const out = r.map(g => `<div class="results__group" role="group" aria-labelledby="sg-${g.group}"><p class="results__h" id="sg-${g.group}">${esc(t('search.' + g.group))}</p>${g.items.map(it =>
    item(it, href(it.href.split('?')[0], Object.fromEntries(new URLSearchParams(it.href.split('?')[1] || ''))))).join('')}</div>`).join('');
  const more = q.trim() ? `<div class="results__group" role="group" aria-labelledby="sg-more"><p class="results__h" id="sg-more">${esc(t('search.more'))}</p>
    ${item({ icon: 'book', html: esc(t('search.records', { q })) }, href('/ask', { q, records: 1 }))}
    <button class="result" data-act="assist-ask" data-q="${esc(q)}">${icon('ai')}<span class="result__text">${esc(t('search.ask', { q }))}</span></button></div>` : '';
  const none = q.trim() && !r.length ? `<p class="muted small">${t('search.none')}</p>` : '';
  return none + out + more;
}

sheet('search', {
  kind: 'search', full: true,
  render(arg, query, local) {
    return {
      head: false,
      top: `<div class="search-head"><div class="field">${icon('search')}<input id="search-input" data-fk="search-input" type="search" autocomplete="off" placeholder="${esc(t('search.placeholder'))}" aria-label="${esc(t('search.open'))}" value="${esc(local.q || '')}" data-autofocus>
        <button class="btn btn--icon btn--sm" data-act="sheet-close" aria-label="${esc(t('close'))}">${icon('x')}</button></div></div>`,
      body: `<div class="results" id="search-results" aria-live="polite">${listHTML(local.q || '')}</div><p class="muted small">${t('search.hint')}</p>`,
    };
  },
  after(el, arg, local) {
    if (!local.asked) readOnce(local);
    const input = el.querySelector('#search-input');
    // nosemgrep: javascript.browser.security.insecure-document-method, javascript.browser.security.insecure-innerhtml -- every result's text escaped (esc, rich, code) and its address escaped; the rest are words
    input.addEventListener('input', () => { local.q = input.value; el.querySelector('#search-results').innerHTML = listHTML(input.value); });
    input.addEventListener('keydown', e => onKey(el, e));
  },
});
/** What the search reads the first time it opens: the sections it searches and the branches; the results are drawn again. */
function readOnce(local) {
  local.asked = true;
  need(SEARCHED).then(() => { if (local.q) rerenderSheet(); });
  if (client && !branches) client.branches.inventory().then(b => { branches = b; if (local.q) rerenderSheet(); }, () => {});
}
/** The arrows move the active result, Enter opens it (or the first). */
function onKey(el, e) {
  const items = Array.from(el.querySelectorAll('.result'));
  if (!items.length) return;
  const i = items.findIndex(x => x.dataset.active === 'true');
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const n = e.key === 'ArrowDown' ? Math.min(items.length - 1, i + 1) : Math.max(0, i - 1);
    items.forEach(x => delete x.dataset.active); items[n].dataset.active = 'true'; items[n].scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') { e.preventDefault(); (items[i] || items[0]).click(); }
}
