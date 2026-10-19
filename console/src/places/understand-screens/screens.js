// S-36 reviewed pages (SCR-01), S-37 every screen (SCR-02) and S-38 one screen (SCR-03, LIB-06), on screens.json and
// journeys.json: the pages the check pictured and reviewed, their findings placed on the real pictures; every declared
// screen, captured or not, with its open issues and journey flags; one screen with its pictures per width (before and
// after a batch when the media pairs them), its findings, its inputs, where it is declared and its pictures.
import { t, tn, L, num, esc, icon, code, sev, href, rich, screen, data, parseHash } from 'eaos';
import { tabs, seg, search, count, facts, nm, enc, back, loading, notMeasured, empty, notFound, matches, where, missingRow, page } from '../understand-kit/kit.js';
import { figure } from '../understand-kit/pictures.js';

const NEEDS = ['screens', 'journeys', 'media', 'coverage'];
const SEVR = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const S = () => data.section('screens');
const scr = id => (S().screens || []).find(s => s.id === id);
const jscreen = id => ((data.section('journeys') || {}).screens || []).find(s => s.id === id);
const pageOf = (id, kind) => (S().pages || []).find(p => (!kind || p.kind === kind) && ((p.same_as || []).includes(id) || p.path === id));
const kindsOf = () => ((S().coverage || {}).kinds || []);
const kindName = id => L((kindsOf().find(k => k.id === id) || { name: id }).name);
const scrLink = (id, q) => href('/understand/screens/' + enc(id), q);
const worst = list => list.reduce((m, f) => Math.min(m, SEVR[f.severity] ?? 9), 9);
const findingsOf = p => (p.pictures || []).flatMap(x => x.findings || []).filter((f, i, all) => all.findIndex(y => y.id === f.id) === i);
const vpWord = v => (v === 'phone' || v <= 480 ? t('un.vp.phone') : t('un.vp.desk'));

