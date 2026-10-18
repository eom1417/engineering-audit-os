// S-28 the functions explorer (SYS-05, SRC-03) and S-29 one function and its calls (SYS-06), on functions.json, the
// largest section: read only when these screens open (never by the search box), indexed once per read, shown 50 at a
// time. Every number is the exporter's (lizard's complexity and lines, the traced calls), with its source.
import { t, tn, L, num, esc, icon, code, href, rich, screen, data, model, normalize, parseHash, selection } from 'eaos';
import { tabs, seg, search, page, count, fold, facts, prow, enc, back, loading, notMeasured, empty, notFound, readout, where, missingRow } from '../understand-kit/kit.js';

const NEEDS = ['functions', 'cards', 'coverage'];
const COMPLEX = 15, WATCH = 10; // lizard's warning line (eaos/engines/lizard.py), half of it to watch
const F = () => data.section('functions');
const cx = f => (f.complexity ? f.complexity.value : null);
const lines = f => (f.lines ? f.lines.value : null);

let idx = null;
/** The functions by id and their search text, normalised once per read of the section. */
function index() {
  const d = F();
  if (idx && idx.d === d) return idx;
  const byId = new Map(d.functions.map(f => [f.id, f]));
  const text = new Map(d.functions.map(f => [f.id, normalize.tokenize(normalize.normalize([f.name, f.module, f.kind, f.signature || '',
    ...(f.reads || []).map(x => x.name), ...(f.writes || []).map(x => x.name)].join(' '))).flatMap(normalize.terms).join(' ')]));
  idx = { d, byId, text };
  return idx;
}
const fnOf = id => index().byId.get(id) || null;
const risk = (a, b) => (cx(b) ?? -1) - (cx(a) ?? -1) || (b.cards || []).length - (a.cards || []).length || b.callers.length - a.callers.length;
const ORDER = { complex: risk, called: (a, b) => b.callers.length - a.callers.length || risk(a, b), long: (a, b) => (lines(b) ?? -1) - (lines(a) ?? -1), name: (a, b) => a.name.localeCompare(b.name) || a.module.localeCompare(b.module) };
const shortName = n => n.split(/[.:]+/).pop() || n;

