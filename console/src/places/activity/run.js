// S-15 One run (RUN-04..12, CHK-07, CHK-08, CHK-11, FIX-07, FIX-10, SCR-04, CHT-05, AST-03): the run's record and its
// events, followed live (GET /api/runs/<id>/events, server-sent with Last-Event-ID) and derived into what happens now,
// the batches' progress, the question it waits on, the result or the error and the timeline (derive.deriveRun); a
// check's stages by layer from /api/progress, and the replay of a finished check at x10 or x30.
import {
  t, tn, L, num, esc, rich, icon, code, diffLines, href, fmtWhen, screen, act, refresh, refreshSoon, afterRender, parseHash, offline, has,
  live, store, model, client, derive, ac, md,
} from 'eaos';
import { controls, byOf } from './activity.js';
import { stagesOf, board, counts, finished, summary, span, lostOf, stageTitle } from './stages.js';
import { clockHTML } from './clock.js';
import { resultHTML, fixProgress, handoffHTML } from './result.js';

const enc = encodeURIComponent;
const SHOWN = 60;                 // the newest timeline lines drawn; the rest one press away
const followed = {};              // run id -> {events, stop, done}
let follow = true;                // follow the running stage (CHK-08)
let replay = { id: null, at: null, timer: 0 };

/** The run's events, read once and then live while it runs. */
function eventsOf(r) {
  if (!client || r.trimmed) return [];
  const f = followed[r.id] = followed[r.id] || { events: [], stop: null, open: false, over: false };
  const from = derive.followFrom(f, ac.ended(ac.runOf(r.id) || r));
  if (from != null) {
    f.open = true; f.over = false;
    // an ended run's stream ends once it has replayed: the reconnection that follows is not needed
    f.stop = client.follow(r.id, from, event => { f.events.push(event); refreshSoon(); }, status => {
      if (status === 'closed') f.open = false;
      if (status === 'reconnecting' && ac.ended(ac.runOf(r.id) || r)) { f.stop(); f.open = false; f.over = true; refreshSoon(); }
    });
  }
  return f.events;
}
const followOver = r => r.trimmed || !!(followed[r.id] && followed[r.id].over);
afterRender(ctx => {
  const here = (ctx.path.match(/^\/activity\/run\/(.+)$/) || [])[1];
  Object.keys(followed).forEach(id => { if (id !== (here && decodeURIComponent(here))) { if (followed[id].stop) followed[id].stop(); delete followed[id]; } });
  if (!here || replay.id !== decodeURIComponent(here) || !ctx.query.replay) { clearInterval(replay.timer); replay = { id: null, at: null, timer: 0 }; }
});

/* ---------- what the page says ---------- */
const runningCount = list => list.filter(s => ['running', 'you', 'paused'].includes(s.state)).length;
const failedLede = r => t('ac.run.failed.lede', { label: ac.runLabel(r) });
const queuedLede = r => t('ac.run.queued.lede', { n: num(r.position || 1) });
function checkDoneLede(r, list) {
  const own = ac.flowOfRun(r), lost = list.filter(lostOf).length;
  const took = ac.minutes(ac.took(r) || 1);
  if (own && lost) return t('ac.run.check.lost.lede', { took, stages: tn('pl.stage', lost), problems: tn('pl.problem', model.totals().problems) });
  if (!own) return t('ac.run.done.lede', { took });
  return t('ac.run.check.done.lede', { took, problems: tn('pl.problem', model.totals().problems), health: model.health().score == null ? t('nm') : num(model.health().score) });
}
/** A check's lede by its state; `at` counts its stages. */
const CHECK_LEDES = new Map(Object.entries({
  done: (r, at, list) => checkDoneLede(r, list),
  you: () => t(live.signIn && live.signIn.asked ? 'ac.run.check.you.lede' : 'ac.run.check.q.lede'),
  paused: (r, at) => t('ac.run.check.paused.lede', at),
  stopped: (r, at, list) => t(list.length ? 'ac.run.check.stopped.lede' : 'ac.run.check.stopped.early', at),
  failed: failedLede,
  queued: queuedLede,
}));
function checkLede(r, rs, list) {
  const at = { done: num(finished(list)), total: num(list.length), running: num(runningCount(list)) };
  if (CHECK_LEDES.has(rs)) return CHECK_LEDES.get(rs)(r, at, list);
  return list.length ? t('ac.run.check.lede', at) : t('ac.now.check');
}
/** Any other run's lede while it is not done. */
const LEDES = new Map(Object.entries({
  queued: queuedLede,
  you: () => t('ac.run.you.lede'),
  paused: r => t('ac.run.paused.lede', { label: ac.runLabel(r) }),
  running: (r, view) => (r.verb === 'fix' ? t('ac.run.fix.lede', { done: num(derive.fixCount(view, r)), total: num((r.cards || []).length) }) : t('ac.run.running.lede', { label: ac.runLabel(r) })),
  stopped: r => t(r.verb === 'fix' ? 'ac.run.fix.stopped.lede' : 'ac.run.stopped.lede'),
  failed: failedLede,
  unchanged: () => t('ac.run.unchanged.lede'),
}));
function doneLede(r) {
  const branch = r.result && r.result.branch;
  if (branch && r.outcome === 'accepted') return t('ac.run.r12.accepted', { target: ac.mergedInto(r) });
  if (branch && r.outcome === 'undone') return t('ac.run.r12.rejected');
  if (branch) return t('ac.run.r12.lede');
  return t('ac.run.done.lede2', { label: ac.runLabel(r), took: ac.minutes(ac.took(r) || 1) });
}
function lede(r, rs, view, list) {
  if (r.action === 'audit') return checkLede(r, rs, list);
  return LEDES.has(rs) ? LEDES.get(rs)(r, view) : doneLede(r);
}
/** A check that ended with stages its assistant was lost in: which, why, when the assistant comes back, and the one
 *  press that runs them again (from the first of them). */
