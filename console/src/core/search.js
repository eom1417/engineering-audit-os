// Search or ask (SRC-01, SRC-02): one light search over the whole project, opened from every screen (Ctrl/Cmd+K).
// Places, decisions, problems, actions, runs, branches, plan steps, your app's screens, code paths, gaps, components
// and documents (title, path, headings). It reads the sections it searches when it opens and never the large ones:
// functions are searched on their own view, the documents' text through "Search the check's records" (PRB-13). Every
// word must match (src/data/normalize.js); each result opens its screen.
import { prefs } from './prefs.js';
import { t, L } from './i18n.js';
import { esc, icon, code, rich, sev } from './format.js';
import { allScreens, href } from './router.js';
import { sheet, rerenderSheet } from './sheets.js';
import { matches } from '../data/normalize.js';
import { need, section } from '../data/source.js';
import { live } from '../data/store.js';
import { client } from '../data/actions.js';
import { ACTIONS } from '../data/contract.js';
import { labelOf } from '../data/derive.js';
import { decisions, plan, problems } from '../data/model.js';

const SEARCHED = ['cards', 'decisions', 'plans', 'gaps', 'screens', 'docs', 'paths', 'story'];
const enc = encodeURIComponent;
const PLACE_ICON = { status: 'status', waiting: 'waiting', problems: 'problems', activity: 'activity', understand: 'understand' };
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
  ['pb.view.plan', '/problems/plan', 'layers'], ['nav.activity', '/activity', 'activity'], ['nav.understand', '/understand', 'understand'],
  ['proj.branches', '/project/branches', 'branch'], ['proj.assistants', '/project/assistants', 'ai'], ['proj.settings', '/project/settings', 'gear'],
].map(([key, path, ic]) => ({ icon: ic, html: esc(t(key)), href: path }));

function results(q) {
  if (!q.trim()) return [{ group: 'places', items: FIRST() }];
  const m = hay => matches(hay, q);
  const docs = (section('docs') && section('docs').docs) || [];
  const groups = [
    ['places', 6, places().filter(p => m(`${p.ar} ${p.en} ${p.href.replace(/[/-]/g, ' ')}`)).map(p => ({ icon: p.icon, html: esc(prefs.lang === 'ar' ? p.ar : p.en), href: p.href }))],
    ['decisions', 4, decisions().filter(d => d.state === 'waiting' && m(L(d.question))).map(d => ({ icon: 'waiting', html: esc(L(d.question)), href: '/waiting/' + enc(d.id) }))],
    ['problems', 6, problems().filter(p => m([p.id, L(p.title), p.paths.join(' '), p.kind, p.category, p.why ? L(p.why) : ''].join(' '))).map(p => ({ sev: p.severity, html: `${code(p.id)} ${rich(L(p.title))}`, href: '/problems/' + p.id }))],
    ['actions', 5, ACTIONS.filter(a => m([a.id, a.label.ar, a.label.en, a.description.ar, a.description.en].join(' '))).map(a => ({ icon: 'play', html: esc(L(a.label)), href: href('/activity', { sheet: 'action:' + a.id }).slice(1) }))],
    ['runs', 4, live.runs.filter(r => m([r.id, labelOf(r.label, 'ar'), labelOf(r.label, 'en'), r.action, (r.cards || []).join(' ')].join(' '))).map(r => ({ icon: 'activity', html: `${code(r.id)} ${esc(labelOf(r.label, prefs.lang))}`, href: '/activity/run/' + enc(r.id) }))],
    ['branches', 4, ((branches && branches.branches) || []).filter(b => m([b.name, b.subject || '', b.upstream || ''].join(' '))).map(b => ({ icon: 'branch', html: code(b.name), href: '/project/branches/' + enc(b.name) }))],
    ['steps', 4, plan().steps.filter(st => m(`${st.id} ${L(st.title || '')} ${L(st.gate || '')}`)).map(st => ({ icon: 'layers', html: `${code(st.id)} ${rich(L(st.title || st.gate || ''))}`, href: '/problems/plan/' + st.id }))],
    ['screens', 4, ((section('screens') && section('screens').screens) || []).filter(sc => m([sc.id, sc.title, sc.route, sc.file].join(' '))).map(sc => ({ icon: 'screen', html: `${esc(L(sc.title || sc.id))} ${code(sc.route || '')}`, href: '/understand/screens/' + enc(sc.id) }))],
    ['paths', 4, ((section('paths') && section('paths').paths) || []).filter(p => m([p.id, L(p.title || ''), p.entry && (p.entry.path || p.entry)].join(' '))).map(p => ({ icon: 'map', html: `${code(p.id)} ${esc(L(p.title || ''))}`, href: '/understand/paths/' + enc(p.id) }))],
    ['gaps', 4, ((section('gaps') && section('gaps').gaps) || []).filter(g => m([g.id, g.component, g.operation, g.to].join(' '))).map(g => ({ icon: 'layers', html: `${code(g.id)} ${code(g.component || '')}`, href: '/understand/gaps/' + enc(g.id) }))],
    ['components', 4, ((section('story') && section('story').current.components) || []).filter(c => m(c.name)).map(c => ({ icon: 'map', html: code(c.name), href: '/understand/components/' + enc(c.name) }))],
    ['docs', 5, docs.filter(d => m([d.id, d.title, (d.titles && (d.titles.ar || '') + ' ' + (d.titles.en || '')) || '', d.path, (d.headings || []).map(h => h.text).join(' ')].join(' '))).map(d => ({ icon: 'book', html: `${esc((d.titles && d.titles[prefs.lang]) || d.title)} ${code(d.path)}`, href: '/understand/library/' + enc(d.id) }))],
  ];
  let left = 40; // up to 40 results, grouped by kind
  return groups.map(([group, cap, items]) => { const take = items.slice(0, Math.min(cap, left)); left -= take.length; return { group, items: take }; }).filter(g => g.items.length);
}

