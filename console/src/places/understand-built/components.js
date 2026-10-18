// S-24 the components map (SYS-01, SYS-03, SYS-04, SYS-18) and S-25 one component (SYS-02), on system.json: the
// project as territory, laid out by EAOS (regions, components, weighted import links), today, as the change and as the
// target. Desktop: the map with an inspector; the phone: a still preview, the explorer one press away (?sheet=map:<mode>),
// and the ranked list, the map's twin. At rest only the heaviest links are drawn; a focused component keeps its
// neighbourhood and fades the rest.
import { t, tn, L, num, esc, icon, code, href, rich, screen, sheet, data, parseHash, offline } from 'eaos';
import {
  tabs, seg, prov, nm, search, opTag, opOf, glyph, OPS, sevMix, findings, band, facts, fold, enc, back, zoomBar, after, loading, matches,
  empty, keyItem, openOf, q as query, decisionLink,
} from '../understand-kit/kit.js';
import { components, component, targets, targetOf, storyCounts, problemsOf } from '../understand-kit/model.js';

const REST = 40; // links drawn at rest (DESIGN-SYSTEM 8)
const SEVW = { critical: 8, high: 4, medium: 2, low: 1 };
const sevWeight = f => Object.keys(SEVW).reduce((s, k) => s + ((f && f[k]) || 0) * SEVW[k], 0);
const modeOf = q => (q.mode === 'change' || q.mode === 'target' ? q.mode : 'today');
const sys = () => data.section('system');
const compLink = (id, q, extra) => href('/understand/components/' + enc(id), Object.assign({ mode: q.mode, lens: q.lens, only: q.only }, extra || {}));
/** Unseen work a component holds (hidden.json components: the items of each group under it). */
const unseen = id => { const h = data.section('hidden'); const c = h && h.components && h.components[id]; return c ? Object.values(c).reduce((s, n) => s + n, 0) : 0; };

function viewBox(view) {
  const [x, y, w, h] = view.bounds || [0, 0, 1000, 900];
  return `${x - 20} ${y - 20} ${w + 40} ${h + 40}`;
}
function lands(view, still) {
  return view.regions.map(r => `<g class="un-map__region">${(r.land || []).map(l => `<path class="un-map__land un-map__land--${l.level}" d="${l.d}"/>`).join('')}
    ${still ? '' : `<text x="${r.label.x}" y="${r.label.y}" text-anchor="middle">${esc(L(r.name))}</text>`}</g>`).join('');
}
const label = (n, still, cls) => (still || !n.label || !n.label.placed ? '' : `<text class="un-map__label ${cls || ''}" x="${n.label.x}" y="${n.label.y}" text-anchor="${n.label.anchor || 'middle'}" style="font-size:${((n.label.size || 12) * 1.05).toFixed(1)}px">${esc(n.short || n.id)}</text>`);