function lostHTML(r, rs, list) {
  const lost = r.action === 'audit' && rs === 'done' ? list.filter(lostOf) : [];
  if (!lost.length) return '';
  const first = lostOf(lost[0]), who = first.assistant || t('ac.run.lost.who');
  const why = /_limit$/.test(first.code) ? t('ac.run.lost.limit', { who }) : t('ac.run.lost.failed', { who });
  return `<div class="panel ac-refuse my-3" role="note">
    <p><b>${esc(t('ac.run.lost.q', { stages: tn('pl.stage', lost.length) }))}</b> ${esc(why)}${first.resets ? ' ' + esc(t('ac.run.lost.resets', { at: first.resets })) : ''}</p>
    <p class="small ink-2">${esc(lost.map(s => stageTitle(s.id)).join(t('list.sep')))}</p>
    <div class="actions mt-2"><button class="btn btn--primary" data-act="sheet" data-sheet="redo:${esc(lost[0].id)}" data-fk="lost-redo">${t('ac.run.lost.act')}</button></div>
    <p class="small ink-2">${t('ac.run.lost.how')}</p></div>`;
}
function doneGuide(list) {
  const c = counts(list);
  return t('ac.run.check.done.guide', { done: num(c.ok || 0), partial: num((c.failed || 0) + (c.partial || 0)), other: num(list.length - (c.ok || 0) - (c.failed || 0) - (c.partial || 0)) });
}
/** A check's own guide, or undefined when the common one says it. */
function checkGuide(rs, list) {
  if (rs === 'done' && list.length) return doneGuide(list);
  if (rs === 'you') return t('ac.run.check.you.guide');
  if (rs === 'stopped' || rs === 'failed') return t('ac.run.check.stopped.guide');
  if (rs === 'running' || rs === 'paused') return t('ac.run.check.guide');
  return undefined;
}
const GUIDES = { queued: 'ac.run.queued.guide', you: 'ac.run.you.guide', unchanged: 'ac.run.unchanged.guide' };
const FIX_GUIDES = { running: 'ac.run.fix.guide', stopped: 'ac.run.fix.stopped.guide', failed: 'ac.run.fix.stopped.guide' };
function guide(r, rs, list) {
  const own = r.action === 'audit' ? checkGuide(rs, list) : undefined;
  if (own !== undefined) return own;
  const key = GUIDES[rs] || (r.verb === 'fix' && FIX_GUIDES[rs]);
  if (key) return t(key);
  if (r.result && r.result.branch) return t(r.outcome ? 'ac.run.r12.done.guide' : 'ac.run.r12.guide');
  return '';
}