function listHTML(q) {
  const r = results(q);
  const item = (it, target) => `<button class="result" data-act="go" data-href="${target}">${it.sev ? sev(it.sev, false) : icon(it.icon)}<span class="result__text">${it.html}</span></button>`;
  const out = r.map(g => `<div class="results__group" role="group" aria-labelledby="sg-${g.group}"><p class="results__h" id="sg-${g.group}">${esc(t('search.' + g.group))}</p>${g.items.map(it =>
    item(it, href(it.href.split('?')[0], Object.fromEntries(new URLSearchParams(it.href.split('?')[1] || ''))))).join('')}</div>`).join('');
  const more = q.trim() ? `<div class="results__group" role="group" aria-labelledby="sg-more"><p class="results__h" id="sg-more">${esc(t('search.more'))}</p>
    ${item({ icon: 'code', html: esc(t('search.functions.in', { q })) }, href('/understand/functions', { q }))}
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
    if (!local.asked) {
      local.asked = true;
      need(SEARCHED).then(() => { if (local.q) rerenderSheet(); });
      if (client && !branches) client.branches.inventory().then(b => { branches = b; if (local.q) rerenderSheet(); }, () => {});
    }
    const input = el.querySelector('#search-input');
    input.addEventListener('input', () => { local.q = input.value; el.querySelector('#search-results').innerHTML = listHTML(input.value); });
    input.addEventListener('keydown', e => {
      const items = Array.from(el.querySelectorAll('.result'));
      if (!items.length) return;
      const i = items.findIndex(x => x.dataset.active === 'true');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const n = e.key === 'ArrowDown' ? Math.min(items.length - 1, i + 1) : Math.max(0, i - 1);
        items.forEach(x => delete x.dataset.active); items[n].dataset.active = 'true'; items[n].scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Enter') { e.preventDefault(); (items[i] || items[0]).click(); }
    });
  },
});