function cxTag(f) {
  const c = cx(f);
  return c == null ? '' : c > COMPLEX ? `<span class="tag tag--caution">${esc(t('un.fn.cx.warn', { n: num(c) }))}</span>` : c >= WATCH ? `<span class="tag tag--state">${esc(t('un.fn.cx.watch', { n: num(c) }))}</span>` : '';
}
const fnLink = id => href('/understand/functions/' + enc(id));
function fnRow(f) {
  return `<a class="row un-fnrow" href="${fnLink(f.id)}">
    <span class="row__main"><span class="un-gaprow__top">${code(f.name)}${cxTag(f)}${(f.cards || []).length ? `<span class="tag tag--you">${esc(tn('pl.problem', f.cards.length))}</span>` : ''}</span>
      <span class="row__meta" style="display:block">${code(f.module)}${t('list.sep')}${t('un.fnkind.' + f.kind)}</span></span>
    <span class="row__end un-fnnums"><span>${lines(f) == null ? '' : esc(tn('pl.line', lines(f)))}</span><span>${esc(t('un.fn.calledby', { n: num(f.callers.length) }))}</span></span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
}

function fnsPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  const d = F();
  if (!d) return notMeasured('functions', 'functions');
  const q = ctx.query, sort = ORDER[q.sort] ? q.sort : 'complex', show = q.show || 'all';
  const { text } = index();
  const words = normalize.tokenize(normalize.normalize(q.q || ''));
  let rows = d.functions.filter(f => {
    if (show === 'problems' && !(f.cards || []).length) return false;
    if (show === 'data' && !(f.reads || []).length && !(f.writes || []).length) return false;
    if (show === 'orphan' && (f.callers.length || f.kind === 'component' || f.exported)) return false;
    if (q.kind && f.kind !== q.kind) return false;
    if (q.module && f.module !== q.module) return false;
    return !words.length || words.every(w => normalize.terms(w).some(x => text.get(f.id).includes(x)));
  });
  rows = rows.slice().sort(ORDER[sort]);
  const pg = page(rows, fnRow);
  const r = parseHash();
  const c = d.counts || {}, v = k => (c[k] ? c[k].value : null);
  const shortcut = (label, extra, on) => `<a class="btn btn--secondary btn--sm ${on ? 'is-on' : ''}" href="${href(r.path, Object.assign({ q: q.q }, extra))}" ${on ? 'aria-current="true"' : ''}>${label}</a>`;
  const kinds = [...new Set(d.functions.map(f => f.kind))];
  return `<div class="page page--wide">
    ${tabs('functions')}
    <h1 class="lede">${esc(t('un.fns.lede', { n: tn('un.pl.fn', v('functions') || d.functions.length), files: tn('un.pl.file2', v('modules') || d.modules.length) }))}</h1>
    <p class="guide">${esc(t('un.fns.guide.v', { calls: num(v('calls')), reads: num(v('reads')), writes: num(v('writes')) }))}</p>
    <div class="actions un-shortcuts">${shortcut(t('un.fns.s.complex'), {}, sort === 'complex' && show === 'all' && !q.kind)}${shortcut(t('un.fns.s.problems'), { show: 'problems' }, show === 'problems')}${shortcut(t('un.fns.s.called'), { sort: 'called' }, sort === 'called' && show === 'all')}</div>
    <div class="ptools">
      ${search(q.q, t('un.fns.search'))}
      <div class="un-orderline"><span class="small muted">${t('un.order')}</span>${seg('sort', [['complex', t('un.fns.o.complex')], ['called', t('un.fns.o.called')], ['long', t('un.fns.o.long')], ['name', t('un.fns.o.name')]], sort, t('un.order'), { dflt: 'complex', cls: 'un-seg-wrap' })}</div>
      <div class="un-orderline"><span class="small muted">${t('un.fns.show')}</span>${seg('show', [['all', t('un.all')], ['problems', t('un.fns.f.problems')], ['data', t('un.fns.f.data')], ['orphan', t('un.fns.f.orphan')]], show, t('un.fns.show'), { dflt: 'all', cls: 'un-seg-wrap' })}</div>
      ${kinds.length > 1 ? `<div class="un-orderline"><span class="small muted">${t('un.fns.kind')}</span>${seg('kind', [['', t('un.all')]].concat(kinds.map(k => [k, t('un.fnkinds.' + k)])), q.kind || '', t('un.fns.kind'), { dflt: '', cls: 'un-seg-wrap' })}</div>` : ''}
      ${q.module ? `<div class="fchips"><a class="fchip" href="${href(r.path, Object.assign({}, q, { module: null }))}">${code(q.module)}${icon('x')}</a></div>` : ''}
    </div>
    <div class="listhead">${count(pg.shown, rows.length)}</div>
    ${rows.length ? `<div class="panel rows">${pg.html}</div>${pg.more}` : `<div class="panel empty"><p class="empty__title">${t('un.fns.none')}</p><a class="btn btn--secondary" href="${href('/understand/functions')}">${t('pb.clear')}</a></div>`}
    <div class="panel section">${fold(t('un.fns.cov'), esc(t('un.fns.cov.sum')), `<ul class="rows">${(d.languages || []).map(l => `<li class="row" style="padding-inline:0"><span class="row__main"><span class="row__title small">${esc(l.id)}</span><span class="row__meta" style="display:block">${t('un.fns.cov.' + l.state)}</span></span><b class="num">${l.functions && l.functions.value != null ? num(l.functions.value) : '—'}</b></li>`).join('')}</ul>${(d.missing || []).map(missingRow).join('')}`)}</div>
  </div>`;
}
screen({ id: 'S-28', path: '/understand/functions', place: 'understand', needs: NEEDS, title: () => t('un.v.functions'), render: fnsPage,
  loading: () => `<div class="page page--wide" aria-busy="true">${tabs('functions')}<h1 class="lede">${t('un.fns.loading')}</h1><p class="guide">${t('un.fns.loading.guide')}</p></div>` });

/* ---------- one function, two steps of calls each way (SYS-06) ---------- */
const PER = 6;
function graphCols(f) {
  const pick = ids => ids.map(fnOf).filter(x => x && x.id !== f.id).sort(risk);
  const callers = pick(f.callers), callees = pick(f.callees);
  const near = new Set([f.id, ...f.callers, ...f.callees]);
  const far = (from, side) => { const out = new Map(); from.slice(0, PER).forEach(x => x[side].forEach(id => { if (!near.has(id) && !out.has(id) && fnOf(id)) out.set(id, fnOf(id)); })); return [...out.values()].sort(risk); };
  return [far(callers, 'callers'), callers, [f], callees, far(callees, 'callees')];
}
function callGraphSVG(f, cols) {
  const colW = 200, nodeW = 176, rowH = 40;
  const w = colW * 5, rows = Math.max(1, ...cols.map(c => Math.min(PER, c.length) + (c.length > PER ? 1 : 0)));
  const h = rows * rowH + 50;
  const pos = {};
  cols.forEach((c, ci) => { const shown = c.slice(0, PER), total = shown.length + (c.length > PER ? 1 : 0); shown.forEach((x, i) => { pos[ci + ':' + x.id] = { x: ci * colW + 12, y: 44 + i * rowH + (rows - total) * rowH / 2 }; }); });
  const link = (a, b) => `<path class="un-cg__link" d="M${a.x + nodeW} ${a.y + 14}C${a.x + nodeW + 14} ${a.y + 14} ${b.x - 14} ${b.y + 14} ${b.x} ${b.y + 14}"/>`;
  const links = [];
  cols[1].slice(0, PER).forEach(x => { const a = pos['1:' + x.id], b = pos['2:' + f.id]; links.push(link(a, b)); x.callers.forEach(id => { const z = pos['0:' + id]; if (z) links.push(link(z, a)); }); });
  cols[3].slice(0, PER).forEach(x => { const a = pos['2:' + f.id], b = pos['3:' + x.id]; links.push(link(a, b)); x.callees.forEach(id => { const z = pos['4:' + id]; if (z) links.push(link(b, z)); }); });
  const heads = ['un.fn.c0', 'un.fn.c1', 'un.fn.c2', 'un.fn.c3', 'un.fn.c4'].map((k, i) => `<text x="${i * colW + 12}" y="20" class="un-cg__head">${esc(t(k))}</text>`).join('');
  const nodes = cols.map((c, ci) => {
    const shown = c.slice(0, PER);
    const out = shown.map(x => {
      const p = pos[ci + ':' + x.id], nm = shortName(x.name);
      const lab = nm.length > 21 ? nm.slice(0, 20) + '…' : nm;
      const tip = `${x.name} (${x.module})`;
      const body = `<rect x="${p.x}" y="${p.y}" width="${nodeW}" height="28" rx="6"/><text x="${p.x + 10}" y="${p.y + 19}">${esc(lab)}</text><title>${esc(tip)}</title>`;
      return ci !== 2 ? `<a href="${fnLink(x.id)}" class="un-cg__node" data-tip="${esc(tip)}" aria-label="${esc(tip)}">${body}</a>` : `<g class="un-cg__node un-cg__node--me" data-tip="${esc(tip)}">${body}</g>`;
    }).join('');
    const more = c.length > PER ? `<text x="${ci * colW + 22}" y="${44 + shown.length * rowH + (rows - shown.length - 1) * rowH / 2 + 18}" class="un-cg__more">${esc(t('un.comp.andmore', { n: num(c.length - PER) }))}</text>` : '';
    const none = !c.length ? `<text x="${ci * colW + 12}" y="${44 + (rows - 1) * rowH / 2 + 18}" class="un-cg__more">${esc(t('un.fn.nocalls'))}</text>` : '';
    return out + more + none;
  }).join('');
  return `<div class="panel un-callgraph only-desk" data-readout-root><svg viewBox="0 0 ${w} ${h}" role="group" aria-label="${esc(t('un.fn.svg'))}">${heads}${links.join('')}${nodes}</svg>
    <p class="small muted un-readout" data-readout aria-live="polite">${t('un.fn.svg.hint')}</p></div>`;
}
function callList(title, first, side) {
  if (!first.length) return `<section class="psec"><h3 class="h2">${title}</h3><p class="small muted">${t('un.fn.nocalls')}</p></section>`;
  return `<section class="psec"><h3 class="h2">${title}</h3><ul class="un-calls">${first.slice(0, PER).map(x => {
    const next = x[side].map(fnOf).filter(Boolean);
    return `<li><a class="link" href="${fnLink(x.id)}">${code(shortName(x.name))}</a> <span class="small muted">${code(x.module)}</span>
      ${next.length ? `<ul>${next.slice(0, 3).map(n2 => `<li class="small"><a class="link" href="${fnLink(n2.id)}">${code(shortName(n2.name))}</a> <span class="muted">${code(n2.module)}</span></li>`).join('')}${next.length > 3 ? `<li class="small muted">${esc(t('un.comp.andmore', { n: num(next.length - 3) }))}</li>` : ''}</ul>` : ''}</li>`;
  }).join('')}${first.length > PER ? `<li class="small muted">${esc(t('un.comp.andmore', { n: num(first.length - PER) }))}</li>` : ''}</ul></section>`;
}
const idList = ids => `<ul class="rows">${ids.slice(0, 200).map(id => `<li class="row" style="padding-inline:0;min-height:40px">${fnOf(id) ? `<a class="link" href="${fnLink(id)}">${code(id)}</a>` : code(id)}</li>`).join('')}</ul>${ids.length > 200 ? `<p class="small muted">${esc(t('un.comp.andmore', { n: num(ids.length - 200) }))}</p>` : ''}`;

function fnPage(ctx) {
  if (!F()) return notMeasured('functions', 'functions');
  const f = fnOf(ctx.params.id);
  if (!f) return notFound(ctx.params.id.split('#').pop(), '/understand/functions', t('un.v.functions'));
  const cols = graphCols(f);
  const c = cx(f);
  const sumKey = c == null ? 'un.fn.sum.nm' : c > COMPLEX ? 'un.fn.sum.warn' : c >= WATCH ? 'un.fn.sum.watch' : 'un.fn.sum';
  const probs = (f.cards || []).map(id => model.problem(id)).filter(Boolean);
  const touches = [...(f.reads || []).map(x => [x, 'r']), ...(f.writes || []).map(x => [x, 'w'])];
  const comp = selection.componentOf({ paths: [f.module] });
  return `<div class="page page--wide">
    ${back('/understand/functions', t('un.v.functions'))}
    <div class="un-itemtags"><span class="tag tag--state">${t('un.fnkind.' + f.kind)}</span>${cxTag(f)}${f.language ? `<span class="tag tag--state">${esc(f.language)}</span>` : ''}</div>
    <h1 class="lede un-lede-sm un-title-code">${code(f.name)}</h1>
    <p class="guide">${esc(t(sumKey, { kind: t('un.fnkinds.' + f.kind), file: f.module, lines: tn('pl.line', lines(f) || 0), by: num(f.callers.length), calls: num(f.callees.length), cx: num(c) }))}${f.callers.length ? '' : ' ' + t('un.fn.nocaller')}</p>
    ${f.summary ? `<p>${rich(L(f.summary))}</p>` : ''}
    <div class="actions">
      ${probs.length ? `<a class="btn btn--primary" href="${href('/problems/' + enc(probs[0].id))}">${esc(t('un.fn.problem', { id: probs[0].id }))}</a>` : ''}
      <a class="btn btn--quiet" href="${href('/understand/functions', { module: f.module })}">${t('un.fn.file')}</a>
      <a class="btn btn--quiet" href="${href('/understand/components', { focus: comp })}">${icon('map', 'icon--sm')}${t('un.fn.map')}</a>
    </div>
    <section class="section"><div class="section-head"><h2>${t('un.fn.graph')}</h2></div>
      ${callGraphSVG(f, cols)}
      <div class="un-callcols">${callList(t('un.fn.whocalls'), cols[1], 'callers')}${callList(t('un.fn.whatcalls'), cols[3], 'callees')}</div></section>
    <section class="section"><h2 class="h2" style="margin-bottom:12px">${t('un.fn.facts')}</h2>
      <div class="panel panel__pad">${facts([
        [t('un.fn.where'), code(where(f.module, f.line) + (f.end_line ? '-' + f.end_line : ''))],
        f.signature ? [t('un.fn.sig'), code(f.signature)] : null,
        [t('un.fn.cx'), c == null ? `<span class="muted">${t('nm')}</span>` : `${num(c)} <span class="small muted">${esc(f.complexity.src)}</span>`],
        [t('un.fn.lines'), lines(f) == null ? `<span class="muted">${t('nm')}</span>` : `${num(lines(f))} <span class="small muted">${esc(f.lines.src)}</span>`],
        [t('un.fn.exported'), f.exported == null ? `<span class="muted">${t('nm')}</span>` : t(f.exported ? 'un.fn.public' : 'un.fn.internal')],
      ])}</div></section>
    <section class="section"><h2 class="h2">${t('un.fn.data')}</h2>${touches.length ? `<ul class="rows" style="margin-top:8px">${touches.map(([x, rw]) => `<li class="row" style="padding-inline:0;min-height:44px"><span class="tag tag--state">${t('un.data.' + x.kind)}</span><span class="row__main">${code(x.name)}</span><span class="small muted">${t('un.rw.' + rw)}</span></li>`).join('')}</ul>` : `<p class="small muted" style="margin-top:8px">${t('un.fn.nodata')}</p>`}</section>
    <section class="section"><h2 class="h2">${t('un.fn.problems')}</h2>${probs.length ? `<div class="panel rows" style="margin-top:8px">${probs.map(p => prow(p)).join('')}</div>` : `<p class="small muted" style="margin-top:8px">${t('un.fn.noproblems')}</p>`}</section>
    <div class="panel section">
      ${fold(t('un.fn.allcallers'), esc(tn('un.pl.fn', f.callers.length)), f.callers.length ? idList(f.callers) : `<p class="small muted">${t('un.fn.nocaller')}</p>`)}
      ${fold(t('un.fn.allcallees'), esc(tn('un.pl.fn', f.callees.length)), f.callees.length ? idList(f.callees) : `<p class="small muted">${t('un.fn.nocalls')}</p>`)}
    </div>
  </div>`;
}
screen({ id: 'S-29', path: '/understand/functions/:id', place: 'understand', needs: NEEDS, title: ctx => ctx.params.id.split('#').pop() + ' - ' + t('un.v.functions'), render: fnPage, after: readout,
  loading: () => loading(t('un.fns.loading')) });
