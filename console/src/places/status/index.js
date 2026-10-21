// S-01 Status: where the project stands and the one step that fits now (PRJ-01..12, HIS-02, BLD-04, SET-06), on the
// report and the live command state. Its sheets: freshness (PRJ-04) and health on the phone (PRJ-02).
import {
  t, tn, L, num, esc, icon, code, sev, href, band, fmtWhen, exactTime, screen, sheet, liveNow, freshness, live, model, data, contract, prefs, derive,
} from 'eaos';
import { buildStep } from '../understand-kit/kit.js';

const { SEV } = model;
const NEEDS = ['meta', 'head', 'health', 'cards', 'decisions', 'history', 'plans'];
const STAGE_WORD = { done: 'st.journey.done', partial: 'st.about.partial', skipped: 'st.about.skipped' };

/** The next step the report names (head.next.tool), as the words of its button and where it goes. */
function next(offline) {
  const tot = model.totals();
  const tool = model.project().next_tool;
  if (offline) return { label: t('st.offline.next'), sheet: 'open-live', icon: 'copy' };
  if (tool === 'fix_start' && tot.fixable) return { label: t('st.next.fix', { problems: tn('pl.problem', tot.fixable) }), sheet: 'verb:fix:fixable', short: t('st.stand.next.fix', { problems: tn('pl.problem', tot.fixable) }) };
  if (tot.needs_you) return { label: t('st.next.review', { problems: tn('pl.problem', tot.needs_you) }), link: href('/problems', { who: 'you' }), short: t('st.stand.next.review') };
  return { label: t('st.empty.act'), link: href('/activity', { sheet: 'check' }), short: t('st.stand.next.check') };
}

function verdictHTML() {
  const tot = model.totals(), h = model.health();
  if (h.score == null) return esc(t('st.verdict.none'));
  if (!tot.problems) return esc(t('st.verdict.clean'));
  return t('st.verdict', {
    problems: `<a href="${href('/problems')}">${esc(tn('pl.problem', tot.problems))}</a>`,
    fixable: `<a href="${href('/problems', { who: 'eaos' })}">${num(tot.fixable)}</a>`,
  });
}

function contextChips() {
  const f = freshness(), p = model.project();
  const stale = ['behind', 'rewritten', 'dirty', 'other_branch'].includes(f.state);
  const said = !stale ? t('st.fresh', { when: fmtWhen(p.checked_at) })
    : f.state === 'behind' ? t('st.stale', { commits: tn('pl.commit', (f.behind && f.behind.commits) || 0) }) : t('st.stale.' + f.state);
  return `<div class="context">
    <a class="chip" href="${href('/project/branches')}">${icon('branch')}${code(p.branch)}</a>
    <button class="chip ${stale ? 'chip--caution' : 'chip--ok'}" data-act="sheet" data-sheet="freshness" aria-label="${esc(t('st.fresh.sr'))}">${icon(stale ? 'warn' : 'check')}${esc(said)}</button></div>`;
}

function nextStep(ctx) {
  const n = next(ctx.offline);
  const primary = n.link ? `<a class="btn btn--primary" href="${n.link}">${esc(n.label)}</a>`
    : `<button class="btn btn--primary" data-act="sheet" data-sheet="${n.sheet}">${n.icon ? icon(n.icon) : ''}${esc(n.label)}</button>`;
  return `<p class="guide">${t('st.guide')}</p>
    <div class="actions">${primary}
      <button class="btn btn--quiet" data-act="sheet" data-sheet="${ctx.offline ? 'open-live' : 'launcher'}">${t('st.other')}</button>
      <p class="actions__note">${t('st.next.note')}</p>
    </div>`;
}

const rowLink = (to, lead, title, meta) => `<a class="row" href="${href(to)}">${lead}
  <span class="row__main"><span class="row__title">${esc(title)}</span>${meta ? `<span class="row__meta" style="display:block">${esc(meta)}</span>` : ''}</span>${icon('chev', 'icon--dir muted')}</a>`;

