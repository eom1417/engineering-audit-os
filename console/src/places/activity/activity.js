// S-11 Activity (RUN-01, RUN-02, RUN-08, CHK-07, CHK-08, CHK-12, ACT-01): what runs now with its stages, the other
// flows, the line in the order the person chooses, and the recent runs; S-14 All runs (RUN-03, SRC-03); the run
// controls (pause, resume, stop with its question, retry, move up and down, remove from the line) on the live
// action API (POST /api/runs/<id>/<op>, /api/runs/reorder). Everything comes from the live command state (EAOS.live).
import {
  t, tn, num, esc, icon, href, fmtWhen, screen, sheet, act, refresh, toast, announce, setQuery, searchTyped, parseHash, closeSheetThen, offline, local, rerenderSheet,
  live, store, client, ActionError, normalize, model, ac,
} from 'eaos';
import { stagesOf, stageButton, counts, finished, stageTitle } from './stages.js';
import { clockHTML } from './clock.js';

const enc = encodeURIComponent;
const runHref = r => href('/activity/run/' + enc(r.id));

/** A refusal of the live API, said where it happened. */
export function refused(e) { toast(e instanceof ActionError ? e.message : String(e), { refusal: true }); }

export function controls(r, small) {
  if (offline()) return '';
  const rs = ac.runState(r), sm = small ? 'btn--sm' : '';
  const stop = `<button class="btn btn--secondary ${sm}" data-act="sheet" data-sheet="stop:${esc(r.id)}">${icon('stop')}${t('ac.ctl.stop')}</button>`;
  if (rs === 'running' || rs === 'you') return `<button class="btn btn--secondary ${sm}" data-act="ac-ctl" data-op="pause" data-id="${esc(r.id)}" data-fk="pause-${esc(r.id)}">${icon('pause')}${t('ac.ctl.pause')}</button>${stop}`;
  if (rs === 'paused') return `<button class="btn btn--primary ${sm}" data-act="ac-ctl" data-op="resume" data-id="${esc(r.id)}" data-fk="resume-${esc(r.id)}">${icon('play')}${t('ac.ctl.resume')}</button>${stop}`;
  return '';
}

/** The check now: the running stages, n of N, what is left, its controls. */
function checkNow(r) {
  const flow = ac.flowOfRun(r);
  const list = stagesOf(flow, r);
  const rs = ac.runState(r), signin = !!(live.signIn && live.signIn.asked), you = rs === 'you' || signin;
  const running = list.filter(s => ['running', 'paused', 'you'].includes(s.state));
  const done = finished(list), c = counts(list);
  const e = flow && flow.estimate;
  const left = e && e.low != null ? t('live.left', { lo: num(Math.max(1, Math.round(e.low / 60))), hi: num(Math.max(1, Math.round(e.high / 60))) }) : '';
  const title = signin ? t('ac.now.check.you') : you ? t('ac.now.check.q') : rs === 'paused' ? t('ac.now.check.paused') : t('ac.now.check');
  const sub = signin ? t('ac.now.check.you.sub', { until: live.signIn.asked.until ? ac.when(live.signIn.asked.until) : '' })
    : you ? t('ac.now.check.q.sub')
    : list.length ? t('ac.now.check.sub', { done: num(done), total: num(list.length), stages: running.map(s => stageTitle(s.id)).join(t('list.sep')) || t('ac.now.starting') }) + left
      : t('ac.now.starting');
  return `<div class="panel ac-now ${you ? 'ac-now--you' : ''}">
    <a class="ac-now__head" href="${runHref(r)}">${ac.glyph(rs)}<span class="row__main"><span class="row__title">${esc(title)}</span>
      <span class="row__meta" style="display:block">${sub}</span></span>${icon('chev', 'icon--dir muted')}</a>
    ${clockHTML(r, flow, list)}
    ${ac.progressBar(list.length ? done / list.length : 0, title)}
    ${running.length ? `<div class="ac-now__stages"><span class="block-title">${you ? t('ac.now.waits') : rs === 'paused' ? t('ac.now.paused_at') : t('ac.now.running_stages')}</span>
      <ul class="ac-layer__list ac-layer__list--row">${running.map(s => stageButton(s, false)).join('')}</ul>
      <p class="small ink-2">${esc(t('ac.now.counts', { done: num(c.ok || 0), waiting: num(c.waiting || 0), total: num(list.length) }))} <a class="link" href="${runHref(r)}">${t('ac.now.all_stages')}</a></p></div>` : ''}
    <div class="ac-now__foot">${you ? `<a class="btn btn--primary" href="${href('/waiting/sign-in')}">${t('wt.signin.act')}</a>` : `<span class="small muted">${t('ac.now.started', { when: ac.when(r.started || r.created) })}</span>`}
      <span class="ac-now__ctl">${controls(r, true)}</span></div></div>`;
}

