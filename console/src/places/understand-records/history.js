// S-43 checks over time (HIS-01..05), S-44 one past check (HIS-06) and S-45 compare two checks (HIS-07), on
// history.json: every check the ledger recorded (null where it did not record a value, said so, never 0), the fixes
// taken in after each check and each merge as a step line, the score's trend once two checks have one, open problems
// by severity, the events, and the cards closed or found new between two checks.
import { t, tn, num, esc, icon, code, href, rich, fmtWhen, exactTime, screen, act, setQuery, data, sev, L } from 'eaos';
import { tabs, back, facts, fold, loading, notMeasured, emptyView, notFound, rtl, missingRow, enc, readout } from '../understand-kit/kit.js';

const NEEDS = ['history', 'health', 'coverage'];
const SEVS = ['critical', 'high', 'medium', 'low', 'info'];
const H = () => data.section('history');
const known = s => SEVS.every(k => typeof s.open[k] === 'number');
const openTotal = s => (typeof s.open_total === 'number' ? s.open_total : known(s) ? SEVS.reduce((n, k) => n + s.open[k], 0) : null);
const score = s => (s.score == null ? null : Math.round(s.score * 100));
const short = c => (c ? c.slice(0, 7) : '—');
const checkLink = s => href('/understand/history/' + enc(s.id));
const EVENT_ICON = { scan: 'history', merge: 'branch', batch: 'tool', decision: 'waiting', release: 'layers' };

/** The fixes taken in as a step line over every recorded point (after a check, after a merge); a reset is marked. */
function fixesChart(points) {
  const w = 720, h = 230, top = 16, bot = 40, R = rtl();
  const l = R ? 16 : 44, r = R ? 44 : 16;
  const x = i => (points.length < 2 ? (l + w - r) / 2 : R ? (w - r) - i * ((w - l - r) / (points.length - 1)) : l + i * ((w - l - r) / (points.length - 1)));
  const y = v => top + (1 - v) * (h - top - bot);
  const share = p => (p.total ? p.closed / p.total : 0);
  let d = '';
  points.forEach((p, i) => { d += i === 0 ? `M${x(i)} ${y(share(p))}` : `H${x(i)}V${y(share(p))}`; });
  const grid = [0, 0.5, 1].map(v => `<line x1="${l}" x2="${w - r}" y1="${y(v)}" y2="${y(v)}" class="un-ch__grid"/><text x="${R ? w - r + 8 : l - 8}" y="${y(v) + 4}" class="un-ch__ax ${R ? 'un-ch__ax--yr' : 'un-ch__ax--y'}">${v * 100}%</text>`).join('');
  const marks = points.map((p, i) => {
    const tip = `${fmtWhen(p.at)}: ${t('un.his.closedof', { k: num(p.closed), n: num(p.total), p: Math.round(share(p) * 100) + '%' })}`;
    return `<circle cx="${x(i)}" cy="${y(share(p))}" r="5" class="un-ch__pt" tabindex="0" data-tip="${esc(tip)}"><title>${esc(tip)}</title></circle>`;
  }).join('');
  // a reset is marked by its line; its word is written once, at the first, where words do not crowd
  const resets = points.map((p, i) => (i && p.total < points[i - 1].total ? i : -1)).filter(i => i > 0).map((i, k) => `<line x1="${x(i)}" x2="${x(i)}" y1="${top}" y2="${h - bot}" class="un-ch__reset"><title>${esc(t('un.his.reset'))}</title></line>${k ? '' : `<text x="${x(i) + (R ? -4 : 4)}" y="${top + 10}" class="un-ch__resetl" text-anchor="${R ? 'end' : 'start'}">${esc(t('un.his.reset'))}</text>`}`).join('');
  return `<div class="panel un-chart" data-readout-root><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(t('un.his.fixes.label'))}">${grid}${resets}<path d="${d}" class="un-ch__line"/>${marks}
    <text x="${(l + w - r) / 2}" y="${h - 8}" class="un-ch__ax">${esc(t('un.his.xaxis'))}</text></svg>
    <p class="small muted un-readout" data-readout aria-live="polite">${t('un.his.chart.hint')}</p></div>`;
}
function sevBar(open) {
  const total = SEVS.reduce((s, k) => s + (open[k] || 0), 0);
  return `<div class="sevbar" role="img" aria-label="${esc(SEVS.map(k => `${t('sev.' + k)} ${open[k] || 0}`).join(', '))}">${SEVS.filter(k => open[k] > 0).map(k => `<span class="s-${k}" style="flex:${open[k]}"></span>`).join('')}</div>
    <div class="legend">${SEVS.map(k => `<a href="${href('/problems', { sev: k })}" class="${open[k] ? '' : 'zero'}">${sev(k, false)}<span>${t('sev.' + k)}</span> <b>${num(open[k] || 0)}</b></a>`).join('')}</div><span class="sr-only">${num(total)}</span>`;
}
const eventRow = e => `<li class="row" style="padding-inline:0;align-items:flex-start">${icon(EVENT_ICON[e.kind] || 'history', 'muted')}
  <span class="row__main"><span class="row__title small">${esc(t('un.ev.' + e.kind, { n: num(e.count) }))}</span><span class="row__meta" style="display:block">${esc(fmtWhen(e.at))}${e.ref ? `${t('list.sep')}${code(e.ref.length === 40 ? short(e.ref) : e.ref)}` : ''}</span></span></li>`;
