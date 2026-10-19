// S-15 One run (RUN-04..12, CHK-07, CHK-08, CHK-11, FIX-07, FIX-10, SCR-04, CHT-05, AST-03): the run's record and its
// events, followed live (GET /api/runs/<id>/events, server-sent with Last-Event-ID) and derived into what happens now,
// the batches' progress, the question it waits on, the result or the error and the timeline (derive.deriveRun); a
// check's stages by layer from /api/progress, and the replay of a finished check at x10 or x30.
import {
  t, tn, L, num, esc, rich, icon, code, href, fmtWhen, screen, act, refresh, refreshSoon, afterRender, parseHash, offline, has,
  live, store, model, client, derive, ac,
} from 'eaos';
import { controls, byOf } from './activity.js';
import { stagesOf, board, counts, finished, summary, span, lostOf, stageTitle } from './stages.js';
import { clockHTML } from './clock.js';

const enc = encodeURIComponent;
const SHOWN = 60;                 // the newest timeline lines drawn; the rest one press away
const followed = {};              // run id -> {events, stop, done}
let follow = true;                // follow the running stage (CHK-08)
let replay = { id: null, at: null, timer: 0 };

/** The run's events, read once and then live while it runs. */
function eventsOf(r) {
  if (!client || r.trimmed) return [];
  let f = followed[r.id];
  if (!f) {
    f = followed[r.id] = { events: [], stop: null, over: false };
    // an ended run's stream ends once it has replayed: the reconnection that follows is not needed
    f.stop = client.follow(r.id, 0, event => { f.events.push(event); refreshSoon(); }, status => {
      if (status === 'reconnecting' && ac.ended(ac.runOf(r.id) || r)) { f.stop(); f.over = true; refreshSoon(); }
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
const pathName = p => (has('ac.path.' + p) ? t('ac.path.' + p) : p);
function checkLede(r, rs, list) {
  const at = { done: num(finished(list)), total: num(list.length), running: num(list.filter(s => ['running', 'you', 'paused'].includes(s.state)).length) };
  if (rs === 'done') {
    const own = ac.flowOfRun(r), lost = list.filter(lostOf).length;
    if (own && lost) return t('ac.run.check.lost.lede', { took: ac.minutes(ac.took(r) || 1), stages: tn('pl.stage', lost), problems: tn('pl.problem', model.totals().problems) });
    return own ? t('ac.run.check.done.lede', { took: ac.minutes(ac.took(r) || 1), problems: tn('pl.problem', model.totals().problems), health: model.health().score == null ? t('nm') : num(model.health().score) })
      : t('ac.run.done.lede', { took: ac.minutes(ac.took(r) || 1) });
  }
  if (rs === 'you') return t(live.signIn && live.signIn.asked ? 'ac.run.check.you.lede' : 'ac.run.check.q.lede');
  if (rs === 'paused') return t('ac.run.check.paused.lede', at);
  if (rs === 'stopped') return t(list.length ? 'ac.run.check.stopped.lede' : 'ac.run.check.stopped.early', at);
  if (rs === 'failed') return t('ac.run.failed.lede', { label: ac.runLabel(r) });
  if (rs === 'queued') return t('ac.run.queued.lede', { n: num(r.position || 1) });
  return list.length ? t('ac.run.check.lede', at) : t('ac.now.check');
}
function lede(r, rs, view, list) {
  if (r.action === 'audit') return checkLede(r, rs, list);
  const branch = r.result && r.result.branch;
  if (rs === 'queued') return t('ac.run.queued.lede', { n: num(r.position || 1) });
  if (rs === 'you') return t('ac.run.you.lede');
  if (rs === 'paused') return t('ac.run.paused.lede', { label: ac.runLabel(r) });
  if (rs === 'running') return r.verb === 'fix' ? t('ac.run.fix.lede', { done: num(view.edits), total: num((r.cards || []).length) }) : t('ac.run.running.lede', { label: ac.runLabel(r) });
  if (rs === 'stopped') return t(r.verb === 'fix' ? 'ac.run.fix.stopped.lede' : 'ac.run.stopped.lede');
  if (rs === 'failed') return t('ac.run.failed.lede', { label: ac.runLabel(r) });
  if (rs === 'unchanged') return t('ac.run.unchanged.lede');
  if (branch && r.outcome === 'accepted') return t('ac.run.r12.accepted', { target: ac.mergedInto(r) });
  if (branch && r.outcome === 'undone') return t('ac.run.r12.rejected');
  if (branch) return t('ac.run.r12.lede');
  return t('ac.run.done.lede2', { label: ac.runLabel(r), took: ac.minutes(ac.took(r) || 1) });
}
/** A check that ended with stages its assistant was lost in: which, why, when the assistant comes back, and the one
 *  press that runs them again (from the first of them). */
function lostHTML(r, rs, list) {
  const lost = r.action === 'audit' && rs === 'done' ? list.filter(lostOf) : [];
  if (!lost.length) return '';
  const first = lostOf(lost[0]), who = first.assistant || t('ac.run.lost.who');
  const why = /_limit$/.test(first.code) ? t('ac.run.lost.limit', { who }) : t('ac.run.lost.failed', { who });
  return `<div class="panel ac-refuse" role="note" style="margin:12px 0">
    <p><b>${esc(t('ac.run.lost.q', { stages: tn('pl.stage', lost.length) }))}</b> ${esc(why)}${first.resets ? ' ' + esc(t('ac.run.lost.resets', { at: first.resets })) : ''}</p>
    <p class="small ink-2">${esc(lost.map(s => stageTitle(s.id)).join(t('list.sep')))}</p>
    <div class="actions" style="margin-top:8px"><button class="btn btn--primary" data-act="sheet" data-sheet="redo:${esc(lost[0].id)}" data-fk="lost-redo">${t('ac.run.lost.act')}</button></div>
    <p class="small ink-2">${t('ac.run.lost.how')}</p></div>`;
}
function guide(r, rs, list) {
  if (r.action === 'audit') {
    if (rs === 'done' && list.length) { const c = counts(list); return t('ac.run.check.done.guide', { done: num(c.ok || 0), partial: num((c.failed || 0) + (c.partial || 0)), other: num(list.length - (c.ok || 0) - (c.failed || 0) - (c.partial || 0)) }); }
    if (rs === 'you') return t('ac.run.check.you.guide');
    if (rs === 'stopped' || rs === 'failed') return t('ac.run.check.stopped.guide');
    if (rs === 'running' || rs === 'paused') return t('ac.run.check.guide');
  }
  if (rs === 'queued') return t('ac.run.queued.guide');
  if (rs === 'you') return t('ac.run.you.guide');
  if (r.verb === 'fix' && rs === 'running') return t('ac.run.fix.guide');
  if (r.verb === 'fix' && (rs === 'stopped' || rs === 'failed')) return t('ac.run.fix.stopped.guide');
  if (rs === 'unchanged') return t('ac.run.unchanged.guide');
  if (r.result && r.result.branch) return t(r.outcome ? 'ac.run.r12.done.guide' : 'ac.run.r12.guide');
  return '';
}

function actionsHTML(r, rs) {
  if (offline()) return `<div class="actions"><button class="btn btn--secondary" data-act="sheet" data-sheet="open-live">${icon('lock')}${t('ac.run.live_only')}</button></div>`;
  const ask = `<a class="btn btn--quiet" href="${href('/ask', { run: r.id })}">${icon('ask')}${t(['failed', 'stopped', 'unchanged'].includes(rs) ? 'ac.run.ask_why' : 'ac.run.ask')}</a>`;
  if (['running', 'paused', 'you'].includes(rs)) {
    const answer = rs === 'you' ? (live.signIn && live.signIn.asked && r.action === 'audit' ? `<a class="btn btn--primary" href="${href('/waiting/sign-in')}">${t('wt.signin.act')}</a>`
      : r.question ? `<a class="btn btn--primary" href="${href('/waiting/questions')}">${t('ac.now.answer')}</a>` : '') : '';
    return `<div class="actions">${answer}${controls(r)}${ask}</div>`;
  }
  if (rs === 'queued') {
    const q = ac.queue().map(x => x.id), i = q.indexOf(r.id);
    return `<div class="actions"><button class="btn btn--secondary" data-act="ac-move" data-id="${esc(r.id)}" data-dir="-1" ${i <= 0 ? 'disabled' : ''}>${icon('chev', 'ac-rot-up')}${t('ac.line.up')}</button>
      <button class="btn btn--secondary" data-act="ac-move" data-id="${esc(r.id)}" data-dir="1" ${i < 0 || i === q.length - 1 ? 'disabled' : ''}>${icon('chev', 'ac-rot-down')}${t('ac.line.down')}</button>
      <button class="btn btn--plain" data-act="ac-remove" data-id="${esc(r.id)}">${t('ac.line.remove')}</button>
      <p class="actions__note">${t('ac.line.note')}</p></div>`;
  }
  if (['failed', 'stopped', 'unchanged'].includes(rs)) {
    const extra = r.verb === 'fix' && rs === 'stopped' ? `<button class="btn btn--secondary" data-act="sheet" data-sheet="action:fix_abandon">${t('ac.run.close_batch')}</button>`
      : r.action === 'run_setup' || r.action === 'safety_net' ? `<button class="btn btn--secondary" data-act="sheet" data-sheet="action:run_try">${t('ac.run.get_running')}</button>`
        : rs === 'unchanged' ? `<a class="btn btn--secondary" href="${href('/problems', { who: 'eaos' })}">${t('ac.run.pick_other')}</a>` : '';
    return `<div class="actions"><button class="btn btn--primary" data-act="ac-ctl" data-op="retry" data-id="${esc(r.id)}">${icon('retry')}${t('ac.ctl.retry')}</button>${extra}${ask}
      <p class="actions__note">${t('ac.ctl.retry.note')}</p></div>`;
  }
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

/* ---------- its result ---------- */
function resultHTML(r, rs, view) {
  const e = view.error;
  if (e && ['failed', 'stopped'].includes(rs)) {
    return `<section class="panel ac-result ac-result--fail" aria-label="${esc(t('ac.run.error'))}">
      <dl class="facts"><dt>${t('ac.run.what')}</dt><dd>${rich(L(e.text))}${e.reason ? ` <span class="small muted">${rich(e.reason)}</span>` : ''}</dd>
        ${e.what_now ? `<dt>${t('ac.run.todo')}</dt><dd>${rich(L(e.what_now))}</dd>` : ''}
        <dt>${t('ac.run.recoverable')}</dt><dd>${t(e.recoverable ? 'ac.run.recoverable.yes' : 'ac.run.recoverable.no')}</dd></dl>
      ${e.detail ? `<details class="ac-ev-fold"><summary>${t('ac.run.tech')}${icon('chev-down', 'icon--sm muted')}</summary><div class="code" style="padding:8px 12px;white-space:pre-wrap">${esc(e.detail)}</div></details>` : ''}</section>`;
  }
  const res = view.result || r.result;
  if (!res) return '';
  const d = res.diff_stat, tests = res.tests;
  const rows = [];
  if (res.branch) rows.push([t('ac.run.branch'), `<a class="link" href="${href('/project/branches/' + enc(res.branch))}">${code(res.branch)}</a>`]);
  if (d) rows.push([t('ac.run.diffstat'), `${esc(tn('pl.file_changed', d.files))} <bdi dir="ltr" class="num">+${num(d.insertions)} −${num(d.deletions)}</bdi>`]);
  /* older records carry only the engine's English sentence: its two numbers are read back so the page speaks the person's language */
  const said = tests && tests.kept == null && /^(\d+) change\(s\) passed every check; (\d+) left out/.exec(tests.summary || '');
  if (said) Object.assign(tests, { kept: +said[1], left: +said[2] });
  if (tests) rows.push([t('ac.run.tests'), ac.mark(tests.passed ? 'ok' : tests.passed === false ? 'failed' : 'skipped', esc(tests.kept != null ? t('ac.run.tests.n', { kept: tn('ac.run.change', tests.kept), left: num(tests.left || 0) }) : t(tests.passed ? 'wt.fix.tests.ok' : 'wt.fix.tests.no')))]);
  if ((r.left_out || []).length) rows.push([t('ac.run.leftout'), r.left_out.slice(0, 8).map(x => code(x.id)).join(' ')]);
  if ((res.cards_closed || []).length) rows.push([t('ac.run.closes'), res.cards_closed.slice(0, 12).map(c => `<a class="link" href="${href('/problems/' + enc(c))}">${code(c)}</a>`).join(' ')]);
  if ((res.indicators || []).length) rows.push([t('ac.run.indicators'), res.indicators.map(x => esc(t('ac.run.indicator', { id: x.id, before: x.before == null ? '—' : num(x.before), after: x.after == null ? '—' : num(x.after) }))).join('<br>')]);
  if (res.branch) rows.push([t('ac.run.decision'), r.outcome ? esc(t(r.outcome === 'accepted' ? 'wt.done.accepted' : 'wt.done.rejected', { when: fmtWhen(r.decided), target: ac.mergedInto(r) })) : `<span class="ac-c-accent">${t('ac.out.waits')}</span>`]);
  if (r.action === 'audit' && ac.flowOfRun(r)) {
    rows.push([t('ac.run.check.found'), `<a class="link" href="${href('/problems')}">${esc(tn('pl.problem', model.totals().problems))}</a>`]);
    rows.push([t('ac.run.check.paths'), esc(((r.inputs && r.inputs.paths) || ['complete']).map(pathName).join(t('list.sep')))]);
  }
  const words = typeof res.answer === 'string' || r.action !== 'audit' ? ac.answerHTML(res.answer) : '';
  if (!rows.length && !words) return '';
  return `<section class="panel ac-result ${r.outcome === 'undone' ? '' : 'ac-result--ok'}" aria-label="${esc(t('ac.run.result'))}">
    ${rows.length ? `<dl class="facts">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>` : ''}${words}</section>`;
}

/** FIX-07: the batches' progress and every problem of the batch, kept or taken back, from the edit events. */
function fixProgress(r, rs, view, events) {
  const cards = r.cards || [];
  if (!cards.length) return '';
  const byCard = {};
  events.filter(e => e.kind === 'edit' && e.data && e.data.card).forEach(e => { byCard[e.data.card] = e.data.kept; });
  const share = derive.share(view.batches);
  const tried = Object.keys(byCard).length;
  const row = id => {
    const p = model.problem(id);
    const k = byCard[id];
    const st = k === true ? 'ok' : k === false ? 'unchanged' : rs === 'running' ? 'waiting' : ac.ended(r) ? 'notreached' : 'waiting';
    const word = k === true ? t('ac.fix.p.kept') : k === false ? t('ac.ev.back') : ac.stateWord(st);
    return `<li class="row">${ac.glyph(st)}<span class="row__main"><span class="row__title small"><a class="link" href="${href('/problems/' + enc(id))}">${code(id)}</a> ${p ? rich(L(p.title)) : ''}</span>
      <span class="row__meta" style="display:block">${esc(word)}</span></span></li>`;
  };
  const shown = cards.slice(0, 12);
  return `<section class="section" aria-labelledby="fp-h"><div class="section-head"><h2 id="fp-h">${t('ac.fix.progress')}</h2><span class="small muted num">${esc(t('ac.now.fix.sub', { done: num(tried), total: num(cards.length) }))}</span></div>
    ${ac.progressBar(share != null ? share : tried / cards.length, t('ac.fix.progress'))}
    <ul class="panel rows" style="margin-top:12px">${shown.map(row).join('')}${cards.length > shown.length ? `<li class="row small muted" style="min-height:44px">+ ${esc(tn('pl.problem', cards.length - shown.length))}</li>` : ''}</ul></section>`;
}

/** RUN-09: the request that waits for the person's assistant elsewhere, to copy. */
function handoffHTML(r) {
  const req = r.handoff;
  if (!req) return '';
  return `<section class="section" aria-labelledby="ho-h"><div class="section-head"><h2 id="ho-h">${t('ac.ho.title')}</h2></div>
    <div class="panel panel__pad ac-stack"><p class="small ink-2">${t('ac.ho.why')}</p>
      ${['ar', 'en'].filter(l => req[l]).map(l => `<div class="ac-req"><span class="block-title">${t('lang.' + l)}</span><div class="code ac-req__text" dir="${l === 'ar' ? 'rtl' : 'ltr'}" style="white-space:pre-wrap">${esc(req[l])}</div>
        <button class="btn btn--secondary btn--sm" data-act="copy" data-text="${esc(req[l])}">${icon('copy')}${t('copy')}</button></div>`).join('')}</div></section>`;
}

/* ---------- the timeline (RUN-05) ---------- */
const GLY = { action: ['play', 'ink-2'], state: ['circle', 'ink-2'], step: ['dash', 'muted'], read: ['file', 'muted'], edit: ['code', 'ink-2'], screenshot: ['screen', 'ink-2'],
  progress: ['layers', 'ink-2'], question: ['waiting', 'accent'], answer: ['check', 'ok'], result: ['check', 'ok'], error: ['fail', 'danger'], say: ['ai', 'ai'] };
function eventGlyph(e) {
  const m = e.kind === 'check' ? (e.data.passed === false ? ['fail', 'danger'] : ['check', 'ok']) : GLY[e.kind] || ['dash', 'muted'];
  return icon(m[0], 'icon--sm ac-c-' + m[1]);
}
function diffHTML(diff) {
  return `<div class="code diff">${String(diff).split('\n').slice(0, 300).map((l, i) => `<div class="code__line ${l.startsWith('+') && !l.startsWith('+++') ? 'code__line--add' : l.startsWith('-') && !l.startsWith('---') ? 'code__line--del' : ''}"><span class="code__ln">${i + 1}</span><span>${esc(l)}</span></div>`).join('')}</div>`;
}
function eventBody(e) {
  const d = e.data || {}, tx = rich(L(e.text));
  switch (e.kind) {
    case 'edit':
      return `<div>${d.card ? `<a class="link" href="${href('/problems/' + enc(d.card))}">${code(d.card)}</a> ` : ''}${tx}</div>
        <div class="small ink-2">${(d.paths || []).map(code).join(' ')} ${d.kept === true ? `<span class="tag tag--ok">${icon('check')}${t('ac.ev.kept')}</span>` : d.kept === false ? `<span class="tag tag--state">${t('ac.ev.back')}</span>` : ''}</div>
        ${d.diff ? `<details class="ac-ev-fold"><summary>${t('ac.ev.diff')}${icon('chev-down', 'icon--sm muted')}</summary>${diffHTML(d.diff)}</details>` : ''}`;
    case 'screenshot':
      return `<div>${tx}</div><div class="small ink-2">${code(d.route || '')} ${d.viewport ? esc(t('ac.ev.width', { w: d.viewport })) : ''} ${d.when ? esc(t('ac.ev.' + (d.when === 'before' ? 'before' : 'after'))) : ''}</div>`;
    case 'question':
      return `<div>${tx}</div><div class="small ink-2"><a class="link" href="${href('/waiting/questions')}">${t('ac.ev.asked')}</a></div>`;
    case 'say':
      return `<div class="ai-block"><span class="ai-block__label">${icon('ai', 'icon--sm')}${t('ai.label')}</span><p class="small" style="margin-top:4px">${rich(d.words || L(e.text))}</p></div>`;
    case 'error':
      return `<div>${tx}</div>${e.detail ? `<details class="ac-ev-fold"><summary>${t('ac.run.tech')}${icon('chev-down', 'icon--sm muted')}</summary><div class="code" style="padding:8px 12px;white-space:pre-wrap">${esc(e.detail)}</div></details>` : ''}`;
    case 'progress':
      return `<div>${tx}</div>`;
    default:
      return `<div>${tx}</div>${e.detail ? `<details class="ac-ev-fold"><summary>${t('ac.run.tech')}${icon('chev-down', 'icon--sm muted')}</summary><div class="code" style="padding:8px 12px;white-space:pre-wrap">${esc(e.detail)}</div></details>` : ''}`;
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
function factsHTML(r, rs, events) {
  const rows = [[t('ac.f.label'), esc(ac.runLabel(r))], [t('ac.f.kind'), esc(ac.kindWord(r))], [t('ac.f.state'), ac.mark(rs)]];
  if (rs === 'queued' && r.position) rows.push([t('ac.f.position'), esc(t('ac.line.nth', { n: num(r.position) }))]);
  rows.push([t('ac.f.who'), esc(ac.whoWord(r))], [t('ac.f.by'), esc(t('ac.line.by.' + byOf(r)))], [t('ac.f.created'), ac.when(r.created)]);
  const m = ac.took(r);
  if (ac.ended(r) && m) rows.push([t('ac.f.took'), esc(ac.minutes(m))]);
  else if (r.started && rs !== 'queued') rows.push([t('ac.f.elapsed'), ac.ticker(r.started)]);
  rows.push([t('ac.f.attempt'), num(r.attempt || 1)]);
  const cards = r.cards || [];
  if (cards.length) rows.push([t('ac.f.problems'), `${esc(tn('pl.problem', cards.length))}: ${cards.slice(0, 4).map(id => `<a class="link" href="${href('/problems/' + enc(id))}">${code(id)}</a>`).join(' ')}${cards.length > 4 ? ' …' : ''}`]);
  if ((r.left_out || []).length) rows.push([t('ac.f.left'), esc(tn('pl.problem', r.left_out.length))]);
  const c = r.context || {};
  if (c.analysis_branch) rows.push([t('ac.f.made_on'), t('ac.f.made_on.v', { branch: code(c.analysis_branch), commit: code(String(c.analysis_commit || '').slice(0, 7)) })]);
  if (c.checkout) rows.push([t('ac.f.folder'), code(c.checkout)]);
  const wb = r.work_branch;
  rows.push([t('ac.f.work_branch'), wb && wb.name ? `${wb.state === 'exists' ? `<a class="link" href="${href('/project/branches/' + enc(wb.name))}">${code(wb.name)}</a>` : code(wb.name)} ${esc(has('ac.f.wb.' + wb.state) ? t('ac.f.wb.' + wb.state) : wb.state)}` : esc(t('ac.f.wb.none'))]);
  const u = r.usage, tok = ac.usedTokens(u);
  rows.push([t('ac.f.used'), r.mode === 'handoff' ? ac.nmTag(t('ac.f.used.handoff')) : r.mode === 'direct' || !r.assistant ? ac.nmTag(t('ac.f.used.direct'))
    : tok ? `${esc(ac.tokens(tok))}${u.cost_usd != null ? `, ${ac.money(u.cost_usd)}` : ac.ended(r) ? '' : `, ${t('ac.f.used.cost_later')}`}` : ac.nmTag(t(ac.ended(r) ? 'ac.f.used.none' : 'ac.f.used.cost_later'))]);
  if (events.length) rows.push([t('ac.f.record'), esc(t('ac.f.record.ok', { n: num(events.length) }))]);
  return `<dl class="facts ac-facts">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
    ${tok ? `<p class="small muted" style="margin-top:8px">${t('ac.f.used.note')} <a class="link" href="${href('/project/assistants')}">${t('proj.assistants')}</a></p>` : ''}`;
}

function notFound(id) {
  return `<div class="page">${ac.back('/activity', t('nav.activity'))}<div class="panel empty" style="margin-top:12px"><h1 class="empty__title">${esc(t(offline() ? 'ac.run.offline' : 'ac.run.notfound', { id }))}</h1>
    <p class="small ink-2">${t(offline() ? 'ac.act.guide.offline' : 'ac.run.notfound.guide')}</p><a class="btn btn--secondary" href="${href('/activity/runs')}">${t('ac.runs.title')}</a></div></div>`;
}

function runPage(ctx) {
  const id = ctx.params.id;
  const r = ac.runOf(id);
  if (!r) return live.loaded || offline() ? notFound(id) : `<div class="page" aria-busy="true"><h1 class="lede">${t('st.loading')}</h1></div>`;
  const events = eventsOf(r);
  const view = derive.deriveRun(events, r);
  const rs = ac.runState(r);
  const flow = ac.flowOfRun(r);
  const replaying = flow && ctx.query.replay && rs === 'done' ? Number(ctx.query.replay) : null;
  const list = flow ? stagesOf(flow, r, replaying ? replay.at || 0 : null) : [];
  const top = `<div class="context">${ac.mark(rs)}<span class="tag tag--state">${esc(ac.kindWord(r))}</span>${byOf(r) === 'terminal' ? `<span class="tag tag--state">${icon('terminal')}${t('ac.line.by.terminal')}</span>` : ''}<bdi class="mono muted" style="align-self:center">${esc(r.id)}</bdi></div>`;
  const stamp = replaying ? `<div class="ac-stamp" role="status">${icon('history')}<span><b>${esc(t('ac.replay.stamp', { x: num(replaying) }))}</b> <span class="ac-stamp__at">${esc(t('ac.replay.at', { n: num(finished(list)), total: num(list.length) }))}</span></span>
    <a class="btn btn--secondary btn--sm" href="${href('/activity/run/' + enc(r.id))}">${t('ac.replay.back')}</a></div>` : '';
  const clock = r.action === 'audit' && !replaying && rs !== 'queued' ? clockHTML(r, flow, list) : '';
  const progress = r.action === 'audit' && list.length && rs !== 'done' ? `${ac.progressBar(finished(list) / list.length, '')}<p class="small ink-2 ac-under">${esc(t(rs === 'stopped' ? 'ac.run.check.stopped.at' : 'ac.run.check.at', { done: num(finished(list)), total: num(list.length), running: num(list.filter(s => ['running', 'you', 'paused'].includes(s.state)).length) }))}</p>` : '';
  const stages = r.action === 'audit' ? `<section class="section" aria-labelledby="stg-h"><div class="section-head"><h2 id="stg-h">${t('ac.run.stages')}</h2>
      ${rs === 'running' ? `<label class="ac-inline-switch small ink-2"><span class="switch"><input type="checkbox" data-change="ac-follow" data-fk="follow" ${follow ? 'checked' : ''} aria-label="${esc(t('ac.run.follow'))}"><span class="switch__track"></span><span class="switch__thumb"></span></span>${t('ac.run.follow')}</label>` : ''}</div>
      ${list.length ? `<p class="small ink-2" style="margin-bottom:12px"><span id="ac-stage-sum">${esc(summary(counts(list)))}</span> ${t('ac.run.stages.help')}</p>
      <div id="ac-board">${board(list, rs !== 'running' || follow)}</div>
      <p class="small muted ac-iline" style="margin-top:8px">${icon('ai', 'icon--sm ac-c-ai')}<span>${t('ac.run.stages.ai')}</span></p>` : `<p class="small muted">${t(rs === 'queued' ? 'ac.run.stages.later' : 'ac.run.stages.older')}</p>`}</section>` : '';
  const facts = factsHTML(r, rs, events);
  const said = guide(r, rs, list);
  return `<div class="page ac-page--run">
    ${ac.back('/activity', t('nav.activity'))}
    ${top}
    <h1 class="lede">${esc(lede(r, rs, view, list))}</h1>
    ${said ? `<p class="guide">${said}</p>` : ''}
    ${lostHTML(r, rs, list)}
    ${view.now && ['running', 'paused'].includes(rs) ? `<p class="small ink-2" role="status">${rich(L(view.now))}</p>` : ''}
    ${actionsHTML(r, rs)}
    ${stamp}
    <div class="ac-run-cols">
      <div class="ac-run-main">
        ${clock}
        ${progress}
        ${view.question && rs === 'you' ? `<div class="panel row row--you" role="status" style="margin-top:16px">${icon('waiting')}<span class="row__main small">${rich(L(view.question.text))}</span><a class="btn btn--secondary btn--sm" href="${href('/waiting/questions')}">${t('ac.now.answer')}</a></div>` : ''}
        ${resultHTML(r, rs, view)}
        ${r.verb === 'fix' ? fixProgress(r, rs, view, events) : ''}
        ${r.mode === 'handoff' ? handoffHTML(r) : ''}
        ${stages}
        ${timeline(r, view, events, ctx.query.all === '1')}
        <div class="panel only-phone section">${ac.fold('facts', t('ac.run.facts'), esc(t('ac.run.facts.sum', { who: ac.whoWord(r), when: fmtWhen(r.created) })), facts)}</div>
      </div>
      <aside class="ac-run-aside only-desk" aria-labelledby="facts-h"><div class="panel panel__pad"><h2 class="h2" id="facts-h" style="margin-bottom:12px">${t('ac.run.facts')}</h2>${facts}</div></aside>
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
      el.innerHTML = board(list, true);
      const sum = document.getElementById('ac-stage-sum'); if (sum) sum.textContent = summary(counts(list));
      const at = document.querySelector('.ac-stamp__at'); if (at) at.textContent = t('ac.replay.at', { n: num(finished(list)), total: num(list.length) });
      if (replay.at >= span(flow)) { clearInterval(replay.timer); }
    }, 1000) };
  },
});
act('ac-follow', el => { follow = el.checked; refresh(); });