/** The answer a run waiting on the person asks for: the sign-in, or its question. */
function answerButton(r, rs) {
  if (rs !== 'you') return '';
  if (live.signIn && live.signIn.asked && r.action === 'audit') return `<a class="btn btn--primary" href="${href('/waiting/sign-in')}">${t('wt.signin.act')}</a>`;
  return r.question ? `<a class="btn btn--primary" href="${href('/waiting/questions')}">${t('ac.now.answer')}</a>` : '';
}
function queuedActions(r) {
  const q = ac.queue().map(x => x.id), i = q.indexOf(r.id);
  return `<div class="actions"><button class="btn btn--secondary" data-act="ac-move" data-id="${esc(r.id)}" data-dir="-1" ${i <= 0 ? 'disabled' : ''}>${icon('chev', 'ac-rot-up')}${t('ac.line.up')}</button>
      <button class="btn btn--secondary" data-act="ac-move" data-id="${esc(r.id)}" data-dir="1" ${i < 0 || i === q.length - 1 ? 'disabled' : ''}>${icon('chev', 'ac-rot-down')}${t('ac.line.down')}</button>
      <button class="btn btn--plain" data-act="ac-remove" data-id="${esc(r.id)}">${t('ac.line.remove')}</button>
      <p class="actions__note">${t('ac.line.note')}</p></div>`;
}
/** Beside Retry: close a stopped fix batch, get the app running, or pick another problem. */
function retryExtra(r, rs) {
  if (r.verb === 'fix' && rs === 'stopped') return `<button class="btn btn--secondary" data-act="sheet" data-sheet="action:fix_abandon">${t('ac.run.close_batch')}</button>`;
  if (r.action === 'run_setup' || r.action === 'safety_net') return `<button class="btn btn--secondary" data-act="sheet" data-sheet="action:run_try">${t('ac.run.get_running')}</button>`;
  return rs === 'unchanged' ? `<a class="btn btn--secondary" href="${href('/problems', { who: 'eaos' })}">${t('ac.run.pick_other')}</a>` : '';
}
function endedActions(r, ask) {
  if (store.awaitsApproval(r)) return `<div class="actions"><a class="btn btn--primary" href="${href('/waiting/' + enc(r.id))}">${icon('seal')}${t('ac.run.r12.decide')}</a>${ask}<p class="actions__note">${t('ac.run.r12.note')}</p></div>`;
  if (r.outcome) return `<div class="actions"><a class="btn btn--secondary" href="${href('/waiting/decided')}">${t('ac.run.r12.see_decided')}</a>${ask}</div>`;
  if (r.action === 'audit' && ac.flowOfRun(r)) {
    return `<div class="actions"><a class="btn btn--primary" href="${href('/problems')}">${esc(t('ac.run.see_problems', { problems: tn('pl.problem', model.totals().problems) }))}</a>
      <a class="btn btn--quiet" href="${href('/activity/run/' + enc(r.id), { replay: '10' })}">${icon('play')}${t('ac.run.replay10')}</a>
      <a class="btn btn--quiet" href="${href('/activity/run/' + enc(r.id), { replay: '30' })}">${t('ac.run.replay30')}</a>
      <p class="actions__note">${t('ac.run.redo.note')}</p></div>`;
  }
  return `<div class="actions">${ask}</div>`;
}
const UNDONE = ['failed', 'stopped', 'unchanged'];
function actionsHTML(r, rs) {
  if (offline()) return `<div class="actions"><button class="btn btn--secondary" data-act="sheet" data-sheet="open-live">${icon('lock')}${t('ac.run.live_only')}</button></div>`;
  const ask = `<a class="btn btn--quiet" href="${href('/ask', { run: r.id })}">${icon('ask')}${t(UNDONE.includes(rs) ? 'ac.run.ask_why' : 'ac.run.ask')}</a>`;
  if (['running', 'paused', 'you'].includes(rs)) return `<div class="actions">${answerButton(r, rs)}${controls(r)}${ask}</div>`;
  if (rs === 'queued') return queuedActions(r);
  if (UNDONE.includes(rs)) {
    return `<div class="actions"><button class="btn btn--primary" data-act="ac-ctl" data-op="retry" data-id="${esc(r.id)}">${icon('retry')}${t('ac.ctl.retry')}</button>${retryExtra(r, rs)}${ask}
      <p class="actions__note">${t('ac.ctl.retry.note')}</p></div>`;
  }
  return endedActions(r, ask);
}