/** The map of today or of the change. */
function mapSVG(q, focusId, still) {
  const s = sys(), mode = modeOf(q);
  if (mode === 'target') return targetSVG(q, focusId, still);
  const view = s.current, comps = view.nodes;
  const nb = new Set();
  if (focusId) view.edges.forEach(l => { if (l.from === focusId) nb.add(l.to); if (l.to === focusId) nb.add(l.from); });
  const found = q.q ? new Set(comps.filter(c => matches(c.id, q.q)).map(c => c.id)) : null;
  const faded = c => (focusId && c.id !== focusId && !nb.has(c.id)) || (found && !found.has(c.id)) || (mode === 'change' && q.only && opOf(c.op) !== q.only);
  const heavy = new Set(view.edges.slice().sort((a, b) => b.imports - a.imports).slice(0, REST));
  const links = view.edges.filter(l => (focusId ? l.from === focusId || l.to === focusId : heavy.has(l))).map(l => {
    const on = focusId && (l.from === focusId || l.to === focusId);
    return `<path class="un-map__link ${l.cycle ? 'un-map__link--cycle' : ''} ${on ? 'is-on' : ''}" d="${l.d}" stroke-width="${(l.width || 1).toFixed(1)}"/>${on && l.mid ? `<text class="un-map__lcount" x="${l.mid[0]}" y="${l.mid[1] - 4}">${num(l.imports)}</text>` : ''}`;
  }).join('');
  const nodes = comps.map(c => {
    const f = findings(c.findings);
    const op = opOf(c.op);
    const tip = mode === 'change' ? `${c.id}: ${t('un.op.' + op)}${c.target ? ' → ' + c.target : ''}, ${tn('pl.file', c.files)}`
      : `${c.id}: ${tn('pl.file', c.files)}, ${tn('pl.problem', f)}, ${t('un.map.usedby', { n: num(c.fan_in || 0) })}`;
    const fill = mode === 'change' ? `un-map__node--${op}` : `un-map__node--fb${band(f)}`;
    const g = mode === 'change' ? `<g transform="translate(${c.x - 7} ${c.y - 7})" class="un-map__glyph">${glyph(op, 14)}</g>` : '';
    const u = q.lens === 'unseen' ? unseen(c.id) : 0;
    const badge = u ? `<g class="un-map__badge"><rect x="${c.x + c.r - 4}" y="${c.y - c.r - 14}" width="${String(u).length * 9 + 14}" height="20" rx="10"/><text x="${c.x + c.r + 3 + String(u).length * 4.5}" y="${c.y - c.r + 1}">${u}</text></g>` : '';
    const body = `<circle class="un-map__node ${fill}" cx="${c.x}" cy="${c.y}" r="${Math.max(mode === 'change' ? 9 : 5, c.r).toFixed(1)}"/>${g}${label(c, still)}${badge}`;
    return still ? `<g class="${faded(c) ? 'is-off' : ''}">${body}</g>`
      : `<a href="${compLink(c.id, q)}" class="un-map__a ${faded(c) ? 'is-off' : ''} ${c.id === focusId ? 'is-focus' : ''}" data-tip="${esc(tip)}" aria-label="${esc(tip)}">${body}<title>${esc(tip)}</title></a>`;
  }).join('');
  return `<svg class="un-map ${still ? 'un-map--still' : ''}" viewBox="${viewBox(view)}" ${still ? 'aria-hidden="true"' : `role="group" aria-label="${esc(t('un.map.label.' + mode))}" tabindex="0"`}>${lands(view, still)}<g>${links}</g><g>${nodes}</g></svg>`;
}
function targetSVG(q, focusId, still) {
  const view = sys().target;
  const nb = new Set();
  if (focusId) view.edges.forEach(l => { if (l.from === focusId) nb.add(l.to); if (l.to === focusId) nb.add(l.from); });
  const links = view.edges.map(l => {
    const on = focusId && (l.from === focusId || l.to === focusId);
    return `<path class="un-map__link ${on ? 'is-on' : ''} ${focusId && !on ? 'is-off' : ''}" d="${l.d}" stroke-width="${(l.width || 1).toFixed(1)}"/>${on && l.mid ? `<text class="un-map__lcount" x="${l.mid[0]}" y="${l.mid[1] - 4}">${num(l.imports)}</text>` : ''}`;
  }).join('');
  const nodes = view.nodes.map(x => {
    const fresh = !(x.sources || []).length;
    const tip = `${x.id}: ${L(x.responsibility || '')} ${tn('pl.file', x.files)}`;
    const body = `<circle class="un-map__node un-map__node--target ${fresh ? 'un-map__node--new' : ''}" cx="${x.x}" cy="${x.y}" r="${x.r.toFixed(1)}"/>${label(x, still, 'un-map__label--t')}`;
    const off = focusId && x.id !== focusId && !nb.has(x.id);
    return still ? `<g class="${off ? 'is-off' : ''}">${body}</g>` : `<a href="${compLink(x.id, q)}" class="un-map__a ${off ? 'is-off' : ''} ${x.id === focusId ? 'is-focus' : ''}" data-tip="${esc(tip)}" aria-label="${esc(tip)}">${body}<title>${esc(tip)}</title></a>`;
  }).join('');
  return `<svg class="un-map ${still ? 'un-map--still' : ''}" viewBox="${viewBox(view)}" ${still ? 'aria-hidden="true"' : `role="group" aria-label="${esc(t('un.map.label.target'))}" tabindex="0"`}>${lands(view, still)}<g>${links}</g><g>${nodes}</g></svg>`;
}
/** A key listing only what is drawn. */
function mapKey(q) {
  const mode = modeOf(q);
  if (mode === 'target') return `<div class="un-key">${keyItem('rules')}${targets().some(x => !(x.sources || []).length) ? `<span class="un-key__item"><span class="un-key__sw un-key__sw--nm" aria-hidden="true"></span>${t('un.map.key.new')}</span>` : ''}</div>`;
  if (mode === 'change') return `<div class="un-key">${OPS.filter(o => components().some(c => opOf(c.op) === o)).map(o => `<span class="un-key__item">${opTag(o)}</span>`).join('')}</div>`;
  const bands = [0, 1, 2, 3, 4].filter(b => components().some(c => band(findings(c.findings)) === b));
  return `<div class="un-key">${bands.map(b => `<span class="un-key__item"><span class="un-key__dot un-key__dot--fb${b}" aria-hidden="true"></span>${t('un.map.band' + b)}</span>`).join('')}
    ${sys().current.edges.some(e => e.cycle) ? `<span class="un-key__item"><span class="un-key__line un-key__line--cycle" aria-hidden="true"></span>${t('un.map.key.cycle')}</span>` : ''}
    ${q.lens === 'unseen' ? `<span class="un-key__item"><span class="un-key__badge" aria-hidden="true">n</span>${t('un.map.key.unseen')}</span>` : ''}</div>`;
}