/** Any other run now: a fix (its flow's stage), an explanation, an app run… */
function otherNow(r) {
  const rs = ac.runState(r);
  const fix = r.verb === 'fix' ? live.progress && live.progress.flows && live.progress.flows.fix : null;
  const stages = fix && fix.state === 'running' ? fix.stages || [] : [];
  const doing = stages.find(s => s.state === 'running');
  const share = stages.length ? stages.filter(s => s.state === 'ok').length / stages.length : null;
  const title = r.verb === 'fix' ? t(rs === 'paused' ? 'ac.now.fix.paused' : 'ac.now.fix', { problems: tn('pl.problem', (r.cards || []).length) }) : ac.runLabel(r);
  const sub = rs === 'you' ? t('ac.now.you') : doing ? (doing.description || doing.name) : ac.stateWord(rs);
  return `<div class="panel ac-now ${rs === 'you' ? 'ac-now--you' : ''}">
    <a class="ac-now__head" href="${runHref(r)}">${ac.glyph(rs)}<span class="row__main"><span class="row__title">${esc(title)}</span>
      <span class="row__meta" style="display:block">${esc(sub)}</span></span>${icon('chev', 'icon--dir muted')}</a>
    ${share != null ? ac.progressBar(share, title) : ''}
    <div class="ac-now__foot">${rs === 'you' ? `<a class="btn btn--primary" href="${r.question ? href('/waiting/questions') : runHref(r)}">${t('ac.now.answer')}</a>` : `<span class="small muted">${t('ac.now.started', { when: ac.when(r.started || r.created) })}</span>`}
      <span class="ac-now__ctl">${controls(r, true)}</span></div></div>`;
}

const FLOW_PAGE = { tools: '/project/tools', setup: '/project/app', safety: '/project/app' };
/** CHK-12: one line per other flow that ran (installing the tools, setting up the app, recording the screens). */
function otherFlows() {
  const flows = (live.progress && live.progress.flows) || {};
  const rows = Object.keys(FLOW_PAGE).map(id => [id, flows[id]]).filter(([, f]) => f && f.state && f.state !== 'none');
  if (!rows.length) return '';
  return `<div class="panel rows" style="margin-top:12px">${rows.map(([id, f]) => {
    const st = f.state === 'done' ? (f.status === 'COMPLETE' ? 'ok' : 'partial') : f.state;
    const stages = f.stages || [];
    const sub = f.state === 'running' ? t('ac.flow.running', { done: num(stages.filter(s => s.state === 'ok').length), total: num(stages.length) })
      : t('ac.flow.ended', { when: fmtWhen(f.ended_at) });
    return `<a class="row" href="${href(FLOW_PAGE[id])}">${ac.glyph(st)}<span class="row__main"><span class="row__title">${t('ac.flow.' + id)}</span><span class="row__meta" style="display:block">${esc(sub)}</span></span>${icon('chev', 'icon--dir muted')}</a>`;
  }).join('')}</div>`;
}