/* ---------- the timeline (RUN-05) ---------- */
const GLY = { action: ['play', 'ink-2'], state: ['circle', 'ink-2'], step: ['dash', 'muted'], read: ['file', 'muted'], edit: ['code', 'ink-2'], screenshot: ['screen', 'ink-2'],
  progress: ['layers', 'ink-2'], question: ['waiting', 'accent'], answer: ['check', 'ok'], result: ['check', 'ok'], error: ['fail', 'danger'], say: ['ai', 'ai'] };
function eventGlyph(e) {
  const m = e.kind === 'check' ? (e.data.passed === false ? ['fail', 'danger'] : ['check', 'ok']) : GLY[e.kind] || ['dash', 'muted'];
  return icon(m[0], 'icon--sm ac-c-' + m[1]);
}
function diffHTML(diff) {
  return `<div class="code diff">${diffLines(String(diff).split('\n').slice(0, 300))}</div>`;
}
/** A run's technical words, folded. */
const techFold = e => (e.detail ? `<details class="ac-ev-fold"><summary>${t('ac.run.tech')}${icon('chev-down', 'icon--sm muted')}</summary><div class="code pad-2-3 pre">${esc(e.detail)}</div></details>` : '');
/** An edit: its problem, its files, whether it was kept, and its diff folded. */
function editBody(d, tx) {
  return `<div>${d.card ? `<a class="link" href="${href('/problems/' + enc(d.card))}">${code(d.card)}</a> ` : ''}${tx}</div>
        <div class="small ink-2">${(d.paths || []).map(code).join(' ')} ${d.kept === true ? `<span class="tag tag--ok">${icon('check')}${t('ac.ev.kept')}</span>` : d.kept === false ? `<span class="tag tag--state">${t('ac.ev.back')}</span>` : ''}</div>
        ${d.diff ? `<details class="ac-ev-fold"><summary>${t('ac.ev.diff')}${icon('chev-down', 'icon--sm muted')}</summary>${diffHTML(d.diff)}</details>` : ''}`;
}
/** A screenshot: its route, width, and whether before or after the change. */
function shotBody(d, tx) {
  return `<div>${tx}</div><div class="small ink-2">${code(d.route || '')} ${d.viewport ? esc(t('ac.ev.width', { w: d.viewport })) : ''} ${d.when ? esc(t('ac.ev.' + (d.when === 'before' ? 'before' : 'after'))) : ''}</div>`;
}
function eventBody(e) {
  const d = e.data || {}, tx = rich(L(e.text));
  switch (e.kind) {
    case 'edit':
      return editBody(d, tx);
    case 'screenshot':
      return shotBody(d, tx);
    case 'question':
      return `<div>${tx}</div><div class="small ink-2"><a class="link" href="${href('/waiting/questions')}">${t('ac.ev.asked')}</a></div>`;
    case 'say':
      return `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${t('ai.label')}</span>${md(d.words || L(e.text))}</div>`;
    case 'error':
      return `<div>${tx}</div>${techFold(e)}`;
    case 'progress':
      return `<div>${tx}</div>`;
    default:      // a result the assistant wrote may hold tables and lists: drawn as Markdown when it has lines
      return `${/\n/.test(L(e.text) || '') ? md(L(e.text)) : `<div>${tx}</div>`}${techFold(e)}`;
  }
}
function itemHTML(item) {
  if (item.kind === 'reads') {
    const first = item.events[0];
    const files = item.events.map(e => (e.data && e.data.path) || L(e.text));
    return `<li class="ac-tl__item"><span class="ac-tl__t">${ac.clock(first.at)}</span><span class="ac-tl__g">${eventGlyph(first)}</span>
      <div class="ac-tl__b small"><details class="ac-ev-fold"><summary>${esc(tn('ac.pl.read', files.length))}${icon('chev-down', 'icon--sm muted')}</summary>
        <ul class="ac-files">${files.slice(0, 80).map(f => `<li><bdi class="mono">${esc(f)}</bdi></li>`).join('')}</ul></details></div></li>`;
  }
  const e = item.event;
  return `<li class="ac-tl__item"><span class="ac-tl__t">${ac.clock(e.at)}</span><span class="ac-tl__g">${eventGlyph(e)}</span><div class="ac-tl__b small">${eventBody(e)}</div></li>`;
}
function timeline(r, view, events, all) {
  const items = view.items;
  const shown = all || items.length <= SHOWN ? items : items.slice(-SHOWN);
  return `<section class="section" aria-labelledby="tl-h"><div class="section-head"><h2 id="tl-h">${t('ac.run.happened')}</h2>
      ${shown.length < items.length ? `<a class="link small" href="${href('/activity/run/' + enc(r.id), { all: '1' })}">${esc(t('ac.run.happened.trim', { n: num(shown.length), total: num(items.length) }))}</a>` : ''}</div>
    <div class="panel panel__pad">${!client ? `<p class="small muted">${t('ac.run.live_only')}</p>` : !events.length && followOver(r) ? `<p class="small muted">${t('ac.run.trimmed')}</p>` : !events.length ? `<p class="small muted" aria-busy="true">${t('st.loading')}</p>` : `<ol class="ac-tl">${shown.map(itemHTML).join('')}</ol>`}</div></section>`;
}