/* ---------- the ranked list, the map's twin (SYS-03) ---------- */
function ranked(q, focusId) {
  const mode = modeOf(q);
  if (mode === 'target') {
    return `<ul class="panel rows">${targets().slice().sort((a, b) => b.files - a.files).map(x => `<li><a class="row ${x.id === focusId ? 'is-open' : ''}" href="${compLink(x.id, q)}">
      <span class="row__main"><span class="un-gaprow__top">${code(x.id)}${(x.sources || []).length ? '' : `<span class="tag tag--state">${t('un.op.introduce')}</span>`}</span><span class="row__meta" style="display:block">${x.layer ? esc(t('un.layer', { layer: x.layer })) : ''}</span></span>
      <span class="row__end num">${esc(tn('pl.file', x.files))}</span>${icon('chev', 'icon--sm icon--dir muted')}</a></li>`).join('')}</ul>`;
  }
  let comps = components().slice().sort((a, b) => (sevWeight(b.findings) - sevWeight(a.findings)) || (findings(b.findings) - findings(a.findings)) || (b.files - a.files) || a.id.localeCompare(b.id));
  if (q.q) comps = comps.filter(c => matches(c.id, q.q));
  if (mode === 'change' && q.only) comps = comps.filter(c => opOf(c.op) === q.only);
  if (!comps.length) return `<div class="panel empty"><p class="empty__title">${t('un.comp.none')}</p></div>`;
  return `<ul class="panel rows">${comps.map(c => {
    const u = q.lens === 'unseen' ? unseen(c.id) : 0;
    return `<li><a class="row ${c.id === focusId ? 'is-open' : ''}" href="${compLink(c.id, q)}">
    <span class="row__main"><span class="un-gaprow__top">${code(c.id)}${u ? `<span class="tag tag--state">${esc(t('un.comp.unseen', { n: num(u) }))}</span>` : ''}</span>
      <span class="row__meta" style="display:block">${mode === 'change' ? `${opTag(c.op, true)} ${c.target ? code(c.target) : ''}` : esc(tn('pl.file', c.files))}</span></span>
    <span class="row__end">${sevMix(c.findings)}</span>${icon('chev', 'icon--sm icon--dir muted')}</a></li>`;
  }).join('')}</ul>`;
}
function regionsFold() {
  const regions = sys().current.regions;
  return `<div class="panel" style="margin-top:12px">${fold(t('un.comp.regions'), esc(tn('un.pl.region', regions.length)), `<div class="un-table-wrap"><table class="un-table">
    <thead><tr><th scope="col">${t('un.comp.region')}</th><th scope="col">${t('un.comp.comps')}</th><th scope="col">${t('un.gap.files')}</th><th scope="col">${t('un.comp.findingsk')}</th></tr></thead>
    <tbody>${regions.map(r => `<tr><th scope="row">${esc(L(r.name))}</th><td class="num">${num(r.components)}</td><td class="num">${num(r.files)}</td><td class="num">${r.findings == null ? '—' : num(r.findings)}</td></tr>`).join('')}</tbody></table></div>`)}</div>`;
}