/* ---------- S-36 reviewed pages ---------- */
function pagesPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.idx.empty'), t('un.idx.empty.guide'));
  if (!S()) return notMeasured('screens', 'screens');
  const kinds = kindsOf(), kind = kinds.some(k => k.id === ctx.query.kind) ? ctx.query.kind : null;
  const pages = (S().pages || []).filter(p => !kind || p.kind === kind).sort((a, b) => (worst(findingsOf(a)) - worst(findingsOf(b))) || (b.findings - a.findings));
  const total = pages.reduce((n, p) => n + (p.findings || 0), 0);
  const row = p => {
    const fs = findingsOf(p);
    const sid = (p.same_as || [])[0] || p.path;
    const s = scr(sid);
    const state = p.state === 'findings' ? `<span class="tag tag--state">${esc(tn('un.pl.finding', p.findings))}</span>` : p.state === 'clean' ? `<span class="tag tag--ok">${icon('check')}${t('un.pages.clean')}</span>`
      : `<span class="tag tag--nm">${t('un.pages.notreviewed')}</span>`;
    return `<a class="row" href="${scrLink(sid, { from: 'reviewed', kind: p.kind || null })}"><span class="row__main"><span class="un-gaprow__top"><span class="row__title">${esc(s ? s.title : p.path)}</span>${code(p.path)}${p.kind ? `<span class="tag">${esc(kindName(p.kind))}</span>` : ''}</span>
      <span class="row__meta" style="display:block">${(p.same_as || []).length > 1 ? esc(t('un.pages.template', { n: num(p.same_as.length) })) + t('list.sep') : ''}${p.state === 'not_reviewed' ? t('un.pages.notreviewed.why') : fs.length ? esc(t('un.pages.worst', { sev: t('sev.' + fs.slice().sort((a, b) => SEVR[a.severity] - SEVR[b.severity])[0].severity) })) : t('un.pages.nothing')}</span></span>
      <span class="row__end">${state}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
  };
  const first = pages.find(p => (p.pictures || []).length);
  const shot = first && (first.pictures.find(x => x.viewport !== 'phone') || first.pictures[0]);
  return `<div class="page page--wide">
    ${tabs('screens')}
    <h1 class="lede">${esc(t('un.pages.lede', { n: tn('un.pl.page', pages.length), k: tn('un.pl.finding', total) }))}</h1>
    <p class="guide">${t('un.pages.guide')}</p>
    ${kinds.length ? covered(kinds) : ''}
    ${kinds.length > 1 ? `<div class="section">${seg('kind', [['all', t('un.kinds.all'), (S().pages || []).length], ...kinds.map(k => [k.id, esc(L(k.name)), (S().pages || []).filter(p => p.kind === k.id).length])], kind || 'all', t('un.kinds.label'), { dflt: 'all' })}</div>` : ''}
    ${pages.length ? `<div class="un-pagesgrid section" style="margin-top:24px">
      <div><div class="listhead">${count(pages.length, pages.length)}<span class="small muted">${t('un.pages.order')}</span></div><div class="panel rows">${pages.map(row).join('')}</div></div>
      ${shot ? `<aside class="only-desk un-pagesgrid__pic" aria-label="${esc(t('un.pages.preview'))}"><div class="block-title">${esc(t('un.pages.preview.of', { route: first.path }))}</div>
        ${figure(shot, findingsOf(first).map((f, i) => ({ n: i + 1, region: (shot.findings || []).find(x => x.id === f.id) ? (shot.findings.find(x => x.id === f.id).region) : null })), t('un.pic.cap', { w: num(shot.width) }))}
        <a class="btn btn--secondary btn--sm" href="${scrLink((first.same_as || [])[0] || first.path, { from: 'reviewed' })}">${t('un.pages.openlarge')}</a></aside>` : ''}
    </div>` : nm(t('un.pages.none'), t('un.pages.none.why'))}
  </div>`;
}
// Which kinds of users of the code the check saw, why not the others, and a page one kind opened that is another's only
function covered(kinds) {
  const missed = kinds.filter(k => !k.reached), breaches = (S().coverage || {}).breaches || [];
  return `<div class="section"><p class="small ink-2">${esc(t('un.kinds.seen', { n: num(kinds.length - missed.length), of: num(kinds.length) }))}
    ${missed.map(k => esc(t('un.kinds.unseen.' + k.why, { name: L(k.name), n: num(k.pages) }))).join(' ')}</p>
    ${breaches.map(b => `<p class="small" role="alert" style="display:flex;gap:6px;align-items:baseline">${icon('warn', 'icon--sm')}<span>${esc(t('un.kinds.breach', { kind: kindName(b.kind), page: b.page, of: kindName(b.of) }))}</span></p>`).join('')}</div>`;
}
screen({ id: 'S-36', path: '/understand/screens', place: 'understand', needs: NEEDS, title: () => t('un.v.screens'), render: pagesPage, loading: () => loading(t('un.pages.loading')) });

/* ---------- S-37 every screen ---------- */
const openIssues = s => (s.issues || []).filter(x => x.state !== 'fixed');
function allPage(ctx) {
  if (ctx.state === 'empty') return empty(t('un.all.empty'), t('un.all.empty.guide'));
  if (!S()) return notMeasured('screens/all', 'screens');
  const q = ctx.query, f = q.filter || 'all';
  const all = S().screens || [];
  let rows = all.slice();
  if (f === 'issues') rows = rows.filter(s => openIssues(s).length);
  else if (f === 'flags') rows = rows.filter(s => (s.flags || []).length);
  else if (f === 'captured') rows = rows.filter(s => (s.shots || []).length);
  if (q.q) rows = rows.filter(s => matches([s.title, s.route, s.file].join(' '), q.q));
  rows.sort((a, b) => (openIssues(b).length - openIssues(a).length) || a.route.localeCompare(b.route));
  const captured = all.filter(s => (s.shots || []).length).length, issues = all.reduce((n, s) => n + openIssues(s).length, 0);
  const row = s => {
    const iss = !(s.shots || []).length ? `<span class="tag tag--nm">${t('un.all.notchecked')}</span>` : openIssues(s).length ? `<span class="tag tag--state">${esc(tn('un.pl.issue', openIssues(s).length))}</span>` : `<span class="tag tag--ok">${icon('check')}${t('un.all.noissues')}</span>`;
    return `<a class="row" href="${scrLink(s.id)}">${icon('screen', 'muted')}<span class="row__main"><span class="un-gaprow__top"><span class="row__title">${esc(s.title)}</span>${code(s.route)}</span>
      <span class="row__meta" style="display:block">${(s.shots || []).length ? esc(tn('un.pl.shot', s.shots.length)) : t('un.all.notcaptured')}${(s.flags || []).map(fl => `${t('list.sep')}<span class="caution-ic">${t('un.flag.' + fl)}</span>`).join('')}</span></span>
      <span class="row__end">${iss}</span>${icon('chev', 'icon--sm icon--dir muted')}</a>`;
  };
  const pg = page(rows, row);
  return `<div class="page page--wide">
    ${tabs('screens/all')}
    <h1 class="lede">${esc(t('un.all.lede', { n: tn('un.pl.screen', all.length) }))}</h1>
    <p class="guide">${esc(t('un.all.guide', { c: num(captured), m: num(all.length), i: num(issues) }))}</p>
    ${!captured ? `<div class="actions"><a class="btn btn--primary" href="${href('/activity', { sheet: 'launcher' })}">${t('un.all.empty.act')}</a></div>` : ''}
    <div class="ptools">${search(q.q, t('un.all.search'))}${seg('filter', [['all', t('un.all')], ['issues', t('un.all.f.issues')], ['flags', t('un.all.f.flags')], ['captured', t('un.all.f.captured')]], f, t('un.all.filter'), { dflt: 'all', cls: 'un-seg-wrap' })}</div>
    <div class="listhead">${count(pg.shown, rows.length)}<span class="small muted">${t('un.all.order')}</span></div>
    ${rows.length ? `<div class="panel rows">${pg.html}</div>${pg.more}` : `<div class="panel empty"><p class="empty__title">${t('un.all.none')}</p><a class="btn btn--secondary" href="${href('/understand/screens/all')}">${t('pb.clear')}</a></div>`}
    ${(S().missing || []).map(missingRow).join('')}
  </div>`;
}
screen({ id: 'S-37', path: '/understand/screens/all', place: 'understand', needs: NEEDS, title: () => t('un.v.screens-all'), render: allPage, loading: () => loading(t('un.all.loading')) });

/* ---------- S-38 one screen ---------- */
function screenPage(ctx) {
  if (!S()) return notMeasured('screens/all', 'screens');
  const id = ctx.params.id, q = ctx.query;
  const backTo = q.from === 'reviewed' ? ['/understand/screens', t('un.v.screens')] : ['/understand/screens/all', t('un.v.screens-all')];
  const s = scr(id);
  if (!s) return notFound(id, backTo[0], backTo[1]);
  const js = jscreen(id) || {};
  const pg = pageOf(id, q.kind);
  const pics = pg ? pg.pictures || [] : [];
  const shots = (s.shots || []).length ? s.shots : pics.map(p => ({ path: p.path, width: p.width, phase: null, batch: null }));
  const widths = [...new Set(pics.map(p => p.width).concat(shots.map(x => x.width)))].filter(Boolean).sort((a, b) => b - a);
  const vp = widths.includes(+q.vp) ? +q.vp : widths[0];
  const shown = pics.find(p => p.width === vp) || (shots.find(x => x.width === vp) ? Object.assign({ findings: [] }, shots.find(x => x.width === vp)) : null);
  const before = shots.find(x => x.width === vp && x.phase === 'before'), after = shots.find(x => x.width === vp && x.phase === 'after');
  const view = q.view === 'compare' && before && after ? 'compare' : 'one';
  const findings = shown ? shown.findings || [] : [];
  const issues = openIssues(s);
  const sel = q.finding != null ? +q.finding : null;
  const r = parseHash();
  let picsHTML;
  if (!shots.length && !pics.length) picsHTML = nm(t('un.scr.notcaptured'), t('un.scr.notcaptured.why'), `<a class="btn btn--secondary btn--sm" href="${href('/activity', { sheet: 'launcher' })}">${t('un.all.empty.act')}</a>`);
  else if (view === 'compare') picsHTML = `<div class="un-compare"><div><div class="block-title">${t('un.phase.before')}</div>${figure(before, [], t('un.pic.cap', { w: num(vp) }))}</div><div><div class="block-title">${t('un.phase.after')}</div>${figure(after, [], t('un.pic.cap', { w: num(vp) }))}</div></div>
    ${before.batch ? `<p class="small muted">${esc(t('un.scr.batch', { batch: before.batch }))}</p>` : ''}`;
  else picsHTML = shown ? figure(shown, findings.map((f, i) => ({ n: i + 1, region: f.region, on: sel === i })), `${t('un.pic.cap', { w: num(vp) })}${t('list.sep')}${vpWord(shown.viewport || vp)}`) : '';
  const issueList = findings.length ? `<ol class="panel rows un-issues">${findings.map((f, i) => `<li><a class="row ${sel === i ? 'is-open' : ''}" href="${href(r.path, Object.assign({}, q, { finding: sel === i ? null : i }))}">
      <span class="un-num num">${i + 1}</span><span class="row__main"><span class="row__title small">${rich(L(f.title))}</span>
      <span class="row__meta" style="display:block">${t('un.fkind.' + f.kind)}${t('list.sep')}${rich(L(f.why || ''))}${f.region ? '' : `${t('list.sep')}${t('un.scr.wholepage')}`}</span></span>${sev(f.severity)}</a></li>`).join('')}</ol>`
    : issues.length ? `<ul class="panel rows">${issues.map(x => `<li class="row"><span class="row__main"><span class="row__title small">${rich(L(x.summary))}</span><span class="row__meta" style="display:block">${t('un.fkind.' + x.rule)}${t('list.sep')}${esc(t('un.pic.cap', { w: num(x.width) }))}</span></span>${sev(x.severity)}</li>`).join('')}</ul>`
    : `<p class="small muted">${t(shots.length ? 'un.scr.noissues' : 'un.scr.nocheck')}</p>`;
  const inputs = s.inputs || [];
  return `<div class="page page--wide">
    ${back(backTo[0], backTo[1])}
    <div class="un-itemtags">${code(s.route)}${(s.flags || []).map(fl => `<span class="tag tag--caution">${t('un.flag.' + fl)}</span>`).join('')}</div>
    <h1 class="lede un-lede-sm">${esc(s.title)}</h1>
    <p class="guide">${esc(shots.length ? ((findings.length || issues.length) ? tn('un.scr.guide', findings.length || issues.length) : t('un.scr.guide.clean')) : t('un.scr.guide.none'))}</p>
    ${widths.length ? `<div class="ptools"><div class="un-tools">${widths.length > 1 ? seg('vp', widths.map(w => [String(w), w <= 480 ? t('un.vp.phone') : t('un.vp.desk')]), String(vp), t('un.vp'), { dflt: String(widths[0]), cls: 'un-seg2' }) : ''}
      ${before && after ? seg('view', [['one', t('un.scr.now')], ['compare', t('un.scr.compare')]], view, t('un.path.view'), { dflt: 'one', cls: 'un-seg2' }) : ''}</div></div>` : ''}
    <div class="un-scrgrid">
      <div class="un-scrgrid__pic">${picsHTML}</div>
      <div class="un-scrgrid__side">
        <section><h2 class="h2" style="margin-bottom:8px">${t('un.scr.issues')}</h2>${issueList}</section>
        <section class="section"><h2 class="h2" style="margin-bottom:8px">${t('un.scr.inputs')}</h2>${inputs.length ? `<ul class="rows">${inputs.map(x => `<li class="row small" style="padding-inline:0">${code(x.label || x.name || '')}<span class="row__main muted">${esc(x.kind || '')}</span></li>`).join('')}</ul>` : nm(t('un.scr.inputs.nm'), t('un.scr.inputs.why'))}</section>
        <section class="section"><h2 class="h2" style="margin-bottom:8px">${t('un.scr.where')}</h2>${facts([
          [t('un.fn.where'), s.file ? code(s.file) : '—'],
          [t('un.scr.router'), code(where(s.router, s.line))],
          [t('un.path.comp'), s.component ? `<a class="link" href="${href('/understand/components/' + enc(s.component))}">${code(s.component)}</a>` : '—'],
          (js.twins || []).length ? [t('un.scr.twin'), js.twins.map(x => `<a class="link" href="${scrLink(x)}">${code(x)}</a>`).join(' ')] : null,
          [t('un.scr.depth'), js.depth == null || js.depth < 0 ? `<span class="caution-ic">${t('un.flag.no_way_in')}</span>` : esc(js.depth === 0 ? t('un.depth.start') : tn('un.depth.n', js.depth))],
        ])}
          <div class="un-insp__more" style="margin-top:12px"><a class="link" href="${href('/understand/journeys', { focus: id })}">${icon('map', 'icon--sm')}${t('un.scr.injourneys')}</a>
            ${s.file ? `<a class="link" href="${href('/understand/functions', { module: s.file })}">${icon('code', 'icon--sm')}${t('un.scr.fns')}</a>` : ''}</div></section>
        ${shots.length ? `<section class="section"><h2 class="h2" style="margin-bottom:8px">${t('un.scr.images')}</h2><ul class="rows">${shots.map(x => `<li class="row" style="padding-inline:0">${icon('screen', 'muted')}<span class="row__main small">${code(x.path)}<span class="row__meta" style="display:block">${num(x.width)} px${x.phase ? `${t('list.sep')}${t('un.phase.' + x.phase)}` : ''}${x.batch ? `${t('list.sep')}${code(x.batch)}` : ''}</span></span></li>`).join('')}</ul></section>` : ''}
      </div>
    </div>
  </div>`;
}
screen({ id: 'S-38', path: '/understand/screens/:id', place: 'understand', needs: NEEDS, title: ctx => ctx.params.id + ' - ' + t('un.v.screens-all'), render: screenPage, loading: () => loading(t('un.all.loading')) });
