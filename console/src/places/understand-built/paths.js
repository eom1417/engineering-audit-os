// S-26 the code paths (SYS-07) and S-27 one path (SYS-08), on paths.json: every page, server route and command
// through the seven layers, each node and link with its evidence, and a gap where the records stop (never an invented
// link). A link reached only through imports is possible, not traced ("Only what the trace confirms" hides it).
import { t, tn, L, num, esc, icon, code, href, screen, data, model, parseHash } from 'eaos';
import { tabs, seg, search, count, fold, facts, opTag, enc, back, loading, notMeasured, emptyView, notFound, matches, readout, where, page, q as query } from '../understand-kit/kit.js';

const NEEDS = ['paths', 'cards', 'gaps', 'system', 'coverage'];
const LANES = ['screen', 'component', 'handler', 'call', 'endpoint', 'service', 'data'];
const STOP = { no_server_route: 'no_route', trace_stopped: 'trace_stopped', component_not_found: 'no_component', handler_not_found: 'no_handler' };
const SURFACE = { page: 'screen', http: 'server', cli: 'command', job: 'job' };
const HOW = { call: 'calls', gap: 'stops', trace: 'stops' };
const howWord = h => t('un.how.' + (HOW[h] || h));
const surface = s => (SURFACE[s] ? t('un.surface.' + SURFACE[s]) : s);
const P = () => data.section('paths');

let indexed = null;
/** The nodes by id and the paths each node is on (once per section read). */
function index() {
  const d = P();
  if (indexed && indexed.d === d) return indexed;
  const on = new Map();
  d.paths.forEach(p => p.columns.forEach(c => c.forEach(id => { if (!on.has(id)) on.set(id, []); on.get(id).push(p.id); })));
  indexed = { d, node: new Map(d.nodes.map(n => [n.id, n])), on };
  return indexed;
}
const nodeOf = id => index().node.get(id);
/** The nodes of a path the flow does not confirm: reached from the entry only through `imports` links. */
function possible(p) {
  const d = P(), out = new Map();
  p.steps.forEach(i => { const e = d.edges[i]; if (e.how !== 'imports') { if (!out.has(e.from)) out.set(e.from, []); out.get(e.from).push(e.to); } });
  const sure = new Set([p.entry]), queue = [p.entry];
  while (queue.length) for (const to of out.get(queue.shift()) || []) if (!sure.has(to)) { sure.add(to); queue.push(to); }
  return new Set(p.columns.flat().filter(id => !sure.has(id)));
}
/** Each lane of a path: 0 not on it, 1 traced, 2 possible only, 'g' where the records stop. */
function reachOf(p) {
  const maybe = possible(p);
  return p.columns.map(c => (!c.length ? 0 : c.some(id => (nodeOf(id) || {}).kind === 'gap') ? 'g' : c.every(id => maybe.has(id)) ? 2 : 1));
}
const stopOf = p => { const g = p.columns.flat().map(nodeOf).find(n => n && n.kind === 'gap'); return g ? g.reason : null; };