export function queueRows() {
  const q = ac.queue();
  if (!q.length) return `<p class="small muted">${t('ac.line.empty')}</p>`;
  const busy = !!ac.liveRun();
  return `<ul class="panel rows">${q.map((r, i) => {
    const meta = i === 0 ? t(busy ? 'ac.line.next.busy' : 'ac.line.next.free') : t('ac.line.nth', { n: num(i + 1) });
    const label = ac.runLabel(r);
    return `<li class="row ac-qrow">${ac.glyph('queued')}
      <a class="row__main ac-qrow__main" href="${runHref(r)}"><span class="row__title">${esc(label)}</span>
        <span class="row__meta" style="display:block">${esc(meta)}. ${esc(t('ac.line.by.' + byOf(r)))}</span></a>
      ${offline() ? '' : `<span class="row__end ac-qrow__ctl">
        <button class="btn btn--icon" data-act="ac-move" data-id="${esc(r.id)}" data-dir="-1" data-fk="up-${esc(r.id)}" ${i === 0 ? 'disabled' : ''} aria-label="${esc(t('ac.line.up'))}: ${esc(label)}" title="${esc(i === 0 ? t('ac.line.first') : t('ac.line.up'))}">${icon('chev', 'ac-rot-up')}</button>
        <button class="btn btn--icon" data-act="ac-move" data-id="${esc(r.id)}" data-dir="1" data-fk="down-${esc(r.id)}" ${i === q.length - 1 ? 'disabled' : ''} aria-label="${esc(t('ac.line.down'))}: ${esc(label)}" title="${esc(i === q.length - 1 ? t('ac.line.last') : t('ac.line.down'))}">${icon('chev', 'ac-rot-down')}</button>
        <button class="btn btn--plain btn--sm" data-act="ac-remove" data-id="${esc(r.id)}">${t('ac.line.remove')}</button></span>`}</li>`;
  }).join('')}</ul>`;
}
/** Who started a run: the person here, or their assistant from the terminal. */
export const byOf = r => (r.by === 'assistant' || r.via === 'terminal' ? 'terminal' : 'you');

/** What a run ended on, for its row: its branch waits, was merged or thrown away. */
function outcome(r) {
  if (store.awaitsApproval(r)) return `<span class="ac-c-accent">${esc(t('ac.out.waits'))}</span>`;
  if (r.outcome === 'accepted') return `<span>${esc(t('ac.out.merged', { target: ac.mergedInto(r) }))}</span>`;
  if (r.outcome === 'undone') return `<span>${esc(t('ac.out.rejected'))}</span>`;
  return '';
}
export function runRow(r) {
  const rs = ac.runState(r), m = ac.took(r);
  const bits = [ac.kindWord(r), fmtWhen(r.ended || r.created)].concat(ac.ended(r) && m ? [ac.minutes(m)] : []);
  /* a run that ended badly asks the assistant why from its own row (RUN-12), without opening it first */
  const why = !offline() && ['failed', 'stopped', 'unchanged'].includes(rs)
    ? `<a class="ac-runline__why" href="${href('/ask', { run: r.id })}" aria-label="${esc(t('ac.run.ask_why') + ': ' + ac.runLabel(r))}">${icon('ask', 'icon--sm')}<span class="ac-runline__word">${t('ac.run.ask_why')}</span></a>` : '';
  return `<li${why ? ' class="ac-runline"' : ''}><a class="row" href="${runHref(r)}">${ac.glyph(rs)}<span class="row__main"><span class="row__title">${esc(ac.runLabel(r))}</span>
    <span class="row__meta ac-meta"><span>${esc(ac.stateWord(rs))}</span>${bits.map(b => `<span>${esc(b)}</span>`).join('')}${outcome(r)}</span></span>${icon('chev', 'icon--dir muted')}</a>${why}</li>`;
}

function loadingPage() {
  return `<div class="page" aria-busy="true"><h1 class="lede">${t('ac.act.loading')}</h1><div class="actions"><span class="btn skel" style="width:200px"></span></div>
    <ul class="panel rows section">${[1, 2, 3, 4].map(() => `<li class="row"><span class="skel" style="width:20px;height:20px;border-radius:50%"></span><span style="flex:1;display:grid;gap:8px"><span class="skel-line" style="width:55%"></span><span class="skel-line" style="width:35%"></span></span></li>`).join('')}</ul></div>`;
}