function nowRows() {
  const rows = [];
  const wc = model.waitingCount();
  if (wc) {
    const parts = [];
    const branches = model.waitingBranches().length, decisions = model.waitingDecisions().length, questions = live.questions.length;
    if (branches) parts.push(tn('pl.fix_branch', branches));
    if (decisions) parts.push(tn('pl.decision', decisions));
    if (questions) parts.push(tn('pl.question', questions));
    if (live.signIn && live.signIn.asked) parts.push(t('st.waiting.signin'));
    rows.push(rowLink('/waiting', '<span class="dot dot--you" aria-hidden="true"></span>', tn('pl.thing_waits', wc), parts.join(t('list.sep'))).replace('class="row"', 'class="row row--you"'));
  }
  const now = liveNow();
  if (now && now.kind !== 'signin') rows.push(rowLink(now.href, `<span class="dot ${now.you ? 'dot--you' : 'dot--live'}" aria-hidden="true"></span>`, now.text, now.run ? L(now.run.label) : ''));
  const queued = live.runs.filter(r => r.state === 'queued');
  if (queued.length) rows.push(rowLink('/activity', icon('clock', 'muted'), t('st.queued', { label: L(queued[0].label) }), queued.length > 1 ? tn('pl.queued_more', queued.length - 1) : t('st.queued.sub')));
  return rows.length ? `<div class="panel rows now-rows">${rows.join('')}</div>` : '';
}

function glance(loading) {
  const tot = model.totals(), by = tot.by_severity;
  const bar = loading ? '<div class="sevbar sevbar--loading" aria-hidden="true"></div>'
    : `<div class="sevbar" role="img" aria-label="${esc(SEV.map(s => `${t('sev.' + s)} ${by[s]}`).join(', '))}">
        ${SEV.filter(s => by[s] > 0).map(s => `<span class="s-${s}" style="flex:${by[s]}"></span>`).join('')}</div>`;
  const legend = SEV.map(s => {
    const n = by[s];
    const inner = `${sev(s, false)}<span>${t('sev.' + s)}</span> <b>${loading ? '…' : num(n)}</b>`;
    return n > 0 && !loading ? `<a href="${href('/problems', { sev: s })}">${inner}</a>` : `<span class="zero">${inner}</span>`;
  }).join('');
  return `<section class="section" aria-labelledby="glance-h">
    <div class="section-head"><h2 id="glance-h">${t('st.glance')}</h2><a class="link" href="${href('/problems')}">${t('st.glance.open')}</a></div>
    <div class="panel panel__pad">${bar}<div class="legend">${legend}</div>
      <div class="split-line">
        <a href="${href('/problems', { who: 'you' })}">${t('who.you')} <b>${loading ? t('st.counting') : num(tot.needs_you)}</b></a>
        <a href="${href('/problems', { who: 'eaos' })}">${t('who.eaos')} <b>${loading ? t('st.counting') : num(tot.fixable)}</b></a>
      </div></div></section>`;
}

/** The trend sentence (HIS-02): the score against the check before, once there are two. */
function trend(h) {
  const scored = h.history.filter(x => x.score != null);
  if (scored.length < 2) return t('st.health.trend');
  const d = scored[scored.length - 1].score - scored[scored.length - 2].score;
  return d === 0 ? t('st.health.same') : t(d > 0 ? 'st.health.up' : 'st.health.down', { n: num(Math.abs(d)) });
}

function notMeasured(area) {
  return area === 'performance'
    ? `${t('st.nm.performance')} <a class="link" href="${href('/activity', { sheet: 'check', path: 'speed' })}">${t('st.nm.act')}</a>`
    : t('st.nm.other');
}

