// S-06 Problems: the list with its filters, groups and selection (PRB-01..05, PRB-11, PRB-12, SEL-01..04, SRC-03,
// LNK-01). The address carries the view (who, sev, area, pstate, step, comp, q, group, n); the list shows 50 problems
// at a time. A new check that lands while the person reads leaves the list as it was until they ask (PRB-11).
import {
  t, tn, L, num, esc, rich, icon, code, sev, chk, href, screen, sheet, act, tickAct, refresh, setQuery, searchTyped, parseHash, announce, closeSheetThen, setSelbar,
  S, model, selection, data,
} from 'eaos';
import { NEEDS, SEV, AREAS, STATES, FACETS, component, who, steps, value, list, filterProblems, activeFilters, facetLabel, keepQuery } from './shared.js';
import { detailHTML } from './detail.js';
import { empty } from '../kit/kit.js';

const PAGE = 50;

/* ---------- the problems drawn: held while a new check waits to be shown (PRB-11) ---------- */
let held = null;
function shown() {
  const cards = data.section('cards');
  if (!held || held.cards === cards || !S.newcheck) held = { cards, list: model.problems() };
  return held.list;
}
// a check that lands while Problems is open is announced, not swapped in
const stamp = () => (data.manifest() && data.manifest().scanned ? data.manifest().scanned.at : null);
let seenScan = null;
function watchScan() {
  const now = stamp();
  if (seenScan && now && now !== seenScan && parseHash().path.startsWith('/problems')) S.newcheck = true;
  seenScan = now;
}

function row(p, open) {
  const selected = selection.picked.ids.has(p.id);
  const stateTag = p.state !== 'open' ? `<span class="tag tag--state">${t('state.' + p.state)}</span>` : '';
  const whoTag = who(p) === 'you' ? `<span class="tag tag--you">${t('who.you')}</span>` : `<span class="tag tag--eaos">${t('who.eaos')}</span>`;
  return `<li class="prow ${selected ? 'is-selected' : ''} ${open ? 'is-open' : ''}">
    ${chk(`data-change="sel" value="${esc(p.id)}" data-fk="sel-${esc(p.id)}"`, selected, `${t('pd.select')}: ${p.id}`)}
    <a class="prow__link" href="${href('/problems/' + encodeURIComponent(p.id), keepQuery(parseHash().query))}" ${open ? 'aria-current="true"' : ''} data-fk="row-${esc(p.id)}">
      <span class="prow__top">${sev(p.severity)}${stateTag}<span class="prow__end">${whoTag}</span></span>
      <span class="prow__title">${rich(L(p.title))}</span>
      <span class="prow__meta">${code(p.id)}<span>${t('area.' + (p.category || 'none'))}</span>${code(p.paths[0] || '')}</span>
    </a></li>`;
}

function groupKey(p, g) {
  if (g === 'area') return t('area.' + (p.category || 'none'));
  if (g === 'component') return component(p);
  if (g === 'step') return p.milestone || t('facet.notplan');
  return '';
}

function listHTML(rows, q, openId) {
  if (!rows.length) {
    return `<div class="panel empty"><p class="empty__title">${t('pb.empty')}</p>
      <a class="btn btn--secondary" href="${href('/problems', q.who ? { who: q.who } : {})}">${t('pb.clear')}</a></div>`;
  }
  const g = q.group;
  if (!g || g === 'none') return `<ul class="panel rows plist">${rows.map(p => row(p, p.id === openId)).join('')}</ul>`;
  const groups = new Map();
  rows.forEach(p => { const k = groupKey(p, g); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(p); });
  const order = Array.from(groups.keys());
  if (g === 'step') order.sort((a, b) => steps().indexOf(a) - steps().indexOf(b));
  return `<div class="panel">${order.map(k => `<div class="group-head"><span>${k.includes('/') ? code(k) : esc(k)}</span><span class="num">${num(groups.get(k).length)}</span></div>
    <ul class="rows plist">${groups.get(k).map(p => row(p, p.id === openId)).join('')}</ul>`).join('')}</div>`;
}