function emptyPage(off) {
  return `<div class="page"><h1 class="lede">${t('ac.act.empty')}</h1><p class="guide">${t('ac.act.empty.guide')}</p>
      <div class="actions"><button class="btn btn--primary" data-act="sheet" data-sheet="${off ? 'open-live' : 'check'}" data-fk="act-check">${t('st.empty.act')}</button>
        <button class="btn btn--quiet" data-act="sheet" data-sheet="${off ? 'open-live' : 'launcher'}">${t('st.other')}</button></div>
      <section class="section"><div class="section-head"><h2>${t('ac.act.recent')}</h2></div><div class="panel empty"><p class="small ink-2">${t('ac.act.recent.empty')}</p></div></section></div>`;
}
/** What the running run is at, in one sentence. */
function runLede(lr, flow) {
  if (lr.action !== 'audit') return esc(t(lr.verb === 'fix' ? 'ac.act.lede.fix' : 'ac.act.lede.run', { label: ac.runLabel(lr) }));
  if (live.signIn && live.signIn.asked) return esc(t('ac.act.lede.signin'));
  if (ac.runState(lr) === 'you') return esc(t('ac.act.lede.q'));
  if (lr.state === 'paused') return esc(t('ac.act.lede.paused'));
  const list = stagesOf(flow, lr);
  return esc(list.length ? t('ac.act.lede.check', { done: num(finished(list)), total: num(list.length) }) : t('ac.now.check'));
}
/** The page's first sentence: the read-only copy, what runs now, or how long the last check took. */
function activityLede(off, lr, last, flow) {
  if (off) return esc(t('ac.act.lede.offline', { when: fmtWhen(model.project().checked_at) }));
  if (lr) return runLede(lr, flow);
  if (last && ac.took(last)) return t('ac.act.lede.idle', { took: `<a href="${runHref(last)}">${esc(ac.minutes(ac.took(last)))}</a>`, when: esc(fmtWhen(last.ended || last.created).replace(/ \d\d:\d\d$/, '')) });
  return esc(t('ac.act.lede.none'));
}
/** Check, more, and redo from a stage when nothing runs; in the read-only copy each opens how to go live. */
function actionsHTML(off, busy, last, flow) {
  const o = a => (off ? 'data-act="sheet" data-sheet="open-live"' : a);
  return `<div class="actions">
      <button class="btn ${busy ? 'btn--secondary' : 'btn--primary'}" ${o('data-act="sheet" data-sheet="check"')} data-fk="act-check">${t('st.empty.act')}</button>
      <button class="btn btn--quiet" ${o('data-act="sheet" data-sheet="launcher"')}>${t('st.other')}</button>
      ${!busy && !off && last && ac.ended(last) && flow ? `<button class="btn btn--quiet" data-act="sheet" data-sheet="redo-pick">${t('ac.pick.open')}</button>` : ''}
      <p class="actions__note">${t(busy ? 'ac.act.note.busy' : 'ac.act.note')}</p>
    </div>`;
}
/** The latest ended runs: what waits for the person first; a refresh of the branches is kept in the full list, not here. */
function recentHTML(all) {
  const done = all.filter(r => ac.ended(r));
  const recent = done.filter(r => store.awaitsApproval(r)).concat(done.filter(r => !store.awaitsApproval(r) && r.action !== 'branch_fetch')).slice(0, 4);
  return `<section class="section" aria-labelledby="recent-h"><div class="section-head"><h2 id="recent-h">${t('ac.act.recent')}</h2><a class="link" href="${href('/activity/runs')}">${esc(t('ac.act.all', { n: num(all.length) }))}</a></div>
      ${recent.length ? `<ul class="panel rows">${recent.map(runRow).join('')}</ul>` : `<div class="panel empty"><p class="small ink-2">${t('ac.act.recent.empty')}</p></div>`}</section>`;
}
function activityPage(ctx) {
  const off = ctx.offline;
  if (ctx.state === 'loading' || (!off && !live.loaded)) return loadingPage();
  const all = ac.runs();
  if (ctx.state === 'empty' || (!off && !all.length)) return emptyPage(off);
  const lr = ac.liveRun(), last = ac.lastCheck(), flow = ac.checkFlow();
  const busy = !!lr;
  return `<div class="page">
    <h1 class="lede">${activityLede(off, lr, last, flow)}</h1>
    <p class="guide">${t(off ? 'ac.act.guide.offline' : busy ? 'ac.act.guide.busy' : 'ac.act.guide')}</p>
    ${actionsHTML(off, busy, last, flow)}
    ${lr ? `<section class="section" aria-labelledby="now-h"><div class="section-head"><h2 id="now-h">${t('ac.act.now')}</h2></div>${lr.action === 'audit' ? checkNow(lr) : otherNow(lr)}${otherFlows()}</section>` : ''}
    <section class="section" aria-labelledby="line-h"><div class="section-head"><h2 id="line-h">${t('ac.act.line')}</h2><span class="small muted">${t('ac.act.line.sub')}</span></div>${queueRows()}</section>
    ${recentHTML(all)}
    ${lr ? '' : `<section class="section" aria-labelledby="flows-h"><div class="section-head"><h2 id="flows-h">${t('ac.flow.title')}</h2></div>${otherFlows() || `<p class="small muted">${t('ac.flow.none')}</p>`}</section>`}
  </div>`;
}
screen({ id: 'S-11', path: '/activity', place: 'activity', needs: ['cards', 'history'], title: () => t('nav.activity'), render: activityPage, loading: loadingPage });