function healthBody() {
  const h = model.health();
  if (h.score == null) return `<p class="small ink-2">${t('st.verdict.none')}</p>`;
  const ticks = [40, 60, 75, 90].map(v => `<span class="meter__tick" style="inset-inline-start:${v}%"></span>`).join('');
  const meters = h.areas.map(a => {
    if (a.score == null) {
      return `<div class="meter meter--nm"><div class="meter__top"><span>${t('area.' + a.id)}</span><span class="tag tag--nm">${t('nm')}</span></div>
        <div class="meter__track"></div><div class="meter__nm">${notMeasured(a.id)}</div></div>`;
    }
    return `<div class="meter"><div class="meter__top"><span><a class="meter__name" href="${href('/problems', { area: a.id })}">${t('area.' + a.id)}</a><span class="meter__count">${esc(tn('pl.problem', a.cards))}</span></span>
      <span class="meter__val">${esc(t('st.meter.v', { score: num(a.score), band: t('band.' + band(a.score)) }))}</span></div>
      <div class="meter__track" role="img" aria-label="${esc(t('area.' + a.id))}: ${a.score}">${ticks}<span class="meter__fill" style="width:${a.score}%"></span></div></div>`;
  }).join('');
  return `<div class="health-card__top"><span class="figure">${h.score}</span><span class="health-card__band">${t('band.' + band(h.score))}</span></div>
    <p class="small ink-2" style="margin-top:4px">${esc(trend(h))}</p>
    <div class="meters" style="margin-top:20px">${meters}</div>
    <details class="fold" style="margin-top:16px;border-top:1px solid var(--line)"><summary style="padding-inline:0;min-height:48px">${icon('info', 'muted')}<span class="row__main small">${t('st.health.formula.title')}</span>${icon('chev', 'chev icon--sm')}</summary>
      <div class="fold__body small ink-2" style="padding-inline:0">${t('st.health.formula')}</div></details>`;
}

function healthRow() {
  const h = model.health();
  if (h.score == null) return '';
  const weakest = h.areas.filter(a => a.score != null).sort((a, b) => a.score - b.score)[0];
  return `<section class="section only-phone"><div class="panel rows">
    <button class="row" data-act="sheet" data-sheet="health">
      <span class="row__main"><span class="row__title">${esc(t('st.health', { score: h.score, band: t('band.' + band(h.score)) }))}</span>
      <span class="row__meta" style="display:block">${weakest ? esc(t('st.health.weakest', { area: t('area.' + weakest.id), score: weakest.score })) + '. ' : ''}${esc(trend(h))}</span></span>
      ${icon('chev', 'icon--dir muted')}</button></div></section>`;
}

function fold(id, title, sum, body) {
  return `<details class="fold" id="fold-${id}"><summary><span class="row__main"><span class="row__title">${title}</span><span class="row__meta" style="display:block">${sum}</span></span>${icon('chev', 'chev')}</summary>
    <div class="fold__body">${body}</div></details>`;
}

/** The journey's steps (live: /api/progress journey), else the check alone, which this report proves done. */
function journeySteps() {
  const steps = (live.progress && live.progress.journey) || [];
  if (steps.length) return steps.map(s => ({ title: L(s.title), done: s.done, now: !s.done && s.state === 'running' }));
  return [{ title: t('st.journey.1'), done: true, now: false }];
}