/* ---------- one component: the inspector (SYS-02) ---------- */
function nbList(list, other, q, total) {
  return `${list.slice(0, 6).map(l => `<li><a class="row" href="${compLink(l[other], q)}">${code(l[other])}<span class="row__main"></span><span class="small muted num">${esc(tn('un.pl.import', l.imports))}</span></a></li>`).join('')}
    ${total > Math.min(6, list.length) ? `<li class="row small muted" style="min-height:40px">${esc(t('un.comp.andmore', { n: num(total - Math.min(6, list.length)) }))}</li>` : ''}`;
}
function inspector(id, q) {
  const T = targetOf(id);
  if (T && (modeOf(q) === 'target' || !component(id))) return targetInspector(T, q);
  const c = component(id);
  if (!c) return `<div class="empty"><p class="empty__title">${esc(t('pd.notfound', { id }))}</p><p class="small ink-2">${t('un.notfound.guide')}</p></div>`;
  const probs = problemsOf(c.id), open = openOf(probs.map(p => p.id));
  const edges = sys().current.edges;
  const callers = edges.filter(l => l.to === c.id).sort((a, b) => b.imports - a.imports);
  const uses = edges.filter(l => l.from === c.id).sort((a, b) => b.imports - a.imports);
  const gap = ((data.section('gaps') || {}).gaps || []).find(g => g.component === c.id);
  const region = sys().current.regions.find(r => r.id === c.region);
  const u = unseen(c.id);
  return `<article class="un-insp" aria-labelledby="ci-title">
    ${back('/understand/components', t('un.v.components'), { mode: q.mode, lens: q.lens })}
    <div class="un-itemtags">${opTag(c.op)}${c.target ? `<span class="un-to">${icon('chev', 'icon--sm icon--dir muted')}${code(c.target)}</span>` : ''}</div>
    <h2 class="title" id="ci-title">${code(c.id)}</h2>
    <p class="small ink-2">${esc(t('un.comp.sum', { region: region ? L(region.name) : '—', files: tn('pl.file', c.files), by: num(c.fan_in || 0), uses: num(c.fan_out || 0) }))}</p>
    <div class="un-insp__acts">
      ${open.length && !offline() ? `<button class="btn btn--primary" data-act="un-select" data-ids="${esc(open.join(','))}" data-name="${esc(c.id)}" data-comp="${esc(c.id)}">${esc(t('un.comp.select', { n: num(open.length) }))}</button>`
        : `<a class="btn btn--secondary" href="${href('/problems', { comp: c.id })}">${t('un.comp.open')}</a>`}
      ${gap ? `<a class="btn btn--quiet" href="${href('/understand/gaps/' + enc(gap.id))}">${t('un.comp.gap')}</a>` : ''}
    </div>
    <section class="psec"><h3 class="h2">${t('un.comp.findings')}</h3>${sevMix(c.findings, true)}</section>
    <section class="psec"><h3 class="h2">${t('un.comp.usedby')}</h3><ul class="rows un-insp__list">${callers.length ? nbList(callers, 'from', q, callers.length) : `<li class="small muted">${t('un.comp.nousers')}</li>`}</ul></section>
    <section class="psec"><h3 class="h2">${t('un.comp.uses')}</h3><ul class="rows un-insp__list">${uses.length ? nbList(uses, 'to', q, uses.length) : `<li class="small muted">${t('un.comp.nouses')}</li>`}</ul></section>
    <section class="psec"><h3 class="h2">${t('un.comp.change')}</h3>
      ${facts([
        [t('un.gap.becomes'), c.target ? code(c.target) : t('un.gap.removed')],
        c.merged_with ? [t('un.gap.merged'), esc(tn('un.pl.comp', c.merged_with))] : null,
        [t('un.comp.decision'), c.decision ? `${decisionLink(c.decision.id)}${c.decision.chosen ? `<span class="small ink-2" style="display:block">${rich(L(c.decision.chosen))}</span>` : ''}` : c.reason ? rich(L(c.reason)) : t('un.comp.nodecision')],
        [t('un.comp.unseenk'), u ? esc(t('un.comp.unseen', { n: num(u) })) : t('un.none')],
      ])}</section>
    <div class="un-insp__more">
      <a class="link" href="${href('/understand/paths', { through: c.id })}">${icon('code', 'icon--sm')}${t('un.comp.paths')}</a>
      ${c.target ? `<a class="link" href="${compLink(c.target, Object.assign({}, q, { mode: 'target' }), { mode: 'target' })}">${icon('map', 'icon--sm')}${t('un.comp.intarget')}</a>` : ''}
    </div>
  </article>`;
}
function targetInspector(x, q) {
  const src = components().filter(c => c.target === x.id);
  const f = {}; src.forEach(c => ['critical', 'high', 'medium', 'low'].forEach(k => { f[k] = (f[k] || 0) + ((c.findings && c.findings[k]) || 0); }));
  const edges = sys().target.edges;
  const users = edges.filter(l => l.to === x.id), uses = edges.filter(l => l.from === x.id);
  return `<article class="un-insp" aria-labelledby="ci-title">
    ${back('/understand/components', t('un.v.components'), { mode: 'target' })}
    <div class="un-itemtags">${(x.sources || []).length ? opTag(x.op) : `<span class="tag tag--state">${glyph('introduce')}${t('un.op.introduce')}</span>`}<span class="tag tag--state">${t('un.key.rules')}</span></div>
    <h2 class="title" id="ci-title">${code(x.id)}</h2>
    <p class="small ink-2">${x.layer ? esc(t('un.layer', { layer: x.layer })) + t('list.sep') : ''}${esc(tn('pl.file', x.files))}</p>
    ${x.responsibility ? `<p>${rich(L(x.responsibility))}</p>` : ''}
    <section class="psec"><h3 class="h2">${t('un.comp.from')}</h3>${src.length ? `<ul class="rows un-insp__list">${src.map(c => `<li><a class="row" href="${compLink(c.id, Object.assign({}, q, { mode: 'change' }), { mode: 'change' })}">${code(c.id)}<span class="row__main"></span>${opTag(c.op, true)}</a></li>`).join('')}</ul>` : `<p class="small muted">${t('un.bridge.nosrc')}</p>`}</section>
    <section class="psec"><h3 class="h2">${t('un.comp.carriedf')}</h3>${sevMix(f, true)}${x.carried != null ? `<p class="small muted" style="margin-top:4px">${esc(tn('pl.problem', x.carried))}</p>` : ''}</section>
    <section class="psec">${facts([[t('un.comp.usedby'), users.length ? users.map(l => code(l.from)).join(' ') : t('un.none')], [t('un.comp.uses'), uses.length ? uses.map(l => code(l.to)).join(' ') : t('un.none')]])}</section>
  </article>`;
}