function reach(p) {
  const cell = 22, r = 5.5, w = cell * 7, rv = reachOf(p);
  const words = [];
  const marks = rv.map((v, i) => {
    const x = i * cell + cell / 2;
    if (v === 1) { words.push(t('un.layer.' + LANES[i])); return `<circle cx="${x}" cy="9" r="${r}" class="un-reach__on"/>`; }
    if (v === 2) { words.push(t('un.layer.' + LANES[i]) + ' (' + t('un.how.possible') + ')'); return `<circle cx="${x}" cy="9" r="${r}" class="un-reach__maybe"/>`; }
    if (v === 'g') return `<circle cx="${x}" cy="9" r="${r}" class="un-reach__gap"/>`;
    return `<circle cx="${x}" cy="9" r="1.6" class="un-reach__none"/>`;
  }).join('');
  const first = rv.findIndex(v => v !== 0), last = 6 - rv.slice().reverse().findIndex(v => v !== 0);
  const line = first >= 0 && last > first ? `<line x1="${first * cell + cell / 2}" y1="9" x2="${last * cell + cell / 2}" y2="9" class="un-reach__line"/>` : '';
  const stopAt = rv.indexOf('g');
  const label = t('un.paths.reach', { list: words.join(t('list.sep')) || t('un.none') }) + (stopAt >= 0 ? ' ' + t('un.paths.stopsat', { layer: t('un.layer.' + LANES[stopAt]) }) : '');
  return `<svg class="un-reach" viewBox="0 0 ${w} 18" width="${w}" height="18" role="img" aria-label="${esc(label)}">${line}${marks}</svg>`;
}
const layerHead = () => `<div class="un-reachhead only-desk" aria-hidden="true">${LANES.map(l => `<span>${t('un.layer.' + l)}</span>`).join('')}</div>`;
function pathRow(p) {
  const stop = stopOf(p);
  const links = p.steps.filter(i => !['gap', 'trace'].includes(P().edges[i].how)).length;
  return `<a class="row un-pathrow" href="${href('/understand/paths/' + enc(p.id))}">
    <span class="row__main"><span class="row__title">${code(p.title)}${p.handler ? ` <span class="small muted">${esc(p.handler)}</span>` : ''}</span>
      <span class="row__meta" style="display:block">${esc(surface(p.surface))}${stop ? `${t('list.sep')}<span class="caution-ic">${esc(t('un.stop.' + STOP[stop]))}</span>` : `${t('list.sep')}${esc(tn('un.pl.link', links))}`}</span></span>
    <span class="row__end">${reach(p)}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
}
const reachKey = () => ['on', 'maybe', 'gap'].map((k, i) => `<span class="un-key__item"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5" class="un-reach__${k}"/></svg>${t(['un.how.traced', 'un.how.possible', 'un.how.stop'][i])}</span>`).join('');

function pathsPage(ctx) {
  if (ctx.state === 'empty') return emptyView('paths');
  const d = P();
  if (!d) return notMeasured('paths', 'paths');
  const q = ctx.query, f = q.filter || 'all';
  const { node } = index();
  let rows = d.paths.filter(p => f === 'all' || (f === 'gaps' && p.gaps > 0) || (f === 'screens' && p.surface === 'page') || (f === 'server' && p.surface !== 'page'));
  if (q.through) rows = rows.filter(p => p.columns.flat().some(id => (node.get(id) || {}).component === q.through));
  if (q.q) rows = rows.filter(p => matches([p.id, p.title, p.handler || ''].concat(p.columns.flat().map(id => { const n = node.get(id); return n ? `${n.label} ${n.path || ''}` : ''; })).join(' '), q.q));
  const r = parseHash();
  const c = d.counts || {}, v = k => (c[k] ? c[k].value : null);
  const gaps = d.paths.filter(p => p.gaps > 0).length;
  const through = q.through ? `<div class="fchips"><a class="fchip" href="${href(r.path, Object.assign({}, q, { through: null }))}" aria-label="${esc(t('un.paths.through', { comp: q.through }))}: ${esc(t('close'))}">${esc(t('un.paths.through', { comp: q.through }))}${icon('x')}</a></div>` : '';
  const pg = page(rows, pathRow);
  const stops = Object.keys(STOP).filter(k => v(k));
  return `<div class="page page--wide">
    ${tabs('paths')}
    <h1 class="lede">${esc(t('un.paths.lede', { n: tn('un.pl.path', d.paths.length), k: num(gaps) }))}</h1>
    <p class="guide">${t('un.paths.guide')}</p>
    <div class="ptools">
      ${search(q.q, t('un.paths.search'))}
      ${seg('filter', [['all', t('un.all')], ['gaps', t('un.paths.f.gaps')], ['screens', t('un.paths.f.screens')], ['server', t('un.paths.f.server')]], f, t('un.paths.filter'), { dflt: 'all', cls: 'un-seg-wrap' })}
      ${through}
    </div>
    <div class="listhead">${count(pg.shown, rows.length)}<span class="un-keyline small muted">${reachKey()}</span></div>
    ${rows.length ? `<div class="panel">${layerHead()}<div class="rows">${pg.html}</div></div>${pg.more}` : `<div class="panel empty"><p class="empty__title">${t('un.paths.none')}</p><a class="btn btn--secondary" href="${href('/understand/paths')}">${t('pb.clear')}</a></div>`}
    <div class="panel" style="margin-top:12px">
      ${fold(t('un.paths.counts'), esc(t('un.paths.counts.sum', { links: num(v('links')), nodes: num(v('nodes')) })), facts([
        [t('un.paths.c.paths'), num(v('paths'))], [t('un.paths.c.links'), num(v('links'))], [t('un.paths.c.calls'), num(v('by_call'))], [t('un.paths.c.imports'), num(v('by_imports'))],
        [t('un.paths.c.gaps'), num(v('gaps'))], [t('un.paths.c.unresolved'), num(v('unresolved_steps'))]]))}
      ${stops.length ? fold(t('un.paths.why'), esc(tn('un.pl.path', gaps)), `<ul class="rows">${stops.map(k => `<li class="row" style="padding-inline:0"><span class="row__main"><span class="row__title small">${t('un.stop.' + STOP[k])}</span><span class="row__meta" style="display:block">${t('un.stop.' + STOP[k] + '.why')}</span></span><b class="num">${num(v(k))}</b></li>`).join('')}</ul>`) : ''}
      ${(d.new || []).length ? fold(t('un.paths.unreached'), esc(tn('un.pl.part', d.new.length)), `<ul class="rows">${d.new.map(u => `<li class="row" style="padding-inline:0">${code(u)}</li>`).join('')}</ul><p class="small muted">${t('un.paths.unreached.note')}</p>`) : ''}
    </div>
  </div>`;
}
screen({ id: 'S-26', path: '/understand/paths', place: 'understand', needs: NEEDS, title: () => t('un.v.paths'), render: pathsPage, loading: () => loading(t('un.paths.loading')) });

/* ---------- one path ---------- */
/** The path as seven lanes read from the top; a lane the path skips stays visible and empty; a lane with many nodes
 *  shows the first ones and how many more. */
function pathSVG(p, sel, onlyTraced, maybe) {
  const d = P(), rowH = 58, w = 760, bx = 150, h = rowH * 7 + 12, most = 3;
  const at = {};
  const lanes = LANES.map((l, i) => {
    const ids = p.columns[i] || [];
    const shown = ids.filter(id => !(onlyTraced && maybe.has(id))).slice(0, most);
    const bw = shown.length ? Math.min(300, (w - bx - (ids.length > shown.length ? 52 : 12)) / shown.length - 8) : 0;
    shown.forEach((id, k) => { at[id] = { x: bx + k * (bw + 8), y: 6 + i * rowH + 7, w: bw }; });
    const hidden = ids.length - shown.length;
    return `<g class="un-p__lane"><rect x="0" y="${6 + i * rowH}" width="${w}" height="${rowH - 6}" rx="8"/>
      <text x="16" y="${6 + i * rowH + 31}" class="un-p__head">${esc(t('un.layer.' + l))}</text>
      ${ids.length ? (hidden > 0 ? `<text x="${w - 12}" y="${6 + i * rowH + 31}" class="un-p__at">+${num(hidden)}</text>` : '') : `<text x="${bx + 12}" y="${6 + i * rowH + 31}" class="un-p__none">${esc(t('un.path.notonpath'))}</text>`}</g>`;
  }).join('');
  const links = p.steps.map(i => d.edges[i]).filter(e => at[e.from] && at[e.to] && !(onlyTraced && e.how === 'imports')).map(e => {
    const a = at[e.from], b = at[e.to];
    const x1 = a.x + a.w / 2, y1 = a.y + 36, x2 = b.x + b.w / 2, y2 = b.y;
    return `<path d="M${x1} ${y1}C${x1} ${(y1 + y2) / 2} ${x2} ${(y1 + y2) / 2} ${x2} ${y2}" class="un-p__link ${e.how === 'imports' ? 'un-p__link--maybe' : ''} ${['gap', 'trace'].includes(e.how) ? 'un-p__link--stop' : ''}"/>`;
  }).join('');
  const fit = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
  const boxes = Object.keys(at).map(id => {
    const n = nodeOf(id), b = at[id];
    if (!n) return '';
    const stop = n.kind === 'gap';
    const text = stop ? t('un.stop.' + STOP[n.reason]) : n.label;
    const tip = `${t('un.layer.' + n.lane)}: ${text}${n.path ? ' (' + where(n.path, n.line) + ')' : ''}`;
    return `<a href="${href('/understand/paths/' + enc(p.id), Object.assign({}, query(), { node: id }))}" class="un-p__node ${stop ? 'un-p__node--stop' : ''} ${sel === id ? 'is-focus' : ''}" data-tip="${esc(tip)}" aria-label="${esc(tip)}">
      <rect x="${b.x}" y="${b.y}" width="${b.w}" height="36" rx="8"/><text x="${b.x + 10}" y="${b.y + 23}" class="${stop ? '' : 'un-p__mono'}">${esc(fit(text, Math.max(8, Math.floor(b.w / 8.5))))}</text><title>${esc(tip)}</title></a>`;
  }).join('');
  return `<div class="panel un-pathmap only-desk" data-readout-root><svg viewBox="0 0 ${w} ${h}" role="group" aria-label="${esc(t('un.path.svg'))}">${lanes}${links}${boxes}</svg>
    <div class="un-key"><span class="un-key__item"><span class="un-key__line un-key__line--solid" aria-hidden="true"></span>${t('un.how.traced')}</span><span class="un-key__item"><span class="un-key__line un-key__line--possible" aria-hidden="true"></span>${t('un.how.possible')}</span><span class="un-key__item"><span class="un-key__sw un-key__sw--nm" aria-hidden="true"></span>${t('un.how.stop')}</span></div>
    <p class="small muted un-readout" data-readout aria-live="polite">${t('un.map.hint')}</p></div>`;
}
function nodeDetail(p, n) {
  const d = P();
  const part = n.component ? d.components[n.component] : null;
  const probs = (n.cards || []).map(id => model.problem(id)).filter(Boolean).slice(0, 4);
  const others = (index().on.get(n.id) || []).filter(id => id !== p.id).map(id => d.paths.find(x => x.id === id)).filter(Boolean);
  const gap = n.component ? ((data.section('gaps') || {}).gaps || []).find(g => g.component === n.component) : null;
  const stop = n.kind === 'gap';
  return `<section class="panel panel__pad un-node" aria-labelledby="node-h">
    <div class="un-itemtags"><span class="tag tag--state">${t('un.layer.' + n.lane)}</span>${part ? opTag(part.op) : ''}</div>
    <h2 class="h2" id="node-h">${stop ? esc(t('un.stop.' + STOP[n.reason])) : code(n.label)}</h2>
    ${stop ? `<p class="small ink-2">${t('un.stop.' + STOP[n.reason] + '.why')}</p>${n.detail ? `<p class="small muted">${esc(L(n.detail))}</p>` : ''}` : ''}
    ${facts([
      [t('un.path.at'), n.path ? code(where(n.path, n.line)) : `<span class="muted">${t('un.path.noat')}</span>`],
      n.fact ? [t('un.path.fact'), code(n.fact)] : null,
      [t('un.path.comp'), n.component ? `<a class="link" href="${href('/understand/components/' + enc(n.component))}">${code(n.component)}</a>` : `<span class="muted">${t('un.path.nocomp')}</span>`],
      [t('un.path.target'), part && part.target ? `${code(part.target)}${part.layer ? ` <span class="small muted">${esc(t('un.layer', { layer: part.layer }))}</span>` : ''}` : `<span class="muted">—</span>`],
      [t('un.path.problems'), probs.length ? probs.map(x => `<a class="link" href="${href('/problems/' + enc(x.id))}">${code(x.id)}</a>`).join(' ') : `<span class="muted">${t('un.none')}</span>`],
      (n.steps || []).length ? [t('un.gap.steps'), n.steps.map(s => `<a class="link" href="${href('/problems/plan/' + enc(s))}">${code(s)}</a>`).join(' ')] : null,
      [t('un.path.others'), others.length ? others.slice(0, 4).map(x => `<a class="link" href="${href('/understand/paths/' + enc(x.id))}">${code(x.title)}</a>`).join(t('list.sep')) + (others.length > 4 ? ' ' + esc(t('un.comp.andmore', { n: num(others.length - 4) })) : '') : `<span class="muted">${t('un.none')}</span>`],
    ])}
    ${(n.items || []).length ? `<div class="block-title" style="margin-top:12px">${t('un.path.unresolved')}</div><ul class="rows">${n.items.slice(0, 8).map(x => `<li class="row small" style="padding-inline:0">${code(x.callee)}<span class="row__main muted">${esc(where(x.path, x.line))}</span></li>`).join('')}</ul>` : ''}
    ${gap ? `<div class="actions" style="margin-top:12px"><a class="btn btn--secondary btn--sm" href="${href('/understand/gaps/' + enc(gap.id))}">${t('un.comp.gap')}</a></div>` : ''}
  </section>`;
}
/** A node's name in the walk: the stop's words for a gap, the code label otherwise. */
const chainLabel = id => { const n = nodeOf(id); return !n ? id : n.kind === 'gap' ? esc(t('un.stop.' + STOP[n.reason])) : code(n.label); };
/** One step of the walk as a numbered link (empty when its node is unknown). */
function chainStep(e, k, maybe, sel, r, q) {
  const n = nodeOf(e.to);
  if (!n) return '';
  return `<li class="un-chain__step ${n.kind === 'gap' ? 'un-chain__step--gap' : ''} ${maybe.has(n.id) ? 'un-chain__step--maybe' : ''}">
      <a class="un-chain__a ${sel === n.id ? 'is-open' : ''}" href="${href(r.path, Object.assign({}, q, { node: n.id }))}">
        <span class="un-chain__n num">${k + 1}</span>
        <span class="row__main"><span class="small muted">${t('un.layer.' + n.lane)}${e.how ? `${t('list.sep')}${howWord(e.how)}` : ''}</span>
          <span class="un-chain__label">${chainLabel(n.id)}</span>
          ${n.path ? `<span class="small muted" style="display:block">${code(where(n.path, n.line))}</span>` : ''}</span></a></li>`;
}
/** The walk as a table of links: from, to, how, where. */
const stepsTable = walk => `<div class="panel un-table-wrap"><table class="un-table"><thead><tr><th scope="col">${t('un.path.from')}</th><th scope="col">${t('un.path.to')}</th><th scope="col">${t('un.path.how')}</th><th scope="col">${t('un.path.at')}</th></tr></thead>
    <tbody>${walk.map(e => `<tr><td>${chainLabel(e.from)}</td><td>${chainLabel(e.to)}</td><td>${howWord(e.how)}</td><td>${e.path ? code(where(e.path, e.line)) : '—'}</td></tr>`).join('')}</tbody></table></div>`;
/** The path's tags (surface, entry place, where it stops) and its title. */
function pathHead(p, entry, stop) {
  return `<div class="un-itemtags"><span class="tag tag--state">${esc(surface(p.surface))}</span>${entry && entry.path ? code(where(entry.path, entry.line)) : ''}${stop ? `<span class="tag tag--caution">${icon('warn')}${t('un.stop.' + STOP[stop])}</span>` : ''}</div>
    <h1 class="lede un-lede-sm">${code(p.title)}${p.handler ? ` <span class="muted">${esc(p.handler)}</span>` : ''}</h1>`;
}
// the "only what the trace confirms" toggle
const tracedToggle = (r, q, onlyTraced) => `<a class="btn btn--secondary btn--sm ${onlyTraced ? 'is-on' : ''}" ${onlyTraced ? 'aria-current="true"' : ''} href="${href(r.path, Object.assign({}, q, { confirmed: onlyTraced ? null : '1' }))}">${icon('check', 'icon--sm')}${t('un.path.confirmed')}</a>`;
// the notes under the path: links not drawn, and the cap on what is drawn
const pathNotes = p => `${p.unresolved ? `<p class="small muted" style="margin-top:12px">${esc(tn('un.pl.notdrawn', p.unresolved))}</p>` : ''}
    ${p.capped ? `<p class="small muted">${esc(t('un.path.capped', { n: num(p.capped) }))}</p>` : ''}`;
function pathPage(ctx) {
  const d = P();
  if (!d) return notMeasured('paths', 'paths');
  const p = d.paths.find(x => x.id === ctx.params.id);
  if (!p) return notFound(ctx.params.id, '/understand/paths', t('un.v.paths'));
  const q = ctx.query, view = q.view === 'steps' ? 'steps' : 'layers', onlyTraced = q.confirmed === '1';
  const maybe = possible(p);
  const walk = p.steps.map(i => d.edges[i]).filter(e => !(onlyTraced && e.how === 'imports'));
  const sel = q.node && nodeOf(q.node) ? q.node : null;
  const r = parseHash();
  const entry = nodeOf(p.entry);
  const seq = `<ol class="un-chain">${[{ to: p.entry, how: null }].concat(walk).map((e, k) => chainStep(e, k, maybe, sel, r, q)).join('')}</ol>`;
  const steps = stepsTable(walk);
  const stop = stopOf(p);
  return `<div class="page page--wide">
    ${back('/understand/paths', t('un.v.paths'))}
    ${pathHead(p, entry, stop)}
    <p class="guide">${esc(t('un.path.guide', { entry: p.title }))}</p>
    <div class="ptools">
      <div class="un-tools">${seg('view', [['layers', t('un.path.layers')], ['steps', t('un.path.steps')]], view, t('un.path.view'), { dflt: 'layers', cls: 'un-seg2' })}
      ${tracedToggle(r, q, onlyTraced)}</div>
    </div>
    <div class="un-pathgrid">
      <div class="un-pathgrid__main">
        ${view === 'layers' ? `${pathSVG(p, sel, onlyTraced, maybe)}<div class="only-phone">${seq}</div>` : steps}
        <p class="small muted" style="margin-top:8px">${t('un.path.order')}</p>
      </div>
      <div class="un-pathgrid__side">${sel ? nodeDetail(p, nodeOf(sel)) : `<div class="panel panel__pad small muted">${t('un.path.pick')}</div>`}</div>
    </div>
    ${pathNotes(p)}
  </div>`;
}
screen({ id: 'S-27', path: '/understand/paths/:id', place: 'understand', needs: NEEDS, title: ctx => ctx.params.id + ' - ' + t('un.v.paths'), render: pathPage, after: readout, loading: () => loading(t('un.paths.loading')) });