function folds(ctx) {
  const p = model.project(), tot = model.totals(), sz = model.size();
  const fixRuns = live.runs.filter(r => r.verb === 'fix' || r.action === 'fix_start');
  const lastFix = fixRuns[0];
  const waiting = model.waitingBranches();
  const n = next(ctx.offline);
  const stand = `<dl class="facts">
      ${n.short ? `<dt>${t('st.stand.next')}</dt><dd>${esc(n.short)}</dd>` : ''}
      <dt>${t('st.stand.checked')}</dt><dd>${t('st.stand.checked.v', { commit: code(p.commit.slice(0, 7)) })}</dd>
      ${tot.all_cards ? `<dt>${t('st.stand.progress')}</dt><dd>${esc(t('st.stand.progress.v', { closed: num(tot.closed), all: num(tot.all_cards) }))}</dd>` : ''}
      ${lastFix ? `<dt>${t('st.stand.batch')}</dt><dd>${esc(t('st.stand.batch.v', { state: L(contract.STATE_WORDS[lastFix.state]), label: derive.labelOf(lastFix.label, prefs.lang) }))}
        ${lastFix.state === 'stopped' && !lastFix.outcome && !ctx.offline ? `<div style="margin-top:4px"><button class="btn btn--secondary btn--sm" data-act="sheet" data-sheet="action:fix_abandon">${t('st.stand.close')}</button></div>` : ''}</dd>` : ''}
      ${waiting.map(run => `<dt>${t('st.stand.branch')}</dt><dd><a class="link" href="${href('/waiting/' + encodeURIComponent(run.id))}">${code(run.result.branch)}</a></dd>`).join('')}
    </dl>
    ${ctx.offline ? '' : `<div class="actions" style="margin-top:12px"><a class="btn btn--secondary btn--sm" href="${href('/ask', { note: 'project' })}">${icon('note')}${t('st.stand.note')}</a></div>`}`;
  const steps = journeySteps();
  const journey = `<ol class="rows">${steps.map(s => `<li class="row" style="padding-inline:0;min-height:44px">${s.done ? icon('check', '') : icon('circle', 'muted')}
      <span class="row__main">${esc(s.title)}</span>${s.done || s.now ? `<span class="tag ${s.done ? 'tag--ok' : 'tag--state'}">${t(s.done ? 'st.journey.done' : 'st.journey.now')}</span>` : ''}</li>`).join('')}</ol>`;
  const left = steps.filter(s => !s.done);
  const journeySum = left.length ? t('st.fold.journey.sum', { done: num(steps.length - left.length), all: num(steps.length), next: left[0].title }) : t('st.fold.journey.all');
  const st = sz.stages;
  const count = state => st.filter(s => s.state === state).length;
  const lastCheck = live.runs.find(r => r.action === 'audit');
  const langs = sz.languages.map(l => `${esc(l.name)} ${Math.round(l.share * 100)}%`).join(t('list.sep'));
  const notDone = st.filter(x => x.state !== 'done');
  const about = `<dl class="facts">
      <dt>${t('st.about.langs')}</dt><dd>${langs}</dd>
      <dt>${t('st.about.files')}</dt><dd class="num">${num(sz.files)}</dd>
      <dt>${t('st.about.lines')}</dt><dd class="num">${num(sz.lines)}</dd>
      <dt>${t('st.about.stages')}</dt><dd>${t('st.about.stages.v', { done: num(count('done')), partial: num(count('partial')), skipped: num(count('skipped')) })}
        ${lastCheck ? `<a class="link" href="${href('/activity/run/' + encodeURIComponent(lastCheck.id))}">${t('st.about.stages.open')}</a>` : ''}</dd>
      <dt>${t('st.about.scan')}</dt><dd>${code(p.branch)} ${code(p.commit.slice(0, 7))}</dd>
      <dt>${t('st.about.eaos')}</dt><dd>${code('EAOS ' + p.eaos_version)}</dd>
    </dl>
    ${notDone.length ? `<div class="block-title" style="margin-top:16px">${t('st.about.notdone')}</div>
    <ul class="panel rows">${notDone.map(x => `<li><button class="row" data-act="sheet" data-sheet="stage:${esc(x.id)}">${icon(x.state === 'skipped' ? 'dash' : 'warn', 'muted')}
        <span class="row__main"><span class="row__title">${code(x.id)}</span><span class="row__meta" style="display:block">${t(STAGE_WORD[x.state] || 'st.about.partial')}</span></span>
        ${icon('chev', 'icon--sm icon--dir muted')}</button></li>`).join('')}</ul>
    <p class="small muted" style="margin-top:8px">${t('st.about.redo')}</p>` : ''}`;
  const unmeasured = model.health().areas.filter(a => a.score == null);
  const measured = `<p class="small ink-2">${unmeasured.length ? t('st.measured.v', { n: tn('pl.area', unmeasured.length) }) : t('st.measured.all')}</p>
    ${unmeasured.map(a => `<div class="nm" style="margin-top:12px"><div class="nm__title"><span class="tag tag--nm">${t('nm')}</span>${t('area.' + a.id)}</div>
      <p class="small ink-2">${a.id === 'performance' ? t('st.measured.why') : t('st.nm.other')}</p>
      ${a.id === 'performance' ? `<div><a class="btn btn--secondary btn--sm" href="${href('/activity', { sheet: 'check', path: 'speed' })}">${t('st.nm.act')}</a></div>` : ''}</div>`).join('')}`;
  const standSum = waiting.length ? tn('pl.fix_branch_waits', waiting.length) : n.short || '';
  return `<div class="section panel">
    ${fold('stand', t('st.fold.stand'), esc(standSum), stand)}
    ${fold('journey', t('st.fold.journey'), esc(journeySum), journey)}
    ${fold('about', t('st.fold.about'), esc(t('st.fold.about.sum', { files: tn('pl.file', sz.files || 0), lines: tn('pl.line', sz.lines || 0), stages: tn('pl.stage', st.length) })), about)}
    ${fold('measured', t('st.fold.measured'), esc(unmeasured.length ? unmeasured.map(a => t('area.' + a.id)).join(t('list.sep')) : t('st.measured.all')), measured)}
  </div>`;
}