function listColumn(q, openId) {
  const all = shown();
  const rows = filterProblems(all, q);
  const limit = Math.max(PAGE, Number(q.n) || PAGE);
  // the problem open beside the list is always in it, however far down it is
  const at = openId ? rows.findIndex(p => p.id === openId) : -1;
  const visible = rows.slice(0, Math.max(limit, at + 1));
  const tot = model.totals();
  const whoSeg = [['all', t('who.all'), tot.problems], ['you', t('who.you'), tot.needs_you], ['eaos', t('who.eaos'), tot.fixable]]
    .map(([k, label, n]) => `<a href="${href('/problems', keepQuery(q, { who: k === 'all' ? null : k, n: null }))}" aria-current="${(q.who || 'all') === k}"><span>${label}</span><b>${num(n)}</b></a>`).join('');
  const active = activeFilters(q);
  const chips = active.length ? `<div class="fchips">${active.map(a => `<button class="fchip" data-act="facet-remove" data-facet="${a.f}" data-value="${esc(a.v)}" aria-label="${esc(facetLabel(a.f, a.v))}: ${esc(t('close'))}">${esc(facetLabel(a.f, a.v))}${icon('x')}</button>`).join('')}
    <button class="fchip" data-act="facet-clear">${t('flt.clear')}</button></div>` : '';
  const fixesItself = rows.filter(p => p.decision && p.decision.state === 'fixes' && p.state === 'open');
  const band = fixesItself.length ? `<div class="ai-block band">${icon('ai', 'icon--sm')}<span class="band__text">${esc(t('pb.band', { problems: tn('pl.problem', fixesItself.length) }))}</span>
    <button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="verb:fix:assistant">${t('pb.band.fix')}</button>
    <button class="btn btn--quiet btn--sm" data-act="select-ids" data-ids="${esc(fixesItself.map(p => p.id).join(','))}">${t('pb.band.select')}</button></div>` : '';
  const more = rows.length - visible.length;
  return `<div class="psplit__list">
    <div class="context"><div class="seg" role="group" aria-label="${esc(t('pb.place'))}" style="min-width:200px">
      <a href="${href('/problems')}" aria-current="true">${t('pb.view.list')}</a><a href="${href('/problems/plan')}">${t('pb.view.plan')}</a></div></div>
    <h1 class="lede">${esc(t('pb.lede', { total: tn('pl.problem', tot.problems), fixable: num(tot.fixable), you: num(tot.needs_you) }))}</h1>
    <p class="guide">${t('pb.guide')}</p>
    <div class="ptools">
      <nav class="seg seg--count" aria-label="${esc(t('facet.who'))}">${whoSeg}</nav>
      <div class="ptools__row">
        <label class="field">${icon('search')}<span class="sr-only">${t('pb.search')}</span>
          <input type="search" id="pq" data-fk="pq" data-input="pq" value="${esc(q.q || '')}" placeholder="${esc(t('pb.search'))}" autocomplete="off"></label>
        <button class="btn btn--secondary" data-act="sheet" data-sheet="filters" data-fk="flt">${icon('filter')}${active.length ? t('pb.filter.n', { n: active.length }) : t('pb.filter')}</button>
      </div>
      ${chips}
    </div>
    ${S.newcheck ? `<div class="panel row row--you" role="status" style="margin-top:16px">${icon('info')}<span class="row__main small">${t('pb.newcheck')}</span>
      <button class="btn btn--quiet btn--sm" data-act="newcheck-show">${t('pb.newcheck.show')}</button></div>` : ''}
    ${band}
    <div class="listhead">
      <span class="listhead__count" aria-live="polite">${esc(t('pb.count', { shown: num(visible.length), total: num(rows.length) }))}. ${t('pb.order')}${q.group && q.group !== 'none' ? `. ${t('pb.group.n', { g: t('grp.' + q.group) })}` : ''}</span>
      <span class="listhead__acts">
        <button class="btn btn--plain btn--sm" data-act="sheet" data-sheet="groups">${icon('select', 'icon--sm')}${t('pb.selgroup')}</button>
        <button class="btn btn--plain btn--sm only-desk" data-act="select-ids" data-ids="${esc(rows.filter(p => p.state === 'open').slice(0, 500).map(p => p.id).join(','))}">${t('pb.selall')}</button>
      </span>
    </div>
    ${listHTML(visible, q, openId)}
    ${more > 0 ? `<div class="actions" style="justify-content:center;margin-top:12px"><a class="btn btn--secondary" href="${href(parseHash().path, keepQuery(q, { n: limit + PAGE }))}" data-fk="more">${esc(t('pb.more', { n: num(Math.min(PAGE, more)), left: num(more) }))}</a></div>` : ''}
  </div>`;
}