/* ---------- its facts (RUN-04, RUN-11, AST-03) ---------- */
/** What the run is, its state, who started it, when, and how long it took. */
function whatRows(r, rs) {
  const rows = [[t('ac.f.label'), esc(ac.runLabel(r))], [t('ac.f.kind'), esc(ac.kindWord(r))], [t('ac.f.state'), ac.mark(rs)]];
  if (rs === 'queued' && r.position) rows.push([t('ac.f.position'), esc(t('ac.line.nth', { n: num(r.position) }))]);
  rows.push([t('ac.f.who'), esc(ac.whoWord(r))], [t('ac.f.by'), esc(t('ac.line.by.' + byOf(r)))], [t('ac.f.created'), ac.when(r.created)]);
  const m = ac.took(r);
  if (ac.ended(r) && m) rows.push([t('ac.f.took'), esc(ac.minutes(m))]);
  else if (r.started && rs !== 'queued') rows.push([t('ac.f.elapsed'), ac.runTicker(r, r.started)]);
  rows.push([t('ac.f.attempt'), num(r.attempt || 1)]);
  return rows;
}
const cardsValue = cards => `${esc(tn('pl.problem', cards.length))}: ${cards.slice(0, 4).map(id => `<a class="link" href="${href('/problems/' + enc(id))}">${code(id)}</a>`).join(' ')}${cards.length > 4 ? ' …' : ''}`;
const branchValue = wb => (wb && wb.name ? `${wb.state === 'exists' ? `<a class="link" href="${href('/project/branches/' + enc(wb.name))}">${code(wb.name)}</a>` : code(wb.name)} ${esc(has('ac.f.wb.' + wb.state) ? t('ac.f.wb.' + wb.state) : wb.state)}` : esc(t('ac.f.wb.none')));
/** What the run works on: its problems, the code it was made on, its folder and its work branch. */
function workRows(r) {
  const rows = [];
  const cards = r.cards || [];
  if (cards.length) rows.push([t('ac.f.problems'), cardsValue(cards)]);
  if ((r.left_out || []).length) rows.push([t('ac.f.left'), esc(tn('pl.problem', r.left_out.length))]);
  const c = r.context || {};
  if (c.analysis_branch) rows.push([t('ac.f.made_on'), t('ac.f.made_on.v', { branch: code(c.analysis_branch), commit: code(String(c.analysis_commit || '').slice(0, 7)) })]);
  if (c.checkout) rows.push([t('ac.f.folder'), code(c.checkout)]);
  rows.push([t('ac.f.work_branch'), branchValue(r.work_branch)]);
  return rows;
}
/** What the run's assistant used: its tokens and cost, or why it is not measured. */
function usedValue(r, u, tok) {
  return r.mode === 'handoff' ? ac.nmTag(t('ac.f.used.handoff')) : r.mode === 'direct' || !r.assistant ? ac.nmTag(t('ac.f.used.direct'))
    : tok ? `${esc(ac.tokens(tok))}${u.cost_usd != null ? `, ${ac.money(u.cost_usd)}` : ac.ended(r) ? '' : `, ${t('ac.f.used.cost_later')}`}` : ac.nmTag(t(ac.ended(r) ? 'ac.f.used.none' : 'ac.f.used.cost_later'));
}
function factsHTML(r, rs, events) {
  const rows = whatRows(r, rs).concat(workRows(r));
  const u = r.usage, tok = ac.usedTokens(u);
  rows.push([t('ac.f.used'), usedValue(r, u, tok)]);
  if (events.length) rows.push([t('ac.f.record'), esc(t('ac.f.record.ok', { n: num(events.length) }))]);
  return `<dl class="facts ac-facts">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
    ${tok ? `<p class="small muted mt-2">${t('ac.f.used.note')} <a class="link" href="${href('/project/assistants')}">${t('proj.assistants')}</a></p>` : ''}`;
}