function contextSentence() {
  const p = model.project(), c = live.context;
  const report = t('st.context.report', { branch: code(p.branch), commit: code(p.commit.slice(0, 7)) });
  if (!c || !c.checkout || !c.analysis) return report;
  const same = c.checkout.branch === c.analysis.branch;
  return t(same ? 'st.context.same' : 'st.context.other', { checkout: code(c.checkout.branch || c.checkout.commit || ''), analysis: code(c.analysis.branch || '') }) + ' ' + report;
}

function aside() {
  return `<aside class="status-aside only-desk" aria-label="${esc(t('st.health.title'))}">
    <div class="panel health-card"><h2 class="sr-only">${t('st.health.title')}</h2>${healthBody()}</div>
    <p class="panel context-sentence">${contextSentence()}</p>
  </aside>`;
}

function emptyState(ctx) {
  const steps = (live.progress && live.progress.journey) || [];
  return `<div class="page">
    <h1 class="lede">${t('st.empty.lede')}</h1>
    <p class="guide">${t('st.empty.guide')}</p>
    <div class="actions">${ctx.offline ? `<button class="btn btn--primary" data-act="sheet" data-sheet="open-live">${t('offline.how')}</button>`
      : `<a class="btn btn--primary" href="${href('/activity', { sheet: 'check' })}">${t('st.empty.act')}</a>`}
      <button class="btn btn--quiet" data-act="copy" data-text="eaos check --preview">${icon('copy')}${t('st.copy_request')}</button></div>
    ${steps.length ? `<div class="section panel">${fold('journey', t('st.fold.journey'), esc(L(steps[0].title)), `<ol class="rows">${steps.map(s => `<li class="row" style="padding-inline:0;min-height:44px">${icon('circle', 'muted')}<span class="row__main">${esc(L(s.title))}</span></li>`).join('')}</ol>`)}</div>` : ''}
  </div>`;
}

/** A project still being built from its plan: the build's verdict and its one next step, never a check's score. */
function buildState() {
  return `<div class="page">
    <h1 class="lede">${esc(model.project().verdict)}</h1>
    <div class="actions">${buildStep()}<a class="btn btn--quiet" href="${href('/problems/plan')}">${icon('layers', 'icon--sm')}${t('st.build.plan')}</a>
      <p class="actions__note">${t('bp.note')}</p></div>
    ${nowRows()}
  </div>`;
}