/** The trend sentence (HIS-02): from the last two checks with a score. */
function trend(scored) {
  if (scored.length < 2) return t('un.his.trend.one');
  const a = score(scored[scored.length - 2]), b = score(scored[scored.length - 1]);
  return b === a ? t('un.his.trend.same') : t(b > a ? 'un.his.trend.up' : 'un.his.trend.down', { n: num(Math.abs(b - a)) });
}

/** The four figures over the history: checks, the last score, open problems, fixes taken in. */
const tiles = (scans, last) => `<div class="un-diffs section" role="list" style="margin-top:24px">
      <div class="un-diff" role="listitem"><b class="num">${num(scans.length)}</b><span>${t('un.his.t.checks')}</span></div>
      <div class="un-diff" role="listitem"><b class="num">${last.score != null ? num(score(last)) : '—'}</b><span>${t('un.his.t.score')}</span></div>
      <div class="un-diff" role="listitem"><b class="num">${openTotal(last) != null ? num(openTotal(last)) : '—'}</b><span>${t('un.his.t.open')}</span></div>
      <div class="un-diff" role="listitem"><b class="num">${num(last.closed)}</b><span>${esc(t('un.his.t.closed', { n: num(last.total) }))}</span></div>
    </div>`;
/** The fixes chart's points: the recorded progress, else one point per check. */
const progressOf = (h, scans) => ((h.progress || []).length ? h.progress : scans.map(s => ({ at: s.at, closed: s.closed || 0, total: s.total || 0, event: s.event })));