function notFound(id) {
  return `<div class="page">${ac.back('/activity', t('nav.activity'))}<div class="panel empty mt-3"><h1 class="empty__title">${esc(t(offline() ? 'ac.run.offline' : 'ac.run.notfound', { id }))}</h1>
    <p class="small ink-2">${t(offline() ? 'ac.act.guide.offline' : 'ac.run.notfound.guide')}</p><a class="btn btn--secondary" href="${href('/activity/runs')}">${t('ac.runs.title')}</a></div></div>`;
}

/** The run's state, kind and id, and whether it came from the terminal. */
const topHTML = (r, rs) => `<div class="context">${ac.mark(rs)}<span class="tag tag--state">${esc(ac.kindWord(r))}</span>${byOf(r) === 'terminal' ? `<span class="tag tag--state">${icon('terminal')}${t('ac.line.by.terminal')}</span>` : ''}<bdi class="mono muted" style="align-self:center">${esc(r.id)}</bdi></div>`;
/** The replay's stamp: how fast, how far, and the way back to the run. */
const stampHTML = (r, replaying, list) => (replaying ? `<div class="ac-stamp" role="status">${icon('history')}<span><b>${esc(t('ac.replay.stamp', { x: num(replaying) }))}</b> <span class="ac-stamp__at">${esc(t('ac.replay.at', { n: num(finished(list)), total: num(list.length) }))}</span></span>
    <a class="btn btn--secondary btn--sm" href="${href('/activity/run/' + enc(r.id))}">${t('ac.replay.back')}</a></div>` : '');