function page(ctx) {
  const q = ctx.query, id = ctx.params.id;
  watchScan();
  if (ctx.state === 'empty') return empty(t('pb.nocheck'), t('pb.nocheck.guide'));
  const p = id ? shown().find(x => x.id === id) : null;
  const detail = id
    ? (p ? detailHTML(p, ctx) : `<div class="empty"><p class="empty__title">${esc(t('pd.notfound', { id }))}</p><p class="small ink-2">${t('pd.notfound.guide')}</p><a class="btn btn--secondary" href="${href('/problems')}">${t('pd.back')}</a></div>`)
    : `<div class="empty" style="justify-items:center;text-align:center;padding:64px 16px">${icon('problems', 'icon--lg muted')}<p class="muted">${t('pd.none')}</p></div>`;
  return `<div class="page page--wide">
    <div class="psplit ${id ? 'psplit--detail' : ''}">
      ${listColumn(q, id)}
      <div class="psplit__detail" ${id ? '' : 'aria-hidden="true"'}>${detail}</div>
    </div></div>`;
}

function loading() {
  return `<div class="page page--wide" aria-busy="true"><h1 class="lede">${t('st.loading')}</h1>
    <ul class="panel rows" style="margin-top:24px">${[1, 2, 3, 4, 5].map(() => `<li class="prow"><span class="skel" style="width:22px;height:22px"></span><span style="flex:1;display:grid;gap:8px"><span class="skel-line" style="width:40%"></span><span class="skel-line" style="width:90%"></span><span class="skel-line" style="width:60%"></span></span></li>`).join('')}</ul></div>`;
}

screen({ id: 'S-06', path: '/problems', place: 'problems', needs: NEEDS, loading, title: () => t('pb.place'), render: page });
screen({
  id: 'S-07', path: '/problems/:id', place: 'problems', loading,
  needs: NEEDS.concat(['evidence', 'decisions']),
  title: ctx => ctx.params.id + ' - ' + t('pb.place'), render: page,
  after(main) {
    if (matchMedia('(max-width: 1023px)').matches) return;
    setTimeout(() => { const el = main.querySelector('.prow.is-open'); if (el) el.scrollIntoView({ block: 'center' }); }, 0);
  },
});

/* ---------- selection (SEL-01..04) ---------- */
tickAct('sel', '.plist', '.prow input[type=checkbox], .pdetail input[type=checkbox]');
act('select-ids', el => {
  selection.pick(el.dataset.ids.split(',').filter(Boolean));
  refresh();
  announce(tn('pl.selected', selection.picked.ids.size));
});
act('sel-clear', () => { selection.clearSelection(); refresh(); });
setSelbar('sel-clear');

/* ---------- search inside the view (PRB-02) ---------- */
act('pq', el => searchTyped(el, 180, { n: null }));