/* ---------- the controls (RUN-02, RUN-08) ---------- */
act('ac-ctl', async el => {
  if (el.disabled || !client) return;
  el.disabled = true;
  try {
    const run = await client.control(el.dataset.id, el.dataset.op);
    store.patchRun(run.id, run);
    toast(t({ pause: 'ac.ctl.paused', resume: 'ac.ctl.resumed', retry: 'ac.ctl.retried' }[el.dataset.op], { n: num(run.attempt || 1) }),
      el.dataset.op === 'retry' ? { link: { href: runHref(run), text: t('toast.follow') } } : undefined);
    store.refresh();
  } catch (e) { refused(e); el.disabled = false; }
});
act('ac-move', async el => {
  if (el.disabled || !client) return;
  const ids = ac.queue().map(r => r.id);
  const i = ids.indexOf(el.dataset.id), j = i + Number(el.dataset.dir);
  if (i < 0 || j < 0 || j >= ids.length) return;
  [ids[i], ids[j]] = [ids[j], ids[i]];
  try {
    live.queue = await client.reorder(ids);
    refresh();
    announce(t('ac.line.moved', { label: ac.runLabel(ac.runOf(el.dataset.id)), n: num(j + 1) }));
  } catch (e) { refused(e); }
  store.refresh();
});
act('ac-remove', async el => {
  const r = ac.runOf(el.dataset.id);
  if (!r || !client) return;
  try {
    store.patchRun(r.id, await client.control(r.id, 'stop'));
    toast(t('ac.line.removed', { label: ac.runLabel(r) }));
    if (parseHash().path === '/activity/run/' + r.id && parseHash().query.sheet) closeSheetThen(() => {});
    store.refresh();
  } catch (e) { refused(e); }
});

/* Stop asks once (RUN-08) */
sheet('stop', {
  kind: 'dialog',
  render(id, query, own) {
    const r = ac.runOf(id);
    if (!r) return { title: esc(t('ac.run.notfound', { id })), body: '' };
    return {
      title: esc(t(r.action === 'audit' ? 'ac.stop.title.check' : 'ac.stop.title', { label: ac.runLabel(r) })),
      body: `<p>${t('ac.stop.body')}</p><p class="small ink-2">${t(r.action === 'audit' ? 'ac.stop.kept.check' : 'ac.stop.kept')}</p>${own.refused ? `<p class="small" role="alert">${icon('warn', 'icon--sm')} ${esc(own.refused)}</p>` : ''}`,
      foot: `<div class="sheet__foot-row"><button class="btn btn--secondary" data-act="sheet-close" data-autofocus>${t('cancel')}</button>
        <button class="btn btn--primary" data-act="ac-stop" data-id="${esc(id)}" ${own.busy ? 'disabled' : ''}>${icon('stop')}${t('ac.ctl.stop.do')}</button></div>`,
    };
  },
});
act('ac-stop', async el => {
  const own = local();
  if (el.disabled || !client) return;
  own.busy = true; rerenderSheet();
  try {
    const run = await client.control(el.dataset.id, 'stop');
    store.patchRun(run.id, run);
    closeSheetThen(() => { refresh(); toast(t('ac.ctl.stopped')); store.refresh(); });
  } catch (e) { Object.assign(own, { busy: false, refused: e instanceof ActionError ? e.message : String(e) }); rerenderSheet(); }
});