/** A check's progress bar under its clock while it is not done. */
const progressHTML = (r, rs, list) => (r.action === 'audit' && list.length && rs !== 'done' ? `${ac.progressBar(finished(list) / list.length, '')}<p class="small ink-2 ac-under">${esc(t(rs === 'stopped' ? 'ac.run.check.stopped.at' : 'ac.run.check.at', { done: num(finished(list)), total: num(list.length), running: num(list.filter(s => ['running', 'you', 'paused'].includes(s.state)).length) }))}</p>` : '');
/** A check's stages on their board, with the switch that follows the running one. */
function stagesHTML(r, rs, list) {
  return r.action === 'audit' ? `<section class="section" aria-labelledby="stg-h"><div class="section-head"><h2 id="stg-h">${t('ac.run.stages')}</h2>
      ${rs === 'running' ? `<label class="ac-inline-switch small ink-2"><span class="switch"><input type="checkbox" data-change="ac-follow" data-fk="follow" ${follow ? 'checked' : ''} aria-label="${esc(t('ac.run.follow'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span>${t('ac.run.follow')}</label>` : ''}</div>
      ${list.length ? `<p class="small ink-2 mb-3"><span id="ac-stage-sum">${esc(summary(counts(list)))}</span> ${t('ac.run.stages.help')}</p>
      <div id="ac-board">${board(list, rs !== 'running' || follow)}</div>
      <p class="small muted ac-iline mt-2">${icon('ai', 'icon--sm ac-c-ai')}<span>${t('ac.run.stages.ai')}</span></p>` : `<p class="small muted">${t(rs === 'queued' ? 'ac.run.stages.later' : 'ac.run.stages.older')}</p>`}</section>` : '';
}
/** What the run does now, while it runs. */
const nowHTML = (view, rs) => (view.now && ['running', 'paused'].includes(rs) ? `<p class="small ink-2" role="status">${rich(L(view.now))}</p>` : '');
/** The question a waiting run asks, with the way to answer it. */
const questionHTML = (view, rs) => (view.question && rs === 'you' ? `<div class="panel row row--you mt-4" role="status">${icon('waiting')}<span class="row__main small">${rich(L(view.question.text))}</span><a class="btn btn--secondary btn--sm" href="${href('/waiting/questions')}">${t('ac.now.answer')}</a></div>` : '');
/** A check's stages as they stood at the replay's second, else as they are. */
const listOf = (flow, r, replaying) => (flow ? stagesOf(flow, r, replaying ? replay.at || 0 : null) : []);
const clockOf = (r, rs, flow, list, replaying) => (r.action === 'audit' && !replaying && rs !== 'queued' ? clockHTML(r, flow, list) : '');

function runPage(ctx) {
  const id = ctx.params.id;
  const r = ac.runOf(id);
  if (!r) return live.loaded || offline() ? notFound(id) : `<div class="page" aria-busy="true"><h1 class="lede">${t('st.loading')}</h1></div>`;
  const events = eventsOf(r);
  const view = derive.deriveRun(events, r);
  const rs = ac.runState(r);
  const flow = ac.flowOfRun(r);
  const replaying = flow && ctx.query.replay && rs === 'done' ? Number(ctx.query.replay) : null;
  const list = listOf(flow, r, replaying);
  const top = topHTML(r, rs);
  const stamp = stampHTML(r, replaying, list);
  const clock = clockOf(r, rs, flow, list, replaying);
  const progress = progressHTML(r, rs, list);
  const stages = stagesHTML(r, rs, list);
  const facts = factsHTML(r, rs, events);
  const said = guide(r, rs, list);
  return `<div class="page ac-page--run">
    ${ac.back('/activity', t('nav.activity'))}
    ${top}
    <h1 class="lede">${esc(lede(r, rs, view, list))}</h1>
    ${said ? `<p class="guide">${said}</p>` : ''}
    ${lostHTML(r, rs, list)}
    ${nowHTML(view, rs)}
    ${actionsHTML(r, rs)}
    ${stamp}
    <div class="ac-run-cols">
      <div class="ac-run-main">
        ${clock}
        ${progress}
        ${questionHTML(view, rs)}
        ${resultHTML(r, rs, view)}
        ${r.verb === 'fix' ? fixProgress(r, rs, view) : ''}
        ${r.mode === 'handoff' ? handoffHTML(r) : ''}
        ${stages}
        ${timeline(r, view, events, ctx.query.all === '1')}
        <div class="panel only-phone section">${ac.fold('facts', t('ac.run.facts'), esc(t('ac.run.facts.sum', { who: ac.whoWord(r), when: fmtWhen(r.created) })), facts)}</div>
      </div>
      <aside class="ac-run-aside only-desk" aria-labelledby="facts-h"><div class="panel panel__pad"><h2 class="h2 mb-3" id="facts-h">${t('ac.run.facts')}</h2>${facts}</div></aside>
    </div>
  </div>`;
}

screen({
  id: 'S-15', path: '/activity/run/:id', place: 'activity', needs: ['cards', 'health', 'history'],
  title: ctx => ctx.params.id + ' - ' + t('nav.activity'), render: runPage,
  after(main, ctx) {
    const x = Number(ctx.query.replay);
    const r = ac.runOf(ctx.params.id), flow = r && ac.flowOfRun(r);
    if (!x || !flow || replay.timer) return;
    // CHK-11: the check's own stage times, stepped every second without tweening; only the board redraws
    replay = { id: r.id, at: 0, timer: setInterval(() => {
      const el = document.getElementById('ac-board');
      if (!el || parseHash().query.replay !== String(x)) { clearInterval(replay.timer); replay.timer = 0; return; }
      replay.at = Math.min(span(flow), replay.at + x);
      const list = stagesOf(flow, r, replay.at);
      el.innerHTML = board(list, true);  // nosemgrep: javascript.browser.security.insecure-document-method, javascript.browser.security.insecure-innerhtml -- the board escapes every text it shows
      const sum = document.getElementById('ac-stage-sum'); if (sum) sum.textContent = summary(counts(list));
      const at = document.querySelector('.ac-stamp__at'); if (at) at.textContent = t('ac.replay.at', { n: num(finished(list)), total: num(list.length) });
      if (replay.at >= span(flow)) { clearInterval(replay.timer); }
    }, 1000) };
  },
});
act('ac-follow', el => { follow = el.checked; refresh(); });