function historyPage(ctx) {
  if (ctx.state === 'empty') return emptyView('history');
  const h = H();
  if (!h || !h.scans.length) return notMeasured('history', 'history');
  const scans = h.scans, last = scans[scans.length - 1];
  const scored = scans.filter(s => s.score != null);
  const knownSev = scans.filter(known);
  const row = (s, i) => `<a class="row ${s === last ? 'row--latest' : ''}" href="${checkLink(s)}"><span class="un-num num">${i + 1}</span>
    <span class="row__main"><span class="row__title">${esc(fmtWhen(s.at))}${s === last ? ` <span class="tag tag--state">${t('un.his.latest')}</span>` : ''}</span>
      <span class="row__meta" style="display:block">${code(short(s.commit))}${t('list.sep')}${t('un.his.kind.' + (i ? 'new' : 'first'))}${t('list.sep')}${s.score != null ? esc(t('un.his.score', { s: num(score(s)) })) : t('un.his.noscore')}</span></span>
    <span class="row__end small num">${esc(t('un.his.closedof.s', { k: num(s.closed), n: num(s.total) }))}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
  const points = progressOf(h, scans);
  const share = last.total ? Math.round((last.closed / last.total) * 100) + '%' : '—';
  return `<div class="page page--wide">
    ${tabs('history')}
    <h1 class="lede">${esc(t('un.his.lede.v', { n: tn('un.pl.check', scans.length) }))}</h1>
    <p class="guide">${t(scans.length < 2 ? 'un.his.guide.one' : 'un.his.guide')}</p>
    ${scans.length > 1 ? `<div class="actions"><a class="btn btn--primary" href="${href('/understand/history/compare')}">${t('un.his.compare')}</a></div>` : ''}
    ${tiles(scans, last)}
    <section class="section" aria-labelledby="fx-h"><div class="section-head"><h2 id="fx-h">${t('un.his.fixes')}</h2></div>
      <p class="small ink-2" style="margin-bottom:12px">${esc(last.closed ? t('un.his.fixes.sum', { k: num(last.closed), n: num(last.total), p: share }) : t('un.his.fixes.none'))}</p>${fixesChart(points)}</section>
    <section class="section" aria-labelledby="sc-h"><div class="section-head"><h2 id="sc-h">${t('un.his.trend')}</h2></div><p class="ink-2">${esc(trend(scored))}</p></section>
    <section class="section" aria-labelledby="sv-h"><div class="section-head"><h2 id="sv-h">${t('un.his.bysev')}</h2></div>
      <div class="panel panel__pad"><p class="small ink-2" style="margin-bottom:12px">${t(knownSev.length < 2 ? 'un.his.bysev.one' : 'un.his.bysev.now')}</p>${known(last) ? sevBar(last.open) : `<p class="small muted">${t('un.his.nosev')}</p>`}</div></section>
    <section class="section" aria-labelledby="ck-h"><div class="section-head"><h2 id="ck-h">${t('un.his.all')}</h2><span class="small muted">${t('un.his.oldest')}</span></div>
      <div class="panel rows">${scans.map(row).join('')}</div></section>
    <div class="panel section">${fold(t('un.his.events'), esc(tn('un.pl.event', h.events.length)), `<ul class="rows">${h.events.slice().reverse().map(eventRow).join('')}</ul>`, { id: 'events' })}</div>
    ${(h.missing || []).map(missingRow).join('')}
  </div>`;
}
screen({ id: 'S-43', path: '/understand/history', place: 'understand', needs: NEEDS, title: () => t('un.v.history'), render: historyPage, loading: () => loading(t('un.his.loading')),
  after: readout });

/* ---------- S-44 one past check ---------- */
/** The check's facts; `nr` where the ledger did not record a value. */
const checkFacts = (c, nr) => facts([
      [t('un.his.f.when'), esc(exactTime(c.at))], [t('un.his.f.commit'), code(c.commit || '—')], [t('un.his.f.branch'), c.branch ? code(c.branch) : nr],
      [t('un.his.f.score'), c.score != null ? num(score(c)) : nr], [t('un.his.f.open'), openTotal(c) != null ? num(openTotal(c)) : nr],
      [t('un.his.f.closed'), esc(t('un.his.closedof.s', { k: num(c.closed), n: num(c.total) }))],
      [t('un.his.f.new'), c.added != null ? num(c.added) : nr], [t('un.his.f.gone'), c.resolved != null ? num(c.resolved) : nr],
    ]);
// the links to the check before and after (an empty cell holds the place of a missing previous one)
const prevLink = prev => (prev ? `<a class="row panel" href="${checkLink(prev)}">${icon('back', 'icon--dir muted')}<span class="row__main"><span class="small muted">${t('un.his.prev')}</span><span class="row__title" style="display:block">${esc(fmtWhen(prev.at))}</span></span></a>` : '<span></span>');
const nextLink = next => (next ? `<a class="row panel" href="${checkLink(next)}"><span class="row__main"><span class="small muted">${t('un.his.next')}</span><span class="row__title" style="display:block">${esc(fmtWhen(next.at))}</span></span>${icon('chev', 'icon--dir muted')}</a>` : '');
function checkPage(ctx) {
  const h = H();
  if (!h) return notMeasured('history', 'history');
  const scans = h.scans, i = scans.findIndex(x => x.id === ctx.params.check);
  if (i < 0) return notFound(ctx.params.check, '/understand/history', t('un.v.history'));
  const c = scans[i], prev = scans[i - 1], next = scans[i + 1];
  const evs = h.events.filter(e => e.at >= c.at && (!next || e.at < next.at) && !(e.kind === 'scan' && e.at === c.at));
  const nr = `<span class="muted">${t('un.his.notrec')}</span>`;
  const reset = prev && c.total < prev.total;
  return `<div class="page">
    ${back('/understand/history', t('un.v.history'))}
    <div class="un-itemtags">${code(short(c.commit))}<span class="tag tag--state">${t('un.his.kind.' + (i ? 'new' : 'first'))}</span>${reset ? `<span class="tag tag--caution">${t('un.his.reset')}</span>` : ''}</div>
    <h1 class="lede un-lede-sm">${esc(t('un.his.check.lede', { when: fmtWhen(c.at) }))}</h1>
    <p class="guide">${esc(openTotal(c) == null ? t('un.his.check.guide.old', { k: num(c.closed), n: num(c.total) }) : t('un.his.check.guide', { o: num(openTotal(c)), k: num(c.closed), n: num(c.total) }))}</p>
    <div class="actions">${prev ? `<a class="btn btn--primary" href="${href('/understand/history/compare', { a: prev.id, b: c.id })}">${t('un.his.compareprev')}</a>` : ''}</div>
    <section class="section"><div class="panel panel__pad">${checkFacts(c, nr)}</div></section>
    <section class="section"><h2 class="h2" style="margin-bottom:12px">${t('un.his.bysev')}</h2><div class="panel panel__pad">${known(c) ? sevBar(c.open) : `<p class="small ink-2">${t('un.his.nosev')}</p>`}</div></section>
    <section class="section"><h2 class="h2" style="margin-bottom:8px">${t(next ? 'un.his.until' : 'un.his.since')}</h2>
      ${evs.length ? `<ul class="rows">${evs.map(eventRow).join('')}</ul>` : `<p class="small muted">${t('un.his.noevents')}</p>`}</section>
    <nav class="un-doc__pn section" aria-label="${esc(t('un.v.history'))}">
      ${prevLink(prev)}
      ${nextLink(next)}
    </nav>
  </div>`;
}

/* ---------- S-45 compare two checks ---------- */
/** How a value moved between two checks; `better` is the way that is good ('up', 'down', or null for neither). */
function moved(va, vb, better) {
  const up = vb > va, good = better === 'up' ? up : better === 'down' ? !up : null;
  const diff = (up ? '+' : '−') + num(Math.abs(vb - va));
  return good == null ? `<span class="state">${esc(diff)}</span>` : `<span class="state ${good ? 'ok-ic' : 'danger-ic'}">${icon(good ? 'check' : 'warn', 'icon--sm')}<bdi class="num">${esc(diff)}</bdi> ${t(good ? 'un.cmp.better' : 'un.cmp.worse')}</span>`;
}
/** The change cell: not comparable, the same, or how it moved. */
function change(va, vb, better) {
  if (va == null || vb == null) return `<span class="muted">${t('un.cmp.na')}</span>`;
  if (va === vb) return `<span class="state">${icon('dash', 'icon--sm')}${t('un.cmp.same')}</span>`;
  return moved(va, vb, better);
}
/** The two checks compared (indices, earlier first): those asked for, else the last two. */
function pair(scans, q) {
  let a = scans.findIndex(x => x.id === q.a), b = scans.findIndex(x => x.id === q.b);
  if (a < 0) a = scans.length - 2;
  if (b < 0) b = scans.length - 1;
  if (a > b) [a, b] = [b, a];
  return [a, b];
}
// the line under a card list cut at 50
const andMore = list => (list.length > 50 ? `<p class="small muted">${esc(t('un.comp.andmore', { n: num(list.length - 50) }))}</p>` : '');
function comparePage(ctx) {
  const h = H();
  if (!h) return notMeasured('history', 'history');
  const scans = h.scans, q = ctx.query;
  if (scans.length < 2) return `<div class="page">${back('/understand/history', t('un.v.history'))}<h1 class="lede un-lede-sm">${t('un.cmp.title')}</h1><p class="guide">${t('un.his.guide.one')}</p></div>`;
  const [a, b] = pair(scans, q);
  const A = scans[a], B = scans[b], same = a === b;
  const opt = (sel, name) => `<label class="un-pick"><span class="block-title">${t('un.cmp.' + name)}</span><select class="un-select" data-change="un-cmp" data-side="${name === 'earlier' ? 'a' : 'b'}" data-fk="cmp-${name}">
    ${scans.map((c, i) => `<option value="${esc(c.id)}" ${i === sel ? 'selected' : ''}>${esc(`${i + 1}. ${fmtWhen(c.at)} (${short(c.commit)})`)}</option>`).join('')}</select></label>`;
  const line = (key, va, vb, better) => `<tr><th scope="row">${t(key)}</th><td class="num">${va == null ? `<span class="muted">${t('un.his.notrec')}</span>` : num(va)}</td><td class="num">${vb == null ? `<span class="muted">${t('un.his.notrec')}</span>` : num(vb)}</td><td>${change(va, vb, better)}</td></tr>`;
  const cards = h.cards || [];
  const closed = cards.filter(c => (c.state === 'done' || c.state === 'resolved') && c.at && c.at > A.at && c.at <= B.at);
  const fresh = b === scans.length - 1 ? cards.filter(c => c.new && c.state === 'open') : null;
  const cardRow = c => `<li class="row" style="padding-inline:0;min-height:44px">${c.id ? `<a class="link" href="${href('/problems/' + enc(c.id))}">${code(c.id)}</a>` : code(c.key)}<span class="row__main small">${rich(L(c.title))}</span></li>`;
  return `<div class="page">
    ${back('/understand/history', t('un.v.history'))}
    <h1 class="lede un-lede-sm">${esc(t('un.cmp.lede', { a: fmtWhen(A.at), b: fmtWhen(B.at) }))}</h1>
    <p class="guide">${t('un.cmp.guide')}</p>
    <div class="un-picks">${opt(a, 'earlier')}${opt(b, 'later')}</div>
    ${same ? `<div class="panel empty" style="margin-top:16px"><p class="empty__title">${t('un.cmp.same.pick')}</p></div>` : `
    <section class="section"><div class="panel un-table-wrap" tabindex="0"><table class="un-table un-cmp"><thead><tr><th scope="col">${t('un.ind.what')}</th><th scope="col">${t('un.cmp.earlier')}</th><th scope="col">${t('un.cmp.later')}</th><th scope="col">${t('un.cmp.change')}</th></tr></thead>
      <tbody>${line('un.cmp.score', score(A), score(B), 'up')}${line('un.cmp.open', openTotal(A), openTotal(B), 'down')}
        ${SEVS.slice(0, 4).map(k => line('sev.' + k, A.open[k], B.open[k], 'down')).join('')}
        ${line('un.cmp.closed', A.closed, B.closed, 'up')}${line('un.cmp.all', A.total, B.total, null)}</tbody></table></div>
      <p class="small muted" style="margin-top:8px">${t('un.cmp.note')}</p></section>
    <section class="section"><h2 class="h2">${esc(t('un.cmp.closedbetween', { n: num(closed.length) }))}</h2>
      ${closed.length ? `<ul class="rows" style="margin-top:8px">${closed.slice(0, 50).map(cardRow).join('')}</ul>${andMore(closed)}` : `<p class="small muted" style="margin-top:8px">${t('un.cmp.noclosed')}</p>`}</section>
    <section class="section"><h2 class="h2">${t('un.cmp.fresh')}</h2>
      ${fresh ? `<p class="small ink-2" style="margin:8px 0">${esc(t('un.cmp.fresh.v', { n: num(fresh.length) }))}</p>${fresh.length ? `<ul class="rows">${fresh.slice(0, 50).map(cardRow).join('')}</ul>${andMore(fresh)}` : ''}` : `<p class="small muted" style="margin-top:8px">${t('un.cmp.fresh.onlylast')}</p>`}</section>`}
  </div>`;
}
screen({ id: 'S-45', path: '/understand/history/compare', place: 'understand', needs: NEEDS, title: () => t('un.cmp.title'), render: comparePage, loading: () => loading(t('un.his.loading')) });
screen({ id: 'S-44', path: '/understand/history/:check', place: 'understand', needs: NEEDS, title: ctx => ctx.params.check + ' - ' + t('un.v.history'), render: checkPage, loading: () => loading(t('un.his.loading')) });
act('un-cmp', el => setQuery({ [el.dataset.side]: el.value }));