/* ---------- S-14 all runs ---------- */
const OPEN = ['queued', 'running', 'paused', 'you'];
function searchText(r) {
  return [r.id, r.label && r.label.ar, r.label && r.label.en, ac.kindWord(r), (r.cards || []).join(' '), (r.result && r.result.branch) || '',
    ac.stateWord(ac.runState(r)), ac.whoWord(r), store.awaitsApproval(r) ? t('ac.out.waits') : ''].join(' ');
}
function runsPage(ctx) {
  if (!ctx.offline && !live.loaded) return loadingPage();
  const q = ctx.query;
  const all = ac.runs();
  const list = all.filter(r => {
    const rs = ac.runState(r);
    if (q.show === 'open' && !OPEN.includes(rs)) return false;
    if (q.show === 'ended' && OPEN.includes(rs)) return false;
    if (q.st && rs !== q.st) return false;
    return !q.q || normalize.matches(searchText(r), q.q);
  });
  const seg = [['', t('who.all')], ['open', t('ac.runs.open')], ['ended', t('ac.runs.ended')]]
    .map(([k, label]) => `<a href="${href('/activity/runs', Object.assign({}, q, { show: k || null }))}" aria-current="${(q.show || '') === k}">${label}</a>`).join('');
  const chips = ['queued', 'running', 'done', 'stopped', 'failed', 'unchanged'].map(s => `<a class="fchip ${q.st === s ? 'is-on' : ''}" href="${href('/activity/runs', Object.assign({}, q, { st: q.st === s ? null : s }))}" ${q.st === s ? 'aria-current="true"' : ''}>${ac.glyph(s)}${esc(ac.stateWord(s))}</a>`).join('');
  const answers = ac.quickAnswers().slice(0, 20);
  const quick = q.quick ? `<div class="section"><div class="block-title">${t('ac.runs.quick.title')}</div>${answers.length ? `<ul class="panel rows">${answers.map(x => `<li class="row">${icon('book', 'icon--sm muted')}<span class="row__main"><span class="row__title">${esc(ac.runLabel(x))}</span><span class="row__meta" style="display:block">${t('ac.runs.quick.row')} ${esc(fmtWhen(x.created))}</span></span></li>`).join('')}</ul>` : `<p class="small muted">${t('ac.runs.quick.none')}</p>`}</div>` : '';
  return `<div class="page">
    ${ac.back('/activity', t('nav.activity'))}
    <h1 class="lede">${esc(t('ac.runs.lede', { runs: tn('ac.pl.run', all.length) }))}</h1>
    <p class="guide">${t('ac.runs.guide')}</p>
    <div class="ptools">
      <label class="field">${icon('search')}<span class="sr-only">${t('ac.runs.search')}</span><input type="search" id="rq" data-fk="rq" data-input="ac-rq" value="${esc(q.q || '')}" placeholder="${esc(t('ac.runs.search'))}" autocomplete="off"></label>
      <nav class="seg" aria-label="${esc(t('ac.runs.filter'))}">${seg}</nav>
      <div class="fchips" role="group" aria-label="${esc(t('facet.state'))}">${chips}</div>
    </div>
    <div class="listhead"><span class="listhead__count" aria-live="polite">${esc(t('ac.runs.count', { shown: num(list.length), total: num(all.length) }))}</span>
      <label class="ac-inline-switch small ink-2"><span class="switch"><input type="checkbox" data-change="ac-quick" data-fk="quick" ${q.quick ? 'checked' : ''} aria-label="${esc(t('ac.runs.quick'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span>${t('ac.runs.quick')}</label></div>
    ${list.length ? `<ul class="panel rows">${list.map(runRow).join('')}</ul>` : `<div class="panel empty"><p class="empty__title">${t('ac.runs.none')}</p><a class="btn btn--secondary" href="${href('/activity/runs')}">${t('pb.clear')}</a></div>`}
    ${quick}
    <p class="list-foot">${t('ac.runs.kept')}</p>
  </div>`;
}
screen({ id: 'S-14', path: '/activity/runs', place: 'activity', title: () => t('ac.runs.title'), render: runsPage, loading: loadingPage });
act('ac-rq', el => searchTyped(el));
act('ac-quick', el => setQuery({ quick: el.checked ? '1' : null }));
export { runHref };