/* ---------- the page ---------- */
function page(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  const s = sys();
  if (!s) {
    return `<div class="page page--wide">${tabs('components')}<h1 class="lede">${t('un.comp.nm.lede')}</h1>
      ${nm(t('un.comp.nm'), t('un.comp.nm.why'), `<a class="btn btn--secondary btn--sm" href="${href('/understand/story')}">${t('un.comp.nm.act')}</a>`)}</div>`;
  }
  const q = ctx.query, id = ctx.params.id || null;
  const mode = modeOf(q);
  const focusId = id || q.focus || null;
  const c = storyCounts();
  const counts = s.counts || {};
  const v = m => (counts[m] ? counts[m].value : null);
  const lede = mode === 'change' ? t('un.comp.lede.change', { n: num(c.change), all: num(s.current.nodes.length) })
    : mode === 'target' ? t('un.comp.lede.target', { n: tn('un.pl.comp', s.target.nodes.length), k: num(s.target.nodes.filter(x => !(x.sources || []).length).length) })
    : t('un.comp.lede.today', { n: tn('un.pl.comp', v('components') || s.current.nodes.length), r: tn('un.pl.region', v('regions') || s.current.regions.length), links: tn('un.pl.link', v('edges') || s.current.edges.length) });
  const r = parseHash();
  const modeSeg = seg('mode', [['today', t('un.story.today')], ['change', t('un.story.change')], ['target', t('un.story.target')]], mode, t('un.comp.mode'), { dflt: 'today' });
  const lens = mode !== 'target' ? `<a class="btn btn--secondary btn--sm ${q.lens === 'unseen' ? 'is-on' : ''}" ${q.lens === 'unseen' ? 'aria-current="true"' : ''} href="${href(r.path, Object.assign({}, q, { lens: q.lens === 'unseen' ? null : 'unseen' }))}">${icon('screen', 'icon--sm')}${t('un.comp.lens')}</a>` : '';
  const only = mode === 'change' ? `<nav class="un-chips un-chips--sm" aria-label="${esc(t('un.comp.only'))}"><a href="${href(r.path, Object.assign({}, q, { only: null }))}" ${!q.only ? 'aria-current="true"' : ''}>${t('un.all')}</a>${OPS.filter(o => components().some(x => opOf(x.op) === o)).map(o => `<a href="${href(r.path, Object.assign({}, q, { only: o }))}" ${q.only === o ? 'aria-current="true"' : ''}>${glyph(o, 12)}${t('un.op.' + o)}</a>`).join('')}</nav>` : '';
  const capped = mode === 'today' && s.current.edges.length > REST && !focusId ? t('un.comp.capped', { links: num(REST), all: num(s.current.edges.length) }) : t('un.map.hint');
  const mapPanel = `<div class="panel un-mapwrap" data-zoom-root data-readout-root>
      <div class="un-mapwrap__bar">${zoomBar()}<a class="btn btn--plain btn--sm" href="${href(r.path, Object.assign({}, q, { view: 'list' }))}">${icon('problems', 'icon--sm')}${t('un.comp.aslist')}</a></div>
      ${mapSVG(q, focusId)}
      ${mapKey(q)}
      <p class="small muted un-readout" data-readout aria-live="polite">${esc(capped)}</p>
    </div>`;
  const deskMain = q.view === 'list'
    ? `<div><div class="un-mapwrap__bar" style="margin-bottom:8px"><a class="btn btn--plain btn--sm" href="${href(r.path, Object.assign({}, q, { view: null }))}">${icon('map', 'icon--sm')}${t('un.comp.asmap')}</a></div>${ranked(q, focusId)}${mode !== 'target' ? regionsFold() : ''}</div>`
    : mapPanel;
  const insp = focusId ? inspector(focusId, q) : `<div class="un-insp un-insp--empty">${icon('map', 'icon--lg muted')}<p class="muted">${t('un.comp.pick')}</p></div>`;
  return `<div class="page page--wide un-comp ${id ? 'un-comp--detail' : ''}">
    <div class="un-comp__intro">
      ${tabs('components')}
      <h1 class="lede">${esc(lede)}</h1>
      <p class="guide">${t('un.comp.guide')}</p>
      <div class="actions only-phone"><button class="btn btn--primary" data-act="sheet" data-sheet="map:${mode}">${icon('map')}${t('un.comp.openmap')}</button></div>
      ${mode !== 'today' ? prov(s.provenance) : ''}
      <div class="ptools">${modeSeg}<div class="un-tools">${search(q.q, t('un.comp.find'))}${lens}</div>${only}</div>
    </div>
    <div class="un-split">
      <div class="un-split__main">
        <div class="only-desk">${deskMain}</div>
        <div class="only-phone">
          <button class="un-preview" data-act="sheet" data-sheet="map:${mode}" aria-label="${esc(t('un.comp.openmap'))}">${mapSVG(q, focusId, true)}<span class="un-preview__cap">${icon('map', 'icon--sm')}${t('un.comp.still')}</span></button>
          <div class="section-head" style="margin-top:24px"><h2>${t('un.comp.ranked.' + mode)}</h2></div>
          ${ranked(q, focusId)}
          ${mode !== 'target' ? regionsFold() : ''}
        </div>
      </div>
      <aside class="un-split__side" aria-label="${esc(t('un.comp.inspector'))}">${insp}</aside>
    </div>
  </div>`;
}
const needs = ctx => ['system', 'cards', 'story', 'gaps', 'decisions', 'coverage'].concat(ctx.query.lens === 'unseen' ? ['hidden'] : []);
screen({ id: 'S-24', path: '/understand/components', place: 'understand', needs, title: () => t('un.v.components'), render: page, after, loading: () => loading(t('un.comp.loading')) });
screen({ id: 'S-25', path: '/understand/components/:id', place: 'understand', needs, title: ctx => ctx.params.id + ' - ' + t('un.v.components'), render: page, after, loading: () => loading(t('un.comp.loading')) });

/* The explorer on the phone: the same map, interactive, full height. */
sheet('map', {
  kind: 'sheet', full: true,
  needs: ['system'],
  render(mode) {
    if (!sys()) return { title: esc(t('un.comp.explorer')), body: nm(t('un.comp.nm'), t('un.comp.nm.why')) };
    const q = Object.assign({}, query(), { mode: mode === 'today' ? null : mode });
    return {
      title: esc(t('un.comp.explorer')),
      sub: esc(t('un.comp.explorer.sub')),
      body: `<div class="un-mapwrap un-mapwrap--sheet" data-zoom-root data-readout-root>${zoomBar()}${mapSVG(q, q.focus || null)}${mapKey(q)}<p class="small muted un-readout" data-readout aria-live="polite">${t('un.map.hint')}</p></div>`,
    };
  },
  after,
});