/* ---------- filters (PRB-04, PRB-05) ---------- */
function facetValues(f) {
  if (f === 'sev') return SEV.slice();
  if (f === 'area') return AREAS.slice();
  if (f === 'pstate') return STATES.slice();
  if (f === 'step') return steps().concat(['notplan']);
  return Array.from(new Set(shown().map(component))).sort();
}
const facetTitle = f => t('facet.' + (f === 'sev' ? 'severity' : f === 'comp' ? 'component' : f === 'pstate' ? 'state' : f));
sheet('filters', {
  needs: ['cards', 'plans', 'story', 'system'],
  kind: 'drawer',
  render(arg, q) {
    const all = shown();
    const count = filterProblems(all, q).length;
    const groups = ['none', 'area', 'component', 'step'].map(g => `<button type="button" data-act="group" data-group="${g}" data-fk="grp-${g}" aria-pressed="${(q.group || 'none') === g}">${t('grp.' + g)}</button>`).join('');
    const facets = FACETS.map(f => {
      const base = filterProblems(all, q, f);
      const sel = list(q, f);
      const vals = facetValues(f);
      sel.forEach(v => { if (!vals.includes(v)) vals.push(v); }); // a value from an old link stays visible with 0
      const items = vals.map((v, i) => {
        const n = base.filter(p => value(p, f) === v).length;
        const on = sel.includes(v);
        const hide = vals.length > 12 && i >= 8 && !on ? 'data-more hidden' : '';
        return `<label class="row" style="min-height:48px;padding-inline:4px;gap:12px" ${hide}>
          ${chk(`data-change="facet" data-facet="${f}" value="${esc(v)}" data-fk="f-${f}-${esc(v)}" ${n || on ? '' : 'disabled'}`, on, facetLabel(f, v))}
          <span class="row__main" style="margin-inline-start:8px;${n ? '' : 'color:var(--ink-3)'}">${f === 'sev' ? sev(v) : f === 'comp' ? code(v) : esc(facetLabel(f, v))}</span>
          <span class="num ${n ? '' : 'muted'}">${num(n)}</span></label>`;
      }).join('');
      const more = vals.length > 12 ? `<button class="btn btn--quiet btn--sm" data-act="facet-more">${t('facet.more', { n: num(vals.length) })}</button>` : '';
      return `<fieldset style="border:0;padding:0;margin:0"><legend class="block-title">${facetTitle(f)}</legend><div class="rows">${items}</div>${more}</fieldset>`;
    }).join('');
    return {
      title: esc(t('flt.title')), sub: esc(t('flt.sub')),
      body: `<div><div class="block-title">${t('grp.title')}</div><div class="seg" role="group" aria-label="${esc(t('grp.title'))}">${groups}</div></div>${facets}`,
      foot: `<div class="sheet__foot-row"><button class="btn btn--secondary" data-act="facet-clear">${t('flt.clear')}</button>
        <button class="btn btn--primary" data-act="sheet-close" data-fk="flt-show">${esc(t('flt.show', { problems: tn('pl.problem', count) }))}</button></div>`,
    };
  },
});
act('facet', el => {
  const q = parseHash().query, f = el.dataset.facet;
  const vals = list(q, f).filter(v => v !== el.value);
  if (el.checked) vals.push(el.value);
  setQuery({ [f]: vals.join(',') || null, n: null });
});
act('facet-remove', el => {
  const q = parseHash().query, f = el.dataset.facet;
  setQuery({ [f]: list(q, f).filter(v => v !== el.dataset.value).join(',') || null, n: null });
});
act('facet-clear', () => { const o = { q: null, n: null }; FACETS.forEach(f => { o[f] = null; }); setQuery(o); });
act('facet-more', el => { el.closest('fieldset').querySelectorAll('[data-more]').forEach(x => x.removeAttribute('hidden')); el.remove(); });
act('newcheck-show', () => { S.newcheck = false; held = null; refresh(); });
act('group', el => setQuery({ group: el.dataset.group === 'none' ? null : el.dataset.group }));

/* ---------- select a group whole (SEL-02): sent by its name where the server resolves it the same way ---------- */
sheet('groups', {
  needs: ['cards', 'plans', 'story', 'system'],
  kind: 'drawer',
  render() {
    const groups = selection.groupsOf(shown());
    const kinds = [['severity', v => sev(v)], ['area', v => esc(t('area.' + v))], ['step', v => code(v)], ['component', v => code(v)]];
    const body = kinds.map(([k, label]) => {
      const rows = groups[k].map(g => `<button class="row" data-act="select-group" data-by="${k}" data-value="${esc(g.value)}"><span class="row__main">${label(g.value)}</span><span class="num muted">${num(g.ids.length)}</span>${icon('chev', 'icon--sm icon--dir muted')}</button>`).join('');
      return rows ? `<div><div class="block-title">${t('facet.' + k)}</div><div class="panel rows">${rows}</div></div>` : '';
    }).join('');
    return { title: esc(t('sg.title')), sub: esc(t('sg.sub')), body };
  },
});
act('select-group', el => {
  const g = selection.groupsOf(shown())[el.dataset.by].find(x => x.value === el.dataset.value);
  if (!g) return;
  const label = el.dataset.by === 'severity' ? t('sev.' + g.value) : el.dataset.by === 'area' ? t('area.' + g.value) : g.value;
  selection.pick(g.ids, { by: el.dataset.by, value: g.value, label });
  closeSheetThen(() => { refresh(); announce(tn('pl.selected', selection.picked.ids.size)); });
});