function loadingState() {
  return `<div class="page" aria-busy="true">
    <div class="context"><span class="chip skel" style="width:110px"></span><span class="chip skel" style="width:190px"></span></div>
    <h1 class="lede">${t('st.loading')}</h1>
    <div class="actions"><span class="btn skel" style="width:260px"></span></div>
    <div class="status-cols"><div>${glance(true)}</div></div>
  </div>`;
}

screen({
  id: 'S-01', path: '/status', place: 'status', needs: NEEDS,
  title: () => t('st.place'),
  loading: loadingState,
  render(ctx) {
    const build = model.buildPlan();
    if (build && !model.plan().steps.length) return buildState();
    if (ctx.state === 'empty') return emptyState(ctx);
    return `<div class="page page--status">
      ${contextChips()}
      <h1 class="lede">${verdictHTML()}</h1>
      ${nextStep(ctx)}
      <div class="status-cols">
        <div class="status-main">${nowRows()}${glance(false)}${healthRow()}${folds(ctx)}</div>
        ${aside()}
      </div>
    </div>`;
  },
});

/** Is the check still current (PRJ-04)? Asked of git now in the live console; the report's own answer otherwise. */
sheet('freshness', {
  needs: ['head'],
  kind: 'drawer',
  render() {
    const p = model.project(), f = freshness(), fresh = live.freshness || {};
    const lede = f.state === 'fresh' ? t('st.fresh.lede') : f.state === 'behind'
      ? t('st.fresh.lede.behind', { commits: tn('pl.commit', (f.behind && f.behind.commits) || 0), files: tn('pl.file', (f.behind && f.behind.files) || 0) })
      : t('st.fresh.lede.' + (['rewritten', 'dirty', 'other_branch'].includes(f.state) ? f.state : 'unknown'));
    const files = (f.behind && f.behind.file_list) || [];
    return {
      title: esc(t('st.fresh.title')),
      body: `<p class="h2">${esc(lede)}</p>
        <dl class="facts">
          <dt>${t('st.fresh.checked')}</dt><dd>${p.checked_at ? esc(exactTime(p.checked_at)) : ''}</dd>
          <dt>${t('st.fresh.branch')}</dt><dd>${code(p.branch)}</dd>
          <dt>${t('st.fresh.commit')}</dt><dd>${code(p.commit)}</dd>
          <dt>${t('st.fresh.dirty')}</dt><dd>${t(p.dirty ? 'st.fresh.dirty.yes' : 'st.fresh.dirty.v')}</dd>
          ${fresh.tip ? `<dt>${t('st.fresh.head')}</dt><dd>${fresh.tip === p.commit ? t('st.fresh.head.v', { commit: code(fresh.tip.slice(0, 7)) }) : code(fresh.tip.slice(0, 7))}</dd>` : ''}
          ${fresh.checked_at ? `<dt>${t('st.fresh.looked')}</dt><dd>${esc(fmtWhen(fresh.checked_at))}</dd>` : ''}
        </dl>
        ${files.length ? `<div><div class="block-title">${t('st.fresh.files')}</div><ul class="panel rows">${files.slice(0, 12).map(x => `<li class="row small">${code(x)}</li>`).join('')}</ul></div>` : ''}`,
      foot: `<a class="btn btn--primary btn--block" href="${href('/activity', { sheet: 'check' })}" data-act="go" data-href="${href('/activity', { sheet: 'check' })}">${t('st.fresh.check')}</a>
        <button class="btn btn--quiet btn--block" data-act="copy" data-text="eaos check --branch ${esc(p.branch)} --preview">${icon('copy')}${t('st.fresh.copy')}</button>`,
    };
  },
});

/** Health on the phone (PRJ-02); the desktop shows the same body beside the page. */
sheet('health', { kind: 'drawer', needs: ['health'], render: () => ({ title: esc(t('st.health.title')), body: `<div>${healthBody()}</div>` }) });
